#!/usr/bin/env python3
"""dots_extract.py — Tri-Head Idea-Refinery Harvester & Anti-Astronaut Scoreboard."""

import argparse
from collections import Counter
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
    "about", "above", "across", "active", "activating", "added", "after", "again", "against",
    "along", "alongside", "already", "also", "always", "article", "articles", "audit", "back",
    "before", "being", "below", "between", "blog", "blogs", "both", "bottom", "build", "builds",
    "built", "call", "candidates", "capture", "check", "clean", "cleanly", "clear", "code",
    "command", "commands", "commit", "compile", "config", "context", "copy", "count", "counts",
    "create", "current", "data", "date", "days", "default", "delete", "does", "done", "down",
    "drop", "each", "edit", "empty", "every", "exact", "existing", "exit", "exits", "false",
    "file", "files", "filter", "find", "first", "flag", "flags", "float", "from", "full", "gate",
    "gates", "give", "good", "hand", "have", "head", "here", "high", "hold", "human", "into",
    "item", "items", "join", "joining", "json", "just", "keep", "keys", "land", "landed", "lands",
    "last", "latest", "left", "less", "line", "lines", "link", "list", "live", "load", "local",
    "long", "loop", "make", "mode", "model", "models", "more", "most", "move", "must", "name",
    "names", "need", "needs", "never", "next", "none", "nothing", "once", "only", "open", "order",
    "other", "output", "over", "owed", "page", "pages", "pair", "pass", "past", "patch", "path",
    "paths", "place", "plain", "plus", "post", "posts", "print", "prints", "probe", "probes",
    "prompt", "prompts", "public", "pull", "pulls", "push", "python", "queue", "read", "reads",
    "ready", "real", "recent", "remove", "render", "replace", "repo", "repos", "report", "return",
    "root", "rule", "rules", "runs", "safe", "same", "save", "script", "scripts", "search", "seed",
    "seeds", "seen", "self", "send", "shell", "ship", "short", "should", "show", "shows", "side",
    "single", "site", "sites", "skip", "slug", "slugs", "some", "sort", "source", "split", "stage",
    "start", "state", "static", "stay", "step", "steps", "still", "stop", "stops", "store", "strip",
    "sync", "system", "table", "take", "target", "test", "tests", "text", "than", "that", "their",
    "them", "then", "there", "these", "they", "thing", "things", "this", "three", "through",
    "tighten", "time", "title", "todo", "todos", "token", "tokens", "tool", "tools", "track",
    "tracked", "tree", "true", "turn", "turns", "type", "under", "until", "update", "updated",
    "used", "user", "uses", "using", "value", "values", "verify", "view", "wait", "when", "where",
    "which", "while", "window", "wire", "wired", "with", "within", "without", "word", "words",
    "work", "working", "wrap", "write", "writes", "zero",
})
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*")
_NOISE_TOKEN_RE = re.compile(r"^(?:\d[\d._/-]*|p0\.\d+[a-z]?|[0-9a-f]{7,40})$")
_ALLOW_SHORT = frozenset({"o2o", "gsc", "ast", "tts", "wal", "idf"})
_PILLAR_PHRASES = frozenset({"rfc 9110", "rfc 9111", "rfc 9421", "nix flakes", "content negotiation", "edge caching", "911 llm optics"})


def _tokenize_topics(texts: list[str]) -> set[str]:
    blob, out = " ".join(texts).lower(), set()
    for raw in _TOKEN_RE.findall(blob):
        for tok in (raw, *(p for p in raw.split("/") if p)):
            t = tok.strip("._-")
            if (len(t) >= 4 or t in _ALLOW_SHORT) and t not in _STOPWORDS and not _NOISE_TOKEN_RE.match(t):
                out.add(t)
    return out


