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
    ) -> bool:
        """Body close above origin major high — pullback reclaim invalidates bearish leg."""
        if df is None or len(df) == 0 or leg_choch is None:
            return False
        origin = self._leg_origin_major_high(df, leg_choch)
        if origin is None:
            return False
        last_bar = len(df) - 1
        return self._bar_body_close_above(df, last_bar, origin)

    def _body_reclaimed_origin_low(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
    ) -> bool:
        """Body close below origin major low — pullback reclaim invalidates bullish leg."""
        if df is None or len(df) == 0 or leg_choch is None:
            return False
        origin = self._leg_origin_major_low(df, leg_choch)
        if origin is None:
            return False
        last_bar = len(df) - 1
        return self._bar_body_close_below(df, last_bar, origin)


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
        bar_idx: int,
    ) -> Optional[float]:
        """Ultimul Major High at bar — for flip confirmation on that bar."""
        latest = self._latest_major_high_body(df, major_highs, bar_idx)
        if latest is not None:
            return latest
        return self._leg_origin_major_high(df, leg_choch)

    def _flip_threshold_for_bullish_leg(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        major_lows: List,
        bar_idx: int,
    ) -> Optional[float]:
        """Ultimul Major Low at bar — for flip confirmation on that bar."""
        latest = self._latest_major_low_body(df, major_lows, bar_idx)
        if latest is not None:
            return latest
        return self._leg_origin_major_low(df, leg_choch)

    def _leg_invalidation_level_bearish(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        major_highs: List,
        bar_idx: int,
    ) -> Optional[float]:
        """Range ceiling — ultimul Major High at bar (pure SMC flip boundary)."""
        latest = self._latest_major_high_body(df, major_highs, bar_idx)
        if latest is not None:
            return latest
        return self._leg_origin_major_high(df, leg_choch)

    def _leg_invalidation_level_bullish(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
        major_lows: List,
        bar_idx: int,
    ) -> Optional[float]:
        """Range floor — ultimul Major Low at bar (pure SMC flip boundary)."""
        latest = self._latest_major_low_body(df, major_lows, bar_idx)
        if latest is not None:
            return latest
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
                df, leg_choch, major_lows, bar_idx,
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
            df, leg_choch, major_highs, bar_idx,
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
                df, anchor, major_highs, bar_idx,
            )
        prior = [l for l in major_lows if l.index < bar_idx]
        if prior:
            return self._swing_body_low(df, prior[-1].index)
        return self._leg_invalidation_level_bullish(
            df, anchor, major_lows, bar_idx,
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
            if leg_choch.direction == 'bearish':
                prior = [h for h in major_highs if h.index < b.index]
                if prior and self._bar_body_close_above(
                    df, b.index, self._swing_body_high(df, prior[-1].index),
                ):
                    filtered.append(b)
            else:
                prior = [l for l in major_lows if l.index < b.index]
                if prior and self._bar_body_close_below(
                    df, b.index, self._swing_body_low(df, prior[-1].index),
                ):
                    filtered.append(b)
        return filtered

    @staticmethod
    def _forming_higher_low(swing_lows: List) -> bool:
        return len(swing_lows) >= 2 and swing_lows[-1].price > swing_lows[-2].price

    @staticmethod
    def _forming_lower_high(swing_highs: List) -> bool:
        return len(swing_highs) >= 2 and swing_highs[-1].price < swing_highs[-2].price

    def _resolve_active_direction_from_bos(
        self,
        df: pd.DataFrame,
        bos_list: List,
        major_highs: List,
        major_lows: List,
    ) -> Tuple[Optional[BOS], Optional[str]]:
        if not bos_list:
            return None, None
        swing_highs = self.detect_swing_highs(df)
        swing_lows = self.detect_swing_lows(df)
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
        active_anchor = self._leg_anchor_from_bos(active)
        if self._pure_leg_still_valid(df, active_anchor, major_highs, major_lows):
            return active, active.direction
        prior_opposite: Optional[BOS] = None
        for b in reversed(bos_list):
            if b.index <= active.index and b.direction != active.direction:
                prior_opposite = b
                break
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
                    and not self._forming_higher_low(swing_lows)
                ):
                    return prior_opposite, prior_opposite.direction
                if (
                    last.direction == 'bearish'
                    and prior_opposite.direction == 'bullish'
                    and not self._forming_lower_high(swing_highs)
                ):
                    return last, last.direction
        return last, last.direction

    def _resolve_pure_d1_matrix(
        self,
        df: pd.DataFrame,
        chochs: List[CHoCH],
        bos_list: List,
        debug: bool = False,
        range_state: Optional[StructuralRangeState] = None,
    ) -> Tuple[Optional[object], str, str, Optional[CHoCH]]:
        del range_state
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
                swing_lows = self.detect_swing_lows(df)
                if not self._post_leg_bos(last_bear, bos_list):
                    if not self._forming_higher_low(swing_lows):
                        leg_choch = last_bear
                else:
                    swing_h = self.detect_swing_highs(df)
                    lh_reclaimed = False
                    for i in range(len(swing_h) - 1, 0, -1):
                        if swing_h[i].index <= last_bear.index:
                            continue
                        if swing_h[i].price < swing_h[i - 1].price:
                            lh_body = self._swing_body_high(df, swing_h[i].index)
                            if self._bar_body_close_above(df, len(df) - 1, lh_body):
                                lh_reclaimed = True
                            break
                    if not lh_reclaimed:
                        leg_choch = last_bear
        if leg_choch is not None:
            chochs, bos_list = self._demote_post_leg_choch_to_bos(
                leg_choch, chochs, bos_list,
            )
            bos_list = self._filter_countertrend_pullback_bos(
                df, leg_choch, bos_list,
            )
            sig, st, trend, leg = self._strategy_from_leg_choch(leg_choch, bos_list)
            if debug:
                label = 'CONTINUATION' if st == 'continuation' else 'REVERSAL'
                print(
                    f"   📐 [PURE SMC] leg CHoCH {leg_choch.direction.upper()} "
                    f"@bar{leg_choch.index} → {label}"
                )
            return sig, st, trend, leg
        active_bos, bos_trend = self._resolve_active_direction_from_bos(
            df, bos_list, major_highs, major_lows,
        )
        if active_bos is not None and bos_trend is not None:
            return active_bos, 'continuation', bos_trend, None
        if bos_list:
            b = bos_list[-1]
            return b, 'continuation', b.direction, None
        if chochs:
            c = chochs[-1]
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
                df, leg_choch, major_lows, len(df) - 1,
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
            df, leg_choch, major_highs, len(df) - 1,
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

    @staticmethod
    def _strategy_from_leg_choch(
        leg_choch: CHoCH,
        bos_list: Optional[List],
    ) -> Tuple[object, str, str, CHoCH]:
        """
        Canon SMC organic (fără praguri de timp):
        - CHoCH flip = singurul eveniment de schimbare de caracter → REVERSAL dacă 0 BOS post-leg
        - Orice LL/HH break same-dir după CHoCH = BOS → CONTINUITY (semnal = ultimul BOS)
        """
        post_bos = D1LegMixin._post_leg_bos(leg_choch, bos_list)
        if post_bos:
            return post_bos[-1], 'continuation', leg_choch.direction, leg_choch
        return leg_choch, 'reversal', leg_choch.direction, leg_choch

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
