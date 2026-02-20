import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from datetime import datetime


@dataclass
class SwingPoint:
    index: int
    price: float
    swing_type: str  # 'high' or 'low'
    candle_time: datetime


@dataclass
class CHoCH:
    index: int
    direction: str
    break_price: float
    previous_trend: str
    candle_time: datetime
    swing_broken: SwingPoint
 

@dataclass
class BOS:
    index: int
    direction: str
    break_price: float
    candle_time: datetime
    swing_broken: SwingPoint


@dataclass
class FVG:
    index: int
    direction: str
    top: float
    bottom: float
    middle: float
    candle_time: datetime
    is_filled: bool = False
    associated_choch: Optional[CHoCH] = None
    quality_score: int = 0


@dataclass
class OrderBlock:
    """📦 Order Block - Ultima lumânare opusă înainte de impuls instituțional (CHoCH)"""
    index: int
    direction: str  # 'bullish' or 'bearish'
    top: float  # Body high pentru bullish, wick high pentru bearish
    bottom: float  # Wick low pentru bullish, body low pentru bearish
    middle: float
    candle_time: datetime
    associated_choch: Optional[CHoCH] = None
    associated_fvg: Optional[FVG] = None  # FVG lăsat de impuls
    has_unfilled_fvg: bool = False  # TRUE = Setup 10/10 (OB + FVG necompletat)
    ob_score: int = 0  # 1-10 scoring (10 = OB + unfilled FVG)
    impulse_strength: float = 0.0  # Mărimea impulsului după OB (în pips/pct)


@dataclass
class TradeSetup:
    symbol: str
    daily_choch: CHoCH
    fvg: FVG
    h4_choch: Optional[CHoCH]
    h1_choch: Optional[CHoCH] = None  # V3.0: 1H CHoCH for GBP pairs
    order_block: Optional['OrderBlock'] = None  # 📦 V3.5: Order Block pentru entry precision
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_reward: float = 0.0
    estimated_rr: float = 0.0  # 🎯 V3.5: RR estimat pentru swing (minimum 1:5)
    setup_time: datetime = None
    priority: int = 0
    strategy_type: str = "reversal"
    status: str = 'MONITORING'

# ------------------- SMCDetector -------------------


