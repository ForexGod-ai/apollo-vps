#!/usr/bin/env python3
"""
Test News Filter Fix by ФорексГод
Validates that ONLY ForexFactory HIGH events are accepted
Critical keywords do NOT promote Medium/Low events to HIGH
"""

from datetime import datetime
from news_calendar_monitor import NewsEvent, NewsCalendarMonitor

def test_filter_logic():
    """Test the fixed filter_high_impact_events logic"""
    
    print("\n" + "="*70)
    print("🧪 NEWS FILTER FIX TEST by ФорексГод")
    print("="*70)
    
    monitor = NewsCalendarMonitor()
    
    # Create test events
    test_events = [
        # 1. TRUE HIGH (ForexFactory red icon)
        NewsEvent(
            time=datetime.now(),
            currency="USD",
            impact="High Impact Expected",  # ✅ ForexFactory HIGH
            event="Non-Farm Payrolls"
        ),
        
        # 2. MEDIUM with critical keyword (should be REJECTED now!)
        NewsEvent(
            time=datetime.now(),
            currency="USD",
            impact="Medium Impact Expected",  # ❌ ForexFactory MEDIUM
            event="CPI m/m"  # Contains "CPI" keyword
        ),
        
        # 3. LOW with critical keyword (should be REJECTED!)
        NewsEvent(
            time=datetime.now(),
            currency="EUR",
            impact="Low Impact Expected",  # ❌ ForexFactory LOW
            event="Retail Sales m/m"  # Contains "Retail Sales" keyword
        ),
        
        # 4. TRUE HIGH without critical keyword
        NewsEvent(
            time=datetime.now(),
            currency="GBP",
            impact="High Impact Expected",  # ✅ ForexFactory HIGH
            event="Claimant Count Change"
        ),
        
        # 5. MEDIUM without critical keyword (should be REJECTED!)
        NewsEvent(
            time=datetime.now(),
            currency="EUR",
            impact="Medium Impact Expected",  # ❌ ForexFactory MEDIUM
            event="Building Permits"
        ),
        
        # 6. Edge case: Impact contains "High" but not at start
        NewsEvent(
            time=datetime.now(),
            currency="JPY",
            impact="Highly Important",  # ❌ NOT ForexFactory format
            event="Some Event"
        ),
        
        # 7. Non-major currency HIGH (should be REJECTED!)
        NewsEvent(
            time=datetime.now(),
            currency="CNY",  # ❌ Not in major_currencies
            impact="High Impact Expected",
            event="GDP q/y"
        ),
        
        # 8. TRUE HIGH with critical keyword (SUPER CRITICAL)
        NewsEvent(
            time=datetime.now(),
            currency="USD",
            impact="High Impact Expected",  # ✅ ForexFactory HIGH
            event="FOMC Statement"  # Contains "FOMC" keyword
        ),
    ]
    
    # Apply filter
    filtered = monitor.filter_high_impact_events(test_events)
    
    # ══════════════════════════════════════════════════════════════
    # VALIDATION
    # ══════════════════════════════════════════════════════════════
    
    print("\n📊 TEST RESULTS:")
    print("─" * 70)
    
    expected_pass = [0, 3, 7]  # Events 1, 4, 8 (indexes 0, 3, 7)
    expected_reject = [1, 2, 4, 5, 6]  # Events 2, 3, 5, 6, 7
    
    print(f"\n✅ EXPECTED TO PASS: {len(expected_pass)} events")
    for idx in expected_pass:
        event = test_events[idx]
        print(f"   • {event.currency} - {event.event[:30]}")
        print(f"     Impact: {event.impact}")
    
    print(f"\n❌ EXPECTED TO REJECT: {len(expected_reject)} events")
    for idx in expected_reject:
        event = test_events[idx]
        print(f"   • {event.currency} - {event.event[:30]}")
        print(f"     Impact: {event.impact}")
        print(f"     Reason: {'Non-major currency' if event.currency not in monitor.major_currencies else 'Not ForexFactory HIGH'}")
    
    print("\n" + "─" * 70)
    print(f"🔍 FILTER RESULTS: {len(filtered)}/{len(test_events)} events passed")
    print("─" * 70)
    
    # Check if results match expectations
    passed_indices = [test_events.index(e) for e in filtered]
    
    all_correct = True
    
    # Check expected pass
    for idx in expected_pass:
        if idx not in passed_indices:
            print(f"❌ FAIL: Event {idx+1} should have PASSED but was REJECTED")
            print(f"   {test_events[idx].currency} - {test_events[idx].event}")
            all_correct = False
    
    # Check expected reject
    for idx in expected_reject:
        if idx in passed_indices:
            print(f"❌ FAIL: Event {idx+1} should have been REJECTED but PASSED")
            print(f"   {test_events[idx].currency} - {test_events[idx].event}")
            all_correct = False
    
    if all_correct and len(filtered) == len(expected_pass):
        print("\n" + "="*70)
        print("🎉 ALL TESTS PASSED!")
        print("="*70)
        print("\n✅ STRICT ForexFactory HIGH filtering works correctly")
        print("✅ Critical keywords NO LONGER promote Medium/Low to HIGH")
        print("✅ Non-major currencies filtered out")
        print("✅ Edge cases handled (substring matching fixed)")
        
        print("\n📊 EXPECTED BEHAVIOR:")
        print("   • Before fix: 48 HIGH events (many false positives)")
        print("   • After fix: ~8 HIGH events (ForexFactory accurate)")
        
        print("\n🎯 Next Steps:")
        print("   1. Test with real ForexFactory data:")
        print("      python3 weekly_news_report.py")
        print("   2. Verify Telegram report shows ~8 events (not 48)")
        print("   3. Compare with manual Forex Factory check")
        
        return True
    else:
        print("\n" + "="*70)
        print("❌ SOME TESTS FAILED - Review logic above")
        print("="*70)
        return False

if __name__ == "__main__":
    test_filter_logic()
