#!/bin/bash
# ╔══════════════════════════════════════════════════════╗
# ║   🔱 RESET MATRIX V11.5 — Total System Restart      ║
# ║   Glitch in Matrix by ФорексГод                     ║
# ╚══════════════════════════════════════════════════════╝

SCRIPT_DIR="/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
PYTHON="$SCRIPT_DIR/.venv/bin/python"

echo ""
echo "🔱 ═══════════════════════════════════════════════════"
echo "   RESET MATRIX V11.5 — Glitch In Matrix"
echo "🔱 ═══════════════════════════════════════════════════"
echo ""

cd "$SCRIPT_DIR"

# ━━━ STEP 1: Kill all Python monitors ━━━
echo "🛑 [1/4] Killing all Python processes..."
pkill -f "setup_executor_monitor" 2>/dev/null && echo "   ✅ setup_executor_monitor killed" || echo "   ⚪ setup_executor_monitor not running"
pkill -f "position_monitor" 2>/dev/null && echo "   ✅ position_monitor killed" || echo "   ⚪ position_monitor not running"
pkill -f "telegram_command_center" 2>/dev/null && echo "   ✅ telegram_command_center killed" || echo "   ⚪ telegram_command_center not running"
pkill -f "watchdog_monitor" 2>/dev/null && echo "   ✅ watchdog_monitor killed" || echo "   ⚪ watchdog_monitor not running"
pkill -f "ctrader_sync_daemon" 2>/dev/null && echo "   ✅ ctrader_sync_daemon killed" || echo "   ⚪ ctrader_sync_daemon not running"
pkill -f "news_calendar_monitor" 2>/dev/null && echo "   ✅ news_calendar_monitor killed" || echo "   ⚪ news_calendar_monitor not running"
pkill -f "news_reminder_engine" 2>/dev/null && echo "   ✅ news_reminder_engine killed" || echo "   ⚪ news_reminder_engine not running"

sleep 2

# ━━━ STEP 2: Cleanup all .lock files ━━━
echo ""
echo "🧹 [2/4] Cleaning lock files..."
for lockfile in "$SCRIPT_DIR"/*.lock; do
    if [ -f "$lockfile" ]; then
        rm -f "$lockfile"
        echo "   ✅ Deleted: $(basename $lockfile)"
    fi
done
echo "   ✅ Lock files cleared"

# ━━━ STEP 3: Verify no Python processes left ━━━
echo ""
echo "🔍 [3/4] Verifying clean state..."
REMAINING=$(ps aux | grep -E "setup_executor|position_monitor|telegram_command|watchdog_monitor|ctrader_sync|news_calendar|news_reminder" | grep -v grep | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "   ⚠️  $REMAINING process(es) still alive — force killing..."
    ps aux | grep -E "setup_executor|position_monitor|telegram_command|watchdog_monitor|ctrader_sync|news_calendar|news_reminder" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
    sleep 1
    echo "   ✅ Force kill complete"
else
    echo "   ✅ All processes stopped cleanly"
fi

# ━━━ STEP 4: Restart Watchdog ━━━
echo ""
echo "🛡️ [4/4] Starting Watchdog Guardian..."
"$PYTHON" watchdog_monitor.py --interval 60 > watchdog.log 2>&1 &
WATCHDOG_PID=$!
sleep 2

if ps -p $WATCHDOG_PID > /dev/null 2>&1; then
    echo "   ✅ Watchdog started (PID $WATCHDOG_PID)"
else
    echo "   ❌ Watchdog failed to start — check watchdog.log"
fi

echo ""
echo "🔱 ═══════════════════════════════════════════════════"
echo "   MATRIX RESET COMPLETE"
echo "   Watchdog Guardian activ — va reporni automat toate"
echo "   procesele critice în max 60 secunde."
echo "🔱 ═══════════════════════════════════════════════════"
echo ""
