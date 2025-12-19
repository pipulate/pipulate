# scripts/articles/update_graphs.py
import os
import sys
import subprocess
import time
from pathlib import Path

# --- CONFIGURATION ---
# We assume sibling scripts are in the same directory as this orchestrator
BASE_DIR = Path(__file__).parent.resolve()

# The Sequence of Operations (Order Matters!)
PIPELINE = [
    {
        "name": "Contextualizer",
        "file": "contextualizer.py",
        "desc": "Extracting keywords and metadata from new articles..."
    },
    {
        "name": "SEMRush Candidates",
        "file": "generate_semrush_candidates.py",
        "desc": "Updating keyword candidate list for market analysis..."
    },
    {
        "name": "GSC Historical Fetch",
        "file": "gsc_historical_fetch.py",
        "desc": "Fetching latest performance velocity from Google Search Console..."
    },
    {
        "name": "Hierarchy Builder",
        "file": "build_hierarchy.py",
        "desc": "Clustering content and generating D3 Link Graph..."
    },
    {
        "name": "NavGraph Builder",
        "file": "build_navgraph.py",
        "desc": "Constructing the recursive navigation tree (NavGraph)..."
    },
    {
        "name": "Hub Generator",
        "file": "generate_hubs.py",
        "desc": "Generating static Jekyll Hub pages from NavGraph..."
    }
]

def run_step(step_info):
    """Runs a single python script as a subprocess."""
    script_path = BASE_DIR / step_info["file"]
    
    if not script_path.exists():
        print(f"❌ ERROR: Could not find {script_path}")
        return False

    print(f"\n--- 🚀 Step: {step_info['name']} ---")
    print(f"ℹ️  {step_info['desc']}")
    
    try:
        # We use sys.executable to ensure we use the same Python interpreter (and venv)
        # that is running this orchestrator.
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, str(script_path)], 
            check=True,
            text=True
        )
        duration = time.time() - start_time
        print(f"✅ {step_info['name']} complete ({duration:.2f}s).")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n💥 ERROR in {step_info['name']}!")
        print(f"   Exit Code: {e.returncode}")
        return False
    except Exception as e:
        print(f"\n💥 UNEXPECTED ERROR: {e}")
        return False

def main():
    print(f"🤖 Initiating Pipulate Graph Update Sequence...")
    print(f"📂 Working Directory: {BASE_DIR}")
    
    total_start = time.time()
    success_count = 0
    
    for step in PIPELINE:
        if run_step(step):
            success_count += 1
        else:
            print("\n🛑 Pipeline halted due to error.")
            sys.exit(1)

    total_duration = time.time() - total_start
    print(f"\n✨ All {success_count} steps completed successfully in {total_duration:.2f}s.")
    print("👉 Your Link Graph and Hub Pages are now synchronized with Reality.")

if __name__ == "__main__":
    main()
