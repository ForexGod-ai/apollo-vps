"""
TradingView Screenshot Helper - ForexGod
Simple solution: Takes screenshot of your TradingView window exactly as you see it
"""

import subprocess
import time
import os
from typing import Optional


def capture_tradingview_window() -> Optional[bytes]:
    """
    Capture screenshot of TradingView application window
    Returns PNG bytes
    """
    try:
        # Activate TradingView
        subprocess.run(['osascript', '-e', 'tell application "TradingView" to activate'], check=True)
        time.sleep(0.2)
        
        # Take screenshot interactively (user presses Space or Click to capture window)
        temp_file = "/tmp/tradingview_screenshot.png"
        
        # Use screencapture with -w flag (captures selected window)
        print("📸 Taking screenshot of TradingView window...")
        subprocess.run(['screencapture', '-o', '-w', temp_file], check=True)
        
        if os.path.exists(temp_file):
            with open(temp_file, 'rb') as f:
                data = f.read()
            os.remove(temp_file)
            print(f"✅ Captured: {len(data):,} bytes")
            return data
        
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


if __name__ == "__main__":
    print("Testing...")
    img = capture_tradingview_window()
    if img:
        with open("test_native.png", "wb") as f:
            f.write(img)
        print("Saved to test_native.png")
