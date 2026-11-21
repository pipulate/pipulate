import re
import sqlite3
import datetime
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit


INTEL_PATH = Path(__file__).resolve().parent / "bot_intel.json"

with open(INTEL_PATH, "r") as f:
    BOT_INTEL = json.load(f)

# Shared Intelligence automatically generated from JSON
KNOWN_BOTS = list(BOT_INTEL["seen"].keys())

INTERNAL_DOMAINS = frozenset({
    "mikelev.in", "pipulate.com", "pipulate.org", "npvg.org", "lpvg.org", "qamy.ai",
    "levinix.org", "levinix.com", "levinux.com", "sunpug.io", "guerillatech.com",
    "rfc9110.org", "rfc9110.com", "rfc9110.io", "rfc9111.io", "rfc9111.com", "rfc9111.org",
    "mike-levin.com", "mikelevinseo.com",
})
_ALLOWED_REF_QUERY_KEYS = frozenset({"id", "v", "q", "query", "t", "topic", "thread", "item"})
_STATIC_SUBRESOURCE_RE = re.compile(
    r"(?:^/api/telemetry/js_confirm\.gif$|\.(?:css|js|mjs|map|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|eot)(?:$|\?))",
    re.IGNORECASE,
)
_PIRATE_TARGET_RE = re.compile(
    r"(?:/wp-(?:admin|login|content|includes)|/xmlrpc\.php|/\.(?:env|git|aws)|/phpmyadmin|\.(?:php[0-9]?|asp|aspx|jsp|cgi|env|sql|bak)(?:$|\?|/))",
    re.IGNORECASE,
)


def _is_internal_or_invalid_host(host: str) -> bool:
    h = (host or "").strip().lower().rstrip(".").removeprefix("www.")
    if not h or h == "localhost" or h.endswith(".local") or ":" in h or "." not in h or re.match(r"^\d+(?:\.\d+)+$", h):
        return True
    return any(h == d or h.endswith("." + d) for d in INTERNAL_DOMAINS)


_MULTI_PART_SUFFIXES = frozenset({
    "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au", "co.jp",
    "com.br", "com.mx", "co.in", "co.nz", "co.za", "com.sg", "github.io", "gitlab.io",
    "substack.com", "bsky.social",
})


def extract_registered_domain(host: str) -> str:
    """Collapse subdomains/packages to registered apex (e.g. old.reddit.com -> reddit.com)."""
    h = (host or "").strip().lower().rstrip(".").removeprefix("www.")
    parts = [p for p in h.split(".") if p]
    if len(parts) <= 2:
        return h
    if parts[0] in ("com", "org", "net") and (len(parts[-1]) > 3 or "android" in parts):
        return f"{parts[1]}.{parts[0]}"
    return ".".join(parts[-3:] if f"{parts[-2]}.{parts[-1]}" in _MULTI_PART_SUFFIXES else parts[-2:])


def normalize_external_referrer(referrer: str | None, raw_path: str = "") -> tuple[str, str] | None:
    """Return (canonical_referrer, ref_host) for external referrals, or None for internal/noise."""
    raw = (referrer or "").replace(r"\x22", "").strip().strip('"').strip()
    if raw.lower().startswith("utm:"):
        src = raw[4:].strip().lower().rstrip(".").removeprefix("www.")
        if re.match(r"^[a-z0-9._-]{2,80}$", src) and not ("." in src and _is_internal_or_invalid_host(src)):
            return f"utm:{src}", src
        return None
    if not raw or raw == "-":
        if "?" in (raw_path or ""):
            for k, v in parse_qsl(raw_path.split("?", 1)[1], keep_blank_values=False):
                if k.lower() == "utm_source":
                    return normalize_external_referrer(f"utm:{v}", "")
        return None
    if raw.lower().startswith("android-app://"):
        pkg = raw[14:].split("/", 1)[0].strip().lower()
        return (f"android-app://{pkg}", pkg) if re.match(r"^[a-z0-9_]+(?:\.[a-z0-9_]+)+$", pkg) else None
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    host = (parts.hostname or "").strip().lower().rstrip(".").removeprefix("www.")
    if parts.scheme.lower() not in ("http", "https") or _is_internal_or_invalid_host(host):
        return None
    clean_p = re.sub(r"/{2,}", "/", parts.path or "/")
    clean_p = clean_p if clean_p.startswith("/") else "/" + clean_p
    kept_q = [(k.lower(), v.strip()[:80]) for k, v in parse_qsl(parts.query, keep_blank_values=False) if k.lower() in _ALLOWED_REF_QUERY_KEYS and v.strip()]
    if (host.startswith("google.") or ".google." in host) and clean_p in ("/url", "/search") and not kept_q:
        clean_p = "/"
    clean_p = clean_p.rstrip("/") if len(clean_p) > 1 and clean_p.endswith("/") else clean_p
    canon = f"https://{host}{clean_p}" + (f"?{urlencode(kept_q)}" if kept_q else "")
    return canon[:200], host

