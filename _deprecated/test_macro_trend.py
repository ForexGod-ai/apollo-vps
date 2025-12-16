"""
Test new MACRO TREND detection on GBPUSD
"""
from daily_scanner import MT5DataProvider
from smc_detector import SMCDetector
from loguru import logger

logger.info("🔍 Testing MACRO TREND detection on GBPUSD...")

# Initialize
data_provider = MT5DataProvider()
smc_detector = SMCDetector()

if data_provider.connect():
    # Get data
    df_daily = data_provider.get_historical_data("GBPUSD", "D1", 100)
    df_4h = data_provider.get_historical_data("GBPUSD", "H4", 200)
    
    # Test NEW CHoCH/BOS detection
    chochs = smc_detector.detect_choch(df_daily)
    
    if not chochs:
        logger.error("❌ No CHoCH detected!")
    else:
        latest_choch = chochs[-1]
        current_trend = latest_choch.direction
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 GBPUSD TREND ANALYSIS (CHoCH/BOS)")
        logger.info(f"{'='*60}")
        logger.info(f"🎯 Current Trend: {current_trend.upper()} (from latest CHoCH)")
        logger.info(f"📍 Latest CHoCH: {latest_choch.direction.upper()} at index {latest_choch.index}")
        logger.info(f"   Price: {latest_choch.break_price:.5f}")
        logger.info(f"   Time: {df_daily['time'].iloc[latest_choch.index]}")
        
        # Show recent CHoCHs
        logger.info(f"\n🔄 Recent CHoCHs (last 5):")
        for choch in chochs[-5:]:
            logger.info(f"   {choch.direction.upper()} @ {choch.break_price:.5f} (index {choch.index})")
    
    # Show swing structure
    swing_highs = smc_detector.detect_swing_highs(df_daily)
    swing_lows = smc_detector.detect_swing_lows(df_daily)
    
    logger.info(f"\n📈 Recent Swing Highs (last 5):")
    for sh in swing_highs[-5:]:
        logger.info(f"   {sh.candle_time} - {sh.price:.5f}")
    
    logger.info(f"\n📉 Recent Swing Lows (last 5):")
    for sl in swing_lows[-5:]:
        logger.info(f"   {sl.candle_time} - {sl.price:.5f}")
    
    # Check if setup exists with new logic
    setup = smc_detector.scan_for_setup("GBPUSD", df_daily, df_4h, priority=1)
    
    logger.info(f"\n{'='*60}")
    if setup:
        logger.info(f"✅ SETUP FOUND!")
        logger.info(f"   • Daily Direction (MACRO): {setup.daily_choch.direction.upper()}")
        logger.info(f"   • FVG Direction: {setup.fvg.direction.upper()}")
        logger.info(f"   • 4H CHoCH: {setup.h4_choch.direction.upper()}")
        logger.info(f"   • Trade Direction: {'BUY' if setup.daily_choch.direction == 'bullish' else 'SELL'}")
        logger.info(f"   • Entry: {setup.entry_price:.5f}")
        logger.info(f"   • SL: {setup.stop_loss:.5f}")
        logger.info(f"   • TP: {setup.take_profit:.5f}")
        logger.info(f"   • R:R: 1:{setup.risk_reward:.2f}")
        logger.info(f"   • Strategy: {setup.strategy_type.upper()}")
        
        # Verify direction correctness
        if current_trend == 'bearish':
            if setup.daily_choch.direction == 'bearish':
                logger.info(f"\n   ✅ CORRECT: Setup matches BEARISH current trend!")
            else:
                logger.error(f"\n   ❌ WRONG: Setup is BULLISH but current trend is BEARISH!")
        else:
            if setup.daily_choch.direction == 'bullish':
                logger.info(f"\n   ✅ CORRECT: Setup matches BULLISH current trend!")
            else:
                logger.error(f"\n   ❌ WRONG: Setup is BEARISH but current trend is BULLISH!")
                logger.error(f"\n   ❌ WRONG: Setup is BEARISH but current trend is BULLISH!")
    else:
        logger.warning(f"⚠️ No setup detected with new CHoCH/BOS logic")
        logger.info(f"   This could mean:")
        logger.info(f"   • Price not in FVG zone yet")
        logger.info(f"   • No 4H confirmation matching current trend")
        logger.info(f"   • Waiting for proper entry setup")
    
    logger.info(f"{'='*60}\n")
    
    data_provider.disconnect()
else:
    logger.error("❌ Failed to connect to MT5")
