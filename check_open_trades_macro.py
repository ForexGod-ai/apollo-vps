"""
Check if open trades still match MACRO STRUCTURE
"""
from daily_scanner import MT5DataProvider
from smc_detector import SMCDetector
from loguru import logger

data_provider = MT5DataProvider()
smc_detector = SMCDetector()

if data_provider.connect():
    
    # Check BTCUSD (have SELL)
    logger.info("🔍 Checking BTCUSD SELL trades...")
    df_daily = data_provider.get_historical_data("BTCUSD", "D1", 100)
    chochs = smc_detector.detect_choch(df_daily)
    
    if chochs:
        latest = chochs[-1]
        logger.info(f"   BTCUSD Trend: {latest.direction.upper()}")
        logger.info(f"   SELL trades: {'✅ CORRECT' if latest.direction == 'bearish' else '❌ WRONG'}")
    
    # Check GBPCHF (have SELL)
    logger.info("\n🔍 Checking GBPCHF SELL trade...")
    df_daily = data_provider.get_historical_data("GBPCHF", "D1", 100)
    chochs = smc_detector.detect_choch(df_daily)
    
    if chochs:
        latest = chochs[-1]
        logger.info(f"   GBPCHF Trend: {latest.direction.upper()}")
        logger.info(f"   SELL trade: {'✅ CORRECT' if latest.direction == 'bearish' else '❌ WRONG'}")
    
    # Check AUDNZD (have BUY)
    logger.info("\n🔍 Checking AUDNZD BUY trade...")
    df_daily = data_provider.get_historical_data("AUDNZD", "D1", 100)
    chochs = smc_detector.detect_choch(df_daily)
    
    if chochs:
        latest = chochs[-1]
        logger.info(f"   AUDNZD Trend: {latest.direction.upper()}")
        logger.info(f"   BUY trade: {'✅ CORRECT' if latest.direction == 'bullish' else '❌ WRONG'}")
    
    data_provider.disconnect()
