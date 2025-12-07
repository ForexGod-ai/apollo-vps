#!/usr/bin/env python3
"""
Auto-refresh Dashboard cu File Watcher
Monitorizează trade_history.json și notifică când se updatează
"""

import time
import os
from datetime import datetime
from loguru import logger
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class TradeHistoryWatcher(FileSystemEventHandler):
    """Watch for changes in trade_history.json"""
    
    def __init__(self):
        self.last_modified = None
        self.file_path = "trade_history.json"
    
    def on_modified(self, event):
        if event.src_path.endswith(self.file_path):
            logger.success("🔄 trade_history.json UPDATED!")
            self.show_current_data()
    
    def show_current_data(self):
        """Display current data from JSON"""
        try:
            import json
            with open(self.file_path, 'r') as f:
                trades = json.load(f)
            
            if not trades:
                logger.warning("⚠️  JSON is empty")
                return
            
            final_balance = trades[-1]['balance_after']
            total_trades = len(trades)
            total_profit = final_balance - 1000
            
            logger.info("="*70)
            logger.info(f"📊 LIVE DATA UPDATED at {datetime.now().strftime('%H:%M:%S')}")
            logger.info(f"   Trades: {total_trades}")
            logger.info(f"   Balance: ${final_balance:.2f}")
            logger.info(f"   Profit: ${total_profit:.2f}")
            logger.info(f"   Last trade: #{trades[-1]['ticket']} {trades[-1]['symbol']} = ${trades[-1]['profit']:.2f}")
            logger.info("="*70)
            
        except Exception as e:
            logger.error(f"❌ Error reading data: {e}")

def main():
    """Main function"""
    logger.info("="*70)
    logger.info("👁️  FILE WATCHER - Monitoring trade_history.json")
    logger.info("="*70)
    logger.info("")
    logger.info("🔍 Watching for changes in trade_history.json...")
    logger.info("")
    logger.info("💡 Când TradeHistorySyncer scrie în JSON, vei vedea instant aici!")
    logger.info("")
    logger.info("Press Ctrl+C to stop")
    logger.info("="*70)
    logger.info("")
    
    # Initial data
    watcher = TradeHistoryWatcher()
    watcher.show_current_data()
    
    # Start watching
    observer = Observer()
    observer.schedule(watcher, path='.', recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("\n🛑 Stopping watcher...")
    
    observer.join()

if __name__ == "__main__":
    main()
