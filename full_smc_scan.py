"""
Full SMC scan on all pairs - Display results only (no Telegram)
Testing for BTCUSD, NZDUSD, GBPJPY and others
"""

import MetaTrader5 as mt5
import pandas as pd
import json
from loguru import logger
from smc_algorithm import SMCAlgorithm

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
                 'GBPCHF', 'NZDCAD', 'AUDNZD', 'USDJPY', 'USDCAD', 'GBPNZD']

# Initialize SMC
smc = SMCAlgorithm()

logger.info("\n" + "="*80)
logger.info("🎯 SMC ALGORITHM - FULL MARKET SCAN")
logger.info("="*80)
logger.info(f"Scanning {len(all_pairs)} pairs...")

found_signals = []

for symbol in all_pairs:
    try:
        # Get data
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 100)
        if rates is None or len(rates) == 0:
            continue
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        current_price = df['close'].iloc[-1]
        
        # Run SMC analysis
        signal = smc.analyze(df, symbol)
        
        if signal:
            found_signals.append(signal)
            logger.info(f"\n{'='*80}")
            logger.info(f"🔥 {symbol} - SMC SIGNAL DETECTED!")
            logger.info(f"{'='*80}")
            logger.info(f"Current Price: ${current_price:.5f}")
            logger.info(f"Direction: {signal.direction.upper()}")
            logger.info(f"Confidence: {signal.confidence}/10 {'⭐' * signal.confidence}")
            
            logger.info(f"\n📊 ORDER BLOCK:")
            logger.info(f"   Type: {signal.order_block.type.upper()}")
            logger.info(f"   Strength: {signal.order_block.strength.upper()}")
            logger.info(f"   Zone: ${signal.order_block.bottom:.5f} - ${signal.order_block.top:.5f}")
            logger.info(f"   Body: ${signal.order_block.body_bottom:.5f} - ${signal.order_block.body_top:.5f}")
            
            logger.info(f"\n📈 MARKET ANALYSIS:")
            logger.info(f"   Structure: {signal.market_structure}")
            logger.info(f"   In Premium: {'✅' if signal.in_premium else '❌'}")
            logger.info(f"   In Discount: {'✅' if signal.in_discount else '❌'}")
            logger.info(f"   Liquidity Swept: {'✅' if signal.liquidity_swept else '❌'}")
            if signal.fvg:
                logger.info(f"   FVG Present: ✅ (${signal.fvg.bottom:.5f} - ${signal.fvg.top:.5f})")
            else:
                logger.info(f"   FVG Present: ❌")
            
            logger.info(f"\n💰 TRADING SETUP:")
            logger.info(f"   Entry Zone: ${signal.entry_zone[0]:.5f} - ${signal.entry_zone[1]:.5f}")
            logger.info(f"   Stop Loss: ${signal.stop_loss:.5f}")
            logger.info(f"   Take Profit: ${signal.take_profit:.5f}")
            logger.info(f"   Risk/Reward: 1:{signal.risk_reward:.2f}")
            
            risk = abs(signal.entry_zone[0] - signal.stop_loss)
            reward = abs(signal.take_profit - signal.entry_zone[0])
            logger.info(f"   Risk: ${risk:.5f}")
            logger.info(f"   Reward: ${reward:.5f}")
            
            logger.info(f"\n✅ CONFLUENCE REASONS ({len(signal.reasons)}):")
            for i, reason in enumerate(signal.reasons, 1):
                logger.info(f"   {i}. {reason}")
    
    except Exception as e:
        logger.error(f"Error scanning {symbol}: {e}")
        continue

# Summary
logger.info(f"\n{'='*80}")
logger.info(f"📊 SCAN SUMMARY")
logger.info(f"{'='*80}")
logger.info(f"Total pairs scanned: {len(all_pairs)}")
logger.info(f"Signals found: {len(found_signals)}")

if found_signals:
    logger.info(f"\n🔥 DETECTED SETUPS:")
    for sig in found_signals:
        logger.info(f"   • {sig.symbol}: {sig.direction.upper()} (confidence {sig.confidence}/10, R:R 1:{sig.risk_reward:.2f})")
else:
    logger.info(f"\n⏳ No high-quality SMC setups found at the moment")
    logger.info(f"   SMC Algorithm is VERY selective - looking for institutional footprints only!")

# Check specific pairs user mentioned
logger.info(f"\n🔍 SPECIFIC PAIRS CHECK:")
watchlist = ['BTCUSD', 'NZDUSD', 'GBPJPY']
for symbol in watchlist:
    found = [s for s in found_signals if s.symbol == symbol]
    if found:
        logger.info(f"   {symbol}: ✅ SIGNAL FOUND ({found[0].direction.upper()} {found[0].confidence}/10)")
    else:
        logger.info(f"   {symbol}: ⏳ No signal (waiting for better setup)")

logger.info(f"\n{'='*80}")
logger.info("✅ SCAN COMPLETE")
logger.info("="*80)

mt5.shutdown()
