# /home/mike/repos/pipulate/pipulate/__init__.py

import os
import sys
from pathlib import Path
from loguru import logger
import warnings
import logging

# --- GLOBAL ENVIRONMENT SETUP ---
warnings.filterwarnings("ignore", category=UserWarning)
os.environ['ABSL_MIN_LOG_LEVEL'] = '2'
# -----------------------------

from .core import Pipulate

def find_project_root(start_path):
    """Walks up from a starting path to find the project root (marked by 'flake.nix')."""
    current_path = Path(start_path).resolve()
    while current_path != current_path.parent:
        if (current_path / 'flake.nix').exists():
            return current_path
        current_path = current_path.parent
    return None

# --- PATH & LOGGING CONFIGURATION ---
project_root = find_project_root(os.getcwd()) or Path.cwd()

# ... after project_root is defined ...
if project_root:
    notebooks_path = str(project_root / "Notebooks")
    if notebooks_path not in sys.path:
        sys.path.append(notebooks_path)
        
    # 🪄 THE FUSION DANCE: Merge core imports with user imports
    import imports
    notebook_imports_path = project_root / "Notebooks" / "imports"
    if notebook_imports_path.exists() and str(notebook_imports_path) not in imports.__path__:
        imports.__path__.append(str(notebook_imports_path))

# --- PATH & LOGGING CONFIGURATION ---
# 1. Silence loguru's default handler and set up the quiet console logger FIRST
logger.remove()
logger.add(sys.stderr, level="WARNING", colorize=True, format="<level>{level: <8}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>")

# 2. Instantiate the wand so we can use its Topological Manifold for paths
DB_PATH = project_root / "Notebooks" / "data" / "pipeline.sqlite"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
wand = Pipulate(db_path=str(DB_PATH))

# 3. Add the file logger using the wand's manifold to capture everything else
logger.add(wand.paths.logs / "notebook_run.log", level="DEBUG", rotation="10 MB", format="{time} {level} {message}")
# --- END CONFIGURATION ---

# 4. Auto-Configure JupyterLab Table of Contents
try:
    jupyter_settings_dir = Path.home() / ".jupyter" / "lab" / "user-settings" / "@jupyterlab" / "toc-extension"
    jupyter_settings_dir.mkdir(parents=True, exist_ok=True)
    toc_config_path = jupyter_settings_dir / "plugin.jupyterlab-settings"
    
    # Only write if it doesn't exist to respect user overrides later
    if not toc_config_path.exists():
        toc_config = {
            "title": "Table of Contents",
            "numberingH1": False,
            "collapseTree": True
        }
        with open(toc_config_path, "w", encoding="utf-8") as f:
            import json
            json.dump(toc_config, f, indent=4)
        logger.debug("Successfully auto-configured JupyterLab Table of Contents.")
except Exception as e:
    logger.warning(f"Failed to auto-configure JupyterLab TOC: {e}")

# Maintain backward compatibility during the codebase transition
pip = wand
