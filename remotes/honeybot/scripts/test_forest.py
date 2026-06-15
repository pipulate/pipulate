#!/usr/bin/env python3
"""
🌲 test_forest.py — Visual-First, Inline, Hardware-Free Forest Tester.

WHAT THIS IS
    A local sandbox for iterating on forest.py (the station-break "beads")
    without touching the audio bus, the threading engine, or X11.

THE DISCIPLINE THIS FILE ENCODES (read before "fixing" it)
    1. PROBE BEFORE PATCH. This file exists because one cheap probe
       (`ls remotes/honeybot/imports/`) returned MISSING, proving the
       obvious approach — borrowing conjure_patronus/conjure_window from
       stream.py — would silently no-op locally (those resolve assets via
       stream.py's parents[1], a Honeybot-only directory layout).
    2. DELETE THE ASSUMPTION, DON'T VERIFY IT. Every popup path
       (patronus, conjure_window) bottoms out in alacritty + X11, which the
       local pipulate flake does not ship. Rather than probe for alacritty,
       this harness renders the art INLINE via figurate() — the pure Rich
       primitive both patronus() and the live stream wrap — so the question
       "is alacritty here?" becomes irrelevant.
    3. IMPORT DATA, NOT ENGINES. We import forest.STATION_SEGMENTS (inert
       data) and ascii_displays.figurate (pure rendering). We do NOT import
       stream.py, which would drag in requests, threading, and an
       instantiated Narrator just to scrounge two functions.
    4. NO SILENT FAILURES. There are zero subprocesses below. If you ever add
       one, point its stderr at THIS terminal, never at DEVNULL — a swallowed
       stderr is exactly what turned a one-line path bug into a lost Saturday.

WHAT IT VALIDATES
    Content fidelity: art fits its panel, borders close, figlet cards render,
    CRC wax seals are intact (drift flagged), and the bead story reads in order.

WHAT IT DOES NOT VALIDATE
    X11 popup geometry, window centering, borderless rendering, z-order. Those
    are Honeybot-only truths — verify them on the server, not here.

Usage:
    python remotes/honeybot/scripts/test_forest.py          # real-time pacing
    python remotes/honeybot/scripts/test_forest.py --fast   # accelerated review
"""

import os
import sys
import time
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    """Walk up to the pipulate repo root (flake.nix + imports/ascii_displays.py).

    Deliberately NOT a hardcoded parents[3]: that brittle offset is the exact
    Honeybot-vs-local divergence this whole harness exists to dodge. We look for
    the two markers that prove we are at the pipulate root, then fall back to
    PIPULATE_ROOT (set by the flake) only if the walk somehow fails.
    """
    cur = start.resolve()
    while cur != cur.parent:
        if (cur / "flake.nix").exists() and (cur / "imports" / "ascii_displays.py").exists():
            return cur
        cur = cur.parent
    env_root = os.environ.get("PIPULATE_ROOT")
    if env_root:
        return Path(env_root).resolve()
    # Last resort: structural guess, loudly suspect.
    print("⚠️  Could not locate repo root via flake.nix; falling back to parents[3].", file=sys.stderr)
    return start.resolve().parents[3]


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = _find_repo_root(SCRIPT_DIR)

# forest.py lives beside us; ascii_displays lives at the repo root.
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT))

try:
    from forest import STATION_SEGMENTS
except ImportError as e:
    print(f"❌ Could not import STATION_SEGMENTS from forest.py: {e}", file=sys.stderr)
    sys.exit(1)

try:
    from imports.ascii_displays import figurate, safe_console_print
except ImportError as e:
    print(f"❌ Could not import figurate from imports/ascii_displays.py: {e}", file=sys.stderr)
    print(f"   (repo root resolved to: {REPO_ROOT})", file=sys.stderr)
    sys.exit(1)


def _render_card_inline(label: str) -> None:
    """Render a station-break title card inline as a figlet banner.

    Mirrors card.py's CONTENT without its screen-clear: card.py calls
    console.clear(), which on the real stage wipes the terminal for a clean
    popup. In a scrolling test log that would erase the very output we are
    reading, so we render the figlet directly and leave the log intact.
    """
    try:
        from pyfiglet import Figlet
        print(Figlet(font="standard").renderText(label))
    except Exception:
        print(f"  ┌─ CARD ─┐  {label}  └────────┘")


def _render_patronus_inline(key: str) -> None:
    """Render a registered figurate asset inline, surfacing CRC drift loudly."""
    art = figurate(key)
    if art.drift:
        print(f"  ⚠️  DRIFT DETECTED in '{key}': wax-seal CRC mismatch — "
              f"the art changed but FIGURATE_LEDGER was not updated.")
    safe_console_print(art.human)


