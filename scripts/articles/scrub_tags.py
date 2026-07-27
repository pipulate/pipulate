#!/usr/bin/env python3
"""
scrub_tags.py — Generic Tag & Credential Scrubber for Pipulate.

Sweeps articles and text files for Liquid template tags ({% raw %}, {% endraw %})
and potential private credential leaks (Bearer tokens, AWS keys, GitHub PATs,
private key blocks, generic API secrets).
"""

import argparse
import re
import sys
from pathlib import Path

# Patterns for credentials and template artifacts
SCRUB_RULES = [
    (
        "Liquid Raw Tag (start)",
        re.compile(r"\{%\s*raw\s*%\}"),
        "",
    ),
    (
        "Liquid Raw Tag (end)",
        re.compile(r"\{%\s*endraw\s*%\}"),
        "",
    ),
    (
        "Private Key Block",
        re.compile(
            r"-----BEGIN (?:RSA|OPENSSH|EC|PGP)?\s*PRIVATE KEY-----[\s\S]*?-----END (?:RSA|OPENSSH|EC|PGP)?\s*PRIVATE KEY-----"
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (
        "Google OAuth Token",
        re.compile(r"\bya29\.[a-zA-Z0-9_\-]{30,}\b"),
        "[REDACTED_OAUTH_TOKEN]",
    ),
    (
        "Bearer Authorization Header",
        re.compile(r"(?i)\bBearer\s+[a-zA-Z0-9_\-\.~+/]+=*"),
        "Bearer [REDACTED_TOKEN]",
    ),
    (
        "AWS Access Key ID",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_KEY]",
    ),
    (
        "GitHub Token",
        re.compile(r"\b(?:ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82})\b"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    (
        "Generic API Secret Assignment",
        re.compile(
            r"(?i)\b(api[_\-]?key|secret|password|auth[_\-]?token)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{16,})['\"]?"
        ),
        r"\1: '[REDACTED_SECRET]'",
    ),
]


def scrub_content(content: str) -> tuple[str, dict[str, int]]:
    """Apply scrub rules to text content and return (new_content, match_counts)."""
    counts = {}
    new_content = content
    for label, pattern, replacement in SCRUB_RULES:
        new_content, n = pattern.subn(replacement, new_content)
        if n > 0:
            counts[label] = n
    return new_content, counts


def process_path(target_path: Path, dry_run: bool = True) -> int:
    """Process a single file or traverse a directory recursively."""
    if not target_path.exists():
        print(f"❌ Path not found: {target_path}")
        return 0

    files_to_process = []
    if target_path.is_file():
        files_to_process.append(target_path)
    else:
        for ext in ("*.md", "*.txt"):
            files_to_process.extend(target_path.rglob(ext))

    modified_count = 0
    mode_label = "DRY RUN MODE" if dry_run else "LIVE MODE"
    print(f"--- 🧹 Scrubbing Tags & Secrets ({mode_label}): {target_path} ---")

    for file_path in files_to_process:
        try:
            original_content = file_path.read_text(encoding="utf-8")
            new_content, counts = scrub_content(original_content)

            if original_content != new_content:
                modified_count += 1
                print(f"📌 Found matches in: {file_path}")
                for rule_name, count in counts.items():
                    print(f"   • {rule_name}: {count} instance(s)")

                if not dry_run:
                    file_path.write_text(new_content, encoding="utf-8")
                    print(f"   ✅ Updated {file_path.name}")
        except Exception as e:
            print(f"⚠️ Error reading {file_path}: {e}")

    action = "Would modify" if dry_run else "Modified"
    print(f"\n✨ {action} {modified_count} file(s).")
    return modified_count


def main():
    parser = argparse.ArgumentParser(
        description="Scrub Liquid template tags and secret credentials from text and markdown files."
    )
    parser.add_argument(
        "target",
        help="File or directory path to scan (e.g., article.txt or _posts)",
    )
    parser.add_argument(
        "--do-it",
        action="store_true",
        help="Perform changes in-place (disables default dry-run mode)",
    )
    args = parser.parse_args()

    process_path(Path(args.target).resolve(), dry_run=not args.do_it)


if __name__ == "__main__":
    main()
