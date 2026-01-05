import subprocess
import sys
import time
import shutil
import argparse
from pathlib import Path
import common

# The pipeline sequence
SCRIPTS = [
    "contextualizer.py",
    "generate_semrush_candidates.py",
    "gsc_historical_fetch.py",
    "build_hierarchy.py",  # Generates graph.json locally
    "build_navgraph.py",
    "generate_hubs.py"
]

def run_step(script_name, target_key):
    print(f"\n--- 🚀 Step: {script_name} ---")
    start = time.time()
    
    # We pass the target key to every script
    cmd = [sys.executable, script_name, "--target", target_key]
    
    try:
        # check=True ensures we stop if a step fails
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        print(f"❌ Critical Failure in {script_name}. Stopping pipeline.")
        sys.exit(1)
        
    duration = time.time() - start
    print(f"✅ {script_name} complete ({duration:.2f}s).")

def sync_data_to_jekyll(target_path):
    """
    Copies the generated graph.json to the Jekyll SITE ROOT.
    This allows both humans and LLMs to fetch it at /graph.json
    """
    print("\n--- 📦 Syncing Data to Jekyll ---")
    
    # Source is local to this script
    script_dir = Path(__file__).parent
    graph_source = script_dir / "graph.json"
    
    # target_path is usually .../trimnoir/_posts
    # We want the site root: .../trimnoir/
    repo_root = target_path.parent
    
    # Destination 1: The Site Root (For fetch /graph.json)
    graph_dest_root = repo_root / "graph.json"
    
    if graph_source.exists():
        shutil.copy2(graph_source, graph_dest_root)
        print(f"✅ Copied graph.json to SITE ROOT: {graph_dest_root}")
        
        # Optional: We stopped copying show_graph.html because it is now an 
        # _include managed in the theme, but if you wanted to sync a 
        # standalone viewer, you could do it here. 
        # For now, we trust the repo's internal _includes/show_graph.html
        
    else:
        print(f"⚠️ Warning: {graph_source} not found. Skipping sync.")

def main():
    parser = argparse.ArgumentParser(description="Update all Pipulate graphs")
    common.add_target_argument(parser)
    args = parser.parse_args()
    
    # 1. Resolve the Target Key ONCE
    targets = common.load_targets()
    target_key = args.target

    if not target_key:
        print("🤖 Initiating Pipulate Graph Update Sequence...")
        print("Select Target Repo for ALL steps:")
        for k, v in targets.items():
            print(f"  [{k}] {v['name']} ({v['path']})")
        
        target_key = input("Enter choice (default 1): ").strip() or "1"
    
    if target_key not in targets:
        print(f"❌ Invalid target key: {target_key}")
        sys.exit(1)

    # Resolve actual path for file operations
    target_path = Path(targets[target_key]['path']).expanduser().resolve()
    print(f"\n🔒 Locked Target: {targets[target_key]['name']}")
    
    # 2. Run the sequence
    total_start = time.time()
    
    for script in SCRIPTS:
        run_step(script, target_key)
    
    # 3. Sync Data
    sync_data_to_jekyll(target_path)
        
    total_duration = time.time() - total_start
    print(f"\n✨ All steps completed successfully in {total_duration:.2f}s.")

if __name__ == "__main__":
    main()