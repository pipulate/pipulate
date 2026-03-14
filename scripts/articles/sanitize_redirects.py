#!/usr/bin/env python3
"""
Sanitizes the Nginx _redirects.map file.
Ensures valid syntax, escapes danger, and enforces semicolons.
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

    for line in lines:
        stripped = line.strip()
        
        # Keep comments and empty lines
        if not stripped or stripped.startswith('#'):
            clean_lines.append(line)
            continue

        # Nginx map lines must have two parts: the source and the target
        parts = stripped.split(maxsplit=1)
        if len(parts) != 2:
            print(f"  ❌ Dropped (Invalid Format): {stripped}")
            dropped_count += 1
            continue

        source, target = parts

        # 1. Reject dangerous characters
        # If the target somehow contains a curly brace, it will break the Nginx map block
        if '{' in target or '}' in target:
            print(f"  ❌ Dropped (Dangerous Syntax): {stripped}")
            dropped_count += 1
            continue

        # 2. Enforce the Semicolon
        if not target.endswith(';'):
            # It might have trailing spaces or comments after the target. 
            # We strip it, add the semicolon, and reconstruct.
            target = target.rstrip(';') + ';'
            fixed_count += 1

        # Reconstruct the line safely
        safe_line = f"    {source} {target}\n"
        clean_lines.append(safe_line)

    # Write it back if we made changes
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

    # Resolve target directory using common
    target_dir = common.get_target_path(args)
    repo_root = target_dir.parent
    
    map_file = repo_root / "_redirects.map"
    
    sanitize_map_file(map_file)

if __name__ == "__main__":
    main()