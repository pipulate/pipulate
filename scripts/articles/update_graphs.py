import subprocess
import sys
import time
import argparse
from pathlib import Path
import common

# The pipeline sequence
SCRIPTS = [
    "contextualizer.py",
    "generate_semrush_candidates.py",
    "gsc_historical_fetch.py",
    "build_hierarchy.py",
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

    print(f"\n🔒 Locked Target: {targets[target_key]['name']}")
    
    # 2. Run the sequence
    total_start = time.time()
    
    for script in SCRIPTS:
        run_step(script, target_key)
        
    total_duration = time.time() - total_start
    print(f"\n✨ All steps completed successfully in {total_duration:.2f}s.")

if __name__ == "__main__":
    main()