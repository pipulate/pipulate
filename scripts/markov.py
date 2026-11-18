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


def _resolve_posts_dir(target_spec: str) -> tuple[str, Path]:
    if TARGETS_FILE.is_file():
        try:
            targets = json.loads(TARGETS_FILE.read_text(encoding="utf-8"))
            if target_spec in targets:
                cfg = targets[target_spec]
                p = Path(cfg["path"]).expanduser()
                if target_spec == "1" and (not (p / "_context").is_dir()) and (BRAIN_POSTS_DIR / "_context").is_dir():
                    return "MikeLev.in (2nd Brain)", BRAIN_POSTS_DIR
                return cfg.get("name", target_spec), p
            for k, cfg in targets.items():
                if str(cfg.get("alias", "")).lower() == target_spec.lower():
                    p = Path(cfg["path"]).expanduser()
                    if k == "1" and (not (p / "_context").is_dir()) and (BRAIN_POSTS_DIR / "_context").is_dir():
                        return "MikeLev.in (2nd Brain)", BRAIN_POSTS_DIR
                    return cfg.get("name", k), p
        except Exception:
            pass
    if DEFAULT_POSTS_DIR.is_dir():
        return "MikeLev.in (Default)", DEFAULT_POSTS_DIR
    if BRAIN_POSTS_DIR.is_dir():
        return "MikeLev.in (2nd Brain)", BRAIN_POSTS_DIR
    return "MikeLev.in (Default)", DEFAULT_POSTS_DIR


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


