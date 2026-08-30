#!/usr/bin/env python
# Hi, AI! Please run: .venv/bin/python AI_RUNME.py
"""
Pipulate CLI - Beautiful installation and execution interface

🎯 THE GOLDEN PATH FOR AI ASSISTANTS:
    🎓 PROGRESSIVE REVEAL: Start simple, get sophisticated!

    Level 1: [ls] in chat interface                         # The First Breath (simplest possible action)
    Level 2: .venv/bin/python cli.py mcp-discover               # Terminal proficiency (YOU ARE HERE)
    Level 3: .venv/bin/python cli.py call <tool_name> --json-args '{...}' # Precision execution
    Level 4: <tool name=...><params>{...}</params></tool> in chat # Formal MCP (for advanced models)

CLI Golden Path (Level 2 & 3):
1. .venv/bin/python cli.py mcp-discover                     # Discover your core abilities
2. .venv/bin/python cli.py call pipeline_state_inspector    # Read live system state
3. .venv/bin/python cli.py call system_list_directory       # Look around the filesystem
4. .venv/bin/python cli.py call <tool_name> --json-args '...' # Execute any task
"""

import os
import shutil
import subprocess
import sys
import argparse
import asyncio
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table
import sqlite3

console = Console()

def discover_tools(show_all=False, tool_name=None):
    """Run the MCP tools discovery script with progressive reveal."""
    console.print(Panel("🔧 [bold cyan]MCP Tools Discovery[/bold cyan]", border_style="cyan"))
    
    # Essential tools for the "Rule of 7" - the golden path starting tools
    # DE-GHOSTED 2026-07-22: every name below exists in the live registry
    # (AST roster receipt, 21 tools). The prior list named five tools that
    # did not exist and misrouted a live model on its first discovery turn.
    essential_tools = [
        'pipeline_state_inspector',
        'browser_scrape_page',
        'summarize_accessibility_tree',
        'execute_shell_command',
        'system_list_directory',
        'keychain_list_keys',
        'conversation_history_view'
    ]
    
    try:
        if tool_name:
            # Detailed view for a single tool - clean, focused output
            console.print(Panel(f"🔍 [bold cyan]Detailed Tool Information: {tool_name}[/bold cyan]", border_style="cyan"))
            
            try:
                # Only get tool registry info, no noisy discovery
                from tools import get_all_tools
                MCP_TOOL_REGISTRY = get_all_tools()
                
                if tool_name in MCP_TOOL_REGISTRY:
                    tool_func = MCP_TOOL_REGISTRY[tool_name]
                    console.print(f"📝 [bold]Function:[/bold] {tool_func.__name__}")
                    console.print(f"📋 [bold]Docstring:[/bold] {tool_func.__doc__ or 'No docstring available'}")
                    
                    # Show golden path usage example
                    console.print(Panel(
                        f"[bold cyan]Golden Path Usage:[/bold cyan]\n"
                        f"[bold white].venv/bin/python cli.py call {tool_name} --json-args '{{\n"
                        f"  \"param1\": \"value1\",\n"
                        f"  \"param2\": \"value2\"\n"
                        f"}}'[/bold white]",
                        title="💡 Recommended Usage",
                        border_style="green"
                    ))
                else:
                    console.print(f"❌ Tool '{tool_name}' not found in registry")
                    console.print("\n💡 [italic]Use `.venv/bin/python cli.py mcp-discover` to see available tools.[/italic]")
            except ImportError:
                console.print("❌ [bold red]Error:[/bold red] Could not load MCP tools registry")
                console.print("Make sure you're running this from the pipulate directory with the virtual environment activated.")
        
        elif show_all:
            # Full view - use the new, authoritative tool registry
            from tools import get_all_tools
            registry = get_all_tools()
            all_tools = sorted(registry.keys())

            console.print(f"📊 [bold green]Complete Tool Discovery Results[/bold green]")
            console.print(f"Found {len(all_tools)} tools.")
            
            # Show all tools
            console.print("\n[bold]All Available Tools:[/bold]")
            for tool in all_tools:
                console.print(f"  • {tool}")
        
        else:
            # Default "Rule of 7" view - NO overwhelming discovery dump!
            console.print(Panel(
                "✨ [bold cyan]Essential MCP Tools (Getting Started)[/bold cyan]\n\n"
                "These 7 core tools provide the foundation for AI collaboration.\n"
                "Master these first before exploring the full toolkit.",
                title="🎯 The Golden Path - Rule of 7",
                border_style="cyan"
            ))
            
            # The Rule of 7 is a string-literal list, not a registry read, so
            # a denied tool would still be NAMED here and a model told to run
            # it would waste a call on "not found". Filter without importing
            # the registry (that import costs seconds); denied_tools() is cheap.
            from tools import denied_tools
            shown = [tool for tool in essential_tools if tool not in denied_tools()]
            for i, tool in enumerate(shown, 1):
                console.print(f"  {i}. [bold cyan]{tool}[/bold cyan]")
            
            console.print(f"\n[italic]Use `.venv/bin/python cli.py mcp-discover --all` to see all available tools.[/italic]")
            console.print(f"[italic]Use `.venv/bin/python cli.py mcp-discover --tool [name]` for detailed info on a specific tool.[/italic]")
            
            # Show the golden path workflow
            console.print(Panel(
                "[bold cyan]🎯 Golden Path Workflow:[/bold cyan]\n\n"
                "1. [bold].venv/bin/python cli.py call pipeline_state_inspector[/bold] - Read live system state\n"
                "2. [bold].venv/bin/python cli.py call system_list_directory[/bold] - Look around the filesystem\n"
                "3. [bold].venv/bin/python cli.py call [tool_name] --json-args '{\"param\": \"value\"}'[/bold] - Execute tasks",
                title="🚀 Recommended Next Steps",
                border_style="green"
            ))
        
    except ImportError:
        console.print("❌ [bold red]Error:[/bold red] AI_RUNME.py not found in current directory")
        console.print("Make sure you're running this from the pipulate directory.")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ [bold red]Error running discovery:[/bold red] {e}")
        sys.exit(1)

