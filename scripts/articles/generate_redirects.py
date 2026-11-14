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

def resolve_navgraph_path(repo_root):
    """Locate navgraph.json across script directory, CWD, or target repo root."""
    candidates = [
        Path(__file__).resolve().parent / "navgraph.json",
        Path("navgraph.json").resolve(),
        repo_root / "navgraph.json",
    ]
    return next((p for p in candidates if p.is_file()), candidates[0])


def _scan_markdown_permalinks(md_dir):
    """Fast frontmatter permalink fallback so redirects never run blind without navgraph.json."""
    found = []
    if not md_dir or not md_dir.is_dir():
        return found
    for md_path in sorted(md_dir.glob("*.md")):
        try:
            head = md_path.read_text(encoding="utf-8", errors="ignore")[:2048]
        except OSError:
            continue
        m = re.search(r"^permalink:\s*(\S+)", head, re.M)
        if m:
            raw_p = m.group(1).strip().strip('"').strip("'")
            if raw_p:
                if not raw_p.startswith("/"):
                    raw_p = "/" + raw_p
                found.append(enforce_slash(raw_p))
    return found


def get_navgraph_sets(navgraph_path, posts_dir=None, pages_dir=None):
    """Extract living URLs, canonical slashed permalinks, and hub-isolated sets."""
    living_tissue = set()
    canonical_all = set()
    canonical_hubs = set()
    slug_map = {}
    hub_slug_map = {}

    def register_url(p, is_hub=False):
        if not p:
            return
        canon = p if p == "/" or p.endswith("/") else enforce_slash(p)
        living_tissue.add(canon)
        if canon != "/":
            living_tissue.add(canon.rstrip("/"))
        canonical_all.add(canon)
        clean_p = canon.strip("/")
        if clean_p:
            raw_slug = clean_p.split("/")[-1]
            slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", raw_slug)
            slug_map[slug] = canon
            if is_hub:
                canonical_hubs.add(canon)
                hub_slug_map[slug] = canon

    if navgraph_path and navgraph_path.exists():
        with open(navgraph_path, "r", encoding="utf-8") as f:
            nav = json.load(f)

        def traverse(node):
            ntype = node.get("type", "")
            if "permalink" in node:
                register_url(node["permalink"], is_hub=(ntype == "hub"))
            for child in node.get("children_hubs", []):
                traverse(child)
            for child in node.get("children_articles", []):
                traverse(child)

        traverse(nav)

    for hp in _scan_markdown_permalinks(pages_dir):
        register_url(hp, is_hub=True)
    for ap in _scan_markdown_permalinks(posts_dir):
        register_url(ap, is_hub=False)

    return living_tissue, canonical_all, canonical_hubs, slug_map, hub_slug_map


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

    # 1. Establish the Absolute Truth (hub/article separated + disk frontmatter fallback)
    repo_root = csv_input_path.parent
    living_tissue, active_permalinks, active_hubs, slug_map, _ = get_navgraph_sets(
        navgraph_path, posts_dir=repo_root / "_posts", pages_dir=repo_root / "pages"
    )
    if not active_permalinks:
        print("❌ Error: Zero active permalinks resolved; refusing to prune _raw_map.csv blind.")
        return
    
    # 1.5 Protect Explicit System Paths (DO NOT REMAP THESE)
    protected_system_paths = [
        '/', '/index.html', '/feed.xml', '/llms.txt', '/robots.txt',
        '/sitemap.xml', '/sitemap-core.xml', '/sitemap-hubs.xml',
        *[f'/sitemap-branch-{i}.xml' for i in range(16)],
    ]
    living_tissue.update(protected_system_paths)
    active_permalinks.update(protected_system_paths)
    
    # Define anchored exploit/system noise signatures without false-matching legitimate slugs like 'actuator-imperative'
    known_noise_signatures = [
        '/actuator', '/owa', '/rdweb', '/sslvpn',
        '/wp-', '/xmlrpc', 'dr0v',
        'sitemap', '.xml',
        '/.', 'ads.txt', 'bingsiteauth', '/api/', '/cgi-bin', '/phpmyadmin', '/boaform', '/autodiscover',
        'security.txt', 'favicon.ico', '.php', '.asp', '.jsp', '.env', '.git'
    ]

    retired_to_active = {}
    retired_hubs_clean = {}
    retired_hubs_path = repo_root / "_data" / "retired_hubs.json"
    if retired_hubs_path.is_file():
        try:
            retired_hubs_raw = json.loads(retired_hubs_path.read_text(encoding="utf-8")) or {}
        except Exception:
            retired_hubs_raw = {}
        lower_hubs = {h.lower(): h for h in active_hubs}
        for old_h, tgt_h in sorted(retired_hubs_raw.items()):
            chk_h = old_h if old_h.endswith("/") else old_h + "/"
            if chk_h in living_tissue or old_h in living_tissue:
                continue
            clean_tgt = enforce_slash(str(tgt_h).strip().lower())
            if clean_tgt in lower_hubs:
                retired_hubs_clean[chk_h] = lower_hubs[clean_tgt]
                retired_to_active[chk_h.lower()] = lower_hubs[clean_tgt]
    safe_map_path_re = re.compile(r"^/[A-Za-z0-9/_.-]+$")
    lower_to_actual = {p.lower(): p for p in active_permalinks}
    lower_slug_map = {k.lower(): v for k, v in slug_map.items()}
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
            if check_url in living_tissue or old_url in living_tissue:
                print(f"🛡️ Protected Living URL (Collision Avoided): {old_url}")
                continue # Drop the row entirely

            # 2. The Noise Filter (Blocks Script Kiddies)
            is_noise = any(sig in old_url.lower() for sig in known_noise_signatures)
            if is_noise:
                print(f"🗑️ Dropped Known Noise Probe: {old_url}")
                continue

            # 3. The Placeholder Filter (Blocks LLM Hallucinations while preserving real slugs containing 'slug')
            if (
                '...' in old_url
                or 'placeholder' in old_url.lower()
                or '<slug>' in old_url.lower()
                or '{slug}' in old_url.lower()
                or '/slug/' in old_url.lower()
            ):
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
                
            # THE BOUNCER: Asset & Parameter Filter (strip trailing slash so .gif/ probes never slip through)
            old_probe = old_url.rstrip('/').lower()
            if '?' in old_url or old_probe.endswith((
                '.png', '.jpg', '.jpeg', '.gif', '.ico', '.txt', '.xml',
                '.css', '.js', '.svg', '.webp', '.woff', '.woff2', '.ttf',
            )):
                print(f"⚠️ Dropping asset/parameter URL: {old_url[:30]}...")
                continue

            # THE BOUNCER: Normalize /index.md and clean extensionless slugs; allow .html/.htm legacy posts
            old_url = re.sub(r'/+', '/', old_url)
            if old_url.lower().endswith('/index.md') and len(old_url) > len('/index.md'):
                old_url = old_url[:-len('index.md')]
            elif not old_url.endswith('/') and not old_url.lower().endswith(('.html', '.htm')):
                if old_url.startswith('/') and '.' not in old_url.split('/')[-1]:
                    old_url = old_url + '/'
                else:
                    print(f"🗡️ Dropping non-directory URL (No trailing slash): {old_url}")
                    continue
            if not safe_map_path_re.match(old_url):
                print(f"🧹 Dropping Nginx-unsafe source path: {old_url}")
                continue
            norm_check = old_url if old_url.endswith('/') else old_url + '/'
            if norm_check in living_tissue or old_url in living_tissue or old_url.rstrip('/') in living_tissue:
                print(f"🛡️ Protected Living URL (Post-Normalization Collision Avoided): {old_url}")
                continue

            # --- THE HEALER & VALIDATOR (FUZZY SNAP) ---
            
            # 1. Aggressive cleaning: lower, unquote, strip hidden chars, and collapse retired hubs in 1 hop
            clean_new = urllib.parse.unquote(new_url.lower().replace('\r', '').replace('\u200b', '').strip())
            clean_new = enforce_slash(clean_new)
            if clean_new in retired_to_active:
                clean_new = retired_to_active[clean_new].lower()

            # Check precomputed lower_to_actual and lower_slug_map

            # 2. Try Exact Match (Case-Insensitive), then stripped .md / /index.md fallback
            if clean_new in lower_to_actual:
                valid_mappings[old_url] = lower_to_actual[clean_new]
                continue
            stripped_md_new = re.sub(r'(?:/index\.md|\.md)/?$', '/', clean_new)
            if stripped_md_new in lower_to_actual:
                valid_mappings[old_url] = lower_to_actual[stripped_md_new]
                continue

            # 3. Try Slug Match
            new_slug = stripped_md_new.strip('/').split('/')[-1] if stripped_md_new.strip('/') else ""
            new_slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', new_slug)
            
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
        
        # --- HARDCODED SYSTEM REDIRECTS (O(1) exact-match via $redirect_key) ---
        outfile.write("    /feed /feed.xml;\n")
        # ----------------------------------

        combined_mappings = dict(valid_mappings)
        combined_mappings.update(retired_hubs_clean)

        seen_keys = {"/feed"}
        for old_url, new_url in combined_mappings.items():
            safe_old_url = re.sub(r'/+', '/', old_url.strip())
            if not safe_old_url.startswith('/'):
                safe_old_url = '/' + safe_old_url
            if not new_url.startswith('/'):
                new_url = '/' + new_url
            if not safe_map_path_re.match(safe_old_url) or not safe_map_path_re.match(new_url):
                continue

            # THE O(1) HASH FORGER ($redirect_key strips trailing / and /index.md; .html/.htm stay exact)
            map_key = safe_old_url if safe_old_url.lower().endswith(('.html', '.htm')) else safe_old_url.rstrip('/')
            if not map_key or map_key == '/' or map_key in seen_keys:
                continue
            seen_keys.add(map_key)
            outfile.write(f"    {map_key} {new_url};\n")

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
    navgraph_path = resolve_navgraph_path(repo_root)

    build_nginx_map(csv_input_path, map_output_path, navgraph_path)

if __name__ == "__main__":
    main()
