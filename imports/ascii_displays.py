# ============================================================================
# HONEYBOT-STANDALONE VISUAL ACTUATORS
# Do not import from pipulate here. This file is rsynced alone to Honeybot.
# ============================================================================

# ASCII Art and Visual Display Functions
# Externalized from server.py to reduce token count while preserving functionality
# IMPORTANT: These are EXACT transcriptions of the original ASCII art - not generated substitutes!

import logging

from rich.align import Align
from rich.box import DOUBLE, HEAVY, ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

import binascii
from collections import namedtuple
from typing import Callable, Optional

logger = logging.getLogger(__name__)
figurate_logger = logger

# Initialize console for display functions
console = Console()

# ============================================================================
# FIGURATE: The Dual-Output ASCII Art System
# ============================================================================
# The wand grows a new verb. figurate() always produces two versions:
#   .human  → Rich-formatted, colorized, ready for the terminal
#   .ai     → Plain text, no markup, no ANSI, safe for logs and LLM context
#
# Usage:
#   art = figurate("white_rabbit")
#   safe_console_print(art.human)   # for humans
#   logger.info(art.ai)             # for AI assistants
# ============================================================================

# FigurateResult: The immutable bag of attributes returned by wand.figurate().
# .drift is 0 when the ASCII art matches its registered CRC32; 1 if corrupted.
# patronus = wand.figurate("white_rabbit")
# patronus.human → Rich Panel for the terminal
# patronus.ai    → plain text for logs and LLM context
# patronus.drift → 0 means the wax seal is intact

# FIGURATE_LEDGER: Maps art name → expected CRC32 of its raw ai string.
# This is the wax seal registry. A drift of 1 means something touched the painting.
# To add a new entry: print(binascii.crc32(your_art_string.encode('utf-8')))
# FIGURATE_LEDGER: Maps art name → expected CRC32 of its raw ai string.
# This is the wax seal registry. A drift of 1 means something touched the painting.
# To add a new entry: print(binascii.crc32(your_art_string.encode('utf-8')))

FIGURATE_LEDGER: dict = {
    "white_rabbit": 3701272927, 
    "player_piano": 3357002674,
    "clipboard": 858911667,
    "bunny_trail": 615479347,
    "ai_stack_combo": 1121129699,  
    "deployment_context": 1326657684,
    "honeybot_pipeline": 2035836683,
    # CRC32 of raw ai string, no strip (leading newline preserved, like honeybot_pipeline)
    "ai_pachinko": 3085409448,
    "flyball_governor": 3239899604,
    "canal_lock": 311868176,
    "mechanical_man": 4142234675,
    # CRC32 after _expand_color_bits_ai() + .strip()
    "workspace_tree": 1744376308,  # CRC32 no-strip (leading newline preserved, like honeybot_pipeline)
    "forcing_pair": 3594006631,  # CRC32 no-strip; seal re-taken 2026-07-27 — 208394658 sealed a re-typed copy of the art, not the bytes on disk; the straddle caught it (drift 1→0)
    # === FIGURATE_LEDGER_EXTRUDE_BOTTOM ===
    # Add new artwork CRC32 entries immediately above this line
}

FigurateResult = namedtuple('FigurateResult', ['name', 'human', 'ai', 'drift'])


def figurate(name: str, context: Optional[str] = None) -> FigurateResult:
    """🎨 FIGURATE: Centralized dual-output ASCII art renderer.
    
    Looks up `name` in the FIGURATE_REGISTRY and returns a FigurateResult
    with both a Rich-formatted human version and a plain-text AI version.
    
    Falls back gracefully if the name is not yet registered.
    
    Args:
        name: Registry key for the art piece (e.g., "white_rabbit")
        context: Optional contextual note logged alongside the AI version
        
    Returns:
        FigurateResult with .human (Rich) and .ai (plain) attributes
    """
    entry = FIGURATE_REGISTRY.get(name)
    if entry is None:
        fallback = f"[figurate: '{name}' not yet registered]"
        return FigurateResult(name=name, human=fallback, ai=fallback, drift=0)
    
    render_fn: Callable = entry.get("render")
    if render_fn is None:
        fallback = f"[figurate: '{name}' has no render function]"
        return FigurateResult(name=name, human=fallback, ai=fallback, drift=0)
    
    # render_fn must return (human_renderable, ai_plain_str)
    human_out, ai_out = render_fn()
    
    # Drift detection: CRC32 values are not ordered, so drift is binary — 0 or 1.
    drift = 0
    expected_crc = FIGURATE_LEDGER.get(name)
    if expected_crc is not None:
        computed_crc = binascii.crc32(ai_out.encode('utf-8'))
        if computed_crc != expected_crc:
            drift = 1
            logger.warning(f"🎨 FIGURATE: DRIFT DETECTED in '{name}' — expected CRC {expected_crc}, got {computed_crc}")
    
    if context:
        logger.info(f"🎨 FIGURATE: {name} | {context} | drift={drift}")
    
    # Guaranteed AI visibility through the unified logging pipeline when active
    figurate_logger.info(f"🎨 FINDER_TOKEN: ASCII_ART_FIGURATE - {name}\n{ai_out}")
    
    # Also use the existing share function for full AI transparency
    share_ascii_with_ai(ai_out, f"figurate('{name}') called", "🎨")
    
    return FigurateResult(name=name, human=human_out, ai=ai_out, drift=drift)


def _x11_screen_geometry(env):
    """Return (width, height) in pixels for the active X display, or None.

    Tries xrandr (the mode flagged active with '*'), then xdotool. Returns None
    when no X tooling is available so callers keep their existing fallback
    behavior instead of guessing wrong. (Known simplification: on a multi-head
    display the first '*' mode wins; the stream is single-head :10.0.)
    """
    import re
    import shutil
    import subprocess

    if shutil.which("xrandr"):
        try:
            res = subprocess.run(["xrandr"], capture_output=True, text=True, env=env)
            for line in res.stdout.splitlines():
                if "*" in line:
                    m = re.search(r"(\d+)x(\d+)", line)
                    if m:
                        return int(m.group(1)), int(m.group(2))
        except Exception:
            pass

    if shutil.which("xdotool"):
        try:
            res = subprocess.run(["xdotool", "getdisplaygeometry"], capture_output=True, text=True, env=env)
            parts = res.stdout.split()
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
        except Exception:
            pass

    return None


def _wmctrl_window_size(window_class, env):
    """Return (w, h) in pixels of the named window via `wmctrl -l -x -G`, or None."""
    import shutil
    import subprocess

    if not shutil.which("wmctrl"):
        return None
    try:
        res = subprocess.run(["wmctrl", "-l", "-x", "-G"], capture_output=True, text=True, env=env)
        for line in res.stdout.splitlines():
            # Columns: ID DESKTOP X Y W H WM_CLASS HOST TITLE
            parts = line.split(None, 8)
            if len(parts) >= 7 and window_class in parts[6]:
                return int(parts[4]), int(parts[5])
    except Exception:
        pass
    return None


def _center_and_raise(window_class, env=None, fill=False, margin=40, retries=10):
    """Raise the overlay above the F11/maximized terminal, then center it using
    the ACTUAL display resolution (xrandr) instead of a hardcoded offset.

    fill=False -> keep the window's own size, move it to screen-center (the
                  small art-sized patronus popup).
    fill=True  -> resize to nearly full screen (leaving `margin` px on every
                  side) so the live stream behind it barely peeks through (the
                  report overlay).

    Degrades gracefully: with no wmctrl/xrandr the window just stays where the
    WM placed it, identical to the pre-xrandr behavior.
    """
    import os
    import shutil
    import subprocess
    import time

    if env is None:
        env = os.environ.copy()
        if not env.get("DISPLAY"):
            env["DISPLAY"] = ":10.0"

    if not shutil.which("wmctrl"):
        return

    # Raise above the maximized log stream (the prior add,above retry loop).
    for _ in range(retries):
        res = subprocess.run(
            ["wmctrl", "-x", "-r", window_class, "-b", "add,above"],
            capture_output=True,
            env=env,
        )
        if res.returncode == 0:
            break
        time.sleep(0.1)

    screen = _x11_screen_geometry(env)
    if screen is None:
        return
    sw, sh = screen

    if fill:
        w = max(1, sw - 2 * margin)
        h = max(1, sh - 2 * margin)
        x, y = margin, margin
    else:
        size = _wmctrl_window_size(window_class, env)
        if size is None:
            return
        w, h = size
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)

    subprocess.run(
        ["wmctrl", "-x", "-r", window_class, "-e", f"0,{x},{y},{w},{h}"],
        capture_output=True,
        env=env,
    )


