#!/usr/bin/env python3
"""
scripts/articles/confluenceizer.py
The Idempotent Confluence Publishing Adapter.
Loads targets from blogs.json, extracts the Confluence metadata surface,
and sequences local Markdown posts into the wiki page tree.
"""

import sys
import html
import re
import argparse
import os
import json
import base64
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import urlparse
from pathlib import Path
import frontmatter
import common

def _strip_front_matter(md_text: str) -> str:
    """Drop a leading --- ... --- YAML block if present; otherwise pass through."""
    lines = md_text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:])
    return md_text

def _inline(text: str) -> str:
    """Escape HTML metacharacters first, then layer supported inline forms."""
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\.(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text

def markdown_to_storage(md_text: str) -> str:
    """Convert a narrow subset of Markdown to Confluence storage XML."""
    lines = _strip_front_matter(md_text).split("\n")
    out = []
    para = []

    def flush_para():
        if para:
            joined = " ".join(s.strip() for s in para).strip()
            if joined:
                out.append(f"<p>{_inline(joined)}</p>")
            para.clear()

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        if stripped.startswith("```"):
            flush_para()
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # consume the closing fence
            code = "\n".join(code_lines)
            code = code.replace("]]>", "]]]]><![CDATA[>")
            out.append(
                '<ac:structured-macro ac:name="code">'
                "<ac:plain-text-body><![CDATA[" + code + "]]></ac:plain-text-body>"
                "</ac:structured-macro>"
            )
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush_para()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2).strip())}</h{level}>")
            i += 1
            continue

        if not stripped:
            flush_para()
            i += 1
            continue

        para.append(lines[i])
        i += 1

    flush_para()
    return "".join(out)

def main():
    parser = argparse.ArgumentParser(description="Publish local markdown articles to Confluence Cloud.")
    common.add_standard_arguments(parser)
    args = parser.parse_args()

    targets = common.load_targets()
    target_key = str(args.target)

    if target_key not in targets:
        print(f"❌ Error: Target key '{target_key}' not found in blogs.json.")
        sys.exit(1)

    config = targets[target_key]
    print(f"🔒 Locked Target: {config.get('name')} ({config.get('path')})")

    parent_id = config.get("confluence_parent_id")
    if not parent_id:
        print(f"❌ Aborted: Target '{target_key}' does not define a 'confluence_parent_id' in blogs.json.")
        sys.exit(1)

    print(f"📡 Anchored Confluence Parent ID: {parent_id}")

    posts_dir = Path(config["path"]).expanduser().resolve()
    if not posts_dir.is_dir():
        print(f"❌ Error: Posts directory does not exist: {posts_dir}")
        sys.exit(1)

    md_files = sorted(list(posts_dir.glob("*.md")))
    print(f"📝 Found {len(md_files)} candidate document(s) for publishing queue.")

    if not md_files:
        print("🛑 Queue empty. Nothing to parse.")
        return

    # Handshake validation pass on the first document in the queue
    first_file = md_files[0]
    print(f"\n🔍 Handshake Verification Pass: Analyzing '{first_file.name}'...")
    
    try:
        post = frontmatter.load(first_file)
        print(f"  • Frontmatter Title: {post.metadata.get('title', 'None')}")
        print(f"  • Frontmatter Date:  {post.metadata.get('date', 'None')}")
        
        storage_xml = markdown_to_storage(post.content)
        print("\n--- Compiled Storage XML Representation Preview ---")
        print(storage_xml[:500] + ("..." if len(storage_xml) > 500 else ""))
        print("---------------------------------------------------")
        print("✅ Local conversion pass successful.")
    except Exception as e:
        print(f"❌ Structural load or compilation failure: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
