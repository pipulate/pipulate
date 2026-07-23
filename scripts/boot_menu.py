#!/usr/bin/env python3
"""
boot_menu.py — the threshold at the end of `nix develop`.

Two doors, one keypress:
  [1] Start <AppName>   JupyterLab + server, browser tabs (today's behavior)
  [2] Just the shell    no server; `learn`, `seed`, `foo`, `ahc` live here

THE PROTOCOL IS THE EXIT CODE, never stdout. Nothing parses this program's
output, so no capture pipe can ever be held open by it (the rgx/xclip
deadlock of 2026-07 is the conviction). That also makes the renderer
swappable: a Textual version can replace this one without flake.nix
learning anything.

  0   start the app       (also: timeout, non-tty, PIPULATE_BOOT_MENU=0)
  10  drop to the Nix CLI (also: Ctrl+C, Esc, q)

FAIL-OPEN BY CONSTRUCTION. Every ambiguous path — no tty, no termios,
unknown env value, timeout, unexpected exception — returns 0, which is
exactly what the shell did before this file existed. A menu that can
strand an automated `nix develop` (autognome's Desktop 7 tab, CI, an
SSH session without a tty) is strictly worse than no menu at all.

Stdlib only. Rich is used when importable and never required.

Env:
  PIPULATE_BOOT_MENU=0            skip the menu entirely, start the app
  PIPULATE_BOOT_MENU_TIMEOUT=10   seconds before the default fires
"""
import os
import select
import sys
import time
from pathlib import Path

EXIT_START = 0
EXIT_SHELL = 10

DEFAULT_TIMEOUT = 10.0

# Enter and a few mnemonics all mean "go". Unlisted keys are ignored and the
# deadline keeps running, so a fat finger never picks a door for you.
START_KEYS = {"1", "\r", "\n", "y", "Y", "s", "S"}
SHELL_KEYS = {"2", "q", "Q", "n", "N", "l", "L", "\x03", "\x04"}


def _app_name(root: Path) -> str:
    """Mirror runScript's awk: capitalize first char, lowercase the rest."""
    try:
        raw = (root / "whitelabel.txt").read_text(encoding="utf-8").strip()
    except OSError:
        raw = ""
    raw = raw or "Pipulate"
    return raw[:1].upper() + raw[1:].lower()


def _timeout() -> float:
    try:
        value = float(os.environ.get("PIPULATE_BOOT_MENU_TIMEOUT", DEFAULT_TIMEOUT))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT
    return value if value > 0 else DEFAULT_TIMEOUT


def _render(name: str, seconds: float) -> None:
    lines = [
        f"[1]  Start {name}   JupyterLab + server + browser tabs",
        "[2]  Just the shell   no server -- type  learn  for the guided tour",
    ]
    try:
        from rich.console import Console
        from rich.panel import Panel

        Console().print(
            Panel(
                "\n".join(lines),
                title=f"{name} :: pick a door",
                subtitle=f"no keypress in {seconds:.0f}s starts {name}",
                border_style="cyan",
                padding=(1, 2),
            )
        )
    except Exception:
        print()
        print(f"--- {name} :: pick a door ---")
        for line in lines:
            print("  " + line)
        print(f"  (no keypress in {seconds:.0f}s starts {name})")
        print()


def _read_choice(seconds: float) -> int:
    """One raw keypress against a deadline. Restores termios unconditionally."""
    import termios
    import tty

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    deadline = time.monotonic() + seconds
    try:
        tty.setraw(fd)
        while True:
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
        print(f"Staying in the shell. {name} is not running.")
        print("Type  learn  to have an AI walk you through the workshop.")
        print(f"Type  python server.py  to start {name} later.")
    else:
        print(f"Starting {name}...")
    return choice


if __name__ == "__main__":
    sys.exit(main())
