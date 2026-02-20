#!/usr/bin/env python3
"""
🎯 BTCUSD ELITE SCAN - V3.5 Order Blocks + FVG Magnets
Post-diagnostic scan pentru setup-uri instituționale BTCUSD

Detectează:
- CHoCH 1H (body closure confirmation)
- Order Blocks (OB scoring 1-10)
- FVG gaps (>0.10% threshold)
- FVG Magnets (zone de întoarcere)
- Reversal vs Continuation setup
- AI Confidence Score
"""
import sys
from loguru import logger
from daily_scanner import DailyScanner
from smc_detector import SMCDetector
from strategy_optimizer import StrategyOptimizer
import pandas as pd
import json
from datetime import datetime

logger.remove()
logger.add(sys.stdout, format='<level>{message}</level>', colorize=True)


def analyze_btcusd_elite():
    """
    🔍 BTCUSD Elite Scan cu V3.5 Order Blocks
    """
    print("\n" + "="*80)
    print("🎯 BTCUSD ELITE SCAN - V3.5 ORDER BLOCKS + FVG MAGNETS")
    print("="*80)
    print()
    
    scanner = DailyScanner()
    smc = SMCDetector()
    
    symbol = "BTCUSD"
    
    # ==================== STEP 1: DATA DOWNLOAD ====================
    logger.info("📥 Step 1/8: Downloading BTCUSD data...")
    
    # V3.5 Elite settings: 100 Daily, 200 4H, 300 1H
    df_daily = scanner.data_provider.get_historical_data(symbol, 'D1', 100)
    df_4h = scanner.data_provider.get_historical_data(symbol, 'H4', 200)
    df_1h = scanner.data_provider.get_historical_data(symbol, 'H1', 300)
    
    if df_daily is None or df_4h is None or df_1h is None:
        logger.error("❌ Failed to download data!")
        return None
    
    logger.success(f"✅ Data downloaded: {len(df_daily)} Daily, {len(df_4h)} 4H, {len(df_1h)} 1H bars")
    
    # Current price
    current_price = df_daily['close'].iloc[-1]
    logger.info(f"💰 Current BTCUSD: ${current_price:,.2f}")
    
    # Recent price action
    recent_high = df_daily['high'].tail(20).max()
    recent_low = df_daily['low'].tail(20).min()
    drop_pct = ((recent_high - current_price) / recent_high * 100)
    recovery_pct = ((current_price - recent_low) / recent_low * 100)
    
    logger.info(f"📊 Recent High: ${recent_high:,.0f} | Low: ${recent_low:,.0f}")
    logger.info(f"📉 Drop from High: {drop_pct:.1f}% | Recovery from Low: {recovery_pct:.1f}%")
    print()
    
    # ==================== STEP 2: CHoCH DETECTION (1H) ====================
    logger.info("📊 Step 2/8: Detecting CHoCH on 1H...")
    
    chochs_1h = smc.detect_choch(df_1h)
    
    if chochs_1h:
        latest_choch_1h = chochs_1h[-1]
        logger.success(f"✅ CHoCH 1H detected: {latest_choch_1h.direction.upper()} at ${latest_choch_1h.break_price:,.2f}")
        logger.info(f"   📅 Time: {latest_choch_1h.candle_time}")
        logger.info(f"   🔍 Index: {latest_choch_1h.index}/{len(df_1h)}")
        
        # Check if body closure confirmed
        choch_candle = df_1h.iloc[latest_choch_1h.index]
        body_close = choch_candle['close']
        body_open = choch_candle['open']
        
        if latest_choch_1h.direction == 'bullish':
            if body_close > latest_choch_1h.break_price:
                logger.success(f"   ✅ Body closure CONFIRMED (close > break price)")
            else:
                logger.warning(f"   ⚠️  Wick only (close: {body_close:.2f} vs break: {latest_choch_1h.break_price:.2f})")
        else:
            if body_close < latest_choch_1h.break_price:
                logger.success(f"   ✅ Body closure CONFIRMED (close < break price)")
            else:
                logger.warning(f"   ⚠️  Wick only (close: {body_close:.2f} vs break: {latest_choch_1h.break_price:.2f})")
    else:
        logger.warning("⚠️  No CHoCH detected on 1H")
        latest_choch_1h = None
    
    print()
    
    # ==================== STEP 3: ORDER BLOCKS (V3.5) ====================
    logger.info("📦 Step 3/8: Detecting Order Blocks...")
    
    order_blocks = []
    
    # Detect OB for Daily CHoCH
    chochs_daily = smc.detect_choch(df_daily)
    if chochs_daily:
        latest_choch_daily = chochs_daily[-1]
        ob_daily = smc.detect_order_block(df_daily, latest_choch_daily, debug=True)
        if ob_daily:
            order_blocks.append(('Daily', ob_daily))
            logger.success(f"✅ Order Block Daily: {ob_daily.direction.upper()} | Score: {ob_daily.ob_score}/10")
            logger.info(f"   📍 Zone: ${ob_daily.bottom:,.2f} - ${ob_daily.top:,.2f}")
            logger.info(f"   💎 Unfilled FVG: {'YES' if ob_daily.has_unfilled_fvg else 'NO'}")
    
    # Detect OB for 4H CHoCH
    chochs_4h = smc.detect_choch(df_4h)
    if chochs_4h:
        latest_choch_4h = chochs_4h[-1]
        ob_4h = smc.detect_order_block(df_4h, latest_choch_4h, debug=True)
        if ob_4h:
            order_blocks.append(('4H', ob_4h))
            logger.success(f"✅ Order Block 4H: {ob_4h.direction.upper()} | Score: {ob_4h.ob_score}/10")
            logger.info(f"   📍 Zone: ${ob_4h.bottom:,.2f} - ${ob_4h.top:,.2f}")
    
    # Detect OB for 1H CHoCH
    if latest_choch_1h:
        ob_1h = smc.detect_order_block(df_1h, latest_choch_1h, debug=True)
        if ob_1h:
            order_blocks.append(('1H', ob_1h))
            logger.success(f"✅ Order Block 1H: {ob_1h.direction.upper()} | Score: {ob_1h.ob_score}/10")
            logger.info(f"   📍 Zone: ${ob_1h.bottom:,.2f} - ${ob_1h.top:,.2f}")
    
    if not order_blocks:
        logger.warning("⚠️  No Order Blocks detected")
    
    print()
    
    # ==================== STEP 4: FVG DETECTION ====================
    logger.info("📊 Step 4/8: Detecting FVG gaps...")
    
    fvgs_found = []
    
    # Detect FVG on Daily (if CHoCH exists)
    if chochs_daily:
        fvg_daily = smc.detect_fvg(df_daily, chochs_daily[-1], current_price)
        if fvg_daily:
            gap_pct = ((fvg_daily.top - fvg_daily.bottom) / fvg_daily.bottom) * 100
            logger.success(f"✅ FVG Daily: {fvg_daily.direction.upper()}")
            logger.info(f"   📍 Zone: ${fvg_daily.bottom:,.2f} - ${fvg_daily.top:,.2f}")
            logger.info(f"   📏 Gap Size: {gap_pct:.3f}%")
            
            if gap_pct >= 0.10:
                logger.success(f"   ✅ Gap VALID (≥0.10%)")
                fvgs_found.append(('Daily', fvg_daily, gap_pct))
            else:
                logger.warning(f"   ❌ Gap too small (<0.10%)")
    
    # Detect FVG on 4H
    if chochs_4h:
        fvg_4h = smc.detect_fvg(df_4h, chochs_4h[-1], current_price)
        if fvg_4h:
            gap_pct = ((fvg_4h.top - fvg_4h.bottom) / fvg_4h.bottom) * 100
            logger.success(f"✅ FVG 4H: {fvg_4h.direction.upper()}")
            logger.info(f"   📍 Zone: ${fvg_4h.bottom:,.2f} - ${fvg_4h.top:,.2f}")
            logger.info(f"   📏 Gap Size: {gap_pct:.3f}%")
            
            if gap_pct >= 0.10:
                logger.success(f"   ✅ Gap VALID (≥0.10%)")
                fvgs_found.append(('4H', fvg_4h, gap_pct))
            else:
                logger.warning(f"   ❌ Gap too small (<0.10%)")
    
    # Detect FVG on 1H
    if latest_choch_1h:
        fvg_1h = smc.detect_fvg(df_1h, latest_choch_1h, current_price)
        if fvg_1h:
            gap_pct = ((fvg_1h.top - fvg_1h.bottom) / fvg_1h.bottom) * 100
            logger.success(f"✅ FVG 1H: {fvg_1h.direction.upper()}")
            logger.info(f"   📍 Zone: ${fvg_1h.bottom:,.2f} - ${fvg_1h.top:,.2f}")
            logger.info(f"   📏 Gap Size: {gap_pct:.3f}%")
            
            if gap_pct >= 0.10:
                logger.success(f"   ✅ Gap VALID (≥0.10%)")
                fvgs_found.append(('1H', fvg_1h, gap_pct))
            else:
                logger.warning(f"   ❌ Gap too small (<0.10%)")
    
    if not fvgs_found:
        logger.warning("⚠️  No valid FVG gaps (≥0.10%) detected")
    
    print()
    
    # ==================== STEP 5: FVG MAGNETS ====================
    logger.info("🧲 Step 5/8: Analyzing FVG Magnets...")
    
    magnets_4h = smc.get_fvg_magnets(symbol, '4H')
    magnets_1h = smc.get_fvg_magnets(symbol, '1H')
    
    logger.info(f"📊 4H Magnets: {len(magnets_4h)} zones")
    for i, magnet in enumerate(magnets_4h, 1):
        logger.info(f"   {i}. ${magnet.bottom:,.2f} - ${magnet.top:,.2f} ({magnet.direction.upper()})")
    
    logger.info(f"📊 1H Magnets: {len(magnets_1h)} zones")
    for i, magnet in enumerate(magnets_1h, 1):
        logger.info(f"   {i}. ${magnet.bottom:,.2f} - ${magnet.top:,.2f} ({magnet.direction.upper()})")
    
    # Check if price is approaching a magnet
    approaching_magnet = None
    for magnet in magnets_4h + magnets_1h:
        distance_to_bottom = abs(current_price - magnet.bottom) / current_price * 100
        distance_to_top = abs(current_price - magnet.top) / current_price * 100
        
        if distance_to_bottom < 5.0 or distance_to_top < 5.0:
            approaching_magnet = magnet
            logger.warning(f"⚠️  Price approaching magnet: ${magnet.bottom:,.2f} - ${magnet.top:,.2f}")
            break
    
    print()
    
    # ==================== STEP 6: REVERSAL VS CONTINUATION ====================
    logger.info("🔄 Step 6/8: Reversal vs Continuation Analysis...")
    
    # Determine trend direction
    ma20 = df_daily['close'].rolling(20).mean().iloc[-1]
    ma50 = df_daily['close'].rolling(50).mean().iloc[-1]
    
    if current_price > ma20 > ma50:
        trend = "BULLISH"
        logger.info(f"📈 Trend: {trend} (price > MA20 > MA50)")
    elif current_price < ma20 < ma50:
        trend = "BEARISH"
        logger.info(f"📉 Trend: {trend} (price < MA20 < MA50)")
    else:
        trend = "MIXED"
        logger.info(f"🔀 Trend: {trend}")
    
    # Setup type determination
    setup_type = None
    setup_direction = None
    
    if latest_choch_1h:
        if latest_choch_1h.direction == 'bullish':
            if trend == "BEARISH":
                setup_type = "REVERSAL"
                setup_direction = "LONG"
                logger.success(f"✅ REVERSAL LONG detected (bullish CHoCH in bearish trend)")
            else:
                setup_type = "CONTINUATION"
                setup_direction = "LONG"
                logger.success(f"✅ CONTINUATION LONG detected (bullish CHoCH in bullish trend)")
        else:
            if trend == "BULLISH":
                setup_type = "REVERSAL"
                setup_direction = "SHORT"
                logger.success(f"✅ REVERSAL SHORT detected (bearish CHoCH in bullish trend)")
            else:
                setup_type = "CONTINUATION"
                setup_direction = "SHORT"
                logger.success(f"✅ CONTINUATION SHORT detected (bearish CHoCH in bearish trend)")
    else:
        logger.warning("⚠️  Cannot determine setup type (no CHoCH 1H)")
    
    print()
    
    # ==================== STEP 7: AI SCORER ====================
    logger.info("🧠 Step 7/8: Running AI Scorer...")
    
    try:
        optimizer = StrategyOptimizer()
        
        # Create mock setup for AI scoring
        if latest_choch_1h and order_blocks:
            # Use best OB
            best_ob = max(order_blocks, key=lambda x: x[1].ob_score)[1]
            
            ai_score = optimizer.calculate_ai_probability(
                symbol=symbol,
                hour=datetime.now().hour,
                fvg_quality=fvgs_found[0][2] if fvgs_found else 0,
                choch_strength=10,  # Assume strong CHoCH
                pattern_type=setup_type.lower() if setup_type else 'unknown'
            )
            
            logger.success(f"🧠 AI Score: {ai_score}/100")
            
            if ai_score >= 80:
                logger.success(f"   ✅ HIGH CONFIDENCE - TAKE THE TRADE!")
            elif ai_score >= 60:
                logger.info(f"   ⚠️  MEDIUM CONFIDENCE - Review setup")
            else:
                logger.warning(f"   ❌ LOW CONFIDENCE - Skip trade")
        else:
            logger.warning("⚠️  Cannot calculate AI score (missing CHoCH or OB)")
            ai_score = 0
    except Exception as e:
        logger.error(f"❌ AI Scorer error: {e}")
        ai_score = 0
    
    print()
    
    # ==================== STEP 8: FINAL VERDICT ====================
    logger.info("🎯 Step 8/8: Final Verdict...")
    print()
    print("="*80)
    print("🎯 BTCUSD ELITE SCAN RESULTS")
    print("="*80)
    print()
    
    # Summary
    print(f"💰 Current Price: ${current_price:,.2f}")
    print(f"📊 Trend: {trend}")
    print(f"🔄 Setup Type: {setup_type if setup_type else 'N/A'}")
    print(f"📈 Direction: {setup_direction if setup_direction else 'N/A'}")
    print()
    
    print(f"📦 Order Blocks: {len(order_blocks)} detected")
    for tf, ob in order_blocks:
        print(f"   • {tf}: {ob.direction.upper()} | Score: {ob.ob_score}/10 | ${ob.bottom:,.0f}-${ob.top:,.0f}")
    print()
    
    print(f"📊 Valid FVGs: {len(fvgs_found)} (≥0.10%)")
    for tf, fvg, gap_pct in fvgs_found:
        print(f"   • {tf}: {fvg.direction.upper()} | Gap: {gap_pct:.3f}% | ${fvg.bottom:,.0f}-${fvg.top:,.0f}")
    print()
    
    print(f"🧠 AI Score: {ai_score}/100")
    print()
    
    # Final recommendation
    print("="*80)
    print("🏆 RECOMMENDATION:")
    print("="*80)
    
    # Scoring logic
    total_score = 0
    
    # CHoCH (30 points)
    if latest_choch_1h:
        total_score += 30
        print("✅ CHoCH 1H detected (+30 pts)")
    else:
        print("❌ No CHoCH 1H (0 pts)")
    
    # Order Blocks (30 points)
    if order_blocks:
        best_ob_score = max([ob[1].ob_score for ob in order_blocks])
        ob_points = int(best_ob_score * 3)  # Scale 0-10 to 0-30
        total_score += ob_points
        print(f"✅ Order Block detected (+{ob_points} pts)")
    else:
        print("❌ No Order Block (0 pts)")
    
    # FVG (20 points)
    if fvgs_found:
        total_score += 20
        print("✅ Valid FVG detected (+20 pts)")
    else:
        print("❌ No valid FVG (0 pts)")
    
    # AI Score (20 points)
    ai_points = int(ai_score / 5)  # Scale 0-100 to 0-20
    total_score += ai_points
    print(f"🧠 AI Confidence (+{ai_points} pts)")
    
    print()
    print(f"📊 TOTAL SCORE: {total_score}/100")
    print()
    
    if total_score >= 70:
        print("🚀 VERDICT: TRADE SETUP DETECTED!")
        print("   ✅ Glitch in Matrix recommends ENTRY")
        
        # Entry details
        if order_blocks:
            best_ob = max(order_blocks, key=lambda x: x[1].ob_score)[1]
            print()
            print("📍 ENTRY ZONE:")
            print(f"   OB: ${best_ob.bottom:,.2f} - ${best_ob.top:,.2f}")
            print(f"   Middle: ${best_ob.middle:,.2f}")
            print(f"   Direction: {best_ob.direction.upper()}")
    elif total_score >= 50:
        print("⚠️  VERDICT: MONITOR SETUP")
        print("   Setup has potential but needs confirmation")
    else:
        print("❌ VERDICT: NO TRADE")
        print("   Insufficient institutional signals - stay on sidelines")
    
    print()
    print("="*80)
    
    return {
        'symbol': symbol,
        'current_price': current_price,
        'trend': trend,
        'setup_type': setup_type,
        'setup_direction': setup_direction,
        'choch_1h': latest_choch_1h,
        'order_blocks': order_blocks,
        'fvgs': fvgs_found,
        'ai_score': ai_score,
        'total_score': total_score,
        'recommendation': 'TRADE' if total_score >= 70 else 'MONITOR' if total_score >= 50 else 'NO_TRADE'
    }


if __name__ == "__main__":
    try:
        result = analyze_btcusd_elite()
        
        if result:
            # Save results to JSON
            output_file = 'btcusd_elite_scan_results.json'
            with open(output_file, 'w') as f:
                # Convert non-serializable objects to dict
                result_json = {
                    'symbol': result['symbol'],
                    'current_price': result['current_price'],
                    'trend': result['trend'],
                    'setup_type': result['setup_type'],
                    'setup_direction': result['setup_direction'],
                    'ai_score': result['ai_score'],
                    'total_score': result['total_score'],
                    'recommendation': result['recommendation'],
                    'scan_time': datetime.now().isoformat()
                }
                json.dump(result_json, f, indent=2)
            
            print(f"\n💾 Results saved to: {output_file}")
    except KeyboardInterrupt:
        print("\n⏹️  Scan interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
