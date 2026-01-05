import json
import glob
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import TruncatedSVD
from collections import Counter
import re
import warnings
import argparse
import common

# Silence the specific warning if copy usage is correct logic-wise
warnings.filterwarnings('ignore', category=pd.errors.SettingWithCopyWarning)

# --- CONFIGURATION ---
OUTPUT_FILE = "graph.json"
TARGET_BRANCHING_FACTOR = 7  # The "Rule of 7" (Clusters)
GOLD_PAN_SIZE = 5            # Top articles to keep at the Hub level
MIN_CLUSTER_SIZE = 5         # Don't split if smaller than this

def load_shards(directory):
    """Ingests the Holographic Shards (JSON context files)."""
    shards = []
    if not directory.exists():
         directory = Path(__file__).parent / directory
    
    files = list(directory.glob("*.json"))
    print(f"💎 Found {len(files)} shards in {directory}...")
    
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                # Weighting: Title (3x), Keywords (2x), Subtopics (1x)
                soup = (
                    (data.get('t', '') + " ") * 3 + 
                    (" ".join(data.get('kw', [])) + " ") * 2 + 
                    " ".join(data.get('sub', []))
                )
                
                shards.append({
                    "id": data.get('id', f.stem),
                    "label": data.get('t', 'Untitled'),
                    "soup": soup,
                    "keywords": data.get('kw', []) + data.get('sub', []),
                    "type": "article"
                })
        except Exception as e:
            print(f"⚠️ Error loading {f.name}: {e}")
            
    return pd.DataFrame(shards)

def load_market_data(directory=Path(".")):
    """Loads SEMRush/GSC CSV data for gravity weighting."""
    if not directory.exists():
        directory = Path(__file__).parent

    files = list(directory.glob("*bulk_us*.csv"))
    if not files:
        # print("ℹ️ No market data (CSV) found. Graph will be unweighted.")
        return {}
    
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    print(f"💰 Loading market gravity from: {latest_file.name}")
    
    try:
        df = pd.read_csv(latest_file)
        market_map = {}
        for _, row in df.iterrows():
            kw = str(row['Keyword']).lower().strip()
            try:
                vol = int(row['Volume'])
            except:
                vol = 0
            market_map[kw] = vol
        return market_map
    except Exception as e:
        print(f"⚠️ Error loading market data: {e}")
        return {}

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

def get_cluster_label(df_cluster, market_data=None):
    """Determines the name of a Hub."""
    all_keywords = [kw for sublist in df_cluster['keywords'] for kw in sublist]
    if not all_keywords:
        return "Misc"
    
    counts = Counter(all_keywords)
    candidates = counts.most_common(5)
    
    if market_data:
        best_kw = candidates[0][0]
        best_score = -1
        
        for kw, freq in candidates:
            vol = market_data.get(kw.lower().strip(), 0)
            score = freq * np.log1p(vol)
            
            if score > best_score:
                best_score = score
                best_kw = kw
        return best_kw
        
    return candidates[0][0]

def calculate_gravity(keywords, market_data):
    if not market_data or not keywords: return 0
    max_vol = 0
    for kw in keywords:
        k_clean = kw.lower().strip()
        vol = market_data.get(k_clean, 0)
        if vol > max_vol: max_vol = vol
    if max_vol > 0: return np.log1p(max_vol)
    return 0

def add_article_node(row, parent_id, current_depth, nodes, links, market_data, velocity_data):
    """Helper to create an article node and link."""
    gravity_boost = calculate_gravity(row['keywords'], market_data)
    
    # Match filename/ID to GSC slug
    slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', row['id'])
    health = velocity_data.get(slug, {})
    
    node = {
        "id": row['id'],
        "group": "article",
        "depth": current_depth,
        "label": row['label'],
        "val": 5 + gravity_boost,
        "parentId": parent_id,
        "status": health.get("status", "unknown"),
        "velocity": health.get("velocity", 0),
        "clicks": health.get("total_clicks", 0)
    }
    nodes.append(node)
    links.append({
        "source": parent_id,
        "target": row['id'],
        "type": "article_link"
    })

