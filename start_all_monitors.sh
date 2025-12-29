#!/bin/bash

cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

echo "🔥 ForexGod - Starting ALL Monitoring Systems"
echo "=============================================="
echo ""

# Create logs directory
mkdir -p logs

# Stop existing monitors
echo "🧹 Stopping existing monitors..."
pkill -f "python3.*monitor" 2>/dev/null
sleep 2

# Start Trade Monitor (pentru TP/SL hits)
echo "📊 Starting Trade Monitor (TP/SL detection)..."
nohup python3 trade_monitor.py --loop > logs/trade_monitor.log 2>&1 &
TRADE_PID=$!
echo "   ✅ Trade Monitor started (PID: $TRADE_PID)"
sleep 1

# Start Position Monitor (pentru new trades)
echo "👀 Starting Position Monitor (New trade detection)..."
nohup python3 position_monitor.py > logs/position_monitor.log 2>&1 &
POS_PID=$!
echo "   ✅ Position Monitor started (PID: $POS_PID)"
sleep 1

# Start Realtime 4H Monitor (pentru setups)
echo "🎯 Starting Realtime 4H Monitor (Setup detection)..."
nohup python3 realtime_monitor.py > logs/realtime_monitor.log 2>&1 &
RT_PID=$!
echo "   ✅ Realtime Monitor started (PID: $RT_PID)"

echo ""
echo "=============================================="
echo "✅ ALL MONITORS STARTED!"
echo ""
echo "📋 Monitor Status:"
ps aux | grep "python3.*monitor" | grep -v grep | awk '{print "   " $2 " - " $11 " " $12}'
echo ""
echo "📝 Log files:"
echo "   - Trade Monitor:    logs/trade_monitor.log"
echo "   - Position Monitor: logs/position_monitor.log"
echo "   - Realtime Monitor: logs/realtime_monitor.log"
echo ""
echo "🔍 To view logs:"
echo "   tail -f logs/trade_monitor.log"
echo ""
echo "⏹️  To stop all:"
echo "   pkill -f 'python3.*monitor'"
echo ""
