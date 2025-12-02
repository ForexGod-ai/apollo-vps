import json

with open('trade_history.json', 'r') as f:
    trades = json.load(f)

active = [t for t in trades if t['status'] == 'OPEN']

print(f"\n✅ ACTIVE TRADES: {len(active)}\n")
for t in active:
    print(f"{t['symbol']} {t['direction']} - Entry: {t.get('entry_price', t.get('entry', 'N/A'))}")
