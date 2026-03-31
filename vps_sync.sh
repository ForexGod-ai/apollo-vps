#!/bin/bash
# 🔱 GLITCH IN MATRIX — Quick Sync (după modificări de cod)
# Rulează local: bash vps_sync.sh <VPS_IP>
# Sincronizează doar fișierele .py și .json de config (nu datele live)

VPS_IP="${1:-YOUR_VPS_IP}"
REMOTE_DIR="/home/matrix/trading-ai-agent-apollo"
LOCAL_DIR="/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

if [ "$VPS_IP" = "YOUR_VPS_IP" ]; then
    echo "❌ Usage: bash vps_sync.sh <VPS_IP>"
    exit 1
fi

echo "🔄 Syncing code changes to VPS $VPS_IP..."

rsync -avz --progress \
    --include='*.py' \
    --include='*.json' \
    --include='.env' \
    --include='requirements_vps_clean.txt' \
    --exclude='monitoring_setups.json' \
    --exclude='trade_history.json' \
    --exclude='active_positions.json' \
    --exclude='data/' \
    --exclude='logs/' \
    --exclude='.venv/' \
    --exclude='.git/' \
    --exclude='__pycache__/' \
    --exclude='*.log' \
    --filter='- *.pyc' \
    "$LOCAL_DIR/" \
    "root@$VPS_IP:$REMOTE_DIR/"

echo ""
echo "🔄 Restarting services on VPS..."
ssh root@$VPS_IP "systemctl restart matrix-setup_executor_monitor matrix-telegram_command_center matrix-news_calendar_monitor"
echo "✅ Sync + restart complete!"
