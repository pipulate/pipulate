#!/usr/bin/env python3
"""
boot_menu.py -- the one-door threshold at the end of `nix develop`.

An interactive terminal no longer asks the newcomer to choose a numbered door.
It prints the short command list and returns 10, which tells flake.nix to stop
before either server starts and hand the human the shell prompt. `menu` recalls
the short list; `all` recalls the expanded list; `about` prints the workspace
tree and the three tier sentences.

THE PROTOCOL IS THE EXIT CODE, never stdout:

  0   start the app       (non-tty or PIPULATE_BOOT_MENU=0)
  10  drop to the Nix CLI after printing the short list

FAIL-OPEN BY CONSTRUCTION. Every unattended path keeps the pre-menu behavior:
no tty, PIPULATE_BOOT_MENU=0, or an unexpected display failure returns 0. The
interactive path blocks on nothing and reads no keys; the terminal itself is
the introduction.

Stdlib only on the threshold path. --about is the one branch that reaches
past it: the sealed workspace art (imports/ascii_displays.py) and rich, which
the venv the flake invokes this with already carries.

Env:
  PIPULATE_BOOT_MENU=0   skip the list and start the app
"""
import os
import sys
from pathlib import Path

EXIT_START = 0
EXIT_SHELL = 10

# THE BLANK STARE RULE (2026-09-28, the operator's words): every word here is
# the plain name of the thing it does; an abbreviation (conn) is an alias
# behind the word, never the word the menu prints.
SHORT_WORDS = (
    ("menu", "print this list again (useful once it scrolls away)."),
    ("walk", "take guided tour of context compiler (recommended)."),
    ("talk", "turn text-to-speech narration on or off."),
    ("connect", "put mcp, jira, email, docs, etc. into your contexts."),
    ("context", "edit the list of files an AI will read (after the walk)."),
    ("prompt", "save your clipboard as the question for the AI."),
    ("compile", "build the list and the question into one payload for a chatbot."),
    ("about", 'how to Q/A AI output ("what Claude said").'),
    ("all", "expanded menu."),
)

ALL_WORDS = (
    ("menu", "print the shorter list."),
    ("walk", "take guided tour of context compiler (recommended)."),
    ("talk", "turn text-to-speech narration on or off."),
    ("connect", "put mcp, jira, email, docs, etc. into your contexts."),
    ("context", "edit the list of files an AI will read (after the walk)."),
    ("prompt", "save your clipboard as the question for the AI."),
    ("compile", "build the list and the question into one payload for a chatbot."),
    ("about", 'how to Q/A AI output ("what Claude said").'),
    ("all", "print this expanded list again."),
    # THE THREE WORDS (2026-09-25): context, prompt, compile are the whole
    # loop, on both lists. ahe, ahc and the short spellings still work; epr
    # and cpr are gone with the separate walk router they edited.
    ("brief", "compile this workshop into your clipboard for an AI."),
    ("jn", "start JupyterLab and Pipulate, JupyterLab first."),
    ("pu", "start the Pipulate server."),
    ("reseal", "fix the ASCII art checksums after you edit the art."),
    # OPERATION STICK BUG (2026-10-02): osb is THE BLANK STARE RULE's one
    # exception, a twig of a name over the one loud screen, so it rides
    # this list, last, and the short list never prints it.
    ("osb", "operation stick bug."),
)

ABOUT_LINES = (
    "",
    "1. corporate manages corporate.",
    "2. You manage personal.",
    "3. Each person shares into shared, in a folder named after them.",
    "",
    "personal -> shared when the person says so.",
    "shared -> corporate when corporate says so.",
    "Nothing leaves personal unless you copy it into YOUR shared folder.",
    "",
    "What an AI was given is a text file (context.txt). What it said comes",
    "back beside the receipts it was shown. Both are on disk, so",
    '"what Claude said" can be checked against what Claude was handed.',
)


def print_about() -> None:
    """The sealed workspace tree, then the tier sentences and the Q/A line.

    A failed import prints why and still prints the sentences, so `about`
    never reads as an empty screen. A drifted seal is said out loud.
    """
    import logging
    import shutil
    logging.disable(logging.CRITICAL)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from imports.ascii_displays import figurate
        from rich.console import Console
        art = figurate("workspace_tree")
        Console(width=max(shutil.get_terminal_size((100, 24)).columns, 100)).print(art.human)
        if art.drift:
            print("(the drawing above has drifted from its seal; type reseal)")
    except Exception as exc:
        print(f"(workspace tree unavailable: {type(exc).__name__}: {exc})")
    for line in ABOUT_LINES:
        print(line)


def print_words(words) -> None:
    """Print one command list from data; short and expanded cannot drift."""
    print("type one:")
    width = max(len(word) for word, _ in words)
    for word, description in words:
        # No indent (2026-10-02): a narrow window wraps to column 0 anyway.
        print(word.ljust(width) + "  " + description)


MENU_HINT = "Type menu on the command line at any time to see this menu again."


def speak_menu_hint() -> None:
    """Say MENU_HINT if narration is on. Never waits, never raises.

    voice_consent() decides, inside speak_text(), in a detached child, so this
    process stays stdlib-only and the menu never waits on audio. Narration
    off, no terminal, or any failure: silent.
    """
    if not sys.stdout.isatty():
        return
    try:
        import subprocess
        root = str(Path(__file__).resolve().parent.parent)
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "from imports.voice_synthesis import chip_voice_system as v; "
            "v and v.speak_text(sys.argv[2])"
        )
        subprocess.Popen(
            [sys.executable, "-c", code, root, MENU_HINT],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def main() -> int:
    args = set(sys.argv[1:])
    # about is a display, like recall: it runs before the unattended gates.
    if "--about" in args:
        print_about()
        return 0

    # Recall is a display, not the startup threshold. It deliberately runs
    # before the unattended gates so `menu` and `all` also work when stdout is
    # redirected or PIPULATE_BOOT_MENU=0 is inherited by the shell.
    if "--recall" in args:
        print()
        print_words(ALL_WORDS if "--all" in args else SHORT_WORDS)
        speak_menu_hint()
        return 0

    if os.environ.get("PIPULATE_BOOT_MENU", "1").strip().lower() in {
        "0",
        "no",
        "off",
        "false",
    }:
        return EXIT_START

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return EXIT_START

    try:
        print()
        print_words(SHORT_WORDS)
        speak_menu_hint()
    except Exception:
        return EXIT_START
    return EXIT_SHELL


if __name__ == "__main__":
    sys.exit(main())
