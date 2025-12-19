import json
import glob
from pathlib import Path
from collections import Counter
import re

# --- CONFIGURATION ---
# Path to your JSON context shards relative to this script
CONTEXT_DIR = Path("/home/mike/repos/MikeLev.in/_posts/_context")
OUTPUT_FILE = "semrush_candidates.txt"
TOP_N = 100

# Stop words to filter out low-signal noise from your specific corpus
# (Adjust this list as you see what comes out)
STOP_WORDS = {
    "misc", "untitled", "intro", "introduction", "part", "series",
    "summary", "guide", "tutorial", "notes", "update", "vs"
}

def normalize_keyword(kw):
    """
    Cleans and normalizes a keyword string.
    - Lowercases
    - Strips whitespace
    - Removes special characters that confuse SEMRush (optional)
    """
    if not kw:
        return None
    
    clean = kw.lower().strip()
    
    # Filter out short/empty strings or pure numbers
    if len(clean) < 2 or clean.isdigit():
        return None
        
    if clean in STOP_WORDS:
        return None
        
    return clean

def generate_candidates():
    print(f"🚀 Scanning shards in {CONTEXT_DIR}...")
    
    files = list(CONTEXT_DIR.glob("*.json"))
    if not files:
        print(f"❌ No JSON files found in {CONTEXT_DIR}. Check your path.")
        return

    keyword_counter = Counter()
    file_count = 0

    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                
                # We mine both 'kw' (Keywords) and 'sub' (Sub-topics)
                # These are your highest signal semantic markers
                sources = data.get('kw', []) + data.get('sub', [])
                
                for raw_kw in sources:
                    clean_kw = normalize_keyword(raw_kw)
                    if clean_kw:
                        keyword_counter[clean_kw] += 1
            
            file_count += 1
        except Exception as e:
            print(f"⚠️ Error reading {f.name}: {e}")

    print(f"💎 Processed {file_count} shards.")
    print(f"🧠 Found {len(keyword_counter)} unique keywords.")

    # Get the Top N most frequent keywords
    top_candidates = keyword_counter.most_common(TOP_N)

    # --- OUTPUT ---
    print(f"\n🏆 Top {TOP_N} Candidates for SEMRush:")
    print("-" * 40)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        for kw, count in top_candidates:
            print(f"{count:4d} | {kw}")
            out.write(f"{kw}\n")
            
    print("-" * 40)
    print(f"💾 Saved list to: {OUTPUT_FILE}")
    print("📋 Copy the contents of this file into SEMRush Keyword Overview (Bulk Analysis).")

if __name__ == "__main__":
    generate_candidates()
