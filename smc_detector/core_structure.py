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
)


class CoreStructureMixin:
    """V67 C: CHoCH/BOS + structural range."""

    def d1_closed_structure_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """V72: structural D1 authority uses only finalized daily candles."""
        if df is None or df.empty:
            return df
        if len(df) < 2:
            return df
        if df.attrs.get("apollo_d1_closed_only"):
            return df
        out = df.iloc[:-1].copy()
        out.attrs["apollo_d1_closed_only"] = True
        return out

    @staticmethod
    def _bar_time(df: pd.DataFrame, idx: int):
        if isinstance(df.index, pd.RangeIndex):
            return idx
        return df.index[idx]

    def run_d1_smc_state_machine(
        self,
        df: pd.DataFrame,
        debug: bool = False,
    ) -> dict:
        """
        V82.1 — Pivot state machine + stale-leg reconcile + CONT/REV from post-CHoCH BOS.

        State: bias, protected_pivot (HL/LH), target_pivot (HH/LL). Pullback keeps bias;
        flip on body close through protected_pivot. Terminal pass: if close breaks below
        the active bullish leg CHoCH/BOS floor, force bearish (and symmetric for bearish).
        """
        empty = {
            'trend': 'neutral',
            'latest_signal': None,
            'strategy_type': 'continuation',
            'leg_choch': None,
            'chochs': [],
            'bos_list': [],
            'protected_low': None,
            'protected_high': None,
            'structural_hh': None,
            'structural_hl': None,
        }
        if df is None or len(df) < 2:
            return empty

        bh = self._swing_body_high
        bl = self._swing_body_low
        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        major_highs, major_lows = self.filter_major_swings(
            df, swing_highs, swing_lows,
        )
        fw = max(self._swing_fractal_window(df), 2)
        swing_low_indices = {l.index for l in swing_lows}
        swing_high_indices = {h.index for h in swing_highs}

        def swing_pt(i: int, st: str) -> SwingPoint:
            if st == 'high':
                for h in swing_highs:
                    if h.index == i:
                        return h
                price = float(df['high'].iloc[i])
            else:
                for l in swing_lows:
                    if l.index == i:
                        return l
                price = float(df['low'].iloc[i])
            return SwingPoint(
                index=i,
                price=price,
                swing_type=st,
                candle_time=self._bar_time(df, i),
            )

        def confirmed_highs(bar_i: int) -> List[SwingPoint]:
            return [h for h in swing_highs if h.index + fw <= bar_i]

        def confirmed_lows(bar_i: int) -> List[SwingPoint]:
            return [l for l in swing_lows if l.index + fw <= bar_i]

        def broken_swing_high(bar_i: int, close_px: float) -> Optional[SwingPoint]:
            pool = [h for h in major_highs if h.index + fw <= bar_i]
            if not pool:
                pool = confirmed_highs(bar_i)
            for h in reversed(pool):
                if close_px > bh(df, h.index):
                    return h
            return None

        def broken_swing_low(bar_i: int, close_px: float) -> Optional[SwingPoint]:
            pool = [l for l in major_lows if l.index + fw <= bar_i]
            if not pool:
                pool = confirmed_lows(bar_i)
            for l in reversed(pool):
                if close_px < bl(df, l.index):
                    return l
            return None

        def deepest_confirmed_low(bar_i: int, cap_idx: int) -> Optional[SwingPoint]:
            lows = [l for l in confirmed_lows(bar_i) if l.index <= cap_idx]
            if not lows:
                return None
            return min(lows, key=lambda l: bl(df, l.index))

        def highest_confirmed_high(bar_i: int, cap_idx: int) -> Optional[SwingPoint]:
            highs = [h for h in confirmed_highs(bar_i) if h.index <= cap_idx]
            if not highs:
                return None
            return max(highs, key=lambda h: bh(df, h.index))

        chochs: List[CHoCH] = []
        bos_list: List[BOS] = []
        bias: Optional[str] = None
        protected_pivot: Optional[float] = None
        target_pivot: Optional[float] = None
        protected_idx: Optional[int] = None
        target_idx: Optional[int] = None
        ref_high = bh(df, 0)
        ref_low = bl(df, 0)
        last_event_bar = 0
        latest_signal = None
        leg_choch = None
        MIN_FLIP_COOLDOWN = 5

        def _set_bullish_pivots(hl_idx: int, hh_idx: int) -> None:
            nonlocal protected_pivot, target_pivot, protected_idx, target_idx
            protected_idx = hl_idx
            target_idx = hh_idx
            protected_pivot = float(bl(df, hl_idx))
            target_pivot = float(bh(df, hh_idx))

        def _set_bearish_pivots(lh_idx: int, ll_idx: int) -> None:
            nonlocal protected_pivot, target_pivot, protected_idx, target_idx
            protected_idx = lh_idx
            target_idx = ll_idx
            protected_pivot = float(bh(df, lh_idx))
            target_pivot = float(bl(df, ll_idx))

        def _hl_from_impulse(start_idx: int, end_idx: int) -> Tuple[int, float]:
            """Fractal HL at impulse origin before BOS-up (body low of pivot)."""
            origin = self._impulse_origin_low_between(
                df, swing_lows, start_idx, end_idx,
            )
            if origin is not None:
                return origin.index, float(bl(df, origin.index))
            lows = [l for l in confirmed_lows(end_idx) if start_idx < l.index <= end_idx]
            if lows:
                deepest = min(lows, key=lambda l: bl(df, l.index))
                return deepest.index, float(bl(df, deepest.index))
            return end_idx, float(bl(df, end_idx))

        def _lh_from_impulse(start_idx: int, end_idx: int) -> Tuple[int, float]:
            """Fractal LH at impulse origin before BOS-down (body high of pivot)."""
            origin = self._impulse_origin_high_between(
                df, swing_highs, start_idx, end_idx,
            )
            if origin is not None:
                return origin.index, float(bh(df, origin.index))
            highs = [h for h in confirmed_highs(end_idx) if start_idx < h.index <= end_idx]
            if highs:
                highest = max(highs, key=lambda h: bh(df, h.index))
                return highest.index, float(bh(df, highest.index))
            return end_idx, float(bh(df, end_idx))

        for i in range(1, len(df)):
            close = float(df['close'].iloc[i])
            ct = self._bar_time(df, i)

            if bias is None:
                if close > ref_high:
                    br_h = broken_swing_high(i, close)
                    if br_h is None:
                        ref_high = max(ref_high, bh(df, i))
                        ref_low = min(ref_low, bl(df, i))
                        continue
                    hl_idx, hl_px = _hl_from_impulse(0, i)
                    bias = 'bullish'
                    protected_pivot = hl_px
                    protected_idx = hl_idx
                    target_idx = br_h.index
                    target_pivot = float(bh(df, br_h.index))
                    last_event_bar = i
                    ev = CHoCH(
                        index=i,
                        direction='bullish',
                        break_price=target_pivot,
                        previous_trend=None,
                        candle_time=ct,
                        swing_broken=br_h,
                    )
                    chochs.append(ev)
                    latest_signal = ev
                    leg_choch = ev
                elif close < ref_low:
                    br_l = broken_swing_low(i, close)
                    if br_l is None:
                        ref_high = max(ref_high, bh(df, i))
                        ref_low = min(ref_low, bl(df, i))
                        continue
                    lh_idx, lh_px = _lh_from_impulse(0, i)
                    bias = 'bearish'
                    protected_pivot = lh_px
                    protected_idx = lh_idx
                    target_idx = br_l.index
                    target_pivot = float(bl(df, br_l.index))
                    last_event_bar = i
                    ev = CHoCH(
                        index=i,
                        direction='bearish',
                        break_price=target_pivot,
                        previous_trend=None,
                        candle_time=ct,
                        swing_broken=br_l,
                    )
                    chochs.append(ev)
                    latest_signal = ev
                    leg_choch = ev
                else:
                    ref_high = max(ref_high, bh(df, i))
                    ref_low = min(ref_low, bl(df, i))
                continue

            assert protected_pivot is not None and target_pivot is not None

            if bias == 'bullish':
                # 3. Bearish CHoCH — body close below sacred HL
                if (
                    i > last_event_bar + MIN_FLIP_COOLDOWN
                    and close < protected_pivot
                ):
                    lh_idx = target_idx if target_idx is not None else i
                    ll_cand = deepest_confirmed_low(i, i)
                    if ll_cand is None:
                        ll_cand = swing_pt(i, 'low')
                    ll_idx = ll_cand.index
                    bias = 'bearish'
                    _set_bearish_pivots(lh_idx, ll_idx)
                    last_event_bar = i
                    broken = swing_pt(protected_idx or 0, 'low')
                    ev = CHoCH(
                        index=i,
                        direction='bearish',
                        break_price=protected_pivot,
                        previous_trend='bullish',
                        candle_time=ct,
                        swing_broken=broken,
                    )
                    chochs.append(ev)
                    latest_signal = ev
                    leg_choch = ev
                    continue

                # 1. BOS bullish — close above HH target (confirmed fractal high)
                if close > target_pivot:
                    pool = [
                        h for h in major_highs
                        if h.index + fw <= i and close > bh(df, h.index)
                    ]
                    if not pool:
                        pool = [
                            h for h in confirmed_highs(i)
                            if close > bh(df, h.index)
                        ]
                    if pool:
                        br_h = max(pool, key=lambda h: bh(df, h.index))
                        if target_idx is not None and br_h.index <= target_idx:
                            continue
                        start = target_idx if target_idx is not None else 0
                        hl_idx, hl_px = _hl_from_impulse(start, i)
                        protected_pivot = hl_px
                        protected_idx = hl_idx
                        target_idx = br_h.index
                        target_pivot = float(bh(df, br_h.index))
                        last_event_bar = i
                        ev = BOS(
                            index=i,
                            direction='bullish',
                            break_price=target_pivot,
                            candle_time=ct,
                            swing_broken=br_h,
                        )
                        bos_list.append(ev)
                        latest_signal = ev
                    continue

                # 2. Pullback: protected_pivot < close <= target_pivot — no state change
                continue

            if bias == 'bearish':
                if (
                    i > last_event_bar + MIN_FLIP_COOLDOWN
                    and close > protected_pivot
                ):
                    hl_idx = target_idx if target_idx is not None else i
                    hh_cand = highest_confirmed_high(i, i)
                    if hh_cand is None:
                        hh_cand = swing_pt(i, 'high')
                    hh_idx = hh_cand.index
                    bias = 'bullish'
                    _set_bullish_pivots(hl_idx, hh_idx)
                    last_event_bar = i
                    broken = swing_pt(protected_idx or 0, 'high')
                    ev = CHoCH(
                        index=i,
                        direction='bullish',
                        break_price=protected_pivot,
                        previous_trend='bearish',
                        candle_time=ct,
                        swing_broken=broken,
                    )
                    chochs.append(ev)
                    latest_signal = ev
                    leg_choch = ev
                    continue

                if close < target_pivot:
                    pool = [
                        l for l in major_lows
                        if l.index + fw <= i and close < bl(df, l.index)
                    ]
                    if not pool:
                        pool = [
                            l for l in confirmed_lows(i)
                            if close < bl(df, l.index)
                        ]
                    if pool:
                        br_l = min(pool, key=lambda l: bl(df, l.index))
                        if target_idx is not None and br_l.index <= target_idx:
                            continue
                        start = target_idx if target_idx is not None else 0
                        lh_idx, lh_px = _lh_from_impulse(start, i)
                        protected_pivot = lh_px
                        protected_idx = lh_idx
                        target_idx = br_l.index
                        target_pivot = float(bl(df, br_l.index))
                        last_event_bar = i
                        ev = BOS(
                            index=i,
                            direction='bearish',
                            break_price=target_pivot,
                            candle_time=ct,
                            swing_broken=br_l,
                        )
                        bos_list.append(ev)
                        latest_signal = ev
                    continue

                continue

        def _last_leg_choch(direction: str) -> Optional[CHoCH]:
            for c in reversed(chochs):
                if c.direction == direction:
                    return c
            return None

        def _leg_impulse_ref(leg: CHoCH) -> float:
            ref = float(leg.break_price)
            same = [
                b for b in bos_list
                if b.index > leg.index and b.direction == leg.direction
            ]
            if not same:
                return ref
            last_b = same[-1]
            if leg.direction == 'bullish':
                return max(ref, float(last_b.break_price))
            return min(ref, float(last_b.break_price))

        last_i = len(df) - 1
        last_close = float(df['close'].iloc[last_i])
        last_ct = self._bar_time(df, last_i)

        def _force_bearish_terminal() -> None:
            nonlocal bias, latest_signal, leg_choch, last_event_bar
            lh_cand = highest_confirmed_high(last_i, last_i)
            lh_idx = (
                lh_cand.index if lh_cand is not None
                else (target_idx if target_idx is not None else last_i)
            )
            ll_cand = deepest_confirmed_low(last_i, last_i)
            ll_idx = ll_cand.index if ll_cand is not None else last_i
            bias = 'bearish'
            _set_bearish_pivots(lh_idx, ll_idx)
            broken = swing_pt(protected_idx or ll_idx, 'low')
            br_px = float(protected_pivot) if protected_pivot is not None else float(bl(df, ll_idx))
            ev = CHoCH(
                index=last_i,
                direction='bearish',
                break_price=br_px,
                previous_trend='bullish',
                candle_time=last_ct,
                swing_broken=broken,
            )
            chochs.append(ev)
            latest_signal = ev
            leg_choch = ev
            last_event_bar = last_i

        if bias == 'bullish':
            bull_leg = _last_leg_choch('bullish')
            if bull_leg is not None and last_close < _leg_impulse_ref(bull_leg):
                _force_bearish_terminal()
            elif (
                protected_pivot is not None
                and target_pivot is not None
                and target_pivot > protected_pivot
            ):
                span = target_pivot - protected_pivot
                pos_in_leg = (last_close - protected_pivot) / span
                bull_bos = [b for b in bos_list if b.direction == 'bullish']
                if (
                    bull_bos
                    and last_close < float(bull_bos[-1].break_price)
                    and pos_in_leg >= 0.88
                ):
                    _force_bearish_terminal()
            elif (
                bull_leg is not None
                and hasattr(self, '_leg_choch_still_valid')
                and not self._leg_choch_still_valid(
                    df, bull_leg, bos_list, chochs,
                )
            ):
                _force_bearish_terminal()

        trend = bias if bias is not None else 'neutral'

        leg_choch = _last_leg_choch(trend) if trend in ('bullish', 'bearish') else None
        strategy_type = 'continuation'
        latest_out = latest_signal
        if leg_choch is not None and trend in ('bullish', 'bearish'):
            post_leg_bos = [
                b for b in bos_list
                if b.index > leg_choch.index and b.direction == trend
            ]
            if post_leg_bos:
                strategy_type = 'continuation'
                latest_out = post_leg_bos[-1]
            else:
                strategy_type = 'reversal'
                latest_out = leg_choch
        elif isinstance(latest_signal, CHoCH):
            strategy_type = 'reversal'
            latest_out = latest_signal

        protected_low = None
        protected_high = None
        structural_hh = None
        structural_hl = None
        if bias == 'bullish':
            structural_hl = protected_pivot
            protected_low = protected_pivot
            structural_hh = target_pivot
        elif bias == 'bearish':
            structural_hl = protected_pivot
            protected_high = protected_pivot
            structural_hh = target_pivot

        if debug and trend != 'neutral':
            kind = 'CHoCH' if isinstance(latest_signal, CHoCH) else 'BOS'
            print(
                f"   📐 [V82.1 SMC SM] trend={trend.upper()} "
                f"HL/LH={protected_pivot} HH/LL={target_pivot} last={kind} "
                f"@bar{getattr(latest_signal, 'index', '?')}"
            )

        return {
            'trend': trend,
            'latest_signal': latest_out,
            'strategy_type': strategy_type,
            'leg_choch': leg_choch,
            'chochs': chochs,
            'bos_list': bos_list,
            'protected_low': protected_low,
            'protected_high': protected_high,
            'structural_hh': structural_hh,
            'structural_hl': structural_hl,
        }

    def detect_choch_and_bos(self, df: pd.DataFrame) -> Tuple[List[CHoCH], List[BOS]]:
        """V74: delegate to sequential state machine (body close only)."""
        out = self.run_d1_smc_state_machine(df)
        return out['chochs'], out['bos_list']

    def compute_structural_range(
        self,
        df: pd.DataFrame,
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint],
        symbol: Optional[str] = None,
    ) -> Optional[StructuralRangeState]:
        """Macro range from major LH/LL bodies (V74: no crypto ceiling / asset overrides)."""
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

        del symbol
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
