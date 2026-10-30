#!/usr/bin/env python3
"""
Sonar V2.5: The Dual-Minded HUD.
Tracks both Javascript Execution (Rendering) and Semantic Reading (Source).
"""

import sys
import re
import hashlib
from datetime import datetime
from collections import Counter
import os 
import time

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Static, Log, RichLog, Label, Markdown, DataTable
from textual import work
from rich.text import Text
from rich.console import Console

from db import db, KNOWN_BOTS  # Import the list

# --- Configuration ---
STRIP_MOZILLA_PREFIX = False  # Set to True to save space in bottom panels
HUD_TABLE_ROWS = 12           # Visible data rows in both bottom HUD tables (freed 3 rows for 5-row #ticker_bar)
HUD_PANEL_HEIGHT = HUD_TABLE_ROWS + 4  # +4 rows for top border, panel title, header rule, and column headers
BOT_IDENTITY_WIDTH = 21       # Emoji (2) + space (1) + 18-char bot name (trims 15 chars for Raw Signature)
TICKER_FILE_PATH = "/tmp/honeybot_ticker.txt"
CARD_HOLD_TICKS = 56  # 56 * 0.08s = ~4.5s still hold per card (0% CPU during hold)
CARD_STYLES = ("bold #ffd700", "bold #00ffff", "bold #ffae42")
DEFAULT_TICKER_MESSAGE = (
    "JUST GIVE 30 SECS | "
    "YOU'LL SEE MAX ME! | "
    "VISIT SUNPUG.IO | "
    "CHAT SUMMONS MIKE! | "
    "AI LOGS * MIKELEV.IN"
)

# 5-Row Full-Block (█) LED Matrix Font (6-col round bowls + 7-col M/W wide basis strokes)
LED_FONT_3X3 = {
    "A": (" ████ ", "█    █", "██████", "█    █", "█    █"),
    "B": ("█████ ", "█    █", "█████ ", "█    █", "█████ "),
    "C": (" █████", "█     ", "█     ", "█     ", " █████"),
    "D": ("█████ ", "█    █", "█    █", "█    █", "█████ "),
    "E": ("██████", "█     ", "█████ ", "█     ", "██████"),
    "F": ("██████", "█     ", "█████ ", "█     ", "█     "),
    "G": (" █████", "█     ", "█  ███", "█    █", " ████ "),
    "H": ("█    █", "█    █", "██████", "█    █", "█    █"),
    "I": ("███", " █ ", " █ ", " █ ", "███"),
    "J": (" █████", "     █", "     █", "█    █", " ████ "),
    "K": ("█    █", "█  ██ ", "███   ", "█  ██ ", "█    █"),
    "L": ("█     ", "█     ", "█     ", "█     ", "██████"),
    "M": ("█     █", "██   ██", "█ █ █ █", "█  █  █", "█     █"),
    "N": ("█    █", "██   █", "█ █  █", "█  █ █", "█   ██"),
    "O": (" ████ ", "█    █", "█    █", "█    █", " ████ "),
    "P": ("█████ ", "█    █", "█████ ", "█     ", "█     "),
    "Q": (" ████ ", "█    █", "█    █", "█  █ █", " █████"),
    "R": ("█████ ", "█    █", "█████ ", "█   █ ", "█    █"),
    "S": (" █████", "█     ", " ████ ", "     █", "█████ "),
    "T": ("█████", "  █  ", "  █  ", "  █  ", "  █  "),
    "U": ("█    █", "█    █", "█    █", "█    █", " ████ "),
    "V": ("█   █", "█   █", "█   █", " █ █ ", "  █  "),
    "W": ("█     █", "█  █  █", "█ █ █ █", "██   ██", "█     █"),
    "X": ("█   █", " █ █ ", "  █  ", " █ █ ", "█   █"),
    "Y": ("█   █", " █ █ ", "  █  ", "  █  ", "  █  "),
    "Z": ("██████", "    █ ", "  ██  ", " █    ", "██████"),
    "0": (" ████ ", "█    █", "█    █", "█    █", " ████ "),
    "1": (" █ ", "██ ", " █ ", " █ ", "███"),
    "2": ("█████ ", "     █", " ████ ", "█     ", "██████"),
    "3": ("█████ ", "     █", " ████ ", "     █", "█████ "),
    "4": ("█    █", "█    █", "██████", "     █", "     █"),
    "5": ("██████", "█     ", "█████ ", "     █", "█████ "),
    "6": (" █████", "█     ", "█████ ", "█    █", " ████ "),
    "7": ("██████", "     █", "   ██ ", "  █   ", "  █   "),
    "8": (" ████ ", "█    █", " ████ ", "█    █", " ████ "),
    "9": (" ████ ", "█    █", " █████", "     █", "█████ "),
    " ": ("   ", "   ", "   ", "   ", "   "),
    "!": ("█", "█", "█", " ", "█"),
    "?": (" ████ ", "█    █", "   ██ ", "      ", "  █   "),
    ".": (" ", " ", " ", " ", "█"),
    ",": ("  ", "  ", "  ", " █", "█ "),
    "-": ("    ", "    ", "████", "    ", "    "),
    "+": ("     ", "  █  ", "█████", "  █  ", "     "),
    ":": (" ", "█", " ", "█", " "),
    "/": ("    █", "   █ ", "  █  ", " █   ", "█    "),
    "*": ("     ", " █ █ ", "  █  ", " █ █ ", "     "),
    "'": ("█", "█", " ", " ", " "),
    '"': ("█ █", "█ █", "   ", "   ", "   "),
    "$": (" █████", "█  █  ", " ████ ", "  █  █", "█████ "),
    "%": ("██   █", "    █ ", "  ██  ", " █    ", "█   ██"),
    "&": (" ███  ", "█   █ ", " ███  ", "█   █ ", " ███ █"),
    "(": ("  █", " █ ", " █ ", " █ ", "  █"),
    ")": ("█  ", " █ ", " █ ", " █ ", "█  "),
    "@": (" ████ ", "█    █", "█ ██ █", "█ ███ ", " ████ "),
    "#": (" █  █ ", "██████", " █  █ ", "██████", " █  █ "),
    "=": ("    ", "████", "    ", "████", "    "),
}


