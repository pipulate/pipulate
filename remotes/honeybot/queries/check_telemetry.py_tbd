#!/usr/bin/env python3
"""
📡 Telemetry Check
A simple diagnostic tool to verify the Accept Header and Markdown trapdoor logging.
"""

import sys
from pathlib import Path

# Add script dir to path to find db module
sys.path.append(str(Path(__file__).parent))
from db import db

def check_telemetry():
    conn = db.get_conn()
    cur = conn.cursor()
    
    print("\n=== 📡 TELEMETRY SENSOR CHECK ===\n")
    
    # 1. Total Records Check
    try:
        cur.execute("SELECT COUNT(*), SUM(count) FROM telemetry")
        row_count, total_hits = cur.fetchone()
        print(f"Unique Telemetry Signatures : {row_count or 0}")
        print(f"Total Telemetry Hits Logged : {total_hits or 0}\n")
    except Exception as e:
        print(f"⚠️ Error reading telemetry (Is the table created?): {e}")
        return

    if not row_count:
        print("⏳ No telemetry data found yet. Send some test curls!")
        return

    # 2. Top Accept Headers
    print("--- 🎯 Top 'Accept' Headers ---")
    cur.execute("""
        SELECT acc.value, SUM(t.count) as total
        FROM telemetry t
        JOIN accept_headers acc ON t.accept_id = acc.id
        GROUP BY acc.id
        ORDER BY total DESC
        LIMIT 5
    """)
    for acc, count in cur.fetchall():
        # Truncate accept header slightly if it's monstrously long
        acc_short = acc[:70] + "..." if acc and len(acc) > 70 else acc
        print(f"{count:<5} | {acc_short}")
    print()

    # 3. Trapdoor Activations (Served MD)
    print("--- 🪤 Recent Markdown Trapdoor Events ---")
    cur.execute("""
        SELECT p.value, ua.value, t.count, t.last_updated
        FROM telemetry t
        JOIN paths p ON t.path_id = p.id
        JOIN user_agents ua ON t.ua_id = ua.id
        WHERE t.served_md = 1
        ORDER BY t.last_updated DESC
        LIMIT 5
    """)
    md_events = cur.fetchall()
    if md_events:
        for path, ua, count, last_updated in md_events:
            ua_short = ua[:40] + "..." if len(ua) > 40 else ua
            print(f"[{last_updated[11:19]}] Hits: {count:<3} | Path: {path:<25} | UA: {ua_short}")
    else:
        print("No explicit Markdown requests (served_md=1) logged yet.")
    print()

if __name__ == "__main__":
    check_telemetry()