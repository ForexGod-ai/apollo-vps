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
        V75 — Sequential Glitch SMC on live D1 series (caller passes closed bars only).
        Body-close vs active_high / protected_low (bull) or active_low / protected_high (bear).
        No crypto ceilings, ATR displacement, or bias fallback overrides.
        """
        empty = {
            'trend': 'neutral',
            'latest_signal': None,
            'strategy_type': 'continuation',
            'leg_choch': None,
            'chochs': [],
            'bos_list': [],
        }
        if df is None or len(df) < 2:
            return empty

        bh = self._swing_body_high
        bl = self._swing_body_low

        def wick_hi(i: int) -> float:
            return float(df['high'].iloc[i])

        def wick_lo(i: int) -> float:
            return float(df['low'].iloc[i])

        def swing_pt(i: int, st: str) -> SwingPoint:
            price = wick_hi(i) if st == 'high' else wick_lo(i)
            return SwingPoint(
                index=i,
                price=price,
                swing_type=st,
                candle_time=self._bar_time(df, i),
            )

        chochs: List[CHoCH] = []
        bos_list: List[BOS] = []
        state: Optional[str] = None
        ref_high = bh(df, 0)
        ref_low = bl(df, 0)
        active_high_idx = 0
        protected_low_idx = 0
        active_low_idx = 0
        protected_high_idx = 0
        last_bos_bar = 0
        latest_signal = None
        leg_choch = None

        for i in range(1, len(df)):
            close = float(df['close'].iloc[i])
            ct = self._bar_time(df, i)

            if state is None:
                if close > ref_high:
                    state = 'bullish'
                    last_bos_bar = i
                    lo_idx = 0
                    for j in range(0, i + 1):
                        if wick_lo(j) <= wick_lo(lo_idx):
                            lo_idx = j
                    protected_low_idx = lo_idx
                    hi_idx = i
                    for j in range(0, i + 1):
                        if wick_hi(j) >= wick_hi(hi_idx):
                            hi_idx = j
                    active_high_idx = hi_idx
                    broken = swing_pt(active_high_idx, 'high')
                    ev = CHoCH(
                        index=i,
                        direction='bullish',
                        break_price=bh(df, active_high_idx),
                        previous_trend=None,
                        candle_time=ct,
                        swing_broken=broken,
                    )
                    chochs.append(ev)
                    latest_signal = ev
                    leg_choch = ev
                elif close < ref_low:
                    state = 'bearish'
                    last_bos_bar = i
                    hi_idx = 0
                    for j in range(0, i + 1):
                        if wick_hi(j) >= wick_hi(hi_idx):
                            hi_idx = j
                    protected_high_idx = hi_idx
                    lo_idx = i
                    for j in range(0, i + 1):
                        if wick_lo(j) <= wick_lo(lo_idx):
                            lo_idx = j
                    active_low_idx = lo_idx
                    protected_low_idx = lo_idx
                    broken = swing_pt(active_low_idx, 'low')
                    ev = CHoCH(
                        index=i,
                        direction='bearish',
                        break_price=bl(df, active_low_idx),
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
                if close < bl(df, protected_low_idx):
                    seg_start = max(0, last_bos_bar)
                    hi_idx = seg_start
                    for j in range(seg_start, i + 1):
                        if wick_hi(j) >= wick_hi(hi_idx):
                            hi_idx = j
                    protected_high_idx = hi_idx
                    lo_idx = i
                    for j in range(seg_start, i + 1):
                        if wick_lo(j) <= wick_lo(lo_idx):
                            lo_idx = j
                    active_low_idx = lo_idx
                    broken = swing_pt(protected_low_idx, 'low')
                    ev = CHoCH(
                        index=i,
                        direction='bearish',
                        break_price=bl(df, protected_low_idx),
                        previous_trend='bullish',
                        candle_time=ct,
                        swing_broken=broken,
                    )
                    chochs.append(ev)
                    latest_signal = ev
                    leg_choch = ev
                    state = 'bearish'
                    last_bos_bar = i
                    continue

                if close > bh(df, active_high_idx):
                    seg_start = max(0, last_bos_bar)
                    lo_idx = protected_low_idx
                    for j in range(seg_start, i + 1):
                        if wick_lo(j) <= wick_lo(lo_idx):
                            lo_idx = j
                    protected_low_idx = lo_idx
                    hi_idx = i
                    for j in range(seg_start, i + 1):
                        if wick_hi(j) >= wick_hi(hi_idx):
                            hi_idx = j
                    active_high_idx = hi_idx
                    broken = swing_pt(active_high_idx, 'high')
                    ev = BOS(
                        index=i,
                        direction='bullish',
                        break_price=bh(df, active_high_idx),
                        candle_time=ct,
                        swing_broken=broken,
                    )
                    bos_list.append(ev)
                    latest_signal = ev
                    last_bos_bar = i
                continue

            if state == 'bearish':
                if close > bh(df, protected_high_idx):
                    seg_start = max(0, last_bos_bar)
                    lo_idx = i
                    for j in range(seg_start, i + 1):
                        if wick_lo(j) <= wick_lo(lo_idx):
                            lo_idx = j
                    protected_low_idx = lo_idx
                    hi_idx = seg_start
                    for j in range(seg_start, i + 1):
                        if wick_hi(j) >= wick_hi(hi_idx):
                            hi_idx = j
                    active_high_idx = hi_idx
                    broken = swing_pt(protected_high_idx, 'high')
                    ev = CHoCH(
                        index=i,
                        direction='bullish',
                        break_price=bh(df, protected_high_idx),
                        previous_trend='bearish',
                        candle_time=ct,
                        swing_broken=broken,
                    )
                    chochs.append(ev)
                    latest_signal = ev
                    leg_choch = ev
                    state = 'bullish'
                    last_bos_bar = i
                    continue

                if close < bl(df, active_low_idx):
                    seg_start = max(0, last_bos_bar)
                    hi_idx = protected_high_idx
                    for j in range(seg_start, i + 1):
                        if wick_hi(j) >= wick_hi(hi_idx):
                            hi_idx = j
                    protected_high_idx = hi_idx
                    lo_idx = i
                    for j in range(seg_start, i + 1):
                        if wick_lo(j) <= wick_lo(lo_idx):
                            lo_idx = j
                    active_low_idx = lo_idx
                    broken = swing_pt(active_low_idx, 'low')
                    ev = BOS(
                        index=i,
                        direction='bearish',
                        break_price=bl(df, active_low_idx),
                        candle_time=ct,
                        swing_broken=broken,
                    )
                    bos_list.append(ev)
                    latest_signal = ev
                    last_bos_bar = i

        trend = state if state is not None else 'neutral'

        strategy_type = 'continuation'
        if latest_signal is not None and isinstance(latest_signal, CHoCH):
            pt = getattr(latest_signal, 'previous_trend', None)
            if pt and pt != latest_signal.direction:
                strategy_type = 'reversal'
            elif pt is None:
                strategy_type = 'reversal'

        if debug and trend != 'neutral':
            kind = 'CHoCH' if isinstance(latest_signal, CHoCH) else 'BOS'
            print(
                f"   📐 [V74 SMC SM] trend={trend.upper()} last={kind} "
                f"@bar{getattr(latest_signal, 'index', '?')}"
            )

        return {
            'trend': trend,
            'latest_signal': latest_signal,
            'strategy_type': strategy_type,
            'leg_choch': leg_choch,
            'chochs': chochs,
            'bos_list': bos_list,
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
