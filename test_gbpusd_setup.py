"""
Test real GBPUSD setup detection with correct TP/SL
"""
import sys
from loguru import logger
from daily_scanner import DailyScanner

logger.remove()
logger.add(sys.stdout, colorize=True, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")


def test_gbpusd_setup():
    logger.info("=" * 80)
    logger.info("🧪 Testing GBPUSD Setup Detection")
    logger.info("=" * 80)
    
    scanner = DailyScanner()
    
    if not scanner.data_provider.connect():
        logger.error("❌ Failed to connect to MT5")
        return
    
    symbol = "GBPUSD"
    logger.info(f"\n📊 Scanning {symbol}...")
    
    # Get data
    df_daily = scanner.data_provider.get_historical_data(symbol, "D1", 50)
    df_4h = scanner.data_provider.get_historical_data(symbol, "H4", 200)
    
    # Scan for setup
    setup = scanner.smc_detector.scan_for_setup(
        symbol=symbol,
        df_daily=df_daily,
        df_4h=df_4h,
        priority=1
    )
    
    if setup:
        logger.info("\n🎯 SETUP FOUND!")
        logger.info(f"\n📊 Daily Context:")
        logger.info(f"   CHoCH: {setup.daily_choch.direction.upper()}")
        logger.info(f"   FVG: {setup.fvg.direction.upper()} ({setup.fvg.bottom:.5f} - {setup.fvg.top:.5f})")
        
        logger.info(f"\n🔍 4H Confirmation:")
        logger.info(f"   CHoCH: {setup.h4_choch.direction.upper()}")
        
        trade_direction = "LONG" if setup.h4_choch.direction == 'bullish' else "SHORT"
        logger.info(f"\n{'🟢' if trade_direction == 'LONG' else '🔴'} TRADE DIRECTION: {trade_direction}")
        
        logger.info(f"\n📍 EXECUTION PLAN:")
        logger.info(f"   Entry: {setup.entry_price:.5f}")
        logger.info(f"   Stop Loss: {setup.stop_loss:.5f}")
        logger.info(f"   Take Profit: {setup.take_profit:.5f}")
        
        # Calculate pips
        if trade_direction == "LONG":
            sl_pips = abs(setup.entry_price - setup.stop_loss) * 10000
            tp_pips = abs(setup.take_profit - setup.entry_price) * 10000
        else:
            sl_pips = abs(setup.stop_loss - setup.entry_price) * 10000
            tp_pips = abs(setup.entry_price - setup.take_profit) * 10000
        
        rr = tp_pips / sl_pips if sl_pips > 0 else 0
        
        logger.info(f"\n📊 RISK ANALYSIS:")
        logger.info(f"   SL Distance: {sl_pips:.1f} pips")
        logger.info(f"   TP Distance: {tp_pips:.1f} pips")
        logger.info(f"   Risk:Reward: 1:{rr:.2f}")
        logger.info(f"   Priority: {setup.priority}")
        
        if rr < 1.5:
            logger.warning(f"\n⚠️ R:R is below 1.5! This setup might not be valid.")
        else:
            logger.info(f"\n✅ Good Risk:Reward ratio!")
        
    else:
        logger.warning("\n⚠️ No setup detected for GBPUSD")
        logger.info("\nPossible reasons:")
        logger.info("- No Daily CHoCH")
        logger.info("- No FVG after CHoCH")
        logger.info("- Price not in FVG zone")
        logger.info("- No opposite 4H CHoCH inside FVG")
        logger.info("- R:R below minimum threshold")
    
    scanner.data_provider.disconnect()
    logger.info("\n" + "=" * 80)


if __name__ == "__main__":
    test_gbpusd_setup()
