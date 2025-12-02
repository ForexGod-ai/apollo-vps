"""
START MONITOR - ForexGod Trading AI
Pornește monitorizarea pentru:
1. BTC Alert ($89k zone)
2. Real-time scanner pentru toate perechile (REVERSAL + CONTINUATION)
"""

import subprocess
import sys
import time
from loguru import logger

logger.info("🚀 Starting ForexGod Trading Monitor...")
logger.info("="*80)

processes = []

# 1. Start Morning Scanner (runs once daily at 09:00)
logger.info("📊 Morning Scanner: Configured to run daily at 09:00")
logger.info("   Use: python3 morning_strategy_scan.py (manual)")

# 2. Start Real-Time Monitor for all pairs
logger.info("\n🔄 Starting Real-Time Monitor...")
logger.info("   • Scans: ALL PAIRS every 15 minutes")
logger.info("   • Strategy: REVERSAL + CONTINUATION")
logger.info("   • Alerts: Telegram when setup READY")

try:
    # Define symbols to monitor
    symbols = [
        'GBPUSD', 'EURUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD',
        'NZDUSD', 'EURJPY', 'GBPJPY', 'EURGBP', 'EURCAD', 'AUDCAD',
        'AUDNZD', 'NZDCAD', 'GBPNZD', 'GBPCHF', 'CADCHF',
        'XAUUSD', 'BTCUSD', 'USOIL'
    ]
    
    logger.info(f"\n📍 Monitoring {len(symbols)} symbols:")
    for i, sym in enumerate(symbols, 1):
        logger.info(f"   {i:2d}. {sym}")
    
    logger.info("\n" + "="*80)
    logger.info("✅ MONITOR ACTIVE - Press Ctrl+C to stop")
    logger.info("="*80)
    
    # Simple loop that runs morning scanner
    from morning_strategy_scan import MorningStrategyScanner
    
    scanner = MorningStrategyScanner()
    
    iteration = 0
    while True:
        iteration += 1
        logger.info(f"\n\n🔍 SCAN #{iteration} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)
        
        # Run scan
        summary = scanner.run_scan()
        
        # Send Telegram report
        scanner.send_telegram_report(summary)
        
        # Wait 1 hour before next scan
        logger.info("\n💤 Waiting 60 minutes until next scan...")
        time.sleep(3600)

except KeyboardInterrupt:
    logger.info("\n\n⚠️  Monitor stopped by user")
    sys.exit(0)
except Exception as e:
    logger.error(f"\n\n❌ Monitor error: {e}")
    sys.exit(1)
