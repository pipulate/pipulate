#!/usr/bin/env python3
"""
Sanitizes the Nginx _redirects.map file.
Ensures valid syntax, escapes danger, deduplicates, and enforces semicolons.
Drops offending lines entirely to prevent Nginx reload failures.
"""

import sys
import argparse
from pathlib import Path
import common

def sanitize_map_file(filepath):
    if not filepath.exists():
        print(f"⚠️ Warning: Redirect map not found at {filepath}")
        return

    print(f"🧹 Sanitizing Nginx map: {filepath.name}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    clean_lines = []
    dropped_count = 0
    fixed_count = 0
    seen_sources = set()

    for line in lines:
        stripped = line.strip()
        
        if not stripped or stripped.startswith('#'):
            clean_lines.append(line)
            continue

        # Split strictly by spaces. Nginx map lines cannot contain unescaped spaces.
        parts = stripped.split()
        
        # If there are more or less than 2 parts, there are spaces in the URL or it's malformed
        if len(parts) != 2:
            print(f"  ❌ Dropped (Spaces/Bad Format): {stripped}")
            dropped_count += 1
            continue

        source, target = parts

        # 1. Drop dangerous characters (Markdown bleed-over, unmatched regex)
        dangerous_chars = ['{', '}', '[', ']', '(', ')', '*', '|', '"', "'", '`']
        if any(char in target for char in dangerous_chars):
            print(f"  ❌ Dropped (Dangerous Target Syntax): {stripped}")
            dropped_count += 1
            continue
            
        if any(char in source for char in dangerous_chars):
            print(f"  ❌ Dropped (Corrupt Source Syntax): {stripped}")
            dropped_count += 1
            continue

        # 2. Deduplication (Nginx throws fatal error on duplicate keys)
        if source in seen_sources:
            print(f"  ❌ Dropped (Duplicate Source): {stripped}")
            dropped_count += 1
            continue
        seen_sources.add(source)

        # 3. Enforce the Semicolon
        if not target.endswith(';'):
            target = target.rstrip(';') + ';'
            fixed_count += 1

        clean_lines.append(f"    {source} {target}\n")

    if dropped_count > 0 or fixed_count > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(clean_lines)
        print(f"✅ Sanitization complete. Fixed {fixed_count} lines. Dropped {dropped_count} invalid lines.")
    else:
        print("✅ Map file is already pristine.")

def main():
    parser = argparse.ArgumentParser(description="Sanitize Nginx redirect maps.")
    common.add_target_argument(parser)
    args = parser.parse_args()

    target_dir = common.get_target_path(args)
    repo_root = target_dir.parent
    map_file = repo_root / "_redirects.map"
    
    sanitize_map_file(map_file)

if __name__ == "__main__":
    main()