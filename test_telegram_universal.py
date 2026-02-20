#!/usr/bin/env python3
"""Final test: BLOOMBERG COLUMN v35.0 on Telegram"""

from telegram_notifier import TelegramNotifier

# Create notifier
telegram = TelegramNotifier()

# Test message in Bloomberg Column format
test_message = """📊 <b>FORMAT UPDATE</b>

✅ <b>BLOOMBERG COLUMN v35.0</b>

<b>Changes:</b>
✨ Quality: Exc
🕒 London ✅
📊 25 Trades

──────────────────
<b>Benefits:</b>

🔹 Vertical
   Stack Design
🔸 Max Width
   18 chars
🎯 Perfect
   Alignment

💡 No line wider than separator!
📱 Optimized for mobile
🎨 Bloomberg aesthetic

──────────────────
<b>Status:</b> LIVE
<b>Version:</b> v35.0
<b>Date:</b> Feb 18, 2026"""

# Send to Telegram (signature added automatically with blank line)
success = telegram.send_message(test_message, parse_mode="HTML")

if success:
    print("✅ BLOOMBERG COLUMN test sent to Telegram!")
    print("📱 Check your phone - you should see:")
    print("   • Vertical badge stack")
    print("   • Perfect column alignment")
    print("   • Blank line before final separator")
    print("   • 18-char separator: ──────────────────")
    print("   • Your signature: ✨ Glitch in Matrix by ФорексГод ✨")
else:
    print("❌ Failed to send message")