def _extract_post_seeds(md_path: Path, ctx_dir: Path, source_tag: str) -> dict:
    raw = md_path.read_text(encoding="utf-8", errors="replace")
    body = raw.split("---", 2)[2] if (raw.startswith("---") and len(raw.split("---", 2)) >= 3) else raw
    info = norma_extract._read_header_and_preview(md_path)
    title = info["meta"].get("title") or md_path.stem
    aid = common.read_article_id(md_path) or 0
    kws: list[str] = []
    shard_summary = ""
    shard_p = ctx_dir / f"{md_path.stem}.json"
    if shard_p.is_file():
        try:
            sh = json.loads(shard_p.read_text(encoding="utf-8"))
            kws = [str(k).strip() for k in (sh.get("kw") or []) if str(k).strip()]
            shard_summary = str(sh.get("s") or sh.get("summary") or "").strip()[:600]
        except Exception:
            kws = []
    lean_body, _ = articleizer.strip_fences(body)
    ideas = [m.group(1).strip()[:1200] for m in _IDEAS_BLK_RE.finditer(lean_body) if m.group(1).strip()]
    m_next = _NEXT_STEPS_RE.search(body)
    next_steps = m_next.group(1).strip()[:1200] if m_next else ""
    return {
        "article_id": aid, "date": md_path.name[:10], "name": md_path.name,
        "title": title, "source_tag": source_tag, "kws": kws[:5],
        "ideas": ideas, "next_steps": next_steps, "shard_summary": shard_summary,
    }


_BEGIN_ARTICLE_RE = re.compile(r"(?m)^---\s*BEGIN NEW ARTICLE\s*---[ \t]*$")
_META_PROMPT_PREFIXES = (
    "You are running THE DOTS",
    "You are running THE FORGETTING KATA",
    "If this arrived as a zip, treat",
)
_TURN_ME_RE = re.compile(r"^\*\*(?:Me|MikeLev\.in)\*\*:[ \t]*(.*)$")
_TURN_DELIV_RE = re.compile(r"^\*\*5:\s*DELIVERABLE\*\*(?:\s*\([^)\n]*\))?:[ \t]*(.*)$", re.IGNORECASE)
_TURN_STOP_RE = re.compile(
    r"^(?:\*\*(?:Gemini|Claude|ChatGPT|Grok|Shipmunk|Norma|AI|[1-4]:\s*(?:BEFORE|AFTER|CHANGE|PROMPT))\b[^*\n]*\*\*:|"
    r"##[ \t]+THE AI-EDIT METHOD\b|---\s*END\b|===\s*QA ARCHIVE SEAL\b|#\s*⚠️\s*ROUTING INVARIANT\b)",
    re.IGNORECASE,
)
_DELIV_SKIP = frozenset({
    'what does "done" look like?',
    '[what does "done" look like?]',
    '[does the after reading support your prediction?]',
})


def _strip_fences_commonmark(text: str) -> str:
    out, fence_ch, fence_len, fence_open = [], "", 0, ""
    for ln in text.splitlines():
        s = ln.strip()
        if not fence_len:
            m = re.match(r"^[ \t]*(`{3,}|~{3,})(.*)$", ln)
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                fence_ch, fence_len, fence_open = m.group(1)[0], len(m.group(1)), s
                continue
            out.append(ln)
        elif (len(s) >= fence_len and s == fence_ch * len(s)) or (fence_open and s == fence_open):
            fence_ch, fence_len, fence_open = "", 0, ""
        elif _TURN_ME_RE.match(ln) or _TURN_DELIV_RE.match(ln) or _TURN_STOP_RE.match(ln):
            fence_ch, fence_len, fence_open = "", 0, ""
            out.append(ln)
    return "\n".join(out)


