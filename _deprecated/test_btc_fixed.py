"""Quick test pentru BTCUSD cu chart fixed"""
import sys
from morning_strategy_scan import MorningStrategyScanner

scanner = MorningStrategyScanner()

# Test BTCUSD
btc_pair = {'symbol': 'BTCUSD', 'priority': 1}
result = scanner.analyze_pair(btc_pair)

print(f"\n{'='*60}")
print("🎯 BTCUSD TEST RESULT:")
print(f"{'='*60}")
print(f"Has Setup: {result.has_setup}")
if result.setup:
    print(f"Direction: {result.setup.daily_choch.direction.upper()}")
    print(f"Strategy: {result.setup.strategy_type.upper()}")
    print(f"Entry: {result.setup.entry_price:.2f}")
    print(f"Chart: {result.chart_path}")
else:
    print("No setup detected")
print(f"{'='*60}")
