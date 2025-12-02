"""
Test SMC Algorithm on real market data
Compare with GLITCH Price Action Analyzer
"""

import MetaTrader5 as mt5
import pandas as pd
from loguru import logger
from smc_algorithm import SMCAlgorithm
from price_action_analyzer import PriceActionAnalyzer

# Initialize MT5
if not mt5.initialize():
    logger.error("MT5 initialization failed")
    exit()

logger.info(f"✅ MT5 Connected: Account #{mt5.account_info().login}")

# Test symbols
test_symbols = ['NZDUSD', 'GBPUSD', 'BTCUSD', 'EURUSD', 'XAUUSD']

# Initialize both systems
smc = SMCAlgorithm()
glitch = PriceActionAnalyzer()

logger.info("\n" + "="*80)
logger.info("🔥 SMC ALGORITHM vs GLITCH ANALYZER - HEAD TO HEAD")
logger.info("="*80)

for symbol in test_symbols:
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 Testing {symbol}")
    logger.info(f"{'='*80}")
    
    # Get data
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 100)
    if rates is None:
        logger.warning(f"No data for {symbol}")
        continue
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    current_price = df['close'].iloc[-1]
    logger.info(f"Current Price: ${current_price:.5f}")
    
    # Test SMC Algorithm
    logger.info(f"\n🎯 SMC ALGORITHM:")
    smc_signal = smc.analyze(df, symbol)
    
    if smc_signal:
        logger.info(f"   ✅ SIGNAL DETECTED!")
        logger.info(f"   Direction: {smc_signal.direction.upper()}")
        logger.info(f"   Confidence: {smc_signal.confidence}/10 {'⭐' * smc_signal.confidence}")
        logger.info(f"   Order Block: {smc_signal.order_block.type.upper()} at ${smc_signal.order_block.body_middle:.5f}")
        logger.info(f"   Market Structure: {smc_signal.market_structure}")
        logger.info(f"   In Premium: {'✅' if smc_signal.in_premium else '❌'}")
        logger.info(f"   In Discount: {'✅' if smc_signal.in_discount else '❌'}")
        logger.info(f"   Liquidity Swept: {'✅' if smc_signal.liquidity_swept else '❌'}")
        logger.info(f"   Entry Zone: ${smc_signal.entry_zone[0]:.5f} - ${smc_signal.entry_zone[1]:.5f}")
        logger.info(f"   Stop Loss: ${smc_signal.stop_loss:.5f}")
        logger.info(f"   Take Profit: ${smc_signal.take_profit:.5f}")
        logger.info(f"   Risk/Reward: 1:{smc_signal.risk_reward:.2f}")
        logger.info(f"\n   Reasons:")
        for i, reason in enumerate(smc_signal.reasons, 1):
            logger.info(f"      {i}. {reason}")
    else:
        logger.info(f"   ⏳ No signal")
    
    # Test GLITCH
    logger.info(f"\n🔥 GLITCH ANALYZER:")
    glitch_signal = glitch.analyze_full_context(df, symbol)
    
    if glitch_signal:
        logger.info(f"   ✅ SIGNAL DETECTED!")
        logger.info(f"   Direction: {glitch_signal.direction.upper()}")
        logger.info(f"   Confidence: {glitch_signal.confidence}/10 {'⭐' * glitch_signal.confidence}")
        logger.info(f"   Market Structure: {glitch_signal.market_structure}")
        logger.info(f"   CHoCH: {'✅' if glitch_signal.choch_confirmed else '❌'}")
        logger.info(f"   FVG: {'✅' if glitch_signal.fvg_present else '❌'}")
    else:
        logger.info(f"   ⏳ No signal")
    
    # Compare
    if smc_signal and glitch_signal:
        logger.info(f"\n💥 BOTH SYSTEMS AGREE!")
        if smc_signal.direction == glitch_signal.direction:
            logger.info(f"   ✅✅ SAME DIRECTION: {smc_signal.direction.upper()}")
            logger.info(f"   🔥🔥 MEGA CONFLUENCE - INSTITUTIONAL + GLITCH!")
            logger.info(f"   Combined Confidence: {(smc_signal.confidence + glitch_signal.confidence) / 2:.1f}/10")
        else:
            logger.info(f"   ⚠️ CONFLICT: SMC={smc_signal.direction.upper()} vs GLITCH={glitch_signal.direction.upper()}")

logger.info(f"\n{'='*80}")
logger.info("✅ TEST COMPLETE")
logger.info("="*80)

mt5.shutdown()
