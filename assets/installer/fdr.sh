#!/usr/bin/env bash
# Pipulate FDR Bootstrap v0.1.0 — the Flight Data Recorder replay lane
# ====================================================================
# THE COMMAND:  curl -fsSL https://npvg.org/fdr/<id> | bash
#
# THE PATH IS THE FLAG. A piped script cannot see its own URL, so the
# npvg.org route serves THIS file with the id stamped into the
# __FDR_ID__ placeholder (nginx sub_filter; route spec ships beside this
# script). Local and offline forms also work:
#
#   bash fdr.sh <id>                             # positional id
#   FDR_ID=<id> bash fdr.sh                      # env id
#   PIPULATE_FDR_MANIFEST=./m.json bash fdr.sh   # offline manifest, no fetch
#
# WHAT THIS DOES — all of it, transparently:
#   1. Resolve <id> -> a pinned FDR manifest (JSON):
#        { "kind": "trail" | "cartridge" | "capture-bundle",
#          "url": "https://... or local path",   # revision-pinned payload
#          "sha256": "<64 hex>",                 # REQUIRED — unpinned = refused
#          "label": "human-facing name",
#          "env": { "VAR": "value" } }           # optional; trail rides only
#   2. Fetch the payload and verify sha256. Any mismatch = refusal, exit 2.
#      The pin is what makes this a RECORDER: an FDR whose payload can be
#      re-recorded after the flight is a CVR in a black-box costume.
#   3. Confirm with the human via /dev/tty — under curl|bash, stdin IS the
#      script, so /dev/tty is the only honest keyboard (precedent: the
#      2026-07-29 CAPTURE-checkpoint conviction in tools/scraper_tools.py).
#   4. Dispatch by kind:
#        trail          -> ride via mothercat when run inside a Pipulate
#                          checkout; otherwise save the trail + print card
#        cartridge      -> hand the verified file to replay.sh
#        capture-bundle -> stage the payload to the clipboard + print card
#
# WHAT THIS NEVER DOES: no install, no persistence, no shell-rc edits,
# no background processes. Resolve, verify, confirm, dispatch, exit.
#
# ENV OVERRIDES:
#   PIPULATE_FDR_INDEX_URL    manifest base (default https://npvg.org/fdr)
#   PIPULATE_FDR_MANIFEST     local manifest path (skips resolution fetch)
#   PIPULATE_FDR_REPLAY_URL   replay.sh source for cartridge dispatch
#   PIPULATE_FDR_REPLAY       local replay.sh path (skips fetch)
#   PIPULATE_FDR_ASSUME_YES   =1 skips the /dev/tty confirmation (trusted
#                             automation only; never the default)
#
# EXIT CODES: 0 replayed/staged | 1 usage/dependency/abort | 2 integrity refusal

if [ -z "${BASH_VERSION:-}" ]; then
  echo "❌ Error: this script requires bash. Re-run with:"
  echo "   curl -fsSL https://npvg.org/fdr/<id> | bash"
  exit 1
fi

set -euo pipefail

INDEX_URL="${PIPULATE_FDR_INDEX_URL:-https://npvg.org/fdr}"
REPLAY_URL="${PIPULATE_FDR_REPLAY_URL:-https://pipulate.com/replay.sh}"

# --- Resolve the ID: positional > env > server-templated placeholder.
# The split spelling of _ph is load-bearing: sub_filter replaces every
# contiguous __FDR_ID__ in the served body, and the split literal is the
# one occurrence it can never touch, so template-vs-untemplated stays
# detectable after substitution (the SECRET_TRIPWIRES self-quoting dodge).
_tpl='__FDR_ID__'
_ph='__FDR_''ID__'
FDR_ID="${1:-${FDR_ID:-}}"
if [ -z "$FDR_ID" ] && [ "$_tpl" != "$_ph" ]; then
  FDR_ID="$_tpl"
fi

