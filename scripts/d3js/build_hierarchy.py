import json
import glob
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import TruncatedSVD
from collections import Counter
import warnings

# Silence the specific warning if copy usage is correct logic-wise
warnings.filterwarnings('ignore', category=pd.errors.SettingWithCopyWarning)

# --- CONFIGURATION ---
CONTEXT_DIR = Path("/home/mike/repos/MikeLev.in/_posts/_context")  # Adjust path to your context folder
OUTPUT_FILE = "graph.json"
TARGET_BRANCHING_FACTOR = 7  # The "Rule of 7"
MIN_CLUSTER_SIZE = 5         # Don't split if smaller than this

def load_shards(directory):
    """Ingests the Holographic Shards (JSON context files)."""
    shards = []
    files = list(directory.glob("*.json"))
    print(f"💎 Found {len(files)} shards in {directory}...")
    
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                #Create a rich semantic soup for vectorization
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
                    "keywords": data.get('kw', []) + data.get('sub', []), # For labeling
                    "type": "article"
                })
        except Exception as e:
            print(f"⚠️ Error loading {f.name}: {e}")
            
    return pd.DataFrame(shards)

def get_cluster_label(df_cluster):
    """
    Determines the name of a Hub by finding the most common 
    significant keyword in that cluster.
    """
    all_keywords = [kw for sublist in df_cluster['keywords'] for kw in sublist]
    if not all_keywords:
        return "Misc"
    
    # Simple frequency count for V1
    # V2 could use TF-IDF per cluster to find unique terms
    counts = Counter(all_keywords)
    return counts.most_common(1)[0][0]

def recursive_cluster(df_slice, parent_id, current_depth, nodes, links, vectorizer=None):
    """
    The Recursive Mitosis engine. Splits groups until they fit the Rule of 7.
    """
    # Explicit copy to avoid SettingWithCopyWarning
    df = df_slice.copy()
    
    # --- STOP CONDITION ---
    # If the group is small enough, these are just articles on a page.
    # We attach them to the parent and stop.
    if len(df) <= TARGET_BRANCHING_FACTOR + 2: # Fuzzy tolerance
        for _, row in df.iterrows():
            nodes.append({
                "id": row['id'],
                "group": "article",
                "depth": current_depth,
                "label": row['label'],
                "val": 5, # Size of bubble
                "parentId": parent_id
            })
            links.append({
                "source": parent_id,
                "target": row['id'],
                "type": "article_link"
            })
        return

    # --- VECTORIZATION ---
    # We re-vectorize at each step to find local distinctions.
    # (Global vectors might miss subtle differences within a niche topic)
    if vectorizer is None:
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
    
    try:
        tfidf_matrix = vectorizer.fit_transform(df['soup'])
        
        # SVD for dimensionality reduction (helps K-Means on small datasets)
        # We need n_components < n_samples
        n_components = min(5, len(df) - 1) 
        if n_components > 1:
            svd = TruncatedSVD(n_components=n_components)
            matrix = svd.fit_transform(tfidf_matrix)
        else:
            matrix = tfidf_matrix

        # --- CLUSTERING ---
        # We try to force exactly 'TARGET_BRANCHING_FACTOR' clusters
        kmeans = MiniBatchKMeans(
            n_clusters=TARGET_BRANCHING_FACTOR,
            random_state=42,
            n_init=10,
            batch_size=256
        )
        clusters = kmeans.fit_predict(matrix)
        df.loc[:, 'cluster'] = clusters # Safe assignment
        
        # --- RECURSION ---
        for cluster_id in range(TARGET_BRANCHING_FACTOR):
            cluster_data = df[df['cluster'] == cluster_id]
            
            if len(cluster_data) == 0:
                continue
            
            # Create a HUB node for this cluster
            hub_label = get_cluster_label(cluster_data)
            new_hub_id = f"{parent_id}_{cluster_id}"
            
            # Visual weight decreases with depth
            hub_val = max(10, 40 - (current_depth * 10))
            
            nodes.append({
                "id": new_hub_id,
                "group": "hub",
                "depth": current_depth + 1,
                "label": hub_label,
                "val": hub_val,
                "parentId": parent_id
            })
            
            links.append({
                "source": parent_id,
                "target": new_hub_id,
                "type": "hub_link"
            })
            
            # Recurse into this new hub
            recursive_cluster(
                cluster_data, 
                new_hub_id, 
                current_depth + 1, 
                nodes, 
                links
            )
            
    except ValueError as e:
        # Fallback if clustering fails (e.g., too few samples for SVD)
        # Just attach remaining as articles
        print(f"⚠️ Clustering fallback at depth {current_depth}: {e}")
        for _, row in df.iterrows():
            nodes.append({
                "id": row['id'],
                "group": "article",
                "depth": current_depth,
                "label": row['label'],
                "val": 5,
                "parentId": parent_id
            })
            links.append({
                "source": parent_id,
                "target": row['id'],
                "type": "article_link"
            })

def main():
    print("🚀 Initializing Hierarchy Builder...")
    
    # 1. Load Data
    df = load_shards(CONTEXT_DIR)
    if df.empty:
        print("❌ No data found. Check CONTEXT_DIR path.")
        return

    # 2. Prepare Root
    nodes = [{
        "id": "hub_0",
        "group": "root",
        "depth": 0,
        "label": "HOME",
        "val": 50,
        "parentId": None # Root has no parent
    }]
    links = []

    # 3. Start Recursive Cloning
    print(f"🧠 Clustering {len(df)} articles using Rule of {TARGET_BRANCHING_FACTOR}...")
    recursive_cluster(df, "hub_0", 0, nodes, links)

    # 4. Export
    output_data = {"nodes": nodes, "links": links}
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=None) # Compact JSON
        
    print(f"✅ Hierarchy generated: {len(nodes)} nodes, {len(links)} links.")
    print(f"💾 Saved to {OUTPUT_FILE}")
    
    # 5. Inject into HTML (Safe Replacement Method)
    try:
        html_path = Path("ideal_hierarchy_master.html")
        if html_path.exists():
            print("💉 Injecting data into HTML visualization...")
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find the placeholder using regex, but perform replacement using string slicing
            # or simple string replacement if unique enough.
            # Here we use regex to FIND the span, but manual string reconstruction
            # to avoid regex substitution issues with backslashes.
            import re
            json_str = json.dumps(output_data)
            
            # Look for: const rawGraph = { ... };
            match = re.search(r'const rawGraph = \{.*?\};', content, flags=re.DOTALL)
            
            if match:
                start, end = match.span()
                new_content = content[:start] + f'const rawGraph = {json_str};' + content[end:]
                
                with open("ideal_hierarchy_master_real.html", 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print("✅ Created 'ideal_hierarchy_master_real.html' with live data.")
            else:
                print("⚠️ Could not find 'const rawGraph = {...};' placeholder in HTML file.")
                
    except Exception as e:
        print(f"⚠️ HTML Injection failed: {e}")

if __name__ == "__main__":
    main()
