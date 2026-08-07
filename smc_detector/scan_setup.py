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



class ScanSetupMixin:
    """V67 C: scan D1/FVG/POI phase."""

    def _scan_through_poi_validation(        self,        symbol: str,        df_daily: pd.DataFrame,        df_4h: pd.DataFrame,        priority: int,        require_4h_choch: bool,        skip_fvg_quality: bool,        debug: bool,        stored_poi_top: Optional[float],        stored_poi_bottom: Optional[float],        d1_ctx: Optional[D1AuthContext],    ):        # ✅ V10.4 FIX CRASH: alias debug in corpul funcției
        # V67: fără NZDCAD forțat — debug controlat de SCANNER_DEBUG env
        debug = debug

        # ⚡ V13.1 PERFORMANCE: Re-init cache la fiecare pair nou (defensiv — nu .clear())
        self._swing_highs_cache = {}
        self._swing_lows_cache = {}
        
        # V4.0: Initialize variables early to avoid UnboundLocalError
        order_block = None  # Will be populated later with detect_order_block()
        h4_sync_fvg = None  # V10.4: FVG from 4H confirmation move (entry zone)

        _unconfirmed_bearish_choch = False
        _unconfirmed_bullish_choch = False

        if d1_ctx is not None:
            daily_chochs = list(d1_ctx.chochs)
            daily_bos_list = list(d1_ctx.bos_list)
            _range_state = d1_ctx.range_state
            _swing_highs_unconf = d1_ctx.swing_h
            _swing_lows_unconf = d1_ctx.swing_l
            latest_signal = d1_ctx.latest_signal
            strategy_type = d1_ctx.strategy_type
            current_trend = d1_ctx.trend
            leg_choch = d1_ctx.leg_choch
        else:
            # Step 1: Detect Daily CHoCH AND BOS
            daily_chochs, daily_bos_list = self.detect_choch_and_bos(df_daily)
            
            if debug:
                print(f"\n{'='*60}")
                print(f"🔍 DEBUG: {symbol} - GLITCH IN MATRIX SCAN")
                print(f"{'='*60}")
                print(f"📊 Daily CHoCH detected: {len(daily_chochs)}")
                print(f"📊 Daily BOS detected: {len(daily_bos_list)}")
                if daily_chochs:
                    for i, choch in enumerate(daily_chochs[-3:]):  # Last 3
                        print(f"   CHoCH [{i}] {choch.direction.upper()} @ {choch.break_price:.5f} (index {choch.index})")
                if daily_bos_list:
                    for i, bos in enumerate(daily_bos_list[-3:]):  # Last 3
                        print(f"   BOS [{i}] {bos.direction.upper()} @ {bos.break_price:.5f} (index {bos.index})")
            
            _swing_highs_unconf = self.detect_swing_highs(df_daily)
            _swing_lows_unconf  = self.detect_swing_lows(df_daily)

            if self.enable_unconfirmed_guard:
                current_price_unconf = df_daily['close'].iloc[-1]
                _unconf_bearish_drop_pct = 0.0
                _unconf_bullish_rise_pct = 0.0

                if _swing_highs_unconf:
                    for _sh_candidate in reversed(_swing_highs_unconf):
                        _sh_bars_ago = len(df_daily) - _sh_candidate.index - 1
                        if _sh_bars_ago > 60:
                            break
                        _wick_h = df_daily['high'].iloc[_sh_candidate.index] if _sh_candidate.index < len(df_daily) else _sh_candidate.price
                        _ref_h = max(_sh_candidate.price, _wick_h)
                        if _ref_h > 0:
                            _drop = (_ref_h - current_price_unconf) / _ref_h * 100.0
                            if _drop > _unconf_bearish_drop_pct:
                                _unconf_bearish_drop_pct = _drop
                                _unconf_bearish_ref = _ref_h
                    if _unconf_bearish_drop_pct >= 3.0:
                        _unconfirmed_bearish_choch = True
                        if debug:
                            print(f"   ⚠️ [V11.9] {symbol}: CHoCH bearish neconfirmat — preț a scăzut {_unconf_bearish_drop_pct:.1f}% față de swing high @ {_unconf_bearish_ref:.3f} (în 60 bare)")

                if _swing_lows_unconf:
                    for _sl_candidate in reversed(_swing_lows_unconf):
                        _sl_bars_ago = len(df_daily) - _sl_candidate.index - 1
                        if _sl_bars_ago > 60:
                            break
                        _wick_l = df_daily['low'].iloc[_sl_candidate.index] if _sl_candidate.index < len(df_daily) else _sl_candidate.price
                        _ref_l = min(_sl_candidate.price, _wick_l)
                        if _ref_l > 0:
                            _rise = (current_price_unconf - _ref_l) / _ref_l * 100.0
                            if _rise > _unconf_bullish_rise_pct:
                                _unconf_bullish_rise_pct = _rise
                                _unconf_bullish_ref = _ref_l
                    if _unconf_bullish_rise_pct >= 3.0:
                        _unconfirmed_bullish_choch = True
                        if debug:
                            print(f"   ⚠️ [V11.9] {symbol}: CHoCH bullish neconfirmat — preț a urcat {_unconf_bullish_rise_pct:.1f}% față de swing low @ {_unconf_bullish_ref:.3f} (în 60 bare)")

            _range_state = self.compute_structural_range(
                df_daily, _swing_highs_unconf, _swing_lows_unconf, symbol=symbol
            )
            daily_chochs, daily_bos_list, _range_state = self.filter_internal_range_signals(
                symbol, df_daily, daily_chochs, daily_bos_list, _range_state, debug=debug,
            )

            latest_signal, strategy_type, current_trend, leg_choch = self._resolve_d1_leg(
                df_daily, daily_chochs, daily_bos_list, debug=debug, range_state=_range_state
            )

        if latest_signal is None or current_trend == 'neutral':
            if debug:
                print(f"❌ REJECTED: No Daily CHoCH or BOS found")
            return None

        _close = float(df_daily['close'].iloc[-1])
        _macro_swings = self.macro_trend_from_swings(df_daily)
        if (
            strategy_type == 'reversal'
            and current_trend == 'bullish'
            and _range_state
            and _close <= float(_range_state.macro_range_high)
            and _close > float(_range_state.macro_range_low)
            and _macro_swings != 'bullish'
        ):
            print(
                f"⛔ [V63 GATE] {symbol}: REVERSAL LONG rejected — "
                f"close {_close:.5f} inside range without macro bullish confirmation"
            )
            return None
        if (
            strategy_type == 'reversal'
            and current_trend == 'bullish'
            and _range_state
            and _range_state.locked_bias == 'bearish'
            and _close <= float(_range_state.macro_range_low)
        ):
            print(
                f"⛔ [V58 MACRO GATE] {symbol}: REVERSAL LONG rejected — "
                f"close {_close:.5f} below LL {_range_state.macro_range_low:.5f}"
            )
            return None
        if (
            strategy_type == 'reversal'
            and current_trend == 'bullish'
            and _macro_swings == 'bearish'
            and _range_state
            and _close <= float(_range_state.macro_range_low)
        ):
            print(
                f"⛔ [V58 MACRO GATE] {symbol}: REVERSAL LONG rejected — "
                f"macro swings BEARISH + close below LL"
            )
            return None
        if (
            strategy_type == 'reversal'
            and current_trend == 'bearish'
            and _macro_swings == 'bullish'
            and _range_state
            and _close > float(_range_state.macro_range_high)
        ):
            print(
                f"⛔ [V58 MACRO GATE] {symbol}: REVERSAL SHORT rejected — "
                f"macro swings BULLISH + close above LH"
            )
            return None

        if (
            leg_choch is not None
            and not self._leg_choch_still_valid(
                df_daily, leg_choch, daily_bos_list, daily_chochs,
            )
            and strategy_type == 'reversal'
            and current_trend == 'bullish'
        ):
            print(
                f"⛔ [V57 LEG INVALID] {symbol}: bullish REVERSAL rejected — "
                f"close below leg CHoCH break @bar{leg_choch.index}"
            )
            return None

        _signal_label = 'CHoCH' if strategy_type == 'reversal' else 'BOS'

        if debug:
            print(
                f"\n✅ [V42.5 LEG] {symbol}: D1 {_signal_label} {current_trend.upper()} "
                f"@bar{latest_signal.index} price={latest_signal.break_price:.5f} "
                f"→ {strategy_type.upper()} / WAITING_D1_PULLBACK"
            )

        current_price = df_daily['close'].iloc[-1]

        _swing_h = self.detect_swing_highs(df_daily)
        _swing_l = self.detect_swing_lows(df_daily)
        _adr = self.build_active_dealing_range(
            df_daily,
            _swing_h,
            _swing_l,
            latest_signal.index,
            current_trend,
            range_state=_range_state,
            symbol=symbol,
            debug=debug,
        )
        _structural_breach = self.compute_structural_breach(
            float(current_price), current_trend, _adr,
        )
        if _structural_breach and debug:
            print(
                f"   🚨 [V43.0 ADR] {symbol}: structural_breach=True — "
                f"daily close breached protected structure (stateless signal for Etapa 2+)"
            )
        _poi_res = self.resolve_d1_poi(
            df_daily,
            latest_signal,
            float(current_price),
            current_trend,
            strategy_type,
            _adr,
            symbol=symbol,
            stored_poi_top=stored_poi_top,
            stored_poi_bottom=stored_poi_bottom,
            debug=debug,
        )
        fvg = _poi_res.fvg

        if not fvg:
            if debug:
                print(f"   ⏸️ [Faza A] {symbol}: no organic D1 FVG — setup withheld (WAITING_D1_PULLBACK)")
            return None

        if debug:
            gap_size = fvg.top - fvg.bottom
            gap_pct = (gap_size / fvg.bottom) * 100
            print(f"\n✅ FVG Found:")
            print(f"   Direction: {fvg.direction.upper()}")
            print(f"   Zone: {fvg.bottom:.5f} - {fvg.top:.5f}")
            print(f"   Gap Size: {gap_size:.5f} ({gap_pct:.3f}%)")
            print(f"   Middle: {fvg.middle:.5f}")
        
        # 🔥 V8.2: STRATEGY-DIFFERENTIATED PREMIUM/DISCOUNT VALIDATION
        # Calculate equilibrium using CORRECT Macro Leg for strategy type
        swing_highs = self.detect_swing_highs(df_daily)
        swing_lows = self.detect_swing_lows(df_daily)
        
        # V8.2: Use different equilibrium calculation based on strategy
        if strategy_type == 'reversal':
            # REVERSAL: Use PRE-CHoCH Macro Leg
            equilibrium = self.calculate_equilibrium_reversal(latest_signal, swing_highs, swing_lows)
            
            if debug and equilibrium:
                print(f"\n🔄 REVERSAL Macro Leg (Pre-CHoCH):")
                print(f"   Equilibrium: {equilibrium:.5f}")
                print(f"   Measured from: Last swing before CHoCH → CHoCH break")
        else:
            # CONTINUITY: Use POST-CHoCH Impulse Leg
            # Find last CHoCH before this BOS
            last_choch = daily_chochs[-1] if daily_chochs else None
            equilibrium = self.calculate_equilibrium_continuity(latest_signal, last_choch, swing_highs, swing_lows)
            
            if debug and equilibrium:
                print(f"\n➡️ CONTINUITY Macro Leg (Post-CHoCH Impulse):")
                print(f"   Equilibrium: {equilibrium:.5f}")
                print(f"   Measured from: Last swing after CHoCH → BOS break")
        
        # 🔥 V8.0: SKIP equilibrium validation for MOMENTUM entries (breakout setups, no pullback required)
        if hasattr(fvg, 'is_momentum_entry') and fvg.is_momentum_entry:
            if debug:
                print(f"\n⚡ MOMENTUM ENTRY: Skipping equilibrium validation (breakout strategy, no pullback)")
        elif equilibrium is not None:
            # V10.8: validate_fvg_zone este INFORMATIV — nu mai blocăm nicio strategie.
            # Motivare: Un FVG valid deasupra echilibrului pentru un LONG este normal într-un trend bullish puternic.
            # Filtrarea era prea agresivă și bloca setup-uri instituționale reale (AUDUSD 93%, EURUSD 88%).
            equilibrium_buffer = equilibrium * 1.20 if current_trend == 'bullish' else equilibrium
            equilibrium_for_short = equilibrium * 0.80 if current_trend == 'bearish' else equilibrium
            
            is_valid_zone = self.validate_fvg_zone(
                fvg,
                equilibrium_buffer if current_trend == 'bullish' else equilibrium_for_short,
                current_trend,
                debug=debug
            )
            
            if not is_valid_zone:
                zone_name = 'DISCOUNT' if current_trend == 'bullish' else 'PREMIUM'
                print(f"[V10.8 INFO: FVG în afara zonă {zone_name} locală (echilibru={equilibrium:.5f}) — continuăm oricum] {symbol}")
                # ✅ V10.8: NICIUN return None — ambele strategii continuă
            
            if debug:
                print(f"\n✅ [V10.8 ACTIVE] Zone check: {'VALID' if is_valid_zone else 'OUTSIDE (bypassed)'}")
                zone_type = "PREMIUM" if current_trend == 'bearish' else "DISCOUNT"
                print(f"   Strategy: {strategy_type.upper()} | FVG vs {zone_type} zone")
        else:
            if debug:
                print(f"\n⚠️  Could not calculate {strategy_type.upper()} equilibrium - skipping validation")
        
        # 🔥 V8.0: SKIP FVG quality scoring for MOMENTUM entries (breakout setups, not pullback retracements)
        # MOMENTUM entries use last swing range → no "gap quality" to validate (synthetic FVG)
        if hasattr(fvg, 'is_momentum_entry') and fvg.is_momentum_entry:
            fvg.quality_score = 100  # Max score for momentum breakouts
            if debug:
                print(f"\n⚡ MOMENTUM ENTRY: Skipping FVG quality scoring (synthetic momentum zone, not pullback gap)")
                print(f"   ✅ Momentum validation 1/5 passed (Quality Scoring)")
            # Skip to price check and 4H confirmation
        # V3.0: Calculate FVG Quality Score (0-100) - OPTIONAL for backtest
        elif not skip_fvg_quality:
            fvg_score = self.calculate_fvg_quality_score(fvg, df_daily, symbol, debug=debug)
            fvg.quality_score = fvg_score  # Store score in FVG object

            # ─── V9.0 V4: GOLDEN ZONE SCORING (PD Array 70.5%–80%) ─────────────────
            # Calculăm unde se află middle-ul FVG față de macro range (CHoCH high ↔ low).
            # Golden Zone = retragere la 70.5%–80% din macro range → setup PREMIUM.
            # Sub 50% pentru BUY (discount) sau peste 50% pentru SELL (premium) = obligatoriu.
            # ─────────────────────────────────────────────────────────────────────────
            _macro_h = None
            _macro_l = None
            # Culegem macro high/low din swing points recente (ultimi 150 bare)
            _swing_highs_v4 = self.detect_swing_highs(df_daily)
            _swing_lows_v4  = self.detect_swing_lows(df_daily)
            if _swing_highs_v4:
                _macro_h = max(s.price for s in _swing_highs_v4[-5:])
            if _swing_lows_v4:
                _macro_l = min(s.price for s in _swing_lows_v4[-5:])

            if _macro_h and _macro_l and _macro_h > _macro_l:
                macro_range = _macro_h - _macro_l
                fvg_mid = (fvg.top + fvg.bottom) / 2.0

                if current_trend == 'bullish':
                    # ✅ V10.5 FIX: Penalizare inversă eliminată.
                    # BUY cu FVG în zona ridicată (premium) = NORMAL pentru un trend bullish puternic.
                    # Penalizarea veche scădea scorul inutil. Acum: bonus doar pentru golden zone.
                    pct_from_low = (fvg_mid - _macro_l) / macro_range * 100.0
                    # Golden Zone BUY: retragere 70.5–80% din HIGH (adică pct_from_low 20–29.5%)
                    golden_buy = 20.0 <= pct_from_low <= 29.5
                    if golden_buy:
                        fvg.quality_score = max(fvg.quality_score, 90)
                        if debug:
                            print(f"\n🏆 V4 GOLDEN ZONE BUY: {pct_from_low:.1f}% from low → quality_score ≥ 90")
                    elif pct_from_low <= 50.0:
                        # FVG în zona discount (corect pentru BUY) — mică bonificare
                        fvg.quality_score = min(100, fvg.quality_score + 5)
                        if debug:
                            print(f"\n✅ V4 FVG BUY discount zone: {pct_from_low:.1f}% from low (score {fvg.quality_score})")
                    else:
                        # FVG peste 50% — OK, fără penalizare
                        if debug:
                            print(f"\n✅ V4 FVG BUY: {pct_from_low:.1f}% from low (score {fvg.quality_score}) — no penalty")

                else:  # bearish
                    # ✅ V10.5 FIX: Penalizare inversă eliminată.
                    # SELL cu FVG în zona scăzută (discount) = NORMAL după un move bearish puternic.
                    # Penalizarea veche scădea scorul sub pragul minim și bloca setup-uri valide.
                    # Acum: bonus dacă FVG e în zona premium (>50%), fără penalizare altfel.
                    pct_from_low = (fvg_mid - _macro_l) / macro_range * 100.0
                    # Golden Zone SELL: 70.5%–80% din range de sus (pct_from_low 70.5–80%)
                    golden_sell = 70.5 <= pct_from_low <= 80.0
                    if golden_sell:
                        fvg.quality_score = max(fvg.quality_score, 90)
                        if debug:
                            print(f"\n🏆 V4 GOLDEN ZONE SELL: {pct_from_low:.1f}% from low → quality_score ≥ 90")
                    elif pct_from_low >= 50.0:
                        # FVG în zona premium (corect pentru SELL) — mică bonificare
                        fvg.quality_score = min(100, fvg.quality_score + 5)
                        if debug:
                            print(f"\n✅ V4 FVG SELL premium zone: {pct_from_low:.1f}% from low (score {fvg.quality_score})")
                    else:
                        # FVG sub 50% — OK, trend bearish continuă, fără penalizare
                        if debug:
                            print(f"\n✅ V4 FVG SELL: {pct_from_low:.1f}% from low (score {fvg.quality_score}) — no penalty")
            # ─────────────────────────────────────────────────────────────────────────
            
            # V3.0 QUALITY THRESHOLD (only when not skipped)
            # - Normal pairs: ≥60 required (RELAXED from 70)
            # - GBP pairs: ≥70 required (RELAXED from 75)
            # - XAUUSD: SKIP quality check - filtered later by ATR + anti-loss-streak
            is_gbp = 'GBP' in symbol
            is_gold = any(x in symbol.upper() for x in ['XAU', 'XAG', 'GOLD', 'SILVER'])
            is_crypto = any(x in symbol.upper() for x in ['BTC', 'ETH', 'XRP', 'LTC', 'ADA', 'DOGE'])

            if is_crypto:
                # V24.4 CRYPTO: Gap procentual minim 0.05% (BTC@95k = ~47$ gap — suficient)
                # Body ratio 0.20 — crypto are frecvent doji/inside bars valide structural
                gap_size = fvg.top - fvg.bottom
                gap_pct = (gap_size / fvg.bottom) * 100
                if gap_pct < 0.05:
                    if debug:
                        print(f"\n❌ REJECTED {symbol} FVG: Gap {gap_pct:.3f}% < 0.05%")
                    return None
                gap_candle = df_daily.iloc[fvg.index]
                candle_body = abs(gap_candle['close'] - gap_candle['open'])
                candle_range = gap_candle['high'] - gap_candle['low']
                body_ratio = candle_body / candle_range if candle_range > 0 else 1.0
                if body_ratio < 0.20:
                    if debug:
                        print(f"\n❌ REJECTED {symbol} FVG: Body {body_ratio:.1%} < 20%")
                    return None
                if debug:
                    print(f"\n✅ CRYPTO FVG V24.4 PASSED: Gap {gap_pct:.3f}%, Body {body_ratio:.1%}")

            elif is_gold:
                gap_size = fvg.top - fvg.bottom
                gap_pct = (gap_size / fvg.bottom) * 100 if fvg.bottom else 0
                _gap_idx = min(max(fvg.index, 0), len(df_daily) - 1)
                gap_candle = df_daily.iloc[_gap_idx]
                candle_body = abs(gap_candle['close'] - gap_candle['open'])
                candle_range = gap_candle['high'] - gap_candle['low']
                body_ratio = candle_body / candle_range if candle_range > 0 else 0

                if gap_pct < 0.10 or body_ratio < 0.25:
                    _reason = []
                    if gap_pct < 0.10:
                        _reason.append(f"gap {gap_pct:.3f}% < 0.10%")
                    if body_ratio < 0.25:
                        _reason.append(f"body {body_ratio:.1%} < 25%")
                    print(f"   ⏸️ [Faza A {symbol}] FVG organic imperfect ({', '.join(_reason)}) — setup withheld")
                    return None
                if debug:
                    print(f"\n✅ XAUUSD FVG V14.0 PASSED: Gap {gap_pct:.3f}%, Body {body_ratio:.1%}")
                    
            elif is_gbp:
                min_score = 45  # V10.8: GBP relaxat la 45 (era 60)
                if fvg_score < min_score:
                    # V29.0: Nu mai respingem — Bias D1 valid (CHoCH/BOS + Body Close confirmat)
                    # FVG slab pe Daily = zona degradată, Radar 4H decide calitatea reală
                    print(f"⚠️ [V29.0 {symbol}] FVG score {fvg_score}/100 < {min_score} GBP min — WAITING_D1_PULLBACK (nu rejected)")
                    fvg._is_daily_bias_zone = True
            else:
                min_score = 15  # ✅ V10.8: Relaxat la 15 pentru non-GBP (era 40→20→15)
                # Pe Daily, FVG-uri perfecte sunt rare — ce contează e direcția și CHoCH
                if fvg_score < min_score:
                    # V29.0: Nu mai respingem — Bias D1 valid, scor mic ≠ setup invalid
                    print(f"⚠️ [V29.0 {symbol}] FVG score {fvg_score}/100 < {min_score} min — WAITING_D1_PULLBACK (nu rejected)")
                    fvg._is_daily_bias_zone = True
            
            # XAUUSD ADDITIONAL FILTERS: FVG quality (NO ADX - Gold moves differently)
            if is_gold and not skip_fvg_quality and debug:
                print(f"\n✅ XAUUSD FILTERS PASSED:")
                print(f"   FVG Quality: {fvg_score}/100 ✓")
                print(f"   (ADX check skipped - Gold momentum patterns differ from forex)")
        else:
            # Skip quality check for backtest - accept all FVGs
            fvg.quality_score = 100  # Default high score when skipped
        
        # FVG direction must match current trend
        fvg.direction = current_trend
        
        # Step 4: Check price relationship with FVG
        current_price = df_daily['close'].iloc[-1]
        
        if debug:
            print(f"\n📍 Current Price: {current_price:.5f}")
        
        # NEW: More flexible - accept setups even if price not perfectly in FVG yet
        price_in_fvg = self.is_price_in_fvg(current_price, fvg)
        
        # 🔥 V8.0: Skip price proximity check for MOMENTUM entries (breakout, not pullback)
        # For backtesting: skip price proximity check
        if skip_fvg_quality or (hasattr(fvg, 'is_momentum_entry') and fvg.is_momentum_entry):
            if debug and hasattr(fvg, 'is_momentum_entry') and fvg.is_momentum_entry:
                print(f"\n⚡ MOMENTUM ENTRY: Skipping price proximity check (breakout entry, not pullback wait)")
        elif debug:
            # V42.7: approaching = preț pe partea corectă spre POI (nu Premium pentru LONG)
            if current_trend == 'bullish' and current_price > fvg.top:
                print(f"   ⏳ [V42.7 POI] BULLISH: preț {current_price:.5f} în Premium peste POI top {fvg.top:.5f} — așteptăm pullback")
            elif current_trend == 'bearish' and current_price < fvg.bottom:
                print(f"   ⏳ [V42.7 POI] BEARISH: preț {current_price:.5f} în Discount sub POI bottom {fvg.bottom:.5f} — așteptăm pullback")
            elif not price_in_fvg:
                print(f"   ℹ️  [V42.7 POI] Preț pe traseu spre POI [{fvg.bottom:.5f}–{fvg.top:.5f}]")
        
        if debug:
            print(f"   In FVG: {price_in_fvg}")
            if current_trend == 'bullish':
                distance = current_price - fvg.top
                print(f"   Distance from FVG top: {distance:.5f} ({(distance/current_price)*100:.2f}%)")
            else:
                distance = fvg.bottom - current_price
                print(f"   Distance from FVG bottom: {distance:.5f} ({(distance/current_price)*100:.2f}%)")
        
        # Step 5: Strategy type already determined from signal type (CHoCH=REVERSAL, BOS=CONTINUITY)
        # No need to re-detect strategy_type
        
        if debug:
            print(f"\n📋 Strategy Type: {strategy_type.upper()}")
        
        # Step 6: Check 4H for confirmation (CHoCH FROM FVG zone)
        h4_chochs, _ = self.detect_choch_and_bos(df_4h)
        
        if debug:
            print(f"\n🔍 H4 Analysis:")
            print(f"   Total H4 CHoCH: {len(h4_chochs)}")
            if h4_chochs:
                for i, h4ch in enumerate(h4_chochs[-5:]):  # Last 5
                    in_fvg = fvg.bottom <= h4ch.break_price <= fvg.top
                    matches = h4ch.direction == current_trend
                    print(f"   [{i}] {h4ch.direction.upper()} @ {h4ch.break_price:.5f} - InFVG:{in_fvg} Match:{matches}")
        
        # Find H4 CHoCH that matches current trend AND happens FROM FVG zone
        valid_h4_choch = None
        
        # 🔥 V8.0: Skip 4H CHoCH requirement for MOMENTUM entries
        # MOMENTUM = breakout at last swing (no pullback to confirm)
        # Standard = pullback into FVG zone, then 4H CHoCH confirms reversal
        if hasattr(fvg, 'is_momentum_entry') and fvg.is_momentum_entry:
            if debug:
                print(f"\n⚡ MOMENTUM ENTRY: Skipping 4H CHoCH requirement (breakout strategy, no pullback)")
            # Skip to Order Block detection
            valid_h4_choch = None  # Not required for momentum
            require_4h_choch = False  # Override for momentum logic
        
        # V2.1 vs V3.0 DIFFERENCE:
        # V2.1: Daily CHoCH + FVG = READY (original $88k profit logic)
        # V3.0: Daily CHoCH + FVG + 4H CHoCH = READY (strict entry confirmation)
        
        elif require_4h_choch:
            # ━━━ V10.4 CLARIFIED STRATEGY: 4H = DIRECTIONAL CONFIRMATION ONLY ━━━
            # 
            # D1 sets the BIAS (Reversal or Continuation).
            # 4H CHoCH with BODY CLOSURE confirms D1 bias direction.
            # 4H CHoCH does NOT need to be inside Daily FVG zone!
            # The FVG for entry comes from the 4H sync move AFTER confirmation.
            # 
            # REVERSAL: D1 CHoCH (trend change) → Price reaches D1 zone → 4H CHoCH confirms → Enter in 4H sync FVG
            # CONTINUITY: D1 BOS (trend continues) → Price reaches D1 zone → 4H CHoCH confirms → Enter in 4H sync FVG
            # 
            # WHY body closure? "Generalii dau ordinul cu forță, nu cu umbra!"
            # Body closure = institutional commitment, not just a wick test.
            
            # V26.0: Scan last 80 candles (20 zile) — pullback Daily poate dura 2-3 săptămâni
            # 50 candle = 12.5 zile era prea scurt pentru pullback-uri extinse (ex: XAUUSD, GBPNZD)
            recent_h4_chochs = [ch for ch in h4_chochs if ch.index >= len(df_4h) - 80]
            
            for h4_choch in reversed(recent_h4_chochs):
                # H4 CHoCH direction must match Daily trend direction
                if h4_choch.direction != current_trend:
                    continue
                
                # V25.0: LIMITA DE VÂRSTĂ 48 CANDLE ELIMINATĂ
                # Orice CHoCH pe 4H în direcția biasului Daily este valid, indiferent de vârstă.
                # MOTIVUL: pullback-ul pe Daily poate dura 4, 14 sau 25 zile.
                # În secunda în care 4H printează un CHoCH aliniat → alinierea este validă.
                # Body closure garantată de detect_choch_and_bos() (V8.1).
                choch_age = len(df_4h) - 1 - h4_choch.index
                
                # Body closure already validated in detect_choch_and_bos (V8.1).
                # No FVG zone restriction — 4H is directional sync, not zone-specific.
                
                # ✅ VALID 4H CHoCH — direction matches D1 bias + body closure (no age limit)
                valid_h4_choch = h4_choch
                if debug:
                    print(f"   ✅ [V25.0 4H SYNC] {h4_choch.direction.upper()} CHoCH @ {h4_choch.break_price:.5f} ({choch_age} candle în urmă — fără limită vârstă)")
                    print(f"      Body closure validated (institutional commitment)")
                break
            
            # ━━━ V10.4: DETECT 4H SYNC FVG (entry zone from confirmation move) ━━━
            # After 4H CHoCH confirmed, find the FVG generated by that 4H impulse move.
            # This is the ENTRY ZONE — not the Daily FVG (which is the POI zone).
            if valid_h4_choch:
                h4_sync_fvg = self.detect_fvg(df_4h, valid_h4_choch)
                if h4_sync_fvg:
                    h4_sync_fvg.direction = current_trend  # Align with D1 bias
                    if debug:
                        print(f"   🎯 V10.4 4H SYNC FVG DETECTED: {h4_sync_fvg.bottom:.5f} - {h4_sync_fvg.top:.5f}")
                        print(f"      This is the ENTRY ZONE (from 4H confirmation move)")
                else:
                    if debug:
                        print(f"   ⚠️  V10.4: No 4H sync FVG found after CHoCH — will use Daily FVG for entry")
            
            if not valid_h4_choch:
                print(f"⏳ [V25.0 WAITING_D1_PULLBACK] {symbol}: {current_trend.upper()} — niciun 4H CHoCH {current_trend.upper()} găsit (fără limită temporală — așteptăm alinierea)")
                if debug:
                    print(f"   Bot în PÂNDĂ pe 4H — fără deadline, alinierea va veni când vine!")
        else:
            # V2.1 MODE: Skip 4H CHoCH requirement (original logic)
            if debug:
                print(f"   ⚠️  V2.1 MODE: Skipping 4H CHoCH requirement")
        
        # ━━━ V10.3 D1 DOMINANCE: DAILY POI (Point of Interest) VALIDATION ━━━
        # PHILOSOPHY by ФорексГод: "Generalii (D1) dau ordinul, soldații (4H) execută."
        # Price MUST be in or approaching the Daily FVG (POI) to qualify for READY.
        # If price hasn't reached the Daily POI, no execution — stay MONITORING.
        
        d1_poi_validated = False
        d1_poi_reason = ""
        
        # V42.7: LONG doar în POI/Discount (≤ POI top); SHORT doar în POI/Premium (≥ POI bottom)
        if current_trend == 'bullish':
            if current_price <= fvg.top:
                d1_poi_validated = True
                if price_in_fvg:
                    d1_poi_reason = "Price IN Daily FVG (POI reached)"
                elif current_price < fvg.bottom:
                    d1_poi_reason = "Price in Discount below Daily POI"
                else:
                    d1_poi_reason = "Price at Daily POI zone"
            else:
                d1_poi_reason = (
                    f"Price in Premium above POI top ({current_price:.5f} > {fvg.top:.5f}) — waiting pullback"
                )
        else:
            if current_price >= fvg.bottom:
                d1_poi_validated = True
                if price_in_fvg:
                    d1_poi_reason = "Price IN Daily FVG (POI reached)"
                elif current_price > fvg.top:
                    d1_poi_reason = "Price in Premium above Daily POI"
                else:
                    d1_poi_reason = "Price at Daily POI zone"
            else:
                d1_poi_reason = (
                    f"Price in Discount below POI bottom ({current_price:.5f} < {fvg.bottom:.5f}) — waiting pullback"
                )
        
        if debug:
            poi_status = "✅" if d1_poi_validated else "❌"
            print(f"\n{poi_status} V42.7 D1 POI VALIDATION: {d1_poi_reason}")
            print(f"   Daily FVG: {fvg.bottom:.5f} - {fvg.top:.5f}")
            print(f"   Current Price: {current_price:.5f}")
            if not d1_poi_validated:
                print(f"   ⏳ Status forced to WAITING_D1_PULLBACK — preț nu e la POI Daily")
        
        # V3.0 STRICT STATUS LOGIC:
        # READY = 4H CHoCH confirmed (same direction as Daily) AND price currently IN FVG
        # MONITORING = waiting for 4H CHoCH OR waiting for price to enter FVG
        # 🆕 V10.3: READY also requires D1 POI validation (price at/near Daily FVG)
        #
        # This prevents premature entries during aggressive pullbacks (like NZDUSD case)
        
        # V3.3 CONTINUITY FILTER RELAXED
        # CONTINUITY setups (Daily BOS) accept:
        # 1. Single recent BOS (< 30 candles) with strong FVG (quality ≥ 70)
        # 2. Multiple BOS (any age) = strong continuation
        # REVERSAL setups (Daily CHoCH) skip this - trend just changed
        # 🔥 V8.0: MOMENTUM entries skip this (3+ consecutive BOS by definition = strong continuation)
        # V25.0: continuity filter removed — Body Close Rule is sufficient (see block comment above).
        
        # V28.0/W→D→4H: confirmare LTF exclusiv pe 4H la execuție (multi_tf_radar)

        # STATUS LOGIC: V2.1 vs V3.0
        # 🔥 V8.0: MOMENTUM entries always READY (breakout strategy, no pullback confirmation needed)
        # ━━━ V11.9 GUARD: MOMENTUM READY blocat dacă macro trend e opus direcției ━━━
        # Cazul GBPJPY: 4 BOS bullish consecutive → MOMENTUM LONG, DAR macro trend bearish
        # (prețul a făcut CHoCH bearish vizibil pe chart dar Fractal Window 10 nu l-a prins încă)
        # → Verificăm overall_daily_trend: dacă e opus BOS-ului dominant, trimitem la MONITORING
        if hasattr(fvg, 'is_momentum_entry') and fvg.is_momentum_entry:
            _momentum_dir = current_trend
            _unconf_choch_blocks = False
            if self.enable_unconfirmed_guard:
                _unconf_choch_blocks = (
                    (_momentum_dir == 'bullish' and _unconfirmed_bearish_choch) or
                    (_momentum_dir == 'bearish' and _unconfirmed_bullish_choch)
                )
            if (
                not _unconf_choch_blocks
                and _range_state and _range_state.locked
                and _range_state.locked_bias == 'bearish' and _momentum_dir == 'bullish'
            ):
                _unconf_choch_blocks = True
            if _unconf_choch_blocks:
                # Posibil pullback major neconfirmat → nu executăm breakout, așteptăm 4H
                status = 'MONITORING'
                print(f"⏳ [V11.9 MOMENTUM GUARD] {symbol}: MOMENTUM {_momentum_dir.upper()} blocat — CHoCH opus neconfirmat detectat (drop/rise ≥0.8% față de swing în 60 bare). Așteptăm 4H CHoCH.")
            else:
                status = 'READY'
                if debug:
                    print(f"\n✅ STATUS: READY TO EXECUTE (MOMENTUM breakout - no wait)")
                    print(f"   ⚡ MOMENTUM ENTRY: Direct entry at last swing break")
                    print(f"   📊 Current Price: {current_price:.5f}")
                    print(f"   🎯 Entry Zone: {fvg.bottom:.5f} - {fvg.top:.5f}")
        elif not require_4h_choch:
            # V2.1 MODE: Daily CHoCH + FVG + price in FVG = READY
            if price_in_fvg:
                status = 'READY'
                if debug:
                    print(f"\n✅ STATUS: READY TO EXECUTE (V2.1 MODE)")
                    print(f"   ✓ Daily CHoCH: {current_trend.upper()}")
                    print(f"   ✓ Price IN FVG: {current_price:.5f} (FVG: {fvg.bottom:.5f} - {fvg.top:.5f})")
            else:
                status = 'MONITORING'
                if debug:
                    print(f"\n⏳ STATUS: MONITORING (V2.1 MODE - waiting for price in FVG)")
                    print(f"   ✓ Daily CHoCH: {current_trend.upper()}")
                    print(f"   ✗ Price NOT in FVG (current: {current_price:.5f})")
        elif valid_h4_choch:
            # V42.7: READY doar cu POI Daily validat + 4H CHoCH (V10.6 retracement = info, nu trigger)
            _swing_highs_v10 = self.detect_swing_highs(df_daily)
            _swing_lows_v10  = self.detect_swing_lows(df_daily)
            _macro_h_v10 = max(s.price for s in _swing_highs_v10[-5:]) if _swing_highs_v10 else None
            _macro_l_v10 = min(s.price for s in _swing_lows_v10[-5:])  if _swing_lows_v10  else None

            retracement_pct = 0.0
            if _macro_h_v10 and _macro_l_v10 and _macro_h_v10 > _macro_l_v10:
                _range_v10 = _macro_h_v10 - _macro_l_v10
                retracement_pct = (current_price - _macro_l_v10) / _range_v10 * 100.0
                if debug:
                    direction_lbl = "≤55% (discount ref)" if current_trend == 'bullish' else "≥45% (premium ref)"
                    print(f"\n📐 V10.6 RETRACEMENT INFO (non-trigger): {retracement_pct:.1f}% from low → {direction_lbl}")

            if d1_poi_validated:
                status = 'READY'
                if debug:
                    sync_fvg_info = ""
                    if h4_sync_fvg:
                        sync_fvg_info = f"\n   ✓ 4H Sync FVG (Entry Zone): {h4_sync_fvg.bottom:.5f} - {h4_sync_fvg.top:.5f}"
                    print(f"\n✅ STATUS: READY TO EXECUTE (V42.7 — D1 POI + 4H CHoCH)")
                    print(f"   ✓ D1 Bias: {strategy_type.upper()} ({current_trend.upper()})")
                    print(f"   ✓ 4H CHoCH Body Close: {valid_h4_choch.direction.upper()} @ {valid_h4_choch.break_price:.5f}")
                    print(f"   ✓ Daily FVG (POI): {fvg.bottom:.5f} - {fvg.top:.5f}{sync_fvg_info}")
                    print(f"   📊 Current Price: {current_price:.5f}")
            else:
                status = 'WAITING_D1_PULLBACK'
                print(f"⏳ [V42.7 POI GATE] {symbol}: 4H CHoCH aliniat, dar preț NU e la POI Daily → WAITING_D1_PULLBACK")
                if debug:
                    print(f"   ✓ D1 Bias: {strategy_type.upper()} ({current_trend.upper()})")
                    print(f"   ✓ 4H Sync CHoCH: {valid_h4_choch.direction.upper()} @ {valid_h4_choch.break_price:.5f}")
                    print(f"   ✗ D1 POI: {d1_poi_reason}")
                    print(f"   ⏳ Așteptăm pullback la POI Daily înainte de READY")
        else:
            # V28.0: WAITING_D1_PULLBACK — D1 break valid (CHoCH/BOS confirmat cu Body Close)
            # Așteptăm 4H CHoCH aliniat cu bias-ul Daily. Status curat, vizibil în Telegram.
            # multi_tf_radar verifică continuu 4H și upgradează la READY la aliniere.
            status = 'WAITING_D1_PULLBACK'
            print(f"⏳ [V28.0 BIAS] {symbol}: D1 {current_trend.upper()} {_signal_label} valid → WAITING_D1_PULLBACK (fără 4H CHoCH încă)")
            if debug:
                print(f"   ✓ Daily CHoCH/BOS: {current_trend.upper()}")
                print(f"   ✓ FVG Zone: {fvg.bottom:.5f} - {fvg.top:.5f}")
                print(f"   ✗ 4H CHoCH încă nedetectat — radar monitorizează")
                print(f"   📊 Current Price: {current_price:.5f}")
        
        return self._scan_finalize_trade_setup(locals())
