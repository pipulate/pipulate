#!/usr/bin/env bash
# Pipulate Installer v1.1.0
# =========================
# 
# This installer uses a "magic cookie" approach to setup a git-based nix flake without 
# requiring git to be available on the host system initially.
#
# === WHY THIS APPROACH WORKS ===
# We want effectively the same path whether it's macOS or Linux (which might include Windows WSL)
# because the value proposition of nix is deterministic behavior solving the "not on my machine" 
# problem. The nix flake provides a normalized version of Linux that runs things identically 
# across all host OSes. The exceptions are exactly that, tiny edge-case areas where we need 
# to insert special handling logic for radical differences in the host OS or hardware, such 
# as taking advantage of CUDA on non-Windows environments and the `--impure` flag needed on macOS.
# We go out of our way to re-unite the paths in all other locations so there is no special 
# host OS handling on core script functionality.
#
# === THE "MAGIC COOKIE" APPROACH ===
# Nix flakes require a git repository to function properly. However, requiring users to have 
# git pre-installed creates a dependency we want to avoid. So instead:
#
# 1. This assets/installer/install.sh script is distributed via curl (highly reliable across systems)
# 2. We download a zip of the repo (more reliable than git clone on diverse systems)
# 3. We extract the zip and place a ROT13-encoded SSH key in the .ssh folder
# 4. We run `nix develop` which activates the flake
# 5. The flake itself handles converting the directory into a proper git repo
#
# This is called a "magic cookie" approach because we provide the initial "cookie" 
# (SSH key + zip contents) that the nix flake later uses to transform itself into 
# a proper git repository with auto-update capabilities.
#
# === IMPORTANT ===
# DO NOT MOVE GIT FUNCTIONALITY INTO THIS SCRIPT. This approach deliberately avoids
# requiring git during the initial setup phase for maximum compatibility across systems.
# The more robust approach is to let nix ensure git is available before attempting any
# git operations in the controlled nix environment.

# Detect shell compatibility - pipefail is bash-specific
if [ -z "${BASH_VERSION:-}" ]; then
    echo "❌ Error: This script requires bash but is being run with a different shell."
    echo "   On Windows WSL and some Linux systems, 'sh' points to dash instead of bash."
    echo ""
    echo "   Please run the installer with bash explicitly:"
    echo "   curl -L https://pipulate.com/assets/installer/install.sh | bash -s ${1:-pipulate}"
    echo ""
    echo "   Or if you have bash installed:"
    echo "   curl -L https://pipulate.com/assets/installer/install.sh | bash -s ${1:-pipulate}"
    echo ""
    exit 1
fi

# Strict mode (bash-specific features)
set -euo pipefail

# At the beginning, add argument handling
CUSTOM_NAME="${1:-pipulate}"  # Default to "pipulate" if no arg provided

# --- Configuration ---
REPO_USER="miklevin"
REPO_NAME="pipulate"
# Stable URL for the main branch ZIP
ZIP_URL="https://github.com/${REPO_USER}/${REPO_NAME}/archive/refs/heads/main.zip"
# Target directory name - use absolute path to avoid any confusion
TARGET_DIR="${HOME}/${CUSTOM_NAME}"
# Temporary directory for ZIP extraction
TMP_EXTRACT_DIR="${REPO_NAME}-main"
# URL for the ROT13 deploy key
KEY_URL="https://pipulate.com/key.rot"

# --- Helper Functions ---
check_command() {
  if ! command -v "$1" &> /dev/null; then
    echo "Error: Required command '$1' not found. Please install it."
    exit 1
  fi
}

print_separator() {
  echo "--------------------------------------------------------------"
}

# --- Setup Nix Develop Command ---
# Function to get the appropriate nix develop command based on OS
# This is one of the few OS-specific adaptations we need to make
get_nix_develop_cmd() {
  if [[ "$(uname)" == "Darwin" ]]; then
    # echo "nix develop --impure"  # Commented out for now
    echo "nix develop"
  else
    echo "nix develop"
  fi
}
NIX_DEVELOP_CMD=$(get_nix_develop_cmd)

# --- Display Banner ---
echo
print_separator
echo "   🚀 Welcome to Pipulate Installer 🚀   "
echo "   Free and Open Source SEO Software     "
print_separator
echo

# --- Dependency Checks ---
# Note: We check for minimal dependencies that are needed for this phase
# Git is NOT required at this stage - the flake will handle git operations later
echo "🔍 Checking prerequisites..."
check_command "curl"
check_command "unzip"

# The Universe Builder (Nix Foundation Check)
if ! command -v nix &> /dev/null; then
  echo "📦 Nix Package Manager not found. Inventing the universe..."
  curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install
  echo "=================================================================="
  echo "⚠️  CRITICAL: The universe has been built, but you must enter it."
  echo "Please CLOSE this terminal window, open a NEW one, and re-run:"
  echo "curl -L https://pipulate.com/assets/installer/install.sh | bash -s ${CUSTOM_NAME}"
  echo "=================================================================="
  exit 0
fi

echo "✅ All required tools found."
echo

