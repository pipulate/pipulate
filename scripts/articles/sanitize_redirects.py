#!/usr/bin/env python3
"""
Sanitizes the Nginx _redirects.map file for O(1) exact-match hash lookup.
Enforces strict literal path syntax (^/[A-Za-z0-9/_.-]+$), deduplicates keys,
enforces semicolons, and aborts non-zero if a contract mismatch would wipe the map.
"""

import argparse
from pathlib import Path
import re
import sys
import common

SAFE_MAP_PATH_RE = re.compile(r"^/[A-Za-z0-9/_.-]+$")


def sanitize_map_file(filepath: Path) -> None:
    if not filepath.exists():
        print(f"⚠️ Warning: Redirect map not found at {filepath}")
        return

    print(f"🧹 Sanitizing Nginx map: {filepath.name}...")
    lines = filepath.read_text(encoding="utf-8").splitlines(keepends=True)

    clean_lines = []
    dropped_count = 0
    fixed_count = 0
    seen_sources = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            clean_lines.append(line)
            continue

        parts = stripped.split()
        if len(parts) != 2:
            print(f"  ❌ Dropped (Spaces/Bad Format): {stripped}")
            dropped_count += 1
            continue

        source, raw_target = parts
        has_semi = raw_target.endswith(";")
        target_path = raw_target[:-1] if has_semi else raw_target

        if source == "/" or not SAFE_MAP_PATH_RE.match(source):
            print(f"  ❌ Dropped (Corrupt Source Syntax): {stripped}")
            dropped_count += 1
            continue

        if not SAFE_MAP_PATH_RE.match(target_path):
            print(f"  ❌ Dropped (Dangerous Target Syntax): {stripped}")
            dropped_count += 1
            continue

        if source in seen_sources:
            print(f"  ❌ Dropped (Duplicate Source): {stripped}")
            dropped_count += 1
            continue
        seen_sources.add(source)

        if not has_semi:
            fixed_count += 1

        clean_lines.append(f"    {source} {target_path};\n")

    if dropped_count > 0 and dropped_count >= max(1, len(seen_sources)):
        print(
            f"❌ CRITICAL: Sanitizer dropped {dropped_count} line(s) vs. {len(seen_sources)} kept. "
            "Refusing to overwrite _redirects.map on a generator/sanitizer contract mismatch!"
        )
        sys.exit(1)

    if dropped_count > 0 or fixed_count > 0:
        filepath.write_text("".join(clean_lines), encoding="utf-8")
        print(f"✅ Sanitization complete. Fixed {fixed_count} lines. Dropped {dropped_count} invalid lines.")
    else:
        print("✅ Map file is already pristine.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sanitize Nginx redirect maps.")
    common.add_target_argument(parser)
    args = parser.parse_args()

    target_dir = common.get_target_path(args)
    repo_root = target_dir.parent
    map_file = repo_root / "_redirects.map"
    sanitize_map_file(map_file)


if __name__ == "__main__":
    main()
