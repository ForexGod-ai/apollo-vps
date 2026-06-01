#!/usr/bin/env python3
"""
Simple Manual Calendar Update - Add next month's high-impact events
Run this monthly: python3 add_monthly_events.py
"""

import json
from datetime import datetime
from typing import List, Dict

# HIGH IMPACT EVENTS FOR JUNE 2026
# Verificat manual față de ForexFactory — toate orele sunt GMT (UTC+0)
# NOTĂ TIMEZONE: ForexFactory afișat în EEST (UTC+3, ora României în vară)
# Conversie: GMT = ora FF - 3h  |  Ex: FF 15:30 → GMT 12:30
JUNE_2026_EVENTS = [
    # ══════════════════════════════════════════════════════════
    # SĂPTĂMÂNA 1 (1-5 Iunie) — ISM + ADP + ISM Services + NFP Week
    # ══════════════════════════════════════════════════════════
    # Lun 1 Iun
    {"date": "2026-06-01", "time": "14:00", "currency": "USD", "event": "ISM Manufacturing PMI", "impact": "High"},

    # Mar 2 Iun
    {"date": "2026-06-02", "time": "14:00", "currency": "GBP", "event": "BOE Gov Bailey Speaks", "impact": "High"},

    # Mie 3 Iun
    {"date": "2026-06-03", "time": "01:30", "currency": "AUD", "event": "GDP q/q", "impact": "High"},
    {"date": "2026-06-03", "time": "08:30", "currency": "JPY", "event": "BOJ Gov Ueda Speaks", "impact": "High"},
    {"date": "2026-06-03", "time": "12:15", "currency": "USD", "event": "ADP Non-Farm Employment Change", "impact": "High"},
    {"date": "2026-06-03", "time": "14:00", "currency": "USD", "event": "ISM Services PMI", "impact": "High"},

    # Joi 4 Iun
    {"date": "2026-06-04", "time": "05:00", "currency": "AUD", "event": "RBA Gov Bullock Speaks", "impact": "High"},
    {"date": "2026-06-04", "time": "15:40", "currency": "GBP", "event": "BOE Gov Bailey Speaks", "impact": "High"},

    # Vin 5 Iun — NFP
    {"date": "2026-06-05", "time": "12:30", "currency": "CAD", "event": "Employment Change", "impact": "High"},
    {"date": "2026-06-05", "time": "12:30", "currency": "CAD", "event": "Unemployment Rate", "impact": "High"},
    {"date": "2026-06-05", "time": "12:30", "currency": "USD", "event": "Average Hourly Earnings m/m", "impact": "High"},
    {"date": "2026-06-05", "time": "12:30", "currency": "USD", "event": "Non-Farm Employment Change", "impact": "High"},
    {"date": "2026-06-05", "time": "12:30", "currency": "USD", "event": "Unemployment Rate", "impact": "High"},

    # ══════════════════════════════════════════════════════════
    # SĂPTĂMÂNA 2 (8-13 Iunie) — CPI USD + BOC + ECB + PPI + GBP GDP
    # ══════════════════════════════════════════════════════════
    # Mie 10 Iun
    {"date": "2026-06-10", "time": "12:30", "currency": "USD", "event": "Core CPI m/m", "impact": "High"},
    {"date": "2026-06-10", "time": "12:30", "currency": "USD", "event": "Core CPI y/y", "impact": "High"},
    {"date": "2026-06-10", "time": "12:30", "currency": "USD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-06-10", "time": "12:30", "currency": "USD", "event": "CPI y/y", "impact": "High"},
    {"date": "2026-06-10", "time": "13:45", "currency": "CAD", "event": "BOC Rate Statement", "impact": "High"},
    {"date": "2026-06-10", "time": "13:45", "currency": "CAD", "event": "Overnight Rate", "impact": "High"},
    {"date": "2026-06-10", "time": "14:30", "currency": "CAD", "event": "BOC Press Conference", "impact": "High"},

    # Joi 11 Iun
    {"date": "2026-06-11", "time": "12:15", "currency": "EUR", "event": "Main Refinancing Rate", "impact": "High"},
    {"date": "2026-06-11", "time": "12:15", "currency": "EUR", "event": "ECB Monetary Policy Statement", "impact": "High"},
    {"date": "2026-06-11", "time": "12:30", "currency": "USD", "event": "Core PPI m/m", "impact": "High"},
    {"date": "2026-06-11", "time": "12:30", "currency": "USD", "event": "PPI m/m", "impact": "High"},
    {"date": "2026-06-11", "time": "12:45", "currency": "EUR", "event": "ECB Press Conference", "impact": "High"},

    # Vin 12 Iun
    {"date": "2026-06-12", "time": "06:00", "currency": "GBP", "event": "GDP m/m", "impact": "High"},

    # ══════════════════════════════════════════════════════════
    # SĂPTĂMÂNA 3 (14-20 Iunie) — BOJ + RBA + GBP CPI + FOMC + NZD + BOE + SNB
    # ══════════════════════════════════════════════════════════
    # Mar 16 Iun — BOJ (Tentative) + RBA
    {"date": "2026-06-16", "time": "00:00", "currency": "JPY", "event": "BOJ Policy Rate", "impact": "High"},
    {"date": "2026-06-16", "time": "00:00", "currency": "JPY", "event": "BOJ Monetary Policy Statement", "impact": "High"},
    {"date": "2026-06-16", "time": "04:30", "currency": "AUD", "event": "Cash Rate", "impact": "High"},
    {"date": "2026-06-16", "time": "04:30", "currency": "AUD", "event": "RBA Rate Statement", "impact": "High"},
    {"date": "2026-06-16", "time": "05:30", "currency": "AUD", "event": "RBA Press Conference", "impact": "High"},
    {"date": "2026-06-16", "time": "06:00", "currency": "JPY", "event": "BOJ Press Conference", "impact": "High"},

    # Mie 17 Iun — GBP CPI + FOMC + NZD GDP
    {"date": "2026-06-17", "time": "06:00", "currency": "GBP", "event": "CPI y/y", "impact": "High"},
    {"date": "2026-06-17", "time": "18:00", "currency": "USD", "event": "Federal Funds Rate", "impact": "High"},
    {"date": "2026-06-17", "time": "18:00", "currency": "USD", "event": "FOMC Economic Projections", "impact": "High"},
    {"date": "2026-06-17", "time": "18:00", "currency": "USD", "event": "FOMC Statement", "impact": "High"},
    {"date": "2026-06-17", "time": "18:30", "currency": "USD", "event": "FOMC Press Conference", "impact": "High"},
    {"date": "2026-06-17", "time": "22:45", "currency": "NZD", "event": "GDP q/q", "impact": "High"},

    # Joi 18 Iun — GBP Claimant + SNB + BOE
    {"date": "2026-06-18", "time": "06:00", "currency": "GBP", "event": "Claimant Count Change", "impact": "High"},
    {"date": "2026-06-18", "time": "07:30", "currency": "CHF", "event": "SNB Monetary Policy Assessment", "impact": "High"},
    {"date": "2026-06-18", "time": "07:30", "currency": "CHF", "event": "SNB Policy Rate", "impact": "High"},
    {"date": "2026-06-18", "time": "08:00", "currency": "CHF", "event": "SNB Press Conference", "impact": "High"},
    {"date": "2026-06-18", "time": "11:00", "currency": "GBP", "event": "Monetary Policy Summary", "impact": "High"},
    {"date": "2026-06-18", "time": "11:00", "currency": "GBP", "event": "MPC Official Bank Rate Votes", "impact": "High"},
    {"date": "2026-06-18", "time": "11:00", "currency": "GBP", "event": "Official Bank Rate", "impact": "High"},

    # ══════════════════════════════════════════════════════════
    # SĂPTĂMÂNA 4 (21-27 Iunie) — CAD CPI + GBP PMI + AUD CPI + AUD Jobs + PCE + GDP
    # ══════════════════════════════════════════════════════════
    # Lun 22 Iun — CAD CPI
    {"date": "2026-06-22", "time": "12:30", "currency": "CAD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-06-22", "time": "12:30", "currency": "CAD", "event": "Median CPI y/y", "impact": "High"},
    {"date": "2026-06-22", "time": "12:30", "currency": "CAD", "event": "Trimmed CPI y/y", "impact": "High"},

    # Mar 23 Iun — GBP Flash PMIs
    {"date": "2026-06-23", "time": "08:30", "currency": "GBP", "event": "Flash Manufacturing PMI", "impact": "High"},
    {"date": "2026-06-23", "time": "08:30", "currency": "GBP", "event": "Flash Services PMI", "impact": "High"},

    # Mie 24 Iun — AUD CPI
    {"date": "2026-06-24", "time": "01:30", "currency": "AUD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-06-24", "time": "01:30", "currency": "AUD", "event": "CPI y/y", "impact": "High"},
    {"date": "2026-06-24", "time": "01:30", "currency": "AUD", "event": "Trimmed Mean CPI m/m", "impact": "High"},

    # Joi 25 Iun — AUD Jobs + USD Core PCE + Final GDP
    {"date": "2026-06-25", "time": "01:30", "currency": "AUD", "event": "Employment Change", "impact": "High"},
    {"date": "2026-06-25", "time": "01:30", "currency": "AUD", "event": "Unemployment Rate", "impact": "High"},
    {"date": "2026-06-25", "time": "12:30", "currency": "USD", "event": "Core PCE Price Index m/m", "impact": "High"},
    {"date": "2026-06-25", "time": "12:30", "currency": "USD", "event": "Final GDP q/q", "impact": "High"},

    # ══════════════════════════════════════════════════════════
    # SĂPTĂMÂNA 5 (30 Iunie) — Închidere lună
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
