#!/usr/bin/env python3
"""
Pipulate Master Release Orchestrator

A comprehensive release pipeline that handles:
1. Version synchronization across all files
2. ASCII art documentation synchronization  
3. AI-generated commit messages via local LLM
4. Trifecta derivative plugin rebuilding (when template changes detected)
5. Git operations and PyPI publishing

Usage:
  python scripts/release/publish.py --release -m "Custom message"
  python scripts/release/publish.py --release --force -m "Force republish"
  python scripts/release/publish.py --release --ai-commit  # Use AI for commit message
  python scripts/release/publish.py --release --skip-trifecta-rebuild  # Skip plugin rebuilding
"""
import argparse
import subprocess
import sys
import re
import json
import requests
from pathlib import Path

# Rich table imports for beautiful output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("💡 Install 'rich' for beautiful table output: pip install rich")

# --- Configuration ---
try:
    PIPULATE_ROOT = Path(".").resolve()
except FileNotFoundError:
    print("Error: Could not resolve script path.")
    sys.exit(1)

INIT_PY_PATH = PIPULATE_ROOT / "__init__.py"
# Add Pipulate.com path configuration
PIPULATE_COM_ROOT = PIPULATE_ROOT.parent / "Pipulate.com"

# THE RULE OF SILENCE (2026-08-30). "When a program has nothing surprising to
# say, it should say nothing." One release run printed ~520 lines, ~430 of
# them `python -m build` copying files to itself and ~30 narrating which git
# command was about to run. The receipt a human needs fits on one screen: what
# changed, where it went, what got built, where it is. Quiet is the default;
# -v/--verbose restores the stream; a FAILURE prints everything the child said
# (the Rule of Repair), so silence never hides a RED.
VERBOSE = False


def note(msg):
    """A progress line that exists only under --verbose."""
    if VERBOSE:
        print(msg)


def run_command(cmd, cwd=PIPULATE_ROOT, capture=False, check=True, shell=False):
    """Run a command: quiet on success, loud on failure.
    The child's output is captured unless --verbose, so callers that pass
    capture=True read .stdout exactly as before and callers that never did may
    now read it too. On CalledProcessError every byte the child said goes to
    stderr before the exit, because a captured failure with no transcript is
    the one thing worse than 430 lines of build log.
    """
    shown = cmd if shell else ' '.join(cmd)
    note(f"🏃 Running: {shown} in {cwd}")
    try:
        return subprocess.run(cmd, cwd=str(cwd), capture_output=(capture or not VERBOSE),
                              text=True, check=check, shell=shell)
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed (exit {e.returncode}): {shown}", file=sys.stderr)
        for stream in (e.stdout, e.stderr):
            if stream and stream.strip():
                print(stream.rstrip(), file=sys.stderr)
        sys.exit(1)

def validate_git_remotes():
    """Validate git remote configuration and provide helpful guidance."""
    note("🔍 Validating git remote configuration...")
    
    try:
        # Check if we're in a git repository
        run_command(['git', 'rev-parse', '--git-dir'], capture=True)
        
        # Check if origin remote exists
        remotes_result = run_command(['git', 'remote', '-v'], capture=True)
        remotes_output = remotes_result.stdout.strip()
        
        if not remotes_output:
            print("⚠️  Warning: No git remotes configured")
            print("💡 To add origin remote: git remote add origin <repository-url>")
            return False
        
        # Check for origin specifically
        if 'origin' not in remotes_output:
            print("⚠️  Warning: No 'origin' remote found")
            print("💡 To add origin remote: git remote add origin <repository-url>")
            print(f"📋 Current remotes:\n{remotes_output}")
            return False
        
        # Check current branch
        branch_result = run_command(['git', 'branch', '--show-current'], capture=True)
        current_branch = branch_result.stdout.strip()
        
        if not current_branch:
            print("⚠️  Warning: Unable to determine current branch")
            return False
        
        note("✅ Git validation passed:")
        note(f"   📍 Current branch: {current_branch}")
        note("   🔗 Remote 'origin' configured")
        
        # Check upstream status (informational only)
        upstream_result = run_command(['git', 'rev-parse', '--abbrev-ref', f'{current_branch}@{{upstream}}'], 
                                    capture=True, check=False)
        
        if upstream_result.returncode == 0:
            upstream_branch = upstream_result.stdout.strip()
            note(f"   ⬆️  Upstream: {upstream_branch}")
        else:
            print(f"   🔗 No upstream configured (will be set automatically during push)")
        
        return True
        
    except Exception as e:
        print(f"⚠️  Git validation failed: {e}")
        print("💡 Make sure you're in a git repository with proper remote configuration")
        return False

def get_current_version():
    """Gets the version from pipulate/__init__.py."""
    content = INIT_PY_PATH.read_text()
    match = re.search(r"__version__\s*=\s*[\"']([^\"']+)[\"']", content)
    if not match:
        raise RuntimeError("Could not find __version__ in __init__.py")
    return match.group(1)

def pep440_normalize(version: str) -> str:
    """PEP 440 normalization ('2.00' -> '2.0') so printed PyPI URLs match
    the artifact twine actually uploads instead of drifting by a zero."""
    try:
        from packaging.version import Version
        return str(Version(version))
    except Exception:
        return version

def run_version_sync():
    """Runs the version synchronization script."""
    note("\n🔄 Step 1: Synchronizing versions across all files...")
    version_sync_script = PIPULATE_ROOT / "scripts" / "release" / "version_sync.py"
    if not version_sync_script.exists():
        print("❌ version_sync.py not found, skipping version sync")
        return False
    
    try:
        result = run_command(["python", str(version_sync_script)], capture=True)
        # Only the lines that name a CHANGE survive; "already up to date" is silence.
        for line in (result.stdout or "").splitlines():
            if "Updated" in line:
                print(line)
        note("✅ Version synchronization complete")
        return True
    except Exception as e:
        print(f"⚠️  Version sync failed: {e}")
        return False

def run_waxascii_release_stamp():
    """Programmatically stamps the canonical, text-only bunny into Markdown boundaries."""
    note("\n🎨 Step 1.5: Executing Idempotent Waxascii Header-Bounded Stamping...")
    try:
        sys.path.insert(0, str(PIPULATE_ROOT))
        from imports.ascii_displays import figurate
        rabbit = figurate("white_rabbit", context="release pipeline deployment stamp")
        sys.path.pop(0)
        
        if rabbit.drift:
            print(f"⚠️  Warning: Canonical white_rabbit shows drift={rabbit.drift}!")
            print("   ↳ Proceeding with document stamping loop because execution is in local test layout configuration.")
            
        raw_rabbit_art = rabbit.ai.strip()
        unique_invariant_line = ">  I HEREBY WILL NOT RE-GENERATE"
        
        # Targets to sweep and stamp smoothly across the mother system
        targets = [PIPULATE_ROOT / "README.md", PIPULATE_COM_ROOT / "index.md"]
        
        for target in targets:
            if not target.exists():
                print(f"ℹ️  Target path skipped (not found): {target}")
                continue
                
            content = target.read_text(encoding="utf-8")
            if unique_invariant_line not in content:
                note(f"ℹ️  No active visual canary matched inside {target.name}. Skipping injection.")
                continue
                
            lines = content.splitlines()
            target_idx = -1
            for idx, line in enumerate(lines):
                if unique_invariant_line in line:
                    target_idx = idx
                    break
                    
            if target_idx == -1:
                continue
                
            # Scan upwards for the parent header boundary
            start_header_idx = -1
            for idx in range(target_idx - 1, -1, -1):
                if lines[idx].startswith(("# ", "## ", "### ")):
                    start_header_idx = idx
                    break
                    
            # Scan downwards for the child header boundary
            end_header_idx = -1
            for idx in range(target_idx + 1, len(lines)):
                if lines[idx].startswith(("# ", "## ", "### ")):
                    end_header_idx = idx
                    break
                    
            if start_header_idx != -1 and end_header_idx != -1:
                # Reconstruct the file with a frozen layout padding constant
                before_block = lines[:start_header_idx + 1]
                after_block = lines[end_header_idx:]
                
                # Invariant formatting template to flatten padding modifications entirely
                new_middle = ["", "```text", raw_rabbit_art, "```", ""]
                
                updated_content = "\n".join(before_block + new_middle + after_block) + "\n"
                if updated_content != content:
                    target.write_text(updated_content, encoding="utf-8")
                    print(f"🎨 Wax seal restamped inside {target.name}")
                else:
                    note(f"✅ Wax seal already current inside {target.name}")
                
        return True
    except Exception as e:
        print(f"❌ Waxascii release stamping failed: {e}")
        return False

