#!/bin/bash

cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

echo "🚀 Starting Glitch in Matrix Trading System..."
echo ""

# Check if trade_monitor is running
if pgrep -f "trade_monitor.py" > /dev/null; then
    echo "✅ trade_monitor.py already running"
else
    echo "🔄 Starting trade_monitor.py..."
    nohup python3 trade_monitor.py --loop > logs/trade_monitor.log 2>&1 &
    echo "✅ trade_monitor.py started"
fi

# Check if HTTP server is running
if lsof -ti:8000 > /dev/null; then
    echo "✅ Dashboard HTTP server already running on port 8000"
else
    echo "🔄 Starting dashboard HTTP server..."
    nohup python3 -m http.server 8000 > logs/http_server.log 2>&1 &
    echo "✅ Dashboard HTTP server started on port 8000"
fi

echo ""
echo "📊 System Status:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ps aux | grep -E "trade_monitor|http.server" | grep -v grep
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 Dashboard: http://localhost:8000/dashboard_live.html"
echo "📱 Telegram: @ForexGodGlitch_bot"
echo ""
echo "⏰ Morning scanner: Programat pentru 08:00 (automat)"
echo "🤖 cTrader cBots: Pornește manual din cTrader"
echo ""
echo "✅ All services started!"
