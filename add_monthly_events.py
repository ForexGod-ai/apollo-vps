#!/usr/bin/env python3
"""
Simple Manual Calendar Update - Add next month's high-impact events
Run this monthly: python3 add_monthly_events.py
"""

import json
from datetime import datetime
from typing import List, Dict

# HIGH IMPACT EVENTS FOR JANUARY 2026
# Update this list monthly with upcoming events
JANUARY_2026_EVENTS = [
    # Week 1
    {"date": "2026-01-03", "time": "15:00", "currency": "USD", "event": "ISM Manufacturing PMI", "impact": "High"},
    
    # Week 2
    {"date": "2026-01-06", "time": "10:00", "currency": "EUR", "event": "CPI Flash Estimate y/y", "impact": "High"},
    {"date": "2026-01-06", "time": "08:55", "currency": "EUR", "event": "German Unemployment Change", "impact": "Medium"},
    {"date": "2026-01-06", "time": "09:30", "currency": "GBP", "event": "Halifax HPI m/m", "impact": "Medium"},
    {"date": "2026-01-07", "time": "13:15", "currency": "USD", "event": "ADP Non-Farm Employment Change", "impact": "High"},
    {"date": "2026-01-08", "time": "13:30", "currency": "USD", "event": "Unemployment Claims", "impact": "Medium"},
    {"date": "2026-01-09", "time": "13:30", "currency": "CAD", "event": "Employment Change", "impact": "High"},
    {"date": "2026-01-09", "time": "13:30", "currency": "USD", "event": "Average Hourly Earnings m/m", "impact": "High"},
    {"date": "2026-01-09", "time": "13:30", "currency": "USD", "event": "Non-Farm Employment Change", "impact": "High"},
    {"date": "2026-01-09", "time": "13:30", "currency": "USD", "event": "Unemployment Rate", "impact": "High"},
    
    # Week 3
    {"date": "2026-01-13", "time": "13:30", "currency": "USD", "event": "Core CPI m/m", "impact": "High"},
    {"date": "2026-01-13", "time": "13:30", "currency": "USD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-01-14", "time": "13:30", "currency": "USD", "event": "Core PPI m/m", "impact": "High"},
    {"date": "2026-01-14", "time": "13:30", "currency": "USD", "event": "PPI m/m", "impact": "High"},
    {"date": "2026-01-15", "time": "13:30", "currency": "USD", "event": "Retail Sales m/m", "impact": "High"},
    {"date": "2026-01-15", "time": "13:30", "currency": "CAD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-01-16", "time": "13:30", "currency": "USD", "event": "Building Permits", "impact": "Medium"},
    {"date": "2026-01-16", "time": "15:00", "currency": "USD", "event": "Prelim UoM Consumer Sentiment", "impact": "High"},
    
    # Week 4
    {"date": "2026-01-21", "time": "07:00", "currency": "GBP", "event": "CPI y/y", "impact": "High"},
    {"date": "2026-01-21", "time": "13:30", "currency": "CAD", "event": "Core Retail Sales m/m", "impact": "High"},
    {"date": "2026-01-22", "time": "09:30", "currency": "GBP", "event": "Retail Sales m/m", "impact": "High"},
    {"date": "2026-01-23", "time": "08:30", "currency": "EUR", "event": "German Flash Manufacturing PMI", "impact": "High"},
    {"date": "2026-01-23", "time": "09:00", "currency": "EUR", "event": "Flash Manufacturing PMI", "impact": "High"},
    {"date": "2026-01-23", "time": "14:45", "currency": "USD", "event": "Flash Manufacturing PMI", "impact": "High"},
    {"date": "2026-01-23", "time": "15:00", "currency": "USD", "event": "New Home Sales", "impact": "Medium"},
    
    # Week 5
    {"date": "2026-01-27", "time": "15:00", "currency": "USD", "event": "CB Consumer Confidence", "impact": "High"},
    {"date": "2026-01-28", "time": "13:30", "currency": "USD", "event": "Core Durable Goods Orders m/m", "impact": "High"},
    {"date": "2026-01-28", "time": "13:30", "currency": "USD", "event": "Durable Goods Orders m/m", "impact": "Medium"},
    {"date": "2026-01-29", "time": "13:30", "currency": "USD", "event": "Advance GDP q/q", "impact": "High"},
    {"date": "2026-01-29", "time": "15:00", "currency": "USD", "event": "Pending Home Sales m/m", "impact": "Medium"},
    {"date": "2026-01-29", "time": "19:00", "currency": "USD", "event": "FOMC Statement", "impact": "High"},
    {"date": "2026-01-29", "time": "19:30", "currency": "USD", "event": "FOMC Press Conference", "impact": "High"},
    {"date": "2026-01-30", "time": "13:15", "currency": "EUR", "event": "ECB Interest Rate Decision", "impact": "High"},
    {"date": "2026-01-30", "time": "13:45", "currency": "EUR", "event": "ECB Press Conference", "impact": "High"},
]


def update_calendar():
    """Add events to economic_calendar.json"""
    
    calendar_file = "economic_calendar.json"
    
    try:
        # Load existing calendar
        with open(calendar_file, 'r', encoding='utf-8') as f:
            calendar_data = json.load(f)
        
        # Update with new events
        calendar_data["custom_events_january_2026"] = JANUARY_2026_EVENTS
        
        # Save
        with open(calendar_file, 'w', encoding='utf-8') as f:
            json.dump(calendar_data, f, indent=2, ensure_ascii=False)
        
        print("✅ Calendar updated successfully!")
        print(f"📅 Added {len(JANUARY_2026_EVENTS)} events for January 2026")
        
        # Show summary
        high_impact = [e for e in JANUARY_2026_EVENTS if e['impact'] == 'High']
        print(f"🚨 {len(high_impact)} HIGH impact events")
        
        currencies = {}
        for event in JANUARY_2026_EVENTS:
            curr = event['currency']
            currencies[curr] = currencies.get(curr, 0) + 1
        
        print("\n📊 Events by currency:")
        for curr, count in sorted(currencies.items()):
            print(f"   {curr}: {count}")
            
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("📅 MANUAL CALENDAR UPDATE - JANUARY 2026")
    print("=" * 60)
    print()
    
    update_calendar()
    
    print()
    print("💡 To update for next month:")
    print("   1. Edit JANUARY_2026_EVENTS in this file")
    print("   2. Change section name to next month")
    print("   3. Run: python3 add_monthly_events.py")
    print("=" * 60)
