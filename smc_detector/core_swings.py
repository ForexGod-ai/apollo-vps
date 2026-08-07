from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from smc_detector.models import (
    ActiveDealingRange,
    BOS,
    CHoCH,
    D1AuthContext,
    FVG,
    OrderBlock,
    POIResolution,
    StructuralRangeState,
    SwingPoint,
    TradeSetup,
    CRYPTO_MACRO_CEILING_LOOKBACK,
    CRYPTO_MACRO_CEILING_MIN_BARS,
)


class CoreSwingsMixin:
    """V67 C: swing + equilibrium detection."""

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """🔥 Calculate Average True Range for prominence filtering
        
        ATR measures volatility and helps distinguish major swings from micro-structure.
        A swing must move at least atr_multiplier * ATR to be considered significant.
        
        Args:
            df: DataFrame with OHLC data
            period: ATR period (default 14)
        
        Returns:
            ATR value or 0.0 if insufficient data
        """
        if df is None or len(df) < period + 1:
            return 0.0
        
        try:
            # Calculate True Range
            high_low = df['high'] - df['low']
            high_prev_close = abs(df['high'] - df['close'].shift(1))
            low_prev_close = abs(df['low'] - df['close'].shift(1))
            
            true_range = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
            
            # Calculate ATR (simple moving average of TR)
            atr = true_range.rolling(window=period).mean().iloc[-1]
            
            return atr if not pd.isna(atr) else 0.0
        except Exception as e:
            print(f"❌ ATR calculation error: {e}")
            return 0.0

    def calculate_equilibrium_reversal(self, choch: CHoCH,
                                       swing_highs: List[SwingPoint], swing_lows: List[SwingPoint]) -> Optional[float]:
        """🔄 V8.2: Calculate Equilibrium for REVERSAL (CHoCH) - Uses PRE-CHoCH Macro Leg
        
        REVERSAL LOGIC (CHoCH):
        - Measures from the PREVIOUS trend's extreme to CHoCH break price
        - BEARISH Reversal: Last swing HIGH before CHoCH → CHoCH break (LL)
        - BULLISH Reversal: Last swing LOW before CHoCH → CHoCH break (HH)
        
        WHY PRE-CHoCH?
        - CHoCH marks trend change - we measure OLD trend's leg
        - Deep retracement (48-52%) into old trend's range = institutional reversal
        - Example: Downtrend ends at LL (CHoCH), price retraces 50% back to old highs
        
        Args:
            choch: CHoCH signal object
            swing_highs: List of detected swing highs
            swing_lows: List of detected swing lows
        
        Returns:
            Equilibrium price (50% of pre-CHoCH leg) or None
        """
        if not swing_highs or not swing_lows:
            return None
        
        try:
            if choch.direction == 'bearish':
                # BEARISH CHoCH: Price broke down (made LL)
                # Measure from last swing HIGH BEFORE CHoCH to CHoCH break price (LL)
                macro_high = None
                for sh in reversed(swing_highs):
                    if sh.index < choch.index:
                        macro_high = sh.price
                        break
                
                if macro_high is None:
                    return None
                
                macro_low = choch.break_price  # CHoCH break (LL)
                
            else:  # choch.direction == 'bullish'
                # BULLISH CHoCH: Price broke up (made HH)
                # Measure from last swing LOW BEFORE CHoCH to CHoCH break price (HH)
                macro_low = None
                for sl in reversed(swing_lows):
                    if sl.index < choch.index:
                        macro_low = sl.price
                        break
                
                if macro_low is None:
                    return None
                
                macro_high = choch.break_price  # CHoCH break (HH)
            
            # Calculate 50% equilibrium of PRE-CHoCH leg
            equilibrium = (macro_high + macro_low) / 2.0
            
            return equilibrium
        
        except Exception as e:
            print(f"❌ Reversal equilibrium calculation error: {e}")
            return None

    def calculate_equilibrium_continuity(self, bos: BOS, last_choch: Optional[CHoCH],
                                        swing_highs: List[SwingPoint], swing_lows: List[SwingPoint]) -> Optional[float]:
        """➡️ V8.2: Calculate Equilibrium for CONTINUITY (BOS) - Uses POST-CHoCH Impulse Leg
        
        CONTINUITY LOGIC (BOS):
        - Measures ONLY the current impulse leg (after last CHoCH)
        - BEARISH BOS: Last swing HIGH after CHoCH → BOS break (LL in downtrend)
        - BULLISH BOS: Last swing LOW after CHoCH → BOS break (HH in uptrend)
        
        WHY POST-CHoCH?
        - BOS confirms trend continuation - we measure CURRENT impulse
        - Shallower retracement (38-62%) acceptable in strong trends
        - Example: Uptrend continues with BOS (HH), 40% pullback is healthy
        
        Args:
            df: DataFrame with OHLC data
            bos: BOS signal object
            last_choch: Last CHoCH before this BOS (defines impulse start)
            swing_highs: List of detected swing highs
            swing_lows: List of detected swing lows
        
        Returns:
            Equilibrium price (50% of impulse leg) or None
        """
        if not swing_highs or not swing_lows:
            return None
        
        try:
            # If no CHoCH, use last swing as fallback
            choch_index = last_choch.index if last_choch else 0
            
            if bos.direction == 'bullish':
                # BULLISH BOS: Uptrend continuation (HH)
                # Measure from last swing LOW AFTER CHoCH to BOS break (HH)
                macro_low = None
                for sl in reversed(swing_lows):
                    if choch_index < sl.index < bos.index:
                        macro_low = sl.price
                        break
                
                # Fallback: Use last swing low before BOS if no swing after CHoCH
                if macro_low is None:
                    for sl in reversed(swing_lows):
                        if sl.index < bos.index:
                            macro_low = sl.price
                            break
                
                if macro_low is None:
                    return None
                
                macro_high = bos.break_price  # BOS break (HH)
                
            else:  # bos.direction == 'bearish'
                # BEARISH BOS: Downtrend continuation (LL)
                # Measure from last swing HIGH AFTER CHoCH to BOS break (LL)
                macro_high = None
                for sh in reversed(swing_highs):
                    if choch_index < sh.index < bos.index:
                        macro_high = sh.price
                        break
                
                # Fallback: Use last swing high before BOS if no swing after CHoCH
                if macro_high is None:
                    for sh in reversed(swing_highs):
                        if sh.index < bos.index:
                            macro_high = sh.price
                            break
                
                if macro_high is None:
                    return None
                
                macro_low = bos.break_price  # BOS break (LL)
            
            # Calculate 50% equilibrium of IMPULSE leg
            equilibrium = (macro_high + macro_low) / 2.0
            
            return equilibrium
        
        except Exception as e:
            print(f"❌ Continuity equilibrium calculation error: {e}")
            return None

    def detect_liquidity_sweep(
        self,
        df: pd.DataFrame,
        choch: CHoCH,
        symbol: str = "",
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
        
        # V10.0 FIX — pip_multiplier dinamic, corecteaza BUG-ul JPY (100x prea mic)
        # USDJPY: 5/100=0.05 (corect) vs vechea versiune 5/10000=0.0005 (gresit)
        _pip_sz = self._get_pip_size(symbol) if hasattr(self, '_get_pip_size') else 0.0001
        pip_multiplier = int(1 / _pip_sz) if _pip_sz > 0 else 10000
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

    def detect_choch(self, df: pd.DataFrame) -> List[CHoCH]:
        """
        Wrapper simplu: returnează doar lista de CHoCH folosind detect_choch_and_bos.
        """
        chochs, _ = self.detect_choch_and_bos(df)
        return chochs

    def detect_swing_highs(self, df: pd.DataFrame) -> List[SwingPoint]:
        """🎯 GLITCH IN MATRIX - MACRO SWING DETECTION V24.0 (ORGANIC PIVOT)

        🆕 V24.0 — COLONEL'S ORGANIC REFACTOR:
        - FRACTAL_WINDOW = 2 fix (minimal agil — identifică geometric vârful local)
        - Odată recunoscut, pivotul rămâne în memorie la NESFÂRȘIT — NU expiră
        - Identificare prin WICK absolut (df['high']) — fitilul real al pieței
        - Body Close Rule se aplică EXCLUSIV la validarea BOS/CHoCH (detect_choch_and_bos)

        PHILOSOPHY by ФорексГод + Colonel:
        "Un Swing High format pe grafic rămâne nivel structural VALID la nesfârșit,
        până când prețul îl sparge. Nu expiră în 10 zile, nici în 20."

        Args:
            df: DataFrame with OHLC data

        Returns:
            List of SwingPoint objects — toți pivoții geometrici, fără expirare
        """
        if df is None or len(df) == 0:
            return []

        # ⚡ V13.1 CACHE CHECK — acelasi df obiect + aceeasi lungime = date identice
        _cache_key = (id(df), len(df))
        if _cache_key in self._swing_highs_cache:
            return self._swing_highs_cache[_cache_key]

        # V36.0 FIX B3: FRACTAL_WINDOW ADAPTIV — Daily redus de la 5 la 3
        # V29.0: FW=5 pe Daily lasa o zona moarta de 5 zile la marginea graficului.
        # Un CHoCH bearish format vineri dimineata era INVIZIBIL pana marti dimineata.
        # V36.0: FW=3 → zona moarta redusa la 3 zile (weekend = 0 bare = practic invizibil 1 zi)
        # Daily (≥20h/bar): FW=3 — prinde swing-uri din ultimele 3 zile (era 5)
        # 4H  (3-20h/bar): FW=3 — echilibru precizie/calitate (nemodificat)
        # 1H/sub         : FW=2 — fractal agil (comportament V24.0 original, nemodificat)
        FRACTAL_WINDOW = 2  # default: 1H și sub
        try:
            if len(df) >= 3 and hasattr(df.index, 'to_series'):
                _td_series = df.index.to_series().diff().dropna()
                _median_sec = _td_series.median().total_seconds()
                if _median_sec >= 72000:    # ≥20h → Daily
                    FRACTAL_WINDOW = 3  # V36.0: era 5 → redus la 3 (zona oarba 5→3 zile)
                elif _median_sec >= 10800:  # ≥3h → 4H
                    FRACTAL_WINDOW = 3
                # else: 1H sau sub → 2
        except Exception:
            pass  # index non-timestamp (RangeIndex, backtesting) → fallback 2
        swing_highs = []
        body_highs = df[['open', 'close']].max(axis=1)

        for i in range(FRACTAL_WINDOW, len(df) - FRACTAL_WINDOW):
            current_high = body_highs.iloc[i]

            left_check = all(
                current_high > body_highs.iloc[i - j]
                for j in range(1, FRACTAL_WINDOW + 1)
            )
            right_check = all(
                current_high > body_highs.iloc[i + j]
                for j in range(1, FRACTAL_WINDOW + 1)
            )

            if left_check and right_check:
                swing_highs.append(SwingPoint(
                    index=i,
                    price=float(current_high),
                    swing_type='high',
                    candle_time=df.index[i] if not isinstance(df.index, pd.RangeIndex) else i
                ))

        # ⚡ V13.1: Stochează în cache înainte de return
        self._swing_highs_cache[_cache_key] = swing_highs
        return swing_highs

    def detect_swing_lows(self, df: pd.DataFrame) -> List[SwingPoint]:
        """🎯 GLITCH IN MATRIX - MACRO SWING DETECTION V24.0 (ORGANIC PIVOT)

        🆕 V24.0 — COLONEL'S ORGANIC REFACTOR:
        - FRACTAL_WINDOW = 2 fix (minimal agil — identifică geometric minimul local)
        - Odată recunoscut, pivotul rămâne în memorie la NESFÂRȘIT — NU expiră
        - Identificare prin WICK absolut (df['low']) — fitilul real al pieței
        - Body Close Rule se aplică EXCLUSIV la validarea BOS/CHoCH (detect_choch_and_bos)

        PHILOSOPHY by ФорексГод + Colonel:
        "Un Swing Low format pe grafic rămâne nivel structural VALID la nesfârșit,
        până când prețul îl sparge. Nu expiră niciodată din cauza timpului."
        """
        if df is None or len(df) == 0:
            return []

        # ⚡ V13.1 CACHE CHECK — acelasi df obiect + aceeasi lungime = date identice
        _cache_key = (id(df), len(df))
        if _cache_key in self._swing_lows_cache:
            return self._swing_lows_cache[_cache_key]

        # V36.0 FIX B3: FRACTAL_WINDOW ADAPTIV — Daily=3 (era 5), 4H=3, 1H/sub=2 (simetric cu detect_swing_highs)
        # Motivul: FW=5 pe Daily lasa zona moarta de 5 zile la marginea graficului.
        # V36.0: FW=3 → zona moarta redusa la 3 zile (simetric cu detect_swing_highs).
        FRACTAL_WINDOW = 2
        try:
            if len(df) >= 3 and hasattr(df.index, 'to_series'):
                _td_series = df.index.to_series().diff().dropna()
                _median_sec = _td_series.median().total_seconds()
                if _median_sec >= 72000:
                    FRACTAL_WINDOW = 3  # V36.0: era 5 → redus la 3 (zona oarba 5→3 zile)
                elif _median_sec >= 10800:
                    FRACTAL_WINDOW = 3
        except Exception:
            pass
        swing_lows = []
        body_lows = df[['open', 'close']].min(axis=1)

        for i in range(FRACTAL_WINDOW, len(df) - FRACTAL_WINDOW):
            current_low = body_lows.iloc[i]

            left_check = all(
                current_low < body_lows.iloc[i - j]
                for j in range(1, FRACTAL_WINDOW + 1)
            )
            right_check = all(
                current_low < body_lows.iloc[i + j]
                for j in range(1, FRACTAL_WINDOW + 1)
            )

            if left_check and right_check:
                swing_lows.append(SwingPoint(
                    index=i,
                    price=float(current_low),
                    swing_type='low',
                    candle_time=df.index[i] if not isinstance(df.index, pd.RangeIndex) else i
                ))

        # ⚡ V13.1: Stochează în cache înainte de return
        self._swing_lows_cache[_cache_key] = swing_lows
        return swing_lows

    def _body_close_below_after(
        self, df: pd.DataFrame, after_index: int, level: float,
    ) -> bool:
        """True dacă vreun close după after_index sparge sub level (body-close)."""
        for i in range(max(after_index + 1, 0), len(df)):
            if float(df['close'].iloc[i]) < level:
                return True
        return False

    def _body_close_above_after(
        self, df: pd.DataFrame, after_index: int, level: float,
    ) -> bool:
        """True dacă vreun close după after_index sparge peste level (body-close)."""
        for i in range(max(after_index + 1, 0), len(df)):
            if float(df['close'].iloc[i]) > level:
                return True
        return False

    def filter_major_swings(
        self,
        df: pd.DataFrame,
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint],
    ) -> Tuple[List[SwingPoint], List[SwingPoint]]:
        """
        Faza A — Leg authority: pivot major confirmat cu impuls LL/HH (body-close).

        Swing High major = impuls descendent cu close sub ultimul Swing Low anterior.
        Swing Low major = impuls ascendent cu close peste ultimul Swing High anterior.
        """
        if not swing_highs or not swing_lows:
            return [], []

        major_highs: List[SwingPoint] = []
        major_lows: List[SwingPoint] = []

        for sh in swing_highs:
            prior_lows = [sl for sl in swing_lows if sl.index < sh.index]
            if not prior_lows:
                continue
            ref_level = self._swing_body_low(df, prior_lows[-1].index)
            if self._body_close_below_after(df, sh.index, ref_level):
                major_highs.append(sh)

        for sl in swing_lows:
            prior_highs = [sh for sh in swing_highs if sh.index < sl.index]
            if not prior_highs:
                continue
            ref_level = self._swing_body_high(df, prior_highs[-1].index)
            if self._body_close_above_after(df, sl.index, ref_level):
                major_lows.append(sl)

        return major_highs, major_lows

    @staticmethod
    def _last_swing_before(
        bar_index: int,
        preferred: List[SwingPoint],
        fallback: List[SwingPoint],
    ) -> Optional[SwingPoint]:
        """V64: ultimul pivot înainte de bar — preferă majori, altfel geometrici."""
        prior = [s for s in preferred if s.index < bar_index]
        if prior:
            return prior[-1]
        prior_fb = [s for s in fallback if s.index < bar_index]
        return prior_fb[-1] if prior_fb else None

    @staticmethod
    def _swing_body_high(df: pd.DataFrame, idx: int) -> float:
        return max(float(df['open'].iloc[idx]), float(df['close'].iloc[idx]))

    @staticmethod
    def _swing_body_low(df: pd.DataFrame, idx: int) -> float:
        return min(float(df['open'].iloc[idx]), float(df['close'].iloc[idx]))

    def macro_trend_from_swings(self, df: pd.DataFrame) -> str:
        """HH+HL vs LH+LL — majori dacă disponibili, altfel geometrici recenti (V64 JPY fix)."""
        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        major_highs, major_lows = self.filter_major_swings(df, swing_highs, swing_lows)
        trend_highs = major_highs if len(major_highs) >= 3 else swing_highs
        trend_lows = major_lows if len(major_lows) >= 3 else swing_lows
        if len(trend_highs) < 3 or len(trend_lows) < 3:
            return 'neutral'
        recent_highs = trend_highs[-3:]
        recent_lows = trend_lows[-3:]
        hh_count = sum(
            1 for i in range(1, len(recent_highs))
            if recent_highs[i].price > recent_highs[i - 1].price
        )
        lh_count = sum(
            1 for i in range(1, len(recent_highs))
            if recent_highs[i].price < recent_highs[i - 1].price
        )
        hl_count = sum(
            1 for i in range(1, len(recent_lows))
            if recent_lows[i].price > recent_lows[i - 1].price
        )
        ll_count = sum(
            1 for i in range(1, len(recent_lows))
            if recent_lows[i].price < recent_lows[i - 1].price
        )
        if hh_count >= 2 and hl_count >= 1:
            return 'bullish'
        if lh_count >= 2 and ll_count >= 1:
            return 'bearish'
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
