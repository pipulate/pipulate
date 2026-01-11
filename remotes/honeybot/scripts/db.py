import sqlite3
import datetime
from pathlib import Path


# Shared Intelligence
KNOWN_BOTS = """\
ClaudeBot
GPTBot
OAI-SearchBot
PerplexityBot
Amazonbot
Googlebot
bingbot
meta-externalagent
Applebot
Aliyun
Yandex
AhrefsBot
DataForSeoBot
SemrushBot
DotBot
LinkupBot
botify
PetalBot
Bytespider
Barkrowler
SeekportBot
MJ12bot
Baiduspider
SeznamBot
ChatGPT-User
Perplexity-User
DuckAssistBot
Qwantbot
AwarioBot
GenomeCrawlerd
IbouBot
Sogou
python-requests
python-httpx
Go-http-client
Wget
curl
SERankingBacklinksBot
""".splitlines()

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

    def log_request(self, ip, ua, path, status, date_str=None):
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
        AND ua.value NOT LIKE 'python-httpx%'
        AND ua.value NOT LIKE 'Go-http-client%'
        AND NOT (
            ua.value LIKE 'Mozilla%' 
            AND ua.value NOT LIKE '%compatible%' 
            AND (
                ua.value LIKE '%Windows NT%' OR 
                ua.value LIKE '%Macintosh%' OR 
                ua.value LIKE '%X11; Linux%' OR
                ua.value LIKE '%iPhone%' OR
                ua.value LIKE '%Android%'
            )
        )
    """

    def get_js_executors(self, limit=20): # Increased default limit slightly
        conn = self.get_conn()
        cur = conn.cursor()
        sql = f"""
            SELECT ua.value, SUM(logs.count) as total
            FROM daily_logs logs
            JOIN user_agents ua ON logs.ua_id = ua.id
            JOIN paths p ON logs.path_id = p.id
            WHERE (p.value LIKE '%mathjax%' OR p.value LIKE '%d3.v7.min.js%')
              AND p.value NOT LIKE '%.html'
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
        sql = f"""
            SELECT ua.value, SUM(logs.count) as total
            FROM daily_logs logs
            JOIN user_agents ua ON logs.ua_id = ua.id
            JOIN paths p ON logs.path_id = p.id
            WHERE p.value LIKE '%.md'
              {self._BROWSER_FILTER} /* Apply Noise Filter */
            GROUP BY ua.id
            ORDER BY total DESC
            LIMIT ?
        """
        cur.execute(sql, (limit,))
        return cur.fetchall()


# Global Instance
db = HoneyDB()
