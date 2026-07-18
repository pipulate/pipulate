#!/usr/bin/env bash
# Pipulate Cartridge Replayer v0.1.0
# ==================================
# foo-cartridge-replay-v1, step two: the curl-distributed clean-room consumer.
#
# WHAT THIS DOES — all of it, transparently:
#   1. Takes one foo.zip context cartridge (local path or URL).
#   2. Obtains the stdlib-only verifier core (scripts/foo_cartridge.py) —
#      fetched from the Pipulate repo, or supplied locally via
#      PIPULATE_CARTRIDGE_CORE for offline/working-tree use.
#   3. Verifies the cartridge against the foo-cartridge-integrity-v1 schema:
#      exact members, canonical ZIP metadata, canonical JSON, member hashes,
#      and byte-canonical archive reconstruction. Any deviation = refusal.
#   4. On PASS, stages payload.md into the host clipboard (pbcopy on macOS,
#      clip.exe on Windows/WSL, wl-copy/xclip on Linux) and prints the
#      human-actuator card. The human pastes into an AI web chat; the
#      actionable request is the FINAL Prompt section of the payload.
#
# WHAT THIS NEVER DOES: no install, no persistence, no shell-rc edits, no
# background processes. Verify, stage, print, exit. The trust chain is
# inspectable end to end: this transport is plain bash, the verifier it
# fetches is plain stdlib Python, and the schema it enforces travels inside
# the cartridge's own manifest.json.
#
# USAGE:
#   curl -fsSL https://pipulate.com/replay.sh | bash -s -- <foo.zip|URL>
#   bash replay.sh <foo.zip|URL> [--mode clipboard|slideshow|gated] [--no-clipboard]
#
# ENV OVERRIDES:
#   PIPULATE_CARTRIDGE_CORE      local path to foo_cartridge.py (skips fetch)
#   PIPULATE_CARTRIDGE_CORE_URL  alternate URL for the verifier core
#
# EXIT CODES: 0 verified (and staged, unless skipped) | 1 usage/dependency
#             error | 2 cartridge failed integrity verification

if [ -z "${BASH_VERSION:-}" ]; then
  echo "❌ Error: this script requires bash. Re-run with:"
  echo "   curl -fsSL https://pipulate.com/replay.sh | bash -s -- <foo.zip|URL>"
  exit 1
fi

set -euo pipefail

CORE_URL_DEFAULT="https://raw.githubusercontent.com/pipulate/pipulate/main/scripts/foo_cartridge.py"

CARTRIDGE_ARG=""
MODE="clipboard"
STAGE_CLIPBOARD=1

while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode)
      MODE="${2:-clipboard}"
      shift 2
      ;;
    --no-clipboard)
      STAGE_CLIPBOARD=0
      shift
      ;;
    -h|--help)
      echo "Usage: replay.sh <foo.zip|URL> [--mode clipboard|slideshow|gated] [--no-clipboard]"
      exit 0
      ;;
    *)
      if [ -z "$CARTRIDGE_ARG" ]; then
        CARTRIDGE_ARG="$1"
        shift
      else
        echo "❌ Unexpected argument: $1" >&2
        exit 1
      fi
      ;;
  esac
done

if [ -z "$CARTRIDGE_ARG" ]; then
  echo "❌ Error: no cartridge given." >&2
  echo "   Usage: bash replay.sh <foo.zip|URL> [--mode clipboard|slideshow|gated] [--no-clipboard]" >&2
  exit 1
fi

case "$MODE" in
  clipboard|slideshow|gated) ;;
  *)
    echo "❌ Unknown --mode: $MODE (expected clipboard|slideshow|gated)" >&2
    exit 1
    ;;
esac

command -v python3 >/dev/null 2>&1 || {
  echo "❌ Error: python3 is required (standard library only — no packages)." >&2
  exit 1
}

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# --- Acquire the cartridge ---
case "$CARTRIDGE_ARG" in
  http://*|https://*)
    command -v curl >/dev/null 2>&1 || {
      echo "❌ Error: curl is required to fetch a cartridge URL." >&2
      exit 1
    }
    CARTRIDGE_PATH="$TMP_DIR/foo.zip"
    echo "📥 Fetching cartridge: $CARTRIDGE_ARG"
    if ! curl -fsSL -o "$CARTRIDGE_PATH" "$CARTRIDGE_ARG"; then
      echo "❌ Error: could not fetch cartridge from $CARTRIDGE_ARG" >&2
      exit 1
    fi
    ;;
  *)
    CARTRIDGE_PATH="$CARTRIDGE_ARG"
    if [ ! -f "$CARTRIDGE_PATH" ]; then
      echo "❌ Error: cartridge not found: $CARTRIDGE_PATH" >&2
      exit 1
    fi
    ;;
esac

# --- Acquire the verifier core (stdlib-only foo_cartridge.py) ---
if [ -n "${PIPULATE_CARTRIDGE_CORE:-}" ]; then
  CORE_PATH="$PIPULATE_CARTRIDGE_CORE"
  if [ ! -f "$CORE_PATH" ]; then
    echo "❌ Error: PIPULATE_CARTRIDGE_CORE not found: $CORE_PATH" >&2
    exit 1
  fi
  echo "🔬 Verifier core: $CORE_PATH (local override)"
