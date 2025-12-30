#!/usr/bin/env python3
"""
Sonar V2: Stable Core Edition.
Based on the rock-solid aquarium.py log widget, enhanced with IP hashing.
"""

import sys
import re
import hashlib
from datetime import datetime
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, Static, Log, Label, Markdown
from textual import work
from rich.text import Text

# --- Configuration ---
# 1. The "Nuclear" ANSI Stripper
ANSI_ESCAPE = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')

# 2. Standard Nginx Regex
LOG_PATTERN = re.compile(r'(?P<ip>[\d\.]+) - - \[(?P<time>.*?)\] "(?P<request>.*?)" (?P<status>\d+) (?P<bytes>\d+) "(?P<referrer>.*?)" "(?P<ua>.*?)"')

class SonarApp(App):
    """The Cybernetic HUD (Stable Edition)."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 4 6;
        background: #0f1f27;
    }

    /* TOP SECTION: Full Width Log Stream */
    #log_stream {
        column-span: 4;
        row-span: 5;
        background: #000000;
        border: solid #00ff00;
        color: #00ff00;
        height: 100%;
        scrollbar-gutter: stable;
        overflow-y: scroll;
    }

    /* BOTTOM LEFT: AI Commentary */
    #ai_commentary {
        column-span: 3;
        row-span: 1;
        border: solid magenta;
        background: #100010;
        height: 100%;
        content-align: center middle;
        text-style: bold;
    }
    
    /* BOTTOM RIGHT: Stats */
    #stats_panel {
        column-span: 1;
        row-span: 1;
        border: solid cyan;
        background: #051515;
        padding: 0 1;
    }

    /* Update AI Commentary style for Markdown */
    #active_projects {
        column-span: 3;
        row-span: 1;
        border: solid magenta;
        background: #100010;
        height: 100%;
        padding: 0 1;
    }
    
    Label {
        width: 100%;
    }
    
    .header {
        color: cyan;
        text-style: bold underline;
        margin-bottom: 1;
    }
    """

    TITLE = "🌊 SONAR V2 🌊"
    SUB_TITLE = "Listening to the Black River"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Log(id="log_stream", highlight=True)
        
        # CHANGED: Replaced Static with Markdown for formatted list
        yield Markdown("""
**Active Projects:**
1. 📖 Storytelling Framework (In Progress)
2. 🚦 Smart 404 Handler (Pending)
3. 🤖 AI-Bot JS Execution Detector (Pending)
""", id="active_projects")
        
        with Container(id="stats_panel"):
            yield Label("STATS", classes="header")
            yield Label("Hits: 0", id="stat_hits")
            yield Label("Bots: 0", id="stat_bots")
            yield Label("Err:  0", id="stat_errors")
            
        yield Footer()

    def on_mount(self) -> None:
        self.stream_logs()

    # -------------------------------------------------------------------------
    # Core Logic: IP Anonymization (Ported from Sonar V1)
    # -------------------------------------------------------------------------
    def anonymize_ip(self, ip_str):
        """Transforms raw IP into a semi-anonymous 'Personality'."""
        try:
            parts = ip_str.split('.')
            if len(parts) == 4:
                # Mask
                masked = f"{parts[0]}.{parts[1]}.*.*"
                # Hash
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
                return parts[0], parts[1] # Method, Path
            return "???", request_str
        except:
            return "???", request_str

    @work(thread=True)
    def stream_logs(self) -> None:
        hits = 0
        bots = 0
        errors = 0
        
        # Read directly from standard input (The Pipe)
        for line in sys.stdin:
            # 1. Clean
            clean_line = ANSI_ESCAPE.sub('', line)
            if "<" in clean_line and ";" in clean_line and "M" in clean_line: continue
            clean_line = clean_line.strip()
            if not clean_line: continue

            hits += 1
            
            # 2. Parse & Format
            match = LOG_PATTERN.search(clean_line)
            if match:
                data = match.groupdict()
                
                # Stats update
                if "bot" in data['ua'].lower() or "spider" in data['ua'].lower():
                    bots += 1
                if data['status'].startswith('4') or data['status'].startswith('5'):
                    errors += 1
                
                rich_text = self.format_log_line(data)

                # --- NEW LOGIC: Conditional Prefix Newline ---
                # This breaks the "forever line" by adding a return BEFORE the entry
                # but ONLY if it is not the first one.
                if hits > 1:
                    rich_text = Text("\n") + rich_text
                
                # Write to Log widget (Stable!)
                self.call_from_thread(self.write_log, rich_text)
                self.call_from_thread(self.update_stats, hits, bots, errors)
            else:
                # Fallback for non-matching lines
                text_obj = Text(clean_line, style="dim")
                if hits > 1:
                    text_obj = Text("\n") + text_obj
                self.call_from_thread(self.write_log, text_obj)

    def write_log(self, text):
        log = self.query_one(Log)
        # Only write the string content for now to stop the crash
        # We lose color temporarily but gain stability
        if hasattr(text, "plain"):
             log.write(text.plain)
        else:
             log.write(str(text))

    def update_stats(self, hits, bots, errors):
        try:
            self.query_one("#stat_hits", Label).update(f"Hits: {hits}")
            self.query_one("#stat_bots", Label).update(f"Bots: {bots}")
            self.query_one("#stat_errors", Label).update(f"Err:  {errors}")
        except:
            pass

    def format_log_line(self, data):
        # Color coding status
        status = int(data['status'])
        if 200 <= status < 300: status_style = "bold green"
        elif 300 <= status < 400: status_style = "yellow"
        elif 400 <= status < 500: status_style = "bold red"
        else: status_style = "white on red"

        # Identity
        ip_display = self.anonymize_ip(data['ip'])
        
        # Request
        method, path = self.parse_request(data['request'])
        
        # User Agent (Full Width Logic)
        ua = data['ua']
        ua_style = "dim white"
        prefix = ""
        if "Googlebot" in ua: prefix = "🤖 "; ua_style = "green"
        elif "GPTBot" in ua or "Claude" in ua: prefix = "🧠 "; ua_style = "bold purple"
        elif "Mozilla" in ua and "compatible" not in ua: prefix = "👤 "; ua_style = "bright_white"
        elif "python" in ua.lower() or "curl" in ua.lower(): prefix = "🔧 "; ua_style = "cyan"
        
        ua_display = f"{prefix}{ua}"

        # Assembly
        text = Text()
        try:
            time_str = data['time'].split(':')[1:]
            time_str = ":".join(time_str).split(' ')[0]
            text.append(f"[{time_str}] ", style="dim")
        except:
            text.append("[TIME] ", style="dim")
            
        text.append(ip_display)
        text.append(" | ", style="dim")
        text.append(f"{method:4} ", style="bold")
        text.append(f"{path} ", style="blue")
        text.append(f"[{status}] ", style=status_style)
        
        # Single line separator
        text.append(" | ", style="dim")
        text.append(f"{ua_display}", style=ua_style)
        
        return text

if __name__ == "__main__":
    app = SonarApp()
    app.run()
