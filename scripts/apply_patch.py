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

import traceback
import ast
from pathlib import Path

# Ensure pipulate is in the path for the wand
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pipulate import Pipulate
import config as CFG


def detect_indent_step(lines: list) -> int:
    from collections import Counter
    indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
    diffs = [abs(indents[i] - indents[i-1]) for i in range(1, len(indents)) if abs(indents[i] - indents[i-1]) > 0]
    if not diffs: return 4
    most_common = Counter(diffs).most_common(1)[0][0]
    return most_common if most_common in [2, 4, 8] else 4


def apply_larry_wall_patch(filepath: str, start_line: int, end_line: int, diff_content: str) -> bool:
    # Fine-tuning parameter for context lines grabbed above/below
    CONTEXT_BUFFER_LINES = 5  # Tweak this to require more or less surrounding context

    print(f"🎯 TARGET ACQUIRED: {filepath} (Lines {start_line}-{end_line})")
    
    if not os.path.exists(filepath):
        print(f"❌ Error: Target file '{filepath}' not found.")
        return False

    # 1. Load the live file and extract the Before slice 
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()

    # Convert 1-based inclusive coordinates to 0-based Python slice indices
    start_idx = start_line - 1
    end_idx = end_line

    # 1.5 Parse the unified diff into a pristine block of replacement text
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

    # 2. Dynamic Indentation Anchor & Iteration (Option A)
    indent_step = detect_indent_step(lines)
    
    # Determine baseline indentation from the target block
    orig_target_lines = lines[start_idx:end_idx]
    non_empty_orig = [line for line in orig_target_lines if line.strip()]
    baseline_indent = len(non_empty_orig[0]) - len(non_empty_orig[0].lstrip()) if non_empty_orig else 0
    
    # Normalize the replacement lines internally
    non_empty_repl = [line for line in replacement_lines if line.strip()]
    min_repl_indent = min(len(line) - len(line.lstrip()) for line in non_empty_repl) if non_empty_repl else 0
    normalized_repl = [line[min_repl_indent:] if line.strip() else "" for line in replacement_lines]
    
    # Iterative AST Airlock
    candidate_offsets = [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5]
    
    for offset_mult in candidate_offsets:
        target_indent = max(0, baseline_indent + (offset_mult * indent_step))
        prefix = " " * target_indent
        
        shifted_repl = [prefix + line if line else "" for line in normalized_repl]
        
        # The Trace: Add a discrete Pep8-compliant tracker to the first modified line
        marked_repl = list(shifted_repl)
        for i, line in enumerate(marked_repl):
            if line.strip():
                if "  # AI-PATCH" not in line:
                    marked_repl[i] = line + "  # AI-PATCH"
                break

        # 3. The Chisel Strike: Stitch the file back together
        new_file_lines = lines[:start_idx] + marked_repl + lines[end_idx:]
        proposed_file_str = '\n'.join(new_file_lines) + '\n'

        # 4. The Syntax Airlock Validator
        try:
            ast.parse(proposed_file_str)
            # AST PASSED! Write the mutated state back to disk
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(proposed_file_str)
            print(f"✅ AST AIRLOCK PASSED: Patch applied and validated (Indent offset: {offset_mult * indent_step}).")
            return True
        except SyntaxError:
            continue

    print(f"❌ AST AIRLOCK FAILED: Exhausted indentation offsets, generated syntax remains invalid.")
    return False

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
    diff_match = re.search(r'\[The Larry Wall Patch\].*?(?:```|~~~)(?:diff)?\n(.*?)\n(?:```|~~~)', payload, re.DOTALL | re.IGNORECASE)
    
    if not diff_match:
        print("❌ Error: Could not parse [The Larry Wall Patch] enclosure.")
        sys.exit(1)

    diff_content = diff_match.group(1).strip()
    
    # Execute the transposition
    apply_larry_wall_patch(filepath, start_line, end_line, diff_content)

if __name__ == "__main__":
    main()