def render_led_3x3(text: str):
    """Render an uppercase string into five equal-length rows of 5-row full-block (█) glyphs."""
    clean = (text or "").upper()
    rows = [[], [], [], [], []]
    fallback = ("   ", "   ", "   ", "   ", "   ")
    for ch in clean:
        glyph = LED_FONT_3X3.get(ch, fallback)
        for i in range(5):
            rows[i].append(glyph[i] + " ")
    return tuple("".join(r) for r in rows)


def _led_rendered_width(text: str) -> int:
    """Return the exact rendered column width of text in the 5-row LED font."""
    if not text:
        return 0
    return max(0, len(render_led_3x3(text)[0]) - 1)


def _split_into_fitting_cards(raw_text: str, max_width_cols: int):
    """Split '|' delimited text into uppercase cards whose rendered LED width fits within max_width_cols."""
    avail_cols = max(48, int(max_width_cols))
    segments = [seg.strip() for seg in re.split(r"\|", raw_text or "") if seg.strip()]
    if len(segments) == 1 and " * " in segments[0] and _led_rendered_width(segments[0]) > avail_cols:
        segments = [seg.strip() for seg in segments[0].split(" * ") if seg.strip()]
    cards = []
    for seg in segments:
        words = seg.upper().split()
        cur = ""
        for w in words:
            if not cur:
                cur = w
            elif _led_rendered_width(f"{cur} {w}") <= avail_cols:
                cur = f"{cur} {w}"
            else:
                cards.append(cur)
                cur = w
        if cur:
            cards.append(cur)
    return cards or ["VISIT SUNPUG.IO"]


