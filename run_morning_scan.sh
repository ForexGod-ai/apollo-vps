#!/bin/bash

# ====================================================================
# Morning Scanner - Automated Execution Script
# Runs at 09:00 daily to scan markets and find trading setups
# ====================================================================

# Change to project directory
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

echo "════════════════════════════════════════════════════════════════"
echo "🌅 MORNING SCANNER STARTED - $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Activate Python environment (if using venv)
# source venv/bin/activate

# Run morning scanner (GLITCH IN MATRIX 2.0)
echo "🔍 Step 1: Scanning markets for trading setups..."
python3 daily_scanner.py

# Check scanner exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Scanner completed successfully!"
    echo ""
    echo "📱 Step 2: Sending Telegram report with setups..."
    python3 send_morning_scan_report.py
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Morning report sent to Telegram!"
    else
        echo ""
        echo "⚠️ Report send failed (code $?)"
    fi
else
    echo ""
    echo "❌ Scanner failed with error code $?"
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