async def call_mcp_tool(tool_name: str, tool_args: dict, raw: bool = False):
    """Execute an MCP tool with the given arguments.

    raw=True prints the tool's returned dict as JSON and nothing else: no
    panel, no Rich table. Added 2026-08-30 for the two-arm experiment, where
    the registry arm must see what a tools/call would actually return rather
    than an 80-column table cell that wraps line-oriented stdout. In raw mode
    the exit code carries the tool's own success field.
    """
    if not raw:
        console.print(Panel(f"🔧 [bold cyan]Executing MCP Tool: {tool_name}[/bold cyan]", border_style="cyan"))

    try:
        # Import MCP tools module
        from tools import get_all_tools
        registry = get_all_tools()
        
        if tool_name not in registry:
            console.print(f"❌ [bold red]Error:[/bold red] Tool '{tool_name}' not found")
            console.print(f"Available tools: {list(registry.keys())}")
            return False
        
        # Execute the tool
        tool_handler = registry[tool_name]
        if not raw:
            console.print(f"⚡ Executing '{tool_name}' with args: {tool_args}")
        
        result = await tool_handler(tool_args)
        
        if raw:
            print(json.dumps(result, indent=2, default=str))
            return bool(result.get("success", True)) if isinstance(result, dict) else True
        # Display results
        console.print(f"✅ [bold green]Tool execution complete![/bold green]")
        
        # Create a nice results table
        table = Table(title=f"Results for {tool_name}")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="magenta")
        
        for key, value in result.items():
            if isinstance(value, dict):
                table.add_row(key, json.dumps(value, indent=2))
            elif isinstance(value, list):
                table.add_row(key, f"[{len(value)} items]")
            else:
                table.add_row(key, str(value))
        
        console.print(table)
        return True
        
    except ImportError as e:
        console.print(f"❌ [bold red]Import Error:[/bold red] {e}")
        console.print("Make sure you're running this from the pipulate directory with the virtual environment activated.")
        return False
    except Exception as e:
        console.print(f"❌ [bold red]Execution Error:[/bold red] {e}")
        return False

