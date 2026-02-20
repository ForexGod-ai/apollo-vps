#!/usr/bin/env python3
"""
Preview Compact Setup Report Format v4.0
Shows before/after comparison for setup alerts
"""

def show_old_format():
    """OLD FORMAT (verbose)"""
    return """
🔥🚨 <b>SETUP - XTIUSD</b> 🔥🚨
🔴 SHORT 📉

✅ <b>READY TO EXECUTE</b>
<b>REVERSAL - MAJOR TREND CHANGE!</b>
🎯 <b>ENTRY METHOD:</b> Pullback @ Fibo 50% (Classic)

⏰ <b>Time Elapsed:</b> 8.5h / 12h timeout
🟩🟩🟩🟩🟩🟩🟩⬜⬜⬜ 70%

──────────────────
📈 <b>XTIUSD STATISTICS:</b>
──────────────────
🟢 Win Rate: 65.0% (13W/7L)
💰 Avg R:R: 1:2.3
🏆 Best Trade: $450.00
📊 Total Trades: 20

──────────────────
🧠 <b>AI CONFIDENCE SCORE:</b>
──────────────────
🟢 Score: 78/100 (HIGH)
🟩🟩🟩🟩🟩🟩🟩🟩⬜⬜
🤖 AI Says: ✅ TAKE

📊 Analysis:
  • Trend Alignment: Strong
  • Volume Profile: Above average
  • Risk Reward: Excellent (1:2.5)
  • Time Of Day: Prime (London open)

<i>Based on 116 historical trades</i>

──────────────────
📊 <b>DAILY ANALYSIS:</b>
📍 CHoCH: <code>BEARISH</code>
🎯 FVG Zone: <code>73.450 - 73.850</code>

⚡ <b>1H STATUS (Entry 1):</b>
⚡ 1H CHoCH: BEARISH @ 73.650 ✅
⏰ <b>Waiting for pullback to Fibo 50%</b>

🔍 <b>4H STATUS (Entry 2):</b>
⏳ <b>Waiting for 4H confirmation</b>
⏰ Monitoring for Entry 2...

──────────────────
💰 <b>TRADE SETUP:</b>
💎 Entry: <code>73.650</code>
🛑 Stop Loss: <code>74.150</code>
🎯 Take Profit: <code>72.400</code>

📊 R:R Ratio: <code>1:2.50</code>
📦 Lot Size: <code>0.15</code>
💵 Risk: <code>$200.00</code>

⭐ Priority: <code>HIGH</code>
⏰ Setup: <code>2026-02-17 08:30 UTC</code>

──────────────────
📈 <b>VIEW CHARTS:</b>
📊 Daily • ⚡ 1H • 🔍 4H
"""

def show_new_format():
    """NEW FORMAT (compact v4.0)"""
    return """
🔥 <b>SETUP: XTIUSD</b> 🔴 SHORT 📉
✅ <b>READY</b> • REVERSAL
🟢 <b>Stats:</b> 65% WR • 1:2.3 R:R • 20 trades
🧠 <b>AI:</b> 78/100 (HIGH) ✅ TAKE
🟩🟩🟩🟩🟩🟩🟩🟩⬜⬜
🎯 <b>Entry:</b> Pullback @ Fibo 50%
⏰ <b>Elapsed:</b> 8.5h/12h
🟩🟩🟩🟩🟩🟩🟩⬜⬜⬜ 70%
╼╼╼╼╼╼╼╼
📊 <b>DAILY:</b> CHoCH BEARISH
🎯 FVG: <code>73.450 - 73.850</code>
⚡ 1H CHoCH @ 73.650 ✅
⏳ Waiting 4H confirm
╼╼╼╼╼╼╼╼
💰 <b>TRADE:</b>
📥 In: <code>73.650</code> | 🛑 SL: <code>74.150</code>
🎯 TP: <code>72.400</code> | ⚖️ RR: <code>1:2.50</code>
📦 Size: <code>0.15</code> lots | 💵 Risk: <code>$200.00</code>
╼╼╼╼╼╼╼╼
✨ <b>Glitch in Matrix by ФорексГод</b> ✨
"""

def show_btcusd_example():
    """BTCUSD continuation setup - compact format"""
    return """
🎯 <b>SETUP: BTCUSD</b> 🟢 LONG 📈
👀 <b>MONITORING</b> • CONTINUATION
🟡 <b>Stats:</b> 52% WR • 1:1.8 R:R • 8 trades
🧠 <b>AI:</b> 65/100 (MODERATE) ⚠️ REVIEW
🟩🟩🟩🟩🟩🟩⬜⬜⬜⬜
🚀 <b>Entry:</b> Momentum (Score: 72/100)
🔥🔥🔥🔥🔥🔥🔥⬜⬜⬜ 72/100 ✅
╼╼╼╼╼╼╼╼
📊 <b>DAILY:</b> CHoCH BULLISH
🎯 FVG: <code>94250.00 - 94850.00</code>
⚡ 1H CHoCH @ 94650.00 ✅
🔄 4H CHoCH @ 95100.00 ✅
╼╼╼╼╼╼╼╼
💰 <b>TRADE:</b>
📥 In: <code>94650.00</code> | 🛑 SL: <code>93850.00</code>
🎯 TP: <code>96100.00</code> | ⚖️ RR: <code>1:1.81</code>
📦 Size: <code>0.05</code> lots | 💵 Risk: <code>$200.00</code>
╼╼╼╼╼╼╼╼
✨ <b>Glitch in Matrix by ФорексГод</b> ✨
"""

def calculate_reduction():
    """Calculate size reduction"""
    old = show_old_format()
    new = show_new_format()
    
    old_lines = len(old.strip().split('\n'))
    new_lines = len(new.strip().split('\n'))
    
    old_chars = len(old)
    new_chars = len(new)
    
    line_reduction = (old_lines - new_lines) / old_lines * 100
    char_reduction = (old_chars - new_chars) / old_chars * 100
    
    return old_lines, new_lines, line_reduction, old_chars, new_chars, char_reduction

def main():
    print("=" * 60)
    print("📱 SETUP REPORT - COMPACT v4.0 PREVIEW")
    print("=" * 60)
    print()
    
    print("━━━ OLD FORMAT (VERBOSE) ━━━")
    print(show_old_format())
    print()
    
    print("━━━ NEW FORMAT (COMPACT v4.0) ━━━")
    print(show_new_format())
    print()
    
    print("━━━ BTCUSD EXAMPLE (COMPACT v4.0) ━━━")
    print(show_btcusd_example())
    print()
    
    # Statistics
    old_lines, new_lines, line_reduction, old_chars, new_chars, char_reduction = calculate_reduction()
    
    print("=" * 60)
    print("📊 REDUCTION STATISTICS")
    print("=" * 60)
    print(f"Lines:      {old_lines} → {new_lines} ({line_reduction:.1f}% reduction)")
    print(f"Characters: {old_chars} → {new_chars} ({char_reduction:.1f}% reduction)")
    print()
    print("KEY IMPROVEMENTS:")
    print("  ✅ Separator: 20 chars → 8 chars (60% reduction)")
    print("  ✅ AI Score: Multi-line → Single line + bar")
    print("  ✅ Stats: Separate section → Inline")
    print("  ✅ Trade params: 3 lines → 3 inline")
    print("  ✅ Footer: Long branding → Compact 1-line")
    print("  ✅ Overall: 40%+ content reduction 🎯")
    print()
    print("=" * 60)
    print("✨ Compact format ready for Telegram! ✨")
    print("=" * 60)

if __name__ == '__main__':
    main()
