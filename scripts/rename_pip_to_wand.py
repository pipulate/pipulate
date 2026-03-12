#!/usr/bin/env python3
"""
scripts/rename_pip_to_wand.py
Surgically renames the variable/attribute `pip` to `wand` across python files.
Uses the Python standard library `tokenize` module to safely ignore strings and comments.
"""
import os
import tokenize
from pathlib import Path

def process_file(filepath):
    # Read original source to preserve exact formatting
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    # Generate tokens from bytes
    with open(filepath, 'rb') as f:
        try:
            tokens = list(tokenize.tokenize(f.readline))
        except tokenize.TokenError as e:
            print(f"⚠️ Could not tokenize {filepath.name}: {e}")
            return False

    lines = source.splitlines(keepends=True)
    changed = False
    
    # Collect replacements per line
    # Format: line_index -> list of (start_col, end_col, new_text)
    replacements = {} 
    
    for tok in tokens:
        # We only care about programmatic names (variables, attributes, functions)
        # This naturally ignores comments, strings, and docstrings.
        if tok.type == tokenize.NAME and tok.string == 'pip':
            line_idx = tok.start[0] - 1  # tokens are 1-indexed, lists are 0-indexed
            start_col = tok.start[1]
            end_col = tok.end[1]
            
            if line_idx not in replacements:
                replacements[line_idx] = []
            replacements[line_idx].append((start_col, end_col, 'wand'))
            changed = True

    if not changed:
        return False

    # Apply replacements from right-to-left (reverse column order) 
    # so we don't mess up the offset coordinates for multiple replacements on one line
    for line_idx, reps in replacements.items():
        reps.sort(key=lambda x: x[0], reverse=True)
        line = lines[line_idx]
        for start_col, end_col, new_text in reps:
            line = line[:start_col] + new_text + line[end_col:]
        lines[line_idx] = line
        
    # Write back to file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("".join(lines))
        
    return True

def main():
    apps_dir = Path('assets/nbs/imports')
    if not apps_dir.exists() or not apps_dir.is_dir():
        print("❌ Error: apps/ directory not found. Run this from the project root.")
        return

    changed_count = 0
    file_count = 0

    print("🪄 Splicing 'pip' into 'wand'...\n")

    for filepath in apps_dir.glob('*.py'):
        if filepath.name.startswith('__'):
            continue
            
        if process_file(filepath):
            print(f"✅ Updated: {filepath.name}")
            changed_count += 1
        file_count += 1

    print(f"\n🎯 Done! Processed {file_count} files, updated {changed_count} files.")

if __name__ == '__main__':
    main()
