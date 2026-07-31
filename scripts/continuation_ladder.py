#!/usr/bin/env python3
# scripts/continuation_ladder.py
"""
continuation_ladder.py -- four reasons a loop keeps going, one harness.

THE HARNESS IS THE POINT. Every rung below runs through the IDENTICAL
run_rung() loop. The only thing that differs between rungs is the GUARD
EXPRESSION -- a zero-argument callable returning bool, evaluated fresh at
the top of every iteration. Swap the guard, change nothing else, and the
reason the loop continues changes underneath you.

    1. SKYHOOK    -- continuation by MECHANISM. A sentinel file exists.
                     No mind anywhere. The control group.
                     Already shipping unnamed: scripts/weblogin.py:128 loops
                     on driver.window_handles. A browser window IS a skyhook.
    2. COIN FLIP  -- continuation by CHANCE. One bit of entropy per turn.
                     Still no mind; now there is variance.
    3. WILL       -- continuation by VOLITION. Something DECIDES each turn.
                     A human at a TTY, or any command named by --will-cmd.
    4. CINDERELLA -- continuation by COMPETENCE UNDER DEADLINE. A credential
                     is still inside its stamped lifetime. The ride ends when
                     the clock runs out, unless something refreshes it.

HARNESS INVARIANT (the whole reason this file exists): the guard is
evaluated by THIS code, every iteration, before the body runs. It is never
delegated to the thing inside the loop. A prompt that says "check before
continuing" is a CONVENTION -- the agent may comply, may forget, may be
talked out of it. A `while guard():` is PHYSICS. Conventions are the
failure surface; physics is not.

THE GUARD IS A SENSOR, NOT AN ACTUATOR. No guard here changes the world.
Rung 1 ends when someone removes the sentinel; rung 4 ends when a clock
runs out and resumes only if something OUT OF BAND re-mints the credential
(python scripts/connectors/mcp_warm.py --refresh). That asymmetry is
deliberate: a guard that can repair its own precondition is a guard whose
failures stop being visible.

THE CAP IS NOT A GUARD. run_rung() enforces --max independently of the
guard and records WHICH one stopped the loop. A rung that always exits on
'cap_reached' has a guard that never fires -- that is a finding, not a
success. An unattended rung 1 SHOULD hit the cap: a mechanism guard has no
opinion about when to stop, which is exactly why weblogin.py needs a human
to close the window. Unbounded agentic loops are the thing this file
vaccinates against.

WITNESS: one JSONL line per iteration, appended to
data/continuation_ladder/rung<N>.jsonl, plus a summary record at the end.
The receipt exists on disk whether or not anyone was watching stdout.

Stdlib only, on purpose: a stranger can run this with nothing installed.

    python scripts/continuation_ladder.py --rung 1
    python scripts/continuation_ladder.py --rung 2 --max 12
    python scripts/continuation_ladder.py --rung 3 --will-cmd 'test $RANDOM -gt 8000'
    python scripts/continuation_ladder.py --rung 4
    python scripts/continuation_ladder.py --all --max 6
    python scripts/continuation_ladder.py --reset
"""

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(os.environ.get("PIPULATE_ROOT")
                 or Path(__file__).resolve().parent.parent)
WITNESS_DIR = REPO_ROOT / "data" / "continuation_ladder"
SENTINEL = WITNESS_DIR / "skyhook.sentinel"
TOKEN_FILE = Path.home() / ".config" / "pipulate" / "mcp_botify_token.json"

RUNG_NAMES = {1: "skyhook", 2: "coin_flip", 3: "will", 4: "cinderella"}
RUNG_GUARD_DOC = {
    1: "the sentinel file exists (mechanism; no mind anywhere)",
    2: "one bit of entropy came up 1 (chance; still no mind)",
    3: "a decider said yes (volition; something chose)",
    4: "the credential is still inside its stamped lifetime (deadline)",
}


