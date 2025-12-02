"""
Quick SMC Scan cu Telegram Report
"""
import MetaTrader5 as mt5
import pandas as pd
import json
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram(message):
    """Send to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'})

# Initialize MT5
print("\n🔌 Connecting to MT5...")
if not mt5.initialize():
    print("❌ MT5 init failed")
    exit()

account = mt5.account_info()
print(f"✅ Connected: Account #{account.login}")

# Load pairs
with open('pairs_config.json', 'r') as f:
    config = json.load(f)
    pairs = [p['symbol'] for p in config['pairs']]

print(f"\n📊 Scanning {len(pairs)} pairs...")

# Import SMC detector
try:
    from smc_detector import SMCDetector
    smc = SMCDetector()
    print("✅ SMC Detector loaded")
except Exception as e:
    print(f"❌ Error loading SMC: {e}")
    exit()

found_setups = []

for i, symbol in enumerate(pairs, 1):
    print(f"[{i}/{len(pairs)}] Scanning {symbol}...", end=" ")
    
    try:
        # Get Daily data
        rates_d1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 100)
        if rates_d1 is None or len(rates_d1) < 20:
            print("❌ No data")
            continue
        
        df_daily = pd.DataFrame(rates_d1)
        df_daily['time'] = pd.to_datetime(df_daily['time'], unit='s')
        
        current_price = df_daily['close'].iloc[-1]
        
        # Detect CHoCH on Daily
        chochs = smc.detect_choch(df_daily)
        if not chochs:
            print("⏳ No CHoCH")
            continue
        
        latest_choch = chochs[-1]
        
        # Detect FVG after CHoCH
        fvg = smc.detect_fvg(df_daily, latest_choch, current_price)
        if not fvg:
            print("⏳ No FVG")
            continue
        
        # Check if price is in FVG
        if not smc.is_price_in_fvg(current_price, fvg):
            print("⏳ Price not in FVG yet")
            continue
        
        # Get 4H data
        rates_4h = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 200)
        if rates_4h is None or len(rates_4h) < 20:
            print("❌ No 4H data")
            continue
        
        df_4h = pd.DataFrame(rates_4h)
        df_4h['time'] = pd.to_datetime(df_4h['time'], unit='s')
        
        # Detect 4H CHoCH in FVG
        setup = smc.detect_4h_choch_in_fvg(df_daily, df_4h, latest_choch, fvg, current_price)
        
        if setup and setup.status == 'READY':
            found_setups.append(setup)
            print(f"✅ SETUP FOUND! ({setup.h4_choch.direction if setup.h4_choch else 'monitoring'})")
        else:
            print(f"⏳ Monitoring")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        continue

print(f"\n{'='*60}")
print(f"📊 SCAN COMPLETE")
print(f"{'='*60}")
print(f"Pairs scanned: {len(pairs)}")
print(f"Setups found: {len(found_setups)}")

# Build Telegram message
if len(found_setups) == 0:
    msg = f"""
🌅 <b>GLITCH IN MATRIX - SCAN REPORT</b>
⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}

📊 Scanned: <b>{len(pairs)} pairs</b>

⏳ <b>No READY setups found</b>

The market is consolidating... Patience! 🧘‍♂️

<i>SMC Algorithm is VERY selective - looking for institutional footprints only!</i>
"""
else:
    msg = f"""
🌅 <b>GLITCH IN MATRIX - SCAN REPORT</b>
⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}

📊 Scanned: <b>{len(pairs)} pairs</b>
🔥 Found: <b>{len(found_setups)} READY setup(s)!</b>

"""
    
    for i, setup in enumerate(found_setups, 1):
        direction = setup.h4_choch.direction if setup.h4_choch else "monitoring"
        emoji = "🟢" if direction == "bullish" else "🔴" if direction == "bearish" else "⏳"
        
        msg += f"""
━━━━━━━━━━━━━━━━━━━━━━
<b>#{i} {setup.symbol}</b> {emoji} <b>{direction.upper()}</b>

📊 Daily CHoCH: {setup.daily_choch.direction.upper()}
💎 FVG Zone: ${setup.fvg.bottom:.5f} - ${setup.fvg.top:.5f}
⚡ 4H CHoCH: {direction.upper()}

💰 <b>Trading Setup:</b>
Entry: <b>${setup.entry_price:.5f}</b>
Stop Loss: ${setup.stop_loss:.5f}
Take Profit: ${setup.take_profit:.5f}
Risk/Reward: <b>1:{setup.risk_reward:.2f}</b>

Priority: {setup.priority}/10 {'⭐' * setup.priority}
Type: {setup.strategy_type.upper()}
"""

print(f"\n📱 Sending to Telegram...")
send_telegram(msg)
print(f"✅ Report sent!")

mt5.shutdown()

print(f"\n{'='*60}")
print("✅ DONE!")
print(f"{'='*60}")
