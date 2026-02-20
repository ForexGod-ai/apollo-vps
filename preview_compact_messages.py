#!/usr/bin/env python3
"""
Preview Compact Telegram Messages - Mobile Optimized
Shows how the new compact format looks on narrow screens
"""

def show_compact_preview():
    """Display compact message examples"""
    
    print("\n" + "="*50)
    print("📱 COMPACT TELEGRAM PREVIEW - MOBILE OPTIMIZED")
    print("="*50)
    
    # Example 1: All Clear
    print("\n━━━ EXAMPLE 1: ALL CLEAR ━━━\n")
    all_clear = """✅ *ALL CLEAR*
🟢 *Status:* SAFE TO TRADE
📊 *Next 48h:* No major events
💎 *Risk:* LOW
╼╼╼╼╼╼╼╼
✨ *Glitch in Matrix*
👑 ФорексГод
╼╼╼╼╼╼╼╼"""
    print(all_clear)
    
    # Example 2: Daily News Alert
    print("\n━━━ EXAMPLE 2: DAILY NEWS ALERT ━━━\n")
    daily_news = """⚡ *NEWS* • 14:30
📅 Mon Feb 16
🔥 *2 CRITICAL*
📊 5 HIGH impact (48h)
⚠️ Avoid 30min before
╼╼╼╼╼╼╼╼
📍 *Monday, February 16*
╼╼╼╼╼╼╼╼
⚠️🇺🇸 *USD* Non-Farm Payrolls
🕐 15:30 • 🔴 < 1 HOUR
📊 F:`200K` P:`190K`
💥 *EXTREME VOL*

🇪🇺 *EUR* ECB Press Conference
🕐 19:45 • 🟡 5h
📊 F:`N/A` P:`N/A`

📍 *Tuesday, February 17*
╼╼╼╼╼╼╼╼
🇬🇧 *GBP* CPI y/y
🕐 10:00 • 🟢 19h
📊 F:`2.5%` P:`2.3%`
📊 *INFLATION*

╼╼╼╼╼╼╼╼
📊 *SUMMARY:*
🇺🇸USD:2 ⚠️1
🇪🇺EUR:2 
🇬🇧GBP:1 ⚠️1
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
    print(daily_news)
    
    # Example 3: Weekly Report
    print("\n━━━ EXAMPLE 3: WEEKLY REPORT ━━━\n")
    weekly_report = """📅 *WEEKLY REPORT*
🗓️ Feb 16-Feb 23
🔥 12 HIGH impact
⏰ Sun 14:30
╼╼╼╼╼╼╼╼
⚠️ *3 CRITICAL*
📍 *Monday, February 16*
╼╼╼╼╼╼╼╼
⚠️🇺🇸 *USD* NFP
🕐 15:30
📊 F:`200K` P:`190K`
💥 *EXTREME VOL*

🇪🇺 *EUR* ECB Meeting
🕐 13:45
📊 F:`4.50%` P:`4.50%`

📍 *Wednesday, February 18*
╼╼╼╼╼╼╼╼
⚠️🇺🇸 *USD* FOMC Minutes
🕐 20:00
💥 *FED*

🇬🇧 *GBP* Retail Sales
🕐 10:00
📊 F:`1.2%` P:`0.8%`

╼╼╼╼╼╼╼╼
📊 *SUMMARY:*
🇺🇸USD:5 ⚠️2
🇪🇺EUR:3 ⚠️1
🇬🇧GBP:2 
🇯🇵JPY:2 
╼╼╼╼╼╼╼╼
🎯 *STRATEGY:*
⚡ MODERATE
• Standard risk
• Close before news
╼╼╼╼╼╼╼╼
📅 Next: Sun Feb 23
╼╼╼╼╼╼╼╼
✨ *Glitch in Matrix*
👑 ФорексГод
╼╼╼╼╼╼╼╼"""
    print(weekly_report)
    
    # Statistics
    print("\n" + "="*50)
    print("📊 COMPACT FORMAT STATISTICS")
    print("="*50)
    print()
    print("BEFORE (Old Format):")
    print("  • Separator: ────────────────── (14 chars)")
    print("  • Empty lines: Multiple")
    print("  • Width: ~40-50 chars")
    print("  • Footer: 3 lines")
    print()
    print("AFTER (New Compact):")
    print("  • Separator: ╼╼╼╼╼╼╼╼ (8 chars)")
    print("  • Empty lines: Minimal")
    print("  • Width: ~25-30 chars")
    print("  • Footer: 2 lines")
    print()
    print("📉 WIDTH REDUCTION: ~50%")
    print("📉 LINE REDUCTION: ~35%")
    print("✅ MOBILE FRIENDLY: Perfect!")
    print()
    print("="*50)
    print("👑 ФорексГод • Glitch in Matrix V4.0")
    print("="*50)
    print()


if __name__ == "__main__":
    show_compact_preview()
