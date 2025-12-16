#!/usr/bin/env python3
"""
Manual Calendar Update Helper
Helps you quickly add events to economic_calendar.json

Usage:
    python3 update_calendar.py
    
Then follow the prompts to add events for the upcoming week
"""

import json
from datetime import datetime
from pathlib import Path

def load_calendar():
    """Load current calendar"""
    calendar_file = Path(__file__).parent / 'economic_calendar.json'
    with open(calendar_file, 'r') as f:
        return json.load(f)

def save_calendar(data):
    """Save calendar with pretty formatting"""
    calendar_file = Path(__file__).parent / 'economic_calendar.json'
    with open(calendar_file, 'w') as f:
        json.dump(data, f, indent=2)

def add_event_interactive():
    """Interactively add a new event"""
    print("\n" + "="*50)
    print("📅 ADD NEW EVENT TO CALENDAR")
    print("="*50)
    
    # Date
    date_str = input("\n📆 Date (YYYY-MM-DD, e.g., 2025-12-20): ").strip()
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
    except:
        print("❌ Invalid date format!")
        return None
    
    # Time
    time_str = input("⏰ Time (HH:MM in UTC, e.g., 13:30): ").strip()
    try:
        datetime.strptime(time_str, '%H:%M')
    except:
        print("❌ Invalid time format!")
        return None
    
    # Currency
    print("\n💱 Currency options: USD, EUR, GBP, JPY, AUD, NZD, CAD, CHF")
    currency = input("Currency: ").strip().upper()
    
    # Event name
    event_name = input("📰 Event name (e.g., 'Non-Farm Payrolls'): ").strip()
    
    # Impact
    print("\n🎯 Impact level: High, Medium, Low")
    impact = input("Impact: ").strip().capitalize()
    
    # Optional forecast/previous
    forecast = input("📊 Forecast (optional, press Enter to skip): ").strip()
    previous = input("📊 Previous (optional, press Enter to skip): ").strip()
    
    event = {
        "date": date_str,
        "time": time_str,
        "currency": currency,
        "event": event_name,
        "impact": impact
    }
    
    if forecast:
        event["forecast"] = forecast
    if previous:
        event["previous"] = previous
    
    return event

def update_week_range():
    """Update the week range in calendar description"""
    print("\n📅 What week are you updating?")
    week_start = input("Week start date (e.g., December 16): ").strip()
    week_end = input("Week end date (e.g., December 20): ").strip()
    
    return f"custom_events_{week_start}_to_{week_end}"

def main():
    print("\n" + "="*60)
    print("🗓️  ECONOMIC CALENDAR UPDATE TOOL")
    print("="*60)
    
    # Load current calendar
    calendar = load_calendar()
    
    # Get current custom events key
    custom_keys = [k for k in calendar.keys() if k.startswith('custom_events_')]
    if custom_keys:
        current_key = custom_keys[0]
        print(f"\n📋 Current section: {current_key}")
        print(f"   Events: {len(calendar[current_key])}")
    
    print("\nOptions:")
    print("1. Add events to current section")
    print("2. Create new week section")
    print("3. View all events")
    print("4. Exit")
    
    choice = input("\nChoice (1-4): ").strip()
    
    if choice == '1':
        # Add to current section
        events = calendar.get(current_key, [])
        
        print(f"\n➕ Adding events to {current_key}")
        
        while True:
            event = add_event_interactive()
            if event:
                events.append(event)
                print(f"✅ Added: {event['date']} {event['time']} - {event['currency']} {event['event']}")
            
            another = input("\nAdd another event? (y/n): ").strip().lower()
            if another != 'y':
                break
        
        calendar[current_key] = events
        save_calendar(calendar)
        print(f"\n✅ Saved {len(events)} events to {current_key}")
    
    elif choice == '2':
        # Create new section
        new_key = update_week_range()
        calendar[new_key] = []
        
        print(f"\n✅ Created new section: {new_key}")
        print("Now adding events...")
        
        while True:
            event = add_event_interactive()
            if event:
                calendar[new_key].append(event)
                print(f"✅ Added: {event['date']} {event['time']} - {event['currency']} {event['event']}")
            
            another = input("\nAdd another event? (y/n): ").strip().lower()
            if another != 'y':
                break
        
        save_calendar(calendar)
        print(f"\n✅ Saved {len(calendar[new_key])} events to {new_key}")
    
    elif choice == '3':
        # View all events
        for key in calendar.keys():
            if key.startswith('custom_events_'):
                events = calendar[key]
                print(f"\n📅 {key}:")
                for e in events:
                    print(f"  {e['date']} {e.get('time', 'N/A')} - {e['currency']} - {e['event']}")
    
    print("\n✅ Done!\n")

if __name__ == "__main__":
    main()
