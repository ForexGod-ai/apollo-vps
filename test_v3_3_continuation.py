#!/usr/bin/env python3
"""
Test V3.3 Continuation Momentum Logic
Simulates a setup that's been waiting for 6+ hours to trigger continuation check
"""
import json
from datetime import datetime, timedelta

def test_continuation_trigger():
    """
    Modify USDCHF setup to have 6+ hour old CHoCH timestamp
    This will trigger continuation momentum check on next executor cycle
    """
    
    with open('monitoring_setups.json', 'r') as f:
        data = json.load(f)
    
    if not data['setups']:
        print("❌ No setups to test. Run daily_scanner.py first.")
        return
    
    print("🧪 V3.3 CONTINUATION TEST")
    print("="*60)
    
    # Find USDCHF or first setup
    test_setup = None
    for setup in data['setups']:
        if setup['symbol'] == 'USDCHF':
            test_setup = setup
            break
    
    if not test_setup:
        test_setup = data['setups'][0]
    
    symbol = test_setup['symbol']
    print(f"\n📊 Testing on: {symbol}")
    print(f"   Direction: {test_setup['direction']}")
    print(f"   Entry: {test_setup['entry_price']}")
    
    # Check current state
    choch_detected = test_setup.get('choch_1h_detected', False)
    if not choch_detected:
        print(f"\n⚠️  {symbol} doesn't have CHoCH detected yet")
        print("   Continuation logic only triggers AFTER CHoCH detected")
        return
    
    current_timestamp = test_setup.get('choch_1h_timestamp')
    print(f"\n📅 Current CHoCH timestamp: {current_timestamp}")
    
    # Simulate 6+ hours ago
    six_hours_ago = (datetime.now() - timedelta(hours=7)).isoformat()
    
    print(f"\n🔧 SIMULATING 7-hour old CHoCH...")
    print(f"   Old timestamp: {current_timestamp}")
    print(f"   New timestamp: {six_hours_ago}")
    
    # Update timestamp
    test_setup['choch_1h_timestamp'] = six_hours_ago
    
    # Save
    with open('monitoring_setups.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✅ Setup modified!")
    print(f"\n📋 NEXT STEPS:")
    print(f"   1. Wait for next executor cycle (30 seconds)")
    print(f"   2. Watch logs for continuation momentum check:")
    print(f"      tail -f setup_executor.log | grep -E '(momentum|Continuation|EXECUTE)'")
    print(f"\n🎯 EXPECTED BEHAVIOR:")
    print(f"   - If price shows 3+ consecutive candles in trend direction")
    print(f"   - AND momentum score ≥ 60")
    print(f"   - THEN: 🚀 EXECUTE_ENTRY1_CONTINUATION")
    print(f"   - ELSE: ⏳ Keep waiting for pullback")
    print(f"\n⏱️  Timeout will occur at 12 hours (5 more hours from now)")

if __name__ == '__main__':
    test_continuation_trigger()
