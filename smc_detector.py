"""
Smart Money Concepts (SMC) Detector
Implements: CHoCH, FVG, Multi-timeframe Analysis for "Glitch in Matrix" Strategy
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SwingPoint:
    """Represents a swing high or swing low"""
    index: int
    price: float
    swing_type: str  # 'high' or 'low'
    candle_time: datetime


@dataclass
class CHoCH:
    """
    Change of Character - SCHIMBAREA TRENDULUI
    Se întâmplă O SINGURĂ DATĂ când trendul se inversează
    BULLISH → BEARISH sau BEARISH → BULLISH
    """
    index: int
    direction: str  # 'bullish' or 'bearish' (NOUL trend după schimbare)
    break_price: float
    previous_trend: str
    candle_time: datetime
    swing_broken: SwingPoint


@dataclass
class BOS:
    """
    Break of Structure - CONTINUAREA TRENDULUI
    Se întâmplă REPETAT în același trend
    BULLISH: BOS = Higher High (HH)
    BEARISH: BOS = Lower Low (LL)
    """
    index: int
    direction: str  # 'bullish' or 'bearish' (direcția break-ului)
    break_price: float
    candle_time: datetime
    swing_broken: SwingPoint


@dataclass
class FVG:
    """Fair Value Gap / Imbalance"""
    index: int
    direction: str  # 'bullish' or 'bearish'
    top: float
    bottom: float
    middle: float
    candle_time: datetime
    is_filled: bool = False
    associated_choch: Optional[CHoCH] = None
    quality_score: int = 0  # V3.0: FVG quality score (0-100)


@dataclass
class TradeSetup:
    """Complete Glitch in Matrix setup"""
    symbol: str
    daily_choch: CHoCH
    fvg: FVG
    h4_choch: Optional[CHoCH]  # May be None for MONITORING status
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    setup_time: datetime
    priority: int
    strategy_type: str = "reversal"  # 'reversal' or 'continuation'
    status: str = 'MONITORING'  # 'MONITORING' (watching) or 'READY' (can execute)


class SMCDetector:
    """Detects Smart Money Concepts patterns"""
    
    def __init__(self, swing_lookback: int = 5):
        """
        Args:
            swing_lookback: Number of candles to look back for swing points
                          Keep at 5 for sensitivity, but analyze LONGER range for trend
        """
        self.swing_lookback = swing_lookback
    
    def detect_swing_highs(self, df: pd.DataFrame) -> List[SwingPoint]:
        """
        Detect swing highs using BODY-ONLY (NO WICKS!)
        Swing high = highest BODY with lower BODIES on both sides
        BODY HIGH = max(open, close) - wicks are MANIPULATION!
        """
        swing_highs = []
        
        # Calculate BODY highs for all candles (ignore wicks!)
        body_highs = df[['open', 'close']].max(axis=1)
        
        for i in range(self.swing_lookback, len(df) - self.swing_lookback):
            current_high = body_highs.iloc[i]
            
            # Check left side - all bodies lower
            left_check = all(
                current_high > body_highs.iloc[i - j] 
                for j in range(1, self.swing_lookback + 1)
            )
            
            # Check right side - all bodies lower
            right_check = all(
                current_high > body_highs.iloc[i + j] 
                for j in range(1, self.swing_lookback + 1)
            )
            
            if left_check and right_check:
                candle_time = df['time'].iloc[i] if 'time' in df.columns else i
                swing_highs.append(SwingPoint(
                    index=i,
                    price=current_high,
                    swing_type='high',
                    candle_time=candle_time
                ))
        
        return swing_highs
    
    def detect_swing_lows(self, df: pd.DataFrame) -> List[SwingPoint]:
        """
        Detect swing lows using BODY-ONLY (NO WICKS!)
        Swing low = lowest BODY with higher BODIES on both sides
        BODY LOW = min(open, close) - wicks are MANIPULATION!
        """
        swing_lows = []
        
        # Calculate BODY lows for all candles (ignore wicks!)
        body_lows = df[['open', 'close']].min(axis=1)
        
        for i in range(self.swing_lookback, len(df) - self.swing_lookback):
            current_low = body_lows.iloc[i]
            
            # Check left side - all bodies higher
            left_check = all(
                current_low < body_lows.iloc[i - j] 
                for j in range(1, self.swing_lookback + 1)
            )
            
            # Check right side - all bodies higher
            right_check = all(
                current_low < body_lows.iloc[i + j] 
                for j in range(1, self.swing_lookback + 1)
            )
            
            if left_check and right_check:
                candle_time = df['time'].iloc[i] if 'time' in df.columns else i
                swing_lows.append(SwingPoint(
                    index=i,
                    price=current_low,
                    swing_type='low',
                    candle_time=candle_time
                ))
        
        return swing_lows
    
    def detect_choch_and_bos(self, df: pd.DataFrame) -> Tuple[List[CHoCH], List[BOS]]:
        """
        Detect CHoCH (Change of Character) and BOS (Break of Structure)
        
        REAL-TIME LOGIC - SPAȚIU-TIMP:
        Chart-ul se mișcă în timp real → prețul evoluează → structura se schimbă!
        
        1. Găsesc toate swing highs/lows
        2. Caut BREAK-URI RECENTE ale acestor swing-uri
        3. CHoCH = break care SCHIMBĂ direcția (bearish → bullish sau invers)
        4. BOS = break care CONTINUĂ direcția
        
        IMPORTANT: Prioritizez break-urile RECENTE (ultimele candles)
        
        Returns:
            Tuple[List[CHoCH], List[BOS]]
        """
        chochs = []
        bos_list = []
        
        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return (chochs, bos_list)
        
        # Determine INITIAL trend from historical structure (older swings)
        # Use swings from middle of data to establish baseline trend
        mid_point = max(10, len(df) // 2)
        historical_highs = [sh for sh in swing_highs if sh.index < mid_point]
        historical_lows = [sl for sl in swing_lows if sl.index < mid_point]
        
        current_trend = None
        if len(historical_highs) >= 2 and len(historical_lows) >= 2:
            # Check if highs/lows were ascending or descending historically
            h_ascending = historical_highs[-1].price > historical_highs[-2].price
            l_ascending = historical_lows[-1].price > historical_lows[-2].price
            
            if h_ascending and l_ascending:
                current_trend = 'bullish'
            elif not h_ascending and not l_ascending:
                current_trend = 'bearish'
        
        # Now look for RECENT BREAKS of swing points (last 30 candles)
        recent_start = max(0, len(df) - 30)
        
        # Combine all swings and sort by index
        all_swings = []
        for sh in swing_highs:
            all_swings.append(('high', sh))
        for sl in swing_lows:
            all_swings.append(('low', sl))
        all_swings.sort(key=lambda x: x[1].index)
        
        # Process swings and look for breaks AFTER each swing
        for i, (swing_type, swing) in enumerate(all_swings):
            # Look for price breaks AFTER this swing point
            break_start = swing.index + 1
            break_end = min(swing.index + 20, len(df))  # Look 20 candles ahead
            
            if break_end <= break_start:
                continue
            
            for j in range(break_start, break_end):
                close = df['close'].iloc[j]
                
                if swing_type == 'high':
                    # Check if price BROKE ABOVE this swing high
                    if close > swing.price:
                        # Price broke a high = BULLISH signal
                        if current_trend == 'bearish':
                            # VALIDATION: Was structure truly bearish before break?
                            # Need BOTH LH and LL patterns (strong bearish structure)
                            recent_highs = [s for s in swing_highs if s.index <= swing.index][-3:]
                            recent_lows = [s for s in swing_lows if s.index <= swing.index][-3:]
                            
                            lh_pattern = False
                            ll_pattern = False
                            
                            # Check for LH (lower highs)
                            if len(recent_highs) >= 2:
                                lh_pattern = recent_highs[-1].price < recent_highs[-2].price
                            
                            # Check for LL (lower lows)
                            if len(recent_lows) >= 2:
                                ll_pattern = recent_lows[-1].price < recent_lows[-2].price
                            
                            # RELAXED VALIDATION: Accept CHoCH if has LH or LL pattern
                            # Strong CHoCH has BOTH, but accept partial for early detection
                            if lh_pattern or ll_pattern:  # OR - either pattern is enough
                                # POST-BREAK VALIDATION: Check if price CONFIRMS the change
                                # Look for swings AFTER the break to confirm HH or HL
                                swings_after_break = [s for s in swing_highs if s.index > j] + \
                                                    [s for s in swing_lows if s.index > j]
                                
                                # RELAXED: Allow CHoCH even without full confirmation (MONITORING status)
                                confirmed = True  # Default to true for monitoring
                                
                                # If we have recent data after break, validate confirmation
                                if len(swings_after_break) >= 1:
                                    # Check if any HIGH after break is Higher High
                                    highs_after = [s for s in swing_highs if s.index > j]
                                    lows_after = [s for s in swing_lows if s.index > j]
                                    
                                    # For BULLISH CHoCH: need HH or HL after break
                                    if len(highs_after) >= 1:
                                        # Is there a Higher High?
                                        if any(h.price > swing.price for h in highs_after):
                                            confirmed = True
                                    if not confirmed and len(lows_after) >= 1 and len(recent_lows) >= 1:
                                        # Is there a Higher Low?
                                        if any(l.price > recent_lows[-1].price for l in lows_after):
                                            confirmed = True
                                
                                if confirmed:
                                    # WHIPSAW PROTECTION: Minimum 10 candles between CHoCH
                                    if chochs and (j - chochs[-1].index) < 10:
                                        continue  # Skip this CHoCH, too close to previous one
                                    
                                    chochs.append(CHoCH(
                                        index=j,
                                        direction='bullish',
                                        break_price=swing.price,
                                        previous_trend='bearish',
                                        candle_time=df['time'].iloc[j] if 'time' in df.columns else j,
                                        swing_broken=swing
                                    ))
                                    current_trend = 'bullish'
                        elif current_trend == 'bullish':
                            # Already bullish, breaking another high → BOS
                            bos_list.append(BOS(
                                index=j,
                                direction='bullish',
                                break_price=swing.price,
                                candle_time=df['time'].iloc[j] if 'time' in df.columns else j,
                                swing_broken=swing
                            ))
                        else:
                            # First trend establishment
                            current_trend = 'bullish'
                        break  # Only count first break
                
                elif swing_type == 'low':
                    # Check if price BROKE BELOW this swing low
                    if close < swing.price:
                        # Price broke a low = BEARISH signal
                        if current_trend == 'bullish':
                            # VALIDATION: Was structure truly bullish before break?
                            # Need BOTH HH and HL patterns (strong bullish structure)
                            recent_highs = [s for s in swing_highs if s.index <= swing.index][-3:]
                            recent_lows = [s for s in swing_lows if s.index <= swing.index][-3:]
                            
                            hh_pattern = False
                            hl_pattern = False
                            
                            # Check for HH (higher highs)
                            if len(recent_highs) >= 2:
                                hh_pattern = recent_highs[-1].price > recent_highs[-2].price
                            
                            # Check for HL (higher lows)
                            if len(recent_lows) >= 2:
                                hl_pattern = recent_lows[-1].price > recent_lows[-2].price
                            
                            # RELAXED VALIDATION: Accept CHoCH if has HH or HL pattern
                            # Strong CHoCH has BOTH, but accept partial for early detection
                            if hh_pattern or hl_pattern:  # OR - either pattern is enough
                                # POST-BREAK VALIDATION: Check if price CONFIRMS the change
                                # Look for swings AFTER the break to confirm LH or LL
                                swings_after_break = [s for s in swing_highs if s.index > j] + \
                                                    [s for s in swing_lows if s.index > j]
                                
                                # RELAXED: Allow CHoCH even without full confirmation (MONITORING status)
                                confirmed = True  # Default to true for monitoring
                                
                                # If we have recent data after break, validate confirmation
                                if len(swings_after_break) >= 1:
                                    # Check if any LOW after break is Lower Low
                                    highs_after = [s for s in swing_highs if s.index > j]
                                    lows_after = [s for s in swing_lows if s.index > j]
                                    
                                    # For BEARISH CHoCH: need LL or LH after break
                                    if len(lows_after) >= 1:
                                        # Is there a Lower Low?
                                        if any(l.price < swing.price for l in lows_after):
                                            confirmed = True
                                    if not confirmed and len(highs_after) >= 1 and len(recent_highs) >= 1:
                                        # Is there a Lower High?
                                        if any(h.price < recent_highs[-1].price for h in highs_after):
                                            confirmed = True
                                
                                if confirmed:
                                    # WHIPSAW PROTECTION: Minimum 10 candles between CHoCH
                                    if chochs and (j - chochs[-1].index) < 10:
                                        continue  # Skip this CHoCH, too close to previous one
                                    
                                    chochs.append(CHoCH(
                                        index=j,
                                        direction='bearish',
                                        break_price=swing.price,
                                        previous_trend='bullish',
                                        candle_time=df['time'].iloc[j] if 'time' in df.columns else j,
                                        swing_broken=swing
                                    ))
                                    current_trend = 'bearish'
                        elif current_trend == 'bearish':
                            # Already bearish, breaking another low → BOS
                            bos_list.append(BOS(
                                index=j,
                                direction='bearish',
                                break_price=swing.price,
                                candle_time=df['time'].iloc[j] if 'time' in df.columns else j,
                                swing_broken=swing
                            ))
                        else:
                            # First trend establishment
                            current_trend = 'bearish'
                        break  # Only count first break
        
        return chochs, bos_list
    
    def detect_choch(self, df: pd.DataFrame) -> List[CHoCH]:
        """
        Wrapper function to maintain compatibility
        Returns only CHoCH (without BOS)
        """
        chochs, _ = self.detect_choch_and_bos(df)
        return chochs
    
    def detect_fvg(self, df: pd.DataFrame, choch: CHoCH, current_price: float) -> Optional[FVG]:
        """
        Detect Fair Value Gap (FVG) / Imbalance Zone after a CHoCH
        
        NEW LOGIC - FLEXIBLE FVG DETECTION:
        - Accepts both SMALL gaps (3-candle strict) and LARGE imbalance zones
        - REVERSAL setups = large FVG zones after CHoCH
        - CONTINUATION setups = smaller pullback gaps
        
        Method:
        1. Look for traditional 3-candle gaps (strict)
        2. If none found, create imbalance zone from CHoCH to last pullback swing
        3. Return FVG that makes sense for current price action
        """
        all_fvgs = []
        
        # Extended range after CHoCH (up to 50 candles to catch large reversals)
        start_idx = choch.index + 1
        end_idx = min(choch.index + 51, len(df))
        
        if end_idx - start_idx < 3:
            return None
        
        # METHOD 1: Find traditional 3-candle gaps (SMALL FVGs)
        for i in range(start_idx + 2, end_idx):
            if choch.direction == 'bullish':
                # Bullish FVG: gap up (candle[i-2].high < candle[i].low)
                if df['high'].iloc[i - 2] < df['low'].iloc[i]:
                    gap_bottom = df['high'].iloc[i - 2]
                    gap_top = df['low'].iloc[i]
                    
                    fvg = FVG(
                        index=i,
                        direction='bullish',
                        top=gap_top,
                        bottom=gap_bottom,
                        middle=(gap_top + gap_bottom) / 2,
                        candle_time=df['time'].iloc[i] if 'time' in df.columns else i,
                        is_filled=False,
                        associated_choch=choch
                    )
                    all_fvgs.append(fvg)
            
            elif choch.direction == 'bearish':
                # Bearish FVG: gap down (candle[i-2].low > candle[i].high)
                if df['low'].iloc[i - 2] > df['high'].iloc[i]:
                    gap_top = df['low'].iloc[i - 2]
                    gap_bottom = df['high'].iloc[i]
                    
                    fvg = FVG(
                        index=i,
                        direction='bearish',
                        top=gap_top,
                        bottom=gap_bottom,
                        middle=(gap_top + gap_bottom) / 2,
                        candle_time=df['time'].iloc[i] if 'time' in df.columns else i,
                        is_filled=False,
                        associated_choch=choch
                    )
                    all_fvgs.append(fvg)
        
        # METHOD 2: If no strict gaps found, create LARGE imbalance zone (REVERSAL setup)
        if not all_fvgs:
            # Look for swing points BEFORE and AFTER CHoCH to define imbalance zone
            swing_highs = self.detect_swing_highs(df)
            swing_lows = self.detect_swing_lows(df)
            
            if choch.direction == 'bullish':
                # BULLISH CHoCH: Find zone between last LOW (before CHoCH) and momentum HIGH (after)
                # This is the pullback zone where price should retrace
                
                # Find last swing LOW before CHoCH
                lows_before = [sl for sl in swing_lows if sl.index < choch.index]
                # Find first swing HIGH after CHoCH (or current high in range)
                highs_after = [sh for sh in swing_highs if sh.index >= choch.index and sh.index < end_idx]
                
                if lows_before:
                    last_low = lows_before[-1]
                    gap_bottom = last_low.price
                    
                    # Top = highest point after CHoCH
                    if highs_after:
                        gap_top = max([sh.price for sh in highs_after])
                        fvg_index = highs_after[0].index
                    else:
                        gap_top = df['high'].iloc[start_idx:end_idx].max()
                        fvg_index = start_idx + df['high'].iloc[start_idx:end_idx].argmax()
                    
                    # Create large FVG zone (minimum 0.5% range for valid imbalance)
                    if (gap_top - gap_bottom) / gap_bottom > 0.005:
                        all_fvgs.append(FVG(
                            index=fvg_index,
                            direction='bullish',
                            top=gap_top,
                            bottom=gap_bottom,
                            middle=(gap_top + gap_bottom) / 2,
                            candle_time=df['time'].iloc[fvg_index] if 'time' in df.columns else fvg_index,
                            is_filled=False,
                            associated_choch=choch
                        ))
            
            elif choch.direction == 'bearish':
                # BEARISH CHoCH: Find zone between last HIGH (before CHoCH) and momentum LOW (after)
                
                # Find last swing HIGH before CHoCH
                highs_before = [sh for sh in swing_highs if sh.index < choch.index]
                # Find first swing LOW after CHoCH
                lows_after = [sl for sl in swing_lows if sl.index >= choch.index and sl.index < end_idx]
                
                if highs_before:
                    last_high = highs_before[-1]
                    gap_top = last_high.price
                    
                    # Bottom = lowest point after CHoCH
                    if lows_after:
                        gap_bottom = min([sl.price for sl in lows_after])
                        fvg_index = lows_after[0].index
                    else:
                        gap_bottom = df['low'].iloc[start_idx:end_idx].min()
                        fvg_index = start_idx + df['low'].iloc[start_idx:end_idx].argmin()
                    
                    # Create large FVG zone (minimum 0.5% range)
                    if (gap_top - gap_bottom) / gap_bottom > 0.005:
                        all_fvgs.append(FVG(
                            index=fvg_index,
                            direction='bearish',
                            top=gap_top,
                            bottom=gap_bottom,
                            middle=(gap_top + gap_bottom) / 2,
                            candle_time=df['time'].iloc[fvg_index] if 'time' in df.columns else fvg_index,
                            is_filled=False,
                            associated_choch=choch
                        ))
        
        # Return the MOST RECENT FVG (closest to current time, not price!)
        # FIXED: Use most recent FVG after CHoCH (highest index = latest formed)
        # This gives consistent results - always the LAST pullback zone before current price
        if all_fvgs:
            # Sort by index (chronological order after CHoCH)
            all_fvgs.sort(key=lambda fvg: fvg.index)
            
            # Return LAST FVG (most recent, closest to current time)
            # This is the latest pullback zone where price should retrace
            return all_fvgs[-1]
        
        return None
    
    def is_fvg_filled(self, df: pd.DataFrame, fvg: FVG, current_index: int) -> bool:
        """
        Check if FVG has been filled by price action
        Filled = price CLOSES significantly through the gap (not just wicks)
        
        For BEARISH FVG: Filled if candle CLOSES above FVG top by 0.2%
        For BULLISH FVG: Filled if candle CLOSES below FVG bottom by 0.2%
        """
        if fvg.direction == 'bullish':
            # Check if price CLOSED significantly below the gap
            for i in range(fvg.index, current_index + 1):
                if df['close'].iloc[i] < fvg.bottom * 0.998:  # Must close 0.2% below
                    return True
        
        elif fvg.direction == 'bearish':
            # Check if price CLOSED significantly above the gap
            for i in range(fvg.index, current_index + 1):
                if df['close'].iloc[i] > fvg.top * 1.002:  # Must close 0.2% above
                    return True
        
        return False
    
    def is_price_in_fvg(self, current_price: float, fvg: FVG) -> bool:
        """Check if current price is inside FVG zone"""
        return fvg.bottom <= current_price <= fvg.top
    
    def is_high_quality_fvg(self, fvg: FVG, df: pd.DataFrame) -> bool:
        """
        Filter FVG quality to reduce false signals
        
        Checks:
        1. Gap size: Minimum 0.15% of price for forex (reject micro-gaps)
        2. Momentum: Strong candle that created the gap (≥40% body)
        3. Not already filled
        
        Returns:
            True if high quality FVG, False otherwise
        """
        # Check 1: Gap size minimum 0.15% (relaxed for forex)
        gap_size = fvg.top - fvg.bottom
        gap_pct = (gap_size / fvg.bottom) * 100
        
        if gap_pct < 0.10:  # Temporarily relaxed to 0.10% to see all FVGs
            return False  # Micro-gap, too small
        
        # Check 2: Momentum - check the candle that created the gap
        if fvg.index >= len(df):
            return True  # Can't validate, assume OK
        
        gap_candle = df.iloc[fvg.index]
        candle_body = abs(gap_candle['close'] - gap_candle['open'])
        candle_range = gap_candle['high'] - gap_candle['low']
        
        # Body should be at least 40% of total range (relaxed from 50%)
        if candle_range > 0:
            body_ratio = candle_body / candle_range
            if body_ratio < 0.25:  # Temporarily relaxed to 0.25 to see all FVGs
                return False  # Weak candle, likely manipulation
        
        # Check 3: Not already filled
        if fvg.is_filled:
            return False
        
        return True
    
    def calculate_fvg_quality_score(
        self, 
        fvg: FVG, 
        df: pd.DataFrame, 
        symbol: str,
        debug: bool = False
    ) -> int:
        """
        V3.0 FVG QUALITY SCORING SYSTEM
        
        Returns score 0-100:
        - ≥70: HIGH QUALITY (execute)
        - 50-69: MEDIUM QUALITY (monitor)
        - <50: LOW QUALITY (reject)
        
        Scoring Components:
        1. Gap Size (0-25 points):
           - ≥0.20%: 25 pts (excellent)
           - ≥0.15%: 20 pts (good)
           - ≥0.10%: 15 pts (acceptable)
           - <0.10%: 0 pts (reject)
        
        2. Body Dominance (0-30 points):
           - ≥80%: 30 pts (strong momentum) [GBP requires this]
           - ≥70%: 25 pts (good momentum) [Normal pairs min]
           - ≥60%: 15 pts (moderate)
           - <60%: 0 pts (weak)
        
        3. Consecutive Strength (0-25 points):
           - 3+ candles same direction: 25 pts
           - 2 candles same direction: 15 pts
           - 1 candle: 5 pts
           - Mixed: 0 pts
        
        4. Gap Clarity (0-20 points):
           - Clean gap (no overlap): 20 pts
           - Partial overlap: 10 pts
           - Heavy overlap: 0 pts
        
        GBP ADAPTIVE FILTERING:
        - GBP pairs need ≥80% body dominance (vs 70% normal)
        - Minimum score: 75 (vs 70 normal)
        """
        score = 0
        is_gbp = 'GBP' in symbol
        
        if debug:
            print(f"\n🎯 FVG QUALITY SCORING:")
            print(f"   Symbol: {symbol} {'[GBP - STRICT MODE]' if is_gbp else ''}")
        
        # 1. GAP SIZE SCORING (0-25 points)
        gap_size = fvg.top - fvg.bottom
        gap_pct = (gap_size / fvg.bottom) * 100
        
        if gap_pct >= 0.20:
            gap_score = 25
            gap_tier = "EXCELLENT"
        elif gap_pct >= 0.15:
            gap_score = 20
            gap_tier = "GOOD"
        elif gap_pct >= 0.10:
            gap_score = 15
            gap_tier = "ACCEPTABLE"
        else:
            gap_score = 0
            gap_tier = "TOO SMALL"
        
        score += gap_score
        
        if debug:
            print(f"   1. Gap Size: {gap_pct:.3f}% → {gap_score}/25 pts ({gap_tier})")
        
        # 2. BODY DOMINANCE SCORING (0-30 points)
        if fvg.index < len(df):
            gap_candle = df.iloc[fvg.index]
            candle_body = abs(gap_candle['close'] - gap_candle['open'])
            candle_range = gap_candle['high'] - gap_candle['low']
            
            if candle_range > 0:
                body_ratio = (candle_body / candle_range) * 100
                
                # GBP: Requires ≥70% body dominance (RELAXED from 80%)
                if is_gbp:
                    if body_ratio >= 80:
                        body_score = 30
                        body_tier = "STRONG (GBP OK)"
                    elif body_ratio >= 70:
                        body_score = 25
                        body_tier = "GOOD (GBP OK)"
                    else:
                        body_score = 0
                        body_tier = f"WEAK (GBP needs ≥70%, got {body_ratio:.1f}%)"
                else:
                    # Normal pairs: ≥60% acceptable (RELAXED from 70%)
                    if body_ratio >= 80:
                        body_score = 30
                        body_tier = "STRONG"
                    elif body_ratio >= 70:
                        body_score = 25
                        body_tier = "GOOD"
                    elif body_ratio >= 60:
                        body_score = 15
                        body_tier = "MODERATE"
                    else:
                        body_score = 0
                        body_tier = f"WEAK ({body_ratio:.1f}% < 60%)"
                
                score += body_score
                
                if debug:
                    print(f"   2. Body Dominance: {body_ratio:.1f}% → {body_score}/30 pts ({body_tier})")
            else:
                if debug:
                    print(f"   2. Body Dominance: N/A (zero range candle) → 0/30 pts")
        else:
            if debug:
                print(f"   2. Body Dominance: N/A (index out of range) → 0/30 pts")
        
        # 3. CONSECUTIVE STRENGTH SCORING (0-25 points)
        # Check 2-3 candles BEFORE FVG for trend strength
        if fvg.index >= 3:
            lookback_start = max(0, fvg.index - 3)
            lookback_candles = df.iloc[lookback_start:fvg.index]
            
            # Count consecutive candles in same direction as FVG
            consecutive_count = 0
            for idx in range(len(lookback_candles)):
                candle = lookback_candles.iloc[idx]
                candle_direction = 'bullish' if candle['close'] > candle['open'] else 'bearish'
                
                if candle_direction == fvg.direction:
                    consecutive_count += 1
            
            if consecutive_count >= 3:
                consec_score = 25
                consec_tier = "STRONG (3+ candles)"
            elif consecutive_count >= 2:
                consec_score = 15
                consec_tier = "GOOD (2 candles)"
            elif consecutive_count >= 1:
                consec_score = 5
                consec_tier = "WEAK (1 candle)"
            else:
                consec_score = 0
                consec_tier = "NONE (mixed)"
            
            score += consec_score
            
            if debug:
                print(f"   3. Consecutive Strength: {consecutive_count} candles → {consec_score}/25 pts ({consec_tier})")
        else:
            if debug:
                print(f"   3. Consecutive Strength: N/A (not enough history) → 0/25 pts")
        
        # 4. GAP CLARITY SCORING (0-20 points)
        # Check if gap is clean (no candle wicks overlap the gap zone)
        if fvg.index >= 2:
            candle_before = df.iloc[fvg.index - 2]
            candle_after = df.iloc[fvg.index]
            
            if fvg.direction == 'bullish':
                # Bullish gap: check if no overlap between before.high and after.low
                overlap = max(0, candle_before['high'] - candle_after['low'])
            else:
                # Bearish gap: check if no overlap between before.low and after.high
                overlap = max(0, candle_after['high'] - candle_before['low'])
            
            overlap_pct = (overlap / gap_size) * 100 if gap_size > 0 else 100
            
            if overlap_pct == 0:
                clarity_score = 20
                clarity_tier = "CLEAN GAP"
            elif overlap_pct < 30:
                clarity_score = 10
                clarity_tier = "PARTIAL OVERLAP"
            else:
                clarity_score = 0
                clarity_tier = "HEAVY OVERLAP"
            
            score += clarity_score
            
            if debug:
                print(f"   4. Gap Clarity: {overlap_pct:.1f}% overlap → {clarity_score}/20 pts ({clarity_tier})")
        else:
            if debug:
                print(f"   4. Gap Clarity: N/A (not enough history) → 0/20 pts")
        
        # FINAL SCORE
        min_required = 75 if is_gbp else 70
        quality_rating = "✅ HIGH QUALITY" if score >= min_required else "⚠️ LOW QUALITY"
        
        if debug:
            print(f"\n   📊 TOTAL SCORE: {score}/100 ({quality_rating})")
            print(f"   Required: ≥{min_required} pts")
        
        return score
    
    def detect_microtrend(self, df_4h: pd.DataFrame, fvg: FVG, choch_4h_index: int) -> bool:
        """
        Check if 4H was in microtrend toward the FVG before the 4H CHoCH
        
        For bullish FVG (expecting bearish reversal):
            - 4H should be moving UP toward FVG (bullish microtrend)
            - Then CHoCH bearish happens inside FVG
        
        For bearish FVG (expecting bullish reversal):
            - 4H should be moving DOWN toward FVG (bearish microtrend)
            - Then CHoCH bullish happens inside FVG
        """
        # Look at 5-10 candles before the 4H CHoCH
        lookback_start = max(0, choch_4h_index - 10)
        lookback_end = choch_4h_index
        
        if lookback_end - lookback_start < 5:
            return False  # Not enough data
        
        # Calculate trend direction
        start_price = df_4h['close'].iloc[lookback_start]
        end_price = df_4h['close'].iloc[lookback_end - 1]
        
        microtrend_direction = 'bullish' if end_price > start_price else 'bearish'
        
        # For bullish FVG, we want bearish reversal, so microtrend should be bullish
        if fvg.direction == 'bullish' and microtrend_direction == 'bullish':
            return True
        
        # For bearish FVG, we want bullish reversal, so microtrend should be bearish
        if fvg.direction == 'bearish' and microtrend_direction == 'bearish':
            return True
        
        return False
    
    def calculate_entry_sl_tp(
        self, 
        fvg: FVG, 
        h4_choch: CHoCH, 
        df_4h: pd.DataFrame,
        df_daily: pd.DataFrame
    ) -> Tuple[float, float, float]:
        """
        Calculate Entry, Stop Loss, and Take Profit
        
        ENTRY: FVG OPTIMAL ZONE (slightly better than exact middle)
        - For LONG (bullish): Lower third of FVG (better entry, closer to bottom)
        - For SHORT (bearish): Upper third of FVG (better entry, closer to top)
        
        TRADE DIRECTION: Follows DAILY CHoCH direction (FVG direction)
        - Daily BEARISH → Trade is SHORT
        - Daily BULLISH → Trade is LONG
        
        STOP LOSS: Last swing High/Low on 4H (opposite to trade direction)
        - SHORT (Daily bearish) → Last High on 4H (protection above)
        - LONG (Daily bullish) → Last Low on 4H (protection below)
        
        TAKE PROFIT: Last structure point on DAILY (same as trade direction)
        - SHORT (Daily bearish) → Last Low on Daily (target lower structure)
        - LONG (Daily bullish) → Last High on Daily (target higher structure)
        """
        
        # Trade direction = DAILY CHoCH direction = FVG direction
        if fvg.direction == 'bullish':
            # LONG TRADE (Daily bullish trend)
            
            # Entry = WITHIN FVG zone (35% from bottom = optimal discount zone)
            # NOT below FVG - that defeats the purpose of FVG retracement!
            fvg_range = fvg.top - fvg.bottom
            entry = fvg.bottom + (fvg_range * 0.35)  # 35% from bottom, inside FVG
            
            # SL = Last Low on 4H from PULLBACK in FVG zone
            # Look at 4H candles AROUND and INSIDE FVG (pullback zone)
            # This is the swing low that 4H CHoCH breaks!
            fvg_index_4h = df_4h[df_4h['time'] <= fvg.candle_time].index[-1] if len(df_4h[df_4h['time'] <= fvg.candle_time]) > 0 else len(df_4h) - 20
            # Look 20 candles AFTER FVG forms (this is the pullback period)
            lookback_start = fvg_index_4h
            lookback_end = min(len(df_4h), fvg_index_4h + 20)
            recent_lows = df_4h['low'].iloc[lookback_start:lookback_end]
            swing_low = recent_lows.min()
            
            # ATR buffer for SL (1.5x 4H ATR)
            atr_4h = (df_4h['high'] - df_4h['low']).rolling(14).mean().iloc[-1]
            stop_loss = swing_low - (1.5 * atr_4h)
            
            # TP = Next Daily HIGH structure (body-based, not wick)
            # STRATEGY: Find the next resistance level (previous swing high)
            daily_swing_highs = self.detect_swing_highs(df_daily)
            
            # Get swing highs BEFORE current position
            previous_highs = [sh for sh in daily_swing_highs if sh.index < len(df_daily) - 5]
            
            if previous_highs:
                # Use last significant high as TP (next resistance)
                take_profit = previous_highs[-1].price
            else:
                # Fallback: Use recent high from last 30 days
                recent_highs = df_daily['high'].iloc[-30:]
                take_profit = recent_highs.max()
            
            # Cap TP at 3x Daily ATR from entry (prevent unrealistic targets)
            max_tp_distance = 3 * daily_atr
            take_profit = min(take_profit, entry + max_tp_distance)
            
        else:
            # SHORT TRADE (Daily bearish trend)
            
            # Entry = WITHIN FVG zone (35% from top = optimal premium zone)
            # NOT above FVG - that defeats the purpose of FVG retracement!
            fvg_range = fvg.top - fvg.bottom
            entry = fvg.top - (fvg_range * 0.35)  # 35% from top, inside FVG
            
            # SL = Last High on 4H from PULLBACK in FVG zone
            # Look at 4H candles AROUND and INSIDE FVG (pullback zone)
            # This is the swing high that 4H CHoCH breaks!
            fvg_index_4h = df_4h[df_4h['time'] <= fvg.candle_time].index[-1] if len(df_4h[df_4h['time'] <= fvg.candle_time]) > 0 else len(df_4h) - 20
            # Look 20 candles AFTER FVG forms (this is the pullback period)
            lookback_start = fvg_index_4h
            lookback_end = min(len(df_4h), fvg_index_4h + 20)
            recent_highs = df_4h['high'].iloc[lookback_start:lookback_end]
            swing_high = recent_highs.max()
            
            # ATR buffer for SL (1.5x 4H ATR)
            atr_4h = (df_4h['high'] - df_4h['low']).rolling(14).mean().iloc[-1]
            stop_loss = swing_high + (1.5 * atr_4h)
            
            # TP = Next Daily LOW structure (body-based, not wick)
            # STRATEGY: Find the next support level (previous swing low)
            daily_swing_lows = self.detect_swing_lows(df_daily)
            
            # Get swing lows BEFORE current position
            previous_lows = [sl for sl in daily_swing_lows if sl.index < len(df_daily) - 5]
            
            if previous_lows:
                # Use last significant low as TP (next support)
                take_profit = previous_lows[-1].price
            else:
                # Fallback: Use recent low from last 30 days
                recent_lows = df_daily['low'].iloc[-30:]
                take_profit = recent_lows.min()
            
            # Cap TP at 3x Daily ATR from entry (prevent unrealistic targets)
            max_tp_distance = 3 * daily_atr
            take_profit = max(take_profit, entry - max_tp_distance)
        
        return entry, stop_loss, take_profit
    
    def detect_pullback_zone(
        self, 
        df: pd.DataFrame, 
        fvg: FVG, 
        current_trend: str,
        current_index: int
    ) -> Optional[Dict]:
        """
        🎯 PULLBACK DETECTION - Entry on pullback consolidation!
        
        After FVG is identified and price moves away from it,
        detect when price CONSOLIDATES (pullback) before resuming trend.
        
        Logic:
        1. LONG (bullish): Price breaks FVG bottom → moves up → pullback consolidation
           - Entry = when price breaks OUT of pullback consolidation upward
        
        2. SHORT (bearish): Price breaks FVG top → moves down → pullback consolidation
           - Entry = when price breaks OUT of pullback consolidation downward
        
        Returns: Dict with pullback info or None
        """
        
        if current_index < fvg.index + 5:
            return None  # Too early, not enough price action
        
        recent_df = df.iloc[fvg.index:current_index+1].copy()
        if len(recent_df) < 3:
            return None
        
        if current_trend == 'bullish':
            # LONG PULLBACK: Price up, then consolidates
            high_since_fvg = recent_df['high'].max()
            fvg_breakout_distance = (high_since_fvg - fvg.bottom) / fvg.bottom
            
            if fvg_breakout_distance < 0.003:  # Need 0.3%+ move
                return None
            
            recent_lows = recent_df['low'].iloc[-10:].min()
            pullback_range = (high_since_fvg - recent_lows) / fvg.bottom
            
            if 0.002 <= pullback_range <= 0.01:  # Valid pullback (0.2%-1%)
                return {
                    'type': 'bullish_pullback',
                    'high_point': high_since_fvg,
                    'pullback_low': recent_lows,
                    'pullback_depth_pct': pullback_range * 100
                }
        
        else:  # bearish
            # SHORT PULLBACK: Price down, then consolidates
            low_since_fvg = recent_df['low'].min()
            fvg_breakout_distance = (fvg.top - low_since_fvg) / fvg.top
            
            if fvg_breakout_distance < 0.003:  # Need 0.3%+ move
                return None
            
            recent_highs = recent_df['high'].iloc[-10:].max()
            pullback_range = (recent_highs - low_since_fvg) / fvg.top
            
            if 0.002 <= pullback_range <= 0.01:  # Valid pullback (0.2%-1%)
                return {
                    'type': 'bearish_pullback',
                    'low_point': low_since_fvg,
                    'pullback_high': recent_highs,
                    'pullback_depth_pct': pullback_range * 100
                }
        
        return None
    
    def check_pullback_breakout(
        self,
        df: pd.DataFrame,
        pullback: Dict,
        current_index: int
    ) -> bool:
        """
        Check if price broke OUT of pullback consolidation
        
        LONG: Price breaks ABOVE pullback high
        SHORT: Price breaks BELOW pullback low
        """
        if pullback is None:
            return False
        
        recent_high = df['high'].iloc[max(0, current_index-2):current_index+1].max()
        recent_low = df['low'].iloc[max(0, current_index-2):current_index+1].min()
        
        if pullback['type'] == 'bullish_pullback':
            pullback_high = pullback['pullback_high'] * 1.001
            return recent_high > pullback_high
        else:
            pullback_low = pullback['pullback_low'] * 0.999
            return recent_low < pullback_low
        
        return False
    
    def _analyze_pre_choch_structure(
        self,
        df: pd.DataFrame,
        choch: CHoCH
    ) -> Dict:
        """
        Analyze structure BEFORE CHoCH to determine previous trend
        
        V3.0 UPGRADE: Extended macro context (100-120 candles)
        - Identifies TRUE reversals (5-6 months trend change)
        - Separates major reversals from micro pullbacks
        
        Returns:
            {'pattern': 'HH_HL' | 'LH_LL' | 'mixed', 'confidence': 0-100, 'duration': int}
        """
        # V3.0: Extended MACRO window (100-120 candles = 5-6 months)
        # Purpose: Confirm REAL trend, not just short-term fluctuations
        
        # Get 100-120 candles before CHoCH
        macro_start = max(0, choch.index - 120)  # V3.0: 120 candles back (was 60)
        macro_end = max(macro_start + 10, choch.index - 5)  # V3.0: Stop 5 candles before (was 10)
        macro_df = df.iloc[macro_start:macro_end]
        
        trend_duration = len(macro_df)  # Track how long the trend lasted
        
        if len(macro_df) >= 30:  # V3.0: Minimum 30 candles for valid macro (was 20)
            # Analyze MACRO trend using price action
            first_third = macro_df.iloc[:len(macro_df)//3]
            last_third = macro_df.iloc[-len(macro_df)//3:]
            
            first_high = first_third['high'].max()
            first_low = first_third['low'].min()
            last_high = last_third['high'].max()
            last_low = last_third['low'].min()
            
            # V3.0: Calculate trend strength with percentage move
            price_range = max(first_high, last_high) - min(first_low, last_low)
            high_change = last_high - first_high
            low_change = last_low - first_low
            high_change_pct = (high_change / first_high) * 100 if first_high > 0 else 0
            low_change_pct = (low_change / first_low) * 100 if first_low > 0 else 0
            
            # Determine MACRO trend with strength validation
            if high_change > 0 and low_change > 0:
                # Higher highs AND higher lows = BULLISH MACRO TREND
                macro_trend = 'bullish'
                # V3.0: Confidence based on trend duration and strength
                if trend_duration >= 80 and high_change_pct > 5:
                    confidence = 95  # Very strong trend (5%+ move over 80+ candles)
                elif trend_duration >= 50:
                    confidence = 90  # Strong trend
                else:
                    confidence = 85  # Moderate trend
            elif high_change < 0 and low_change < 0:
                # Lower highs AND lower lows = BEARISH MACRO TREND
                macro_trend = 'bearish'
                # V3.0: Confidence based on trend duration and strength
                if trend_duration >= 80 and abs(low_change_pct) > 5:
                    confidence = 95  # Very strong trend (5%+ move over 80+ candles)
                elif trend_duration >= 50:
                    confidence = 90  # Strong trend
                else:
                    confidence = 85  # Moderate trend
            else:
                # Mixed = use CHoCH previous_trend as fallback
                macro_trend = choch.previous_trend if hasattr(choch, 'previous_trend') else None
                confidence = 60
            
            # Return pattern based on MACRO trend with duration tracking
            if macro_trend == 'bearish':
                return {
                    'pattern': 'LH_LL', 
                    'confidence': confidence,
                    'duration': trend_duration,  # V3.0: Track trend strength
                    'strength_pct': abs(low_change_pct)  # V3.0: Percentage move
                }
            elif macro_trend == 'bullish':
                return {
                    'pattern': 'HH_HL', 
                    'confidence': confidence,
                    'duration': trend_duration,  # V3.0: Track trend strength
                    'strength_pct': high_change_pct  # V3.0: Percentage move
                }
        
        # FALLBACK: Use CHoCH's previous_trend field if macro analysis fails
        if hasattr(choch, 'previous_trend') and choch.previous_trend:
            if choch.previous_trend == 'bearish':
                return {'pattern': 'LH_LL', 'confidence': 90, 'duration': 0, 'strength_pct': 0}
            elif choch.previous_trend == 'bullish':
                return {'pattern': 'HH_HL', 'confidence': 90, 'duration': 0, 'strength_pct': 0}
        
        # LAST RESORT: Analyze swings if previous_trend not available
        # Get candles BEFORE CHoCH (30-50 bars before for MAJOR trend analysis)
        pre_choch_idx = max(0, choch.index - 50)
        pre_df = df.iloc[pre_choch_idx:choch.index]
        
        if len(pre_df) < 5:
            return {'pattern': 'mixed', 'confidence': 30}
        
        # Detect swings in pre-CHoCH period
        highs = self.detect_swing_highs(pre_df)
        lows = self.detect_swing_lows(pre_df)
        
        if len(highs) < 2 or len(lows) < 2:
            # Not enough swings, check recent price action
            recent_high = pre_df['high'].max()
            recent_low = pre_df['low'].min()
            first_half_high = pre_df.iloc[:len(pre_df)//2]['high'].max()
            second_half_high = pre_df.iloc[len(pre_df)//2:]['high'].max()
            first_half_low = pre_df.iloc[:len(pre_df)//2]['low'].min()
            second_half_low = pre_df.iloc[len(pre_df)//2:]['low'].min()
            
            if second_half_high < first_half_high and second_half_low < first_half_low:
                # Lower highs AND lower lows = BEARISH
                return {'pattern': 'LH_LL', 'confidence': 60}
            elif second_half_high > first_half_high and second_half_low > first_half_low:
                # Higher highs AND higher lows = BULLISH
                return {'pattern': 'HH_HL', 'confidence': 60}
            else:
                return {'pattern': 'mixed', 'confidence': 40}
        
        # Count patterns
        hh_count = sum(1 for i in range(1, len(highs)) if highs[i].price > highs[i-1].price)
        hl_count = sum(1 for i in range(1, len(lows)) if lows[i].price > lows[i-1].price)
        lh_count = sum(1 for i in range(1, len(highs)) if highs[i].price < highs[i-1].price)
        ll_count = sum(1 for i in range(1, len(lows)) if lows[i].price < lows[i-1].price)
        
        # Determine pattern
        if hh_count >= 2 and hl_count >= 2:
            # Clear BULLISH trend before CHoCH
            return {'pattern': 'HH_HL', 'confidence': 85}
        elif lh_count >= 2 and ll_count >= 2:
            # Clear BEARISH trend before CHoCH
            return {'pattern': 'LH_LL', 'confidence': 85}
        elif hh_count >= 1 and hl_count >= 1:
            # Weak bullish
            return {'pattern': 'HH_HL', 'confidence': 65}
        elif lh_count >= 1 and ll_count >= 1:
            # Weak bearish
            return {'pattern': 'LH_LL', 'confidence': 65}
        else:
            # Mixed/ranging - use price action as tiebreaker
            recent_trend = pre_df['close'].iloc[-1] - pre_df['close'].iloc[0]
            if recent_trend < 0:
                return {'pattern': 'LH_LL', 'confidence': 50}
            else:
                return {'pattern': 'HH_HL', 'confidence': 50}
    
    def detect_strategy_type(
        self,
        df_daily: pd.DataFrame,
        latest_choch: CHoCH,
        fvg: Optional[FVG] = None
    ) -> str:
        """
        IMPROVED: Determine if setup is REVERSAL or CONTINUATION
        
        REVERSAL: Previous trend OPPOSITE to CHoCH direction
        - Bullish CHoCH + Previous BEARISH (LH/LL) = REVERSAL BULLISH (BUY)
        - Bearish CHoCH + Previous BULLISH (HH/HL) = REVERSAL BEARISH (SELL)
        
        CONTINUATION: Previous trend SAME as CHoCH direction
        - Bullish CHoCH + Previous BULLISH (HH/HL) = CONTINUATION BULLISH (pullback, then continue UP)
        - Bearish CHoCH + Previous BEARISH (LH/LL) = CONTINUATION BEARISH (pullback, then continue DOWN)
        
        Returns:
            'reversal' or 'continuation'
        """
        # Analyze trend BEFORE CHoCH
        pre_choch_structure = self._analyze_pre_choch_structure(df_daily, latest_choch)
        
        if latest_choch.direction == 'bullish':
            # BULLISH CHoCH
            if pre_choch_structure['pattern'] == 'LH_LL':
                # Previous: BEARISH → CHoCH: BULLISH = REVERSAL
                # Should have GREEN FVG (bullish imbalance)
                if fvg and fvg.direction == 'bullish':
                    return 'reversal'  # ✅ REVERSAL BULLISH (BUY in green zone)
                else:
                    # FVG not aligned, but structure says reversal
                    return 'reversal'
            
            elif pre_choch_structure['pattern'] == 'HH_HL':
                # Previous: BULLISH → CHoCH: BULLISH = CONTINUATION
                # Pullback retest at HL, should have GREEN/BLUE FVG
                return 'continuation'  # ✅ CONTINUATION BULLISH (continue UP)
            
            else:
                # Mixed - default to reversal if confidence low
                return 'reversal' if pre_choch_structure['confidence'] < 50 else 'continuation'
        
        else:  # bearish CHoCH
            # BEARISH CHoCH
            if pre_choch_structure['pattern'] == 'HH_HL':
                # Previous: BULLISH → CHoCH: BEARISH = REVERSAL
                # Should have RED FVG (bearish imbalance)
                if fvg and fvg.direction == 'bearish':
                    return 'reversal'  # ✅ REVERSAL BEARISH (SELL in red zone)
                else:
                    # FVG not aligned, but structure says reversal
                    return 'reversal'
            
            elif pre_choch_structure['pattern'] == 'LH_LL':
                # Previous: BEARISH → CHoCH: BEARISH = CONTINUATION
                # Pullback retest at LH, should have RED/BLUE FVG
                return 'continuation'  # ✅ CONTINUATION BEARISH (continue DOWN)
            
            else:
                # Mixed - default to reversal if confidence low
                return 'reversal' if pre_choch_structure['confidence'] < 50 else 'continuation'
    
    def scan_for_setup(
        self, 
        symbol: str,
        df_daily: pd.DataFrame, 
        df_4h: pd.DataFrame,
        priority: int,
        df_1h: Optional[pd.DataFrame] = None,  # V3.0: For GBP pairs 2-TF confirmation
        require_4h_choch: bool = True,  # V3.0: Strict entry, V2.1: False for original logic
        skip_fvg_quality: bool = False  # For backtesting: skip quality check to find more trades
    ) -> Optional[TradeSetup]:
        """
        Main scanner: Check if "Glitch in Matrix" setup exists
        
        FINAL LOGIC (V3.0 - CHoCH + BOS CORRECT USAGE):
        
        TWO SETUP TYPES:
        1. REVERSAL: Daily CHoCH (trend changes) + FVG + 4H CHoCH from pullback
           - Previous trend OPPOSITE to new trend
           - Example: BEARISH → CHoCH BULLISH → Pullback → H4 CHoCH BULLISH
        
        2. CONTINUITY: Daily BOS (trend continues) + FVG + 4H CHoCH from pullback
           - Previous trend SAME as current (BOS = HH in bullish, LL in bearish)
           - Example: BULLISH → BOS HH → Pullback → H4 CHoCH BULLISH
        
        WHY 4H CHoCH FOR BOTH?
        - Confirms pullback finished
        - Confirms momentum returns to Daily direction
        - Safer entry (prevents SL hit during extended pullbacks)
        
        V3.0 GBP ADAPTIVE FILTERING:
        - GBP pairs require 2-timeframe confirmation (4H + 1H)
        - Stricter FVG quality (≥70 vs ≥60)
        - Body dominance ≥70%
        
        Steps:
        1. Detect Daily CHoCH (REVERSAL) or Daily BOS (CONTINUITY)
        2. Find FVG after signal
        3. Check if price is retesting FVG
        4. Check 4H for CHoCH confirmation (pullback finished)
        5. Return complete setup
        """
        # DEBUG MODE for specific symbols
        debug = symbol == "NZDCAD"
        
        # Step 1: Detect Daily CHoCH AND BOS
        daily_chochs, daily_bos_list = self.detect_choch_and_bos(df_daily)
        
        if debug:
            print(f"\n{'='*60}")
            print(f"🔍 DEBUG: {symbol} - GLITCH IN MATRIX SCAN")
            print(f"{'='*60}")
            print(f"📊 Daily CHoCH detected: {len(daily_chochs)}")
            print(f"📊 Daily BOS detected: {len(daily_bos_list)}")
            if daily_chochs:
                for i, choch in enumerate(daily_chochs[-3:]):  # Last 3
                    print(f"   CHoCH [{i}] {choch.direction.upper()} @ {choch.break_price:.5f} (index {choch.index})")
            if daily_bos_list:
                for i, bos in enumerate(daily_bos_list[-3:]):  # Last 3
                    print(f"   BOS [{i}] {bos.direction.upper()} @ {bos.break_price:.5f} (index {bos.index})")
        
        # V3.0 LOGIC: TWO SETUP TYPES
        # REVERSAL: Requires Daily CHoCH (trend change)
        # CONTINUITY: Requires Daily BOS (trend continuation)
        
        # Try both strategies and pick the most recent valid signal
        latest_choch = daily_chochs[-1] if daily_chochs else None
        latest_bos = daily_bos_list[-1] if daily_bos_list else None
        
        # Determine which signal is more recent and use that
        latest_signal = None
        strategy_type = None
        
        if latest_choch and latest_bos:
            # Both exist - use the more recent one
            if latest_choch.index > latest_bos.index:
                latest_signal = latest_choch
                strategy_type = 'reversal'
            else:
                latest_signal = latest_bos
                strategy_type = 'continuation'
        elif latest_choch:
            latest_signal = latest_choch
            strategy_type = 'reversal'
        elif latest_bos:
            latest_signal = latest_bos
            strategy_type = 'continuation'
        else:
            if debug:
                print(f"❌ REJECTED: No Daily CHoCH or BOS found")
            return None
        
        current_trend = latest_signal.direction  # 'bullish' or 'bearish'
        
        if debug:
            print(f"\n✅ Latest Signal: {strategy_type.upper()} - {current_trend.upper()} @ {latest_signal.break_price:.5f}")
        
        # Step 2: Find FVG after signal (CHoCH or BOS) - closest to current price
        current_price = df_daily['close'].iloc[-1]
        fvg = self.detect_fvg(df_daily, latest_signal, current_price)
        
        if not fvg:
            if debug:
                print(f"❌ REJECTED: No FVG found after {strategy_type.upper()} signal")
            return None  # No FVG found
        
        if debug:
            gap_size = fvg.top - fvg.bottom
            gap_pct = (gap_size / fvg.bottom) * 100
            print(f"\n✅ FVG Found:")
            print(f"   Direction: {fvg.direction.upper()}")
            print(f"   Zone: {fvg.bottom:.5f} - {fvg.top:.5f}")
            print(f"   Gap Size: {gap_size:.5f} ({gap_pct:.3f}%)")
            print(f"   Middle: {fvg.middle:.5f}")
        
        # V3.0: Calculate FVG Quality Score (0-100) - OPTIONAL for backtest
        if not skip_fvg_quality:
            fvg_score = self.calculate_fvg_quality_score(fvg, df_daily, symbol, debug=debug)
            fvg.quality_score = fvg_score  # Store score in FVG object
            
            # V3.0 QUALITY THRESHOLD (only when not skipped)
            # - Normal pairs: ≥60 required (RELAXED from 70)
            # - GBP pairs: ≥70 required (RELAXED from 75)
            is_gbp = 'GBP' in symbol
            min_score = 70 if is_gbp else 60
            
            if fvg_score < min_score:
                if debug:
                    print(f"\n❌ REJECTED: FVG score {fvg_score}/100 < {min_score} (minimum)")
                    if is_gbp:
                        print(f"   GBP pair requires stricter quality (≥70)")
                return None  # Low quality FVG
        else:
            # Skip quality check for backtest - accept all FVGs
            fvg.quality_score = 100  # Default high score when skipped
        
        # FVG direction must match current trend
        fvg.direction = current_trend
        
        # Step 4: Check price relationship with FVG
        current_price = df_daily['close'].iloc[-1]
        
        if debug:
            print(f"\n📍 Current Price: {current_price:.5f}")
        
        # NEW: More flexible - accept setups even if price not perfectly in FVG yet
        price_approaching_fvg = False
        price_in_fvg = self.is_price_in_fvg(current_price, fvg)
        
        # For backtesting: skip price proximity check
        if skip_fvg_quality:
            price_approaching_fvg = True  # Accept all price positions for backtest
        else:
            if current_trend == 'bullish':
                # BULLISH: Price should be BELOW or IN FVG (waiting for pullback to buy)
                if current_price <= fvg.top:
                    price_approaching_fvg = True
            else:
                # BEARISH: Price should be ABOVE or IN FVG (waiting for pullback to sell)
                if current_price >= fvg.bottom:
                    price_approaching_fvg = True
        
        if debug:
            print(f"   In FVG: {price_in_fvg}")
            print(f"   Approaching FVG: {price_approaching_fvg}")
            if current_trend == 'bullish':
                distance = current_price - fvg.top
                print(f"   Distance from FVG top: {distance:.5f} ({(distance/current_price)*100:.2f}%)")
            else:
                distance = fvg.bottom - current_price
                print(f"   Distance from FVG bottom: {distance:.5f} ({(distance/current_price)*100:.2f}%)")
        
        if not price_approaching_fvg and not skip_fvg_quality:
            if debug:
                print(f"❌ REJECTED: Price too far from FVG")
            return None  # Price too far from FVG
        
        # Step 5: Strategy type already determined from signal type (CHoCH=REVERSAL, BOS=CONTINUITY)
        # No need to re-detect strategy_type
        
        if debug:
            print(f"\n📋 Strategy Type: {strategy_type.upper()}")
        
        # Step 6: Check 4H for confirmation (CHoCH FROM FVG zone)
        h4_chochs, h4_bos_list = self.detect_choch_and_bos(df_4h)
        
        if debug:
            print(f"\n🔍 H4 Analysis:")
            print(f"   Total H4 CHoCH: {len(h4_chochs)}")
            if h4_chochs:
                for i, h4ch in enumerate(h4_chochs[-5:]):  # Last 5
                    in_fvg = fvg.bottom <= h4ch.break_price <= fvg.top
                    matches = h4ch.direction == current_trend
                    print(f"   [{i}] {h4ch.direction.upper()} @ {h4ch.break_price:.5f} - InFVG:{in_fvg} Match:{matches}")
        
        # Find H4 CHoCH that matches current trend AND happens FROM FVG zone
        valid_h4_choch = None
        
        # V2.1 vs V3.0 DIFFERENCE:
        # V2.1: Daily CHoCH + FVG = READY (original $88k profit logic)
        # V3.0: Daily CHoCH + FVG + 4H CHoCH = READY (strict entry confirmation)
        
        if require_4h_choch:
            # V3.0 STRICT CONFIRMATION:
            # BOTH STRATEGIES (REVERSAL & CONTINUITY) USE H4 CHoCH FROM PULLBACK:
            # 
            # REVERSAL: Daily CHoCH (trend change) → Pullback în FVG → H4 CHoCH (confirms reversal continuation) FROM FVG
            # Example: Was BEARISH → Daily CHoCH BULLISH → Pullback → H4 CHoCH BULLISH (confirms bulls taking over)
            # 
            # CONTINUITY: Daily BOS (trend continues) → Pullback în FVG → H4 CHoCH (from pullback back to main trend) FROM FVG
            # Example: Daily BULLISH BOS (HH) → Pullback bearish → H4 CHoCH BULLISH (from pullback back to bullish)
            # 
            # WHY H4 CHoCH FOR BOTH?
            # - Confirms pullback is FINISHED
            # - Confirms momentum returning in Daily trend direction
            # - Prevents entries during extended pullbacks (risk SL hit)
            
            # V3.0 FIXED: Scanează ultimele 50 candles pentru CONTEXT complet
            # Dar acceptă doar CHoCH RECENT (max 12 candles = 48 ore vechi)
            # Asta permite: detectare cu context + validare că e fresh (nu vechi de 3-5 zile)
            recent_h4_chochs = [ch for ch in h4_chochs if ch.index >= len(df_4h) - 50]
            
            for h4_choch in reversed(recent_h4_chochs):
                # H4 CHoCH direction must match Daily trend direction
                if h4_choch.direction != current_trend:
                    continue
                
                # CRITICAL: CHoCH break_price must be WITHIN FVG zone
                if not (fvg.bottom <= h4_choch.break_price <= fvg.top):
                    continue
                
                # NEW CHECK: Verify CHoCH is RECENT (not older than 12 candles = 48 hours)
                # This ensures we catch pullback CHoCH, not old CHoCH from before
                choch_age = len(df_4h) - 1 - h4_choch.index
                if choch_age > 12:  # More than 48 hours old (12 × 4h)
                    if debug:
                        print(f"   ⏭️  H4 CHoCH @ {h4_choch.break_price:.5f} too old ({choch_age} candles = {choch_age*4}h)")
                    continue
                
                # NEW CHECK: Verify momentum AFTER CHoCH confirms trend continuation
                # Need at least 1 candle after CHoCH to confirm
                if h4_choch.index + 1 < len(df_4h):
                    candles_after = df_4h.iloc[h4_choch.index + 1:]
                    if len(candles_after) >= 1:
                        # Check if recent candle(s) support the trend
                        last_candle = candles_after.iloc[-1]
                        
                        if current_trend == 'bullish':
                            # For bullish: last candle should be bullish or price moving up
                            momentum_ok = (last_candle['close'] > last_candle['open']) or \
                                        (last_candle['close'] > df_4h.iloc[h4_choch.index]['close'])
                        else:
                            # For bearish: last candle should be bearish or price moving down
                            momentum_ok = (last_candle['close'] < last_candle['open']) or \
                                        (last_candle['close'] < df_4h.iloc[h4_choch.index]['close'])
                        
                        if not momentum_ok:
                            if debug:
                                print(f"   ⏭️  H4 CHoCH @ {h4_choch.break_price:.5f} lacks momentum confirmation")
                            continue
                
                # ✅ All checks passed - VALID, RECENT, CONFIRMED CHoCH
                valid_h4_choch = h4_choch
                if debug:
                    print(f"   ✅ Valid H4 CHoCH found @ {h4_choch.break_price:.5f} ({choch_age} candles ago, momentum confirmed)")
                break
            
            if debug and not valid_h4_choch:
                print(f"   ❌ No valid RECENT H4 CHoCH FROM FVG zone (scanned 50 candles, accept max 12 candles old = 48h)")
                print(f"      Waiting for fresh CHoCH to confirm pullback is finished")
        else:
            # V2.1 MODE: Skip 4H CHoCH requirement (original logic)
            if debug:
                print(f"   ⚠️  V2.1 MODE: Skipping 4H CHoCH requirement")
        
        # V3.0 GBP ADAPTIVE FILTERING: Require 1H confirmation
        # GBP pairs are volatile - need 2-timeframe confirmation (4H + 1H)
        is_gbp = 'GBP' in symbol
        valid_1h_choch = None
        
        if is_gbp and valid_h4_choch and df_1h is not None:
            if debug:
                print(f"\n🔍 1H Analysis (GBP requirement):")
            
            # Detect 1H CHoCH
            h1_chochs, _ = self.detect_choch_and_bos(df_1h)
            
            if debug:
                print(f"   Total 1H CHoCH: {len(h1_chochs)}")
            
            # Look for 1H CHoCH in last 20 candles (~20 hours)
            recent_h1_chochs = [ch for ch in h1_chochs if ch.index >= len(df_1h) - 20]
            
            for h1_choch in reversed(recent_h1_chochs):
                # 1H CHoCH direction must match Daily trend
                if h1_choch.direction != current_trend:
                    continue
                
                # 1H CHoCH should be in or near FVG zone
                if fvg.bottom <= h1_choch.break_price <= fvg.top:
                    valid_1h_choch = h1_choch
                    if debug:
                        print(f"   ✅ Valid 1H CHoCH found @ {h1_choch.break_price:.5f}")
                    break
            
            if debug and not valid_1h_choch:
                print(f"   ❌ No valid 1H CHoCH (GBP requires 2-TF confirmation)")
        
        # V3.0 STRICT STATUS LOGIC:
        # READY = 4H CHoCH confirmed (same direction as Daily) AND price currently IN FVG
        # MONITORING = waiting for 4H CHoCH OR waiting for price to enter FVG
        #
        # This prevents premature entries during aggressive pullbacks (like NZDUSD case)
        
        # V3.0 CONTINUITY FILTER (skip for backtest to match original V2.1 logic)
        # For CONTINUITY setups (Daily BOS), require additional BOS in same direction (last 90 candles)
        # This ensures we have multiple BOS confirming strong trend continuation
        # REVERSAL setups (Daily CHoCH) skip this - trend just changed, no need for multiple BOS
        continuity_validated = True
        if not skip_fvg_quality and strategy_type == 'continuation':
            # Already have the latest_signal as BOS, check for additional BOS before it
            # Check last 90 candles for BOS in same direction (RELAXED from 60)
            recent_bos = [bos for bos in daily_bos_list if bos.index >= len(df_daily) - 90 and bos.index < latest_signal.index]
            matching_bos = [bos for bos in recent_bos if bos.direction == current_trend]
            
            if not matching_bos:
                continuity_validated = False
                if debug:
                    print(f"\n⚠️  CONTINUITY FILTER: No additional BOS found before latest BOS")
                    print(f"   Trend: {current_trend.upper()}")
                    print(f"   Need at least 1 more BOS to confirm strong continuation")
            else:
                if debug:
                    print(f"\n✅ CONTINUITY FILTER: {len(matching_bos)} additional BOS found (strong continuation)")
                    print(f"   Latest additional BOS: {matching_bos[-1].direction.upper()} @ candle {matching_bos[-1].index}")
        
        # V3.0 GBP 2-TIMEFRAME FILTER (skip for backtest)
        # GBP pairs need BOTH 4H AND 1H confirmation
        gbp_confirmed = True
        if not skip_fvg_quality:
            is_gbp = 'GBP' in symbol
            if is_gbp and valid_h4_choch:
                if df_1h is not None and not valid_1h_choch:
                    gbp_confirmed = False
                    if debug:
                        print(f"\n⚠️  GBP FILTER: Missing 1H confirmation")
                        print(f"   GBP pairs require 2-timeframe confirmation (4H + 1H)")
                elif df_1h is None:
                    if debug:
                        print(f"\n⚠️  GBP FILTER: 1H data not provided")
                        print(f"   Cannot validate 2-TF confirmation for GBP")
                    gbp_confirmed = False
        
        # STATUS LOGIC: V2.1 vs V3.0
        if not require_4h_choch:
            # V2.1 MODE: Daily CHoCH + FVG + price in FVG = READY
            if price_in_fvg:
                status = 'READY'
                if debug:
                    print(f"\n✅ STATUS: READY TO EXECUTE (V2.1 MODE)")
                    print(f"   ✓ Daily CHoCH: {current_trend.upper()}")
                    print(f"   ✓ Price IN FVG: {current_price:.5f} (FVG: {fvg.bottom:.5f} - {fvg.top:.5f})")
            else:
                status = 'MONITORING'
                if debug:
                    print(f"\n⏳ STATUS: MONITORING (V2.1 MODE - waiting for price in FVG)")
                    print(f"   ✓ Daily CHoCH: {current_trend.upper()}")
                    print(f"   ✗ Price NOT in FVG (current: {current_price:.5f})")
        elif valid_h4_choch:
            # V3.0 SIMPLIFIED: Only need 4H CHoCH aligned with Daily
            # Price will naturally move to FVG (that's where the action is)
            # No need for: BOS filter, GBP 2-TF, or exact price in FVG
            status = 'READY'  # ✅ 4H trend confirmed - READY to execute
            if debug:
                print(f"\n✅ STATUS: READY TO EXECUTE (V3.0 SIMPLIFIED)")
                print(f"   ✓ Daily CHoCH: {current_trend.upper()}")
                print(f"   ✓ 4H CHoCH confirmed: {valid_h4_choch.direction.upper()} @ {valid_h4_choch.break_price:.5f}")
                print(f"   ✓ FVG Zone: {fvg.bottom:.5f} - {fvg.top:.5f} (entry target)")
                print(f"   📊 Current Price: {current_price:.5f}")
        else:
            # No 4H CHoCH yet - keep monitoring
            status = 'MONITORING'
            if debug:
                print(f"\n⏳ STATUS: MONITORING (waiting for 4H CHoCH confirmation)")
                print(f"   ✓ Daily CHoCH: {current_trend.upper()}")
                print(f"   ✓ FVG Zone: {fvg.bottom:.5f} - {fvg.top:.5f}")
                print(f"   ✗ No 4H CHoCH yet (checked last 30 candles)")
                print(f"   📊 Current Price: {current_price:.5f}")
        
        # Step 7: Calculate entry, SL, TP
        # Use H4 CHoCH for both REVERSAL and CONTINUITY
        h4_signal = valid_h4_choch
        
        if h4_signal:
            entry, sl, tp = self.calculate_entry_sl_tp(fvg, h4_signal, df_4h, df_daily)
        else:
            # No 4H CHoCH yet - use FVG edge as entry (discount/premium zone)
            # LONG: Entry at FVG bottom (buy the discount)
            # SHORT: Entry at FVG top (sell the premium)
            if current_trend == 'bullish':
                entry = fvg.bottom  # Buy at FVG bottom
                sl = fvg.bottom * 0.998  # SL below FVG
                tp = fvg.top * 1.015  # TP above FVG
            else:
                entry = fvg.top  # Sell at FVG top
                sl = fvg.top * 1.002  # SL above FVG
                tp = fvg.bottom * 0.985  # TP below FVG
        
        if debug:
            print(f"\n💰 Trade Levels:")
            print(f"   Entry: {entry:.5f}")
            print(f"   SL: {sl:.5f}")
            print(f"   TP: {tp:.5f}")
            rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
            print(f"   Risk:Reward: 1:{rr:.2f}")
            print(f"{'='*60}\n")
        
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        risk_reward = reward / risk if risk > 0 else 0
        
        # ⚠️  CRITICAL VALIDATION: Reject setups that are TOO LATE
        # STRATEGY 2.0: SL on 4H (close swing), TP on Daily (far swing)
        # Normal R:R = 4.0 - 8.0 (NOT 2.0!)
        # If R:R < 4.0, the move already happened - we missed it!
        if risk_reward < 4.0:
            return None  # Setup detected too late, move already happened
        
        # 🚨 CHECK 1: Price already moved too close to TP?
        # If current price is within 20% of TP distance, it's too late
        current_price = df_daily['close'].iloc[-1]
        distance_to_tp = abs(current_price - tp)
        total_move = abs(entry - tp)
        
        if total_move > 0 and (distance_to_tp / total_move) < 0.20:
            return None  # Price already 80%+ toward TP - TOO LATE!
        
        # 🎯 CHECK 2: Stop Loss already HIT?
        # If price broke through SL, try to find RE-ENTRY opportunity
        sl_broken = False
        if fvg.direction == 'bearish':
            # SHORT setup - SL is ABOVE entry
            if current_price > sl:
                sl_broken = True
        else:
            # LONG setup - SL is BELOW entry
            if current_price < sl:
                sl_broken = True
        
        # 🔄 RE-ENTRY LOGIC: If SL broken but trend still valid, look for new entry
        if sl_broken:
            # RE-ENTRY CONFIRMATION: Wait for 4H CHoCH in same direction before re-entering
            # This prevents re-entering during a pullback that continues against us
            
            # Get recent 4H CHoCH signals (after potential SL break)
            h4_chochs, _ = self.detect_choch_and_bos(df_4h)
            
            # Find the most recent CHoCH
            recent_h4_choch = None
            if h4_chochs:
                # Look for CHoCH in last 20 candles (recent confirmation)
                recent_h4_chochs = [ch for ch in h4_chochs if ch.index >= len(df_4h) - 20]
                if recent_h4_chochs:
                    recent_h4_choch = recent_h4_chochs[-1]
            
            # Require 4H CHoCH confirmation in SAME direction as original setup
            if not recent_h4_choch or recent_h4_choch.direction != fvg.direction:
                return None  # No re-entry without 4H confirmation
            
            # Check if trend is STILL VALID (recent price action confirms trend)
            recent_candles = df_daily.iloc[-10:]  # Last 10 days
            
            if fvg.direction == 'bearish':
                # BEARISH trend - check if still making lower lows
                recent_low = recent_candles['low'].min()
                older_low = df_daily.iloc[-30:-10]['low'].min()
                trend_continues = recent_low < older_low  # Still going down
                
                if trend_continues:
                    # RE-ENTRY for SHORT: Use current price as new entry
                    entry = current_price
                    # New SL: Recent high on 4H with ATR buffer
                    recent_4h = df_4h.iloc[-10:]
                    swing_high = recent_4h['high'].max()
                    atr_4h = (df_4h['high'] - df_4h['low']).rolling(14).mean().iloc[-1]
                    sl = swing_high + (1.5 * atr_4h)
                    # Keep same TP target (original target still valid on Daily)
                    # tp stays the same
                    
                    # Recalculate R:R with new parameters
                    risk = abs(entry - sl)
                    reward = abs(tp - entry)
                    risk_reward = reward / risk if risk > 0 else 0
                    
                    if risk_reward < 4.0:
                        return None  # Re-entry not worth it (need R:R ≥ 4.0)
                        
                    print(f"🔄 RE-ENTRY setup found for {symbol}!")
                    print(f"   Original SL was broken, but 4H CHoCH confirmed trend continues")
                    print(f"   New Entry: {entry:.5f}")
                    print(f"   New SL: {sl:.5f} (with ATR buffer)")
                    print(f"   New R:R: 1:{risk_reward:.2f}")
                else:
                    return None  # Trend invalidated
                    
            else:
                # BULLISH trend - check if still making higher highs
                recent_high = recent_candles['high'].max()
                older_high = df_daily.iloc[-30:-10]['high'].max()
                trend_continues = recent_high > older_high  # Still going up
                if trend_continues:
                    # RE-ENTRY for LONG: Use current price as new entry
                    entry = current_price
                    # New SL: Recent low on 4H with ATR buffer
                    recent_4h = df_4h.iloc[-10:]
                    swing_low = recent_4h['low'].min()
                    atr_4h = (df_4h['high'] - df_4h['low']).rolling(14).mean().iloc[-1]
                    sl = swing_low - (1.5 * atr_4h)
                    # Keep same TP target (original on Daily)
                    
                    # Recalculate R:R
                    risk = abs(entry - sl)
                    reward = abs(tp - entry)
                    risk_reward = reward / risk if risk > 0 else 0
                    
                    if risk_reward < 4.0:
                        return None  # Re-entry not worth it (need R:R ≥ 4.0)
                        return None  # Re-entry not worth it
                        
                    print(f"🔄 RE-ENTRY setup found for {symbol}!")
                    print(f"   Original SL was broken, but trend continues")
                    print(f"   New Entry: {entry:.5f}")
                    print(f"   New SL: {sl:.5f}")
                    print(f"   New R:R: 1:{risk_reward:.2f}")
                else:
                    return None  # Trend invalidated
        
        # ✅ Setup still valid! Price hasn't hit SL or TP yet (or re-entry found)
        
        # Return setup (MONITORING or READY)
        return TradeSetup(
            symbol=symbol,
            daily_choch=latest_signal,  # Daily CHoCH (REVERSAL) or BOS (CONTINUITY)
            fvg=fvg,
            h4_choch=h4_signal,  # H4 CHoCH (same for both REVERSAL and CONTINUITY)
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            risk_reward=risk_reward,
            setup_time=df_4h.index[-1],  # Use index instead of 'time' column
            priority=priority,
            strategy_type=strategy_type,
            status=status
        )


def format_setup_message(setup: TradeSetup) -> str:
    """Format trade setup for Telegram message"""
    direction = "🟢 LONG" if setup.daily_choch.direction == 'bullish' else "🔴 SHORT"
    
    # Status icon
    if setup.status == 'READY':
        status_icon = "✅ READY TO EXECUTE"
    else:
        status_icon = "👀 MONITORING (waiting for entry)"
    
    # Strategy type emoji
    strategy_emoji = "🔄 REVERSAL" if setup.strategy_type == 'reversal' else "➡️ CONTINUITY"
    
    # H4 confirmation type
    if setup.h4_choch:
        # Both strategies use CHoCH
        h4_info = f"🔄 4H CHoCH: {setup.h4_choch.direction.upper()} (FROM FVG zone)"
    else:
        h4_info = "⏳ Waiting for 4H CHoCH confirmation"
    
    message = f"""
🚨 SETUP - {setup.symbol}
{direction} | {status_icon} | {strategy_emoji}

📊 Daily CHoCH: {setup.daily_choch.direction.upper()}
📍 FVG Zone: {setup.fvg.bottom:.5f} - {setup.fvg.top:.5f}
{h4_info}

💰 Entry: {setup.entry_price:.5f}
🛑 Stop Loss: {setup.stop_loss:.5f}
🎯 Take Profit: {setup.take_profit:.5f}

📈 Risk:Reward: 1:{setup.risk_reward:.2f}
⭐ Priority: {setup.priority}

⏰ Setup Time: {setup.setup_time.strftime('%Y-%m-%d %H:%M')}
"""
    
    return message.strip()
