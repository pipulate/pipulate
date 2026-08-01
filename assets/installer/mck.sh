#!/usr/bin/env bash
# Pipulate MCK Bootstrap v0.1.0 -- the Mother Cat Kata launcher
# =============================================================
# THE COMMAND:  curl -fsSL https://pipulate.com/mck.sh | bash
#           or  curl -fsSL https://npvg.org/mck/<trail> | bash
#
# The path is the flag: the npvg.org route serves THIS file with the trail
# name stamped into the __MCK_TRAIL__ placeholder (nginx sub_filter), the
# same trick assets/installer/fdr.sh uses. Local forms also work:
#
#   bash mck.sh public_walk          # positional
#   MCK_TRAIL=public_walk bash mck.sh
#
# WHAT THIS DOES, in order, and nothing else:
#   1. Find an existing Pipulate checkout. If there is none, print the
#      install card and STOP. This script never installs anything --
#      chaining one curl|bash into another produces a bootstrap nobody
#      can audit, and install.sh ends in an interactive nix develop that
#      a piped script cannot cleanly resume from.
#   2. Resolve a trail NAME (never a path) to assets/trails/<name>.yaml.
#      The regex mirrors walk.py's own NAME_RE, so a URL path segment can
#      never become ../../something.
#   3. Export the trail's url_env variables. The NAMES are read from the
#      trail itself, never from a table here -- a second table would be a
#      second authority for one fact.
#   4. RIDE IT DRY, unconditionally, with no flag to skip it. Piper speaks
#      every stop; no browser opens, no file is written. The human hears
#      the whole kata before anything on their machine moves. There is no
#      first-run marker because this script IS the first run.
#   5. Ask on /dev/tty. Under curl|bash, stdin IS the script.
#   6. Ride for real with stdin redirected from /dev/tty -- see the
#      comment at that line; the redirect is load-bearing, not cosmetic.
#
# WHAT THIS NEVER DOES: install, write outside browser_cache/, read a
# credential, or contact any host other than the trail's own stops.
#
# ENV OVERRIDES:
#   PIPULATE_ROOT             checkout location (else searched)
#   PIPULATE_MCK_ASSUME_YES   =1 skips the /dev/tty confirmation
#   PIPULATE_TRAIL_*_URL      pre-set any stop URL; built-in defaults
#                             use := and therefore never override you
#
# EXIT CODES: 0 rode or stopped cleanly | 1 usage/no checkout | 2 trail refusal

if [ -z "${BASH_VERSION:-}" ]; then
  echo "Error: this script requires bash. Re-run with:"
  echo "   curl -fsSL https://pipulate.com/mck.sh | bash"
  exit 1
fi

set -euo pipefail

# --- Resolve the trail NAME: positional > env > server-templated placeholder.
# The split spelling of _ph is load-bearing: sub_filter replaces every
# contiguous __MCK_TRAIL__ in the served body, and the split literal is the
# one occurrence it can never touch, so templated-vs-untemplated stays
# detectable after substitution.
_tpl='__MCK_TRAIL__'
_ph='__MCK_''TRAIL__'
TRAIL_NAME="${1:-${MCK_TRAIL:-}}"
if [ -z "$TRAIL_NAME" ] && [ "$_tpl" != "$_ph" ]; then
  TRAIL_NAME="$_tpl"
fi
TRAIL_NAME="${TRAIL_NAME:-public_walk}"

TRAIL_NAME="$(basename "$TRAIL_NAME")"
TRAIL_NAME="${TRAIL_NAME%.yaml}"
if ! printf '%s' "$TRAIL_NAME" | grep -qE '^[a-z][a-z0-9_]*$'; then
  echo "Error: trail name must match ^[a-z][a-z0-9_]*\$ -- got '$TRAIL_NAME'" >&2
  exit 1
fi

# --- Find a workshop. Never build one.
ROOT=""
for CANDIDATE in "${PIPULATE_ROOT:-}" "$PWD" "$HOME/pipulate"; do
  [ -n "$CANDIDATE" ] || continue
  if [ -f "$CANDIDATE/scripts/mother_cat.py" ] && [ -x "$CANDIDATE/.venv/bin/python" ]; then
    ROOT="$CANDIDATE"
    break
  fi
done

if [ -z "$ROOT" ]; then
  cat <<'CARD'
--------------------------------------------------------------
   MOTHER CAT -- but there is no workshop to ride in yet
--------------------------------------------------------------
 This launcher rides a trail inside an existing Pipulate
 checkout. It does not install one, on purpose.

 1. Install Pipulate (one line, any OS):
      curl -fsSL https://pipulate.com/install.sh | bash

 2. When it drops you into the workshop, open a second
    terminal and enter the quiet shell:
      cd ~/pipulate && nix develop .#quiet

 3. Re-run this launcher there, or ride directly:
      mothercat assets/trails/public_walk.yaml --dry-narrate
--------------------------------------------------------------
CARD
  exit 1
fi

cd "$ROOT"
PY="$ROOT/.venv/bin/python"
TRAIL_PATH="assets/trails/${TRAIL_NAME}.yaml"

