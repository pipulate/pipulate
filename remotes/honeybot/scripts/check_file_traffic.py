import sys
from db import db

def check_file(filename_pattern):
    print(f"🔍 Checking traffic for pattern: '{filename_pattern}'...")
    
    conn = db.get_conn()
    cur = conn.cursor()
    
    # 1. Total Hits
    sql_total = """
        SELECT SUM(logs.count)
        FROM daily_logs logs
        JOIN paths p ON logs.path_id = p.id
        WHERE p.value LIKE ?
    """
    cur.execute(sql_total, (f"%{filename_pattern}%",))
    total = cur.fetchone()[0] or 0
    
    print(f"📉 Total Hits: {total}")
    print("-" * 80)
    
    # 2. Breakdown by User Agent
    sql_breakdown = """
        SELECT ua.value, SUM(logs.count) as hits
        FROM daily_logs logs
        JOIN paths p ON logs.path_id = p.id
        JOIN user_agents ua ON logs.ua_id = ua.id
        WHERE p.value LIKE ?
        GROUP BY ua.id
        ORDER BY hits DESC
        LIMIT 50
    """
    
    cur.execute(sql_breakdown, (f"%{filename_pattern}%",))
    rows = cur.fetchall()
    
    if not rows:
        print("❌ No traffic found for this file.")
        return

    # Use a wider format
    print(f"{'HITS':<6} | {'USER AGENT'}")
    print("-" * 80)
    
    for ua, count in rows:
        # No truncation: Show the full raw UA string
        print(f"{count:<6} | {ua}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        target = "feed.xml" # Default
    else:
        target = sys.argv[1]
        
    check_file(target)