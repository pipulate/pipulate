import json
import re
import warnings
import argparse
from pathlib import Path
from collections import Counter

import pandas as pd
import numpy as np
import frontmatter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import TruncatedSVD

import common

warnings.filterwarnings('ignore', category=pd.errors.SettingWithCopyWarning)

# --- GLOBAL CONFIGURATION ---
TARGET_BRANCHING_FACTOR = 7  # The "Rule of 7"
GOLD_PAN_SIZE = 5            # Top articles kept at hub level
NAVGRAPH_FILE = "navgraph.json"
GRAPH_FILE = "graph.json"

# --- 1. UNIFIED DATA INGESTION ---

def slugify(text):
    if not text: return ""
    text = str(text).lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text)
    return text.strip('-')

def load_enriched_shards(context_dir, posts_dir):
    """
    Deep Ingestion: Reads JSON shards AND Markdown Frontmatter.
    This ensures the Graph and the Nav use the exact same Titles and Permalinks.
    """
    shards = []
    if not context_dir.exists():
         print(f"⚠️ Context dir {context_dir} does not exist.")
         return pd.DataFrame()

    files = list(context_dir.glob("*.json"))
    print(f"💎 Loading {len(files)} shards from {context_dir}...")
    
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            md_path = posts_dir / f"{f.stem}.md"
            if not md_path.exists():
                continue

            post = frontmatter.load(md_path)
            
            # --- DEFENSIVE TITLE EXTRACTION ---
            title = post.metadata.get('title')
            if not title:
                title = data.get('t', 'Untitled')
            if not title:
                title = "Untitled"
            # ----------------------------------

            # Weighted Soup: Title gets 3x weight
            soup = (
                (str(title) + " ") * 3 + 
                (" ".join(data.get('kw', [])) + " ") * 2 + 
                " ".join(data.get('sub', []))
            )
            
            date_val = post.metadata.get('date', data.get('d', ''))
            
            shards.append({
                "id": f.stem,
                "title": str(title), # Force string
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
    if not directory.exists(): directory = Path(__file__).parent
    velocity_file = directory / "gsc_velocity.json"
    if not velocity_file.exists(): return {}
    try:
        with open(velocity_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        slug_map = {}
        for key, metrics in data.items():
            if key.startswith("_"): continue
            slug = key.strip('/').split('/')[-1]
            slug_map[slug] = metrics
        return slug_map
    except: return {}

def load_market_data(directory=Path(".")):
    if not directory.exists(): directory = Path(__file__).parent
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

# --- 2. CANONICAL CLUSTERING LOGIC ---

def get_cluster_candidates(df_cluster, market_data=None):
    """Returns a list of (keyword, score) tuples sorted by relevance."""
    all_keywords = [kw for sublist in df_cluster['keywords'] for kw in sublist]
    if not all_keywords: return [("Misc", 0)]
    
    counts = Counter(all_keywords)
    candidates = counts.most_common(10) # Buffer for collisions
    
    scored_candidates = []
    for kw, freq in candidates:
        if not kw: continue 
        score = freq
        if market_data:
            vol = market_data.get(str(kw).lower().strip(), 0)
            score = freq * np.log1p(vol)
        scored_candidates.append((kw, score))
        
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    return scored_candidates

def calculate_node_gravity(label, keywords, market_data):
    """Calculates visual size (gravity) for D3."""
    base = 0
    if not label: label = "Untitled"
    
    if market_data:
        # Check label volume
        base += np.log1p(market_data.get(str(label).lower(), 0))
        # Check max keyword volume
        max_kw_vol = 0
        for kw in keywords:
            if not kw: continue
            vol = market_data.get(str(kw).lower(), 0)
            if vol > max_kw_vol: max_kw_vol = vol
        base += np.log1p(max_kw_vol)
    return 5 + base  # Minimum size 5

def build_canonical_tree(df_slice, current_node, current_depth, market_data, velocity_data, vectorizer=None):
    """
    The Single Logic Stream.
    Builds a recursive dictionary (Tree) that represents the Truth.
    """
    df = df_slice.copy()

    # Sort by GSC Clicks (High velocity content floats to top)
    df['sort_clicks'] = df['id'].apply(lambda x: velocity_data.get(re.sub(r'^\d{4}-\d{2}-\d{2}-', '', x), {}).get('total_clicks', 0))
    df = df.sort_values(by='sort_clicks', ascending=False)

    def attach_article(row):
        # Calculate gravity for the article based on its keywords
        grav = calculate_node_gravity(row['title'], row['keywords'], market_data)
        
        # Get status from GSC
        slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', row['id'])
        gsc_meta = velocity_data.get(slug, {})
        
        article_node = {
            "type": "article",
            "id": row['id'],
            "title": str(row['title']), # Force string
            "permalink": row['permalink'],
            "date": row['date'],
            "gravity": grav,
            "status": gsc_meta.get("status", "unknown"),
            "velocity": gsc_meta.get("velocity", 0),
            "clicks": gsc_meta.get("total_clicks", 0)
        }
        current_node.setdefault('children_articles', []).append(article_node)

    # 1. Stop Condition
    if len(df) <= TARGET_BRANCHING_FACTOR + GOLD_PAN_SIZE:
        for _, row in df.iterrows(): attach_article(row)
        return

    # 2. Gold Pan (High Value Items stay at this level)
    gold = df.head(GOLD_PAN_SIZE)
    remainder = df.iloc[GOLD_PAN_SIZE:].copy()

    for _, row in gold.iterrows(): attach_article(row)

    if len(remainder) == 0: return

    # 3. Clustering
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

        kmeans = MiniBatchKMeans(n_clusters=TARGET_BRANCHING_FACTOR, random_state=42, n_init=10, batch_size=256)
        clusters = kmeans.fit_predict(matrix)
        remainder.loc[:, 'cluster'] = clusters

        # Collision Tracking (Scoped to this level of recursion)
        used_slugs = set()

        for cluster_id in range(TARGET_BRANCHING_FACTOR):
            cluster_data = remainder[remainder['cluster'] == cluster_id]
            if len(cluster_data) == 0: continue

            # Semantic Labeling & Collision Resolution
            candidates = get_cluster_candidates(cluster_data, market_data)
            
            hub_label = "Misc"
            for kw, score in candidates:
                if not kw: continue
                test_slug = slugify(kw)
                if test_slug not in used_slugs:
                    hub_label = kw
                    break
            else:
                # Fallback: Append number
                top_kw = candidates[0][0]
                base_slug = slugify(top_kw)
                counter = 2
                while f"{base_slug}-{counter}" in used_slugs:
                    counter += 1
                hub_label = f"{top_kw} {counter}"

            slug = slugify(hub_label)
            used_slugs.add(slug)
            
            # Create Hub Node
            hub_gravity = calculate_node_gravity(hub_label, [hub_label], market_data)
            # Boost Hub gravity based on depth (root is massive, leaves are smaller)
            hub_val = max(10, 50 - (current_depth * 10)) + hub_gravity

            new_hub_node = {
                "type": "hub",
                "id": f"{current_node['id']}_{cluster_id}",
                "title": hub_label,
                "permalink": f"{current_node['permalink']}{slug}/",
                "blurb": f"Explore {len(cluster_data)} articles about {hub_label}.",
                "gravity": hub_val,
                "children_hubs": [],
                "children_articles": []
            }
            
            current_node.setdefault('children_hubs', []).append(new_hub_node)

            # Recurse
            build_canonical_tree(
                cluster_data, new_hub_node, current_depth + 1, 
                market_data, velocity_data
            )

    except Exception as e:
        print(f"⚠️ Clustering fallback at depth {current_depth}: {e}")
        for _, row in remainder.iterrows(): attach_article(row)

# --- 3. PROJECTORS ---

def project_d3_graph(tree_node, nodes, links):
    """
    Projector B: Flattens the Canonical Tree into D3 Nodes/Links.
    """
    # Create the node for D3
    d3_node = {
        "id": tree_node['id'],
        "label": tree_node['title'],
        "group": "hub", # tree_node['type'],
        "val": tree_node.get('gravity', 20),
        "status": "hub",
        # D3 specific logic can go here (e.g. depth)
    }
    # Don't add root twice if it's already seeded, but here we just append
    nodes.append(d3_node)

    # Process Articles (Leaves)
    for article in tree_node.get('children_articles', []):
        art_node = {
            "id": article['id'],
            "label": article['title'],
            "group": "article",
            "val": article.get('gravity', 5),
            "status": article.get('status', 'unknown'),
            "velocity": article.get('velocity', 0)
        }
        nodes.append(art_node)
        links.append({
            "source": tree_node['id'],
            "target": article['id'],
            "type": "article_link"
        })

    # Process Sub-Hubs (Recursion)
    for hub in tree_node.get('children_hubs', []):
        links.append({
            "source": tree_node['id'],
            "target": hub['id'],
            "type": "hub_link"
        })
        project_d3_graph(hub, nodes, links)

# --- MAIN EXECUTION ---

def main():
    print("🚀 Initializing Cartographer (Unified Graph Builder)...")
    parser = argparse.ArgumentParser()
    common.add_target_argument(parser)
    args = parser.parse_args()

    posts_dir = common.get_target_path(args)
    context_dir = posts_dir / "_context"

    if not context_dir.exists():
        print(f"❌ Context dir not found: {context_dir}")
        return

    # 1. LOAD DATA
    df = load_enriched_shards(context_dir, posts_dir)
    if df.empty:
        print("❌ No data found.")
        return
        
    market_data = load_market_data()
    velocity_data = load_velocity_data()

    # 2. BUILD CANONICAL TREE
    print(f"🧠 Clustering {len(df)} articles into Canonical Tree...")
    canonical_tree = {
        "type": "hub",
        "id": "root",
        "title": "Home",
        "permalink": "/",
        "blurb": "Welcome to the knowledge graph.",
        "gravity": 60,
        "children_hubs": [],
        "children_articles": []
    }
    
    build_canonical_tree(df, canonical_tree, 0, market_data, velocity_data)

    # 3. EXPORT NAVGRAPH (JSON Tree for Jekyll)
    # The canonical tree structure matches the NavGraph requirements closely
    with open(NAVGRAPH_FILE, 'w', encoding='utf-8') as f:
        json.dump(canonical_tree, f, indent=2)
    print(f"✅ Generated NavGraph: {NAVGRAPH_FILE}")

    # 4. EXPORT GRAPH (Flat JSON for D3)
    nodes = []
    links = []
    # Seed nodes/links via recursion
    project_d3_graph(canonical_tree, nodes, links)
    
    d3_data = {"nodes": nodes, "links": links}
    with open(GRAPH_FILE, 'w', encoding='utf-8') as f:
        json.dump(d3_data, f, indent=None) # Minified for network speed
    print(f"✅ Generated D3 Graph: {GRAPH_FILE} ({len(nodes)} nodes)")

if __name__ == "__main__":
    main()