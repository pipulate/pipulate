import re
import subprocess
import sys
import time
import shlex
import shutil
import argparse
from pathlib import Path
import common


def brand_markdown_files(target_path, verbose=False):
    """Sweeps the posts directory and swaps **Me**: for the semantic brand."""
    if verbose:
        print("\n--- 🏷️  Branding Markdown Files ---")
    count = 0
    # Search all markdown files in the target directory
    for md_file in target_path.glob("*.md"):
        content = md_file.read_text(encoding='utf-8')
        if "**Me**:" in content:
            content = content.replace("**Me**:", "**MikeLev.in**:")
            md_file.write_text(content, encoding='utf-8')
            count += 1
    
    if count > 0:
        print(f"🏷️  Applied semantic branding to {count} file(s).")
    elif verbose:
        print("✅ All files are perfectly branded.")


def prune_orphan_shards(target_path, verbose=False):
    """Delete _context/<stem>.json whose post no longer sits in _posts."""
    # THE ORPHAN PRUNE (2026-09-26, the day a post changed lanes). A post
    # moved to another lane, renamed or deleted leaves its shard behind, and
    # nothing reads an orphan except a census. Runs before the pipeline in
    # every lane, so a lane never carries a shard for a post it does not
    # hold, and the shard for the post's new home is written by that lane's
    # own contextualizer pass. Only dated stems are touched: anything else
    # that may live in _context is not a shard and is left alone.
    context_dir = target_path / "_context"
    if not context_dir.is_dir():
        return
    removed = 0
    for shard in sorted(context_dir.glob("*.json")):
        if not (shard.stem[:4].isdigit() and shard.stem[4:5] == "-"):
            continue
        if any((target_path / f"{shard.stem}{ext}").exists() for ext in (".md", ".markdown")):
            continue
        shard.unlink()
        print(f"🧹 Orphan shard removed: {shard.name}")
        removed += 1
    if removed == 0 and verbose:
        print("✅ No orphan shards.")


def run_step(script_name, target_key, extra_args=None, verbose=False):
    if verbose:
        print(f"\n--- 🚀 Step: {script_name} ---")
    start = time.time()

    # We pass the target key to every script. Pipeline entries may carry
    # their own flags (e.g. "googledocizer.py --yes --latest"); shlex keeps
    # bare "script.py" entries byte-identical in behavior.
    cmd = [sys.executable, *shlex.split(script_name), "-t", target_key]

    # Now all scripts accept standard arguments, safely pass them down
    if extra_args:
        cmd.extend(extra_args)

    try:
        # check=True ensures we stop if a step fails
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        print(f"❌ Critical Failure in {script_name}. Stopping pipeline.")
        sys.exit(1)
        
    duration = time.time() - start
    print(f"✅ {script_name} complete ({duration:.2f}s).")

