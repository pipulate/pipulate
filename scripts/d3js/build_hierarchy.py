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

# Silence the specific warning if copy usage is correct logic-wise
warnings.filterwarnings('ignore', category=pd.errors.SettingWithCopyWarning)

# --- CONFIGURATION ---
# Adjust path to your context folder relative to script execution location
CONTEXT_DIR = Path("/home/mike/repos/MikeLev.in/_posts/_context") 
OUTPUT_FILE = "graph.json"
TARGET_BRANCHING_FACTOR = 7  # The "Rule of 7"
MIN_CLUSTER_SIZE = 5         # Don't split if smaller than this

def load_shards(directory):
    """Ingests the Holographic Shards (JSON context files)."""
    shards = []
    # Handle relative path resolution if run from different dir
    if not directory.exists():
         # Fallback try relative to this file
         directory = Path(__file__).parent / directory
    
    files = list(directory.glob("*.json"))
    print(f"💎 Found {len(files)} shards in {directory}...")
    
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                # Create a rich semantic soup for vectorization
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

def load_market_data(directory=Path(".")):
    """Loads SEMRush/GSC CSV data for gravity weighting."""
    # Look for files matching the pattern in the current directory
    # This handles both relative execution and direct script location if needed
    if not directory.exists():
        directory = Path(__file__).parent

    files = list(directory.glob("*bulk_us*.csv"))
    if not files:
        print("ℹ️ No market data (CSV) found. Graph will be unweighted.")
        return {}
    
    # Pick the newest file
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    print(f"💰 Loading market gravity from: {latest_file.name}")
    
    try:
        df = pd.read_csv(latest_file)
        market_map = {}
        for _, row in df.iterrows():
            # Clean keyword: lowercase, strip
            kw = str(row['Keyword']).lower().strip()
            # Handle volume being a string with commas? Usually pandas handles int, but careful
            try:
                vol = int(row['Volume'])
            except:
                vol = 0
            market_map[kw] = vol
        return market_map
    except Exception as e:
        print(f"⚠️ Error loading market data: {e}")
        return {}

def get_cluster_label(df_cluster, market_data=None):
    """
    Determines the name of a Hub.
    Uses frequency count, but breaks ties with Market Volume if available.
    """
    all_keywords = [kw for sublist in df_cluster['keywords'] for kw in sublist]
    if not all_keywords:
        return "Misc"
    
    # Count frequency
    counts = Counter(all_keywords)
    
    # Get top 5 candidates by internal frequency
    candidates = counts.most_common(5)
    
    # If we have market data, weigh the candidates by volume
    # This ensures we pick "Python" (High Vol) over "MyScript" (Low Vol) 
    # even if "MyScript" appears slightly more often in the cluster.
    if market_data:
        best_kw = candidates[0][0]
        best_score = -1
        
        for kw, freq in candidates:
            # Score = Frequency * log(Volume + 1)
            # This favors high volume but requires the word to actually appear often
            vol = market_data.get(kw.lower().strip(), 0)
            score = freq * np.log1p(vol)
            
            if score > best_score:
                best_score = score
                best_kw = kw
        return best_kw
        
    return candidates[0][0]

def calculate_gravity(keywords, market_data):
    """Calculates additional node radius based on max keyword volume."""
    if not market_data or not keywords:
        return 0
    
    max_vol = 0
    for kw in keywords:
        k_clean = kw.lower().strip()
        vol = market_data.get(k_clean, 0)
        if vol > max_vol:
            max_vol = vol
            
    if max_vol > 0:
        # Logarithmic scale: 
        # 100 search vol -> +4.6 px
        # 1000 search vol -> +6.9 px
        # 100k search vol -> +11.5 px
        return np.log1p(max_vol)
    return 0

