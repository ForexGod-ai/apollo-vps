"""
BTCUSD Price Alert - Notify when price reaches $89k (ForexGod's SELL zone)
Uses TradingView data (via yfinance)
"""

import yfinance as yf
import time
import os
import requests
from loguru import logger
from dotenv import load_dotenv
from datetime import datetime
from tradingview_chart_generator import TradingViewChartGenerator

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TARGET_PRICE = 89000
SYMBOL = "BTC-USD"
CHECK_INTERVAL = 60
ALERT_SENT = False

def send_telegram_alert(message: str, chart_image: bytes = None):
    """Send alert with optional chart screenshot"""
    url_base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    
    try:
        # Send text message
        url = f"{url_base}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, data=data)
        
        # Send chart screenshot if available
        if chart_image:
            url = f"{url_base}/sendPhoto"
            files = {"photo": ("btc_chart.png", chart_image, "image/png")}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": "📊 BTCUSD Daily Chart"}
            requests.post(url, data=data, files=files)
            logger.info("✅ Chart screenshot sent!")
        
        if response.status_code == 200:
            logger.info("✅ Alert sent to Telegram!")
    except Exception as e:
        logger.error(f"❌ Failed to send alert: {e}")

def check_price():
    global ALERT_SENT
    try:
        ticker = yf.Ticker(SYMBOL)
        data = ticker.history(period='1d', interval='1m')
        if data.empty:
            return False
        
        current_price = data['Close'].iloc[-1]
        distance = ((TARGET_PRICE - current_price) / current_price) * 100
        logger.info(f"💰 BTCUSD: ${current_price:,.2f} | Target: ${TARGET_PRICE:,.2f} ({distance:+.2f}%)")
        
        if not ALERT_SENT and current_price >= TARGET_PRICE:
            alert = f"""🚨 BTCUSD PRICE ALERT! 🚨

💰 Current Price: ${current_price:,.2f}
🎯 Target Reached: $89,000

🔥 FOREXGOD SELL ZONE ACTIVATED!

📊 Setup: BEARISH (Lower High)
⚡ Action: Watch for rejection signals
💪 Stay disciplined!

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            # Get TradingView chart screenshot
            chart_image = None
            try:
                chart_gen = TradingViewChartGenerator(login=False)
                chart_image = chart_gen.get_chart_screenshot('BTCUSD', 'D')
                chart_gen.close()
                logger.info("✅ Chart screenshot captured")
            except Exception as e:
                logger.error(f"⚠️  Could not capture chart: {e}")
            
            send_telegram_alert(alert, chart_image)
            ALERT_SENT = True
            return True
    except Exception as e:
        logger.error(f"Error: {e}")
    return False

def run_alert_monitor():
    logger.info("="*80)
    logger.info("🔔 BTCUSD ALERT MONITOR - TradingView Data")
    logger.info(f"📍 Target: ${TARGET_PRICE:,.2f}")
    logger.info("="*80)
    
    try:
        while True:
            if check_price():
                logger.info("✅ Alert sent! Shutting down in 5 min...")
                time.sleep(300)
                break
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Monitor stopped")

if __name__ == "__main__":
    run_alert_monitor()
