#!/usr/bin/env python3
import re
import argparse
from pathlib import Path
import common

# Regex to find the pure commit hash line: [main 15372bf4]
COMMIT_REGEX = re.compile(r'\[(?:main|master)\s+([a-f0-9]{7,40})\]')

# Regex to find the remote repository line
REMOTE_REGEX = re.compile(r'To\s+github\.com:([\w-]+/[\w-]+)\.git')

# Regex to find and CLEAN the broken inline HTML from the previous script iteration
OLD_BROKEN_LINK_REGEX = re.compile(r'\[(main|master)\s+<a href="[^"]+"\s+target="_blank">([a-f0-9]+)</a>\]\s+\(<a href="[^"]+"\s+target="_blank">raw</a>\)')

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # --- PASS 1: THE CLEANER ---
    # Revert any previously mangled HTML injections back to literal terminal text
    if '<a href=' in content and 'raw</a>' in content:
        content = OLD_BROKEN_LINK_REGEX.sub(r'[\1 \2]', content)

    # --- PASS 2: THE EXTRACTOR ---
    remote_match = REMOTE_REGEX.search(content)
    if not remote_match:
        # No remote repository found, we can't build links.
        # But we still might need to save if Pass 1 cleaned up old broken links.
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False

    repo_path = remote_match.group(1)

    # Extract all unique commit hashes, preserving order of appearance
    hashes = []
    for match in COMMIT_REGEX.finditer(content):
        h = match.group(1)
        if h not in hashes:
            hashes.append(h)

    if not hashes:
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False

    # --- PASS 3: THE LEDGER INJECTION ---
    # Check if a ledger already exists so we can be idempotent
    LEDGER_START = '<div class="commit-ledger"'
    if LEDGER_START in content:
        # Strip out the old ledger to rebuild a fresh one
        content = re.sub(r'<div class="commit-ledger".*?</div>\n*', '', content, flags=re.DOTALL)

    # Construct the new HTML Ledger Box
    ledger_html = [
        '<div class="commit-ledger" style="background: var(--pico-card-background-color); border: 1px solid var(--pico-muted-border-color); border-radius: var(--pico-border-radius); padding: 1rem; margin-bottom: 2rem;">',
        '  <h4 style="margin-top: 0; margin-bottom: 0.5rem; font-size: 1rem;">🔗 Verified Commits in this Article:</h4>',
        '  <ul style="margin-bottom: 0; font-family: monospace; font-size: 0.9rem;">'
    ]

    for h in hashes:
        web_url = f"https://github.com/{repo_path}/commit/{h}"
        raw_url = f"https://github.com/{repo_path}/raw/{h}/"
        ledger_html.append(f'    <li><a href="{web_url}" target="_blank">{h}</a> (<a href="{raw_url}" target="_blank">raw</a>)</li>')

    ledger_html.append('  </ul>')
    ledger_html.append('</div>\n')
    
    ledger_block = "\n".join(ledger_html)

    # Inject immediately after the Journal Entry anchor
    ANCHOR = "## Technical Journal Entry Begins\n\n"
    if ANCHOR in content:
        content = content.replace(ANCHOR, ANCHOR + ledger_block)
    else:
        # Fallback if the anchor is missing: put it right after the frontmatter
        parts = content.split('---', 2)
        if len(parts) >= 3:
            content = f"---{parts[1]}---\n\n{ledger_block}{parts[2]}"

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True

    return False

def main():
    parser = argparse.ArgumentParser(description="Extract commit hashes and inject a top-level Ledger.")
    common.add_standard_arguments(parser)
    args = parser.parse_args()

    target_dir = common.get_target_path(args)
    print(f"🔗 Rebuilding GitHub Commit Ledgers in {target_dir.name}...")
    
    modified_count = 0
    for md_file in target_dir.glob("*.md"):
        if process_file(md_file):
            modified_count += 1
            print(f"  ✅ Ledger Updated: {md_file.name}")
            
    print(f"✨ Ledger injection complete. Modified {modified_count} files.")

if __name__ == "__main__":
    main()