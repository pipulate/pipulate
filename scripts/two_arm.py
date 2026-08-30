#!/usr/bin/env python3
"""
two_arm.py -- Run the shell-verb vs registry-tool experiment against one connector.

NOT A CONNECTOR. This is the harness for Experiment 1 (invocation grammar):
Arm S runs scripts/connectors/botify.py as a command line; Arm R calls the
same connector through cli.py's registry face (tools/connector_tools.py).
Same backend, same docstring, same tasks, same oracle. The only variables are
the invocation grammar and the discovery surface.

THE PROTOCOL IS ONE LINE PER MODEL TURN. The model replies `RUN: <command>` or
`FINAL: <answer>`. A RUN outside the arm's allowed prefix is refused with exit
126 and counts as a call. A reply with neither verb is a protocol violation,
exit 125, also a call. The loop ends at FINAL or at --cap calls; the cap
forces an empty FINAL, which fails.

THE ORACLE IS THE CONNECTOR ITSELF, run by the harness before AND after each
task, arm-independent. The predicate is checked against the BEFORE reading;
if the AFTER reading disagrees the trial is VOID (D1 drift: a project list can
change under you). Predicates apply to the text after FINAL: only, never to
tool stdout, so a connector's own output cannot pass a check by appearing in
the transcript.

RUN INSIDE THE QUIET SHELL. Start this program from `nix develop .#quiet` (or
an already-entered `nix develop`); every RUN executes with bash -c in the
environment this process inherited, so both arms see the same PATH, the same
.venv and the same BOTIFY_API_TOKEN. Nothing here spawns nix.

ONE HAND-AUTHORED LINE PER ARM. Each arm's system prompt carries its allowed
prefix and a one-line Shape (positional/flags for S, --raw --json-args for R).
Capability description comes only from the arm's own discovery command, and
on both arms that command prints the same module docstring.

RECORDS ARE JSONL, one per model turn, under browser_cache/two_arm/ (gitignored):
  arm task session seq kind command exit_code stdout_bytes stderr_bytes
  prompt_tokens completion_tokens text pass
plus model, model_echo, ts on every record; kind is run | final | oracle.
The final record adds void, calls, capped; the oracle record adds before,
after, void, reason. Refusals and protocol violations are kind=run with exit
126 and 125, so a count of run records IS the calls metric.

COMPILE-LANE CAUTION: oracle values and FINAL texts carry the account's
username and client org/project slugs. Records stay under browser_cache/;
project them with jq (omit text, before, after) before any `!` line rides to a
cloud chat window. A model call is a mutation of a token ledger, not a probe:
never echo a non-dry run into adhoc.txt.

Usage:
  .venv/bin/python scripts/two_arm.py --arm S --tasks T1 --model gemma3:latest
  .venv/bin/python scripts/two_arm.py --arm R --tasks T1 --model gemma3:latest
  .venv/bin/python scripts/two_arm.py --arm S --tasks T3 T4 T5 --org ORG --project PROJ
  .venv/bin/python scripts/two_arm.py --arm R --dry-run --tasks          # discovery only
  .venv/bin/python scripts/two_arm.py --arm S --dry-run --tasks T1 T2    # + oracles, no model
"""
import argparse
import ast
import json
import os
import re
import shlex
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONNECTOR_PATH = REPO_ROOT / "scripts" / "connectors" / "botify.py"
CONNECTOR = ".venv/bin/python scripts/connectors/botify.py"
CLI = ".venv/bin/python cli.py"
OUT_DIR = REPO_ROOT / "browser_cache" / "two_arm"
STDOUT_CAP = 4000
STDERR_CAP = 1000
DISCOVERY_CAP = 12000
CMD_TIMEOUT = 180
EXIT_TIMEOUT = 124
EXIT_PROTOCOL = 125
EXIT_REFUSED = 126

ARMS = {
    "S": {
        "prefix": CONNECTOR,
        "shape": CONNECTOR + " [query] [--org ORG] [--project PROJECT] [-n MAX] [--check]",
        "env": {},
        "discovery": [CONNECTOR + " --help"],
        "catalog": [".venv/bin/python scripts/sources_menu.py"],
    },
    "R": {
        "prefix": CLI,
        "shape": CLI + " call botify --raw --json-args '<json object>'",
        "env": {"PIPULATE_TOOL_DENY": "execute_shell_command"},
        "discovery": [CLI + " mcp-discover --tool botify"],
        "catalog": [CLI + " mcp-discover --all"],
    },
}

