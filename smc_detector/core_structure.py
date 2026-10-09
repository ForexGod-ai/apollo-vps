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


class CoreStructureMixin:
    """V67 C: CHoCH/BOS + structural range."""

    def detect_choch_and_bos(self, df: pd.DataFrame) -> Tuple[List[CHoCH], List[BOS]]:
        """🎯 GLITCH IN MATRIX - CHoCH & BOS DETECTION V71.0 (MAJOR SWINGS ONLY)

        V71 — Pure SMC lifecycle (no Rule 2 / Major LH gate):
        - CHoCH/BOS on major swings only; body-close vs prior swing body (not wick)
        - Body-close break of prior swing high/low → CHoCH when trend flips, else BOS
        - No internal-pullback veto from historical Major LH/HL
        """
        chochs = []
        bos_list = []

        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        major_highs, major_lows = self.filter_major_swings(df, swing_highs, swing_lows)

        if len(major_highs) < 2 or len(major_lows) < 2:
            return chochs, bos_list

        # V68: iterate MAJOR swings only — micro pivots are noise.
        all_swings = []
        for sh in major_highs:
            all_swings.append(('high', sh))
        for sl in major_lows:
            all_swings.append(('low', sl))
        all_swings.sort(key=lambda x: x[1].index)

        prev_trend = self.macro_trend_from_swings(df)
        if prev_trend == 'neutral':
            init_highs = major_highs[:2]
            init_lows = major_lows[:2]
            if len(init_highs) >= 2 and len(init_lows) >= 2:
                h_asc = init_highs[1].price > init_highs[0].price
                l_asc = init_lows[1].price > init_lows[0].price
                if h_asc and l_asc:
                    prev_trend = 'bullish'
                elif not h_asc and not l_asc:
                    prev_trend = 'bearish'

        for i in range(1, len(all_swings)):
            swing_type, swing = all_swings[i]

            if swing_type == 'high':
                prev_high = next(
                    (s for t, s in reversed(all_swings[:i]) if t == 'high'),
                    None,
                )
                if prev_high is None:
                    continue

                if swing.price > prev_high.price:
                    # V36.0 FIX B1: BODY CLOSE RULE CORECTATA — close > BODY_HIGH (nu > WICK)
                    # Motivul bug-ului V22: _prev_wick_h = prev_high.price = df['high'] (wick absolut)
                    # Pe GBPNZD/XTIUSD/JPY crosses: wick >> body → close depasea BODY dar nu WICK
                    # → CHoCH/BOS omis complet pe piete volatile = unghiul mort principal.
                    # Fix: comparam close cu BODY_HIGH (max open/close) al pivot-ului anterior.
                    # Liquidity Sweep (wick hunt) este prins tot: wick trece dincolo de BODY
                    # dar close revine sub body_high = sweep fara confirmare structurala.
                    _prev_body_h = max(
                        float(df['open'].iloc[prev_high.index]),
                        float(df['close'].iloc[prev_high.index])
                    )  # V36.0: body high al swing-ului anterior (nu wick absolut)
                    _body_close_confirmed_h = False
                    _confirm_bar_h = None
                    for _ci in range(prev_high.index + 1, min(swing.index + 1, len(df))):
                        if float(df['close'].iloc[_ci]) > _prev_body_h:
                            _body_close_confirmed_h = True
                            _confirm_bar_h = _ci
                            break
                    if not _body_close_confirmed_h:
                        # Close nu a depasit body-ul prev_high → sweep sau miscare fara confirmare
                        pass
                    elif _body_close_confirmed_h and prev_trend is None:
                        chochs.append(CHoCH(
                            index=swing.index,
                            direction='bullish',
                            break_price=swing.price,
                            previous_trend=None,
                            candle_time=swing.candle_time,
                            swing_broken=prev_high
                        ))
                        prev_trend = 'bullish'
                    elif _body_close_confirmed_h and prev_trend == 'bearish':
                        chochs.append(CHoCH(
                            index=swing.index,
                            direction='bullish',
                            break_price=swing.price,
                            previous_trend='bearish',
                            candle_time=swing.candle_time,
                            swing_broken=prev_high,
                        ))
                        prev_trend = 'bullish'
                    elif _body_close_confirmed_h:  # prev_trend == 'bullish'
                        # BOS bullish = HH continuation only (macro high break in uptrend)
                        bos_list.append(BOS(
                            index=swing.index,
                            direction='bullish',
                            break_price=prev_high.price,
                            candle_time=swing.candle_time,
                            swing_broken=prev_high
                        ))

            elif swing_type == 'low':
                prev_low = next(
                    (s for t, s in reversed(all_swings[:i]) if t == 'low'),
                    None,
                )
                if prev_low is None:
                    continue

                if swing.price < prev_low.price:
                    # V36.0 FIX B1: BODY CLOSE RULE CORECTATA — close < BODY_LOW (nu < WICK)
                    # Motivul bug-ului V22: _prev_wick_l = prev_low.price = df['low'] (wick absolut)
                    # Pe GBPNZD/XTIUSD/JPY crosses: wick << body → close depasea BODY dar nu WICK
                    # → CHoCH/BOS omis complet pe piete volatile.
                    # Fix: comparam close cu BODY_LOW (min open/close) al pivot-ului anterior.
                    _prev_body_l = min(
                        float(df['open'].iloc[prev_low.index]),
                        float(df['close'].iloc[prev_low.index])
                    )  # V36.0: body low al swing-ului anterior (nu wick absolut)
                    _body_close_confirmed_l = False
                    _confirm_bar_l = None
                    for _ci in range(prev_low.index + 1, min(swing.index + 1, len(df))):
                        if float(df['close'].iloc[_ci]) < _prev_body_l:
                            _body_close_confirmed_l = True
                            _confirm_bar_l = _ci
                            break
                    if not _body_close_confirmed_l:
                        # Close nu a depasit body-ul prev_low → sweep sau miscare fara confirmare
                        pass
                    elif _body_close_confirmed_l and prev_trend is None:
                        chochs.append(CHoCH(
                            index=swing.index,
                            direction='bearish',
                            break_price=swing.price,
                            previous_trend=None,
                            candle_time=swing.candle_time,
                            swing_broken=prev_low
                        ))
                        prev_trend = 'bearish'
                    elif _body_close_confirmed_l and prev_trend == 'bullish':
                        chochs.append(CHoCH(
                            index=swing.index,
                            direction='bearish',
                            break_price=swing.price,
                            previous_trend='bullish',
                            candle_time=swing.candle_time,
                            swing_broken=prev_low,
                        ))
                        prev_trend = 'bearish'
                    elif _body_close_confirmed_l:  # prev_trend == 'bearish'
                        # BOS bearish = LL continuation only (macro low break in downtrend)
                        bos_list.append(BOS(
                            index=swing.index,
                            direction='bearish',
                            break_price=prev_low.price,
                            candle_time=swing.candle_time,
                            swing_broken=prev_low
                        ))

        return chochs, bos_list

    def compute_structural_range(
        self,
        df: pd.DataFrame,
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint],
        symbol: Optional[str] = None,
    ) -> Optional[StructuralRangeState]:
        """Lock bearish range between major LH (body high) and LL (body low).

        V40.1: pe crypto/metals/energy, macro_range_high = max(body-high) ultimele
        90–150 bare D1 — evită LH local ~63k care genera LOCK BULLISH fals pe BTCUSD.
        """
        if df is None or len(df) < 20:
            return None

        major_highs, major_lows = self.filter_major_swings(df, swing_highs, swing_lows)
        if len(major_highs) >= 2 and len(major_lows) >= 2:
            swing_highs, swing_lows = major_highs, major_lows
        elif len(swing_highs) < 3 or len(swing_lows) < 2:
            return None

        recent_highs = swing_highs[-3:]
        recent_lows = swing_lows[-3:]
        lh_count = sum(
            1 for i in range(1, len(recent_highs))
            if recent_highs[i].price < recent_highs[i - 1].price
        )
        ll_count = sum(
            1 for i in range(1, len(recent_lows))
            if recent_lows[i].price < recent_lows[i - 1].price
        )
        if lh_count < 1 or ll_count < 1:
            return None

        low_sp = swing_lows[-1]
        macro_range_low = self._swing_body_low(df, low_sp.index)
        macro_range_low_bar = low_sp.index

        highs_before = [h for h in swing_highs if h.index < macro_range_low_bar]
        macro_range_high = None
        macro_range_high_bar = None
        if len(highs_before) >= 2:
            for i in range(len(highs_before) - 1, 0, -1):
                if highs_before[i].price < highs_before[i - 1].price:
                    macro_range_high_bar = highs_before[i].index
                    macro_range_high = self._swing_body_high(df, macro_range_high_bar)
                    break
        if macro_range_high is None and highs_before:
            h = highs_before[-1]
            macro_range_high_bar = h.index
            macro_range_high = self._swing_body_high(df, h.index)

        if macro_range_high is None or macro_range_high <= macro_range_low:
            return None

        # V40.1 CRYPTO MACRO CEILING — tavan real (~77k BTC), nu LH din ultimul picior
        if self._uses_macro_ceiling(symbol):
            avail = len(df)
            lookback = min(CRYPTO_MACRO_CEILING_LOOKBACK, avail)
            if lookback >= CRYPTO_MACRO_CEILING_MIN_BARS:
                ceiling, ceiling_bar = self._compute_macro_ceiling_d1(df, lookback)
                if ceiling > macro_range_low:
                    _old_lh = macro_range_high
                    macro_range_high = ceiling
                    macro_range_high_bar = ceiling_bar
                    _sym = symbol or 'CRYPTO'
                    print(
                        f"   📐 [V40.1 MACRO CEILING] {_sym}: LH local {_old_lh:.2f} → "
                        f"max body-high {lookback}D = {ceiling:.2f} (bar {ceiling_bar})"
                    )

        close = float(df['close'].iloc[-1])
        locked_bias = 'neutral'
        if close > macro_range_high:
            locked = True
            locked_bias = 'bullish'
        elif close <= macro_range_low:
            locked = True
            locked_bias = 'bearish'
        elif macro_range_low < close < macro_range_high:
            locked = True
            macro = self.macro_trend_from_swings(df)
            locked_bias = macro if macro != 'neutral' else 'neutral'
        else:
            locked = False

        return StructuralRangeState(
            macro_range_high=macro_range_high,
            macro_range_low=macro_range_low,
            macro_range_high_bar=macro_range_high_bar,
            macro_range_low_bar=macro_range_low_bar,
            locked=locked,
            locked_bias=locked_bias,
        )

    def _range_signal_level(self, df: pd.DataFrame, signal) -> float:
        return float(signal.break_price)

    def _bar_body_close_above(self, df: pd.DataFrame, bar_index: int, level: float) -> bool:
        """V42: True if bar body close (or body high) clears structural level."""
        if bar_index < 0 or bar_index >= len(df):
            return False
        _close = float(df['close'].iloc[bar_index])
        _open = float(df['open'].iloc[bar_index])
        _body_high = max(_open, _close)
        return _close > level or _body_high > level

    def _bar_body_close_below(self, df: pd.DataFrame, bar_index: int, level: float) -> bool:
        """V59: symmetric — body close (or body low) clears structural level downward."""
        if bar_index < 0 or bar_index >= len(df):
            return False
        _close = float(df['close'].iloc[bar_index])
        _open = float(df['open'].iloc[bar_index])
        _body_low = min(_open, _close)
        return _close < level or _body_low < level

    def _is_internal_range_signal(
        self,
        df: pd.DataFrame,
        signal,
        range_state: StructuralRangeState,
    ) -> bool:
        """V59 + V64.3: sub-structure filter — true CHoCH flips never internal."""
        if isinstance(signal, CHoCH):
            pt = getattr(signal, 'previous_trend', None)
            if pt and pt != signal.direction:
                return False
        if isinstance(signal, BOS):
            if (
                signal.direction == 'bullish'
                and range_state.locked_bias == 'bearish'
                and not self._bar_body_close_above(
                    df, signal.index, range_state.macro_range_high,
                )
            ):
                return True
            if (
                signal.direction == 'bearish'
                and range_state.locked_bias == 'bullish'
                and not self._bar_body_close_below(
                    df, signal.index, range_state.macro_range_low,
                )
            ):
                return True
        if not range_state.locked:
            return False
        close = float(df['close'].iloc[-1])
        if not (range_state.macro_range_low < close < range_state.macro_range_high):
            return False
        # Structural breakout from range — keep CHoCH that clears bound with body-close
        if isinstance(signal, CHoCH):
            if signal.direction == 'bullish' and self._bar_body_close_above(
                df, signal.index, range_state.macro_range_high
            ):
                return False
            if signal.direction == 'bearish' and self._bar_body_close_below(
                df, signal.index, range_state.macro_range_low
            ):
                return False
        level = self._range_signal_level(df, signal)
        if range_state.macro_range_low < level < range_state.macro_range_high:
            return True
        if signal.index >= range_state.macro_range_low_bar and level < range_state.macro_range_high:
            return level >= range_state.macro_range_low
        return False

    def filter_internal_range_signals(
        self,
        symbol: str,
        df: pd.DataFrame,
        chochs: List[CHoCH],
        bos_list: List[BOS],
        range_state: Optional[StructuralRangeState],
        debug: bool = False,
    ) -> Tuple[List[CHoCH], List[BOS], Optional[StructuralRangeState]]:
        """V71: no sub-structure stripping — keep all body-close-valid CHoCH/BOS."""
        del symbol, df, debug
        return chochs, bos_list, range_state
