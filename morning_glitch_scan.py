"""
Morning GLITCH IN MATRIX Scanner
Runs at 08:00 daily and sends beautiful Telegram report
"""

import MetaTrader5 as mt5
import pandas as pd
import json
import os
from datetime import datetime
from loguru import logger
from price_action_analyzer import PriceActionAnalyzer
import requests
from dotenv import load_dotenv

load_dotenv()

# Telegram config from .env
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram_message(message: str):
    """Send message to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            logger.info("✅ Message sent to Telegram")
        else:
            logger.error(f"❌ Telegram error: {response.text}")
    except Exception as e:
        logger.error(f"❌ Failed to send Telegram: {e}")

def format_beautiful_report(signals: list) -> str:
    """Format signals into beautiful Telegram message"""
    
    if not signals:
        return """
🌅 <b>GOOD MORNING - GLITCH IN MATRIX SCAN</b>
⏰ <b>Scan Time:</b> {}

❌ <b>No High-Quality Setups Found Today</b>

The market is waiting... Stay patient! 🧘‍♂️
        """.format(datetime.now().strftime("%Y-%m-%d %H:%M"))
    
    # Build beautiful message
    msg = f"""
🌅 <b>GOOD MORNING - GLITCH IN MATRIX SCAN</b>
⏰ <b>Scan Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}

🔥 <b>Found {len(signals)} HIGH-QUALITY SETUP(S)!</b>

"""
    
    for i, sig in enumerate(signals, 1):
        direction_emoji = "🟢" if sig.direction == "bullish" else "🔴"
        direction_text = "LONG" if sig.direction == "bullish" else "SHORT"
        
        # Confidence stars
        stars = "⭐" * min(int(sig.confidence), 10)
        
        msg += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>#{i} {sig.symbol}</b> {direction_emoji} <b>{direction_text}</b>

💎 <b>Confidence:</b> {sig.confidence}/10 {stars}
📊 <b>Market Structure:</b> {sig.market_structure}
⚡ <b>Momentum:</b> {sig.momentum}

✅ <b>Confluence Factors:</b>
"""
        
        # Add reasons
        for reason in sig.reasons[:5]:  # Top 5 reasons
            msg += f"   • {reason}\n"
        
        # Trading levels
        msg += f"""
📍 <b>Entry Zone:</b> {sig.entry_zone[0]:.5f} - {sig.entry_zone[1]:.5f}
🛑 <b>Stop Loss:</b> {sig.stop_loss:.5f}
🎯 <b>Take Profit:</b> {sig.take_profit:.5f}

💰 <b>Risk/Reward:</b> 1:{(abs(sig.take_profit - sig.entry_zone[0]) / abs(sig.entry_zone[0] - sig.stop_loss)):.2f}

"""
    
    msg += """
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 <b>Trade Smart, Stay Disciplined!</b>
💪 <b>Glitch in Matrix Strategy Active</b>
"""
    
    return msg

def run_morning_scan():
    """Run morning GLITCH scan and send to Telegram"""
    
    logger.info("🌅 Starting Morning GLITCH Scan...")
    
    # Initialize MT5
    if not mt5.initialize():
        logger.error("MT5 initialization failed")
        send_telegram_message("❌ MT5 connection failed!")
        return
    
    logger.info(f"✅ MT5 Connected: Account #{mt5.account_info().login}")
    
    # Load pairs config
    try:
        with open('pairs_config.json', 'r') as f:
            config = json.load(f)
            all_pairs = [p['symbol'] for p in config['pairs']]
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        mt5.shutdown()
        return
    
    # Initialize GLITCH analyzer
    glitch_analyzer = PriceActionAnalyzer()
    
    # Scan all pairs
    signals = []
    
    for symbol in all_pairs:
        try:
            # Get Daily data
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 100)
            
            if rates is None or len(rates) == 0:
                continue
            
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Run GLITCH analysis
            signal = glitch_analyzer.analyze_full_context(df, symbol)
            
            if signal and signal.confidence >= 6:  # High quality threshold
                signals.append(signal)
                logger.info(f"✅ {symbol}: {signal.direction.upper()} (confidence {signal.confidence}/10)")
            
        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            continue
    
    # Sort by confidence (highest first)
    signals.sort(key=lambda x: x.confidence, reverse=True)
    
    # Format and send report
    report = format_beautiful_report(signals)
    send_telegram_message(report)
    
    logger.info(f"✅ Morning scan complete! Found {len(signals)} signals")
    
    mt5.shutdown()

if __name__ == "__main__":
    run_morning_scan()
