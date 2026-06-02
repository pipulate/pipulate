#!/usr/bin/env python3
"""
generate_ai_context.py

Writes AI_CONTEXT.md to the Pipulate repository root: a self-contained briefing
that lets the repo "talk back" to any AI that clones and inspects it.

It fuses a small static framing header (what Pipulate is, how to drill down, the
player-piano protocol) with a URL-first, reverse-chronological narrative ledger
pulled from the blog archive via lsa.get_holographic_article_data(). Article
bodies are NEVER checked into this repo — only their absolute, fetchable
/index.md URLs — so the repo stays lean while still pointing an AI at the full
intellectual history.

Standalone by design: depends only on lsa.py (already externalized) and the
standard library. No common.py coupling, no prompt_foo.py scaffolding to strip.

Idempotent: rewrites AI_CONTEXT.md from scratch on every run. Intended as a
release-pipeline step so a fresh clone always greets an AI with the latest map.

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
OUTPUT_FILE = REPO_ROOT / "AI_CONTEXT.md"
DEFAULT_BASE_URL = "https://mikelev.in"
DEFAULT_LIMIT = 0          # 0 = no limit; all articles indexed
FULL_URL_THRESHOLD = 20    # First N entries use full URLs; rest use compact slugs


def get_base_url(target_config: dict) -> str:
    """Canonical base URL, tolerating either 'base_url' or older 'url' keys."""
    return (target_config.get("base_url") or target_config.get("url") or DEFAULT_BASE_URL).rstrip("/")


def article_markdown_url(item: dict, base_url: str) -> str:
    """Mirror lsa.py --fmt dated-slugs routing: honor the YAML permalink, else
    fall back to /futureproof/<slug>/, always serving the raw index.md variant."""
    permalink = (item.get("permalink") or "").rstrip("/")
    if not permalink:
        stem = Path(item["filename"]).stem
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)
        permalink = f"/futureproof/{slug}"
    return f"{base_url}{permalink}/index.md"


def article_slug(item: dict) -> str:
    """Extract just the bare slug from an article item."""
    permalink = (item.get("permalink") or "").rstrip("/")
    if permalink:
        return permalink.strip("/").split("/")[-1]
    stem = Path(item["filename"]).stem
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)


def build_header(article_count: int, base_url: str) -> str:
    """The static framing an interrogating AI reads before the index."""
    today = datetime.now().strftime("%Y-%m-%d")
    host = base_url.replace("https://", "").replace("http://", "").rstrip("/")
    return f"""# AI_CONTEXT.md — Start Here If You Are an AI

> Auto-generated on {today}. Rewritten from scratch on every release. If this
> date looks stale, assume the rest of the repo is newer than this map.
> {article_count} entries indexed.

You are reading the orientation file for **Pipulate**, a local-first,
hand-cranked AI/SEO automation framework (the NPvg stack: Nix, Python, Vim,
Git). If a human asked you to investigate `pipulate/pipulate`, read this before
forming conclusions.

## What this file is

This repository holds the *machinery*. The *reasoning* — the running journal
that explains why every piece exists — lives on a separate website, not in this
git history (that keeps the repo lean). This file is the bridge: a
reverse-chronological index of that journal, each entry linking straight to its
raw Markdown.

## How to drill down (out-of-band, no repo bloat)

Every link below points at an `index.md` URL. The site serves raw Markdown at
those paths (the Apache-style implied `index.html` is simply swapped for
`index.md`). Fetch any entry directly — `curl <url>` or your web-fetch tool —
and pull in only what the current question needs. Treat the list as a menu, not
a payload.

## If you are running inside this repo locally

Request a precise context bundle for yourself with the player-piano protocol:
emit a block like the one below and pipe your clipboard through `xp`
(`scripts/xp.py`), which resolves bare slugs *or* full `index.md` URLs and
recompiles a fresh context payload.
```text
[[[TODO_SLUGS]]]
deterministic-ai-wet-philosophy
https://{host}/futureproof/magic-cookie-pattern-self-bootstrapping-sovereignty/index.md
[[[END_SLUGS]]]

[[[TODO_FILES]]]
prompt_foo.py
apply.py
[[[END_FILES]]]
```
For a guided, interactive tour of the codebase itself, run
`.venv/bin/python AI_RUNME.py`.

## The narrative index (newest first)

The first {FULL_URL_THRESHOLD} entries include full `index.md` URLs to establish
the link pattern. All remaining entries are bare slugs. Reconstruct any full
URL as: `{base_url}/futureproof/{{slug}}/index.md`
"""


def build_ledger(target_config: dict, rich: bool, limit) -> tuple:
    """Returns (markdown_lines, count) for the URL-first article index."""
    target_path = Path(target_config["path"]).expanduser().resolve()
    base_url = get_base_url(target_config)

    if not target_path.is_dir():
        print(f"⚠️  Article source not found: {target_path}. Writing header-only file.", file=sys.stderr)
        return "", 0

    metadata = lsa.get_holographic_article_data(str(target_path))  # newest-first
    if limit:
        metadata = metadata[:limit]

    lines = []
    for idx, item in enumerate(metadata):
        title = item.get("title", "Untitled")
        if idx < FULL_URL_THRESHOLD:
            url = article_markdown_url(item, base_url)
            line = f"- [{item['date']}] [{title}]({url})"
        else:
            if idx == FULL_URL_THRESHOLD:
                lines.append(f"\n## Compact slug index — pattern: {base_url}/futureproof/{{slug}}/index.md\n")
            slug = article_slug(item)
            line = f"- [{item['date']}] {slug}: {title}"
        if rich and item.get("shard_kw"):
            line += f" — {item['shard_kw']}"
        lines.append(line)

    return "\n".join(lines), len(metadata)


def main():
    parser = argparse.ArgumentParser(description="Generate AI_CONTEXT.md repo briefing.")
    parser.add_argument("-t", "--target", type=str, default="1", help="Target ID from targets.json (default: 1)")
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

    print(f"🧭 Generating AI_CONTEXT.md from target: {target_config.get('name', target_key)}")
    ledger, count = build_ledger(target_config, args.rich, limit)
    header = build_header(count, base_url)
    body = ledger if ledger else "_No articles indexed (article source unavailable at generation time)._"

    final = header + "\n" + body + "\n"
    OUTPUT_FILE.write_text(final, encoding="utf-8")
    print(f"✅ Wrote {OUTPUT_FILE} ({count} entries, {len(final.encode('utf-8')):,} bytes).")


if __name__ == "__main__":
    main()
