This is the **"Triptych Dashboard"** update.

We are transforming the report from a single list into a **3-Panel Intelligence Console**.

**The Layout:**

* **Top Row:** A unified header explaining the "State of the Trap."
* **Bottom Row (Left):** "The Horse Race" (Top User Agents by volume).
* **Bottom Row (Center):** "The Renderers" (Agents that executed JS/MathJax).
* **Bottom Row (Right):** "The Readers" (Agents that fetched Source Markdown).

Here is the complete rewrite for `remotes/honeybot/scripts/report.py`.

```python:/home/mike/repos/pipulate/remotes/honeybot/scripts/report.py
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, DataTable, Label
from textual.containers import Container, Vertical
from db import db  # Import our shared DB instance

class ReportApp(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 6;
        background: #200020;
    }

    /* TOP HEADER: Spans all 3 columns */
    #main_header {
        column-span: 3;
        row-span: 1;
        text-align: center;
        color: #00ff00;
        text-style: bold;
        border-bottom: solid green;
        padding: 1;
    }

    /* COLUMNS: Each takes 1 column, spanning remaining height */
    .column {
        column-span: 1;
        row-span: 5;
        border: solid purple;
        margin: 1;
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
        padding: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        
        # 1. The Main Explainer (Top Row)
        yield Static(
            "\n📊 TRAFFIC INTELLIGENCE REPORT\n\n"
            "Left: Volume Leaders | Center: JavaScript Executors (MathJax) | Right: Semantic Readers (Markdown)", 
            id="main_header"
        )

        # 2. Left Panel: Volume
        with Vertical(classes="column"):
            yield Label("🏆 TOP VOLUME", classes="col_header")
            yield DataTable(id="table_top")

        # 3. Center Panel: Capability (JS)
        with Vertical(classes="column"):
            yield Label("⚡ JS EXECUTORS", classes="col_header")
            yield DataTable(id="table_js")

        # 4. Right Panel: Intent (Markdown)
        with Vertical(classes="column"):
            yield Label("🧠 MD READERS", classes="col_header")
            yield DataTable(id="table_md")

        yield Footer()

    def populate_table(self, table_id, data_source):
        """Helper to fill a table safely."""
        try:
            table = self.query_one(f"#{table_id}", DataTable)
            table.add_columns("Hits", "Agent")
            
            data = data_source(limit=10) # Fetch top 10
            
            if not data:
                table.add_row("-", "No data yet")
                return

            for ua, count in data:
                # --- The Mozilla Mask Fix ---
                clean_ua = ua.strip()
                # Truncate strictly for UI fit
                if len(clean_ua) > 35: 
                    clean_ua = clean_ua[:32] + "..."
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

```

### What this does:

1. **Visual Structure:** Creates a clean 3-column grid.
2. **Data Wiring:** Connects the three `DataTable` widgets to your three `HoneyDB` methods:
* `#table_top` -> `get_top_user_agents`
* `#table_js` -> `get_js_executors` (The Trap Results)
* `#table_md` -> `get_markdown_readers` (The Reader Results)


3. **Safety:** Includes the truncation logic (Mozilla Mask fix) adjusted for narrower columns (`limit=35` chars) so the layout doesn't break.

Deploy this, and when the countdown hits zero, you will see the **Classification** of your visitors, not just a count.