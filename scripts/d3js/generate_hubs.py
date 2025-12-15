import json
import os
from pathlib import Path
import shutil

# --- CONFIGURATION ---
NAVGRAPH_FILE = Path("navgraph.json")
TARGET_REPO = Path("/home/mike/repos/trimnoir")

# 1. Change _hubs to pages so Jekyll sees them automatically
HUBS_DIR = TARGET_REPO / "pages" 

def clean_and_prep_dirs():
    """Ensures the target directory exists and is empty."""
    if HUBS_DIR.exists():
        shutil.rmtree(HUBS_DIR)
    HUBS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"🧹 Cleaned and prepped: {HUBS_DIR}")

def generate_hub_file(node):
    """
    Creates a markdown file for a single hub node.
    Recurses to create children.
    """
    safe_id = node['id']
    
    # --- SPECIAL HANDLING FOR ROOT ---
    # If this is the root node, we overwrite the main index.md
    if node.get('id') == 'root' or node.get('permalink') == '/':
        filename = "index.md"
        filepath = TARGET_REPO / filename
        print(f"🏠 Overwriting Homepage: {filepath}")
    else:
        # Standard Hubs go into /pages/
        filename = f"{safe_id}.md"
        filepath = HUBS_DIR / filename
    
    # 2. Build Frontmatter
    frontmatter = f"""---
layout: page
title: "{node['title']}"
permalink: {node['permalink']}
---
"""

    # 3. Build Body (The Drill-Down)
    body = f"# {node['title']}\n\n"
    
    # Add Description/Blurb if available (from your articles)
    if node.get('blurb'):
        body += f"_{node['blurb']}_\n\n"
    
    # Render Sub-Hubs
    if node.get('children_hubs'):
        body += "## Explore Topics\n"
        for child in node['children_hubs']:
            body += f"* [{child['title']}]({child['permalink']})\n"
    
    # Render Articles (The "Gold Pan" items)
    if node.get('children_articles'):
        body += "\n## Top Articles\n"
        for article in node['children_articles']:
            # Use the article's own permalink
            body += f"* [{article['title']}]({article['permalink']})\n"
            if 'date' in article:
                body += f"  <small>{article['date']}</small>\n"

    if not node.get('children_hubs') and not node.get('children_articles'):
        body += "*No sub-topics found.*\n"

    # 4. Write File
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(frontmatter + body)
        
    # 5. Recurse
    for child in node.get('children_hubs', []):
        generate_hub_file(child)

def main():
    print("🚀 Starting Hub Generation v2...")
    
    if not NAVGRAPH_FILE.exists():
        print(f"❌ Error: {NAVGRAPH_FILE} not found.")
        return

    with open(NAVGRAPH_FILE, 'r', encoding='utf-8') as f:
        nav_tree = json.load(f)

    # Clean the pages directory
    clean_and_prep_dirs()
    
    # Nuke the old default index if it exists (Jekyll defaults to index.markdown sometimes)
    old_index = TARGET_REPO / "index.markdown"
    if old_index.exists():
        os.remove(old_index)
        print("🗑️  Removed default index.markdown")

    generate_hub_file(nav_tree)

    print(f"\n🎉 Generation Complete.")
    print(f"📂 Hubs are in {HUBS_DIR}")
    print(f"🏠 Homepage is at {TARGET_REPO}/index.md")

if __name__ == "__main__":
    main()