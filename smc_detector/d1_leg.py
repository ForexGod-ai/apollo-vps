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

    def _leg_invalidated_by_protected_breach(
        self,
        df: pd.DataFrame,
        leg_choch: CHoCH,
    ) -> bool:
        """Close curent sub HL / peste LH protejat — leg bullish/bearish mort structural."""
        if leg_choch is None or df is None or len(df) == 0:
            return False
        close = float(df['close'].iloc[-1])
        if leg_choch.direction == 'bullish':
            level = self._protected_hl_level_after_leg(df, leg_choch)
            return level is not None and close < level
        level = self._protected_lh_level_after_leg(df, leg_choch)
        return level is not None and close > level

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
        if leg_choch.direction == 'bullish':
            protected = self._protected_hl_level_after_leg(df, leg_choch)
            if protected is not None and close < protected:
                return False
            if same_dir_bos:
                return True
            return close >= ref
        protected = self._protected_lh_level_after_leg(df, leg_choch)
        if protected is not None and close > protected:
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
        """
        V63: Leg = ultimul CHoCH major confirmat (flip real pe pivot major).
        """
        if not chochs:
            return None
        chochs = self._dedupe_chochs_by_bar(chochs)
        major_flips = [
            c for c in chochs
            if self._is_major_structural_choch(c) and self._major_reversal_confirmed(df, c)
        ]
        if major_flips:
            for c in reversed(major_flips):
                if not self._leg_choch_still_valid(df, c, bos_list, chochs):
                    continue
                later_opposite = [
                    x for x in major_flips
                    if x.index > c.index and x.direction != c.direction
                    and self._leg_choch_still_valid(df, x, bos_list, chochs)
                ]
                if later_opposite:
                    continue
                return c

        flips = self._true_choch_flips(chochs)
        if not flips:
            for c in reversed(chochs):
                if self._leg_choch_still_valid(df, c, bos_list, chochs):
                    return c
            return chochs[-1]

        latest = flips[-1]
        if (
            not self._leg_choch_still_valid(df, latest, bos_list, chochs)
            and latest.direction == 'bullish'
            and self._leg_invalidated_by_protected_breach(df, latest)
        ):
            return latest

        active_dir = None
        for f in reversed(flips):
            if self._leg_choch_still_valid(df, f, bos_list, chochs):
                active_dir = f.direction
                break
        if not active_dir:
            return flips[-1]

        for f in reversed(flips):
            if f.direction != active_dir:
                continue
            if not self._leg_choch_still_valid(df, f, bos_list, chochs):
                continue
            return f

        return flips[-1]

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
            else:
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
            else:
                print(
                    f"   🔄 [V57 LEG FLIP] dead {dead_leg.direction.upper()} leg @bar{dead_leg.index} "
                    f"→ {opposite.upper()} REVERSAL @bar{new_leg.index}"
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
