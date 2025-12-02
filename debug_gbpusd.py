"""
Debug GBPUSD setup - check if direction is correct
"""
from daily_scanner import MT5DataProvider
from smc_detector import SMCDetector
from loguru import logger

logger.info("🔍 Analyzing GBPUSD setup...")

# Initialize
data_provider = MT5DataProvider()
smc_detector = SMCDetector()

if data_provider.connect():
    # Get data
    df_daily = data_provider.get_historical_data("GBPUSD", "D1", 100)
    df_4h = data_provider.get_historical_data("GBPUSD", "H4", 200)
    
    logger.info(f"\n📊 GBPUSD Daily - Last 10 candles:")
    for i in range(-10, 0):
        candle = df_daily.iloc[i]
        logger.info(f"   {candle['time']} | O: {candle['open']:.5f} H: {candle['high']:.5f} L: {candle['low']:.5f} C: {candle['close']:.5f}")
    
    # Detect CHoCH
    chochs = smc_detector.detect_choch(df_daily)
    
    if chochs:
        last_choch = chochs[-1]
        logger.info(f"\n🎯 Last Daily CHoCH:")
        logger.info(f"   • Direction: {last_choch.direction.upper()}")
        logger.info(f"   • Time: {last_choch.candle_time}")
        logger.info(f"   • Break Price: {last_choch.break_price:.5f}")
        
        # Check current price vs CHoCH
        current_price = df_daily['close'].iloc[-1]
        logger.info(f"\n💰 Current Price: {current_price:.5f}")
        
        if last_choch.direction == 'bearish':
            logger.info(f"   ⬇️ BEARISH CHoCH - Price broke structure DOWN")
        else:
            logger.info(f"   ⬆️ BULLISH CHoCH - Price broke structure UP")
    
    # Check FVG
    fvg = smc_detector.detect_fvg(df_daily, chochs[-1] if chochs else None)
    
    if fvg:
        logger.info(f"\n📦 FVG Detected:")
        logger.info(f"   • Direction: {fvg.direction.upper()}")
        logger.info(f"   • Top: {fvg.top:.5f}")
        logger.info(f"   • Bottom: {fvg.bottom:.5f}")
        logger.info(f"   • Middle: {fvg.middle:.5f}")
        logger.info(f"   • Time: {fvg.candle_time}")
    
    # Run full setup detection
    setup = smc_detector.scan_for_setup("GBPUSD", df_daily, df_4h, priority=1)
    
    if setup:
        logger.info(f"\n🎯 SETUP DETECTED:")
        logger.info(f"   • Daily CHoCH: {setup.daily_choch.direction.upper()}")
        logger.info(f"   • FVG: {setup.fvg.direction.upper()}")
        logger.info(f"   • 4H CHoCH: {setup.h4_choch.direction.upper()}")
        logger.info(f"   • Strategy: {setup.strategy_type.upper()}")
        logger.info(f"   • Entry: {setup.entry_price:.5f}")
        logger.info(f"   • SL: {setup.stop_loss:.5f}")
        logger.info(f"   • TP: {setup.take_profit:.5f}")
        
        # Expected trade direction
        if setup.daily_choch.direction == 'bearish':
            logger.info(f"\n   ⚠️ Daily is BEARISH - Should be SHORT trade!")
            if setup.entry_price > setup.stop_loss:
                logger.error(f"   ❌ ERROR: Entry above SL for BEARISH setup!")
        else:
            logger.info(f"\n   ✅ Daily is BULLISH - Should be LONG trade")
            if setup.entry_price < setup.stop_loss:
                logger.error(f"   ❌ ERROR: Entry below SL for BULLISH setup!")
    else:
        logger.warning("⚠️ No setup detected")
    
    data_provider.disconnect()
else:
    logger.error("❌ Failed to connect to MT5")
