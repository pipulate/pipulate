#!/usr/bin/env python3
"""
markov.py — Composable Markov Transition Matrix & Online Streaming ML (river) Lens.

Modes:
  1. Default (`markov` or `markov -t 1`):
     Reads the target blog's `_posts/_context/*.json` holographic shards in
     chronological order, builds 1st- and 2nd-order Markov transition matrices
     over topic/keyword states, runs `river` EWMA + online linear regression on
     topic momentum and token velocity, and prints a compact <45-line compass
     for `! markov` in `context.txt`.
  2. Generic Series (`markov path/to/series.txt` or `cat file | markov --stdin`):
     Auto-detects numeric time-series (prices, ticks, metrics) vs. discrete state
     sequences (paths, bots, words) and outputs Markov transition probabilities,
     entropy, `river.drift.ADWIN` regime-change alerts, and next-step forecasts.
  3. Demo (`markov --demo-series`):
     Runs a self-contained numeric + categorical verification pass.
"""

import argparse
from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from river import drift, linear_model, optim, preprocessing, stats

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from imports.ascii_displays import compute_ols_velocity, render_sparkline

CONFIG_DIR = Path.home() / ".config" / "pipulate"
TARGETS_FILE = Path(
    os.environ.get("PIPULATE_BLOGS_CONFIG", CONFIG_DIR / "blogs.json")
).expanduser()
DEFAULT_POSTS_DIR = Path(
    os.environ.get("PIPULATE_DEFAULT_POSTS_DIR", Path.home() / "repos" / "trimnoir" / "_posts")
).expanduser()
BRAIN_POSTS_DIR = Path(
    os.environ.get("PIPULATE_BRAIN_DIR", Path.home() / ".local" / "share" / "pipulate" / "brain" / "_posts")
).expanduser()
_DATED_STEM_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")
_FLOAT_TOKEN_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?$")


def _resolve_targets(target_spec: str) -> list[dict]:
    art_dir = str(_REPO_ROOT / "scripts" / "articles")
    if art_dir not in sys.path:
        sys.path.append(art_dir)
    import common as _common
    import lsa as _lsa
    targets = json.loads(TARGETS_FILE.read_text(encoding="utf-8")) if TARGETS_FILE.is_file() else _common.load_targets()
    keys = _lsa.parse_target_spec(str(target_spec or "1").strip() or "1", targets)
    out = []
    for k in keys:
        cfg = targets[k]
        p, name = Path(cfg["path"]).expanduser(), str(cfg.get("name") or k)
        if k == "1" and (not (p / "_context").is_dir()) and (BRAIN_POSTS_DIR / "_context").is_dir():
            name, p = "MikeLev.in (2nd Brain)", BRAIN_POSTS_DIR
        bu = str(cfg.get("base_url") or "").strip()
        lane = str(cfg.get("lane") or ("public" if bu.lower().startswith("https://") else "private")).strip().lower()
        out.append({"key": k, "alias": str(cfg.get("alias") or k), "name": name, "posts_dir": p, "base_url": bu, "lane": lane})
    return out


def _resolve_posts_dir(target_spec: str) -> tuple[str, Path]:
    first = _resolve_targets(target_spec)[0]
    return first["name"], first["posts_dir"]


def _target_public_domains(targets_list: list[dict]) -> list[str]:
    import urllib.parse
    doms = []
    for t in targets_list:
        bu = str(t.get("base_url") or "").strip()
        if bu.lower().startswith("https://"):
            h = urllib.parse.urlparse(bu).netloc.split(":", 1)[0].lower().rstrip(".").removeprefix("www.")
            if h and not h.endswith(".local") and h not in ("localhost", "127.0.0.1") and h not in doms:
                doms.append(h)
    return doms


def _read_md_fallback_topics(md_file: Path) -> tuple[list[str], int]:
    import yaml
    try:
        with open(md_file, "r", encoding="utf-8", errors="replace") as fh:
            parts = fh.read(6144).split("---", 2)
        fm = (yaml.safe_load(parts[1]) or {}) if len(parts) >= 3 and parts[0] == "" else {}
    except Exception:
        return [], 0
    raw_kw = (fm.get("meta_keywords") or fm.get("keywords") or fm.get("tags") or []) if isinstance(fm, dict) else []
    items = raw_kw.split(",") if isinstance(raw_kw, str) else (raw_kw if isinstance(raw_kw, (list, tuple)) else [])
    kws = [_norm_topic(k) for k in items if _norm_topic(k)]
    so_raw = fm.get("sort_order") if isinstance(fm, dict) else 0
    return kws, (int(so_raw) if str(so_raw or "").lstrip("-").isdigit() else 0)


