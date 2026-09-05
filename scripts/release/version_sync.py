#!/usr/bin/env python3
"""
Version Synchronization Script for Pipulate

This script ensures all version numbers and descriptions across the codebase come from a single
source of truth: pipulate.__version__ and pipulate.__description__ in __init__.py

Files updated:
- pyproject.toml (version, description, license)

Usage:
    python -c "from pipulate.version_sync import sync_all_versions; sync_all_versions()"
    
Or run directly:
    python pipulate/version_sync.py
"""

import os
import re
import sys
from pathlib import Path

def get_version_and_description():
    """Get the version and description from __init__.py at project root"""
    # Script is at: pipulate/helpers/release/version_sync.py
    # __init__.py is at: pipulate/__init__.py
    # So we need to go up 2 levels from script location
    script_dir = Path(__file__).parent  # pipulate/helpers/release/
    project_root = script_dir.parent.parent  # pipulate/
    init_file = project_root / "__init__.py"
    
    if not init_file.exists():
        raise RuntimeError(f"Could not find __init__.py at {init_file}")
    
    content = init_file.read_text()
    
    # Get version
    version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not version_match:
        raise RuntimeError(f"Could not find __version__ in {init_file}")
    
    # Get description
    description_match = re.search(r'__description__\s*=\s*["\']([^"\']+)["\']', content)
    if not description_match:
        raise RuntimeError(f"Could not find __description__ in {init_file}")
    
    return version_match.group(1), description_match.group(1)

def get_version():
    """Get the version from __init__.py at project root (backward compatibility)"""
    version, _ = get_version_and_description()
    return version

def update_pyproject_toml(version, description):
    """Update version and description in pyproject.toml"""
    pyproject_file = Path("pyproject.toml")
    if not pyproject_file.exists():
        print(f"⚠️  {pyproject_file} not found, skipping...")
        return False
    
    content = pyproject_file.read_text()
    old_content = content
    
    # Update version line (anchored to line start so [tool.ruff]'s
    # `target-version` can never be clobbered into `target-version = "2.00"`)
    content = re.sub(
        r'^version\s*=\s*["\'][^"\']+["\']',
        f'version = "{version}"',
        content,
        flags=re.MULTILINE
    )
    
    # Update description line (anchored for the same reason: only a line
    # that BEGINS with `description` is the [project] field we own)
    content = re.sub(
        r'^description\s*=\s*["\'][^"\']+["\']',
        f'description = "{description}"',
        content,
        flags=re.MULTILINE
    )
    
    if content != old_content:
        pyproject_file.write_text(content)
        print(f"✅ Updated {pyproject_file} (version and description)")
        return True
    else:
        print(f"ℹ️  {pyproject_file} already up to date")
        return False


def get_license():
    """Read __license__ from __init__.py, or None if not declared."""
    project_root = Path(__file__).parent.parent.parent
    init_file = project_root / "__init__.py"
    if not init_file.exists():
        return None
    match = re.search(r'__license__\s*=\s*["\']([^"\']+)["\']', init_file.read_text())
    return match.group(1) if match else None
def update_pyproject_license():
    """Sync the SPDX license expression into pyproject.toml.
    THE DRIFT THIS CLOSES (convicted 2026-07-31): pyproject.toml declared MIT
    while LICENSE, __init__.py's header, and prompt_foo.py's cartridge
    frontmatter all declared AGPL -- and py-modules ships __init__.py INSIDE
    the wheel, so ONE distribution carried TWO contradictory grants. The
    license had been set by hand once and never re-derived from anything,
    which is exactly the shape version and description had before this script.
    Deliberately NOT adding a trove classifier: PEP 639 deprecates them in
    favor of this field, and a second authority is how the first one drifted.
    """
    license_expr = get_license()
    if not license_expr:
        print("ℹ️  No __license__ in __init__.py; skipping license sync.")
        return False
    pyproject_file = Path("pyproject.toml")
    if not pyproject_file.exists():
        print(f"⚠️  {pyproject_file} not found, skipping...")
        return False
    content = pyproject_file.read_text()
    new_content = re.sub(
        r'^license\s*=\s*["\'][^"\']+["\']',
        f'license = "{license_expr}"',
        content,
        flags=re.MULTILINE
    )
    if new_content != content:
        pyproject_file.write_text(new_content)
        print(f"✅ Updated {pyproject_file} (license → {license_expr})")
        return True
    print(f"ℹ️  {pyproject_file} license already {license_expr}")
    return False
def sync_all_versions():
    """Synchronize all version numbers and descriptions from the single source of truth"""
    print("🔄 Synchronizing version and description from single source of truth...")
    
    try:
        version, description = get_version_and_description()
        print(f"📋 Source version: {version}")
        print(f"📋 Source description: {description}")
        print()
        
        updates = []
        updates.append(update_pyproject_toml(version, description))
        updates.append(update_pyproject_license())
        # TWO DEAD LIMBS CUT 2026-09-05, both source-witnessed no-ops that the
        # Rule of Silence hid: release.py forwards only "Updated" lines, so
        # their "already up to date" verdicts were never shown. The flake
        # stamp searched flake.nix for a quoted version literal, and the flake
        # derives its version from the root __init__.py at eval time and
        # carries no such literal, so the matcher never matched. The
        # package-init stamp aimed at pipulate/__init__.py -- the PACKAGE
        # init, not the repo-root version source -- and that file has never
        # declared __version__ or __version_description__, so both of its
        # substitutions matched nothing; had the second field ever appeared
        # there, it would have received the long PyPI description in a
        # subtitle-named slot. The retired installer stamp went the same day,
        # its one-turn grep clean. A no-op that reports success is worse than
        # an absent one.


        
        print()
        if any(updates):
            print("✨ Version and description synchronization complete!")
            print("🔧 Files updated with unified version and description")
        else:
            print("✨ All files already synchronized!")
            
    except Exception as e:
        print(f"❌ Error synchronizing versions and descriptions: {e}")
        sys.exit(1)

if __name__ == "__main__":
    sync_all_versions() 
