#!/usr/bin/env python3
"""
🗞️ NEWS CALENDAR MONITOR V2.0 - ALWAYS-ON DAEMON
──────────────────
✨ Glitch in Matrix by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money

Forex News Calendar Monitor - Continuous Background Daemon
Monitors high-impact economic events and sends Telegram alerts
Uses ForexFactory calendar with Selenium to bypass Cloudflare

🆕 V13.2 Features:
✅ Always-On Daemon (infinite loop, never exits) — 24/7, fără excepții
✅ Știrile = combustibil, NU obstacol — ZERO trade blocking
✅ Sniper Alert minimalist: ⚡ VOLATILITY RADAR format
✅ Timezone chirurgical: Europe/Bucharest strict (EET/EEST)
✅ Auto-retry on errors (graceful degradation)
✅ Watchdog-compatible (always shows RUNNING status)

Usage:
    python3 news_calendar_monitor.py [--interval HOURS]
    
    --interval: Hours between calendar checks (default: 24)
──────────────────
"""

import os
import sys
import time
import fcntl
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Try importing optional dependencies with graceful fallback
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    logger.warning("⚠️ BeautifulSoup4 not installed - HTML parsing disabled")
    HAS_BS4 = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    logger.warning("⚠️ requests not installed - HTTP fetching disabled")
    HAS_REQUESTS = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    HAS_SELENIUM = True
except ImportError:
    logger.warning("⚠️ Selenium not installed - Web scraping disabled")
    HAS_SELENIUM = False

try:
    import pytz
    HAS_PYTZ = True
except ImportError:
    logger.warning("⚠️ pytz not installed - Timezone handling limited")
    HAS_PYTZ = False

load_dotenv()

# Configure logger (remove default, add custom)
# Windows VPS fix: wrap stdout with UTF-8 to prevent UnicodeEncodeError on emoji
import io as _io
_safe_stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'buffer') else sys.stdout
logger.remove()
logger.add(
    _safe_stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="INFO",
    colorize=False
)
_LOG_DIR = Path(__file__).parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)
logger.add(
    str(_LOG_DIR / "news_calendar.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="DEBUG",
    rotation="10 MB",
    retention="7 days",
    compression="zip"
)


class NewsEvent:
    """Represents a single economic news event"""
    
    def __init__(self, time: datetime, currency: str, impact: str, event: str, actual: str = "", forecast: str = "", previous: str = ""):
        self.time = time
        self.currency = currency
        self.impact = impact  # LOW, MEDIUM, HIGH
        self.event = event
        self.actual = actual
        self.forecast = forecast
        self.previous = previous
    
    def __repr__(self):
        return f"NewsEvent({self.currency} - {self.event} at {self.time})"


# ═══════════════════════════════════════════════════════════════════
# 🏦 V11.0 MACRO WEEKLY TABLE — Central Bank Rates (hardcoded 2026)
# ═══════════════════════════════════════════════════════════════════

CENTRAL_BANK_RATES: Dict[str, float] = {
    "NZD": 5.25,
    "GBP": 5.00,
    "USD": 4.75,
    "AUD": 4.35,
    "CAD": 3.75,
    "EUR": 3.50,
    "CHF": 1.50,
    "JPY": 0.25,
}

# Watched pairs for top-carry calculation
_CARRY_PAIRS = [
    ("GBP", "JPY"), ("NZD", "JPY"), ("AUD", "JPY"), ("USD", "JPY"),
    ("GBP", "CHF"), ("NZD", "CHF"), ("AUD", "CHF"), ("USD", "CHF"),
    ("GBP", "EUR"), ("NZD", "EUR"), ("AUD", "EUR"), ("USD", "EUR"),
    ("GBP", "CAD"), ("NZD", "CAD"), ("AUD", "CAD"), ("USD", "CAD"),
]

# Central bank names (for live scraping)
_CB_NAMES = {
    "USD": "Federal Reserve (Fed)",
    "EUR": "European Central Bank (ECB)",
    "GBP": "Bank of England (BOE)",
    "JPY": "Bank of Japan (BOJ)",
    "AUD": "Reserve Bank of Australia (RBA)",
    "NZD": "Reserve Bank of New Zealand (RBNZ)",
    "CAD": "Bank of Canada (BOC)",
    "CHF": "Swiss National Bank (SNB)",
}

# Currency flags
_FLAGS = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵",
    "AUD": "🇦🇺", "NZD": "🇳🇿", "CAD": "🇨🇦", "CHF": "🇨🇭",
}


