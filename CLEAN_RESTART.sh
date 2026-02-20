#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 CLEAN RESTART SCRIPT - Glitch in Matrix V4.3
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Purpose: Kill ALL Python trading processes and restart clean
# Fixes: Double notifications from duplicate instances
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔥 GLITCH IN MATRIX - CLEAN RESTART"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Step 1: Kill all trading processes
echo "🛑 Step 1: Stopping all trading processes..."
echo ""

pkill -9 -f "setup_executor_monitor" && echo "   ✅ Setup Executor - STOPPED" || echo "   ℹ️  Setup Executor - not running"
pkill -9 -f "position_monitor" && echo "   ✅ Position Monitor - STOPPED" || echo "   ℹ️  Position Monitor - not running"
pkill -9 -f "telegram_command_center" && echo "   ✅ Command Center - STOPPED" || echo "   ℹ️  Command Center - not running"
pkill -9 -f "watchdog_monitor" && echo "   ✅ Watchdog - STOPPED" || echo "   ℹ️  Watchdog - not running"
pkill -9 -f "ctrader_sync_daemon" && echo "   ✅ cTrader Sync - STOPPED" || echo "   ℹ️  cTrader Sync - not running"

echo ""
echo "⏳ Waiting 3 seconds for clean shutdown..."
sleep 3

# Step 2: Remove PID lock files
echo ""
echo "🔓 Step 2: Removing PID lock files..."
echo ""

rm -f process_setup_executor.lock && echo "   ✅ Removed: process_setup_executor.lock"
rm -f process_position_monitor.lock && echo "   ✅ Removed: process_position_monitor.lock"
rm -f process_telegram_command_center.lock && echo "   ✅ Removed: process_telegram_command_center.lock"

# Step 3: Verify all processes are stopped
echo ""
echo "🔍 Step 3: Verifying clean state..."
echo ""

RUNNING_PROCS=$(ps aux | grep -E "setup_executor|position_monitor|telegram_command|watchdog_monitor" | grep -v grep | wc -l)

if [ "$RUNNING_PROCS" -eq 0 ]; then
    echo "   ✅ All processes stopped successfully"
else
    echo "   ⚠️  Warning: $RUNNING_PROCS processes still running"
    ps aux | grep -E "setup_executor|position_monitor|telegram_command|watchdog_monitor" | grep -v grep
fi

# Step 4: Restart with V4.3 fixes
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Step 4: Restarting with V4.3 Anti-Duplicate Protection"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start Setup Executor
python3 setup_executor_monitor.py --interval 30 --loop > setup_monitor.log 2>&1 &
SETUP_PID=$!
echo "   ✅ Setup Executor - STARTED (PID $SETUP_PID)"

sleep 2

# Start Position Monitor
python3 position_monitor.py --loop > position_monitor.log 2>&1 &
POSITION_PID=$!
echo "   ✅ Position Monitor - STARTED (PID $POSITION_PID)"

sleep 2

# Start Command Center
python3 telegram_command_center.py > command_center.log 2>&1 &
COMMAND_PID=$!
echo "   ✅ Command Center - STARTED (PID $COMMAND_PID)"

sleep 2

# Start Watchdog (monitors all others)
python3 watchdog_monitor.py > watchdog.log 2>&1 &
WATCHDOG_PID=$!
echo "   ✅ Watchdog Monitor - STARTED (PID $WATCHDOG_PID)"

# Step 5: Final verification
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Step 5: System Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sleep 3

ps aux | grep -E "setup_executor|position_monitor|telegram_command|watchdog_monitor" | grep -v grep | awk '{print "   🟢 " $11 " (PID " $2 ")"}'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ CLEAN RESTART COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🔒 Protection Features:"
echo "   • PID Lock: Prevents duplicate instances"
echo "   • Message Deduplication: 5s cooldown window"
echo "   • Smart Watchdog: psutil-based process verification"
echo ""
echo "📝 Log files:"
echo "   • setup_monitor.log"
echo "   • position_monitor.log"
echo "   • command_center.log"
echo "   • watchdog.log"
echo ""
echo "�� No more double notifications!"
echo ""
