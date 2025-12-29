#!/bin/bash

# Morning Scan - Unified with Daily Scan
# Runs daily scan logic for morning execution

cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

echo "════════════════════════════════════════════════════════════════"
echo "🌅 MORNING SCAN (Unified) STARTED - $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════════════"
echo ""

PYTHONPATH=. python3 daily_scanner.py

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
echo "🏁 MORNING SCAN (Unified) FINISHED - $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════════════"
