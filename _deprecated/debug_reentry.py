#!/usr/bin/env python3
"""Debug RE-ENTRY logic for BTCUSD"""

from ctrader_data_client import get_ctrader_client

client = get_ctrader_client()
df_daily = client.get_historical_data('BTCUSD', 'D1', 200)

current_price = df_daily['close'].iloc[-1]
print(f'\n🔍 BTCUSD RE-ENTRY DEBUG')
print(f'='*60)
print(f'\n📊 Current Price: ${current_price:,.2f}')

# Check trend continuation (BEARISH)
recent_candles = df_daily.iloc[-10:]
older_candles = df_daily.iloc[-30:-10]

recent_low = recent_candles['low'].min()
older_low = older_candles['low'].min()
trend_continues = recent_low < older_low

print(f'\n📉 BEARISH Trend Check:')
print(f'   Recent low (last 10D): ${recent_low:,.2f}')
print(f'   Older low (10-30D ago): ${older_low:,.2f}')
print(f'   Trend continues? {trend_continues}')
print(f'   Result: {"✅ YES - making lower lows" if trend_continues else "❌ NO - trend broken"}')

if trend_continues:
    # Calculate RE-ENTRY parameters
    entry = current_price
    sl = recent_candles['high'].max()
    tp = 80659.81  # Original TP (30D low)
    
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr = reward / risk if risk > 0 else 0
    
    print(f'\n🔄 RE-ENTRY Parameters:')
    print(f'   New Entry: ${entry:,.2f}')
    print(f'   New SL (recent high): ${sl:,.2f}')
    print(f'   TP (unchanged): ${tp:,.2f}')
    print(f'   Risk: ${risk:,.2f}')
    print(f'   Reward: ${reward:,.2f}')
    print(f'   R:R: 1:{rr:.2f}')
    
    if rr >= 2.0:
        print(f'\n✅ RE-ENTRY VALID! R:R {rr:.2f} >= 2.0')
        if rr >= 5.0:
            print(f'🚀 AUTO-EXECUTE ready! (R:R >= 5.0)')
    else:
        print(f'\n❌ RE-ENTRY rejected (R:R {rr:.2f} < 2.0)')
else:
    print(f'\n❌ No RE-ENTRY - trend broken')

print(f'\n{"="*60}\n')
