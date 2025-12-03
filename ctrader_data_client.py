"""
IC Markets LIVE Data Client - NO Yahoo Finance
Uses Twelve Data API for real-time market data (FREE, 800 req/day)
Fallback hierarchy: cTrader API -> Twelve Data API -> Error
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
    Client LIVE pentru date de piață - ZERO Yahoo Finance dependency
    Priority: cTrader OpenAPI -> Twelve Data API
    """
    
    # cTrader Open API endpoints
    API_BASE = "https://api.ctrader.com"
    DEMO_API_BASE = "https://api.ctrader.com"
    
    # Twelve Data API (FREE tier: 800 requests/day, <1 sec delay)
    TWELVEDATA_BASE = "https://api.twelvedata.com"
    
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
    
    # Twelve Data symbol mapping (different format: EUR/USD)
    TWELVEDATA_SYMBOLS = {
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
        self.client_id = os.getenv('CTRADER_CLIENT_ID')
        self.client_secret = os.getenv('CTRADER_CLIENT_SECRET')
        self.twelvedata_key = os.getenv('TWELVEDATA_API_KEY', 'demo')
        self.demo = os.getenv('CTRADER_DEMO', 'True').lower() == 'true'
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        logger.info(f"🔗 IC Markets LIVE Data Client initialized (NO Yahoo Finance)")
        logger.info(f"   Priority: cTrader API -> Twelve Data API")
        logger.info(f"   Account: {self.account_id}")
        logger.info(f"   Mode: {'DEMO' if self.demo else 'LIVE'}")
    
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
            
            # Try cTrader API first (if configured)
            if self.access_token or (self.client_id and self.client_secret):
                df = self._fetch_from_ctrader_api(ctrader_symbol, ctrader_timeframe, bars)
                if df is not None and not df.empty:
                    logger.success(f"✅ Got {len(df)} LIVE candles from cTrader API")
                    return df
            
            # Fallback to Twelve Data API (LIVE data, <1 sec delay)
            logger.info(f"🔄 Using Twelve Data API for {symbol}...")
            df = self._fetch_from_twelvedata(symbol, timeframe, bars)
            
            if df is not None and not df.empty:
                logger.success(f"✅ Got {len(df)} LIVE candles from Twelve Data API")
                return df
            
            logger.error(f"❌ No data available for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error fetching data for {symbol}: {e}")
            return None
    
    def _fetch_from_ctrader_api(self, symbol: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
        """Fetch data from cTrader Open API (if configured)"""
        try:
            # Get authentication token
            token = self.access_token
            if not token:
                logger.debug("No cTrader API token configured")
                return None
            
            # Build API request
            url = f"{self.DEMO_API_BASE if self.demo else self.API_BASE}/v3/ohlc"
            headers = {'Authorization': f'Bearer {token}'}
            
            # Calculate time range
            end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            if timeframe == 'D1':
                start_time = end_time - (bars * 86400000)
            elif timeframe == 'H4':
                start_time = end_time - (bars * 14400000)
            elif timeframe == 'H1':
                start_time = end_time - (bars * 3600000)
            else:
                start_time = end_time - (bars * 86400000)
            
            params = {
                'symbol': symbol,
                'periodicity': timeframe,
                'fromTimestamp': start_time,
                'toTimestamp': end_time,
                'barsCount': bars
            }
            
            response = self.session.get(url, headers=headers, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                candles_data = data.get('data', data.get('candles', data.get('bars', [])))
                
                if candles_data:
                    df = self._parse_candles_response(candles_data)
                    if df is not None and not df.empty:
                        return df.tail(bars)
            
            return None
            
        except Exception as e:
            logger.debug(f"cTrader API error: {e}")
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
    
    def _fetch_from_twelvedata(self, symbol: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
        """Fetch LIVE data from Twelve Data API (FREE, 800 req/day, <1 sec delay)"""
        try:
            # Get Twelve Data symbol
            td_symbol = self.TWELVEDATA_SYMBOLS.get(symbol)
            
            if not td_symbol:
                logger.debug(f"{symbol} not mapped for Twelve Data")
                return None
            
            # Timeframe mapping
            interval_map = {
                'D1': '1day',
                'H4': '4h',
                'H1': '1h',
                'M15': '15min',
                'M5': '5min',
                'M1': '1min'
            }
            interval = interval_map.get(timeframe, '1day')
            
            # Build API request
            url = f"{self.TWELVEDATA_BASE}/time_series"
            params = {
                'symbol': td_symbol,
                'interval': interval,
                'outputsize': min(bars + 10, 5000),  # Add buffer
                'apikey': self.twelvedata_key,
                'format': 'JSON'
            }
            
            # Request data
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
