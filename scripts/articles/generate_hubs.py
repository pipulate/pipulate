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

def generate_hub_file(node, target_repo_root, hubs_dir):
    safe_id = node['id']
    
    # Root Node -> Homepage
    if node.get('id') == 'root' or node.get('permalink') == '/':
        filename = "index.md"
        filepath = target_repo_root / filename
        print(f"🏠 Homepage: {filepath}")
    else:
        # Hub Page
        filename = f"{safe_id}.md"
        filepath = hubs_dir / filename
    
    # 2. Build Frontmatter
    frontmatter = f"""---
layout: page
title: "{node['title']}"
permalink: {node['permalink']}
---
"""

    # 3. Build Body
    body = f"# {node['title']}\n\n"
    if node.get('blurb'):
        body += f"_{node['blurb']}_\n\n"
    
    if node.get('children_hubs'):
        body += "## Explore Topics\n"
        for child in node['children_hubs']:
            body += f"* [{child['title']}]({child['permalink']})\n"
    
    if node.get('children_articles'):
        body += "\n## Top Articles\n"
        for article in node['children_articles']:
            body += f"* [{article['title']}]({article['permalink']})\n"
            if 'date' in article:
                body += f"  <small>{article['date']}</small>\n"

    if not node.get('children_hubs') and not node.get('children_articles'):
        body += "*No sub-topics found.*\n"

    # 4. Write File
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(frontmatter + body)
        
    # NOTE: No recursion here! It is handled in main().


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
    
    old_index = target_repo_root / "index.markdown"
    if old_index.exists():
        os.remove(old_index)

    # Recursive Walker
    def recurse(node):
        generate_hub_file(node, target_repo_root, hubs_dir)
        for child in node.get('children_hubs', []):
            recurse(child)

    recurse(nav_tree)

    print(f"\n🎉 Done. Hubs in {hubs_dir}")

if __name__ == "__main__":
    main()
