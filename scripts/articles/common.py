import json
import os
import re
import argparse
import getpass
from datetime import datetime
from pathlib import Path
import sys

# Standard Config Location
CONFIG_DIR = Path.home() / ".config" / "pipulate"
TARGETS_FILE = CONFIG_DIR / "blogs.json"
KEYS_FILE = CONFIG_DIR / "keys.json"
LAST_PUBLISHED_FILE = CONFIG_DIR / "last_published.json"

DEFAULT_TARGETS = {
    "1": {
        "name": "Trimnoir (Personal Journal)",
        "path": str(Path.home() / "repos" / "trimnoir" / "_posts"),
        "base_url": "https://mikelev.in",
        "permalink_prefix": "futureproof"
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


def record_last_published(target_key, file_path, target_name=None):
    """Record the article articleizer.py just wrote, keyed by target.

    confluenceizer.py --latest reads this to sync ONLY the freshly published
    file instead of sweeping the whole directory. Keying by target means a
    public-side publish (target 1) never shadows a private-side one (target 4).
    """
    target_key = str(target_key)
    data = {}
    if LAST_PUBLISHED_FILE.exists():
        try:
            with open(LAST_PUBLISHED_FILE, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    data[target_key] = {
        "path": str(Path(file_path).resolve()),
        "name": target_name,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LAST_PUBLISHED_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_last_published(target_key):
    """Return the recorded path for a target, or None if absent/stale/invalid."""
    target_key = str(target_key)
    if not LAST_PUBLISHED_FILE.exists():
        return None
    try:
        with open(LAST_PUBLISHED_FILE, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    entry = data.get(target_key) if isinstance(data, dict) else None
    if not entry:
        return None
    path = entry.get("path") if isinstance(entry, dict) else entry
    if path and Path(path).is_file():
        return path
    return None


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

def add_target_argument(parser):
    """Legacy helper - redirects to add_standard_arguments for backwards compatibility."""
    add_standard_arguments(parser)


def get_target_path(cli_args=None):
    """
    Determines the active project path.
    Priority:
    1. CLI Argument (--target)
    2. Default (Target "1")
    3. Interactive Selection (Fallback)
    """
    targets = load_targets()
    
    # If args provided and key exists, use it
    if cli_args and getattr(cli_args, 'target', None):
        key = str(cli_args.target)
        if key in targets:
            # Polish: Tell the user if it was explicit or defaulted
            if '-t' in sys.argv or '--target' in sys.argv:
                print(f"🎯 Target set via CLI: {targets[key]['name']}")
            else:
                print(f"🎯 Default target auto-selected: {targets[key]['name']}")
            return Path(targets[key]['path']).expanduser()
        else:
            print(f"❌ Invalid target key: {key}")
            sys.exit(1)

    # Interactive Mode (Fallback if cli_args is completely missing)
    print("\nSelect Target Repo:")
    for k, v in targets.items():
        print(f"  [{k}] {v['name']} ({v['path']})")
    
    choice = input("Enter choice (default 1): ").strip() or "1"
    
    if choice in targets:
        path = Path(targets[choice]['path']).expanduser()
        print(f"✅ Active Target: {targets[choice]['name']}")
        return path
    else:
        print("❌ Invalid selection.")
        sys.exit(1)

def add_standard_arguments(parser):
    """Unified API for all scripts."""
    # CRITICAL FIX: Inject default="1" here
    parser.add_argument('-t', '--target', type=str, default="1", help="Target ID from blogs.json (default: '1')")
    parser.add_argument('-k', '--key', type=str, help="API key alias from keys.json (e.g., 'pipulate')")


# ----------------------------------------------------------------------------
# Frontmatter stamping — the 1-to-1 ledger (Jekyll post <-> Google Doc)
# ----------------------------------------------------------------------------
GDOC_URL_KEY = "gdoc_url"


def gdoc_share_url(file_id):
    """Canonical anyone-with-link share URL for a Google Doc file id."""
    return f"https://docs.google.com/document/d/{file_id}/edit?usp=sharing"


def gdoc_id_from_frontmatter(metadata):
    """Extract the Doc file id from a post's gdoc_url, or None if unstamped."""
    url = str((metadata or {}).get(GDOC_URL_KEY) or "").strip()
    match = re.search(r"/document/d/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else None


def stamp_frontmatter_value(md_path, key, value, preserve_mtime=True):
    """Surgically upsert one single-line `key: value` in a post's YAML block.

    Deliberately NOT a parse->mutate->dump round-trip: pushing 1,200+ posts
    through a YAML dumper would churn quoting, folding, and key order across
    the whole corpus. This touches exactly one line inside the leading
    `--- ... ---` block, leaves every other byte alone, and (by default)
    restores the file's mtime so a bookkeeping stamp never masquerades as a
    content edit to mtime-based freshness logic.

    Returns one of: "ADDED", "UPDATED", "UNCHANGED", "NO_FRONTMATTER".
    """
    path = Path(md_path)
    original = path.read_text(encoding="utf-8")
    lines = original.split("\n")
    if not lines or lines[0].strip() != "---":
        return "NO_FRONTMATTER"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return "NO_FRONTMATTER"

    new_line = f"{key}: {value}"
    key_re = re.compile(rf"^{re.escape(key)}\s*:")
    for i in range(1, end):
        if key_re.match(lines[i]):
            if lines[i] == new_line:
                return "UNCHANGED"
            lines[i] = new_line
            _write_text_preserving_mtime(path, "\n".join(lines), preserve_mtime)
            return "UPDATED"

    lines.insert(end, new_line)
    _write_text_preserving_mtime(path, "\n".join(lines), preserve_mtime)
    return "ADDED"


def _write_text_preserving_mtime(path, text, preserve_mtime):
    st = path.stat() if preserve_mtime else None
    path.write_text(text, encoding="utf-8")
    if st is not None:
        os.utime(path, (st.st_atime, st.st_mtime))
