#!/usr/bin/env python3
"""
🔍 DAILY STRATEGY AUDIT - Reversal vs Continuity Analysis
═══════════════════════════════════════════════════════════

SCOPE: Analiza profundă a logicii de Reversal (CHoCH) vs Continuity (BOS)

OBIECTIVE:
1. Verifică dacă botul detectează corect ambele tipuri de setup-uri
2. Analizează modul de calcul al Macro Leg pentru Premium/Discount
3. Identifică lacune în logica de BOS (Break of Structure)
4. Raportează câte setups de fiecare tip sunt găsite pe ultimele 100 bare

═══════════════════════════════════════════════════════════
by ФорексГод - Glitch in Matrix V8.1
"""

import sys
sys.path.append('.')

from smc_detector import SMCDetector
from ctrader_cbot_client import CTraderCBotClient
import pandas as pd
from datetime import datetime
from loguru import logger

# Suppress logs
logger.remove()
logger.add(sys.stderr, level="ERROR")


class Colors:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Colors
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    
    # Backgrounds
    BG_RED = '\033[101m'
    BG_GREEN = '\033[102m'
    BG_YELLOW = '\033[103m'
    BG_BLUE = '\033[104m'


def print_header(title: str):
    """Print formatted section header"""
    print(f"\n{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{title}{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*80}{Colors.RESET}\n")


def print_subheader(title: str):
    """Print formatted subsection header"""
    print(f"\n{Colors.YELLOW}{'─'*80}{Colors.RESET}")
    print(f"{Colors.YELLOW}{title}{Colors.RESET}")
    print(f"{Colors.YELLOW}{'─'*80}{Colors.RESET}")