class NewsCalendarMonitor:
    """
    Monitors forex economic calendar and sends alerts — V12.2 Intelligence Preemptiv
    
    Scheduler:
      • Sunday 23:00 EET  → 📋 WAR MAP (weekly High Impact grouped by day)
      • Every minute       → ⚠️ 15-MIN SNIPER ALERT before any High Impact event
      • Monday 09:00 EET  → 🏦 MACRO WEEKLY TABLE (central bank rates)
    """

    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')

        if HAS_REQUESTS:
            self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

        # 🏦 V11.0 MACRO: last sent date tracker (avoid double-send on same Monday)
        self._macro_last_sent_date: Optional[str] = None
        # Persistent fail-safe: survives restarts — stores last sent date on disk
        self._macro_sent_file = Path(__file__).parent / 'data' / 'macro_report_last_sent.txt'
        self._load_macro_sent_date()  # restore from disk on startup
        # Live rates override (populated by fetch_live_cb_rates)
        self._live_rates: Dict[str, float] = {}

        # ━━━ V12.2: SNIPER ALERT state ━━━
        # Set of (event_date_str, currency, event_name) already alerted — prevents duplicate fires
        self._sniper_alerted: set = set()
        # War Map: ISO-date of Monday already sent (Sunday night report covers upcoming Mon-Fri)
        self._war_map_sent_week: Optional[str] = None
        self._war_map_sent_file = Path(__file__).parent / 'data' / 'war_map_last_sent.txt'
        self._load_war_map_sent_week()  # restore from disk
        
        # Timezone for Romania (GMT+2 / EET)
        if HAS_PYTZ:
            self.local_tz = pytz.timezone('Europe/Bucharest')
            self.utc_tz = pytz.UTC
        else:
            self.local_tz = None
            self.utc_tz = None

        if not self.bot_token or not self.chat_id:
            logger.warning("⚠️ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set - alerts disabled")
            self.alerts_enabled = False
        else:
            self.alerts_enabled = True
        
        # Critical news keywords to highlight
        self.critical_keywords = [
            # Super critical - major market movers
            'NFP', 'Non-Farm', 'Payroll',
            'FOMC', 'Fed', 'Interest Rate', 'Bank Rate', 'Official Bank Rate',
            'CPI', 'Inflation', 'Core CPI', 'Median CPI', 'Trimmed CPI',
            'GDP', 'Gross Domestic',
            
            # Central banks & policy decisions
            'Central Bank', 'ECB', 'BOE', 'BOJ',
            'Monetary Policy', 'MPC', 'Rate Decision',
            'Main Refinancing', 'Refinancing Rate',
            
            # Employment & labor
            'Employment', 'Unemployment', 'Claimant Count',
            'ADP', 'Weekly Employment', 'Hourly Earnings', 'Average Earnings',
            
            # Key economic indicators
            'Retail Sales', 'Core Retail Sales',
            'PMI', 'Flash PMI', 'Manufacturing PMI', 'Services PMI',
            'Flash Manufacturing', 'Flash Services',
            
            # Central bank officials (governors)
            'Bailey', 'Lagarde', 'Powell'
        ]
        
        # Major currencies we trade
        self.major_currencies = ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'NZD', 'CAD', 'CHF']
    
    def fetch_manual_calendar(self, days_ahead: int = 7) -> List[NewsEvent]:
        """
        Fetch events from local JSON file
        Most reliable method - manually curated events
        """
        try:
            import json
            from pathlib import Path
            
            logger.info("📅 Loading manual calendar from economic_calendar.json...")
            
            calendar_file = Path(__file__).parent / 'economic_calendar.json'
            
            if not calendar_file.exists():
                logger.error("❌ economic_calendar.json not found!")
                return []
            
            now = datetime.now()  # Define now BEFORE using it
            
            with open(calendar_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Try current month + next month (needed when days_ahead spans month boundary)
            current_month = now.strftime("%B_%Y").lower()  # e.g., "march_2026"
            section_name = f'custom_events_{current_month}'
            
            # Calculate next month key
            from calendar import monthrange
            next_month_dt = now.replace(day=1) + timedelta(days=32)
            next_month_key = f'custom_events_{next_month_dt.strftime("%B_%Y").lower()}'
            
            custom_events = data.get(section_name, [])
            next_events = data.get(next_month_key, [])
            
            if custom_events:
                logger.info(f"✅ Using events from '{section_name}' ({len(custom_events)} total events)")
            if next_events:
                logger.info(f"✅ Also loading next month '{next_month_key}' ({len(next_events)} total events)")
                custom_events = custom_events + next_events
            
            if not custom_events:
                # Scan available sections for the most recent one
                available = sorted([k for k in data.keys() if k.startswith('custom_events_')], reverse=True)
                fallback_section = available[0] if available else None
                if fallback_section:
                    custom_events = data.get(fallback_section, [])
                    logger.warning(f"⚠️ Section '{section_name}' not found — using fallback: '{fallback_section}'")
                else:
                    logger.error(f"❌ No event sections found in economic_calendar.json!")
            elif not data.get(section_name):
                logger.warning(f"⚠️ Section '{section_name}' empty — using '{next_month_key}'")
            
            # Use timezone-aware now
            now = datetime.now(self.local_tz)
            end_date = now + timedelta(days=days_ahead)
            
            events = []
            for e in custom_events:
                try:
                    event_date = datetime.strptime(e['date'], '%Y-%m-%d')
                    
                    # Add time if specified
                    if 'time' in e and e['time'] not in ('All Day', '', None):
                        time_parts = e['time'].split(':')
                        event_date = event_date.replace(
                            hour=int(time_parts[0]),
                            minute=int(time_parts[1])
                        )
                        # V13.2 FIX: timpii din economic_calendar.json sunt EET (Europe/Bucharest)
                        # NU UTC! FOMC azi 21:00 EET = 21:00 în JSON, nu conversie UTC+2=23:00.
                        # Dacă vrei UTC în JSON, adaugă câmpul 'tz': 'UTC' explicit.
                        tz_field = e.get('tz', 'EET').upper()
                        if tz_field == 'UTC':
                            event_date = self.utc_tz.localize(event_date).astimezone(self.local_tz)
                        else:
                            # Default: EET — ora din JSON = ora română directă
                            event_date = self.local_tz.localize(event_date)
                    else:
                        event_date = event_date.replace(hour=9, minute=0)
                        event_date = self.local_tz.localize(event_date)
                    
                    # Check if within date range
                    if event_date < now or event_date > end_date:
                        continue
                    
                    event = NewsEvent(
                        time=event_date,
                        currency=e['currency'],
                        impact=e.get('impact', 'High'),
                        event=e['event'],
                        actual='',
                        forecast=e.get('forecast', ''),
                        previous=e.get('previous', '')
                    )
                    
                    # Mark as critical
                    event.is_critical = e.get('impact') == 'High'
                    
                    events.append(event)
                    
                except Exception as ex:
                    logger.debug(f"Error parsing event: {ex}")
                    continue
            
            logger.info(f"✅ Loaded {len(events)} events from manual calendar")
            return events
            
        except Exception as e:
            logger.error(f"❌ Error loading manual calendar: {e}")
            return []
    
    def fetch_ctrader_calendar(self, days_ahead: int = 7) -> List[NewsEvent]:
        """
        Fetch economic calendar from cTrader Desktop via EconomicCalendarBot
        Much more reliable than web scraping!
        """
        try:
            logger.info("📅 Fetching calendar from cTrader Desktop...")
            
            response = requests.get('http://localhost:8768/calendar', timeout=10)
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to fetch calendar: HTTP {response.status_code}")
                return []
            
            data = response.json()
            
            if not data.get('success'):
                logger.error(f"❌ Calendar fetch failed: {data.get('error', 'Unknown error')}")
                return []
            
            raw_events = data.get('events', [])
            logger.info(f"📊 Received {len(raw_events)} events from cTrader")
            
            # Convert to NewsEvent objects
            events = []
            for e in raw_events:
                try:
                    event_time = datetime.strptime(e['time'], '%Y-%m-%d %H:%M:%S')
                    
                    event = NewsEvent(
                        time=event_time,
                        currency=e['currency'],
                        impact=e['impact'],
                        event=e['event'],
                        actual=str(e['actual']) if e['actual'] else '',
                        forecast=str(e['forecast']) if e['forecast'] else '',
                        previous=str(e['previous']) if e['previous'] else ''
                    )
                    
                    # Mark critical events
                    event.is_critical = any(
                        keyword.lower() in e['event'].lower() 
                        for keyword in self.critical_keywords
                    )
                    
                    events.append(event)
                except Exception as ex:
                    logger.debug(f"Error parsing event: {ex}")
                    continue
            
            logger.info(f"✅ Parsed {len(events)} calendar events")
            return events
            
        except requests.exceptions.ConnectionError:
            logger.error("❌ Cannot connect to cTrader Desktop on localhost:8768")
            logger.error("💡 Make sure EconomicCalendarBot is running in cTrader!")
            return []
        except Exception as e:
            logger.error(f"❌ Error fetching calendar: {e}")
            return []
    
    def fetch_forexfactory_calendar(self, days_ahead: int = 2) -> List[NewsEvent]:
        """
        Fetch upcoming news from ForexFactory calendar using Selenium
        Uses real browser to bypass Cloudflare protection
        
        IMPORTANT: ForexFactory returns blank/limited data when scraping WEEK view for bots.
        Must scrape EACH DAY individually (day=dec15.2025 instead of week=dec14.2025)
        """
        driver = None
        all_events = []
        
        try:
            logger.info("📰 Fetching ForexFactory calendar...")
            
            # Calculate individual days to fetch
            now = datetime.now()
            days_to_fetch = []
            
            for day_offset in range(days_ahead + 1):
                fetch_date = now + timedelta(days=day_offset)
                day_param = fetch_date.strftime('%b%d.%Y').lower()  # e.g., "dec15.2025"
                days_to_fetch.append((fetch_date, day_param))
            
            logger.info(f"📅 Will fetch {len(days_to_fetch)} day(s): {', '.join([d[1] for d in days_to_fetch])}")
            
            # Setup Chrome options for headless browsing
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Initialize driver once for all days
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Fetch each day individually (not week view!)
            for i, (fetch_date, day_param) in enumerate(days_to_fetch):
                # Add delay between requests to avoid rate limiting (except first request)
                if i > 0:
                    delay = 3  # 3 seconds between requests
                    logger.info(f"⏳ Waiting {delay}s before next request...")
                    time.sleep(delay)
                
                url = f"https://www.forexfactory.com/calendar?day={day_param}"
                
                logger.info(f"🌐 Loading {fetch_date.strftime('%a %b %d')}: {url}")
                
                try:
                    driver.get(url)
                    
                    # Wait for calendar table
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "calendar__table"))
                    )
                    time.sleep(2)  # Extra wait for dynamic content
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load {day_param}: {e}")
                    continue
                
                # Get page source and parse
                html = driver.page_source
                logger.info(f"📥 Received {len(html)} bytes for {day_param}")
                
                soup = BeautifulSoup(html, 'html.parser')
                
                events = []
                current_date = None
                
                # Parse calendar table
                calendar_rows = soup.find_all('tr', class_='calendar__row')
                
                for row in calendar_rows:
                    try:
                        # Get date
                        date_cell = row.find('td', class_='calendar__date')
                        if date_cell and date_cell.text.strip():
                            date_str = date_cell.text.strip()
                            try:
                                # ForexFactory format: "Sun Dec 14" or "Mon Dec 15"
                                # FIX V13.2: use fetch_date.year NOT datetime.now().year
                                # Motivul: dacă scrape-ul e pe 31 Dec la 23:59 și
                                # evenimentul e pe 1 Ian — .now().year ar da anul greșit.
                                if len(date_str.split()) == 3:  # e.g., "Sun Dec 14"
                                    current_date = datetime.strptime(f"{date_str} {fetch_date.year}", "%a %b %d %Y")
                                else:  # e.g., "Dec 14"
                                    current_date = datetime.strptime(f"{date_str} {fetch_date.year}", "%b %d %Y")
                            except Exception as e:
                                logger.debug(f"Error parsing date '{date_str}': {e}")
                        
                        if not current_date:
                            continue
                        
                        # Get time
                        time_cell = row.find('td', class_='calendar__time')
                        if not time_cell:
                            continue
                        
                        time_str = time_cell.text.strip()
                        
                        # Handle different time formats
                        if not time_str or time_str == "All Day" or time_str == "Tentative" or time_str == "":
                            # Use noon as default time for events without specific time
                            event_time = current_date.replace(hour=12, minute=0)
                        else:
                            try:
                                event_time = datetime.strptime(f"{current_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %I:%M%p")
                            except Exception as e:
                                logger.debug(f"Error parsing time '{time_str}': {e}")
                                # Default to noon if time parsing fails
                                event_time = current_date.replace(hour=12, minute=0)
                        
                        # Get currency
                        currency_cell = row.find('td', class_='calendar__currency')
                        currency = currency_cell.text.strip() if currency_cell else ""
                        
                        # Get impact - check CSS class for red icon (HIGH impact)
                        impact_cell = row.find('td', class_='calendar__impact')
                        impact = ""
                        is_high_impact = False
                        
                        if impact_cell:
                            impact_span = impact_cell.find('span')
                            if impact_span:
                                # Check if has red impact class
                                span_classes = impact_span.get('class', [])
                                if 'icon--ff-impact-red' in span_classes:
                                    impact = "High Impact Expected"
                                    is_high_impact = True
                                elif 'icon--ff-impact-ora' in span_classes:
                                    impact = "Medium Impact Expected"
                                elif 'icon--ff-impact-yel' in span_classes:
                                    impact = "Low Impact Expected"
                                
                                # Fallback to title attribute
                                if not impact and 'title' in impact_span.attrs:
                                    impact = impact_span['title']
                                    # 🚨 FIX: Use exact match for ForexFactory format
                                    if impact in ["High Impact Expected", "High"]:
                                        is_high_impact = True
                        
                        # Get event name
                        event_cell = row.find('td', class_='calendar__event')
                        event_name = event_cell.text.strip() if event_cell else ""
                        
                        # Get actual, forecast, previous
                        actual_cell = row.find('td', class_='calendar__actual')
                        forecast_cell = row.find('td', class_='calendar__forecast')
                        previous_cell = row.find('td', class_='calendar__previous')
                        
                        actual = actual_cell.text.strip() if actual_cell else ""
                        forecast = forecast_cell.text.strip() if forecast_cell else ""
                        previous = previous_cell.text.strip() if previous_cell else ""
                        
                        # Create event object
                        if event_name and currency:
                            event = NewsEvent(
                                time=event_time,
                                currency=currency,
                                impact=impact,
                                event=event_name,
                                actual=actual,
                                forecast=forecast,
                                previous=previous
                            )
                            events.append(event)
                    
                    except Exception as e:
                        logger.debug(f"Error parsing row: {e}")
                        continue
                
                # Add events from this day to all_events
                all_events.extend(events)
                logger.info(f"✅ Found {len(events)} events on {day_param}")
            
            # Filter events within next N days
            now = datetime.now()
            cutoff = now + timedelta(days=days_ahead)
            
            filtered_events = [
                e for e in all_events
                if now <= e.time <= cutoff
            ]
            
            logger.info(f"✅ Total: {len(all_events)} events, filtered to {len(filtered_events)} upcoming events")
            return filtered_events
        
        except Exception as e:
            logger.error(f"❌ Error fetching ForexFactory calendar: {e}")
            return []
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    def filter_high_impact_events(self, events: List[NewsEvent]) -> List[NewsEvent]:
        """
        Filter only HIGH impact events for major currencies
        🔥 FIX by ФорексГод: STRICT ForexFactory classification - NO keyword override!
        Critical keywords only ADD warning flags, NOT promote to HIGH
        """
        high_impact = []
        
        for event in events:
            # Check if major currency
            if event.currency not in self.major_currencies:
                continue
            
            # 🚨 STRICT FIX: ONLY accept events ForexFactory marked as HIGH (red icon)
            # Use EXACT match - must be official ForexFactory format
            is_ff_high = event.impact in ["High Impact Expected", "High"]
            
            # Only accept ForexFactory HIGH events
            if is_ff_high:
                # Check if contains critical keywords (for warning flags only)
                is_critical = any(keyword.lower() in event.event.lower() for keyword in self.critical_keywords)
                event.is_critical = is_critical  # Mark for extra warnings in message
                high_impact.append(event)
        
        return high_impact
    
    def format_telegram_message(self, events: List[NewsEvent]) -> str:
        """Format news events into professional Telegram message - COMPACT v4.0"""
        if not events:
            return """✅ *ALL CLEAR*
🟢 *Status:* SAFE TO TRADE
📊 *Next 48h:* No major events
💎 *Risk:* LOW
╼╼╼╼╼╼╼╼
✨ *Glitch in Matrix*
👑 ФорексГод
╼╼╼╼╼╼╼╼"""
        
        # Currency flag emojis
        flags = {
            'USD': '🇺🇸', 'EUR': '🇪🇺', 'GBP': '🇬🇧', 'JPY': '🇯🇵',
            'AUD': '🇦🇺', 'NZD': '🇳🇿', 'CAD': '🇨🇦', 'CHF': '🇨🇭'
        }
        
        # Count critical events
        critical_count = sum(1 for e in events if any(keyword.lower() in e.event.lower() for keyword in ['NFP', 'FOMC', 'CPI', 'Interest Rate', 'GDP']))
        
        # Header - COMPACT
        now = datetime.now(self.local_tz) if self.local_tz else datetime.now()
        message = f"⚡ *NEWS* • {now.strftime('%H:%M')} EET\n"
        message += f"📅 {now.strftime('%a %b %d')}\n"
        if critical_count > 0:
            message += f"🔥 *{critical_count} CRITICAL*\n"
        message += f"📊 {len(events)} HIGH impact (48h)\n"
        message += "╼╼╼╼╼╼╼╼\n"
        
        # Group by date
        events_by_date = {}
        for event in events:
            date_key = event.time.strftime("%A, %B %d")
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            events_by_date[date_key].append(event)
        
        # Display each day
        for date, date_events in events_by_date.items():
            message += f"📍 *{date}*\n"
            message += "╼╼╼╼╼╼╼╼\n"
            for event in date_events:
                flag = flags.get(event.currency, '🏴')
                time_str = event.time.strftime("%H:%M")
                
                # Time until event - SIMPLIFIED
                now = datetime.now(self.local_tz)
                if event.time.tzinfo is None:
                    event_time_aware = self.local_tz.localize(event.time)
                else:
                    event_time_aware = event.time.astimezone(self.local_tz)
                
                time_diff = event_time_aware - now
                hours = int(time_diff.total_seconds() // 3600)
                
                # Countdown with urgency
                if hours < 0:
                    countdown_emoji = "🔴"
                    countdown = "LIVE NOW"
                elif hours < 1:
                    countdown_emoji = "🔴"
                    countdown = f"< 1 HOUR"
                elif hours < 3:
                    countdown_emoji = "🟠"
                    countdown = f"{hours}h"
                elif hours < 12:
                    countdown_emoji = "🟡"
                    countdown = f"{hours}h"
                else:
                    countdown_emoji = "🟢"
                    days = hours // 24
                    if days > 0:
                        countdown = f"{days}d {hours % 24}h"
                    else:
                        countdown = f"{hours}h"
                
                # Detect CRITICAL events
                is_critical = any(keyword.lower() in event.event.lower() 
                                for keyword in ['NFP', 'Non-Farm', 'Payroll', 'FOMC', 'Interest Rate', 'CPI', 'GDP'])
                
                critical_marker = "⚠️" if is_critical else ""
                # Format event line - COMPACT
                message += f"{critical_marker}{flag} *{event.currency}* {event.event}\n"
                message += f"🕐 {time_str} • {countdown_emoji} {countdown}\n"
                if event.forecast:
                    message += f"📊 F:`{event.forecast}` P:`{event.previous or 'N/A'}`\n"
                # Add warnings for CRITICAL
                if is_critical:
                    if 'NFP' in event.event.upper() or 'PAYROLL' in event.event.upper():
                        message += f"💥 *EXTREME VOL*\n"
                    elif 'FOMC' in event.event.upper():
                        message += f"💥 *FED DECISION*\n"
                    elif 'CPI' in event.event.upper():
                        message += f"📊 *INFLATION*\n"
                message += "\n"
        
        # Summary by currency - COMPACT
        message += "╼╼╼╼╼╼╼╼\n"
        message += "📊 *SUMMARY:*\n"
        currency_counts = {}
        for event in events:
            if event.currency not in currency_counts:
                currency_counts[event.currency] = {'total': 0, 'critical': 0}
            currency_counts[event.currency]['total'] += 1
            if any(k.lower() in event.event.lower() for k in ['NFP', 'FOMC', 'CPI', 'Interest Rate']):
                currency_counts[event.currency]['critical'] += 1
        sorted_currencies = sorted(currency_counts.items(), key=lambda x: x[1]['total'], reverse=True)
        for currency, counts in sorted_currencies:
            flag = flags.get(currency, '🏴')
            crit = f"⚠️{counts['critical']}" if counts['critical'] > 0 else ""
            message += f"{flag}{currency}:{counts['total']} {crit}\n"
        
        # Footer - COMPACT STAMP
        message += "╼╼╼╼╼╼╼╼\n"
        message += "🏛️ Matrix Hunting 24/7\n"
        message += "╼╼╼╼╼╼╼╼\n"
        message += "💡 Updates: 8am,2pm,8pm,2am EET\n"
        message += "─────────────────\n"
        message += "🔱 *AUTHORED BY ФорексГод* 🔱\n"
        message += "🏛️ *Глитч Ин Матрикс* 🏛️"
        
        return message
    
    def send_telegram_alert(self, message: str) -> bool:
        """Send alert to Telegram"""
        try:
            import requests
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ Telegram alert sent successfully")
                return True
            else:
                logger.error(f"❌ Telegram error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error sending Telegram: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════
    # 🏦 V11.0 MACRO WEEKLY TABLE
    # ═══════════════════════════════════════════════════════════════════

    def fetch_live_cb_rates(self) -> Dict[str, float]:
        """
        Tentative scraping of live central bank rates from investing.com.
        Returns a dict {currency: rate}.
        Falls back to CENTRAL_BANK_RATES hardcoded values if scraping fails.
        """
        if not HAS_REQUESTS:
            return {}

        live: Dict[str, float] = {}
        # investing.com central-bank-rates page (public, no JS needed)
        url = "https://www.investing.com/central-banks/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            import requests as _req
            resp = _req.get(url, headers=headers, timeout=12)
            if resp.status_code != 200:
                logger.warning(f"⚠️ Live CB rates fetch returned HTTP {resp.status_code} — using hardcoded")
                return {}

            if not HAS_BS4:
                logger.warning("⚠️ BeautifulSoup not available — using hardcoded rates")
                return {}

            soup = BeautifulSoup(resp.text, "html.parser")

            # investing.com table: rows contain flag img + currency name + rate
            # Pattern: <td class="...flagCur...">USD</td>  <td>4.75%</td>
            currency_map = {
                "united states": "USD", "euro zone": "EUR", "eurozone": "EUR",
                "united kingdom": "GBP", "japan": "JPY", "australia": "AUD",
                "new zealand": "NZD", "canada": "CAD", "switzerland": "CHF",
            }
            rows = soup.select("table tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 3:
                    continue
                country_text = cols[0].get_text(" ", strip=True).lower()
                rate_text = ""
                # rate is usually in the 3rd or 4th column — find first % sign
                for col in cols[1:]:
                    txt = col.get_text(strip=True).replace("%", "").replace(",", ".")
                    try:
                        val = float(txt)
                        rate_text = txt
                        break
                    except ValueError:
                        continue

                if not rate_text:
                    continue

                for key, ccy in currency_map.items():
                    if key in country_text and ccy not in live:
                        try:
                            live[ccy] = float(rate_text)
                        except ValueError:
                            pass
                        break

            if len(live) >= 5:
                logger.success(f"✅ Live CB rates fetched: {live}")
            else:
                logger.warning(f"⚠️ Only {len(live)} live rates parsed — partial result")

        except Exception as e:
            logger.warning(f"⚠️ Live CB rate scrape failed: {e} — using hardcoded")

        return live

    def _get_effective_rates(self) -> Dict[str, float]:
        """
        Returns merged rate dict: live rates override hardcoded where available.
        Detects changes vs hardcoded baseline and logs them.
        """
        effective = dict(CENTRAL_BANK_RATES)  # start with hardcoded
        live = self.fetch_live_cb_rates()

        changes: list = []
        for ccy, live_rate in live.items():
            hardcoded = CENTRAL_BANK_RATES.get(ccy)
            if hardcoded is not None and abs(live_rate - hardcoded) >= 0.01:
                changes.append((ccy, hardcoded, live_rate))
                logger.warning(f"🚨 RATE CHANGE DETECTED: {ccy} {hardcoded}% → {live_rate}%")
            effective[ccy] = live_rate

        # Store for re-use
        self._live_rates = effective
        return effective, changes

    def generate_weekly_macro_report(self) -> str:
        """
        🏦 V11.0 MACRO WEEKLY TABLE
        Generates Telegram-ready macro report with:
         - Central bank rates table (sorted highest→lowest)
         - Strong / Weak classification
         - Top 3 carry opportunities from _CARRY_PAIRS
         - Rate change alerts (vs hardcoded baseline)
        """
        rates, changes = self._get_effective_rates()

        # ── Sort currencies by rate (desc)
        sorted_rates = sorted(rates.items(), key=lambda x: x[1], reverse=True)

        # ── Median for Strong/Weak threshold
        all_vals = [v for _, v in sorted_rates]
        median_rate = sorted(all_vals)[len(all_vals) // 2]

        now_ro = datetime.now(self.local_tz) if self.local_tz else datetime.now()
        week_str = now_ro.strftime("W%W • %d %b %Y")

        SEP = "━━━━━━━━━━━━━━━━"   # 16 chars (scurtat cu 3 față de 19)

        msg = "🏦 <b>MACRO WEEKLY TABLE</b>\n"
        msg += f"📅 <b>{week_str}</b>\n"
        msg += f"🕐 <i>Transmis {now_ro.strftime('%H:%M')} EET</i>\n"
        msg += SEP + "\n"

        # ── Rate change alerts (if any)
        if changes:
            msg += "🚨 <b>RATE CHANGES!</b>\n"
            for ccy, old, new in changes:
                arrow = "🔺" if new > old else "🔻"
                flag = _FLAGS.get(ccy, "")
                msg += f"  {arrow} {flag} <b>{ccy}</b>: {old:.2f}% → <b>{new:.2f}%</b>\n"
            msg += SEP + "\n"

        # ── Rates table
        msg += "📊 <b>DOBÂNZI BĂNCI CENTRALE</b>\n"
        msg += "<code>"
        msg += f"{'CCY':<5} {'RATĂ':>6}  STATUS\n"
        msg += f"{'─'*5} {'─'*6}  {'─'*8}\n"
        for ccy, rate in sorted_rates:
            flag = _FLAGS.get(ccy, " ")
            status = "🟢 STRONG" if rate >= median_rate else "🔴 WEAK"
            source = "*" if ccy in self._live_rates and abs(self._live_rates.get(ccy, 0) - CENTRAL_BANK_RATES.get(ccy, 0)) >= 0.01 else " "
            msg += f"{flag}{ccy:<3} {rate:>5.2f}%  {status}{source}\n"
        msg += "</code>"
        msg += "<i>* = live update</i>\n"
        msg += SEP + "\n"

        # ── Top 3 carry pairs
        pair_spreads = []
        for base, quote in _CARRY_PAIRS:
            b_rate = rates.get(base, 0)
            q_rate = rates.get(quote, 0)
            spread = round(b_rate - q_rate, 2)
            pair_spreads.append((f"{base}/{quote}", base, quote, spread, b_rate, q_rate))

        top3 = sorted(pair_spreads, key=lambda x: x[3], reverse=True)[:3]

        msg += "🚀 <b>TOP 3 CARRY OPPORTUNITIES</b>\n"
        for rank, (pair, base, quote, spread, b_rate, q_rate) in enumerate(top3, 1):
            b_flag = _FLAGS.get(base, "")
            q_flag = _FLAGS.get(quote, "")
            medal = ["🥇", "🥈", "🥉"][rank - 1]
            msg += (
                f"{medal} <b>{b_flag}{base}/{q_flag}{quote}</b>  "
                f"<code>+{spread:.2f}%</code>\n"
                f"   {b_rate:.2f}% − {q_rate:.2f}% spread\n"
            )

        msg += SEP + "\n"

        # ── Strongest vs weakest
        strongest_ccy, strongest_rate = sorted_rates[0]
        weakest_ccy, weakest_rate = sorted_rates[-1]
        msg += (
            f"💪 {_FLAGS.get(strongest_ccy,'')} <b>{strongest_ccy}</b> {strongest_rate:.2f}% · "
            f"😴 {_FLAGS.get(weakest_ccy,'')} <b>{weakest_ccy}</b> {weakest_rate:.2f}%\n"
        )
        msg += SEP + "\n"

        # ── Semnătură oficială V11.8
        msg += "─────────────────\n"
        msg += "🔱 <b>AUTHORED BY ФорексГод</b> 🔱\n"
        msg += "🏛️ <b>Глитч Ин Матрикс</b> 🏛️"

        return msg

    def _load_macro_sent_date(self):
        """Load last sent date from disk (fail-safe: survives process restarts)."""
        try:
            if self._macro_sent_file.exists():
                stored = self._macro_sent_file.read_text().strip()
                self._macro_last_sent_date = stored if stored else None
                logger.debug(f"📂 Macro last sent: {stored}")
        except Exception:
            pass

    def _save_macro_sent_date(self, date_str: str):
        """Persist last sent date to disk so fail-safe works after restarts."""
        try:
            self._macro_sent_file.parent.mkdir(parents=True, exist_ok=True)
            self._macro_sent_file.write_text(date_str)
        except Exception as e:
            logger.warning(f"⚠️ Could not save macro sent date: {e}")

    def _should_send_macro_report(self) -> bool:
        """
        V11.8 STRICT SCHEDULER — Europe/Bucharest (EET/EEST)
        Sends EVERY Monday at 09:00 EET sharp.
        FAIL-SAFE: if missed 09:00 (restart/crash), sends immediately on next wake.
        """
        now = datetime.now(self.local_tz) if self.local_tz else datetime.now()
        is_monday = (now.weekday() == 0)          # 0 = Monday
        is_after_9am = (now.hour >= 9)            # EET — already local tz
        today_str = now.strftime("%Y-%m-%d")
        already_sent = (self._macro_last_sent_date == today_str)
        # Fail-safe: fire if Monday + ≥09:00 and NOT yet sent today
        return is_monday and is_after_9am and not already_sent

    # ═══════════════════════════════════════════════════════════════════
    # 📋 V12.2 WAR MAP — Sunday 23:00 EET Weekly High Impact Report
    # ═══════════════════════════════════════════════════════════════════

    def _load_war_map_sent_week(self):
        """Restore last war-map ISO week string from disk (survives restarts)."""
        try:
            if self._war_map_sent_file.exists():
                stored = self._war_map_sent_file.read_text().strip()
                self._war_map_sent_week = stored if stored else None
                logger.debug(f"📂 War Map last sent week: {stored}")
        except Exception:
            pass

    def _save_war_map_sent_week(self, week_str: str):
        """Persist war-map week string to disk."""
        try:
            self._war_map_sent_file.parent.mkdir(parents=True, exist_ok=True)
            self._war_map_sent_file.write_text(week_str)
        except Exception as e:
            logger.warning(f"⚠️ Could not save war map sent week: {e}")

    def _should_send_war_map(self) -> bool:
        """
        V12.3 TRIGGER cu FAIL-SAFE — Sunday 23:00 EET SAU Monday oricând dacă
        săptămâna curentă nu a fost trimisă (laptop suspendat / restart ratat).
        Uses the ISO week number of the *current* Monday as dedup key.
        """
        if not self.local_tz:
            return False
        now = datetime.now(self.local_tz)
        is_sunday = (now.weekday() == 6)       # 6 = Sunday
        is_23h    = (now.hour == 23 and now.minute < 2)  # 23:00 – 23:01

        # Key = ISO week de luni (dacă e duminică, coming Monday = mâine;
        # dacă e luni, această săptămână = azi)
        if is_sunday:
            coming_monday = now + timedelta(days=1)
        else:
            # Calculează luni-ul curent (ziua 0 a săptămânii)
            days_since_monday = now.weekday()
            coming_monday = now - timedelta(days=days_since_monday)
        week_key = coming_monday.strftime("%Y-W%W")
        already_sent = (self._war_map_sent_week == week_key)

        # Trigger primar: Duminică 23:00 EET
        primary_trigger = is_sunday and is_23h and not already_sent

        # FAIL-SAFE: Luni dimineața (00:00–11:59) — dacă war map nu a fost trimis
        is_monday = (now.weekday() == 0)
        failsafe_trigger = is_monday and (now.hour < 12) and not already_sent

        return primary_trigger or failsafe_trigger

    def format_war_map(self, events: List['NewsEvent']) -> str:
        """
        📋 WAR MAP — High Impact events for the coming week, grouped by day.
        Only days with at least one High Impact event are shown.
        """
        SEP  = "────────────────"
        now  = datetime.now(self.local_tz) if self.local_tz else datetime.now()

        # Filter: HIGH impact only, within next 7 days, ignore "All Day" (no exact time)
        cutoff_start = now
        cutoff_end   = now + timedelta(days=7)

        hi_events = []
        for e in events:
            if e.impact not in ("High Impact Expected", "High"):
                continue
            et = e.time
            if et.tzinfo is None and self.local_tz:
                et = self.local_tz.localize(et)
            elif et.tzinfo and self.local_tz:
                et = et.astimezone(self.local_tz)
            if et < cutoff_start or et > cutoff_end:
                continue
            hi_events.append((et, e))

        hi_events.sort(key=lambda x: x[0])

        # Group by day
        days: Dict[str, list] = {}
        day_labels: Dict[str, str] = {}
        for et, e in hi_events:
            dk = et.strftime("%Y-%m-%d")
            label = et.strftime("%A, %d %b").upper()   # e.g. MONDAY, 07 APR
            days.setdefault(dk, [])
            day_labels[dk] = label
            days[dk].append((et, e))

        coming_monday = (now + timedelta(days=1))
        week_str = f"W{coming_monday.strftime('%W')} • {coming_monday.strftime('%d %b')} – {(coming_monday + timedelta(days=4)).strftime('%d %b %Y')}"

        msg  = f"📋 <b>WAR MAP — {week_str}</b>\n"
        msg += f"🕐 <i>Emis Duminică {now.strftime('%H:%M')} EET</i>\n"
        msg += SEP + "\n"

        if not days:
            msg += "\n✅ <b>ALL CLEAR</b> — Nicio știre High Impact săptămâna viitoare.\n"
            msg += "🟢 Condiții optime de tranzacționare.\n"
        else:
            for dk in sorted(days.keys()):
                label  = day_labels[dk]
                devts  = days[dk]
                msg   += f"\n📅 <b>{label}</b>\n"
                msg   += SEP + "\n"
                for et, e in devts:
                    flag = _FLAGS.get(e.currency, "🏴")
                    tstr = et.strftime("%H:%M")
                    # Critical badge
                    is_critical = any(
                        kw.lower() in e.event.lower()
                        for kw in ['NFP','Non-Farm','Payroll','FOMC','CPI','GDP',
                                   'Interest Rate','Bank Rate','Official Bank Rate']
                    )
                    badge = "🔥 " if is_critical else "⚠️ "
                    fc_str = f" · F:<code>{e.forecast}</code>" if e.forecast else ""
                    msg += f"{badge}{flag} <b>{e.currency}</b> — {e.event}\n"
                    msg += f"   🕐 <code>{tstr} EET</code>{fc_str}\n"
                msg += "\n"

        msg += SEP + "\n"
        msg += "⚡ <b>Matrix Hunting 24/7 — Știrile sunt combustibil.</b>\n"
        msg += SEP + "\n"
        msg += "─────────────────\n"
        msg += "🔱 <b>AUTHORED BY ФорексГод</b> 🔱\n"
        msg += "🏛️ <b>Глитч Ин Матрикс</b> 🏛️"
        return msg

    # ═══════════════════════════════════════════════════════════════════
    # ⚠️ V12.2 SNIPER ALERTS — 15-Min Blackout Trigger
    # ═══════════════════════════════════════════════════════════════════

    def _send_sniper_alerts(self, events: List['NewsEvent']):
        """
        V13.2 VOLATILITY RADAR — format minimalist ultra-compact.
        Fires a Telegram alert for every upcoming High Impact event that is
        exactly 15 minutes away (window: 14:00 – 15:59 minutes before start).
        Each (date, currency, event) fires only ONCE per session.
        Știrile = combustibil. Matrix execută 24/7, fără blocare.
        """
        if not self.alerts_enabled:
            return

        now = datetime.now(self.local_tz) if self.local_tz else datetime.now()

        for e in events:
            if e.impact not in ("High Impact Expected", "High"):
                continue

            et = e.time
            if et.tzinfo is None and self.local_tz:
                et = self.local_tz.localize(et)
            elif et.tzinfo and self.local_tz:
                et = et.astimezone(self.local_tz)

            delta_s = (et - now).total_seconds()
            # Window: 14 min 00 s  ≤  delta  <  16 min 00 s
            if not (840 <= delta_s < 960):
                continue

            dedup_key = (et.strftime("%Y-%m-%d %H:%M"), e.currency, e.event[:30])
            if dedup_key in self._sniper_alerted:
                continue

            flag = _FLAGS.get(e.currency, "🏴")
            tstr = et.strftime("%H:%M")

            # ── V13.2 FORMAT MINIMALIST VOLATILITY RADAR ──────────────────
            msg  = "⚡ <b>VOLATILITY RADAR</b>\n"
            msg += "━━━━━━━━━━━━━━\n"
            msg += f"📅 <b>Event:</b> {e.event}\n"
            msg += f"🌍 <b>Impact:</b> {flag} {e.currency}\n"
            msg += "⏳ <b>Timer:</b> 15 Minutes\n"
            msg += f"🏛️ <b>Status:</b> Matrix Hunting\n"
            msg += "━━━━━━━━━━━━━━\n"
            msg += "🔱 <b>AUTHORED BY ФорексГод</b> 🔱\n"
            msg += "🏛️ <b>Глитч Ин Матрикс</b> 🏛️"

            try:
                import requests as _req
                resp = _req.post(
                    f"{self.base_url}/sendMessage",
                    data={'chat_id': self.chat_id, 'text': msg, 'parse_mode': 'HTML'},
                    timeout=10,
                )
                if resp.status_code == 200:
                    logger.success(f"⚡ VOLATILITY RADAR sent: {e.currency} {e.event} @ {tstr} EET")
                    self._sniper_alerted.add(dedup_key)
                else:
                    logger.warning(f"⚠️ Sniper alert HTTP {resp.status_code}: {resp.text[:80]}")
            except Exception as ex:
                logger.error(f"❌ Sniper alert failed: {ex}")

    def run_daily_check(self):
        """Main function to run daily news check"""

        logger.info("🚀 Starting Daily News Check...")
        logger.info(f"⏰ Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Try manual calendar first (most reliable - updated monthly)
        logger.info("📖 Loading manual economic calendar...")
        all_events = self.fetch_manual_calendar(days_ahead=7)
        
        # Try cTrader Desktop API as backup (if EconomicCalendarBot is running)
        if not all_events:
            logger.warning("⚠️ Manual calendar empty, trying cTrader Desktop API...")
            all_events = self.fetch_ctrader_calendar(days_ahead=7)
        
        # NO ForexFactory fallback - it crashes Chrome and has Cloudflare protection
        # Manual calendar should be updated monthly using add_monthly_events.py
        
        if not all_events:
            logger.error("❌ No events found! Update economic_calendar.json or start cTrader Desktop")
            logger.error("💡 Run: python3 add_monthly_events.py")
            return
        
        # Filter high impact only
        high_impact = self.filter_high_impact_events(all_events)
        
        logger.info(f"📊 Total events: {len(all_events)}")
        logger.info(f"🚨 High impact: {len(high_impact)}")
        
        if not high_impact:
            logger.warning("⚠️ No high impact events in next 7 days — sending ALL CLEAR")
            message = self.format_telegram_message([])  # sends "ALL CLEAR" message
        else:
            message = self.format_telegram_message(high_impact)
        self.send_telegram_alert(message)
        
        logger.info("✅ Daily news check complete!")
    
    def run_daemon(self):
        """
        🔥 V12.2 INTELLIGENCE PREEMPTIV — Minute-by-Minute Daemon

        Scheduler (Europe/Bucharest):
          • Every minute      → ⚠️ 15-MIN SNIPER ALERT check (High Impact events)
          • Sunday 23:00 EET  → 📋 WAR MAP — weekly High Impact battle plan
          • Monday  09:00 EET → 🏦 MACRO WEEKLY TABLE — CB rates & carry

        The 6-hour periodic report has been REMOVED (redundant with targeted alerts).
        """
        logger.info("\n" + "="*60)
        logger.info("🗞️ NEWS CALENDAR MONITOR V13.2 — VOLATILITY RADAR")
        logger.info("⏱️  Minute-by-minute scheduler active | 24/7 NO BLOCK")
        logger.info(f"📊 Alerts enabled: {self.alerts_enabled}")
        logger.info("📋 Sunday  23:00 EET → WAR MAP (weekly battle plan)")
        logger.info("⚡ Every minute     → VOLATILITY RADAR (15 min before High Impact)")
        logger.info("🏦 Monday  09:00 EET → MACRO WEEKLY TABLE")
        logger.info("🔥 Știrile = combustibil. Matrix Hunting 24/7.")
        logger.info("="*60 + "\n")

        # Pre-load event cache at startup and refresh every 4 hours
        cached_events: List['NewsEvent'] = []
        last_cache_refresh: Optional[datetime] = None
        CACHE_TTL_SECONDS = 4 * 3600  # 4 hours

        iteration = 0

        while True:
            iteration += 1
            now = datetime.now(self.local_tz) if self.local_tz else datetime.now()

            # ━━━ Refresh event cache every 4 hours ━━━
            needs_refresh = (
                last_cache_refresh is None
                or (now - last_cache_refresh).total_seconds() >= CACHE_TTL_SECONDS
            )
            if needs_refresh:
                logger.info(f"🔄 Refreshing event cache (iteration #{iteration})...")
                try:
                    raw = self.fetch_manual_calendar(days_ahead=8)
                    if not raw:
                        raw = self.fetch_ctrader_calendar(days_ahead=8)
                    cached_events = self.filter_high_impact_events(raw)
                    last_cache_refresh = now
                    logger.success(f"✅ Cache refreshed: {len(cached_events)} High Impact events")
                except Exception as ce:
                    logger.error(f"❌ Cache refresh failed: {ce}")

            # ━━━ ⚠️ SNIPER ALERTS — 15-min blackout trigger ━━━
            try:
                self._send_sniper_alerts(cached_events)
            except Exception as se:
                logger.error(f"❌ Sniper alert check failed: {se}")

            # ━━━ 📋 WAR MAP — Sunday 23:00 EET ━━━
            try:
                if self._should_send_war_map():
                    logger.info("📋 Sunday 23:00 detected — sending WAR MAP...")
                    # Fetch full next-week events (not just cached 8 days)
                    raw_wm = self.fetch_manual_calendar(days_ahead=7)
                    if not raw_wm:
                        raw_wm = self.fetch_ctrader_calendar(days_ahead=7)
                    war_msg = self.format_war_map(raw_wm)
                    import requests as _req
                    resp = _req.post(
                        f"{self.base_url}/sendMessage",
                        data={'chat_id': self.chat_id, 'text': war_msg, 'parse_mode': 'HTML'},
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        coming_monday = now + timedelta(days=1)
                        week_key = coming_monday.strftime("%Y-W%W")
                        self._war_map_sent_week = week_key
                        self._save_war_map_sent_week(week_key)
                        logger.success(f"✅ WAR MAP sent for week {week_key}")
                    else:
                        logger.error(f"❌ WAR MAP Telegram error: {resp.status_code} {resp.text[:80]}")
            except Exception as we:
                logger.error(f"❌ WAR MAP send failed: {we}")

            # ━━━ 🏦 MACRO WEEKLY TABLE — Monday 09:00 EET ━━━
            try:
                if self._should_send_macro_report():
                    logger.info("🏦 Monday 09:00+ detected — sending Macro Weekly Table...")
                    macro_msg = self.generate_weekly_macro_report()
                    import requests as _req
                    _req.post(
                        f"{self.base_url}/sendMessage",
                        data={'chat_id': self.chat_id, 'text': macro_msg, 'parse_mode': 'HTML'},
                        timeout=10,
                    )
                    date_str = now.strftime("%Y-%m-%d")
                    self._macro_last_sent_date = date_str
                    self._save_macro_sent_date(date_str)
                    logger.success("✅ Macro Weekly Table sent to Telegram!")
            except Exception as me:
                logger.error(f"❌ Macro report send failed: {me}")

            # ━━━ Heartbeat (every 60 iterations = ~1 hour) ━━━
            if iteration % 60 == 0:
                logger.info(
                    f"💓 HEARTBEAT | iter=#{iteration} "
                    f"| alerts={'ON' if self.alerts_enabled else 'OFF'} "
                    f"| cached_events={len(cached_events)} "
                    f"| ts={now.strftime('%Y-%m-%d %H:%M:%S')}"
                )

            # ━━━ Sleep 60 seconds (minute-by-minute granularity) ━━━
            try:
                time.sleep(60)
            except KeyboardInterrupt:
                logger.warning("\n⚠️ Daemon interrupted by user (Ctrl+C)")
                logger.info("🛑 Shutting down gracefully...")
                break
            except Exception as e:
                logger.error(f"❌ Sleep error: {e}")
                time.sleep(60)


def main():
    """Entry point for V12.2 Intelligence Preemptiv Daemon"""
    parser = argparse.ArgumentParser(
        description='News Calendar Monitor V12.2 — Intelligence Preemptiv'
    )
    # No --interval argument: V12.2 runs minute-by-minute with targeted schedulers
    parser.parse_args()

    # ✅ V10.9 SINGLE-INSTANCE LOCK: Prevent duplicate processes
    _lock_path = Path(__file__).parent / "process_news_calendar_monitor.lock"
    try:
        _lock_fd = open(_lock_path, 'w')
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.error("🔒 Another news_calendar_monitor.py instance is already running. Exiting.")
        sys.exit(0)

    try:
        logger.info("🚀 Starting News Calendar Monitor V12.2 — Intelligence Preemptiv...")
        monitor = NewsCalendarMonitor()
        monitor.run_daemon()

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Daemon stopped by user")
        sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        logger.debug("Stack trace:", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
