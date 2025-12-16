"""Debug NZDUSD to see why it's not detected"""
import numpy as np
import pandas as pd
from datetime import datetime
from smc_detector import SMCDetector

# Create NZDUSD pattern exactly as in morning_strategy_scan.py
bars = 100
np.random.seed(42)  # Fixed seed
prices = np.zeros(bars)
prices[0] = 0.590

# Candles 1-50: Strong bearish trend
for i in range(1, 50):
    drop = 0.0004 if i % 5 != 0 else -0.0008
    prices[i] = prices[i-1] - drop

# Candles 50-59: Bottom formation
for i in range(50, 60):
    prices[i] = 0.565 + np.random.uniform(-0.001, 0.001)

# Candles 60-62: FVG creation
prices[60] = 0.565
prices[61] = 0.5665
prices[62] = 0.567

# Candle 63: CHoCH @ 0.568
prices[63] = 0.568

# Candles 64-75: Bullish impulse
for i in range(64, 76):
    prices[i] = prices[i-1] + np.random.uniform(0.0005, 0.0015)

# Candles 76-90: Pullback to FVG
current = prices[75]
for i in range(76, 91):
    prices[i] = current - (current - 0.566) * (i - 75) / 15.0

# Last 9 candles: Consolidation
for i in range(91, bars):
    prices[i] = 0.566 + np.random.uniform(-0.0003, 0.0005)

# Generate OHLC
dates = pd.date_range(end=datetime.now(), periods=bars, freq='D')
opens = prices * (1 + np.random.uniform(-0.001, 0.001, bars))
highs = np.maximum(opens, prices) * (1 + np.abs(np.random.uniform(0, 0.003, bars)))
lows = np.minimum(opens, prices) * (1 - np.abs(np.random.uniform(0, 0.003, bars)))

df = pd.DataFrame({
    'time': dates,
    'open': opens,
    'high': highs,
    'low': lows,
    'close': prices,
    'volume': np.ones(bars) * 1000
})

print("📊 NZDUSD Debug Analysis")
print("="*60)
print(f"Price range: {prices.min():.5f} - {prices.max():.5f}")
print(f"Current price: {prices[-1]:.5f}")
print(f"CHoCH candle (63): {prices[63]:.5f}")

# Test SMC detector
detector = SMCDetector()

print("\n🔍 Detecting CHoCH...")
chochs = detector.detect_choch(df)
print(f"CHoCH found: {len(chochs)}")
for i, choch in enumerate(chochs):
    print(f"  #{i+1}: Index={choch.index}, Direction={choch.direction}, Price={choch.break_price:.5f}")

print("\n🔍 Running full scan_for_setup...")
setup = detector.scan_for_setup('NZDUSD', df, df, priority=2)

if setup:
    print("✅ SETUP FOUND!")
    print(f"   Strategy: {setup.strategy_type}")
    print(f"   Direction: {setup.daily_choch.direction}")
    print(f"   Entry: {setup.entry_price:.5f}")
    print(f"   R:R: 1:{setup.risk_reward:.2f}")
else:
    print("❌ NO SETUP DETECTED - Checking why...")
    if not chochs:
        print("   ❌ No CHoCH detected")
    else:
        print(f"   ✅ CHoCH exists: {chochs[-1].direction}")