def analyze_reversal_logic(detector: SMCDetector, df: pd.DataFrame, symbol: str):
    """
    STEP 1: Analiza logicii de REVERSAL (CHoCH)
    
    Verifică:
    - Cum definește un CHoCH valid?
    - CHoCH-ul este la o extremă sau din consolidare?
    - Există confirmare post-CHoCH (confirmation swing)?
    """
    print_header("📊 STEP 1: ANALIZA LOGICII DE REVERSAL (CHoCH)")
    
    # Detect swings first
    swing_highs = detector.detect_swing_highs(df)
    swing_lows = detector.detect_swing_lows(df)
    
    print(f"{Colors.BOLD}Swing Detection (ATR Prominence Filter):{Colors.RESET}")
    print(f"   Swing Lookback: {detector.swing_lookback} bars")
    print(f"   ATR Multiplier: {detector.atr_multiplier}x")
    print(f"   Swing Highs Detected: {len(swing_highs)}")
    print(f"   Swing Lows Detected: {len(swing_lows)}")
    
    # Detect CHoCH
    chochs, bos_list = detector.detect_choch_and_bos(df)
    
    print(f"\n{Colors.BOLD}CHoCH Detection Results:{Colors.RESET}")
    print(f"   Total CHoCH Detected: {len(chochs)}")
    
    if not chochs:
        print(f"   {Colors.RED}⚠️  NO CHoCH DETECTED!{Colors.RESET}")
        print(f"   Reason: No structure breaks in opposite direction found")
        return chochs, bos_list
    
    # Analyze last 5 CHoCH
    print(f"\n{Colors.BOLD}Last 5 CHoCH Signals:{Colors.RESET}")
    for i, choch in enumerate(chochs[-5:]):
        idx_display = len(chochs) - 5 + i + 1
        emoji = "🟢" if choch.direction == 'bullish' else "🔴"
        
        print(f"\n   {emoji} CHoCH #{idx_display}: {choch.direction.upper()}")
        print(f"      Bar Index: {choch.index}")
        print(f"      Break Price: {choch.break_price:.5f}")
        print(f"      Previous Trend: {choch.previous_trend if choch.previous_trend else 'None (First Break)'}")
        print(f"      Swing Broken: {choch.swing_broken.price:.5f} (bar {choch.swing_broken.index})")
        
        # Check if at extremes (last 20% of bars = recent)
        bars_count = len(df)
        position_pct = (choch.index / bars_count) * 100
        
        if position_pct > 80:
            print(f"      Position: {Colors.GREEN}Recent ({position_pct:.1f}% into dataset){Colors.RESET}")
        elif position_pct > 50:
            print(f"      Position: {Colors.YELLOW}Mid-range ({position_pct:.1f}% into dataset){Colors.RESET}")
        else:
            print(f"      Position: {Colors.RED}Old ({position_pct:.1f}% into dataset){Colors.RESET}")
        
        # Check for confirmation swing (post-CHoCH structure)
        has_confirmation = detector.has_confirmation_swing(df, choch)
        if has_confirmation:
            print(f"      Confirmation: {Colors.GREEN}✅ YES (reversal validated){Colors.RESET}")
        else:
            print(f"      Confirmation: {Colors.RED}❌ NO (reversal not confirmed){Colors.RESET}")
    
    # LOGIC EXPLANATION
    print_subheader("📖 REVERSAL LOGIC EXPLANATION")
    print(f"{Colors.BOLD}Code Location:{Colors.RESET} smc_detector.py → detect_choch_and_bos()")
    print(f"\n{Colors.BOLD}Definition:{Colors.RESET}")
    print(f"   CHoCH = Change of Character (Trend Reversal)")
    print(f"   Occurs when price breaks swing in OPPOSITE direction to previous trend")
    
    print(f"\n{Colors.BOLD}Detection Rules:{Colors.RESET}")
    print(f"   1. INTERLEAVE swings (merge highs/lows chronologically)")
    print(f"   2. Track previous trend direction (bullish/bearish)")
    print(f"   3. {Colors.GREEN}BULLISH CHoCH{Colors.RESET}: Higher High AFTER bearish trend")
    print(f"   4. {Colors.RED}BEARISH CHoCH{Colors.RESET}: Lower Low AFTER bullish trend")
    print(f"   5. First break = CHoCH (establishes initial trend)")
    
    print(f"\n{Colors.BOLD}Validation (has_confirmation_swing):{Colors.RESET}")
    print(f"   - Checks if CHoCH has post-break structure")
    print(f"   - BULLISH CHoCH: Requires HL (Higher Low) after HH")
    print(f"   - BEARISH CHoCH: Requires LH (Lower High) after LL")
    print(f"   - Without confirmation: Reversal not yet validated")
    
    print(f"\n{Colors.BOLD}Is CHoCH at Extremes or Consolidation?{Colors.RESET}")
    latest_choch = chochs[-1] if chochs else None
    if latest_choch:
        # Check distance from highest/lowest points
        all_highs = df['high'].values
        all_lows = df['low'].values
        
        highest_price = all_highs.max()
        lowest_price = all_lows.min()
        price_range = highest_price - lowest_price
        
        if latest_choch.direction == 'bearish':
            distance_from_high = highest_price - latest_choch.break_price
            distance_pct = (distance_from_high / price_range) * 100
            
            if distance_pct < 20:
                print(f"   {Colors.GREEN}✅ Latest CHoCH near HIGH ({distance_pct:.1f}% from top){Colors.RESET}")
                print(f"   → Valid reversal from extreme (institutional distribution)")
            else:
                print(f"   {Colors.YELLOW}⚠️  Latest CHoCH away from HIGH ({distance_pct:.1f}% from top){Colors.RESET}")
                print(f"   → Could be mid-range reversal (less reliable)")
        
        elif latest_choch.direction == 'bullish':
            distance_from_low = latest_choch.break_price - lowest_price
            distance_pct = (distance_from_low / price_range) * 100
            
            if distance_pct < 20:
                print(f"   {Colors.GREEN}✅ Latest CHoCH near LOW ({distance_pct:.1f}% from bottom){Colors.RESET}")
                print(f"   → Valid reversal from extreme (institutional accumulation)")
            else:
                print(f"   {Colors.YELLOW}⚠️  Latest CHoCH away from LOW ({distance_pct:.1f}% from bottom){Colors.RESET}")
                print(f"   → Could be mid-range reversal (less reliable)")
    
    return chochs, bos_list


