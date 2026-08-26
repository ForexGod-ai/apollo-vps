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


class D1LegMixin:
    """V67 C: D1 leg resolution helpers."""

    def _protected_hl_level_after_leg(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
    ) -> Optional[float]:
        """Ultimul HL (body low) format după leg bullish — podea structurală."""
        if leg_choch is None or leg_choch.direction != 'bullish':
            return None
        swing_lows = self.detect_swing_lows(df)
        post = [l for l in swing_lows if l.index > leg_choch.index]
        if not post:
            return None
        hl = None
        for i in range(1, len(post)):
            if post[i].price > post[i - 1].price:
                hl = post[i]
        if hl is None:
            hl = max(post, key=lambda l: l.price)
        return self._swing_body_low(df, hl.index)

    def _protected_lh_level_after_leg(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
    ) -> Optional[float]:
        """Ultimul LH (body high) format după leg bearish — plafon structural."""
        if leg_choch is None or leg_choch.direction != 'bearish':
            return None
        swing_highs = self.detect_swing_highs(df)
        post = [h for h in swing_highs if h.index > leg_choch.index]
        if not post:
            return None
        lh = None
        for i in range(1, len(post)):
            if post[i].price < post[i - 1].price:
                lh = post[i]
        if lh is None:
            lh = min(post, key=lambda h: h.price)
        return self._swing_body_high(df, lh.index)

    def _leg_origin_major_high(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
    ) -> Optional[float]:
        """Major high before bearish leg — swing_broken if high, else prior major high."""
        if leg_choch is None or leg_choch.direction != 'bearish':
            return None
        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        major_highs, _ = self.filter_major_swings(df, swing_highs, swing_lows)
        broken = getattr(leg_choch, 'swing_broken', None)
        if broken is not None and getattr(broken, 'swing_type', None) == 'high':
            if not major_highs or any(h.index == broken.index for h in major_highs):
                return self._swing_body_high(df, broken.index)
        if broken is not None and getattr(broken, 'swing_type', None) == 'low':
            prior = [h for h in major_highs if h.index < broken.index]
            if prior:
                peak = max(prior, key=lambda h: self._swing_body_high(df, h.index))
                return self._swing_body_high(df, peak.index)
        prior = [h for h in major_highs if h.index < leg_choch.index]
        if prior:
            return self._swing_body_high(df, prior[-1].index)
        prior_geo = [h for h in swing_highs if h.index < leg_choch.index]
        if prior_geo:
            return self._swing_body_high(df, prior_geo[-1].index)
        return None

    def _leg_origin_major_low(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
    ) -> Optional[float]:
        """Major low before bullish leg — swing_broken if low, else prior major low."""
        if leg_choch is None or leg_choch.direction != 'bullish':
            return None
        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        _, major_lows = self.filter_major_swings(df, swing_highs, swing_lows)
        broken = getattr(leg_choch, 'swing_broken', None)
        if broken is not None and getattr(broken, 'swing_type', None) == 'low':
            if not major_lows or any(l.index == broken.index for l in major_lows):
                return self._swing_body_low(df, broken.index)
        if broken is not None and getattr(broken, 'swing_type', None) == 'high':
            prior = [l for l in major_lows if l.index < broken.index]
            if prior:
                trough = min(prior, key=lambda l: self._swing_body_low(df, l.index))
                return self._swing_body_low(df, trough.index)
        prior = [l for l in major_lows if l.index < leg_choch.index]
        if prior:
            return self._swing_body_low(df, prior[-1].index)
        prior_geo = [l for l in swing_lows if l.index < leg_choch.index]
        if prior_geo:
            return self._swing_body_low(df, prior_geo[-1].index)
        return None

    def _body_reclaimed_origin_high(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        major_highs: Optional[List] = None,
        major_lows: Optional[List] = None,
    ) -> bool:
        """Rule 2: bearish leg flips bullish ONLY on body-close above Major LH."""
        if df is None or len(df) == 0 or leg_choch is None:
            return False
        if major_highs is None or major_lows is None:
            swing_highs = self.detect_swing_highs(df)
            swing_lows = self.detect_swing_lows(df)
            major_highs, major_lows = self.filter_major_swings(
                df, swing_highs, swing_lows,
            )
        lh = self._leg_invalidation_level_bearish(
            df, leg_choch, major_highs, major_lows, len(df) - 1,
        )
        if lh is None:
            return False
        return self._bar_body_close_above(df, len(df) - 1, lh)

    def _body_reclaimed_origin_low(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        major_highs: Optional[List] = None,
        major_lows: Optional[List] = None,
    ) -> bool:
        """Rule 2: bullish leg flips bearish ONLY on body-close below Major HL."""
        if df is None or len(df) == 0 or leg_choch is None:
            return False
        if major_highs is None or major_lows is None:
            swing_highs = self.detect_swing_highs(df)
            swing_lows = self.detect_swing_lows(df)
            major_highs, major_lows = self.filter_major_swings(
                df, swing_highs, swing_lows,
            )
        hl = self._leg_invalidation_level_bullish(
            df, leg_choch, major_highs, major_lows, len(df) - 1,
        )
        if hl is None:
            return False
        return self._bar_body_close_below(df, len(df) - 1, hl)

    def _active_leg_boundary(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        major_highs: List,
        major_lows: List,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Return (floor, ceiling) body levels bounding the active leg range."""
        if leg_choch is None:
            return None, None
        if leg_choch.direction == 'bearish':
            ceiling = self._leg_invalidation_level_bearish(
                df, leg_choch, major_highs, major_lows, len(df) - 1,
            )
            ml = [l for l in major_lows if l.index <= len(df) - 1]
            floor = self._swing_body_low(df, ml[-1].index) if ml else None
            return floor, ceiling
        floor = self._leg_invalidation_level_bullish(
            df, leg_choch, major_highs, major_lows, len(df) - 1,
        )
        highs_after = [h for h in major_highs if h.index >= leg_choch.index]
        ceiling = None
        if highs_after:
            peak = max(highs_after, key=lambda h: h.price)
            ceiling = self._swing_body_high(df, peak.index)
        return floor, ceiling

    def _close_inside_active_leg_boundary(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        major_highs: List,
        major_lows: List,
        bar_idx: Optional[int] = None,
    ) -> bool:
        """True when close sits inside [Major Low, Major High] of the active leg."""
        if df is None or len(df) == 0 or leg_choch is None:
            return False
        bar_idx = len(df) - 1 if bar_idx is None else bar_idx
        floor, ceiling = self._active_leg_boundary(
            df, leg_choch, major_highs, major_lows,
        )
        if floor is None or ceiling is None:
            return False
        close = float(df['close'].iloc[bar_idx])
        lo, hi = min(floor, ceiling), max(floor, ceiling)
        return lo <= close <= hi

    def _coerce_leg_with_boundary_gate(
        self,
        df: pd.DataFrame,
        leg_choch: Optional[CHoCH],
        flips: List[CHoCH],
        major_highs: List,
        major_lows: List,
    ) -> Optional[CHoCH]:
        """
        V68 Pilon 1: retrace inside leg range without origin reclaim → keep prior leg.
        Bullish CHoCH inside bearish crash range without MH body-close = pullback (stay SHORT).
        """
        if leg_choch is None:
            return leg_choch
        if leg_choch.direction == 'bullish':
            bears = [
                f for f in flips
                if f.direction == 'bearish' and f.index < leg_choch.index
            ]
            if not bears:
                return leg_choch
            last_bear = bears[-1]
            lh = self._leg_invalidation_level_bearish(
                df, last_bear, major_highs, major_lows, len(df) - 1,
            )
            _close = float(df['close'].iloc[-1])
            if (
                lh is not None
                and _close <= lh
                and not self._body_reclaimed_origin_high(
                    df, last_bear, major_highs, major_lows,
                )
            ):
                return last_bear
        if leg_choch.direction == 'bearish':
            lh = self._leg_invalidation_level_bearish(
                df, leg_choch, major_highs, major_lows, len(df) - 1,
            )
            _close = float(df['close'].iloc[-1])
            if lh is not None and _close <= lh:
                return leg_choch
            bulls = [
                f for f in flips
                if f.direction == 'bullish' and f.index < leg_choch.index
            ]
            if bulls:
                last_bull = bulls[-1]
                hl = self._leg_invalidation_level_bullish(
                    df, last_bull, major_highs, major_lows, len(df) - 1,
                )
                _close = float(df['close'].iloc[-1])
                if (
                    hl is not None
                    and _close >= hl
                    and not self._body_reclaimed_origin_low(
                        df, last_bull, major_highs, major_lows,
                    )
                ):
                    return last_bull
        return leg_choch

    def _macro_tiebreak_bos_direction(
        self,
        df: pd.DataFrame,
        bos_list: List,
        last: BOS,
        major_highs: List,
        major_lows: List,
    ) -> Tuple[BOS, str]:
        """When last BOS is a pullback against macro HH+HL / LH+LL, macro trend wins."""
        macro = self.macro_trend_from_swings(df)
        if macro not in ('bullish', 'bearish'):
            return last, last.direction
        if last.direction == macro:
            return last, macro
        aligned = [b for b in bos_list if b.direction == macro]
        if aligned:
            return aligned[-1], macro
        return last, macro

    def _latest_major_high_body(
        self,
        df: pd.DataFrame,
        major_highs: List,
        bar_idx: int,
    ) -> Optional[float]:
        prior = [h for h in major_highs if h.index <= bar_idx]
        if not prior:
            return None
        return self._swing_body_high(df, prior[-1].index)

    def _latest_major_low_body(
        self,
        df: pd.DataFrame,
        major_lows: List,
        bar_idx: int,
    ) -> Optional[float]:
        prior = [l for l in major_lows if l.index <= bar_idx]
        if not prior:
            return None
        return self._swing_body_low(df, prior[-1].index)

    def _flip_threshold_for_bearish_leg(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        major_highs: List,
        major_lows: List,
        bar_idx: int,
    ) -> Optional[float]:
        """Major LH body at bar — bearish→bullish flip boundary."""
        return self._leg_invalidation_level_bearish(
            df, leg_choch, major_highs, major_lows, bar_idx,
        )

    def _flip_threshold_for_bullish_leg(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        major_highs: List,
        major_lows: List,
        bar_idx: int,
    ) -> Optional[float]:
        """Major HL body at bar — bullish→bearish flip boundary."""
        return self._leg_invalidation_level_bullish(
            df, leg_choch, major_highs, major_lows, bar_idx,
        )

    def _leg_invalidation_level_bearish(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        major_highs: List,
        major_lows: List,
        bar_idx: int,
    ) -> Optional[float]:
        """Bearish range ceiling — Major LH body before/at last Major LL at bar."""
        mh = [h for h in major_highs if h.index <= bar_idx]
        ml = [l for l in major_lows if l.index <= bar_idx]
        if ml:
            last_low = ml[-1]
            swing_highs = self.detect_swing_highs(df)
            pullback_highs = [
                h for h in swing_highs
                if last_low.index < h.index <= bar_idx
            ]
            if pullback_highs:
                peak = max(
                    pullback_highs,
                    key=lambda h: self._swing_body_high(df, h.index),
                )
                return self._swing_body_high(df, peak.index)
            highs_before = [h for h in mh if h.index < last_low.index]
            if len(highs_before) >= 2:
                for i in range(len(highs_before) - 1, 0, -1):
                    if highs_before[i].price < highs_before[i - 1].price:
                        return self._swing_body_high(df, highs_before[i].index)
            if highs_before:
                return self._swing_body_high(df, highs_before[-1].index)
        return self._leg_origin_major_high(df, leg_choch)

    def _leg_invalidation_level_bullish(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        major_highs: List,
        major_lows: List,
        bar_idx: int,
    ) -> Optional[float]:
        """Bullish range floor — Major HL body before/at last Major HH at bar."""
        mh = [h for h in major_highs if h.index <= bar_idx]
        ml = [l for l in major_lows if l.index <= bar_idx]
        if mh:
            last_high = mh[-1]
            swing_lows = self.detect_swing_lows(df)
            pullback_lows = [
                l for l in swing_lows
                if last_high.index < l.index <= bar_idx
            ]
            if pullback_lows:
                trough = min(
                    pullback_lows,
                    key=lambda l: self._swing_body_low(df, l.index),
                )
                return self._swing_body_low(df, trough.index)
            lows_before = [l for l in ml if l.index < last_high.index]
            if len(lows_before) >= 2:
                for i in range(len(lows_before) - 1, 0, -1):
                    if lows_before[i].price > lows_before[i - 1].price:
                        return self._swing_body_low(df, lows_before[i].index)
            if lows_before:
                return self._swing_body_low(df, lows_before[-1].index)
        return self._leg_origin_major_low(df, leg_choch)

    def _pure_leg_still_valid_at(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        major_highs: List,
        major_lows: List,
        bar_idx: int,
    ) -> bool:
        if leg_choch is None or df is None or len(df) == 0:
            return False
        bar_idx = min(max(int(bar_idx), 0), len(df) - 1)
        if leg_choch.direction == 'bullish':
            protected = self._protected_hl_level_after_leg(df, leg_choch)
            if protected is not None and self._bar_body_close_below(
                df, bar_idx, protected,
            ):
                return False
            threshold = self._leg_invalidation_level_bullish(
                df, leg_choch, major_highs, major_lows, bar_idx,
            )
            if threshold is None:
                return True
            return not self._bar_body_close_below(df, bar_idx, threshold)
        protected = self._protected_lh_level_after_leg(df, leg_choch)
        if protected is not None and self._bar_body_close_above(
            df, bar_idx, protected,
        ):
            return False
        threshold = self._leg_invalidation_level_bearish(
            df, leg_choch, major_highs, major_lows, bar_idx,
        )
        if threshold is None:
            return True
        return not self._bar_body_close_above(df, bar_idx, threshold)

    def _pure_leg_still_valid(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        major_highs: List,
        major_lows: List,
    ) -> bool:
        if leg_choch is None or df is None or len(df) == 0:
            return False
        return self._pure_leg_still_valid_at(
            df, leg_choch, major_highs, major_lows, len(df) - 1,
        )

    @staticmethod
    def _leg_anchor_from_bos(bos: BOS) -> CHoCH:
        prev = 'bullish' if bos.direction == 'bearish' else 'bearish'
        return CHoCH(
            index=bos.index,
            direction=bos.direction,
            break_price=bos.break_price,
            previous_trend=prev,
            candle_time=getattr(bos, 'candle_time', None),
            swing_broken=getattr(bos, 'swing_broken', None),
        )

    def _structural_break_level_for_signal(
        self,
        df: pd.DataFrame,
        signal,
        major_highs: List,
        major_lows: List,
    ) -> Optional[float]:
        """Body-close threshold from the pivot broken by this CHoCH/BOS."""
        broken = getattr(signal, 'swing_broken', None)
        if broken is not None:
            if signal.direction == 'bullish':
                return self._swing_body_high(df, broken.index)
            return self._swing_body_low(df, broken.index)
        if signal.direction == 'bullish':
            prior = [h for h in major_highs if h.index < signal.index]
            if not prior:
                return None
            return self._swing_body_high(df, prior[-1].index)
        prior = [l for l in major_lows if l.index < signal.index]
        if not prior:
            return None
        return self._swing_body_low(df, prior[-1].index)

    def _opposite_flip_confirms_leg_change(
        self,
        df: pd.DataFrame,
        active: CHoCH,
        flip: CHoCH,
        major_highs: List,
        major_lows: List,
    ) -> bool:
        if flip.direction == active.direction:
            return True
        level = self._structural_break_level_for_signal(
            df, flip, major_highs, major_lows,
        )
        if level is None:
            return False
        if flip.direction == 'bullish':
            return self._bar_body_close_above(df, flip.index, level)
        return self._bar_body_close_below(df, flip.index, level)

    def _active_leg_range_boundary_for_flip(
        self,
        df: pd.DataFrame,
        active: BOS,
        major_highs: List,
        major_lows: List,
        bar_idx: int,
    ) -> Optional[float]:
        """Ultimul Major High/Low inainte de bar — flip boundary vs pullback range."""
        anchor = self._leg_anchor_from_bos(active)
        if active.direction == 'bearish':
            prior = [h for h in major_highs if h.index < bar_idx]
            if prior:
                return self._swing_body_high(df, prior[-1].index)
            return self._leg_invalidation_level_bearish(
                df, anchor, major_highs, major_lows, bar_idx,
            )
        prior = [l for l in major_lows if l.index < bar_idx]
        if prior:
            return self._swing_body_low(df, prior[-1].index)
        return self._leg_invalidation_level_bullish(
            df, anchor, major_highs, major_lows, bar_idx,
        )

    def _opposite_bos_confirms_leg_change(
        self,
        df: pd.DataFrame,
        active: BOS,
        counter: BOS,
        major_highs: List,
        major_lows: List,
    ) -> bool:
        if counter.direction == active.direction:
            return True
        level = self._structural_break_level_for_signal(
            df, counter, major_highs, major_lows,
        )
        if level is None:
            return False
        structural = (
            self._bar_body_close_above(df, counter.index, level)
            if counter.direction == 'bullish'
            else self._bar_body_close_below(df, counter.index, level)
        )
        if not structural:
            return False
        boundary = self._active_leg_range_boundary_for_flip(
            df, active, major_highs, major_lows, counter.index,
        )
        if boundary is None:
            return True
        if counter.direction == 'bullish':
            return self._bar_body_close_above(df, counter.index, boundary)
        return self._bar_body_close_below(df, counter.index, boundary)

    def _resolve_active_leg_from_flips(
        self,
        df: pd.DataFrame,
        flips: List[CHoCH],
        major_highs: List,
        major_lows: List,
        bos_list: Optional[List] = None,
    ) -> Optional[CHoCH]:
        if not flips:
            return None
        confirmed = [
            f for f in flips
            if self._is_major_structural_choch(f)
            and self._major_reversal_confirmed(df, f)
        ]
        candidates = confirmed if confirmed else flips
        active = candidates[0]
        for flip in candidates[1:]:
            if flip.direction == active.direction:
                active = flip
                continue
            if not self._is_major_structural_choch(flip):
                continue
            if not self._opposite_flip_confirms_leg_change(
                df, active, flip, major_highs, major_lows,
            ):
                continue
            active = flip
        if self._pure_leg_still_valid(df, active, major_highs, major_lows):
            return active
        bos_list = bos_list or []
        for flip in reversed(candidates):
            if not self._pure_leg_still_valid(df, flip, major_highs, major_lows):
                continue
            if flip.direction == 'bullish':
                post_bear = [
                    b for b in bos_list
                    if b.index > flip.index and b.direction == 'bearish'
                ]
                if post_bear:
                    continue
            else:
                post_bull = [
                    b for b in bos_list
                    if b.index > flip.index and b.direction == 'bullish'
                ]
                if post_bull:
                    lh = self._leg_invalidation_level_bearish(
                        df, flip, major_highs, major_lows, len(df) - 1,
                    )
                    if lh is not None and any(
                        self._bar_body_close_above(df, b.index, lh) for b in post_bull
                    ):
                        continue
            return flip
        return None

    def _filter_countertrend_pullback_bos(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        bos_list: List,
    ) -> List:
        if leg_choch is None or not bos_list:
            return bos_list
        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        major_highs, major_lows = self.filter_major_swings(
            df, swing_highs, swing_lows,
        )
        filtered: List = []
        for b in bos_list:
            if b.index <= leg_choch.index:
                filtered.append(b)
                continue
            if b.direction == leg_choch.direction:
                filtered.append(b)
                continue
            if self._counter_bos_is_leg_pullback(
                df, leg_choch, b, major_highs, major_lows,
            ):
                continue
            if leg_choch.direction == 'bearish':
                lh = self._leg_invalidation_level_bearish(
                    df, leg_choch, major_highs, major_lows, b.index,
                )
                if lh and self._bar_body_close_above(df, b.index, lh):
                    filtered.append(b)
            else:
                hl = self._leg_invalidation_level_bullish(
                    df, leg_choch, major_highs, major_lows, b.index,
                )
                if hl and self._bar_body_close_below(df, b.index, hl):
                    filtered.append(b)
        return filtered

    @staticmethod
    def _forming_higher_low(major_lows: List, since_index: int = 0) -> bool:
        """Major-only HL forming after anchor — no weak geometric pivots."""
        scoped = [l for l in major_lows if l.index > since_index]
        if len(scoped) < 2:
            return False
        return scoped[-1].price > scoped[-2].price

    @staticmethod
    def _forming_lower_high(major_highs: List, since_index: int = 0) -> bool:
        """Major-only LH forming after anchor — no weak geometric pivots."""
        scoped = [h for h in major_highs if h.index > since_index]
        if len(scoped) < 2:
            return False
        return scoped[-1].price < scoped[-2].price

    def _forming_higher_low_at_edge(
        self,
        df: pd.DataFrame,
        major_lows: List,
        since_index: int,
    ) -> bool:
        """Major HL after anchor; if majors still printing, use tail swing lows."""
        if self._forming_higher_low(major_lows, since_index):
            return True
        if len([l for l in major_lows if l.index > since_index]) >= 2:
            return False
        swing_lows = self.detect_swing_lows(df)
        return (
            len(swing_lows) >= 2
            and swing_lows[-1].price > swing_lows[-2].price
        )

    def _forming_lower_high_at_edge(
        self,
        df: pd.DataFrame,
        major_highs: List,
        since_index: int,
    ) -> bool:
        """Major LH after anchor; if majors still printing, use tail swing highs."""
        if self._forming_lower_high(major_highs, since_index):
            return True
        if len([h for h in major_highs if h.index > since_index]) >= 2:
            return False
        swing_highs = self.detect_swing_highs(df)
        return (
            len(swing_highs) >= 2
            and swing_highs[-1].price < swing_highs[-2].price
        )

    def _counter_bos_is_leg_pullback(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        bos: BOS,
        major_highs: List,
        major_lows: List,
    ) -> bool:
        """Counter-trend BOS inside active leg without origin reclaim = pullback only."""
        if bos.index <= leg_choch.index or bos.direction == leg_choch.direction:
            return False
        if leg_choch.direction == 'bearish':
            if self._body_reclaimed_origin_high(df, leg_choch, major_highs, major_lows):
                return False
            return self._close_inside_active_leg_boundary(
                df, leg_choch, major_highs, major_lows, bar_idx=bos.index,
            )
        if self._body_reclaimed_origin_low(df, leg_choch, major_highs, major_lows):
            return False
        return self._close_inside_active_leg_boundary(
            df, leg_choch, major_highs, major_lows, bar_idx=bos.index,
        )

    def _resolve_active_direction_from_bos(
        self,
        df: pd.DataFrame,
        bos_list: List,
        major_highs: List,
        major_lows: List,
    ) -> Tuple[Optional[BOS], Optional[str]]:
        if not bos_list:
            return None, None
        active = bos_list[0]
        for counter in bos_list[1:]:
            if counter.direction == active.direction:
                active = counter
                continue
            if self._opposite_bos_confirms_leg_change(
                df, active, counter, major_highs, major_lows,
            ):
                active = counter
        last = bos_list[-1]
        prior_opposite: Optional[BOS] = None
        for b in reversed(bos_list):
            if b.index <= active.index and b.direction != active.direction:
                prior_opposite = b
                break
        active_anchor = self._leg_anchor_from_bos(active)
        if self._pure_leg_still_valid(df, active_anchor, major_highs, major_lows):
            if (
                active.direction == 'bullish'
                and prior_opposite is not None
                and prior_opposite.direction == 'bearish'
            ):
                bear_anchor = self._leg_anchor_from_bos(prior_opposite)
                if (
                    self._pure_leg_still_valid(df, bear_anchor, major_highs, major_lows)
                    and not self._body_reclaimed_origin_high(
                        df, bear_anchor, major_highs, major_lows,
                    )
                ):
                    return prior_opposite, 'bearish'
            return active, active.direction
        if (
            not self._pure_leg_still_valid(df, active_anchor, major_highs, major_lows)
            and prior_opposite is not None
        ):
            prior_anchor = self._leg_anchor_from_bos(prior_opposite)
            if self._pure_leg_still_valid(
                df, prior_anchor, major_highs, major_lows,
            ):
                if (
                    last.direction == 'bullish'
                    and prior_opposite.direction == 'bearish'
                    and not self._forming_higher_low_at_edge(
                        df, major_lows, active.index,
                    )
                ):
                    return prior_opposite, prior_opposite.direction
                if (
                    last.direction == 'bearish'
                    and prior_opposite.direction == 'bullish'
                    and not self._forming_lower_high_at_edge(
                        df, major_highs, active.index,
                    )
                ):
                    return self._macro_tiebreak_bos_direction(
                        df, bos_list, last, major_highs, major_lows,
                    )
        return self._macro_tiebreak_bos_direction(
            df, bos_list, last, major_highs, major_lows,
        )

    def _resolve_pure_d1_matrix(
        self,
        df: pd.DataFrame,
        chochs: List[CHoCH],
        bos_list: List,
        debug: bool = False,
        range_state: Optional[StructuralRangeState] = None,
    ) -> Tuple[Optional[object], str, str, Optional[CHoCH]]:
        chochs = self._dedupe_chochs_by_bar(chochs)
        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        major_highs, major_lows = self.filter_major_swings(
            df, swing_highs, swing_lows,
        )
        flips = self._true_choch_flips(chochs)
        leg_choch = self._resolve_active_leg_from_flips(
            df, flips, major_highs, major_lows, bos_list=bos_list,
        )
        if leg_choch is not None and leg_choch.direction == 'bullish':
            bear_before = [
                f for f in flips
                if f.direction == 'bearish' and f.index < leg_choch.index
            ]
            if bear_before:
                last_bear = bear_before[-1]
                lh = self._leg_invalidation_level_bearish(
                    df, last_bear, major_highs, major_lows, len(df) - 1,
                )
                _close = float(df['close'].iloc[-1])
                if (
                    lh is not None
                    and _close <= lh
                    and not self._body_reclaimed_origin_high(
                        df, last_bear, major_highs, major_lows,
                    )
                ):
                    leg_choch = last_bear
        leg_choch = self._coerce_leg_with_boundary_gate(
            df, leg_choch, flips, major_highs, major_lows,
        )
        if leg_choch is not None:
            chochs, bos_list = self._demote_post_leg_choch_to_bos(
                leg_choch, chochs, bos_list,
            )
            bos_list = self._filter_countertrend_pullback_bos(
                df, leg_choch, bos_list,
            )
            sig, st, trend, leg = self._strategy_from_leg_choch(
                df, leg_choch, bos_list, major_highs, major_lows,
            )
            if debug:
                label = 'CONTINUATION' if st == 'continuation' else 'REVERSAL'
                print(
                    f"   📐 [PURE SMC] leg CHoCH {leg_choch.direction.upper()} "
                    f"@bar{leg_choch.index} → {label}"
                )
            return sig, st, trend, leg
        # V69: trend authority = macro range body-close only — no blind BOS fallback
        last_bear = None
        bear_flips = [f for f in flips if f.direction == 'bearish']
        if bear_flips:
            last_bear = bear_flips[-1]
        elif bos_list:
            bear_bos = [b for b in bos_list if b.direction == 'bearish']
            if bear_bos:
                last_bear = self._leg_anchor_from_bos(bear_bos[-1])
        last_bull = None
        bull_flips = [f for f in flips if f.direction == 'bullish']
        if bull_flips:
            last_bull = bull_flips[-1]
        elif bos_list:
            bull_bos = [b for b in bos_list if b.direction == 'bullish']
            if bull_bos:
                last_bull = self._leg_anchor_from_bos(bull_bos[-1])
        _close = float(df['close'].iloc[-1])
        if range_state and range_state.locked_bias == 'bearish':
            _lh = float(range_state.macro_range_high)
            if _close <= _lh and last_bear is not None:
                if not self._body_reclaimed_origin_high(
                    df, last_bear, major_highs, major_lows,
                ):
                    leg_choch = last_bear
                    bos_list = self._filter_countertrend_pullback_bos(
                        df, leg_choch, bos_list,
                    )
                    sig, st, trend, leg = self._strategy_from_leg_choch(
                        df, leg_choch, bos_list, major_highs, major_lows,
                    )
                    if debug:
                        print(
                            f"   📐 [PURE SMC] macro bear range — leg "
                            f"{leg_choch.direction.upper()} @bar{leg_choch.index}"
                        )
                    return sig, st, trend, leg
        if range_state and range_state.locked_bias == 'bullish':
            _hl = float(range_state.macro_range_low)
            if _close >= _hl and last_bull is not None:
                if not self._body_reclaimed_origin_low(
                    df, last_bull, major_highs, major_lows,
                ):
                    leg_choch = last_bull
                    bos_list = self._filter_countertrend_pullback_bos(
                        df, leg_choch, bos_list,
                    )
                    sig, st, trend, leg = self._strategy_from_leg_choch(
                        df, leg_choch, bos_list, major_highs, major_lows,
                    )
                    if debug:
                        print(
                            f"   📐 [PURE SMC] macro bull range — leg "
                            f"{leg_choch.direction.upper()} @bar{leg_choch.index}"
                        )
                    return sig, st, trend, leg
        if last_bear is not None and not self._body_reclaimed_origin_high(
            df, last_bear, major_highs, major_lows,
        ):
            lh = self._leg_invalidation_level_bearish(
                df, last_bear, major_highs, major_lows, len(df) - 1,
            )
            if lh is not None and _close <= lh:
                leg_choch = last_bear
                bos_list = self._filter_countertrend_pullback_bos(
                    df, leg_choch, bos_list,
                )
                sig, st, trend, leg = self._strategy_from_leg_choch(
                    df, leg_choch, bos_list, major_highs, major_lows,
                )
                return sig, st, trend, leg
        if last_bull is not None and not self._body_reclaimed_origin_low(
            df, last_bull, major_highs, major_lows,
        ):
            hl = self._leg_invalidation_level_bullish(
                df, last_bull, major_highs, major_lows, len(df) - 1,
            )
            if hl is not None and _close >= hl:
                leg_choch = last_bull
                bos_list = self._filter_countertrend_pullback_bos(
                    df, leg_choch, bos_list,
                )
                sig, st, trend, leg = self._strategy_from_leg_choch(
                    df, leg_choch, bos_list, major_highs, major_lows,
                )
                return sig, st, trend, leg
        if chochs:
            c = chochs[-1]
            _close = float(df['close'].iloc[-1])
            if c.direction == 'bullish' and bear_flips:
                _lb = bear_flips[-1]
                _lh = self._leg_invalidation_level_bearish(
                    df, _lb, major_highs, major_lows, len(df) - 1,
                )
                if (
                    _lh is not None
                    and _close <= _lh
                    and not self._body_reclaimed_origin_high(
                        df, _lb, major_highs, major_lows,
                    )
                ):
                    leg_choch = _lb
                    bos_list = self._filter_countertrend_pullback_bos(
                        df, leg_choch, bos_list,
                    )
                    return self._strategy_from_leg_choch(
                        df, leg_choch, bos_list, major_highs, major_lows,
                    )
            if c.direction == 'bearish' and bull_flips:
                _lbull = bull_flips[-1]
                _hl = self._leg_invalidation_level_bullish(
                    df, _lbull, major_highs, major_lows, len(df) - 1,
                )
                if (
                    _hl is not None
                    and _close >= _hl
                    and not self._body_reclaimed_origin_low(
                        df, _lbull, major_highs, major_lows,
                    )
                ):
                    leg_choch = _lbull
                    bos_list = self._filter_countertrend_pullback_bos(
                        df, leg_choch, bos_list,
                    )
                    return self._strategy_from_leg_choch(
                        df, leg_choch, bos_list, major_highs, major_lows,
                    )
            st = (
                'reversal'
                if self._is_major_structural_choch(c)
                and self._major_reversal_confirmed(df, c)
                else 'continuation'
            )
            return c, st, c.direction, c if st == 'reversal' else None
        return None, 'continuation', 'neutral', None

    def _leg_invalidated_by_protected_breach(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
    ) -> bool:
        if leg_choch is None or df is None or len(df) == 0:
            return False
        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        major_highs, major_lows = self.filter_major_swings(
            df, swing_highs, swing_lows,
        )
        return not self._pure_leg_still_valid(
            df, leg_choch, major_highs, major_lows,
        )

    def _leg_choch_price_level_valid(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        bos_list: List,
    ) -> bool:
        """
        V67.1: validare pură break + HL/LH protejat + BOS same-dir.
        Fără apeluri la supersede — folosită de _leg_superseded_by_opposite_major_flip
        ca să evite recursia infinită cu _leg_choch_still_valid.
        """
        if df is None or len(df) == 0 or leg_choch is None:
            return False
        close = float(df['close'].iloc[-1])
        ref = float(leg_choch.break_price)
        same_dir_bos = [
            b for b in bos_list
            if b.index > leg_choch.index and b.direction == leg_choch.direction
        ]
        if same_dir_bos:
            latest_bos = same_dir_bos[-1]
            if leg_choch.direction == 'bullish':
                ref = max(ref, float(latest_bos.break_price))
            else:
                ref = min(ref, float(latest_bos.break_price))
        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        major_highs, major_lows = self.filter_major_swings(
            df, swing_highs, swing_lows,
        )
        if leg_choch.direction == 'bullish':
            threshold = self._leg_invalidation_level_bullish(
                df, leg_choch, major_highs, major_lows, len(df) - 1,
            )
            if threshold is not None and close < threshold:
                return False
            protected = self._protected_hl_level_after_leg(df, leg_choch)
            if protected is not None and close < protected:
                return False
            if same_dir_bos:
                return True
            return close >= ref
        threshold = self._leg_invalidation_level_bearish(
            df, leg_choch, major_highs, major_lows, len(df) - 1,
        )
        if threshold is not None and close > threshold:
            return False
        if same_dir_bos:
            return True
        return close <= ref

    def _leg_superseded_by_opposite_major_flip(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        chochs: List[CHoCH],
        bos_list: Optional[List] = None,
    ) -> bool:
        """V63: later opposite major CHoCH retires this leg only when that flip is still active."""
        if leg_choch is None or not chochs:
            return False
        bos_list = bos_list or []
        opposite = 'bearish' if leg_choch.direction == 'bullish' else 'bullish'
        for c in chochs:
            if c.index <= leg_choch.index:
                continue
            if c.direction != opposite:
                continue
            if not self._is_major_structural_choch(c):
                continue
            if not self._major_reversal_confirmed(df, c):
                continue
            # V67.1: price-level only — NU _leg_choch_still_valid (recursie infinită)
            if self._leg_choch_price_level_valid(df, c, bos_list):
                return True
        return False

    def _leg_choch_still_valid(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        bos_list: List,
        chochs: Optional[List[CHoCH]] = None,
    ) -> bool:
        """V64.1: leg activ doar cât prețul respectă break + HL/LH protejat (fără BOS zombie)."""
        if df is None or len(df) == 0 or leg_choch is None:
            return False
        if chochs and self._leg_superseded_by_opposite_major_flip(
            df, leg_choch, chochs, bos_list,
        ):
            return False
        return self._leg_choch_price_level_valid(df, leg_choch, bos_list)

    @staticmethod
    def _dedupe_chochs_by_bar(chochs: List[CHoCH]) -> List[CHoCH]:
        """Un singur CHoCH per bar — evită bullish+bearish pe același index."""
        by_bar: dict = {}
        for c in chochs:
            prev = by_bar.get(c.index)
            if prev is None:
                by_bar[c.index] = c
                continue
            # Păstrează flip-ul cu previous_trend explicit (CHoCH real vs bootstrap)
            if c.previous_trend and c.previous_trend != c.direction:
                by_bar[c.index] = c
        return sorted(by_bar.values(), key=lambda x: x.index)

    @staticmethod
    def _true_choch_flips(chochs: List[CHoCH]) -> List[CHoCH]:
        return [
            c for c in chochs
            if c.previous_trend and c.previous_trend != c.direction
        ]

    @staticmethod
    def _post_leg_bos(
        leg_choch: Optional[CHoCH],
        bos_list: Optional[List],
    ) -> List:
        """BOS same-direction după leg CHoCH (body-close breaks în noul trend)."""
        if leg_choch is None or not bos_list:
            return []
        return [
            b for b in bos_list
            if b.index > leg_choch.index and b.direction == leg_choch.direction
        ]

    def _strategy_from_leg_choch(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        bos_list: Optional[List],
        major_highs: List,
        major_lows: List,
    ) -> Tuple[object, str, str, CHoCH]:
        """
        Canon SMC organic (fără praguri de timp):
        - CHoCH flip = singurul eveniment de schimbare de caracter → REVERSAL dacă 0 BOS post-leg
        - Orice LL/HH break same-dir după CHoCH = BOS → CONTINUITY (semnal = ultimul BOS)
        V68 Pilon 1: counter-trend BOS inside active leg boundary = pullback (trend unchanged).
        """
        bos_list = bos_list or []
        trend = leg_choch.direction

        if leg_choch.direction == 'bearish':
            if not self._body_reclaimed_origin_high(df, leg_choch, major_highs, major_lows):
                counter_bull = [
                    b for b in bos_list
                    if b.index > leg_choch.index and b.direction == 'bullish'
                ]
                if counter_bull:
                    post_bos = self._post_leg_bos(leg_choch, bos_list)
                    if post_bos:
                        return post_bos[-1], 'continuation', 'bearish', leg_choch
                    return leg_choch, 'reversal', 'bearish', leg_choch
        elif leg_choch.direction == 'bullish':
            if not self._body_reclaimed_origin_low(df, leg_choch, major_highs, major_lows):
                counter_bear = [
                    b for b in bos_list
                    if b.index > leg_choch.index and b.direction == 'bearish'
                ]
                if counter_bear:
                    post_bos = self._post_leg_bos(leg_choch, bos_list)
                    if post_bos:
                        return post_bos[-1], 'continuation', 'bullish', leg_choch
                    return leg_choch, 'reversal', 'bullish', leg_choch

        post_bos = self._post_leg_bos(leg_choch, bos_list)
        if post_bos:
            return post_bos[-1], 'continuation', trend, leg_choch
        return leg_choch, 'reversal', trend, leg_choch

    @staticmethod
    def _classify_d1_strategy(
        latest_signal: Optional[object],
        leg_choch: Optional[CHoCH],
        bos_list: Optional[List] = None,
        df: Optional[pd.DataFrame] = None,
    ) -> str:
        """Etichetă din structură: post-leg BOS → CONT; doar CHoCH → REV."""
        del df  # organic — fără lookback temporal
        if leg_choch is not None:
            if D1LegMixin._post_leg_bos(leg_choch, bos_list):
                return 'continuation'
            return 'reversal'
        if isinstance(latest_signal, CHoCH):
            return 'reversal'
        return 'continuation'

    @staticmethod
    def _d1_signal_for_strategy(
        latest_signal: Optional[object],
        leg_choch: Optional[CHoCH],
        strategy_type: str,
        bos_list: Optional[List] = None,
    ) -> Optional[object]:
        """CHoCH pentru REV; ultimul BOS post-leg pentru CONT."""
        if strategy_type == 'continuation' and leg_choch is not None:
            post_bos = D1LegMixin._post_leg_bos(leg_choch, bos_list)
            if post_bos:
                return post_bos[-1]
        if strategy_type == 'reversal' and leg_choch is not None:
            return leg_choch
        if strategy_type == 'reversal' and isinstance(latest_signal, CHoCH):
            return latest_signal
        return latest_signal

    def _demote_post_leg_choch_to_bos(
        self,
        leg_choch: CHoCH,
        chochs: List[CHoCH],
        bos_list: List,
    ) -> Tuple[List[CHoCH], List]:
        """CHoCH o dată per leg — orice break same-direction după leg = BOS."""
        if leg_choch is None:
            return chochs, bos_list
        kept: List[CHoCH] = []
        extra_bos: List = []
        for c in chochs:
            if c.index > leg_choch.index and c.direction == leg_choch.direction:
                extra_bos.append(BOS(
                    index=c.index,
                    direction=c.direction,
                    break_price=c.break_price,
                    candle_time=c.candle_time,
                    swing_broken=getattr(c, 'swing_broken', None),
                ))
            else:
                kept.append(c)
        merged = list(bos_list) + extra_bos
        merged.sort(key=lambda x: x.index)
        return kept, merged

    def _find_leg_choch(
        self,
        df: pd.DataFrame,
        chochs: List[CHoCH],
        bos_list: List,
    ) -> Optional[CHoCH]:
        del bos_list
        if not chochs:
            return None
        chochs = self._dedupe_chochs_by_bar(chochs)
        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        major_highs, major_lows = self.filter_major_swings(
            df, swing_highs, swing_lows,
        )
        flips = self._true_choch_flips(chochs)
        return self._resolve_active_leg_from_flips(
            df, flips, major_highs, major_lows,
        )


    def _expansion_bos_confirms_new_range(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        latest_bos: BOS,
    ) -> bool:
        """V44.1 — single expansion BOS after leg CHoCH confirms new HL→HH / LH→LL range."""
        if leg_choch is None or latest_bos is None:
            return False
        if latest_bos.index <= leg_choch.index:
            return False
        if latest_bos.direction != leg_choch.direction:
            return False

        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        post_lows = [
            l for l in swing_lows
            if leg_choch.index < l.index < latest_bos.index
        ]
        post_highs = [
            h for h in swing_highs
            if leg_choch.index < h.index < latest_bos.index
        ]

        if leg_choch.direction == 'bullish':
            if hasattr(latest_bos, 'swing_broken') and latest_bos.swing_broken is not None:
                if float(latest_bos.break_price) <= float(latest_bos.swing_broken.price):
                    return False
            elif not post_highs:
                pre_highs = [h for h in swing_highs if h.index < latest_bos.index]
                if not pre_highs or float(latest_bos.break_price) <= float(pre_highs[-1].price):
                    return False
            if not post_lows:
                return False
            hl = max(post_lows, key=lambda l: self._swing_body_low(df, l.index))
            return float(hl.price) < float(latest_bos.break_price)

        if hasattr(latest_bos, 'swing_broken') and latest_bos.swing_broken is not None:
            if float(latest_bos.break_price) >= float(latest_bos.swing_broken.price):
                return False
        elif not post_lows:
            pre_lows = [l for l in swing_lows if l.index < latest_bos.index]
            if not pre_lows or float(latest_bos.break_price) >= float(pre_lows[-1].price):
                return False
        if not post_highs:
            return False
        lh = min(post_highs, key=lambda h: self._swing_body_high(df, h.index))
        return float(lh.price) > float(latest_bos.break_price)

    def resolve_structural_bias_fallback(
        self,
        df: pd.DataFrame,
        chochs: List[CHoCH],
        bos_list: List,
        range_state: Optional[StructuralRangeState] = None,
    ) -> str:
        """V58: when leg resolve is neutral — infer bias from range + last valid BOS/CHoCH."""
        macro = self.macro_trend_from_swings(df)
        if macro != 'neutral':
            return macro
        close = float(df['close'].iloc[-1])
        if range_state is not None and range_state.locked:
            _ll = float(range_state.macro_range_low)
            _lh = float(range_state.macro_range_high)
            if close <= _ll:
                bearish_bos = [b for b in bos_list if b.direction == 'bearish']
                bearish_chochs = [c for c in chochs if c.direction == 'bearish']
                if bearish_bos or bearish_chochs:
                    return 'bearish'
            elif close > _lh:
                bullish_bos = [b for b in bos_list if b.direction == 'bullish']
                bullish_chochs = [c for c in chochs if c.direction == 'bullish']
                if bullish_bos or bullish_chochs:
                    return 'bullish'
        return 'neutral'

    def _resolve_historical_opposite_bias(
        self,
        df: pd.DataFrame,
        chochs: List[CHoCH],
        bos_list: List,
        dead_leg: CHoCH,
        debug: bool = False,
    ) -> Tuple[Optional[object], str, str, Optional[CHoCH]]:
        """V58: last opposite CHoCH/BOS in full series when post-leg flip finds nothing."""
        opposite = 'bearish' if dead_leg.direction == 'bullish' else 'bullish'
        hist_bos = [
            b for b in bos_list
            if b.direction == opposite and b.index > dead_leg.index
        ]
        hist_chochs = [
            c for c in chochs
            if c.direction == opposite and c.index > dead_leg.index
        ]
        if hist_chochs:
            new_leg = hist_chochs[-1]
            msg = (
                f"   🔄 [V58 HIST FLIP] dead {dead_leg.direction.upper()} leg @bar{dead_leg.index} "
                f"→ {opposite.upper()} REVERSAL CHoCH @bar{new_leg.index} (historical)"
            )
            if debug:
                print(msg)
            return new_leg, 'reversal', opposite, new_leg
        return None, 'continuation', 'neutral', None

    def _resolve_post_leg_flip(
        self,
        df: pd.DataFrame,
        chochs: List[CHoCH],
        bos_list: List,
        dead_leg: CHoCH,
        debug: bool = False,
    ) -> Tuple[Optional[object], str, str, Optional[CHoCH]]:
        """V57 + V65: opposite CHoCH post-leg = REVERSAL (body-close flip)."""
        opposite = 'bearish' if dead_leg.direction == 'bullish' else 'bullish'
        post_chochs = [
            c for c in chochs
            if c.index > dead_leg.index
            and c.direction == opposite
            and c.previous_trend
            and c.previous_trend != c.direction
        ]
        if post_chochs:
            new_leg = post_chochs[-1]
            if debug:
                print(
                    f"   🔄 [V57 LEG FLIP] dead {dead_leg.direction.upper()} leg @bar{dead_leg.index} "
                    f"→ {opposite.upper()} REVERSAL CHoCH @bar{new_leg.index}"
                )
            return new_leg, 'reversal', opposite, new_leg
        hist = self._resolve_historical_opposite_bias(
            df, chochs, bos_list, dead_leg, debug=debug,
        )
        if hist[0] is not None:
            return hist
        if debug:
            print(
                f"   ⛔ [V57 LEG FLIP] dead {dead_leg.direction.upper()} leg @bar{dead_leg.index} "
                f"— no opposite structure post-leg"
            )
        return None, 'continuation', 'neutral', None

    @staticmethod
    def _is_major_structural_choch(choch: Optional[CHoCH]) -> bool:
        """CHoCH major = flip real (previous_trend ≠ direction)."""
        if choch is None:
            return False
        return bool(choch.previous_trend and choch.previous_trend != choch.direction)

    def _major_reversal_confirmed(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
    ) -> bool:
        """
        REVERSAL doar după body-close confirmat peste/sub ultimul pivot major opus.
        CHoCH-urile din detect_choch_and_bos folosesc deja pivoți majori filtrați.
        """
        if not self._is_major_structural_choch(leg_choch):
            return False
        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
        major_highs, major_lows = self.filter_major_swings(df, swing_highs, swing_lows)
        broken = getattr(leg_choch, 'swing_broken', None)
        if broken is not None:
            ref_idx = broken.index
            if leg_choch.direction == 'bullish':
                if any(h.index == ref_idx for h in major_highs):
                    ref = self._swing_body_high(df, ref_idx)
                    return self._body_close_above_after(df, ref_idx, ref)
            else:
                if any(l.index == ref_idx for l in major_lows):
                    ref = self._swing_body_low(df, ref_idx)
                    return self._body_close_below_after(df, ref_idx, ref)
        if leg_choch.direction == 'bullish':
            prior = [h for h in major_highs if h.index < leg_choch.index]
            if not prior:
                return True
            ref = self._swing_body_high(df, prior[-1].index)
            return self._body_close_above_after(df, prior[-1].index, ref)
        prior = [l for l in major_lows if l.index < leg_choch.index]
        if not prior:
            return True
        ref = self._swing_body_low(df, prior[-1].index)
        return self._body_close_below_after(df, prior[-1].index, ref)
