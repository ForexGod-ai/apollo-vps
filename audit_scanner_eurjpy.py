#!/usr/bin/env python3
"""
🔍 AUDIT SCANNER - EURJPY Deep Dive
===================================

Diagnostic tool pentru a vedea EXACT unde este respins EURJPY în V8.0 filters.

Funcționalitate:
- Bypass open positions check (forțează analiza)
- Print ATR Filter details (Swing Highs/Lows validation)
- Print CHoCH detection (Bearish pe Daily?)
- Print FVG detection (unde se află?)
- Print Equilibrium calculation (Macro High/Low, 50% level)
- Print Premium/Discount validation (FVG în Premium zone?)
- Step-by-step rejection reasons

Utilizare:
    python3 audit_scanner_eurjpy.py

Autor: ФорексГод
Data: 27 Februarie 2026
Versiune: V8.0 Audit Tool
"""

import sys
import pandas as pd
from datetime import datetime
from typing import Optional, List
import json

# Import SMC Detector
from smc_detector import SMCDetector, SwingPoint, CHoCH, FVG
from ctrader_cbot_client import CTraderCBotClient

# ANSI Colors pentru terminal
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

# Configuration
SYMBOL = "EURJPY"
DAILY_BARS = 100
H4_BARS = 200
H1_BARS = 225

def print_banner():
    """Printează banner-ul aplicației."""
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}🔍 AUDIT SCANNER - EURJPY Deep Dive{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}{'='*80}{Colors.RESET}\n")
    print(f"{Colors.WHITE}Diagnostic tool pentru V8.0 filter analysis{Colors.RESET}")
    print(f"{Colors.WHITE}Symbol: {Colors.CYAN}{SYMBOL}{Colors.RESET}")
    print(f"{Colors.WHITE}Filters: ATR Prominence (1.5x) + Premium/Discount (50% Fib){Colors.RESET}")
    print(f"{Colors.WHITE}Date: {datetime.now().strftime('%d %B %Y, %H:%M:%S')}{Colors.RESET}\n")

