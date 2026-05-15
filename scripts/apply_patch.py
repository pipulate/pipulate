#!/usr/bin/env python3
"""
apply_patch.py

The Deterministic Actuator. 
Reads a raw LLM response from stdin, extracts the Target Coordinates 
and the Unified Diff, and performs a surgical array-slice patch on the target file.

Usage: cat ai_response.md | python scripts/apply_patch.py
"""

import sys
import re
import os

def apply_larry_wall_patch(filepath: str, start_line: int, end_line: int, diff_content: str) -> bool:
    print(f"🎯 TARGET ACQUIRED: {filepath} (Lines {start_line}-{end_line})")
    
    if not os.path.exists(filepath):
        print(f"❌ Error: Target file '{filepath}' not found.")
        return False
    
    # 1. Parse the unified diff into a pristine block of replacement text
    replacement_lines = []
    in_hunk = False
    
    for d_line in diff_content.splitlines():
        if d_line.startswith('@@ '):
            in_hunk = True
            continue
        if not in_hunk:
            continue
            
        # Keep additions and context, strip the prefix character
        if d_line.startswith('+') or d_line.startswith(' '):
            replacement_lines.append(d_line[1:])
        elif d_line == '': # Edge case for empty context lines
            replacement_lines.append('')
        # Lines starting with '-' are ignored (they are the old state)

    # 2. Open the live file and read it as an array
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()

    # Convert 1-based inclusive coordinates to 0-based Python slice indices
    start_idx = start_line - 1
    end_idx = end_line

    # 3. The Chisel Strike: Stitch the file back together
    new_file_lines = lines[:start_idx] + replacement_lines + lines[end_idx:]

    # 4. Write the mutated state back to disk
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_file_lines) + '\n')

    print(f"✅ PATCH APPLIED: Swapped out {end_idx - start_idx} lines for {len(replacement_lines)} new lines.")
    return True

def main():
    # Read the raw Markdown payload from the Unix pipe
    payload = sys.stdin.read()

    # Non-greedy regex to find the coordinates
    coord_match = re.search(r'\[Target Coordinates\].*?File:\s*([^\s]+).*?Start:\s*(\d+).*?End:\s*(\d+)', payload, re.DOTALL | re.IGNORECASE)

    if not coord_match:
        print("❌ Error: Could not parse [Target Coordinates] block.")
        sys.exit(1)

    filepath = coord_match.group(1).strip()
    start_line = int(coord_match.group(2))
    end_line = int(coord_match.group(3))

    # Non-greedy regex to find the diff payload, embracing the gravity of backticks
    diff_match = re.search(r'\[The Larry Wall Patch\].*?```(?:diff)?\n(.*?)\n``', payload, re.DOTALL | re.IGNORECASE)
    
    if not diff_match:
        print("❌ Error: Could not parse [The Larry Wall Patch] enclosure.")
        sys.exit(1)

    diff_content = diff_match.group(1).strip()
    
    # Execute the transposition
    apply_larry_wall_patch(filepath, start_line, end_line, diff_content)

if __name__ == "__main__":
    main()
