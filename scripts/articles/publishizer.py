import subprocess
import sys
import time
import shutil
import argparse
from pathlib import Path
import common


def run_step(script_name, target_key, extra_args=None):
    print(f"\n--- 🚀 Step: {script_name} ---")
    start = time.time()
    
    # We pass the target key to every script
    cmd = [sys.executable, script_name, "--target", target_key]

    # Only feed API keys to the scripts that know how to eat them
    if script_name == "contextualizer.py" and extra_args:
        cmd.extend(extra_args)

    
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
    Copies the generated artifacts to the Jekyll SITE ROOT.
    """
    print("\n--- 📦 Syncing Data to Jekyll ---")
    
    # Source is local to this script
    script_dir = Path(__file__).parent
    
    # Artifacts to sync
    artifacts = {
        "graph.json": "graph.json",
        "llms.txt": "llms.txt",
    }
    
    # target_path is usually .../trimnoir/_posts
    # We want the site root: .../trimnoir/
    repo_root = target_path.parent
    
    # Sync static artifacts
    for filename, dest_name in artifacts.items():
        source = script_dir / filename
        dest = repo_root / dest_name
        
        if source.exists():
            shutil.copy2(source, dest)
            print(f"✅ Synced {filename} -> {dest}")
        else:
            print(f"⚠️ Warning: {filename} not found. Skipping sync.")

    # Sync dynamic sitemaps (sitemap.xml, sitemap-core.xml, sitemap-branch-0.xml, etc.)
    for sitemap in script_dir.glob("sitemap*.xml"):
        dest = repo_root / sitemap.name
        shutil.copy2(sitemap, dest)
        print(f"✅ Synced {sitemap.name} -> {dest}")

def main():
    parser = argparse.ArgumentParser(description="Update all Pipulate graphs")
    common.add_target_argument(parser)
    
    # --- NEW: Catch API key arguments to pass down ---
    parser.add_argument('-k', '--key', type=str, help="Pass a specific API key alias to the contextualizer")
    parser.add_argument('-m', '--keys', type=str, help="Pass a comma-separated list of keys for rotation")

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
    
    # THE BJJ SWEEP: Dynamically pull the pipeline array from the JSON config
    pipeline_scripts = targets[target_key].get('pipeline', [])
    
    print(f"\n🔒 Locked Target: {targets[target_key]['name']}")
    print(f"🛤️  Active Pipeline: {len(pipeline_scripts)} steps")

    # Pack the extra arguments
    extra_args = []
    if args.key:
        extra_args.extend(['-k', args.key])
    if args.keys:
        extra_args.extend(['-m', args.keys])
    
    # 2. Run the sequence
    total_start = time.time()
    
    for script in pipeline_scripts:
        run_step(script, target_key, extra_args)
    
    # 3. Sync Data
    sync_data_to_jekyll(target_path)
        
    total_duration = time.time() - total_start
    print(f"\n✨ All steps completed successfully in {total_duration:.2f}s.")

if __name__ == "__main__":
    main()
