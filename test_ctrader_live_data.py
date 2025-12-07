"""
Test IC Markets Live Data via cTrader
Verifică conexiunea și primirea de date real-time
"""

import asyncio
import sys
from loguru import logger
from ctrader_data_client import get_ctrader_client

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")

async def test_live_data():
    """Test live data from IC Markets"""
    
    print("=" * 70)
    print("🧪 TEST IC MARKETS LIVE DATA")
    print("=" * 70)
    print()
    
    # Initialize client
    logger.info("🔌 Conectare la IC Markets...")
    client = get_ctrader_client()
    
    # Test pairs
    test_pairs = ['GBPUSD', 'EURUSD', 'XAUUSD']
    timeframes = ['D1', 'H4']
    
    for symbol in test_pairs:
        print(f"\n📊 Testing {symbol}...")
        
        for tf in timeframes:
            try:
                logger.info(f"   Fetching {symbol} {tf} data...")
                df = client.get_live_data(symbol, tf, bars=10)
                
                if df is not None and not df.empty:
                    logger.success(f"   ✅ {symbol} {tf}: {len(df)} bars received")
                    logger.info(f"      Last close: {df['close'].iloc[-1]:.5f}")
                    logger.info(f"      Time: {df.index[-1]}")
                else:
                    logger.warning(f"   ⚠️  {symbol} {tf}: No data")
                    
            except Exception as e:
                logger.error(f"   ❌ {symbol} {tf}: {str(e)}")
    
    print()
    print("=" * 70)
    print("✅ TEST COMPLET!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_live_data())
