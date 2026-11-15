#!/usr/bin/env bash
# Runs ON the server (Ubuntu 22.04/24.04). Installs deps and the agent as an always-on systemd service.
set -euo pipefail

APP_DIR="$HOME/tiktok-agent"
cd "$APP_DIR"

sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip ffmpeg

python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt

sudo tee /etc/systemd/system/tiktok-agent.service >/dev/null <<EOF
[Unit]
Description=TikTok auto-repost agent
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python -u agent.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Keep yt-dlp fresh every day: TikTok changes often and old versions break.
( crontab -l 2>/dev/null | grep -v 'tiktok-agent-ytdlp'; \
  echo "0 4 * * * $APP_DIR/venv/bin/pip install -q -U yt-dlp && sudo systemctl restart tiktok-agent # tiktok-agent-ytdlp" ) | crontab -

sudo systemctl daemon-reload
sudo systemctl enable --now tiktok-agent
sudo systemctl restart tiktok-agent
echo "✅ Agent is running. Logs: journalctl -u tiktok-agent -f"
