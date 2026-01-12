import json
import os
from pathlib import Path
import shutil
import argparse
import common


NAVGRAPH_FILE = Path("navgraph.json")

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
    
    if not NAVGRAPH_FILE.exists():
        print(f"❌ Error: {NAVGRAPH_FILE} not found.")
        return

    with open(NAVGRAPH_FILE, 'r', encoding='utf-8') as f:
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
