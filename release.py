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

def run_command(cmd, cwd=PIPULATE_ROOT, capture=False, check=True, shell=False):
    """Runs a command and handles errors."""
    print(f"🏃 Running: {' '.join(cmd) if not shell else cmd} in {cwd}")
    try:
        result = subprocess.run(cmd, cwd=str(cwd), capture_output=capture, text=True, check=check, shell=shell)
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {' '.join(cmd) if not shell else cmd}", file=sys.stderr)
        sys.exit(1)

def validate_git_remotes():
    """Validate git remote configuration and provide helpful guidance."""
    print("🔍 Validating git remote configuration...")
    
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
        
        print(f"✅ Git validation passed:")
        print(f"   📍 Current branch: {current_branch}")
        print(f"   🔗 Remote 'origin' configured")
        
        # Check upstream status (informational only)
        upstream_result = run_command(['git', 'rev-parse', '--abbrev-ref', f'{current_branch}@{{upstream}}'], 
                                    capture=True, check=False)
        
        if upstream_result.returncode == 0:
            upstream_branch = upstream_result.stdout.strip()
            print(f"   ⬆️  Upstream: {upstream_branch}")
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

def run_version_sync():
    """Runs the version synchronization script."""
    print("\n🔄 Step 1: Synchronizing versions across all files...")
    version_sync_script = PIPULATE_ROOT / "scripts" / "release" / "version_sync.py"
    if not version_sync_script.exists():
        print("❌ version_sync.py not found, skipping version sync")
        return False
    
    try:
        run_command(["python", str(version_sync_script)])
        print("✅ Version synchronization complete")
        return True
    except Exception as e:
        print(f"⚠️  Version sync failed: {e}")
        return False

def run_ascii_art_sync():
    """Runs the ASCII art documentation synchronization and captures statistics."""
    print("\n📚 Step 2: Synchronizing ASCII art documentation...")
    ascii_sync_script = PIPULATE_ROOT / "scripts" / "release" / "sync_ascii_art.py"
    if not ascii_sync_script.exists():
        print("❌ sync_ascii_art.py not found, skipping documentation sync")
        return False, None
    
    try:
        result = run_command([".venv/bin/python", str(ascii_sync_script)], capture=True)
        output = result.stdout
        
        # Parse statistics from output
        stats = parse_ascii_art_stats(output)
        
        print("✅ ASCII art documentation synchronization complete")
        return True, stats
    except Exception as e:
        print(f"⚠️  Documentation sync failed: {e}")
        return False, None

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

def sync_install_sh():
    """Copies install.sh to Pipulate.com and commits if changed."""
    print("\n🔄 Step 3: Synchronizing install.sh to Pipulate.com...")
    source_path = PIPULATE_ROOT / "assets/installer/install.sh"
    dest_path = PIPULATE_COM_ROOT / "install.sh"

    if not PIPULATE_COM_ROOT.exists():
        print(f"⚠️  Warning: Pipulate.com repo not found at {PIPULATE_COM_ROOT}. Skipping install.sh sync.")
        return False

    if not source_path.exists():
        print(f"⚠️  Warning: Source install.sh not found at {source_path}. Skipping install.sh sync.")
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
            commit_msg = f"chore: Update install.sh from pipulate repo v{get_current_version()}"
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
                    print(f"✅ Pushed install.sh update and set upstream: origin/{current_branch}")
                else:
                    # Upstream exists, normal push
                    run_command(['git', 'push'], cwd=PIPULATE_COM_ROOT)
                    print("✅ Pushed install.sh update to Pipulate.com repo.")
                    
            except Exception as e:
                print(f"⚠️  Git push to Pipulate.com encountered an issue: {e}")
                print("🔄 Attempting fallback push with upstream setup...")
                try:
                    # Fallback: try to push with upstream setup
                    branch_result = run_command(['git', 'branch', '--show-current'], cwd=PIPULATE_COM_ROOT, capture=True)
                    current_branch = branch_result.stdout.strip()
                    run_command(['git', 'push', '--set-upstream', 'origin', current_branch], cwd=PIPULATE_COM_ROOT)
                    print(f"✅ Fallback successful: Pushed install.sh update and set upstream: origin/{current_branch}")
                except Exception as fallback_error:
                    print(f"❌ Fallback push to Pipulate.com also failed: {fallback_error}")
                    print("💡 Pipulate.com repo may need manual git remote configuration")
                    return False
            
            return True
        else:
            print("✅ install.sh is already up-to-date in Pipulate.com repo.")
            return False
    except Exception as e:
        print(f"⚠️  Install.sh sync failed: {e}")
        return False

