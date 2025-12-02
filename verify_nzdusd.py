"""
🔍 VERIFICARE DETALIATĂ NZDUSD
Verifică dacă algoritmul detectează reversalul bearish → bullish
"""

import MetaTrader5 as mt5
import pandas as pd
from loguru import logger
from smc_algorithm import SMCAlgorithm
from smc_detector import SMCDetector

# Initialize MT5
if not mt5.initialize():
    logger.error("❌ MT5 failed")
    exit()

symbol = "NZDUSD"
logger.info("="*80)
logger.info(f"🔍 ANALYZING {symbol} - Checking for Bearish → Bullish Reversal")
logger.info("="*80)

# Get Daily data
logger.info("\n📊 DAILY TIMEFRAME ANALYSIS:")
rates_d1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 100)
if rates_d1 is None:
    logger.error(f"No data for {symbol}")
    exit()

df_d1 = pd.DataFrame(rates_d1)
df_d1['time'] = pd.to_datetime(df_d1['time'], unit='s')

current_price = df_d1['close'].iloc[-1]
logger.info(f"Current Price: ${current_price:.5f}")

# SMC Detector - raw detections
smc_detector = SMCDetector()

# Detect CHoCH
logger.info("\n🔄 CHANGE OF CHARACTER (CHoCH) DETECTION:")
chochs = smc_detector.detect_choch(df_d1)
if chochs:
    logger.info(f"Found {len(chochs)} CHoCH events:")
    for i, choch in enumerate(chochs[-3:], 1):  # Last 3
        logger.info(f"  {i}. Direction: {choch.direction.upper()}")
        logger.info(f"     Break Price: ${choch.break_price:.5f}")
        logger.info(f"     Previous Trend: {choch.previous_trend} → New: {choch.direction}")
    
    latest_choch = chochs[-1]
    logger.info(f"\n✅ LATEST CHoCH: {latest_choch.direction.upper()}")
    if latest_choch.direction == 'bullish':
        logger.info("   🟢 BEARISH → BULLISH REVERSAL CONFIRMED!")
    else:
        logger.info("   🔴 BULLISH → BEARISH REVERSAL")
else:
    logger.info("❌ No CHoCH detected")

# Detect BOS (commented - not in current SMCDetector)
# logger.info("\n📈 BREAK OF STRUCTURE (BOS) DETECTION:")
# if bos_events:
#     ...

# Detect FVG (Fair Value Gaps)
logger.info("\n📊 FAIR VALUE GAP (FVG) DETECTION:")
if chochs:
    fvg = smc_detector.detect_fvg(df_d1, chochs[-1], current_price)
    if fvg:
        logger.info(f"✅ FVG FOUND!")
        logger.info(f"   Zone: ${fvg.bottom:.5f} - ${fvg.top:.5f}")
        size = fvg.top - fvg.bottom
        logger.info(f"   Size: ${size:.5f}")
        
        # Check if price in FVG
        in_fvg = smc_detector.is_price_in_fvg(current_price, fvg)
        logger.info(f"   Price in FVG: {'✅ YES' if in_fvg else '❌ NO'}")
        
        if not in_fvg:
            distance = min(abs(current_price - fvg.top), abs(current_price - fvg.bottom))
            logger.info(f"   Distance to FVG: ${distance:.5f}")
    else:
        logger.info("❌ No FVG detected after latest CHoCH")

# Premium/Discount zones
logger.info("\n💰 PREMIUM/DISCOUNT ANALYSIS:")
high = df_d1['high'].max()
low = df_d1['low'].min()
range_size = high - low
equilibrium = (high + low) / 2

premium_start = equilibrium + (range_size * 0.05)
discount_end = equilibrium - (range_size * 0.05)

logger.info(f"Range High: ${high:.5f}")
logger.info(f"Range Low: ${low:.5f}")
logger.info(f"Equilibrium: ${equilibrium:.5f}")
logger.info(f"Premium Zone: Above ${premium_start:.5f}")
logger.info(f"Discount Zone: Below ${discount_end:.5f}")

if current_price > premium_start:
    logger.info(f"✅ Price in PREMIUM - Good for SELLS")
elif current_price < discount_end:
    logger.info(f"✅ Price in DISCOUNT - Good for BUYS")
else:
    logger.info(f"⚖️ Price in EQUILIBRIUM")

# Get 4H data for confirmation
logger.info("\n⏰ 4-HOUR TIMEFRAME CONFIRMATION:")
rates_4h = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 200)
if rates_4h is not None:
    df_4h = pd.DataFrame(rates_4h)
    df_4h['time'] = pd.to_datetime(df_4h['time'], unit='s')
    
    chochs_4h = smc_detector.detect_choch(df_4h)
    if chochs_4h:
        latest_4h = chochs_4h[-1]
        logger.info(f"Latest 4H CHoCH: {latest_4h.direction.upper()}")
        
        if chochs and latest_choch.direction == 'bullish' and latest_4h.direction == 'bearish':
            logger.info("✅ GLITCH IN MATRIX SETUP POSSIBLE!")
            logger.info("   Daily: BULLISH | 4H: BEARISH (opposite = entry signal)")
        elif chochs and latest_choch.direction == 'bearish' and latest_4h.direction == 'bullish':
            logger.info("✅ GLITCH IN MATRIX SETUP POSSIBLE!")
            logger.info("   Daily: BEARISH | 4H: BULLISH (opposite = entry signal)")

# Now run full SMC Algorithm
logger.info("\n" + "="*80)
logger.info("🤖 RUNNING FULL SMC ALGORITHM:")
logger.info("="*80)

smc_algo = SMCAlgorithm()
signal = smc_algo.analyze(df_d1, symbol)

if signal:
    logger.info(f"\n🔥 SIGNAL DETECTED!")
    logger.info(f"Direction: {signal.direction.upper()}")
    logger.info(f"Confidence: {signal.confidence}/10 {'⭐' * signal.confidence}")
    logger.info(f"\nEntry Zone: ${signal.entry_zone[0]:.5f} - ${signal.entry_zone[1]:.5f}")
    logger.info(f"Stop Loss: ${signal.stop_loss:.5f}")
    logger.info(f"Take Profit: ${signal.take_profit:.5f}")
    logger.info(f"Risk/Reward: 1:{signal.risk_reward:.2f}")
    
    logger.info(f"\n✅ CONFLUENCE REASONS ({len(signal.reasons)}):")
    for i, reason in enumerate(signal.reasons, 1):
        logger.info(f"   {i}. {reason}")
else:
    logger.info(f"\n❌ NO SIGNAL GENERATED")
    logger.info("Possible reasons:")
    logger.info("  • No strong CHoCH detected")
    logger.info("  • No valid Order Block found")
    logger.info("  • Insufficient confluence factors")
    logger.info("  • Risk/Reward below threshold (< 1.5)")
    logger.info("  • Missing FVG or price not in optimal zone")

logger.info("\n" + "="*80)
logger.info("✅ ANALYSIS COMPLETE")
logger.info("="*80)

mt5.shutdown()
