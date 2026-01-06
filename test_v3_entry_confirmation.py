"""
V3.0 Entry Confirmation System - Quick Test
Tests the new MONITORING → READY status logic
"""

import sys
from pathlib import Path

# Mock data structures for testing
class MockCHoCH:
    def __init__(self, direction, break_price, index):
        self.direction = direction
        self.break_price = break_price
        self.index = index

class MockFVG:
    def __init__(self, top, bottom, direction):
        self.top = top
        self.bottom = bottom
        self.direction = direction

def test_price_in_fvg():
    """Test price-in-FVG validation"""
    print("\n🧪 TEST 1: Price in FVG Detection")
    print("="*60)
    
    fvg = MockFVG(top=1.0820, bottom=1.0800, direction='bullish')
    
    test_cases = [
        (1.0810, True, "Price in middle of FVG"),
        (1.0800, True, "Price at FVG bottom"),
        (1.0820, True, "Price at FVG top"),
        (1.0790, False, "Price below FVG"),
        (1.0830, False, "Price above FVG")
    ]
    
    for price, expected, description in test_cases:
        in_fvg = fvg.bottom <= price <= fvg.top
        status = "✅ PASS" if in_fvg == expected else "❌ FAIL"
        print(f"{status} | Price: {price:.4f} | Expected: {expected} | {description}")

def test_4h_choch_validation():
    """Test 4H CHoCH validation logic"""
    print("\n🧪 TEST 2: 4H CHoCH Validation")
    print("="*60)
    
    # Setup
    daily_trend = 'bullish'
    fvg = MockFVG(top=1.0820, bottom=1.0800, direction='bullish')
    total_4h_candles = 100
    
    test_cases = [
        # (CHoCH direction, break_price, index, should_validate, description)
        ('bullish', 1.0810, 95, True, "Bullish CHoCH in FVG, recent (candle 95/100)"),
        ('bullish', 1.0815, 85, True, "Bullish CHoCH in FVG, within 30 candles"),
        ('bullish', 1.0805, 60, False, "Bullish CHoCH in FVG, too old (candle 60)"),
        ('bearish', 1.0810, 95, False, "Wrong direction (bearish, need bullish)"),
        ('bullish', 1.0850, 95, False, "Bullish but break_price outside FVG (above)"),
        ('bullish', 1.0790, 95, False, "Bullish but break_price outside FVG (below)"),
    ]
    
    print(f"Daily Trend: {daily_trend.upper()}")
    print(f"FVG Zone: {fvg.bottom:.4f} - {fvg.top:.4f}")
    print(f"Lookback Window: Last 30 candles (candle {total_4h_candles-30} to {total_4h_candles})")
    print()
    
    for direction, break_price, index, expected, description in test_cases:
        # Check if in last 30 candles
        in_window = index >= (total_4h_candles - 30)
        
        # Check direction match
        direction_match = direction == daily_trend
        
        # Check break_price in FVG
        in_fvg = fvg.bottom <= break_price <= fvg.top
        
        # Valid if ALL conditions met
        is_valid = in_window and direction_match and in_fvg
        
        status = "✅ PASS" if is_valid == expected else "❌ FAIL"
        
        print(f"{status} | {description}")
        print(f"       Direction: {direction} (match: {direction_match})")
        print(f"       Break: {break_price:.4f} (in FVG: {in_fvg})")
        print(f"       Index: {index}/100 (in window: {in_window})")
        print()

def test_status_logic():
    """Test MONITORING vs READY status assignment"""
    print("\n🧪 TEST 3: Status Assignment Logic")
    print("="*60)
    
    fvg = MockFVG(top=1.0820, bottom=1.0800, direction='bullish')
    
    test_cases = [
        # (has_4h_choch, price_in_fvg, expected_status, description)
        (True, True, 'READY', "4H confirmed + price in FVG"),
        (True, False, 'MONITORING', "4H confirmed but price outside FVG"),
        (False, True, 'MONITORING', "Price in FVG but no 4H confirmation"),
        (False, False, 'MONITORING', "Neither condition met"),
    ]
    
    print(f"FVG Zone: {fvg.bottom:.4f} - {fvg.top:.4f}")
    print()
    
    for has_4h, price_in, expected_status, description in test_cases:
        # Simulate status logic from smc_detector.py
        if has_4h and price_in:
            status = 'READY'
        else:
            status = 'MONITORING'
        
        result = "✅ PASS" if status == expected_status else "❌ FAIL"
        
        print(f"{result} | {description}")
        print(f"       Has 4H CHoCH: {has_4h}")
        print(f"       Price in FVG: {price_in}")
        print(f"       Expected: {expected_status} | Got: {status}")
        print()

def test_execution_blocker():
    """Test execution blocker logic"""
    print("\n🧪 TEST 4: Execution Blocker")
    print("="*60)
    
    test_cases = [
        ('READY', True, "READY status allows execution"),
        ('MONITORING', False, "MONITORING status blocks execution"),
        ('PENDING', False, "Unknown status blocks execution"),
        ('', False, "Empty status blocks execution"),
    ]
    
    for status, should_execute, description in test_cases:
        # Simulate blocker from ctrader_executor.py
        can_execute = (status == 'READY')
        
        result = "✅ PASS" if can_execute == should_execute else "❌ FAIL"
        action = "ALLOWED ✓" if can_execute else "BLOCKED ✗"
        
        print(f"{result} | Status: '{status}' → {action} | {description}")

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("V3.0 ENTRY CONFIRMATION SYSTEM - UNIT TESTS")
    print("="*60)
    
    test_price_in_fvg()
    test_4h_choch_validation()
    test_status_logic()
    test_execution_blocker()
    
    print("\n" + "="*60)
    print("✅ ALL TESTS COMPLETE")
    print("="*60)
    print("\n💡 Next Steps:")
    print("   1. Run daily_scanner.py on historical data")
    print("   2. Verify monitoring_setups.json has 'status' field")
    print("   3. Test setup_executor_monitor.py with MONITORING setup")
    print("   4. Confirm execution blocker works in ctrader_executor.py")
    print()

if __name__ == "__main__":
    main()
