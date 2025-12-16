"""
Debug: Open ForexFactory in visible browser to see actual content
"""
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

now = datetime.now()
days_until_sunday = (6 - now.weekday()) % 7
if days_until_sunday == 0 and now.weekday() != 6:
    days_until_sunday = 7
next_sunday = now + timedelta(days=days_until_sunday)
week_param = next_sunday.strftime('%b%d.%Y').lower()

print(f"Opening ForexFactory for week: {week_param}")
print(f"URL: https://www.forexfactory.com/calendar?week={week_param}")
print("\nBrowser will open for 30 seconds - check what you see!")

# Setup Chrome - NOT headless so you can see it
chrome_options = Options()
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

url = f"https://www.forexfactory.com/calendar?week={week_param}"
driver.get(url)

print("\n⏳ Waiting 30 seconds for you to inspect the page...")
print("Check:")
print("1. What dates are shown (Dec 14-20?)")
print("2. How many HIGH impact (red) events you see")
print("3. Are there filters applied?")

time.sleep(30)

# Save HTML after wait
html = driver.page_source
with open('forexfactory_visible_browser.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("\n💾 Saved HTML to: forexfactory_visible_browser.html")

soup = BeautifulSoup(html, 'html.parser')
rows = soup.find_all('tr', class_='calendar__row')

high_count = 0
for row in rows:
    impact_cell = row.find('td', class_='calendar__impact')
    if impact_cell:
        impact_span = impact_cell.find('span')
        if impact_span and 'title' in impact_span.attrs:
            if 'High' in impact_span['title']:
                high_count += 1

print(f"\n📊 Total rows in HTML: {len(rows)}")
print(f"🚨 HIGH impact events in HTML: {high_count}")

driver.quit()
print("\n✅ Done!")
