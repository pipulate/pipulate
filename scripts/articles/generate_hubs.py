import json
import os
import re
from pathlib import Path
import shutil
import argparse
import common


NAVGRAPH_FILE = Path(__file__).resolve().parent / "navgraph.json"

THUMB_WIDTH = 480
THUMB_HEIGHT = 252
RECENT_START_MARKER = "<!-- START_RECENT_POSTS -->"
RECENT_END_MARKER = "<!-- END_RECENT_POSTS -->"


def _ensure_post_thumbnail(target_repo_root, raw_img_path, fallback_rel="/assets/images/AI_Readiness_Consultant_RFC_9111.png"):
    """Create or reuse a 480x252 (1.91:1) PIL thumbnail under /assets/images/thumbs/."""
    from PIL import Image
    rel_src = (raw_img_path or fallback_rel or "").strip()
    if not rel_src:
        return ""
    if not rel_src.startswith("/"):
        rel_src = "/" + rel_src
    src_file = target_repo_root / rel_src.lstrip("/")
    if not src_file.is_file():
        if not fallback_rel:
            return ""
        rel_src = fallback_rel if fallback_rel.startswith("/") else "/" + fallback_rel
        src_file = target_repo_root / rel_src.lstrip("/")
    if not src_file.is_file():
        return ""
    thumbs_dir = target_repo_root / "assets" / "images" / "thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    thumb_name = f"{src_file.stem}-{THUMB_WIDTH}x{THUMB_HEIGHT}.jpg"
    thumb_file = thumbs_dir / thumb_name
    thumb_rel = f"/assets/images/thumbs/{thumb_name}"
    try:
        if thumb_file.is_file() and thumb_file.stat().st_mtime >= src_file.stat().st_mtime:
            return thumb_rel
        im = Image.open(src_file).convert("RGBA")
        bg = Image.new("RGB", im.size, (17, 17, 17))
        bg.paste(im, mask=im.split()[3])
        src_w, src_h = bg.size
        target_ratio = THUMB_WIDTH / THUMB_HEIGHT
        src_ratio = src_w / max(1, src_h)
        if abs(src_ratio - target_ratio) <= 0.03:
            out = bg.resize((THUMB_WIDTH, THUMB_HEIGHT), Image.Resampling.LANCZOS)
        else:
            scale = min(THUMB_WIDTH / max(1, src_w), THUMB_HEIGHT / max(1, src_h))
            new_w = max(1, int(round(src_w * scale)))
            new_h = max(1, int(round(src_h * scale)))
            resized = bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
            out = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), (17, 17, 17))
            out.paste(resized, ((THUMB_WIDTH - new_w) // 2, (THUMB_HEIGHT - new_h) // 2))
        out.save(thumb_file, "JPEG", quality=82, optimize=True, progressive=True)
        return thumb_rel
    except Exception as exc:
        print(f"⚠️ Thumbnail fallback for {src_file.name}: {exc}")
        return rel_src


def _escape_liquid_html(text: str) -> str:
    """HTML-escape text and defang Liquid '{{' / '{%' delimiters for static Jekyll markdown pages."""
    import html
    return (
        html.escape(str(text or ""), quote=True)
        .replace("{{", "&#123;&#123;")
        .replace("{%", "&#123;%")
    )


def _render_pagination_nav(page_num: int, total_pages: int, total_posts: int, per_page: int) -> str:
    """Render dark-isolated Previous 10 / Next 10 static pagination controls."""
    if total_pages <= 1:
        return ""
    start_i = ((page_num - 1) * per_page) + 1
    end_i = min(total_posts, page_num * per_page)
    btn_base = (
        "display:inline-block;padding:0.42rem 0.9rem;border-radius:8px;"
        "font-weight:700;font-size:0.85rem;text-decoration:none !important;"
    )
    pri_style = btn_base + "background:#1f6feb;border:1px solid #58a6ff;color:#ffffff !important;"
    sec_style = btn_base + "background:rgba(56,139,253,0.14);border:1px solid rgba(88,166,255,0.45);color:#79c0ff !important;"
    links = []
    if page_num > 1:
        prev_href = "/" if page_num == 2 else f"/page/{page_num - 1}/"
        if page_num > 2:
            links.append(f'<a href="/" style="{sec_style}">« Newest</a>')
        links.append(f'<a href="{prev_href}" rel="prev" style="{sec_style}">← Previous {per_page}</a>')
    if page_num < total_pages:
        next_href = f"/page/{page_num + 1}/"
        links.append(f'<a href="{next_href}" rel="next" style="{pri_style}">Next {per_page} →</a>')
    return (
        '<nav class="archive-pagination" aria-label="Journal archive pagination" '
        'style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:0.75rem;'
        'margin:1.15rem 0;padding:0.75rem 1rem;border-radius:10px;border:1px solid rgba(88,166,255,0.35);'
        'background:linear-gradient(135deg,#0d1117 0%,#161b22 100%);color:#e6edf3;">\n'
        f'  <span style="font-size:0.84rem;color:#c9d1d9;">Showing <strong style="color:#ffffff;">{start_i:,}–{end_i:,}</strong> '
        f'of <strong style="color:#ffffff;">{total_posts:,}</strong> articles (Page {page_num:,} of {total_pages:,})</span>\n'
        f'  <div style="display:flex;flex-wrap:wrap;align-items:center;gap:0.55rem;">{" ".join(links)}</div>\n'
        '</nav>'
    )


def _render_post_cards_html(post_slice, target_repo_root, default_thumb, yaml_loader, stage_rel_paths) -> str:
    """Render a slice of post paths into a .recent-posts-grid HTML block using 4 KB header reads."""
    import yaml
    cards = ['<div class="recent-posts-grid">']
    for post_path in post_slice:
        raw_head = post_path.read_text(encoding="utf-8", errors="ignore")[:4096]
        fm = {}
        if raw_head.startswith("---"):
            parts = raw_head.split("---", 2)
            if len(parts) >= 3:
                try:
                    fm = yaml.load(parts[1], Loader=yaml_loader) or {}
                except Exception:
                    fm = {}
        title = str(fm.get("title") or post_path.stem).strip()
        date_str = post_path.name[:10]
        slug = post_path.stem[11:]
        permalink = str(fm.get("permalink") or f"/futureproof/{slug}/").strip()
        summary = str(fm.get("meta_description") or fm.get("excerpt") or fm.get("description") or "").strip()
        if len(summary) > 160:
            summary = summary[:157].rsplit(" ", 1)[0] + "..."
        vod_url = str(fm.get("vod_url") or "").strip()
        card_cls = "recent-post-card has-vod" if vod_url else "recent-post-card"
        badge_html = '<span class="recent-post-badge badge-vod">🎬 Watch YouTube VOD</span>' if vod_url else ""
        img_field = fm.get("image")
        if isinstance(img_field, dict):
            raw_img = str(img_field.get("path") or "").strip()
            raw_alt = str(img_field.get("alt") or title)
        elif isinstance(img_field, str):
            raw_img = img_field.strip()
            raw_alt = title
        else:
            raw_img = default_thumb
            raw_alt = title
        thumb_url = _ensure_post_thumbnail(target_repo_root, raw_img, fallback_rel=default_thumb) if raw_img else ""
        for rel_candidate in (raw_img, thumb_url):
            clean_rel = (rel_candidate or "").strip().lstrip("/")
            if clean_rel and (target_repo_root / clean_rel).is_file():
                stage_rel_paths.append(clean_rel)
        esc_title = _escape_liquid_html(title)
        esc_alt = _escape_liquid_html(raw_alt)
        esc_summary = _escape_liquid_html(summary)
        img_html = (
            f'    <img class="recent-post-thumb" src="{thumb_url}" alt="{esc_alt}" width="{THUMB_WIDTH}" height="{THUMB_HEIGHT}" loading="lazy">\n'
            if thumb_url else ""
        )
        meta_html = (
            f'      <div class="recent-post-meta">\n'
            f'        <span class="recent-post-date">{date_str}</span>\n'
            f'        {badge_html}\n'
            f'      </div>\n'
            if badge_html
            else f'      <span class="recent-post-date">{date_str}</span>\n'
        )
        cards.append(
            f'  <a class="{card_cls}" href="{permalink}">\n'
            f'{img_html}'
            f'    <div class="recent-post-body">\n'
            f'{meta_html}'
            f'      <strong class="recent-post-title">{esc_title}</strong>\n'
            f'      <span class="recent-post-desc">{esc_summary}</span>\n'
            f'    </div>\n'
            f'  </a>'
        )
    cards.append("</div>")
    return "\n".join(cards)


def update_homepage_recent_posts(posts_dir, target_repo_root, count=10):
    """Build 480x252 PIL thumbnails, splice Page 1 into index.md, and build /page/2/..N static archive pages."""
    import yaml
    index_path = target_repo_root / "index.md"
    if not index_path.is_file() or not posts_dir.is_dir():
        return
    dated = [p for p in posts_dir.glob("*.md") if common._DATED_POST_RE.match(p.name)]
    if not dated:
        return
    yaml_loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    cfg_path = target_repo_root / "_config.yml"
    site_cfg = {}
    if cfg_path.is_file():
        try:
            site_cfg = yaml.load(cfg_path.read_text(encoding="utf-8", errors="ignore"), Loader=yaml_loader) or {}
        except Exception:
            site_cfg = {}
    try:
        count = max(1, int(site_cfg.get("recent_posts_limit") or count))
    except (ValueError, TypeError):
        count = 10
    default_thumb = str(site_cfg.get("default_post_thumb") or "").strip()
    ordered_posts = sorted(dated, key=common._post_sort_key, reverse=True)
    total_posts = len(ordered_posts)
    total_pages = max(1, (total_posts + count - 1) // count)
    stage_rel_paths = ["index.md"]
    page1_grid = _render_post_cards_html(ordered_posts[:count], target_repo_root, default_thumb, yaml_loader, stage_rel_paths)
    page1_nav = _render_pagination_nav(1, total_pages, total_posts, count)
    block = f"{RECENT_START_MARKER}\n{page1_grid}" + (f"\n{page1_nav}" if page1_nav else "") + f"\n{RECENT_END_MARKER}"
    idx_text = index_path.read_text(encoding="utf-8")
    if RECENT_START_MARKER in idx_text and RECENT_END_MARKER in idx_text:
        pattern = re.compile(
            re.escape(RECENT_START_MARKER) + r".*?" + re.escape(RECENT_END_MARKER),
            re.DOTALL,
        )
        new_idx = pattern.sub(lambda _: block, idx_text, count=1)
        if new_idx != idx_text:
            index_path.write_text(new_idx, encoding="utf-8")
        print(f"🖼️  Updated {min(count, total_posts)} recent post cards in {index_path}")
    pages_sub = target_repo_root / "pages" / "page"
    expected_page_files = set()
    written_pages = 0
    if total_pages > 1:
        pages_sub.mkdir(parents=True, exist_ok=True)
        for page_num in range(2, total_pages + 1):
            slice_start = (page_num - 1) * count
            slice_posts = ordered_posts[slice_start : slice_start + count]
            end_num = min(total_posts, slice_start + len(slice_posts))
            fname = f"page-{page_num}.md"
            expected_page_files.add(fname)
            p_file = pages_sub / fname
            nav_html = _render_pagination_nav(page_num, total_pages, total_posts, count)
            grid_html = _render_post_cards_html(slice_posts, target_repo_root, default_thumb, yaml_loader, stage_rel_paths)
            page_md = (
                "---\n"
                "layout: default\n"
                f'title: "Journal Archive — Page {page_num} of {total_pages}"\n'
                f'meta_description: "Chronological journal entries {slice_start + 1}–{end_num} of {total_posts} on {target_repo_root.name} (Page {page_num} of {total_pages})."\n'
                f"permalink: /page/{page_num}/\n"
                "---\n"
                f"# Journal Archive — Page {page_num} of {total_pages}\n\n"
                f"{nav_html}\n\n"
                f"{grid_html}\n\n"
                f"{nav_html}\n"
            )
            old_md = p_file.read_text(encoding="utf-8") if p_file.is_file() else None
            if old_md != page_md:
                p_file.write_text(page_md, encoding="utf-8")
                written_pages += 1
        stage_rel_paths.append("pages/page")
    if pages_sub.is_dir():
        for stale_p in sorted(pages_sub.glob("page-*.md")):
            if stale_p.name not in expected_page_files:
                stale_p.unlink()
    if total_pages > 1:
        print(f"📖 Paginated {total_posts:,} posts across {total_pages:,} pages (/page/2/..{total_pages}/, {written_pages} written).")
    if (target_repo_root / ".git").exists():
        import subprocess
        unique_stage = list(dict.fromkeys(stage_rel_paths))
        res = subprocess.run(
            ["git", "-C", str(target_repo_root), "add", "--", *unique_stage],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            print(f"📌 Surgically staged {len(unique_stage)} homepage/archive/image path(s) in {target_repo_root.name} git index.")


def clean_and_prep_dirs(hubs_dir):
    hubs_dir.mkdir(parents=True, exist_ok=True)


def generate_hub_file(node, target_repo_root, hubs_dir, parents=None):
    safe_id = node['id']
    is_root = node.get('id') == 'root' or node.get('permalink') == '/'
    
    if is_root:
        # ROOT NODE STRATEGY: "Hole Punching"
        # We generate an _include file, NOT the full page.
        # This allows index.md to be maintained manually.
        includes_dir = target_repo_root / "_includes"
        includes_dir.mkdir(exist_ok=True)
        filepath = includes_dir / "home_hub.md"
        print(f"🏠 Homepage Include: {filepath}")
        
        # Start with empty content (No Frontmatter, No Title)
        content = ""
        
    else:
        # STANDARD HUB STRATEGY: Full Page Generation
        filename = f"{safe_id}.md"
        filepath = hubs_dir / filename
    
        # Build Frontmatter & Title
        frontmatter = f"""---
layout: default
title: "{node['title']}"
permalink: {node['permalink']}
---
"""
        content = frontmatter + f"# {node['title']}\n\n"

    # --- COMMON BODY GENERATION ---
    # This logic applies to both Root (Partial) and Standard (Full)
    
    if node.get('blurb'):
        content += f"_{node['blurb']}_\n\n"

    # Conditional Header
    if node.get('children_hubs'):
        content += '<h2>Explore Topics</h2>\n'

    # Unconditional Nav Container (The Magic Carpet Dock)
    content += '<nav class="hub-nav">\n<ul>\n'
    
    if node.get('children_hubs'):
        for child in node['children_hubs']:
            content += f'  <li><a href="{child["permalink"]}">{child["title"]}</a></li>\n'
            
    content += '</ul>\n</nav>\n'
    
    if node.get('children_articles'):
        content += "\n## Top Articles\n"
        for article in node['children_articles']:
            content += f"* [{article['title']}]({article['permalink']})\n"
            if 'date' in article:
                content += f"  <small>{article['date']}</small>\n"

    if not node.get('children_hubs') and not node.get('children_articles'):
        content += "*No sub-topics found.*\n"

    # --- JSON-LD BREADCRUMBS ---
    # Only for non-root pages (Home usually handles its own schema)
    if not is_root and parents is not None:
        base_url = "https://mikelev.in"
        
        # Full Trail: Ancestors + Self
        trail = parents + [{'title': node['title'], 'permalink': node['permalink']}]
        
        list_items = []
        for i, item in enumerate(trail):
            list_items.append({
                "@type": "ListItem",
                "position": i + 1,
                "name": item['title'],
                "item": f"{base_url}{item['permalink']}"
            })

        json_ld = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": list_items
        }
       
        # --- VISIBLE STEALTH BREADCRUMBS ---
        # Render as spans with data attributes. No <a> tags.
        breadcrumbs_html = '<div class="stealth-breadcrumbs">'
        breadcrumbs_html += f'<span class="crumb" data-go="/">Home</span>'
        
        for item in parents:
            # Skip the root node if it's in the parents list to avoid redundancy
            if item['permalink'] == '/': continue
            breadcrumbs_html += f' &gt; <span class="crumb" data-go="{item["permalink"]}">{item["title"]}</span>'
            
        # The current page is usually just text, not a link
        breadcrumbs_html += f' &gt; <span class="current-crumb">{node["title"]}</span>'
        breadcrumbs_html += '</div>\n'

        # Inject at the top of the content (after the H1)
        # We need to insert this *after* the H1 which is added earlier in 'content'.
        # A simple string replacement or append strategy works.
        # Since we are building 'content' string, we can inject it now.
        
        # NOTE: We need to put this near the top. Let's prepend it to the body content logic.
        # Actually, let's insert it right after the title in the generated markdown.
        
        content = content.replace(f"# {node['title']}\n\n", f"# {node['title']}\n\n{breadcrumbs_html}\n")

        content += "\n\n<script type=\"application/ld+json\">\n"
        content += json.dumps(json_ld, indent=2)
        content += "\n</script>\n"

    # Write File only when content changed (preserves mtimes and zero-churn git diffs)
    old_content = filepath.read_text(encoding='utf-8') if filepath.is_file() else None
    changed = old_content != content
    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    return filepath, changed


def main():
    parser = argparse.ArgumentParser(description="Generate Hub Pages")
    common.add_target_argument(parser)
    args = parser.parse_args()

    posts_dir = common.get_target_path(args)
    target_repo_root = posts_dir.parent
    hubs_dir = target_repo_root / "pages"

    print(f"🚀 Generating Hubs for: {target_repo_root.name}")
    
    update_homepage_recent_posts(posts_dir, target_repo_root, count=10)
    targets = common.load_targets()
    target_cfg = targets.get(str(args.target), {})
    uses_kg = "build_knowledge_graph.py" in target_cfg.get("pipeline", [])
    navgraph_candidates = [target_repo_root / "navgraph.json"]
    if uses_kg:
        navgraph_candidates = [
            NAVGRAPH_FILE,
            Path(__file__).resolve().parent / "navgraph.json",
            target_repo_root / "navgraph.json",
        ]
    navgraph_path = next((p for p in navgraph_candidates if p.is_file()), None)
    if not navgraph_path:
        print(f"ℹ️  No navgraph.json for {target_repo_root.name}; recent posts updated.")
        return

    with open(navgraph_path, 'r', encoding='utf-8') as f:
        nav_tree = json.load(f)

    clean_and_prep_dirs(hubs_dir)
    expected_hub_files = set()
    stats = {"written": 0, "unchanged": 0}
    
    # NOTE: We no longer delete index.md here, because it is now a persistent source file.
   
    # Recursive Walker
    def recurse(node, parents=None):
        if parents is None: parents = []
        
        out_path, did_write = generate_hub_file(node, target_repo_root, hubs_dir, parents)
        if out_path.parent == hubs_dir:
            expected_hub_files.add(out_path.name)
            stats["written" if did_write else "unchanged"] += 1
        
        # Current node becomes parent for the next level
        # We capture just the data needed for breadcrumbs
        current_crumb = {'title': node['title'], 'permalink': node['permalink']}
        next_parents = parents + [current_crumb]
        
        for child in node.get('children_hubs', []):
            recurse(child, next_parents)

    recurse(nav_tree)
    pruned = 0
    for stale_md in sorted(hubs_dir.glob("*.md")):
        if stale_md.name not in expected_hub_files:
            stale_md.unlink()
            pruned += 1
    print(
        f"📊 Hub Sync: {stats['written']} written, {stats['unchanged']} unchanged, "
        f"{pruned} retired file(s) pruned."
    )


if __name__ == "__main__":
    main()
