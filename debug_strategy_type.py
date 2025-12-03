#!/usr/bin/env python3
"""Debug strategy type detection for GBPJPY and USDCHF"""

from ctrader_data_client import get_ctrader_client
from smc_detector import SMCDetector

client = get_ctrader_client()
detector = SMCDetector()

# Test GBPJPY
print("="*60)
print("🔍 GBPJPY Analysis")
print("="*60)
df_gbpjpy = client.get_historical_data('GBPJPY', 'D1', 100)
setup_gbpjpy = detector.scan_for_setup('GBPJPY', df_gbpjpy, df_gbpjpy, priority=1)

if setup_gbpjpy:
    choch = setup_gbpjpy.daily_choch
    pre_structure = detector._analyze_pre_choch_structure(df_gbpjpy, choch)
    
    print(f"\nCHoCH Direction: {choch.direction.upper()}")
    print(f"Previous Trend (from CHoCH): {choch.previous_trend}")
    print(f"\nPre-CHoCH Structure Analysis:")
    print(f"  Pattern: {pre_structure['pattern']}")
    print(f"  Confidence: {pre_structure['confidence']}%")
    print(f"\nDetected Strategy: {setup_gbpjpy.strategy_type.upper()}")
    print(f"\n❌ Should be: CONTINUITY (trendul BULLISH continua)")
    print(f"   Reason: GBPJPY was already BULLISH before CHoCH")

# Test USDCHF
print("\n" + "="*60)
print("🔍 USDCHF Analysis")
print("="*60)
df_usdchf = client.get_historical_data('USDCHF', 'D1', 100)
setup_usdchf = detector.scan_for_setup('USDCHF', df_usdchf, df_usdchf, priority=2)

if setup_usdchf:
    choch = setup_usdchf.daily_choch
    pre_structure = detector._analyze_pre_choch_structure(df_usdchf, choch)
    
    print(f"\nCHoCH Direction: {choch.direction.upper()}")
    print(f"Previous Trend (from CHoCH): {choch.previous_trend}")
    print(f"\nPre-CHoCH Structure Analysis:")
    print(f"  Pattern: {pre_structure['pattern']}")
    print(f"  Confidence: {pre_structure['confidence']}%")
    print(f"\nDetected Strategy: {setup_usdchf.strategy_type.upper()}")
    print(f"\n❌ Should be: CONTINUITY (trendul BEARISH continua)")

# Test EURCAD
print("\n" + "="*60)
print("🔍 EURCAD Analysis")
print("="*60)
df_eurcad = client.get_historical_data('EURCAD', 'D1', 100)
setup_eurcad = detector.scan_for_setup('EURCAD', df_eurcad, df_eurcad, priority=2)

if setup_eurcad:
    choch = setup_eurcad.daily_choch
    pre_structure = detector._analyze_pre_choch_structure(df_eurcad, choch)
    
    print(f"\nCHoCH Direction: {choch.direction.upper()}")
    print(f"Previous Trend (from CHoCH): {choch.previous_trend}")
    print(f"\nPre-CHoCH Structure Analysis:")
    print(f"  Pattern: {pre_structure['pattern']}")
    print(f"  Confidence: {pre_structure['confidence']}%")
    print(f"\nDetected Strategy: {setup_eurcad.strategy_type.upper()}")
    print(f"\n✅ Should be: REVERSAL (trendul se inverseaza)")

print("\n" + "="*60)
