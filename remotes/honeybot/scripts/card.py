#!/usr/bin/env python3
"""
🪧 card.py — Station-break Figlet title card.

Renders a large Figlet banner (e.g. "THE ITCH") centered on a transient
Alacritty overlay. Used as the leading *label* brush of a station-break bead.

The shared conjure_window actuator owns teardown: it kills this process after
its `duration`, so this script just renders and idles until dismissed.

Usage:
    card.py "THE ITCH"
    card.py "THE ITCH" 6      # optional self-hold cap in seconds
"""

import sys
import time

try:
    from pyfiglet import Figlet
except Exception:
    Figlet = None

try:
    from rich.console import Console
    from rich.align import Align
    from rich.text import Text
    _console = Console()
except Exception:
    _console = None


def render(label: str):
    """Render the label as a Figlet banner, centered if Rich is available."""
    banner = label
    if Figlet is not None:
        try:
            banner = Figlet(font="standard").renderText(label)
        except Exception:
            banner = label

    if _console is not None:
        try:
            _console.clear()
            _console.print(Align.center(Text(banner), vertical="middle"))
            return
        except Exception:
            pass

    print(banner)


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "Station"

    # Self-hold cap is a safety net only; the conjure_window actuator is the
    # real source of truth for how long the card stays up.
    hold = 60.0
    if len(sys.argv) > 2:
        try:
            hold = float(sys.argv[2])
        except ValueError:
            hold = 60.0

    render(label)
    time.sleep(hold)


if __name__ == "__main__":
    main()
