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

# 1. Configure the data directory
data_dir = project_root / "Notebooks" / "data"
data_dir.mkdir(parents=True, exist_ok=True)
DB_PATH = data_dir / "pipeline.sqlite"

# 2. Configure the log directory
log_dir = project_root / "Notebooks" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

# 3. Set up the loggers
logger.remove()
logger.add(sys.stderr, level="WARNING", colorize=True, format="<level>{level: <8}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>")
logger.add(log_dir / "notebook_run.log", level="DEBUG", rotation="10 MB", format="{time} {level} {message}")
# --- END CONFIGURATION ---

# Create the singleton instance that acts as the central actuator.
wand = Pipulate(db_path=str(DB_PATH))

# Maintain backward compatibility during the codebase transition
pip = wand

