#!/usr/bin/env python3
"""
🎯 PREMIUM/DISCOUNT ZONE VALIDATION TEST
=========================================
Test Premium/Discount (50% Equilibrium) filtering on USDCHF Daily

Purpose:
- Verify that BEARISH setups only trigger in PREMIUM zones (above 50%)
- Verify that BULLISH setups only trigger in DISCOUNT zones (below 50%)
- Show which setups would be REJECTED by shallow retracement filter

This is the "Masterclass" filter that eliminates retail inducement zones.
"""

import sys
from pathlib import Path
from typing import Optional
import requests
import pandas as pd

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from smc_detector import SMCDetector

# Configuration
import sys
SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "USDCHF"
TIMEFRAME = "D1"
BAR_COUNT = 100

def fetch_data(symbol: str) -> Optional[pd.DataFrame]:
    """Fetch data from cTrader API"""
    try:
        url = f"http://localhost:8767/price?symbol={symbol}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            bars = data.get('bars', [])
            
            if bars:
                df = pd.DataFrame(bars[-BAR_COUNT:])  # Last 100 bars
                
                # Convert time to datetime
                if 'time' in df.columns:
                    df['time'] = pd.to_datetime(df['time'])
                    df.set_index('time', inplace=True)
                
                print(f"✅ Fetched {len(df)} bars for {symbol}")
                return df
        
        print(f"❌ API error: {response.status_code}")
        return None
    
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return None

def main():
    """Test Premium/Discount filtering on USDCHF"""
    print(f"\n{'='*80}")
    print(f"🎯 PREMIUM/DISCOUNT ZONE VALIDATION TEST")
    print(f"{'='*80}\n")
    print(f"Symbol: {SYMBOL}")
    print(f"Bars: {BAR_COUNT}")
    print(f"Filter: 50% Fibonacci Equilibrium (Premium/Discount)\n")
    
    # Fetch data
    df = fetch_data(SYMBOL)
    if df is None:
        print("\n❌ Test failed - could not fetch data")
        return 1
    
    # Initialize detector with ATR filter
    detector = SMCDetector(swing_lookback=5, atr_multiplier=1.5)
    
    # Run scan with DEBUG mode
    print(f"\n{'='*80}")
    print(f"🔍 SCANNING {SYMBOL} (DEBUG MODE)")
    print(f"{'='*80}\n")
    
    # Create dummy 4H data (not used for this test, but required by scan_for_setup)
    df_4h = df.copy()  # Simplified for test
    
    # Temporarily patch the debug check in scan_for_setup to enable debug for USDCHF
    # We'll test with a symbol that triggers debug mode, or manually analyze
    
    # Alternative: Manually run the analysis steps with debug output
    print("📊 Step 1: Detect CHoCH and BOS...\n")
    chochs, bos_list = detector.detect_choch_and_bos(df)
    
    print(f"   CHoCH detected: {len(chochs)}")
    if chochs:
        for i, c in enumerate(chochs[-3:]):
            print(f"      [{i}] {c.direction.upper()} @ {c.break_price:.5f} (bar {c.index})")
    
    print(f"   BOS detected: {len(bos_list)}")
    if bos_list:
        for i, b in enumerate(bos_list[-3:]):
            print(f"      [{i}] {b.direction.upper()} @ {b.break_price:.5f} (bar {b.index})")
    
    if not chochs and not bos_list:
        print("\n❌ No CHoCH or BOS detected - cannot test Premium/Discount filter")
        return 1
    
    # Get latest signal
    latest_choch = chochs[-1] if chochs else None
    latest_bos = bos_list[-1] if bos_list else None
    
    latest_signal = None
    if latest_choch and latest_bos:
        latest_signal = latest_choch if latest_choch.index > latest_bos.index else latest_bos
    elif latest_choch:
        latest_signal = latest_choch
    elif latest_bos:
        latest_signal = latest_bos
    
    print(f"\n📊 Step 2: Detect FVG...\n")
    current_price = df['close'].iloc[-1]
    fvg = detector.detect_fvg(df, latest_signal, current_price)
    
    if not fvg:
        print("   ❌ No FVG found")
        return 1
    
    print(f"   ✅ FVG Found:")
    print(f"      Direction: {fvg.direction.upper()}")
    print(f"      Zone: {fvg.bottom:.5f} - {fvg.top:.5f}")
    print(f"      Middle: {fvg.middle:.5f}")
    
    print(f"\n📊 Step 3: Calculate Equilibrium (50% level)...\n")
    swing_highs = detector.detect_swing_highs(df)
    swing_lows = detector.detect_swing_lows(df)
    equilibrium = detector.calculate_equilibrium(df, swing_highs, swing_lows)
    
    if equilibrium is None:
        print("   ❌ Could not calculate equilibrium")
        return 1
    
    print(f"   ✅ Equilibrium: {equilibrium:.5f}")
    print(f"      Macro High: {swing_highs[-1].price:.5f} (bar {swing_highs[-1].index})")
    print(f"      Macro Low: {swing_lows[-1].price:.5f} (bar {swing_lows[-1].index})")
    
    print(f"\n📊 Step 4: Validate Premium/Discount Zone...\n")
    is_valid = detector.validate_fvg_zone(fvg, equilibrium, latest_signal.direction, debug=True)
    print(f"\n📊 Step 4: Validate Premium/Discount Zone...\n")
    is_valid = detector.validate_fvg_zone(fvg, equilibrium, latest_signal.direction, debug=True)
    
    # Results
    print(f"\n{'='*80}")
    print(f"📊 TEST RESULTS")
    print(f"{'='*80}\n")
    
    if is_valid:
        print(f"✅ FVG PASSED Premium/Discount validation")
        zone_type = "PREMIUM" if latest_signal.direction == 'bearish' else "DISCOUNT"
        print(f"   Zone Type: {zone_type} (>50% retracement)")
        print(f"   Setup Direction: {latest_signal.direction.upper()}")
        print(f"   FVG Middle: {fvg.middle:.5f}")
        print(f"   Equilibrium: {equilibrium:.5f}")
        print(f"   Distance: {abs(fvg.middle - equilibrium):.5f}")
    else:
        print(f"❌ FVG REJECTED by Premium/Discount filter")
        print(f"   Setup Direction: {latest_signal.direction.upper()}")
        print(f"   FVG Middle: {fvg.middle:.5f}")
        print(f"   Equilibrium: {equilibrium:.5f}")
        
        if latest_signal.direction == 'bearish':
            print(f"   ⚠️  BEARISH setup requires FVG ABOVE 50% (Premium)")
            print(f"   ⚠️  This FVG is BELOW 50% (Discount) - shallow retracement")
        else:
            print(f"   ⚠️  BULLISH setup requires FVG BELOW 50% (Discount)")
            print(f"   ⚠️  This FVG is ABOVE 50% (Premium) - shallow retracement")
        
        print(f"   ⚠️  This is a RETAIL INDUCEMENT zone (avoid)")
    
    print(f"\n{'='*80}")
    print(f"✅ TEST COMPLETE")
    print(f"{'='*80}\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
