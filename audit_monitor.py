#!/usr/bin/env python3
"""
🔍 Monitoring Setup Audit Script V23.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Audits monitoring_setups.json to reveal WHAT the monitor is waiting for.

Purpose:
1. Decode confirmation logic (CHoCH vs Limit)
2. Check price distance to activation zone
3. Simulate monitor decision logic
4. Answer: "Would monitor trigger NOW if price was X?"

For: ФорексГод - Glitch in Matrix V3.7
Date: February 12, 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import os
from datetime import datetime
from pathlib import Path

def load_monitoring_file():
    """Load monitoring_setups.json from workspace or GlitchMatrix"""
    
    # Try workspace first
    workspace_path = Path(__file__).parent / "monitoring_setups.json"
    glitch_path = Path.home() / "GlitchMatrix" / "monitoring_setups.json"
    
    for path in [workspace_path, glitch_path]:
        if path.exists():
            print(f"📂 Reading: {path}")
            with open(path, 'r') as f:
                return json.load(f), str(path)
    
    print("❌ monitoring_setups.json NOT FOUND!")
    print(f"   Checked: {workspace_path}")
    print(f"   Checked: {glitch_path}")
    return None, None

def get_btc_price():
    """Get current BTCUSD price (fallback to manual if API fails)"""
    
    try:
        import yfinance as yf
        ticker = yf.Ticker("BTC-USD")
        data = ticker.history(period="1d")
        if not data.empty:
            price = data['Close'].iloc[-1]
            print(f"📊 Live BTCUSD Price (Yahoo): ${price:,.2f}")
            return float(price)
    except Exception as e:
        print(f"⚠️  yfinance failed: {e}")
    
    # Fallback to ccxt
    try:
        import ccxt
        exchange = ccxt.binance()
        ticker = exchange.fetch_ticker('BTC/USDT')
        price = ticker['last']
        print(f"📊 Live BTCUSD Price (Binance): ${price:,.2f}")
        return float(price)
    except Exception as e:
        print(f"⚠️  ccxt failed: {e}")
    
    # Manual fallback
    print("\n⚠️  Unable to fetch live price automatically.")
    manual_price = input("Enter current BTCUSD price (e.g., 68000): $")
    return float(manual_price)

def decode_confirmation_logic(setup):
    """Decode what the monitor is waiting for"""
    
    symbol = setup.get('symbol', 'UNKNOWN')
    direction = setup.get('direction', 'UNKNOWN')
    
    print(f"\n{'='*70}")
    print(f"🔍 SETUP AUDIT: {symbol} {direction.upper()}")
    print(f"{'='*70}\n")
    
    # 1. Display basic info
    print("📋 BASIC INFO:")
    print(f"   Symbol: {symbol}")
    print(f"   Direction: {direction}")
    print(f"   Strategy: {setup.get('strategy_type', 'N/A')}")
    print(f"   ML Score: {setup.get('ml_score', 'N/A')}")
    print(f"   AI Probability: {setup.get('ai_probability', 'N/A')}")
    
    # 2. Entry parameters
    print(f"\n💰 ENTRY PARAMETERS:")
    print(f"   Entry Price: ${setup.get('entry_price', 'N/A'):,.2f}")
    print(f"   Stop Loss: ${setup.get('stop_loss', 'N/A'):,.2f}")
    print(f"   Take Profit: ${setup.get('take_profit', 'N/A'):,.2f}")
    print(f"   SL Pips: {setup.get('stop_loss_pips', 'N/A')}")
    print(f"   TP Pips: {setup.get('take_profit_pips', 'N/A')}")
    print(f"   Risk/Reward: {setup.get('risk_reward', 'N/A')}")
    
    # 3. CRITICAL: Confirmation mode
    print(f"\n🎯 CONFIRMATION LOGIC (CRITICAL):")
    
    confirmation_mode = setup.get('confirmation_mode', None)
    trigger_condition = setup.get('trigger_condition', None)
    status = setup.get('status', 'UNKNOWN')
    
    print(f"   Status: {status}")
    
    if confirmation_mode:
        print(f"   ⚡ Confirmation Mode: {confirmation_mode}")
        
        if 'choch' in confirmation_mode.lower() or 'break' in confirmation_mode.lower():
            print(f"   ⏳ WAITING FOR: CHoCH (Change of Character) on 1H or 4H")
            print(f"   📌 Trigger Type: MARKET ORDER (after body closure)")
            print(f"   ❌ Will NOT trigger on price touch alone")
        elif 'limit' in confirmation_mode.lower() or 'price' in confirmation_mode.lower():
            print(f"   ⏳ WAITING FOR: Price to reach entry level")
            print(f"   📌 Trigger Type: LIMIT ORDER (immediate)")
            print(f"   ✅ WILL trigger when price touches entry")
        else:
            print(f"   ❓ Unknown mode: {confirmation_mode}")
    
    if trigger_condition:
        print(f"   Trigger Condition: {trigger_condition}")
    
    # 4. Timing info
    print(f"\n⏰ TIMING INFO:")
    created_at = setup.get('created_at', setup.get('timestamp', 'N/A'))
    print(f"   Created: {created_at}")
    
    expires_at = setup.get('expires_at', None)
    if expires_at:
        print(f"   Expires: {expires_at}")
        # Calculate time remaining
        try:
            expire_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            now_dt = datetime.now(expire_dt.tzinfo)
            remaining = expire_dt - now_dt
            hours = remaining.total_seconds() / 3600
            print(f"   ⏳ Time Remaining: {hours:.1f} hours")
        except:
            pass
    
    # 5. CHoCH specific parameters
    choch_price = setup.get('choch_price', None)
    if choch_price:
        print(f"\n📊 CHoCH INFO:")
        print(f"   CHoCH Price: ${choch_price:,.2f}")
        print(f"   CHoCH Timeframe: {setup.get('choch_timeframe', 'N/A')}")
        print(f"   CHoCH Detected: {setup.get('choch_confirmed', 'NO')}")
    
    # 6. Key levels
    print(f"\n🎚️ KEY LEVELS:")
    if 'ob_1h_high' in setup:
        print(f"   1H OB High: ${setup['ob_1h_high']:,.2f}")
    if 'ob_1h_low' in setup:
        print(f"   1H OB Low: ${setup['ob_1h_low']:,.2f}")
    if 'fvg_daily_bottom' in setup:
        print(f"   Daily FVG Bottom: ${setup['fvg_daily_bottom']:,.2f}")
    if 'fvg_daily_top' in setup:
        print(f"   Daily FVG Top: ${setup['fvg_daily_top']:,.2f}")
    
    return setup

def check_price_distance(setup, current_price):
    """Calculate distance to activation zone"""
    
    entry_price = setup.get('entry_price', 0)
    direction = setup.get('direction', '').lower()
    
    print(f"\n{'='*70}")
    print(f"📏 PRICE DISTANCE ANALYSIS")
    print(f"{'='*70}\n")
    
    print(f"💵 Current Market Price: ${current_price:,.2f}")
    print(f"🎯 Target Entry Price: ${entry_price:,.2f}")
    
    distance = abs(current_price - entry_price)
    percent_distance = (distance / current_price) * 100
    
    print(f"📊 Absolute Distance: ${distance:,.2f}")
    print(f"📊 Percentage Distance: {percent_distance:.2f}%")
    
    # Direction-specific analysis
    if direction == 'sell':
        if current_price > entry_price:
            print(f"\n✅ Price is ABOVE entry ({current_price - entry_price:,.2f} dollars)")
            print(f"   Setup is VALID - waiting for price to fall to ${entry_price:,.2f}")
            
            # Check if we're in pullback zone
            choch_price = setup.get('choch_price', None)
            if choch_price and current_price <= choch_price * 1.10:
                print(f"   🔥 NEAR ACTIVATION ZONE (within 10% of CHoCH)")
        else:
            print(f"\n⚠️  Price is BELOW entry ({entry_price - current_price:,.2f} dollars)")
            print(f"   Price already passed entry point!")
    
    elif direction == 'buy':
        if current_price < entry_price:
            print(f"\n✅ Price is BELOW entry ({entry_price - current_price:,.2f} dollars)")
            print(f"   Setup is VALID - waiting for price to rise to ${entry_price:,.2f}")
        else:
            print(f"\n⚠️  Price is ABOVE entry ({current_price - entry_price:,.2f} dollars)")
            print(f"   Price already passed entry point!")
    
    return distance, percent_distance

def simulate_monitor_decision(setup, current_price):
    """Simulate what the monitor would decide RIGHT NOW"""
    
    print(f"\n{'='*70}")
    print(f"🤖 MONITOR DECISION SIMULATION")
    print(f"{'='*70}\n")
    
    confirmation_mode = setup.get('confirmation_mode', '').lower()
    entry_price = setup.get('entry_price', 0)
    direction = setup.get('direction', '').lower()
    status = setup.get('status', '').lower()
    
    print(f"🔍 Checking conditions...\n")
    
    # Check 1: Status
    print(f"1️⃣ Status Check: {status}")
    if status != 'active' and status != 'pending':
        print(f"   ❌ Setup is not active (status: {status})")
        print(f"\n🚫 VERDICT: Would NOT trigger (inactive setup)")
        return False
    print(f"   ✅ Setup is active")
    
    # Check 2: Confirmation mode
    print(f"\n2️⃣ Confirmation Mode: {confirmation_mode or 'Not specified'}")
    
    if 'choch' in confirmation_mode or 'break' in confirmation_mode:
        print(f"   ⏳ Requires CHoCH (body closure)")
        print(f"   📌 Current price touch is NOT enough")
        
        choch_confirmed = setup.get('choch_confirmed', False)
        print(f"\n3️⃣ CHoCH Confirmed: {choch_confirmed}")
        
        if not choch_confirmed:
            print(f"   ❌ CHoCH not yet detected")
            print(f"\n🚫 VERDICT: Would NOT trigger NOW")
            print(f"   💡 Waiting for: 1H or 4H candle to CLOSE beyond structure")
            return False
        else:
            print(f"   ✅ CHoCH already confirmed")
    
    elif 'limit' in confirmation_mode or 'price' in confirmation_mode:
        print(f"   📌 Only requires price to reach level")
    
    else:
        print(f"   ⚠️  Confirmation mode unclear")
    
    # Check 3: Price proximity
    print(f"\n4️⃣ Price Proximity Check:")
    print(f"   Entry: ${entry_price:,.2f}")
    print(f"   Current: ${current_price:,.2f}")
    
    TOLERANCE_PIPS = 10  # 10 pips tolerance for crypto ($10)
    price_in_range = abs(current_price - entry_price) <= TOLERANCE_PIPS
    
    if direction == 'sell':
        if current_price >= entry_price - TOLERANCE_PIPS:
            print(f"   ✅ Price in range (within {TOLERANCE_PIPS} pips of entry)")
        else:
            print(f"   ❌ Price too far below entry")
            print(f"\n🚫 VERDICT: Would NOT trigger (price not reached)")
            return False
    
    elif direction == 'buy':
        if current_price <= entry_price + TOLERANCE_PIPS:
            print(f"   ✅ Price in range (within {TOLERANCE_PIPS} pips of entry)")
        else:
            print(f"   ❌ Price too far above entry")
            print(f"\n🚫 VERDICT: Would NOT trigger (price not reached)")
            return False
    
    # Check 4: Expiry
    expires_at = setup.get('expires_at', None)
    if expires_at:
        try:
            expire_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            now_dt = datetime.now(expire_dt.tzinfo)
            if now_dt >= expire_dt:
                print(f"\n⏰ Expiry Check: ❌ Setup expired at {expires_at}")
                print(f"\n🚫 VERDICT: Would NOT trigger (expired)")
                return False
            else:
                print(f"\n⏰ Expiry Check: ✅ Still valid")
        except:
            print(f"\n⏰ Expiry Check: ⚠️  Could not parse")
    
    # Final verdict
    print(f"\n{'='*70}")
    print(f"✅ VERDICT: Would TRIGGER NOW (all conditions met)")
    print(f"{'='*70}")
    print(f"\n📤 Monitor would send signal to cTrader:")
    print(f"   Symbol: {setup['symbol']}")
    print(f"   Direction: {direction.upper()}")
    print(f"   Entry: ${entry_price:,.2f}")
    print(f"   SL: ${setup.get('stop_loss', 'N/A'):,.2f}")
    print(f"   TP: ${setup.get('take_profit', 'N/A'):,.2f}")
    
    return True

def main():
    """Main audit execution"""
    
    print("\n" + "="*70)
    print("🔍 MONITORING SETUP AUDIT SCRIPT V23.0")
    print("="*70)
    print("Purpose: Decode what the monitor is waiting for")
    print("Focus: BTCUSD setup confirmation logic")
    print("="*70 + "\n")
    
    # 1. Load monitoring file
    data, file_path = load_monitoring_file()
    if not data:
        print("\n❌ Cannot proceed without monitoring_setups.json")
        return
    
    print(f"✅ Loaded: {file_path}")
    
    # Handle structure: {"setups": [...]} or [...]
    setups_list = data.get('setups', data) if isinstance(data, dict) else data
    print(f"📊 Total setups in file: {len(setups_list)}\n")
    
    # 2. Find BTCUSD setup
    btc_setup = None
    for setup in setups_list:
        if setup.get('symbol', '').upper() == 'BTCUSD':
            btc_setup = setup
            break
    
    if not btc_setup:
        print("❌ BTCUSD setup NOT FOUND in monitoring_setups.json")
        print("\n📋 Available symbols:")
        for setup in setups_list:
            print(f"   - {setup.get('symbol', 'UNKNOWN')}")
        return
    
    print("✅ BTCUSD setup FOUND\n")
    
    # 3. Decode confirmation logic
    decode_confirmation_logic(btc_setup)
    
    # 4. Get current price
    print("\n" + "="*70)
    print("Fetching current BTCUSD price...")
    print("="*70 + "\n")
    
    try:
        current_price = get_btc_price()
    except Exception as e:
        print(f"❌ Error getting price: {e}")
        return
    
    # 5. Check price distance
    check_price_distance(btc_setup, current_price)
    
    # 6. Simulate monitor decision
    simulate_monitor_decision(btc_setup, current_price)
    
    # 7. Final summary
    print("\n" + "="*70)
    print("📊 AUDIT COMPLETE")
    print("="*70)
    print("\n💡 KEY INSIGHTS:")
    print("   1. Check 'Confirmation Mode' above - does it say CHoCH or Limit?")
    print("   2. Check 'Price Distance' - are we close to entry?")
    print("   3. Check 'Monitor Decision' - would it trigger now or wait?")
    print("\n🎯 Next Step:")
    print("   - If waiting for CHoCH: Wait for 1H/4H candle close beyond structure")
    print("   - If waiting for price: Wait for market to reach entry level")
    print("   - If expired: Remove from monitoring_setups.json")
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    main()
