#!/bin/bash
# Sync trade_history.json from old folder to current project folder
# Runs every 10 seconds

SOURCE="/Users/forexgod/Desktop/trading-ai-agent apollo/trade_history.json"
DEST="/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/trade_history.json"

echo "🔄 Starting trade_history.json sync..."
echo "📂 Source: $SOURCE"
echo "📂 Dest: $DEST"

while true; do
    if [ -f "$SOURCE" ]; then
        cp "$SOURCE" "$DEST"
        echo "✅ Synced at $(date '+%H:%M:%S')"
    else
        echo "❌ Source file not found!"
    fi
    sleep 10
done
