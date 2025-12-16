"""
Test ForexFactory Scraper - Debug ce primim de pe site
"""

import requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import urllib3
import ssl
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import certifi

# Disable SSL warnings (since we're disabling verification)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Custom adapter using certifi certificates
class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context(cafile=certifi.where())
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

print("🧪 Testing ForexFactory Calendar Scraper...")
print("=" * 60)

# Calculate week parameter
now = datetime.now()
days_until_sunday = (6 - now.weekday()) % 7
if days_until_sunday == 0 and now.weekday() != 6:
    days_until_sunday = 7
next_sunday = now + timedelta(days=days_until_sunday)
week_param = next_sunday.strftime('%b%d.%Y').lower()

url = f"https://www.forexfactory.com/calendar?week={week_param}"
print(f"📅 Using week parameter: {week_param}")
print(f"\n📡 Fetching: {url}")
print(f"🕐 Time: {datetime.now()}")
print("\n⚙️  Using cloudscraper to bypass Cloudflare...")
print()

try:
    # Create cloudscraper with certifi certificates
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'darwin',
            'desktop': True
        }
    )
    
    # Mount SSL adapter with certifi certificates
    scraper.mount('https://', SSLAdapter())
    
    response = scraper.get(url, timeout=30)
    print(f"✅ Status Code: {response.status_code}")
    print(f"📦 Content Length: {len(response.text)} bytes")
    print()
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for calendar rows
        calendar_rows = soup.find_all('tr', class_='calendar__row')
        print(f"📊 Found {len(calendar_rows)} calendar rows")
        
        if len(calendar_rows) == 0:
            print("\n❌ NO CALENDAR ROWS FOUND!")
            print("\n🔍 Looking for alternative selectors...")
            
            # Try different selectors
            alt_selectors = [
                ('table.calendar__table', 'Calendar table'),
                ('tr[class*="calendar"]', 'TR with calendar class'),
                ('div.calendar', 'Calendar div'),
                ('tbody', 'Table body')
            ]
            
            for selector, desc in alt_selectors:
                elements = soup.select(selector)
                print(f"   {desc}: {len(elements)} found")
            
            # Save HTML for manual inspection
            with open('forexfactory_debug.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print("\n💾 Saved HTML to forexfactory_debug.html for inspection")
            
        else:
            print("\n✅ Calendar rows found! Parsing first 5...")
            print()
            
            for i, row in enumerate(calendar_rows[:5]):
                print(f"--- Row {i+1} ---")
                
                # Try to extract data
                date_cell = row.find('td', class_='calendar__date')
                time_cell = row.find('td', class_='calendar__time')
                currency_cell = row.find('td', class_='calendar__currency')
                impact_cell = row.find('td', class_='calendar__impact')
                event_cell = row.find('td', class_='calendar__event')
                
                print(f"Date: {date_cell.text.strip() if date_cell else 'N/A'}")
                print(f"Time: {time_cell.text.strip() if time_cell else 'N/A'}")
                print(f"Currency: {currency_cell.text.strip() if currency_cell else 'N/A'}")
                print(f"Event: {event_cell.text.strip() if event_cell else 'N/A'}")
                
                # Check impact
                if impact_cell:
                    impact_span = impact_cell.find('span')
                    if impact_span:
                        impact_class = impact_span.get('class', [])
                        print(f"Impact classes: {impact_class}")
                        if 'icon--ff-impact-red' in impact_class:
                            print("🔴 HIGH IMPACT!")
                        elif 'icon--ff-impact-ora' in impact_class:
                            print("🟠 MEDIUM IMPACT")
                        else:
                            print("🟡 LOW IMPACT")
                print()
        
    else:
        print(f"❌ Failed to fetch: HTTP {response.status_code}")
        print(f"Response: {response.text[:500]}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)
print("🧪 Test complete!")
