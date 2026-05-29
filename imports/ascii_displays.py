# ASCII Art and Visual Display Functions
# Externalized from server.py to reduce token count while preserving functionality
# IMPORTANT: These are EXACT transcriptions of the original ASCII art - not generated substitutes!

import logging

from pyfiglet import Figlet
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
    figurate_logger.info(f"🎨 FIGURATE_AI: {name}\n{ai_out}")
    
    # Also use the existing share function for full AI transparency
    share_ascii_with_ai(ai_out, f"figurate('{name}') called", "🎨")
    
    return FigurateResult(name=name, human=human_out, ai=ai_out, drift=drift)


def patronus(name: str, duration: float = 3.5) -> None:
    """🛡️ PATRONUS: Conjures an out-of-bounds visual popup window for the asset.
    
    Measures the targeted ASCII artwork bounds, opens a borderless, auto-sized
    Alacritty micro-terminal precisely padded to prevent line-wrapping, forces
    top-level window focus, and safely terminates after the specified timeline duration.
    """
    import shutil
    import platform
    import subprocess
    from pathlib import Path

    # Gracefully lookup asset data to derive layout geometry matrix boundaries
    entry = FIGURATE_REGISTRY.get(name)
    if entry is None:
        logger.error(f"🛡️ PATRONUS aborted: '{name}' is not a registered visual asset layer.")
        return

    _, ai_out = entry()
    raw_lines = ai_out.splitlines()
    
    # Calculate exact dynamic column width and row bounds
    max_width = max(len(line) for line in raw_lines) if raw_lines else 80
    total_rows = len(raw_lines) if raw_lines else 12
    
    # Inject exact safety padding constants for the Rich panel frame boundaries
    columns_needed = max_width + 12
    lines_needed = total_rows + 4

    # Resolve paths relative to framework root directory structures
    display_file_path = Path(__file__).resolve()
    repo_root = str(display_file_path.parents[1])
    sys_platform = platform.system().lower()

    # Isolated subshell inline execution payload script blueprint string
    python_payload = (
        f"import sys; sys.path.insert(0, '{repo_root}'); "
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
        "-e", f"{repo_root}/.venv/bin/python", "-u", "-c", python_payload
    ]

    try:
        logger.info(f"🛡️ Conjuring Patronus shield framework window overlay ({columns_needed}x{lines_needed}) for art asset: '{name}'")
        proc = subprocess.Popen(cmd, cwd=repo_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Settle delay for system display context registration mappings
        time.sleep(0.15)

        # Handle top-level window elevation maps uniquely per running host os environment
        if sys_platform == "linux" and shutil.which("wmctrl"):
            subprocess.run(["wmctrl", "-x", "-r", "patronus_visual_shield", "-b", "add,above"])
        elif sys_platform == "darwin":
            subprocess.run(["osascript", "-e", 'tell application "Alacritty" to activate'], stdout=subprocess.DEVNULL)

        # Retain execution thread lock until duration lifecycle expires cleanly
        proc.wait()
    except Exception as e:
        logger.error(f"🛡️ PATRONUS connection framework failure encountered: {e}")


# FIGURATE_COLOR_BITS: The color-bits player piano dictionary.
# Maps named tokens to Rich style strings.
# Usage in art strings: [[[TokenName]]] expands to styled text for humans,
# and strips to plain TokenName for AI context and CRC hashing.
FIGURATE_COLOR_BITS: dict = {
    "NPvg":     "bold bright_blue",
    "Pipulate": "bold bright_cyan",
}


def _expand_color_bits_human(text: str) -> str:
    """Expand [[[Token]]] markers into Rich markup for terminal display."""
    import re
    def replace(m):
        token = m.group(1)
        style = FIGURATE_COLOR_BITS.get(token, "")
        if style:
            return f"[{style}]{token}[/{style}]"
        return token  # Unknown token: pass through raw
    return re.sub(r'\[\[\[([^\]]+)\]\]\]', replace, text)


def _expand_color_bits_ai(text: str) -> str:
    """Strip [[[Token]]] markers to plain text for AI context and CRC hashing."""
    import re
    return re.sub(r'\[\[\[([^\]]+)\]\]\]', r'\1', text)


# FIGURATE_LEDGER: Maps art name → expected CRC32 of its raw ai string.
# This is the wax seal registry. A drift of 1 means something touched the painting.
# To add a new entry: print(binascii.crc32(your_art_string.encode('utf-8')))
# FIGURATE_LEDGER: Maps art name → expected CRC32 of its raw ai string.
# This is the wax seal registry. A drift of 1 means something touched the painting.
# To add a new entry: print(binascii.crc32(your_art_string.encode('utf-8')))
FIGURATE_LEDGER: dict = {
    "white_rabbit": 2735320865,
    "player_piano": 2962137920,
    "clipboard": 2324709982,
}

# FIGURATE_REGISTRY: The map of all visual vocabulary.
# Each entry provides a render() function returning (human, ai) tuple.
# Art goes here as a data asset; rendering logic stays separate from content.
# Populate incrementally — add entries as existing functions are migrated.
def _figurate_white_rabbit():
    """Render white_rabbit as (human, ai) tuple for FIGURATE_REGISTRY."""
    art = r"""
                        ( Like a canary you say? )                      
                                           O        /)  ____            The "No Problem" Framework
>  I HEREBY WILL NOT RE-GENERATE            o /)\__//  /    \        Pipulate - Protecting Your Code 
>  Once upon machines be smarten          ___(/_ 0 0  | [[[NPvg]]] |       just by being honest about text.
>  ASCII sealing immutata art in        *(    ==(_T_)== WORA |           < https://pipulate.com >
>  This here cony if it's broken          \  )   ""\  | free |                    🥕🥕🥕 
>  Smokin gun drift now in token           |__>-\_>_>  \____/ 
    """
    ai_art = _expand_color_bits_ai(art)
    human_art = _expand_color_bits_human(art)
    human = Panel(human_art, title="🐰 Welcome to Consoleland", border_style="white")
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
    logger.info(f"{emoji} AI_CREATIVE_VISION: {context_message}")
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
[dim white]Local First AI SEO Software[/dim white]

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
    fallback = f"""🍞 AI DISCOVERY COMPLETE

🧠 AI CAPABILITIES DISCOVERED:
✅ MCP Tools: {tool_count} programmatic tools ready
✅ Browser Eyes: Screenshot + DOM analysis
✅ Browser Hands: Selenium automation control  
✅ Session Hijack: Complete workflow capture
✅ Persistent Memory: Keychain across restarts
✅ Documentation: 14 comprehensive guides

Zero uncertainty • 100% automation success rate"""
    
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
✅ MCP Tools: {tool_count} programmatic tools ready
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
    fallback = f"""🍞 AI DISCOVERY COMPLETE

🧠 AI CAPABILITIES DISCOVERED:
✅ MCP Tools: {tool_count} programmatic tools ready
✅ Browser Eyes: Screenshot + DOM analysis
✅ Browser Hands: Selenium automation control  
✅ Session Hijack: Complete workflow capture
✅ Persistent Memory: Keychain across restarts
✅ Documentation: 14 comprehensive guides

Zero uncertainty • 100% automation success rate"""
    
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
    fallback = """🚨 AI ASSISTANT GUIDELINES

⚠️ ESSENTIAL KNOWLEDGE FOR 100% SUCCESS RATE:
• Python Path Issue: NEVER use 'python' - ALWAYS use '.venv/bin/python'
• Golden Path: cd pipulate && .venv/bin/python cli.py call <tool_name> works everywhere
• Working Directory: MCP tools require 'cd pipulate' first - never run from workspace root
• Browser Evidence: Check browser_cache/looking_at/ FIRST, system internals second

Essential knowledge for 100% success rate"""
    
    return safe_console_capture(console, panel, fallback)
