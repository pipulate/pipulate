#!/usr/bin/env python3
"""
extract_404_ghosts.py
Resolves trimnoir via ~/repos/trimnoir, loads all active + retired + CSV redirect
exclusions, extracts unmapped non-pirate 404 ghosts from Honeybot SQLite using the
shared literal-key contract, routes them onto the 28 permanent hubs, and reloads
Honeybot Nginx RAM via `404` (--heal / --apply / --verify).
"""
import argparse
import csv
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
import generate_redirects  # noqa: E402
import sanitize_redirects  # noqa: E402

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


def _run_remote_sql(sql_body: str, exclusions: set) -> list:
    full_sql = _build_exclusions_sql_prefix(exclusions) + sql_body
    cmd = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
        "honeybot", "sqlite3 -readonly -noheader -list ~/www/mikelev.in/honeybot.db",
    ]
    res = subprocess.run(cmd, input=full_sql, text=True, capture_output=True, timeout=25, env=_clean_sys_env())
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or f"ssh sqlite3 exited {res.returncode}")
    paths = []
    for line in res.stdout.splitlines():
        raw = line.strip()
        if not raw or not raw.startswith("/"):
            continue
        p = raw.split("|", 1)[0].strip()
        if not p.startswith("/"):
            continue
        if generate_redirects.is_noise_or_unmappable_source(p):
            continue
        norm_low = re.sub(r"/+", "/", p.lower())
        if norm_low in exclusions or norm_low.rstrip("/") in exclusions:
            continue
        paths.append(p)
    return paths


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


def normalize_ghost_source(ghost_path: str) -> str:
    s = re.sub(r"/+", "/", ghost_path.strip())
    if s.lower().endswith("/index.md") and len(s) > len("/index.md"):
        return s[:-len("index.md")]
    if s.lower().endswith((".html", ".htm")) or s.endswith("/"):
        return s
    if s.startswith("/") and "." not in s.split("/")[-1]:
        return s + "/"
    return s


def apply_ghost_remaps(max_rounds: int = 30) -> int:
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
    all_new_rows = []

    for query_sql in (sweep_sql, true_sweep_sql):
        for _ in range(max_rounds):
            ghosts = [g for g in _run_remote_sql(query_sql, exclusions) if g.lower() not in attempted]
            if not ghosts:
                break
            for g in ghosts:
                attempted.add(g.lower())
                src = normalize_ghost_source(g)
                tgt = route_ghost_to_hub(g, hub_permalinks, hub_terms, lower_slug_map)
                all_new_rows.append([src, tgt])
                _add_exclusion_variants(exclusions, g)
                _add_exclusion_variants(exclusions, src)

    if all_new_rows:
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(all_new_rows)
        generate_redirects.build_nginx_map(csv_path, map_path, nav_path)
        sanitize_redirects.sanitize_map_file(map_path)

    return len(all_new_rows)


def verify_zero_ghosts() -> tuple:
    """Return (hot_404_count, intel_true_404_count) after applying repository exclusions."""
    tr = resolve_trimnoir_root()
    exclusions = get_excluded_urls(tr)
    hot_sql = (REPO_ROOT / "remotes" / "honeybot" / "queries" / "hot_404_remaps_top.sql").read_text(encoding="utf-8")
    true_sql = (REPO_ROOT / "remotes" / "honeybot" / "queries" / "intel_true_404s.sql").read_text(encoding="utf-8")
    hot_paths = _run_remote_sql(hot_sql, exclusions)
    true_paths = _run_remote_sql(true_sql, exclusions)
    return (len(hot_paths), len(true_paths))


def heal_and_reload_honeybot(push_git: bool = False) -> tuple:
    """Drain all non-pirate 404 ghosts, commit map in trimnoir, and hot-reload Honeybot Nginx RAM."""
    tr = resolve_trimnoir_root()
    map_path = tr / "_redirects.map"
    added = apply_ghost_remaps()
    map_bytes = map_path.read_bytes()
    rule_lines = [
        ln for ln in map_bytes.decode("utf-8", errors="ignore").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    if len(rule_lines) <= 10:
        raise RuntimeError(f"Refusing to deploy _redirects.map with <= 10 rules ({len(rule_lines)} found).")

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
            msg = f"chore(404): heal {added} ghost path(s) into O(1) _redirects.map ({len(rule_lines)} rules)"
            subprocess.run(
                ["git", "-C", str(tr), "commit", "-m", msg, "--", "_raw_map.csv", "_redirects.map"],
                check=True, env=env,
            )
            print(f"📝 Committed in {tr.name}: {msg}")
        if push_git:
            subprocess.run(["git", "-C", str(tr), "push"], check=True, env=env)

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
        print(f"🔄 Reloaded Honeybot Nginx redirect map into RAM ({len(rule_lines):,} rules, zero password needed).")
    elif sys.stdin.isatty():
        print("🔐 Honeybot requested sudo password to reload Nginx redirect map:")
        subprocess.run(
            ["ssh", "-t", "honeybot", "sudo /run/current-system/sw/bin/systemctl reload nginx"],
            check=True, env=env,
        )
    else:
        raise RuntimeError(f"Non-interactive Nginx reload failed: {reload_res.stderr.strip()}")

    hot_n, true_n = verify_zero_ghosts()
    print(f"✅ 404 Healer Complete: +{added} new rule(s) | Live rules={len(rule_lines):,} | ZERO_404_VERIFY: hot={hot_n} true={true_n}")
    return added, len(rule_lines), hot_n, true_n


def main():
    parser = argparse.ArgumentParser(description="Extract, remap, or hot-heal non-pirate 404 ghosts on Honeybot")
    parser.add_argument("--heal", action="store_true", help="End-to-end 1-word `404` flow: remap, sanitize, commit in trimnoir, and reload Honeybot Nginx RAM")
    parser.add_argument("--push", action="store_true", help="With --heal, also run `git push` in trimnoir (triggers full Jekyll post-receive build)")
    parser.add_argument("--apply", action="store_true", help="Deterministically remap all remaining 404 ghosts into trimnoir/_raw_map.csv & _redirects.map")
    parser.add_argument("--verify", action="store_true", help="Print remaining unmapped counts across hot_404_remaps_top.sql and intel_true_404s.sql")
    args = parser.parse_args()

    if args.heal:
        heal_and_reload_honeybot(push_git=args.push)
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
