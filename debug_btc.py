"""
Debug BTC setup detection in detail
"""
import sys
from loguru import logger
from daily_scanner import MT5DataProvider
from smc_detector import SMCDetector

logger.remove()
logger.add(sys.stdout, colorize=True, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")


def debug_btc():
    logger.info("🔍 Debugging BTCUSD Setup")
    logger.info("=" * 80)
    
    dp = MT5DataProvider()
    detector = SMCDetector()
    
    if not dp.connect():
        return
    
    symbol = "BTCUSD"
    df_daily = dp.get_historical_data(symbol, "D1", 50)
    df_4h = dp.get_historical_data(symbol, "H4", 200)
    
    logger.info(f"\n📊 Daily Data: {len(df_daily)} candles")
    logger.info(f"📊 4H Data: {len(df_4h)} candles")
    
    # Show recent daily candles
    logger.info("\n📈 Last 5 Daily Candles:")
    for i in range(-5, 0):
        row = df_daily.iloc[i]
        logger.info(f"   {row['time']} - O:{row['open']:.2f} H:{row['high']:.2f} L:{row['low']:.2f} C:{row['close']:.2f}")
    
    # Step 1: Detect Daily CHoCH
    logger.info("\n📊 Step 1: Daily CHoCH Detection")
    daily_chochs = detector.detect_choch(df_daily)
    logger.info(f"   Total Daily CHoCH: {len(daily_chochs)}")
    
    if daily_chochs:
        logger.info("\n   Last 3 Daily CHoCH:")
        for choch in daily_chochs[-3:]:
            logger.info(f"      • {choch.direction.upper()} @ {choch.break_price:.2f} on {choch.candle_time}")
        
        latest_choch = daily_chochs[-1]
        logger.info(f"\n   ✅ Latest Daily CHoCH: {latest_choch.direction.upper()}")
        logger.info(f"      Break Price: {latest_choch.break_price:.2f}")
        logger.info(f"      Previous Trend: {latest_choch.previous_trend}")
        logger.info(f"      Time: {latest_choch.candle_time}")
        
        # Detect strategy type
        strategy = detector.detect_strategy_type(df_daily, latest_choch)
        logger.info(f"      Strategy Type: {strategy.upper()}")
        
        # Step 2: Detect FVG
        logger.info(f"\n📦 Step 2: FVG Detection")
        current_price = df_daily['close'].iloc[-1]
        fvg = detector.detect_fvg(df_daily, latest_choch, current_price)
        
        if fvg:
            logger.info(f"   ✅ FVG Found: {fvg.direction.upper()}")
            logger.info(f"      Top: {fvg.top:.2f}")
            logger.info(f"      Middle: {fvg.middle:.2f}")
            logger.info(f"      Bottom: {fvg.bottom:.2f}")
            logger.info(f"      Size: {fvg.top - fvg.bottom:.2f} ({((fvg.top - fvg.bottom) / fvg.bottom * 100):.2f}%)")
            
            # Check if filled
            is_filled = detector.is_fvg_filled(df_daily, fvg, len(df_daily) - 1)
            logger.info(f"      Filled: {'Yes ❌' if is_filled else 'No ✅'}")
            
            if not is_filled:
                # Check current price
                current_price = df_daily['close'].iloc[-1]
                in_fvg = detector.is_price_in_fvg(current_price, fvg)
                
                logger.info(f"\n📍 Step 3: Price Position")
                logger.info(f"   Current Daily Close: {current_price:.2f}")
                logger.info(f"   In FVG: {'Yes ✅' if in_fvg else 'No ❌'}")
                
                if not in_fvg:
                    if current_price > fvg.top:
                        logger.info(f"   Price is ABOVE FVG by {current_price - fvg.top:.2f}")
                    else:
                        logger.info(f"   Price is BELOW FVG by {fvg.bottom - current_price:.2f}")
                
                # Check 4H CHoCH
                logger.info(f"\n🔍 Step 4: 4H CHoCH Detection")
                h4_chochs = detector.detect_choch(df_4h)
                logger.info(f"   Total 4H CHoCH: {len(h4_chochs)}")
                
                if h4_chochs:
                    logger.info("\n   Last 5 4H CHoCH:")
                    for choch in h4_chochs[-5:]:
                        h4_price = df_4h['close'].iloc[choch.index]
                        in_zone = detector.is_price_in_fvg(h4_price, fvg)
                        logger.info(f"      • {choch.direction.upper()} @ {choch.break_price:.2f} - Price: {h4_price:.2f} - In FVG: {'✅' if in_zone else '❌'}")
                    
                    # Check for opposite direction
                    expected_dir = 'bearish' if fvg.direction == 'bullish' else 'bullish'
                    logger.info(f"\n   Looking for: {expected_dir.upper()} CHoCH (opposite of {fvg.direction.upper()} FVG)")
                    
                    found_opposite = False
                    for choch in reversed(h4_chochs):
                        if choch.direction == expected_dir:
                            h4_price = df_4h['close'].iloc[choch.index]
                            in_zone = detector.is_price_in_fvg(h4_price, fvg)
                            
                            if in_zone:
                                logger.info(f"   ✅ Found {expected_dir.upper()} CHoCH in FVG!")
                                logger.info(f"      Break Price: {choch.break_price:.2f}")
                                logger.info(f"      Time: {choch.candle_time}")
                                
                                # Check microtrend
                                has_micro = detector.detect_microtrend(df_4h, fvg, choch.index)
                                logger.info(f"      Microtrend: {'✅' if has_micro else '❌'}")
                                
                                if has_micro:
                                    # Calculate TP/SL
                                    entry, sl, tp = detector.calculate_entry_sl_tp(fvg, choch, df_4h, df_daily)
                                    
                                    trade_dir = "LONG" if choch.direction == 'bullish' else "SHORT"
                                    
                                    if trade_dir == "LONG":
                                        sl_pips = abs(entry - sl)
                                        tp_pips = abs(tp - entry)
                                    else:
                                        sl_pips = abs(sl - entry)
                                        tp_pips = abs(entry - tp)
                                    
                                    rr = tp_pips / sl_pips if sl_pips > 0 else 0
                                    
                                    logger.info(f"\n🎯 SETUP DETAILS:")
                                    logger.info(f"   Direction: {trade_dir}")
                                    logger.info(f"   Entry: {entry:.2f}")
                                    logger.info(f"   SL: {sl:.2f} ({sl_pips:.2f} pips)")
                                    logger.info(f"   TP: {tp:.2f} ({tp_pips:.2f} pips)")
                                    logger.info(f"   R:R: 1:{rr:.2f}")
                                    
                                    if rr < 1.5:
                                        logger.warning(f"   ❌ R:R too low (minimum 1.5)")
                                    else:
                                        logger.info(f"   ✅ Valid setup!")
                                
                                found_opposite = True
                                break
                    
                    if not found_opposite:
                        logger.warning(f"   ❌ No {expected_dir.upper()} CHoCH found inside FVG")
        else:
            logger.warning("   ❌ No FVG detected after Daily CHoCH")
    else:
        logger.warning("   ❌ No Daily CHoCH detected")
    
    dp.disconnect()


if __name__ == "__main__":
    debug_btc()