def run_ai_context_generation():
    """Regenerate AI_CONTEXT.md — the repo's self-describing briefing for any AI
    that clones and inspects it. Reads the (separate) blog archive and rewrites
    AI_CONTEXT.md in the Pipulate repo root from scratch, so a fresh clone always
    greets an AI with the latest narrative map. Non-fatal: skips cleanly if the
    generator or the article source is unavailable."""
    note("\n🧭 Step 1.6: Regenerating AI_CONTEXT.md (repo talk-back briefing)...")
    generator = PIPULATE_ROOT / "scripts" / "articles" / "generate_ai_context.py"
    if not generator.exists():
        print(f"ℹ️  AI_CONTEXT generator not found at {generator}. Skipping.")
        return False
    # Direct subprocess.run (not run_command) so a failure never sys.exit()s the release.
    result = subprocess.run([sys.executable, str(generator)], cwd=str(PIPULATE_ROOT),
                            capture_output=not VERBOSE, text=True)
    if result.returncode != 0:
        print("⚠️  AI_CONTEXT generation returned non-zero; continuing release.")
        for stream in (result.stdout, result.stderr):
            if stream and stream.strip():
                print(stream.rstrip(), file=sys.stderr)
        return False
    # Stage explicitly: `git commit -am` ignores untracked files, so the very
    # first (untracked) AI_CONTEXT.md must be added by hand. After that it rides -am.
    subprocess.run(["git", "add", "AI_CONTEXT.md"], cwd=str(PIPULATE_ROOT))
    note("✅ AI_CONTEXT.md regenerated and staged.")
    return True

