import subprocess
import sys
import time
import shlex
import shutil
import argparse
from pathlib import Path
import common


def brand_markdown_files(target_path):
    """Sweeps the posts directory and swaps **Me**: for the semantic brand."""
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
        print(f"✅ Applied semantic branding to {count} files.")
    else:
        print("✅ All files are perfectly branded.")


def prune_orphan_shards(target_path):
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
    if removed == 0:
        print("✅ No orphan shards.")


def run_step(script_name, target_key, extra_args=None):
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
def sync_data_to_jekyll(target_path, since=0.0):
    """
    Copies the generated artifacts to the Jekyll SITE ROOT.
    """
    print("\n--- 📦 Syncing Data to Jekyll ---")
    
    # Source is local to this script
    script_dir = Path(__file__).parent
    
    # Artifacts to sync
    artifacts = {
        "graph.json": "graph.json",
        "llms.txt": "llms.txt",
    }
    
    # target_path is usually .../trimnoir/_posts
    # We want the site root: .../trimnoir/
    repo_root = target_path.parent
    
    # Sync static artifacts
    for filename, dest_name in artifacts.items():
        source = script_dir / filename
        dest = repo_root / dest_name
        
        if source.exists() and source.stat().st_mtime < since:
            print(f"⏭️  {filename} predates this run; another lane made it. Not synced.")
            continue
        if source.exists():
            shutil.copy2(source, dest)
            print(f"✅ Synced {filename} -> {dest}")
        else:
            print(f"⚠️ Warning: {filename} not found. Skipping sync.")

    # Sync dynamic sitemaps (sitemap.xml, sitemap-core.xml, sitemap-branch-0.xml, etc.)
    for sitemap in script_dir.glob("sitemap*.xml"):
        if sitemap.stat().st_mtime < since:
            print(f"⏭️  {sitemap.name} predates this run; another lane made it. Not synced.")
            continue
        dest = repo_root / sitemap.name
        shutil.copy2(sitemap, dest)
        print(f"✅ Synced {sitemap.name} -> {dest}")

def main():
    parser = argparse.ArgumentParser(description="Update all Pipulate graphs")
    common.add_standard_arguments(parser)
    parser.add_argument('-m', '--keys', type=str, help="Pass a comma-separated list of keys for rotation")

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
    brand_markdown_files(target_path)
    prune_orphan_shards(target_path)

    # 2. Run the sequence
    total_start = time.time()
    
    for script in pipeline_scripts:
        run_step(script, target_key, extra_args)
    
    # 3. Sync Data
    sync_data_to_jekyll(target_path, since=total_start)
        
    total_duration = time.time() - total_start
    print(f"\n✨ All steps completed successfully in {total_duration:.2f}s.")

if __name__ == "__main__":
    main()
