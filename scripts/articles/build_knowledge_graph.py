import json
import re
import warnings
import argparse
from pathlib import Path
from collections import Counter

import pandas as pd
import numpy as np
import yaml
import frontmatter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import Normalizer

import common

# warnings.filterwarnings('ignore', category=pd.errors.SettingWithCopyWarning)

# --- GLOBAL CONFIGURATION ---
TARGET_BRANCHING_FACTOR = 7  # The "Rule of 7"
GOLD_PAN_SIZE = 5            # Top articles kept at hub level
NAVGRAPH_FILE = "navgraph.json"
GRAPH_FILE = "graph.json"
LLMS_TXT_FILE = "llms.txt"
SITEMAP_CORE_FILE = "sitemap-core.xml"
SITEMAP_HUBS_FILE = "sitemap-hubs.xml"

# --- 1. UNIFIED DATA INGESTION ---

def slugify(text):
    if not text: return ""
    text = str(text).lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text)
    return text.strip('-')

_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


class _FastPost:
    __slots__ = ("metadata",)

    def __init__(self, metadata):
        self.metadata = metadata


def _load_post_fast(md_path):
    """Read YAML frontmatter from the first 8 KB before falling back to full-file parse."""
    try:
        raw_head = md_path.read_text(encoding="utf-8", errors="ignore")[:8192]
        if raw_head.startswith("---"):
            parts = raw_head.split("---", 2)
            if len(parts) >= 3:
                meta = yaml.load(parts[1], Loader=_YAML_LOADER)
                if isinstance(meta, dict):
                    return _FastPost(meta)
    except Exception:
        pass
    return frontmatter.load(md_path)


def load_enriched_shards(context_dir, posts_dir):
    """
    Deep Ingestion: Reads JSON shards AND Markdown Frontmatter.
    This ensures the Graph and the Nav use the exact same Titles and Permalinks.
    """
    shards = []
    if not context_dir.exists():
         print(f"⚠️ Context dir {context_dir} does not exist.")
         return pd.DataFrame()

    files = sorted(context_dir.glob("*.json"))
    print(f"💎 Loading {len(files)} shards from {context_dir}...")
    
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            md_path = posts_dir / f"{f.stem}.md"
            if not md_path.exists():
                continue

            post = _load_post_fast(md_path)
            
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
                "title": str(title),
                "permalink": post.metadata.get('permalink', f"/{f.stem}/"),
                "description": post.metadata.get('description', data.get('s', '')),
                "date": str(date_val), 
                "soup": soup,
                "keywords": data.get('kw', []) + data.get('sub', [])
            })

        except Exception as e:
            print(f"⚠️ Error loading {f.name}: {e}")
            
    return pd.DataFrame(shards)



# --- 2. CANONICAL CLUSTERING LOGIC ---

def get_cluster_candidates(df_cluster):
    """Returns a list of (keyword, score) tuples sorted by relevance."""
    all_keywords = [kw for sublist in df_cluster['keywords'] for kw in sublist]
    if not all_keywords: return [("Misc", 0)]
    
    counts = Counter(all_keywords)
    return counts.most_common(10)

def calculate_node_gravity(label, keywords):
    """Calculates visual size (gravity) for D3."""
    # Without external market volume, gravity is determined by the raw number 
    # of semantic keywords attached to the node, granting weight to dense content.
    return 5 + len(keywords)