def _extract_draft_seeds(prompt_path: Path, max_chars: int = 20000) -> list[dict]:
    if not prompt_path.is_file():
        return []
    raw = prompt_path.read_text(encoding="utf-8", errors="replace").strip()
    if len(raw) < 25 or raw.startswith(_META_PROMPT_PREFIXES):
        return []
    has_begin = bool(_BEGIN_ARTICLE_RE.search(raw))
    lean = _strip_fences_commonmark(_BEGIN_ARTICLE_RE.split(raw, maxsplit=1)[-1] if has_begin else raw)
    segments: list[tuple[str, str]] = []
    mode, buf = "", []
    for ln in [*lean.splitlines(), "## THE AI-EDIT METHOD"]:
        m_me, m_del = _TURN_ME_RE.match(ln), _TURN_DELIV_RE.match(ln)
        if m_me or m_del or _TURN_STOP_RE.match(ln):
            txt = "\n".join(buf).strip()
            if mode and len(txt) >= 15:
                segments.append((mode, txt))
            init_ln = m_me.group(1) if m_me else (m_del.group(1) if m_del else "")
            keep_init = [init_ln] if init_ln.strip() and init_ln.strip().lower() not in _DELIV_SKIP else []
            mode, buf = ("Me", keep_init) if m_me else (("Deliverable", keep_init) if m_del else ("", []))
        elif mode and ln.strip().lower() not in _DELIV_SKIP:
            buf.append(ln)
    source_tag = "in-flight-article"
    if not segments and not has_begin and len(lean.strip()) >= 25:
        segments, source_tag = [("Prompt", lean.strip()[:8000])], "in-flight-prompt"
    if not segments:
        return []
    total_c = sum(len(t) for _, t in segments)
    chosen = segments
    if total_c > max_chars and len(segments) > 1:
        head_s, rem, tail_s = (segments[0][0], segments[0][1][:8000]), max_chars - min(8000, len(segments[0][1])), []
        for k, t in reversed(segments[1:]):
            if rem > 0:
                tail_s.append((k, t[-rem:] if len(t) > rem else t))
                rem -= len(tail_s[-1][1])
        chosen = [head_s, *reversed(tail_s)]
    return [{
        "article_id": 0, "date": "live", "name": prompt_path.name,
        "title": f"Active Draft ({len(chosen)} segment(s), {total_c:,} chars)",
        "source_tag": source_tag, "kws": ["in-flight-draft"],
        "ideas": [f"[SEGMENT {i}/{len(chosen)} - {k}]:\n{t}" for i, (k, t) in enumerate(chosen, 1)],
        "turn_summaries": [f"Seg {i}/{len(chosen)} ({k}, {len(t):,}c): {' '.join(t.split())[:105]}" for i, (k, t) in enumerate(chosen, 1)],
        "next_steps": "", "shard_summary": "",
    }]


RETRO_CURSOR_FILE = common.CONFIG_DIR / "dots_retro_cursor.json"


def _resolve_retro_window(args: argparse.Namespace) -> tuple[int, int, str]:
    tkey = str(getattr(args, "target", "1") or "1")
    def_lbl = "norma-up-next" if tkey == "1" else "outline-unindexed"
    raw = json.loads(RETRO_CURSOR_FILE.read_text(encoding="utf-8")) if RETRO_CURSOR_FILE.is_file() else {}
    all_cur = {"1": raw} if ("offset" in raw or "next_offset" in raw) else (raw if isinstance(raw, dict) else {})
    if getattr(args, "retro_reset", False):
        all_cur.pop(tkey, None)
        RETRO_CURSOR_FILE.write_text(json.dumps(all_cur, indent=2) + "\n", encoding="utf-8") if all_cur else RETRO_CURSOR_FILE.unlink(missing_ok=True)
        return 0, args.backfill, f"reset->{def_lbl}"
    if getattr(args, "offset", 0) > 0:
        return int(args.offset), args.backfill, f"offset={int(args.offset)}"
    cur = all_cur.get(tkey) if isinstance(all_cur.get(tkey), dict) else {}
    if getattr(args, "retro", None) is not None:
        step = max(1, int(args.retro))
        off = int(cur.get("next_offset") or max(1, int(args.forward)))
        all_cur[tkey] = {"offset": off, "next_offset": off + step, "step": step}
        common.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        RETRO_CURSOR_FILE.write_text(json.dumps(all_cur, indent=2) + "\n", encoding="utf-8")
        return off, step, f"retro-step(offset={off}, step={step})"
    if cur.get("offset"):
        return int(cur["offset"]), int(cur.get("step") or args.backfill), f"retro-parked(offset={cur['offset']})"
    return 0, args.backfill, def_lbl


