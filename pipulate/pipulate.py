# START: pipulate_factory_content
import os
import sys
from pathlib import Path
from loguru import logger
import warnings
from .core import Pipulate

# 🎯 NOTEBOOK LOGGING: Configure logger for a cleaner Jupyter experience.
logger.remove()
logger.add(sys.stderr, level="WARNING")

# Suppress the specific UserWarning from pkg_resources in selenium-wire
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="pkg_resources is deprecated as an API.*"
)

def _find_project_root(start_path):
    """Find the project root by looking for the flake.nix file."""
    current_path = Path(start_path).resolve()
    while current_path != current_path.parent:
        if (current_path / 'flake.nix').exists():
            return current_path
        current_path = current_path.parent
    return None

def _get_db_path():
    """
    Determines the correct database path for standalone (notebook) usage.
    - If run from within the dev repo, it uses the local `data/` directory.
    - If run as an installed package, it uses a stable, hidden `~/.pipulate/` directory.
    """
    project_root = _find_project_root(os.getcwd())

    if project_root:
        # We are in the dev environment. Use the existing logic.
        app_name_file = project_root / 'whitelabel.txt'
        if app_name_file.exists():
            app_name = app_name_file.read_text().strip().lower()
        else:
            # Fallback to directory name if whitelabel.txt doesn't exist
            app_name = project_root.name.lower()
        # Always use the dev database for notebook work inside the repo
        return project_root / f'data/{app_name}_dev.db'
    else:
        # We are likely in an installed package environment (e.g., via pip).
        # Create a stable, user-specific location for the database.
        home_dir = Path.home()
        pipulate_dir = home_dir / '.pipulate'
        pipulate_dir.mkdir(exist_ok=True)
        return pipulate_dir / 'pipulate.db'

# The "factory" instantiation. This code runs when this module is imported.
# It creates a single, pre-configured instance of the Pipulate class.
# This is the magic `wand` object for notebooks.
wand = Pipulate(db_path=str(db_path))

# Maintain backward compatibility during the codebase transition
pip = wand
# END: pipulate_factory_content
