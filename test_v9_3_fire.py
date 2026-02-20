import json
import time

signal = {
    "SignalId": f"TEST_V9_3_{int(time.time())}",
    "Symbol": "BTC/USD",
    "Direction": "sell",
    "OrderType": "market",
    "LotSize": 0.50,
    "RawUnits": 0,
    "EntryPrice": 66500.0,
    "StopLoss": 68000.0,
    "TakeProfit": 60000.0,
    "StrategyType": "BRUTE_FORCE",
    "DailyRangePercentage": 0.0,
    "RiskAmount": 341.0,
    "AccountBalance": 6800.0
}

file_path = "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/signals.json"

with open(file_path, 'w') as f:
    json.dump(signal, f, indent=4)

print(f"🚀 SEMNAL V9.3 TRIMIS! OCHI PE CTRADER!")