# The single file that holds the truth
DB_PATH = Path("/home/mike/www/mikelev.in/honeybot.db")

class HoneyDB:
    def __init__(self, db_path=DB_PATH, read_only=False):
        import os
        if db_path != ":memory:" and not Path(db_path).parent.exists():
            db_path = ":memory:"
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

        # 3b. Script-Kiddie Pirate & IDS Footprint Table (VPN-safe IP + UA + Path + Domain profiling)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pirate_logs (
                date TEXT,
                ip_id INTEGER,
                ua_id INTEGER,
                path_id INTEGER,
                domain_id INTEGER,
                status INTEGER,
                count INTEGER DEFAULT 1,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (date, ip_id, ua_id, path_id, domain_id, status),
                FOREIGN KEY(ip_id) REFERENCES ips(id),
                FOREIGN KEY(ua_id) REFERENCES user_agents(id),
                FOREIGN KEY(path_id) REFERENCES paths(id),
                FOREIGN KEY(domain_id) REFERENCES domains(id)
            )
        """)
        # 4. Performance Indexes for Sub-Second Station-Break Reports & 5s HUD Refreshes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_daily_logs_path_id ON daily_logs(path_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_daily_logs_ua_id ON daily_logs(ua_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_served_md ON telemetry(served_md, accept_id, path_id)")
        rdl_cols = {r[1] for r in cur.execute("PRAGMA table_info(referrer_daily_logs)").fetchall()}
        if rdl_cols and "ref_apex" not in rdl_cols:
            cur.execute("DROP TABLE IF EXISTS referrer_daily_logs")
            cur.execute("DROP TABLE IF EXISTS external_referrers")
        cur.execute("CREATE TABLE IF NOT EXISTS external_referrers (referrer TEXT PRIMARY KEY, ref_host TEXT NOT NULL, ref_apex TEXT NOT NULL DEFAULT '', first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS referrer_radar (ref_apex TEXT NOT NULL, domain_id INTEGER NOT NULL, path_id INTEGER NOT NULL, first_referrer TEXT NOT NULL, last_referrer TEXT NOT NULL, first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP, total_count INTEGER DEFAULT 1, human_count INTEGER DEFAULT 0, bot_count INTEGER DEFAULT 0, PRIMARY KEY (ref_apex, domain_id, path_id), FOREIGN KEY(domain_id) REFERENCES domains(id), FOREIGN KEY(path_id) REFERENCES paths(id))")
        cur.execute("CREATE TABLE IF NOT EXISTS referrer_daily_logs (date TEXT NOT NULL, ref_apex TEXT NOT NULL, domain_id INTEGER NOT NULL, path_id INTEGER NOT NULL, sample_referrer TEXT NOT NULL, count INTEGER DEFAULT 1, human_count INTEGER DEFAULT 0, bot_count INTEGER DEFAULT 0, unique_ips INTEGER DEFAULT 1, last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (date, ref_apex, domain_id, path_id), FOREIGN KEY(domain_id) REFERENCES domains(id), FOREIGN KEY(path_id) REFERENCES paths(id))")
        cur.execute("CREATE TABLE IF NOT EXISTS referrer_daily_ip_gate (date TEXT NOT NULL, ref_apex TEXT NOT NULL, domain_id INTEGER NOT NULL, path_id INTEGER NOT NULL, ip_id INTEGER NOT NULL, PRIMARY KEY (date, ref_apex, domain_id, path_id, ip_id)) WITHOUT ROWID")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rfc9421_logs_ua_id ON rfc9421_logs(ua_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pirate_logs_ip_id ON pirate_logs(ip_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_referrer_radar_seen ON referrer_radar(first_seen DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_referrer_daily_date_path ON referrer_daily_logs(date, path_id)")
        cur.execute("CREATE TABLE IF NOT EXISTS daily_metrics (metric TEXT NOT NULL, dim TEXT NOT NULL DEFAULT 'all', day TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0, last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (metric, dim, day)) WITHOUT ROWID")
        cur.execute("CREATE TABLE IF NOT EXISTS daily_transitions (day TEXT NOT NULL, from_state TEXT NOT NULL, to_state TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0, last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (day, from_state, to_state)) WITHOUT ROWID")

        conn.commit()
        self.backfill_rfc9421_from_access_log()
        self.backfill_dns_audit()
        self.backfill_external_referrers()
        self.rollup_daily_metrics()

    def backfill_external_referrers(self):
        """One-time idempotent backfill of external_referrers, referrer_radar, & referrer_daily_logs."""
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            if (cur.execute("SELECT COUNT(*) FROM referrer_radar").fetchone() or [0])[0] > 0:
                return
            rows = cur.execute("SELECT id, value FROM referrers WHERE value IS NOT NULL AND value != '-' AND value != ''").fetchall()
            valid_refs = {int(rid): (*norm, extract_registered_domain(norm[1])) for rid, rval in rows if (norm := normalize_external_referrer(rval)) is not None}
            if not valid_refs:
                return
            dom_id, ref_ids, agg_daily, agg_radar, ref_bounds = self._get_or_create_id("domains", "mikelev.in"), list(valid_refs), {}, {}, {}
            for idx in range(0, len(ref_ids), 400):
                chunk = ref_ids[idx : idx + 400]
                sql = f"SELECT t.date, t.referrer_id, t.path_id, t.ip_id, p.value, ua.value, SUM(t.count) FROM telemetry t JOIN paths p ON t.path_id = p.id JOIN user_agents ua ON t.ua_id = ua.id JOIN ips i ON t.ip_id = i.id WHERE t.referrer_id IN ({','.join('?' for _ in chunk)}) AND i.value NOT LIKE '127.%' AND i.value NOT LIKE '10.%' AND i.value NOT LIKE '192.168.%' AND t.path_id IN (SELECT DISTINCT path_id FROM daily_logs WHERE status BETWEEN 200 AND 299) GROUP BY t.date, t.referrer_id, t.path_id, t.ip_id, ua.id"
                for d_str, rid, pid, ip_id, p_val, ua_val, cnt in cur.execute(sql, chunk).fetchall():
                    if _STATIC_SUBRESOURCE_RE.search(p_val or "") or _PIRATE_TARGET_RE.search(p_val or ""):
                        continue
                    canon_ref, r_host, r_apex = valid_refs[int(rid)]
                    r_pid = self._get_or_create_id("paths", p_val.split("?", 1)[0]) if "?" in (p_val or "") else int(pid)
                    c, is_hum = int(cnt or 0), self.is_likely_human_ua(ua_val)
                    b_cur = ref_bounds.get(canon_ref)
                    ref_bounds[canon_ref] = (r_host, r_apex, min(b_cur[2], d_str) if b_cur else d_str, max(b_cur[3], d_str) if b_cur else d_str)
                    rk, dk = (r_apex, dom_id, r_pid), (d_str, r_apex, dom_id, r_pid)
                    rc, dc = agg_radar.get(rk), agg_daily.get(dk)
                    agg_radar[rk] = (canon_ref if not rc or d_str < rc[2] else rc[0], canon_ref if not rc or d_str >= rc[3] else rc[1], min(rc[2], d_str) if rc else d_str, max(rc[3], d_str) if rc else d_str, (rc[4] if rc else 0) + c, (rc[5] if rc else 0) + (c if is_hum else 0), (rc[6] if rc else 0) + (0 if is_hum else c))
                    s_ref = canon_ref if (not dc or len(canon_ref) > len(dc[0])) else dc[0]
                    agg_daily[dk] = (s_ref, (dc[1] if dc else 0) + c, (dc[2] if dc else 0) + (c if is_hum else 0), (dc[3] if dc else 0) + (0 if is_hum else c), (dc[4] if dc else set()) | {int(ip_id)})
            conn.executemany("INSERT OR IGNORE INTO external_referrers (referrer, ref_host, ref_apex, first_seen, last_seen) VALUES (?, ?, ?, ?, ?)", [(r, h, ap, f_dt, l_dt) for r, (h, ap, f_dt, l_dt) in ref_bounds.items()])
            conn.executemany("INSERT OR REPLACE INTO referrer_radar (ref_apex, domain_id, path_id, first_referrer, last_referrer, first_seen, last_seen, total_count, human_count, bot_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [(ap, dm, p, fr, lr, fd, ld, tot, hum, bot) for (ap, dm, p), (fr, lr, fd, ld, tot, hum, bot) in agg_radar.items()])
            conn.executemany("INSERT OR REPLACE INTO referrer_daily_logs (date, ref_apex, domain_id, path_id, sample_referrer, count, human_count, bot_count, unique_ips) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [(d, ap, dm, p, sr, tot, hum, bot, len(ips)) for (d, ap, dm, p), (sr, tot, hum, bot, ips) in agg_daily.items()])
            conn.commit()
        except Exception:
            pass

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

    def log_request(self, ip, ua, path, status, date_str=None, referrer=None, accept=None, served_md=None, host=None, sig_agent=None, is_pirate=False):
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
        # 6. Handle Script-Kiddie Pirate & IDS Footprint Sidecar
        if is_pirate:
            dom_id_p = self._get_or_create_id('domains', (host or 'mikelev.in').lower().strip())
            sql_pirate = """
                INSERT INTO pirate_logs (date, ip_id, ua_id, path_id, domain_id, status, count)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(date, ip_id, ua_id, path_id, domain_id, status)
                DO UPDATE SET count = count + 1, last_updated = CURRENT_TIMESTAMP
            """
            conn.execute(sql_pirate, (date_str, ip_id, ua_id, path_id, dom_id_p, int(status)))

        # 7. Handle Normalized External Referrer Sidecar (Compound-Key Radar & Daily N/P Ledger)
        if not is_pirate and 200 <= int(status) < 300 and not _STATIC_SUBRESOURCE_RE.search(path or ""):
            norm_ref = normalize_external_referrer(referrer, path or "")
            if norm_ref is not None:
                canon_ref, ref_host = norm_ref
                ref_apex = extract_registered_domain(ref_host)
                dom_id_r = self._get_or_create_id("domains", (host or "mikelev.in").lower().strip())
                r_pid = self._get_or_create_id("paths", path.split("?", 1)[0]) if "?" in (path or "") else path_id
                is_hum = 1 if self.is_likely_human_ua(ua) else 0
                if getattr(self, "_ip_gate_date", None) != date_str:
                    conn.execute("DELETE FROM referrer_daily_ip_gate WHERE date < ?", (date_str,))
                    self._ip_gate_date = date_str
                new_ip = 1 if conn.execute("INSERT OR IGNORE INTO referrer_daily_ip_gate VALUES (?, ?, ?, ?, ?)", (date_str, ref_apex, dom_id_r, r_pid, ip_id)).rowcount > 0 else 0
                conn.execute("INSERT INTO external_referrers (referrer, ref_host, ref_apex) VALUES (?, ?, ?) ON CONFLICT(referrer) DO UPDATE SET last_seen = CURRENT_TIMESTAMP", (canon_ref, ref_host, ref_apex))
                conn.execute("INSERT INTO referrer_radar (ref_apex, domain_id, path_id, first_referrer, last_referrer, total_count, human_count, bot_count) VALUES (?, ?, ?, ?, ?, 1, ?, ?) ON CONFLICT(ref_apex, domain_id, path_id) DO UPDATE SET last_referrer = excluded.last_referrer, last_seen = CURRENT_TIMESTAMP, total_count = total_count + 1, human_count = human_count + excluded.human_count, bot_count = bot_count + excluded.bot_count", (ref_apex, dom_id_r, r_pid, canon_ref, canon_ref, is_hum, 1 - is_hum))
                conn.execute("INSERT INTO referrer_daily_logs (date, ref_apex, domain_id, path_id, sample_referrer, count, human_count, bot_count, unique_ips) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?) ON CONFLICT(date, ref_apex, domain_id, path_id) DO UPDATE SET sample_referrer = CASE WHEN length(excluded.sample_referrer) > length(referrer_daily_logs.sample_referrer) THEN excluded.sample_referrer ELSE referrer_daily_logs.sample_referrer END, count = count + 1, human_count = human_count + excluded.human_count, bot_count = bot_count + excluded.bot_count, unique_ips = unique_ips + excluded.unique_ips, last_updated = CURRENT_TIMESTAMP", (date_str, ref_apex, dom_id_r, r_pid, canon_ref, is_hum, 1 - is_hum, new_ip))

        self._record_request_funnel_metrics(date_str, ip, ua, path, status, referrer, served_md, host, is_pirate)
        conn.commit()
        if ua and ("Googlebot" in ua or "bingbot" in ua.lower() or "Applebot" in ua):
            self.verify_fcrdns_ip(ip, ua)

    def is_likely_human_ua(self, ua_str: str | None) -> bool:
        """True when User-Agent matches a standard interactive browser rather than a bot or CLI client."""
        s = (ua_str or "").strip()
        if not s or "HeadlessChrome" in s or "Google-InspectionTool" in s or "Nexus 5X" in s or self._detect_rollup_key(s) is not None:
            return False
        return s.startswith("Mozilla/5.0 ") and any(k in s for k in ("AppleWebKit", "Gecko", "Windows NT", "Macintosh", "X11", "Android", "iPhone", "iPad"))

    def get_external_referrals(self, days: int = 30, limit: int = 50, humans_only: bool = False):
        """Return (sample_referrer, ref_apex, domain, path, hits, human_hits, bot_hits, first_seen, last_seen, unique_ips)."""
        cutoff = (datetime.date.today() - datetime.timedelta(days=max(1, int(days)))).isoformat()
        hum_clause = "AND rdl.human_count > 0" if humans_only else ""
        sql = f"SELECT MAX(rdl.sample_referrer), rdl.ref_apex, d.value, p.value, SUM(rdl.count) as hits, SUM(rdl.human_count), SUM(rdl.bot_count), rr.first_seen, rr.last_seen, SUM(rdl.unique_ips) FROM referrer_daily_logs rdl JOIN referrer_radar rr ON (rdl.ref_apex = rr.ref_apex AND rdl.domain_id = rr.domain_id AND rdl.path_id = rr.path_id) JOIN domains d ON rdl.domain_id = d.id JOIN paths p ON rdl.path_id = p.id WHERE rdl.date >= ? {hum_clause} GROUP BY rdl.ref_apex, rdl.domain_id, rdl.path_id ORDER BY hits DESC, SUM(rdl.unique_ips) DESC LIMIT ?"
        return self.get_conn().execute(sql, (cutoff, int(limit))).fetchall()

    def get_referrer_radar(self, days: int = 30, limit: int = 30, humans_only: bool = False):
        """Return newest (ref_apex, domain, path, hits, human_hits, bot_hits, unique_ips, first_seen, last_seen, first_referrer)."""
        cutoff = (datetime.date.today() - datetime.timedelta(days=max(1, int(days)))).isoformat()
        hum_clause = "AND rr.human_count > 0" if humans_only else ""
        sql = f"SELECT rr.ref_apex, d.value, p.value, COALESCE(SUM(rdl.count), rr.total_count), COALESCE(SUM(rdl.human_count), rr.human_count), COALESCE(SUM(rdl.bot_count), rr.bot_count), COALESCE(SUM(rdl.unique_ips), 1), rr.first_seen, rr.last_seen, rr.first_referrer FROM referrer_radar rr JOIN domains d ON rr.domain_id = d.id JOIN paths p ON rr.path_id = p.id LEFT JOIN referrer_daily_logs rdl ON (rdl.ref_apex = rr.ref_apex AND rdl.domain_id = rr.domain_id AND rdl.path_id = rr.path_id AND rdl.date >= ?) WHERE substr(rr.first_seen, 1, 10) >= ? {hum_clause} GROUP BY rr.ref_apex, rr.domain_id, rr.path_id ORDER BY rr.first_seen DESC, rr.rowid DESC LIMIT ?"
        return self.get_conn().execute(sql, (cutoff, cutoff, int(limit))).fetchall()

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
            AND ua.value NOT LIKE '%HeadlessChrome%'
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
        "ChatGPT-User",
        "Claude-User",
        "ClaudeBot",
        "claude-code",
        "Claude-Web",
        "GoogleOther",
        "Google-InspectionTool",
        "Storebot-Google",
        "Google-Extended",
        "Googlebot",
        "ShapBot",
        "KeenableBot",
        "ExaSearchBot",
        "ExaUser",
        "PerplexityBot",
        "Perplexity-User",
        "Amazonbot",
        "Applebot",
        "bingbot",
        "YandexBot",
        "PetalBot",
        "AhrefsBot",
        "SemrushBot",
        "DotBot",
        "MJ12bot",
        "DataForSeoBot",
        "Barkrowler",
        "DuckAssistBot",
        "facebookexternalhit",
        "FacebookBot",
        "Twitterbot",
        "LinkedInBot",
        "Discordbot",
        "TelegramBot",
        "Slackbot",
        "HeadlessChrome",
        "Bytespider",
        "axios",
        "curl/",
        "wget/",
        "python-requests",
    )
    _COMPAT_BOT_RE = re.compile(r"compatible;\s*([A-Za-z0-9._-]+)", re.IGNORECASE)
    _KEYWORD_BOT_RE = re.compile(
        r"\b([A-Za-z0-9._-]*(?:bot|spider|crawler|agent|radar|worker|mcp|research|scraper|fetcher|inspector|archiver|httpx|requests|axios|curl|wget|aiohttp|urllib|go-http-client|python)[A-Za-z0-9._-]*)",
        re.IGNORECASE,
    )
    _LEADING_AGENT_RE = re.compile(r"^([A-Za-z0-9._-]+?)(?:/[\d.]+|\s+\(|\s*$)")

    def _detect_rollup_key(self, clean_ua: str):
        """Return a canonical lowercase bot identity key so recurring bots roll up into one HUD row."""
        s = (clean_ua or "").strip()
        if not s or s == "-":
            return None
        s_lower = s.lower()
        for tok in self._ROLLUP_BOT_TOKENS:
            if tok.lower() in s_lower:
                return tok.lower().rstrip("/")
        for bot_name in sorted(KNOWN_BOTS, key=len, reverse=True):
            if bot_name in s:
                m_ext = re.search(rf"({re.escape(bot_name)}[A-Za-z0-9._-]*)", s)
                raw_tok = m_ext.group(1).strip(";/() ") if m_ext else bot_name
                return re.sub(r"[-_]+v?\d+(?:\.\d+)+$", "", raw_tok).lower()
        for m in self._COMPAT_BOT_RE.finditer(s):
            tok = m.group(1).strip(";/() ")
            if tok and tok.upper() not in ("MSIE", "MOZILLA"):
                return re.sub(r"[-_]+v?\d+(?:\.\d+)+$", "", tok).lower()
        if not s.startswith(("Mozilla/", "AppleWebKit/", "(")):
            m_lead = self._LEADING_AGENT_RE.match(s)
            if m_lead:
                return re.sub(r"[-_]+v?\d+(?:\.\d+)+$", "", m_lead.group(1).strip()).lower()
        m_kw = self._KEYWORD_BOT_RE.search(s)
        if m_kw:
            tok = m_kw.group(1).strip(";/() ")
            if tok.lower() not in ("mozilla", "applewebkit", "safari", "chrome", "gecko", "khtml", "mobile"):
                return re.sub(r"[-_]+v?\d+(?:\.\d+)+$", "", tok).lower()
        return None

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
            matched_token = self._detect_rollup_key(clean_ua)
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

    _CLI_PIPE_UA_RE = re.compile(r"^(?:curl|Wget|fetch\s+libfetch|sunpug-installer)/", re.IGNORECASE)
    _SOCIAL_IN_APEX = frozenset({"t.co", "x.com", "twitter.com", "linkedin.com", "lnkd.in", "reddit.com", "facebook.com", "bsky.app", "news.ycombinator.com", "lobste.rs"})

    def record_daily_metric(self, metric: str, dim: str = "all", amount: int = 1, day: str | None = None, commit: bool = True) -> None:
        """Increment a compact daily directional counter (1 row per metric + dim + UTC day)."""
        d_str = day or datetime.date.today().isoformat()
        conn = self.get_conn()
        conn.execute("INSERT INTO daily_metrics (metric, dim, day, count) VALUES (?, ?, ?, ?) ON CONFLICT(metric, dim, day) DO UPDATE SET count = count + excluded.count, last_updated = CURRENT_TIMESTAMP", (str(metric), str(dim or "all"), d_str, int(amount)))
        if commit:
            conn.commit()

    def record_daily_transition(self, from_state: str, to_state: str, amount: int = 1, day: str | None = None, commit: bool = True) -> None:
        """Increment a daily Markov funnel transition edge (from_state -> to_state)."""
        d_str = day or datetime.date.today().isoformat()
        conn = self.get_conn()
        conn.execute("INSERT INTO daily_transitions (day, from_state, to_state, count) VALUES (?, ?, ?, ?) ON CONFLICT(day, from_state, to_state) DO UPDATE SET count = count + excluded.count, last_updated = CURRENT_TIMESTAMP", (d_str, str(from_state), str(to_state), int(amount)))
        if commit:
            conn.commit()

    def _record_request_funnel_metrics(self, date_str, ip, ua, path, status, referrer, served_md, host, is_pirate) -> None:
        """Update daily_metrics and daily_transitions inside log_request's active transaction."""
        ip_s = str(ip or "")
        if ip_s.startswith(("127.", "10.", "192.168.")):
            return
        dom = (host or "mikelev.in").strip().lower().rstrip(".").removeprefix("www.") or "mikelev.in"
        raw_p = str(path or "/")
        clean_p = raw_p.split("?", 1)[0]
        st = int(status or 0)
        ua_s = str(ua or "")
        ua_low = ua_s.lower()
        if is_pirate or _PIRATE_TARGET_RE.search(clean_p):
            self.record_daily_metric("ids_pirate", "418" if st == 418 else f"{max(0, st) // 100}xx", 1, date_str, commit=False)
            return
        if 200 <= st < 400 and (clean_p == "/discord" or clean_p.startswith("/go/")):
            slug = "discord" if clean_p == "/discord" else (clean_p[4:].strip("/") or "root")[:40]
            self.record_daily_metric("social_out", slug, 1, date_str, commit=False)
            self.record_daily_transition(f"visit:{dom}", f"social:{slug}", 1, date_str, commit=False)
            return
        if not (200 <= st < 300):
            return
        if clean_p in ("/brain.zip", "/book.zip"):
            arch = clean_p.lstrip("/")
            self.record_daily_metric("archive_dl", arch, 1, date_str, commit=False)
            if self.is_likely_human_ua(ua_s):
                self.record_daily_transition(f"visit:{dom}", f"dl:{arch}", 1, date_str, commit=False)
            return
        is_scanner = any(b in ua_low for b in ("qlyzebot", "google-safety", "bot", "spider", "crawler"))
        if not is_scanner and (clean_p in ("/manifest.txt", "/key.rot") or "src=install" in raw_p or ua_low.startswith("sunpug-installer/")):
            self.record_daily_metric("curl_exec", dom, 1, date_str, commit=False)
            self.record_daily_transition(f"airlock:{dom}", f"exec:{dom}", 1, date_str, commit=False)
            return
        if not is_scanner and self._CLI_PIPE_UA_RE.search(ua_s) and clean_p in ("/", "/install.sh"):
            self.record_daily_metric("curl_airlock", dom, 1, date_str, commit=False)
            self.record_daily_transition(f"door:{dom}", f"airlock:{dom}", 1, date_str, commit=False)
            return
        if _STATIC_SUBRESOURCE_RE.search(raw_p):
            return
        if str(served_md) == "1":
            self.record_daily_metric("md_negotiated", dom, 1, date_str, commit=False)
        if self.is_likely_human_ua(ua_s):
            self.record_daily_metric("human_visit", dom, 1, date_str, commit=False)
            norm_ref = normalize_external_referrer(referrer, raw_p)
            if norm_ref is not None:
                ap = extract_registered_domain(norm_ref[1])
                if ap in ("youtube.com", "youtu.be"):
                    self.record_daily_metric("yt_referral_human", dom, 1, date_str, commit=False)
                    self.record_daily_transition("ref:youtube", f"visit:{dom}", 1, date_str, commit=False)
                elif ap in self._SOCIAL_IN_APEX:
                    self.record_daily_metric("social_in", ap, 1, date_str, commit=False)
                    self.record_daily_transition(f"ref:{ap}", f"visit:{dom}", 1, date_str, commit=False)

    def rollup_daily_metrics(self, force: bool = False) -> int:
        """Idempotently backfill daily_metrics from existing normalized Honeybot tables when empty."""
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            if not force and (cur.execute("SELECT COUNT(*) FROM daily_metrics").fetchone() or [0])[0] > 0:
                return 0
            queries = (
                "INSERT OR REPLACE INTO daily_metrics (metric, dim, day, count) SELECT 'ids_pirate', CASE WHEN status = 418 THEN '418' ELSE CAST(status / 100 AS TEXT) || 'xx' END, date, SUM(count) FROM pirate_logs GROUP BY 1, 2, 3",
                "INSERT OR REPLACE INTO daily_metrics (metric, dim, day, count) SELECT 'md_negotiated', 'mikelev.in', t.date, SUM(t.count) FROM telemetry t JOIN ips i ON t.ip_id = i.id WHERE t.served_md = 1 AND i.value NOT LIKE '127.%' AND i.value NOT LIKE '10.%' AND i.value NOT LIKE '192.168.%' GROUP BY t.date",
                "INSERT OR REPLACE INTO daily_metrics (metric, dim, day, count) SELECT CASE WHEN p.value IN ('/brain.zip', '/book.zip') THEN 'archive_dl' ELSE 'social_out' END, CASE WHEN p.value IN ('/brain.zip', '/book.zip') THEN ltrim(p.value, '/') WHEN p.value = '/discord' THEN 'discord' ELSE substr(p.value, 5) END, l.date, SUM(l.count) FROM daily_logs l JOIN paths p ON l.path_id = p.id JOIN ips i ON l.ip_id = i.id WHERE ((p.value IN ('/brain.zip', '/book.zip') AND l.status BETWEEN 200 AND 299) OR ((p.value = '/discord' OR p.value LIKE '/go/%') AND l.status BETWEEN 200 AND 399)) AND i.value NOT LIKE '127.%' AND i.value NOT LIKE '10.%' AND i.value NOT LIKE '192.168.%' GROUP BY 1, 2, 3",
                "INSERT OR REPLACE INTO daily_metrics (metric, dim, day, count) SELECT 'curl_airlock', d.value, ddl.date, SUM(ddl.count) FROM domain_daily_logs ddl JOIN domains d ON ddl.domain_id = d.id JOIN paths p ON ddl.path_id = p.id JOIN user_agents ua ON ddl.ua_id = ua.id WHERE ddl.status BETWEEN 200 AND 299 AND p.value IN ('/', '/install.sh') AND (ua.value LIKE 'curl/%' OR ua.value LIKE 'Wget/%') GROUP BY d.value, ddl.date",
                "INSERT OR REPLACE INTO daily_metrics (metric, dim, day, count) SELECT 'curl_exec', d.value, ddl.date, SUM(ddl.count) FROM domain_daily_logs ddl JOIN domains d ON ddl.domain_id = d.id JOIN paths p ON ddl.path_id = p.id JOIN user_agents ua ON ddl.ua_id = ua.id WHERE ddl.status BETWEEN 200 AND 299 AND (p.value IN ('/manifest.txt', '/key.rot') OR p.value LIKE '%src=install%') AND lower(ua.value) NOT LIKE '%bot%' GROUP BY d.value, ddl.date",
                "INSERT OR REPLACE INTO daily_metrics (metric, dim, day, count) SELECT CASE WHEN rdl.ref_apex IN ('youtube.com', 'youtu.be') THEN 'yt_referral_human' ELSE 'social_in' END, CASE WHEN rdl.ref_apex IN ('youtube.com', 'youtu.be') THEN d.value ELSE rdl.ref_apex END, rdl.date, SUM(rdl.human_count) FROM referrer_daily_logs rdl JOIN domains d ON rdl.domain_id = d.id WHERE rdl.human_count > 0 AND rdl.ref_apex IN ('youtube.com', 'youtu.be', 't.co', 'x.com', 'twitter.com', 'linkedin.com', 'lnkd.in', 'reddit.com', 'facebook.com', 'bsky.app', 'news.ycombinator.com', 'lobste.rs') GROUP BY 1, 2, 3",
            )
            for q in queries:
                cur.execute(q)
            conn.commit()
            return int((cur.execute("SELECT COUNT(*) FROM daily_metrics").fetchone() or [0])[0])
        except Exception:
            return 0

    def get_daily_series(self, metric: str, dim: str = "all", days: int = 14, end_date: str | None = None) -> list[tuple[str, int]]:
        """Return a zero-filled contiguous [(YYYY-MM-DD, count), ...] daily series for honest OLS slopes."""
        end_d = datetime.date.fromisoformat(end_date) if end_date else datetime.date.today()
        n_days = max(1, int(days))
        start_d = end_d - datetime.timedelta(days=n_days - 1)
        span = [(start_d + datetime.timedelta(days=i)).isoformat() for i in range(n_days)]
        rows = self.get_conn().execute("SELECT day, COALESCE(SUM(count), 0) FROM daily_metrics WHERE metric = ? AND (? = '*' OR dim = ?) AND day BETWEEN ? AND ? GROUP BY day", (str(metric), str(dim), str(dim), span[0], span[-1])).fetchall()
        by_day = {str(d): int(c or 0) for d, c in rows}
        return [(d, by_day.get(d, 0)) for d in span]

    def get_curl_airlock_split(self, door: str = "sunpug.io", days: int = 14, end_date: str | None = None) -> dict:
        """Separate Stage-1 curl|less inspection from Stage-2 curl|bash execution for a Sun Pug door (or '*')."""
        s1 = self.get_daily_series("curl_airlock", dim=door, days=days, end_date=end_date)
        s2 = self.get_daily_series("curl_exec", dim=door, days=days, end_date=end_date)
        return {"door": door, "airlock": s1, "exec": s2, "inspect_only": [(d, max(0, a - e)) for (d, a), (_, e) in zip(s1, s2)]}

# Global Instance
db = HoneyDB()
