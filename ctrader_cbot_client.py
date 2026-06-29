"""
cTrader cBot Market Data Client
Connects to local cBot HTTP server for real-time IC Markets data
"""

import requests
import pandas as pd
import time
from datetime import datetime
from typing import List, Optional
from loguru import logger

class CTraderCBotClient:
    """Client for cTrader cBot Market Data Provider"""
    
    def __init__(self, host='localhost', port=8010):
        self.base_url = f"http://{host}:{port}"
        logger.info(f"🤖 CTrader cBot Client initialized: {self.base_url}")
    
    def is_available(self, retries: int = 3, wait: float = 2.0) -> bool:
        """
        Check if cBot server is running on port 8010 with retry logic.
        V44.2: /health (instant) + probe /data 1 bar — 500 Timeout = cBot pornit dar main thread blocat.
        """
        for attempt in range(1, retries + 1):
            try:
                health = requests.get(f"{self.base_url}/health", timeout=5)
                if health.status_code != 200:
                    raise requests.exceptions.ConnectionError("health not ok")
                # Probe real data — 1 bar Daily
                response = requests.get(
                    f"{self.base_url}/data",
                    params={'symbol': 'GBPUSD', 'timeframe': 'Daily', 'bars': 1},
                    timeout=15,
                )
                if response.status_code == 200:
                    payload = response.json()
                    if payload.get('bars'):
                        return True
                    api_err = payload.get('error', '')
                    if api_err and 'Timeout' in str(api_err):
                        logger.warning(
                            "⚠️ cBot port 8010 UP but main thread busy (Timeout on probe) — "
                            "restart MarketDataProvider cBot or reduce radar load during scan"
                        )
                        return True  # server up; scanner may still struggle until cBot fix deployed
                elif response.status_code == 500 and 'Timeout' in response.text:
                    logger.warning("⚠️ cBot HTTP 500 Timeout on probe — main thread overloaded")
                    return True
            except requests.exceptions.ConnectionError:
                print(f"⏳ Waiting for cTrader on port 8010... (attempt {attempt}/{retries})")
            except Exception as e:
                print(f"⚠️ cTrader health check error: {e}")
            if attempt < retries:
                time.sleep(wait)
        print("❌ cTrader MarketDataProvider (port 8010) not reachable. Start the DATA-Market cBot in cTrader.")
        return False
    
    @staticmethod
    def _bar_fallback_chain(requested: int) -> List[int]:
        """V36.4: lanț de avarie — jumătate, apoi 150/100/50 bare minime."""
        chain: List[int] = []
        seen: set = set()
        for candidate in (requested, requested // 2, 150, 100, 50, 30):
            if candidate and candidate >= 10 and candidate not in seen:
                seen.add(candidate)
                chain.append(candidate)
        return chain

    def _dataframe_from_payload(
        self,
        data: object,
        symbol: str,
        timeframe: str,
    ) -> Optional[pd.DataFrame]:
        """V36.4: parse sigur — fără crash pe None / error dict / bars lipsă."""
        if data is None:
            logger.warning(f"⚠️ [V36.4] Payload None pentru {symbol} {timeframe}")
            return None
        if not isinstance(data, dict):
            logger.warning(f"⚠️ [V36.4] Payload invalid ({type(data).__name__}) pentru {symbol} {timeframe}")
            return None
        api_error = data.get('error')
        if api_error:
            logger.warning(f"⚠️ [V36.4] API error {symbol} {timeframe}: {api_error}")
            return None
        bars = data.get('bars')
        if not isinstance(bars, list) or len(bars) == 0:
            logger.warning(f"⚠️ [V36.4] Fără bare în răspuns pentru {symbol} {timeframe}")
            return None
        try:
            df = pd.DataFrame(bars)
            if df.empty or 'close' not in df.columns:
                return None
            df['time'] = pd.to_datetime(df['time'])
            df = df.set_index('time')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            if df['close'].isna().all():
                return None
            return df
        except Exception as parse_err:
            logger.warning(f"⚠️ [V36.4] Parse DataFrame eșuat {symbol} {timeframe}: {parse_err}")
            return None

    def _fetch_bars_once(
        self,
        symbol: str,
        timeframe: str,
        bars: int,
        timeout: int = 30,
    ) -> Optional[pd.DataFrame]:
        """O singură cerere HTTP — returnează DataFrame sau None, fără excepții neprinse."""
        params = {'symbol': symbol, 'timeframe': timeframe, 'bars': bars}
        logger.debug(f"📊 Requesting {bars} {timeframe} bars for {symbol}")
        response = requests.get(f"{self.base_url}/data", params=params, timeout=timeout)
        logger.debug(f"🔍 Request URL: {response.url}")
        logger.debug(f"🔍 Response Status: {response.status_code}")
        logger.debug(f"🔍 Response Text (first 200 chars): {response.text[:200]}")
        if response.status_code != 200:
            logger.error(f"❌ HTTP {response.status_code}: {response.text[:200]}")
            return None
        try:
            payload = response.json()
        except Exception as json_err:
            logger.warning(f"⚠️ [V36.4] JSON invalid {symbol} {timeframe}: {json_err}")
            return None
        return self._dataframe_from_payload(payload, symbol, timeframe)

    def get_historical_data(self, symbol: str, timeframe: str = 'Daily', bars: int = 200) -> Optional[pd.DataFrame]:
        """
        Get historical OHLCV data from cBot — V36.4 fallback automat pe număr de bare.
        """
        try:
            for bar_count in self._bar_fallback_chain(bars):
                try:
                    df = self._fetch_bars_once(symbol, timeframe, bar_count)
                    if df is not None and not df.empty:
                        if bar_count != bars:
                            logger.warning(
                                f"⚠️ [V36.4 FALLBACK] {symbol} {timeframe}: "
                                f"{bars}→{bar_count} bare OK ({len(df)} primite)"
                            )
                        else:
                            logger.success(
                                f"✅ Got {len(df)} bars for {symbol} "
                                f"(latest: {df['close'].iloc[-1]:.5f})"
                            )
                        return df
                except requests.exceptions.Timeout:
                    logger.warning(
                        f"⏱️  TIMEOUT {symbol} {timeframe} x{bar_count} — încerc mai puține bare..."
                    )
                except Exception as req_err:
                    logger.warning(
                        f"⚠️ [V36.4] Cerere eșuată {symbol} {timeframe} x{bar_count}: {req_err}"
                    )
                time.sleep(0.15)  # V44.2: evită flood pe cBot main thread (radar + scanner)
            logger.warning(f"⚠️ [V36.4] Toate fallback-urile epuizate pentru {symbol} {timeframe}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("❌ Cannot connect to cBot server. Is cTrader running with MarketDataProvider cBot?")
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
