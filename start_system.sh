#!/bin/bash

# ====================================================================
# GLITCH IN MATRIX - Master System Startup Script
# Pornește toate componentele în ordinea corectă
# ====================================================================

PROJECT_DIR="/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
cd "$PROJECT_DIR"

echo "════════════════════════════════════════════════════════════════"
echo "🚀 GLITCH IN MATRIX SYSTEM STARTUP"
echo "📅 $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════════════"
echo ""

# ====================================================================
# 1. Verify cTrader cBots are running
# ====================================================================
echo "🔍 Step 1: Checking cTrader cBots..."
echo "   - MarketDataProvider (localhost:8767)"
echo "   - TradeHistorySyncer2 (trade_history.json)"
echo "   - PythonSignalExecutor (signals.json)"
echo ""

# Test MarketDataProvider
if curl -s http://localhost:8767/health > /dev/null 2>&1; then
    echo "   ✅ MarketDataProvider: RUNNING"
else
    echo "   ❌ MarketDataProvider: NOT RUNNING"
    echo "   ⚠️  Please start MarketDataProvider cBot in cTrader!"
    echo ""
    read -p "Press ENTER when cBot is started, or Ctrl+C to exit..."
fi

# Test trade_history.json sync
if [ -f "$PROJECT_DIR/trade_history.json" ]; then
    LAST_UPDATE=$(python3 -c "import json; d=json.load(open('trade_history.json')); print(d['account']['last_update'])" 2>/dev/null)
    if [ -n "$LAST_UPDATE" ]; then
        echo "   ✅ TradeHistorySyncer2: RUNNING (last update: $LAST_UPDATE)"
    else
        echo "   ⚠️  TradeHistorySyncer2: File exists but no data"
    fi
else
    echo "   ❌ TradeHistorySyncer2: trade_history.json not found"
fi
echo ""

# ====================================================================
# 2. Stop any old Python processes
# ====================================================================
echo "🧹 Step 2: Cleaning old processes..."
pkill -f "setup_monitor.py" 2>/dev/null && echo "   Stopped old setup_monitor.py"
pkill -f "daily_scanner.py" 2>/dev/null && echo "   Stopped old daily_scanner.py"
pkill -f "realtime_monitor.py" 2>/dev/null && echo "   Stopped old realtime_monitor.py"
pkill -f "morning_strategy_scan.py" 2>/dev/null && echo "   Stopped deprecated morning_strategy_scan.py"
sleep 2
echo "   ✅ Cleanup complete"
echo ""

# ====================================================================
# 3. Create necessary directories
# ====================================================================
echo "📁 Step 3: Creating directories..."
mkdir -p logs charts data
echo "   ✅ Directories ready"
echo ""

# ====================================================================
# 4. Start Setup Monitor (monitors MONITORING setups for 4H confirmation)
# ====================================================================
echo "🎯 Step 4: Starting Setup Monitor..."
nohup python3 setup_monitor.py > logs/setup_monitor.log 2>&1 &
MONITOR_PID=$!
sleep 2

if ps -p $MONITOR_PID > /dev/null; then
    echo "   ✅ Setup Monitor started (PID: $MONITOR_PID)"
    echo "   📊 Monitoring file: monitoring_setups.json"
    echo "   ⏱️  Check interval: 15 minutes"
else
    echo "   ❌ Setup Monitor failed to start - check logs/setup_monitor.log"
fi
echo ""

# ====================================================================
# 5. Start HTTP Server for Dashboard
# ====================================================================
echo "📊 Step 5: Starting Dashboard HTTP Server..."
pkill -f "python3 -m http.server 8000" 2>/dev/null
nohup python3 -m http.server 8000 > logs/http_server.log 2>&1 &
sleep 1
echo "   ✅ Dashboard available at: http://localhost:8000/dashboard_live.html"
echo ""

# ====================================================================
# 6. Verify Everything is Running
# ====================================================================
echo "════════════════════════════════════════════════════════════════"
echo "✅ SYSTEM STATUS"
echo "════════════════════════════════════════════════════════════════"
echo ""

# cTrader Status
curl -s http://localhost:8767/health > /dev/null 2>&1 && \
    echo "🟢 MarketDataProvider: http://localhost:8767" || \
    echo "🔴 MarketDataProvider: OFFLINE"

# Trade History Status
if [ -f "trade_history.json" ]; then
    BALANCE=$(python3 -c "import json; d=json.load(open('trade_history.json')); print(f\"\${d['account']['balance']:.2f}\")" 2>/dev/null)
    OPEN_POS=$(python3 -c "import json; d=json.load(open('trade_history.json')); print(len(d['open_positions']))" 2>/dev/null)
    echo "🟢 Trade History Sync: Balance $BALANCE | Open: $OPEN_POS"
else
    echo "🔴 Trade History Sync: NOT FOUND"
fi

# Python Processes
ps aux | grep -E "setup_monitor.py" | grep -v grep > /dev/null && \
    echo "🟢 Setup Monitor: RUNNING" || \
    echo "🔴 Setup Monitor: OFFLINE"

# Dashboard
curl -s http://localhost:8000 > /dev/null 2>&1 && \
    echo "🟢 Dashboard: http://localhost:8000/dashboard_live.html" || \
    echo "🔴 Dashboard: OFFLINE"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📋 NEXT STEPS"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "1. 🌅 Morning Scanner: Scheduled to run at 09:00 daily"
echo "   • Run manually: ./run_morning_scan.sh"
echo ""
echo "2. 📊 Monitor Logs:"
echo "   • Setup Monitor: tail -f logs/setup_monitor.log"
echo "   • Morning Scanner: tail -f logs/morning_scan.log"
echo ""
echo "3. 📱 Telegram: All notifications sent to configured chat"
echo ""
echo "4. 🛑 Stop System: pkill -f setup_monitor.py"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "🎯 GLITCH IN MATRIX 2.0 - READY FOR TRADING!"
echo "════════════════════════════════════════════════════════════════"