class SMCDetector:
    def __init__(self, swing_lookback: int = 5):
        self.swing_lookback = swing_lookback
        # Track FVG zones with trade count for ALL pairs (UNIVERSAL anti-overtrading)
        # Format: {symbol: [(top, bottom, date, trade_count), ...]}
        self.fvg_zones_tracker = {}  # UNIVERSAL for all pairs
        
        # 🎯 V3.4 ORDER BLOCKS PREPARATION: Store last 2 FVG zones per timeframe as "price magnets"
        # Format: {symbol: {'4H': [FVG, FVG], '1H': [FVG, FVG]}}
        self.fvg_magnets = {}  # Zonele de întoarcere pentru preț
    
    def store_fvg_magnet(self, symbol: str, timeframe: str, fvg: FVG) -> None:
        """
        🎯 V3.4 ORDER BLOCKS: Store last 2 FVG zones per timeframe as price magnets
        These zones act as "zones of return" where price is likely to react
        
        Args:
            symbol: Trading pair (e.g., 'GBPUSD')
            timeframe: '4H' or '1H'
            fvg: FVG object to store
        """
        if symbol not in self.fvg_magnets:
            self.fvg_magnets[symbol] = {'4H': [], '1H': []}
        
        # Add new FVG to the list
        self.fvg_magnets[symbol][timeframe].append(fvg)
        
        # Keep only last 2 FVGs (most recent zones)
        self.fvg_magnets[symbol][timeframe] = self.fvg_magnets[symbol][timeframe][-2:]
        
        # DEBUG LOG
        print(f"🎯 ORDER BLOCK MAGNET: {symbol} {timeframe} - Stored FVG zone {fvg.bottom:.5f}-{fvg.top:.5f}")
        print(f"   Total magnets for {symbol} {timeframe}: {len(self.fvg_magnets[symbol][timeframe])}")
    
    def get_fvg_magnets(self, symbol: str, timeframe: str) -> List[FVG]:
        """
        Get stored FVG magnets for a symbol/timeframe
        Returns empty list if none exist
        """
        if symbol not in self.fvg_magnets:
            return []
        return self.fvg_magnets[symbol].get(timeframe, [])
    
    def detect_liquidity_sweep(
        self,
        df: pd.DataFrame,
        choch: CHoCH,
        lookback: int = 20,
        tolerance_pips: float = 5,
        debug: bool = False
    ) -> Optional[Dict]:
        """
        💧 V4.0 LIQUIDITY SWEEP DETECTION: Identifică sweep-uri de stop loss
        
        LOGIC:
        1. Găsește Equal Highs/Lows (în raza de 5 pips)
        2. Verifică dacă CHoCH a fost precedat de sweep (wick prin nivel + close înapoi)
        3. Dacă YES → +20 Confidence Boost (setup validat de Smart Money)
        
        Args:
            df: DataFrame with OHLC data
            choch: CHoCH object (break point)
            lookback: Candles to scan for equal levels (default 20)
            tolerance_pips: Pip tolerance for "equal" levels (default 5)
            debug: Print debug info
        
        Returns:
            {
                'sweep_detected': bool,
                'sweep_type': 'BSL' | 'SSL' | None,  # Buy Side / Sell Side Liquidity
                'sweep_price': float,
                'sweep_index': int,
                'equal_level_count': int  # How many times level was tested
            }
        """
        if choch is None or len(df) < lookback:
            return None
        
        choch_idx = choch.index
        
        # Calculate pip multiplier (JPY vs standard)
        # Assume standard (4 decimals) for now, can be enhanced per symbol
        pip_multiplier = 10000
        tolerance = tolerance_pips / pip_multiplier
        
        # STEP 1: Find equal highs/lows BEFORE CHoCH
        lookback_start = max(0, choch_idx - lookback)
        lookback_df = df.iloc[lookback_start:choch_idx]
        
        equal_highs = []  # BSL (Buy Side Liquidity)
        equal_lows = []   # SSL (Sell Side Liquidity)
        
        # Identify equal highs (BSL pools)
        for i in range(len(lookback_df) - 1):
            current_high = lookback_df.iloc[i]['high']
            
            # Check if this high is "equal" to any subsequent high
            for j in range(i + 1, len(lookback_df)):
                next_high = lookback_df.iloc[j]['high']
                
                if abs(current_high - next_high) <= tolerance:
                    equal_highs.append({
                        'price': current_high,
                        'indices': [lookback_start + i, lookback_start + j],
                        'count': 2
                    })
                    break
        
        # Identify equal lows (SSL pools)
        for i in range(len(lookback_df) - 1):
            current_low = lookback_df.iloc[i]['low']
            
            for j in range(i + 1, len(lookback_df)):
                next_low = lookback_df.iloc[j]['low']
                
                if abs(current_low - next_low) <= tolerance:
                    equal_lows.append({
                        'price': current_low,
                        'indices': [lookback_start + i, lookback_start + j],
                        'count': 2
                    })
                    break
        
        # STEP 2: Check if CHoCH was preceded by liquidity sweep
        sweep_detected = False
        sweep_type = None
        sweep_price = None
        sweep_index = None
        equal_level_count = 0
        
        if choch.direction == 'bullish':
            # BULLISH CHoCH → Look for SSL sweep (fake breakdown)
            # Price should have dipped BELOW equal lows, then closed back ABOVE
            
            if equal_lows:
                # Get most recent equal low before CHoCH
                most_recent_ssl = equal_lows[-1]
                ssl_price = most_recent_ssl['price']
                equal_level_count = most_recent_ssl['count']
                
                # Check 3 candles before CHoCH for sweep pattern
                sweep_window = df.iloc[max(0, choch_idx - 3):choch_idx]
                
                for idx, candle in sweep_window.iterrows():
                    # Sweep = wick BELOW ssl_price BUT close ABOVE
                    if candle['low'] < ssl_price and candle['close'] > ssl_price:
                        sweep_detected = True
                        sweep_type = 'SSL'
                        sweep_price = ssl_price
                        sweep_index = idx
                        break
        
        elif choch.direction == 'bearish':
            # BEARISH CHoCH → Look for BSL sweep (fake breakout)
            # Price should have spiked ABOVE equal highs, then closed back BELOW
            
            if equal_highs:
                # Get most recent equal high before CHoCH
                most_recent_bsl = equal_highs[-1]
                bsl_price = most_recent_bsl['price']
                equal_level_count = most_recent_bsl['count']
                
                # Check 3 candles before CHoCH for sweep pattern
                sweep_window = df.iloc[max(0, choch_idx - 3):choch_idx]
                
                for idx, candle in sweep_window.iterrows():
                    # Sweep = wick ABOVE bsl_price BUT close BELOW
                    if candle['high'] > bsl_price and candle['close'] < bsl_price:
                        sweep_detected = True
                        sweep_type = 'BSL'
                        sweep_price = bsl_price
                        sweep_index = idx
                        break
        
        if debug and sweep_detected:
            print(f"\n💧 LIQUIDITY SWEEP DETECTED:")
            print(f"   Type: {sweep_type} (Smart Money swept stops)")
            print(f"   Price: {sweep_price:.5f}")
            print(f"   Equal level tested: {equal_level_count} times")
            print(f"   CHoCH direction: {choch.direction.upper()}")
            print(f"   ✅ +20 Confidence Boost (validated by liquidity raid)")
        elif debug:
            print(f"\n💧 LIQUIDITY SWEEP: Not detected")
            print(f"   Equal highs found: {len(equal_highs)}")
            print(f"   Equal lows found: {len(equal_lows)}")
        
        if not sweep_detected:
            return None
        
        return {
            'sweep_detected': True,
            'sweep_type': sweep_type,
            'sweep_price': sweep_price,
            'sweep_index': sweep_index,
            'equal_level_count': equal_level_count
        }
    
    def detect_order_block(
        self, 
        df: pd.DataFrame, 
        choch: CHoCH, 
        fvg: Optional[FVG] = None,
        debug: bool = False
    ) -> Optional['OrderBlock']:
        """
        🎯 V3.5 ORDER BLOCKS: Detectează ultima lumânare opusă înainte de impuls
        
        LOGIC:
        1. Găsește CHoCH (break of structure)
        2. Identifică ultima lumânare OPUSĂ înainte de impuls (Order Block)
        3. Verifică dacă impulsul a lăsat FVG (validare instituțională)
        4. Scorează OB (10/10 dacă FVG necompletat lângă el)
        
        Args:
            df: DataFrame with OHLC data
            choch: CHoCH object (break point)
            fvg: Optional FVG object (pentru corelație)
            debug: Print debug info
        
        Returns:
            OrderBlock object or None
        """
        if choch is None:
            return None
        
        choch_idx = choch.index
        
        # STEP 1: Identifică ultima lumânare OPUSĂ înainte de CHoCH
        # Bullish CHoCH → căutăm ultima lumânare BEARISH (red candle)
        # Bearish CHoCH → căutăm ultima lumânare BULLISH (green candle)
        
        # Lookback range: 10 candele înainte de CHoCH (suficient pentru OB detection)
        lookback_start = max(0, choch_idx - 10)
        
        ob_candle_idx = None
        
        if choch.direction == 'bullish':
            # Căutăm ultima lumânare BEARISH (close < open)
            for i in range(choch_idx - 1, lookback_start - 1, -1):
                if df['close'].iloc[i] < df['open'].iloc[i]:
                    ob_candle_idx = i
                    break
        
        elif choch.direction == 'bearish':
            # Căutăm ultima lumânare BULLISH (close > open)
            for i in range(choch_idx - 1, lookback_start - 1, -1):
                if df['close'].iloc[i] > df['open'].iloc[i]:
                    ob_candle_idx = i
                    break
        
        if ob_candle_idx is None:
            if debug:
                print(f"   ⚠️ No Order Block found (no opposite candle before CHoCH)")
            return None
        
        # STEP 2: Extrage zonă Order Block
        # Bullish OB (după bearish candle): Body high + Wick low
        # Bearish OB (după bullish candle): Wick high + Body low
        
        ob_open = df['open'].iloc[ob_candle_idx]
        ob_close = df['close'].iloc[ob_candle_idx]
        ob_high = df['high'].iloc[ob_candle_idx]
        ob_low = df['low'].iloc[ob_candle_idx]
        ob_time = df['time'].iloc[ob_candle_idx] if 'time' in df.columns else ob_candle_idx
        
        if choch.direction == 'bullish':
            # Bullish OB: Body high to Wick low (zone unde price se va întoarce)
            ob_top = max(ob_open, ob_close)  # Body high
            ob_bottom = ob_low  # Wick low
        else:
            # Bearish OB: Wick high to Body low
            ob_top = ob_high  # Wick high
            ob_bottom = min(ob_open, ob_close)  # Body low
        
        ob_middle = (ob_top + ob_bottom) / 2
        
        # STEP 3: Calculează impulse strength (mărimea mișcării după OB)
        impulse_start = ob_candle_idx
        impulse_end = min(choch_idx + 5, len(df) - 1)  # 5 candele după CHoCH
        
        if choch.direction == 'bullish':
            impulse_high = df['high'].iloc[impulse_start:impulse_end].max()
            impulse_strength = impulse_high - ob_bottom
        else:
            impulse_low = df['low'].iloc[impulse_start:impulse_end].min()
            impulse_strength = ob_top - impulse_low
        
        impulse_strength_pct = (impulse_strength / ob_middle) * 100
        
        # STEP 4: Verifică corelație cu FVG (OB + unfilled FVG = SCOR 10/10)
        has_unfilled_fvg = False
        ob_score = 5  # Base score
        
        if fvg is not None:
            # Verifică dacă FVG este LÂNGĂ Order Block (gap < 50 pips sau overlap)
            fvg_distance = abs(fvg.middle - ob_middle)
            ob_size = ob_top - ob_bottom
            
            # Proximity check: FVG în raza de 2x mărimea OB
            is_proximate = fvg_distance < (ob_size * 2)
            
            # Verifică dacă FVG este NECOMPLETAT (unfilled)
            if not fvg.is_filled and is_proximate:
                has_unfilled_fvg = True
                ob_score = 10  # PERFECT SETUP!
            elif is_proximate:
                ob_score = 8  # FVG filled dar proxim
            else:
                ob_score = 6  # FVG exists dar departe
        
        # STEP 5: Bonus pentru impuls puternic (>1% move)
        if impulse_strength_pct > 1.0:
            ob_score = min(10, ob_score + 1)
        
        # STEP 6: Creează Order Block object
        order_block = OrderBlock(
            index=ob_candle_idx,
            direction=choch.direction,
            top=ob_top,
            bottom=ob_bottom,
            middle=ob_middle,
            candle_time=ob_time,
            associated_choch=choch,
            associated_fvg=fvg,
            has_unfilled_fvg=has_unfilled_fvg,
            ob_score=ob_score,
            impulse_strength=impulse_strength_pct
        )
        
        if debug:
            print(f"\n📦 ORDER BLOCK DETECTED:")
            print(f"   Direction: {choch.direction.upper()}")
            print(f"   Zone: {ob_bottom:.5f} - {ob_top:.5f} (Middle: {ob_middle:.5f})")
            print(f"   Impulse Strength: {impulse_strength_pct:.2f}%")
            print(f"   FVG Correlation: {'✅ UNFILLED FVG!' if has_unfilled_fvg else '⚠️ No FVG' if fvg is None else 'FVG filled'}")
            print(f"   OB Score: {ob_score}/10")
        
        return order_block

    def detect_choch(self, df: pd.DataFrame) -> List[CHoCH]:
        """
        Wrapper simplu: returnează doar lista de CHoCH folosind detect_choch_and_bos.
        """
        chochs, _ = self.detect_choch_and_bos(df)
        return chochs

    def detect_fvg(self, df: pd.DataFrame, choch, current_price) -> Optional[FVG]:
        all_fvgs = []
        start_idx = choch.index if hasattr(choch, 'index') else 0
        end_idx = len(df)
        # METHOD 1: Strict 3-candle gap (classic FVG)
        for i in range(start_idx + 2, end_idx):
            if choch.direction == 'bullish':
                if df['high'].iloc[i - 2] < df['low'].iloc[i]:
                    gap_top = df['low'].iloc[i]
                    gap_bottom = df['high'].iloc[i - 2]
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
        # METHOD 2: Large imbalance zone (REVERSAL setup)
        if not all_fvgs:
            swing_highs = self.detect_swing_highs(df)
            swing_lows = self.detect_swing_lows(df)
            if choch.direction == 'bullish':
                lows_before = [sl for sl in swing_lows if sl.index < choch.index]
                highs_after = [sh for sh in swing_highs if sh.index >= choch.index and sh.index < end_idx]
                if lows_before:
                    last_low = lows_before[-1]
                    gap_bottom = last_low.price
                    if highs_after:
                        gap_top = max([sh.price for sh in highs_after])
                        fvg_index = highs_after[0].index
                    else:
                        # Use body highs (not wicks) for consistent FVG zone definition
                        body_highs = df[['open', 'close']].max(axis=1)
                        gap_top = body_highs.iloc[start_idx:end_idx].max()
                        fvg_index = start_idx + body_highs.iloc[start_idx:end_idx].argmax()
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
                highs_before = [sh for sh in swing_highs if sh.index < choch.index]
                lows_after = [sl for sl in swing_lows if sl.index >= choch.index and sl.index < end_idx]
                if highs_before:
                    last_high = highs_before[-1]
                    gap_top = last_high.price
                    if lows_after:
                        gap_bottom = min([sl.price for sl in lows_after])
                        fvg_index = lows_after[0].index
                    else:
                        gap_bottom = df['low'].iloc[start_idx:end_idx].min()
                        fvg_index = start_idx + df['low'].iloc[start_idx:end_idx].argmin()
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
        if all_fvgs:
            all_fvgs.sort(key=lambda fvg: fvg.index)
            return all_fvgs[-1]
        return None

    def detect_swing_lows(self, df: pd.DataFrame) -> List[SwingPoint]:
        if df is None or len(df) == 0:
            return []
        
        # 🛡️ SAFETY CHECK: Verificare lungime minimă pentru swing_lookback
        min_length = (self.swing_lookback * 2) + 1
        if len(df) < min_length:
            return []  # Nu avem suficiente candele pentru lookback=5 (need 11 minimum)
        
        swing_lows = []
        body_lows = df[['open', 'close']].min(axis=1)
        for i in range(self.swing_lookback, len(df) - self.swing_lookback):
            current_low = body_lows.iloc[i]
            left_check = all(
                current_low < body_lows.iloc[i - j]
                for j in range(1, self.swing_lookback + 1)
            )
            right_check = all(
                current_low < body_lows.iloc[i + j]
                for j in range(1, self.swing_lookback + 1)
            )
            if left_check and right_check:
                swing_lows.append(SwingPoint(
                    index=i,
                    price=current_low,
                    swing_type='low',
                    candle_time=df['time'].iloc[i] if 'time' in df.columns else i
                ))
        return swing_lows

    # ...restul metodelor din SMCDetector (detect_choch_and_bos, detect_swing_highs, calculate_entry_sl_tp etc.)...
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
                            
                            # STRICT VALIDATION: CHoCH requires BOTH LH AND LL patterns
                            # This ensures we only detect TRUE structure changes (REVERSAL)
                            # If only one pattern exists → it's BOS, not CHoCH!
                            if lh_pattern and ll_pattern:  # AND - both patterns required!
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
                            
                            # STRICT VALIDATION: CHoCH requires BOTH HH AND HL patterns
                            # This ensures we only detect TRUE structure changes (REVERSAL)
                            # If only one pattern exists → it's BOS, not CHoCH!
                            if hh_pattern and hl_pattern:  # AND - both patterns required!
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
    
    def detect_swing_highs(self, df: pd.DataFrame) -> List[SwingPoint]:
        """Detect swing highs using BODY CLOSURE (not wicks) - Smart Money Concepts principle."""
        if df is None or len(df) == 0:
            return []
        
        # 🛡️ SAFETY CHECK: Verificare lungime minimă pentru swing_lookback (consistent cu detect_swing_lows)
        min_length = (self.swing_lookback * 2) + 1
        if len(df) < min_length:
            return []  # Nu avem suficiente candele pentru lookback=5 (need 11 minimum)
        
        swing_highs = []
        # Calculate body highs (max of open/close) - ignores wicks
        body_highs = df[['open', 'close']].max(axis=1)
        
        for i in range(2, len(df) - 2):
            if (
                body_highs.iloc[i] > body_highs.iloc[i - 1]
                and body_highs.iloc[i] > body_highs.iloc[i - 2]
                and body_highs.iloc[i] > body_highs.iloc[i + 1]
                and body_highs.iloc[i] > body_highs.iloc[i + 2]
            ):
                swing_highs.append(SwingPoint(
                    index=i,
                    price=body_highs.iloc[i],  # Use body high, not wick
                    swing_type='high',
                    candle_time=df['time'].iloc[i] if 'time' in df.columns else i
                ))
        return swing_highs

    def detect_swing_lows(self, df: pd.DataFrame) -> List[SwingPoint]:
        if df is None or len(df) == 0:
            return []
        
        # 🛡️ SAFETY CHECK: Asigurare că avem suficiente candele pentru swing detection
        if len(df) < 5:
            return []  # Minimum 5 candele pentru swing points (2 left + 1 center + 2 right)
        
        swing_lows = []
        for i in range(2, len(df) - 2):
            if (
                df['low'].iloc[i] < df['low'].iloc[i - 1]
                and df['low'].iloc[i] < df['low'].iloc[i - 2]
                and df['low'].iloc[i] < df['low'].iloc[i + 1]
                and df['low'].iloc[i] < df['low'].iloc[i + 2]
            ):
                swing_lows.append(SwingPoint(
                    index=i,
                    price=df['low'].iloc[i],
                    swing_type='low',
                    candle_time=df['time'].iloc[i] if 'time' in df.columns else i
                ))
        return swing_lows

    def detect_choch_and_bos(self, df: pd.DataFrame) -> Tuple[List[CHoCH], List[BOS]]:
        chochs = []
        bos_list = []
        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        prev_trend = None
        for i in range(1, len(swing_highs)):
            if swing_highs[i].price > swing_highs[i - 1].price:
                bos_list.append(BOS(
                    index=swing_highs[i].index,
                    direction='bullish',
                    break_price=swing_highs[i - 1].price,  # FIXED: Price that got broken (previous swing)
                    candle_time=swing_highs[i].candle_time,
                    swing_broken=swing_highs[i-1]
                ))
        for i in range(1, len(swing_lows)):
            if swing_lows[i].price < swing_lows[i - 1].price:
                bos_list.append(BOS(
                    index=swing_lows[i].index,
                    direction='bearish',
                    break_price=swing_lows[i - 1].price,  # FIXED: Price that got broken (previous swing)
                    candle_time=swing_lows[i].candle_time,
                    swing_broken=swing_lows[i-1]
                ))
        # CHoCH detection with CLOSE confirmation
        for i in range(1, min(len(swing_highs), len(swing_lows))):
            if prev_trend == 'bearish' and swing_highs[i].price > swing_highs[i - 1].price:
                # VALIDATION: Confirm Close price is above previous swing high
                swing_idx = swing_highs[i].index
                close_price = df['close'].iloc[swing_idx]
                prev_swing_high = swing_highs[i - 1].price
                
                if close_price > prev_swing_high:
                    chochs.append(CHoCH(
                        index=swing_highs[i].index,
                        direction='bullish',
                        break_price=swing_highs[i].price,
                        previous_trend=prev_trend,
                        candle_time=swing_highs[i].candle_time,
                        swing_broken=swing_highs[i-1]
                    ))
                    prev_trend = 'bullish'
            elif prev_trend == 'bullish' and swing_lows[i].price < swing_lows[i - 1].price:
                # VALIDATION: Confirm Close price is below previous swing low
                swing_idx = swing_lows[i].index
                close_price = df['close'].iloc[swing_idx]
                prev_swing_low = swing_lows[i - 1].price
                
                if close_price < prev_swing_low:
                    chochs.append(CHoCH(
                        index=swing_lows[i].index,
                        direction='bearish',
                        break_price=swing_lows[i].price,
                        previous_trend=prev_trend,
                        candle_time=swing_lows[i].candle_time,
                        swing_broken=swing_lows[i-1]
                    ))
                    prev_trend = 'bearish'
            else:
                if swing_highs[i].price > swing_highs[i - 1].price:
                    prev_trend = 'bullish'
                elif swing_lows[i].price < swing_lows[i - 1].price:
                    prev_trend = 'bearish'
        return chochs, bos_list
    
    def determine_daily_trend(self, df: pd.DataFrame) -> str:
        """
        V5.0 ANTI-COUNTER-TREND: Determine OVERALL Daily trend from swing structure
        
        This is NOT about latest signal (CHoCH/BOS), but about DOMINANT market structure.
        Analyzes last 3 swing highs and lows to identify the PREVAILING trend.
        
        Returns:
            'bullish': HH + HL pattern (strong uptrend)
            'bearish': LL + LH pattern (strong downtrend)
            'neutral': No clear pattern or mixed signals
        
        Purpose: Prevent counter-trend trades by validating setup against OVERALL bias
        """
        if df is None or len(df) < 20:
            return 'neutral'
        
        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        
        # Need at least 3 swings of each type for pattern analysis
        if len(swing_highs) < 3 or len(swing_lows) < 3:
            return 'neutral'
        
        # Get last 3 swings of each type
        recent_highs = swing_highs[-3:]
        recent_lows = swing_lows[-3:]
        
        # BULLISH STRUCTURE: Higher Highs (HH) + Higher Lows (HL)
        hh_count = 0
        for i in range(1, len(recent_highs)):
            if recent_highs[i].price > recent_highs[i-1].price:
                hh_count += 1
        
        hl_count = 0
        for i in range(1, len(recent_lows)):
            if recent_lows[i].price > recent_lows[i-1].price:
                hl_count += 1
        
        # BEARISH STRUCTURE: Lower Lows (LL) + Lower Highs (LH)
        ll_count = 0
        for i in range(1, len(recent_lows)):
            if recent_lows[i].price < recent_lows[i-1].price:
                ll_count += 1
        
        lh_count = 0
        for i in range(1, len(recent_highs)):
            if recent_highs[i].price < recent_highs[i-1].price:
                lh_count += 1
        
        # V5.1 FIX: More flexible pattern detection
        # Calculate DOMINANT direction based on overall count
        bullish_score = hh_count + hl_count
        bearish_score = ll_count + lh_count
        
        # BULLISH: Requires BOTH HH and HL patterns (at least 2/3 swings each) - STRICT
        if hh_count >= 2 and hl_count >= 1:
            return 'bullish'
        
        # BEARISH: Requires BOTH LL and LH patterns (at least 2/3 swings each) - STRICT  
        if ll_count >= 2 and lh_count >= 1:
            return 'bearish'
        
        # V5.1: If no perfect pattern, use DOMINANT direction (RELAXED)
        # This catches imperfect but clearly directional markets
        # Example: LL=1, LH=1 (score=2) vs HH=0, HL=0 (score=0) → Bearish dominant
        if bearish_score >= 2 and bearish_score > bullish_score:
            return 'bearish'  # Bearish dominant
        
        if bullish_score >= 2 and bullish_score > bearish_score:
            return 'bullish'  # Bullish dominant
        
        # No dominant pattern → neutral
        return 'neutral'
    
    def has_confirmation_swing(self, df: pd.DataFrame, choch: CHoCH) -> bool:
        """
        V5.0 REVERSAL VALIDATION: Check if CHoCH has post-break confirmation
        
        A CHoCH (Change of Character) signals POTENTIAL reversal, but needs confirmation.
        We check if market structure AFTER the CHoCH validates the new trend direction.
        
        Bullish CHoCH: Needs Higher Low (HL) after break
        Bearish CHoCH: Needs Lower High (LH) after break
        
        Args:
            df: DataFrame with OHLC data
            choch: CHoCH signal to validate
        
        Returns:
            True: Confirmation swing exists (reversal validated)
            False: No confirmation (premature reversal signal)
        """
        if df is None or len(df) < choch.index + 5:
            return False  # Not enough data after CHoCH
        
        # Get swings AFTER CHoCH (need at least 5 candles for swing detection)
        df_after_choch = df.iloc[choch.index:]
        
        swing_highs_after = self.detect_swing_highs(df_after_choch)
        swing_lows_after = self.detect_swing_lows(df_after_choch)
        
        if choch.direction == 'bullish':
            # BULLISH CHoCH: Look for Higher Low (HL) confirmation
            # Need: A swing low AFTER CHoCH that is HIGHER than swing low BEFORE CHoCH
            
            # Get swing lows BEFORE CHoCH
            swing_lows_before = self.detect_swing_lows(df.iloc[:choch.index])
            
            if not swing_lows_before or not swing_lows_after:
                return False
            
            last_low_before = swing_lows_before[-1].price
            
            # Check if ANY low after CHoCH is Higher Low
            for low_after in swing_lows_after:
                if low_after.price > last_low_before:
                    return True  # ✅ Higher Low confirmed!
            
            return False  # No HL found
        
        elif choch.direction == 'bearish':
            # BEARISH CHoCH: Look for Lower High (LH) confirmation
            # Need: A swing high AFTER CHoCH that is LOWER than swing high BEFORE CHoCH
            
            # Get swing highs BEFORE CHoCH
            swing_highs_before = self.detect_swing_highs(df.iloc[:choch.index])
            
            if not swing_highs_before or not swing_highs_after:
                return False
            
            last_high_before = swing_highs_before[-1].price
            
            # Check if ANY high after CHoCH is Lower High
            for high_after in swing_highs_after:
                if high_after.price < last_high_before:
                    return True  # ✅ Lower High confirmed!
            
            return False  # No LH found
        
        return False
        
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
    
    def _get_asset_class(self, symbol: str) -> str:
        """Detect asset class for symbol-specific SL rules"""
        symbol_upper = symbol.upper()
        if any(x in symbol_upper for x in ['BTC', 'ETH', 'XRP', 'LTC', 'ADA', 'DOGE']):
            return 'crypto'
        elif any(x in symbol_upper for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
            return 'metals'
        elif any(x in symbol_upper for x in ['XTI', 'WTI', 'OIL', 'BRENT']):
            return 'energy'
        elif 'JPY' in symbol_upper:
            return 'jpy_pairs'
        else:
            return 'forex'
    
    def _calculate_minimum_sl_distance(self, symbol: str, entry_price: float, asset_class: str) -> float:
        """
        Calculate MINIMUM SL distance based on asset class
        
        THE 30-PIP HARD FLOOR (Forex):
        - All FX pairs: minimum 30 pips
        
        CRYPTO SCALE FIX:
        - BTC/ETH: minimum 1.5-2% of current price
        
        Returns: minimum distance in price terms
        """
        if asset_class == 'crypto':
            # Crypto: 1.5% minimum for safety (prevents Invalid Volume errors)
            min_pct = 0.015  # 1.5%
            min_distance = entry_price * min_pct
            print(f"[SL MIN] {symbol} (Crypto): 1.5% = {min_distance:.2f}")
            return min_distance
        
        elif asset_class == 'metals':
            # Gold/Silver: 0.8% minimum
            min_pct = 0.008
            min_distance = entry_price * min_pct
            print(f"[SL MIN] {symbol} (Metals): 0.8% = {min_distance:.5f}")
            return min_distance
        
        elif asset_class == 'energy':
            # Oil: 1.0% minimum
            min_pct = 0.010
            min_distance = entry_price * min_pct
            print(f"[SL MIN] {symbol} (Energy): 1.0% = {min_distance:.5f}")
            return min_distance
        
        elif asset_class == 'jpy_pairs':
            # JPY pairs: 30 pips (at 2 decimals: 0.30)
            min_pips = 30
            pip_size = 0.01
            min_distance = min_pips * pip_size
            print(f"[SL MIN] {symbol} (JPY): 30 pips = {min_distance:.2f}")
            return min_distance
        
        else:  # Standard forex
            # THE 30-PIP HARD FLOOR: All forex pairs get 30 pips minimum
            min_pips = 30
            pip_size = 0.0001
            min_distance = min_pips * pip_size  # 0.0030
            print(f"[SL MIN] {symbol} (Forex): 30 pips = {min_distance:.4f}")
            return min_distance
    
    def calculate_entry_sl_tp(
        self, 
        fvg: FVG, 
        h4_choch: CHoCH, 
        df_4h: pd.DataFrame,
        df_daily: pd.DataFrame,
        df_1h: Optional[pd.DataFrame] = None  # pentru fallback dacă e nevoie
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
        # ✅ CRITICAL FIX by ФорексГод: Asset-specific minimum SL distances
        asset_class = self._get_asset_class(fvg.symbol)
        
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
            try:
                atr_4h = (df_4h['high'] - df_4h['low']).rolling(14).mean().iloc[-1]
                if pd.isna(atr_4h) or atr_4h <= 0:
                    # Fallback: 2% of current price
                    atr_4h = entry * 0.02
                    print(f"⚠️  ATR fallback: {atr_4h:.5f} (2% of entry)")
            except Exception as e:
                atr_4h = entry * 0.02
                print(f"❌ ATR error: {e} | Using 2% fallback: {atr_4h:.5f}")
            
            stop_loss = swing_low - (1.5 * atr_4h)
            
            # ✅ THE 30-PIP HARD FLOOR (Forex) / 1.5% CRYPTO SCALE FIX
            min_distance = self._calculate_minimum_sl_distance(fvg.symbol, entry, asset_class)
            current_distance = abs(entry - stop_loss)
            
            if current_distance < min_distance:
                stop_loss = entry - min_distance
                print(f"✅ [SL ENFORCED] {fvg.symbol} LONG: {current_distance:.5f} → {min_distance:.5f}")
                
                # Fallback pe 1H dacă există și distanța e mai bună
                if df_1h is not None:
                    recent_lows_1h = df_1h['low'].iloc[-40:]
                    swing_low_1h = recent_lows_1h.min()
                    distance_1h = abs(entry - swing_low_1h)
                    if distance_1h >= min_distance and distance_1h > current_distance:
                        stop_loss = swing_low_1h
                        print(f"✅ [SL IMPROVED] Using 1H swing: {distance_1h:.5f}")
            
            # Daily ATR for TP distance cap
            daily_atr = (df_daily['high'] - df_daily['low']).rolling(14).mean().iloc[-1]
            
            # TP = Next Daily HIGH structure (body-based, not wick)
            # STRATEGY: Find the next resistance level (previous swing high)
            daily_swing_highs = self.detect_swing_highs(df_daily)
            
            # ✅ FILTER: Get swing highs from last 60 days ONLY (not ancient highs)
            # AND before current position (last 5 bars)
            recent_lookback = min(60, len(df_daily) - 5)  # Last 60 days or less
            previous_highs = [
                sh for sh in daily_swing_highs 
                if sh.index >= len(df_daily) - recent_lookback 
                and sh.index < len(df_daily) - 5
            ]
            
            if previous_highs:
                # Use last significant high as TP (next resistance from recent structure)
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
            try:
                atr_4h = (df_4h['high'] - df_4h['low']).rolling(14).mean().iloc[-1]
                if pd.isna(atr_4h) or atr_4h <= 0:
                    # Fallback: 2% of current price
                    atr_4h = entry * 0.02
                    print(f"⚠️  ATR fallback: {atr_4h:.5f} (2% of entry)")
            except Exception as e:
                atr_4h = entry * 0.02
                print(f"❌ ATR error: {e} | Using 2% fallback: {atr_4h:.5f}")
            
            stop_loss = swing_high + (1.5 * atr_4h)
            
            # ✅ THE 30-PIP HARD FLOOR (Forex) / 1.5% CRYPTO SCALE FIX
            min_distance = self._calculate_minimum_sl_distance(fvg.symbol, entry, asset_class)
            current_distance = abs(entry - stop_loss)
            
            if current_distance < min_distance:
                stop_loss = entry + min_distance
                print(f"✅ [SL ENFORCED] {fvg.symbol} SHORT: {current_distance:.5f} → {min_distance:.5f}")
                
                # Fallback pe 1H dacă există și distanța e mai bună
                if df_1h is not None:
                    recent_highs_1h = df_1h['high'].iloc[-40:]
                    swing_high_1h = recent_highs_1h.max()
                    distance_1h = abs(entry - swing_high_1h)
                    if distance_1h >= min_distance and distance_1h > current_distance:
                        stop_loss = swing_high_1h
                        print(f"✅ [SL IMPROVED] Using 1H swing: {distance_1h:.5f}")
            
            # Daily ATR for TP distance cap
            daily_atr = (df_daily['high'] - df_daily['low']).rolling(14).mean().iloc[-1]
            
            # TP = Next Daily LOW structure (body-based, not wick)
            # STRATEGY: Find the next support level (previous swing low)
            daily_swing_lows = self.detect_swing_lows(df_daily)
            
            # ✅ FILTER: Get swing lows from last 60 days ONLY (not ancient lows)
            # AND before current position (last 5 bars)
            recent_lookback = min(60, len(df_daily) - 5)  # Last 60 days or less
            previous_lows = [
                sl for sl in daily_swing_lows 
                if sl.index >= len(df_daily) - recent_lookback 
                and sl.index < len(df_daily) - 5
            ]
            
            if previous_lows:
                # Use last significant low as TP (next support from recent structure)
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
    
    def calculate_premium_discount(
        self,
        df_daily: pd.DataFrame,
        current_price: float,
        debug: bool = False
    ) -> Dict:
        """
        📊 V4.0 PREMIUM/DISCOUNT FILTER: Calculate price position in daily range
        
        LOGIC:
        - Daily range = High to Low (last candle)
        - Equilibrium = 50% level
        - Premium = 70%-100% (risky for LONG)
        - Discount = 0%-30% (risky for SHORT)
        - Fair = 30%-70% (optimal zone)
        
        Args:
            df_daily: Daily timeframe DataFrame
            current_price: Current market price
            debug: Print debug info
        
        Returns:
            {
                'zone': 'PREMIUM' | 'DISCOUNT' | 'FAIR',
                'percentage': float (0-100),
                'equilibrium': float,
                'daily_high': float,
                'daily_low': float
            }
        """
        # Get last daily candle range
        daily_high = df_daily['high'].iloc[-1]
        daily_low = df_daily['low'].iloc[-1]
        
        range_size = daily_high - daily_low
        equilibrium = daily_low + (range_size * 0.5)
        
        # Calculate percentage from bottom (0% = low, 100% = high)
        if range_size > 0:
            percentage = ((current_price - daily_low) / range_size) * 100
        else:
            percentage = 50  # Range too small, assume fair
        
        # Determine zone
        if percentage >= 70:
            zone = 'PREMIUM'
        elif percentage <= 30:
            zone = 'DISCOUNT'
        else:
            zone = 'FAIR'
        
        if debug:
            print(f"\n📊 PREMIUM/DISCOUNT ANALYSIS:")
            print(f"   Daily High: {daily_high:.5f}")
            print(f"   Daily Low: {daily_low:.5f}")
            print(f"   Equilibrium (50%): {equilibrium:.5f}")
            print(f"   Current Price: {current_price:.5f}")
            print(f"   Position: {percentage:.1f}% ({zone})")
            
            if zone == 'PREMIUM':
                print(f"   ⚠️ PREMIUM ZONE - Risky for LONG (price at top 30%)")
            elif zone == 'DISCOUNT':
                print(f"   ⚠️ DISCOUNT ZONE - Risky for SHORT (price at bottom 30%)")
            else:
                print(f"   ✅ FAIR ZONE - Optimal for both directions")
        
        return {
            'zone': zone,
            'percentage': round(percentage, 1),
            'equilibrium': equilibrium,
            'daily_high': daily_high,
            'daily_low': daily_low
        }
    
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
        
        # V4.0: Initialize variables early to avoid UnboundLocalError
        order_block = None  # Will be populated later with detect_order_block()
        
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
        
        # V5.0 ANTI-COUNTER-TREND FILTER: Check Daily alignment BEFORE continuing
        overall_daily_trend = self.determine_daily_trend(df_daily)
        
        if debug:
            print(f"\n🔍 Daily Trend Analysis:")
            print(f"   Overall Daily Structure: {overall_daily_trend.upper()}")
            print(f"   Latest Signal Direction: {current_trend.upper()}")
            print(f"   Strategy Type: {strategy_type.upper()}")
        
        # STRICT RULE: No counter-trend trades!
        if overall_daily_trend == 'bearish' and current_trend == 'bullish':
            print(f"❌ Signal Blocked: {symbol} Buy Setup rejected due to Bearish Daily Bias")
            print(f"   📊 Overall Daily Trend: BEARISH (LL + LH structure)")
            print(f"   📈 Setup Signal: BULLISH ({strategy_type})")
            print(f"   ⚠️  Counter-trend trade FORBIDDEN - wait for Daily alignment")
            
            # If REVERSAL, check if it has confirmation
            if strategy_type == 'reversal' and isinstance(latest_signal, CHoCH):
                has_confirm = self.has_confirmation_swing(df_daily, latest_signal)
                if has_confirm:
                    print(f"   ℹ️  Note: CHoCH has confirmation swing, but still blocked (wait for multiple BOS)")
                else:
                    print(f"   ℹ️  Note: CHoCH lacks confirmation swing - reversal not yet validated")
            
            return None
        
        if overall_daily_trend == 'bullish' and current_trend == 'bearish':
            print(f"❌ Signal Blocked: {symbol} Sell Setup rejected due to Bullish Daily Bias")
            print(f"   📊 Overall Daily Trend: BULLISH (HH + HL structure)")
            print(f"   📉 Setup Signal: BEARISH ({strategy_type})")
            print(f"   ⚠️  Counter-trend trade FORBIDDEN - wait for Daily alignment")
            
            # If REVERSAL, check if it has confirmation
            if strategy_type == 'reversal' and isinstance(latest_signal, CHoCH):
                has_confirm = self.has_confirmation_swing(df_daily, latest_signal)
                if has_confirm:
                    print(f"   ℹ️  Note: CHoCH has confirmation swing, but still blocked (wait for multiple BOS)")
                else:
                    print(f"   ℹ️  Note: CHoCH lacks confirmation swing - reversal not yet validated")
            
            return None
        
        # If neutral, allow trade but log warning
        if overall_daily_trend == 'neutral':
            if debug:
                print(f"   ⚠️  Warning: Daily trend NEUTRAL - proceed with caution")
        else:
            if debug:
                print(f"   ✅ Daily alignment CONFIRMED - {overall_daily_trend.upper()} trend validated")
        
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
            # - XAUUSD: SKIP quality check - filtered later by ATR + anti-loss-streak
            is_gbp = 'GBP' in symbol
            is_gold = symbol == 'XAUUSD'
            
            if is_gold:
                # XAUUSD: Use V2.0 simple validation (86% WR logic)
                # V2.0 had strict FVG requirements → fewer but better setups
                # Gap ≥ 0.10% + Body ≥ 25% (no complex scoring)
                
                gap_size = fvg.top - fvg.bottom
                gap_pct = (gap_size / fvg.bottom) * 100
                
                if gap_pct < 0.15:  # V2.0 threshold (stricter than 0.10%)
                    if debug:
                        print(f"\n❌ REJECTED XAUUSD FVG: Gap {gap_pct:.3f}% < 0.15%")
                    return None
                
                # Check body strength (V2.0 logic)
                gap_candle = df_daily.iloc[fvg.index]
                candle_body = abs(gap_candle['close'] - gap_candle['open'])
                candle_range = gap_candle['high'] - gap_candle['low']
                body_ratio = candle_body / candle_range if candle_range > 0 else 0
                
                if body_ratio < 0.40:  # V2.0 threshold (strict momentum)
                    if debug:
                        print(f"\n❌ REJECTED XAUUSD FVG: Body {body_ratio:.1%} < 40%")
                    return None
                
                if debug:
                    print(f"\n✅ XAUUSD FVG V2.0 PASSED: Gap {gap_pct:.3f}%, Body {body_ratio:.1%}")
                    
            elif is_gbp:
                min_score = 70
                if fvg_score < min_score:
                    if debug:
                        print(f"\n❌ REJECTED: FVG score {fvg_score}/100 < {min_score} (minimum)")
                        print(f"   GBP pair requires stricter quality (≥70)")
                    return None
            else:
                min_score = 60
                if fvg_score < min_score:
                    if debug:
                        print(f"\n❌ REJECTED: FVG score {fvg_score}/100 < {min_score} (minimum)")
                    return None  # Low quality FVG
            
            # XAUUSD ADDITIONAL FILTERS: FVG quality + ATR volatility (NO ADX - Gold moves differently)
            if is_gold and not skip_fvg_quality:
                # Skip ADX check for Gold - momentum works differently than forex
                # Gold can have strong directional moves even with lower ADX
                
                # Calculate ATR ratio (current ATR / 20-period average)
                current_atr = calculate_atr(df_daily, period=14)
                avg_atr_20 = current_atr  # Fallback
                
                # Calculate 20-period average ATR more safely
                if len(df_daily) >= 35:
                    atr_values = []
                    for i in range(len(df_daily) - 20, len(df_daily)):
                        if i >= 15:
                            atr_val = calculate_atr(df_daily.iloc[max(0, i-14):i+1], period=14)
                            if atr_val > 0:
                                atr_values.append(atr_val)
                    if atr_values:
                        avg_atr_20 = np.mean(atr_values)
                
                atr_ratio = current_atr / avg_atr_20 if avg_atr_20 > 0 else 1.0
                
                if atr_ratio > 3.0:
                    if debug:
                        print(f"\n❌ REJECTED XAUUSD: ATR ratio {atr_ratio:.2f} > 3.0 (extreme volatility, unstable setup)")
                    return None
                
                if debug:
                    print(f"\n✅ XAUUSD FILTERS PASSED:")
                    print(f"   FVG Quality: {fvg_score}/100 (≥65) ✓")
                    print(f"   ATR Ratio: {atr_ratio:.2f} (≤3.0) ✓")
                    print(f"   (ADX check skipped - Gold momentum patterns differ from forex)")
        else:
            # Skip quality check for backtest - accept all FVGs
            fvg.quality_score = 100  # Default high score when skipped
            is_gbp = 'GBP' in symbol
        
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
                
                # V4.0 FIX-004: REMOVED momentum confirmation check after CHoCH
                # Reason: CHoCH with body closure is SUFFICIENT confirmation of structure break
                # The old momentum check created false rejections (like USDJPY Feb 09)
                # SMC principle: Body closure breaks level = structure changed, no additional filter needed
                
                # ✅ All checks passed - VALID, RECENT CHoCH (body closure confirmed in detect_choch_and_bos)
                valid_h4_choch = h4_choch
                if debug:
                    print(f"   ✅ Valid H4 CHoCH found @ {h4_choch.break_price:.5f} ({choch_age} candles ago)")
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
        
        # V3.3 CONTINUITY FILTER RELAXED
        # CONTINUITY setups (Daily BOS) accept:
        # 1. Single recent BOS (< 30 candles) with strong FVG (quality ≥ 70)
        # 2. Multiple BOS (any age) = strong continuation
        # REVERSAL setups (Daily CHoCH) skip this - trend just changed
        continuity_validated = True
        if not skip_fvg_quality and strategy_type == 'continuation':
            # Check last 90 candles for additional BOS before latest
            recent_bos = [bos for bos in daily_bos_list if bos.index >= len(df_daily) - 90 and bos.index < latest_signal.index]
            matching_bos = [bos for bos in recent_bos if bos.direction == current_trend]
            
            if not matching_bos:
                # Single BOS - validate based on recency and FVG quality
                bos_age = len(df_daily) - latest_signal.index
                
                if bos_age <= 30 and fvg.quality_score >= 70:
                    # ✅ Accept: Recent BOS (≤30 candles) + Strong FVG (≥70)
                    continuity_validated = True
                    if debug:
                        print(f"\n✅ CONTINUITY FILTER: Single BOS accepted (recent + strong FVG)")
                        print(f"   BOS age: {bos_age} candles (≤30)")
                        print(f"   FVG quality: {fvg.quality_score}/100 (≥70)")
                else:
                    # ❌ Reject: Old BOS or weak FVG
                    continuity_validated = False
                    if debug:
                        print(f"\n⚠️  CONTINUITY FILTER: Single BOS rejected (old or weak FVG)")
                        print(f"   BOS age: {bos_age} candles (need ≤30)")
                        print(f"   FVG quality: {fvg.quality_score}/100 (need ≥70)")
            else:
                # ✅ Multiple BOS found = strong continuation
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
        
        # 📦 V4.0 ORDER BLOCK OVERRIDE: If OB score >= 7, use OB for precise entry/SL
        if order_block and order_block.ob_score >= 7:
            # Use Order Block zones for entry/SL instead of FVG
            if debug:
                print(f"\n📦 ORDER BLOCK ACTIVATED for Entry/SL calculation:")
                print(f"   OB Zone: {order_block.bottom:.5f} - {order_block.top:.5f}")
                print(f"   OB Score: {order_block.ob_score}/10")
            
            # Entry = OB middle (more precise than FVG 35%)
            entry = order_block.middle
            
            # Tighter SL using OB boundaries (not 4H swing)
            if current_trend == 'bullish':
                # LONG: SL just below OB bottom
                sl = order_block.bottom * 0.9995  # 5 pips below OB bottom
            else:
                # SHORT: SL just above OB top
                sl = order_block.top * 1.0005  # 5 pips above OB top
            
            # TP calculation still uses Daily structure (unchanged)
            # Calculate via calculate_entry_sl_tp but override entry/SL
            _, _, tp = self.calculate_entry_sl_tp(fvg, h4_signal, df_4h, df_daily) if h4_signal else (entry, sl, entry * 1.02 if current_trend == 'bullish' else entry * 0.98)
            
            if debug:
                print(f"   ✅ Entry: {entry:.5f} (OB middle)")
                print(f"   ✅ SL: {sl:.5f} (OB boundary + 5 pips)")
                print(f"   ✅ TP: {tp:.5f} (Daily structure)")
        
        elif h4_signal:
            # Fallback: Use FVG-based entry/SL from calculate_entry_sl_tp
            entry, sl, tp = self.calculate_entry_sl_tp(fvg, h4_signal, df_4h, df_daily)
            if debug:
                print(f"\n💰 FVG-based Trade Levels (no high-quality OB):")
        
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
        
        # 🟡 XAUUSD SPECIAL FILTER: Only CONTINUATION bearish (V2.0 Logic - 86% WR)
        if symbol == 'XAUUSD' and not skip_fvg_quality:
            if strategy_type != 'continuation' or current_trend != 'bearish':
                if debug:
                    print(f"\n❌ REJECTED XAUUSD: Only CONTINUATION bearish")
                return None
        
        # 🌍 UNIVERSAL ANTI-OVERTRADING FILTER: Max 4 trades per FVG zone (ALL PAIRS)
        # This prevents NZDUSD-style hemorrhaging (-$1,054 on 26 trades with small SLs)
        # Preserves winning clusters (Mai 4-7) while blocking endless overtrading
        if not skip_fvg_quality:
            # Initialize symbol tracker if needed
            if symbol not in self.fvg_zones_tracker:
                self.fvg_zones_tracker[symbol] = []
            
            current_fvg_top = fvg.top
            current_fvg_bottom = fvg.bottom
            current_date = df_daily.index[-1]
            
            # Find matching FVG zone (>50% overlap)
            matched_zone_idx = None
            for idx, (prev_top, prev_bottom, prev_date, trade_count) in enumerate(self.fvg_zones_tracker[symbol]):
                # Calculate overlap percentage
                overlap_top = min(current_fvg_top, prev_top)
                overlap_bottom = max(current_fvg_bottom, prev_bottom)
                
                if overlap_bottom < overlap_top:
                    overlap_size = overlap_top - overlap_bottom
                    current_size = current_fvg_top - current_fvg_bottom
                    prev_size = prev_top - prev_bottom
                    
                    overlap_pct = overlap_size / min(current_size, prev_size) if min(current_size, prev_size) > 0 else 0
                    
                    if overlap_pct > 0.50:  # 50% overlap = same zone
                        matched_zone_idx = idx
                        break
            
            if matched_zone_idx is not None:
                # Existing FVG zone - check trade count
                prev_top, prev_bottom, prev_date, trade_count = self.fvg_zones_tracker[symbol][matched_zone_idx]
                
                if trade_count >= 4:
                    # Too many trades in this zone already
                    if debug:
                        print(f"\n❌ REJECTED {symbol}: FVG zone exhausted ({trade_count} trades already)")
                        print(f"   Zone: {prev_bottom:.5f}-{prev_top:.5f}")
                        print(f"   🛡️ UNIVERSAL anti-overtrading protection active!")
                    return None
                
                # Increment trade count for this zone
                self.fvg_zones_tracker[symbol][matched_zone_idx] = (prev_top, prev_bottom, prev_date, trade_count + 1)
                
                if debug:
                    print(f"\n✅ {symbol} ACCEPTED: FVG zone trade #{trade_count + 1}/4")
            else:
                # New FVG zone - add with trade_count = 1
                self.fvg_zones_tracker[symbol].append((current_fvg_top, current_fvg_bottom, current_date, 1))
                
                if debug:
                    print(f"\n✅ {symbol} ACCEPTED: New FVG zone {current_fvg_bottom:.5f}-{current_fvg_top:.5f}")
                    print(f"   Total tracked zones for {symbol}: {len(self.fvg_zones_tracker[symbol])}")
        
        # 💧 V4.0 LIQUIDITY SWEEP DETECTION (Faza 1)
        liquidity_sweep = self.detect_liquidity_sweep(
            df=df_daily,
            choch=latest_signal,
            lookback=20,
            tolerance_pips=5,
            debug=debug
        )
        
        # Confidence boost if liquidity swept
        confidence_boost = 0
        if liquidity_sweep and liquidity_sweep['sweep_detected']:
            confidence_boost = 20  # +20 points for liquidity validation
            if debug:
                print(f"   ✅ LIQUIDITY SWEEP CONFIRMED: +{confidence_boost} confidence")
        
        # 📊 V4.0 PREMIUM/DISCOUNT FILTER (Faza 1)
        # Don't buy in premium, don't sell in discount
        if not skip_fvg_quality:
            premium_discount = self.calculate_premium_discount(
                df_daily=df_daily,
                current_price=current_price,
                debug=debug
            )
            
            # FILTER: Reject trades in wrong zones
            if current_trend == 'bullish' and premium_discount['zone'] == 'PREMIUM':
                if debug:
                    print(f"\n❌ REJECTED: Buying in PREMIUM zone ({premium_discount['percentage']:.1f}%)")
                    print(f"   Too high risk - price at top 30% of daily range")
                return None
            
            if current_trend == 'bearish' and premium_discount['zone'] == 'DISCOUNT':
                if debug:
                    print(f"\n❌ REJECTED: Selling in DISCOUNT zone ({premium_discount['percentage']:.1f}%)")
                    print(f"   Too high risk - price at bottom 30% of daily range")
                return None
            
            if debug:
                print(f"\n✅ PREMIUM/DISCOUNT CHECK PASSED: {premium_discount['zone']} zone")
        
        # 🎯 V3.5 ORDER BLOCKS: Detect OB pentru entry precision + corelație cu FVG
        order_block = self.detect_order_block(
            df=df_daily,
            choch=latest_signal,
            fvg=fvg,
            debug=debug
        )
        
        # 📦 V4.0 ACTIVATE ORDER BLOCKS: Use OB for entry/SL if valid (Faza 1)
        # Previously OB was detected but NOT used - now we enforce it!
        if order_block and order_block.ob_score >= 7:
            # Use Order Block for precise entry instead of FVG middle
            if debug:
                print(f"\n📦 ORDER BLOCK ACTIVATED for Entry/SL:")
                print(f"   OB Zone: {order_block.bottom:.5f} - {order_block.top:.5f}")
                print(f"   OB Score: {order_block.ob_score}/10")
                print(f"   Using OB middle for entry (more precise than FVG)")
            
            # Override entry calculation to use OB
            entry = order_block.middle
            
            # Tighter SL using OB boundaries
            if current_trend == 'bullish':
                sl = order_block.bottom * 0.9995  # 5 pips below OB bottom
            else:
                sl = order_block.top * 1.0005  # 5 pips above OB top
        else:
            # Fallback to FVG-based entry if no high-quality OB
            entry = None  # Will be calculated later in calculate_entry_sl_tp
            sl = None
            
            if debug and order_block:
                print(f"\n⚠️ ORDER BLOCK NOT ACTIVATED: Score {order_block.ob_score}/10 < 7")
                print(f"   Falling back to FVG-based entry")
        
        # Calculate ESTIMATED RR pentru swing trading (minimum 1:5)
        estimated_rr = risk_reward  # Default to standard RR
        if order_block and order_block.has_unfilled_fvg:
            # OB + unfilled FVG = HIGH PROBABILITY swing (boost RR estimate)
            estimated_rr = risk_reward * 1.5  # 1.5x multiplier pentru OB setups
        
        if debug and order_block:
            print(f"\n🎯 SWING SETUP ENHANCED:")
            print(f"   OB Score: {order_block.ob_score}/10")
            print(f"   Estimated RR: 1:{estimated_rr:.1f} (minimum)")
            print(f"   Entry Zone (OB): {order_block.bottom:.5f} - {order_block.top:.5f}")
        
        # 🎯 V3.4 ORDER BLOCKS: Store FVG as price magnet for future reference
        # This prepares infrastructure for Order Block detection in V3.5
        self.store_fvg_magnet(symbol, '4H', fvg)  # Store from 4H timeframe
        if df_1h is not None and valid_1h_choch:
            # If we have 1H data, detect and store 1H FVG magnets
            h1_fvg = self.detect_fvg(df_1h, valid_1h_choch, current_price)
            if h1_fvg:
                self.store_fvg_magnet(symbol, '1H', h1_fvg)
        
        # Return setup (MONITORING or READY)
        # Convert pandas Timestamp to Python datetime properly
        # Get the actual timestamp value (not the index position!)
        try:
            setup_timestamp = df_4h.index[-1]
            # If it's a pandas Timestamp, convert to Python datetime
            if hasattr(setup_timestamp, 'to_pydatetime'):
                setup_timestamp = setup_timestamp.to_pydatetime()
            # If it's somehow an int (position), use current time
            elif isinstance(setup_timestamp, (int, np.integer)):
                setup_timestamp = datetime.now()
        except Exception as e:
            print(f"⚠️ Warning: Could not convert setup_time properly: {e}")
            setup_timestamp = datetime.now()
        
        # Store liquidity sweep and premium/discount in setup for reporting
        setup = TradeSetup(
            symbol=symbol,
            daily_choch=latest_signal,  # Daily CHoCH (REVERSAL) or BOS (CONTINUITY)
            fvg=fvg,
            h4_choch=h4_signal,  # H4 CHoCH (same for both REVERSAL and CONTINUITY)
            h1_choch=valid_1h_choch,  # V3.0: 1H CHoCH for GBP pairs (None if not detected)
            order_block=order_block,  # 📦 V3.5: Order Block pentru entry precision
            entry_price=entry,  # V4.0: Uses OB if available, else FVG
            stop_loss=sl,  # V4.0: Tighter SL from OB if available
            take_profit=tp,
            risk_reward=risk_reward,
            estimated_rr=estimated_rr + (confidence_boost / 20) if confidence_boost > 0 else estimated_rr,  # Boost RR if liquidity swept
            setup_time=setup_timestamp,  # Properly converted Python datetime
            priority=priority,
            strategy_type=strategy_type,
            status=status
        )
        
        # 💧 V4.0: Store liquidity sweep info (for Telegram reporting)
        if liquidity_sweep:
            setup.liquidity_sweep = liquidity_sweep
            setup.confidence_boost = confidence_boost
        
        return setup


def format_setup_message(setup: TradeSetup) -> str:
    """Format trade setup for Telegram message - V3.5 with Order Blocks"""
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
    
    # 📦 V3.5 ORDER BLOCK INFO
    ob_info = ""
    rr_info = f"📈 Risk:Reward: 1:{setup.risk_reward:.2f}"
    
    if setup.order_block:
        ob = setup.order_block
        ob_score_stars = "⭐" * min(5, ob.ob_score // 2)  # 10/10 = 5 stars
        ob_quality = "🔥 PERFECT!" if ob.has_unfilled_fvg else "✅ VALID"
        
        ob_info = f"""
📦 Entry Zone (OB): {ob.bottom:.5f} - {ob.top:.5f}
   {ob_quality} Order Block {ob_score_stars}
   Impulse: {ob.impulse_strength:.2f}%"""
        
        # Update RR info with estimated swing RR
        if setup.estimated_rr > setup.risk_reward:
            rr_info = f"""📈 Risk:Reward: 1:{setup.risk_reward:.2f}
🎯 RR Estimat (Swing): Minim 1:{setup.estimated_rr:.1f}"""
    
    message = f"""
🚨 SETUP - {setup.symbol}
{direction} | {status_icon} | {strategy_emoji}

📊 Daily CHoCH: {setup.daily_choch.direction.upper()}
📍 FVG Zone: {setup.fvg.bottom:.5f} - {setup.fvg.top:.5f}
{h4_info}
{ob_info}

💰 Entry: {setup.entry_price:.5f}
🛑 Stop Loss: {setup.stop_loss:.5f}
🎯 Take Profit: {setup.take_profit:.5f}

{rr_info}
⭐ Priority: {setup.priority}

⏰ Setup Time: {setup.setup_time.strftime('%Y-%m-%d %H:%M')}
"""
    
    return message.strip()


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """
    Calculate Average True Range (ATR)
    
    Args:
        df: DataFrame with high, low, close columns
        period: ATR period (default 14)
    
    Returns:
        Current ATR value
    """
    if len(df) < period + 1:
        return 0.0
    
    # True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    tr = []
    for i in range(1, len(df)):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i-1])
        lc = abs(low[i] - close[i-1])
        tr.append(max(hl, hc, lc))
    
    # Simple Moving Average of TR
    tr_series = pd.Series(tr)
    atr = tr_series.rolling(window=period).mean().iloc[-1]
    
    return atr if not np.isnan(atr) else 0.0


def calculate_adx(df: pd.DataFrame, period: int = 14) -> float:
    """
    Calculate Average Directional Index (ADX) - measures trend strength
    
    Args:
        df: DataFrame with high, low, close columns
        period: ADX period (default 14)
    
    Returns:
        Current ADX value (0-100, >25 = strong trend)
    """
    if len(df) < period + 1:
        return 0.0
    
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    # Calculate +DM and -DM
    plus_dm = []
    minus_dm = []
    
    for i in range(1, len(df)):
        high_diff = high[i] - high[i-1]
        low_diff = low[i-1] - low[i]
        
        plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0)
        minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0)
    
    # Calculate True Range
    tr = []
    for i in range(1, len(df)):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i-1])
        lc = abs(low[i] - close[i-1])
        tr.append(max(hl, hc, lc))
    
    # Smooth using EMA
    plus_dm_series = pd.Series(plus_dm).ewm(span=period, adjust=False).mean()
    minus_dm_series = pd.Series(minus_dm).ewm(span=period, adjust=False).mean()
    tr_series = pd.Series(tr).ewm(span=period, adjust=False).mean()
    
    # Calculate +DI and -DI
    plus_di = 100 * (plus_dm_series / tr_series)
    minus_di = 100 * (minus_dm_series / tr_series)
    
    # Calculate DX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    
    # Calculate ADX (smoothed DX)
    adx = dx.ewm(span=period, adjust=False).mean().iloc[-1]
    
    return adx if not np.isnan(adx) else 0.0


