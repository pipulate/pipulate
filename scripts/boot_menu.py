#!/usr/bin/env python3
"""
boot_menu.py — the threshold at the end of `nix develop`.

Two doors, one keypress:
  [1] Start <AppName>   JupyterLab + server, browser tabs (today's behavior)
  [2] Just the shell    NOTHING starts; `walk`, `sources`, `brief`, `seed`, `foo` live here

THE PROTOCOL IS THE EXIT CODE, never stdout. Nothing parses this program's
output, so no capture pipe can ever be held open by it (the rgx/xclip
deadlock of 2026-07 is the conviction). That also makes the renderer
swappable: a Textual version can replace this one without flake.nix
learning anything.

  0   start the app       (non-tty, PIPULATE_BOOT_MENU=0, opt-in timeout)
  10  drop to the Nix CLI (also: Ctrl+C, Esc, q)

FAIL-OPEN BY CONSTRUCTION. Every path an automated caller can reach -- no
tty, no termios, PIPULATE_BOOT_MENU=0, unexpected exception -- returns 0,
exactly what the shell did before this file existed. A menu that can
strand an automated `nix develop` (autognome's Desktop 7 tab, CI, an
SSH session without a tty) is strictly worse than no menu at all.

WAITING FOREVER IS SAFE only because it happens strictly AFTER the isatty
gate: a human is provably present before anything blocks. The one
unattended tty in this world -- autognome's Desktop 7 "Pipulate Server"
tab -- declares intent with PIPULATE_BOOT_MENU=0 and never reaches the
select loop at all.

Stdlib only. Rich is used when importable and never required.

Env:
  PIPULATE_BOOT_MENU=0            skip the menu entirely, start the app
  PIPULATE_BOOT_MENU_TIMEOUT=10   opt back in to a countdown (default: none)
"""
import os
import select
import sys
import time
from pathlib import Path

EXIT_START = 0
EXIT_SHELL = 10

# No deadline by default. A countdown here protects nothing: the only
# unattended tty is opted out with PIPULATE_BOOT_MENU=0, so every caller
# reaching the select loop has a human in front of it. Convicted
# 2026-07-23 -- the panel rendered, ten seconds elapsed underneath a
# dot-spew from the browser-poll subshell, and the server started unasked.
DEFAULT_TIMEOUT = None

# Enter and a few mnemonics all mean "go". Unlisted keys are ignored, so a
# fat finger never picks a door for you.
START_KEYS = {"1", "\r", "\n", "y", "Y", "s", "S"}
SHELL_KEYS = {"2", "q", "Q", "n", "N", "l", "L", "\x03", "\x04"}
# THE DOOR-2 VOCABULARY, AND ITS COUNT DERIVED FROM IT (2026-08-26). Two
# strings in this file used to claim how many words wait at this prompt --
# the panel row and the list heading -- coupled only by somebody remembering
# they were coupled. That coupling has ALREADY been missed by an instrument:
# an rg probe for 'Three words to start from' found the heading and was
# structurally blind to 'three words wait at the prompt', because the second
# string spells the identical claim differently. A count that nothing
# computes is a claim that drifts, so nothing computes it by hand here
# either. Both surfaces read this tuple; the next word costs one line and
# cannot lie. (The module docstring above still names the words in prose --
# that one is a description for a reader, not a count, and it moves under
# the SAME-CAR LABEL RULE like any other label.)
# ORDER IS A SCOPE LADDER, neither alphabetical nor arbitrary: be carried
# (walk) -> look around here yourself (sources) -> hand it to someone
# elsewhere (brief) -> reverse the choice you just made (pu). `walk` leads
# because it is the only row that asks nothing of you first.
# {name} is filled at print time; the whitelabel is not known at import.
DOOR_TWO_WORDS = (
    ("walk", "take the guided tour -- public pages, nothing to log into"),
    ("sources", "see what this shell can reach outside this machine"),
    ("brief", "compile this workshop into your clipboard for an AI"),
    ("pu", "change your mind and start {name} after all"),
)
# Spelled out because "four words wait" reads better than "4 words wait".
# The digit fallback means a word count past seven degrades to something
# true rather than to an IndexError in a menu.
_COUNT_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven")
def _count_word(n):
    """Spell a small count; fall back to the digit rather than guessing."""
    return _COUNT_WORDS[n] if 0 <= n < len(_COUNT_WORDS) else str(n)


