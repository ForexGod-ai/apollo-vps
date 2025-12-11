#!/bin/bash
# ========================================
# COMENZI MONITORIZARE ForexGod Trading AI
# ========================================

# 1. OPREȘTE MONITOARELE VECHI
pkill -f "position_monitor|trade_monitor"
sleep 1

# 2. PORNEȘTE MONITOARELE NOI (background cu logging)
cd "/Users/forexgod/Desktop/trading-ai-agent apollo"
nohup python3 position_monitor.py --loop > logs/position_monitor.log 2>&1 & echo $! > .position_monitor.pid
nohup python3 trade_monitor.py --loop > logs/trade_monitor.log 2>&1 & echo $! > .trade_monitor.pid

echo "✅ Monitors started!"
sleep 2

# 3. VERIFICĂ STATUSUL
echo ""
echo "📊 MONITOARE ACTIVE:"
ps aux | grep -E "position_monitor|trade_monitor" | grep -v grep

# 4. PORNEȘTE DASHBOARD (port 8080)
echo ""
echo "🎨 DASHBOARD:"
lsof -ti:8080 | xargs kill -9 2>/dev/null  # Kill old server
nohup python3 -m http.server 8080 > logs/http_server.log 2>&1 &
echo "✅ Dashboard: http://localhost:8080/dashboard_live.html"

# 5. SINCRONIZARE MANUALĂ cTrader (dacă TradeHistorySyncer nu rulează)
echo ""
echo "🔄 Sincronizare trade_history.json..."
python3 ctrader_sync.py

echo ""
echo "========================================
✅ SISTEM ACTIVAT!
========================================

📡 Monitoare:
   - position_monitor.py (detectează poziții noi)
   - trade_monitor.py (detectează TP/SL hits)

🎨 Dashboard:
   - http://localhost:8080/dashboard_live.html
   - Auto-refresh la 10 secunde

💾 Logs:
   - logs/position_monitor.log
   - logs/trade_monitor.log

🔍 Verificare:
   tail -f logs/trade_monitor.log

🛑 Oprire:
   pkill -f 'position_monitor|trade_monitor'
========================================"