def _shannon_entropy(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    ent = 0.0
    for c in counter.values():
        if c > 0:
            p = c / total
            ent -= p * math.log2(p)
    return ent


def _norm_topic(raw: str) -> str:
    return " ".join(str(raw or "").strip().split())


_PUBLIC_FILE_TOPICS = frozenset({
    "llms.txt", "robots.txt", "sitemap.xml", "feed.xml",
    "agents.md", "skill.md", ".zshrc", ".bashrc",
})
_INTERNAL_FILE_RE = re.compile(
    r"(?:^|/)[A-Za-z0-9_.-]+\.(?:py|md|txt|json|jsonl|nix|sh|lua|yml|yaml|toml|lock)$",
    re.IGNORECASE,
)


def _is_internal_artifact(topic: str) -> bool:
    low = (topic or "").strip().lower()
    if not low or low in _PUBLIC_FILE_TOPICS:
        return False
    return bool(_INTERNAL_FILE_RE.search(low))


_REMOTE_REF_PY = r"""
import datetime, json, sqlite3, sys
days, lim = int(sys.argv[1]), int(sys.argv[2])
bkt_req = sys.argv[3] if len(sys.argv) > 3 else "all"
db_p = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else "/home/mike/www/mikelev.in/honeybot.db"
conn = sqlite3.connect(f"file:{db_p}?mode=ro", uri=True)
if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='referrer_radar'").fetchone():
    print(json.dumps({"status": "sync_pending", "obs_days": max(1, days), "total_edges": 0, "bucket_edges": 0, "bucket_domains": 0, "bucket_hits": 0, "demand": [], "radar": [], "edges": [], "domains": []}))
    raise SystemExit(0)
_AI_APEX = {"bing.com", "duckduckgo.com", "ddg.gg", "kagi.com", "baidu.com", "yahoo.com", "brave.com", "ecosia.org", "qwant.com", "sogou.com", "so.com", "naver.com", "seznam.cz", "mojeek.com", "startpage.com", "yep.com", "marginalia-search.com", "chatgpt.com", "openai.com", "claude.ai", "anthropic.com", "perplexity.ai", "you.com", "phind.com", "poe.com", "grok.com", "x.ai", "mistral.ai", "deepseek.com", "meta.ai", "genspark.ai", "exa.ai", "copilot.microsoft.com"}
_SOCIAL_APEX = {"t.co", "x.com", "twitter.com", "lnkd.in", "linkedin.com", "facebook.com", "fb.com", "fb.me", "reddit.com", "redd.it", "bsky.app", "news.ycombinator.com", "ycombinator.com", "lobste.rs", "discord.com", "discord.gg", "instagram.com", "threads.net", "youtube.com", "youtu.be", "pinterest.com", "tiktok.com", "msn.com", "live.com"}
_NOISE_APEX = {"nip.io", "sslip.io", "verizon.net", "netcraft.com"}
_BAD_REF_SUB = ("/wp-admin", "/wp-login", "xmlrpc.php", "/.env")
today = datetime.date.today()
cut = (today - datetime.timedelta(days=max(1, days))).isoformat()
cut_7d = (today - datetime.timedelta(days=6)).isoformat()
tot = conn.execute("SELECT COUNT(*) FROM referrer_radar").fetchone()[0]
dem = conn.execute("SELECT rdl.ref_apex, d.value, p.value, SUM(rdl.count) as hits, SUM(rdl.human_count) as hum, SUM(rdl.unique_ips) as ips, MAX(rdl.sample_referrer) FROM referrer_daily_logs rdl JOIN domains d ON rdl.domain_id = d.id JOIN paths p ON rdl.path_id = p.id WHERE rdl.date >= ? AND rdl.human_count > 0 GROUP BY rdl.ref_apex, rdl.domain_id, rdl.path_id ORDER BY hum DESC, ips DESC, hits DESC LIMIT ?", (cut, lim)).fetchall()
rad = conn.execute("SELECT rr.ref_apex, d.value, p.value, COALESCE(SUM(rdl.count), rr.total_count), COALESCE(SUM(rdl.human_count), rr.human_count), COALESCE(SUM(rdl.unique_ips), 1), substr(rr.first_seen, 1, 16), rr.first_referrer FROM referrer_radar rr JOIN domains d ON rr.domain_id = d.id JOIN paths p ON rr.path_id = p.id LEFT JOIN referrer_daily_logs rdl ON (rdl.ref_apex = rr.ref_apex AND rdl.domain_id = rr.domain_id AND rdl.path_id = rr.path_id AND rdl.date >= ?) WHERE substr(rr.first_seen, 1, 10) >= ? GROUP BY rr.ref_apex, rr.domain_id, rr.path_id ORDER BY rr.first_seen DESC, rr.rowid DESC LIMIT ?", (cut, cut, lim)).fetchall()
min_d = (conn.execute("SELECT MIN(date) FROM referrer_daily_logs WHERE date >= ?", (cut,)).fetchone() or [None])[0]
obs_days = max(1, min(max(1, days), (today - datetime.date.fromisoformat(min_d)).days + 1)) if min_d else max(1, days)
dom_days = dict(conn.execute("SELECT ref_apex, COUNT(DISTINCT date) FROM referrer_daily_logs WHERE date >= ? GROUP BY ref_apex", (cut,)).fetchall())
d_rows = conn.execute("SELECT rdl.ref_apex, d.value, p.value, SUM(rdl.count), SUM(rdl.human_count), SUM(rdl.unique_ips), SUM(CASE WHEN rdl.date >= ? THEN rdl.count ELSE 0 END), COUNT(DISTINCT rdl.date), COALESCE(substr(rr.first_seen, 1, 16), MIN(rdl.date)), COALESCE(rr.first_referrer, ''), COALESCE(rr.last_referrer, ''), MAX(rdl.sample_referrer) FROM referrer_daily_logs rdl JOIN domains d ON rdl.domain_id = d.id JOIN paths p ON rdl.path_id = p.id LEFT JOIN referrer_radar rr ON (rr.ref_apex = rdl.ref_apex AND rr.domain_id = rdl.domain_id AND rr.path_id = rdl.path_id) WHERE rdl.date >= ? GROUP BY rdl.ref_apex, rdl.domain_id, rdl.path_id", (cut_7d, cut)).fetchall()
def _vel(hits, h7):
    r_all, r_7 = round(hits / obs_days, 2), round(h7 / min(7, obs_days), 2)
    r_pre = ((hits - h7) / (obs_days - 7)) if obs_days > 7 else r_7
    return r_all, r_7, round(r_7 - r_pre, 2)
edges, by_dom = [], {}
for ap, dom, p_s, hits, hum, ips, h7, p_days, f_seen, f_ref, l_ref, s_ref in d_rows:
    a = (ap or "").lower()
    refs = [r for r in (f_ref, l_ref, s_ref) if r]
    https_u = [u for u in refs if "://" in u and u.split(":", 1)[0].lower() in ("http", "https") and not any(b in u.lower() for b in _BAD_REF_SUB)]
    if not a:
        continue
    if a in _AI_APEX or a.startswith(("google.", "yandex.", "yahoo.", "baidu.")) or any(x in a for x in (".google.", ".yandex.", ".yahoo.", ".baidu.", "googlequicksearchbox")):
        bkt = "ai"
    elif a in _SOCIAL_APEX or (a.startswith(("com.", "org.", "net.")) and a.count(".") >= 2):
        bkt = "social"
    elif https_u and a not in _NOISE_APEX:
        bkt = "links"
    else:
        bkt = "other"
    if bkt_req in ("ai", "links", "social") and bkt != bkt_req:
        continue
    best_u = max(https_u, key=len) if https_u else (refs[0] if refs else a)
    src = best_u if bkt_req == "links" else a
    h_i, hm_i, ip_i, h7_i = int(hits), int(hum), int(ips), int(h7)
    edges.append([src, a, dom, p_s, h_i, hm_i, ip_i, h7_i, int(p_days), f_seen, *_vel(h_i, h7_i)])
    cur, cand = by_dom.get(a), (h_i, hm_i, f"{dom}{p_s}", best_u)
    by_dom[a] = [h_i, hm_i, ip_i, h7_i, 1, f_seen, cand] if cur is None else [cur[0] + h_i, cur[1] + hm_i, cur[2] + ip_i, cur[3] + h7_i, cur[4] + 1, max(cur[5], f_seen), max(cur[6], cand)]
edges.sort(key=lambda x: (x[4], x[5], x[6], x[7], x[9]), reverse=True)
doms = [[a, c[0], c[1], c[2], c[4], int(dom_days.get(a, 1)), c[5], c[6][2], c[6][3], *_vel(c[0], c[3])] for a, c in by_dom.items()]
doms.sort(key=lambda x: (x[1], x[2], x[3], x[4], x[6]), reverse=True)
print(json.dumps({"status": "live", "obs_days": obs_days, "total_edges": tot, "bucket_edges": len(edges), "bucket_domains": len(doms), "bucket_hits": sum(x[4] for x in edges), "demand": dem, "radar": rad, "edges": edges[:lim], "domains": doms[:lim]}))
"""


def _fetch_honeybot_referrals(days: int = 30, limit: int = 20, force_refresh: bool = False, bucket: str = "all") -> dict:
    db_override = os.environ.get("PIPULATE_HONEYBOT_DB", "").strip()
    if db_override and Path(db_override).is_file():
        res = subprocess.run([sys.executable, "-", str(int(days)), str(int(limit)), bucket, db_override], input=_REMOTE_REF_PY, capture_output=True, text=True, timeout=4, check=False)
        return json.loads(res.stdout.strip()) if res.returncode == 0 and (res.stdout or "").strip() else {"status": "error", "total_edges": 0, "demand": [], "radar": []}
    cache_p = CONFIG_DIR / "honeybot_referrals_cache.json"
    if not force_refresh and bucket == "all" and cache_p.is_file() and (time.time() - cache_p.stat().st_mtime) < 300:
        try:
            return json.loads(cache_p.read_text(encoding="utf-8"))
        except Exception:
            pass
    host = os.environ.get("PIPULATE_HONEYBOT_HOST", "honeybot")
    try:
        res = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", host, "python3", "-", str(int(days)), str(int(limit)), bucket], input=_REMOTE_REF_PY, capture_output=True, text=True, timeout=4, check=False)
        if res.returncode == 0 and (res.stdout or "").strip():
            data = json.loads(res.stdout.strip())
            if data.get("status") == "live" and int(days) == 30 and bucket == "all":
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                cache_p.write_text(json.dumps(data), encoding="utf-8")
            return data
    except Exception:
        pass
    if cache_p.is_file():
        try:
            return {**json.loads(cache_p.read_text(encoding="utf-8")), "status": "cached"}
        except Exception:
            pass
    return {"status": "offline", "total_edges": 0, "demand": [], "radar": []}


def _match_path_keywords(path_str: str, slug_map: dict) -> list[str]:
    clean = re.sub(r"(?:/index\.md|\.html)$", "", (path_str or "").split("?", 1)[0]).strip("/")
    if not clean:
        return ["Home Observatory", "SunPug.io", "RFC 9110"]
    rec = slug_map.get(clean.rsplit("/", 1)[-1].lower())
    return rec["kws"][:4] if rec else []


def _print_cross_lane_diff(records: list[dict], targets_list: list[dict], top_k: int = 5) -> None:
    lanes = {t["alias"]: t.get("lane", "public") for t in targets_list}
    if len(set(lanes.values())) < 2:
        return
    pub_c, priv_c, labels = Counter(), Counter(), {}
    for r in records:
        bucket = priv_c if lanes.get(r["alias"]) == "private" else pub_c
        for k in dict.fromkeys(r["kws"]):
            if not _is_internal_artifact(k):
                low = k.lower()
                labels.setdefault(low, k)
                bucket[low] += 1
    shared = sorted(
        ((min(priv_c[k], pub_c[k]), priv_c[k] + pub_c[k], priv_c[k], pub_c[k], labels[k]) for k in priv_c if pub_c[k] > 0),
        reverse=True,
    )
    priv_only = sorted(((cnt, labels[k]) for k, cnt in priv_c.items() if cnt >= 2 and pub_c[k] == 0), reverse=True)
    print("\n## 6. Cross-Lane Topic Differential (Private <-> Public)")
    for _, _, pr_n, pu_n, lbl in shared[:top_k]:
        print(f"  • [bridge     | priv={pr_n:3d}, pub={pu_n:4d}] {lbl}")
    for pr_n, lbl in priv_only[:top_k]:
        print(f"  • [air-gapped | priv={pr_n:3d}, pub=   0] {lbl}")


def analyze_corpus_shards(target_spec: str = "1", top_k: int = 5) -> int:
    try:
        targets_list = _resolve_targets(target_spec)
    except ValueError as exc:
        print(f"❌ markov: {exc}", file=sys.stderr)
        return 1
    multi = len(targets_list) > 1
    target_name = targets_list[0]["name"] if not multi else f"{', '.join(t['alias'] for t in targets_list)} ({len(targets_list)} blogs)"
    context_dir = ", ".join(str(t["posts_dir"]) for t in targets_list)

    fm_cache = {}
    fm_cache_file = CONFIG_DIR / "fm_cache.json"
    if fm_cache_file.is_file():
        try:
            fm_cache = json.loads(fm_cache_file.read_text(encoding="utf-8"))
        except Exception:
            fm_cache = {}

    token_cache = {}
    token_cache_file = CONFIG_DIR / "token_cache.json"
    if token_cache_file.is_file():
        try:
            token_cache = json.loads(token_cache_file.read_text(encoding="utf-8"))
        except Exception:
            token_cache = {}

    records = []
    def _push_rec(m_obj, mf: Path, alias: str, kws: list[str], subs: list[str], fb_ord: int = 0) -> None:
        if not kws and not subs:
            return
        mp = str(mf)
        so = int(fm_cache[mp][1] or 0) if (mp in fm_cache and len(fm_cache[mp]) >= 2) else fb_ord
        tok = int(token_cache[mp][1] or 0) if (mp in token_cache and len(token_cache[mp]) >= 2) else (max(1, mf.stat().st_size // 4) if mf.is_file() else 0)
        records.append({"stem": mf.stem, "date": m_obj.group(1), "slug": m_obj.group(2), "alias": alias, "sort_order": so, "tokens": tok, "kws": kws, "subs": subs, "lead": kws[0] if kws else subs[0]})
    for t_cfg in targets_list:
        p_dir, c_dir, seen = t_cfg["posts_dir"], t_cfg["posts_dir"] / "_context", set()
        for jf in (c_dir.glob("*.json") if c_dir.is_dir() else ()):
            m = _DATED_STEM_RE.match(jf.stem)
            if m:
                seen.add(jf.stem)
                try:
                    data = json.loads(jf.read_text(encoding="utf-8"))
                    _push_rec(m, p_dir / f"{jf.stem}.md", t_cfg["alias"], [_norm_topic(k) for k in (data.get("kw") or []) if _norm_topic(k)], [_norm_topic(s) for s in (data.get("sub") or []) if _norm_topic(s)])
                except Exception:
                    continue
        for mf in (p_dir.glob("*.md") if p_dir.is_dir() else ()):
            m = _DATED_STEM_RE.match(mf.stem)
            if m and mf.stem not in seen:
                kws, fm_ord = _read_md_fallback_topics(mf)
                _push_rec(m, mf, t_cfg["alias"], kws, [], fm_ord)

    outlines = [str(t["posts_dir"].parent / "OUTLINE.md") for t in targets_list if (t["posts_dir"].parent / "OUTLINE.md").is_file()]
    if not records:
        if outlines:
            print(f"# 🎲 MARKOV & RIVER ONLINE COMPASS — {target_name} (0 shards — outline seeded)")
            print(f"# 🗺️  Track Outline: {', '.join(outlines)}")
            print("  • (Seeded creative track — publish post #1 to activate Markov transitions)")
            return 0
        print(f"⚠️ markov: 0 valid shards in {context_dir}", file=sys.stderr)
        return 1

    records.sort(key=lambda r: (r["date"], r["sort_order"], r["stem"]))

    trans_1: dict[str, Counter] = defaultdict(Counter)
    trans_2: dict[tuple[str, str], Counter] = defaultdict(Counter)
    topic_counts: Counter = Counter()
    last_seen_idx: dict[str, int] = {}

    ewma_tokens = stats.EWMean(fading_factor=0.2)
    token_drift = drift.ADWIN()
    drift_events = 0

    for idx, rec in enumerate(records):
        if rec["tokens"] > 0:
            ewma_tokens.update(rec["tokens"])
            token_drift.update(rec["tokens"])
            if token_drift.drift_detected:
                drift_events += 1
        for k in rec["kws"]:
            topic_counts[k] += 1
            last_seen_idx[k] = idx
        # Intra-article keyword chain
        for i in range(len(rec["kws"]) - 1):
            a, b = rec["kws"][i], rec["kws"][i + 1]
            if a.lower() != b.lower():
                trans_1[a][b] += 1
        # Inter-article lead transition
        if idx > 0:
            prev_kws = records[idx - 1]["kws"]
            cur_kws = rec["kws"]
            for a in prev_kws[:2]:
                for b in cur_kws[:2]:
                    if a.lower() != b.lower():
                        trans_1[a][b] += 2
            if idx > 1:
                p2 = records[idx - 2]["lead"]
                p1 = records[idx - 1]["lead"]
                c0 = rec["lead"]
                if len({p2.lower(), p1.lower(), c0.lower()}) == 3:
                    trans_2[(p2, p1)][c0] += 1

    if len(records) > 30:
        recent_window, prior_window, min_rcnt = records[-30:], records[-120:-30], 2
    elif len(records) >= 4:
        half = len(records) // 2
        recent_window, prior_window, min_rcnt = records[half:], records[:half], (2 if len(records) - half >= 6 else 1)
    else:
        recent_window, prior_window, min_rcnt = records, [], 1
    recent_counts = Counter(k for r in recent_window for k in r["kws"])
    prior_counts = Counter(k for r in prior_window for k in r["kws"])
    r_len = max(1, len(recent_window))
    p_len = max(1, len(prior_window))

    momentum = []
    for topic, r_cnt in recent_counts.items():
        if r_cnt < min_rcnt or _is_internal_artifact(topic):
            continue
        r_rate = r_cnt / r_len
        p_rate = prior_counts.get(topic, 0) / p_len
        lift = (r_rate - p_rate) / max(0.01, p_rate)
        momentum.append((lift, r_cnt, topic))
    momentum.sort(reverse=True)

    total_recs = len(records)
    last_3 = records[-3:]
    cur_rec = records[-1]
    prev_rec = records[-2] if total_recs >= 2 else cur_rec
    raw_pool = list(dict.fromkeys([*cur_rec["kws"], *cur_rec["subs"]]))
    connected = [k for k in raw_pool if topic_counts[k] >= 2 and len(trans_1.get(k, ())) > 0]
    cur_states = (connected + [k for k in raw_pool if k not in connected])[:4]

    cur_pool_lower = {k.lower() for k in raw_pool}
    # Aggregate 1st-order predictions from current article's top keywords
    next_candidates: Counter = Counter()
    for st in cur_states:
        row = trans_1.get(st, Counter())
        row_total = sum(row.values())
        if row_total > 0:
            for target_st, cnt in row.items():
                if target_st.lower() not in cur_pool_lower and not _is_internal_artifact(target_st):
                    next_candidates[target_st] += cnt / row_total

    # HitTail "Step Into Traffic" Bridges: connected to current state, high corpus weight,
    # not visited in the last 8 articles
    bridges = []
    for target_st, score in next_candidates.items():
        age = (total_recs - 1) - last_seen_idx.get(target_st, 0)
        if age >= 8 and topic_counts[target_st] >= 3:
            bridge_score = score * math.log2(1 + topic_counts[target_st]) * min(3.0, age / 10.0)
            bridges.append((bridge_score, age, topic_counts[target_st], target_st))
    bridges.sort(reverse=True)

    print(f"# 🎲 MARKOV & RIVER ONLINE COMPASS — {target_name} ({total_recs:,} shards)")
    print(
        f"# 🌊 River Token EWMA: {int(ewma_tokens.get() or 0):,} tok/post | "
        f"ADWIN Regime Shifts: {drift_events} | Unique States: {len(topic_counts):,}"
    )
    outlines = [str(t["posts_dir"].parent / "OUTLINE.md") for t in targets_list if (t["posts_dir"].parent / "OUTLINE.md").is_file()]
    if outlines:
        print(f"# 🗺️  Track Outline: {', '.join(outlines)}")
    print("\n## 1. Current Trajectory (Last 3 Balls Thrown)")
    for r in last_3:
        kw_preview = ", ".join(r["kws"][:4])
        tag_s = f" | {r['alias']}" if multi else ""
        print(f"  • [{r['date']} #{r['sort_order']}{tag_s}] {r['slug']} -> ({kw_preview})")

    print(f"\n## 2. Markov Next-State Predictions P(S_t+1 | S_t in {{{', '.join(cur_states)}}})")
    top_next = next_candidates.most_common(top_k)
    norm_sum = sum(v for _, v in top_next) or 1.0
    for st, raw_p in top_next:
        pct = (raw_p / norm_sum) * 100.0
        ent = _shannon_entropy(trans_1[st])
        print(f"  • {pct:5.1f}% -> {st:<28s} (corpus_hits={topic_counts[st]}, H={ent:.2f} bits)")

    pair_key = (prev_rec["lead"], cur_rec["lead"])
    if pair_key in trans_2:
        p2_top = trans_2[pair_key].most_common(3)
        p2_str = ", ".join(f"{k} ({v})" for k, v in p2_top)
        print(f"  • 2nd-Order Chain [{pair_key[0]} -> {pair_key[1]}] => {p2_str}")

    print("\n## 3. HitTail 'Step Into Traffic' Bridges (Connected + Unvisited >= 8 Turns)")
    if bridges:
        for b_score, age, hits, st in bridges[:top_k]:
            print(f"  • [lift={b_score:4.2f} | idle={age:3d} turns | hits={hits:3d}] {st}")
    else:
        print("  • (All immediate neighbor states visited within last 8 turns)")

    win_n = len(recent_window)
    print(f"\n## 4. River Streaming Momentum Surge (Last {30 if len(records) > 30 else win_n} vs. Baseline)")
    for lift, r_cnt, topic in momentum[:top_k]:
        print(f"  • [+{lift:5.1f}x surge | {r_cnt:2d}/{win_n} recent posts] {topic}")

    pub_doms = _target_public_domains(targets_list)
    if not pub_doms:
        print("\n## 5. Post-GSC HitTail External Demand & Shard Intent (local/air-gapped)")
        print("  • (Local-only target — external Honeybot wire referrals omitted by design)")
    else:
        slug_map = {r["slug"].lower(): r for r in records}
        ext = _fetch_honeybot_referrals(days=30, limit=max(25, top_k * 5), force_refresh=False)
        dem_rows = [row for row in (ext.get("demand") or []) if str(row[1] or "").lower().rstrip(".").removeprefix("www.") in pub_doms]
        print(f"\n## 5. Post-GSC HitTail External Demand & Shard Intent (30d | {ext.get('status', 'offline')})")
        if dem_rows:
            for apex, dom, path_s, hits, hum, ips, _ in dem_rows[:top_k]:
                kws = ", ".join(_match_path_keywords(path_s, slug_map)) or "non-post surface"
                print(f"  • [{apex:<16s} | N={hits:3d}, P={ips:2d} IPs] {dom}{path_s} -> ({kws})")
        elif ext.get("status") == "sync_pending":
            print("  • (Honeybot referrer_radar sync pending — run ytreboot to backfill honeybot.db)")
        else:
            print(f"  • (No external human referrals in window; source={ext.get('status', 'offline')})")
    _print_cross_lane_diff(records, targets_list, top_k=top_k)
    return 0


def run_referral_radar(target_spec: str = "1", days: int = 30, top_k: int = 15, links_only: bool = False, ai_only: bool = False, social_only: bool = False, by_domain: bool = False) -> int:
    try:
        targets_list = _resolve_targets(target_spec)
    except ValueError as exc:
        print(f"❌ markov: {exc}", file=sys.stderr)
        return 1
    if not _target_public_domains(targets_list):
        print(f"# 📡 HONEYBOT POST-GSC REFERRAL RADAR ({targets_list[0]['name']} — local/air-gapped target)")
        return 0
    posts_dir, slug_map = targets_list[0]["posts_dir"], {}
    ctx_dir = posts_dir / "_context"
    if ctx_dir.is_dir():
        for jf in ctx_dir.glob("*.json"):
            m = _DATED_STEM_RE.match(jf.stem)
            if m:
                try:
                    d = json.loads(jf.read_text(encoding="utf-8"))
                    slug_map[m.group(2).lower()] = {"kws": [_norm_topic(k) for k in (d.get("kw") or []) if _norm_topic(k)]}
                except Exception:
                    pass
    bkt = "ai" if ai_only else ("social" if social_only else ("links" if links_only else "all"))
    snap = _fetch_honeybot_referrals(days=days, limit=top_k, force_refresh=True, bucket=bkt)
    obs = snap.get("obs_days", days)
    if bkt in ("ai", "links", "social") or by_domain:
        tag = "🤖 HONEYBOT SEARCH & AI" if bkt == "ai" else ("📱 HONEYBOT SOCIAL PLATFORMS" if bkt == "social" else ("🔗 HONEYBOT CLICKABLE WEB" if bkt == "links" else "📡 HONEYBOT EXTERNAL"))
        if by_domain:
            doms = snap.get("domains") or []
            print(f"# {tag} DOMAIN ROLLUP ({days}d, obs={obs}d | status={snap.get('status')} | domains={snap.get('bucket_domains', 0)} | edges={snap.get('bucket_edges', 0)} | hits={snap.get('bucket_hits', 0)})")
            for idx, (ap, hits, hum, ips, urls, a_days, _, top_t, top_u, r_all, r_7, dv) in enumerate(doms, 1):
                lead = f"{top_u} => {top_t}" if bkt == "links" and top_u != ap else top_t
                dv_s = f"[{dv:+.2f}/d]"
                print(f"  {idx:2d}. {ap:<18s} | N={hits:4d}, P={ips:3d} IPs, hum={hum:4d} | urls={urls:3d}, days={a_days:2d} | {r_all:5.2f}/d, 7d={r_7:5.2f}/d {dv_s:>10s} | top: {lead}")
            if not doms:
                print(f"  • (No {bkt} domain referrals in window)")
            return 0
        edges = snap.get("edges") or []
        print(f"# {tag} REFERRAL VELOCITY ({days}d, obs={obs}d | status={snap.get('status')} | edges={snap.get('bucket_edges', 0)} | hits={snap.get('bucket_hits', 0)})")
        for idx, (src, _, dom, path_s, hits, hum, ips, _, _, f_seen, r_all, r_7, dv) in enumerate(edges, 1):
            kws = _match_path_keywords(path_s, slug_map)
            kw_str = f" -> ({', '.join(kws)})" if kws else ""
            dv_s = f"[{dv:+.2f}/d]"
            print(f"  {idx:2d}. [{f_seen[:10]}] | N={hits:4d}, P={ips:3d} IPs, hum={hum:4d} | {r_all:5.2f}/d, 7d={r_7:5.2f}/d {dv_s:>10s} | {src:<18s} => {dom}{path_s}{kw_str}")
        if not edges:
            print(f"  • (No {bkt} referrals in window)")
        return 0
    print(f"# 📡 HONEYBOT POST-GSC REFERRAL RADAR ({days}d | status={snap.get('status')} | unique_edges={snap.get('total_edges', 0)})")
    for idx, (apex, dom, path_s, hits, hum, ips, f_seen, f_ref) in enumerate(snap.get("radar") or [], 1):
        kws = _match_path_keywords(path_s, slug_map)
        kw_str = f" -> ({', '.join(kws)})" if kws else ""
        print(f"  {idx:2d}. [{f_seen}] {apex:<16s} => {dom}{path_s} (N={hits}, P={ips} IPs, hum={hum}) via {f_ref}{kw_str}")
    if not snap.get("radar"):
        print("  • (Run ytreboot to deploy remotes/honeybot/scripts/db.py and backfill live Honeybot radar)")
    return 0


def _parse_series_lines(lines: list[str]) -> tuple[bool, list]:
    """Detect whether input lines represent a numeric series or categorical states."""
    numeric_vals = []
    categorical_vals = []
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        parts = [p.strip() for p in re.split(r"[,\t ]+", s) if p.strip()]
        if not parts:
            continue
        last_tok = parts[-1]
        if _FLOAT_TOKEN_RE.match(last_tok):
            numeric_vals.append((parts[0] if len(parts) > 1 else str(len(numeric_vals) + 1), float(last_tok)))
        categorical_vals.append(s if len(parts) == 1 else parts[-1])
    if len(numeric_vals) >= max(4, int(0.75 * len(categorical_vals))) and len(numeric_vals) >= 4:
        return True, numeric_vals
    return False, categorical_vals


def analyze_generic_series(lines: list[str], label: str = "stdin", top_k: int = 5) -> int:
    is_num, items = _parse_series_lines(lines)
    if len(items) < 3:
        print(f"⚠️ markov: need at least 3 observations in {label} (got {len(items)})", file=sys.stderr)
        return 1

    if is_num:
        model = preprocessing.StandardScaler() | linear_model.LinearRegression(
            optimizer=optim.SGD(0.01)
        )
        ewma = stats.EWMean(fading_factor=0.3)
        delta_var = stats.Var()
        adwin = drift.ADWIN()

        regimes = []
        drifts = []
        preds = []
        for idx, (ts_label, val) in enumerate(items):
            if idx > 0:
                prev_val = items[idx - 1][1]
                delta = val - prev_val
                delta_var.update(delta)
                std = math.sqrt(max(1e-9, delta_var.get() or 1.0))
                if delta > 0.75 * std:
                    reg = "SURGE_UP"
                elif delta > 0.15 * std:
                    reg = "UP"
                elif delta < -0.75 * std:
                    reg = "DROP_DOWN"
                elif delta < -0.15 * std:
                    reg = "DOWN"
                else:
                    reg = "FLAT"
                regimes.append(reg)
                x_feat = {"t": float(idx), "prev": prev_val, "ewma": float(ewma.get() or prev_val)}
                preds.append(model.predict_one(x_feat))
                model.learn_one(x_feat, val)
            ewma.update(val)
            adwin.update(val)
            if adwin.drift_detected:
                drifts.append(ts_label)

        trans_1: dict[str, Counter] = defaultdict(Counter)
        trans_2: dict[tuple[str, str], Counter] = defaultdict(Counter)
        for i in range(len(regimes) - 1):
            trans_1[regimes[i]][regimes[i + 1]] += 1
            if i > 0:
                trans_2[(regimes[i - 1], regimes[i])][regimes[i + 1]] += 1

        last_label, last_val = items[-1]
        cur_reg = regimes[-1]
        prev_reg = regimes[-2] if len(regimes) >= 2 else cur_reg
        next_x = {"t": float(len(items)), "prev": last_val, "ewma": float(ewma.get() or last_val)}
        next_pred = model.predict_one(next_x)

        print(f"# 📈 MARKOV & RIVER NUMERIC SERIES LENS — {label} ({len(items)} steps)")
        print(
            f"# Latest: {last_val:.4g} (@{last_label}) | Regime: {prev_reg} -> {cur_reg} | "
            f"EWMA: {(ewma.get() or last_val):.4g} | River Next Forecast: {next_pred:.4g} | "
            f"ADWIN Drifts: {len(drifts)}"
        )
        row = trans_1.get(cur_reg, Counter())
        tot = sum(row.values()) or 1
        print(f"\n## 1. 1st-Order Regime Transition P(R_t+1 | R_t = {cur_reg})")
        for r_state, cnt in row.most_common(top_k):
            print(f"  • {(cnt / tot) * 100:5.1f}% -> {r_state:<12s} (n={cnt})")
        pair = (prev_reg, cur_reg)
        if pair in trans_2:
            r2 = trans_2[pair]
            t2 = sum(r2.values()) or 1
            dist_str = ", ".join(f"{k}: {(v / t2) * 100:.0f}%" for k, v in r2.most_common(3))
            print(f"  • 2nd-Order [{pair[0]} -> {pair[1]}] => {dist_str}")
        return 0

    # Categorical / Discrete State Sequence
    trans_1 = defaultdict(Counter)
    trans_2 = defaultdict(Counter)
    for i in range(len(items) - 1):
        trans_1[items[i]][items[i + 1]] += 1
        if i > 0:
            trans_2[(items[i - 1], items[i])][items[i + 1]] += 1

    cur_st = items[-1]
    prev_st = items[-2]
    row = trans_1.get(cur_st, Counter())
    tot = sum(row.values()) or 1
    print(f"# 🔗 MARKOV DISCRETE STATE LENS — {label} ({len(items)} events, {len(set(items))} unique)")
    print(f"# Current Tail: {prev_st} -> {cur_st} | Transition Entropy H={_shannon_entropy(row):.2f} bits")
    for st, cnt in row.most_common(top_k):
        print(f"  • {(cnt / tot) * 100:5.1f}% -> {st} (n={cnt})")
    return 0


_REMOTE_FUNNEL_PY = r"""
import datetime, json, sqlite3, sys
days = max(2, int(sys.argv[1]))
db_p = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else "/home/mike/www/mikelev.in/honeybot.db"
conn = sqlite3.connect(f"file:{db_p}?mode=ro", uri=True)
end_d = datetime.date.today()
span = [(end_d - datetime.timedelta(days=days - 1 - i)).isoformat() for i in range(days)]
d0, d1, idx_m = span[0], span[-1], {d: i for i, d in enumerate(span)}
tbls = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
_VALID_DOORS = {"mikelev.in", "pipulate.com", "pipulate.org", "npvg.org", "lpvg.org", "qamy.ai", "levinix.org", "levinix.com", "levinux.com", "sunpug.io", "guerillatech.com", "rfc9110.org", "rfc9110.com", "rfc9110.io", "rfc9111.io", "rfc9111.com", "rfc9111.org", "mike-levin.com", "mikelevinseo.com"}
metrics, doors, trans = {}, {}, []
def _clean_door(dom):
    h = str(dom or "").strip().lower().split(":", 1)[0].rstrip(".").removeprefix("www.")
    return h if h in _VALID_DOORS else ""
def _bump(k, dy, n_v, p_v):
    if str(dy) in idx_m:
        a = metrics.setdefault(k, [[0, 0] for _ in range(days)])[idx_m[str(dy)]]
        a[0], a[1] = a[0] + int(n_v or 0), a[1] + int(p_v or 0)
def _door(dom, kind, dy, n_v, p_v):
    if dom and str(dy) in idx_m:
        r = doors.setdefault(dom, {x: [0] * days for x in ("air_n", "air_p", "exe_n", "exe_p")})
        r[f"{kind}_n"][idx_m[str(dy)]] += int(n_v or 0)
        r[f"{kind}_p"][idx_m[str(dy)]] += int(p_v or 0)
has_dm = "daily_metrics" in tbls and (conn.execute("SELECT COUNT(*) FROM daily_metrics").fetchone() or [0])[0] > 0
if has_dm:
    dm_cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_metrics)").fetchall()}
    p_col = "unique_ips" if "unique_ips" in dm_cols else "count"
    for m, dm, dy, c, u in conn.execute(f"SELECT metric, dim, day, count, {p_col} FROM daily_metrics WHERE day BETWEEN ? AND ?", (d0, d1)):
        if m in ("curl_airlock", "curl_exec"):
            cd = _clean_door(dm)
            if cd:
                _bump(m, dy, c, u)
                _door(cd, "air" if m == "curl_airlock" else "exe", dy, c, u)
        else:
            _bump(m, dy, c, u)
    if "daily_transitions" in tbls:
        trans = [[f, t, int(c)] for f, t, c in conn.execute("SELECT from_state, to_state, SUM(count) FROM daily_transitions WHERE day BETWEEN ? AND ? GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 20", (d0, d1))]
    mode = "live_metrics"
else:
    if "pirate_logs" in tbls:
        [_bump("ids_pirate", dy, c, u) for dy, c, u in conn.execute("SELECT date, SUM(count), COUNT(DISTINCT ip_id) FROM pirate_logs WHERE date BETWEEN ? AND ? GROUP BY date", (d0, d1))]
    if "telemetry" in tbls:
        [_bump("md_negotiated", dy, c, u) for dy, c, u in conn.execute("SELECT t.date, SUM(t.count), COUNT(DISTINCT t.ip_id) FROM telemetry t JOIN ips i ON t.ip_id = i.id WHERE t.served_md = 1 AND t.date BETWEEN ? AND ? AND i.value NOT LIKE '127.%' AND i.value NOT LIKE '10.%' AND i.value NOT LIKE '192.168.%' GROUP BY t.date", (d0, d1))]
    if "daily_logs" in tbls:
        [_bump(m, dy, c, u) for m, dy, c, u in conn.execute("SELECT CASE WHEN p.value IN ('/brain.zip', '/book.zip') THEN 'archive_dl' ELSE 'social_out' END, l.date, SUM(l.count), COUNT(DISTINCT l.ip_id) FROM daily_logs l JOIN paths p ON l.path_id = p.id JOIN ips i ON l.ip_id = i.id WHERE l.date BETWEEN ? AND ? AND ((p.value IN ('/brain.zip', '/book.zip') AND l.status BETWEEN 200 AND 299) OR ((p.value IN ('/discord', '/discord/', '/live', '/live/') OR p.value LIKE '/discord?%' OR p.value LIKE '/live?%' OR p.value LIKE '/go/%') AND l.status BETWEEN 200 AND 399)) AND i.value NOT LIKE '127.%' AND i.value NOT LIKE '10.%' AND i.value NOT LIKE '192.168.%' GROUP BY 1, 2", (d0, d1))]
    if "domain_daily_logs" in tbls:
        for knd, dom, dy, c, u in conn.execute("SELECT CASE WHEN p.value IN ('/', '/install.sh') THEN 'air' ELSE 'exe' END, d.value, ddl.date, SUM(ddl.count), COUNT(DISTINCT ddl.ua_id) FROM domain_daily_logs ddl JOIN domains d ON ddl.domain_id = d.id JOIN paths p ON ddl.path_id = p.id JOIN user_agents ua ON ddl.ua_id = ua.id WHERE ddl.date BETWEEN ? AND ? AND ddl.status BETWEEN 200 AND 299 AND ((p.value IN ('/', '/install.sh') AND (ua.value LIKE 'curl/%' OR ua.value LIKE 'Wget/%')) OR ((p.value IN ('/manifest.txt', '/key.rot') OR p.value LIKE '%src=install%') AND lower(ua.value) NOT LIKE '%bot%')) GROUP BY 1, 2, 3", (d0, d1)):
            cd = _clean_door(dom)
            if cd:
                _bump("curl_airlock" if knd == "air" else "curl_exec", dy, c, u)
                _door(cd, knd, dy, c, u)
    if "referrer_daily_logs" in tbls:
        [_bump(m, dy, c, u) for m, dy, c, u in conn.execute("SELECT CASE WHEN ref_apex IN ('youtube.com', 'youtu.be') THEN 'yt_referral_human' ELSE 'social_in' END, date, SUM(human_count), SUM(unique_ips) FROM referrer_daily_logs WHERE date BETWEEN ? AND ? AND human_count > 0 AND ref_apex IN ('youtube.com', 'youtu.be', 't.co', 'x.com', 'twitter.com', 'linkedin.com', 'lnkd.in', 'reddit.com', 'facebook.com', 'bsky.app', 'news.ycombinator.com', 'lobste.rs') GROUP BY 1, 2", (d0, d1))]
    mode = "live_derived"
bundles = []
if "pulse_events" in tbls:
    try:
        import os, pathlib
        os.environ["HONEYBOT_DB_READONLY"] = "1"
        for cand in (str(pathlib.Path(db_p).resolve().parent / "scripts"), "/home/mike/www/mikelev.in/scripts", "remotes/honeybot/scripts"):
            if pathlib.Path(cand, "db.py").is_file() and cand not in sys.path:
                sys.path.insert(0, cand)
        from db import HoneyDB
        h_ro = HoneyDB(db_p, read_only=True)
        if hasattr(h_ro, "get_hot_bundles"):
            bundles = h_ro.get_hot_bundles(window_sec=120, days=min(7, days), limit=8)
    except Exception:
        bundles = []
print(json.dumps({"status": mode, "span": span, "metrics": metrics, "doors": doors, "transitions": trans, "bundles": bundles}))
"""


def _river_next_day(vals: list[int]) -> float:
    model = preprocessing.StandardScaler() | linear_model.LinearRegression(optimizer=optim.SGD(0.02))
    ew = stats.EWMean(fading_factor=0.35)
    for i, v in enumerate(vals):
        if i > 0:
            model.learn_one({"t": float(i), "prev": float(vals[i - 1]), "ewma": float(ew.get() or v)}, float(v))
        ew.update(float(v))
    return max(0.0, float(model.predict_one({"t": float(len(vals)), "prev": float(vals[-1]), "ewma": float(ew.get() or vals[-1])}))) if len(vals) >= 2 else float(vals[-1] if vals else 0.0)


def run_funnel_compass(days: int = 14, top_k: int = 5) -> int:
    db_ov, host = os.environ.get("PIPULATE_HONEYBOT_DB", "").strip(), os.environ.get("PIPULATE_HONEYBOT_HOST", "honeybot")
    cmd = [sys.executable, "-", str(int(days)), db_ov] if (db_ov and Path(db_ov).is_file()) else ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", host, "python3", "-", str(int(days))]
    res = subprocess.run(cmd, input=_REMOTE_FUNNEL_PY, capture_output=True, text=True, timeout=6, check=False)
    snap = json.loads(res.stdout.strip()) if res.returncode == 0 and (res.stdout or "").strip() else {"status": "offline", "span": [], "metrics": {}, "doors": {}, "transitions": []}
    span = snap.get("span") or []
    n_d, m_map = len(span) or max(2, int(days)), snap.get("metrics") or {}
    def _np(key: str) -> tuple[list[int], list[int]]:
        arr = m_map.get(key) or [[0, 0] for _ in range(n_d)]
        return [int(x[0]) for x in arr], [int(x[1]) for x in arr]
    air_n, air_p = _np("curl_airlock")
    exe_n, exe_p = _np("curl_exec")
    less_n, less_p = [max(0, a - e) for a, e in zip(air_n, exe_n)], [max(0, a - e) for a, e in zip(air_p, exe_p)]
    cmd_np, paid_np = _np("yt_chat_cmd"), _np("paid_click")
    tracks = [("yt_arrive", *_np("yt_arrive")), ("yt_chat", *_np("yt_chat")), *([("yt_chat_cmd", *cmd_np)] if sum(cmd_np[0]) > 0 else []), ("yt_referral_human", *_np("yt_referral_human")), ("archive_dl", *_np("archive_dl")), ("curl_less_inspect", less_n, less_p), ("curl_bash_exec", exe_n, exe_p), ("social_in", *_np("social_in")), ("social_out", *_np("social_out")), *([("paid_click", *paid_np)] if sum(paid_np[0]) > 0 else []), ("md_negotiated", *_np("md_negotiated")), ("ids_pirate", *_np("ids_pirate"))]
    print(f"# 🧭 PIPULATE DIRECTIONAL VELOCITY & RIVER FUNNEL ({n_d}d: {span[0] + '..' + span[-1] if span else n_d} | status={snap.get('status')})")
    print("\n## 1. Daily Directional Counters (Sparkline, OLS Slope, N Hits / P Daily IPs, River t+1)")
    slopes = {}
    for name, nv, pv in tracks:
        st = slopes[name] = compute_ols_velocity(nv)
        print(f"  • {name:<18s} {(render_sparkline(nv, width=14) or '—'):<14s} {st['arrow']} {st['slope']:+6.2f}/d | N={int(st['total']):5d}, P={sum(pv):4d} IPs | river_t+1={_river_next_day(nv):5.1f}")
    print("\n## 2. Sun Pug Per-Door Airlock Split (curl | less vs. curl | bash)")
    doors = snap.get("doors") or {}
    for dk in sorted(doors, key=lambda k: sum(doors[k]["air_n"]) + sum(doors[k]["exe_n"]), reverse=True)[: max(4, top_k)]:
        dn, dp, en = doors[dk]["air_n"], doors[dk]["air_p"], doors[dk]["exe_n"]
        st, tot_a, tot_e = compute_ols_velocity(dn), sum(dn), sum(en)
        print(f"  • {dk:<18s} {render_sparkline(dn, width=14):<14s} {st['arrow']} {st['slope']:+6.2f}/d | less={sum(max(0, a - e) for a, e in zip(dn, en)):4d}, bash={tot_e:4d} ({(100.0 * tot_e / tot_a if tot_a else 0.0):3.0f}% exec, P={sum(dp):3d} IPs)")
    if not doors:
        print("  • (No curl/Wget door hits recorded in window yet)")
    print("\n## 3. Markov Transition Odds & What To Do Next")
    f_tot = Counter()
    for f_s, _, cnt in (snap.get("transitions") or []):
        f_tot[f_s] += int(cnt)
    for f_s, t_s, cnt in (snap.get("transitions") or [])[:top_k]:
        print(f"  • P({t_s} | {f_s}) = {(100.0 * int(cnt) / max(1, f_tot[f_s])):5.1f}% (n={cnt})")
    acts = []
    if sum(less_n) > sum(exe_n) and sum(less_n) >= 1:
        acts.append(f"Inspect-only `curl | less` leads `curl | bash` ({sum(less_n)} vs {sum(exe_n)}) -> run `markov --quests` to inspect door -> L3 trails.")
    acts.append(f"`brain.zip` slope is {slopes['archive_dl']['slope']:+.2f}/d -> {'keep `/book.zip` synced on publish (P0.67).' if slopes['archive_dl']['slope'] > 0 else 'spotlight `brain.zip` + WOPR hook in next Norma cone.'}")
    if slopes["ids_pirate"]["total"] > 0:
        acts.append(f"Pirate 4xx/418 scanner pressure active (N={int(slopes['ids_pirate']['total'])}) -> prime HTTP 418 Rickroll Weebo show (P0.80).")
    for idx, act in enumerate(acts[:3], 1):
        print(f"  {idx}. NEXT: {act}")
    print("\n## 4. 🔥 Hot Bundles (Cross-Surface & Multi-Step Coincidences, 7d)")
    bundles = snap.get("bundles") or []
    for b in bundles[:top_k]:
        r_lbl = "->".join(f"L{r}" for r in (b.get("rings") or [1]))
        q_lbl = f" +{b['quests']}q" if b.get("quests") else ""
        chain = " -> ".join(f"{s['surface']}:{s['event']}" + (f"({s['dim']})" if s.get("dim") else "") + (f"@+{s['dt']}s" if s.get("dt") else "") for s in (b.get("steps") or [])[:6])
        print(f"  • [{b.get('iso', '')} | {b.get('bits', 0):.1f}b | {r_lbl}{q_lbl}] {chain}")
    if not bundles:
        print("  • (0 multi-step bundles in 7d window yet — pulse_events armed for live YT + wire coincidences)")
    return 0


_SOCIAL_SHORT_ALIASES = {
    "x": "x.com", "twitter": "x.com", "t.co": "x.com", "li": "linkedin.com", "linkedin": "linkedin.com", "lnkd.in": "linkedin.com",
    "yt": "youtube.com", "youtube": "youtube.com", "youtu.be": "youtube.com", "fb": "facebook.com", "facebook": "facebook.com",
    "hn": "news.ycombinator.com", "hackernews": "news.ycombinator.com", "bsky": "bsky.app", "bluesky": "bsky.app",
    "reddit": "reddit.com", "discord": "discord.com", "lobsters": "lobste.rs",
}

_REMOTE_SOCIAL_PY = r"""
import datetime, json, sqlite3, sys
days, lim = max(2, int(sys.argv[1])), max(10, int(sys.argv[4]))
plat_f = "" if sys.argv[2].strip().lower() in ("", "all", "-") else sys.argv[2].strip().lower()
dom_csv = "" if sys.argv[3].strip().lower() in ("", "all", "-") else sys.argv[3].strip().lower()
db_p = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else "/home/mike/www/mikelev.in/honeybot.db"
conn = sqlite3.connect(f"file:{db_p}?mode=ro", uri=True)
end_d = datetime.date.today()
span = [(end_d - datetime.timedelta(days=days - 1 - i)).isoformat() for i in range(days)]
d0, d1, idx_m = span[0], span[-1], {d: i for i, d in enumerate(span)}
if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='referrer_daily_logs'").fetchone():
    print(json.dumps({"status": "sync_pending", "span": span, "platforms": {}, "edges": []}))
    raise SystemExit(0)
_FOLD = {"t.co": "x.com", "twitter.com": "x.com", "lnkd.in": "linkedin.com", "youtu.be": "youtube.com", "fb.com": "facebook.com", "fb.me": "facebook.com", "redd.it": "reddit.com", "ycombinator.com": "news.ycombinator.com"}
_SOC = {"x.com", "linkedin.com", "youtube.com", "reddit.com", "facebook.com", "discord.com", "bsky.app", "news.ycombinator.com", "lobste.rs", "threads.net", "instagram.com", "tiktok.com"}
dom_set = {x for x in dom_csv.split(",") if x}
plats, edges = {}, {}
sql = "SELECT rdl.date, rdl.ref_apex, d.value, p.value, rdl.human_count, rdl.unique_ips, rdl.sample_referrer FROM referrer_daily_logs rdl JOIN domains d ON rdl.domain_id = d.id JOIN paths p ON rdl.path_id = p.id WHERE rdl.date BETWEEN ? AND ? AND rdl.human_count > 0"
for dy, raw_ap, dom, p_s, hum, ips, s_ref in conn.execute(sql, (d0, d1)):
    ap, d_clean = _FOLD.get((raw_ap or "").lower(), (raw_ap or "").lower()), (dom or "").lower().rstrip(".").removeprefix("www.")
    if ap not in _SOC or (plat_f and ap != plat_f) or (dom_set and d_clean not in dom_set) or str(dy) not in idx_m:
        continue
    h_i = int(hum or 0)
    i, ip_i = idx_m[str(dy)], min(h_i, int(ips or 0))
    pr = plats.setdefault(ap, {"n": [0] * days, "p": [0] * days, "paths": set()})
    pr["n"][i] += h_i; pr["p"][i] += ip_i; pr["paths"].add((d_clean, p_s))
    er = edges.setdefault((ap, d_clean, p_s), {"n": [0] * days, "p": [0] * days, "ref": s_ref or ap})
    er["n"][i] += h_i; er["p"][i] += ip_i
    if s_ref and len(s_ref) > len(er["ref"]):
        er["ref"] = s_ref
p_out = {k: {"n": v["n"], "p": v["p"], "paths": len(v["paths"])} for k, v in plats.items()}
e_out = [[ap, dm, p_s, v["n"], v["p"], v["ref"]] for (ap, dm, p_s), v in edges.items()]
e_out.sort(key=lambda x: (sum(x[3]), sum(x[4]), x[3][-1]), reverse=True)
print(json.dumps({"status": "live", "span": span, "platforms": p_out, "edges": e_out[:lim]}))
"""


def run_social_article_velocity(target_spec: str = "1", days: int = 14, top_k: int = 12, platform: str = "", target_explicit: bool = False) -> int:
    try:
        targets_list = _resolve_targets(target_spec)
    except ValueError as exc:
        print(f"❌ markov: {exc}", file=sys.stderr)
        return 1
    pub_doms = _target_public_domains(targets_list)
    if not pub_doms:
        print(f"# 📱 SOCIAL -> ARTICLE COMPOUND-KEY VELOCITY ({targets_list[0]['name']} — local/air-gapped target)")
        return 0
    slug_map = {}
    for t_cfg in targets_list:
        c_dir = t_cfg["posts_dir"] / "_context"
        for jf in (c_dir.glob("*.json") if c_dir.is_dir() else ()):
            m = _DATED_STEM_RE.match(jf.stem)
            if m:
                try:
                    d = json.loads(jf.read_text(encoding="utf-8"))
                    slug_map[m.group(2).lower()] = {"kws": [_norm_topic(k) for k in (d.get("kw") or []) if _norm_topic(k)]}
                except Exception:
                    pass
    raw_p = (platform or "").strip().lower().removeprefix("www.")
    plat_f, dom_csv, lim = _SOCIAL_SHORT_ALIASES.get(raw_p, raw_p), (",".join(pub_doms) if target_explicit else ""), max(60, int(top_k) * 4)
    plat_arg, dom_arg = re.sub(r"[^a-z0-9._-]", "", plat_f) or "all", re.sub(r"[^a-z0-9.,_-]", "", dom_csv) or "all"
    db_ov, host = os.environ.get("PIPULATE_HONEYBOT_DB", "").strip(), os.environ.get("PIPULATE_HONEYBOT_HOST", "honeybot")
    cmd = [sys.executable, "-", str(int(days)), plat_arg, dom_arg, str(lim), db_ov] if (db_ov and Path(db_ov).is_file()) else ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", host, "python3", "-", str(int(days)), plat_arg, dom_arg, str(lim)]
    res = subprocess.run(cmd, input=_REMOTE_SOCIAL_PY, capture_output=True, text=True, timeout=6, check=False)
    snap = json.loads(res.stdout.strip()) if res.returncode == 0 and (res.stdout or "").strip() else {"status": "offline", "span": [], "platforms": {}, "edges": []}
    span, plats, edges = snap.get("span") or [], snap.get("platforms") or {}, snap.get("edges") or []
    n_d, p_lbl = len(span) or max(2, int(days)), (f" | platform={plat_f}" if plat_f else "")
    print(f"# 📱 SOCIAL -> ARTICLE COMPOUND-KEY VELOCITY ({n_d}d: {span[0] + '..' + span[-1] if span else n_d}{p_lbl} | status={snap.get('status')})")
    print("\n## 1. Platform Cohort Sparklines (OLS Slope, N Human Clicks / P Daily IPs, Articles, River t+1)")
    for ap in sorted(plats, key=lambda k: (sum(plats[k]["n"]), sum(plats[k]["p"])), reverse=True):
        nv, pv, st = plats[ap]["n"], plats[ap]["p"], compute_ols_velocity(plats[ap]["n"])
        print(f"  • {ap:<20s} {(render_sparkline(nv, width=14) or '—'):<14s} {st['arrow']} {st['slope']:+6.2f}/d | N={int(st['total']):4d}, P={sum(pv):4d} IPs, arts={plats[ap]['paths']:3d} | river_t+1={_river_next_day(nv):5.1f}")
    if not plats:
        print("  • (No human social referrals recorded in window)")
    print(f"\n## 2. Top (Platform, Article) Compound-Key Trajectories (Top {top_k})")
    kw_daily: dict[str, list[int]] = {}
    for _, _, path_s, nv, _, _ in edges:
        for k in (kw for kw in _match_path_keywords(path_s, slug_map) if not _is_internal_artifact(kw)):
            arr = kw_daily.setdefault(k, [0] * len(nv))
            for i, val in enumerate(nv):
                arr[i] += int(val)
    for ap, dom, path_s, nv, pv, _ in edges[:top_k]:
        st, kws = compute_ols_velocity(nv), (", ".join(_match_path_keywords(path_s, slug_map)[:3]) or "surface")
        short_t = f"{dom}{path_s}" if len(f"{dom}{path_s}") <= 54 else f"{dom}{path_s[:51]}..."
        print(f"  • {ap:<14s} {(render_sparkline(nv, width=14) or '—'):<14s} {st['arrow']} {st['slope']:+5.2f}/d | N={int(st['total']):3d}, P={sum(pv):3d} | t+1={_river_next_day(nv):4.1f} | {short_t} -> ({kws})")
    if not edges:
        print("  • (No per-article social trajectories in window)")
    print("\n## 3. Social-Weighted Shard Topic Velocity (River Forecast)")
    kw_ranked = sorted(kw_daily.items(), key=lambda kv: (sum(kv[1]), compute_ols_velocity(kv[1])["slope"]), reverse=True)[: min(8, top_k)]
    for k, kv in kw_ranked:
        st = compute_ols_velocity(kv)
        print(f"  • {k:<24s} {(render_sparkline(kv, width=14) or '—'):<14s} {st['arrow']} {st['slope']:+5.2f}/d | social_N={int(st['total']):4d} | river_t+1={_river_next_day(kv):4.1f}")
    if not kw_ranked:
        print("  • (No shard-matched social topics in window)")
    return 0


_REMOTE_QUESTS_PY = r"""
import datetime, json, sqlite3, sys
days, lim = max(2, int(sys.argv[1])), max(5, int(sys.argv[2]))
db_p = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] not in ("", "all", "-") else "/home/mike/www/mikelev.in/honeybot.db"
conn = sqlite3.connect(f"file:{db_p}?mode=ro", uri=True)
end_d = datetime.date.today()
span = [(end_d - datetime.timedelta(days=days - 1 - i)).isoformat() for i in range(days)]
d0, d1, idx_m = span[0], span[-1], {d: i for i, d in enumerate(span)}
tbls = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
if "daily_quests" not in tbls:
    print(json.dumps({"status": "sync_pending", "span": span, "series": {}, "doors": [], "party": []}))
    raise SystemExit(0)
ser = {k: [0] * days for k in ("l1_all", "deep_2p", "l2_plus", "l3_unlock")}
doors = {}
rows = conn.execute("SELECT day, actor_tag, entry_ref, first_dim, last_dim, max_ring, steps, pages, flags, first_ts, last_ts FROM daily_quests WHERE day BETWEEN ? AND ?", (d0, d1)).fetchall()
for dy, tg, eref, f_dm, l_dm, mr, stp, pgs, flg, f_ts, l_ts in rows:
    if str(dy) not in idx_m:
        continue
    i, mr_i, pg_i = idx_m[str(dy)], int(mr or 1), int(pgs or 0)
    ser["l1_all"][i] += 1
    ser["deep_2p"][i] += 1 if pg_i >= 2 else 0
    ser["l2_plus"][i] += 1 if mr_i >= 2 else 0
    ser["l3_unlock"][i] += 1 if mr_i >= 3 else 0
    dk = eref or "(direct/internal)"
    dr = doors.setdefault(dk, [0, 0, 0, 0, 0])
    dr[0] += 1; dr[1] += (1 if pg_i >= 2 else 0); dr[2] += (1 if mr_i >= 2 else 0); dr[3] += (1 if mr_i >= 3 else 0); dr[4] += pg_i
d_out = [[k, *v] for k, v in sorted(doors.items(), key=lambda kv: (kv[1][2], kv[1][3], kv[1][0]), reverse=True)[:10]]
cand = [r for r in rows if int(r[5] or 1) >= 2 or int(r[7] or 0) >= 2 or int(r[6] or 0) >= 2] or list(rows)
cand.sort(key=lambda r: (str(r[0]), int(r[5] or 1), int(r[7] or 0), int(r[6] or 0), int(r[10] or 0)), reverse=True)
party, has_pe = [], "pulse_events" in tbls
for dy, tg, eref, f_dm, l_dm, mr, stp, pgs, flg, f_ts, l_ts in cand[:lim]:
    trail = []
    if has_pe and int(f_ts or 0) > 0:
        for _, sf, ev, dm in conn.execute("SELECT ts, surface, event, dim FROM pulse_events WHERE actor_tag = ? AND ts BETWEEN ? AND ? ORDER BY ts ASC, id ASC", (tg, int(f_ts) - 5, int(l_ts) + 5)):
            if ev.startswith("ref:"):
                continue
            tok = (dm.removeprefix("mikelev.in") or "/") if ev == "visit:human" else (f"{ev}({dm})" if dm else ev)
            if not trail or trail[-1] != tok:
                trail.append(tok)
    if not trail:
        trail = list(dict.fromkeys((x.removeprefix("mikelev.in") or "/") for x in (f_dm, l_dm) if x))
    party.append([dy, tg, eref or "direct", int(mr or 1), int(pgs or 0), int(stp or 0), max(0, int(l_ts or 0) - int(f_ts or 0)), flg or "visit", trail[:5], len(trail)])
print(json.dumps({"status": "live", "span": span, "series": ser, "doors": d_out, "party": party}))
"""


def _fmt_dwell(sec: int) -> str:
    return f"{sec / 3600:.1f}h" if sec >= 3600 else (f"{sec // 60}m" if sec >= 60 else f"{sec}s")


def run_quest_party_roster(target_spec: str = "1", days: int = 14, top_k: int = 10) -> int:
    try:
        targets_list = _resolve_targets(target_spec)
    except ValueError as exc:
        print(f"❌ markov: {exc}", file=sys.stderr)
        return 1
    slug_map = {}
    for t_cfg in targets_list:
        c_dir = t_cfg["posts_dir"] / "_context"
        for jf in (c_dir.glob("*.json") if c_dir.is_dir() else ()):
            m = _DATED_STEM_RE.match(jf.stem)
            if m:
                try:
                    d = json.loads(jf.read_text(encoding="utf-8"))
                    slug_map[m.group(2).lower()] = [_norm_topic(k) for k in (d.get("kw") or []) if _norm_topic(k) and not _is_internal_artifact(k)]
                except Exception:
                    pass
    db_ov, host = os.environ.get("PIPULATE_HONEYBOT_DB", "").strip(), os.environ.get("PIPULATE_HONEYBOT_HOST", "honeybot")
    cmd = [sys.executable, "-", str(int(days)), str(max(5, int(top_k))), db_ov] if (db_ov and Path(db_ov).is_file()) else ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", host, "python3", "-", str(int(days)), str(max(5, int(top_k))), "all"]
    res = subprocess.run(cmd, input=_REMOTE_QUESTS_PY, capture_output=True, text=True, timeout=6, check=False)
    snap = json.loads(res.stdout.strip()) if res.returncode == 0 and (res.stdout or "").strip() else {"status": "offline", "span": [], "series": {}, "doors": [], "party": []}
    span, ser, doors, party = snap.get("span") or [], snap.get("series") or {}, snap.get("doors") or [], snap.get("party") or []
    n_d = len(span) or max(2, int(days))
    print(f"# 🗡️ DAILY ADVENTURER QUEST LOG & COHORT SURFER ({n_d}d: {span[0] + '..' + span[-1] if span else n_d} | status={snap.get('status')})")
    print("\n## 1. Daily Quest Ring Velocity (Sparkline, OLS Slope, Adventurers, River t+1)")
    for key, lbl in (("l1_all", "L1_all_visitors"), ("deep_2p", "L2_deep_readers"), ("l2_plus", "L2_quest_explorers"), ("l3_unlock", "L3_sanctum_unlocks")):
        vals = ser.get(key) or [0] * n_d
        st = compute_ols_velocity(vals)
        print(f"  • {lbl:<20s} {(render_sparkline(vals, width=14) or '—'):<14s} {st['arrow']} {st['slope']:+6.2f}/d | P={int(st['total']):5d} actors | river_t+1={_river_next_day(vals):5.1f}")
    print("\n## 2. Entry-Door -> Quest Conversion Odds (L2+ Explorer & 2+ Page Rates)")
    for dk, tot_a, deep_a, l2_a, l3_a, tot_pg in doors:
        print(f"  • {dk:<20s} | P={int(tot_a):4d} | L2+={int(l2_a):3d} ({100.0 * int(l2_a) / max(1, int(tot_a)):4.1f}%) | 2+pg={int(deep_a):3d} ({100.0 * int(deep_a) / max(1, int(tot_a)):4.1f}%) | L3={int(l3_a):2d} | avg_pg={int(tot_pg) / max(1, int(tot_a)):.2f}")
    if not doors:
        print("  • (No daily_quests rows recorded in window yet)")
    print(f"\n## 3. Recent Adventurer Party Roster (Top {top_k} Zero-PII (day, actor_tag) Trails)")
    for dy, tg, eref, mr, pgs, stp, dw_s, flg, trail, t_len in party[:top_k]:
        kws = []
        for step_s in trail:
            leaf = step_s.strip("/").rsplit("/", 1)[-1].lower()
            hit = slug_map.get(leaf) or next((v for sl, v in slug_map.items() if len(leaf) >= 12 and sl.startswith(leaf)), [])
            for k in hit[:2]:
                if k not in kws:
                    kws.append(k)
        short_steps = [s if len(s) <= 34 else (s[:31] + "...") for s in trail]
        more_s = f" (+{int(t_len) - len(short_steps)} more)" if int(t_len) > len(short_steps) else ""
        kw_s = f" | topics=({', '.join(kws[:3])})" if kws else ""
        print(f"  • [{dy} | {tg:<9s} | L{mr} {flg:<12s} | {pgs:2d}p/{_fmt_dwell(int(dw_s)):>5s} | in:{eref}] {' -> '.join(short_steps)}{more_s}{kw_s}")
    if not party:
        print("  • (No adventurer trails recorded in window yet)")
    return 0


def run_demo_series() -> int:
    synth_num = [
        f"t{i} {100.0 + 0.8 * i + (3.5 if i % 4 in (0, 1) else -2.0):.2f}"
        for i in range(1, 25)
    ]
    return analyze_generic_series(synth_num, label="demo-quant-series", top_k=4)


def run_outlines_overview(target_spec: str = "all") -> int:
    try:
        targets_list = _resolve_targets("all" if target_spec == "1" else target_spec)
    except ValueError as exc:
        print(f"❌ markov: {exc}", file=sys.stderr)
        return 1
    print(f"# 📚 JEKYLL CREATIVE TRACKS & OUTLINE MATRIX ({len(targets_list)} declared)")
    for t in targets_list:
        p_dir, root = t["posts_dir"], t["posts_dir"].parent
        md_n = sum(1 for mf in (p_dir.glob("*.md") if p_dir.is_dir() else ()) if _DATED_STEM_RE.match(mf.stem))
        ctx_n = sum(1 for jf in ((p_dir / "_context").glob("*.json") if (p_dir / "_context").is_dir() else ()) if _DATED_STEM_RE.match(jf.stem))
        out_p = root / "OUTLINE.md"
        out_hdr = next((ln.lstrip("# ").strip() for ln in out_p.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip().startswith("#")), "OUTLINE.md") if out_p.is_file() else ""
        git_lbl = "git" if (root / ".git").exists() else ("dir-only" if root.is_dir() else "unseeded")
        out_lbl = f"🗺️ {out_hdr}" if out_hdr else "⚠️ no OUTLINE.md"
        print(f"  • [{t['key']:>2s}={t['alias']:<8s}] posts={md_n:4d} (shards={ctx_n:4d}) | {git_lbl:<8s} | {out_lbl}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Markov Transition Matrix & River Online Streaming ML CLI for context.txt."
    )
    parser.add_argument("source", nargs="?", default=None, help="Optional file path of series data.")
    parser.add_argument(
        "-t", "--target", action="append", default=None, metavar="SPEC",
        help="Target spec from blogs.json: key/alias, comma list, range, or all (repeatable; default: 1).",
    )
    parser.add_argument("-k", "--top", type=int, default=5, help="Top K transitions to show (default: 5).")
    parser.add_argument("--radar", action="store_true", help="Show newest Compound-Key (ref_apex, domain, path) discoveries.")
    parser.add_argument("--ai", action="store_true", help="Filter --radar to Search & AI referral velocity.")
    parser.add_argument("--links", action="store_true", help="Filter --radar to clickable non-search/non-AI referring web URLs.")
    parser.add_argument("--social", action="store_true", help="Show per-(platform, article) social sparklines, OLS slopes, & River velocity (or filter --radar).")
    parser.add_argument("--platform", type=str, default="", help="Filter --social to one platform (e.g. x, linkedin, youtube, reddit, hn, fb).")
    parser.add_argument("--by-domain", action="store_true", help="Aggregate --radar velocity by referring domain.")
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days for --radar / --funnel (default: 30).")
    parser.add_argument("--funnel", action="store_true", help="Show daily directional sparklines (N/P), OLS slopes, & River/Markov funnel.")
    parser.add_argument("--quests", action="store_true", help="Show daily (day, actor_tag) Adventurer cohorts, door conversions, & party trails.")
    parser.add_argument("--stdin", action="store_true", help="Read series observations from stdin.")
    parser.add_argument("--outlines", action="store_true", help="Show 80/20 OUTLINE.md & shard matrix across Jekyll tracks.")
    parser.add_argument("--demo-series", action="store_true", help="Run built-in numeric time-series verification.")
    args = parser.parse_args()
    target_spec = ",".join(args.target) if args.target else "1"
    src_cmd = (args.source or "").strip().lower()
    if args.outlines or (src_cmd in ("outlines", "outline") and not Path(args.source).is_file()):
        return run_outlines_overview(target_spec=target_spec)
    if args.quests or (src_cmd in ("quests", "quest") and not Path(args.source).is_file()):
        q_days = 14 if "--days" not in sys.argv else args.days
        q_top = 10 if ("-k" not in sys.argv and "--top" not in sys.argv) else args.top
        return run_quest_party_roster(target_spec=target_spec, days=q_days, top_k=q_top)
    if args.funnel or (src_cmd in ("funnel", "sparklines") and not Path(args.source).is_file()):
        return run_funnel_compass(days=14 if "--days" not in sys.argv else args.days, top_k=args.top)
    if (args.social or args.platform or (src_cmd == "social" and not Path(args.source).is_file())) and not (args.radar or args.by_domain):
        soc_days = 14 if "--days" not in sys.argv else args.days
        soc_top = 12 if ("-k" not in sys.argv and "--top" not in sys.argv) else args.top
        return run_social_article_velocity(target_spec=target_spec, days=soc_days, top_k=soc_top, platform=args.platform, target_explicit=bool(args.target))
    if args.radar or args.ai or args.links or args.social or args.by_domain or (src_cmd == "radar" and not Path(args.source).is_file()):
        return run_referral_radar(target_spec=target_spec, days=args.days, top_k=max(15, args.top), links_only=args.links, ai_only=args.ai, social_only=args.social, by_domain=args.by_domain)

    if args.demo_series:
        return run_demo_series()
    if args.stdin:
        return analyze_generic_series(sys.stdin.read().splitlines(), label="stdin", top_k=args.top)
    if args.source:
        p = Path(args.source).expanduser()
        if not p.is_file():
            print(f"❌ markov: file not found: {p}", file=sys.stderr)
            return 1
        return analyze_generic_series(p.read_text(encoding="utf-8").splitlines(), label=p.name, top_k=args.top)
    return analyze_corpus_shards(target_spec=target_spec, top_k=args.top)


if __name__ == "__main__":
    sys.exit(main())
