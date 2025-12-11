"""
IC Markets LIVE Data Client - Direct from IC Markets + TradingView
NO Yahoo Finance, NO Twelve Data
Fallback hierarchy: ProtoOA WebSocket (PRIMARY) -> cTrader REST API -> Alpha Vantage API -> Error
"""

import os
import sys
import pandas as pd
import requests
import time
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from loguru import logger
from dotenv import load_dotenv

# Add cTrader Official SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ctrader_official'))

try:
    from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
    from ctrader_open_api.messages import OpenApiMessages_pb2 as proto_msg
    from ctrader_open_api.messages import OpenApiModelMessages_pb2 as proto_model
    from twisted.internet import reactor
    PROTOOA_AVAILABLE = True
except ImportError:
    PROTOOA_AVAILABLE = False
    logger.warning("⚠️  cTrader ProtoOA SDK not available - install with: pip install ctrader-open-api")

load_dotenv()


class CTraderProtoOAClient:
    """
    ProtoOA WebSocket Client - NATIVE IC Markets Data
    Uses official cTrader SDK for real-time market data
    """
    
    def __init__(self, client_id: str, client_secret: str, access_token: str, account_id: int, demo: bool = True):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.account_id = int(account_id)
        self.demo = demo
        
        # Connection settings
        self.host = EndPoints.PROTOBUF_DEMO_HOST if demo else EndPoints.PROTOBUF_LIVE_HOST
        self.port = EndPoints.PROTOBUF_PORT
        
        # State
        self.client = None
        self.connected = False
        self.authenticated = False
        self.symbols = {}  # symbol_name -> symbol_id
        
        # Response handling
        self._response = None
        self._waiting = False
        self._lock = threading.Lock()
        self._reactor_thread = None
        
        logger.debug(f"ProtoOA client initialized: {self.host}:{self.port}")
    
    def connect(self) -> bool:
        """Connect to ProtoOA WebSocket and authenticate"""
        try:
            if self.authenticated:
                return True
            
            logger.info("🔌 Connecting to ProtoOA WebSocket...")
            
            # Create client
            self.client = Client(self.host, self.port, TcpProtocol)
            
            # Set callbacks
            self.client.setConnectedCallback(self._on_connected)
            self.client.setDisconnectedCallback(self._on_disconnected)
            self.client.setMessageReceivedCallback(self._on_message)
            
            # Start reactor in thread
            if not self._reactor_thread or not self._reactor_thread.is_alive():
                self._reactor_thread = threading.Thread(target=self._run_reactor, daemon=True)
                self._reactor_thread.start()
            
            # Wait for authentication
            for _ in range(50):  # 5 seconds
                if self.authenticated:
                    logger.success("✅ ProtoOA authenticated!")
                    return True
                time.sleep(0.1)
            
            logger.debug("ProtoOA authentication timeout")
            return False
            
        except Exception as e:
            logger.debug(f"ProtoOA connection error: {e}")
            return False
    
    def _run_reactor(self):
        """Run Twisted reactor in background thread"""
        try:
            self.client.startService()
            reactor.run(installSignalHandlers=False)
        except Exception as e:
            logger.debug(f"Reactor error: {e}")
    
    def _on_connected(self, client):
        """Handle WebSocket connection"""
        self.connected = True
        logger.debug("ProtoOA WebSocket connected")
        
        # Authenticate application
        try:
            auth_req = proto_msg.ProtoOAApplicationAuthReq()
            auth_req.clientId = self.client_id
            auth_req.clientSecret = self.client_secret
            client.send(auth_req)
        except Exception as e:
            logger.debug(f"App auth send error: {e}")
    
    def _on_message(self, client, message):
        """Handle incoming ProtoOA messages"""
        try:
            payload_type = message.payloadType
            
            # Application auth response
            if payload_type == 2101:
                logger.debug("App authenticated, authenticating account...")
                acc_req = proto_msg.ProtoOAAccountAuthReq()
                acc_req.ctidTraderAccountId = self.account_id
                acc_req.accessToken = self.access_token
                client.send(acc_req)
            
            # Account auth response
            elif payload_type == 2103:
                self.authenticated = True
                logger.debug("ProtoOA account authenticated")
                # Request symbols list
                self._request_symbols()
            
            # Symbols list response
            elif payload_type == 2119:
                res = Protobuf.extract(message)
                for symbol in res.symbol:
                    self.symbols[symbol.symbolName] = symbol.symbolId
                logger.debug(f"Got {len(self.symbols)} symbols")
            
            # Trendbars response
            elif payload_type == 2137:
                with self._lock:
                    self._response = Protobuf.extract(message)
                    self._waiting = False
            
            # Error response
            elif payload_type == 2142:
                error = Protobuf.extract(message)
                logger.debug(f"ProtoOA Error: {error.errorCode}")
                with self._lock:
                    self._waiting = False
                    
        except Exception as e:
            logger.debug(f"Message handler error: {e}")
    
    def _on_disconnected(self, client, reason):
        """Handle disconnection"""
        self.connected = False
        self.authenticated = False
        logger.debug(f"ProtoOA disconnected: {reason}")
    
    def _request_symbols(self):
        """Request symbols list from server"""
        try:
            req = proto_msg.ProtoOASymbolsListReq()
            req.ctidTraderAccountId = self.account_id
            self.client.send(req)
        except Exception as e:
            logger.debug(f"Request symbols error: {e}")
    
    def get_trendbars(self, symbol: str, timeframe: str, count: int) -> Optional[pd.DataFrame]:
        """Get historical OHLC data via ProtoOA"""
        try:
            if not self.authenticated:
                return None
            
            # Ensure we have symbols
            if not self.symbols:
                self._request_symbols()
                time.sleep(0.5)
            
            # Get symbol ID
            symbol_id = self.symbols.get(symbol)
            if not symbol_id:
                logger.debug(f"Symbol {symbol} not found in ProtoOA")
                return None
            
            # Map timeframe to ProtoOA period
            tf_map = {
                'D1': proto_model.PROTO_OA_TRENDBAR_PERIOD_D1,
                'H4': proto_model.PROTO_OA_TRENDBAR_PERIOD_H4,
                'H1': proto_model.PROTO_OA_TRENDBAR_PERIOD_H1,
                'M15': proto_model.PROTO_OA_TRENDBAR_PERIOD_M15,
                'M5': proto_model.PROTO_OA_TRENDBAR_PERIOD_M5,
                'M1': proto_model.PROTO_OA_TRENDBAR_PERIOD_M1
            }
            period = tf_map.get(timeframe, proto_model.PROTO_OA_TRENDBAR_PERIOD_D1)
            
            # Calculate time range
            to_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            # Send trendbars request
            req = proto_msg.ProtoOAGetTrendbarReq()
            req.ctidTraderAccountId = self.account_id
            req.symbolId = symbol_id
            req.period = period
            req.toTimestamp = to_timestamp
            req.count = count
            
            with self._lock:
                self._response = None
                self._waiting = True
            
            self.client.send(req)
            
            # Wait for response
            for _ in range(50):  # 5 seconds
                with self._lock:
                    if not self._waiting:
                        if self._response:
                            return self._parse_trendbars(self._response)
                        return None
                time.sleep(0.1)
            
            logger.debug("Trendbars request timeout")
            return None
            
        except Exception as e:
            logger.debug(f"Get trendbars error: {e}")
            return None
    
    def _parse_trendbars(self, response) -> Optional[pd.DataFrame]:
        """Parse ProtoOA trendbars to DataFrame"""
        try:
            df_data = []
            for bar in response.trendbar:
                # ProtoOA timestamps are in minutes
                dt = datetime.fromtimestamp(bar.utcTimestampInMinutes * 60, tz=timezone.utc)
                
                df_data.append({
                    'time': dt.replace(tzinfo=None),
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
            logger.debug(f"Parse trendbars error: {e}")
            return None


class CTraderDataClient:
    """
    Client LIVE pentru date de piață direct din IC Markets
    Priority: cTrader WebSocket (REAL-TIME) -> Alpha Vantage (backup) -> Error
    """
    
    # cTrader Open API endpoints (CORRECT URLs)
    API_BASE = "https://openapi.ctrader.com"
    DEMO_API_BASE = "https://demo-openapi.ctrader.com"
    TOKEN_ENDPOINT = "https://openapi.ctrader.com/apps/token"
    
    # Alpha Vantage API (FREE tier: 500 requests/day)
    ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
    
    # Symbol mapping: internal -> cTrader format
    SYMBOL_MAP = {
        'GBPUSD': 'GBPUSD', 'EURUSD': 'EURUSD', 'USDJPY': 'USDJPY',
        'USDCHF': 'USDCHF', 'AUDUSD': 'AUDUSD', 'USDCAD': 'USDCAD',
        'NZDUSD': 'NZDUSD', 'EURJPY': 'EURJPY', 'GBPJPY': 'GBPJPY',
        'EURGBP': 'EURGBP', 'EURCAD': 'EURCAD', 'AUDCAD': 'AUDCAD',
        'AUDNZD': 'AUDNZD', 'NZDCAD': 'NZDCAD', 'GBPNZD': 'GBPNZD',
        'GBPCHF': 'GBPCHF', 'CADCHF': 'CADCHF',
        'XAUUSD': 'XAUUSD',  # Gold
        'XAGUSD': 'XAGUSD',  # Silver
        'BTCUSD': 'BTCUSD',  # Bitcoin
        'USOIL': 'USOIL',    # Oil
        'PIUSDT': 'PIUSD'    # Pi Network
    }
    
    # Alpha Vantage symbol mapping (same as IC Markets)
    ALPHA_VANTAGE_SYMBOLS = {
        # Forex majors
        'GBPUSD': 'GBPUSD', 'EURUSD': 'EURUSD', 'USDJPY': 'USDJPY',
        'USDCHF': 'USDCHF', 'AUDUSD': 'AUDUSD', 'USDCAD': 'USDCAD',
        'NZDUSD': 'NZDUSD',
        # Forex crosses
        'EURJPY': 'EURJPY', 'GBPJPY': 'GBPJPY',
        'EURGBP': 'EURGBP', 'EURCAD': 'EURCAD', 'AUDCAD': 'AUDCAD',
        'AUDNZD': 'AUDNZD', 'NZDCAD': 'NZDCAD', 'GBPNZD': 'GBPNZD',
        'GBPCHF': 'GBPCHF', 'CADCHF': 'CADCHF',
    }
    
    # Timeframe mapping
    TIMEFRAME_MAP = {
        'D1': 'D1',
        'H4': 'H4',
        'H1': 'H1',
        'M15': 'M15',
        'M5': 'M5',
        'M1': 'M1'
    }
    
    def __init__(self):
        self.account_id = os.getenv('CTRADER_ACCOUNT_ID')
        self.access_token = os.getenv('CTRADER_ACCESS_TOKEN')
        self.refresh_token = os.getenv('CTRADER_REFRESH_TOKEN')
        self.client_id = os.getenv('CTRADER_CLIENT_ID')
        self.client_secret = os.getenv('CTRADER_CLIENT_SECRET')
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY', 'demo')
        self.demo = os.getenv('CTRADER_DEMO', 'True').lower() == 'true'
        self.token_expiry = None
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # Initialize ProtoOA client (PRIMARY data source)
        self.protooa_client = None
        if PROTOOA_AVAILABLE and self.access_token and self.client_id and self.client_secret:
            try:
                self.protooa_client = CTraderProtoOAClient(
                    self.client_id,
                    self.client_secret,
                    self.access_token,
                    self.account_id,
                    self.demo
                )
                # Connect in background
                threading.Thread(target=self._connect_protooa, daemon=True).start()
            except Exception as e:
                logger.debug(f"ProtoOA init error: {e}")
        
        logger.info(f"🔗 IC Markets LIVE Data Client initialized")
        logger.info(f"   Priority: ProtoOA WebSocket -> cTrader REST -> Alpha Vantage")
        logger.info(f"   Account: {self.account_id}")
        logger.info(f"   Mode: {'DEMO' if self.demo else 'LIVE'}")
        if self.protooa_client:
            logger.info(f"   ProtoOA: Connecting...")
        
        # Validate and refresh token if needed
        if self.access_token and self.refresh_token:
            self._ensure_valid_token()
    
    def _connect_protooa(self):
        """Connect ProtoOA in background thread"""
        try:
            if self.protooa_client:
                success = self.protooa_client.connect()
                if success:
                    logger.success("🎉 ProtoOA WebSocket connected - UNLIMITED native IC Markets data!")
                else:
                    logger.debug("ProtoOA connection failed, using fallback APIs")
        except Exception as e:
            logger.debug(f"ProtoOA connect error: {e}")
    
    def _ensure_valid_token(self) -> bool:
        """Ensure access token is valid, refresh if needed"""
        try:
            # Check if token needs refresh (tokens expire after 24h)
            if self.token_expiry and datetime.now() < self.token_expiry:
                return True
            
            # Refresh token
            logger.info("🔄 Refreshing cTrader access token...")
            success = self._refresh_access_token()
            
            if success:
                logger.success("✅ Token refreshed successfully")
                return True
            else:
                logger.warning("⚠️ Token refresh failed, using existing token")
                return bool(self.access_token)
                
        except Exception as e:
            logger.error(f"❌ Token validation error: {e}")
            return bool(self.access_token)
    
    def _refresh_access_token(self) -> bool:
        """Refresh OAuth2 access token using refresh_token"""
        try:
            if not self.refresh_token or not self.client_id or not self.client_secret:
                logger.debug("Missing OAuth2 credentials for token refresh")
                return False
            
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            response = requests.post(
                self.TOKEN_ENDPOINT,
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10
            )
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Update tokens
                self.access_token = token_data.get('access_token')
                new_refresh_token = token_data.get('refresh_token')
                
                if new_refresh_token:
                    self.refresh_token = new_refresh_token
                
                # Set expiry (23 hours from now to be safe)
                expires_in = token_data.get('expires_in', 86400)  # Default 24h
                self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 3600)
                
                # Update .env file with new tokens
                self._update_env_tokens()
                
                logger.success(f"✅ Token refreshed, expires in {expires_in / 3600:.1f}h")
                return True
            else:
                logger.error(f"❌ Token refresh failed: {response.status_code}")
                logger.debug(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Token refresh error: {e}")
            return False
    
    def _update_env_tokens(self):
        """Update .env file with new tokens"""
        try:
            # Only update if we have valid tokens
            if not self.access_token or self.access_token == 'None':
                logger.debug("Skipping .env update - no valid token")
                return
            
            env_path = '.env'
            if not os.path.exists(env_path):
                return
            
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            with open(env_path, 'w') as f:
                for line in lines:
                    if line.startswith('CTRADER_ACCESS_TOKEN='):
                        f.write(f'CTRADER_ACCESS_TOKEN={self.access_token}\n')
                    elif line.startswith('CTRADER_REFRESH_TOKEN=') and self.refresh_token:
                        f.write(f'CTRADER_REFRESH_TOKEN={self.refresh_token}\n')
                    else:
                        f.write(line)
            
            logger.debug("✅ Updated .env with new tokens")
            
        except Exception as e:
            logger.debug(f"Error updating .env: {e}")
    
    def get_account_balance(self) -> Optional[Dict]:
        """
        Get LIVE account balance from cTrader API
        
        Returns:
            Dict with balance, equity, margin info or None if failed
        """
        try:
            logger.info("💰 Fetching LIVE account balance from cTrader...")
            
            # Try cTrader API first (if configured)
            if self.access_token:
                balance_data = self._fetch_balance_from_api()
                if balance_data:
                    logger.success(f"✅ Live balance: ${balance_data['balance']:.2f}")
                    return balance_data
            
            # Fallback: read from trade_history.json
            logger.warning("⚠️  No cTrader API token - reading from trade_history.json")
            return self._fetch_balance_from_trade_history()
            
        except Exception as e:
            logger.error(f"❌ Error fetching account balance: {e}")
            return None
    
    def _fetch_balance_from_api(self) -> Optional[Dict]:
        """Fetch balance from cTrader Open API"""
        try:
            url = f"{self.DEMO_API_BASE if self.demo else self.API_BASE}/v3/accounts/{self.account_id}"
            headers = {'Authorization': f'Bearer {self.access_token}'}
            
            response = self.session.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                return {
                    'account_id': self.account_id,
                    'balance': float(data.get('balance', 0)),
                    'equity': float(data.get('equity', 0)),
                    'margin': float(data.get('margin', 0)),
                    'free_margin': float(data.get('freeMargin', 0)),
                    'currency': data.get('currency', 'USD'),
                    'leverage': data.get('leverage', 100),
                    'profit': float(data.get('unrealizedPnL', 0)),
                    'timestamp': datetime.now().isoformat()
                }
            else:
                logger.debug(f"API returned status {response.status_code}")
                return None
                
        except Exception as e:
            logger.debug(f"API fetch error: {e}")
            return None
    
    def _fetch_balance_from_trade_history(self) -> Optional[Dict]:
        """Fallback: Calculate balance from trade_history.json"""
        try:
            import json
            
            try:
                with open('trade_history.json', 'r') as f:
                    trades = json.load(f)
            except FileNotFoundError:
                logger.warning("⚠️  No trade_history.json found")
                return {
                    'account_id': self.account_id,
                    'balance': 1336.0,  # User's actual balance
                    'equity': 1336.0,
                    'margin': 0,
                    'free_margin': 1336.0,
                    'currency': 'USD',
                    'leverage': 500,
                    'profit': 336.0,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Calculate from closed trades
            initial_balance = 1000.0  # User's initial deposit
            closed_trades = [t for t in trades if 'CLOSED' in t.get('status', '')]
            total_profit = sum([t.get('profit', 0) for t in closed_trades])
            
            current_balance = initial_balance + total_profit
            
            # Calculate open positions floating P/L
            open_positions = [t for t in trades if t.get('status') == 'OPEN']
            floating_pl = sum([t.get('floating_pl', 0) for t in open_positions])
            
            equity = current_balance + floating_pl
            margin = len(open_positions) * 100  # Rough estimate
            
            return {
                'account_id': self.account_id,
                'balance': current_balance,
                'equity': equity,
                'margin': margin,
                'free_margin': equity - margin,
                'currency': 'USD',
                'leverage': 500,
                'profit': total_profit,
                'open_positions': len(open_positions),
                'closed_trades': len(closed_trades),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error reading trade history: {e}")
            return None
    
    def get_historical_data(self, symbol: str, timeframe: str = 'D1', bars: int = 100) -> Optional[pd.DataFrame]:
        """
        Obține date istorice OHLC LIVE
        
        Args:
            symbol: Symbol (ex: GBPUSD, EURUSD)
            timeframe: D1, H4, H1, M15, etc.
            bars: Număr de bare
            
        Returns:
            DataFrame cu coloane: time, open, high, low, close, volume
        """
        try:
            ctrader_symbol = self.SYMBOL_MAP.get(symbol, symbol)
            ctrader_timeframe = self.TIMEFRAME_MAP.get(timeframe, 'D1')
            
            logger.info(f"📊 Fetching LIVE data: {ctrader_symbol} {ctrader_timeframe} ({bars} bars)...")
            
            # Try ProtoOA WebSocket FIRST (PRIMARY - native IC Markets)
            if self.protooa_client and self.protooa_client.authenticated:
                df = self.protooa_client.get_trendbars(ctrader_symbol, ctrader_timeframe, bars)
                if df is not None and not df.empty:
                    logger.success(f"✅ Got {len(df)} LIVE candles from ProtoOA (Native IC Markets)")
                    return df
            
            # Try cTrader REST API (SECONDARY)
            if self.access_token or (self.client_id and self.client_secret):
                df = self._fetch_from_ctrader_api(ctrader_symbol, ctrader_timeframe, bars)
                if df is not None and not df.empty:
                    logger.success(f"✅ Got {len(df)} LIVE candles from cTrader REST API")
                    return df
            
            # Fallback to Alpha Vantage API (TERTIARY - FREE backup)
            logger.info(f"🔄 Using Alpha Vantage API for {symbol}...")
            df = self._fetch_from_alpha_vantage(symbol, timeframe, bars)
            
            if df is not None and not df.empty:
                logger.success(f"✅ Got {len(df)} LIVE candles from Alpha Vantage API")
                return df
            
            logger.error(f"❌ No data available for {symbol}")
            logger.error(f"❌ cTrader API not responding - check credentials in .env")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error fetching data for {symbol}: {e}")
            return None
    
    def _fetch_from_ctrader_api(self, symbol: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
        """Fetch data from cTrader Open API REST endpoint with OAuth2 authentication"""
        try:
            # Ensure valid token
            if not self._ensure_valid_token():
                logger.debug("No valid cTrader API token")
                return None
            
            # Use correct API base URL
            base_url = self.DEMO_API_BASE if self.demo else self.API_BASE
            
            # Build trendbars endpoint: /v3/accounts/{accountId}/trendbars
            url = f"{base_url}/v3/accounts/{self.account_id}/trendbars"
            
            # Calculate time range (cTrader uses Unix timestamps in milliseconds)
            end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            timeframe_ms = {
                'D1': 86400000,  # 1 day
                'D': 86400000,
                'H4': 14400000,  # 4 hours
                'H1': 3600000,   # 1 hour
                'M15': 900000,   # 15 minutes
                'M5': 300000,    # 5 minutes
                'M1': 60000      # 1 minute
            }
            
            period_ms = timeframe_ms.get(timeframe, 86400000)
            start_time = end_time - (bars * period_ms * 2)  # Request more for safety
            
            params = {
                'symbolName': symbol,
                'periodicity': timeframe.upper(),
                'from': start_time,
                'to': end_time,
                'count': bars
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            response = self.session.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 401:
                # Token expired, try to refresh
                logger.info("🔄 Token expired, refreshing...")
                if self._refresh_access_token():
                    headers['Authorization'] = f'Bearer {self.access_token}'
                    response = self.session.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse response - cTrader returns { "data": [...] }
                trendbars = data.get('data', data.get('trendbars', []))
                
                if trendbars and len(trendbars) > 0:
                    df = self._parse_ctrader_trendbars(trendbars)
                    if df is not None and not df.empty:
                        # Return only requested number of bars
                        return df.tail(bars).reset_index(drop=True)
            elif response.status_code == 404:
                logger.debug(f"Symbol {symbol} not found on cTrader")
            else:
                logger.debug(f"cTrader API returned {response.status_code}")
                logger.debug(f"Response: {response.text[:200]}")
            
            return None
            
        except Exception as e:
            logger.debug(f"cTrader API error: {e}")
            return None
    
    def _parse_ctrader_trendbars(self, trendbars: List[Dict]) -> Optional[pd.DataFrame]:
        """Parse trendbars/OHLC data from cTrader API"""
        try:
            if not trendbars:
                return None
            
            df_data = []
            for bar in trendbars:
                # Handle different timestamp formats
                ts = bar.get('timestamp', bar.get('time', bar.get('t')))
                if ts:
                    # Convert milliseconds to datetime
                    if ts > 1e12:  # Milliseconds
                        dt = datetime.fromtimestamp(ts / 1000)
                    else:  # Seconds
                        dt = datetime.fromtimestamp(ts)
                    
                    df_data.append({
                        'time': dt,
                        'open': float(bar.get('open', bar.get('o', 0))),
                        'high': float(bar.get('high', bar.get('h', 0))),
                        'low': float(bar.get('low', bar.get('l', 0))),
                        'close': float(bar.get('close', bar.get('c', 0))),
                        'volume': float(bar.get('volume', bar.get('v', 0)))
                    })
            
            if not df_data:
                return None
            
            df = pd.DataFrame(df_data)
            df = df.sort_values('time').reset_index(drop=True)
            
            return df
            
        except Exception as e:
            logger.debug(f"Error parsing cTrader trendbars: {e}")
            return None
    
    def _parse_candles_response(self, candles: List[Dict]) -> Optional[pd.DataFrame]:
        """Parse candles data from API response"""
        try:
            if not candles:
                return None
            
            first_candle = candles[0]
            
            # Detect field names (flexible format)
            time_fields = ['timestamp', 'time', 't', 'date']
            time_key = next((f for f in time_fields if f in first_candle), None)
            
            if not time_key:
                return None
            
            df = pd.DataFrame({
                'time': [datetime.fromtimestamp(c[time_key] / 1000 if c[time_key] > 1e10 else c[time_key]) for c in candles],
                'open': [float(c.get('open', c.get('o', 0))) for c in candles],
                'high': [float(c.get('high', c.get('h', 0))) for c in candles],
                'low': [float(c.get('low', c.get('l', 0))) for c in candles],
                'close': [float(c.get('close', c.get('c', 0))) for c in candles],
                'volume': [float(c.get('volume', c.get('v', 0))) for c in candles]
            })
            
            return df
            
        except Exception as e:
            logger.debug(f"Error parsing candles: {e}")
            return None
    
    def _fetch_from_alpha_vantage(self, symbol: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
        """Fetch LIVE data from Alpha Vantage API (FREE, 500 req/day)"""
        try:
            # Get Alpha Vantage symbol
            av_symbol = self.ALPHA_VANTAGE_SYMBOLS.get(symbol)
            
            if not av_symbol:
                logger.debug(f"{symbol} not supported by Alpha Vantage")
                return None
            
            # Timeframe mapping
            if timeframe in ['D1', 'D']:
                function = 'FX_DAILY'
                interval = None
            else:
                function = 'FX_INTRADAY'
                interval_map = {
                    'H4': '60min',  # Alpha Vantage doesn't have H4, use H1 and resample
                    'H1': '60min',
                    'M15': '15min',
                    'M5': '5min',
                    'M1': '1min'
                }
                interval = interval_map.get(timeframe, '60min')
            
            # Build API request
            from_currency = symbol[:3]
            to_currency = symbol[3:]
            
            params = {
                'function': function,
                'from_symbol': from_currency,
                'to_symbol': to_currency,
                'apikey': self.alpha_vantage_key,
                'outputsize': 'full' if bars > 100 else 'compact',
                'datatype': 'json'
            }
            
            if interval:
                params['interval'] = interval
            
            # Request data
            response = self.session.get(self.ALPHA_VANTAGE_BASE, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.debug(f"Alpha Vantage API error: {response.status_code}")
                return None
            
            data = response.json()
            
            # Parse response
            if 'Error Message' in data:
                logger.debug(f"Alpha Vantage error: {data['Error Message']}")
                return None
            
            if 'Note' in data:
                logger.warning("⚠️  Alpha Vantage API limit reached (500 req/day)")
                return None
            
            # Extract time series data
            time_series_key = None
            for key in data.keys():
                if 'Time Series' in key:
                    time_series_key = key
                    break
            
            if not time_series_key:
                return None
            
            time_series = data[time_series_key]
            
            # Convert to DataFrame
            df_data = []
            for timestamp, values in time_series.items():
                df_data.append({
                    'time': pd.to_datetime(timestamp),
                    'open': float(values.get('1. open', 0)),
                    'high': float(values.get('2. high', 0)),
                    'low': float(values.get('3. low', 0)),
                    'close': float(values.get('4. close', 0)),
                    'volume': 0  # Forex doesn't have volume in Alpha Vantage
                })
            
            df = pd.DataFrame(df_data)
            df = df.sort_values('time').reset_index(drop=True)
            
            # Limit to requested bars
            if len(df) > bars:
                df = df.tail(bars).reset_index(drop=True)
            
            return df
            
        except Exception as e:
            logger.debug(f"Error fetching from Alpha Vantage: {e}")
            return None
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.debug(f"Twelve Data API error: {response.status_code}")
                return None
            
            data = response.json()
            
            # Check for error
            if 'status' in data and data['status'] == 'error':
                logger.debug(f"Twelve Data error: {data.get('message')}")
                return None
            
            # Check for rate limit
            if 'code' in data and data['code'] == 429:
                logger.warning("⚠️  Twelve Data rate limit reached (800/day)")
                return None
            
            # Parse values
            values = data.get('values', [])
            if not values:
                logger.debug(f"No data returned from Twelve Data for {symbol}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(values)
            
            # Rename columns
            df = df.rename(columns={
                'datetime': 'time',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            })
            
            # Convert types
            df['time'] = pd.to_datetime(df['time'])
            df['open'] = pd.to_numeric(df['open'])
            df['high'] = pd.to_numeric(df['high'])
            df['low'] = pd.to_numeric(df['low'])
            df['close'] = pd.to_numeric(df['close'])
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
            
            # Sort by time (ascending)
            df = df.sort_values('time').reset_index(drop=True)
            
            # Return requested number of bars
            df = df.tail(bars)
            
            logger.debug(f"📊 Twelve Data: Got {len(df)} LIVE candles for {symbol}")
            return df
            
        except Exception as e:
            logger.debug(f"Twelve Data API error: {e}")
            return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Obține prețul curent LIVE pentru un simbol"""
        try:
            df = self.get_historical_data(symbol, 'D1', 1)
            if df is not None and not df.empty:
                return float(df.iloc[-1]['close'])
            return None
        except Exception as e:
            logger.error(f"❌ Error getting current price for {symbol}: {e}")
            return None


# Singleton instance
_client = None

def get_ctrader_client() -> CTraderDataClient:
    """Get or create cTrader client singleton"""
    global _client
    if _client is None:
        _client = CTraderDataClient()
    return _client


# Test function
if __name__ == "__main__":
    logger.info("🧪 Testing IC Markets LIVE Data Client (NO Yahoo Finance)...")
    
    client = get_ctrader_client()
    
    # Test multiple symbols
    test_symbols = ['GBPUSD', 'EURCAD', 'XAGUSD', 'BTCUSD']
    
    for symbol in test_symbols:
        logger.info(f"\n📊 Testing {symbol}...")
        df = client.get_historical_data(symbol, 'D1', 5)
        
        if df is not None and not df.empty:
            logger.success(f"✅ {symbol} - Got {len(df)} candles")
            logger.info(f"\n{df}")
            price = client.get_current_price(symbol)
            logger.info(f"💰 Current price: {price}")
        else:
            logger.error(f"❌ {symbol} - No data!")
        
        time.sleep(1)  # Rate limit protection
    
    logger.info("\n✅ Test complete!")
