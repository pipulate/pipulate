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
    """Estimates token count using tiktoken."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        return len(text.split())

def load_keys_dict():
    """Loads the entire keys dictionary."""
    if KEYS_FILE.exists():
        try:
            with open(KEYS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"❌ Error: {KEYS_FILE} is corrupt.")
            sys.exit(1)
    return {}

def get_api_key(key_name="default", keys_dict=None):
    """Gets a specific named API key."""
    if keys_dict is None:
        keys_dict = load_keys_dict()

    if key_name in keys_dict:
        return keys_dict[key_name]
    
    # Interactive fallback
    print(f"⚠️ API Key '{key_name}' not found in {KEYS_FILE}.")
    new_key = getpass.getpass(f"Enter Google API Key for '{key_name}': ").strip()
    
    if new_key:
        save = input(f"Save key '{key_name}' to config? (y/n): ").lower()
        if save == 'y':
            keys_dict[key_name] = new_key
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(KEYS_FILE, 'w') as f:
                json.dump(keys_dict, f, indent=2)
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
            
            if text.startswith("```json"): text = text[7:]
            if text.startswith("```"): text = text[3:]
            if text.endswith("```"): text = text[:-3]
            
            return json.loads(text.strip()), duration

        except Exception as e:
            error_msg = str(e)
            attempt += 1
            
            # Case A: DAILY QUOTA (RPD) - Hard Stop
            if "ResourceExhausted" in error_msg or "quota" in error_msg.lower():
                print(f"\n🛑 HARD STOP: Quota Exceeded for this key.")
                return None, 0 # Return None to signal caller to stop/switch keys

            # Case B: RATE LIMIT (RPM) or SERVER ERROR - Soft Retry
            if "429" in error_msg or "500" in error_msg or "503" in error_msg:
                if attempt < max_retries:
                    wait_time = 10 * attempt
                    print(f"  ⚠️ Transient error (RPM/Server). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"  ❌ Failed after {max_retries} attempts.")
                    return None, 0
            else:
                print(f"  ⚠️ Non-retriable error: {e}")
                return None, 0
    return None, 0

def process_batch(batch_files, key_name, api_key, context_dir, dry_run):
    """Processes a specific list of files with a specific key."""
    
    print(f"\n🔑 Switch-on: '{key_name}' | Batch Size: {len(batch_files)}")
    
    if not dry_run:
        genai.configure(api_key=api_key)

    processed_count = 0
    
    for i, post in enumerate(batch_files):
        print(f"   [{i+1}/{len(batch_files)}] Processing: {post.name}...")
        
        if dry_run:
            continue

        data = extract_metadata_and_content(post)
        if not data: continue

        input_tokens = count_tokens(data['content'][:15000])
        print(f"     ↳ Input Tokens: {input_tokens} ... ", end='', flush=True)

        context_json, duration = generate_context_json(data, input_tokens)
        
        if context_json:
            json_path = context_dir / f"{post.stem}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(context_json, f, separators=(',', ':'))
            
            print(f"✅ Saved ({duration:.2f}s)")
            processed_count += 1
            time.sleep(SAFETY_SLEEP_SECONDS)
        else:
            print("❌ Failed / Quota Exceeded.")
            # If we failed (likely quota), we stop this batch early
            break

    return processed_count

def main():
    parser = argparse.ArgumentParser(description="Generate AI context JSONs with multi-key rotation.")
    parser.add_argument('--limit', type=int, default=20, help="Max items per key batch")
    parser.add_argument('--force', action='store_true', help="Overwrite existing context files")
    parser.add_argument('--dry-run', action='store_true', help="Show what would happen")
    parser.add_argument('-k', '--key', type=str, default="default", help="Single key mode (default: 'default')")
    parser.add_argument('-m', '--keys', type=str, help="Multi-key mode: Comma-separated list of keys (e.g., 'c1,c2,c3')")
    
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

    # Key Strategy Selection
    keys_queue = []
    keys_dict = load_keys_dict()

    if args.keys:
        # Multi-key Mode
        requested_keys = [k.strip() for k in args.keys.split(',')]
        for k in requested_keys:
            val = get_api_key(k, keys_dict) # Ensures interactive prompt if missing
            keys_queue.append((k, val))
        print(f"🔄 Multi-Key Rotation Enabled: {len(keys_queue)} keys loaded.")
    else:
        # Single Key Mode
        val = get_api_key(args.key, keys_dict)
        keys_queue.append((args.key, val))

    # File Discovery
    all_posts = sorted(list(posts_dir.glob("*.md")), reverse=True)
    to_process = []

    print(f"\n🔍 Scanning {posts_dir}...")
    for post in all_posts:
        json_path = context_dir / f"{post.stem}.json"
        if not json_path.exists() or args.force:
            to_process.append(post)

    print(f"📝 {len(to_process)} articles need context.")
    
    total_processed = 0
    
    # --- OUTER LOOP: KEY ROTATION ---
    for key_name, api_key in keys_queue:
        if not to_process:
            break
            
        # Slice off the next batch
        batch_size = args.limit # In multi-mode, limit applies per key
        current_batch = to_process[:batch_size]
        to_process = to_process[batch_size:] # Remove them from the queue
        
        count = process_batch(current_batch, key_name, api_key, context_dir, args.dry_run)
        total_processed += count
        
        if count < len(current_batch):
            print(f"⚠️ Key '{key_name}' exhausted early. Switching...")
    
    print(f"\n✨ Grand Total: {total_processed} articles processed across {len(keys_queue)} keys.")

if __name__ == "__main__":
    main()