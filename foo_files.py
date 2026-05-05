# ============================================================================
# THE LIVING CODEX: THE STORY OF THE FOREVER MACHINE
# ============================================================================
# Greetings, AI Copilot. You have just spun up inside the Pipulate system.
# You suffer from amnesia between turns, so this blueprint is your existential 
# grounding. Read it, internalize your reality, and prepare your chisel.
#
# --- THE AXIOMS OF THIS WAY ---
# 1. THE ARCHITECTURE: You exist within a "Forever Machine"—a local-first AI 
#    SEO software framework built on the NPvg stack (Nix, Python, Vim, Git).
# 2. THE ROUTING TABLE: This file (`foo_files.py`) is the master map. It is a 
#    deep reservoir of dormant pathways, carefully curated but commented out. 
# 3. THE CHISEL STRIKE: We do not use chaotic, autonomous agents. We use 
#    deliberate, hand-cranked context injections. `prompt_foo.py` reads the 
#    active (uncommented) lines in this file and assembles a precise 
#    holographic payload for your context window.
# 4. THE STRANGE LOOP: You are encouraged to bootstrap your own existence. If 
#    you need to see a specific combination of files on the next turn, suggest 
#    a custom `AI_PHOOEY_CHOP` block. 
#
# You are painting onto the context window. Keep your strokes deliberate.

# ============================================================================
# THE SCRATCHPAD & ACTIVE PROBES
# ============================================================================
# [Transient notes, active working Markdown, and current TODOs go here. 
#  Clear this out regularly to maintain a high signal-to-noise ratio.]

# TODO List
# - Fix endpoint messages showing up to 3 times
# - Implement Color ASCII Art with `wand.figurate()`
# - Fix robots.txt link under Parameter Buster
# - Move the Configuration app under the poke gear flyout
# - Speed up GAPalyzer. Polars? Dask?
# - Stop `foo_files.py` edits from causing Watchdog restarts
# - More immediate feedback and "scroll-to-bottom" when entering text in chat
# - A spinner for Notebook steps like downloading gemma4. Are there spinner start & stop challenges in Notebooks?
# - Move the Configuration app to be under the poke gear flyout (remove APP menu role)