def parse_ascii_art_stats(output):
    """Parse ASCII art synchronization statistics from output."""
    stats = {
        'files_updated': 0,
        'total_blocks_updated': 0,
        'ascii_blocks_found': 0,
        'used_blocks': 0,
        'unused_blocks': 0,
        'coverage_percentage': 0.0,
        'heuristic_candidates': 0,
        'quality_candidates': 0,
        'unknown_markers': 0,
        'markdown_files_scanned': 0
    }
    
    try:
        import re
        
        # Extract key statistics using regex patterns
        patterns = {
            'files_updated': r'📊 Files updated:\s*(\d+)',
            'total_blocks_updated': r'🔄 Total blocks updated:\s*(\d+)',
            'ascii_blocks_found': r'✅ Found (\d+) ASCII blocks in README\.md',
            'markdown_files_scanned': r'🔍 Found (\d+) markdown files',
            'used_blocks': r'✅ Used blocks:\s*(\d+)',
            'unused_blocks': r'📝 Unused blocks:\s*(\d+)',
            'coverage_percentage': r'Used blocks:\s*\d+ \((\d+\.?\d*)%\)',
            'heuristic_candidates': r'Found (\d+) potential ASCII art blocks in naked fenced code blocks',
            'quality_candidates': r'HIGH-QUALITY CANDIDATES \((\d+)\)',
            'unknown_markers': r'UNKNOWN MARKERS FOUND \((\d+)\)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, output)
            if match:
                if key == 'coverage_percentage':
                    stats[key] = float(match.group(1))
                else:
                    stats[key] = int(match.group(1))
    
    except Exception as e:
        print(f"⚠️  Failed to parse ASCII art statistics: {e}")
    
    return stats

def display_ascii_art_stats(stats):
    """Display ASCII art synchronization statistics in a beautiful rich table."""
    if not RICH_AVAILABLE or not stats:
        # Fallback to simple text display
        if stats:
            print("\n📊 ASCII ART SYNC STATISTICS:")
            print(f"   📄 Markdown files scanned: {stats['markdown_files_scanned']}")
            print(f"   📦 ASCII blocks found: {stats['ascii_blocks_found']}")
            print(f"   ✅ Used blocks: {stats['used_blocks']}")
            print(f"   📝 Unused blocks: {stats['unused_blocks']}")
            print(f"   📊 Coverage: {stats['coverage_percentage']:.1f}%")
            print(f"   🔄 Files updated: {stats['files_updated']}")
            print(f"   🎯 Blocks updated: {stats['total_blocks_updated']}")
        return
    
    console = Console()
    
    # Create ASCII art statistics table
    table = Table(
        title="📚 ASCII Art Sync Statistics",
        box=box.ROUNDED,
        title_style="bold blue",
        header_style="bold cyan",
        show_header=True,
        show_lines=True,
        expand=True
    )
    
    table.add_column("Metric", style="bold yellow", width=25)
    table.add_column("Value", style="white", width=15)
    table.add_column("Status", justify="center", width=15)
    
    # Add rows with appropriate status indicators
    coverage = stats['coverage_percentage']
    coverage_status = "🎯 Excellent" if coverage >= 80 else "⚡ Good" if coverage >= 60 else "📈 Improving"
    coverage_color = "green" if coverage >= 80 else "yellow" if coverage >= 60 else "red"
    
    table.add_row(
        "📄 Markdown Files Scanned",
        str(stats['markdown_files_scanned']),
        "🔍 Complete"
    )
    
    table.add_row(
        "📦 ASCII Blocks Available", 
        str(stats['ascii_blocks_found']),
        "📚 Ready"
    )
    
    table.add_row(
        "✅ Blocks in Use",
        str(stats['used_blocks']),
        "🎨 Active"
    )
    
    table.add_row(
        "📝 Unused Blocks",
        str(stats['unused_blocks']),
        "💤 Dormant" if stats['unused_blocks'] > 0 else "✨ All Used"
    )
    
    table.add_row(
        "📊 Coverage Percentage",
        Text(f"{coverage:.1f}%", style=f"bold {coverage_color}"),
        coverage_status
    )
    
    if stats['files_updated'] > 0:
        table.add_row(
            "🔄 Files Updated",
            str(stats['files_updated']),
            "✅ Synced"
        )
        
        table.add_row(
            "🎯 Blocks Updated",
            str(stats['total_blocks_updated']),
            "🚀 Fresh"
        )
    else:
        table.add_row(
            "🔄 Files Updated",
            "0",
            "✨ Current"
        )
    
    # Add discovery statistics if present
    if stats['heuristic_candidates'] > 0:
        table.add_row(
            "🔍 New Candidates Found",
            str(stats['heuristic_candidates']),
            "🌟 Potential"
        )
        
        if stats['quality_candidates'] > 0:
            table.add_row(
                "⭐ Quality Candidates",
                str(stats['quality_candidates']),
                "🎨 Promote"
            )
    
    if stats['unknown_markers'] > 0:
        table.add_row(
            "❓ Unknown Markers",
            str(stats['unknown_markers']),
            "⚠️ Review"
        )
    
    # Create a panel around the table
    panel = Panel(
        table,
        title="📚 Documentation Sync Results",
        title_align="center",
        border_style="bright_blue",
        padding=(1, 2)
    )
    
    console.print("\n")
    console.print(panel)

# ROSTER CUT 2026-08-01, hazard-convicted one turn after it was named: fdr.sh
# and replay.sh sat in this tuple for a day and the first ordinary `release`
# put both on the public internet at HTTP 200 -- neither ever ridden, neither
# ever syntax-checked in any compile receipt. A name in this tuple is not a
# plan; it is a live curl-pipe endpoint that fires on the next release with no
# further decision. Re-add either one in the SAME car as its first green ride
# receipt, never before. NOTE: cutting a name stops future SYNC; it does not
# delete the already-published file from the Pipulate.com checkout.
INSTALLER_SCRIPTS = ("install.sh", "mck.sh")
def sync_install_sh(script_name="install.sh"):
    """Copy ONE assets/installer/*.sh to Pipulate.com and commit if changed.
    ONE LANE, N SCRIPTS (2026-08-01). This function used to name install.sh in
    seven separate string literals, so fdr.sh and replay.sh could be authored,
    committed and pushed to the pipulate repo and still never become fetchable.
    curl -fsSL https://pipulate.com/<name> is served out of ~/repos/Pipulate.com
    (Jekyll/GitHub Pages), and THIS FUNCTION IS THE ONLY THING THAT PUTS A FILE
    THERE. A launcher nobody can fetch is a launcher that does not exist.
    THE ROSTER IS EXPLICIT, NOT A GLOB, on purpose: assets/installer/ is allowed
    to hold scripts that are not meant to be world-fetchable, and publishing by
    glob would silently redefine "put a file in this directory" as "publish it
    to the internet." Adding a name here is a deliberate act.
    """
    note(f"\n🔄 Step 3: Synchronizing {script_name} to Pipulate.com...")
    source_path = PIPULATE_ROOT / "assets/installer" / script_name
    dest_path = PIPULATE_COM_ROOT / script_name

    if not PIPULATE_COM_ROOT.exists():
        print(f"⚠️  Warning: Pipulate.com repo not found at {PIPULATE_COM_ROOT}. Skipping install.sh sync.")
        return False

    if not source_path.exists():
        print(f"⚠️  Warning: Source {script_name} not found at {source_path}. Skipping {script_name} sync.")
        return False

    # Copy the file
    dest_path.write_text(source_path.read_text())
    print(f"📄 Copied {source_path.name} to {dest_path}")

    # Check if there are changes in the Pipulate.com repo
    try:
        status_result = run_command(['git', 'status', '--porcelain', str(dest_path.name)], cwd=PIPULATE_COM_ROOT, capture=True)
        if status_result.stdout.strip():
            print(f"📦 Changes detected in {dest_path.name}. Committing and pushing...")
            run_command(['git', 'add', str(dest_path.name)], cwd=PIPULATE_COM_ROOT)
            commit_msg = f"chore: Update {script_name} from pipulate repo v{get_current_version()}"
            run_command(['git', 'commit', '-m', commit_msg], cwd=PIPULATE_COM_ROOT)
            
            # Handle upstream branch setup for Pipulate.com repo
            try:
                # Try to get current branch name
                branch_result = run_command(['git', 'branch', '--show-current'], cwd=PIPULATE_COM_ROOT, capture=True)
                current_branch = branch_result.stdout.strip()
                
                # Check if upstream is configured
                upstream_result = run_command(['git', 'rev-parse', '--abbrev-ref', f'{current_branch}@{{upstream}}'], 
                                            cwd=PIPULATE_COM_ROOT, capture=True, check=False)
                
                if upstream_result.returncode != 0:
                    # No upstream configured, set it during push
                    print(f"🔗 No upstream configured for Pipulate.com branch '{current_branch}', setting upstream...")
                    run_command(['git', 'push', '--set-upstream', 'origin', current_branch], cwd=PIPULATE_COM_ROOT)
                    print(f"✅ Pushed {script_name} update and set upstream: origin/{current_branch}")
                else:
                    # Upstream exists, normal push
                    run_command(['git', 'push'], cwd=PIPULATE_COM_ROOT)
                    print(f"✅ Pushed {script_name} update to Pipulate.com repo.")
                    
            except Exception as e:
                print(f"⚠️  Git push to Pipulate.com encountered an issue: {e}")
                print("🔄 Attempting fallback push with upstream setup...")
                try:
                    # Fallback: try to push with upstream setup
                    branch_result = run_command(['git', 'branch', '--show-current'], cwd=PIPULATE_COM_ROOT, capture=True)
                    current_branch = branch_result.stdout.strip()
                    run_command(['git', 'push', '--set-upstream', 'origin', current_branch], cwd=PIPULATE_COM_ROOT)
                    print(f"✅ Fallback successful: Pushed {script_name} update and set upstream: origin/{current_branch}")
                except Exception as fallback_error:
                    print(f"❌ Fallback push to Pipulate.com also failed: {fallback_error}")
                    print("💡 Pipulate.com repo may need manual git remote configuration")
                    return False
            
            return True
        else:
            note(f"✅ {script_name} is already up-to-date in Pipulate.com repo.")
            return False
    except Exception as e:
        print(f"⚠️  Install.sh sync failed: {e}")
        return False

def sync_audit_md():
    """Copies AUDIT.md to Pipulate.com root and commits if changed."""
    note("\n🔄 Step 3.5: Synchronizing AUDIT.md to Pipulate.com...")
    source_path = PIPULATE_ROOT / "AUDIT.md"
    dest_path = PIPULATE_COM_ROOT / "AUDIT.md"

    if not PIPULATE_COM_ROOT.exists():
        print(f"⚠️  Warning: Pipulate.com repo not found at {PIPULATE_COM_ROOT}. Skipping AUDIT.md sync.")
        return False

    if not source_path.exists():
        print(f"⚠️  Warning: Source AUDIT.md not found at {source_path}. Skipping AUDIT.md sync.")
        return False

    # Copy the file
    dest_path.write_text(source_path.read_text())
    print(f"📄 Copied {source_path.name} to {dest_path}")

    # Check if there are changes in the Pipulate.com repo
    try:
        status_result = run_command(['git', 'status', '--porcelain', str(dest_path.name)], cwd=PIPULATE_COM_ROOT, capture=True)
        if status_result.stdout.strip():
            print(f"📦 Changes detected in {dest_path.name}. Committing and pushing...")
            run_command(['git', 'add', str(dest_path.name)], cwd=PIPULATE_COM_ROOT)
            commit_msg = f"chore: Update AUDIT.md from pipulate repo v{get_current_version()}"
            run_command(['git', 'commit', '-m', commit_msg], cwd=PIPULATE_COM_ROOT)

            # Handle upstream branch setup for Pipulate.com repo
            try:
                branch_result = run_command(['git', 'branch', '--show-current'], cwd=PIPULATE_COM_ROOT, capture=True)
                current_branch = branch_result.stdout.strip()

                upstream_result = run_command(['git', 'rev-parse', '--abbrev-ref', f'{current_branch}@{{upstream}}'],
                                            cwd=PIPULATE_COM_ROOT, capture=True, check=False)

                if upstream_result.returncode != 0:
                    print(f"🔗 No upstream configured for Pipulate.com branch '{current_branch}', setting upstream...")
                    run_command(['git', 'push', '--set-upstream', 'origin', current_branch], cwd=PIPULATE_COM_ROOT)
                    print(f"✅ Pushed AUDIT.md update and set upstream: origin/{current_branch}")
                else:
                    run_command(['git', 'push'], cwd=PIPULATE_COM_ROOT)
                    print("✅ Pushed AUDIT.md update to Pipulate.com repo.")

            except Exception as e:
                print(f"⚠️  Git push to Pipulate.com encountered an issue: {e}")
                print("💡 Pipulate.com repo may need manual git remote configuration")
                return False

            return True
        else:
            note("✅ AUDIT.md is already up-to-date in Pipulate.com repo.")
            return False
    except Exception as e:
        print(f"⚠️  AUDIT.md sync failed: {e}")
        return False

def sync_ai_context_md():
    """Copies AI_CONTEXT.md to Pipulate.com root and commits if changed.

    Note: AI_CONTEXT.md is regenerated from scratch at Step 1.6
    (run_ai_context_generation), so by the time this runs the source is fresh.
    """
    note("\n🔄 Step 3.6: Synchronizing AI_CONTEXT.md to Pipulate.com...")
    source_path = PIPULATE_ROOT / "AI_CONTEXT.md"
    dest_path = PIPULATE_COM_ROOT / "AI_CONTEXT.md"

    if not PIPULATE_COM_ROOT.exists():
        print(f"⚠️  Warning: Pipulate.com repo not found at {PIPULATE_COM_ROOT}. Skipping AI_CONTEXT.md sync.")
        return False

    if not source_path.exists():
        print(f"⚠️  Warning: Source AI_CONTEXT.md not found at {source_path}. Skipping AI_CONTEXT.md sync.")
        return False

    # Copy the file
    dest_path.write_text(source_path.read_text())
    print(f"📄 Copied {source_path.name} to {dest_path}")

    # Check if there are changes in the Pipulate.com repo
    try:
        status_result = run_command(['git', 'status', '--porcelain', str(dest_path.name)], cwd=PIPULATE_COM_ROOT, capture=True)
        if status_result.stdout.strip():
            print(f"📦 Changes detected in {dest_path.name}. Committing and pushing...")
            run_command(['git', 'add', str(dest_path.name)], cwd=PIPULATE_COM_ROOT)
            commit_msg = f"chore: Update AI_CONTEXT.md from pipulate repo v{get_current_version()}"
            run_command(['git', 'commit', '-m', commit_msg], cwd=PIPULATE_COM_ROOT)

            # Handle upstream branch setup for Pipulate.com repo
            try:
                branch_result = run_command(['git', 'branch', '--show-current'], cwd=PIPULATE_COM_ROOT, capture=True)
                current_branch = branch_result.stdout.strip()

                upstream_result = run_command(['git', 'rev-parse', '--abbrev-ref', f'{current_branch}@{{upstream}}'],
                                            cwd=PIPULATE_COM_ROOT, capture=True, check=False)

                if upstream_result.returncode != 0:
                    print(f"🔗 No upstream configured for Pipulate.com branch '{current_branch}', setting upstream...")
                    run_command(['git', 'push', '--set-upstream', 'origin', current_branch], cwd=PIPULATE_COM_ROOT)
                    print(f"✅ Pushed AI_CONTEXT.md update and set upstream: origin/{current_branch}")
                else:
                    run_command(['git', 'push'], cwd=PIPULATE_COM_ROOT)
                    print("✅ Pushed AI_CONTEXT.md update to Pipulate.com repo.")

            except Exception as e:
                print(f"⚠️  Git push to Pipulate.com encountered an issue: {e}")
                print("💡 Pipulate.com repo may need manual git remote configuration")
                return False

            return True
        else:
            note("✅ AI_CONTEXT.md is already up-to-date in Pipulate.com repo.")
            return False
    except Exception as e:
        print(f"⚠️  AI_CONTEXT.md sync failed: {e}")
        return False

def sync_workspace_tree_to_com():
    """Splice the sealed workspace_tree art into Pipulate.com/index.md.
    THE THIRD PROJECTION, AND IT LIVES IN release.py RATHER THAN prompt_foo.py
    FOR A REASON READ OFF CADENCE, NOT OFF PATH. prompt_foo.py has never written
    outside REPO_ROOT and runs many times a day; a splice from there would leave
    a foreign git repo permanently dirty, and Pipulate.com's publish path does
    `git add .`, so the change would ride into a commit under whatever message
    that run happened to carry -- an unattributed write to a public site.
    release.py already crosses this boundary deliberately three times (installer
    scripts, AUDIT.md, AI_CONTEXT.md), each ending in add/commit/push against
    PIPULATE_COM_ROOT. This is the fourth deliberate crossing, same shape.
    IT IS A SPLICE, NOT A SYNC, WHICH IS WHY IT IS NOT A FOURTH COPY OF THE SYNC
    FAMILY. Those three COPY a source file over a destination. There is no source
    file here: the art is rendered from a sealed asset and injected into a region
    of an otherwise hand-authored page. Different verb, different function.
    IT ADOPTS index.md'S OWN KEYED SENTINEL NAMING rather than inventing a third
    convention. That file already carries two START_ASCII_ART pairs, both
    orphaned -- no live writer fills them -- and the key is exactly the parameter
    a future splice_sealed_art() will need. The SHAPE is deliberately not
    adopted: those orphans wrap hand-written headings and prose INSIDE the
    sentinels, and a generated region must contain only generated bytes, so this
    one's heading sits outside the pair.
    FAIL-CLOSED ON DRIFT, exactly like its siblings. Splicing art whose CRC
    reports drift would propagate a corrupted frame onto the project's public
    homepage. A stale homepage is a wound; a confidently wrong one is a lie.
    ABSENT vs DIRTY: refuse when the repo is missing; do NOT refuse merely
    because it is dirty. A content repo mid-edit is dirty as its normal state,
    and refusing there means firing almost never. Every git call below is scoped
    to index.md alone, so unrelated dirty files can never be swept in.
    """
    note("\n🗂️  Step 3.7: Splicing workspace tree into Pipulate.com/index.md...")
    dest_path = PIPULATE_COM_ROOT / "index.md"
    if not PIPULATE_COM_ROOT.exists():
        print(f"⚠️  Warning: Pipulate.com repo not found at {PIPULATE_COM_ROOT}. Skipping workspace tree splice.")
        return False
    if not dest_path.exists():
        print(f"⚠️  Warning: {dest_path} not found. Skipping workspace tree splice.")
        return False
    try:
        sys.path.insert(0, str(PIPULATE_ROOT))
        from imports.ascii_displays import figurate
        tree = figurate("workspace_tree", context="Pipulate.com homepage splice")
        sys.path.pop(0)
        if getattr(tree, 'drift', 0):
            print("⚠️  workspace_tree reports drift; index.md left untouched.")
            return False
        art = tree.ai.strip("\n")
        content = dest_path.read_text(encoding="utf-8")
        pattern = re.compile(
            r'(<!-- START_ASCII_ART: workspace-tree -->\n)(.*?)(<!-- END_ASCII_ART: workspace-tree -->)',
            re.DOTALL
        )
        match = pattern.search(content)
        if not match:
            print("ℹ️  No workspace-tree sentinels found inside index.md. Skipping injection.")
            return False
        # Fence literal split so this source line can never be eaten by apply.py's
        # own fence stripper -- the same dodge the prompt_foo splicers already use.
        fence = "``" + "`"
        block = f"{fence}text\n{art}\n{fence}\n"
        new_content = (
            content[:match.start()] + match.group(1) + block
            + match.group(3) + content[match.end():]
        )
        if new_content == content:
            note("✅ index.md workspace tree is already up-to-date.")
            return False
        dest_path.write_text(new_content, encoding="utf-8")
        print("🗂️  index.md workspace tree regenerated from the sealed asset.")
        status_result = run_command(['git', 'status', '--porcelain', dest_path.name], cwd=PIPULATE_COM_ROOT, capture=True)
        if not status_result.stdout.strip():
            note("✅ index.md is already up-to-date in Pipulate.com repo.")
            return False
        print(f"📦 Changes detected in {dest_path.name}. Committing and pushing...")
        run_command(['git', 'add', dest_path.name], cwd=PIPULATE_COM_ROOT)
        commit_msg = f"chore: Update index.md workspace tree from pipulate repo v{get_current_version()}"
        run_command(['git', 'commit', '-m', commit_msg], cwd=PIPULATE_COM_ROOT)
        branch_result = run_command(['git', 'branch', '--show-current'], cwd=PIPULATE_COM_ROOT, capture=True)
        current_branch = branch_result.stdout.strip()
        upstream_result = run_command(['git', 'rev-parse', '--abbrev-ref', f'{current_branch}@{{upstream}}'],
                                      cwd=PIPULATE_COM_ROOT, capture=True, check=False)
        if upstream_result.returncode != 0:
            print(f"🔗 No upstream configured for Pipulate.com branch '{current_branch}', setting upstream...")
            run_command(['git', 'push', '--set-upstream', 'origin', current_branch], cwd=PIPULATE_COM_ROOT)
        else:
            run_command(['git', 'push'], cwd=PIPULATE_COM_ROOT)
        print("✅ Pushed index.md workspace tree update to Pipulate.com repo.")
        return True
    except Exception as e:
        print(f"⚠️  Workspace tree splice failed: {e}")
        return False
def sync_breadcrumb_trail():
    """Syncs BREADCRUMB_TRAIL_DVCS.mdc to workspace root as DONT_WRITE_HERE.mdc with Cursor frontmatter."""
    note("\n🍞 Step 4: Synchronizing breadcrumb trail to workspace root...")
    
    # Define paths
    source_path = PIPULATE_ROOT / ".cursor" / "rules" / "BREADCRUMB_TRAIL_DVCS.mdc"
    workspace_root = PIPULATE_ROOT.parent
    dest_path = workspace_root / ".cursor" / "rules" / "BREADCRUMB_TRAIL.mdc"
    
    if not source_path.exists():
        # A warning that fires on every run is not a warning. .cursor/ is
        # gitignored, so this source never exists on a clone; the step is a
        # Cursor-era fossil and its whole body belongs in one deletion car.
        note(f"⚠️  Warning: Source breadcrumb trail not found at {source_path}. Skipping breadcrumb sync.")
        return False
    
    # Create destination directory if it doesn't exist
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Read source content
    source_content = source_path.read_text()
    
    # Create destination content with Cursor frontmatter
    cursor_frontmatter = """---
description: 
globs: 
alwaysApply: true
---
"""
    
    dest_content = cursor_frontmatter + source_content
    
    # Check if content has changed
    content_changed = True
    if dest_path.exists():
        current_content = dest_path.read_text()
        content_changed = current_content != dest_content
    
    if content_changed:
        # Write the new content
        dest_path.write_text(dest_content)
        print(f"📄 Synced breadcrumb trail: {source_path.name} → {dest_path}")
        print(f"📍 Location: {dest_path}")
        print("✅ Breadcrumb trail updated at workspace root for Cursor 'Always include'.")
        return True
    else:
        print("✅ Breadcrumb trail is already up-to-date at workspace root.")
        return False

def detect_trifecta_changes():
    """Check if the Botify Trifecta template has been modified in git."""
    trifecta_file = "apps/400_botify_trifecta.py"
    
    try:
        # Check if file is in staged changes
        staged_result = run_command(['git', 'diff', '--staged', '--name-only'], capture=True)
        if trifecta_file in staged_result.stdout:
            return True, "staged"
        
        # Check if file is in unstaged changes
        unstaged_result = run_command(['git', 'diff', '--name-only'], capture=True)
        if trifecta_file in unstaged_result.stdout:
            return True, "unstaged"
        
        # Check if file was modified in the last commit (in case we're doing a force republish)
        last_commit_result = run_command(['git', 'diff', 'HEAD~1', 'HEAD', '--name-only'], capture=True)
        if trifecta_file in last_commit_result.stdout:
            return True, "last_commit"
        
        return False, None
    except Exception as e:
        print(f"⚠️  Warning: Could not check Trifecta changes: {e}")
        return False, None

def rebuild_trifecta_derivatives():
    """Rebuild Parameter Buster and Link Graph from the updated Trifecta template."""
    print("\n🏗️ Step 4.5: Rebuilding Trifecta derivative plugins...")
    
    rebuild_script = PIPULATE_ROOT / "rebuild_trifecta_derivatives.sh"
    if not rebuild_script.exists():
        print(f"⚠️  Warning: Trifecta rebuild script not found at {rebuild_script}. Skipping rebuild.")
        return False, {}
    
    try:
        print("🔨 Executing deterministic Trifecta derivative reconstruction...")
        print("   📍 This ensures Parameter Buster and Link Graph inherit template improvements")
        
        # Run the rebuild script
        result = run_command([str(rebuild_script), "--verbose"], capture=True)
        output = result.stdout
        
        # Parse rebuild statistics from output
        stats = parse_trifecta_rebuild_stats(output)
        
        print("✅ Trifecta derivative reconstruction complete")
        return True, stats
    except Exception as e:
        print(f"⚠️  Trifecta rebuild failed: {e}")
        return False, {}

def parse_trifecta_rebuild_stats(output):
    """Parse Trifecta rebuild statistics from output."""
    stats = {
        'apps_rebuilt': 0,
        'parameter_buster_methods': 0,
        'link_graph_methods': 0,
        'success_rate': 0,
        'validation_passed': False
    }
    
    try:
        import re
        
        # Extract statistics
        if "Successfully processed: 2/2 plugins" in output:
            stats['apps_rebuilt'] = 2
            stats['success_rate'] = 100
            stats['validation_passed'] = True
        elif "Successfully processed: 1/2 plugins" in output:
            stats['apps_rebuilt'] = 1
            stats['success_rate'] = 50
        
        # Extract method counts
        param_match = re.search(r'Found (\d+) workflow-specific methods.*parameter', output, re.IGNORECASE)
        if param_match:
            stats['parameter_buster_methods'] = int(param_match.group(1))
        
        link_match = re.search(r'Found (\d+) workflow-specific methods.*link', output, re.IGNORECASE)
        if link_match:
            stats['link_graph_methods'] = int(link_match.group(1))
        
        # Look for validation results
        if "Validation passed" in output:
            stats['validation_passed'] = True
    
    except Exception as e:
        print(f"⚠️  Failed to parse Trifecta rebuild statistics: {e}")
    
    return stats

def display_trifecta_rebuild_stats(stats):
    """Display Trifecta rebuild statistics in a beautiful rich table."""
    if not RICH_AVAILABLE or not stats:
        # Fallback to simple text display
        if stats:
            print("\n🏗️ TRIFECTA REBUILD STATISTICS:")
            print(f"   🔨 Plugins rebuilt: {stats['apps_rebuilt']}/2")
            print(f"   📦 Parameter Buster methods: {stats['parameter_buster_methods']}")
            print(f"   🌐 Link Graph methods: {stats['link_graph_methods']}")
            print(f"   ✅ Success rate: {stats['success_rate']}%")
            print(f"   🎯 Validation: {'Passed' if stats['validation_passed'] else 'Failed'}")
        return
    
    console = Console()
    
    # Create Trifecta rebuild statistics table
    table = Table(
        title="🏗️ Trifecta Derivative Rebuild Statistics",
        box=box.ROUNDED,
        title_style="bold blue",
        header_style="bold cyan",
        show_header=True,
        show_lines=True,
        expand=True
    )
    
    table.add_column("Component", style="bold yellow", width=25)
    table.add_column("Value", style="white", width=15)
    table.add_column("Status", justify="center", width=15)
    
    # Add rebuild status
    success_color = "green" if stats['success_rate'] == 100 else "yellow" if stats['success_rate'] > 0 else "red"
    success_status = "🎯 Perfect" if stats['success_rate'] == 100 else "⚠️ Partial" if stats['success_rate'] > 0 else "❌ Failed"
    
    table.add_row(
        "🔨 Plugins Rebuilt",
        f"{stats['apps_rebuilt']}/2",
        Text(f"{stats['success_rate']}%", style=f"bold {success_color}")
    )
    
    if stats['parameter_buster_methods'] > 0:
        table.add_row(
            "📦 Parameter Buster Methods",
            str(stats['parameter_buster_methods']),
            "🔨 Transplanted"
        )
    
    if stats['link_graph_methods'] > 0:
        table.add_row(
            "🌐 Link Graph Methods", 
            str(stats['link_graph_methods']),
            "🔨 Transplanted"
        )
    
    table.add_row(
        "🎯 Template Inheritance",
        "AST-based",
        "✅ Deterministic" if stats['validation_passed'] else "⚠️ Check Required"
    )
    
    table.add_row(
        "🔍 Validation Status",
        "Complete" if stats['validation_passed'] else "Failed",
        "✅ Passed" if stats['validation_passed'] else "❌ Failed"
    )
    
    # Create a panel around the table
    panel = Panel(
        table,
        title="🏗️ Template Inheritance Results",
        title_align="center",
        border_style="bright_blue",
        padding=(1, 2)
    )
    
    console.print("\n")
    console.print(panel)

def analyze_git_changes():
    """Intelligently analyze git changes to categorize additions, deletions, modifications, etc."""
    note("🔍 Analyzing git changes for intelligent commit generation...")
    
    analysis = {
        'added_files': [],
        'deleted_files': [],
        'modified_files': [],
        'renamed_files': [],
        'lines_added': 0,
        'lines_deleted': 0,
        'is_housekeeping': False,
        'change_summary': '',
        'primary_action': 'modified'  # added, deleted, modified, renamed, housekeeping
    }
    
    try:
        # Get file status changes
        status_result = run_command(['git', 'status', '--porcelain'], capture=True)
        status_lines = status_result.stdout.strip().split('\n') if status_result.stdout.strip() else []
        
        for line in status_lines:
            if len(line) < 3:
                continue
            status = line[:2]
            filename = line[3:].strip()  # Remove any extra whitespace
            
            if status.startswith('A'):
                analysis['added_files'].append(filename)
            elif status.startswith('D'):
                analysis['deleted_files'].append(filename)
            elif status.startswith('M'):
                analysis['modified_files'].append(filename)
            elif status.startswith('R'):
                analysis['renamed_files'].append(filename)
        
        # Get line-level statistics using git diff --stat
        diff_stat_result = run_command(['git', 'diff', '--stat'], capture=True)
        if not diff_stat_result.stdout.strip():
            # Try staged changes
            diff_stat_result = run_command(['git', 'diff', '--staged', '--stat'], capture=True)
        
        stat_output = diff_stat_result.stdout.strip()
        if stat_output:
            # Parse the summary line (e.g., "3 files changed, 45 insertions(+), 12 deletions(-)")
            import re
            insertions_match = re.search(r'(\d+) insertions?\(\+\)', stat_output)
            deletions_match = re.search(r'(\d+) deletions?\(\-\)', stat_output)
            
            if insertions_match:
                analysis['lines_added'] = int(insertions_match.group(1))
            if deletions_match:
                analysis['lines_deleted'] = int(deletions_match.group(1))
        
        # Determine primary action and housekeeping nature
        total_files = len(analysis['added_files']) + len(analysis['deleted_files']) + len(analysis['modified_files']) + len(analysis['renamed_files'])
        
        # Check for housekeeping patterns
        housekeeping_indicators = [
            # File patterns that suggest cleanup
            any('test' in f.lower() for f in analysis['deleted_files']),
            any('.log' in f or '.tmp' in f or '.cache' in f for f in analysis['deleted_files']),
            any('backup' in f.lower() for f in analysis['deleted_files']),
            # High deletion-to-addition ratio
            analysis['lines_deleted'] > analysis['lines_added'] * 2 and analysis['lines_deleted'] > 50,
            # Mostly deletions with few/no additions
            len(analysis['deleted_files']) > len(analysis['added_files']) * 2 and len(analysis['deleted_files']) > 3
        ]
        
        analysis['is_housekeeping'] = any(housekeeping_indicators)
        
        # Determine primary action
        if len(analysis['deleted_files']) > len(analysis['added_files']) and len(analysis['deleted_files']) > len(analysis['modified_files']):
            analysis['primary_action'] = 'deleted'
        elif len(analysis['added_files']) > len(analysis['deleted_files']) and len(analysis['added_files']) > len(analysis['modified_files']):
            analysis['primary_action'] = 'added'
        elif len(analysis['renamed_files']) > 0:
            analysis['primary_action'] = 'renamed'
        elif analysis['is_housekeeping']:
            analysis['primary_action'] = 'housekeeping'
        else:
            analysis['primary_action'] = 'modified'
        
        # Create change summary
        parts = []
        if analysis['added_files']:
            parts.append(f"{len(analysis['added_files'])} files added")
        if analysis['deleted_files']:
            parts.append(f"{len(analysis['deleted_files'])} files deleted")
        if analysis['modified_files']:
            parts.append(f"{len(analysis['modified_files'])} files modified")
        if analysis['renamed_files']:
            parts.append(f"{len(analysis['renamed_files'])} files renamed")
        
        line_parts = []
        if analysis['lines_added']:
            line_parts.append(f"+{analysis['lines_added']} lines")
        if analysis['lines_deleted']:
            line_parts.append(f"-{analysis['lines_deleted']} lines")
        
        analysis['change_summary'] = ', '.join(parts)
        if line_parts:
            analysis['change_summary'] += f" ({', '.join(line_parts)})"
        
        note(f"📊 Change analysis: {analysis['change_summary']}")
        if analysis['is_housekeeping']:
            note("🧹 Detected housekeeping/cleanup operations")
        note(f"🎯 Primary action: {analysis['primary_action']}")
        
        return analysis
        
    except Exception as e:
        print(f"⚠️  Error analyzing git changes: {e}")
        return analysis

def get_ai_commit_message():
    """Gets an AI-generated commit message from the unified local LLM script."""
    note("🤖 Analyzing changes for AI commit message...")
    
    try:
        # FIX: Changed capture_output=True to capture=True to match your wrapper
        staged_result = run_command(['git', 'diff', '--staged'], capture=True)
        unstaged_result = run_command(['git', 'diff'], capture=True)
        if not staged_result.stdout.strip() and not unstaged_result.stdout.strip():
            print("❌ No changes found for AI commit message generation")
            return None, None
    except Exception as e:
        print(f"❌ Error checking git changes: {e}")
        return None, None
    
    change_analysis = analyze_git_changes()
    
    ai_script = PIPULATE_ROOT / "scripts" / "ai.py"
    if not ai_script.exists():
        print("❌ scripts/ai.py not found, skipping AI commit generation")
        return None, None
    
    try:
        import os
        import json
        import subprocess
        
        enhanced_env = os.environ.copy()
        enhanced_env['PIPULATE_CHANGE_ANALYSIS'] = json.dumps(change_analysis)
        
        result = subprocess.run(
            ["python", str(ai_script), "--auto", "--format", "plain"], 
            cwd=str(PIPULATE_ROOT),
            capture_output=True,  # This one is correct because it's using raw subprocess.run
            text=True,
            env=enhanced_env,
            check=False
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            
            # Robustly unpack the delimiter string passed from the unified ai.py
            parts = output.split('__MODEL_DELIMITER__')
            ai_message = parts[0].strip()
            model_name = parts[1].strip() if len(parts) > 1 else "AI Model"
            
            if ai_message:
                note("🤖 AI generated commit message:")
                note(f"   {ai_message}")
                return ai_message, model_name
            else:
                print("⚠️  AI commit script returned empty message")
                return None, None
        else:
            print(f"⚠️  AI commit script failed with error: {result.stderr}")
            return None, None
    except Exception as e:
        print(f"⚠️  AI commit generation failed: {e}")
        print("💡 Make sure Ollama is running: ollama serve")
        return None, None

def display_beautiful_summary(commit_message, ai_generated=False, version=None, published=False, ai_model_name=None, trifecta_rebuilt=False, trifecta_stats=None):
    """Display a beautiful rich table summary of the release."""
    if not RICH_AVAILABLE:
        # Fallback to simple text display
        print("\n" + "="*60)
        print("🎉 RELEASE SUMMARY")
        print("="*60)
        if ai_generated:
            model_display = f" ({ai_model_name})" if ai_model_name else ""
            print(f"🤖 AI-Generated Commit Message{model_display}:")
            print(f"   {commit_message}")
        else:
            print(f"📝 Commit Message: {commit_message}")
        if version:
            print(f"📦 Version: {version}")
        if published:
            print(f"🚀 Published to PyPI: ✅")
        if trifecta_rebuilt and trifecta_stats:
            print(f"🏗️ Trifecta Derivatives Rebuilt: {trifecta_stats.get('apps_rebuilt', 0)}/2 plugins")
        print("="*60)
        return
    
    console = Console()
    
    # Create the main summary table
    table = Table(
        title="🎉 Pipulate Release Summary",
        box=box.ROUNDED,
        title_style="bold magenta",
        header_style="bold cyan",
        show_header=True,
        show_lines=True,
        expand=True
    )
    
    table.add_column("Component", style="bold yellow", width=20)
    table.add_column("Details", style="white", width=60)
    table.add_column("Status", justify="center", width=10)
    
    # Add commit message row with special styling for AI-generated
    if ai_generated:
        commit_text = Text(commit_message, style="italic green")
        ai_label = f"🤖 {ai_model_name} Message" if ai_model_name else "🤖 AI Commit Message"
        ai_status = f"✨ {ai_model_name}" if ai_model_name else "✨ AI"
        table.add_row(
            ai_label,
            commit_text,
            ai_status
        )
    else:
        table.add_row(
            "📝 Commit Message", 
            commit_message,
            "📝 Manual"
        )
    
    # Add version row if provided
    if version:
        table.add_row(
            "📦 Version",
            version,
            "✅ Set"
        )
    
    # Add PyPI status if published
    if published:
        table.add_row(
            "🚀 PyPI Release",
            f"https://pypi.org/project/pipulate/{pep440_normalize(version)}/",
            "✅ Live"
        )
    
    # Add Trifecta rebuild status if performed
    if trifecta_rebuilt and trifecta_stats:
        rebuild_status = "✅ Perfect" if trifecta_stats.get('success_rate', 0) == 100 else "⚠️ Partial"
        table.add_row(
            "🏗️ Trifecta Derivatives",
            f"{trifecta_stats.get('apps_rebuilt', 0)}/2 plugins",
            rebuild_status
        )
    
    # Add timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    table.add_row(
        "⏰ Completed",
        timestamp,
        "🎯 Done"
    )
    
    # Create a panel around the table for extra beauty
    panel = Panel(
        table,
        title="🎉 Release Pipeline Complete",
        title_align="center",
        border_style="bright_green",
        padding=(1, 2)
    )
    
    console.print("\n")
    console.print(panel)

def main():
    global VERBOSE
    # Manifest the first bunny via the wand
    from pipulate import wand
    wand.figurate("white_rabbit")

    parser = argparse.ArgumentParser(description="Pipulate Master Release Orchestrator")
    parser.add_argument("--release", action="store_true", help="Perform a PyPI release")
    parser.add_argument("-m", "--message", type=str, help="Custom commit message")
    parser.add_argument("--force", action="store_true", help="Force operation even when no git changes detected")
    parser.add_argument("--ai-commit", action="store_true", help="Use AI to generate commit message")
    parser.add_argument("--skip-version-sync", action="store_true", help="Skip version synchronization")
    parser.add_argument("--skip-docs-sync", action="store_true", help="Skip documentation synchronization")
    parser.add_argument("--skip-install-sh-sync", action="store_true", help="Skip install.sh synchronization")
    parser.add_argument("--skip-audit-sync", action="store_true", help="Skip AUDIT.md synchronization")
    parser.add_argument("--skip-ai-context-sync", action="store_true", help="Skip AI_CONTEXT.md synchronization")
    parser.add_argument("--skip-breadcrumb-sync", action="store_true", help="Skip breadcrumb trail synchronization")
    parser.add_argument("--skip-trifecta-rebuild", action="store_true", help="Skip Trifecta derivative plugin rebuilding")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show every command and its full output (the Rule of Silence is the default)")
    
    args = parser.parse_args()
    VERBOSE = args.verbose
    
    note("🚀 Pipulate Master Release Orchestrator")
    note("=" * 50)
    
    current_version = get_current_version()
    print(f"📋 Current version: {current_version}")
    
    # Early validation of git configuration
    if not validate_git_remotes():
        print("\n❌ Git remote validation failed. Please fix git configuration before proceeding.")
        sys.exit(1)
    
    # === RELEASE PIPELINE PHASE 1: PREPARATION ===
    note("\n🔧 === RELEASE PIPELINE: PREPARATION PHASE ===")
    
    # Step 1: Version Synchronization
    if not args.skip_version_sync:
        version_sync_success = run_version_sync()
    else:
        print("\n⏭️  Skipping version synchronization (--skip-version-sync)")
        version_sync_success = True

    # Step 1.5: Programmatic Visual Canary Stamping
    if not args.skip_docs_sync:
        waxascii_sync_success = run_waxascii_release_stamp()
    else:
        print("\n⏭️  Skipping Waxascii release stamping (--skip-docs-sync)")
        waxascii_sync_success = True

    # Step 1.6: Regenerate the AI_CONTEXT.md repo briefing (talk-back map)
    if not args.skip_docs_sync:
        run_ai_context_generation()
    else:
        print("\n⏭️  Skipping AI_CONTEXT.md regeneration (--skip-docs-sync)")
    
    # Docs-sync step retired. Its "Skipping (--skip-docs-sync)" line printed on
    # EVERY run whether or not the flag was given: a false statement in the
    # receipt, and nothing read the two variables it set.
    
    # Step 3: Install.sh Synchronization
    if not args.skip_install_sh_sync:
        # EXPLICIT LOOP, NOT any(generator): any() short-circuits on the first
        # True, so the first CHANGED script would silently cancel every sync
        # after it -- a bug whose symptom is "sometimes mck.sh publishes."
        install_sh_success = False
        for _installer in INSTALLER_SCRIPTS:
            if sync_install_sh(_installer):
                install_sh_success = True
    else:
        print("\n⏭️  Skipping installer script synchronization (--skip-install-sh-sync)")
        install_sh_success = False

    # Step 3.5: AUDIT.md Synchronization
    if not args.skip_audit_sync:
        audit_md_success = sync_audit_md()
    else:
        print("\n⏭️  Skipping AUDIT.md synchronization (--skip-audit-sync)")
        audit_md_success = False

    # Step 3.6: AI_CONTEXT.md Synchronization
    if not args.skip_ai_context_sync:
        ai_context_md_success = sync_ai_context_md()
    else:
        print("\n⏭️  Skipping AI_CONTEXT.md synchronization (--skip-ai-context-sync)")
        ai_context_md_success = False
    
    # Step 3.7: Workspace Tree Splice into Pipulate.com
    workspace_tree_success = sync_workspace_tree_to_com()

    # Step 4: Breadcrumb Trail Synchronization
    if not args.skip_breadcrumb_sync:
        breadcrumb_sync_success = sync_breadcrumb_trail()
    else:
        print("\n⏭️  Skipping breadcrumb trail synchronization (--skip-breadcrumb-sync)")
        breadcrumb_sync_success = False
    
    # Step 4.5: Trifecta Derivative Rebuilding (if template was modified)
    trifecta_rebuild_success = False
    trifecta_rebuild_stats = {}
    if not args.skip_trifecta_rebuild:
        trifecta_changed, change_type = detect_trifecta_changes()
        if trifecta_changed:
            print(f"\n🔍 Detected Trifecta template changes ({change_type})")
            trifecta_rebuild_success, trifecta_rebuild_stats = rebuild_trifecta_derivatives()
            if trifecta_rebuild_stats:
                display_trifecta_rebuild_stats(trifecta_rebuild_stats)
        else:
            note("\n✅ No Trifecta template changes detected - skipping derivative rebuild")
    else:
        print("\n⏭️  Skipping Trifecta derivative rebuilding (--skip-trifecta-rebuild)")
    
    # === RELEASE PIPELINE PHASE 2: GIT OPERATIONS ===
    note("\n📝 === RELEASE PIPELINE: GIT OPERATIONS PHASE ===")
    
    # Check for git changes unless forcing
    has_changes = run_command(['git', 'status', '--porcelain'], capture=True).stdout.strip()
    
    if not has_changes and not args.force:
        print("\n✅ No changes to commit. Your repository is clean.")
        if args.release:
            print("💡 Use --force to proceed with PyPI republishing anyway.")
        else:
            print("💡 Use --force to proceed anyway, or make some changes first.")
        sys.exit(0)
    elif not has_changes and args.force:
        print("\n🚨 --force flag detected: Proceeding despite no git changes.")
        commit_message = args.message or "force: Manual republish without code changes"
        ai_generated_commit = False
        ai_model_name = None
    else:
        # We have changes, determine commit message
        if args.message:
            # User provided explicit message, use it
            commit_message = args.message
            ai_generated_commit = False
            ai_model_name = None
        else:
            # Default behavior: Try AI commit, fallback to standard message
            note("\n🤖 Generating AI commit message...")
            ai_message, model_name = get_ai_commit_message()
            if ai_message:
                commit_message = ai_message
                ai_generated_commit = True
                ai_model_name = model_name
            else:
                print("⚠️  Falling back to standard commit message")
                commit_message = "chore: Update project files"
                ai_generated_commit = False
                ai_model_name = None
    
    # Handle git operations
    if has_changes:
        # The receipt is git's own first line: hash and subject, once.
        committed = run_command(['git', 'commit', '-am', commit_message])
        first = (committed.stdout or "").strip().splitlines()
        print(first[0] if first else f"📝 Committed: {commit_message}")
        
        # Check if upstream branch exists and push accordingly
        try:
            # Try to get current branch name
            branch_result = run_command(['git', 'branch', '--show-current'], capture=True)
            current_branch = branch_result.stdout.strip()
            
            # Check if upstream is configured
            upstream_result = run_command(['git', 'rev-parse', '--abbrev-ref', f'{current_branch}@{{upstream}}'], 
                                        capture=True, check=False)
            
            if upstream_result.returncode != 0:
                # No upstream configured, set it during push
                print(f"🔗 No upstream configured for branch '{current_branch}', setting upstream...")
                run_command(['git', 'push', '--set-upstream', 'origin', current_branch])
                print(f"✅ Pushed changes and set upstream: origin/{current_branch}")
            else:
                # Upstream exists, normal push. git push talks on stderr; its
                # last line is the range, which is the only line worth keeping.
                pushed = run_command(['git', 'push'])
                tail = (pushed.stderr or "").strip().splitlines()
                print("✅ Pushed " + (tail[-1].strip() if tail else "changes to remote repository."))
                
        except Exception as e:
            print(f"⚠️  Git push operation encountered an issue: {e}")
            print("🔄 Attempting fallback push with upstream setup...")
            try:
                # Fallback: try to push with upstream setup
                branch_result = run_command(['git', 'branch', '--show-current'], capture=True)
                current_branch = branch_result.stdout.strip()
                run_command(['git', 'push', '--set-upstream', 'origin', current_branch])
                print(f"✅ Fallback successful: Pushed changes and set upstream: origin/{current_branch}")
            except Exception as fallback_error:
                print(f"❌ Fallback push also failed: {fallback_error}")
                print("💡 You may need to manually configure git remote or check network connectivity")
                sys.exit(1)
                
    elif args.force:
        print("🚨 --force flag: Skipping git commit (no changes to commit)")
        print("➡️  Proceeding directly to PyPI publishing...")
    
    # === RELEASE PIPELINE PHASE 3: PYPI PUBLISHING ===
    published_to_pypi = False
    if args.release:
        note("\n📦 === RELEASE PIPELINE: PYPI PUBLISHING PHASE ===")
        note(f"🏗️  Building and Publishing version {current_version} to PyPI...")
        note("🧹 Cleaning old build artifacts...")
        run_command("rm -rf dist/ build/ *.egg-info", shell=True)
        note("🛠️ Building package...")
        built = run_command([".venv/bin/python", '-m', 'build'])
        built_tail = (built.stdout or "").strip().splitlines()
        print(built_tail[-1] if built_tail else "🛠️ Built (run with -v for the build log)")
        note("📦 Publishing to PyPI...")
        run_command([".venv/bin/python", '-m', 'twine', 'upload', 'dist/*'])
        print(f"🎉 Published {current_version} -> https://pypi.org/project/pipulate/{pep440_normalize(current_version)}/")
        published_to_pypi = True
    
    # === BEAUTIFUL SUMMARY DISPLAY ===
    note("\n" + "=" * 50)
    display_beautiful_summary(
        commit_message=commit_message,
        ai_generated=ai_generated_commit,
        version=current_version,
        published=published_to_pypi,
        ai_model_name=ai_model_name,
        trifecta_rebuilt=trifecta_rebuild_success,
        trifecta_stats=trifecta_rebuild_stats
    )
    
    # 🔄 Trigger server restart so user can immediately talk to Chip about the update
    note("\n🔄 Triggering server restart for immediate Chip interaction...")
    server_py_path = PIPULATE_ROOT / "server.py"
    if server_py_path.exists():
        # Touch the server.py file to trigger watchdog restart
        server_py_path.touch()
        print("🔄 server.py touched; the watchdog restarts the server.")
    else:
        print("⚠️  server.py not found, manual restart may be needed")

if __name__ == "__main__":
    main()

