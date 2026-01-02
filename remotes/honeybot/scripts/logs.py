#!/usr/bin/env python3
"""
Sonar V2: Stable Core Edition.
Based on the rock-solid aquarium.py log widget, enhanced with IP hashing.
"""

import sys
import re
import hashlib
from datetime import datetime
from collections import Counter
import os 
import time

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
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
    """The Cybernetic HUD (Stable Edition)."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1 6; /* CHANGED: 1 column layout */
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
        border: solid cyan;
        background: #051515;
        padding: 0 1;
    }
    
    #panel_header {
        text-align: center;
        background: #002200;
        color: #00ff00;
        text-style: bold;
        border-bottom: solid green;
    }

    DataTable {
        height: 1fr;
        width: 100%;
    }
    
    #countdown_label {
        color: orange;
        text-style: bold;
        dock: right;
    }
    """

    TITLE = "Honeybot Sonar"
    SUB_TITLE = "Live Nginx Log Analysis (Textual HUD)"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Log(id="log_stream", highlight=True)
        
        # --- NEW: The Intelligence Panel (Replaces old 3-col layout) ---
        with Container(id="intelligence_panel"):
            # Header with Source + Title
            yield Label("⚡ JAVASCRIPT EXECUTORS (Live Tracking from https://mikelev.in) ⚡", id="panel_header")
            
            # The Data Table
            yield DataTable(id="js_table")
            
            # The Countdown (Footer of panel)
            yield Label("Next Report: --:--", id="countdown_label")
        # ---------------------------------------------------------------
            
        yield Footer()

    def on_mount(self) -> None:
        self.ua_counter = Counter()
        self.stream_logs()
        
        # Setup Table
        table = self.query_one("#js_table", DataTable)
        table.add_columns("Hits", "Agent (Proof of JS Execution)")
        self.refresh_js_table() # Initial load

        # Timers
        try:
            self.start_time = float(os.environ.get("SONAR_START_TIME", time.time()))
            self.duration_mins = float(os.environ.get("SONAR_DURATION", 15))
        except:
            self.start_time = time.time()
            self.duration_mins = 15
            
        self.set_interval(1, self.update_countdown)
        self.set_interval(5, self.refresh_js_table) # Refresh table every 5s

    def refresh_js_table(self):
        """Updates the JS Executors table from DB."""
        if not db: return
        try:
            table = self.query_one("#js_table", DataTable)
            table.clear()
            
            # Get top 5 JS executors
            data = db.get_js_executors(limit=5)
            
            if not data:
                table.add_row("-", "Waiting for data...")
                return

            for ua, count in data:
                clean_ua = ua.strip()
                if len(clean_ua) > 120: 
                    clean_ua = clean_ua[:117] + "..."
                table.add_row(str(count), clean_ua)
        except:
            pass

    def update_countdown(self):
        """Ticks the clock."""
        elapsed = time.time() - self.start_time
        total_seconds = self.duration_mins * 60
        remaining = total_seconds - elapsed
        
        if remaining < 0: remaining = 0
        mins, secs = divmod(int(remaining), 60)
        
        try:
            self.query_one("#countdown_label", Label).update(f"⏱️ Next Full Report: {mins:02d}:{secs:02d}")
        except: pass

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