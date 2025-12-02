"""
BTCUSD Detailed Structure Analysis - Looking for SELL setup on retrace
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from loguru import logger

# Initialize MT5
if not mt5.initialize():
    logger.error("MT5 initialization failed")
    exit()

# Get BTCUSD data
symbol = "BTCUSD"
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 100)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

logger.info(f"\n{'='*80}")
logger.info(f"🔍 BTCUSD DETAILED STRUCTURE ANALYSIS")
logger.info(f"{'='*80}")

# Current price action
current_price = df['close'].iloc[-1]
prev_close = df['close'].iloc[-2]
logger.info(f"\n📊 CURRENT STATE:")
logger.info(f"   Current Close: ${current_price:,.2f}")
logger.info(f"   Previous Close: ${prev_close:,.2f}")
logger.info(f"   Today's Range: ${df['low'].iloc[-1]:,.2f} - ${df['high'].iloc[-1]:,.2f}")

# Find swing highs and lows (last 30 bars)
def find_swing_highs(df, window=2):
    highs = []
    for i in range(window, len(df) - window):
        if df['high'].iloc[i] == df['high'].iloc[i-window:i+window+1].max():
            highs.append((i, df['high'].iloc[i], df['time'].iloc[i]))
    return highs

def find_swing_lows(df, window=2):
    lows = []
    for i in range(window, len(df) - window):
        if df['low'].iloc[i] == df['low'].iloc[i-window:i+window+1].min():
            lows.append((i, df['low'].iloc[i], df['time'].iloc[i]))
    return lows

swing_highs = find_swing_highs(df.iloc[-30:])
swing_lows = find_swing_lows(df.iloc[-30:])

logger.info(f"\n📈 RECENT SWING HIGHS (Last 30 bars):")
for i, (idx, price, time) in enumerate(swing_highs[-5:], 1):
    logger.info(f"   {i}. ${price:,.2f} on {time.strftime('%Y-%m-%d')}")

logger.info(f"\n📉 RECENT SWING LOWS (Last 30 bars):")
for i, (idx, price, time) in enumerate(swing_lows[-5:], 1):
    logger.info(f"   {i}. ${price:,.2f} on {time.strftime('%Y-%m-%d')}")

# Check for Lower Highs pattern (bearish)
if len(swing_highs) >= 2:
    last_high = swing_highs[-1][1]
    prev_high = swing_highs[-2][1]
    logger.info(f"\n🔍 MARKET STRUCTURE:")
    if last_high < prev_high:
        logger.info(f"   ✅ LOWER HIGH detected: ${last_high:,.2f} < ${prev_high:,.2f}")
        logger.info(f"   → BEARISH structure confirmed!")
    else:
        logger.info(f"   ⚠️ HIGHER HIGH: ${last_high:,.2f} > ${prev_high:,.2f}")
        logger.info(f"   → Still in uptrend or consolidating")

# Check for potential resistance zones
logger.info(f"\n🚧 KEY RESISTANCE ZONES:")
resistance_levels = []

# Recent highs as resistance
for i, (idx, price, time) in enumerate(swing_highs[-3:], 1):
    distance = ((price - current_price) / current_price) * 100
    resistance_levels.append((price, distance))
    logger.info(f"   R{i}: ${price:,.2f} (+{distance:.2f}% from current)")

# Find FVG zones (Fair Value Gaps) - potential resistance
logger.info(f"\n📊 FAIR VALUE GAPS (potential resistance):")
fvg_found = False
for i in range(len(df) - 3, max(len(df) - 30, 0), -1):
    # Bullish FVG: gap up (previous low > next high)
    if df['low'].iloc[i-1] > df['high'].iloc[i+1]:
        gap_top = df['low'].iloc[i-1]
        gap_bottom = df['high'].iloc[i+1]
        distance = ((gap_bottom - current_price) / current_price) * 100
        if abs(distance) < 20:  # Within 20% of current price
            logger.info(f"   Bullish FVG: ${gap_bottom:,.2f} - ${gap_top:,.2f} ({distance:+.2f}%)")
            fvg_found = True

if not fvg_found:
    logger.info(f"   No significant FVG zones near current price")

# Best SELL zone recommendation
logger.info(f"\n🎯 FOREXGOD'S SETUP:")
if resistance_levels:
    best_resistance = min(resistance_levels, key=lambda x: abs(x[1]))
    if best_resistance[1] > 0 and best_resistance[1] < 10:
        logger.info(f"   ✅ IDEAL SELL ZONE: ${best_resistance[0]:,.2f}")
        logger.info(f"   📍 Wait for retrace to +{best_resistance[1]:.2f}%")
        logger.info(f"   🎯 Entry strategy: Look for rejection/bearish patterns at resistance")
        logger.info(f"   💡 Watch for: Bearish engulfing, pinbar, or CHoCH bearish")
    elif best_resistance[1] > 10:
        logger.info(f"   ⚠️ Nearest resistance is ${best_resistance[0]:,.2f} (+{best_resistance[1]:.2f}%)")
        logger.info(f"   → Price needs significant move up first")
        logger.info(f"   💡 Alternative: Watch for lower timeframe structure breaks")
    else:
        logger.info(f"   ⚠️ Price already above key resistance")
        logger.info(f"   💡 Wait for clear rejection or new lower high formation")

mt5.shutdown()