def recursive_cluster(df_slice, parent_id, current_depth, nodes, links, market_data, velocity_data, vectorizer=None):
    """The Gold Panning Recursive Engine."""
    df = df_slice.copy()
    
    # 0. Enrich with Clicks for Sorting
    df['sort_clicks'] = df['id'].apply(lambda x: velocity_data.get(re.sub(r'^\d{4}-\d{2}-\d{2}-', '', x), {}).get('total_clicks', 0))
    df = df.sort_values(by='sort_clicks', ascending=False)

    # 1. STOP CONDITION (Small groups just get attached)
    if len(df) <= TARGET_BRANCHING_FACTOR + GOLD_PAN_SIZE:
        for _, row in df.iterrows():
            add_article_node(row, parent_id, current_depth, nodes, links, market_data, velocity_data)
        return

    # 2. THE GOLD PAN (Extract Top Items)
    # These stay attached to the Current Hub (parent_id)
    gold = df.head(GOLD_PAN_SIZE)
    remainder = df.iloc[GOLD_PAN_SIZE:].copy() # Important: Copy to avoid SettingWithCopy
    
    for _, row in gold.iterrows():
        add_article_node(row, parent_id, current_depth, nodes, links, market_data, velocity_data)

    # 3. CLUSTER THE REST
    if len(remainder) == 0:
        return

    if vectorizer is None:
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
    
    try:
        # Fit on remainder
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
        for cluster_id in range(TARGET_BRANCHING_FACTOR):
            cluster_data = remainder[remainder['cluster'] == cluster_id]
            
            if len(cluster_data) == 0:
                continue
            
            hub_label = get_cluster_label(cluster_data, market_data)
            new_hub_id = f"{parent_id}_{cluster_id}"
            
            hub_base_val = max(10, 40 - (current_depth * 10))
            hub_gravity = 0
            if market_data:
                 vol = market_data.get(hub_label.lower().strip(), 0)
                 if vol > 0:
                     hub_gravity = np.log1p(vol) * 1.5
            
            nodes.append({
                "id": new_hub_id,
                "group": "hub",
                "depth": current_depth + 1,
                "label": hub_label,
                "val": hub_base_val + hub_gravity,
                "parentId": parent_id,
                "status": "hub"
            })
            
            links.append({
                "source": parent_id,
                "target": new_hub_id,
                "type": "hub_link"
            })
            
            recursive_cluster(
                cluster_data, 
                new_hub_id, 
                current_depth + 1, 
                nodes, 
                links,
                market_data,
                velocity_data
            )
            
    except Exception as e:
        print(f"⚠️ Clustering fallback at depth {current_depth}: {e}")
        # Fallback: Just attach everything in remainder to parent
        for _, row in remainder.iterrows():
            add_article_node(row, parent_id, current_depth, nodes, links, market_data, velocity_data)

def main():
    print("🚀 Initializing Hierarchy Builder...")
    parser = argparse.ArgumentParser(description="Build D3 Hierarchy Graph")
    common.add_target_argument(parser)
    args = parser.parse_args()

    # Dynamic Path Resolution
    posts_dir = common.get_target_path(args)
    context_dir = posts_dir / "_context"
    
    df = load_shards(context_dir) 
    
    if df.empty:
        print(f"❌ No data found in {context_dir}")
        return
        
    market_data = load_market_data()
    velocity_data = load_velocity_data() 

    nodes = [{
        "id": "hub_0",
        "group": "root",
        "depth": 0,
        "label": "HOME",
        "val": 50,
        "parentId": None,
        "status": "root"
    }]
    links = []

    print(f"🧠 Clustering {len(df)} articles using Rule of {TARGET_BRANCHING_FACTOR}...")
    recursive_cluster(df, "hub_0", 0, nodes, links, market_data, velocity_data)

    output_data = {"nodes": nodes, "links": links}
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=None)
        
    print(f"✅ Hierarchy generated: {len(nodes)} nodes, {len(links)} links.")
    print(f"💾 Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()