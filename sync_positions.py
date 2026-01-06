#!/usr/bin/env python3
"""
Sync monitoring_setups.json with LIVE cTrader positions
Ensures all open positions are tracked in monitoring file
"""

import json
from ctrader_account_stats import get_account_info
from datetime import datetime

def sync_positions():
    """Sync live positions with monitoring file"""
    
    print("🔄 Syncing monitoring_setups.json with LIVE cTrader positions...")
    
    # Get LIVE positions from cTrader
    account_data = get_account_info()
    live_positions = account_data.get('open_positions', [])
    
    print(f"📊 Found {len(live_positions)} LIVE positions in cTrader")
    
    # Load current monitoring setups
    try:
        with open('monitoring_setups.json', 'r') as f:
            data = json.load(f)
        setups = data.get('setups', [])
        print(f"📋 Found {len(setups)} setups in monitoring file")
    except:
        setups = []
        print("⚠️  No monitoring file found, creating new")
    
    # Create lookup of existing setups by symbol
    existing = {s.get('symbol'): s for s in setups}
    
    # Add missing positions
    added = 0
    for pos in live_positions:
        symbol = pos.get('symbol')
        if symbol not in existing:
            # Add to monitoring
            setup = {
                "symbol": symbol,
                "direction": pos.get('direction', '').lower(),
                "entry_price": pos.get('entry_price', 0),
                "stop_loss": pos.get('stop_loss', 0),
                "take_profit": pos.get('take_profit', 0),
                "risk_reward": 0,  # Calculate if needed
                "strategy_type": "unknown",  # Will be updated by scanner
                "setup_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "priority": 1,
                "status": "MONITORING",
                "lot_size": pos.get('volume', 0.01),
                "sync_source": "ctrader_live"
            }
            setups.append(setup)
            added += 1
            print(f"✅ Added {symbol} to monitoring")
    
    # Remove closed positions
    closed_symbols = []
    live_symbols = {p.get('symbol') for p in live_positions}
    
    updated_setups = []
    for s in setups:
        symbol = s.get('symbol')
        if symbol in live_symbols:
            # Still open
            s['status'] = 'MONITORING'
            updated_setups.append(s)
        else:
            # Closed
            closed_symbols.append(symbol)
            print(f"🔴 Removed {symbol} (closed in cTrader)")
    
    # Save updated file
    data = {"setups": updated_setups}
    with open('monitoring_setups.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print()
    print(f"✅ Sync complete!")
    print(f"   Added: {added}")
    print(f"   Removed: {len(closed_symbols)}")
    print(f"   Total: {len(updated_setups)} setups")
    
    return updated_setups

if __name__ == "__main__":
    print("=" * 60)
    print("🔄 POSITION SYNC - cTrader ↔️ monitoring_setups.json")
    print("=" * 60)
    print()
    
    sync_positions()
    
    print()
    print("=" * 60)
