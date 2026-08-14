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


class D1AuthorityMixin:
    """V67 C: canonical D1 authority."""

    def build_d1_context(
        self,
        df: pd.DataFrame,
        symbol: str = '?',
        debug: bool = False,
    ) -> D1AuthContext:
        """V67: One canonical D1 pipeline per symbol — cache for scanner + JSON."""
        empty = D1AuthContext(
            symbol=symbol,
            trend='neutral',
            strategy_type='continuation',
            macro_swings='neutral',
            direction='',
            d1_bias_direction='neutral',
            daily_bias='NEUTRAL',
            latest_signal=None,
            leg_choch=None,
            d1_signal_type='BOS',
            chochs=[],
            bos_list=[],
            range_state=None,
            swing_h=[],
            swing_l=[],
        )
        if df is None or df.empty:
            return empty
        if not {'open', 'high', 'low', 'close'}.issubset(df.columns):
            return empty

        chochs, bos_list = self.detect_choch_and_bos(df)
        swing_h = self.detect_swing_highs(df)
        swing_l = self.detect_swing_lows(df)
        range_state = self.compute_structural_range(df, swing_h, swing_l, symbol=symbol)
        chochs, bos_list, range_state = self.filter_internal_range_signals(
            symbol, df, chochs, bos_list, range_state, debug=debug,
        )
        latest, strategy_type, current_trend, leg_choch = self._resolve_d1_leg(
            df, chochs, bos_list, debug=debug, range_state=range_state,
        )
        strategy_type = self._classify_d1_strategy(
            latest, leg_choch, bos_list, df,
        )
        latest = self._d1_signal_for_strategy(
            latest, leg_choch, strategy_type, bos_list,
        )
        macro_swings = self.macro_trend_from_swings(df)
        if current_trend == 'neutral' and macro_swings != 'neutral':
            current_trend = macro_swings
            if leg_choch is None:
                strategy_type = 'continuation'
        if current_trend == 'neutral':
            fallback = self.resolve_structural_bias_fallback(
                df, chochs, bos_list, range_state,
            )
            if fallback != 'neutral':
                current_trend = fallback
                if leg_choch is None:
                    strategy_type = 'continuation'

        trade_dir = ''
        if current_trend == 'bullish':
            trade_dir = 'buy'
        elif current_trend == 'bearish':
            trade_dir = 'sell'

        d1_signal_type = 'CHoCH' if strategy_type == 'reversal' else 'BOS'
        if leg_choch is not None and strategy_type == 'reversal':
            latest = leg_choch
        elif strategy_type == 'reversal' and isinstance(latest, CHoCH):
            pass
        elif strategy_type == 'reversal' and leg_choch is not None:
            latest = leg_choch

        return D1AuthContext(
            symbol=symbol,
            trend=current_trend,
            strategy_type=strategy_type,
            macro_swings=macro_swings,
            direction=trade_dir,
            d1_bias_direction=current_trend,
            daily_bias=current_trend.upper() if current_trend != 'neutral' else 'NEUTRAL',
            latest_signal=latest,
            leg_choch=leg_choch,
            d1_signal_type=d1_signal_type,
            chochs=chochs,
            bos_list=bos_list,
            range_state=range_state,
            swing_h=swing_h,
            swing_l=swing_l,
        )

    def resolve_authoritative_d1_bias(
        self,
        df: pd.DataFrame,
        symbol: str = '?',
    ) -> dict:
        """
        V63: Single source of truth for D1 direction/strategy (scanner + identity lock + JSON).
        Runs canonical resolve_d1_leg on major-filtered signals.
        """
        return self.build_d1_context(df, symbol=symbol).as_dict()

    def macro_authority_supports_direction(
        self,
        df: pd.DataFrame,
        direction: str,
        symbol: str = '?',
    ) -> bool:
        """V62: True when authoritative D1 bias matches normalized direction."""
        auth = self.resolve_authoritative_d1_bias(df, symbol=symbol)
        want = str(direction or '').strip().lower()
        if want in ('buy', 'long', 'bullish'):
            want = 'bullish'
        elif want in ('sell', 'short', 'bearish'):
            want = 'bearish'
        else:
            return False
        return auth.get('trend') == want

    def _resolve_v426_latest_flip(
        self,
        df: pd.DataFrame,
        chochs: List[CHoCH],
        bos_list: List,
        range_state: Optional[StructuralRangeState] = None,
    ) -> Optional[Tuple[Optional[object], str, str, Optional[CHoCH]]]:
        """
        V66 organic: ultimul CHoCH flip + post-leg BOS → CONT; fără BOS → REV.
        """
        flips = self._true_choch_flips(self._dedupe_chochs_by_bar(chochs))
        if not flips:
            return None
        last_bar = len(df) - 1
        close = float(df['close'].iloc[-1])

        def _pack_leg(flip: CHoCH) -> Tuple[Optional[object], str, str, CHoCH]:
            return self._strategy_from_leg_choch(flip, bos_list)

        def _bearish_authority() -> Optional[Tuple[Optional[object], str, str, Optional[CHoCH]]]:
            bear_flips = [f for f in flips if f.direction == 'bearish']
            for bf in reversed(bear_flips):
                if not self._leg_choch_still_valid(df, bf, bos_list, chochs):
                    continue
                return _pack_leg(bf)
            # V65: flip bearish recent (HL lichidat) bate BOS orphan vechi
            if bear_flips:
                return _pack_leg(bear_flips[-1])
            aligned = [b for b in bos_list if b.direction == 'bearish']
            if aligned:
                return aligned[-1], 'continuation', 'bearish', None
            return None

        latest = flips[-1]

        if latest.direction == 'bullish':
            bear_before = [f for f in flips if f.direction == 'bearish' and f.index < latest.index]
            if bear_before:
                last_bear = bear_before[-1]
                # CHoCH bearish fără BOS post-leg = REVERSAL activ (ex. EURJPY crash D1).
                # Bounce bullish nu promovează la CONT decât după BOS bearish post-leg.
                if not self._post_leg_bos(last_bear, bos_list):
                    return _pack_leg(last_bear)
                origin_high = self._leg_origin_major_high(df, last_bear)
                lh_reclaimed = False
                if origin_high is not None:
                    lh_reclaimed = self._bar_body_close_above(df, last_bar, origin_high)
                else:
                    swing_h = self.detect_swing_highs(df)
                    for i in range(len(swing_h) - 1, 0, -1):
                        if swing_h[i].index <= last_bear.index:
                            continue
                        if swing_h[i].price < swing_h[i - 1].price:
                            lh_body = self._swing_body_high(df, swing_h[i].index)
                            if self._bar_body_close_above(df, last_bar, lh_body):
                                lh_reclaimed = True
                            break
                if not lh_reclaimed:
                    return _pack_leg(last_bear)

            reject_bull = False
            if (
                range_state
                and range_state.locked
                and range_state.locked_bias == 'bearish'
            ):
                lh_body = self._swing_body_high(df, range_state.macro_range_high_bar)
                if not self._bar_body_close_above(df, last_bar, lh_body):
                    reject_bull = True
            else:
                swing_h = self.detect_swing_highs(df)
                if len(swing_h) >= 2 and swing_h[-1].price < swing_h[-2].price:
                    lh_body = self._swing_body_high(df, swing_h[-1].index)
                    if close <= lh_body:
                        reject_bull = True
                if not reject_bull and self.macro_trend_from_swings(df) == 'bearish':
                    for i in range(len(swing_h) - 1, 0, -1):
                        if swing_h[i].price < swing_h[i - 1].price:
                            lh_body = self._swing_body_high(df, swing_h[i].index)
                            if not self._bar_body_close_above(df, last_bar, lh_body):
                                reject_bull = True
                            break
            if reject_bull:
                bear = _bearish_authority()
                if bear:
                    return bear
                return None, 'reversal', 'bearish', None

            if (
                not self._leg_choch_still_valid(df, latest, bos_list, chochs)
                and self._leg_invalidated_by_protected_breach(df, latest)
            ):
                bear = _bearish_authority()
                if bear:
                    return bear
                return latest, 'reversal', 'bearish', latest

        if not self._leg_choch_still_valid(df, latest, bos_list, chochs):
            if latest.direction == 'bullish':
                bear = _bearish_authority()
                if bear:
                    return bear
            else:
                bear = _bearish_authority()
                if bear:
                    return bear
            return None

        return _pack_leg(latest)

    def _resolve_d1_leg(
        self,
        df: pd.DataFrame,
        chochs: List[CHoCH],
        bos_list: List,
        debug: bool = False,
        range_state: Optional[StructuralRangeState] = None,
    ) -> Tuple[Optional[object], str, str, Optional[CHoCH]]:
        """
        V66 organic SMC (body-close):
        - CHoCH flip (HL/LH lichidat) = REVERSAL dacă 0 BOS post-leg
        - BOS same-dir după CHoCH = CONTINUITY
        """
        chochs = self._dedupe_chochs_by_bar(chochs)

        v426 = self._resolve_v426_latest_flip(df, chochs, bos_list, range_state)
        if v426 is not None and v426[0] is not None:
            return v426

        leg_choch = self._find_leg_choch(df, chochs, bos_list)

        if leg_choch is not None and not self._leg_choch_still_valid(
            df, leg_choch, bos_list, chochs,
        ):
            if (
                leg_choch.direction == 'bullish'
                and self._leg_invalidated_by_protected_breach(df, leg_choch)
            ):
                return leg_choch, 'reversal', 'bearish', leg_choch
            flipped = self._resolve_post_leg_flip(df, chochs, bos_list, leg_choch, debug=debug)
            if flipped[0] is not None:
                return flipped
            leg_choch = self._find_leg_choch(df, chochs, bos_list)

        chochs, bos_list = self._demote_post_leg_choch_to_bos(leg_choch, chochs, bos_list)

        if leg_choch is None:
            flips = self._true_choch_flips(chochs)
            if flips:
                f = flips[-1]
                filtered_bos = self._filter_countertrend_pullback_bos(df, f, bos_list)
                return self._strategy_from_leg_choch(f, filtered_bos)
            return self._resolve_orphan_d1_bias(df, chochs, bos_list, range_state)

        if leg_choch is not None:
            bos_list = self._filter_countertrend_pullback_bos(df, leg_choch, bos_list)
            sig, st, trend, leg = self._strategy_from_leg_choch(leg_choch, bos_list)
            if debug:
                label = 'CONTINUATION' if st == 'continuation' else 'REVERSAL'
                print(
                    f"   📐 [V66] leg CHoCH {leg_choch.direction.upper()} "
                    f"@bar{leg_choch.index} → {label}"
                )
            return sig, st, trend, leg