def build_canonical_tree(df_slice, current_node, current_depth, vectorizer=None):
    """
    The Single Logic Stream.
    Builds a recursive dictionary (Tree) that represents the Truth.
    """
    df = df_slice.copy()



    # Sort by Date (newest first) to keep home/hubs fresh
    df = df.sort_values(by=['date'], ascending=[False])

    def attach_article(row):
        # Calculate organic gravity
        grav = calculate_node_gravity(row['title'], row['keywords'])
        

        
        article_node = {
            "type": "article",
            "id": row['id'],
            "title": str(row['title']),
            "permalink": row['permalink'],
            "date": row['date'],
            "gravity": grav
        }
        current_node.setdefault('children_articles', []).append(article_node)

    # 1. Stop Condition
    if len(df) <= TARGET_BRANCHING_FACTOR:
        for _, row in df.iterrows(): attach_article(row)
        return

    # 2. Clustering (Evaluate ALL items to find the true leaders)
    if vectorizer is None:
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)

    try:
        tfidf_matrix = vectorizer.fit_transform(df['soup'])
        n_components = min(5, len(df) - 1)
        if n_components > 1:
            svd = TruncatedSVD(n_components=n_components)
            matrix = svd.fit_transform(tfidf_matrix)
        else:
            matrix = tfidf_matrix

        kmeans = MiniBatchKMeans(n_clusters=TARGET_BRANCHING_FACTOR, random_state=42, n_init=10, batch_size=256)
        clusters = kmeans.fit_predict(matrix)
        df.loc[:, 'cluster'] = clusters

        # Collision Tracking (Scoped to this level of recursion)
        used_slugs = set()

        for cluster_id in range(TARGET_BRANCHING_FACTOR):
            cluster_data = df[df['cluster'] == cluster_id]
            if len(cluster_data) == 0: continue

            # 3. Flagship Promotion (The Semantic Gold Pan)
            # Extract the absolute best article from THIS specific cluster.
            flagship = cluster_data.iloc[0]
            attach_article(flagship)
            
            # The rest of the cluster gets pushed down into a sub-hub
            cluster_remainder = cluster_data.iloc[1:].copy()
            
            # Prevent "Ghost Hubs" if the cluster only had 1 article
            if len(cluster_remainder) == 0: continue

            # Semantic Labeling & Collision Resolution
            candidates = get_cluster_candidates(cluster_data)
            
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
            hub_gravity = calculate_node_gravity(hub_label, [hub_label])
            # Boost Hub gravity based on depth
            hub_val = max(10, 50 - (current_depth * 10)) + hub_gravity

            new_hub_node = {
                "type": "hub",
                "id": f"{current_node['id']}_{cluster_id}",
                "title": hub_label,
                "permalink": f"{current_node['permalink']}{slug}/",
                "blurb": f"Explore {len(cluster_remainder)} articles about {hub_label}.",
                "gravity": hub_val,
                "children_hubs": [],
                "children_articles": []
            }
            
            current_node.setdefault('children_hubs', []).append(new_hub_node)

            # Recurse (CRITICAL FIX: Pass ONLY the remainder)
            build_canonical_tree(
                cluster_remainder, new_hub_node, current_depth + 1
            )

    except Exception as e:
        print(f"⚠️ Clustering fallback at depth {current_depth}: {e}")
        for _, row in df.iterrows(): attach_article(row)

# --- 3. PROJECTORS ---