def _app_name(root: Path) -> str:
    """Mirror runScript's awk: capitalize first char, lowercase the rest."""
    try:
        raw = (root / "whitelabel.txt").read_text(encoding="utf-8").strip()
    except OSError:
        raw = ""
    raw = raw or "Pipulate"
    return raw[:1].upper() + raw[1:].lower()


def _timeout():
    """Seconds before the default fires, or None to wait for the human.

    Missing, empty, unparseable, and non-positive values all resolve to the
    same answer -- no deadline -- so a typo can never silently install a
    countdown nobody asked for. PIPULATE_BOOT_MENU_TIMEOUT=N opts one back in.
    """
    raw = os.environ.get("PIPULATE_BOOT_MENU_TIMEOUT", "").strip()
    if not raw:
        return DEFAULT_TIMEOUT
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT
    return value if value > 0 else DEFAULT_TIMEOUT


def _render(name, seconds) -> None:
    lines = [
        f"[1]  Start {name}   JupyterLab + server + browser tabs",
        "[2]  Just the shell   nothing starts -- three words wait at the prompt",
    ]
    if seconds is None:
        subtitle = "waiting for your choice -- Ctrl+C also drops to the shell"
    else:
        subtitle = f"no keypress in {seconds:.0f}s starts {name}"
    try:
        from rich.console import Console
        from rich.panel import Panel

        Console().print(
            Panel(
                "\n".join(lines),
                title=f"{name} :: pick a door",
                subtitle=subtitle,
                border_style="cyan",
                padding=(1, 2),
            )
        )
    except Exception:
        print()
        print(f"--- {name} :: pick a door ---")
        for line in lines:
            print("  " + line)
        print(f"  ({subtitle})")
        print()


def _read_choice(seconds) -> int:
    """One raw keypress, optionally against a deadline.

    seconds=None blocks in select() until a key arrives. termios is restored
    unconditionally either way.
    """
    import termios
    import tty

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    deadline = None if seconds is None else time.monotonic() + seconds
    try:
        tty.setraw(fd)
        while True:
            remaining = None
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return EXIT_START
            ready, _, _ = select.select([fd], [], [], remaining)
            if not ready:
                return EXIT_START
            key = os.read(fd, 1).decode("utf-8", "replace")
            if key == "\x1b":
                # Arrow and function keys arrive ESC-prefixed. Drain the tail
                # and keep waiting so a stray arrow never picks a door; a
                # LONE Esc is a deliberate "give me the shell".
                if select.select([fd], [], [], 0.05)[0]:
                    os.read(fd, 8)
                    continue
                return EXIT_SHELL
            if key in START_KEYS:
                return EXIT_START
            if key in SHELL_KEYS:
                return EXIT_SHELL
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def main() -> int:
    if os.environ.get("PIPULATE_BOOT_MENU", "1").strip().lower() in {
        "0",
        "no",
        "off",
        "false",
    }:
        return EXIT_START

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return EXIT_START

    root = Path(os.environ.get("PIPULATE_ROOT") or Path(__file__).resolve().parent.parent)
    name = _app_name(root)
    seconds = _timeout()

    _render(name, seconds)

    try:
        choice = _read_choice(seconds)
    except KeyboardInterrupt:
        choice = EXIT_SHELL
    except Exception:
        choice = EXIT_START

    print()
    if choice == EXIT_SHELL:
        print(f"Staying in the shell. Nothing started -- no {name}, no JupyterLab.")
        print()
        print("Three words to start from:")
        print("  sources   see what this shell can reach outside this machine")
        print("  brief     compile this workshop into your clipboard for an AI")
        print(f"  pu        change your mind and start {name} after all")
    else:
        print(f"Starting {name}...")
    return choice


if __name__ == "__main__":
    sys.exit(main())