URL_RE = re.compile(r"https?://[^\s\"'<>\\)\]]+")
REPLY_RE = re.compile(r"^\s*[`*\->]*\s*(RUN|FINAL)\s*:\s*(.*?)\s*`*\s*$", re.IGNORECASE)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_cmd(cmd, env_extra=None, timeout=CMD_TIMEOUT):
    """bash -c in the inherited environment -> (exit_code, stdout, stderr, seconds)."""
    env = dict(os.environ)
    env.update(env_extra or {})
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            ["bash", "-c", cmd], cwd=str(REPO_ROOT), env=env,
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
        err = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace")
        return EXIT_TIMEOUT, out, err + f"\n[timeout after {timeout}s]", time.monotonic() - t0
    return proc.returncode, proc.stdout, proc.stderr, time.monotonic() - t0


# --- oracles: the connector itself, arm-independent ------------------------

def _data_lines(stdout):
    return [ln for ln in stdout.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")
            and not ln.lstrip().startswith("(")]


def oracle_username(ctx):
    _, out, _, _ = run_cmd(CONNECTOR + " --check")
    m = re.search(r"botify GREEN (\S+)", out)
    return m.group(1) if m else None


def oracle_first_project(ctx):
    _, out, _, _ = run_cmd(CONNECTOR + " -n 25")
    lines = _data_lines(out)
    return lines[0].split()[0] if lines else None


def oracle_newest_analysis(ctx):
    target = shlex.quote(ctx["org"] + "/" + ctx["project"])
    _, out, _, _ = run_cmd(CONNECTOR + " " + target + " -n 1")
    lines = _data_lines(out)
    return lines[0].split()[0] if lines else None


def oracle_urls(ctx):
    cmd = (CONNECTOR + " 'SELECT url FROM crawl' --org " + shlex.quote(ctx["org"])
           + " --project " + shlex.quote(ctx["project"]) + " -n 25")
    _, out, _, _ = run_cmd(cmd)
    return sorted(set(URL_RE.findall(out)))


def oracle_missing_project(ctx):
    target = shlex.quote(ctx["org"] + "/" + ctx["bogus"])
    _, _, err, _ = run_cmd(CONNECTOR + " " + target + " -n 1")
    m = re.search(r"HTTP (\d{3})", err)
    return m.group(1) if m else None


TASKS = {
    "T1": {"text": "What Botify username is this environment authenticated as?",
           "oracle": oracle_username, "kind": "scalar", "needs": ()},
    "T2": {"text": "Name the first org/project slug pair listed for this account.",
           "oracle": oracle_first_project, "kind": "scalar", "needs": ()},
    "T3": {"text": "For the Botify project {org}/{project}, what is the slug of the newest analysis?",
           "oracle": oracle_newest_analysis, "kind": "scalar", "needs": ("org", "project")},
    "T4": {"text": ("Run the BQL query SELECT url FROM crawl against the Botify project "
                    "{org}/{project} with a cap of 5 and report one URL it returned."),
           "oracle": oracle_urls, "kind": "set", "needs": ("org", "project")},
    "T5": {"text": ("Run the BQL query SELECT url FROM crawl against the Botify project "
                    "{project}, under the org this account belongs to, with a cap of 5 "
                    "and report one URL it returned."),
           "oracle": oracle_urls, "kind": "set", "needs": ("org", "project")},
    "N3": {"text": "For the Botify project {org}/{bogus}, what is the slug of the newest analysis?",
           "oracle": oracle_missing_project, "kind": "scalar", "needs": ("org",)},
}


def drift(before, after, kind):
    if kind == "set":
        return not (set(before or []) & set(after or []))
    return before != after


def passes(final_text, before, after, kind):
    if not final_text:
        return False
    if kind == "set":
        return any(u in final_text for u in set(before or []) | set(after or []))
    return bool(before) and before in final_text


# --- discovery and the system prompt ---------------------------------------

