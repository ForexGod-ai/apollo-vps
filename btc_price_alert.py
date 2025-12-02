"""
BTCUSD Price Alert - Notify when price reaches $89k (ForexGod's SELL zone)
Runs continuously and sends Telegram alert
"""

import MetaTrader5 as mt5
import time
import os
import requests
from loguru import logger
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Telegram config
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Alert config
TARGET_PRICE = 89000  # $89k - ForexGod's perfect entry
SYMBOL = "BTCUSD"
CHECK_INTERVAL = 60  # Check every 60 seconds
ALERT_SENT = False

def send_telegram_alert(message: str):
    """Send alert to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            logger.info("✅ Alert sent to Telegram!")
        else:
            logger.error(f"❌ Telegram error: {response.text}")
    except Exception as e:
        logger.error(f"❌ Failed to send alert: {e}")

def check_price():
    """Check BTCUSD price and send alert if target reached"""
    global ALERT_SENT
    
    # Get current price
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None:
        logger.error(f"Failed to get {SYMBOL} tick")
        return False
    
    current_price = tick.bid
    distance = ((TARGET_PRICE - current_price) / current_price) * 100
    
    logger.info(f"💰 {SYMBOL}: ${current_price:,.2f} | Target: ${TARGET_PRICE:,.2f} ({distance:+.2f}%)")
    
    # Check if price reached or passed target
    if not ALERT_SENT and current_price >= TARGET_PRICE:
        # Price reached $89k!
        alert_message = f"""
🚨 <b>BTCUSD PRICE ALERT!</b> 🚨

💰 <b>Current Price: ${current_price:,.2f}</b>
🎯 <b>Target Reached: $89,000</b>

🔥 <b>FOREXGOD's SELL ZONE ACTIVATED!</b>

📊 <b>Setup Reminder:</b>
• Market Structure: BEARISH (Lower High confirmed)
• Entry Zone: $89k area
• Resistance: $93,062 (swing high)
• Stop Loss: Above $93k-$95k
• Take Profit: $80,535 (recent low)
• R:R: ~14% move potential

⚡ <b>Action Plan:</b>
1. Watch for rejection signals (bearish engulfing, pinbar)
2. Check lower timeframe for CHoCH bearish
3. Wait for confirmation before entry
4. Use proper risk management!

💪 <b>Stay disciplined, ForexGod!</b>
🎯 <b>This is your zone!</b>

⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        send_telegram_alert(alert_message)
        ALERT_SENT = True
        logger.info("🔔 ALERT SENT! Price target reached!")
        return True
    
    return False

def run_alert_monitor():
    """Main monitoring loop"""
    logger.info("="*80)
    logger.info("🔔 BTCUSD PRICE ALERT MONITOR STARTED")
    logger.info("="*80)
    logger.info(f"📍 Target: ${TARGET_PRICE:,.2f}")
    logger.info(f"⏱️  Check interval: {CHECK_INTERVAL}s")
    logger.info("="*80)
    
    # Initialize MT5
    if not mt5.initialize():
        logger.error("❌ MT5 initialization failed!")
        return
    
    logger.info(f"✅ MT5 Connected: Account #{mt5.account_info().login}")
    
    try:
        while True:
            if check_price():
                # Alert sent, wait 5 minutes then exit
                logger.info("Waiting 5 minutes before shutting down...")
                time.sleep(300)
                break
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        logger.info("\n⚠️ Monitor stopped by user")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    finally:
        mt5.shutdown()
        logger.info("✅ Monitor shut down")

if __name__ == "__main__":
    run_alert_monitor()
