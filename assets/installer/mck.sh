#!/usr/bin/env bash
# Pipulate MCK Bootstrap v0.7.0 -- the Mother Cat Kata launcher
# =============================================================
#
# WHAT CHANGED IN v0.7.0 -- A TRAIL IS YAML, AND MAY CARRY AN INTRODUCTION
#   (2026-10-04) The trail is read by walk.load_trail, the rider's own loader,
#   so a YAML trail and a JSON one read alike and a bad trail says why; .yaml
#   is looked up before .json. `walk NAME intro` asks the rider to play the
#   trail's introduction before its stops; a plain `walk NAME` skips it.
#
# WHAT CHANGED IN v0.6.0 -- A WORD ROUTES (2026-09-29)
#   walk <name> args: the first word is looked up as an executable under a
#   private tier's walks/ folder (personal, then corporate) and run with
#   everything after the word, untouched; no tier holds it, the word is a
#   trail, as before. Options before the word are the launcher's; options
#   after it belong to the walk, or reach the launcher only after the lookup
#   says trail (so --yolo after a trail name governs the ride and not the
#   install offer, which asks; PIPULATE_MCK_ASSUME_YES=1 skips it). --where
#   is the launcher's wherever it sits. This file names no walk: a
#   proprietary walk is a name in a private repo, never a word in the flake.
#
# WHAT CHANGED IN v0.5.0 -- THE EXPORTS FILE IS FOUND, NOT TYPED
#   bookmark_import.py has written <name>.exports.sh beside every surface
#   since 2026-08-08, and nothing read it: the human sourced it by hand or
#   the ring refused. The launcher now resolves it the way the rider does --
#   --exports=PATH, else the sibling beside the trail -- reads NAMES from it
#   so the ring can pass, and hands the path to the rider, which loads the
#   VALUES with environment-over-file precedence. This file still never
#   evals a line of a file that holds addresses.
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
#   now searches Workshop/personal/trails, then Workshop/shared/trails,
#   then assets/trails -- local overrides canon, exactly the way PATH puts
#   /usr/local/bin ahead of /usr/bin. A stranger who fetched this launcher
#   has only the last lane, so public adventures resolve unchanged.
# THE COMMAND:  curl -fsSL https://pipulate.com/mck.sh | bash
#
# THE TWO PLACEHOLDERS (2026-10-02, read off configuration.nix and a 404):
# __MCK_TRAIL__ and __MCK_WHITELABEL__ below are where a door would stamp a
# trail name and an install name into this file as it serves it (nginx
# sub_filter), the way npvg.org and qamy.ai stamp install.sh's
# __INSTALL_DEFAULT_NAME__. No door does it yet: configuration.nix has no
# /mck/ location, and https://npvg.org/mck/public_walk answers 404.
# Unstamped, the trail is public_walk and the name is pipulate. Local forms:
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
# credential, or skip a fence. The rider writes browser_cache/ plus private
# per-run captures.md archives under data/captures/ in the same checkout.
#
# ENV OVERRIDES:
#   PIPULATE_ROOT             checkout location (else discovered)
#   PIPULATE_WHITELABEL       install folder name and namespace (default: pipulate)
#   PIPULATE_INSTALL_URL      where install.sh is fetched from
#   PIPULATE_MCK_ASSUME_YES   =1 skips INSTALL and the menu; rehearses then rides
#   PIPULATE_TRAIL_*_URL      pre-set any stop URL; built-in defaults use :=
#                             and therefore never override you
#
# Plain invocation offers Practice, Sample walk, Select a walk, or Exit before narration.
# A walk named on the command line (walk <name>) rides without that menu.
# FLAGS:
#   --exports=PATH  the exports file for this ride when it is NOT the
#            <trail>.exports.sh sibling bookmark_import.py writes. This
#            launcher reads NAMES from it and nothing else; the rider loads
#            the values. A relative PATH resolves from the workshop root.
#   --where  print the discovered workshop and exit. READ-ONLY: no install
#            offer, no browser, no voice, no writes, no network. This is the
#            probe that makes marker discovery witnessable without needing a
#            fresh machine.
#   --yolo   skip INSTALL confirmation and the menu; every page still
#            waits for Enter. ASSUME_YES practices first, then walks.
#
# EXIT CODES: 0 rode or explicit stop; nonzero usage, refusal, input or rider failure.
if [ -z "${BASH_VERSION:-}" ]; then
  echo "This script needs bash. Run it again with bash, not sh."
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
WITH_INTRO=0
MCK_POSITIONAL=""
EXPORTS_OVERRIDE=""
# THE ROUTE IS THE FIRST WORD (v0.6.0). Everything after the first positional is
# held back, untouched, until the workshop is found and the word is looked up:
# a routed walk owns its own arguments (a ticket key, -n, --fresh, a bare -), so
# this loop must not refuse them; a trail gets them parsed by the same case,
# exactly as before, once the lookup says the word is a trail. --where is the
# launcher's wherever it sits, because it asks about the workshop and never
# about a walk. Options before the word are parsed here as they always were.
HELD_ARGS=()
mck_option() {
  case "$1" in
    --yolo) YOLO=1 ;;
    --where) WHERE_ONLY=1 ;;
    --exports=*) EXPORTS_OVERRIDE="${1#--exports=}" ;;
    -*) echo "Error: unknown option '$1' (only --yolo, --where and --exports=PATH are understood)" >&2; exit 1 ;;
    intro)
      # The second word of `walk NAME intro` (v0.7.0). A routed walk never
      # gets here with its words: they are held and handed to it untouched.
      if [ -n "$MCK_POSITIONAL" ]; then WITH_INTRO=1; else MCK_POSITIONAL="$1"; fi ;;
    *) [ -n "$MCK_POSITIONAL" ] || MCK_POSITIONAL="$1" ;;
  esac
}
for MCK_ARG in "$@"; do
  if [ -n "$MCK_POSITIONAL" ] && [ "$MCK_ARG" != "--where" ]; then
    HELD_ARGS+=("$MCK_ARG")
  else
    mck_option "$MCK_ARG"
  fi
