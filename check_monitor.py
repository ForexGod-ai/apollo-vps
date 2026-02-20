#!/usr/bin/env python3
"""
🔍 Monitoring Setups Radiography Tool
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Quick snapshot of what the monitor is waiting for in monitoring_setups.json

For: ФорексГод - Glitch in Matrix V3.7
Date: February 13, 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

def load_monitoring_file() -> Optional[Dict]:
    """Load monitoring_setups.json from workspace or GlitchMatrix"""
    
    workspace_path = Path(__file__).parent / "monitoring_setups.json"
    glitch_path = Path.home() / "GlitchMatrix" / "monitoring_setups.json"
    
    for path in [workspace_path, glitch_path]:
        if path.exists():
            with open(path, 'r') as f:
                data = json.load(f)
                # Handle both {"setups": [...]} and [...] structures
                return data.get('setups', data) if isinstance(data, dict) else data
    
    return None

def get_live_price(symbol: str) -> Optional[float]:
    """Get current price for symbol (with fallback options)"""
    
    # Map trading symbols to data provider symbols
    symbol_map = {
        'BTCUSD': 'BTC-USD',
        'ETHUSD': 'ETH-USD',
        'EURUSD': 'EURUSD=X',
        'GBPUSD': 'GBPUSD=X',
        'USDJPY': 'USDJPY=X',
        'USDCHF': 'USDCHF=X',
        'AUDUSD': 'AUDUSD=X',
        'USDCAD': 'USDCAD=X',
        'NZDUSD': 'NZDUSD=X',
        'EURGBP': 'EURGBP=X',
        'EURJPY': 'EURJPY=X',
        'GBPJPY': 'GBPJPY=X',
        'XTIUSD': 'CL=F',  # Crude Oil
        'XAUUSD': 'GC=F',  # Gold
    }
    
    yahoo_symbol = symbol_map.get(symbol.upper(), symbol)
    
    # Try yfinance first
    try:
        import yfinance as yf
        ticker = yf.Ticker(yahoo_symbol)
        data = ticker.history(period="1d", timeout=3)
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    
    # Fallback to ccxt for crypto
    if 'BTC' in symbol or 'ETH' in symbol:
        try:
            import ccxt
            exchange = ccxt.binance()
            ticker_symbol = symbol.replace('USD', '/USDT')
            ticker = exchange.fetch_ticker(ticker_symbol)
            return float(ticker['last'])
        except:
            pass
    
    return None

def decode_trigger_condition(setup: Dict) -> str:
    """Decode what the monitor is waiting for"""
    
    status = setup.get('status', '').upper()
    
    # Check for CHoCH detection flags
    choch_1h = setup.get('choch_1h_detected', False)
    choch_4h = setup.get('choch_4h_detected', False)
    
    # Check confirmation mode
    confirmation = setup.get('confirmation_mode', '').lower()
    trigger = setup.get('trigger_condition', '').lower()
    
    # Fibo pullback logic
    fibo_data = setup.get('fibo_data', {})
    fibo_50 = fibo_data.get('fibo_50', None)
    
    # Determine what we're waiting for
    if choch_1h or choch_4h:
        timeframe = "1H" if choch_1h else "4H"
        if fibo_50:
            return f"✅ CHoCH {timeframe} confirmed → Waiting for Fibo 50% pullback (${fibo_50:,.2f})"
        else:
            return f"✅ CHoCH {timeframe} confirmed → Waiting for pullback to entry"
    
    elif 'choch' in confirmation or 'choch' in trigger or 'break' in confirmation:
        return "⏳ Waiting for CHoCH (1H or 4H body close beyond structure)"
    
    elif 'limit' in confirmation or 'price' in confirmation:
        return "⏳ Waiting for price to reach entry zone (Limit Order)"
    
    elif fibo_50:
        return f"⏳ Waiting for pullback to Fibo 50% (${fibo_50:,.2f})"
    
    else:
        return "⏳ Waiting for entry zone activation"

def calculate_setup_status(setup: Dict, current_price: Optional[float]) -> str:
    """Determine current status of the setup"""
    
    entry = setup.get('entry_price', 0)
    direction = setup.get('direction', '').lower()
    status = setup.get('status', '').upper()
    
    if not current_price:
        return f"⚪ {status}"
    
    # Check expiry
    expires = setup.get('expires_at', setup.get('expiry_time', None))
    if expires:
        try:
            expire_dt = datetime.fromisoformat(expires.replace('Z', '+00:00'))
            now_dt = datetime.now(timezone.utc)
            if now_dt >= expire_dt:
                return "❌ EXPIRED"
        except:
            pass
    
    # Calculate distance
    distance_pct = abs(current_price - entry) / current_price * 100
    
    # Check if in zone (within 1% for crypto, 0.2% for forex)
    is_crypto = 'BTC' in setup['symbol'] or 'ETH' in setup['symbol']
    tolerance = 1.0 if is_crypto else 0.2
    
    if distance_pct <= tolerance:
        if setup.get('choch_1h_detected') or setup.get('choch_4h_detected'):
            fibo_50 = setup.get('fibo_data', {}).get('fibo_50')
            if fibo_50:
                fibo_distance = abs(current_price - fibo_50) / current_price * 100
                if fibo_distance <= tolerance:
                    return "🟢 IN FIBO ZONE - READY TO TRIGGER"
                else:
                    return f"🟡 IN ZONE - WAITING FOR PULLBACK ({fibo_distance:.1f}% to Fibo)"
            return "🟢 IN ZONE - READY TO TRIGGER"
        else:
            return "🟡 IN ZONE - WAITING FOR CHoCH"
    
    # Not in zone yet
    if direction == 'sell':
        if current_price > entry:
            return f"⚪ WAITING ({distance_pct:.1f}% above entry)"
        else:
            return f"⚠️ PRICE BELOW ENTRY ({distance_pct:.1f}%)"
    else:  # buy
        if current_price < entry:
            return f"⚪ WAITING ({distance_pct:.1f}% below entry)"
        else:
            return f"⚠️ PRICE ABOVE ENTRY ({distance_pct:.1f}%)"

def format_price(price: float, symbol: str) -> str:
    """Format price based on symbol type"""
    is_crypto = 'BTC' in symbol or 'ETH' in symbol
    is_oil = 'XTI' in symbol
    
    if is_crypto:
        return f"${price:,.2f}"
    elif is_oil:
        return f"${price:.2f}"
    else:
        return f"{price:.5f}"

def print_setup_table(setups: List[Dict]):
    """Print beautiful formatted table of setups"""
    
    if not setups:
        print("\n❌ No setups found in monitoring_setups.json\n")
        return
    
    print("\n" + "="*100)
    print("🔍 MONITORING SETUPS RADIOGRAPHY")
    print("="*100)
    print(f"📊 Total Active Setups: {len(setups)}")
    print(f"🕐 Snapshot Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100 + "\n")
    
    for idx, setup in enumerate(setups, 1):
        symbol = setup.get('symbol', 'UNKNOWN')
        direction = setup.get('direction', 'unknown').upper()
        entry = setup.get('entry_price', 0)
        sl = setup.get('stop_loss', 0)
        tp = setup.get('take_profit', 0)
        rr = setup.get('risk_reward', 0)
        strategy = setup.get('strategy_type', 'unknown')
        
        # Get live price
        current_price = get_live_price(symbol)
        
        # Decode trigger
        trigger_info = decode_trigger_condition(setup)
        
        # Calculate status
        status = calculate_setup_status(setup, current_price)
        
        # Direction emoji
        dir_emoji = "🔴" if direction == "SELL" else "🟢"
        
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"Setup #{idx}: {dir_emoji} {symbol} {direction} ({strategy})")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Entry levels
        print(f"\n📍 ENTRY LEVELS:")
        print(f"   Entry:      {format_price(entry, symbol)}")
        print(f"   Stop Loss:  {format_price(sl, symbol)} ({sl - entry:.2f} pips)")
        print(f"   Take Profit: {format_price(tp, symbol)} ({tp - entry:.2f} pips)")
        print(f"   Risk/Reward: {rr:.2f}x")
        
        # Current price & distance
        if current_price:
            distance = abs(current_price - entry)
            distance_pct = (distance / current_price) * 100
            
            print(f"\n💵 LIVE PRICE:")
            print(f"   Current:    {format_price(current_price, symbol)}")
            print(f"   Distance:   {format_price(distance, symbol)} ({distance_pct:.2f}%)")
            
            if direction == "SELL":
                print(f"   Position:   {'Above entry ✅' if current_price > entry else 'Below entry ⚠️'}")
            else:
                print(f"   Position:   {'Below entry ✅' if current_price < entry else 'Above entry ⚠️'}")
        else:
            print(f"\n💵 LIVE PRICE: ⚠️ Unable to fetch")
        
        # Trigger condition
        print(f"\n🎯 TRIGGER CONDITION:")
        print(f"   {trigger_info}")
        
        # CHoCH info if available
        if setup.get('choch_1h_detected'):
            choch_time = setup.get('choch_1h_timestamp', 'N/A')
            print(f"   ✅ CHoCH 1H Detected: {choch_time}")
        if setup.get('choch_4h_detected'):
            choch_time = setup.get('choch_4h_timestamp', 'N/A')
            print(f"   ✅ CHoCH 4H Detected: {choch_time}")
        
        # Fibo levels if available
        fibo_data = setup.get('fibo_data', {})
        if fibo_data:
            print(f"\n📊 FIBONACCI LEVELS:")
            if 'fibo_0' in fibo_data:
                print(f"   Fibo 0%:  {format_price(fibo_data['fibo_0'], symbol)}")
            if 'fibo_50' in fibo_data:
                print(f"   Fibo 50%: {format_price(fibo_data['fibo_50'], symbol)} ⭐")
            if 'fibo_618' in fibo_data:
                print(f"   Fibo 61.8%: {format_price(fibo_data['fibo_618'], symbol)}")
            if 'fibo_100' in fibo_data:
                print(f"   Fibo 100%: {format_price(fibo_data['fibo_100'], symbol)}")
        
        # Status
        print(f"\n📊 STATUS: {status}")
        
        # Timing info
        setup_time = setup.get('setup_time', setup.get('created_at', 'N/A'))
        print(f"\n⏰ TIMING:")
        print(f"   Created: {setup_time}")
        
        expires = setup.get('expires_at', setup.get('expiry_time', None))
        if expires:
            try:
                expire_dt = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                now_dt = datetime.now(timezone.utc)
                remaining = expire_dt - now_dt
                hours = remaining.total_seconds() / 3600
                print(f"   Expires: {expires}")
                print(f"   Remaining: {hours:.1f} hours")
            except:
                print(f"   Expires: {expires}")
        
        print()
    
    print("="*100)
    print("\n💡 LEGEND:")
    print("   🟢 IN FIBO ZONE - READY TO TRIGGER = Price at Fibo 50%, ready to execute")
    print("   🟡 IN ZONE - WAITING FOR CHoCH = Price in range, needs body close confirmation")
    print("   ⚪ WAITING = Price not yet in activation zone")
    print("   ⚠️ PRICE PASSED = Price moved past entry (setup may be invalid)")
    print("   ❌ EXPIRED = Setup timeout reached")
    print("="*100 + "\n")

def print_quick_summary(setups: List[Dict]):
    """Print quick one-line summary"""
    
    if not setups:
        return
    
    print("📋 QUICK SUMMARY:")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    for setup in setups:
        symbol = setup.get('symbol', 'UNKNOWN')
        direction = setup.get('direction', 'unknown').upper()
        dir_emoji = "🔴" if direction == "SELL" else "🟢"
        
        current_price = get_live_price(symbol)
        status = calculate_setup_status(setup, current_price)
        
        print(f"{dir_emoji} {symbol:8s} {direction:4s} | {status}")
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

def main():
    """Main execution"""
    
    print("\n🔍 Loading monitoring_setups.json...")
    
    setups = load_monitoring_file()
    
    if setups is None:
        print("\n❌ ERROR: monitoring_setups.json not found!")
        print("\n📂 Checked locations:")
        print(f"   - {Path(__file__).parent / 'monitoring_setups.json'}")
        print(f"   - {Path.home() / 'GlitchMatrix' / 'monitoring_setups.json'}")
        print("\n💡 Run daily_scanner.py first to generate setups.\n")
        return
    
    if not setups:
        print("\n⚠️  monitoring_setups.json is empty (no active setups)\n")
        return
    
    # Print detailed table
    print_setup_table(setups)
    
    # Print quick summary
    print_quick_summary(setups)
    
    print("✅ Radiography complete!\n")

if __name__ == "__main__":
    main()
