#!/usr/bin/env bash
# Deploy "Brain" to Honeybot
# DEPLOYMENT BOUNDARY (2026-09-13):
# A served body changes when its file is synced; an HTML-only edit does not
# require a NixOS rebuild. Prefer a targeted sync for a body-only change.
# NixOS configuration is merely staged here. Its runtime changes require a
# successful build and activation before an AFTER probe can witness them.
# "Sync Complete" alone proves neither activation nor certificate issuance.

TARGET="mike@192.168.10.100"

# THE INSTALLER LANE (2026-09-29, convicted by release 2.70). Three doors serve
# assets/installer/install.sh: pipulate.com out of the Pipulate.com checkout,
# which release.py's sync_install_sh moves, and npvg.org and qamy.ai out of
# Honeybot's ~/www, which only this file reaches. That release moved one door
# and the Mac read the old header from the other two. One function holds the
# pad list, the full sync calls it below, and `./nixops.sh --installer` runs
# it alone so release.py can move all three doors without staging config or
# sweeping scripts. Body only; no rebuild.
sync_installer() {
  echo "🚀 Syncing installer to the home-hosted doors (npvg.org, qamy.ai, levinix.org, sunpug.io)..."
  ssh $TARGET "mkdir -p ~/www/npvg.org ~/www/qamy.ai ~/www/levinix.org ~/www/sunpug.io" \
    && rsync -av assets/installer/install.sh $TARGET:~/www/npvg.org/install.sh \
    && rsync -av assets/installer/install.sh $TARGET:~/www/qamy.ai/install.sh \
    && rsync -av assets/installer/install.sh $TARGET:~/www/levinix.org/install.sh \
    && rsync -av assets/installer/install.sh $TARGET:~/www/sunpug.io/install.sh
}
if [ "${1:-}" = "--installer" ]; then
  if sync_installer; then
    echo "✅ Installer synced to npvg.org, qamy.ai, levinix.org, and sunpug.io (body only; no rebuild)."
    exit 0
  fi
  echo "❌ Installer sync failed; one or more doors still serve the previous file."
  exit 1
fi

echo "🚀 Syncing Hooks..."
scp remotes/honeybot/hooks/post-receive $TARGET:~/git/mikelev.in.git/hooks/post-receive
ssh $TARGET "chmod +x ~/git/mikelev.in.git/hooks/post-receive"

echo "🚀 Syncing Scripts (New Location)..."
# Ensure the directory exists
ssh $TARGET "mkdir -p ~/www/mikelev.in/scripts ~/www/mikelev.in/imports ~/www/mikelev.in/assets/sounds"

# Sync the new dedicated script folder
rsync --delete -av remotes/honeybot/scripts/ $TARGET:~/www/mikelev.in/scripts/

# Surgical sync of the visual display, patronus engine, and CC0 sound assets
rsync -av imports/ascii_displays.py $TARGET:~/www/mikelev.in/imports/
rsync -av assets/sounds/tick.wav $TARGET:~/www/mikelev.in/assets/sounds/tick.wav

echo "🚀 Syncing NPvg pad (one address, two bodies)..."
ssh $TARGET "mkdir -p ~/www/npvg.org"
rsync -av remotes/honeybot/www/npvg.org/ $TARGET:~/www/npvg.org/
# ONE SOURCE, THREE PROJECTIONS: the installer lives at assets/installer/install.sh.
# release.py projects it to Pipulate.com; sync_installer (above) projects it to both pads.

echo "🚀 Syncing qamy.ai door (npvg.org's shape, its own tree)..."
ssh $TARGET "mkdir -p ~/www/qamy.ai"
rsync -av remotes/honeybot/www/qamy.ai/ $TARGET:~/www/qamy.ai/
sync_installer
if [ -x ".venv/bin/python" ]; then
  .venv/bin/python -c "import sys, pathlib; sys.path.insert(0, 'scripts/articles'); import common, publishizer; t = common.load_targets().get('1', {}); p = pathlib.Path(t.get('path', '~/repos/trimnoir/_posts')).expanduser(); publishizer.build_brain_archive('1', p)" || true
fi
if [ -f "$HOME/.cache/pipulate/brain.zip" ]; then
  echo "🧠 Syncing 2nd Brain archive (brain.zip) to qamy.ai and mikelev.in..."
  rsync -av "$HOME/.cache/pipulate/brain.zip" $TARGET:~/www/qamy.ai/brain.zip
  ssh $TARGET "cp -lf ~/www/qamy.ai/brain.zip ~/www/mikelev.in/_site/brain.zip 2>/dev/null || cp -f ~/www/qamy.ai/brain.zip ~/www/mikelev.in/_site/brain.zip"
fi

echo "🚀 Syncing levinux.com deck (remark.js HTML + RFC 9110 index.md)..."
LEVINUX_CACHE="$HOME/.cache/pipulate/levinux-assets"
mkdir -p "$LEVINUX_CACHE"
for asset in levinux.png mike-levin-ambigram.svg; do
  if [ ! -f "$LEVINUX_CACHE/$asset" ]; then
    curl -fsSL "https://levinux.com/$asset" -o "$LEVINUX_CACHE/$asset" 2>/dev/null || true
  fi
done
if [ ! -f "$LEVINUX_CACHE/remark-latest.min.js" ]; then
  curl -fsSL "https://remarkjs.com/downloads/remark-latest.min.js" -o "$LEVINUX_CACHE/remark-latest.min.js" 2>/dev/null || true
fi
ssh $TARGET "mkdir -p ~/www/levinux.com ~/www/levinix.org"
rsync -av remotes/honeybot/www/levinux.com/ "$LEVINUX_CACHE/" $TARGET:~/www/levinux.com/
rsync -av remotes/honeybot/www/levinix.org/ $TARGET:~/www/levinix.org/

echo "🚀 Syncing NixOS Config..."
rsync --delete -av remotes/honeybot/nixos/ $TARGET:~/nixos-config-staged/

echo "✅ Sync Complete."
echo "   To apply NixOS config: ssh -t $TARGET 'sudo cp ~/nixos-config-staged/* /etc/nixos/ && sudo nixos-rebuild switch'"
