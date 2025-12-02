"""
Test Telegram Alert for Current BTCUSD Setup
Sends the BTCUSD SHORT setup with chart and Execute/Skip buttons
"""

import sys
from loguru import logger
from daily_scanner import MT5DataProvider
from smc_detector import SMCDetector
from telegram_notifier import TelegramNotifier

def test_btc_alert():
    logger.info("🔍 Testing BTCUSD Alert to Telegram")
    logger.info("=" * 80)
    
    # Initialize components
    data_provider = MT5DataProvider()
    detector = SMCDetector()
    notifier = TelegramNotifier()
    
    symbol = "BTCUSD"
    
    # Connect to MT5
    if not data_provider.connect():
        logger.error("❌ Failed to connect to MT5")
        return
    
    # Get data
    logger.info(f"\n📊 Downloading data for {symbol}...")
    df_daily = data_provider.get_historical_data(symbol, "D1", 50)
    df_4h = data_provider.get_historical_data(symbol, "H4", 200)
    
    if df_daily is None or df_4h is None:
        logger.error(f"❌ Failed to get data for {symbol}")
        data_provider.disconnect()
        return
    
    logger.info(f"✅ Downloaded {len(df_daily)} Daily + {len(df_4h)} 4H candles")
    
    # Scan for setup
    logger.info(f"\n🔍 Scanning for setup...")
    setup = detector.scan_for_setup(symbol, df_daily, df_4h, priority=1)
    
    if not setup:
        logger.error("❌ No setup found!")
        return
    
    logger.info(f"✅ Setup found!")
    logger.info(f"   Type: {setup.strategy_type.upper()}")
    logger.info(f"   Direction: {setup.daily_choch.direction.upper()}")
    logger.info(f"   Entry: {setup.entry_price:.5f}")
    logger.info(f"   SL: {setup.stop_loss:.5f}")
    logger.info(f"   TP: {setup.take_profit:.5f}")
    logger.info(f"   R:R: 1:{setup.risk_reward:.2f}")
    
    # Send to Telegram
    logger.info(f"\n📤 Sending alert to Telegram...")
    
    success = notifier.send_setup_alert(
        setup=setup,
        df_daily=df_daily,
        df_4h=df_4h
    )
    
    if success:
        logger.info("✅ Alert sent successfully!")
        logger.info("\n👉 Check your Telegram group: 'ForexGod - Glitch Signals 🔥'")
        logger.info("👉 Click 'Execute Trade' to place order on MT5 Demo")
    else:
        logger.error("❌ Failed to send alert")
    
    data_provider.disconnect()

if __name__ == "__main__":
    test_btc_alert()
