#!/usr/bin/env python3
"""
Test Auto-Execution System
Simulates morning scanner finding a setup and sending it to cTrader
"""
import json
import time
from datetime import datetime
from telegram_notifier import TelegramNotifier

def test_auto_execution():
    """Simulate a high-quality setup being found"""
    
    print("🧪 TESTING AUTO-EXECUTION SYSTEM")
    print("="*80)
    
    # Simulate best setup found
    test_setup = {
        "symbol": "GBPUSD",
        "strategy_type": "reversal",
        "direction": "bullish",
        "entry_price": 1.2650,
        "stop_loss": 1.2620,
        "take_profit": 1.2710,
        "risk_reward": 2.0,
        "priority": 1
    }
    
    print(f"\n🎯 BEST SETUP DETECTED:")
    print(f"   Symbol: {test_setup['symbol']}")
    print(f"   Strategy: {test_setup['strategy_type'].upper()}")
    print(f"   Direction: {test_setup['direction'].upper()}")
    print(f"   Entry: {test_setup['entry_price']}")
    print(f"   SL: {test_setup['stop_loss']}")
    print(f"   TP: {test_setup['take_profit']}")
    print(f"   R:R: 1:{test_setup['risk_reward']}")
    
    # Generate cTrader signal
    signal = {
        "SignalId": f"MORNING_TEST_{int(time.time())}",
        "Symbol": "GBP/USD",
        "Direction": "buy",
        "StrategyType": "Morning Glitch - Reversal",
        "EntryPrice": test_setup["entry_price"],
        "StopLoss": test_setup["stop_loss"],
        "TakeProfit": test_setup["take_profit"],
        "StopLossPips": abs(test_setup["entry_price"] - test_setup["stop_loss"]) * 10000,
        "TakeProfitPips": abs(test_setup["take_profit"] - test_setup["entry_price"]) * 10000,
        "RiskReward": test_setup["risk_reward"],
        "Timestamp": datetime.now().isoformat()
    }
    
    # Write signal file
    print("\n📝 Creating signals.json...")
    with open('signals.json', 'w') as f:
        json.dump(signal, f, indent=2)
    
    print("✅ Signal file created!")
    print(f"   File: signals.json")
    print(f"   Signal ID: {signal['SignalId']}")
    
    # Send Telegram notification
    print("\n📱 Sending Telegram notification...")
    try:
        telegram = TelegramNotifier()
        
        direction_emoji = "🟢" if signal["Direction"] == "buy" else "🔴"
        message = f"""
🤖 *AUTO-TRADE SIGNAL SENT TO cTRADER*

{direction_emoji} *{test_setup['symbol']}* - {signal['Direction'].upper()}
Strategy: `{test_setup['strategy_type'].upper()}`
R:R: `1:{test_setup['risk_reward']:.1f}`

📍 Entry: `{signal['EntryPrice']:.5f}`
🛑 SL: `{signal['StopLoss']:.5f}` ({signal['StopLossPips']:.1f} pips)
🎯 TP: `{signal['TakeProfit']:.5f}` ({signal['TakeProfitPips']:.1f} pips)

⏰ cBot will execute within 10 seconds...
"""
        telegram.send_message(message.strip())
        print("✅ Telegram message sent!")
        
    except Exception as e:
        print(f"❌ Telegram error: {e}")
    
    print("\n" + "="*80)
    print("🚀 TEST COMPLETE!")
    print("👀 Check:")
    print("   1. cTrader Algo panel - should show execution log")
    print("   2. cTrader Positions tab - should have new trade")
    print("   3. trade_confirmations.json - should be created")
    print("   4. Telegram - should have notification")

if __name__ == "__main__":
    test_auto_execution()
