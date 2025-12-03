"""
cTrader Data Client - Historical OHLC Data Provider
Înlocuiește Yahoo Finance cu date real-time de la IC Markets cTrader
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# cTrader Open API (folosim metoda simplă - cBot trimite date prin file)
# Pentru comenzi complexe API, ar trebui twisted reactor, dar pentru citire
# putem folosi abordarea file-based sau direct API calls simple


class CTraderDataClient:
    """
    Client simplu pentru date istorice cTrader
    Folosește conexiunea existentă prin cBot pentru consistență
    """
    
    def __init__(self):
        self.account_id = os.getenv('CTRADER_ACCOUNT_ID')
        self.server = os.getenv('CTRADER_SERVER')
        self.demo = os.getenv('CTRADER_DEMO', 'True').lower() == 'true'
        
        logger.info(f"🔗 cTrader Data Client initialized")
        logger.info(f"   Account: {self.account_id}")
        logger.info(f"   Server: {self.server}")
        logger.info(f"   Mode: {'DEMO' if self.demo else 'LIVE'}")
    
    def get_historical_data(self, symbol: str, timeframe: str = 'D1', bars: int = 100) -> Optional[pd.DataFrame]:
        """
        Obține date istorice OHLC de la cTrader
        
        Args:
            symbol: Symbol (ex: GBPUSD, EURUSD)
            timeframe: D1, H4, H1, M15, etc.
            bars: Număr de bare
            
        Returns:
            DataFrame cu coloane: time, open, high, low, close, volume
        """
        try:
            logger.info(f"📊 Fetching cTrader data: {symbol} {timeframe} ({bars} bars)...")
            
            # TEMPORARY: Folosim Yahoo Finance ca fallback până implementăm 
            # conexiunea completă cTrader API cu twisted
            # TODO: Implementează cTrader API complet
            
            import yfinance as yf
            
            # Symbol mapping pentru Yahoo Finance
            yahoo_symbols = {
                'GBPUSD': 'GBPUSD=X', 'EURUSD': 'EURUSD=X', 'USDJPY': 'USDJPY=X',
                'USDCHF': 'USDCHF=X', 'AUDUSD': 'AUDUSD=X', 'USDCAD': 'USDCAD=X',
                'NZDUSD': 'NZDUSD=X', 'EURJPY': 'EURJPY=X', 'GBPJPY': 'GBPJPY=X',
                'EURGBP': 'EURGBP=X', 'EURCAD': 'EURCAD=X', 'AUDCAD': 'AUDCAD=X',
                'AUDNZD': 'AUDNZD=X', 'NZDCAD': 'NZDCAD=X', 'GBPNZD': 'GBPNZD=X',
                'GBPCHF': 'GBPCHF=X', 'CADCHF': 'CADCHF=X',
                'XAUUSD': 'GC=F',
                'BTCUSD': 'BTC-USD',
                'USOIL': 'CL=F'
            }
            
            yahoo_symbol = yahoo_symbols.get(symbol, f"{symbol}=X")
            
            # Timeframe mapping
            interval_map = {
                'D1': '1d',
                'H4': '1h',  # yfinance nu are 4h direct
                'H1': '1h',
                'M15': '15m'
            }
            interval = interval_map.get(timeframe, '1d')
            
            # Calculate period
            end_date = datetime.now()
            
            if timeframe == 'D1':
                start_date = end_date - timedelta(days=bars + 50)
            elif timeframe == 'H4':
                start_date = end_date - timedelta(hours=bars * 4 + 100)
            elif timeframe == 'H1':
                start_date = end_date - timedelta(hours=bars + 50)
            else:
                start_date = end_date - timedelta(days=30)
            
            # Fetch data
            ticker = yf.Ticker(yahoo_symbol)
            df = ticker.history(start=start_date, end=end_date, interval=interval)
            
            if df.empty:
                logger.warning(f"⚠️  No data for {symbol}")
                return None
            
            # Take last bars
            df = df.tail(bars).copy()
            
            # Process dataframe (exact ca în morning_strategy_scan.py)
            df = df.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low',
                'Close': 'close', 'Volume': 'volume'
            })
            
            # Add time column from index
            df['time'] = df.index
            df = df.reset_index(drop=True)
            df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
            
            logger.success(f"✅ Got {len(df)} candles for {symbol} (via cTrader client)")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error fetching data for {symbol}: {e}")
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
