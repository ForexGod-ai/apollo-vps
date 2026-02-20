#!/usr/bin/env python3
"""
Test Compact Telegram Format - Send to Telegram
Uses mock data to test the new compact format
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests

load_dotenv()

def send_telegram_test():
    """Send test message with compact format to Telegram"""
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("❌ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found in .env")
        return False
    
    # Create compact test message with mock data
    now = datetime.now()
    
    message = f"""⚡ *NEWS TEST* • {now.strftime('%H:%M')}
📅 {now.strftime('%a %b %d')}
🔥 *2 CRITICAL*
📊 4 HIGH impact (48h)
⚠️ Avoid 30min before
╼╼╼╼╼╼╼╼
📍 *Monday, February 16*
╼╼╼╼╼╼╼╼
⚠️🇺🇸 *USD* Non-Farm Payrolls
🕐 15:30 • 🔴 IMMINENT
📊 F:`200K` P:`185K`
💥 *EXTREME VOL*

🇪🇺 *EUR* ECB Press Conference
🕐 19:45 • 🟡 4h
📊 F:`N/A` P:`N/A`

📍 *Tuesday, February 17*
╼╼╼╼╼╼╼╼
⚠️🇬🇧 *GBP* CPI y/y
🕐 10:00 • 🟢 18h
📊 F:`2.5%` P:`2.3%`
📊 *INFLATION*

🇯🇵 *JPY* BOJ Rate Decision
🕐 04:00 • 🟢 12h
📊 F:`0.25%` P:`0.25%`

╼╼╼╼╼╼╼╼
📊 *SUMMARY:*
🇺🇸USD:2 ⚠️1
🇪🇺EUR:1 
🇬🇧GBP:1 ⚠️1
🇯🇵JPY:1 
╼╼╼╼╼╼╼╼
🎯 *PROTOCOL:*
🟠 MODERATE
• Watch news times
• SL to BE before
╼╼╼╼╼╼╼╼
💡 Updates: 8am,2pm,8pm,2am
╼╼╼╼╼╼╼╼
✨ *Glitch in Matrix*
👑 ФорексГод
╼╼╼╼╼╼╼╼"""
    
    # Send to Telegram
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    
    print("📤 Sending compact format test to Telegram...")
    print()
    print("Preview:")
    print(message)
    print()
    
    try:
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            print("✅ SUCCESS! Message sent to Telegram")
            print()
            print("📱 Check your Telegram to see the compact format!")
            print()
            print("Width comparison:")
            print("  OLD: ────────────────── (14 chars)")
            print("  NEW: ╼╼╼╼╼╼╼╼ (8 chars)")
            print()
            print("  Reduction: 43% narrower! 🎯")
            return True
        else:
            print(f"❌ Telegram API error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False


if __name__ == "__main__":
    print()
    print("="*50)
    print("🧪 COMPACT FORMAT TEST - TELEGRAM")
    print("="*50)
    print()
    
    success = send_telegram_test()
    
    print()
    print("="*50)
    if success:
        print("✅ Test complete! Check Telegram app")
    else:
        print("❌ Test failed - check credentials")
    print("="*50)
    print()
