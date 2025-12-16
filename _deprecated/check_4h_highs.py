"""
Check what 4H highs are being used for SL
"""

from daily_scanner import MT5DataProvider
from loguru import logger
import pandas as pd

data_provider = MT5DataProvider()

if not data_provider.connect():
    exit()

df_4h = data_provider.get_historical_data("BTCUSD", "H4", 200)

logger.info(f"📊 Last 20 4H candles HIGH values:")
recent_highs = df_4h['high'].iloc[-20:]
for i, high in enumerate(recent_highs):
    logger.info(f"   {i+1}. {high:.2f}")

logger.info(f"\n📈 MAX of last 20 4H highs: {recent_highs.max():.2f}")
logger.info(f"📈 MAX of last 50 4H highs: {df_4h['high'].iloc[-50:].max():.2f}")
logger.info(f"📈 MAX of ALL 200 4H highs: {df_4h['high'].max():.2f}")

data_provider.disconnect()
