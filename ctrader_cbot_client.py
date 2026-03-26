"""
cTrader cBot Market Data Client
Connects to local cBot HTTP server for real-time IC Markets data
"""

import requests
import pandas as pd
from datetime import datetime
from typing import Optional
from loguru import logger

class CTraderCBotClient:
    """Client for cTrader cBot Market Data Provider"""
    
    def __init__(self, host='localhost', port=8767):
        self.base_url = f"http://{host}:{port}"
        logger.info(f"🤖 CTrader cBot Client initialized: {self.base_url}")
    
    def is_available(self) -> bool:
        """Check if cBot server is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def get_historical_data(self, symbol: str, timeframe: str = 'Daily', bars: int = 200) -> Optional[pd.DataFrame]:
        """
        Get historical OHLCV data from cBot
        
        Args:
            symbol: Trading symbol (e.g., 'GBPUSD', 'XAUUSD')
            timeframe: 'M1', 'M5', 'M15', 'H1', 'H4', 'Daily'
            bars: Number of bars to retrieve
            
        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        try:
            logger.debug(f"📊 Requesting {bars} {timeframe} bars for {symbol}")
            
            params = {
                'symbol': symbol,
                'timeframe': timeframe,
                'bars': bars
            }
            
            # V10.1: timeout 30s — cTrader GetAccountCalculatedValues poate dura >10s la conexiuni lente
            response = requests.get(f"{self.base_url}/data", params=params, timeout=30)
            
            # DETAILED LOGGING FOR DEBUGGING
            logger.debug(f"🔍 Request URL: {response.url}")
            logger.debug(f"🔍 Response Status: {response.status_code}")
            logger.debug(f"🔍 Response Headers: {response.headers}")
            logger.debug(f"🔍 Response Text (first 200 chars): {response.text[:200]}")
            
            if response.status_code != 200:
                logger.error(f"❌ HTTP {response.status_code}: {response.text}")
                
                # FALLBACK: Try with fewer bars if 500 error (cTrader data availability issue)
                if response.status_code == 500 and bars > 100:
                    fallback_counts = [200, 100, 50]
                    for fallback in fallback_counts:
                        if fallback >= bars:
                            continue
                        logger.warning(f"⚠️ Retrying {symbol} {timeframe} with {fallback} bars (fallback from {bars})")
                        try:
                            fallback_response = requests.get(
                                f"{self.base_url}/data",
                                params={'symbol': symbol, 'timeframe': timeframe, 'bars': fallback},
                                timeout=10
                            )
                            if fallback_response.status_code == 200:
                                data = fallback_response.json()
                                if 'bars' in data and len(data['bars']) > 0:
                                    df = pd.DataFrame(data['bars'])
                                    df['time'] = pd.to_datetime(df['time'])
                                    df = df.set_index('time')
                                    for col in ['open', 'high', 'low', 'close', 'volume']:
                                        df[col] = pd.to_numeric(df[col])
                                    logger.success(f"✅ Fallback success: Got {len(df)} bars for {symbol} (requested {bars}, got {fallback})")
                                    return df
                        except Exception as fallback_error:
                            logger.debug(f"Fallback {fallback} failed: {fallback_error}")
                            continue
                
                return None
            
            data = response.json()
            
            if 'bars' not in data or len(data['bars']) == 0:
                logger.warning(f"⚠️ No data returned for {symbol}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(data['bars'])
            df['time'] = pd.to_datetime(df['time'])
            df = df.set_index('time')
            
            # Ensure numeric types
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
            
            logger.success(f"✅ Got {len(df)} bars for {symbol} (latest: {df['close'].iloc[-1]:.5f})")
            return df
            
        except requests.exceptions.ConnectionError:
            logger.error("❌ Cannot connect to cBot server. Is cTrader running with MarketDataProvider cBot?")
            return None
        except requests.exceptions.Timeout:
            # V10.1: cTrader timeout (GetAccountCalculatedValuesResMessage) — nu blocăm scannerul
            logger.warning(f"⏱️  cTrader TIMEOUT pentru {symbol} {timeframe} — date indisponibile temporar (cTrader ocupat)")
            logger.warning(f"   Setup-ul va fi salvat oricum dacă structura există. Retry la scan-ul următor.")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching data: {e}")
            return None

    def get_swap_info(self, symbol: str) -> dict:
        """
        V10.9 CARRY MATRIX — Fetch live swap rates for a symbol from cTrader.

        Returns dict with keys:
            swap_long       (float)  — pips/day charged/credited for BUY positions
            swap_short      (float)  — pips/day charged/credited for SELL positions
            swap_triple_day (str)    — day of the week when triple swap is applied (e.g. "Wednesday")
            success         (bool)
            error           (str)    — only present on failure

        Logic for callers:
            direction == 'buy'  → check swap_long  > 0 ✅ positive (credit) | < 0 ⚠️ cost
            direction == 'sell' → check swap_short > 0 ✅ positive (credit) | < 0 ⚠️ cost
        """
        try:
            response = requests.get(
                f"{self.base_url}/swap_info",
                params={'symbol': symbol},
                timeout=10
            )
            if response.status_code != 200:
                logger.warning(f"⚠️ swap_info HTTP {response.status_code} for {symbol}")
                return {'success': False, 'error': f"HTTP {response.status_code}"}

            data = response.json()
            if not data.get('success'):
                logger.warning(f"⚠️ swap_info error for {symbol}: {data.get('error')}")
                return {'success': False, 'error': data.get('error', 'Unknown')}

            logger.debug(
                f"💱 SWAP {symbol}: long={data['swap_long']:+.2f} "
                f"short={data['swap_short']:+.2f} triple={data['swap_triple_day']}"
            )
            return {
                'success': True,
                'swap_long': float(data['swap_long']),
                'swap_short': float(data['swap_short']),
                'swap_triple_day': str(data['swap_triple_day']),
            }

        except requests.exceptions.ConnectionError:
            logger.debug(f"⚠️ swap_info: cBot not available for {symbol}")
            return {'success': False, 'error': 'Connection refused'}
        except Exception as e:
            logger.debug(f"⚠️ swap_info exception for {symbol}: {e}")
            return {'success': False, 'error': str(e)}


def get_cbot_client() -> CTraderCBotClient:
    """Get singleton cBot client instance"""
    return CTraderCBotClient()


if __name__ == '__main__':
    # Test the client
    client = get_cbot_client()
    
    print("🧪 Testing cBot connection...")
    print()
    
    if not client.is_available():
        print("❌ cBot server not running!")
        print()
        print("Please start MarketDataProvider cBot in cTrader Automate:")
        print("1. Open cTrader Desktop")
        print("2. Go to Automate tab")
        print("3. Find 'MarketDataProvider' cBot")
        print("4. Click Start")
        exit(1)
    
    print("✅ cBot server is running!")
    print()
    
    # Test GBPUSD
    print("📊 Testing GBPUSD Daily data...")
    df = client.get_historical_data('GBPUSD', 'Daily', 10)
    
    if df is not None:
        print(f"✅ Success! Got {len(df)} bars")
        print()
        print("Latest 3 candles:")
        print(df[['open', 'high', 'low', 'close']].tail(3))
        print()
        print(f"💰 Latest close: ${df['close'].iloc[-1]:.5f}")
    else:
        print("❌ Failed to get data")
