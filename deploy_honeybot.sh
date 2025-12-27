#!/usr/bin/env bash
# Deploy "Brain" to Honeybot

TARGET="mike@192.168.10.100"

echo "🚀 Syncing Hooks..."
# We use rsync to push the hook to the bare repo
scp remotes/honeybot/hooks/post-receive $TARGET:~/git/mikelev.in.git/hooks/post-receive
ssh $TARGET "chmod +x ~/git/mikelev.in.git/hooks/post-receive"

echo "🚀 Syncing Tools..."
# We move the sonar script that hides IPs into location
ssh $TARGET "mkdir -p ~/scripts"
rsync -av scripts/sonar.py $TARGET:~/scripts/

echo "🚀 Syncing NixOS Config..."
# We push the config to a temp folder, then sudo move it (requires interactive password or NOPASSWD sudo)
# For now, let's just push it to the home dir for review
rsync -av remotes/honeybot/nixos/ $TARGET:~/nixos-config-staged/

echo "✅ Sync Complete."
echo "   To apply NixOS config: ssh -t $TARGET 'sudo cp ~/nixos-config-staged/* /etc/nixos/ && sudo nixos-rebuild switch'"