def validate_1h_choch(df_1h, daily_trend, fvg, debug=False):
    """
    Validate 1H CHoCH for Entry 1 in SCALE_IN strategy.
    
    Args:
        df_1h: DataFrame with 1H OHLC data (min 225 candles)
        daily_trend: Current Daily trend direction ('bullish' or 'bearish')
        fvg: FVG object with .bottom and .top
        debug: Print debug messages
    
    Requirements:
        - 1H CHoCH direction matches Daily trend
        - CHoCH break_price WITHIN FVG zone
        - Momentum confirmation (1 candle after CHoCH)
    
    Returns:
        CHoCH object if valid, None otherwise
    """
    if df_1h is None or len(df_1h) < 50:
        return None
    
    if debug:
        print(f"\n🔍 1H CHoCH Validation for Entry 1:")
    
    # Detect 1H CHoCH using SMCDetector
    from smc_detector import SMCDetector
    detector = SMCDetector()
    h1_chochs, _ = detector.detect_choch_and_bos(df_1h)
    
    if debug:
        print(f"   Total 1H CHoCH detected: {len(h1_chochs)}")
    
    # Look in last 50 candles for context
    recent_h1_chochs = [ch for ch in h1_chochs if ch.index >= len(df_1h) - 50]
    
    for h1_choch in reversed(recent_h1_chochs):
        # Direction must match Daily trend
        if h1_choch.direction != daily_trend:
            continue
        
        # CHoCH break_price must be WITHIN FVG zone
        if not (fvg.bottom <= h1_choch.break_price <= fvg.top):
            continue
        
        # Momentum confirmation
        if h1_choch.index + 1 < len(df_1h):
            candles_after = df_1h.iloc[h1_choch.index + 1:]
            if len(candles_after) >= 1:
                last_candle = candles_after.iloc[-1]
                
                if daily_trend == 'bullish':
                    momentum_ok = (last_candle['close'] > last_candle['open']) or \
                                (last_candle['close'] > df_1h.iloc[h1_choch.index]['close'])
                else:
                    momentum_ok = (last_candle['close'] < last_candle['open']) or \
                                (last_candle['close'] < df_1h.iloc[h1_choch.index]['close'])
                
                if not momentum_ok:
                    if debug:
                        print(f"   ⏭️  1H CHoCH @ {h1_choch.break_price:.5f} lacks momentum")
                    continue
        
        # Calculate CHoCH age for logging
        choch_age = len(df_1h) - 1 - h1_choch.index
        
        # ✅ Valid 1H CHoCH found
        if debug:
            print(f"   ✅ Valid 1H CHoCH @ {h1_choch.break_price:.5f} ({choch_age} candles ago = {choch_age}h)")
        return h1_choch
    
    if debug:
        print(f"   ❌ No valid 1H CHoCH found")
    return None


