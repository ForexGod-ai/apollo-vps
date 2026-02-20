#!/usr/bin/env python3
"""
Test UPGRADED execution message
"""
import requests
import os
import random

telegram_token = '7888595238:AAFfD5N6T0AaByb1C0ZN6HZ2LYYhtixmNFg'
telegram_chat_id = '6693464829'

# Simulate a real trade execution
symbol = 'USDCAD'
direction = 'BUY'
entry = 1.36824
lot = 0.05
ticket = '12345678'
stop_loss = 1.36751
take_profit = 1.37500

# Calculate risk metrics
pip_value = 0.0001
risk_pips = abs(entry - stop_loss) / pip_value
reward_pips = abs(take_profit - entry) / pip_value
rr = reward_pips / risk_pips if risk_pips > 0 else 0

# Epic ARMAGEDDON messages
armageddon_messages = [
    "⚔️ <b>THE ARMAGEDDON BEGINS</b> ⚔️",
    "💥 <b>MARKET DOMINATION MODE</b> 💥",
    "🔥 <b>BEAST MODE UNLEASHED</b> 🔥",
    "⚡ <b>GODMODE ACTIVATED</b> ⚡",
    "🎯 <b>SNIPER ELITE • TARGET LOCKED</b> 🎯",
    "💀 <b>NO MERCY • FULL AGGRO</b> 💀",
    "🚀 <b>TO THE MOON WE GO</b> 🚀",
    "👑 <b>KING'S GAMBIT • CHECKMATE</b> 👑",
    "⚡ <b>GLITCH ACTIVATED • MATRIX BREACHED</b> ⚡",
    "🔮 <b>PROPHECY FULFILLED</b> 🔮"
]
epic_title = random.choice(armageddon_messages)

# Direction arrow
direction_arrow = "📈 ↗️" if direction == 'BUY' else "📉 ↘️"

# Build UPGRADED message
message = f"""
{epic_title}

🔥 <b>GLITCH IN MATRIX • POSITION LIVE</b> 🔥
──────────────────

{direction_arrow} <b>{direction}</b> • {lot} lots
💎 <b>{symbol}</b>
💰 <b>Entry:</b> {entry:.5f}
🎫 <b>Ticket:</b> #{ticket}

🛑 <b>Stop Loss:</b> {stop_loss:.5f}
🎯 <b>Take Profit:</b> {take_profit:.5f}

🛑 <b>Risk:</b> {risk_pips:.1f} pips
🎯 <b>Reward:</b> {reward_pips:.1f} pips
📊 <b>R:R Ratio:</b> 1:{rr:.2f}

──────────────────
🧠 <b>AI Validation:</b> ✅ CONFIRMED
⚡ <b>Risk Level:</b> CALCULATED
🤖 <b>Execution:</b> AUTOMATED
💯 <b>Confidence:</b> HIGH

<i>💎 "The Matrix cannot hold us" 💎</i>

──────────────────
✨ <b>Glitch in Matrix</b> by ForexGod ✨
🧠 AI-Powered • 💎 Smart Money
──────────────────
"""

print("📱 Trimit UPGRADED EXECUTION message pe Telegram...\n")
print("="*60)
print("PREVIEW:")
print("="*60)
print(message)

# Send to Telegram
url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
payload = {
    'chat_id': telegram_chat_id,
    'text': message.strip(),
    'parse_mode': 'HTML',
    'disable_web_page_preview': True
}

response = requests.post(url, json=payload, timeout=10)

if response.status_code == 200:
    print("\n✅ UPGRADED EXECUTION MESSAGE TRIMIS PE TELEGRAM!")
    print("\nVerifică pe Telegram să vezi:")
    print("  ⚔️ Random epic title (10 variante)")
    print("  📈 Direction arrows (BUY/SELL)")
    print("  🛑 Risk pips calculated")
    print("  🎯 Reward pips calculated")
    print("  📊 R:R Ratio displayed")
    print("  💎 Better formatting & separators")
    print("  🧠 AI validation status")
else:
    print(f"\n❌ Error: {response.status_code} - {response.text}")
