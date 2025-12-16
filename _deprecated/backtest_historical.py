"""
Backtest Scanner on Historical BTCUSD Trades

User's successful trades:
1. Oct 31, 2025: BTCUSD trade (+16.65%)
2. Nov 11, 2025: BTCUSD trade (+11.20%)
3. Current: Dec 1, 2025: BTCUSD SHORT (R:R 1:4.99)

Will scan historical data to see if bot would have detected these setups
"""

from daily_scanner import MT5DataProvider
from smc_detector import SMCDetector
from loguru import logger
import pandas as pd
from datetime import datetime, timedelta

def backtest_historical_trades():
    logger.info("🔍 BACKTESTING HISTORICAL TRADES")
    logger.info("=" * 80)
    
    data_provider = MT5DataProvider()
    detector = SMCDetector()
    
    if not data_provider.connect():
        logger.error("❌ Failed to connect to MT5")
        return
    
    symbol = "BTCUSD"
    
    # Download maximum available historical data
    logger.info(f"\n📊 Downloading maximum historical data for {symbol}...")
    df_daily = data_provider.get_historical_data(symbol, "D1", 100)  # Try 100 days
    df_4h = data_provider.get_historical_data(symbol, "H4", 500)  # Try 500 4H candles
    
    if df_daily is None or df_4h is None:
        logger.error("❌ Failed to get historical data")
        data_provider.disconnect()
        return
    
    logger.info(f"✅ Downloaded {len(df_daily)} Daily candles")
    logger.info(f"✅ Downloaded {len(df_4h)} 4H candles")
    logger.info(f"\n📅 Date range:")
    logger.info(f"   Daily: {df_daily['time'].iloc[0]} to {df_daily['time'].iloc[-1]}")
    logger.info(f"   4H: {df_4h['time'].iloc[0]} to {df_4h['time'].iloc[-1]}")
    
    # TEST 1: Current trade (Dec 1, 2025)
    logger.info(f"\n{'='*80}")
    logger.info("TEST 1: Current Trade (Dec 1, 2025)")
    logger.info("="*80)
    
    setup_current = detector.scan_for_setup(symbol, df_daily, df_4h, priority=1)
    
    if setup_current:
        logger.info(f"✅ SETUP DETECTED!")
        logger.info(f"   Type: {setup_current.strategy_type.upper()}")
        logger.info(f"   Direction: {setup_current.daily_choch.direction.upper()}")
        logger.info(f"   Entry: {setup_current.entry_price:.2f}")
        logger.info(f"   SL: {setup_current.stop_loss:.2f}")
        logger.info(f"   TP: {setup_current.take_profit:.2f}")
        logger.info(f"   R:R: 1:{setup_current.risk_reward:.2f}")
    else:
        logger.warning("❌ No setup detected for current date")
    
    # TEST 2: Simulate Nov 11, 2025
    logger.info(f"\n{'='*80}")
    logger.info("TEST 2: Nov 11, 2025 Trade (+11.20%)")
    logger.info("="*80)
    
    # Find index for Nov 11 in daily data
    nov11_date = pd.Timestamp('2025-11-11')
    if nov11_date in df_daily['time'].values:
        nov11_idx = df_daily[df_daily['time'] == nov11_date].index[0]
        
        # Simulate data up to Nov 11
        df_daily_sim = df_daily.iloc[:nov11_idx + 1].copy()
        
        # Find corresponding 4H data
        nov11_4h_cutoff = df_4h[df_4h['time'] <= nov11_date]
        df_4h_sim = nov11_4h_cutoff.copy()
        
        logger.info(f"   Simulating with {len(df_daily_sim)} Daily + {len(df_4h_sim)} 4H candles")
        
        setup_nov11 = detector.scan_for_setup(symbol, df_daily_sim, df_4h_sim, priority=1)
        
        if setup_nov11:
            logger.info(f"✅ SETUP DETECTED!")
            logger.info(f"   Type: {setup_nov11.strategy_type.upper()}")
            logger.info(f"   Direction: {setup_nov11.daily_choch.direction.upper()}")
            logger.info(f"   Entry: {setup_nov11.entry_price:.2f}")
            logger.info(f"   SL: {setup_nov11.stop_loss:.2f}")
            logger.info(f"   TP: {setup_nov11.take_profit:.2f}")
            logger.info(f"   R:R: 1:{setup_nov11.risk_reward:.2f}")
        else:
            logger.warning("❌ No setup detected for Nov 11")
    else:
        logger.warning(f"⚠️ Nov 11 data not available in historical data")
    
    # TEST 3: Simulate Oct 31, 2025
    logger.info(f"\n{'='*80}")
    logger.info("TEST 3: Oct 31, 2025 Trade (+16.65%)")
    logger.info("="*80)
    
    oct31_date = pd.Timestamp('2025-10-31')
    if oct31_date in df_daily['time'].values:
        oct31_idx = df_daily[df_daily['time'] == oct31_date].index[0]
        
        df_daily_sim = df_daily.iloc[:oct31_idx + 1].copy()
        oct31_4h_cutoff = df_4h[df_4h['time'] <= oct31_date]
        df_4h_sim = oct31_4h_cutoff.copy()
        
        logger.info(f"   Simulating with {len(df_daily_sim)} Daily + {len(df_4h_sim)} 4H candles")
        
        setup_oct31 = detector.scan_for_setup(symbol, df_daily_sim, df_4h_sim, priority=1)
        
        if setup_oct31:
            logger.info(f"✅ SETUP DETECTED!")
            logger.info(f"   Type: {setup_oct31.strategy_type.upper()}")
            logger.info(f"   Direction: {setup_oct31.daily_choch.direction.upper()}")
            logger.info(f"   Entry: {setup_oct31.entry_price:.2f}")
            logger.info(f"   SL: {setup_oct31.stop_loss:.2f}")
            logger.info(f"   TP: {setup_oct31.take_profit:.2f}")
            logger.info(f"   R:R: 1:{setup_oct31.risk_reward:.2f}")
        else:
            logger.warning("❌ No setup detected for Oct 31")
    else:
        logger.warning(f"⚠️ Oct 31 data not available in historical data")
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("BACKTEST SUMMARY")
    logger.info("="*80)
    
    tests_passed = 0
    if setup_current:
        tests_passed += 1
    if 'setup_nov11' in locals() and setup_nov11:
        tests_passed += 1
    if 'setup_oct31' in locals() and setup_oct31:
        tests_passed += 1
    
    logger.info(f"✅ Setups detected: {tests_passed}/3")
    logger.info(f"\n{'='*80}")
    
    data_provider.disconnect()

if __name__ == "__main__":
    backtest_historical_trades()
