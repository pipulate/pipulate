import os
import sys
import json
import time
import re
import argparse
import getpass
from pathlib import Path
from datetime import datetime
import google.generativeai as genai
import frontmatter
import tiktoken  # Requires: pip install tiktoken
import common

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

def clean_json_string(text):
    """Attempts to fix common JSON syntax errors from LLMs."""
    # Fix: invalid escape sequences (e.g., \t or \n in text that aren't escaped)
    # This is a naive fix; robust fixing is harder, but this handles common Windows path issues
    # or single backslashes.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try a raw string load or simple escape fix? 
        # For now, let's just try to grab the JSON block more aggressively if it exists
        pattern = r"\{.*\}"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        return None

def generate_context_json(article_data, token_count):
    """
    Calls Gemini to compress the article.
    Returns: (json_object, duration, status_code)
    status_code: 
      0 = Success
      1 = Quota Error (Stop Key)
      2 = Parsing/Other Error (Skip File)
    """
    
    prompt = f"""
    You are a Knowledge Graph Architect. Your goal is to compress the provided technical article into a 'Holographic Shard'—a minimal JSON object.

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
    Provide ONLY a valid JSON object. Do not include markdown formatting like ```json.
    
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

    # REVERT: Removed generation_config for compatibility with older SDKs
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
            
            # Basic cleanup if mime_type doesn't catch it
            if text.startswith("```json"): text = text[7:]
            if text.startswith("```"): text = text[3:]
            if text.endswith("```"): text = text[:-3]
            text = text.strip()

            try:
                json_obj = json.loads(text)
                return json_obj, duration, 0 # Success
            except json.JSONDecodeError as e:
                # Attempt One Cleanup
                print(f"  ⚠️ JSON Parse Error: {e}. Attempting cleanup...")
                cleaned = clean_json_string(text)
                if cleaned:
                    return cleaned, duration, 0
                else:
                    print(f"  ❌ Parse Failed on attempt {attempt+1}")
                    # Retrying generation might fix it if temperature > 0
                    raise Exception("JSON Parsing Failed") 

        except Exception as e:
            error_msg = str(e)
            attempt += 1
            
            # Case A: DAILY QUOTA (RPD) - Hard Stop
            if "ResourceExhausted" in error_msg or "quota" in error_msg.lower():
                print(f"\n🛑 HARD STOP: Quota Exceeded for this key.")
                return None, 0, 1 # Signal: STOP KEY

            # Case B: RATE LIMIT (RPM) or SERVER ERROR - Soft Retry
            if "429" in error_msg or "500" in error_msg or "503" in error_msg:
                if attempt < max_retries:
                    wait_time = 10 * attempt
                    print(f"  ⚠️ Transient error (RPM/Server). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"  ❌ Failed after {max_retries} attempts.")
                    return None, 0, 2 # Signal: SKIP FILE
            
            # Case C: Parsing/Content Errors
            elif "JSON" in error_msg:
                 if attempt < max_retries:
                    print(f"  ⚠️ Retrying generation due to bad JSON...")
                 else:
                    print(f"  ❌ consistently bad JSON.")
                    return None, 0, 2 # Signal: SKIP FILE
            
            else:
                print(f"  ⚠️ Non-retriable error: {e}")
                return None, 0, 2 # Signal: SKIP FILE

    return None, 0, 2

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

        context_json, duration, status = generate_context_json(data, input_tokens)
        
        if status == 0: # Success
            json_path = context_dir / f"{post.stem}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(context_json, f, separators=(',', ':'))
            
            print(f"✅ Saved ({duration:.2f}s)")
            processed_count += 1
            time.sleep(SAFETY_SLEEP_SECONDS)
        
        elif status == 1: # Quota Hit
            print("❌ Quota Exceeded. Stopping batch.")
            break # Stop this key, move to next
        
        elif status == 2: # Skip File
            print("⏭️  Skipping file due to error.")
            continue # Move to next file, SAME key

    return processed_count

def main():
    parser = argparse.ArgumentParser(description="Generate AI context JSONs.")
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('-k', '--key', type=str, default="default")
    parser.add_argument('-m', '--keys', type=str)
    
    # Use Common Argument
    common.add_target_argument(parser)
    
    args = parser.parse_args()

    # Dynamic Path Resolution via Common
    posts_dir = common.get_target_path(args)
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
