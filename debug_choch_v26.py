#!/usr/bin/env python3
"""
🔬 DEBUG CHoCH DETECTION V26.0
════════════════════════════════════════════════════════════════════
MISIUNE: Răspunde la 3 întrebări pentru EURUSD, GBPUSD, GBPNZD

1. Unde e ultimul Swing High / Low dominant pe Daily?
2. La ce bară a fost TENTATĂ spargerea? (CHoCH sau BOS attempt)
3. Cât de aproape era body close de confirmare? (pips diff)

RUN PE VPS:
  python debug_choch_v26.py

RUN SIMBOL SPECIFIC:
  python debug_choch_v26.py --symbol EURUSD

ENCODARE OUTPUT CORECT (Windows):
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; chcp 65001
  python debug_choch_v26.py 2>&1
════════════════════════════════════════════════════════════════════
by ФорексГод — Glitch in Matrix V26.0 Debug
"""

import sys
import argparse
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from typing import List, Tuple, Optional

from smc_detector import SMCDetector, SwingPoint
from ctrader_cbot_client import CTraderCBotClient

# ─── ANSI colors (funcționează pe Win10+ cu UTF8) ───────────────
RED    = "\033[91m"
GRN    = "\033[92m"
YLW    = "\033[93m"
BLU    = "\033[94m"
MAG    = "\033[95m"
CYN    = "\033[96m"
WHT    = "\033[97m"
RST    = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

def pip_size(symbol: str) -> float:
    if 'JPY' in symbol:
        return 0.01
    elif any(x in symbol.upper() for x in ['XAU', 'XAG', 'GOLD']):
        return 0.10
    elif any(x in symbol.upper() for x in ['BTC', 'ETH']):
        return 1.0
    elif any(x in symbol.upper() for x in ['XTI', 'OIL', 'WTI']):
        return 0.01
    return 0.0001

def pips(diff: float, sym: str) -> float:
    return abs(diff) / pip_size(sym)

def header(text: str):
    print(f"\n{BOLD}{CYN}{'═'*70}{RST}")
    print(f"{BOLD}{CYN}  {text}{RST}")
    print(f"{BOLD}{CYN}{'═'*70}{RST}")

def subhead(text: str):
    print(f"\n{BOLD}{BLU}  ─── {text} ───{RST}")

def ok(text: str):
    print(f"  {GRN}✅ {text}{RST}")

def fail(text: str):
    print(f"  {RED}❌ {text}{RST}")

def warn(text: str):
    print(f"  {YLW}⚠️  {text}{RST}")

def info(text: str):
    print(f"  {WHT}   {text}{RST}")


def trace_body_close_rule(
    df: pd.DataFrame,
    swing_idx: int,
    swing_price: float,
    direction: str,   # 'break_up' sau 'break_down'
    symbol: str,
    label: str = ""
) -> dict:
    """
    Verifică dacă există un close de corp DINCOLO de swing_price
    după bara swing_idx. Returnează detalii complete.

    direction='break_up'   → căutăm close > swing_price (HH confirmation)
    direction='break_down' → căutăm close < swing_price (LL confirmation)
    """
    ps = pip_size(symbol)
    confirmed = False
    confirm_bar = None
    best_close = None
    best_diff_pips = None

    # Bara swing poate fi în ultimele bare — cerem cel puțin 1 bară după
    search_start = swing_idx + 1
    search_end   = min(swing_idx + 1, len(df) - 1)  # cel puțin bara imediat după
    # Extindem: căutăm pe tot ce e DUPĂ swing_idx
    search_end = len(df)

    closes_after = []
    for ci in range(search_start, search_end):
        c = float(df['close'].iloc[ci])
        closes_after.append(c)
        diff = (c - swing_price) if direction == 'break_up' else (swing_price - c)
        diff_pips = diff / ps

        if diff > 0:  # body close confirmat
            confirmed = True
            confirm_bar = ci
            best_close = c
            best_diff_pips = diff_pips
            break
        else:
            # Nu confirmat — cât de aproape era?
            if best_diff_pips is None or diff_pips > best_diff_pips:
                best_diff_pips = diff_pips  # negativ = cât i-a lipsit
                best_close = c

    bars_after = search_end - search_start

    return {
        'confirmed'       : confirmed,
        'confirm_bar'     : confirm_bar,
        'best_close'      : best_close,
        'best_diff_pips'  : best_diff_pips,   # pozitiv = confirmat cu X pips; negativ = i-a lipsit X pips
        'bars_searched'   : bars_after,
        'swing_price'     : swing_price,
        'swing_idx'       : swing_idx,
        'direction'       : direction,
        'label'           : label
    }