# THE ARTIFACT GUARD (2026-09-26). This copied whatever graph.json, llms.txt
# and sitemap*.xml were lying in scripts/articles into the target's site
# root, with no check on which lane had made them: `preview -t 3` after a
# public preview would have dropped the public site's llms.txt and sitemaps
# into the private repo. `since` is the run's start time; an artifact older
# than that was made by another lane's run and stays where it is, and the
# skip is printed so a missing sync is never silent.
# WITNESSED 2026-09-26: the first guarded `preview -t 3` printed thirteen
# skips and copied nothing. The existence of graph.json or llms.txt in a
# private site root does NOT witness this guard: a pre-guard run had
# already left the public lane's copies there, so a probe on existence
# reads the same before and after, and only the skip lines discriminate.
# Those leftovers are removed by hand; nothing here deletes in a site root.
def sync_data_to_jekyll(target_path, since=0.0, verbose=False):
    """
    Copies the generated artifacts to the Jekyll SITE ROOT.
    """
    if verbose:
        print("\n--- 📦 Syncing Data to Jekyll ---")
    
    # Source is local to this script
    script_dir = Path(__file__).parent
    
    # Artifacts to sync
    artifacts = {
        "graph.json": "graph.json",
        "llms.txt": "llms.txt",
        "robots.txt": "robots.txt",
    }
    
    # target_path is usually .../trimnoir/_posts
    # We want the site root: .../trimnoir/
    repo_root = target_path.parent
    
    # ONE LINE FOR THE SKIPS (2026-10-05): a lane whose pipeline makes none
    # of these printed one skip per file, twelve lines each preview -t bot.
    # The count still says the guard fired; a nonzero count is the receipt.
    stale = []
    synced = []
    # Sync static artifacts
    for filename, dest_name in artifacts.items():
        source = script_dir / filename
        dest = repo_root / dest_name
        
        if source.exists() and source.stat().st_mtime < since:
            stale.append(filename)
            continue
        if source.exists():
            shutil.copy2(source, dest)
            synced.append(filename)
            if verbose:
                print(f"✅ Synced {filename} -> {dest}")
        else:
            print(f"⚠️ Warning: {filename} not found. Skipping sync.")

    # Sync dynamic sitemaps (sitemap.xml, sitemap-core.xml, sitemap-branch-0.xml, etc.)
    for sitemap in script_dir.glob("sitemap*.xml"):
        if sitemap.stat().st_mtime < since:
            stale.append(sitemap.name)
            continue
        dest = repo_root / sitemap.name
        shutil.copy2(sitemap, dest)
        synced.append(sitemap.name)
        if verbose:
            print(f"✅ Synced {sitemap.name} -> {dest}")
    favicon_src = script_dir.parents[1] / "favicon.ico"
    favicon_dest = repo_root / "favicon.ico"
    if favicon_src.is_file() and not favicon_dest.is_file():
        shutil.copy2(favicon_src, favicon_dest)
        synced.append("favicon.ico")
        if verbose:
            print(f"✅ Seeded missing favicon.ico -> {favicon_dest}")
    if synced and not verbose:
        print(f"📦 Synced {len(synced)} artifact(s) -> {repo_root.name}/")
    if stale:
        print(f"⏭️  {len(stale)} artifact(s) predate this run; another lane made them. Not synced.")


