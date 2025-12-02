"""
Test Price Action Analyzer on REAL market data
"""
import MetaTrader5 as mt5
import pandas as pd
from loguru import logger
from price_action_analyzer import PriceActionAnalyzer

# Initialize MT5
if not mt5.initialize():
    logger.error("MT5 initialization failed")
    exit()

logger.info(f"MT5 Connected: Account #{mt5.account_info().login}\n")

# Test pairs
test_symbols = ['EURUSD', 'GBPUSD', 'NZDUSD', 'BTCUSD', 'XAUUSD']

analyzer = PriceActionAnalyzer()

logger.info("="*70)
logger.info("🎯 GLITCH IN MATRIX - Price Action Analysis")
logger.info("="*70)

for symbol in test_symbols:
    logger.info(f"\n{'='*70}")
    logger.info(f"📊 Analyzing {symbol}...")
    logger.info(f"{'='*70}")
    
    # Get Daily data
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 100)
    
    if rates is None or len(rates) == 0:
        logger.warning(f"⚠️ No data for {symbol}")
        continue
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Analyze
    signal = analyzer.analyze_full_context(df, symbol)
    
    if signal:
        logger.info(f"\n🚀 SIGNAL DETECTED!")
        logger.info(f"   Direction: {signal.direction.upper()}")
        logger.info(f"   Confidence: {signal.confidence}/10 {'🔥' if signal.confidence >= 8 else '⚡'}")
        logger.info(f"   Market Structure: {signal.market_structure}")
        logger.info(f"   Momentum: {signal.momentum}")
        logger.info(f"   Liquidity Cleared: {'✅' if signal.liquidity_cleared else '❌'}")
        logger.info(f"   FVG Present: {'✅' if signal.fvg_present else '❌'}")
        logger.info(f"   CHoCH Confirmed: {'✅' if signal.choch_confirmed else '❌'}")
        logger.info(f"\n   📍 Levels:")
        logger.info(f"      Entry Zone: {signal.entry_zone[0]:.5f} - {signal.entry_zone[1]:.5f}")
        logger.info(f"      Stop Loss: {signal.stop_loss:.5f}")
        logger.info(f"      Take Profit: {signal.take_profit:.5f}")
        
        # Calculate R:R
        entry_mid = (signal.entry_zone[0] + signal.entry_zone[1]) / 2
        if signal.direction == 'bullish':
            risk = entry_mid - signal.stop_loss
            reward = signal.take_profit - entry_mid
        else:
            risk = signal.stop_loss - entry_mid
            reward = entry_mid - signal.take_profit
        
        rr_ratio = reward / risk if risk > 0 else 0
        logger.info(f"      R:R Ratio: 1:{rr_ratio:.2f}")
        
        logger.info(f"\n   💡 Reasons:")
        for i, reason in enumerate(signal.reasons, 1):
            logger.info(f"      {i}. {reason}")
    else:
        logger.info(f"   ⏳ No high-confidence setup (yet)")

mt5.shutdown()
logger.info("\nMT5 disconnected")

logger.info(f"\n{'='*70}")
logger.info("Analysis Complete!")
logger.info(f"{'='*70}")