def harvest_dual_heads(posts_dir: Path, forward_n: int = 2, backfill_n: int = 2, retro_offset: int = 0, target_key: str = "1", outline_path: Path | None = None) -> tuple[list[dict], list[dict]]:
    pdir = Path(posts_dir).expanduser().resolve()
    ctx_dir = pdir / "_context"
    dated = sorted([p for p in pdir.glob("*.md") if common._DATED_POST_RE.match(p.name)], key=common._post_sort_key) if pdir.is_dir() else []
    newest_first = list(reversed(dated))
    head_a_paths = newest_first[: max(0, int(forward_n))] if forward_n > 0 else []
    seen = {p.name for p in head_a_paths}
    head_a = [_extract_post_seeds(p, ctx_dir, "forward-latest") for p in head_a_paths]
    head_b: list[dict] = []
    if retro_offset > 0 or str(target_key) != "1":
        out_txt = outline_path.read_text(encoding="utf-8", errors="replace") if (retro_offset == 0 and outline_path and outline_path.is_file()) else ""
        unidx = [p for p in newest_first if p.name not in seen and p.name not in out_txt and p.stem[11:] not in out_txt]
        for p in (newest_first[retro_offset:] if retro_offset > 0 else [*unidx, *newest_first]):
            if len(head_b) >= backfill_n:
                break
            if p.name not in seen and not common.read_frontmatter_bool(p, "aside"):
                seen.add(p.name)
                tag = "retro-archive" if retro_offset > 0 else ("outline-unindexed" if (out_txt and p in unidx) else "recent-backfill")
                head_b.append(_extract_post_seeds(p, ctx_dir, tag))
        return head_a, head_b
    for cand in norma_extract.rank_candidates(pdir, limit=max(1, forward_n) + backfill_n + 8):
        if len(head_b) >= backfill_n:
            break
        cp = Path(cand["path"])
        if cp.name not in seen and cp.is_file():
            seen.add(cp.name)
            head_b.append(_extract_post_seeds(cp, ctx_dir, "norma-up-next"))
    return head_a, head_b


def compute_scoreboard(foo_path: Path, head_a: list[dict], head_b: list[dict], head_0: list[dict] | None = None, is_outline: bool = False) -> dict:
    h0 = head_0 or []
    all_heads = [*h0, *head_a, *head_b]
    fl = foo_path.read_text(encoding="utf-8", errors="replace").splitlines() if foo_path.is_file() else []
    if is_outline:
        open_q = [ln.strip() for ln in fl if re.match(r"^\s*-\s*\[\s\]\s+", ln)]
        spine_q = [ln.strip() for ln in fl if re.match(r"^\s*(?:\d+\.|###\s+Act\b|-\s+\*\*)", ln)]
        todos, p0_count = (open_q or spine_q), len(open_q)
        axis1 = sum(1 for ln in fl if re.match(r"^\s*-\s*\[[xX]\]\s+", ln) or "article_id:" in ln)
        claimed_files = {m.strip().lower() for m in re.findall(r"`([A-Za-z0-9_./:-]{3,40})`", "\n".join(fl))}
    else:
        rs = next((i for i, ln in enumerate(fl) if ln.startswith("# --- START RECEIPTS")), None)
        re_i = next((i for i, ln in enumerate(fl) if ln.startswith("# --- END RECEIPTS")), None)
        top_rec = fl[rs + 1 : min(re_i, rs + 4)] if (rs is not None and re_i is not None) else []
        paint_i = next((i for i, ln in enumerate(fl) if "XIX. THE PAINTBOX" in ln), len(fl))
        claimed_files = set(re.findall(r"\b[a-z0-9_]+\.(?:py|nix|sh|js)\b", "\n".join(fl[:paint_i]).lower()))
        axis1 = sum(ln.lower().count("discharging") + ln.count("ALL LANDED") + (1 if "pipulate commit" in ln else 0) for ln in top_rec)
        todos = [ln for ln in fl if ln.startswith("# - TODO")]
        p0_count = sum(1 for ln in todos if ", P0." in ln)
    over_cap = sum(1 for ln in todos if len(ln) > 320)
    seed_tokens = _tokenize_topics([" ".join([*it["kws"], *it["ideas"], it["next_steps"], it.get("shard_summary", "")]) for it in all_heads])
    raw_phrases = {" ".join(re.findall(r"[a-z0-9]+", kw.lower())) for it in all_heads for kw in it["kws"]}
    raw_phrases = {p for p in raw_phrases if len(p.split()) >= 2 and p not in _PILLAR_PHRASES}
    todo_toks = [_tokenize_topics([ln]) for ln in todos]
    todo_words = [" " + " ".join(re.findall(r"[a-z0-9]+", ln.lower())) + " " for ln in todos]
    tok_df = Counter(t for ts in todo_toks for t in ts)
    phr_df = Counter(p for w in todo_words for p in raw_phrases if f" {p} " in w)
    rare_tokens = {t for t in seed_tokens if 1 <= tok_df[t] <= 4}
    rare_phrases = {p for p in raw_phrases if 1 <= phr_df[p] <= 4}
    for it in all_heads:
        blob = " ".join([it["title"], *it["kws"], *it["ideas"], it["next_steps"], it.get("shard_summary", "")])
        cap_ov = 8 if it.get("article_id") == 0 else 4
        t_ov = sorted(_tokenize_topics([blob]) & rare_tokens)[:cap_ov]
        if is_outline:
            f_ov = sorted(r for r in claimed_files if len(r) >= 4 and r in blob.lower())[:cap_ov]
            it["foo_hint"] = f"outline_overlap=({', '.join(t_ov) or 'none'}) | spine_refs=({', '.join(f_ov) or 'none'})"
        else:
            f_ov = sorted(set(re.findall(r"\b[a-z0-9_]+\.(?:py|nix|sh|js)\b", blob.lower())) & claimed_files)[:cap_ov]
            it["foo_hint"] = f"todo_overlap=({', '.join(t_ov) or 'none'}) | claimed_files=({', '.join(f_ov) or 'none'})"
    collisions, min_hits = [], (2 if is_outline else 3)
    for ln, ln_w, t_set in zip(todos, todo_words, todo_toks):
        p_hits = sorted(p for p in rare_phrases if f" {p} " in ln_w)
        t_hits = sorted(t_set & rare_tokens)
        if p_hits or len(t_hits) >= min_hits:
            shown = [*p_hits, *(t for t in t_hits if all(t not in p.split() for p in p_hits))][:5]
            raw_lbl = re.sub(r"^\s*(?:-\s*\[\s\]\s*|\d+\.\s*|###\s*)", "", ln).replace("**", "") if is_outline else ln.replace("# - TODO ", "")
            head_lbl = raw_lbl.split(":", 1)[0].strip()
            collisions.append((len(p_hits) * 2 + len(t_hits), head_lbl[:72], shown))
    collisions.sort(key=lambda x: (-x[0], x[1]))
    axis2 = len(collisions)
    verdict = "IN_FLIGHT_DRAFT_HARVEST" if h0 else ("OPEN_FOR_MERGES_AND_SPARKS" if (axis1 + axis2) > 0 else "HOLD_NET_ZERO")
    return {"axis0": len(h0[0]["ideas"]) if h0 else 0, "axis1": axis1, "axis2": axis2, "open_todos": len(todos), "p0_todos": p0_count, "over_cap": over_cap, "verdict": verdict, "collisions": collisions[:8]}


