#!/usr/bin/env python3
import os
import json
import sys
from pathlib import Path

# Add pipulate root to path so we can import lsa
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.articles import lsa

TARGET_DIR = "/home/mike/repos/trimnoir/_posts"
OUTPUT_FILE = "/home/mike/repos/bookforge/00_meta/pass_ledger.jsonl"
MAX_TOKENS_PER_PASS = 100000

def main():
    print(f"🔍 Surveying {TARGET_DIR}...")
    articles = lsa.get_holographic_article_data(TARGET_DIR)
    # Reverse to chronological order (oldest to newest) for book reading
    articles.reverse()

    passes = []
    current_pass_files = []
    current_tokens = 0
    pass_num = 1
    start_idx = 0

    for idx, article in enumerate(articles):
        # Fallback token count estimation if not pre-calculated
        content = Path(article['path']).read_text(encoding='utf-8', errors='ignore')
        tokens = len(content.split()) * 1.3 # Rough token estimate

        if current_tokens + tokens > MAX_TOKENS_PER_PASS and current_pass_files:
            passes.append({
                "pass_id": f"pass_{pass_num:03d}",
                "slice": f"[{start_idx}:{idx}]",
                "total_tokens": int(current_tokens),
                "article_count": len(current_pass_files)
            })
            pass_num += 1
            current_pass_files = []
            current_tokens = 0
            start_idx = idx

        current_pass_files.append(article['filename'])
        current_tokens += tokens

    # Catch the remaining articles
    if current_pass_files:
        passes.append({
            "pass_id": f"pass_{pass_num:03d}",
            "slice": f"[{start_idx}:{len(articles)}]",
            "total_tokens": int(current_tokens),
            "article_count": len(current_pass_files)
        })

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for p in passes:
            f.write(json.dumps(p) + '\n')
            
    print(f"✨ Ledger forged! Created {len(passes)} optimized passes.")
    print(f"💾 Saved to: {OUTPUT_FILE}")
    if passes:
        print(f"🎯 Your first command for Article 999 will use slice: {passes[0]['slice']}")

if __name__ == "__main__":
    main()