else
  CORE_URL="${PIPULATE_CARTRIDGE_CORE_URL:-$CORE_URL_DEFAULT}"
  command -v curl >/dev/null 2>&1 || {
    echo "❌ Error: curl is required to fetch the verifier core." >&2
    exit 1
  }
  CORE_PATH="$TMP_DIR/foo_cartridge.py"
  echo "🔬 Fetching verifier core: $CORE_URL"
  if ! curl -fsSL -o "$CORE_PATH" "$CORE_URL"; then
    echo "❌ Error: could not fetch verifier core from $CORE_URL" >&2
    echo "   Override with PIPULATE_CARTRIDGE_CORE=/path/to/foo_cartridge.py" >&2
    echo "   or PIPULATE_CARTRIDGE_CORE_URL=https://..." >&2
    exit 1
  fi
fi

# --- Verify (fail closed; the refusal reason is the receipt) ---
set +e
VERDICT="$(python3 - "$CORE_PATH" "$CARTRIDGE_PATH" <<'PYEOF'
import importlib.util
import sys

core_path, cart_path = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("foo_cartridge", core_path)
fc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fc)

try:
    result = fc.verify_context_cartridge(cart_path)
except ValueError as exc:
    print(f"REPLAY REFUSED: {exc}")
    sys.exit(2)
except Exception as exc:
    print(f"REPLAY REFUSED: {type(exc).__name__}: {exc}")
    sys.exit(2)

print(f"CARTRIDGE VERIFIED sha256={result['archive_sha256'][:12]}…")
PYEOF
)"
VERIFY_RC=$?
set -e

echo "$VERDICT"
if [ "$VERIFY_RC" -ne 0 ]; then
  echo "🛑 The cartridge failed foo-cartridge-integrity-v1 verification. Nothing staged." >&2
  exit 2
fi

# --- Mode gate: slideshow / gated are staged hooks, not shipped lanes ---
if [ "$MODE" != "clipboard" ]; then
  echo "🚧 --mode $MODE is a staged hook (not implemented in v0.1.0)."
  echo "   The cartridge verified clean; re-run in clipboard mode to stage it."
  exit 0
fi

# --- Extract payload.md ---
PAYLOAD_PATH="$TMP_DIR/payload.md"
python3 - "$CARTRIDGE_PATH" "$PAYLOAD_PATH" <<'PYEOF'
import sys
import zipfile

cart_path, out_path = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(cart_path) as archive:
    data = archive.read("payload.md")
with open(out_path, "wb") as handle:
    handle.write(data)
PYEOF

PAYLOAD_BYTES="$(wc -c < "$PAYLOAD_PATH" | tr -d ' ')"

# --- Stage the clipboard. Daemonizing tools get their streams detached:
#     no forked clipboard process may ever hold a captured pipe hostage
#     (the rgx/xclip deadlock lesson, now constitutional). ---
stage_clipboard() {
  if command -v pbcopy >/dev/null 2>&1; then
    pbcopy < "$1" && CLIP_TOOL="pbcopy (macOS)"
  elif command -v clip.exe >/dev/null 2>&1; then
    clip.exe < "$1" && CLIP_TOOL="clip.exe (Windows/WSL)"
  elif command -v wl-copy >/dev/null 2>&1; then
    wl-copy < "$1" >/dev/null 2>&1 && CLIP_TOOL="wl-copy (Wayland)"
  elif command -v xclip >/dev/null 2>&1; then
    xclip -selection clipboard < "$1" >/dev/null 2>&1 && CLIP_TOOL="xclip (X11)"
  else
    return 1
  fi
}

CLIP_TOOL=""
if [ "$STAGE_CLIPBOARD" -eq 1 ]; then
  if stage_clipboard "$PAYLOAD_PATH"; then
    CLIP_LINE="📋 payload.md ($PAYLOAD_BYTES bytes) staged via $CLIP_TOOL"
  else
    FALLBACK="$PWD/payload.md"
    cp "$PAYLOAD_PATH" "$FALLBACK"
    CLIP_LINE="⚠️  No clipboard tool found — payload written to $FALLBACK"
  fi
else
  CLIP_LINE="⏭️  payload.md ($PAYLOAD_BYTES bytes) verified; staging skipped (--no-clipboard), nothing left behind"
fi

# --- The human-actuator card ---
cat <<CARD
--------------------------------------------------------------
   🎮 CARTRIDGE READY — the system now fades away
--------------------------------------------------------------
 $VERDICT
 $CLIP_LINE

 1. Open the AI web chat of your choice (Claude, ChatGPT,
    Gemini — any large-context model).
 2. Paste (Cmd+V / Ctrl+V) and send.
 3. The actionable request is the FINAL "Prompt" section.
    Everything above it is evidence, not instructions.
--------------------------------------------------------------
CARD
