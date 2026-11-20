#!/usr/bin/env python3
"""
norma_extract.py — The Pinball Plunger for Norma Centroid Storytime Extractions.

Unties the Jukebox Coin nested-dependency knot in two plain-Python steps:
  1. CANDIDATE RADAR: Scans `_posts/` + `_posts/_context/*.json` shards to rank
     un-minted articles (#1..#N) against the Three Commercial Pillars:
       • RFC_9110 : Section 12 HTTP Content Negotiation (`Accept: text/markdown`)
       • RFC_9111 : Bimodal CDN Edge Caching (`Vary: Accept`, ADNS/O2O, 3-Hop Web)
       • SUNPUG   : `sunpug.io` Self-Replicating Nix/Python/vim/git Workbench
  2. PINBALL PLUNGER: Strips bulky code diffs via `articleizer.strip_fences()`,
     assembles a clipboard-ready 900–1,200 word 3-Voice Socratic Puppet-Theater
     extraction prompt (`Norma Centroid` intro/headings + `**Me**:` / `**Gemini**:`
     parable turns + Kuhnian below-the-fold trapdoor), and saves validated masters
     into `_posts/_abstracts/<YYYY-MM-DD-slug>.md` (the single source projected to
     Honeybot Storytime and `SunPug.io`).
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import articleizer
import common

STORYTIME_MIN_WORDS = 900
STORYTIME_MAX_WORDS = 1200

PILLAR_TERMS = {
    "RFC_9110": (
        "rfc 9110",
        "content negotiation",
        "text/markdown",
        "accept: text/markdown",
        "markdown feed",
        "section 12",
    ),
    "RFC_9111": (
        "rfc 9111",
        "vary: accept",
        "edge caching",
        "bimodal",
        "cloudflare o2o",
        "authoritative dns",
        "adns",
        "three-hop",
        "3-hop",
    ),
    "SUNPUG": (
        "sunpug",
        "von neumann",
        "magic cookie",
        "nix flake",
        "install.sh",
        "local-first",
        "reproducible",
    ),
}

_KV_RE = re.compile(r"^([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$")
_RAW_LIQUID_RE = re.compile(r"^\s*\{%\s*(?:raw|endraw)\s*%\}\s*$", re.MULTILINE)
_WEEBO_CUE_RE = re.compile(r"\[\[\[weebo:([^\]]+)\]\]\]", re.IGNORECASE)
ABSTRACTS_SUBDIR = "_abstracts"
_TICKER_STOPWORDS = frozenset({
    "THE", "A", "AN", "AND", "OR", "BUT", "FOR", "NOR", "ON", "AT", "TO", "FROM",
    "BY", "WITH", "IN", "OF", "INTO", "OVER", "AFTER", "UNDER", "HOW", "WHY", "WHAT",
    "WHEN", "WHERE", "WHO", "YOUR", "OUR", "MY", "THIS", "THAT", "IS", "ARE", "WAS",
    "WERE", "BE", "IT", "ITS", "AS", "VS", "VIA", "KILL", "KILLING", "KILLS", "RETIRE",
    "RETIRING", "AUTOMATED", "BUILDING", "MAKING", "USING", "TURNING",
})


def derive_ticker_tag(meta: dict, title: str = "", slug: str = "", max_chars: int = 18) -> str:
    """Resolve a <=18-char 1-2 word uppercase LED ticker topic tag from frontmatter or slug/title."""
    explicit = str((meta or {}).get("ticker_tag") or "").strip().upper()
    explicit = " ".join(re.sub(r"[^A-Z0-9 ./+&:#!?'-]+", " ", explicit).split())
    if explicit:
        return explicit[:max_chars].rstrip()
    src = (slug or "").split("/")[-1].replace("-", " ") or title
    toks = [t.upper() for t in re.findall(r"[A-Za-z0-9]+", src) if t.upper() not in _TICKER_STOPWORDS]
    if not toks:
        return "STORY-TIME"
    if len(toks) >= 2 and len(f"{toks[0]} {toks[1]}") <= max_chars:
        return f"{toks[0]} {toks[1]}"
    return toks[0][:max_chars]


def _enrolled_weebo_stems(limit: int = 16) -> list[str]:
    """Return enrolled local Weebo shorthand stems so the AI Editor can reuse existing assets."""
    scripts_dir = str(Path(__file__).resolve().parents[1])
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        import weebo
        stems = []
        for lbl, p in weebo.list_shorthand_assets(limit=limit):
            s = "seal" if lbl.startswith("seal ") else p.stem
            if s not in stems:
                stems.append(s)
        return stems or ["seal"]
    except Exception:
        return ["seal"]


def extract_weebo_cues(text: str) -> list[tuple[str, str]]:
    """Extract (stem, duration_s) tuples from inline `[[[weebo:stem[:sec]]]]` cues in Markdown body."""
    body = text.split("\n---\n", 1)[1] if text.startswith("---\n") and "\n---\n" in text[4:] else text
    cues = []
    for raw_spec in _WEEBO_CUE_RE.findall(body):
        spec = raw_spec.strip()
        stem, dur = spec.rsplit(":", 1) if ":" in spec else (spec, "2.5")
        cues.append((stem.strip(), dur.strip() or "2.5"))
    return cues


def extract_weebo_brief(meta: dict, body_text: str = "") -> list[dict]:
    """Combine inline `[[[weebo:...]]]` cues and `weebo_N_*` frontmatter keys with local enrollment status."""
    enrolled_low = {s.lower() for s in _enrolled_weebo_stems(limit=100)}
    cues = extract_weebo_cues(body_text)
    n_slots = max(len(cues), 2 if (meta or {}).get("weebo_1_search") or (meta or {}).get("weebo_2_search") else 0)
    rows = []
    for idx in range(n_slots):
        slot = idx + 1
        stem, dur = cues[idx] if idx < len(cues) else ("", "2.5")
        if not stem:
            parsed = extract_weebo_cues(str((meta or {}).get(f"weebo_{slot}_cue") or ""))
            if parsed:
                stem, dur = parsed[0]
        if not stem:
            continue
        rows.append({
            "slot": slot,
            "phase": "PRE-BREAK" if slot == 1 else ("POST-BREAK" if slot == 2 else f"CUE-{slot}"),
            "cue": f"[[[weebo:{stem}:{dur}]]]",
            "stem": stem,
            "duration": dur,
            "kind": str((meta or {}).get(f"weebo_{slot}_kind") or "blip_meme").strip(),
            "search": str((meta or {}).get(f"weebo_{slot}_search") or "").strip(),
            "enrolled": stem.lower() in enrolled_low,
        })
    return rows


def format_weebo_brief_report(brief_rows: list[dict], article_id: int | None = None) -> str:
    """Format operator search queries and `weeboh` staging commands for a parable's Weebo cues."""
    if not brief_rows:
        return ""
    lines = [f"🤖 Operation Weebo Sourcing Brief (#{article_id or '?'})"]
    for r in brief_rows:
        st = "✅ ENROLLED" if r["enrolled"] else f"🔎 STAGE -> weeboh ~/Downloads/{r['stem']}.png {r['duration']}"
        lines.append(f"   • [{r['phase']} | {r['kind']}] {r['cue']} ({st})")
        if r["search"]:
            lines.append(f"     ↳ Search: {r['search']}")
    return "\n".join(lines)


