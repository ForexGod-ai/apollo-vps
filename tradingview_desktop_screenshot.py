"""
TradingView Desktop Screenshot - Captures charts directly from TradingView Desktop app
Uses macOS scripting to automate TradingView Desktop and capture screenshots
"""

import subprocess
import time
import os
from typing import Optional
from loguru import logger
import tempfile


class TradingViewDesktopCapture:
    """Capture charts directly from TradingView Desktop application"""
    
    def __init__(self):
        self.app_name = "TradingView"
        self.temp_dir = tempfile.gettempdir()
        
    def is_tradingview_running(self) -> bool:
        """Check if TradingView Desktop is running"""
        try:
            result = subprocess.run(
                ['pgrep', '-x', 'TradingView'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking TradingView: {e}")
            return False
    
    def launch_tradingview(self):
        """Launch TradingView Desktop application"""
        try:
            logger.info("🚀 Launching TradingView Desktop...")
            subprocess.run(['open', '-a', 'TradingView'], check=True)
            time.sleep(5)  # Wait for app to fully load
            return True
        except Exception as e:
            logger.error(f"Failed to launch TradingView: {e}")
            return False
    
    def focus_tradingview(self):
        """Bring TradingView to front"""
        applescript = '''
        tell application "TradingView"
            activate
        end tell
        '''
        try:
            subprocess.run(['osascript', '-e', applescript], check=True)
            time.sleep(1)
        except Exception as e:
            logger.error(f"Failed to focus TradingView: {e}")
    
    def change_symbol(self, symbol: str):
        """Change symbol in TradingView using keyboard shortcut"""
        applescript = f'''
        tell application "System Events"
            tell process "TradingView"
                -- Press Cmd+K to open symbol search
                keystroke "k" using command down
                delay 0.5
                
                -- Type symbol
                keystroke "{symbol}"
                delay 0.5
                
                -- Press Enter to load symbol
                key code 36
                delay 2
            end tell
        end tell
        '''
        try:
            subprocess.run(['osascript', '-e', applescript], check=True)
            logger.success(f"✅ Changed to symbol: {symbol}")
            time.sleep(2)  # Wait for chart to load
            return True
        except Exception as e:
            logger.error(f"Failed to change symbol: {e}")
            return False
    
    def change_timeframe(self, timeframe: str):
        """Change timeframe in TradingView"""
        # Map our timeframe to TradingView shortcuts
        timeframe_keys = {
            "1": "1",      # 1 minute
            "5": "5",      # 5 minutes
            "15": "15",    # 15 minutes
            "60": "H",     # 1 hour
            "240": "4H",   # 4 hours
            "D": "D",      # Daily
            "W": "W",      # Weekly
            "M": "M"       # Monthly
        }
        
        tf_key = timeframe_keys.get(timeframe, "D")
        
        applescript = f'''
        tell application "System Events"
            tell process "TradingView"
                -- Press , (comma) to open interval menu
                keystroke ","
                delay 0.3
                
                -- Type timeframe
                keystroke "{tf_key}"
                delay 0.5
                
                -- Press Enter
                key code 36
                delay 1.5
            end tell
        end tell
        '''
        try:
            subprocess.run(['osascript', '-e', applescript], check=True)
            logger.success(f"✅ Changed to timeframe: {timeframe}")
            return True
        except Exception as e:
            logger.error(f"Failed to change timeframe: {e}")
            return False
    
    def capture_window(self, output_path: str) -> bool:
        """Capture screenshot of TradingView window"""
        try:
            # Use screencapture with window selection
            # -l captures specific window, -o removes shadow
            applescript = '''
            tell application "TradingView"
                set windowID to id of front window
            end tell
            return windowID
            '''
            
            # Get window ID
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error("Failed to get window ID")
                # Fallback: capture entire screen and crop
                return self._capture_fullscreen(output_path)
            
            window_id = result.stdout.strip()
            
            # Capture window
            subprocess.run([
                'screencapture',
                '-l', window_id,
                '-o',  # No shadow
                '-x',  # No sound
                output_path
            ], check=True)
            
            logger.success(f"✅ Screenshot saved: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to capture window: {e}")
            return self._capture_fullscreen(output_path)
    
    def _capture_fullscreen(self, output_path: str) -> bool:
        """Fallback: Capture entire screen"""
        try:
            subprocess.run([
                'screencapture',
                '-x',  # No sound
                output_path
            ], check=True)
            logger.warning("⚠️  Captured fullscreen (fallback)")
            return True
        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return False
    
    def get_chart_screenshot(
        self,
        symbol: str,
        timeframe: str = "D",
        output_path: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Get chart screenshot from TradingView Desktop
        
        Args:
            symbol: Trading pair (GBPUSD, XAUUSD, etc.)
            timeframe: D, 240, 60, 15, etc.
            output_path: Where to save screenshot (optional)
        
        Returns:
            PNG image bytes or None
        """
        try:
            # Ensure TradingView is running
            if not self.is_tradingview_running():
                if not self.launch_tradingview():
                    logger.error("❌ Cannot launch TradingView")
                    return None
            
            # Focus TradingView
            self.focus_tradingview()
            
            # Change symbol
            if not self.change_symbol(symbol):
                logger.error(f"❌ Failed to load symbol: {symbol}")
                return None
            
            # Change timeframe
            if not self.change_timeframe(timeframe):
                logger.error(f"❌ Failed to set timeframe: {timeframe}")
                return None
            
            # Wait for chart to fully render
            time.sleep(2)
            
            # Capture screenshot
            if output_path is None:
                output_path = os.path.join(self.temp_dir, f"tv_{symbol}_{timeframe}.png")
            
            if not self.capture_window(output_path):
                return None
            
            # Read screenshot
            with open(output_path, 'rb') as f:
                screenshot_bytes = f.read()
            
            logger.success(f"✅ Captured {symbol} @ {timeframe}: {len(screenshot_bytes)} bytes")
            return screenshot_bytes
            
        except Exception as e:
            logger.error(f"❌ Error capturing chart: {e}")
            return None


def test_desktop_capture():
    """Test the desktop capture functionality"""
    logger.info("🧪 Testing TradingView Desktop Capture...")
    
    capture = TradingViewDesktopCapture()
    
    # Test capture
    screenshot = capture.get_chart_screenshot("GBPUSD", "D", "test_desktop_chart.png")
    
    if screenshot:
        logger.success(f"✅ Success! Screenshot: {len(screenshot)} bytes")
        logger.info("📁 Saved to: test_desktop_chart.png")
    else:
        logger.error("❌ Failed to capture chart")


if __name__ == "__main__":
    test_desktop_capture()
