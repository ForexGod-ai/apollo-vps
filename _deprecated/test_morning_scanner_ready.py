#!/usr/bin/env python3
"""
Test if Morning Scanner is ready for tomorrow
"""
from morning_strategy_scan import MorningStrategyScanner
from loguru import logger
import sys

def test_scanner():
    logger.info("🧪 Testing Morning Scanner...")
    
    try:
        # Initialize scanner
        scanner = MorningStrategyScanner()
        logger.success(f"✅ Scanner initialized with {len(scanner.pairs_config)} pairs")
        
        # Test Telegram
        if scanner.telegram.test_connection():
            logger.success("✅ Telegram connection OK")
            
            # Send test message
            test_msg = """🧪 **MORNING SCANNER TEST**

Scanner is ready for tomorrow 09:00!

✅ System operational
📊 Will scan all pairs at market open
📱 Results sent to Telegram
🤖 Auto-execution enabled in cTrader"""
            
            scanner.telegram.send_message(test_msg)
            logger.success("✅ Test message sent to Telegram!")
            
        else:
            logger.error("❌ Telegram connection failed")
            return False
        
        # Check cTrader data client
        if scanner.ctrader_client:
            logger.success("✅ cTrader data client initialized")
        else:
            logger.warning("⚠️  cTrader client not available")
        
        logger.info(f"\n📋 Configured pairs: {len(scanner.pairs_config)}")
        for pair in scanner.pairs_config[:5]:
            logger.info(f"   • {pair['symbol']} (Priority {pair.get('priority', 2)})")
        if len(scanner.pairs_config) > 5:
            logger.info(f"   ... and {len(scanner.pairs_config) - 5} more")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Scanner test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_scanner()
    sys.exit(0 if success else 1)