def validate_choch_confirmation_scale_in(setup, current_time, df_daily, df_4h, df_1h, config, debug=False):
    """
    SCALE_IN strategy validation with dual entry logic.
    
    Priority cascade:
    1. Check setup expiry (72h total)
    2. If Entry 1 not filled → Try 1H CHoCH validation
    3. If Entry 1 filled → Try 4H CHoCH validation (with 48h timeout)
    4. If Entry 1 filled + timeout expired → Evaluate Entry 1 P&L
    
    Args:
        setup: Setup object with entry1_filled, entry1_time, entry1_price, etc.
        current_time: datetime object
        df_daily, df_4h, df_1h: OHLC DataFrames
        config: pairs_config.json execution_strategy section
        debug: Print debug messages
    
    Returns:
        dict with:
            - action: 'EXECUTE_ENTRY1', 'EXECUTE_ENTRY2', 'CLOSE_ENTRY1', 'KEEP_MONITORING', 'EXPIRE'
            - reason: str explanation
            - entry_price: float (if action = EXECUTE_*)
            - stop_loss: float
            - take_profit: float
            - position_size: float (0.5 for scale in)
    """
    if debug:
        print(f"\n🔍 SCALE_IN Validation for {setup.symbol}:")
    
    # Setup age check (72h expiry)
    setup_age_hours = (current_time - setup.setup_time).total_seconds() / 3600
    if setup_age_hours > config['setup_expiry_hours']:
        return {
            'action': 'EXPIRE',
            'reason': f'Setup expired ({setup_age_hours:.1f}h > {config["setup_expiry_hours"]}h)',
        }
    
    # Entry 1 status check
    entry1_filled = getattr(setup, 'entry1_filled', False)
    
    if not entry1_filled:
        # ========== ENTRY 1 LOGIC (1H CHoCH) ==========
        if debug:
            print(f"   Entry 1 not filled, checking 1H CHoCH...")
        
        # Validate 1H CHoCH
        valid_1h_choch = validate_1h_choch(
            df_1h, 
            setup.daily_choch.direction, 
            setup.fvg, 
            debug=debug
        )
        
        if valid_1h_choch:
            # ✅ Execute Entry 1 (50% position size)
            return {
                'action': 'EXECUTE_ENTRY1',
                'reason': f'1H CHoCH confirmed @ {valid_1h_choch.break_price:.5f}',
                'entry_price': setup.entry_price,
                'stop_loss': setup.stop_loss,
                'take_profit': setup.take_profit,
                'position_size': config['entry1_position_size'],  # 0.5
                'choch': valid_1h_choch
            }
        else:
            # Keep monitoring for 1H CHoCH
            return {
                'action': 'KEEP_MONITORING',
                'reason': 'Waiting for 1H CHoCH confirmation',
            }
    
    else:
        # ========== ENTRY 2 LOGIC (4H CHoCH) ==========
        entry1_time = getattr(setup, 'entry1_time', None)
        entry1_price = getattr(setup, 'entry1_price', None)
        
        if not entry1_time or not entry1_price:
            return {
                'action': 'KEEP_MONITORING',
                'reason': 'Entry 1 data incomplete',
            }
        
        # Check Entry 2 timeout (48h after Entry 1)
        entry1_age_hours = (current_time - entry1_time).total_seconds() / 3600
        timeout_hours = config['entry2_timeout_hours']
        
        if debug:
            print(f"   Entry 1 filled @ {entry1_price:.5f}, age: {entry1_age_hours:.1f}h")
        
        if entry1_age_hours <= timeout_hours:
            # Within timeout - try 4H CHoCH validation
            if debug:
                print(f"   Within timeout ({entry1_age_hours:.1f}h <= {timeout_hours}h), checking 4H CHoCH...")
            
            # Validate 4H CHoCH (similar to existing validate_choch_confirmation)
            from smc_detector import SMCDetector
            detector = SMCDetector()
            h4_chochs, _ = detector.detect_choch_and_bos(df_4h)
            
            recent_h4_chochs = [ch for ch in h4_chochs if ch.index >= len(df_4h) - 50]
            
            for h4_choch in reversed(recent_h4_chochs):
                # Direction match
                if h4_choch.direction != setup.daily_choch.direction:
                    continue
                
                # Within FVG zone
                if not (setup.fvg.bottom <= h4_choch.break_price <= setup.fvg.top):
                    continue
                
                # Age check (max 12 candles = 48h)
                choch_age = len(df_4h) - 1 - h4_choch.index
                if choch_age > 12:
                    continue
                
                # Momentum confirmation
                if h4_choch.index + 1 < len(df_4h):
                    candles_after = df_4h.iloc[h4_choch.index + 1:]
                    if len(candles_after) >= 1:
                        last_candle = candles_after.iloc[-1]
                        
                        if setup.daily_choch.direction == 'bullish':
                            momentum_ok = (last_candle['close'] > last_candle['open']) or \
                                        (last_candle['close'] > df_4h.iloc[h4_choch.index]['close'])
                        else:
                            momentum_ok = (last_candle['close'] < last_candle['open']) or \
                                        (last_candle['close'] < df_4h.iloc[h4_choch.index]['close'])
                        
                        if not momentum_ok:
                            continue
                
                # ✅ Valid 4H CHoCH found - Execute Entry 2
                if debug:
                    print(f"   ✅ Valid 4H CHoCH @ {h4_choch.break_price:.5f} ({choch_age} candles ago)")
                
                return {
                    'action': 'EXECUTE_ENTRY2',
                    'reason': f'4H CHoCH confirmed @ {h4_choch.break_price:.5f}',
                    'entry_price': setup.entry_price,
                    'stop_loss': setup.stop_loss,
                    'take_profit': setup.take_profit,
                    'position_size': config['entry2_position_size'],  # 0.5
                    'choch': h4_choch,
                    'move_entry1_sl_to_breakeven': True  # Important!
                }
            
            # No 4H CHoCH yet, keep monitoring
            if debug:
                print(f"   ❌ No valid 4H CHoCH yet, keep monitoring...")
            
            return {
                'action': 'KEEP_MONITORING',
                'reason': f'Waiting for 4H CHoCH (timeout in {timeout_hours - entry1_age_hours:.1f}h)',
            }
        
        else:
            # ========== TIMEOUT EXPIRED - EVALUATE ENTRY 1 P&L ==========
            if debug:
                print(f"   ⏰ Timeout expired ({entry1_age_hours:.1f}h > {timeout_hours}h)")
            
            # Get current price
            current_price = df_1h.iloc[-1]['close']
            
            # Calculate Entry 1 P&L
            if setup.daily_choch.direction == 'bullish':
                entry1_pnl_pips = (current_price - entry1_price) * 10000
            else:
                entry1_pnl_pips = (entry1_price - current_price) * 10000
            
            profit_threshold = config['entry1_profit_threshold_pips']
            
            if debug:
                print(f"   Entry 1 P&L: {entry1_pnl_pips:.1f} pips (threshold: {profit_threshold} pips)")
            
            if entry1_pnl_pips >= profit_threshold:
                # ✅ Entry 1 profitable - KEEP IT
                if debug:
                    print(f"   ✅ Entry 1 profitable ({entry1_pnl_pips:.1f} pips >= {profit_threshold}), KEEP")
                
                return {
                    'action': 'KEEP_MONITORING',
                    'reason': f'Entry 1 profitable (+{entry1_pnl_pips:.1f} pips), keeping position',
                    'note': 'No Entry 2, but Entry 1 is winning'
                }
            
            else:
                # ⚠️ Entry 1 not profitable - CLOSE @ breakeven/small loss
                if debug:
                    print(f"   ⚠️ Entry 1 not profitable ({entry1_pnl_pips:.1f} pips < {profit_threshold}), CLOSE")
                
                return {
                    'action': 'CLOSE_ENTRY1',
                    'reason': f'Timeout expired, Entry 1 negative ({entry1_pnl_pips:.1f} pips)',
                    'close_price': current_price,
                    'pnl_pips': entry1_pnl_pips
                }


