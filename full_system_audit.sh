#!/bin/bash
# Complete system audit - verify everything is working correctly

echo "🔍 FOREXGOD COMPLETE SYSTEM AUDIT"
echo "=========================================="
echo ""

CORRECT_DIR="/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

# 1. FOLDER CHECK
echo "1️⃣ FOLDER VERIFICATION:"
if [ "$PWD" == "$CORRECT_DIR" ]; then
    echo "   ✅ Running from CORRECT folder"
else
    echo "   ❌ WARNING: In wrong folder!"
    echo "      Current: $PWD"
fi

# Check if old folder exists
if [ -d "/Users/forexgod/Desktop/trading-ai-agent apollo" ]; then
    echo "   ⚠️  OLD FOLDER STILL EXISTS!"
else
    echo "   ✅ Old folder removed"
fi

echo ""
echo "2️⃣ ACTIVE PROCESSES:"
monitor_count=$(ps aux | grep "python3.*monitor" | grep -v grep | wc -l | xargs)
echo "   Total monitors running: $monitor_count"

if [ "$monitor_count" -eq 0 ]; then
    echo "   ❌ NO MONITORS RUNNING!"
else
    ps aux | grep "python3.*monitor\.py" | grep -v grep | while read line; do
        pid=$(echo $line | awk '{print $2}')
        cmd=$(echo $line | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
        
        # Check working directory
        cwd=$(lsof -p $pid 2>/dev/null | grep cwd | awk '{print $NF}')
        
        if echo "$cwd" | grep -q "Glitch in Matrix"; then
            echo "   ✅ PID $pid: $cmd"
            echo "      Dir: $cwd"
        else
            echo "   ❌ PID $pid running from WRONG folder!"
            echo "      Dir: $cwd"
        fi
    done
fi

echo ""
echo "3️⃣ DUPLICATE CHECK:"
trade_monitor_count=$(ps aux | grep "trade_monitor.py" | grep -v grep | wc -l | xargs)
position_monitor_count=$(ps aux | grep "position_monitor.py" | grep -v grep | wc -l | xargs)
realtime_monitor_count=$(ps aux | grep "realtime_monitor.py" | grep -v grep | wc -l | xargs)

echo "   Trade Monitor: $trade_monitor_count (should be 1)"
echo "   Position Monitor: $position_monitor_count (should be 1)"  
echo "   Realtime Monitor: $realtime_monitor_count (should be 1)"

if [ "$trade_monitor_count" -gt 1 ] || [ "$position_monitor_count" -gt 1 ] || [ "$realtime_monitor_count" -gt 1 ]; then
    echo "   ❌ DUPLICATES DETECTED!"
else
    echo "   ✅ No duplicates"
fi

echo ""
echo "4️⃣ DATA FILES (recent activity):"
cd "$CORRECT_DIR"
for file in trade_history.json .last_trade_check.json .seen_positions.json monitoring_setups.json; do
    if [ -f "$file" ]; then
        mod_time=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$file")
        echo "   ✅ $file (updated: $mod_time)"
    else
        echo "   ❌ $file MISSING!"
    fi
done

echo ""
echo "5️⃣ LOGS (last 5 lines each):"
echo ""
echo "   📊 Trade Monitor:"
tail -5 logs/trade_monitor.log 2>/dev/null | head -3 || echo "      No log"

echo ""
echo "   👀 Position Monitor:"  
tail -5 logs/position_monitor.log 2>/dev/null | head -3 || echo "      No log"

echo ""
echo "6️⃣ CTRADER CONNECTION:"
python3 << 'PYEOF'
from ctrader_cbot_client import CTraderCBotClient
import sys
try:
    client = CTraderCBotClient()
    if client.is_available():
        print("   ✅ cBot connected on localhost:8767")
        # Quick data test
        df = client.get_historical_data('GBPUSD', 'Daily', 2)
        if df is not None and len(df) > 0:
            print(f"   ✅ Data retrieval working ({len(df)} bars)")
        else:
            print("   ⚠️  cBot responds but no data")
    else:
        print("   ❌ cBot not responding")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)
PYEOF

echo ""
echo "7️⃣ CRON JOBS:"
crontab -l 2>/dev/null | grep -v "^#" | grep -v "^$" | while read line; do
    if echo "$line" | grep -q "Glitch in Matrix"; then
        echo "   ✅ $line"
    else
        echo "   ⚠️  $line (check path)"
    fi
done

echo ""
echo "8️⃣ LAUNCHAGENT:"
if [ -f ~/Library/LaunchAgents/com.forexgod.morningscan.plist ]; then
    if grep -q "Glitch in Matrix" ~/Library/LaunchAgents/com.forexgod.morningscan.plist; then
        echo "   ✅ LaunchAgent configured with correct path"
    else
        echo "   ⚠️  LaunchAgent has old path"
    fi
else
    echo "   ℹ️  No LaunchAgent found"
fi

echo ""
echo "=========================================="
echo "✅ AUDIT COMPLETE!"
echo ""

