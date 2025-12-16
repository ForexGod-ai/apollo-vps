#!/usr/bin/env python3
"""
Test ForexFactory scraping DAY BY DAY instead of week view
"""
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Keywords for critical events
CRITICAL_KEYWORDS = [
    "NFP", "Non-Farm", "Payroll",
    "FOMC", "Fed", "Interest Rate", "Bank Rate",
    "CPI", "Inflation",
    "GDP", "Gross Domestic",
    "ECB", "BOE", "BOJ", "Central Bank",
    "Employment", "Unemployment",
    "Retail Sales",
    "PMI", "Manufacturing", "Services PMI",
    "Flash PMI", "Flash Manufacturing", "Flash Services",
    "Monetary Policy", "MPC", "Official Bank Rate",
    "Claimant Count", "ADP", "Earnings",
    "Bailey", "Lagarde", "Powell"
]

MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF"]

# Setup Selenium
chrome_options = Options()
chrome_options.add_argument('--headless=new')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    # Fetch Dec 14-20 (each day individually)
    all_critical_events = []
    
    for day_offset in range(7):  # 7 days (Dec 14-20)
        date = datetime(2025, 12, 14) + timedelta(days=day_offset)
        day_param = date.strftime('%b%d.%Y').lower()  # e.g., "dec14.2025"
        url = f"https://www.forexfactory.com/calendar?day={day_param}"
        
        print(f"\n🌐 Loading {date.strftime('%a %b %d')}: {url}")
        driver.get(url)
        
        # Wait for calendar
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "calendar__table"))
        )
        time.sleep(2)  # Extra wait for content
        
        # Parse HTML
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table', {'class': 'calendar__table'})
        
        if not table:
            print("❌ No calendar table found")
            continue
        
        rows = table.find_all('tr', {'class': 'calendar__row'})
        print(f"📊 Found {len(rows)} rows")
        
        # Count events for this day
        day_critical = 0
        day_ff_high = 0
        
        for row in rows:
            currency_td = row.find('td', {'class': 'calendar__currency'})
            event_td = row.find('td', {'class': 'calendar__event'})
            
            if not (currency_td and event_td):
                continue
            
            currency = currency_td.get_text(strip=True)
            event_name = event_td.get_text(strip=True)
            
            if currency not in MAJOR_CURRENCIES:
                continue
            
            # Check impact span
            impact_span = row.find('span', {'class': 'icon'})
            is_ff_high = False
            if impact_span:
                classes = impact_span.get('class', [])
                is_ff_high = 'icon--ff-impact-red' in classes
            
            # Check critical keywords
            is_critical = any(kw.lower() in event_name.lower() for kw in CRITICAL_KEYWORDS)
            
            if is_ff_high:
                day_ff_high += 1
            
            if is_critical or is_ff_high:
                marker = "🔥" if is_critical else "⚠️"
                impact_str = "HIGH" if is_ff_high else ("MED" if 'icon--ff-impact-ora' in classes else "LOW")
                print(f"  {marker} {currency:3} {impact_str:4} | {event_name[:60]}")
                all_critical_events.append({
                    'date': date.strftime('%a %b %d'),
                    'currency': currency,
                    'event': event_name,
                    'ff_high': is_ff_high,
                    'critical': is_critical
                })
                if is_critical:
                    day_critical += 1
        
        print(f"  ✅ Day total: {day_critical} critical keywords, {day_ff_high} FF HIGH")
    
    print(f"\n\n📈 FULL WEEK SUMMARY:")
    print(f"Total critical events found: {len(all_critical_events)}")
    
    ff_high_only = sum(1 for e in all_critical_events if e['ff_high'] and not e['critical'])
    critical_only = sum(1 for e in all_critical_events if e['critical'] and not e['ff_high'])
    both = sum(1 for e in all_critical_events if e['critical'] and e['ff_high'])
    
    print(f"  FF HIGH only: {ff_high_only}")
    print(f"  Critical keywords only: {critical_only}")
    print(f"  Both: {both}")
    
finally:
    driver.quit()
    print("\n✅ Done")
