#!/usr/bin/env bash
# Pipulate Cartridge Replayer v0.2.0
# ==================================
# foo-cartridge-replay-v1, step two: the curl-distributed clean-room consumer.
#
# WHAT THIS DOES -- all of it, transparently:
#   1. Takes one foo.zip context cartridge (local path or URL).
#   2. Obtains the stdlib-only verifier core (scripts/foo_cartridge.py) and
#      VERIFIES ITS SHA-256 AGAINST A PIN BAKED INTO THIS FILE before that
#      core is ever executed. A fetched core that does not match is REFUSED.
#   3. Verifies the cartridge against the foo-cartridge-integrity-v1 schema:
#      exact members, canonical ZIP metadata, canonical JSON, member hashes,
#      and byte-canonical archive reconstruction. Any deviation = refusal.
#   4. On PASS, stages payload.md into the host clipboard (pbcopy on macOS,
#      clip.exe on Windows/WSL, wl-copy/xclip on Linux) and prints the
#      human-actuator card. The human pastes into an AI web chat; the
#      actionable request is the FINAL Prompt section of the payload.
#
# WHAT CHANGED IN v0.2.0
#
#   1. THE VERIFIER IS PINNED. v0.1.0 fetched its own verifier from a MOVING
#      BRANCH -- the one artifact in the whole chain whose integrity matters
#      most was the single thing acquired unverified, by the tool whose entire
#      job is proving integrity. A pip in the file that most needed to be a
#      graft. CORE_SHA256 below is the graft, and it fails CLOSED.
#   2. --mode IS GONE. It advertised slideshow and gated; both printed "not
#      implemented". A flag with one legal value is not a flag, and an
#      advertised capability with no implementation is a map ahead of its
#      territory inside a file that strangers execute.
#
# PIN MAINTENANCE, stated so it can never be discovered instead of read: the
# day scripts/foo_cartridge.py legitimately changes, this pin is stale and
# every default-path replay REFUSES until a release ships a new CORE_SHA256.
# That is the correct failure. Update the pin in the SAME commit as any change
# to the core, or the served replayer breaks for everyone except the person
# holding a local copy.
#
# WHAT THIS NEVER DOES: install, persist, edit a shell rc, or leave a
# background process behind. Verify, stage, print, exit.
#
# USAGE:
#   curl -fsSL https://pipulate.com/replay.sh | bash -s -- <foo.zip|URL>
#   bash replay.sh <foo.zip|URL> [--no-clipboard]
#
# ENV OVERRIDES:
#   PIPULATE_CARTRIDGE_CORE      local path to foo_cartridge.py. Hashed
#                                against the pin and WARNS on mismatch rather
#                                than refusing: you named a file you control,
#                                so a mismatch is information about the PIN,
#                                not about the file.
#   PIPULATE_CARTRIDGE_CORE_URL  alternate URL for the core. Still pinned; a
#                                URL override is not a trust override.
#
# EXIT CODES: 0 verified (and staged, unless skipped) | 1 usage/dependency
#             error | 2 verifier or cartridge failed verification
if [ -z "${BASH_VERSION:-}" ]; then
  echo "Error: this script requires bash. Re-run with:"
  echo "   curl -fsSL https://pipulate.com/replay.sh | bash -s -- <foo.zip|URL>"
  exit 1
fi
set -euo pipefail
CORE_URL_DEFAULT="https://raw.githubusercontent.com/pipulate/pipulate/main/scripts/foo_cartridge.py"
CORE_SHA256="9f5520ad41fdea0a89828df7336d9124d5aaa7209b1838aaf7465c04c6ea6d8b"
CARTRIDGE_ARG=""
STAGE_CLIPBOARD=1
while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-clipboard)
      STAGE_CLIPBOARD=0
      shift
      ;;
    -h|--help)
      echo "Usage: replay.sh <foo.zip|URL> [--no-clipboard]"
      exit 0
      ;;
    -*)
      echo "Error: unknown option '$1' (only --no-clipboard is understood)" >&2
      exit 1
      ;;
    *)
      if [ -z "$CARTRIDGE_ARG" ]; then
        CARTRIDGE_ARG="$1"
        shift
      else
        echo "Error: unexpected argument: $1" >&2
        exit 1
      fi
      ;;
  esac
done
if [ -z "$CARTRIDGE_ARG" ]; then
  echo "Error: no cartridge given." >&2
  echo "   Usage: bash replay.sh <foo.zip|URL> [--no-clipboard]" >&2
  exit 1
