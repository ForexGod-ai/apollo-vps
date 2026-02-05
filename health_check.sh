#!/bin/bash

# 🏥 V3.5 SYSTEM HEALTH CHECK
# Rapid diagnostic pentru "Glitch in Matrix" trading system

echo "🏥 V3.5 SYSTEM HEALTH CHECK"
echo "=========================="
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo

# 1. Check processes
echo "📍 Process Status:"
SETUP_PID=$(pgrep -f setup_executor_monitor)
POSITION_PID=$(pgrep -f position_monitor)
TRADE_PID=$(pgrep -f trade_monitor)

if [ -n "$SETUP_PID" ]; then
    echo "✅ Setup Monitor: Running (PID $SETUP_PID)"
else
    echo "❌ Setup Monitor: Stopped"
fi

if [ -n "$POSITION_PID" ]; then
    echo "✅ Position Monitor: Running (PID $POSITION_PID)"
else
    echo "❌ Position Monitor: Stopped"
fi

if [ -n "$TRADE_PID" ]; then
    echo "✅ Trade Monitor: Running (PID $TRADE_PID)"
else
    echo "❌ Trade Monitor: Stopped"
fi
echo

# 2. Check lookback config
echo "⚙️  Lookback Configuration:"
if [ -f pairs_config.json ]; then
    grep -A3 '"lookback_candles"' pairs_config.json | grep -E "daily|h4|h1" | sed 's/^/  /'
else
    echo "  ❌ pairs_config.json not found"
fi
echo

# 3. Recent OB detections
echo "📦 Order Block Stats (Today):"
TODAY=$(date +%Y-%m-%d)
if [ -f daily_scanner.log ]; then
    OB_COUNT=$(grep "ORDER BLOCK DETECTED" daily_scanner.log 2>/dev/null | grep "$TODAY" | wc -l | tr -d ' ')
    PERFECT_COUNT=$(grep -A3 "ORDER BLOCK DETECTED" daily_scanner.log 2>/dev/null | grep "OB Score: 10/10" | wc -l | tr -d ' ')
    echo "  Total OB Detected: $OB_COUNT"
    echo "  Perfect 10/10 Setups: $PERFECT_COUNT"
    
    # OB score distribution
    echo "  Score Distribution:"
    for score in 10 9 8 7 6 5; do
        count=$(grep "OB Score: $score/10" daily_scanner.log 2>/dev/null | grep "$TODAY" | wc -l | tr -d ' ')
        if [ "$count" -gt 0 ]; then
            echo "    $score/10: $count setups"
        fi
    done
else
    echo "  ❌ daily_scanner.log not found"
fi
echo

# 4. Active positions
echo "💼 Active Positions:"
if [ -f active_positions.json ]; then
    POS_COUNT=$(cat active_positions.json 2>/dev/null | grep -o '"positionId"' | wc -l | tr -d ' ')
    echo "  Open Trades: $POS_COUNT"
    
    # Calculate total volume and PnL if positions exist
    if [ "$POS_COUNT" -gt 0 ]; then
        python3 -c "
import json
try:
    with open('active_positions.json') as f:
        positions = json.load(f)
    total_volume = sum(p.get('volume', 0) for p in positions.values())
    total_pnl = sum(p.get('netProfit', 0) for p in positions.values())
    print(f'  Total Volume: {total_volume:.2f} lots')
    print(f'  Unrealized PnL: \${total_pnl:.2f}')
except Exception as e:
    print(f'  ⚠️  Could not parse positions: {e}')
" 2>/dev/null
    fi
else
    echo "  No active positions file found"
fi
echo

# 5. Last scan time
echo "⏱️  Last Scan:"
if [ -f daily_scanner.log ]; then
    LAST_SCAN=$(tail -1 daily_scanner.log 2>/dev/null)
    if [ -n "$LAST_SCAN" ]; then
        echo "  $LAST_SCAN"
    else
        echo "  No recent scan found"
    fi
else
    echo "  No scan log found"
fi
echo

# 6. System resources
echo "💻 System Resources:"
CPU_USAGE=$(top -l 1 | grep "CPU usage" | awk '{print $3, $5}' | tr '\n' ' ')
echo "  CPU: $CPU_USAGE"

MEMORY_USAGE=$(ps aux | grep python | grep -v grep | awk '{sum+=$4} END {printf "%.1f%%", sum}')
echo "  Python Memory: $MEMORY_USAGE"

DISK_USAGE=$(df -h . | tail -1 | awk '{print $5 " used (" $4 " free)"}')
echo "  Disk: $DISK_USAGE"
echo

# 7. Recent errors
echo "⚠️  Recent Errors (Last 10):"
if [ -f daily_scanner.log ]; then
    ERROR_COUNT=$(grep -i "error\|exception\|failed" daily_scanner.log 2>/dev/null | tail -10 | wc -l | tr -d ' ')
    if [ "$ERROR_COUNT" -gt 0 ]; then
        grep -i "error\|exception\|failed" daily_scanner.log 2>/dev/null | tail -10 | sed 's/^/  /'
    else
        echo "  ✅ No recent errors"
    fi
else
    echo "  No log file to check"
fi
echo

# 8. Summary
echo "📊 HEALTH SUMMARY"
echo "=================="

# Calculate health score
HEALTH_SCORE=100

# Deduct points for stopped processes
[ -z "$SETUP_PID" ] && HEALTH_SCORE=$((HEALTH_SCORE - 30))
[ -z "$POSITION_PID" ] && HEALTH_SCORE=$((HEALTH_SCORE - 20))
[ -z "$TRADE_PID" ] && HEALTH_SCORE=$((HEALTH_SCORE - 20))

# Deduct points for errors
if [ -f daily_scanner.log ]; then
    RECENT_ERRORS=$(grep -i "error\|exception\|failed" daily_scanner.log 2>/dev/null | grep "$TODAY" | wc -l | tr -d ' ')
    if [ "$RECENT_ERRORS" -gt 5 ]; then
        HEALTH_SCORE=$((HEALTH_SCORE - 20))
    elif [ "$RECENT_ERRORS" -gt 0 ]; then
        HEALTH_SCORE=$((HEALTH_SCORE - 10))
    fi
fi

# Display health status
if [ "$HEALTH_SCORE" -ge 90 ]; then
    echo "✅ System Health: EXCELLENT ($HEALTH_SCORE/100)"
elif [ "$HEALTH_SCORE" -ge 70 ]; then
    echo "⚠️  System Health: GOOD ($HEALTH_SCORE/100)"
elif [ "$HEALTH_SCORE" -ge 50 ]; then
    echo "⚠️  System Health: NEEDS ATTENTION ($HEALTH_SCORE/100)"
else
    echo "❌ System Health: CRITICAL ($HEALTH_SCORE/100)"
fi

echo
echo "✅ Health check complete!"
echo

# Exit code based on health score
if [ "$HEALTH_SCORE" -ge 70 ]; then
    exit 0
else
    exit 1
fi
