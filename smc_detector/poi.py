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


class PoiMixin:
    """V67 C: D1 POI resolution."""

    def detect_order_block(
        self, 
        df: pd.DataFrame, 
        choch: CHoCH, 
        fvg: Optional[FVG] = None,
        debug: bool = False
    ) -> Optional['OrderBlock']:
        """
        🎯 V3.5 ORDER BLOCKS: Detectează ultima lumânare opusă înainte de impuls
        
        LOGIC:
        1. Găsește CHoCH (break of structure)
        2. Identifică ultima lumânare OPUSĂ înainte de impuls (Order Block)
        3. Verifică dacă impulsul a lăsat FVG (validare instituțională)
        4. Scorează OB (10/10 dacă FVG necompletat lângă el)
        
        Args:
            df: DataFrame with OHLC data
            choch: CHoCH object (break point)
            fvg: Optional FVG object (pentru corelație)
            debug: Print debug info
        
        Returns:
            OrderBlock object or None
        """
        if choch is None:
            return None
        
        choch_idx = choch.index
        
        # STEP 1: Identifică ultima lumânare OPUSĂ înainte de CHoCH
        # Bullish CHoCH → căutăm ultima lumânare BEARISH (red candle)
        # Bearish CHoCH → căutăm ultima lumânare BULLISH (green candle)
        
        # Lookback range: 10 candele înainte de CHoCH (suficient pentru OB detection)
        lookback_start = max(0, choch_idx - 10)
        
        ob_candle_idx = None
        
        if choch.direction == 'bullish':
            # Căutăm ultima lumânare BEARISH (close < open)
            for i in range(choch_idx - 1, lookback_start - 1, -1):
                if df['close'].iloc[i] < df['open'].iloc[i]:
                    ob_candle_idx = i
                    break
        
        elif choch.direction == 'bearish':
            # Căutăm ultima lumânare BULLISH (close > open)
            for i in range(choch_idx - 1, lookback_start - 1, -1):
                if df['close'].iloc[i] > df['open'].iloc[i]:
                    ob_candle_idx = i
                    break
        
        if ob_candle_idx is None:
            if debug:
                print(f"   ⚠️ No Order Block found (no opposite candle before CHoCH)")
            return None
        
        # STEP 2: Extrage zonă Order Block
        # Bullish OB (după bearish candle): Body high + Wick low
        # Bearish OB (după bullish candle): Wick high + Body low
        
        ob_open = df['open'].iloc[ob_candle_idx]
        ob_close = df['close'].iloc[ob_candle_idx]
        ob_high = df['high'].iloc[ob_candle_idx]
        ob_low = df['low'].iloc[ob_candle_idx]
        ob_time = df['time'].iloc[ob_candle_idx] if 'time' in df.columns else ob_candle_idx
        
        if choch.direction == 'bullish':
            # Bullish OB: Body high to Wick low (zone unde price se va întoarce)
            ob_top = max(ob_open, ob_close)  # Body high
            ob_bottom = ob_low  # Wick low
        else:
            # Bearish OB: Wick high to Body low
            ob_top = ob_high  # Wick high
            ob_bottom = min(ob_open, ob_close)  # Body low
        
        ob_middle = (ob_top + ob_bottom) / 2
        
        # STEP 3: Calculează impulse strength (mărimea mișcării după OB)
        impulse_start = ob_candle_idx
        impulse_end = min(choch_idx + 5, len(df) - 1)  # 5 candele după CHoCH
        
        if choch.direction == 'bullish':
            impulse_high = df['high'].iloc[impulse_start:impulse_end].max()
            impulse_strength = impulse_high - ob_bottom
        else:
            impulse_low = df['low'].iloc[impulse_start:impulse_end].min()
            impulse_strength = ob_top - impulse_low
        
        impulse_strength_pct = (impulse_strength / ob_middle) * 100
        
        # STEP 4: Verifică corelație cu FVG (OB + unfilled FVG = SCOR 10/10)
        has_unfilled_fvg = False
        ob_score = 5  # Base score
        
        if fvg is not None:
            # Verifică dacă FVG este LÂNGĂ Order Block (gap < 50 pips sau overlap)
            fvg_distance = abs(fvg.middle - ob_middle)
            ob_size = ob_top - ob_bottom
            
            # Proximity check: FVG în raza de 2x mărimea OB
            is_proximate = fvg_distance < (ob_size * 2)
            
            # Verifică dacă FVG este NECOMPLETAT (unfilled)
            if not fvg.is_filled and is_proximate:
                has_unfilled_fvg = True
                ob_score = 10  # PERFECT SETUP!
            elif is_proximate:
                ob_score = 8  # FVG filled dar proxim
            else:
                ob_score = 6  # FVG exists dar departe
        
        # STEP 5: Bonus pentru impuls puternic (>1% move)
        if impulse_strength_pct > 1.0:
            ob_score = min(10, ob_score + 1)
        
        # STEP 6: Creează Order Block object
        order_block = OrderBlock(
            index=ob_candle_idx,
            direction=choch.direction,
            top=ob_top,
            bottom=ob_bottom,
            middle=ob_middle,
            candle_time=ob_time,
            associated_choch=choch,
            associated_fvg=fvg,
            has_unfilled_fvg=has_unfilled_fvg,
            ob_score=ob_score,
            impulse_strength=impulse_strength_pct
        )
        
        if debug:
            print(f"\n📦 ORDER BLOCK DETECTED:")
            print(f"   Direction: {choch.direction.upper()}")
            print(f"   Zone: {ob_bottom:.5f} - {ob_top:.5f} (Middle: {ob_middle:.5f})")
            print(f"   Impulse Strength: {impulse_strength_pct:.2f}%")
            print(f"   FVG Correlation: {'✅ UNFILLED FVG!' if has_unfilled_fvg else '⚠️ No FVG' if fvg is None else 'FVG filled'}")
            print(f"   OB Score: {ob_score}/10")
        
        return order_block

    def build_active_dealing_range(
        self,
        df: pd.DataFrame,
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint],
        leg_anchor_index: int,
        current_trend: str,
        range_state: Optional[StructuralRangeState] = None,
        symbol: Optional[str] = None,
        debug: bool = False,
    ) -> Optional[ActiveDealingRange]:
        """V43.0 ADR — dynamic impulse bounds after latest valid D1 BOS/CHoCH.

        V43.4: last_lh / last_ll / last_hl from chronological HH→HL or LH→LL pairs
        post-anchor (not decoupled old LH + recent LL).
        """
        if df is None or len(df) < 5:
            return None

        anchor = max(0, int(leg_anchor_index))
        post_highs = [h for h in swing_highs if h.index >= anchor]
        post_lows = [l for l in swing_lows if l.index >= anchor]

        if not post_highs and swing_highs:
            post_highs = swing_highs[-3:]
        if not post_lows and swing_lows:
            post_lows = swing_lows[-3:]

        close = float(df['close'].iloc[-1])
        trend = (current_trend or 'neutral').lower()

        last_ll = last_lh = last_hl = None
        last_ll_bar = last_lh_bar = last_hl_bar = anchor

        # V43.4: paired pivots from chronological post-anchor swings (not decoupled LH-old + LL-recent)
        high_sp = low_sp = None
        if trend == 'bullish':
            hh_sp = None
            for i in range(1, len(post_highs)):
                if post_highs[i].price > post_highs[i - 1].price:
                    hh_sp = post_highs[i]
            if hh_sp is None and post_highs:
                hh_sp = post_highs[-1]
            hl_sp = None
            if hh_sp is not None:
                lows_after_hh = [l for l in post_lows if l.index > hh_sp.index]
                for i in range(1, len(lows_after_hh)):
                    if lows_after_hh[i].price > lows_after_hh[i - 1].price:
                        hl_sp = lows_after_hh[i]
                if hl_sp is None and lows_after_hh:
                    hl_sp = max(
                        lows_after_hh,
                        key=lambda l: self._swing_body_low(df, l.index),
                    )
                elif hl_sp is None:
                    prior = [l for l in post_lows if l.index <= hh_sp.index]
                    if prior and hh_sp.index > prior[-1].index:
                        if len(prior) >= 2 and prior[-1].price > prior[-2].price:
                            hl_sp = prior[-1]
            high_sp, low_sp = hh_sp, hl_sp
        else:
            lh_sp = None
            for i in range(1, len(post_highs)):
                if post_highs[i].price < post_highs[i - 1].price:
                    lh_sp = post_highs[i]
            if lh_sp is None and post_highs:
                lh_sp = post_highs[-1]
            ll_sp = None
            if lh_sp is not None:
                lows_after_lh = [l for l in post_lows if l.index > lh_sp.index]
                for i in range(1, len(lows_after_lh)):
                    if lows_after_lh[i].price < lows_after_lh[i - 1].price:
                        ll_sp = lows_after_lh[i]
                if ll_sp is None and lows_after_lh:
                    ll_sp = min(
                        lows_after_lh,
                        key=lambda l: self._swing_body_low(df, l.index),
                    )
                elif ll_sp is None:
                    prior = [l for l in post_lows if l.index <= lh_sp.index]
                    if prior and lh_sp.index > prior[-1].index:
                        if len(prior) >= 2 and prior[-1].price < prior[-2].price:
                            ll_sp = prior[-1]
            high_sp, low_sp = lh_sp, ll_sp

        if high_sp is not None:
            last_lh = self._swing_body_high(df, high_sp.index)
            last_lh_bar = high_sp.index
        if low_sp is not None:
            body_low = self._swing_body_low(df, low_sp.index)
            if trend == 'bullish':
                last_hl = body_low
                last_hl_bar = low_sp.index
            else:
                last_ll = body_low
                last_ll_bar = low_sp.index
        if post_lows:
            ll_tail = post_lows[-1]
            if trend == 'bullish' and last_hl is not None:
                last_ll = last_hl
                last_ll_bar = last_hl_bar
            elif last_ll is None:
                last_ll = self._swing_body_low(df, ll_tail.index)
                last_ll_bar = ll_tail.index
            if trend == 'bullish' and last_hl is None:
                last_hl = self._swing_body_low(df, ll_tail.index)
                last_hl_bar = ll_tail.index

        if range_state is not None and (
            last_ll is None or last_lh is None or last_ll >= last_lh
        ):
            last_ll = last_ll if last_ll is not None else range_state.macro_range_low
            last_lh = last_lh if last_lh is not None else range_state.macro_range_high
            last_ll_bar = range_state.macro_range_low_bar
            last_lh_bar = range_state.macro_range_high_bar
            if last_hl is None:
                last_hl = last_ll

        if last_ll is None or last_lh is None or last_ll >= last_lh:
            return None

        if trend == 'bullish':
            c_high = last_lh
            c_low = last_hl if last_hl is not None else last_ll
            c_high_bar = last_lh_bar
            c_low_bar = last_hl_bar if last_hl is not None else last_ll_bar
        else:
            c_high = last_lh
            c_low = last_ll
            c_high_bar = last_lh_bar
            c_low_bar = last_ll_bar

        if c_low >= c_high:
            return None

        price_inside = c_low <= close <= c_high
        _sym = symbol or ''
        if debug:
            print(
                f"   📐 [V43.0 ADR] {_sym}: container [{c_low:.5f} – {c_high:.5f}] "
                f"| close={close:.5f} {'INSIDE' if price_inside else 'OUTSIDE'} "
                f"| anchor=bar{anchor}"
            )

        return ActiveDealingRange(
            container_low=c_low,
            container_high=c_high,
            current_swing_high=c_high,
            current_swing_low=c_low,
            last_lh=last_lh,
            last_hl=last_hl if last_hl is not None else last_ll,
            last_ll=last_ll,
            current_swing_high_bar=c_high_bar,
            current_swing_low_bar=c_low_bar,
            leg_anchor_index=anchor,
            price_inside=price_inside,
        )

    @staticmethod
    def poi_conflicts_with_continuation(
        poi_top: float,
        poi_bottom: float,
        direction: str,
        adr: ActiveDealingRange,
    ) -> bool:
        """V43.0 anti-zombie: POI invalid for continuation if it breaks protected structure."""
        d = (direction or '').lower()
        if d == 'bearish':
            return float(poi_bottom) > float(adr.current_swing_high)
        if d == 'bullish':
            return float(poi_top) < float(adr.current_swing_low)
        return False

    @staticmethod
    def should_preserve_stored_poi(
        stored_poi_top: Optional[float],
        stored_poi_bottom: Optional[float],
        direction: str,
        strategy_type: str,
        adr: ActiveDealingRange,
        current_price: float,
    ) -> bool:
        """V43.0 — signal only; JSON write is daily_scanner (Etapa 2)."""
        if (strategy_type or '').lower() != 'continuation':
            return False
        if stored_poi_top is None or stored_poi_bottom is None:
            return False
        # V43.4: flip bearish — nu păstra POI bullish vechi din JSON
        if (direction or '').lower() == 'bearish' and float(current_price) < float(stored_poi_bottom):
            return False
        if not adr.price_inside:
            return False
        price = float(current_price)
        if price < adr.container_low or price > adr.container_high:
            return False
        return not PoiMixin.poi_conflicts_with_continuation(
            float(stored_poi_top),
            float(stored_poi_bottom),
            direction,
            adr,
        )

    @staticmethod
    def compute_structural_breach(
        close: float,
        current_trend: str,
        adr: Optional[ActiveDealingRange],
    ) -> bool:
        """V43.0 E1-T7 — passive breach flag when daily close breaks protected ADR bound."""
        if adr is None:
            return False
        price = float(close)
        trend = (current_trend or '').lower()
        if trend == 'bearish' and price > float(adr.current_swing_high):
            return True
        if trend == 'bullish' and price < float(adr.current_swing_low):
            return True
        return False

    @staticmethod
    def _fvg_within_adr(fvg: FVG, adr: ActiveDealingRange, orderflow_direction: str) -> bool:
        """Truncated scan: FVG must overlap ADR container."""
        d = (orderflow_direction or '').lower()
        if d == 'bearish':
            return (
                float(fvg.bottom) <= float(adr.current_swing_high)
                and float(fvg.top) >= float(adr.container_low)
            )
        if d == 'bullish':
            return (
                float(fvg.top) >= float(adr.current_swing_low)
                and float(fvg.bottom) <= float(adr.container_high)
            )
        return True

    def _fvg_body_mitigated(self, df: pd.DataFrame, fvg: FVG) -> bool:
        """True dacă body close a mitigat FVG-ul (>20% buffer)."""
        body_highs = df[['open', 'close']].max(axis=1)
        body_lows = df[['open', 'close']].min(axis=1)
        fvg_size = fvg.top - fvg.bottom
        mitigation_buffer = fvg_size * 0.20
        for j in range(fvg.index + 1, len(df)):
            body_high = body_highs.iloc[j]
            body_low = body_lows.iloc[j]
            if fvg.direction == 'bullish':
                if body_low < fvg.bottom - mitigation_buffer:
                    return True
            elif body_high > fvg.top + mitigation_buffer:
                return True
        return False

    def _scan_organic_fvgs(
        self,
        df: pd.DataFrame,
        start_idx: int,
        end_idx: int,
        direction: str,
    ) -> List[FVG]:
        """FVG-uri organice wick-to-wick în interval [start_idx, end_idx]."""
        fvgs: List[FVG] = []
        search_end = min(end_idx, len(df) - 1)
        for i in range(max(start_idx + 1, 1), search_end):
            if direction == 'bullish':
                if df['high'].iloc[i - 1] < df['low'].iloc[i + 1]:
                    gap_top = df['low'].iloc[i + 1]
                    gap_bottom = df['high'].iloc[i - 1]
                    gap_size = gap_top - gap_bottom
                    if gap_size > 0 and (gap_size / gap_bottom) >= 0.0005:
                        fvgs.append(FVG(
                            index=i,
                            direction='bullish',
                            top=gap_top,
                            bottom=gap_bottom,
                            middle=(gap_top + gap_bottom) / 2,
                            candle_time=df['time'].iloc[i] if 'time' in df.columns else i,
                            is_filled=False,
                        ))
            elif df['low'].iloc[i - 1] > df['high'].iloc[i + 1]:
                gap_top = df['low'].iloc[i - 1]
                gap_bottom = df['high'].iloc[i + 1]
                gap_size = gap_top - gap_bottom
                if gap_size > 0 and (gap_size / gap_bottom) >= 0.0005:
                    fvgs.append(FVG(
                        index=i,
                        direction='bearish',
                        top=gap_top,
                        bottom=gap_bottom,
                        middle=(gap_top + gap_bottom) / 2,
                        candle_time=df['time'].iloc[i] if 'time' in df.columns else i,
                        is_filled=False,
                    ))
        return fvgs

    def _impulse_equilibrium(self, df: pd.DataFrame, signal) -> Tuple[Optional[float], int, int]:
        """Equilibrium 50% din impulsul semnalului (origine → break)."""
        sig_idx = signal.index if hasattr(signal, 'index') else 0
        direction = getattr(signal, 'direction', '') or ''
        origin_idx = max(0, sig_idx - 20)
        equilibrium = None
        origin_price = None
        break_price = float(getattr(signal, 'break_price', 0) or 0)

        if hasattr(signal, 'swing_broken') and signal.swing_broken is not None:
            try:
                origin_price = float(signal.swing_broken.price)
                if hasattr(signal.swing_broken, 'index'):
                    origin_idx = int(signal.swing_broken.index)
            except Exception:
                origin_price = None

        if origin_price is None and direction in ('bullish', 'bearish'):
            swing_highs = self.detect_swing_highs(df)
            swing_lows = self.detect_swing_lows(df)
            if direction == 'bearish':
                prior_lows = [l for l in swing_lows if l.index < sig_idx]
                prior_highs = [h for h in swing_highs if h.index < sig_idx]
                if prior_lows:
                    origin_price = float(prior_lows[-1].price)
                    origin_idx = prior_lows[-1].index
                elif prior_highs:
                    origin_price = float(prior_highs[-1].price)
                    origin_idx = prior_highs[-1].index
            else:
                prior_highs = [h for h in swing_highs if h.index < sig_idx]
                prior_lows = [l for l in swing_lows if l.index < sig_idx]
                if prior_highs:
                    origin_price = float(prior_highs[-1].price)
                    origin_idx = prior_highs[-1].index
                elif prior_lows:
                    origin_price = float(prior_lows[-1].price)
                    origin_idx = prior_lows[-1].index

        if origin_price is not None and break_price and abs(break_price - origin_price) > 0:
            equilibrium = (origin_price + break_price) / 2.0

        return equilibrium, origin_idx, sig_idx

    def _fvg_in_pd_zone(self, fvg: FVG, equilibrium: float, direction: str) -> bool:
        if equilibrium is None:
            return True
        if direction == 'bullish':
            return fvg.middle < equilibrium
        return fvg.middle > equilibrium

    def _resolve_continuation_poi_cascade(
        self,
        df: pd.DataFrame,
        latest_signal,
        current_trend: str,
        adr: Optional[ActiveDealingRange],
        audit_out: Optional[dict] = None,
    ) -> Optional[FVG]:
        """
        CONTINUITY: dacă primul FVG post-BOS e mitigat, caută în cascadă:
          (a) ultimul FVG organic ne-mitigat din impulsul major
          (b) Order Block organic la originea impulsului
        """
        direction = (current_trend or getattr(latest_signal, 'direction', '') or '').lower()
        if direction not in ('bullish', 'bearish'):
            return None

        equilibrium, origin_idx, sig_idx = self._impulse_equilibrium(df, latest_signal)
        scan_end = min(len(df) - 1, sig_idx + 40)
        all_fvgs = self._scan_organic_fvgs(df, origin_idx, scan_end, direction)
        impulse_fvgs = [f for f in all_fvgs if origin_idx <= f.index <= scan_end]

        unmitigated = [f for f in impulse_fvgs if not self._fvg_body_mitigated(df, f)]
        pd_unmitigated = [
            f for f in unmitigated
            if self._fvg_in_pd_zone(f, equilibrium, direction)
        ]

        selected: Optional[FVG] = None
        reason = 'no cascade POI'

        if pd_unmitigated:
            pd_unmitigated.sort(key=lambda f: (f.index, f.top - f.bottom), reverse=True)
            selected = pd_unmitigated[0]
            reason = 'continuation cascade: unmitigated FVG in impulse P/D'
        else:
            # (b) OB la originea impulsului — semnalul BOS/CHoCH ancorat pe impuls
            pseudo_choch = latest_signal
            if not isinstance(latest_signal, CHoCH):
                pseudo_choch = CHoCH(
                    index=latest_signal.index,
                    direction=direction,
                    break_price=float(latest_signal.break_price),
                    previous_trend='bearish' if direction == 'bullish' else 'bullish',
                    candle_time=getattr(latest_signal, 'candle_time', None),
                    swing_broken=getattr(latest_signal, 'swing_broken', None),
                )
            ob = self.detect_order_block(df, pseudo_choch, fvg=None, debug=False)
            if ob is not None:
                ob_top, ob_bottom = float(ob.top), float(ob.bottom)
                if ob_bottom < ob_top:
                    mid = (ob_top + ob_bottom) / 2.0
                    if self._fvg_in_pd_zone(
                        FVG(
                            index=ob.index, direction=direction,
                            top=ob_top, bottom=ob_bottom, middle=mid,
                            candle_time=ob.candle_time, is_filled=False,
                        ),
                        equilibrium,
                        direction,
                    ):
                        selected = FVG(
                            index=ob.index,
                            direction=direction,
                            top=ob_top,
                            bottom=ob_bottom,
                            middle=mid,
                            candle_time=ob.candle_time,
                            is_filled=False,
                            associated_choch=pseudo_choch if isinstance(pseudo_choch, CHoCH) else None,
                        )
                        reason = 'continuation cascade: impulse origin OB in P/D'

        if audit_out is not None:
            audit_out['continuation_cascade'] = {
                'reason': reason,
                'origin_idx': origin_idx,
                'signal_idx': sig_idx,
                'equilibrium': round(float(equilibrium), 5) if equilibrium else None,
                'unmitigated_count': len(unmitigated),
                'pd_unmitigated_count': len(pd_unmitigated),
                'selected': self.fvg_audit_entry(selected) if selected else None,
            }

        if selected is not None and audit_out is not None:
            audit_out.setdefault('continuation_cascade', {})['logged'] = True
        return selected

    def resolve_d1_poi(
        self,
        df: pd.DataFrame,
        latest_signal,
        current_price: float,
        current_trend: str,
        strategy_type: str,
        adr: Optional[ActiveDealingRange],
        symbol: str = '',
        stored_poi_top: Optional[float] = None,
        stored_poi_bottom: Optional[float] = None,
        audit_out: Optional[dict] = None,
        debug: bool = False,
    ) -> POIResolution:
        """Faza A — POI organic only; no JSON preserve, no synthetic Equilibrium clip."""
        _ = (current_price, stored_poi_top, stored_poi_bottom)
        meta: dict = {
            'adr': None,
            'preserve_stored_poi': False,
            'poi_source': 'detect_fvg',
            'poi_zombie': False,
            'adr_rescan': False,
        }
        if audit_out is not None:
            audit_out['v43'] = meta

        if adr is not None:
            meta['adr'] = {
                'container_low': round(adr.container_low, 5),
                'container_high': round(adr.container_high, 5),
                'current_swing_high': round(adr.current_swing_high, 5),
                'current_swing_low': round(adr.current_swing_low, 5),
                'price_inside': adr.price_inside,
            }

        fvg_audit: dict = {}
        selected = self.detect_fvg(
            df,
            latest_signal,
            audit_out=fvg_audit,
            strategy_type=strategy_type,
            dealing_range=adr,
        )
        if (
            selected is None
            and (strategy_type or '').lower() == 'continuation'
        ):
            selected = self._resolve_continuation_poi_cascade(
                df,
                latest_signal,
                current_trend,
                adr,
                audit_out=fvg_audit,
            )
            if selected is not None:
                meta['poi_source'] = fvg_audit.get(
                    'continuation_cascade', {},
                ).get('reason', 'continuation cascade POI')
        if audit_out is not None:
            audit_out.update(fvg_audit)

        if selected is None:
            meta['poi_source'] = 'no organic FVG'
            if symbol and debug:
                print(f"   ⏸️ [Faza A] {symbol}: no organic FVG in P/D — WAITING_D1_PULLBACK")

        poi_zombie = bool(fvg_audit.get('v43', {}).get('poi_zombie'))
        rejected = fvg_audit.get('v43', {}).get('rejected')
        rejected_top = rejected_bottom = None
        if rejected:
            rejected_top = rejected.get('top')
            rejected_bottom = rejected.get('bottom')

        if audit_out is not None:
            meta['poi_source'] = fvg_audit.get('selection_reason', meta['poi_source'])
            audit_out['v43'] = {**meta, **fvg_audit.get('v43', {})}

        return POIResolution(
            fvg=selected,
            adr=adr,
            preserve_stored_poi=False,
            poi_source=meta.get('poi_source', 'detect_fvg'),
            poi_zombie=poi_zombie,
            adr_rescan=bool(fvg_audit.get('v43', {}).get('force_in_range_rescan')),
            rejected_poi_top=rejected_top,
            rejected_poi_bottom=rejected_bottom,
        )

    def calculate_premium_discount_zones(self, df: pd.DataFrame) -> Tuple[float, float, float, float]:
        """
        🆕 V6.2: Calculate Premium and Discount zones based on macro swing range
        
        Premium Zone: Top 40% of macro range (61.8% - 100% Fib levels)
        Equilibrium: Middle 20% of macro range (40% - 60% Fib levels)  
        Discount Zone: Bottom 40% of macro range (0% - 38.2% Fib levels)
        
        Used to validate reversal setups:
        - Bullish Reversal (BUY) only allowed from Discount zone
        - Bearish Reversal (SELL) only allowed from Premium zone
        
        Returns:
            (macro_high, macro_low, premium_threshold, discount_threshold)
        """
        if df is None or len(df) < 20:
            return (0, 0, 0, 0)
        
        # V24.1: Macro range calculat din prețuri reale (df high/low) pe 150 bare
        # 150 bare Daily = ~7 luni = Dealing Range instituțional optim pentru Fibonacci 55/45
        # 100 bare (4 luni) era prea scurt — rata rateuri la zone majore HTF
        # 200+ bare (10 luni) ar da zone prea largi, greu de atins în swing trading
        macro_lookback = min(150, len(df))
        df_macro = df.iloc[-macro_lookback:]
        
        # ✅ V10.4: Folosim max/min din prețuri reale, nu swing points filtrate
        macro_high = df_macro['high'].max()
        macro_low  = df_macro['low'].min()
        
        # Calculate range
        macro_range = macro_high - macro_low
        
        # ✅ V10.3/V10.4: Fibonacci thresholds 55%/45% (relaxate de la 61.8%/38.2%)
        premium_threshold = macro_low + (macro_range * 0.55)
        
        # Discount threshold = 45% Fib level
        discount_threshold = macro_low + (macro_range * 0.45)
        
        return (macro_high, macro_low, premium_threshold, discount_threshold)

    def is_price_in_fvg(self, current_price: float, fvg: FVG) -> bool:
        """Check if current price is inside FVG zone"""
        return fvg.bottom <= current_price <= fvg.top
