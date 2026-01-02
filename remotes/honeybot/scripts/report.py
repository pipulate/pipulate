from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, DataTable, Label
from textual.containers import Container, Vertical
from db import db  # Import our shared DB instance

class ReportApp(App):
    CSS = """
    Screen {
        layout: vertical; /* CHANGED: Stack panels vertically */
        background: #200020;
    }

    /* TOP HEADER: Compact and efficient */
    #main_header {
        height: auto;
        text-align: center;
        color: #00ff00;
        text-style: bold;
        background: #002200;
        border-bottom: solid green;
        padding: 0 1;
    }

    /* SECTIONS: Each takes equal available vertical space */
    .section {
        height: 1fr;
        border: solid purple;
        margin: 0 0 1 0; /* Slight spacing between panels */
    }

    /* Table Styling */
    DataTable {
        height: 1fr;
        width: 100%;
    }
    
    .col_header {
        text-align: center;
        background: #400040;
        color: white;
        text-style: bold;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        
        # 1. The Main Explainer (Top Row - Compact)
        yield Static(
            "📊 TRAFFIC INTELLIGENCE REPORT | Volume vs Capability vs Intent", 
            id="main_header"
        )

        # 2. Top Volume Panel
        with Container(classes="section"):
            yield Label("🏆 TOP VOLUME LEADERS", classes="col_header")
            yield DataTable(id="table_top")

        # 3. Capability Panel (JS)
        with Container(classes="section"):
            yield Label("⚡ JAVASCRIPT EXECUTORS (MathJax Resource Fetch)", classes="col_header")
            yield DataTable(id="table_js")

        # 4. Intent Panel (Markdown)
        with Container(classes="section"):
            yield Label("🧠 SEMANTIC READERS (Source Markdown Fetch)", classes="col_header")
            yield DataTable(id="table_md")

        yield Footer()

    def populate_table(self, table_id, data_source):
        """Helper to fill a table safely."""
        try:
            table = self.query_one(f"#{table_id}", DataTable)
            table.add_columns("Hits", "Agent")
            
            # Use limit=5 for stacked layout to avoid scrolling on standard screens
            data = data_source(limit=5) 
            
            if not data:
                table.add_row("-", "No data yet")
                return

            for ua, count in data:
                # --- The Mozilla Mask Fix ---
                clean_ua = ua.strip()
                # Truncate strictly for UI fit - WIDER NOW due to vertical layout
                if len(clean_ua) > 90: 
                    clean_ua = clean_ua[:87] + "..."
                # ----------------------------
                table.add_row(str(count), clean_ua)
                
        except Exception as e:
            try:
                table = self.query_one(f"#{table_id}", DataTable)
                table.add_row("ERR", str(e)[:20])
            except: pass

    def on_mount(self) -> None:
        # Populate all three panels
        self.populate_table("table_top", db.get_top_user_agents)
        self.populate_table("table_js", db.get_js_executors)
        self.populate_table("table_md", db.get_markdown_readers)

if __name__ == "__main__":
    app = ReportApp()
    app.run()