# ============================================================
# V3.2 PULLBACK STRATEGY FUNCTIONS
# ============================================================

def calculate_choch_fibonacci(
    df_h1: pd.DataFrame, 
    choch_idx: int, 
    direction: str,
    df_4h: Optional[pd.DataFrame] = None,
    df_daily: Optional[pd.DataFrame] = None,
    strategy_type: str = 'continuation',
    fibo_timeframe: Optional[str] = None,
    symbol: str = ''
) -> dict:
    """
    V4.0 MULTI-TIMEFRAME FIBONACCI: Calculate Fibonacci 50% from appropriate swing
    
    SMC PURE LOGIC:
    - REVERSAL: Uses Daily/4H CHoCH swing (macro-structure for major reversals)
    - CONTINUATION: Uses 1H 5-candle swing (micro-structure for pullback entries)
    
    Args:
        df_h1: 1H timeframe dataframe
        choch_idx: Index where CHoCH occurred (on 1H)
        direction: 'bullish' or 'bearish'
        df_4h: 4H timeframe dataframe (for REVERSAL strategies)
        df_daily: Daily timeframe dataframe (for major REVERSAL strategies)
        strategy_type: 'reversal' or 'continuation'
        fibo_timeframe: Override TF ('Daily', '4H', '1H') - if None, auto-select
        symbol: Symbol name (for JPY detection)
    
    Returns:
        {
            'fibo_50': float,
            'swing_high': float,
            'swing_low': float,
            'swing_range': float (in pips),
            'swing_start_idx': int,
            'swing_end_idx': int,
            'direction': str,
            'fibo_timeframe': str  # Which TF was used
        }
    """
    # Determine which timeframe to use for Fibonacci calculation
    if fibo_timeframe:
        use_tf = fibo_timeframe
    elif strategy_type == 'reversal':
        # REVERSAL: Use 4H (or Daily for major moves)
        use_tf = '4H' if df_4h is not None else '1H'
    else:
        # CONTINUATION: Use 1H micro-swing
        use_tf = '1H'
    
    # Calculate swing based on selected timeframe
    if use_tf == 'Daily' and df_daily is not None:
        # Find Daily CHoCH and calculate from that swing
        try:
            from smc_detector import SMCDetector
            detector = SMCDetector(swing_lookback=5)
            chochs_daily, _ = detector.detect_choch_and_bos(df_daily)
            
            if chochs_daily:
                latest_choch_daily = chochs_daily[-1]
                lookback = 10  # 10 days before CHoCH
                start_idx = max(0, latest_choch_daily.index - lookback)
                end_idx = latest_choch_daily.index
                swing_data = df_daily.iloc[start_idx:end_idx]
            else:
                # Fallback to 4H
                use_tf = '4H'
        except:
            # Fallback to 4H if Daily detection fails
            use_tf = '4H'
    
    if use_tf == '4H' and df_4h is not None:
        # Find 4H CHoCH and calculate from that swing
        try:
            from smc_detector import SMCDetector
            detector = SMCDetector(swing_lookback=5)
            chochs_4h, _ = detector.detect_choch_and_bos(df_4h)
            
            if chochs_4h:
                # Find most recent 4H CHoCH matching direction
                matching_choch = None
                for ch in reversed(chochs_4h):
                    if ch.direction == direction:
                        matching_choch = ch
                        break
                
                if matching_choch:
                    lookback = 15  # 15 × 4H = 60H = 2.5 days
                    start_idx = max(0, matching_choch.index - lookback)
                    end_idx = matching_choch.index
                    swing_data = df_4h.iloc[start_idx:end_idx]
                else:
                    # Fallback to 1H
                    use_tf = '1H'
            else:
                # Fallback to 1H
                use_tf = '1H'
        except:
            # Fallback to 1H if 4H detection fails
            use_tf = '1H'
    
    if use_tf == '1H':
        # CONTINUATION or FALLBACK: 5-candle 1H micro-swing
        lookback = 5
        start_idx = max(0, choch_idx - lookback)
        end_idx = choch_idx
        swing_data = df_h1.iloc[start_idx:end_idx]
    
    # Calculate swing high/low from determined timeframe
    swing_high = swing_data['high'].max()
    swing_low = swing_data['low'].min()
    swing_range = swing_high - swing_low
    
    # Calculate Fibonacci 50%
    if direction == 'bullish':
        fibo_50 = swing_low + (swing_range * 0.5)
    else:
        fibo_50 = swing_high - (swing_range * 0.5)
    
    # V4.0 FIX: Detect JPY pairs for correct pip calculation
    if 'JPY' in symbol.upper():
        swing_range_pips = swing_range * 100  # JPY = 2 decimals
    else:
        swing_range_pips = swing_range * 10000  # Standard = 4 decimals
    
    return {
        'fibo_50': round(fibo_50, 5),
        'swing_high': round(swing_high, 5),
        'swing_low': round(swing_low, 5),
        'swing_range': round(swing_range_pips, 1),
        'swing_start_idx': start_idx,
        'swing_end_idx': end_idx,
        'direction': direction,
        'fibo_timeframe': use_tf  # V4.0: Store which TF was used
    }


