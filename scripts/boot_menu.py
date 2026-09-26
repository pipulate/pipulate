#!/usr/bin/env python3
"""
boot_menu.py — the one-door threshold at the end of `nix develop`.

An interactive terminal no longer asks the newcomer to choose a numbered door.
It prints the short command list and returns 10, which tells flake.nix to stop
before either server starts and hand the human the shell prompt. `menu` recalls
the short list; `all` recalls the expanded list.

THE PROTOCOL IS THE EXIT CODE, never stdout:

  0   start the app       (non-tty or PIPULATE_BOOT_MENU=0)
  10  drop to the Nix CLI after printing the short list

FAIL-OPEN BY CONSTRUCTION. Every unattended path keeps the pre-menu behavior:
no tty, PIPULATE_BOOT_MENU=0, or an unexpected display failure returns 0. The
interactive path blocks on nothing and reads no keys; the terminal itself is
the introduction.

Stdlib only.

Env:
  PIPULATE_BOOT_MENU=0   skip the list and start the app
"""
import os
import sys

EXIT_START = 0
EXIT_SHELL = 10

SHORT_WORDS = (
    ("menu", "print this list again (useful once it scrolls away)"),
    ("walk", "take guided tour of context compiler (recommended)"),
    ("conn", "get mcp, jira, email, docs, etc. into context"),
    ("context", "edit the list of files an AI will read (after the walk)"),
    ("prompt", "save your clipboard as the question for the AI"),
    ("compile", "build the list and the question into one payload for a chatbot"),
    ("all", "expanded menu"),
)

ALL_WORDS = (
    ("menu", "print the shorter list"),
    ("walk", "take guided tour of context compiler (recommended)"),
    ("conn", "get mcp, jira, email, docs, etc. into context"),
    ("context", "edit the list of files an AI will read (after the walk)"),
    ("prompt", "save your clipboard as the question for the AI"),
    ("compile", "build the list and the question into one payload for a chatbot"),
    ("all", "print this expanded list again"),
    # THE THREE WORDS (2026-09-25): context, prompt, compile are the whole
    # loop, on both lists. ahe, ahc and the short spellings still work; epr
    # and cpr are gone with the separate walk router they edited.
    ("brief", "compile this workshop into your clipboard for an AI"),
    ("jn", "start JupyterLab and Pipulate, JupyterLab first"),
    ("pu", "start the Pipulate server"),
)


def print_words(words) -> None:
    """Print one command list from data; short and expanded cannot drift."""
    print("type one:")
    width = max(len(word) for word, _ in words)
    for word, description in words:
        print("  " + word.ljust(width) + "  " + description)


def main() -> int:
    args = set(sys.argv[1:])

    # Recall is a display, not the startup threshold. It deliberately runs
    # before the unattended gates so `menu` and `all` also work when stdout is
    # redirected or PIPULATE_BOOT_MENU=0 is inherited by the shell.
    if "--recall" in args:
        print()
        print_words(ALL_WORDS if "--all" in args else SHORT_WORDS)
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
    except Exception:
        return EXIT_START
    return EXIT_SHELL


if __name__ == "__main__":
    sys.exit(main())
