import MetaTrader5 as mt5
import pandas as pd

mt5.initialize()

# Daily data
rates_daily = mt5.copy_rates_from_pos('NZDUSD', mt5.TIMEFRAME_D1, 0, 50)
df_daily = pd.DataFrame(rates_daily)
df_daily['time'] = pd.to_datetime(df_daily['time'], unit='s')

print('\n' + '='*80)
print('🔍 NZDUSD STRUCTURE ANALYSIS - Continuitate sau Reversal?')
print('='*80 + '\n')

print('📊 DAILY TIMEFRAME - Last 15 candles:\n')
recent = df_daily.tail(15)
for idx, row in recent.iterrows():
    candle_color = '🟢' if row['close'] > row['open'] else '🔴'
    print(f"{row['time'].strftime('%Y-%m-%d')} {candle_color} H:{row['high']:.5f} L:{row['low']:.5f} C:{row['close']:.5f}")

print('\n' + '-'*80)
print('📈 TREND ANALYSIS:\n')

# Analyze highs and lows
highs = df_daily['high'].tail(20).tolist()
lows = df_daily['low'].tail(20).tolist()

# Check for Higher Highs / Lower Lows
print('Last 10 Highs:', [f'{h:.5f}' for h in highs[-10:]])
print('Last 10 Lows:', [f'{l:.5f}' for l in lows[-10:]])

# Identify trend
recent_highs = highs[-5:]
recent_lows = lows[-5:]

# Check if making Higher Highs and Higher Lows (bullish trend)
hh_count = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i] > recent_highs[i-1])
hl_count = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i] > recent_lows[i-1])

# Check if making Lower Lows and Lower Highs (bearish trend)  
ll_count = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i] < recent_lows[i-1])
lh_count = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i] < recent_highs[i-1])

print(f'\n📊 Structure Count (last 5 candles):')
print(f'   Higher Highs: {hh_count}/4')
print(f'   Higher Lows: {hl_count}/4')
print(f'   Lower Highs: {lh_count}/4')
print(f'   Lower Lows: {ll_count}/4')

# Determine trend type
print('\n' + '='*80)
if hh_count >= 2 and hl_count >= 2:
    print('✅ VERDICT: BULLISH TREND ESTABLISHED (Higher Highs + Higher Lows)')
    print('\n📋 STRATEGIA: CONTINUITATE BULLISH')
    print('   1. Trend bullish deja în desfășurare ✅')
    print('   2. Așteaptă retragere la Higher Low (HL)')
    print('   3. Caută FVG/Imbalance în zona HL')
    print('   4. Când price ajunge în FVG → switch la 4H')
    print('   5. Pe 4H va fi bearish (retracing)')
    print('   6. Așteaptă 4H CHoCH bullish (confirmă ca zona e bună)')
    print('   7. Entry LONG = continuarea trendului Daily bullish')
    
elif ll_count >= 2 and lh_count >= 2:
    print('✅ VERDICT: BEARISH TREND ESTABLISHED (Lower Lows + Lower Highs)')
    print('\n📋 STRATEGIA: CONTINUITATE BEARISH')
    print('   Similar dar invers pentru SHORT')
    
else:
    # Check for CHoCH (Change of Character)
    # Look for break of previous structure
    old_highs = highs[-15:-5]
    old_lows = lows[-15:-5]
    current_price = df_daily.iloc[-1]['close']
    
    max_old_high = max(old_highs)
    min_old_low = min(old_lows)
    
    # Was bearish, now broke structure high?
    if ll_count >= 2 in [lows[-15:-10]] and current_price > max_old_high:
        print('🔥 VERDICT: REVERSAL - CHoCH BULLISH!')
        print('   Trend era BEARISH → acum a rupt structure high')
        print('\n📋 STRATEGIA: REVERSAL BULLISH')
        print('   1. Daily CHoCH bullish confirmat ✅')
        print('   2. FVG creat în breakout')
        print('   3. Așteaptă retest în FVG')
        print('   4. Switch la 4H când price în FVG')
        print('   5. 4H CHoCH bullish confirmă reversal')
        print('   6. Entry LONG = noul trend bullish')
    else:
        print('⚠️  VERDICT: TRANSITION/RANGING - nu e clar')

print('\n' + '='*80)
print('💡 DIFERENȚA CHEIE:\n')
print('CONTINUITATE = Trend deja existent, trade pullbacks (retrageri)')
print('   → Daily bullish → așteaptă HL în FVG → 4H CHoCH confirmă → continue UP')
print('')
print('REVERSAL = Trend schimbă direcția complet')  
print('   → Daily CHoCH (break structure) → FVG pe breakout → retest → 4H confirmă → new trend')

print('\n' + '='*80)

mt5.shutdown()
