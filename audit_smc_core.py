#!/usr/bin/env python3
"""
🔍 SUPREME DIAGNOSTIC SCRIPT - V8.4 CORE AUDIT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Printează FIECARE variabilă în procesul de detecție pentru a identifica
EXACT unde și de ce setup-urile sunt respinse.

Scopul: Să vedem exact matematica pe EURJPY și să înțelegem
DE CE botul "nu vede" setup-uri evidente pe grafic.
"""

import sys
import argparse
from datetime import datetime
from smc_detector import SMCDetector
from ctrader_cbot_client import CTraderCBotClient


def audit_symbol(symbol: str, ignore_open_positions: bool = False):
    """Auditează complet detecția pe un singur simbol"""
    
    print(f"\n{'='*80}")
    print(f"🔍 SUPREME DIAGNOSTIC AUDIT - {symbol}")
    print(f"{'='*80}\n")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 1. LOAD DATA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"📊 STEP 1: LOADING DATA...")
    print(f"   Symbol: {symbol}")
    
    try:
        client = CTraderCBotClient()
        
        if not client.is_available():
            print(f"❌ FAILED: cTrader cBot not running. Please start MarketDataProvider cBot.")
            return
        
        print(f"✅ cTrader cBot connected (IC Markets)")
        
        df_daily = client.get_historical_data(symbol, 'D1', 100)
        df_4h = client.get_historical_data(symbol, 'H4', 200)
        
        if df_daily is None or df_daily.empty or df_4h is None or df_4h.empty:
            print(f"❌ FAILED: No data fetched for {symbol}")
            return
        
        # Reset index to have 'time' column
        df_daily = df_daily.reset_index()
        df_4h = df_4h.reset_index()
        
        print(f"✅ Data loaded:")
        print(f"   → D1: {len(df_daily)} bars")
        print(f"   → H4: {len(df_4h)} bars")
        
        if 'time' in df_daily.columns:
            print(f"   → D1 Latest: {df_daily['time'].iloc[-1]}")
        
        if 'close' in df_daily.columns:
            print(f"   → D1 Close: {df_daily['close'].iloc[-1]:.5f}")
        
    except Exception as e:
        print(f"❌ FAILED to load data: {e}")
        return
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 2. INITIALIZE DETECTOR
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n🤖 STEP 2: INITIALIZING SMCDetector...")
    
    detector = SMCDetector()
    
    print(f"✅ SMCDetector initialized")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 3. DETECT SWINGS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n📈 STEP 3: DETECTING SWINGS...")
    
    try:
        swing_highs = detector.detect_swing_highs(df_daily)
        swing_lows = detector.detect_swing_lows(df_daily)
        
        print(f"✅ Swings detected:")
        print(f"   → Swing Highs: {len(swing_highs)}")
        print(f"   → Swing Lows: {len(swing_lows)}")
        
        if swing_highs:
            print(f"\n   Last 5 Swing Highs:")
            for sh in list(swing_highs)[-5:]:
                print(f"      • Bar {sh.index}: {sh.price:.5f}")
        
        if swing_lows:
            print(f"\n   Last 5 Swing Lows:")
            for sl in list(swing_lows)[-5:]:
                print(f"      • Bar {sl.index}: {sl.price:.5f}")
        
        if not swing_highs or not swing_lows:
            print(f"\n⚠️ WARNING: Insufficient swings!")
            print(f"   → This will cause equilibrium calculation to return None")
            print(f"   → BLACK HOLE #1: No swings = No equilibrium = Validation bypass")
    
    except Exception as e:
        print(f"❌ FAILED to detect swings: {e}")
        return
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 4. DETECT SIGNALS (CHoCH & BOS)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n🎯 STEP 4: DETECTING SIGNALS (CHoCH & BOS)...")
    
    try:
        daily_chochs, daily_bos_list = detector.detect_choch_and_bos(df_daily)
        
        print(f"✅ Signals detected:")
        print(f"   → CHoCH: {len(daily_chochs)}")
        print(f"   → BOS: {len(daily_bos_list)}")
        
        if daily_chochs:
            print(f"\n   Last CHoCH:")
            latest_choch = daily_chochs[-1]
            print(f"      • Direction: {latest_choch.direction.upper()}")
            print(f"      • Bar Index: {latest_choch.index}")
            print(f"      • Break Price: {latest_choch.break_price:.5f}")
        else:
            print(f"\n   ⚠️ No CHoCH detected")
        
        if daily_bos_list:
            print(f"\n   Last BOS:")
            latest_bos = daily_bos_list[-1]
            print(f"      • Direction: {latest_bos.direction.upper()}")
            print(f"      • Bar Index: {latest_bos.index}")
            print(f"      • Break Price: {latest_bos.break_price:.5f}")
        else:
            print(f"\n   ⚠️ No BOS detected")
        
        if not daily_chochs and not daily_bos_list:
            print(f"\n❌ CRITICAL: No signals detected!")
            print(f"   → BLACK HOLE #4: No CHoCH/BOS = scan_for_setup returns None immediately")
            return
    
    except Exception as e:
        print(f"❌ FAILED to detect signals: {e}")
        return
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 5. DETERMINE STRATEGY TYPE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n🎲 STEP 5: DETERMINING STRATEGY TYPE...")
    
    latest_choch = daily_chochs[-1] if daily_chochs else None
    latest_bos = daily_bos_list[-1] if daily_bos_list else None
    
    if latest_choch and latest_bos:
        if latest_choch.index > latest_bos.index:
            strategy_type = 'reversal'
            latest_signal = latest_choch
            strategy_emoji = '🔄'
        else:
            strategy_type = 'continuation'
            latest_signal = latest_bos
            strategy_emoji = '➡️'
    elif latest_choch:
        strategy_type = 'reversal'
        latest_signal = latest_choch
        strategy_emoji = '🔄'
    elif latest_bos:
        strategy_type = 'continuation'
        latest_signal = latest_bos
        strategy_emoji = '➡️'
    else:
        print(f"❌ CRITICAL: No strategy can be determined (no signals)")
        return
    
    print(f"✅ Strategy determined:")
    print(f"   → Type: {strategy_emoji} {strategy_type.upper()}")
    print(f"   → Latest Signal: {latest_signal.direction.upper()} {type(latest_signal).__name__}")
    print(f"   → Signal Bar: {latest_signal.index}")
    print(f"   → Signal Price: {latest_signal.break_price:.5f}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 6. CALCULATE EQUILIBRIUM
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n⚖️ STEP 6: CALCULATING EQUILIBRIUM...")
    
    try:
        if strategy_type == 'reversal':
            print(f"\n   🔄 REVERSAL: Using Pre-CHoCH Macro Leg")
            print(f"   → Searching for last swing BEFORE CHoCH (bar {latest_signal.index})")
            
            equilibrium = detector.calculate_equilibrium_reversal(
                df_daily, 
                latest_signal, 
                swing_highs, 
                swing_lows
            )
            
            # Detailed diagnostic
            if latest_signal.direction == 'bearish':
                print(f"\n   BEARISH CHoCH Logic:")
                print(f"   → Need: Last swing HIGH before bar {latest_signal.index}")
                
                found_swing = None
                for sh in reversed(swing_highs):
                    if sh.index < latest_signal.index:
                        found_swing = sh
                        break
                
                if found_swing:
                    print(f"   → Found: Macro High = {found_swing.price:.5f} @ bar {found_swing.index}")
                    print(f"   → Macro Low = {latest_signal.break_price:.5f} (CHoCH break)")
                    calculated_eq = (found_swing.price + latest_signal.break_price) / 2.0
                    print(f"   → Calculated Equilibrium: ({found_swing.price:.5f} + {latest_signal.break_price:.5f}) / 2")
                    print(f"   → = {calculated_eq:.5f}")
                else:
                    print(f"   ❌ NOT FOUND: No swing high before CHoCH!")
                    print(f"   → BLACK HOLE #1: equilibrium will be None")
            
            else:  # bullish
                print(f"\n   BULLISH CHoCH Logic:")
                print(f"   → Need: Last swing LOW before bar {latest_signal.index}")
                
                found_swing = None
                for sl in reversed(swing_lows):
                    if sl.index < latest_signal.index:
                        found_swing = sl
                        break
                
                if found_swing:
                    print(f"   → Found: Macro Low = {found_swing.price:.5f} @ bar {found_swing.index}")
                    print(f"   → Macro High = {latest_signal.break_price:.5f} (CHoCH break)")
                    calculated_eq = (latest_signal.break_price + found_swing.price) / 2.0
                    print(f"   → Calculated Equilibrium: ({latest_signal.break_price:.5f} + {found_swing.price:.5f}) / 2")
                    print(f"   → = {calculated_eq:.5f}")
                else:
                    print(f"   ❌ NOT FOUND: No swing low before CHoCH!")
                    print(f"   → BLACK HOLE #1: equilibrium will be None")
        
        else:  # continuation
            print(f"\n   ➡️ CONTINUITY: Using Post-CHoCH Impulse Leg")
            last_choch = daily_chochs[-1] if daily_chochs else None
            choch_index = last_choch.index if last_choch else 0
            
            print(f"   → Last CHoCH: bar {choch_index}")
            print(f"   → Current BOS: bar {latest_signal.index}")
            print(f"   → Searching for last swing BETWEEN bars {choch_index} and {latest_signal.index}")
            
            equilibrium = detector.calculate_equilibrium_continuity(
                df_daily,
                latest_signal,
                last_choch,
                swing_highs,
                swing_lows
            )
            
            # Detailed diagnostic
            if latest_signal.direction == 'bullish':
                print(f"\n   BULLISH BOS Logic:")
                print(f"   → Need: Last swing LOW between bars {choch_index} and {latest_signal.index}")
                
                found_swing = None
                for sl in reversed(swing_lows):
                    if choch_index < sl.index < latest_signal.index:
                        found_swing = sl
                        break
                
                if found_swing:
                    print(f"   → Found: Macro Low = {found_swing.price:.5f} @ bar {found_swing.index}")
                    print(f"   → Macro High = {latest_signal.break_price:.5f} (BOS break)")
                    calculated_eq = (latest_signal.break_price + found_swing.price) / 2.0
                    print(f"   → Calculated Equilibrium: ({latest_signal.break_price:.5f} + {found_swing.price:.5f}) / 2")
                    print(f"   → = {calculated_eq:.5f}")
                else:
                    print(f"   ⚠️ NOT FOUND between CHoCH and BOS")
                    print(f"   → Trying fallback: Last swing low BEFORE BOS (bar {latest_signal.index})")
                    
                    for sl in reversed(swing_lows):
                        if sl.index < latest_signal.index:
                            found_swing = sl
                            break
                    
                    if found_swing:
                        print(f"   → Fallback Found: {found_swing.price:.5f} @ bar {found_swing.index}")
                        calculated_eq = (latest_signal.break_price + found_swing.price) / 2.0
                        print(f"   → Calculated Equilibrium: {calculated_eq:.5f}")
                    else:
                        print(f"   ❌ NOT FOUND: No swing low at all!")
                        print(f"   → BLACK HOLE #2: equilibrium will be None")
            
            else:  # bearish
                print(f"\n   BEARISH BOS Logic:")
                print(f"   → Need: Last swing HIGH between bars {choch_index} and {latest_signal.index}")
                
                found_swing = None
                for sh in reversed(swing_highs):
                    if choch_index < sh.index < latest_signal.index:
                        found_swing = sh
                        break
                
                if found_swing:
                    print(f"   → Found: Macro High = {found_swing.price:.5f} @ bar {found_swing.index}")
                    print(f"   → Macro Low = {latest_signal.break_price:.5f} (BOS break)")
                    calculated_eq = (found_swing.price + latest_signal.break_price) / 2.0
                    print(f"   → Calculated Equilibrium: ({found_swing.price:.5f} + {latest_signal.break_price:.5f}) / 2")
                    print(f"   → = {calculated_eq:.5f}")
                else:
                    print(f"   ⚠️ NOT FOUND between CHoCH and BOS")
                    print(f"   → Trying fallback: Last swing high BEFORE BOS (bar {latest_signal.index})")
                    
                    for sh in reversed(swing_highs):
                        if sh.index < latest_signal.index:
                            found_swing = sh
                            break
                    
                    if found_swing:
                        print(f"   → Fallback Found: {found_swing.price:.5f} @ bar {found_swing.index}")
                        calculated_eq = (found_swing.price + found_swing.price) / 2.0
                        print(f"   → Calculated Equilibrium: {calculated_eq:.5f}")
                    else:
                        print(f"   ❌ NOT FOUND: No swing high at all!")
                        print(f"   → BLACK HOLE #2: equilibrium will be None")
        
        if equilibrium is None:
            print(f"\n❌ CRITICAL: Equilibrium calculation returned None!")
            print(f"   → BLACK HOLE #3: validate_fvg_zone will return True (bypass validation)")
            print(f"   → Setup may pass through OR be rejected by other filters")
        else:
            print(f"\n✅ Equilibrium calculated: {equilibrium:.5f}")
    
    except Exception as e:
        print(f"❌ FAILED to calculate equilibrium: {e}")
        equilibrium = None
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 7. DETECT FVG
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n🔲 STEP 7: DETECTING FVG...")
    
    try:
        current_price = df_daily['close'].iloc[-1]
        
        # detect_fvg requires choch and current_price
        last_fvg = detector.detect_fvg(df_daily, latest_signal, current_price)
        
        if last_fvg:
            print(f"✅ FVG detected: 1")
            
            print(f"\n   Last FVG:")
            print(f"      • Type: {last_fvg.direction.upper()}")
            print(f"      • Top: {last_fvg.top:.5f}")
            print(f"      • Middle: {last_fvg.middle:.5f}")
            print(f"      • Bottom: {last_fvg.bottom:.5f}")
            print(f"      • Bar Index: {last_fvg.index}")
            print(f"      • Size: {(last_fvg.top - last_fvg.bottom):.5f} pips")
        else:
            print(f"\n   ⚠️ No FVG detected")
            print(f"   → This will cause scan_for_setup to return None")
            return
    
    except Exception as e:
        print(f"❌ FAILED to detect FVG: {e}")
        return
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 8. VALIDATE PREMIUM/DISCOUNT ZONE (V8.4 BINARY LOGIC)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n💎 STEP 8: VALIDATING PREMIUM/DISCOUNT ZONE (V8.4 BINARY)...")
    
    try:
        current_trend = latest_signal.direction
        
        print(f"\n   Validation Parameters:")
        print(f"   → Trend: {current_trend.upper()}")
        eq_str = f"{equilibrium:.5f}" if equilibrium is not None else "None"
        print(f"   → Equilibrium: {eq_str}")
        print(f"   → FVG Top: {last_fvg.top:.5f}")
        print(f"   → FVG Middle: {last_fvg.middle:.5f}")
        print(f"   → FVG Bottom: {last_fvg.bottom:.5f}")
        
        if equilibrium is None:
            print(f"\n   ⚠️ BLACK HOLE #3 TRIGGERED:")
            print(f"   → equilibrium is None")
            print(f"   → validate_fvg_zone will return True (bypass)")
            print(f"   → Setup passes Premium/Discount check automatically")
            is_valid = True
        else:
            # Manual validation replication
            if current_trend == 'bearish':
                print(f"\n   🔽 BEARISH SHORT: FVG must reach PREMIUM (above 50%)")
                print(f"   → Check: FVG.top >= Equilibrium")
                print(f"   → {last_fvg.top:.5f} >= {equilibrium:.5f}")
                
                is_valid = last_fvg.top >= equilibrium
                
                if is_valid:
                    distance = last_fvg.top - equilibrium
                    distance_pct = (distance / equilibrium) * 100
                    
                    print(f"   ✅ VALID: FVG reaches PREMIUM zone")
                    print(f"   → Distance: +{distance:.5f} pips (+{distance_pct:.2f}%)")
                    
                    if distance >= equilibrium * 0.12:
                        ote_level = "💎 EXTREME OTE (70%+)"
                    elif distance >= equilibrium * 0.06:
                        ote_level = "✨ GOLDEN OTE (62%)"
                    else:
                        ote_level = "🎯 STANDARD OTE (50%+)"
                    
                    print(f"   → {ote_level}")
                else:
                    print(f"   ❌ REJECTED: FVG does NOT reach Premium")
                    print(f"   → FVG in DISCOUNT zone = NOT GOOD for SHORT")
            
            elif current_trend == 'bullish':
                print(f"\n   🔼 BULLISH LONG: FVG must reach DISCOUNT (below 50%)")
                print(f"   → Check: FVG.bottom <= Equilibrium")
                print(f"   → {last_fvg.bottom:.5f} <= {equilibrium:.5f}")
                
                is_valid = last_fvg.bottom <= equilibrium
                
                if is_valid:
                    distance = equilibrium - last_fvg.bottom
                    distance_pct = (distance / equilibrium) * 100
                    
                    print(f"   ✅ VALID: FVG reaches DISCOUNT zone")
                    print(f"   → Distance: -{distance:.5f} pips (-{distance_pct:.2f}%)")
                    
                    if distance >= equilibrium * 0.12:
                        ote_level = "💎 EXTREME OTE (70%- deep)"
                    elif distance >= equilibrium * 0.06:
                        ote_level = "✨ GOLDEN OTE (62%- deep)"
                    else:
                        ote_level = "🎯 STANDARD OTE (50%-)"
                    
                    print(f"   → {ote_level}")
                else:
                    print(f"   ❌ REJECTED: FVG does NOT reach Discount")
                    print(f"   → FVG in PREMIUM zone = NOT GOOD for LONG")
            else:
                print(f"   ❌ UNKNOWN TREND: {current_trend}")
                is_valid = False
        
        print(f"\n   {'✅ VALIDATION RESULT: PASS' if is_valid else '❌ VALIDATION RESULT: FAIL'}")
        
    except Exception as e:
        print(f"❌ FAILED Premium/Discount validation: {e}")
        is_valid = False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 9. CHECK FVG QUALITY SCORE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n🔍 STEP 9: CHECKING FVG QUALITY SCORE...")
    
    try:
        fvg_quality = detector.calculate_fvg_quality_score(last_fvg, df_daily, symbol, debug=False)
        
        is_gbp = 'GBP' in symbol
        min_score = 70 if is_gbp else 60
        
        print(f"✅ FVG Quality Score: {fvg_quality}/100")
        print(f"   → Minimum required: {min_score}/100 ({'GBP pair' if is_gbp else 'Standard'})")
        
        if fvg_quality >= min_score:
            print(f"   ✅ PASS: Quality sufficient")
            quality_pass = True
        else:
            print(f"   ❌ FAIL: Quality too low (< {min_score})")
            print(f"   → BLACK HOLE #5: FVG Quality Filter rejection")
            quality_pass = False
    
    except Exception as e:
        print(f"❌ FAILED to calculate FVG quality: {e}")
        quality_pass = False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 10. FINAL VERDICT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n{'='*80}")
    print(f"🎯 FINAL VERDICT")
    print(f"{'='*80}\n")
    
    if not daily_chochs and not daily_bos_list:
        print(f"❌ REJECTED: No signals (CHoCH/BOS) detected")
        print(f"   → BLACK HOLE #4")
    elif not last_fvg:
        print(f"❌ REJECTED: No FVG detected")
    elif not is_valid:
        print(f"❌ REJECTED: Premium/Discount validation FAILED")
        print(f"   → FVG not in correct zone for {current_trend.upper()} setup")
    elif not quality_pass:
        print(f"❌ REJECTED: FVG Quality Score too low")
        print(f"   → BLACK HOLE #5: Score {fvg_quality}/100 < {min_score}/100")
        print(f"   → This is the MOST COMMON rejection reason!")
        print(f"   → Solution: Lower threshold (60→50?) or adjust scoring logic")
    else:
        print(f"✅ SETUP SHOULD BE DETECTED!")
        print(f"   → Strategy: {strategy_emoji} {strategy_type.upper()}")
        print(f"   → Direction: {current_trend.upper()}")
        print(f"   → FVG: {last_fvg.direction.upper()}")
        eq_str2 = f"{equilibrium:.5f}" if equilibrium is not None else "None (bypassed)"
        print(f"   → Equilibrium: {eq_str2}")
        print(f"   → Validation: PASS")
        print(f"\n   If this setup is NOT appearing in daily_scanner.py:")
        print(f"   → Check ATR filter (swing not prominent enough?)")
        print(f"   → Check 4H confirmation requirement")
        print(f"   → Check FVG quality/size filters")
        print(f"   → Check open positions (use --ignore-open-positions)")
    
    print(f"\n{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(
        description='🔍 Supreme Diagnostic - Audit SMC Core Logic V8.4'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        default='EURJPY',
        help='Symbol to audit (default: EURJPY)'
    )
    parser.add_argument(
        '--ignore-open-positions',
        action='store_true',
        help='Ignore open positions check'
    )
    
    args = parser.parse_args()
    
    audit_symbol(args.symbol, args.ignore_open_positions)


if __name__ == '__main__':
    main()
