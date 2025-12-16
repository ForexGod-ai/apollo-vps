#!/bin/bash

# ====================================================================
# Morning Scanner - Automated Execution Script
# Runs at 09:00 daily to scan markets and find trading setups
# ====================================================================

# Change to project directory
cd /Users/forexgod/Desktop/trading-ai-agent\ apollo

echo "════════════════════════════════════════════════════════════════"
echo "🌅 MORNING SCANNER STARTED - $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Activate Python environment (if using venv)
# source venv/bin/activate

# Run morning scanner (GLITCH IN MATRIX 2.0)
echo "🔍 Scanning markets for trading setups with Glitch 2.0..."
python3 daily_scanner.py

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Morning scan completed successfully!"
    echo "📱 Check Telegram for results"
else
    echo ""
    echo "❌ Morning scan failed with error code $?"
    echo "📋 Check logs/morning_scan.log for details"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "🏁 MORNING SCANNER FINISHED - $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════════════"

# Optional: Send completion notification to Telegram
python3 -c "
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

if token and chat_id:
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    message = f'✅ Morning scan completed at {datetime.now().strftime(\"%H:%M\")}!'
    requests.post(url, json={'chat_id': chat_id, 'text': message})
"
