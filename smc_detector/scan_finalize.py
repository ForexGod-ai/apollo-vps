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



class ScanFinalizeMixin:
    """V67 C: scan finalize/build phase."""

    def _scan_finalize_trade_setup(self, _scan: dict) -> Optional[TradeSetup]:
        l = _scan
        _adr = l['_adr']
        _poi_res = l['_poi_res']
        _signal_label = l['_signal_label']
        _structural_breach = l['_structural_breach']
        current_price = l['current_price']
        current_trend = l['current_trend']
        d1_ctx = l['d1_ctx']
        debug = l['debug']
        df_4h = l['df_4h']
        df_daily = l['df_daily']
        fvg = l['fvg']
        h4_sync_fvg = l['h4_sync_fvg']
        latest_signal = l['latest_signal']
        order_block = l['order_block']
        priority = l['priority']
        recent_h4_chochs = l['recent_h4_chochs']
        require_4h_choch = l['require_4h_choch']
        skip_fvg_quality = l['skip_fvg_quality']
        status = l['status']
        stored_poi_bottom = l['stored_poi_bottom']
        stored_poi_top = l['stored_poi_top']
        strategy_type = l['strategy_type']
        symbol = l['symbol']
        valid_h4_choch = l['valid_h4_choch']
        # Step 7: Calculate entry, SL, TP
        # Use H4 CHoCH for both REVERSAL and CONTINUITY
        h4_signal = valid_h4_choch

        # V30.0: Dead code eliminat — primul bloc OB (order_block=None la acest punct,
        # detect_order_block() este apelat abia la Step 8 mai jos).
        # Flux corect: Step 7 = entry/sl/tp din h4_signal sau FVG edge;
        #              Step 8 = detect_order_block → poate OVERRIDE entry/sl dacă ob_score ≥ 7.
        if h4_signal:
            # ✅ V14.0 BUG#2 FIX: Prioritizează h4_sync_fvg (entry zone precisă din mișcarea 4H)
            # față de Daily FVG (POI macro). Daily FVG = zona de interes, h4_sync_fvg = entry sniper.
            # Dacă Fibonacci pe impulsul macro 4H cade sub FVG (ex: XTIUSD impulse 31$),
            # entry era decuplat complet de zonă. Cu h4_sync_fvg, entry = marginea FVG-ului 4H real.
            fvg_for_entry = h4_sync_fvg if h4_sync_fvg else fvg
            entry, sl, tp = self.calculate_entry_sl_tp(
                symbol, fvg_for_entry, h4_signal, df_4h, df_daily,
                daily_bias_active=getattr(fvg, '_is_daily_bias_zone', False)  # V30.0
            )
            # V26.0: SALVARE BIAS — când RR<4 sau SL>cap, NU mai aruncăm setup-ul.
            # Bias-ul D1 este REAL (CHoCH/BOS confirmat + 4H CHoCH aliniat).
            # Salvăm în MONITORING cu FVG edge ca entry informativ.
            # RR va fi recalculat de multi_tf_radar la tranziția EXECUTE_NOW.
            if entry is None:
                print(f"⏳ [V26.0 BIAS SALVAT] {symbol}: calculate_entry_sl_tp eșuat (RR<4 sau SL>cap) → forțat MONITORING cu FVG edge")
                fvg_ref = h4_sync_fvg if h4_sync_fvg else fvg
                if current_trend == 'bullish':
                    entry = fvg_ref.bottom
                    sl    = fvg_ref.bottom * 0.995
                    tp    = fvg_ref.top    * 1.02
                else:
                    entry = fvg_ref.top
                    sl    = fvg_ref.top    * 1.005
                    tp    = fvg_ref.bottom * 0.98
                status = 'MONITORING'  # Forțat — RR informativ, recalculat la EXECUTE_NOW
            if debug:
                fvg_source = 'h4_sync_fvg' if h4_sync_fvg else 'Daily FVG (fallback)'
                print(f"\n💰 FVG-based Trade Levels — Entry zone: {fvg_source}")
        
        else:
            # No 4H CHoCH yet - use FVG edge as entry (discount/premium zone)
            # LONG: Entry at FVG bottom (buy the discount)
            # SHORT: Entry at FVG top (sell the premium)
            if current_trend == 'bullish':
                entry = fvg.bottom  # Buy at FVG bottom
                sl = fvg.bottom * 0.998  # SL below FVG
                tp = fvg.top * 1.015  # TP above FVG
            else:
                entry = fvg.top  # Sell at FVG top
                sl = fvg.top * 1.002  # SL above FVG
                tp = fvg.bottom * 0.985  # TP below FVG
        
        if debug:
            print(f"\n💰 Trade Levels:")
            print(f"   Entry: {entry:.5f}")
            print(f"   SL: {sl:.5f}")
            print(f"   TP: {tp:.5f}")
            rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
            print(f"   Risk:Reward: 1:{rr:.2f}")
            print(f"{'='*60}\n")
        
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        risk_reward = reward / risk if risk > 0 else 0

        # ─── V25.0: RR FLOOR — EVALUAT DOAR LA READY (EXECUTE_NOW) ────────────────────
        # MOTIVUL: În faza WAITING_D1_PULLBACK, SL și TP sunt calculate din structura curentă
        # care NU este ancora finală. Ancora reală = swing-ul 4H proaspăt de la momentul
        # alinierii (EXECUTE_NOW). Un RR de 1:2.5 calculat acum poate deveni 1:6 când
        # prețul ajunge la FVG și CHoCH-ul 4H reface structura.
        # RR-ul se recalculează în setup_executor_monitor.py la tranziția EXECUTE_NOW.
        # ─────────────────────────────────────────────────────────────────────────────
        _MIN_RR = 4.0  # V10.2: floor structural 1:4 — activ NUMAI la READY / EXECUTE_NOW
        if risk_reward < _MIN_RR and status == 'READY':
            # V43.5: NU aruncăm setup-ul — bias + 4H CHoCH + POI sunt reale.
            # RR la scan e informativ (SL/TP se recalculează la EXECUTE_NOW când prețul
            # ajunge în zonă). Fără downgrade, daily_scanner cade în bias_fallback (fără entry/SL/TP).
            print(f"⏳ [V43.5 RR DEFER] {symbol}: RR=1:{risk_reward:.2f} < 1:{_MIN_RR} la READY → downgrade MONITORING")
            print(f"   Entry={entry:.5f} | SL={sl:.5f} | TP={tp:.5f}")
            print(f"   Risk={abs(entry-sl):.5f} | Reward={abs(tp-entry):.5f} — recalculat la EXECUTE_NOW")
            status = 'MONITORING'
        elif risk_reward < _MIN_RR and debug:
            print(f"   ℹ️  [V25.0 RR INFO] RR=1:{risk_reward:.2f} < 1:{_MIN_RR} dar status=MONITORING — NU respingem (va fi recalculat la EXECUTE_NOW)")
        
        # 🚨 CHECK 1: Price already moved too close to TP?
        # If current price is within 20% of TP distance, it's too late
        current_price = df_daily['close'].iloc[-1]
        distance_to_tp = abs(current_price - tp)
        total_move = abs(entry - tp)
        _pct_ramas = (distance_to_tp / total_move * 100) if total_move > 0 else 100.0
        
        if debug:
            print(f"📊 [V27 TOO-LATE {symbol}] {100 - _pct_ramas:.1f}% spre TP | h4={'DA' if h4_signal else 'NU (placeholder)'} | status={status} | curr={current_price:.5f} entry={entry:.5f} tp={tp:.5f}")
        
        # V30.0: Prag relaxat 0.20→0.10 (90%+ spre TP = prea tarziu, nu 80%).
        # + WAITING_D1_PULLBACK exclus: entry/tp sunt placeholder, nu reale → filtrul era fals.
        if h4_signal and total_move > 0 and (distance_to_tp / total_move) < 0.10 and status != 'WAITING_D1_PULLBACK':
            print(f"⛔ [DROP {symbol}] FILTRU 'TOO LATE' — {100 - _pct_ramas:.1f}% completat | h4_signal PREZENT → entry/tp REALE | entry={entry:.5f} tp={tp:.5f}")
            return None  # Price already 80%+ toward TP - TOO LATE!
        
        # V67 D: RE-ENTRY legacy removed — SL structural atins = setup respins
        if h4_signal:
            sl_broken = (
                (fvg.direction == 'bearish' and current_price > sl)
                or (fvg.direction != 'bearish' and current_price < sl)
            )
            if sl_broken:
                print(f"⛔ [DROP {symbol}] SL structural atins (curr={current_price:.5f} vs SL={sl:.5f}) — fără re-entry legacy")
                return None

        # ✅ Setup still valid! Price hasn't hit SL or TP yet

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # V25.3 XAUUSD: FILTRUL DIRECȚIE ELIMINAT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Filtrul 'Only CONTINUATION bearish' (V2.0) ELIMINAT.
        # MOTIVUL: Gold era în trend BULLISH masiv în 2025-2026 (2000→ 3200$).
        # Filtrul bloca 100% din setup-urile XAUUSD pentru că current_trend='bullish'.
        # V25.0 Universal Bias detectează corect direcția din structură (CHoCH/BOS).
        # XAUUSD acceptă acum orice direcție validă: LONG (pull la discount) sau SHORT (pull la premium).
        # Filtrele de calitate rămân active: gap ≥0.10%, body ≥25%, quality score ≥15.
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if debug and symbol == 'XAUUSD':
            print(f"✅ [V25.3 XAUUSD] Direcție: {current_trend.upper()} | Tip: {strategy_type} — acceptat (filtru V2.0 eliminat)")
        
        # 🌍 UNIVERSAL ANTI-OVERTRADING FILTER: Max 4 trades per FVG zone (ALL PAIRS)
        # This prevents NZDUSD-style hemorrhaging (-$1,054 on 26 trades with small SLs)
        # Preserves winning clusters (Mai 4-7) while blocking endless overtrading
        if not skip_fvg_quality:
            # Initialize symbol tracker if needed
            if symbol not in self.fvg_zones_tracker:
                self.fvg_zones_tracker[symbol] = []
            
            current_fvg_top = fvg.top
            current_fvg_bottom = fvg.bottom
            current_date = df_daily.index[-1]
            
            # Find matching FVG zone (>50% overlap)
            matched_zone_idx = None
            for idx, (prev_top, prev_bottom, prev_date, trade_count) in enumerate(self.fvg_zones_tracker[symbol]):
                # Calculate overlap percentage
                overlap_top = min(current_fvg_top, prev_top)
                overlap_bottom = max(current_fvg_bottom, prev_bottom)
                
                if overlap_bottom < overlap_top:
                    overlap_size = overlap_top - overlap_bottom
                    current_size = current_fvg_top - current_fvg_bottom
                    prev_size = prev_top - prev_bottom
                    
                    overlap_pct = overlap_size / min(current_size, prev_size) if min(current_size, prev_size) > 0 else 0
                    
                    if overlap_pct > 0.50:  # 50% overlap = same zone
                        matched_zone_idx = idx
                        break
            
            if matched_zone_idx is not None:
                # Existing FVG zone - check trade count
                prev_top, prev_bottom, prev_date, trade_count = self.fvg_zones_tracker[symbol][matched_zone_idx]
                
                if trade_count >= 4:
                    # Too many trades in this zone already
                    # V30.0: print afara din debug — vizibil în producție
                    print(f"\n❌ [V30.0 ANTI-OT] REJECTED {symbol}: FVG zone epuizată ({trade_count} trades în zonă)")
                    print(f"   Zone: {prev_bottom:.5f}-{prev_top:.5f} — 🛡️ UNIVERSAL anti-overtrading")
                    return None
                
                # Increment trade count for this zone
                self.fvg_zones_tracker[symbol][matched_zone_idx] = (prev_top, prev_bottom, prev_date, trade_count + 1)
                
                if debug:
                    print(f"\n✅ {symbol} ACCEPTED: FVG zone trade #{trade_count + 1}/4")
            else:
                # New FVG zone - add with trade_count = 1
                self.fvg_zones_tracker[symbol].append((current_fvg_top, current_fvg_bottom, current_date, 1))
                
                if debug:
                    print(f"\n✅ {symbol} ACCEPTED: New FVG zone {current_fvg_bottom:.5f}-{current_fvg_top:.5f}")
                    print(f"   Total tracked zones for {symbol}: {len(self.fvg_zones_tracker[symbol])}")
        
        # 💧 V4.0 LIQUIDITY SWEEP DETECTION (Faza 1)
        liquidity_sweep = self.detect_liquidity_sweep(
            df=df_daily,
            choch=latest_signal,
            symbol=symbol,
            lookback=20,
            tolerance_pips=5,
            debug=debug
        )
        
        # Confidence boost if liquidity swept
        confidence_boost = 0
        if liquidity_sweep and liquidity_sweep['sweep_detected']:
            confidence_boost = 20  # +20 points for liquidity validation
            if debug:
                print(f"   ✅ LIQUIDITY SWEEP CONFIRMED: +{confidence_boost} confidence")
        
        # 📊 V4.0 PREMIUM/DISCOUNT FILTER (Faza 1)
        # ✅ V15.2 FIX: Skip P/D filter pentru REVERSAL — CHoCH + FVG deja confirmă structural.
        # Filtrul P/D se bazează pe lumânarea Daily curentă (range mic) → pentru REVERSAL
        # prețul e într-un pullback și apare în "DISCOUNT" pe lumânarea zilei, deși macro e premium.
        # Ex: BTCUSD pullback bearish la 80k — lumânarea zilei mică → 25% = DISCOUNT → REJECT greșit.
        # REVERSAL = CHoCH a confirmat schimbarea de trend → P/D pe lumânarea zilei e irelevant.
        # P/D rămâne ACTIV doar pentru CONTINUATION (trend urmărit, intri la nivelul corect).
        # ✅ V10.8: Skip for MOMENTUM entries (breakout = intrăm la BOS break, P/D irrelevant)
        _is_momentum = hasattr(fvg, 'is_momentum_entry') and fvg.is_momentum_entry
        _is_reversal = (strategy_type == 'reversal')
        if not skip_fvg_quality and not _is_momentum and not _is_reversal:
            # V37.17: calculate_premium_discount() era inexistentă → crash pe CONTINUATION (XAUUSD)
            macro_high, macro_low, premium_threshold, discount_threshold = (
                self.calculate_premium_discount_zones(df_daily)
            )
            _macro_range = macro_high - macro_low
            if _macro_range > 0:
                _pd_pct = ((current_price - macro_low) / _macro_range) * 100.0
            else:
                _pd_pct = 50.0
            if current_price >= premium_threshold:
                _pd_zone = 'PREMIUM'
            elif current_price <= discount_threshold:
                _pd_zone = 'DISCOUNT'
            else:
                _pd_zone = 'EQUILIBRIUM'
            premium_discount = {'percentage': _pd_pct, 'zone': _pd_zone}
            if debug:
                print(f"\n📊 [V37.17 P/D] Macro range {macro_low:.5f}-{macro_high:.5f} → "
                      f"{_pd_zone} {_pd_pct:.1f}%")

            # V26.0: P/D filter relaxat — prag extreme 85/15 + bypass complet la MONITORING
            # PROBLEMA V15.2: calculate_premium_discount() citește O SINGURĂ lumânare Daily.
            # Trend bullish → lumânare closes la high → 85-95% = PREMIUM → LONG respins greșit.
            # FIX: blocăm NUMAI extremele absolute (>85% / <15%) ȘI NUMAI la READY.
            # La MONITORING bypass total — geometria finală se recalculează la EXECUTE_NOW.
            _pd_pct = premium_discount['percentage']
            if current_trend == 'bullish' and _pd_pct > 85 and status == 'READY':
                if debug:
                    print(f"\n❌ REJECTED: CONTINUATION LONG EXTREME PREMIUM ({_pd_pct:.1f}% > 85%) la READY")
                return None

            if current_trend == 'bearish' and _pd_pct < 15 and status == 'READY':
                if debug:
                    print(f"\n❌ REJECTED: CONTINUATION SHORT EXTREME DISCOUNT ({_pd_pct:.1f}% < 15%) la READY")
                return None

            if debug:
                _pd_bypass = (status != 'READY')
                print(f"   [V26.0 P/D] {premium_discount['zone']} {_pd_pct:.1f}% → "
                      f"{'⚠️ BYPASS (MONITORING)' if _pd_bypass else '✅ PASSED (sub prag extrem)'}")
        elif _is_reversal and debug:
            print(f"\n✅ [V15.2] REVERSAL strategy — P/D daily candle filter SKIPPED (CHoCH+FVG confirmă structural)")
        elif _is_momentum and debug:
            print(f"\n⚡ MOMENTUM ENTRY: Skipping P/D daily filter (breakout — P/D ignored)")
        
        if not _is_momentum and not skip_fvg_quality and debug and 'premium_discount' in locals():
            print(f"\n✅ PREMIUM/DISCOUNT CHECK PASSED: {premium_discount['zone']} zone")
        
        # 🎯 V3.5 ORDER BLOCKS: Detect OB pentru entry precision + corelație cu FVG
        order_block = self.detect_order_block(
            df=df_daily,
            choch=latest_signal,
            fvg=fvg,
            debug=debug
        )
        
        # 📦 V4.0 ACTIVATE ORDER BLOCKS: Use OB for entry/SL if valid (Faza 1)
        # Previously OB was detected but NOT used - now we enforce it!
        if order_block and order_block.ob_score >= 7:
            # Use Order Block for precise entry instead of FVG middle
            if debug:
                print(f"\n📦 ORDER BLOCK ACTIVATED for Entry/SL:")
                print(f"   OB Zone: {order_block.bottom:.5f} - {order_block.top:.5f}")
                print(f"   OB Score: {order_block.ob_score}/10")
                print(f"   Using OB middle for entry (more precise than FVG)")

            # Override entry calculation to use OB
            entry = order_block.middle

            # Tighter SL using OB boundaries
            if current_trend == 'bullish':
                sl = order_block.bottom * 0.9995  # 5 pips below OB bottom
            else:
                sl = order_block.top * 1.0005  # 5 pips above OB top

            # ✅ V14.3 FIX: Recalculează TP din structura D1 când OB overrideaza entry/SL
            if current_trend == 'bullish':
                _swing_highs_ob = self.detect_swing_highs(df_daily)
                _highs_above = [sh for sh in _swing_highs_ob if df_daily['high'].iloc[sh.index] > entry]
                if _highs_above:
                    _nearest_high = min(_highs_above, key=lambda sh: df_daily['high'].iloc[sh.index])
                    tp = df_daily['high'].iloc[_nearest_high.index]
                else:
                    tp = df_daily['high'].iloc[:-1].max()
                # Dacă TP tot e sub entry după recalcul → fallback la max D1
                if tp <= entry:
                    tp = df_daily['high'].iloc[:-1].max()
                if debug:
                    print(f"   ✅ [V14.3 OB TP RECALC] LONG TP from D1 swing high: {tp:.5f}")
            else:
                _swing_lows_ob = self.detect_swing_lows(df_daily)
                _lows_below = [sl_pt for sl_pt in _swing_lows_ob if df_daily['low'].iloc[sl_pt.index] < entry]
                if _lows_below:
                    _nearest_low = max(_lows_below, key=lambda sl_pt: df_daily['low'].iloc[sl_pt.index])
                    tp = df_daily['low'].iloc[_nearest_low.index]
                else:
                    tp = df_daily['low'].iloc[:-1].min()
                # Dacă TP tot e deasupra entry → fallback la min D1
                if tp >= entry:
                    tp = df_daily['low'].iloc[:-1].min()
                if debug:
                    print(f"   ✅ [V14.3 OB TP RECALC] SHORT TP from D1 swing low: {tp:.5f}")
        else:
            # V30.0 FIX PRINCIPAL: NU mai resetăm entry/sl la None!
            # entry și sl sunt deja calculate (calculate_entry_sl_tp sau FVG edge din Step 7).
            # OB score < 7 = nu override cu OB, dar menținăm valorile existente.
            # Vechiul cod: entry=None; sl=None → triggereza V14.2 NULL GUARD → return None.
            if debug and order_block:
                print(f"\n⚠️ ORDER BLOCK NOT ACTIVATED: Score {order_block.ob_score}/10 < 7")
                print(f"   Menținând entry/sl calculate anterior (FVG-based sau h4_signal)")
            elif debug:
                print(f"\nℹ️ [V30.0] Fără OB valid — entry/sl din Step 7 rămân nemodificate")
        
        # Calculate ESTIMATED RR pentru swing trading (minimum 1:5)
        estimated_rr = risk_reward  # Default to standard RR
        if order_block and order_block.has_unfilled_fvg:
            # OB + unfilled FVG = HIGH PROBABILITY swing (boost RR estimate)
            estimated_rr = risk_reward * 1.5  # 1.5x multiplier pentru OB setups
        
        if debug and order_block:
            print(f"\n🎯 SWING SETUP ENHANCED:")
            print(f"   OB Score: {order_block.ob_score}/10")
            print(f"   Estimated RR: 1:{estimated_rr:.1f} (minimum)")
            print(f"   Entry Zone (OB): {order_block.bottom:.5f} - {order_block.top:.5f}")
        
        # 🎯 V3.4 ORDER BLOCKS: Store FVG as price magnet for future reference
        # This prepares infrastructure for Order Block detection in V3.5
        self.store_fvg_magnet(symbol, '4H', fvg, debug=debug)  # Store from 4H timeframe
        
        # ✅ V10.5 STRATEGY LOCK GUARD: Reject setup if strategy_type is ambiguous or default
        # Prevents the dataclass default 'reversal' from silently passing through
        # if the decision logic above was somehow bypassed.
        if strategy_type not in ('reversal', 'continuation'):
            if debug:
                print(f"\n\u274c REJECTED {symbol}: strategy_type='{strategy_type}' is not valid (must be 'reversal' or 'continuation')")
                print(f"   Circuit D1\u21924H requires an explicit D1 bias. Setup discarded.")
            return None

        # ✅ V14.2 FINAL DIRECTION GUARD — ultimul zid înainte de TradeSetup
        # Bug: blocul OB din step 2 (linie ~4395) overrideaza entry+SL dar NU și TP.
        # Dacă entry vine din OB.middle (zona 212.94) dar tp vine din else-branch FVG
        # (fvg.top * 1.015 = 206.90), TP iese sub entry pentru LONG → trade inversat!
        # Fix: verificare finală direcțională — dacă TP e în direcție greșită → anulat.
        if entry is not None and sl is not None and tp is not None:
            if current_trend == 'bullish' and tp <= entry:
                print(f"⛔ [V14.2 FINAL DIRECTION GUARD] {symbol} LONG: TP={tp:.5f} <= Entry={entry:.5f} "
                      f"— direcție GREȘITĂ (OB override fără recalcul TP). Trade ANULAT.")
                return None
            elif current_trend == 'bearish' and tp >= entry:
                print(f"⛔ [V14.2 FINAL DIRECTION GUARD] {symbol} SHORT: TP={tp:.5f} >= Entry={entry:.5f} "
                      f"— direcție GREȘITĂ (OB override fără recalcul TP). Trade ANULAT.")
                return None
        elif entry is None or sl is None or tp is None:
            print(f"⛔ [V14.2 NULL GUARD] {symbol}: entry/sl/tp are None — setup incomplete. Trade ANULAT.")
            return None
        

        # Return setup (MONITORING or READY)
        # Convert pandas Timestamp to Python datetime properly
        # Get the actual timestamp value (not the index position!)
        try:
            setup_timestamp = df_4h.index[-1]
            # If it's a pandas Timestamp, convert to Python datetime
            if hasattr(setup_timestamp, 'to_pydatetime'):
                setup_timestamp = setup_timestamp.to_pydatetime()
            # If it's somehow an int (position), use current time
            elif isinstance(setup_timestamp, (int, np.integer)):
                setup_timestamp = datetime.now()
        except Exception as e:
            print(f"⚠️ Warning: Could not convert setup_time properly: {e}")
            setup_timestamp = datetime.now()
        
        # Store liquidity sweep and premium/discount in setup for reporting
        setup = TradeSetup(
            symbol=symbol,
            daily_choch=latest_signal,  # Daily CHoCH (REVERSAL) or BOS (CONTINUITY)
            fvg=fvg,  # Daily FVG (D1 POI zone)
            h4_choch=h4_signal,  # H4 CHoCH (directional sync confirmation)
            order_block=order_block,  # 📦 V3.5: Order Block pentru entry precision
            entry_price=entry,  # V4.0: Uses OB if available, else FVG
            stop_loss=sl,  # V4.0: Tighter SL from OB if available
            take_profit=tp,
            risk_reward=risk_reward,
            estimated_rr=estimated_rr + (confidence_boost / 20) if confidence_boost > 0 else estimated_rr,  # Boost RR if liquidity swept
            setup_time=setup_timestamp,  # Properly converted Python datetime
            priority=priority,
            strategy_type=strategy_type,  # D1 bias: 'reversal' or 'continuation'
            status=status,
            # V10.4: 4H Sync FVG — entry zone from 4H confirmation move
            h4_sync_fvg=h4_sync_fvg if h4_sync_fvg else None,
            h4_sync_fvg_top=float(h4_sync_fvg.top) if h4_sync_fvg else 0.0,
            h4_sync_fvg_bottom=float(h4_sync_fvg.bottom) if h4_sync_fvg else 0.0,
            # V24.6 PERMISSIVE DAILY FLOW: FVG sintetic din Equilibrium swing-uri Daily
            daily_bias_active=getattr(fvg, '_is_daily_bias_zone', False),
            structural_breach=_structural_breach,
            adr_lh=float(_adr.last_lh) if _adr else None,
            adr_ll=float(_adr.last_ll) if _adr else None,
            adr_hl=float(_adr.last_hl) if _adr else None,
            poi_v43_source=_poi_res.poi_source,
            preserve_stored_poi=_poi_res.preserve_stored_poi,
            d1_bias_direction=current_trend,
            d1_signal_type=_signal_label,
        )
        
        # 💧 V4.0: Store liquidity sweep info (for Telegram reporting)
        if liquidity_sweep:
            setup.liquidity_sweep = liquidity_sweep
            setup.confidence_boost = confidence_boost
        
        return setup
