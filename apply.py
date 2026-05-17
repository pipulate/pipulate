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
    # A more robust regex that ignores bracket width variations and code fence lines
    block_pattern = re.compile(
        r'(?:(?:File|Target):\s*`?([^`\s*]+)`?\s*\n)?[\[{]{3,5}SEARCH[\]}]{3,5}\n(.*?)\n[\[{]{3,5}DIVIDER[\]}]{3,5}\n(.*?)\n[\[{]{3,5}REPLACE[\]}]{3,5}',
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
            # DIAGNOSTIC: Show context around this SEARCH block in the raw payload
            # Find the position of the search block content in the payload
            search_snippet = search_block[:80].split('\n')[0]
            # Find surrounding lines in payload
            payload_lines = payload.split('\n')
            for li, pl in enumerate(payload_lines):
                if search_snippet and search_snippet.strip() in pl:
                    ctx_start = max(0, li - 4)
                    ctx_end = min(len(payload_lines), li + 3)
                    print(f"\n--- DIAGNOSTIC: Payload context around SEARCH block ---")
                    print(f"  The [[[SEARCH]]] block was found but no 'Target: `filename`' line")
                    print(f"  immediately preceded it. Here is what WAS there:")
                    for ci, cl in enumerate(payload_lines[ctx_start:ctx_end], start=ctx_start+1):
                        print(f"  {ci:4d}: {repr(cl)}")
                    print(f"\n  FIX: Add 'Target: `path/to/file`' on the line")
                    print(f"  immediately before the [[[SEARCH]]] marker, no blank lines between.")
                    print(f"--- END DIAGNOSTIC ---\n")
                    break
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
            # DIAGNOSTIC: Find closest matching window in target file
            search_lines = search_block.split('\n')
            content_lines = content.split('\n')
            search_len = len(search_lines)
            best_score, best_idx = 0, 0
            for i in range(max(0, len(content_lines) - search_len + 1)):
                score = sum(1 for j in range(min(search_len, len(content_lines) - i))
                            if content_lines[i+j].lstrip() == search_lines[j].lstrip())
                if score > best_score:
                    best_score, best_idx = score, i
            print(f"\n--- DIAGNOSTIC: First line of your SEARCH block ---")
            print(f"  SEARCH repr : {repr(search_lines[0])}")
            file_first = content_lines[best_idx] if best_idx < len(content_lines) else ''
            print(f"  FILE nearest: {repr(file_first)}")
            search_indent = len(search_lines[0]) - len(search_lines[0].lstrip())
            file_indent = len(file_first) - len(file_first.lstrip())
            if search_indent != file_indent:
                print(f"  ⚠ Indentation mismatch: SEARCH has {search_indent} spaces, file has {file_indent} spaces.")
                corrected = (' ' * file_indent) + search_lines[0].lstrip()
                print(f"  ✓ Corrected first line should be: {repr(corrected)}")
            if search_lines[0].lstrip() != file_first.lstrip():
                print(f"  ⚠ Content mismatch even after stripping: lines differ beyond whitespace.")
            # Also show the full SEARCH block so the LLM can compare against the source
            print(f"--- YOUR SUBMITTED SEARCH BLOCK (verbatim) ---")
            for li, sl in enumerate(search_lines, start=1):
                print(f"  {li:3d}: {repr(sl)}")
            print(f"--- END SUBMITTED SEARCH BLOCK ---\n")
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
                err_lines = new_content.split('\n')
                err_lineno = e.lineno or 0
                start = max(0, err_lineno - 3)
                end = min(len(err_lines), err_lineno + 2)
                print("--- DIAGNOSTIC: Context around syntax error ---")
                for i, ln in enumerate(err_lines[start:end], start=start+1):
                    marker = " >>>" if i == err_lineno else "    "
                    print(f"{marker} {i:4d}: {ln}")
                print("--- END DIAGNOSTIC ---")
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