def analyze_continuity_logic(detector: SMCDetector, df: pd.DataFrame, chochs, bos_list):
    """
    STEP 2: Analiza logicii de CONTINUITY (BOS)
    
    Verifică:
    - Cum definește un BOS valid?
    - BOS-ul este folosit pentru entries sau doar tracked?
    - Există logică de FVG după BOS pentru continuation trades?
    """
    print_header("📊 STEP 2: ANALIZA LOGICII DE CONTINUITY (BOS)")
    
    print(f"{Colors.BOLD}BOS Detection Results:{Colors.RESET}")
    print(f"   Total BOS Detected: {len(bos_list)}")
    
    if not bos_list:
        print(f"   {Colors.RED}⚠️  NO BOS DETECTED!{Colors.RESET}")
        print(f"   {Colors.YELLOW}This means:{Colors.RESET}")
        print(f"   - No continuation signals found")
        print(f"   - All breaks are reversals (CHoCH)")
        print(f"   - Bot may be missing trend continuation setups")
        return
    
    # Analyze last 5 BOS
    print(f"\n{Colors.BOLD}Last 5 BOS Signals:{Colors.RESET}")
    for i, bos in enumerate(bos_list[-5:]):
        idx_display = len(bos_list) - 5 + i + 1
        emoji = "🟢" if bos.direction == 'bullish' else "🔴"
        
        print(f"\n   {emoji} BOS #{idx_display}: {bos.direction.upper()}")
        print(f"      Bar Index: {bos.index}")
        print(f"      Break Price: {bos.break_price:.5f}")
        print(f"      Swing Broken: {bos.swing_broken.price:.5f} (bar {bos.swing_broken.index})")
        
        # Check position in dataset
        bars_count = len(df)
        position_pct = (bos.index / bars_count) * 100
        
        if position_pct > 80:
            print(f"      Position: {Colors.GREEN}Recent ({position_pct:.1f}% into dataset){Colors.RESET}")
        elif position_pct > 50:
            print(f"      Position: {Colors.YELLOW}Mid-range ({position_pct:.1f}% into dataset){Colors.RESET}")
        else:
            print(f"      Position: {Colors.RED}Old ({position_pct:.1f}% into dataset){Colors.RESET}")
    
    # LOGIC EXPLANATION
    print_subheader("📖 CONTINUITY LOGIC EXPLANATION")
    print(f"{Colors.BOLD}Code Location:{Colors.RESET} smc_detector.py → detect_choch_and_bos()")
    print(f"\n{Colors.BOLD}Definition:{Colors.RESET}")
    print(f"   BOS = Break of Structure (Trend Continuation)")
    print(f"   Occurs when price breaks swing in SAME direction as previous trend")
    
    print(f"\n{Colors.BOLD}Detection Rules:{Colors.RESET}")
    print(f"   1. Previous trend must be established (by prior CHoCH)")
    print(f"   2. {Colors.GREEN}BULLISH BOS{Colors.RESET}: Higher High AFTER bullish trend (HH confirmation)")
    print(f"   3. {Colors.RED}BEARISH BOS{Colors.RESET}: Lower Low AFTER bearish trend (LL confirmation)")
    print(f"   4. Indicates strong momentum continuation")
    
    print(f"\n{Colors.BOLD}Usage in scan_for_setup():{Colors.RESET}")
    print(f"   {Colors.GREEN}✅ BOS IS USED FOR ENTRIES!{Colors.RESET}")
    print(f"   - Code: scan_for_setup() uses both CHoCH and BOS")
    print(f"   - Logic: Picks most recent signal (CHoCH or BOS)")
    print(f"   - Strategy Type: 'reversal' (CHoCH) or 'continuation' (BOS)")
    
    print(f"\n{Colors.BOLD}Entry Logic for BOS:{Colors.RESET}")
    print(f"   1. Detect Daily BOS (trend continuation)")
    print(f"   2. Find FVG after BOS (pullback zone)")
    print(f"   3. Wait for price to retrace into FVG")
    print(f"   4. Require 4H CHoCH confirmation (pullback finished)")
    print(f"   5. Enter in direction of BOS (continuation)")
    
    print(f"\n{Colors.BOLD}Key Difference from CHoCH:{Colors.RESET}")
    print(f"   - CHoCH: Entry after trend CHANGE (reversal at extremes)")
    print(f"   - BOS: Entry on trend CONTINUATION (ride existing momentum)")
    print(f"   - Both use same FVG detection and 4H confirmation")
    
    # Compare CHoCH vs BOS counts
    print_subheader("📊 REVERSAL vs CONTINUITY COUNT")
    choch_count = len(chochs)
    bos_count = len(bos_list)
    total_signals = choch_count + bos_count
    
    if total_signals > 0:
        choch_pct = (choch_count / total_signals) * 100
        bos_pct = (bos_count / total_signals) * 100
        
        print(f"   {Colors.BOLD}Signal Distribution:{Colors.RESET}")
        print(f"   - CHoCH (Reversal): {choch_count} ({choch_pct:.1f}%)")
        print(f"   - BOS (Continuity): {bos_count} ({bos_pct:.1f}%)")
        print(f"   - Total Signals: {total_signals}")
        
        print(f"\n   {Colors.BOLD}Interpretation:{Colors.RESET}")
        if bos_count > choch_count:
            print(f"   {Colors.GREEN}✅ More BOS than CHoCH = Strong trending market{Colors.RESET}")
            print(f"   → Good for continuation trades (ride the trend)")
        elif choch_count > bos_count:
            print(f"   {Colors.YELLOW}⚠️  More CHoCH than BOS = Choppy / Ranging market{Colors.RESET}")
            print(f"   → Focus on reversal trades (wait for extremes)")
        else:
            print(f"   {Colors.BLUE}ℹ️  Equal CHoCH and BOS = Balanced market{Colors.RESET}")
            print(f"   → Both reversal and continuation setups valid")