done
TRAIL_NAME="${MCK_POSITIONAL:-${MCK_TRAIL:-}}"
if [ -z "$TRAIL_NAME" ] && [ "$_tpl_trail" != "$_ph_trail" ]; then
  TRAIL_NAME="$_tpl_trail"
fi
TRAIL_NAME="${TRAIL_NAME:-public_walk}"
TRAIL_NAME="$(basename "$TRAIL_NAME")"
TRAIL_NAME="${TRAIL_NAME%.json}"
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
# A PATH AS A PERSON READS IT (2026-10-02): ~ for the home folder, which also
# keeps a narrow window from wrapping it. Display only, never parsed.
_shown() {
  case "$1" in
    "$HOME"/*) printf '~%s' "${1#"$HOME"}" ;;
    *) printf '%s' "$1" ;;
  esac
}
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
    printf '%s\n' "$OTHERS"
  fi
  exit 0
fi
# --- No workshop: OFFER, install, resume -------------------------------
offer_install() {
  INSTALL_URL="${PIPULATE_INSTALL_URL:-https://pipulate.com/install.sh}"
  TARGET="$HOME/$WHITELABEL"
  # THE OFFER COMES LAST (2026-10-02, the operator's ruling): a refusal or a
  # failed download ends the run before any of it prints, so the screen ends
  # on the question and the file it is about. No box, no indent. OUTSIDE is
  # every place beyond the folder that the install and the walk write: Nix's
  # store and cache, uv's cache, the voice answer and the Mac's shadow posts
  # (flake.nix), and the folder undetected-chromedriver makes each time it
  # starts a browser. The deploy key has its own line. rm -rf on the folder
  # leaves all of these; until today this card called it a complete uninstall.
  if [ -e "$TARGET" ]; then
    echo "Not installing: $(_shown "$TARGET") is already there and is not a workshop. Move it aside, or set PIPULATE_WHITELABEL to another name." >&2
    return 1
  fi
  if ! command -v curl >/dev/null 2>&1; then
    echo "Not installing: curl is not on PATH." >&2
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
  OUTSIDE="/nix/store, ~/.cache/nix, ~/.cache/uv, ~/.config/pipulate"
  if [ "$(uname -s)" = "Darwin" ]; then
    OUTSIDE="$OUTSIDE, ~/.local/share/pipulate and ~/Library/Application Support/undetected_chromedriver"
  else
    OUTSIDE="$OUTSIDE and ~/.local/share/undetected_chromedriver"
  fi
  printf '\nThere is no workshop on this computer yet, so the walk can install one first.\n'
  printf '\nThe installer is saved on this computer. To read it before you answer, open another window and type:\nless %s\n' "$(_shown "$TMP_INSTALLER")"
  printf 'It is %s lines%s.\n' "$INSTALLER_LINES" "${INSTALLER_SUM:+; sha256 $INSTALLER_SUM}"
  printf '\nIt unpacks Pipulate into %s.\n' "$(_shown "$TARGET")"
  if ! command -v nix >/dev/null 2>&1; then
    echo "Nix is not installed yet: the installer adds it first, a change to the whole system that says so when it runs, and then you run this same command again in a new window."
  fi
  echo "Outside that folder it writes $OUTSIDE."
  echo "If there is no ~/.ssh/id_rsa, it saves a read-only deploy key there, sets ssh to use it for github.com in ~/.ssh/config, and adds github.com to ~/.ssh/known_hosts."
  echo "rm -rf $(_shown "$TARGET") removes the folder; the files outside it stay until you remove them."
  if [ "$YOLO" -eq 1 ] || [ "${PIPULATE_MCK_ASSUME_YES:-0}" = "1" ]; then
    printf '\nInstalling now; the question is skipped.\n'
  else
    printf '\nType INSTALL and press Enter to install. Anything else stops here.\nINSTALL> '
    ANSWER=""
    # 2>/dev/null comes BEFORE </dev/tty, so a terminal that cannot be
    # opened is this branch's to report and not bash's (a receipt of
    # 2026-10-02 printed "line 324: /dev/tty: No such device or address").
    if ! IFS= read -r ANSWER 2>/dev/null </dev/tty; then
      printf '\nThere is no keyboard here to answer on, so nothing was installed. To install by hand, type:\nbash %s %s\n' "$(_shown "$TMP_INSTALLER")" "$WHITELABEL" >&2
      return 1
    fi
    # INSTALL IN ANY CASE (2026-10-02, the operator's ruling): the word asks
    # for a deliberate act, and its capitals were never the safety.
    if [ "$(printf '%s' "$ANSWER" | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]')" != "INSTALL" ]; then
      echo "Nothing was installed. The installer is still at $(_shown "$TMP_INSTALLER")."
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
  return 0
}
if [ -z "$ROOT" ]; then
  if ! offer_install; then
    exit 1
  fi
  resolve_checkout
  if [ -z "$ROOT" ]; then
    # The usual reason: the installer has just added Nix, and this window
    # opened before it did; the installer's own lines above say so.
    printf '\nNext: open a new window and run the same command again.\n'
    exit 1
  fi
fi
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  printf 'The workshop at %s is not built yet.\nNext: cd %s && nix develop, then type walk.\n' "$(_shown "$ROOT")" "$(_shown "$ROOT")" >&2
  exit 1
fi
# --- THE WALK ROUTER (v0.6.0): a word routes; a flag does not ---------------
# `walk <name> args`: the first word is looked up as an executable under the
# private tiers' walks/ folders, local overriding canon the way the trail lanes
# below do, and when one is found it runs with everything held back after the
# word; a walk writes context.txt itself, the way the rider does, and its exit
# code is this launcher's. No tier holds it: the word is a trail, and the held
# arguments are parsed as launcher options exactly as they were before this
# block existed. The tiers are gitignored, so the names live in private repos
# and this public launcher knows none of them; a checkout with no walks/ folder
# routes nothing and behaves as it always did. shared/ is not a lane: its
# grammar is shared/<name>/, and a walk handed to a teammate is copied into
# their personal tier or promoted to corporate. NAMED LIMITATION: a routed walk
# runs in the shell this launcher was typed in, so from outside the workshop
# shell a walk that needs a connector word (jira, botify) refuses by that
# word's name; the .#quiet wrap the rider gets below is not yet extended here.
WALK_SEARCH_DIRS="Workshop/personal/walks Workshop/corporate/walks"
for WALK_DIR in $WALK_SEARCH_DIRS; do
  if [ -f "$WALK_DIR/$TRAIL_NAME" ] && [ -x "$WALK_DIR/$TRAIL_NAME" ]; then
    echo "Walk resolved: $WALK_DIR/$TRAIL_NAME" >&2
    if [ ${#HELD_ARGS[@]} -gt 0 ]; then
      exec "$WALK_DIR/$TRAIL_NAME" "${HELD_ARGS[@]}"
    fi
    exec "$WALK_DIR/$TRAIL_NAME"
  fi
done
if [ ${#HELD_ARGS[@]} -gt 0 ]; then
  for MCK_ARG in "${HELD_ARGS[@]}"; do
    mck_option "$MCK_ARG"
  done
fi
# --- TRAIL SEARCH PATH (local overrides canon) -------------------------
# Ordered like PATH: the first lane that has the file wins. The two churn
# lanes are gitignored, so a client walk authored there can never reach the
# public repo -- that is a structural property, not a policy anyone has to
# remember. `mothercat <repo-relative-path>` has always accepted these
# lanes (mother_cat.ride anchors to REPO_ROOT); this teaches the URL
# launcher the same thing.
TRAIL_SEARCH_DIRS="Workshop/personal/trails Workshop/shared/trails assets/trails"
TRAIL_PATH=""
# Reserved explicit name; a missing private plan must not fall back to a demo.
if [ "$TRAIL_NAME" = "plan" ]; then
  TRAIL_PATH="$("$PY" scripts/mother_cat.py --plan-path)"
fi
for TRAIL_DIR in $TRAIL_SEARCH_DIRS; do
  [ -z "$TRAIL_PATH" ] || break
  if [ -f "$TRAIL_DIR/${TRAIL_NAME}.yaml" ]; then
    TRAIL_PATH="$TRAIL_DIR/${TRAIL_NAME}.yaml"
    break
  fi
  if [ -f "$TRAIL_DIR/${TRAIL_NAME}.json" ]; then
    TRAIL_PATH="$TRAIL_DIR/${TRAIL_NAME}.json"
    break
  fi
done
if [ -z "$TRAIL_PATH" ]; then
  # EVERY WORD THAT WORKS, ONCE (2026-10-02, the operator's ruling): routed
  # walks first, the way the router looks, then trails lane by lane; a name
  # two lanes share is listed once, and only names the check above accepts
  # are listed. No ls in a pipe: a glob that matches nothing fails the -f
  # test and is skipped, so a missing lane cannot stop the list (the
  # 2026-08-05 conviction, answered without ls).
  WORDS=""
  for LIST_DIR in $WALK_SEARCH_DIRS $TRAIL_SEARCH_DIRS; do
    [ -d "$LIST_DIR" ] || continue
    for LIST_FILE in "$LIST_DIR"/*; do
      [ -f "$LIST_FILE" ] || continue
      LIST_WORD="$(basename "$LIST_FILE")"
      case "$LIST_DIR" in
        */walks) [ -x "$LIST_FILE" ] || continue ;;
        *)
          case "$LIST_WORD" in
            *.json|*.yaml) LIST_WORD="${LIST_WORD%.*}" ;;
            *) continue ;;
          esac
          ;;
      esac
      printf '%s' "$LIST_WORD" | grep -qE '^[a-z][a-z0-9_]*$' || continue
      case " $WORDS " in *" $LIST_WORD "*) continue ;; esac
      WORDS="${WORDS:+$WORDS }$LIST_WORD"
    done
  done
  echo "No walk is named $TRAIL_NAME. Type walk and one of these: $WORDS" >&2
  exit 1
