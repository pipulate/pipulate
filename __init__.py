"""
Pipulate: A hand-cranked, local-first AI-readiness software framework — the successor to AI SEO software.

Your data. Your AI. Your machine. Your control.

This package provides the `pipulate` command for discovering and installing
the full Pipulate environment via PyPI, while the actual application runs
in a Nix-managed environment for complete reproducibility.

Usage:
    pip install pipulate
    pipulate
"""

__version__ = "2.00"
__version_description__ = "AI-Readiness Retitle"
__email__ = "pipulate@gmail.com"
__description__ = "AI-readiness for the agentic web — local-first, Nix-reproducible workflows. The successor to AI SEO software."

# Pipulate: A hand-cranked, local-first AI-readiness software framework — the successor to AI SEO software.
# Copyright (C) 2026 Michael Jay Levin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# SINGLE SOURCE OF TRUTH FOR VERSION AND DESCRIPTION
# This version number and description are used across all components:
# - pyproject.toml (synced via version_sync.py)
# - flake.nix (reads this file directly at build time)
# - install.sh (synced via version_sync.py)
# - server.py startup banners (reads this file directly)
# Update these values and (under `nix develop .#quiet` env) run: release
