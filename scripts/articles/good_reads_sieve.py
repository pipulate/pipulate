#!/usr/bin/env python3
"""Materialize 3-2-1 Progressive Good-Read Editions from _posts/{_abstracts,_briefs}."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

_RAW_TAG_RE = re.compile(r"^\s*\{%\s*(?:raw|endraw)\s*%\}\s*$", re.MULTILINE)
_WEEBO_LINE_RE = re.compile(r"^[ \t]*\[\[\[weebo:([^\]]+)\]\]\][ \t]*$", re.IGNORECASE | re.MULTILINE)


def _split_frontmatter(raw_text: str) -> tuple[dict, str]:
    text = (raw_text or "").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text.strip()
    end_idx = text.find("\n---\n", 4)
    if end_idx == -1:
        return {}, text.strip()
    fm_raw, body = text[4:end_idx], text[end_idx + 5 :].strip()
    try:
        loaded = yaml.safe_load(fm_raw)
        meta = loaded if isinstance(loaded, dict) else {}
    except Exception:
        meta = {}
    return meta, body


def _clean_edition_body(body: str, edition: str) -> str:
    cleaned = _RAW_TAG_RE.sub("", body or "").strip()
    cleaned = _WEEBO_LINE_RE.sub(r"<!-- weebo:\1 -->", cleaned)
    if edition == "norma":
        cleaned = re.sub(r"(?m)^\*\*Me\*\*:", "**Mike**:", cleaned)
    return "{% raw %}\n" + cleaned + "\n{% endraw %}\n"


def _build_edition_doc(edition: str, parent_meta: dict, ed_meta: dict, slug: str, date_str: str, base_url: str, body: str) -> tuple[str, str]:
    parent_url = str(parent_meta.get("permalink") or f"/futureproof/{slug}/").strip()
    if not parent_url.startswith("/"):
        parent_url = "/" + parent_url
    if not parent_url.endswith("/"):
        parent_url += "/"
    sub = "norma" if edition == "norma" else "brief"
    permalink = f"{parent_url}{sub}/"
    title = str(ed_meta.get("title") or parent_meta.get("title") or slug).strip()
    desc = str(ed_meta.get("summary") or parent_meta.get("meta_description") or parent_meta.get("description") or "").strip()
    aid = ed_meta.get("article_id") or parent_meta.get("article_id")
    img = parent_meta.get("image")
    img_path = img.get("path", "") if isinstance(img, dict) else (img if isinstance(img, str) else "")
    img_alt = img.get("alt", "") if isinstance(img, dict) else ""
    fm = [
        "---",
        "layout: post",
        f"edition: {edition}",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"date: {date_str}",
        f"permalink: {permalink}",
        f"canonical_url: {base_url.rstrip('/')}{parent_url}",
        f"canonical_raw_url: {parent_url}",
        "sitemap: false",
    ]
    if desc:
        fm.extend([f"description: {json.dumps(desc, ensure_ascii=False)}", f"excerpt: {json.dumps(desc, ensure_ascii=False)}"])
    if str(aid or "").isdigit():
        fm.append(f"article_id: {int(aid)}")
    for k in ("gdoc_url", "vod_url"):
        if parent_meta.get(k):
            fm.append(f"{k}: {json.dumps(str(parent_meta[k]), ensure_ascii=False)}")
    if img_path:
        fm.extend(["image:", f"  path: {json.dumps(str(img_path), ensure_ascii=False)}", f"  alt: {json.dumps(str(img_alt or title), ensure_ascii=False)}"])
    fm.append("---")
    return permalink, "\n".join(fm) + "\n\n" + _clean_edition_body(body, edition)


def sync_good_read_editions(target_key: str, target_path: Path, verbose: bool = False) -> dict:
    if str(target_key) != "1" or not Path(target_path).is_dir():
        return {"norma": 0, "csuite": 0, "written": 0, "removed": 0}
    posts_dir = Path(target_path).expanduser().resolve()
    repo_root = posts_dir.parent
    targets = common.load_targets()
    base_url = str((targets.get(str(target_key)) or {}).get("base_url") or "https://" + "mikelev.in")
    specs = (("norma", posts_dir / "_abstracts", repo_root / "editions" / "norma"), ("csuite", posts_dir / "_briefs", repo_root / "editions" / "brief"))
    counts = {"norma": 0, "csuite": 0, "written": 0, "removed": 0}
    keep = {"norma": set(), "csuite": set()}
    for md_path in sorted(posts_dir.glob("*.md")):
        if not common._DATED_POST_RE.match(md_path.name):
            continue
        slug, date_str = md_path.stem[11:], md_path.name[:10]
        p_meta = None
        for ed_key, src_dir, out_dir in specs:
            src_file = src_dir / md_path.name
            if not src_file.is_file():
                continue
            if p_meta is None:
                p_meta, _ = _split_frontmatter(md_path.read_text(encoding="utf-8", errors="replace"))
            e_meta, e_body = _split_frontmatter(src_file.read_text(encoding="utf-8", errors="replace"))
            _, rendered = _build_edition_doc(ed_key, p_meta, e_meta, slug, date_str, base_url, e_body)
            out_file = out_dir / f"{slug}.md"
            keep[ed_key].add(out_file.name)
            counts[ed_key] += 1
            old = out_file.read_text(encoding="utf-8") if out_file.is_file() else None
            if old != rendered:
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file.write_text(rendered, encoding="utf-8")
                counts["written"] += 1
    for ed_key, _, out_dir in specs:
        if out_dir.is_dir():
            for stale in sorted(out_dir.glob("*.md")):
                if stale.name not in keep[ed_key]:
                    stale.unlink()
                    counts["removed"] += 1
    if (counts["written"] or counts["removed"]) and (repo_root / ".git").exists() and (repo_root / "editions").exists():
        subprocess.run(["git", "-C", str(repo_root), "add", "--", "editions"], capture_output=True, text=True, check=False)
    if verbose or counts["written"] or counts["removed"]:
        print(f"📚 Good-Read Editions synced ({repo_root.name}): {counts['norma']} Norma, {counts['csuite']} C-Suite ({counts['written']} written, {counts['removed']} pruned).")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync 3-2-1 Progressive Good-Read Editions.")
    common.add_standard_arguments(parser)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    sync_good_read_editions(args.target, common.get_target_path(args), verbose=args.verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
