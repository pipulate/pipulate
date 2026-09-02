#!/usr/bin/env bash
# Pipulate MCK Bootstrap v0.4.0 -- the Mother Cat Kata launcher
# =============================================================
#
# WHAT CHANGED IN v0.4.0 -- A TRAIL MAY CARRY ITS OWN URLS
#   walk.py now accepts a literal `url` on a stop as an alternative to
#   `url_env`. This launcher was not merely a URL SUPPLIER, it was a url_env
#   CONSUMER: it read s["url_env"] from every stop and treated an empty result
#   as "could not read the trail". A direct-URL trail makes that expression
#   raise KeyError, the stderr is discarded, and the launcher exits 2 with a
#   message describing a parse failure that never happened -- so the public
#   curl|bash walk would have stopped working the day the exemplar flipped.
#   The reader now prints a leading OK token, so "read the file" and "found
#   zero variables" no longer produce the identical output.
#
# WHAT CHANGED IN v0.3.0 -- TRAILS RESOLVE FROM A SEARCH PATH
#   v0.2.0 hardcoded assets/trails/, so every walk had to be committed to
#   the main repo. Client walks carry client names and churn several a day;
#   they belong in a private repo, not in a public checkout. The launcher
#   now searches Notebooks/Playground/trails, then Notebooks/Shared/trails,
#   then assets/trails -- local overrides canon, exactly the way PATH puts
#   /usr/local/bin ahead of /usr/bin. A stranger who fetched this launcher
#   has only the last lane, so public adventures resolve unchanged.
# THE COMMAND:  curl -fsSL https://pipulate.com/mck.sh | bash
#           or  curl -fsSL https://npvg.org/mck/<trail> | bash
#
# The path is the flag: the npvg.org route serves THIS file with the trail
# name stamped into the __MCK_TRAIL__ placeholder (nginx sub_filter), and a
# whitelabel may ride the same way through __MCK_WHITELABEL__. Local forms:
#
#   bash mck.sh public_walk
#   MCK_TRAIL=public_walk bash mck.sh
#   PIPULATE_WHITELABEL=clientname bash mck.sh
#
# WHAT CHANGED IN v0.2.0 -- THE SEED HATCHES THE CHICKEN
#
#   1. MARKER, NOT NAME. v0.1.0 searched $HOME/pipulate, so a whitelabel
#      install was invisible to its own launcher from anywhere except inside
#      it. Discovery now looks for the RIDER FILE -- scripts/mother_cat.py
#      beside flake.nix and assets/trails/ -- which is path = f(marker), never
#      path = f(guessed name). That is the DERIVED-PATH RULE pointed at the
#      installer, and it is the precondition for whitelabel namespacing
#      rather than a polish pass.
#
#   2. DETECT, OFFER, RESUME. v0.1.0 printed a card and exited 1 when no
#      workshop existed, so first contact was a dead end and every other
#      feature optimized a door nobody could open. The old refusal was argued
#      from HOW to install and then applied to WHETHER, which is the wrong
#      question. The HOW objection is answered STRUCTURALLY instead: the
#      installer is fetched TO DISK, its path, size and SHA-256 are printed,
#      the human is told they may read it before answering, and a NAMED FILE
#      is executed. No stranger's pipe is chained into another.
#
# WHAT THIS STILL NEVER DOES: chain one curl-pipe into another, read a
# credential, write outside the checkout's browser_cache/, or skip a fence.
#
# ENV OVERRIDES:
#   PIPULATE_ROOT             checkout location (else discovered)
#   PIPULATE_WHITELABEL       install folder name and namespace (default: pipulate)
#   PIPULATE_INSTALL_URL      where install.sh is fetched from
#   PIPULATE_MCK_ASSUME_YES   =1 skips the INSTALL and RIDE confirmations
#   PIPULATE_TRAIL_*_URL      pre-set any stop URL; built-in defaults use :=
#                             and therefore never override you
#
# FLAGS:
#   --where  print the discovered workshop and exit. READ-ONLY: no install
#            offer, no browser, no voice, no writes, no network. This is the
#            probe that makes marker discovery witnessable without needing a
#            fresh machine.
#   --yolo   skip the spoken rehearsal AND both confirmations. It does NOT
#            skip the CAPTURE fence at any stop, nor the DECANT gate at the
#            end, and no flag ever will. --yolo is typed BEFORE the ride, so
#            it cannot consent to the disposition of material that did not
#            exist when it was typed; and it was never unattended anyway,
#            because the CAPTURE fences already block.
#            CEREMONY IS SKIPPABLE; BARRIERS ARE NOT: a confirmation
#            authorizes a SEQUENCE, a fence authorizes each WRITE, and the
#            unfenced capture lane already exists under other names.
#
# EXIT CODES: 0 rode or stopped cleanly | 1 usage / no workshop | 2 trail refusal
if [ -z "${BASH_VERSION:-}" ]; then
  echo "Error: this script requires bash. Re-run with:"
  echo "   curl -fsSL https://pipulate.com/mck.sh | bash"
  exit 1
