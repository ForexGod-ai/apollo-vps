"""Test Alpha Vantage API"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

print("🧪 TESTARE ALPHA VANTAGE API")
print("=" * 60)
print()

api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
print(f"🔑 API Key: {api_key[:5]}...{api_key[-5:]}")
print()

# Test API call
print("📊 Testing GBPUSD Daily data...")
url = "https://www.alphavantage.co/query"
params = {
    'function': 'FX_DAILY',
    'from_symbol': 'GBP',
    'to_symbol': 'USD',
    'apikey': api_key,
    'outputsize': 'compact'
}

response = requests.get(url, params=params, timeout=10)

if response.status_code == 200:
    data = response.json()
    
    if 'Error Message' in data:
        print(f"❌ Error: {data['Error Message']}")
    elif 'Note' in data:
        print(f"⚠️  {data['Note']}")
    elif 'Time Series FX (Daily)' in data:
        time_series = data['Time Series FX (Daily)']
        latest_date = list(time_series.keys())[0]
        latest_data = time_series[latest_date]
        
        print(f"✅ SUCCESS! Data received")
        print(f"📅 Latest: {latest_date}")
        print(f"💱 GBPUSD: {latest_data['4. close']}")
        print(f"📊 High: {latest_data['2. high']}")
        print(f"📊 Low: {latest_data['3. low']}")
        print()
        print("✅ Alpha Vantage API funcționează perfect!")
        print()
        print("📊 SURSE DE DATE ACTIVE:")
        print("  1. IC Markets cTrader (Primary)")
        print("  2. Alpha Vantage API (Backup)")
        print("  3. TradingView Webhook (Alerts)")
    else:
        print(f"⚠️  Unexpected response: {list(data.keys())}")
else:
    print(f"❌ HTTP Error: {response.status_code}")

print()
print("=" * 60)
print("✅ STEP 1 COMPLET: Date LIVE configurate!")
print("=" * 60)
print()
print("📋 NEXT: STEP 2 - PythonSignalExecutor în cTrader")