def validate_pullback_entry(
    df_h1: pd.DataFrame, 
    fibo_data: dict, 
    direction: str, 
    tolerance_pips: int = 10,
    sl_buffer_pips: int = 10,
    swing_lookback: int = 5,
    check_momentum: bool = True,  # V3.3: Enable continuation momentum check
    hours_elapsed: int = 0  # V3.3: Hours since setup found
) -> dict:
    """
    V3.3 HYBRID ENTRY: Check pullback OR continuation momentum
    
    Priority 1: Pullback to Fibo 50% (classic entry)
    Priority 2: If no pullback after 6h + strong momentum → ENTER anyway!
    
    Args:
        df_h1: 1H timeframe dataframe
        fibo_data: Dictionary from calculate_choch_fibonacci()
        direction: 'bullish' or 'bearish'
        tolerance_pips: Acceptable distance from Fibo 50% (default 10)
        sl_buffer_pips: Extra pips added to SL beyond swing point (default 10)
        swing_lookback: Number of candles to find swing low/high for SL (default 5)
        check_momentum: Enable continuation momentum detection (default True)
        hours_elapsed: Hours since setup found (for momentum threshold)
    
    Returns:
        {
            'pullback_reached': bool,
            'continuation_momentum': bool,  # NEW V3.3
            'entry_triggered': bool,  # NEW V3.3 (pullback OR momentum)
            'entry_type': str,  # 'pullback' or 'continuation'
            'current_price': float,
            'distance_to_fibo': float (in pips),
            'stop_loss': float,
            'entry_price': float,
            'sl_distance_pips': float,
            'momentum_score': float  # NEW V3.3
        }
    """
    current_price = df_h1.iloc[-1]['close']
    fibo_50 = fibo_data['fibo_50']

    pip_multiplier = 10000
    tolerance = tolerance_pips / pip_multiplier

    # ATR-based buffer (1.5x ATR(14)), fallback la 20 pips dacă ATR nu e disponibil
    try:
        atr = (df_h1['high'] - df_h1['low']).rolling(14).mean().iloc[-1]
        if pd.isna(atr) or atr == 0:
            atr = 20 / pip_multiplier
    except Exception:
        atr = 20 / pip_multiplier
    sl_buffer = max(sl_buffer_pips / pip_multiplier, 1.5 * atr)

    # Lookback mai mare pentru swing (10 candle-uri)
    recent_candles = df_h1.iloc[-max(swing_lookback, 10):]

    # Calculate distance to Fibo 50%
    distance = abs(current_price - fibo_50)
    distance_pips = distance * pip_multiplier
    pullback_reached = distance <= tolerance
    
    # V3.3: Check continuation momentum if no pullback after 6h
    continuation_momentum = False
    momentum_score = 0
    entry_type = None
    
    if check_momentum and not pullback_reached and hours_elapsed >= 6:
        # Check if price shows strong continuation (won't pullback!)
        momentum_data = check_continuation_momentum(df_h1, direction, lookback_candles=3)
        continuation_momentum = momentum_data['has_momentum']
        momentum_score = momentum_data['momentum_score']
        
        if continuation_momentum:
            entry_type = 'continuation'
            # Use current price as entry (no pullback happened)
            entry_price = current_price
        else:
            entry_price = None
    elif pullback_reached:
        entry_type = 'pullback'
        entry_price = fibo_50
    else:
        entry_price = None
    
    # Entry triggered if EITHER pullback reached OR continuation momentum
    entry_triggered = pullback_reached or continuation_momentum

    if direction == 'bullish':
        swing_low = recent_candles['low'].min()
        stop_loss = swing_low - sl_buffer
        if entry_price:
            sl_distance_pips = (entry_price - stop_loss) * pip_multiplier
        else:
            sl_distance_pips = (fibo_50 - stop_loss) * pip_multiplier
    else:
        swing_high = recent_candles['high'].max()
        stop_loss = swing_high + sl_buffer
        if entry_price:
            sl_distance_pips = (stop_loss - entry_price) * pip_multiplier
        else:
            sl_distance_pips = (stop_loss - fibo_50) * pip_multiplier

    return {
        'pullback_reached': pullback_reached,
        'continuation_momentum': continuation_momentum,  # NEW V3.3
        'entry_triggered': entry_triggered,  # NEW V3.3
        'entry_type': entry_type,  # 'pullback', 'continuation', or None
        'current_price': round(current_price, 5),
        'distance_to_fibo': round(distance_pips, 1),
        'stop_loss': round(stop_loss, 5),
        'entry_price': round(entry_price, 5) if entry_price else None,
        'sl_distance_pips': round(sl_distance_pips, 1),
        'fibo_50': round(fibo_50, 5),
        'momentum_score': round(momentum_score, 1),  # NEW V3.3
        'hours_elapsed': hours_elapsed  # Track time
    }


