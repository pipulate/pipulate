#!/usr/bin/env python3
"""
lsa.py (List All Articles)

A unified utility merging the fast-streaming, copy-paste-friendly output of ls2.py
with the deep structural sort_order analysis of list_articles.py.
Dynamically routed via targets.json.
"""

import os
import sys
import yaml
import json
import argparse
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# Gracefully handle tiktoken
try:
    import tiktoken
    def count_tokens(text: str, model: str = "gpt-4o") -> int:
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception:
            return len(text.split())
except ImportError:
    def count_tokens(text: str, model: str = "") -> int:
        return len(text.split())

# Gracefully handle rich for the gaps report
try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

CONFIG_DIR = Path.home() / ".config" / "articleizer"
TARGETS_FILE = CONFIG_DIR / "blogs.json"

DEFAULT_TARGETS = {
    "1": {
        "name": "Local Project (Default)",
        "path": "./_posts"
    }
}

def load_targets():
    if TARGETS_FILE.exists():
        try:
            with open(TARGETS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Warning: {TARGETS_FILE} is corrupt. Using defaults.", file=sys.stderr)
    return DEFAULT_TARGETS

def fast_get_sort_order(filepath):
    """Reads only the YAML frontmatter to extract sort_order extremely fast."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            if not first_line.startswith('---'):
                return 0, ''
            
            yaml_content = []
            for line in f:
                if line.startswith('---'):
                    break
                yaml_content.append(line)
                
            fm = yaml.safe_load(''.join(yaml_content)) or {}
            return int(fm.get('sort_order', 0)), (fm.get('permalink') or '')
    except Exception:
        return 0, ''

def analyze_sort_order_contiguity(metadata):
    """Analyzes sort_order for gaps, duplicates, and late starts."""
    anomalies = []
    posts_by_day = defaultdict(list)

    for item in metadata:
        posts_by_day[item['date']].append(item['sort_order'])

    for date, orders in sorted(posts_by_day.items()):
        unique_orders = sorted(list(set(orders)))

        # Duplicates
        if len(orders) != len(unique_orders):
            dupes = sorted([o for o in unique_orders if orders.count(o) > 1])
            anomalies.append({
                "date": date, "type": "Duplicate",
                "details": f"Duplicate value(s): {dupes}", "sequence": str(orders)
            })

        # Starts Late
        if unique_orders and unique_orders[0] != 1:
            anomalies.append({
                "date": date, "type": "Starts Late",
                "details": f"Sequence starts at {unique_orders[0]} instead of 1.", "sequence": str(orders)
            })

        # Gaps
        if unique_orders:
            expected_sequence = set(range(1, unique_orders[-1] + 1))
            gaps = sorted(list(expected_sequence - set(unique_orders)))
            if gaps:
                anomalies.append({
                    "date": date, "type": "Gap",
                    "details": f"Missing value(s): {gaps}", "sequence": str(orders)
                })

    return anomalies

def print_contiguity_report(anomalies):
    if not RICH_AVAILABLE:
        print("\n=== Sort Order Contiguity Report ===")
        if not anomalies:
            print("✅ All Clear! Sort order is contiguous.")
            return
        for a in anomalies:
            print(f"[{a['date']}] {a['type']}: {a['details']} | Seq: {a['sequence']}")
        return

    console = Console()
    console.print("\n" + "="*50)
    console.print("[bold bright_blue]Sort Order Contiguity Report[/bold bright_blue]")
    console.print("="*50)

    if not anomalies:
        console.print("✅ [bold green]All Clear![/bold green] Sort order is contiguous and correct for all days.")
        return

    table = Table(box=box.ROUNDED, show_lines=True)
    table.add_column("Date", style="magenta", justify="left")
    table.add_column("Anomaly Type", style="cyan", justify="left")
    table.add_column("Details", style="white", justify="left")
    table.add_column("Observed Sequence", style="yellow", justify="left")

    for a in anomalies:
        table.add_row(str(a["date"]), a["type"], a["details"], a["sequence"])
    console.print(table)


def parse_slice_arg(arg_str: str):
    """Parses a string like '[-5:]' into a valid Python slice object."""
    if not arg_str or not arg_str.startswith('[') or not arg_str.endswith(']'): return None
    content = arg_str[1:-1].strip()
    if ':' in content:
        parts = content.split(':', 1)
        start = int(parts[0].strip()) if parts[0].strip() else None
        end = int(parts[1].strip()) if parts[1].strip() else None
        return slice(start, end)
    elif content: return int(content)
    return slice(None, None)


def main():
    parser = argparse.ArgumentParser(description="Unified Article Lister & Analyzer")
    parser.add_argument('-t', '--target', type=str, help="Target ID from blogs.json (e.g., '1', '4')")
    parser.add_argument('-g', '--gaps', action='store_true', help="Run and display the sort_order contiguity gap report")
    parser.add_argument('-r', '--reverse', action='store_true', help="Reverse the sorting order")
    parser.add_argument('-a', '--article', type=str, help="Generate a prompt_foo.py command for a slice of articles (e.g., '[-5:]')")
    parser.add_argument('--top', type=int, default=None, metavar='N', help="Limit output to the first N results (after sorting)")
    parser.add_argument('--match', type=str, default=None, metavar='TERMS', help="Filter articles whose filename contains all whitespace-separated terms (case-insensitive)")
    parser.add_argument('--tokens-under', type=int, default=None, metavar='N', dest='tokens_under', help="Exclude articles with token count >= N (requires reading each file)")
    parser.add_argument('--fmt', type=str, default='full', choices=['full', 'paths', 'slugs', 'dated-slugs'], help="Output format: 'full' (default, with comments), 'paths' (bare absolute paths), or 'slugs' (concept slug only, no date prefix)")
    parser.add_argument('--slugs', nargs='+', default=None, metavar='SLUG', help="Select articles by exact slug match (space-separated, no date prefix needed)")
    parser.add_argument('--clear-cache', action='store_true', help="Purge the token cache file before processing")
    args = parser.parse_args()

    targets = load_targets()
    target_key = args.target

    if not target_key:
        print("\nSelect Target Repo for Listing:")
        for k, v in targets.items():
            print(f"  [{k}] {v['name']} ({v['path']})")
        target_key = input("Enter choice (default 1): ").strip() or "1"

    if target_key not in targets:
        print(f"❌ Invalid target key: {target_key}", file=sys.stderr)
        sys.exit(1)

    target_dir = Path(targets[target_key]['path']).expanduser().resolve()
    if not target_dir.is_dir():
        print(f"❌ Directory not found: {target_dir}", file=sys.stderr)
        sys.exit(1)

    # Determine the sort description based on the reverse flag
    sort_desc = "Newest First" if args.reverse else "Oldest First"
    
    # Suppress header for machine-readable output formats
    if args.fmt not in ('paths', 'slugs', 'dated-slugs'):
        print(f"# 🎯 Target: {targets[target_key]['name']} [{sort_desc}]\n", flush=True)

    metadata = []
    # --- PASS 1: FAST METADATA EXTRACTION ---
    for filename in os.listdir(target_dir):
        filepath = os.path.join(target_dir, filename)
        if not os.path.isfile(filepath) or not filename.endswith(('.md', '.markdown')):
            continue
            
        try:
            date_str = filename[:10]
            post_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            sort_order, permalink = fast_get_sort_order(filepath)
            
            metadata.append({
                'path': filepath,
                'date': post_date,
                'sort_order': sort_order,
                'permalink': permalink
            })
        except (ValueError, TypeError):
            continue
            
    # Sort first by date, then by the YAML sort_order
    metadata.sort(key=lambda p: (p['date'], p['sort_order']), reverse=args.reverse)

    # --- PASS 1.5: FILTERING ---
    # --slugs: exact slug selection (free, no I/O)
    if args.slugs:
        import re as _re
        wanted = set(args.slugs)
        def _stem_to_slug(path):
            stem = os.path.splitext(os.path.basename(path))[0]
            return _re.sub(r'^\d{4}-\d{2}-\d{2}-', '', stem)
        metadata = [item for item in metadata if _stem_to_slug(item['path']) in wanted]

    # --match: substring filter on filename (free, no I/O)
    if args.match:
        terms = args.match.lower().split()
        metadata = [item for item in metadata if all(t in item['path'].lower() for t in terms)]

    # --top: limit after sort+filter
    if args.top is not None:
        metadata = metadata[:args.top]

    # --tokens-under: expensive filter, read each file
    if args.tokens_under is not None:
        filtered = []
        for item in metadata:
            try:
                with open(item['path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                if count_tokens(content) < args.tokens_under:
                    filtered.append(item)
            except Exception:
                filtered.append(item)  # keep on error
        metadata = filtered

    # --- PASS 2: OUTPUT GENERATION (REPORT OR COMMAND) ---
    cache_file = CONFIG_DIR / "token_cache.json"
    
    if args.clear_cache and cache_file.exists():
        try:
            cache_file.unlink()
            print("✨ Token cache file purged successfully.", file=sys.stderr)
        except Exception:
            pass

    token_cache = {}
    cache_updated = False
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as cf:
                token_cache = json.load(cf)
        except Exception:
            pass

    def _get_metrics(path):
        nonlocal cache_updated
        try:
            mtime = os.path.getmtime(path)
            # Anti-swallow guard: Local files can be locked during git stash pops.
            # Only trust the cache if the file timestamp matches AND the token count is > 0.
            if path in token_cache and token_cache[path][0] == mtime and token_cache[path][1] > 0:
                return token_cache[path][1], token_cache[path][2]
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            t_cnt = count_tokens(content)
            b_cnt = len(content.encode('utf-8'))
            if t_cnt > 0:
                token_cache[path] = [mtime, t_cnt, b_cnt]
                cache_updated = True
            return t_cnt, b_cnt
        except Exception:
            return 0, 0

    if args.article:
        # Executable Telemetry Mode: Generate the prompt_foo.py command
        slice_obj = parse_slice_arg(args.article)
        if slice_obj is not None:
            sliced_metadata = metadata[slice_obj] if isinstance(slice_obj, slice) else [metadata[slice_obj]]
            
            if not sliced_metadata:
                print("# No articles matched the provided slice.", file=sys.stderr)
            else:
                # Build the multiline command safely
                command_lines = ["python prompt_foo.py -l [:] --no-tree \\"]
                for i, item in enumerate(sliced_metadata):
                    # Add the continuation backslash to all but the last item
                    line = f"  --decanter {item['path']}"
                    if i < len(sliced_metadata) - 1:
                        line += " \\"
                    command_lines.append(line)
                
                print("\n".join(command_lines))
        else:
            print(f"❌ Invalid slice format: {args.article}. Use format like '[-5:]'", file=sys.stderr)
    else:
        # Standard Mode: Heavy Lifting & Streaming Output
        if args.fmt == 'paths':
            for item in metadata:
                print(item['path'], flush=True)
        elif args.fmt == 'slugs':
            import re
            for item in metadata:
                stem = os.path.splitext(os.path.basename(item['path']))[0]
                slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', stem)
                print(slug, flush=True)
        elif args.fmt == 'dated-slugs':
            import re
            target_config = targets[target_key]
            base_url = target_config.get('base_url', 'https://mikelev.in').rstrip('/')
            for item in metadata:
                stem = os.path.splitext(os.path.basename(item['path']))[0]
                slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', stem)
                tokens, _ = _get_metrics(item['path'])
                # OPTIMIZATION: Complete hypermedia routing parity with fully qualified absolute URLs.
                # Leverages YAML frontmatter permalinks falling back to default route structures.
                permalink = item.get('permalink', '').rstrip('/')
                if not permalink:
                    permalink = f"/futureproof/{slug}"
                url_target = f"{base_url}{permalink}/index.md"
                if tokens > 0:
                    print(f"{item['date']} [{tokens//1000}k] {url_target}", flush=True)
                else:
                    print(f"{item['date']} [?k] {url_target}", flush=True)
        else:
            for idx, item in enumerate(metadata, start=1):
                filepath = item['path']
                tokens, bytes_count = _get_metrics(filepath)
                if tokens > 0:
                    order = item['sort_order']
                    print(f"{filepath}  # [Idx: {idx} | Order: {order} | Tokens: {tokens:,} | Bytes: {bytes_count:,}]", flush=True)
                else:
                    print(f"# Error processing {filepath}", file=sys.stderr)

    if cache_updated:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as cf:
                json.dump(token_cache, cf, indent=2)
        except Exception:
            pass


def get_holographic_article_data(target_dir: str) -> list[dict]:
    """
    The Universal Semantic Extractor.
    Reads Jekyll Markdown and associated JSON shards to create dense context objects.
    """
    target_path = Path(target_dir).expanduser().resolve()
    context_dir = target_path / "_context"
    
    metadata = []
    
    for filename in os.listdir(target_path):
        filepath = target_path / filename
        if not filepath.is_file() or not filename.endswith(('.md', '.markdown')):
            continue
            
        try:
            # 1. Fast YAML Extraction
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if not content.startswith('---'):
                continue
                
            parts = content.split('---', 2)
            if len(parts) < 3:
                continue
                
            fm = yaml.safe_load(parts[1]) or {}
            
            # 2. Basic Metadata
            date_str = filename[:10]
            post_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            sort_order = int(fm.get('sort_order', 0))
            
            # 3. Holographic JSON Shard Extraction (The Flattener logic)
            stem = filepath.stem
            json_path = context_dir / f"{stem}.json"
            
            kw_str, sub_str, sum_str = "", "", ""
            if json_path.exists():
                try:
                    with open(json_path, 'r', encoding='utf-8') as jf:
                        shard = json.load(jf)
                        kw_str = ", ".join(shard.get('kw', []))
                        sub_str = ", ".join(shard.get('sub', []))
                        sum_str = shard.get('s', '').replace('\n', ' ').strip()
                except Exception:
                    pass

            metadata.append({
                'path': str(filepath),
                'filename': filename,
                'date': post_date,
                'sort_order': sort_order,
                'title': fm.get('title', 'Untitled'),
                'permalink': fm.get('permalink', ''),
                'summary': fm.get('meta_description', fm.get('description', '')),
                'shard_kw': kw_str,
                'shard_sub': sub_str,
                'shard_sum': sum_str,
                # We defer expensive token/byte counting until needed by the caller
            })
            
        except Exception:
            continue
            
    # Sort first by date (newest first), then by the YAML sort_order
    metadata.sort(key=lambda p: (p['date'], p['sort_order']), reverse=True)
    return metadata

if __name__ == "__main__":
    main()
