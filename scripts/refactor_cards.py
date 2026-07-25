#!/usr/bin/env python3
"""
refactor_cards.py

One-shot refactoring script to replace legacy FastHTML `Card(` calls
with semantic `Article(` calls across all files in apps/.
Includes AST syntax validation before overwriting each file.
"""

import ast
import re
from pathlib import Path

APPS_DIR = Path(__file__).resolve().parent.parent / "apps"


def refactor_file(py_file: Path) -> tuple[bool, int]:
    content = py_file.read_text(encoding="utf-8")
    if "Card(" not in content:
        return False, 0

    new_content, count = re.subn(r"\bCard\(", "Article(", content)
    if count == 0 or new_content == content:
        return False, 0

    try:
        ast.parse(new_content)
    except SyntaxError as e:
        print(f"❌ Syntax error validating refactored {py_file.name}: {e}")
        return False, 0

    py_file.write_text(new_content, encoding="utf-8")
    return True, count


def main():
    print(f"🔍 Scanning {APPS_DIR} for legacy Card() calls...")
    modified_files = 0
    total_replacements = 0

    for py_file in sorted(APPS_DIR.glob("*.py")):
        modified, count = refactor_file(py_file)
        if modified:
            modified_files += 1
            total_replacements += count
            print(f"  ✅ Refactored {py_file.name}: {count} replacement(s)")

    print(
        f"\n🎉 Completed! Refactored {modified_files} file(s) "
        f"across {total_replacements} total Card() call-site(s)."
    )


if __name__ == "__main__":
    main()