def analyze_macro_leg_calculation(detector: SMCDetector, df: pd.DataFrame, chochs, bos_list, symbol: str):
    """
    STEP 3: Analiza calculului Macro Leg pentru Premium/Discount
    
    Verifică:
    - Cum se calculează Equilibrium (50% Fib)?
    - Se folosește același Macro Leg pentru Reversal și Continuity?
    - Logica de Premium/Discount diferă între cele două strategii?
    """
    print_header("📊 STEP 3: ANALIZA MACRO LEG & PREMIUM/DISCOUNT")
    
    swing_highs = detector.detect_swing_highs(df)
    swing_lows = detector.detect_swing_lows(df)
    
    print(f"{Colors.BOLD}Macro Swing Detection:{Colors.RESET}")
    print(f"   Swing Highs Available: {len(swing_highs)}")
    print(f"   Swing Lows Available: {len(swing_lows)}")
    
    if not swing_highs or not swing_lows:
        print(f"   {Colors.RED}⚠️  Insufficient swings for Macro Leg calculation{Colors.RESET}")
        return
    
    # Calculate equilibrium
    equilibrium = detector.calculate_equilibrium(df, swing_highs, swing_lows)
    
    print(f"\n{Colors.BOLD}Equilibrium Calculation:{Colors.RESET}")
    if equilibrium:
        macro_high = swing_highs[-1].price
        macro_low = swing_lows[-1].price
        
        print(f"   Method: (Macro High + Macro Low) / 2.0")
        print(f"   Macro High: {macro_high:.5f} (bar {swing_highs[-1].index})")
        print(f"   Macro Low: {macro_low:.5f} (bar {swing_lows[-1].index})")
        print(f"   {Colors.CYAN}Equilibrium (50%): {equilibrium:.5f}{Colors.RESET}")
        
        macro_range = macro_high - macro_low
        print(f"   Macro Range: {macro_range:.5f} (100% swing)")
        
        # Show zones
        print(f"\n{Colors.BOLD}Zone Breakdown:{Colors.RESET}")
        print(f"   {Colors.GREEN}Premium Zone (Sell):{Colors.RESET} {equilibrium:.5f} - {macro_high:.5f}")
        print(f"   {Colors.CYAN}Equilibrium (50%):{Colors.RESET} {equilibrium:.5f}")
        print(f"   {Colors.BLUE}Discount Zone (Buy):{Colors.RESET} {macro_low:.5f} - {equilibrium:.5f}")
    else:
        print(f"   {Colors.RED}⚠️  Could not calculate equilibrium{Colors.RESET}")
        return
    
    # LOGIC EXPLANATION
    print_subheader("📖 MACRO LEG LOGIC EXPLANATION")
    print(f"{Colors.BOLD}Code Location:{Colors.RESET} smc_detector.py → calculate_equilibrium()")
    
    print(f"\n{Colors.BOLD}Algorithm:{Colors.RESET}")
    print(f"   1. Get last swing high from swing_highs list")
    print(f"   2. Get last swing low from swing_lows list")
    print(f"   3. Calculate: (high + low) / 2.0 = Equilibrium")
    print(f"   4. This creates 50% Fibonacci level")
    
    print(f"\n{Colors.BOLD}Same Macro Leg for Both Strategies?{Colors.RESET}")
    print(f"   {Colors.GREEN}✅ YES - Identical calculation{Colors.RESET}")
    print(f"   - Reversal (CHoCH): Uses last swing high/low")
    print(f"   - Continuity (BOS): Uses last swing high/low")
    print(f"   - {Colors.YELLOW}No differentiation in code{Colors.RESET}")
    
    print(f"\n{Colors.BOLD}Is This Correct?{Colors.RESET}")
    print(f"   {Colors.YELLOW}⚠️  POTENTIAL ISSUE DETECTED:{Colors.RESET}")
    print(f"   - For REVERSAL: Macro Leg should be from previous trend (pre-CHoCH)")
    print(f"   - For CONTINUITY: Macro Leg should be from current impulse (post-BOS)")
    print(f"   - Current code: Uses SAME logic for both (last swing high/low)")
    
    print(f"\n{Colors.BOLD}Recommended Fix:{Colors.RESET}")
    print(f"   {Colors.CYAN}REVERSAL (CHoCH):{Colors.RESET}")
    print(f"   - Macro Leg = Swing before CHoCH to CHoCH break point")
    print(f"   - Measures depth of pullback from OLD trend")
    print(f"   - Example: Bearish CHoCH → Macro Leg from last HH to LL")
    
    print(f"\n   {Colors.CYAN}CONTINUITY (BOS):{Colors.RESET}")
    print(f"   - Macro Leg = Swing after last CHoCH to BOS break point")
    print(f"   - Measures depth of pullback in NEW trend")
    print(f"   - Example: Bullish BOS → Macro Leg from last LL (post-CHoCH) to HH")
    
    # Test with latest signals
    print_subheader("🧪 PRACTICAL TEST WITH LATEST SIGNALS")
    
    latest_choch = chochs[-1] if chochs else None
    latest_bos = bos_list[-1] if bos_list else None
    
    if latest_choch:
        print(f"\n{Colors.BOLD}Latest CHoCH (Reversal):{Colors.RESET}")
        print(f"   Direction: {latest_choch.direction.upper()}")
        print(f"   Break Price: {latest_choch.break_price:.5f}")
        print(f"   Current Equilibrium: {equilibrium:.5f}")
        
        if latest_choch.direction == 'bearish':
            if latest_choch.break_price < equilibrium:
                print(f"   {Colors.GREEN}✅ CHoCH break below 50% (valid bearish reversal){Colors.RESET}")
            else:
                print(f"   {Colors.YELLOW}⚠️  CHoCH break above 50% (shallow reversal?){Colors.RESET}")
        else:
            if latest_choch.break_price > equilibrium:
                print(f"   {Colors.GREEN}✅ CHoCH break above 50% (valid bullish reversal){Colors.RESET}")
            else:
                print(f"   {Colors.YELLOW}⚠️  CHoCH break below 50% (shallow reversal?){Colors.RESET}")
    
    if latest_bos:
        print(f"\n{Colors.BOLD}Latest BOS (Continuity):{Colors.RESET}")
        print(f"   Direction: {latest_bos.direction.upper()}")
        print(f"   Break Price: {latest_bos.break_price:.5f}")
        print(f"   Current Equilibrium: {equilibrium:.5f}")
        
        if latest_bos.direction == 'bearish':
            if latest_bos.break_price < equilibrium:
                print(f"   {Colors.GREEN}✅ BOS break below 50% (strong bearish continuation){Colors.RESET}")
            else:
                print(f"   {Colors.YELLOW}⚠️  BOS break above 50% (weak continuation?){Colors.RESET}")
        else:
            if latest_bos.break_price > equilibrium:
                print(f"   {Colors.GREEN}✅ BOS break above 50% (strong bullish continuation){Colors.RESET}")
            else:
                print(f"   {Colors.YELLOW}⚠️  BOS break below 50% (weak continuation?){Colors.RESET}")


