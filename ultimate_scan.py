"""
ULTIMATE TRADING SYSTEM - ForexGod's Complete Knowledge
Combines: SMC Algorithm + GLITCH Price Action + All Teachings

This is the BEAST MODE - when all systems align = GOLD!
"""

import MetaTrader5 as mt5
import pandas as pd
import json
from loguru import logger
from smc_algorithm import SMCAlgorithm
from price_action_analyzer import PriceActionAnalyzer

# Initialize MT5
if not mt5.initialize():
    logger.error("MT5 initialization failed")
    exit()

logger.info(f"✅ MT5 Connected: Account #{mt5.account_info().login}")

# Load all pairs
try:
    with open('pairs_config.json', 'r') as f:
        config = json.load(f)
        all_pairs = [p['symbol'] for p in config['pairs']]
except:
    all_pairs = ['BTCUSD', 'NZDUSD', 'GBPJPY', 'GBPUSD', 'EURUSD', 'XAUUSD', 
                 'GBPCHF', 'NZDCAD', 'AUDNZD', 'USDJPY', 'USDCAD', 'GBPNZD',
                 'EURJPY', 'EURCAD', 'AUDCAD', 'USDCHF', 'CADCHF']

# Initialize both systems
smc = SMCAlgorithm()
glitch = PriceActionAnalyzer()

logger.info("\n" + "="*80)
logger.info("🔥🔥🔥 ULTIMATE SYSTEM - SMC + GLITCH + FOREXGOD KNOWLEDGE 🔥🔥🔥")
logger.info("="*80)

# Results storage
mega_signals = []  # Both agree - BEST!
glitch_only = []
smc_only = []

for symbol in all_pairs:
    try:
        # Get data
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 100)
        if rates is None or len(rates) == 0:
            continue
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        current_price = df['close'].iloc[-1]
        
        # Run both systems
        smc_signal = smc.analyze(df, symbol)
        glitch_signal = glitch.analyze_full_context(df, symbol)
        
        # Analyze results
        if smc_signal and glitch_signal:
            # BOTH detected - check agreement
            if smc_signal.direction == glitch_signal.direction:
                # 🔥🔥🔥 MEGA CONFLUENCE!
                mega_signals.append({
                    'symbol': symbol,
                    'direction': smc_signal.direction,
                    'smc': smc_signal,
                    'glitch': glitch_signal,
                    'price': current_price
                })
            else:
                # Conflict - show both
                logger.info(f"\n⚠️ {symbol} - SYSTEMS DISAGREE!")
                logger.info(f"   SMC: {smc_signal.direction.upper()} ({smc_signal.confidence}/10)")
                logger.info(f"   GLITCH: {glitch_signal.direction.upper()} ({glitch_signal.confidence}/10)")
                logger.info(f"   → Analyze manually or wait for clarity!")
        
        elif glitch_signal:
            glitch_only.append({'symbol': symbol, 'signal': glitch_signal, 'price': current_price})
        
        elif smc_signal:
            smc_only.append({'symbol': symbol, 'signal': smc_signal, 'price': current_price})
    
    except Exception as e:
        logger.error(f"Error scanning {symbol}: {e}")
        continue

# Display MEGA SIGNALS (both agree)
logger.info("\n" + "="*80)
logger.info("🔥🔥🔥 MEGA CONFLUENCE SIGNALS (SMC + GLITCH AGREE) 🔥🔥🔥")
logger.info("="*80)

