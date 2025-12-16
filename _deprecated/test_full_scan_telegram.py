"""
FULL SCAN TEST - Trading View Data + Telegram Notification
Test complet pentru strategia Glitch in Matrix
"""

import os
import sys
from datetime import datetime
from loguru import logger
from morning_strategy_scan import MorningStrategyScanner

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}", level="INFO")

def main():
    logger.info("="*70)
    logger.info("🚀 STARTING FULL MORNING SCAN - LIVE TRADING VIEW DATA")
    logger.info(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*70)
    
    # Create scanner
    scanner = MorningStrategyScanner()
    
    # Run full scan
    results = scanner.run_scan()
    
    # Print summary
    logger.info("\n" + "="*70)
    logger.info("📊 SCAN SUMMARY:")
    logger.info("="*70)
    
    reversal_setups = results['reversal_setups']
    continuation_setups = results['continuity_setups']
    no_setup = results['no_setup_pairs']
    
    logger.info(f"🔴 REVERSAL Setups: {len(reversal_setups)}")
    for setup in reversal_setups:
        logger.info(f"   • {setup.symbol}: {setup.setup.daily_choch.direction.upper()} @ {setup.setup.entry_price:.5f} (R:R 1:{setup.setup.risk_reward:.2f})")
    
    logger.info(f"\n🟢 CONTINUATION Setups: {len(continuation_setups)}")
    for setup in continuation_setups:
        logger.info(f"   • {setup.symbol}: {setup.setup.daily_choch.direction.upper()} @ {setup.setup.entry_price:.5f} (R:R 1:{setup.setup.risk_reward:.2f})")
    
    logger.info(f"\n⚪ No Setup: {len(no_setup)}")
    
    # Calculate total
    total_setups = len(reversal_setups) + len(continuation_setups)
    
    logger.info("\n" + "="*70)
    logger.info(f"✅ Total Setups Found: {total_setups}")
    logger.info("="*70)
    
    # Check if we have at least 2 setups
    if total_setups >= 2:
        logger.success(f"✅ SUCCESS! Found {total_setups} setups - sending to Telegram...")
        
        # Send to Telegram
        scanner.send_telegram_report(results)
        
        return True
    else:
        logger.warning(f"⚠️  Only {total_setups} setup(s) found")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
