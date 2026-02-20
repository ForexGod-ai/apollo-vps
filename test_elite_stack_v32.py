#!/usr/bin/env python3
"""
Test ELITE STACK v32.0 - Live Telegram
Trimite setup-uri cu noul format Elegant, Scannable, Aerisit
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def send_elite_stack_v32():
    """Send ELITE STACK v32.0 format to Telegram"""
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("❌ Missing Telegram credentials!")
        return False
    
    # XTIUSD REVERSAL - ELITE STACK v32.0
    xtiusd_message = """🔥 <b>SETUP: XTIUSD</b> 🔴 SHORT 📉
✅ <b>READY</b> • REVERSAL
🟢 <b>Stats:</b> 65% WR • 1:2.3 R:R • 20 trades

╼╼╼╼╼
🧠 <b>AI Score:</b> 78/100 (HIGH)
[🟩🟩🟩🟩🟩🟩🟩🟩⬜⬜] ✅ TAKE
🎯 <b>Entry:</b> Pullback @ Fibo 50%
⏰ <b>Elapsed:</b> 8.5h/12h
[🟩🟩🟩🟩🟩🟩🟩⬜⬜⬜] 70% ⚠️

╼╼╼╼╼
📊 <b>DAILY:</b> CHoCH BEARISH
🎯 FVG: <code>73.450 - 73.850</code>
⚡ 1H CHoCH @ 73.650 ✅
⏳ Waiting 4H confirm

╼╼╼╼╼
💰 <b>TRADE:</b>
📥 In: <code>73.650</code> | 🛑 SL: <code>74.150</code>
🎯 TP: <code>72.400</code> | 💵 Risk: <code>$200.00</code>
📦 Size: <code>0.15</code> lots | ⚖️ RR: <code>1:2.50</code>

╼╼╼╼╼
✨ <b>Glitch in Matrix by ФорексГод</b> ✨
🧠 AI-Powered • 💎 Smart Money"""
    
    # BTCUSD CONTINUATION - ELITE STACK v32.0
    btcusd_message = """🎯 <b>SETUP: BTCUSD</b> 🟢 LONG 📈
👀 <b>MONITORING</b> • CONTINUATION
🟡 <b>Stats:</b> 52% WR • 1:1.8 R:R • 8 trades

╼╼╼╼╼
🧠 <b>AI Score:</b> 65/100 (MODERATE)
[🟩🟩🟩🟩🟩🟩⬜⬜⬜⬜] ⚠️ REVIEW
🚀 <b>Entry:</b> Momentum (Score: 72/100)
[🔥🔥🔥🔥🔥🔥🔥⬜⬜⬜] 72/100 ✅

╼╼╼╼╼
📊 <b>DAILY:</b> CHoCH BULLISH
🎯 FVG: <code>94250.00 - 94850.00</code>
⚡ 1H CHoCH @ 94650.00 ✅
🔄 4H CHoCH @ 95100.00 ✅

╼╼╼╼╼
💰 <b>TRADE:</b>
📥 In: <code>94650.00</code> | 🛑 SL: <code>93850.00</code>
🎯 TP: <code>96100.00</code> | 💵 Risk: <code>$200.00</code>
📦 Size: <code>0.05</code> lots | ⚖️ RR: <code>1:1.81</code>

╼╼╼╼╼
✨ <b>Glitch in Matrix by ФорексГод</b> ✨
🧠 AI-Powered • 💎 Smart Money"""
    
    # EXECUTION ALERT - ELITE STACK v32.0
    execution_message = """⚡ <b>TRADE LIVE</b> • XTIUSD
📉 <b>SELL</b>

╼╼╼╼╼
📥 In: <code>73.650</code> | 🛑 SL: <code>74.150</code> (50.0p)
🎯 TP: <code>72.400</code> (125.0p)
⚖️ RR: 1:2.50

╼╼╼╼╼
✅ EXECUTED • 16:24:30

╼╼╼╼╼
✨ <b>Glitch in Matrix by ФорексГод</b> ✨
🧠 AI-Powered • 💎 Smart Money"""
    
    print("=" * 70)
    print("🧪 ELITE STACK v32.0 - LIVE TELEGRAM TEST")
    print("Elegant • Scannable • Aerisit")
    print("=" * 70)
    print()
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    # Send XTIUSD
    print("📤 Sending XTIUSD setup (REVERSAL)...")
    print()
    print("Preview:")
    print(xtiusd_message)
    print()
    
    response = requests.post(url, data={
        'chat_id': chat_id,
        'text': xtiusd_message,
        'parse_mode': 'HTML'
    })
    
    if response.status_code == 200:
        print("✅ XTIUSD sent successfully!")
    else:
        print(f"❌ XTIUSD failed: {response.text}")
        return False
    
    print()
    print("━" * 70)
    print()
    
    # Send BTCUSD
    print("📤 Sending BTCUSD setup (CONTINUATION)...")
    print()
    print("Preview:")
    print(btcusd_message)
    print()
    
    response = requests.post(url, data={
        'chat_id': chat_id,
        'text': btcusd_message,
        'parse_mode': 'HTML'
    })
    
    if response.status_code == 200:
        print("✅ BTCUSD sent successfully!")
    else:
        print(f"❌ BTCUSD failed: {response.text}")
        return False
    
    print()
    print("━" * 70)
    print()
    
    # Send EXECUTION
    print("📤 Sending EXECUTION alert...")
    print()
    print("Preview:")
    print(execution_message)
    print()
    
    response = requests.post(url, data={
        'chat_id': chat_id,
        'text': execution_message,
        'parse_mode': 'HTML'
    })
    
    if response.status_code == 200:
        print("✅ EXECUTION sent successfully!")
    else:
        print(f"❌ EXECUTION failed: {response.text}")
        return False
    
    print()
    print("=" * 70)
    print("✅ ALL MESSAGES SENT TO TELEGRAM!")
    print("=" * 70)
    print()
    print("📱 Check your Telegram to see:")
    print("  • ✅ Spații între secțiuni (aerisit)")
    print("  • ✅ Separator scurt (╼╼╼╼╼ = 5 chars)")
    print("  • ✅ AI bar cu paranteze []")
    print("  • ✅ Footer complet cu semnătură oficială")
    print("  • ✅ Trade params clare (3 linii)")
    print()
    print("🎯 OBIECTIV v32.0:")
    print("  • Elegant: Vizual plăcut, nu aglomerat ✅")
    print("  • Scannable: Secțiuni clare, ușor de citit ✅")
    print("  • Aerisit: Spații între secțiuni ✅")
    print()
    print("📊 vs v4.0 COMPACT:")
    print("  • 4x mai mult spațiu între secțiuni")
    print("  • Separator mai scurt (5 vs 8 chars)")
    print("  • Footer complet (AI-Powered + Smart Money)")
    print()
    print("=" * 70)
    print("✨ ELITE STACK v32.0 - Perfect Balance! ✨")
    print("=" * 70)
    
    return True

if __name__ == '__main__':
    send_elite_stack_v32()
