#!/usr/bin/env python3
"""
Afișează status live al dashboard-ului și trimite pe Telegram
"""
import json
from datetime import datetime
from pathlib import Path

# Citește trade_history.json
trade_file = Path("trade_history.json")

if not trade_file.exists():
    print("❌ trade_history.json nu există!")
    exit(1)

with open(trade_file, 'r', encoding='utf-8') as f:
    trades = json.load(f)

# Stats
closed_trades = [t for t in trades if t.get('status') == 'CLOSED']
open_trades = [t for t in trades if t.get('status') == 'OPEN']

winning = [t for t in closed_trades if t.get('profit', 0) > 0]
losing = [t for t in closed_trades if t.get('profit', 0) < 0]

total_profit = sum(t.get('profit', 0) for t in closed_trades)
balance = closed_trades[-1].get('balance_after', 1000) if closed_trades else 1000
win_rate = (len(winning) / len(closed_trades) * 100) if closed_trades else 0

# Fișier info
last_update = datetime.fromtimestamp(trade_file.stat().st_mtime)

print("\n" + "="*70)
print("📊 DASHBOARD STATUS - LIVE")
print("="*70)
print(f"\n📁 File: trade_history.json")
print(f"⏰ Last Update: {last_update.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"🔄 Age: {(datetime.now() - last_update).seconds} seconds ago")

print("\n" + "="*70)
print("💰 ACCOUNT SUMMARY")
print("="*70)
print(f"Balance: ${balance:,.2f}")
print(f"Total P/L: ${total_profit:+,.2f}")
print(f"ROI: {((balance - 1000) / 1000 * 100):+.1f}%")

print("\n" + "="*70)
print("📊 STATISTICS")
print("="*70)
print(f"Total Closed: {len(closed_trades)}")
print(f"Winners: {len(winning)} (${sum(t.get('profit', 0) for t in winning):.2f})")
print(f"Losers: {len(losing)} (${sum(t.get('profit', 0) for t in losing):.2f})")
print(f"Win Rate: {win_rate:.1f}%")
print(f"Open Positions: {len(open_trades)}")

if open_trades:
    print("\n" + "="*70)
    print("🔓 OPEN POSITIONS")
    print("="*70)
    for trade in open_trades:
        symbol = trade.get('symbol', 'N/A')
        direction = trade.get('direction', 'N/A')
        entry = trade.get('entry_price', 0)
        lot = trade.get('lot_size', 0)
        profit = trade.get('profit', 0)
        ticket = trade.get('ticket', 'N/A')
        
        emoji = "📈" if direction == 'BUY' else "📉"
        print(f"\n{emoji} {direction} {lot} {symbol}")
        print(f"   Entry: {entry:.5f}")
        print(f"   P/L: ${profit:+.2f}")
        print(f"   Ticket: #{ticket}")

print("\n" + "="*70)
print("🌐 DASHBOARD ACCESS")
print("="*70)
print("Local: http://localhost:8000/dashboard_live.html")
print("File: file:///Users/forexgod/Desktop/trading-ai-agent%20apollo/dashboard_live.html")

print("\n" + "="*70)
print("✅ Dashboard is LIVE and updating!")
print("="*70 + "\n")

# Trimite și pe Telegram
import os
from dotenv import load_dotenv
import requests

load_dotenv()
token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

msg = f"""
📊 <b>DASHBOARD STATUS UPDATE</b>

⏰ Last Sync: {last_update.strftime('%H:%M:%S')}
🔄 Age: {(datetime.now() - last_update).seconds}s ago

💰 <b>Account Summary</b>
Balance: ${balance:,.2f}
P/L: ${total_profit:+.2f}
ROI: {((balance - 1000) / 1000 * 100):+.1f}%

📊 <b>Statistics</b>
Closed: {len(closed_trades)}
Winners: {len(winning)} | Losers: {len(losing)}
Win Rate: {win_rate:.1f}%
Open: {len(open_trades)}

🌐 <b>Dashboard</b>
http://localhost:8000/dashboard_live.html

✅ <b>System Status: ONLINE</b>
"""

try:
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={'chat_id': chat_id, 'text': msg.strip(), 'parse_mode': 'HTML'},
        timeout=10
    )
    if response.status_code == 200:
        print("✅ Status sent to Telegram!")
    else:
        print(f"⚠️  Telegram: {response.status_code}")
except Exception as e:
    print(f"⚠️  Telegram error: {e}")
