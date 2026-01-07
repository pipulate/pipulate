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
    # Handle cases where context_dir is relative to script execution
    if not context_dir.exists():
         print(f"⚠️ Context dir {context_dir} does not exist. Checking relative...")
         return pd.DataFrame()

    files = list(context_dir.glob("*.json"))
    print(f"💎 Loading {len(files)} shards from {context_dir}...")
    
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            # Map shard back to markdown file
            md_path = posts_dir / f"{f.stem}.md"
            if not md_path.exists():
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

def load_velocity_data(directory=Path(".")):
    """Loads GSC velocity/health data."""
    if not directory.exists():
        directory = Path(__file__).parent
        
    velocity_file = directory / "gsc_velocity.json"
    if not velocity_file.exists():
        print("ℹ️ No GSC velocity data found.")
        return {}
        
    print(f"❤️ Loading health velocity from: {velocity_file.name}")
    try:
        with open(velocity_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        slug_map = {}
        for key, metrics in data.items():
            if key.startswith("_"): continue
            slug = key.strip('/').split('/')[-1]
            slug_map[slug] = metrics
        return slug_map
    except Exception as e:
        print(f"⚠️ Error loading velocity data: {e}")
        return {}

def load_market_data(directory=Path(".")):
    """Loads SEMRush/GSC CSV data for weighting."""
    if not directory.exists():
        directory = Path(__file__).parent
    files = list(directory.glob("*bulk_us*.csv"))
    if not files: return {}
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    print(f"💰 Loading market data from: {latest_file.name}")
    try:
        df = pd.read_csv(latest_file)
        market_map = {}
        for _, row in df.iterrows():
            kw = str(row['Keyword']).lower().strip()
            try: vol = int(row['Volume'])
            except: vol = 0
            market_map[kw] = vol
        return market_map
    except: return {}

# --- UPDATED: Return candidates instead of single label ---
def get_cluster_candidates(df_cluster, market_data=None):
    """Returns a list of (keyword, score) tuples sorted by relevance."""
    all_keywords = [kw for sublist in df_cluster['keywords'] for kw in sublist]
    if not all_keywords:
        return [("Misc", 0)]
    
    counts = Counter(all_keywords)
    # Get top 10 candidates to have a buffer for collisions
    candidates = counts.most_common(10)
    
    scored_candidates = []
    for kw, freq in candidates:
        score = freq
        if market_data:
            vol = market_data.get(kw.lower().strip(), 0)
            # Use same scoring logic as before
            score = freq * np.log1p(vol)
        scored_candidates.append((kw, score))
        
    # Sort by score descending
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    return scored_candidates

def add_article_to_node(hub_node, row):
    """Helper to append article dict to the hub node."""
    article = {
        "title": row['title'],
        "permalink": row['permalink'],
        "date": row['date'],
        "id": row['id']
    }
    hub_node.setdefault('children_articles', []).append(article)

def recursive_cluster_tree(df_slice, current_node, current_depth, market_data, velocity_data, vectorizer=None):
    """Builds the nested JSON tree using Gold Pan logic."""
    df = df_slice.copy()

    # 0. SORT BY CLICKS
    df['sort_clicks'] = df['id'].apply(lambda x: velocity_data.get(re.sub(r'^\d{4}-\d{2}-\d{2}-', '', x), {}).get('total_clicks', 0))
    df = df.sort_values(by='sort_clicks', ascending=False)

    # 1. STOP CONDITION
    if len(df) <= TARGET_BRANCHING_FACTOR + GOLD_PAN_SIZE:
        for _, row in df.iterrows():
            add_article_to_node(current_node, row)
        return

    # 2. THE GOLD PAN
    gold = df.head(GOLD_PAN_SIZE)
    remainder = df.iloc[GOLD_PAN_SIZE:].copy()

    for _, row in gold.iterrows():
        add_article_to_node(current_node, row)

    # 3. CLUSTER REMAINDER
    if len(remainder) == 0: return

    if vectorizer is None:
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)

    try:
        tfidf_matrix = vectorizer.fit_transform(remainder['soup'])
        n_components = min(5, len(remainder) - 1)
        if n_components > 1:
            svd = TruncatedSVD(n_components=n_components)
            matrix = svd.fit_transform(tfidf_matrix)
        else:
            matrix = tfidf_matrix

        kmeans = MiniBatchKMeans(
            n_clusters=TARGET_BRANCHING_FACTOR,
            random_state=42,
            n_init=10,
            batch_size=256
        )
        clusters = kmeans.fit_predict(matrix)
        remainder.loc[:, 'cluster'] = clusters

        # --- RECURSION ---
        # Track used slugs at this level to prevent collisions
        used_slugs = set()

        for cluster_id in range(TARGET_BRANCHING_FACTOR):
            cluster_data = remainder[remainder['cluster'] == cluster_id]
            if len(cluster_data) == 0: continue

            # --- NEW COLLISION DETECTION LOGIC ---
            candidates = get_cluster_candidates(cluster_data, market_data)
            
            # Find the first candidate that hasn't been used yet
            hub_label = "Misc"
            for kw, score in candidates:
                test_slug = slugify(kw)
                if test_slug not in used_slugs:
                    hub_label = kw
                    break
            else:
                # Fallback: If all candidates used, append number to top candidate
                top_kw = candidates[0][0]
                base_slug = slugify(top_kw)
                counter = 2
                while f"{base_slug}-{counter}" in used_slugs:
                    counter += 1
                hub_label = f"{top_kw} {counter}"

            slug = slugify(hub_label)
            used_slugs.add(slug)
            # -------------------------------------
            
            # Create Sub-Hub Node
            new_hub_node = {
                "id": f"{current_node['id']}_{cluster_id}",
                "title": hub_label,
                "permalink": f"{current_node['permalink']}{slug}/",
                "blurb": f"Explore {len(cluster_data)} articles about {hub_label}."
            }
            
            # Attach to Parent
            current_node.setdefault('children_hubs', []).append(new_hub_node)

            # Recurse
            recursive_cluster_tree(
                cluster_data, 
                new_hub_node, 
                current_depth + 1, 
                market_data, 
                velocity_data
            )

    except Exception as e:
        print(f"⚠️ Clustering fallback at depth {current_depth}: {e}")
        for _, row in remainder.iterrows():
            add_article_to_node(current_node, row)

def main():
    print("🚀 Initializing NavGraph Builder...")
    parser = argparse.ArgumentParser(description="Build Navigation Graph")
    common.add_target_argument(parser)
    args = parser.parse_args()

    posts_dir = common.get_target_path(args)
    context_dir = posts_dir / "_context"
    output_file = Path("navgraph.json") 

    if not context_dir.exists():
        print(f"❌ Context dir not found: {context_dir}")
        return

    df = load_enriched_shards(context_dir, posts_dir)
    if df.empty:
        print("❌ No data found.")
        return
        
    market_data = load_market_data()
    velocity_data = load_velocity_data()

    # Root Node
    nav_tree = {
        "id": "root",
        "title": "Home",
        "permalink": "/",
        "blurb": "Welcome to the knowledge graph."
    }

    print(f"🧠 Building NavTree for {len(df)} articles...")
    recursive_cluster_tree(df, nav_tree, 0, market_data, velocity_data)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(nav_tree, f, indent=2)

    print(f"✅ NavGraph generated: {output_file}")

if __name__ == "__main__":
    main()