command -v python3 >/dev/null 2>&1 || {
  echo "❌ Error: python3 is required (standard library only — no packages)." >&2
  exit 1
}

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    echo "❌ Error: need sha256sum or shasum on PATH." >&2
    exit 1
  fi
}

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# --- Acquire the manifest ---
if [ -n "${PIPULATE_FDR_MANIFEST:-}" ]; then
  MANIFEST_PATH="$PIPULATE_FDR_MANIFEST"
  if [ ! -f "$MANIFEST_PATH" ]; then
    echo "❌ Error: manifest not found: $MANIFEST_PATH" >&2
    exit 1
  fi
  echo "📇 Manifest: $MANIFEST_PATH (local override)"
else
  if [ -z "$FDR_ID" ]; then
    echo "❌ Error: no FDR id resolved." >&2
    echo "   Usage: curl -fsSL https://npvg.org/fdr/<id> | bash" >&2
    exit 1
  fi
  command -v curl >/dev/null 2>&1 || {
    echo "❌ Error: curl is required to resolve a manifest." >&2
    exit 1
  }
  MANIFEST_PATH="$TMP_DIR/manifest.json"
  echo "📇 Resolving FDR id '$FDR_ID' via $INDEX_URL/$FDR_ID.json"
  if ! curl -fsSL -o "$MANIFEST_PATH" "$INDEX_URL/$FDR_ID.json"; then
    echo "❌ Error: could not resolve manifest for id '$FDR_ID'." >&2
    exit 1
  fi
fi

# --- Parse + pin-check (stdlib json; fail closed with exit 2) ---
set +e
MANIFEST_FIELDS="$(python3 - "$MANIFEST_PATH" <<'PYEOF'
import json
import re
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        manifest = json.load(handle)
except Exception as exc:
    print(f"bad manifest: {exc}", file=sys.stderr)
    sys.exit(2)

kind = manifest.get("kind")
url = manifest.get("url")
pin = manifest.get("sha256")
label = manifest.get("label") or str(kind)

if kind not in ("trail", "cartridge", "capture-bundle"):
    print(f"unknown kind: {kind!r}", file=sys.stderr)
    sys.exit(2)
if not isinstance(url, str) or not url.strip():
    print("missing payload url", file=sys.stderr)
    sys.exit(2)
if not (isinstance(pin, str) and re.fullmatch(r"[0-9a-f]{64}", pin)):
    print("UNPINNED PAYLOAD: sha256 missing or malformed", file=sys.stderr)
    sys.exit(2)

print(kind)
print(url.strip())
print(pin)
print(label)
for key, value in (manifest.get("env") or {}).items():
    if isinstance(key, str) and isinstance(value, str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
        print(f"ENV {key}={value}")
PYEOF
)"
MANIFEST_RC=$?
set -e
if [ "$MANIFEST_RC" -ne 0 ]; then
  echo "🛑 MANIFEST REFUSED: it must declare kind, url, and a 64-hex sha256 pin. Nothing executed." >&2
  exit 2
fi

KIND="$(printf '%s\n' "$MANIFEST_FIELDS" | sed -n '1p')"
PAYLOAD_URL="$(printf '%s\n' "$MANIFEST_FIELDS" | sed -n '2p')"
PIN="$(printf '%s\n' "$MANIFEST_FIELDS" | sed -n '3p')"
LABEL="$(printf '%s\n' "$MANIFEST_FIELDS" | sed -n '4p')"

# --- Fetch the payload and verify the pin ---
PAYLOAD_PATH="$TMP_DIR/payload"
case "$PAYLOAD_URL" in
  http://*|https://*)
    if ! curl -fsSL -o "$PAYLOAD_PATH" "$PAYLOAD_URL"; then
      echo "❌ Error: could not fetch payload from $PAYLOAD_URL" >&2
      exit 1
    fi
    ;;
  *)
    if [ ! -f "$PAYLOAD_URL" ]; then
      echo "❌ Error: local payload not found: $PAYLOAD_URL" >&2
      exit 1
    fi
    cp "$PAYLOAD_URL" "$PAYLOAD_PATH"
    ;;
esac

GOT="$(sha256_of "$PAYLOAD_PATH")"
if [ "$GOT" != "$PIN" ]; then
  echo "🛑 INTEGRITY REFUSAL: payload sha256 $GOT does not match pinned $PIN. Nothing executed." >&2
  exit 2
fi
echo "✅ PIN VERIFIED sha256=${PIN:0:12}…  kind=$KIND  label=$LABEL"

