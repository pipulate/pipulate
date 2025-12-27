#!/usr/bin/env python3
"""
Sonar: A Real-Time Log Visualizer for the Forever Machine.
Usage: tail -f access.log | python sonar.py
"""

import sys
import re
import hashlib
import asyncio
from datetime import datetime

# Third-party imports (Provided by Nix flake)
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Header, Footer
from textual.binding import Binding

# -----------------------------------------------------------------------------
# Configuration & Patterns
# -----------------------------------------------------------------------------

# Nginx Combined Log Format Regex
# Matches: 127.0.0.1 - - [27/Dec/2025:10:00:00 +0000] "GET /index.html HTTP/1.1" 200 1234 "-" "Mozilla/5.0..."
LOG_PATTERN = re.compile(
    r'(?P<ip>[\d\.]+) - - \[(?P<time>.*?)\] "(?P<request>.*?)" (?P<status>\d+) (?P<bytes>\d+) "(?P<referrer>.*?)" "(?P<ua>.*?)"'
)

class SonarApp(App):
    """The Cybernetic HUD for watching the Black River."""

    CSS = """
    DataTable {
        height: 100%;
        border-top: solid green;
        scrollbar-gutter: stable;
    }
    Header {
        dock: top;
        height: 1;
        content-align: center middle;
        background: $primary;
        color: auto;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit Sonar"),
        Binding("c", "clear_table", "Clear History"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield DataTable(zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the data table structure."""
        table = self.query_one(DataTable)
        # Define our columns
        table.add_columns(
            "Time", 
            "Identity [Hash]", 
            "Method", 
            "Path", 
            "Status", 
            "Agent (Snippet)"
        )
        table.cursor_type = "row"
        
        # Start the background worker to read the pipe
        self.run_worker(self.monitor_stdin(), exclusive=True)

    def action_clear_table(self) -> None:
        """Clear the table rows."""
        table = self.query_one(DataTable)
        table.clear()

    # -------------------------------------------------------------------------
    # Core Logic: The Anonymization Protocol
    # -------------------------------------------------------------------------
    
    def anonymize_ip(self, ip_str):
        """
        Transforms raw IP into a semi-anonymous 'Personality'.
        Input: 192.168.10.5
        Output: 192.168.*.* [a1b2]
        """
        try:
            parts = ip_str.split('.')
            if len(parts) == 4:
                # The Mask: Keep the neighborhood
                masked = f"{parts[0]}.{parts[1]}.*.*"
                
                # The Hash: A consistent fingerprint for this session
                # We salt it with the current date so tracking resets daily (privacy)
                salt = datetime.now().strftime("%Y-%m-%d")
                hash_input = f"{ip_str}-{salt}"
                hash_digest = hashlib.md5(hash_input.encode()).hexdigest()[:4]
                
                return Text.assemble(
                    (masked, "cyan"), 
                    " ", 
                    (f"[{hash_digest}]", "bold magenta")
                )
            return Text(ip_str, style="red") # Fallback for non-IPv4
        except Exception:
            return Text(ip_str, style="red")

    def parse_request(self, request_str):
        """Breaks down the request string."""
        try:
            parts = request_str.split()
            if len(parts) >= 2:
                method = parts[0]
                path = parts[1]
                return method, path
            return "???", request_str
        except:
            return "???", request_str

    # -------------------------------------------------------------------------
    # The Pump: Reading the Stream
    # -------------------------------------------------------------------------

    async def monitor_stdin(self):
        """Reads stdin line by line in a non-blocking way."""
        # We use a file iterator on stdin which blocks, so we run it in a thread.
        # This keeps the UI responsive.
        while True:
            # Read a line from the pipe
            line = await asyncio.to_thread(sys.stdin.readline)
            
            if not line:
                break # End of stream
            
            self.process_line(line.strip())

    def process_line(self, line):
        """Parses a raw log line and schedules the UI update."""
        match = LOG_PATTERN.match(line)
        if match:
            data = match.groupdict()
            
            # 1. Identity
            ip_display = self.anonymize_ip(data['ip'])
            
            # 2. Action
            method, path = self.parse_request(data['request'])
            
            # 3. Status (Color Coded)
            status = int(data['status'])
            if 200 <= status < 300:
                status_style = "bold green"
            elif 300 <= status < 400:
                status_style = "yellow"
            elif 400 <= status < 500:
                status_style = "bold red"
            else:
                status_style = "white on red"

            # 4. Agent (The Fingerprint)
            ua = data['ua']
            
            # Default Style
            ua_style = "dim white"
            prefix = ""

            # Simple heuristic detection for coloring
            if "Googlebot" in ua:
                prefix = "🤖 "
                ua_style = "green"
            elif "GPTBot" in ua or "ClaudeBot" in ua or "anthropic" in ua.lower():
                prefix = "🧠 "
                ua_style = "bold purple"
            elif "Mozilla" in ua and "compatible" not in ua:
                prefix = "👤 "
                ua_style = "bright_white"
            elif "python" in ua.lower() or "curl" in ua.lower() or "Go-http" in ua:
                prefix = "🔧 "
                ua_style = "cyan"
            elif "bot" in ua.lower() or "spider" in ua.lower() or "crawl" in ua.lower():
                prefix = "🕷️ "
                ua_style = "yellow"

            # FULL WIDTH: No truncation. Let Textual handle the layout.
            ua_display = f"{prefix}{ua}"

            # Extract clean time (HH:MM:SS)
            # Log time format is typically: 27/Dec/2025:10:00:00
            try:
                time_part = data['time'].split(':')[1:] # Drop date part
                time_str = ":".join(time_part).split(' ')[0]
            except:
                time_str = data['time']

            row = [
                time_str,
                ip_display,
                Text(method, style="bold"),
                Text(path, style="blue"),
                Text(str(status), style=status_style),
                Text(ua_display, style=ua_style) # Use full display
            ]

            # Extract clean time (HH:MM:SS)
            # Log time format is typically: 27/Dec/2025:10:00:00
            try:
                time_part = data['time'].split(':')[1:] # Drop date part
                time_str = ":".join(time_part).split(' ')[0]
            except:
                time_str = data['time']

            row = [
                time_str,
                ip_display,
                Text(method, style="bold"),
                Text(path, style="blue"),
                Text(str(status), style=status_style),
                Text(ua_display, style=ua_style)
            ]
            
            # Schedule the UI update on the main thread
            # self.call_from_thread(self.add_table_row, row)
            # self.add_log_row(row)
            self.add_table_row(row)

    def add_table_row(self, row):
        """Adds the row to the widget."""
        table = self.query_one(DataTable)
        table.add_row(*row)
        # Auto-scroll to bottom to keep the "river" flowing
        table.scroll_end(animate=False)

if __name__ == "__main__":
    app = SonarApp()
    app.run()