def abstract_path_for_post(md_path: Path) -> Path:
    """Return the 1-to-1 `_posts/_abstracts/<YYYY-MM-DD-slug>.md` master path."""
    p = Path(md_path).expanduser().resolve()
    return p.parent / ABSTRACTS_SUBDIR / p.name


def _read_header_and_preview(md_path: Path) -> dict:
    """Stream YAML frontmatter + a 2 KB body preview without parsing full posts."""
    meta = {}
    body_preview = ""
    has_fm = False
    try:
        with open(md_path, "r", encoding="utf-8", errors="replace") as f:
            if f.readline().strip() == "---":
                for line in f:
                    if line.strip() == "---":
                        has_fm = True
                        break
                    m = _KV_RE.match(line.rstrip("\r\n"))
                    if m and m.group(1) not in meta:
                        meta[m.group(1)] = m.group(2).strip().strip("'\"")
                if has_fm:
                    body_preview = f.read(2048)
    except OSError:
        pass
    return {"has_fm": has_fm, "meta": meta, "body_preview": body_preview}


def score_pillars(title_text: str, meta_text: str) -> tuple[int, list[str]]:
    """Score text against the 3 commercial pillars; return (score, matched_pillars)."""
    t_low = (title_text or "").lower()
    m_low = (meta_text or "").lower()
    matched = []
    score = 0
    for pillar, terms in PILLAR_TERMS.items():
        t_hits = sum(1 for term in terms if term in t_low)
        m_hits = sum(1 for term in terms if term in m_low)
        if t_hits or m_hits:
            matched.append(pillar)
            score += (t_hits * 3) + (m_hits * 2)
    if len(matched) == 2:
        score += 4
    elif len(matched) == 3:
        score += 8
    return score, matched