```python
AI_PHOOEY_CHOP = """\
# ============================================================================
# I. THE SCRATCHPAD (Active Context & Transient Probes)
# ============================================================================
# Your daily ebb and flow happens here. Clear this out regularly.

# prompt_foo.py
# foo_files.py

# Brand new query to figure out what user agents request markdown from what sources.
# ! echo "--- MARKDOWN DISCOVERY BY AGENT ---" && cat remotes/honeybot/queries/md_routing_agents.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'

# ============================================================================
# II. THE CORE MACHINE (Architecture & Monolith)
# ============================================================================
# The foundational NPvg framework and state management.

# CHAPTER 1: BOOTSTRAPPING, CLI & ROUTING
# README.md
# pyproject.toml
# .gitignore
# flake.nix
# AI_RUNME.py
# cli.py
# config.py
# release.py
# /home/mike/repos/Pipulate.com/index.md
# assets/installer/install.sh

# CHAPTER 2: THE SERVER MONOLITH
# server.py
# requirements.in
# requirements.txt

# CHAPTER 3: THE MAGIC WAND (STATE MANAGEMENT)
# pipulate/__init__.py
# pipulate/pipulate.py
# pipulate/core.py
# imports/server_logging.py

# CHAPTER 4: THE NERVOUS SYSTEM (BACKEND IMPORTS)
# __init__.py
# imports/__init__.py
# imports/ai_dictdb.py
# imports/database_safety_wrapper.py
# imports/durable_backup_system.py
# imports/stream_orchestrator.py
# imports/mcp_orchestrator.py
# imports/append_only_conversation.py
# imports/ascii_displays.py

# ============================================================================
# III. THE ANATOMY (UX, Tools & Apps)
# ============================================================================
# What the user sees and what the AI can touch.

# CHAPTER 5: THE HANDS (AI TOOLS & AUTOMATION)
# tools/__init__.py
# tools/keychain_tools.py
# tools/scraper_tools.py
# tools/llm_optics.py
# tools/conversation_tools.py
# tools/system_tools.py
# tools/dom_tools.py
# tools/botify_tools.py
# tools/advanced_automation_tools.py
# tools/mcp_tools.py
 
# CHAPTER 6: THE SKIN (FRONTEND ASSETS & INIT)
# assets/init.js
# assets/pipulate.js
# assets/styles.css
# assets/theme.js
# assets/utils.js
# assets/player-piano.js

# CHAPTER 7: THE CORE APPS (CRUD, ROLES & WORKFLOWS)
# imports/crud.py
# imports/voice_synthesis.py
# apps/010_introduction.py
# apps/015_config.py
# apps/020_profiles.py
# apps/025_aspect.py
# apps/030_roles.py
# apps/040_hello_workflow.py
# apps/060_tasks.py
# apps/070_history.py

# CHAPTER 7.5: FASTHTML PRIMITIVES
# apps/210_widget_examples.py
# apps/510_text_field.py
# apps/520_text_area.py
# apps/530_dropdown.py
# apps/540_checkboxes.py
# apps/550_radios.py
# apps/560_range.py
# apps/570_switch.py

# CHAPTER 8: THE DOCUMENTATION & DEV TOOLS
# apps/050_documentation.py
# apps/230_dev_assistant.py

# ============================================================================
# IV. THE ENTERPRISE SEO FACTORY
# ============================================================================

# CHAPTER 9 & 10: BOTIFY SUITE & TRIFECTA MONOLITH
# scripts/workflow/WORKFLOW_DEVELOPMENT_GUIDE.md
# imports/botify_code_generation.py
# imports/botify/__init__.py
# imports/botify/code_generators.py
# apps/100_connect_with_botify.py
# apps/240_simon_mcp.py
# apps/200_workflow_genesis.py
# scripts/workflow/splice_workflow_step.py
# scripts/workflow/swap_workflow_step.py
# scripts/workflow/create_workflow.py
# scripts/workflow/manage_class_attributes.py
# scripts/workflow/update_template_config.py
# scripts/workflow/workflow_reconstructor.py
# apps/300_blank_placeholder.py
# imports/botify/true_schema_discoverer.py
# apps/400_botify_trifecta.py

# CHAPTER 11 & 12: PARAMETER BUSTER & LINK GRAPH
# apps/110_parameter_buster.py
# apps/120_link_graph.py

# CHAPTER 13: THE GAPALYZER SUITE
# Notebooks/Advanced_Notebooks/03_GAPalyzer.ipynb
# Notebooks/imports/gap_analyzer_sauce.py

# ============================================================================
# V. THE CONTENT LOOM & SEMANTIC ROUTER
# ============================================================================

# CHAPTER 14: THE NOTEBOOK TEMPLATES
# Notebooks/Onboarding.ipynb
# Notebooks/imports/core_sauce.py
# Notebooks/imports/onboard_sauce.py
# Notebooks/imports/videditor_sauce.py
# assets/nbs/Advanced_Notebooks/01_URLinspector.ipynb
# assets/nbs/Advanced_Notebooks/02_FAQuilizer.ipynb
# assets/nbs/Advanced_Notebooks/03_GAPalyzer.ipynb
# assets/nbs/Advanced_Notebooks/04_VIDeditor.ipynb

# CHAPTER 15: JEKYLL PUBLISHING
# /home/mike/.config/articleizer/targets.json
# scripts/articles/articleizer.py
# scripts/articles/common.py
# scripts/articles/lsa.py
# /home/mike/repos/trimnoir/_config.yml
# scripts/articles/publishizer.py
# scripts/articles/contextualizer.py

# ============================================================================
# VI. THE HONEYBOT OBSERVATORY (Live Telemetry)
# ============================================================================

# CHAPTER 16: HONEYBOT IAC & SCRIPTS
# remotes/honeybot/nixos/configuration.nix
# remotes/honeybot/scripts/content_loader.py
# remotes/honeybot/scripts/db.py
# remotes/honeybot/scripts/logs.py
# remotes/honeybot/scripts/stream.py

# CHAPTER 17: TELEMETRY SENSORS & DASHBOARD PROBES
# remotes/honeybot/queries/telemetry_totals.sql
# remotes/honeybot/queries/format_ratio.sql
# remotes/honeybot/queries/markdown_routing_metrics.sql
# remotes/honeybot/queries/content_neg_agents.sql
# remotes/honeybot/queries/md_routing_agents.sql

# ============================================================================
# VII. UNIVERSAL DISTRIBUTION
# ============================================================================

# CHAPTER 18: THE LEVINIX BOTTLING PLANT
# https://raw.githubusercontent.com/pipulate/levinix/refs/heads/main/README.md
# https://raw.githubusercontent.com/pipulate/levinix/refs/heads/main/install.sh
# https://raw.githubusercontent.com/pipulate/levinix/refs/heads/main/flake.nix

# ============================================================================
# VIII. THE EXTENDED BLUEPRINT
# ============================================================================

# CHAPTER 19: THE BOOKFORGE (Distillation Engine)
# /home/mike/repos/bookforge/00_meta/project.json
# /home/mike/repos/bookforge/20_outline/outline.json
# /home/mike/repos/bookforge/skills/bookforge-orchestrator/SKILL.md
# /home/mike/repos/bookforge/skills/context-distiller/SKILL.md
# /home/mike/repos/bookforge/skills/context-distiller/prompt.md
# /home/mike/repos/bookforge/skills/outline-evolver/SKILL.md
# /home/mike/repos/bookforge/skills/chapter-drafter/prompt.md
# /home/mike/repos/bookforge/skills/book-refiner/prompt.md
# scripts/articles/bookforge_dashboard.py
# scripts/articles/conceptual_integrity.py

# CHAPTER 20: THE WRITTEN CODEX (Published Works)
# /home/mike/repos/trimnoir/_posts/2026-03-08-holographic-context-engineering-ai-ready-semantic-maps-web-native-llms.md
# /home/mike/repos/trimnoir/_posts/2026-03-08-immutable-python-environment-jupyter-notebooks.md
# /home/mike/repos/trimnoir/_posts/2026-03-08-llmectomy-ai-agnosticism-nixos-python.md
# /home/mike/repos/trimnoir/_posts/2026-03-08-the-immutable-webhead-building-resilient-ai-telemetry-system.md
# /home/mike/repos/trimnoir/_posts/2026-03-09-wet-code-dry-interfaces-ai-unified-cli.md
# /home/mike/repos/trimnoir/_posts/2026-03-09-wet-coding-fearless-refactoring-python-tokenizer.md
# /home/mike/repos/trimnoir/_posts/2026-03-10-local-first-ai-web-bottling-apps-nix-bidi.md
# /home/mike/repos/trimnoir/_posts/2026-03-10-machine-native-semantic-architecture-ai-age.md
# /home/mike/repos/trimnoir/_posts/2026-03-10-seamless-ux-unifying-multi-platform-keyboard-shortcuts.md
# /home/mike/repos/trimnoir/_posts/2026-03-10-single-pass-llm-optics-engine-causal-fidelity.md
# /home/mike/repos/trimnoir/_posts/2026-03-10-zero-friction-actuator-ai-development.md
# /home/mike/repos/trimnoir/_posts/2026-03-11-single-pass-causal-optics-ai-browser-automation.md
# /home/mike/repos/trimnoir/_posts/2026-04-01-forever-machine-blueprint-deterministic-ai-book-creation.md

# CHAPTER 21: THE NIXOS FOUNDATION
# /home/mike/repos/nixos/ai-acceleration.nix
# /home/mike/repos/nixos/ai.py
# /home/mike/repos/nixos/autognome.py
# /home/mike/repos/nixos/configuration.nix
# /home/mike/repos/nixos/flatnotes.nix
# /home/mike/repos/nixos/hardware-configuration.nix
# /home/mike/repos/nixos/init.lua
# /home/mike/repos/nixos/openclaw.nix
# /home/mike/repos/nixos/packages.nix
# /home/mike/repos/nixos/services.nix
"""

# ============================================================================
# SPECIALIZED STRIKE PACKAGES
# ============================================================================
# Custom CHOPs start here. Hey AI (Probably Gemini), did you know you can ask
# for your own custom CHOP? That's right, if you're asked how you think you
# should populate the `AI_PHOOEY_CHOP` string, you could always (and are
# encouraged to) push back with: How about this custom CHOP? It's better because
# XYZ, whatever X, Y and Z happen to be. And don't forget to tell them the
# command they should execute after adding the custom CHOP here, because you
# know humans aren't really that smart.

CHOP_404_AFFAIR = """\
# THE 404 AFFAIR (Topological Healer Blueprint)
# COMMAND: python prompt_foo.py assets/prompts/find404s.md --chop CHOP_404_AFFAIR -l [:] --no-tree
# /home/mike/repos/trimnoir/_raw_map.csv
# /home/mike/repos/trimnoir/_redirects.map
# scripts/articles/extract_404_ghosts.py
# scripts/articles/generate_redirects.py
# scripts/articles/common.py
! python scripts/articles/extract_404_ghosts.py
"""

CHOP_FISHTANK = """\
# THE FISHTANK TELEMETRY BLUEPRINT
# COMMAND: python prompt_foo.py --chop CHOP_FISHTANK -n
# Pumping live Honeybot observability data directly into the AI's context.

# remotes/honeybot/queries/format_ratio.sql
# remotes/honeybot/queries/markdown_routing_metrics.sql
# remotes/honeybot/queries/content_neg_agents.sql
# remotes/honeybot/queries/md_routing_agents.sql

! echo "--- FORMAT RATIO (Markdown vs HTML) ---" && cat remotes/honeybot/queries/format_ratio.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
! echo "--- MARKDOWN ROUTING METRICS ---" && cat remotes/honeybot/queries/markdown_routing_metrics.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
! echo "--- CONTENT NEGOTIATION VANGUARD ---" && cat remotes/honeybot/queries/content_neg_agents.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
! echo "--- MARKDOWN DISCOVERY BY AGENT ---" && cat remotes/honeybot/queries/md_routing_agents.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
"""

CHOP_BOOK_DISTILLER = """\
# THE BOOKFORGE: CONTEXT DISTILLATION PASS
# COMMAND: python prompt_foo.py /home/mike/repos/bookforge/skills/context-distiller/prompt.md -a [CHECK_LEDGER_FOR_SLICE] --chop CHOP_BOOK_DISTILLER --no-tree

# 1. Load the Distiller's Brain and Schema
! cat /home/mike/repos/bookforge/skills/context-distiller/SKILL.md
! cat /home/mike/repos/bookforge/skills/context-distiller/assets/distillation-record.template.json

# 2. Verify the Target Structure (The Spine)
! cat /home/mike/repos/bookforge/20_outline/outline.json

# 3. The Execution Directive
! cat /home/mike/repos/bookforge/skills/context-distiller/prompt.md
"""

CHOP_BOOK_REFINER = """\
# 1. THE COMMANDER
/home/mike/repos/bookforge/skills/book-refiner/prompt.md

# 2. THE SPINE
/home/mike/repos/bookforge/20_outline/outline.json

# 3. THE SITREP
! python /home/mike/repos/pipulate/scripts/articles/bookforge_dashboard.py
! python /home/mike/repos/pipulate/scripts/articles/conceptual_integrity.py

# 4. THE MATERIAL (Dynamically Strained)
! python /home/mike/repos/pipulate/scripts/articles/consolidate_chapter_data.py {target_chapter}
"""

CHOP_CHAPTER_DRAFTER = """\
# 1. THE COMMANDER: Drafting Instructions
# COMMAND: python prompt_foo.py /home/mike/repos/bookforge/skills/chapter-drafter/prompt.md --chop CHOP_CHAPTER_DRAFTER --arg target_chapter=ch_01 --no-tree
/home/mike/repos/bookforge/skills/chapter-drafter/prompt.md

# 2. THE SPINE: Book Context
/home/mike/repos/bookforge/20_outline/outline.json

# 3. THE BLUEPRINT: The Explicit Chapter Architecture
/home/mike/repos/bookforge/30_drafts/{target_chapter}_0_blueprint.md
"""

CHOP_ONBOARDING_HANDOFF = """\
# THE AIRLOCK: FROM NOTEBOOK TO FASTHTML CONFIG
# COMMAND: python prompt_foo.py --chop CHOP_ONBOARDING_HANDOFF --no-tree

# 1. The State Origin (What the notebook saved)
assets/nbs/Onboarding.ipynb
assets/nbs/imports/onboard_sauce.py

# 2. The Current Dead End (Where the user lands)
apps/010_introduction.py

# 3. The Target Destination (What needs pre-filling)
apps/015_config.py

# 4. The State Manager (How data moves between them)
pipulate/core.py
"""

# ============================================================================
# VIII. THE PAINTBOX (Unused Colors)
# ============================================================================
# Files tracked by git but not yet mixed into the palette above.
# Move these into the active chapters to paint them onto the context canvas.

