"""
Verify new trades with macro trend logic
"""
from daily_scanner import MT5DataProvider
from smc_detector import SMCDetector
from loguru import logger
import json

logger.info("🔍 Verifying newly executed trades with MACRO TREND...")

# Load latest trades
with open('trade_history.json', 'r') as f:
    all_trades = json.load(f)

# Get only OPEN trades
open_trades = [t for t in all_trades if t['status'] == 'OPEN']

logger.info(f"\n📊 Found {len(open_trades)} open trades\n")

# Initialize
data_provider = MT5DataProvider()
smc_detector = SMCDetector()

if data_provider.connect():
    for trade in open_trades:
        symbol = trade['symbol']
        direction = trade['direction']
        
        logger.info(f"{'='*70}")
        logger.info(f"📊 {symbol} {direction}")
        logger.info(f"{'='*70}")
        
        # Get Daily data
        df_daily = data_provider.get_historical_data(symbol, "D1", 100)
        
        if df_daily is not None:
            # Detect MACRO TREND
            macro_trend = smc_detector.detect_macro_trend(df_daily)
            
            logger.info(f"🎯 MACRO TREND: {macro_trend.upper()}")
            
            # Check swing structure
            swing_highs = smc_detector.detect_swing_highs(df_daily)
            swing_lows = smc_detector.detect_swing_lows(df_daily)
            
            logger.info(f"\n📈 Last 3 Swing Highs:")
            for sh in swing_highs[-3:]:
                logger.info(f"   {sh.candle_time.strftime('%b %d')} - {sh.price:.5f}")
            
            logger.info(f"\n📉 Last 3 Swing Lows:")
            for sl in swing_lows[-3:]:
                logger.info(f"   {sl.candle_time.strftime('%b %d')} - {sl.price:.5f}")
            
            # Expected direction
            if macro_trend == 'bullish':
                expected = "BUY"
            elif macro_trend == 'bearish':
                expected = "SELL"
            else:
                expected = "NEUTRAL"
            
            # Verify correctness
            logger.info(f"\n💡 Analysis:")
            if direction == expected:
                logger.info(f"   ✅ CORRECT: {direction} aligns with {macro_trend.upper()} macro trend")
                logger.info(f"   This trade follows the overall market structure!")
            else:
                logger.error(f"   ❌ WRONG: {direction} but macro trend is {macro_trend.upper()}")
                logger.warning(f"   Expected {expected} trade!")
            
            # Show trade details
            logger.info(f"\n📝 Trade Details:")
            logger.info(f"   Entry: {trade['entry_price']}")
            logger.info(f"   SL: {trade['stop_loss']}")
            logger.info(f"   TP: {trade['take_profit']}")
            logger.info(f"   R:R: 1:{trade['risk_reward']:.2f}")
            logger.info(f"   Strategy: {trade['strategy_type'].upper()}")
            
            logger.info(f"\n")
        else:
            logger.error(f"❌ No data for {symbol}")
    
    data_provider.disconnect()
else:
    logger.error("❌ Failed to connect to MT5")

logger.info(f"{'='*70}")
logger.info("✅ Verification complete!")
