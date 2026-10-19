from __future__ import annotations

import pandas as pd
from typing import Dict, List, Optional, Tuple

from smc_detector.models import (
    BOS,
    CHoCH,
    D1AuthContext,
)


class D1AuthorityMixin:
    """V67 C: canonical D1 authority (V74 sequential state machine)."""

    def build_d1_context(
        self,
        df: pd.DataFrame,
        symbol: str = '?',
        debug: bool = False,
    ) -> D1AuthContext:
        """V74: D1 bias = final state of sequential SMC state machine on closed bars."""
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
            protected_low=None,
            protected_high=None,
        )
        if df is None or df.empty:
            return empty
        if not {'open', 'high', 'low', 'close'}.issubset(df.columns):
            return empty

        df_struct = self.d1_closed_structure_df(df)
        if df_struct is None or df_struct.empty:
            return empty

        sm = self.run_d1_smc_state_machine(df_struct, debug=debug)
        current_trend = sm['trend']
        latest = sm['latest_signal']
        strategy_type = sm['strategy_type']
        leg_choch = sm['leg_choch']
        chochs = sm['chochs']
        bos_list = sm['bos_list']

        swing_h = self.detect_swing_highs(df_struct)
        swing_l = self.detect_swing_lows(df_struct)
        range_state = self.compute_structural_range(
            df_struct, swing_h, swing_l, symbol=symbol,
        )

        macro_swings = current_trend if current_trend in ('bullish', 'bearish') else (
            self.macro_trend_from_swings(df_struct)
        )

        trade_dir = ''
        if current_trend == 'bullish':
            trade_dir = 'buy'
        elif current_trend == 'bearish':
            trade_dir = 'sell'

        d1_signal_type = 'CHoCH' if strategy_type == 'reversal' else 'BOS'

        if bos_list and current_trend in ('bullish', 'bearish'):
            same_dir_bos = [b for b in bos_list if getattr(b, 'direction', '') == current_trend]
            if same_dir_bos:
                strategy_type = 'continuation'
                d1_signal_type = 'BOS'
                latest = same_dir_bos[-1]

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
            protected_low=sm.get('protected_low'),
            protected_high=sm.get('protected_high'),
        )

    def resolve_authoritative_d1_bias(
        self,
        df: pd.DataFrame,
        symbol: str = '?',
    ) -> dict:
        """Single source of truth for D1 direction/strategy."""
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
        range_state=None,
    ) -> Tuple[Optional[object], str, str, Optional[CHoCH]]:
        """Scan fallback — V74 state machine snapshot."""
        sm = self.run_d1_smc_state_machine(df, debug=debug)
        return (
            sm['latest_signal'],
            sm['strategy_type'],
            sm['trend'],
            sm['leg_choch'],
        )