def mock_dispatch_cue(command, content, fast_mode=False) -> None:
    """The visual-first, audio-free twin of stream.py's dispatch_cue.

    Same SAY/PATRONUS/WINDOW/VISIT/WAIT/CLOSE grammar; the SAY clock is mocked
    by the production pacing rule (len/20) so cadence stays honest, and every
    window/visit cue is announced rather than launched.
    """
    if command == "SAY":
        print(f'\n💬 SAY: "{content}"')
        if fast_mode:
            time.sleep(0.4)
        else:
            # Faithful to dispatch_cue's trees pacing: time.sleep(len / 20),
            # with a small floor so very short lines remain readable.
            duration = max(1.5, len(content) / 20.0)
            print(f"   ⏳ voice-clock ≈ {duration:.1f}s")
            time.sleep(duration)

    elif command == "PATRONUS":
        if isinstance(content, dict):
            key = content.get("key", "white_rabbit")
        else:
            key = str(content)
        print(f"🎨 PATRONUS: '{key}' (rendered inline; popup geometry NOT tested here)")
        _render_patronus_inline(key)
        time.sleep(0.15)  # settle, so the panel does not blur into the next print

    elif command == "WINDOW":
        # Grammar: "script.py:seconds[:arg]". The arg has no colon.
        parts = str(content).split(":", 2)
        win_script = parts[0].strip()
        win_arg = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
        if win_script == "card.py" and win_arg:
            print(f"🪧 WINDOW card.py → rendering title card '{win_arg}' inline:")
            _render_card_inline(win_arg)
        else:
            # Report dashboards (education.py, radar.py, ...) are Textual TUIs;
            # they cannot meaningfully render inline in a non-interactive harness.
            print(f"🪟 WINDOW: would launch '{content}' as an X11 overlay "
                  f"(TUI/geometry — verify on Honeybot, skipped locally)")

    elif command == "VISIT":
        # Never launch a real browser from a test harness: that is blast radius
        # and depends on the page actually existing on the live server.
        print(f"🌐 VISIT: would open '{content}' in Firefox (skipped locally)")

    elif command == "WAIT":
        try:
            secs = float(content)
        except (TypeError, ValueError):
            secs = 1.0
        if fast_mode:
            secs = min(0.5, secs)
        print(f"⏱️  WAIT {secs:g}s")
        time.sleep(secs)

    elif command == "CLOSE":
        print("🛑 CLOSE: would tear down browser windows (no-op locally)")

    else:
        # Unknown cue: loud, never silent.
        print(f"❓ UNKNOWN CUE: {command!r} → {content!r}", file=sys.stderr)


def _validate_beads() -> None:
    """Cheap structural check so a malformed bead fails loudly, not weirdly."""
    if not STATION_SEGMENTS:
        print("⚠️  STATION_SEGMENTS is empty — nothing to test.", file=sys.stderr)
        return
    for i, bead in enumerate(STATION_SEGMENTS):
        for j, cue in enumerate(bead):
            if not (isinstance(cue, (tuple, list)) and len(cue) == 2):
                print(f"⚠️  Bead {i}, cue {j} is not a (command, content) pair: {cue!r}",
                      file=sys.stderr)


def main() -> None:
    fast_mode = "--fast" in sys.argv
    print("=" * 64)
    print("🌲 HONEYBOT FOREST TESTER — inline, audio-free, hardware-free 🌲")
    print(f"   repo root : {REPO_ROOT}")
    print(f"   mode      : {'⚡ FAST REVIEW' if fast_mode else '⏱️  REAL-TIME PACING'}")
    print(f"   beads     : {len(STATION_SEGMENTS)}")
    print("   Ctrl+C to abort.")
    print("=" * 64)

    _validate_beads()

    try:
        for idx, bead in enumerate(STATION_SEGMENTS, start=1):
            print(f"\n🎬 BEAD {idx}/{len(STATION_SEGMENTS)}")
            for command, content in bead:
                mock_dispatch_cue(command, content, fast_mode=fast_mode)
            buffer_time = 1.0 if fast_mode else 3.0
            print(f"\n— inter-bead buffer {buffer_time:g}s —")
            time.sleep(buffer_time)
        print("\n✅ All beads reviewed. Content fidelity checked; "
              "popup geometry still owed to Honeybot.")
    except KeyboardInterrupt:
        print("\n🛑 Aborted by operator.")


if __name__ == "__main__":
    main()