def _center_led_rows(card_str: str, width: int):
    """Render card_str in 5-row LED blocks and center-pad each row to exact terminal width."""
    raw_rows = [r[:-1] if r.endswith(" ") else r for r in render_led_3x3(card_str)]
    glyph_w = len(raw_rows[0]) if raw_rows else 0
    if glyph_w >= width:
        return tuple(r[:width] for r in raw_rows)
    left_pad = " " * ((width - glyph_w) // 2)
    right_pad = " " * (width - glyph_w - len(left_pad))
    return tuple(left_pad + r + right_pad for r in raw_rows)

# A hidden console to render styles into ANSI codes for the Log widget
# We set a massive width to prevent the console from hard-wrapping the text before the Log widget gets it
OFFSCREEN_CONSOLE = Console(force_terminal=True, color_system="truecolor", file=open(os.devnull, "w"), width=100000)

BOT_STYLE = "bold orange1"             # 🟠 Self-asserted Bot / Agent UA
VERIFIED_STYLE = "bold deep_sky_blue1" # 🔷 RFC 9421 / Web Bot Auth Verified Agent
SPOOF_STYLE = "bold red"               # 🛑 Cloaked / IP-spoofed Bot Identity
SPOOF_PREFIX = "[SPOOFED-IP] "
VERIFIED_PREFIX = "[VERIFIED] "
GOOGLE_IP_PREFIXES = (
    "66.249.", "64.233.", "72.14.", "74.125.", "108.177.",
    "142.250.", "142.251.", "172.217.", "173.194.", "192.178.",
    "207.126.", "209.85.", "216.58.", "216.239.",
)
_COMPAT_BOT_RE = re.compile(r"compatible;\s*([A-Za-z0-9._-]+)", re.IGNORECASE)
_KEYWORD_BOT_RE = re.compile(
    r"\b([A-Za-z0-9._-]*(?:bot|spider|crawler|agent|radar|worker|mcp|research|scraper|fetcher|inspector|archiver|httpx|requests|axios|curl|wget|aiohttp|urllib|go-http-client|python)[A-Za-z0-9._-]*)",
    re.IGNORECASE,
)
_LEADING_AGENT_RE = re.compile(r"^([A-Za-z0-9._-]+?)(?:/[\d.]+|\s+\(|\s*$)")
_ROLLUP_PREFIX_RE = re.compile(r"^\[(\+\d+)\]\s*")

try:
    from db import db  # Import our new database singleton
except ImportError:
    db = None

# --- Configuration ---
ANSI_ESCAPE = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
# Updated to optionally capture the new custom fields at the end of the line
LOG_PATTERN = re.compile(
    r'(?P<ip>[\d\.]+) - - \[(?P<time>.*?)\] "(?P<request>.*?)" (?P<status>\d+) (?P<bytes>\d+) '
    r'"(?P<referrer>.*?)" "(?P<ua>.*?)"(?: Accept:"(?P<accept>.*?)" MarkdownServed:(?P<md>\d))?'
    r'(?: Host:"(?P<host>.*?)")?(?: Sig:"(?P<sig>.*?)")?'
)

class SonarApp(App):
    """The Cybernetic HUD (Dual-Panel Edition)."""

    CSS = """
    Screen {
        layout: vertical;
        background: #0f1f27;
    }

    /* TOP SECTION: Full Width Log Stream (auto-fills height above HUD) */
    #log_stream {
        height: 1fr;
        background: #000000;
        color: #00ff00;
        overflow-y: auto;   /* <-- RESTORES VERTICAL SCROLL & AUTO-SCROLLING */
        overflow-x: hidden; /* <-- KEEPS THE BOTTOM FLUSH */
        width: 100%;
        min-width: 100%;
    }

    /* MIDDLE SECTION: Eye-Level Giant 5-Row LED Marquee Ticker (borderless, 100% signage) */
    #ticker_bar {
        height: 5;
        width: 100%;
        background: #140826;
        color: #ffd700;
        text-style: bold;
        padding: 0 1;
        overflow: hidden;
    }

    /* BOTTOM SECTION: The Intelligence Panel (sized in unison by HUD_TABLE_ROWS) */
    #intelligence_panel {
        height: __HUD_PANEL_HEIGHT__;
        border-top: solid cyan;
        background: #051515;
        padding: 0;
        layout: horizontal; /* Split Left/Right */
        overflow: hidden;
    }
    
    .half_panel {
        width: 50%;
        height: 100%;
        border-right: solid #004400;
    }

    .panel_header {
        text-align: center;
        background: #002200;
        color: #00ff00;
        text-style: bold;
        border-bottom: solid green;
        width: 100%;
    }

    DataTable {
        height: 1fr;
        width: 100%;
        overflow: hidden;
    }
    
    /* Countdown moves to the footer area style override if needed, 
       but standard Footer widget handles it well. */
    """.replace("__HUD_PANEL_HEIGHT__", str(HUD_PANEL_HEIGHT))

    TITLE = "Web Bot AI Observatory — https://mikelev.in (RFC 9110 · RFC 9421 · JS Trapdoor)"

    # --- NEW: Banish the interactive Command Palette ---
    ENABLE_COMMAND_PALETTE = False
    
    def get_sub_title(self):
        return f"Live Nginx Log Analysis | Next Report: {self.countdown_str}"

    def compose(self) -> ComposeResult:
        yield Header()
        # RichLog handles wrapping and styling natively. 
        # wrap=True ensures lines don't get cut off.
        yield RichLog(id="log_stream", highlight=False, wrap=True)
        yield Static("", id="ticker_bar")
        
        # --- NEW: The Dual Intelligence Panel ---
        with Container(id="intelligence_panel"):
            
            # LEFT: Javascript Executors
            with Vertical(classes="half_panel"):
                yield Label("⚡ DOM HYDRATION TRAPDOOR (Bots Executing JS)", classes="panel_header")
                yield DataTable(id="js_table")
            
            # RIGHT: Markdown Seekers
            with Vertical(classes="half_panel"):
                yield Label("🧠 RFC 9110 MARKDOWN NEGOTIATORS (Accept: text/markdown)", classes="panel_header")
                yield DataTable(id="md_table")
        # ----------------------------------------
            
        # yield Footer()

    def on_mount(self) -> None:
        self.ua_counter = Counter()
        self.countdown_str = "--:--"
        self.spoof_flip = False
        self.verified_tokens = {"ExaSearchBot", "AhrefsBot", "DesearchBot"}
        self.stream_logs()
        
        # Setup Tables (Now with 3 columns!)
        js_table = self.query_one("#js_table", DataTable)
        js_table.add_column("Hits")
        js_table.add_column("Bot Identity", width=BOT_IDENTITY_WIDTH)
        js_table.add_column("Raw Signature")
        
        md_table = self.query_one("#md_table", DataTable)
        md_table.add_column("Hits")
        md_table.add_column("Bot Identity", width=BOT_IDENTITY_WIDTH)
        md_table.add_column("Raw Signature")

        self.refresh_tables() # Initial load

        # Timers
        try:
            self.start_time = float(os.environ.get("SONAR_START_TIME", time.time()))
            self.duration_mins = float(os.environ.get("SONAR_DURATION", 15))
        except:
            self.start_time = time.time()
            self.duration_mins = 15
            
        self.ticker_offset = 0
        self.ticker_mtime = None
        self.ticker_tick_count = 0
        self.ticker_mode = "billboard"  # "billboard" (default still+flip) | "scroll" | "small"
        self.ticker_raw_text = ""
        self.ticker_led_rows = ("", "", "", "", "")
        self.ticker_cards = []
        self.ticker_card_idx = 0
        self.ticker_hold_ticks = 0
        self.ticker_flip_step = 0
        self.ticker_cached_width = 0
        self.ticker_last_mono = time.monotonic()
        self.ticker_recent_dts = []
        self._reload_ticker_source(force=True)
        self.set_interval(0.08, self.tick_marquee)
        self.set_interval(1, self.update_countdown)
        self.set_interval(5, self.refresh_tables)

    def _rebuild_billboard_cache(self, width: int):
        """Pre-render double-buffered 5-row Rich.Text still cards and 2-step vertical split-flap frames."""
        self.ticker_cached_width = width
        card_strings = _split_into_fitting_cards(self.ticker_raw_text, width)
        raw_rows = [_center_led_rows(cs, width) for cs in card_strings]
        total = len(card_strings)
        built = []
        for idx, cs in enumerate(card_strings):
            c_r0, c_r1, c_r2, c_r3, c_r4 = raw_rows[idx]
            nxt_idx = (idx + 1) % total
            n_r0, n_r1, n_r2, n_r3, n_r4 = raw_rows[nxt_idx]
            style_cur = CARD_STYLES[idx % len(CARD_STYLES)]
            style_nxt = CARD_STYLES[nxt_idx % len(CARD_STYLES)]
            still_txt = Text(f"{c_r0}\n{c_r1}\n{c_r2}\n{c_r3}\n{c_r4}", style=style_cur)
            # Frame 1 of 5-row split-flap roll (stride 2): old rows 2-4 shift up, blank gap, new row 0 enters
            flip_1 = Text.assemble(
                (c_r2 + "\n", style_cur),
                (c_r3 + "\n", style_cur),
                (c_r4 + "\n", style_cur),
                (" " * width + "\n", style_cur),
                (n_r0, style_nxt),
            )
            # Frame 2 of 5-row split-flap roll (stride 4): old row 4 at top, blank gap, new rows 0-2 rise
            flip_2 = Text.assemble(
                (c_r4 + "\n", style_cur),
                (" " * width + "\n", style_cur),
                (n_r0 + "\n", style_nxt),
                (n_r1 + "\n", style_nxt),
                (n_r2, style_nxt),
            )
            built.append({
                "text": cs,
                "still": still_txt,
                "flip_1": flip_1,
                "flip_2": flip_2,
            })
        self.ticker_cards = built
        self.ticker_card_idx = 0
        self.ticker_hold_ticks = 0
        self.ticker_flip_step = 0
        try:
            bar = self.query_one("#ticker_bar", Static)
            if built:
                bar.update(built[0]["still"])
        except Exception:
            pass

    def _is_window_clear_for_smooth_flip(self) -> bool:
        """True when recent event-loop ticks had low jitter (<115ms) and no active Piper synthesis lock."""
        if len(self.ticker_recent_dts) >= 4 and max(self.ticker_recent_dts[-6:]) > 0.115:
            return False
        return True

    def _reload_ticker_source(self, force=False):
        """Check /tmp/honeybot_ticker.txt mtime and rebuild the double-buffered LED frames only when changed."""
        try:
            st_mtime = os.stat(TICKER_FILE_PATH).st_mtime if os.path.exists(TICKER_FILE_PATH) else -1.0
        except OSError:
            st_mtime = -1.0
        if not force and st_mtime == self.ticker_mtime:
            return
        self.ticker_mtime = st_mtime
        raw = ""
        if st_mtime > 0:
            try:
                with open(TICKER_FILE_PATH, "r", encoding="utf-8", errors="replace") as tf:
                    lines = [ln.strip() for ln in tf.read().splitlines() if ln.strip()]
                raw = " | ".join(lines)
            except OSError:
                raw = ""
        if not raw:
            raw = DEFAULT_TICKER_MESSAGE
        mode = "billboard"
        up = raw.upper()
        if up.startswith(("SMALL:", "1ROW:")):
            mode = "small"
            raw = raw.split(":", 1)[1].strip() or DEFAULT_TICKER_MESSAGE
        elif up.startswith(("SCROLL:", "MARQUEE:")):
            mode = "scroll"
            raw = raw.split(":", 1)[1].strip() or DEFAULT_TICKER_MESSAGE
        elif up.startswith(("BILLBOARD:", "CARDS:", "BIG:", "STILL:")):
            mode = "billboard"
            raw = raw.split(":", 1)[1].strip() or DEFAULT_TICKER_MESSAGE
        self.ticker_mode = mode
        if mode in ("scroll", "small"):
            scroll_raw = raw.replace(" | ", " * ")
            if not scroll_raw.endswith("* "):
                scroll_raw = scroll_raw.rstrip() + " * "
            self.ticker_raw_text = scroll_raw
            self.ticker_led_rows = render_led_3x3(scroll_raw)
            try:
                bar = self.query_one("#ticker_bar", Static)
                preview = scroll_raw.replace(" * ", " · ").strip(" ·")
                if len(preview) > 110:
                    preview = preview[:107] + "..."
                bar.border_title = f"📡 LIVE SIDE-BAND TICKER — {preview}"
            except Exception:
                pass
        else:
            self.ticker_raw_text = raw
            try:
                bar = self.query_one("#ticker_bar", Static)
                width = max(40, (bar.size.width or 160) - 2)
            except Exception:
                width = 160
            self._rebuild_billboard_cache(width)

    def tick_marquee(self):
        """Drive #ticker_bar: 0% CPU during 4.5s still-card hold, with idle-gated 2-frame split-flap flip."""
        now_mono = time.monotonic()
        dt = now_mono - self.ticker_last_mono
        self.ticker_last_mono = now_mono
        self.ticker_recent_dts.append(dt)
        if len(self.ticker_recent_dts) > 12:
            self.ticker_recent_dts.pop(0)

        self.ticker_tick_count += 1
        if self.ticker_tick_count % 10 == 0:
            self._reload_ticker_source(force=False)
        try:
            bar = self.query_one("#ticker_bar", Static)
            width = max(40, (bar.size.width or 160) - 2)
        except Exception:
            return

        if self.ticker_mode == "billboard":
            if width != self.ticker_cached_width or not self.ticker_cards:
                self._rebuild_billboard_cache(width)
            cards = self.ticker_cards
            if not cards or len(cards) == 1:
                return
            cur_card = cards[self.ticker_card_idx % len(cards)]
            if self.ticker_flip_step == 0:
                self.ticker_hold_ticks += 1
                if self.ticker_hold_ticks < CARD_HOLD_TICKS:
                    return  # 0% CPU still-frame hold
                self.ticker_hold_ticks = 0
                if self._is_window_clear_for_smooth_flip():
                    self.ticker_flip_step = 1
                    bar.update(cur_card["flip_1"])
                else:
                    self.ticker_card_idx = (self.ticker_card_idx + 1) % len(cards)
                    nxt_card = cards[self.ticker_card_idx]
                    bar.update(nxt_card["still"])
            elif self.ticker_flip_step == 1:
                self.ticker_flip_step = 2
                bar.update(cur_card["flip_2"])
            else:
                self.ticker_flip_step = 0
                self.ticker_card_idx = (self.ticker_card_idx + 1) % len(cards)
                nxt_card = cards[self.ticker_card_idx]
                bar.update(nxt_card["still"])
            return

        if self.ticker_mode == "small":
            base = self.ticker_raw_text or DEFAULT_TICKER_MESSAGE
            n = max(1, len(base))
            off = self.ticker_offset % n
            repeats = (width // n) + 3
            doubled = base * repeats
            win = doubled[off : off + width]
            bar.update(Text("\n\n" + win + "\n\n", style="bold bright_yellow"))
            self.ticker_offset = (off + 1) % n
            return

        r0, r1, r2, r3, r4 = self.ticker_led_rows
        if not r0:
            return
        n = len(r0)
        off = self.ticker_offset % n
        repeats = (width // n) + 3
        w0 = (r0 * repeats)[off : off + width]
        w1 = (r1 * repeats)[off : off + width]
        w2 = (r2 * repeats)[off : off + width]
        w3 = (r3 * repeats)[off : off + width]
        w4 = (r4 * repeats)[off : off + width]
        bar.update(Text(f"{w0}\n{w1}\n{w2}\n{w3}\n{w4}", style="bold #ffd700"))
        self.ticker_offset = (off + 1) % n

    def is_spoofed_bot(self, ip_str, ua_str):
        """True when a request claims Googlebot from outside Google's crawler IP blocks."""
        return "Googlebot" in (ua_str or "") and not str(ip_str or "").startswith(GOOGLE_IP_PREFIXES)

    def clean_sig_agent(self, sig_str):
        """Unescape Nginx \\x22 quotes from RFC 9421 Signature-Agent header values."""
        s = (sig_str or "").replace(r"\x22", '"').strip().strip('"').strip()
        return "" if s == "-" else s

    def is_verified_bot(self, sig_str):
        """True when RFC 9421 / IETF Web Bot Auth Signature-Agent header is present."""
        return bool(self.clean_sig_agent(sig_str))

    def detect_bot_token(self, ua_str):
        """Extract the self-identifying bot/agent token from a User-Agent string, or None for standard browsers."""
        s = (ua_str or "").strip()
        if not s or s == "-":
            return None
        for bot_name in sorted(KNOWN_BOTS, key=len, reverse=True):
            if bot_name in s:
                m_ext = re.search(rf"({re.escape(bot_name)}[A-Za-z0-9._-]*)", s)
                return m_ext.group(1).strip(";/() ") if m_ext else bot_name
        for m in _COMPAT_BOT_RE.finditer(s):
            tok = m.group(1).strip(";/() ")
            if tok and tok.upper() not in ("MSIE", "MOZILLA"):
                return tok
        if not s.startswith(("Mozilla/", "AppleWebKit/", "(")):
            m_lead = _LEADING_AGENT_RE.match(s)
            if m_lead:
                return m_lead.group(1).strip()
        m_kw = _KEYWORD_BOT_RE.search(s)
        if m_kw:
            tok = m_kw.group(1).strip(";/() ")
            if tok.lower() not in ("mozilla", "applewebkit", "safari", "chrome", "gecko", "khtml", "mobile"):
                return tok
        return None

    def stylize_agent(self, agent_str, is_spoof=False, is_verified=False, bot_token=None):
        """Converts a raw UA string into a Rich Text object with highlights."""
        agent_str = agent_str.strip()
        text = Text(agent_str)
        if ("Mozilla" in agent_str or "AppleWebKit" in agent_str) and "compatible" not in agent_str and not bot_token:
            text.stylize("dim white")
        hl_style = SPOOF_STYLE if is_spoof else (VERIFIED_STYLE if is_verified else BOT_STYLE)
        matched_any = False
        for bot_name in KNOWN_BOTS:
            if bot_name in agent_str:
                text.highlight_regex(re.escape(bot_name), hl_style)
                matched_any = True
        if not matched_any and bot_token and bot_token in agent_str:
            text.highlight_regex(re.escape(bot_token), hl_style)
        return text

    def extract_and_stylize(self, agent_str):
        """Returns a tuple: (Styled Identity with 🛑/🔷/🟠 shape badge, Styled Full String)"""
        raw = agent_str.strip()
        is_spoof = raw.startswith(SPOOF_PREFIX)
        if is_spoof:
            raw = raw[len(SPOOF_PREFIX):].strip()
        is_verified = raw.startswith(VERIFIED_PREFIX)
        if is_verified:
            raw = raw[len(VERIFIED_PREFIX):].strip()
        rollup_badge = ""
        m_rollup = _ROLLUP_PREFIX_RE.match(raw)
        if m_rollup:
            rollup_badge = m_rollup.group(1)
            raw = raw[m_rollup.end():].strip()
        bot_token = self.detect_bot_token(raw)
        clean_ua = raw.replace("Mozilla/5.0 ", "")
        if not is_spoof and not is_verified and bot_token in getattr(self, "verified_tokens", set()):
            is_verified = True
        short_bot = (bot_token or "")[:18]
        if is_spoof:
            label = "Cloaking" if getattr(self, "spoof_flip", False) else (short_bot or "Googlebot")
            identity = f"🛑 {label}"
            identity_style = SPOOF_STYLE
            sig_style = "red"
        elif is_verified:
            identity = f"🔷 {short_bot or 'Verified'}"
            identity_style = VERIFIED_STYLE
            sig_style = "deep_sky_blue1"
        elif short_bot:
            identity = f"🟠 {short_bot}"
            identity_style = BOT_STYLE
            sig_style = "dim green"
        else:
            identity = "👤 Browser/Other"
            identity_style = "dim white"
            sig_style = "dim white"
        body_text = Text(clean_ua, style=sig_style)
        hl_style = SPOOF_STYLE if is_spoof else (VERIFIED_STYLE if is_verified else BOT_STYLE)
        if bot_token and bot_token in clean_ua:
            body_text.highlight_regex(re.escape(bot_token), hl_style)
        if rollup_badge:
            sig_text = Text.assemble((f"{rollup_badge} ", "bold bright_yellow"), body_text)
        else:
            sig_text = body_text
        return Text(identity, style=identity_style), sig_text

    def _populate_hud_table(self, table, data):
        """Populate a HUD DataTable and size Bot Identity to its longest visible entry (+2-space buffer)."""
        table.clear(columns=True)
        if not data:
            table.add_columns("Hits", "Bot Identity", "Raw Signature")
            table.add_row("-", "None", "Waiting for data...")
            return
        styled_rows = []
        for ua, count in data:
            display_ua = ua.replace("Mozilla/5.0 ", "") if STRIP_MOZILLA_PREFIX else ua
            identity, signature = self.extract_and_stylize(display_ua)
            styled_rows.append((str(count), identity, signature))
        id_width = min(
            BOT_IDENTITY_WIDTH,
            max(
                len("Bot Identity"),
                max((ident.cell_len for _, ident, _ in styled_rows), default=0),
            ),
        )
        table.add_column("Hits")
        table.add_column("Bot Identity", width=id_width)
        table.add_column("Raw Signature")
        for count_str, identity, signature in styled_rows:
            table.add_row(count_str, identity, signature)

    def refresh_tables(self):
        """Updates both Intelligence tables from DB."""
        if not db: return
        self.spoof_flip = not getattr(self, "spoof_flip", False)
        
        # 1. Update JS Executors (Left)
        try:
            table = self.query_one("#js_table", DataTable)
            data = db.get_js_executors(limit=HUD_TABLE_ROWS)
            self._populate_hud_table(table, data)
        except Exception as e:
            table.clear()
            table.add_row("ERROR", "None", str(e)[:40])

        # 2. Update Markdown Negotiators (Right - strict RFC 9110 Accept: text/markdown)
        try:
            table = self.query_one("#md_table", DataTable)
            data = db.get_content_neg_agents(limit=HUD_TABLE_ROWS)
            self._populate_hud_table(table, data)
        except Exception as e:
            table.clear()
            table.add_row("ERROR", "None", str(e)[:40])

    def update_countdown(self):
        """Ticks the clock and updates the Sub-Title."""
        elapsed = time.time() - self.start_time
        total_seconds = self.duration_mins * 60
        remaining = total_seconds - elapsed
        
        if remaining < 0: remaining = 0
        mins, secs = divmod(int(remaining), 60)
        
        self.countdown_str = f"{mins:02d}:{secs:02d}"
        self.sub_title = self.get_sub_title() # Trigger header update

    # -------------------------------------------------------------------------
    # Core Logic: IP Anonymization & Stream Parsing
    # -------------------------------------------------------------------------
    def anonymize_ip(self, ip_str):
        try:
            parts = ip_str.split('.')
            if len(parts) == 4:
                masked = f"{parts[0]}.{parts[1]}.*.*"
                salt = datetime.now().strftime("%Y-%m-%d")
                hash_input = f"{ip_str}-{salt}"
                hash_digest = hashlib.md5(hash_input.encode()).hexdigest()[:4]
                return Text.assemble((masked, "cyan"), " ", (f"[{hash_digest}]", "bold cyan"))
            return Text(ip_str, style="red")
        except:
            return Text(ip_str, style="red")

    def parse_request(self, request_str):
        try:
            parts = request_str.split()
            if len(parts) >= 2:
                return parts[0], parts[1]
            return "???", request_str
        except:
            return "???", request_str

    def format_host_domain(self, raw_host):
        """Normalize Nginx $host into the registered domain name without leaking raw IP headers."""
        h = (raw_host or "").strip().lower().split(":", 1)[0].rstrip(".")
        if h.startswith("www."):
            h = h[4:]
        if not h or h == "-" or h == "localhost" or h.endswith(".local"):
            return "mikelev.in"
        if re.match(r"^\d+(\.\d+)+$", h) or ":" in h:
            return "mikelev.in"
        for known in (
            "mikelev.in", "qamy.ai", "npvg.org", "sunpug.io",
            "levinix.org", "levinix.com", "levinux.com",
            "pipulate.com", "guerillatech.com", "rfc9110.org", "rfc9111.io", "rfc9111.com",
        ):
            if h == known or h.endswith("." + known):
                return known
        if "qamy" in h:
            return "qamy.ai"
        if "npvg" in h:
            return "npvg.org"
        if "sunpug" in h:
            return "sunpug.io"
        if "levinix" in h:
            return "levinix.org"
        if "levinux" in h:
            return "levinux.com"
        if re.match(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$", h):
            return h
        return "mikelev.in"

    @work(thread=True)
    def stream_logs(self) -> None:
        hits = 0
        for line in sys.stdin:
            clean_line = ANSI_ESCAPE.sub('', line).strip()
            if not clean_line or " - - [" not in clean_line: continue

            match = LOG_PATTERN.search(clean_line)
            if match:
                data = match.groupdict()
                if "porn" in data['request'].lower(): continue

                hits += 1

                # Persist to DB
                if db:
                    try:
                        # Extract path and strip query strings to prevent DB bloat
                        raw_path = data['request'].split()[1] if len(data['request'].split()) > 1 else data['request']
                        
                        # SELECTIVE QUERY STRING PRESERVATION
                        # We keep the ?src= tracking dyes (including social campaign referrals) for attribution
                        if '?' in raw_path:
                            base_path, qs = raw_path.split('?', 1)
                            if qs in (
                                'src=a+href', 'src=llms.txt', 'src=link+rel',
                                'src=youtube', 'src=linkedin', 'src=x', 'src=twitter',
                            ):
                                clean_path = raw_path
                            else:
                                clean_path = base_path
                        else:
                            clean_path = raw_path

                        # THE PATH GOVERNOR (Dimension Hygiene)
                        # Vitals showed a 6,513-char probe URL embalmed forever in
                        # `paths`. Cap at ingest so hostile payloads can't mint
                        # bloated immortal dimension rows. 200 chars preserves all
                        # legitimate paths AND the <=150 window the 404-remap
                        # queries already filter on.
                        if len(clean_path) > 200:
                            clean_path = clean_path[:200]

                        # THE ALCHEMICAL NORMALIZATION (Purging Ambiguity)
                        # If Nginx served markdown via Content-Negotiation, explicitly tag it
                        if data.get('md') == '1':
                            if clean_path.endswith('/'):
                                clean_path += "index.md?src=content_neg"
                            elif 'src=' not in clean_path:
                                clean_path += "?src=content_neg"

                        clean_sig = self.clean_sig_agent(data.get('sig'))
                        db.log_request(
                            ip=data['ip'],
                            ua=data['ua'],
                            path=clean_path,
                            status=int(data['status']),
                            referrer=data.get('referrer'),
                            accept=data.get('accept'),
                            served_md=data.get('md'),
                            host=data.get('host') or 'mikelev.in',
                            sig_agent=clean_sig,
                        )
                        db.increment_counter("global_hits")
                        if '?' in clean_path and not str(data['ip']).startswith(('127.', '10.', '192.168.')):
                            _, qs_part = clean_path.split('?', 1)
                            if qs_part in ('src=youtube', 'src=linkedin', 'src=x', 'src=twitter'):
                                import json as _json
                                with open('/tmp/honeybot_referrals.jsonl', 'a', encoding='utf-8') as rf:
                                    rf.write(_json.dumps({
                                        'ts': int(time.time()),
                                        'src': qs_part,
                                        'path': clean_path,
                                    }) + '\n')
                    except: pass

                # Update Logs UI
                self.ua_counter[data['ua'].split('/')[0]] += 1
                rich_text = self.format_log_line(data)
                if hits > 1: rich_text = Text("\n") + rich_text
                self.call_from_thread(self.write_log, rich_text)

    def write_log(self, text):
        """Write the Rich Text object directly to the RichLog widget."""
        # Note: We query RichLog now, not Log
        log = self.query_one(RichLog)
        log.write(text)

    def format_log_line(self, data):
        status = int(data['status'])
        if 200 <= status < 300: status_style = "bold green"
        elif 300 <= status < 400: status_style = "bold white"
        elif 400 <= status < 500: status_style = "bold red"
        else: status_style = "white on red"

        ip_display = self.anonymize_ip(data['ip'])
        method, path = self.parse_request(data['request'])
        
        ua = data['ua']
        is_spoof = self.is_spoofed_bot(data.get('ip'), ua)
        is_verified = self.is_verified_bot(data.get('sig'))
        bot_token = self.detect_bot_token(ua)
        if is_verified and bot_token and hasattr(self, "verified_tokens"):
            self.verified_tokens.add(bot_token)
        ua_text = self.stylize_agent(ua, is_spoof=is_spoof, is_verified=is_verified, bot_token=bot_token)
        if is_spoof:
            prefix = "🛑 "
        elif is_verified:
            prefix = "🔷 "
        elif bot_token:
            prefix = "🟠 "
        else:
            prefix = "👤 "

        # Dynamic styling for the requested path
        path_style = "blue"
        if "js_confirm.gif" in path:
            prefix = "🪤 " + prefix
            path_style = "black on blue"

        text = Text()
        try:
            time_str = data['time'].split(':')[1:]
            time_str = ":".join(time_str).split(' ')[0]
            text.append(f"[{time_str}] ", style="dim")
        except: text.append("[TIME] ", style="dim")

        domain_label = self.format_host_domain(data.get('host'))
        text.append(f"[{domain_label}] ", style="bold bright_white")

        text.append(ip_display)
        text.append("  ") # Just space
        if data.get('md') == '1':
            text.append("[RFC9110:MD] ", style="bold black on green")
        for ref_tag, ref_label in (("src=youtube", "YOUTUBE"), ("src=linkedin", "LINKEDIN"), ("src=x", "X.COM"), ("src=twitter", "X.COM")):
            if ref_tag in path:
                text.append(f"[REF:{ref_label}] ", style="bold white on magenta")
                break
        text.append(f"{method:4} ", style="bold")
        text.append(f"{path} ", style=path_style)
        text.append(f"[{status}] ", style=status_style)
        text.append("  ") # Just space
        
        # 3. Append the prefix
        text.append(prefix)
        
        # 4. Append the already-styled UA text
        text.append(ua_text)
        
        return text


if __name__ == "__main__":
    app = SonarApp()
    app.run()
