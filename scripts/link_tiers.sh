#!/usr/bin/env bash
# scripts/link_tiers.sh -- link each tier's clone in ~/repos into Workshop/.
#
# THE TIERS LIVE IN THE NEGATIVE SPACE (2026-10-02, the PocketRender ride).
# Workshop/corporate, Workshop/personal and Workshop/shared are slots that
# this public repo's .gitignore promises never to track. Each holds a repo of
# its own, cloned to ~/repos/<tier> and linked in, so a write in a tier is a
# diff in that tier's repo and apply.py's invisible-write guard lets it
# through. Until today a link was made by hand, on one machine. flake.nix
# runs this on every shell entry, ahead of its mkdir lines, so any machine
# with a clone in ~/repos gets the link, and one that has it already is left
# as it is.
#
# Per tier, and only when ~/repos/<tier> is a git work tree:
#   slot absent           -> link it, and say so
#   slot an empty folder  -> remove the empty folder, link it, and say so
#   slot a link           -> nothing, unless it points at nothing; then say so
#   slot anything else    -> nothing, and say why. A plain folder with files
#                            in it, or a repo of its own in place (the git init
#                            WELCOME.md suggests), is never moved or deleted.
# A tier with no clone in ~/repos is left to the flake's mkdir, as before.
# Silent when there is nothing to do. Always exits 0, so a shell entry never
# fails here. PIPULATE_ROOT and HOME are read from the environment, so a
# throwaway tree can stand in for both.

root="${PIPULATE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
[ -n "$HOME" ] && [ -d "$root" ] || exit 0

shown() {
  case "$1" in
    "$HOME"/*) printf '~/%s' "${1#"$HOME"/}" ;;
    *) printf '%s' "$1" ;;
  esac
}

for tier in corporate personal shared; do
  repo="$HOME/repos/$tier"
  slot="$root/Workshop/$tier"
  [ -e "$repo/.git" ] || continue
  if [ -L "$slot" ]; then
    [ -e "$slot" ] || echo "Workshop/$tier links to $(readlink "$slot"), which is missing."
    continue
  fi
  if [ -d "$slot" ] && [ -z "$(ls -A "$slot" 2>/dev/null)" ]; then
    rmdir "$slot" 2>/dev/null
  fi
  if [ ! -e "$slot" ]; then
    mkdir -p "$root/Workshop" && ln -s "$repo" "$slot" &&
      echo "Workshop/$tier: linked to $(shown "$repo")."
    continue
  fi
  if [ -e "$slot/.git" ]; then
    echo "Workshop/$tier is a repo of its own, so $(shown "$repo") is not linked."
  elif [ -d "$slot" ]; then
    n=$(( $(ls -A "$slot" | wc -l) ))
    [ "$n" -eq 1 ] && what="1 entry" || what="$n entries"
    echo "Workshop/$tier is a plain folder with $what, so $(shown "$repo") is not linked. To link it, move the folder aside and enter the shell again: mv $(shown "$slot") ~/$tier-before-link-$(date +%F)"
  else
    echo "Workshop/$tier is a file, so $(shown "$repo") is not linked."
  fi
done
exit 0
