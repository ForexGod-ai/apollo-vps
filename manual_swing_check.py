import MetaTrader5 as mt5
import pandas as pd

mt5.initialize()

# Get GBPUSD Daily
rates = mt5.copy_rates_from_pos('GBPUSD', mt5.TIMEFRAME_D1, 0, 30)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

print("=" * 80)
print("GBPUSD - Last 20 CLOSE prices for swing analysis")
print("=" * 80)

closes = df['close'].values[-20:]
times = df['time'].values[-20:]

for i, (t, c) in enumerate(zip(times, closes)):
    print(f"{i}: {pd.to_datetime(t).strftime('%Y-%m-%d')} | CLOSE: {c:.5f}")

print("\n" + "=" * 80)
print("MANUAL SWING IDENTIFICATION")
print("=" * 80)

# Find swing highs and lows manually
for j in range(2, len(closes) - 2):
    curr = closes[j]
    
    # Swing HIGH check
    if (curr > closes[j-1] and curr > closes[j-2] and 
        curr > closes[j+1] and curr > closes[j+2]):
        print(f"✅ SWING HIGH at index {j} ({pd.to_datetime(times[j]).strftime('%Y-%m-%d')}): {curr:.5f}")
    
    # Swing LOW check
    if (curr < closes[j-1] and curr < closes[j-2] and 
        curr < closes[j+1] and curr < closes[j+2]):
        print(f"📉 SWING LOW at index {j} ({pd.to_datetime(times[j]).strftime('%Y-%m-%d')}): {curr:.5f}")

mt5.shutdown()
