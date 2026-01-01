from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, DataTable
from textual.containers import Container
from db import db  # Import our shared DB instance

class ReportApp(App):
    CSS = """
    Screen {
        align: center middle;
        background: #200020;
    }
    Static {
        text-align: center;
        color: #00ff00;
        text-style: bold;
        margin-bottom: 2;
    }
    DataTable {
        height: auto;
        width: auto;
        border: solid purple;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("\n📊 TRAFFIC INTELLIGENCE REPORT\nTop Detected Agents"),
            DataTable(id="stats_table"),
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Hits", "User Agent Identity")
        
        # Fetch real data from the salt mine
        try:
            top_agents = db.get_top_user_agents(limit=8)
            for ua, count in top_agents:
                # Clean up the UA string for display
                short_ua = ua.split('/')[0] 
                if len(short_ua) > 50: short_ua = short_ua[:47] + "..."
                table.add_row(str(count), short_ua)
        except Exception as e:
            table.add_row("ERROR", str(e))

if __name__ == "__main__":
    app = ReportApp()
    app.run()