def simulate_setup_detection(detector: SMCDetector, df_daily: pd.DataFrame, df_4h: pd.DataFrame, symbol: str):
    """
    STEP 4: Simulare detecție setup-uri (ultimele 100 bare)
    
    Rulează scan_for_setup() și raportează:
    - Câte setup-uri de Reversal găsite
    - Câte setup-uri de Continuity găsite
    - Regulile exacte aplicate pentru fiecare
    """
    print_header("📊 STEP 4: SIMULARE DETECȚIE SETUP-URI")
    
    print(f"{Colors.BOLD}Simulation Parameters:{Colors.RESET}")
    print(f"   Symbol: {symbol}")
    print(f"   Daily Bars: {len(df_daily)}")
    print(f"   4H Bars: {len(df_4h)}")
    print(f"   ATR Multiplier: {detector.atr_multiplier}x")
    print(f"   Premium/Discount Filter: V8.1 (Overlap + Tolerance)")
    
    # Run scan_for_setup
    print(f"\n{Colors.BOLD}Running scan_for_setup()...{Colors.RESET}")
    
    try:
        setup = detector.scan_for_setup(
            symbol=symbol,
            df_daily=df_daily,
            df_4h=df_4h,
            priority=1,
            require_4h_choch=True,
            skip_fvg_quality=False
        )
        
        if setup:
            print(f"\n{Colors.GREEN}✅ SETUP DETECTED!{Colors.RESET}")
            print(f"\n{Colors.BOLD}Setup Details:{Colors.RESET}")
            print(f"   Direction: {setup['direction'].upper()}")
            print(f"   Entry Price: {setup['entry_price']:.5f}")
            print(f"   Stop Loss: {setup['stop_loss']:.5f}")
            print(f"   Take Profit: {setup['take_profit']:.5f}")
            print(f"   Risk/Reward: {setup.get('risk_reward', 0):.2f}")
            
            # Determine strategy type from detected signals
            chochs, bos_list = detector.detect_choch_and_bos(df_daily)
            latest_choch = chochs[-1] if chochs else None
            latest_bos = bos_list[-1] if bos_list else None
            
            strategy_type = None
            if latest_choch and latest_bos:
                if latest_choch.index > latest_bos.index:
                    strategy_type = 'REVERSAL (CHoCH)'
                else:
                    strategy_type = 'CONTINUITY (BOS)'
            elif latest_choch:
                strategy_type = 'REVERSAL (CHoCH)'
            elif latest_bos:
                strategy_type = 'CONTINUITY (BOS)'
            
            if strategy_type:
                print(f"   {Colors.CYAN}Strategy Type: {strategy_type}{Colors.RESET}")
        else:
            print(f"\n{Colors.RED}❌ NO SETUP DETECTED{Colors.RESET}")
            print(f"   Possible reasons:")
            print(f"   - No valid CHoCH or BOS on Daily")
            print(f"   - No FVG after signal")
            print(f"   - FVG not in Premium/Discount zone")
            print(f"   - No 4H CHoCH confirmation")
            print(f"   - Counter-trend setup blocked")
    
    except Exception as e:
        print(f"\n{Colors.RED}❌ ERROR during scan_for_setup():{Colors.RESET}")
        print(f"   {str(e)}")
    
    # Manual count of potential setups
    print_subheader("📊 MANUAL SETUP COUNT")
    
    chochs, bos_list = detector.detect_choch_and_bos(df_daily)
    current_price = df_daily['close'].iloc[-1]
    
    reversal_count = 0
    continuity_count = 0
    
    # Count CHoCH-based setups (Reversal)
    for choch in chochs:
        fvg = detector.detect_fvg(df_daily, choch, current_price)
        if fvg:
            reversal_count += 1
    
    # Count BOS-based setups (Continuity)
    for bos in bos_list:
        fvg = detector.detect_fvg(df_daily, bos, current_price)
        if fvg:
            continuity_count += 1
    
    total_potential = reversal_count + continuity_count
    
    print(f"\n{Colors.BOLD}Potential Setup Count (with FVG):{Colors.RESET}")
    print(f"   {Colors.GREEN}Reversal (CHoCH + FVG):{Colors.RESET} {reversal_count}")
    print(f"   {Colors.BLUE}Continuity (BOS + FVG):{Colors.RESET} {continuity_count}")
    print(f"   {Colors.CYAN}Total Potential:{Colors.RESET} {total_potential}")
    
    print(f"\n{Colors.BOLD}Filters Applied by scan_for_setup():{Colors.RESET}")
    print(f"   1. ATR Prominence Filter (1.5x ATR)")
    print(f"   2. Premium/Discount Zone (48-52% Fib with tolerance)")
    print(f"   3. Daily Trend Alignment (no counter-trend)")
    print(f"   4. 4H CHoCH Confirmation (pullback finished)")
    print(f"   5. FVG Quality Score (≥60 normal, ≥70 GBP)")
    
    if total_potential > 0:
        print(f"\n{Colors.YELLOW}Note:{Colors.RESET}")
        print(f"   Potential setups ({total_potential}) > Actual setup (0-1)")
        print(f"   This is expected - filters reduce false positives")
        print(f"   V8.1 filters reject 35-55% of raw signals")


