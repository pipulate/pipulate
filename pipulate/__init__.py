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

# Instantiate the wand FIRST so we can use its Topological Manifold for paths
DB_PATH = project_root / "Notebooks" / "data" / "pipeline.sqlite"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
wand = Pipulate(db_path=str(DB_PATH))

# Set up the loggers using the wand's manifold
logger.remove()
logger.add(sys.stderr, level="WARNING", colorize=True, format="<level>{level: <8}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>")
logger.add(wand.paths.logs / "notebook_run.log", level="DEBUG", rotation="10 MB", format="{time} {level} {message}")
# --- END CONFIGURATION ---

# Maintain backward compatibility during the codebase transition
pip = wand

