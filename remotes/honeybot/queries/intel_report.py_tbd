#!/usr/bin/env python3
"""
Intel Report Generator
Queries the HoneyDB and outputs a Markdown-formatted intelligence brief 
designed specifically to be copy-pasted into an LLM context window.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3

# Add script dir to path to find db
sys.path.append(str(Path(__file__).parent))
from db import db, KNOWN_BOTS

def generate_report(days_back=7):
    conn = db.get_conn()
    cur = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    
    report = []
    report.append(f"# HoneyBot Intelligence Report")
    report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**Window:** Last {days_back} days (Since {cutoff_date})\n")
    
    # --- 1. UNKNOWN AGENT DISCOVERY ---
    # Find high-volume agents that are NOT in our KNOWN_BOTS list
    # This helps us identify new AI scrapers or changing user-agents
    known_bots_sql = ", ".join([f"'{b}'" for b in KNOWN_BOTS])
    
    cur.execute(f"""
        SELECT ua.value, SUM(l.count) as total
        FROM daily_logs l
        JOIN user_agents ua ON l.ua_id = ua.id
        WHERE l.date >= ? 
        AND ua.value NOT LIKE '%Mozilla%' 
        AND ua.value NOT LIKE '%Chrome%'
        AND ua.value NOT LIKE '%Safari%'
        GROUP BY ua.id
        ORDER BY total DESC
        LIMIT 15
    """, (cutoff_date,))
    
    unknown_agents = [row for row in cur.fetchall() if not any(kb in row[0] for kb in KNOWN_BOTS)]
    
    report.append("## 🔍 Discovery: High-Volume Unknown Agents")
    report.append("> *Potential new bots to add to KNOWN_BOTS*")
    if unknown_agents:
        report.append("| Hits | User Agent |")
        report.append("|---|---|")
        for ua, count in unknown_agents:
            report.append(f"| {count:,} | `{ua}` |")
    else:
        report.append("No significant unknown agents found in this window.")
    report.append("\n")

    # --- 2. TRUE 404s (Content to Remap) ---
    # Exclude obvious script kiddie paths (.php, wp-admin, .env)
    cur.execute("""
        SELECT p.value, SUM(l.count) as total
        FROM daily_logs l
        JOIN paths p ON l.path_id = p.id
        WHERE l.status = 404
        AND l.date >= ?
        AND p.value NOT LIKE '%.php%'
        AND p.value NOT LIKE '%wp-%'
        AND p.value NOT LIKE '%.env%'
        AND p.value NOT LIKE '%.git%'
        GROUP BY p.id
        ORDER BY total DESC
        LIMIT 20
    """, (cutoff_date,))
    
    true_404s = cur.fetchall()
    
    report.append("## 🗺️ The Map: Top 'True' 404s")
    report.append("> *Legitimate missing content. Candidates for Nginx redirect mapping.*")
    if true_404s:
        report.append("| Hits | Missing Path |")
        report.append("|---|---|")
        for path, count in true_404s:
            report.append(f"| {count:,} | `{path}` |")
    else:
        report.append("No significant True 404s found.")
    report.append("\n")

    # --- 3. THE NOISE (Security & Ban Targets) ---
    # Paths actively being probed by vulnerability scanners
    cur.execute("""
        SELECT p.value, SUM(l.count) as total
        FROM daily_logs l
        JOIN paths p ON l.path_id = p.id
        WHERE l.status = 404
        AND l.date >= ?
        AND (p.value LIKE '%.php%' OR p.value LIKE '%wp-%' OR p.value LIKE '%.env%')
        GROUP BY p.id
        ORDER BY total DESC
        LIMIT 10
    """, (cutoff_date,))
    
    noise_paths = cur.fetchall()
    
    report.append("## 🛡️ Security: Top Vulnerability Probes")
    report.append("> *Script kiddie noise. Candidates for Fail2Ban rules.*")
    if noise_paths:
        report.append("| Hits | Probed Path |")
        report.append("|---|---|")
        for path, count in noise_paths:
            report.append(f"| {count:,} | `{path}` |")
    else:
        report.append("No significant vulnerability probing detected.")
    report.append("\n")

    # Print the report to stdout
    print("\n".join(report))

if __name__ == "__main__":
    generate_report()