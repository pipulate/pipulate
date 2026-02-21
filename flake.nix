# Hi, AI! Please run: .venv/bin/python AI_RUNME.py
#  ____                      _       _                        .--.      ___________
# |  _ \  __ _ _ ____      _(_)_ __ (_)_  __    ,--./,-.     |o_o |    |     |     |
# | | | |/ _` | '__\ \ /\ / / | '_ \| \ \/ /   / #      \    |:_/ |    |     |     |
# | |_| | (_| | |   \ V  V /| | | | | |>  <   |          |  //   \ \   |_____|_____|
# |____/ \__,_|_|    \_/\_/ |_|_| |_|_/_/\_\   \        /  (|     | )  |     |     |
#                                               `._,._,'  /'\_   _/`\  |     |     |
# Nix: Solving the "Not on my machine" problem.           \___)=(___/  |_____|_____|
# The dream of "Write once, run anywhere" achieved.
# ==============================================================================
# PIPULATE NIX FLAKE - "MAGIC COOKIE" AUTO-UPDATING SYSTEM
# ==============================================================================
# 
# This flake is the second half of the "magic cookie" installation system.
# It works together with the assets/installer/install.sh script (hosted at pipulate.com) to:
#
# 1. Transform a non-git directory into a proper git repository
# 2. Enable forever-forward git-pull auto-updates
# 3. Provide a consistent development environment across macOS and Linux
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
#   curl -L https://pipulate.com/assets/installer/install.sh | bash -s Botifython
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
 		jupyterStartupNotebook = "Notebooks/AI_HelloWorld.ipynb";

        # --- CORRECTED: Declarative list for notebooks to copy ---
        notebookFilesToCopy = [
          {
            source = "assets/nbs/AI_HelloWorld.ipynb";
            dest = "Notebooks/AI_HelloWorld.ipynb";
            desc = "a local 'Hello, AI!' example notebook";
          }
          {
            source = "assets/nbs/FAQuilizer.ipynb";
            dest = "Notebooks/FAQuilizer.ipynb";
            desc = "a local 'FAQuilizer' simple workflow";
          }
          {
            source = "assets/nbs/imports/faq_writer_sauce.py";
            dest = "Notebooks/imports/faq_writer_sauce.py";
            desc = "a local 'faq_writer_sauce.py' source of secret sauce";
          }
          {
            source = "assets/nbs/GAPalyzer.ipynb";
            dest = "Notebooks/GAPalyzer.ipynb";
            desc = "a local 'Competitor Gap Analyzer.' advanced workflow";
          }
          {
            source = "assets/nbs/imports/gap_analyzer_sauce.py";
            dest = "Notebooks/imports/gap_analyzer_sauce.py";
            desc = "a local 'gap_analyzer_sauce.py' source of secret sauce";
          }
          {
            source = "assets/nbs/URLinspector.ipynb";
            dest = "Notebooks/URLinspector.ipynb";
            desc = "a local 'URL-by-URL auditor.' derived from FAQuilizer";
          }
          {
            source = "assets/nbs/imports/url_inspect_sauce.py";
            dest = "Notebooks/imports/url_inspect_sauce.py";
            desc = "a local 'url_inspect_sauce.py' source of secret sauce";
          }
          {
            source = "assets/nbs/VIDeditor.ipynb";
            dest = "Notebooks/VIDeditor.ipynb";
            desc = "a local 'NoGooey Video Editor.'";
          }
          {
            source = "assets/nbs/imports/videditor_sauce.py.py";
            dest = "Notebooks/imports/videditor_sauce.py";
            desc = "a local 'videditor_sauce.py' source of secret sauce";
          }
#           {
#             source = "assets/nbs/imports/seo_gadget.py";
#             dest = "Notebooks/imports/seo_gadget.py";
#             desc = "a local 'seo_gadget.py' subprocess file";
#           }
        ];

        # Convert the Nix list to a string that Bash can loop over
        notebookFilesString = pkgs.lib.concatStringsSep "\n" (
          map (file: "${file.source};${file.dest};${file.desc}") notebookFilesToCopy
        );

        # Common packages that we want available in our environment
        # regardless of the operating system
        commonPackages = with pkgs; [
          sqlite                       # Ensures correct SQLite library is linked on macOS
          (python312.withPackages (ps: with ps; [
            pylint
            nbstripout
          ]))
          nbstripout
          figlet                       # For creating ASCII art welcome messages
          tmux                         # Terminal multiplexer for managing sessions
          zlib                         # Compression library for data compression
          git                          # Version control system for tracking changes
          curl                         # Command-line tool for transferring data with URLs
          wget                         # Utility for non-interactive download of files from the web
          cmake                        # Cross-platform build system generator
          htop                         # Interactive process viewer for Unix systems
          plantuml
          graphviz
          eza                          # A tree directory visualizer that uses .gitignore
        ] ++ (with pkgs; pkgs.lib.optionals isLinux [
          espeak-ng                    # Text-to-speech, Linux only
          sox                          # Sound processing, Linux only
          virtualenv
          gcc                          # GNU Compiler Collection for compiling C/C++ code
          stdenv.cc.cc.lib             # Standard C library for Linux systems
          chromium                     # Chromium browser for Selenium automation
          undetected-chromedriver
          xclip
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
          if [ -n "$IN_NIX_SHELL" ] || [[ "$PS1" == *"(nix)"* ]]; then 
            echo "✓ In Nix shell v${version} - you can run python server.py"
          else 
            echo "✗ Not in Nix shell - please run nix develop"
          fi
          echo "Welcome to the $PROPER_APP_NAME development environment on ${system}!"
          echo 
          # --- JupyterLab Local Configuration ---
          # Set env var for project-local JupyterLab configuration
          export JUPYTER_CONFIG_DIR="$(pwd)/.jupyter"
          echo "✓ JupyterLab configured for project-local settings."
          # Install Python packages from requirements.txt
          # This allows flexibility to use the latest PyPI packages
          # Note: This makes the environment less deterministic
          # Check if this is a fresh Python environment (after reset)
          FRESH_ENV=false
          if [ ! -d .venv/lib/python*/site-packages ] || [ $(find .venv/lib/python*/site-packages -name "*.dist-info" 2>/dev/null | wc -l) -lt 10 ]; then
            FRESH_ENV=true
            echo "🔧 Fresh Python environment detected - installing packages (this may take 2-3 minutes)..."
            echo "   This is normal on a fresh install or after using '🐍 Reset Python Environment' button."
          else
            echo "- Confirming pip packages..."
          fi
          # --- Pip Install Verbosity Toggle ---
          # Set to "true" to see detailed pip install output for debugging
          PIP_VERBOSE="false"
          PIP_QUIET_FLAG="--quiet"
          if [ "$PIP_VERBOSE" = "true" ]; then
            PIP_QUIET_FLAG=""
            echo "🔧 Pip verbose mode enabled."
          fi
          # Always keep pip installation quiet - no scary technical output for users
          if pip install --upgrade pip $PIP_QUIET_FLAG && \
            pip install -r requirements.txt $PIP_QUIET_FLAG && \
            pip install -e . --no-deps $PIP_QUIET_FLAG; then
            true  # Success case handled below
          else
            false  # Error case handled below
          fi
          if [ $? -eq 0 ]; then
              package_count=$(pip list --format=freeze | wc -l)
              if [ "$FRESH_ENV" = true ]; then
                echo "✅ Fresh Python environment build complete! $package_count packages installed."
              else
                echo "- Done. $package_count pip packages present."
              fi
          else
              echo "Warning: An error occurred during pip setup."
          fi
          # Check if numpy is properly installed
          if python -c "import numpy" 2>/dev/null; then
            echo "- numpy is importable (good to go!)"
            echo
            echo "Starting JupyterLab and $APP_NAME server automatically..."
            echo "Both will open in your browser..."
            echo
            echo "To view server logs: tmux attach -t server"
            echo "To view JupyterLab logs: tmux attach -t jupyter"
            echo "To stop all services: pkill tmux"
            echo "To restart all services: run-all"
            echo "To start only server: run-server"
            echo "To start only JupyterLab: run-jupyter"
          else
            echo "Error: numpy could not be imported. Check your installation."
          fi
          # Create convenience scripts for managing JupyterLab
          # Note: We've disabled token and password for easier access, especially in WSL environments
          cat << 'START_SCRIPT_EOF' > .venv/bin/start
          #!/bin/sh
          export JUPYTER_CONFIG_DIR="$(pwd)/.jupyter"
          export JUPYTER_WORKSPACE_NAME="pipulate-main"
          copy_notebook_if_needed
          echo "A JupyterLab tab will open in your default browser."
          tmux kill-session -t jupyter 2>/dev/null || echo "No tmux session named 'jupyter' is running."
          tmux new-session -d -s jupyter "source .venv/bin/activate && jupyter lab ${jupyterStartupNotebook} --workspace=\$JUPYTER_WORKSPACE_NAME --NotebookApp.token=\"\" --NotebookApp.password=\"\" --NotebookApp.disable_check_xsrf=True"
          echo "If no tab opens, visit http://localhost:8888/lab"
          echo "To view JupyterLab server: tmux attach -t jupyter"
          echo "To stop JupyterLab server: stop"
          START_SCRIPT_EOF
          chmod +x .venv/bin/start
          cat << 'STOP_SCRIPT_EOF' > .venv/bin/stop
          #!/bin/sh
          echo "Stopping tmux session 'jupyter'..."
          tmux kill-session -t jupyter 2>/dev/null || echo "No tmux session named 'jupyter' is running."
          echo "The tmux session 'jupyter' has been stopped."
          STOP_SCRIPT_EOF
          chmod +x .venv/bin/stop
          # Create a run-server script
          cat << 'SERVER_SCRIPT_EOF' > .venv/bin/run-server
          #!/bin/sh
          echo "Starting $APP_NAME server..."
          # Kill any running server instances first
          pkill -f "python server.py" || true
          # Always pull the latest code before starting the server
          echo "Pulling latest code updates..."
          git pull
          python server.py
          SERVER_SCRIPT_EOF
          chmod +x .venv/bin/run-server
          # Create a run-jupyter script
          cat << 'JUPYTER_SCRIPT_EOF' > .venv/bin/run-jupyter
          #!/bin/sh
          export JUPYTER_CONFIG_DIR="$(pwd)/.jupyter"
          export JUPYTER_WORKSPACE_NAME="pipulate-main"
          echo "Starting JupyterLab..."
          copy_notebook_if_needed
          # Kill existing jupyter tmux session
          tmux kill-session -t jupyter 2>/dev/null || true
          # Start JupyterLab
          tmux new-session -d -s jupyter "source .venv/bin/activate && jupyter lab ${jupyterStartupNotebook} --workspace=\$JUPYTER_WORKSPACE_NAME --NotebookApp.token=\"\" --NotebookApp.password=\"\" --NotebookApp.disable_check_xsrf=True"
          # Wait for JupyterLab to start
          echo "JupyterLab is starting..."
          for i in {1..30}; do
            if curl -s http://localhost:8888 > /dev/null; then
              echo "JupyterLab is ready!"
              break
            fi
            sleep 1
            echo -n "."
          done
          echo "JupyterLab started! View logs with: tmux attach -t jupyter"
          JUPYTER_SCRIPT_EOF
          chmod +x .venv/bin/run-jupyter
          # Create a run-all script to restart both servers
          cat << 'RUN_ALL_SCRIPT_EOF' > .venv/bin/run-all
          #!/bin/sh
          export JUPYTER_CONFIG_DIR="$(pwd)/.jupyter"
          export JUPYTER_WORKSPACE_NAME="pipulate-main"
          echo "JupyterLab will start in the background."
          copy_notebook_if_needed
          # Kill existing tmux sessions
          tmux kill-session -t jupyter 2>/dev/null || true
          # Kill any running server instances
          pkill -f "python server.py" || true
          # Start JupyterLab
          echo "Starting JupyterLab..."
          tmux new-session -d -s jupyter "source .venv/bin/activate && jupyter lab ${jupyterStartupNotebook} --workspace=\$JUPYTER_WORKSPACE_NAME --NotebookApp.token=\"\" --NotebookApp.password=\"\" --NotebookApp.disable_check_xsrf=True"
          # Wait for JupyterLab to start
          echo "JupyterLab is starting..."
          for i in {1..30}; do
            if curl -s http://localhost:8888 > /dev/null; then
              echo "JupyterLab is ready!"
              break
            fi
            sleep 1
            echo -n "."
          done
          echo "JupyterLab started in the background. View logs with: tmux attach -t jupyter"
          echo "Starting $APP_NAME server in the foreground..."
          # Always pull the latest code before starting the server
          echo "Pulling latest code updates..."
          git pull
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
              if command -v xdg-open >/dev/null 2>&1; then
                xdg-open http://localhost:5001 >/dev/null 2>&1 &
              elif command -v open >/dev/null 2>&1; then
                open http://localhost:5001 >/dev/null 2>&1 &
              fi
            else
              echo
              echo "⚠️  Server didn't start within 30 seconds, but continuing..."
            fi
          ) &
          # Run server in foreground
          python server.py
          RUN_ALL_SCRIPT_EOF
          chmod +x .venv/bin/run-all
          # Add convenience scripts to PATH
          export PATH="$VIRTUAL_ENV/bin:$PATH"
          # Automatically start JupyterLab in background and server in foreground
          # Start JupyterLab in a tmux session
          copy_notebook_if_needed
          tmux kill-session -t jupyter 2>/dev/null || true
          # Start JupyterLab with error logging
          echo "Starting JupyterLab..."
          tmux new-session -d -s jupyter "source .venv/bin/activate && jupyter lab ${jupyterStartupNotebook} --workspace=\$JUPYTER_WORKSPACE_NAME --NotebookApp.token=\"\" --NotebookApp.password=\"\" --NotebookApp.disable_check_xsrf=True 2>&1 | tee /tmp/jupyter-startup.log"
          # Wait for JupyterLab to start with better feedback
          echo "Waiting for JupyterLab to start (checking http://localhost:8888)..."
          JUPYTER_STARTED=false
          for i in {1..30}; do
            if curl -s http://localhost:8888 > /dev/null 2>&1; then
              echo "✅ JupyterLab is ready at http://localhost:8888!"
              JUPYTER_STARTED=true
              break
            fi
            sleep 1
            echo -n "."
          done
          # If JupyterLab didn't start, show the logs
          if [ "$JUPYTER_STARTED" = false ]; then
            echo
            echo "❌ JupyterLab failed to start within 30 seconds."
            echo "📋 Recent JupyterLab logs:"
            if [ -f /tmp/jupyter-startup.log ]; then
              tail -20 /tmp/jupyter-startup.log | sed 's/^/    /'
            fi
            echo "📋 To see full JupyterLab logs: tmux attach -t jupyter"
            echo "📋 To check if tmux session exists: tmux list-sessions"
            echo
          fi
          # Kill any running server instances
          pkill -f "python server.py" || true
          # Start the server in foreground
          echo "Starting $APP_NAME server in the foreground..."
          echo "Press Ctrl+C to stop the server."
          # Always pull the latest code before starting the server
          echo "Pulling latest code updates..."
          git pull
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
              if command -v xdg-open >/dev/null 2>&1; then
                xdg-open http://localhost:5001 >/dev/null 2>&1 &
              elif command -v open >/dev/null 2>&1; then
                open http://localhost:5001 >/dev/null 2>&1 &
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
          # Always upgrade pip first
          pip install --upgrade pip --quiet
          # Install all dependencies from requirements.txt
          pip install -r requirements.txt --quiet
          # Install the local project in editable mode so it's importable
          pip install -e . --no-deps --quiet
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
            if git clone --depth=1 https://github.com/miklevin/pipulate.git "$TEMP_DIR"; then
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
          # Set up nbstripout git filter
          if [ ! -f .gitattributes ]; then
            echo "*.ipynb filter=nbstripout" > .gitattributes
          fi
          git config --local filter.nbstripout.clean "nbstripout"
          # Set EFFECTIVE_OS for browser automation scripts
          if [[ "$(uname -s)" == "Darwin" ]]; then export EFFECTIVE_OS="darwin"; else export EFFECTIVE_OS="linux"; fi
          echo "INFO: EFFECTIVE_OS set to: $EFFECTIVE_OS"
          # Add aliases
          alias isnix="if [ -n \"$IN_NIX_SHELL\" ]; then echo \"✓ In Nix shell v${version}\"; else echo \"✗ Not in Nix shell\"; fi"
          export PS1="(nix) $PS1"
          alias release='.venv/bin/python helpers/release/publish.py'
          alias mcp='.venv/bin/python cli.py call'
          alias gdiff='git --no-pager diff --no-textconv'
          # Update remote URL to use SSH if we have a key
          if [ -d .git ] && [ -f ~/.ssh/id_rsa ]; then
            REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
            if [[ "$REMOTE_URL" == https://* ]]; then
              echo "Updating remote URL to use SSH..."
              git remote set-url origin git@github.com:miklevin/pipulate.git
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
              echo "Entering standard environment with auto-updates..."
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
      in {
        # Multiple devShells for different use cases
        devShells = shells;
      });
}
