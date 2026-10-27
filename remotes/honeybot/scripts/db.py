import sqlite3
import datetime
import json
from pathlib import Path


INTEL_PATH = Path(__file__).resolve().parent / "bot_intel.json"

with open(INTEL_PATH, "r") as f:
    BOT_INTEL = json.load(f)

# Shared Intelligence automatically generated from JSON
KNOWN_BOTS = list(BOT_INTEL["seen"].keys())

# The single file that holds the truth
DB_PATH = Path("/home/mike/www/mikelev.in/honeybot.db")

class HoneyDB:
    def __init__(self, db_path=DB_PATH, read_only=False):
        import os
        self.db_path = db_path
        self.conn = None
        if not read_only and os.environ.get("HONEYBOT_DB_READONLY") != "1":
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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS domains (
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

        # --- MULTI-TENANT DOMAIN FACT TABLE (SIDECAR) ---
        cur.execute("""
            CREATE TABLE IF NOT EXISTS domain_daily_logs (
                date TEXT,
                domain_id INTEGER,
                path_id INTEGER,
                ua_id INTEGER,
                status INTEGER,
                count INTEGER DEFAULT 1,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (date, domain_id, path_id, ua_id, status),
                FOREIGN KEY(domain_id) REFERENCES domains(id),
                FOREIGN KEY(path_id) REFERENCES paths(id),
                FOREIGN KEY(ua_id) REFERENCES user_agents(id)
            )
        """)

        # --- RFC 9421 WEB BOT AUTH TABLES ---
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sig_agents (
                id INTEGER PRIMARY KEY,
                value TEXT UNIQUE,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rfc9421_logs (
                date TEXT,
                ip_id INTEGER,
                ua_id INTEGER,
                sig_id INTEGER,
                count INTEGER DEFAULT 1,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (date, ip_id, ua_id, sig_id)
            )
        """)

        # --- REVERSE DNS (FCrDNS) BOT VERIFICATION TABLE ---
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dns_audit (
                ip_id INTEGER PRIMARY KEY,
                ptr_host TEXT,
                fcrdns_ok INTEGER DEFAULT 0,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        self.backfill_rfc9421_from_access_log()
        self.backfill_dns_audit()

    def verify_fcrdns_ip(self, ip_str, ua_str):
        """Verify Forward-Confirmed Reverse DNS (FCrDNS) for major crawlers (Googlebot, bingbot, Applebot)."""
        import socket
        ua = ua_str or ""
        expected_suffixes = None
        if "Googlebot" in ua or "GoogleOther" in ua:
            expected_suffixes = (".googlebot.com", ".google.com", ".googleusercontent.com")
        elif "bingbot" in ua.lower():
            expected_suffixes = (".search.msn.com",)
        elif "Applebot" in ua:
            expected_suffixes = (".applebot.apple.com",)
        if not expected_suffixes:
            return None
        try:
            ip_id = self._get_or_create_id("ips", ip_str)
            if not ip_id:
                return None
            conn = self.get_conn()
            cur = conn.cursor()
            cur.execute("SELECT fcrdns_ok FROM dns_audit WHERE ip_id = ?", (ip_id,))
            row = cur.fetchone()
            if row is not None:
                return bool(row[0])
            old_to = socket.getdefaulttimeout()
            socket.setdefaulttimeout(1.5)
            try:
                ptr_host = socket.gethostbyaddr(ip_str)[0].rstrip(".").lower()
                fcrdns_ok = 0
                if ptr_host.endswith(expected_suffixes):
                    fwd_ips = {ai[4][0] for ai in socket.getaddrinfo(ptr_host, None)}
                    if ip_str in fwd_ips:
                        fcrdns_ok = 1
            except Exception:
                ptr_host = ""
                fcrdns_ok = 0
            finally:
                socket.setdefaulttimeout(old_to)
            conn.execute(
                "INSERT OR REPLACE INTO dns_audit (ip_id, ptr_host, fcrdns_ok) VALUES (?, ?, ?)",
                (ip_id, ptr_host, fcrdns_ok),
            )
            conn.commit()
            return bool(fcrdns_ok)
        except Exception:
            return None

    def backfill_dns_audit(self):
        """Audit existing Googlebot/bingbot/Applebot IPs in daily_logs and telemetry via FCrDNS."""
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT i.id, i.value, ua.value
                FROM daily_logs l
                JOIN ips i ON l.ip_id = i.id
                JOIN user_agents ua ON l.ua_id = ua.id
                LEFT JOIN dns_audit d ON d.ip_id = i.id
                WHERE d.ip_id IS NULL
                  AND (ua.value LIKE '%Googlebot%' OR ua.value LIKE '%bingbot%' OR ua.value LIKE '%Applebot%')
                LIMIT 40
                """
            )
            for _, ip_val, ua_val in cur.fetchall():
                self.verify_fcrdns_ip(ip_val, ua_val)
        except Exception:
            pass

    def backfill_rfc9421_from_access_log(self, log_path="/var/log/nginx/access.log"):
        """One-time backfill of RFC 9421 Signature-Agent hits from access.log when rfc9421_logs is empty."""
        import re
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM rfc9421_logs")
            if (cur.fetchone() or [0])[0] > 0:
                return
            p = Path(log_path)
            if not p.is_file():
                return
            pat = re.compile(
                r'^(?P<ip>[\d\.]+) - - \[(?P<dt>\d{2}/[A-Za-z]{3}/\d{4}):.*?\] ".*?" \d+ \d+ ".*?" "(?P<ua>.*?)" .*?Sig:"(?P<sig>[^"]+)"'
            )
            date_str = datetime.date.today().isoformat()
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if 'Sig:"' not in line or 'Sig:"-"' in line:
                        continue
                    m = pat.search(line)
                    if not m:
                        continue
                    sig = m.group("sig").replace(r"\x22", '"').strip().strip('"').strip()
                    if not sig or sig == "-":
                        continue
                    ip_id = self._get_or_create_id("ips", m.group("ip"))
                    ua_id = self._get_or_create_id("user_agents", m.group("ua"))
                    sig_id = self._get_or_create_id("sig_agents", sig)
                    conn.execute(
                        """
                        INSERT INTO rfc9421_logs (date, ip_id, ua_id, sig_id, count)
                        VALUES (?, ?, ?, ?, 1)
                        ON CONFLICT(date, ip_id, ua_id, sig_id)
                        DO UPDATE SET count = count + 1, last_updated = CURRENT_TIMESTAMP
                        """,
                        (date_str, ip_id, ua_id, sig_id),
                    )
            conn.commit()
        except Exception:
            pass

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

    def log_request(self, ip, ua, path, status, date_str=None, referrer=None, accept=None, served_md=None, host=None, sig_agent=None):
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

        # 4. Handle Domain Multi-Tenancy Sidecar
        if host:
            dom_id = self._get_or_create_id('domains', host.lower().strip())
            sql_domain = """
                INSERT INTO domain_daily_logs (date, domain_id, path_id, ua_id, status, count)
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(date, domain_id, path_id, ua_id, status)
                DO UPDATE SET count = count + 1, last_updated = CURRENT_TIMESTAMP
            """
            conn.execute(sql_domain, (date_str, dom_id, path_id, ua_id, status))

        # 5. Handle RFC 9421 Web Bot Auth Signature-Agent Sidecar
        if sig_agent and sig_agent != "-":
            sig_id = self._get_or_create_id('sig_agents', sig_agent)
            sql_sig = """
                INSERT INTO rfc9421_logs (date, ip_id, ua_id, sig_id, count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(date, ip_id, ua_id, sig_id)
                DO UPDATE SET count = count + 1, last_updated = CURRENT_TIMESTAMP
            """
            conn.execute(sql_sig, (date_str, ip_id, ua_id, sig_id))

        conn.commit()
        if ua and ("Googlebot" in ua or "bingbot" in ua.lower() or "Applebot" in ua):
            self.verify_fcrdns_ip(ip, ua)

    def get_rfc9421_summary(self):
        """Return (distinct_sig_agents, total_signed_events) from rfc9421_logs."""
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT sig_id), COALESCE(SUM(count), 0) FROM rfc9421_logs")
        row = cur.fetchone()
        return (int(row[0] or 0), int(row[1] or 0)) if row else (0, 0)

    def get_new_user_agents_since(self, min_ua_id=0, limit=10):
        """Return (ua_id, ua_value, first_seen, total_hits) for bots discovered after min_ua_id."""
        conn = self.get_conn()
        cur = conn.cursor()
        sql = f"""
            SELECT ua.id, ua.value, ua.first_seen, COALESCE(SUM(l.count), 0) as hits
            FROM user_agents ua
            LEFT JOIN daily_logs l ON l.ua_id = ua.id
            WHERE ua.id > ?
              {self._BROWSER_FILTER}
            GROUP BY ua.id
            ORDER BY ua.id DESC
            LIMIT ?
        """
        cur.execute(sql, (int(min_ua_id), int(limit)))
        return cur.fetchall()

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

    _GOOGLEBOT_SPOOF_COND = """
        (
            (
                ua.value LIKE '%Googlebot%'
                AND i.value NOT LIKE '66.249.%'
                AND i.value NOT LIKE '64.233.%'
                AND i.value NOT LIKE '72.14.%'
                AND i.value NOT LIKE '74.125.%'
                AND i.value NOT LIKE '108.177.%'
                AND i.value NOT LIKE '142.250.%'
                AND i.value NOT LIKE '142.251.%'
                AND i.value NOT LIKE '172.217.%'
                AND i.value NOT LIKE '173.194.%'
                AND i.value NOT LIKE '192.178.%'
                AND i.value NOT LIKE '207.126.%'
                AND i.value NOT LIKE '209.85.%'
                AND i.value NOT LIKE '216.58.%'
                AND i.value NOT LIKE '216.239.%'
            )
            OR (
                (ua.value LIKE '%Googlebot%' OR ua.value LIKE '%bingbot%' OR ua.value LIKE '%Applebot%')
                AND i.id IN (SELECT ip_id FROM dns_audit WHERE fcrdns_ok = 0)
            )
        )
    """

    # Selective User-Agent rollup tokens: bots that rotate OS platform strings,
    # minor versions, or URL suffixes across many UA strings and would otherwise
    # crowd out other distinct bots in the HUD tables.
    _ROLLUP_BOT_TOKENS = (
        "meta-externalagent",
        "GPTBot",
        "meta-webindexer",
        "OAI-SearchBot",
        "Claude-User",
        "KeenableBot",
    )

    def _rollup_bot_rows(self, rows, limit=20):
        """Selectively roll up noisy multi-UA bots into their top UA with a [+N] prefix."""
        buckets = {}
        results = []
        for raw_agent, raw_total in rows:
            agent_str = str(raw_agent or "")
            count = int(raw_total or 0)
            is_spoof = agent_str.startswith("[SPOOFED-IP] ")
            is_verified = agent_str.startswith("[VERIFIED] ")
            clean_ua = agent_str
            for pfx in ("[SPOOFED-IP] ", "[VERIFIED] "):
                if clean_ua.startswith(pfx):
                    clean_ua = clean_ua[len(pfx):]
            matched_token = None
            clean_lower = clean_ua.lower()
            for tok in self._ROLLUP_BOT_TOKENS:
                if tok.lower() in clean_lower:
                    matched_token = tok.lower()
                    break
            if matched_token is None:
                results.append([agent_str, count, 0, is_spoof, is_verified, clean_ua])
                continue
            bkey = (is_spoof, matched_token)
            if bkey not in buckets:
                entry = [agent_str, count, 0, is_spoof, is_verified, clean_ua]
                buckets[bkey] = entry
                results.append(entry)
            else:
                entry = buckets[bkey]
                entry[1] += count
                entry[2] += 1
                if is_verified and not entry[3]:
                    entry[4] = True

        formatted = []
        for _, total, extra, is_spoof, is_verified, clean_ua in results:
            prefix = "[SPOOFED-IP] " if is_spoof else ("[VERIFIED] " if is_verified else "")
            rollup_tag = f"[+{extra}] " if extra > 0 else ""
            formatted.append((f"{prefix}{rollup_tag}{clean_ua}", total))
        formatted.sort(key=lambda item: item[1], reverse=True)
        return formatted[: int(limit)]

    def get_js_executors(self, limit=20): 
        conn = self.get_conn()
        cur = conn.cursor()
        # We explicitly look for the js_confirm.gif trapdoor.
        # Applies non-local IP filtering, [SPOOFED-IP] tagging, and selective bot rollup.
        sql = f"""
            SELECT
                CASE
                    WHEN {self._GOOGLEBOT_SPOOF_COND}
                    THEN '[SPOOFED-IP] ' || ua.value
                    WHEN ua.id IN (SELECT ua_id FROM rfc9421_logs)
                    THEN '[VERIFIED] ' || ua.value
                    ELSE ua.value
                END as agent,
                SUM(logs.count) as total
            FROM daily_logs logs
            JOIN ips i ON logs.ip_id = i.id
            JOIN user_agents ua ON logs.ua_id = ua.id
            JOIN paths p ON logs.path_id = p.id
            WHERE p.value LIKE '%js_confirm.gif%'
              AND i.value NOT LIKE '127.%'
              AND i.value NOT LIKE '10.%'
              AND i.value NOT LIKE '192.168.%'
              {self._BROWSER_FILTER}  /* Apply Noise Filter */
            GROUP BY agent
            ORDER BY total DESC
            LIMIT 500
        """
        cur.execute(sql)
        return self._rollup_bot_rows(cur.fetchall(), limit=limit)


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
        # Note: Strictly requires served_md=1, Accept: text/markdown, and non-local IPs
        sql = f"""
            SELECT
                CASE
                    WHEN {self._GOOGLEBOT_SPOOF_COND}
                    THEN '[SPOOFED-IP] ' || ua.value
                    WHEN ua.id IN (SELECT ua_id FROM rfc9421_logs)
                    THEN '[VERIFIED] ' || ua.value
                    ELSE ua.value
                END as agent,
                SUM(t.count) as total_reads
            FROM telemetry t
            JOIN ips i ON t.ip_id = i.id
            JOIN paths p ON t.path_id = p.id
            JOIN user_agents ua ON t.ua_id = ua.id
            JOIN accept_headers ah ON t.accept_id = ah.id
            WHERE t.served_md = 1
              AND ah.value LIKE '%text/markdown%'
              AND p.value LIKE '%src=content_neg%'
              AND i.value NOT LIKE '127.%'
              AND i.value NOT LIKE '10.%'
              AND i.value NOT LIKE '192.168.%'
              {self._BROWSER_FILTER}
            GROUP BY agent
            ORDER BY total_reads DESC
            LIMIT 500
        """
        cur.execute(sql)
        return self._rollup_bot_rows(cur.fetchall(), limit=limit)

# Global Instance
db = HoneyDB()