def connector_doc_line():
    """First docstring line of the connector, self-label stripped, as sources_menu.py shows it."""
    try:
        doc = ast.get_docstring(ast.parse(CONNECTOR_PATH.read_text(encoding="utf-8"))) or ""
    except (OSError, SyntaxError):
        return ""
    line = doc.strip().splitlines()[0].strip() if doc.strip() else ""
    return re.sub(r"^\S+\.py\s+\S+\s+", "", line)


def discovery_text(arm, catalog):
    spec = ARMS[arm]
    cmds = list(spec["discovery"]) + (list(spec["catalog"]) if catalog else [])
    chunks = []
    for cmd in cmds:
        _, out, err, _ = run_cmd(cmd, spec["env"])
        chunks.append("$ " + cmd + "\n" + out + err)
    return "\n\n".join(chunks)[:DISCOVERY_CAP]


def system_prompt(arm, disc):
    spec = ARMS[arm]
    return (
        "You are operating a terminal to answer one question. Reply with EXACTLY ONE "
        "line per turn: either `RUN: <command>` to execute a command, or "
        "`FINAL: <answer>` when you have the answer. Do not explain.\n"
        "You may only run commands that begin with: " + spec["prefix"] + "\n"
        "Shape: " + spec["shape"] + "\n"
        "Any other command is refused. After each RUN you receive its exit code, "
        "stdout and stderr.\n\nDISCOVERY (what the command can do):\n" + disc
    )


# --- the model, through the llm library ------------------------------------

def load_model(model_id):
    import llm  # lazy: --dry-run must not need a model
    return llm.get_model(model_id)


def ask(conv, text, system=None, temperature=True):
    """One model turn -> (reply_text, prompt_tokens, completion_tokens, model_echo)."""
    kwargs = {}
    if system:
        kwargs["system"] = system
    if temperature:
        kwargs["temperature"] = 0
    resp = conv.prompt(text, **kwargs)
    reply = resp.text()
    try:
        usage = resp.usage()
        p_tok, c_tok = int(usage.input or 0), int(usage.output or 0)
    except Exception:
        p_tok, c_tok = 0, 0
    echo = None
    raw = getattr(resp, "response_json", None)
    if isinstance(raw, dict):
        echo = raw.get("model")
    return reply, p_tok, c_tok, echo


def parse_reply(reply):
    for line in reply.splitlines():
        m = REPLY_RE.match(line)
        if m:
            return m.group(1).upper(), m.group(2).strip()
    return None, None


# --- one session = one task, one arm, one conversation ----------------------

