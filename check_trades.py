import json
from datetime import datetime

with open('trade_history.json', 'r') as f:
    trades = json.load(f)

print('📊 TRADE HISTORY SUMMARY\n')
print(f'Total trades: {len(trades)}')

open_trades = [t for t in trades if t['status'] == 'OPEN']
closed_trades = [t for t in trades if 'CLOSED' in t['status']]

print(f'\n🟢 OPEN POSITIONS: {len(open_trades)}')
for t in open_trades:
    print(f"  • {t['symbol']} {t['direction']} @ {t['entry_price']:.5f} | R:R {t['risk_reward']:.2f} | {t['strategy_type'].upper()}")

print(f'\n🔴 CLOSED TRADES: {len(closed_trades)}')
total_profit = sum([t.get('profit', 0) for t in closed_trades if t.get('profit')])
print(f'  Total P/L: ${total_profit:.2f}')

for t in closed_trades:
    profit = t.get('profit', 0)
    emoji = '✅' if profit > 0 else '❌'
    print(f"  {emoji} {t['symbol']} {t['direction']} | P/L: ${profit:.2f}")

print('\n📅 Last trade opened:', trades[-1]['open_time'] if trades else 'None')
