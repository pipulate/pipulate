#!/usr/bin/env python3
"""
mcp_menu.py — what door 2 opens onto.

boot_menu.py's door 2 drops the human into the Nix shell and tells them to
type `mcp`. This is the roster they get: the commands that reach OUTSIDE
this machine, each row's description GENERATED from the target script's own
module docstring rather than hand-authored here.

CURATED ROSTER, GENERATED DESCRIPTIONS. The order and the command words are
a pedagogy decision a human makes (Rule of 7 sibling). The sentences beside
them are not -- they are read from live source at display time, so a
connector that changes what it does changes its own menu row and cannot
drift from it.

GHOSTS ARE PRINTED, NOT HIDDEN. A row whose script is missing from disk is
reported LOUDLY above the list and omitted from the numbered rows. A menu
naming a command the machine cannot run is a lie told at the exact moment
someone is deciding what to type -- the MODEL FOLLOWS THE MAP failure with
a human in the seat instead of a model.

AST, NEVER IMPORT. The connectors pull in google-api-python-client,
requests, selenium and friends; importing seven of them to print seven
sentences would cost seconds and could fail outright on absent credentials.
ast.get_docstring reads the file as text and cares about none of that --
the same technique prompt_foo.py's generate_tool_roster() uses on tools/*.

DIGIT DISPATCH. The numbers beside each row are real commands: flake.nix
binds bare 1..9 to a `_pick` helper that calls this file with --resolve N,
takes the single word it prints, and runs it with whatever arguments
followed the digit. Display and dispatch both consume _build_rows(), so a
typed number can never point at a different row than the one the eye just
read, and a ghost that shifts the printed list shifts the digits with it.

Exit codes: 0 for the display and for a successful --resolve; 1 only when
--resolve is handed a number no row answers to.
"""
import ast
import os
import sys
from pathlib import Path

REPO_ROOT = Path(
    os.environ.get("PIPULATE_ROOT") or Path(__file__).resolve().parent.parent
)

# Keep rows to one line so the panel stays scannable on a narrow terminal.
MAX_DESC = 74

# (command word, script path relative to REPO_ROOT)
#
# DELIBERATELY HELD BACK -- absence here is a decision, not an oversight:
#   gong  -- connector exists but is not tested end to end.
#   gsc   -- works, but it is a REPORT lane, not a bring-a-thread-into-context
#            lane; mixing the two muddies what this roster is for.
#   docs  -- no read connector exists yet (see the GOOGLE DOCS EARMARK).
ROSTER = [
    ("warm", "scripts/weblogin.py"),
    ("botify", "scripts/connectors/botify.py"),
    ("confluence", "scripts/connectors/confluence.py"),
    ("jira", "scripts/connectors/jira.py"),
    ("slack", "scripts/connectors/slack.py"),
    ("email", "scripts/connectors/gmail.py"),
    ("sheets", "scripts/connectors/sheets.py"),
]

# Hand-written because these are shell functions in flake.nix, not scripts
# with docstrings to read. Numbered continuously with the roster above.
TAIL = [
    ("pu", "start the Pipulate server (long form: pipulate)"),
]

FOOTER = [
    "Every number is a shortcut for the word beside it, arguments and all.",
    "Add  --help  to any command above for its full usage.",
    "Type  learn  to hand this whole workshop to an AI in a web chat.",
    "Type  mcp <tool_name>  to call a registered MCP tool directly.",
]


def _describe(script_path):
    """Return (description, ghost_reason). Exactly one is None.

    A missing FILE is a ghost -- the command cannot run, so it must not be
    listed. A missing DOCSTRING is not: the command runs fine, it is merely
    undescribed, so it stays in the list wearing a loud placeholder that
    names its own fix.
    """
    if not script_path.exists():
        return None, "missing from disk"
    try:
        source = script_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(script_path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return None, f"unreadable ({exc.__class__.__name__})"

    doc = ast.get_docstring(tree)
    if not doc or not doc.strip():
        return "(NO MODULE DOCSTRING -- add one to describe this command)", None

    line = doc.strip().splitlines()[0].strip()

    # Strip a leading "name.py - " self-label. weblogin.py opens with
    # "weblogin.py \u2014 Warm a persistent browser login...", and repeating the
    # filename in a menu row that already names the command is pure noise.
    stem = script_path.stem
    for sep in ("\u2014", "--", "-", ":"):
        prefix = f"{stem}.py {sep} "
        if line.startswith(prefix):
            line = line[len(prefix):].strip()
            break

    if not line:
        return "(EMPTY FIRST DOCSTRING LINE)", None
    if len(line) > MAX_DESC:
        line = line[: MAX_DESC - 3].rstrip() + "..."
    return line, None


def _build_rows():
    """The single ordered truth behind BOTH the display and --resolve.

    Because one function produces the list, a ghost that shifts the printed
    numbering shifts the dispatch numbering by exactly the same amount.
    There is no second ordering free to drift out of sync with the first.
    """
    rows = []
    ghosts = []
    for command, rel in ROSTER:
        description, ghost = _describe(REPO_ROOT / rel)
        if ghost:
            ghosts.append((command, rel, ghost))
        else:
            rows.append((command, description))
    rows.extend(TAIL)
    return rows, ghosts


def resolve(token):
    """Print one row's command word. The digit-dispatch contract.

    stdout is EXACTLY one bare word on success, because the shell runs it as
    a command name -- any decoration here becomes a syntax error in someone
    else's terminal. Everything explanatory goes to stderr.
    """
    rows, _ghosts = _build_rows()
    try:
        index = int(token)
    except ValueError:
        index = 0
    if not 1 <= index <= len(rows):
        sys.stderr.write(
            f"No menu row {token}. Type  mcp  for the current roster "
            f"(rows 1-{len(rows)}).\n"
        )
        return 1
    print(rows[index - 1][0])
    return 0


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--resolve":
        return resolve(sys.argv[2])

    rows, ghosts = _build_rows()

    # Ghosts print BEFORE the panel and outside it, plainly, so they cannot
    # be mistaken for a menu row or scrolled past inside a border.
    for command, rel, reason in ghosts:
        print(f"!!  {command} omitted from the roster -- {rel} {reason}")
    if ghosts:
        print()

    width = max(len(command) for command, _ in rows)
    body = "\n".join(
        f"{i}.  {command.ljust(width)}   {description}"
        for i, (command, description) in enumerate(rows, start=1)
    )

    try:
        from rich.console import Console
        from rich.panel import Panel

        Console().print(
            Panel(
                body,
                title="reach outside this machine",
                subtitle="type the number or the word",
                border_style="cyan",
                padding=(1, 2),
            )
        )
    except Exception:
        print()
        print("--- reach outside this machine ---")
        for line in body.splitlines():
            print("  " + line)
        print()

    for line in FOOTER:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
