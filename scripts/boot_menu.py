#!/usr/bin/env python3
"""
boot_menu.py — the threshold at the end of `nix develop`.

Three doors, one keypress:
  [1] JupyterLab tab     both servers start; JupyterLab opens in the browser (today's default)
  [2] Text Commands      NOTHING starts; `walk`, `sources`, `brief`, `pu`, `menu` wait at the prompt
  [3] Pipulate tab       both servers start; the app opens in the browser instead of JupyterLab

THE PROTOCOL IS THE EXIT CODE, never stdout. Nothing parses this program's
output, so no capture pipe can ever be held open by it (the rgx/xclip
deadlock of 2026-07 is the conviction). That also makes the renderer
swappable: a Textual version can replace this one without flake.nix
learning anything.

  0   start the app       (non-tty, PIPULATE_BOOT_MENU=0, opt-in timeout)
  10  drop to the Nix CLI (also: Ctrl+C, Esc, q)
  11  start the app, Pipulate tab in front (flake maps this onto the tab shadows)

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
# DOOR 3 (2026-09-03): same servers as door 1, opposite tab. The flake reads
# this code and sets PIPULATE_OPEN_JUPYTER=false / PIPULATE_OPEN_FASTHTML=true
# before its runtime tab shadows resolve. An older flake does not know 11 and
# falls through to door-1 behavior, so this can never strand anyone.
EXIT_PIPULATE = 11

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
PIPULATE_KEYS = {"3", "p", "P"}
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
# because it is the only row that asks nothing of you first. `menu` rides
# LAST and is not a rung on that ladder at all: it is not a place to go, it
# is how you get this list back after it has scrolled away. Its row is also
# the only thing that tells a newcomer the word exists -- a recall command
# nothing announces is a command nobody types.
# No row spells the brand any more, so the .format(name=...) call at the print
# site currently no-ops. It stays: a future row may need it, and a row that
# silently printed a literal {name} would be worse than a call that does
# nothing.
DOOR_TWO_WORDS = (
    ("walk", "take the guided tour -- public pages, nothing to log into"),
    ("sources", "see what this shell can reach outside this machine"),
    ("brief", "compile this workshop into your clipboard for an AI -- the context compiler's first job"),
    ("pu", "change your mind and start the app server after all"),
    ("menu", "print this list again once it scrolls away"),
)
# Spelled out because "four words wait" reads better than "4 words wait".
# The digit fallback means a word count past seven degrades to something
# true rather than to an IndexError in a menu.
_COUNT_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven")
def _count_word(n):
    """Spell a small count; fall back to the digit rather than guessing."""
    return _COUNT_WORDS[n] if 0 <= n < len(_COUNT_WORDS) else str(n)


def print_door_two_words(name):
    """Print the door-two list. ONE implementation, TWO call sites.

    main() prints it at the moment of choice; `menu` prints it again later
    through --recall. Both read the same tuple, so the reminder cannot drift
    from the thing it reminds you of -- which is the whole reason
    DOOR_TWO_WORDS is data rather than two hand-written strings.
    """
    print(_count_word(len(DOOR_TWO_WORDS)).capitalize() + " words to start from:")
    width = max(len(word) for word, _ in DOOR_TWO_WORDS)
    for word, description in DOOR_TWO_WORDS:
        print("  " + word.ljust(width) + "   " + description.format(name=name))


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
    # THE BRAND IS NOT THE DOOR (2026-08-28). Row one said "Start <AppName>"
    # to a reader who has typed exactly one command in their life -- `nix
    # develop` -- and therefore has no referent for the name. It named the
    # SYSTEM where the reader needed the OUTCOME. JupyterLab is what visibly
    # opens; the name is revealed after the choice, and again by the figlet
    # runScript prints on the door-1 path only.
    # `name` IS RETAINED AND CURRENTLY UNUSED HERE, deliberately: it keeps
    # this signature callable as a non-blocking probe
    # (_render("Pipulate", None) renders the panel without waiting on a
    # keypress, which main() cannot do), and a whitelabel install that wants
    # its own name back in the title is then a one-string edit rather than a
    # signature change.
    lines = [
        "[1]  JupyterLab tab     both servers start; JupyterLab opens in the browser",
        f"[2]  Text Commands      nothing starts -- {_count_word(len(DOOR_TWO_WORDS))} words wait at the prompt",
        "[3]  Pipulate tab       both servers start; the app opens in the browser",
    ]
    if seconds is None:
        subtitle = "waiting for your choice -- Ctrl+C also drops to the shell"
    else:
        subtitle = f"no keypress in {seconds:.0f}s opens door 1"
    try:
        from rich.console import Console
        from rich.panel import Panel

        Console().print(
            Panel(
                "\n".join(lines),
                # NOT "Linux": this flake is eachDefaultSystem and carries
                # live Darwin branches, so a title claiming Linux is false on
                # every Mac and invisible to the one person who could fix it.
                # "*nix" is true on Linux, WSL, and certified-UNIX macOS
                # alike, and echoing the command they just typed is the whole
                # education this line owes a first-timer.
                title="nix develop -- a reproducible *nix shell :: pick a door",
                subtitle=subtitle,
                border_style="cyan",
                padding=(1, 2),
            )
        )
    except Exception:
        print()
        print("--- nix develop -- a reproducible *nix shell :: pick a door ---")
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
            if key in PIPULATE_KEYS:
                return EXIT_PIPULATE
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def main() -> int:
    # THE RECALL PATH, AND WHY IT SITS ABOVE EVERY GATE. The door-two list
    # prints once and then scrolls away under whatever the human does next;
    # flake.nix's `menu` calls this to print it again. It runs BEFORE the
    # PIPULATE_BOOT_MENU and isatty gates deliberately: those exist to keep an
    # unattended `nix develop` from blocking at a threshold, and a recall
    # blocks on nothing, so inheriting their fail-open would only make the
    # word print nothing in a pipe and nothing under PIPULATE_BOOT_MENU=0.
    #
    # IT EXITS 0 AS AN ORDINARY SUCCESSFUL DISPLAY, which COLLIDES with
    # EXIT_START. No caller may branch on the exit code of a --recall run, and
    # the flake wrapper deliberately does not: a wrapper that read 0 as "start
    # the app" would launch a server every time `menu` ran without a tty.
    if "--recall" in sys.argv[1:]:
        root = Path(os.environ.get("PIPULATE_ROOT") or Path(__file__).resolve().parent.parent)
        print()
        print_door_two_words(_app_name(root))
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
        print("[2] Text Commands. Nothing started -- no JupyterLab, no server.")
        print()
        print_door_two_words(name)
    elif choice == EXIT_PIPULATE:
        print(f"[3] Starting {name} -- the app tab will open when the server answers.")
    else:
        print(f"[1] Starting {name}...")
    return choice


if __name__ == "__main__":
    sys.exit(main())
