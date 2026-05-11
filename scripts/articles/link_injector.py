#!/usr/bin/env python3
import re
import argparse
from pathlib import Path
import common

# Regex to find the commit hash line: [main 15372bf4] Commit message
COMMIT_REGEX = re.compile(r'\[(main|master)\s+([a-f0-9]+)\]')
# Regex to find the remote repository line: To github.com:pipulate/pipulate.git
REMOTE_REGEX = re.compile(r'To\s+github\.com:([\w-]+/[\w-]+)\.git')

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Early exit if the file already contains our injected links
    if 'href="https://github.com' in content:
        return False

    # Extract the repository path (e.g., 'pipulate/pipulate')
    remote_match = REMOTE_REGEX.search(content)
    if not remote_match:
        return False  # No remote found, can't construct the URL
    repo_path = remote_match.group(1)

    # Function to replace the hash with a link
    def link_replacer(match):
        branch = match.group(1)
        hash_val = match.group(2)
        # Construct the minimal Web UI link
        web_url = f"https://github.com/{repo_path}/commit/{hash_val}"
        # Construct the Raw link (We link the text "raw" for minimal intrusion)
        raw_url = f"https://github.com/{repo_path}/raw/{hash_val}/" 
        
        # Inject the HTML
        # Result: [main <a href="...">15372bf4</a>] (<a href="...">raw</a>)
        return f'[{branch} <a href="{web_url}" target="_blank">{hash_val}</a>] (<a href="{raw_url}" target="_blank">raw</a>)'

    # Apply the replacement
    new_content = COMMIT_REGEX.sub(link_replacer, content)

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

def main():
    parser = argparse.ArgumentParser(description="Inject GitHub links into terminal blocks.")
    common.add_standard_arguments(parser)
    args = parser.parse_args()

    target_dir = common.get_target_path(args)
    print(f"🔗 Injecting GitHub links in {target_dir.name}...")
    
    modified_count = 0
    for md_file in target_dir.glob("*.md"):
        if process_file(md_file):
            modified_count += 1
            print(f"  ✅ Linked: {md_file.name}")
            
    print(f"✨ Link injection complete. Modified {modified_count} files.")

if __name__ == "__main__":
    main()