# --- Human confirmation on /dev/tty (the only honest keyboard here) ---
if [ "${PIPULATE_FDR_ASSUME_YES:-0}" = "1" ]; then
  echo "⏩ Confirmation skipped (PIPULATE_FDR_ASSUME_YES=1)."
else
  printf '\nAbout to dispatch: kind=%s  label=%s  pin=%s…\n' "$KIND" "$LABEL" "${PIN:0:12}"
  printf 'Type RIDE and press Enter to proceed (anything else aborts).\nRIDE> '
  ANSWER=""
  if ! IFS= read -r ANSWER </dev/tty; then
    echo "" >&2
    echo "🛑 No controlling terminal to confirm on (/dev/tty unavailable)." >&2
    echo "   Set PIPULATE_FDR_ASSUME_YES=1 only for automation you trust." >&2
    exit 1
  fi
  if [ "$ANSWER" != "RIDE" ]; then
    echo "Aborted by human. Nothing executed."
    exit 1
  fi
fi

# --- Clipboard staging (replay.sh grammar: daemonizers get detached streams) ---
CLIP_TOOL=""
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

# --- Dispatch by kind ---
case "$KIND" in
  trail)
    while IFS= read -r line; do
      case "$line" in
        ENV\ *)
          kv="${line#ENV }"
          export "${kv%%=*}=${kv#*=}"
          echo "🌱 exported ${kv%%=*}"
          ;;
      esac
    done <<< "$MANIFEST_FIELDS"
    TRAIL_PATH="$TMP_DIR/fdr_trail.yaml"
    cp "$PAYLOAD_PATH" "$TRAIL_PATH"
    if [ -f scripts/mother_cat.py ] && [ -x .venv/bin/python ]; then
      echo "🐈 Pipulate checkout detected. Riding the trail via mothercat…"
      .venv/bin/python scripts/mother_cat.py "$TRAIL_PATH"
      exit $?
    fi
    SAVED="$PWD/fdr_trail_${FDR_ID:-local}.yaml"
    cp "$PAYLOAD_PATH" "$SAVED"
    cat <<CARD
--------------------------------------------------------------
   🐈 TRAIL VERIFIED — but no Pipulate workshop is open here
--------------------------------------------------------------
 The pinned trail was saved to:
   $SAVED

 1. Install Pipulate (one line, any OS):
      curl -fsSL https://pipulate.com/install.sh | bash
 2. Enter the workshop:  cd ~/pipulate && nix develop
 3. Ride the trail:      mothercat $SAVED
--------------------------------------------------------------
CARD
    ;;
  cartridge)
    if [ -n "${PIPULATE_FDR_REPLAY:-}" ]; then
      echo "📼 Handing verified cartridge to local replay.sh…"
      bash "$PIPULATE_FDR_REPLAY" "$PAYLOAD_PATH"
    else
      command -v curl >/dev/null 2>&1 || {
        echo "❌ Error: curl is required to fetch replay.sh." >&2
        exit 1
      }
      echo "📼 Handing verified cartridge to $REPLAY_URL…"
      curl -fsSL "$REPLAY_URL" | bash -s -- "$PAYLOAD_PATH"
    fi
    ;;
  capture-bundle)
    PAYLOAD_BYTES="$(wc -c < "$PAYLOAD_PATH" | tr -d ' ')"
    if stage_clipboard "$PAYLOAD_PATH"; then
      CLIP_LINE="📋 capture bundle ($PAYLOAD_BYTES bytes) staged via $CLIP_TOOL"
    else
      FALLBACK="$PWD/fdr_bundle.md"
      cp "$PAYLOAD_PATH" "$FALLBACK"
      CLIP_LINE="⚠️  No clipboard tool found — bundle written to $FALLBACK"
    fi
    cat <<CARD
--------------------------------------------------------------
   🛬 FLIGHT DATA RECORDED — the instrument now fades away
--------------------------------------------------------------
 $CLIP_LINE

 1. Open the AI web chat of your choice (Claude, ChatGPT,
    Gemini — any large-context model).
 2. Paste (Cmd+V / Ctrl+V) and send.
 3. It will walk you through everything from here.
--------------------------------------------------------------
CARD
    ;;
esac
