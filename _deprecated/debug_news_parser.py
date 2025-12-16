"""
Debug script to see exactly what events we're finding and why they're filtered
"""

from news_calendar_monitor import NewsCalendarMonitor
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

print("🔍 DEBUG: News Calendar Parser")
print("=" * 60)

monitor = NewsCalendarMonitor()

# Fetch all events
print("\n1️⃣ Fetching ALL events from ForexFactory...")
all_events = monitor.fetch_forexfactory_calendar(days_ahead=7)

print(f"\n📊 Total events found: {len(all_events)}")
print("\n" + "=" * 60)

# Show first 10 events
print("\n📋 First 10 events (all impacts):")
for i, event in enumerate(all_events[:10]):
    print(f"\n{i+1}. {event.currency} - {event.event}")
    print(f"   Time: {event.time.strftime('%Y-%m-%d %H:%M')}")
    print(f"   Impact: '{event.impact}'")
    print(f"   Forecast: {event.forecast}")
    print(f"   Previous: {event.previous}")

print("\n" + "=" * 60)

# Check HIGH impact filtering
print("\n2️⃣ Filtering for HIGH impact events...")
high_impact = monitor.filter_high_impact_events(all_events)

print(f"\n🚨 HIGH impact events: {len(high_impact)}")

if high_impact:
    print("\n📋 HIGH impact events found:")
    for i, event in enumerate(high_impact):
        print(f"\n{i+1}. {event.currency} - {event.event}")
        print(f"   Time: {event.time.strftime('%A, %B %d at %I:%M %p')}")
        print(f"   Impact: '{event.impact}'")
        is_crit = "YES" if hasattr(event, 'is_critical') and event.is_critical else "NO"
        print(f"   Critical: {is_crit}")
else:
    print("\n❌ No HIGH impact events found!")
    print("\nLet's check what impacts we're seeing:")
    
    impacts = {}
    for event in all_events:
        impact_key = event.impact if event.impact else "EMPTY"
        if impact_key not in impacts:
            impacts[impact_key] = 0
        impacts[impact_key] += 1
    
    print("\n📊 Impact distribution:")
    for impact, count in impacts.items():
        print(f"   '{impact}': {count} events")
    
    print("\n🔍 Let's see what major currency events we have:")
    major_curr = ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'NZD', 'CAD', 'CHF']
    major_events = [e for e in all_events if e.currency in major_curr]
    print(f"\n   Major currency events: {len(major_events)}")
    
    print("\n   First 5 major currency events:")
    for event in major_events[:5]:
        print(f"\n   - {event.currency}: {event.event}")
        print(f"     Impact: '{event.impact}'")
        print(f"     Time: {event.time.strftime('%Y-%m-%d %H:%M')}")

print("\n" + "=" * 60)
print("🧪 Debug complete!")
