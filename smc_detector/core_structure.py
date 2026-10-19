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
        return df.iloc[:-1].copy()

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
        V81 — Structural leg HH/HL (TradingView circles logic).
        Bullish leg: HL = fractal low at impulse origin of the BOS leg (never ratchets UP).
        Trend stays bullish until a daily body close is below HL; pullbacks inside HL–HH
        must not emit bearish BOS/CHoCH. Bearish leg is symmetric (LH never ratchets DOWN).
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
        fw = self._swing_fractal_window(df)
        swing_low_indices = {l.index for l in swing_lows}
        swing_high_indices = {h.index for h in swing_highs}
        major_high_indices = {h.index for h in major_highs}
        major_low_indices = {l.index for l in major_lows}

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

        def set_protected_low_from_origin(start_idx: int, end_idx: int) -> bool:
            nonlocal protected_low_idx
            origin = self._impulse_origin_low_between(
                df, swing_lows, start_idx, end_idx,
            )
            if origin is None:
                return False
            protected_low_idx = origin.index
            return True

        def set_protected_high_from_origin(start_idx: int, end_idx: int) -> bool:
            nonlocal protected_high_idx
            origin = self._impulse_origin_high_between(
                df, swing_highs, start_idx, end_idx,
            )
            if origin is None:
                return False
            protected_high_idx = origin.index
            return True

        chochs: List[CHoCH] = []
        bos_list: List[BOS] = []
        state: Optional[str] = None
        ref_high = bh(df, 0)
        ref_low = bl(df, 0)
        protected_low_idx = 0
        protected_high_idx = 0
        macro_protected_low_idx = 0
        macro_protected_high_idx = 0
        structure_high_idx: Optional[int] = None
        structure_low_idx: Optional[int] = None
        leg_invalidation_low_idx = 0
        leg_invalidation_high_idx = 0
        structural_hl_idx = 0
        structural_lh_idx = 0
        structural_hh_idx: Optional[int] = None
        structural_ll_idx: Optional[int] = None
        last_bos_bar = 0
        last_state_flip_bar = 0
        latest_signal = None
        leg_choch = None
        MIN_CHOCH_COOLDOWN_BARS = 5

        def hl_body(idx: int) -> float:
            if idx in swing_low_indices:
                return bl(df, idx)
            return float('inf')

        def lh_body(idx: int) -> float:
            if idx in swing_high_indices:
                return bh(df, idx)
            return float('-inf')

        def lock_structural_hl(idx: int) -> None:
            nonlocal structural_hl_idx, leg_invalidation_low_idx, protected_low_idx
            if idx not in swing_low_indices:
                return
            if structural_hl_idx not in swing_low_indices:
                structural_hl_idx = idx
            elif hl_body(idx) < hl_body(structural_hl_idx):
                structural_hl_idx = idx
            leg_invalidation_low_idx = structural_hl_idx
            protected_low_idx = structural_hl_idx

        def lock_structural_lh(idx: int) -> None:
            nonlocal structural_lh_idx, leg_invalidation_high_idx, protected_high_idx
            if idx not in swing_high_indices:
                return
            if structural_lh_idx not in swing_high_indices:
                structural_lh_idx = idx
            elif lh_body(idx) > lh_body(structural_lh_idx):
                structural_lh_idx = idx
            leg_invalidation_high_idx = structural_lh_idx
            protected_high_idx = structural_lh_idx

        def seed_macro_low_for_leg(bar_i: int, break_ref_idx: int) -> None:
            nonlocal macro_protected_low_idx, protected_low_idx
            lows = [l for l in major_lows if l.index <= bar_i]
            if not lows:
                lows = confirmed_lows(bar_i)
            if lows:
                deepest = min(lows, key=lambda l: bl(df, l.index))
                macro_protected_low_idx = deepest.index
                if protected_low_idx not in swing_low_indices:
                    protected_low_idx = macro_protected_low_idx

        def seed_macro_high_for_leg(bar_i: int, break_ref_idx: int) -> None:
            nonlocal macro_protected_high_idx, protected_high_idx
            _ = break_ref_idx
            highs = [h for h in major_highs if h.index <= bar_i]
            if not highs:
                highs = confirmed_highs(bar_i)
            if highs:
                highest = max(highs, key=lambda h: bh(df, h.index))
                macro_protected_high_idx = highest.index
                protected_high_idx = macro_protected_high_idx

        for i in range(1, len(df)):
            close = float(df['close'].iloc[i])
            ct = self._bar_time(df, i)

            if state is None:
                if close > ref_high:
                    br_h = broken_swing_high(i, close)
                    if br_h is None:
                        ref_high = max(ref_high, bh(df, i))
                        ref_low = min(ref_low, bl(df, i))
                        continue
                    state = 'bullish'
                    last_bos_bar = i
                    structure_high_idx = None
                    if not set_protected_low_from_origin(0, i):
                        lows = confirmed_lows(i)
                        if lows:
                            deepest = min(lows, key=lambda l: bl(df, l.index))
                            protected_low_idx = deepest.index
                    lock_structural_hl(protected_low_idx)
                    seed_macro_low_for_leg(i, br_h.index)
                    structural_hh_idx = br_h.index
                    last_state_flip_bar = i
                    broken = br_h
                    ev = CHoCH(
                        index=i,
                        direction='bullish',
                        break_price=bh(df, broken.index),
                        previous_trend=None,
                        candle_time=ct,
                        swing_broken=broken,
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
                    state = 'bearish'
                    last_bos_bar = i
                    structure_low_idx = None
                    if not set_protected_high_from_origin(0, i):
                        highs = confirmed_highs(i)
                        if highs:
                            highest = max(highs, key=lambda h: bh(df, h.index))
                            protected_high_idx = highest.index
                    lock_structural_lh(protected_high_idx)
                    seed_macro_high_for_leg(i, br_l.index)
                    structural_ll_idx = br_l.index
                    last_state_flip_bar = i
                    broken = br_l
                    ev = CHoCH(
                        index=i,
                        direction='bearish',
                        break_price=bl(df, broken.index),
                        previous_trend=None,
                        candle_time=ct,
                        swing_broken=broken,
                    )
                    chochs.append(ev)
                    latest_signal = ev
                    leg_choch = ev
                else:
                    ref_high = max(ref_high, bh(df, i))
                    ref_low = min(ref_low, bl(df, i))
                continue

            if state == 'bullish':
                if (
                    i > last_state_flip_bar + MIN_CHOCH_COOLDOWN_BARS
                    and structural_hl_idx in swing_low_indices
                    and close < bl(df, structural_hl_idx)
                ):
                    pl_idx = structural_hl_idx
                    seed_macro_high_for_leg(i, pl_idx)
                    lock_structural_lh(macro_protected_high_idx)
                    structural_ll_idx = pl_idx
                    last_state_flip_bar = i
                    broken = swing_pt(pl_idx, 'low')
                    ev = CHoCH(
                        index=i,
                        direction='bearish',
                        break_price=bl(df, pl_idx),
                        previous_trend='bullish',
                        candle_time=ct,
                        swing_broken=broken,
                    )
                    chochs.append(ev)
                    latest_signal = ev
                    leg_choch = ev
                    state = 'bearish'
                    last_bos_bar = i
                    structure_low_idx = None
                    continue

                post_highs = [
                    h for h in major_highs
                    if h.index > last_bos_bar and h.index + fw <= i
                ]
                if not post_highs:
                    post_highs = [
                        h for h in swing_highs
                        if h.index > last_bos_bar and h.index + fw <= i
                    ]
                if post_highs:
                    structure_high_idx = max(post_highs, key=lambda h: h.index).index

                if (
                    structure_high_idx is not None
                    and structure_high_idx in swing_high_indices
                    and close > bh(df, structure_high_idx)
                ):
                    broken_idx = structure_high_idx
                    origin = self._impulse_origin_low_between(
                        df, swing_lows, broken_idx, i,
                    )
                    if origin is not None:
                        lock_structural_hl(origin.index)
                        if origin.index in major_low_indices:
                            macro_protected_low_idx = origin.index
                    elif set_protected_low_from_origin(broken_idx, i):
                        lock_structural_hl(protected_low_idx)
                        if protected_low_idx in major_low_indices:
                            macro_protected_low_idx = protected_low_idx
                    structural_hh_idx = broken_idx
                    broken = swing_pt(broken_idx, 'high')
                    ev = BOS(
                        index=i,
                        direction='bullish',
                        break_price=bh(df, broken_idx),
                        candle_time=ct,
                        swing_broken=broken,
                    )
                    bos_list.append(ev)
                    latest_signal = ev
                    last_bos_bar = i
                    structure_high_idx = None
                continue

            if state == 'bearish':
                if (
                    i > last_state_flip_bar + MIN_CHOCH_COOLDOWN_BARS
                    and structural_lh_idx in swing_high_indices
                    and close > bh(df, structural_lh_idx)
                ):
                    ph_idx = structural_lh_idx
                    seed_macro_low_for_leg(i, ph_idx)
                    lock_structural_hl(macro_protected_low_idx)
                    structural_hh_idx = ph_idx
                    last_state_flip_bar = i
                    broken = swing_pt(ph_idx, 'high')
                    ev = CHoCH(
                        index=i,
                        direction='bullish',
                        break_price=bh(df, ph_idx),
                        previous_trend='bearish',
                        candle_time=ct,
                        swing_broken=broken,
                    )
                    chochs.append(ev)
                    latest_signal = ev
                    leg_choch = ev
                    state = 'bullish'
                    last_bos_bar = i
                    structure_high_idx = None
                    continue

                post_lows = [
                    l for l in major_lows
                    if l.index > last_bos_bar and l.index + fw <= i
                ]
                if not post_lows:
                    post_lows = [
                        l for l in swing_lows
                        if l.index > last_bos_bar and l.index + fw <= i
                    ]
                if post_lows:
                    structure_low_idx = max(post_lows, key=lambda l: l.index).index

                if (
                    structure_low_idx is not None
                    and structure_low_idx in swing_low_indices
                    and close < bl(df, structure_low_idx)
                ):
                    broken_idx = structure_low_idx
                    origin_h = self._impulse_origin_high_between(
                        df, swing_highs, broken_idx, i,
                    )
                    if origin_h is not None:
                        lock_structural_lh(origin_h.index)
                    else:
                        set_protected_high_from_origin(broken_idx, i)
                        lock_structural_lh(protected_high_idx)
                    structural_ll_idx = broken_idx
                    broken = swing_pt(broken_idx, 'low')
                    ev = BOS(
                        index=i,
                        direction='bearish',
                        break_price=bl(df, broken_idx),
                        candle_time=ct,
                        swing_broken=broken,
                    )
                    bos_list.append(ev)
                    latest_signal = ev
                    last_bos_bar = i
                    structure_low_idx = None

        trend = state if state is not None else 'neutral'

        strategy_type = 'continuation'
        if latest_signal is not None and isinstance(latest_signal, CHoCH):
            pt = getattr(latest_signal, 'previous_trend', None)
            if pt and pt != latest_signal.direction:
                strategy_type = 'reversal'
            elif pt is None:
                strategy_type = 'reversal'

        protected_low = None
        protected_high = None
        structural_hh = None
        structural_hl = None
        if state == 'bullish':
            if structural_hl_idx in swing_low_indices:
                structural_hl = float(bl(df, structural_hl_idx))
                protected_low = structural_hl
            if structural_hh_idx is not None and structural_hh_idx in swing_high_indices:
                structural_hh = float(bh(df, structural_hh_idx))
        elif state == 'bearish':
            if structural_lh_idx in swing_high_indices:
                structural_hl = float(bh(df, structural_lh_idx))
                protected_high = structural_hl
            if structural_ll_idx is not None and structural_ll_idx in swing_low_indices:
                structural_hh = float(bl(df, structural_ll_idx))

        if debug and trend != 'neutral':
            kind = 'CHoCH' if isinstance(latest_signal, CHoCH) else 'BOS'
            print(
                f"   📐 [V81 SMC SM] trend={trend.upper()} last={kind} "
                f"@bar{getattr(latest_signal, 'index', '?')}"
            )

        return {
            'trend': trend,
            'latest_signal': latest_signal,
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
