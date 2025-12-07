"""
Auto-sync cTrader History to trade_history.json
Rulează continuu în background pentru sincronizare LIVE
"""
import time
import json
from loguru import logger
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class CTraderAutoSync:
    def __init__(self):
        self.json_file = "trade_history.json"
        self.update_interval = 10  # seconds
        self.account_id = os.getenv('CTRADER_ACCOUNT_ID', '9709773')
        
    def fetch_history_from_ctrader(self):
        """
        Fetch trade history from cTrader via Open API
        """
        try:
            # TODO: Implement cTrader Open API connection
            # For now, read from signals.json and mock data
            
            # In production, this will use cTrader Open API to fetch:
            # - All closed positions
            # - Entry/Exit prices
            # - Profit/Loss
            # - Running balance
            
            logger.info("🔄 Fetching history from cTrader...")
            
            # Placeholder: Return empty for now
            # Will be implemented with proper cTrader API
            return None
            
        except Exception as e:
            logger.error(f"❌ Error fetching from cTrader: {e}")
            return None
    
    def sync_to_json(self, trades):
        """Write trades to JSON file"""
        try:
            with open(self.json_file, 'w') as f:
                json.dump(trades, f, indent=4)
            logger.success(f"✅ Synced {len(trades)} trades to {self.json_file}")
            return True
        except Exception as e:
            logger.error(f"❌ Error writing to JSON: {e}")
            return False
    
    def run(self):
        """Main sync loop"""
        logger.info("🚀 Starting cTrader Auto-Sync...")
        logger.info(f"📁 Output: {self.json_file}")
        logger.info(f"⏱️ Update interval: {self.update_interval}s")
        logger.info(f"🔗 Account: {self.account_id}")
        
        while True:
            try:
                trades = self.fetch_history_from_ctrader()
                
                if trades:
                    self.sync_to_json(trades)
                else:
                    logger.warning("⚠️ No trades fetched, keeping existing data")
                
                time.sleep(self.update_interval)
                
            except KeyboardInterrupt:
                logger.info("🛑 Stopping cTrader Auto-Sync...")
                break
            except Exception as e:
                logger.error(f"❌ Sync error: {e}")
                time.sleep(self.update_interval)

if __name__ == "__main__":
    syncer = CTraderAutoSync()
    syncer.run()
