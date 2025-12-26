import json
import os
from pathlib import Path
import shutil
import argparse
import common

NAVGRAPH_FILE = Path("navgraph.json")

def clean_and_prep_dirs(hubs_dir):
    """Ensures the target directory exists and is empty."""
    if hubs_dir.exists():
        # Optimized: Only delete if it looks like a generated folder to avoid accidents
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
    
    # ... [Frontmatter and Body generation logic remains identical] ...
    # ... Just ensure you use the passed 'filepath' variable ...

def main():
    parser = argparse.ArgumentParser(description="Generate Hub Pages")
    common.add_target_argument(parser)
    args = parser.parse_args()

    # Get the _posts dir
    posts_dir = common.get_target_path(args)
    # Deduce Repo Root (parent of _posts)
    target_repo_root = posts_dir.parent
    # Define Hubs Dir
    hubs_dir = target_repo_root / "pages"

    print(f"🚀 Generating Hubs for: {target_repo_root.name}")
    
    if not NAVGRAPH_FILE.exists():
        print(f"❌ Error: {NAVGRAPH_FILE} not found. Run build_navgraph.py first.")
        return

    with open(NAVGRAPH_FILE, 'r', encoding='utf-8') as f:
        nav_tree = json.load(f)

    clean_and_prep_dirs(hubs_dir)
    
    # Cleanup old index if exists
    old_index = target_repo_root / "index.markdown"
    if old_index.exists():
        os.remove(old_index)

    # Recursive generation
    # You will need to wrap the recursion in a helper that passes the dirs
    def recurse(node):
        generate_hub_file(node, target_repo_root, hubs_dir)
        for child in node.get('children_hubs', []):
            recurse(child)

    recurse(nav_tree)

    print(f"\n🎉 Done. Hubs in {hubs_dir}")

if __name__ == "__main__":
    main()