def fetch_data(symbol: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
    """
    Fetch data from cTrader API.
    
    Args:
        symbol: Trading symbol (e.g., 'EURJPY')
        timeframe: 'D1', 'H4', 'H1'
        bars: Number of bars to fetch
    
    Returns:
        DataFrame with OHLC data or None on error
    """
    try:
        client = CTraderCBotClient()
        
        if not client.is_available():
            print(f"{Colors.RED}❌ cTrader cBot not available (localhost:8767){Colors.RESET}")
            return None
        
        df = client.get_historical_data(symbol, timeframe, bars)
        
        if df is not None and not df.empty:
            df = df.reset_index()
            print(f"{Colors.GREEN}✅ Fetched {len(df)} bars for {symbol} ({timeframe}){Colors.RESET}")
            return df
        else:
            print(f"{Colors.RED}❌ No data for {symbol} on {timeframe}{Colors.RESET}")
            return None
    
    except Exception as e:
        print(f"{Colors.RED}❌ Error fetching data: {e}{Colors.RESET}")
        return None

def print_separator(title: str):
    """Print section separator."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'─'*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}📊 {title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'─'*80}{Colors.RESET}\n")

def audit_atr_filter(detector: SMCDetector, df: pd.DataFrame):
    """
    Audit ATR Prominence Filter.
    
    Shows:
    - ATR value (14-period)
    - Prominence threshold (1.5x ATR)
    - Last 3 Swing Highs with validation
    - Last 3 Swing Lows with validation
    """
    print_separator("STEP 1: ATR PROMINENCE FILTER")
    
    # Calculate ATR
    atr = detector.calculate_atr(df, period=14)
    threshold = detector.atr_multiplier * atr
    
    print(f"{Colors.WHITE}ATR Settings:{Colors.RESET}")
    print(f"   Period: 14 bars")
    print(f"   ATR Value: {Colors.YELLOW}{atr:.5f}{Colors.RESET}")
    print(f"   Multiplier: {Colors.YELLOW}{detector.atr_multiplier}x{Colors.RESET}")
    print(f"   Prominence Threshold: {Colors.YELLOW}{threshold:.5f}{Colors.RESET}")
    print()
    
    # Detect Swing Highs
    swing_highs = detector.detect_swing_highs(df)
    print(f"{Colors.GREEN}✅ Swing Highs Detected: {len(swing_highs)}{Colors.RESET}")
    
    if swing_highs:
        print(f"\n{Colors.WHITE}Last 3 Swing Highs:{Colors.RESET}")
        for i, swing in enumerate(reversed(swing_highs[-3:]), 1):
            # Calculate prominence for this swing
            window_start = max(0, swing.index - detector.swing_lookback)
            window_end = min(len(df), swing.index + detector.swing_lookback + 1)
            window_lows = df['low'].iloc[window_start:window_end]
            lowest_low = window_lows.min()
            swing_range = swing.price - lowest_low
            
            is_valid = swing_range >= threshold if threshold > 0 else True
            status = f"{Colors.GREEN}✅ VALID{Colors.RESET}" if is_valid else f"{Colors.RED}❌ REJECTED{Colors.RESET}"
            
            print(f"   #{i} Bar Index: {Colors.CYAN}{swing.index}{Colors.RESET}")
            print(f"      Price: {Colors.YELLOW}{swing.price:.5f}{Colors.RESET}")
            print(f"      Time: {Colors.WHITE}{swing.candle_time}{Colors.RESET}")
            print(f"      Range: {Colors.YELLOW}{swing_range:.5f}{Colors.RESET} ({swing_range/atr:.2f}x ATR)")
            print(f"      Status: {status}")
            print()
    else:
        print(f"{Colors.RED}   ❌ No Swing Highs detected{Colors.RESET}\n")
    
    # Detect Swing Lows
    swing_lows = detector.detect_swing_lows(df)
    print(f"{Colors.GREEN}✅ Swing Lows Detected: {len(swing_lows)}{Colors.RESET}")
    
    if swing_lows:
        print(f"\n{Colors.WHITE}Last 3 Swing Lows:{Colors.RESET}")
        for i, swing in enumerate(reversed(swing_lows[-3:]), 1):
            # Calculate prominence for this swing
            window_start = max(0, swing.index - detector.swing_lookback)
            window_end = min(len(df), swing.index + detector.swing_lookback + 1)
            window_highs = df['high'].iloc[window_start:window_end]
            highest_high = window_highs.max()
            swing_range = highest_high - swing.price
            
            is_valid = swing_range >= threshold if threshold > 0 else True
            status = f"{Colors.GREEN}✅ VALID{Colors.RESET}" if is_valid else f"{Colors.RED}❌ REJECTED{Colors.RESET}"
            
            print(f"   #{i} Bar Index: {Colors.CYAN}{swing.index}{Colors.RESET}")
            print(f"      Price: {Colors.YELLOW}{swing.price:.5f}{Colors.RESET}")
            print(f"      Time: {Colors.WHITE}{swing.candle_time}{Colors.RESET}")
            print(f"      Range: {Colors.YELLOW}{swing_range:.5f}{Colors.RESET} ({swing_range/atr:.2f}x ATR)")
            print(f"      Status: {status}")
            print()
    else:
        print(f"{Colors.RED}   ❌ No Swing Lows detected{Colors.RESET}\n")
    
    return swing_highs, swing_lows

def audit_choch_detection(detector: SMCDetector, df: pd.DataFrame):
    """
    Audit CHoCH and BOS detection.
    
    Shows:
    - Daily CHoCH detected (Bearish expected?)
    - CHoCH direction, price, bar index
    - Daily BOS detected
    """
    print_separator("STEP 2: CHoCH & BOS DETECTION")
    
    chochs, bos_list = detector.detect_choch_and_bos(df)
    
    print(f"{Colors.WHITE}CHoCH Detection:{Colors.RESET}")
    print(f"   Total CHoCH: {Colors.YELLOW}{len(chochs)}{Colors.RESET}")
    
    if chochs:
        print(f"\n{Colors.WHITE}Last 3 CHoCH:{Colors.RESET}")
        for i, choch in enumerate(reversed(chochs[-3:]), 1):
            direction_color = Colors.GREEN if choch.direction == 'bullish' else Colors.RED
            direction_emoji = "🟢" if choch.direction == 'bullish' else "🔴"
            
            print(f"   {direction_emoji} #{i} Direction: {direction_color}{choch.direction.upper()}{Colors.RESET}")
            print(f"      Break Price: {Colors.YELLOW}{choch.break_price:.5f}{Colors.RESET}")
            print(f"      Bar Index: {Colors.CYAN}{choch.index}{Colors.RESET}")
            if hasattr(choch, 'swing_broken') and choch.swing_broken:
                print(f"      Swing Broken: {Colors.WHITE}{choch.swing_broken.price:.5f}{Colors.RESET} (bar {choch.swing_broken.index})")
            print()
    else:
        print(f"{Colors.RED}   ❌ No CHoCH detected{Colors.RESET}\n")
    
    print(f"{Colors.WHITE}BOS Detection:{Colors.RESET}")
    print(f"   Total BOS: {Colors.YELLOW}{len(bos_list)}{Colors.RESET}")
    
    if bos_list:
        print(f"\n{Colors.WHITE}Last 3 BOS:{Colors.RESET}")
        for i, bos in enumerate(reversed(bos_list[-3:]), 1):
            direction_color = Colors.GREEN if bos.direction == 'bullish' else Colors.RED
            direction_emoji = "🟢" if bos.direction == 'bullish' else "🔴"
            
            print(f"   {direction_emoji} #{i} Direction: {direction_color}{bos.direction.upper()}{Colors.RESET}")
            print(f"      Break Price: {Colors.YELLOW}{bos.break_price:.5f}{Colors.RESET}")
            print(f"      Bar Index: {Colors.CYAN}{bos.index}{Colors.RESET}")
            print()
    else:
        print(f"{Colors.RED}   ❌ No BOS detected{Colors.RESET}\n")
    
    return chochs, bos_list

def audit_fvg_detection(detector: SMCDetector, df: pd.DataFrame, latest_signal, current_price: float):
    """
    Audit FVG detection.
    
    Shows:
    - FVG detected after latest CHoCH/BOS?
    - FVG direction, zone (top/bottom/middle)
    - Current price vs FVG zone
    """
    print_separator("STEP 3: FVG DETECTION")
    
    if not latest_signal:
        print(f"{Colors.RED}❌ No CHoCH/BOS signal to detect FVG after{Colors.RESET}\n")
        return None
    
    print(f"{Colors.WHITE}Latest Signal:{Colors.RESET}")
    direction_color = Colors.GREEN if latest_signal.direction == 'bullish' else Colors.RED
    print(f"   Direction: {direction_color}{latest_signal.direction.upper()}{Colors.RESET}")
    print(f"   Bar Index: {Colors.CYAN}{latest_signal.index}{Colors.RESET}")
    print()
    
    # Detect FVG
    fvg = detector.detect_fvg(df, latest_signal, current_price)
    
    if fvg:
        print(f"{Colors.GREEN}✅ FVG Detected:{Colors.RESET}")
        direction_color = Colors.GREEN if fvg.direction == 'bullish' else Colors.RED
        print(f"   Direction: {direction_color}{fvg.direction.upper()}{Colors.RESET}")
        print(f"   Top: {Colors.YELLOW}{fvg.top:.5f}{Colors.RESET}")
        print(f"   Middle: {Colors.YELLOW}{fvg.middle:.5f}{Colors.RESET}")
        print(f"   Bottom: {Colors.YELLOW}{fvg.bottom:.5f}{Colors.RESET}")
        print(f"   Bar Index: {Colors.CYAN}{fvg.index}{Colors.RESET}")
        print()
        
        # Check if price is in FVG
        in_fvg = fvg.bottom <= current_price <= fvg.top
        status = f"{Colors.GREEN}✅ IN FVG{Colors.RESET}" if in_fvg else f"{Colors.YELLOW}⚠️ NOT IN FVG{Colors.RESET}"
        print(f"   Current Price: {Colors.YELLOW}{current_price:.5f}{Colors.RESET}")
        print(f"   Price in FVG: {status}")
        print()
    else:
        print(f"{Colors.RED}❌ No FVG detected{Colors.RESET}\n")
    
    return fvg

def audit_premium_discount(detector: SMCDetector, df: pd.DataFrame, swing_highs: List[SwingPoint], swing_lows: List[SwingPoint], fvg: Optional[FVG], latest_signal):
    """
    Audit Premium/Discount Zone validation.
    
    Shows:
    - Macro High (last swing high)
    - Macro Low (last swing low)
    - Equilibrium (50% level)
    - FVG position vs Equilibrium
    - Premium/Discount validation result
    """
    print_separator("STEP 4: PREMIUM/DISCOUNT ZONE VALIDATION")
    
    if not fvg:
        print(f"{Colors.RED}❌ No FVG to validate (skipped){Colors.RESET}\n")
        return None
    
    if not swing_highs or not swing_lows:
        print(f"{Colors.RED}❌ Insufficient swings for equilibrium calculation{Colors.RESET}\n")
        return None
    
    # Calculate Equilibrium
    equilibrium = detector.calculate_equilibrium(df, swing_highs, swing_lows)
    
    if equilibrium is None:
        print(f"{Colors.RED}❌ Could not calculate equilibrium{Colors.RESET}\n")
        return None
    
    print(f"{Colors.WHITE}Macro Swing Leg:{Colors.RESET}")
    print(f"   Macro High: {Colors.YELLOW}{swing_highs[-1].price:.5f}{Colors.RESET} (bar {swing_highs[-1].index})")
    print(f"   Macro Low: {Colors.YELLOW}{swing_lows[-1].price:.5f}{Colors.RESET} (bar {swing_lows[-1].index})")
    print(f"   Equilibrium (50%): {Colors.CYAN}{equilibrium:.5f}{Colors.RESET}")
    print()
    
    print(f"{Colors.WHITE}FVG Position:{Colors.RESET}")
    print(f"   FVG Top: {Colors.YELLOW}{fvg.top:.5f}{Colors.RESET}")
    print(f"   FVG Middle: {Colors.YELLOW}{fvg.middle:.5f}{Colors.RESET}")
    print(f"   FVG Bottom: {Colors.YELLOW}{fvg.bottom:.5f}{Colors.RESET}")
    print()
    
    # Calculate position relative to equilibrium
    fvg_above_eq = fvg.bottom >= equilibrium
    fvg_below_eq = fvg.top <= equilibrium
    fvg_middle_above = fvg.middle > equilibrium
    fvg_middle_below = fvg.middle < equilibrium
    
    distance_pct = ((fvg.middle - equilibrium) / equilibrium) * 100
    
    print(f"{Colors.WHITE}Equilibrium Analysis:{Colors.RESET}")
    print(f"   Distance from 50%: {Colors.YELLOW}{distance_pct:+.2f}%{Colors.RESET}")
    
    if fvg_above_eq:
        print(f"   Zone: {Colors.CYAN}PREMIUM{Colors.RESET} (FVG completely above 50%)")
    elif fvg_below_eq:
        print(f"   Zone: {Colors.CYAN}DISCOUNT{Colors.RESET} (FVG completely below 50%)")
    elif fvg_middle_above:
        print(f"   Zone: {Colors.CYAN}PREMIUM{Colors.RESET} (FVG middle above 50%)")
    elif fvg_middle_below:
        print(f"   Zone: {Colors.CYAN}DISCOUNT{Colors.RESET} (FVG middle below 50%)")
    else:
        print(f"   Zone: {Colors.YELLOW}AT EQUILIBRIUM{Colors.RESET} (FVG at 50%)")
    print()
    
    # Validate with detector
    is_valid = detector.validate_fvg_zone(fvg, equilibrium, latest_signal.direction, debug=True)
    
    print()
    
    if is_valid:
        print(f"{Colors.GREEN}✅ PREMIUM/DISCOUNT VALIDATION PASSED{Colors.RESET}")
        zone_type = "PREMIUM" if latest_signal.direction == 'bearish' else "DISCOUNT"
        print(f"   Setup: {latest_signal.direction.upper()}")
        print(f"   Required Zone: {zone_type}")
        print(f"   FVG in correct zone: YES")
    else:
        print(f"{Colors.RED}❌ PREMIUM/DISCOUNT VALIDATION FAILED{Colors.RESET}")
        zone_type = "PREMIUM" if latest_signal.direction == 'bearish' else "DISCOUNT"
        print(f"   Setup: {latest_signal.direction.upper()}")
        print(f"   Required Zone: {zone_type}")
        print(f"   FVG in correct zone: NO")
        
        if latest_signal.direction == 'bearish':
            print(f"   {Colors.YELLOW}⚠️ BEARISH setup requires FVG ABOVE 50% (Premium){Colors.RESET}")
            print(f"   {Colors.YELLOW}⚠️ This FVG is BELOW/AT 50% (Discount) - shallow retracement{Colors.RESET}")
        else:
            print(f"   {Colors.YELLOW}⚠️ BULLISH setup requires FVG BELOW 50% (Discount){Colors.RESET}")
            print(f"   {Colors.YELLOW}⚠️ This FVG is ABOVE/AT 50% (Premium) - shallow retracement{Colors.RESET}")
    
    print()
    
    return is_valid

def main():
    """Main entry point."""
    print_banner()
    
    # Step 0: Fetch Data
    print_separator("STEP 0: DATA FETCHING")
    
    df_daily = fetch_data(SYMBOL, "D1", DAILY_BARS)
    
    if df_daily is None or df_daily.empty:
        print(f"\n{Colors.RED}❌ FAILED: Could not fetch Daily data for {SYMBOL}{Colors.RESET}\n")
        return 1
    
    current_price = df_daily['close'].iloc[-1]
    print(f"\n{Colors.WHITE}Current Price: {Colors.YELLOW}{current_price:.5f}{Colors.RESET}\n")
    
    # Initialize SMC Detector with V8.0 settings
    detector = SMCDetector(swing_lookback=5, atr_multiplier=1.5)
    print(f"{Colors.GREEN}✅ SMC Detector initialized (swing_lookback=5, atr_multiplier=1.5){Colors.RESET}\n")
    
    # Step 1: ATR Filter
    swing_highs, swing_lows = audit_atr_filter(detector, df_daily)
    
    if not swing_highs or not swing_lows:
        print(f"\n{Colors.RED}{'='*80}{Colors.RESET}")
        print(f"{Colors.RED}❌ REJECTION POINT: ATR PROMINENCE FILTER{Colors.RESET}")
        print(f"{Colors.RED}{'='*80}{Colors.RESET}\n")
        print(f"{Colors.YELLOW}Reason: No valid swing highs/lows detected (not prominent enough){Colors.RESET}")
        print(f"{Colors.YELLOW}This means price structure is too choppy/noisy for V8.0 filters{Colors.RESET}\n")
        return 0
    
    # Step 2: CHoCH & BOS
    chochs, bos_list = audit_choch_detection(detector, df_daily)
    
    if not chochs and not bos_list:
        print(f"\n{Colors.RED}{'='*80}{Colors.RESET}")
        print(f"{Colors.RED}❌ REJECTION POINT: NO CHoCH/BOS DETECTED{Colors.RESET}")
        print(f"{Colors.RED}{'='*80}{Colors.RESET}\n")
        print(f"{Colors.YELLOW}Reason: No Change of Character or Break of Structure detected{Colors.RESET}")
        print(f"{Colors.YELLOW}This means no clear trend change or continuation signal{Colors.RESET}\n")
        return 0
    
    # Get latest signal (CHoCH or BOS, whichever is more recent)
    latest_choch = chochs[-1] if chochs else None
    latest_bos = bos_list[-1] if bos_list else None
    
    if latest_choch and latest_bos:
        latest_signal = latest_choch if latest_choch.index > latest_bos.index else latest_bos
    elif latest_choch:
        latest_signal = latest_choch
    else:
        latest_signal = latest_bos
    
    # Step 3: FVG Detection
    fvg = audit_fvg_detection(detector, df_daily, latest_signal, current_price)
    
    if not fvg:
        print(f"\n{Colors.RED}{'='*80}{Colors.RESET}")
        print(f"{Colors.RED}❌ REJECTION POINT: NO FVG DETECTED{Colors.RESET}")
        print(f"{Colors.RED}{'='*80}{Colors.RESET}\n")
        print(f"{Colors.YELLOW}Reason: No Fair Value Gap found after CHoCH/BOS{Colors.RESET}")
        print(f"{Colors.YELLOW}This means no inefficiency (gap) in price delivery{Colors.RESET}\n")
        return 0
    
    # Step 4: Premium/Discount Validation
    is_valid = audit_premium_discount(detector, df_daily, swing_highs, swing_lows, fvg, latest_signal)
    
    if is_valid is None:
        print(f"\n{Colors.YELLOW}{'='*80}{Colors.RESET}")
        print(f"{Colors.YELLOW}⚠️ SKIPPED: PREMIUM/DISCOUNT VALIDATION{Colors.RESET}")
        print(f"{Colors.YELLOW}{'='*80}{Colors.RESET}\n")
        print(f"{Colors.WHITE}Reason: Could not calculate equilibrium or missing FVG{Colors.RESET}\n")
        return 0
    
    if not is_valid:
        print(f"\n{Colors.RED}{'='*80}{Colors.RESET}")
        print(f"{Colors.RED}❌ REJECTION POINT: PREMIUM/DISCOUNT FILTER{Colors.RESET}")
        print(f"{Colors.RED}{'='*80}{Colors.RESET}\n")
        print(f"{Colors.YELLOW}Reason: FVG in wrong zone (shallow retracement <50%){Colors.RESET}")
        print(f"{Colors.YELLOW}This is a retail inducement zone - avoid entry{Colors.RESET}\n")
        return 0
    
    # Success!
    print(f"\n{Colors.GREEN}{'='*80}{Colors.RESET}")
    print(f"{Colors.GREEN}✅ ALL V8.0 FILTERS PASSED!{Colors.RESET}")
    print(f"{Colors.GREEN}{'='*80}{Colors.RESET}\n")
    print(f"{Colors.WHITE}EURJPY setup is VALID according to V8.0 filters:{Colors.RESET}")
    print(f"   ✅ ATR Prominence: Swing structure validated (1.5x ATR)")
    print(f"   ✅ CHoCH/BOS: Detected (direction: {latest_signal.direction.upper()})")
    print(f"   ✅ FVG: Detected ({fvg.direction.upper()} @ {fvg.middle:.5f})")
    print(f"   ✅ Premium/Discount: FVG in correct zone (>50% retracement)")
    print()
    print(f"{Colors.CYAN}🎯 Setup should appear in daily_scanner.py results!{Colors.RESET}")
    print(f"{Colors.CYAN}If not, check 4H CHoCH confirmation or other filters.{Colors.RESET}\n")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}❌ Audit cancelled by user (Ctrl+C).{Colors.RESET}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}❌ FATAL ERROR: {e}{Colors.RESET}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
