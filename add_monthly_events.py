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
    {"date": "2026-06-01", "time": "14:00", "currency": "USD", "event": "ISM Manufacturing PMI", "impact": "High"},
    {"date": "2026-06-02", "time": "14:00", "currency": "GBP", "event": "BOE Gov Bailey Speaks", "impact": "High"},
    {"date": "2026-06-03", "time": "01:30", "currency": "AUD", "event": "GDP q/q", "impact": "High"},
    {"date": "2026-06-03", "time": "08:30", "currency": "JPY", "event": "BOJ Gov Ueda Speaks", "impact": "High"},
    {"date": "2026-06-03", "time": "12:15", "currency": "USD", "event": "ADP Non-Farm Employment Change", "impact": "High"},
    {"date": "2026-06-03", "time": "14:00", "currency": "USD", "event": "ISM Services PMI", "impact": "High"},
    {"date": "2026-06-04", "time": "05:00", "currency": "AUD", "event": "RBA Gov Bullock Speaks", "impact": "High"},
    {"date": "2026-06-04", "time": "15:40", "currency": "GBP", "event": "BOE Gov Bailey Speaks", "impact": "High"},
    {"date": "2026-06-05", "time": "12:30", "currency": "CAD", "event": "Employment Change", "impact": "High"},
    {"date": "2026-06-05", "time": "12:30", "currency": "CAD", "event": "Unemployment Rate", "impact": "High"},
    {"date": "2026-06-05", "time": "12:30", "currency": "USD", "event": "Average Hourly Earnings m/m", "impact": "High"},
    {"date": "2026-06-05", "time": "12:30", "currency": "USD", "event": "Non-Farm Employment Change", "impact": "High"},
    {"date": "2026-06-05", "time": "12:30", "currency": "USD", "event": "Unemployment Rate", "impact": "High"},
    {"date": "2026-06-10", "time": "12:30", "currency": "USD", "event": "Core CPI m/m", "impact": "High"},
    {"date": "2026-06-10", "time": "12:30", "currency": "USD", "event": "Core CPI y/y", "impact": "High"},
    {"date": "2026-06-10", "time": "12:30", "currency": "USD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-06-10", "time": "12:30", "currency": "USD", "event": "CPI y/y", "impact": "High"},
    {"date": "2026-06-10", "time": "13:45", "currency": "CAD", "event": "BOC Rate Statement", "impact": "High"},
    {"date": "2026-06-10", "time": "13:45", "currency": "CAD", "event": "Overnight Rate", "impact": "High"},
    {"date": "2026-06-10", "time": "14:30", "currency": "CAD", "event": "BOC Press Conference", "impact": "High"},
    {"date": "2026-06-11", "time": "12:15", "currency": "EUR", "event": "Main Refinancing Rate", "impact": "High"},
    {"date": "2026-06-11", "time": "12:15", "currency": "EUR", "event": "ECB Monetary Policy Statement", "impact": "High"},
    {"date": "2026-06-11", "time": "12:30", "currency": "USD", "event": "Core PPI m/m", "impact": "High"},
    {"date": "2026-06-11", "time": "12:30", "currency": "USD", "event": "PPI m/m", "impact": "High"},
    {"date": "2026-06-11", "time": "12:45", "currency": "EUR", "event": "ECB Press Conference", "impact": "High"},
    {"date": "2026-06-12", "time": "06:00", "currency": "GBP", "event": "GDP m/m", "impact": "High"},
    {"date": "2026-06-16", "time": "00:00", "currency": "JPY", "event": "BOJ Policy Rate", "impact": "High"},
    {"date": "2026-06-16", "time": "00:00", "currency": "JPY", "event": "BOJ Monetary Policy Statement", "impact": "High"},
    {"date": "2026-06-16", "time": "04:30", "currency": "AUD", "event": "Cash Rate", "impact": "High"},
    {"date": "2026-06-16", "time": "04:30", "currency": "AUD", "event": "RBA Rate Statement", "impact": "High"},
    {"date": "2026-06-16", "time": "05:30", "currency": "AUD", "event": "RBA Press Conference", "impact": "High"},
    {"date": "2026-06-16", "time": "06:00", "currency": "JPY", "event": "BOJ Press Conference", "impact": "High"},
    {"date": "2026-06-17", "time": "06:00", "currency": "GBP", "event": "CPI y/y", "impact": "High"},
    {"date": "2026-06-17", "time": "18:00", "currency": "USD", "event": "Federal Funds Rate", "impact": "High"},
    {"date": "2026-06-17", "time": "18:00", "currency": "USD", "event": "FOMC Economic Projections", "impact": "High"},
    {"date": "2026-06-17", "time": "18:00", "currency": "USD", "event": "FOMC Statement", "impact": "High"},
    {"date": "2026-06-17", "time": "18:30", "currency": "USD", "event": "FOMC Press Conference", "impact": "High"},
    {"date": "2026-06-17", "time": "22:45", "currency": "NZD", "event": "GDP q/q", "impact": "High"},
    {"date": "2026-06-18", "time": "06:00", "currency": "GBP", "event": "Claimant Count Change", "impact": "High"},
    {"date": "2026-06-18", "time": "07:30", "currency": "CHF", "event": "SNB Monetary Policy Assessment", "impact": "High"},
    {"date": "2026-06-18", "time": "07:30", "currency": "CHF", "event": "SNB Policy Rate", "impact": "High"},
    {"date": "2026-06-18", "time": "08:00", "currency": "CHF", "event": "SNB Press Conference", "impact": "High"},
    {"date": "2026-06-18", "time": "11:00", "currency": "GBP", "event": "Monetary Policy Summary", "impact": "High"},
    {"date": "2026-06-18", "time": "11:00", "currency": "GBP", "event": "MPC Official Bank Rate Votes", "impact": "High"},
    {"date": "2026-06-18", "time": "11:00", "currency": "GBP", "event": "Official Bank Rate", "impact": "High"},
    {"date": "2026-06-22", "time": "12:30", "currency": "CAD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-06-22", "time": "12:30", "currency": "CAD", "event": "Median CPI y/y", "impact": "High"},
    {"date": "2026-06-22", "time": "12:30", "currency": "CAD", "event": "Trimmed CPI y/y", "impact": "High"},
    {"date": "2026-06-23", "time": "08:30", "currency": "GBP", "event": "Flash Manufacturing PMI", "impact": "High"},
    {"date": "2026-06-23", "time": "08:30", "currency": "GBP", "event": "Flash Services PMI", "impact": "High"},
    {"date": "2026-06-24", "time": "01:30", "currency": "AUD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-06-24", "time": "01:30", "currency": "AUD", "event": "CPI y/y", "impact": "High"},
    {"date": "2026-06-24", "time": "01:30", "currency": "AUD", "event": "Trimmed Mean CPI m/m", "impact": "High"},
    {"date": "2026-06-25", "time": "01:30", "currency": "AUD", "event": "Employment Change", "impact": "High"},
    {"date": "2026-06-25", "time": "01:30", "currency": "AUD", "event": "Unemployment Rate", "impact": "High"},
    {"date": "2026-06-25", "time": "12:30", "currency": "USD", "event": "Core PCE Price Index m/m", "impact": "High"},
    {"date": "2026-06-25", "time": "12:30", "currency": "USD", "event": "Final GDP q/q", "impact": "High"},
    {"date": "2026-06-30", "time": "09:00", "currency": "EUR", "event": "CPI Flash Estimate y/y", "impact": "High"},
    {"date": "2026-06-30", "time": "12:30", "currency": "CAD", "event": "GDP m/m", "impact": "High"},
    {"date": "2026-06-30", "time": "14:45", "currency": "USD", "event": "Chicago PMI", "impact": "High"},
]

