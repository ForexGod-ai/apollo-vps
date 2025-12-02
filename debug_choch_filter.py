"""Debug CHoCH detection"""
import MetaTrader5 as mt5
from spatiotemporal_analyzer import SpatioTemporalAnalyzer

mt5.initialize()
analyzer = SpatioTemporalAnalyzer("NZDUSD")

# Get data
df_daily = analyzer._get_data('D1', 100)

# Find CHoCH events
choch_events = analyzer._find_choch_events(df_daily, 'daily')

print(f"\n{'='*60}")
print(f"TOTAL CHoCH EVENTS FOUND: {len(choch_events)}")
print(f"{'='*60}\n")

for event in choch_events:
    print(f"  [{event.timeframe.upper()}] CHoCH {event.direction}")
    print(f"      Bars ago: {event.bars_ago}")
    print(f"      Price: ${event.price:.5f}")
    print(f"      Timestamp: {event.timestamp}")
    print()

print(f"\n{'='*60}")
print("CHECKING: Which CHoCH is within 20 bars?")
print(f"{'='*60}\n")

recent_choch = next(
    (e for e in reversed(choch_events) if e.event_type == 'choch' and e.timeframe == 'daily' and e.bars_ago <= 20),
    None
)

if recent_choch:
    print(f"✅ FOUND: CHoCH {recent_choch.direction} at bar -{recent_choch.bars_ago}")
else:
    print("❌ NO CHoCH found within 20 bars!")
    print("\nAll CHoCH bars_ago values:")
    for e in choch_events:
        print(f"   - {e.bars_ago} bars ago ({e.direction})")

mt5.shutdown()
