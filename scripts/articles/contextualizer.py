import os
import sys
import json
import time
import argparse
import getpass
from pathlib import Path
from datetime import datetime
import google.generativeai as genai
import frontmatter
import tiktoken  # Requires: pip install tiktoken

# --- CONFIGURATION ---
CONFIG_DIR = Path.home() / ".config" / "articleizer"
KEYS_FILE = CONFIG_DIR / "keys.json"
TARGETS_FILE = CONFIG_DIR / "targets.json"

# MODEL CONFIGURATION
# Note: 2.5-flash-lite appears to have a 20 RPD limit in preview.
# You may need to switch back to 'gemini-2.0-flash-exp' or similar if available.
MODEL_NAME = 'gemini-2.5-flash-lite' 
SAFETY_SLEEP_SECONDS = 5

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

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Estimates token count using tiktoken (consistent with prompt_foo.py)."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback if specific model encoding not found
        return len(text.split())

def get_api_key(key_name="default"):
    """Gets a specific named API key from keys.json."""
    keys = {}
    if KEYS_FILE.exists():
        try:
            with open(KEYS_FILE, 'r') as f:
                keys = json.load(f)
        except json.JSONDecodeError:
            print(f"❌ Error: {KEYS_FILE} is corrupt.")
            sys.exit(1)

    if key_name in keys:
        return keys[key_name]
    
    print(f"⚠️ API Key '{key_name}' not found in {KEYS_FILE}.")
    new_key = getpass.getpass(f"Enter Google API Key for '{key_name}': ").strip()
    
    if new_key:
        save = input(f"Save key '{key_name}' to config? (y/n): ").lower()
        if save == 'y':
            keys[key_name] = new_key
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(KEYS_FILE, 'w') as f:
                json.dump(keys, f, indent=2)
            KEYS_FILE.chmod(0o600)
            print(f"✅ Key '{key_name}' saved.")
        return new_key
    else:
        print("❌ No key provided. Exiting.")
        sys.exit(1)

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

def generate_context_json(article_data, token_count):
    """Calls Gemini to compress the article, with strict quota checking."""
    
    prompt = f"""
    You are a Knowledge Graph Architect. Your goal is to compress the provided technical article into a 'Holographic Shard'—a minimal JSON object that acts as a context pointer for a Retrieval Augmented Generation system.

    **Goal:** Fit maximum semantic meaning into approximately 200 tokens.

    **Input Data:**
    - Title: {article_data['frontmatter'].get('title', 'Unknown')}
    - Date: {article_data['frontmatter'].get('date', 'Unknown')}
    - Filename: {article_data['filename']}
    - Content: 
    {article_data['content'][:15000]} 

    **Instructions:**
    1. **Analyze:** Read the content. Look past the title. Find specific technologies, concepts, or "aha!" moments.
    2. **Extract Sub-topics ('sub'):** Identify 3-5 distinct, specific sub-topics.
    3. **Summarize ('s'):** Write a concise 1-2 sentence summary of the core thesis.
    4. **Keywords ('kw'):** Extract 3-5 high-value technical keywords.

    **Output Format:**
    Provide ONLY a valid JSON object.
    
    Schema:
    {{
      "id": "{article_data['filename']}",
      "d": "YYYY-MM-DD", 
      "t": "Article Title",
      "s": "Concise Summary",
      "sub": ["Subtopic 1", "Subtopic 2", "Subtopic 3"],
      "kw": ["Keyword1", "Keyword2"]
    }}
    """

    model = genai.GenerativeModel(MODEL_NAME)
    
    max_retries = 3
    attempt = 0

    while attempt < max_retries:
        try:
            req_start = time.time()
            response = model.generate_content(prompt)
            req_end = time.time()
            duration = req_end - req_start

            text = response.text.strip()
            
            # Clean up Markdown code blocks
            if text.startswith("```json"): text = text[7:]
            if text.startswith("```"): text = text[3:]
            if text.endswith("```"): text = text[:-3]
            
            return json.loads(text.strip()), duration

        except Exception as e:
            error_msg = str(e)
            attempt += 1
            
            # Case A: DAILY QUOTA (RPD) - Hard Stop
            if "ResourceExhausted" in error_msg or "quota" in error_msg.lower():
                print(f"\n🛑 HARD STOP: Quota Exceeded.")
                print(f"   Model: {MODEL_NAME}")
                print(f"   Input Tokens: {token_count}")
                # Try to extract helpful info from the error message
                if "quota_metric" in error_msg:
                    print(f"   Details: {error_msg.split('violations')[0][:300]}...") 
                else:
                    print(f"   Error: {error_msg[:200]}...")
                sys.exit(0) 

            # Case B: RATE LIMIT (RPM) or SERVER ERROR - Soft Retry
            if "429" in error_msg or "500" in error_msg or "503" in error_msg:
                if attempt < max_retries:
                    wait_time = 10 * attempt 
                    print(f"  ⚠️ Transient error ({e}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"  ❌ Failed after {max_retries} attempts.")
                    return None, 0
            else:
                print(f"  ⚠️ Non-retriable error: {e}")
                return None, 0
    return None, 0

def main():
    parser = argparse.ArgumentParser(description="Generate AI context JSONs for markdown articles.")
    parser.add_argument('--limit', type=int, default=1000, help="Max number of articles to process this run")
    parser.add_argument('--force', action='store_true', help="Overwrite existing context files")
    parser.add_argument('--dry-run', action='store_true', help="Show what would happen without calling API")
    parser.add_argument('-k', '--key', type=str, default="default", help="Name of the API key to use from keys.json (default: 'default')")
    
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

    if not args.dry_run:
        context_dir.mkdir(exist_ok=True)

    if not args.dry_run:
        api_key = get_api_key(args.key)
        if not api_key: return
        genai.configure(api_key=api_key)
        print(f"🔑 Using API Key: '{args.key}'")

    all_posts = sorted(list(posts_dir.glob("*.md")), reverse=True)
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

    print(f"\n🚀 Starting Contextualization using {MODEL_NAME}...")
    print(f"ℹ️  Pacing: ~{SAFETY_SLEEP_SECONDS}s per item to stay under RPM limit.")
    
    count = 0
    batch_start_time = time.time()

    for post in to_process:
        count += 1
        elapsed = time.time() - batch_start_time
        
        if args.dry_run:
            print(f"[{count}] Dry run: {post.name}")
            continue

        data = extract_metadata_and_content(post)
        if not data: continue

        # Calculate Tokens BEFORE sending
        input_tokens = count_tokens(data['content'][:15000])
        
        # Log Start
        print(f"[{count}/{len(to_process)}] Processing: {post.name}")
        print(f"  ↳ Input Tokens: {input_tokens} ... ", end='', flush=True)

        context_json, duration = generate_context_json(data, input_tokens)
        
        if context_json:
            json_path = context_dir / f"{post.stem}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(context_json, f, separators=(',', ':'))
            
            print(f"✅ Saved ({duration:.2f}s)")
            
            time.sleep(SAFETY_SLEEP_SECONDS)
        else:
            print(f"❌ Failed.")
            time.sleep(2)

    print("\n✨ Batch complete.")

if __name__ == "__main__":
    main()