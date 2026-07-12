# Is this just about macOS and Linux? Or is it about Windows too?                     Impervious to Decay   
#  ____  _             _       _         ____       _                                     ___________          .--.
# |  _ \(_)_ __  _   _| | __ _| |_ ___  |  _ \ _ __(_)_ __ ___   ___     ,--./,-.     C  |     |  Nix|  Free  |o_o |
# | |_) | | '_ \| | | | |/ _` | __/ _ \ | |_) | '__| | '_ ` _ \ / _ \   / #      \    l  |     |     |        |:_/ |
# |  __/| | |_) | |_| | | (_| | ||  __/ |  __/| |  | | | | | | |  __/  |          |   o  |_____|_____|  O    //   \ \
# |_|   |_| .__/ \__,_|_|\__,_|\__\___| |_|   |_|  |_|_| |_| |_|\___|   \        /    s  |macOS|     |  p   (|     | )           
#         |_|                                                            `._,._,'     e  |Windows/WSL|  e  /'\_   _/`\           
#             Welcome to Pipulate Prime IaC, a multi-platform app;                    d  |_____|_____|  n  \___)=(___/           
#             Your intro to your "Write once run anywhere" future!                                                                                           
#             Built on a *very good* "No Problem" framework (NPvg)                    HW Decays Over Time 
#
# ==============================================================================
# PIPULATE PRIME NIX FLAKE - "MAGIC COOKIE" AUTO-UPDATING SYSTEM
# ==============================================================================
# 
# This flake is the second half of the "magic cookie" installation system.
# It works together with the assets/installer/install.sh script (hosted at pipulate.com) to:
#
# 1. Transform a non-git directory into a proper git repository
# 2. Enable forever-forward git-pull auto-updates
# 3. Provide a consistent development environment across macOS, Windows (WSL2) and Linux
#
# === THE "MAGIC COOKIE" CONCEPT ===
# The "magic cookie" approach solves a bootstrapping problem:
# - Nix flakes require a git repository to function properly
# - We can't rely on git being available on all systems during initial install
# - We want a simple one-line curl|sh installation that works everywhere
#
# The solution:
# 1. assets/installer/install.sh downloads a ZIP archive (no git required)
# 2. assets/installer/install.sh extracts the ZIP and adds a ROT13-encoded SSH key
# 3. assets/installer/install.sh runs `nix develop` to activate this flake
# 4. THIS FLAKE detects non-git directories and transforms them into git repos
# 5. Auto-updates are enabled through git pulls in future nix develop sessions
#
# === CURRENT IMPLEMENTATION ===
# The flake now fully implements the "magic cookie" functionality:
# - Detects non-git directories and transforms them into git repositories
# - Preserves critical files during transformation:
#   * whitelabel.txt (maintains app identity)
#   * .ssh directory (preserves credentials)
#   * .venv directory (preserves virtual environment)
# - Creates backups before transformation
# - Performs automatic git pulls to keep the installation up to date
# - Switches to SSH-based git operations when SSH keys are available
#
# === REPOSITORY AWARENESS ===
# This flake is part of the target pipulate project repo at:
# /home/mike/repos/pipulate/flake.nix
#
# This is different from the installer script which lives at:
# /home/mike/repos/Pipulate.com/assets/installer/install.sh
#
# When a user runs:
#
#     curl -fsSL https://pipulate.com/install.sh | bash
#
# The installer downloads this flake as part of the ZIP archive.
# Most modern development is done on Linux, but Macs are Unix. If you think Homebrew and Docker
# are the solution, you're wrong. Welcome to the world of Nix Flakes! This file defines a complete,
# reproducible development environment. It's like a recipe for your perfect workspace, ensuring
# everyone on your team has the exact same setup, every time. As a bonus, you can use Nix flakes on
# Windows under WSL. Plus, whatever you make will be deployable to the cloud.
{
  # This description helps others understand the purpose of this Flake
  description = "A flake that reports the OS using separate scripts with optional CUDA support and unfree packages allowed.";
  # Inputs are the dependencies for our Flake
  # They're pinned to specific versions to ensure reproducibility
  inputs = {
    # nixpkgs is the main repository of Nix packages
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    # flake-utils provides helpful functions for working with Flakes
    flake-utils.url = "github:numtide/flake-utils";
  };
  # Outputs define what our Flake produces
  # In this case, it's a development shell that works across different systems
      outputs = { self, nixpkgs, flake-utils }:
      let
        # TRUE SINGLE SOURCE OF TRUTH: Read version and description directly from __init__.py
        # No manual editing of this file needed - everything comes from __init__.py
        initPyContent = builtins.readFile ./__init__.py;
        # Extract __version__ from __init__.py
        versionMatch = builtins.match ".*__version__[[:space:]]*=[[:space:]]*[\"']([^\"']+)[\"'].*" initPyContent;
        versionNumber = if versionMatch != null then builtins.head versionMatch else "unknown";
        # Extract __version_description__ from __init__.py  
        descMatch = builtins.match ".*__version_description__[[:space:]]*=[[:space:]]*[\"']([^\"']+)[\"'].*" initPyContent;
        versionDesc = if descMatch != null then builtins.head descMatch else null;
        # Combine version and description
        version = if versionDesc != null then "${versionNumber} (${versionDesc})" else versionNumber;
      in
    flake-utils.lib.eachDefaultSystem (system:
      let
        # We're creating a custom instance of nixpkgs
        # This allows us to enable unfree packages like CUDA
        pkgs = import nixpkgs {
          inherit system;
          config = {
            allowUnfree = true;  # This is necessary for CUDA support
          };
        };
        # These helpers let us adjust our setup based on the OS
        isDarwin = pkgs.stdenv.isDarwin;
        isLinux = pkgs.stdenv.isLinux;
        # Define a static workspace name to prevent random file generation
        jupyterWorkspaceName = "pipulate-main";

 		# Define the default notebook for JupyterLab to open on startup
 		jupyterStartupNotebook = "Notebooks/Onboarding.ipynb";

        # --- 🌐 BROWSER TAB CONFIGURATION ---
        autoOpenJupyter = "true";
        autoOpenFastHTML = "false";
        fastHtmlOpenDelay = "0";  # Seconds to delay FastHTML tab if both are true

        # --- CORRECTED: Declarative list for notebooks to copy ---
        notebookFilesToCopy = [
          {
            source = "assets/nbs/imports/core_sauce.py";
            dest = "Notebooks/imports/core_sauce.py";
            desc = "the unified core workflow engine";
          }
          {
            source = "assets/nbs/imports/onboard_sauce.py";
            dest = "Notebooks/imports/onboard_sauce.py";
            desc = "a local 'onboard_sauce.py' source of secret sauce";
          }
          {
            source = "assets/nbs/imports/url_inspect_sauce.py";
            dest = "Notebooks/imports/url_inspect_sauce.py";
            desc = "a local 'url_inspect_sauce.py' source of secret sauce";
          }
          {
            source = "assets/nbs/imports/faq_writer_sauce.py";
            dest = "Notebooks/imports/faq_writer_sauce.py";
            desc = "a local 'faq_writer_sauce.py' source of secret sauce";
          }
          {
            source = "assets/nbs/imports/gap_analyzer_sauce.py";
            dest = "Notebooks/imports/gap_analyzer_sauce.py";
            desc = "a local 'gap_analyzer_sauce.py' source of secret sauce";
          }
          {
            source = "assets/nbs/imports/videditor_sauce.py";
            dest = "Notebooks/imports/videditor_sauce.py";
            desc = "a local 'videditor_sauce.py' source of secret sauce";
          }
          {
            source = "assets/nbs/Onboarding.ipynb";
            dest = "Notebooks/Onboarding.ipynb";
            desc = "the Pipulate initiation rite and setup guide";
          }
          {
            source = "assets/nbs/Advanced_Notebooks/01_URLinspector.ipynb";
            dest = "Notebooks/Advanced_Notebooks/01_URLinspector.ipynb";
            desc = "a local 'URL-by-URL auditor.' derived from FAQuilizer";
          }
          {
            source = "assets/nbs/Advanced_Notebooks/02_FAQuilizer.ipynb";
            dest = "Notebooks/Advanced_Notebooks/02_FAQuilizer.ipynb";
            desc = "a local 'FAQuilizer' simple workflow";
          }
          {
            source = "assets/nbs/Advanced_Notebooks/03_GAPalyzer.ipynb";
            dest = "Notebooks/Advanced_Notebooks/03_GAPalyzer.ipynb";
            desc = "a local 'Competitor Gap Analyzer.' advanced workflow";
          }
          {
            source = "assets/nbs/Advanced_Notebooks/04_VIDeditor.ipynb";
            dest = "Notebooks/Advanced_Notebooks/04_VIDeditor.ipynb";
            desc = "a local 'NoGooey Video Editor.'";
          }
          {
            source = "assets/nbs/Educational_Notebooks/Truth_Actually.ipynb";
            dest = "Notebooks/Educational_Notebooks/Truth_Actually.ipynb";
            desc = "the Player Piano Test, an interactive actuator-literacy lesson";
          }
        ];

        # Convert the Nix list to a string that Bash can loop over
        notebookFilesString = pkgs.lib.concatStringsSep "\n" (
          map (file: "${file.source};${file.dest};${file.desc}") notebookFilesToCopy
        );

        # Common packages that we want available in our environment
        # regardless of the operating system
        commonPackages = with pkgs; [
          uv                           # Fast Python package installer and resolver
          sqlite                       # Ensures correct SQLite library is linked on macOS
          (python312.withPackages (ps: with ps; [
            ruff
            nbstripout
          ]))
          nbstripout
          figlet                       # For creating ASCII art welcome messages
          tmux                         # Terminal multiplexer for managing sessions
          zlib                         # Compression library for data compression
          git                          # Version control system for tracking changes
          git-filter-repo              # Surgical git history rewriting (scrub strings/paths across all commits)
          curl                         # Command-line tool for transferring data with URLs
          wget                         # Utility for non-interactive download of files from the web
          cmake                        # Cross-platform build system generator
          htop                         # Interactive process viewer for Unix systems
          plantuml
          graphviz
          eza                          # A tree directory visualizer that uses .gitignore
          ripgrep		               # Like find and grep but honors .gitignore
          xclip
          jq
          dig
          whois
          alsa-utils
          ffmpeg
        ] ++ (with pkgs; pkgs.lib.optionals isLinux [
          espeak-ng                    # Text-to-speech, Linux only
          sox                          # Sound processing, Linux only
          virtualenv
          gcc                          # GNU Compiler Collection for compiling C/C++ code
          stdenv.cc.cc.lib             # Standard C library for Linux systems
          chromium                     # Chromium browser for Selenium automation
          undetected-chromedriver
        ]);
        # This script sets up our Python environment and project
runScript = pkgs.writeShellScriptBin "run-script" ''
          #!/usr/bin/env bash
          # Activate the virtual environment
          source .venv/bin/activate
          # Define function to copy notebook if needed (copy-on-first-run solution)
          # --- CORRECTED: Loop-based copy function ---
          copy_notebook_if_needed() {
            while IFS=';' read -r source dest desc; do
              if [ -f "$source" ] && [ ! -f "$dest" ]; then
                echo "INFO: Creating $desc..."
                echo "      Your work will be saved in '$dest'."
                mkdir -p "$(dirname "$dest")"
                cp "$source" "$dest"
              fi
            done <<EOF
          ${notebookFilesString}
          EOF
          }
          # Set up the personal playground
          if [ ! -f "Notebooks/Playground/WELCOME.md" ]; then
            echo "INFO: Setting up your personal Playground..."
            mkdir -p "Notebooks/Playground"
            cat << 'PLAYGROUND_EOF' > "Notebooks/Playground/WELCOME.md"
          # 🎢 Welcome to the Playground!
          
          This folder is your personal sandbox. It is intentionally **ignored** by Pipulate's main version control.
          
          ## Why does this exist?
          As an SEO consultant, you need a place to write fast, messy, disposable Python scripts to solve immediate client problems. You shouldn't have to worry about breaking the main Pipulate architecture or accidentally committing client data to a public repository.
          
          ## How it works:
          1. **Full Access:** Scripts here use the same `.venv` Python environment as Pipulate. You have access to `pandas`, `httpx`, `lxml`, and the Pipulate `wand` without installing anything.
          2. **The Sausage Factory:** Write your ad hoc "tracer bullet" scripts here. If they prove valuable across multiple clients, you can graduate them up to `Notebooks/imports/` as reusable "sauce" modules.
          3. **Protect Your Work:** Because Pipulate ignores this folder, we highly recommend turning it into your own private repository:
          
          ```bash
          cd Notebooks/Playground
          git init
          # Then link it to a private GitHub repository to back up your work!
          ```
          
          ## What this folder becomes (coming soon — not active yet)

          Right now this Playground is a **solo** sandbox: just you, your throwaway
          scripts, and the shared `.venv`. None of the team features below are wired
          up yet — this is a map of where things are headed, kept here so the intent
          stays visible from inside the code instead of buried in notes.

          The plan: this folder becomes the **`personal/`** bucket of a team-scale
          `Notebooks/Workshop/`. Same idea you already have — a private place to break
          things safely — just nested inside a larger structure that also holds a
          read-only canonical area and a per-person sharing surface.

          ```text
          Notebooks/Workshop/        (future — does not exist yet)
          ├── corporate/             read-only canon, managed for you
          ├── personal/   ◀── THIS   your private sandbox (this Playground)
          └── shared/<your-name>/    drop things here to share with teammates
          ```

          When it lands, the rule will be simple: **this Playground IS the `personal/`
          bucket** — no second sandbox to learn. Until then, use it exactly as
          described above and ignore everything in this section.

          Happy hacking. Throw some paint around.
          PLAYGROUND_EOF
          fi
          # Create a fancy welcome message
          if [ ! -f whitelabel.txt ]; then
            APP_NAME=$(basename "$PWD")
            if [[ "$APP_NAME" == *"botify"* ]]; then
              APP_NAME="$APP_NAME"
            else
              APP_NAME="Pipulate"
            fi
            echo "$APP_NAME" > whitelabel.txt
          fi
          # MAGIC COOKIE COMPONENT: This section reads the whitelabel.txt that should be 
          # preserved if/when the directory is transformed into a git repo
          APP_NAME=$(cat whitelabel.txt)
          PROPER_APP_NAME=$(echo "$APP_NAME" | awk '{print toupper(substr($0,1,1)) tolower(substr($0,2))}')
          figlet "$PROPER_APP_NAME"
          echo "Version: ${version}"
          # --- JupyterLab Local Configuration ---
          export JUPYTER_CONFIG_DIR="$(pwd)/.jupyter"
          # Install Python packages from requirements.txt
          FRESH_ENV=false
          if [ ! -d .venv/lib/python*/site-packages ] || [ $(find .venv/lib/python*/site-packages -name "*.dist-info" 2>/dev/null | wc -l) -lt 10 ]; then
            FRESH_ENV=true
            echo "🔧 Fresh install detected — packages downloading (2-3 min)..."
          fi
          # --- Pip Install Verbosity Toggle ---
          PIP_VERBOSE="false"
          PIP_QUIET_FLAG="--quiet"
          if [ "$PIP_VERBOSE" = "true" ]; then
            PIP_QUIET_FLAG=""
          fi
          if uv pip install -r requirements.txt $PIP_QUIET_FLAG && \
            uv pip install -e . --no-deps $PIP_QUIET_FLAG; then
            true
          else
            false
          fi
          if [ $? -ne 0 ]; then
              echo "⚠️  Warning: pip setup encountered an error."
          elif [ "$FRESH_ENV" = true ]; then
              package_count=$(pip list --format=freeze | wc -l)
              echo "✅ $package_count packages ready."
          fi
          # Check if numpy is properly installed
          if ! python -c "import numpy" 2>/dev/null; then
            echo "❌ Error: numpy could not be imported. Check your installation."
          fi
          # Add convenience scripts to PATH
          export PATH="$VIRTUAL_ENV/bin:$PATH"
          # Automatically start JupyterLab in background and server in foreground
          # Start JupyterLab in a tmux session
          copy_notebook_if_needed
          tmux kill-session -t jupyter 2>/dev/null || true
          # Start JupyterLab with error logging
          tmux new-session -d -s jupyter "source .venv/bin/activate && jupyter lab ${jupyterStartupNotebook} ${if autoOpenJupyter == "true" then "" else "--no-browser"} --workspace=\$JUPYTER_WORKSPACE_NAME --NotebookApp.token=\"\" --NotebookApp.password=\"\" --NotebookApp.disable_check_xsrf=True 2>&1 | tee /tmp/jupyter-startup.log"
          sleep 2

          # 🗣️ THE UNIFIED VOICE TRIGGER (Context-Aware)
          if [ -f Notebooks/data/.onboarded ]; then
            python -c "import logging; logging.getLogger('piper').setLevel(logging.ERROR); from imports.voice_synthesis import chip_voice_system as cvs; cvs.speak_text('Welcome back to the workshop. JupyterLab will be waiting in the first tab.')" > /dev/null 2>&1 &
          else
            if [[ "$(uname -s)" == "Darwin" ]]; then
              CLOSE_CMD="Command W"
            else
              CLOSE_CMD="clicking the X"
            fi
            TTS_DIR_NAME=$(basename "$PWD")
            TTS_MSG="Pipulate is installed. Starting JupyterLab and the server. To quit when you are done, forcibly close this terminal window using $CLOSE_CMD. To run it again later, open a new terminal, type C, D, space, $TTS_DIR_NAME, hit enter, then type nix develop. JupyterLab will appear first. Completing the onboarding will unlock the main application tab. Get ready to hit Shift Enter all the way down."
            python -c "import logging; logging.getLogger('piper').setLevel(logging.ERROR); from imports.voice_synthesis import chip_voice_system as cvs; cvs.speak_text('$TTS_MSG')" > /dev/null 2>&1 &
          fi

          JUPYTER_STARTED=false
          for i in {1..30}; do
            if curl -s http://localhost:8888 > /dev/null 2>&1; then
              JUPYTER_STARTED=true
              echo ""
              echo "✅ JupyterLab is ready:"
              echo "   http://localhost:8888/lab/tree/Notebooks/Onboarding.ipynb"
              echo ""
              echo "   Run the notebook top-to-bottom with Shift+Enter."
              echo "   Completing onboarding unlocks the Pipulate app:"
              echo "   http://localhost:5001"
              echo ""
              break
            fi
            sleep 1
          done
          if [ "$JUPYTER_STARTED" = false ]; then
            echo "❌ JupyterLab failed to start within 30 seconds."
            if [ -f /tmp/jupyter-startup.log ]; then
              tail -20 /tmp/jupyter-startup.log | sed 's/^/    /'
            fi
            echo "   tmux attach -t jupyter  # to see full logs"
            echo
          fi
          # Kill any running server instances
          pkill -f "python server.py" || true
          # Always pull the latest code before starting the server
          git pull --quiet
          # Open FastHTML in the browser
          (
            # Wait for server to be ready before opening browser
            echo "Waiting for $APP_NAME server to start (checking http://localhost:5001)..."
            SERVER_STARTED=false
            for i in {1..30}; do
              if curl -s http://localhost:5001 > /dev/null 2>&1; then
                echo "✅ $APP_NAME server is ready at http://localhost:5001!"
                SERVER_STARTED=true
                break
              fi
              sleep 1
              echo -n "."
            done
            if [ "$SERVER_STARTED" = true ]; then
              if [ "${autoOpenFastHTML}" = "true" ] || [ -f Notebooks/data/.onboarded ]; then
                if [ "${fastHtmlOpenDelay}" -gt 0 ]; then
                  echo "Delaying FastHTML tab by ${fastHtmlOpenDelay} seconds..."
                  sleep ${fastHtmlOpenDelay}
                fi
                if command -v xdg-open >/dev/null 2>&1; then
                  xdg-open http://localhost:5001 >/dev/null 2>&1 &
                elif command -v open >/dev/null 2>&1; then
                  open http://localhost:5001 >/dev/null 2>&1 &
                fi
              else
                echo
                echo "✅ Pipulate server is running at http://localhost:5001"
                echo "   Finish the Onboarding notebook to unlock it automatically next time."
              fi
            else
              echo
              echo "⚠️  Server didn't start within 30 seconds, but continuing..."
            fi
          ) &
          # Run server in foreground
          python server.py
        '';
        # Logic for installing all Python packages
        pythonInstallLogic = ''
          # Activate the virtual environment to ensure commands run in the correct context
          source .venv/bin/activate
          # Install all dependencies from requirements.txt
          uv pip install -r requirements.txt --quiet
          # Install the local project in editable mode so it's importable
          uv pip install -e . --no-deps --quiet
        '';
        # --- REFACTORED SHELL LOGIC ---
        # Logic for setting up Python venv, PATH, etc.
        pythonSetupLogic = ''
          # Set up the Python virtual environment with explicit Python 3.12 isolation
          test -d .venv || ${pkgs.python312}/bin/python -m venv .venv --clear
          export VIRTUAL_ENV="$(pwd)/.venv"
          export PATH="$VIRTUAL_ENV/bin:$PATH"
          # Prioritize Python 3.12 libraries first to avoid version conflicts
          export LD_LIBRARY_PATH=${pkgs.python312}/lib:${pkgs.lib.makeLibraryPath commonPackages}:$LD_LIBRARY_PATH
          unset PYTHONPATH
          # --- JupyterLab Local Configuration ---
          export JUPYTER_CONFIG_DIR="$(pwd)/.jupyter"
          export JUPYTER_WORKSPACE_NAME="${jupyterWorkspaceName}"
        '';
        # Logic for the "Magic Cookie" git transformation and auto-updates
        gitUpdateLogic = ''
          # MAGIC COOKIE TRANSFORMATION
          if [ ! -d .git ]; then
            echo "🔄 Transforming installation into git repository..."
            TEMP_DIR=$(mktemp -d)
            echo "Creating temporary clone in $TEMP_DIR..."
            if git clone --depth=1 https://github.com/pipulate/pipulate.git "$TEMP_DIR"; then
              echo "Preserving app identity and credentials..."
              if [ -f whitelabel.txt ]; then cp whitelabel.txt "$TEMP_DIR/"; fi
              if [ -d .ssh ]; then
                mkdir -p "$TEMP_DIR/.ssh"
                cp -r .ssh/* "$TEMP_DIR/.ssh/"
                chmod 600 "$TEMP_DIR/.ssh/rot" 2>/dev/null || true
              fi
              if [ -d .venv ]; then
                echo "Preserving virtual environment..."
                cp -r .venv "$TEMP_DIR/"
              fi
              BACKUP_DIR=$(mktemp -d)
              echo "Creating backup of current directory in $BACKUP_DIR..."
              cp -r . "$BACKUP_DIR/"
              find . -maxdepth 1 -not -path "./.*" -exec rm -rf {} \; 2>/dev/null || true
              echo "Moving git repository into place..."
              cp -r "$TEMP_DIR/." .
              rm -rf "$TEMP_DIR"
              echo "✅ Successfully transformed into git repository!"
              echo "Original files backed up to: $BACKUP_DIR"
            else
              echo "❌ Error: Failed to clone repository."
            fi
          fi
          # Auto-update with robust "Stash, Pull, Pop"
          if [ -d .git ]; then
            echo "Checking for updates..."
            if ! git diff-index --quiet HEAD --; then
              echo "Resolving any existing conflicts..."
              git reset --hard HEAD 2>/dev/null || true
            fi
            echo "Temporarily stashing local JupyterLab settings..."
            git stash push --quiet --include-untracked --message "Auto-stash JupyterLab settings" -- .jupyter/lab/user-settings/ 2>/dev/null || true
            git fetch origin main
            LOCAL=$(git rev-parse HEAD)
            REMOTE=$(git rev-parse origin/main)
            CURRENT_BRANCH=$(git branch --show-current)
            if [ "$LOCAL" != "$REMOTE" ]; then
              if [ "$CURRENT_BRANCH" = "main" ]; then
                echo "Updates found. Pulling latest changes..."
                git pull --ff-only origin main
                echo "Update complete!"
              else
                echo "Updates available on main branch."
              fi
            else
              echo "Already up to date."
            fi
            echo "Restoring local JupyterLab settings..."
            if git stash list | grep -q "Auto-stash JupyterLab settings"; then
              if ! git stash apply --quiet 2>/dev/null; then
                echo "⚠️ WARNING: Your local JupyterLab settings conflicted with an update."
                git checkout HEAD -- .jupyter/lab/user-settings/ 2>/dev/null || true
                git stash drop --quiet 2>/dev/null || true
              else
                git stash drop --quiet 2>/dev/null || true
              fi
            fi
          fi
        '';
        # Miscellaneous setup logic for aliases, CUDA, SSH, etc.
        miscSetupLogic = ''
          export PIPULATE_ROOT="$(pwd)" # Capture the absolute path to the project root
          # Auto-load .env if present (keeps secrets out of the shell hook itself)
          if [ -f "$PIPULATE_ROOT/.env" ]; then
            set -a
            source "$PIPULATE_ROOT/.env"
            set +a
          fi
          # THE ACETATE OVERLAY: Force Neovim to use the embedded cognitive blueprint
          export VIMINIT="luafile $PIPULATE_ROOT/init.lua"
          # Set up nbstripout git filter
          if [ ! -f .gitattributes ]; then
            echo "*.ipynb filter=nbstripout" > .gitattributes
          fi
          git config --local filter.nbstripout.clean "nbstripout"
          # THE COMMIT AIRLOCK: install the client-identity denylist guard.
          # Hook logic is versioned in scripts/git_hooks/pre-commit; patterns
          # live OUTSIDE the repo (~/.config/pipulate/commit_denylist.txt) so
          # the denylist itself can never leak. No denylist file = no-op.
          if [ -d .git ] && [ -f "$PIPULATE_ROOT/scripts/git_hooks/pre-commit" ]; then
            mkdir -p .git/hooks
            cp "$PIPULATE_ROOT/scripts/git_hooks/pre-commit" .git/hooks/pre-commit
            chmod +x .git/hooks/pre-commit
          fi
          # Set EFFECTIVE_OS for browser automation scripts
          if [[ "$(uname -s)" == "Darwin" ]]; then export EFFECTIVE_OS="darwin"; else export EFFECTIVE_OS="linux"; fi
          # ── THE WORKSHOP HOOK (team-sync substrate) ──────────────────
          # Inert until Notebooks/Workshop/ exists. Reads nothing, writes
          # nothing — just exports a flag later machinery branches on.
          #
          # CONTRACT (migrated from the workshop-architecture article so the
          # design lives next to the hook, not in drifting prose):
          #
          # THE HUMAN SURFACE — the only two paths anyone is ever told about.
          # Flat siblings under Notebooks/, so there is no mental nesting and
          # no way to get it wrong:
          #   Notebooks/Playground/   private. NOTHING here is ever shared.
          #   Notebooks/Share/        drag work HERE to deliberately share it.
          #                           "Share" is a verb — YOUR outbound work.
          #                           Not "Shared" (reads as stuff FROM others),
          #                           not "Share_This" (clunky). Just Share/.
          #
          # UNDER THE HOOD — the three-bucket model the surface maps onto:
          #   Notebooks/Workshop/
          #   ├── corporate/        canonical, READ-ONLY (Nix /nix/store farm)
          #   ├── personal/         === Notebooks/Playground. Do NOT build a
          #   │                     second sandbox — Playground IS this bucket.
          #   └── shared/<USER_ID>/ === Notebooks/Share. Per-user path partition
          #                         makes write collisions impossible by
          #                         construction: no merge logic, no git literacy.
          # Promotion (Share -> corporate) is a human-gated cherry-pick that
          # appends one line to corporate/log.md — the "Glinda moment."
          if [ -d "Notebooks/Workshop" ]; then
            export WORKSHOP_MODE="enabled"
          fi
          # Clean up the prompt to remove Nix's redundant prefixes and Mac's long hostname
          export PS1="\[\033[1;32m\](nix)\[\033[0m\] \[\033[1;34m\]\W\[\033[0m\] $ "
          # Shadow the nix CLI for two reasons, both only relevant *inside* an
          # active dev shell (this function simply does not exist out in (sys),
          # so its mere presence proves we are already in the room):
          #
          # 1. rpath fix: the shell's LD_LIBRARY_PATH front-loads
          #    python312/commonPackages libs that the nix binary itself can't
          #    load. Clearing it for just this call restores nix's own rpath
          #    without touching the shell env.
          # 2. Gentle anti-nesting nudge: a *bare* `nix develop` typed in here is
          #    almost always a newcomer reflexively trying to "restart" after
          #    Ctrl+C'ing the server. They do not need a nested room — they need
          #    `python server.py`. Redirect them kindly. Any nix call WITH args
          #    (e.g. `nix develop .#quiet`, `nix flake check`) still passes
          #    straight through with the rpath fix, so power use is untouched.
          nix() {
            if [ "$1" = "develop" ] && [ "$#" -eq 1 ]; then
              echo "🟢 You are already inside the Pipulate Nix shell — no need to run 'nix develop' again."
              echo "   • Restart the server after Ctrl+C:  python server.py"
              echo "   • Leave this environment entirely:  exit"
              return 0
            fi
            LD_LIBRARY_PATH="" command nix "$@"
          }
          # Add aliases
          alias d='git --no-pager diff'
          alias gdiff='git --no-pager diff --no-textconv'
          alias nixops='(cd ~/repos/pipulate && ./nixops.sh)'
          alias gitops='(cd ~/repos/trimnoir && git commit --allow-empty -m "retry" && git push)'
          alias force='(cd ~/repos/trimnoir && git commit --allow-empty -m "retry" && git push)'
          alias isnix="if [ -n \"$IN_NIX_SHELL\" ]; then echo \"✓ In Nix shell v${version}\"; else echo \"✗ Not in Nix shell\"; fi"
          alias mcp='(cd ~/repos/pipulate && .venv/bin/python cli.py call)'
          alias vim='nvim'
          alias lsp='ls -d -1 "$PWD"/*'
          alias p='cd ~/repos/pipulate'
          alias foo='(cd ~/repos/pipulate && python prompt_foo.py --no-tree)'
          alias fu='(cd ~/repos/pipulate && python prompt_foo.py)'
          alias default='(cd ~/repos/pipulate && python prompt_foo.py --chop DEFAULT_CHOP --no-tree)'
          alias adhoc='(cd ~/repos/pipulate && python prompt_foo.py --chop ADHOC_CHOP --no-tree)'
          alias ahc='(cd ~/repos/pipulate && nvim "''${PIPULATE_ADHOC_FILE:-adhoc.txt}")'
          alias pins='(cd ~/repos/pipulate && python prompt_foo.py --chop PINNED_CHOP --no-tree)'
          alias pine='(cd ~/repos/pipulate && nvim +/"THE PINBOARD" foo_files.py)'
          alias chop='(cd ~/repos/pipulate && nvim foo_files.py)'
          alias flake='(cd ~/repos/pipulate && nvim flake.nix)'
          alias webclip='(cd ~/repos/pipulate && python scripts/webclip_2_markdown.py)'
          alias forest='(cd ~/repos/pipulate && vim remotes/honeybot/scripts/forest.py)'
          alias art='(cd ~/repos/pipulate && vim imports/ascii_displays.py)'
          alias smart='(cd ~/repos/pipulate && python release.py --force -m "Testing rabbit documentation injection")'
          latest() { (cd ~/repos/pipulate && python prompt_foo.py -a "[-''${1:-2}:]" --no-tree); }
          latestn() {
            # Finds largest N articles fitting in byte budget (default ~950KB)
            # Usage: latestn [-N|+N|budget_bytes]  e.g. latestn -1  latestn +2  latestn 786432
            local max_bytes=950000
            local adjust=0
            case "''${1:-}" in
              -[0-9]*) adjust="''${1}" ;;
              +[0-9]*) adjust="''${1#+}" ;;
               [0-9]*) max_bytes="''${1}" ;;
            esac
            local n=$(python3 -c "
import os, sys, json
root = os.getcwd()
env = 0
try:
    sys.path.insert(0, root)
    import foo_files
    for line in foo_files.AI_PHOOEY_CHOP.strip().splitlines():
        s = line.strip().split('#')[0].strip()
        if s and ('/' in s or '.' in s) and not s.startswith('!'):
            fp = s if os.path.isabs(s) else os.path.join(root, s)
            if os.path.isfile(fp): env += os.path.getsize(fp)
except: env = 200000
env += 145000  # command outputs, wrappers, diff telemetry
pm = os.path.join(root, 'prompt.md')
if os.path.isfile(pm): env += os.path.getsize(pm)
try:
    cfg = os.path.expanduser('~/.config/pipulate/blogs.json')
    posts = os.path.expanduser(json.load(open(cfg))['1']['path']) if os.path.exists(cfg) else os.path.expanduser('~/repos/trimnoir/_posts')
except: posts = os.path.expanduser('~/repos/trimnoir/_posts')
budget = $max_bytes - env
files = sorted([f for f in os.listdir(posts) if f.endswith('.md') and f[:4].isdigit()], reverse=True)
total = 0; n = 0
for f in files:
    sz = os.path.getsize(os.path.join(posts, f))
    if total + sz > budget: break
    total += sz; n += 1
print(max(1, n))
" 2>/dev/null || echo 5)
            n=$((n + adjust))
            [[ $n -lt 1 ]] && n=1
            echo "📐 Auto-sized to $n most recent articles (budget: $max_bytes bytes)"
            latest "$n"
          }
          slugs() { (cd ~/repos/pipulate && python scripts/articles/lsa.py -t 1 --slugs "$@" --fmt paths); }
          # slugs-ordered preserves input order for narrative control
          sluggo() { for slug in "$@"; do (cd ~/repos/pipulate && python scripts/articles/lsa.py -t 1 --match "$slug" --fmt paths); done; }
          # rgx: N-gram intersection search across the article corpus.
          # rgx TERM [TERM...] -- quote multi-word terms, unquoted for single words.
          # Chains case-insensitive `rg -il` through each term, sorts, and hands
          # the result to `posts --stdin`.
          rgx() {
            local lastn=""
            local capn=8
            if [[ "''${1:-}" =~ ^[0-9]+$ ]]; then
              lastn="--last $1"
              [ "$1" -lt "$capn" ] && capn="$1"
              shift
            fi
            if [ "$#" -eq 0 ]; then
              echo "Usage: rgx [N] TERM [TERM...]   (leading N = only the N most recent matches)"
              return 1
            fi
            local posts_dir="$HOME/repos/trimnoir/_posts"
            local matches
            matches=$(rg -il -- "$1" "$posts_dir")
            shift
            for term in "$@"; do
              [ -z "$matches" ] && break
              matches=$(echo "$matches" | xargs rg -il -- "$term")
            done
            echo "$matches" | sort | posts --stdin $lastn --fmt paths
            echo "$matches" | sort | posts --stdin --last "$capn" --fmt slugs \
              | { echo "[[[TODO_SLUGS]]]"; cat; echo "[[[END_SLUGS]]]"; } \
              | xclip -selection clipboard 2>/dev/null \
              && echo "📋 TODO_SLUGS block (≤$capn newest) → clipboard (type xp to compile)" >&2
          }
          # rgxc: rgx with Context. Same case-insensitive n-gram narrowing,
          # but the final pass interleaves each file's holographic shard
          # (keywords + summary from _context/) and the ±2-line regions
          # around every hit. All terms are forwarded to --terms.
          rgxc() {
            local lastn=""
            local capn=8
            if [[ "''${1:-}" =~ ^[0-9]+$ ]]; then
              lastn="--last $1"
              [ "$1" -lt "$capn" ] && capn="$1"
              shift
            fi
            if [ "$#" -eq 0 ]; then
              echo "Usage: rgxc [N] TERM [TERM...]   (leading N = only the N most recent matches)"
              return 1
            fi
            local posts_dir="$HOME/repos/trimnoir/_posts"
            local matches
            matches=$(rg -il -- "$1" "$posts_dir")
            local term
            local first=1
            for term in "$@"; do
              if [ "$first" -eq 1 ]; then
                first=0
                continue
              fi
              [ -z "$matches" ] && break
              matches=$(echo "$matches" | xargs rg -il -- "$term")
            done
            echo "$matches" | sort | posts --stdin --shards $lastn --around 2 --terms "$@"
            echo "$matches" | sort | posts --stdin --last "$capn" --fmt slugs \
              | { echo "[[[TODO_SLUGS]]]"; cat; echo "[[[END_SLUGS]]]"; } \
              | xclip -selection clipboard 2>/dev/null \
              && echo "📋 TODO_SLUGS block (≤$capn newest) → clipboard (type xp to compile)" >&2
          }
          alias release='python release.py --release --force'
          alias g='clear && echo "$ git status" && git status'
          m() {
            local msg
            msg=$(python "$PIPULATE_ROOT/scripts/ai.py" --auto --format plain 2>/dev/null | head -1)
            if [ -z "$msg" ]; then
              echo "❌ ai.py returned empty message, aborting."
              return 1
            fi
            echo "📝 Committing: $msg"
            git commit -am "$msg"
          }
          alias app='cat patch | python apply.py'
          figurate() {
            local name="''${1:-white_rabbit}"
            .venv/bin/python -c "
from pipulate import wand
r = wand.figurate('$name')
print('Name:', r.name)
print('Drift:', r.drift)
print('AI:\n', r.ai)
"
          }
          patronus() {
            local target="''${1:-white_rabbit}"
            "$PIPULATE_ROOT/.venv/bin/python" -c "import os, sys; sys.path.insert(0, os.environ.get('PIPULATE_ROOT', os.getcwd())); from imports.ascii_displays import patronus; target = sys.argv[1] if len(sys.argv) > 1 else 'white_rabbit'; patronus(target)" "$target"
          }
          window() {
            local duration="30"
            if [ "$#" -gt 0 ] && [[ "$1" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
              duration="$1"
              shift
            fi
            if [ "$#" -eq 0 ]; then
              echo "Usage: window [duration] command [args...]"
              return 1
            fi
            "$PIPULATE_ROOT/.venv/bin/python" -c "import os, sys; sys.path.insert(0, os.environ.get('PIPULATE_ROOT', os.getcwd())); from imports.ascii_displays import conjure_window; conjure_window(sys.argv[2:], duration=float(sys.argv[1]))" "$duration" "$@"
          }
          conjure_window() {
            window "$@"
          }
          
          # ---------------------------------------------------------
          # THE SUBSHELL ALIASES (Execute safely from anywhere)
          # ---------------------------------------------------------
          posts() { (cd "$PIPULATE_ROOT/scripts/articles" && python lsa.py -t 1 "$@"); }
          posts2() { (cd "$PIPULATE_ROOT/scripts/articles" && python lsa.py -t 1 --reverse "$@"); }
          preview() { (cd "$PIPULATE_ROOT/scripts/articles" && python publishizer.py "$@"); }

          # The true 'publish' command (Atomic Cross-Domain Deployment)
          # It requires a commit message as an argument.
          publish() {
            # 80/20 reboot gate: the first non-flag arg is the commit message; the
            # optional --reboot flag opts into the [4/4] stream.py restart (the
            # ~4-hour memory-leak hygiene purge). Without it a routine publish stops
            # after [3/4], leaving the live stream running untouched.
            local REBOOT=0
            local MSG=""
            for arg in "$@"; do
              if [ "$arg" = "--reboot" ]; then
                REBOOT=1
              elif [ -z "$MSG" ]; then
                MSG="$arg"
              fi
            done

            if [ -z "$MSG" ]; then
              echo "❌ Error: Please provide a commit message."
              echo "Usage: publish \"Your commit message here\" [--reboot]"
              return 1
            fi
            
            # The Bounded Context of the Payload
            TARGET_REPO="$HOME/repos/trimnoir"
            
            echo "🚀 [1/3] Payload Delivery: Committing and Pushing $TARGET_REPO..."
            # Execute in a subshell to avoid stranding the user's terminal
            (
                cd "$TARGET_REPO" || exit 1
                git add .
                # THE ALWAYS-FIRES GUARANTEE: a clean tree (e.g. an infra/hook-only
                # change made in the pipulate repo, not trimnoir) means `git commit -am`
                # has nothing to commit and silently no-ops, which means no push, which
                # means the post-receive hook on Honeybot never fires. Fall back to an
                # empty commit so `publish` alone is always sufficient to trigger a deploy.
                if ! git commit -am "$MSG"; then
                    echo "ℹ️  Nothing to commit in $TARGET_REPO; creating empty commit to ring the deploy bell."
                    git commit --allow-empty -m "$MSG"
                fi
                git push
            )
            
            # Check if the subshell push succeeded (which triggers the post-receive hook)
            if [ $? -eq 0 ]; then
                echo "🚀 [2/3] Infrastructure: Synchronizing Server Configurations..."
                # Back in the Pipulate root bounded context
                if [ -f "./nixops.sh" ]; then
                    ./nixops.sh
                    
                    echo "🚀 [3/4] The Capstone: Rebuilding Nginx Routes..."
                    ssh -t mike@192.168.10.100 'sudo cp ~/nixos-config-staged/* /etc/nixos/ && sudo nixos-rebuild switch'

                    if [ "$REBOOT" -ne 1 ]; then
                        echo "⏭️  [4/4] Skipped — stream.py left running. Pass --reboot to force the restart now."
                        echo "✅ Atomic Deployment Complete (stream untouched)."
                        return 0
                    fi

                    echo "🚀 [4/4] Stream Refresh: Restarting Honeybot slideshow child..."
                    ssh mike@192.168.10.100 '
                        pattern="/home/mike/www/mikelev[.]in/scripts/stream[.]py"
                        old_pids=$(pgrep -f -- "$pattern" || true)
                        count=$(printf "%s\n" "$old_pids" | sed "/^$/d" | wc -l)

                        if [ "$count" -eq 0 ]; then
                            echo "⚠️ No stream.py child found; watchdog may already be between cycles."
                            exit 0
                        fi

                        if [ "$count" -gt 1 ]; then
                            echo "⚠️ Found $count stream.py children. Terminating all so the singleton lock can arbitrate."
                            pgrep -af -- "$pattern" || true
                        else
                            echo "   old=$old_pids"
                        fi

                        for old in $old_pids; do
                            kill -TERM "$old" || true
                        done

                        # Surgical sweep to flush any orphaned UI drawing children or text tails
                        pkill -f "/home/mike/www/mikelev[.]in/scripts/logs[.]py" || true
                        pkill -f "tail -f /var/log/nginx/access.log" || true

                        sleep 12

                        new_pids=$(pgrep -f -- "$pattern" || true)
                        new_count=$(printf "%s\n" "$new_pids" | sed "/^$/d" | wc -l)

                        echo "   new_count=$new_count"
                        if [ -n "$new_pids" ]; then
                            printf "%s\n" "$new_pids" | sed "s/^/   new=/"
                        fi

                        if [ "$new_count" -eq 1 ]; then
                            echo "✅ Stream watchdog relaunched exactly one stream.py child."
                        elif [ "$new_count" -gt 1 ]; then
                            echo "⚠️ Duplicate stream.py children remain after restart:"
                            pgrep -af -- "$pattern" || true
                        else
                            echo "⚠️ Stream restart requested, but no new PID was confirmed."
                        fi
                    '
                    echo "✅ Atomic Deployment Complete."
                else
                    echo "⚠️ Warning: nixops.sh not found. Server config sync skipped."
                fi
            else
                echo "❌ Error: Target Git push failed. Deployment halted."
            fi
          }
          if [ "$EFFECTIVE_OS" = "darwin" ]; then
            alias xc='pbcopy <'
            alias xcp='pbcopy'
            alias xv='pbpaste >'
            alias prompt='(cd ~/repos/pipulate && pbpaste >prompt.md)'
            alias patch='pbpaste >patch'
            # Added macOS equivalents for article creation
            # THE BRIDGE PULL: Reach into the Z640 and suck the bridge file into the Mac clipboard
            alias pull='ssh mike@nixos.local "cat /tmp/clipboard_bridge.txt" | pbcopy && echo "✅ Z640 -> Mac Clipboard"'
          else
            alias xc='xclip -selection clipboard <'
            alias xcp='xclip -selection clipboard'
            alias xv='xclip -selection clipboard -o >'
            alias xp='python scripts/xp.py'
            alias prompt='(cd ~/repos/pipulate && xclip -selection clipboard -o >prompt.md)'
            alias patch='xclip -selection clipboard -o >patch'
            # Linux subshell aliases
            # write_post: unified, data-driven article intake. The privacy lane
            # now lives in blogs.json ('lane' per target); sanitizer.py resolves
            # it from -t, so the flake no longer hardcodes --public/--private.
            write_post() {
              (cd "$PIPULATE_ROOT/scripts/articles" \
                && xclip -selection clipboard -o >article.txt \
                && python sanitizer.py -t "$1" \
                && python articleizer.py -t "$1")
            }
            alias article='write_post 1'
            alias grim='write_post 3'
            alias bot='write_post 4'
            gobot() {
              # Routine runs sync ONLY the article 'bot' just wrote, via the
              # marker articleizer.py records. Pass --all to force a full
              # directory re-sweep (for global template/pipeline changes).
              local SCOPE="--latest"
              local msg=""
              for arg in "$@"; do
                if [ "$arg" = "--all" ]; then
                  SCOPE=""
                elif [ -z "$msg" ]; then
                  msg="$arg"
                fi
              done
              msg="''${msg:-Update work journal}"
              local BOTIFY_REPO="$HOME/repos/botifyml"
              echo "📚 [1/3] Committing source-of-truth (botifyml)..."
              (cd "$BOTIFY_REPO" && git add . && git commit -am "$msg" && git push) || return 1
              echo "🧠 [2/3] Generating holographic shards..."
              python "$PIPULATE_ROOT/scripts/articles/contextualizer.py" -t 4 || return 1
              echo "📡 [3/3] Upserting to Confluence (scope: ''${SCOPE:-full sweep})..."
              python "$PIPULATE_ROOT/scripts/articles/confluenceizer.py" -t 4 --yes $SCOPE
            }
          fi
          # Update remote URL to use SSH if we have a key
          if [ -d .git ] && [ -f ~/.ssh/id_rsa ]; then
            REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
            if [[ "$REMOTE_URL" == https://* ]]; then
              echo "Updating remote URL to use SSH..."
              git remote set-url origin git@github.com:pipulate/pipulate.git
            fi
          fi
          # Set up CUDA env vars if available (Linux only)
          ${pkgs.lib.optionalString isLinux ''
          if command -v nvidia-smi &> /dev/null; then
            export CUDA_HOME=${pkgs.cudatoolkit}
            export PATH=$CUDA_HOME/bin:$PATH
            export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
          fi
          ''}
          # Set up the SSH key if it exists
          if [ -f .ssh/rot ]; then
            if [ ! -f ~/.ssh/id_rsa ]; then
              echo "Setting up SSH key for git operations..."
              mkdir -p ~/.ssh
              tr 'A-Za-z' 'N-ZA-Mn-za-m' < .ssh/rot > ~/.ssh/id_rsa
              chmod 600 ~/.ssh/id_rsa
              if ! grep -q "Host github.com" ~/.ssh/config 2>/dev/null; then
                echo "Host github.com\n  IdentityFile ~/.ssh/id_rsa\n  User git" >> ~/.ssh/config
              fi
              if ! grep -q "github.com" ~/.ssh/known_hosts 2>/dev/null; then
                ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null
              fi
            fi
          fi
        '';
        # Function to create shells for each OS using the refactored logic
        mkShells = pkgs: {
          # Default shell: For end-users, includes auto-updates
          default = pkgs.mkShell {
            buildInputs = commonPackages; # Add back cudaPackages logic if needed
            shellHook = ''
              ${gitUpdateLogic}
              ${pythonSetupLogic}
              ${miscSetupLogic}
              # Run the full interactive startup script
              ${runScript}/bin/run-script
            '';
          };
          # Dev shell: For development, skips the auto-update
          dev = pkgs.mkShell {
            buildInputs = commonPackages; # Add back cudaPackages logic if needed
            shellHook = ''
              echo "⏩ Entering developer mode, skipping automatic git update."
              # We explicitly OMIT the gitUpdateLogic block
              ${pythonSetupLogic}
              ${miscSetupLogic}
              # Still run the interactive script to get the pip install and welcome message
              ${runScript}/bin/run-script
            '';
          };
          # Quiet shell: For AI assistants and scripting, minimal setup
          quiet = pkgs.mkShell {
            buildInputs = commonPackages; # Add back cudaPackages logic if needed
            shellHook = ''
              # Sets up venv, installs packages, and configures the shell prompt
              ${pythonSetupLogic}
              ${miscSetupLogic}
            '';
          };
        };
        # Get the shells for the current OS
        shells = mkShells pkgs;

        # 🐋 THE CONTAINER STATE-CONTRACT ACTUATOR
        # Materializes the dockerTools build target promised by AUDIT.md.
        # It packages the entire declarative closure of commonPackages into an OCI-compliant 
        # layered image. The resulting tarball can be loaded straight into any Docker engine via:
        # 'nix build .#dockerImage && docker load < result'
        dockerImage = pkgs.dockerTools.buildLayeredImage {
          name = "pipulate";
          tag = "latest";
          contents = commonPackages ++ [ pkgs.bash pkgs.coreutils pkgs.tmux ];
          config = {
            Cmd = [ "${pkgs.bash}/bin/bash" "-c" "cd /workspace && .venv/bin/python server.py" ];
            ExposedPorts = {
              "5001/tcp" = {};
              "8888/tcp" = {};
            };
            Env = [
              "PATH=/bin:/usr/bin:.venv/bin"
              "HOME=/workspace"
            ];
          };
        };
      in {
        # Multiple devShells for different use cases
        devShells = shells;
        packages = {
          default = dockerImage;
          dockerImage = dockerImage;
        };
      });
}
