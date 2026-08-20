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
        if current_trend == 'neutral':
            fallback = self.resolve_structural_bias_fallback(
                df, chochs, bos_list, range_state,
            )
            if fallback != 'neutral':
                current_trend = fallback
                if leg_choch is None:
                    strategy_type = 'continuation'

        # V68 Pilon 1: BOS-only pullback vs macro HH+HL / LH+LL — macro wins when leg absent
        if (
            leg_choch is None
            and macro_swings in ('bullish', 'bearish')
            and current_trend in ('bullish', 'bearish')
            and current_trend != macro_swings
        ):
            current_trend = macro_swings
            strategy_type = 'continuation'
            aligned = [b for b in bos_list if b.direction == macro_swings]
            if aligned:
                latest = aligned[-1]

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

    def _resolve_d1_leg(
        self,
        df: pd.DataFrame,
        chochs: List[CHoCH],
        bos_list: List,
        debug: bool = False,
        range_state: Optional[StructuralRangeState] = None,
    ) -> Tuple[Optional[object], str, str, Optional[CHoCH]]:
        """Pure symmetric SMC D1 — major pivots, body-close, pullback/flip rules."""
        return self._resolve_pure_d1_matrix(
            df, chochs, bos_list, debug=debug, range_state=range_state,
        )
