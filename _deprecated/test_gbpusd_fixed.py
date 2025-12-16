"""Quick test for GBPUSD with FIXED trend detection"""
import sys
from morning_strategy_scan import MorningStrategyScanner

scanner = MorningStrategyScanner()

# Test doar GBPUSD
gbpusd_pair = {'symbol': 'GBPUSD', 'priority': 1}
result = scanner.analyze_pair(gbpusd_pair)

print(f"\n{'='*60}")
print("🎯 GBPUSD TEST RESULT:")
print(f"{'='*60}")
print(f"Has Setup: {result.has_setup}")
if result.setup:
    print(f"Direction: {result.setup.daily_choch.direction.upper()}")
    print(f"Strategy: {result.setup.strategy_type.upper()}")
    print(f"Entry: {result.setup.entry_price:.5f}")
    print(f"Chart: {result.chart_path}")
else:
    print("No setup detected")
print(f"{'='*60}")
