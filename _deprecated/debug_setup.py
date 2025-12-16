"""
Debug GBPUSD setup detection step by step
"""
import sys
from loguru import logger
from daily_scanner import MT5DataProvider, DailyScanner
from smc_detector import SMCDetector

logger.remove()
logger.add(sys.stdout, colorize=True, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")


def debug_setup():
    logger.info("🔍 Debugging GBPUSD Setup Detection")
    logger.info("=" * 80)
    
    dp = MT5DataProvider()
    detector = SMCDetector()
    
    if not dp.connect():
        return
    
    symbol = "GBPUSD"
    df_daily = dp.get_historical_data(symbol, "D1", 50)
    df_4h = dp.get_historical_data(symbol, "H4", 200)
    
    # Step 1: Daily CHoCH
    logger.info("\n📊 Step 1: Detect Daily CHoCH")
    daily_chochs = detector.detect_choch(df_daily)
    logger.info(f"   Found {len(daily_chochs)} Daily CHoCH")
    
    if not daily_chochs:
        logger.error("   ❌ STOP: No Daily CHoCH")
        dp.disconnect()
        return
    
    latest_choch = daily_chochs[-1]
    logger.info(f"   ✅ Latest: {latest_choch.direction.upper()} @ {latest_choch.break_price:.5f}")
    
    # Step 2: FVG
    logger.info("\n📦 Step 2: Detect FVG after CHoCH")
    fvg = detector.detect_fvg(df_daily, latest_choch)
    
    if not fvg:
        logger.error("   ❌ STOP: No FVG found")
        dp.disconnect()
        return
    
    logger.info(f"   ✅ FVG: {fvg.direction.upper()}")
    logger.info(f"      Top: {fvg.top:.5f}")
    logger.info(f"      Mid: {fvg.middle:.5f}")
    logger.info(f"      Bot: {fvg.bottom:.5f}")
    
    # Step 3: Check if FVG filled
    logger.info("\n🔄 Step 3: Check if FVG is filled")
    is_filled = detector.is_fvg_filled(df_daily, fvg, len(df_daily) - 1)
    logger.info(f"   {'❌ STOP: FVG is filled' if is_filled else '✅ FVG is valid (not filled)'}")
    
    if is_filled:
        dp.disconnect()
        return
    
    # Step 4: Check if price in FVG
    logger.info("\n📍 Step 4: Check if price is in FVG")
    current_price = df_daily['close'].iloc[-1]
    in_fvg = detector.is_price_in_fvg(current_price, fvg)
    logger.info(f"   Current Daily Close: {current_price:.5f}")
    logger.info(f"   {'✅ Price IS in FVG' if in_fvg else '❌ STOP: Price NOT in FVG'}")
    
    if not in_fvg:
        logger.info(f"      Distance to FVG bottom: {(current_price - fvg.bottom):.5f}")
        logger.info(f"      Distance to FVG top: {(fvg.top - current_price):.5f}")
        dp.disconnect()
        return
    
    # Step 5: Find opposite 4H CHoCH
    logger.info("\n🔍 Step 5: Find opposite 4H CHoCH inside FVG")
    h4_chochs = detector.detect_choch(df_4h)
    logger.info(f"   Total 4H CHoCH: {len(h4_chochs)}")
    
    expected_direction = 'bearish' if fvg.direction == 'bullish' else 'bullish'
    logger.info(f"   Looking for: {expected_direction.upper()} (opposite of {fvg.direction.upper()})")
    
    valid_h4_choch = None
    candidates = []
    
    for h4_choch in reversed(h4_chochs):
        if h4_choch.direction == expected_direction:
            h4_price = df_4h['close'].iloc[h4_choch.index]
            in_zone = detector.is_price_in_fvg(h4_price, fvg)
            candidates.append({
                'direction': h4_choch.direction,
                'price': h4_price,
                'in_fvg': in_zone,
                'choch': h4_choch
            })
            
            if in_zone:
                # Check microtrend
                has_microtrend = detector.detect_microtrend(df_4h, fvg, h4_choch.index)
                if has_microtrend:
                    valid_h4_choch = h4_choch
                    logger.info(f"   ✅ Valid 4H CHoCH found!")
                    logger.info(f"      Direction: {h4_choch.direction.upper()}")
                    logger.info(f"      Price: {h4_price:.5f}")
                    logger.info(f"      Microtrend: ✅")
                    break
    
    if not valid_h4_choch:
        logger.error("   ❌ STOP: No valid 4H CHoCH inside FVG with microtrend")
        logger.info(f"\n   Candidates found: {len(candidates)}")
        for i, c in enumerate(candidates[:5]):
            logger.info(f"      {i+1}. {c['direction'].upper()} @ {c['price']:.5f} - In FVG: {c['in_fvg']}")
        dp.disconnect()
        return
    
    # Step 6: Calculate TP/SL
    logger.info("\n🎯 Step 6: Calculate Entry, SL, TP")
    entry, sl, tp = detector.calculate_entry_sl_tp(fvg, valid_h4_choch, df_4h, df_daily)
    
    trade_dir = "LONG" if valid_h4_choch.direction == 'bullish' else "SHORT"
    logger.info(f"   Trade: {trade_dir}")
    logger.info(f"   Entry: {entry:.5f}")
    logger.info(f"   SL: {sl:.5f}")
    logger.info(f"   TP: {tp:.5f}")
    
    if trade_dir == "LONG":
        sl_pips = abs(entry - sl) * 10000
        tp_pips = abs(tp - entry) * 10000
    else:
        sl_pips = abs(sl - entry) * 10000
        tp_pips = abs(entry - tp) * 10000
    
    rr = tp_pips / sl_pips if sl_pips > 0 else 0
    logger.info(f"\n   SL: {sl_pips:.1f} pips")
    logger.info(f"   TP: {tp_pips:.1f} pips")
    logger.info(f"   R:R: 1:{rr:.2f}")
    
    if rr < 1.5:
        logger.warning(f"   ❌ STOP: R:R {rr:.2f} is below minimum 1.5")
    else:
        logger.info(f"   ✅ Valid setup! R:R is good!")
    
    dp.disconnect()


if __name__ == "__main__":
    debug_setup()