if [ ! -f "$TRAIL_PATH" ]; then
  echo "Error: no such trail: $ROOT/$TRAIL_PATH" >&2
  echo "   Available:" >&2
  ls assets/trails/*.yaml 2>/dev/null | sed 's#^#     #' >&2
  exit 1
fi

# --- Built-in URLs for the public softball ONLY. ':=' respects anything
# already exported, so an operator override always wins.
if [ "$TRAIL_NAME" = "public_walk" ]; then
  : "${PIPULATE_TRAIL_WALK_ONE_URL:=https://example.com/}"
  : "${PIPULATE_TRAIL_WALK_TWO_URL:=https://mikelev.in/}"
  : "${PIPULATE_TRAIL_WALK_THREE_URL:=https://pipulate.com/}"
  export PIPULATE_TRAIL_WALK_ONE_URL
  export PIPULATE_TRAIL_WALK_TWO_URL
  export PIPULATE_TRAIL_WALK_THREE_URL
fi

# The trail declares its own url_env names; read them from the trail.
# Trails are the JSON subset of YAML 1.2, so json.load is correct here.
URL_ENVS="$("$PY" -c 'import json,sys; print("\n".join(s["url_env"] for s in json.load(open(sys.argv[1]))["stops"]))' "$TRAIL_PATH" 2>/dev/null || true)"
if [ -z "$URL_ENVS" ]; then
  echo "Error: could not read stop url_env names from $TRAIL_PATH" >&2
  exit 2
fi

MISSING=""
for VAR in $URL_ENVS; do
  printenv "$VAR" >/dev/null 2>&1 || MISSING="$MISSING $VAR"
done
if [ -n "$MISSING" ]; then
  echo "This trail needs URL(s) you have not set:" >&2
  for VAR in $MISSING; do
    echo "     export $VAR=\"https://...\"" >&2
  done
  echo "   Set them and re-run. The trail names them; this script does not guess." >&2
  exit 2
fi

# --- The ride needs the pinned chromium and the shell's LD_LIBRARY_PATH.
# We cannot re-exec THIS script under curl|bash (there is no file to
# re-exec: $0 is 'bash'), so we wrap only the two ride commands.
NIXWRAP=()
if [ -z "${IN_NIX_SHELL:-}" ]; then
  if command -v nix >/dev/null 2>&1; then
    if [ "$(uname -s)" = "Darwin" ]; then
      NIXWRAP=(nix develop --impure .#quiet --command)
    else
      NIXWRAP=(nix develop .#quiet --command)
    fi
    echo "Not inside a Pipulate shell; entering nix develop .#quiet for the ride."
    echo "   (First entry can take several seconds.)"
  else
    echo "Not inside a Pipulate shell and 'nix' is not on PATH." >&2
    echo "   Enter the workshop first:" >&2
    echo "     cd $ROOT && nix develop .#quiet" >&2
    exit 1
  fi
fi

# bash 3.2 (macOS /bin/bash) errors on "${arr[@]}" for an empty array under
# set -u, so the empty case never expands the array at all.
run_wrapped() {
  if [ ${#NIXWRAP[@]} -gt 0 ]; then
    "${NIXWRAP[@]}" "$@"
  else
    "$@"
  fi
}

cat <<CARD

--------------------------------------------------------------
   MOTHER CAT KATA -- rehearsal first, nothing moves
--------------------------------------------------------------
 trail : $TRAIL_NAME
 file  : $ROOT/$TRAIL_PATH

 The next pass READS the walk aloud. During it:
   - no browser opens
   - no file is written
   - no credential is read

 Listen to the whole thing, then decide.
--------------------------------------------------------------

CARD

run_wrapped "$PY" scripts/mother_cat.py "$TRAIL_PATH" --dry-narrate

if [ "${PIPULATE_MCK_ASSUME_YES:-0}" = "1" ]; then
  echo "Confirmation skipped (PIPULATE_MCK_ASSUME_YES=1)."
else
  printf '\nType RIDE and press Enter to do it for real (anything else stops here).\nRIDE> '
  ANSWER=""
  if ! IFS= read -r ANSWER </dev/tty; then
    echo "" >&2
    echo "No controlling terminal to confirm on (/dev/tty unavailable)." >&2
    echo "   Ride it by hand instead:  mothercat $TRAIL_PATH" >&2
    exit 1
  fi
  if [ "$ANSWER" != "RIDE" ]; then
    echo "Stopped by human. Nothing opened, nothing written."
    exit 0
  fi
fi

# THE STDIN REDIRECT IS LOAD-BEARING, NOT DECORATION. Under curl|bash this
# script's stdin is the PIPE, and guided_browser_capture's PRE-LAUNCH gate
# tests isatty() on the INHERITED descriptor before it opens anything. The
# CAPTURE prompt itself already prefers /dev/tty (hardened 2026-07-29); its
# doorman does not. Handing the ride a real terminal on fd 0 satisfies both,
# and stays correct even after the gate is taught the same trick.
RIDE_RC=0
run_wrapped "$PY" scripts/mother_cat.py "$TRAIL_PATH" </dev/tty || RIDE_RC=$?

if [ "$RIDE_RC" -eq 0 ]; then
  cat <<'CARD'
--------------------------------------------------------------
   RIDE COMPLETE -- the bundle is on your clipboard
--------------------------------------------------------------
 1. Open any AI web chat (Claude, ChatGPT, Gemini).
 2. Paste (Cmd+V / Ctrl+V) and send.
 3. It will walk you through everything from here.

 The raw artifacts stayed on your machine, under
 browser_cache/. Nothing was uploaded by this script.
--------------------------------------------------------------
CARD
else
  echo "The ride stopped early (exit $RIDE_RC)."
  echo "   Any stop that already captured left its artifacts under"
  echo "   browser_cache/; the rider names them above. Re-run to ride again."
fi

exit "$RIDE_RC"
