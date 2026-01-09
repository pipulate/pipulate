from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, DataTable, Label
from textual.containers import Container, Vertical, Horizontal
from rich.text import Text
from db import db, KNOWN_BOTS
import re

# Import Shared Bot List (We need to centralize this properly later, but for now we copy-paste or import)
# Ideally, we should move KNOWN_BOTS to a shared config.py, but to keep it simple we'll use a small helper here.

class RadarApp(App):
    CSS = """
    Screen {
        layout: vertical;
        background: #001000; /* Dark Radar Green Background */
    }

    #radar_header {
        height: auto;
        text-align: center;
        color: #00ff00;
        text-style: bold;
        background: #002200;
        border-bottom: solid green;
        padding: 0 1;
    }

    .panel {
        height: 1fr; 
        border: solid green;
        margin: 0 1;
    }
    
    .panel_title {
        text-align: center;
        background: #004400;
        color: #00ff00;
        text-style: bold;
        padding: 0 1;
        dock: top;
    }
    
    DataTable {
        height: 1fr;
        width: 100%;
        background: #001000;
        color: #00ff00;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        
        yield Static(
            "📡 CAPABILITY RADAR | Detecting Advanced Agent Behaviors", 
            id="radar_header"
        )

        # 1. JS Capability Panel
        with Vertical(classes="panel"):
            yield Label("⚡ JAVASCRIPT EXECUTORS (Rendering Engine Detected)", classes="panel_title")
            yield DataTable(id="table_js")

        # 2. Intent Panel
        with Vertical(classes="panel"):
            yield Label("🧠 SOURCE MINERS (Raw Markdown/Data Fetch)", classes="panel_title")
            yield DataTable(id="table_md")

        yield Footer()

    def stylize_agent(self, agent_str):
        agent_str = agent_str.strip().replace("Mozilla/5.0 ", "")
        text = Text(agent_str)
        
        # Default styling (Radar theme)
        text.stylize("dim green")

        # Highlight Bots (Precision)
        for bot_name in KNOWN_BOTS:
            if bot_name in agent_str:
                # We use regex escape to be safe
                text.highlight_regex(re.escape(bot_name), "bold orange1")
                
        return text

    def populate_table(self, table_id, data_source):
        try:
            table = self.query_one(f"#{table_id}", DataTable)
            table.add_columns("Hits", "Agent Identity")
            
            data = data_source(limit=15) 
            
            if not data:
                table.add_row("-", "No signals detected")
                return

            for ua, count in data:
                table.add_row(str(count), self.stylize_agent(ua))
                
        except Exception as e:
            pass

    def on_mount(self) -> None:
        self.populate_table("table_js", db.get_js_executors)
        self.populate_table("table_md", db.get_markdown_readers)

if __name__ == "__main__":
    app = RadarApp()
    app.run()
