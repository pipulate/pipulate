"""
Tools package for Pipulate - Focused MCP tool modules

This package contains extracted MCP tools organized by domain for token optimization.
"""

# --- NEW: Proof-of-concept for automatic tool registration ---
AUTO_REGISTERED_TOOLS = {}

def auto_tool(func):
    """Decorator to prove that automatic registration is possible."""
    AUTO_REGISTERED_TOOLS[func.__name__] = func
    return func

# --- NEW: Simple alias registration for bracket commands ---
ALIAS_REGISTRY = {}

def alias(alias_name):
    """Decorator to map a simple [command] to a tool function."""
    def decorator(func):
        ALIAS_REGISTRY[alias_name] = func.__name__
        return func
    return decorator
# --- END NEW ---
# --- END NEW ---

import os
import importlib

# --- NEW: Automatic tool discovery and registration ---
def get_all_tools():
    """
    Dynamically imports all tool modules in this package and returns the
    dictionary of functions decorated with @auto_tool.
    """
    package_name = __name__
    package_path = os.path.dirname(__file__)

    for module_info in os.scandir(package_path):
        if module_info.is_file() and module_info.name.endswith('.py') and not module_info.name.startswith('__'):
            module_name = module_info.name[:-3]
            try:
                importlib.import_module(f".{module_name}", package=package_name)
            except ImportError as e:
                print(f"Could not import tool module: {module_name} - {e}")

    denied = denied_tools()
    if denied:
        return {name: func for name, func in AUTO_REGISTERED_TOOLS.items()
                if name not in denied}
    return AUTO_REGISTERED_TOOLS


def denied_tools():
    """Names withheld from the registry by PIPULATE_TOOL_DENY (comma-separated).

    THE ESCAPE HATCH, NAMED. execute_shell_command is a registry tool, so any
    experiment that pits the registry against the shell has a registry arm that
    can shell out and become the other arm. Withholding is an ENV VAR on
    purpose: the registry itself never changes, the denial is visible in the
    harness command that set it, and an empty variable is exactly today.
    Applied at get_all_tools()'s return because every cli.py path -- call,
    mcp-discover --all, mcp-discover --tool -- reads that one dict.
    """
    raw = os.environ.get("PIPULATE_TOOL_DENY", "")
    return {name.strip() for name in raw.split(",") if name.strip()}
# --- END NEW ---

__version__ = "1.0.0"

# Import shared constants to eliminate duplication
try:
    from .botify_tools import CORE_BOTIFY_TOOLS
    botify_exports = CORE_BOTIFY_TOOLS + ['get_botify_tools']
except ImportError:
    # Fallback if import fails
    botify_exports = ['get_botify_tools']

__all__ = botify_exports + [
    'execute_complete_session_hijacking',
    'selenium_automation',
    'execute_automation_recipe',
    'execute_mcp_cli_command',
    'conversation_history_view',
    'conversation_history_clear',
    'get_selenium_automation'
] 
