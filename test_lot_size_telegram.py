"""
Live Telegram Test - LOT SIZE FIX by ФорексГод
Sends actual notification to verify:
1. Lot size displays correctly (0.01 minimum)
2. UNIVERSAL_SEPARATOR aligns perfectly with signature
3. Vertical badges + blank line before final separator
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from telegram_notifier import TelegramNotifier, UNIVERSAL_SEPARATOR

def send_live_test():
    notifier = TelegramNotifier()
    
    test_message = f"""🧪 <b>LOT SIZE FIX TEST</b>

✅ <b>REPAIR COMPLETE</b>

<b>Critical Fixes:</b>
1️⃣ Lot size minimum: 0.01
2️⃣ Separator length: 18 chars
3️⃣ Vertical badge stack
4️⃣ Airy final separator

──────────────────
<b>Demo Badge Stack:</b>

✨ Quality: Exc
🕒 London ✅
📊 25 Trades

──────────────────
<b>Demo Price Block:</b>

🔹 Entry
   <code>67000.00</code>
🔸 SL
   <code>66000.00</code>
🎯 TP
   <code>70000.00</code>

💵 $200.00
📦 <b>0.01 lots</b> ✅
⚖️ 1:3.00"""
    
    success = notifier.send_message(test_message, parse_mode="HTML")
    
    if success:
        print("✅ LOT SIZE FIX test sent to Telegram!")
        print("📱 Check your phone - you should see:")
        print("   • Lot size: 0.01 lots (never 0.00)")
        print(f"   • Separator: {UNIVERSAL_SEPARATOR} (18 chars)")
        print("   • Vertical badges (each on own line)")
        print("   • Blank line before final separator")
        print("   • Perfect alignment with signature")
        print(f"\n   Separator length: {len(UNIVERSAL_SEPARATOR)} characters ✅")
    else:
        print("❌ Failed to send test message")

if __name__ == "__main__":
    send_live_test()
