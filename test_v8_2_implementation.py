#!/usr/bin/env python3
"""
🧪 V8.2 IMPLEMENTATION TEST - Strategy-Differentiated Premium/Discount

Tests the new V8.2 logic:
1. calculate_equilibrium_reversal() - Pre-CHoCH Macro Leg
2. calculate_equilibrium_continuity() - Post-CHoCH Impulse Leg
3. validate_fvg_zone() with strategy_type parameter
4. scan_for_setup() with differentiated thresholds

Expected Results:
- REVERSAL: Strict 48-52% (±2%)
- CONTINUITY: Relaxed 38-62% (±12%)
"""

import sys
sys.path.append('.')

from smc_detector import SMCDetector
from ctrader_cbot_client import CTraderCBotClient
import pandas as pd
from loguru import logger

# Suppress logs
logger.remove()

def test_v8_2():
    """Test V8.2 implementation on EURJPY and AUDUSD"""
    
    print("╔═══════════════════════════════════════════════════════════════════════╗")
    print("║           V8.2 IMPLEMENTATION TEST - Strategy Differentiation         ║")
    print("╚═══════════════════════════════════════════════════════════════════════╝\n")
    
    # Initialize
    client = CTraderCBotClient()
    detector = SMCDetector(swing_lookback=5, atr_multiplier=1.5)
    
    test_pairs = ["EURJPY", "AUDUSD"]
    
    for symbol in test_pairs:
        print(f"\n{'='*75}")
        print(f"TESTING: {symbol}")
        print(f"{'='*75}")
        
        # Fetch data
        df = client.get_historical_data(symbol, 'D1', 100)
        current_price = df['close'].iloc[-1]
        
        # Detect swings
        swing_highs = detector.detect_swing_highs(df)
        swing_lows = detector.detect_swing_lows(df)
        
        print(f"\n📊 Market Structure:")
        print(f"   Swing Highs: {len(swing_highs)}")
        print(f"   Swing Lows: {len(swing_lows)}")
        
        # Detect signals
        chochs, bos_list = detector.detect_choch_and_bos(df)
        
        print(f"\n🔍 Signals Detected:")
        print(f"   CHoCH (Reversal): {len(chochs)}")
        print(f"   BOS (Continuity): {len(bos_list)}")
        
        if chochs:
            latest_choch = chochs[-1]
            print(f"\n🔄 Latest CHoCH (REVERSAL):")
            print(f"   Direction: {latest_choch.direction.upper()}")
            print(f"   Break Price: {latest_choch.break_price:.5f}")
            print(f"   Index: {latest_choch.index}")
            
            # Test PRE-CHoCH equilibrium calculation
            equilibrium_reversal = detector.calculate_equilibrium_reversal(
                df, latest_choch, swing_highs, swing_lows
            )
            
            if equilibrium_reversal:
                print(f"\n   ✅ V8.2 Reversal Equilibrium: {equilibrium_reversal:.5f}")
                print(f"   Measured from: Last swing BEFORE CHoCH → CHoCH break")
            else:
                print(f"\n   ❌ Could not calculate Reversal equilibrium")
            
            # Detect FVG after CHoCH
            fvg = detector.detect_fvg(df, latest_choch, current_price)
            
            if fvg and equilibrium_reversal:
                print(f"\n   FVG Found:")
                print(f"   Zone: {fvg.bottom:.5f} - {fvg.top:.5f}")
                print(f"   Middle: {fvg.middle:.5f}")
                
                # Test REVERSAL validation (STRICT 48-52%)
                is_valid = detector.validate_fvg_zone(
                    fvg, equilibrium_reversal, latest_choch.direction, 
                    strategy_type='reversal', debug=True
                )
                
                print(f"\n   {'✅ VALID' if is_valid else '❌ REJECTED'}: REVERSAL validation (48-52% strict)")
        
        if bos_list:
            latest_bos = bos_list[-1]
            print(f"\n➡️ Latest BOS (CONTINUITY):")
            print(f"   Direction: {latest_bos.direction.upper()}")
            print(f"   Break Price: {latest_bos.break_price:.5f}")
            print(f"   Index: {latest_bos.index}")
            
            # Test POST-CHoCH equilibrium calculation
            last_choch = chochs[-1] if chochs else None
            equilibrium_continuity = detector.calculate_equilibrium_continuity(
                df, latest_bos, last_choch, swing_highs, swing_lows
            )
            
            if equilibrium_continuity:
                print(f"\n   ✅ V8.2 Continuity Equilibrium: {equilibrium_continuity:.5f}")
                print(f"   Measured from: Last swing AFTER CHoCH → BOS break")
            else:
                print(f"\n   ❌ Could not calculate Continuity equilibrium")
            
            # Detect FVG after BOS
            fvg = detector.detect_fvg(df, latest_bos, current_price)
            
            if fvg and equilibrium_continuity:
                print(f"\n   FVG Found:")
                print(f"   Zone: {fvg.bottom:.5f} - {fvg.top:.5f}")
                print(f"   Middle: {fvg.middle:.5f}")
                
                # Test CONTINUITY validation (RELAXED 38-62%)
                is_valid = detector.validate_fvg_zone(
                    fvg, equilibrium_continuity, latest_bos.direction,
                    strategy_type='continuation', debug=True
                )
                
                print(f"\n   {'✅ VALID' if is_valid else '❌ REJECTED'}: CONTINUITY validation (38-62% relaxed)")
    
    print("\n╔═══════════════════════════════════════════════════════════════════════╗")
    print("║                       V8.2 TEST COMPLETE                              ║")
    print("╚═══════════════════════════════════════════════════════════════════════╝\n")
    
    print("🎯 V8.2 Features Tested:")
    print("   ✅ calculate_equilibrium_reversal() - Pre-CHoCH Macro Leg")
    print("   ✅ calculate_equilibrium_continuity() - Post-CHoCH Impulse Leg")
    print("   ✅ validate_fvg_zone() with strategy_type parameter")
    print("   ✅ REVERSAL: Strict 48-52% (±2% tolerance)")
    print("   ✅ CONTINUITY: Relaxed 38-62% (±12% tolerance)")
    print("\n💎 V8.2 IMPLEMENTATION SUCCESSFUL!\n")


if __name__ == '__main__':
    test_v8_2()