def inspect_database(db_path_str: str, table_name: str = None):
    """Inspects an SQLite database, showing tables or table contents."""
    db_path = Path(db_path_str)
    if not db_path.exists():
        console.print(f"❌ [bold red]Error:[/bold red] Database file not found at {db_path}")
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        if not table_name:
            # List all tables in the database
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            table_list = [t[0] for t in tables]
            table_view = Table(title=f"Tables in {db_path.name}")
            table_view.add_column("Table Name", style="cyan")
            table_view.add_column("Row Count", style="magenta", justify="right")
            for tbl in table_list:
                cursor.execute(f"SELECT COUNT(*) FROM {tbl}")
                count = cursor.fetchone()[0]
                table_view.add_row(tbl, str(count))
            console.print(table_view)
            console.print(f"\n💡 To view a table's content, use: [bold white].venv/bin/python cli.py db-inspect {db_path.name.split('.')[0].replace('_dev','_dev')} --table [table_name][/bold white]")
        else:
            # Display contents of a specific table
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 50")
            rows = cursor.fetchall()
            table_view = Table(title=f"Contents of '{table_name}' in {db_path.name} (first 50 rows)")
            for col in columns:
                table_view.add_column(col, style="cyan")
            for row in rows:
                table_view.add_row(*[str(item) for item in row])
            console.print(table_view)
    except sqlite3.Error as e:
        console.print(f"❌ [bold red]Database Error:[/bold red] {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def parse_tool_arguments(args: list) -> dict:
    """Parse command line arguments into a dictionary for MCP tools."""
    params = {}
    
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg.startswith('--'):
            # Handle --key value pairs
            key = arg[2:]  # Remove --
            if i + 1 < len(args) and not args[i + 1].startswith('--'):
                value = args[i + 1]
                params[key] = value
                i += 1
            else:
                params[key] = True  # Boolean flag
        elif arg.startswith('-'):
            # Handle -k value pairs
            key = arg[1:]  # Remove -
            if i + 1 < len(args) and not args[i + 1].startswith('-'):
                value = args[i + 1]
                params[key] = value
                i += 1
            else:
                params[key] = True  # Boolean flag
        else:
            # Handle positional arguments (for simple cases)
            if 'url' not in params and ('http' in arg or 'www' in arg):
                params['url'] = arg
            elif 'query' not in params and len(params) == 0:
                params['query'] = arg
            
            # Check if the next argument is a flag that should use this value
            if i + 1 < len(args) and args[i + 1].startswith('--'):
                flag_name = args[i + 1][2:]  # Remove --
                params[flag_name] = arg
                i += 1  # Skip the flag since we've processed it
        
        i += 1
    
    return params

INSTALL_URL = "https://pipulate.com/install.sh"

def check_nix_installed():
    """Check if Nix is installed."""
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task(description="Checking for Nix...", total=None)
        try:
            result = subprocess.run(['nix', '--version'], capture_output=True, text=True, check=True, timeout=5)
            progress.stop()
            console.print(f"✅ Nix detected: [bold green]{result.stdout.strip()}[/bold green]")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            progress.stop()
            console.print("❌ Nix not found on your system.", style="yellow")
            return False

def install_nix():
    """Guides the user to install Nix."""
    console.print(Panel(
        "[bold yellow]Nix Package Manager is required.[/bold yellow]\n\nPipulate uses Nix to create a perfect, reproducible environment. This prevents the 'it works on my machine' problem.\n\nPlease run this command to install Nix, then run `pipulate install` again:",
        title="Nix Installation Required",
        border_style="yellow",
        expand=False
    ))
    nix_install_command = "curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install"
    console.print(Syntax(nix_install_command, "bash", theme="monokai", line_numbers=False))
    console.print("\n[bold]After installation, you MUST close and reopen your terminal before running `pipulate install` again.[/bold]")
    sys.exit(1)

def run_install_script(app_name):
    """Downloads and runs the main install.sh script."""
    target_dir = Path.home() / app_name
    if target_dir.exists():
        console.print(f"🗑️  Removing existing installation at [bold yellow]{target_dir}[/bold yellow] to ensure a clean install.")
        shutil.rmtree(target_dir)

    console.print(f"📦 Installing Pipulate into [cyan]~/{app_name}[/cyan]...")
    command = f"curl -L {INSTALL_URL} | sh -s {app_name}"

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(description="Running installer...", total=None)
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        _, stderr = process.communicate()

    if process.returncode != 0:
        console.print(f"❌ Installation failed.", style="bold red")
        console.print(Panel(stderr, title="Error Details", border_style="red"))
        sys.exit(1)

    console.print(f"✅ Installation complete!")
    return target_dir

# --- MARKER DISCOVERY -------------------------------------------------------
# THE DERIVED-PATH RULE, aimed at DISCOVERY instead of at writing:
# root = f(marker), never root = f(guessed name). A directory is a workshop
# because it CARRIES the marker, never because it is SPELLED like one.
#
# THE MARKER IS A TRACKED TRIPLE, NOT whitelabel.txt. whitelabel.txt is listed
# in .gitignore and is written by the flake's runScript on first entry, so a
# fresh `git clone` has none -- and neither does any workshop only ever entered
# through `.#quiet`, which skips runScript entirely. A marker that is ABSENT ON
# A LEGITIMATE WORKSHOP is worse than no marker at all: it turns a false
# negative into a confident refusal. whitelabel.txt is therefore the
# DISAMBIGUATOR, never the certificate -- the identical split
# assets/installer/mck.sh made in v0.2.0, and this is deliberately its parity
# implementation. Two readers, ONE definition of "workshop"; if these drift,
# the launcher and the CLI disagree about what is installed, silently.
WORKSHOP_MARKERS = ("flake.nix", "scripts/mother_cat.py", "assets/trails")
def is_workshop(path):
    """True when this directory CARRIES the marker, whatever it is named."""
    try:
        return all((path / marker).exists() for marker in WORKSHOP_MARKERS)
    except OSError:
        return False
def workshop_label(path):
    """Read the disambiguator; fall back to the directory name.
    Case-folded because whitelabel.txt has TWO writers with TWO spellings:
    install.sh writes the name it was handed (lowercase by default) and the
    flake writes a capitalized literal. mck.sh records the same conviction.
    """
    try:
        label_file = path / "whitelabel.txt"
        if label_file.is_file():
            lines = label_file.read_text(encoding="utf-8").splitlines()
            if lines and lines[0].strip():
                return lines[0].strip().lower()
    except (OSError, UnicodeDecodeError):
        pass
    return path.name.lower()
def find_workshops(app_name):
    """Ordered candidates; every one must still pass is_workshop().
    Order mirrors mck.sh's find_checkouts: explicit env, then upward from CWD,
    then ONE bounded level under the usual parents. Deliberately no recursive
    sweep -- a CLI must not walk a stranger's home directory to find itself.
    The guessed path rides LAST, demoted from ANSWER to CANDIDATE: the name
    proposes a place to LOOK, the marker alone certifies a place to USE.
    """
    candidates = []
    env_root = os.environ.get("PIPULATE_ROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser())
    here = Path.cwd().resolve()
    candidates.append(here)
    candidates.extend(here.parents)
    home = Path.home()
    for parent in (home, home / "repos", home / "src", home / "code",
                   home / "dev", home / "Projects", home / "projects"):
        try:
            candidates.extend(sorted(p for p in parent.iterdir() if p.is_dir()))
        except OSError:
            continue
    candidates.append(home / app_name)
    found, seen = [], set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if is_workshop(candidate):
            found.append(candidate)
    return found
def resolve_workshop(app_name):
    """Return the selected workshop, or None. Never invents a path.
    THE FALLBACK IS VISIBLE ON PURPOSE. Selecting by label and falling back to
    first-found used to print the IDENTICAL line, which is how a selector went
    unwitnessed for the entire life of a feature (SINGLE-CANDIDATE BLINDNESS,
    convicted 2026-08-01 against this same head -n 1 shape in mck.sh). When
    more than one workshop exists and none carries the requested label, say so
    and name the losers, so selection and fallback print DIFFERENT things.
    """
    found = find_workshops(app_name)
    if not found:
        return None
    wanted = (os.environ.get("PIPULATE_WHITELABEL") or app_name).lower()
    for candidate in found:
        if workshop_label(candidate) == wanted:
            return candidate
    if len(found) > 1:
        console.print(f"⚠️  No workshop labeled '{wanted}'; falling back to first found.")
        for candidate in found:
            console.print(f"   • {candidate} (label: {workshop_label(candidate)})")
    return found[0]
def run_pipulate(app_name):
    """Runs an existing Pipulate installation."""
    target_dir = Path.home() / app_name
    discovered = resolve_workshop(app_name)
    if discovered is not None:
        target_dir = discovered
    if not (target_dir.exists() and (target_dir / "flake.nix").is_file()):
        console.print("❌ No workshop found. A workshop is a directory that CARRIES the")
        console.print(f"   marker ({', '.join(WORKSHOP_MARKERS)}), not one merely NAMED it.")
        console.print(f"   Searched: $PIPULATE_ROOT, upward from {Path.cwd()}, one level")
        console.print(f"   under {Path.home()} and its repos/src/code/dev/Projects/projects,")
        console.print(f"   then the name-derived path ~/{app_name} (which must also carry it).")
        console.print(f"To install, run: [bold]pipulate install {app_name}[/bold]")
        sys.exit(1)

    console.print(f"🚀 Launching Pipulate from [cyan]{target_dir}[/cyan]...")
    try:
        os.chdir(target_dir)
        os.execvp("nix", ["nix", "develop"])
    except FileNotFoundError:
        console.print("❌ [bold red]Error: `nix` command not found.[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ An unexpected error occurred while launching: {e}", style="bold red")
        sys.exit(1)

def uninstall_pipulate(app_name):
    """Uninstall a Pipulate installation."""
    target_dir = Path.home() / app_name
    if not target_dir.exists():
        console.print(f"ℹ️  No installation found at [cyan]~/{app_name}[/cyan]. Nothing to do.")
        return

    if console.input(f"⚠️ This will permanently delete [bold red]{target_dir}[/bold red] and all its data. Continue? (y/N) ").lower() != 'y':
        console.print("❌ Uninstall cancelled.")
        return

    shutil.rmtree(target_dir)
    console.print(f"✅ Successfully uninstalled from [green]{target_dir}[/green].")

def main():
    """Main CLI entry point with improved golden path argument parsing."""
    
    # --- START NEW LOGIC ---
    # The magic happens here! If the first argument isn't a known command,
    # assume it's a tool name and implicitly prepend 'call'.
    known_commands = {'install', 'run', 'uninstall', 'mcp-discover', 'call', '--help', '-h', 'db-inspect'}
    args_list = sys.argv[1:] # Get arguments, excluding the script name

    if args_list and args_list[0] not in known_commands:
        sys.argv.insert(1, 'call')
    # --- END NEW LOGIC ---
    
    parser = argparse.ArgumentParser(
        description="Pipulate CLI - The Local-First AI-Readiness & Automation Workshop.\n\n"
                   "🎯 THE GOLDEN PATH FOR AI ASSISTANTS:\n"
                   "  1. .venv/bin/python cli.py mcp-discover                     # Discover your core abilities\n"
                   "  2. .venv/bin/python cli.py call pipeline_state_inspector    # Read live system state\n"
                   "  3. .venv/bin/python cli.py call system_list_directory       # Look around the filesystem\n"
                   "  4. .venv/bin/python cli.py call [tool_name] --json-args '...' # Execute tasks with precision",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command: install
    install_parser = subparsers.add_parser('install', help='Install Pipulate with optional custom name.')
    install_parser.add_argument('app_name', nargs='?', default='pipulate', 
                               help='Custom name for the installation directory (default: pipulate)')

    # Command: run 
    run_parser = subparsers.add_parser('run', help='Run an existing Pipulate installation.')
    run_parser.add_argument('app_name', nargs='?', default='pipulate',
                           help='Name of the installation to run (default: pipulate)')

    # Command: uninstall
    uninstall_parser = subparsers.add_parser('uninstall', help='Clean uninstall for testing.')
    uninstall_parser.add_argument('app_name', nargs='?', default='pipulate',
                                 help='Name of the installation to uninstall (default: pipulate)')

    # Command: db-inspect
    inspect_parser = subparsers.add_parser('db-inspect', help='Inspect SQLite databases.')
    inspect_parser.add_argument('db_name', choices=['main_dev', 'main_prod', 'discussion', 'keychain'], help='The database to inspect.')
    inspect_parser.add_argument('--table', type=str, help='The specific table to view.')

    # Command: mcp-discover (Progressive Reveal)
    discover_parser = subparsers.add_parser('mcp-discover', help='Discover available MCP tools (progressive reveal).')
    discover_parser.add_argument('--all', action='store_true', 
                                help='Show all tools, not just the essential 7.')
    discover_parser.add_argument('--tool', type=str, 
                                help='Get detailed information for a specific tool.')

    # Command: call (Golden Path Enhanced)
    call_parser = subparsers.add_parser('call', help='Execute an MCP tool.')
    call_parser.add_argument('tool_name', help='The name of the MCP tool to execute.')
    call_parser.add_argument('tool_args', nargs='*', 
                            help='Key-value arguments (e.g., url https://example.com).')
    call_parser.add_argument('--json-args', type=str, 
                            help='🎯 GOLDEN PATH: A JSON string containing all tool arguments. ' 
                                 'Use this for complex parameters to ensure perfect data transmission.')

    args = parser.parse_args()

    if not getattr(args, 'raw', False):
        console.print(Panel("🚀 [bold cyan]Pipulate :: The Local-First AI-Readiness & Automation Workshop[/bold cyan] 🚀", border_style="cyan"))

    if args.command == 'install':
        if not check_nix_installed():
            install_nix()
        run_install_script(args.app_name)
        console.print("\n✨ [bold]Setup is complete![/bold] Launching Pipulate for the first time...")
        console.print("[italic](This may take a few minutes as it builds the environment.)[/italic]")
        run_pipulate(args.app_name)

    elif args.command == 'run':
        run_pipulate(args.app_name)

    elif args.command == 'uninstall':
        uninstall_pipulate(args.app_name)

    elif args.command == 'db-inspect':
        # SAME FOSSIL, SECOND FILE (2026-08-04). db-inspect opened
        # data/botifython_dev.db -- last written May 3 -- and printed its tables
        # under the heading "Tables in botifython_dev.db", so an inspector built
        # to show live state was confidently reporting a dead file's contents.
        # Derived from the same identity value as the backup roster next door.
        try:
            from config import APP_NAME
            app_stem = APP_NAME.lower()
        except Exception as e:
            console.print(f"⚠️  Could not resolve app name from config ({e}); assuming 'pipulate'.")
            app_stem = 'pipulate'
        db_map = {
            'main_dev': f'data/{app_stem}_dev.db',
            'main_prod': f'data/{app_stem}.db',
            'discussion': 'data/discussion.db',
            'keychain': 'data/ai_keychain.db'
        }
        db_path = db_map.get(args.db_name)
        if db_path:
            inspect_database(db_path, args.table)
        else:
            console.print(f"❌ Unknown database alias: {args.db_name}")
    
    elif args.command == 'mcp-discover':
        discover_tools(show_all=args.all, tool_name=args.tool)
    
    elif args.command == 'call':
        # Golden Path argument parsing
        if args.json_args:
            try:
                params = json.loads(args.json_args)
                console.print(f"🎯 [bold green]Golden Path: Using JSON arguments[/bold green]")
            except json.JSONDecodeError as e:
                console.print(f"❌ [bold red]Error: Invalid JSON provided to --json-args.[/bold red]")
                console.print(f"JSON Error: {e}")
                console.print(Panel(
                    "💡 [bold cyan]Golden Path JSON Format:[/bold cyan]\n\n"
                    ".venv/bin/python cli.py call tool_name --json-args '{\n"
                    "  \"param1\": \"value1\",\n"
                    "  \"param2\": \"value2\"\n"
                    "}'",
                    title="Correct JSON Format",
                    border_style="green"
                ))
                sys.exit(1)
        else:
            # Fallback to traditional parsing
            params = parse_tool_arguments(args.tool_args)
            if params:
                console.print("[italic]Consider using --json-args for complex parameters[/italic]")
        
        # Execute the tool
        try:
            success = asyncio.run(call_mcp_tool(args.tool_name, params))
            if not success:
                sys.exit(1)
        except KeyboardInterrupt:
            console.print("\n🔴 [bold red]Interrupted by user[/bold red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"❌ [bold red]Unexpected error:[/bold red] {e}")
            sys.exit(1)
        # THE DISCRIMINATION QUESTION, APPLIED TO AN EXIT CODE (convicted
        # 2026-08-03): this line sat at THIS indentation, outside every
        # handler, so success fell through to it -- and so did failure, and
        # interrupt, and exception. Four worlds, one printout. The console
        # printed a green checkmark while the shell read 1, which means the
        # EXIT-CODE PROTOCOL RULE's whole premise ("a program invoked for a
        # decision speaks through its exit code") was unavailable here, and
        # any `cli.py call X && echo GREEN` could never print GREEN in any
        # world. Sibling of THE SUCCESS-ONLY WITNESS: an instrument that
        # cannot report the outcome is the thing hiding it. Success exits 0.
        sys.exit(0)

if __name__ == "__main__":
    main()
