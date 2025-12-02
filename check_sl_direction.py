"""
Check BTCUSD 4H CHoCH direction
"""

from daily_scanner import MT5DataProvider
from smc_detector import SMCDetector
from loguru import logger

data_provider = MT5DataProvider()
detector = SMCDetector()

if not data_provider.connect():
    exit()

df_daily = data_provider.get_historical_data("BTCUSD", "D1", 50)
df_4h = data_provider.get_historical_data("BTCUSD", "H4", 200)

setup = detector.scan_for_setup("BTCUSD", df_daily, df_4h, priority=1)

if setup:
    logger.info(f"✅ Setup found!")
    logger.info(f"   Daily CHoCH: {setup.daily_choch.direction.upper()}")
    logger.info(f"   4H CHoCH: {setup.h4_choch.direction.upper()}")
    logger.info(f"   Strategy Type: {setup.strategy_type.upper()}")
    logger.info(f"   Entry: {setup.entry_price:.2f}")
    logger.info(f"   SL: {setup.stop_loss:.2f}")
    logger.info(f"   TP: {setup.take_profit:.2f}")
    logger.info(f"\n   🔍 For SHORT trade, SL should be ABOVE entry!")
    logger.info(f"   ❌ Current SL ({setup.stop_loss:.2f}) is {'BELOW' if setup.stop_loss < setup.entry_price else 'ABOVE'} entry ({setup.entry_price:.2f})")
else:
    logger.error("❌ No setup found")

data_provider.disconnect()
