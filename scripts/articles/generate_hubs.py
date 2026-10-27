import json
import os
import re
from pathlib import Path
import shutil
import argparse
import common


NAVGRAPH_FILE = Path("navgraph.json")

THUMB_WIDTH = 480
THUMB_HEIGHT = 252
RECENT_START_MARKER = "<!-- START_RECENT_POSTS -->"
RECENT_END_MARKER = "<!-- END_RECENT_POSTS -->"


def _ensure_post_thumbnail(target_repo_root, raw_img_path, fallback_rel="/assets/images/AI_Readiness_Consultant_RFC_9111.png"):
    """Create or reuse a 480x252 (1.91:1) PIL thumbnail under /assets/images/thumbs/."""
    from PIL import Image
    rel_src = (raw_img_path or fallback_rel).strip()
    if not rel_src.startswith("/"):
        rel_src = "/" + rel_src
    src_file = target_repo_root / rel_src.lstrip("/")
    if not src_file.is_file():
        rel_src = fallback_rel
        src_file = target_repo_root / rel_src.lstrip("/")
    if not src_file.is_file():
        return rel_src
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


def update_homepage_recent_posts(posts_dir, target_repo_root, count=10):
    """Build 480x252 PIL thumbnails and splice the 10 newest posts into index.md."""
    import html
    import yaml
    index_path = target_repo_root / "index.md"
    if not index_path.is_file() or not posts_dir.is_dir():
        return
    dated = [p for p in posts_dir.glob("*.md") if common._DATED_POST_RE.match(p.name)]
    if not dated:
        return
    cfg_path = target_repo_root / "_config.yml"
    site_cfg = {}
    if cfg_path.is_file():
        try:
            site_cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8", errors="ignore")) or {}
        except Exception:
            site_cfg = {}
    try:
        count = int(site_cfg.get("recent_posts_limit") or count)
    except (ValueError, TypeError):
        pass
    default_thumb = str(site_cfg.get("default_post_thumb") or "").strip()
    dated.sort(key=common._post_sort_key)
    recent = dated[-count:][::-1]
    cards = ['<div class="recent-posts-grid">']
    stage_rel_paths = ["index.md"]
    for post_path in recent:
        raw = post_path.read_text(encoding="utf-8", errors="ignore")
        fm = {}
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                try:
                    fm = yaml.safe_load(parts[1]) or {}
                except Exception:
                    fm = {}
        title = str(fm.get("title") or post_path.stem).strip()
        date_str = post_path.name[:10]
        slug = post_path.stem[11:]
        permalink = str(fm.get("permalink") or f"/futureproof/{slug}/").strip()
        summary = str(fm.get("meta_description") or fm.get("excerpt") or fm.get("description") or "").strip()
        if len(summary) > 160:
            summary = summary[:157].rsplit(" ", 1)[0] + "..."
        img_field = fm.get("image")
        if isinstance(img_field, dict):
            raw_img = str(img_field.get("path") or "")
            raw_alt = str(img_field.get("alt") or title)
        elif isinstance(img_field, str):
            raw_img = img_field
            raw_alt = title
        else:
            raw_img = "/assets/images/AI_Readiness_Consultant_RFC_9111.png"
            raw_alt = title
        thumb_url = _ensure_post_thumbnail(target_repo_root, raw_img)
        for rel_candidate in (raw_img, thumb_url):
            clean_rel = (rel_candidate or "").strip().lstrip("/")
            if clean_rel and (target_repo_root / clean_rel).is_file():
                stage_rel_paths.append(clean_rel)
        esc_title = html.escape(title, quote=True)
        esc_alt = html.escape(raw_alt, quote=True)
        esc_summary = html.escape(summary, quote=True)
        cards.append(
            f'  <a class="recent-post-card" href="{permalink}">\n'
            f'    <img class="recent-post-thumb" src="{thumb_url}" alt="{esc_alt}" width="{THUMB_WIDTH}" height="{THUMB_HEIGHT}" loading="lazy">\n'
            f'    <div class="recent-post-body">\n'
            f'      <span class="recent-post-date">{date_str}</span>\n'
            f'      <strong class="recent-post-title">{esc_title}</strong>\n'
            f'      <span class="recent-post-desc">{esc_summary}</span>\n'
            f'    </div>\n'
            f'  </a>'
        )
    cards.append("</div>")
    block = f"{RECENT_START_MARKER}\n" + "\n".join(cards) + f"\n{RECENT_END_MARKER}"
    idx_text = index_path.read_text(encoding="utf-8")
    if RECENT_START_MARKER in idx_text and RECENT_END_MARKER in idx_text:
        pattern = re.compile(
            re.escape(RECENT_START_MARKER) + r".*?" + re.escape(RECENT_END_MARKER),
            re.DOTALL,
        )
        new_idx = pattern.sub(lambda _: block, idx_text, count=1)
        if new_idx != idx_text:
            index_path.write_text(new_idx, encoding="utf-8")
        print(f"🖼️  Updated {len(recent)} recent post thumbnails in {index_path}")
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
                print(f"📌 Surgically staged {len(unique_stage)} homepage/image asset(s) in {target_repo_root.name} git index.")


def clean_and_prep_dirs(hubs_dir):
    if hubs_dir.exists():
        shutil.rmtree(hubs_dir)
    hubs_dir.mkdir(parents=True, exist_ok=True)
    print(f"🧹 Cleaned: {hubs_dir}")


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

    # Write File
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def main():
    parser = argparse.ArgumentParser(description="Generate Hub Pages")
    common.add_target_argument(parser)
    args = parser.parse_args()

    posts_dir = common.get_target_path(args)
    target_repo_root = posts_dir.parent
    hubs_dir = target_repo_root / "pages"

    print(f"🚀 Generating Hubs for: {target_repo_root.name}")
    
    update_homepage_recent_posts(posts_dir, target_repo_root, count=10)
    navgraph_candidates = [
        NAVGRAPH_FILE,
        Path(__file__).resolve().parent / "navgraph.json",
        target_repo_root / "navgraph.json",
    ]
    navgraph_path = next((p for p in navgraph_candidates if p.is_file()), None)
    if not navgraph_path:
        print(f"ℹ️  {NAVGRAPH_FILE} not in working dir; recent posts updated (run `preview` for full hub rebuild).")
        return

    with open(navgraph_path, 'r', encoding='utf-8') as f:
        nav_tree = json.load(f)

    clean_and_prep_dirs(hubs_dir)
    
    # NOTE: We no longer delete index.md here, because it is now a persistent source file.
   
    # Recursive Walker
    def recurse(node, parents=None):
        if parents is None: parents = []
        
        generate_hub_file(node, target_repo_root, hubs_dir, parents)
        
        # Current node becomes parent for the next level
        # We capture just the data needed for breadcrumbs
        current_crumb = {'title': node['title'], 'permalink': node['permalink']}
        next_parents = parents + [current_crumb]
        
        for child in node.get('children_hubs', []):
            recurse(child, next_parents)

    recurse(nav_tree)


if __name__ == "__main__":
    main()