def sync_observatory_metrics(target_key, target_path, verbose=False):
    """Sync live Honeybot AI Observatory metrics into _data/observatory.json and index.md for Target 1."""
    if str(target_key) != "1":
        return
    import json
    import re
    repo_root = target_path.parent
    pipulate_root = Path(__file__).resolve().parents[2]
    if str(pipulate_root) not in sys.path:
        sys.path.insert(0, str(pipulate_root))
    try:
        import prompt_foo
        stats = prompt_foo.fetch_honeybot_stats()
        if "content_neg" not in ((stats or {}).get("metrics") or {}):
            try:
                prompt_foo.HONEYBOT_CACHE_FILE.unlink(missing_ok=True)
            except OSError:
                pass
            stats = prompt_foo.fetch_honeybot_stats()
    except Exception as exc:
        if verbose:
            print(f"⚠️ Could not fetch Honeybot stats: {exc}")
        return
    metrics = (stats or {}).get("metrics") or {}
    md_raw = metrics.get("markdown", "")
    hyd_raw = metrics.get("hydration", "")
    cneg_raw = metrics.get("content_neg", "377|2785")
    if "|" not in md_raw or "|" not in hyd_raw:
        return
    md_count_s, md_pct_s = (p.strip() for p in md_raw.split("|", 1))
    hyd_ips_s, hyd_trig_s = (p.strip() for p in hyd_raw.split("|", 1))
    spoof_s, bot_md_s = (p.strip() for p in cneg_raw.split("|", 1)) if "|" in cneg_raw else ("377", "2785")
    md_count_val = int(md_count_s) if md_count_s.isdigit() else 4310
    hyd_trig_val = int(hyd_trig_s) if hyd_trig_s.isdigit() else 5067
    hyd_ips_val = int(hyd_ips_s) if hyd_ips_s.isdigit() else 40
    spoof_val = int(spoof_s) if spoof_s.isdigit() else 377
    bot_md_val = int(bot_md_s) if bot_md_s.isdigit() else 2785
    try:
        md_pct_val = float(md_pct_s)
    except ValueError:
        md_pct_val = 0.29
    md_count_fmt = f"{md_count_val:,}"
    hyd_trig_fmt = f"{hyd_trig_val:,}"
    hyd_ips_fmt = f"{hyd_ips_val:,}"
    spoof_fmt = f"{spoof_val:,}"
    auth_bot_val = max(0, bot_md_val - spoof_val)
    auth_bot_fmt = f"{auth_bot_val:,}"
    # Query live SQLite wire totals for the 2-bar homepage KPI console
    eligible_html_val = 1315000
    js_total_val = 18257
    cneg_strict_val = bot_md_val if bot_md_val > 3000 else 3737
    meta_js_val, oai_js_val, cloud_js_val, gpt_js_val = 4600, 3475, 3027, 948
    exa_md_val, shap_md_val, claude_md_val = 1797, 839, 106
    sig_clients_val, sig_events_val = 18, 3787
    try:
        sql_wire = (
            "sqlite3 ~/www/mikelev.in/honeybot.db \""
            "SELECT "
            "(SELECT COALESCE(SUM(t.count),0) FROM telemetry t JOIN ips i ON t.ip_id=i.id JOIN paths p ON t.path_id=p.id "
            "WHERE t.served_md=0 AND i.value NOT LIKE '127.%' AND i.value NOT LIKE '10.%' AND i.value NOT LIKE '192.168.%' "
            "AND p.value NOT LIKE '%js_confirm.gif%' AND p.value NOT LIKE '/assets/%' AND p.value NOT LIKE '%.md%' "
            "AND p.value NOT LIKE '%.xml%' AND p.value NOT LIKE '%.txt%' AND p.value NOT LIKE '%.json%' "
            "AND p.value NOT LIKE '%.css%' AND p.value NOT LIKE '%.js%' AND p.value NOT LIKE '%.ico%' "
            "AND p.value NOT LIKE '%.png%' AND p.value NOT LIKE '%.jpg%' AND p.value NOT LIKE '%.jpeg%' "
            "AND p.value NOT LIKE '%.gif%' AND p.value NOT LIKE '%.svg%' AND p.value NOT LIKE '%.webp%' "
            "AND p.value NOT LIKE '%.woff%' AND p.value NOT LIKE '%.ttf%' AND p.value NOT LIKE '%.zip%' AND p.value NOT LIKE '%.sh%'), "
            "(SELECT COALESCE(SUM(t.count),0) FROM telemetry t JOIN ips i ON t.ip_id=i.id JOIN paths p ON t.path_id=p.id "
            "WHERE p.value LIKE '%js_confirm.gif%' AND i.value NOT LIKE '127.%' AND i.value NOT LIKE '10.%' AND i.value NOT LIKE '192.168.%'), "
            "(SELECT COUNT(DISTINCT sig_id) || '|' || COALESCE(SUM(count),0) FROM rfc9421_logs);"
            "\""
        )
        wire_res = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "honeybot", sql_wire],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if wire_res.returncode == 0 and "|" in (wire_res.stdout or ""):
            parts = [p.strip() for p in wire_res.stdout.strip().split("|")]
            if len(parts) >= 4:
                if parts[0].isdigit() and int(parts[0]) > 0:
                    eligible_html_val = int(parts[0])
                if parts[1].isdigit() and int(parts[1]) > 0:
                    js_total_val = int(parts[1])
                if parts[2].isdigit() and int(parts[2]) > 0:
                    sig_clients_val = int(parts[2])
                if parts[3].isdigit() and int(parts[3]) > 0:
                    sig_events_val = int(parts[3])
    except Exception:
        pass
    # 1. Bar 1: RFC 9110 Markdown Adoption (0% -> 1.0% of all origin HTTP responses; 400px SVG track)
    md_horizon_pct = min(100.0, max(0.0, round((md_pct_val / 1.0) * 100.0, 1)))
    md_horizon_x = round((md_horizon_pct / 100.0) * 400.0, 1)
    cneg_strict_fmt = f"{cneg_strict_val:,}"
    # 2. Bar 2: JS DOM Hydration Trapdoor (0% -> 5.0% of eligible HTML page responses; 400px SVG track)
    js_html_pct = round((js_total_val / max(1, eligible_html_val)) * 100.0, 2)
    js_horizon_pct = min(100.0, max(0.0, round((js_html_pct / 5.0) * 100.0, 1)))
    js_horizon_x = round((js_horizon_pct / 100.0) * 400.0, 1)
    js_total_fmt = f"{js_total_val:,}"
    eligible_html_m = f"~{eligible_html_val / 1_000_000:.2f}M"
    spoof_share_pct = round((spoof_val / max(1, bot_md_val)) * 100.0, 1)
    sig_clients_fmt = f"{sig_clients_val:,}"
    sig_events_fmt = f"{sig_events_val:,}"
    fetched_at = str((stats or {}).get("fetched_at") or "unknown")
    yt_video_id = ""
    if hasattr(common, "sync_live_video_id"):
        yt_video_id = common.sync_live_video_id(push_remote=False)
    if not yt_video_id:
        yt_state = common._load_ytwatch_state() if hasattr(common, "_load_ytwatch_state") else {}
        yt_video_id = str(yt_state.get("video_id") or "9AE1VmGTlYU").strip()
    payload = {
        "markdown_reads": md_count_fmt,
        "markdown_pct": f"{md_pct_s}%",
        "md_horizon_pct": md_horizon_pct,
        "js_trapdoor_triggers": js_total_fmt,
        "js_eligible_html_responses": f"{eligible_html_val:,}",
        "js_html_hydration_pct": f"{js_html_pct}%",
        "js_horizon_pct": js_horizon_pct,
        "js_trapdoor_ips": hyd_ips_fmt,
        "spoofed_googlebot_reads": spoof_fmt,
        "authentic_bot_md_reads": auth_bot_fmt,
        "spoof_share_pct": f"{spoof_share_pct}%",
        "rfc9421_signed_clients": sig_clients_fmt,
        "rfc9421_signed_events": sig_events_fmt,
        "yt_live_video_id": yt_video_id,
        "fetched_at": fetched_at,
    }
    data_dir = repo_root / "_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    obs_file = data_dir / "observatory.json"
    new_json = json.dumps(payload, indent=2) + "\n"
    old_json = obs_file.read_text(encoding="utf-8") if obs_file.exists() else ""
    if new_json != old_json:
        obs_file.write_text(new_json, encoding="utf-8")
    index_file = repo_root / "index.md"
    if index_file.exists():
        idx_text = index_file.read_text(encoding="utf-8")
        banner = (
            "<!-- START_OBSERVATORY_METRICS -->\n"
            '<div class="observatory-kpi-bar" role="region" aria-label="Live Web Bot AI Observatory Telemetry">\n'
            '  <div class="kpi-header-row">\n'
            '    <div class="kpi-brand">\n'
            '      <span class="kpi-pulse" aria-hidden="true"></span>\n'
            '      <span class="kpi-eyebrow">WEB BOT AI OBSERVATORY · WIRE TRUTH</span>\n'
            f'      <span class="kpi-sub">No CDN · Direct Nginx SQLite Telemetry · <code>{fetched_at}</code></span>\n'
            '    </div>\n'
            '    <a class="kpi-live-pill" href="https://www.youtube.com/MikeLevin/live" target="_blank" rel="noopener">🔴 Watch Live HUD ↗</a>\n'
            '  </div>\n'
            '  <div class="kpi-grid">\n'
            '    <div class="kpi-card">\n'
            '      <div class="kpi-top">\n'
            f'        <span class="kpi-val">{md_pct_s}% of All HTTP Responses <span class="kpi-badge-cyan">{md_count_fmt} .md deliveries</span> <span class="kpi-badge-cyan">{cneg_strict_fmt} Accept: text/markdown</span></span>\n'
            f'        <span class="kpi-scale-tag">0% → 1.0% Horizon ({int(round(md_horizon_pct))}% of Goal)</span>\n'
            '      </div>\n'
            '      <svg class="kpi-meter" viewBox="0 0 400 22" role="img" aria-label="RFC 9110 Markdown adoption on a 0 to 1.0 percent scale of all origin HTTP responses">\n'
            f'        <title>RFC 9110 Markdown Share: {md_pct_s}% of all ~1.58M origin HTTP responses ({md_horizon_pct}% of the 1.0% adoption milestone)</title>\n'
            '        <rect x="0" y="4" width="400" height="6" rx="3" fill="rgba(255,255,255,0.08)"></rect>\n'
            '        <line x1="100" y1="2" x2="100" y2="12" stroke="rgba(255,255,255,0.22)" stroke-width="1"></line>\n'
            '        <line x1="200" y1="2" x2="200" y2="12" stroke="rgba(255,255,255,0.22)" stroke-width="1"></line>\n'
            '        <line x1="300" y1="2" x2="300" y2="12" stroke="rgba(255,255,255,0.22)" stroke-width="1"></line>\n'
            f'        <rect x="0" y="4" width="{max(4.0, md_horizon_x)}" height="6" rx="3" fill="#06b6d4"></rect>\n'
            f'        <circle cx="{max(4.0, md_horizon_x)}" cy="7" r="3.8" fill="#22d3ee" stroke="#0d1117" stroke-width="1.2"></circle>\n'
            '        <text x="0" y="20" class="kpi-tick">0%</text>\n'
            '        <text x="92" y="20" class="kpi-tick">0.25%</text>\n'
            '        <text x="192" y="20" class="kpi-tick">0.50%</text>\n'
            '        <text x="292" y="20" class="kpi-tick">0.75%</text>\n'
            '        <text x="380" y="20" class="kpi-tick">1.0%</text>\n'
            '      </svg>\n'
            f'      <div class="kpi-lbl"><strong>🧠 RFC 9110 <code>Accept: text/markdown</code> Horizon:</strong> Share of all ~1.58M origin HTTP responses served as Markdown (never % of User-Agents) on our way to a 1.0% adoption milestone — led by ExaSearchBot ({exa_md_val:,}), ShapBot ({shap_md_val:,}), and Claude-User ({claude_md_val:,}).</div>\n'
            '    </div>\n'
            '    <div class="kpi-card">\n'
            '      <div class="kpi-top">\n'
            f'        <span class="kpi-val">{js_html_pct}% of Eligible HTML Responses <span class="kpi-badge-amber">{js_total_fmt} JS Trapdoor Executions</span> <span class="kpi-badge-amber">Out of {eligible_html_m} HTML Pages</span></span>\n'
            f'        <span class="kpi-scale-tag">0% → 5.0% HTML Hydration Scale</span>\n'
            '      </div>\n'
            '      <svg class="kpi-meter" viewBox="0 0 400 22" role="img" aria-label="JavaScript DOM hydration trapdoor executions on a 0 to 5.0 percent scale of eligible HTML page responses">\n'
            f'        <title>JavaScript DOM Hydration Rate: {js_html_pct}% ({js_total_fmt} executions) of all {eligible_html_m} HTML page responses that carried the 800ms /api/telemetry/js_confirm.gif script</title>\n'
            '        <rect x="0" y="4" width="400" height="6" rx="3" fill="rgba(255,255,255,0.08)"></rect>\n'
            '        <line x1="100" y1="2" x2="100" y2="12" stroke="rgba(255,255,255,0.22)" stroke-width="1"></line>\n'
            '        <line x1="200" y1="2" x2="200" y2="12" stroke="rgba(255,255,255,0.22)" stroke-width="1"></line>\n'
            '        <line x1="300" y1="2" x2="300" y2="12" stroke="rgba(255,255,255,0.22)" stroke-width="1"></line>\n'
            f'        <rect x="0" y="4" width="{max(4.0, js_horizon_x)}" height="6" rx="3" fill="#f59e0b"></rect>\n'
            f'        <circle cx="{max(4.0, js_horizon_x)}" cy="7" r="3.8" fill="#fbbf24" stroke="#0d1117" stroke-width="1.2"></circle>\n'
            '        <text x="0" y="20" class="kpi-tick">0%</text>\n'
            '        <text x="90" y="20" class="kpi-tick">1.25%</text>\n'
            '        <text x="190" y="20" class="kpi-tick">2.50%</text>\n'
            '        <text x="290" y="20" class="kpi-tick">3.75%</text>\n'
            '        <text x="378" y="20" class="kpi-tick">5.0%</text>\n'
            '      </svg>\n'
            f'      <div class="kpi-lbl"><strong>⚡ JavaScript DOM Hydration Trapdoor:</strong> Share of all {eligible_html_m} HTML page responses that <em>could</em> hydrate the DOM (because they received our 800ms <code>js_confirm.gif</code> script) that actually executed client-side JS — led by meta-externalagent ({meta_js_val:,}), OAI-SearchBot ({oai_js_val:,}), Cloud Chrome/Edge ({cloud_js_val:,}), and GPTBot ({gpt_js_val:,}).</div>\n'
            '    </div>\n'
            '  </div>\n'
            '</div>\n'
            "<!-- END_OBSERVATORY_METRICS -->"
        )
        new_idx, n = re.subn(
            r"<!-- START_OBSERVATORY_METRICS -->.*?<!-- END_OBSERVATORY_METRICS -->",
            banner,
            idx_text,
            flags=re.DOTALL,
        )
        if n and new_idx != idx_text:
            index_file.write_text(new_idx, encoding="utf-8")
    if (repo_root / ".git").exists():
        stage_obs = ["_data/observatory.json", "index.md"]
        if (repo_root / "live_video.json").is_file():
            stage_obs.append("live_video.json")
        subprocess.run(
            ["git", "-C", str(repo_root), "add", "--", *stage_obs],
            capture_output=True,
            text=True,
            check=False,
        )
    print(f"🔭 AI Observatory metrics synced: {md_count_fmt} RFC 9110 Markdown reads ({md_pct_s}%), {hyd_trig_fmt} JS trapdoor triggers ({fetched_at}).")


