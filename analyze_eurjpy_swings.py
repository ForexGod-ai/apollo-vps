#!/usr/bin/env python3
"""
🔍 EURJPY SWING DETECTION ANALYSIS
Analyze swing detection to identify the 182.800 CHoCH vs BOS issue
"""

from smc_detector import SMCDetector
from ctrader_cbot_client import CTraderCBotClient

client = CTraderCBotClient()
smc = SMCDetector(swing_lookback=5)

df_daily = client.get_historical_data('EURJPY', 'D1', 100)

print('🔍 SWING DETECTION ANALYSIS - EURJPY DAILY\n')
print('='*80)

swing_highs = smc.detect_swing_highs(df_daily)
swing_lows = smc.detect_swing_lows(df_daily)

print(f'📊 Total Swing Highs: {len(swing_highs)}')
print(f'📊 Total Swing Lows: {len(swing_lows)}')

print(f'\n🔴 LAST 10 SWING HIGHS:')
for sh in swing_highs[-10:]:
    date = sh.candle_time if hasattr(sh.candle_time, 'strftime') else 'N/A'
    date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
    print(f'   Index {sh.index}: {sh.price:.3f} @ {date_str}')

print(f'\n🔵 LAST 10 SWING LOWS:')
for sl in swing_lows[-10:]:
    date = sl.candle_time if hasattr(sl.candle_time, 'strftime') else 'N/A'
    date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
    print(f'   Index {sl.index}: {sl.price:.3f} @ {date_str}')

# Detect CHoCH and BOS
chochs, bos_list = smc.detect_choch_and_bos(df_daily)

print(f'\n{"="*80}')
print(f'💥 CHoCH DETECTED: {len(chochs)}')
for ch in chochs[-5:]:
    print(f'   {ch.direction.upper()} @ {ch.break_price:.3f} (index {ch.index})')

print(f'\n💥 BOS DETECTED: {len(bos_list)}')
for b in bos_list[-5:]:
    print(f'   {b.direction.upper()} @ {b.break_price:.3f} (index {b.index})')

print(f'\n{"="*80}')
print(f'🎯 CHECK: Is 182.800 level detected?')
print('Searching in BOS list...')
for b in bos_list:
    if 182.0 < b.break_price < 183.5:
        print(f'   ✅ FOUND @ {b.break_price:.3f} - Labeled as: BOS (should be CHoCH!)')
        
print('\nSearching in CHoCH list...')
for ch in chochs:
    if 182.0 < ch.break_price < 183.5:
        print(f'   ✅ FOUND @ {ch.break_price:.3f} - Labeled as: CHoCH ✅')

print(f'\n{"="*80}')
print('🔧 PROBLEM ANALYSIS:')
print('   detect_swing_highs: Uses HARDCODED lookback=2 (4 candles)')
print('   detect_swing_lows: Uses self.swing_lookback=5 (10 candles)')
print('   Result: INCONSISTENT swing detection → micro swings on highs')
print('   Fix: Make both use same lookback parameter for MACRO detection')
