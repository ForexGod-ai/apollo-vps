"""
🎯 GLITCH IN MATRIX - MARKET SCAN with TELEGRAM
Scanează toate perechile cu SMC Algorithm și trimite rezultate pe Telegram
"""

import MetaTrader5 as mt5
import pandas as pd
import json
import os
import requests
from loguru import logger
from datetime import datetime
from dotenv import load_dotenv
from smc_algorithm import SMCAlgorithm

load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram(message: str):
    """Trimite mesaj pe Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(url, data={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        })
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

# Initialize MT5
if not mt5.initialize():
    logger.error("❌ MT5 initialization failed")
    send_telegram("❌ <b>MT5 Connection Failed!</b>\n\nCannot run market scan.")
    exit()

logger.info(f"✅ MT5 Connected: Account #{mt5.account_info().login}")

# Load pairs
try:
    with open('pairs_config.json', 'r') as f:
        config = json.load(f)
        all_pairs = [p['symbol'] for p in config['pairs']]
except:
    all_pairs = ['GBPUSD', 'XAUUSD', 'BTCUSD', 'GBPJPY', 'EURUSD', 'GBPNZD', 
                 'EURJPY', 'NZDCAD', 'GBPCHF', 'AUDNZD', 'USDJPY', 'USDCAD']

# Initialize SMC
smc = SMCAlgorithm()

logger.info("\n" + "="*80)
logger.info("🎯 GLITCH IN MATRIX - MARKET SCAN")
logger.info("="*80)
logger.info(f"Scanning {len(all_pairs)} pairs...")

# Send start notification
now = datetime.now()
send_telegram(f"""
🎯 <b>GLITCH IN MATRIX</b>
🔍 Market Scan Started

📊 Scanning: {len(all_pairs)} pairs
⏰ Time: {now.strftime('%H:%M:%S')}
📅 Date: {now.strftime('%d %B %Y')}

<i>Searching for institutional footprints...</i>
""")

found_signals = []

for i, symbol in enumerate(all_pairs, 1):
    try:
        logger.info(f"[{i}/{len(all_pairs)}] Scanning {symbol}...")
        
        # Get Daily data
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 100)
        if rates is None or len(rates) == 0:
            logger.warning(f"   No data for {symbol}")
            continue
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Run SMC analysis
        signal = smc.analyze(df, symbol)
        
        if signal:
            found_signals.append(signal)
            logger.info(f"   🔥 SIGNAL FOUND! {signal.direction.upper()} (confidence {signal.confidence}/10)")
        else:
            logger.info(f"   ⏳ No signal")
    
    except Exception as e:
        logger.error(f"   Error: {e}")
        continue

# Send results
logger.info(f"\n{'='*80}")
logger.info(f"📊 SCAN COMPLETE - Found {len(found_signals)} signals")
logger.info(f"{'='*80}")

if found_signals:
    # Send each signal
    for idx, sig in enumerate(found_signals, 1):
        direction_emoji = "🟢" if sig.direction == "bullish" else "🔴"
        direction_text = "LONG" if sig.direction == "bullish" else "SHORT"
        
        # Calculate risk/reward
        risk = abs(sig.entry_zone[0] - sig.stop_loss)
        reward = abs(sig.take_profit - sig.entry_zone[0])
        
        msg = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>#{idx} {sig.symbol}</b> {direction_emoji} <b>{direction_text}</b>

⭐ <b>Confidence: {sig.confidence}/10</b>

💰 <b>TRADE SETUP:</b>
Entry Zone: <b>${sig.entry_zone[0]:.5f} - ${sig.entry_zone[1]:.5f}</b>
Stop Loss: ${sig.stop_loss:.5f}
Take Profit: ${sig.take_profit:.5f}
Risk/Reward: <b>1:{sig.risk_reward:.2f}</b>

📊 <b>ANALYSIS:</b>
• Market Structure: {sig.market_structure}
• Order Block: {sig.order_block.type.upper()} ({sig.order_block.strength})
• Premium Zone: {'✅' if sig.in_premium else '❌'}
• Discount Zone: {'✅' if sig.in_discount else '❌'}
• Liquidity Swept: {'✅' if sig.liquidity_swept else '❌'}
• FVG Present: {'✅' if sig.fvg else '❌'}

✅ <b>CONFLUENCE ({len(sig.reasons)}):</b>
"""
        for reason in sig.reasons:
            msg += f"• {reason}\n"
        
        msg += f"\n<i>Risk: ${risk:.5f} | Reward: ${reward:.5f}</i>"
        
        send_telegram(msg)
        logger.info(f"📱 Sent {sig.symbol} to Telegram")

# Summary
summary = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>SCAN SUMMARY</b>

✅ Scanned: {len(all_pairs)} pairs
🔥 Found: {len(found_signals)} high-quality setups
⏰ Completed: {datetime.now().strftime('%H:%M:%S')}

"""

if not found_signals:
    summary += """
💤 <b>NO SETUPS FOUND</b>

The SMC algorithm is VERY selective!
We only trade when institutions show their hand.

<i>Patience = Profit 💎</i>
"""
else:
    summary += "<b>Setups above are ready to execute!</b>\n\n"
    summary += "<i>FOREXGOD - Glitch in Matrix</i>\n"
    summary += "<i>\"When institutions glitch, we profit\"</i> 💎"

send_telegram(summary)

logger.info("\n" + "="*80)
logger.info("✅ SCAN COMPLETE - Results sent to Telegram!")
logger.info("="*80)

mt5.shutdown()
