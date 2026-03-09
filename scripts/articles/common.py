import json
import argparse
import getpass
from pathlib import Path
import sys

# Standard Config Location
CONFIG_DIR = Path.home() / ".config" / "articleizer"
TARGETS_FILE = CONFIG_DIR / "targets.json"
KEYS_FILE = CONFIG_DIR / "keys.json"

DEFAULT_TARGETS = {
    "1": {
        "name": "Trim Noir (Default)",
        "path": "/home/mike/repos/trimnoir/_posts",
        "base_url": "https://mikelev.in",
        "permalink_style": "/futureproof/:slug/"
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

def load_keys_dict():
    """Loads the entire keys dictionary from keys.json."""
    if KEYS_FILE.exists():
        try:
            with open(KEYS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"❌ Error: {KEYS_FILE} is corrupt.")
            sys.exit(1)
    return {}

def get_api_key(key_name=None):
    """Gets a specific named API key, falling back to 'default' or prompt."""
    key_name = key_name or "default"
    keys_dict = load_keys_dict()

    if key_name in keys_dict:
        return keys_dict[key_name]

    # Interactive fallback
    print(f"⚠️ API Key '{key_name}' not found in {KEYS_FILE}.")
    new_key = getpass.getpass(f"Enter Google API Key for '{key_name}': ").strip()

    if new_key:
        save = input(f"Save key '{key_name}' to config? (y/n): ").lower()
        if save == 'y':
            keys_dict[key_name] = new_key
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(KEYS_FILE, 'w') as f:
                json.dump(keys_dict, f, indent=2)
            KEYS_FILE.chmod(0o600)
            print(f"✅ Key '{key_name}' saved.")
        return new_key
    else:
        print("❌ No key provided. Exiting.")
        sys.exit(1)

def add_standard_arguments(parser):
    """Unified API for all scripts."""
    parser.add_argument('-t', '--target', type=str, help="Target ID from targets.json (e.g., '1')")
    parser.add_argument('-k', '--key', type=str, help="API key alias from keys.json (e.g., 'pipulate')")

def add_target_argument(parser):
    """Legacy helper - redirects to add_standard_arguments for backwards compatibility."""
    parser.add_argument('--target', type=str, help="Key of the target repo from targets.json (e.g., '1')")