def manual_choch_bos_trace(
    df: pd.DataFrame,
    symbol: str,
    detector: SMCDetector
) -> dict:
    """
    Replică logica detect_choch_and_bos() PAS CU PAS cu output verbose.
    Raportează FIECARE tentativă de CHoCH/BOS și de ce a trecut sau picat.
    """
    ps = pip_size(symbol)
    swing_highs = detector.detect_swing_highs(df)
    swing_lows  = detector.detect_swing_lows(df)

    subhead(f"SWING POINTS detectate (ultimele 10 din TOATĂ seria)")
    info(f"Total Swing Highs: {len(swing_highs)}  |  Total Swing Lows: {len(swing_lows)}")

    # ─── Ultimele 10 swing highs + lows cronologic ─────────────
    all_swings = []
    for sh in swing_highs:
        all_swings.append(('high', sh))
    for sl in swing_lows:
        all_swings.append(('low', sl))
    all_swings.sort(key=lambda x: x[1].index)

    # Afișăm ultimele 15 swing points cu timestamp
    recent_swings = all_swings[-15:]
    print()
    print(f"  {'Tip':<6} {'Idx':>5}  {'Preț':>12}  {'Data':<22}  {'Bare în urmă':>12}")
    print(f"  {'─'*6} {'─'*5}  {'─'*12}  {'─'*22}  {'─'*12}")
    for sw_type, sw in recent_swings:
        bars_ago = len(df) - 1 - sw.index
        try:
            ts = str(df.index[sw.index])[:22]
        except:
            ts = f"idx={sw.index}"
        color = GRN if sw_type == 'high' else RED
        tag = "▲ HIGH" if sw_type == 'high' else "▼ LOW "
        print(f"  {color}{tag}{RST} {sw.index:>5}  {sw.price:>12.5f}  {ts:<22}  {bars_ago:>10} bare")

    # ─── Replică logica principală ───────────────────────────────
    subhead("TRACE detect_choch_and_bos() — fiecare tentativă de break")

    chochs_found    = []
    bos_found       = []
    attempts        = []   # fiecare tentativă cu motiv fail/pass
    prev_trend      = None

    # Bootstrap prev_trend
    init_highs = swing_highs[:2]
    init_lows  = swing_lows[:2]
    if len(init_highs) >= 2 and len(init_lows) >= 2:
        h_asc = init_highs[1].price > init_highs[0].price
        l_asc = init_lows[1].price  > init_lows[0].price
        if h_asc and l_asc:
            prev_trend = 'bullish'
        elif not h_asc and not l_asc:
            prev_trend = 'bearish'

    info(f"Bootstrap prev_trend: {(prev_trend or 'None (nedeterminat)').upper()}")

    for i in range(1, len(all_swings)):
        sw_type, swing = all_swings[i]

        if sw_type == 'high':
            prev_high = next(
                (s for t, s in reversed(all_swings[:i]) if t == 'high'),
                None
            )
            if prev_high is None:
                continue

            if swing.price > prev_high.price:
                # Tentativă HH
                _prev_wick_h = prev_high.price
                bcr = trace_body_close_rule(
                    df, prev_high.index, _prev_wick_h,
                    'break_up', symbol,
                    label=f"HH attempt: swing@{swing.index} broke prev_high@{prev_high.index}"
                )
                attempts.append({
                    'type': 'HH',
                    'swing_idx': swing.index,
                    'prev_idx': prev_high.index,
                    'swing_price': swing.price,
                    'prev_price': prev_high.price,
                    'prev_trend': prev_trend,
                    'bcr': bcr
                })

                if bcr['confirmed']:
                    if prev_trend == 'bearish':
                        # V24.4 VOLATILE FIX check
                        recent_highs = [s for s in swing_highs if s.index <= swing.index][-5:]
                        recent_lows  = [s for s in swing_lows  if s.index <= swing.index][-5:]
                        lh_any = any(recent_highs[j].price < recent_highs[j-1].price for j in range(1, len(recent_highs)))
                        ll_any = any(recent_lows[j].price  < recent_lows[j-1].price  for j in range(1, len(recent_lows)))
                        if lh_any or ll_any:
                            chochs_found.append(('bullish', swing.index, swing.price, prev_trend))
                            prev_trend = 'bullish'
                            attempts[-1]['result'] = f"CHoCH BULLISH (lh_any={lh_any} ll_any={ll_any})"
                        else:
                            attempts[-1]['result'] = f"SKIP V24.4: nicio LH/LL in ultimele 5 swings (lh_any={lh_any} ll_any={ll_any})"
                    elif prev_trend == 'bullish':
                        bos_found.append(('bullish', swing.index, swing.price))
                        attempts[-1]['result'] = "BOS BULLISH"
                    elif prev_trend is None:
                        chochs_found.append(('bullish', swing.index, swing.price, None))
                        prev_trend = 'bullish'
                        attempts[-1]['result'] = "CHoCH BULLISH (init)"
                else:
                    attempts[-1]['result'] = "FAIL: Body Close Rule"

        elif sw_type == 'low':
            prev_low = next(
                (s for t, s in reversed(all_swings[:i]) if t == 'low'),
                None
            )
            if prev_low is None:
                continue

            if swing.price < prev_low.price:
                # Tentativă LL
                _prev_wick_l = prev_low.price
                bcr = trace_body_close_rule(
                    df, prev_low.index, _prev_wick_l,
                    'break_down', symbol,
                    label=f"LL attempt: swing@{swing.index} broke prev_low@{prev_low.index}"
                )
                attempts.append({
                    'type': 'LL',
                    'swing_idx': swing.index,
                    'prev_idx': prev_low.index,
                    'swing_price': swing.price,
                    'prev_price': prev_low.price,
                    'prev_trend': prev_trend,
                    'bcr': bcr
                })

                if bcr['confirmed']:
                    if prev_trend == 'bullish':
                        recent_highs = [s for s in swing_highs if s.index <= swing.index][-5:]
                        recent_lows  = [s for s in swing_lows  if s.index <= swing.index][-5:]
                        hh_any = any(recent_highs[j].price > recent_highs[j-1].price for j in range(1, len(recent_highs)))
                        hl_any = any(recent_lows[j].price  > recent_lows[j-1].price  for j in range(1, len(recent_lows)))
                        if hh_any or hl_any:
                            chochs_found.append(('bearish', swing.index, swing.price, prev_trend))
                            prev_trend = 'bearish'
                            attempts[-1]['result'] = f"CHoCH BEARISH (hh_any={hh_any} hl_any={hl_any})"
                        else:
                            attempts[-1]['result'] = f"SKIP V24.4: nicio HH/HL in ultimele 5 swings (hh_any={hh_any} hl_any={hl_any})"
                    elif prev_trend == 'bearish':
                        bos_found.append(('bearish', swing.index, swing.price))
                        attempts[-1]['result'] = "BOS BEARISH"
                    elif prev_trend is None:
                        chochs_found.append(('bearish', swing.index, swing.price, None))
                        prev_trend = 'bearish'
                        attempts[-1]['result'] = "CHoCH BEARISH (init)"
                else:
                    attempts[-1]['result'] = "FAIL: Body Close Rule"

    # ─── Afișează ultimele 20 tentative ────────────────────────
    show_attempts = attempts[-20:]
    print()
    print(f"  {BOLD}{'Tip':<4} {'Cur@':>5} {'Prev@':>5}  {'Prev Price':>12}  {'BCR?':<6}  {'±pips':>8}  {'Rezultat'}{RST}")
    print(f"  {'─'*4} {'─'*5} {'─'*5}  {'─'*12}  {'─'*6}  {'─'*8}  {'─'*30}")

    fails_bcr = 0
    fails_v24 = 0
    passes    = 0

    for att in show_attempts:
        bcr       = att['bcr']
        typ       = att['type']
        result    = att.get('result', '?')
        confirmed = bcr['confirmed']
        diff_pips = bcr['best_diff_pips'] if bcr['best_diff_pips'] is not None else 0.0

        if 'CHoCH' in result or 'BOS' in result:
            color  = GRN
            marker = "✅"
            passes += 1
        elif 'Body Close' in result:
            color  = RED
            marker = "❌"
            fails_bcr += 1
        elif 'V24.4' in result or 'SKIP' in result:
            color  = YLW
            marker = "⚠️"
            fails_v24 += 1
        else:
            color  = WHT
            marker = "  "

        sign   = "+" if diff_pips >= 0 else ""
        print(
            f"  {color}{marker} {typ:<4}{RST} "
            f"{att['swing_idx']:>5} {att['prev_idx']:>5}  "
            f"{att['prev_price']:>12.5f}  "
            f"{'YES' if confirmed else 'NO':<6}  "
            f"{color}{sign}{diff_pips:>7.1f}p{RST}  "
            f"{color}{result[:50]}{RST}"
        )

    # ─── Summary ────────────────────────────────────────────────
    subhead("SUMMARY TENTATIVE (toate, nu doar ultimele 20)")
    total = len(attempts)
    all_fails_bcr = sum(1 for a in attempts if 'Body Close' in a.get('result', ''))
    all_fails_v24 = sum(1 for a in attempts if 'V24.4' in a.get('result', '') or 'SKIP' in a.get('result', ''))
    all_passes    = sum(1 for a in attempts if 'CHoCH' in a.get('result', '') or 'BOS' in a.get('result', ''))

    info(f"Total tentative HH/LL:     {total}")
    info(f"PASS (CHoCH/BOS detectat): {GRN}{all_passes}{RST}")
    info(f"FAIL Body Close Rule:      {RED}{all_fails_bcr}{RST}  ← principalul suspect")
    info(f"SKIP V24.4 (no LH/LL/HH/HL pattern): {YLW}{all_fails_v24}{RST}")

    # ─── Ultimul CHoCH/BOS detectat ─────────────────────────────
    subhead("REZULTAT FINAL — CHoCH/BOS valide detectate")
    if chochs_found:
        for direction, idx, price, ptend in chochs_found[-3:]:
            bars_ago = len(df) - 1 - idx
            try:
                ts = str(df.index[idx])[:22]
            except:
                ts = f"idx={idx}"
            ok(f"CHoCH {direction.upper()} @ {price:.5f}  bar#{idx}  ({bars_ago} bare în urmă, {ts})")
    else:
        fail("Niciun CHoCH detectat pe toată seria!")

    if bos_found:
        for direction, idx, price in bos_found[-3:]:
            bars_ago = len(df) - 1 - idx
            try:
                ts = str(df.index[idx])[:22]
            except:
                ts = f"idx={idx}"
            ok(f"BOS {direction.upper()} @ {price:.5f}  bar#{idx}  ({bars_ago} bare în urmă, {ts})")
    else:
        warn("Niciun BOS detectat.")

    # ─── Analiza celor mai relevante FAIL-uri BCR ────────────────
    subhead("TOP FAIL-URI BODY CLOSE RULE (cele mai aproape de confirmare)")
    bcr_fails = [
        a for a in attempts
        if 'Body Close' in a.get('result', '')
        and a['bcr']['best_diff_pips'] is not None
    ]
    # Sortăm: cel mai aproape de confirmare = best_diff_pips cel mai puțin negativ
    bcr_fails.sort(key=lambda a: a['bcr']['best_diff_pips'], reverse=True)

    for a in bcr_fails[:8]:
        bcr = a['bcr']
        diff = bcr['best_diff_pips']
        bars_searched = bcr['bars_searched']
        try:
            ts_swing = str(df.index[a['swing_idx']])[:16]
            ts_prev  = str(df.index[a['prev_idx']])[:16]
        except:
            ts_swing = f"#{a['swing_idx']}"
            ts_prev  = f"#{a['prev_idx']}"
        sign = "+" if diff >= 0 else ""
        color = GRN if diff >= 0 else RED
        print(
            f"  {a['type']} @{ts_swing} broke prev_{a['type'][0].lower()}@{ts_prev} "
            f"(prev={a['prev_price']:.5f}) "
            f"→ best_close={bcr['best_close']:.5f} "
            f"{color}({sign}{diff:.1f}p){RST} "
            f"({bars_searched} bare căutate)"
        )

    # ─── Prețul curent vs ultimele swing-uri ─────────────────────
    current_price = float(df['close'].iloc[-1])
    subhead(f"PREȚUL CURENT vs STRUCTURA ({symbol})")
    info(f"Preț curent (close D1 last): {BOLD}{current_price:.5f}{RST}")
    if swing_highs:
        last_sh = swing_highs[-1]
        dist_sh = pips(current_price - last_sh.price, symbol)
        try:
            ts_sh = str(df.index[last_sh.index])[:22]
        except:
            ts_sh = f"idx={last_sh.index}"
        bars_ago_sh = len(df) - 1 - last_sh.index
        info(f"Ultimul Swing HIGH: {last_sh.price:.5f}  @ bar#{last_sh.index} ({bars_ago_sh} bare în urmă, {ts_sh})")
        color = RED if current_price < last_sh.price else GRN
        info(f"  Distanță: {color}{dist_sh:+.1f} pips față de Swing High{RST}")
    if swing_lows:
        last_sl = swing_lows[-1]
        dist_sl = pips(current_price - last_sl.price, symbol)
        try:
            ts_sl = str(df.index[last_sl.index])[:22]
        except:
            ts_sl = f"idx={last_sl.index}"
        bars_ago_sl = len(df) - 1 - last_sl.index
        info(f"Ultimul Swing LOW:  {last_sl.price:.5f}  @ bar#{last_sl.index} ({bars_ago_sl} bare în urmă, {ts_sl})")
        color = GRN if current_price > last_sl.price else RED
        info(f"  Distanță: {color}{dist_sl:+.1f} pips față de Swing Low{RST}")

    return {
        'chochs'     : chochs_found,
        'bos'        : bos_found,
        'attempts'   : attempts,
        'fails_bcr'  : all_fails_bcr,
        'fails_v24'  : all_fails_v24,
        'passes'     : all_passes,
        'swing_highs': swing_highs,
        'swing_lows' : swing_lows,
        'current'    : current_price,
    }


