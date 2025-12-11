import os
import sys
import json
import re
import time
import argparse
import getpass
from pathlib import Path
from datetime import datetime
import google.generativeai as genai
import frontmatter  # Requires: pip install python-frontmatter

# --- CONFIGURATION ---
CONFIG_DIR = Path.home() / ".config" / "articleizer"
API_KEY_FILE = CONFIG_DIR / "api_key.txt"
TARGETS_FILE = CONFIG_DIR / "targets.json"

# Model to use (Flash is best for high-volume, low-cost processing)
MODEL_NAME = 'gemini-2.5-flash' 

# Safe default
DEFAULT_TARGETS = {
    "1": {
        "name": "Local Project (Default)",
        "path": "./_posts"
    }
}

def load_targets():
    """Loads publishing targets from external config or falls back to default."""
    if TARGETS_FILE.exists():
        try:
            with open(TARGETS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Warning: {TARGETS_FILE} is corrupt. Using defaults.")
    return DEFAULT_TARGETS

PROJECT_TARGETS = load_targets()

def get_api_key():
    """Gets API key from config or prompts user."""
    if API_KEY_FILE.is_file():
        return API_KEY_FILE.read_text().strip()
    
    print("Google API Key not found in config.")
    key = getpass.getpass("Enter your Google API Key: ")
    if key.strip():
        save = input("Save key? (y/n): ").lower()
        if save == 'y':
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            API_KEY_FILE.write_text(key.strip())
            API_KEY_FILE.chmod(0o600)
    return key.strip()

def extract_metadata_and_content(file_path):
    """Reads markdown file, extracts YAML frontmatter and body."""
    try:
        post = frontmatter.load(file_path)
        return {
            "frontmatter": post.metadata,
            "content": post.content,
            "filename": file_path.stem
        }
    except Exception as e:
        print(f"❌ Error reading {file_path.name}: {e}")
        return None

def generate_context_json(article_data):
    """Calls Gemini to compress the article into a context JSON object."""
    
    # Construct the Prompt
    prompt = f"""
    You are a Knowledge Graph Architect. Your goal is to compress the provided technical article into a 'Holographic Shard'—a minimal JSON object that acts as a context pointer for a Retrieval Augmented Generation system.

    **Goal:** Fit maximum semantic meaning into approximately 200 tokens (800 bytes).

    **Input Data:**
    - Title: {article_data['frontmatter'].get('title', 'Unknown')}
    - Date: {article_data['frontmatter'].get('date', 'Unknown')}
    - Filename: {article_data['filename']}
    - Content: 
    {article_data['content'][:15000]}  # Truncate to avoid context limit issues, usually enough

    **Instructions:**
    1. **Analyze:** Read the content. Look past the title. Find specific technologies, concepts, or "aha!" moments buried in the text.
    2. **Extract Sub-topics ('sub'):** Identify 3-5 distinct, specific sub-topics or "juicy" details that are NOT just the title re-worded. (e.g., "Fixing Pandas int/str errors", "The 'Chisel Strike' method").
    3. **Summarize ('s'):** Write a concise 1-2 sentence summary of the core thesis.
    4. **Keywords ('kw'):** Extract 3-5 high-value technical keywords (e.g., "NixOS", "HTMX", "Sovereignty").

    **Output Format:**
    Provide ONLY a valid JSON object. No markdown formatting around it if possible, but I will parse it out.
    
    Schema:
    {{
      "id": "{article_data['filename']}",
      "d": "YYYY-MM-DD",  // Extract from filename or frontmatter
      "t": "Article Title",
      "s": "Concise Summary",
      "sub": ["Subtopic 1", "Subtopic 2", "Subtopic 3"],
      "kw": ["Keyword1", "Keyword2"]
    }}
    """

    model = genai.GenerativeModel(MODEL_NAME)
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean up Markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
            
        return json.loads(text.strip())
    except Exception as e:
        error_msg = str(e)
        # Check for Rate Limit (429) or ResourceExhausted errors
        if "429" in error_msg or "ResourceExhausted" in error_msg:
            print(f"\n🛑 Quota Limit Reached (API 429). Exiting script immediately.")
            sys.exit(0) # HARD EXIT
        else:
            print(f"  ⚠️ AI Generation failed: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Generate AI context JSONs for markdown articles.")
    parser.add_argument('--limit', type=int, default=50, help="Max number of articles to process this run (default: 50)")
    parser.add_argument('--force', action='store_true', help="Overwrite existing context files")
    parser.add_argument('--dry-run', action='store_true', help="Show what would happen without calling API")
    args = parser.parse_args()

    # Target Selection
    print("Select target blog directory:")
    for key, target in PROJECT_TARGETS.items():
        print(f"  [{key}] {target['name']}")
    
    choice = input("Enter choice (1..): ").strip()
    if choice not in PROJECT_TARGETS:
        print("Invalid choice.")
        return

    posts_dir = Path(PROJECT_TARGETS[choice]['path']).resolve()
    context_dir = posts_dir / "_context"
    
    if not posts_dir.exists():
        print(f"❌ Error: Directory {posts_dir} does not exist.")
        return

    # Ensure context directory exists
    if not args.dry_run:
        context_dir.mkdir(exist_ok=True)

    # 1. API Setup
    if not args.dry_run:
        api_key = get_api_key()
        if not api_key: return
        genai.configure(api_key=api_key)

    # 2. File Discovery & Filtering
    all_posts = sorted(list(posts_dir.glob("*.md")), reverse=True) # Newest first
    to_process = []

    print(f"\n🔍 Scanning {posts_dir}...")
    
    for post in all_posts:
        json_path = context_dir / f"{post.stem}.json"
        
        if not json_path.exists() or args.force:
            to_process.append(post)

    print(f"Found {len(all_posts)} articles.")
    print(f"📝 {len(to_process)} articles need context generation.")
    
    if args.limit and len(to_process) > args.limit:
        print(f"⚠️ Limiting processing to first {args.limit} items.")
        to_process = to_process[:args.limit]

    if not to_process:
        print("✅ All caught up! No new context to generate.")
        return

    # 3. Processing Loop
    print("\n🚀 Starting Contextualization...")
    
    count = 0
    for post in to_process:
        count += 1
        print(f"[{count}/{len(to_process)}] Processing: {post.name}...")
        
        if args.dry_run:
            continue

        data = extract_metadata_and_content(post)
        if not data: continue

        # Generate JSON
        context_json = generate_context_json(data)
        
        if context_json:
            # Save
            json_path = context_dir / f"{post.stem}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                # Minify JSON to save bytes (separators removes whitespace)
                json.dump(context_json, f, separators=(',', ':'))
            
            print(f"  ✅ Saved {json_path.name}")
            
            # Rate limiting: Flash Free Tier is ~15 RPM. 
            # 60s / 15 = 4s. We use 5s to be safe.
            time.sleep(5)
        else:
            print("  ❌ Failed to generate context.")
            # Even on failure, sleep a bit to avoid hammering
            time.sleep(2)

    print("\n✨ Batch complete.")

if __name__ == "__main__":
    main()