fi
set -euo pipefail
# --- Trail and whitelabel: positional > env > server-templated placeholder.
# The split spelling of each _ph is load-bearing: sub_filter replaces every
# contiguous placeholder in the served body, and the split literal is the one
# occurrence it can never touch, so templated-vs-untemplated stays detectable
# after substitution.
_tpl_trail='__MCK_TRAIL__'
_ph_trail='__MCK_''TRAIL__'
_tpl_label='__MCK_WHITELABEL__'
_ph_label='__MCK_''WHITELABEL__'
YOLO=0
WHERE_ONLY=0
MCK_POSITIONAL=""
for MCK_ARG in "$@"; do
  case "$MCK_ARG" in
    --yolo) YOLO=1 ;;
    --where) WHERE_ONLY=1 ;;
    -*) echo "Error: unknown option '$MCK_ARG' (only --yolo and --where are understood)" >&2; exit 1 ;;
    *) [ -n "$MCK_POSITIONAL" ] || MCK_POSITIONAL="$MCK_ARG" ;;
  esac
done
TRAIL_NAME="${MCK_POSITIONAL:-${MCK_TRAIL:-}}"
if [ -z "$TRAIL_NAME" ] && [ "$_tpl_trail" != "$_ph_trail" ]; then
  TRAIL_NAME="$_tpl_trail"
fi
TRAIL_NAME="${TRAIL_NAME:-public_walk}"
TRAIL_NAME="$(basename "$TRAIL_NAME")"
TRAIL_NAME="${TRAIL_NAME%.yaml}"
if ! printf '%s' "$TRAIL_NAME" | grep -qE '^[a-z][a-z0-9_]*$'; then
  echo "Error: trail name must match ^[a-z][a-z0-9_]*\$ -- got '$TRAIL_NAME'" >&2
  exit 1
fi
WHITELABEL="${PIPULATE_WHITELABEL:-}"
if [ -z "$WHITELABEL" ] && [ "$_tpl_label" != "$_ph_label" ]; then
  WHITELABEL="$_tpl_label"
fi
WHITELABEL="${WHITELABEL:-pipulate}"
WHITELABEL="$(basename "$WHITELABEL")"
if ! printf '%s' "$WHITELABEL" | grep -qE '^[A-Za-z][A-Za-z0-9_-]*$'; then
  echo "Error: whitelabel must match ^[A-Za-z][A-Za-z0-9_-]*\$ -- got '$WHITELABEL'" >&2
  exit 1
