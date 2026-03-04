#!/usr/bin/env python3
"""
ls_semantic.py (List Semantic Articles)

The Semantic Flattener. Reads Jekyll Markdown frontmatter and corresponding 
JSON context shards, compressing them into an ultra-dense, 1-dimensional 
string to maximize LLM context window efficiency (bypassing the 1MB limit).
"""

import os
import sys
import json
import yaml
import re
import argparse
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "articleizer"
TARGETS_FILE = CONFIG_DIR / "targets.json"

def load_targets():
    if TARGETS_FILE.exists():
        try:
            with open(TARGETS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {"1": {"name": "Local Project (Default)", "path": "./_posts"}}

def extract_metadata(filepath):
    """Fast extraction of permalink from YAML frontmatter."""
    permalink = ""
    title = ""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            if first_line.startswith('---'):
                yaml_content = []
                for line in f:
                    if line.startswith('---'): break
                    yaml_content.append(line)
                fm = yaml.safe_load(''.join(yaml_content)) or {}
                permalink = fm.get('permalink', '')
                title = fm.get('title', '')
    except Exception:
        pass
    
    # Fallback to guessing permalink from filename if missing
    if not permalink:
        filename = os.path.basename(filepath)
        slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', filename).replace('.md', '')
        permalink = f"/{slug}/"
        
    return permalink, title

def main():
    parser = argparse.ArgumentParser(description="Generate ultra-dense semantic site map.")
    parser.add_argument('-t', '--target', type=str, default="1", help="Target ID from targets.json")
    args = parser.parse_args()

    targets = load_targets()
    if args.target not in targets:
        print(f"❌ Invalid target key: {args.target}", file=sys.stderr)
        sys.exit(1)

    target_dir = Path(targets[args.target]['path']).expanduser().resolve()
    context_dir = target_dir / "_context"

    if not target_dir.is_dir():
        print(f"❌ Directory not found: {target_dir}", file=sys.stderr)
        sys.exit(1)

    # We output a header so the LLM knows exactly what it's looking at
    print("--- START: INTERLEAVED SEMANTIC MAP ---")
    print("Format: [URL] | [Title] | KW: [Keywords] | SUB: [Sub-topics] | SUM: [Summary]")
    
    file_count = 0
    missing_context = 0

    # Sort files to ensure deterministic output (newest first based on date prefix)
    files = sorted([f for f in os.listdir(target_dir) if f.endswith('.md')], reverse=True)

    for filename in files:
        filepath = target_dir / filename
        stem = filepath.stem
        json_path = context_dir / f"{stem}.json"
        
        permalink, title = extract_metadata(filepath)
        
        # Load the holographic shard
        kw_str, sub_str, sum_str = "", "", ""
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as jf:
                    shard = json.load(jf)
                    # Compress arrays into comma-separated strings
                    kw_str = ", ".join(shard.get('kw', []))
                    sub_str = ", ".join(shard.get('sub', []))
                    # Strip newlines from summary to guarantee 1-line-per-URL
                    sum_str = shard.get('s', '').replace('\n', ' ').strip()
            except Exception:
                missing_context += 1
        else:
            missing_context += 1

        # Construct the dense string
        # If a shard exists, we append the semantic payload. Otherwise, just the URL/Title.
        line = f"{permalink} | {title}"
        if kw_str or sub_str:
            line += f" | KW: {kw_str} | SUB: {sub_str} | SUM: {sum_str}"
            
        print(line)
        file_count += 1

    print("--- END: INTERLEAVED SEMANTIC MAP ---")
    
    # Send stats to stderr so they don't pollute the pipe if we capture stdout
    print(f"\n# Stats: {file_count} files processed. {missing_context} missing context shards.", file=sys.stderr)

if __name__ == "__main__":
    main()