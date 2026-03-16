#!/usr/bin/env python3
"""
Generates the definitive `llms.txt` file by fusing a static, 
highly curated "Prime Directive" header with a reverse-chronological 
dump of all article metadata, utilizing the `lsa.py` extraction logic.
"""

import sys
import argparse
from pathlib import Path
import lsa
import common

# --- CONFIGURATION ---
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HEADER_FILE = REPO_ROOT / "assets" / "prompts" / "llms_header.md"
OUTPUT_FILE = REPO_ROOT / "scripts" / "articles" / "llms.txt"


def build_payload(target_config: dict) -> str:
    """Generates the dense, reverse-chronological ledger using lsa.py logic."""
    target_path = Path(target_config['path']).expanduser().resolve()
    base_url = target_config.get('url', 'https://mikelev.in') # Default fallback
    
    print(f"📚 Extracting metadata from: {target_path}")
    # Leverage the Universal Semantic Extractor from lsa.py
    # Note: get_holographic_article_data already sorts Date (DESC) then sort_order (DESC)
    metadata = lsa.get_holographic_article_data(str(target_path))
    
    lines = []
    for item in metadata:
        # Resolve the URL
        slug = item.get('permalink', '').strip('/')
        if not slug:
            raw_slug = item['filename'].replace('.md', '').replace('.markdown', '')
            # Strip YYYY-MM-DD- prefix if present
            if len(raw_slug) > 10 and raw_slug[10] == '-':
                raw_slug = raw_slug[11:]
            slug = raw_slug
            
        full_url = f"{base_url}/{slug}/index.md?src=llms.txt"
        
        # Fallback to YAML summary if JSON shard summary is missing
        summary = item.get('shard_sum') or item.get('summary', '')
        kw_str = f" | KW: {item['shard_kw']}" if item.get('shard_kw') else ""
        sub_str = f" | SUB: {item['shard_sub']}" if item.get('shard_sub') else ""
        
        # Construct the ultra-dense line
        dense_line = (f"[{item['date']}] {full_url} "
                      f"(Ord:{item['sort_order']}) | "
                      f"{item['title']}{kw_str}{sub_str} | SUM: {summary}")
        lines.append(dense_line)
        
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate llms.txt")
    common.add_standard_arguments(parser)
    args = parser.parse_args()

    targets = common.load_targets()
    target_key = args.target

    if not target_key:
        print("🤖 Generating llms.txt...")
        print("Select Target Repo:")
        for k, v in targets.items():
            print(f"  [{k}] {v['name']} ({v['path']})")
        target_key = input("Enter choice (default 1): ").strip() or "1"

    if target_key not in targets:
        print(f"❌ Invalid target key: {target_key}", file=sys.stderr)
        sys.exit(1)

    target_config = targets[target_key]
    
    # 1. Load the Static Header
    if not HEADER_FILE.exists():
        print(f"❌ Error: Header file not found at {HEADER_FILE}", file=sys.stderr)
        sys.exit(1)
        
    with open(HEADER_FILE, 'r', encoding='utf-8') as f:
        header_content = f.read()

    # 2. Build the Dynamic Payload
    payload_content = build_payload(target_config)
    
    # 3. Fuse and Write
    final_content = f"{header_content.strip()}\n\n{payload_content}\n"
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(final_content)
        
    print(f"✅ Successfully generated: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()