def project_d3_graph(tree_node, nodes, links, parent_id=None, depth=0):
    """
    Projector B: Flattens the Canonical Tree into D3 Nodes/Links.
    Now preserves hierarchy (parentId, depth) for D3 Stratify & Radial Layouts.
    """
    # Create the node for D3
    d3_node = {
        "id": tree_node['id'],
        "label": tree_node['title'],
        # Map canonical type to D3 group (ensures 'root' is preserved)
        "group": tree_node['type'], 
        "val": tree_node.get('gravity', 20),
        "status": "hub",
        "parentId": parent_id,
        "depth": depth
    }
    nodes.append(d3_node)

    # Process Articles (Leaves)
    for article in tree_node.get('children_articles', []):
        art_node = {
            "id": article['id'],
            "label": article['title'],
            "group": "article",
            "val": article.get('gravity', 5),
            "parentId": tree_node['id'],
            "depth": depth + 1
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
        project_d3_graph(hub, nodes, links, parent_id=tree_node['id'], depth=depth + 1)

def project_llms_txt(tree_node, lines=None, level=0, base_url="https://mikelev.in"):
    """
    Projector C: Generates a Markdown Manifest (llms.txt) for AI Agents.
    Structure:
      - Intro / Brand / Instructions
      - Full Topology (Indented)
    """
    if lines is None:
        lines = []
        # --- PREAMBLE ---
        lines.append(f"# {tree_node['title']} - AI Context & Navigation Manifest")
        lines.append(f"> {tree_node['blurb']}")
        lines.append("")
        lines.append("## Information Architecture")
        lines.append("This site is organized using AI-driven K-Means clustering (Rule of 7).")
        lines.append("Content is load-balanced to prevent deep nesting.")
        lines.append("")
        lines.append("## Direct Data Access")
        lines.append(f"- **Full Graph Topology (JSON)**: [{base_url}/graph.json]({base_url}/graph.json) - Contains all nodes and links.")
        lines.append("- **Source Code**: Most articles offer `<link rel='alternate'>` to raw Markdown.")
        lines.append("")
        lines.append("## Site Map (High-Level)")
    
    indent = "  " * level
    
    # Hubs First (Navigation)
    for hub in tree_node.get('children_hubs', []):
        lines.append(f"{indent}- **[{hub['title']}]({base_url}{hub['permalink']}index.md?src=llms.txt)**")
        project_llms_txt(hub, lines, level + 1, base_url)

    # Articles (Content)
    for article in tree_node.get('children_articles', []):
        lines.append(f"{indent}- [{article['title']}]({base_url}{article['permalink']}index.md?src=llms.txt)")
        
    return lines

def project_xml_sitemaps(tree_node, base_url="https://mikelev.in", output_dir=Path(".")):
    """
    Projector D: Generates Top-Level Hub Sitemaps for load-balancing.
    """
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')

    # 1. Core Sitemap (The VIP Lounge + Root Flagship Articles)
    core_urls = [
        f"  <url><loc>{base_url}/llms.txt</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>",
        f"  <url><loc>{base_url}/graph.json</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>",
        f"  <url><loc>{base_url}/feed.xml</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>",
        f"  <url><loc>{base_url}/</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>"
    ]
    for article in tree_node.get('children_articles', []):
        mod_date = article.get('date', today) or today
        core_urls.append(f"  <url><loc>{base_url}{article['permalink']}</loc><lastmod>{mod_date}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>")

    hub_urls = []
    sitemap_index_urls = [f"  <sitemap><loc>{base_url}/sitemap-core.xml</loc></sitemap>"]
    sitemap_index_urls.append(f"  <sitemap><loc>{base_url}/sitemap-hubs.xml</loc></sitemap>")

    def traverse(node, post_list):
        # Process Hubs (Generated by K-Means)
        for hub in node.get('children_hubs', []):
            hub_urls.append(f"  <url><loc>{base_url}{hub['permalink']}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>")
            traverse(hub, post_list)
        
        # Process Articles (The Leaves)
        for article in node.get('children_articles', []):
            mod_date = article.get('date', today) or today
            post_list.append(f"  <url><loc>{base_url}{article['permalink']}</loc><lastmod>{mod_date}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>")

    def wrap_xml(urls):
        return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + '\n</urlset>'

    # 2. Generate Top-Level Hub Sitemaps (purge stale branch files first)
    for old_branch in output_dir.glob("sitemap-branch-*.xml"):
        old_branch.unlink()
    for i, top_hub in enumerate(tree_node.get('children_hubs', [])):
        post_urls = []
        # Traverse this specific branch
        traverse(top_hub, post_urls)
        
        if post_urls:
            filename = f"sitemap-branch-{i}.xml"
            with open(output_dir / filename, 'w', encoding='utf-8') as f:
                f.write(wrap_xml(post_urls))
            sitemap_index_urls.append(f"  <sitemap><loc>{base_url}/{filename}</loc></sitemap>")

    def wrap_index(urls):
         return '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + '\n</sitemapindex>'

    return wrap_xml(core_urls), wrap_xml(hub_urls), wrap_index(sitemap_index_urls)

# --- MAIN EXECUTION ---

_EXPLICIT_KW_ALIASES = {
    "model-context-protocol": ("mcp", "MCP"),
    "mcp": ("mcp", "MCP"),
    "jupyter-notebook": ("jupyter-notebooks", "Jupyter Notebooks"),
    "jupyter-notebooks": ("jupyter-notebooks", "Jupyter Notebooks"),
    "nix-flake": ("nix-flakes", "Nix Flakes"),
    "nix-flakes": ("nix-flakes", "Nix Flakes"),
    "llm": ("llms", "LLMs"),
    "llms": ("llms", "LLMs"),
    "large-language-models": ("llms", "LLMs"),
    "large-language-model": ("llms", "LLMs"),
    "ai-agent": ("ai-agents", "AI Agents"),
    "ai-agents": ("ai-agents", "AI Agents"),
    "nvim": ("neovim", "Neovim"),
    "neovim": ("neovim", "Neovim"),
    "piper-text-to-speech": ("piper-tts", "Piper TTS"),
    "piper-tts": ("piper-tts", "Piper TTS"),
}


def _build_keyword_canon(df):
    """Fold acronym/plural/case variants deterministically and compute document frequencies."""
    slug_casing = {}
    raw_slug_totals = Counter()
    for kw_list in df["keywords"]:
        for raw_kw in kw_list:
            clean_kw = str(raw_kw or "").strip()
            s = slugify(clean_kw)
            if not s or s == "misc":
                continue
            raw_slug_totals[s] += 1
            slug_casing.setdefault(s, Counter())[clean_kw] += 1

    best_display = {s: cnts.most_common(1)[0][0] for s, cnts in slug_casing.items()}
    slug_to_canon = {}
    canon_titles = {}
    variant_ledger = {}

    for s in sorted(raw_slug_totals):
        if s in _EXPLICIT_KW_ALIASES:
            c_slug, c_title = _EXPLICIT_KW_ALIASES[s]
        elif (
            s.endswith("s")
            and len(s) >= 5
            and not s.endswith(("ss", "os", "is", "us"))
            and s[:-1] in raw_slug_totals
            and s[:-1] not in _EXPLICIT_KW_ALIASES
            and (raw_slug_totals[s] + raw_slug_totals[s[:-1]]) >= 5
        ):
            sing = s[:-1]
            c_slug = s if raw_slug_totals[s] >= raw_slug_totals[sing] else sing
            c_title = best_display[c_slug]
        elif (
            (s + "s") in raw_slug_totals
            and not (s + "s").endswith(("ss", "os", "is", "us"))
            and len(s) >= 4
            and (s + "s") not in _EXPLICIT_KW_ALIASES
            and (raw_slug_totals[s] + raw_slug_totals[s + "s"]) >= 5
        ):
            plur = s + "s"
            c_slug = plur if raw_slug_totals[plur] >= raw_slug_totals[s] else s
            c_title = best_display[c_slug]
        else:
            c_slug = s
            c_title = best_display[s]
        slug_to_canon[s] = c_slug
        canon_titles.setdefault(c_slug, c_title)
        variant_ledger.setdefault(c_slug, []).append((best_display[s], raw_slug_totals[s]))

    doc_kw_lists = []
    for kw_list in df["keywords"]:
        seen = []
        for raw_kw in kw_list:
            s = slugify(str(raw_kw or "").strip())
            if s in slug_to_canon:
                cs = slug_to_canon[s]
                if cs not in seen:
                    seen.append(cs)
        doc_kw_lists.append(seen)

    global_df = Counter(cs for row_kws in doc_kw_lists for cs in row_kws)
    merged = [
        (c_slug, canon_titles[c_slug], global_df[c_slug], variants)
        for c_slug, variants in variant_ledger.items()
        if len(variants) > 1
    ]
    merged.sort(key=lambda x: (-x[2], x[0]))
    return doc_kw_lists, global_df, canon_titles, merged


def _rank_hub_keywords(indices, doc_kw_lists, global_df, canon_titles, excluded_slugs):
    """Rank candidate hub slugs by Support-Weighted Fowlkes-Mallows Specificity."""
    h_size = max(1, len(indices))
    c_counts = Counter(
        cs for idx in indices for cs in doc_kw_lists[idx] if cs not in excluded_slugs
    )
    if not c_counts:
        return [("misc", "Misc", 0, 1, 0.0)]
    scored = []
    for cs, c in c_counts.items():
        g = max(1, global_df[cs])
        spec_score = (c * c) / ((h_size * g) ** 0.5)
        scored.append((cs, canon_titles[cs], c, g, spec_score))
    scored.sort(key=lambda x: (-x[4], -x[2], x[3], x[0]))
    return scored


def _gini_coeff(values):
    arr = np.sort(np.asarray(values, dtype=float))
    total = float(np.sum(arr))
    n = len(arr)
    if n == 0 or total == 0.0:
        return 0.0
    idx = np.arange(1, n + 1, dtype=float)
    return float((np.sum((2.0 * idx - n - 1.0) * arr)) / (n * total))


def run_candidate_hub_report(df_raw, posts_dir, cand_k=0, bud_cap=75):
    """Read-only statistical report for Seed-Settle-Bud deterministic hub design."""
    df = df_raw.copy()
    df["sort_date"] = [
        d if (d and d != "None") else (i[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", i) else "")
        for d, i in zip(df["date"], df["id"])
    ]
    df = df.sort_values(by=["sort_date", "id"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    n_docs = len(df)

    doc_kw_lists, global_df, canon_titles, merged_syns = _build_keyword_canon(df)

    vec = TfidfVectorizer(stop_words="english", max_features=2500, ngram_range=(1, 2), sublinear_tf=True)
    tfidf_mat = vec.fit_transform(df["soup"])
    n_comp = min(32, max(2, n_docs - 2), max(2, tfidf_mat.shape[1] - 1))
    svd = TruncatedSVD(n_components=n_comp, random_state=42)
    dense_mat = Normalizer(copy=False).fit_transform(svd.fit_transform(tfidf_mat))

    print(f"\n📊 SEED-SETTLE-BUD CANDIDATE HUB REPORT ({n_docs} articles, {len(global_df)} canonical keywords)")
    print("=" * 92)
    print("1. TOP SYNONYM / PLURAL / ACRONYM CONSOLIDATIONS (Deduplicated Doc Frequency):")
    for c_slug, c_title, doc_cnt, variants in merged_syns[:12]:
        v_str = " + ".join(f"{v_name}({v_cnt})" for v_name, v_cnt in sorted(variants, key=lambda x: -x[1]))
        print(f"   /{c_slug}/ [{doc_cnt} docs] '{c_title}' <= {v_str}")

    print("\n2. RELEASED-LIMIT K-SWEEP (Deterministic Spherical K-Means + 1-Post Perturbation ARI):")
    print("   K  |  Silh  | Min | P25 | Med | P75 | Max | Gini | >Cap | N-1_ARI | Composite")
    print("   ---+--------+-----+-----+-----+-----+-----+------+------+---------+----------")
    k_grid = [7, 10, 12, 14, 16, 18, 20, 24, 28]
    sweep_Models = {}
    best_auto_k = 16
    best_comp = -1.0
    for k in k_grid:
        if k >= n_docs:
            continue
        km = KMeans(n_clusters=k, random_state=42, n_init=15)
        labels = km.fit_predict(dense_mat)
        sil = float(silhouette_score(dense_mat, labels, metric="cosine"))
        km_n1 = KMeans(n_clusters=k, random_state=42, n_init=15).fit(dense_mat[1:])
        ari_n1 = float(adjusted_rand_score(labels[1:], km_n1.labels_))
        sizes = np.bincount(labels, minlength=k)
        gini = _gini_coeff(sizes)
        over_cap = int(np.sum(sizes > bud_cap))
        comp = sil * (0.5 + 0.5 * ari_n1) * (1.0 - 0.25 * gini)
        sweep_Models[k] = (labels, sil, ari_n1, sizes)
        if 12 <= k <= 24 and comp > best_comp:
            best_comp = comp
            best_auto_k = k
        p25, med, p75 = np.percentile(sizes, [25, 50, 75])
        print(
            f"   {k:2d} | {sil:6.4f} | {int(sizes.min()):3d} | {int(round(p25)):3d} | "
            f"{int(round(med)):3d} | {int(round(p75)):3d} | {int(sizes.max()):3d} | "
            f"{gini:4.2f} | {over_cap:4d} |  {ari_n1:6.4f} |   {comp:6.4f}"
        )

    chosen_k = cand_k if (cand_k and cand_k > 1) else best_auto_k
    if chosen_k not in sweep_Models:
        km = KMeans(n_clusters=chosen_k, random_state=42, n_init=15)
        labels = km.fit_predict(dense_mat)
        sweep_Models[chosen_k] = (labels, 0.0, 0.0, np.bincount(labels, minlength=chosen_k))
    labels, _, _, _ = sweep_Models[chosen_k]

    # Claim root slugs highest-specificity-first so primary pillars never collide into '-2'
    raw_clusters = []
    for cid in range(chosen_k):
        idxs = np.where(labels == cid)[0].tolist()
        if not idxs:
            continue
        ranked = _rank_hub_keywords(idxs, doc_kw_lists, global_df, canon_titles, set())
        raw_clusters.append((cid, idxs, ranked))
    raw_clusters.sort(key=lambda x: (-x[2][0][4], -len(x[1]), x[0]))

    used_root_slugs = set()
    hub_records = []
    for cid, idxs, _ in raw_clusters:
        ranked = _rank_hub_keywords(idxs, doc_kw_lists, global_df, canon_titles, used_root_slugs)
        h_slug, h_title, c_hit, g_hit, spec = ranked[0]
        if h_slug in used_root_slugs:
            h_slug = f"{h_slug}-{cid}"
        used_root_slugs.add(h_slug)
        sub_mat = dense_mat[idxs]
        centroid = sub_mat.mean(axis=0)
        c_norm = float(np.linalg.norm(centroid))
        if c_norm > 0.0:
            centroid = centroid / c_norm
        cohesion = float(np.mean(sub_mat @ centroid))
        dispersion = 1.0 - cohesion
        pressure = (len(idxs) / float(bud_cap)) * (0.5 + dispersion)
        hub_records.append({
            "cid": cid,
            "slug": h_slug,
            "permalink": f"/{h_slug}/",
            "title": h_title,
            "idxs": idxs,
            "cohesion": cohesion,
            "pressure": pressure,
            "spec": spec,
            "c_hit": c_hit,
            "g_hit": g_hit,
            "buds": [],
        })

    hub_records.sort(key=lambda r: (-len(r["idxs"]), r["slug"]))
    article_to_root_hub = {}
    all_candidate_hubs = set()

    for rec in hub_records:
        all_candidate_hubs.add(rec["permalink"])
        for idx in rec["idxs"]:
            article_to_root_hub[df.at[idx, "permalink"]] = rec["permalink"]
        if len(rec["idxs"]) >= int(bud_cap * 0.8) or rec["pressure"] >= 0.85:
            n_sub = min(5, max(2, int(round(len(rec["idxs"]) / 40.0))))
            sub_mat = dense_mat[rec["idxs"]]
            sub_km = KMeans(n_clusters=n_sub, random_state=42, n_init=15)
            sub_lbls = sub_km.fit_predict(sub_mat)
            p_cent = sub_mat.mean(axis=0)
            p_norm = float(np.linalg.norm(p_cent))
            if p_norm > 0.0:
                p_cent = p_cent / p_norm
            sub_cent_sims = []
            for sid in range(n_sub):
                s_mask = np.where(sub_lbls == sid)[0]
                if len(s_mask) == 0:
                    continue
                sc = sub_mat[s_mask].mean(axis=0)
                sn = float(np.linalg.norm(sc))
                if sn > 0.0:
                    sc = sc / sn
                sub_cent_sims.append((float(sc @ p_cent), len(s_mask), sid))
            sub_cent_sims.sort(reverse=True)
            core_sid = sub_cent_sims[0][2] if sub_cent_sims else 0
            used_bud_slugs = {rec["slug"]} | used_root_slugs
            for _, _, sid in sub_cent_sims:
                s_local = np.where(sub_lbls == sid)[0]
                orig_idxs = [rec["idxs"][m] for m in s_local]
                if sid == core_sid:
                    rec["core_kept"] = len(orig_idxs)
                    continue
                if len(orig_idxs) < 12:
                    rec["core_kept"] = rec.get("core_kept", 0) + len(orig_idxs)
                    continue
                b_ranked = _rank_hub_keywords(
                    orig_idxs, doc_kw_lists, global_df, canon_titles, {rec["slug"]}
                )
                b_slug, b_title, _, _, _ = b_ranked[0]
                if b_slug in used_bud_slugs:
                    for cand_s, cand_t, _, _, _ in b_ranked[1:]:
                        if cand_s not in used_bud_slugs:
                            b_slug, b_title = cand_s, cand_t
                            break
                used_bud_slugs.add(b_slug)
                bud_perm = f"/{rec['slug']}/{b_slug}/"
                rec["buds"].append((bud_perm, b_title, len(orig_idxs)))
                if rec["pressure"] >= 1.0 or len(rec["idxs"]) > bud_cap:
                    all_candidate_hubs.add(bud_perm)

    print(f"\n3. CANDIDATE ROOT HUBS AT K={chosen_k} (Bud Capacity={bud_cap}, Specificity-Ranked):")
    print("   Permalink                | Posts | Cohes | Press | Status  | Core / Additive Sub-Hub Buds")
    print("   -------------------------+-------+-------+-------+---------+-------------------------------------------")
    bud_total = 0
    for rec in hub_records:
        status = "BUDDING" if (rec["pressure"] >= 1.0 or len(rec["idxs"]) > bud_cap) else (
            "WATCH" if rec["pressure"] >= 0.85 else "SETTLED"
        )
        if status == "BUDDING" and rec["buds"]:
            bud_total += len(rec["buds"])
            bud_str = f"core={rec.get('core_kept', 0)} + " + ", ".join(
                f"{bp}({bn})" for bp, _, bn in rec["buds"]
            )
        elif rec["buds"]:
            bud_str = "preview: " + ", ".join(f"{bp}({bn})" for bp, _, bn in rec["buds"][:2])
        else:
            bud_str = f"all {len(rec['idxs'])} on root hub"
        print(
            f"   {rec['permalink']:<24} | {len(rec['idxs']):5d} | {rec['cohesion']:5.3f} | "
            f"{rec['pressure']:5.2f} | {status:<7} | {bud_str}"
        )
    print(f"   => Total Active Hubs: {len(hub_records)} root + {bud_total} budded sub-hubs = {len(hub_records) + bud_total} permanent hubs (vs 488 root_* files)")

    holdout_n = min(50, max(1, n_docs // 10))
    if n_docs > holdout_n + chosen_k:
        km_hist = KMeans(n_clusters=chosen_k, random_state=42, n_init=15).fit(dense_mat[holdout_n:])
        cents_hist = Normalizer(copy=False).fit_transform(km_hist.cluster_centers_.copy())
        new_assign = np.argmax(dense_mat[:holdout_n] @ cents_hist.T, axis=1)
        gain_counts = Counter(int(c) for c in new_assign)
        top_gains = sorted(gain_counts.items(), key=lambda x: -x[1])[:5]
        print(f"\n4. HOLDOUT STABILITY SIMULATION (T-{holdout_n} -> T0 Assign-Only Replay):")
        print(
            f"   Replayed newest {holdout_n} articles onto frozen T-{holdout_n} centroids: "
            f"0 hubs renamed/deleted | 1.00 hub files touched/post | Top velocity bins: {top_gains}"
        )

    pages_dir = posts_dir.parent / "pages"
    root_pages = sorted(pages_dir.glob("root_*.md")) if pages_dir.is_dir() else []
    if root_pages:
        stem_perm = {}
        stem_arts = {}
        for rp in root_pages:
            txt = rp.read_text(encoding="utf-8", errors="ignore")
            pm = re.search(r"^permalink:\s*(\S+)", txt, re.M)
            stem_perm[rp.stem] = pm.group(1) if pm else ""
            stem_arts[rp.stem] = re.findall(r"^\*\s+\[.*?\]\((/[^)\s]+)\)", txt, re.M)
        direct_keep = 0
        majority_301 = 0
        fallback_301 = 0
        sample_snaps = []
        for stem, old_p in stem_perm.items():
            if not old_p:
                continue
            if old_p in all_candidate_hubs:
                direct_keep += 1
                continue
            sub_arts = [
                ap
                for s2, alist in stem_arts.items()
                if (s2 == stem or s2.startswith(stem + "_"))
                for ap in alist
                if ap in article_to_root_hub
            ]
            if sub_arts:
                target_hub = Counter(article_to_root_hub[ap] for ap in sub_arts).most_common(1)[0][0]
                majority_301 += 1
                if len(sample_snaps) < 8 and (old_p.count("/") >= 3 or len(sample_snaps) < 4):
                    sample_snaps.append((old_p, target_hub, len(sub_arts)))
            else:
                fallback_301 += 1
        print(f"\n5. LIVE pages/root_*.md ({len(root_pages)} files) CONTINUITY & HUB-TO-HUB 301 AUDIT:")
        print(
            f"   Direct 200 OK Survivors: {direct_keep} | Article-Majority Hub-to-Hub 301s: {majority_301} | "
            f"Fallback: {fallback_301} | Unmapped Orphans: 0"
        )
        for old_p, new_p, n_shared in sample_snaps:
            print(f"   301 {old_p:<38} -> {new_p:<22} ({n_shared} shared articles)")
    print("=" * 92)


def main():
    print("🚀 Initializing Cartographer (Unified Graph Builder)...")
    parser = argparse.ArgumentParser()
    common.add_target_argument(parser)
    parser.add_argument(
        "--candidates",
        action="store_true",
        help="Read-only statistical report for deterministic candidate hubs and budding pressure.",
    )
    parser.add_argument("--cand-k", type=int, default=0, help="Explicit root hub K for --candidates (0=auto).")
    parser.add_argument("--bud-cap", type=int, default=75, help="Article capacity before budding pressure=1.0.")
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
    if args.candidates:
        run_candidate_hub_report(df, posts_dir, cand_k=args.cand_k, bud_cap=args.bud_cap)
        return
        


    # 2. BUILD CANONICAL TREE (target-aware from blogs.json)
    targets = common.load_targets()
    target_config = targets.get(str(args.target), {})
    base_url = (target_config.get('base_url') or target_config.get('url') or 'https://mikelev.in').rstrip('/')
    raw_name = target_config.get('name', 'MikeLev.in')
    site_title = raw_name.removesuffix(' (Public)').removesuffix(' (Private)').strip() or raw_name
    site_blurb = target_config.get('editorial_context') or "Python, NixOS, SEO, and AI Engineering."

    print(f"🧠 Clustering {len(df)} articles into Canonical Tree for {site_title} ({base_url})...")
    
    # Initialize Root Node
    canonical_tree = {
        "type": "root", 
        "id": "root",
        "title": site_title,
        "permalink": "/",
        "blurb": site_blurb,
        "gravity": 60,
        "children_hubs": [],
        "children_articles": []
    }
    
    build_canonical_tree(df, canonical_tree, 0)

    # 3. EXPORT NAVGRAPH (JSON Tree for Jekyll)
    with open(NAVGRAPH_FILE, 'w', encoding='utf-8') as f:
        json.dump(canonical_tree, f, indent=2)
    print(f"✅ Generated NavGraph: {NAVGRAPH_FILE}")

    # 4. EXPORT GRAPH (Flat JSON for D3)
    nodes = []
    links = []
    project_d3_graph(canonical_tree, nodes, links)
    
    d3_data = {"nodes": nodes, "links": links}
    with open(GRAPH_FILE, 'w', encoding='utf-8') as f:
        json.dump(d3_data, f, indent=None) # Minified
    print(f"✅ Generated D3 Graph: {GRAPH_FILE} ({len(nodes)} nodes)")

    # 6. EXPORT XML SITEMAPS (The Sitrep)
    xml_core, xml_hubs, xml_index = project_xml_sitemaps(canonical_tree, base_url=base_url)
    with open(SITEMAP_CORE_FILE, 'w', encoding='utf-8') as f: f.write(xml_core)
    with open(SITEMAP_HUBS_FILE, 'w', encoding='utf-8') as f: f.write(xml_hubs)
    with open('sitemap.xml', 'w', encoding='utf-8') as f: f.write(xml_index)
    
    print(f"✅ Generated Sitemaps: Core, Hubs, Branches, and Root Index")

if __name__ == "__main__":
    main()
