#!/usr/bin/env python3
"""
The Codex Compiler: Deterministic Semantic Routing for AI.

Bypasses K-Means clustering entirely for AI ingestion.
Tongue-in-grooves the human-authored narrative structure (book_holographic.json) 
with the AI-compressed semantic shards (_context/*.json).
"""

import json
from pathlib import Path
import re


# --- CONFIGURATION ---
POSTS_DIR = Path("/home/mike/repos/trimnoir/_posts")
CONTEXT_DIR = POSTS_DIR / "_context"
BOOK_SCHEMA_FILE = Path("/home/mike/repos/pipulate/assets/prompts/book_holographic.json")
OUTPUT_LLMS_TXT = Path("llms.txt")
BASE_URL = "https://mikelev.in"


def load_shards():
    """Loads all holographic shards into a dictionary keyed by the clean slug."""
    shards = {}
    if not CONTEXT_DIR.exists():
        print(f"⚠️ Context dir {CONTEXT_DIR} does not exist.")
        return shards

    for f in CONTEXT_DIR.glob("*.json"):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                # Strip the YYYY-MM-DD- date prefix to match the book schema slugs
                clean_slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', f.stem)
                shards[clean_slug] = data
        except Exception as e:
            print(f"⚠️ Error loading shard {f.name}: {e}")
    return shards

def build_manifest():
    if not BOOK_SCHEMA_FILE.exists():
        print(f"❌ Error: Book schema not found at {BOOK_SCHEMA_FILE}")
        return

    with open(BOOK_SCHEMA_FILE, 'r', encoding='utf-8') as f:
        book_data = json.load(f)

    shards = load_shards()
    lines = []

    # --- PREAMBLE ---
    lines.append(f"# {book_data.get('title', 'System Codex')}")
    lines.append(f"Author: {book_data.get('author', 'Unknown')}")
    lines.append("\n> This is the definitive, chronological narrative structure of this system.")
    lines.append("> It bypasses algorithmic clustering to provide absolute architectural context.")
    lines.append("\n## Direct Data Access")
    lines.append("- **Source Code**: Most articles offer `<link rel='alternate'>` to raw Markdown.")
    lines.append("\n## The Narrative Codex\n")

    # --- TONGUE-IN-GROOVE ASSEMBLY ---
    for act in book_data.get('acts', []):
        lines.append(f"### Act: {act.get('title', 'Unknown Act')}")
        
        if act.get('intro_prompt'):
            lines.append(f"*{act['intro_prompt']}*\n")

        for article_path in act.get('articles', []):
            # Extract the slug to match against the shard IDs
            # Assumes format: "/futureproof/future-proof-tech-skills"
            slug = article_path.strip('/').split('/')[-1]
            shard = shards.get(slug)

            if shard:
                title = shard.get('t', 'Untitled')
                summary = shard.get('s', 'No summary available.')
                # The crucial tracer dye/routing parameter
                markdown_url = f"{BASE_URL}{article_path}/index.md?src=llms.txt"
                
                lines.append(f"- **[{title}]({markdown_url})**")
                lines.append(f"  > {summary}")
            else:
                # Graceful degradation if the shard hasn't been generated yet
                lines.append(f"- **[Missing Shard: {slug}]({BASE_URL}{article_path}/index.md?src=llms.txt)**")
        
        lines.append("") # Spacing between acts

    # --- ORPHAN RECOVERY (The "Use Up All Inventory" Rule) ---
    unused_slugs = set(shards.keys()) - used_slugs
    if unused_slugs:
        lines.append("### Uncategorized Archives")
        lines.append("*The chronological overflow. Content pending narrative placement.*\n")
        
        # Pull the unused shards and sort them by date (newest first)
        orphans = [(slug, shards[slug]) for slug in unused_slugs]
        orphans.sort(key=lambda x: x[1].get('d', ''), reverse=True)
        
        for slug, orphan_data in orphans:
            title = orphan_data.get('t', 'Untitled')
            summary = orphan_data.get('s', 'No summary available.')
            orphan_url = f"{BASE_URL}/{slug}/index.md?src=llms.txt"
            
            lines.append(f"- **[{title}]({orphan_url})**")
            lines.append(f"  > {summary}")
        
        lines.append("")

    # --- OUTPUT ---
    with open(OUTPUT_LLMS_TXT, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    
    print(f"✅ Generated deterministic manifest: {OUTPUT_LLMS_TXT}")
    print(f"✅ Reclaimed {len(unused_slugs)} orphaned articles.")


if __name__ == "__main__":
    build_manifest()
