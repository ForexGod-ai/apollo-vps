"""
Test ForexFactory Scraper with Selenium - Bypass Cloudflare with real browser
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

print("🧪 Testing ForexFactory Calendar Scraper with Selenium...")
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
print("\n🌐 Starting Chrome browser...")

try:
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in background
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Initialize driver
    print("⚙️  Installing ChromeDriver...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    print("🚀 Loading page...")
    driver.get(url)
    
    # Wait for Cloudflare to pass
    print("⏳ Waiting for Cloudflare challenge...")
    time.sleep(5)
    
    # Wait for calendar table to load
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "calendar__table"))
        )
        print("✅ Calendar loaded successfully!")
    except:
        print("⚠️  Timeout waiting for calendar table")
    
    # Get page source
    html = driver.page_source
    print(f"📦 Content Length: {len(html)} bytes")
    
    # Save HTML for inspection
    with open('forexfactory_selenium.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("💾 Saved HTML to: forexfactory_selenium.html")
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    # Check for Cloudflare challenge
    if "Just a moment" in html or "Cloudflare" in html[:1000]:
        print("\n⚠️  Cloudflare challenge detected in response")
    
    # Find calendar rows
    calendar_rows = soup.find_all('tr', class_='calendar__row')
    print(f"\n📊 Found {len(calendar_rows)} calendar rows")
    
    if calendar_rows:
        print("\n✅ SUCCESS - Events found!")
        print("\nFirst 3 events:")
        for i, row in enumerate(calendar_rows[:3]):
            # Extract event details
            time_cell = row.find('td', class_='calendar__time')
            currency_cell = row.find('td', class_='calendar__currency')
            impact_cell = row.find('td', class_='calendar__impact')
            event_cell = row.find('td', class_='calendar__event')
            
            event_time = time_cell.text.strip() if time_cell else "N/A"
            currency = currency_cell.text.strip() if currency_cell else "N/A"
            event_name = event_cell.text.strip() if event_cell else "N/A"
            
            impact = "N/A"
            if impact_cell:
                impact_span = impact_cell.find('span')
                if impact_span and 'title' in impact_span.attrs:
                    impact = impact_span['title']
            
            print(f"\n  {i+1}. {currency} - {event_name}")
            print(f"     Time: {event_time} | Impact: {impact}")
    else:
        print("\n❌ No calendar rows found")
        print("\nChecking page title and first 500 chars:")
        print(f"Title: {soup.title.string if soup.title else 'No title'}")
        print(f"Content: {html[:500]}")
    
    driver.quit()
    print("\n" + "=" * 60)
    print("🧪 Test complete!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    try:
        driver.quit()
    except:
        pass