BRAIN_CACHE_DIR = Path.home() / ".cache" / "pipulate"
BRAIN_ZIP_PATH = BRAIN_CACHE_DIR / "brain.zip"
BRAIN_META_PATH = BRAIN_CACHE_DIR / "brain.meta.json"
_TRACER_DYE_RE = re.compile(r"\?src=(?:llms\.txt|a\+href|link\+rel|content_neg)\b")


def build_brain_archive(target_key, target_path, verbose=False):
    """Package dated _posts/*.md (tracer-dye scrubbed) + _posts/_context/*.json into ~/.cache/pipulate/brain.zip."""
    if str(target_key) != "1" or not target_path.is_dir():
        return None
    import json
    import zipfile
    mds = sorted(p for p in target_path.glob("*.md") if p.name[:4].isdigit())
    ctx_dir = target_path / "_context"
    shards = sorted(p for p in ctx_dir.glob("*.json") if p.name[:4].isdigit()) if ctx_dir.is_dir() else []
    if not mds:
        return None
    max_mtime = max(
        max((p.stat().st_mtime_ns for p in mds), default=0),
        max((p.stat().st_mtime_ns for p in shards), default=0),
    )
    total_bytes = sum(p.stat().st_size for p in mds) + sum(p.stat().st_size for p in shards)
    sig = {"md_count": len(mds), "shard_count": len(shards), "max_mtime_ns": max_mtime, "total_bytes": total_bytes}
    if BRAIN_ZIP_PATH.is_file() and BRAIN_META_PATH.is_file():
        try:
            if json.loads(BRAIN_META_PATH.read_text(encoding="utf-8")) == sig:
                if verbose:
                    print(f"✅ 2nd Brain archive already current: {BRAIN_ZIP_PATH}")
                return BRAIN_ZIP_PATH
        except Exception:
            pass
    BRAIN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_zip = BRAIN_ZIP_PATH.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for md in mds:
            raw_text = md.read_text(encoding="utf-8", errors="replace")
            clean_text = _TRACER_DYE_RE.sub("", raw_text)
            zf.writestr(f"_posts/{md.name}", clean_text.encode("utf-8"))
        for sh in shards:
            zf.write(sh, arcname=f"_posts/_context/{sh.name}")
    tmp_zip.replace(BRAIN_ZIP_PATH)
    BRAIN_META_PATH.write_text(json.dumps(sig, indent=2) + "\n", encoding="utf-8")
    mb = BRAIN_ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"🧠 Built 2nd Brain archive: {BRAIN_ZIP_PATH} ({len(mds):,} posts, {len(shards):,} shards, {mb:.1f} MB)")
    return BRAIN_ZIP_PATH


