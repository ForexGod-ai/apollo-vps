"""
Check which candles closed above FVG top
"""

import MetaTrader5 as mt5
import pandas as pd
from loguru import logger

if not mt5.initialize():
    logger.error("MT5 init failed")
    exit()

symbol = "BTCUSD"
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 50)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

fvg_top = 88483.00
threshold = fvg_top * 1.002  # 88,660

logger.info(f"FVG Top: {fvg_top:.2f}")
logger.info(f"Fill Threshold (0.2% above): {threshold:.2f}")
logger.info(f"\n📊 Candles that CLOSED above {threshold:.2f}:")

found_fill = False
for i in range(len(df)):
    close = df['close'].iloc[i]
    if close > threshold:
        found_fill = True
        logger.info(f"\n   ✅ {df['time'].iloc[i]}")
        logger.info(f"      Close: {close:.2f} (above threshold by {close - threshold:.2f})")
        logger.info(f"      High: {df['high'].iloc[i]:.2f}")
        logger.info(f"      Low: {df['low'].iloc[i]:.2f}")

if not found_fill:
    logger.info(f"\n   ❌ NO candles closed above threshold!")
    logger.info(f"\n   Highest CLOSE:")
    max_close_idx = df['close'].argmax()
    logger.info(f"      {df['time'].iloc[max_close_idx]}")
    logger.info(f"      Close: {df['close'].iloc[max_close_idx]:.2f}")

mt5.shutdown()
