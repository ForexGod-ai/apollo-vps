#!/bin/bash

# Configuration
VPS_USER="root"
VPS_HOST="YOUR_VPS_IP_HERE"
VPS_PATH="/var/www/html/dashboard"
LOCAL_FILE="/Users/forexgod/Desktop/trading-ai-agent apollo/trade_history.json"

echo "🔄 ForexGod Dashboard - Auto Sync to VPS"

while true; do
    # Check if file exists
    if [ -f "$LOCAL_FILE" ]; then
        # Sync to VPS
        scp -o ConnectTimeout=5 "$LOCAL_FILE" "$VPS_USER@$VPS_HOST:$VPS_PATH/" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo "✅ [$(date '+%Y-%m-%d %H:%M:%S')] Synced to VPS"
        else
            echo "⚠️  [$(date '+%Y-%m-%d %H:%M:%S')] Sync failed - will retry"
        fi
    fi
    
    # Wait 30 seconds
    sleep 30
done
