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
        V93 — D1 SMC: body-only + major chain bootstrap + target_armed impulse guard.

        No bar-0 fallback; leg anchors on first confirmed L→H or H→L major pair.
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
            'protected_idx': None,
            'target_idx': None,
            'is_internal_pullback': False,
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

        def swing_pt(i: int, st: str) -> SwingPoint:
            for h in swing_highs:
                if st == 'high' and h.index == i:
                    return h
            for l in swing_lows:
                if st == 'low' and l.index == i:
                    return l
            price = float(bh(df, i) if st == 'high' else bl(df, i))
            return SwingPoint(
                index=i,
                price=price,
                swing_type=st,
                candle_time=self._bar_time(df, i),
            )

        def _min_body_low_between(start_idx: int, end_idx: int) -> Tuple[int, float]:
            start_idx = max(0, int(start_idx))
            end_idx = min(int(end_idx), len(df) - 1)
            best_i = start_idx
            best_v = bl(df, start_idx)
            for j in range(start_idx, end_idx + 1):
                v = bl(df, j)
                if v < best_v:
                    best_v = v
                    best_i = j
            return best_i, float(best_v)

        def _max_body_high_between(start_idx: int, end_idx: int) -> Tuple[int, float]:
            start_idx = max(0, int(start_idx))
            end_idx = min(int(end_idx), len(df) - 1)
            best_i = start_idx
            best_v = bh(df, start_idx)
            for j in range(start_idx, end_idx + 1):
                v = bh(df, j)
                if v > best_v:
                    best_v = v
                    best_i = j
            return best_i, float(best_v)

        def _alternating_major_chain() -> List[Tuple[str, int, float, SwingPoint]]:
            events: List[Tuple[str, int, float, SwingPoint]] = []
            for l in major_lows:
                events.append(('L', l.index, float(bl(df, l.index)), l))
            for h in major_highs:
                events.append(('H', h.index, float(bh(df, h.index)), h))
            events.sort(key=lambda x: x[1])
            chain: List[Tuple[str, int, float, SwingPoint]] = []
            for typ, idx, px, sp in events:
                if not chain:
                    chain.append((typ, idx, px, sp))
                    continue
                last_typ, last_idx, last_px, _last_sp = chain[-1]
                if typ == last_typ:
                    if typ == 'L' and px < last_px:
                        chain[-1] = (typ, idx, px, sp)
                    elif typ == 'H' and px > last_px:
                        chain[-1] = (typ, idx, px, sp)
                else:
                    chain.append((typ, idx, px, sp))
            return chain

        chain = _alternating_major_chain()
        if len(chain) < 2:
            return empty

        p0, p1 = chain[0], chain[1]
        if p0[0] == 'L' and p1[0] == 'H':
            bias = 'bullish'
            protected_idx, protected_pivot = p0[1], p0[2]
            target_idx, target_pivot = p1[1], p1[2]
        elif p0[0] == 'H' and p1[0] == 'L':
            bias = 'bearish'
            protected_idx, protected_pivot = p0[1], p0[2]
            target_idx, target_pivot = p1[1], p1[2]
        else:
            return empty

        chochs: List[CHoCH] = []
        bos_list: List[BOS] = []
        latest_signal = None
        leg_choch = None
        start_i = max(int(protected_idx), int(target_idx)) + 1
        last_event_bar = start_i - 1
        target_armed = True

        def _rearm_target(bar_i: int) -> None:
            nonlocal target_armed
            if target_idx is not None and int(target_idx) + fw <= bar_i:
                target_armed = True

        for i in range(start_i, len(df)):
            close = float(df['close'].iloc[i])
            ct = self._bar_time(df, i)
            event_at_bar = False

            lo_p = float(protected_pivot)
            hi_p = float(target_pivot)

            if bias == 'bullish' and lo_p <= close <= hi_p:
                _rearm_target(i)
                if not target_armed:
                    body_h = float(bh(df, i))
                    if body_h > float(target_pivot):
                        target_idx = i
                        target_pivot = body_h
                continue
            if bias == 'bearish' and hi_p >= close >= lo_p:
                _rearm_target(i)
                if not target_armed:
                    body_l = float(bl(df, i))
                    if body_l < float(target_pivot):
                        target_idx = i
                        target_pivot = body_l
                continue

            if not target_armed:
                _rearm_target(i)

            if (
                bias == 'bullish'
                and i > last_event_bar
                and close < protected_pivot - 1e-12
            ):
                old_prot = int(protected_idx)
                old_tgt = int(target_idx)
                win_lo = min(old_prot, old_tgt)
                lh_idx, lh_px = _max_body_high_between(win_lo, i)
                ll_idx = i
                ll_px = float(bl(df, i))
                bias = 'bearish'
                protected_idx, protected_pivot = lh_idx, lh_px
                target_idx, target_pivot = ll_idx, ll_px
                last_event_bar = i
                event_at_bar = True
                target_armed = False
                broken = swing_pt(old_prot, 'low')
                ev = CHoCH(
                    index=i,
                    direction='bearish',
                    break_price=lo_p,
                    previous_trend='bullish',
                    candle_time=ct,
                    swing_broken=broken,
                )
                chochs.append(ev)
                latest_signal = ev
                leg_choch = ev

            elif (
                bias == 'bearish'
                and i > last_event_bar
                and close > protected_pivot + 1e-12
            ):
                old_prot = int(protected_idx)
                old_tgt = int(target_idx)
                win_lo = min(old_prot, old_tgt)
                hl_idx, hl_px = _min_body_low_between(win_lo, i)
                hh_idx = i
                hh_px = float(bh(df, i))
                bias = 'bullish'
                protected_idx, protected_pivot = hl_idx, hl_px
                target_idx, target_pivot = hh_idx, hh_px
                last_event_bar = i
                event_at_bar = True
                target_armed = False
                broken = swing_pt(old_prot, 'high')
                ev = CHoCH(
                    index=i,
                    direction='bullish',
                    break_price=hi_p,
                    previous_trend='bearish',
                    candle_time=ct,
                    swing_broken=broken,
                )
                chochs.append(ev)
                latest_signal = ev
                leg_choch = ev

            elif (
                bias == 'bullish'
                and target_armed
                and i > last_event_bar
                and close > target_pivot + 1e-12
                and target_idx is not None
            ):
                old_target_idx = int(target_idx)
                hl_idx, hl_px = _min_body_low_between(old_target_idx, i)
                hh_idx, hh_px = _max_body_high_between(old_target_idx + 1, i)
                protected_idx, protected_pivot = hl_idx, hl_px
                target_idx, target_pivot = hh_idx, hh_px
                last_event_bar = i
                event_at_bar = True
                target_armed = False
                br_h = swing_pt(old_target_idx, 'high')
                ev = BOS(
                    index=i,
                    direction='bullish',
                    break_price=hh_px,
                    candle_time=ct,
                    swing_broken=br_h,
                )
                bos_list.append(ev)
                latest_signal = ev

            elif (
                bias == 'bearish'
                and target_armed
                and i > last_event_bar
                and close < target_pivot - 1e-12
                and target_idx is not None
            ):
                old_target_idx = int(target_idx)
                lh_idx, lh_px = _max_body_high_between(old_target_idx, i)
                ll_idx, ll_px = _min_body_low_between(old_target_idx + 1, i)
                protected_idx, protected_pivot = lh_idx, lh_px
                target_idx, target_pivot = ll_idx, ll_px
                last_event_bar = i
                event_at_bar = True
                target_armed = False
                br_l = swing_pt(old_target_idx, 'low')
                ev = BOS(
                    index=i,
                    direction='bearish',
                    break_price=ll_px,
                    candle_time=ct,
                    swing_broken=br_l,
                )
                bos_list.append(ev)
                latest_signal = ev

            elif not target_armed and not event_at_bar:
                if bias == 'bullish':
                    body_h = float(bh(df, i))
                    if body_h > float(target_pivot):
                        target_idx = i
                        target_pivot = body_h
                elif bias == 'bearish':
                    body_l = float(bl(df, i))
                    if body_l < float(target_pivot):
                        target_idx = i
                        target_pivot = body_l

            if event_at_bar or protected_idx is None:
                continue

            if not target_armed:
                continue

            prot_i = int(protected_idx)
            if bias == 'bullish':
                best_h: Optional[SwingPoint] = None
                best_px = float(target_pivot)
                for h in major_highs:
                    if h.index + fw > i or h.index <= prot_i:
                        continue
                    px = float(bh(df, h.index))
                    if px > best_px + 1e-12:
                        best_px = px
                        best_h = h
                if best_h is not None:
                    target_idx = best_h.index
                    target_pivot = best_px
            elif bias == 'bearish':
                best_l: Optional[SwingPoint] = None
                best_px = float(target_pivot)
                for l in major_lows:
                    if l.index + fw > i or l.index <= prot_i:
                        continue
                    px = float(bl(df, l.index))
                    if px < best_px - 1e-12:
                        best_px = px
                        best_l = l
                if best_l is not None:
                    target_idx = best_l.index
                    target_pivot = best_px

        trend = bias if bias is not None else 'neutral'

        latest_flip_idx = -1
        for c in reversed(chochs):
            pt = getattr(c, 'previous_trend', None)
            if pt and pt != c.direction:
                latest_flip_idx = int(c.index)
                break
        strategy_type = 'reversal'
        if trend in ('bullish', 'bearish'):
            post_leg_bos = [
                b for b in bos_list
                if getattr(b, 'direction', '') == trend
                and int(b.index) > latest_flip_idx
            ]
            if (
                post_leg_bos
                and isinstance(latest_signal, BOS)
                and int(latest_signal.index) == int(post_leg_bos[-1].index)
            ):
                strategy_type = 'continuation'
            elif latest_flip_idx < 0 and isinstance(latest_signal, BOS):
                strategy_type = 'continuation'

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

        is_internal_pullback = False
        if (
            bias in ('bullish', 'bearish')
            and protected_pivot is not None
            and target_pivot is not None
            and len(df) > 0
        ):
            last_close = float(df['close'].iloc[-1])
            if bias == 'bullish':
                is_internal_pullback = (
                    float(protected_pivot) <= last_close <= float(target_pivot)
                )
            else:
                is_internal_pullback = (
                    float(target_pivot) <= last_close <= float(protected_pivot)
                )

        if debug and trend != 'neutral':
            kind = (
                'CHoCH' if isinstance(latest_signal, CHoCH)
                else 'BOS' if isinstance(latest_signal, BOS)
                else '—'
            )
            print(
                f"   📐 [V93 SMC SM] trend={trend.upper()} "
                f"HL/LH={protected_pivot} HH/LL={target_pivot} last={kind} "
                f"@bar{getattr(latest_signal, 'index', '?')} "
                f"internal_pb={is_internal_pullback}"
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
            'protected_idx': protected_idx,
            'target_idx': target_idx,
            'is_internal_pullback': is_internal_pullback,
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
