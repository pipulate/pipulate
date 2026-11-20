#!/usr/bin/env python3
"""
🪧 card.py -- Station-break Figlet title card.

Renders a large Figlet banner (e.g. "THE ITCH") centered on a transient
Alacritty overlay. Used as the leading *label* brush of a station-break bead.

The shared conjure_window actuator owns teardown: it kills this process after
its `duration`, so this script just renders and idles until dismissed. The
self-hold below is a generous LAST-RESORT safety net only -- it must always be
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


def _ensure_repo_root() -> bool:
    from pathlib import Path
    for anc in Path(__file__).resolve().parents:
        if (anc / "imports" / "ascii_displays.py").is_file():
            if str(anc) not in sys.path:
                sys.path.insert(0, str(anc))
            return True
    return False


def _term_size(fallback=(80, 20)):
    import shutil
    if sys.stdout.isatty():
        try:
            return os.get_terminal_size(sys.stdout.fileno())
        except OSError:
            pass
    return shutil.get_terminal_size(fallback)


def render(label: str):
    """Render the label as a horizontally centered Figlet banner (including wrapped/multi-line blocks)."""
    label = label.replace("\\n", "\n")
    sz = _term_size((80, 20))
    term_w, term_h = max(40, sz.columns), max(10, sz.lines)
    inner_w = max(32, term_w - 8)
    clean_banner = ""
    if _ensure_repo_root():
        try:
            from imports.ascii_displays import render_centered_figlet
            clean_banner = render_centered_figlet(label, font="standard", width=inner_w)
        except Exception:
            clean_banner = ""
    if not clean_banner:
        raw = Figlet(font="standard", width=inner_w).renderText(label) if Figlet is not None else label
        clean_banner = "\n".join(ln.rstrip() for ln in raw.splitlines() if ln.strip()) or label.strip()
    if _console is not None:
        try:
            is_tty = sys.stdout.isatty()
            top_pad = max(0, (term_h - ((len(clean_banner.splitlines()) or 1) + 4)) // 2)
            panel = Panel(Text(clean_banner, style="bold bright_cyan", no_wrap=True), border_style="bright_cyan", padding=(1, 3), expand=False)
            con = Console(width=term_w, force_terminal=is_tty, color_system="truecolor" if is_tty else None)
            sys.stdout.write(("\033[?25l\033[2J\033[H" if is_tty else "") + ("\n" * top_pad))
            con.print(Align.center(panel, width=term_w, pad=False), end="")
            sys.stdout.flush()
            return
        except Exception:
            pass
    print(clean_banner)


def _try_animated_card(label: str, hold: float, stop_file=None, pace: str = "standard") -> bool:
    """Play double-buffered tittle-drop entrance + hold when label carries a .I* TLD."""
    norm_label = label.replace("\\n", "\n")
    _ensure_repo_root()
    try:
        from imports.ascii_displays import has_tittle_drop, run_tittle_drop_card
        return bool(has_tittle_drop(norm_label) and run_tittle_drop_card(norm_label, hold=hold, stop_file=stop_file or "", pace=pace))
    except Exception:
        return False


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "Station"

    # Self-hold cap is a LAST-RESORT safety net only; the conjure_window
    # actuator (or an explicit external pkill tied to a real event) is the
    # real source of truth for how long the card stays up. Keep this large --
    # it exists purely to stop a card from hanging forever if every other
    # teardown mechanism somehow fails, not to time the card's actual life.
    hold = 900.0
    if len(sys.argv) > 2:
        try:
            hold = float(sys.argv[2])
        except ValueError:
            hold = 900.0

    stop_file = sys.argv[3] if len(sys.argv) > 3 else None
    pace = sys.argv[4] if len(sys.argv) > 4 else "standard"
    if _try_animated_card(label, hold=hold, stop_file=stop_file, pace=pace):
        return
    last_sz = _term_size((80, 20))
    render(label)
    start_time = time.time()
    while time.time() - start_time < hold:
        if stop_file and os.path.exists(stop_file):
            break
        cur_sz = _term_size((80, 20))
        if cur_sz != last_sz:
            last_sz = cur_sz
            render(label)
        time.sleep(min(0.05, max(0.005, hold - (time.time() - start_time))))


if __name__ == "__main__":
    main()
