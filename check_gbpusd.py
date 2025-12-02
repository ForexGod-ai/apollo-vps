"""Check GBPUSD setup - should be BEARISH not LONG"""
from daily_scanner import MT5DataProvider
from smc_detector import SMCDetector
from loguru import logger

data_provider = MT5DataProvider()
smc_detector = SMCDetector()

if data_provider.connect():
    logger.info("🔍 Analyzing GBPUSD...")
    
    df_daily = data_provider.get_historical_data("GBPUSD", "D1", 100)
    
    # Check all CHoCHs
    chochs = smc_detector.detect_choch(df_daily)
    
    logger.info(f"\n📊 ALL CHoCHs detected (last 10):")
    for choch in chochs[-10:]:
        logger.info(f"   {choch.direction.upper()} @ {choch.break_price:.5f} (index {choch.index}, {choch.candle_time})")
    
    logger.info(f"\n🎯 LATEST CHoCH:")
    latest = chochs[-1]
    logger.info(f"   Direction: {latest.direction.upper()}")
    logger.info(f"   Price: {latest.break_price:.5f}")
    logger.info(f"   Date: {latest.candle_time}")
    
    # Check swing structure
    swing_highs = smc_detector.detect_swing_highs(df_daily)
    swing_lows = smc_detector.detect_swing_lows(df_daily)
    
    logger.info(f"\n📈 Last 5 Swing Highs:")
    for sh in swing_highs[-5:]:
        logger.info(f"   {sh.price:.5f} @ {sh.candle_time}")
    
    logger.info(f"\n📉 Last 5 Swing Lows:")
    for sl in swing_lows[-5:]:
        logger.info(f"   {sl.price:.5f} @ {sl.candle_time}")
    
    # Pattern analysis
    logger.info(f"\n🔍 PATTERN ANALYSIS:")
    recent_highs = swing_highs[-3:]
    if recent_highs[2].price < recent_highs[1].price < recent_highs[0].price:
        logger.info(f"   Highs: {recent_highs[0].price:.5f} → {recent_highs[1].price:.5f} → {recent_highs[2].price:.5f} = LOWER HIGHS ❌")
    
    recent_lows = swing_lows[-3:]
    if recent_lows[2].price < recent_lows[1].price < recent_lows[0].price:
        logger.info(f"   Lows: {recent_lows[0].price:.5f} → {recent_lows[1].price:.5f} → {recent_lows[2].price:.5f} = LOWER LOWS ❌")
    
    logger.info(f"\n   ⚠️ GBPUSD should be BEARISH, not BULLISH!")
    
    data_provider.disconnect()
