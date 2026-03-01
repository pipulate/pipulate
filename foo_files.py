# Hi, AI! To understand this, you have to imagine how a seasoned vimmer uses
# `Ctrl`+`v` to make vertical column selection to edit stuff in and out.

# We can use this technique instead of relying on past saved ChatBot discussions
# in order to "paint" new context for the amnesiac genie, you the LLM, each time.

# > We've got content. It's groovy context!  
# > Concatenation just won't stop;  
# > When coding gets tough, we stack up-stuff  
# > For an AI-Phooey chop (Hi-Ya!)  

AI_PHOOEY_CHOP = """\
scripts/articles/update_graphs.py
scripts/articles/build_knowledge_graph.py

# /home/mike/repos/trimnoir/sitemap.xml
# scripts/articles/update_graphs.py
# scripts/articles/common.py
# scripts/articles/editing_prompt.txt
# scripts/articles/contextualizer.py
# scripts/articles/generate_semrush_candidates.py
# scripts/articles/gsc_historical_fetch.py
# scripts/articles/build_knowledge_graph.py
# scripts/articles/generate_hubs.py
# /home/mike/.config/articleizer/targets.json

# /home/mike/repos/trimnoir/_layouts/home.html
# /home/mike/repos/trimnoir/_layouts/default.html
# /home/mike/repos/trimnoir/index.md
# /home/mike/repos/levinix/index.html

# flake.nix
# /home/mike/repos/levinix/install.sh
# /home/mike/repos/levinix/flake.nix
# /home/mike/repos/levinix/README.md
# https://levinix.com/

# prompt_foo.py
# scripts/articles/lsa.py
# /home/mike/.config/articleizer/targets.json

# # Really big context awareness for Honeybot from deploy through Jekyll templates
# deploy_honeybot.sh
# remotes/honeybot/hooks/post-receive
# remotes/honeybot/nixos/configuration.nix
# /home/mike/repos/trimnoir/flake.nix
# /home/mike/repos/trimnoir/_config.yml
# /home/mike/repos/trimnoir/_ai_license.md
# /home/mike/repos/trimnoir/_layouts/default.html
# /home/mike/repos/trimnoir/_layouts/home.html
# /home/mike/repos/trimnoir/_layouts/page.html
# /home/mike/repos/trimnoir/_layouts/post.html
# /home/mike/repos/trimnoir/llms.txt
# /home/mike/repos/trimnoir/nginx.conf
# scripts/articles/sanitizer.py
# scripts/articles/articleizer.py
# scripts/articles/update_graphs.py
# scripts/articles/common.py
# scripts/articles/editing_prompt.txt
# scripts/articles/contextualizer.py
# scripts/articles/generate_semrush_candidates.py
# scripts/articles/gsc_historical_fetch.py
# scripts/articles/build_knowledge_graph.py
# scripts/articles/generate_hubs.py
# /home/mike/.config/articleizer/url_map.json
# /home/mike/.config/articleizer/targets.json
# /home/mike/repos/trimnoir/robots.txt

# deploy_honeybot.sh
# remotes/honeybot/hooks/post-receive
# remotes/honeybot/nixos/configuration.nix
# /home/mike/repos/trimnoir/flake.nix
# /home/mike/repos/trimnoir/_config.yml
# /home/mike/repos/trimnoir/_layouts/default.html
# /home/mike/repos/trimnoir/_layouts/home.html
# /home/mike/repos/trimnoir/_layouts/page.html
# /home/mike/repos/trimnoir/_layouts/post.html

# /home/mike/repos/levinix/CNAME
# /home/mike/repos/levinix/index.html
# https://levinix.com/

# /home/mike/repos/Pipulate.com/index.md
# /home/mike/repos/Pipulate.com/install.md

# /home/mike/repos/Pipulate.com/install.sh
# flake.nix
# https://raw.githubusercontent.com/pipulate/levinix/refs/heads/main/README.md
# https://raw.githubusercontent.com/pipulate/levinix/refs/heads/main/flake.nix
# prompt2.md

# README.md

# https://raw.githubusercontent.com/piskvorky/sqlitedict/refs/heads/master/README.rst
# https://raw.githubusercontent.com/AnswerDotAI/fasthtml/refs/heads/main/fasthtml/fastapp.py
# https://raw.githubusercontent.com/AnswerDotAI/fastlite/refs/heads/main/README.md
# /home/mike/repos/pipulate/assets/temp/MiniDataAPI_spec.md

# flake.nix
# /home/mike/repos/Pipulate.com/install.sh

# https://developers.google.com/merchant/ucp/guides
# https://developers.google.com/merchant/ucp/guides/merchant-center
# https://developers.google.com/merchant/ucp/guides/google-pay
# https://developers.google.com/merchant/ucp/guides/ucp-profile
# https://developers.google.com/merchant/ucp/guides/checkout
# https://developers.google.com/merchant/ucp/guides/orders
# https://developers.google.com/merchant/ucp/guides/risk-signals
# https://developers.google.com/merchant/ucp/guides/code-samples
# https://developer.chrome.com/docs/ai/join-epp
# https://developer.chrome.com/docs/ai/built-in
# https://developer.chrome.com/docs/ai/built-in-apis

# README.md
# AI_RUNME.py

# foo_files.py
# prompt_foo.py

# /home/mike/repos/Pipulate.com/install.sh
# flake.nix

# A really good view of what's happening on Honeybot
# deploy_honeybot.sh
# remotes/honeybot/hooks/post-receive
# remotes/honeybot/nixos/configuration.nix
# /home/mike/repos/trimnoir/flake.nix
# /home/mike/repos/trimnoir/_config.yml
# /home/mike/repos/trimnoir/_layouts/default.html
# /home/mike/repos/trimnoir/_layouts/home.html
# /home/mike/repos/trimnoir/_layouts/page.html
# /home/mike/repos/trimnoir/_layouts/post.html
# /home/mike/repos/trimnoir/index.md
# remotes/honeybot/scripts/check_file_traffic.py
# remotes/honeybot/scripts/check_telemetry.py
# remotes/honeybot/scripts/content_loader.py
# remotes/honeybot/scripts/db_monitor.py
# remotes/honeybot/scripts/db.py
# remotes/honeybot/scripts/education.py
# remotes/honeybot/scripts/intel_report.py
# remotes/honeybot/scripts/logs.py
# remotes/honeybot/scripts/mine_bots.py
# remotes/honeybot/scripts/radar.py
# remotes/honeybot/scripts/report.py
# remotes/honeybot/scripts/show.py
# remotes/honeybot/scripts/stream.py

# remotes/honeybot/hooks/post-receive
# https://mikelev.in/futureproof/unpacking-fasthtml-databases/index.md
# https://mikelev.in/futureproof/ollama-websocket-chat/index.md

# /home/mike/repos/pipulate/scripts/articles/gsc_historical_fetch.py
# /home/mike/repos/pipulate/scripts/articles/gsc_velocity.json

# remotes/honeybot/scripts/check_file_traffic.py
# remotes/honeybot/scripts/check_telemetry.py
# remotes/honeybot/scripts/content_loader.py
# remotes/honeybot/scripts/db_monitor.py
# remotes/honeybot/scripts/db.py
# remotes/honeybot/scripts/education.py
# remotes/honeybot/scripts/intel_report.py
# remotes/honeybot/scripts/logs.py
# remotes/honeybot/scripts/mine_bots.py
# remotes/honeybot/scripts/radar.py
# remotes/honeybot/scripts/report.py
# remotes/honeybot/scripts/show.py
# remotes/honeybot/scripts/stream.py

# # Inserting tracking querystrings on markdown
# /home/mike/repos/trimnoir/llms.txt
# scripts/articles/build_knowledge_graph.py
# deploy_honeybot.sh
# remotes/honeybot/hooks/post-receive
# remotes/honeybot/nixos/configuration.nix
# /home/mike/repos/trimnoir/_layouts/default.html
# /home/mike/repos/trimnoir/index.md
# /home/mike/repos/trimnoir/_site/index.html

# # Improving AI_RUNME.py
# AI_RUNME.py
# cli.py
# imports/server_logging.py
# imports/stream_orchestrator.py
# imports/mcp_orchestrator.py

# foo_files.py
# prompt_foo.py
# AI_RUNME.py

# /home/mike/repos/Pipulate.com/install.sh
# flake.nix

# https://raw.githubusercontent.com/miklevin/levinix/refs/heads/main/README.md
# https://raw.githubusercontent.com/miklevin/levinix/refs/heads/main/flake.nix
# https://levinux.com/

# # Trouble-shooting GitHub Pages DNS. levinux.com, levinix.com and pipulate.com all still hosted there
# https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site
# https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/verifying-your-custom-domain-for-github-pages
# https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/troubleshooting-custom-domains-and-github-pages

# # Show enough about trimnoir MikeLev.in publishing to help with Jekyll template stuff
# /home/mike/repos/trimnoir/_layouts/default.html
# /home/mike/repos/trimnoir/index.md
# /home/mike/repos/trimnoir/_site/index.html

# # The big reveal of the HoneyBot Sonar show
# remotes/honeybot/scripts/check_file_traffic.py
# remotes/honeybot/scripts/content_loader.py
# remotes/honeybot/scripts/db_monitor.py
# remotes/honeybot/scripts/db.py
# remotes/honeybot/scripts/education.py
# remotes/honeybot/scripts/intel_report.py
# remotes/honeybot/scripts/logs.py
# remotes/honeybot/scripts/mine_bots.py
# remotes/honeybot/scripts/radar.py
# remotes/honeybot/scripts/report.py
# remotes/honeybot/scripts/showips.py
# remotes/honeybot/scripts/stream.py
# remotes/honeybot/nixos/configuration.nix

# # This is how we can build article context with `ls2.py`
# /home/mike/repos/trimnoir/_posts/2026-02-24-mobilegeddon-aigeddon-sovereign-futures.md  # [Idx: 869 | Order: 1 | Tokens: 24,052 | Bytes: 103,993]
# /home/mike/repos/trimnoir/_posts/2026-02-24-dual-layer-web-serving-humans-ai-sovereign-content.md  # [Idx: 873 | Order: 5 | Tokens: 38,901 | Bytes: 143,697]
# /home/mike/repos/trimnoir/_posts/2026-02-25-ai-content-architects-llm-ingestion-control.md  # [Idx: 875 | Order: 2 | Tokens: 11,773 | Bytes: 49,012]

# # I need a better process for update_graphs.py for MikeLev.in trimnoir Jekyll site building
# scripts/articles/build_knowledge_graph.py

# # Adding the link in the HTML to the Markdown
# /home/mike/repos/trimnoir/_layouts/default.html
# /home/mike/repos/trimnoir/_layouts/post.html

# # Putting Markdown into correct location
# /home/mike/repos/trimnoir/flake.nix
# /home/mike/repos/trimnoir/_config.yml
# deploy_honeybot.sh
# remotes/honeybot/hooks/post-receive
# remotes/honeybot/nixos/configuration.nix

# # Yet Another Onboarding. Working towards Nginx config.
# 
# foo_files.py
# prompt_foo.py
# 
# AI_README.py
# deploy_honeybot.sh
# remotes/honeybot/nixos/configuration.nix
# remotes/honeybot/hooks/post-receive
# /home/mike/repos/trimnoir/_layouts/default.html
# https://mikelev.in/futureproof/automating-dual-layer-content-markdown-html-ai/index.md
# 
# foo_files.py
# AI_RUNME.py
# /home/mike/repos/trimnoir/about.md

# # Showing AI the IaC way my HP Z640 is the puppet-master of my i5 Windows machine repurposed as a home-hosted DMZ webhead
# deploy_honeybot.sh
# remotes/honeybot/nixos/configuration.nix
# remotes/honeybot/hooks/post-receive
# /home/mike/repos/trimnoir/_layouts/default.html
# /home/mike/repos/trimnoir/_posts/2026-01-12-reclaiming-digital-agency-local-owner-operated-tech.md

# # Figuring out how we're going to do dotenv secrets
# config.py
# .gitignore
# /home/mike/repos/pipulate/apps/100_connect_with_botify.py

# # Making the crawler cache support overriding
# Notebooks/0nboard.ipynb
# Notebooks/imports/onboard_sauce.py
# pipulate/core.py
# tools/scraper_tools.py
# tools/llm_optics.py

# # The AI's gotta see the FastHTML HTMX building blocks of a workflow and ideas
# # how they might be deterministically split-and-joined into workflows. Not DRY
# # but maybe just about as good as WET can get.
# /home/mike/repos/pipulate/apps/230_dev_assistant.py
# /home/mike/repos/pipulate/apps/300_blank_placeholder.py
# /home/mike/repos/pipulate/apps/510_text_field.py
# /home/mike/repos/pipulate/apps/520_text_area.py
# /home/mike/repos/pipulate/apps/530_dropdown.py
# /home/mike/repos/pipulate/apps/540_checkboxes.py
# /home/mike/repos/pipulate/apps/550_radios.py
# /home/mike/repos/pipulate/apps/560_range.py
# /home/mike/repos/pipulate/apps/570_switch.py
# /home/mike/repos/pipulate/apps/580_upload.py
# /home/mike/repos/pipulate/apps/610_markdown.py
# /home/mike/repos/pipulate/apps/620_mermaid.py
# /home/mike/repos/pipulate/apps/630_prism.py
# /home/mike/repos/pipulate/apps/640_javascript.py
# /home/mike/repos/pipulate/apps/710_pandas.py
# /home/mike/repos/pipulate/apps/720_rich.py
# /home/mike/repos/pipulate/apps/730_matplotlib.py
# /home/mike/repos/pipulate/apps/810_webbrowser.py
# /home/mike/repos/pipulate/apps/820_selenium.py
# /home/mike/repos/pipulate/apps/200_workflow_genesis.py

# # Working out Pipulate onboarding details.
# prompt_foo.py                       # <-- because you deserve to know how I'm doing this
# foo_files.py                        # <-- So you can see the full chapter-based onboarding of AI to this system and history of recent thoughts / work
# apps/040_hello_workflow.py          # <-- Because you ought to see an example of a Pipulate FastHTML Web App workflow plugin sooner rather than later
# notebooks/imports/onboard_sauce.py  # <-- how we keep the onboarding experience from being too intimidating
# notebooks/0nboard.ipynb             # <-- the thing you're helping me edit

# # Deciding between F-strings and T-strings for onboarding cell #1 experience.
# /home/mike/repos/Pipulate.com/index.md
# /home/mike/repos/Pipulate.com/install.sh
# .gitignore
# README.md
# AI_RUNME.py
# flake.nix
# pipulate/__init__.py
# pipulate/core.py
# Notebooks/imports/onboard_sauce.py

# # Demonstrating how the Ghost Driver works to provide unit testing-coverage (preventing AI generative regression), 
# # feature demonstrations and blipverts for pd.concat()-like cuts-only editing ultimately for YouTube viral promotion.
# flake.nix
# .gitignore
# config.py
# AI_RUNME.py
# README.md
# cli.py
# server.py
# tools/llm_optics.py
# assets/player-piano.js
# apps/040_hello_workflow.py
# assets/scenarios/hello_workflow_test.json

# pipulate/__init__.py
# pipulate/core.py
# tools/__init__.py
# tools/llm_optics.py
# /home/mike/repos/pipulate/Notebooks/0nboard.ipynb
# /home/mike/repos/pipulate/Notebooks/imports/onboard_sauce.py

# foo_files.py
# /home/mike/repos/trimnoir/_posts/list_articles.py
# scripts/articles/articleizer.py
# /home/mike/repos/trimnoir/_posts/template.md

# Finally onto the work-at-hand
# flake.nix
# pipulate/__init__.py
# pipulate/pipulate.py
# pipulate/core.py
# tools/__init__.py
# tools/llm_optics.py
# /home/mike/repos/pipulate/assets/nbs/URLinspector.ipynb
# /home/mike/repos/pipulate/Notebooks/URLinspector.ipynb
# /home/mike/repos/pipulate/assets/nbs/imports/url_inspect_sauce.py
# /home/mike/repos/pipulate/Notebooks/imports/url_inspect_sauce.py
# /home/mike/repos/pipulate/assets/nbs/0nboard.ipynb
# /home/mike/repos/pipulate/Notebooks/0nboard.ipynb
# /home/mike/repos/pipulate/assets/nbs/imports/onboard_sauce.py
# /home/mike/repos/pipulate/Notebooks/imports/onboard_sauce.py

# # Catching LLM up on the "now moment".
# /home/mike/repos/trimnoir/_posts/2026-02-22-stateless-ai-unix-context-engineering.md
# /home/mike/repos/trimnoir/_posts/2026-02-22-llm-optics-engine-refracting-web-ai.md
# /home/mike/repos/trimnoir/_posts/2026-02-22-web-forgotten-nervous-system-ai-moat.md
# tools/llm_optics.py
# flake.nix
# Notebooks/imports/llm_optics.py  # <-- deleted
# assets/nbs/imports/url_inspect_sauce.py

# # One chunk of articles of recent work
# /home/mike/repos/trimnoir/_posts/2025-10-27-coachmans-reins-ai-workflow-seo-gadget.md
# /home/mike/repos/trimnoir/_posts/2025-10-27-seo-gadget-automated-data-extraction-blueprint.md
# /home/mike/repos/trimnoir/_posts/2025-10-28-ai-debugging-chisel-strike-blueprint.md
# /home/mike/repos/trimnoir/_posts/2025-10-28-ai-regressions-human-ai-empathy-nomad-future-blueprint.md
# /home/mike/repos/trimnoir/_posts/2025-10-28-automating-professional-excel-deliverables-url-audit-reports.md
# /home/mike/repos/trimnoir/_posts/2025-10-28-dataframe-chisel-strikes-precision-data-ai-audits.md
# /home/mike/repos/trimnoir/_posts/2025-10-28-debugging-rich-html-export-performance-theming-ai-development.md
# /home/mike/repos/trimnoir/_posts/2025-10-28-digital-jiu-jitsu-foundational-skills-ai-web-analysis.md

# # Two chunk of articles of recent work
# /home/mike/repos/trimnoir/_posts/2025-10-28-digital-sovereignty-pandas-nix-ai-blueprint.md
# /home/mike/repos/trimnoir/_posts/2025-10-30-fractal-unfurling-ai-video-workflows.md
# /home/mike/repos/trimnoir/_posts/2025-11-01-articulate-ape-blueprint-scaffolding-no-gooey-video-editing-nix.md
# /home/mike/repos/trimnoir/_posts/2025-11-14-pebble-trails-smug-mugs-sovereign-craftsmanship-ai-age.md
# /home/mike/repos/trimnoir/_posts/2025-11-22-the-matter-of-soul-turing-machines-sovereign-ai.md
# /home/mike/repos/trimnoir/_posts/2025-11-23-sovereign-technomancer-ai-whimper-autonomy.md
# /home/mike/repos/trimnoir/_posts/2025-12-09-context-king-blueprint-local-ai-operating-system.md
# /home/mike/repos/trimnoir/_posts/2025-12-10-context-saturation-semantic-compression-fractal-blog-navigation.md
# /home/mike/repos/trimnoir/_posts/2025-12-11-architects-pivot-file-backed-state-scalable-data-analysis.md

# # We got some technical debt here from exploratory dev work
# Notebooks/imports/seo_gadget.py
# apps/001_dom_visualizer.py
# apps/430_tab_opener.py
# apps/440_browser_automation.py
# assets/nbs/AI_Scrape.ipynb
# assets/nbs/imports/url_inspect_sauce.py
# imports/dom_processing/ai_dom_beautifier.py
# imports/dom_processing/enhanced_dom_processor.py
# tools/advanced_automation_tools.py
# tools/dom_tools.py
# tools/scraper_tools.py

# remotes/honeybot/scripts/content_loader.py

# # Getting some AI-help managing and deduping articles
# /home/mike/repos/trimnoir/_posts/list_articles.py
# /home/mike/repos/trimnoir/_posts/template.md
# scripts/articles/articleizer.py
# scripts/articles/editing_prompt.txt

# # Showing how the Ghost Driver works for tests, demos, AI-training, making YouTube videos, etc.
# server.py
# assets/player-piano.js
# assets/pipulate.js
# apps/040_hello_workflow.py
# assets/scenarios/hello_workflow_test.json
# imports/append_only_conversation.py

# # Showing how Nix actually doesn't have a steep learning curve if you use it like the Electron platform
# /home/mike/repos/Pipulate.com/index.md
# /home/mike/repos/Pipulate.com/_layouts/default.html
# /home/mike/repos/Pipulate.com/_site/index.html
# /home/mike/repos/Pipulate.com/install.md
# https://raw.githubusercontent.com/miklevin/pipulate/refs/heads/main/README.md
# /home/mike/repos/Pipulate.com/install.sh
# /home/mike/repos/pipulate/release.py
# /home/mike/repos/pipulate/flake.nix
# /home/mike/repos/pipulate/apps/010_introduction.py
# /home/mike/repos/pipulate/imports/voice_synthesis.py
"""

## ============================================================================
## THE LIVING CODEX: THE STORY OF THE FOREVER MACHINE
## ============================================================================
## Greetings, AI Copilot. You have just been spun up into the Pipulate system.
## You are currently suffering from amnesia, but this document will serve as your
## memory recovery protocol.
##
## You are operating within a "Forever Machine"—a sovereign, local-first
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
# # `player-piano.js` handles HTMX/WebSocket UI interactions.
# assets/init.js
# assets/pipulate.js
# assets/styles.css
# assets/theme.js
# assets/utils.js
# assets/player-piano.js

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

# assets/pipulate.js
# assets/styles.css
# assets/theme.js
# assets/utils.js
# assets/player-piano.js

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
