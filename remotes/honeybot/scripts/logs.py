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
from textual.widgets import Header, Footer, Static, Log, Label, Markdown, DataTable
from textual import work
from rich.text import Text

try:
    from db import db  # Import our new database singleton
except ImportError:
    db = None

# --- Configuration ---
ANSI_ESCAPE = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
LOG_PATTERN = re.compile(r'(?P<ip>[\d\.]+) - - \[(?P<time>.*?)\] "(?P<request>.*?)" (?P<status>\d+) (?P<bytes>\d+) "(?P<referrer>.*?)" "(?P<ua>.*?)"')

class SonarApp(App):
    """The Cybernetic HUD (Dual-Panel Edition)."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1 6; 
        background: #0f1f27;
    }

    /* TOP SECTION: Full Width Log Stream (Rows 1-4) */
    #log_stream {
        row-span: 4;
        background: #000000;
        border: solid #00ff00;
        color: #00ff00;
        height: 100%;
        scrollbar-gutter: stable;
        overflow-y: scroll;
    }

    /* BOTTOM SECTION: The Intelligence Panel (Rows 5-6) */
    #intelligence_panel {
        row-span: 2;
        border-top: solid cyan;
        background: #051515;
        padding: 0;
        layout: horizontal; /* Split Left/Right */
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
    }
    
    /* Countdown moves to the footer area style override if needed, 
       but standard Footer widget handles it well. */
    """

    TITLE = "Honeybot Sonar"
    
    def get_sub_title(self):
        return f"Live Nginx Log Analysis | Next Report: {self.countdown_str}"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Log(id="log_stream", highlight=True)
        
        # --- NEW: The Dual Intelligence Panel ---
        with Container(id="intelligence_panel"):
            
            # LEFT: Javascript Executors
            with Vertical(classes="half_panel"):
                yield Label("⚡ JAVASCRIPT EXECUTORS (Renderers)", classes="panel_header")
                yield DataTable(id="js_table")
            
            # RIGHT: Markdown Seekers
            with Vertical(classes="half_panel"):
                yield Label("🧠 SEMANTIC READERS (Source Seekers)", classes="panel_header")
                yield DataTable(id="md_table")
        # ----------------------------------------
            
        yield Footer()

    def on_mount(self) -> None:
        self.ua_counter = Counter()
        self.countdown_str = "--:--"
        self.stream_logs()
        
        # Setup Tables
        js_table = self.query_one("#js_table", DataTable)
        js_table.add_columns("Hits", "Agent")
        
        md_table = self.query_one("#md_table", DataTable)
        md_table.add_columns("Hits", "Agent")

        self.refresh_tables() # Initial load

        # Timers
        try:
            self.start_time = float(os.environ.get("SONAR_START_TIME", time.time()))
            self.duration_mins = float(os.environ.get("SONAR_DURATION", 15))
        except:
            self.start_time = time.time()
            self.duration_mins = 15
            
        self.set_interval(1, self.update_countdown)
        self.set_interval(5, self.refresh_tables) # Refresh data every 5s

    def refresh_tables(self):
        """Updates both Intelligence tables from DB."""
        if not db: return
        
        # 1. Update JS Executors (Left)
        try:
            table = self.query_one("#js_table", DataTable)
            table.clear()
            # Fetch plenty, let UI clip
            data = db.get_js_executors(limit=50) 
            if not data:
                table.add_row("-", "Waiting for data...")
            else:
                for ua, count in data:
                    table.add_row(str(count), ua.strip())
        except: pass

        # 2. Update Markdown Readers (Right)
        try:
            table = self.query_one("#md_table", DataTable)
            table.clear()
            # Fetch plenty, let UI clip
            data = db.get_markdown_readers(limit=50)
            if not data:
                table.add_row("-", "Waiting for data...")
            else:
                for ua, count in data:
                    table.add_row(str(count), ua.strip())
        except: pass

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
                return Text.assemble((masked, "cyan"), " ", (f"[{hash_digest}]", "bold magenta"))
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
                        db.log_request(
                            ip=data['ip'],
                            ua=data['ua'],
                            path=data['request'].split()[1] if len(data['request'].split()) > 1 else data['request'],
                            status=int(data['status'])
                        )
                        db.increment_counter("global_hits")
                    except: pass

                # Update Logs UI
                self.ua_counter[data['ua'].split('/')[0]] += 1
                rich_text = self.format_log_line(data)
                if hits > 1: rich_text = Text("\n") + rich_text
                self.call_from_thread(self.write_log, rich_text)

    def write_log(self, text):
        log = self.query_one(Log)
        if hasattr(text, "plain"): log.write(text.plain)
        else: log.write(str(text))

    def format_log_line(self, data):
        status = int(data['status'])
        if 200 <= status < 300: status_style = "bold green"
        elif 300 <= status < 400: status_style = "yellow"
        elif 400 <= status < 500: status_style = "bold red"
        else: status_style = "white on red"

        ip_display = self.anonymize_ip(data['ip'])
        method, path = self.parse_request(data['request'])
        
        ua = data['ua']
        ua_style = "dim white"
        prefix = ""
        if "Googlebot" in ua: prefix = "🤖 "; ua_style = "green"
        elif "GPTBot" in ua or "Claude" in ua: prefix = "🧠 "; ua_style = "bold purple"
        elif "Mozilla" in ua: prefix = "👤 "; ua_style = "bright_white"
        elif "python" in ua.lower(): prefix = "🔧 "; ua_style = "cyan"
        
        text = Text()
        try:
            time_str = data['time'].split(':')[1:]
            time_str = ":".join(time_str).split(' ')[0]
            text.append(f"[{time_str}] ", style="dim")
        except: text.append("[TIME] ", style="dim")
            
        text.append(ip_display)
        text.append(" | ", style="dim")
        text.append(f"{method:4} ", style="bold")
        text.append(f"{path} ", style="blue")
        text.append(f"[{status}] ", style=status_style)
        text.append(" | ", style="dim")
        text.append(f"{prefix}{ua}", style=ua_style)
        return text

if __name__ == "__main__":
    app = SonarApp()
    app.run()