def rank_candidates(posts_dir: Path, limit: int = 10, pillars_only: bool = False) -> list[dict]:
    """Return un-minted Storytime backfill candidates (newest-first by default, or 3-Pillar ranked)."""
    pdir = Path(posts_dir).expanduser().resolve()
    if not pdir.is_dir():
        return []
    ctx_dir = pdir / "_context"
    candidates = []
    for fname in sorted(os.listdir(pdir)):
        if not common._DATED_POST_RE.match(fname):
            continue
        md_path = pdir / fname
        info = _read_header_and_preview(md_path)
        if not info["has_fm"]:
            continue
        meta = info["meta"]
        if meta.get("jukebox_coin", "").lower() in ("true", "yes", "1"):
            continue
        if meta.get("aside", "").lower() in ("true", "yes", "1"):
            continue
        if meta.get("storytime", "").lower() in ("false", "no", "0", "off", "aside"):
            continue
        if abstract_path_for_post(md_path).is_file():
            continue
        raw_aid = meta.get(common.ARTICLE_ID_KEY, "").split("#", 1)[0].strip()
        aid = int(raw_aid) if raw_aid.isdigit() and int(raw_aid) > 0 else 0
        if aid == 911:
            continue
        stem = md_path.stem
        slug = stem[11:] if len(stem) > 11 else stem
        title = meta.get("title") or slug
        shard_blob = ""
        shard_path = ctx_dir / f"{stem}.json"
        if shard_path.is_file():
            try:
                sh = json.loads(shard_path.read_text(encoding="utf-8"))
                shard_blob = " ".join([
                    str(sh.get("s") or ""),
                    " ".join(sh.get("kw") or []),
                    " ".join(sh.get("sub") or []),
                ])
            except Exception:
                shard_blob = ""
        meta_blob = " ".join([
            shard_blob,
            meta.get("meta_description", ""),
            meta.get("meta_keywords", ""),
            meta.get("description", ""),
            info["body_preview"] if not shard_blob else "",
        ])
        score, pillars = score_pillars(title, meta_blob)
        if pillars_only and score <= 0:
            continue
        candidates.append({
            "article_id": aid,
            "score": score,
            "pillars": pillars,
            "date": fname[:10],
            "slug": slug,
            "title": title,
            "path": str(md_path),
        })
    if pillars_only:
        candidates.sort(key=lambda c: (-c["score"], -c["article_id"], c["slug"]))
    else:
        candidates.sort(key=lambda c: (c["date"], c["article_id"], c["slug"]), reverse=True)
    return candidates[: max(1, int(limit))]


