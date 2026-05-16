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
    print(f"🎯 TARGET ACQUIRED: {filepath} (Lines {start_line}-{end_line})")
    
    if not os.path.exists(filepath):
        print(f"❌ Error: Target file '{filepath}' not found.")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()

    # PHASE 1: The Wind Tunnel Baseline (Sanity Check)
    # Can we parse the host file as-is before doing anything?
    try:
        ast.parse('\n'.join(lines) + '\n')
    except SyntaxError:
        print("❌ Error: The target file ALREADY has invalid Python syntax. Airlock sealed.")
        return False
    start_idx = start_line - 1
    end_idx = end_line

    # Establish the ground truth baseline from the actual file
    orig_target_lines = lines[start_idx:end_idx]
    non_empty_orig = [line for line in orig_target_lines if line.strip()]
    ground_truth_indent = len(non_empty_orig[0]) - len(non_empty_orig[0].lstrip()) if non_empty_orig else 0

    # Wind tunnel: strip ground truth, re-apply, and test AST
    normalized_orig = [line[ground_truth_indent:] if line.strip() and len(line) >= ground_truth_indent else line for line in orig_target_lines]
    reconstructed_orig = [(" " * ground_truth_indent) + line if line.strip() else "" for line in normalized_orig]
    
    wind_tunnel_lines = lines[:start_idx] + reconstructed_orig + lines[end_idx:]
    try:
        ast.parse('\n'.join(wind_tunnel_lines) + '\n')
        print(f"🌬️  WIND TUNNEL PASSED: Original slice deconstructed and reconstructed seamlessly.")
    except SyntaxError:
        print("❌ WIND TUNNEL FAILED: Our baseline indent math breaks the original AST.")
        return False

    # PHASE 2: Parse the Diff into a pristine block of replacement text
    replacement_lines = []
    in_hunk = False
    
    for d_line in diff_content.splitlines():
        if d_line.startswith('@@ '):
            in_hunk = True
            continue
        if not in_hunk:
            continue
            
        if d_line.startswith('+') or d_line.startswith(' '):
            replacement_lines.append(d_line[1:])
        elif d_line == '':
            replacement_lines.append('')

    # PHASE 3: Dynamic Indentation Anchor & Iteration
    indent_step = detect_indent_step(lines)
   
    # Determine what baseline the LLM used for its hunk
    non_empty_repl = [line for line in replacement_lines if line.strip()]
    llm_baseline_indent = len(non_empty_repl[0]) - len(non_empty_repl[0].lstrip()) if non_empty_repl else 0

    # The deterministic shift needed to align the LLM's hunk with the file's ground truth
    indent_shift = ground_truth_indent - llm_baseline_indent    

    # Iterative AST Airlock
    candidate_offsets = [0, 1, -1, 2, -2, 3, -3, 4, -4]
    
    for offset_mult in candidate_offsets:
        current_shift = indent_shift + (offset_mult * indent_step)
        
        shifted_repl = []
        for line in replacement_lines:
            if not line.strip():
                shifted_repl.append("")
                continue
                
            if current_shift > 0:
                shifted_repl.append((" " * current_shift) + line)
            elif current_shift < 0:
                # Strip up to abs(current_shift) spaces safely
                strip_amount = min(abs(current_shift), len(line) - len(line.lstrip()))
                shifted_repl.append(line[strip_amount:])
            else:
                shifted_repl.append(line)

        # The Trace: Add a discrete Pep8-compliant tracker to the first modified line
        marked_repl = list(shifted_repl)
        for i, line in enumerate(marked_repl):
            if line.strip():
                if "  # 👀 AI-PATCH" not in line:
                    marked_repl[i] = line + "  # 👀 AI-PATCH"
                break

        # The Chisel Strike: Stitch the file back together
        new_file_lines = lines[:start_idx] + marked_repl + lines[end_idx:]
        proposed_file_str = '\n'.join(new_file_lines) + '\n'

        try:
            ast.parse(proposed_file_str)
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
