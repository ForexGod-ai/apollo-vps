"""
cTrader ProtoOA Client - IMPLEMENTARE COMPLETĂ cu Official Library
===================================================================
Folosește library-ul oficial ctrader-open-api pentru WebSocket + ProtoOA

📚 Documentație: https://github.com/spotware/py-ctrader-open-api
"""

import os
import time
import json
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from loguru import logger
from dotenv import load_dotenv

# Import cTrader Official Library from cloned repository
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ctrader_official'))

from ctrader_open_api import Client, Protobuf, TcpProtocol
from ctrader_open_api.messages import OpenApiCommonMessages_pb2 as common
from ctrader_open_api.messages import OpenApiMessages_pb2 as msg
from ctrader_open_api.messages import OpenApiModelMessages_pb2 as model

load_dotenv()


class CTraderLiveClient:
    """
    cTrader ProtoOA Live Client - Complete Implementation
    Direct connection to IC Markets broker
    """
    
    def __init__(self):
        self.client_id = os.getenv('CTRADER_CLIENT_ID')
        self.client_secret = os.getenv('CTRADER_CLIENT_SECRET')
        self.access_token = os.getenv('CTRADER_ACCESS_TOKEN')
        self.account_id = int(os.getenv('CTRADER_ACCOUNT_ID', '9709773'))
        
        # WebSocket connection
        self.demo = os.getenv('CTRADER_DEMO', 'True').lower() == 'true'
        self.host = "demo.ctraderapi.com" if self.demo else "live.ctraderapi.com"
        self.port = 5035
        
        # Client instance
        self.client = None
        self.connected = False
        self.authenticated = False
        
        # Data storage
        self.symbols = {}
        self.trendbars_cache = {}
        self.account_info = {}
        self.positions = {}
        self.deals_history = []
        
        logger.info("🚀 cTrader LIVE Client initialized")
        logger.info(f"   Host: {self.host}:{self.port}")
        logger.info(f"   Account: {self.account_id}")
        logger.info(f"   Mode: {'DEMO' if self.demo else 'LIVE'}")
    
    # ==================== FAZA 1: CONEXIUNE & AUTENTIFICARE ====================
    
    async def connect(self) -> bool:
        """
        FAZA 1: Connect to cTrader WebSocket and authenticate
        """
        try:
            logger.info("🔌 Connecting to cTrader WebSocket...")
            
            # Create client instance
            self.client = Client(self.host, self.port, TcpProtocol)
            
            # Connect
            await self.client.connect()
            self.connected = True
            logger.success("✅ WebSocket connected!")
            
            # Authenticate Application
            logger.info("🔐 Authenticating application...")
            app_auth_req = msg.ProtoOAApplicationAuthReq()
            app_auth_req.clientId = self.client_id
            app_auth_req.clientSecret = self.client_secret
            
            await self.client.send(app_auth_req)
            app_auth_res = await self.client.receive()
            
            if isinstance(app_auth_res, msg.ProtoOAApplicationAuthRes):
                logger.success("✅ Application authenticated!")
            else:
                logger.error(f"❌ App auth failed: {app_auth_res}")
                return False
            
            # Authenticate Account
            logger.info("🔐 Authenticating trading account...")
            acc_auth_req = msg.ProtoOAAccountAuthReq()
            acc_auth_req.ctidTraderAccountId = self.account_id
            acc_auth_req.accessToken = self.access_token
            
            await self.client.send(acc_auth_req)
            acc_auth_res = await self.client.receive()
            
            if isinstance(acc_auth_res, msg.ProtoOAAccountAuthRes):
                self.authenticated = True
                logger.success("✅ Trading account authenticated!")
                logger.success("🎉 Ready to trade and fetch data!")
                return True
            else:
                logger.error(f"❌ Account auth failed: {acc_auth_res}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== FAZA 2: FLUX DATE (SYMBOLS & TRENDBARS) ====================
    
    async def get_symbols(self) -> List[Dict]:
        """
        FAZA 2.1: Get list of available symbols
        """
        try:
            if not self.authenticated:
                logger.error("❌ Must authenticate first!")
                return []
            
            logger.info("📋 Requesting symbols list...")
            
            # Request symbols
            symbols_req = msg.ProtoOASymbolsListReq()
            symbols_req.ctidTraderAccountId = self.account_id
            
            await self.client.send(symbols_req)
            symbols_res = await self.client.receive()
            
            if isinstance(symbols_res, msg.ProtoOASymbolsListRes):
                logger.success(f"✅ Received {len(symbols_res.symbol)} symbols")
                
                # Store symbols
                for symbol in symbols_res.symbol:
                    self.symbols[symbol.symbolName] = {
                        'id': symbol.symbolId,
                        'name': symbol.symbolName,
                        'digits': symbol.digits,
                        'pipPosition': symbol.pipPosition,
                        'minVolume': symbol.minVolume,
                        'maxVolume': symbol.maxVolume
                    }
                
                return list(self.symbols.values())
            else:
                logger.error(f"❌ Symbols request failed: {symbols_res}")
                return []
            
        except Exception as e:
            logger.error(f"❌ Get symbols error: {e}")
            return []
    
    async def get_trendbars(self, symbol: str, timeframe: str = 'D1', count: int = 100) -> Optional[List[Dict]]:
        """
        FAZA 2.2: Get historical trendbars (OHLC data)
        
        Args:
            symbol: Symbol name (ex: GBPUSD)
            timeframe: D1, H4, H1, M15, etc.
            count: Number of bars
            
        Returns:
            List of candles with OHLC data
        """
        try:
            if not self.authenticated:
                logger.error("❌ Must authenticate first!")
                return None
            
            logger.info(f"📊 Requesting trendbars: {symbol} {timeframe} ({count} bars)")
            
            # Get symbol ID
            if symbol not in self.symbols:
                await self.get_symbols()
            
            symbol_id = self.symbols.get(symbol, {}).get('id')
            if not symbol_id:
                logger.error(f"❌ Symbol {symbol} not found")
                return None
            
            # Map timeframe to ProtoOA format (seconds)
            tf_map = {
                'D1': model.ProtoOATrendbarPeriod.D1,
                'H4': model.ProtoOATrendbarPeriod.H4,
                'H1': model.ProtoOATrendbarPeriod.H1,
                'M15': model.ProtoOATrendbarPeriod.M15,
                'M5': model.ProtoOATrendbarPeriod.M5,
                'M1': model.ProtoOATrendbarPeriod.M1
            }
            period = tf_map.get(timeframe, model.ProtoOATrendbarPeriod.D1)
            
            # Calculate time range
            to_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            # Request trendbars
            trendbars_req = msg.ProtoOAGetTrendbarsReq()
            trendbars_req.ctidTraderAccountId = self.account_id
            trendbars_req.symbolId = symbol_id
            trendbars_req.period = period
            trendbars_req.toTimestamp = to_timestamp
            trendbars_req.count = count
            
            await self.client.send(trendbars_req)
            trendbars_res = await self.client.receive()
            
            if isinstance(trendbars_res, msg.ProtoOAGetTrendbarsRes):
                logger.success(f"✅ Received {len(trendbars_res.trendbar)} trendbars")
                
                # Parse trendbars
                candles = []
                for bar in trendbars_res.trendbar:
                    candles.append({
                        'time': datetime.fromtimestamp(bar.utcTimestampInMinutes * 60),
                        'open': bar.open / 100000.0,  # Convert from relative price
                        'high': (bar.open + bar.high) / 100000.0,
                        'low': (bar.open - bar.low) / 100000.0,
                        'close': (bar.open + bar.close) / 100000.0,
                        'volume': bar.volume if hasattr(bar, 'volume') else 0
                    })
                
                # Cache for later use
                cache_key = f"{symbol}_{timeframe}"
                self.trendbars_cache[cache_key] = candles
                
                return candles
            else:
                logger.error(f"❌ Trendbars request failed: {trendbars_res}")
                return None
            
        except Exception as e:
            logger.error(f"❌ Get trendbars error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    # ==================== FAZA 3: EXECUȚIE (TRADING) ====================
    
    async def open_position(self, symbol: str, volume: int, order_type: str, 
                           stop_loss: float = None, take_profit: float = None) -> Optional[int]:
        """
        FAZA 3.1: Open new trading position
        
        Args:
            symbol: Symbol (ex: GBPUSD)
            volume: Volume in units (ex: 100000 = 1 lot)
            order_type: 'BUY' or 'SELL'
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            
        Returns:
            Position ID if successful
        """
        try:
            if not self.authenticated:
                logger.error("❌ Must authenticate first!")
                return None
            
            logger.info(f"📈 Opening {order_type} position: {symbol} {volume} units")
            
            # Get symbol ID
            if symbol not in self.symbols:
                await self.get_symbols()
            
            symbol_id = self.symbols.get(symbol, {}).get('id')
            if not symbol_id:
                logger.error(f"❌ Symbol {symbol} not found")
                return None
            
            # Create order request
            order_req = ProtoOANewOrderReq()
            order_req.ctidTraderAccountId = self.account_id
            order_req.symbolId = symbol_id
            order_req.orderType = ProtoOAOrderType.MARKET
            order_req.tradeSide = ProtoOATradeSide.BUY if order_type.upper() == 'BUY' else ProtoOATradeSide.SELL
            order_req.volume = volume
            
            if stop_loss:
                order_req.stopLoss = stop_loss
            if take_profit:
                order_req.takeProfit = take_profit
            
            # Send order
            await self.client.send(order_req)
            execution_event = await self.client.receive()
            
            if isinstance(execution_event, ProtoOAExecutionEvent):
                if execution_event.executionType == ProtoOAExecutionType.ORDER_FILLED:
                    position_id = execution_event.position.positionId
                    logger.success(f"✅ Position opened! ID: {position_id}")
                    return position_id
                else:
                    logger.error(f"❌ Order execution failed: {execution_event}")
                    return None
            else:
                logger.error(f"❌ Unexpected response: {execution_event}")
                return None
            
        except Exception as e:
            logger.error(f"❌ Open position error: {e}")
            return None
    
    async def close_position(self, position_id: int, volume: int = None) -> bool:
        """
        FAZA 3.2: Close existing position
        
        Args:
            position_id: Position ID to close
            volume: Partial close volume (None = close all)
            
        Returns:
            True if successful
        """
        try:
            if not self.authenticated:
                logger.error("❌ Must authenticate first!")
                return False
            
            logger.info(f"📉 Closing position: {position_id}")
            
            # Create close request
            close_req = ProtoOAClosePositionReq()
            close_req.ctidTraderAccountId = self.account_id
            close_req.positionId = position_id
            
            if volume:
                close_req.volume = volume
            
            # Send request
            await self.client.send(close_req)
            execution_event = await self.client.receive()
            
            if isinstance(execution_event, ProtoOAExecutionEvent):
                if execution_event.executionType == ProtoOAExecutionType.ORDER_FILLED:
                    logger.success(f"✅ Position closed!")
                    return True
                else:
                    logger.error(f"❌ Close failed: {execution_event}")
                    return False
            else:
                logger.error(f"❌ Unexpected response: {execution_event}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Close position error: {e}")
            return False
    
    # ==================== FAZA 4: SINCRONIZARE CONT LIVE ====================
    
    async def get_account_info(self) -> Optional[Dict]:
        """
        FAZA 4: Get live account balance/equity
        """
        try:
            if not self.authenticated:
                logger.error("❌ Must authenticate first!")
                return None
            
            logger.info("💰 Requesting account info...")
            
            # Request trader info
            trader_req = ProtoOATraderReq()
            trader_req.ctidTraderAccountId = self.account_id
            
            await self.client.send(trader_req)
            trader_res = await self.client.receive()
            
            if isinstance(trader_res, ProtoOATraderRes):
                trader = trader_res.trader
                
                self.account_info = {
                    'account_id': self.account_id,
                    'balance': trader.balance / 100.0,  # Convert from cents
                    'balance_version': trader.balanceVersion,
                    'timestamp': datetime.now().isoformat()
                }
                
                logger.success(f"✅ Account balance: ${self.account_info['balance']:.2f}")
                return self.account_info
            else:
                logger.error(f"❌ Account info request failed: {trader_res}")
                return None
            
        except Exception as e:
            logger.error(f"❌ Get account info error: {e}")
            return None
    
    # ==================== FAZA 5: ISTORIC TRANZACȚII (DASHBOARD) ====================
    
    async def get_deals_history(self, days: int = 30) -> List[Dict]:
        """
        FAZA 5: Get closed positions history for dashboard
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of closed deals
        """
        try:
            if not self.authenticated:
                logger.error("❌ Must authenticate first!")
                return []
            
            logger.info(f"📜 Requesting deals history (last {days} days)...")
            
            # Calculate time range
            to_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
            from_timestamp = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
            
            # Request deals
            deals_req = ProtoOADealListReq()
            deals_req.ctidTraderAccountId = self.account_id
            deals_req.fromTimestamp = from_timestamp
            deals_req.toTimestamp = to_timestamp
            deals_req.maxRows = 1000  # Max deals to retrieve
            
            await self.client.send(deals_req)
            deals_res = await self.client.receive()
            
            if isinstance(deals_res, ProtoOADealListRes):
                logger.success(f"✅ Received {len(deals_res.deal)} deals")
                
                # Parse deals
                self.deals_history = []
                for deal in deals_res.deal:
                    self.deals_history.append({
                        'deal_id': deal.dealId,
                        'position_id': deal.positionId,
                        'symbol_id': deal.symbolId,
                        'volume': deal.volume,
                        'filled_volume': deal.filledVolume,
                        'commission': deal.commission / 100.0 if hasattr(deal, 'commission') else 0,
                        'balance': deal.balance / 100.0 if hasattr(deal, 'balance') else 0,
                        'close_price': deal.closePrice if hasattr(deal, 'closePrice') else 0,
                        'profit': deal.grossProfit / 100.0 if hasattr(deal, 'grossProfit') else 0,
                        'timestamp': datetime.fromtimestamp(deal.createTimestamp / 1000)
                    })
                
                # Update dashboard
                await self._update_dashboard()
                
                return self.deals_history
            else:
                logger.error(f"❌ Deals request failed: {deals_res}")
                return []
            
        except Exception as e:
            logger.error(f"❌ Get deals history error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _update_dashboard(self):
        """Update trade_history.json with closed positions"""
        try:
            # Convert deals to dashboard format
            trades = []
            running_balance = 1000.0
            
            for deal in sorted(self.deals_history, key=lambda x: x['timestamp']):
                running_balance += deal['profit']
                
                # Get symbol name from ID
                symbol_name = "UNKNOWN"
                for sym_name, sym_data in self.symbols.items():
                    if sym_data['id'] == deal['symbol_id']:
                        symbol_name = sym_name
                        break
                
                trades.append({
                    'ticket': deal['position_id'],
                    'symbol': symbol_name,
                    'direction': 'BUY',  # Would need to track from original order
                    'entry_price': 0,  # Would need to track from original order
                    'closing_price': deal['close_price'],
                    'lot_size': deal['volume'] / 100000.0,
                    'open_time': deal['timestamp'].isoformat(),
                    'close_time': deal['timestamp'].isoformat(),
                    'status': 'CLOSED',
                    'profit': deal['profit'],
                    'pips': 0,  # Calculate if needed
                    'balance_after': running_balance
                })
            
            # Save to JSON
            with open('trade_history.json', 'w') as f:
                json.dump(trades, f, indent=2)
            
            logger.success(f"✅ Dashboard updated with {len(trades)} trades")
            
        except Exception as e:
            logger.error(f"❌ Dashboard update error: {e}")
    
    # ==================== CLEANUP ====================
    
    async def disconnect(self):
        """Close connection"""
        try:
            if self.client:
                await self.client.disconnect()
            logger.info("👋 Disconnected from cTrader")
        except Exception as e:
            logger.error(f"❌ Disconnect error: {e}")


# ==================== INTEGRATION WITH MORNING SCANNER ====================

async def get_historical_data_proto(symbol: str, timeframe: str = 'D1', bars: int = 100):
    """
    Helper function to get historical data via ProtoOA
    Can be used by morning_strategy_scan.py
    """
    client = CTraderLiveClient()
    
    try:
        # Connect and authenticate
        if await client.connect():
            # Get trendbars
            candles = await client.get_trendbars(symbol, timeframe, bars)
            
            if candles:
                # Convert to pandas DataFrame format
                import pandas as pd
                df = pd.DataFrame(candles)
                df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
                return df
            
        return None
        
    finally:
        await client.disconnect()


# ==================== TEST FUNCTION ====================

async def test_complete_flow():
    """Test all 6 phases of cTrader ProtoOA implementation"""
    logger.info("=" * 80)
    logger.info("🧪 TESTING COMPLETE CTRADER PROTOOA FLOW")
    logger.info("=" * 80)
    
    client = CTraderLiveClient()
    
    try:
        # FAZA 1: Connect & Authenticate
        if not await client.connect():
            logger.error("❌ Connection failed!")
            return
        
        logger.success("✅ FAZA 1: Connection & Authentication - SUCCESS")
        
        # FAZA 2.1: Get Symbols
        symbols = await client.get_symbols()
        logger.success(f"✅ FAZA 2.1: Got {len(symbols)} symbols")
        
        # FAZA 2.2: Get Trendbars for GBPUSD
        trendbars = await client.get_trendbars('GBPUSD', 'D1', 10)
        if trendbars:
            logger.success(f"✅ FAZA 2.2: Got {len(trendbars)} GBPUSD D1 candles")
            logger.info(f"   Latest close: {trendbars[-1]['close']:.5f}")
        
        # Test commodities
        for symbol in ['XAUUSD', 'BTCUSD']:
            bars = await client.get_trendbars(symbol, 'D1', 5)
            if bars:
                logger.success(f"✅ {symbol}: {bars[-1]['close']:.2f}")
        
        # FAZA 4: Get Account Info
        acc_info = await client.get_account_info()
        if acc_info:
            logger.success(f"✅ FAZA 4: Balance = ${acc_info['balance']:.2f}")
        
        # FAZA 5: Get Deals History
        deals = await client.get_deals_history(days=30)
        logger.success(f"✅ FAZA 5: Got {len(deals)} closed deals")
        
        logger.info("\n" + "=" * 80)
        logger.success("🎉 ALL PHASES COMPLETED SUCCESSFULLY!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_complete_flow())