# HIGH IMPACT EVENTS FOR JULY 2026 — ForexFactory EEST → UTC (−3h)
JULY_2026_EVENTS = [
    # Săpt 28 Jun – 4 Jul
    {"date": "2026-07-01", "time": "14:00", "currency": "USD", "event": "ISM Manufacturing PMI", "impact": "High"},
    {"date": "2026-07-02", "time": "12:30", "currency": "USD", "event": "Average Hourly Earnings m/m", "impact": "High"},
    {"date": "2026-07-02", "time": "12:30", "currency": "USD", "event": "Non-Farm Employment Change", "impact": "High"},
    {"date": "2026-07-02", "time": "12:30", "currency": "USD", "event": "Unemployment Rate", "impact": "High"},
    # Săpt 5–11 Jul
    {"date": "2026-07-06", "time": "14:00", "currency": "USD", "event": "ISM Services PMI", "impact": "High"},
    {"date": "2026-07-08", "time": "02:00", "currency": "NZD", "event": "Official Cash Rate", "impact": "High"},
    {"date": "2026-07-08", "time": "02:00", "currency": "NZD", "event": "RBNZ Rate Statement", "impact": "High"},
    {"date": "2026-07-08", "time": "03:00", "currency": "NZD", "event": "RBNZ Press Conference", "impact": "High"},
    {"date": "2026-07-08", "time": "18:00", "currency": "USD", "event": "FOMC Meeting Minutes", "impact": "High"},
    {"date": "2026-07-10", "time": "12:30", "currency": "CAD", "event": "Employment Change", "impact": "High"},
    {"date": "2026-07-10", "time": "12:30", "currency": "CAD", "event": "Unemployment Rate", "impact": "High"},
    # Săpt 12–18 Jul
    {"date": "2026-07-14", "time": "12:30", "currency": "USD", "event": "Core CPI m/m", "impact": "High"},
    {"date": "2026-07-14", "time": "12:30", "currency": "USD", "event": "Core CPI y/y", "impact": "High"},
    {"date": "2026-07-14", "time": "12:30", "currency": "USD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-07-14", "time": "12:30", "currency": "USD", "event": "CPI y/y", "impact": "High"},
    {"date": "2026-07-15", "time": "12:30", "currency": "USD", "event": "Core PPI m/m", "impact": "High"},
    {"date": "2026-07-15", "time": "12:30", "currency": "USD", "event": "PPI m/m", "impact": "High"},
    {"date": "2026-07-15", "time": "13:45", "currency": "CAD", "event": "BOC Monetary Policy Report", "impact": "High"},
    {"date": "2026-07-15", "time": "13:45", "currency": "CAD", "event": "BOC Rate Statement", "impact": "High"},
    {"date": "2026-07-15", "time": "13:45", "currency": "CAD", "event": "Overnight Rate", "impact": "High"},
    {"date": "2026-07-15", "time": "14:30", "currency": "CAD", "event": "BOC Press Conference", "impact": "High"},
    {"date": "2026-07-16", "time": "06:00", "currency": "GBP", "event": "GDP m/m", "impact": "High"},
    {"date": "2026-07-16", "time": "12:30", "currency": "USD", "event": "Core Retail Sales m/m", "impact": "High"},
    {"date": "2026-07-16", "time": "12:30", "currency": "USD", "event": "Retail Sales m/m", "impact": "High"},
    # Săpt 19–25 Jul
    {"date": "2026-07-20", "time": "12:30", "currency": "CAD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-07-20", "time": "12:30", "currency": "CAD", "event": "Median CPI y/y", "impact": "High"},
    {"date": "2026-07-20", "time": "12:30", "currency": "CAD", "event": "Trimmed CPI y/y", "impact": "High"},
    {"date": "2026-07-20", "time": "22:45", "currency": "NZD", "event": "CPI q/q", "impact": "High"},
    {"date": "2026-07-21", "time": "06:00", "currency": "GBP", "event": "Claimant Count Change", "impact": "High"},
    {"date": "2026-07-22", "time": "06:00", "currency": "GBP", "event": "CPI y/y", "impact": "High"},
    {"date": "2026-07-23", "time": "01:30", "currency": "AUD", "event": "Employment Change", "impact": "High"},
    {"date": "2026-07-23", "time": "01:30", "currency": "AUD", "event": "Unemployment Rate", "impact": "High"},
    {"date": "2026-07-23", "time": "12:15", "currency": "EUR", "event": "Main Refinancing Rate", "impact": "High"},
    {"date": "2026-07-23", "time": "12:15", "currency": "EUR", "event": "Monetary Policy Statement", "impact": "High"},
    {"date": "2026-07-23", "time": "12:45", "currency": "EUR", "event": "ECB Press Conference", "impact": "High"},
    # Săpt 26 Jul – 1 Aug
    {"date": "2026-07-29", "time": "01:30", "currency": "AUD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-07-29", "time": "01:30", "currency": "AUD", "event": "CPI y/y", "impact": "High"},
    {"date": "2026-07-29", "time": "01:30", "currency": "AUD", "event": "Trimmed Mean CPI m/m", "impact": "High"},
    {"date": "2026-07-29", "time": "18:00", "currency": "USD", "event": "Federal Funds Rate", "impact": "High"},
    {"date": "2026-07-29", "time": "18:00", "currency": "USD", "event": "FOMC Statement", "impact": "High"},
    {"date": "2026-07-29", "time": "18:30", "currency": "USD", "event": "FOMC Press Conference", "impact": "High"},
    {"date": "2026-07-30", "time": "11:00", "currency": "GBP", "event": "BOE Monetary Policy Report", "impact": "High"},
    {"date": "2026-07-30", "time": "11:00", "currency": "GBP", "event": "Monetary Policy Summary", "impact": "High"},
    {"date": "2026-07-30", "time": "11:00", "currency": "GBP", "event": "MPC Official Bank Rate Votes", "impact": "High"},
    {"date": "2026-07-30", "time": "11:00", "currency": "GBP", "event": "Official Bank Rate", "impact": "High"},
    {"date": "2026-07-30", "time": "12:30", "currency": "USD", "event": "Advance GDP q/q", "impact": "High"},
    {"date": "2026-07-30", "time": "12:30", "currency": "USD", "event": "Core PCE Price Index m/m", "impact": "High"},
    {"date": "2026-07-31", "time": "00:00", "currency": "JPY", "event": "BOJ Policy Rate", "impact": "High"},
    {"date": "2026-07-31", "time": "00:00", "currency": "JPY", "event": "Monetary Policy Statement", "impact": "High"},
    {"date": "2026-07-31", "time": "00:00", "currency": "JPY", "event": "BOJ Outlook Report", "impact": "High"},
    {"date": "2026-07-31", "time": "03:00", "currency": "JPY", "event": "BOJ Press Conference", "impact": "High"},
    {"date": "2026-07-31", "time": "12:30", "currency": "CAD", "event": "GDP m/m", "impact": "High"},
]

