#!/usr/bin/env python3
"""
Simple Manual Calendar Update - Add next month's high-impact events
Run this monthly: python3 add_monthly_events.py
"""

import json
from datetime import datetime
from typing import List, Dict

# HIGH IMPACT EVENTS FOR JUNE 2026
# Verificat manual — surse: ForexFactory, Investing.com, BIS calendar
# Toate orele sunt GMT (UTC+0). Ajustați dacă VPS-ul rulează pe alt timezone.
JUNE_2026_EVENTS = [
    # ══════════════════════════════════════════════════════════
    # SĂPTĂMÂNA 1 (2-5 Iunie) — NFP Week + ECB + BOC
    # ══════════════════════════════════════════════════════════
    {"date": "2026-06-01", "time": "15:00", "currency": "USD", "event": "ISM Manufacturing PMI", "impact": "High"},

    {"date": "2026-06-03", "time": "13:15", "currency": "USD", "event": "ADP Non-Farm Employment Change", "impact": "High"},
    {"date": "2026-06-03", "time": "14:45", "currency": "CAD", "event": "BOC Interest Rate Decision", "impact": "High"},
    {"date": "2026-06-03", "time": "15:30", "currency": "CAD", "event": "BOC Press Conference", "impact": "High"},

    {"date": "2026-06-04", "time": "07:55", "currency": "EUR", "event": "German Unemployment Change", "impact": "Medium"},
    {"date": "2026-06-04", "time": "13:15", "currency": "EUR", "event": "ECB Interest Rate Decision", "impact": "High"},
    {"date": "2026-06-04", "time": "13:30", "currency": "USD", "event": "Unemployment Claims", "impact": "Medium"},
    {"date": "2026-06-04", "time": "13:45", "currency": "EUR", "event": "ECB Press Conference", "impact": "High"},

    {"date": "2026-06-05", "time": "13:30", "currency": "USD", "event": "Average Hourly Earnings m/m", "impact": "High"},
    {"date": "2026-06-05", "time": "13:30", "currency": "USD", "event": "Non-Farm Employment Change", "impact": "High"},
    {"date": "2026-06-05", "time": "13:30", "currency": "USD", "event": "Unemployment Rate", "impact": "High"},
    {"date": "2026-06-05", "time": "13:30", "currency": "CAD", "event": "Employment Change", "impact": "High"},
    {"date": "2026-06-05", "time": "15:00", "currency": "USD", "event": "ISM Services PMI", "impact": "High"},

    # ══════════════════════════════════════════════════════════
    # SĂPTĂMÂNA 2 (8-12 Iunie) — RBA + CPI USD + PPI USD
    # ══════════════════════════════════════════════════════════
    {"date": "2026-06-09", "time": "04:30", "currency": "AUD", "event": "RBA Interest Rate Decision", "impact": "High"},
    {"date": "2026-06-09", "time": "05:30", "currency": "AUD", "event": "RBA Press Conference", "impact": "High"},

    {"date": "2026-06-11", "time": "13:30", "currency": "USD", "event": "Core CPI m/m", "impact": "High"},
    {"date": "2026-06-11", "time": "13:30", "currency": "USD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-06-11", "time": "13:30", "currency": "USD", "event": "CPI y/y", "impact": "High"},

    {"date": "2026-06-12", "time": "13:30", "currency": "USD", "event": "Core PPI m/m", "impact": "High"},
    {"date": "2026-06-12", "time": "13:30", "currency": "USD", "event": "PPI m/m", "impact": "High"},
    {"date": "2026-06-12", "time": "13:30", "currency": "USD", "event": "Unemployment Claims", "impact": "Medium"},

    {"date": "2026-06-13", "time": "15:00", "currency": "USD", "event": "Prelim UoM Consumer Sentiment", "impact": "High"},

    # ══════════════════════════════════════════════════════════
    # SĂPTĂMÂNA 3 (15-19 Iunie) — FOMC + BOE + SNB + BOJ
    # ══════════════════════════════════════════════════════════
    {"date": "2026-06-16", "time": "07:00", "currency": "GBP", "event": "CPI y/y", "impact": "High"},
    {"date": "2026-06-16", "time": "07:00", "currency": "GBP", "event": "Core CPI y/y", "impact": "High"},

    {"date": "2026-06-17", "time": "03:00", "currency": "JPY", "event": "BOJ Interest Rate Decision", "impact": "High"},
    {"date": "2026-06-17", "time": "06:00", "currency": "JPY", "event": "BOJ Press Conference", "impact": "High"},
    {"date": "2026-06-17", "time": "13:30", "currency": "USD", "event": "Retail Sales m/m", "impact": "High"},
    {"date": "2026-06-17", "time": "13:30", "currency": "CAD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-06-17", "time": "13:30", "currency": "CAD", "event": "Core CPI m/m", "impact": "High"},

    {"date": "2026-06-18", "time": "19:00", "currency": "USD", "event": "FOMC Statement", "impact": "High"},
    {"date": "2026-06-18", "time": "19:30", "currency": "USD", "event": "FOMC Press Conference", "impact": "High"},

    {"date": "2026-06-19", "time": "07:30", "currency": "CHF", "event": "SNB Interest Rate Decision", "impact": "High"},
    {"date": "2026-06-19", "time": "11:00", "currency": "GBP", "event": "BOE Interest Rate Decision", "impact": "High"},
    {"date": "2026-06-19", "time": "11:00", "currency": "GBP", "event": "BOE MPC Meeting Minutes", "impact": "High"},
    {"date": "2026-06-19", "time": "13:30", "currency": "USD", "event": "Unemployment Claims", "impact": "Medium"},

    # ══════════════════════════════════════════════════════════
    # SĂPTĂMÂNA 4 (22-26 Iunie) — Flash PMIs + Durable Goods + GDP + PCE
    # ══════════════════════════════════════════════════════════
    {"date": "2026-06-22", "time": "08:30", "currency": "EUR", "event": "German Flash Manufacturing PMI", "impact": "High"},
    {"date": "2026-06-22", "time": "08:30", "currency": "EUR", "event": "German Flash Services PMI", "impact": "High"},

    {"date": "2026-06-23", "time": "08:00", "currency": "EUR", "event": "Flash Manufacturing PMI", "impact": "High"},
    {"date": "2026-06-23", "time": "08:30", "currency": "GBP", "event": "Flash Manufacturing PMI", "impact": "High"},
    {"date": "2026-06-23", "time": "08:30", "currency": "GBP", "event": "Flash Services PMI", "impact": "High"},
    {"date": "2026-06-23", "time": "15:00", "currency": "USD", "event": "CB Consumer Confidence", "impact": "High"},
    {"date": "2026-06-23", "time": "15:00", "currency": "USD", "event": "New Home Sales", "impact": "Medium"},

    {"date": "2026-06-24", "time": "13:30", "currency": "USD", "event": "Core Durable Goods Orders m/m", "impact": "High"},
    {"date": "2026-06-24", "time": "13:30", "currency": "USD", "event": "Durable Goods Orders m/m", "impact": "Medium"},
    {"date": "2026-06-24", "time": "14:45", "currency": "USD", "event": "Flash Manufacturing PMI", "impact": "High"},
    {"date": "2026-06-24", "time": "14:45", "currency": "USD", "event": "Flash Services PMI", "impact": "High"},

    {"date": "2026-06-25", "time": "13:30", "currency": "USD", "event": "Final GDP q/q", "impact": "High"},
    {"date": "2026-06-25", "time": "13:30", "currency": "USD", "event": "Unemployment Claims", "impact": "Medium"},

    {"date": "2026-06-26", "time": "13:30", "currency": "USD", "event": "Core PCE Price Index m/m", "impact": "High"},
    {"date": "2026-06-26", "time": "13:30", "currency": "USD", "event": "Personal Income m/m", "impact": "Medium"},
    {"date": "2026-06-26", "time": "13:30", "currency": "CAD", "event": "GDP m/m", "impact": "High"},

    # ══════════════════════════════════════════════════════════
    # SĂPTĂMÂNA 5 (29-30 Iunie) — Închidere lună
    # ══════════════════════════════════════════════════════════
    {"date": "2026-06-30", "time": "09:00", "currency": "EUR", "event": "CPI Flash Estimate y/y", "impact": "High"},
    {"date": "2026-06-30", "time": "14:45", "currency": "USD", "event": "Chicago PMI", "impact": "High"},
]