def _build_outline_dots_prompt(tkey: str, tcfg: dict, ledger_path: Path) -> str:
    o3, c3 = "[" * 3, "]" * 3
    alias = str(tcfg.get("alias") or tkey)
    name = str(tcfg.get("name") or alias)
    bu = str(tcfg.get("base_url") or "").strip()
    lane = str(tcfg.get("lane") or ("public" if bu.lower().startswith("https://") else "private")).strip().lower()
    return (
        f"You are running THE DOTS TRI-HEAD OUTLINE-REFINERY KATA against {ledger_path}\n"
        f"(Target: {tkey}={alias} — {name} | lane={lane}).\n"
        "Read the Goodhart Scoreboard, optional In-Flight Head 0 (prompt.md human draft segments),\n"
        "Forward Head A, Retrograde Head B ([OUTLINE_CHECK]), ! markov, and raw OUTLINE.md.\n"
        "GOVERNING LAW ( <= 1 file, <= 10 blocks, <= 120 replacement lines; CAPTURE & SPINE SYNC ONLY ):\n"
        "1. FOSSIL EXCAVATION & IDEMPOTENCE: Keep OUTLINE.md a crisp 80/20 spine, character/concept\n"
        "   crucible, shard index, and '- [ ]' chapter/scene queue (each queue item <= 320 chars).\n"
        "   Drop sparks already covered; fold net-new details into matching items; when every live\n"
        "   spark is already represented, return NOTHING_ELIGIBLE so repeated runs converge in 1 pass.\n"
        "2. TWO-SPEED HARVEST & LANE HYGIENE:\n"
        "   - IN_FLIGHT_DRAFT_HARVEST (Head 0 present): harvest net-new chapter/scene seeds,\n"
        "     character/concept friction rows, or structural mechanisms forged in prompt.md.\n"
        "   - CORPUS SWEEP: index any unindexed _posts/*.md dispatches in the Shard Index and flip\n"
        f"     discharged '- [ ]' items to '- [x]'. Enforce lane={lane}: never leak private-lane lore\n"
        "     into public outlines, and use bare domains (sunpug.io, mikelev.in, never schemes).\n"
        "OUTPUT CONTRACT: enclose the entire reply inside ONE fenced 'text' code block holding ONLY\n"
        f"Target: {ledger_path} + {o3}SEARCH{c3}/{o3}DIVIDER{c3}/{o3}REPLACE{c3} blocks, or\n"
        "NOTHING_ELIGIBLE axis0=<n> axis1=<n> axis2=<n> inside that single fence, zero prose outside.\n"
    )


