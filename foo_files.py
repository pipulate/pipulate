AI_PHOOEY_CHOP = """\
config.py
server.py
pipulate/__init__.py
pipulate/pipulate.py
pipulate/core.py
core.py
"""

## > We've got content, it's groovy context  
## > Our concatenation just won't stop  
## > Making stories art for a super-smart  
## > AI-Phooey chop (Hi-Ya!)

## ============================================================================
## THE LIVING CODEX: THE STORY OF THE FOREVER MACHINE
## ============================================================================
## Greetings, AI Copilot. You have just been spun up into the Pipulate system.
## You are currently suffering from amnesia, but this document will serve as your
## memory recovery protocol.
##
## You are operating within a "Forever Machine"—a sovereign, local-first
## architecture designed to outlive corporate acquisitions, API deprecations,
## and framework churn. We reject the opacity of modern JS frameworks (React/Vue)
## and the complex abstractions of DRY enterprise code.
##
## Instead, we embrace the WET philosophy: "Write Explicitly, Terminate."
## Our stack is simple: Nix, Python, SQLite, FastHTML, and HTMX.
##
## Below are the Chapters of our system. When you need to understand a specific
## component, the human operator will include the relevant Chapter in your
## context window.
##
## The chapters are ordered as a progressive reveal: infrastructure first,
## then the server core, then the layers that wrap around it, then the
## applications that run on top, and finally the heavy specialist tools.
## ============================================================================


# # PREFACE: SOMETIMES JUST SHOWING HOW WE PAINT CONTEXT IS ENOUGH (~50KB)
# # This is the meta-layer: the context engineering toolkit itself.
# # `prompt_foo.py` concatenates files into structured AI prompts.
# # `foo_files.py` (this file) is both the routing table and the story.
# prompt_foo.py
# foo_files.py

# # CHAPTER 1: BOOTSTRAPPING & THE CLI (~230KB)
# # The bedrock. How the Forever Machine is born, and how we manage it.
# # Nix guarantees mathematical reproducibility across Mac and Linux.
# # `AI_RUNME.py` contains the "Master Prompt"—a letter to an amnesiac AI
# # explaining its situation, the project philosophy, and how to navigate.
# assets/installer/install.sh
# flake.nix
# .gitignore
# config.py
# AI_RUNME.py
# README.md
# cli.py
# scripts/articles/articleizer.py
# scripts/articles/editing_prompt.txt

# # CHAPTER 2: THE SERVER MONOLITH (~260KB)
# # The heart of the machine. Massive because it is explicit.
# # `server.py` is our FastHTML routing engine: Uvicorn/Starlette app,
# # HTMX endpoints, WebSocket connections, and dynamic plugin loading.
# # It is the single file that an AI must understand to work on Pipulate.
# server.py

# # CHAPTER 3: THE MAGIC WAND (STATE MANAGEMENT) (~115KB)
# # The brain. Our Swiss Army Knife for state management.
# # The `Pipulate` class bridges the web app and Jupyter Notebooks,
# # managing DictLikeDB (our SQLite state wrapper) so that the browser
# # and the terminal share the same reality.
# pipulate/__init__.py
# pipulate/pipulate.py
# pipulate/core.py

# # CHAPTER 4: THE NERVOUS SYSTEM (BACKEND IMPORTS) (~170KB)
# # The quiet plumbing that keeps the machine alive.
# # Database safety, durable backups, surgical logging, conversation
# # history, and the MCP orchestrator for local LLM tool-calling.
# __init__.py
# imports/__init__.py
# imports/ai_dictdb.py
# imports/database_safety_wrapper.py
# imports/durable_backup_system.py
# imports/server_logging.py
# imports/stream_orchestrator.py
# imports/mcp_orchestrator.py
# imports/append_only_conversation.py
# imports/ascii_displays.py