def run_debug(symbol: str, client: CTraderCBotClient, detector: SMCDetector):
    header(f"🔬 DEEP DEBUG — {symbol} — Daily Structure")

    # Fetch D1 data
    print(f"\n  {CYN}Fetching D1 data (100 bare)...{RST}")
    df_daily = client.get_historical_data(symbol, 'D1', 100)
    if df_daily is None or len(df_daily) < 20:
        fail(f"Nu s-au putut obține date D1 pentru {symbol}")
        return

    info(f"Date D1 primite: {len(df_daily)} bare")
    info(f"Perioadă: {str(df_daily.index[0])[:16]} → {str(df_daily.index[-1])[:16]}")

    # Rulăm detect_choch_and_bos() oficial
    subhead("OUTPUT OFICIAL detect_choch_and_bos() (fără debug intern)")
    official_chochs, official_bos = detector.detect_choch_and_bos(df_daily)
    info(f"CHoCH detectate oficial: {len(official_chochs)}")
    info(f"BOS detectate oficial:   {len(official_bos)}")
    if official_chochs:
        last = official_chochs[-1]
        bars_ago = len(df_daily) - 1 - last.index
        ok(f"Ultimul CHoCH oficial: {last.direction.upper()} @ {last.break_price:.5f}  ({bars_ago} bare în urmă)")
    if official_bos:
        last = official_bos[-1]
        bars_ago = len(df_daily) - 1 - last.index
        ok(f"Ultimul BOS oficial:   {last.direction.upper()} @ {last.break_price:.5f}  ({bars_ago} bare în urmă)")

    # Trace manual complet
    result = manual_choch_bos_trace(df_daily, symbol, detector)

    # Concluzie finală
    subhead(f"DIAGNOSTIC {symbol}")
    chochs = result['chochs']
    bos    = result['bos']

    if not chochs and not bos:
        fail(f"{symbol}: ZERO structuri — scanner zilnic NU găsește NIMIC")
        warn("CAUZE POSIBILE:")
        info(f"  A) Body Close Rule V22: {result['fails_bcr']} tentative respinse")
        info(f"  B) V24.4 VOLATILE FIX: {result['fails_v24']} tentative respinse (nicio LH/LL/HH/HL)")
        info(f"  C) FRACTAL_WINDOW=2 nu găsește swinguri geometrice cu 2 bare bilateral")
    elif chochs:
        last_c = chochs[-1]
        bars_ago = len(df_daily) - 1 - last_c[1]
        if bars_ago > 50:
            warn(f"{symbol}: CHoCH {last_c[0].upper()} detectat DAR are {bars_ago} bare (>50) — FVG posibil mituit")
        else:
            ok(f"{symbol}: CHoCH {last_c[0].upper()} @ {last_c[2]:.5f} ({bars_ago} bare) — structură validă")

    # Ratio fails pentru vizualizare
    total = result['attempts']
    if total:
        total_n = len(total)
        fail_pct = result['fails_bcr'] / total_n * 100
        v24_pct  = result['fails_v24'] / total_n * 100
        pass_pct = result['passes'] / total_n * 100
        info(f"Rate: ✅{pass_pct:.0f}% CHoCH/BOS | ❌{fail_pct:.0f}% BCR fail | ⚠️{v24_pct:.0f}% V24.4 skip")


