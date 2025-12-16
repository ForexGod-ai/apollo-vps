"""
Test ForexFactory with HIGH impact filter via URL parameter
"""
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

print("🧪 Testing ForexFactory HIGH Impact Filter...")
print("=" * 60)

# Calculate week parameter
now = datetime.now()
days_until_sunday = (6 - now.weekday()) % 7
if days_until_sunday == 0 and now.weekday() != 6:
    days_until_sunday = 7
next_sunday = now + timedelta(days=days_until_sunday)
week_param = next_sunday.strftime('%b%d.%Y').lower()

# Try different URL parameters
test_urls = [
    f"https://www.forexfactory.com/calendar?week={week_param}",
    f"https://www.forexfactory.com/calendar?week={week_param}&impact=high",
]

chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

for i, url in enumerate(test_urls):
    print(f"\n{'='*60}")
    print(f"Test {i+1}: {url}")
    print('='*60)
    
    driver.get(url)
    time.sleep(5)
    
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CLASS_NAME, "calendar__table"))
    )
    
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    rows = soup.find_all('tr', class_='calendar__row')
    
    # Count HIGH impact
    high_count = 0
    high_events = []
    
    current_date = None
    for row in rows:
        date_cell = row.find('td', class_='calendar__date')
        if date_cell and date_cell.text.strip() and date_cell.text.strip() != 'Date':
            current_date = date_cell.text.strip()
        
        impact_cell = row.find('td', class_='calendar__impact')
        if impact_cell:
            impact_span = impact_cell.find('span')
            if impact_span and 'title' in impact_span.attrs:
                impact = impact_span['title']
                
                if 'High' in impact:
                    high_count += 1
                    event_cell = row.find('td', class_='calendar__event')
                    currency_cell = row.find('td', class_='calendar__currency')
                    
                    if event_cell and high_count <= 10:
                        currency = currency_cell.text.strip() if currency_cell else 'N/A'
                        event_name = event_cell.text.strip()
                        high_events.append(f"{current_date} - {currency}: {event_name}")
    
    print(f"\n📊 Total rows: {len(rows)}")
    print(f"🚨 HIGH impact events: {high_count}")
    
    if high_events:
        print(f"\nFirst {len(high_events)} HIGH impact events:")
        for event in high_events:
            print(f"  - {event}")
    else:
        print("\n❌ No HIGH impact events found!")

driver.quit()
print("\n" + "=" * 60)
print("🧪 Test complete!")
