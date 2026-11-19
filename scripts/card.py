#!/usr/bin/env python3
"""
🪧 card.py -- Station-break Figlet title card.

Renders a large Figlet banner centered on a transient Alacritty overlay.
"""

import sys
import time
import os

try:
    from pyfiglet import Figlet
except Exception:
    Figlet = None

try:
    from rich.console import Console
    from rich.align import Align
    from rich.panel import Panel
    from rich.text import Text
    _console = Console()
except Exception:
    _console = None


def render(label: str):
    """Render the label as a Figlet banner, centered if Rich is available."""
    label = label.replace("\\n", "\n")
    banner = label
    if Figlet is not None:
        try:
            banner = Figlet(font="standard").renderText(label)
        except Exception:
            banner = label

    if _console is not None:
        try:
            term_w = _console.size.width or 80
            term_h = _console.size.height or 20
            raw_lines = [ln.rstrip() for ln in banner.splitlines()]
            while raw_lines and not raw_lines[-1].strip():
                raw_lines.pop()
            while raw_lines and not raw_lines[0].strip():
                raw_lines.pop(0)
            clean_banner = "\n".join(raw_lines) if raw_lines else label.strip()
            panel_h = (len(clean_banner.splitlines()) or 1) + 4
            top_pad = max(0, (term_h - panel_h) // 2)
            panel = Panel(
                Align.center(Text(clean_banner, style="bold bright_cyan")),
                border_style="bright_cyan",
                padding=(1, 3),
                expand=False,
            )
            _console.clear()
            if top_pad > 0:
                sys.stdout.write("\n" * top_pad)
            _console.print(Align.center(panel, width=max(40, term_w - 1)), end="")
            sys.stdout.flush()
            return
        except Exception:
            pass

    print(banner)


def _try_animated_card(label: str, hold: float, stop_file=None) -> bool:
    """Play double-buffered tittle-drop entrance + hold when label carries a .I* TLD."""
    from pathlib import Path
    norm_label = label.replace("\\n", "\n")
    for anc in Path(__file__).resolve().parents:
        if (anc / "imports" / "ascii_displays.py").is_file():
            if str(anc) not in sys.path:
                sys.path.insert(0, str(anc))
            break
    try:
        from imports.ascii_displays import has_tittle_drop, run_tittle_drop_card
        return bool(has_tittle_drop(norm_label) and run_tittle_drop_card(norm_label, hold=hold, stop_file=stop_file or ""))
    except Exception:
        return False


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "Station"

    hold = 900.0
    if len(sys.argv) > 2:
        try:
            hold = float(sys.argv[2])
        except ValueError:
            hold = 900.0

    stop_file = sys.argv[3] if len(sys.argv) > 3 else None

    if _try_animated_card(label, hold=hold, stop_file=stop_file):
        return
    render(label)
    if stop_file:
        start_time = time.time()
        while time.time() - start_time < hold:
            if os.path.exists(stop_file):
                break
            time.sleep(0.05)
    else:
        time.sleep(hold)


if __name__ == "__main__":
    main()
