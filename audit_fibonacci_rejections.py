#!/usr/bin/env python3
"""
🔍 FIBONACCI REJECTIONS AUDIT - Premium/Discount Filter Analysis
═══════════════════════════════════════════════════════════════════

MISSION: Identify ALL setups rejected ONLY by Premium/Discount filter

SCOPE:
- Scan multiple major pairs (EURJPY, EURUSD, GBPUSD, USDJPY, AUDUSD)
- Find signals (CHoCH or BOS) with valid FVG
- Check if setup passes ATR filter but FAILS at validate_fvg_zone
- Report exact retracement percentage for each rejection

GOAL: See how many setups we're missing at 38%, 40%, 45%, 49% retracement
      (perfect for BOS continuation, but rejected by strict 48-52% rule)

═══════════════════════════════════════════════════════════════════
by ФорексГод - Glitch in Matrix V8.1
"""

import sys
sys.path.append('.')

from smc_detector import SMCDetector
from ctrader_cbot_client import CTraderCBotClient
import pandas as pd
from datetime import datetime
from loguru import logger
from typing import List, Dict, Tuple

# Suppress logs
logger.remove()
logger.add(sys.stderr, level="ERROR")


class Colors:
    """ANSI color codes"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'


class RejectedSetup:
    """Container for rejected setup details"""
    def __init__(self, symbol: str, direction: str, strategy_type: str,
                 signal_price: float, fvg_top: float, fvg_middle: float, fvg_bottom: float,
                 equilibrium: float, retracement_pct: float, distance_from_50: float,
                 signal_index: int, reason: str):
        self.symbol = symbol
        self.direction = direction
        self.strategy_type = strategy_type  # 'reversal' or 'continuation'
        self.signal_price = signal_price
        self.fvg_top = fvg_top
        self.fvg_middle = fvg_middle
        self.fvg_bottom = fvg_bottom
        self.equilibrium = equilibrium
        self.retracement_pct = retracement_pct
        self.distance_from_50 = distance_from_50
        self.signal_index = signal_index
        self.reason = reason


def print_header(title: str):
    """Print formatted header"""
    print(f"\n{Colors.CYAN}{'='*100}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{title:^100}{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*100}{Colors.RESET}\n")


def print_subheader(title: str):
    """Print formatted subheader"""
    print(f"\n{Colors.YELLOW}{'─'*100}{Colors.RESET}")
    print(f"{Colors.YELLOW}{title}{Colors.RESET}")
    print(f"{Colors.YELLOW}{'─'*100}{Colors.RESET}")


def calculate_retracement_percentage(fvg_middle: float, signal_price: float, 
                                     equilibrium: float, direction: str) -> float:
    """
    Calculate exact retracement percentage of FVG relative to swing leg
    
    BEARISH (SELL):
    - Signal at bottom (LL), FVG forms during retracement UP
    - Retracement % = (FVG_middle - Signal_LL) / (Equilibrium - Signal_LL) * 100
    - 0% = at Signal_LL (no retracement)
    - 50% = at Equilibrium (halfway)
    - 100% = at macro high (full retracement)
    
    BULLISH (BUY):
    - Signal at top (HH), FVG forms during retracement DOWN
    - Retracement % = (Signal_HH - FVG_middle) / (Signal_HH - Equilibrium) * 100
    - 0% = at Signal_HH (no retracement)
    - 50% = at Equilibrium (halfway)
    - 100% = at macro low (full retracement)
    """
    if direction == 'bearish':
        # BEARISH: Measure how far FVG retraced UP from signal_LL toward equilibrium
        # Equilibrium is ABOVE signal_LL
        total_range = abs(equilibrium - signal_price)
        fvg_distance = abs(fvg_middle - signal_price)
        retracement_pct = (fvg_distance / total_range) * 100 if total_range > 0 else 0
    else:
        # BULLISH: Measure how far FVG retraced DOWN from signal_HH toward equilibrium
        # Equilibrium is BELOW signal_HH
        total_range = abs(signal_price - equilibrium)
        fvg_distance = abs(signal_price - fvg_middle)
        retracement_pct = (fvg_distance / total_range) * 100 if total_range > 0 else 0
    
    return retracement_pct


def scan_pair_for_rejections(symbol: str, detector: SMCDetector, 
                             client: CTraderCBotClient) -> List[RejectedSetup]:
    """
    Scan a single pair for Premium/Discount rejections
    
    Logic:
    1. Detect all CHoCH and BOS signals
    2. For each signal, detect FVG
    3. If FVG exists, check if it passes ATR filter (implicit in swing detection)
    4. Calculate equilibrium and validate FVG zone
    5. If validation FAILS, record as rejected setup with exact retracement %
    """
    rejections = []
    
    try:
        # Fetch data
        df_daily = client.get_historical_data(symbol, 'D1', 100)
        current_price = df_daily['close'].iloc[-1]
        
        # Detect swings (ATR filter applied automatically)
        swing_highs = detector.detect_swing_highs(df_daily)
        swing_lows = detector.detect_swing_lows(df_daily)
        
        # Detect CHoCH and BOS
        chochs, bos_list = detector.detect_choch_and_bos(df_daily)
        
        # Check REVERSAL setups (CHoCH)
        for choch in chochs:
            # V8.2: Calculate equilibrium using REVERSAL method (pre-CHoCH)
            equilibrium = detector.calculate_equilibrium_reversal(df_daily, choch, swing_highs, swing_lows)
            
            if equilibrium is None:
                continue  # Can't validate without equilibrium
            
            # Detect FVG after CHoCH
            fvg = detector.detect_fvg(df_daily, choch, current_price)
            
            if fvg:
                # FVG exists - now check Premium/Discount validation
                # V8.2: Use 'reversal' strategy type (STRICT 48-52%)
                is_valid = detector.validate_fvg_zone(fvg, equilibrium, choch.direction, strategy_type='reversal', debug=False)
                
                if not is_valid:
                    # REJECTED by Premium/Discount filter
                    # Calculate exact retracement percentage
                    retracement_pct = calculate_retracement_percentage(
                        fvg.middle, choch.break_price, equilibrium, choch.direction
                    )
                    
                    # Calculate distance from 50% equilibrium
                    distance_from_50 = ((fvg.middle - equilibrium) / equilibrium) * 100
                    
                    # Determine rejection reason
                    if choch.direction == 'bearish':
                        if fvg.top < equilibrium:
                            reason = f"FVG top ({fvg.top:.5f}) below 50% ({equilibrium:.5f}) - Discount zone"
                        else:
                            reason = f"FVG not deep enough in Premium (distance: {distance_from_50:+.2f}%)"
                    else:
                        if fvg.bottom > equilibrium:
                            reason = f"FVG bottom ({fvg.bottom:.5f}) above 50% ({equilibrium:.5f}) - Premium zone"
                        else:
                            reason = f"FVG not deep enough in Discount (distance: {distance_from_50:+.2f}%)"
                    
                    rejection = RejectedSetup(
                        symbol=symbol,
                        direction=choch.direction,
                        strategy_type='reversal',
                        signal_price=choch.break_price,
                        fvg_top=fvg.top,
                        fvg_middle=fvg.middle,
                        fvg_bottom=fvg.bottom,
                        equilibrium=equilibrium,
                        retracement_pct=retracement_pct,
                        distance_from_50=distance_from_50,
                        signal_index=choch.index,
                        reason=reason
                    )
                    rejections.append(rejection)
        
        # Check CONTINUITY setups (BOS)
        for bos in bos_list:
            # V8.2: Calculate equilibrium using CONTINUITY method (post-CHoCH impulse)
            last_choch = chochs[-1] if chochs else None
            equilibrium = detector.calculate_equilibrium_continuity(df_daily, bos, last_choch, swing_highs, swing_lows)
            
            if equilibrium is None:
                continue  # Can't validate without equilibrium
            
            # Detect FVG after BOS
            fvg = detector.detect_fvg(df_daily, bos, current_price)
            
            if fvg:
                # FVG exists - now check Premium/Discount validation
                # V8.2: Use 'continuation' strategy type (RELAXED 38-62%)
                is_valid = detector.validate_fvg_zone(fvg, equilibrium, bos.direction, strategy_type='continuation', debug=False)
                
                if not is_valid:
                    # REJECTED by Premium/Discount filter
                    # Calculate exact retracement percentage
                    retracement_pct = calculate_retracement_percentage(
                        fvg.middle, bos.break_price, equilibrium, bos.direction
                    )
                    
                    # Calculate distance from 50% equilibrium
                    distance_from_50 = ((fvg.middle - equilibrium) / equilibrium) * 100
                    
                    # Determine rejection reason
                    if bos.direction == 'bearish':
                        if fvg.top < equilibrium:
                            reason = f"FVG top ({fvg.top:.5f}) below 50% ({equilibrium:.5f}) - Discount zone"
                        else:
                            reason = f"FVG not deep enough in Premium (distance: {distance_from_50:+.2f}%)"
                    else:
                        if fvg.bottom > equilibrium:
                            reason = f"FVG bottom ({fvg.bottom:.5f}) above 50% ({equilibrium:.5f}) - Premium zone"
                        else:
                            reason = f"FVG not deep enough in Discount (distance: {distance_from_50:+.2f}%)"
                    
                    rejection = RejectedSetup(
                        symbol=symbol,
                        direction=bos.direction,
                        strategy_type='continuation',
                        signal_price=bos.break_price,
                        fvg_top=fvg.top,
                        fvg_middle=fvg.middle,
                        fvg_bottom=fvg.bottom,
                        equilibrium=equilibrium,
                        retracement_pct=retracement_pct,
                        distance_from_50=distance_from_50,
                        signal_index=bos.index,
                        reason=reason
                    )
                    rejections.append(rejection)
        
    except Exception as e:
        print(f"{Colors.RED}Error scanning {symbol}: {str(e)}{Colors.RESET}")
    
    return rejections


def analyze_rejections_by_retracement(rejections: List[RejectedSetup]):
    """
    Analyze rejections grouped by retracement percentage ranges
    
    Show:
    - How many rejected at 30-38% (too shallow, correct rejection)
    - How many rejected at 38-45% (could be valid BOS)
    - How many rejected at 45-48% (borderline, could be valid BOS)
    - How many rejected at 48-52% (should pass with tolerance, edge case)
    - How many rejected at 52%+ (too deep for discount/not deep enough for premium)
    """
    print_subheader("📊 REJECTIONS BY RETRACEMENT RANGE")
    
    # Define ranges
    ranges = [
        (0, 30, "Too Shallow (<30%)"),
        (30, 38, "Shallow (30-38%)"),
        (38, 45, "Valid BOS Range (38-45%)"),
        (45, 48, "Borderline (45-48%)"),
        (48, 52, "V8.1 Tolerance Range (48-52%)"),
        (52, 70, "Deep but Wrong Zone (52-70%)"),
        (70, 100, "Very Deep (70%+)")
    ]
    
    # Count rejections in each range
    for min_pct, max_pct, label in ranges:
        count = sum(1 for r in rejections if min_pct <= r.retracement_pct < max_pct)
        
        if count > 0:
            pct_of_total = (count / len(rejections)) * 100 if rejections else 0
            
            # Color code based on range
            if 38 <= min_pct < 48:
                color = Colors.YELLOW  # Could be valid BOS
                status = "⚠️  MISSED OPPORTUNITIES"
            elif 48 <= min_pct < 52:
                color = Colors.RED  # Should pass with tolerance
                status = "❌ EDGE CASE ISSUE"
            elif min_pct < 38:
                color = Colors.GREEN  # Correct rejection
                status = "✅ CORRECT REJECTION"
            else:
                color = Colors.BLUE  # Deep but wrong zone
                status = "ℹ️  WRONG ZONE"
            
            print(f"\n{color}{label}:{Colors.RESET}")
            print(f"   Count: {count} ({pct_of_total:.1f}% of rejections)")
            print(f"   Status: {status}")
            
            # Show examples from this range
            examples = [r for r in rejections if min_pct <= r.retracement_pct < max_pct][:3]
            if examples:
                print(f"   {Colors.BOLD}Examples:{Colors.RESET}")
                for ex in examples:
                    emoji = "🟢" if ex.direction == "bullish" else "🔴"
                    strategy_emoji = "🔄" if ex.strategy_type == "reversal" else "➡️"
                    print(f"      {emoji} {strategy_emoji} {ex.symbol} {ex.direction.upper()} "
                          f"({ex.strategy_type}): {ex.retracement_pct:.1f}% retracement")


def analyze_rejections_by_strategy(rejections: List[RejectedSetup]):
    """
    Analyze rejections split by strategy type (Reversal vs Continuity)
    
    Show:
    - Reversal (CHoCH): How many rejected and at what %
    - Continuity (BOS): How many rejected and at what %
    """
    print_subheader("📊 REJECTIONS BY STRATEGY TYPE")
    
    reversal_rejections = [r for r in rejections if r.strategy_type == 'reversal']
    continuity_rejections = [r for r in rejections if r.strategy_type == 'continuation']
    
    print(f"\n{Colors.BOLD}REVERSAL (CHoCH) Rejections:{Colors.RESET}")
    print(f"   Total: {len(reversal_rejections)}")
    
    if reversal_rejections:
        avg_retracement = sum(r.retracement_pct for r in reversal_rejections) / len(reversal_rejections)
        min_retracement = min(r.retracement_pct for r in reversal_rejections)
        max_retracement = max(r.retracement_pct for r in reversal_rejections)
        
        print(f"   Avg Retracement: {avg_retracement:.1f}%")
        print(f"   Range: {min_retracement:.1f}% - {max_retracement:.1f}%")
        
        # Count how many in 38-48% range (could be valid with relaxed threshold)
        valid_bos_range = sum(1 for r in reversal_rejections if 38 <= r.retracement_pct < 48)
        if valid_bos_range > 0:
            print(f"   {Colors.YELLOW}⚠️  {valid_bos_range} rejected at 38-48% (too strict for reversal?){Colors.RESET}")
    
    print(f"\n{Colors.BOLD}CONTINUITY (BOS) Rejections:{Colors.RESET}")
    print(f"   Total: {len(continuity_rejections)}")
    
    if continuity_rejections:
        avg_retracement = sum(r.retracement_pct for r in continuity_rejections) / len(continuity_rejections)
        min_retracement = min(r.retracement_pct for r in continuity_rejections)
        max_retracement = max(r.retracement_pct for r in continuity_rejections)
        
        print(f"   Avg Retracement: {avg_retracement:.1f}%")
        print(f"   Range: {min_retracement:.1f}% - {max_retracement:.1f}%")
        
        # Count how many in 38-48% range (SHOULD be accepted for BOS)
        valid_bos_range = sum(1 for r in continuity_rejections if 38 <= r.retracement_pct < 48)
        if valid_bos_range > 0:
            pct_of_bos = (valid_bos_range / len(continuity_rejections)) * 100
            print(f"   {Colors.RED}❌ {valid_bos_range} ({pct_of_bos:.1f}%) rejected at 38-48%{Colors.RESET}")
            print(f"   {Colors.RED}   → These are PERFECT BOS continuations but TOO STRICT filter!{Colors.RESET}")


def generate_recommendations(rejections: List[RejectedSetup]):
    """Generate actionable recommendations based on rejections"""
    print_subheader("💡 RECOMMENDATIONS")
    
    # Count BOS rejections in 38-48% range
    bos_38_48 = [r for r in rejections 
                 if r.strategy_type == 'continuation' and 38 <= r.retracement_pct < 48]
    
    # Count CHoCH rejections in 45-48% range
    choch_45_48 = [r for r in rejections 
                   if r.strategy_type == 'reversal' and 45 <= r.retracement_pct < 48]
    
    # Count edge cases at exactly 48-52%
    edge_cases = [r for r in rejections if 48 <= r.retracement_pct < 52]
    
    print(f"\n{Colors.BOLD}Critical Findings:{Colors.RESET}")
    
    if bos_38_48:
        print(f"\n{Colors.RED}🚨 ISSUE #1: BOS Rejections at 38-48%{Colors.RESET}")
        print(f"   Found: {len(bos_38_48)} BOS setups rejected")
        print(f"   Problem: Current filter requires 48%+ for ALL strategies")
        print(f"   Impact: Missing valid continuation trades in trending markets")
        print(f"\n   {Colors.CYAN}RECOMMENDATION:{Colors.RESET}")
        print(f"   - Implement calculate_equilibrium_continuity()")
        print(f"   - Relax Premium/Discount for BOS: 38-62% (instead of 48-52%)")
        print(f"   - Expected: +{len(bos_38_48)} more valid BOS setups")
    
    if choch_45_48:
        print(f"\n{Colors.YELLOW}⚠️  ISSUE #2: CHoCH Rejections at 45-48%{Colors.RESET}")
        print(f"   Found: {len(choch_45_48)} CHoCH setups rejected")
        print(f"   Problem: Borderline reversals (45-48%) rejected")
        print(f"   Impact: Missing some valid reversal setups")
        print(f"\n   {Colors.CYAN}RECOMMENDATION:{Colors.RESET}")
        print(f"   - Consider relaxing CHoCH threshold: 45-52% (instead of 48-52%)")
        print(f"   - Or keep strict 48-52% for CHoCH (more conservative)")
        print(f"   - Expected: +{len(choch_45_48)} more reversal setups if relaxed")
    
    if edge_cases:
        print(f"\n{Colors.RED}❌ ISSUE #3: Edge Cases at 48-52%{Colors.RESET}")
        print(f"   Found: {len(edge_cases)} setups rejected in tolerance range")
        print(f"   Problem: V8.1 tolerance (±2%) should accept these!")
        print(f"   Impact: BUG in validate_fvg_zone logic")
        print(f"\n   {Colors.CYAN}RECOMMENDATION:{Colors.RESET}")
        print(f"   - Review validate_fvg_zone() implementation")
        print(f"   - Verify tolerance buffer calculation")
        print(f"   - These SHOULD pass with current V8.1 logic")
    
    # Summary
    print(f"\n{Colors.BOLD}Implementation Priority:{Colors.RESET}")
    print(f"   1. {Colors.RED}HIGH:{Colors.RESET} Implement BOS relaxed threshold (38-62%)")
    print(f"   2. {Colors.YELLOW}MEDIUM:{Colors.RESET} Review CHoCH threshold (45% vs 48%)")
    print(f"   3. {Colors.RED}HIGH:{Colors.RESET} Fix edge cases in tolerance range")
    
    # Estimate impact
    total_rescued = len(bos_38_48) + len(choch_45_48)
    if rejections:
        rescue_pct = (total_rescued / len(rejections)) * 100
        print(f"\n{Colors.BOLD}Expected Impact:{Colors.RESET}")
        print(f"   Setups Rescued: {total_rescued} out of {len(rejections)} rejections ({rescue_pct:.1f}%)")
        print(f"   Focus: BOS continuations in trending markets")


def main():
    """Main audit execution"""
    
    # Pairs to scan
    pairs = ["EURJPY", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    
    print(f"\n{Colors.CYAN}{Colors.BOLD}")
    print("╔════════════════════════════════════════════════════════════════════════════════════════════════╗")
    print("║              FIBONACCI REJECTIONS AUDIT - Premium/Discount Filter Analysis                    ║")
    print("╚════════════════════════════════════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}\n")
    
    print(f"Date: {datetime.now().strftime('%B %d, %Y, %H:%M:%S')}")
    print(f"Pairs: {', '.join(pairs)}")
    print(f"Filter: V8.1 Premium/Discount (48-52% + 2% tolerance)")
    print(f"Goal: Identify ALL setups rejected ONLY by Premium/Discount filter\n")
    
    # Initialize
    print(f"{Colors.CYAN}Connecting to cTrader...{Colors.RESET}")
    client = CTraderCBotClient()
    detector = SMCDetector(swing_lookback=5, atr_multiplier=1.5)
    print(f"{Colors.GREEN}✅ Connected{Colors.RESET}\n")
    
    # Scan all pairs
    all_rejections = []
    
    for symbol in pairs:
        print(f"{Colors.CYAN}Scanning {symbol}...{Colors.RESET}", end=" ")
        rejections = scan_pair_for_rejections(symbol, detector, client)
        all_rejections.extend(rejections)
        print(f"{Colors.GREEN}✅ Found {len(rejections)} rejections{Colors.RESET}")
    
    # Summary
    print_header(f"SUMMARY: {len(all_rejections)} Total Rejections Found")
    
    if not all_rejections:
        print(f"{Colors.GREEN}✅ No rejections found - All setups passed Premium/Discount filter!{Colors.RESET}")
        print(f"   This is unexpected. Either:")
        print(f"   1. All signals have perfect 50%+ retracements (unlikely)")
        print(f"   2. No signals detected (check CHoCH/BOS detection)")
        print(f"   3. No FVGs formed after signals")
        return
    
    # Group by symbol
    print(f"\n{Colors.BOLD}Rejections by Symbol:{Colors.RESET}")
    for symbol in pairs:
        symbol_rejections = [r for r in all_rejections if r.symbol == symbol]
        if symbol_rejections:
            reversal_count = sum(1 for r in symbol_rejections if r.strategy_type == 'reversal')
            continuity_count = sum(1 for r in symbol_rejections if r.strategy_type == 'continuation')
            print(f"   {symbol}: {len(symbol_rejections)} total "
                  f"({reversal_count} Reversal, {continuity_count} Continuity)")
    
    # Detailed analysis
    analyze_rejections_by_retracement(all_rejections)
    analyze_rejections_by_strategy(all_rejections)
    
    # Show detailed examples
    print_subheader("📋 DETAILED EXAMPLES (First 10 Rejections)")
    
    for i, rejection in enumerate(all_rejections[:10], 1):
        emoji = "🟢" if rejection.direction == "bullish" else "🔴"
        strategy_emoji = "🔄" if rejection.strategy_type == "reversal" else "➡️"
        
        print(f"\n{Colors.BOLD}{i}. {emoji} {strategy_emoji} {rejection.symbol} "
              f"{rejection.direction.upper()} ({rejection.strategy_type.upper()}){Colors.RESET}")
        print(f"   Signal Price: {rejection.signal_price:.5f} (bar {rejection.signal_index})")
        print(f"   FVG Zone: {rejection.fvg_bottom:.5f} - {rejection.fvg_top:.5f}")
        print(f"   FVG Middle: {rejection.fvg_middle:.5f}")
        print(f"   Equilibrium (50%): {rejection.equilibrium:.5f}")
        print(f"   {Colors.CYAN}Retracement: {rejection.retracement_pct:.1f}%{Colors.RESET}")
        print(f"   Distance from 50%: {rejection.distance_from_50:+.2f}%")
        print(f"   {Colors.RED}Rejection: {rejection.reason}{Colors.RESET}")
    
    if len(all_rejections) > 10:
        print(f"\n{Colors.YELLOW}... and {len(all_rejections) - 10} more rejections{Colors.RESET}")
    
    # Generate recommendations
    generate_recommendations(all_rejections)
    
    # Final summary
    print_header("AUDIT COMPLETE")
    
    print(f"{Colors.BOLD}Key Metrics:{Colors.RESET}")
    print(f"   Total Rejections: {len(all_rejections)}")
    print(f"   Reversal (CHoCH): {sum(1 for r in all_rejections if r.strategy_type == 'reversal')}")
    print(f"   Continuity (BOS): {sum(1 for r in all_rejections if r.strategy_type == 'continuation')}")
    
    avg_retracement = sum(r.retracement_pct for r in all_rejections) / len(all_rejections)
    print(f"   Avg Retracement: {avg_retracement:.1f}%")
    
    # Critical range
    critical_range = [r for r in all_rejections if 38 <= r.retracement_pct < 48]
    if critical_range:
        critical_pct = (len(critical_range) / len(all_rejections)) * 100
        print(f"\n   {Colors.RED}🚨 {len(critical_range)} ({critical_pct:.1f}%) rejected at 38-48%{Colors.RESET}")
        print(f"   {Colors.RED}   → PERFECT for BOS continuations but REJECTED!{Colors.RESET}")
    
    print(f"\n{Colors.CYAN}For implementation plan, see recommendations above.{Colors.RESET}\n")


if __name__ == '__main__':
    main()
