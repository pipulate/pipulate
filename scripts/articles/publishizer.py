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
    # 1. RFC 9110 Adoption Horizon (0% -> 20% linear target scale; 200px SVG track)
    md_horizon_pct = min(100.0, max(0.0, round((md_pct_val / 20.0) * 100.0, 2)))
    md_horizon_x = round((md_horizon_pct / 100.0) * 200.0, 1)
    # 2. Bimodal AI Sensor Split (JS Trapdoor Triggers vs. RFC 9110 Markdown Reads)
    total_ai_signals = max(1, hyd_trig_val + md_count_val)
    js_share_pct = round((hyd_trig_val / total_ai_signals) * 100.0, 1)
    md_share_pct = round(100.0 - js_share_pct, 1)
    js_bar_w = round((js_share_pct / 100.0) * 200.0, 1)
    md_bar_w = round(200.0 - js_bar_w, 1)
    # 3. Markdown Bot Identity Forensics (IP-Spoofed Googlebot vs. Authentic Self-Asserted Bots)
    spoof_share_pct = round((spoof_val / max(1, bot_md_val)) * 100.0, 1)
    auth_share_pct = round(100.0 - spoof_share_pct, 1)
    spoof_bar_w = round((spoof_share_pct / 100.0) * 200.0, 1)
    auth_bar_w = round(200.0 - spoof_bar_w, 1)
    # 4. RFC 9421 Web Bot Auth Signed Clients & Events (from access.log + honeybot.db)
    sig_clients_val, sig_events_val = 3, 11
    try:
        sig_cmd = (
            "grep 'Sig:\"' /var/log/nginx/access.log | grep -v 'Sig:\"-\"' | "
            "awk -F'Sig:\"' '{print $2}' | awk -F'\"' '{c[$1]++; n++} END{print length(c) \"|\" (n+0)}'"
        )
        sig_res = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "honeybot", sig_cmd],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if sig_res.returncode == 0 and "|" in (sig_res.stdout or ""):
            sc_s, se_s = (p.strip() for p in sig_res.stdout.strip().split("|", 1))
            if sc_s.isdigit() and int(sc_s) > 0:
                sig_clients_val = int(sc_s)
            if se_s.isdigit() and int(se_s) > 0:
                sig_events_val = int(se_s)
    except Exception:
        pass
    sig_clients_fmt = f"{sig_clients_val:,}"
    sig_events_fmt = f"{sig_events_val:,}"
    sig_horizon_x = min(200.0, max(6.0, round((sig_clients_val / 10.0) * 200.0, 1)))
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
        "js_trapdoor_triggers": hyd_trig_fmt,
        "js_trapdoor_ips": hyd_ips_fmt,
        "js_share_pct": f"{js_share_pct}%",
        "md_share_pct": f"{md_share_pct}%",
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
            '    <a class="kpi-live-pill" href="https://www.youtube.com/@MikeLevin/live" target="_blank" rel="noopener">🔴 Watch Live HUD ↗</a>\n'
            '  </div>\n'
            '  <div class="kpi-grid">\n'
            '    <div class="kpi-card">\n'
            '      <div class="kpi-top">\n'
            f'        <span class="kpi-val">{md_pct_s}% <span class="kpi-badge-cyan">{md_count_fmt} .md reads</span></span>\n'
            '        <span class="kpi-scale-tag">0% → 20% Horizon</span>\n'
            '      </div>\n'
            '      <svg class="kpi-meter" viewBox="0 0 200 22" role="img" aria-label="RFC 9110 Markdown adoption on a 0 to 20 percent horizon scale">\n'
            f'        <title>RFC 9110 Markdown Share: {md_pct_s}% of all origin responses ({md_horizon_pct}% of the 20% adoption horizon)</title>\n'
            '        <rect x="0" y="4" width="200" height="6" rx="3" fill="rgba(255,255,255,0.08)"></rect>\n'
            '        <line x1="50" y1="2" x2="50" y2="12" stroke="rgba(255,255,255,0.22)" stroke-width="1"></line>\n'
            '        <line x1="100" y1="2" x2="100" y2="12" stroke="rgba(255,255,255,0.22)" stroke-width="1"></line>\n'
            '        <line x1="150" y1="2" x2="150" y2="12" stroke="rgba(255,255,255,0.22)" stroke-width="1"></line>\n'
            f'        <rect x="0" y="4" width="{max(2.5, md_horizon_x)}" height="6" rx="3" fill="#06b6d4"></rect>\n'
            f'        <circle cx="{max(3.5, md_horizon_x)}" cy="7" r="3.8" fill="#22d3ee" stroke="#0d1117" stroke-width="1.2"></circle>\n'
            '        <text x="0" y="20" class="kpi-tick">0%</text>\n'
            '        <text x="46" y="20" class="kpi-tick">5%</text>\n'
            '        <text x="93" y="20" class="kpi-tick">10%</text>\n'
            '        <text x="143" y="20" class="kpi-tick">15%</text>\n'
            '        <text x="180" y="20" class="kpi-tick">20%</text>\n'
            '      </svg>\n'
            '      <div class="kpi-lbl">RFC 9110 <code>Accept: text/markdown</code> Adoption</div>\n'
            '    </div>\n'
            '    <div class="kpi-card">\n'
            '      <div class="kpi-top">\n'
            f'        <span class="kpi-val">{hyd_trig_fmt} <span class="kpi-badge-amber">{js_share_pct}% JS</span> vs. {md_count_fmt} <span class="kpi-badge-cyan">{md_share_pct}% .md</span></span>\n'
            '      </div>\n'
            '      <svg class="kpi-meter" viewBox="0 0 200 22" role="img" aria-label="Bimodal split between JS trapdoor executions and RFC 9110 Markdown reads">\n'
            f'        <title>Bimodal AI Sensor Split: {hyd_trig_fmt} JS executions ({js_share_pct}%) vs. {md_count_fmt} Markdown reads ({md_share_pct}%)</title>\n'
            f'        <rect x="0" y="4" width="{js_bar_w}" height="6" rx="3" fill="#f59e0b"></rect>\n'
            f'        <rect x="{js_bar_w}" y="4" width="{md_bar_w}" height="6" rx="3" fill="#06b6d4"></rect>\n'
            f'        <text x="0" y="20" class="kpi-tick">⚡ JS Trapdoor ({hyd_ips_fmt} IPs · OAI-SearchBot)</text>\n'
            '        <text x="148" y="20" class="kpi-tick">🧠 RFC 9110</text>\n'
            '      </svg>\n'
            '      <div class="kpi-lbl">Bimodal AI Sensor Split (DOM Hydration vs. Raw Markdown)</div>\n'
            '    </div>\n'
            '    <div class="kpi-card">\n'
            '      <div class="kpi-top">\n'
            f'        <span class="kpi-val">{sig_events_fmt} <span class="kpi-badge-cyan">🔷 Signed Hits</span> · {sig_clients_fmt} <span class="kpi-badge-cyan">Clients</span></span>\n'
            '      </div>\n'
            '      <svg class="kpi-meter" viewBox="0 0 200 22" role="img" aria-label="RFC 9421 Web Bot Auth cryptographic agent adoption">\n'
            f'        <title>RFC 9421 Web Bot Auth: {sig_events_fmt} cryptographically signed requests across {sig_clients_fmt} verified bot operators (ExaSearchBot, AhrefsBot, DesearchBot)</title>\n'
            '        <rect x="0" y="4" width="200" height="6" rx="3" fill="rgba(255,255,255,0.08)"></rect>\n'
            f'        <rect x="0" y="4" width="{sig_horizon_x}" height="6" rx="3" fill="#38bdf8"></rect>\n'
            f'        <circle cx="{sig_horizon_x}" cy="7" r="3.8" fill="#38bdf8" stroke="#0d1117" stroke-width="1.2"></circle>\n'
            '        <text x="0" y="20" class="kpi-tick">🔷 ExaSearchBot · AhrefsBot · DesearchBot</text>\n'
            '      </svg>\n'
            '      <div class="kpi-lbl">RFC 9421 <code>Web Bot Auth</code> (<code>Signature-Agent</code>)</div>\n'
            '    </div>\n'
            '    <div class="kpi-card">\n'
            '      <div class="kpi-top">\n'
            f'        <span class="kpi-val">{spoof_fmt} <span class="kpi-badge-red">🛑 {spoof_share_pct}% Cloaked</span> vs. {auth_bot_fmt} <span class="kpi-badge-amber">🟠 {auth_share_pct}% Bot UA</span></span>\n'
            '      </div>\n'
            '      <svg class="kpi-meter" viewBox="0 0 200 22" role="img" aria-label="Proportion of spoofed Googlebot IPs versus authentic self-asserted bots negotiating Markdown">\n'
            f'        <title>Markdown Bot Forensics: {spoof_fmt} IP-spoofed Googlebot reads ({spoof_share_pct}%) vs. {auth_bot_fmt} authentic self-asserted bot reads ({auth_share_pct}%)</title>\n'
            f'        <rect x="0" y="4" width="{spoof_bar_w}" height="6" rx="3" fill="#ef4444"></rect>\n'
            f'        <rect x="{spoof_bar_w}" y="4" width="{auth_bar_w}" height="6" rx="3" fill="#f97316"></rect>\n'
            '        <text x="0" y="20" class="kpi-tick">🛑 Spoofed Googlebot IPs</text>\n'
            '        <text x="118" y="20" class="kpi-tick">🟠 Self-Asserted Bots</text>\n'
            '      </svg>\n'
            '      <div class="kpi-lbl">Unmasked Cloakers in RFC 9110 Markdown Stream</div>\n'
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
