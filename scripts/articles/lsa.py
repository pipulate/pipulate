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
TARGETS_FILE = CONFIG_DIR / "targets.json"

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
                return 0
            
            yaml_content = []
            for line in f:
                if line.startswith('---'):
                    break
                yaml_content.append(line)
                
            fm = yaml.safe_load(''.join(yaml_content)) or {}
            return int(fm.get('sort_order', 0))
    except Exception:
        return 0

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


def main():
    parser = argparse.ArgumentParser(description="Unified Article Lister & Analyzer")
    parser.add_argument('-t', '--target', type=str, help="Target ID from targets.json (e.g., '1', '3')")
    parser.add_argument('-g', '--gaps', action='store_true', help="Run and display the sort_order contiguity gap report")
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

    print(f"# 🎯 Target: {targets[target_key]['name']}\n", flush=True)

    metadata = []
    # --- PASS 1: FAST METADATA EXTRACTION ---
    for filename in os.listdir(target_dir):
        filepath = os.path.join(target_dir, filename)
        if not os.path.isfile(filepath) or not filename.endswith(('.md', '.markdown')):
            continue
            
        try:
            date_str = filename[:10]
            post_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            sort_order = fast_get_sort_order(filepath)
            
            metadata.append({
                'path': filepath,
                'date': post_date,
                'sort_order': sort_order
            })
        except (ValueError, TypeError):
            continue
            
    # Sort first by date, then by the YAML sort_order
    metadata.sort(key=lambda p: (p['date'], p['sort_order']))
    
    # --- PASS 2: HEAVY LIFTING & STREAMING OUTPUT ---
    for idx, item in enumerate(metadata, start=1):
        filepath = item['path']
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tokens = count_tokens(content)
            bytes_count = len(content.encode('utf-8'))
            order = item['sort_order']
            
            # Format explicitly for prompt_foo.py consumption
            print(f"{filepath}  # [Idx: {idx} | Order: {order} | Tokens: {tokens:,} | Bytes: {bytes_count:,}]", flush=True)
            
        except Exception as e:
            print(f"# Error processing {filepath}: {e}", file=sys.stderr)

    # --- PASS 3: GAP ANALYSIS (Optional) ---
    if args.gaps:
        anomalies = analyze_sort_order_contiguity(metadata)
        print_contiguity_report(anomalies)

if __name__ == "__main__":
    main()