#!/usr/bin/env python3
"""
extract_404_ghosts.py
One-word `404` tree-shaker: syncs hubs & Next-10 pagination, loads all active +
retired + system + CSV redirect exclusions, drains non-pirate 404 ghosts from
Honeybot SQLite onto the 28 permanent hubs, reloads Honeybot Nginx RAM when
rules change, and prints a before/after Tree-Shaker Scoreboard.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common  # noqa: E402
import generate_hubs  # noqa: E402
import generate_redirects  # noqa: E402
import sanitize_redirects  # noqa: E402

PROTECTED_SYSTEM_PATHS = (
    "/", "/index.html", "/feed.xml", "/llms.txt", "/robots.txt",
    "/sitemap.xml", "/sitemap-core.xml", "/sitemap-hubs.xml",
    *[f"/sitemap-branch-{i}.xml" for i in range(16)],
)

TOKEN_HUB_ALIASES = {
    "llm": "llms",
    "llms": "llms",
    "ollama": "local-llm",
    "local": "local-llm",
    "prompt": "prompt-engineering",
    "prompts": "prompt-engineering",
    "context": "context-compiler",
    "compression": "context-compiler",
    "fu": "context-compiler",
    "sympathy": "mechanical-sympathy",
    "arexx": "mechanical-sympathy",
    "crc32": "mechanical-sympathy",
    "workflow": "ai-workflows",
    "workflows": "ai-workflows",
    "automation": "ai-workflows",
    "aider": "ai-workflows",
    "ruff": "ai-workflows",
    "cli": "ai-workflows",
    "refactoring": "ai-workflows",
    "mcp": "mcp",
    "pipulate": "pipulate",
    "actuator": "pipulate",
    "airlock": "pipulate",
    "jupyter": "jupyter-notebooks",
    "notebook": "jupyter-notebooks",
    "notebooks": "jupyter-notebooks",
    "nbstripout": "jupyter-notebooks",
    "fasthtml": "fasthtml",
    "htmx": "fasthtml",
    "viewstate": "fasthtml",
    "git": "git",
    "flow": "flow-state",
    "shoshin": "flow-state",
    "ikigai": "forever-machine",
    "forever": "forever-machine",
    "levinix": "forever-machine",
    "levinux": "forever-machine",
    "npvg": "forever-machine",
    "sovereignty": "digital-sovereignty",
    "computational": "digital-sovereignty",
    "computing": "digital-sovereignty",
    "seo": "seo",
    "google": "seo",
    "search": "seo",
    "gsc": "seo",
    "schemaorg": "seo",
    "overviews": "seo",
    "redirects": "seo",
    "agentic": "agentic-web",
    "bots": "ai-bots",
    "bot": "ai-bots",
    "agents": "ai-bots",
    "botify": "ai-bots",
    "fingerprinting": "ai-bots",
    "d3": "d3js",
    "d3js": "d3js",
    "graph": "d3js",
    "jekyll": "jekyll",
    "nixos": "nixos",
    "nginx": "nixos",
    "devops": "nix-flakes",
    "flakes": "nix-flakes",
    "flake": "nix-flakes",
    "declarative": "nix-flakes",
    "nix": "nix",
    "unix": "unix-philosophy",
    "lisp": "unix-philosophy",
    "scraping": "browser-automation",
    "optics": "browser-automation",
    "browser": "browser-automation",
    "selenium": "browser-automation",
    "negotiation": "content-negotiation",
    "rfc9110": "content-negotiation",
    "rfc9111": "content-negotiation",
    "piper": "piper-tts",
    "tts": "piper-tts",
}


def _clean_sys_env() -> dict:
    """Clear devShell LD_LIBRARY_PATH so system ssh and git binaries never see library skew."""
    return {**os.environ, "LD_LIBRARY_PATH": ""}


def resolve_trimnoir_root() -> Path:
    """Resolve the active trimnoir Jekyll repository without interactive menu prompts."""
    candidates = [
        Path.home() / "repos" / "trimnoir",
        REPO_ROOT.parent / "trimnoir",
    ]
    for cand in candidates:
        if cand.is_dir() and ((cand / "_posts").is_dir() or (cand / "_raw_map.csv").is_file()):
            return cand
    try:
        posts_dir = common.get_target_path("1")
        if posts_dir:
            return Path(posts_dir).resolve().parent
    except Exception:
        pass
    return candidates[0]


def normalize_ghost_source(ghost_path: str) -> str:
    s = re.sub(r"/+", "/", str(ghost_path or "").strip())
    if s.lower().endswith("/index.md") and len(s) > len("/index.md"):
        return s[:-len("index.md")]
    if s.lower().endswith((".html", ".htm")) or s.endswith("/"):
        return s
    if s.startswith("/") and "." not in s.split("/")[-1]:
        return s + "/"
    return s


def is_ghost_noise(raw_url: str) -> bool:
    """Check both raw and slash-normalized forms so bare '/api' never loops against '/api/'."""
    norm_src = normalize_ghost_source(raw_url)
    return (
        generate_redirects.is_noise_or_unmappable_source(raw_url)
        or generate_redirects.is_noise_or_unmappable_source(norm_src)
    )


def _add_exclusion_variants(exclusions: set, raw_url: str) -> None:
    s = re.sub(r"/+", "/", str(raw_url or "").strip().lower())
    if not s:
        return
    exclusions.add(s)
    if s.endswith("/index.md") and len(s) > len("/index.md"):
        s = s[:-len("index.md")]
        exclusions.add(s)
    base = s.rstrip("/")
    if base:
        exclusions.add(base)
        exclusions.add(base + "/")
        exclusions.add(base + "/index.md")


def get_excluded_urls(trimnoir_root: Path = None) -> set:
    exclusions = set()
    tr = trimnoir_root or resolve_trimnoir_root()

    for sys_path in PROTECTED_SYSTEM_PATHS:
        _add_exclusion_variants(exclusions, sys_path)

    raw_csv_path = tr / "_raw_map.csv"
    if raw_csv_path.is_file():
        with open(raw_csv_path, "r", encoding="utf-8") as f:
            for row in csv.reader(f):
                if row and row[0].strip():
                    _add_exclusion_variants(exclusions, row[0])

    map_path = tr / "_redirects.map"
    if map_path.is_file():
        for line in map_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) == 2:
                _add_exclusion_variants(exclusions, parts[0])

    retired_path = tr / "_data" / "retired_hubs.json"
    if retired_path.is_file():
        try:
            retired_map = json.loads(retired_path.read_text(encoding="utf-8")) or {}
        except Exception:
            retired_map = {}
        for old_hub in retired_map:
            _add_exclusion_variants(exclusions, old_hub)

    nav_path = generate_redirects.resolve_navgraph_path(tr)
    living_tissue, _, _, _, _ = generate_redirects.get_navgraph_sets(
        nav_path, posts_dir=tr / "_posts", pages_dir=tr / "pages"
    )
    for url in living_tissue:
        _add_exclusion_variants(exclusions, url)

    pages_archive = tr / "pages" / "page"
    if pages_archive.is_dir():
        for p_md in pages_archive.glob("page-*.md"):
            m = re.match(r"^page-(\d+)\.md$", p_md.name)
            if m:
                _add_exclusion_variants(exclusions, f"/page/{m.group(1)}/")

    return exclusions


def _build_exclusions_sql_prefix(exclusions: set) -> str:
    inserts = ["CREATE TEMP TABLE IF NOT EXISTS exclusions (url TEXT);", "DELETE FROM exclusions;"]
    if exclusions:
        urls = sorted(exclusions)
        chunk_size = 400
        for i in range(0, len(urls), chunk_size):
            chunk = urls[i : i + chunk_size]
            values = ", ".join(f"('{u.replace(chr(39), chr(39) + chr(39))}')" for u in chunk)
            inserts.append(f"INSERT INTO exclusions (url) VALUES {values};")
    inserts.append("CREATE INDEX IF NOT EXISTS idx_temp_excl_url ON exclusions(url);")
    return "\n".join(inserts) + "\n\n"


def _run_remote_sql_rows(sql_body: str, exclusions: set) -> tuple:
    """Return ([(path, hits), ...], noise_dropped_count) from Honeybot SQLite."""
    full_sql = _build_exclusions_sql_prefix(exclusions) + sql_body
    cmd = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
        "honeybot", "sqlite3 -readonly -noheader -list ~/www/mikelev.in/honeybot.db",
    ]
    res = subprocess.run(cmd, input=full_sql, text=True, capture_output=True, timeout=25, env=_clean_sys_env())
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or f"ssh sqlite3 exited {res.returncode}")
    rows = []
    noise_dropped = 0
    for line in res.stdout.splitlines():
        raw = line.strip()
        if not raw or not raw.startswith("/"):
            continue
        cols = [c.strip() for c in raw.split("|")]
        p = cols[0]
        if not p.startswith("/"):
            continue
        hits = int(cols[1]) if len(cols) > 1 and cols[1].isdigit() else 1
        if is_ghost_noise(p):
            noise_dropped += 1
            continue
        norm_low = re.sub(r"/+", "/", p.lower())
        src_low = normalize_ghost_source(p).lower()
        if (
            norm_low in exclusions
            or norm_low.rstrip("/") in exclusions
            or src_low in exclusions
            or src_low.rstrip("/") in exclusions
        ):
            continue
        rows.append((p, hits))
    return rows, noise_dropped


def _run_remote_sql(sql_body: str, exclusions: set) -> list:
    rows, _ = _run_remote_sql_rows(sql_body, exclusions)
    return [p for p, _ in rows]


def _load_hub_router_data(trimnoir_root: Path):
    hm_path = trimnoir_root / "_data" / "hubs_manifest.json"
    hub_terms = {}
    hub_permalinks = {}
    if hm_path.is_file():
        hm = json.loads(hm_path.read_text(encoding="utf-8"))
        raw_hubs = hm.get("hubs", [])
        hlist = list(raw_hubs.values()) if isinstance(raw_hubs, dict) else list(raw_hubs)
        for h in hlist:
            if not isinstance(h, dict):
                continue
            slug = str(h.get("slug") or "").strip().lower()
            perm = str(h.get("permalink") or f"/{slug}/").strip()
            if not slug:
                continue
            hub_permalinks[slug] = perm if perm.endswith("/") else perm + "/"
            bag = set(re.findall(r"[a-z0-9]+", slug))
            for field in ("title", "prototype_keywords", "prototype_terms"):
                val = h.get(field) or []
                items = [val] if isinstance(val, str) else list(val)
                for item in items:
                    bag.update(re.findall(r"[a-z0-9]+", str(item).lower()))
            hub_terms[slug] = bag
    nav_path = generate_redirects.resolve_navgraph_path(trimnoir_root)
    _, _, _, slug_map, _ = generate_redirects.get_navgraph_sets(
        nav_path, posts_dir=trimnoir_root / "_posts", pages_dir=trimnoir_root / "pages"
    )
    lower_slug_map = {k.lower(): v for k, v in slug_map.items()}
    return hub_permalinks, hub_terms, lower_slug_map


def route_ghost_to_hub(ghost_path: str, hub_permalinks: dict, hub_terms: dict, lower_slug_map: dict) -> str:
    clean = ghost_path.strip()
    if clean.lower().endswith("/index.md"):
        clean = clean[:-len("index.md")]
    clean_stripped = re.sub(r"\.(?:html|htm)$", "", clean.strip("/"), flags=re.IGNORECASE)
    segs = [s.lower() for s in clean_stripped.split("/") if s and not re.match(r"^\d{4}$|^\d{2}$", s)]
    if segs:
        leaf = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", segs[-1])
        if leaf in lower_slug_map:
            return lower_slug_map[leaf]
        if leaf in hub_permalinks:
            return hub_permalinks[leaf]

    scores = {slug: 0.0 for slug in hub_permalinks}
    for depth_idx, seg in enumerate(segs):
        weight = 1.0 + (0.35 * depth_idx)
        if seg in hub_permalinks:
            scores[seg] += 4.0 * weight
        if seg in TOKEN_HUB_ALIASES and TOKEN_HUB_ALIASES[seg] in scores:
            scores[TOKEN_HUB_ALIASES[seg]] += 3.5 * weight
        for tok in re.findall(r"[a-z0-9]+", seg):
            if tok in hub_permalinks:
                scores[tok] += 2.5 * weight
            alias_hub = TOKEN_HUB_ALIASES.get(tok)
            if alias_hub in scores:
                scores[alias_hub] += 2.2 * weight
            for h_slug, bag in hub_terms.items():
                if len(tok) >= 3 and tok in bag:
                    scores[h_slug] += 0.8 * weight

    best_slug = max(scores, key=lambda k: (scores[k], k == "future-proofing")) if scores else "future-proofing"
    if scores.get(best_slug, 0.0) <= 0.0:
        return hub_permalinks.get("future-proofing", "/future-proofing/")
    return hub_permalinks[best_slug]


def sync_hubs_and_pagination(trimnoir_root: Path = None) -> None:
    """Refresh homepage cards, /page/2..N/ pagination, and 28 hub files before 404 healing."""
    tr = trimnoir_root or resolve_trimnoir_root()
    posts_dir = tr / "_posts"
    if not posts_dir.is_dir():
        return
    generate_hubs.update_homepage_recent_posts(posts_dir, tr, count=10)
    nav_path = generate_redirects.resolve_navgraph_path(tr)
    if nav_path and nav_path.is_file():
        nav_tree = json.loads(nav_path.read_text(encoding="utf-8"))
        hubs_dir = tr / "pages"
        generate_hubs.clean_and_prep_dirs(hubs_dir)

        def _walk(node, parents=None):
            anc = [] if parents is None else parents
            generate_hubs.generate_hub_file(node, tr, hubs_dir, anc)
            nxt = anc + [{"title": node["title"], "permalink": node["permalink"]}]
            for child in node.get("children_hubs", []):
                _walk(child, nxt)

        _walk(nav_tree)


def _count_map_rules(map_path: Path) -> int:
    if not map_path.is_file():
        return 0
    return sum(
        1 for ln in map_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    )


def _snapshot_ghost_queues(trimnoir_root: Path) -> dict:
    exclusions = get_excluded_urls(trimnoir_root)
    sql_dir = REPO_ROOT / "remotes" / "honeybot" / "queries"
    hot_sql = (sql_dir / "hot_404_remaps_top.sql").read_text(encoding="utf-8")
    true_sql = (sql_dir / "intel_true_404s.sql").read_text(encoding="utf-8")
    hot_rows, hot_noise = _run_remote_sql_rows(hot_sql, exclusions)
    true_rows, true_noise = _run_remote_sql_rows(true_sql, exclusions)
    return {
        "hot_n": len(hot_rows),
        "hot_hits": sum(h for _, h in hot_rows),
        "true_n": len(true_rows),
        "true_hits": sum(h for _, h in true_rows),
        "noise_ignored": max(hot_noise, true_noise),
    }


def apply_ghost_remaps_detailed(max_rounds: int = 30) -> tuple:
    """Return ([(src, tgt, hits), ...], noise_ignored_max) after rebuilding _redirects.map."""
    tr = resolve_trimnoir_root()
    sql_dir = REPO_ROOT / "remotes" / "honeybot" / "queries"
    sweep_sql = (sql_dir / "hot_404_remaps_top.sql").read_text(encoding="utf-8").replace(
        "HAVING total_hits > 1", "HAVING total_hits >= 1"
    ).replace("LIMIT 250;", "LIMIT 500;")
    true_sweep_sql = (sql_dir / "intel_true_404s.sql").read_text(encoding="utf-8").replace(
        "LIMIT 20;", "LIMIT 500;"
    )
    hub_permalinks, hub_terms, lower_slug_map = _load_hub_router_data(tr)
    csv_path = tr / "_raw_map.csv"
    map_path = tr / "_redirects.map"
    nav_path = generate_redirects.resolve_navgraph_path(tr)

    generate_redirects.build_nginx_map(csv_path, map_path, nav_path)
    sanitize_redirects.sanitize_map_file(map_path)

    exclusions = get_excluded_urls(tr)
    attempted = set()
    remapped = []
    noise_peak = 0

    for query_sql in (sweep_sql, true_sweep_sql):
        for _ in range(max_rounds):
            rows, noise_cnt = _run_remote_sql_rows(query_sql, exclusions)
            noise_peak = max(noise_peak, noise_cnt)
            fresh = [(g, hits) for g, hits in rows if g.lower() not in attempted]
            if not fresh:
                break
            for g, hits in fresh:
                attempted.add(g.lower())
                src = normalize_ghost_source(g)
                tgt = route_ghost_to_hub(g, hub_permalinks, hub_terms, lower_slug_map)
                remapped.append((src, tgt, hits))
                _add_exclusion_variants(exclusions, g)
                _add_exclusion_variants(exclusions, src)

    if remapped:
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows([[src, tgt] for src, tgt, _ in remapped])
        generate_redirects.build_nginx_map(csv_path, map_path, nav_path)
        sanitize_redirects.sanitize_map_file(map_path)

    return remapped, noise_peak


def apply_ghost_remaps(max_rounds: int = 30) -> int:
    remapped, _ = apply_ghost_remaps_detailed(max_rounds=max_rounds)
    return len(remapped)


def verify_zero_ghosts() -> tuple:
    """Return (hot_404_count, intel_true_404_count) after applying repository exclusions."""
    tr = resolve_trimnoir_root()
    snap = _snapshot_ghost_queues(tr)
    return (snap["hot_n"], snap["true_n"])


def print_tree_shake_report(
    before_snap: dict,
    after_snap: dict,
    before_rules: int,
    after_rules: int,
    remapped: list,
    living_count: int,
    sha8: str,
    reloaded_ram: bool,
) -> None:
    """Render a concise before/after Tree-Shaker Scoreboard to stdout."""
    net_rules = after_rules - before_rules
    sign = "+" if net_rules >= 0 else ""
    ram_note = "reloaded into Honeybot RAM" if reloaded_ram else "already current in Honeybot RAM"
    noise_n = max(before_snap.get("noise_ignored", 0), after_snap.get("noise_ignored", 0))
    print("\n🌳 404 TREE-SHAKER SCOREBOARD (mikelev.in -> Honeybot O(1) RAM Map)")
    print("─" * 72)
    print(f"  • Protected Living URLs : {living_count:,} (28 hubs + posts + /page/2..N/ archive)")
    print(
        f"  • Hot Ghosts (multi-hit): {before_snap['hot_n']} -> {after_snap['hot_n']} "
        f"({before_snap['hot_hits']:,} hits -> {after_snap['hot_hits']:,} hits)"
    )
    print(
        f"  • True Ghosts (recent)  : {before_snap['true_n']} -> {after_snap['true_n']} "
        f"({before_snap['true_hits']:,} hits -> {after_snap['true_hits']:,} hits)"
    )
    print(f"  • Pirate/Scanner Noise  : {noise_n} probe path(s) ignored (left as 404 on purpose)")
    print(
        f"  • O(1) 301 Rules in RAM : {before_rules:,} -> {after_rules:,} "
        f"({sign}{net_rules} net | sha256:{sha8} | {ram_note})"
    )
    print("─" * 72)
    if remapped:
        hub_counts = Counter(tgt for _, tgt, _ in remapped)
        top_hubs = " | ".join(f"{h}: +{c}" for h, c in hub_counts.most_common(6))
        print(f"  🎯 Hub Catch Breakdown (+{len(remapped)} shaken): {top_hubs}")
        print("  🍎 Newly Healed 301 Paths (top 12 by hit count):")
        for src, tgt, hits in sorted(remapped, key=lambda x: (-x[2], x[0]))[:12]:
            h_lbl = f"{hits} hit " if hits == 1 else f"{hits} hits"
            print(f"     [{h_lbl:>7}] {src}  ──301──▶  {tgt}")
    else:
        print(f"  ✨ Tree is clean: 0 new non-pirate 404s since last shake ({after_rules:,} rules active NOW).")


def heal_and_reload_honeybot(push_git: bool = False, run_hubs: bool = True, force_reload: bool = False) -> tuple:
    """Sync hubs/pagination, drain non-pirate 404 ghosts, commit map in trimnoir, and reload Honeybot Nginx RAM."""
    tr = resolve_trimnoir_root()
    if run_hubs:
        sync_hubs_and_pagination(tr)
    map_path = tr / "_redirects.map"
    nav_path = generate_redirects.resolve_navgraph_path(tr)
    _, active_perms, _, _, _ = generate_redirects.get_navgraph_sets(
        nav_path, posts_dir=tr / "_posts", pages_dir=tr / "pages"
    )
    before_rules = _count_map_rules(map_path)
    before_snap = _snapshot_ghost_queues(tr)
    remapped, noise_peak = apply_ghost_remaps_detailed()
    before_snap["noise_ignored"] = max(before_snap["noise_ignored"], noise_peak)
    added = len(remapped)

    map_bytes = map_path.read_bytes()
    sha256_full = hashlib.sha256(map_bytes).hexdigest()
    sha8 = sha256_full[:8]
    after_rules = _count_map_rules(map_path)
    if after_rules <= 10:
        raise RuntimeError(f"Refusing to deploy _redirects.map with <= 10 rules ({after_rules} found).")

    env = _clean_sys_env()
    if (tr / ".git").exists():
        st = subprocess.run(
            ["git", "-C", str(tr), "status", "--porcelain", "--", "_raw_map.csv", "_redirects.map"],
            capture_output=True, text=True, env=env,
        )
        if (st.stdout or "").strip():
            subprocess.run(
                ["git", "-C", str(tr), "add", "--", "_raw_map.csv", "_redirects.map"],
                check=True, env=env,
            )
            msg = f"chore(404): heal {added} ghost path(s) into O(1) _redirects.map ({after_rules} rules)"
            subprocess.run(
                ["git", "-C", str(tr), "commit", "-m", msg, "--", "_raw_map.csv", "_redirects.map"],
                check=True, env=env,
            )
            print(f"📝 Committed in {tr.name}: {msg}")
        if push_git:
            subprocess.run(["git", "-C", str(tr), "push"], check=True, env=env)

    remote_sha_res = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "honeybot", "sha256sum ~/www/mikelev.in/_site/redirects.map 2>/dev/null | cut -d' ' -f1"],
        capture_output=True, text=True, timeout=12, env=env,
    )
    remote_sha = (remote_sha_res.stdout or "").strip()
    reloaded_ram = False
    if force_reload or remote_sha != sha256_full:
        remote_stage_cmd = (
            "cat > ~/www/mikelev.in/_redirects.map.tmp && "
            "chmod 644 ~/www/mikelev.in/_redirects.map.tmp && "
            "cp ~/www/mikelev.in/_redirects.map.tmp ~/www/mikelev.in/_site/redirects.map.tmp && "
            "mv ~/www/mikelev.in/_redirects.map.tmp ~/www/mikelev.in/_redirects.map && "
            "mv ~/www/mikelev.in/_site/redirects.map.tmp ~/www/mikelev.in/_site/redirects.map"
        )
        subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "honeybot", remote_stage_cmd],
            input=map_bytes, check=True, timeout=20, env=env,
        )
        reload_res = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "honeybot", "sudo -n /run/current-system/sw/bin/systemctl reload nginx"],
            capture_output=True, text=True, timeout=15, env=env,
        )
        if reload_res.returncode == 0:
            reloaded_ram = True
        elif sys.stdin.isatty():
            print("🔐 Honeybot requested sudo password to reload Nginx redirect map:")
            subprocess.run(
                ["ssh", "-t", "honeybot", "sudo /run/current-system/sw/bin/systemctl reload nginx"],
                check=True, env=env,
            )
            reloaded_ram = True
        else:
            raise RuntimeError(f"Non-interactive Nginx reload failed: {reload_res.stderr.strip()}")

    after_snap = _snapshot_ghost_queues(tr)
    print_tree_shake_report(
        before_snap=before_snap,
        after_snap=after_snap,
        before_rules=before_rules,
        after_rules=after_rules,
        remapped=remapped,
        living_count=len(active_perms),
        sha8=sha8,
        reloaded_ram=reloaded_ram,
    )
    print(
        f"✅ 404 Healer Complete: +{added} new rule(s) | Live rules={after_rules:,} | "
        f"ZERO_404_VERIFY: hot={after_snap['hot_n']} true={after_snap['true_n']}"
    )
    return added, after_rules, after_snap["hot_n"], after_snap["true_n"]


def main():
    parser = argparse.ArgumentParser(description="Extract, remap, or hot-heal non-pirate 404 ghosts on Honeybot")
    parser.add_argument("--heal", action="store_true", help="End-to-end 1-word `404` flow: sync hubs/pages, remap 404s, commit map, and reload Honeybot Nginx RAM")
    parser.add_argument("--no-hubs", action="store_true", help="With --heal, skip generate_hubs homepage/pagination refresh")
    parser.add_argument("--hubs", action="store_true", help="Only refresh homepage cards, /page/2..N/ pagination, and 28 hub files")
    parser.add_argument("--force-reload", action="store_true", help="Force Nginx systemctl reload even if redirects.map SHA-256 already matches")
    parser.add_argument("--push", action="store_true", help="With --heal, also run `git push` in trimnoir (triggers full Jekyll post-receive build)")
    parser.add_argument("--apply", action="store_true", help="Deterministically remap all remaining 404 ghosts into trimnoir/_raw_map.csv & _redirects.map")
    parser.add_argument("--verify", action="store_true", help="Print remaining unmapped counts across hot_404_remaps_top.sql and intel_true_404s.sql")
    args = parser.parse_args()

    if args.hubs:
        sync_hubs_and_pagination()
        return

    if args.heal:
        heal_and_reload_honeybot(push_git=args.push, run_hubs=not args.no_hubs, force_reload=args.force_reload)
        return

    if args.apply:
        added = apply_ghost_remaps()
        hot_n, true_n = verify_zero_ghosts()
        print(f"✅ Mapped {added} ghost path(s) into trimnoir/_redirects.map | Remaining: hot={hot_n}, true={true_n}")
        return

    if args.verify:
        hot_n, true_n = verify_zero_ghosts()
        print(f"ZERO_404_VERIFY: hot={hot_n} true={true_n}")
        return

    tr = resolve_trimnoir_root()
    exclusions = get_excluded_urls(tr)
    hot_sql = (REPO_ROOT / "remotes" / "honeybot" / "queries" / "hot_404_remaps_top.sql").read_text(encoding="utf-8")
    ghosts = _run_remote_sql(hot_sql, exclusions)
    print(f"🚀 Extracted {len(ghosts)} unmapped 404 ghost(s) (exclusions={len(exclusions)}):\n")
    for g in ghosts:
        print(g)


if __name__ == "__main__":
    main()
