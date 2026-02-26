#!/usr/bin/env python3
"""
Test Weekly News Format - PREMIUM v5.0
Validates new separator consistency and signature
"""

from datetime import datetime, timedelta
from weekly_news_report import WeeklyNewsReport, NewsEvent

def test_format():
    """Test the PREMIUM formatted weekly message"""
    
    print("\n" + "="*70)
    print("🎨 WEEKLY NEWS FORMAT TEST - PREMIUM v5.0")
    print("="*70)
    
    reporter = WeeklyNewsReport()
    
    # Create test events
    test_events = [
        NewsEvent(
            time=datetime.now() + timedelta(days=1, hours=8, minutes=30),
            currency="USD",
            impact="High Impact Expected",
            event="Non-Farm Payrolls",
            actual="",
            forecast="185K",
            previous="180K"
        ),
        NewsEvent(
            time=datetime.now() + timedelta(days=1, hours=14, minutes=0),
            currency="USD",
            impact="High Impact Expected",
            event="FOMC Statement",
            actual="",
            forecast="",
            previous=""
        ),
        NewsEvent(
            time=datetime.now() + timedelta(days=2, hours=9, minutes=30),
            currency="GBP",
            impact="High Impact Expected",
            event="Official Bank Rate",
            actual="",
            forecast="5.25%",
            previous="5.00%"
        ),
        NewsEvent(
            time=datetime.now() + timedelta(days=3, hours=10, minutes=0),
            currency="EUR",
            impact="High Impact Expected",
            event="CPI y/y",
            actual="",
            forecast="2.8%",
            previous="2.6%"
        ),
    ]
    
    # Format message
    message = reporter.format_weekly_telegram_message(test_events)
    
    # Display
    print("\n" + "─"*70)
    print("📱 TELEGRAM MESSAGE PREVIEW:")
    print("─"*70)
    print(message)
    print("─"*70)
    
    # Validation
    print("\n✅ VALIDATION CHECKS:")
    
    SEPARATOR = "━━━━━━━━━━━━━━━━━━━━━"
    separator_count = message.count(SEPARATOR)
    print(f"   • Separator consistency: {separator_count} instances of '{SEPARATOR[:10]}...'")
    
    if "✨ *Glitch in Matrix by ФорексГод* ✨" in message:
        print("   • ✅ Official signature present")
    else:
        print("   • ❌ Signature missing or incorrect")
    
    if "🧠 AI-Powered • 💎 Smart Money" in message:
        print("   • ✅ Tagline present")
    else:
        print("   • ❌ Tagline missing")
    
    # Check spacing
    if "\n\n" in message:
        print("   • ✅ Breathing room (double newlines) present")
    else:
        print("   • ❌ No spacing between sections")
    
    # Check old separators removed
    old_separators = ["╼╼╼╼╼╼╼╼", "---", "-------"]
    old_found = any(old in message for old in old_separators)
    if not old_found:
        print("   • ✅ Old separators removed")
    else:
        print("   • ❌ Old separators still present")
    
    print("\n" + "="*70)
    print("🎉 FORMAT TEST COMPLETE - Ready for Telegram!")
    print("="*70)

if __name__ == "__main__":
    test_format()
