"""
Scan all 18 pairs for both REVERSAL and CONTINUATION setups
"""
import sys
from loguru import logger
from daily_scanner import DailyScanner
import json

logger.remove()
logger.add(sys.stdout, colorize=True, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")


def scan_all_pairs():
    logger.info("=" * 80)
    logger.info("🔍 SCANNING ALL 18 PAIRS FOR SETUPS")
    logger.info("=" * 80)
    
    scanner = DailyScanner()
    
    if not scanner.data_provider.connect():
        logger.error("❌ Failed to connect to MT5")
        return
    
    # Load pairs
    with open('pairs_config.json', 'r') as f:
        config = json.load(f)
    
    pairs = config['pairs']
    logger.info(f"\n📊 Scanning {len(pairs)} pairs...\n")
    
    setups_found = []
    
    for pair_config in pairs:
        symbol = pair_config['symbol']
        priority = pair_config['priority']
        
        logger.info(f"🔍 {symbol} (Priority {priority})...")
        
        try:
            # Get data
            df_daily = scanner.data_provider.get_historical_data(symbol, "D1", 50)
            df_4h = scanner.data_provider.get_historical_data(symbol, "H4", 200)
            
            if df_daily is None or df_4h is None:
                logger.warning(f"   ⚠️ Failed to get data for {symbol}")
                continue
            
            # Scan for setup
            setup = scanner.smc_detector.scan_for_setup(
                symbol=symbol,
                df_daily=df_daily,
                df_4h=df_4h,
                priority=priority
            )
            
            if setup:
                setups_found.append(setup)
                
                trade_dir = "LONG" if setup.h4_choch.direction == 'bullish' else "SHORT"
                strategy_icon = "🔥" if setup.strategy_type == 'reversal' else "🎯"
                
                logger.info(f"   ✅ {strategy_icon} SETUP FOUND!")
                logger.info(f"      Type: {setup.strategy_type.upper()}")
                logger.info(f"      Direction: {trade_dir}")
                logger.info(f"      Entry: {setup.entry_price:.5f}")
                logger.info(f"      R:R: 1:{setup.risk_reward:.2f}")
            else:
                logger.info(f"   ⚪ No setup")
        
        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 SCAN SUMMARY")
    logger.info("=" * 80)
    logger.info(f"\nTotal Setups Found: {len(setups_found)}")
    
    if setups_found:
        # Group by strategy type
        reversals = [s for s in setups_found if s.strategy_type == 'reversal']
        continuations = [s for s in setups_found if s.strategy_type == 'continuation']
        
        logger.info(f"\n🔥 REVERSAL Setups: {len(reversals)}")
        for setup in reversals:
            trade_dir = "LONG" if setup.h4_choch.direction == 'bullish' else "SHORT"
            logger.info(f"   • {setup.symbol} {trade_dir} - R:R 1:{setup.risk_reward:.2f} (Priority {setup.priority})")
        
        logger.info(f"\n🎯 CONTINUATION Setups: {len(continuations)}")
        for setup in continuations:
            trade_dir = "LONG" if setup.h4_choch.direction == 'bullish' else "SHORT"
            logger.info(f"   • {setup.symbol} {trade_dir} - R:R 1:{setup.risk_reward:.2f} (Priority {setup.priority})")
        
        # Sort by priority and R:R
        setups_found.sort(key=lambda x: (x.priority, -x.risk_reward))
        
        logger.info(f"\n⭐ TOP 3 SETUPS (by priority and R:R):")
        for i, setup in enumerate(setups_found[:3], 1):
            trade_dir = "LONG" if setup.h4_choch.direction == 'bullish' else "SHORT"
            strategy_icon = "🔥" if setup.strategy_type == 'reversal' else "🎯"
            logger.info(f"   {i}. {strategy_icon} {setup.symbol} {trade_dir} - R:R 1:{setup.risk_reward:.2f} ({setup.strategy_type.upper()})")
    else:
        logger.warning("\n⚠️ No setups found on any pair at this time")
        logger.info("\nThis is normal - valid setups don't appear every day!")
        logger.info("Scanner will run daily at 08:00 AM to catch new opportunities.")
    
    scanner.data_provider.disconnect()
    logger.info("\n" + "=" * 80)


if __name__ == "__main__":
    scan_all_pairs()
