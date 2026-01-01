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
                # --- FIX: Stop chopping at the first slash ---
                # Just truncate the very end if it's too long for the TUI
                clean_ua = ua.strip()
                if len(clean_ua) > 60: 
                    clean_ua = clean_ua[:57] + "..."
                # ---------------------------------------------
                table.add_row(str(count), clean_ua)
        except Exception as e:
            table.add_row("ERROR", str(e))


if __name__ == "__main__":
    app = ReportApp()
    app.run()
