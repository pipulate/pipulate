#!/usr/bin/env python3
"""
⛏️ The Bot Miner
Interrogates the sovereign database to find high-volume agents
that are missing from the KNOWN_BOTS "Orange List".
"""

import sys
import re
from rich.console import Console
from rich.table import Table
from db import db
from logs import KNOWN_BOTS

console = Console()

# Keywords that strongly suggest non-human behavior
SUSPICIOUS_TERMS = [
    "bot", "crawl", "spider", "fetch", "scrape", "search", 
    "preview", "monitor", "http", "python", "curl", "wget", 
    "headless", "puppeteer", "selenium"
]

def mine():
    console.print(f"[bold cyan]⛏️  Mining honeybot.db for unclassified agents...[/]")
    console.print(f"   Current Known Bots: [green]{len(KNOWN_BOTS)}[/]")
    
    conn = db.get_conn()
    cur = conn.cursor()
    
    # 1. Get ALL User Agents and their hit counts
    sql = """
        SELECT ua.value, SUM(logs.count) as total
        FROM daily_logs logs
        JOIN user_agents ua ON logs.ua_id = ua.id
        GROUP BY ua.id
        ORDER BY total DESC
    """
    cur.execute(sql)
    results = cur.fetchall()
    
    candidates = []
    
    for ua, count in results:
        # Skip if already known
        is_known = False
        for known in KNOWN_BOTS:
            if known.lower() in ua.lower():
                is_known = True
                break
        
        if is_known:
            continue
            
        # Analyze Unknowns
        score = 0
        reasons = []
        
        # Heuristic 1: Suspicious Keywords
        for term in SUSPICIOUS_TERMS:
            if term in ua.lower():
                score += 10
                reasons.append(term)
                
        # Heuristic 2: Non-Mozilla/Standard format (Often scripts)
        if "Mozilla" not in ua:
            score += 5
            reasons.append("non-mozilla")
            
        # Heuristic 3: High Volume
        if count > 50:
            score += 2
            reasons.append("high-volume")
            
        # Heuristic 4: "Compatible" but not standard browser
        if "compatible" in ua.lower() and "mozilla" in ua.lower():
            # Check if it's NOT a standard browser
            if "chrome" not in ua.lower() and "safari" not in ua.lower() and "firefox" not in ua.lower():
                 score += 5
                 reasons.append("compatible-non-browser")

        if score > 0:
            candidates.append({
                "ua": ua,
                "count": count,
                "score": score,
                "reasons": ", ".join(reasons)
            })

    # Sort by Score (Most bot-like first), then by Count
    candidates.sort(key=lambda x: (x['score'], x['count']), reverse=True)
    
    # Display
    table = Table(title="🚨 Suspicious Unknown Agents")
    table.add_column("Hits", style="cyan", justify="right")
    table.add_column("Score", style="magenta", justify="right")
    table.add_column("User Agent", style="white")
    table.add_column("Reasons", style="dim yellow")
    
    for c in candidates[:50]: # Show top 50 candidates
        table.add_row(str(c['count']), str(c['score']), c['ua'], c['reasons'])
        
    console.print(table)

    # Generate Copy-Paste List (Stacked Format)
    if candidates:
        console.print("\n[bold green]📋 Paste this into logs.py:[/]")
        print('KNOWN_BOTS = """\\')
        
        # 1. Print existing bots to keep context (optional, but helpful for merging)
        # for bot in KNOWN_BOTS:
        #     print(bot)
            
        # 2. Print new candidates
        suggested_names = set()
        for c in candidates[:20]:
            # Try to extract a clean name (e.g., "FooBot/1.0" -> "FooBot")
            parts = re.split(r'[ /;()]', c['ua'])
            for p in parts:
                if any(x in p.lower() for x in SUSPICIOUS_TERMS) and len(p) > 2:
                    suggested_names.add(p)
                    break
        
        for s in sorted(list(suggested_names)):
            if s not in KNOWN_BOTS:
                print(s)
                
        print('""".splitlines()')


if __name__ == "__main__":
    mine()
