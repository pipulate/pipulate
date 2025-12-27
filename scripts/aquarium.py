import sys
import re
from datetime import datetime
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, Static, Log, Label
from textual import work
from rich.text import Text

# --- Configuration ---
# 1. The "Nuclear" ANSI Stripper (Removes colors and weird terminal codes)
ANSI_ESCAPE = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')

# 2. Standard Nginx Regex
LOG_PATTERN = re.compile(r'(?P<ip>[\d\.]+) - - \[(?P<time>.*?)\] "(?P<request>.*?)" (?P<status>\d+) (?P<bytes>\d+) "(?P<referrer>.*?)" "(?P<agent>.*?)"')

class AquariumApp(App):
    """The Cybernetic Aquarium TUI"""

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
    
    Label {
        width: 100%;
    }
    
    .header {
        color: cyan;
        text-style: bold underline;
        margin-bottom: 1;
    }
    """

    TITLE = "🌊 CYBERNETIC AQUARIUM 🌊"
    SUB_TITLE = "Monitoring Sector 7G"

    def compose(self) -> ComposeResult:
        yield Header()
        # highlight=True gives us mouse interaction, but we turn off markup parsing to be safe
        yield Log(id="log_stream", highlight=True)
        
        yield Static("Chip O'Theseus is listening...", id="ai_commentary")
        
        with Container(id="stats_panel"):
            yield Label("STATS", classes="header")
            yield Label("Hits: 0", id="stat_hits")
            yield Label("Bots: 0", id="stat_bots")
            yield Label("Err: 0", id="stat_errors")
            
        yield Footer()

    def on_mount(self) -> None:
        self.stream_logs()

    @work(thread=True)
    def stream_logs(self) -> None:
        hits = 0
        bots = 0
        errors = 0
        
        # Read directly from standard input
        for line in sys.stdin:
            # 1. Aggressive Cleaning
            # Remove ANSI codes
            clean_line = ANSI_ESCAPE.sub('', line)
            # Remove mouse reporting garbage (common patterns like <35;14;M)
            if "<" in clean_line and ";" in clean_line and "M" in clean_line:
                continue
                
            clean_line = clean_line.strip()
            if not clean_line:
                continue

            hits += 1
            data = self.parse_line(clean_line)
            
            # 2. Format
            rich_text = self.format_log_line(data)
            
            # 3. Write with explicit newline
            # We convert to string (.plain) and add \n to force the widget to wrap
            self.call_from_thread(self.write_log, rich_text.plain + "\n")

            # 4. Update Stats
            agent = data.get('agent', '')
            status = data.get('status', '')
            
            if "Google" in agent or "bot" in agent.lower():
                bots += 1
            if status.startswith('4') or status.startswith('5'):
                errors += 1
            
            self.call_from_thread(self.update_stats, hits, bots, errors)

    def write_log(self, text):
        """Write text to the log widget."""
        log = self.query_one(Log)
        log.write(text)

    def update_stats(self, hits, bots, errors):
        try:
            self.query_one("#stat_hits", Label).update(f"Hits: {hits}")
            self.query_one("#stat_bots", Label).update(f"Bots: {bots}")
            self.query_one("#stat_errors", Label).update(f"Err:  {errors}")
        except:
            pass

    def parse_line(self, line):
        match = LOG_PATTERN.search(line) # Changed from match to search to find pattern inside garbage
        if match:
            return match.groupdict()
        return {"raw": line}

    def format_log_line(self, data):
        if "raw" in data:
            return Text(data["raw"], style="dim white")
            
        status_color = "green" if data['status'].startswith('2') else "red"
        
        text = Text()
        try:
            time_part = data['time'].split(':')[1] + ":" + data['time'].split(':')[2].split(' ')[0]
            text.append(f"[{time_part}] ", style="dim")
        except:
            text.append("[TIME] ", style="dim")
            
        text.append(f"{data['ip']} ", style="blue")
        
        req_str = f"{data['request']}"
        if len(req_str) > 50:
            req_str = req_str[:47] + "..."
            
        text.append(f"{req_str} ", style="bold white")
        text.append(f"{data['status']}", style=status_color)
        return text

if __name__ == "__main__":
    app = AquariumApp()
    app.run()
