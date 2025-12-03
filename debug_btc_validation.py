#!/usr/bin/env python3
"""Debug BTCUSD validation - see which check fails"""

from ctrader_data_client import get_ctrader_client
import pandas as pd

client = get_ctrader_client()
df_daily = client.get_historical_data('BTCUSD', 'D1', 200)
df_4h = client.get_historical_data('BTCUSD', 'H4', 200)

# Manual validation simulation
current_price = df_daily['close'].iloc[-1]
entry = 87953.82  # From previous scan
sl = 88703.88
tp = 86070.09

print(f'\n🔍 BTCUSD VALIDATION DEBUG')
print(f'='*60)
print(f'\n📊 Current Setup:')
print(f'   Current Price: ${current_price:,.2f}')
print(f'   Entry: ${entry:,.2f}')
print(f'   SL: ${sl:,.2f}')
print(f'   TP: ${tp:,.2f}')

# Calculate metrics
risk = abs(entry - sl)
reward = abs(tp - entry)
rr = reward / risk
distance_to_tp = abs(current_price - tp)
total_move = abs(entry - tp)
pct_to_tp = (distance_to_tp / total_move) * 100 if total_move > 0 else 0

print(f'\n✅ CHECK 1: R:R >= 2.0')
print(f'   R:R: 1:{rr:.2f}')
print(f'   Result: {"✅ PASS" if rr >= 2.0 else "❌ FAIL"}')

print(f'\n✅ CHECK 2: Distance to TP >= 20%')
print(f'   Current → TP: ${distance_to_tp:,.2f}')
print(f'   Total move: ${total_move:,.2f}')
print(f'   Remaining: {pct_to_tp:.1f}%')
print(f'   Result: {"✅ PASS" if pct_to_tp >= 20 else "❌ FAIL"}')

print(f'\n✅ CHECK 3: SL not broken (SHORT setup)')
print(f'   Current: ${current_price:,.2f}')
print(f'   SL: ${sl:,.2f}')
print(f'   SL broken? Current > SL = {current_price > sl}')
print(f'   Result: {"❌ FAIL - SL HIT!" if current_price > sl else "✅ PASS"}')

print(f'\n{"="*60}')
if rr >= 2.0 and pct_to_tp >= 20 and current_price <= sl:
    print(f'✅ VERDICT: Setup VALID!')
else:
    print(f'❌ VERDICT: Setup INVALID!')
    if rr < 2.0:
        print(f'   Reason: R:R too low ({rr:.2f} < 2.0)')
    if pct_to_tp < 20:
        print(f'   Reason: Too close to TP ({pct_to_tp:.1f}% < 20%)')
    if current_price > sl:
        print(f'   Reason: SL broken (${current_price:,.2f} > ${sl:,.2f})')
print(f'{"="*60}\n')
