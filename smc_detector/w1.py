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


class W1Mixin:
    """V67 C: w1 mixin."""

    @staticmethod
    def _normalize_macro_bias_label(bias: str) -> Optional[str]:
        b = str(bias or '').strip().upper()
        if b in ('BULLISH', 'BUY', 'LONG'):
            return 'bullish'
        if b in ('BEARISH', 'SELL', 'SHORT'):
            return 'bearish'
        return None

    @staticmethod
    def daily_poi_inside_weekly_zone(
        daily_poi_top: Optional[float],
        daily_poi_bottom: Optional[float],
        w1_poi_top: Optional[float],
        w1_poi_bottom: Optional[float],
    ) -> bool:
        """Faza 2: middle Daily FVG trebuie în range-ul W1 POI macro."""
        if None in (daily_poi_top, daily_poi_bottom, w1_poi_top, w1_poi_bottom):
            return True
        w_lo = min(float(w1_poi_bottom), float(w1_poi_top))
        w_hi = max(float(w1_poi_bottom), float(w1_poi_top))
        d_lo = min(float(daily_poi_bottom), float(daily_poi_top))
        d_hi = max(float(daily_poi_bottom), float(daily_poi_top))
        mid = (d_lo + d_hi) / 2.0
        return w_lo <= mid <= w_hi

    def _resolve_w1_leg_pipeline(
        self,
        df_w1: 'pd.DataFrame',
        debug: bool = False,
    ):
        """W1 = același pipeline D1: major swings + filter_internal + _resolve_d1_leg."""
        import pandas as pd
        if df_w1 is None or len(df_w1) < 10:
            return None, None, 'neutral', None, None, None

        df = df_w1.iloc[-60:].copy()
        w1_det = type(self)(swing_lookback=3, atr_multiplier=self.atr_multiplier)
        w1_det._swing_highs_cache.clear()
        w1_det._swing_lows_cache.clear()

        chochs, bos_list = w1_det.detect_choch_and_bos(df)
        sh = w1_det.detect_swing_highs(df)
        sl = w1_det.detect_swing_lows(df)
        range_state = w1_det.compute_structural_range(df, sh, sl, symbol='W1_MACRO')
        chochs, bos_list, range_state = w1_det.filter_internal_range_signals(
            'W1_MACRO', df, chochs, bos_list, range_state,
        )
        latest_signal, strategy_type, current_trend, leg_choch = w1_det._resolve_d1_leg(
            df, chochs, bos_list, debug=debug, range_state=range_state,
        )
        return latest_signal, strategy_type, current_trend, leg_choch, w1_det, df

    def calculate_w1_bias(self, df_w1: 'pd.DataFrame', debug: bool = False) -> dict:
        """
        W1 macro bias — EXACT același pipeline ca D1 (_resolve_d1_leg pe pivoți majori).

        Returnează dict:
            bias, strategy_type, current_trend, last_signal_type,
            last_bos_direction, last_bos_price, last_bos_bar_idx
        """
        _empty = {
            'bias': 'NEUTRAL',
            'strategy_type': None,
            'current_trend': None,
            'last_signal_type': None,
            'last_bos_direction': None,
            'last_bos_price': None,
            'last_bos_bar_idx': None,
        }
        try:
            latest_signal, strategy_type, current_trend, leg_choch, w1_det, df = (
                self._resolve_w1_leg_pipeline(df_w1, debug=debug)
            )
            if w1_det is None or latest_signal is None or current_trend == 'neutral':
                if debug:
                    print("   🔍 [W1 BIAS] leg pipeline → NEUTRAL (fără semnal major)")
                return _empty

            bias = 'BULLISH' if current_trend == 'bullish' else 'BEARISH'
            sig_type = 'CHoCH' if isinstance(latest_signal, CHoCH) else 'BOS'
            if debug:
                chochs, bos_list = w1_det.detect_choch_and_bos(df)
                print(
                    f"   🔍 [W1 BIAS] {sig_type} {current_trend.upper()} "
                    f"@bar{latest_signal.index} → {strategy_type.upper()} → BIAS={bias}"
                )
                if leg_choch is not None:
                    print(
                        f"   🔍 [W1 LEG] leg CHoCH {leg_choch.direction.upper()} "
                        f"@bar{leg_choch.index}"
                    )

            return {
                'bias': bias,
                'strategy_type': strategy_type,
                'current_trend': current_trend,
                'last_signal_type': sig_type,
                'last_bos_direction': latest_signal.direction,
                'last_bos_price': float(latest_signal.break_price),
                'last_bos_bar_idx': latest_signal.index,
            }
        except Exception as e:
            print(f"⚠️ [W1 BIAS] Error: {e}")
            return _empty

    def resolve_w1_poi(
        self,
        df_w1: 'pd.DataFrame',
        w1_bias: str,
        debug: bool = False,
    ) -> Optional[dict]:
        """
        Faza 1: FVG/OB organic W1 în Premium/Discount (V16.1).
        Fallback: bandă macro P/D (50% din range weekly) când lipsește FVG.
        """
        w1_norm = (w1_bias or 'NEUTRAL').upper()
        if w1_norm == 'NEUTRAL':
            return None

        latest_signal, strategy_type, current_trend, _, w1_det, df = (
            self._resolve_w1_leg_pipeline(df_w1, debug=debug)
        )
        if w1_det is None or latest_signal is None:
            return None

        orderflow = 'bullish' if w1_norm == 'BULLISH' else 'bearish'
        fvg = w1_det.detect_fvg(df, latest_signal, strategy_type=strategy_type)
        poi_source = 'w1_fvg'

        if fvg is not None:
            w1_top = float(fvg.top)
            w1_bottom = float(fvg.bottom)
        else:
            macro_high, macro_low, premium_threshold, discount_threshold = (
                w1_det.calculate_premium_discount_zones(df)
            )
            eq = (macro_low + macro_high) / 2.0
            if orderflow == 'bullish':
                w1_bottom = float(macro_low)
                w1_top = float(eq)
            else:
                w1_bottom = float(eq)
                w1_top = float(macro_high)
            poi_source = 'w1_pd_band'

        if debug:
            print(
                f"   📅 [W1 POI] {poi_source} zone "
                f"{min(w1_bottom, w1_top):.5f} – {max(w1_bottom, w1_top):.5f} "
                f"({w1_norm} macro)"
            )

        return {
            'w1_poi_top': max(w1_top, w1_bottom),
            'w1_poi_bottom': min(w1_top, w1_bottom),
            'w1_poi_source': poi_source,
        }

    def evaluate_w_d_sync(
        self,
        d1_direction: str,
        w1_bias: str,
        daily_poi_top: Optional[float],
        daily_poi_bottom: Optional[float],
        w1_poi_top: Optional[float] = None,
        w1_poi_bottom: Optional[float] = None,
        current_price: Optional[float] = None,
    ) -> dict:
        """
        Faza 2: clasificare W+D — soft wait, fără reject hard.
        Returnează w_d_aligned, status (optional override), reason.
        """
        w1_dir = self._normalize_macro_bias_label(w1_bias)
        d1_dir = self._normalize_macro_bias_label(d1_direction)

        if w1_dir is None:
            return {'w_d_aligned': True, 'status': None, 'reason': 'w1_neutral'}

        w_d_aligned = w1_dir == d1_dir
        if not w_d_aligned:
            return {
                'w_d_aligned': False,
                'status': 'WAITING_W_D_SYNC',
                'reason': f'W1={w1_bias} vs D1={d1_direction}',
            }

        if w1_poi_top is not None and w1_poi_bottom is not None:
            if not self.daily_poi_inside_weekly_zone(
                daily_poi_top, daily_poi_bottom, w1_poi_top, w1_poi_bottom,
            ):
                return {
                    'w_d_aligned': True,
                    'status': 'WAITING_D1_PULLBACK',
                    'reason': 'daily_poi_outside_w1_macro_zone',
                }
            if current_price is not None:
                w_lo = min(float(w1_poi_bottom), float(w1_poi_top))
                w_hi = max(float(w1_poi_bottom), float(w1_poi_top))
                if not (w_lo <= float(current_price) <= w_hi):
                    return {
                        'w_d_aligned': True,
                        'status': 'WAITING_W_ZONE',
                        'reason': 'price_outside_w1_poi',
                    }

        return {'w_d_aligned': True, 'status': None, 'reason': 'w_d_aligned'}

    @staticmethod
    def resolve_status_after_w_d_sync(current_status: str, sync: dict) -> str:
        """
        Promote or set status from evaluate_w_d_sync result.
        Fixes sticky WAITING_W_D_SYNC when W+D become aligned (status None).
        """
        current = str(current_status or '')
        w_d_aligned = bool(sync.get('w_d_aligned', True))
        sync_status = sync.get('status')

        if sync_status == 'WAITING_W_D_SYNC':
            return 'WAITING_W_D_SYNC'
        if sync_status:
            return str(sync_status)
        if w_d_aligned and current in ('WAITING_W_D_SYNC', 'WAITING_W_ZONE'):
            return 'MONITORING'
        return current

    def apply_w_d_sync_gate(
        self,
        setup: Optional['TradeSetup'],
        w1_bias: str,
        w1_poi: Optional[dict] = None,
        current_price: Optional[float] = None,
    ) -> Optional['TradeSetup']:
        """Faza 2: aplică W+D soft sync pe TradeSetup (status + câmpuri JSON)."""
        if setup is None or not getattr(setup, 'daily_choch', None):
            return setup

        sym = getattr(setup, 'symbol', '?')
        setup.w1_bias = (w1_bias or 'NEUTRAL').upper()

        if w1_poi:
            setup.w1_poi_top = w1_poi.get('w1_poi_top')
            setup.w1_poi_bottom = w1_poi.get('w1_poi_bottom')

        d1_top = setup.fvg.top if setup.fvg else None
        d1_bottom = setup.fvg.bottom if setup.fvg else None
        sync = self.evaluate_w_d_sync(
            setup.daily_choch.direction,
            setup.w1_bias,
            d1_top,
            d1_bottom,
            setup.w1_poi_top,
            setup.w1_poi_bottom,
            current_price=current_price,
        )
        setup.w_d_aligned = bool(sync.get('w_d_aligned', True))
        _prev_status = getattr(setup, 'status', '') or ''
        setup.status = self.resolve_status_after_w_d_sync(_prev_status, sync)

        if setup.status == 'WAITING_W_D_SYNC':
            setup.confidence = 'LOW_W1_COUNTER_TREND'
            print(
                f"⏸️ [W+D SOFT SYNC] {sym}: {sync.get('reason')} — "
                f"monitor only, zero EXECUTE_NOW"
            )
        elif sync.get('status') and setup.status != _prev_status:
            if debug_msg := sync.get('reason'):
                print(f"   📅 [W+D] {sym}: {setup.status} ({debug_msg})")
        elif (
            setup.w_d_aligned
            and _prev_status == 'WAITING_W_D_SYNC'
            and setup.status == 'MONITORING'
        ):
            setup.confidence = 'NORMAL'
            print(f"   ✅ [W+D SYNC] {sym}: WAITING_W_D_SYNC → MONITORING (W+D aligned)")
        elif setup.w_d_aligned and setup.confidence == 'LOW_W1_COUNTER_TREND':
            setup.confidence = 'NORMAL'

        return setup

    def apply_w1_gate(self, setup: Optional['TradeSetup'], w1_bias: str) -> Optional['TradeSetup']:
        return self.apply_w_d_sync_gate(setup, w1_bias)
