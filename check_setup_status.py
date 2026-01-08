"""
Quick check: Why are setups still in MONITORING?
"""
from smc_detector import SMCDetector
from ctrader_cbot_client import CTraderCBotClient

# Initialize
client = CTraderCBotClient()
detector = SMCDetector()

# Test USDCHF (should be in MONITORING)
symbol = "USDCHF"
print(f"\n{'='*60}")
print(f"Checking {symbol} Setup Status (V3.0 Requirements)")
print(f"{'='*60}\n")

df_daily = client.get_historical_data(symbol, "D1", 365)
df_4h = client.get_historical_data(symbol, "H4", 250)

setup = detector.scan_for_setup(
    symbol=symbol,
    df_daily=df_daily,
    df_4h=df_4h,
    priority=1
)

if setup:
    print(f"\n{'='*60}")
    print(f"SETUP STATUS: {setup.status}")
    print(f"{'='*60}")
    print(f"Symbol: {setup.symbol}")
    print(f"Direction: {setup.daily_choch.direction.upper()}")
    print(f"Strategy: {setup.strategy_type.upper()}")
    print(f"Entry: {setup.entry_price:.5f}")
    print(f"Stop Loss: {setup.stop_loss:.5f}")
    print(f"Take Profit: {setup.take_profit:.5f}")
    print(f"Status: {setup.status}")
    
    # Get current price
    current_price = df_4h['close'].iloc[-1]
    fvg = setup.fvg
    price_in_fvg = fvg.bottom <= current_price <= fvg.top
    
    print(f"\n📊 CURRENT STATUS:")
    print(f"  Current Price: {current_price:.5f}")
    print(f"  FVG Zone: {fvg.bottom:.5f} - {fvg.top:.5f}")
    print(f"  Price in FVG: {'✅ YES' if price_in_fvg else '❌ NO'}")
    
    # Check 4H CHoCH
    has_4h_choch = setup.h4_choch is not None
    print(f"  4H CHoCH: {'✅ YES' if has_4h_choch else '❌ NO'}")
    if has_4h_choch:
        print(f"    Direction: {setup.h4_choch.direction.upper()}")
        print(f"    Break Price: {setup.h4_choch.break_price:.5f}")
    
    print(f"\n🎯 TO BECOME READY:")
    if not has_4h_choch:
        print(f"  ⏳ Waiting for 4H CHoCH ({setup.daily_choch.direction.upper()} direction)")
    if not price_in_fvg:
        print(f"  ⏳ Waiting for price to enter FVG zone")
    if setup.strategy_type == 'continuation':
        print(f"  ⏳ Need BOS confirmation in last 90 Daily candles")
    
    if has_4h_choch and price_in_fvg:
        print(f"  ✅ All conditions met! Should be READY")
        print(f"  ⚠️ Check why status is still MONITORING (BOS filter? GBP filter?)")
else:
    print(f"\n❌ No setup detected for {symbol}")
