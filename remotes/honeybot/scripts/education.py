from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, DataTable, Label
from textual.containers import Container, Vertical
from rich.text import Text
from db import db

class EducationApp(App):
    CSS = """
    Screen {
        layout: vertical;
        background: #000022; /* Deep Academic Blue */
    }

    #header {
        height: auto;
        text-align: center;
        color: #00ffff;
        text-style: bold;
        background: #000044;
        border-bottom: solid cyan;
        padding: 0 1;
    }

    .panel {
        height: 1fr; 
        border: solid cyan;
        margin: 0 1;
        padding: 1;
    }
    
    DataTable {
        height: 1fr;
        width: 100%;
        background: #000022;
        color: #00ffff;
        border: none;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        
        yield Static(
            "🎓 AIE MONITOR | Artificial Intelligence Education Rate", 
            id="header"
        )

        with Vertical(classes="panel"):
            yield DataTable(id="roster")

        yield Footer()

    def make_bar(self, count, max_count):
        """Generates a visual progress bar of attention."""
        if max_count == 0: return ""
        width = 40
        filled = int((count / max_count) * width)
        # Gradient from Cyan to Blue
        bar = "█" * filled
        empty = "░" * (width - filled)
        return Text.assemble((bar, "bold cyan"), (empty, "dim blue"))

    def populate_table(self):
        try:
            table = self.query_one("#roster", DataTable)
            table.clear()
            table.add_columns("Family", "Ingestion Volume", "Attention Share")
            
            data = db.get_ai_education_status()
            
            if not data:
                table.add_row("No Classes in Session", "-", "-")
                return

            # Find the "Top Student" to scale the bars
            max_hits = data[0][1] if data else 1

            for family, count in data:
                bar = self.make_bar(count, max_hits)
                table.add_row(
                    Text(family, style="bold white"), 
                    str(count), 
                    bar
                )
                
        except Exception as e:
            pass

    def on_mount(self) -> None:
        self.populate_table()

if __name__ == "__main__":
    app = EducationApp()
    app.run()