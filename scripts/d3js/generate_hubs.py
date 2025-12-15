import json
import os
from pathlib import Path
import shutil

# --- CONFIGURATION ---
# Source Data (The Blueprint)
NAVGRAPH_FILE = Path("navgraph.json")

# Target Sandbox (The Construction Site)
# We use _hubs to keep it organized, but Jekyll will treat them as pages
TARGET_REPO = Path("/home/mike/repos/trimnoir")
HUBS_DIR = TARGET_REPO / "_hubs"

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
    # 1. Determine Filename (Flat structure on disk)
    # e.g., hub_python.md or hub_root.md
    safe_id = node['id']
    filename = f"{safe_id}.md"
    filepath = HUBS_DIR / filename
    
    # 2. Build Frontmatter
    # We use the permalink from the JSON to define the URL structure
    frontmatter = f"""---
layout: page
title: "{node['title']}"
permalink: {node['permalink']}
---
"""

    # 3. Build Body Content (The Drill-Down)
    # Phase 1: Only links to Sub-Hubs
    body = f"# {node['title']}\n\n"
    
    if node.get('children_hubs'):
        body += "## Explore Topics\n"
        for child in node['children_hubs']:
            # Create a simple markdown link: [Title](Permalink)
            body += f"* [{child['title']}]({child['permalink']})\n"
    else:
        body += "*No sub-topics found.*\n"

    # (Placeholder for Articles - Phase 2)
    # body += "\n## Articles\n..."

    # 4. Write File
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(frontmatter + body)
        
    print(f"✅ Created: {filename} -> {node['permalink']}")

    # 5. Recurse (Depth-First Creation)
    for child in node.get('children_hubs', []):
        generate_hub_file(child)

def main():
    print("🚀 Starting Hub Generation...")
    
    if not NAVGRAPH_FILE.exists():
        print(f"❌ Error: {NAVGRAPH_FILE} not found. Run build_navgraph.py first.")
        return

    # Load the blueprint
    with open(NAVGRAPH_FILE, 'r', encoding='utf-8') as f:
        nav_tree = json.load(f)

    # Prepare the site
    clean_and_prep_dirs()

    # Start the recursive build from the root
    # Note: 'nav_tree' is the root node itself in our JSON structure
    generate_hub_file(nav_tree)

    print(f"\n🎉 Generation Complete.")
    print(f"📂 Check {HUBS_DIR} for your new hub pages.")
    print("👉 Next Step: Run 'jes' (or 'jekyll serve') in the trimnoir repo.")

if __name__ == "__main__":
    main()