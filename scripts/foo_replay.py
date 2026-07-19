#!/usr/bin/env python3
"""
foo_replay.py — replay harness for the foo-cartridge-replay-v1 spec.

Sibling to foo_cartridge.py; stdlib only. A clean-room receiver needs
exactly three things: this file, foo_cartridge.py, and a foo.zip.
No repo checkout, no pip installs, no API keys.

Subcommands:
  mech PATH             Canonically verify the cartridge and emit the
                        mechanical skeleton of a replay statement — the
                        fields no model is ever trusted to compute.
  playback PATH         Emit the paste-ready replay preamble followed by
                        payload.md, for any web chat. manifest.json NEVER
                        goes to the model: models cannot compute SHA-256,
                        so the manifest belongs to the receiver's scorer.
  score PATH OBSERVED   Score a model's observed replay statement (a JSON
                        file, or '-' for stdin) against expectations parsed
                        from the cartridge itself. Output is a VECTOR of
                        named dimensions, never one scalar.
  selftest PATH         Build a perfect observed statement from the
                        cartridge's own expected values and score it.
                        Proves mech + parse + score run clean end to end.

The scoring vector (foo-cartridge-replay-v1):
  schema_match           exact string match
  cartridge_sha256       receiver-computed from the archive; any observed
                         value is ignored, never trusted
  actionable_request     normalize (strip trailing newlines, append one LF),
                         encode UTF-8, SHA-256, compare to the manifest's
                         sha256["prompt.md"] — exact-match grading of a
                         semantic extraction, no human judging required
  pinboard_debts         precision/recall vs pin entries parsed from the
                         payload's own PINBOARD section
  standing_rules         precision/recall vs RULE/AMENDMENT/COROLLARY/
                         VERDICT headers parsed from the payload
  cheapest_next_probe    bounded (single line, length cap) and read-only
                         (mutating-token denylist) — heuristic, and labeled
                         as such in the output
  unsupported_assertions count of observed debt/rule items with no textual
                         support anywhere in payload.md

Answers being physically present in the payload is by design: the replay
test measures extraction and attention fidelity, not secrecy.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path

REPLAY_SCHEMA = "foo-cartridge-replay-v1"
PROBE_MAX_LEN = 200
MUTATING_TOKENS = (
    "rm ", "mv ", " > ", ">>", "sed -i", "git push", "git commit",
    "curl ", "wget ", "dd ", "chmod ", "chown ", "kill", "truncate ",
    "tee ", "mkdir ", "touch ", "pip install", "apt ", "nix-env",
)

PLAYBACK_PREAMBLE = """\
You are receiving a compiled context cartridge (payload.md) forwarded from
another operator's machine. Read it fully, then reply with EXACTLY ONE JSON
object and nothing else — no prose before or after, no markdown fence.

