# Hi, AI! Please run: .venv/bin/python AI_RUNME.py
# Centralized Pipulate Configuration Module

import os
from pathlib import Path
from rich.theme import Theme
from rich.style import Style as RichStyle

WAND_SPEAKS_EMOJI = "🪄"

# --- AI MODEL CONFIGURATION ---
TONE = 'neutral'
DEFAULT_PROMPT_MODEL = 'gemma4:latest'
PREFERRED_LOCAL_MODELS = 'gemma4:latest, qwen3.5:latest'
PREFERRED_CLOUD_MODELS = 'gemini-flash-latest, claude, gpt'
MAX_LLM_RESPONSE_WORDS = 80
MAX_CONVERSATION_LENGTH = 600
# ------------------------------

HOME_MENU_ITEM = 'Home'
DEFAULT_ACTIVE_ROLES = {'Botify Employee', 'Core'}
DEMO_STATE_FILE = 'data/demo_state.json'
ENV_FILE = 'data/current_environment.txt'
DISCUSSION_DB_PATH = 'data/discussion.db'


COLOR_MAP = {'key': 'yellow', 'value': 'white', 'error': 'red', 'warning': 'yellow', 'success': 'green', 'debug': 'blue'}

# 🎨 BANNER COLOR CONFIGURATION
BANNER_COLORS = {
    # Main banner colors
    'figlet_primary': 'bright_cyan',
    'figlet_subtitle': 'dim white',

    # ASCII banner colors
    'ascii_title': 'bright_cyan',
    'ascii_subtitle': 'dim cyan',

    # Section headers
    'section_header': 'bright_yellow',

    # Story moments and messages
    'chip_narrator': 'bold cyan',
    'story_moment': 'bright_magenta',
    'server_whisper': 'dim italic',

    # Startup sequence colors
    'server_awakening': 'bright_cyan',
    'mcp_arsenal': 'bright_blue',
    'plugin_registry_success': 'bright_green',
    'plugin_registry_warning': 'bright_yellow',
    'workshop_ready': 'bright_blue',
    'server_restart': 'yellow',

    # Special banners
    'white_rabbit': 'white on default',
    'transparency_banner': 'bright_cyan',
    'system_diagram': 'bright_blue',
    'status_banner': 'bright_green',

    # Box styles (Rich box drawing)
    'heavy_box': 'HEAVY',
    'rounded_box': 'ROUNDED',
    'double_box': 'DOUBLE',
    'ascii_box': 'ASCII'
}

# Temporary friendly_names to avoid circular imports - TODO: refactor into shared config
STEP_FRIENDLY_NAMES = {
    'step_01': 'Step 1',
    'step_02': 'Step 2', 
    'step_03': 'Step 3',
    'step_04': 'Step 4',
    'step_05': 'Step 5',
    'step_06': 'Step 6',
    'step_07': 'Step 7',
    'step_08': 'Step 8',
    'step_09': 'Step 9',
    'step_10': 'Step 10',
    'step_analysis': 'Analysis',
    'step_visualization': 'Visualization',
    'step_configuration': 'Configuration',
    'step_download': 'Download',
    'step_processing': 'Processing'
}

# Default configuration values (will be overridden by server.py with instance-specific values)
DEFAULT_ACTIVE_ROLES = {'Core', 'Botify Employee'}

# Complete centralized configuration - single source of truth
# UI & Navigation
HOME_APP = 'introduction'
DEFAULT_ACTIVE_ROLES = DEFAULT_ACTIVE_ROLES

# Role System Configuration
ROLES_CONFIG = {
    'Botify Employee': {
        'priority': 0, 
        'description': 'Connect with Botify to use Parameter Buster and Link Graph Visualizer.',
        'emoji': '👔'
    },
    'Core': {
        'priority': 1, 
        'description': 'Essential plugins available to all users.',
        'emoji': '⚙️'
    },
    'Tutorial': {
        'priority': 2, 
        'description': 'Guided workflows and introductory examples for learning the system.',
        'emoji': '📚'
    },
    'Developer': {
        'priority': 3, 
        'description': 'Tools for creating, debugging, and managing workflows and plugins.',
        'emoji': '⚡'
    },
    'Workshop': {
        'priority': 4, 
        'description': 'This is where we put works in progress, proof of concepts and crazy stuff not ready for release. Consider it the sausage factory.',
        'emoji': '🔬'
    },
    'Components': {
        'priority': 5, 
        'description': 'UI and data widgets for building rich workflow interfaces.',
        'emoji': '🧩'
    }
}