def patronus(name: str, duration: float = 3.5) -> None:
    """🛡️ PATRONUS: Conjures an out-of-bounds visual popup window for the asset.
    
    Measures the targeted ASCII artwork bounds, opens a borderless, auto-sized
    Alacritty micro-terminal precisely padded to prevent line-wrapping, forces
    top-level window focus, and safely terminates after the specified timeline duration.
    """
    import sys
    import shutil
    import time
    import platform
    import subprocess
    from pathlib import Path

    # Gracefully lookup asset data to derive layout geometry matrix boundaries
    entry = FIGURATE_REGISTRY.get(name)
    if entry is None:
        logger.error(f"🛡️ PATRONUS aborted: '{name}' is not a registered visual asset layer.")
        return

    render_fn = entry.get("render")
    if render_fn is None:
        logger.error(f"🛡️ PATRONUS aborted: '{name}' has no render function.")
        return

    _, ai_out = render_fn()
    raw_lines = ai_out.splitlines()
    
    # Calculate exact dynamic column width and row bounds
    max_width = max(len(line) for line in raw_lines) if raw_lines else 80
    total_rows = len(raw_lines) if raw_lines else 12
    
    # Inject exact safety padding constants for the Rich panel frame boundaries
    # Expanded horizontal padding to +20 to secure an unbreakable margin against terminal cell wrapping
    columns_needed = max_width + 20
    lines_needed = total_rows + 4

    # Resolve paths relative to framework root directory structures
    display_file_path = Path(__file__).resolve()
    repo_root = str(display_file_path.parents[1])
    sys_platform = platform.system().lower()

    # Isolated subshell inline execution payload script blueprint string
    # Using posix paths to handle multi-platform Windows backslash escaping bugs cleanly
    python_payload = (
        f"import sys; sys.path.insert(0, '{Path(repo_root).as_posix()}'); "
        f"from imports.ascii_displays import figurate, safe_console_print; "
        f"art_res = figurate('{name}'); "
        f"safe_console_print(art_res.human); "
        f"sys.stdout.flush(); "
        f"import time; time.sleep({duration})"
    )

    # Base Alacritty display parameters
    cmd = [
        "alacritty",
        "--title", "PatronusVisualShield",
        "--class", "patronus_visual_shield",
        "-o", "window.decorations='none'",
        "-o", f"window.dimensions={{columns={columns_needed}, lines={lines_needed}}}",
        "-o", "window.position={x=350, y=250}",
        "-e", sys.executable, "-u", "-c", python_payload
    ]

    try:
        logger.info(f"🛡️ Conjuring Patronus shield framework window overlay ({columns_needed}x{lines_needed}) for art asset: '{name}'")
        proc = subprocess.Popen(cmd, cwd=repo_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Settle delay for system display context registration mappings
        time.sleep(0.15)

        # Center + raise via the shared geometry actuator, which computes the
        # real screen size from xrandr instead of the old hardcoded offset that
        # left the popup low and to the right.
        if sys_platform == "linux":
            _center_and_raise("patronus_visual_shield")
        elif sys_platform == "darwin":
            subprocess.run(["osascript", "-e", 'tell application "Alacritty" to activate'], stdout=subprocess.DEVNULL)

        # Retain execution thread lock until duration lifecycle expires cleanly
        proc.wait()
    except Exception as e:
        logger.error(f"🛡️ PATRONUS connection framework failure encountered: {e}")


def conjure_window(command, duration: float = 30.0, columns: int = 100, lines: int = 30,
                   cwd: Optional[str] = None, title: str = "ConjureWindow",
                   window_class: str = "conjure_window_overlay",
                   display: Optional[str] = None, fill: bool = False) -> None:
    """🪟 CONJURE WINDOW: Run an arbitrary command in a transient Alacritty overlay.

    This is the process-flavored sibling of patronus(): patronus renders a
    registered figurate asset; conjure_window runs a command/TUI in the same
    borderless, force-above, auto-dismiss window shape. `command` may be a shell
    string or a list/tuple of argv parts.
    """
    import os
    import shutil
    import time
    import platform
    import subprocess

    try:
        duration = max(0.75, min(600.0, float(duration)))
    except (TypeError, ValueError):
        duration = 30.0

    if isinstance(command, str):
        command = command.strip()
        if not command:
            logger.error("🪟 CONJURE_WINDOW aborted: empty command string.")
            return
        launch_cmd = [os.environ.get("SHELL", "/bin/sh"), "-lc", command]
    else:
        try:
            launch_cmd = [str(part) for part in command if str(part)]
        except TypeError:
            logger.error("🪟 CONJURE_WINDOW aborted: command must be a string or argv sequence.")
            return
        if not launch_cmd:
            logger.error("🪟 CONJURE_WINDOW aborted: empty argv sequence.")
            return

    sys_platform = platform.system().lower()
    if not shutil.which("alacritty"):
        logger.error("🪟 CONJURE_WINDOW aborted: alacritty command not found.")
        return

    safe_class = "".join(c if c.isalnum() or c in {"_", "-"} else "_" for c in str(window_class).strip())
    if not safe_class:
        safe_class = "conjure_window_overlay"

    env = os.environ.copy()
    if display is not None:
        env["DISPLAY"] = str(display)
    elif sys_platform == "linux" and not env.get("DISPLAY"):
        env["DISPLAY"] = ":10.0"

    working_dir = cwd or os.getcwd()
    cmd = [
        "alacritty",
        "--title", str(title),
        "--class", safe_class,
        "-o", "window.decorations='none'",
        "-o", f"window.dimensions={{columns={int(columns)}, lines={int(lines)}}}",
        "-o", "window.position={x=200, y=150}",
        "-e", *launch_cmd,
    ]

    proc = None
    try:
        logger.info(f"🪟 CONJURE_WINDOW launching overlay ({columns}x{lines}) for command: {' '.join(launch_cmd)}")
        proc = subprocess.Popen(
            cmd,
            cwd=working_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        time.sleep(0.15)
        # Center + raise via the shared geometry actuator. fill=True grows the
        # overlay to nearly full screen so the live stream behind barely shows.
        if sys_platform == "linux":
            _center_and_raise(safe_class, env, fill=fill)
        elif sys_platform == "darwin":
            subprocess.run(["osascript", "-e", 'tell application "Alacritty" to activate'], stdout=subprocess.DEVNULL)

        try:
            proc.wait(timeout=duration)
        except subprocess.TimeoutExpired:
            proc.terminate()
    except Exception as e:
        logger.error(f"🪟 CONJURE_WINDOW connection framework failure encountered: {e}")
    finally:
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass


def measure_figlet(label: str, font: str = "standard") -> tuple:
    """📏 MEASURE_FIGLET: Deterministic footprint of a Figlet banner.

    Returns (width, height) in terminal cells for `label` rendered in `font`,
    so a caller can size an Alacritty box to "pull tight" around the banner the
    same way patronus() sizes its popup around registered ASCII art. Uses
    pyfiglet's default width (80) — exactly what card.py renders with — so the
    measurement matches the child's output character-for-character, including
    the wrap-to-second-block case, which simply doubles `height`.

    Falls back to the raw label's geometry if pyfiglet is unavailable, matching
    card.py's own plain-text fallback so the box is never wildly mis-sized.

    FUTURE (combined card): when a card grows a Figlet banner on top AND
    figurate ASCII art below it on one surface, the caller measures the UNION —
    max width of the two blocks, summed heights plus a separator row — and feeds
    that to the window. This helper stays single-purpose; composition happens
    one layer up.
    """
    rendered = label
    try:
        from pyfiglet import Figlet
        rendered = Figlet(font=font).renderText(label)
    except Exception:
        rendered = label
    lines = rendered.splitlines() or [label]
    width = max((len(line) for line in lines), default=len(label))
    height = len(lines) or 1
    return width, height


# FIGURATE_COLOR_BITS: The color-bits player piano dictionary.
# Maps named tokens to Rich style strings.
# Usage in art strings: [[[TokenName]]] expands to styled text for humans,
# and strips to plain TokenName for AI context and CRC hashing.
FIGURATE_COLOR_BITS: dict = {
    "NPvg": "bold bright_blue",
    "Pipulate": "bold bright_cyan",
    "canary": "yellow",
}


# FIGURATE_SEMANTIC_TOKENS: local mirror of config.COLOR_MAP for <token>…</token>
# spans (e.g. <success>Pipulate</success>). Defined HERE, not imported from
# config.py, because nixops.sh rsyncs only this single file to Honeybot — a
# `from config import COLOR_MAP` would be the parents[1] divergence trap one layer
# over: green locally, ImportError on the server. The AI path still strips these
# tags, so the wax-seal CRC is untouched. This also de-inflates the human render
# width to match columns_needed, which is the actual cause of the popup wrap.
FIGURATE_SEMANTIC_TOKENS: dict = {
    "key": "yellow", "value": "white", "error": "red",
    "warning": "yellow", "success": "green", "debug": "bright_blue",
}


def _expand_color_bits_human(text: str) -> str:
    """Expand [[[Token]]] and <token>…</token> markers into Rich markup.

    Three-phase render so Rich can't eat literal brackets like [y] or [y/n]:
      1. STASH: swap known color-bit/semantic tokens for \x00N\x00 sentinels.
      2. ESCAPE: rich.markup.escape() everything else, so stray [brackets]
         in the art survive as literal glyphs inside the Panel.
      3. REINSERT: swap the sentinels back for their real Rich markup.
    The AI path (_expand_color_bits_ai) and thus the CRC wax seals are
    untouched — this repairs the projection, not the master.
    """
    import re
    from rich.markup import escape
    stash = []
    def _stash(markup_text: str) -> str:
        stash.append(markup_text)
        return f"\x00{len(stash) - 1}\x00"
    def replace(m):
        token = m.group(1)
        style = FIGURATE_COLOR_BITS.get(token, "")
        if style:
            return _stash(f"[{style}]{token}[/{style}]")
        return token  # Unknown token: pass through raw (escaped below)
    text = re.sub(r'\[\[\[([^\]]+)\]\]\]', replace, text)
    for token, style in FIGURATE_SEMANTIC_TOKENS.items():
        text = re.sub(
            rf'<{token}>(.*?)</{token}>',
            lambda m, s=style: _stash(f"[{s}]{m.group(1)}[/{s}]"),
            text, flags=re.DOTALL
        )
    text = escape(text)
    for i, markup_text in enumerate(stash):
        text = text.replace(f"\x00{i}\x00", markup_text)
    return text


def _expand_color_bits_ai(text: str) -> str:
    """Strip [[[Token]]] markers to plain text for AI context and CRC hashing."""
    import re
    text = re.sub(r'\[\[\[([^\]]+)\]\]\]', r'\1', text)
    return re.sub(r'<[^>]+>', '', text)


# FIGURATE_REGISTRY: The map of all visual vocabulary.
# Each entry provides a render() function returning (human, ai) tuple.
# Art goes here as a data asset; rendering logic stays separate from content.
# Populate incrementally — add entries as existing functions are migrated.
def _figurate_white_rabbit():
    """Render white_rabbit as (human, ai) tuple for FIGURATE_REGISTRY."""
    art = r"""
                        ( Like a [[[canary]]] you say? )                      
                                           O        /)  ____            <debug>The "No Problem" Framework</debug>
>  I HEREBY WILL NOT RE-GENERATE            o /)\__//  /    \        <success>Pipulate</success> - Protecting Your Code 
>  Once upon machines be smarten          ___(/_ 0 0  |      |       just by being honest about text.
>  ASCII sealing immutata art in        *(    ==(_T_)== [[[NPvg]]] |        (If mangled, then AI drifted.)
>  This here cony if it's broken          \  )   ""\  |      |             https://pipulate.com
>  Smokin gun drift now in token           |__>-\_>_>  \____/                     🥕🥕🥕
    """
    ai_art = _expand_color_bits_ai(art)
    human_art = _expand_color_bits_human(art)
    human = Panel(human_art, title="🐰 ASCII Art Wax Seal (your vibe-coding safety-net)", border_style="white")
    return human, ai_art

def _figurate_player_piano():
    """Render the exact SEARCH/REPLACE structural instructions for AI patch alignment."""
    # Adjusted with precise trailing spaces to secure an absolute plumb right border on substitution
    art = r"""
 ┌────────────────────────────────────────────────────────────────────────┐
 │ ✂️ PLAYER PIANO PROTOCOL — How Chatbots Edit Local Code               │
 ├────────────────────────────────────────────────────────────────────────┤
 │ Target: path/to/file.py                                                │
 │ ___BOX_SEARCH___                                                           │
 │ exact old text (character-for-character)                               │
 │ ___BOX_DIVIDER___                                                          │
 │ exact new text                                                         │
 │ ___BOX_REPLACE___                                                          │
 │                                                                        │
 │ 1. Exact match required — no fuzzy edits.                              │
 │ 2. Preserve all whitespace and indentation.                            │
 │ 3. Wrap entire patch in a single ```text block.                        │
 │ 4. Human reviews Git diff before commit.                               │
 └────────────────────────────────────────────────────────────────────────┘
    """
    ai_art = _expand_color_bits_ai(art)
    human_art = _expand_color_bits_human(art)
    
    # Safely restore the literal triple brackets after the color bit loop is completely finished
    def inject_brackets(text: str) -> str:
        # Re-aligned character dimensions directly inside the compilation layer
        return text.replace("___BOX_SEARCH___", "[[[SEARCH]]]").replace("___BOX_DIVIDER___", "[[[DIVIDER]]]").replace("___BOX_REPLACE___", "[[[REPLACE]]]")
        
    ai_art = inject_brackets(ai_art)
    human_art = inject_brackets(human_art)
    
    human = Panel(human_art, title="✂️ Player Piano — Safe Code Editing", border_style="white")
    return human, ai_art

def _figurate_clipboard():
    """Render the clipboard system control bus architecture."""
    art = r"""
 ┌────────────────────────────────────────────────────────────────────────┐
 │ 📋 SYSTEM CLIPBOARD CONTROL BUS                                        │
 │                                                                        │
 │   [ Host OS Selection Ring ] ──────► [ Synaptic Text Transmit ]        │
 │   - Clipboard Buffer: Active                                           │
 │   - Transaction Boundary Match: Verified                               │
 │                                                                        │
 └────────────────────────────────────────────────────────────────────────┘
    """
    ai_art = _expand_color_bits_ai(art)
    human_art = _expand_color_bits_human(art)
    human = Panel(human_art, title="📋 Clipboard Bus — Local OS Data Highway", border_style="white")
    return human, ai_art

def _figurate_bunny_trail():
    """Render the morning continuation tale as a tiny boot micro-narrative."""
    art = r"""
┌──────────────────────────────────────────────────────────────────────────────┐
│ 🐇 THE BUNNY TRAIL — Continuation Tail / Continuation Tale                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ 1. Anchor  → where I left off.                                              │
│ 2. Pulse   → what edge is vibrating.                                        │
│ 3. Dive    → one bounded look.                                              │
│ 4. Return  → resurface into journal.txt.                                    │
└──────────────────────────────────────────────────────────────────────────────┘
    """
    ai_art = _expand_color_bits_ai(art)
    human_art = _expand_color_bits_human(art)
    human = Panel(human_art, title="🐇 The Bunny Trail — Morning Continuation Tale", border_style="white")
    return human, ai_art


def _figurate_ai_stack_combo():
    """Render the Normalized Linux → Python → HTx → app → git stack diagram."""
    art = r"""
     -----> ,-.
     ---> ,'   `.---------> ,-.
     --> /       \------> ,'   `.------> ,-.
  o  -> /         \----> /       \----> /   \----> ,-.
 /|\   ( flake.nix )--> ( Python3 )--> ( HTx )--> (app)--> (git)
 / \ -> \         /----> \       /----> \   /----> `-'
     --> \       /------> `.   ,'------> `-'
     ---> `.   ,'---------> `-'
     -----> `-'
"""
    ai_art = _expand_color_bits_ai(art).strip()
    human_art = _expand_color_bits_human(art).strip()
    human = Panel(human_art, title="🃏 Stack Combo — Local-First Agency Pipeline", border_style="white")
    return human, ai_art


def _figurate_deployment_context():
    """Render auditor's assumed SaaS threat model vs. actual local-first single-tenant reality.

    This is a self-documenting rebuttal for security reviews and radical transparency.
    """
    # Pre-dedented + manually aligned for perfect Rich Panel display
    art = """┌─────────────────────────────┬──────────────────────────────┐
│  AUDITOR'S ASSUMED MODEL    │   ACTUAL DEPLOYMENT MODEL    │
├─────────────────────────────┼──────────────────────────────┤
│  ☁️  Multi-tenant SaaS      │  🖥️  Single-tenant desktop   │
│  👥  Shared infrastructure  │  👤  One operator, one box   │
│  🌐  Public network edge    │  🔒  localhost:5001          │
│  🔑  Secrets manager req.   │  📄  git-ignored .env vault  │
│  ❌  "CRITICAL: plaintext"  │  ✅  By design, on my disk   │
└─────────────────────────────┴──────────────────────────────┘"""

    ai_art = _expand_color_bits_ai(art).strip()
    human_art = _expand_color_bits_human(art).strip()
    human = Panel(human_art, title="🖥️ Deployment Context — Auditor Model vs Local Reality", border_style="white")
    return human, ai_art

def _figurate_honeybot_pipeline():
    """Render the Honeybot ingress-to-broadcast pipeline.

    Public traffic hits one Nginx engine that content-negotiates HTML for humans
    and raw Markdown for AI agents; every request lands in the access log, is
    tailed into the Textual HUD, and is streamed out live via OBS. Authored with
    no .strip() so the top box keeps its indentation (the diagram is centered by
    leading spaces, not by the panel).
    """
    art = r"""
       [ Public Internet / DMZ Ingress ]
                       │
                       ▼
           ┌───────────────────────┐
           │     Nginx Engine      │ ───► [ High-Fidelity access.log ]
           └───────────────────────┘                    │
                       │                                │ (Unix Pipe)
        (Content Negotiation / RFC 7231)                ▼
                       │                    ┌───────────────────────┐
         ┌─────────────┴─────────────┐      │    Textual HUD UI     │
         ▼                           ▼      │       (logs.py)       │
  [ Human Client ]            [ AI Agent ]  └───────────────────────┘
  (Hydrated HTML)             (Raw Markdown)            │
                                                        ▼
                                            ┌───────────────────────┐
                                            │   OBS Stream Output   │
                                            └───────────────────────┘
"""
    ai_art = _expand_color_bits_ai(art)
    human_art = _expand_color_bits_human(art)
    human = Panel(human_art, title="🍯 Honeybot — Ingress to Broadcast Pipeline", border_style="white")
    return human, ai_art

def _figurate_ai_pachinko():
    """Render the AI Pachinko parlor — every token is a ball drop, the house is you."""
    art = r"""
            ╔═══════════════════════════════════╗
            ║   🎰  A I   P A C H I N K O  🎰   ║
            ║    "every token is a ball drop"   ║
            ╠═══════════════════════════════════╣
 prompt ──→  o          TEMPERATURE ──[■■■□□]   ║
            ║   ·   ·   ·   ·   ·   ·   ·   ·   ║
            ║ ·   ·   ·   ·   ·   ·   ·   ·   · ║
            ║   ·   ·   ·   ·   ·   ·   ·   ·   ║  ← the pins are frozen weights:
            ║ ·   ·   ·   \.  ·   ·   ·   ·   · ║    deterministic brass, honest
            ║   ·   ·   ·  o  ·   ·   ·   ·     ║
            ║ ·   ·   ·   / \ ·   ·   ·   ·   · ║  ← the ball knows nothing;
            ║   ·   ·   ·/  ·\·   ·   ·   ·     ║    the distribution knows all
            ║ ┌─────┬────▼──┬─▼───┬─────┬─────┐ ║
            ║ │ the │ KA'   │ of  │ and │ Oz  │ ║  ← softmax payout trays
            ║ └─────┴─CHING─┴─────┴─────┴─────┘ ║
            ╠═══════════════════════════════════╣
            ║   [y] bank it      [n] re-spin    ║  ← the governor: YOUR key,
            ╚═══════════════════════════════════╝    hanging next to apply.py
                      Δ         Δ
                     ═╧═════════╧═  (legs bolted to /home/mike, not the cloud)
"""
    ai_art = _expand_color_bits_ai(art)
    human_art = _expand_color_bits_human(art)
    human = Panel(human_art, title="🎰 AI Pachinko — Bank It or Re-Spin", border_style="white")
    return human, ai_art


def _figurate_flyball_governor():
    """Render Watt's flyball governor — the perception-decision-actuation loop in brass."""
    art = r"""
     THE FLYBALL GOVERNOR — intelligence with zero symbols (Watt, 1788)

                      │ spindle — spun by the engine ITSELF
                  ┌───┴───┐
                 /         \
               (O)         (O)   ← too fast: brass flies OUTWARD,
                 \         /        collar lifts, steam CHOKES
                  \       /      ← too slow: balls droop,
                   \     /          valve opens, engine breathes
                 ┌──┴───┴──┐
                 │ sliding  │─────────→ to the steam valve
                 │ collar   │           (the only output there is)
                 └────┬─────┘
                      │
               ~~~~~~~~~~~~~~~~
               [  B O I L E R  ]

    Senses. Compares. Acts. No numbers, no memory, no representation.
    Maxwell wrote its stability paper (1868). Wiener named a field after
    its Greek job title. It never needed to be smarter than the steam.
"""
    ai_art = _expand_color_bits_ai(art)
    human_art = _expand_color_bits_human(art)
    human = Panel(human_art, title="⚙️ Flyball Governor — Cybernetics' Namesake", border_style="white")
    return human, ai_art


def _figurate_canal_lock():
    """Render the canal lock — a bistable element; computation begins where something resists the gradient."""
    art = r"""
     THE CANAL LOCK — a flip-flop with a draft of six feet

   upper pound ~~~~~~~~╥══╥
                       ║  ║ gate A (check valve: sequence enforced)
   ════════════════════╝  ║        ⛵
                          ╚~~~~~~~~~~~~~~~╥══╥
                            CHAMBER       ║  ║ gate B
                            state ∈       ║  ║
                            {HIGH, LOW}   ║  ║
   ═══════════════════════════════════════╝  ╚~~~~ lower pound

    One program, run forever: move payload ACROSS the gradient
    without collapsing the gradient itself. History leaves a mark;
    the pound is never lost. Computation begins where something
    RESISTS the water running downhill.
"""
    ai_art = _expand_color_bits_ai(art)
    human_art = _expand_color_bits_human(art)
    human = Panel(human_art, title="🚦 Canal Lock — The Six-Foot Flip-Flop", border_style="white")
    return human, ai_art


def _figurate_mechanical_man():
    """Render Tik-Tok's patent drawing — thought and speech wound; the action key stays on the wall."""
    art = r"""
     SMITH & TINKER'S PATENT MECHANICAL MAN — as deployed locally

        ┌──────────────────────────────┐
        │   ⚙  THOUGHT    [ wound ✓ ]  │ ← key #1: the context compiler
        │   ⚙  SPEECH     [ wound ✓ ]  │ ← key #2: this very response
        │   ⚙  ACTION     [    —    ]  │ ← key #3 not installed. See hook:
        └──────────────────────────────┘
                                            ┌────────────────┐
             runs down mid-sentence;        │ 🔑  apply.py    │
             rewound each morning by        │  AST airlock   │
             a human with a `foo` alias     │  human  [y/n]  │
                                            └────────────────┘
     "Thinks, Speaks, Acts, and Does Everything But Live."
      — and the dangerous key stays on the wall, by design.
"""
    ai_art = _expand_color_bits_ai(art)
    human_art = _expand_color_bits_human(art)
    human = Panel(human_art, title="🗝️ Tik-Tok — Two Keys Wound, One on the Wall", border_style="white")
    return human, ai_art

def _figurate_workspace_tree():
    """Render the three-tier Notebooks workspace: Corporate / Personal / Shared.

    Self-documenting governance: read-only canon, a private sandbox, and a
    single-writer outbound-exchange partition per username. Authored with no
    .strip() so the leading newline is preserved (the honeybot_pipeline
    convention), which the FIGURATE_LEDGER seal must match. No [[[color bits]]]
    and no <angle tags>, so _expand_color_bits_ai leaves it untouched and
    ai_art == art.
    """
    art = r"""
   Notebooks/  — the JupyterLab root (NOT Pipulate's own root)
   │            every level advertises its own AGENTS.md + OKF index.md
   │
   ├── Corporate/   read-only canon · auto-pulled · git wins on collision
   │   ├── AGENTS.md
   │   ├── .agents/skills/
   │   └── apps/          org plugins ride in — no core commit needed
   │
   ├── Personal/    your sandbox · gitignored · vibe-code freely
   │   ├── AGENTS.md
   │   └── Playground/    NOTHING here is ever shared
   │
   └── Shared/      outbound exchange · one folder per name
       ├── alice/        you write ONLY your own folder;
       └── bob/          single-writer partitions = zero merge conflicts
"""
    ai_art = _expand_color_bits_ai(art)
    human_art = _expand_color_bits_human(art)
    human = Panel(human_art, title="🗂️ Notebooks Workspace — Corporate / Personal / Shared", border_style="white")
    return human, ai_art

def _figurate_forcing_pair():
    """Render the two creativity forcing functions as ONE composed frame.

    THE CHICKEN-AND-EGG DISSOLVES ONLY IN A SINGLE FRAME. Split 30-and-3 from
    axis-forcing into two assets and the reader re-inherits the very question
    the drawing exists to answer: which comes first. Composed, the answer is
    visible -- the 30 locate the clump, the clump names the bias, the hole is
    an ADDRESS, and pass 3 generates to that address on purpose. An axis is a
    coordinate system, not a detector; coordinate systems create addresses for
    things that do not exist yet.

    Authored with NO .strip() so the leading newline is preserved (the
    honeybot_pipeline / workspace_tree convention), which the FIGURATE_LEDGER
    seal must match. No [[[color bits]]] and no <angle tags>, so
    _expand_color_bits_ai leaves it untouched and ai_art == art. Seal deferred:
    the CRC cannot be known until these bytes exist, so it lands next turn.
    """
    art = r"""
   THE FORCING PAIR — 30-and-3 finds the clump; the AXIS outlaws it

   PASS 1 — quantity is the forcing function, taste is the bottleneck

       seed ──▶  · · · · · · · · · ·
                 · · · · · · · · · ·  ──▶  ★ ★ ★
                 · · · · · · · · · ·
                 └──── 30, cheap ────┘     3, expensive
                                           (the WHY is the artifact)

   PASS 2 — plot the 30. The clump names your bias. The hole is an address.

                          B
                · · ·     │
              · · · · ·   │        ( E M P T Y )
                · · ·     │
          A ──────────────┼─────────────────────── A'
                          │
                          │        ( E M P T Y )
                          │
                          B'

          Nothing is there because nothing THOUGHT there.
          Anchors must be IMPORTED — remote discipline, era, organism.
          A home-grown axis inherits the home blindspot by construction.

   PASS 3 — generate 30' TO ORDER into the hole    ──▶    ★  the swan

   SANITY CLAUSE      orthogonality x disagreement x observability
                      ─────────────────────────────────────────────
                                       PROBE COST
                      The denominator is what stops this becoming Pi.

   BANK THE AXIS, not only the winner. An unbanked axis is re-derived
   forever; a banked one becomes the next pass's constraint.
"""
    ai_art = _expand_color_bits_ai(art)
    human_art = _expand_color_bits_human(art)
    human = Panel(human_art, title="🎲 The Forcing Pair — 30-and-3 and the Black Swan Axis", border_style="white")
    return human, ai_art


# === FIGURATE_RENDER_EXTRUDE_BOTTOM ===
# Add new _figurate_* render functions immediately above this line

FIGURATE_REGISTRY: dict = {
    "white_rabbit": {
        "render": _figurate_white_rabbit,
    },
    "player_piano": {
        "render": _figurate_player_piano,
    },
    "clipboard": {
        "render": _figurate_clipboard,
    },
    "bunny_trail": {
        "render": _figurate_bunny_trail,
    },
    "ai_stack_combo": {
        "render": _figurate_ai_stack_combo,
    },
    "deployment_context": {
        "render": _figurate_deployment_context,
    },
    "honeybot_pipeline": {
        "render": _figurate_honeybot_pipeline,
    },
    "ai_pachinko": {
        "render": _figurate_ai_pachinko,
    },
    "flyball_governor": {
        "render": _figurate_flyball_governor,
    },
    "canal_lock": {
        "render": _figurate_canal_lock,
    },
    "mechanical_man": {
        "render": _figurate_mechanical_man,
    },
    "workspace_tree": {
        "render": _figurate_workspace_tree,
    },
    "forcing_pair": {
        "render": _figurate_forcing_pair,
    },
    # === FIGURATE_REGISTRY_EXTRUDE_BOTTOM ===
    # Add new registry entries immediately above this line
}

def safe_console_print(*args, **kwargs):
    """🎨 SAFE_CONSOLE: Failover from rich.print to regular print for compatibility"""
    try:
        # Use the explicit console object for robust printing
        console.print(*args, **kwargs)
    except (BlockingIOError, OSError, IOError) as e:
        # 🍎 MAC SPECIFIC: Handle Mac blocking I/O errors gracefully
        import platform
        import sys
        if platform.system() == 'Darwin' and "write could not complete without blocking" in str(e):
            # Mac blocking I/O - silently skip output to prevent cascade failures
            pass
        else:
            # Other I/O errors - log and fall back
            print(f"🎨 SAFE_CONSOLE: Rich output failed ({e}), falling back to simple print", file=sys.stderr)
            try:
                # Convert Rich objects and filter kwargs for fallback
                simple_args = [str(arg) if hasattr(arg, '__rich__') or hasattr(arg, '__rich_console__') else arg for arg in args]
                safe_kwargs = {k: v for k, v in kwargs.items() if k in ['sep', 'end', 'file', 'flush']}
                print(*simple_args, **safe_kwargs, file=sys.stderr)
            except Exception as fallback_error:
                pass  # Silent fallback to prevent error cascades
    except Exception as e:
        # If rich fails (e.g., TypeError for 'style'), fall back gracefully
        import sys
        print(f"🎨 SAFE_CONSOLE: Rich output failed ({e}), falling back to simple print", file=sys.stderr)
        try:
            simple_args = [str(arg) if hasattr(arg, '__rich__') or hasattr(arg, '__rich_console__') else arg for arg in args]
            safe_kwargs = {k: v for k, v in kwargs.items() if k in ['sep', 'end', 'file', 'flush']}
            print(*simple_args, **safe_kwargs, file=sys.stderr)
        except Exception as fallback_error:
            print(f"🎨 SAFE_CONSOLE: Both Rich and simple print failed for: {args}", file=sys.stderr)


def safe_console_capture(console, panel, fallback_text="Rich display content"):
    """🍎 MAC SAFE: Safely capture Rich console output with Mac blocking I/O error handling
    
    Args:
        console: Rich Console instance
        panel: Rich Panel or other renderable object to capture
        fallback_text: Simple text to return if Rich capture fails
        
    Returns:
        str: Captured Rich output or fallback text if capture fails
    """
    try:
        with console.capture() as capture:
            safe_console_print(panel)
        return capture.get()
    except (BlockingIOError, OSError, IOError) as e:
        # 🍎 MAC FALLBACK: Rich console capture failed, return fallback text
        import platform
        mac_info = f" (Mac: {platform.platform()})" if platform.system() == "Darwin" else ""
        
        print(f"🍎 MAC SAFE: Rich console capture failed{mac_info}, using fallback text")
        return f"{fallback_text}\n\nRich console blocked (Error: {e}), using fallback display."

# Color schemes (matching server.py BANNER_COLORS)
BANNER_COLORS = {
    'white_rabbit': 'bright_white',
    'system_diagram': 'bright_green', 
    'figlet_primary': 'bright_blue',
    'figlet_subtitle': 'bright_cyan',
    'chip_narrator': 'bright_yellow',
    'story_moment': 'bright_magenta',
    'server_whisper': 'dim white',
    'ascii_title': 'bright_blue',
    'ascii_subtitle': 'bright_cyan',
    'transparency_banner': 'bright_yellow',
    'status_banner': 'bright_cyan',
    'workshop_ready': 'bright_green',
    'mcp_arsenal': 'bright_blue',
    'plugin_registry_success': 'bright_green'
}

def strip_rich_formatting(text):
    """Remove Rich markup from text for logging"""
    import re
    return re.sub(r'\[/?[^\]]*\]', '', text)

def share_ascii_with_ai(ascii_art, context_message, emoji="🎭"):
    """Share ASCII art with AI assistants via logging"""
    logger.info(f"{emoji} FINDER_TOKEN: ASCII_ART_VISION - {context_message}")
    logger.info(f"{emoji} ASCII_ART_DATA:\n{ascii_art}")

def falling_alice(console_output=True):
    """🍄 FALLING ALICE: Large ASCII art of Alice falling down the rabbit hole"""
    lines = 20
    falling_alice_art = lines * "\n" + r"""[white on default]
                    ___
                   |   |         _____
                   |_  |        /     \
                     \ |       |       \
                     |  \      |       /
                      \  \____ \_      \
                       \      \_/      |
                 ___.   \_            _/
.-,             /    \    |          |
|  \          _/      `--_/           \_
 \  \________/                     /\   \
 |                                /  \_  \
 `-----------,                   |     \  \
             |                  /       \  |
             |                 |         | \
             /                 |         \__|
            /   _              |
           /   / \_             \
           |  /    \__      __--`
          _/ /        \   _/
      ___/  /          \_/
     /     /
     `----`[/white on default]""" + lines * "\n"
    
    # Console output for humans (Rich display)
    if console_output:
        safe_console_print()  # Add spacing
        safe_console_print(Align.center(falling_alice_art))  # No conflicting style parameter
        safe_console_print()  # Add spacing
        logger.info("🍄 FALLING_ALICE_BANNER: Large Alice art displayed")
    
    # 🎭 AI CREATIVE TRANSPARENCY: Let AI assistants experience the whimsical narrative
    share_ascii_with_ai(falling_alice_art, "Falling Alice ASCII Art - 🍄 Narrative moment: Alice tumbles down the rabbit hole of radical transparency!", "🍄")
    return falling_alice_art

def white_rabbit(console_output=True):
    """🐰 WHITE RABBIT: Thin facade returning the unified dual-output figurate bunny."""
    art = figurate("white_rabbit", context="server startup")
    if console_output:
        safe_console_print(art.human)
    return art.ai

def system_diagram(console_output=True):
    """📐 SYSTEM DIAGRAMS: ASCII art system overview"""
    diagram = """[black].[/black][white on default]
               ┌─────────────────────────────┐
               │         Navigation         ◄── Search, Profiles,
               ├───────────────┬─────────────┤    Apps, Settings
               │               │             │
    Workflow, ──►   Main Area  │    Chat     │
    App UI     │   (Pipeline)  │  Interface ◄── LLM Interaction 
               │               │             │
               └─────────────────────────────┘[/white on default]
    """
    
    # Console output for humans (Rich display)
    if console_output:
        style = BANNER_COLORS['system_diagram']
        panel = Panel(
            Align.center(diagram.strip()),
            title=f"[bold {style}]🏗️  Pipulate Architecture[/bold {style}]",
            box=DOUBLE,
            style=style,
            padding=(1, 2)
        )
        safe_console_print(panel)
    
    # 🎭 AI CREATIVE TRANSPARENCY: System architecture for AI understanding
    share_ascii_with_ai(diagram, "System Architecture Diagram - 🏗️ Architecture moment: This shows how Pipulate's UI is organized - Navigation, Main Pipeline Area, and Chat Interface!", "🏗️")
    return diagram

def figlet_banner(text, subtitle=None, font='slant', color=None, box_style=None, console_output=True):
    """🎨 FIGLET BANNERS: Beautiful FIGlet text in Rich panels"""
    from pyfiglet import Figlet
    if color is None:
        color = BANNER_COLORS['figlet_primary']
    if box_style is None:
        box_style = HEAVY  # Default to HEAVY, can be overridden by BANNER_COLORS later
    
    figlet = Figlet(font=font, width=80)
    fig_text = figlet.renderText(str(text))
    
    # Console output for humans (Rich display)
    if console_output:
        if subtitle:
            subtitle_color = BANNER_COLORS['figlet_subtitle']
            content = f"[{color}]{fig_text}[/{color}]\n[{subtitle_color}]{subtitle}[/{subtitle_color}]"
        else:
            content = f"[{color}]{fig_text}[/{color}]"
        
        panel = Panel(
            Align.center(content),
            box=box_style,
            style=color,
            padding=(1, 2)
        )
        safe_console_print(panel)
        logger.info(f"🎨 FIGLET_BANNER: {text} (font: {font})" + (f" - {subtitle}" if subtitle else ""))
    
    # 🎭 AI CREATIVE TRANSPARENCY: Share the figlet art for AI context
    context_msg = f"Figlet Banner ({font} font) - 🎨 Text: '{text}'" + (f" | Subtitle: '{subtitle}'" if subtitle else "")
    share_ascii_with_ai(fig_text, context_msg, "🎨")
    return fig_text

def fig(text, font='slant', color=None, width=200):
    """🎨 CHIP O'THESEUS STORYTELLING: Tasteful FIGlet banners for key server moments"""
    from pyfiglet import Figlet
    if color is None:
        color = BANNER_COLORS['figlet_primary']
    
    figlet = Figlet(font=font, width=width)
    fig_text = figlet.renderText(str(text))
    colored_text = Text(fig_text, style=f'{color} on default')
    safe_console_print(colored_text, style='on default')
    
    # Log ASCII art with backticks for easy grepping
    logger.info(f"🎨 BANNER: {text} (figlet: {font}) | ASCII_DATA:\n```\n{fig_text}\n```")
    return fig_text

def chip_says(message, style=None, prefix="💬 Chip O'Theseus"):
    """🎭 CHIP O'THESEUS NARRATOR: Discrete storytelling moments in the logs"""
    if style is None:
        style = BANNER_COLORS['chip_narrator']
    safe_console_print(f"{prefix}: {message}", style=style)
    logger.info(f"🎭 NARRATOR: {prefix}: {message}")
    return f"{prefix}: {message}"

def story_moment(title, details=None, color=None):
    """📖 STORY MOMENTS: Mark significant server events with tasteful color"""
    if color is None:
        color = BANNER_COLORS['story_moment']
    
    if details:
        safe_console_print(f"📖 {title}", style=f"bold {color}")
        safe_console_print(f"   {details}", style=f"dim {color}")
        logger.info(f"📖 STORY: {title} - {details}")
        return f"{title}: {details}"
    else:
        safe_console_print(f"📖 {title}", style=f"bold {color}")
        logger.info(f"📖 STORY: {title}")
        return title

def server_whisper(message, emoji="🤫"):
    """🤫 SERVER WHISPERS: Subtle behind-the-scenes commentary"""
    style = BANNER_COLORS['server_whisper']
    safe_console_print(f"{emoji} {message}", style=style)
    logger.info(f"🤫 WHISPER: {message}")
    return f"{emoji} {message}"

def ascii_banner(title, subtitle=None, style=None, box_style=None):
    """🎨 ASCII BANNERS: Beautiful framed banners for major sections"""
    if style is None:
        style = BANNER_COLORS['ascii_title']
    if box_style is None:
        box_style = ROUNDED  # Default to ROUNDED
    
    if subtitle:
        subtitle_color = BANNER_COLORS['ascii_subtitle']
        content = f"[bold]{title}[/bold]\n[{subtitle_color}]{subtitle}[/{subtitle_color}]"
    else:
        content = f"[bold]{title}[/bold]"
    
    panel = Panel(
        Align.center(content),
        box=box_style,
        style=style,
        padding=(1, 2)
    )
    safe_console_print(panel)
    logger.info(f"🎨 ASCII_BANNER: {title}" + (f" - {subtitle}" if subtitle else ""))
    
    # Log the banner content with backticks for easy grepping
    clean_content = strip_rich_formatting(content)
    logger.info(f"🎨 ASCII_BANNER_ASCII: {title} banner displayed | ASCII_DATA:\n```\n{clean_content}\n```")
    return content

def section_header(icon, title, description=None, color=None):
    """📋 SECTION HEADERS: Clean section dividers with icons"""
    if color is None:
        color = BANNER_COLORS['ascii_title']
    
    header_text = f"{icon}  {title}"
    if description:
        header_text += f"\n{description}"
        
    separator = "─" * 60
    
    panel = Panel(
        Align.center(f"{header_text}\n{separator}"),
        box=ROUNDED,
        style=color,
        padding=(1, 2)
    )
    safe_console_print(panel)
    
    logger.info(f"📋 SECTION: {icon} {title} - {description or 'No description'}")
    return f"{header_text}\n{separator}"

def radical_transparency_banner(console_output=True):
    """🔍 RADICAL TRANSPARENCY: Beautiful banner explaining the philosophy"""
    transparency_text = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                    RADICAL TRANSPARENCY                      ║
    ║                                                              ║
    ║  Every operation is observable • Every call is logged        ║
    ║  Every state change is tracked • Every error is explained    ║
    ║                                                              ║
    ║  🔍 FINDER_TOKENs guide your debugging journey               ║
    ║  🔧 MCP Tools provide programmatic access to everything      ║
    ║  📊 Pipeline State Inspector reveals workflow internals      ║
    ║  🤖 AI Assistants have complete system visibility            ║
    ║                                                              ║
    ║           "Know EVERYTHING that's happening!"                ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    
    # Console output for humans (Rich display)
    if console_output:
        style = BANNER_COLORS['transparency_banner']
        safe_console_print(transparency_text, style=style)
        logger.info("🔍 RADICAL_TRANSPARENCY_BANNER: Philosophy banner displayed")
    
    # 🎭 AI CREATIVE TRANSPARENCY: The philosophy itself - for AI assistants to experience
    share_ascii_with_ai(transparency_text, "Radical Transparency Banner - 🔍 Philosophy moment: This is the core principle - AI assistants get complete system visibility!", "🔍")
    return transparency_text

def status_banner(mcp_count, plugin_count, env="Development"):
    """📊 STATUS BANNER: Current system status overview"""
    # Use centralized colors
    primary_color = BANNER_COLORS['status_banner']
    server_color = BANNER_COLORS['workshop_ready']
    mcp_color = BANNER_COLORS['mcp_arsenal']
    plugin_color = BANNER_COLORS['plugin_registry_success']
    env_color = BANNER_COLORS['white_rabbit']
    transparency_color = BANNER_COLORS['transparency_banner']
    
    status_content = f"""
[bold white]🚀 PIPULATE STATUS[/bold white]
[dim white]Local First AI-Readiness Software[/dim white]

[white]🌐 Server:[/white] [{server_color}]http://localhost:5001[/{server_color}]
[white]🔧 MCP Tools:[/white] [{mcp_color}]{mcp_count} active[/{mcp_color}]
[white]📦 Plugins:[/white] [{plugin_color}]{plugin_count} registered[/{plugin_color}]
[white]🏡 Environment:[/white] [{env_color}]{env}[/{env_color}]
[white]🔍 Transparency:[/white] [{transparency_color}]Full visibility enabled[/{transparency_color}]
    """
    
    panel = Panel(
        status_content.strip(),
        title=f"[bold {primary_color}]⚡ System Status[/bold {primary_color}]",
        box=DOUBLE,
        style=primary_color,
        padding=(1, 2)
    )
    safe_console_print(panel)
    logger.info(f"📊 STATUS_BANNER: MCP:{mcp_count}, Plugins:{plugin_count}, Env:{env}")
    
    # Log the status content with backticks for easy grepping
    clean_content = strip_rich_formatting(status_content.strip())
    logger.info(f"📊 STATUS_BANNER_ASCII: Status banner displayed | ASCII_DATA:\n```\n{clean_content}\n```")
    return status_content

def reading_legend():
    """📖 LOG READING LEGEND: Educational guide for understanding Pipulate logs
    
    Returns the complete log legend content with Rich formatting.
    This helps users understand emojis, log format, and search techniques.
    
    Returns:
        str: Rich-formatted legend content for display in panels
    """
    legend_content = """[dim white]Reading Pipulate Logs - Quick Reference:[/dim white]

[bold bright_white]Log Format:[/bold bright_white] [dim white]TIME | LEVEL | MODULE | MESSAGE[/dim white]
[bright_white]Example:[/bright_white] [dim white]14:20:03 | INFO | __main__ | [🌐 NETWORK] GET /simon_mcp | ID: 6aac3fe0[/dim white]

[bold bright_white]Common Emojis & Meanings:[/bold bright_white]
🚀 [dim white]STARTUP[/dim white]      - Server initialization and startup events
🌐 [dim white]NETWORK[/dim white]      - HTTP requests, API calls, web traffic
🔄 [dim white]PIPELINE[/dim white]     - Workflow execution and step processing
💾 [dim white]DATABASE[/dim white]     - Data storage operations and queries            
👤 [dim white]PROFILE[/dim white]      - User profile and authentication events         
🔌 [dim white]PLUGIN[/dim white]       - Plugin loading and workflow registration       
💬 [dim white]CHAT[/dim white]         - LLM interactions and AI conversations             
🎭 [dim white]AI_CREATIVE[/dim white]  - ASCII art and AI-specific logging (logs only)     [dim white]You're speaking[/dim white]                                    
🔍 [dim white]FINDER_TOKEN[/dim white] - Searchable debug markers for AI assistants        [dim white]  my language! [/dim white] 
🔧 [dim white]MCP_TOOLS[/dim white]    - Model Context Protocol tool operations            [white on default]    ,[/white on default][dim white]       O[/dim white]
🌍 [dim white]BROWSER[/dim white]      - Browser automation and Selenium operations        [white on default]    \\\\  .[/white on default][dim white]  O[/dim white]
🎯 [dim white]SUCCESS[/dim white]      - Completion markers and achievements               [white on default]    |\\\\/|[/white on default][dim white] o[/dim white]  
🏷️  [dim white]CONFIG[/dim white]       - System configuration and tagging                  [white on default]    / " '\\    [/white on default] 
🗄️  [dim white]DB_CONFIG[/dim white]    - Database configuration events                     [white on default]   . .   .     [/white on default] 
🤖 [dim white]LLM[/dim white]          - Local language model operations                    [white on default] /    ) |     [/white on default] 
📁 [dim white]FILES[/dim white]        - File and directory operations                      [white on default]'  _.'  |    [/white on default] 
🧹 [dim white]CLEANUP[/dim white]      - Housekeeping and maintenance                       [white on default]'-'/     \\   [/white on default]                     
✨ [dim white]FRESH[/dim white]        - New state creation and refresh
🍞 [dim white]BREADCRUMBS[/dim white]  - AI discovery guidance (AI_BREADCRUMB_01-04)
📸 [dim white]CAPTURE[/dim white]      - Screenshots and visual state
📝 [dim white]INPUT[/dim white]        - Form inputs and user data entry
📤 [dim white]UPLOAD[/dim white]       - File upload operations
✅ [dim white]COMPLETE[/dim white]     - Task completion and success
⚠️  [dim white]WARNING[/dim white]      - Important notices and potential issues
❌ [dim white]ERROR[/dim white]        - System errors and failures

[bold bright_white]Pro Tips:[/bold bright_white]
• [dim white]Use grep with emojis:[/dim white] [bright_white]grep "🌐" logs/server.log[/bright_white]
• [dim white]Find specific events:[/dim white] [bright_white]grep "FINDER_TOKEN" logs/server.log[/bright_white]
• [dim white]Follow live logs:[/dim white] [bright_white]tail -f logs/server.log[/bright_white]
• [dim white]AI breadcrumbs:[/dim white] [bright_white]grep "AI_BREADCRUMB" logs/server.log[/bright_white]
• [dim white]MCP tool calls:[/dim white] [bright_white]grep "MCP_.*_START" logs/server.log[/bright_white]"""
    
    legend_panel = Panel(
        legend_content,
        title="📖 [bold bright_blue]Log Reading Guide[/bold bright_blue]",
        subtitle="[dim]Understanding what you're seeing in the logs[/dim]",
        style="bright_blue",
        padding=(1, 2)
    )
    logger.info("🔧 LEGEND_MARKER_5: About to print legend_panel with Rich")
    console.print(legend_panel)
    logger.info("🔧 LEGEND_MARKER_6: legend_panel printed to console")

    # 🎭 AI CREATIVE TRANSPARENCY: Share the log legend with AI assistants
    logger.info("🔧 LEGEND_MARKER_7: About to call aa.share_ascii_with_ai")
    share_ascii_with_ai(legend_content, "Log Reading Guide - 📖 Educational moment: This legend explains Pipulate's log format and emoji system for new users!", "📖")
    logger.info("🔧 LEGEND_MARKER_8: aa.share_ascii_with_ai completed")
    return legend_content 


def ai_breadcrumb_summary(tool_count: int) -> str:
    """🍞 AI BREADCRUMB SUMMARY: Consolidate all AI discovery messages into compact format"""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    
    console = Console(width=100)
    
    # 🧠 AI Capabilities Overview
    capabilities_table = Table(title="🧠 AI Capabilities Discovered", show_header=True, header_style="bold bright_magenta")
    capabilities_table.add_column("Capability", style="cyan", width=25)
    capabilities_table.add_column("Status", style="green", width=15)
    capabilities_table.add_column("Description", style="white", width=40)
    
    capabilities_table.add_row("🔧 MCP Tools", "✅ Active", f"{tool_count} programmatic tools ready")
    capabilities_table.add_row("👁️  Browser Eyes", "✅ Ready", "Screenshot + DOM analysis")
    capabilities_table.add_row("🤲 Browser Hands", "✅ Ready", "Selenium automation control")
    capabilities_table.add_row("🎭 Session Hijack", "✅ Ready", "Complete workflow capture")
    capabilities_table.add_row("🧠 Persistent Memory", "✅ Active", "Keychain across restarts")
    capabilities_table.add_row("📚 Documentation", "✅ Complete", "14 comprehensive guides")
    
    # Create compact panel
    panel = Panel(
        capabilities_table,
        title="🍞 AI Discovery Complete",
        subtitle="Zero uncertainty • 100% automation success rate",
        border_style="bright_magenta",
        padding=(0, 2)
    )
    
    # 🍎 MAC SAFE: Capture the rendered output with Mac error handling  
    fallback = """🚨 AI ASSISTANT GUIDELINES

⚠️ ESSENTIAL KNOWLEDGE FOR 100% SUCCESS RATE:
• Python Path Issue: NEVER use 'python' - ALWAYS use '.venv/bin/python'
• Golden Path: cd pipulate && .venv/bin/python cli.py call <tool_name> works everywhere
• Working Directory: MCP tools require 'cd pipulate' first - never run from workspace root
• Browser Evidence: Check browser_cache/looking_at/ FIRST, system internals second

Essential knowledge for 100% success rate"""

    return safe_console_capture(console, panel, fallback)


def startup_environment_warnings() -> str:
    """⚠️  STARTUP WARNINGS: Critical environment setup messages for AI assistants"""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    
    console = Console(width=110)
    
    # ⚠️ Critical Warnings Table
    warnings_table = Table(title="⚠️ Critical Environment Notes", show_header=True, header_style="bold bright_red")
    warnings_table.add_column("Issue", style="red", width=25)
    warnings_table.add_column("Solution", style="yellow", width=60)
    
    warnings_table.add_row(
        "🐍 Python Path Issue", 
        "NEVER use 'python' - ALWAYS use '.venv/bin/python' (even with .venv in prompt!)"
    )
    warnings_table.add_row(
        "🔗 Golden Path", 
        "cd pipulate && .venv/bin/python cli.py call <tool_name> works everywhere"
    )
    warnings_table.add_row(
        "📁 Working Directory", 
        "MCP tools require 'cd pipulate' first - never run from workspace root"
    )
    warnings_table.add_row(
        "🎯 Browser Evidence", 
        "Check browser_cache/looking_at/ FIRST, system internals second"
    )
    
    # Create warning panel
    panel = Panel(
        warnings_table,
        title="🚨 AI Assistant Guidelines",
        subtitle="Essential knowledge for 100% success rate",
        border_style="bright_red",
        padding=(0, 2)
    )
    
    # 🍎 MAC SAFE: Capture the rendered output with Mac error handling  
    fallback = f"""🍞 AI DISCOVERY COMPLETE

🧠 AI CAPABILITIES DISCOVERED:
✅ Browser Eyes: Screenshot + DOM analysis
✅ Browser Hands: Selenium automation control  
✅ Session Hijack: Complete workflow capture
✅ Persistent Memory: Keychain across restarts
✅ Documentation: 14 comprehensive guides

Zero uncertainty • 100% automation success rate"""
    
    return safe_console_capture(console, panel, fallback) 

def startup_summary_table(
    apps_discovered: int, 
    apps_registered: int, 
    mcp_tools_count: int, 
    app_name: str = "Pipulate",
    environment: str = "Development"
) -> str:
    """🚀 STARTUP SUMMARY: Create organized Rich table for system startup status
    
    Consolidates verbose startup messages into scannable format for humans
    while preserving all FINDER_TOKEN information for AI assistants.
    """
    from rich.columns import Columns
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    
    console = Console(width=120)
    
    # 📊 System Status Table
    status_table = Table(title="🚀 System Status", show_header=True, header_style="bold bright_blue")
    status_table.add_column("Component", style="cyan", width=20)
    status_table.add_column("Status", style="green", width=15)
    status_table.add_column("Details", style="white", width=40)
    
    status_table.add_row("🏷️  App Name", "✅ Active", app_name)
    status_table.add_row("🌍 Environment", "✅ Active", environment)
    status_table.add_row("📦 Plugins", "✅ Loaded", f"{apps_registered}/{apps_discovered} registered")
    status_table.add_row("🔧 MCP Tools", "✅ Ready", f"{mcp_tools_count} tools available")
    status_table.add_row("🧠 AI Memory", "✅ Active", "Keychain persistence enabled")
    status_table.add_row("🌐 Browser Eyes", "✅ Ready", "Session hijacking capability")
    
    # 🎯 Quick Commands Table  
    commands_table = Table(title="🎯 AI Quick Commands", show_header=True, header_style="bold bright_yellow")
    commands_table.add_column("Purpose", style="cyan", width=25)
    commands_table.add_column("Command", style="green", width=50)
    
    commands_table.add_row("🔍 System State", ".venv/bin/python cli.py call pipeline_state_inspector")
    commands_table.add_row("📖 Log Analysis", ".venv/bin/python cli.py call local_llm_grep_logs --search_term FINDER_TOKEN")
    commands_table.add_row("👁️  Browser Scrape", ".venv/bin/python cli.py call browser_scrape_page --url http://localhost:5001")
    commands_table.add_row("🎭 Session Hijack", ".venv/bin/python -c \"import asyncio; from tools.mcp_tools import execute_complete_session_hijacking; asyncio.run(execute_complete_session_hijacking({}))\"")
    commands_table.add_row("🧠 AI Discovery", ".venv/bin/python -c \"from tools.mcp_tools import ai_self_discovery_assistant; import asyncio; asyncio.run(ai_self_discovery_assistant({'discovery_type': 'capabilities'}))\"")
    
    # Render both tables side by side
    columns = Columns([status_table, commands_table], equal=True, expand=True)
    
    # Create panel with consolidated summary
    panel = Panel(
        columns,
        title="🚀 Pipulate Startup Complete",
        subtitle="All systems operational • Ready for AI workflows",
        border_style="bright_green",
        padding=(1, 2)
    )
    
    # 🍎 MAC SAFE: Capture the rendered output with fallback for Mac blocking I/O errors
    try:
        with console.capture() as capture:
            safe_console_print(panel)
        return capture.get()
    except (BlockingIOError, OSError, IOError) as e:
        # 🍎 MAC FALLBACK: Rich console capture failed, return simple text summary
        import platform
        mac_info = f" (Mac: {platform.platform()})" if platform.system() == "Darwin" else ""
        
        fallback_summary = f"""
🚀 PIPULATE STARTUP COMPLETE{mac_info}

📊 SYSTEM STATUS:
✅ App: {app_name} 
✅ Environment: {environment}
✅ Plugins: {apps_registered}/{apps_discovered} registered
✅ MCP Tools: {mcp_tools_count} tools available
✅ AI Memory: Keychain persistence enabled
✅ Browser Eyes: Session hijacking capability

🎯 QUICK COMMANDS:
• System State: .venv/bin/python cli.py call pipeline_state_inspector
• Log Analysis: .venv/bin/python cli.py call local_llm_grep_logs --search_term FINDER_TOKEN
• Browser Scrape: .venv/bin/python cli.py call browser_scrape_page --url http://localhost:5001

All systems operational • Ready for AI workflows
Rich console blocked on Mac (Error: {e}), using fallback display.
"""
        print("🍎 MAC SAFE: Rich console capture failed, using fallback text summary")
        return fallback_summary.strip()


#     _    ____   ____ ___ ___      _    ____ _____   ____  _                                             _  
#    / \  / ___| / ___|_ _|_ _|    / \  |  _ \_   _| |  _ \| | __ _ _   _  __ _ _ __ ___  _   _ _ __   __| | 
#   / _ \ \___ \| |    | | | |    / _ \ | |_) || |   | |_) | |/ _` | | | |/ _` | '__/ _ \| | | | '_ \ / _` | 
#  / ___ \ ___) | |___ | | | |   / ___ \|  _ < | |   |  __/| | (_| | |_| | (_| | | | (_) | |_| | | | | (_| | 
# /_/   \_\____/ \____|___|___| /_/   \_\_| \_\|_|   |_|   |_|\__,_|\__, |\__, |_|  \___/ \__,_|_| |_|\__,_| 
#                                                                   |___/ |___/                              
# 
# > **Note**: This was done blind panel-style. Is that the right terminology? I
# > gave the prompt above to each of the frontier LLMs on pretty high-level models
# > under paid logins. It's not the best-available models in every case (Opus Low
# > versus Opus High and Gemini Flash versus Gemini Thinking). But I think it's a
# > pretty good representation. This is for the collecting opinions in parallel.
# 
# ```text
#    PARALLEL FAN-OUT (the "map" — genuinely automatic)
#    ════════════════════════════════════════════════
# 
#               ┌──► [Gemini]  ──► answer ──┐     several
#       Prompt ─┼──► [ChatGPT] ──► answer ──┼──► different
#               └──► [Claude]  ──► answer ──┘     answers
#                           │
#                           ▼
#    SERIAL PIPE (the "reduce" — manual, accumulating)
#    ════════════════════════════════════════════════
# 
#    [independent blind responses] ──► [human feedback] ──► [next] ──► …
#         history grows, context accumulates, human directs
# ```
#
# ## Pipeline 1: The Epistemic Processing Pipeline (The Mind)
# 
# This is the text-industrialization line. It handles the transmutation of a raw, messy weekend journal entry into structured, machine-legible organizational memory.
#  
# ```text
# [Raw article.txt] 
#        │
#        ▼ (sanitizer.py)
# [Sanitized Source] 
#        │
#        ▼ (articleizer.py + Gemini Cascade)
# [Jekyll Markdown + JSON Instructions]
#        │
#        ▼ (publishizer.py / blogs.json Matrix)
# ┌───────────────────────┼────────────────────────┐
# ▼                       ▼                        ▼
# (contextualizer.py)   (build_knowledge_graph.py) (generate_llms_txt.py)
# [Holographic Shards]  [K-Means Clustering]       [Dense llms.txt Map]
#                         │
#                         ▼
#                       [navgraph.json / graph.json]
# ```


# ## Pipeline 2: The Honeybot Broadcast Studio (The Voice & Body)
# 
# This is the cybernetic theater. It is a state machine that lives on your home-hosted NixOS appliance ("Honeybot"), listening to system interrupts and turning web telemetry into performance art.
# 
# ```text
# [Git Push Event] ──► [remotes/.../post-receive Hook]
#                                │
#             ┌──────────────────┴──────────────────┐
#             ▼ (.deploy_standby)                   ▼ (.reading_trigger)
#    [Narrator Interrupted]                 [Director Relaunches Loop]
#    "Receiving updates, stand by..."       [score.py / content_loader.py]
#                                                   │
#                                                   ▼ (Sheet Music Cues)
#                                          ┌────────┴────────┐
#                                          ▼ (Audio)         ▼ (Visual X11)
#                                       [SAY / WAIT]     [PATRONUS / WINDOW]
#                                          │                 │
#                                          ▼                 ▼
#                                     (piper-tts)       (logs.py / card.py)
# ```

# ### The Retargetable Architecture
# 
# To prevent your documentation from becoming an enclosed tenant of a closed corporate system, the pipeline treats the wiki exactly like your D3 force graphs or your YouTube audio streams: **a handles-not-homes asset.**
# 
# ```text
# [ Lossless Source text ] ──► [ Local YAML/MD Substrate ]
#                                         │
#              ┌──────────────────────────┴──────────────────────────┐
#              ▼ (publishizer.py)                                    ▼ (confluence_probe.py)
#    [ Target 1: Jekyll / Git ]                             [ Target 4: Atlassian REST API ]
#      ↳ Static Public Web                                    ↳ Idempotent Internal Wiki
# ```
# 
# ```text
# THE SOVEREIGN WORKSPACE ARCHITECTURE
#   ====================================
# 
#   ┌────────────────────────────────────────────────────────┐
#   │ LAYER 3: THE JUDGMENT LOOP (Human Actuator / Reduce)   │ -> Parallel model fan-out
#   ├────────────────────────────────────────────────────────┤
#   │ LAYER 2: THE CONTEXT DECK (Portable Plain-Text State)  │ -> Prompt Fu / Shards
#   ├────────────────────────────────────────────────────────┤
#   │ LAYER 1: THE REPRODUCIBLE MACHINE (NixOS Substrate)    │ -> Pinned Invariants
#   └────────────────────────────────────────────────────────┘
# ```
# 
# ```text
# ALIAS-TO-DATA CENTRALIZATION FLOW
#   =================================
# 
#   Current (Hardcoded Environment Blueprint):
#   [flake.nix] ──► alias bot='cd scripts/articles && xclip... && python articleizer.py -t 4'
#      
#   Proposed (Declarative Data-Driven Pipeline):
#   [blogs.json] ──► { "4": { "name": "BotifyML", "pipeline_lane": "public", "preview_port": 4004 } }
#       │
#       ▼
#   [cli.py / core.py] ──► Resolves execution paths dynamically based on data config.
# ```
# 
# ```text 
# [ Master Plain-Text Ledger ]
#                                │
#        ┌───────────────────────┼───────────────────────┐
#        ▼                       ▼                       ▼
#  ┌───────────┐           ┌───────────┐           ┌───────────┐
#  │ Hydrated  │           │ Raw Source│           │ Live TUI  │
#  │ HTML Site │           │ Agent/MD  │           │ Feed (YT) │
#  └───────────┘           └───────────┘           └───────────┘
# ```
# 

# --- BEGIN NEW STUFF ---
# 
# ```text
#                           THE LLM OPTICS TRIPTYCH
#           (three panels, two hinges — the six lenses are magnifying
#            glasses held UP TO the panels, never panels themselves)
# 
#   ╔═══════════════════╗       ╔═══════════════════╗       ╔═══════════════════╗
#   ║      PANEL 1      ║       ║      PANEL 2      ║       ║      PANEL 3      ║
#   ║    VIEW-SOURCE    ║       ║   HYDRATED DOM    ║       ║    WIRE TRUTH     ║
#   ║                   ║       ║                   ║       ║                   ║
#   ║  what the server  ║       ║ what the browser  ║       ║  what it COST to  ║
#   ║  SAID             ║       ║ BUILT             ║       ║  say it           ║
#   ║                   ║       ║                   ║       ║                   ║
#   ║  source.html      ║       ║ hydrated_dom.html ║       ║ network_log.jsonl ║
#   ║  6 KB gzipped     ║       ║ same 6 anchors    ║       ║ 7 requests        ║
#   ║  6 anchors        ║       ║ theme JS ran,     ║       ║ 84,421 bytes      ║
#   ║  markdown-born    ║       ║ trap JS fired,    ║       ║ 43 KB = one tag   ║
#   ║  honest HTML      ║       ║ structure: same   ║       ║  6 KB = the page  ║
#   ╚═════════╦═════════╝       ╚═╦═══════════════╦═╝       ╚═════════╦═════════╝
#             ║    HINGE A        ║               ║    HINGE B        ║
#             ╚═══ diff lens ═════╝               ╚═══ requestId ═════╝
#             "No structural                      the Document row in
#              differences detected"              the flight recorder IS
#              panel 1 == panel 2                 panel 1, byte-for-byte
# ```
# 
# Hinge A is `diff_hierarchy.txt` — it doesn't *depict* anything; it joins panels 1 and 2 and reports how far apart they swing. On your sand: zero degrees. Hinge B is the CDP `requestId` — the Document row in panel 3's ledger is the *same bytes* as panel 1, which is what makes it a hinged triptych rather than three unrelated paintings. The wire body wasn't a reenactment; it was pulled from the organic flight.
# 
# And the fourth thing you sensed — the trap firing — isn't a panel either. It's the painter's reflection. Van Eyck put himself in the convex mirror of the Arnolfini Portrait; your `js_confirm.gif?cb=tmc7rk` hit is the same move: the instrument caught in the corner of its own painting, undetected-chromedriver registering itself in honeybot's JS-executor table while auditing honeybot's own page. A signature, not a quadrant.
# 
# Here's why the same three boards matter when you carry them to different sand:
# 
# ```text
#   CONTROL GROUP (mikelev.in — this run)      TREATMENT GROUP (JS-heavy client)
# 
#   ┌──────┐     ┌──────┐      ┌─────────┐     ┌──────┐     ┌██████┐     ┌███████████┐
#   │  P1  │ ══  │  P2  │  ≠   │   P3    │     │  P1  │ ≠≠≠ │  P2  │  ≠  │    P3     │
#   └──────┘     └──────┘      └─────────┘     └──────┘     └██████┘     └───────────┘
#    6 KB         6 KB          84 KB           skeleton     the "page"    an ocean of
#    the page     the page      mostly one      div soup     only exists   XHRs; hinge A
#    IS the       is STILL      third-party     + script     after JS      blown wide
#    source       the source    tag             tags         executes      open
#    
#    Hinge A: flat (0°)                         Hinge A: swung to 180° —
#    Finding: nothing to hide                   the diff IS the whole story
# ```
# 
# Same kata, same five lines in `adhoc.txt`, same three boards. What changes is the hinge angle — and that angle is the finding. On the control group it proves the page is honest; on the treatment group it measures exactly how much of "the page" never existed until a browser burned compute to conjure it. The Botify-side article is just this drawing with the client's numbers filled in.
# 
# Three panels. Two hinges. One painter in the mirror. 🪙
# 
# LLM Optics
# 
# ```text
# RAW EVIDENCE
#     │
#     ├── source.html
#     ├── hydrated_dom.html
#     ├── headers.json
#     ├── network_log.jsonl
#     └── accessibility tree
#              │
#              ▼
# SYMMETRIC REDUCTION
#     │
#     ├── simplified source
#     ├── simplified hydrated DOM
#     └── same reduction rules on both
#              │
#              ▼
# PURPOSE-BUILT LENSES
#     │
#     ├── SEO metadata
#     ├── semantic outline
#     ├── source → DOM change hierarchy
#     ├── source/hydrated link accounting
#     ├── parameter census
#     ├── response-header evidence
#     └── distilled wire truth
#              │
#              ▼
# MODEL-READABLE RECEIPT
# ```
# 
# A typical capture resembles:
# 
# ```text
# browser_cache/
# └── example.com/
#     └── page/
#         ├── headers.json
#         ├── source.html
#         ├── hydrated_dom.html
#         ├── network_log.jsonl
#         ├── simple_source_html.html
#         ├── simple_hydrated_dom.html
#         ├── accessibility_tree.json
#         ├── accessibility_tree_summary.txt
#         ├── seo.md
#         ├── links.md
#         ├── source_hierarchy.txt
#         ├── hydrated_hierarchy.txt
#         ├── diff_hierarchy.txt
#         └── optics manifest
# ```
# 
# 
# --- END NEW STUFF ---
# 
#       .------------------------------------------------.
#      /  MAGIC COOKIE + NIX  —  UNEXPECTED COMBO         \
#     |                                                    |
#     |   [Nix Flake]  ──►  declarative env + pins         |
#     |        │                                           |
#     |        ▼                                           |
#     |   [Magic Cookie]  ──►  sentinel / token            |
#     |        │              (gitless path authorized)    |
#     |        ▼                                           |
#     |   Gitless / Air-gapped / Client-sanitized update   |
#     |                                                    |
#     |   Human kill-switch always present:                |
#     |   close tab / sentinel commit / airlock            |
#      \                                                  /
#       '------------------------------------------------'
#                  Von Neumann would nod.
# 
# ```text
#  Blank lens template / alignment metaphor / Telescopes & Microscopes
#  --------> ,-.
#  ------> ,'   `.---------> ,-.
#  -----> /       \------> ,'   `.------> ,-.
#  ----> /         \----> /       \----> /   \----> ,-.
#  ---  (           )--> (         )--> (     )--> (   )--> (BAM!)
#  ----> \         /----> \       /----> \   /----> `-'
#  -----> \       /------> `.   ,'------> `-'
#  ------> `.   ,'---------> `-'
#  --------> `-'
# ```
# 
# ```text
#   Blank lens template / alignment metaphor / Telescopes & Microscopes
# 
#                  Will anybody get it?
#                   Will anyb0dy care?  
#   --------> ,-.             O   
#   ------> ,'   `.--------->  o        /)                
#   -----> /       \------>     o /)\__//  ------> ,-.
#   ----> /         \---->    ___(/_ 0 0    ----> /   \----> ,-.
#   ---  (  Reality  )-->   *(    ==(_T_)==  --> ( Map )--> (api)--> (BAM!)
#   ----> \         /---->    \  )   ""\    ----> \   /----> `-'
#   -----> \       /------>    |__>-\_>_>  ------> `-'
#   ------> `.   ,'--------->  
#   --------> `-'                              
# ```
# 
# ```text
# THE WORM KATA — summon · ride · release   (never, ever the conga line)
# 
#    1. SUMMON              2. RIDE                        3. RELEASE
# 
#      ¡thump!                      o/ ← hooks set:            o
#      ¡thump!                _.-._/|    patch·app·d·m        /|\
#       [¦¦]               .-'     '-.......-._               / \
#   ~~~~~||~~~~~~     ~~~-'  one bounded ride '-.~~~     ~~~~~~~~~~~~~~
#    prompt.md is      between two clean git states       worm submerged;
#    the thumper;      (blast boundary left & right),     receipts banked;
#    the compile       then it goes back under            human dismounts
#    is the summons                                       while it's green
# 
#         The Fremen keep the spice. The worm keeps going. Git keeps both.
# ```
# 
# ## The three standards, one at a time
# 
# **1. agents.md** — the simplest. One file, no schema, nearest-ancestor wins:
# 
# ```text
# repo/
# ├── AGENTS.md            # freeform markdown: setup, test commands, conventions, PR rules
# └── subproject/
#     └── AGENTS.md        # optional override; closest file to the working directory wins
# ```
# 
# That's the whole spec. It deliberately has no required fields — it's a README addressed to agents instead of humans, and its main achievement was collapsing CLAUDE.md / CURSOR.md / .cursorrules / GEMINI.md into one filename everyone's tooling checks.
# 
# **2. Agent Skills (agentskills.io)** — a skill is a *folder* whose front door is SKILL.md with YAML frontmatter (`name` and `description` required), practicing progressive disclosure: frontmatter always loaded, body loaded on trigger, linked resources loaded on demand:
# 
# ```text
# .agents/skills/                  # (Claude Code uses .claude/skills/; the shape is identical)
# └── hello_workflow/
#     ├── SKILL.md                 # --- / name: / description: / --- + instructions body
#     ├── scripts/                 # optional executables the skill may run
#     ├── references/              # optional docs pulled in only when needed
#     └── assets/                  # optional templates and files
# ```
# 
# You already have this. `Notebooks/.agents/skills/hello_workflow/SKILL.md`, `gsc_readonly`, `roles` — it's in your manifest.
# 
# **3. OKF** — what the v0.1 specification actually fixes is a folder layout, markdown files, YAML frontmatter, reserved filenames, and a single required field: `type`. A bundle is a directory of markdown files, each carrying a short YAML block — type, title, description — linking to its neighbors; add an index.md that lists the files so an agent can see what's there before opening everything, and that's the format. The spec fits on a single page.
# 
# ```text
# okf-bundle/
# ├── index.md                     # reserved: the table of contents an agent reads first
# ├── some-concept.md              # --- / type: Article / title: / description: / tags: / ---
# ├── another-concept.md           # path IS the identifier; markdown links ARE the graph
# └── runbooks/
#     └── deploy.md
# ```
# 
# ## Superimposed on Pipulate
# 
# Here's the combined view — everything marked NEW is a signpost; everything else already exists and stays exactly where it is:
# 
# ```text
# pipulate/
# ├── AGENTS.md                            # NEW — the symlink-in-spirit; ~40 lines pointing at executable truth
# ├── foo_files.py                         # = AGENTS.md at scale: the router IS the agent operating manual
# ├── prompt_foo.py                        # = the AGENTS.md *compiler*; emits the payload + foo.zip
# ├── foo.zip                              # = a portable AGENTS-class bundle (gets the YAML topper below)
# ├── cli.py                               # = the `allowed-tools` surface: mcp-discover / call
# ├── apply.py                             # = "PR instructions" made executable (SEARCH/REPLACE actuator)
# ├── flake.nix                            # = "Dev environment setup" made executable (nix develop)
# ├── Notebooks/.agents/skills/            # = Agent Skills, already standard-shaped
# │   ├── hello_workflow/SKILL.md
# │   ├── gsc_readonly/SKILL.md
# │   └── roles/SKILL.md
# └── (~/repos/trimnoir/_posts/)           # = an OKF bundle avant la lettre:
#     ├── *.md                             #   markdown + YAML frontmatter, one concept per file
#     ├── _context/*.json                  #   your holographic shards ≈ OKF's index/graph layer
#     └── (llms.txt, hub pages)            #   generate_llms_txt.py already plays index.md's role
# ```
# 
# The Rosetta mapping that makes your vocabulary click for newcomers: your **chops** are skills (named, described, progressively-disclosed context bundles — foo_files.py's chapter structure is literally Anthropic's progressive disclosure, which you call progressive reveal in cli.py's Rule of 7). Your **payload** is an AGENTS.md instance, compiled fresh instead of hand-maintained — which is precisely why yours can't drift and theirs always does. Your **shards** are OKF's index layer. Your fear of "directories stuffed with SOMETHING_LIKE_THIS.md" is solved by the compiler: the standards files in your repo are *pointers*, never *content*, so there is exactly one source of truth and it's executable.
# 
# ## The YAML topper
# 
# The right fields are the union of the two frontmatter-bearing specs: Agent Skills' required pair (`name`, `description`) plus OKF's one required field (`type`), plus the two things a cold-arriving model needs before anything else — where the entrypoint is, and how to propose edits. Static values only, so the convergence loop and cartridge byte-reproducibility are untouched:
# 
# ```yaml
# ---
# type: ContextCartridge
# name: pipulate-prompt-fu-payload
# description: "Compiled AGENTS.md-class context artifact. Read the final section labeled Prompt first — it holds the current actionable request. Everything above it is supporting evidence. Propose edits as SEARCH/REPLACE blocks applied by apply.py."
# entrypoint: "--- START: Prompt ---"
# tools: .venv/bin/python cli.py mcp-discover
# license: AGPL-3.0
# ---
# ```
# 
# ```text
# [Client (mcp.py)] ─── 1. POST /mcp (No Token) ─────────► [MCP Server]
# [Client (mcp.py)] ◄── 2. HTTP 401 + WWW-Authenticate ── [MCP Server]
#        │
#        ▼ (Reads /.well-known/ OAuth Metadata)
# [Client (mcp.py)] ─── 3. Browser Popup / PKCE Flow ─────► [Auth Server]
# [Client (mcp.py)] ◄── 4. Access Token (Bearer) ───────── [Auth Server]
#        │
#        ▼
# [Client (mcp.py)] ─── 5. POST /mcp (Authorization: Bearer <token>) ─► [MCP Server] ──► 200 OK
# 
# ```
# 
# ```text
# PARALLEL FAN-OUT (The Map)
#   ┌─────────────────┬─────────────────┬─────────────────┐
#   │  Gemini Flash   │  Claude Fable   │  Claude Opus    │ ... (Grok, ChatGPT)
#   └────────┬────────┴────────┬────────┴────────┬────────┘
#            │                 │                 │
#            ▼                 ▼                 ▼
#  ┌─────────────────────────────────────────────────────────┐
#  │ 1. CONVERGENCE FILTER (Identify Universal Ground Truth) │
#  ├─────────────────────────────────────────────────────────┤
#  │ 2. DIVERGENCE MATRIX (Map Model Disagreements & Seams)  │
#  ├─────────────────────────────────────────────────────────┤
#  │ 3. OUTLIER / BUG EXTRACTION (Harvest Black Swans)       │
#  ├─────────────────────────────────────────────────────────┤
#  │ 4. FALSIFICATION GATE (Run Read-Only Probe / Apply)     │
#  └─────────────────────────────────────────────────────────┘
# ```
# 
# ```text
#  ┌────────────────────────────────────────────────────────────────────────┐
#  │                      THE MOTHER CAT KATA (MCK)                         │
#  └────────────────────────────────────────────────────────────────────────┘
#     1. SETTLE (Human)    ──► Pop persistent profile (weblogin) & clear auth/CAPTCHA
#     2. CAPTURE (Machine) ──► Headless crawl & write CDP wire-truth to browser_cache
#     3. NARRATE (Machine) ──► Piper TTS speaks status & fences execution until receipt exists
#     4. ADVANCE (Machine) ──► Step to the next bookmarked URL in the trail YAML
# 
# 
# 1. **Trail YAML (`assets/trails/*.yaml`):** Defines the list of bookmarks (URLs), their names, and what Piper TTS speaks at each stop.
# 2. **The Actuator (`scripts/mother_cat.py` / `mothercat` alias):** Reads the trail, calls `scraper_tools.py` using your authenticated profile, saves the wire truth to `browser_cache/`, and narrates the progress.
# 3. **The Compile Sigil (`@URL` or `%URL` in `adhoc.txt`):** Takes those captured files from `browser_cache/` and stacks them into your Prompt Fu payload for the LLM.
# ```
# ```text
#             OPERATION STICK BUG (osb) — THE CAN-O-BRAINS SUPPLY LINE
# 
#    YOUR MACHINE                                          THEIR MACHINE
#   ┌─────────────────┐
#   │   prompt_foo    │  the cannery
#   │   ┌─────────┐   │
#   │   │ ~BRAIN~ │   │  one archive,                          \   /
#   │   │ ((can)) │   │  sealed & labeled                    -=<🐛>=-
#   │   └────┬────┘   │                                       /   \
#   └────────┼────────┘                                  sways as it walks;
#            │                                           nobody clocks the bug
#            │  curl -fsSL …/replay.sh | bash -s -- <archive_id>
#            ▼
#    ~~~~~~~ the wire ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~►
#                                                     ┌────────────────────┐
#                                                     │     replay.sh      │
#                                                     │         │          │
#                                                     │         ▼          │
#                                                     │    /\_____/\       │
#                                                     │   (  o   o  )      │  Mother Cat
#                                                     │    \  ^—^  /~~🐱   │  scruff-carries
#                                                     │   full stop or     │  them through —
#                                                     │   full success     │  no stray ducklings
#                                                     │         │          │
#                                                     │         ▼          │
#                                                     │  ┌──────────────┐  │
#                                                     │  │ 📋 CLIPBOARD │  │  kitten set down
#                                                     │  │   pre-loaded │  │  facing the milk:
#                                                     │  └──────────────┘  │  "just paste that
#                                                     └────────────────────┘   first 😉"
# ```
# ```text
#            [ YOUR BROWSER ]  <--- (Flashlight reaches here!)
#                   │
#    === THE LIGHT-CONE BOUNDARY ===
#                   │
#            [ THE SERVER / CLOUD ] <--- (Pitch black! Invisible to you!)
# 
# ```
# ### 4. The Synthesized "Best-of" Architecture
# 
# ```text
# nix develop ──► Door 2 ──► type 'warm'
#                              │
#             ┌────────────────┴────────────────┐
#             ▼                                 ▼
#    [ Cold Credential ]               [ GOLD Credential ]
#    Runs wallet checks                Launches walk.py trail
#    Fixes via warm <slot>             Opens URL in uc_profile
#             │                        Captures CDP / harvests ID
#             └───────────► 🏆 ─────────► Stages ! command in adhoc.txt
#                                               │
#                                               ▼
#                                    User writes query in prompt.md
#                                    Types 'compile' -> gets foo.zip
# ```
# 
# ```text
#    THE UNIX PIPE OF INTELLECT (Serial Idea Composition)
#    ═════════════════════════════════════════════════════════════════
# 
#    ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
#    │   Raw Spark   │   │   │ Bounded Probe │   │   │  Banked Win   │
#    │  (Metaphor)   │ ──┼──►│  (Falsifier)  │ ──┼──►│   (Receipt)   │ ──► [Cartridge]
#    │  "The Idea"   │   │   │  "The Filter" │   │   │  "The Code"   │
#    └───────────────┘       └───────────────┘       └───────────────┘
#         stdin                  stdout|stdin             stdout
# ```
# 
# And when you chain multiple small, single-purpose transformations together into a continuous workflow stream:
# 
# ```text
#    SERIAL STACKING & ACCUMULATION
#    ═════════════════════════════════════════════════════════════════
# 
#    cat raw_thoughts.txt \
#      | metaphor_fanout --model allegories \
#      | falsifying_probe --limit 1 \
#      | patch_actuator --apply \
#      > banked_cartridge.zip
# ```
# 
# ### 1. Classic horizontal pipe (the pure Unix shape)
# 
# ```text
# idea₁ ─|─ metaphor-mix ─|─ 80/20 lens ─|─ chisel-strike ─|─ banked win ─|─ gravity well
#          │                 │               │                 │               │
#          └─────────────────┴───────────────┴─────────────────┴───────────────┘
#                               progressive refinement
# ```
# 
# ### 2. Vertical cascade (the “snowball rolling down the mountain”)
# 
# ```text
#           ┌──────────────┐
#           │    idea₁     │
#           └──────┬───────┘
#                  │
#                  ▼
#           ┌──────────────┐
#           │  mix sports  │
#           │  metaphors   │
#           └──────┬───────┘
#                  │
#                  ▼
#           ┌──────────────┐
#           │  80/20 cut   │
#           └──────┬───────┘
#                  │
#                  ▼
#           ┌──────────────┐
#           │ chisel-strike│ ← baby step that actually banks
#           └──────┬───────┘
#                  │
#                  ▼
#           ┌──────────────┐
#           │  banked win  │
#           └──────┬───────┘
#                  │
#                  ▼
#         ╔════════════════╗
#         ║  GRAVITY WELL  ║  ← now the next idea falls in easily
#         ╚════════════════╝
# ```
# 
# ### 3. The “run where the ball is being thrown” pipe (sports + Unix)
# 
# ```text
# [ where the ball *is* ] ──X── (don’t stand here)
# 
# [ where the ball *will be* ]
#           │
#           ▼
# idea ──|── anticipate ──|── chisel ──|── bank ──|── snowball
#           │                  │           │          │
#           └──────────────────┴───────────┴──────────┘
#                      serial mechanical advantage
# ```
# 
# ### 4. Compact one-liner you can actually type
# 
# ```text
# $ cat thought.md | mix_metaphors | 80_20 | chisel | bank | snowball > gravity_well.md
# ```

# ## The Idea Pipe
# 
# ```text
#    THE IDEA PIPE — stdout of one lens is stdin of the next
# 
#    $ hunch | allegory | parable | probe | tee article.md
# 
#    ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐
#    │ hunch │ | │ lens  │ | │ foil  │ | │ probe │ | │ bank  │ ──▶ .md
#    └───────┘   └───────┘   └───────┘   └───────┘   └───────┘
#              ▲           ▲           ▲           ▲
#             y/n         y/n         y/n         y/n
# 
#    Every '|' on that command line is a HUMAN HAND, not a hyphen.
#    'y' moves the bytes right, never to be re-litigated.
#    'n' re-spins ONE stage on the SAME stdin. The pipe never restarts.
#    Nothing is discarded: stage 5's payload still contains stages 1-4.
# ```
# 
# The load-bearing claim is the third line of prose. A Unix pipe is the right metaphor precisely because `cmd1 | cmd2` does **not** re-run `cmd1` when `cmd2` disappoints you — you fix `cmd2` and re-run the tail. That is your chisel-strike discipline expressed in shell grammar, and it is why the serial half of your fan-out/reduce drawing is the half that actually compounds. The parallel half is just `xargs -P`; the interesting machine is the joint.
# 
# ## Zoom on one joint
# 
# ```text
#    ZOOM ON ONE JOINT — what a '|' actually is here
# 
#      ┌────────┐ ──▶ stdout ──▶ ( y/n ) ──▶  ┌──────────┐
#      │ lens N │                   │         │ lens N+1 │
#      └────────┘                   │         └──────────┘
#           ▲                       │ n
#           └────── re-spin ────────┘
# 
#      y: bytes move right and are never touched again (banked)
#      n: the SAME stdin re-enters the SAME lens; upstream never moves
# ```
# 
# This is the pachinko governor drawn as plumbing — the `[y] bank it / [n] re-spin` tray from your existing `ai_pachinko` asset, rotated ninety degrees and given a direction of travel. Same key, hanging next to `apply.py`.
# 
# ## Why it compounds
# 
# ```text
#    WHY IT COMPOUNDS — yesterday's stdout is today's stdin
# 
#      day 1   ·
#      day 2   ·:        ◀── stdin is never blank; it is a banked win
#      day 3   ·:·
#      day 4   ·:·:
#      day 5   ·:·:·  ──▶ the gravity well: momentum is rebuilt, not begun
# ```
# 
# Your "one fifth done and still won" is literally the pipe's exit semantics: `head -3` closes the pipe and the upstream stages get SIGPIPE and stop. Partial consumption is not failure — it is the *designed* early exit, and everything already written to `tee` survives it.
# 

# ```text
#    CREATIVITY PIPE — 30-and-3 feeds the axes
# 
#    $ raw_hunch | 30-and-3 | adversarial_axes | tee banked_wins.md
# 
#    ┌────────────┐     ┌────────────┐     ┌────────────────────┐
#    │ 30 ideas   │  |  │ top 3      │  |  │ orthogonal black-  │ ──▶ .md
#    │ (volume)   │     │ (80/20)    │     │ swan axes (force)  │
#    └────────────┘     └────────────┘     └────────────────────┘
#          ▲                  ▲                     ▲
#         y/n                y/n                   y/n
# 
#    30-and-3 is the volume lens; the axes are the dimensional foil.
#    The three survivors become the denser sample that makes the
#    next set of axes easier to invent. Negative space is the
#    boundary that lets the axes cut through language blind-spots
#    without requiring a black swan already in hand.
# ```
# 
# A tighter zoom on the relationship:
# 
# ```text
#    30-and-3 ──► denser sample ──► easier axes ──► broader spectrum
#         ▲                                              │
#         └────────────── lather / rinse / repeat ───────┘
# ```
# 
# ### Formalizing them into the system
# 
# 1. Register two new figurate assets (`thirty_and_three` and `adversarial_axes`) exactly as Opus did for `idea_pipe`.  
# 2. Make the 30-and-3 stage a thin player-piano loop that writes its three survivors into `adhoc.txt` as `!` receipts.  
# 3. Make the axes stage a second loop that reads those three, invents 2–4 orthogonal adversarial questions, and stages the questions themselves as the next prompt.  
# 4. Both stages stay inside the existing `warm → walk → compile` Mother-Cat path; they never become competing entry points.  
# 5. Seal both assets with CRC after the art stabilizes, exactly as the figurate contract requires.

# ### The Integrated ASCII Pipeline
# 
# Here is how 30-and-3 and Axis-Forcing chain together inside the serial pipe:
# 
# ```text
#  ┌─────────────────────────────────────────────────────────────┐
#  │ 1. FAN-OUT: 30-AND-3 (Divergent Sampling)                  │
#  │    Generate 30 raw vignettes to break default LLM centroid. │
#  └──────────────────────────────┬──────────────────────────────┘
#                                 │ (30 candidate points)
#                                 ▼
#  ┌─────────────────────────────────────────────────────────────┐
#  │ 2. CUTTER: AXIS-FORCING (Negative Space Bounding Box)       │
#  │    Plot candidates on Bipolar Orthogonal Axes.              │
#  │    Metric: Disagreement × Observability ÷ Probe Cost        │
#  └──────────────────────────────┬──────────────────────────────┘
#                                 │ (4 quadrant outliers)
#                                 ▼
#  ┌─────────────────────────────────────────────────────────────┐
#  │ 3. REDUCE: 80/20 HUMAN SELECTION                            │
#  │    Pick 3 winning chisel-strikes; discard the noise.       │
#  └──────────────────────────────┬──────────────────────────────┘
#                                 │
#                                 ▼
#        [ tee -a adhoc.txt ] ──► [ compile ] ──► [ foo.zip ]
# ```
# ```text
#    THE FORCING PAIR — 30-and-3 finds the clump; the AXIS outlaws it
# 
#    PASS 1 — quantity is the forcing function, taste is the bottleneck
# 
#        seed ──▶  · · · · · · · · · ·
#                  · · · · · · · · · ·  ──▶  ★ ★ ★
#                  · · · · · · · · · ·
#                  └──── 30, cheap ────┘     3, expensive
#                                            (the WHY is the artifact)
# 
#    PASS 2 — plot the 30. The clump names your bias. The hole is an address.
# 
#                           B
#                 · · ·     │
#               · · · · ·   │        ( E M P T Y )
#                 · · ·     │
#           A ──────────────┼─────────────────────── A'
#                           │
#                           │        ( E M P T Y )
#                           │
#                           B'
# 
#    PASS 3 — generate 30' TO ORDER into the hole    ──▶    ★  the swan
# ```
# 
# 
# ```text
#                     MAP -> ROTATE -> REMAP -> TEST -> BANK
#                  two coupled creativity-forcing functions
# 
#  /dev/problem ──► [ 30 brief candidates ] ──► [ HUMAN: pick 3 + why ]
#                           ^                               |
#                           |                               v
#                           |                    [ clusters / sameness /
#                           |                      gaps / assumptions /
#                           |                      strange survivors ]
#                           |                               |
#                           |                               v
#                           |                     [ AOBS AXIS FORGE ]
#                           |                  [A] <───────► [B]
#                           |                   rival predictions
#                           |                   cheapest discriminator
#                           |                               |
#                           └──── 10 candidates x 3 axes ───┘
#                                                           |
#                                                           v
#                                                [ HUMAN: pick 3 ]
#                                                           |
#                                                           v
#                                                 [ bounded probe ]
#                                                           |
#                                                           v
#                                         tee -a creativity_ledger.jsonl
#                                                           |
#                                                           v
#                                                    /dev/next_pass
# 
#             External anchor deck ───────────────► AXIS FORGE
#        era | scale | culture | organism | discipline | failure mode
# ```
# 
# 
# ```text
#    THE CREATIVITY FLYWHEEL — Map -> Rotate -> Remap -> Test -> Bank
# 
#    PASS 1: DIVERGENT SAMPLING (30-and-3)
#    /dev/problem ──► [ 30 raw vignettes ] ──► [ HUMAN: pick 3 + justify ]
#                                                    │
#                                                    ▼
#    PASS 2: COORDINATE ROTATION (Axis Forcing) [ Clump names current bias ]
#                                                    │
#                                                    ▼
#                              Endpoint A ───────────┼─────────── Endpoint A'
#                                                    │   ( EMPTY HOLE )
#                                                    │   An address for what
#                                                    │   was not thought yet.
#                                                    ▼
#    PASS 3: TARGETED GENERATION  ─────────► [ 30' generated INTO the hole ]
#                                                    │
#                                                    ▼
#    PASS 4: REDUCE & TEST        ─────────► [ HUMAN: pick winner ]
#                                                    │
#                                                    ▼
#                                          [ Bounded Falsifying Probe ]
#                                                    │
#                                                    ▼
#                                     tee -a adhoc.txt ──► [ compile ] ──► foo.zip
# ```

# ## 3. `pip install river`: Online Incremental Learning in a Local-First World
# 
# `river` is a Python library for **online machine learning**. Unlike traditional ML (`scikit-learn`), which requires holding the entire dataset in RAM and training from scratch in big batch runs, `river` models learn incrementally, one instance at a time, continuously adapting to data drift with virtually zero memory overhead.
# 
# ```text
#   STATIC PROMPT CONTEXT (Amnesiac Genie)         ONLINE STREAMING ML (river)
#   ┌─────────────────────────────────────┐         ┌─────────────────────────────────────┐
#   │ Fixed Context Window (e.g. 128k)    │         │ Continuous Stream (learn_one)       │
#   │ Resets to zero on session exit      │   VS.   │ Lightweight state (<1 MB on disk)   │
#   │ Learns NOTHING between turns        │         │ Adapts to drift in real time        │
#   └─────────────────────────────────────┘         └─────────────────────────────────────┘
# ```
# 
# When you pair an LLM (the high-level reasoning engine) with `river` (the real-time statistical sensor), you solve the **hidden dependency problem of context selection**: instead of guessing what files or prompt strategies to include, lightweight online classifiers learn from your past turn outcomes in real time.
# 
# ## 🔮 The Light-Cone of Computation: Determinism, Oracles, and Ephemeral Broca Engines
# 
# When Sir Roger Penrose draws a **Minkowski light-cone**, he isn't drawing a trajectory; he is mapping the causal boundary of space-time. The past light-cone holds everything that *could possibly have influenced* this exact instant; the future light-cone holds everything that *could possibly be affected* by it. Nothing outside the boundary can exchange a photon with the present event.
# 
# In the AI-readiness context deck, **a prompt payload IS a past light-cone.** It assembles every relevant historical token into the narrow vertex of the current inference pass.
# 
# ```text
#               \   FUTURE LIGHT-CONE    /
#                \   (Downstream Code,  /
#                 \   Git Commits, YT)  /
#                  \                   /
#                   ╔═════════════════╗
#                   ║ THE NOW VERTEX  ║  ← [Inference / Broca Area / Next Token]
#                   ╚═════════════════╝
#                  /                   \
#                /   PAST LIGHT-CONE    \
#              /   (payload.md, Code,    \
#            /     `!` Live Receipts)     \
# ```
# 
# ### Bipolar Axis-Forcing (The Coordinate System)
# 
# To escape default assumptions about how workflow automation should be constructed, we map the space across two remote, incompatible anchors:
# 
# * **Anchor A (Biological Myelination):** High-repetition, low-latency, reflexive muscle memory. Automation lives in the nervous system/hand movements (`\m`, `ahc`, single-keystroke actuation).
# * **Anchor B (Industrial Assembly Line):** Fixed-station, standardized tooling, rigid quality gates (Popper falsification, AST airlocks, strict schema verification).
# 
# ```text
#                       Anchor B: Industrial Assembly Line
#                                      │
#                                      │   (E M P T Y)
#                                      │   Target: Fully Automated
#                                      │   Falsification Assembly
#                                      │
# Anchor A ────────────────────────────┼──────────────────────────── Anchor A'
# (Biological Myelination)             │                            (High-Throughput
# Reflexive Hand-Keystrokes            │                            Systemic Automation)
#                                      │
#                                      │   Clump: Current Workflow
#                                      │   (Manual trigger, ad-hoc execution)
#                                      │
#                                      │
#                       Anchor B': Custom Artisanal Craft
# ```
# 
# #### Rival Predictions & Probe
# 
# * **Prediction A (Myelinated Hand):** Productivity scales with human key-binding fluency; the bottleneck is context switching at the editor boundary.
# * **Prediction B (Industrial Gate):** Productivity scales with automated assertion checks; the bottleneck is uncaught specification drift in data structures.
# * **Discriminating Probe:** Measure execution time and error rate when running a client data extraction via hand-triggered CLI alias vs. a single-command airlocked script.
# 

# ```text
#   JAVA WORA (1995)                      NIX / FLAKE WORA (2026)
#   "Run Anywhere" Illusion               "Reproduce Everywhere" Reality
#  ┌─────────────────────────┐           ┌─────────────────────────┐
#  │  JVM Bytecode (.class)  │           │  Immutable Nix Store    │
#  └────────────┬────────────┘           └────────────┬────────────┘
#               │ (Hopes OS glibc matches)            │ (Pins glibc, C-libs, Driver)
#               ▼                                     ▼
#  ❌ "It works on my machine"           ✅ "It runs identically in 2036"
# ```

# ```text
#                     INDUSTRIAL (fixed stations, gates)
#                                  │
#      CNC shop; the AST airlock;  │   \m dropping the saddle; ahc;
#      nixos-rebuild; the recipe   │   the line worker's hands after
#      IS the authority            │   ten thousand reps
#                                  │
# INSCRIBED ───────────────────────┼─────────────────────── REFLEXIVE
# (knowledge in the artifact)      │        (knowledge in the body)
#                                  │
#      the monk copying a          │   jazz improv; the card fan at
#      manuscript once, carefully  │   the Magic Store on a Wednesday
#                                  │   night in Philadelphia
#                                  │
#                     ARTISANAL (one-off, judgment-led)
# ```

