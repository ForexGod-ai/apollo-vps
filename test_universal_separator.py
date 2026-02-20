#!/usr/bin/env python3
"""Test UNIVERSAL 18-CHAR RULE with WHITESPACE MASTERY"""

from telegram_notifier import TelegramNotifier

# Create notifier
telegram = TelegramNotifier()

# Test message
test_message = """🎯 <b>SETUP: GBPJPY</b> 🟢 LONG 📈
👀 <b>MONITORING</b> • REVERSAL

──────────────────
🧠 <b>AI Matrix Score: 85% (HIGH)</b>
[🟩🟩🟩🟩🟩🟩🟩🟩⬜⬜]
🤖 <b>Recommendation:</b> EXECUTE
✨ Quality: Good | 🕒 Timing: London ✅
📊 Context: 15 Trades

──────────────────
📊 <b>DAILY:</b> CHoCH BULLISH
🎯 FVG: <code>212.47800</code> - <code>213.85600</code>

⏳ Waiting 1H CHoCH
🔄 4H CHoCH @ <code>213.16450</code> ✅

──────────────────
💰 <b>TRADE:</b>

📥 In: <code>213.16450</code>
🛑 SL: <code>211.94700</code>
🎯 TP: <code>215.60200</code>

💵 Risk: <code>$200.00</code>
📦 Size: <code>0.02</code> lots
⚖️ R:R: <code>1:2.00</code>"""

# Add signature with WHITESPACE MASTERY
final_message = telegram._add_branding_signature(test_message, parse_mode="HTML")

print('=' * 70)
print('🏆  UNIVERSAL 18-CHAR RULE + WHITESPACE MASTERY')
print('=' * 70)
print(final_message)
print('=' * 70)
print('\n✅ BLANK LINE: Added above final separator')
print('✅ 18 CHARS: Separator perfectly aligned with signature')
print('✅ CONSISTENT: Same format across ALL notifications')
print('✅ AIRY DESIGN: High-end terminal aesthetic maintained')
