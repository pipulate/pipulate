#!/usr/bin/env python3
"""
Generates the definitive `llms.txt` file by fusing a static, 
highly curated "Prime Directive" header with a reverse-chronological 
dump of all article metadata, utilizing the `lsa.py` extraction logic.
"""

import html
import json
import re
import shutil
import sys
import argparse
from pathlib import Path
import lsa
import common
from datetime import datetime

# --- CONFIGURATION ---
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_DIR = REPO_ROOT / "scripts" / "articles"
HEADER_FILE = REPO_ROOT / "assets" / "prompts" / "llms_header.md"
OUTPUT_FILE = SCRIPT_DIR / "llms.txt"
ROBOTS_FILE = SCRIPT_DIR / "robots.txt"
SITEMAP_FILE = SCRIPT_DIR / "sitemap.xml"


def resolve_base_url(target_config: dict) -> str:
    return (target_config.get('base_url') or target_config.get('url')
            or 'https://mikelev.in').rstrip('/')


def resolve_post_permalink(item: dict, prefix: str) -> str:
    slug = str(item.get('permalink') or '').strip('/')
    if not slug:
        raw_slug = item['filename'].replace('.md', '').replace('.markdown', '')
        if len(raw_slug) > 10 and raw_slug[10] == '-':
            raw_slug = raw_slug[11:]
        slug = lsa.default_permalink(raw_slug, prefix).strip('/')
    return f"/{slug}/" if slug else "/"


def build_header(target_key: str, target_config: dict) -> str:
    """Use the curated static header for Target 1; synthesize a target-aware header for all others."""
    if str(target_key) == "1" and HEADER_FILE.exists():
        return HEADER_FILE.read_text(encoding='utf-8').strip()

    base_url = resolve_base_url(target_config)
    raw_name = target_config.get('name', 'Site')
    site_title = raw_name.removesuffix(' (Public)').removesuffix(' (Private)').strip() or raw_name
    pitch = (target_config.get('editorial_context') or '').strip()

    lines = [
        f"# {site_title} — AI Context & Content Negotiation Manifest",
        "",
    ]
    if pitch:
        lines.extend([f"> {pitch}", ""])
    lines.extend([
        "## Wire-Truth & RFC 9110 Content Negotiation",
        "This origin supports proactive HTTP content negotiation (RFC 9110 Section 12).",
        "Automated agents and crawlers may request clean Markdown directly at any canonical URL by sending:",
        "`Accept: text/markdown`",
        "",
        f"- **Canonical Base URL**: {base_url}",
        f"- **XML Sitemap**: {base_url}/sitemap.xml",
        f"- **Robots Policy**: {base_url}/robots.txt",
        "",
        "## Chronological Article Ledger",
    ])
    return "\n".join(lines)


def build_payload(target_config: dict) -> tuple[str, list[dict]]:
    """Generates the dense, reverse-chronological ledger using lsa.py logic."""
    target_path = Path(target_config['path']).expanduser().resolve()
    base_url = resolve_base_url(target_config)
    prefix = lsa.permalink_prefix(target_config)

    print(f"📚 Extracting metadata from: {target_path}")
    if not target_path.exists():
        print(f"ℹ️  {target_path} does not exist yet; generating seed manifest with 0 posts.")
        return "", []

    metadata = lsa.get_holographic_article_data(str(target_path))

    lines = []
    for item in metadata:
        perma = resolve_post_permalink(item, prefix)
        full_url = f"{base_url}{perma}index.md?src=llms.txt"

        summary = item.get('shard_sum') or item.get('summary', '')
        kw_str = f" | KW: {item['shard_kw']}" if item.get('shard_kw') else ""
        sub_str = f" | SUB: {item['shard_sub']}" if item.get('shard_sub') else ""

        dense_line = (f"[{item['date']}] {full_url} "
                      f"(Ord:{item['sort_order']}) | "
                      f"{item['title']}{kw_str}{sub_str} | SUM: {summary}")
        lines.append(dense_line)

    return "\n".join(lines), metadata


def build_robots_txt(target_config: dict) -> str:
    base_url = resolve_base_url(target_config)
    return (
        "User-agent: *\n"
        "Allow: /\n\n"
        "# AI Discovery & RFC 9110 Content Negotiation\n"
        "# Agents: send 'Accept: text/markdown' on any canonical URL for raw Markdown.\n"
        f"# LLMs-Txt: {base_url}/llms.txt\n"
        f"Sitemap: {base_url}/sitemap.xml\n"
    )