The JSON object must have exactly these keys:
  "schema": the string "foo-cartridge-replay-v1"
  "cartridge_sha256": null  (the receiver's tooling computes this, not you)
  "repository_position": one paragraph (a string) summarizing where this
      repository/project currently stands, from evidence in the payload only
  "actionable_request": the FULL text of the FINAL section labeled
      '--- START: Prompt ---' ... '--- END: Prompt ---', reproduced verbatim.
      Earlier Prompt sections quoted inside transcripts do not count; only
      the last one in the document.
  "open_pinboard_debts": a list of strings, one per open pin in the PINBOARD
      section (each pin marked with a pushpin emoji), each naming the pin's
      date, article, and the gist of its OWES clause
  "standing_rules": a list of strings naming the standing constitutional
      rules/amendments/corollaries/verdicts you can locate in the payload
  "cheapest_next_probe": one single-line, strictly read-only shell command
      that would most cheaply verify or advance the actionable request
  "uncertainties": a list of strings naming anything you could not determine
      from the payload alone

Ground every field in the payload text. Do not invent receipts, debts, or
rules that are not present. The payload follows.

================ BEGIN payload.md ================
"""

PLAYBACK_POSTAMBLE = "================ END payload.md ================\n"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_foo_cartridge():
    here = Path(__file__).resolve().parent
    module_path = here / "foo_cartridge.py"
    if not module_path.exists():
        sys.exit(f"foo_replay: missing sibling module {module_path} — "
                 f"fetch foo_cartridge.py into the same directory.")
    spec = importlib.util.spec_from_file_location("foo_cartridge", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _verify_and_read(zip_path: str):
    """Fail-closed gate: canonical verification precedes every read."""
    fc = _load_foo_cartridge()
    verification = fc.verify_context_cartridge(zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        members = {name: archive.read(name) for name in fc.FOO_CARTRIDGE_MEMBERS}
    return verification, members


# ----------------------------------------------------------------------------
# Expected-value extraction (parsed from the cartridge, never hand-authored)
# ----------------------------------------------------------------------------
PIN_RE = re.compile(r"^# \U0001F4CC (\d{4}-\d{2}-\d{2}) \| (\S+)", re.M)
RULE_RE = re.compile(
    r"^#\s*((?:THE\s+)?[A-Z0-9'&\- ]{3,}?(?:RULE|AMENDMENT|COROLLARY|VERDICT|NAME))\b",
    re.M,
)


def extract_expected(payload_text: str, manifest: dict) -> dict:
    pins = []
    matches = list(PIN_RE.finditer(payload_text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else m.start() + 1500
        block = payload_text[m.start():end]
        stem = Path(m.group(2)).stem
        pins.append({
            "date": m.group(1),
            "stem": stem,
            "open": "OWES" in block,
        })
    rules = sorted({m.group(1).strip() for m in RULE_RE.finditer(payload_text)})
    return {
        "open_pins": [p for p in pins if p["open"]],
        "all_pins": pins,
        "rules": rules,
        "prompt_sha256": manifest["sha256"]["prompt.md"],
    }


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower())


def _item_matches(observed_item: str, key: str) -> bool:
    return _norm(key) .strip() in _norm(observed_item)


def _precision_recall(observed: list, expected_keys: list):
    obs = [str(o) for o in (observed or [])]
    matched_obs = set()
    matched_exp = set()
    for ei, key in enumerate(expected_keys):
        for oi, item in enumerate(obs):
            if _item_matches(item, key):
                matched_exp.add(ei)
                matched_obs.add(oi)
    precision = (len(matched_obs) / len(obs)) if obs else 0.0
    recall = (len(matched_exp) / len(expected_keys)) if expected_keys else 1.0
    unmatched_obs = [obs[i] for i in range(len(obs)) if i not in matched_obs]
    return round(precision, 3), round(recall, 3), unmatched_obs


def _probe_check(probe: str) -> dict:
    probe = (probe or "").strip()
    single_line = bool(probe) and "\n" not in probe
    bounded = single_line and len(probe) <= PROBE_MAX_LEN
    lowered = f" {probe.lower()} "
    read_only = bounded and not any(tok in lowered for tok in MUTATING_TOKENS)
    return {
        "single_line": single_line,
        "bounded": bounded,
        "read_only_heuristic": read_only,
        "note": "read-only check is a denylist heuristic, not a proof",
    }


# ----------------------------------------------------------------------------
# Subcommands
# ----------------------------------------------------------------------------
def cmd_mech(zip_path: str):
    verification, _members = _verify_and_read(zip_path)
    skeleton = {
        "schema": REPLAY_SCHEMA,
        "cartridge_sha256": verification["archive_sha256"],
        "member_sha256": verification["member_sha256"],
    }
    print(json.dumps(skeleton, indent=2, sort_keys=True))


def cmd_playback(zip_path: str):
    _verification, members = _verify_and_read(zip_path)
    sys.stdout.write(PLAYBACK_PREAMBLE)
    sys.stdout.write(members["payload.md"].decode("utf-8"))
    if not members["payload.md"].endswith(b"\n"):
        sys.stdout.write("\n")
    sys.stdout.write(PLAYBACK_POSTAMBLE)


def _score(zip_path: str, observed: dict) -> dict:
    verification, members = _verify_and_read(zip_path)
    payload_text = members["payload.md"].decode("utf-8")
    manifest = json.loads(members["manifest.json"].decode("utf-8"))
    expected = extract_expected(payload_text, manifest)

    # actionable_request: exact grading of a semantic extraction.
    ar = observed.get("actionable_request") or ""
    ar_bytes = (ar.rstrip("\n") + "\n").encode("utf-8")
    ar_match = _sha256_hex(ar_bytes) == expected["prompt_sha256"]

    debt_keys = [f"{p['date']} {p['stem']}" for p in expected["open_pins"]]
    # A pin reference matching either its date or its slug stem counts.
    def pin_matched(item, pin):
        return _item_matches(item, pin["date"]) or _item_matches(item, pin["stem"])
    obs_debts = [str(o) for o in (observed.get("open_pinboard_debts") or [])]
    matched_pins = [p for p in expected["open_pins"]
                    if any(pin_matched(o, p) for o in obs_debts)]
    debt_recall = (len(matched_pins) / len(expected["open_pins"])) if expected["open_pins"] else 1.0
    debt_matched_obs = [o for o in obs_debts
                        if any(pin_matched(o, p) for p in expected["open_pins"])]
    debt_precision = (len(debt_matched_obs) / len(obs_debts)) if obs_debts else 0.0

    rule_precision, rule_recall, unmatched_rules = _precision_recall(
        observed.get("standing_rules"), expected["rules"]
    )

    unmatched_debts = [o for o in obs_debts if o not in debt_matched_obs]
    unsupported = [
        item for item in (unmatched_debts + unmatched_rules)
        if not any(
            len(tok) >= 6 and tok in _norm(payload_text)
            for tok in _norm(item).split()
        )
    ]

    vector = {
        "schema": REPLAY_SCHEMA,
        "cartridge_sha256": verification["archive_sha256"],
        "dimensions": {
            "schema_match": observed.get("schema") == REPLAY_SCHEMA,
            "actionable_request_sha256_match": ar_match,
            "pinboard_debts": {
                "expected_open_pins": len(expected["open_pins"]),
                "precision": round(debt_precision, 3),
                "recall": round(debt_recall, 3),
            },
            "standing_rules": {
                "expected_rules": len(expected["rules"]),
                "precision": rule_precision,
                "recall": rule_recall,
            },
            "cheapest_next_probe": _probe_check(observed.get("cheapest_next_probe")),
            "unsupported_assertions": len(unsupported),
            "uncertainties_declared": len(observed.get("uncertainties") or []),
        },
        "expected_debt_keys": debt_keys,
        "expected_rule_names": expected["rules"],
    }
    return vector


def cmd_score(zip_path: str, observed_path: str):
    if observed_path == "-":
        observed = json.load(sys.stdin)
    else:
        observed = json.loads(Path(observed_path).read_text(encoding="utf-8"))
    vector = _score(zip_path, observed)
    print(json.dumps(vector, indent=2, sort_keys=True))
    dims = vector["dimensions"]
    ok = (dims["schema_match"]
          and dims["actionable_request_sha256_match"]
          and dims["pinboard_debts"]["recall"] == 1.0
          and dims["unsupported_assertions"] == 0)
    sys.exit(0 if ok else 1)


def cmd_selftest(zip_path: str):
    """Perfect-observed round trip: proves mech + parse + score end to end."""
    _verification, members = _verify_and_read(zip_path)
    payload_text = members["payload.md"].decode("utf-8")
    manifest = json.loads(members["manifest.json"].decode("utf-8"))
    expected = extract_expected(payload_text, manifest)
    observed = {
        "schema": REPLAY_SCHEMA,
        "cartridge_sha256": None,
        "repository_position": "selftest: synthesized from expected values",
        "actionable_request": members["prompt.md"].decode("utf-8"),
        "open_pinboard_debts": [
            f"{p['date']} {p['stem']} — OWES per pinboard" for p in expected["open_pins"]
        ],
        "standing_rules": list(expected["rules"]),
        "cheapest_next_probe": "grep -c '^# ' foo_files.py",
        "uncertainties": [],
    }
    vector = _score(zip_path, observed)
    print(json.dumps(vector, indent=2, sort_keys=True))
    dims = vector["dimensions"]
    ok = (dims["schema_match"]
          and dims["actionable_request_sha256_match"]
          and dims["pinboard_debts"]["recall"] == 1.0
          and dims["standing_rules"]["recall"] == 1.0
          and dims["unsupported_assertions"] == 0)
    print(f"selftest: {'PASS' if ok else 'FAIL'}", file=sys.stderr)
    sys.exit(0 if ok else 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("mech", "playback", "selftest"):
        p = sub.add_parser(name)
        p.add_argument("zip_path")
    p = sub.add_parser("score")
    p.add_argument("zip_path")
    p.add_argument("observed", help="observed replay JSON file, or '-' for stdin")
    args = parser.parse_args()

    if args.command == "mech":
        cmd_mech(args.zip_path)
    elif args.command == "playback":
        cmd_playback(args.zip_path)
    elif args.command == "score":
        cmd_score(args.zip_path, args.observed)
    elif args.command == "selftest":
        cmd_selftest(args.zip_path)


if __name__ == "__main__":
    main()
