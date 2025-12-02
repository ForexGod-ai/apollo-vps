"""Quick test NZDUSD strategy type"""
import MetaTrader5 as mt5
from spatiotemporal_analyzer import SpatioTemporalAnalyzer

mt5.initialize()
analyzer = SpatioTemporalAnalyzer("NZDUSD")
narrative = analyzer.analyze_market()

if narrative.expected_scenarios:
    strategy = narrative.expected_scenarios[0].get('strategy_type', 'UNKNOWN')
    print(f"\n{'='*60}")
    print(f"NZDUSD STRATEGY: {strategy}")
    print(f"{'='*60}\n")
    
    if strategy == 'REVERSAL_BULLISH':
        print("✅ CORRECT! REVERSAL detected")
    else:
        print(f"❌ WRONG! Expected REVERSAL_BULLISH, got {strategy}")
else:
    print("❌ No scenarios generated!")

mt5.shutdown()
