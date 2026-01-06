#!/usr/bin/env python3
"""
LIVE Economic Calendar Fetcher
Fetches real-time forex economic events from Trading Economics API (free tier)
Auto-updates economic_calendar.json daily
"""

import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def fetch_live_calendar_tradingeconomics(days_ahead=14) -> List[Dict]:
    """
    Fetch from Trading Economics free calendar endpoint
    No API key needed for basic calendar data
    """
    try:
        logger.info("📡 Fetching LIVE calendar from Trading Economics...")
        
        # Trading Economics public calendar (updated daily)
        url = "https://api.tradingeconomics.com/calendar"
        
        # Calculate date range
        now = datetime.now()
        end_date = now + timedelta(days=days_ahead)
        
        params = {
            'f': 'json',
            'd1': now.strftime('%Y-%m-%d'),
            'd2': end_date.strftime('%Y-%m-%d')
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Received {len(data)} events from Trading Economics")
            
            # Convert to our format
            events = []
            for item in data:
                # Filter HIGH impact only
                importance = item.get('Importance', 1)
                if importance < 3:  # 3 = High impact
                    continue
                
                event_date = item.get('Date', '')
                if not event_date:
                    continue
                
                events.append({
                    "date": event_date[:10],  # YYYY-MM-DD
                    "time": event_date[11:16] if len(event_date) > 11 else "12:00",  # HH:MM
                    "currency": item.get('Country', 'USD'),  # Map country to currency
                    "event": item.get('Event', 'Unknown'),
                    "impact": "High",
                    "forecast": str(item.get('Forecast', '')),
                    "previous": str(item.get('Previous', ''))
                })
            
            return events
        else:
            logger.error(f"❌ Trading Economics returned status {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Error fetching from Trading Economics: {e}")
        return []


def fetch_live_calendar_investing_com(days_ahead=14) -> List[Dict]:
    """
    Fallback: Scrape Investing.com calendar (public data)
    """
    try:
        logger.info("📡 Fetching from Investing.com...")
        
        url = "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        now = datetime.now()
        
        payload = {
            'dateFrom': now.strftime('%Y-%m-%d'),
            'dateTo': (now + timedelta(days=days_ahead)).strftime('%Y-%m-%d'),
            'importance': '3',  # High impact only
            'timeZone': '8',  # UTC
            'timeFilter': 'timeOnly'
        }
        
        response = requests.post(url, headers=headers, data=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Received data from Investing.com")
            
            # Parse HTML response (simplified - needs proper parsing)
            # This is a fallback - Trading Economics is preferred
            return []
        else:
            logger.error(f"❌ Investing.com returned status {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Error fetching from Investing.com: {e}")
        return []


def update_calendar_file(events: List[Dict]):
    """Update economic_calendar.json with fresh data"""
    try:
        calendar_file = "economic_calendar.json"
        
        # Load existing calendar
        with open(calendar_file, 'r', encoding='utf-8') as f:
            calendar_data = json.load(f)
        
        # Update with LIVE events
        current_month = datetime.now().strftime("%B_%Y").lower()
        section_name = f"custom_events_{current_month}"
        
        # Keep recurring_events, update custom section
        calendar_data[section_name] = events
        
        # Save
        with open(calendar_file, 'w', encoding='utf-8') as f:
            json.dump(calendar_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Updated {calendar_file} with {len(events)} LIVE events")
        
        # Summary
        high_impact = [e for e in events if e.get('impact') == 'High']
        logger.info(f"🚨 {len(high_impact)} HIGH impact events")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error updating calendar file: {e}")
        return False


def main():
    """Fetch LIVE calendar and update local file"""
    logger.info("=" * 60)
    logger.info("🌐 LIVE ECONOMIC CALENDAR FETCH")
    logger.info("=" * 60)
    
    # Try Trading Economics first (most reliable free API)
    events = fetch_live_calendar_tradingeconomics(days_ahead=14)
    
    # Fallback to Investing.com if needed
    if not events or len(events) == 0:
        logger.warning("⚠️ No events from Trading Economics, trying Investing.com...")
        events = fetch_live_calendar_investing_com(days_ahead=14)
    
    if not events:
        logger.error("❌ Failed to fetch LIVE calendar from all sources!")
        logger.info("💡 Keeping existing manual calendar")
        return False
    
    # Update local file
    success = update_calendar_file(events)
    
    if success:
        logger.info("✅ Calendar auto-update COMPLETE!")
        logger.info("📅 Python will now use LIVE data automatically")
    else:
        logger.error("❌ Calendar update FAILED")
    
    logger.info("=" * 60)
    return success


if __name__ == "__main__":
    main()
