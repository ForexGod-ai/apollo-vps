"""
Verify GBPUSD and GBPCHF setup directions
"""
import MetaTrader5 as mt5
import pandas as pd
from loguru import logger
from smc_detector import SMCDetector

# Initialize MT5
if not mt5.initialize():
    print("MT5 initialization failed")
    exit()

print(f"✅ MT5 Connected: Account #{mt5.account_info().login}, Balance: ${mt5.account_info().balance:.2f}")

def get_data(symbol: str, timeframe, bars: int = 100) -> pd.DataFrame:
    """Get OHLC data from MT5"""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0:
        return None
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

pairs = ['GBPUSD', 'GBPCHF']

for symbol in pairs:
    logger.info(f"\n{'='*60}")
    logger.info(f"🔍 Analyzing {symbol}...")
    logger.info(f"{'='*60}")
    
    detector = SMCDetector()
    df = get_data(symbol, mt5.TIMEFRAME_D1, 100)
    
    if df is None or df.empty:
        logger.warning(f"❌ No data for {symbol}")
        continue
    
    # Get CHoCH
    chochs, bos = detector.detect_choch_and_bos(df)
    
    logger.info(f"\n📊 CHoCHs detected: {len(chochs)}")
    if chochs:
        latest_choch = chochs[-1]
        logger.info(f"   Latest: {latest_choch.direction.upper()} @ {latest_choch.break_price} ({latest_choch.candle_time})")
        logger.info(f"   Previous trend: {latest_choch.previous_trend}")
    
    # Get swing structure
    swing_highs = detector.detect_swing_highs(df)
    swing_lows = detector.detect_swing_lows(df)
    
    logger.info(f"\n📈 Last 5 Swing Highs:")
    for sh in swing_highs[-5:]:
        logger.info(f"   {sh.price} @ {df['time'].iloc[sh.index]}")
    
    logger.info(f"\n📉 Last 5 Swing Lows:")
    for sl in swing_lows[-5:]:
        logger.info(f"   {sl.price} @ {df['time'].iloc[sl.index]}")
    
    # Check pattern
    if len(swing_highs) >= 3:
        h1, h2, h3 = swing_highs[-3:]
        if h3.price < h2.price < h1.price:
            logger.info(f"\n❌ LOWER HIGHS pattern → BEARISH structure")
        elif h3.price > h2.price > h1.price:
            logger.info(f"\n✅ HIGHER HIGHS pattern → BULLISH structure")
    
    if len(swing_lows) >= 3:
        l1, l2, l3 = swing_lows[-3:]
        if l3.price < l2.price < l1.price:
            logger.info(f"❌ LOWER LOWS pattern → BEARISH structure")
        elif l3.price > l2.price > l1.price:
            logger.info(f"✅ HIGHER LOWS pattern → BULLISH structure")

mt5.shutdown()
print("🔌 MT5 disconnected")