def recursive_cluster(df_slice, parent_id, current_depth, nodes, links, market_data, vectorizer=None):
    """
    The Recursive Mitosis engine. Splits groups until they fit the Rule of 7.
    """
    # Explicit copy to avoid SettingWithCopyWarning
    df = df_slice.copy()
    
    # --- STOP CONDITION ---
    if len(df) <= TARGET_BRANCHING_FACTOR + 2: # Fuzzy tolerance
        for _, row in df.iterrows():
            # Calculate Article Gravity
            gravity_boost = calculate_gravity(row['keywords'], market_data)
            
            nodes.append({
                "id": row['id'],
                "group": "article",
                "depth": current_depth,
                "label": row['label'],
                "val": 5 + gravity_boost, # Base size 5 + market boost
                "parentId": parent_id
            })
            links.append({
                "source": parent_id,
                "target": row['id'],
                "type": "article_link"
            })
        return

    # --- VECTORIZATION ---
    if vectorizer is None:
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
    
    try:
        tfidf_matrix = vectorizer.fit_transform(df['soup'])
        
        # SVD for dimensionality reduction
        n_components = min(5, len(df) - 1) 
        if n_components > 1:
            svd = TruncatedSVD(n_components=n_components)
            matrix = svd.fit_transform(tfidf_matrix)
        else:
            matrix = tfidf_matrix

        # --- CLUSTERING ---
        kmeans = MiniBatchKMeans(
            n_clusters=TARGET_BRANCHING_FACTOR,
            random_state=42,
            n_init=10,
            batch_size=256
        )
        clusters = kmeans.fit_predict(matrix)
        df.loc[:, 'cluster'] = clusters 
        
        # --- RECURSION ---
        for cluster_id in range(TARGET_BRANCHING_FACTOR):
            cluster_data = df[df['cluster'] == cluster_id]
            
            if len(cluster_data) == 0:
                continue
            
            # Label the Hub
            hub_label = get_cluster_label(cluster_data, market_data)
            new_hub_id = f"{parent_id}_{cluster_id}"
            
            # Calculate Hub Gravity (Boost if label is high volume)
            hub_base_val = max(10, 40 - (current_depth * 10))
            hub_gravity = 0
            if market_data:
                 vol = market_data.get(hub_label.lower().strip(), 0)
                 if vol > 0:
                     hub_gravity = np.log1p(vol) * 1.5 # Slight multiplier for hubs
            
            nodes.append({
                "id": new_hub_id,
                "group": "hub",
                "depth": current_depth + 1,
                "label": hub_label,
                "val": hub_base_val + hub_gravity,
                "parentId": parent_id
            })
            
            links.append({
                "source": parent_id,
                "target": new_hub_id,
                "type": "hub_link"
            })
            
            # Recurse
            recursive_cluster(
                cluster_data, 
                new_hub_id, 
                current_depth + 1, 
                nodes, 
                links,
                market_data
            )
            
    except ValueError as e:
        print(f"⚠️ Clustering fallback at depth {current_depth}: {e}")
        # Fallback: Just dump as articles
        for _, row in df.iterrows():
            gravity_boost = calculate_gravity(row['keywords'], market_data)
            nodes.append({
                "id": row['id'],
                "group": "article",
                "depth": current_depth,
                "label": row['label'],
                "val": 5 + gravity_boost,
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
        
    # 2. Load Market Data (Optional)
    market_data = load_market_data()

    # 3. Prepare Root
    nodes = [{
        "id": "hub_0",
        "group": "root",
        "depth": 0,
        "label": "HOME",
        "val": 50,
        "parentId": None 
    }]
    links = []

    # 4. Start Recursive Cloning
    print(f"🧠 Clustering {len(df)} articles using Rule of {TARGET_BRANCHING_FACTOR}...")
    recursive_cluster(df, "hub_0", 0, nodes, links, market_data)

    # 5. Export
    output_data = {"nodes": nodes, "links": links}
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=None) # Compact JSON
        
    print(f"✅ Hierarchy generated: {len(nodes)} nodes, {len(links)} links.")
    print(f"💾 Saved to {OUTPUT_FILE}")
    
    # 6. Inject into HTML 
    try:
        html_path = Path("ideal_hierarchy_master.html")
        if html_path.exists():
            print("💉 Injecting data into HTML visualization...")
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import re
            json_str = json.dumps(output_data)
            
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
