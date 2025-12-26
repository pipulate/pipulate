import json
import argparse
from pathlib import Path
import sys

# Standard Config Location
CONFIG_DIR = Path.home() / ".config" / "articleizer"
TARGETS_FILE = CONFIG_DIR / "targets.json"

DEFAULT_TARGETS = {
    "1": {
        "name": "Trim Noir (Default)",
        "path": "/home/mike/repos/trimnoir/_posts"
    }
}

def load_targets():
    """Loads targets from JSON or returns defaults."""
    if TARGETS_FILE.exists():
        try:
            with open(TARGETS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Warning: {TARGETS_FILE} is corrupt. Using defaults.")
    return DEFAULT_TARGETS

def get_target_path(cli_args=None):
    """
    Determines the active project path.
    Priority:
    1. CLI Argument (--target_key)
    2. Interactive Selection (if running in terminal)
    3. Default (Target "1")
    """
    targets = load_targets()
    
    # If args provided and key exists, use it
    if cli_args and getattr(cli_args, 'target', None):
        key = str(cli_args.target)
        if key in targets:
            print(f"🎯 Target set via CLI: {targets[key]['name']}")
            return Path(targets[key]['path'])
        else:
            print(f"❌ Invalid target key: {key}")
            sys.exit(1)

    # Interactive Mode
    print("\nSelect Target Repo:")
    for k, v in targets.items():
        print(f"  [{k}] {v['name']} ({v['path']})")
    
    choice = input("Enter choice (default 1): ").strip() or "1"
    
    if choice in targets:
        path = Path(targets[choice]['path'])
        print(f"✅ Active Target: {targets[choice]['name']}")
        return path
    else:
        print("❌ Invalid selection.")
        sys.exit(1)

def add_target_argument(parser):
    """Helper to add standard --target argument to argparse."""
    parser.add_argument('--target', type=str, help="Key of the target repo from targets.json (e.g., '1')")