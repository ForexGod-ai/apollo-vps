#!/usr/bin/env python3
"""
🔍 V4.0 Sync Verification Tool
Checks if executor can handle V4.0 scanner signals

Usage: python verify_sync.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

def verify_signal_structure():
    """Verify signals.json contains V4.0 fields"""
    signals_file = Path("signals.json")
    
    if not signals_file.exists():
        print("⚠️  signals.json not found (normal if no active signal)")
        return True
    
    try:
        with open(signals_file, 'r', encoding='utf-8') as f:
            signal = json.load(f)
        
        if not signal:
            print("✅ signals.json is empty (normal state)")
            return True
        
        print("\n📊 SIGNAL STRUCTURE ANALYSIS:")
        print("─" * 50)
        
        # V1.0 REQUIRED FIELDS
        v1_fields = [
            'SignalId', 'Symbol', 'Direction', 'StrategyType',
            'EntryPrice', 'StopLoss', 'TakeProfit',
            'StopLossPips', 'TakeProfitPips', 'RiskReward', 'Timestamp'
        ]
        
        # V4.0 NEW FIELDS (should be added)
        v4_fields = [
            'LiquiditySweep', 'SweepType', 'ConfidenceBoost',
            'OrderBlockUsed', 'OrderBlockScore',
            'PremiumDiscountZone', 'DailyRangePercentage'
        ]
        
        print("\n✅ V1.0 FIELDS (Required):")
        missing_v1 = []
        for field in v1_fields:
            if field in signal:
                print(f"   ✓ {field}: {signal[field]}")
            else:
                print(f"   ❌ {field}: MISSING")
                missing_v1.append(field)
        
        print("\n📊 V4.0 FIELDS (New - should be present):")
        missing_v4 = []
        for field in v4_fields:
            if field in signal:
                print(f"   ✓ {field}: {signal[field]}")
            else:
                print(f"   ❌ {field}: NOT YET IMPLEMENTED")
                missing_v4.append(field)
        
        print("\n" + "─" * 50)
        
        if missing_v1:
            print(f"\n❌ CRITICAL: {len(missing_v1)} V1.0 fields missing!")
            print(f"   Executor will fail to deserialize signal")
            return False
        
        if missing_v4:
            print(f"\n⚠️  WARNING: {len(missing_v4)} V4.0 fields missing")
            print(f"   Executor works but loses scanner intelligence")
            print(f"   🔴 SYNC GAP: ~35% (see EXECUTION_SYNC_AUDIT.md)")
        else:
            print(f"\n✅ EXCELLENT: Full V4.0 synchronization!")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: signals.json is malformed: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def check_executor_availability():
    """Check if C# executor files exist"""
    print("\n🤖 EXECUTOR AVAILABILITY:")
    print("─" * 50)
    
    executor_file = Path("PythonSignalExecutor.cs")
    if executor_file.exists():
        print(f"✅ {executor_file.name} found")
        
        # Check for V4.0 field definitions
        with open(executor_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'LiquiditySweep' in content:
            print("   ✅ V4.0 fields implemented in TradeSignal class")
        else:
            print("   ⚠️  V4.0 fields NOT YET added to TradeSignal class")
            print("   📋 Action: Follow Task 1 in EXECUTION_SYNC_AUDIT.md")
    else:
        print(f"❌ {executor_file.name} not found")
        print("   Make sure you're running from project root")
    
    return executor_file.exists()


def check_monitoring_setups():
    """Check if monitoring setups have invalidation support"""
    print("\n📂 MONITORING SETUPS:")
    print("─" * 50)
    
    monitoring_file = Path("monitoring_setups.json")
    
    if not monitoring_file.exists():
        print("⚠️  monitoring_setups.json not found")
        return True
    
    try:
        with open(monitoring_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        setups = data.get('setups', [])
        print(f"📊 Active setups: {len(setups)}")
        
        if setups:
            print("\n🔍 Setup statuses:")
            for setup in setups[:5]:  # Show first 5
                symbol = setup.get('symbol', 'UNKNOWN')
                status = setup.get('status', 'UNKNOWN')
                direction = setup.get('direction', '?')
                
                status_icon = {
                    'MONITORING': '👀',
                    'READY': '✅',
                    'EXPIRED': '⏰',
                    'INVALIDATED': '🚫'
                }.get(status, '❓')
                
                print(f"   {status_icon} {symbol} {direction.upper()}: {status}")
            
            if len(setups) > 5:
                print(f"   ... and {len(setups) - 5} more")
        
        # Check for invalidation logic
        print("\n🔍 INVALIDATION SUPPORT:")
        invalidated_count = sum(1 for s in setups if s.get('status') == 'INVALIDATED')
        
        if invalidated_count > 0:
            print(f"   ✅ Invalidation logic active ({invalidated_count} invalidated)")
        else:
            print(f"   ⚠️  No invalidated setups found")
            print(f"   📋 Action: Implement validate_existing_setups() (Task 4)")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR reading monitoring_setups.json: {e}")
        return False


def main():
    print("╔═══════════════════════════════════════════════════╗")
    print("║                                                   ║")
    print("║     🔍 V4.0 SYNC VERIFICATION TOOL               ║")
    print("║     Glitch in Matrix by ФорексГод                ║")
    print("║                                                   ║")
    print("╚═══════════════════════════════════════════════════╝")
    print()
    
    # Run checks
    signal_ok = verify_signal_structure()
    executor_ok = check_executor_availability()
    monitoring_ok = check_monitoring_setups()
    
    # Final verdict
    print("\n" + "═" * 50)
    print("\n🎯 FINAL VERDICT:")
    print("─" * 50)
    
    if signal_ok and executor_ok and monitoring_ok:
        print("✅ Core systems operational")
        print("\n⚠️  ACTION REQUIRED:")
        print("   1. Add V4.0 fields to PythonSignalExecutor.cs (Task 1)")
        print("   2. Update ctrader_executor.py to populate V4.0 fields (Task 2)")
        print("   3. Implement setup invalidation logic (Task 4)")
        print("\n📋 Full details: EXECUTION_SYNC_AUDIT.md")
    else:
        print("❌ Critical issues detected")
        print("\n📋 See EXECUTION_SYNC_AUDIT.md for detailed fixes")
    
    print("\n" + "═" * 50)
    
    return 0 if (signal_ok and executor_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
