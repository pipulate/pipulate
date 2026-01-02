from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, DataTable, Label
from textual.containers import Container, Vertical
from db import db  # Import our shared DB instance

class ReportApp(App):
    CSS = """
    Screen {
        layout: vertical;
        background: #200020;
    }

    #main_header {
        height: auto;
        text-align: center;
        color: #00ff00;
        text-style: bold;
        background: #002200;
        border-bottom: solid green;
        padding: 0 1;
    }

    .section {
        height: 1fr; 
        border: solid purple;
        margin: 0 0 1 0;
        /* Removed overflow: auto from here to keep label sticky */
    }
    
    /* New container specifically for the table scrolling */
    .table_container {
        height: 1fr;
        overflow: auto;
    }

    DataTable {
        height: auto; /* Let table grow inside the scroll container */
        width: 100%;
    }
    
    .col_header {
        text-align: center;
        background: #400040;
        color: white;
        text-style: bold;
        padding: 0 1;
        dock: top; /* Ensure it stays at the top */
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        
        yield Static(
            "📊 TRAFFIC INTELLIGENCE REPORT | Volume vs Capability vs Intent", 
            id="main_header"
        )

        # 2. Top Volume Panel
        with Vertical(classes="section"):
            yield Label("🏆 TOP VOLUME LEADERS", classes="col_header")
            with Container(classes="table_container"):
                yield DataTable(id="table_top")

        # 3. Capability Panel (JS)
        with Vertical(classes="section"):
            yield Label("⚡ JAVASCRIPT EXECUTORS (MathJax Resource Fetch)", classes="col_header")
            with Container(classes="table_container"):
                yield DataTable(id="table_js")

        # 4. Intent Panel (Markdown)
        with Vertical(classes="section"):
            yield Label("🧠 SEMANTIC READERS (Source Markdown Fetch)", classes="col_header")
            with Container(classes="table_container"):
                yield DataTable(id="table_md")

        yield Footer()

    def populate_table(self, table_id, data_source):
        try:
            table = self.query_one(f"#{table_id}", DataTable)
            table.add_columns("Hits", "Agent")
            
            data = data_source(limit=20) 
            
            if not data:
                table.add_row("-", "No data yet")
                return

            for ua, count in data:
                clean_ua = ua.strip()
                if len(clean_ua) > 140: 
                    clean_ua = clean_ua[:137] + "..."
                
                table.add_row(str(count), clean_ua)
                
        except Exception as e:
            try:
                table = self.query_one(f"#{table_id}", DataTable)
                table.add_row("ERR", str(e)[:20])
            except: pass

    def on_mount(self) -> None:
        self.populate_table("table_top", db.get_top_user_agents)
        self.populate_table("table_js", db.get_js_executors)
        self.populate_table("table_md", db.get_markdown_readers)

if __name__ == "__main__":
    app = ReportApp()
    app.run()