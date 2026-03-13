import sqlite3
import datetime
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INTEL_PATH = REPO_ROOT / "assets" / "prompts" / "bot_intel.json"

with open(INTEL_PATH, "r") as f:
    BOT_INTEL = json.load(f)

# Shared Intelligence automatically generated from JSON
KNOWN_BOTS = list(BOT_INTEL["seen"].keys())

# The single file that holds the truth
DB_PATH = Path("/home/mike/www/mikelev.in/honeybot.db")

class HoneyDB:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = None
        self.init_db()

    def get_conn(self):
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            # Enable WAL mode for concurrency (readers don't block writers)
            self.conn.execute("PRAGMA journal_mode=WAL;")
        return self.conn

    def init_db(self):
        """Creates the schema if it doesn't exist. Idempotent."""
        conn = self.get_conn()
        cur = conn.cursor()

        # 1. The Dimensions (Normalized Tables)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ips (
                id INTEGER PRIMARY KEY,
                value TEXT UNIQUE,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_agents (
                id INTEGER PRIMARY KEY,
                value TEXT UNIQUE,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS paths (
                id INTEGER PRIMARY KEY,
                value TEXT UNIQUE,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. The Fact Table (Daily Aggregation)
        # Composite Key: Date + IP + UA + Path + Status
        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_logs (
                date TEXT,
                ip_id INTEGER,
                ua_id INTEGER,
                path_id INTEGER,
                status INTEGER,
                count INTEGER DEFAULT 1,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (date, ip_id, ua_id, path_id, status),
                FOREIGN KEY(ip_id) REFERENCES ips(id),
                FOREIGN KEY(ua_id) REFERENCES user_agents(id),
                FOREIGN KEY(path_id) REFERENCES paths(id)
            )
        """)

        # --- NEW: TELEMETRY DIMENSIONS ---
        cur.execute("""
            CREATE TABLE IF NOT EXISTS referrers (
                id INTEGER PRIMARY KEY,
                value TEXT UNIQUE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS accept_headers (
                id INTEGER PRIMARY KEY,
                value TEXT UNIQUE
            )
        """)
        
        # --- NEW: TELEMETRY FACT TABLE (SIDECAR) ---
        # Maps the daily activity to the new dimensions without breaking the old table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                date TEXT,
                ip_id INTEGER,
                path_id INTEGER,
                ua_id INTEGER,
                referrer_id INTEGER,
                accept_id INTEGER,
                served_md INTEGER,
                count INTEGER DEFAULT 1,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (date, ip_id, path_id, ua_id, referrer_id, accept_id, served_md)
            )
        """)

        # 3. The Simple KV Store (Persistent Counters)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()

    def _get_or_create_id(self, table, value):
        """Helper to manage normalized dimensions."""
        conn = self.get_conn()
        cur = conn.cursor()
        
        # Try to find existing
        cur.execute(f"SELECT id FROM {table} WHERE value = ?", (value,))
        res = cur.fetchone()
        if res:
            return res[0]
            
        # Insert new (Ignore conflicts to be safe against race conditions)
        try:
            cur.execute(f"INSERT OR IGNORE INTO {table} (value) VALUES (?)", (value,))
            conn.commit()
            # Fetch again to get the ID
            cur.execute(f"SELECT id FROM {table} WHERE value = ?", (value,))
            return cur.fetchone()[0]
        except:
            return None

    def log_request(self, ip, ua, path, status, date_str=None, referrer=None, accept=None, served_md=None):
        """
        The Main Ingestor. 
        Takes raw log data, normalizes it, and updates the daily counter.
        """
        if not date_str:
            date_str = datetime.date.today().isoformat()

        # 1. Resolve IDs (The Normalization)
        ip_id = self._get_or_create_id('ips', ip)
        ua_id = self._get_or_create_id('user_agents', ua)
        path_id = self._get_or_create_id('paths', path)

        # 2. Upsert the Daily Record
        sql = """
            INSERT INTO daily_logs (date, ip_id, ua_id, path_id, status, count)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(date, ip_id, ua_id, path_id, status) 
            DO UPDATE SET count = count + 1, last_updated = CURRENT_TIMESTAMP
        """
        
        conn = self.get_conn()
        conn.execute(sql, (date_str, ip_id, ua_id, path_id, status))

        # 3. Handle Telemetry (If provided by the new Nginx format)
        if accept is not None:
            ref_id = self._get_or_create_id('referrers', referrer) if referrer else None
            acc_id = self._get_or_create_id('accept_headers', accept)
            is_md = 1 if served_md == '1' else 0
            
            sql_telemetry = """
                INSERT INTO telemetry (date, ip_id, path_id, ua_id, referrer_id, accept_id, served_md, count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(date, ip_id, path_id, ua_id, referrer_id, accept_id, served_md) 
                DO UPDATE SET count = count + 1, last_updated = CURRENT_TIMESTAMP
            """
            conn.execute(sql_telemetry, (date_str, ip_id, path_id, ua_id, ref_id, acc_id, is_md))

        conn.commit()

    def increment_counter(self, key, amount=1):
        """Updates a simple persistent counter."""
        sql = """
            INSERT INTO kv_store (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = value + ?, updated_at = CURRENT_TIMESTAMP
        """
        conn = self.get_conn()
        conn.execute(sql, (key, amount, amount))
        conn.commit()

    def get_counter(self, key):
        """Reads a counter."""
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT value FROM kv_store WHERE key = ?", (key,))
        res = cur.fetchone()
        return res[0] if res else 0

    def get_top_user_agents(self, limit=5):
        """Fetches the top user agents by total hit count."""
        conn = self.get_conn()
        cur = conn.cursor()
        sql = """
            SELECT ua.value, SUM(logs.count) as total
            FROM daily_logs logs
            JOIN user_agents ua ON logs.ua_id = ua.id
            GROUP BY ua.id
            ORDER BY total DESC
            LIMIT ?
        """
        cur.execute(sql, (limit,))
        return cur.fetchall()

    # Helper to construct the exclusion clause
    # We filter out UAs that are "Mozilla" but NOT "compatible" (which bots often use)
    # AND contain typical platform strings.
    # UPDATE: Added exclusion for Googlebot Smartphone/Inspection (Nexus 5X)
    # UPDATE: Added exclusion for generic HTTP clients (python-httpx, Go-http-client)
    # UPDATE: Added exclusion for Google Inspection Tool and ancient Ubuntu 10.04 bots
    _BROWSER_FILTER = """
        AND ua.value NOT LIKE '%Nexus 5X%'
        AND ua.value NOT LIKE '%Google-InspectionTool%'
        AND ua.value NOT LIKE '%Ubuntu/10.04%'
        AND ua.value NOT LIKE '%Ubuntu%'  /* Admin Scrub: Catches your local dev boxes */
        AND ua.value NOT LIKE '%iPad%'    /* Admin Scrub: Catches the iPad OS leak */
        AND ua.value NOT LIKE 'python-httpx%'
        AND ua.value NOT LIKE 'Go-http-client%'
        AND NOT (
            ua.value LIKE 'Mozilla%' 
            AND ua.value NOT LIKE '%compatible%' 
            AND (
                ua.value LIKE '%Windows NT%' OR 
                ua.value LIKE '%Macintosh%' OR 
                ua.value LIKE '%X11%' OR      /* Broadened to catch all X11 variants */
                ua.value LIKE '%iPhone%' OR
                ua.value LIKE '%iPad%' OR     /* Added iPad to standard OS checks */
                ua.value LIKE '%Android%'
            )
        )
    """

    # NEW: The AIE Aggregation Query
    def get_ai_education_status(self):
        """
        Groups traffic by AI Family to visualize Education Rate.
        Who is actually learning from us?
        """
        conn = self.get_conn()
        cur = conn.cursor()
        
        # We categorize the Known Bots into Families
        case_lines = []
        for bot, family in BOT_INTEL["seen"].items():
            if family not in ("Other", "Script", "Search", "SEO Tool"):
                case_lines.append(f"WHEN ua.value LIKE '%{bot}%' THEN '{family}'")
        
        case_sql = "\n                    ".join(case_lines)

        sql = f"""
            SELECT 
                CASE 
                    {case_sql}
                    ELSE 'Other Agents'
                END as family,
                SUM(logs.count) as total
            FROM daily_logs logs
            JOIN user_agents ua ON logs.ua_id = ua.id
            WHERE family != 'Other Agents' 
            {self._BROWSER_FILTER}
            GROUP BY family
            ORDER BY total DESC
        """
        cur.execute(sql)
        return cur.fetchall()

    def get_js_executors(self, limit=20): 
        conn = self.get_conn()
        cur = conn.cursor()
        # We explicitly look for the js_confirm.gif trapdoor.
        # We dropped mathjax and d3.js because they don't prove CAPTCHA execution.
        sql = f"""
            SELECT ua.value, SUM(logs.count) as total
            FROM daily_logs logs
            JOIN user_agents ua ON logs.ua_id = ua.id
            JOIN paths p ON logs.path_id = p.id
            WHERE p.value LIKE '%js_confirm.gif%'
              {self._BROWSER_FILTER}  /* Apply Noise Filter */
            GROUP BY ua.id
            ORDER BY total DESC
            LIMIT ?
        """
        cur.execute(sql, (limit,))
        return cur.fetchall()


    def get_markdown_readers(self, limit=20):
        conn = self.get_conn()
        cur = conn.cursor()
        # Filtered: Drop the noise (like local Ubuntu testing) so the orange Known Bots bubble to the top.
        sql = f"""
            SELECT ua.value, SUM(logs.count) as total
            FROM daily_logs logs
            JOIN user_agents ua ON logs.ua_id = ua.id
            JOIN paths p ON logs.path_id = p.id
            WHERE p.value LIKE '%.md?src=%'
              {self._BROWSER_FILTER}  /* Apply Noise Filter */
            GROUP BY ua.id
            ORDER BY total DESC
            LIMIT ?
        """
        cur.execute(sql, (limit,))
        return cur.fetchall()

    def get_md_routing_agents(self, limit=30):
        """Fetches the AI Vanguard using specific routing parameters."""
        conn = self.get_conn()
        cur = conn.cursor()
        sql = f"""
            SELECT 
                CASE 
                    WHEN p.value LIKE '%src=a+href%' THEN 'Hyperlink'
                    WHEN p.value LIKE '%src=link+rel%' THEN 'Head Tag'
                    WHEN p.value LIKE '%src=llms.txt%' THEN 'Manifest'
                    ELSE 'Unknown'
                END as ingestion_method,
                ua.value as agent,
                SUM(l.count) as total_reads
            FROM daily_logs l
            JOIN paths p ON l.path_id = p.id
            JOIN user_agents ua ON l.ua_id = ua.id
            WHERE p.value LIKE '%.md?src=%'
              AND p.value NOT LIKE '%src=content_neg%'
              {self._BROWSER_FILTER}
            GROUP BY ingestion_method, ua.id
            ORDER BY ingestion_method ASC, total_reads DESC
            LIMIT ?
        """
        cur.execute(sql, (limit,))
        return cur.fetchall()

    def get_content_neg_agents(self, limit=30):
        """Fetches the bleeding-edge bots using HTTP Accept headers."""
        conn = self.get_conn()
        cur = conn.cursor()
        # Note: This specifically uses the newer 'telemetry' table per your SQL
        sql = """
            SELECT ua.value as agent, SUM(t.count) as total_reads
            FROM telemetry t
            JOIN paths p ON t.path_id = p.id
            JOIN user_agents ua ON t.ua_id = ua.id
            WHERE p.value LIKE '%src=content_neg%'
            GROUP BY ua.id
            ORDER BY total_reads DESC
            LIMIT ?
        """
        cur.execute(sql, (limit,))
        return cur.fetchall()

# Global Instance
db = HoneyDB()
