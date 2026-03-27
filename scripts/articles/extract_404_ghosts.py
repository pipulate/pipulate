#!/usr/bin/env python3
"""
extract_404_ghosts.py
Reads current redirects and active hubs, injects them into SQLite as exclusions,
and runs the hot_404_remaps_top.sql query over SSH to guarantee idempotency.
"""
import os
import json
import subprocess
from pathlib import Path

def get_excluded_urls():
    exclusions = set()
    repo_root = Path(__file__).resolve().parent.parent.parent
    trimnoir_root = repo_root.parent / 'trimnoir'
    
    # 1. Read the upstream CSV ledger to push deeper into the Zipfian tail instantly
    raw_csv_path = trimnoir_root / '_raw_map.csv'
    if raw_csv_path.exists():
        import csv
        with open(raw_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 1:
                    raw_source = row[0].strip()
                    if raw_source:
                        exclusions.add(raw_source)
                        exclusions.add(raw_source.rstrip('/')) # Catch variations

    # 2. Read active physical hubs to prevent Nginx collision
    navgraph_path = trimnoir_root / 'navgraph.json'
    if navgraph_path.exists():
        with open(navgraph_path, 'r') as f:
            nav = json.load(f)
            
        def traverse(node):
            if 'permalink' in node:
                exclusions.add(node['permalink'])
                exclusions.add(node['permalink'].rstrip('/'))
            for child in node.get('children_hubs', []): traverse(child)
            for child in node.get('children_articles', []):
                if 'permalink' in child:
                    exclusions.add(child['permalink'])
                    exclusions.add(child['permalink'].rstrip('/'))
        traverse(nav)
    
    return exclusions

def main():
    exclusions = get_excluded_urls()
    repo_root = Path(__file__).resolve().parent.parent.parent
    sql_file = repo_root / 'remotes' / 'honeybot' / 'queries' / 'hot_404_remaps_top.sql'
    
    with open(sql_file, 'r') as f:
        base_query = f.read()

    # Build dynamic INSERT statements in chunks to respect SQLite limits
    inserts = []
    if exclusions:
        chunk_size = 500
        urls = list(exclusions)
        for i in range(0, len(urls), chunk_size):
            chunk = urls[i:i + chunk_size]
            # Escape single quotes in URLs for SQL insertion
            values = ", ".join([f"('{u.replace(chr(39), chr(39)+chr(39))}')" for u in chunk])
            inserts.append(f"INSERT INTO exclusions (url) VALUES {values};")
    
    dynamic_sql = "CREATE TEMP TABLE IF NOT EXISTS exclusions (url TEXT);\n"
    dynamic_sql += "DELETE FROM exclusions;\n" # Ensure clean slate in session
    dynamic_sql += "\n".join(inserts) + "\n\n"
    dynamic_sql += base_query

    # Execute over SSH
    cmd = ["ssh", "honeybot", "sqlite3 -header -column ~/www/mikelev.in/honeybot.db"]
    print("🚀 Uploading repository state and extracting 404 Ghosts...\n", flush=True)
    result = subprocess.run(cmd, input=dynamic_sql, text=True, capture_output=True)
    
    if result.returncode != 0:
        print("❌ Error executing query:", result.stderr)
    else:
        # Extract the prompt block from the SQL to display to the user
        prompt_lines = [line for line in base_query.splitlines() if line.startswith('--') and 'PROMPT FU' in base_query]
        print("\n".join(prompt_lines[:15])) # Print the prompt header
        print("\n--- LIST A: THE 404 GHOSTS (Source) ---")
        print(result.stdout)

        # Intercept and scrub the SQL output before sending to the LLM
        for line in result.stdout.splitlines():
            # Drop Nginx regex, spaces, and trailing semicolons
            if line.startswith('~^') or ' ' in line or ';' in line:
                continue
                
            # ENFORCE TRAILING SLASH: Only pass URLs ending in '/' to the AI
            if not line.endswith('/'):
                continue
                
            print(line)

if __name__ == "__main__":
    main()