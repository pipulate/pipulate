#!/usr/bin/env python3
"""dots_extract.py — Dual-Head Idea-Refinery Harvester & Anti-Astronaut Scoreboard."""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import articleizer
import common
import norma_extract

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
_IDEAS_BLK_RE = re.compile(
    r"(?m)^---\s*BEGIN IDEAS TO CAPTURE\s*---[ \t]*\n([\s\S]{1,12000}?)\n---\s*END IDEAS TO CAPTURE\s*---[ \t]*$"
)
_NEXT_STEPS_RE = re.compile(
    r"(?im)^#{2,4}[ \t]+Next[- ]Step Prompts?\b[^\n]*\n([\s\S]{1,4000}?)(?=\n#{1,4}[ \t]+|\n\{%\s*endraw\s*%\}|\Z)"
)
_STOPWORDS = frozenset({
    "about", "after", "again", "against", "articles", "before", "between", "build",
    "check", "clean", "command", "context", "create", "default", "every", "files",
    "first", "into", "lines", "local", "model", "models", "never", "other", "output",
    "patch", "posts", "print", "prints", "probe", "prompt", "prompts", "python",
    "script", "scripts", "should", "single", "state", "their", "there", "these",
    "thing", "things", "through", "under", "using", "where", "which", "while", "without",
})


def _tokenize_topics(texts: list[str]) -> set[str]:
    blob = " ".join(texts).lower()
    return {t for t in re.findall(r"[a-z0-9][a-z0-9._-]{2,}", blob) if len(t) >= 4 and t not in _STOPWORDS and not t.isdigit()}


def _extract_post_seeds(md_path: Path, ctx_dir: Path, source_tag: str) -> dict:
    raw = md_path.read_text(encoding="utf-8", errors="replace")
    body = raw.split("---", 2)[2] if (raw.startswith("---") and len(raw.split("---", 2)) >= 3) else raw
    info = norma_extract._read_header_and_preview(md_path)
    title = info["meta"].get("title") or md_path.stem
    aid = common.read_article_id(md_path) or 0
    kws: list[str] = []
    shard_p = ctx_dir / f"{md_path.stem}.json"
    if shard_p.is_file():
        try:
            sh = json.loads(shard_p.read_text(encoding="utf-8"))
            kws = [str(k).strip() for k in (sh.get("kw") or []) if str(k).strip()]
        except Exception:
            kws = []
    lean_body, _ = articleizer.strip_fences(body)
    ideas = [m.group(1).strip()[:1200] for m in _IDEAS_BLK_RE.finditer(lean_body) if m.group(1).strip()]
    m_next = _NEXT_STEPS_RE.search(body)
    next_steps = m_next.group(1).strip()[:1200] if m_next else ""
    return {
        "article_id": aid, "date": md_path.name[:10], "name": md_path.name,
        "title": title, "source_tag": source_tag, "kws": kws[:5],
        "ideas": ideas, "next_steps": next_steps,
    }


def harvest_dual_heads(posts_dir: Path, forward_n: int = 2, backfill_n: int = 2) -> tuple[list[dict], list[dict]]:
    pdir = Path(posts_dir).expanduser().resolve()
    ctx_dir = pdir / "_context"
    dated = sorted([p for p in pdir.glob("*.md") if common._DATED_POST_RE.match(p.name)], key=common._post_sort_key)
    head_a_paths = list(reversed(dated[-max(1, int(forward_n)):])) if dated else []
    seen = {p.name for p in head_a_paths}
    head_a = [_extract_post_seeds(p, ctx_dir, "forward-latest") for p in head_a_paths]
    head_b: list[dict] = []
    abs_dir = pdir / norma_extract.ABSTRACTS_SUBDIR
    if abs_dir.is_dir():
        abs_sorted = sorted([p for p in abs_dir.glob("*.md") if common._DATED_POST_RE.match(p.name)], key=lambda p: p.stat().st_mtime_ns, reverse=True)
        for ap in abs_sorted:
            if len(head_b) >= backfill_n:
                break
            parent_p = pdir / ap.name
            if ap.name not in seen and parent_p.is_file():
                seen.add(ap.name)
                head_b.append(_extract_post_seeds(parent_p, ctx_dir, "norma-minted"))
    if len(head_b) < backfill_n:
        for cand in norma_extract.rank_candidates(pdir, limit=forward_n + backfill_n + 4):
            if len(head_b) >= backfill_n:
                break
            cp = Path(cand["path"])
            if cp.name not in seen and cp.is_file():
                seen.add(cp.name)
                head_b.append(_extract_post_seeds(cp, ctx_dir, "norma-up-next"))
    return head_a, head_b


