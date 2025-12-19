import json
import glob
from pathlib import Path
import pandas as pd
import numpy as np
import frontmatter  # Requires: pip install python-frontmatter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import TruncatedSVD
from collections import Counter
import re
import warnings

# Silence warnings
warnings.filterwarnings('ignore', category=pd.errors.SettingWithCopyWarning)

# --- CONFIGURATION ---
# Paths relative to the script execution or absolute
CONTEXT_DIR = Path("/home/mike/repos/MikeLev.in/_posts/_context")
POSTS_DIR = Path("/home/mike/repos/MikeLev.in/_posts") 
OUTPUT_FILE = "navgraph.json"

TARGET_BRANCHING_FACTOR = 7  # Rule of 7
GOLD_PAN_SIZE = 5            # Articles to keep at this level
MIN_CLUSTER_SIZE = 5         # Minimum items to force a split

def slugify(text):
    """Turns a label into a URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text)
    return text.strip('-')

def load_enriched_shards():
    """
    Ingests shards AND merges with Frontmatter from actual Markdown files.
    This ensures we have the canonical permalink and manual description.
    """
    shards = []
    files = list(CONTEXT_DIR.glob("*.json"))
    print(f"💎 Loading {len(files)} shards & enriching from Markdown...")
    
    for f in files:
        try:
            # 1. Load the AI Context (The Semantic Signal)
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            # 2. Load the Physical Article (The Metadata)
            md_path = POSTS_DIR / f"{f.stem}.md"
            if not md_path.exists():
                print(f"⚠️ Warning: Markdown file missing for {f.name}")
                continue

            post = frontmatter.load(md_path)
            
            # 3. Create the Semantic Soup
            soup = (
                (data.get('t', '') + " ") * 3 + 
                (" ".join(data.get('kw', [])) + " ") * 2 + 
                " ".join(data.get('sub', []))
            )

            # 4. Build the Object
            # FIX: Ensure date is a string (YAML parser might return datetime object)
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

def load_market_data(directory=Path(".")):
    """Loads SEMRush/GSC CSV data for gravity weighting."""
    if not directory.exists():
        directory = Path(__file__).parent

    files = list(directory.glob("*bulk_us*.csv"))
    if not files:
        return {}
    
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    print(f"💰 Loading market gravity from: {latest_file.name}")
    
    try:
        df = pd.read_csv(latest_file)
        market_map = {}
        for _, row in df.iterrows():
            kw = str(row['Keyword']).lower().strip()
            try: vol = int(row['Volume'])
            except: vol = 0
            market_map[kw] = vol
        return market_map
    except:
        return {}

def load_velocity_data(directory=Path(".")):
    """Loads GSC velocity/health data."""
    if not directory.exists():
        directory = Path(__file__).parent
        
    velocity_file = directory / "gsc_velocity.json"
    if not velocity_file.exists():
        return {}
        
    print(f"❤️ Loading health velocity from: {velocity_file.name}")
    try:
        with open(velocity_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def get_cluster_label(df_cluster, market_data):
    """Determines the best name for a Hub."""
    all_keywords = [kw for sublist in df_cluster['keywords'] for kw in sublist]
    if not all_keywords: return "Misc"
    
    counts = Counter(all_keywords)
    candidates = counts.most_common(5)
    
    best_kw = candidates[0][0]
    best_score = -1
    
    if market_data:
        for kw, freq in candidates:
            vol = market_data.get(kw.lower().strip(), 0)
            score = freq * np.log1p(vol)
            if score > best_score:
                best_score = score
                best_kw = kw
    
    return best_kw

def calculate_gravity(row, market_data, velocity_data):
    """Calculates the sorting score."""
    max_vol = 0
    if market_data:
        for kw in row['keywords']:
            vol = market_data.get(kw.lower().strip(), 0)
            if vol > max_vol: max_vol = vol
            
    # Match Logic for GSC (stripping date prefix usually found in filenames)
    # Adjust this regex if your filenames don't start with YYYY-MM-DD
    slug_match = re.search(r'\d{4}-\d{2}-\d{2}-(.*)', row['id'])
    slug = slug_match.group(1) if slug_match else row['id']
    
    gsc_clicks = 0
    if velocity_data:
        gsc_clicks = velocity_data.get(slug, {}).get('total_clicks', 0)

    # Composite Score
    # FIX: Cast to native float for JSON serialization
    return float((np.log1p(max_vol) * 1.0) + (np.log1p(gsc_clicks) * 5.0))

def build_tree_recursive(df_slice, current_depth, market_data, velocity_data, vectorizer=None, used_slugs=None):
    """
    Recursively builds the NavGraph dictionary.
    """
    if used_slugs is None: used_slugs = set()
    
    # 1. Score and Sort
    df = df_slice.copy()
    df['score'] = df.apply(lambda row: calculate_gravity(row, market_data, velocity_data), axis=1)
    df = df.sort_values('score', ascending=False)
    
    node = {
        "children_hubs": [],
        "children_articles": []
    }
    
    # 2. Stop Condition / Leaf Node
    if len(df) <= TARGET_BRANCHING_FACTOR + GOLD_PAN_SIZE:
        # Dump everything as articles
        for _, row in df.iterrows():
            node["children_articles"].append({
                "title": row['title'],
                "permalink": row['permalink'],
                "blurb": row['description'],
                "date": row['date'],
                "gravity": row['score']
            })
        return node

    # 3. Gold Pan (Top Articles stay here)
    gold_df = df.head(GOLD_PAN_SIZE)
    for _, row in gold_df.iterrows():
        node["children_articles"].append({
            "title": row['title'],
            "permalink": row['permalink'],
            "blurb": row['description'],
            "date": row['date'],
            "gravity": row['score']
        })

    # 4. Cluster the Remainder
    remainder_df = df.iloc[GOLD_PAN_SIZE:].copy()
    
    if vectorizer is None:
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
    
    try:
        tfidf_matrix = vectorizer.fit_transform(remainder_df['soup'])
        n_components = min(5, len(remainder_df) - 1)
        matrix = TruncatedSVD(n_components).fit_transform(tfidf_matrix) if n_components > 1 else tfidf_matrix
        
        kmeans = MiniBatchKMeans(n_clusters=TARGET_BRANCHING_FACTOR, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(matrix)
        remainder_df.loc[:, 'cluster'] = clusters
        
        for cluster_id in range(TARGET_BRANCHING_FACTOR):
            cluster_data = remainder_df[remainder_df['cluster'] == cluster_id]
            if len(cluster_data) == 0: continue
            
            # Determine Hub Identity
            hub_label = get_cluster_label(cluster_data, market_data)
            
            # Slug Deduplication Strategy
            base_slug = slugify(hub_label)
            slug = base_slug
            counter = 1
            while slug in used_slugs:
                counter += 1
                slug = f"{base_slug}-{counter}"
            used_slugs.add(slug)
            
            # Recursive Call
            child_node = build_tree_recursive(cluster_data, current_depth + 1, market_data, velocity_data, vectorizer, used_slugs)
            
            # Enrich Child Node with Hub Metadata
            child_node["title"] = hub_label
            child_node["permalink"] = f"/{slug}/"
            child_node["id"] = f"hub_{slug}"
            
            node["children_hubs"].append(child_node)
            
    except Exception as e:
        print(f"⚠️ Clustering failed at depth {current_depth}: {e}. Dumping as flat articles.")
        for _, row in remainder_df.iterrows():
             node["children_articles"].append({
                "title": row['title'],
                "permalink": row['permalink'],
                "gravity": row['score']
            })

    return node

def main():
    print("🚀 Initializing NavGraph Builder...")
    
    df = load_enriched_shards()
    if df.empty:
        print("❌ No data. Check paths.")
        return
        
    market_data = load_market_data()
    velocity_data = load_velocity_data()
    
    print(f"🧠 Building NavGraph from {len(df)} articles...")
    
    # Build the Root
    nav_tree = build_tree_recursive(df, 0, market_data, velocity_data)
    
    # Decorate Root
    nav_tree["title"] = "Home"
    nav_tree["permalink"] = "/"
    nav_tree["id"] = "root"
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(nav_tree, f, indent=2)
        
    print(f"✅ NavGraph generated.")
    print(f"💾 Saved to {OUTPUT_FILE}")
    print("👉 Next Step: Run the Jekyll Page Generator against this JSON.")

if __name__ == "__main__":
    main()
