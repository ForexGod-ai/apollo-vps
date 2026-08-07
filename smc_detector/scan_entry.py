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


class ScanEntryMixin:
    """V67 C: entry / SL / TP calculation."""

    def _get_asset_class(self, symbol: str) -> str:
        """Detect asset class for symbol-specific SL rules"""
        symbol_upper = symbol.upper()
        if any(x in symbol_upper for x in ['BTC', 'ETH', 'XRP', 'LTC', 'ADA', 'DOGE']):
            return 'crypto'
        elif any(x in symbol_upper for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
            return 'metals'
        elif any(x in symbol_upper for x in ['XTI', 'WTI', 'OIL', 'BRENT']):
            return 'energy'
        elif 'JPY' in symbol_upper:
            return 'jpy_pairs'
        else:
            return 'forex'

    def _uses_macro_ceiling(self, symbol: Optional[str]) -> bool:
        """V40.1: BTC/crypto + mărfuri volatile — tavan D1 din fereastra 90–150 bare."""
        if not symbol:
            return False
        return self._get_asset_class(symbol) in ('crypto', 'metals', 'energy')

    def _compute_macro_ceiling_d1(self, df: pd.DataFrame, lookback: int) -> Tuple[float, int]:
        """Max body-high (open/close) pe ultimele `lookback` bare D1."""
        lb = min(lookback, len(df))
        if lb < 1:
            return 0.0, 0
        start = len(df) - lb
        best_high = 0.0
        best_bar = start
        for pos in range(start, len(df)):
            bh = self._swing_body_high(df, pos)
            if bh > best_high:
                best_high = bh
                best_bar = pos
        return best_high, best_bar

    def _get_pip_size(self, symbol: str) -> float:
        """V37.0 — delegat la pip_utils.get_pip_size."""
        from pip_utils import get_pip_size
        return get_pip_size(symbol)

    def _calculate_minimum_sl_distance(self, symbol: str, entry_price: float, asset_class: str) -> float:
        """
        V10.0 — Minimum SL structural distance.
        Crypto: fara floor procentual fix — structura dicteaza.
        Forex/JPY/Metals: 30 pips hard floor pentru a evita slippage kill.
        """
        pip_size = self._get_pip_size(symbol)
        if asset_class == 'crypto':
            # V10.0: nu mai aplicam 1.5% fix — structura 4H dicteaza SL
            # Pastram un floor minimal de 0.3% pentru a evita erori broker
            min_distance = entry_price * 0.003
            return min_distance
        
        elif asset_class == 'metals':
            # V42.6: XAU sniper 30p max — era 50p floor (forța SL prea larg)
            return 30 * pip_size
        elif asset_class == 'energy':
            return 30 * pip_size
        elif asset_class == 'jpy_pairs':
            # JPY: 30 pips (0.01 pip_size) = 0.30
            return 30 * pip_size
        else:
            # Forex standard: 30 pips (0.0001 pip_size) = 0.0030
            return 30 * pip_size

    def calculate_entry_sl_tp(
        self,
        symbol: str,
        fvg: FVG,
        h4_choch: CHoCH,
        df_4h: pd.DataFrame,
        df_daily: pd.DataFrame,
        daily_bias_active: bool = False  # V30.0: True = setup WAITING, RR threshold 4.0→2.0
    ) -> Tuple[float, float, float]:
        """
        ═══════════════════════════════════════════════════════════════════
        V13.2 — STRUCTURAL SWING SL/TP — GENERALUL (MAX WICK PRE-CHoCH)
        ═══════════════════════════════════════════════════════════════════

        FLUX DE EXECUȚIE:
          1. D1 POI (FVG Daily) atins                      → MAGNET
          2. 4H CHoCH confirmat (body closure)              → CONFIRMARE
          3. Pullback în FVG 4H — zona 70-80% Fibonacci     → ENTRY SNIPER
          4. SL = cel mai înalt/scăzut WICK din TOATE       → GENERALUL
             swing-urile 4H înainte de CHoCH + 1 pip buffer
             (NU ultimul fractal [-1] — acela poate fi minor!)
          5. TP = primul swing Low/High D1 dincolo de       → STRUCTURA REALĂ
             prețul curent (nu extrema din 10 luni)
          6. RR ≥ 1:4 structural                            → EXECUȚIE

        REGULI ABSOLUTE V13.2 (REPAIR LOG USDCHF 2026-04-07):
          - SL SHORT = max wick HIGH dintre TOATE swing-urile 4H pre-CHoCH
          - SL LONG  = min wick LOW  dintre TOATE swing-urile 4H pre-CHoCH
          - Dacă distanța SL > 100 pips → trade RESPINS (RR nesustenabil)
            Botul NU strânge SL artificial — ori respiră cu structura, ori NU intră
          - 1 pip buffer pe SL (protecție wick-hunt)
          - Fractal Window 10: doar munții/văile reale
          - Dacă RR < 1:4 → trade RESPINS, nu ajustat
        ═══════════════════════════════════════════════════════════════════
        """

        if fvg.direction == 'bullish':
            # ══════════════════════════════════════════════
            # LONG TRADE
            # ══════════════════════════════════════════════

            # ── ENTRY: Marginea FVG 4H în zona 70-80% Fibonacci ──────────
            # FVG 4H creat de CHoCH = zona de pullback sniper.
            # Impulsul 4H = de la swing low la swing high al CHoCH.
            # Fibonacci 70-80% = Golden Zone instituțională.
            # Entry = marginea INFERIOARĂ a FVG dacă FVG se suprapune cu 70-80%.
            # Dacă nu avem FVG separat, folosim direct 70-80% din impulsul 4H.
            #
            # Implementare: h4_choch conține swing_low și swing_high ale impulsului.
            # Fibonacci se trage pe acest impuls. FVG 4H (parametrul fvg) este
            # FVG-ul creat de CHoCH — entry = fvg.bottom (marginea de jos a FVG)
            # dacă aceasta se află în zona 70-80% Fibonacci.
            #
            # Fallback: dacă fvg.bottom nu e în zona 70-80%, calculăm direct
            # nivelul 75% din impulsul CHoCH (mijlocul Golden Zone).

            if h4_choch is not None and hasattr(h4_choch, 'swing_low') and h4_choch.swing_low is not None:
                impulse_low = h4_choch.swing_low
                impulse_high = h4_choch.swing_high if hasattr(h4_choch, 'swing_high') and h4_choch.swing_high is not None else fvg.top
                impulse_range = impulse_high - impulse_low
                fib_70 = impulse_high - (impulse_range * 0.70)   # Pullback 70% = nivel 70
                fib_80 = impulse_high - (impulse_range * 0.80)   # Pullback 80% = nivel 80
                fib_75 = impulse_high - (impulse_range * 0.75)   # Mijlocul Golden Zone

                # Verifică dacă FVG se suprapune cu zona 70-80%
                fvg_in_golden_zone = (fvg.bottom <= fib_70 and fvg.top >= fib_80)
                if fvg_in_golden_zone:
                    # Entry = marginea inferioară a FVG (primul punct de intrare în zonă)
                    entry = fvg.bottom
                else:
                    # FVG nu e în zona exactă — folosim nivelul 75% direct
                    entry = fib_75
            else:
                # Fallback fără date CHoCH: marginea inferioară a FVG
                entry = fvg.bottom

            # ── V14.1 SL STRUCTURAL 4H: ultimul swing Low VALID pre-CHoCH (Fix #9) ────────────────────
            # REGULA SMC CORECTĂ: SL = ultimul punct structural creat ÎNAINTE de impulsul CHoCH.
            # Nu maximul/minimul absolut din toată istoria (bug V13.2 = 385 pips pe GBPNZD).
            # Filtru ATR: eliminăm micro-fractali (swing-uri sub 0.5x ATR = zgomot, nu structură).
            h4_choch_idx = h4_choch.index if h4_choch is not None and hasattr(h4_choch, 'index') else max(0, len(df_4h) - 40)
            swing_lows_4h_list = self.detect_swing_lows(df_4h)
            lows_before_choch = [sl for sl in swing_lows_4h_list if sl.index <= h4_choch_idx]
            # V36.0 FIX B4: pip_size corect per instrument (XTI/OIL era 0.0001 → SL 100x eronat)
            if 'JPY' in symbol:
                pip_size = 0.01
            elif any(x in symbol.upper() for x in ['XAU', 'XAG', 'GOLD']):
                pip_size = 0.10    # XAUUSD IC Markets: 1 pip = $0.10
            elif any(x in symbol.upper() for x in ['BTC', 'ETH']):
                pip_size = 1.0     # BTCUSD: 1 pip = $1.00
            elif any(x in symbol.upper() for x in ['XTI', 'WTI', 'OIL', 'BRENT']):
                pip_size = 0.01    # V36.0: Oil IC Markets — 1 pip = $0.01 (era 0.0001 → 100x eronat)
            else:
                pip_size = 0.0001
            sl_buffer = pip_size * 2  # 2 pips buffer sub swing Low (spread protection)
            body_lows_4h = df_4h[['open', 'close']].min(axis=1)  # V36.1: pre-calculat — fix UnboundLocalError
            # Calculăm ATR 14 pentru a filtra micro-fractali
            atr_14 = (df_4h['high'] - df_4h['low']).rolling(14).mean().iloc[h4_choch_idx] if h4_choch_idx >= 14 else (df_4h['high'] - df_4h['low']).mean()
            stop_loss = None
            chosen_sl_obj = None
            if lows_before_choch:
                # Sortăm descrescător după index = cel mai recent primul
                lows_sorted = sorted(lows_before_choch, key=lambda s: s.index, reverse=True)
                for sl_candidate in lows_sorted:
                    wick_low = df_4h['low'].iloc[sl_candidate.index]
                    # Filtru: swing-ul trebuie să fie semnificativ (wick sub entry cu min 0.5x ATR)
                    if (entry - wick_low) >= atr_14 * 0.5:
                        stop_loss = wick_low - sl_buffer
                        chosen_sl_obj = sl_candidate
                        break
                if stop_loss is None:
                    # Toți sunt micro-fractali → luăm cel mai recent oricum
                    chosen_sl_obj = lows_sorted[0]
                    stop_loss = df_4h['low'].iloc[chosen_sl_obj.index] - sl_buffer
                sl_distance_pips = abs(entry - stop_loss) / pip_size
                print(f"   🛡️ [V14.1 SL STRUCTURAL LONG] Ultimul swing Low 4H pre-CHoCH valid: "
                      f"idx={chosen_sl_obj.index} wick_low={df_4h['low'].iloc[chosen_sl_obj.index]:.5f} "
                      f"→ SL={stop_loss:.5f} (distanță={sl_distance_pips:.1f} pips, ATR={atr_14/pip_size:.1f}p)")
                # V42.6: cap unic din pip_utils (XTI=50p, forex=100p, JPY=150p, etc.)
                from pip_utils import get_max_sl_pips
                _max_sl_pips = get_max_sl_pips(symbol)
                if sl_distance_pips > _max_sl_pips:
                    print(f"   ⚠️ [V42.6 SL INFO] {symbol} LONG: SL {sl_distance_pips:.1f}p > {_max_sl_pips}p — "
                          f"Executor/Radar vor folosi sniper SL ≤ {_max_sl_pips:.0f}p la EXECUTE_NOW")

            # Validare: SL trebuie să fie sub entry pentru LONG (V36.1: body_lows_4h pre-calculat sus)
            if stop_loss is not None and stop_loss >= entry:
                stop_loss = body_lows_4h.min() - sl_buffer
                print(f"   🛡️ [V13.2 SL FALLBACK2] Body min total 4H: {stop_loss:.5f}")

            # ── V12.1 TP STRUCTURAL D1: primul swing High D1 DEASUPRA prețului curent ────
            # TP = cel mai apropiat swing High pe D1 care este deasupra entry-ului.
            # Acesta este nivelul de structură real, NU extrema din 10 luni.
            # V24.8 ATR FILTER: Eliminăm micro-pivoții Daily — TP trebuie să fie la minim 1.5x ATR
            # distanță de entry. Fără filtru, botul alegea swing-uri de 2-5 pips → RR distrus.
            current_price = df_4h['close'].iloc[-1]
            swing_highs_d1_list = self.detect_swing_highs(df_daily)
            # Calculăm ATR 14 pe Daily pentru filtrul de distanță minimă TP
            atr_daily = self.calculate_atr(df_daily, period=14)
            atr_daily_val = float(atr_daily) if atr_daily else 0.0  # V36.2: calculate_atr() → float direct, nu Series
            min_tp_distance = atr_daily_val * 1.5  # Minim 1.5x ATR Daily față de entry
            # Filtrăm swing-urile D1 DEASUPRA prețului curent ȘI la distanță ATR suficientă
            highs_above_price = [
                sh for sh in swing_highs_d1_list
                if sh.price > current_price and (sh.price - entry) >= min_tp_distance
            ]
            if not highs_above_price:
                # Fallback: dacă filtrul ATR elimină totul, acceptăm swing-uri deasupra prețului (fără filtru distanță)
                highs_above_price = [sh for sh in swing_highs_d1_list if sh.price > current_price]
                print(f"   ⚠️ [V24.8 TP ATR FALLBACK] {symbol}: Niciun swing D1 la ≥{min_tp_distance/( 0.01 if 'JPY' in symbol else 0.0001):.0f}p de entry — folosim cel mai apropiat swing D1")
            if highs_above_price:
                # Cel mai apropiat (cel mai jos) swing High deasupra prețului
                nearest_high = min(highs_above_price, key=lambda sh: sh.price)
                take_profit = df_daily['high'].iloc[nearest_high.index]
                print(f"   🎯 [V12.1 TP] Nearest D1 swing High: idx={nearest_high.index} price={take_profit:.5f} (ATR_filter={min_tp_distance/( 0.01 if 'JPY' in symbol else 0.0001):.0f}p)")
            else:
                # Fallback: ultimul swing High pe D1
                if swing_highs_d1_list:
                    take_profit = df_daily['high'].iloc[swing_highs_d1_list[-1].index]
                else:
                    body_highs_d1 = df_daily[['open', 'close']].max(axis=1)
                    take_profit = body_highs_d1.iloc[:-1].max()
                print(f"   🎯 [V12.1 TP FALLBACK] Ultimul swing High D1: {take_profit:.5f}")

            # Validare: TP trebuie să fie deasupra entry pentru LONG
            if take_profit <= entry:
                body_highs_d1 = df_daily[['open', 'close']].max(axis=1)
                take_profit = body_highs_d1.iloc[:-1].max()
                print(f"   🎯 [V12.1 TP FALLBACK2] Max body D1: {take_profit:.5f}")
                # ✅ V14.0 ATH REJECT: dacă toate fallback-urile eșuează (ex: preț la ATH)
                # nu există target structural deasupra → trade ANULAT, nu raportat inversat
                if take_profit <= entry:
                    print(f"   ⛔ [V14.0 ATH REJECT] {symbol}: Niciun swing High D1 deasupra entry {entry:.5f} "
                          f"— preț la ATH, TP imposibil structural. Trade ANULAT.")
                    return None, None, None

        else:
            # ══════════════════════════════════════════════
            # SHORT TRADE
            # ══════════════════════════════════════════════

            # ── ENTRY: Marginea FVG 4H în zona 70-80% Fibonacci ──────────
            if h4_choch is not None and hasattr(h4_choch, 'swing_high') and h4_choch.swing_high is not None:
                impulse_high = h4_choch.swing_high
                impulse_low = h4_choch.swing_low if hasattr(h4_choch, 'swing_low') and h4_choch.swing_low is not None else fvg.bottom
                impulse_range = impulse_high - impulse_low
                fib_70 = impulse_low + (impulse_range * 0.70)   # Pullback 70% SHORT
                fib_80 = impulse_low + (impulse_range * 0.80)   # Pullback 80% SHORT
                fib_75 = impulse_low + (impulse_range * 0.75)   # Mijlocul Golden Zone

                fvg_in_golden_zone = (fvg.top >= fib_70 and fvg.bottom <= fib_80)
                if fvg_in_golden_zone:
                    # Entry = marginea SUPERIOARĂ a FVG (primul punct de intrare în zonă)
                    entry = fvg.top
                else:
                    entry = fib_75
            else:
                entry = fvg.top

            # ── V14.1 SL STRUCTURAL 4H: ultimul swing High VALID pre-CHoCH (Fix #9) ────────────────────
            # REGULA SMC CORECTĂ: SL = ultimul punct structural creat ÎNAINTE de impulsul CHoCH.
            # Nu maximul absolut din toată istoria (bug V13.2 = 385 pips pe GBPNZD).
            # Filtru ATR: eliminăm micro-fractali (swing-uri sub 0.5x ATR = zgomot, nu structură).
            h4_choch_idx = h4_choch.index if h4_choch is not None and hasattr(h4_choch, 'index') else max(0, len(df_4h) - 40)
            swing_highs_4h_list = self.detect_swing_highs(df_4h)
            highs_before_choch = [sh for sh in swing_highs_4h_list if sh.index <= h4_choch_idx]
            # V36.0 FIX B4: pip_size corect per instrument (XTI/OIL era 0.0001 → SL 100x eronat)
            if 'JPY' in symbol:
                pip_size = 0.01
            elif any(x in symbol.upper() for x in ['XAU', 'XAG', 'GOLD']):
                pip_size = 0.10    # XAUUSD IC Markets: 1 pip = $0.10
            elif any(x in symbol.upper() for x in ['BTC', 'ETH']):
                pip_size = 1.0     # BTCUSD: 1 pip = $1.00
            elif any(x in symbol.upper() for x in ['XTI', 'WTI', 'OIL', 'BRENT']):
                pip_size = 0.01    # V36.0: Oil IC Markets — 1 pip = $0.01 (era 0.0001 → 100x eronat)
            else:
                pip_size = 0.0001
            sl_buffer = pip_size * 2  # 2 pips buffer deasupra swing High (spread protection)
            body_highs_4h = df_4h[['open', 'close']].max(axis=1)  # V36.1: pre-calculat — fix UnboundLocalError
            # Calculăm ATR 14 pentru a filtra micro-fractali
            atr_14 = (df_4h['high'] - df_4h['low']).rolling(14).mean().iloc[h4_choch_idx] if h4_choch_idx >= 14 else (df_4h['high'] - df_4h['low']).mean()
            stop_loss = None
            chosen_sh_obj = None
            if highs_before_choch:
                # Sortăm descrescător după index = cel mai recent primul
                highs_sorted = sorted(highs_before_choch, key=lambda s: s.index, reverse=True)
                for sh_candidate in highs_sorted:
                    wick_high = df_4h['high'].iloc[sh_candidate.index]
                    # Filtru: swing-ul trebuie să fie semnificativ (wick deasupra entry cu min 0.5x ATR)
                    if (wick_high - entry) >= atr_14 * 0.5:
                        stop_loss = wick_high + sl_buffer
                        chosen_sh_obj = sh_candidate
                        break
                if stop_loss is None:
                    # Toți sunt micro-fractali → luăm cel mai recent oricum
                    chosen_sh_obj = highs_sorted[0]
                    stop_loss = df_4h['high'].iloc[chosen_sh_obj.index] + sl_buffer
                sl_distance_pips = abs(stop_loss - entry) / pip_size
                print(f"   🛡️ [V14.1 SL STRUCTURAL SHORT] Ultimul swing High 4H pre-CHoCH valid: "
                      f"idx={chosen_sh_obj.index} wick_high={df_4h['high'].iloc[chosen_sh_obj.index]:.5f} "
                      f"→ SL={stop_loss:.5f} (distanță={sl_distance_pips:.1f} pips, ATR={atr_14/pip_size:.1f}p)")
                # V26.0: SL cap per instrument (V19.7: 50→100 non-JPY; XAU/BTC: cap separat)
                from pip_utils import get_max_sl_pips
                _max_sl_pips = get_max_sl_pips(symbol)
                if sl_distance_pips > _max_sl_pips:
                    print(f"   ⚠️ [V42.6 SL INFO] {symbol} SHORT: SL {sl_distance_pips:.1f}p > {_max_sl_pips}p — "
                          f"Executor/Radar vor folosi sniper SL ≤ {_max_sl_pips:.0f}p la EXECUTE_NOW")

            # Validare: SL trebuie să fie deasupra entry pentru SHORT (V36.1: body_highs_4h pre-calculat sus)
            if stop_loss is not None and stop_loss <= entry:
                stop_loss = body_highs_4h.max() + sl_buffer
                print(f"   🛡️ [V13.2 SL FALLBACK2] Body max total 4H: {stop_loss:.5f}")

            # ── V12.1 TP STRUCTURAL D1: primul swing Low D1 SUB prețul curent ────
            # TP = cel mai apropiat swing Low pe D1 care este sub entry.
            # Acesta este suportul structural real, NU extrema din 10 luni.
            # V24.8 ATR FILTER: Eliminăm micro-pivoții Daily — TP trebuie să fie la minim 1.5x ATR
            # distanță de entry. Fără filtru, botul alegea swing-uri de 2-5 pips → RR distrus.
            current_price = df_4h['close'].iloc[-1]
            swing_lows_d1_list = self.detect_swing_lows(df_daily)
            # Calculăm ATR 14 pe Daily pentru filtrul de distanță minimă TP
            atr_daily = self.calculate_atr(df_daily, period=14)
            atr_daily_val = float(atr_daily) if atr_daily else 0.0  # V36.2: calculate_atr() → float direct, nu Series
            min_tp_distance = atr_daily_val * 1.5  # Minim 1.5x ATR Daily față de entry
            # Filtrăm swing-urile D1 SUB prețul curent ȘI la distanță ATR suficientă
            lows_below_price = [
                sl for sl in swing_lows_d1_list
                if sl.price < current_price and (entry - sl.price) >= min_tp_distance
            ]
            if not lows_below_price:
                # Fallback: dacă filtrul ATR elimină totul, acceptăm swing-uri sub preț (fără filtru distanță)
                lows_below_price = [sl for sl in swing_lows_d1_list if sl.price < current_price]
                print(f"   ⚠️ [V24.8 TP ATR FALLBACK] {symbol}: Niciun swing D1 la ≥{min_tp_distance/( 0.01 if 'JPY' in symbol else 0.0001):.0f}p de entry — folosim cel mai apropiat swing D1")
            if lows_below_price:
                # Cel mai apropiat (cel mai sus) swing Low sub preț = primul suport
                nearest_low = max(lows_below_price, key=lambda sl: sl.price)
                take_profit = df_daily['low'].iloc[nearest_low.index]
                print(f"   🎯 [V12.1 TP] Nearest D1 swing Low: idx={nearest_low.index} price={take_profit:.5f} (ATR_filter={min_tp_distance/( 0.01 if 'JPY' in symbol else 0.0001):.0f}p)")
            else:
                # Fallback: ultimul swing Low pe D1
                if swing_lows_d1_list:
                    take_profit = df_daily['low'].iloc[swing_lows_d1_list[-1].index]
                else:
                    body_lows_d1 = df_daily[['open', 'close']].min(axis=1)
                    take_profit = body_lows_d1.iloc[:-1].min()
                print(f"   🎯 [V12.1 TP FALLBACK] Ultimul swing Low D1: {take_profit:.5f}")

            # Validare: TP trebuie să fie sub entry pentru SHORT
            if take_profit >= entry:
                body_lows_d1 = df_daily[['open', 'close']].min(axis=1)
                take_profit = body_lows_d1.iloc[:-1].min()
                print(f"   🎯 [V12.1 TP FALLBACK2] Min body D1: {take_profit:.5f}")
                # ✅ V14.0 ATL REJECT: dacă toate fallback-urile eșuează (ex: preț la ATL)
                # nu există target structural sub preț → trade ANULAT
                if take_profit >= entry:
                    print(f"   ⛔ [V14.0 ATL REJECT] {symbol}: Niciun swing Low D1 sub entry {entry:.5f} "
                          f"— preț la ATL, TP imposibil structural. Trade ANULAT.")
                    return None, None, None

        # ══════════════════════════════════════════════════════════════════
        # V14.0 DIRECTION GUARD — abs() masca direcția greșită, eliminat
        # reward TREBUIE să fie pozitiv direcțional: LONG = TP > Entry, SHORT = TP < Entry
        # ══════════════════════════════════════════════════════════════════
        risk = abs(entry - stop_loss)
        if fvg.direction == 'bullish':
            reward = take_profit - entry        # LONG: TP deasupra entry → reward pozitiv
        else:
            reward = entry - take_profit        # SHORT: TP sub entry → reward pozitiv

        # ✅ V14.0 DIRECTION GUARD: reward ≤ 0 = TP în direcție greșită → respins
        if reward <= 0:
            print(f"⛔ [V14.0 DIRECTION GUARD] {symbol} {'LONG' if fvg.direction == 'bullish' else 'SHORT'}: "
                  f"TP={take_profit:.5f} în direcție GREȘITĂ față de Entry={entry:.5f}. Trade ANULAT.")
            return None, None, None

        if risk <= 0:
            print(f"⛔ [V10.2 REJECT: SL=ENTRY, risc zero] {symbol} — SL invalid structural")
            return None, None, None

        rr = reward / risk
        # V30.0: daily_bias_active (WAITING_D1_PULLBACK) → threshold relaxat la 2.0
        # Motivul: SL structural 4H pe un setup incomplet (fără pullback final) poate fi larg,
        # dar structura D1 este validă. RR real se recalculează la EXECUTE_NOW.
        _rr_threshold = 2.0 if daily_bias_active else 4.0
        if rr < _rr_threshold:
            print(f"⛔ [V14.1 REJECT: RR=1:{rr:.2f} < 1:{_rr_threshold}{'(daily_bias)' if daily_bias_active else ''}] {symbol} — "
                  f"SL 4H structural + TP Daily nu generează RR suficient. Trade ANULAT.")
            return None, None, None

        print(f"✅ [V14.1 SL STRUCTURAL] {symbol} {'LONG' if fvg.direction == 'bullish' else 'SHORT'}: "
              f"Entry={entry:.5f} | SL={stop_loss:.5f} | TP={take_profit:.5f} | RR=1:{rr:.2f}")
        pip_size_final = self._get_pip_size(symbol)  # V37.17: pip corect XAU/BTC/JPY/FX
        print(f"   📐 SL dist={abs(entry-stop_loss)/pip_size_final:.1f} pips | TP dist={abs(take_profit-entry)/pip_size_final:.1f} pips")

        return entry, stop_loss, take_profit