def check_continuation_momentum(
    df_h1: pd.DataFrame,
    direction: str,
    lookback_candles: int = 3,
    atr_multiplier: float = 1.5
) -> dict:
    """
    V3.3: Check if price shows strong continuation momentum
    
    Requirements:
    1. 3+ consecutive candles in trend direction
    2. ATR not contracting (momentum maintained)
    3. No significant counter-trend wicks
    
    Args:
        df_h1: 1H timeframe dataframe
        direction: 'bullish' or 'bearish'
        lookback_candles: Number of recent candles to check (default 3)
        atr_multiplier: ATR expansion threshold (default 1.5)
    
    Returns:
        {
            'has_momentum': bool,
            'consecutive_candles': int,
            'atr_expanding': bool,
            'current_price': float,
            'momentum_score': float (0-100)
        }
    """
    if len(df_h1) < lookback_candles + 14:  # Need 14 for ATR
        return {'has_momentum': False, 'reason': 'Insufficient data'}
    
    recent_candles = df_h1.iloc[-lookback_candles:]
    current_price = df_h1.iloc[-1]['close']
    
    # Check 1: Consecutive candles in trend direction
    consecutive_count = 0
    for idx, candle in recent_candles.iterrows():
        if direction == 'bullish':
            is_bullish = candle['close'] > candle['open']
            if is_bullish:
                consecutive_count += 1
            else:
                break  # Stop if bearish candle found
        else:
            is_bearish = candle['close'] < candle['open']
            if is_bearish:
                consecutive_count += 1
            else:
                break
    
    # Check 2: ATR expansion (momentum strength)
    atr_current = (df_h1['high'] - df_h1['low']).rolling(14).mean().iloc[-1]
    atr_previous = (df_h1['high'] - df_h1['low']).rolling(14).mean().iloc[-15]
    atr_expanding = atr_current >= (atr_previous * 0.9)  # Allow slight contraction
    
    # Check 3: Price movement strength (total pips moved)
    price_start = recent_candles.iloc[0]['open']
    price_end = current_price
    price_move_pct = abs(price_end - price_start) / price_start * 100
    
    # Check 4: Counter-trend wick analysis (rejection wicks reduce confidence)
    rejection_wicks = 0
    for idx, candle in recent_candles.iterrows():
        body = abs(candle['close'] - candle['open'])
        total_range = candle['high'] - candle['low']
        
        if total_range > 0 and body > 0:
            if direction == 'bullish':
                upper_wick = candle['high'] - max(candle['open'], candle['close'])
                if upper_wick > body * 1.5:  # Upper wick > 1.5x body = rejection
                    rejection_wicks += 1
            else:
                lower_wick = min(candle['open'], candle['close']) - candle['low']
                if lower_wick > body * 1.5:
                    rejection_wicks += 1
    
    # Calculate momentum score (0-100)
    score = 0
    score += min(consecutive_count / lookback_candles * 40, 40)  # Max 40 pts
    score += 20 if atr_expanding else 0  # 20 pts for ATR
    score += min(price_move_pct * 20, 30)  # Max 30 pts for price move
    score -= rejection_wicks * 10  # Penalty for rejection wicks
    score = max(0, min(100, score))
    
    # Decision: Has momentum if score ≥ 60
    has_momentum = (consecutive_count >= 3 and score >= 60)
    
    return {
        'has_momentum': has_momentum,
        'consecutive_candles': consecutive_count,
        'atr_expanding': atr_expanding,
        'current_price': round(current_price, 5),
        'momentum_score': round(score, 1),
        'price_move_pct': round(price_move_pct, 2),
        'rejection_wicks': rejection_wicks
    }