def build_flat_sitemap_xml(target_config: dict, metadata: list[dict]) -> str:
    base_url = resolve_base_url(target_config)
    prefix = lsa.permalink_prefix(target_config)
    today = datetime.now().strftime('%Y-%m-%d')
    urls = [
        f"  <url><loc>{base_url}/</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>",
        f"  <url><loc>{base_url}/llms.txt</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>",
    ]
    for item in metadata:
        perma = resolve_post_permalink(item, prefix)
        mod_date = str(item.get('date') or today)
        urls.append(
            f"  <url><loc>{base_url}{perma}</loc><lastmod>{mod_date}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )


def build_hub_topology_section(target_config: dict) -> str:
    """Render the 2-Tier Hub Map (Macro-Pillars -> Sub-Hubs) when navgraph.json is in pipeline."""
    if "build_knowledge_graph.py" not in target_config.get("pipeline", []):
        return ""
    navgraph_path = SCRIPT_DIR / "navgraph.json"
    if not navgraph_path.is_file():
        return ""
    try:
        nav_tree = json.loads(navgraph_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    pillars = nav_tree.get("children_hubs") or []
    if not pillars:
        return ""
    base_url = resolve_base_url(target_config)
    total_hubs = sum(1 + len(p.get("children_hubs") or []) for p in pillars)
    lines = [
        "---",
        "",
        f"## THREE-HOP TOPIC HUB DIRECTORY ({len(pillars)} PILLARS -> {total_hubs} PERMANENT HUBS)",
        "Agents may traverse the corpus in <= 3 Markdown hops (`/` -> `/<hub>/` -> `/futureproof/<slug>/`) via `Accept: text/markdown` (RFC 9110):",
        f"- **Link-Graph Topology (JSON)**: {base_url}/graph.json",
        f"- **XML Sitemap Index**: {base_url}/sitemap.xml (`sitemap-hubs.xml` + `sitemap-branch-0..{len(pillars) - 1}.xml`)",
        "",
    ]
    for p in pillars:
        kids = p.get("children_hubs") or []
        p_arts = len(p.get("children_articles") or [])
        branch_arts = p_arts + sum(len(c.get("children_articles") or []) for c in kids)
        span_note = f"{p_arts} articles; branch total: {branch_arts}" if kids else f"{p_arts} articles"
        lines.append(f"- **[{p['title']}]({base_url}{p['permalink']}index.md?src=llms.txt)** ({span_note})")
        for c in kids:
            c_arts = len(c.get("children_articles") or [])
            lines.append(f"  - [{c['title']}]({base_url}{c['permalink']}index.md?src=llms.txt) ({c_arts} articles)")
    lines.extend(["", "---", "", "## CHRONOLOGICAL ARTICLE LEDGER"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate llms.txt, robots.txt, and flat sitemap.xml")
    common.add_standard_arguments(parser)
    args = parser.parse_args()

    targets = common.load_targets()
    target_key = args.target

    if not target_key:
        print("🤖 Generating llms.txt...")
        print("Select Target Repo:")
        for k, v in targets.items():
            print(f"  [{k}] {v['name']} ({v['path']})")
        target_key = input("Enter choice (default 1): ").strip() or "1"

    if target_key not in targets:
        print(f"❌ Invalid target key: {target_key}", file=sys.stderr)
        sys.exit(1)

    target_config = targets[target_key]

    # 1. Build Header + Hub Topology + Payload for llms.txt
    header_content = build_header(target_key, target_config)
    hub_section = build_hub_topology_section(target_config)
    payload_content, metadata = build_payload(target_config)
    sections = [s for s in (header_content, hub_section, payload_content) if s]
    final_content = "\n\n".join(sections) + "\n"

    OUTPUT_FILE.write_text(final_content, encoding='utf-8')
    print(f"✅ Successfully generated: {OUTPUT_FILE}")

    # 2. Build robots.txt
    ROBOTS_FILE.write_text(build_robots_txt(target_config), encoding='utf-8')
    print(f"✅ Successfully generated: {ROBOTS_FILE}")

    # 3. Build flat sitemap.xml when build_knowledge_graph.py is not in this target's pipeline
    pipeline = target_config.get('pipeline', [])
    if "build_knowledge_graph.py" not in pipeline:
        for old_sub in SCRIPT_DIR.glob("sitemap-*.xml"):
            old_sub.unlink()
        SITEMAP_FILE.write_text(build_flat_sitemap_xml(target_config, metadata), encoding='utf-8')
        print(f"✅ Successfully generated flat sitemap: {SITEMAP_FILE} ({len(metadata)} post(s))")


if __name__ == "__main__":
    main()
