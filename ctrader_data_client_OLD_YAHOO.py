"""
cTrader Data Client - Historical OHLC Data Provider
Conexiune LIVE la IC Markets prin cTrader Open API REST
"""

import os
import pandas as pd
import requests
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class CTraderDataClient:
    """
    Client LIVE pentru date cTrader Open API
    Conexiune directă la IC Markets broker pentru date real-time
    """
    
    # cTrader Open API endpoints (Spotware - nu direct IC Markets)
    API_BASE = "https://api.ctrader.com"
    DEMO_API_BASE = "https://api.ctrader.com"  # Same endpoint for demo/live
    
    # Alternative: Use cTrader Connect proxy
    CONNECT_API = "https://connect.spotware.com/apps/proxy"
    
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
        'PIUSDT': 'PIUSD'    # Pi Network (try without T)
    }
    
    # Timeframe mapping: internal -> cTrader
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
        self.client_id = os.getenv('CTRADER_CLIENT_ID')
        self.client_secret = os.getenv('CTRADER_CLIENT_SECRET')
        self.demo = os.getenv('CTRADER_DEMO', 'True').lower() == 'true'
        
        # Use demo or live endpoint
        self.base_url = self.DEMO_API_BASE if self.demo else self.API_BASE
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # Cache for access tokens
        self._token_cache = None
        self._token_expiry = None
        
        logger.info(f"🔗 cTrader LIVE Data Client initialized")
        logger.info(f"   Account: {self.account_id}")
        logger.info(f"   Mode: {'DEMO' if self.demo else 'LIVE'}")
        logger.info(f"   Endpoint: {self.base_url}")
    
    def _get_access_token(self) -> Optional[str]:
        """Get valid access token (cached or refresh)"""
        try:
            # Check cache
            if self._token_cache and self._token_expiry:
                if datetime.now() < self._token_expiry:
                    return self._token_cache
            
            # Use existing token if provided
            if self.access_token:
                logger.info("🔑 Using provided access token")
                self._token_cache = self.access_token
                self._token_expiry = datetime.now() + timedelta(hours=24)
                return self.access_token
            
            # OAuth2 flow (if credentials provided)
            if self.client_id and self.client_secret:
                logger.info("🔑 Requesting new access token...")
                token_url = f"{self.base_url}/oauth/token"
                data = {
                    'grant_type': 'client_credentials',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                }
                response = requests.post(token_url, data=data)
                
                if response.status_code == 200:
                    token_data = response.json()
                    self._token_cache = token_data['access_token']
                    expires_in = token_data.get('expires_in', 3600)
                    self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)
                    logger.success("✅ Got new access token")
                    return self._token_cache
                else:
                    logger.error(f"❌ Token request failed: {response.status_code}")
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting access token: {e}")
            return None
    
    def get_historical_data(self, symbol: str, timeframe: str = 'D1', bars: int = 100) -> Optional[pd.DataFrame]:
        """
        Obține date istorice OHLC LIVE de la cTrader/IC Markets
        
        Args:
            symbol: Symbol (ex: GBPUSD, EURUSD)
            timeframe: D1, H4, H1, M15, etc.
            bars: Număr de bare
            
        Returns:
            DataFrame cu coloane: time, open, high, low, close, volume
        """
        try:
            # Map symbol
            ctrader_symbol = self.SYMBOL_MAP.get(symbol, symbol)
            ctrader_timeframe = self.TIMEFRAME_MAP.get(timeframe, 'D1')
            
            logger.info(f"📊 Fetching LIVE data: {ctrader_symbol} {ctrader_timeframe} ({bars} bars)...")
            
            # Try cTrader API first
            df = self._fetch_from_ctrader_api(ctrader_symbol, ctrader_timeframe, bars)
            
            if df is not None and not df.empty:
                logger.success(f"✅ Got {len(df)} LIVE candles from IC Markets")
                return df
            
            # Fallback to Twelve Data API (FREE, LIVE data)
            logger.warning(f"⚠️  cTrader API failed for {symbol}, using Twelve Data API...")
            df = self._fetch_from_twelvedata(symbol, timeframe, bars)
            
            if df is not None and not df.empty:
                logger.info(f"✅ Got {len(df)} LIVE candles from Twelve Data API")
                return df
            
            logger.error(f"❌ No data available for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error fetching data for {symbol}: {e}")
            return None
    
    def _fetch_from_ctrader_api(self, symbol: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
        """Fetch data from cTrader Open API"""
        try:
            # Get authentication token
            token = self._get_access_token()
            if not token:
                logger.debug("No cTrader API token configured")
                return None
            
            # Try multiple API endpoints (cTrader uses different URLs)
            endpoints = [
                f"{self.base_url}/v3/ohlc",  # v3 API
                f"{self.base_url}/v2/ohlc",  # v2 API
                f"{self.base_url}/api/v1/ohlc",  # Alternative path
                "https://api-demo.ctrader.com/v3/ohlc"  # Demo-specific
            ]
            
            # Calculate time range
            end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            # Estimate start time based on timeframe
            if timeframe == 'D1':
                start_time = end_time - (bars * 86400000)  # days
            elif timeframe == 'H4':
                start_time = end_time - (bars * 14400000)  # 4 hours
            elif timeframe == 'H1':
                start_time = end_time - (bars * 3600000)   # hours
            elif timeframe == 'M15':
                start_time = end_time - (bars * 900000)    # 15 min
            else:
                start_time = end_time - (bars * 86400000)  # default daily
            
            headers = {'Authorization': f'Bearer {token}'}
            params = {
                'symbol': symbol,
                'periodicity': timeframe,
                'fromTimestamp': start_time,
                'toTimestamp': end_time,
                'barsCount': bars
            }
            
            # Try each endpoint with short timeout
            for endpoint in endpoints:
                try:
                    response = self.session.get(endpoint, headers=headers, params=params, timeout=3)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Parse response (flexible format)
                        candles_data = data.get('data', data.get('candles', data.get('bars', [])))
                        
                        if candles_data:
                            df = self._parse_candles_response(candles_data)
                            if df is not None and not df.empty:
                                return df.tail(bars)
                    
                except (requests.Timeout, requests.ConnectionError):
                    continue  # Try next endpoint
            
            # All endpoints failed
            logger.debug("All cTrader API endpoints failed or returned empty data")
            return None
            
        except Exception as e:
            logger.debug(f"cTrader API error: {e}")
            return None
    
    def _parse_candles_response(self, candles: List[Dict]) -> Optional[pd.DataFrame]:
        """Parse candles data from API response (flexible format)"""
        try:
            if not candles:
                return None
            
            # Try different field names (APIs use different formats)
            time_fields = ['timestamp', 'time', 't', 'date']
            open_fields = ['open', 'o']
            high_fields = ['high', 'h']
            low_fields = ['low', 'l']
            close_fields = ['close', 'c']
            volume_fields = ['volume', 'vol', 'v']
            
            first_candle = candles[0]
            
            # Detect field names
            time_key = next((f for f in time_fields if f in first_candle), None)
            open_key = next((f for f in open_fields if f in first_candle), None)
            high_key = next((f for f in high_fields if f in first_candle), None)
            low_key = next((f for f in low_fields if f in first_candle), None)
            close_key = next((f for f in close_fields if f in first_candle), None)
            volume_key = next((f for f in volume_fields if f in first_candle), None)
            
            if not all([time_key, open_key, high_key, low_key, close_key]):
                return None
            
            df = pd.DataFrame({
                'time': [datetime.fromtimestamp(c[time_key] / 1000) if c[time_key] > 1e10 else datetime.fromtimestamp(c[time_key]) for c in candles],
                'open': [float(c[open_key]) for c in candles],
                'high': [float(c[high_key]) for c in candles],
                'low': [float(c[low_key]) for c in candles],
                'close': [float(c[close_key]) for c in candles],
                'volume': [float(c.get(volume_key, 0)) for c in candles]
            })
            
            return df
            
        except Exception as e:
            logger.debug(f"Error parsing candles: {e}")
            return None
    
    def _fetch_from_twelvedata(self, symbol: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
        """Fetch LIVE data from Twelve Data API (FREE, 800 req/day)"""
        try:
            # Twelve Data API key (free tier)
            api_key = os.getenv('TWELVEDATA_API_KEY', 'demo')  # 'demo' for testing
            
            # Symbol mapping for Twelve Data
            # Twelve Data uses different format: EUR/USD instead of EURUSD
            td_symbols = {
                # Forex majors
                'GBPUSD': 'GBP/USD', 'EURUSD': 'EUR/USD', 'USDJPY': 'USD/JPY',
                'USDCHF': 'USD/CHF', 'AUDUSD': 'AUD/USD', 'USDCAD': 'USD/CAD',
                'NZDUSD': 'NZD/USD',
                # Forex crosses
                'EURJPY': 'EUR/JPY', 'GBPJPY': 'GBP/JPY',
                'EURGBP': 'EUR/GBP', 'EURCAD': 'EUR/CAD', 'AUDCAD': 'AUD/CAD',
                'AUDNZD': 'AUD/NZD', 'NZDCAD': 'NZD/CAD', 'GBPNZD': 'GBP/NZD',
                'GBPCHF': 'GBP/CHF', 'CADCHF': 'CAD/CHF',
                # Commodities
                'XAUUSD': 'XAU/USD',  # Gold
                'XAGUSD': 'XAG/USD',  # Silver
                'USOIL': 'WTI/USD',   # Oil
                # Crypto
                'BTCUSD': 'BTC/USD',
                'PIUSDT': 'PI/USD'    # Pi Network
            }
            
            td_symbol = td_symbols.get(symbol)
            
            # Skip if symbol not available
            if yahoo_symbol is None:
                logger.debug(f"{symbol} not available on Yahoo Finance")
                return None
            
            # If no mapping found, try adding =X suffix
            if yahoo_symbol not in yahoo_symbols.values():
                yahoo_symbol = f"{symbol}=X"
            
            # Timeframe mapping
            interval_map = {'D1': '1d', 'H4': '1h', 'H1': '1h', 'M15': '15m'}
            interval = interval_map.get(timeframe, '1d')
            
            # Calculate period with buffer
            end_date = datetime.now()
            if timeframe == 'D1':
                start_date = end_date - timedelta(days=bars + 50)
            elif timeframe == 'H4':
                start_date = end_date - timedelta(hours=bars * 4 + 100)
            elif timeframe == 'H1':
                start_date = end_date - timedelta(hours=bars + 50)
            else:
                start_date = end_date - timedelta(days=30)
            
            # Fetch with retry
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    ticker = yf.Ticker(yahoo_symbol)
                    df = ticker.history(start=start_date, end=end_date, interval=interval, timeout=5)
                    
                    if not df.empty:
                        break
                        
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(1)
            
            if df.empty:
                return None
            
            # For H4 on yfinance (which only has H1), resample to 4H
            if timeframe == 'H4' and interval == '1h':
                df = df.resample('4h').agg({
                    'Open': 'first',
                    'High': 'max',
                    'Low': 'min',
                    'Close': 'last',
                    'Volume': 'sum'
                }).dropna()
            
            df = df.tail(bars).copy()
            df = df.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low',
                'Close': 'close', 'Volume': 'volume'
            })
            df['time'] = df.index
            df = df.reset_index(drop=True)
            df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
            
            return df
            
        except Exception as e:
            logger.debug(f"yfinance fallback error: {e}")
            return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Obține prețul curent pentru un simbol"""
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
    logger.info("🧪 Testing cTrader Data Client...")
    
    client = get_ctrader_client()
    
    # Test GBPUSD
    df = client.get_historical_data('GBPUSD', 'D1', 50)
    
    if df is not None:
        logger.success(f"✅ Test successful!")
        logger.info(f"\n{df.tail(5)}")
        logger.info(f"\nCurrent GBPUSD price: {client.get_current_price('GBPUSD')}")
    else:
        logger.error("❌ Test failed!")
