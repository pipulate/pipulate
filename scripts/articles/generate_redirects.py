#!/usr/bin/env python3
import csv
import urllib.parse
import os
import sys
import json
import argparse
from pathlib import Path
import re
import difflib
import common

def get_active_permalinks(navgraph_path):
    """Recursively extracts active permalinks AND builds a slug fallback map."""
    active = set()
    slug_map = {}
    if not navgraph_path.exists():
        print(f"⚠️ Warning: {navgraph_path} not found. Proceeding without collision check.")
        return active, slug_map

    with open(navgraph_path, 'r', encoding='utf-8') as f:
        nav = json.load(f)

    def traverse(node):
        if 'permalink' in node:
            p = node['permalink']
            active.add(p)
            active.add(p.rstrip('/'))

            # Build fuzzy slug map for auto-correction
            clean_p = p.strip('/')
            if clean_p:
                raw_slug = clean_p.split('/')[-1]
                # Strip date prefix if it exists (YYYY-MM-DD-)
                slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', raw_slug)
                slug_map[slug] = p

        for child in node.get('children_hubs', []): traverse(child)
        for child in node.get('children_articles', []): traverse(child)

    traverse(nav)
    return active, slug_map

def enforce_slash(url):
    """Ensures directories have trailing slashes while leaving explicit files alone."""
    if not url.endswith('/'):
        last_part = url.split('/')[-1] if '/' in url else url
        if '.' not in last_part:
            return url + '/'
        # If it has a dot but isn't a known file type, it's an ambiguous bot probe. Add slash.
        elif not url.lower().endswith(('.txt', '.php', '.html', '.xml', '.md', '.json', '.ico', '.png', '.jpg', '.gif', '.css', '.js')):
            return url + '/'
    return url