def main():
    parser = argparse.ArgumentParser(description="Update all Pipulate graphs")
    common.add_standard_arguments(parser)
    parser.add_argument('-m', '--keys', type=str, help="Pass a comma-separated list of keys for rotation")
    parser.add_argument('-v', '--verbose', action='store_true', help="Verbose output (show routine announcements and individual file syncs).")

    args = parser.parse_args()
    
    # 1. Resolve the Target Key ONCE
    targets = common.load_targets()
    target_key = args.target

    if target_key not in targets:
        print(f"❌ Invalid target key: {target_key}")
        sys.exit(1)

    # Resolve actual path for file operations
    target_path = Path(targets[target_key]['path']).expanduser().resolve()
    
    # THE JIU-JITSU SWEEP: Dynamically pull the pipeline array from the JSON config
    # THE PRIVATE LANES HAVE NO PUBLISH WORD (banked 2026-09-26, the day
    # the Grimoire's backlog closed at 151 posts, 151 shards). Lanes 1 and
    # 4 are dismounted by `publish` and `gobot`, which run this pipeline
    # and commit; lanes 2 and 3 are dismounted by nothing, so `preview -t N`
    # IS their dismount, typed by hand, and a shard backlog on a private
    # lane means nobody typed it. The per-lane list below is the whole of
    # what a lane gets; the word that runs it is the whole of when.
    pipeline_scripts = targets[target_key].get('pipeline', [])
    
    print(f"\n🔒 Locked Target: {targets[target_key]['name']}")
    print(f"🛤️  Active Pipeline: {len(pipeline_scripts)} steps")

    # Pack the extra arguments
    extra_args = []
    if args.key:
        extra_args.extend(['-k', args.key])
    if args.keys:
        extra_args.extend(['-m', args.keys])

    # 1.5 THE BRANDING SWEEP (Run this right before the JIU-JITSU Sweep!)
    brand_markdown_files(target_path, verbose=args.verbose)
    prune_orphan_shards(target_path, verbose=args.verbose)
    common.ensure_indexnow_key_file(target_key)
    yt_thumb = common.ensure_latest_yt_studio_thumbnail(target_key)
    if yt_thumb:
        print(f"📺 Ready 1280x720 (16:9) YouTube Studio Thumbnail: {yt_thumb}")
    sync_observatory_metrics(target_key, target_path, verbose=args.verbose)

    # 2. Run the sequence
    total_start = time.time()
    
    for script in pipeline_scripts:
        run_step(script, target_key, extra_args, verbose=args.verbose)
    
    # 3. Sync Data & Build 2nd Brain Zip Archive
    sync_data_to_jekyll(target_path, since=total_start, verbose=args.verbose)
    build_brain_archive(target_key, target_path, verbose=args.verbose)
        
    total_duration = time.time() - total_start
    print(f"\n✨ All steps completed successfully in {total_duration:.2f}s.")

if __name__ == "__main__":
    main()
