#!/usr/bin/env python3
"""
cTrader History Sync via REST API
Simple și functional - citește history și scrie în JSON
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class CTraderRESTSync:
    """
    Sync cTrader history via REST API
    """
    
    def __init__(self):
        self.account_id = os.getenv('CTRADER_ACCOUNT_ID', '9709773')
        self.access_token = os.getenv('CTRADER_ACCESS_TOKEN')
        self.demo = os.getenv('CTRADER_DEMO', 'True').lower() == 'true'
        
        # REST API endpoints - CORRECT URLS
        self.base_url = "https://demo-openapi.ctrader.com" if self.demo else "https://openapi.ctrader.com"
        self.json_file = "trade_history.json"
        self.update_interval = 10
        
        logger.info("🔄 cTrader REST Sync initialized")
        logger.info(f"   Account: {self.account_id}")
        logger.info(f"   Mode: {'DEMO' if self.demo else 'LIVE'}")
        logger.info(f"   API: {self.base_url}")
        logger.info(f"   Output: {self.json_file}")
    
    def fetch_account_balance(self):
        """Get current account balance"""
        try:
            url = f"{self.base_url}/v3/accounts/{self.account_id}"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                balance = data.get('balance', 0) / 100  # cents to dollars
                logger.success(f"✅ Current balance: ${balance:.2f}")
                return balance
            else:
                logger.error(f"❌ API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Fetch balance error: {e}")
            return None
    
    def fetch_deals_history(self):
        """Get deals/trades history"""
        try:
            # Use /v3/accounts/{id}/history endpoint for trade history
            url = f"{self.base_url}/v3/accounts/{self.account_id}/history"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Get last 30 days of history
            end_time = int(time.time() * 1000)
            start_time = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)
            
            params = {
                'from': start_time,
                'to': end_time
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                deals = data.get('deals', [])
                logger.success(f"✅ Fetched {len(deals)} deals")
                return deals
            else:
                logger.error(f"❌ API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Fetch deals error: {e}")
            return None
    
    def sync_to_json(self):
        """Sync history to JSON"""
        logger.info("📥 Syncing from cTrader...")
        
        # Get balance
        balance = self.fetch_account_balance()
        
        if balance is None:
            logger.warning("⚠️ Could not fetch balance, using REST API fallback...")
            # If REST API doesn't work, keep existing data
            logger.info("💡 Install TradeHistorySyncer.cs in cTrader for automatic sync!")
            return False
        
        # Get deals
        deals = self.fetch_deals_history()
        
        if deals is None:
            logger.warning("⚠️ Could not fetch deals")
            return False
        
        # Convert deals to trade format
        trades = []
        running_balance = 1000.0
        
        for deal in sorted(deals, key=lambda x: x.get('timestamp', 0)):
            profit = deal.get('profit', 0) / 100.0
            running_balance += profit
            
            trade = {
                'ticket': deal.get('dealId', 0),
                'symbol': deal.get('symbol', 'UNKNOWN'),
                'direction': 'BUY' if deal.get('side') == 'BUY' else 'SELL',
                'entry_price': deal.get('entryPrice', 0.0),
                'closing_price': deal.get('closePrice', 0.0),
                'lot_size': deal.get('volume', 0.0) / 100000.0,
                'open_time': datetime.fromtimestamp(deal.get('timestamp', 0) / 1000).isoformat(),
                'close_time': datetime.fromtimestamp(deal.get('closeTime', deal.get('timestamp', 0)) / 1000).isoformat(),
                'status': 'CLOSED',
                'profit': profit,
                'pips': 0.0,
                'balance_after': running_balance
            }
            
            trades.append(trade)
        
        # Save to JSON
        with open(self.json_file, 'w') as f:
            json.dump(trades, f, indent=4)
        
        logger.success(f"✅ Synced {len(trades)} trades to {self.json_file}")
        logger.info(f"💰 Final balance: ${running_balance:.2f}")
        
        return True
    
    def run_continuous(self):
        """Run sync loop"""
        logger.info("🚀 Starting continuous sync...")
        
        while True:
            try:
                success = self.sync_to_json()
                
                if success:
                    logger.success("✅ Sync complete")
                else:
                    logger.warning("⚠️ Sync failed, will retry")
                
                logger.info(f"⏳ Next sync in {self.update_interval}s...")
                time.sleep(self.update_interval)
                
            except KeyboardInterrupt:
                logger.info("🛑 Stopping sync...")
                break
            except Exception as e:
                logger.error(f"❌ Sync error: {e}")
                time.sleep(self.update_interval)


def main():
    """Main function"""
    logger.info("="*70)
    logger.info("🔄 cTRADER HISTORY SYNC (REST API)")
    logger.info("="*70)
    
    syncer = CTraderRESTSync()
    
    # Try sync once
    success = syncer.sync_to_json()
    
    if success:
        logger.success("\n✅ SUCCESS! History synced from cTrader!")
        logger.info(f"📁 Check: {syncer.json_file}")
        logger.info(f"🔗 Dashboard: http://127.0.0.1:5001")
    else:
        logger.error("\n❌ Sync failed - using TradeHistorySyncer.cs fallback")
        logger.info("\n💡 SOLUȚIA FINALĂ:")
        logger.info("   1. Deschide cTrader → Automate (Ctrl+Shift+A)")
        logger.info("   2. New cBot → TradeHistorySyncer")
        logger.info("   3. Copiază codul din TradeHistorySyncer.cs")
        logger.info("   4. Build → Drag pe chart → START")
        logger.info("   5. Botul va sincroniza automat la fiecare 10s!")
    
    logger.info("\n" + "="*70)


if __name__ == "__main__":
    main()