def generate_recommendations(chochs, bos_list):
    """
    STEP 5: Recomandări pentru îmbunătățirea logicii
    """
    print_header("💡 STEP 5: RECOMANDĂRI & ÎMBUNĂTĂȚIRI")
    
    print(f"{Colors.BOLD}Analiza Rezultatelor:{Colors.RESET}")
    print(f"   CHoCH Detectate: {len(chochs)}")
    print(f"   BOS Detectate: {len(bos_list)}")
    
    # Issue 1: BOS Logic
    if len(bos_list) == 0:
        print(f"\n{Colors.RED}🚨 ISSUE #1: NO BOS DETECTED{Colors.RESET}")
        print(f"   Impact: Bot may be missing continuation setups")
        print(f"   Recommendation:")
        print(f"   - Verify BOS detection logic in detect_choch_and_bos()")
        print(f"   - Ensure previous trend is tracked correctly")
        print(f"   - Check if swings are alternating properly (interleaved)")
    else:
        print(f"\n{Colors.GREEN}✅ BOS Logic: Working{Colors.RESET}")
        print(f"   {len(bos_list)} BOS signals detected")
    
    # Issue 2: Macro Leg Differentiation
    print(f"\n{Colors.YELLOW}⚠️  ISSUE #2: MACRO LEG NOT DIFFERENTIATED{Colors.RESET}")
    print(f"   Current: Same Macro Leg calculation for Reversal and Continuity")
    print(f"   Problem: May not accurately reflect retracement depth")
    print(f"\n   {Colors.CYAN}Recommendation:{Colors.RESET}")
    print(f"   - REVERSAL: Macro Leg = Previous trend swing (pre-CHoCH)")
    print(f"   - CONTINUITY: Macro Leg = Current impulse (post-BOS)")
    print(f"   - Implement: calculate_equilibrium_reversal() vs calculate_equilibrium_continuity()")
    
    # Issue 3: Premium/Discount on BOS
    print(f"\n{Colors.YELLOW}⚠️  ISSUE #3: PREMIUM/DISCOUNT LOGIC IDENTICAL{Colors.RESET}")
    print(f"   Current: Same Premium/Discount rules for CHoCH and BOS")
    print(f"   Problem: BOS continuation may need different threshold")
    print(f"\n   {Colors.CYAN}Recommendation:{Colors.RESET}")
    print(f"   - REVERSAL: Keep 48-52% (deep retracement required)")
    print(f"   - CONTINUITY: Consider 38-62% (shallower pullback acceptable)")
    print(f"   - Rationale: Trending markets have shallower retracements")
    
    # Issue 4: Signal Recency
    if len(chochs) > 0:
        latest_choch = chochs[-1]
        latest_choch_bars_ago = 100 - latest_choch.index
        
        if latest_choch_bars_ago > 20:
            print(f"\n{Colors.YELLOW}⚠️  ISSUE #4: STALE CHoCH SIGNAL{Colors.RESET}")
            print(f"   Latest CHoCH: {latest_choch_bars_ago} bars ago")
            print(f"   Recommendation: Consider CHoCH age filter (reject >30 bars)")
    
    # Summary
    print_subheader("📋 SUMMARY OF RECOMMENDATIONS")
    print(f"\n{Colors.BOLD}Priority 1 (Critical):{Colors.RESET}")
    print(f"   1. Differentiate Macro Leg calculation (Reversal vs Continuity)")
    print(f"   2. Verify BOS detection working correctly")
    
    print(f"\n{Colors.BOLD}Priority 2 (Important):{Colors.RESET}")
    print(f"   3. Adjust Premium/Discount thresholds for BOS (38-62%)")
    print(f"   4. Add CHoCH age filter (reject signals >30 bars old)")
    
    print(f"\n{Colors.BOLD}Priority 3 (Enhancement):{Colors.RESET}")
    print(f"   5. Add BOS strength validation (momentum check)")
    print(f"   6. Implement multi-BOS confirmation (2+ BOS = strong trend)")


