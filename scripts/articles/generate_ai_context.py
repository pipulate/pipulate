#!/usr/bin/env python3
"""
generate_ai_context.py

Writes the journal index that the `journal` Agent Skill reads on demand:
.agents/skills/journal/references/index.md, a URL-first, reverse-chronological
ledger of the blog archive pulled via lsa.get_holographic_article_data().
Article bodies are NEVER checked into this repo, only their absolute,
fetchable /index.md URLs, so the repo stays lean while still pointing an AI
at the full intellectual history.

THE FILE MOVED (2026-09-28). It was AI_CONTEXT.md at the repo root: the AI_
prefix sorted it first in `ls`, which AGENTS.md now does by name, and its
header restated AGENTS.md and the code, which AGENTS.md forbids in so many
words. Under the Agent Skills specification (agentskills.io) the index is a
reference file: the skill's name and description cost a few tokens every
session, and this file is opened only when a question needs the reasoning
behind the machinery. The assurance posture the old header carried lives in
AUDIT.md. The script keeps its name so release.py keeps its call.

Standalone by design: depends only on lsa.py (already externalized) and the
standard library. No common.py coupling, no prompt_foo.py scaffolding to strip.

Idempotent: rewrites the index from scratch on every run. Intended as a
release-pipeline step so a fresh clone always carries the latest map.

Usage:
    python scripts/articles/generate_ai_context.py            # default target (1)
    python scripts/articles/generate_ai_context.py -t 1
    python scripts/articles/generate_ai_context.py --rich     # append shard keywords
    python scripts/articles/generate_ai_context.py --limit 50 # only the N newest
"""

import re
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Make sibling lsa.py importable regardless of the working directory, so this
# runs cleanly from the repo root (release.py) or from scripts/articles.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lsa

# scripts/articles/generate_ai_context.py -> up three == pipulate repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_FILE = REPO_ROOT / ".agents" / "skills" / "journal" / "references" / "index.md"
DEFAULT_BASE_URL = "https://mikelev.in"
DEFAULT_LIMIT = 0          # 0 = no limit; all articles indexed
FULL_URL_THRESHOLD = 20    # First N entries use full URLs; rest use compact slugs


def get_base_url(target_config: dict) -> str:
    """Canonical base URL, tolerating either 'base_url' or older 'url' keys."""
    return (target_config.get("base_url") or target_config.get("url") or DEFAULT_BASE_URL).rstrip("/")


def article_markdown_url(item: dict, base_url: str, prefix: str) -> str:
    """Mirror lsa.py --fmt dated-slugs routing: honor the YAML permalink, else
    fall back to the blog's declared permalink_prefix, always serving index.md."""
    permalink = (item.get("permalink") or "").rstrip("/")
    if not permalink:
        stem = Path(item["filename"]).stem
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)
        permalink = lsa.default_permalink(slug, prefix)
    return f"{base_url}{permalink}/index.md"


def article_slug(item: dict) -> str:
    """Extract just the bare slug from an article item."""
    permalink = (item.get("permalink") or "").rstrip("/")
    if permalink:
        return permalink.strip("/").split("/")[-1]
    stem = Path(item["filename"]).stem
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)


