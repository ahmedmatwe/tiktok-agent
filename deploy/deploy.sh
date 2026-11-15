#!/usr/bin/env bash
# Runs on YOUR Mac. Copies the agent (with .env, YouTube login and state) to the server and starts it.
#   ./deploy/deploy.sh ubuntu@SERVER_IP ~/.ssh/oracle_key
set -euo pipefail

TARGET="${1:?usage: deploy.sh user@server_ip [ssh_key]}"
KEY="${2:-}"
SSH=(ssh -o StrictHostKeyChecking=accept-new)
[ -n "$KEY" ] && SSH+=(-i "$KEY")

cd "$(dirname "$0")/.."
[ -f .env ] || { echo "❌ .env missing: copy .env.example to .env and fill it first"; exit 1; }
if grep -q '^ENABLE_YOUTUBE=true' .env && [ ! -f data/youtube_token.json ]; then
  echo "❌ Run './venv/bin/python agent.py --youtube-login' here first (the server has no browser)"; exit 1
fi

rsync -az --delete -e "${SSH[*]}" \
  --exclude venv --exclude '__pycache__' --exclude 'data/videos' \
  ./ "$TARGET:tiktok-agent/"

"${SSH[@]}" "$TARGET" "bash ~/tiktok-agent/deploy/server_setup.sh"
