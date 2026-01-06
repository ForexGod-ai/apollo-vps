#!/usr/bin/env python3
"""
Check if we can find basic patterns in historical data
"""

import sys
import pandas as pd
from datetime import datetime
from ctrader_cbot_client import CTraderCBotClient
from smc_detector import SMCDetector

def main():
    print("🔍 Checking pattern detection in historical data...\n")
    
    client = CTraderCBotClient()
    detector = SMCDetector(swing_lookback=5)
    
    # Download NZDUSD data
    symbol = 'NZDUSD'
    print(f"📊 Downloading {symbol} data...")
    
    df_daily = client.get_historical_data(symbol, 'D1', 465)
    df_4h = client.get_historical_data(symbol, 'H4', 2690)
    
    print(f"   ✅ Daily: {len(df_daily)} candles ({df_daily.index[0].date()} to {df_daily.index[-1].date()})")
    print(f"   ✅ 4H: {len(df_4h)} candles\n")
    
    # Step 1: Check for swing highs/lows on Daily
    print("🔎 Step 1: Detecting Daily swing points...")
    highs = detector.detect_swing_highs(df_daily)
    lows = detector.detect_swing_lows(df_daily)
    print(f"   Found {len(highs)} swing highs, {len(lows)} swing lows\n")
    
    # Step 2: Check for Daily CHoCH
    print("🔎 Step 2: Detecting Daily CHoCH patterns...")
    try:
        daily_chochs = detector._detect_choch(df_daily)
        print(f"   Found {len(daily_chochs)} Daily CHoCH patterns")
        
        if len(daily_chochs) > 0:
            # Show last 3
            print("\n   Last 3 CHoCH patterns:")
            for choch in daily_chochs[-3:]:
                choch_date = df_daily.index[choch.break_index]
                print(f"      - {choch.direction.upper()} CHoCH at {choch_date.date()}")
    except Exception as e:
        print(f"   ❌ Error detecting CHoCH: {e}")
    
    # Step 3: Check for Daily FVGs
    print("\n🔎 Step 3: Detecting Daily FVG patterns...")
    try:
        daily_fvgs = detector._detect_fvg(df_daily)
        print(f"   Found {len(daily_fvgs)} Daily FVG patterns")
        
        if len(daily_fvgs) > 0:
            # Show last 3
            print("\n   Last 3 FVG patterns:")
            for fvg in daily_fvgs[-3:]:
                fvg_date = df_daily.index[fvg.index]
                quality = fvg.quality_score if hasattr(fvg, 'quality_score') else 'N/A'
                print(f"      - {fvg.direction.upper()} FVG at {fvg_date.date()} | Quality: {quality}")
    except Exception as e:
        print(f"   ❌ Error detecting FVG: {e}")
    
    # Step 4: Try scanning different historical points
    print("\n🔎 Step 4: Attempting scans at different historical points...")
    
    scan_points = [100, 200, 300, 400]  # Different points in history
    setups_found = 0
    
    for i in scan_points:
        if i >= len(df_daily):
            continue
        
        scan_date = df_daily.index[i]
        df_daily_slice = df_daily.iloc[:i+1]
        df_4h_slice = df_4h[df_4h.index <= scan_date]
        
        if len(df_4h_slice) < 200:
            continue
        
        try:
            setup = detector.scan_for_setup(
                symbol=symbol,
                df_daily=df_daily_slice,
                df_4h=df_4h_slice,
                priority=1,
                df_1h=None
            )
            
            if setup:
                setups_found += 1
                print(f"   ✅ FOUND SETUP at {scan_date.date()}")
                print(f"      Type: {setup.get('pattern_type', 'N/A')}")
                print(f"      Direction: {setup.get('direction', 'N/A')}")
                print(f"      Status: {setup.get('status', 'N/A')}")
        except Exception as e:
            pass
    
    print(f"\n📊 Summary: Found {setups_found} setups across {len(scan_points)} sample points")
    
    if setups_found == 0:
        print("\n⚠️ WARNING: No setups found in any historical scan!")
        print("   This suggests the V3.0 filters may be too restrictive.")
        print("   Consider:")
        print("   1. Lowering FVG quality threshold (70 → 60)")
        print("   2. Relaxing body dominance requirement (70% → 60%)")
        print("   3. Removing 4H CHoCH requirement for V2.1 comparison")

if __name__ == "__main__":
    main()