def sync_breadcrumb_trail():
    """Syncs BREADCRUMB_TRAIL_DVCS.mdc to workspace root as DONT_WRITE_HERE.mdc with Cursor frontmatter."""
    print("\n🍞 Step 4: Synchronizing breadcrumb trail to workspace root...")
    
    # Define paths
    source_path = PIPULATE_ROOT / ".cursor" / "rules" / "BREADCRUMB_TRAIL_DVCS.mdc"
    workspace_root = PIPULATE_ROOT.parent
    dest_path = workspace_root / ".cursor" / "rules" / "BREADCRUMB_TRAIL.mdc"
    
    if not source_path.exists():
        print(f"⚠️  Warning: Source breadcrumb trail not found at {source_path}. Skipping breadcrumb sync.")
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

def get_ai_model_name():
    """Extract the model name from ai_commit.py."""
    ai_commit_script = PIPULATE_ROOT / "scripts" / "release" / "ai_commit.py"
    if not ai_commit_script.exists():
        return "AI Model"
    
    try:
        content = ai_commit_script.read_text()
        # Look for OLLAMA_MODEL = "model_name"
        import re
        match = re.search(r'OLLAMA_MODEL\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
        else:
            return "AI Model"
    except Exception:
        return "AI Model"

def analyze_git_changes():
    """Intelligently analyze git changes to categorize additions, deletions, modifications, etc."""
    print("🔍 Analyzing git changes for intelligent commit generation...")
    
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
        
        print(f"📊 Change analysis: {analysis['change_summary']}")
        if analysis['is_housekeeping']:
            print("🧹 Detected housekeeping/cleanup operations")
        print(f"🎯 Primary action: {analysis['primary_action']}")
        
        return analysis
        
    except Exception as e:
        print(f"⚠️  Error analyzing git changes: {e}")
        return analysis

def get_ai_commit_message():
    """Gets an AI-generated commit message from local LLM with intelligent change analysis."""
    print("🤖 Analyzing changes for AI commit message...")
    
    # Check if there are any changes (staged or unstaged)
    try:
        staged_result = run_command(['git', 'diff', '--staged'], capture=True)
        unstaged_result = run_command(['git', 'diff'], capture=True)
        if not staged_result.stdout.strip() and not unstaged_result.stdout.strip():
            print("❌ No changes found for AI commit message generation")
            return None, None
    except Exception as e:
        print(f"❌ Error checking git changes: {e}")
        return None, None
    
    # Analyze changes intelligently
    change_analysis = analyze_git_changes()
    
    # Get the model name
    model_name = get_ai_model_name()
    
    # Try to get AI commit message with enhanced context
    ai_commit_script = PIPULATE_ROOT / "scripts" / "release" / "ai_commit.py"
    if not ai_commit_script.exists():
        print("❌ ai_commit.py not found, skipping AI commit generation")
        return None, None
    
    try:
        # Create enhanced environment variables to pass analysis to ai_commit.py
        import os
        import json
        
        # Pass the analysis as environment variable
        enhanced_env = os.environ.copy()
        enhanced_env['PIPULATE_CHANGE_ANALYSIS'] = json.dumps(change_analysis)
        
        # Use subprocess directly to pass environment variables
        import subprocess
        result = subprocess.run(
            ["python", str(ai_commit_script)], 
            cwd=str(PIPULATE_ROOT),
            capture_output=True,
            text=True,
            env=enhanced_env,
            check=False  # Don't raise exception on error
        )
        
        if result.returncode == 0:
            ai_message = result.stdout.strip()
            if ai_message:
                print(f"🤖 AI generated commit message:")
                print(f"   {ai_message}")
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
            f"https://pypi.org/project/pipulate/{version}/",
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
    parser = argparse.ArgumentParser(description="Pipulate Master Release Orchestrator")
    parser.add_argument("--release", action="store_true", help="Perform a PyPI release")
    parser.add_argument("-m", "--message", type=str, help="Custom commit message")
    parser.add_argument("--force", action="store_true", help="Force operation even when no git changes detected")
    parser.add_argument("--ai-commit", action="store_true", help="Use AI to generate commit message")
    parser.add_argument("--skip-version-sync", action="store_true", help="Skip version synchronization")
    parser.add_argument("--skip-docs-sync", action="store_true", help="Skip documentation synchronization")
    parser.add_argument("--skip-install-sh-sync", action="store_true", help="Skip install.sh synchronization")
    parser.add_argument("--skip-breadcrumb-sync", action="store_true", help="Skip breadcrumb trail synchronization")
    parser.add_argument("--skip-trifecta-rebuild", action="store_true", help="Skip Trifecta derivative plugin rebuilding")
    
    args = parser.parse_args()
    
    print("🚀 Pipulate Master Release Orchestrator")
    print("=" * 50)
    
    current_version = get_current_version()
    print(f"📋 Current version: {current_version}")
    
    # Early validation of git configuration
    if not validate_git_remotes():
        print("\n❌ Git remote validation failed. Please fix git configuration before proceeding.")
        sys.exit(1)
    
    # === RELEASE PIPELINE PHASE 1: PREPARATION ===
    print("\n🔧 === RELEASE PIPELINE: PREPARATION PHASE ===")
    
    # Step 1: Version Synchronization
    if not args.skip_version_sync:
        version_sync_success = run_version_sync()
    else:
        print("\n⏭️  Skipping version synchronization (--skip-version-sync)")
        version_sync_success = True
    
    # Step 2: Documentation Synchronization  
    if not args.skip_docs_sync:
        docs_sync_success, ascii_art_stats = run_ascii_art_sync()
        if ascii_art_stats:
            display_ascii_art_stats(ascii_art_stats)
    else:
        print("\n⏭️  Skipping documentation synchronization (--skip-docs-sync)")
        docs_sync_success = True
        ascii_art_stats = None
    
    # Step 3: Install.sh Synchronization
    if not args.skip_install_sh_sync:
        install_sh_success = sync_install_sh()
    else:
        print("\n⏭️  Skipping install.sh synchronization (--skip-install-sh-sync)")
        install_sh_success = False
    
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
            print("\n✅ No Trifecta template changes detected - skipping derivative rebuild")
    else:
        print("\n⏭️  Skipping Trifecta derivative rebuilding (--skip-trifecta-rebuild)")
    
    # === RELEASE PIPELINE PHASE 2: GIT OPERATIONS ===
    print("\n📝 === RELEASE PIPELINE: GIT OPERATIONS PHASE ===")
    
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
            print("\n🤖 Generating AI commit message...")
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
        print(f"\n📝 Commit message: {commit_message}")
        run_command(['git', 'commit', '-am', commit_message])
        
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
                # Upstream exists, normal push
                run_command(['git', 'push'])
                print("✅ Pushed changes to remote repository.")
                
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
        print("\n📦 === RELEASE PIPELINE: PYPI PUBLISHING PHASE ===")
        print(f"🏗️  Building and Publishing version {current_version} to PyPI...")
        print("🧹 Cleaning old build artifacts...")
        run_command("rm -rf dist/ build/ *.egg-info", shell=True)
        print("🛠️ Building package...")
        run_command([".venv/bin/python", '-m', 'build'])
        print("📦 Publishing to PyPI...")
        run_command([".venv/bin/python", '-m', 'twine', 'upload', 'dist/*'])
        print(f"\n🎉 Successfully published version {current_version} to PyPI! 🎉")
        print(f"📍 View at: https://pypi.org/project/pipulate/{current_version}/")
        published_to_pypi = True
    
    # === BEAUTIFUL SUMMARY DISPLAY ===
    print("\n" + "=" * 50)
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
    print("\n🔄 Triggering server restart for immediate Chip interaction...")
    server_py_path = PIPULATE_ROOT / "server.py"
    if server_py_path.exists():
        # Touch the server.py file to trigger watchdog restart
        server_py_path.touch()
        print("✅ Server restart triggered - you can now chat with Chip about this update!")
    else:
        print("⚠️  server.py not found, manual restart may be needed")

if __name__ == "__main__":
    main()