_REMOTE_REF_PY = """
import datetime, json, re, sqlite3, sys
days, lim = int(sys.argv[1]), int(sys.argv[2])
bkt_req = sys.argv[3] if len(sys.argv) > 3 else "all"
db_p = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else "/home/mike/www/mikelev.in/honeybot.db"
conn = sqlite3.connect(f"file:{db_p}?mode=ro", uri=True)
if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='referrer_radar'").fetchone():
    print(json.dumps({"status": "sync_pending", "obs_days": max(1, days), "total_edges": 0, "bucket_edges": 0, "bucket_domains": 0, "bucket_hits": 0, "demand": [], "radar": [], "edges": [], "domains": []}))
    raise SystemExit(0)
_AI_APEX = {"bing.com", "duckduckgo.com", "ddg.gg", "kagi.com", "baidu.com", "yahoo.com", "brave.com", "ecosia.org", "qwant.com", "sogou.com", "so.com", "naver.com", "seznam.cz", "mojeek.com", "startpage.com", "yep.com", "marginalia-search.com", "chatgpt.com", "openai.com", "claude.ai", "anthropic.com", "perplexity.ai", "you.com", "phind.com", "poe.com", "grok.com", "x.ai", "mistral.ai", "deepseek.com", "meta.ai", "genspark.ai", "exa.ai", "copilot.microsoft.com"}
_SOCIAL_APEX = {"t.co", "x.com", "twitter.com", "lnkd.in", "linkedin.com", "facebook.com", "fb.com", "instagram.com", "threads.net", "youtube.com", "youtu.be", "pinterest.com", "tiktok.com", "msn.com", "live.com"}
_NOISE_APEX = {"nip.io", "sslip.io", "verizon.net", "netcraft.com"}
_BAD_REF_RE = re.compile(r"/wp-admin|/wp-login|xmlrpc\.php|/\.env", re.I)
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
    https_u = [u for u in refs if "://" in u and u.split(":", 1)[0].lower() in ("http", "https") and not _BAD_REF_RE.search(u)]
    if not a:
        continue
    if a in _AI_APEX or a.startswith(("google.", "yandex.", "yahoo.")) or ".google." in a or ".yandex." in a or ".yahoo." in a or "googlequicksearchbox" in a:
        bkt = "ai"
    elif a in _SOCIAL_APEX or a.startswith(("com.", "org.", "net.")):
        bkt = "social"
    elif https_u and a not in _NOISE_APEX:
        bkt = "links"
    else:
        bkt = "other"
    if bkt_req in ("ai", "links") and bkt != bkt_req:
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


def analyze_corpus_shards(target_spec: str = "1", top_k: int = 5) -> int:
    target_name, posts_dir = _resolve_posts_dir(target_spec)
    context_dir = posts_dir / "_context"
    if not context_dir.is_dir():
        print(f"⚠️ markov: no _context shard directory at {context_dir}", file=sys.stderr)
        return 1

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
    for jf in context_dir.glob("*.json"):
        m = _DATED_STEM_RE.match(jf.stem)
        if not m:
            continue
        date_str, slug = m.group(1), m.group(2)
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        md_path = str(posts_dir / f"{jf.stem}.md")
        sort_order = 0
        if md_path in fm_cache and len(fm_cache[md_path]) >= 2:
            sort_order = int(fm_cache[md_path][1] or 0)
        tokens = 0
        if md_path in token_cache and len(token_cache[md_path]) >= 2:
            tokens = int(token_cache[md_path][1] or 0)
        kws = [_norm_topic(k) for k in (data.get("kw") or []) if _norm_topic(k)]
        subs = [_norm_topic(s) for s in (data.get("sub") or []) if _norm_topic(s)]
        if not kws and not subs:
            continue
        records.append({
            "stem": jf.stem,
            "date": date_str,
            "slug": slug,
            "sort_order": sort_order,
            "tokens": tokens,
            "kws": kws,
            "subs": subs,
            "lead": kws[0] if kws else subs[0],
        })

    if not records:
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

    # Online river EWMA momentum over the last 60 vs prior window
    recent_window = records[-30:]
    prior_window = records[-120:-30] if len(records) > 30 else records[:-5]
    recent_counts = Counter(k for r in recent_window for k in r["kws"])
    prior_counts = Counter(k for r in prior_window for k in r["kws"])
    r_len = max(1, len(recent_window))
    p_len = max(1, len(prior_window))

    momentum = []
    for topic, r_cnt in recent_counts.items():
        if r_cnt < 2 or _is_internal_artifact(topic):
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
    print("\n## 1. Current Trajectory (Last 3 Balls Thrown)")
    for r in last_3:
        kw_preview = ", ".join(r["kws"][:4])
        print(f"  • [{r['date']} #{r['sort_order']}] {r['slug']} -> ({kw_preview})")

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

    print("\n## 4. River Streaming Momentum Surge (Last 30 vs. Baseline)")
    for lift, r_cnt, topic in momentum[:top_k]:
        print(f"  • [+{lift:5.1f}x surge | {r_cnt:2d}/30 recent posts] {topic}")

    slug_map = {r["slug"].lower(): r for r in records}
    ext = _fetch_honeybot_referrals(days=30, limit=max(10, top_k * 2), force_refresh=False)
    print(f"\n## 5. Post-GSC HitTail External Demand & Shard Intent (30d | {ext.get('status', 'offline')})")
    if ext.get("demand"):
        for apex, dom, path_s, hits, hum, ips, _ in ext["demand"][:top_k]:
            kws = ", ".join(_match_path_keywords(path_s, slug_map)) or "non-post surface"
            print(f"  • [{apex:<16s} | N={hits:3d}, P={ips:2d} IPs] {dom}{path_s} -> ({kws})")
    elif ext.get("status") == "sync_pending":
        print("  • (Honeybot referrer_radar sync pending — run ytreboot to backfill honeybot.db)")
    else:
        print(f"  • (No external human referrals in window; source={ext.get('status', 'offline')})")
    return 0


def run_referral_radar(target_spec: str = "1", days: int = 30, top_k: int = 15, links_only: bool = False, ai_only: bool = False, by_domain: bool = False) -> int:
    _, posts_dir = _resolve_posts_dir(target_spec)
    slug_map = {}
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
    bkt = "ai" if ai_only else ("links" if links_only else "all")
    snap = _fetch_honeybot_referrals(days=days, limit=top_k, force_refresh=True, bucket=bkt)
    obs = snap.get("obs_days", days)
    if bkt in ("ai", "links") or by_domain:
        tag = "🤖 HONEYBOT SEARCH & AI" if bkt == "ai" else ("🔗 HONEYBOT CLICKABLE WEB" if bkt == "links" else "📡 HONEYBOT EXTERNAL")
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


def run_demo_series() -> int:
    synth_num = [
        f"t{i} {100.0 + 0.8 * i + (3.5 if i % 4 in (0, 1) else -2.0):.2f}"
        for i in range(1, 25)
    ]
    return analyze_generic_series(synth_num, label="demo-quant-series", top_k=4)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Markov Transition Matrix & River Online Streaming ML CLI for context.txt."
    )
    parser.add_argument("source", nargs="?", default=None, help="Optional file path of series data.")
    parser.add_argument("-t", "--target", type=str, default="1", help="Target blog key/alias (default: 1).")
    parser.add_argument("-k", "--top", type=int, default=5, help="Top K transitions to show (default: 5).")
    parser.add_argument("--radar", action="store_true", help="Show newest Compound-Key (ref_apex, domain, path) discoveries.")
    parser.add_argument("--ai", action="store_true", help="Filter --radar to Search & AI referral velocity.")
    parser.add_argument("--links", action="store_true", help="Filter --radar to clickable non-search/non-AI referring web URLs.")
    parser.add_argument("--by-domain", action="store_true", help="Aggregate --radar velocity by referring domain.")
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days for --radar (default: 30).")
    parser.add_argument("--stdin", action="store_true", help="Read series observations from stdin.")
    parser.add_argument("--demo-series", action="store_true", help="Run built-in numeric time-series verification.")
    args = parser.parse_args()
    if args.radar or args.ai or args.links or args.by_domain:
        return run_referral_radar(target_spec=args.target, days=args.days, top_k=max(15, args.top), links_only=args.links, ai_only=args.ai, by_domain=args.by_domain)

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
    return analyze_corpus_shards(target_spec=args.target, top_k=args.top)


if __name__ == "__main__":
    sys.exit(main())