fi
command -v python3 >/dev/null 2>&1 || {
  echo "Error: python3 is required (standard library only -- no packages)." >&2
  exit 1
}
# THREE TIERS SO A HASH IS ALWAYS COMPUTABLE. python3 is already a hard
# dependency checked above, so "no hashing tool on this machine" is not a
# reachable state and the pin can never be silently skipped. A verifier that
# quietly stops verifying when a coreutil is missing is not a verifier.
sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | cut -d' ' -f1
  else
    python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
  fi
}
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
# --- Acquire the cartridge ---
case "$CARTRIDGE_ARG" in
  http://*|https://*)
    command -v curl >/dev/null 2>&1 || {
      echo "Error: curl is required to fetch a cartridge URL." >&2
      exit 1
    }
    CARTRIDGE_PATH="$TMP_DIR/foo.zip"
    echo "📥 Fetching cartridge: $CARTRIDGE_ARG"
    if ! curl -fsSL -o "$CARTRIDGE_PATH" "$CARTRIDGE_ARG"; then
      echo "Error: could not fetch cartridge from $CARTRIDGE_ARG" >&2
      exit 1
    fi
    ;;
  *)
    CARTRIDGE_PATH="$CARTRIDGE_ARG"
    if [ ! -f "$CARTRIDGE_PATH" ]; then
      echo "Error: cartridge not found: $CARTRIDGE_PATH" >&2
      exit 1
    fi
    ;;
esac
# --- Acquire the verifier core, and PIN IT before executing anything ---
if [ -n "${PIPULATE_CARTRIDGE_CORE:-}" ]; then
  CORE_PATH="$PIPULATE_CARTRIDGE_CORE"
  if [ ! -f "$CORE_PATH" ]; then
    echo "Error: PIPULATE_CARTRIDGE_CORE not found: $CORE_PATH" >&2
    exit 1
  fi
  echo "🔬 Verifier core: $CORE_PATH (local override)"
  CORE_SUM="$(sha256_of "$CORE_PATH")"
  if [ "$CORE_SUM" = "$CORE_SHA256" ]; then
    echo "🔐 Verifier core pinned and matched (sha256 ${CORE_SHA256:0:12})"
  else
    echo "⚠️  PIN MISMATCH on the local override -- proceeding, and here is why:"
    echo "    expected $CORE_SHA256"
    echo "    actual   $CORE_SUM"
    echo "    You named this file, so it is trusted. The mismatch is a fact"
    echo "    about THIS replayer's pin, which is now stale relative to your"
    echo "    core. Update CORE_SHA256 in the same commit as the core, or the"
    echo "    served copy fails closed for everyone else."
  fi
else
  CORE_URL="${PIPULATE_CARTRIDGE_CORE_URL:-$CORE_URL_DEFAULT}"
  command -v curl >/dev/null 2>&1 || {
    echo "Error: curl is required to fetch the verifier core." >&2
    exit 1
  }
  CORE_PATH="$TMP_DIR/foo_cartridge.py"
  echo "🔬 Fetching verifier core: $CORE_URL"
  if ! curl -fsSL -o "$CORE_PATH" "$CORE_URL"; then
    echo "Error: could not fetch verifier core from $CORE_URL" >&2
    echo "   Override with PIPULATE_CARTRIDGE_CORE=/path/to/foo_cartridge.py" >&2
    exit 1
  fi
  CORE_SUM="$(sha256_of "$CORE_PATH")"
  if [ "$CORE_SUM" != "$CORE_SHA256" ]; then
    echo "🛑 VERIFIER REFUSED: the fetched core does not match the pin." >&2
    echo "    expected $CORE_SHA256" >&2
    echo "    actual   $CORE_SUM" >&2
    echo "    NOTHING WAS EXECUTED. Two explanations, in order of likelihood:" >&2
    echo "    (1) the core moved ahead of this replayer -- fetch a newer" >&2
    echo "        replay.sh, or point PIPULATE_CARTRIDGE_CORE at a local copy" >&2
    echo "        you trust; (2) something served you a file that is not the" >&2
    echo "        verifier. Do not run it to find out which." >&2
    exit 2
  fi
  echo "🔐 Verifier core pinned and matched (sha256 ${CORE_SHA256:0:12})"
fi
# --- Verify the cartridge (fail closed; the refusal reason is the receipt) ---
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
print(f"CARTRIDGE VERIFIED sha256={result['archive_sha256'][:12]}...")
PYEOF
)"
VERIFY_RC=$?
set -e
echo "$VERDICT"
if [ "$VERIFY_RC" -ne 0 ]; then
  echo "🛑 The cartridge failed foo-cartridge-integrity-v1 verification. Nothing staged." >&2
  exit 2
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
# --- Stage the clipboard. Daemonizing tools get their streams detached: no
# forked clipboard process may ever hold a captured pipe hostage (the
# rgx/xclip deadlock lesson, now constitutional). ---
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
    CLIP_LINE="⚠️  No clipboard tool found -- payload written to $FALLBACK"
  fi
else
  CLIP_LINE="⏭️  payload.md ($PAYLOAD_BYTES bytes) verified; staging skipped (--no-clipboard), nothing left behind"
fi
# --- The human-actuator card ---
cat <<CARD
--------------------------------------------------------------
   🎮 CARTRIDGE READY -- the system now fades away
--------------------------------------------------------------
 $VERDICT
 $CLIP_LINE
 1. Open the AI web chat of your choice (Claude, ChatGPT,
    Gemini -- any large-context model).
 2. Paste (Cmd+V / Ctrl+V) and send.
 3. The actionable request is the FINAL "Prompt" section.
    Everything above it is evidence, not instructions.
--------------------------------------------------------------
CARD
