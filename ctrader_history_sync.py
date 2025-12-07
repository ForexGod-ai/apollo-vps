#!/usr/bin/env python3
"""
cTrader History Sync - Citește history din cTrader și scrie în trade_history.json
Rulează continuu pentru sincronizare LIVE
"""

import os
import time
import json
import asyncio
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

# cTrader Open API SDK
try:
    from ctrader_open_api import Client, Protobuf, TcpProtocol, Auth, EndPoints
    from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import *
    from ctrader_open_api.messages.OpenApiMessages_pb2 import *
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.warning("⚠️ cTrader SDK not available, using fallback")

load_dotenv()


class CTraderHistorySync:
    """
    Sync cTrader History to trade_history.json
    """
    
    def __init__(self):
        self.client_id = os.getenv('CTRADER_CLIENT_ID')
        self.client_secret = os.getenv('CTRADER_CLIENT_SECRET')
        self.access_token = os.getenv('CTRADER_ACCESS_TOKEN')
        self.account_id = int(os.getenv('CTRADER_ACCOUNT_ID', '9709773'))
        
        self.host = "demo.ctraderapi.com"
        self.port = 5035
        
        self.json_file = "trade_history.json"
        self.update_interval = 10  # seconds
        
        self.client = None
        self.is_connected = False
        self.trades_history = []
        
        logger.info("🔄 cTrader History Sync initialized")
        logger.info(f"   Account: {self.account_id}")
        logger.info(f"   Output: {self.json_file}")
        logger.info(f"   Interval: {self.update_interval}s")
    
    async def connect(self):
        """Connect to cTrader API"""
        if not SDK_AVAILABLE:
            logger.error("❌ cTrader SDK not installed!")
            logger.info("💡 Run: pip install ctrader-open-api")
            return False
        
        try:
            logger.info("🔌 Connecting to cTrader...")
            
            self.client = Client(self.host, self.port, TcpProtocol)
            self.client.setMessageHandler(self._message_handler)
            
            await self.client.connect()
            
            # App auth
            app_auth = ProtoOAApplicationAuthReq()
            app_auth.clientId = self.client_id
            app_auth.clientSecret = self.client_secret
            
            await self.client.send(app_auth)
            await asyncio.sleep(1)
            
            # Account auth
            acc_auth = ProtoOAAccountAuthReq()
            acc_auth.ctidTraderAccountId = self.account_id
            acc_auth.accessToken = self.access_token
            
            await self.client.send(acc_auth)
            await asyncio.sleep(1)
            
            self.is_connected = True
            logger.success("✅ Connected to cTrader API!")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    def _message_handler(self, message):
        """Handle messages from cTrader"""
        try:
            payload_type = message.payloadType
            
            if payload_type == ProtoOAApplicationAuthRes.ID:
                logger.success("✅ App authenticated")
            
            elif payload_type == ProtoOAAccountAuthRes.ID:
                logger.success("✅ Account authenticated")
            
            elif payload_type == ProtoOADealsListRes.ID:
                # History deals received
                deals_res = Protobuf.extract(message)
                logger.info(f"📊 Received {len(deals_res.deal)} deals")
                
                self.trades_history = []
                running_balance = 1000.0
                
                for deal in deals_res.deal:
                    profit = deal.grossProfit / 100.0  # cents to dollars
                    running_balance += profit
                    
                    trade = {
                        'ticket': deal.dealId,
                        'symbol': deal.symbolName,
                        'direction': 'BUY' if deal.tradeSide == BUY else 'SELL',
                        'entry_price': deal.executionPrice,
                        'closing_price': deal.closePrice if hasattr(deal, 'closePrice') else deal.executionPrice,
                        'lot_size': deal.volume / 100000.0,
                        'open_time': datetime.fromtimestamp(deal.executionTimestamp / 1000).isoformat(),
                        'close_time': datetime.fromtimestamp(deal.executionTimestamp / 1000).isoformat(),
                        'status': 'CLOSED',
                        'profit': profit,
                        'pips': 0.0,  # Calculate if needed
                        'balance_after': running_balance
                    }
                    
                    self.trades_history.append(trade)
                
                logger.success(f"✅ Parsed {len(self.trades_history)} trades")
                self._save_to_json()
            
            elif payload_type == ProtoOAErrorRes.ID:
                error = Protobuf.extract(message)
                logger.error(f"❌ API Error: {error.errorCode}")
            
        except Exception as e:
            logger.error(f"❌ Message handler error: {e}")
    
    async def fetch_history(self):
        """Fetch deals history from cTrader"""
        try:
            if not self.is_connected:
                logger.error("❌ Not connected")
                return False
            
            logger.info("📥 Requesting deals history...")
            
            deals_req = ProtoOADealListReq()
            deals_req.ctidTraderAccountId = self.account_id
            deals_req.fromTimestamp = 0  # All history
            deals_req.toTimestamp = int(time.time() * 1000)
            
            await self.client.send(deals_req)
            
            # Wait for response
            await asyncio.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Fetch history error: {e}")
            return False
    
    def _save_to_json(self):
        """Save trades to JSON file"""
        try:
            with open(self.json_file, 'w') as f:
                json.dump(self.trades_history, f, indent=4)
            
            logger.success(f"✅ Saved {len(self.trades_history)} trades to {self.json_file}")
            
            if self.trades_history:
                final_balance = self.trades_history[-1]['balance_after']
                logger.info(f"💰 Final balance: ${final_balance:.2f}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Save error: {e}")
            return False
    
    async def run_once(self):
        """Run sync once"""
        connected = await self.connect()
        
        if connected:
            await self.fetch_history()
            await asyncio.sleep(2)
            
            if self.client:
                await self.client.disconnect()
        
        return len(self.trades_history)
    
    async def run_continuous(self):
        """Run sync continuously"""
        logger.info("🚀 Starting continuous sync...")
        
        while True:
            try:
                count = await self.run_once()
                
                if count > 0:
                    logger.success(f"✅ Synced {count} trades")
                else:
                    logger.warning("⚠️ No trades synced")
                
                logger.info(f"⏳ Waiting {self.update_interval}s...")
                await asyncio.sleep(self.update_interval)
                
            except KeyboardInterrupt:
                logger.info("🛑 Stopping sync...")
                break
            except Exception as e:
                logger.error(f"❌ Sync error: {e}")
                await asyncio.sleep(self.update_interval)


async def main():
    """Main function"""
    logger.info("="*70)
    logger.info("🔄 cTRADER HISTORY SYNC")
    logger.info("="*70)
    
    syncer = CTraderHistorySync()
    
    # Run once
    count = await syncer.run_once()
    
    if count > 0:
        logger.success(f"\n✅ SUCCESS! Synced {count} trades from cTrader!")
        logger.info(f"📁 Check: {syncer.json_file}")
    else:
        logger.error("\n❌ No trades synced!")
    
    logger.info("\n" + "="*70)


if __name__ == "__main__":
    asyncio.run(main())