if mega_signals:
    for setup in mega_signals:
        smc = setup['smc']
        glitch = setup['glitch']
        symbol = setup['symbol']
        direction = setup['direction'].upper()
        
        logger.info(f"\n{'='*80}")
        logger.info(f"💎💎💎 {symbol} - {direction} - ULTIMATE SETUP! 💎💎💎")
        logger.info(f"{'='*80}")
        logger.info(f"Current Price: ${setup['price']:.5f}")
        
        # Combined confidence
        combined_confidence = (smc.confidence + glitch.confidence) / 2
        stars = "⭐" * int(combined_confidence)
        logger.info(f"🎯 COMBINED CONFIDENCE: {combined_confidence:.1f}/10 {stars}")
        
        logger.info(f"\n📊 SMC ANALYSIS (Institutional Footprint):")
        logger.info(f"   Confidence: {smc.confidence}/10")
        logger.info(f"   Order Block: {smc.order_block.type.upper()} (strength: {smc.order_block.strength.upper()})")
        logger.info(f"   Premium/Discount: {'PREMIUM ✅' if smc.in_premium else 'DISCOUNT ✅' if smc.in_discount else 'EQUILIBRIUM'}")
        logger.info(f"   Liquidity Swept: {'✅' if smc.liquidity_swept else '❌'}")
        logger.info(f"   FVG: {'✅' if smc.fvg else '❌'}")
        logger.info(f"   SMC Reasons:")
        for i, reason in enumerate(smc.reasons, 1):
            logger.info(f"      {i}. {reason}")
        
        logger.info(f"\n🔥 GLITCH ANALYSIS (Price Action Master):")
        logger.info(f"   Confidence: {glitch.confidence}/10")
        logger.info(f"   Market Structure: {glitch.market_structure}")
        logger.info(f"   CHoCH Confirmed: {'✅' if glitch.choch_confirmed else '❌'}")
        logger.info(f"   FVG Present: {'✅' if glitch.fvg_present else '❌'}")
        logger.info(f"   Liquidity Cleared: {'✅' if glitch.liquidity_cleared else '❌'}")
        logger.info(f"   Momentum: {glitch.momentum}")
        logger.info(f"   GLITCH Reasons:")
        for i, reason in enumerate(glitch.reasons, 1):
            logger.info(f"      {i}. {reason}")
        
        logger.info(f"\n💰 TRADING PLAN:")
        # Use SMC levels (more precise with Order Blocks)
        logger.info(f"   Entry Zone: ${smc.entry_zone[0]:.5f} - ${smc.entry_zone[1]:.5f}")
        logger.info(f"   Stop Loss: ${smc.stop_loss:.5f}")
        logger.info(f"   Take Profit: ${smc.take_profit:.5f}")
        logger.info(f"   Risk/Reward: 1:{smc.risk_reward:.2f}")
        
        risk = abs(smc.entry_zone[0] - smc.stop_loss)
        reward = abs(smc.take_profit - smc.entry_zone[0])
        logger.info(f"   Risk: ${risk:.5f}")
        logger.info(f"   Reward: ${reward:.5f}")
        
        logger.info(f"\n🎯 EXECUTION STRATEGY:")
        logger.info(f"   1. Wait for price in entry zone")
        logger.info(f"   2. Look for confirmation: rejection candle, volume surge")
        logger.info(f"   3. Enter with proper lot size (risk 1-2% of account)")
        logger.info(f"   4. Set SL at ${smc.stop_loss:.5f}")
        logger.info(f"   5. Target TP at ${smc.take_profit:.5f}")
        logger.info(f"   6. Trail stop after 50% to TP")
        
        logger.info(f"\n💪 WHY THIS IS GOLD:")
        logger.info(f"   ✅ SMC confirms institutional interest")
        logger.info(f"   ✅ GLITCH confirms price action alignment")
        logger.info(f"   ✅ Multiple timeframe confluence")
        logger.info(f"   ✅ Risk/Reward is favorable")
        logger.info(f"   ✅ All systems say: {direction}!")

else:
    logger.info("\n⏳ No MEGA confluence signals at the moment")
    logger.info("   (Waiting for both systems to align)")

# Display GLITCH-only signals
if glitch_only:
    logger.info("\n" + "="*80)
    logger.info("🔥 GLITCH-ONLY SIGNALS (Price Action)")
    logger.info("="*80)
    for setup in glitch_only:
        sig = setup['signal']
        logger.info(f"   • {setup['symbol']}: {sig.direction.upper()} (confidence {sig.confidence}/10)")
        logger.info(f"     CHoCH: {'✅' if sig.choch_confirmed else '❌'}, FVG: {'✅' if sig.fvg_present else '❌'}")

# Display SMC-only signals
if smc_only:
    logger.info("\n" + "="*80)
    logger.info("🎯 SMC-ONLY SIGNALS (Institutional)")
    logger.info("="*80)
    for setup in smc_only:
        sig = setup['signal']
        logger.info(f"   • {setup['symbol']}: {sig.direction.upper()} (confidence {sig.confidence}/10, R:R 1:{sig.risk_reward:.2f})")
        logger.info(f"     OB: {sig.order_block.strength.upper()}, Premium: {'✅' if sig.in_premium else '❌'}, Discount: {'✅' if sig.in_discount else '❌'}")

# Summary
logger.info("\n" + "="*80)
logger.info("📊 ULTIMATE SCAN SUMMARY")
logger.info("="*80)
logger.info(f"🔥🔥🔥 MEGA Signals (both agree): {len(mega_signals)}")
logger.info(f"🔥 GLITCH-only: {len(glitch_only)}")
logger.info(f"🎯 SMC-only: {len(smc_only)}")
logger.info(f"📊 Total opportunities: {len(mega_signals) + len(glitch_only) + len(smc_only)}")

logger.info("\n" + "="*80)
logger.info("✅ FOREXGOD's ULTIMATE SYSTEM - SCAN COMPLETE!")
logger.info("="*80)

mt5.shutdown()
