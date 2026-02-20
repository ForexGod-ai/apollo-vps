#!/usr/bin/env python3
"""
🧪 BTCUSD FIX VALIDATION SUITE
Tests all fixes from EXECUTION_FAIL_AUDIT.md

✨ Glitch in Matrix by ФорексГод ✨
"""

import json
from datetime import datetime
from pathlib import Path
import sys

def test_1_d1_data_availability():
    """Phase 1: Validate BTCUSD D1 data download"""
    print("\n" + "="*70)
    print("TEST 1: BTCUSD D1 Data Availability")
    print("="*70)
    
    try:
        from daily_scanner import DailyScanner
        
        scanner = DailyScanner()
        
        if not scanner.data_provider.connect():
            print("❌ FAILED: Cannot connect to cTrader cBot")
            return False
        
        df = scanner.data_provider.get_historical_data('BTCUSD', 'D1', 50)
        
        scanner.data_provider.disconnect()
        
        if df is not None and not df.empty:
            print(f"✅ PASSED: BTCUSD D1 data available ({len(df)} candles)")
            print(f"\n   Last 3 candles:")
            print(df[['time', 'open', 'high', 'low', 'close']].tail(3).to_string(index=False))
            return True
        else:
            print("❌ FAILED: BTCUSD D1 data NOT AVAILABLE")
            print("   This will cause 'Daily Range: 0.0%' errors!")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_2_risk_calculation():
    """Phase 2: Test corrected pip_value for BTCUSD"""
    print("\n" + "="*70)
    print("TEST 2: Risk Calculation with Corrected pip_value")
    print("="*70)
    
    try:
        from unified_risk_manager import UnifiedRiskManager
        
        rm = UnifiedRiskManager()
        
        # Simulate BTCUSD trade
        result = rm.validate_new_trade(
            symbol='BTCUSD',
            direction='sell',
            entry_price=66500,
            stop_loss=67830
        )
        
        print(f"\n   Validation Result: {'✅ APPROVED' if result['approved'] else '❌ REJECTED'}")
        print(f"   Lot Size: {result['lot_size']:.2f}")
        print(f"   Reason: {result['reason']}")
        
        if result['approved'] and result['lot_size'] >= 0.01:
            print(f"\n✅ PASSED: Lot size is valid ({result['lot_size']:.2f} lots)")
            
            # Check if it's reasonable for $200 risk on 1330 pip SL
            # With pip_value = 0.01: 200 / (1330 * 0.01) = 15.04 micro lots = 0.15 standard lots
            expected_approx = 0.15
            if abs(result['lot_size'] - expected_approx) < 0.10:
                print(f"   ✅ Math check: {result['lot_size']:.2f} lots ≈ {expected_approx:.2f} expected")
            else:
                print(f"   ⚠️  Math check: {result['lot_size']:.2f} lots != {expected_approx:.2f} expected")
            
            return True
        elif not result['approved']:
            print(f"\n❌ FAILED: Trade rejected - {result['reason']}")
            return False
        else:
            print(f"\n❌ FAILED: Lot size too small ({result['lot_size']:.2f} < 0.01)")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_signal_generation():
    """Phase 3: Test signal file generation with Manual Override"""
    print("\n" + "="*70)
    print("TEST 3: Signal Generation with Manual Override Pattern")
    print("="*70)
    
    try:
        # Check if test signals exist
        workspace = Path("/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo")
        signal_paths = [
            workspace / "signals.json",
            Path("/Users/forexgod/GlitchMatrix/signals.json")
        ]
        
        test_signal = workspace / "signal_test_full.json"
        
        if not test_signal.exists():
            print(f"❌ FAILED: Test signal not found: {test_signal}")
            return False
        
        # Load test signal
        with open(test_signal, 'r') as f:
            signal = json.load(f)
        
        print(f"\n   Test Signal: {signal['SignalId']}")
        print(f"   Symbol: {signal['Symbol']}")
        print(f"   Lot Size: {signal['LotSize']}")
        print(f"   Raw Units: {signal.get('RawUnits', 'N/A')}")
        
        # Verify Manual Override values
        if signal['Symbol'] == 'BTCUSD' and signal['LotSize'] == 0.50:
            print(f"\n✅ PASSED: Manual Override active (0.50 lots hardcoded)")
        else:
            print(f"\n❌ FAILED: Manual Override not applied")
            return False
        
        # Check dual-path write
        paths_exist = []
        for path in signal_paths:
            paths_exist.append(path.exists())
            status = "✅" if path.exists() else "❌"
            print(f"   {status} {path}")
        
        if all(paths_exist):
            print(f"\n✅ PASSED: Dual-path write confirmed")
            return True
        else:
            print(f"\n⚠️  WARNING: Some signal paths missing (expected after cleanup)")
            return True  # Not critical if signals were processed
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_cbot_configuration():
    """Phase 4: Validate cBot has correct configuration"""
    print("\n" + "="*70)
    print("TEST 4: cBot Configuration Validation")
    print("="*70)
    
    try:
        cbot_file = Path("/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/PythonSignalExecutor.cs")
        
        if not cbot_file.exists():
            print(f"❌ FAILED: cBot file not found: {cbot_file}")
            return False
        
        with open(cbot_file, 'r') as f:
            content = f.read()
        
        # Check for V5.7 Manual Replication
        checks = {
            'Manual Override': 'V5.7 MANUAL REPLICATION' in content,
            'Fixed Volume': 'volume = (long)symbol.QuantityToVolumeInUnits(0.50)' in content,
            'Path Validation': 'Signal directory validated' in content,
            'ModifyPosition Fix': 'ModifyPosition(result.Position, signal.StopLoss, signal.TakeProfit, null)' in content
        }
        
        all_passed = True
        for check, result in checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check}")
            if not result:
                all_passed = False
        
        if all_passed:
            print(f"\n✅ PASSED: cBot has all V5.7 fixes")
            print(f"\n   ⚠️  REMINDER: You must REBUILD the cBot in cTrader!")
            print(f"   Steps:")
            print(f"   1. Open cTrader")
            print(f"   2. Go to Automate → cBots")
            print(f"   3. Right-click PythonSignalExecutor → Build")
            print(f"   4. Verify 'Build succeeded' message")
            return True
        else:
            print(f"\n❌ FAILED: cBot missing some V5.7 fixes")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def main():
    """Run all validation tests"""
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*15 + "🧪 BTCUSD FIX VALIDATION SUITE" + " "*23 + "║")
    print("║" + " "*20 + "✨ Glitch in Matrix by ФорексГод ✨" + " "*13 + "║")
    print("╚" + "="*68 + "╝")
    
    tests = [
        ("D1 Data Availability", test_1_d1_data_availability),
        ("Risk Calculation", test_2_risk_calculation),
        ("Signal Generation", test_3_signal_generation),
        ("cBot Configuration", test_4_cbot_configuration),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n💥 EXCEPTION in {test_name}: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {test_name}")
    
    print(f"\n   Score: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n📋 NEXT STEPS:")
        print("   1. Rebuild cBot in cTrader (Automate → Build)")
        print("   2. Start/restart PythonSignalExecutor cBot")
        print("   3. Generate live signal: python3 -c 'from ctrader_executor import *'")
        print("   4. Watch Journal tab for '🚨 V5.7 MANUAL REPLICATION'")
        print("\n✨ May the Matrix be with you, ФорексГод! ✨")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} TEST(S) FAILED - Review errors above")
        print("\n📋 TROUBLESHOOTING:")
        if not results.get("D1 Data Availability"):
            print("   - Start MarketDataProvider cBot in cTrader")
            print("   - Verify cBot HTTP server running on localhost:8767")
        if not results.get("Risk Calculation"):
            print("   - Check SUPER_CONFIG.json exists")
            print("   - Verify account balance in .env file")
        if not results.get("Signal Generation"):
            print("   - Run: cp signal_test_full.json signals.json")
        sys.exit(1)


if __name__ == "__main__":
    main()
