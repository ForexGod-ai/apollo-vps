"""
Quick summary of found setups
"""
import MetaTrader5 as mt5
from daily_scanner import scan_all_pairs

# Initialize MT5
if not mt5.initialize():
    print("MT5 initialization failed")
    exit()

print(f"✅ MT5 Connected")

print("\n" + "="*60)
print("🔍 Scanning all pairs for setups...")
print("="*60)

setups = scan_all_pairs()

print("\n" + "="*60)
print(f"✅ FOUND {len(setups)} SETUPS:")
print("="*60)

for i, setup in enumerate(setups, 1):
    status_icon = "🟢" if setup.status == "READY" else "🟡"
    print(f"\n{i}. {status_icon} {setup.symbol} {setup.direction.upper()}")
    print(f"   Entry: {setup.entry_price:.5f}")
    print(f"   SL: {setup.stop_loss:.5f}")
    print(f"   TP: {setup.take_profit:.5f}")
    print(f"   R:R: 1:{setup.risk_reward_ratio:.2f}")
    print(f"   Status: {setup.status}")
    print(f"   Daily CHoCH: {setup.daily_choch.direction.upper()} @ {setup.daily_choch.break_price}")

mt5.shutdown()
print("\n🔌 MT5 disconnected")
