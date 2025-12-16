"""
Check active trades and verify website posting
"""
import json
import requests
from loguru import logger

# Check active trades
with open('trade_history.json', 'r') as f:
    history = json.load(f)

active_trades = [t for t in history if t['status'] == 'OPEN']

print("\n" + "="*60)
print(f"🔓 ACTIVE TRADES: {len(active_trades)}")
print("="*60)

for i, trade in enumerate(active_trades, 1):
    print(f"\n{i}. {trade['symbol']} {trade['direction']}")
    print(f"   Ticket: #{trade['ticket']}")
    print(f"   Entry: {trade.get('entry', trade.get('entry_price', 'N/A'))}")
    print(f"   Status: {trade['status']}")
    print(f"   Opened: {trade['open_time']}")

# Check if website is running
print("\n" + "="*60)
print("🌐 Checking website connection...")
print("="*60)

try:
    response = requests.get("http://127.0.0.1:5001/", timeout=2)
    print(f"✅ Website is ONLINE (status: {response.status_code})")
except Exception as e:
    print(f"❌ Website is OFFLINE: {e}")
    print("\n⚠️ Trade-urile nu pot fi postate dacă website-ul nu rulează!")
    print("   Pornește website-ul cu: python app.py (în folderul website)")

print("\n" + "="*60)
print("💡 INFO:")
print("="*60)
print("Trade-urile se postează AUTOMAT când auto_trader le execută.")
print("Dacă website-ul era offline când trade-ul s-a deschis, nu a fost postat.")
print("Soluție: Re-postează manual sau așteaptă noi trade-uri cu website-ul pornit.")
