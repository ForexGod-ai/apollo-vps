"""
Debug CHoCH Detection - Verify NZDUSD Daily CHoCH
"""

import MetaTrader5 as mt5
import pandas as pd
from loguru import logger

def check_nzdusd_choch():
    """
    Manual check pentru CHoCH pe NZDUSD Daily
    """
    if not mt5.initialize():
        logger.error("MT5 init failed")
        return
    
    try:
        # Get Daily data
        rates = mt5.copy_rates_from_pos("NZDUSD", mt5.TIMEFRAME_D1, 0, 50)
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        logger.info(f"\n📊 NZDUSD DAILY - Last 20 candles:")
        logger.info(f"{'Date':<12} {'High':<10} {'Low':<10} {'Close':<10}")
        logger.info("="*50)
        
        for i in range(-20, 0):
            row = df.iloc[i]
            logger.info(f"{row['time'].strftime('%Y-%m-%d'):<12} {row['high']:<10.5f} {row['low']:<10.5f} {row['close']:<10.5f}")
        
        # Manual CHoCH detection
        logger.info("\n🔍 ANALYZING STRUCTURE:")
        
        highs = df['high'].tail(30).values
        lows = df['low'].tail(30).values
        
        # Find recent swing highs/lows
        logger.info("\n📈 RECENT HIGHS (last 15):")
        for i in range(-15, 0):
            logger.info(f"   [{i:3d}] {highs[i]:.5f}")
        
        logger.info("\n📉 RECENT LOWS (last 15):")
        for i in range(-15, 0):
            logger.info(f"   [{i:3d}] {lows[i]:.5f}")
        
        # Check for CHoCH
        logger.info("\n🎯 LOOKING FOR CHOCH:")
        logger.info("   CHoCH = When price breaks previous swing high (bearish→bullish)")
        logger.info("         OR breaks previous swing low (bullish→bearish)")
        
        # Look for bullish CHoCH (break of Lower High in bearish trend)
        logger.info("\n   Checking for BULLISH CHoCH...")
        
        # Find if there was a bearish structure (LH + LL) followed by break
        for i in range(len(highs) - 5, len(highs)):
            current_high = highs[i]
            prev_highs = highs[max(0, i-10):i]
            
            if len(prev_highs) > 0:
                recent_lower_highs = [h for h in prev_highs if h < current_high]
                
                if len(recent_lower_highs) >= 3:
                    logger.info(f"   ✅ POSSIBLE BULLISH CHoCH at bar {i-len(highs)} ({df.iloc[i]['time'].strftime('%Y-%m-%d')})")
                    logger.info(f"      Price broke above {max(recent_lower_highs):.5f} reaching {current_high:.5f}")
                    logger.info(f"      Bars ago: {len(highs) - i}")
                    break
        else:
            logger.info("   ⚠️ No clear BULLISH CHoCH found in last 30 bars")
        
        # Check current structure (last 10 candles)
        logger.info("\n📊 CURRENT STRUCTURE (last 10 candles):")
        recent_highs = highs[-10:]
        recent_lows = lows[-10:]
        
        hh = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i] > recent_highs[i-1])
        hl = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i] > recent_lows[i-1])
        lh = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i] < recent_highs[i-1])
        ll = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i] < recent_lows[i-1])
        
        logger.info(f"   HH: {hh}, HL: {hl} (bullish)")
        logger.info(f"   LH: {lh}, LL: {ll} (bearish)")
        
        if hh >= 4 and hl >= 4:
            logger.info("\n   ✅ Current: BULLISH TREND (CONTINUITY)")
            logger.info("   📋 Strategy: Wait for pullback to HL in FVG")
        elif lh >= 4 and ll >= 4:
            logger.info("\n   ✅ Current: BEARISH TREND (CONTINUITY)")
        else:
            logger.info("\n   ⚠️ Current: MIXED/RANGING")
        
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    check_nzdusd_choch()
