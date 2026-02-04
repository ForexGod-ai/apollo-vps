#!/usr/bin/env python3
"""
Test Telegram HTML Formatting
Quick test to verify HTML tags render properly
"""

import os
from dotenv import load_dotenv
from telegram_notifier import TelegramNotifier

load_dotenv()

def test_html_formatting():
    """Test HTML formatting in Telegram messages"""
    notifier = TelegramNotifier()
    
    test_message = """
🔥🚨 <b>SETUP - GBPUSD</b> 🔥🚨
🟢 LONG 📈

✅ <b>READY TO EXECUTE</b>
<b>REVERSAL - MAJOR TREND CHANGE!</b>

━━━━━━━━━━━━━━━━━━━━
🧠 <b>AI CONFIDENCE SCORE:</b>
━━━━━━━━━━━━━━━━━━━━
🟢 Score: 80/100 (HIGH)
🟩🟩🟩🟩🟩🟩🟩🟩⬜⬜
🤖 AI Says: ✅ TAKE

📊 Analysis:
  • <b>Pair Quality:</b> Excellent (PF: 2.54)
  • <b>Timing:</b> Good timing (14:00)

<i>Based on 116 historical trades</i>

━━━━━━━━━━━━━━━━━━━━
🧠 <b>AI PROBABILITY ANALYSIS</b>
━━━━━━━━━━━━━━━━━━━━
🟢 <b>AI Score: 8/10</b> (VERY HIGH)
🟩🟩🟩🟩🟩🟩🟩🟩⬜⬜

📊 <b>Analysis Factors:</b>
  • <b>Symbol Quality:</b> Excellent (PF: 2.54, 67.7% win rate)
  • <b>Timing:</b> GOOD TIMING (14:00 - 42.9% win rate, 7 trades)
  • <b>Session:</b> NEW YORK (high volume, strong momentum)

🤖 <b>AI Recommendation:</b> EXECUTE (system learns from all trades)

━━━━━━━━━━━━━━━━━━━━
💰 <b>TRADE SETUP:</b>
💎 Entry: <code>1.33406</code>
🛑 Stop Loss: <code>1.33000</code>
🎯 Take Profit: <code>1.44000</code>

📊 R:R Ratio: <code>1:26.78</code>
    """
    
    print("📤 Sending test message to Telegram...")
    print(f"Parse mode: HTML")
    print(f"Add signature: True (automatic)")
    
    success = notifier.send_message(test_message, parse_mode="HTML", add_signature=True)
    
    if success:
        print("✅ Test message sent successfully!")
        print("\n📱 Check your Telegram to verify:")
        print("   1. Bold text renders properly (<b>text</b>)")
        print("   2. Code blocks render properly (<code>1.33406</code>)")
        print("   3. Italic text renders properly (<i>text</i>)")
        print("   4. Only ONE branding stamp at the end")
    else:
        print("❌ Failed to send test message")
        
if __name__ == "__main__":
    test_html_formatting()
