"""
TradingView Native Screenshot - ForexGod
Takes screenshots directly from your TradingView app
Preserves your custom layouts, indicators, and branding!
"""

import subprocess
import time
from typing import Optional
import os


class TradingViewNativeScreenshot:
    """Capture screenshots from native TradingView app"""
    
    def __init__(self):
        """Check if TradingView app is running"""
        self.app_name = "TradingView"
        self._ensure_tradingview_running()
    
    def _ensure_tradingview_running(self):
        """Check if TradingView is running"""
        result = subprocess.run(
            ['osascript', '-e', 'tell application "System Events" to get name of (processes where name is "TradingView")'],
            capture_output=True,
            text=True
        )
        
        if "TradingView" not in result.stdout:
            print("⚠️  TradingView app not running. Please open it first.")
        else:
            print("✅ TradingView app detected!")
    
    def get_chart_screenshot(
        self, 
        symbol: str, 
        timeframe: str = "D"
    ) -> Optional[bytes]:
        """
        Get screenshot from TradingView app window
        
        Args:
            symbol: Trading pair (for logging)
            timeframe: Timeframe (for reference)
        
        Returns:
            PNG image bytes or None
        """
        try:
            print(f"📊 Capturing TradingView window (current chart: {symbol})...")
            
            # Activate TradingView
            subprocess.run(['osascript', '-e', 'tell application "TradingView" to activate'], check=True)
            time.sleep(0.3)
            
            # Get window bounds
            bounds_script = '''
            tell application "System Events"
                tell process "TradingView"
                    set winPos to position of window 1
                    set winSize to size of window 1
                    return (item 1 of winPos) & "," & (item 2 of winPos) & "," & (item 1 of winSize) & "," & (item 2 of winSize)
                end tell
            end tell
            '''
            
            result = subprocess.run(['osascript', '-e', bounds_script], capture_output=True, text=True, check=True)
            bounds = result.stdout.strip().split(',')
            
            if len(bounds) == 4:
                x, y, width, height = map(int, bounds)
                
                # Take screenshot of that region
                temp_file = f"/tmp/tradingview_{symbol}.png"
                subprocess.run([
                    'screencapture',
                    '-R', f'{x},{y},{width},{height}',
                    temp_file
                ], check=True)
                
                # Read screenshot
                if os.path.exists(temp_file):
                    with open(temp_file, 'rb') as f:
                        screenshot = f.read()
                    os.remove(temp_file)
                    
                    print(f"✅ Screenshot captured: {len(screenshot):,} bytes")
                    return screenshot
            
            print("❌ Could not get window bounds")
            return None
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def close(self):
        """Cleanup - nothing to do for native app"""
        pass


# Quick test
if __name__ == "__main__":
    print("🧪 Testing TradingView Native Screenshot...")
    print("="*80)
    
    screenshotter = TradingViewNativeScreenshot()
    
    # Test with BTCUSD
    screenshot = screenshotter.get_chart_screenshot("BTCUSD", "D")
    
    if screenshot:
        with open("tradingview_native_test.png", "wb") as f:
            f.write(screenshot)
        print(f"✅ Screenshot saved: tradingview_native_test.png ({len(screenshot):,} bytes)")
    else:
        print("❌ Failed to capture screenshot")
    
    screenshotter.close()
