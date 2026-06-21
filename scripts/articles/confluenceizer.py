#!/usr/bin/env python3
"""
scripts/articles/confluenceizer.py
The Idempotent Confluence Publishing Adapter.
Loads targets from blogs.json, extracts the Confluence metadata surface,
and sequences local Markdown posts into the wiki page tree.
"""

import os
import sys
import argparse
from pathlib import Path
import common

def main():
    parser = argparse.ArgumentParser(description="Publish local markdown articles to Confluence Cloud.")
    common.add_standard_arguments(parser)
    args = parser.parse_args()

    # 1. Resolve Target Config via common framework utilities
    targets = common.load_targets()
    target_key = str(args.target)

    if target_key not in targets:
        print(f"❌ Error: Target key '{target_key}' not found in blogs.json.")
        sys.exit(1)

    config = targets[target_key]
    print(f"🔒 Locked Target: {config.get('name')} ({config.get('path')})")

    # 2. Extract Confluence Environmental Anchor
    parent_id = config.get("confluence_parent_id")
    if not parent_id:
        print(f"❌ Aborted: Target '{target_key}' does not define a 'confluence_parent_id' in blogs.json.")
        sys.exit(1)

    print(f"📡 Anchored Confluence Parent ID: {parent_id}")

    # 3. Discovery Pass (Zero-Network Falsifying Preflight)
    posts_dir = Path(config["path"]).expanduser().resolve()
    if not posts_dir.is_dir():
        print(f"❌ Error: Posts directory does not exist: {posts_dir}")
        sys.exit(1)

    md_files = sorted(list(posts_dir.glob("*.md")))
    print(f"📝 Found {len(md_files)} candidate document(s) for publishing queue:")
    for f in md_files:
        print(f"   • {f.name}")

if __name__ == "__main__":
    main()
