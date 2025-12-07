#!/usr/bin/env python3
"""
cTrader LIVE Sync Manager
Continuous synchronization with cTrader account via Open API
Auto-updates balance, positions, and trades in real-time
"""

import os
import time
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
from dotenv import load_dotenv
from threading import Thread, Event

load_dotenv()


class CTraderLiveSync:
    """
    Real-time synchronization with cTrader account
    Runs in background thread and updates local state continuously
    """
    
    def __init__(self):
        self.account_id = os.getenv('CTRADER_ACCOUNT_ID', '9709773')
        self.access_token = os.getenv('CTRADER_ACCESS_TOKEN')
        self.client_id = os.getenv('CTRADER_CLIENT_ID')
        self.client_secret = os.getenv('CTRADER_CLIENT_SECRET')
        self.demo = os.getenv('CTRADER_DEMO', 'True').lower() == 'true'
        
        # API endpoints
        self.api_base = "https://openapi.ctrader.com"
        self.demo_api_base = "https://demo-openapi.ctrader.com"
        
        # Sync state
        self.running = False
        self.stop_event = Event()
        self.sync_interval = 30  # seconds
        
        # Local cache
        self.last_balance = None
        self.last_equity = None
        self.last_positions = []
        self.last_sync_time = None
        
        self.history_file = 'trade_history.json'
        
        logger.info(f"🔄 cTrader LIVE Sync initialized")
        logger.info(f"   Account: {self.account_id}")
        logger.info(f"   Mode: {'DEMO' if self.demo else 'LIVE'}")
        logger.info(f"   API configured: {bool(self.access_token or (self.client_id and self.client_secret))}")
    
    def authenticate(self) -> Optional[str]:
        """
        Get OAuth token if using Client ID/Secret
        Returns access token or None
        """
        if self.access_token:
            return self.access_token
        
        if not (self.client_id and self.client_secret):
            logger.warning("⚠️  No cTrader API credentials configured")
            return None
        
        try:
            logger.info("🔐 Authenticating with cTrader API...")
            
            url = f"{self.api_base}/oauth2/token"
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                token = token_data.get('access_token')
                logger.success("✅ Authentication successful")
                return token
            else:
                logger.error(f"❌ Authentication failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            return None
    
    def fetch_account_info(self, token: str) -> Optional[Dict]:
        """
        Fetch account balance and info from cTrader API
        """
        try:
            base = self.demo_api_base if self.demo else self.api_base
            url = f"{base}/v3/accounts/{self.account_id}"
            headers = {'Authorization': f'Bearer {token}'}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                account_info = {
                    'account_id': self.account_id,
                    'balance': float(data.get('balance', 0)),
                    'equity': float(data.get('equity', 0)),
                    'margin': float(data.get('margin', 0)),
                    'free_margin': float(data.get('freeMargin', 0)),
                    'currency': data.get('currency', 'USD'),
                    'leverage': data.get('leverage', 100),
                    'unrealized_pnl': float(data.get('unrealizedPnL', 0)),
                    'timestamp': datetime.now().isoformat()
                }
                
                return account_info
            else:
                logger.debug(f"API returned {response.status_code}")
                return None
                
        except Exception as e:
            logger.debug(f"Fetch account error: {e}")
            return None
    
    def fetch_open_positions(self, token: str) -> List[Dict]:
        """
        Fetch open positions from cTrader API
        """
        try:
            base = self.demo_api_base if self.demo else self.api_base
            url = f"{base}/v3/accounts/{self.account_id}/positions"
            headers = {'Authorization': f'Bearer {token}'}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                positions_data = data.get('positions', data.get('data', []))
                
                positions = []
                for pos in positions_data:
                    position = {
                        'ticket': pos.get('id', pos.get('positionId')),
                        'symbol': pos.get('symbol', pos.get('symbolName')),
                        'direction': 'BUY' if pos.get('tradeType', pos.get('side')) == 'BUY' else 'SELL',
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'current_price': float(pos.get('currentPrice', 0)),
                        'lot_size': float(pos.get('volume', 0)) / 100000,  # Convert to lots
                        'profit': float(pos.get('pnl', pos.get('profit', 0))),
                        'open_time': pos.get('openTime', pos.get('createTime')),
                        'status': 'OPEN'
                    }
                    positions.append(position)
                
                return positions
            else:
                logger.debug(f"Positions API returned {response.status_code}")
                return []
                
        except Exception as e:
            logger.debug(f"Fetch positions error: {e}")
            return []
    
    def fetch_trade_history(self, token: str, days: int = 30) -> List[Dict]:
        """
        Fetch closed trades from cTrader API
        """
        try:
            base = self.demo_api_base if self.demo else self.api_base
            
            # Calculate time range
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
            
            url = f"{base}/v3/accounts/{self.account_id}/history"
            headers = {'Authorization': f'Bearer {token}'}
            params = {
                'from': start_time,
                'to': end_time
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                trades_data = data.get('trades', data.get('data', []))
                
                trades = []
                for trade in trades_data:
                    closed_trade = {
                        'ticket': trade.get('id', trade.get('dealId')),
                        'symbol': trade.get('symbol', trade.get('symbolName')),
                        'direction': 'BUY' if trade.get('tradeType', trade.get('side')) == 'BUY' else 'SELL',
                        'entry_price': float(trade.get('entryPrice', 0)),
                        'closing_price': float(trade.get('closePrice', 0)),
                        'lot_size': float(trade.get('volume', 0)) / 100000,
                        'open_time': trade.get('openTime', trade.get('createTime')),
                        'close_time': trade.get('closeTime'),
                        'profit': float(trade.get('pnl', trade.get('profit', 0))),
                        'status': 'CLOSED'
                    }
                    trades.append(closed_trade)
                
                return trades
            else:
                logger.debug(f"History API returned {response.status_code}")
                return []
                
        except Exception as e:
            logger.debug(f"Fetch history error: {e}")
            return []
    
    def update_local_history(self, account_info: Dict, positions: List[Dict], closed_trades: List[Dict]):
        """
        Update trade_history.json with live data from cTrader
        """
        try:
            # Combine closed trades and open positions
            all_trades = closed_trades + positions
            
            # Sort by time
            all_trades.sort(key=lambda x: x.get('open_time', ''), reverse=False)
            
            # Save to file
            with open(self.history_file, 'w') as f:
                json.dump(all_trades, f, indent=4)
            
            logger.success(f"✅ Updated {self.history_file} with {len(all_trades)} trades")
            logger.info(f"   Balance: ${account_info['balance']:.2f}")
            logger.info(f"   Equity: ${account_info['equity']:.2f}")
            logger.info(f"   Open positions: {len(positions)}")
            logger.info(f"   Closed trades: {len(closed_trades)}")
            
            # Update cache
            self.last_balance = account_info['balance']
            self.last_equity = account_info['equity']
            self.last_positions = positions
            self.last_sync_time = datetime.now()
            
        except Exception as e:
            logger.error(f"❌ Error updating local history: {e}")
    
    def sync_once(self) -> bool:
        """
        Perform one sync cycle
        Returns True if successful
        """
        try:
            # Get authentication token
            token = self.authenticate()
            if not token:
                logger.warning("⚠️  Cannot sync - no API token")
                return False
            
            logger.info("🔄 Syncing with cTrader...")
            
            # Fetch account info
            account_info = self.fetch_account_info(token)
            if not account_info:
                logger.warning("⚠️  Failed to fetch account info")
                return False
            
            # Fetch positions
            positions = self.fetch_open_positions(token)
            
            # Fetch closed trades
            closed_trades = self.fetch_trade_history(token, days=30)
            
            # Update local files
            self.update_local_history(account_info, positions, closed_trades)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Sync error: {e}")
            return False
    
    def start_background_sync(self):
        """
        Start continuous background sync
        """
        if self.running:
            logger.warning("⚠️  Sync already running")
            return
        
        self.running = True
        self.stop_event.clear()
        
        def sync_loop():
            logger.info(f"🔄 Starting background sync (every {self.sync_interval}s)")
            
            while not self.stop_event.is_set():
                try:
                    self.sync_once()
                except Exception as e:
                    logger.error(f"❌ Sync loop error: {e}")
                
                # Wait for next cycle
                self.stop_event.wait(self.sync_interval)
            
            logger.info("🛑 Background sync stopped")
        
        # Start in background thread
        sync_thread = Thread(target=sync_loop, daemon=True)
        sync_thread.start()
        
        logger.success("✅ Background sync started")
    
    def stop_background_sync(self):
        """
        Stop background sync
        """
        if not self.running:
            return
        
        logger.info("🛑 Stopping background sync...")
        self.running = False
        self.stop_event.set()


def test_live_sync():
    """Test the live sync functionality"""
    logger.info("="*70)
    logger.info("🧪 TESTING CTRADER LIVE SYNC")
    logger.info("="*70)
    
    sync_manager = CTraderLiveSync()
    
    # Test single sync
    logger.info("\n📊 Testing single sync...")
    success = sync_manager.sync_once()
    
    if success:
        logger.success("✅ Single sync completed successfully")
    else:
        logger.warning("⚠️  Sync failed - check API credentials")
        logger.info("\n💡 To enable live sync:")
        logger.info("   1. Get access token from: https://connect.spotware.com/")
        logger.info("   2. Add to .env file:")
        logger.info("      CTRADER_ACCESS_TOKEN=your_token_here")
    
    logger.info("\n" + "="*70)


if __name__ == "__main__":
    test_live_sync()
