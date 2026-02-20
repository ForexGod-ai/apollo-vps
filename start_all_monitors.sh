#!/bin/bash

cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

echo "🚀 ForexGod - Starting Complete Auto-Notification System"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create logs directory
mkdir -p logs
mkdir -p .pids

# Stop existing monitors
echo "🧹 Stopping existing monitors..."
pkill -f "ctrader_sync_daemon" 2>/dev/null
pkill -f "position_monitor" 2>/dev/null
pkill -f "setup_executor_monitor" 2>/dev/null
sleep 2

# Activate virtual environment
source .venv/bin/activate

# 1️⃣ Start cTrader Sync Daemon (Updates trade_history.json every 30s)
echo ""
echo "1️⃣ Starting cTrader Sync Daemon..."
nohup .venv/bin/python ctrader_sync_daemon.py --loop > logs/ctrader_sync.log 2>&1 &
SYNC_PID=$!
echo "   ✅ cTrader Sync Daemon started (PID: $SYNC_PID)"
echo "   📊 Updates trade_history.json every 30s from cTrader API"
echo "$SYNC_PID" > .pids/ctrader_sync.pid
sleep 2

# 2️⃣ Start Position Monitor (SL/TP/Close notifications)
echo ""
echo "2️⃣ Starting Position Monitor..."
nohup .venv/bin/python position_monitor.py --loop > logs/position_monitor.log 2>&1 &
POS_PID=$!
echo "   ✅ Position Monitor started (PID: $POS_PID)"
echo "   🎯 Sends instant notifications for:"
echo "      - New positions opened"
echo "      - Stop Loss hits"
echo "      - Take Profit hits"
echo "      - Manual closes"
echo "$POS_PID" > .pids/position_monitor.pid
sleep 2

# 3️⃣ Start Setup Executor Monitor (Entry execution + notifications)
echo ""
echo "3️⃣ Starting Setup Executor Monitor..."
nohup .venv/bin/python setup_executor_monitor.py --interval 30 --loop > logs/setup_monitor.log 2>&1 &
EXEC_PID=$!
echo "   ✅ Setup Executor Monitor started (PID: $EXEC_PID)"
echo "   ⚡ Aggressive mode: 5s checks for in-zone setups"
echo "   📱 Sends execution notifications for Entry 1 & Entry 2"
echo "$EXEC_PID" > .pids/setup_executor.pid
sleep 2

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ ALL SYSTEMS ONLINE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Active Processes:"
echo "   - cTrader Sync:      PID $SYNC_PID (log: logs/ctrader_sync.log)"
echo "   - Position Monitor:  PID $POS_PID (log: logs/position_monitor.log)"
echo "   - Setup Executor:    PID $EXEC_PID (log: logs/setup_monitor.log)"
echo ""
echo "📱 Telegram Notifications ENABLED for:"
echo "   ✅ Trade Executions (Entry 1 & Entry 2)"
echo "   ✅ Stop Loss Hits"
echo "   ✅ Take Profit Hits"
echo "   ✅ Position Closes (Manual/Auto)"
echo ""
echo "🛑 To stop all monitors: pkill -f 'ctrader_sync|position_monitor|setup_executor'"
echo "📊 To check status:       ps aux | grep -E 'ctrader_sync|position_monitor|setup_executor' | grep -v grep"
echo ""
echo "📝 To view logs:"
echo "   tail -f logs/ctrader_sync.log"
echo "   tail -f logs/position_monitor.log"
echo "   tail -f logs/setup_monitor.log"
echo ""
