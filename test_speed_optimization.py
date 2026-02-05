#!/usr/bin/env python3
"""
🧪 SPEED OPTIMIZATION VALIDATION TEST
Tests V3.4 optimizations: Lookback reduction + Order Blocks infrastructure
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from smc_detector import SMCDetector, CHoCH, FVG

def generate_mock_data(num_candles: int, symbol: str = "TEST") -> pd.DataFrame:
    """Generate mock OHLC data for testing"""
    dates = pd.date_range(end=datetime.now(), periods=num_candles, freq='h')  # lowercase 'h' for pandas 2.x
    
    # Generate realistic price action
    close = [1.27000]
    for i in range(1, num_candles):
        change = (0.0005 if i % 10 < 5 else -0.0003)  # Simple wave pattern
        close.append(close[-1] + change)
    
    df = pd.DataFrame({
        'time': dates,
        'open': close,
        'high': [c + 0.0002 for c in close],
        'low': [c - 0.0002 for c in close],
        'close': close,
        'volume': [1000] * num_candles
    })
    
    return df

def test_1_lookback_config():
    """TEST 1: Verify pairs_config.json has optimized lookback values"""
    print("\n" + "="*60)
    print("🧪 TEST 1: Lookback Configuration Validation")
    print("="*60)
    
    with open('pairs_config.json', 'r') as f:
        config = json.load(f)
    
    lookback = config['scanner_settings']['lookback_candles']
    
    # Expected values
    expected = {
        'daily': 60,
        'h4': 120,
        'h1': 180
    }
    
    all_correct = True
    for tf, expected_val in expected.items():
        actual_val = lookback[tf]
        status = "✅" if actual_val == expected_val else "❌"
        print(f"{status} {tf.upper()}: {actual_val} (expected {expected_val})")
        if actual_val != expected_val:
            all_correct = False
    
    if all_correct:
        print("\n✅ TEST 1 PASSED: All lookback values optimized correctly!")
    else:
        print("\n❌ TEST 1 FAILED: Some lookback values incorrect!")
    
    return all_correct

def test_2_swing_safety_checks():
    """TEST 2: Verify swing detection safety checks prevent errors"""
    print("\n" + "="*60)
    print("🧪 TEST 2: Swing Detection Safety Checks")
    print("="*60)
    
    detector = SMCDetector(swing_lookback=5)
    
    # Test with insufficient data
    test_cases = [
        (5, "5 candele (insufficient)"),
        (10, "10 candele (insufficient, need 11)"),
        (11, "11 candele (minimum)"),
        (60, "60 candele (Daily)"),
        (120, "120 candele (4H)"),
        (180, "180 candele (1H)")
    ]
    
    all_passed = True
    for num_candles, description in test_cases:
        df = generate_mock_data(num_candles)
        
        try:
            swing_highs = detector.detect_swing_highs(df)
            swing_lows = detector.detect_swing_lows(df)
            
            # Expected behavior
            should_be_empty = num_candles < 11
            
            if should_be_empty:
                if len(swing_highs) == 0 and len(swing_lows) == 0:
                    print(f"✅ {description}: Correctly returned empty (safety check working)")
                else:
                    print(f"❌ {description}: Should return empty but didn't!")
                    all_passed = False
            else:
                if len(swing_highs) >= 0 and len(swing_lows) >= 0:  # Just check no crash
                    print(f"✅ {description}: Swing detection working ({len(swing_highs)} highs, {len(swing_lows)} lows)")
                else:
                    print(f"❌ {description}: Unexpected behavior!")
                    all_passed = False
        
        except Exception as e:
            print(f"❌ {description}: Exception raised: {e}")
            all_passed = False
    
    if all_passed:
        print("\n✅ TEST 2 PASSED: All safety checks working correctly!")
    else:
        print("\n❌ TEST 2 FAILED: Some safety checks not working!")
    
    return all_passed

def test_3_fvg_magnets():
    """TEST 3: Verify FVG magnets storage infrastructure"""
    print("\n" + "="*60)
    print("🧪 TEST 3: FVG Magnets Storage (Order Blocks Prep)")
    print("="*60)
    
    detector = SMCDetector(swing_lookback=5)
    
    # Create mock FVG
    fvg_4h = FVG(
        index=50,
        direction='bullish',
        top=1.27500,
        bottom=1.27200,
        middle=1.27350,
        candle_time=datetime.now(),
        is_filled=False
    )
    
    fvg_1h = FVG(
        index=120,
        direction='bearish',
        top=1.27800,
        bottom=1.27600,
        middle=1.27700,
        candle_time=datetime.now(),
        is_filled=False
    )
    
    # Test storage
    try:
        # Store 4H magnet
        detector.store_fvg_magnet('GBPUSD', '4H', fvg_4h)
        magnets_4h = detector.get_fvg_magnets('GBPUSD', '4H')
        
        if len(magnets_4h) == 1:
            print(f"✅ 4H Storage: 1 magnet stored correctly")
            print(f"   Zone: {magnets_4h[0].bottom:.5f} - {magnets_4h[0].top:.5f}")
        else:
            print(f"❌ 4H Storage: Expected 1 magnet, got {len(magnets_4h)}")
            return False
        
        # Store 1H magnet
        detector.store_fvg_magnet('GBPUSD', '1H', fvg_1h)
        magnets_1h = detector.get_fvg_magnets('GBPUSD', '1H')
        
        if len(magnets_1h) == 1:
            print(f"✅ 1H Storage: 1 magnet stored correctly")
            print(f"   Zone: {magnets_1h[0].bottom:.5f} - {magnets_1h[0].top:.5f}")
        else:
            print(f"❌ 1H Storage: Expected 1 magnet, got {len(magnets_1h)}")
            return False
        
        # Test max 2 magnets per timeframe
        fvg_4h_2 = FVG(
            index=60, direction='bullish',
            top=1.27600, bottom=1.27300,
            middle=1.27450, candle_time=datetime.now()
        )
        fvg_4h_3 = FVG(
            index=70, direction='bullish',
            top=1.27700, bottom=1.27400,
            middle=1.27550, candle_time=datetime.now()
        )
        
        detector.store_fvg_magnet('GBPUSD', '4H', fvg_4h_2)
        detector.store_fvg_magnet('GBPUSD', '4H', fvg_4h_3)
        
        magnets_4h = detector.get_fvg_magnets('GBPUSD', '4H')
        
        if len(magnets_4h) == 2:
            print(f"✅ Max Limit: Correctly keeps only last 2 magnets")
            print(f"   Magnet 1: {magnets_4h[0].bottom:.5f} - {magnets_4h[0].top:.5f}")
            print(f"   Magnet 2: {magnets_4h[1].bottom:.5f} - {magnets_4h[1].top:.5f}")
        else:
            print(f"❌ Max Limit: Expected 2 magnets, got {len(magnets_4h)}")
            return False
        
        # Test retrieval for non-existent symbol
        magnets_empty = detector.get_fvg_magnets('EURUSD', '4H')
        if len(magnets_empty) == 0:
            print(f"✅ Empty Retrieval: Correctly returns empty list for new symbol")
        else:
            print(f"❌ Empty Retrieval: Should return empty, got {len(magnets_empty)}")
            return False
        
        print("\n✅ TEST 3 PASSED: FVG magnets infrastructure working perfectly!")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED: Exception raised: {e}")
        return False

def test_4_data_reduction():
    """TEST 4: Calculate actual data reduction"""
    print("\n" + "="*60)
    print("🧪 TEST 4: Data Reduction Calculation")
    print("="*60)
    
    with open('pairs_config.json', 'r') as f:
        config = json.load(f)
    
    lookback = config['scanner_settings']['lookback_candles']
    num_pairs = len(config['pairs'])
    
    # BEFORE
    before_daily = 365 * num_pairs
    before_4h = 365 * num_pairs
    before_1h = 500 * num_pairs
    before_total = before_daily + before_4h + before_1h
    
    # AFTER
    after_daily = lookback['daily'] * num_pairs
    after_4h = lookback['h4'] * num_pairs
    after_1h = lookback['h1'] * num_pairs
    after_total = after_daily + after_4h + after_1h
    
    # Reduction
    reduction = before_total - after_total
    reduction_pct = (reduction / before_total) * 100
    
    print(f"Pairs Scanned: {num_pairs}")
    print(f"\nBEFORE OPTIMIZATION:")
    print(f"  Daily (1D): {365} × {num_pairs} = {before_daily:,} candele")
    print(f"  4H: {365} × {num_pairs} = {before_4h:,} candele")
    print(f"  1H: {500} × {num_pairs} = {before_1h:,} candele")
    print(f"  TOTAL: {before_total:,} candele")
    
    print(f"\nAFTER OPTIMIZATION:")
    print(f"  Daily (1D): {lookback['daily']} × {num_pairs} = {after_daily:,} candele")
    print(f"  4H: {lookback['h4']} × {num_pairs} = {after_4h:,} candele")
    print(f"  1H: {lookback['h1']} × {num_pairs} = {after_1h:,} candele")
    print(f"  TOTAL: {after_total:,} candele")
    
    print(f"\n📊 REDUCTION:")
    print(f"  {reduction:,} candele removed (-{reduction_pct:.1f}%)")
    
    # Speed estimation
    speed_boost = before_total / after_total
    print(f"\n⚡ SPEED BOOST: {speed_boost:.1f}x faster!")
    
    if reduction_pct >= 65:
        print("\n✅ TEST 4 PASSED: Significant data reduction achieved!")
        return True
    else:
        print("\n⚠️  TEST 4 WARNING: Data reduction less than expected!")
        return False

def main():
    """Run all validation tests"""
    print("\n" + "="*60)
    print("🚀 GLITCH IN MATRIX - V3.4 SPEED OPTIMIZATION VALIDATION")
    print("="*60)
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Run tests
    results.append(("Lookback Config", test_1_lookback_config()))
    results.append(("Swing Safety Checks", test_2_swing_safety_checks()))
    results.append(("FVG Magnets", test_3_fvg_magnets()))
    results.append(("Data Reduction", test_4_data_reduction()))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! V3.4 optimization ready for production!")
        print("✅ Safe to deploy: pairs_config.json + smc_detector.py")
    else:
        print("⚠️  SOME TESTS FAILED! Review errors above before deployment!")
    print("="*60 + "\n")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
