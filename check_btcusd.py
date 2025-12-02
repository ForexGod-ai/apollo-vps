"""
Check BTCUSD for SELL setup - ForexGod analysis
"""

import MetaTrader5 as mt5
import pandas as pd
from loguru import logger
from price_action_analyzer import PriceActionAnalyzer

# Initialize MT5
if not mt5.initialize():
    logger.error("MT5 initialization failed")
    exit()

logger.info(f"✅ MT5 Connected: Account #{mt5.account_info().login}")

# Get BTCUSD data
symbol = "BTCUSD"
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 100)

if rates is None:
    logger.error(f"Failed to get {symbol} data")
    mt5.shutdown()
    exit()

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

logger.info(f"\n{'='*80}")
logger.info(f"📊 ANALYZING {symbol} - ForexGod's Eye")
logger.info(f"{'='*80}")
logger.info(f"Last Close: ${df['close'].iloc[-1]:,.2f}")
logger.info(f"Last High: ${df['high'].iloc[-1]:,.2f}")
logger.info(f"Last Low: ${df['low'].iloc[-1]:,.2f}")

# Run GLITCH analysis
analyzer = PriceActionAnalyzer()
signal = analyzer.analyze_full_context(df, symbol)

if signal:
    logger.info(f"\n🔥 GLITCH SIGNAL DETECTED!")
    logger.info(f"{'='*80}")
    logger.info(f"Direction: {signal.direction.upper()}")
    logger.info(f"Confidence: {signal.confidence}/10 {'⭐' * signal.confidence}")
    logger.info(f"\n📊 MARKET ANALYSIS:")
    logger.info(f"   Market Structure: {signal.market_structure}")
    logger.info(f"   Momentum: {signal.momentum}")
    logger.info(f"   CHoCH Confirmed: {'✅' if signal.choch_confirmed else '❌'}")
    logger.info(f"   FVG Present: {'✅' if signal.fvg_present else '❌'}")
    logger.info(f"   Liquidity Cleared: {'✅' if signal.liquidity_cleared else '❌'}")
    
    logger.info(f"\n💡 CONFLUENCE REASONS ({len(signal.reasons)}):")
    for i, reason in enumerate(signal.reasons, 1):
        logger.info(f"   {i}. {reason}")
    
    logger.info(f"\n📍 TRADING LEVELS:")
    logger.info(f"   Entry Zone: ${signal.entry_zone[0]:,.2f} - ${signal.entry_zone[1]:,.2f}")
    logger.info(f"   Stop Loss: ${signal.stop_loss:,.2f}")
    logger.info(f"   Take Profit: ${signal.take_profit:,.2f}")
    
    risk = abs(signal.entry_zone[0] - signal.stop_loss)
    reward = abs(signal.take_profit - signal.entry_zone[0])
    logger.info(f"   Risk/Reward: 1:{reward/risk:.2f}")
    
    logger.info(f"\n{'='*80}")
else:
    logger.info(f"\n⏳ No high-confidence signal detected")
    logger.info(f"Checking why...")
    
    # Manual check for SELL potential
    logger.info(f"\n🔍 MANUAL ANALYSIS:")
    
    # Check recent highs for resistance
    recent_highs = df['high'].iloc[-20:].nlargest(3)
    logger.info(f"   Recent key highs: {recent_highs.values}")
    
    # Check if price near resistance
    current_price = df['close'].iloc[-1]
    max_high = df['high'].iloc[-20:].max()
    distance_to_high = ((max_high - current_price) / current_price) * 100
    
    logger.info(f"   Current price: ${current_price:,.2f}")
    logger.info(f"   Recent high: ${max_high:,.2f}")
    logger.info(f"   Distance to high: {distance_to_high:.2f}%")
    
    if distance_to_high < 2:
        logger.info(f"   ✅ Price IS near resistance - good for SELL on retrace!")
    else:
        logger.info(f"   ⚠️ Price NOT yet at ideal resistance zone")

mt5.shutdown()