def _run_dots_compile(args: argparse.Namespace, passthrough: list[str], repo_root: Path, targets: dict) -> int:
    import os
    import shutil
    import subprocess
    import tempfile
    tkey = str(args.target or "1")
    if args.retro is not None or args.retro_reset:
        _resolve_retro_window(args)
    tcfg = targets[tkey]
    alias = str(tcfg.get("alias") or tkey)
    pdir = Path(tcfg["path"]).expanduser().resolve()
    if tkey == "1":
        ledger_path = repo_root / "foo_files.py"
        chop_lines = ["! markov", "! postsc 3", "! .venv/bin/python scripts/articles/dots_extract.py", "foo_files.py", "apply.py"]
        if args.dry_compile:
            print(f"TARGET={tkey}:{alias} MODE=foo_files LEDGER={ledger_path}\nCHOP={' ; '.join(chop_lines)}\nPASSTHROUGH={passthrough}")
            return 0
        cmd = [sys.executable, str(repo_root / "prompt_foo.py"), "@DOTS_PROMPT", "--chop", "DOTS_CHOP", "--no-tree", *passthrough]
        return subprocess.run(cmd, cwd=str(repo_root)).returncode
    ledger_path = pdir.parent / "OUTLINE.md"
    has_posts = pdir.is_dir() and any(common._DATED_POST_RE.match(p.name) for p in pdir.glob("*.md"))
    ext_flags = [f"-t {alias}"]
    if args.forward != 2:
        ext_flags.append(f"-f {args.forward}")
    if args.backfill != 2:
        ext_flags.append(f"-b {args.backfill}")
    if args.offset > 0:
        ext_flags.append(f"--offset {args.offset}")
    if args.no_draft:
        ext_flags.append("--no-draft")
    chop_lines = [
        f"! markov -t {alias}",
        *([f"! postsc 3 -t {alias}"] if has_posts else []),
        f"! .venv/bin/python scripts/articles/dots_extract.py {' '.join(ext_flags)}",
        str(ledger_path),
    ]
    prompt_txt = _build_outline_dots_prompt(tkey, tcfg, ledger_path)
    if args.dry_compile:
        print(f"TARGET={tkey}:{alias} MODE=outline LEDGER={ledger_path} HAS_POSTS={has_posts}\nCHOP={' ; '.join(chop_lines)}\nPROMPT_LINE1={prompt_txt.splitlines()[0]}")
        return 0
    if not ledger_path.is_file():
        print(f"❌ dots: missing outline ledger at {ledger_path}", file=sys.stderr)
        return 1
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"dots_{alias}_"))
    try:
        chop_f, prompt_f = tmp_dir / f"dots_{alias}.chop.txt", tmp_dir / f"dots_{alias}.prompt.md"
        chop_f.write_text("\n".join(chop_lines) + "\n", encoding="utf-8")
        prompt_f.write_text(prompt_txt, encoding="utf-8")
        env = {**os.environ, "PIPULATE_ADHOC_FILE": str(chop_f)}
        cmd = [sys.executable, str(repo_root / "prompt_foo.py"), str(prompt_f), "--chop", "ADHOC_CHOP", "--no-tree", "-t", tkey, *passthrough]
        rc = subprocess.run(cmd, cwd=str(repo_root), env=env).returncode
        if rc == 0:
            print(f"🎯 DOTS Outline Refinery compiled for {tkey}={alias} -> {ledger_path}")
        return rc
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else list(argv)
    parser = argparse.ArgumentParser(description="Tri-Head Idea-Refinery Harvester (`dots`).")
    common.add_standard_arguments(parser)
    parser.add_argument("-f", "--forward", type=int, default=2, help="Newest _posts/*.md count for Head A (default: 2).")
    parser.add_argument("-b", "--backfill", type=int, default=2, help="Head B serotinous-cone count (default: 2).")
    parser.add_argument("--offset", type=int, default=0, help="Stateless backward post offset for Head B (default: 0).")
    parser.add_argument("--retro", nargs="?", const=3, default=None, type=int, help="Step persisted retrograde cursor back N posts (default: 3).")
    parser.add_argument("--retro-reset", action="store_true", help="Clear persisted retrograde cursor back to norma-up-next.")
    parser.add_argument("--no-draft", action="store_true", help="Skip In-Flight Head 0 (prompt.md) and inspect published _posts/ only.")
    parser.add_argument("--radar", action="store_true", help="Compact terminal summary without full seed bodies.")
    parser.add_argument("--compile", action="store_true", help="Compile refinery payload onto clipboard via prompt_foo.py.")
    parser.add_argument("--dry-compile", action="store_true", help="Preview target ledger, chop lines, and prompt header without compiling.")
    parser.add_argument("--repo-root", type=str, default=str(DEFAULT_REPO_ROOT), help="Repo root containing foo_files.py and prompt.md.")
    args, passthrough = parser.parse_known_args(raw_argv) if ("--compile" in raw_argv or "--dry-compile" in raw_argv) else (parser.parse_args(raw_argv), [])
    repo_root = Path(args.repo_root).expanduser().resolve()
    targets = common.load_targets()
    tkey = str(args.target or "1")
    if tkey not in targets:
        valid = ", ".join(f"{k}={v.get('alias', k)}" for k, v in targets.items())
        print(f"❌ dots: unknown target {tkey!r} (expected one of: {valid})", file=sys.stderr)
        return 1
    if args.compile or args.dry_compile:
        return _run_dots_compile(args, passthrough, repo_root, targets)
    tcfg = targets[tkey]
    pdir, is_outline = Path(tcfg["path"]).expanduser().resolve(), (tkey != "1")
    ledger_path = (pdir.parent / "OUTLINE.md") if is_outline else (repo_root / "foo_files.py")
    chk_lbl, t_alias = ("OUTLINE_CHECK" if is_outline else "FOO_CHECK"), str(tcfg.get("alias") or tkey)
    retro_off, eff_backfill, mode_lbl = _resolve_retro_window(args)
    head_0 = [] if args.no_draft else _extract_draft_seeds(repo_root / "prompt.md")
    head_a, head_b = harvest_dual_heads(pdir, forward_n=args.forward, backfill_n=eff_backfill, retro_offset=retro_off, target_key=tkey, outline_path=ledger_path if is_outline else None)
    sb = compute_scoreboard(ledger_path, head_a, head_b, head_0=head_0, is_outline=is_outline)
    eff_mode = f"in-flight+{mode_lbl}" if head_0 else mode_lbl
    q_lbl = f"Outline_Seeds={sb['open_todos']} (OpenBox={sb['p0_todos']})" if is_outline else f"Open_TODOs={sb['open_todos']} (P0={sb['p0_todos']})"
    print(f"# 🔵 DOTS TRI-HEAD IDEA REFINERY — Target: {tkey}={t_alias} ({ledger_path.name}) | Verdict: {sb['verdict']} | Mode: {eff_mode} | Over320c={sb['over_cap']}")
    print(f"# ⚖️  Goodhart Scoreboard: Axis0(DraftSegs)={sb['axis0']} | Axis1({'Indexed' if is_outline else 'Discharged'})={sb['axis1']} | Axis2(Collisions)={sb['axis2']} | {q_lbl}")
    for cnt, lbl, kws in sb["collisions"]:
        print(f"  • [overlap={cnt}] {lbl} <- ({', '.join(kws)})")
    heads = ([("In-Flight Head 0 (prompt.md)", head_0)] if head_0 else []) + [("Forward Head A (! latest)", head_a), (f"Retrograde Head B ({mode_lbl})", head_b)]
    for label, items in heads:
        print(f"\n## {label}")
        if not items:
            print("  • (No published posts in window yet)")
        for it in items:
            print(f"- #{it['article_id']} [{it['date']} | {it['source_tag']}] {it['title']} | kw=({', '.join(it['kws'])})")
            print(f"  [{chk_lbl}]: {it.get('foo_hint', '')}")
            if args.radar:
                for s_ln in it.get("turn_summaries", []):
                    print(f"  • {s_ln}")
            else:
                for blk in it["ideas"]:
                    print(f"  [IDEAS_BLOCK]:\n{blk}")
                if it["next_steps"]:
                    print(f"  [NEXT_STEP_PROMPTS]:\n{it['next_steps']}")
                elif not it["ideas"] and it.get("shard_summary"):
                    print(f"  [SHARD_SUMMARY]:\n{it['shard_summary']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
