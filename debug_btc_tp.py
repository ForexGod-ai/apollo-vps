#!/usr/bin/env python3
"""
Debug BTCUSD TP calculation - why is it so tight?
"""

from ctrader_data_client import get_ctrader_client
from smc_detector import SMCDetector
import pandas as pd

def debug_btc_tp():
    """Check BTCUSD structure and TP calculation"""
    
    # Get data
    client = get_ctrader_client()
    df_daily = client.get_historical_data('BTCUSD', 'D1', 100)
    df_4h = client.get_historical_data('BTCUSD', 'H4', 200)
    
    print("\n" + "="*60)
    print("🔍 BTCUSD STRUCTURE ANALYSIS")
    print("="*60)
    
    # Current price
    current_price = df_daily['close'].iloc[-1]
    print(f"\n📊 Current Price: ${current_price:,.2f}")
    
    # Last 30 Daily lows (this is what TP uses)
    print(f"\n📉 Last 30 Daily LOWS (for bearish TP):")
    recent_lows = df_daily['low'].iloc[-30:]
    print(f"   Minimum: ${recent_lows.min():,.2f}")
    print(f"   Maximum: ${recent_lows.max():,.2f}")
    print(f"   Current TP target: ${recent_lows.min():,.2f}")
    
    # Calculate potential R:R with this TP
    print(f"\n💡 If SHORT setup at ~${current_price:,.2f}:")
    entry = current_price
    
    # Find last high on 4H (SL)
    recent_highs = df_4h['high'].iloc[-30:]
    sl = recent_highs.max()
    
    # TP = min low on daily
    tp = recent_lows.min()
    
    risk = abs(entry - sl)
    reward = abs(entry - tp)
    rr = reward / risk if risk > 0 else 0
    
    print(f"   Entry: ${entry:,.2f}")
    print(f"   SL: ${sl:,.2f} (last 4H high)")
    print(f"   TP: ${tp:,.2f} (last 30D low)")
    print(f"   Risk: ${risk:,.2f}")
    print(f"   Reward: ${reward:,.2f}")
    print(f"   R:R: 1:{rr:.2f}")
    
    # Find better TP targets
    print(f"\n🎯 ALTERNATIVE TP TARGETS (for better R:R):")
    
    # Major swing lows on Daily (last 50 days)
    detector = SMCDetector(swing_lookback=5)
    swing_lows = detector.detect_swing_lows(df_daily.iloc[-50:])
    
    if swing_lows:
        print(f"\n   Major Swing Lows (last 50 days):")
        for i, swing in enumerate(swing_lows[-5:]):  # Last 5 swing lows
            test_tp = swing.price
            test_reward = abs(entry - test_tp)
            test_rr = test_reward / risk if risk > 0 else 0
            print(f"   {i+1}. ${test_tp:,.2f} → R:R 1:{test_rr:.2f}")
    
    # Check last major low (60-90 days ago)
    print(f"\n   Extended lookback (60-90 days):")
    if len(df_daily) >= 90:
        lows_60d = df_daily['low'].iloc[-90:-30].min()
        lows_90d = df_daily['low'].iloc[-90:].min()
        
        reward_60d = abs(entry - lows_60d)
        reward_90d = abs(entry - lows_90d)
        rr_60d = reward_60d / risk if risk > 0 else 0
        rr_90d = reward_90d / risk if risk > 0 else 0
        
        print(f"   60-day low: ${lows_60d:,.2f} → R:R 1:{rr_60d:.2f}")
        print(f"   90-day low: ${lows_90d:,.2f} → R:R 1:{rr_90d:.2f}")
    
    # Fibonacci levels
    print(f"\n   Fibonacci Extension Targets:")
    # Find recent major swing high and low
    recent_high = df_daily['high'].iloc[-30:].max()
    recent_low = df_daily['low'].iloc[-30:].min()
    range_size = recent_high - recent_low
    
    fib_127 = recent_high - (range_size * 1.272)
    fib_162 = recent_high - (range_size * 1.618)
    fib_200 = recent_high - (range_size * 2.0)
    
    reward_127 = abs(entry - fib_127)
    reward_162 = abs(entry - fib_162)
    reward_200 = abs(entry - fib_200)
    
    rr_127 = reward_127 / risk if risk > 0 else 0
    rr_162 = reward_162 / risk if risk > 0 else 0
    rr_200 = reward_200 / risk if risk > 0 else 0
    
    print(f"   Fib 127.2%: ${fib_127:,.2f} → R:R 1:{rr_127:.2f}")
    print(f"   Fib 161.8%: ${fib_162:,.2f} → R:R 1:{rr_162:.2f}")
    print(f"   Fib 200.0%: ${fib_200:,.2f} → R:R 1:{rr_200:.2f}")
    
    print("\n" + "="*60)
    print("💡 RECOMMENDATION:")
    print("="*60)
    print("For BTCUSD, consider:")
    print("1. Extend TP lookback to 60-90 days (more room to fall)")
    print("2. Use Fibonacci extensions (1.618x or 2x)")
    print("3. Target major swing lows, not recent mini-pullbacks")
    print("="*60 + "\n")

if __name__ == "__main__":
    debug_btc_tp()
