#!/usr/bin/env python3
"""
Trimite statistici complete cont pe Telegram
"""
import json
import os
from dotenv import load_dotenv
import requests
from datetime import datetime

load_dotenv()

token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

# Citește trade history
with open('trade_history.json', 'r') as f:
    trades = json.load(f)

# Calculează stats
closed_trades = [t for t in trades if t.get('status') == 'CLOSED']
open_trades = [t for t in trades if t.get('status') == 'OPEN']

total_profit = sum(t.get('profit', 0) for t in closed_trades)
winning_trades = [t for t in closed_trades if t.get('profit', 0) > 0]
losing_trades = [t for t in closed_trades if t.get('profit', 0) < 0]

win_rate = (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0

# Balance final
balance = 1000.00
if closed_trades:
    balance = closed_trades[-1].get('balance_after', 1000.00)

# Profit/Loss total
total_wins = sum(t.get('profit', 0) for t in winning_trades)
total_losses = sum(t.get('profit', 0) for t in losing_trades)

# Best/Worst trade
best_trade = max(closed_trades, key=lambda t: t.get('profit', 0)) if closed_trades else None
worst_trade = min(closed_trades, key=lambda t: t.get('profit', 0)) if closed_trades else None

# Build message
message = f"""
🔥 <b>FOREXGOD TRADING SYSTEM</b> 🔥
📊 <b>Account Statistics Report</b>

──────────────────
💰 <b>ACCOUNT OVERVIEW</b>
──────────────────

💵 Current Balance: <b>${balance:.2f}</b>
📈 Total Profit: <b>${total_profit:+.2f}</b>
📊 ROI: <b>{((balance - 1000) / 1000 * 100):+.1f}%</b>
🎯 Initial Capital: $1,000.00

──────────────────
📋 <b>TRADE STATISTICS</b>
──────────────────

📌 Total Trades: <b>{len(closed_trades)}</b>
✅ Winning Trades: <b>{len(winning_trades)}</b> (${total_wins:.2f})
❌ Losing Trades: <b>{len(losing_trades)}</b> (${total_losses:.2f})
🎯 Win Rate: <b>{win_rate:.1f}%</b>

🔓 <b>Open Positions: {len(open_trades)}</b>
"""

# Add open positions details
if open_trades:
    message += "\n──────────────────\n"
    message += "🔓 <b>OPEN POSITIONS</b>\n"
    message += "──────────────────\n\n"
    for trade in open_trades:
        symbol = trade.get('symbol', 'N/A')
        direction = trade.get('direction', 'N/A')
        entry = trade.get('entry_price', 0)
        lot = trade.get('lot_size', 0)
        profit = trade.get('profit', 0)
        sl = trade.get('stop_loss', 0)
        tp = trade.get('take_profit', 0)
        ticket = trade.get('ticket', 'N/A')
        
        emoji = "📈" if direction == 'BUY' else "📉"
        
        message += f"{emoji} <b>{direction} {lot} {symbol}</b>\n"
        message += f"   💰 Entry: {entry:.5f}\n"
        message += f"   💵 P/L: ${profit:+.2f}\n"
        message += f"   🛑 SL: {sl:.5f}\n"
        message += f"   🎯 TP: {tp:.5f}\n"
        message += f"   🎫 #{ticket}\n\n"

# Add best/worst trades
message += "──────────────────\n"
message += "🏆 <b>PERFORMANCE HIGHLIGHTS</b>\n"
message += "──────────────────\n\n"

if best_trade:
    message += f"🥇 <b>Best Trade:</b> {best_trade.get('symbol')} "
    message += f"{best_trade.get('direction')} - ${best_trade.get('profit', 0):+.2f}\n"

if worst_trade:
    message += f"😓 <b>Worst Trade:</b> {worst_trade.get('symbol')} "
    message += f"{worst_trade.get('direction')} - ${worst_trade.get('profit', 0):+.2f}\n"

# Recent trades (last 5)
message += "\n──────────────────\n"
message += "📅 <b>RECENT TRADES (Last 5)</b>\n"
message += "──────────────────\n\n"

recent = closed_trades[-5:] if len(closed_trades) >= 5 else closed_trades
for trade in reversed(recent):
    symbol = trade.get('symbol', 'N/A')
    direction = trade.get('direction', 'N/A')
    profit = trade.get('profit', 0)
    pips = trade.get('pips', 0)
    close_time = trade.get('close_time', 'N/A')
    
    emoji = "✅" if profit > 0 else "❌"
    
    message += f"{emoji} {symbol} {direction} - ${profit:+.2f} ({pips:+.1f} pips)\n"
    message += f"   🕐 {close_time}\n\n"

message += """──────────────────
✨ <b>Strategy by ForexGod</b> ✨
🧠 Glitch in Matrix Trading System
💎 + AI Validation
──────────────────

⏰ Report Generated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Send to Telegram
url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {
    'chat_id': chat_id,
    'text': message.strip(),
    'parse_mode': 'HTML'
}

response = requests.post(url, json=payload, timeout=10)

if response.status_code == 200:
    print("✅ Account statistics sent to Telegram!")
else:
    print(f"❌ Error: {response.status_code} - {response.text}")
