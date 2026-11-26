#!/usr/bin/env python3
"""Materialize 3-2-1 Progressive Good-Read Editions from _posts/{_abstracts,_briefs}."""

import argparse
import html
import shutil
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
_WEEBO_ANY_RE = re.compile(r"\[\[\[weebo:[^\]]+\]\]\]", re.IGNORECASE)
SIEVE_STAGE_DIR = Path.home() / ".cache" / "pipulate" / "good_reads_www"
_UPSTREAM_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(https?://(?:w{3}\.)?mikelev\.in[^)]*\)", re.IGNORECASE)
_UPSTREAM_PAREN_URL_RE = re.compile(r"\s*\(\s*https?://(?:w{3}\.)?mikelev\.in[^)]*\)", re.IGNORECASE)
_UPSTREAM_BARE_URL_RE = re.compile(r"https?://(?:w{3}\.)?mikelev\.in[^\s)>]*", re.IGNORECASE)
_UPSTREAM_DOMAIN_RE = re.compile(r"\bmikelev\.in(?:/[^\s.,;:!?)>'\"]*)?", re.IGNORECASE)


def _scrub_upstream(body: str, fallback_url: str, brand_label: str) -> str:
    s = _RAW_TAG_RE.sub("", body or "").strip()
    s = _WEEBO_ANY_RE.sub("", _WEEBO_LINE_RE.sub("", s))
    s = re.sub(r"(?m)^\*\*(?:Me|MikeLev\.in)\*\*:", "**Mike**:", s)
    s = _UPSTREAM_MD_LINK_RE.sub(lambda m: fallback_url if "mikelev.in" in m.group(1).lower() else m.group(1), s)
    s = _UPSTREAM_PAREN_URL_RE.sub("", s)
    s = _UPSTREAM_BARE_URL_RE.sub(fallback_url, s)
    s = _UPSTREAM_DOMAIN_RE.sub(brand_label, s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def _inline_md(text: str) -> str:
    codes: list[str] = []
    def _stash(m):
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00C{len(codes) - 1}\x00"
    s = re.sub(r"`([^`]+)`", _stash, text)
    s = html.escape(s, quote=False)
    s = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+|/[^)\s]*)\)",
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
        s,
    )
    s = re.sub(r"\*\*\*([^*]+)\*\*\*", r"<strong><em>\1</em></strong>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    for i, c in enumerate(codes):
        s = s.replace(f"\x00C{i}\x00", c)
    return s


def _md_to_html(md_body: str) -> str:
    out, para, list_tag = [], [], None
    def _flush():
        if para:
            out.append(f"<p>{_inline_md(' '.join(para))}</p>")
            para.clear()
    def _close():
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None
    for raw_ln in (md_body or "").splitlines():
        ln = raw_ln.strip()
        if not ln or ln.startswith("<!--"):
            _flush()
            _close()
            continue
        if ln in ("---", "***"):
            _flush()
            _close()
            out.append("<hr>")
            continue
        m_h = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m_h:
            _flush()
            _close()
            lvl = min(4, max(2, len(m_h.group(1))))
            out.append(f"<h{lvl}>{_inline_md(m_h.group(2).strip())}</h{lvl}>")
            continue
        m_ul, m_ol = re.match(r"^[-*]\s+(.*)$", ln), re.match(r"^\d+\.\s+(.*)$", ln)
        if m_ul or m_ol:
            _flush()
            want = "ul" if m_ul else "ol"
            if list_tag != want:
                _close()
                out.append(f"<{want}>")
                list_tag = want
            out.append(f"  <li>{_inline_md((m_ul or m_ol).group(1).strip())}</li>")
            continue
        if ln.startswith(">"):
            _flush()
            _close()
            out.append(f"<blockquote>{_inline_md(ln.lstrip('> ').strip())}</blockquote>")
            continue
        _close()
        para.append(ln)
    _flush()
    _close()
    return "\n".join(out)


def _wrap_door_html(title: str, desc: str, canon_url: str, crumb_html: str, switcher_html: str, body_html: str) -> str:
    esc_t, esc_d = html.escape(title), html.escape(desc, quote=True)
    return (
        f"<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{esc_t}</title>\n"
        + (f"<meta name=\"description\" content=\"{esc_d}\">\n" if desc else "")
        + f"<link rel=\"canonical\" href=\"{html.escape(canon_url, quote=True)}\">\n"
        f"<link rel=\"alternate\" type=\"text/markdown\" href=\"index.md\">\n"
        "<style>\n  body { max-width: 42rem; margin: 3rem auto; padding: 0 1rem; font: 18px/1.55 Georgia, serif; color: #111; }\n"
        "  pre, code { background: #f4f4f4; border-radius: 4px; font-family: ui-monospace, monospace; font-size: 0.9em; }\n"
        "  code { padding: 0.12rem 0.32rem; }\n  blockquote { margin: 1.5rem 0; padding: 0.2rem 1rem; border-left: 3px solid #ccc; color: #444; }\n"
        "  .sieve-bar { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; margin: 1rem 0 1.5rem; padding: 0.65rem 0.85rem; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; font: 14px/1.3 system-ui, sans-serif; }\n"
        "  .pill-on { padding: 0.28rem 0.7rem; border-radius: 999px; background: #0f172a; color: #fff; font-weight: 700; }\n"
        "  .pill-off { padding: 0.28rem 0.7rem; border-radius: 999px; border: 1px solid #94a3b8; color: #0f172a; text-decoration: none; font-weight: 600; }\n"
        "  .crumb { font: 14px/1.4 system-ui, sans-serif; color: #475569; margin-bottom: 0.75rem; }\n  .crumb a { color: #0f172a; }\n</style>\n"
        f"</head>\n<body>\n<div class=\"crumb\">{crumb_html}</div>\n<h1>{esc_t}</h1>\n"
        f"{switcher_html}\n{body_html}\n</body>\n</html>\n"
    )


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
    counts["downstream"] = project_downstream_doors(posts_dir, verbose=verbose)
    return counts


def _write_bimodal(out_dir: Path, title: str, desc: str, date_s: str, canon: str, crumb: str, sw_html: str, sw_md: str, md_body: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_doc = f"# {title}\n\n*{date_s}*" + (f" · {sw_md}" if sw_md else "") + f"\n\n{md_body}\n"
    (out_dir / "index.md").write_text(md_doc, encoding="utf-8")
    body_h = f"<p style=\"color:#475569;font-size:0.9em;\">{html.escape(date_s)}</p>\n" + _md_to_html(md_body)
    (out_dir / "index.html").write_text(_wrap_door_html(title, desc, canon, crumb, sw_html, body_h), encoding="utf-8")


def _resolve_brief_pillars(p_meta: dict, e_meta: dict, title: str, body: str) -> set[str]:
    import norma_extract
    raw_p = e_meta.get("pillars") if "pillars" in (e_meta or {}) else (p_meta or {}).get("pillars")
    if raw_p is not None:
        items = raw_p if isinstance(raw_p, list) else re.split(r"[,|\s]+", str(raw_p).strip("[]"))
        return {str(x).strip().upper() for x in items if str(x).strip()} & {"RFC_9110", "RFC_9111", "SUNPUG"}
    _, matched = norma_extract.score_pillars(title, body)
    return set(matched)


def project_downstream_doors(posts_dir: Path, stage_root: Path = SIEVE_STAGE_DIR, verbose: bool = False) -> dict:
    pdir, sroot = Path(posts_dir).expanduser().resolve(), Path(stage_root).expanduser().resolve()
    for sub in (sroot / "sunpug.io" / "stories", sroot / "rfc9110.org" / "briefs", sroot / "rfc9111.io" / "briefs"):
        if sub.exists():
            shutil.rmtree(sub)
    sp_rows, rfc_rows = [], {"rfc9110.org": [], "rfc9111.io": []}
    candidates = []
    for md_p in pdir.glob("*.md"):
        if common._DATED_POST_RE.match(md_p.name) and ((pdir / "_abstracts" / md_p.name).is_file() or (pdir / "_briefs" / md_p.name).is_file()):
            pm, _ = _split_frontmatter(md_p.read_text(encoding="utf-8", errors="replace"))
            candidates.append(((md_p.name[:10], int(pm.get("sort_order") or 0), md_p.stem), md_p, pm))
    for _, md_p, p_meta in sorted(candidates, key=lambda r: r[0], reverse=True):
        slug, date_s = md_p.stem[11:], md_p.name[:10]
        abs_p, brf_p = pdir / "_abstracts" / md_p.name, pdir / "_briefs" / md_p.name
        has_n, has_b = abs_p.is_file(), brf_p.is_file()
        n_meta, n_raw = _split_frontmatter(abs_p.read_text(encoding="utf-8", errors="replace")) if has_n else ({}, "")
        b_meta, b_raw = _split_frontmatter(brf_p.read_text(encoding="utf-8", errors="replace")) if has_b else ({}, "")
        if str(p_meta.get("sunpug", "true")).lower() not in ("false", "0", "no"):
            sp_base = f"https://sunpug.io/stories/{slug}/"
            crumb = '<a href="/">← Sun Pug</a> &middot; <a href="/stories/">Good-Reads</a> &middot; <a href="index.md">Raw Markdown (RFC 9110)</a>'
            sw_n = f'<div class="sieve-bar"><span>Choose Depth:</span><span class="pill-on">🎭 Socratic Good-Read</span><a class="pill-off" href="/stories/{slug}/brief/">💼 Executive Brief</a></div>' if (has_n and has_b) else ""
            sw_b = f'<div class="sieve-bar"><span>Choose Depth:</span><a class="pill-off" href="/stories/{slug}/">🎭 Socratic Good-Read</a><span class="pill-on">💼 Executive Brief</span></div>' if (has_n and has_b) else ""
            if has_n:
                nt = _scrub_upstream(str(n_meta.get("title") or p_meta.get("title") or slug), sp_base, "SunPug.io")
                nd = _scrub_upstream(str(p_meta.get("meta_description") or p_meta.get("description") or ""), sp_base, "SunPug.io")
                _write_bimodal(sroot / "sunpug.io" / "stories" / slug, nt, nd, date_s, sp_base, crumb, sw_n, f"[Executive Brief](/stories/{slug}/brief/)" if has_b else "", _scrub_upstream(n_raw, sp_base, "SunPug.io"))
            if has_b:
                bt = _scrub_upstream(str(b_meta.get("title") or p_meta.get("title") or slug), sp_base, "SunPug.io")
                bd = _scrub_upstream(str(b_meta.get("summary") or p_meta.get("meta_description") or ""), sp_base, "SunPug.io")
                b_dest = (sroot / "sunpug.io" / "stories" / slug / "brief") if has_n else (sroot / "sunpug.io" / "stories" / slug)
                _write_bimodal(b_dest, bt, bd, date_s, f"{sp_base}brief/" if has_n else sp_base, crumb, sw_b, f"[Socratic Good-Read](/stories/{slug}/)" if has_n else "", _scrub_upstream(b_raw, sp_base, "SunPug.io"))
            lead_t = _scrub_upstream(str((n_meta if has_n else b_meta).get("title") or p_meta.get("title") or slug), sp_base, "SunPug.io")
            badges = " · ".join(x for x, ok in (("🎭 Socratic", has_n), ("💼 Brief", has_b)) if ok)
            sp_rows.append(f"- **{date_s}** — [{lead_t}](/stories/{slug}/) ({badges})")
        if has_b:
            bt_raw = str(b_meta.get("title") or p_meta.get("title") or slug).strip()
            bd_raw = str(b_meta.get("summary") or p_meta.get("meta_description") or "").strip()
            pillars = _resolve_brief_pillars(p_meta, b_meta, bt_raw, b_raw)
            for pk, dom, lbl in (("RFC_9110", "rfc9110.org", "RFC 9110"), ("RFC_9111", "rfc9111.io", "RFC 9111")):
                if pk in pillars:
                    rc_url = f"https://{dom}/briefs/{slug}/"
                    bt, bd = _scrub_upstream(bt_raw, rc_url, lbl), _scrub_upstream(bd_raw, rc_url, lbl)
                    rc_crumb = f'<a href="/">← {lbl}</a> &middot; <a href="/briefs/">Executive Briefs</a> &middot; <a href="index.md">Raw Markdown (RFC 9110)</a>'
                    _write_bimodal(sroot / dom / "briefs" / slug, bt, bd, date_s, rc_url, rc_crumb, "", "", _scrub_upstream(b_raw, rc_url, lbl))
                    rfc_rows[dom].append(f"- **{date_s}** — [{bt}](/briefs/{slug}/)" + (f" — {bd}" if bd else ""))
    sp_idx = "\n".join(sp_rows) or "- *Good-Read episodes populate automatically from `_posts/_abstracts/`.*"
    _write_bimodal(sroot / "sunpug.io" / "stories", "Sun Pug Good-Reads: Socratic & Executive Editions", "Plain-English Socratic parables and architectural briefs on reproducible AI workflows.", "Updated Live", "https://sunpug.io/stories/", '<a href="/">← Sun Pug Home</a> &middot; <a href="index.md">Raw Markdown (RFC 9110)</a>', "", "", sp_idx)
    for dom, lbl in (("rfc9110.org", "RFC 9110 Executive Briefs"), ("rfc9111.io", "RFC 9111 Executive Briefs")):
        r_idx = "\n".join(rfc_rows[dom]) or "- *Executive briefs populate automatically when `_posts/_briefs/` entries match this RFC pillar.*"
        _write_bimodal(sroot / dom / "briefs", lbl, f"Buttoned-up architectural specifications and wire audits for {dom}.", "Updated Live", f"https://{dom}/briefs/", f'<a href="/">← {dom} Home</a> &middot; <a href="index.md">Raw Markdown (RFC 9110)</a>', "", "", r_idx)
    leaks = sum(1 for f in sroot.rglob("*") if f.is_file() and re.search(r"mikelev\.in", f.read_text(encoding="utf-8"), re.IGNORECASE))
    res = {"sunpug": len(sp_rows), "rfc9110": len(rfc_rows["rfc9110.org"]), "rfc9111": len(rfc_rows["rfc9111.io"]), "upstream_leaks": leaks, "stage_root": str(sroot)}
    if verbose:
        print(f"🌐 Downstream Sieve staged ({sroot}): SunPug={res['sunpug']} [2], RFC9110={res['rfc9110']} [1], RFC9111={res['rfc9111']} [1], upstream_leaks={leaks}.")
    return res


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync 3-2-1 Progressive Good-Read Editions.")
    common.add_standard_arguments(parser)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    sync_good_read_editions(args.target, common.get_target_path(args), verbose=args.verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
