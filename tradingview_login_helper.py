"""
TradingView Manual Login Helper - ForexGod
Opens browser for manual login, then saves session for future use
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import os

def manual_login_and_save_session():
    """
    Opens Chrome with TradingView login page
    User logs in manually, script saves the session
    """
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # Use persistent profile to save login
    chrome_options.add_argument('--user-data-dir=/tmp/tradingview_chrome_profile')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    print("="*80)
    print("🔐 TRADINGVIEW MANUAL LOGIN")
    print("="*80)
    print("\n📝 Instructions:")
    print("1. Browser will open to TradingView login page")
    print("2. Login manually with your credentials:")
    print(f"   Email: {os.getenv('TRADINGVIEW_USERNAME', 'pocovnicu.razvan12@gmail.com')}")
    print("3. After successful login, press ENTER here in terminal")
    print("4. Session will be saved for future automated use\n")
    
    # Open TradingView
    driver.get("https://www.tradingview.com/")
    
    input("\n⏸️  Press ENTER after you've logged in manually in the browser... ")
    
    # Check current URL to confirm login
    current_url = driver.current_url
    print(f"\n📍 Current URL: {current_url}")
    
    # Take a test screenshot to verify
    try:
        driver.get("https://www.tradingview.com/chart/?symbol=BITSTAMP:BTCUSD&interval=D")
        time.sleep(5)
        screenshot = driver.get_screenshot_as_png()
        
        with open('test_logged_session.png', 'wb') as f:
            f.write(screenshot)
        
        print(f"✅ Test screenshot saved: test_logged_session.png ({len(screenshot):,} bytes)")
        print("✅ Session saved! Future scripts will use this logged-in session.")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n🎉 Setup complete! You can close this window.")
    input("\nPress ENTER to close browser...")
    
    driver.quit()

if __name__ == "__main__":
    manual_login_and_save_session()
