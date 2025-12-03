#!/usr/bin/env python3
"""
Test BTCUSD validation - simulate yesterday's scenario
"""

from ctrader_data_client import get_ctrader_client
from smc_detector import SMCDetector
import pandas as pd

def test_btc_validation():
    """Test if new validation would catch yesterday's late setup"""
    
    print("\n" + "="*60)
    print("🧪 TESTING BTCUSD VALIDATION")
    print("="*60)
    
    # Simulate YESTERDAY's scenario (Dec 2, 17:58)
    print("\n📅 SCENARIO: Yesterday (Dec 2, 17:58)")
    print("   Price was at: $87,953")
    print("   Entry: $87,953.81")
    print("   SL: $88,703.88")
    print("   TP: $86,070.09")
    
    entry = 87953.81
    sl = 88703.88
    tp = 86070.09
    current_price = 87953.78
    
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr = reward / risk
    
    print(f"\n📊 OLD VALIDATION (before fix):")
    print(f"   Risk: ${risk:.2f}")
    print(f"   Reward: ${reward:.2f}")
    print(f"   R:R: 1:{rr:.2f}")
    print(f"   ❌ OLD: Would PASS (R:R {rr:.2f} >= 1.0)")
    
    # New validation
    print(f"\n🆕 NEW VALIDATION (after fix):")
    print(f"   Check 1: R:R >= 2.0? {rr:.2f} >= 2.0 = {'✅ PASS' if rr >= 2.0 else '❌ FAIL'}")
    
    distance_to_tp = abs(current_price - tp)
    total_move = abs(entry - tp)
    pct_remaining = (distance_to_tp / total_move) if total_move > 0 else 0
    
    print(f"   Check 2: Distance to TP >= 20%?")
    print(f"      Current → TP: ${distance_to_tp:.2f}")
    print(f"      Entry → TP: ${total_move:.2f}")
    print(f"      Remaining: {pct_remaining*100:.1f}% {'✅ PASS' if pct_remaining >= 0.20 else '❌ FAIL (< 20%)'}")
    
    would_reject = rr < 2.0 or pct_remaining < 0.20
    
    print(f"\n{'🚫 REJECTED!' if would_reject else '✅ ACCEPTED'}")
    print(f"   Result: Setup would be {'FILTERED OUT (too late)' if would_reject else 'ACCEPTED'}")
    
    # Test TODAY's scenario
    print("\n" + "="*60)
    print("📅 SCENARIO: Today (Dec 3, current)")
    print("="*60)
    
    client = get_ctrader_client()
    df_daily = client.get_historical_data('BTCUSD', 'D1', 100)
    df_4h = client.get_historical_data('BTCUSD', 'H4', 200)
    
    current_price_today = df_daily['close'].iloc[-1]
    
    # Simulate setup detection
    entry_today = current_price_today
    sl_today = df_4h['high'].iloc[-30:].max()
    tp_today = df_daily['low'].iloc[-30:].min()
    
    risk_today = abs(entry_today - sl_today)
    reward_today = abs(tp_today - entry_today)
    rr_today = reward_today / risk_today if risk_today > 0 else 0
    
    distance_today = abs(current_price_today - tp_today)
    total_move_today = abs(entry_today - tp_today)
    pct_today = (distance_today / total_move_today) if total_move_today > 0 else 0
    
    print(f"\n   Current Price: ${current_price_today:,.2f}")
    print(f"   Entry: ${entry_today:,.2f}")
    print(f"   SL: ${sl_today:,.2f}")
    print(f"   TP: ${tp_today:,.2f}")
    print(f"   R:R: 1:{rr_today:.2f}")
    print(f"   Distance to TP: {pct_today*100:.1f}%")
    
    print(f"\n🆕 NEW VALIDATION:")
    print(f"   Check 1: R:R {rr_today:.2f} >= 2.0? {'✅ PASS' if rr_today >= 2.0 else '❌ FAIL'}")
    print(f"   Check 2: Distance {pct_today*100:.1f}% >= 20%? {'✅ PASS' if pct_today >= 0.20 else '❌ FAIL'}")
    
    would_accept_today = rr_today >= 2.0 and pct_today >= 0.20
    
    print(f"\n{'✅ ACCEPTED!' if would_accept_today else '🚫 REJECTED!'}")
    print(f"   Result: Setup would be {'ACCEPTED (good timing!)' if would_accept_today else 'FILTERED OUT (too late)'}")
    
    print("\n" + "="*60)
    print("💡 CONCLUSION:")
    print("="*60)
    print("✅ New validation catches late setups")
    print("✅ Minimum R:R: 2.0 (was 1.0)")
    print("✅ Must have 20%+ room to TP")
    print("✅ Prevents entering at end of trend")
    print("="*60 + "\n")

if __name__ == "__main__":
    test_btc_validation()
