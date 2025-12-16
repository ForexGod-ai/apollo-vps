#!/usr/bin/env python3
"""
Test cTrader Signal Executor - Generate test signal
"""
import json
import time
from datetime import datetime

def create_test_signal():
    """Create a test trading signal for cTrader"""
    
    signal = {
        "SignalId": f"TEST_{int(time.time())}",
        "Symbol": "EUR/USD",
        "Direction": "buy",
        "StrategyType": "Morning Glitch Matrix",
        "EntryPrice": 1.0850,
        "StopLoss": 1.0830,
        "TakeProfit": 1.0890,
        "StopLossPips": 20.0,
        "TakeProfitPips": 40.0,
        "RiskReward": 2.0,
        "Timestamp": datetime.now().isoformat()
    }
    
    signal_path = "/Users/forexgod/Desktop/trading-ai-agent/signals.json"
    
    with open(signal_path, 'w') as f:
        json.dump(signal, f, indent=2)
    
    print("🚀 TEST SIGNAL CREATED!")
    print("="*80)
    print(f"📊 Symbol: {signal['Symbol']}")
    print(f"📈 Direction: {signal['Direction'].upper()}")
    print(f"💰 Entry: {signal['EntryPrice']}")
    print(f"🛑 SL: {signal['StopLoss']} ({signal['StopLossPips']} pips)")
    print(f"🎯 TP: {signal['TakeProfit']} ({signal['TakeProfitPips']} pips)")
    print(f"⚡ R:R: 1:{signal['RiskReward']}")
    print("="*80)
    print(f"📁 Signal file: {signal_path}")
    print("\n✅ cBot should execute this trade in ~10 seconds!")
    print("👀 Watch cTrader Algo panel for execution confirmation...")

if __name__ == "__main__":
    create_test_signal()
