#!/usr/bin/env python3
"""
🪧 card.py — Station-break Figlet title card.

Renders a large Figlet banner (e.g. "THE ITCH") centered on a transient
Alacritty overlay. Used as the leading *label* brush of a station-break bead.

The shared conjure_window actuator owns teardown: it kills this process after
its `duration`, so this script just renders and idles until dismissed. The
self-hold below is a generous LAST-RESORT safety net only — it must always be
longer than any caller's `duration`, or this script becomes the thing that
closes the window early instead of the actuator (this is exactly what bit
Honeybot once: a 130s sentinel card died at the old 60s default, well before
the real signal it was waiting on ever arrived). When in doubt, raise this
number, never lower it.

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

    # Self-hold cap is a LAST-RESORT safety net only; the conjure_window
    # actuator (or an explicit external pkill tied to a real event) is the
    # real source of truth for how long the card stays up. Keep this large —
    # it exists purely to stop a card from hanging forever if every other
    # teardown mechanism somehow fails, not to time the card's actual life.
    hold = 900.0
    if len(sys.argv) > 2:
        try:
            hold = float(sys.argv[2])
        except ValueError:
            hold = 900.0

    render(label)
    time.sleep(hold)


if __name__ == "__main__":
    main()
