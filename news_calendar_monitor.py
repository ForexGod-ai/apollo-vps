"""
Forex News Calendar Monitor for ForexGod Trading System
Monitors high-impact economic events and sends Telegram alerts
Uses ForexFactory calendar with Selenium to bypass Cloudflare
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import logging
import requests  # For Telegram API and cTrader calendar
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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


class NewsCalendarMonitor:
    """Monitors forex economic calendar and sends alerts"""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        if not self.bot_token or not self.chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
        
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
            
            with open(calendar_file, 'r') as f:
                data = json.load(f)
            
            # Try current month first, then fallback to other sections
            current_month = now.strftime("%B_%Y").lower()  # e.g., "january_2026"
            section_name = f'custom_events_{current_month}'
            
            custom_events = data.get(section_name, [])
            
            # Fallback to December 2025 if current month not found
            if not custom_events:
                custom_events = data.get('custom_events_december_2025', [])
                logger.warning(f"⚠️ Section '{section_name}' not found, using December 2025 events")
            else:
                logger.info(f"✅ Using events from '{section_name}'")
            
            now = datetime.now()
            end_date = now + timedelta(days=days_ahead)
            
            events = []
            for e in custom_events:
                try:
                    event_date = datetime.strptime(e['date'], '%Y-%m-%d')
                    
                    # Add time if specified
                    if 'time' in e:
                        time_parts = e['time'].split(':')
                        event_date = event_date.replace(
                            hour=int(time_parts[0]),
                            minute=int(time_parts[1])
                        )
                    else:
                        event_date = event_date.replace(hour=12, minute=0)
                    
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
                                # Try with day name first
                                if len(date_str.split()) == 3:  # e.g., "Sun Dec 14"
                                    current_date = datetime.strptime(f"{date_str} {datetime.now().year}", "%a %b %d %Y")
                                else:  # e.g., "Dec 14"
                                    current_date = datetime.strptime(f"{date_str} {datetime.now().year}", "%b %d %Y")
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
                                    if 'High' in impact:
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
        Uses both ForexFactory classification AND keyword detection for critical events
        """
        high_impact = []
        
        for event in events:
            # Check if major currency
            if event.currency not in self.major_currencies:
                continue
            
            # Method 1: ForexFactory marked as HIGH impact
            is_ff_high = "High" in event.impact
            
            # Method 2: Contains critical keywords (override ForexFactory classification)
            is_critical = any(keyword.lower() in event.event.lower() for keyword in self.critical_keywords)
            
            # Accept if either condition is true
            if is_ff_high or is_critical:
                event.is_critical = is_critical  # Mark if it matches critical keywords
                high_impact.append(event)
        
        return high_impact
    
    def format_telegram_message(self, events: List[NewsEvent]) -> str:
        """Format news events into Telegram message"""
        if not events:
            return "✅ No high-impact news in the next 48 hours. Safe to trade! 💰"
        
        # Currency flag emojis
        flags = {
            'USD': '🇺🇸', 'EUR': '🇪🇺', 'GBP': '🇬🇧', 'JPY': '🇯🇵',
            'AUD': '🇦🇺', 'NZD': '🇳🇿', 'CAD': '🇨🇦', 'CHF': '🇨🇭'
        }
        
        message = "⚠️ *HIGH IMPACT NEWS ALERT* ⚠️\n\n"
        message += "🚨 *AVOID TRADING DURING THESE TIMES* 🚨\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Group by date
        events_by_date = {}
        for event in events:
            date_key = event.time.strftime("%A, %B %d")
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            events_by_date[date_key].append(event)
        
        for date, date_events in events_by_date.items():
            message += f"📅 *{date}*\n\n"
            
            for event in date_events:
                flag = flags.get(event.currency, '🏴')
                time_str = event.time.strftime("%I:%M %p")
                
                # Time until event
                now = datetime.now()
                time_diff = event.time - now
                hours = int(time_diff.total_seconds() // 3600)
                
                if hours < 1:
                    countdown = "⏰ *SOON*"
                elif hours < 24:
                    countdown = f"⏰ in {hours}h"
                else:
                    days = hours // 24
                    countdown = f"⏰ in {days}d {hours % 24}h"
                
                # Critical marker
                critical_marker = "🔥 *CRITICAL* " if hasattr(event, 'is_critical') and event.is_critical else ""
                
                message += f"{flag} *{event.currency}* - {time_str} {countdown}\n"
                message += f"{critical_marker}{event.event}\n"
                
                if event.forecast:
                    message += f"📊 Forecast: {event.forecast}\n"
                if event.previous:
                    message += f"📈 Previous: {event.previous}\n"
                
                message += "\n"
            
            message += "─────────────────────\n\n"
        
        message += "💡 *Trading Tip:*\n"
        message += "Close positions 30min before news\n"
        message += "Wait 15-30min after for volatility to settle\n\n"
        message += "🤖 ForexGod AI - Glitch in Matrix"
        
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
            logger.warning("⚠️ No high impact events found!")
            return
        
        # Format and send alert
        message = self.format_telegram_message(high_impact)
        self.send_telegram_alert(message)
        
        logger.info("✅ Daily news check complete!")


def main():
    """Entry point for script"""
    try:
        monitor = NewsCalendarMonitor()
        monitor.run_daily_check()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
