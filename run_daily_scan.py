"""
Daily Scanner Runner - Runs automatically via Task Scheduler

This script:
1. Scans all 18 pairs for setups
2. Sends Telegram alerts for found setups
3. Logs results to file
"""

import sys
import os
from datetime import datetime
from loguru import logger
from daily_scanner import DailyScanner

# Configure logging to file
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f"scanner_{datetime.now().strftime('%Y%m%d')}.log")
logger.add(log_file, rotation="1 day", retention="30 days", level="INFO")

def run_daily_scan():
    """Run the daily scanner"""
    logger.info("=" * 80)
    logger.info(f"🚀 DAILY SCANNER STARTED - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    try:
        scanner = DailyScanner()
        setups = scanner.run_daily_scan()
        
        logger.info(f"\n✅ Scan completed successfully!")
        logger.info(f"📊 Total setups found: {len(setups)}")
        
        if setups:
            logger.info(f"\n🎯 Setups detected:")
            for setup in setups:
                logger.info(f"   • {setup.symbol} {setup.daily_choch.direction.upper()} - R:R 1:{setup.risk_reward:.2f} ({setup.strategy_type.upper()})")
        else:
            logger.info(f"\n⚪ No setups found today")
        
        logger.info(f"\n{'=' * 80}")
        logger.info("✅ DAILY SCANNER COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Scanner failed with error: {e}")
        logger.exception("Full error traceback:")
        sys.exit(1)

if __name__ == "__main__":
    run_daily_scan()
