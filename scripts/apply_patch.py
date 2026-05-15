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

def apply_larry_wall_patch(filepath: str, start_line: int, end_line: int, diff_content: str) -> bool:
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

    original_slice = '\n'.join(lines[start_idx:end_idx])
    
    # 2. Build the Myopic Generative Prompt
    system_prompt = "You are a surgical Python AST editor. You output ONLY valid Python code. No markdown formatting, no backticks, no explanations."
    
    prompt = f"""
Apply the following unified diff to the Original Python Slice.
Ensure the resulting code maintains exact structural indentation relative to the slice.
Output ONLY the final mutated Python code block that will perfectly replace the original slice. Do NOT wrap in backticks.

ORIGINAL SLICE:
{original_slice}

DIFF TO APPLY:
{diff_content}
"""

    # 3. The Syntax Airlock Validator
    def ast_validator(ai_response):
        clean_response = re.sub(r'^```python\n|^```\n|```$', '', ai_response.strip(), flags=re.MULTILINE)
        proposed_file_lines = lines[:start_idx] + clean_response.splitlines() + lines[end_idx:]
        proposed_file_str = '\n'.join(proposed_file_lines) + '\n'
        
        try:
            ast.parse(proposed_file_str)
            return True, ""
        except Exception:
            return False, traceback.format_exc()

    # 4. Engage the Sovereign Actuator
    db_path = str(Path(__file__).resolve().parent.parent / "Notebooks" / "data" / "pipeline.sqlite")
    wand = Pipulate(db_path=db_path)
    final_slice_string = wand.resilient_prompt(prompt, system_prompt=system_prompt, validator=ast_validator)
    
    if not final_slice_string:
        print("❌ PATCH FAILED: Could not generate an AST-valid mutation across the model cascade.")
        return False
        
    # 5. Write the mutated, validated state back to disk
    clean_response = re.sub(r'^```python\n|^```\n|```$', '', final_slice_string.strip(), flags=re.MULTILINE)
    new_file_lines = lines[:start_idx] + clean_response.splitlines() + lines[end_idx:]
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_file_lines) + '\n')
        
    print(f"✅ AST AIRLOCK PASSED: Patch applied and validated in memory.")
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
