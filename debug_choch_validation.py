"""
Debug CHoCH validation - see exact swings checked at break moment
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

symbol = 'GBPUSD'

logger.info(f"🔍 Analyzing {symbol} CHoCH validation...")

detector = SMCDetector()
df = get_data(symbol, mt5.TIMEFRAME_D1, 100)

swing_highs = detector.detect_swing_highs(df)
swing_lows = detector.detect_swing_lows(df)

# Find the CHoCH swing (1.32158 @ index ~96)
for sh in swing_highs[-5:]:
    if abs(sh.price - 1.32158) < 0.001:
        logger.info(f"\n✅ Found CHoCH swing: {sh.price} @ index {sh.index}")
        
        # Get swings BEFORE this point (as validation does)
        recent_highs = [s for s in swing_highs if s.index <= sh.index][-3:]
        recent_lows = [s for s in swing_lows if s.index <= sh.index][-3:]
        
        logger.info(f"\n📈 Recent Highs BEFORE break (last 3):")
        for rh in recent_highs:
            logger.info(f"   {rh.price} @ index {rh.index}")
        
        logger.info(f"\n📉 Recent Lows BEFORE break (last 3):")
        for rl in recent_lows:
            logger.info(f"   {rl.price} @ index {rl.index}")
        
        # Check patterns
        if len(recent_highs) >= 2:
            lh_pattern = recent_highs[-1].price < recent_highs[-2].price
            logger.info(f"\n{'✅' if lh_pattern else '❌'} LH pattern: {recent_highs[-2].price} → {recent_highs[-1].price}")
        
        if len(recent_lows) >= 2:
            ll_pattern = recent_lows[-1].price < recent_lows[-2].price
            logger.info(f"{'✅' if ll_pattern else '❌'} LL pattern: {recent_lows[-2].price} → {recent_lows[-1].price}")
        
        if lh_pattern and ll_pattern:
            logger.info(f"\n✅ BOTH patterns confirmed → CHoCH BULLISH valid")
        else:
            logger.info(f"\n❌ NOT both patterns → CHoCH should be rejected")

mt5.shutdown()
print("🔌 MT5 disconnected")