fi
# Which lane won is a receipt only when it is a surprise: a private trail
# shadowing a tracked one. The bundled lane is the expected answer and says
# nothing (2026-10-02, the operator's ruling: the ordinary case is silent).
case "$TRAIL_PATH" in
  assets/trails/*) ;;
  *)
    for SHADOWED in "assets/trails/${TRAIL_NAME}.json" "assets/trails/${TRAIL_NAME}.yaml"; do
      if [ -f "$SHADOWED" ]; then
        echo "Trail resolved: $TRAIL_PATH, in place of $SHADOWED"
        break
      fi
    done
    ;;
esac
# --- EXPORTS FILE (2026-09-05): the same derivation the rider runs ---------
# bookmark_import.py writes <name>.exports.sh beside <name>.walk.md and
# walk_compile.py puts <name>.json beside both, so the file a trail needs is
# a function of the trail's own path. Explicit --exports=PATH wins and a miss
# is an ERROR, because the human named it; the sibling is next and a miss is
# silence, because nothing promised it. A relative path resolves from the
# workshop root (we cd'd there above), never from where you stood.
# THIS SHELL LOADS NOTHING. It reads NAMES with grep -- never an eval of a
# file that holds addresses -- so the ring below can treat a declared name as
# satisfied. The rider loads the VALUES, environment over file, and is the
# verdict; this ring stays a SUBSET of it, names and never verdicts, exactly
# as the url_env ring already is. The rider says which file it read.
TRAIL_STEM="${TRAIL_PATH%.json}"
TRAIL_STEM="${TRAIL_STEM%.yaml}"
EXPORTS_PATH="$EXPORTS_OVERRIDE"
if [ -z "$EXPORTS_PATH" ] && [ -f "$TRAIL_STEM.exports.sh" ]; then
  EXPORTS_PATH="$TRAIL_STEM.exports.sh"
fi
EXPORTS_DECLARED=""
if [ -n "$EXPORTS_PATH" ]; then
  if [ ! -f "$EXPORTS_PATH" ]; then
    echo "This walk cannot run: --exports names $EXPORTS_PATH, which is not there. A relative path starts at the workshop folder." >&2
    exit 2
  fi
  EXPORTS_DECLARED="$(grep -oE '^[[:space:]]*(export[[:space:]]+)?[A-Z][A-Z0-9_]*=' "$EXPORTS_PATH" | sed -E 's/^[[:space:]]*(export[[:space:]]+)?//; s/=$//' || true)"
fi
# The trail declares its own url_env names; walk.load_trail reads them, the
# loader the rider uses, so YAML and JSON read alike and a refusal says why.
# ZERO VARIABLES IS A VALID ANSWER NOW. A stop may carry a literal url instead
# of a url_env, so a whole trail can legitimately name nothing. The leading OK
# token is what separates "the file parsed and there were none" from "the file
# did not parse at all" -- two worlds that used to print one empty string and
# get one wrong error message.
# REQUIRED ONLY (2026-09-02, TWO PRE-FLIGHTS, ONE OUTER). A stop marked
# `optional: true` is skipped by the rider when its variable is unset, so this
# shell ring must not refuse on it: the shell check may only ever be a SUBSET
# of the rider's, names and never verdicts, and the rider prints the skips.
TRAIL_READ="$("$PY" -c '
import sys
sys.path.insert(0, "scripts")
import walk
try:
    trail = walk.load_trail(walk.Path(sys.argv[1]))
except walk.TrailError as exc:
    print("ERR", exc)
    raise SystemExit(0)
print("OK")
for stop in trail["stops"]:
    if stop.get("url_env") and not stop.get("optional"):
        print(stop["url_env"])
' "$TRAIL_PATH" 2>/dev/null || true)"
case "$TRAIL_READ" in
  OK*) ;;
  "ERR "*) echo "This walk cannot run: ${TRAIL_READ#ERR }" >&2; exit 2 ;;
  *) echo "Error: could not read $TRAIL_PATH" >&2; exit 2 ;;
esac
URL_ENVS="$(printf '%s\n' "$TRAIL_READ" | tail -n +2)"
MISSING=""
for VAR in $URL_ENVS; do
  printenv "$VAR" >/dev/null 2>&1 && continue
  printf '%s\n' "$EXPORTS_DECLARED" | grep -qx "$VAR" && continue
  case "$MISSING " in *" $VAR "*) continue ;; esac
  MISSING="$MISSING $VAR"
done
if [ -n "$MISSING" ]; then
  # THE RIDER'S WORDS (2026-10-02): this ring refuses first, so the menu
  # never opens for a walk that cannot run, and it says exactly what the
  # rider would, so one situation has one wording.
  printf '\nThis walk needs addresses that are not set. Type these lines with the real addresses, or put them in %s.exports.sh, then start the walk again:\n' "$TRAIL_STEM" >&2
  for VAR in $MISSING; do
    printf "export %s='https://...'\n" "$VAR" >&2
  done
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
    echo "Entering the workshop for this walk; the first time takes a few seconds."
    # The walk ends outside the workshop shell, where context is not a word
    # yet, so the rider's last line names the way in (2026-10-02).
    export PIPULATE_WALK_OUTSIDE=1
  else
    echo "This window cannot find nix. Open a new window, type cd $(_shown "$ROOT") && nix develop, then type walk." >&2
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
# ONE SPELLING FOR BOTH RIDER CALLS, so the rehearsal and the ride can never
# read different exports files. The flag rides only when a file resolved; the
# empty case expands no array (bash 3.2 + set -u, the trap NIXWRAP dodges).
run_rider() {
  # `walk NAME intro` (v0.7.0) asks for the introduction, practice included.
  if [ "$WITH_INTRO" -eq 1 ]; then
    set -- --with-intro "$@"
  fi
  if [ -n "$EXPORTS_PATH" ]; then
    run_wrapped "$PY" scripts/mother_cat.py "$TRAIL_PATH" --exports "$EXPORTS_PATH" "$@"
  else
    run_wrapped "$PY" scripts/mother_cat.py "$TRAIL_PATH" "$@"
  fi
}
# PRACTICE HAS NO INPUT CHECKPOINT (2026-09-15, deed 1417): the installed
# player left inherited stdin nonblocking. Both rehearsals get /dev/null,
# not the menu or caller input; fd 3 is closed in the child as well. This
# does not change shared voice callers or the real ride's /dev/tty input.
if [ "$YOLO" -eq 1 ]; then
  echo "Starting the walk. Each page still waits for Enter."
elif [ "${PIPULATE_MCK_ASSUME_YES:-0}" = "1" ]; then
  echo "Practice first, then the walk. Each page still waits for Enter."
  run_rider --dry-narrate </dev/null 3<&-
elif [ -n "$MCK_POSITIONAL" ] && [ "$TRAIL_NAME" != "public_walk" ]; then
  # A NAMED WALK RIDES (2026-10-02, the operator's ruling): walk <name> has
  # already made the choice the menu would ask for. The sample keeps its menu
  # however it is named, and so do MCK_TRAIL and a door's stamped trail. Each
  # page still waits for Enter.
  :
else
  if ! { exec 3</dev/tty; } 2>/dev/null; then
    echo "No keyboard to read here; type walk at the command line." >&2
    exit 1
  fi
  # NO INDENT IN WHAT A PERSON READS (2026-10-02, the operator's ruling): a
  # narrow window wraps a long line back to column 0, so an indent only looks
  # right on a wide one. Blank lines separate; nothing on screen is indented.
  while :; do
    printf '\n1  Practice - read the steps; no pages open.\n'
    printf '2  Sample walk - pops pages open.\n'
    printf '3  Select a walk.\n'
    printf 'q  Exit (Enter also exits).\nChoice: '
    ANSWER=""
    # Preserve failure instead of converting it into a successful stop.
    # Bash read does not expose errno here: EOF and read errors both stop
    # nonzero; only a successfully read q/Q or blank line is a clean exit.
    READ_RC=0
    IFS= read -r ANSWER <&3 || READ_RC=$?
    if [ "$READ_RC" -ne 0 ]; then
      printf '\nMenu input ended or failed (read exit %s). No real walk started.\n' "$READ_RC" >&2
      exec 3<&-
      exit "$READ_RC"
    fi
    case "$ANSWER" in
      1)
        PRACTICE_RC=0
        run_rider --dry-narrate </dev/null 3<&- || PRACTICE_RC=$?
        if [ "$PRACTICE_RC" -ne 0 ]; then
          # 130 is Ctrl+C, and the rider has already said Stopped.
          [ "$PRACTICE_RC" -eq 130 ] || echo "Practice stopped (exit $PRACTICE_RC). No real walk started." >&2
          exec 3<&-
          exit "$PRACTICE_RC"
        fi
        ;;
      3)
        WALK_NAMES=()
        WALK_PATHS=()
        for WALK_DIR in $WALK_SEARCH_DIRS; do
          [ -d "$WALK_DIR" ] || continue
          for WALK_FILE in "$WALK_DIR"/*; do
            [ -f "$WALK_FILE" ] && [ -x "$WALK_FILE" ] || continue
            WALK_NAME="$(basename "$WALK_FILE")"
            WALK_SEEN=0
            WALK_I=0
            while [ "$WALK_I" -lt "${#WALK_NAMES[@]}" ]; do
              [ "${WALK_NAMES[$WALK_I]}" = "$WALK_NAME" ] && WALK_SEEN=1
              WALK_I=$((WALK_I + 1))
            done
            [ "$WALK_SEEN" -eq 0 ] || continue
            WALK_NAMES+=("$WALK_NAME")
            WALK_PATHS+=("$WALK_FILE")
          done
        done
        printf '\nInstalled walks:\n'
        printf '1  Sample walk - pops pages open.\n'
        WALK_I=0
        while [ "$WALK_I" -lt "${#WALK_NAMES[@]}" ]; do
          printf '%s  %s\n' "$((WALK_I + 2))" "${WALK_NAMES[$WALK_I]}"
          WALK_I=$((WALK_I + 1))
        done
        printf 'q  Back (Enter also goes back).\nChoice: '
        PICK=""
        READ_RC=0
        IFS= read -r PICK <&3 || READ_RC=$?
        if [ "$READ_RC" -ne 0 ]; then
          printf '\nMenu input ended or failed (read exit %s). No walk started.\n' "$READ_RC" >&2
          exec 3<&-
          exit "$READ_RC"
        fi
        case "$PICK" in
          1) break ;;
          ""|q|Q) ;;
          *[!0-9]*) echo "Choose a number, q or Enter." ;;
          *)
            WALK_I=$((10#$PICK - 2))
            if [ "$WALK_I" -ge 0 ] && [ "$WALK_I" -lt "${#WALK_NAMES[@]}" ]; then
              exec 3<&-
              echo "Walk resolved: ${WALK_PATHS[$WALK_I]}" >&2
              exec "${WALK_PATHS[$WALK_I]}"
            fi
            echo "Choose a number from the list, q or Enter." ;;
        esac
        ;;
      2|RIDE) break ;;
      q|Q|"")
        echo "Stopped. No real walk started."
        exec 3<&-
        exit 0
        ;;
      *) echo "Choose 1, 2, 3 or q; Enter exits." ;;
    esac
  done
  exec 3<&-
fi
# THE RIDER SAYS THE TERMS (2026-10-02): mother_cat.py prints and speaks the
# trail's description and the walk's rules, one string for screen and voice,
# before the first page. Every walk ends the same way, with nothing to type.
# THE STDIN REDIRECT IS LOAD-BEARING, NOT DECORATION. Under curl|bash this
# script's stdin is the PIPE, and guided_browser_capture's PRE-LAUNCH gate
# tests isatty() on the INHERITED descriptor before it opens anything. The
# Enter prompt itself already prefers /dev/tty; its doorman does not.
# Handing the ride a real terminal on fd 0 satisfies both, and stays correct
# even after the gate is taught the same trick.
RIDE_RC=0
run_rider </dev/tty || RIDE_RC=$?
# THE RIDER OWNS THE LAST LINE (2026-10-02): it prints and speaks the next
# word after a finished walk, or says where it stopped and what to type, so
# nothing prints here after it.
exit "$RIDE_RC"
