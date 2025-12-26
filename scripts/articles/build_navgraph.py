import json
import glob
from pathlib import Path
import pandas as pd
import numpy as np
import frontmatter 
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import TruncatedSVD
from collections import Counter
import re
import warnings
import argparse
# Import the new common loader
import common 

warnings.filterwarnings('ignore', category=pd.errors.SettingWithCopyWarning)

# --- GLOBAL SETTINGS ---
TARGET_BRANCHING_FACTOR = 7
GOLD_PAN_SIZE = 5
MIN_CLUSTER_SIZE = 5

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text)
    return text.strip('-')

def load_enriched_shards(context_dir, posts_dir):
    """Ingests shards AND merges with Frontmatter."""
    shards = []
    # Use the unified path provided by common.py
    files = list(context_dir.glob("*.json"))
    print(f"💎 Loading {len(files)} shards from {context_dir}...")
    
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            # Map shard back to markdown file
            md_path = posts_dir / f"{f.stem}.md"
            if not md_path.exists():
                # Try finding it if date prefix varies? For now, skip.
                continue

            post = frontmatter.load(md_path)
            
            soup = (
                (data.get('t', '') + " ") * 3 + 
                (" ".join(data.get('kw', [])) + " ") * 2 + 
                " ".join(data.get('sub', []))
            )
            
            date_val = post.metadata.get('date', data.get('d', ''))
            
            shards.append({
                "id": f.stem,
                "title": post.metadata.get('title', data.get('t', 'Untitled')),
                "permalink": post.metadata.get('permalink', f"/{f.stem}/"),
                "description": post.metadata.get('description', data.get('s', '')),
                "date": str(date_val), 
                "soup": soup,
                "keywords": data.get('kw', []) + data.get('sub', [])
            })

        except Exception as e:
            print(f"⚠️ Error loading {f.name}: {e}")
            
    return pd.DataFrame(shards)

# ... [Keep calculate_gravity, get_cluster_label, load_market/velocity as they were] ...
# (They effectively just read files, so they are fine, but ensure load_velocity uses the script dir)

def main():
    parser = argparse.ArgumentParser(description="Build Navigation Graph")
    common.add_target_argument(parser)
    args = parser.parse_args()

    # Dynamic Path Resolution
    posts_dir = common.get_target_path(args)
    context_dir = posts_dir / "_context"
    
    # Output navgraph.json to the SCRIPTS directory (or project root?)
    # Let's keep it local to the script for now, so generate_hubs can find it easily
    output_file = Path("navgraph.json") 

    print("🚀 Initializing NavGraph Builder...")
    
    if not context_dir.exists():
        print(f"❌ Context dir not found: {context_dir}")
        return

    df = load_enriched_shards(context_dir, posts_dir)
    if df.empty:
        print("❌ No data found.")
        return
        
    # ... [Load market/velocity data logic remains the same] ...
    # Placeholder for the logic functions defined in your previous version
    
    # ... [Clustering logic] ...
    
    # NOTE: Since I am abbreviating to fit the response, 
    # assume the clustering logic here uses the 'df' loaded above.
    
    print(f"✅ NavGraph generated (Target: {posts_dir.name})")

if __name__ == "__main__":
    main()