def build_header(article_count: int, base_url: str, prefix: str) -> str:
    """The short framing a reader sees before the index. Everything the old
    root file's header said about setup, tools, edits and assurance now lives
    where it belongs (AGENTS.md, the code, AUDIT.md); this file only points."""
    today = datetime.now().strftime("%Y-%m-%d")
    folder = f"/{prefix}" if prefix else ""
    return f"""# The Pipulate journal, indexed

> Auto-generated on {today} by `scripts/articles/generate_ai_context.py` and
> rewritten from scratch on every release. If this date looks stale, assume
> the rest of the repo is newer than this map. {article_count} entries indexed.

This repository holds the *machinery*. The *reasoning*, the running journal
that explains why every piece exists, lives on a separate website and not in
this git history, which keeps the repo lean. This file is the bridge: a
reverse-chronological index of that journal, each entry pointing at its raw
Markdown. It is the reference file of the `journal` skill one folder up.
`AGENTS.md` at the repo root is where an agent starts; `AUDIT.md` beside it
answers a reviewer's change-control questions.

## How to drill down (out-of-band, no repo bloat)

Every link below points at an `index.md` URL. The site serves raw Markdown at
those paths (the Apache-style implied `index.html` is simply swapped for
`index.md`). Fetch any entry directly, with `curl <url>` or a web-fetch tool,
and pull in only what the current question needs. Treat the list as a menu,
not a payload. Inside a checkout, `scripts/xp.py` turns a pasted list of slugs
into the next compile's context; `AGENTS.md` names that grammar.

## The narrative index (newest first)

The first {FULL_URL_THRESHOLD} entries include full `index.md` URLs to establish
the link pattern. All remaining entries are bare slugs. Reconstruct any full
URL as: `{base_url}{folder}/{{slug}}/index.md`
"""


def build_ledger(target_config: dict, rich: bool, limit) -> tuple:
    """Returns (markdown_lines, count) for the URL-first article index."""
    target_path = Path(target_config["path"]).expanduser().resolve()
    base_url = get_base_url(target_config)

    if not target_path.is_dir():
        print(f"⚠️  Article source not found: {target_path}. Writing header-only file.", file=sys.stderr)
        return "", 0

    metadata = lsa.get_holographic_article_data(str(target_path))  # newest-first
    prefix = lsa.permalink_prefix(target_config)
    folder = f"/{prefix}" if prefix else ""
    url_pattern = f"{base_url}{folder}/{{slug}}/index.md"
    if limit:
        metadata = metadata[:limit]

    lines = []
    for idx, item in enumerate(metadata):
        title = item.get("title", "Untitled")
        # File size via stat — cheap metadata syscall, no full read needed
        try:
            byte_size = Path(item["path"]).stat().st_size if item.get("path") else 0
        except OSError:
            byte_size = 0
        size_k = f"{max(1, round(byte_size / 1000))}k" if byte_size else "?"
        if idx < FULL_URL_THRESHOLD:
            url = article_markdown_url(item, base_url, prefix)
            line = f"- [{item['date']}] [{title}]({url})"
        else:
            if idx == FULL_URL_THRESHOLD:
                lines.append(
                    f"\n## Compact slug index — pattern: {url_pattern}\n"
                    f"\nFormat: `[date] [size] slug` — fetch any entry as `{url_pattern}`\n"
                )
            slug = article_slug(item)
            line = f"- [{item['date']}] [{size_k}] {slug}"
        if rich and item.get("shard_kw"):
            line += f" — {item['shard_kw']}"
        lines.append(line)

    return "\n".join(lines), len(metadata)


def main():
    parser = argparse.ArgumentParser(description="Generate the journal index (.agents/skills/journal/references/index.md).")
    parser.add_argument("-t", "--target", type=str, default="1", help="Target ID from blogs.json (default: 1)")
    parser.add_argument("--rich", action="store_true", help="Append holographic-shard keywords to each entry.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Index only the N newest articles (default: {DEFAULT_LIMIT}; 0 = all).")
    args = parser.parse_args()

    targets = lsa.load_targets()
    target_key = args.target or "1"
    if target_key not in targets:
        print(f"❌ Invalid target key: {target_key}", file=sys.stderr)
        sys.exit(1)
    target_config = targets[target_key]
    base_url = get_base_url(target_config)
    limit = args.limit if (args.limit and args.limit > 0) else None
    prefix = lsa.permalink_prefix(target_config)

    print(f"🧭 Generating the journal index from target: {target_config.get('name', target_key)}")
    ledger, count = build_ledger(target_config, args.rich, limit)
    header = build_header(count, base_url, prefix)
    body = ledger if ledger else "_No articles indexed (article source unavailable at generation time)._"

    final = header + "\n" + body + "\n"
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(final, encoding="utf-8")
    print(f"✅ Wrote {OUTPUT_FILE} ({count} entries, {len(final.encode('utf-8')):,} bytes).")


if __name__ == "__main__":
    main()
