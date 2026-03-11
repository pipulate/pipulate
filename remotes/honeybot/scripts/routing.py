from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, DataTable, Label
from textual.containers import Vertical
from rich.text import Text
from db import db, KNOWN_BOTS
import re

class RoutingApp(App):
    CSS = """
    Screen {
        layout: vertical;
        background: #0d001a; /* Deep Violet Background */
    }

    #routing_header {
        height: auto;
        text-align: center;
        color: #ff00ff;
        text-style: bold;
        background: #2a0033;
        border-bottom: solid magenta;
        padding: 0 1;
    }

    .panel {
        height: 1fr; 
        border: solid magenta;
        margin: 0 1;
    }
    
    .panel_title {
        text-align: center;
        background: #4d004d;
        color: #ffb3ff;
        text-style: bold;
        padding: 0 1;
        dock: top;
    }
    
    DataTable {
        height: 1fr;
        width: 100%;
        background: #0d001a;
        color: #ffccff;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        
        yield Static(
            "🧭 SEMANTIC LOGISTICS | Tracking Agent Discovery Vectors", 
            id="routing_header"
        )

        # 1. Routing Panel
        with Vertical(classes="panel"):
            yield Label("🗺️ EXPLICIT ROUTING (Manifests & Link Tags)", classes="panel_title")
            yield DataTable(id="table_routes")

        # 2. Negotiation Panel
        with Vertical(classes="panel"):
            yield Label("🤝 HTTP CONTENT NEGOTIATION (The Loading Dock)", classes="panel_title")
            yield DataTable(id="table_neg")

        yield Footer()

    def extract_and_stylize(self, agent_str):
        agent_str = agent_str.strip().replace("Mozilla/5.0 ", "")
        identity = "Unknown"
        identity_style = "dim white"
        
        for bot_name in KNOWN_BOTS:
            if bot_name in agent_str:
                identity = bot_name
                identity_style = "bold orange1"
                break
                
        id_text = Text(identity, style=identity_style)
        full_text = Text(agent_str, style="dim magenta")
        return id_text, full_text

    def on_mount(self) -> None:
        # Populate Routes Table
        table_routes = self.query_one("#table_routes", DataTable)
        table_routes.add_columns("Vector", "Hits", "Identity", "Raw Signature")
        
        try:
            route_data = db.get_md_routing_agents()
            if not route_data:
                table_routes.add_row("-", "-", "None", "No signals detected")
            else:
                for vector, ua, count in route_data:
                    identity, signature = self.extract_and_stylize(ua)
                    table_routes.add_row(Text(vector, style="bold cyan"), str(count), identity, signature)
        except Exception as e:
            table_routes.add_row("ERROR", "-", "None", str(e)[:40])

        # Populate Negotiation Table
        table_neg = self.query_one("#table_neg", DataTable)
        table_neg.add_columns("Hits", "Identity", "Raw Signature")
        
        try:
            neg_data = db.get_content_neg_agents()
            if not neg_data:
                table_neg.add_row("-", "None", "No negotiation detected")
            else:
                for ua, count in neg_data:
                    identity, signature = self.extract_and_stylize(ua)
                    table_neg.add_row(str(count), identity, signature)
        except Exception as e:
            table_neg.add_row("ERROR", "None", str(e)[:40])

if __name__ == "__main__":
    app = RoutingApp()
    app.run()