def main():
    parser = argparse.ArgumentParser(description='Debug CHoCH detection V26.0')
    parser.add_argument('--symbol', type=str, default=None,
                        help='Symbol specific (default: EURUSD GBPUSD GBPNZD)')
    parser.add_argument('--port', type=int, default=8010,
                        help='Port cTrader MarketDataProvider (default: 8010)')
    args = parser.parse_args()

    # Conectare
    print(f"\n{BOLD}{MAG}╔══════════════════════════════════════════════════════════╗")
    print(f"║   🔬 CHoCH DETECTION DEBUGGER V26.0 — Glitch in Matrix  ║")
    print(f"╚══════════════════════════════════════════════════════════╝{RST}")
    print(f"\n  {CYN}Conectare la cTrader port {args.port}...{RST}")

    client = CTraderCBotClient(port=args.port)
    detector = SMCDetector(swing_lookback=5, atr_multiplier=1.5)

    # Verificare conexiune
    try:
        test = client.get_historical_data('EURUSD', 'D1', 5)
        if test is None or len(test) < 3:
            print(f"\n  {RED}EROARE: Port {args.port} nu răspunde sau cBot oprit!{RST}")
            print(f"  {YLW}Verifică: Test-NetConnection -ComputerName localhost -Port {args.port}{RST}")
            sys.exit(1)
        ok(f"Conexiune OK — port {args.port} activ")
    except Exception as e:
        print(f"\n  {RED}Eroare conexiune: {e}{RST}")
        sys.exit(1)

    # Simboluri de analizat
    if args.symbol:
        symbols = [args.symbol.upper()]
    else:
        symbols = ['EURUSD', 'GBPUSD', 'GBPNZD']

    for sym in symbols:
        run_debug(sym, client, detector)

    # ─── Summary final ────────────────────────────────────────
    print(f"\n{BOLD}{CYN}{'═'*70}{RST}")
    print(f"{BOLD}{CYN}  SUMMARY COMPLET{RST}")
    print(f"{BOLD}{CYN}{'═'*70}{RST}")
    print(f"\n  {'Simbol':<10}  {'CHoCH':<8}  {'BOS':<8}  {'BCR Fails':<10}  {'V24.4 Fails':<12}  {'Status'}")
    print(f"  {'─'*10}  {'─'*8}  {'─'*8}  {'─'*10}  {'─'*12}  {'─'*20}")

    # Re-run rapid pentru summary (fără output verbose)
    import io, contextlib
    for sym in symbols:
        df_d = client.get_historical_data(sym, 'D1', 100)
        if df_d is None:
            print(f"  {sym:<10}  {'N/A':<8}  {'N/A':<8}  {'N/A':<10}  {'N/A':<12}  {RED}NO DATA{RST}")
            continue
        chochs_off, bos_off = detector.detect_choch_and_bos(df_d)
        c_count = len(chochs_off)
        b_count = len(bos_off)
        if c_count + b_count == 0:
            status = f"{RED}ZERO structuri — BLOCAT{RST}"
        elif c_count + b_count >= 1:
            last = chochs_off[-1] if chochs_off else bos_off[-1]
            bars_ago = len(df_d) - 1 - last.index
            status = f"{GRN}OK (ultima {bars_ago} bare){RST}" if bars_ago <= 30 else f"{YLW}VECHI ({bars_ago} bare){RST}"
        print(f"  {sym:<10}  {c_count:<8}  {b_count:<8}  {'?':<10}  {'?':<12}  {status}")

    print(f"\n  {DIM}Rulează cu --symbol EURUSD pentru trace complet individual{RST}\n")


if __name__ == '__main__':
    main()
