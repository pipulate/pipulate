import json
import math
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
from sklearn.cluster import AgglomerativeClustering, KMeans, MiniBatchKMeans
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
        hub_urls.append(f"  <url><loc>{base_url}{top_hub['permalink']}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.85</priority></url>")
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

_RESERVED_HUB_SLUGS = frozenset({
    "misc", "assets", "images", "pages", "feed", "latest",
    "about", "futureproof", "api", "discord", "index",
})

_EXPLICIT_KW_ALIASES = {
    "model-context-protocol": ("mcp", "MCP"),
    "gsc": ("google-search-console", "Google Search Console"),
    "google-search-console": ("google-search-console", "Google Search Console"),
    "cli": ("command-line", "Command Line"),
    "command-line-interface": ("command-line", "Command Line"),
    "command-line": ("command-line", "Command Line"),
    "search-engine-optimization": ("seo", "SEO"),
    "seo": ("seo", "SEO"),
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
            if not s or s in _RESERVED_HUB_SLUGS:
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
    """Rank candidate hub slugs by Bayesian-smoothed specificity with a 14% support floor."""
    h_size = max(1, len(indices))
    c_counts = Counter(
        cs for idx in indices for cs in doc_kw_lists[idx]
        if cs not in excluded_slugs and cs not in _RESERVED_HUB_SLUGS
    )
    if not c_counts:
        return [("topic", "Topic", 0, 1, 0.0)]
    min_support = max(3, min(10, int(round(0.14 * h_size)))) if h_size >= 15 else 1
    eligible = [item for item in c_counts.items() if item[1] >= min_support] or list(c_counts.items())
    scored = []
    for cs, c in eligible:
        g = max(1, global_df[cs])
        spec_score = (c * c) / (((h_size + 4.0) * (g + 15.0)) ** 0.5)
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


def _extract_prototype_terms(tfidf_mat, feature_names, indices, top_n=75):
    """Extract L2-normalized sparse Rocchio prototype weights for JSON persistence."""
    if not indices:
        return {}
    mean_vec = np.asarray(tfidf_mat[indices].mean(axis=0)).ravel()
    top_idx = np.argsort(mean_vec)[::-1][:top_n]
    picked = [(str(feature_names[i]), float(mean_vec[i])) for i in top_idx if mean_vec[i] > 1e-5]
    norm = math.sqrt(sum(v * v for _, v in picked)) or 1.0
    return {t: round(v / norm, 5) for t, v in picked}


def compute_two_tier_hub_plan(df_raw, posts_dir, cand_k=0, n_pillars=0, bud_cap=75):
    """Pre-baked 2-Tier Spherical K-Means + Ward Pillar Hierarchy + River Streaming Radar."""
    df = df_raw.copy()
    df["sort_date"] = [
        d if (d and d != "None") else (i[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", i) else "")
        for d, i in zip(df["date"], df["id"])
    ]
    df = df.sort_values(by=["sort_date", "id"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    n_docs = len(df)
    chosen_k = cand_k if (cand_k and cand_k > 1) else (28 if n_docs >= 500 else max(2, n_docs // 25))
    chosen_p = n_pillars if (n_pillars and n_pillars > 1) else min(9, max(2, round(chosen_k / 3.0)))

    doc_kw_lists, global_df, canon_titles, merged_syns = _build_keyword_canon(df)
    vec = TfidfVectorizer(stop_words="english", max_features=2500, ngram_range=(1, 2), sublinear_tf=True)
    tfidf_mat = vec.fit_transform(df["soup"])
    n_comp = min(32, max(2, n_docs - 2), max(2, tfidf_mat.shape[1] - 1))
    dense_mat = Normalizer(copy=False).fit_transform(
        TruncatedSVD(n_components=n_comp, random_state=42).fit_transform(tfidf_mat)
    )
    feature_names = vec.get_feature_names_out()

    km = KMeans(n_clusters=chosen_k, random_state=42, n_init=20)
    labels = km.fit_predict(dense_mat)
    raw_clusters = []
    for cid in range(chosen_k):
        idxs = np.where(labels == cid)[0].tolist()
        if idxs:
            raw_clusters.append((cid, idxs, _rank_hub_keywords(idxs, doc_kw_lists, global_df, canon_titles, set())))
    raw_clusters.sort(key=lambda x: (-x[2][0][4], -len(x[1]), x[0]))

    used_slugs = set()
    hub_records = []
    for cid, idxs, _ in raw_clusters:
        ranked = _rank_hub_keywords(idxs, doc_kw_lists, global_df, canon_titles, used_slugs)
        h_slug, h_title, c_hit, g_hit, spec = ranked[0]
        if h_slug in used_slugs:
            h_slug = f"{h_slug}-{cid}"
        used_slugs.add(h_slug)
        sub_mat = dense_mat[idxs]
        cent = sub_mat.mean(axis=0)
        cn = float(np.linalg.norm(cent)) or 1.0
        cent = cent / cn
        hub_records.append({
            "cid": cid,
            "slug": h_slug,
            "title": h_title,
            "permalink": f"/{h_slug}/",
            "parent_slug": None,
            "idxs": idxs,
            "centroid": cent,
            "cohesion": float(np.mean(sub_mat @ cent)),
            "g_hit": g_hit,
            "spec": spec,
            "prototype_terms": _extract_prototype_terms(tfidf_mat, feature_names, idxs),
            "prototype_keywords": {cs: round(sc, 4) for cs, _, _, _, sc in ranked[:20] if sc > 0},
        })

    if len(hub_records) > chosen_p >= 2:
        s_lbls = AgglomerativeClustering(n_clusters=chosen_p, linkage="ward").fit_predict(
            np.vstack([r["centroid"] for r in hub_records])
        )
        groups = {}
        for pos, sl in enumerate(s_lbls):
            groups.setdefault(int(sl), []).append(hub_records[pos])
        for grp in groups.values():
            grp.sort(
                key=lambda r: (
                    -(len(r["idxs"]) * (0.5 + r["cohesion"]) * (1.0 + 0.12 * math.log1p(r["g_hit"]))),
                    r["slug"],
                )
            )
            p_slug = grp[0]["slug"]
            for child in grp[1:]:
                child["parent_slug"] = p_slug

    try:
        import river
        from river.drift import ADWIN
        river_ver = getattr(river, "__version__", "ok")
        adwins = {r["slug"]: ADWIN(delta=0.05) for r in hub_records}
    except Exception:
        river_ver, adwins = "fallback", {}

    active_slugs = {r["slug"] for r in hub_records}
    doc_to_hub = {idx: r["slug"] for r in hub_records for idx in r["idxs"]}
    cents = {r["slug"]: r["centroid"] for r in hub_records}
    drift_hits = Counter()
    nov_ema = {s: 0.25 for s in active_slugs}
    hub_mom, hub_last = {s: 0.0 for s in active_slugs}, {s: 0 for s in active_slugs}
    kw_mom, kw_last, kw_tot = {}, {}, Counter()
    h_kw_mom = {s: {} for s in active_slugs}
    h_kw_last = {s: {} for s in active_slugs}
    h_kw_cnt = {s: Counter() for s in active_slugs}
    decay = 0.985

    for step, doc_idx in enumerate(reversed(range(n_docs))):
        hs = doc_to_hub.get(doc_idx)
        if not hs:
            continue
        nov = max(0.0, 1.0 - float(dense_mat[doc_idx] @ cents[hs]))
        nov_ema[hs] = 0.90 * nov_ema[hs] + 0.10 * nov
        if hs in adwins:
            adwins[hs].update(nov)
            if getattr(adwins[hs], "drift_detected", False):
                drift_hits[hs] += 1
        hub_mom[hs] = hub_mom[hs] * (decay ** (step - hub_last[hs])) + 1.0
        hub_last[hs] = step
        for cs in doc_kw_lists[doc_idx]:
            if cs in active_slugs or cs in _RESERVED_HUB_SLUGS:
                continue
            kw_mom[cs] = kw_mom.get(cs, 0.0) * (decay ** (step - kw_last.get(cs, step))) + 1.0
            kw_last[cs] = step
            kw_tot[cs] += 1
            h_kw_mom[hs][cs] = h_kw_mom[hs].get(cs, 0.0) * (decay ** (step - h_kw_last[hs].get(cs, step))) + 1.0
            h_kw_last[hs][cs] = step
            h_kw_cnt[hs][cs] += 1

    f_step = max(0, n_docs - 1)
    h_vel_raw = {s: hub_mom[s] * (decay ** (f_step - hub_last[s])) for s in active_slugs}
    vel_sum = sum(h_vel_raw.values()) or 1.0
    for r in hub_records:
        s = r["slug"]
        v_share = h_vel_raw[s] / vel_sum
        v_boost = min(0.35, max(0.0, (v_share * len(active_slugs) - 1.0) * 0.12))
        r["vel_pct"] = v_share * 100.0
        r["drift_hits"] = int(drift_hits[s])
        r["pressure"] = (len(r["idxs"]) / float(bud_cap)) * (
            0.55 + nov_ema[s] + v_boost + (0.15 if drift_hits[s] else 0.0)
        )
        cands = [
            (m * (decay ** (f_step - h_kw_last[s][cs])), h_kw_cnt[s][cs], cs, canon_titles.get(cs, cs))
            for cs, m in h_kw_mom[s].items() if h_kw_cnt[s][cs] >= 5
        ]
        cands.sort(reverse=True)
        r["emerging"] = cands[0] if cands else None

    emerging_global = []
    for cs, m in kw_mom.items():
        if kw_tot[cs] >= 6:
            best_h = max(active_slugs, key=lambda s: h_kw_cnt[s][cs])
            emerging_global.append((
                cs, canon_titles.get(cs, cs), m * (decay ** (f_step - kw_last[cs])),
                kw_tot[cs], best_h, h_kw_cnt[best_h][cs],
            ))
    emerging_global.sort(key=lambda x: (-x[2], -x[3], x[0]))

    pages_dir = posts_dir.parent / "pages"
    retired_map, direct_keep = {}, 0
    if pages_dir.is_dir():
        active_perms = {r["permalink"] for r in hub_records}
        art_to_hub = {df.at[i, "permalink"]: r["permalink"] for r in hub_records for i in r["idxs"]}
        default_hub = sorted(hub_records, key=lambda r: (-len(r["idxs"]), r["slug"]))[0]["permalink"]
        stem_perm, stem_arts = {}, {}
        for mp in sorted(pages_dir.glob("*.md")):
            txt = mp.read_text(encoding="utf-8", errors="ignore")
            pm = re.search(r"^permalink:\s*(\S+)", txt, re.M)
            if pm:
                p_str = pm.group(1).strip()
                stem_perm[mp.stem] = p_str if p_str.endswith("/") else p_str + "/"
                stem_arts[mp.stem] = re.findall(r"^\*\s+\[.*?\]\((/[^)\s]+)\)", txt, re.M)
        for stem, old_p in sorted(stem_perm.items()):
            if old_p in active_perms:
                direct_keep += 1
                continue
            sub_a = [
                ap for s2, al in stem_arts.items()
                if (stem.startswith("root_") and (s2 == stem or s2.startswith(stem + "_"))) or s2 == stem
                for ap in al if ap in art_to_hub
            ]
            if sub_a:
                retired_map[old_p] = sorted(
                    Counter(art_to_hub[ap] for ap in sub_a).items(), key=lambda x: (-x[1], x[0])
                )[0][0]
            else:
                retired_map[old_p] = default_hub

    return {
        "df": df,
        "dense_mat": dense_mat,
        "merged_syns": merged_syns,
        "chosen_k": chosen_k,
        "chosen_p": chosen_p,
        "hub_records": hub_records,
        "river_ver": river_ver,
        "emerging_global": emerging_global,
        "retired_map": retired_map,
        "direct_keep": direct_keep,
    }


def _score_article_against_hubs(soup_text, doc_kws, hub_defs, analyzer):
    """Deterministic Rocchio TF + Canonical Keyword scorer for Assign-Only routing."""
    tf_counts = Counter(analyzer(soup_text))
    doc_weights = {t: 1.0 + math.log(c) for t, c in tf_counts.items()}
    d_norm = math.sqrt(sum(v * v for v in doc_weights.values())) or 1.0
    doc_unit = {t: v / d_norm for t, v in doc_weights.items()}
    best_slug = hub_defs[0]["slug"]
    best_score = -1.0
    for h in hub_defs:
        p_terms = h.get("prototype_terms", {})
        cos_sim = sum(w * p_terms[t] for t, w in doc_unit.items() if t in p_terms)
        p_kws = h.get("prototype_keywords", {})
        kw_bonus = sum(p_kws.get(cs, 0.0) for cs in doc_kws) * 0.08
        if h["slug"] in doc_kws:
            kw_bonus += 0.25
        score = cos_sim + kw_bonus
        if score > best_score:
            best_score = score
            best_slug = h["slug"]
    return best_slug


def build_settled_canonical_tree(
    df_raw, posts_dir, site_title, site_blurb, reseed=False, cand_k=0, n_pillars=0, bud_cap=75
):
    """Seed once into _data/hubs_manifest.json, settle assign-only thereafter, and harvest 301s."""
    from datetime import datetime

    repo_root = posts_dir.parent
    data_dir = repo_root / "_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = data_dir / "hubs_manifest.json"
    retired_path = data_dir / "retired_hubs.json"

    df = df_raw.copy()
    df["sort_date"] = [
        d if (d and d != "None") else (i[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", i) else "")
        for d, i in zip(df["date"], df["id"])
    ]
    df = df.sort_values(by=["sort_date", "id"], ascending=[False, True], kind="mergesort").reset_index(drop=True)

    root_node = {
        "type": "root",
        "id": "root",
        "title": site_title,
        "permalink": "/",
        "blurb": site_blurb,
        "gravity": 60,
        "children_hubs": [],
        "children_articles": [],
    }
    if len(df) <= 12:
        for _, row in df.iterrows():
            root_node["children_articles"].append({
                "type": "article",
                "id": str(row["id"]),
                "title": str(row["title"]),
                "permalink": row["permalink"],
                "date": row["sort_date"],
                "gravity": calculate_node_gravity(row["title"], row["keywords"]),
            })
        return root_node

    today = datetime.now().strftime("%Y-%m-%d")
    fresh_retired = {}

    if reseed or not manifest_path.is_file():
        plan = compute_two_tier_hub_plan(
            df, posts_dir, cand_k=cand_k, n_pillars=n_pillars, bud_cap=bud_cap
        )
        df = plan["df"]
        fresh_retired = dict(plan["retired_map"])
        kids_of = {
            r["slug"]: [c for c in plan["hub_records"] if c["parent_slug"] == r["slug"]]
            for r in plan["hub_records"]
        }
        pillars_seed = sorted(
            [r for r in plan["hub_records"] if r["parent_slug"] is None],
            key=lambda p: (-(len(p["idxs"]) + sum(len(c["idxs"]) for c in kids_of[p["slug"]])), p["slug"]),
        )
        ordered_recs = []
        for p in pillars_seed:
            ordered_recs.append(p)
            for c in sorted(kids_of[p["slug"]], key=lambda k: (-len(k["idxs"]), k["slug"])):
                ordered_recs.append(c)
        hubs_out = []
        assignments = {}
        for rec in ordered_recs:
            hubs_out.append({
                "slug": rec["slug"],
                "title": rec["title"],
                "permalink": rec["permalink"],
                "parent_slug": rec["parent_slug"],
                "seeded_at": today,
                "seeded_count": len(rec["idxs"]),
                "prototype_terms": rec["prototype_terms"],
                "prototype_keywords": rec["prototype_keywords"],
            })
            for idx in rec["idxs"]:
                assignments[str(df.at[idx, "id"])] = rec["slug"]
        manifest = {
            "schema_version": 1,
            "seeded_k": plan["chosen_k"],
            "pillar_count": plan["chosen_p"],
            "bud_capacity": bud_cap,
            "hubs": hubs_out,
            "assignments": dict(sorted(assignments.items())),
        }
        print(
            f"🌱 Seeded 2-Tier Hub Manifest ({plan['chosen_p']} Pillars -> "
            f"{len(hubs_out)} Permanent Hubs)."
        )
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hub_defs = list(manifest.get("hubs", []))
        valid_slugs = {h["slug"] for h in hub_defs}
        current_ids = set(df["id"].astype(str).tolist())
        assignments = {
            aid: hsl
            for aid, hsl in manifest.get("assignments", {}).items()
            if aid in current_ids and hsl in valid_slugs
        }
        missing_rows = [idx for idx in range(len(df)) if str(df.at[idx, "id"]) not in assignments]
        if missing_rows and hub_defs:
            doc_kw_lists, _, _, _ = _build_keyword_canon(df)
            analyzer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).build_analyzer()
            for idx in missing_rows:
                aid = str(df.at[idx, "id"])
                assignments[aid] = _score_article_against_hubs(
                    df.at[idx, "soup"], doc_kw_lists[idx], hub_defs, analyzer
                )
            print(
                f"🧭 Assign-Only Router: {len(missing_rows)} new article(s) settled into pinned hubs "
                f"(0 existing hubs or articles churned)."
            )
        manifest["assignments"] = dict(sorted(assignments.items()))

    new_m_text = json.dumps(manifest, indent=2) + "\n"
    old_m_text = manifest_path.read_text(encoding="utf-8") if manifest_path.is_file() else ""
    if new_m_text != old_m_text:
        manifest_path.write_text(new_m_text, encoding="utf-8")

    hub_defs = manifest.get("hubs", [])
    active_hub_perms = {h["permalink"] for h in hub_defs}
    default_hub = sorted(hub_defs, key=lambda h: (-h.get("seeded_count", 0), h["slug"]))[0]["permalink"]
    retired_ledger = {}
    if retired_path.is_file():
        try:
            retired_ledger = json.loads(retired_path.read_text(encoding="utf-8")) or {}
        except Exception:
            retired_ledger = {}
    retired_ledger.update(fresh_retired)
    for live_p in active_hub_perms:
        retired_ledger.pop(live_p, None)
    clean_retired = {}
    for old_p, tgt_p in sorted(retired_ledger.items()):
        hop = tgt_p
        seen_hops = {old_p}
        while hop in retired_ledger and hop not in seen_hops:
            seen_hops.add(hop)
            hop = retired_ledger[hop]
        if hop not in active_hub_perms:
            hop = default_hub
        if old_p != hop:
            clean_retired[old_p] = hop
    new_r_text = json.dumps(clean_retired, indent=2, sort_keys=True) + "\n"
    old_r_text = retired_path.read_text(encoding="utf-8") if retired_path.is_file() else ""
    if new_r_text != old_r_text:
        retired_path.write_text(new_r_text, encoding="utf-8")
        print(f"🗺️  Harvested {len(clean_retired)} hub-to-hub 301 redirect(s) -> {retired_path.name}")

    assignments = manifest.get("assignments", {})
    hub_articles = {h["slug"]: [] for h in hub_defs}
    for _, row in df.iterrows():
        aid = str(row["id"])
        hsl = assignments.get(aid)
        if hsl in hub_articles:
            hub_articles[hsl].append({
                "type": "article",
                "id": aid,
                "title": str(row["title"]),
                "permalink": row["permalink"],
                "date": row["sort_date"],
                "gravity": calculate_node_gravity(row["title"], row["keywords"]),
            })

    nodes_by_slug = {}
    for h in hub_defs:
        hsl = h["slug"]
        arts = hub_articles[hsl]
        depth_lvl = 1 if not h.get("parent_slug") else 2
        nodes_by_slug[hsl] = {
            "type": "hub",
            "id": hsl,
            "title": h["title"],
            "permalink": h["permalink"],
            "blurb": f"Explore {len(arts)} articles about {h['title']}.",
            "gravity": max(15, 55 - depth_lvl * 10) + min(30, len(arts) // 3),
            "children_hubs": [],
            "children_articles": arts,
        }

    pillars = []
    for h in hub_defs:
        hsl = h["slug"]
        psl = h.get("parent_slug")
        if psl and psl in nodes_by_slug and psl != hsl:
            nodes_by_slug[psl]["children_hubs"].append(nodes_by_slug[hsl])
        else:
            pillars.append(nodes_by_slug[hsl])

    root_node["children_hubs"] = pillars
    return root_node


def run_candidate_hub_report(df_raw, posts_dir, cand_k=0, n_pillars=0, bud_cap=75):
    """Read-only Pass 2 report: 2-Tier Ward Hierarchy + River Streaming Radar + 301 Audit."""
    plan = compute_two_tier_hub_plan(df_raw, posts_dir, cand_k=cand_k, n_pillars=n_pillars, bud_cap=bud_cap)
    df, dense_mat = plan["df"], plan["dense_mat"]
    hub_records = plan["hub_records"]

    print(f"\n📊 PASS 2 SEED-SETTLE-BUD REPORT ({len(df)} articles, River {plan['river_ver']})")
    print("=" * 96)
    print("1. TOP SYNONYM / PLURAL / ACRONYM CONSOLIDATIONS:")
    for c_slug, c_title, doc_cnt, variants in plan["merged_syns"][:10]:
        v_str = " + ".join(f"{vn}({vc})" for vn, vc in sorted(variants, key=lambda x: -x[1]))
        print(f"   /{c_slug}/ [{doc_cnt} docs] '{c_title}' <= {v_str}")

    print("\n2. RELEASED-LIMIT K-SWEEP (Deterministic Spherical K-Means + 1-Post Perturbation ARI):")
    print("   K  |  Silh  | Min | P25 | Med | P75 | Max | Gini | >Cap | N-1_ARI | Composite")
    print("   ---+--------+-----+-----+-----+-----+-----+------+------+---------+----------")
    for k in (7, 12, 16, 20, 24, 28):
        if k >= len(df):
            continue
        lbl = KMeans(n_clusters=k, random_state=42, n_init=15).fit_predict(dense_mat)
        sil = float(silhouette_score(dense_mat, lbl, metric="cosine"))
        ari = float(adjusted_rand_score(lbl[1:], KMeans(n_clusters=k, random_state=42, n_init=15).fit(dense_mat[1:]).labels_))
        sz = np.bincount(lbl, minlength=k)
        gini = _gini_coeff(sz)
        comp = sil * (0.5 + 0.5 * ari) * (1.0 - 0.25 * gini)
        p25, med, p75 = np.percentile(sz, [25, 50, 75])
        print(
            f"   {k:2d} | {sil:6.4f} | {int(sz.min()):3d} | {int(round(p25)):3d} | "
            f"{int(round(med)):3d} | {int(round(p75)):3d} | {int(sz.max()):3d} | "
            f"{gini:4.2f} | {int(np.sum(sz > bud_cap)):4d} |  {ari:6.4f} |   {comp:6.4f}"
        )

    pillars = [r for r in hub_records if r["parent_slug"] is None]
    kids_map = {p["slug"]: [r for r in hub_records if r["parent_slug"] == p["slug"]] for p in pillars}
    pillars.sort(key=lambda p: (-(len(p["idxs"]) + sum(len(c["idxs"]) for c in kids_map[p["slug"]])), p["slug"]))

    print(
        f"\n3. TWO-TIER WARD HIERARCHY ({len(pillars)} Macro-Pillars -> "
        f"{len(hub_records) - len(pillars)} Sub-Hubs = {len(hub_records)} Permanent /<slug>/ Hubs):"
    )
    print("   Hierarchy / Permalink               | Posts | Cohes | Vel% | ADWIN | Press | Top Unhomed Emerging Topic")
    print("   ------------------------------------+-------+-------+------+-------+-------+------------------------------")
    for p in pillars:
        em_p = f"{p['emerging'][3]} ({p['emerging'][1]}d, m={p['emerging'][0]:.1f})" if p["emerging"] else "-"
        print(
            f"   [P] {p['permalink']:<31} | {len(p['idxs']):5d} | {p['cohesion']:5.3f} | "
            f"{p['vel_pct']:4.1f} | {p['drift_hits']:5d} | {p['pressure']:5.2f} | {em_p}"
        )
        kids = sorted(kids_map[p["slug"]], key=lambda c: (-len(c["idxs"]), c["slug"]))
        for i_c, c in enumerate(kids):
            br = "└─" if i_c == len(kids) - 1 else "├─"
            em_c = f"{c['emerging'][3]} ({c['emerging'][1]}d, m={c['emerging'][0]:.1f})" if c["emerging"] else "-"
            print(
                f"     {br} {c['permalink']:<30} | {len(c['idxs']):5d} | {c['cohesion']:5.3f} | "
                f"{c['vel_pct']:4.1f} | {c['drift_hits']:5d} | {c['pressure']:5.2f} | {em_c}"
            )

    print("\n4. RIVER STREAMING RADAR — TOP UNHOMED KEYWORDS BUILDING BUDDING PRESSURE:")
    for cs, c_title, mom, tot_cnt, home_s, home_cnt in plan["emerging_global"][:10]:
        print(
            f"   • {c_title:<26} (/{cs}/) | RiverMom={mom:5.2f} | Total={tot_cnt:3d} docs | "
            f"Host Hub: /{home_s}/ ({home_cnt} docs)"
        )

    ret = plan["retired_map"]
    print(
        f"\n5. LIVE HUB CONTINUITY & 301 SNAP AUDIT: Direct 200 OK Survivors={plan['direct_keep']} | "
        f"Hub-to-Hub 301s={len(ret)} | Orphans=0"
    )
    for old_p, new_p in list(ret.items())[:8]:
        print(f"   301 {old_p:<40} -> {new_p}")
    print("=" * 96)


def main():
    print("🚀 Initializing Cartographer (Unified Graph Builder)...")
    parser = argparse.ArgumentParser()
    common.add_target_argument(parser)
    parser.add_argument(
        "--candidates",
        action="store_true",
        help="Read-only statistical report for deterministic candidate hubs and budding pressure.",
    )
    parser.add_argument("--cand-k", type=int, default=0, help="Explicit total hub K for --candidates (0=auto 28).")
    parser.add_argument("--pillars", type=int, default=0, help="Explicit Depth-1 Macro-Pillar count (0=auto 9).")
    parser.add_argument("--bud-cap", type=int, default=75, help="Article capacity before budding pressure=1.0.")
    parser.add_argument("--reseed", action="store_true", help="Force fresh K-Means + Ward seed of _data/hubs_manifest.json.")
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
        run_candidate_hub_report(
            df, posts_dir, cand_k=args.cand_k, n_pillars=args.pillars, bud_cap=args.bud_cap
        )
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
    
    canonical_tree = build_settled_canonical_tree(
        df,
        posts_dir,
        site_title=site_title,
        site_blurb=site_blurb,
        reseed=args.reseed,
        cand_k=args.cand_k,
        n_pillars=args.pillars,
        bud_cap=args.bud_cap,
    )

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
