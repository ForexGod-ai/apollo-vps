"""
Full scan with GLITCH IN MATRIX Price Action Analyzer
Compare cu vechiul sistem vs noul sistem
"""
import MetaTrader5 as mt5
import pandas as pd
from loguru import logger
from price_action_analyzer import PriceActionAnalyzer
from smc_detector import SMCDetector
import json

# Initialize MT5
if not mt5.initialize():
    logger.error("MT5 initialization failed")
    exit()

logger.info(f"MT5 Connected: Account #{mt5.account_info().login}")

# Load pairs config
with open('pairs_config.json', 'r') as f:
    config = json.load(f)

all_pairs = [p['symbol'] for p in config['pairs']]

# Initialize analyzers
glitch_analyzer = PriceActionAnalyzer()
old_detector = SMCDetector()

logger.info("\n" + "="*80)
logger.info("🔥 GLITCH IN MATRIX vs OLD SYSTEM - COMPARISON SCAN")
logger.info("="*80)

glitch_signals = []
old_signals = []

for symbol in all_pairs:
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 Scanning {symbol}...")
    logger.info(f"{'='*80}")
    
    # Get Daily data
    rates_d1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 100)
    rates_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 200)
    
    if rates_d1 is None or len(rates_d1) == 0:
        logger.warning(f"⚠️ No data for {symbol}")
        continue
    
    df_d1 = pd.DataFrame(rates_d1)
    df_d1['time'] = pd.to_datetime(df_d1['time'], unit='s')
    
    df_h4 = pd.DataFrame(rates_h4) if rates_h4 is not None else None
    if df_h4 is not None:
        df_h4['time'] = pd.to_datetime(df_h4['time'], unit='s')
    
    # 1. NEW GLITCH ANALYZER
    glitch_signal = glitch_analyzer.analyze_full_context(df_d1, symbol)
    
    if glitch_signal and glitch_signal.confidence >= 6:
        glitch_signals.append(glitch_signal)
        logger.info(f"\n🔥 GLITCH SIGNAL!")
        logger.info(f"   Direction: {glitch_signal.direction.upper()}")
        logger.info(f"   Confidence: {glitch_signal.confidence}/10")
        logger.info(f"   CHoCH: {'✅' if glitch_signal.choch_confirmed else '❌'}")
        logger.info(f"   FVG: {'✅' if glitch_signal.fvg_present else '❌'}")
        logger.info(f"   Reasons: {len(glitch_signal.reasons)}")
    else:
        logger.info(f"   ⏳ GLITCH: No signal (confidence too low or no setup)")
    
    # 2. OLD SMC DETECTOR
    old_setup = old_detector.scan_for_setup(symbol, df_d1, df_h4, priority=1) if df_h4 is not None else None
    
    if old_setup:
        old_signals.append(old_setup)
        logger.info(f"\n📊 OLD SYSTEM:")
        logger.info(f"   Direction: {old_setup.daily_choch.direction.upper()}")
        logger.info(f"   Status: {old_setup.status}")
        logger.info(f"   Daily CHoCH: {old_setup.daily_choch.direction.upper()}")
    else:
        logger.info(f"   ⏳ OLD: No setup")
    
    # COMPARISON
    if glitch_signal and old_setup:
        if glitch_signal.direction == old_setup.daily_choch.direction:
            logger.info(f"\n✅ AGREEMENT: Both say {glitch_signal.direction.upper()}")
        else:
            logger.info(f"\n⚠️ CONFLICT: GLITCH={glitch_signal.direction.upper()} vs OLD={old_setup.daily_choch.direction.upper()}")
            logger.info(f"   GLITCH confidence: {glitch_signal.confidence}/10")
            logger.info(f"   GLITCH reasons: {glitch_signal.reasons}")

mt5.shutdown()

# SUMMARY
logger.info("\n" + "="*80)
logger.info("📊 SCAN SUMMARY")
logger.info("="*80)

logger.info(f"\n🔥 GLITCH SIGNALS: {len(glitch_signals)}")
for sig in glitch_signals:
    logger.info(f"   • {sig.symbol}: {sig.direction.upper()} (confidence {sig.confidence}/10)")

logger.info(f"\n📊 OLD SYSTEM SIGNALS: {len(old_signals)}")
for setup in old_signals:
    logger.info(f"   • {setup.symbol}: {setup.daily_choch.direction.upper()} ({setup.status})")

# Check for specific issues
logger.info(f"\n🔍 SPECIFIC CHECKS:")

gbpusd_glitch = [s for s in glitch_signals if s.symbol == 'GBPUSD']
gbpusd_old = [s for s in old_signals if s.symbol == 'GBPUSD']

if gbpusd_glitch:
    logger.info(f"   GBPUSD GLITCH: {gbpusd_glitch[0].direction.upper()} (confidence {gbpusd_glitch[0].confidence}/10)")
else:
    logger.info(f"   GBPUSD GLITCH: No signal ✅ (Good! Era detectat greșit ca LONG)")

if gbpusd_old:
    logger.info(f"   GBPUSD OLD: {gbpusd_old[0].daily_choch.direction.upper()} ({gbpusd_old[0].status})")
else:
    logger.info(f"   GBPUSD OLD: No signal")

nzdusd_glitch = [s for s in glitch_signals if s.symbol == 'NZDUSD']
nzdusd_old = [s for s in old_signals if s.symbol == 'NZDUSD']

if nzdusd_glitch:
    logger.info(f"   NZDUSD GLITCH: {nzdusd_glitch[0].direction.upper()} (confidence {nzdusd_glitch[0].confidence}/10) ✅")
else:
    logger.info(f"   NZDUSD GLITCH: No signal")

if nzdusd_old:
    logger.info(f"   NZDUSD OLD: {nzdusd_old[0].daily_choch.direction.upper()} ({nzdusd_old[0].status}) ✅")
else:
    logger.info(f"   NZDUSD OLD: No signal")

logger.info("\n" + "="*80)
logger.info("✅ SCAN COMPLETE!")
logger.info("="*80)
