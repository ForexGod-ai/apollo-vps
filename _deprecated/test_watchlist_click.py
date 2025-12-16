#!/usr/bin/env python3
"""
Test TradingView Watchlist Click Automation
Verifies that we can automatically click on symbols in Watchlist
"""

import sys
from loguru import logger
from tradingview_desktop_screenshot import TradingViewDesktopCapture

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}", level="INFO")

def test_watchlist_click():
    """Test clicking on a symbol in Watchlist"""
    
    print("\n" + "="*70)
    print("🧪 TEST: TradingView Watchlist Click Automation")
    print("="*70 + "\n")
    
    # Initialize capture
    capture = TradingViewDesktopCapture()
    
    # Check if TradingView is running
    if not capture.is_tradingview_running():
        logger.error("❌ TradingView Desktop is NOT running!")
        logger.info("💡 Please open TradingView Desktop first")
        return False
    
    logger.success("✅ TradingView Desktop is running")
    
    # Test symbols from your Watchlist
    test_symbols = ["BTCUSD", "GBPUSD", "XAUUSD"]
    
    print("\n📋 Will test clicking on these symbols:")
    for sym in test_symbols:
        print(f"   • {sym}")
    
    input("\n⏸️  Press ENTER when ready to start test (make sure Watchlist is visible)...")
    
    results = []
    
    for symbol in test_symbols:
        print(f"\n{'='*70}")
        logger.info(f"Testing: {symbol}")
        print("="*70)
        
        # Try to click on symbol in Watchlist
        success = capture.change_symbol(symbol)
        
        if success:
            logger.success(f"✅ Successfully clicked on {symbol}")
            results.append((symbol, True))
            
            # Try to capture screenshot
            output_path = f"/tmp/test_{symbol}.png"
            logger.info(f"📸 Capturing screenshot...")
            
            screenshot_ok = capture.capture_window(output_path)
            if screenshot_ok:
                logger.success(f"✅ Screenshot saved: {output_path}")
            else:
                logger.warning(f"⚠️  Screenshot failed for {symbol}")
        else:
            logger.error(f"❌ Failed to click on {symbol}")
            results.append((symbol, False))
        
        # Wait before next test
        import time
        time.sleep(2)
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST RESULTS")
    print("="*70 + "\n")
    
    success_count = sum(1 for _, success in results if success)
    total = len(results)
    
    for symbol, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {symbol:12} {status}")
    
    print(f"\n🎯 Success Rate: {success_count}/{total} ({success_count*100//total}%)")
    
    if success_count == total:
        print("\n🎉 ALL TESTS PASSED! Watchlist automation is working!")
        print("   Ready for morning scanner! 🚀")
    else:
        print(f"\n⚠️  Some tests failed. Check TradingView Watchlist visibility.")
    
    print("="*70 + "\n")
    
    return success_count == total

if __name__ == "__main__":
    success = test_watchlist_click()
    sys.exit(0 if success else 1)