def _read_json(path):
    """Best-effort JSON read. None on any failure -- absence is a reading."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def seconds_left(record):
    """Seconds remaining on a warmed credential, or None if unreadable.

    WET SIBLING, DELIBERATE. scripts/connectors/mcp.py::_expiry_note is the
    SHIPPING instrument and owns the operator-facing wording; this is the
    pedagogical mirror, kept stdlib-only so this demo needs nothing from the
    connector lane (which imports httpx). Same two fields, same arithmetic,
    different job. If they ever disagree, mcp.py wins.
    """
    if not isinstance(record, dict):
        return None
    obtained_at = record.get("obtained_at")
    expires_in = record.get("expires_in")
    if not obtained_at or not expires_in:
        return None
    try:
        minted = datetime.fromisoformat(obtained_at)
        if minted.tzinfo is None:
            minted = minted.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - minted).total_seconds()
        return float(expires_in) - age
    except (TypeError, ValueError):
        return None


def _decide(will_cmd):
    """Rung 3's decider. Exit 0, or a leading 'y', means continue.

    FAIL-CLOSED, LOUDLY. With no --will-cmd and no TTY there is no volunteer
    for the volition, so the rung declares itself unreachable rather than
    inventing a default. A rung that silently answers its own question is
    rung 1 wearing rung 3's label.
    """
    if will_cmd:
        return subprocess.run(will_cmd, shell=True).returncode == 0
    if sys.stdin.isatty():
        try:
            return input("  will> continue? [y/N] ").strip().lower().startswith("y")
        except EOFError:
            return False
    sys.stderr.write(
        "# rung 3 UNREACHABLE: no --will-cmd and no TTY. Volition needs a "
        "volunteer -- wire one with --will-cmd, or run this in a terminal.\n"
    )
    return False


def make_guard(rung, will_cmd=None, token_path=TOKEN_FILE):
    """Return the ONE thing that differs between rungs: a zero-arg predicate.

    Nothing else in this file branches on rung number at execution time.
    """
    if rung == 1:
        return lambda: SENTINEL.exists()
    if rung == 2:
        return lambda: secrets.randbits(1) == 1
    if rung == 3:
        return lambda: _decide(will_cmd)
    if rung == 4:
        def _credential_live():
            left = seconds_left(_read_json(token_path))
            return left is not None and left > 0.0
        return _credential_live
    raise ValueError(f"no such rung: {rung!r}")


def _witness(path, record):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def run_rung(rung, guard, max_iters, interval):
    """The invariant harness. Identical for every rung, forever."""
    name = RUNG_NAMES[rung]
    WITNESS_DIR.mkdir(parents=True, exist_ok=True)
    witness = WITNESS_DIR / f"rung{rung}.jsonl"
    started = time.time()
    iterations = 0

    while True:
        ok = bool(guard())
        _witness(witness, {
            "kind": "iteration",
            "rung": rung,
            "name": name,
            "iteration": iterations + 1,
            "guard": ok,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"  [{name}] iter {iterations + 1:>3}  guard={str(ok).lower()}")
        if not ok:
            stopped = "guard_false"
            break
        iterations += 1
        if iterations >= max_iters:
            stopped = "cap_reached"
            break
        time.sleep(interval)

    summary = {
        "kind": "summary",
        "rung": rung,
        "name": name,
        "stopped": stopped,
        "iterations": iterations,
        "cap": max_iters,
        "elapsed_seconds": round(time.time() - started, 3),
        "witness": str(witness),
        "at": datetime.now(timezone.utc).isoformat(),
    }
    _witness(witness, summary)
    print(f"  -> stopped={stopped} after {iterations} iteration(s)")
    print(f"  -> witness: {witness}")
    return summary


def _reset():
    if not WITNESS_DIR.exists():
        print(f"nothing to reset: {WITNESS_DIR} does not exist")
        return
    removed = 0
    for path in sorted(WITNESS_DIR.glob("rung*.jsonl")):
        path.unlink()
        removed += 1
    if SENTINEL.exists():
        SENTINEL.unlink()
        removed += 1
    print(f"reset: removed {removed} file(s) from {WITNESS_DIR}")


def main():
    parser = argparse.ArgumentParser(
        description="Four reasons a loop keeps going, one invariant harness.")
    parser.add_argument("--rung", type=int, choices=[1, 2, 3, 4],
                        help="Which rung to run.")
    parser.add_argument("--all", action="store_true",
                        help="Run all four rungs in order.")
    parser.add_argument("--max", type=int, default=12,
                        help="Hard iteration cap, enforced independently of "
                             "the guard (default: 12).")
    parser.add_argument("--interval", type=float, default=0.2,
                        help="Seconds between iterations (default: 0.2).")
    parser.add_argument("--will-cmd", default=None,
                        help="Rung 3 decider: any shell command. Exit 0 means "
                             "continue. Without it, rung 3 prompts a TTY.")
    parser.add_argument("--token-file", default=str(TOKEN_FILE),
                        help=f"Rung 4 credential (default: {TOKEN_FILE}).")
    parser.add_argument("--reset", action="store_true",
                        help="Delete prior witnesses and the sentinel, then exit.")
    args = parser.parse_args()

    if args.reset:
        _reset()
        return

    if not args.all and not args.rung:
        parser.error("pick --rung 1|2|3|4, or --all, or --reset")

    rungs = [1, 2, 3, 4] if args.all else [args.rung]
    WITNESS_DIR.mkdir(parents=True, exist_ok=True)

    for rung in rungs:
        print(f"\n[rung {rung} {RUNG_NAMES[rung]}] "
              f"continues while: {RUNG_GUARD_DOC[rung]}")

        if rung == 1:
            SENTINEL.touch()
            print(f"  sentinel armed: {SENTINEL}")
            print("  the guard lets go only when that file does -- `rm` it from "
                  "another terminal.")
            print("  unattended, this SHOULD hit the cap. A mechanism guard has "
                  "no opinion about stopping.")

        if rung == 4:
            left = seconds_left(_read_json(args.token_file))
            if left is None:
                print(f"  clock: unreadable at {args.token_file} "
                      "(no obtained_at/expires_in) -- guard will read false")
            elif left > 0:
                print(f"  clock: ~{int(left)}s left -- the ride continues "
                      "until it does not")
            else:
                print(f"  clock: EXPIRED {int(-left)}s ago -- guard reads false "
                      "on iteration 1, by design")
                print("  re-mint out of band: python scripts/connectors/"
                      "mcp_warm.py --refresh")

        run_rung(rung,
                 make_guard(rung, will_cmd=args.will_cmd,
                            token_path=args.token_file),
                 args.max, args.interval)


if __name__ == "__main__":
    main()