# --- Target Directory Handling ---
# Check if target directory already exists and gracefully fail
echo "📁 Checking target directory: ${TARGET_DIR}"
if [ -d "${TARGET_DIR}" ]; then
  echo "❌ Error: Directory '${TARGET_DIR}' already exists."
  echo "   The installer cannot proceed when the target directory already exists."
  echo "   This prevents accidental overwrites of existing data."
  echo
  echo "   To resolve this, you can:"
  echo "   1. Choose a different name: curl -sSL https://pipulate.com/assets/installer/install.sh | bash -s your-custom-name"
  echo "   2. Remove the existing directory: rm -rf ${TARGET_DIR}"
  echo "   3. Rename the existing directory: mv ${TARGET_DIR} ${TARGET_DIR}.backup"
  echo
  if [ -f "${TARGET_DIR}/flake.nix" ]; then
    echo "   Note: The existing directory appears to be a Pipulate installation."
    echo "   You can start it directly with: cd ${TARGET_DIR} && ${NIX_DEVELOP_CMD}"
  fi
  echo
  exit 1
else
  echo "✅ Target directory is available."
  echo "📁 Creating directory '${TARGET_DIR}'"
  mkdir -p "${TARGET_DIR}"
fi

# --- Download and Extract ---
# The "magic cookie" approach begins here - downloading the ZIP archive
# This is more reliable across systems than using git directly
echo "📥 Downloading Pipulate source code..."
# Download to a temporary file
TMP_ZIP_FILE=$(mktemp)
# Ensure temp file is removed on exit
trap 'rm -f "$TMP_ZIP_FILE"' EXIT
curl -L --fail -o "${TMP_ZIP_FILE}" "${ZIP_URL}"
echo "✅ Download complete."
echo

echo "📦 Extracting source code..."
# Create a temporary directory for extraction
TMP_EXTRACT_PATH=$(mktemp -d)
trap 'rm -rf "$TMP_EXTRACT_PATH"; rm -f "$TMP_ZIP_FILE"' EXIT

# Extract into the temporary directory
unzip -q "${TMP_ZIP_FILE}" -d "${TMP_EXTRACT_PATH}"

# Check if extraction created the expected directory
FULL_EXTRACT_DIR="${TMP_EXTRACT_PATH}/${TMP_EXTRACT_DIR}"
if [ ! -d "${FULL_EXTRACT_DIR}" ]; then
  echo "❌ Error: Extraction did not produce the expected directory '${TMP_EXTRACT_DIR}'."
  exit 1
fi

# Move extracted contents into TARGET_DIR
# Using cp first to ensure all files are copied correctly
cp -R "${FULL_EXTRACT_DIR}/." "${TARGET_DIR}/"
rm -f "$TMP_ZIP_FILE"
echo "✅ Extraction complete. Source code installed to '${TARGET_DIR}'."
echo

# --- Navigate Into Project ---
cd "${TARGET_DIR}"
echo "📍 Now in directory: $(pwd)"
echo

# --- Deploy Key Setup ("Magic Cookie") ---
# Part of the "magic cookie" is the SSH key that will allow the flake
# to perform git operations without password prompts
echo "🔑 Setting up deployment key..."
mkdir -p .ssh
echo "Fetching deployment key from ${KEY_URL}..."
# Use curl to fetch the key from the URL and save it to .ssh/rot
if curl -L -sS --fail -o .ssh/rot "${KEY_URL}"; then
  echo "✅ Deployment key downloaded successfully."
else
  echo "❌ Error: Failed to download deployment key from ${KEY_URL}."
  # Optional: remove potentially incomplete key file
  rm -f .ssh/rot
  exit 1
fi

# Verify that the downloaded file is not empty
if [ ! -s .ssh/rot ]; then
    echo "❌ Error: Downloaded deployment key file (.ssh/rot) is empty."
    rm -f .ssh/rot # Clean up empty file
    exit 1
fi

chmod 600 .ssh/rot # Important: Set permissions for the raw key file
echo "🔒 Deployment key file saved and secured."
echo

# --- Trigger Initial Nix Build & Git Conversion ---
# Now we hand over to nix develop, which will activate the flake
# The flake will handle converting this to a proper git repository
echo "🚀 Starting Pipulate environment..."
print_separator
echo "  All set! Pipulate is installed at: ${TARGET_DIR}  "
echo "  To use Pipulate in the future, simply run:  "
echo "  cd ${TARGET_DIR} && ${NIX_DEVELOP_CMD}  "
print_separator
echo

# Before the exec command, add:
echo "Setting up app identity as '$CUSTOM_NAME'..."
echo "$CUSTOM_NAME" > "${TARGET_DIR}/whitelabel.txt"
chmod 644 "${TARGET_DIR}/whitelabel.txt"
echo "✅ Application identity set."
echo

# Creating the 'Double-Click' Actuator
echo "Creating the universal ./run actuator..."
cat > "${TARGET_DIR}/run" << 'EOL'
#!/usr/bin/env bash
cd "$(dirname "$0")" 
if [[ "$(uname)" == "Darwin" ]]; then
  exec nix develop --impure
else
  exec nix develop
fi
EOL
chmod +x "${TARGET_DIR}/run"

# VERSION NOTE: This version is synced from pipulate/__init__.py.__version__
# To update: Edit __version__ in __init__.py, then run: python version_sync.py
# This ensures consistent versioning across all installation components
VERSION="1.0.2"

# The nix flake will take over from here, handling the git repository setup
# This is the final step of the "magic cookie" approach - letting the controlled
# nix environment handle the git operations
echo "Pipulate Installer v${VERSION} - Test checkpoint reached"
echo "Setup complete! To start using Pipulate, run:"
echo "  cd ${TARGET_DIR}"
echo "  ${NIX_DEVELOP_CMD}"
echo
echo "This will activate the Nix development environment and"
echo "complete the 'magic cookie' transformation process."