# HIGH IMPACT EVENTS FOR AUGUST 2026 — ForexFactory EEST → UTC (−3h)
AUGUST_2026_EVENTS = [
    {"date": "2026-08-11", "time": "04:30", "currency": "AUD", "event": "Cash Rate", "impact": "High"},
    {"date": "2026-08-11", "time": "04:30", "currency": "AUD", "event": "RBA Monetary Policy Statement", "impact": "High"},
    {"date": "2026-08-11", "time": "04:30", "currency": "AUD", "event": "RBA Rate Statement", "impact": "High"},
    {"date": "2026-08-11", "time": "05:30", "currency": "AUD", "event": "RBA Press Conference", "impact": "High"},
    {"date": "2026-08-12", "time": "12:30", "currency": "USD", "event": "Core CPI m/m", "impact": "High"},
    {"date": "2026-08-12", "time": "12:30", "currency": "USD", "event": "Core CPI y/y", "impact": "High"},
    {"date": "2026-08-12", "time": "12:30", "currency": "USD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-08-12", "time": "12:30", "currency": "USD", "event": "CPI y/y", "impact": "High"},
    {"date": "2026-08-13", "time": "06:00", "currency": "GBP", "event": "GDP m/m", "impact": "High"},
    {"date": "2026-08-13", "time": "12:30", "currency": "USD", "event": "Core PPI m/m", "impact": "High"},
    {"date": "2026-08-13", "time": "12:30", "currency": "USD", "event": "PPI m/m", "impact": "High"},
    {"date": "2026-08-17", "time": "12:30", "currency": "CAD", "event": "CPI m/m", "impact": "High"},
    {"date": "2026-08-17", "time": "12:30", "currency": "CAD", "event": "Median CPI y/y", "impact": "High"},
    {"date": "2026-08-17", "time": "12:30", "currency": "CAD", "event": "Trimmed CPI y/y", "impact": "High"},
    {"date": "2026-08-18", "time": "06:00", "currency": "GBP", "event": "Claimant Count Change", "impact": "High"},
    {"date": "2026-08-19", "time": "06:00", "currency": "GBP", "event": "CPI y/y", "impact": "High"},
    {"date": "2026-08-19", "time": "18:00", "currency": "USD", "event": "FOMC Meeting Minutes", "impact": "High"},
    {"date": "2026-08-20", "time": "01:30", "currency": "AUD", "event": "Employment Change", "impact": "High"},
    {"date": "2026-08-20", "time": "01:30", "currency": "AUD", "event": "Unemployment Rate", "impact": "High"},
]