def compute_scoreboard(foo_path: Path, head_a: list[dict], head_b: list[dict]) -> dict:
    fl = foo_path.read_text(encoding="utf-8", errors="replace").splitlines() if foo_path.is_file() else []
    try:
        rs = next(i for i, ln in enumerate(fl) if ln.startswith("# --- START RECEIPTS"))
        re_i = next(i for i, ln in enumerate(fl) if ln.startswith("# --- END RECEIPTS"))
        top_rec = fl[rs + 1 : min(re_i, rs + 4)]
    except StopIteration:
        top_rec = []
    axis1 = sum(ln.lower().count("discharging") + ln.count("ALL LANDED") + (1 if "pipulate commit" in ln else 0) for ln in top_rec)
    todos = [ln for ln in fl if ln.startswith("# - TODO")]
    p0_count = sum(1 for ln in todos if ", P0." in ln)
    seed_tokens = _tokenize_topics([" ".join([*it["kws"], *it["ideas"], it["next_steps"]]) for it in [*head_a, *head_b]])
    collisions = []
    for ln in todos:
        hits = sorted(t for t in seed_tokens if t in ln.lower())
        if len(hits) >= 2:
            head_lbl = ln.split(":", 1)[0].replace("# - TODO ", "").strip()
            collisions.append((len(hits), head_lbl[:72], hits[:5]))
    collisions.sort(key=lambda x: (-x[0], x[1]))
    axis2 = len(collisions)
    verdict = "OPEN_FOR_MERGES_AND_SPARKS" if (axis1 + axis2) > 0 else "HOLD_NET_ZERO"
    return {"axis1": axis1, "axis2": axis2, "open_todos": len(todos), "p0_todos": p0_count, "verdict": verdict, "collisions": collisions[:6]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dual-Head Idea-Refinery Harvester (`dots`).")
    common.add_standard_arguments(parser)
    parser.add_argument("-f", "--forward", type=int, default=2, help="Newest _posts/*.md count for Head A (default: 2).")
    parser.add_argument("-b", "--backfill", type=int, default=2, help="Retrograde _abstracts/ count for Head B (default: 2).")
    parser.add_argument("--radar", action="store_true", help="Compact terminal summary without full seed bodies.")
    parser.add_argument("--repo-root", type=str, default=str(DEFAULT_REPO_ROOT), help="Repo root containing foo_files.py.")
    args = parser.parse_args(argv)
    targets = common.load_targets()
    tcfg = targets.get(str(args.target), {"path": common.resolve_default_posts_dir()})
    pdir = Path(tcfg["path"]).expanduser().resolve()
    head_a, head_b = harvest_dual_heads(pdir, forward_n=args.forward, backfill_n=args.backfill)
    sb = compute_scoreboard(Path(args.repo_root).expanduser().resolve() / "foo_files.py", head_a, head_b)
    print(f"# 🔵 DOTS DUAL-HEAD IDEA REFINERY — Verdict: {sb['verdict']}")
    print(f"# ⚖️  Two-Axis Goodhart Scoreboard: Axis1(Discharged)={sb['axis1']} | Axis2(Collisions)={sb['axis2']} | Open_TODOs={sb['open_todos']} (P0={sb['p0_todos']})")
    for cnt, lbl, kws in sb["collisions"]:
        print(f"  • [overlap={cnt}] {lbl} <- ({', '.join(kws)})")
    for label, items in (("Forward Head A (! latest)", head_a), ("Retrograde Head B (norma cones)", head_b)):
        print(f"\n## {label}")
        for it in items:
            print(f"- #{it['article_id']} [{it['date']} | {it['source_tag']}] {it['title']} | kw=({', '.join(it['kws'])})")
            if not args.radar:
                for blk in it["ideas"]:
                    print(f"  [IDEAS_BLOCK]:\n{blk}")
                if it["next_steps"]:
                    print(f"  [NEXT_STEP_PROMPTS]:\n{it['next_steps']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
