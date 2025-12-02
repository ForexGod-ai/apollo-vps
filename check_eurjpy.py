"""Check EURJPY setup details"""
from daily_scanner import MT5DataProvider
from smc_detector import SMCDetector
from loguru import logger

data_provider = MT5DataProvider()
smc_detector = SMCDetector()

if data_provider.connect():
    logger.info("🔍 Analyzing EURJPY setup...")
    
    df_daily = data_provider.get_historical_data("EURJPY", "D1", 100)
    df_4h = data_provider.get_historical_data("EURJPY", "H4", 200)
    
    setup = smc_detector.scan_for_setup("EURJPY", df_daily, df_4h, priority=1)
    
    if setup:
        logger.info(f"\n✅ SETUP FOUND:")
        logger.info(f"   Daily CHoCH: {setup.daily_choch.direction.upper()}")
        logger.info(f"   FVG: {setup.fvg.bottom:.5f} - {setup.fvg.top:.5f}")
        logger.info(f"   4H CHoCH: {setup.h4_choch.direction.upper()}")
        logger.info(f"   Entry: {setup.entry_price:.5f}")
        logger.info(f"   SL: {setup.stop_loss:.5f}")
        logger.info(f"   TP: {setup.take_profit:.5f}")
        logger.info(f"   R:R: 1:{setup.risk_reward:.2f}")
        logger.info(f"   Strategy: {setup.strategy_type}")
    
    data_provider.disconnect()