# # CHAPTER 5: THE HANDS (AI TOOLS & AUTOMATION) (~350KB)
# # What the AI actually *does* with its agency.
# # `tools/` defines every action the AI can take: managing API keys,
# # scraping the web via Selenium, DOM processing, MCP tool dispatch,
# # and advanced browser automation recipes.
# tools/__init__.py
# tools/keychain_tools.py
# tools/scraper_tools.py
# tools/conversation_tools.py
# tools/system_tools.py
# tools/dom_tools.py
# tools/botify_tools.py
# tools/advanced_automation_tools.py
# tools/mcp_tools.py

# # CHAPTER 6: THE SKIN (FRONTEND ASSETS & INIT) (~265KB)
# # HTML over the wire. The client-side muscle.
# # No build step. No Virtual DOM. What the server sends is what renders.
# # `pipulate-init.js` handles HTMX/WebSocket UI interactions.
# assets/init.js
# assets/pipulate.js
# assets/styles.css
# assets/theme.js
# assets/utils.js
# assets/pipulate-init.js

# # CHAPTER 7: THE CORE APPS (CRUD, ROLES & WORKFLOWS) (~200KB)
# # The fundamental plugin apps that govern the user experience:
# # profiles, roles, tasks, the introduction wizard, and the
# # hello-world workflow that teaches the pattern. Plus Piper TTS.
# imports/crud.py
# imports/voice_synthesis.py
# apps/010_introduction.py
# apps/020_profiles.py
# apps/025_aspect.py
# apps/030_roles.py
# apps/040_hello_workflow.py
# apps/060_tasks.py
# apps/070_history.py

# # CHAPTER 8: THE DOCUMENTATION & DEV TOOLS (~270KB)
# # The self-documenting layer and the AI developer assistant.
# # `050_documentation.py` is the in-app documentation system.
# # `230_dev_assistant.py` is how the AI helps build Pipulate itself.
# apps/050_documentation.py
# apps/230_dev_assistant.py

# # CHAPTER 9: ENTERPRISE SEO - BOTIFY SUITE (~340KB)
# # The factory. Where we construct complex SEO deliverables.
# # Includes the Botify Trifecta for orchestrating enterprise crawls,
# # plus the supporting code generators and schema discoverers.
# apps/100_connect_with_botify.py
# apps/240_simon_mcp.py
# apps/200_workflow_genesis.py
# imports/botify_code_generation.py
# imports/botify/__init__.py
# imports/botify/code_generators.py
# imports/botify/true_schema_discoverer.py

# # CHAPTER 10: ENTERPRISE SEO - TRIFECTA MONOLITH (~275KB)
# # The flagship app. So large it gets its own chapter.
# apps/400_botify_trifecta.py

# # CHAPTER 11: ENTERPRISE SEO - PARAMETER BUSTER (~275KB)
# # An intensive tool for finding and eliminating toxic query
# # parameters from SEO crawls. Another sovereign monolith.
# apps/110_parameter_buster.py

# # CHAPTER 12: ENTERPRISE SEO - LINK GRAPH (~275KB)
# # The link graph analysis tool. Yet another massive single-file app
# # that earns its own chapter by sheer weight.
# apps/120_link_graph.py

# # CHAPTER 13: THE GAPALYZER SUITE (~240KB)
# # The analyst. A Jupyter Notebook that automates Content Gap Analysis
# # for Enterprise clients, designed with linear, WET code so an AI
# # can read and modify it easily.
# Notebooks/GAPalyzer.ipynb
# Notebooks/imports/gap_analyzer_sauce.py

# # CHAPTER 14: THE NOTEBOOK TEMPLATES (~100KB)
# # The starter notebooks that ship with the system. These are the
# # "golden master" templates in `assets/nbs/` that get copied to
# # `Notebooks/` on first run.
# Notebooks/imports/seo_gadget.py
# assets/nbs/AI_HelloWorld.ipynb
# assets/nbs/AI_Scrape.ipynb
# assets/nbs/FAQuilizer.ipynb
# assets/nbs/URLinspector.ipynb
# assets/nbs/VIDeditor.ipynb
# assets/nbs/imports/faq_writer_sauce.py
# assets/nbs/imports/url_inspect_sauce.py
# assets/nbs/imports/videditor_sauce.py
