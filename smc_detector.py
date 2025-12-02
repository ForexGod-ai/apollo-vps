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
    strategy_type: str  # 'reversal' or 'continuation'
    status: str = 'MONITORING'  # 'MONITORING' (watching) or 'READY' (can execute)
    setup_time: datetime
    priority: int
    strategy_type: str = "reversal"  # 'reversal' or 'continuation'


class SMCDetector:
    """Detects Smart Money Concepts patterns"""
    
    def __init__(self, swing_lookback: int = 5):
        """
        Args:
            swing_lookback: Number of candles to look back for swing points
        """
        self.swing_lookback = swing_lookback
    
    def detect_swing_highs(self, df: pd.DataFrame) -> List[SwingPoint]:
        """
        Detect swing highs in price data
        Swing high = highest point with lower highs on both sides
        """
        swing_highs = []
        
        for i in range(self.swing_lookback, len(df) - self.swing_lookback):
            current_high = df['high'].iloc[i]
            
            # Check left side
            left_check = all(
                current_high > df['high'].iloc[i - j] 
                for j in range(1, self.swing_lookback + 1)
            )
            
            # Check right side
            right_check = all(
                current_high > df['high'].iloc[i + j] 
                for j in range(1, self.swing_lookback + 1)
            )
            
            if left_check and right_check:
                swing_highs.append(SwingPoint(
                    index=i,
                    price=current_high,
                    swing_type='high',
                    candle_time=df['time'].iloc[i]
                ))
        
        return swing_highs
    
    def detect_swing_lows(self, df: pd.DataFrame) -> List[SwingPoint]:
        """
        Detect swing lows in price data
        Swing low = lowest point with higher lows on both sides
        """
        swing_lows = []
        
        for i in range(self.swing_lookback, len(df) - self.swing_lookback):
            current_low = df['low'].iloc[i]
            
            # Check left side
            left_check = all(
                current_low < df['low'].iloc[i - j] 
                for j in range(1, self.swing_lookback + 1)
            )
            
            # Check right side
            right_check = all(
                current_low < df['low'].iloc[i + j] 
                for j in range(1, self.swing_lookback + 1)
            )
            
            if left_check and right_check:
                swing_lows.append(SwingPoint(
                    index=i,
                    price=current_low,
                    swing_type='low',
                    candle_time=df['time'].iloc[i]
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
                            
                            # Valid CHoCH only if BOTH LH and LL (confirmed bearish structure)
                            if lh_pattern and ll_pattern:
                                # POST-BREAK VALIDATION: Check if price CONFIRMS the change
                                # Look for swings AFTER the break to confirm HH or HL
                                swings_after_break = [s for s in swing_highs if s.index > j] + \
                                                    [s for s in swing_lows if s.index > j]
                                
                                # If we have recent data after break, validate confirmation
                                if len(swings_after_break) >= 1:
                                    # Check if any HIGH after break is Higher High
                                    highs_after = [s for s in swing_highs if s.index > j]
                                    lows_after = [s for s in swing_lows if s.index > j]
                                    
                                    confirmed = False
                                    # For BULLISH CHoCH: need HH or HL after break
                                    if len(highs_after) >= 1:
                                        # Is there a Higher High?
                                        if any(h.price > swing.price for h in highs_after):
                                            confirmed = True
                                    if not confirmed and len(lows_after) >= 1 and len(recent_lows) >= 1:
                                        # Is there a Higher Low?
                                        if any(l.price > recent_lows[-1].price for l in lows_after):
                                            confirmed = True
                                    
                                    if not confirmed:
                                        # No confirmation yet - might be pullback
                                        break
                                
                                chochs.append(CHoCH(
                                    index=j,
                                    direction='bullish',
                                    break_price=swing.price,
                                    previous_trend='bearish',
                                    candle_time=df['time'].iloc[j],
                                    swing_broken=swing
                                ))
                                current_trend = 'bullish'
                        elif current_trend == 'bullish':
                            # Already bullish, breaking another high → BOS
                            bos_list.append(BOS(
                                index=j,
                                direction='bullish',
                                break_price=swing.price,
                                candle_time=df['time'].iloc[j],
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
                            
                            # Valid CHoCH only if BOTH HH and HL (confirmed bullish structure)
                            if hh_pattern and hl_pattern:
                                # POST-BREAK VALIDATION: Check if price CONFIRMS the change
                                # Look for swings AFTER the break to confirm LH or LL
                                swings_after_break = [s for s in swing_highs if s.index > j] + \
                                                    [s for s in swing_lows if s.index > j]
                                
                                # If we have recent data after break, validate confirmation
                                if len(swings_after_break) >= 1:
                                    # Check if any LOW after break is Lower Low
                                    highs_after = [s for s in swing_highs if s.index > j]
                                    lows_after = [s for s in swing_lows if s.index > j]
                                    
                                    confirmed = False
                                    # For BEARISH CHoCH: need LL or LH after break
                                    if len(lows_after) >= 1:
                                        # Is there a Lower Low?
                                        if any(l.price < swing.price for l in lows_after):
                                            confirmed = True
                                    if not confirmed and len(highs_after) >= 1 and len(recent_highs) >= 1:
                                        # Is there a Lower High?
                                        if any(h.price < recent_highs[-1].price for h in highs_after):
                                            confirmed = True
                                    
                                    if not confirmed:
                                        # No confirmation yet - might be pullback
                                        break
                                
                                chochs.append(CHoCH(
                                    index=j,
                                    direction='bearish',
                                    break_price=swing.price,
                                    previous_trend='bullish',
                                    candle_time=df['time'].iloc[j],
                                    swing_broken=swing
                                ))
                                current_trend = 'bearish'
                        elif current_trend == 'bearish':
                            # Already bearish, breaking another low → BOS
                            bos_list.append(BOS(
                                index=j,
                                direction='bearish',
                                break_price=swing.price,
                                candle_time=df['time'].iloc[j],
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
                        candle_time=df['time'].iloc[i],
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
                        candle_time=df['time'].iloc[i],
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
                            candle_time=df['time'].iloc[fvg_index],
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
                            candle_time=df['time'].iloc[fvg_index],
                            is_filled=False,
                            associated_choch=choch
                        ))
        
        # Return the best FVG (closest to current price or most recent)
        if all_fvgs:
            # For bearish: closest FVG above current price
            # For bullish: closest FVG below current price
            if choch.direction == 'bearish':
                # Find FVG with bottom closest to (but ideally above or near) current price
                all_fvgs.sort(key=lambda fvg: abs(fvg.bottom - current_price))
            else:
                # Find FVG with top closest to (but ideally below or near) current price
                all_fvgs.sort(key=lambda fvg: abs(fvg.top - current_price))
            
            return all_fvgs[0]
        
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
            # Entry = Slightly ABOVE middle (wait for price to confirm entry)
            # Middle + 0.5% of FVG range
            fvg_range = fvg.top - fvg.bottom
            entry = fvg.middle + (fvg_range * 0.005)
            
            # SL = Last Low on 4H BEFORE the FVG (swing low that created FVG)
            # Look at 4H candles around FVG formation time
            fvg_index_4h = df_4h[df_4h['time'] <= fvg.candle_time].index[-1] if len(df_4h[df_4h['time'] <= fvg.candle_time]) > 0 else len(df_4h) - 20
            lookback_start = max(0, fvg_index_4h - 30)
            lookback_end = min(len(df_4h), fvg_index_4h + 10)
            recent_lows = df_4h['low'].iloc[lookback_start:lookback_end]
            stop_loss = recent_lows.min()
            
            # TP = Last High on Daily (aim for higher structure)
            # EXPANDED: Look at last 30 days for major structure points (not just 10)
            recent_highs = df_daily['high'].iloc[-30:]
            take_profit = recent_highs.max()
            
        else:
            # SHORT TRADE (Daily bearish trend)
            # Entry = Slightly BELOW middle (wait for price to confirm pullback)
            # Middle - 0.5% of FVG range
            fvg_range = fvg.top - fvg.bottom
            entry = fvg.middle - (fvg_range * 0.005)
            
            # SL = Last High on 4H BEFORE/AROUND the FVG (swing high that created FVG)
            # Look at 4H candles around FVG formation time (not just last 20!)
            fvg_index_4h = df_4h[df_4h['time'] <= fvg.candle_time].index[-1] if len(df_4h[df_4h['time'] <= fvg.candle_time]) > 0 else len(df_4h) - 20
            lookback_start = max(0, fvg_index_4h - 30)
            lookback_end = min(len(df_4h), fvg_index_4h + 10)
            recent_highs = df_4h['high'].iloc[lookback_start:lookback_end]
            stop_loss = recent_highs.max()
            
            # TP = Last Low on Daily (aim for lower structure)
            # EXPANDED: Look at last 30 days for major structure points (not just 10)
            recent_lows = df_daily['low'].iloc[-30:]
            take_profit = recent_lows.min()
        
        return entry, stop_loss, take_profit
    
    def detect_strategy_type(
        self,
        df_daily: pd.DataFrame,
        latest_choch: CHoCH
    ) -> str:
        """
        Determine if setup is REVERSAL or CONTINUATION
        
        REVERSAL: Daily CHoCH changes trend direction completely
        - Bullish: Previous trend was bearish (LL→HH) - MAJOR reversal
        - Bearish: Previous trend was bullish (HH→LL) - MAJOR reversal
        
        CONTINUATION: Daily CHoCH is a pullback in existing trend
        - Bullish continuation: Uptrend → pullback (HL) → resume (HH)
        - Bearish continuation: Downtrend → pullback (LH) → resume (LL)
        
        Returns:
            'reversal' or 'continuation'
        """
        # Look at swing points before the CHoCH
        swing_highs = self.detect_swing_highs(df_daily)
        swing_lows = self.detect_swing_lows(df_daily)
        
        # Get swings before CHoCH
        swings_before = []
        for sh in swing_highs:
            if sh.index < latest_choch.index:
                swings_before.append(('high', sh.price, sh.index))
        for sl in swing_lows:
            if sl.index < latest_choch.index:
                swings_before.append(('low', sl.price, sl.index))
        
        # Sort by index
        swings_before.sort(key=lambda x: x[2])
        
        if len(swings_before) < 3:
            # Not enough data, default to reversal
            return 'reversal'
        
        # Get last 3 swings
        last_3_swings = swings_before[-3:]
        
        if latest_choch.direction == 'bullish':
            # Bullish CHoCH - check if it's continuation or reversal
            # Reversal: LL → LL → HH (breaking out of downtrend)
            # Continuation: HL in uptrend, then resuming
            
            # Check if we had higher lows (uptrend continuation)
            lows = [s for s in last_3_swings if s[0] == 'low']
            if len(lows) >= 2:
                # If recent lows are higher (HL pattern) = continuation
                if lows[-1][1] > lows[-2][1]:
                    return 'continuation'
            
            # Otherwise reversal (breaking from downtrend)
            return 'reversal'
        
        else:  # bearish CHoCH
            # Bearish CHoCH - check if it's continuation or reversal
            # Reversal: HH → HH → LL (breaking out of uptrend)
            # Continuation: LH in downtrend, then resuming
            
            # Check if we had lower highs (downtrend continuation)
            highs = [s for s in last_3_swings if s[0] == 'high']
            if len(highs) >= 2:
                # If recent highs are lower (LH pattern) = continuation
                if highs[-1][1] < highs[-2][1]:
                    return 'continuation'
            
            # Otherwise reversal (breaking from uptrend)
            return 'reversal'
    
    def scan_for_setup(
        self, 
        symbol: str,
        df_daily: pd.DataFrame, 
        df_4h: pd.DataFrame,
        priority: int
    ) -> Optional[TradeSetup]:
        """
        Main scanner: Check if "Glitch in Matrix" setup exists
        
        FINAL LOGIC (Dec 2025 - CHoCH + BOS):
        - CHoCH = SCHIMBAREA trendului (o dată când se inversează)
        - BOS = CONTINUAREA trendului (HH în bullish, LL în bearish)
        - Ultimul CHoCH pe Daily = trendul ACTUAL
        - Doar trades în direcția ultimului CHoCH
        
        Steps:
        1. Detect Daily CHoCH (ultimul = trendul curent)
        2. Find FVG after CHoCH
        3. Check if price is retesting FVG
        4. Check 4H for confirmation (CHoCH sau BOS în aceeași direcție)
        5. Return complete setup
        """
        # Step 1: Detect Daily CHoCH
        daily_chochs = self.detect_choch(df_daily)
        
        if not daily_chochs:
            return None  # No CHoCH found
        
        # Get most recent CHoCH = TRENDUL ACTUAL
        latest_choch = daily_chochs[-1]
        current_trend = latest_choch.direction  # 'bullish' or 'bearish'
        
        # Step 2: Find FVG after CHoCH (closest to current price)
        current_price = df_daily['close'].iloc[-1]
        fvg = self.detect_fvg(df_daily, latest_choch, current_price)
        
        if not fvg:
            return None  # No FVG found
        
        # FVG direction must match current trend
        fvg.direction = current_trend
        
        # Step 4: Check price relationship with FVG
        current_price = df_daily['close'].iloc[-1]
        
        # NEW: More flexible - accept setups even if price not perfectly in FVG yet
        price_approaching_fvg = False
        price_in_fvg = self.is_price_in_fvg(current_price, fvg)
        
        if current_trend == 'bullish':
            # BULLISH: Price should be BELOW or IN FVG (waiting for pullback to buy)
            if current_price <= fvg.top:
                price_approaching_fvg = True
        else:
            # BEARISH: Price should be ABOVE or IN FVG (waiting for pullback to sell)
            if current_price >= fvg.bottom:
                price_approaching_fvg = True
        
        if not price_approaching_fvg:
            return None  # Price too far from FVG
        
        # Step 5: Detect strategy type
        strategy_type = self.detect_strategy_type(df_daily, latest_choch)
        
        # Step 6: Check 4H for confirmation (OPTIONAL for MONITORING status)
        h4_chochs = self.detect_choch(df_4h)
        
        # Find 4H CHoCH that matches current trend
        valid_h4_choch = None
        
        for h4_choch in reversed(h4_chochs):  # Start from most recent
            # 4H must confirm CURRENT TREND direction
            if h4_choch.direction != current_trend:
                continue
            
            # Check if CHoCH happened inside or near FVG zone
            h4_price_at_choch = df_4h['close'].iloc[h4_choch.index]
            
            if self.is_price_in_fvg(h4_price_at_choch, fvg):
                # Found valid 4H confirmation!
                valid_h4_choch = h4_choch
                break
        
        # Determine setup status
        if valid_h4_choch and price_in_fvg:
            status = 'READY'  # Can execute now
        else:
            status = 'MONITORING'  # Watch and wait
        
        # Step 7: Calculate entry, SL, TP
        if valid_h4_choch:
            entry, sl, tp = self.calculate_entry_sl_tp(fvg, valid_h4_choch, df_4h, df_daily)
        else:
            # No 4H CHoCH yet - use FVG middle as estimated entry
            entry = fvg.middle
            if current_trend == 'bullish':
                sl = fvg.bottom * 0.998  # SL below FVG
                tp = fvg.top * 1.015  # TP above FVG
            else:
                sl = fvg.top * 1.002  # SL above FVG
                tp = fvg.bottom * 0.985  # TP below FVG
        
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        risk_reward = reward / risk if risk > 0 else 0
        
        if risk_reward < 1.0:  # Relaxed from 1.5 for MONITORING
            return None
        
        # Return setup (MONITORING or READY)
        return TradeSetup(
            symbol=symbol,
            daily_choch=latest_choch,
            fvg=fvg,
            h4_choch=valid_h4_choch,  # May be None
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            risk_reward=risk_reward,
            setup_time=df_4h['time'].iloc[-1],
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
    
    h4_info = f"🔄 4H CHoCH: {setup.h4_choch.direction.upper()} (inside FVG)" if setup.h4_choch else "⏳ Waiting for 4H confirmation"
    
    message = f"""
🚨 SETUP - {setup.symbol}
{direction} | {status_icon}

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
