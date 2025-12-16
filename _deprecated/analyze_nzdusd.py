"""
Analyze NZDUSD to understand the setup
"""
from daily_scanner import MT5DataProvider
from smc_detector import SMCDetector
from loguru import logger

data_provider = MT5DataProvider()
smc_detector = SMCDetector()

if data_provider.connect():
    logger.info("🔍 Analyzing NZDUSD...")
    
    df_daily = data_provider.get_historical_data("NZDUSD", "D1", 100)
    df_4h = data_provider.get_historical_data("NZDUSD", "H4", 200)
    
    # Daily CHoCH
    daily_chochs = smc_detector.detect_choch(df_daily)
    latest_choch = daily_chochs[-1]
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 DAILY ANALYSIS")
    logger.info(f"{'='*60}")
    logger.info(f"🎯 Trend: {latest_choch.direction.upper()}")
    logger.info(f"📍 CHoCH @ {latest_choch.break_price:.5f} (index {latest_choch.index})")
    logger.info(f"📅 Time: {latest_choch.candle_time}")
    
    # Recent swing structure
    swing_highs = smc_detector.detect_swing_highs(df_daily)
    swing_lows = smc_detector.detect_swing_lows(df_daily)
    
    logger.info(f"\n📈 Recent Highs (last 5):")
    for sh in swing_highs[-5:]:
        logger.info(f"   {sh.price:.5f} @ {sh.candle_time}")
    
    logger.info(f"\n📉 Recent Lows (last 5):")
    for sl in swing_lows[-5:]:
        logger.info(f"   {sl.price:.5f} @ {sl.candle_time}")
    
    # FVG after CHoCH
    current_price = df_daily['close'].iloc[-1]
    fvg = smc_detector.detect_fvg(df_daily, latest_choch, current_price)
    
    if fvg:
        logger.info(f"\n💎 FVG DETECTED:")
        logger.info(f"   Zone: {fvg.bottom:.5f} - {fvg.top:.5f}")
        logger.info(f"   Direction: {fvg.direction.upper()}")
        logger.info(f"   Current Price: {current_price:.5f}")
        
        if smc_detector.is_price_in_fvg(current_price, fvg):
            logger.info(f"   ✅ Price IS in FVG!")
        else:
            logger.info(f"   ⏳ Price NOT in FVG yet")
    else:
        logger.info(f"\n❌ No FVG found")
    
    # 4H CHoCHs
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 4H ANALYSIS (looking for entry)")
    logger.info(f"{'='*60}")
    
    h4_chochs = smc_detector.detect_choch(df_4h)
    logger.info(f"🔄 Recent 4H CHoCHs (last 5):")
    for choch in h4_chochs[-5:]:
        h4_price = df_4h['close'].iloc[choch.index]
        in_fvg = "🎯 IN FVG" if fvg and smc_detector.is_price_in_fvg(h4_price, fvg) else ""
        logger.info(f"   {choch.direction.upper()} @ {choch.break_price:.5f} (index {choch.index}) {in_fvg}")
    
    logger.info(f"{'='*60}\n")
    
    data_provider.disconnect()
