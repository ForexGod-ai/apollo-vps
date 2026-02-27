#!/usr/bin/env python3
"""
🧪 V8.1 PREMIUM/DISCOUNT OVERLAP TEST - EURJPY
Test nou validate_fvg_zone cu SMC Zone Overlap + Toleranță ±2%
"""

import sys
sys.path.append('.')

from smc_detector import SMCDetector
from ctrader_cbot_client import CTraderCBotClient
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="ERROR")  # Only errors

def test_eurjpy_v8_1():
    """Test EURJPY cu noua logică V8.1 (Overlap + Tolerance)"""
    
    print("="*80)
    print("🧪 V8.1 PREMIUM/DISCOUNT OVERLAP TEST")
    print("="*80)
    print()
    
    # Fetch data
    client = CTraderCBotClient()
    print("📊 Fetching EURJPY data...")
    df_daily = client.get_historical_data('EURJPY', 'D1', 100)
    current_price = df_daily['close'].iloc[-1]
    print(f"✅ Got {len(df_daily)} Daily bars")
    print(f"   Current Price: {current_price:.5f}")
    print()
    
    # Initialize detector
    detector = SMCDetector(swing_lookback=5, atr_multiplier=1.5)
    print("✅ SMC Detector V8.1 initialized")
    print()
    
    # Step 1: ATR Filter
    print("─"*80)
    print("STEP 1: ATR PROMINENCE FILTER")
    print("─"*80)
    swing_highs = detector.detect_swing_highs(df_daily)
    swing_lows = detector.detect_swing_lows(df_daily)
    print(f"✅ Swing Highs: {len(swing_highs)} detected")
    print(f"✅ Swing Lows: {len(swing_lows)} detected")
    print()
    
    # Step 2: CHoCH
    print("─"*80)
    print("STEP 2: CHoCH DETECTION")
    print("─"*80)
    chochs, bos = detector.detect_choch_and_bos(df_daily)
    print(f"✅ CHoCH: {len(chochs)} detected")
    if chochs:
        latest_choch = chochs[-1]
        print(f"   Latest: {latest_choch.direction.upper()} @ {latest_choch.break_price:.5f}")
    print()
    
    # Step 3: FVG
    print("─"*80)
    print("STEP 3: FVG DETECTION")
    print("─"*80)
    if chochs:
        fvg = detector.detect_fvg(df_daily, chochs[-1], current_price)
        if fvg:
            print(f"✅ FVG Detected:")
            print(f"   Direction: {fvg.direction.upper()}")
            print(f"   Zone: {fvg.bottom:.5f} - {fvg.top:.5f}")
            print(f"   Middle: {fvg.middle:.5f}")
            print()
            
            # Step 4: Premium/Discount V8.1
            print("─"*80)
            print("STEP 4: PREMIUM/DISCOUNT V8.1 (OVERLAP + TOLERANCE)")
            print("─"*80)
            
            equilibrium = detector.calculate_equilibrium(df_daily, swing_highs, swing_lows)
            if equilibrium:
                print(f"Equilibrium (50%): {equilibrium:.5f}")
                print()
                
                # Call validate_fvg_zone with debug=True
                is_valid = detector.validate_fvg_zone(
                    fvg, 
                    equilibrium, 
                    latest_choch.direction, 
                    debug=True
                )
                
                print()
                print("="*80)
                if is_valid:
                    print("✅ EURJPY V8.1 TEST: PASSED")
                    print("   FVG intersects with 50% equilibrium (Overlap logic works!)")
                else:
                    print("❌ EURJPY V8.1 TEST: FAILED")
                    print("   FVG still rejected despite new logic")
                print("="*80)
            else:
                print("❌ No equilibrium level calculated")
        else:
            print("❌ No FVG detected")
    else:
        print("❌ No CHoCH detected")

if __name__ == '__main__':
    test_eurjpy_v8_1()