fi
# CASE-FOLDED IDENTITY (2026-08-01, two-writer conviction): whitelabel.txt has
# TWO writers with TWO spellings -- install.sh writes the name it was handed
# verbatim (lowercase by default), while the flake's runScript writes a
# capitalized "Pipulate" for any folder whose name lacks "botify". A clone-first
# workshop therefore carries the capital, and a case-sensitive compare against
# the lowercase default could never match it: every discovery on this machine
# answered from the head -n 1 fallback, which is indistinguishable from a match
# until a second workshop exists. The READER folds case because it cannot reach
# files already on disk that no writer patch can retroactively touch, and
# because the display path normalizes capitalization anyway, so the capital
# carries no information. tr, never the bash-4 lowercase expansion -- macOS
# ships bash 3.2.
WHITELABEL_LC="$(printf '%s' "$WHITELABEL" | tr '[:upper:]' '[:lower:]')"
# --- MARKER DISCOVERY --------------------------------------------------
# A workshop is identified by three TRACKED files, so a plain git clone
# qualifies. whitelabel.txt is deliberately NOT the marker: it is gitignored
# and written on first shell entry, so it does not exist yet on a clone. It
# is used only to disambiguate when several workshops are found.
_is_checkout() {
  [ -n "${1:-}" ] || return 1
  [ -f "$1/scripts/mother_cat.py" ] || return 1
  [ -f "$1/flake.nix" ] || return 1
  [ -d "$1/assets/trails" ] || return 1
  return 0
}
_whitelabel_of() {
  if [ -f "$1/whitelabel.txt" ]; then
    head -n 1 "$1/whitelabel.txt" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]'
  else
    basename "$1" | tr '[:upper:]' '[:lower:]'
  fi
}
find_checkouts() {
  if [ -n "${PIPULATE_ROOT:-}" ]; then
    if _is_checkout "$PIPULATE_ROOT"; then
      printf '%s\n' "$PIPULATE_ROOT"
    fi
  fi
  # Walk UP from here, so running inside any subdirectory of a workshop works.
  UPDIR="$PWD"
  while [ -n "$UPDIR" ] && [ "$UPDIR" != "/" ]; do
    if _is_checkout "$UPDIR"; then
      printf '%s\n' "$UPDIR"
    fi
    UPDIR="$(dirname "$UPDIR")"
  done
  # ONE bounded level under the usual parents. Deliberately no find(1): a
  # launcher must not sweep a stranger's home directory to introduce itself.
  for PARENT in "$HOME" "$HOME/repos" "$HOME/src" "$HOME/code" "$HOME/dev" "$HOME/Projects" "$HOME/projects"; do
    [ -d "$PARENT" ] || continue
    for CAND in "$PARENT"/*; do
      [ -d "$CAND" ] || continue
      if _is_checkout "$CAND"; then
        printf '%s\n' "$CAND"
      fi
    done
  done
  return 0
}
ROOT=""
ALL_CHECKOUTS=""
resolve_checkout() {
  ROOT=""
  ALL_CHECKOUTS="$(find_checkouts | awk 'NF && !seen[$0]++' || true)"
  [ -n "$ALL_CHECKOUTS" ] || return 0
  while IFS= read -r CANDIDATE; do
    [ -n "$CANDIDATE" ] || continue
    if [ "$(_whitelabel_of "$CANDIDATE")" = "$WHITELABEL_LC" ]; then
      ROOT="$CANDIDATE"
      break
    fi
  done <<EOF
$ALL_CHECKOUTS
EOF
  if [ -z "$ROOT" ]; then
    ROOT="$(printf '%s\n' "$ALL_CHECKOUTS" | head -n 1)"
  fi
  return 0
}
resolve_checkout
# --- --where: the read-only discovery probe ----------------------------
if [ "$WHERE_ONLY" -eq 1 ]; then
  if [ -z "$ROOT" ]; then
    echo "no workshop found (marker: scripts/mother_cat.py beside flake.nix and assets/trails/)"
    exit 1
  fi
  echo "$ROOT"
  OTHERS="$(printf '%s\n' "$ALL_CHECKOUTS" | grep -vxF "$ROOT" || true)"
  if [ -n "$OTHERS" ]; then
    echo "other workshops found (select one with PIPULATE_WHITELABEL):"
    printf '%s\n' "$OTHERS" | sed 's/^/  /'
  fi
  exit 0
fi
# --- No workshop: OFFER, install, resume -------------------------------
DID_INSTALL=0
offer_install() {
  INSTALL_URL="${PIPULATE_INSTALL_URL:-https://pipulate.com/install.sh}"
  TARGET="$HOME/$WHITELABEL"
  cat <<CARD
--------------------------------------------------------------
   NO WORKSHOP FOUND -- and that is fixable right here
--------------------------------------------------------------
 Nothing is installed on this machine yet, so there is nothing
 to ride. Here is exactly what happens if you say yes:
   1. the installer is fetched TO DISK from
        $INSTALL_URL
      You may read it before you answer. It is a shell script,
      not a binary, and the path is printed below.
   2. it unpacks Pipulate into
        $TARGET
   3. Nix builds the environment there. Nothing else on your
      machine is modified, and 'rm -rf' on that one folder is a
      complete uninstall.
   4. this launcher resumes and the walk begins.
--------------------------------------------------------------
CARD
  if ! command -v nix >/dev/null 2>&1; then
    echo " Note: Nix is not installed yet. The installer bootstraps it, and"
    echo "       Nix requires a NEW terminal afterward. If that happens, just"
    echo "       re-run this same command in the new terminal."
    echo ""
  fi
  if [ -e "$TARGET" ]; then
    echo "Refusing to install: $TARGET already exists but is not a workshop." >&2
    echo "   Move it aside, or set PIPULATE_WHITELABEL to a different name." >&2
    return 1
  fi
  if ! command -v curl >/dev/null 2>&1; then
    echo "Refusing to install: curl is not on PATH." >&2
    return 1
  fi
  TMP_INSTALLER="$(mktemp "${TMPDIR:-/tmp}/pipulate-install.XXXXXX")"
  if ! curl -fsSL "$INSTALL_URL" -o "$TMP_INSTALLER"; then
    echo "Could not fetch the installer from $INSTALL_URL" >&2
    rm -f "$TMP_INSTALLER"
    return 1
  fi
  INSTALLER_LINES="$(wc -l < "$TMP_INSTALLER" | tr -d ' ')"
  INSTALLER_SUM=""
  if command -v sha256sum >/dev/null 2>&1; then
    INSTALLER_SUM="$(sha256sum "$TMP_INSTALLER" | cut -d' ' -f1)"
  elif command -v shasum >/dev/null 2>&1; then
    INSTALLER_SUM="$(shasum -a 256 "$TMP_INSTALLER" | cut -d' ' -f1)"
  fi
  echo " installer : $TMP_INSTALLER"
  echo " lines     : $INSTALLER_LINES"
  if [ -n "$INSTALLER_SUM" ]; then
    echo " sha256    : $INSTALLER_SUM"
  fi
  echo ""
  echo " To read it first, open another terminal and run:"
  echo "   less $TMP_INSTALLER"
  echo ""
  if [ "$YOLO" -eq 1 ] || [ "${PIPULATE_MCK_ASSUME_YES:-0}" = "1" ]; then
    echo "Confirmation skipped. Installing to $TARGET."
  else
    printf 'Type INSTALL and press Enter to proceed (anything else stops here).\nINSTALL> '
    ANSWER=""
    if ! IFS= read -r ANSWER </dev/tty; then
      echo "" >&2
      echo "No controlling terminal to confirm on (/dev/tty unavailable)." >&2
      echo "   Nothing was installed. Run the installer yourself:" >&2
      echo "     bash $TMP_INSTALLER $WHITELABEL" >&2
      return 1
    fi
    if [ "$ANSWER" != "INSTALL" ]; then
      echo "Stopped by human. Nothing was installed."
      echo "   The installer is still at $TMP_INSTALLER if you want to read it."
      return 1
    fi
  fi
  # PIPULATE_INSTALL_ONLY asks the installer to hydrate and RETURN instead of
  # opening an interactive workshop. An older served installer ignores the
  # variable and opens the workshop as it always did; this launcher resumes
  # when the human leaves it. Either way nothing breaks.
  # /dev/tty is handed over because that older path needs a real terminal.
  INSTALL_RC=0
  if [ -c /dev/tty ]; then
    PIPULATE_INSTALL_ONLY=1 bash "$TMP_INSTALLER" "$WHITELABEL" </dev/tty || INSTALL_RC=$?
  else
    PIPULATE_INSTALL_ONLY=1 bash "$TMP_INSTALLER" "$WHITELABEL" || INSTALL_RC=$?
  fi
  rm -f "$TMP_INSTALLER"
  if [ "$INSTALL_RC" -ne 0 ]; then
    echo "The installer exited $INSTALL_RC. Nothing further attempted." >&2
    return 1
  fi
  DID_INSTALL=1
  return 0
}
if [ -z "$ROOT" ]; then
  if ! offer_install; then
    exit 1
  fi
  resolve_checkout
  if [ -z "$ROOT" ]; then
    cat <<'CARD'
--------------------------------------------------------------
   INSTALL FINISHED, BUT NO WORKSHOP IS VISIBLE YET
--------------------------------------------------------------
 The most common reason is that Nix was just bootstrapped and
 needs a fresh terminal before it is on your PATH.
 Close this terminal, open a NEW one, and run the same command
 again. Nothing needs to be undone first.
--------------------------------------------------------------
CARD
    exit 1
  fi
fi
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  cat <<CARD
--------------------------------------------------------------
   WORKSHOP FOUND, BUT NOT HYDRATED YET
--------------------------------------------------------------
 $ROOT
 The Python environment has not been built there yet. Build it
 once, the normal way, then re-run this launcher:
   cd $ROOT
   nix develop
 (That first entry is also what turns the folder into a git
 repository and starts the auto-updates.)
--------------------------------------------------------------
CARD
  exit 1
fi
# --- TRAIL SEARCH PATH (local overrides canon) -------------------------
# Ordered like PATH: the first lane that has the file wins. The two churn
# lanes are gitignored, so a client walk authored there can never reach the
# public repo -- that is a structural property, not a policy anyone has to
# remember. `mothercat <repo-relative-path>` has always accepted these
# lanes (mother_cat.ride anchors to REPO_ROOT); this teaches the URL
# launcher the same thing.
TRAIL_SEARCH_DIRS="Notebooks/Playground/trails Notebooks/Shared/trails assets/trails"
TRAIL_PATH=""
for TRAIL_DIR in $TRAIL_SEARCH_DIRS; do
  if [ -f "$TRAIL_DIR/${TRAIL_NAME}.yaml" ]; then
    TRAIL_PATH="$TRAIL_DIR/${TRAIL_NAME}.yaml"
    break
  fi
done
if [ -z "$TRAIL_PATH" ]; then
  echo "Error: no trail named '${TRAIL_NAME}' in any search lane." >&2
  echo "   Searched, in order:" >&2
  for TRAIL_DIR in $TRAIL_SEARCH_DIRS; do
    echo "     $ROOT/$TRAIL_DIR/" >&2
  done
  echo "   Available:" >&2
  for TRAIL_DIR in $TRAIL_SEARCH_DIRS; do
    # set -euo pipefail + a missing lane = the script DIES HERE. An
    # unmatched glob makes bash hand ls the literal pattern, ls exits 2,
    # pipefail propagates it, set -e kills the run -- so the FIRST absent
    # lane suppressed the listing for every lane after it. Convicted
    # 2026-08-05 by the AFTER receipt: "Available:" printed with nothing
    # under it while four YAMLs sat in assets/trails. Guard the directory
    # AND neutralize the pipeline; either alone is enough, both is cheap.
    [ -d "$TRAIL_DIR" ] || continue
    ls "$TRAIL_DIR"/*.yaml 2>/dev/null | sed 's#^#     #' >&2 || true
  done
  exit 1
fi
# Which lane won is a receipt, not chatter: a Playground trail silently
# shadowing a tracked one is exactly the surprise this line prevents.
echo "Trail resolved: $TRAIL_PATH"
# The trail declares its own url_env names; read them from the trail. Trails
# are the JSON subset of YAML 1.2, so json.load is correct here.
# ZERO VARIABLES IS A VALID ANSWER NOW. A stop may carry a literal url instead
# of a url_env, so a whole trail can legitimately name nothing. The leading OK
# token is what separates "the file parsed and there were none" from "the file
# did not parse at all" -- two worlds that used to print one empty string and
# get one wrong error message.
# REQUIRED ONLY (2026-09-02, TWO PRE-FLIGHTS, ONE OUTER). A stop marked
# `optional: true` is skipped by the rider when its variable is unset, so this
# shell ring must not refuse on it: the shell check may only ever be a SUBSET
# of the rider's, names and never verdicts, and the rider prints the skips.
TRAIL_READ="$("$PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print("OK"); [print(s["url_env"]) for s in d["stops"] if s.get("url_env") and not s.get("optional")]' "$TRAIL_PATH" 2>/dev/null || true)"
if [ -z "$TRAIL_READ" ]; then
  echo "Error: could not read $TRAIL_PATH" >&2
  exit 2
fi
URL_ENVS="$(printf '%s\n' "$TRAIL_READ" | tail -n +2)"
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
# We cannot re-exec THIS script under curl|bash (there is no file to re-exec:
# $0 is 'bash'), so we wrap only the two ride commands.
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
if [ "$YOLO" -eq 1 ]; then
  echo "--yolo: skipping the spoken rehearsal and the RIDE confirmation."
  echo "        NOT skipped, and not skippable by any flag: the CAPTURE fence"
  echo "        at every stop. Nothing is written until you type the word."
  echo "        Also NOT skipped: the DECANT gate at the end. Nothing leaves"
  echo "        this machine until you type that word too."
fi
if [ "$YOLO" -eq 0 ]; then
cat <<CARD
--------------------------------------------------------------
   MOTHER CAT KATA -- rehearsal first, nothing moves
--------------------------------------------------------------
 workshop : $ROOT
 trail    : $TRAIL_NAME
 file     : $ROOT/$TRAIL_PATH
 The next pass READS the walk aloud. During it:
   - no browser opens
   - no file is written
   - no credential is read
 Listen to the whole thing, then decide.
--------------------------------------------------------------
CARD
run_wrapped "$PY" scripts/mother_cat.py "$TRAIL_PATH" --dry-narrate
fi
if [ "$YOLO" -eq 1 ] || [ "${PIPULATE_MCK_ASSUME_YES:-0}" = "1" ]; then
  echo "Confirmation skipped. Every CAPTURE fence still stands."
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
# CAPTURE prompt itself already prefers /dev/tty; its doorman does not.
# Handing the ride a real terminal on fd 0 satisfies both, and stays correct
# even after the gate is taught the same trick.
RIDE_RC=0
run_wrapped "$PY" scripts/mother_cat.py "$TRAIL_PATH" </dev/tty || RIDE_RC=$?
if [ "$RIDE_RC" -eq 0 ]; then
  cat <<'CARD'
--------------------------------------------------------------
   RIDE COMPLETE
--------------------------------------------------------------
 Every stop that OPENED produced a capture receipt. An optional
 stop whose URL you had not exported was skipped; the rider
 said which, above, and the bundle lists it as skipped.

 Whether the bundle LEFT this machine depends on the DECANT
 gate you just answered. This script cannot see your clipboard,
 so it does not claim to. Read the rider's own last line:

   AUTHORIZED  it is on your clipboard. Open any AI web chat
               (Claude, ChatGPT, Gemini), paste and send.
   DECLINED    nothing was copied, and the rider printed the
   REFUSED     exact directories your artifacts are sitting in.
 The raw artifacts stayed on your machine, under
 browser_cache/. Nothing was uploaded by this script.
--------------------------------------------------------------
CARD
  if [ "$DID_INSTALL" -eq 1 ]; then
    echo " One more thing, since this machine was installed just now:"
    echo "   cd $ROOT && nix develop"
    echo " That first plain entry turns the folder into a git repository and"
    echo " starts the auto-updates. The ride did not need it; the future does."
    echo ""
  fi
else
  echo "The ride stopped early (exit $RIDE_RC)."
  echo "   Any stop that already captured left its artifacts under"
  echo "   browser_cache/; the rider names them above. Re-run to ride again."
fi
exit "$RIDE_RC"
