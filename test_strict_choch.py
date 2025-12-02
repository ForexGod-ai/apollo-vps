from spatiotemporal_analyzer import SpatioTemporalAnalyzer
import MetaTrader5 as mt5

mt5.initialize()

print("=" * 80)
print("TESTING NEW CHoCH DETECTION - STRICT VERSION")
print("=" * 80)

# Test GBPUSD
print("\n🔍 Analyzing GBPUSD...")
analyzer = SpatioTemporalAnalyzer('GBPUSD')
result = analyzer.analyze_market()

print(f"\n🎯 Strategy Type: {result['strategy_type']}")
print(f"📊 Recommendation: {result['recommendation']}")
print(f"💬 Reasoning: {result['narrative']['present']['reasoning']}")

if result['narrative']['past']['events']:
    print(f"\n📅 Events detected:")
    for event in result['narrative']['past']['events'][:5]:
        print(f"   - {event.event_type.upper()} {event.direction} @ {event.price:.5f} ({event.bars_ago} bars ago)")

print("\n" + "=" * 80)

mt5.shutdown()