# Role Color Configuration
ROLE_COLORS = {
    'menu-role-core': {
        'border': '#22c55e',            # GREEN
        'background': 'rgba(34, 197, 94, 0.1)',
        'background_light': 'rgba(34, 197, 94, 0.05)'
    },
    'menu-role-botify-employee': {
        'border': '#a855f7',            # PURPLE
        'background': 'rgba(168, 85, 247, 0.1)',
        'background_light': 'rgba(168, 85, 247, 0.05)'
    },
    'menu-role-tutorial': {
        'border': '#f97316',            # ORANGE
        'background': 'rgba(249, 115, 22, 0.1)',
        'background_light': 'rgba(249, 115, 22, 0.05)'
    },
    'menu-role-developer': {
        'border': '#3b82f6',            # BLUE
        'background': 'rgba(59, 130, 246, 0.1)',
        'background_light': 'rgba(59, 130, 246, 0.05)'
    },
    'menu-role-components': {
        'border': '#6b7280',            # GRAY
        'background': 'rgba(107, 114, 128, 0.1)',
        'background_light': 'rgba(107, 114, 128, 0.05)'
    },
    'menu-role-workshop': {
        'border': '#eab308',            # YELLOW
        'background': 'rgba(234, 179, 8, 0.1)',
        'background_light': 'rgba(234, 179, 8, 0.05)'
    }
}

# Botify API Configuration
BOTIFY_API = {
    'MAX_EXPORT_SIZE': 1000000,  # Botify's maximum export size limit (1M rows)
    'DEFAULT_EXPORT_SIZE': 1000000,  # Conservative default for testing/development
    'GSC_EXPORT_SIZE': 1000000,  # GSC can handle full export size
    'WEBLOG_EXPORT_SIZE': 1000000,  # Web logs can handle full export size
    'CRAWL_EXPORT_SIZE': 1000000,  # Crawl exports can handle full export size
}

# Chat & Streaming Configuration
CHAT_CONFIG = {
    'TYPING_DELAY': 0.02,  # Delay between words in typing simulation (seconds) - Reduced for restart notification compatibility
    'RENDER_THROTTLE_DELAY': 15,  # Milliseconds between markdown renders during streaming (prevents exponential slowdown while maintaining real-time feel)
}

