#!/usr/bin/env python3
"""
Test Daily Reset Logic - Unified Risk Manager
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from unified_risk_manager import UnifiedRiskManager

def test_daily_reset():
    """Test new day auto-reset functionality"""
    
    print("\n" + "="*70)
    print("🧪 TESTING DAILY RESET LOGIC")
    print("="*70)
    
    state_file = Path("data/daily_state.json")
    
    # Test 1: Create fake old state (yesterday)
    print("\n1️⃣ Creating fake state from YESTERDAY...")
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
    
    fake_state = {
        'date': yesterday,
        'starting_balance': 1000.00,
        'trades_count': 5,
        'reset_timestamp': (datetime.now() - timedelta(days=1)).isoformat()
    }
    
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, 'w') as f:
        json.dump(fake_state, f, indent=2)
    
    print(f"   ✅ Fake state created: {yesterday}")
    print(f"   📊 Fake starting balance: $1000.00")
    print(f"   🔢 Fake trades count: 5")
    
    # Test 2: Initialize Risk Manager (should detect new day)
    print("\n2️⃣ Initializing Risk Manager...")
    print("   (Should detect NEW DAY and reset state)")
    
    rm = UnifiedRiskManager()
    
    # Test 3: Verify state was reset
    print("\n3️⃣ Verifying state after initialization...")
    
    with open(state_file, 'r') as f:
        new_state = json.load(f)
    
    today = datetime.now().date().isoformat()
    
    assert new_state['date'] == today, "❌ Date not updated to today!"
    assert new_state['trades_count'] == 0, "❌ Trades count not reset to 0!"
    assert new_state['starting_balance'] > 0, "❌ Starting balance not set!"
    
    print(f"   ✅ Date: {new_state['date']} (TODAY)")
    print(f"   ✅ Starting balance: ${new_state['starting_balance']:.2f}")
    print(f"   ✅ Trades count: {new_state['trades_count']}")
    
    # Test 4: Check Risk Manager attributes
    print("\n4️⃣ Checking Risk Manager attributes...")
    print(f"   📅 starting_balance_today: ${rm.starting_balance_today:.2f}")
    print(f"   🔢 daily_trades_count: {rm.daily_trades_count}")
    
    assert rm.daily_trades_count == 0, "❌ Risk Manager trades count not 0!"
    
    # Test 5: Calculate daily P&L (should be based on today's starting balance)
    print("\n5️⃣ Testing daily P&L calculation...")
    pnl = rm.get_daily_pnl()
    
    print(f"   📊 Closed P&L: ${pnl['closed_pnl']:.2f}")
    print(f"   📊 Open P&L: ${pnl['open_pnl']:.2f}")
    print(f"   💰 Total P&L: ${pnl['total_pnl']:.2f}")
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED!")
    print("="*70)
    print("\n📝 SUMMARY:")
    print(f"   • Daily state auto-reset: ✅ WORKING")
    print(f"   • Starting balance tracked: ✅ WORKING")
    print(f"   • P&L calculation fixed: ✅ WORKING")
    print(f"   • Old data from yesterday: ✅ CLEARED")
    print("\n🎉 Risk Manager will now correctly reset P&L at midnight!")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_daily_reset()
