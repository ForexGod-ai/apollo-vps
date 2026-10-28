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


class FvgMixin:
    """V67 C: FVG detection and scoring."""

    @staticmethod
    def fvg_valid_for_pullback(
        fvg: FVG,
        direction: str,
        current_price: Optional[float],
    ) -> bool:
        """
        POI activ pe calea pullback: LONG — deasupra bazei FVG sau în interior;
        SHORT — sub vârful FVG sau în interior. Mitigarea completă = daily close breach.
        """
        if current_price is None:
            return True
        mkt = float(current_price)
        d = (direction or '').lower()
        if d == 'bullish':
            return mkt >= float(fvg.bottom) or mkt > float(fvg.top)
        if d == 'bearish':
            return mkt <= float(fvg.top) or mkt < float(fvg.bottom)
        return True

    @staticmethod
    def fvg_mitigated_by_daily_close(df: pd.DataFrame, fvg: FVG) -> bool:
        """FVG invalid doar la închidere Daily dincolo de zonă (wick / intrare ≠ mitigare)."""
        if df is None or fvg is None or len(df) <= fvg.index + 1:
            return False
        bottom = float(fvg.bottom)
        top = float(fvg.top)
        for j in range(fvg.index + 1, len(df)):
            close = float(df['close'].iloc[j])
            if fvg.direction == 'bullish' and close < bottom:
                return True
            if fvg.direction == 'bearish' and close > top:
                return True
        return False

    DECISIONAL_RETRACE_LO = 0.52
    DECISIONAL_RETRACE_HI = 0.78
    EXTREME_RETRACE_HI = 0.98

    @staticmethod
    def _fvg_retrace_pct(
        fvg: FVG,
        adr: ActiveDealingRange,
        direction: str,
    ) -> Optional[float]:
        lo = float(adr.container_low)
        hi = float(adr.container_high)
        rng = hi - lo
        if rng <= 0:
            return None
        mid = float(fvg.middle)
        d = (direction or '').lower()
        if d == 'bearish':
            return (mid - lo) / rng
        if d == 'bullish':
            return (hi - mid) / rng
        return None

    @classmethod
    def _pick_largest_gap(cls, fvgs: List[FVG]) -> Optional[FVG]:
        if not fvgs:
            return None
        return max(fvgs, key=lambda f: float(f.top - f.bottom))

    @classmethod
    def _select_fvg_decisional_first(
        cls,
        fvgs: List[FVG],
        direction: str,
        adr: Optional[ActiveDealingRange],
    ) -> Optional[FVG]:
        """V83: OTE decisional (52–78%) before extreme (78–98%); tie = largest gap."""
        if not fvgs:
            return None
        if adr is None:
            ranked = cls._sort_fvg_greedy_ote(fvgs, direction)
            return ranked[0] if ranked else None
        g1: List[FVG] = []
        g2: List[FVG] = []
        for f in fvgs:
            rp = cls._fvg_retrace_pct(f, adr, direction)
            if rp is None:
                continue
            if cls.DECISIONAL_RETRACE_LO <= rp <= cls.DECISIONAL_RETRACE_HI:
                g1.append(f)
            elif cls.DECISIONAL_RETRACE_HI < rp <= cls.EXTREME_RETRACE_HI:
                g2.append(f)
        pick = cls._pick_largest_gap(g1) or cls._pick_largest_gap(g2)
        if pick is not None:
            return pick
        ranked = cls._sort_fvg_greedy_ote(fvgs, direction)
        return ranked[0] if ranked else None

    @staticmethod
    def _sort_fvg_greedy_ote(fvgs: List[FVG], direction: str) -> List[FVG]:
        """Fallback sort — largest gap in Premium/Discount half."""
        d = (direction or '').lower()
        if d == 'bearish':
            return sorted(
                fvgs,
                key=lambda f: (float(f.middle), float(f.top - f.bottom)),
                reverse=True,
            )
        if d == 'bullish':
            return sorted(
                fvgs,
                key=lambda f: (float(f.middle), -float(f.top - f.bottom)),
            )
        return list(fvgs)

    def store_fvg_magnet(
        self, symbol: str, timeframe: str, fvg: FVG, debug: bool = False,
    ) -> None:
        """
        🎯 V3.4 ORDER BLOCKS: Store last 2 FVG zones per timeframe as price magnets
        These zones act as "zones of return" where price is likely to react
        
        Args:
            symbol: Trading pair (e.g., 'GBPUSD')
            timeframe: '4H'
            fvg: FVG object to store
        """
        if symbol not in self.fvg_magnets:
            self.fvg_magnets[symbol] = {'4H': []}
        
        # Add new FVG to the list
        self.fvg_magnets[symbol][timeframe].append(fvg)
        
        # Keep only last 2 FVGs (most recent zones)
        self.fvg_magnets[symbol][timeframe] = self.fvg_magnets[symbol][timeframe][-2:]
        
        if debug:
            print(f"🎯 ORDER BLOCK MAGNET: {symbol} {timeframe} - Stored FVG zone {fvg.bottom:.5f}-{fvg.top:.5f}")
            print(f"   Total magnets for {symbol} {timeframe}: {len(self.fvg_magnets[symbol][timeframe])}")

    def validate_fvg_zone(self, fvg: FVG, equilibrium: float, current_trend: str, debug: bool = False) -> bool:
        """🔥 PREMIUM/DISCOUNT ZONE VALIDATION - V8.4 ULTRA-SIMPLE BINARY LOGIC
        
        V8.4 FILOZOFIA SIMPLICITĂȚII:
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        EROAREA V8.2-V8.3: Matematică procentuală complicată, tolerance buffers,
        calcule complexe de "38%", "62%", etc. → Respingea setup-uri valide!
        
        SOLUȚIA V8.4: LOGICĂ BINARĂ PURĂ - DOAR COMPARARE DE PREȚURI (FLOAT)
        → Dacă prețul e peste 50% = Premium (bun pentru SHORT)
        → Dacă prețul e sub 50% = Discount (bun pentru LONG)
        → PUNCTUL DE 50% = (macro_high + macro_low) / 2.0 (simplu!)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        CONCEPTUL VIZUAL (Pe grafic):
        
        macro_high ━━━━━━━━━━━━━━━━┓
                                   ┃ 
                                   ┃ PREMIUM ZONE (pentru BEARISH SHORT)
                                   ┃ → FVG.top >= equilibrium = VALID ✅
        equilibrium (50%) ━━━━━━━━━┫ (Cu cât mai sus, cu atât mai bun)
                                   ┃ 
                                   ┃ DISCOUNT ZONE (pentru BULLISH LONG)
                                   ┃ → FVG.bottom <= equilibrium = VALID ✅
        macro_low ━━━━━━━━━━━━━━━━┛ (Cu cât mai jos, cu atât mai bun)
        
        VALIDARE ULTRA-SIMPLĂ:
        
        BEARISH SHORT (Premium Zone):
        ├─ Check: fvg.top >= equilibrium
        ├─ Logică: FVG atinge zona de sus (expensive = good for SHORT)
        └─ Rezultat: True = VALID, False = REJECTED (prea jos, nu e premium)
        
        BULLISH LONG (Discount Zone):
        ├─ Check: fvg.bottom <= equilibrium
        ├─ Logică: FVG atinge zona de jos (cheap = good for LONG)
        └─ Rezultat: True = VALID, False = REJECTED (prea sus, nu e discount)
        
        NO CEILING, NO FLOOR, NO PERCENTAGES!
        - Bearish: 70%, 80%, 90% în Premium = EXCELLENT (mai scump = mai bun SHORT)
        - Bullish: 30%, 20%, 10% în Discount = EXCELLENT (mai ieftin = mai bun LONG)
        
        Args:
            fvg: FVG object to validate
            equilibrium: 50% level (macro_high + macro_low) / 2.0
            current_trend: 'bullish' or 'bearish'
            debug: Print validation details
        
        Returns:
            True if FVG reaches correct zone (Premium for SHORT, Discount for LONG), False otherwise
        """
        if equilibrium is None:
            if debug:
                print("⚠️  No equilibrium level - accepting organic FVG (no P/D gate)")
            return True  # Can't validate without equilibrium — keep valid imbalance
        
        # Extract FVG price levels
        fvg_top = fvg.top
        fvg_bottom = fvg.bottom
        fvg_middle = fvg.middle
        
        if current_trend == 'bearish':
            is_valid = fvg_middle >= equilibrium
            if debug:
                print(f"\n🔍 V82 P/D (BEARISH): middle {fvg_middle:.5f} vs EQ {equilibrium:.5f} → {is_valid}")
            return is_valid

        elif current_trend == 'bullish':
            is_valid = fvg_middle <= equilibrium
            if debug:
                print(f"\n🔍 V82 P/D (BULLISH): middle {fvg_middle:.5f} vs EQ {equilibrium:.5f} → {is_valid}")
            return is_valid
        
        # Unknown trend direction
        if debug:
            print(f"⚠️  Unknown trend direction: {current_trend}")
        return False

    def get_fvg_magnets(self, symbol: str, timeframe: str) -> List[FVG]:
        """
        Get stored FVG magnets for a symbol/timeframe
        Returns empty list if none exist
        """
        if symbol not in self.fvg_magnets:
            return []
        return self.fvg_magnets[symbol].get(timeframe, [])


    @staticmethod
    def fvg_audit_entry(fvg: FVG) -> dict:
        """Serialize FVG for POI audit scripts."""
        return {
            "index": fvg.index,
            "direction": fvg.direction,
            "bottom": round(float(fvg.bottom), 5),
            "top": round(float(fvg.top), 5),
            "middle": round(float(fvg.middle), 5),
            "gap_size": round(float(fvg.top - fvg.bottom), 5),
        }

    @staticmethod
    def macro_equilibrium(
        df: pd.DataFrame,
        choch,
        dealing_range: Optional[ActiveDealingRange] = None,
        sm_protected_low: Optional[float] = None,
        sm_protected_high: Optional[float] = None,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], float]:
        """V79: equilibrium from ADR mid, else SM protected range, else CHoCH impulse."""
        if dealing_range is not None:
            lo = float(dealing_range.container_low)
            hi = float(dealing_range.container_high)
            return (hi + lo) / 2.0, lo, hi, hi - lo

        pl = sm_protected_low
        ph = sm_protected_high
        if pl is not None and ph is not None:
            lo, hi = float(min(pl, ph)), float(max(pl, ph))
            return (lo + hi) / 2.0, lo, hi, hi - lo

        direction = (getattr(choch, 'direction', '') or '').lower()
        body_hi = df[['open', 'close']].max(axis=1)
        body_lo = df[['open', 'close']].min(axis=1)
        if direction == 'bullish' and pl is not None:
            hi = float(body_hi.iloc[-40:].max())
            if ph is not None:
                hi = max(hi, float(ph))
            lo = float(pl)
            if hi > lo:
                return (lo + hi) / 2.0, lo, hi, hi - lo
        if direction == 'bearish' and ph is not None:
            lo = float(body_lo.iloc[-40:].min())
            if pl is not None:
                lo = min(lo, float(pl))
            hi = float(ph)
            if hi > lo:
                return (lo + hi) / 2.0, lo, hi, hi - lo

        swing_broken_price = choch_break_price = None
        impulse_size = 0.0
        if hasattr(choch, 'swing_broken') and hasattr(choch, 'break_price'):
            try:
                swing_broken_price = float(choch.swing_broken.price)
                choch_break_price = float(choch.break_price)
                impulse_size = abs(choch_break_price - swing_broken_price)
                lo = min(swing_broken_price, choch_break_price)
                hi = max(swing_broken_price, choch_break_price)
                return (swing_broken_price + choch_break_price) / 2.0, lo, hi, impulse_size
            except Exception:
                pass
        return None, None, None, 0.0

    def detect_fvg(
        self,
        df: pd.DataFrame,
        choch,
        audit_out: Optional[dict] = None,
        strategy_type: Optional[str] = None,
        dealing_range: Optional[ActiveDealingRange] = None,
        force_in_range_rescan: bool = False,
        current_price: Optional[float] = None,
        sm_protected_low: Optional[float] = None,
        sm_protected_high: Optional[float] = None,
        debug: bool = False,
    ) -> Optional[FVG]:
        """🎯 GLITCH IN MATRIX - FVG DETECTION (V8.1 - ORDERFLOW ALIGNED)
        
        CRITICAL V8.1 FIX: FVG selection MUST follow Daily Orderflow direction!
        
        🔥 ORDERFLOW ALIGNMENT RULES:
        1. If CHoCH/BOS direction = BEARISH → Search ONLY for BEARISH FVGs (SELL zones above price)
        2. If CHoCH/BOS direction = BULLISH → Search ONLY for BULLISH FVGs (BUY zones below price)
        3. IGNORE opposite direction FVGs completely (they are counter-trend noise)
        
        🔥 BODY CLOSURE MITIGATION (V8.0):
        - FVG is MITIGATED only when a BODY closes through it (wicks don't count)
        - Use body_highs = df[['open','close']].max(axis=1)
        - Use body_lows = df[['open','close']].min(axis=1)
        
        🔥 PROXIMITY FILTER:
        - Choose FVG that formed IMMEDIATELY AFTER CHoCH/BOS (max 30 candles old)
        - Ignore ancient FVGs from 3+ months ago (outdated zones)
        
        BULLISH FVG (Gap Up):
        - Condition: body_high[i-1] < body_low[i+1]
        - FVG Top: body_low[i+1]
        - FVG Bottom: body_high[i-1]
        - Meaning: Price jumped UP, leaving unfilled demand zone below
        
        BEARISH FVG (Gap Down):
        - Condition: body_low[i-1] > body_high[i+1]
        - FVG Top: body_low[i-1]
        - FVG Bottom: body_high[i+1]
        - Meaning: Price dropped DOWN, leaving unfilled supply zone above
        
        3-Candle Pattern:
        - Candle i-1: Setup candle (before gap)
        - Candle i: Gap candle (big move creating imbalance)
        - Candle i+1: Confirmation candle (after gap)
        """
        all_fvgs = []
        end_idx = len(df)
        
        # ✅ V10.6 FIX MEMORIA TOTALĂ: scanăm de la CHoCH.index fără nicio restricție artificială
        # V10.4 limita la ultimele 30 bare → bloca FVG-urile formate la bara 40-70 dintr-un range de 100
        # V10.6: folosim întreg intervalul [choch.index → prezent], exact cum vede traderul pe chart
        raw_start = choch.index if hasattr(choch, 'index') else 0
        pre_signal = 80 if dealing_range is not None else 20
        start_idx = max(0, raw_start - pre_signal)
        
        # 🔥 V8.1: ORDERFLOW DIRECTION - Only search for FVGs aligned with CHoCH/BOS direction
        orderflow_direction = choch.direction  # 'bullish' or 'bearish'
        _v43_continuation = (
            (strategy_type or '').lower() == 'continuation'
            and dealing_range is not None
        )

        def _v43_adr_allows(fvg: FVG) -> bool:
            if dealing_range is None:
                return True
            return self._fvg_within_adr(fvg, dealing_range, orderflow_direction)
        
        # V45 METHOD 1 — wick-to-wick FVG (Pianul Pur); wick overlap = skip
        search_end = end_idx - 1

        for i in range(start_idx + 1, search_end):
            if orderflow_direction == 'bullish':
                if df['high'].iloc[i - 1] < df['low'].iloc[i + 1]:
                    gap_top = df['low'].iloc[i + 1]
                    gap_bottom = df['high'].iloc[i - 1]
                    gap_size = gap_top - gap_bottom
                    if gap_size > 0 and (gap_size / gap_bottom) >= 0.0005:
                        fvg = FVG(
                            index=i,
                            direction='bullish',
                            top=gap_top,
                            bottom=gap_bottom,
                            middle=(gap_top + gap_bottom) / 2,
                            candle_time=df['time'].iloc[i] if 'time' in df.columns else i,
                            is_filled=False,
                            associated_choch=choch
                        )
                        if _v43_adr_allows(fvg):
                            all_fvgs.append(fvg)

            elif orderflow_direction == 'bearish':
                if df['low'].iloc[i - 1] > df['high'].iloc[i + 1]:
                    gap_top = df['low'].iloc[i - 1]
                    gap_bottom = df['high'].iloc[i + 1]
                    gap_size = gap_top - gap_bottom
                    if gap_size > 0 and (gap_size / gap_bottom) >= 0.0005:
                        fvg = FVG(
                            index=i,
                            direction='bearish',
                            top=gap_top,
                            bottom=gap_bottom,
                            middle=(gap_top + gap_bottom) / 2,
                            candle_time=df['time'].iloc[i] if 'time' in df.columns else i,
                            is_filled=False,
                            associated_choch=choch
                        )
                        if _v43_adr_allows(fvg):
                            all_fvgs.append(fvg)

        all_found_fvgs = list(all_fvgs)

        # Mitigare: doar daily CLOSE sub baza (bullish) sau peste vârf (bearish)
        if all_fvgs:
            all_fvgs = [
                f for f in all_fvgs
                if not self.fvg_mitigated_by_daily_close(df, f)
            ]

        after_mitigation_fvgs = list(all_fvgs)

        def _fill_audit(
            selected: Optional[FVG],
            selection_reason: str,
            equilibrium_val: Optional[float],
            pd_valid: list,
            post_choch: list,
            v43_extra: Optional[dict] = None,
        ) -> None:
            if audit_out is None:
                return
            audit_out.clear()
            v43_block = {
                "adr_enforced": _v43_continuation,
                "force_in_range_rescan": force_in_range_rescan,
            }
            if dealing_range is not None:
                v43_block.update({
                    "container_low": round(dealing_range.container_low, 5),
                    "container_high": round(dealing_range.container_high, 5),
                    "current_swing_high": round(dealing_range.current_swing_high, 5),
                    "current_swing_low": round(dealing_range.current_swing_low, 5),
                })
            if v43_extra:
                v43_block.update(v43_extra)
            audit_out.update({
                "body_fvgs": [self.fvg_audit_entry(f) for f in all_found_fvgs],
                "all_fvgs": [self.fvg_audit_entry(f) for f in all_found_fvgs],
                "after_mitigation": [self.fvg_audit_entry(f) for f in after_mitigation_fvgs],
                "pd_valid": [self.fvg_audit_entry(f) for f in pd_valid],
                "post_choch": [self.fvg_audit_entry(f) for f in post_choch],
                "selected": self.fvg_audit_entry(selected) if selected else None,
                "equilibrium": round(float(equilibrium_val), 5) if equilibrium_val is not None else None,
                "selection_reason": selection_reason,
                "orderflow_direction": orderflow_direction,
                "signal_index": choch.index if hasattr(choch, "index") else None,
                "v43": v43_block,
            })

        # ═══════════════════════════════════════════════════════════════════
        # 🎯 V16.1 PREMIUM/DISCOUNT FVG SELECTION — Ierarhia Daily Bias
        # ═══════════════════════════════════════════════════════════════════
        #
        # PRINCIPIU: Impulsul de referință = mișcarea care a produs CHoCH-ul.
        # Definit între swing_broken.price (origine) și break_price (confirmare ruptura).
        # Equilibrium (50%) = mijlocul acestui impuls = frontiera Discount/Premium.
        #
        # REGULI P/D ARRAY:
        #   Daily LONG  → Cumpărăm NUMAI din Discount (sub 50% al impulsului)
        #                 Ignorăm orice FVG aflat în Premium (deasupra 50%)
        #   Daily SHORT → Vindem NUMAI din Premium (peste 50% al impulsului)
        #                 Ignorăm orice FVG aflat în Discount (sub 50%)
        #
        # SELECȚIE FINALĂ (V82 — strict P/D + greedy OTE depth):
        #   Bearish: cel mai sus fvg.middle în Premium; bullish: cel mai jos; tie = gap size.
        #
        # FALLBACK → None: niciun FVG în P/D → OTE 62–79% în resolve_d1_poi
        # ═══════════════════════════════════════════════════════════════════
        if not all_fvgs:
            _fill_audit(None, "no_fvg_found", None, [], [])
            return None

        # ── STEP 1: V79 equilibrium — ADR mid, else SM range, else micro-impulse ──
        mkt = current_price
        if mkt is None and len(df):
            mkt = float(df['close'].iloc[-1])
        equilibrium, macro_low, macro_high, impulse_size = self.macro_equilibrium(
            df,
            choch,
            dealing_range=dealing_range,
            sm_protected_low=sm_protected_low,
            sm_protected_high=sm_protected_high,
        )

        def _v79_pd_valid(fvg: FVG) -> bool:
            if equilibrium is None:
                return False
            if not self.fvg_valid_for_pullback(fvg, orderflow_direction, mkt):
                return False
            if orderflow_direction == 'bullish':
                return float(fvg.middle) <= float(equilibrium)
            return float(fvg.middle) >= float(equilibrium)

        # ── STEP 2: Filtrare strictă P/D + preț curent ──
        pd_valid_fvgs: List[FVG] = []
        impulse_span_fvgs: List[FVG] = []
        if equilibrium is not None:
            for fvg in all_fvgs:
                if macro_low is not None and macro_high is not None:
                    if fvg.bottom > macro_high or fvg.top < macro_low:
                        continue
                    impulse_span_fvgs.append(fvg)
                if _v79_pd_valid(fvg) and _v43_adr_allows(fvg):
                    pd_valid_fvgs.append(fvg)

        # ── STEP 3: Strict P/D pool only ─────────
        pool = pd_valid_fvgs
        if pool:
            choch_idx = choch.index if hasattr(choch, 'index') else 0
            post_choch = [f for f in pool if f.index >= choch_idx]
            candidates = pool

            if dealing_range is not None:
                in_adr = [f for f in candidates if _v43_adr_allows(f)]
                if in_adr:
                    candidates = in_adr
                else:
                    _fill_audit(
                        None,
                        "V83 no clamped P/D FVG inside ADR",
                        equilibrium,
                        pd_valid_fvgs,
                        post_choch,
                        v43_extra={"adr_scan_empty": True},
                    )
                    return None

            selected = self._select_fvg_decisional_first(
                candidates, orderflow_direction, dealing_range,
            )
            if selected is None:
                _fill_audit(None, "V83 no decisional FVG", equilibrium, pd_valid_fvgs, post_choch)
                return None

            if _v43_continuation and self.poi_conflicts_with_continuation(
                selected.top, selected.bottom, orderflow_direction, dealing_range,
            ):
                _fill_audit(
                    None,
                    "V43 POI ZOMBIE — above LH / below HL",
                    equilibrium,
                    pd_valid_fvgs,
                    post_choch,
                    v43_extra={
                        "poi_zombie": True,
                        "rejected": self.fvg_audit_entry(selected),
                    },
                )
                return None

            _reason = "V83 decisional-first OTE (52–78%)"
            if _v43_continuation:
                _reason = "V83 decisional OTE (ADR clamped)"
            if force_in_range_rescan:
                _reason = "V83 in-range rescan after zombie reject"

            if debug:
                print(f"  ✅ [V70 P/D FVG] {'Discount' if orderflow_direction == 'bullish' else 'Premium'} "
                      f"FVG @ {selected.bottom:.5f}-{selected.top:.5f} "
                      f"| EQ={equilibrium:.5f} | Index={selected.index}")
            _fill_audit(selected, _reason, equilibrium, pd_valid_fvgs, post_choch)
            return selected

        # ── FALLBACK → None: OTE handled in resolve_d1_poi ──
        _eq_display = f"{equilibrium:.5f}" if equilibrium else "N/A"
        if debug:
            print(f"  ⚠️ [V70 FVG] Niciun FVG strict P/D "
                  f"(EQ={_eq_display}) → OTE fallback")
        _fill_audit(None, "V70 no strict P/D FVG", equilibrium, pd_valid_fvgs, impulse_span_fvgs)
        return None

    OTE_FIB_LOW = 0.62
    OTE_FIB_HIGH = 0.79

    @classmethod
    def impulse_bounds_from_signal(cls, choch) -> Tuple[Optional[float], Optional[float]]:
        """Impulse low/high from CHoCH/BOS swing broken → break price."""
        if not hasattr(choch, 'swing_broken') or not hasattr(choch, 'break_price'):
            return None, None
        try:
            a = float(choch.swing_broken.price)
            b = float(choch.break_price)
            return min(a, b), max(a, b)
        except Exception:
            return None, None

    @classmethod
    def build_ote_pd_fvg(
        cls,
        impulse_low: float,
        impulse_high: float,
        orderflow_direction: str,
        choch,
        df: pd.DataFrame,
    ) -> Optional[FVG]:
        """
        OTE 62–79% retracement box in Premium (bearish) or Discount (bullish).
        """
        if impulse_high <= impulse_low:
            return None
        rng = impulse_high - impulse_low
        if orderflow_direction == 'bullish':
            top = impulse_high - cls.OTE_FIB_LOW * rng
            bottom = impulse_high - cls.OTE_FIB_HIGH * rng
        else:
            bottom = impulse_low + cls.OTE_FIB_LOW * rng
            top = impulse_low + cls.OTE_FIB_HIGH * rng
        top_f = float(max(top, bottom))
        bottom_f = float(min(top, bottom))
        if top_f <= bottom_f:
            return None
        idx = choch.index if hasattr(choch, 'index') else max(0, len(df) - 2)
        if 'time' in df.columns and len(df) > idx:
            candle_time = df['time'].iloc[min(idx, len(df) - 1)]
        else:
            candle_time = datetime.now()
        return FVG(
            index=int(idx),
            direction=orderflow_direction,
            top=top_f,
            bottom=bottom_f,
            middle=(top_f + bottom_f) / 2.0,
            candle_time=candle_time,
            is_filled=False,
            associated_choch=choch if hasattr(choch, 'direction') else None,
        )

    def calculate_fvg_quality_score(
        self, 
        fvg: FVG, 
        df: pd.DataFrame, 
        symbol: str,
        debug: bool = False
    ) -> int:
        """
        V3.0 FVG QUALITY SCORING SYSTEM
        
        Returns score 0-100:
        - ≥70: HIGH QUALITY (execute)
        - 50-69: MEDIUM QUALITY (monitor)
        - <50: LOW QUALITY (reject)
        
        Scoring Components:
        1. Gap Size (0-25 points):
           - ≥0.20%: 25 pts (excellent)
           - ≥0.15%: 20 pts (good)
           - ≥0.10%: 15 pts (acceptable)
           - <0.10%: 0 pts (reject)
        
        2. Body Dominance (0-30 points):
           - ≥80%: 30 pts (strong momentum) [GBP requires this]
           - ≥70%: 25 pts (good momentum) [Normal pairs min]
           - ≥60%: 15 pts (moderate)
           - <60%: 0 pts (weak)
        
        3. Consecutive Strength (0-25 points):
           - 3+ candles same direction: 25 pts
           - 2 candles same direction: 15 pts
           - 1 candle: 5 pts
           - Mixed: 0 pts
        
        4. Gap Clarity (0-20 points):
           - Clean gap (no overlap): 20 pts
           - Partial overlap: 10 pts
           - Heavy overlap: 0 pts
        
        GBP ADAPTIVE FILTERING:
        - GBP pairs need ≥80% body dominance (vs 70% normal)
        - Minimum score: 75 (vs 70 normal)
        """
        score = 0
        is_gbp = 'GBP' in symbol
        
        if debug:
            print(f"\n🎯 FVG QUALITY SCORING:")
            print(f"   Symbol: {symbol} {'[GBP - STRICT MODE]' if is_gbp else ''}")
        
        # 1. GAP SIZE SCORING (0-25 points)
        gap_size = fvg.top - fvg.bottom
        gap_pct = (gap_size / fvg.bottom) * 100
        
        if gap_pct >= 0.20:
            gap_score = 25
            gap_tier = "EXCELLENT"
        elif gap_pct >= 0.15:
            gap_score = 20
            gap_tier = "GOOD"
        elif gap_pct >= 0.10:
            gap_score = 15
            gap_tier = "ACCEPTABLE"
        else:
            gap_score = 0
            gap_tier = "TOO SMALL"
        
        score += gap_score
        
        if debug:
            print(f"   1. Gap Size: {gap_pct:.3f}% → {gap_score}/25 pts ({gap_tier})")
        
        # 2. BODY DOMINANCE SCORING (0-30 points)
        if fvg.index < len(df):
            gap_candle = df.iloc[fvg.index]
            candle_body = abs(gap_candle['close'] - gap_candle['open'])
            candle_range = gap_candle['high'] - gap_candle['low']
            
            if candle_range > 0:
                body_ratio = (candle_body / candle_range) * 100
                
                # GBP: Requires ≥70% body dominance (RELAXED from 80%)
                if is_gbp:
                    if body_ratio >= 80:
                        body_score = 30
                        body_tier = "STRONG (GBP OK)"
                    elif body_ratio >= 70:
                        body_score = 25
                        body_tier = "GOOD (GBP OK)"
                    else:
                        body_score = 0
                        body_tier = f"WEAK (GBP needs ≥70%, got {body_ratio:.1f}%)"
                else:
                    # ✅ V10.4: Normal pairs: 50%+ acceptable (RELAXAT de la 60%)
                    # Pe Daily, lumânările nu sunt totdeauna "textbook" — 50% e suficient
                    if body_ratio >= 80:
                        body_score = 30
                        body_tier = "STRONG"
                    elif body_ratio >= 70:
                        body_score = 25
                        body_tier = "GOOD"
                    elif body_ratio >= 60:
                        body_score = 15
                        body_tier = "MODERATE"
                    elif body_ratio >= 50:
                        body_score = 8
                        body_tier = f"ACCEPTABLE ({body_ratio:.1f}% >= 50%)"
                    else:
                        body_score = 0
                        body_tier = f"WEAK ({body_ratio:.1f}% < 50%)"
                
                score += body_score
                
                if debug:
                    print(f"   2. Body Dominance: {body_ratio:.1f}% → {body_score}/30 pts ({body_tier})")
            else:
                if debug:
                    print(f"   2. Body Dominance: N/A (zero range candle) → 0/30 pts")
        else:
            if debug:
                print(f"   2. Body Dominance: N/A (index out of range) → 0/30 pts")
        
        # 3. CONSECUTIVE STRENGTH SCORING (0-25 points)
        # Check 2-3 candles BEFORE FVG for trend strength
        if fvg.index >= 3:
            lookback_start = max(0, fvg.index - 3)
            lookback_candles = df.iloc[lookback_start:fvg.index]
            
            # Count consecutive candles in same direction as FVG
            consecutive_count = 0
            for idx in range(len(lookback_candles)):
                candle = lookback_candles.iloc[idx]
                candle_direction = 'bullish' if candle['close'] > candle['open'] else 'bearish'
                
                if candle_direction == fvg.direction:
                    consecutive_count += 1
            
            if consecutive_count >= 3:
                consec_score = 25
                consec_tier = "STRONG (3+ candles)"
            elif consecutive_count >= 2:
                consec_score = 15
                consec_tier = "GOOD (2 candles)"
            elif consecutive_count >= 1:
                consec_score = 5
                consec_tier = "WEAK (1 candle)"
            else:
                consec_score = 0
                consec_tier = "NONE (mixed)"
            
            score += consec_score
            
            if debug:
                print(f"   3. Consecutive Strength: {consecutive_count} candles → {consec_score}/25 pts ({consec_tier})")
        else:
            if debug:
                print(f"   3. Consecutive Strength: N/A (not enough history) → 0/25 pts")
        
        # 4. GAP CLARITY SCORING (0-20 points)
        # Check if gap is clean (no candle wicks overlap the gap zone)
        if fvg.index >= 2:
            candle_before = df.iloc[fvg.index - 2]
            candle_after = df.iloc[fvg.index]
            
            if fvg.direction == 'bullish':
                # Bullish gap: check if no overlap between before.high and after.low
                overlap = max(0, candle_before['high'] - candle_after['low'])
            else:
                # Bearish gap: check if no overlap between before.low and after.high
                overlap = max(0, candle_after['high'] - candle_before['low'])
            
            overlap_pct = (overlap / gap_size) * 100 if gap_size > 0 else 100
            
            if overlap_pct == 0:
                clarity_score = 20
                clarity_tier = "CLEAN GAP"
            elif overlap_pct < 30:
                clarity_score = 10
                clarity_tier = "PARTIAL OVERLAP"
            elif overlap_pct < 150:
                clarity_score = 5
                clarity_tier = "MODERATE OVERLAP"
            else:
                clarity_score = 2
                clarity_tier = "HEAVY OVERLAP (dar acceptat Daily)"
            
            score += clarity_score
            
            if debug:
                print(f"   4. Gap Clarity: {overlap_pct:.1f}% overlap → {clarity_score}/20 pts ({clarity_tier})")
        else:
            if debug:
                print(f"   4. Gap Clarity: N/A (not enough history) → 0/20 pts")
        
        # FINAL SCORE
        min_required = 75 if is_gbp else 70
        quality_rating = "✅ HIGH QUALITY" if score >= min_required else "⚠️ LOW QUALITY"
        
        if debug:
            print(f"\n   📊 TOTAL SCORE: {score}/100 ({quality_rating})")
            print(f"   Required: ≥{min_required} pts")
        
        return score
