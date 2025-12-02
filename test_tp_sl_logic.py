"""
Test TP/SL calculation logic with real market data
"""
import sys
from datetime import datetime
from loguru import logger
import MetaTrader5 as mt5

from daily_scanner import MT5DataProvider
from smc_detector import SMCDetector

logger.remove()
logger.add(sys.stdout, colorize=True, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")


def test_tp_sl_calculation():
    """Test TP/SL calculation on GBPUSD"""
    
    logger.info("=" * 80)
    logger.info("🧪 Testing TP/SL Calculation Logic")
    logger.info("=" * 80)
    
    # Initialize
    data_provider = MT5DataProvider()
    detector = SMCDetector()
    
    if not data_provider.connect():
        logger.error("❌ Failed to connect to MT5")
        return
    
    symbol = "GBPUSD"
    logger.info(f"\n📊 Analyzing {symbol}...")
    
    # Get data
    df_daily = data_provider.get_historical_data(symbol, "D1", 50)
    df_4h = data_provider.get_historical_data(symbol, "H4", 200)
    
    if df_daily is None or df_4h is None:
        logger.error(f"❌ Failed to get data for {symbol}")
        return
    
    logger.info(f"✅ Daily data: {len(df_daily)} candles")
    logger.info(f"✅ 4H data: {len(df_4h)} candles")
    
    # Detect CHoCH on Daily
    daily_chochs = detector.detect_choch(df_daily)
    logger.info(f"\n📈 Daily CHoCH detected: {len(daily_chochs)}")
    
    if daily_chochs:
        latest_choch = daily_chochs[-1]
        logger.info(f"   Direction: {latest_choch.direction.upper()}")
        logger.info(f"   Break Price: {latest_choch.break_price:.5f}")
        logger.info(f"   Time: {latest_choch.candle_time}")
        
        # Detect FVG
        fvg = detector.detect_fvg(df_daily, latest_choch)
        
        if fvg:
            logger.info(f"\n📦 FVG Found:")
            logger.info(f"   Top: {fvg.top:.5f}")
            logger.info(f"   Middle: {fvg.middle:.5f}")
            logger.info(f"   Bottom: {fvg.bottom:.5f}")
            logger.info(f"   Direction: {fvg.direction.upper()}")
            
            # Detect 4H CHoCH
            h4_chochs = detector.detect_choch(df_4h)
            logger.info(f"\n📊 4H CHoCH detected: {len(h4_chochs)}")
            
            if h4_chochs:
                latest_h4_choch = h4_chochs[-1]
                logger.info(f"   Direction: {latest_h4_choch.direction.upper()}")
                logger.info(f"   Break Price: {latest_h4_choch.break_price:.5f}")
                
                # Calculate TP/SL
                logger.info(f"\n🎯 Calculating Entry, SL, TP...")
                
                entry, sl, tp = detector.calculate_entry_sl_tp(
                    fvg, 
                    latest_h4_choch, 
                    df_4h,
                    df_daily
                )
                
                current_price = df_4h['close'].iloc[-1]
                
                logger.info(f"\n📍 TRADE SETUP:")
                logger.info(f"   Symbol: {symbol}")
                logger.info(f"   Direction: {'LONG' if latest_h4_choch.direction == 'bullish' else 'SHORT'}")
                logger.info(f"   Current Price: {current_price:.5f}")
                logger.info(f"   Entry: {entry:.5f}")
                logger.info(f"   Stop Loss: {sl:.5f}")
                logger.info(f"   Take Profit: {tp:.5f}")
                
                # Calculate pips and R:R
                if latest_h4_choch.direction == 'bullish':
                    sl_pips = abs(entry - sl) * 10000
                    tp_pips = abs(tp - entry) * 10000
                else:
                    sl_pips = abs(sl - entry) * 10000
                    tp_pips = abs(entry - tp) * 10000
                
                risk_reward = tp_pips / sl_pips if sl_pips > 0 else 0
                
                logger.info(f"\n📊 RISK MANAGEMENT:")
                logger.info(f"   SL Distance: {sl_pips:.1f} pips")
                logger.info(f"   TP Distance: {tp_pips:.1f} pips")
                logger.info(f"   Risk:Reward: 1:{risk_reward:.2f}")
                
                # Show logic
                logger.info(f"\n🔍 LOGIC EXPLANATION:")
                if latest_h4_choch.direction == 'bullish':
                    logger.info(f"   ✅ LONG Trade")
                    logger.info(f"   📍 Entry: FVG Middle = {entry:.5f}")
                    logger.info(f"   🛑 SL: Last Low on 4H (last 20 candles) = {sl:.5f}")
                    logger.info(f"   🎯 TP: Last High on Daily (last 10 days) = {tp:.5f}")
                else:
                    logger.info(f"   ❌ SHORT Trade")
                    logger.info(f"   📍 Entry: FVG Middle = {entry:.5f}")
                    logger.info(f"   🛑 SL: Last High on 4H (last 20 candles) = {sl:.5f}")
                    logger.info(f"   🎯 TP: Last Low on Daily (last 10 days) = {tp:.5f}")
                
                # Show recent highs/lows for verification
                logger.info(f"\n📈 VERIFICATION DATA:")
                if latest_h4_choch.direction == 'bullish':
                    recent_lows_4h = df_4h['low'].iloc[-20:]
                    recent_highs_daily = df_daily['high'].iloc[-10:]
                    logger.info(f"   4H Recent Lows (last 20): min={recent_lows_4h.min():.5f}, max={recent_lows_4h.max():.5f}")
                    logger.info(f"   Daily Recent Highs (last 10): min={recent_highs_daily.min():.5f}, max={recent_highs_daily.max():.5f}")
                else:
                    recent_highs_4h = df_4h['high'].iloc[-20:]
                    recent_lows_daily = df_daily['low'].iloc[-10:]
                    logger.info(f"   4H Recent Highs (last 20): min={recent_highs_4h.min():.5f}, max={recent_highs_4h.max():.5f}")
                    logger.info(f"   Daily Recent Lows (last 10): min={recent_lows_daily.min():.5f}, max={recent_lows_daily.max():.5f}")
            
            else:
                logger.warning("⚠️ No 4H CHoCH detected")
        else:
            logger.warning("⚠️ No FVG detected after Daily CHoCH")
    else:
        logger.warning("⚠️ No Daily CHoCH detected")
    
    data_provider.disconnect()
    logger.info("\n" + "=" * 80)
    logger.info("✅ Test Complete")


if __name__ == "__main__":
    test_tp_sl_calculation()