def update_calendar():
    """Add events to economic_calendar.json"""
    
    calendar_file = "economic_calendar.json"
    
    try:
        # Load existing calendar
        with open(calendar_file, 'r', encoding='utf-8') as f:
            calendar_data = json.load(f)
        
        # Update with new events
        calendar_data["custom_events_june_2026"] = JUNE_2026_EVENTS
        
        # Save
        with open(calendar_file, 'w', encoding='utf-8') as f:
            json.dump(calendar_data, f, indent=2, ensure_ascii=False)
        
        print("✅ Calendar updated successfully!")
        print(f"📅 Added {len(JUNE_2026_EVENTS)} events for June 2026")
        
        # Show summary
        high_impact = [e for e in JUNE_2026_EVENTS if e['impact'] == 'High']
        print(f"🚨 {len(high_impact)} HIGH impact events")
        
        currencies = {}
        for event in JUNE_2026_EVENTS:
            curr = event['currency']
            currencies[curr] = currencies.get(curr, 0) + 1
        
        print("\n📊 Events by currency:")
        for curr, count in sorted(currencies.items()):
            print(f"   {curr}: {count}")
            
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("📅 MANUAL CALENDAR UPDATE - JUNE 2026")
    print("=" * 60)
    print()
    
    update_calendar()
    
    print()
    print("💡 To update for next month:")
    print("   1. Edit JUNE_2026_EVENTS in this file")
    print("   2. Change section name to next month")
    print("   3. Run: python3 add_monthly_events.py")
    print("=" * 60)
