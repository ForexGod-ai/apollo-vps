import json
import os
from datetime import datetime, timedelta
import requests
from pathlib import Path
import random

# Load Telegram credentials
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print('Missing Telegram credentials!')
    exit(1)

trade_history_file = Path('trade_history.json')
if not trade_history_file.exists():
    print('trade_history.json not found!')
    exit(1)

data = json.loads(trade_history_file.read_text())
today = datetime.now().date()
closed_today = [t for t in data['closed_trades'] if 'close_time' in t and datetime.fromisoformat(t['close_time']).date() == today]

if not closed_today:
    print('No trades closed today.')
    exit(0)

# Epic TP titles
tp_titles = [
    "🎯 <b>TARGET DESTROYED</b> 🎯",
    "💰 <b>BANK SECURED</b> 💰",
    "🏆 <b>VICTORY ACHIEVED</b> 🏆",
    "💎 <b>PROFIT LOCKED</b> 💎",
    "⚡ <b>TAKE PROFIT OBLITERATED</b> ⚡",
    "🚀 <b>MISSION ACCOMPLISHED</b> 🚀",
    "👑 <b>KING'S HARVEST</b> 👑",
    "🔥 <b>PROFIT EXTRACTION COMPLETE</b> 🔥"
]

epic_title = random.choice(tp_titles)

# Calculate daily stats
total_profit = sum(float(t.get('profit', 0)) for t in closed_today)
total_trades = len(closed_today)
winners = [t for t in closed_today if float(t.get('profit', 0)) > 0]
win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0

# Find best trade
best_trade = max(closed_today, key=lambda t: float(t.get('profit', 0)))

# Build enhanced message
msg = f"""
{epic_title}

🔥 <b>DAILY PROFIT REPORT</b> 🔥
──────────────────

"""

# Individual trades
for t in closed_today:
    profit = float(t.get('profit', 0))
    symbol = t.get('symbol', 'N/A')
    direction = t.get('direction', 'N/A').upper()
    entry = float(t.get('entry_price', 0))
    close = float(t.get('closing_price', 0))
    
    # Calculate trade duration
    if 'open_time' in t and 'close_time' in t:
        open_dt = datetime.fromisoformat(t['open_time'])
        close_dt = datetime.fromisoformat(t['close_time'])
        duration = close_dt - open_dt
        hours = duration.total_seconds() / 3600
        duration_str = f"{int(hours)}h {int((hours % 1) * 60)}m"
    else:
        duration_str = "N/A"
    
    # Direction arrow
    arrow = "📈 ↗️" if direction == 'BUY' else "📉 ↘️"
    
    # Profit emoji
    profit_emoji = "💰" if profit > 0 else "⚠️"
    
    # Calculate actual R:R if possible
    rr_actual = "N/A"
    if 'stop_loss' in t and t['stop_loss']:
        sl = float(t['stop_loss'])
        risk = abs(entry - sl)
        reward = abs(close - entry)
        if risk > 0:
            rr_actual = f"1:{reward/risk:.2f}"
    
    is_best = (t == best_trade)
    best_marker = " 🏆 <b>BEST</b>" if is_best else ""
    
    msg += f"""
💎 <b>{symbol}</b> • {arrow} <b>{direction}</b>{best_marker}
{profit_emoji} <b>Profit:</b> ${profit:.2f}
⏱️ <b>Duration:</b> {duration_str}
📊 <b>R:R:</b> {rr_actual}
──────────────────
"""

# Daily summary
acc = data['account']
msg += f"""

📊 <b>TODAY'S SUMMARY:</b>
──────────────────
🎯 <b>Trades Closed:</b> {total_trades}
💰 <b>Total Profit:</b> ${total_profit:.2f}
📈 <b>Win Rate:</b> {win_rate:.1f}%
🏆 <b>Best Trade:</b> ${float(best_trade.get('profit', 0)):.2f}

💼 <b>ACCOUNT STATUS:</b>
──────────────────
💰 <b>Balance:</b> ${acc["balance"]:.2f}
💎 <b>Equity:</b> ${acc["equity"]:.2f}
📊 <b>Open P/L:</b> ${acc["open_pl"]:.2f}

──────────────────
✨ <b>Glitch in Matrix</b> by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money
──────────────────
"""

url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
payload = {
    'chat_id': TELEGRAM_CHAT_ID,
    'text': msg.strip(),
    'parse_mode': 'HTML',
    'disable_web_page_preview': True
}

response = requests.post(url, json=payload, timeout=10)
if response.status_code == 200:
    print('✅ Enhanced TP report sent to Telegram!')
else:
    print(f'❌ Telegram error: {response.status_code} - {response.text}')
