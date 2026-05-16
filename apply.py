#!/usr/bin/env python3
"""
apply_patch.py

The Deterministic Actuator.
Reads a raw LLM response from stdin, extracts the SEARCH/REPLACE blocks,
and performs a deterministic string replacement patch on the target file.

Usage: cat ai_response.md | python scripts/apply_patch.py
"""

import sys
import re
import os

def apply_search_replace_patch(payload: str) -> bool:
    # 1. NORMALIZE PAYLOAD WHITESPACE
    # Convert non-breaking spaces to regular spaces and normalize line endings
    payload = payload.replace('\xa0', ' ').replace('\r\n', '\n')

    # Regex to find an optional 'File:' indicator followed by SEARCH/DIVIDER/REPLACE blocks
    block_pattern = re.compile(
        r'(?:(?:File|Target):\s*`?([^`\s*]+)`?\s*\n.*?)?\[\[\[SEARCH\]\]\]\n(.*?)\n\[\[\[DIVIDER\]\]\]\n(.*?)\n\[\[\[REPLACE\]\]\]',
        re.DOTALL | re.IGNORECASE
    )

    matches = block_pattern.findall(payload)
    if not matches:
        print("❌ Error: No [[[SEARCH]]] / [[[REPLACE]]] blocks found in payload.")
        return False

    success = True
    for filename_match, search_block, replace_block in matches:
        filename = filename_match.strip('` \t\n') if filename_match else None
        
        if not filename:
            print("❌ Error: Missing target filename before the SEARCH block.")
            success = False
            continue

        if not os.path.exists(filename):
            print(f"❌ Error: Target file '{filename}' not found.")
            success = False
            continue

        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()

        # 2. NORMALIZE TARGET FILE WHITESPACE
        content = content.replace('\xa0', ' ').replace('\r\n', '\n')
        search_block = search_block.replace('\xa0', ' ').replace('\r\n', '\n')
        replace_block = replace_block.replace('\xa0', ' ').replace('\r\n', '\n')

        # The Exact Match Invariant
        match_count = content.count(search_block)
        
        if match_count == 0:
            print(f"❌ Warning: SEARCH block not found in '{filename}'. Skipping.")
            success = False
            continue
        elif match_count > 1:
            print(f"❌ Warning: Ambiguous match (found {match_count} times) in '{filename}'. Skipping.")
            success = False
            continue
            
        # The Surgical Strike
        new_content = content.replace(search_block, replace_block)
        
        # AST VALIDATION AIRLOCK (The Final Safeguard)
        if filename.endswith('.py'):
            import ast
            try:
                ast.parse(new_content)
            except SyntaxError as e:
                print(f"❌ Error: Patching '{filename}' aborted. Invalid Python syntax:\n   {e}")
                success = False
                continue

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        print(f"✅ DETERMINISTIC PATCH APPLIED: Successfully mutated '{filename}'.")
        
    return success

def main():
    # Read the raw Markdown payload from the Unix pipe
    payload = sys.stdin.read()
    apply_search_replace_patch(payload)

if __name__ == "__main__":
    main()
