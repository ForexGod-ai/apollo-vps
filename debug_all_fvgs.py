"""
Debug All FVGs - Find ALL FVG zones on BTCUSD Daily
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd
from smc_detector import SMCDetector
from loguru import logger

def debug_all_fvgs():
    # Initialize MT5
    if not mt5.initialize():
        logger.error("MT5 initialization failed")
        return
    
    logger.info("🔍 Finding ALL FVGs on BTCUSD")
    logger.info("=" * 80)
    
    symbol = "BTCUSD"
    
    # Get data
    daily_candles = 50
    rates_daily = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, daily_candles)
    
    if rates_daily is None or len(rates_daily) == 0:
        logger.error(f"Failed to get Daily data for {symbol}")
        mt5.shutdown()
        return
    
    df_daily = pd.DataFrame(rates_daily)
    df_daily['time'] = pd.to_datetime(df_daily['time'], unit='s')
    
    logger.info(f"✅ MT5 Connected: Account #{mt5.account_info().login}, Balance: ${mt5.account_info().balance:.2f}")
    logger.info(f"✅ Downloaded {len(df_daily)} candles for {symbol} (D1)")
    logger.info(f"\n📊 Daily Data: {len(df_daily)} candles")
    logger.info(f"\n📈 Last 5 Daily Candles:")
    for i in range(-5, 0):
        c = df_daily.iloc[i]
        logger.info(f"   {c['time']} - O:{c['open']:.2f} H:{c['high']:.2f} L:{c['low']:.2f} C:{c['close']:.2f}")
    
    # Initialize detector
    detector = SMCDetector()
    
    # Find ALL CHoCHs
    chochs = detector.detect_choch(df_daily)
    
    logger.info(f"\n📊 Found {len(chochs)} Daily CHoCH:")
    for choch in chochs:
        logger.info(f"\n   CHoCH #{choch.index}:")
        logger.info(f"      Direction: {choch.direction.upper()}")
        logger.info(f"      Break Price: {choch.break_price:.2f}")
        logger.info(f"      Time: {choch.candle_time}")
        
        # Find FVG for this CHoCH
        current_price = df_daily['close'].iloc[-1]
        fvg = detector.detect_fvg(df_daily, choch, current_price)
        
        if fvg:
            logger.info(f"\n      ✅ FVG Found:")
            logger.info(f"         Top: {fvg.top:.2f}")
            logger.info(f"         Middle: {fvg.middle:.2f}")
            logger.info(f"         Bottom: {fvg.bottom:.2f}")
            logger.info(f"         Size: {fvg.top - fvg.bottom:.2f} ({(fvg.top - fvg.bottom) / fvg.bottom * 100:.2f}%)")
            logger.info(f"         Time: {fvg.candle_time}")
            
            # Check if filled
            is_filled = detector.is_fvg_filled(df_daily, fvg, len(df_daily) - 1)
            logger.info(f"         Filled: {'Yes ❌' if is_filled else 'No ✅'}")
            
            # Check current price vs FVG
            current_price = df_daily['close'].iloc[-1]
            logger.info(f"         Current Price: {current_price:.2f}")
            
            if fvg.direction == 'bearish':
                if current_price > fvg.top:
                    logger.info(f"         Price Position: ABOVE FVG ⬆️")
                elif current_price < fvg.bottom:
                    logger.info(f"         Price Position: BELOW FVG ⬇️")
                else:
                    logger.info(f"         Price Position: INSIDE FVG 🎯")
        else:
            logger.info(f"\n      ❌ No FVG found")
    
    mt5.shutdown()
    logger.info("🔌 MT5 disconnected")

if __name__ == "__main__":
    debug_all_fvgs()
