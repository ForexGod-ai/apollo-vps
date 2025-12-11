#!/usr/bin/env python3
"""
cTrader Data Client v2 - Using OFFICIAL OpenApiPy from Spotware
Unlimited market data for all 21 trading pairs via ProtoOA WebSocket
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv
from loguru import logger

# Official OpenApiPy from Spotware
from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import *
from ctrader_open_api.messages.OpenApiMessages_pb2 import *
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import *
from twisted.internet import reactor
import threading
import time

load_dotenv()


class CTraderDataClientV2:
    """
    UNLIMITED market data client using Official OpenApiPy
    Supports all 21 trading pairs with ProtoOA WebSocket
    """
    
    def __init__(self):
        self.client_id = os.getenv('CTRADER_CLIENT_ID')
        self.client_secret = os.getenv('CTRADER_CLIENT_SECRET')
        self.account_id = int(os.getenv('CTRADER_ACCOUNT_ID', '9709773'))
        self.access_token = os.getenv('CTRADER_ACCESS_TOKEN')
        
        # Use DEMO host (IC Markets demo server)
        self.host = EndPoints.PROTOBUF_DEMO_HOST
        self.port = EndPoints.PROTOBUF_PORT
        
        # Client instance
        self.client = None
        self.authenticated = False
        self.symbols_map = {}  # symbol_name -> symbol_id
        
        # Storage for responses
        self.last_trendbars = None
        self.last_error = None
        
        logger.info(f"🚀 Initialized CTraderDataClientV2 (Official OpenApiPy)")
        logger.info(f"📍 Host: {self.host}:{self.port}")
    
    def connect(self):
        """Connect to cTrader ProtoOA server"""
        try:
            logger.info("🔌 Connecting to cTrader ProtoOA...")
            
            # Create client
            self.client = Client(self.host, self.port, TcpProtocol)
            
            # Set callbacks
            self.client.setConnectedCallback(self._on_connected)
            self.client.setDisconnectedCallback(self._on_disconnected)
            self.client.setMessageReceivedCallback(self._on_message_received)
            
            # Start client in separate thread
            reactor_thread = threading.Thread(target=self._run_reactor, daemon=True)
            reactor_thread.start()
            
            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self.authenticated and time.time() - start_time < timeout:
                time.sleep(0.1)
            
            if self.authenticated:
                logger.success("✅ ProtoOA authentication SUCCESS!")
                return True
            else:
                logger.error("❌ ProtoOA authentication timeout")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connect error: {e}")
            return False
    
    def _run_reactor(self):
        """Run Twisted reactor in background thread"""
        try:
            self.client.startService()
            if not reactor.running:
                reactor.run(installSignalHandlers=False)
        except Exception as e:
            logger.debug(f"Reactor error: {e}")
    
    def _on_connected(self, client):
        """Callback when WebSocket connects"""
        logger.info("🔐 WebSocket connected, authenticating app...")
        
        # Send app authentication
        request = ProtoOAApplicationAuthReq()
        request.clientId = self.client_id
        request.clientSecret = self.client_secret
        
        deferred = client.send(request)
        deferred.addErrback(self._on_error)
    
    def _on_disconnected(self, client, reason):
        """Callback when WebSocket disconnects"""
        logger.debug(f"Disconnected: {reason}")
    
    def _on_message_received(self, client, message):
        """Callback for all received messages"""
        try:
            # Application auth response
            if message.payloadType == ProtoOAApplicationAuthRes().payloadType:
                logger.success("✅ App authenticated, authenticating account...")
                self._authenticate_account()
            
            # Account auth response
            elif message.payloadType == ProtoOAAccountAuthRes().payloadType:
                logger.success(f"✅ Account {self.account_id} authenticated!")
                self.authenticated = True
                # Request symbols list
                self._request_symbols()
            
            # Symbols list response
            elif message.payloadType == ProtoOASymbolsListRes().payloadType:
                response = Protobuf.extract(message)
                self.symbols_map = {symbol.symbolName: symbol.symbolId for symbol in response.symbol}
                logger.success(f"✅ Got {len(self.symbols_map)} symbols")
            
            # Trendbars response
            elif message.payloadType == ProtoOAGetTrendbarsRes().payloadType:
                response = Protobuf.extract(message)
                self.last_trendbars = response
                logger.debug(f"✅ Got {len(response.trendbar)} trendbars")
            
            # Error message
            elif message.payloadType == ProtoOAErrorRes().payloadType:
                error = Protobuf.extract(message)
                self.last_error = error.errorCode
                logger.error(f"❌ ProtoOA Error: {error.errorCode}")
                
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    def _on_error(self, failure):
        """Error callback"""
        logger.error(f"Request error: {failure}")
        self.last_error = str(failure)
    
    def _authenticate_account(self):
        """Authenticate trading account"""
        request = ProtoOAAccountAuthReq()
        request.ctidTraderAccountId = self.account_id
        request.accessToken = self.access_token
        
        deferred = self.client.send(request)
        deferred.addErrback(self._on_error)
    
    def _request_symbols(self):
        """Request available symbols"""
        request = ProtoOASymbolsListReq()
        request.ctidTraderAccountId = self.account_id
        request.includeArchivedSymbols = False
        
        deferred = self.client.send(request)
        deferred.addErrback(self._on_error)
    
    def get_historical_data(self, symbol: str, timeframe: str = 'D1', bars: int = 100) -> Optional[pd.DataFrame]:
        """
        Get LIVE OHLC data via ProtoOA WebSocket
        
        Args:
            symbol: GBPUSD, EURUSD, XAUUSD, BTCUSD, etc.
            timeframe: D1, H4, H1, M15, M5, M1
            bars: Number of candles (weeks of data)
            
        Returns:
            DataFrame with time, open, high, low, close, volume
        """
        try:
            if not self.authenticated:
                if not self.connect():
                    logger.error("❌ Not authenticated to ProtoOA")
                    return None
            
            # Wait for symbols list
            timeout = 5
            start_time = time.time()
            while not self.symbols_map and time.time() - start_time < timeout:
                time.sleep(0.1)
            
            if symbol not in self.symbols_map:
                logger.error(f"❌ Symbol {symbol} not found in cTrader")
                return None
            
            symbol_id = self.symbols_map[symbol]
            
            # Timeframe mapping
            period_map = {
                'M1': ProtoOATrendbarPeriod.M1,
                'M5': ProtoOATrendbarPeriod.M5,
                'M15': ProtoOATrendbarPeriod.M15,
                'H1': ProtoOATrendbarPeriod.H1,
                'H4': ProtoOATrendbarPeriod.H4,
                'D1': ProtoOATrendbarPeriod.D1,
                'D': ProtoOATrendbarPeriod.D1
            }
            
            period = period_map.get(timeframe, ProtoOATrendbarPeriod.D1)
            
            # Calculate time range (weeks back based on bars needed)
            weeks = max(1, bars // 5)  # Daily: ~5 bars per week
            from_timestamp = int((datetime.utcnow() - timedelta(weeks=weeks)).timestamp() * 1000)
            to_timestamp = int(datetime.utcnow().timestamp() * 1000)
            
            # Send trendbars request
            request = ProtoOAGetTrendbarsReq()
            request.ctidTraderAccountId = self.account_id
            request.symbolId = symbol_id
            request.period = period
            request.fromTimestamp = from_timestamp
            request.toTimestamp = to_timestamp
            
            self.last_trendbars = None
            self.last_error = None
            
            deferred = self.client.send(request)
            deferred.addErrback(self._on_error)
            
            # Wait for response
            timeout = 10
            start_time = time.time()
            while self.last_trendbars is None and self.last_error is None and time.time() - start_time < timeout:
                time.sleep(0.1)
            
            if self.last_error:
                logger.error(f"❌ Trendbars error: {self.last_error}")
                return None
            
            if self.last_trendbars is None:
                logger.error(f"❌ Trendbars timeout for {symbol}")
                return None
            
            # Parse to DataFrame
            df = self._parse_trendbars(self.last_trendbars)
            
            if df is not None and not df.empty:
                # Return only requested number of bars
                df = df.tail(bars).reset_index(drop=True)
                logger.success(f"✅ Got {len(df)} LIVE candles for {symbol}")
                return df
            else:
                logger.error(f"❌ No data for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching {symbol}: {e}")
            return None
    
    def _parse_trendbars(self, response) -> Optional[pd.DataFrame]:
        """Parse ProtoOA trendbars to DataFrame"""
        try:
            df_data = []
            for bar in response.trendbar:
                # Timestamps are in Unix milliseconds
                dt = datetime.fromtimestamp(bar.utcTimestampInMinutes * 60)
                
                df_data.append({
                    'time': dt,
                    'open': bar.open / 100000,  # Convert from ticks
                    'high': bar.high / 100000,
                    'low': bar.low / 100000,
                    'close': bar.close / 100000,
                    'volume': bar.volume if hasattr(bar, 'volume') else 0
                })
            
            if not df_data:
                return None
            
            df = pd.DataFrame(df_data)
            return df.sort_values('time').reset_index(drop=True)
            
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return None
    
    def disconnect(self):
        """Disconnect from ProtoOA"""
        try:
            if self.client and reactor.running:
                reactor.callFromThread(reactor.stop)
            logger.info("🔌 Disconnected from ProtoOA")
        except Exception as e:
            logger.debug(f"Disconnect error: {e}")


# Global client instance (reuse connection)
_global_client = None

def get_ctrader_client_v2() -> CTraderDataClientV2:
    """Get or create global ProtoOA client"""
    global _global_client
    if _global_client is None:
        _global_client = CTraderDataClientV2()
    return _global_client


if __name__ == "__main__":
    # Test with all 21 pairs
    logger.info("🧪 Testing CTraderDataClientV2 with 21 pairs...")
    
    test_pairs = [
        'BTCUSD', 'XAUUSD', 'XAGUSD', 'USOIL',
        'GBPNZD', 'GBPUSD', 'GBPJPY', 'USDCAD',
        'NZDCAD', 'EURUSD', 'EURJPY', 'EURCAD',
        'AUDCAD', 'USDCHF', 'USDJPY', 'GBPCHF',
        'AUDNZD', 'AUDUSD', 'NZDUSD', 'GBPCAD', 'EURNZD'
    ]
    
    client = get_ctrader_client_v2()
    
    successful = []
    failed = []
    
    for i, symbol in enumerate(test_pairs, 1):
        logger.info(f"\n📊 [{i}/21] Testing {symbol}...")
        df = client.get_historical_data(symbol, 'D1', 100)
        
        if df is not None and not df.empty:
            logger.success(f"✅ {symbol}: {len(df)} candles")
            successful.append(symbol)
        else:
            logger.error(f"❌ {symbol}: FAILED")
            failed.append(symbol)
        
        time.sleep(0.5)  # Small delay between requests
    
    logger.info(f"\n{'='*60}")
    logger.success(f"✅ SUCCESS: {len(successful)}/21 pairs")
    if failed:
        logger.error(f"❌ FAILED: {len(failed)}/21 pairs: {failed}")
    
    client.disconnect()
