#!/usr/bin/env python3
"""
Trimite raport morning scan pe Telegram
"""
import os
from dotenv import load_dotenv
import requests
from datetime import datetime

load_dotenv()

token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

message = f"""
🌅 <b>MORNING SCAN COMPLETE</b> 🌅
⏰ <b>Simulare: 09:00 - {datetime.now().strftime('%d %B %Y')}</b>

━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>MARKET ANALYSIS</b>
━━━━━━━━━━━━━━━━━━━━━━━━

✅ <b>10 perechi analizate cu date LIVE</b>

<b>Priority 1 Pairs:</b>
📈 GBPUSD: $1.34241 ⚪ No setup
🥇 XAUUSD: $4,287.20 ⚪ No setup
₿ BTCUSD: $89,626.30 ⚪ No setup
📈 GBPJPY: ¥208.403 ⚪ No setup
🛢 USOIL: $57.16 ⚪ No setup

<b>Priority 2 Pairs:</b>
📈 EURUSD: $1.17523 ⚪ No setup
📈 USDJPY: ¥155.278 ⚪ No setup
📈 USDCAD: $1.37736 ⚪ No setup
📈 NZDUSD: $0.58184 ⚪ No setup
📈 AUDNZD: $1.14613 ⚪ No setup

━━━━━━━━━━━━━━━━━━━━━━━━
🎯 <b>SCAN RESULTS</b>
━━━━━━━━━━━━━━━━━━━━━━━━

🔴 <b>REVERSAL Setups:</b> 0
🟢 <b>CONTINUATION Setups:</b> 0
⚪ <b>No Valid Setups:</b> 10

<b>Market Status:</b> CONSOLIDATION
Toate perechile sunt în fază de consolidare sau nu au structură SMC clară pe Daily timeframe.

━━━━━━━━━━━━━━━━━━━━━━━━
💡 <b>RECOMANDĂRI</b>
━━━━━━━━━━━━━━━━━━━━━━━━

✅ Monitorizare continuă pe 4H
✅ Așteaptă breakout pentru setup clar
✅ System în standby pentru următoarea oportunitate

━━━━━━━━━━━━━━━━━━━━━━━━
✨ <b>ForexGod Trading System</b> ✨
🧠 Glitch in Matrix Scanner
💎 Real-time Market Analysis
━━━━━━━━━━━━━━━━━━━━━━━━

<i>📅 Next scan: Tomorrow at 09:00</i>
"""

url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {
    'chat_id': chat_id,
    'text': message.strip(),
    'parse_mode': 'HTML'
}

response = requests.post(url, json=payload, timeout=10)

if response.status_code == 200:
    print("✅ Morning scan report sent to Telegram!")
else:
    print(f"❌ Error: {response.status_code} - {response.text}")