def build_nginx_map(csv_input_path, map_output_path, navgraph_path):
    print(f"🛠️ Forging Nginx map from {csv_input_path.name}...")
    
    if not csv_input_path.exists():
        print(f"❌ Error: {csv_input_path} not found.")
        return

    # 1. Establish the Absolute Truth
    active_permalinks, slug_map = get_active_permalinks(navgraph_path)
    
    # 1.5 Protect Explicit System Paths (DO NOT REMAP THESE)
    protected_system_paths = [
        '/', '/index.html', '/feed.xml', '/llms.txt', '/robots.txt',
        '/sitemap.xml', '/sitemap-core.xml', '/sitemap-hubs.xml',
        '/sitemap-branch-0.xml', '/sitemap-branch-1.xml',
        '/sitemap-branch-2.xml', '/sitemap-branch-3.xml',
        '/sitemap-branch-4.xml', '/sitemap-branch-5.xml',
        '/sitemap-branch-6.xml'
    ]
    active_permalinks.update(protected_system_paths)
    
    # Define obvious noise signatures that SQL might have missed
    known_noise_signatures = [
        'actuator', 'owa', 'rdweb', 'sslvpn', 'remote', 
        'wp-', 'wordpress', 'sdk', 'dr0v',
        'sitemap', '.xml', # Aggressively block any sitemap variations
        '.well-known', 'ads.txt', 'bingsiteauth', 'login', 'admin',
        'security.txt', 'favicon.ico', '.php', '.env', '.git'
    ]

    valid_mappings = {}  # The Deduplication Ledger
    
    # Pass 1: Read, Clean, and Filter the CSV
    with open(csv_input_path, 'r', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        for row in reader:
            if len(row) != 2:
                continue # Skip hallucinated or malformed rows
                
            old_url = row[0].strip()
            new_url = row[1].strip()

            # --- THE DEFENSIVE PERIMETER ---

            # 1. The Living Tissue Filter (Protects Hubs, Articles, and Root)
            # Ensure we check both with and without trailing slashes
            check_url = old_url if old_url.endswith('/') else old_url + '/'
            if check_url in active_permalinks or old_url in active_permalinks:
                print(f"🛡️ Protected Living URL (Collision Avoided): {old_url}")
                continue # Drop the row entirely

            # 2. The Noise Filter (Blocks Script Kiddies)
            is_noise = any(sig in old_url.lower() for sig in known_noise_signatures)
            if is_noise:
                print(f"🗑️ Dropped Known Noise Probe: {old_url}")
                continue

            # 3. The Placeholder Filter (Blocks LLM Hallucinations)
            if '...' in old_url or 'placeholder' in old_url.lower() or 'slug' in old_url.lower():
                print(f"🤖 Dropped LLM Placeholder/Hallucination: {old_url}")
                continue

            # -------------------------------

            # THE BOUNCER: 80/20 Encoding Filter
            if '%' in old_url or '%' in new_url:
                print(f"⚠️ Dropping encoded URL: {old_url[:30]}...")
                continue

            # THE BOUNCER: Artifact Filter
            if 'attachment' in old_url.lower():
                print(f"⚠️ Dropping artifact URL: {old_url[:30]}...")
                continue
                
            # THE BOUNCER: Asset & Parameter Filter
            if '?' in old_url or old_url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.txt', '.xml')):
                print(f"⚠️ Dropping asset/parameter URL: {old_url[:30]}...")
                continue

            # THE BOUNCER: Strict Trailing Slash Enforcer
            # Drops .php, .html, and ambiguous non-slashed directory paths.
            if not old_url.endswith('/'):
                print(f"🗡️ Dropping non-directory URL (No trailing slash): {old_url}")
                continue

            # --- THE HEALER & VALIDATOR (FUZZY SNAP) ---
            
            # 1. Aggressive cleaning: lower, unquote, strip hidden chars
            clean_new = urllib.parse.unquote(new_url.lower().replace('\r', '').replace('\u200b', '').strip())
            clean_new = enforce_slash(clean_new)

            # Create a lowercased map of active permalinks for resilient checking
            lower_to_actual = {p.lower(): p for p in active_permalinks}

            # 2. Try Exact Match (Case-Insensitive)
            if clean_new in lower_to_actual:
                valid_mappings[old_url] = lower_to_actual[clean_new]
                continue

            # 3. Try Slug Match
            new_slug = clean_new.strip('/').split('/')[-1] if clean_new.strip('/') else ""
            new_slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', new_slug)
            lower_slug_map = {k.lower(): v for k, v in slug_map.items()}
            
            if new_slug in lower_slug_map:
                corrected_url = lower_slug_map[new_slug]
                print(f"🪄 Slug-corrected: {new_url} -> {corrected_url}")
                valid_mappings[old_url] = corrected_url
                continue

            # 4. The Ultimate Fuzzy Matcher (Nipping it in the bud)
            # Find the closest matching actual permalink (minimum 70% similarity)
            matches = difflib.get_close_matches(clean_new, lower_to_actual.keys(), n=1, cutoff=0.7)
            if matches:
                corrected_url = lower_to_actual[matches[0]]
                print(f"🧲 Fuzzy-snapped: {new_url} -> {corrected_url}")
                valid_mappings[old_url] = corrected_url
                continue

            # 5. Total Hallucination (Drop it)
            print(f"👻 Dropping AI Hallucination (No match found): {new_url}")
            continue
            # ------------------------------
                
            # Add to dict. If old_url already exists, the newer AI mapping silently overrides it.
            valid_mappings[old_url] = new_url

    # Pass 2: Rewrite the CSV Ledger (Self-Pruning, No Blank Lines)
    with open(csv_input_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Convert the dict back to a list of rows for the CSV
        writer.writerows([[k, v] for k, v in valid_mappings.items()])
    print(f"🧹 Pruned and synchronized raw CSV ledger.")

    # Pass 3: Compile the final Nginx Map
    with open(map_output_path, 'w', encoding='utf-8') as outfile:
        outfile.write("# AI-Generated Semantic Redirects\n")
        
        # --- HARDCODED SYSTEM REDIRECTS ---
        outfile.write("    ~^/feed/?$ /feed.xml;\n")
        # ----------------------------------

        for old_url, new_url in valid_mappings.items():
            safe_old_url = urllib.parse.quote(old_url, safe='/%')
            if not safe_old_url.startswith('/'): safe_old_url = '/' + safe_old_url
            if not new_url.startswith('/'): new_url = '/' + new_url

            # THE REGEX FORGER
            outfile.write(f"    ~^{safe_old_url}/?$ {new_url};\n")

    print(f"✅ Nginx map forged successfully at {map_output_path.name}")

def main():
    parser = argparse.ArgumentParser(description="Generate Nginx Redirect Map")
    common.add_target_argument(parser)
    args = parser.parse_args()

    # Dynamically resolve target repository paths
    posts_dir = common.get_target_path(args)
    repo_root = posts_dir.parent
    
    csv_input_path = repo_root / '_raw_map.csv'
    map_output_path = repo_root / '_redirects.map'
    navgraph_path = Path('navgraph.json').resolve()

    build_nginx_map(csv_input_path, map_output_path, navgraph_path)

if __name__ == "__main__":
    main()
