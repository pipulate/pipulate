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
  echo "🚀 Syncing installer to the home-hosted doors (npvg.org, qamy.ai)..."
  ssh $TARGET "mkdir -p ~/www/npvg.org ~/www/qamy.ai" \
    && rsync -av assets/installer/install.sh $TARGET:~/www/npvg.org/install.sh \
    && rsync -av assets/installer/install.sh $TARGET:~/www/qamy.ai/install.sh
}
if [ "${1:-}" = "--installer" ]; then
  if sync_installer; then
    echo "✅ Installer synced to npvg.org and qamy.ai (body only; no rebuild)."
    exit 0
  fi
  echo "❌ Installer sync failed; one or both doors still serve the previous file."
  exit 1
fi

echo "🚀 Syncing Hooks..."
scp remotes/honeybot/hooks/post-receive $TARGET:~/git/mikelev.in.git/hooks/post-receive
ssh $TARGET "chmod +x ~/git/mikelev.in.git/hooks/post-receive"

echo "🚀 Syncing Scripts (New Location)..."
# Ensure the directory exists
ssh $TARGET "mkdir -p ~/www/mikelev.in/scripts ~/www/mikelev.in/imports"

# Sync the new dedicated script folder
rsync --delete -av remotes/honeybot/scripts/ $TARGET:~/www/mikelev.in/scripts/

# Surgical sync of the visual display and patronus engine assets
rsync -av imports/ascii_displays.py $TARGET:~/www/mikelev.in/imports/

echo "🚀 Syncing NPvg pad (one address, two bodies)..."
ssh $TARGET "mkdir -p ~/www/npvg.org"
rsync -av remotes/honeybot/www/npvg.org/ $TARGET:~/www/npvg.org/
# ONE SOURCE, THREE PROJECTIONS: the installer lives at assets/installer/install.sh.
# release.py projects it to Pipulate.com; sync_installer (above) projects it to both pads.

echo "🚀 Syncing qamy.ai door (npvg.org's shape, its own tree)..."
ssh $TARGET "mkdir -p ~/www/qamy.ai"
rsync -av remotes/honeybot/www/qamy.ai/ $TARGET:~/www/qamy.ai/
rsync -av assets/installer/install.sh $TARGET:~/www/qamy.ai/install.sh

echo "🚀 Syncing NixOS Config..."
rsync --delete -av remotes/honeybot/nixos/ $TARGET:~/nixos-config-staged/

echo "✅ Sync Complete."
echo "   To apply NixOS config: ssh -t $TARGET 'sudo cp ~/nixos-config-staged/* /etc/nixos/ && sudo nixos-rebuild switch'"