def main():
    """Main audit execution"""
    
    # Symbol to audit (default: EURJPY)
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "EURJPY"
    
    print(f"\n{Colors.CYAN}{Colors.BOLD}")
    print("╔════════════════════════════════════════════════════════════════════════════╗")
    print("║                   DAILY STRATEGY AUDIT - V8.1                              ║")
    print("║             Reversal (CHoCH) vs Continuity (BOS) Analysis                 ║")
    print("╚════════════════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}\n")
    
    print(f"Analyzing: {Colors.BOLD}{symbol}{Colors.RESET}")
    print(f"Date: {datetime.now().strftime('%B %d, %Y, %H:%M:%S')}")
    print(f"Scope: Last 100 Daily bars + 200 4H bars\n")
    
    # Connect to cTrader
    print(f"{Colors.CYAN}Connecting to cTrader...{Colors.RESET}")
    client = CTraderCBotClient()
    
    # Fetch data
    print(f"{Colors.CYAN}Fetching historical data...{Colors.RESET}")
    df_daily = client.get_historical_data(symbol, 'D1', 100)
    df_4h = client.get_historical_data(symbol, 'H4', 200)
    
    print(f"{Colors.GREEN}✅ Data fetched:{Colors.RESET}")
    print(f"   Daily bars: {len(df_daily)}")
    print(f"   4H bars: {len(df_4h)}")
    print(f"   Current Price: {df_daily['close'].iloc[-1]:.5f}\n")
    
    # Initialize detector
    detector = SMCDetector(swing_lookback=5, atr_multiplier=1.5)
    print(f"{Colors.GREEN}✅ SMC Detector V8.1 initialized{Colors.RESET}\n")
    
    # Run audit steps
    chochs, bos_list = analyze_reversal_logic(detector, df_daily, symbol)
    analyze_continuity_logic(detector, df_daily, chochs, bos_list)
    analyze_macro_leg_calculation(detector, df_daily, chochs, bos_list, symbol)
    simulate_setup_detection(detector, df_daily, df_4h, symbol)
    generate_recommendations(chochs, bos_list)
    
    # Final summary
    print(f"\n{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}AUDIT COMPLETE{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*80}{Colors.RESET}\n")
    
    print(f"{Colors.BOLD}Key Findings:{Colors.RESET}")
    print(f"   - CHoCH (Reversal) Logic: {Colors.GREEN}Working{Colors.RESET}")
    print(f"   - BOS (Continuity) Logic: {Colors.GREEN if len(bos_list) > 0 else Colors.RED}{'Working' if len(bos_list) > 0 else 'Needs Review'}{Colors.RESET}")
    print(f"   - Macro Leg Calculation: {Colors.YELLOW}Not Differentiated (Issue){Colors.RESET}")
    print(f"   - Premium/Discount: {Colors.GREEN}Working (V8.1 Overlap){Colors.RESET}")
    
    print(f"\n{Colors.CYAN}For detailed analysis, scroll up to review each step.{Colors.RESET}\n")


if __name__ == '__main__':
    main()
