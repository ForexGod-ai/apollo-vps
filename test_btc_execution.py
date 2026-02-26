#!/usr/bin/env python3
"""
Test BTC Execution with Two-Way Handshake
Verifies: Signal writing + Confirmation waiting + Telegram notification
"""

import json
import time
from pathlib import Path
from ctrader_executor import CTraderExecutor

def test_btc_execution():
    """Test BTCUSD execution with real Two-Way Handshake"""
    
    print("\n" + "="*70)
    print("🧪 TESTING BTCUSD EXECUTION - TWO-WAY HANDSHAKE")
    print("="*70)
    
    # Initialize executor
    print("\n1️⃣ Initializing CTrader Executor...")
    executor = CTraderExecutor()
    
    # Test parameters
    symbol = "BTCUSD"
    direction = "BUY"
    entry_price = 65000.50
    stop_loss = 64500.00
    take_profit = 66000.00
    lot_size = 0.50  # Will be forced by V5.6 bulletproof fix
    
    print(f"\n2️⃣ Preparing BTC signal...")
    print(f"   Symbol: {symbol}")
    print(f"   Direction: {direction}")
    print(f"   Entry: {entry_price}")
    print(f"   SL: {stop_loss}")
    print(f"   TP: {take_profit}")
    print(f"   Lot Size: {lot_size}")
    
    # Execute trade
    print(f"\n3️⃣ Executing trade...")
    print(f"   (Signal will be written to signals.json)")
    print(f"   (Python will WAIT for execution_report.json)")
    print(f"   (Timeout: 30 seconds)")
    
    result = executor.execute_trade(
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        lot_size=lot_size,
        comment="TEST - Two-Way Handshake",
        status="READY"
    )
    
    if result:
        print(f"\n✅ Trade signal sent to queue!")
        print(f"\n4️⃣ Monitoring confirmation process...")
        print(f"   Check Telegram for notification:")
        print(f"   • ✅ SUCCESS = cTrader executed trade")
        print(f"   • ❌ REJECTED = cTrader rejected (BadVolume, etc.)")
        print(f"   • ⏱️ TIMEOUT = cTrader not responding")
        
        # Wait for queue to process (background thread)
        print(f"\n⏳ Waiting 35 seconds for queue processing...")
        time.sleep(35)
        
        # Check if execution_report.json was created
        report_path = Path("execution_report.json")
        if report_path.exists():
            print(f"\n5️⃣ Execution report found!")
            with open(report_path, 'r') as f:
                report = json.load(f)
            
            print(f"\n📊 REPORT DETAILS:")
            print(f"   Signal ID: {report.get('SignalId')}")
            print(f"   Status: {report.get('Status')}")
            print(f"   Order ID: {report.get('OrderId')}")
            print(f"   Volume: {report.get('Volume')}")
            print(f"   Entry: {report.get('EntryPrice')}")
            print(f"   Message: {report.get('Message')}")
            print(f"   Timestamp: {report.get('Timestamp')}")
            
            if report.get('Status') == 'EXECUTED':
                print(f"\n✅ SUCCESS: Trade executed in cTrader!")
            elif report.get('Status') == 'REJECTED':
                print(f"\n❌ REJECTED: {report.get('Reason')}")
            else:
                print(f"\n⚠️ UNKNOWN STATUS: {report.get('Status')}")
        else:
            print(f"\n⏱️ TIMEOUT: No execution report received")
            print(f"   Possible causes:")
            print(f"   • cBot not running in cTrader")
            print(f"   • File permissions issue")
            print(f"   • Silent error in cBot")
    else:
        print(f"\n❌ Trade signal rejected by Risk Manager!")
        print(f"   Check logs above for rejection reason")
    
    print("\n" + "="*70)
    print("🧪 TEST COMPLETE")
    print("="*70)
    print("\n📱 Check Telegram for notification!")
    print("📂 Check cTrader Journal for execution logs")
    print("\n")

if __name__ == "__main__":
    test_btc_execution()
