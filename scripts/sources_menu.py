#!/usr/bin/env python3
"""
sources_menu.py — what door 2 opens onto.

boot_menu.py's door 2 drops the human into the Nix shell and tells them to
type `sources`. This is the roster they get: the commands that reach OUTSIDE
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

NO NUMBERS, DELIBERATELY. An earlier version numbered these rows and bound
bare 1..9 in flake.nix to dispatch them. It could not work: most roster
words are shell ALIASES, and bash expands an alias only when it is the
literal first word a parser reads -- never when it arrives through a
variable, which is what any dispatcher must do. Row 8 (`pu`, a FUNCTION)
would have run while rows 1-7 printed command-not-found, and half a menu
working for a reason invisible from the menu is worse than no numbers at
all. The words ARE the interface. See THE ALIAS-DISPATCH RULE in
foo_files.py before adding any shortcut layer over this list.

Exit code is always 0. This is a display, not a decision; nothing parses it.
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
#   weblogin -- still a command, but `warm` is now its front door: a
#            browser_session slot's fixer IS weblogin.py, so one word warms
#            anything and this row would be a second door to the same room.
#
# `warm` used to point at weblogin.py directly. It now points at the wallet,
# whose docstring line is read from source at display time -- so when the word
# changed meaning, the sentence beside it could not stay behind.
ROSTER = [
    ("warm", "scripts/connectors/wallet.py"),
    ("botify", "scripts/connectors/botify.py"),
    ("confluence", "scripts/connectors/confluence.py"),
    ("jira", "scripts/connectors/jira.py"),
    ("slack", "scripts/connectors/slack.py"),
    ("email", "scripts/connectors/gmail.py"),
    ("sheets", "scripts/connectors/sheets.py"),
]

# Hand-written because these are shell functions in flake.nix, not scripts
# with docstrings to read. Appended after the roster, in display order.
#
# `pu` is the one row the panel title does not cover -- it starts a LOCAL
# server, the opposite of reaching outside. It stays anyway: a human who
# just declined door 1 wants that word exactly where they are looking, and
# a title that is right about 7 of 8 rows beats a roster missing the row
# they came for. Recorded as a decision so nobody "fixes" it silently.
TAIL = [
    ("pu", "start the Pipulate server (long form: pipulate)"),
]

FOOTER = [
    "Add  --help  to any command above for its full usage.",
    "Type  learn  to hand this whole workshop to an AI in a web chat.",
    "Type  tools  to list registry tools, or  tools <name>  to call one.",
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


def main():
    rows = []
    ghosts = []
    for command, rel in ROSTER:
        description, ghost = _describe(REPO_ROOT / rel)
        if ghost:
            ghosts.append((command, rel, ghost))
        else:
            rows.append((command, description))
    rows.extend(TAIL)

    # Ghosts print BEFORE the panel and outside it, plainly, so they cannot
    # be mistaken for a menu row or scrolled past inside a border.
    for command, rel, reason in ghosts:
        print(f"!!  {command} omitted from the roster -- {rel} {reason}")
    if ghosts:
        print()

    width = max(len(command) for command, _ in rows)

    # THE 80-COLUMN BUDGET, SHOUTED RATHER THAN SILENTLY TRUNCATED.
    # Rich gives a padding=(1,2) Panel a body of console_width - 6, so at the
    # 80 columns a fresh terminal (and every non-tty lane, including the `!`
    # executor) defaults to, the body is 74. Each row spends the command
    # column plus a 3-space gutter -- the same derivation
    # connectors/README.md already documents, recomputed here from the live
    # width so a longer command word lowers the ceiling for every row at once.
    # MAINTAINER-INVISIBLE BY CONSTRUCTION: the author's terminal is ~180
    # columns, so an over-budget row wraps only for strangers. Row one (warm)
    # sat at 63 against a 61 budget for the entire life of this roster, and no
    # one who could fix it was ever in a position to see it.
    # WARN, NEVER TRUNCATE: MAX_DESC's silent cut is the LAST-INCH failure --
    # a correct sentence destroyed by the transformation nearest the reader,
    # with no tell. A loud line names its own fix, stays silent when every row
    # fits, and the rendered panel below is the independent witness that this
    # check ran at all. The healthy margin is thin (the longest surviving row
    # clears by two characters), which is why the guard matters more than the
    # single row it was written to catch.
    budget = 74 - width - 3
    overflows = [
        (command, description)
        for command, description in rows
        if len(description) > budget
    ]
    for command, description in overflows:
        print(
            f"!!  {command} description is {len(description)} chars against a "
            f"{budget}-char budget -- this row WILL WRAP at 80 columns."
        )
    if overflows:
        print()
    body = "\n".join(
        f"{command.ljust(width)}   {description}"
        for command, description in rows
    )

    try:
        from rich.console import Console
        from rich.panel import Panel

        Console().print(
            Panel(
                body,
                title="reach outside this machine",
                subtitle="type any of these",
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
