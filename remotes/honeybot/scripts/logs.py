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
HUD_TABLE_ROWS = 15           # Visible data rows in both bottom HUD tables (tuned from 17 to 15)
HUD_PANEL_HEIGHT = HUD_TABLE_ROWS + 4  # +4 rows for top border, panel title, header rule, and column headers
BOT_IDENTITY_WIDTH = 21       # Emoji (2) + space (1) + 18-char bot name (trims 15 chars for Raw Signature)

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
            
        self.set_interval(1, self.update_countdown)
        self.set_interval(5, self.refresh_tables)

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

    def refresh_tables(self):
        """Updates both Intelligence tables from DB."""
        if not db: return
        self.spoof_flip = not getattr(self, "spoof_flip", False)
        
        # 1. Update JS Executors (Left)
        try:
            table = self.query_one("#js_table", DataTable)
            table.clear()
            data = db.get_js_executors(limit=HUD_TABLE_ROWS)
            if not data:
                table.add_row("-", "None", "Waiting for data...")
            else:
                for ua, count in data:
                    display_ua = ua.replace("Mozilla/5.0 ", "") if STRIP_MOZILLA_PREFIX else ua
                    identity, signature = self.extract_and_stylize(display_ua)
                    table.add_row(str(count), identity, signature)
        except Exception as e:
            table.clear()
            table.add_row("ERROR", "None", str(e)[:40])

        # 2. Update Markdown Negotiators (Right - strict RFC 9110 Accept: text/markdown)
        try:
            table = self.query_one("#md_table", DataTable)
            table.clear()
            data = db.get_content_neg_agents(limit=HUD_TABLE_ROWS)
            if not data:
                table.add_row("-", "None", "Waiting for data...")
            else:
                for ua, count in data:
                    display_ua = ua.replace("Mozilla/5.0 ", "") if STRIP_MOZILLA_PREFIX else ua
                    identity, signature = self.extract_and_stylize(display_ua)
                    table.add_row(str(count), identity, signature)
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