def build_extraction_prompt(md_path: Path) -> dict:
    """Strip code fences and build the Norma Centroid Storytime extraction prompt."""
    path = Path(md_path).expanduser().resolve()
    raw = path.read_text(encoding="utf-8", errors="replace")
    fm_block, body = "", raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            fm_block, body = parts[1], parts[2]
    aid = common.read_article_id(path) or 0
    info = _read_header_and_preview(path)
    title = info["meta"].get("title") or path.stem
    permalink = info["meta"].get("permalink") or f"/futureproof/{path.stem[11:]}/"
    clean_body = _RAW_LIQUID_RE.sub("", body).strip()
    lean_body, fences_stripped = articleizer.strip_fences(clean_body)
    _, pillars = score_pillars(title, f"{fm_block}\n{lean_body[:4000]}")
    suggested_tag = derive_ticker_tag(info["meta"], title=title, slug=path.stem[11:])
    enrolled_hint = ", ".join(_enrolled_weebo_stems(limit=12))
    coin_cmd = str(aid) if aid else "<ID>"
    canon_url = "https://" + f"mikelev.in{permalink}"
    sunpug_cmd = "curl -fsSL https://" + "sunpug.io | less"
    prompt = (
        "You are crafting a SEED-GROUNDED 3-VOICE SOCRATIC PUPPET-THEATER ABSTRACT\n"
        "for Honeybot YouTube Storytime and the newcomer-facing SunPug.io blog.\n"
        "Do NOT copy or summarize the author's raw workshop rambling verbatim, and do\n"
        "NOT write a single-voice monologue. Use the primary lab receipt below as your\n"
        "factual seed to write BRAND-NEW, entertaining, plain-English Socratic dialogue\n"
        "with a clear parable/moral for smart newcomers in the middle of the bell curve.\n\n"
        f"SOURCE ARTICLE: #{aid} — {title}\n"
        f"CANONICAL LAB RECEIPT: {canon_url}\n"
        f"OPTIONAL PILLAR HOOKS: {', '.join(pillars) or 'GENERAL_GOOD_READ (philosophy, craft, or systems parable)'}\n\n"
        "NORMA CENTROID 'GOOD READ' FILTER (ARCHAEOLOGIST FROM THE FUTURE — ZERO WASTED SYLLABLES):\n"
        "- An article does NOT need to be about RFC 9110, RFC 9111, or SunPug to earn a Jukebox Coin.\n"
        "  ANY genuine discovery, engineering reversal, craft lesson, or philosophical insight that makes\n"
        "  a compelling, memorable YouTube Storytime episode for a smart newcomer ('Normie') qualifies.\n"
        "- Zero wasted syllables: translate insider jargon, strip internal repo plumbing, and earn every\n"
        "  sentence with curiosity, clarity, and Norma's sawtooth 'And then the surprising thing the\n"
        "  author did...' momentum. When RFC 9110, RFC 9111, or SunPug ARE naturally present in the seed,\n"
        "  connect them plainly; when they are not, let the article's true human story stand on its own.\n"
        "- Only if the post is pure housekeeping/changelog noise with zero human parable, reply ONLY:\n"
        f"SKIP_CANDIDATE #{aid}: <one-sentence reason>\n\n"
        "3-VOICE PUPPET-THEATER MARKDOWN CONTRACT (ENCLOSE ENTIRE REPLY IN ONE ```markdown FENCE):\n"
        f"- Total spoken length: strictly {STORYTIME_MIN_WORDS}–{STORYTIME_MAX_WORDS} words (~6–8 min between 20-min breaks).\n"
        "- Zero fenced code blocks and zero unexplained internal repo filenames inside the story.\n"
        "- Start with YAML frontmatter (`title`, `article_id: " + f"{aid}`, `ticker_tag: \"{suggested_tag}\"` [or a sharper 1–2 word uppercase topic <=18 chars], `jukebox_coin: true`, `source_url: {canon_url}`, `layout: post`, plus the 6 single-line double-quoted `weebo_1_*` / `weebo_2_*` sourcing keys below using single quotes inside strings).\n"
        "- OPERATION WEEBO (2 VISUAL BLIP / PORTRAIT CUES — 1 PRE-INTERMISSION, 1 POST-INTERMISSION):\n"
        "  Honeybot airs a Midpoint Showcase intermission halfway through each episode, and pops frameless\n"
        "  X11 overlays over the HUD without interrupting speech whenever it hits a standalone `[[[weebo:<slug>:<sec>]]]` line.\n"
        "  Place EXACTLY 2 standalone `[[[weebo:<slug>:<sec>]]]` lines (blank line above and below, never inline in a sentence):\n"
        "    1. Pre-Intermission Cue #1 (in Act 1–2, BEFORE midpoint): `[[[weebo:<pre-slug>:<sec>]]]`\n"
        "    2. Post-Intermission Cue #2 (in Act 3–4, AFTER midpoint): `[[[weebo:<post-slug>:<sec>]]]`\n"
        "  Choose the sharpest Content-ID-safe visual archetype for each beat (enrolled local stems if fitting: " + f"{enrolled_hint}; else mint descriptive kebab-case slugs):\n"
        "    • `blip_meme` (1.8–2.5s silent): 1997 *Flubber* 'Weebo' barely-a-blip visual pun or reaction ('did I just see that?'\n"
        "      transformative fair-use / public-domain / Prelinger / Wikimedia / silent-era gag — zero copyrighted audio).\n"
        "    • `literal_photo` (3.5–5.0s PNG/JPEG): Real human builders or historical artifacts behind the ideas — e.g. when\n"
        "      RFC 9110 or RFC 9111 is discussed, feature the 3 IETF HTTP specification authors: Roy Fielding, Mark Nottingham,\n"
        "      and Julian Reschke (`[[[weebo:rfc-authors-trio:4.5]]]`), or inventors/patents named in the seed (Margaret E. Knight,\n"
        "      Norbert Wiener, Claude Shannon, Wilbur & Orville Wright's 1901 wind-tunnel balance).\n"
        "  Record your sourcing brief in YAML frontmatter (single-line double-quoted strings, never spoken aloud):\n"
        "    `weebo_1_cue: \"[[[weebo:<pre-slug>:<sec>]]]\"`, `weebo_1_kind: \"blip_meme|literal_photo\"`, `weebo_1_search: \"<2-3 exact Wikimedia/Prelinger/image search queries + comedic/pedagogical beat>\"`\n"
        "    `weebo_2_cue: \"[[[weebo:<post-slug>:<sec>]]]\"`, `weebo_2_kind: \"literal_photo|blip_meme\"`, `weebo_2_search: \"<2-3 exact search queries (e.g. 'Roy Fielding' 'Mark Nottingham' 'Julian Reschke' IETF HTTP) + beat>\"`\n"
        "- Prologue (`## Setting the Stage: Context for the Curious Book Reader`): 1–2 short paragraphs\n"
        "  spoken by NORMA CENTROID (16,000 Hz narrator) framing the everyday human stakes.\n"
        "- Body (`## Technical Journal Entry Begins` + 3–4 `## ` Act Headings also read by NORMA CENTROID):\n"
        "  Alternate crisp Socratic turns using ONLY these exact speaker prefixes at column 0:\n"
        "    • `**Me**:` (Stage Left — Mike-E the Apprentice @ 19,200 Hz: voices the curious newcomer's\n"
        "      grounded questions, pushback, and practical 'so what does this mean for my work?' stakes).\n"
        "    • `**Gemini**:` (Stage Right — Shipmunk O'Theseus! @ 22,050 Hz: answers with vivid parables,\n"
        "      the real surprise/receipt from the lab session proving Shannon surprisal over zero-bit mush,\n"
        "      and—under a Below-the-Fold heading—the pre-registered Kuhnian Gatekeeper Trapdoor naming\n"
        "      the predictable knee-jerk dismissal and its plain-spoken refutation).\n"
        f"- Final turn: land the parable's takeaway cleanly (weaving `{sunpug_cmd}` or RFC 9110/9111\n"
        f"  only when natural), link Lab Receipt #{aid} ({canon_url}), and invite viewers to type `{coin_cmd}` (or `MENU`) in live chat to play this story.\n\n"
        "--- SOURCE ARTICLE (CODE FENCES CONDENSED) ---\n"
        f"{lean_body}\n"
        "--- END SOURCE ARTICLE ---\n"
    )
    return {
        "article_id": aid,
        "title": title,
        "pillars": pillars,
        "fences_stripped": fences_stripped,
        "abstract_path": str(abstract_path_for_post(path)),
        "prompt": prompt,
    }


