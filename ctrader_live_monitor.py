#!/usr/bin/env python3
"""
cTrader LIVE Monitor - Background service
Monitorizează și sincronizează AUTOMAT cu cTrader
"""

import time
import json
import subprocess
from datetime import datetime
from loguru import logger
import sys

def get_ctrader_balance():
    """
    Citește balanța LIVE din cTrader prin AppleScript (macOS)
    """
    # Placeholder - va fi implementat cu metode specifice
    # Pentru acum, returnăm None pentru a forța manual sync
    return None

def monitor_and_sync():
    """
    Monitorizează continuu și sincronizează
    """
    logger.info("="*70)
    logger.info("🔄 cTRADER LIVE MONITOR - BACKGROUND SERVICE")
    logger.info("="*70)
    logger.info("")
    logger.info("⚠️  IMPORTANT:")
    logger.info("   Acest script NU poate citi DIRECT din cTrader!")
    logger.info("   cTrader nu expune API public accesibil din Python!")
    logger.info("")
    logger.info("✅ SINGURA SOLUȚIE 100% AUTOMATĂ:")
    logger.info("   📌 TradeHistorySyncer.cs în cTrader")
    logger.info("   📌 Rulează NON-STOP în cTrader")
    logger.info("   📌 Scrie în trade_history.json la 10s")
    logger.info("   📌 Dashboard citește automat (refresh 5s)")
    logger.info("")
    logger.info("="*70)
    logger.info("")
    
    # Check if TradeHistorySyncer is updating the file
    logger.info("🔍 Verificare dacă TradeHistorySyncer rulează...")
    
    import os
    file_path = "trade_history.json"
    
    if not os.path.exists(file_path):
        logger.error(f"❌ {file_path} nu există!")
        return
    
    # Check last modification time
    last_modified = os.path.getmtime(file_path)
    last_modified_time = datetime.fromtimestamp(last_modified)
    time_diff = datetime.now() - last_modified_time
    
    logger.info(f"📄 trade_history.json ultima modificare: {last_modified_time.strftime('%H:%M:%S')}")
    logger.info(f"⏱️  Acum: {datetime.now().strftime('%H:%M:%S')}")
    logger.info(f"🕐 Diferență: {time_diff.seconds} secunde")
    
    if time_diff.seconds > 30:
        logger.error("")
        logger.error("❌ PROBLEMA DETECTATĂ!")
        logger.error(f"   trade_history.json NU a fost modificat de {time_diff.seconds}s")
        logger.error("   TradeHistorySyncer NU RULEAZĂ în cTrader!")
        logger.error("")
        logger.error("🔧 SOLUȚIA:")
        logger.error("   1. Deschide cTrader")
        logger.error("   2. Apasă Ctrl+Shift+A (Automate)")
        logger.error("   3. Găsește 'TradeHistorySyncer'")
        logger.error("   4. Drag pe chart BTCUSD")
        logger.error("   5. Verifică setări:")
        logger.error(f"      - JSON Path: {os.path.abspath(file_path)}")
        logger.error("      - Update Interval: 10")
        logger.error("   6. Click START ▶️")
        logger.error("")
        logger.error("   În Logs ar trebui să vezi:")
        logger.error("   🔄 Trade History Syncer Started")
        logger.error("   📊 Syncing X closed positions...")
        logger.error("   ✅ Synced X trades to JSON")
        logger.error("")
    else:
        logger.success("")
        logger.success("✅ TradeHistorySyncer pare să ruleze!")
        logger.success(f"   Ultima sincronizare acum {time_diff.seconds}s")
        logger.success("")
    
    # Load current data
    try:
        with open(file_path, 'r') as f:
            trades = json.load(f)
        
        if not trades:
            logger.warning("⚠️  trade_history.json este GOL!")
            logger.info("   Așteaptă primul sync de la TradeHistorySyncer...")
            return
        
        final_balance = trades[-1]['balance_after']
        total_trades = len(trades)
        total_profit = final_balance - 1000
        
        logger.info("📊 DATE CURENTE:")
        logger.info(f"   Trades: {total_trades}")
        logger.info(f"   Balance: ${final_balance:.2f}")
        logger.info(f"   Profit: ${total_profit:.2f}")
        logger.info("")
        
        logger.info("🔗 Dashboard: http://127.0.0.1:5001")
        logger.info("")
        
    except Exception as e:
        logger.error(f"❌ Error reading {file_path}: {e}")
    
    logger.info("="*70)


if __name__ == "__main__":
    try:
        monitor_and_sync()
    except KeyboardInterrupt:
        logger.info("\n🛑 Stopping monitor...")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)
