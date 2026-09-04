#!/usr/bin/env python3
"""
generate_post_nav.py

Precomputes previous/next post links as a Jekyll data file so the post layout
does an O(1) `site.data.post_nav[page.url]` lookup instead of walking
`site.posts` once per page (O(n^2) Liquid at 1,400+ posts).

Ordering is the same flat index the old post layout rebuilt in Liquid:
newest first, and within a day highest sort_order first. That ordering comes
from lsa.get_holographic_article_data(), which is also what llms.txt uses, so
the nav and the manifest can never disagree.

Convention (matches the retired design):
  prev = the OLDER post, next = the NEWER post.

Output: <target repo root>/_data/post_nav.json, keyed by page URL.

Usage:
    python scripts/articles/generate_post_nav.py -t 1
"""
import re
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lsa
import common

OUTPUT_NAME = "post_nav.json"


def article_url(item: dict) -> str:
    """Mirror the site's URL contract: honor an explicit permalink, else /:slug/."""
    permalink = str(item.get("permalink") or "").strip()
    if permalink:
        if not permalink.startswith("/"):
            permalink = "/" + permalink
        if not permalink.endswith("/"):
            permalink += "/"
        return permalink
    stem = Path(item["filename"]).stem
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)
    return f"/{slug}/"


def build_nav(metadata: list) -> dict:
    """metadata is newest-first; neighbours are taken from that single ordering."""
    nav = {}
    total = len(metadata)
    for i, item in enumerate(metadata):
        entry = {}
        if i + 1 < total:                     # older neighbour
            older = metadata[i + 1]
            entry["prev"] = {"url": article_url(older), "title": older.get("title", "")}
        if i > 0:                             # newer neighbour
            newer = metadata[i - 1]
            entry["next"] = {"url": article_url(newer), "title": newer.get("title", "")}
        entry["position"] = total - i         # 1 = oldest, total = newest
        nav[article_url(item)] = entry
    return nav


def main():
    parser = argparse.ArgumentParser(description="Generate _data/post_nav.json (prev/next links).")
    common.add_standard_arguments(parser)
    args = parser.parse_args()

    posts_dir = common.get_target_path(args)
    repo_root = posts_dir.parent
    data_dir = repo_root / "_data"
    output_file = data_dir / OUTPUT_NAME

    metadata = lsa.get_holographic_article_data(str(posts_dir))  # newest-first
    if not metadata:
        print(f"❌ No articles found under {posts_dir}", file=sys.stderr)
        sys.exit(1)

    # THE FALLBACK'S REACHABILITY, SELF-REPORTING (2026-09-04). article_url
    # above invents "/<slug>/" for a post with no frontmatter permalink, while
    # lsa.default_permalink invents "/<prefix>/<slug>" for that same post.
    # They disagree, and NEITHER is authoritative: what Jekyll serves comes
    # from _config.yml's permalink: setting -- "/:slug/" for trimnoir, and the
    # unset `date` default for grimoire, which is neither of the two guesses.
    # permalink_prefix cannot settle it, because that value answers a
    # different question (where articleizer WRITES new posts), and it lives in
    # a file that does not own Jekyll's routing.
    # So: do not pick a winner blind. Make the branch speak. Silence means
    # every post carried its own permalink and the disagreement never fired,
    # which is the reading that decides whether a fix is owed at all.
    unlinked = [i["filename"] for i in metadata if not str(i.get("permalink") or "").strip()]
    if unlinked:
        print(f"⚠️ {len(unlinked)} post(s) have no frontmatter permalink; their nav keys are GUESSED as /<slug>/.")
        for name in unlinked[:5]:
            print(f"   - {name}")
        if len(unlinked) > 5:
            print(f"   ... and {len(unlinked) - 5} more")
    nav = build_nav(metadata)
    if len(nav) != len(metadata):
        print(f"⚠️ URL collision: {len(metadata)} posts collapsed to {len(nav)} nav keys.")

    payload = {"_meta": {"total": len(metadata)}, **nav}
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write("\n")

    newest = article_url(metadata[0])
    print(f"✅ Wrote {output_file} ({len(nav)} entries).")
    print(f"   Newest: {newest} -> prev={nav[newest].get('prev', {}).get('url', '-')}")


if __name__ == "__main__":
    main()