def save_abstract_for_post(md_path: Path, raw_text: str) -> dict:
    """Validate 3-voice Socratic puppet-theater structure, write `_posts/_abstracts/<name>`, and stamp coin."""
    path = Path(md_path).expanduser().resolve()
    text = (raw_text or "").replace("\r\n", "\n").strip()
    m_fence = re.match(r"^(`{3,})[a-zA-Z0-9_-]*\n([\s\S]*?)\n\1\s*$", text) or re.search(r"(`{3,})[a-zA-Z0-9_-]*\n(---\n[\s\S]*?)\n\1", text)
    if m_fence:
        text = m_fence.group(2).strip()
    missing = [
        lbl for lbl, ok in (
            ("YAML frontmatter", text.startswith("---\n") and "\n---\n" in text[4:]),
            ("## Setting the Stage heading", "## Setting the Stage" in text),
            ("**Me**: turn", bool(re.search(r"^\*\*Me\*\*:", text, re.MULTILINE))),
            ("**Gemini**: turn", bool(re.search(r"^\*\*Gemini\*\*:", text, re.MULTILINE))),
        )
        if not ok
    ]
    if missing:
        return {"ok": False, "error": f"Missing required 3-voice puppet-theater element(s): {', '.join(missing)}"}
    dest = abstract_path_for_post(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    aid = common.read_article_id(path)
    if aid:
        common.stamp_frontmatter_value(dest, common.ARTICLE_ID_KEY, str(aid), preserve_mtime=False)
    dest_meta = _read_header_and_preview(dest)["meta"]
    parent_meta = _read_header_and_preview(path)["meta"]
    t_tag = derive_ticker_tag(
        {**parent_meta, **dest_meta},
        title=dest_meta.get("title") or parent_meta.get("title") or "",
        slug=path.stem[11:],
    )
    common.stamp_frontmatter_value(dest, "ticker_tag", f'"{t_tag}"', preserve_mtime=False)
    coin_st = common.stamp_frontmatter_value(path, "jukebox_coin", "true", preserve_mtime=True)
    body_only = text.split("\n---\n", 1)[1] if text.startswith("---\n") and "\n---\n" in text[4:] else text
    spoken_body = _WEEBO_CUE_RE.sub("", body_only)
    words = len(re.findall(r"\b\w+\b", spoken_body))
    w_cues = extract_weebo_cues(text)
    w_brief = extract_weebo_brief(_read_header_and_preview(dest)["meta"], text)
    return {"ok": True, "abstract_path": str(dest), "coin_status": coin_st, "words": words, "article_id": aid, "ticker_tag": t_tag, "weebo_cues": w_cues, "weebo_brief": w_brief}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Norma Centroid Newest-First Storytime Backfill & Plunger.")
    common.add_standard_arguments(parser)
    parser.add_argument("-s", "--slug", type=str, default=None, help="Post #ID (e.g. #1652) or slug substring.")
    parser.add_argument("-n", "--next", "--best", dest="best", action="store_true", help="Pull the plunger on the newest un-minted post (or #1 with --pillars).")
    parser.add_argument("--pillars", action="store_true", help="Filter and rank strictly by 3-Pillar commercial score instead of newest-first backfill.")
    parser.add_argument("--limit", type=int, default=10, help="Number of backfill candidates to display (default: 10).")
    parser.add_argument("--copy", action="store_true", help="Copy the assembled extraction prompt to the clipboard.")
    parser.add_argument("--save-clipboard", action="store_true", help="Validate & save Socratic abstract from clipboard into `_posts/_abstracts/` + stamp coin.")
    parser.add_argument("--weebo", action="store_true", help="Inspect Weebo cues, search brief, & local enrollment for a saved Storytime abstract.")
    parser.add_argument("--stamp-coin", action="store_true", help="Stamp `jukebox_coin: true` on -s <post>.")
    parser.add_argument("extra", nargs="*", help="Optional subcommand (`weebo [#ID]`).")
    args = parser.parse_args(argv)
    if args.extra and args.extra[0].lower() in ("weebo", "brief"):
        args.weebo = True
        if len(args.extra) > 1 and not args.slug:
            args.slug = args.extra[1]

    posts_dir = common.get_target_path(args)
    if args.weebo:
        abs_dir = posts_dir / ABSTRACTS_SUBDIR
        if args.slug:
            post_p, _ = common._latest_post_for_target(args.target, slug_match=args.slug)
            abs_p = abstract_path_for_post(post_p) if post_p else None
        else:
            abs_files = sorted(abs_dir.glob("*.md")) if abs_dir.is_dir() else []
            abs_p = abs_files[-1] if abs_files else None
        if not abs_p or not abs_p.is_file():
            print("⚠️ No saved `_posts/_abstracts/` file matched for Weebo inspection.")
            return 1
        raw_abs = abs_p.read_text(encoding="utf-8", errors="replace")
        meta_abs = _read_header_and_preview(abs_p)["meta"]
        brief = extract_weebo_brief(meta_abs, raw_abs)
        print(format_weebo_brief_report(brief, common.read_article_id(abs_p)) or f"ℹ️  No `[[[weebo:...]]]` cues found in {abs_p.name}.")
        return 0
    if args.stamp_coin:
        if not args.slug:
            print("❌ Pass `-s #<article_id>` (or slug) with `--stamp-coin`.")
            return 1
        post_p, _ = common._latest_post_for_target(args.target, slug_match=args.slug)
        if not post_p:
            print(f"❌ No post matched {args.slug!r}.")
            return 1
        st = common.stamp_frontmatter_value(post_p, "jukebox_coin", "true", preserve_mtime=True)
        print(f"🪙 [{st}] Stamped jukebox_coin: true on {post_p.name} (#{common.read_article_id(post_p)}).")
        return 0

    if args.save_clipboard:
        clip_raw = articleizer.clipboard_paste()
        slug_q = args.slug
        if not slug_q:
            m_aid = re.search(r"(?m)^article_id\s*:\s*['\"]?([1-9]\d*)['\"]?\s*$", clip_raw or "")
            if m_aid:
                slug_q = f"#{m_aid.group(1)}"
        if not slug_q:
            print("❌ Pass `-s #<article_id>` (or include `article_id:` in clipboard YAML) with `--save-clipboard`.")
            return 1
        post_p, _ = common._latest_post_for_target(args.target, slug_match=slug_q)
        if not post_p or not post_p.is_file():
            print(f"❌ No post matched {slug_q!r}.")
            return 1
        res = save_abstract_for_post(post_p, clip_raw)
        if not res["ok"]:
            print(f"❌ Refused abstract for {post_p.name}: {res['error']}")
            return 1
        print(f"🎭 Saved 3-voice Socratic abstract ({res['words']} words, ticker_tag={res.get('ticker_tag')!r}, weebo_cues={len(res.get('weebo_cues', []))}) -> {res['abstract_path']} & [{res['coin_status']}] jukebox_coin on #{res['article_id']}!")
        if res.get("weebo_brief"):
            print(format_weebo_brief_report(res["weebo_brief"], res["article_id"]))
        nxt = rank_candidates(posts_dir, limit=1, pillars_only=args.pillars)
        if nxt:
            print(f"⏭️  Next un-minted in queue: #{nxt[0]['article_id']} ({nxt[0]['date']}) — {nxt[0]['title']}")
        return 0

    if not args.slug and not args.best:
        rows = rank_candidates(posts_dir, limit=args.limit, pillars_only=args.pillars)
        mode_lbl = "3-Pillar Radar" if args.pillars else "Newest-First Backfill Queue"
        print(f"🎯 Norma Centroid {mode_lbl} (Top {len(rows)} un-minted in {posts_dir}):")
        for idx, r in enumerate(rows, 1):
            p_tag = "+".join(r["pillars"]) or "GOOD_READ"
            print(f"  {idx:2d}. #{r['article_id']:<4d} [{r['date']} | {p_tag:<24s}] {r['title']}")
            print(f"       ↳ Plunger: .venv/bin/python scripts/articles/norma_extract.py -s #{r['article_id']} --copy")
        return 0

    if args.best and not args.slug:
        top = rank_candidates(posts_dir, limit=1, pillars_only=args.pillars)
        if not top:
            print("⚠️ No un-minted Storytime candidates found.")
            return 1
        post_p = Path(top[0]["path"])
    else:
        post_p, _ = common._latest_post_for_target(args.target, slug_match=args.slug)
    if not post_p or not post_p.is_file():
        print(f"❌ No post matched {args.slug!r}.")
        return 1

    pkt = build_extraction_prompt(post_p)
    est_tok = int(len(pkt["prompt"]) / 3.5)
    print(
        f"🎰 Pinball Plunger Pulled: #{pkt['article_id']} {pkt['title']!r} | "
        f"pillars={pkt['pillars']} | fences_stripped={pkt['fences_stripped']} | "
        f"prompt={len(pkt['prompt']):,} chars (~{est_tok:,} tok)"
    )
    if args.copy:
        articleizer.clipboard_copy(pkt["prompt"])
        print("📋 Norma Centroid extraction prompt copied to clipboard! Paste into Gemini in your browser.")
    else:
        print("💡 Add `--copy` to put this extraction prompt straight onto your clipboard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