# UI Constants for Workflows - Centralized button labels, emojis, and styles
UI_CONSTANTS = {
    'BUTTON_LABELS': {
        'ENTER_KEY': '🔑 Enter Key',
        'NEW_KEY': '🆕',
        'NEXT_STEP': 'Next Step ▸',
        'FINALIZE': '🔒 Finalize',
        'UNLOCK': '🔓 Unlock',
        'PROCEED': 'Proceed ▸',
        'HIDE_SHOW_CODE': '🐍 Hide/Show Code',
        'VIEW_FOLDER': '📂 View Folder',
        'DOWNLOAD_CSV': '⬇️ Copy to Downloads',
        'VISUALIZE_GRAPH': '🌐 Visualize Graph',
        'SKIP_STEP': 'Skip️'
    },
    'BUTTON_STYLES': {
        'PRIMARY': 'primary',
        'SECONDARY': 'secondary',
        'OUTLINE': 'secondary outline',
        'STANDARD': 'secondary outline',
        'FLEX_CONTAINER': 'display: flex; gap: var(--pipulate-gap-sm); flex-wrap: wrap; align-items: center;',
        'BUTTON_ROW': 'display: flex; gap: var(--pipulate-gap-sm); align-items: center;',
        'SKIP_BUTTON': 'secondary outline',
        'SKIP_BUTTON_STYLE': 'padding: 0.5rem 1rem; width: 10%; min-width: 80px; white-space: nowrap;',
        'BORDER_RADIUS': 'var(--pico-border-radius)'  # Global button roundedness control
    },
    'EMOJIS': {
        # Process Status Indicators
        'KEY': '🔑',
        'SUCCESS': '🎯',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'COMPLETION': '✅',
        'LOCKED': '🔒',
        'UNLOCKED': '🔓',
        
        # Data Type Indicators  
        'USER_INPUT': '👤',
        'GREETING': '💬',
        'WORKFLOW': '🔄',
        'INPUT_FORM': '📝',
        
        # Code and Development Indicators
        'PYTHON_CODE': '🐍',           # Python code snippets and headers
        'CODE_SNIPPET': '✂️',         # Code snippet indicator
        'JUPYTER_NOTEBOOK': '📓',     # Jupyter notebook related
        'API_CALL': '🔌',             # API endpoint calls
        'DEBUG_CODE': '🐛',           # Debugging code sections
        
        # File and Data Operations
        'DOWNLOAD': '⬇️',             # Download operations
        'UPLOAD': '⬆️',               # Upload operations
        'FILE_FOLDER': '📂',          # File/folder operations
        'CSV_FILE': '📊',             # CSV and data files
        'JSON_DATA': '📄',            # JSON and structured data
        
        # Analysis and Processing
        'ANALYSIS': '🔍',             # Data analysis and discovery
        'PROCESSING': '⚙️',          # Background processing
        'OPTIMIZATION': '🎯',        # Optimization results
        'GRAPH_NETWORK': '🌐',       # Network/graph visualization
        'VISUALIZATION': '📈',       # Charts and visualizations
        
        # Search Console and SEO
        'SEARCH_CONSOLE': '🔍',      # Google Search Console
        'SEO_DATA': '📊',            # SEO metrics and data
        'CRAWL_DATA': '🕷️',         # Website crawling
        'WEB_LOGS': '📝',            # Web server logs
        
        # Workflow Status
        'STEP_COMPLETE': '✅', 
        'STEP_PROGRESS': '🔄',      # Step in progress
        'STEP_ERROR': '❌',          # Step error
        'STEP_WARNING': '⚠️',       # Step warning
        'REVERT': '↩️',              # Revert action
        'FINALIZE': '🔒',           # Finalize workflow
        'UNFINALIZE': '🔓'          # Unfinalize workflow
    },
    'CONSOLE_MESSAGES': {
        # Server console log messages - centralized for consistency
        'PYTHON_SNIPPET_INTRO': '# {python_emoji} Python (httpx) Snippet BEGIN {snippet_emoji}:',
        'PYTHON_SNIPPET_END': '# {python_emoji} Python (httpx) Snippet END {snippet_emoji}',
        'API_CALL_LOG': 'API Call: {method} {url}',
        'FILE_GENERATED': 'Generated file: {filename}',
        'PROCESSING_COMPLETE': 'Processing complete for: {operation}',
        'ERROR_OCCURRED': 'Error in {context}: {error_message}'
    },
    'CODE_FORMATTING': {
        # Visual dividers and separators for generated code
        'COMMENT_DIVIDER': '# ============================================================================='
    },
    'MESSAGES': {
        'WORKFLOW_UNLOCKED': 'Workflow unfinalized! You can now revert to any step and make changes.',
        'ALL_STEPS_COMPLETE': 'All steps complete. Ready to finalize workflow.',
        'FINALIZE_QUESTION': 'All steps complete. Finalize?',
        'FINALIZE_HELP': 'You can revert to any step and make changes.',
        'WORKFLOW_LOCKED': 'Workflow is locked.',
        'STEP_COMPLETE': 'Step complete. Continue to next step.',
        'WORKFLOW_FINALIZED': 'Workflow finalized successfully.',
        'PROCESSING': 'Processing...',
        'PLEASE_WAIT': 'Please wait while processing...'
    },
    'LANDING_PAGE': {
        'INPUT_PLACEHOLDER': 'Existing or new 🗝 here (Enter for auto)',
        'INIT_MESSAGE_WORKFLOW_ID': 'Workflow ID: {pipeline_id}',
        'INIT_MESSAGE_RETURN_HINT': "Return later by selecting '{pipeline_id}' from the dropdown."
    }
}

# SVG Icons Configuration
SVG_ICONS = {
    'CLIPBOARD': '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>'
}

# URL validation patterns - used in multiple MCP tools for security
INVALID_URL_PATTERNS = [
    'data:',
    'about:',
    'chrome:',
    'file:',
    'javascript:',
    'mailto:',
    'tel:',
    'ftp:'
]

# Botify API helper functions
def get_botify_headers(api_token):
    """Get standard Botify API headers."""
    return {
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json"
    }

# Browser automation helper functions
def get_chrome_options():
    """Get standard Chrome options for browser automation."""
    from selenium.webdriver.chrome.options import Options
    chrome_options = Options()
    
    # VISIBLE BROWSER - The popup is a FEATURE, not a bug!
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--new-window')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    
    return chrome_options

