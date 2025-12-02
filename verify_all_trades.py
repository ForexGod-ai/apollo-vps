"""
Verify all 3 executed trades - check directions
"""
from daily_scanner import MT5DataProvider
from smc_detector import SMCDetector
from loguru import logger
import json

logger.info("🔍 Verifying all executed trades...")

# Load trade history
with open('trade_history.json', 'r') as f:
    trades = json.load(f)

# Initialize
data_provider = MT5DataProvider()
smc_detector = SMCDetector()

if data_provider.connect():
    for trade in trades:
        symbol = trade['symbol']
        direction = trade['direction']
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 Analyzing {symbol} - Trade Direction: {direction}")
        logger.info(f"{'='*60}")
        
        # Get Daily data
        df_daily = data_provider.get_historical_data(symbol, "D1", 100)
        
        if df_daily is not None:
            # Detect MACRO TREND (new logic)
            macro_trend = smc_detector.detect_macro_trend(df_daily)
            
            logger.info(f"✅ MACRO TREND: {macro_trend.upper()}")
            
            # Also show CHoCH for reference
            chochs = smc_detector.detect_choch(df_daily)
            
            if chochs:
                last_choch = chochs[-1]
                logger.info(f"   • Last CHoCH (micro): {last_choch.direction.upper()} @ {last_choch.candle_time}")
                logger.info(f"   • Break: {last_choch.break_price}")
                
                # Expected trade direction based on MACRO TREND
                if macro_trend == 'bullish':
                    expected = "BUY"
                elif macro_trend == 'bearish':
                    expected = "SELL"
                else:
                    expected = "NEUTRAL"
                
                if direction == expected:
                    logger.info(f"   ✅ CORRECT: {direction} matches {macro_trend.upper()} MACRO TREND")
                else:
                    logger.error(f"   ❌ WRONG: {direction} but MACRO TREND is {macro_trend.upper()} (should be {expected})")
                    logger.warning(f"      This trade may be against the macro trend!")
            else:
                logger.warning(f"⚠️ No CHoCH detected for {symbol}")
        else:
            logger.error(f"❌ No data for {symbol}")
    
    data_provider.disconnect()
else:
    logger.error("❌ Failed to connect to MT5")

logger.info(f"\n{'='*60}")
logger.info("✅ Verification complete")