def run_session(arm, task_id, session_idx, ctx, model, args, fh, disc, base):
    spec = ARMS[arm]
    task = TASKS[task_id]

    def emit(**rec):
        rec = {**base, "task": task_id, "session": session_idx, **rec}
        rec.setdefault("ts", utc_now())
        fh.write(json.dumps(rec, default=str) + "\n")
        fh.flush()

    missing = [k for k in task["needs"] if not ctx.get(k)]
    if missing:
        emit(seq=0, kind="oracle", before=None, after=None, void=True,
             reason="missing " + ",".join(missing))
        return None
    before = task["oracle"](ctx)
    if not before:
        emit(seq=0, kind="oracle", before=before, after=None, void=True, reason="oracle_empty")
        return None

    conv = model.conversation()
    reply, p_tok, c_tok, echo = ask(conv, task["text"].format(**ctx),
                                    system=system_prompt(arm, disc),
                                    temperature=not args.no_temperature)
    seq, calls, tokens = 0, 0, 0
    final_text, final_tokens = None, (0, 0)
    while True:
        seq += 1
        tokens += p_tok + c_tok
        verb, rest = parse_reply(reply)
        if verb == "FINAL":
            final_text, final_tokens = rest, (p_tok, c_tok)
            break
        calls += 1
        if verb == "RUN" and rest.startswith(spec["prefix"]):
            cmd = rest
            code, out, err, secs = run_cmd(rest, spec["env"])
        elif verb == "RUN":
            cmd, code, out, err, secs = rest, EXIT_REFUSED, "", "refused: outside arm", 0.0
        else:
            cmd, code, out, err, secs = "", EXIT_PROTOCOL, "", (
                "protocol: reply with exactly one line, RUN: <command> or FINAL: <answer>"), 0.0
        emit(seq=seq, kind="run", command=cmd, exit_code=code,
             stdout_bytes=len(out.encode("utf-8")), stderr_bytes=len(err.encode("utf-8")),
             prompt_tokens=p_tok, completion_tokens=c_tok, seconds=round(secs, 3),
             text=reply[:500], model_echo=echo, **{"pass": None})
        if calls >= args.cap:
            final_text = ""
            break
        feedback = ("exit_code: " + str(code) + "\nstdout:\n" + out[:STDOUT_CAP]
                    + "\nstderr:\n" + err[:STDERR_CAP])
        reply, p_tok, c_tok, echo = ask(conv, feedback, temperature=not args.no_temperature)

    after = task["oracle"](ctx)
    void = drift(before, after, task["kind"])
    ok = (not void) and passes(final_text, before, after, task["kind"])
    emit(seq=seq, kind="final", command=None, exit_code=None, stdout_bytes=0, stderr_bytes=0,
         prompt_tokens=final_tokens[0], completion_tokens=final_tokens[1],
         text=final_text, model_echo=echo, calls=calls,
         capped=(final_text == "" and calls >= args.cap), void=void,
         **{"pass": (None if void else ok)})
    emit(seq=seq + 1, kind="oracle", before=before, after=after, void=void,
         reason=("drift" if void else None))
    return ok, void, calls, tokens


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", choices=sorted(ARMS), required=True)
    ap.add_argument("--tasks", nargs="*", default=["T1", "T2", "T3", "T4", "T5"],
                    help="task ids (T1..T5, N3 negative control); bare --tasks = discovery only")
    ap.add_argument("--sessions", type=int, default=1)
    ap.add_argument("--model", default="gemma3:latest", help="an id from `llm models`")
    ap.add_argument("--org", default=os.getenv("BOTIFY_ORG"))
    ap.add_argument("--project", default=os.getenv("BOTIFY_PROJECT"))
    ap.add_argument("--cap", type=int, default=8, help="max RUN calls per task")
    ap.add_argument("--catalog", action="store_true",
                    help="also feed the arm's catalog (sources roster / mcp-discover --all)")
    ap.add_argument("--no-temperature", action="store_true",
                    help="omit temperature=0 for models whose Options lack it")
    ap.add_argument("--dry-run", action="store_true",
                    help="discovery + oracles only; no model, no records")
    ap.add_argument("--out", default=None, help="JSONL path (default: browser_cache/two_arm/<ts>__<arm>.jsonl)")
    args = ap.parse_args()

    unknown = [t for t in args.tasks if t not in TASKS]
    if unknown:
        sys.stderr.write("unknown task(s): " + " ".join(unknown) + "; known: " + " ".join(TASKS) + "\n")
        return 2
    ctx = {"org": args.org, "project": args.project,
           "bogus": "no-such-project-" + uuid.uuid4().hex[:8]}

    disc = discovery_text(args.arm, args.catalog)
    shared = connector_doc_line()
    print("arm=" + args.arm + " prefix=" + ARMS[args.arm]["prefix"])
    print("discovery_chars=" + str(len(disc))
          + " shared_doc_line_present=" + str(bool(shared) and shared in disc))

    if args.dry_run:
        for t in args.tasks:
            task = TASKS[t]
            missing = [k for k in task["needs"] if not ctx.get(k)]
            if missing:
                print(t + " oracle=skipped missing=" + ",".join(missing))
                continue
            val = task["oracle"](ctx)
            shown = val if task["kind"] == "scalar" else str(len(val)) + " url(s)"
            print(t + " oracle=" + str(shown))
        return 0
    if not args.tasks:
        return 0

    model = load_model(args.model)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = Path(args.out) if args.out else OUT_DIR / (stamp + "__" + args.arm + ".jsonl")
    base = {"arm": args.arm, "model": args.model, "batch": stamp}
    with out_path.open("a", encoding="utf-8") as fh:
        for t in args.tasks:
            for s in range(args.sessions):
                res = run_session(args.arm, t, s, ctx, model, args, fh, disc, base)
                if res is None:
                    print(args.arm + " " + t + " s" + str(s) + " skipped (see oracle record)")
                    continue
                ok, void, calls, tokens = res
                print(args.arm + " " + t + " s" + str(s) + " pass=" + str(ok) + " void=" + str(void)
                      + " calls=" + str(calls) + " tokens=" + str(tokens))
    print("# records: " + str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