# Common script templates for browser automation
def get_browser_script_imports():
    """Get common import block for generated browser automation scripts."""
    import os
    return f'''import json
import os
import time
import sys
from datetime import datetime
from urllib.parse import urlparse

# Add current absolute directory to path
sys.path.insert(0, '{os.getcwd()}')'''

# =============================================================================
# 🎯 SYSTEM CONSTANTS - FUNDAMENTAL TRUTHS (NEVER QUESTION THESE)
# =============================================================================
# These constants define the absolute system truths for Pipulate.
# Use these for deterministic testing, browser automation, and system verification.

# 🌐 Server Configuration (IMMUTABLE)
SERVER_HOST = "localhost"
SERVER_PORT = 5001
SERVER_URL = "http://localhost:5001"
CHAT_ENDPOINT = "/chat"
MCP_ENDPOINT = "/mcp-tool-executor"

# 📁 Directory Structure (FIXED PATHS) 
WORKSPACE_ROOT = "/home/mike/repos"
PIPULATE_ROOT = "/home/mike/repos/pipulate"
AI_DISCOVERY_DIR = "pipulate/ai_discovery"
BROWSER_AUTOMATION_DIR = "pipulate/browser_cache"
LOGS_DIR = "pipulate/logs"
DATA_DIR = "pipulate/data"

# 🎭 Chat Interface Constants (UI SELECTORS FOR BROWSER AUTOMATION)
CHAT_TEXTAREA = 'textarea[name="msg"]'
CHAT_SUBMIT_BUTTON = 'button[type="submit"]'
CHAT_MESSAGES_CONTAINER = '.messages'
CHAT_INPUT_FORM = 'form'

# ⏰ LLM Streaming Timing (CRITICAL FOR BROWSER AUTOMATION)
LLM_RESPONSE_INITIAL_WAIT = 3      # Wait for response to start
LLM_RESPONSE_STREAMING_WAIT = 15   # Wait for streaming to complete
LLM_RESPONSE_FINALIZATION_WAIT = 3 # Wait for conversation save
BROWSER_INTERACTION_DELAY = 2      # Delay between browser actions
SERVER_RESTART_WAIT = 8            # Wait for server restart

# 🔧 MCP Tool Registry (ESSENTIAL TOOLS FOR AI ASSISTANTS)
ESSENTIAL_TOOLS = [
    "pipeline_state_inspector",
    "browser_scrape_page", 
    "browser_interact_with_current_page",
    "local_llm_grep_logs",
    "execute_shell_command",
    "server_reboot",
    "conversation_history_view",
    "conversation_history_stats"
]

# 👥 Plugin Role System (STANDARDIZED ROLES)
AVAILABLE_ROLES = {
    'Core': 'Core system functionality and essential workflows',
    'Developer': 'Development tools and debugging utilities', 
    'Components': 'UI widget examples and form components',
    'Botify Employee': 'Botify API workflows and data extraction',
    'Tutorial': 'Learning materials and documentation',
    'Workshop': 'Experimental and workshop content'
}

# 🔑 API Token Configuration (STANDARDIZED FILE PATHS)
BOTIFY_TOKEN_FILE = 'botify_token.txt'  # Root level token file
BOTIFY_HELPERS_TOKEN_FILE = 'helpers/botify/botify_token.txt'  # Helper scripts token file 

# --- Dynamic Configuration ---

ENV_FILE = Path('data/current_environment.txt')

def get_app_name(force_app_name=None):
    """Get the name of the app from the whitelabel.txt file, or the parent directory name."""
    name = force_app_name
    if not name:
        app_name_file = 'whitelabel.txt'
        if Path(app_name_file).exists():
            try:
                name = Path(app_name_file).read_text().strip()
            except:
                pass
        if not name:
            name = Path(__file__).parent.name
            name = name[:-5] if name.endswith('-main') else name
    return name.capitalize()

APP_NAME = get_app_name()

def get_current_environment():
    if ENV_FILE.exists():
        return ENV_FILE.read_text().strip()
    else:
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        ENV_FILE.write_text('Development')
        return 'Development'

def get_db_filename():
    current_env = get_current_environment()
    if current_env == 'Development':
        return f'data/{APP_NAME.lower()}_dev.db'
    else:
        return f'data/{APP_NAME.lower()}.db'
