"""
TradingView Chart Generator - ForexGod Trading AI
Professional chart screenshots using TradingView directly
"""

import os
import time
import json
from typing import Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from dotenv import load_dotenv
import io

load_dotenv()


class TradingViewChartGenerator:
    """Generate professional TradingView chart screenshots"""
    
    def __init__(self, login: bool = True):
        """
        Initialize Chrome driver with headless mode
        
        Args:
            login: If True, will login to TradingView account (ForexGod Premium)
        """
        self.driver = None
        self.logged_in = False
        self.tv_username = os.getenv('TRADINGVIEW_USERNAME')
        self.tv_password = os.getenv('TRADINGVIEW_PASSWORD')
        self.saved_charts = self._load_saved_charts()
        self._setup_driver()
        if login and self.tv_username and self.tv_password:
            self._login_to_tradingview()
    
    def _load_saved_charts(self) -> dict:
        """Load saved/published chart URLs from config"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'tradingview_saved_charts.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    return data.get('charts', {})
        except Exception as e:
            print(f"⚠️  Could not load saved charts: {e}")
        return {}
    
    def _setup_driver(self):
        """Setup Chrome driver for screenshots"""
        chrome_options = Options()
        # NOTE: Headless disabled to preserve TradingView login session
        # chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        # Persist session across runs
        chrome_options.add_argument('--user-data-dir=/tmp/tradingview_chrome_profile')
        
        # Use Safari WebDriver on macOS (alternative to Chrome)
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            print(f"⚠️  Chrome driver not available: {e}")
            print("📝 Install ChromeDriver: brew install chromedriver")
            self.driver = None
    
    def _login_to_tradingview(self):
        """Login to TradingView account for personalized charts"""
        if not self.driver:
            return
        
        try:
            print("🔐 Logging in to TradingView...")
            
            # Go directly to email login page
            self.driver.get("https://www.tradingview.com/accounts/signin/")
            time.sleep(4)
            
            # Find and fill email field
            try:
                email_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='id_username'], input[name='username'], input[type='email']"))
                )
                email_input.clear()
                email_input.send_keys(self.tv_username)
                print(f"✅ Email entered: {self.tv_username}")
                time.sleep(1)
            except Exception as e:
                print(f"❌ Could not find email field: {e}")
                return
            
            # Find and fill password field
            try:
                password_input = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='id_password'], input[name='password'], input[type='password']"))
                )
                password_input.clear()
                password_input.send_keys(self.tv_password)
                print("✅ Password entered")
                time.sleep(1)
            except Exception as e:
                print(f"❌ Could not find password field: {e}")
                return
            
            # Submit the form
            try:
                # Try clicking submit button
                submit_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], button[name='login']")
                submit_btn.click()
                print("✅ Login submitted")
            except:
                # Fallback: press Enter
                password_input.send_keys(Keys.RETURN)
                print("✅ Login submitted (Enter key)")
            
            # Wait for login to complete
            time.sleep(6)
            
            # Check if login successful by looking for user menu or chart page
            try:
                # If we're redirected to chart or see user menu, login worked
                current_url = self.driver.current_url
                print(f"📍 Current URL: {current_url}")
                
                if "chart" in current_url or "tradingview.com" in current_url and "signin" not in current_url:
                    print("✅ Successfully logged in to TradingView Premium!")
                    self.logged_in = True
                else:
                    print("⚠️  Login status unclear")
                    self.logged_in = False
            except:
                print("⚠️  Could not verify login status")
                self.logged_in = False
                
        except Exception as e:
            print(f"❌ Login failed: {e}")
            print("📝 Will continue without login (public charts)")
    
    def get_chart_screenshot(
        self, 
        symbol: str, 
        timeframe: str = "D",
        width: int = 1920,
        height: int = 1080
    ) -> Optional[bytes]:
        """
        Get professional TradingView chart screenshot
        
        Args:
            symbol: Trading pair (e.g., EURUSD, BTCUSD)
            timeframe: D, 240 (4H), 60 (1H), 15, 5, etc.
            width: Screenshot width
            height: Screenshot height
        
        Returns:
            PNG image bytes or None if failed
        """
        if not self.driver:
            print("❌ WebDriver not initialized")
            return None
        
        try:
            # Convert symbol to TradingView format
            tv_symbol = self._get_tv_symbol(symbol)
            
            # Build TradingView URL with parameters
            url = self._build_chart_url(tv_symbol, timeframe)
            
            print(f"📊 Loading TradingView chart: {tv_symbol} ({timeframe})")
            
            # Load the page
            self.driver.get(url)
            
            # Wait for chart to load (wait for candles to appear)
            wait = WebDriverWait(self.driver, 20)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "canvas")))
            
            # Close any popups/modals (reclame, cookies, etc.)
            time.sleep(3)  # Wait for chart to fully render
            try:
                # Try to close popup by clicking X or overlay
                close_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Close'], .close, [class*='close'], [class*='dismiss']")
                for btn in close_buttons:
                    try:
                        btn.click()
                        time.sleep(0.5)
                    except:
                        pass
                
                # Press ESC to close any modals
                from selenium.webdriver.common.keys import Keys
                from selenium.webdriver.common.action_chains import ActionChains
                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                time.sleep(1)
            except:
                pass
            
            # Give extra time for chart to fully render
            time.sleep(2)
            
            # Take screenshot
            screenshot = self.driver.get_screenshot_as_png()
            
            print(f"✅ Screenshot captured: {len(screenshot)} bytes")
            
            return screenshot
            
        except Exception as e:
            print(f"❌ Error capturing TradingView screenshot: {e}")
            return None
    
    def _build_chart_url(self, tv_symbol: str, timeframe: str) -> str:
        """
        Build TradingView chart URL - uses saved/published chart if available
        
        Priority:
        1. Saved/published chart (includes all drawings - CHoCH, FVG, imbalances)
        2. Default chart with user's layout
        """
        # Check if we have a saved chart for this symbol
        symbol_clean = tv_symbol.split(':')[-1]  # Extract "GBPUSD" from "FX:GBPUSD" or "GOLD" from "TVC:GOLD"
        
        # Try to find saved chart - check both original symbol and TradingView symbol
        # Example: XAUUSD → check both "XAUUSD" and "GOLD"
        saved_url = None
        
        # First check the TradingView symbol name (e.g., "GOLD")
        if symbol_clean in self.saved_charts and self.saved_charts[symbol_clean]:
            saved_url = self.saved_charts[symbol_clean]
            print(f"✅ Using saved chart with drawings: {symbol_clean}")
        
        # Also check for MT5 symbol name mapping (e.g., XAUUSD → GOLD)
        # Reverse lookup in tv_symbols dict
        if not saved_url:
            for mt5_sym, tv_sym in self._get_symbol_map().items():
                if tv_sym == tv_symbol:
                    # Found MT5 symbol, check if it has saved chart
                    if mt5_sym in self.saved_charts and self.saved_charts[mt5_sym]:
                        saved_url = self.saved_charts[mt5_sym]
                        print(f"✅ Using saved chart with drawings: {mt5_sym}")
                        break
        
        if saved_url:
            return saved_url
        
        # Fallback to default chart
        interval_map = {
            "1": "1", "5": "5", "15": "15", "60": "60", 
            "240": "240", "D": "D", "W": "W", "M": "M"
        }
        
        interval = interval_map.get(timeframe, "D")
        url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}&interval={interval}"
        
        print(f"⚠️  Using default chart (no saved chart for {symbol_clean})")
        return url
    
    def _get_symbol_map(self) -> dict:
        """Get MT5 to TradingView symbol mapping"""
        return {
            "EURUSD": "FX:EURUSD",
            "GBPUSD": "FX:GBPUSD",
            "USDJPY": "FX:USDJPY",
            "USDCHF": "FX:USDCHF",
            "AUDUSD": "FX:AUDUSD",
            "USDCAD": "FX:USDCAD",
            "NZDUSD": "FX:NZDUSD",
            "EURJPY": "FX:EURJPY",
            "GBPJPY": "FX:GBPJPY",
            "EURGBP": "FX:EURGBP",
            "EURCAD": "FX:EURCAD",
            "AUDCAD": "FX:AUDCAD",
            "AUDNZD": "FX:AUDNZD",
            "NZDCAD": "FX:NZDCAD",
            "GBPNZD": "FX:GBPNZD",
            "GBPCHF": "FX:GBPCHF",
            "CADCHF": "FX:CADCHF",
            "XAUUSD": "TVC:GOLD",
            "BTCUSD": "BITSTAMP:BTCUSD",
            "USOIL": "TVC:USOIL"
        }
    
    def _get_tv_symbol(self, symbol: str) -> str:
        """Convert MT5 symbol to TradingView symbol format"""
        tv_symbols = self._get_symbol_map()
        return tv_symbols.get(symbol, f"FX:{symbol}")
    
    def close(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def __del__(self):
        """Cleanup on object destruction"""
        self.close()


# Quick test
if __name__ == "__main__":
    generator = TradingViewChartGenerator()
    
    # Test with EURUSD Daily chart
    screenshot = generator.get_chart_screenshot("EURUSD", "D")
    
    if screenshot:
        # Save to file for testing
        with open("tradingview_test.png", "wb") as f:
            f.write(screenshot)
        print("✅ Test screenshot saved: tradingview_test.png")
    else:
        print("❌ Failed to generate screenshot")
    
    generator.close()
