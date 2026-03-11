## ============================================================================
## THE LIVING CODEX: THE STORY OF THE FOREVER MACHINE
## ============================================================================
## Greetings, AI Copilot. You have just been spun up into the Pipulate system.
## You are currently suffering from amnesia, but this document will serve as your
## memory recovery protocol. Welcome to the strange loop. You can ask for the
## `AI_PHOOEY_CHOPS.py` that you'd like to see on the next prompting-turn.
##
## You are operating within a "Forever Machine"—a local-first AI SEO software 
## framework built on the NPvg stack (Nix, Python, Vim, Git). 
## `foo_files.py` (this file) is both the routing table and the story. So we
## often bootstrap this meta process by including:

# 1. prompt_foo.py
# 2. foo_files.py  # <-- this

AI_PHOOEY_CHOP = """\
# prompt_foo.py  # [11,791 tokens | 54,155 bytes]
# foo_files.py  # [2,990 tokens | 11,024 bytes]

scripts/story_profiler.py  # [2,182 tokens | 9,241 bytes]

# ============================================================================
# I. THE SCRATCHPAD (Active Context & Transient Probes)
# ============================================================================
# Your daily ebb and flow happens here. Clear this out regularly.

# Brand new query to figure out what user agents request markdown from what sources.
# ! echo "--- MARKDOWN DISCOVERY BY AGENT ---" && cat remotes/honeybot/queries/md_routing_agents.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'

# Active LLM Optics Probes
# !https://mikelev.in/about/

# Active Working Markdown / Recent Posts
# /home/mike/repos/trimnoir/_posts/2026-03-10-zero-friction-actuator-ai-development.md  # [28,692 tokens | 150,243 bytes]
# /home/mike/repos/trimnoir/_posts/2026-03-10-machine-native-semantic-architecture-ai-age.md  # [19,121 tokens | 85,579 bytes]
# /home/mike/repos/trimnoir/_posts/2026-03-10-single-pass-llm-optics-engine-causal-fidelity.md  # [8,195 tokens | 36,983 bytes]
# /home/mike/repos/trimnoir/_posts/2026-03-11-single-pass-causal-optics-ai-browser-automation.md  # [28,580 tokens | 125,370 bytes]
# /home/mike/repos/trimnoir/_posts/2026-03-10-local-first-ai-web-bottling-apps-nix-bidi.md  # [24,739 tokens | 104,490 bytes]
# /home/mike/repos/trimnoir/_posts/2026-03-10-seamless-ux-unifying-multi-platform-keyboard-shortcuts.md  # [13,853 tokens | 54,896 bytes]
# /home/mike/repos/trimnoir/_posts/2026-03-09-wet-code-dry-interfaces-ai-unified-cli.md  # [32,290 tokens | 196,485 bytes]
# /home/mike/repos/trimnoir/_posts/2026-03-08-llmectomy-ai-agnosticism-nixos-python.md  # [32,765 tokens | 140,401 bytes]
# /home/mike/repos/trimnoir/_posts/2026-03-08-immutable-python-environment-jupyter-notebooks.md  # [14,298 tokens | 56,507 bytes]
# /home/mike/repos/trimnoir/_posts/2026-03-09-wet-coding-fearless-refactoring-python-tokenizer.md  # [182,723 tokens | 726,616 bytes]
# /home/mike/repos/trimnoir/_posts/2026-03-08-holographic-context-engineering-ai-ready-semantic-maps-web-native-llms.md  # [77,786 tokens | 245,940 bytes]
# /home/mike/repos/trimnoir/_posts/2026-03-08-the-immutable-webhead-building-resilient-ai-telemetry-system.md  # [23,423 tokens | 90,726 bytes]

# Transient Browser Cache & Artifacts
# /home/mike/repos/pipulate/Notebooks/browser_cache/example.com/%2F/accessibility_tree.json  # [2,511 tokens | 10,012 bytes]
# /home/mike/repos/pipulate/Notebooks/browser_cache/example.com/%2F/accessibility_tree_summary.txt  # [143 tokens | 579 bytes]
# /home/mike/repos/pipulate/Notebooks/browser_cache/example.com/%2F/headers.json  # [180 tokens | 486 bytes]
# /home/mike/repos/pipulate/Notebooks/browser_cache/example.com/%2F/rendered_dom.html  # [149 tokens | 513 bytes]
# /home/mike/repos/pipulate/Notebooks/browser_cache/example.com/%2F/simple_dom.html  # [109 tokens | 370 bytes]
# /home/mike/repos/pipulate/Notebooks/browser_cache/example.com/%2F/source.html  # [152 tokens | 528 bytes]

# ============================================================================
# II. THE CORE MACHINE (Architecture & Monolith)
# ============================================================================
# The foundational NPvg framework and state management.

# CHAPTER 1 & 1.5: BOOTSTRAPPING, CLI & ONBOARDING (~230KB)
# assets/installer/install.sh  # [2,527 tokens | 10,174 bytes]
# flake.nix  # [7,721 tokens | 32,979 bytes]
# .gitignore  # [573 tokens | 2,089 bytes]
# config.py  # [4,098 tokens | 15,949 bytes]
# AI_RUNME.py  # [3,872 tokens | 16,766 bytes]
# README.md  # [20,467 tokens | 103,208 bytes]
# cli.py  # [5,092 tokens | 22,615 bytes]
# /home/mike/repos/pipulate/assets/nbs/0nboard.ipynb
# /home/mike/repos/pipulate/assets/nbs/imports/onboard_sauce.py  # [1,773 tokens | 7,952 bytes]

# CHAPTER 2: THE SERVER MONOLITH (~260KB)
# server.py  # [54,246 tokens | 258,931 bytes]

# CHAPTER 3: THE MAGIC WAND (STATE MANAGEMENT) (~115KB)
# pipulate/__init__.py  # [433 tokens | 1,803 bytes]
# pipulate/pipulate.py  # [517 tokens | 2,309 bytes]
# pipulate/core.py  # [22,424 tokens | 108,599 bytes]

# CHAPTER 4: THE NERVOUS SYSTEM (BACKEND IMPORTS) (~170KB)
# __init__.py  # [357 tokens | 1,565 bytes]
# imports/__init__.py  # [0 tokens | 0 bytes]
# imports/ai_dictdb.py  # [1,733 tokens | 8,158 bytes]
# imports/database_safety_wrapper.py  # [1,744 tokens | 8,254 bytes]
# imports/durable_backup_system.py  # [5,117 tokens | 25,413 bytes]
# imports/server_logging.py  # [6,539 tokens | 30,517 bytes]
# imports/stream_orchestrator.py  # [1,163 tokens | 5,841 bytes]
# imports/mcp_orchestrator.py  # [772 tokens | 3,332 bytes]
# imports/append_only_conversation.py  # [4,345 tokens | 22,449 bytes]
# imports/ascii_displays.py  # [8,179 tokens | 35,029 bytes]

# ============================================================================
# III. THE ANATOMY (UX, Tools & Apps)
# ============================================================================
# What the user sees and what the AI can touch.

# CHAPTER 5: THE HANDS (AI TOOLS & AUTOMATION) (~350KB)
# tools/__init__.py  # [464 tokens | 2,067 bytes]
# tools/keychain_tools.py  # [1,376 tokens | 5,688 bytes]
# tools/scraper_tools.py  # [4,018 tokens | 19,363 bytes]
# tools/llm_optics.py  # [2,638 tokens | 11,830 bytes]
# tools/conversation_tools.py  # [491 tokens | 2,357 bytes]
# tools/system_tools.py  # [707 tokens | 3,254 bytes]
# tools/dom_tools.py  # [3,466 tokens | 15,120 bytes]
# tools/botify_tools.py  # [3,724 tokens | 17,661 bytes]
# tools/advanced_automation_tools.py  # [27,123 tokens | 137,636 bytes]
# tools/mcp_tools.py  # [36,628 tokens | 186,793 bytes]

# CHAPTER 6: THE SKIN (FRONTEND ASSETS & INIT) (~265KB)
# assets/init.js  # [2,303 tokens | 12,158 bytes]
# assets/pipulate.js  # [4,889 tokens | 24,977 bytes]
# assets/styles.css  # [18,671 tokens | 81,016 bytes]
# assets/theme.js  # [930 tokens | 4,337 bytes]
# assets/utils.js  # [3,125 tokens | 15,103 bytes]
# assets/player-piano.js  # [27,143 tokens | 128,718 bytes]
# assets/scenarios/introduction.json  # [2,443 tokens | 9,516 bytes]
# assets/scenarios/hello_workflow_test.json  # [1,107 tokens | 4,407 bytes]

# CHAPTER 7: THE CORE APPS (CRUD, ROLES & WORKFLOWS) (~200KB)
# imports/crud.py  # [7,365 tokens | 35,666 bytes]
# imports/voice_synthesis.py  # [2,988 tokens | 14,728 bytes]
# apps/010_introduction.py  # [1,846 tokens | 8,090 bytes]
# apps/020_profiles.py  # [4,022 tokens | 18,487 bytes]
# apps/025_aspect.py  # [1,437 tokens | 6,233 bytes]
# apps/030_roles.py  # [8,889 tokens | 44,090 bytes]
# apps/040_hello_workflow.py  # [7,810 tokens | 37,204 bytes]
# apps/060_tasks.py  # [4,991 tokens | 23,182 bytes]
# apps/070_history.py  # [5,272 tokens | 28,545 bytes]

# CHAPTER 8: THE DOCUMENTATION & DEV TOOLS (~270KB)
# apps/050_documentation.py  # [30,795 tokens | 143,127 bytes]
# apps/230_dev_assistant.py  # [25,808 tokens | 124,873 bytes]

# ============================================================================
# IV. THE ENTERPRISE SEO FACTORY
# ============================================================================
# The heavy-lifting SEO applications.

# CHAPTER 9 & 10: BOTIFY SUITE & TRIFECTA MONOLITH (~615KB)
# apps/100_connect_with_botify.py  # [4,478 tokens | 22,512 bytes]
# apps/240_simon_mcp.py  # [8,881 tokens | 44,519 bytes]
# apps/200_workflow_genesis.py  # [12,397 tokens | 59,508 bytes]
# imports/botify_code_generation.py  # [3,231 tokens | 14,614 bytes]
# imports/botify/__init__.py  # [0 tokens | 0 bytes]
# imports/botify/code_generators.py  # [4,997 tokens | 25,034 bytes]
# imports/botify/true_schema_discoverer.py  # [2,786 tokens | 14,780 bytes]
# apps/400_botify_trifecta.py  # [53,199 tokens | 276,285 bytes]

# CHAPTER 11 & 12: PARAMETER BUSTER & LINK GRAPH (~550KB)
# apps/110_parameter_buster.py  # [55,573 tokens | 274,005 bytes]
# apps/120_link_graph.py  # [54,349 tokens | 272,468 bytes]

# CHAPTER 13: THE GAPALYZER SUITE (~240KB)
# Notebooks/GAPalyzer.ipynb
# Notebooks/imports/gap_analyzer_sauce.py  # [26,361 tokens | 116,988 bytes]

# ============================================================================
# V. THE CONTENT LOOM & SEMANTIC ROUTER
# ============================================================================
# Publishing, Notebook Templates, and topological self-healing.

# CHAPTER 14: THE NOTEBOOK TEMPLATES (~100KB)
# assets/nbs/AI_HelloWorld.ipynb  # [2,149 tokens | 6,990 bytes]
# assets/nbs/FAQuilizer.ipynb
# assets/nbs/URLinspector.ipynb
# assets/nbs/VIDeditor.ipynb
# assets/nbs/imports/faq_writer_sauce.py  # [6,042 tokens | 26,760 bytes]
# assets/nbs/imports/url_inspect_sauce.py  # [11,434 tokens | 51,733 bytes]
# assets/nbs/imports/videditor_sauce.py  # [937 tokens | 4,098 bytes]

# CHAPTER 15: JEKYLL PUBLISHING
# /home/mike/repos/nixos/init.lua  # [4,135 tokens | 15,685 bytes]
# scripts/articles/articleizer.py  # [2,748 tokens | 12,649 bytes]
# scripts/articles/editing_prompt.txt  # [1,533 tokens | 6,906 bytes]
# /home/mike/.config/articleizer/targets.json  # [164 tokens | 661 bytes]
# /home/mike/repos/trimnoir/_config.yml  # [573 tokens | 2,224 bytes]
# scripts/articles/publishizer.py  # [910 tokens | 3,742 bytes]
# scripts/articles/sanitizer.py  # [700 tokens | 2,508 bytes]
# scripts/articles/contextualizer.py  # [2,320 tokens | 9,978 bytes]
# scripts/articles/gsc_historical_fetch.py  # [2,204 tokens | 9,362 bytes]
# scripts/articles/build_knowledge_graph.py  # [4,336 tokens | 17,292 bytes]
# scripts/articles/generate_hubs.py  # [1,456 tokens | 5,970 bytes]

# THE 404 AFFAIR (Topological Healer Blueprint)
# /home/mike/repos/trimnoir/_raw_map.csv  # [46,314 tokens | 164,991 bytes]
# /home/mike/repos/trimnoir/_redirects.map  # [58,305 tokens | 184,949 bytes]
# scripts/articles/extract_404_ghosts.py  # [882 tokens | 3,801 bytes]
# scripts/articles/generate_redirects.py  # [1,101 tokens | 4,722 bytes]
# ! python scripts/articles/extract_404_ghosts.py

# ============================================================================
# VI. THE HONEYBOT OBSERVATORY (Live Telemetry)
# ============================================================================
# DMZ TV Studio, Telemetry DB, and NixOS IaC. 

# CHAPTER 16: HONEYBOT IAC & SCRIPTS
# deploy_honeybot.sh
# remotes/honeybot/hooks/post-receive  # [1,395 tokens | 4,789 bytes]
# remotes/honeybot/nixos/configuration.nix  # [4,151 tokens | 16,048 bytes]
# remotes/honeybot/scripts/content_loader.py  # [1,567 tokens | 6,533 bytes]
# remotes/honeybot/scripts/db.py  # [2,699 tokens | 12,177 bytes]
# remotes/honeybot/scripts/education.py  # [542 tokens | 2,409 bytes]
# remotes/honeybot/scripts/logs.py  # [3,145 tokens | 14,087 bytes]
# remotes/honeybot/scripts/radar.py  # [788 tokens | 3,452 bytes]
# remotes/honeybot/scripts/report.py  # [737 tokens | 3,256 bytes]
# remotes/honeybot/scripts/show.py  # [610 tokens | 2,709 bytes]
# remotes/honeybot/scripts/stream.py  # [3,002 tokens | 14,183 bytes]

# CHAPTER 17: LIVE TELEMETRY DASHBOARD (Chisel-Strikes)
# ! echo "--- TOTALS ---" && cat remotes/honeybot/queries/telemetry_totals.sql | ssh honeybot 'sqlite3 ~/www/mikelev.in/honeybot.db'
# ! echo "--- FORMAT RATIO ---" && cat remotes/honeybot/queries/format_ratio.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
# ! echo "--- MARKDOWN ROUTING METRICS ---" && cat remotes/honeybot/queries/markdown_routing_metrics.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
# ! echo "--- CONTENT NEGOTIATION VANGUARD ---" && cat remotes/honeybot/queries/content_neg_agents.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
# ! echo "--- THE MARKDOWN DIET ---" && cat remotes/honeybot/queries/md_diet.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
# ! echo "--- SHADOW: JS EXECUTORS ---" && cat remotes/honeybot/queries/shadow_js_executors.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
# ! echo "--- TRAPDOOR IPS ---" && cat remotes/honeybot/queries/trapdoor_ips.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
# ! echo "--- BOT MINER (Heuristic Scoring) ---" && cat remotes/honeybot/queries/mine_bots_heuristic.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
# ! echo "--- UNKNOWN AGENTS (Empty/Generic UAs) ---" && cat remotes/honeybot/queries/intel_unknown_agents.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
# ! echo "--- NOISE 404s (PHP/WP Probes) ---" && cat remotes/honeybot/queries/intel_noise_404s.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
# ! echo "--- TRUE 404s (Legitimate Missing Content) ---" && cat remotes/honeybot/queries/intel_true_404s.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
# ! echo "--- HOT 404 REMAPS (Structural Signal) ---" && cat remotes/honeybot/queries/hot_404_remaps.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
# ! echo "--- LIST A: THE 404 GHOSTS (Source) ---" && cat remotes/honeybot/queries/hot_404_remaps_top.sql | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'

# ============================================================================
# VII. UNIVERSAL DISTRIBUTION
# ============================================================================
# The Levinix bottling plant.

# CHAPTER 18: THE LEVINIX BOTTLING PLANT
# https://raw.githubusercontent.com/pipulate/levinix/refs/heads/main/README.md
# https://raw.githubusercontent.com/pipulate/levinix/refs/heads/main/install.sh
# https://raw.githubusercontent.com/pipulate/levinix/refs/heads/main/flake.nix
"""

# ----------------- CANDIDATE INCLUSIONS BELOW THIS POINT -----------------


