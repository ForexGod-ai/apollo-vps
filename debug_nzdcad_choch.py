"""
Debug script to check why NZDCAD CHoCH is not detected
Check swing points and CHoCH detection with current settings
"""

import sys
from ctrader_cbot_client import CTraderCBotClient
from smc_detector import SMCDetector
import pandas as pd

def main():
    symbol = "NZDCAD"
    
    print(f"\n{'='*60}")
    print(f"🔍 DEBUGGING {symbol} - CHoCH Detection")
    print(f"{'='*60}\n")
    
    # Get data
    client = CTraderCBotClient()
    df_daily = client.get_historical_data(symbol, 'D1', 250)
    
    print(f"📊 Daily candles: {len(df_daily)}")
    print(f"   Latest close: {df_daily['close'].iloc[-1]:.5f}")
    print(f"   Columns: {list(df_daily.columns)}")
    
    # Test CHoCH detection
    detector = SMCDetector(swing_lookback=5)
    
    # Test swing highs/lows first
    print(f"\n{'='*60}")
    print("🔍 Testing Swing Detection (lookback=5)")
    print(f"{'='*60}")
    
    swing_highs = detector.detect_swing_highs(df_daily)
    swing_lows = detector.detect_swing_lows(df_daily)
    
    print(f"\n✅ Swing Highs: {len(swing_highs)}")
    if swing_highs:
        print("   Last 5 Swing Highs:")
        for sh in swing_highs[-5:]:
            print(f"   [{sh.index}] {sh.price:.5f}")
    
    print(f"\n✅ Swing Lows: {len(swing_lows)}")
    if swing_lows:
        print("   Last 5 Swing Lows:")
        for sl in swing_lows[-5:]:
            print(f"   [{sl.index}] {sl.price:.5f}")
    
    # Test CHoCH detection
    print(f"\n{'='*60}")
    print("🔍 Testing CHoCH Detection (AND logic)")
    print(f"{'='*60}")
    
    chochs, bos_list = detector.detect_choch_and_bos(df_daily)
    
    print(f"\n✅ CHoCH detected: {len(chochs)}")
    if chochs:
        print("   All CHoCH:")
        for i, ch in enumerate(chochs):
            print(f"   [{i}] {ch.direction.upper()} @ {ch.break_price:.5f} (index {ch.index})")
    else:
        print("   ❌ NO CHoCH FOUND!")
        print("\n   💡 This explains why scanner returns 0 setups")
        print("   Need to check if AND logic is too strict")
    
    print(f"\n✅ BOS detected: {len(bos_list)}")
    if bos_list:
        print("   Last 5 BOS:")
        for i, bos in enumerate(bos_list[-5:]):
            print(f"   [{i}] {bos.direction.upper()} @ {bos.break_price:.5f} (index {bos.index})")
    
    # Check last 50 candles for structure
    print(f"\n{'='*60}")
    print("📊 Last 50 Daily Candles Structure")
    print(f"{'='*60}")
    
    last_50 = df_daily.tail(50)
    print(f"\n   Highest: {last_50['high'].max():.5f}")
    print(f"   Lowest: {last_50['low'].min():.5f}")
    print(f"   Current: {last_50['close'].iloc[-1]:.5f}")
    
    # Manual check for bearish→bullish transition
    print(f"\n{'='*60}")
    print("🔍 Manual Check: Looking for Bearish→Bullish Transition")
    print(f"{'='*60}")
    
    # Find recent significant high before potential reversal
    recent_high_idx = last_50['high'].idxmax()
    recent_low_idx = last_50['low'].idxmin()
    
    print(f"\n   Recent High: {df_daily['high'].iloc[recent_high_idx]:.5f} @ index {recent_high_idx}")
    print(f"   Recent Low: {df_daily['low'].iloc[recent_low_idx]:.5f} @ index {recent_low_idx}")
    
    if recent_low_idx > recent_high_idx:
        print(f"\n   ✅ Pattern: High → Low (bearish move)")
        print(f"   Looking for bullish break above {df_daily['high'].iloc[recent_high_idx]:.5f}...")
        
        # Check if price broke back above
        after_low = df_daily.iloc[recent_low_idx+1:]
        if len(after_low) > 0:
            max_after = after_low['high'].max()
            if max_after > df_daily['high'].iloc[recent_high_idx]:
                print(f"   ✅ BULLISH CHoCH: Price broke {max_after:.5f} > {df_daily['high'].iloc[recent_high_idx]:.5f}")
                print(f"   🎯 This is what you see on TradingView!")
            else:
                print(f"   ⏳ Highest since low: {max_after:.5f} (not broken yet)")
    
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    main()
