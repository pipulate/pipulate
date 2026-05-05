"""
Pipulate: Local-First AI SEO Software & Digital Workshop

Your data. Your AI. Your machine. Your control.

This package provides the `pipulate` command for discovering and installing
the full Pipulate environment via PyPI, while the actual application runs
in a Nix-managed environment for complete reproducibility.

Usage:
    pip install pipulate
    pipulate
"""

__version__ = "1.63"
__version_description__ = "Onboarding Configurates"
__email__ = "pipulate@gmail.com"
__description__ = "A Notebook-inspired Hand-cranked Agentic Framework" 

# Pipulate - Local-First AI SEO Software
# Copyright (C) 2026 Mike Levin
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# SINGLE SOURCE OF TRUTH FOR VERSION AND DESCRIPTION
# This version number and description are used across all components:
# - pyproject.toml (synced via version_sync.py)
# - flake.nix (reads this file directly at build time)
# - install.sh (synced via version_sync.py)
# - server.py startup banners (reads this file directly)
# Update these values and run: python version_sync.py
