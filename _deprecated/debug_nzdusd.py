"""Debug why NZDUSD not detected"""
from daily_scanner import MT5DataProvider
from smc_detector import SMCDetector
from loguru import logger

data_provider = MT5DataProvider()
smc_detector = SMCDetector()

if data_provider.connect():
    logger.info("🔍 Debugging NZDUSD detection...")
    
    df_daily = data_provider.get_historical_data("NZDUSD", "D1", 100)
    df_4h = data_provider.get_historical_data("NZDUSD", "H4", 200)
    
    # Check CHoCH detection
    chochs = smc_detector.detect_choch(df_daily)
    
    logger.info(f"\n📊 CHoCHs detected: {len(chochs)}")
    for choch in chochs[-3:]:
        logger.info(f"   {choch.direction.upper()} @ {choch.break_price:.5f} (index {choch.index})")
    
    if chochs:
        latest = chochs[-1]
        logger.info(f"\n🎯 Latest CHoCH: {latest.direction.upper()}")
        
        # Try to get FVG
        current_price = df_daily['close'].iloc[-1]
        fvg = smc_detector.detect_fvg(df_daily, latest, current_price)
        
        if fvg:
            logger.info(f"\n💎 FVG found: {fvg.bottom:.5f} - {fvg.top:.5f}")
            logger.info(f"   Current price: {current_price:.5f}")
            logger.info(f"   Price in FVG: {smc_detector.is_price_in_fvg(current_price, fvg)}")
        else:
            logger.info(f"\n❌ No FVG detected!")
    else:
        logger.info(f"\n❌ No CHoCH detected!")
        
        # Check swing structure
        swing_highs = smc_detector.detect_swing_highs(df_daily)
        swing_lows = smc_detector.detect_swing_lows(df_daily)
        
        logger.info(f"\n📈 Last 5 Swing Highs:")
        for sh in swing_highs[-5:]:
            logger.info(f"   {sh.price:.5f} @ {sh.candle_time}")
        
        logger.info(f"\n📉 Last 5 Swing Lows:")
        for sl in swing_lows[-5:]:
            logger.info(f"   {sl.price:.5f} @ {sl.candle_time}")
    
    # Try scan
    logger.info(f"\n{'='*60}")
    logger.info(f"🔍 Attempting scan_for_setup...")
    logger.info(f"{'='*60}")
    
    setup = smc_detector.scan_for_setup("NZDUSD", df_daily, df_4h, priority=1)
    
    if setup:
        logger.info(f"✅ SETUP FOUND!")
        logger.info(f"   Status: {setup.status}")
    else:
        logger.info(f"❌ NO SETUP RETURNED - checking why...")
    
    data_provider.disconnect()