def _with_tz(events: List[Dict]) -> List[Dict]:
    return [{**event, "tz": event.get("tz", "UTC")} for event in events]


def update_calendar():
    """Add events to economic_calendar.json"""

    calendar_file = "economic_calendar.json"

    try:
        with open(calendar_file, "r", encoding="utf-8") as f:
            calendar_data = json.load(f)

        calendar_data["custom_events_june_2026"] = _with_tz(JUNE_2026_EVENTS)
        calendar_data["custom_events_july_2026"] = _with_tz(JULY_2026_EVENTS)
        calendar_data["custom_events_august_2026"] = _with_tz(AUGUST_2026_EVENTS)

        with open(calendar_file, "w", encoding="utf-8") as f:
            json.dump(calendar_data, f, indent=2, ensure_ascii=False)

        print("✅ Calendar updated successfully!")
        print(f"📅 June 2026:   {len(JUNE_2026_EVENTS)} events")
        print(f"📅 July 2026:   {len(JULY_2026_EVENTS)} events")
        print(f"📅 August 2026: {len(AUGUST_2026_EVENTS)} events")

        for label, events in [
            ("June", JUNE_2026_EVENTS),
            ("July", JULY_2026_EVENTS),
            ("August", AUGUST_2026_EVENTS),
        ]:
            high_impact = [e for e in events if e["impact"] == "High"]
            print(f"🚨 {label}: {len(high_impact)} HIGH impact events")

            currencies: Dict[str, int] = {}
            for event in events:
                curr = event["currency"]
                currencies[curr] = currencies.get(curr, 0) + 1

            print(f"\n📊 {label} events by currency:")
            for curr, count in sorted(currencies.items()):
                print(f"   {curr}: {count}")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("📅 MANUAL CALENDAR UPDATE — JUNE + JULY + AUGUST 2026 (V67.2)")
    print("=" * 60)
    print()

    update_calendar()

    print()
    print("💡 Next: python3 news_fetcher.py --days 14")
    print("=" * 60)
