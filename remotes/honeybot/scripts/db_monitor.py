from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Label, Static
from textual.containers import Container, Horizontal, Vertical
from textual import work
import time
from datetime import datetime
from db import db

class DBMonitor(App):
    CSS = """
    Screen { background: #1a1a1a; }
    
    .metric {
        height: 1fr;
        border: solid green;
        text-align: center;
        content-align: center middle;
        margin: 1;
    }
    
    .metric-title { color: #888; text-style: bold; }
    .metric-value { color: #0f0; text-style: bold; font-size: 2; }
    
    #recent-table {
        height: 2fr;
        border: solid blue;
        margin: 1;
    }
    
    #trap-panel {
        height: 1fr;
        border: solid red;
        margin: 1;
        background: #200;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        # Top Row: Vital Stats
        with Horizontal(style="height: 14;"):
            with Vertical(classes="metric"):
                yield Label("Unique IPs", classes="metric-title")
                yield Label("...", id="count-ips", classes="metric-value")
            with Vertical(classes="metric"):
                yield Label("Unique UAs", classes="metric-title")
                yield Label("...", id="count-uas", classes="metric-value")
            with Vertical(classes="metric"):
                yield Label("Unique Paths", classes="metric-title")
                yield Label("...", id="count-paths", classes="metric-value")
            with Vertical(classes="metric"):
                yield Label("Total Hits", classes="metric-title")
                yield Label("...", id="count-hits", classes="metric-value")

        # Middle: Latest Ingested Rows
        yield Label("  🔻 LATEST DATABASE INSERTS (Live)", style="color: blue; text-style: bold;")
        yield DataTable(id="recent-table")

        # Bottom: The Trap Monitor
        with Vertical(id="trap-panel"):
            yield Label("  🪤 BOT TRAP STATUS (d3.v7.min.js)", style="color: red; text-style: bold;")
            yield Label("Waiting for signal...", id="trap-status")

        yield Footer()

    def on_mount(self):
        table = self.query_one("#recent-table", DataTable)
        table.add_columns("Time", "IP", "Path", "UA", "Status")
        self.set_interval(2, self.refresh_stats)
        self.refresh_stats()

    def refresh_stats(self):
        conn = db.get_conn()
        cur = conn.cursor()

        # 1. Update Counters
        try:
            cur.execute("SELECT Count(*) FROM ips")
            self.query_one("#count-ips", Label).update(str(cur.fetchone()[0]))
            
            cur.execute("SELECT Count(*) FROM user_agents")
            self.query_one("#count-uas", Label).update(str(cur.fetchone()[0]))
            
            cur.execute("SELECT Count(*) FROM paths")
            self.query_one("#count-paths", Label).update(str(cur.fetchone()[0]))

            cur.execute("SELECT value FROM kv_store WHERE key='global_hits'")
            res = cur.fetchone()
            self.query_one("#count-hits", Label).update(str(res[0]) if res else "0")
        except: pass

        # 2. Update Recent Table (Join for readability)
        try:
            sql = """
                SELECT 
                    logs.last_updated,
                    ips.value,
                    paths.value,
                    ua.value,
                    logs.status
                FROM daily_logs logs
                JOIN ips ON logs.ip_id = ips.id
                JOIN paths ON logs.path_id = paths.id
                JOIN user_agents ua ON logs.ua_id = ua.id
                ORDER BY logs.last_updated DESC
                LIMIT 5
            """
            cur.execute(sql)
            rows = cur.fetchall()
            
            table = self.query_one("#recent-table", DataTable)
            table.clear()
            for r in rows:
                # Truncate UA for display
                ua_short = r[3][:40] + "..." if len(r[3]) > 40 else r[3]
                table.add_row(r[0], r[1], r[2], ua_short, str(r[4]))
        except Exception as e:
             self.notify(f"DB Error: {e}")

        # 3. Check Trap specifically
        try:
            sql = """
                SELECT ua.value, SUM(logs.count) 
                FROM daily_logs logs
                JOIN user_agents ua ON logs.ua_id = ua.id
                JOIN paths p ON logs.path_id = p.id
                WHERE p.value LIKE '%d3.v7.min.js%'
                GROUP BY ua.id
                ORDER BY logs.last_updated DESC
                LIMIT 1
            """
            cur.execute(sql)
            trap_res = cur.fetchone()
            if trap_res:
                self.query_one("#trap-status", Label).update(
                    f"⚠️ CAUGHT: {trap_res[0]} (Hits: {trap_res[1]})"
                )
            else:
                self.query_one("#trap-status", Label).update("No trap triggers yet.")
        except: pass

if __name__ == "__main__":
    app = DBMonitor()
    app.run()