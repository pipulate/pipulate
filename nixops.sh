#!/usr/bin/env bash
# Deploy "Brain" to Honeybot

TARGET="mike@192.168.10.100"

echo "🚀 Syncing Hooks..."
scp remotes/honeybot/hooks/post-receive $TARGET:~/git/mikelev.in.git/hooks/post-receive
ssh $TARGET "chmod +x ~/git/mikelev.in.git/hooks/post-receive"

echo "🚀 Syncing Scripts (New Location)..."
# Ensure the directory exists
ssh $TARGET "mkdir -p ~/www/mikelev.in/scripts"

# Sync the new dedicated script folder
rsync --delete -av remotes/honeybot/scripts/ $TARGET:~/www/mikelev.in/scripts/

echo "🚀 Syncing NixOS Config..."
rsync --delete -av remotes/honeybot/nixos/ $TARGET:~/nixos-config-staged/

echo "✅ Sync Complete."
echo "   To apply NixOS config: ssh -t $TARGET 'sudo cp ~/nixos-config-staged/* /etc/nixos/ && sudo nixos-rebuild switch'"
