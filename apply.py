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

        # 3. INDENTATION-AGNOSTIC EXACT MATCH
        content_lines = content.split('\n')
        search_lines = search_block.split('\n')
        
        # Strip trailing newlines from search block to prevent edge cases
        while search_lines and not search_lines[-1].strip():
            search_lines.pop()
        while search_lines and not search_lines[0].strip():
            search_lines.pop(0)

        match_start_idx = -1
        match_count = 0
        search_len = len(search_lines)

        for i in range(len(content_lines) - search_len + 1):
            match = True
            for j in range(search_len):
                if content_lines[i+j].lstrip() != search_lines[j].lstrip():
                    match = False
                    break
            if match:
                match_start_idx = i
                match_count += 1
        
        if match_count == 0:
            print(f"❌ Warning: SEARCH block not found in '{filename}'. Skipping.")
            success = False
            continue
        elif match_count > 1:
            print(f"❌ Warning: Ambiguous match (found {match_count} times) in '{filename}'. Skipping.")
            success = False
            continue
            
        # The Surgical Strike
        # Reconstruct the target area using the original indentation of the first matched line
        original_indent = len(content_lines[match_start_idx]) - len(content_lines[match_start_idx].lstrip())
        indent_str = content_lines[match_start_idx][:original_indent]
        
        # Apply the original indentation to the replacement block
        replace_lines = replace_block.split('\n')
        while replace_lines and not replace_lines[-1].strip():
            replace_lines.pop()
        while replace_lines and not replace_lines[0].strip():
            replace_lines.pop(0)
            
        indented_replace_lines = []
        for line in replace_lines:
            if line.strip():
                # Strip whatever indentation the LLM hallucinates, then apply the target file's indentation
                indented_replace_lines.append(indent_str + line.lstrip())
            else:
                indented_replace_lines.append("")

        new_content_lines = content_lines[:match_start_idx] + indented_replace_lines + content_lines[match_start_idx + search_len:]
        new_content = '\n'.join(new_content_lines)
        
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
