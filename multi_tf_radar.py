#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import io
# Fix UTF-8 encoding for Windows PowerShell console
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

"""
🎯 MULTI-TIMEFRAME EXECUTION RADAR - V47 CHoCH/BOS ALERTS + POI PANDA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
V47: State machine POI | alerte live post-touch | gate 4H→1H | CHoCH/BOS cascadă
V46: EXECUTE = POI Daily + CHoCH 4H + retrace 60–80% (fără gate ≤3 bare)
V45.1: PAS 2 BOS-as-CHoCH eliminat | Trigger B doar post-CHoCH | poi_utils shared
V45: POI wick panda | _allow_bos_4h=False (fara V30.1 shortcut)
V36.5: P/D Guard blochează EXECUTE_NOW, NU scanarea H4/H1 — JSON mereu actualizat
V36.4: H4/H1 bar fallback (300→150→100) | XTIUSD prioritar vs WTIUSD | crash-safe cBot parse
V36.3: pip_size Crypto/Commodities | symbol broker map | skip logging verbose

Double Entry Logic: Scans both 1H and 4H for CHoCH confirmation.

CRITICAL UPGRADE:
- ✅ Scans 1H timeframe (relaxed ATR: 0.8x for precision moves)
- ✅ Scans 4H timeframe (standard ATR: 1.2x for higher confidence)
- ✅ Detects CHoCH on both timeframes
- ✅ Extracts FVG left by CHoCH (entry zone)
- ✅ Calculates distance to pullback zone
- ✅ Shows BOTH confirmations in console

STATUS SYSTEM:
- 👀 WAITING_1H_CHOCH: Scanning 1H for CHoCH alignment
- 👀 WAITING_4H_CHOCH: In Daily FVG, scanning 4H
- ⏳ WAITING_1H_PULLBACK: 1H CHoCH detected, waiting for pullback
- ⏳ WAITING_4H_PULLBACK: 4H CHoCH detected, waiting for pullback
- 🔥 EXECUTE_NOW_1H: Price in 1H FVG - SNIPER ENTRY!
- 🔥 EXECUTE_NOW_4H: Price in 4H FVG - HIGH CONFIDENCE ENTRY!

Usage:
    python3 multi_tf_radar.py
    python3 multi_tf_radar.py --symbol EURJPY
    python3 multi_tf_radar.py --watch --interval 30
"""

import json
import os as _os_global
import time
from pathlib import Path as _Path

# V22.2: Cale absolută — nu depinde de CWD la pornire
_RADAR_DIR = _Path(__file__).parent.resolve()
_MONITORING_FILE = str(_RADAR_DIR / 'monitoring_setups.json')
_MONITORING_TMP  = str(_RADAR_DIR / 'monitoring_setups.json.tmp')
import argparse
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from pip_utils import get_pip_size, get_max_sl_pips
from poi_utils import (
    find_first_poi_touch_time as _find_first_poi_touch_time,
    poi_box_intersects_wick as _poi_box_intersects_wick,
    poi_bounds_from_stored as _poi_bounds_from_stored,
    price_in_poi_box as _price_in_poi_box,
    resolve_poi_touch_anchor as _resolve_poi_touch_anchor,
)
from radar_gates import (
    parse_radar_dt as _parse_radar_dt,
    resolve_mitigation_touch_anchor as _resolve_mitigation_touch_anchor,
    v47_break_post_poi_touch as _v47_break_post_poi_touch,
)

try:
    from ctrader_cbot_client import CTraderCBotClient
    from smc_detector import SMCDetector
    import pandas as pd
    DEPS_AVAILABLE = True
except ImportError:
    DEPS_AVAILABLE = False
    print("WARNING: Dependencies not available")
    sys.exit(1)

import platform
import re

# V37.1: Output ASCII pe Windows VPS — PowerShell citeste log UTF-8 ca mojibake
_RADAR_ASCII = platform.system() == 'Windows' or _os_global.getenv('RADAR_ASCII', '').lower() in ('1', 'true', 'yes')
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE,
)
_ASCII_MAP = str.maketrans({
    'ă': 'a', 'â': 'a', 'î': 'i', 'ș': 's', 'ț': 't',
    'Ă': 'A', 'Â': 'A', 'Î': 'I', 'Ș': 'S', 'Ț': 'T',
    'ş': 's', 'ţ': 't', 'Ş': 'S', 'Ţ': 'T',
    '—': '--', '–': '-', '━': '-', '─': '-',
})


def _ascii_sanitize(text: str) -> str:
    """V37.1.1: ASCII curat pentru log PowerShell Windows."""
    if not _RADAR_ASCII:
        return str(text)
    t = _EMOJI_RE.sub("", str(text))
    t = t.translate(_ASCII_MAP)
    t = t.replace("⏳", "[WAIT]").replace("✅", "[OK]").replace("❌", "[X]")
    t = t.replace("\u2705", "[OK]").replace("\u23f3", "[WAIT]").replace("\u274c", "[X]")
    return t.encode("ascii", errors="ignore").decode("ascii")


def _radar_log_filter(record) -> bool:
    record["message"] = _ascii_sanitize(record["message"])
    return True


def _radar_out(msg: str) -> None:
    """Print radar line — ASCII-safe on Windows log files."""
    print(_ascii_sanitize(msg))
    sys.stdout.flush()


def _plain_status(status: 'PullbackStatus') -> str:
    """Status lizibil fara emoji (ex: WAITING_4H_PULLBACK)."""
    return status.name if hasattr(status, 'name') else str(status)


def _fmt_price(val: Optional[float], digits: int = 5) -> str:
    if val is None or val == 0:
        return "N/A"
    return f"{val:.{digits}f}"


# V46: Premium/Discount entry band on CHoCH impulse (Daily POI pullback model)
_RETRACE_ENTRY_MIN = 0.60
_RETRACE_ENTRY_MAX = 0.80

# V47: max bars for Telegram structural alerts (NOT an EXECUTE gate — V46 unchanged)
# Constants imported from radar_gates

# V50: retrace sanity — extreme values = stale structural anchor
_RETRACE_ALERT_MAX = 2.0
_RETRACE_ALERT_MIN = -0.05


def _choch_impulse_retrace_pct(
    break_price: float,
    swing_broken_price: float,
    current_price: float,
    direction: str,
) -> tuple[float, float]:
    """Return (retrace_pct, impulse_size). Bearish: retrace up from break."""
    impulse = abs(break_price - swing_broken_price)
    if impulse <= 0:
        return 0.0, 0.0
    if direction == 'bullish':
        retrace = (break_price - current_price) / impulse
    else:
        retrace = (current_price - break_price) / impulse
    return retrace, impulse


def _choch_premium_discount_zone(
    break_price: float,
    impulse: float,
    direction: str,
) -> tuple[float, float, float]:
    """V46: 60–80% retrace zone (bottom, top, midpoint)."""
    if direction == 'bullish':
        z_top = break_price - impulse * _RETRACE_ENTRY_MIN
        z_bottom = break_price - impulse * _RETRACE_ENTRY_MAX
    else:
        z_bottom = break_price + impulse * _RETRACE_ENTRY_MIN
        z_top = break_price + impulse * _RETRACE_ENTRY_MAX
    lo, hi = min(z_bottom, z_top), max(z_bottom, z_top)
    return lo, hi, (lo + hi) / 2.0


def _v46_entry_status_and_note(
    timeframe_key: str,
    symbol: str,
    required_direction: str,
    in_poi_entry: bool,
    retrace_pct: float,
    choch_bars_ago: int,
) -> tuple['PullbackStatus', str]:
    """V46: EXECUTE on POI + 60–80% retrace — no ≤3 bar gate."""
    is_h1 = timeframe_key.upper() in ('H1', '1H')
    exec_st = PullbackStatus.EXECUTE_NOW_1H if is_h1 else PullbackStatus.EXECUTE_NOW_4H
    wait_st = PullbackStatus.WAITING_1H_PULLBACK if is_h1 else PullbackStatus.WAITING_4H_PULLBACK
    if in_poi_entry:
        print(
            f"  [V46 POI-PD ENTRY {timeframe_key}] {symbol} {required_direction.upper()} "
            f"-> EXECUTE_NOW retrace={retrace_pct * 100:.1f}% "
            f"CHoCH=-{choch_bars_ago}b (fara gate 3 bare)"
        )
        sys.stdout.flush()
        return exec_st, (
            f"[V46] POI + Premium/Discount {retrace_pct * 100:.1f}% | CHoCH ancora -{choch_bars_ago}b"
        )
    if not in_poi_entry and _RETRACE_ENTRY_MIN <= retrace_pct <= _RETRACE_ENTRY_MAX:
        note = (
            f"⏳ retrace {retrace_pct * 100:.1f}% in 60–80% dar POI Daily inactiv"
        )
    elif retrace_pct > _RETRACE_ENTRY_MAX:
        note = (
            f"⏳ retrace {retrace_pct * 100:.1f}% > {_RETRACE_ENTRY_MAX * 100:.0f}% — "
            f"asteptam re-intrare in Premium/Discount 60–80%"
        )
    elif retrace_pct < _RETRACE_ENTRY_MIN:
        note = (
            f"⏳ retrace {retrace_pct * 100:.1f}% < {_RETRACE_ENTRY_MIN * 100:.0f}% — "
            f"asteptam Premium/Discount 60–80%"
        )
    else:
        note = f"⏳ retrace {retrace_pct * 100:.1f}% — asteptam POI + 60–80%"
    return wait_st, note


def _normalize_structural_dt(raw) -> Optional[datetime]:
    """V55: normalize candle_time / df cell to UTC-aware datetime."""
    if raw is None:
        return None
    parsed = _parse_radar_dt(raw)
    if parsed is not None:
        return parsed
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if hasattr(raw, 'to_pydatetime'):
        dt = raw.to_pydatetime()
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def _dt_from_df_row(df, idx: int) -> Optional[datetime]:
    """V55: timestamp from df.iloc[idx]['time'] or temporal index."""
    try:
        if df is None or idx < 0 or idx >= len(df):
            return None
        if 'time' in df.columns:
            dt = _normalize_structural_dt(df.iloc[idx]['time'])
            if dt is not None:
                return dt
        if not isinstance(df.index, pd.RangeIndex):
            return _normalize_structural_dt(df.index[idx])
    except Exception:
        pass
    return None


def _structural_event_dt(structural, df=None) -> Optional[datetime]:
    """V55: timestamp CHoCH/BOS — candle_time parse + fallback obligatoriu pe df."""
    if structural is None:
        return None
    idx = int(structural.index)
    ct = getattr(structural, 'candle_time', None)
    if ct is not None:
        dt = _normalize_structural_dt(ct)
        if dt is not None:
            return dt
    dt = _dt_from_df_row(df, idx)
    if dt is not None:
        return dt
    print(
        f"  [V55 STRUCT DT] idx={idx} candle_time={ct!r} — fallback df eșuat"
    )
    sys.stdout.flush()
    return None


def _poi_anchor_bar_index(df, anchor: datetime) -> Optional[int]:
    """V55: prima bară cu time >= anchor POI (fallback când edt lipsește)."""
    if df is None or anchor is None:
        return None
    try:
        if 'time' in df.columns:
            for i in range(len(df)):
                bar_dt = _normalize_structural_dt(df.iloc[i]['time'])
                if bar_dt is not None and bar_dt >= anchor:
                    return i
            return len(df) - 1
        if not isinstance(df.index, pd.RangeIndex):
            for i in range(len(df)):
                bar_dt = _normalize_structural_dt(df.index[i])
                if bar_dt is not None and bar_dt >= anchor:
                    return i
            return len(df) - 1
    except Exception:
        pass
    return None


def _filter_structural_post_poi(
    events: list, anchor: Optional[datetime], df=None,
) -> list:
    """V55: păstrează evenimente structurale la/ după primul touch POI (>= anchor)."""
    if anchor is None or not events:
        return events
    poi_bar_idx = _poi_anchor_bar_index(df, anchor)
    filtered = []
    for ev in events:
        edt = _structural_event_dt(ev, df)
        ev_idx = int(ev.index)
        if edt is not None and edt >= anchor:
            filtered.append(ev)
        elif edt is None and poi_bar_idx is not None and ev_idx >= poi_bar_idx:
            print(
                f"  [V55 POST-POI] idx={ev_idx} edt=None — păstrat via bar-index "
                f"(>= poi_bar={poi_bar_idx})"
            )
            filtered.append(ev)
        else:
            reason = 'before_poi' if edt is not None else 'edt_unresolved_before_poi'
            print(
                f"  [V55 POST-POI DROP] idx={ev_idx} edt={edt} anchor={anchor} "
                f"reason={reason}"
            )
    sys.stdout.flush()
    return filtered


def _log_choch_wait_diag(
    symbol: str,
    timeframe_display: str,
    required_direction: str,
    poi_first_touch_time: Optional[str],
    aligned_before_poi: list,
    choch_list: list,
    df,
) -> None:
    """V52.2: De ce WAITING — ultim CHoCH aliniat vs ancoră POI."""
    anchor = poi_first_touch_time or 'none'
    poi_dt = _parse_radar_dt(poi_first_touch_time)
    if aligned_before_poi:
        last = aligned_before_poi[-1]
        bars_ago = len(df) - last.index
        edt = _structural_event_dt(last, df)
        post_poi = edt is not None and poi_dt is not None and edt >= poi_dt
        valid = _is_structural_break_valid(last, last.direction, df)
        ts = edt.isoformat() if edt else '?'
        print(
            f"  [V52 DIAG {timeframe_display}] {symbol}: anchor={anchor} | "
            f"ultim {required_direction}: {ts} -{bars_ago}b "
            f"post_poi={'YES' if post_poi else 'NO'} valid={'YES' if valid else 'NO'}"
        )
    contrary = [c for c in choch_list if c.direction != required_direction]
    if contrary:
        last_c = contrary[-1]
        edt_c = _structural_event_dt(last_c, df)
        ts_c = edt_c.isoformat() if edt_c else '?'
        print(
            f"  [V52 DIAG {timeframe_display}] {symbol}: ultim {last_c.direction} "
            f"ignorat (contrary {required_direction}): {ts_c}"
        )
    sys.stdout.flush()


def _is_structural_break_valid(latest, direction: str, df) -> bool:
    """
    V50: respinge CHoCH/BOS invalidat de structură opusă după break.
    SELL: invalid dacă close > swing_broken (HH după rejection bearish).
    BUY: invalid dacă close < swing_broken (LL după rejection bullish).
    """
    try:
        break_idx = int(latest.index)
        swing_broken_price = float(latest.swing_broken.price)
    except Exception:
        return False
    if break_idx >= len(df) - 1:
        return True
    after = df.iloc[break_idx + 1:]
    if after.empty:
        return True
    closes = after['close'].astype(float)
    if direction == 'bearish':
        if (closes > swing_broken_price).any():
            return False
    else:
        if (closes < swing_broken_price).any():
            return False
    return True


def _retrace_implies_stale_anchor(retrace_pct: float, impulse: float) -> bool:
    """V53: impuls invalid sau retrace sub prag — overshoot >200% NU kill detectare."""
    if impulse <= 0:
        return True
    if retrace_pct < _RETRACE_ALERT_MIN:
        return True
    return False


def _retrace_is_overshoot(retrace_pct: float, impulse: float) -> bool:
    """V53: retrace >200% — degradare la WAITING pullback, păstrează choch_detected."""
    if impulse <= 0:
        return False
    return retrace_pct > _RETRACE_ALERT_MAX


def _retrace_is_alert_valid(retrace_pct: Optional[float]) -> bool:
    """V50: retrace în interval rezonabil pentru alertă Telegram."""
    if retrace_pct is None:
        return True
    if retrace_pct < _RETRACE_ALERT_MIN or retrace_pct > _RETRACE_ALERT_MAX:
        return False
    return True


# V54: erori tranzitorie executor — fără cooldown re-arm 30 min (F5)
_TRANSIENT_BLOCK_PREFIXES = (
    'V48: live data', 'V54: live data', 'SPREAD GUARD', '8010', 'broker feed',
    '[EXEC RETRY]', 'ROLLOVER',
)


def _preserve_execute_latch(setup: dict, result) -> bool:
    """V54: nu dezarma EXECUTE_NOW când panda/retrace/semnal activ (F2)."""
    return bool(
        setup.get('radar_panda_active')
        or result.tf_4h.in_poi_entry_zone
        or result.tf_1h.in_poi_entry_zone
        or setup.get('EXECUTE_NOW') is True
        or result.execution_ready
    )


# V53: chei latch — copy când prezente in-memory; pop din JSON când absente (bidirectional)
_LATCH_MERGE_COPY_KEYS = (
    'execute_now_alert_sent', 'execute_now_alert_key',
    'h4_choch_alert_sent', 'h4_bos_alert_sent', 'h1_choch_alert_sent', 'choch_1h_price',
    'radar_panda_active', 'poi_radar_armed_at', 'poi_touch_latched', 'radar_4h_signal_type',
    'h4_structure_locked_at', 'radar_1h_choch_stale',
    'poi_first_touch_time', 'h4_fvg_first_touch_time',
    '_poi_occupied', '_h4_fvg_occupied',
)
_LATCH_MERGE_POP_IF_ABSENT = (
    'poi_touch_latched', 'poi_first_touch_time', 'poi_radar_armed_at',
    'h4_fvg_first_touch_time', '_poi_occupied', '_h4_fvg_occupied',
)


def _merge_in_memory_latch_to_json(target: dict, source: dict) -> None:
    """V53: sync bidirectional — absența cheii in-memory șterge flag zombie din JSON."""
    for _ek in _LATCH_MERGE_COPY_KEYS:
        if _ek in source:
            target[_ek] = source[_ek]
        elif _ek in _LATCH_MERGE_POP_IF_ABSENT:
            target.pop(_ek, None)


def _evaluate_v43_daily_zone(
    setup_data: dict,
    direction: str,
    current_price: float,
    poi_bottom: float,
    poi_top: float,
    d1_wick_high: Optional[float] = None,
    d1_wick_low: Optional[float] = None,
) -> dict:
    """
    V43.2 E3-T1/T3: POI box + Premium/Discount ADR din JSON.
    LONG = Discount (sub EQ 50% adr_hl–adr_ll); SHORT = Premium (peste EQ adr_ll–adr_lh).
    """
    sym = setup_data.get('symbol', '?')
    in_poi_wick = _poi_box_intersects_wick(d1_wick_high, d1_wick_low, poi_bottom, poi_top)
    in_poi_price = _price_in_poi_box(current_price, poi_bottom, poi_top)
    in_poi = in_poi_wick or in_poi_price
    adr_lh = setup_data.get('adr_lh')
    adr_ll = setup_data.get('adr_ll')
    adr_hl = setup_data.get('adr_hl')

    pd_passed = False
    pd_reason = ''
    eq = None

    if direction == 'LONG':
        if adr_hl is not None and adr_ll is not None:
            eq = (float(adr_hl) + float(adr_ll)) / 2.0
            pd_passed = float(current_price) <= eq
            pd_reason = (
                f"Discount OK ({current_price:.5f} <= EQ {eq:.5f})"
                if pd_passed
                else f"LONG in Premium/neutral ({current_price:.5f} > EQ {eq:.5f})"
            )
        else:
            pd_reason = 'ADR adr_hl/adr_ll lipsă din JSON'
    elif direction == 'SHORT':
        if adr_ll is not None and adr_lh is not None:
            eq = (float(adr_ll) + float(adr_lh)) / 2.0
            pd_passed = float(current_price) >= eq
            pd_reason = (
                f"Premium OK ({current_price:.5f} >= EQ {eq:.5f})"
                if pd_passed
                else f"SHORT in Discount/neutral ({current_price:.5f} < EQ {eq:.5f})"
            )
        else:
            pd_reason = 'ADR adr_ll/adr_lh lipsă din JSON'
    else:
        pd_reason = f'direcție invalidă: {direction}'

    validated = in_poi
    if not in_poi:
        gate_reason = (
            f"wick/preț în afara POI "
            f"[{min(poi_bottom, poi_top):.5f}–{max(poi_bottom, poi_top):.5f}]"
        )
    elif not pd_passed:
        gate_reason = pd_reason
    else:
        gate_reason = pd_reason

    return {
        'validated': validated,
        'in_poi': in_poi,
        'in_poi_wick': in_poi_wick,
        'pd_passed': pd_passed,
        'equilibrium': eq,
        'reason': gate_reason,
        'symbol': sym,
    }


def _compute_pd_guard_for_execute(
    v43_zone: dict,
    pd_fallback: dict,
    daily_zone_validated: bool,
    poi_sequential_active: bool,
) -> tuple:
    """
    V52: După touch POI (latch/panda), P/D gate nu mai cere preț în caseta POI acum —
    permite entry secvențial V46 (retrace 60–80% în afara POI Daily).
    """
    if v43_zone.get('equilibrium') is not None:
        pd_ok = bool(v43_zone.get('pd_passed'))
        if poi_sequential_active:
            passed = pd_ok
        else:
            passed = pd_ok and bool(v43_zone.get('in_poi'))
        reason = '' if passed else v43_zone.get('reason', '')
        return passed, reason

    if pd_fallback.get('skipped'):
        return True, ''

    pd_ok = bool(pd_fallback.get('passed', True))
    if poi_sequential_active:
        passed = pd_ok
    else:
        passed = pd_ok and daily_zone_validated
    reason = '' if passed else pd_fallback.get('reason', '')
    return passed, reason


def _empty_tf_waiting(timeframe: str) -> 'TimeframeAnalysis':
    """V43.2: TF placeholder când POI Daily nu e validat — fără CHoCH în aer."""
    is_h1 = timeframe.upper() in ('H1', '1H')
    return TimeframeAnalysis(
        timeframe="1H" if is_h1 else "4H",
        choch_detected=False,
        choch_direction=None,
        choch_time=None,
        choch_price=None,
        fvg_detected=False,
        fvg_top=None,
        fvg_bottom=None,
        fvg_entry=None,
        in_fvg=False,
        distance_to_fvg_pips=0.0,
        status=PullbackStatus.WAITING_1H_CHOCH if is_h1 else PullbackStatus.WAITING_4H_CHOCH,
    )


def _d1_bar_open_iso(df_d1) -> Optional[str]:
    """V47.1: timp deschidere lumânare D1 curentă (ancoră touch POI wick)."""
    if df_d1 is None or df_d1.empty:
        return None
    row = df_d1.iloc[-1]
    for col in ('time', 'datetime', 'Date', 'date', 'timestamp'):
        if col in df_d1.columns:
            dt = _parse_radar_dt(row[col])
            if dt is not None:
                return dt.isoformat()
    try:
        idx = df_d1.index[-1]
        dt = _parse_radar_dt(idx)
        if dt is not None:
            return dt.isoformat()
    except Exception:
        pass
    return None


def _track_mitigation_touch(
    setup_data: dict,
    v43_zone: dict,
    tf_4h: 'TimeframeAnalysis' = None,
    d1_touch_time: Optional[str] = None,
    df_d1=None,
    df_h4=None,
    poi_bottom: Optional[float] = None,
    poi_top: Optional[float] = None,
) -> None:
    """V47.1: State machine POI — latch panda post-touch până la alertă 4H."""
    now_ts = datetime.now(timezone.utc).isoformat()
    if poi_bottom is None or poi_top is None:
        poi_bottom, poi_top = _poi_bounds_from_stored(setup_data)
    historical_touch = _find_first_poi_touch_time(df_d1, df_h4, poi_bottom, poi_top)
    in_poi = v43_zone.get('in_poi', False)
    validated = v43_zone.get('validated', False)
    was_occupied = bool(setup_data.get('_poi_occupied'))
    h4_structural_alerted = bool(
        setup_data.get('h4_choch_alert_sent') or setup_data.get('h4_bos_alert_sent')
    )

    if not in_poi:
        # V49: latch ON post-touch — CHoCH + retrace 60–80% pot apărea în afara casetei POI
        if setup_data.get('poi_touch_latched'):
            setup_data['_poi_occupied'] = False
            setup_data['radar_panda_active'] = True
            if not h4_structural_alerted:
                print(
                    f"  [V49 POI LATCH] {setup_data.get('symbol', '?')}: preț ieșit din POI — "
                    f"panda ON, așteptăm CHoCH/BOS 4H post-touch"
                )
            else:
                print(
                    f"  [V49 POI LATCH] {setup_data.get('symbol', '?')}: post-alertă 4H — "
                    f"latch activ pentru entry retrace 60–80%"
                )
            sys.stdout.flush()
            return
        setup_data.pop('poi_first_touch_time', None)
        setup_data.pop('h4_fvg_first_touch_time', None)
        setup_data['_poi_occupied'] = False
        setup_data.pop('_h4_fvg_occupied', None)
        setup_data['radar_panda_active'] = False
        setup_data.pop('poi_touch_latched', None)
        return

    if not was_occupied and validated:
        touch_anchor = _resolve_poi_touch_anchor(
            d1_touch_time=d1_touch_time,
            now_ts=now_ts,
            historical_touch=historical_touch,
            existing=None,
        )
        setup_data['poi_first_touch_time'] = touch_anchor
        setup_data['poi_radar_armed_at'] = touch_anchor
        setup_data['poi_touch_latched'] = True
        setup_data.pop('h4_fvg_first_touch_time', None)
        setup_data['h4_choch_alert_sent'] = False
        setup_data['h4_bos_alert_sent'] = False
        setup_data['h1_choch_alert_sent'] = False
        setup_data['h4_structure_locked'] = False
        setup_data.pop('h4_structure_locked_at', None)
        setup_data.pop('choch_1h_price', None)
        # V50: nu resetăm radar_*_choch_detected — evită rising-edge zombi pe CHoCH vechi
        setup_data['radar_panda_active'] = True
        print(
            f"  [V50 POI ARM] {setup_data.get('symbol', '?')}: radar PANDA ON @ {touch_anchor} — "
            f"dedup alerte resetat, asteptam break LIVE ≤3b post-touch"
        )
        sys.stdout.flush()
    elif validated and not setup_data.get('poi_first_touch_time'):
        touch_anchor = _resolve_poi_touch_anchor(
            d1_touch_time=d1_touch_time,
            now_ts=now_ts,
            historical_touch=historical_touch,
            existing=None,
        )
        setup_data['poi_first_touch_time'] = touch_anchor
        setup_data['poi_radar_armed_at'] = touch_anchor
        setup_data['poi_touch_latched'] = True
        setup_data['radar_panda_active'] = True
    elif validated and setup_data.get('poi_touch_latched'):
        old_anchor = setup_data.get('poi_first_touch_time')
        touch_anchor = _resolve_poi_touch_anchor(
            d1_touch_time=d1_touch_time,
            now_ts=now_ts,
            historical_touch=historical_touch,
            existing=old_anchor,
        )
        if touch_anchor != old_anchor:
            setup_data['poi_first_touch_time'] = touch_anchor
            print(
                f"  [V52.2 POI ANCHOR] {setup_data.get('symbol', '?')}: "
                f"{old_anchor} → {touch_anchor} (retroactive first touch)"
            )
            sys.stdout.flush()

    setup_data['_poi_occupied'] = validated

    if tf_4h is not None:
        if tf_4h.in_fvg:
            if not setup_data.get('_h4_fvg_occupied'):
                setup_data['h4_fvg_first_touch_time'] = now_ts
            setup_data['_h4_fvg_occupied'] = True
        else:
            setup_data['_h4_fvg_occupied'] = False


def _apply_h1_chronology_guard(
    symbol: str,
    setup_data: dict,
    tf_4h: 'TimeframeAnalysis',
    tf_1h: 'TimeframeAnalysis',
    daily_zone_validated: bool,
) -> Tuple['TimeframeAnalysis', bool]:
    """
    V43.8: Respinge CHoCH 1H anterior primului touch POI/FVG (ghost trigger GBPJPY).
    Returns (tf_1h, h1_stale).
    """
    if not tf_1h.choch_detected:
        return tf_1h, False

    if not daily_zone_validated and not setup_data.get('poi_touch_latched'):
        print(
            f"  🛑 [V43.8 H1 STALE] {symbol}: 1H CHoCH respins — POI Daily nevalidat"
        )
        sys.stdout.flush()
        logger.warning(f"[V43.8 H1 STALE] {symbol}: 1H CHoCH fără POI validat")
        return _empty_tf_waiting("H1"), True

    anchor = _resolve_mitigation_touch_anchor(setup_data, tf_4h)
    h1_time = _parse_radar_dt(tf_1h.choch_time)

    if anchor is None:
        print(
            f"  🛑 [V43.8 H1 STALE] {symbol}: 1H CHoCH respins — "
            f"lipsă ancoră mitigation_touch"
        )
        sys.stdout.flush()
        logger.warning(
            f"[V43.8 H1 STALE] {symbol}: 1H CHoCH fără poi_first_touch_time"
        )
        return _empty_tf_waiting("H1"), True

    if h1_time is None:
        return tf_1h, False

    if h1_time > anchor:
        return tf_1h, False

    print(
        f"  🛑 [V43.8 H1 STALE] {symbol}: 1H CHoCH @ {h1_time.isoformat()} "
        f"<= mitigation_touch {anchor.isoformat()} — INVALID (pre-POI touch)"
    )
    sys.stdout.flush()
    logger.warning(
        f"[V43.8 H1 STALE] {symbol}: 1H CHoCH stale vs mitigation touch "
        f"({h1_time.isoformat()} <= {anchor.isoformat()})"
    )
    return _empty_tf_waiting("H1"), True


# Log fisier ASCII (V37.1) — alternativa la multi_tf_radar_stdout.log cu emoji
_RADAR_LOG_DIR = _RADAR_DIR / "logs"
_RADAR_LOG_DIR.mkdir(exist_ok=True)
logger.remove()
logger.add(
    str(_RADAR_LOG_DIR / "multi_tf_radar.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}",
    filter=_radar_log_filter,
    level="INFO",
    rotation="10 MB",
    retention="7 days",
    encoding="utf-8",
)
# V37.1.2: Consola interactiva — loguri colorate ctrader (Got N bars...) ca inainte
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level:<8}</level> | <level>{message}</level>",
    level="DEBUG",
    colorize=True,
)


class PullbackStatus(Enum):
    """Execution status for multi-timeframe analysis"""
    WAITING_1H_CHOCH = "👀 WAITING_1H_CHOCH"
    WAITING_4H_CHOCH = "👀 WAITING_4H_CHOCH"
    WAITING_1H_PULLBACK = "⏳ WAITING_1H_PULLBACK"
    WAITING_4H_PULLBACK = "⏳ WAITING_4H_PULLBACK"
    EXECUTE_NOW_1H = "🔥 EXECUTE_NOW_1H"
    EXECUTE_NOW_4H = "🔥 EXECUTE_NOW_4H"


@dataclass
class TimeframeAnalysis:
    """Analysis result for a specific timeframe"""
    timeframe: str  # "1H" or "4H"
    choch_detected: bool
    choch_direction: Optional[str]
    choch_time: Optional[str]
    choch_price: Optional[float]
    fvg_detected: bool
    fvg_top: Optional[float]
    fvg_bottom: Optional[float]
    fvg_entry: Optional[float]
    in_fvg: bool
    distance_to_fvg_pips: float
    status: PullbackStatus
    # V16.2: 50% Equilibrium al impulsului CHoCH (frontiera Discount/Premium)
    # LONG = Discount = sub EQ  |  SHORT = Premium = peste EQ
    equilibrium: Optional[float] = None
    # V19.4 FIX #3: scan_error propagation — previne suprascrierea FVG valid cu None
    scan_error: bool = False
    scan_error_msg: str = ""
    # V19.6 FIX #3: transparență sursă zonă — structural FVG vs. Fibo sintetic
    fvg_source: str = "structural"  # "structural" | "fibo_fallback"
    # V24.5: Structural SL = swing_broken.price ± buffer (4H only, dar calculat pe ambele TF)
    # LONG: SL sub swing_broken | SHORT: SL deasupra swing_broken
    h4_sl_price: Optional[float] = None
    # V24.9: Câte bare în urmă s-a format CHoCH-ul — recency guard pentru h4_structure_locked
    # 9999 = valoare default = CHoCH inexistent / nu am date
    choch_bars_ago: int = 9999
    # V25.1: BOS tracking INDEPENDENT de CHoCH — pentru confirmare trend continuu
    # Logica: CHoCH se formează O SINGURĂ DATĂ la schimbarea de caracter. Trendul continuă prin BOS.
    # Un trend valid = CHoCH vechi (inițiator) + BOS recent aliniat (confirmare trend activ).
    # h4_structure_locked se pune dacă: CHoCH proaspăt ALINIAT *SAU* BOS recent ALINIAT.
    bos_detected: bool = False
    bos_direction: Optional[str] = None
    bos_bars_ago: int = 9999
    # V46: POI + Premium/Discount 60–80% entry tracking
    retrace_pct: Optional[float] = None
    in_poi_entry_zone: bool = False
    # V47: CHoCH vs BOS cascaded entry
    signal_type: Optional[str] = None  # 'CHoCH' | 'BOS'
    # V53: retrace >200% — CHoCH valid, entry așteaptă re-intrare în bandă 60–80%
    overshoot_stale: bool = False


@dataclass
class MultiTFResult:
    """Complete multi-timeframe analysis result"""
    symbol: str
    direction: str
    
    # Daily validation
    daily_zone_validated: bool
    daily_fvg_top: float
    daily_fvg_bottom: float
    daily_entry: float
    
    # Current price
    current_price: float
    
    # 1H analysis
    tf_1h: TimeframeAnalysis
    
    # 4H analysis
    tf_4h: TimeframeAnalysis
    
    # Final verdict
    execution_ready: bool
    verdict: str
    priority_timeframe: Optional[str]  # "1H" or "4H"
    # V36.5: P/D Guard — scan H4/H1 always-on; P/D blochează doar execuția
    pd_guard_passed: bool = True
    pd_guard_reason: str = ""
    # V43.7: 1H CHoCH respins — anterior ancorii 4H (ghost trigger)
    h1_choch_stale: bool = False
    poi_first_touch_time: Optional[str] = None


class MultiTFRadar:
    """Multi-timeframe execution radar with 1H + 4H scanning"""
    
    def __init__(self):
        if not DEPS_AVAILABLE:
            sys.exit(1)
        
        self.ctrader = CTraderCBotClient()
        if not self.ctrader.is_available():
            print("❌ cTrader cBot not running")
            sys.exit(1)
        
        print("✅ cTrader cBot connected")
        
        # Create SMC detectors with different ATR thresholds
        self.smc_1h = SMCDetector(
            swing_lookback=5,
            atr_multiplier=0.8  # Relaxed for 1H precision moves
        )
        
        self.smc_4h = SMCDetector(
            swing_lookback=8,   # V19: più context structural pe 4H (5→8)
            atr_multiplier=1.0  # V15.4: relaxed from 1.2→1.0 — avoid missing clear 4H CHoCH
        )
        
        print("🎯 SMC Detectors initialized:")
        print("   - 1H: ATR 0.8x (SNIPER mode)")
        print("   - 4H: ATR 1.0x (HIGH CONFIDENCE mode — V15.4)")

        # V25.2: Contor eșecuri consecutive port 8010 — alertă Telegram la 3 eșecuri
        self._port8010_fail_count: int = 0
        self._port8010_alert_sent: bool = False  # anti-spam: o singură alertă per incident
        self._execute_now_alert_keys: set = set()  # V37.9: dedup Telegram per setup (persistat in JSON)
        self._telegram_token: str = _os_global.getenv('TELEGRAM_BOT_TOKEN', '')
        self._telegram_chat_id: str = _os_global.getenv('TELEGRAM_CHAT_ID', '')
        # V36.3: motivul ultimului skip — propagat la run_scan pentru logging explicit
        self._last_skip_reason: Optional[str] = None

    # V36.4: IC Markets folosește XTIUSD live — WTIUSD poate returna "Symbol not found"
    _BROKER_SYMBOL_ALIASES: Dict[str, List[str]] = {
        'BTCUSD': ['BTC/USD'],
        'XTIUSD': ['WTIUSD'],
        'USOIL': ['WTIUSD', 'XTIUSD'],
        'WTIUSD': ['XTIUSD'],
    }

    @classmethod
    def _broker_symbol_candidates(cls, json_symbol: str) -> List[str]:
        """V36.4: simbolul din JSON PRIMUL — apoi alias-uri broker."""
        s = (json_symbol or '').upper().strip()
        if not s:
            return ['UNKNOWN']
        seen: set = set()
        ordered: List[str] = []

        def _add(sym: str) -> None:
            if sym and sym not in seen:
                seen.add(sym)
                ordered.append(sym)

        _add(s)
        for alias in cls._BROKER_SYMBOL_ALIASES.get(s, []):
            _add(alias)
        return ordered

    @staticmethod
    def _is_commodity_or_crypto(symbol: str) -> bool:
        s = symbol.upper()
        return any(x in s for x in [
            'XTI', 'WTI', 'OIL', 'BRENT', 'USOIL',
            'XAU', 'XAG', 'GOLD', 'SILVER',
            'BTC', 'ETH', 'XRP', 'LTC', 'ADA', 'DOGE',
        ])

    @classmethod
    def _bar_count_chain(cls, timeframe: str, symbol: str, primary: int) -> List[int]:
        """V36.4: lanț de bare — mărfuri/crypto reduc agresiv la eșec broker."""
        chain: List[int] = []
        seen: set = set()
        extras = (200, 150, 100, 50) if cls._is_commodity_or_crypto(symbol) else (150, 100, 50)
        for n in (primary, primary // 2, *extras):
            if n and n >= 20 and n not in seen:
                seen.add(n)
                chain.append(n)
        return chain

    @staticmethod
    def _fvg_prices_sane(current_price: float, top: float, bottom: float) -> bool:
        """V37.1: Respinge FVG cu bare corupte (ex: 4139 pe pereche 0.57)."""
        if not current_price or current_price <= 0 or top is None or bottom is None:
            return False
        if top <= bottom:
            return False
        for px in (top, bottom):
            ratio = px / current_price
            if ratio > 10.0 or ratio < 0.1:
                return False
        return True

    @staticmethod
    def _get_pip_size(symbol: str) -> float:
        """V37.0 — delegat la pip_utils.get_pip_size (Crypto + Commodities)."""
        return get_pip_size(symbol)

    @staticmethod
    def _log_radar_warn(symbol: str, reason: str) -> None:
        """V36.4: avertisment — setup Daily rămâne în JSON, retry la 30s."""
        print(f"  ⚠️ [RADAR WARN] {symbol}: {reason} — setup păstrat în monitoring, retry ciclu următor")
        sys.stdout.flush()

    @staticmethod
    def _log_radar_skip(symbol: str, reason: str) -> None:
        """V36.3: fiecare skip trebuie explicat explicit în consolă."""
        print(f"  ⛔ [RADAR SKIP] {symbol}: {reason}")
        sys.stdout.flush()

    @staticmethod
    def _log_scan_done(symbol: str, tf: 'TimeframeAnalysis', num_bars: int) -> None:
        """V36.5: confirmare explicită că H4/H1 au fost descărcate și analizate."""
        if tf.choch_detected:
            _choch = f"CHoCH {tf.choch_direction} -{tf.choch_bars_ago}b"
        else:
            _choch = "no CHoCH"
        if tf.bos_detected:
            _bos = f"BOS {tf.bos_direction} -{tf.bos_bars_ago}b"
        else:
            _bos = "no BOS"
        print(
            f"  ✅ [V36.5 SCAN DONE] {symbol} {tf.timeframe} — {num_bars} bare | "
            f"{_choch} | {_bos} | status={tf.status.value}"
        )
        sys.stdout.flush()

    def _evaluate_pd_guard(
        self,
        symbol: str,
        required_direction: str,
        current_price: float,
    ) -> dict:
        """
        V36.5: P/D Guard evaluat DUPĂ scan H4/H1 — returnează dict, fără return None.
        BUY valid în Discount; SELL valid în Premium.
        """
        _pip_pd = self._get_pip_size(symbol)
        _result = {
            'passed': True,
            'zone': 'unknown',
            'midpoint': None,
            'reason': '',
            'skipped': False,
        }
        try:
            _df_d1_pd = self.get_historical_data(symbol, "D1", 3)
            if _df_d1_pd is None or _df_d1_pd.empty:
                _result['skipped'] = True
                _result['reason'] = 'D1 indisponibil — guard P/D omis'
                print(f"  ⚠️ [V36.5 P/D] {symbol}: D1 indisponibil — guard P/D omis "
                      f"(pip_size={_pip_pd})")
                sys.stdout.flush()
                return _result

            _d1_high_pd = float(_df_d1_pd['high'].iloc[-1])
            _d1_low_pd = float(_df_d1_pd['low'].iloc[-1])
            _d1_range_pd = _d1_high_pd - _d1_low_pd
            _min_range = _pip_pd * 5
            if _d1_range_pd < _min_range:
                _result['skipped'] = True
                _result['reason'] = f'range D1 prea mic ({_d1_range_pd:.5f})'
                print(f"  ⚠️ [V36.5 P/D] {symbol}: range D1 prea mic "
                      f"({_d1_range_pd:.5f} < {_min_range:.5f} = 5p @ pip={_pip_pd}) — guard omis")
                sys.stdout.flush()
                return _result

            _d1_midpoint = (_d1_high_pd + _d1_low_pd) / 2.0
            _result['midpoint'] = _d1_midpoint
            _zone = 'premium' if current_price > _d1_midpoint else 'discount'
            _result['zone'] = _zone

            if required_direction == 'bullish' and current_price > _d1_midpoint:
                _result['passed'] = False
                _result['reason'] = (
                    f"LONG in Premium ({current_price:.5f} > EQ {_d1_midpoint:.5f} "
                    f"| range={_d1_range_pd/_pip_pd:.1f}p) — așteptăm Discount"
                )
            elif required_direction == 'bearish' and current_price < _d1_midpoint:
                _result['passed'] = False
                _result['reason'] = (
                    f"SHORT in Discount ({current_price:.5f} < EQ {_d1_midpoint:.5f} "
                    f"| range={_d1_range_pd/_pip_pd:.1f}p) — așteptăm Premium"
                )
            else:
                _pd_label = 'Discount ✅' if required_direction == 'bullish' else 'Premium ✅'
                print(f"  ✅ [V36.5 P/D] {symbol}: {current_price:.5f} in {_pd_label} "
                      f"(EQ={_d1_midpoint:.5f} | range={_d1_range_pd/_pip_pd:.0f}p | pip={_pip_pd})")
                sys.stdout.flush()
        except Exception as _pd_err:
            _result['skipped'] = True
            _result['reason'] = f'eroare calcul P/D: {_pd_err}'
            print(f"  ⚠️ [V36.5 P/D] {symbol}: eroare calcul ({_pd_err}) — procedăm fără guard "
                  f"(pip={_pip_pd})")
            sys.stdout.flush()
        return _result
    
    def _write_monitoring_setups(self, setups: list) -> None:
        """Atomic write monitoring_setups.json (V43.2 purge path)."""
        import os as _wos
        import numpy as _np

        def _json_safe(obj):
            if isinstance(obj, (_np.bool_,)):
                return bool(obj)
            if isinstance(obj, (_np.integer,)):
                return int(obj)
            if isinstance(obj, (_np.floating,)):
                return float(obj)
            if isinstance(obj, (_np.ndarray,)):
                return obj.tolist()
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        payload = {
            'setups': setups,
            'last_updated': datetime.now().isoformat(),
        }
        with open(_MONITORING_TMP, 'w', encoding='utf-8') as _wf:
            json.dump(payload, _wf, indent=2, default=_json_safe)
        _wos.replace(_MONITORING_TMP, _MONITORING_FILE)

    def _purge_structural_breaches(self, setups: list) -> list:
        """V43.2 E3-T2: elimină definitiv setup-uri cu structural_breach din JSON."""
        survivors = []
        purged_symbols = []
        for s in setups:
            if not isinstance(s, dict):
                continue
            sym = s.get('symbol', '?')
            st = s.get('status', '')
            if (
                s.get('structural_breach')
                and not s.get('entry1_filled')
                and st not in ('TRADE_OPEN', 'PARTIAL_OPEN')
            ):
                purged_symbols.append(sym)
                _radar_out(
                    f"[🛰️ RADAR PURGE] Setup invalidat structural eliminat definitiv din JSON."
                )
                _radar_out(
                    f"  [🛰️ RADAR PURGE] {sym}: structural_breach=True — "
                    f"continuitate MORTĂ (LH/LL spart)"
                )
                continue
            survivors.append(s)
        if purged_symbols:
            try:
                self._write_monitoring_setups(survivors)
                logger.warning(
                    f"[V43.2 PURGE] Eliminate {len(purged_symbols)} setup(uri): "
                    f"{', '.join(purged_symbols)}"
                )
            except Exception as _pe:
                logger.error(f"[V43.2 PURGE] Salvare JSON eșuată: {_pe}")
                return setups
        return survivors

    @staticmethod
    def _is_4h_aligned_for_1h_entry(
        tf_4h: 'TimeframeAnalysis',
        required_direction: str,
        allow_bos: bool,
    ) -> bool:
        """V43.2 E3-T4: Entry 1H permis doar dacă 4H e deja aliniat în POI validat."""
        if tf_4h.choch_detected and tf_4h.choch_direction == required_direction:
            return True
        if allow_bos and tf_4h.bos_detected and tf_4h.bos_direction == required_direction:
            return True
        return False

    def _send_radar_telegram_alert(self, message: str) -> None:
        """V25.2: Trimite alertă critică pe Telegram din Radar (port 8010 offline etc.)"""
        if not self._telegram_token or not self._telegram_chat_id:
            return
        try:
            import requests as _req_tg
            sep = "────────────────"
            branded = (
                f"{message.strip()}\n\n"
                f"  {sep}\n"
                f"  🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
                f"  {sep}\n"
                f"  🏛 <b>ГЛИТЧ ИН МАТРИКС</b> 🏛"
            )
            _req_tg.post(
                f"https://api.telegram.org/bot{self._telegram_token}/sendMessage",
                json={'chat_id': self._telegram_chat_id, 'text': branded, 'parse_mode': 'HTML'},
                timeout=10
            )
        except Exception as _tg_err:
            print(f"⚠️ [RADAR TELEGRAM] Eroare trimitere alertă: {_tg_err}")

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price from cTrader — V36.3: broker symbol fallbacks + logging explicit."""
        import requests
        last_err: Optional[str] = None
        for broker_sym in self._broker_symbol_candidates(symbol):
            try:
                response = requests.get(
                    f"http://localhost:8010/price",
                    params={"symbol": broker_sym},
                    timeout=2
                )

                if response.status_code == 200:
                    data = response.json()
                    bid = data.get('bid', 0)
                    ask = data.get('ask', 0)
                    if bid > 0 and ask > 0:
                        if broker_sym != symbol.upper():
                            print(f"  ✅ [V36.3 SYMBOL MAP] {symbol} → {broker_sym} (preț OK)")
                            sys.stdout.flush()
                        if self._port8010_fail_count > 0:
                            print(f"✅ [PORT 8010] Conexiune restaurată pentru {symbol} — resetare contor eșecuri")
                            self._port8010_fail_count = 0
                            self._port8010_alert_sent = False
                        return (bid + ask) / 2.0

                last_err = f"HTTP {response.status_code} body={response.text[:120]}"
                print(f"⚠️  [PORT 8010] Răspuns invalid {symbol} ca {broker_sym}: {last_err}")

            except Exception as e:
                last_err = str(e)
                print(f"⚠️  [PORT 8010] Eroare {symbol} ca {broker_sym}: {e}")

        self._port8010_fail_count += 1
        print(f"⚠️  [RADAR ERROR] Preț indisponibil pentru {symbol} — toate variantele eșuate"
              f" {self._broker_symbol_candidates(symbol)}"
              f"{f' | ultima eroare: {last_err}' if last_err else ''}"
              f" (eșec #{self._port8010_fail_count})")
        sys.stdout.flush()

        # V25.2: Alertă Telegram la 3 eșecuri consecutive (anti-spam: o singură alertă per incident)
        if self._port8010_fail_count >= 3 and not self._port8010_alert_sent:
            self._port8010_alert_sent = True
            print(f"🚨 [PORT 8010 OFFLINE] {self._port8010_fail_count} eșecuri consecutive — trimit alertă Telegram!")
            self._send_radar_telegram_alert(
                f"🚨 <b>CONEXIUNE ÎNTRERUPTĂ — cBot OFFLINE</b>\n\n"
                f"MarketDataProvider cBot de pe cTrader NU răspunde pe portul 8010.\n"
                f"Eșecuri consecutive: <b>{self._port8010_fail_count}</b>\n\n"
                f"⛔ Datele live sunt INDISPONIBILE.\n"
                f"⛔ Execuția automată este BLOCATĂ.\n\n"
                f"🔧 Acțiune necesară:\n"
                f"  1. Verifică dacă cTrader este deschis pe VPS\n"
                f"  2. Verifică dacă cBot-ul <b>DATA-Market</b> rulează\n"
                f"  3. Verifică: <code>Test-NetConnection localhost -Port 8010</code>"
            )

        return None
    
    def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        num_candles: int = 100
    ) -> Optional[pd.DataFrame]:
        """V36.4: broker symbol map + bar-count fallback chain + zero crash."""
        candidates = self._broker_symbol_candidates(symbol)
        bar_chain = self._bar_count_chain(timeframe, symbol, num_candles)
        print(f"  📥 [V36.4 DATA] {symbol} {timeframe} — simboluri {candidates} | bare {bar_chain}")
        sys.stdout.flush()
        last_err: Optional[str] = None
        for bar_count in bar_chain:
            for broker_sym in candidates:
                try:
                    df = self.ctrader.get_historical_data(broker_sym, timeframe, bar_count)
                    if df is not None and not df.empty:
                        if broker_sym != symbol.upper() or bar_count != num_candles:
                            print(f"  ✅ [V36.4 DATA OK] {symbol} → {broker_sym} "
                                  f"{timeframe} x{bar_count} ({len(df)} bare)")
                            sys.stdout.flush()
                        return df.reset_index()
                    last_err = f"{broker_sym} x{bar_count}: răspuns gol"
                except Exception as e:
                    last_err = f"{broker_sym} x{bar_count}: {e}"
                    print(f"  ⚠️ [RADAR ERROR] {symbol} {timeframe} via {broker_sym} "
                          f"x{bar_count}: {e}")
                    sys.stdout.flush()
        print(f"  ⚠️ [RADAR WARN] {symbol} {timeframe}: date indisponibile "
              f"(încercat {candidates} × {bar_chain})"
              f"{f' — ultima: {last_err}' if last_err else ''}")
        sys.stdout.flush()
        return None
    
    def _build_v46_choch_entry_analysis(
        self,
        *,
        symbol: str,
        timeframe: str,
        timeframe_display: str,
        required_direction: str,
        current_price: float,
        latest_choch,
        choch_direction: str,
        choch_time_str: str,
        choch_price,
        choch_break_price: float,
        choch_equilibrium,
        h4_sl_price,
        _choch_bars_ago: int,
        _bos_detected_val: bool,
        _bos_direction_val,
        _bos_bars_ago_val: int,
        _bos_trigger_bars_ago: int,
        daily_in_poi: bool,
        poi_touch_latched: bool = False,
        latest_fvg=None,
        signal_type: str = 'CHoCH',
    ) -> TimeframeAnalysis:
        """V49: entry secvențial — touch POI (latch) apoi retrace 60–80% pe CHoCH/BOS."""
        wait_pb = (
            PullbackStatus.WAITING_1H_PULLBACK
            if timeframe == "H1"
            else PullbackStatus.WAITING_4H_PULLBACK
        )
        try:
            swing_broken_price = float(latest_choch.swing_broken.price)
        except Exception:
            return TimeframeAnalysis(
                timeframe=timeframe_display,
                choch_detected=True,
                choch_direction=choch_direction,
                choch_time=choch_time_str,
                choch_price=choch_price,
                fvg_detected=False,
                status=wait_pb,
                equilibrium=choch_equilibrium,
                h4_sl_price=h4_sl_price,
                choch_bars_ago=_choch_bars_ago,
                bos_detected=_bos_detected_val,
                bos_direction=_bos_direction_val,
                bos_bars_ago=_bos_bars_ago_val,
            )

        retrace_pct, impulse_size = _choch_impulse_retrace_pct(
            choch_break_price, swing_broken_price, current_price, choch_direction,
        )
        pip_size = self._get_pip_size(symbol)

        if _retrace_implies_stale_anchor(retrace_pct, impulse_size):
            print(
                f"  🛑 [V53 RETRACE INVALID] {symbol} {timeframe_display}: "
                f"retrace={retrace_pct * 100:.1f}% impulse={impulse_size:.5f} — anchor invalid"
            )
            sys.stdout.flush()
            wait_choch = (
                PullbackStatus.WAITING_1H_CHOCH if timeframe == "H1"
                else PullbackStatus.WAITING_4H_CHOCH
            )
            return TimeframeAnalysis(
                timeframe=timeframe_display,
                choch_detected=False,
                choch_direction=None,
                choch_time=None,
                choch_price=None,
                fvg_detected=False,
                status=wait_choch,
                equilibrium=choch_equilibrium,
                h4_sl_price=h4_sl_price,
                choch_bars_ago=_choch_bars_ago,
                bos_detected=_bos_detected_val,
                bos_direction=_bos_direction_val,
                bos_bars_ago=_bos_bars_ago_val,
            )

        if _retrace_is_overshoot(retrace_pct, impulse_size):
            print(
                f"  ⚠️ [V53 RETRACE OVERSHOOT] {symbol} {timeframe_display}: "
                f"retrace={retrace_pct * 100:.1f}% > {_RETRACE_ALERT_MAX * 100:.0f}% — "
                f"CHoCH păstrat, așteptăm re-intrare 60–80%"
            )
            sys.stdout.flush()
            return TimeframeAnalysis(
                timeframe=timeframe_display,
                choch_detected=True,
                choch_direction=choch_direction,
                choch_time=choch_time_str,
                choch_price=choch_price,
                fvg_detected=False,
                status=wait_pb,
                equilibrium=choch_equilibrium,
                h4_sl_price=h4_sl_price,
                choch_bars_ago=_choch_bars_ago,
                retrace_pct=retrace_pct,
                overshoot_stale=True,
                bos_detected=_bos_detected_val,
                bos_direction=_bos_direction_val,
                bos_bars_ago=_bos_bars_ago_val,
                signal_type=signal_type,
            )

        if impulse_size <= 0:
            print(f"  ⚠️ [V46 GUARD] {symbol}: impuls 0 pips — WAITING")
            sys.stdout.flush()
            return TimeframeAnalysis(
                timeframe=timeframe_display,
                choch_detected=True,
                choch_direction=choch_direction,
                choch_time=choch_time_str,
                choch_price=choch_price,
                fvg_detected=False,
                status=wait_pb,
                equilibrium=choch_equilibrium,
                h4_sl_price=h4_sl_price,
                choch_bars_ago=_choch_bars_ago,
                retrace_pct=retrace_pct,
                bos_detected=_bos_detected_val,
                bos_direction=_bos_direction_val,
                bos_bars_ago=_bos_bars_ago_val,
            )

        if _choch_bars_ago > 72:
            print(
                f"  ⚠️ [V46 AGE] {symbol}: CHoCH la -{_choch_bars_ago} bare > 72 — "
                f"ancora expirata, asteptam CHoCH nou"
            )
            sys.stdout.flush()
            return TimeframeAnalysis(
                timeframe=timeframe_display,
                choch_detected=True,
                choch_direction=choch_direction,
                choch_time=choch_time_str,
                choch_price=choch_price,
                fvg_detected=False,
                status=wait_pb,
                equilibrium=choch_equilibrium,
                h4_sl_price=h4_sl_price,
                choch_bars_ago=_choch_bars_ago,
                retrace_pct=retrace_pct,
                bos_detected=_bos_detected_val,
                bos_direction=_bos_direction_val,
                bos_bars_ago=_bos_bars_ago_val,
            )

        zone_bottom, zone_top, zone_entry = _choch_premium_discount_zone(
            choch_break_price, impulse_size, choch_direction,
        )
        in_retrace_band = (
            zone_bottom <= current_price <= zone_top
            and _RETRACE_ENTRY_MIN <= retrace_pct <= _RETRACE_ENTRY_MAX
        )
        in_poi_entry = in_retrace_band and (daily_in_poi or poi_touch_latched)

        status, sniper_note = _v46_entry_status_and_note(
            timeframe_display,
            symbol,
            required_direction,
            in_poi_entry,
            retrace_pct,
            _choch_bars_ago,
        )

        if in_retrace_band:
            distance_to_fvg_pips = 0.0
        elif choch_direction == 'bullish':
            distance_to_fvg_pips = abs(current_price - zone_top) / pip_size
        else:
            distance_to_fvg_pips = abs(zone_bottom - current_price) / pip_size

        if _choch_bars_ago <= 3:
            print(f"  [V46 INFO] CHoCH LIVE -{_choch_bars_ago}b (informativ, nu gate)")
        elif _bos_trigger_bars_ago <= 3:
            print(
                f"  [V46 INFO] BOS post-CHoCH LIVE -{_bos_trigger_bars_ago}b "
                f"(CHoCH ancora -{_choch_bars_ago}b, informativ)"
            )
        sys.stdout.flush()

        fvg_source = "structural" if latest_fvg else "premium_discount"
        eq_val = choch_equilibrium if choch_equilibrium else zone_entry
        _sig_label = signal_type.upper()
        print(
            f"  [V46 POI-PD] {symbol} {timeframe_display} ({_sig_label}) | "
            f"Impulse anchor: swing_broken {swing_broken_price:.5f} -> break {choch_break_price:.5f} "
            f"({impulse_size / pip_size:.1f}p)"
        )
        print(
            f"     Zone 60–80%: [{zone_bottom:.5f}–{zone_top:.5f}] | "
            f"Retrace={retrace_pct * 100:.1f}% | in_poi={daily_in_poi} | "
            f"latched={poi_touch_latched} | {sniper_note}"
        )
        sys.stdout.flush()

        return TimeframeAnalysis(
            timeframe=timeframe_display,
            choch_detected=True,
            choch_direction=choch_direction,
            choch_time=choch_time_str,
            choch_price=choch_price,
            fvg_detected=True,
            fvg_top=zone_top,
            fvg_bottom=zone_bottom,
            fvg_entry=zone_entry,
            in_fvg=in_poi_entry,
            in_poi_entry_zone=in_poi_entry,
            retrace_pct=retrace_pct,
            distance_to_fvg_pips=distance_to_fvg_pips,
            status=status,
            equilibrium=eq_val,
            fvg_source=fvg_source,
            h4_sl_price=h4_sl_price,
            choch_bars_ago=_choch_bars_ago,
            bos_detected=_bos_detected_val,
            bos_direction=_bos_direction_val,
            bos_bars_ago=_bos_bars_ago_val,
            signal_type=signal_type,
        )

    def _v47_pick_structural_signal(
        self,
        aligned_chochs: list,
        aligned_bos: list,
        allow_bos_trigger: bool,
    ) -> tuple:
        """V47: CHoCH prioritar; BOS ca intrare 2 dacă allow_bos_trigger."""
        if aligned_chochs:
            return aligned_chochs[-1], 'CHoCH'
        if allow_bos_trigger and aligned_bos:
            return aligned_bos[-1], 'BOS'
        return None, None

    def analyze_timeframe(
        self,
        symbol: str,
        timeframe: str,
        required_direction: str,
        current_price: float,
        smc_detector: SMCDetector,
        allow_bos_trigger: bool = False,  # V30.1: True pt CONTINUATION 4H — BOS = trigger direct
        daily_in_poi: bool = False,  # V46: preț/wick Daily în POI box
        poi_touch_latched: bool = False,  # V49: touch POI anterior — entry secvențial
        poi_first_touch_time: Optional[str] = None,  # V50: ancoră post-POI pentru selecție structurală
    ) -> TimeframeAnalysis:
        """
        Analyze a specific timeframe for CHoCH and FVG
        
        Args:
            symbol: Trading pair
            timeframe: "H1" or "H4"
            required_direction: "bullish" or "bearish"
            current_price: Current market price
            smc_detector: SMC detector with appropriate ATR threshold
        
        Returns:
            TimeframeAnalysis with CHoCH and FVG details
        """
        timeframe_display = "1H" if timeframe == "H1" else "4H"
        
        # V19 FIX #3: Extindere orizont vizual
        # 1H: 400 bare = ~16 zile → CHoCH < 10h acoperit
        # 4H: 300 bare = ~50 zile → CHoCH major Daily acoperit complet
        num_bars = 400 if timeframe == "H1" else 300
        
        # Download data
        df = self.get_historical_data(symbol, timeframe, num_bars)
        
        if df is None or df.empty:
            self._log_radar_warn(
                symbol,
                f"Fără date {timeframe_display} (lanț bare epuizat) — verifică port 8010 / "
                f"simbol {self._broker_symbol_candidates(symbol)}"
            )
            return TimeframeAnalysis(
                timeframe=timeframe_display,
                choch_detected=False,
                choch_direction=None,
                choch_time=None,
                choch_price=None,
                fvg_detected=False,
                fvg_top=None,
                fvg_bottom=None,
                fvg_entry=None,
                in_fvg=False,
                distance_to_fvg_pips=0.0,
                status=PullbackStatus.WAITING_1H_CHOCH if timeframe == "H1" else PullbackStatus.WAITING_4H_CHOCH
            )
        
        try:
            # Detect CHoCH and BOS
            choch_list, bos_list = smc_detector.detect_choch_and_bos(df)

            # ── V25.1: BOS RECENCY — calculat INDEPENDENT, ÎNAINTE de orice filtrare ────────────
            # MOTIVUL: CHoCH apare o singură dată (schimbare de caracter). Continuarea trendului
            # e confirmată de BOS-uri succesive. Lacătul 4H trebuie să accepte și BOS recent aliniat
            # chiar dacă CHoCH-ul original are >30 bare vechime (trend sănătos, nu trend stale).
            _all_aligned_bos_for_lock = sorted(
                [b for b in bos_list if b.direction == required_direction],
                key=lambda x: x.index
            )
            _bos_detected_val: bool = bool(_all_aligned_bos_for_lock)
            _bos_direction_val: Optional[str] = _all_aligned_bos_for_lock[-1].direction if _all_aligned_bos_for_lock else None
            _bos_bars_ago_val: int = (len(df) - _all_aligned_bos_for_lock[-1].index) if _all_aligned_bos_for_lock else 9999
            # ─────────────────────────────────────────────────────────────────────────────────────

            # V19.4 FIX #2: returnăm WAITING doar dacă AMBELE liste sunt goale.
            # Dacă există BOS valid în direcția biasului, cascade-ul trebuie să ruleze (PAS 2/4).
            if not choch_list and not bos_list:
                return TimeframeAnalysis(
                    timeframe=timeframe_display,
                    choch_detected=False,
                    choch_direction=None,
                    choch_time=None,
                    choch_price=None,
                    fvg_detected=False,
                    fvg_top=None,
                    fvg_bottom=None,
                    fvg_entry=None,
                    in_fvg=False,
                    distance_to_fvg_pips=0.0,
                    status=PullbackStatus.WAITING_1H_CHOCH if timeframe == "H1" else PullbackStatus.WAITING_4H_CHOCH
                )
            
            # ━━━ V24.1: ORGANIC STRUCTURAL ALIGNMENT — NO LOOKBACK WALL ━━━
            # V45: doar CHoCH aliniat; BOS fără CHoCH real → WAITING (PAS 2 eliminat).

            all_chochs_count = len(choch_list)
            aligned_chochs = sorted(
                [c for c in choch_list if c.direction == required_direction],
                key=lambda x: x.index
            )
            rejected_count = all_chochs_count - len(aligned_chochs)
            if rejected_count > 0:
                print(
                    f"  🚫 [{timeframe_display} DIRECTION GUARD] {symbol}: "
                    f"{rejected_count} CHoCH(uri) contrare ({required_direction.upper()} opus) — IGNORATE"
                )
                sys.stdout.flush()

            # V50: post-POI — doar structură DUPĂ primul touch POI Daily
            _poi_anchor = _parse_radar_dt(poi_first_touch_time)
            _aligned_before_poi = list(aligned_chochs)
            if _poi_anchor and (poi_touch_latched or daily_in_poi):
                _pre = len(aligned_chochs)
                aligned_chochs = _filter_structural_post_poi(
                    aligned_chochs, _poi_anchor, df,
                )
                _all_aligned_bos_for_lock = _filter_structural_post_poi(
                    _all_aligned_bos_for_lock, _poi_anchor, df,
                )
                _bos_detected_val = bool(_all_aligned_bos_for_lock)
                _bos_direction_val = (
                    _all_aligned_bos_for_lock[-1].direction if _all_aligned_bos_for_lock else None
                )
                _bos_bars_ago_val = (
                    (len(df) - _all_aligned_bos_for_lock[-1].index)
                    if _all_aligned_bos_for_lock else 9999
                )
                if _pre > len(aligned_chochs):
                    print(
                        f"  🛑 [{timeframe_display} V50 POST-POI] {symbol}: "
                        f"{_pre - len(aligned_chochs)} CHoCH(uri) pre-POI eliminate"
                    )
                    sys.stdout.flush()

            # V47: CHoCH prioritar; BOS valid ca intrare 2 (allow_bos_trigger)
            latest_structural, signal_type = self._v47_pick_structural_signal(
                aligned_chochs, _all_aligned_bos_for_lock, allow_bos_trigger,
            )
            if latest_structural is None:
                print(
                    f"  ⏳ [{timeframe_display} V47] {symbol}: Zero CHoCH/BOS "
                    f"{required_direction.upper()} — WAITING"
                )
                _log_choch_wait_diag(
                    symbol,
                    timeframe_display,
                    required_direction,
                    poi_first_touch_time,
                    _aligned_before_poi,
                    choch_list,
                    df,
                )
                sys.stdout.flush()
                return TimeframeAnalysis(
                    timeframe=timeframe_display,
                    choch_detected=False,
                    choch_direction=None,
                    choch_time=None,
                    choch_price=None,
                    fvg_detected=False,
                    fvg_top=None,
                    fvg_bottom=None,
                    fvg_entry=None,
                    in_fvg=False,
                    distance_to_fvg_pips=0.0,
                    status=PullbackStatus.WAITING_1H_CHOCH if timeframe == "H1" else PullbackStatus.WAITING_4H_CHOCH
                )

            latest_choch = latest_structural
            _choch_bars_ago = len(df) - latest_choch.index
            choch_direction = latest_choch.direction

            # V55: gate _is_structural_break_valid eliminat — V46/V53 gestionează retrace 60–80%.

            if signal_type == 'CHoCH':
                print(
                    f"  ✅ [{timeframe_display} V47 CHoCH] {symbol} | "
                    f"{required_direction.upper()} la -{_choch_bars_ago} bare"
                )
            else:
                print(
                    f"  ⚡ [{timeframe_display} V47 BOS] {symbol} | "
                    f"{required_direction.upper()} la -{_choch_bars_ago} bare (intrare 2)"
                )
            sys.stdout.flush()

            # ── V24.9 DIRECTION ASSERTION — guard final ──────────────────────
            # Paranoid check: dacă după toate filtrele choch_direction != required_direction
            # (nu ar trebui să se întâmple, dar dacă se întâmplă → WAITING forțat)
            if choch_direction != required_direction:
                print(f"  🚨 [{timeframe_display} DIRECTION ASSERT FAILED] {symbol}: "
                      f"CHoCH dir={choch_direction} != required={required_direction} — FORȚĂM WAITING")
                sys.stdout.flush()
                return TimeframeAnalysis(
                    timeframe=timeframe_display,
                    choch_detected=False,
                    choch_direction=None,
                    choch_time=None,
                    choch_price=None,
                    fvg_detected=False,
                    fvg_top=None,
                    fvg_bottom=None,
                    fvg_entry=None,
                    in_fvg=False,
                    distance_to_fvg_pips=0.0,
                    status=PullbackStatus.WAITING_1H_CHOCH if timeframe == "H1" else PullbackStatus.WAITING_4H_CHOCH,
                    choch_bars_ago=9999
                )
            choch_index = latest_choch.index
            choch_break_price = float(latest_choch.break_price)

            if signal_type == 'CHoCH':
                _bos_after_choch = [b for b in _all_aligned_bos_for_lock if b.index > choch_index]
            else:
                _bos_after_choch = []
            _bos_trigger_bars_ago = (
                len(df) - _bos_after_choch[-1].index if _bos_after_choch else 9999
            )
            
            # Get CHoCH details
            if choch_index < len(df):
                choch_time = df.iloc[choch_index]['time']
                choch_time_str = choch_time.isoformat() if hasattr(choch_time, 'isoformat') else str(choch_time)
                choch_price = df.iloc[choch_index]['close']
            else:
                choch_time_str = "Unknown"
                choch_price = None
            
            # V18.3: direction alignment este garantat — am filtrat deja pe required_direction
            # Blocul vechi de reject nu mai e necesar
            
            # ── V16.2: Calcul Equilibrium (50% EQ) din impulsul CHoCH ─────────
            # Utilizat în P/D Array validation la analiza setup-ului.
            # Stocat în setup ca radar_1h_eq / radar_4h_eq.
            choch_equilibrium = None
            try:
                _sbp = float(latest_choch.swing_broken.price)
                _cbp = float(latest_choch.break_price)
                choch_equilibrium = (_sbp + _cbp) / 2.0
                pip_size_eq = self._get_pip_size(symbol)
                _eq_str = f"{choch_equilibrium:.5f}" if choch_equilibrium is not None else "N/A"
                print(f"  📐 [V16.2 EQ] {timeframe_display} Impulse: {_sbp:.5f} → {_cbp:.5f} | "
                      f"EQ={_eq_str} ({abs(_cbp - _sbp)/pip_size_eq:.1f} pips)")
                sys.stdout.flush()
            except Exception as _eq_err:
                logger.warning(f"[V37.0] {symbol} {timeframe_display} equilibrium calc failed: {_eq_err}")

            # ── V31.0 STRUCTURAL SL: Swing Low/High de baza — nu swing_broken immediate ──
            # Bug #08/#13: swing_broken.price era prea aproape de entry (BOS micro-impuls = 3 pip SL)
            # V37.2: min 30 pips — fallback swing_broken interzis daca distanta < 30p
            h4_sl_price = None
            try:
                _sl_pip = self._get_pip_size(symbol)
                _sl_buffer = _sl_pip * 2  # V31.0: 2 pip spread buffer
                _min_sl_dist = _sl_pip * 30  # V37.2: acelasi floor ca executorul
                _max_sl_dist = get_max_sl_pips(symbol) * _sl_pip  # V42.6: XAU=30p, FX=40p
                _ref_px = float(current_price) if current_price else float(choch_break_price)
                if choch_direction == 'bullish':
                    _all_lows_sl = smc_detector.detect_swing_lows(df)
                    _in_range = [
                        s for s in _all_lows_sl
                        if s.price < _ref_px
                        and (_ref_px - s.price) >= _min_sl_dist
                        and (_ref_px - s.price) <= _max_sl_dist
                    ]
                    if _in_range:
                        _pick = max(_in_range, key=lambda s: s.index)  # ultimul pivot 4H
                        h4_sl_price = float(_pick.price) - _sl_buffer
                else:
                    _all_highs_sl = smc_detector.detect_swing_highs(df)
                    _in_range = [
                        s for s in _all_highs_sl
                        if s.price > _ref_px
                        and (s.price - _ref_px) >= _min_sl_dist
                        and (s.price - _ref_px) <= _max_sl_dist
                    ]
                    if _in_range:
                        _pick = max(_in_range, key=lambda s: s.index)  # ultimul pivot 4H
                        h4_sl_price = float(_pick.price) + _sl_buffer
                if h4_sl_price is not None:
                    _sl_dist_pips = abs(_ref_px - h4_sl_price) / _sl_pip
                    if _sl_dist_pips < 30:
                        print(f"  ⚠️  [V37.2 MIN SL] {timeframe_display} {symbol}: "
                              f"SL {_sl_dist_pips:.1f}p < 30p — nu scriem h4_sl in JSON")
                        h4_sl_price = None
                    elif _sl_dist_pips > get_max_sl_pips(symbol):
                        print(f"  ⚠️  [V42.6 MAX SL] {timeframe_display} {symbol}: "
                              f"SL {_sl_dist_pips:.1f}p > {get_max_sl_pips(symbol):.0f}p — skip h4_sl")
                        h4_sl_price = None
                if h4_sl_price:
                    _sl_pips_log = abs(choch_break_price - h4_sl_price) / _sl_pip
                    print(f"  🛡️  [V31.0 STRUCT SL] {timeframe_display} base={h4_sl_price:.5f} "
                          f"({_sl_pips_log:.1f}p de la CHoCH break | dir={choch_direction})")
                sys.stdout.flush()
            except Exception as _sl_err:
                print(f"  ⚠️ [V31.0 SL] Eroare calcul structural SL: {_sl_err}")
                sys.stdout.flush()

            # Detect FVG created by CHoCH
            # detect_fvg() returns a single FVG object or None (not a list)
            # V19.2 FIX 1: wrap in try/except — smc_detector.detect_fvg() poate crapa cu
            # ValueError/f-string crash intern. Prinsă eroarea → forțăm Fibo Fallback.
            latest_fvg = None
            try:
                latest_fvg = smc_detector.detect_fvg(
                    df,
                    latest_choch if signal_type == 'CHoCH' else None,
                )
            except Exception as fvg_err:
                print(f"  ⚠️ [PATCH RADAR] detect_fvg structural crash caught: {fvg_err}")
                print(f"  ⚠️ [PATCH RADAR] Forcing V15.4 Fibo Fallback.")
                sys.stdout.flush()
                latest_fvg = None

            # V37.1: Respinge FVG cu OHLC corupt (tick aberrant / scala gresita)
            if latest_fvg and not self._fvg_prices_sane(
                current_price, latest_fvg.top, latest_fvg.bottom
            ):
                _radar_out(
                    f"  [!] [V37.1 FVG GUARD] {symbol} {timeframe_display}: "
                    f"FVG [{latest_fvg.bottom:.5f}-{latest_fvg.top:.5f}] vs pret {current_price:.5f} "
                    f"= date corupte, folosim Fibo Fallback"
                )
                logger.warning(
                    f"{symbol} {timeframe_display} FVG rejected: "
                    f"[{latest_fvg.bottom}-{latest_fvg.top}] vs price {current_price}"
                )
                latest_fvg = None
            
            return self._build_v46_choch_entry_analysis(
                symbol=symbol,
                timeframe=timeframe,
                timeframe_display=timeframe_display,
                required_direction=required_direction,
                current_price=current_price,
                latest_choch=latest_choch,
                choch_direction=choch_direction,
                choch_time_str=choch_time_str,
                choch_price=choch_price,
                choch_break_price=choch_break_price,
                choch_equilibrium=choch_equilibrium,
                h4_sl_price=h4_sl_price,
                _choch_bars_ago=_choch_bars_ago,
                _bos_detected_val=_bos_detected_val,
                _bos_direction_val=_bos_direction_val,
                _bos_bars_ago_val=_bos_bars_ago_val,
                _bos_trigger_bars_ago=_bos_trigger_bars_ago,
                daily_in_poi=daily_in_poi,
                poi_touch_latched=poi_touch_latched,
                latest_fvg=latest_fvg,
                signal_type=signal_type,
            )
        
        except Exception as e:
            import traceback
            print(f"⚠️  Error analyzing {timeframe} for {symbol}: {e}")
            traceback.print_exc()
            sys.stdout.flush()
            # V19.4 FIX #3: scan_error=True propagat în JSON → Executor nu va folosi date corupte
            # Valorile FVG anterioare valabile din JSON sunt PĂSTRATE (nu suprascrise cu None)
            return TimeframeAnalysis(
                timeframe=timeframe_display,
                choch_detected=False,
                choch_direction=None,
                choch_time=None,
                choch_price=None,
                fvg_detected=False,
                fvg_top=None,
                fvg_bottom=None,
                fvg_entry=None,
                in_fvg=False,
                distance_to_fvg_pips=0.0,
                status=PullbackStatus.WAITING_1H_CHOCH if timeframe == "H1" else PullbackStatus.WAITING_4H_CHOCH,
                scan_error=True,
                scan_error_msg=str(e)
            )
    
    def analyze_setup(self, setup_data: Dict, save_to_json: bool = True) -> MultiTFResult:
        """
        Complete multi-timeframe analysis of a setup
        
        Scans both 1H and 4H for CHoCH and FVG
        
        Args:
            setup_data: Setup dict from monitoring_setups.json
            save_to_json: If True, write radar results back to monitoring_setups.json
        """
        symbol = setup_data.get('symbol', 'UNKNOWN')
        self._last_skip_reason = None

        # V43.2 E3-T2: structural_breach → purge imediat, fără scan LTF
        if (
            setup_data.get('structural_breach')
            and not setup_data.get('entry1_filled')
            and setup_data.get('status') not in ('TRADE_OPEN', 'PARTIAL_OPEN')
        ):
            _radar_out(
                f"[🛰️ RADAR PURGE] Setup invalidat structural eliminat definitiv din JSON."
            )
            _radar_out(
                f"  [🛰️ RADAR PURGE] {symbol}: structural_breach=True — scan LTF oprit"
            )
            try:
                all_setups = self.load_monitoring_setups()
                survivors = [
                    s for s in all_setups
                    if not (
                        isinstance(s, dict)
                        and s.get('symbol') == symbol
                        and not s.get('entry1_filled')
                        and s.get('status') not in ('TRADE_OPEN', 'PARTIAL_OPEN')
                        and s.get('structural_breach')
                    )
                ]
                if len(survivors) < len(all_setups):
                    self._write_monitoring_setups(survivors)
            except Exception as _purge_err:
                logger.error(f"[V43.2 PURGE] {symbol}: {_purge_err}")
            self._last_skip_reason = 'structural_breach — setup eliminat din JSON'
            return None

        # ── V25.0 DIRECTION GUARD: ZERO toleranță pentru direcție lipsă sau ambiguuă ──────────
        # BUG PRE-V25.0: default='SHORT' — dacă câmpul 'direction' lipsea din JSON,
        # Radarul scăna silențios CHoCH Bearish pentru un setup care era BUY.
        # FIX: dacă direction e absent sau nerecunoscut → SKIP complet cu log CRITICAL.
        # Nici un trade nu se execută fără direcție explicită confirmată.
        _raw_direction = setup_data.get('direction', '').strip().upper()
        if not _raw_direction:
            self._last_skip_reason = "Câmpul 'direction' ABSENT din monitoring_setups.json"
            logger.critical(
                f"🚨 [V25.0 DIRECTION MISSING] {symbol}: {self._last_skip_reason}. "
                f"Setup SKIPPED — Radarul NU ghicește direcția!"
            )
            self._log_radar_skip(symbol, self._last_skip_reason)
            return None
        # Normalizăm: BUY → LONG, SELL → SHORT (compatibilitate cu scanner)
        if _raw_direction in ('BUY', 'LONG'):
            direction = 'LONG'
        elif _raw_direction in ('SELL', 'SHORT'):
            direction = 'SHORT'
        else:
            self._last_skip_reason = f"Valoare direction invalidă: '{_raw_direction}'"
            logger.critical(
                f"🚨 [V25.0 DIRECTION INVALID] {symbol}: {self._last_skip_reason}. "
                f"Valori valide: BUY, SELL, LONG, SHORT."
            )
            self._log_radar_skip(symbol, self._last_skip_reason)
            return None
        
        # Get Daily data
        # V30.2: Guard None — entry_price/fvg_top/fvg_bottom pot fi null in JSON
        # (setups salvate cu OB else-branch vechi sau WAITING_D1_PULLBACK fara h4_signal)
        # float(None) crasheaza cu TypeError → 12 errors per scan. Fix: fallback explicit la 0.
        _ep = setup_data.get('entry_price')
        daily_entry = float(_ep) if _ep is not None else 0.0
        # V31.0: poi_top/poi_bottom sunt câmpurile noi din Scanner V31.0 — backward compat cu fvg_top/fvg_bottom
        _ft = setup_data.get('poi_top') or setup_data.get('fvg_top')
        daily_fvg_top = float(_ft) if _ft is not None else daily_entry
        _fb = setup_data.get('poi_bottom') or setup_data.get('fvg_bottom')
        daily_fvg_bottom = float(_fb) if _fb is not None else daily_entry
        # V24.6 PERMISSIVE DAILY FLOW: Setup cu FVG sintetic (zona Equilibrium) — niciun FVG corp natural
        # Radarul 4H TREBUIE să găsească un CHoCH real înainte de EXECUTE_NOW
        _daily_bias_active = bool(setup_data.get('daily_bias_active', False))
        # V19.4 FIX #4: prețul live este IMPERATIV — nu existe fallback silențios la daily_entry.
        # Dacă portul 8010 nu răspunde → RuntimeError explicit, prins de run_scan cu `continue`.
        current_price = self.get_current_price(symbol)
        if current_price is None:
            self._last_skip_reason = (
                f"Preț live indisponibil — port 8010 / simbol broker "
                f"{self._broker_symbol_candidates(symbol)}"
            )
            self._log_radar_skip(symbol, self._last_skip_reason)
            raise RuntimeError(
                f"Preț indisponibil pentru {symbol} — portul 8010 nu răspunde. "
                f"Verifică MarketDataProvider cBot pe VPS."
            )

        required_direction = 'bullish' if direction == 'LONG' else 'bearish'

        _d1_wick_high = None
        _d1_wick_low = None
        _d1_touch_time = None
        _df_d1_touch = None
        _df_h4_touch = None
        try:
            _df_d1_touch = self.get_historical_data(symbol, "D1", 60)
            if _df_d1_touch is not None and not _df_d1_touch.empty:
                _d1_wick_high = float(_df_d1_touch['high'].iloc[-1])
                _d1_wick_low = float(_df_d1_touch['low'].iloc[-1])
                _d1_touch_time = _d1_bar_open_iso(_df_d1_touch)
            _df_h4_touch = self.get_historical_data(symbol, "H4", 300)
        except Exception as _wick_err:
            logger.warning(f"[V52] {symbol}: D1/H4 wick fetch failed — POI touch anchor degraded: {_wick_err}")

        # V45: wick Daily ∩ POI → pândă radar; P/D = filtru execuție, nu gate scan
        _v43_zone = _evaluate_v43_daily_zone(
            setup_data, direction, current_price, daily_fvg_bottom, daily_fvg_top,
            d1_wick_high=_d1_wick_high, d1_wick_low=_d1_wick_low,
        )
        daily_zone_validated = _v43_zone['validated']
        _track_mitigation_touch(
            setup_data, _v43_zone, d1_touch_time=_d1_touch_time,
            df_d1=_df_d1_touch, df_h4=_df_h4_touch,
            poi_bottom=daily_fvg_bottom, poi_top=daily_fvg_top,
        )
        # V47.1: scan LTF cât timp panda e latched (inclusiv după ieșirea din POI la respingere)
        _poi_scan_active = bool(daily_zone_validated or setup_data.get('radar_panda_active'))
        _allow_bos_4h = bool(_poi_scan_active)

        print(f"\n{'='*80}")
        print(f"🔍 [{symbol}] Bias Daily: {direction} | Scanare structurală 4H+1H (V43.2 POI Gate)...")
        if _daily_bias_active:
            print(f"⚠️  [V24.6 DAILY BIAS] {symbol}: FVG sintetic (Equilibrium) — EXECUTE_NOW blocat până la CHoCH 4H real!")
        print(f"{'='*80}")
        print(f"💰 Current Price: {current_price:.5f}")
        print(f"📊 Daily POI: [{daily_fvg_bottom:.5f} - {daily_fvg_top:.5f}]")
        if _poi_scan_active:
            if daily_zone_validated:
                _radar_out(
                    f"[🛰️ RADAR ALLOW] Preț în POI (Premium/Discount). Se vânează CHoCH."
                )
                _radar_out(
                    f"  [🛰️ RADAR ALLOW] {symbol}: {_v43_zone['reason']}"
                )
            else:
                _radar_out(
                    f"[🛰️ V47.1 POI LATCH] {symbol}: panda activ post-touch — "
                    f"scan 4H/1H continuă ({_v43_zone['reason']})"
                )
        else:
            print(f"⏳ [V43.2 POI GATE] ÎNCHISĂ — {_v43_zone['reason']}")
            print(f"  LTF CHoCH ignorat până la touch POI + zonă instituțională ADR corectă")
        sys.stdout.flush()

        if _poi_scan_active:
            _daily_in_poi = bool(_v43_zone.get('in_poi', False))
            _poi_latched = bool(setup_data.get('poi_touch_latched'))
            _poi_touch_ts = setup_data.get('poi_first_touch_time')
            # Analyze 1H — doar în POI validat
            print("\n🔎 [1H] SNIPER SCAN (ATR 0.8x)...")
            sys.stdout.flush()
            _h1_bars = 400
            tf_1h = self.analyze_timeframe(
                symbol=symbol,
                timeframe="H1",
                required_direction=required_direction,
                current_price=current_price,
                smc_detector=self.smc_1h,
                daily_in_poi=_daily_in_poi,
                poi_touch_latched=_poi_latched,
                poi_first_touch_time=_poi_touch_ts,
            )
            self._log_scan_done(symbol, tf_1h, _h1_bars)

            # Analyze 4H — doar în POI validat
            print("\n🔎 [4H] HIGH CONFIDENCE SCAN (ATR 1.0x — V15.4)...")
            if _allow_bos_4h:
                print(f"  ⚡ [V30.1 CONTINUATION] {symbol}: allow_bos=True — 4H BOS in directie {required_direction.upper()} = trigger echivalent CHoCH")
            sys.stdout.flush()
            _h4_bars = 300
            tf_4h = self.analyze_timeframe(
                symbol=symbol,
                timeframe="H4",
                required_direction=required_direction,
                current_price=current_price,
                smc_detector=self.smc_4h,
                allow_bos_trigger=_allow_bos_4h,  # V30.1
                daily_in_poi=_daily_in_poi,
                poi_touch_latched=_poi_latched,
                poi_first_touch_time=_poi_touch_ts,
            )
            self._log_scan_done(symbol, tf_4h, _h4_bars)

            _track_mitigation_touch(
                setup_data, _v43_zone, tf_4h, d1_touch_time=_d1_touch_time,
                df_d1=_df_d1_touch, df_h4=_df_h4_touch,
                poi_bottom=daily_fvg_bottom, poi_top=daily_fvg_top,
            )
            tf_1h, _h1_stale = _apply_h1_chronology_guard(
                symbol, setup_data, tf_4h, tf_1h, _poi_scan_active,
            )
        else:
            tf_1h = _empty_tf_waiting("H1")
            tf_4h = _empty_tf_waiting("H4")
            _h1_stale = False

        # V43.2: P/D guard aliniat la validarea ADR (înlocuiește D1 midpoint când ADR disponibil)
        _poi_sequential = bool(
            setup_data.get('poi_touch_latched') or setup_data.get('radar_panda_active')
        )
        if _v43_zone.get('equilibrium') is not None:
            _pd = {'passed': True, 'reason': '', 'skipped': False}
        else:
            _pd = self._evaluate_pd_guard(symbol, required_direction, current_price)
        _pd_guard_passed, _pd_guard_reason = _compute_pd_guard_for_execute(
            _v43_zone, _pd, daily_zone_validated, _poi_sequential,
        )

        # ━━━ V19.5: Determină execution_ready — FĂRĂ nicio poartă Daily ━━━
        # Radarul validează EXCLUSIV alinierea fractală 4H/1H cu biasul Daily.
        # Invalidarea pe SL = responsabilitatea EXCLUSIVĂ a Executorului.
        execution_ready = False
        priority_timeframe = None
        verdict = "👀 MONITORING BOTH TIMEFRAMES"

        # V43.2 E3-T4: 4H prioritar; 1H Entry doar dacă 4H deja aliniat în POI validat
        _4h_aligned = self._is_4h_aligned_for_1h_entry(tf_4h, required_direction, _allow_bos_4h)

        if tf_4h.status == PullbackStatus.EXECUTE_NOW_4H or tf_4h.in_poi_entry_zone:
            execution_ready = True
            priority_timeframe = "4H"
            verdict = "🔥 EXECUTE NOW (4H POI + Premium/Discount 60–80%!)"
        elif tf_1h.status == PullbackStatus.EXECUTE_NOW_1H:
            if _4h_aligned:
                execution_ready = True
                priority_timeframe = "1H"
                verdict = "🔥 EXECUTE NOW (1H SNIPER ENTRY!)"
            else:
                verdict = "⏳ WAITING 4H ALIGNMENT — 1H trigger blocat până la CHoCH/BOS 4H"
                print(
                    f"  ⏳ [V43.2 H1 GATE] {symbol}: 1H EXECUTE blocat — "
                    f"4H nealiniat în POI validat"
                )
                sys.stdout.flush()
        elif tf_1h.choch_detected and tf_1h.fvg_detected:
            verdict = f"⏳ WAITING FOR 1H PULLBACK ({tf_1h.distance_to_fvg_pips:.1f} pips away)"
        elif tf_4h.choch_detected and tf_4h.fvg_detected:
            verdict = f"⏳ WAITING FOR 4H PULLBACK ({tf_4h.distance_to_fvg_pips:.1f} pips away)"
        elif tf_1h.choch_detected or tf_4h.choch_detected:
            verdict = "👀 CHoCH DETECTED - Waiting for FVG formation"
        else:
            verdict = "👀 WAITING FOR 1H/4H CHoCH"

        # V43.2: P/D + POI gate — blocăm EXECUTE dacă zona Daily nu e validată
        if not _pd_guard_passed and _pd_guard_reason and daily_zone_validated is False:
            if execution_ready:
                execution_ready = False
                priority_timeframe = None
            verdict = f"⏳ POI/P-D WAIT — {_pd_guard_reason}"
            print(f"  ⏳ [V43.2 POI BLOCK EXECUTE] {symbol}: {_pd_guard_reason}")
            sys.stdout.flush()
        elif not _pd_guard_passed and _pd_guard_reason:
            _had_execute_trigger = execution_ready
            if execution_ready:
                execution_ready = False
                priority_timeframe = None
            _wait_zone = 'Premium' if required_direction == 'bearish' else 'Discount'
            verdict = f"⏳ P/D WAIT — H4/H1 monitorizate, așteptăm {_wait_zone}"
            print(f"  ⏳ [V36.5 P/D BLOCK EXECUTE] {symbol}: {_pd_guard_reason} — "
                  f"EXECUTE blocat")
            sys.stdout.flush()
            if _had_execute_trigger and (tf_4h.choch_detected or tf_1h.choch_detected):
                try:
                    from telegram_notifier import TelegramNotifier
                    TelegramNotifier().send_execute_now_blocked_alert(
                        symbol,
                        setup_data.get('direction', '?'),
                        f"[Radar P/D] {_pd_guard_reason}",
                    )
                except Exception as _pd_tg_err:
                    logger.warning(f"[V52] P/D block Telegram failed {symbol}: {_pd_tg_err}")

        _poi_entry_gate = daily_zone_validated or bool(setup_data.get('poi_touch_latched'))
        if execution_ready and not _poi_entry_gate:
            execution_ready = False
            priority_timeframe = None
            _wait_zone = 'Premium' if required_direction == 'bullish' else 'Discount'
            verdict = f"⏳ POI WAIT — preț în {_wait_zone}, așteptăm pullback Daily"
            print(f"  ⏳ [V42.7 POI BLOCK EXECUTE] {symbol}: {current_price:.5f} vs POI "
                  f"[{daily_fvg_bottom:.5f}–{daily_fvg_top:.5f}] — EXECUTE blocat")
            sys.stdout.flush()

        # ━━━ V24.6 DAILY BIAS GUARD: Setup cu FVG sintetic ━━━━━━━━━━━━━━━━━━━━━━━━
        # Dacă setup-ul vine din scanarea permisivă (fără FVG corp Daily natural),
        # EXECUTE_NOW este permis NUMAI dacă 4H a detectat un CHoCH real (nu BOS-ca-CHoCH).
        # Aceasta este REGULA DE AUR: Scanner = Bias, Radar = Arbitrul final.
        if _daily_bias_active and execution_ready:
            # Verificăm că avem un CHoCH 4H real (tf_4h.choch_detected = True din CHoCH real)
            # BOS-ul sintetic nu garantează confluență suficientă pe zona sintetică
            if not tf_4h.choch_detected:
                execution_ready = False
                priority_timeframe = None
                verdict = f"⚠️ [V24.6 DAILY BIAS] EXECUTE blocat: FVG sintetic necesită CHoCH 4H real (nu BOS)"
                print(f"  🛡️ [V24.6 DAILY BIAS GUARD] {symbol}: EXECUTE_NOW blocat — zona Equilibrium sintetic\u0103 fara CHoCH 4H confirmat")
            else:
                print(f"  ✅ [V24.6 DAILY BIAS UNLOCK] {symbol}: CHoCH 4H real detectat — EXECUTE_NOW autorizat pe zona Equilibrium")
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        result = MultiTFResult(
            symbol=symbol,
            direction=direction,
            daily_zone_validated=daily_zone_validated,
            daily_fvg_top=daily_fvg_top,
            daily_fvg_bottom=daily_fvg_bottom,
            daily_entry=daily_entry,
            current_price=current_price,
            tf_1h=tf_1h,
            tf_4h=tf_4h,
            execution_ready=execution_ready,
            verdict=verdict,
            priority_timeframe=priority_timeframe,
            pd_guard_passed=_pd_guard_passed,
            pd_guard_reason=_pd_guard_reason,
            h1_choch_stale=_h1_stale,
            poi_first_touch_time=setup_data.get('poi_first_touch_time'),
        )
        
        # 🔥 V8.3 SYNC: Write radar results to monitoring_setups.json
        if save_to_json:
            self._batch_sync_to_monitoring_setups([(setup_data, result)])
        
        return result

    def _evaluate_confirmed_pullback_latch(self, setup: dict, result: 'MultiTFResult') -> Optional[str]:
        """
        V46: Latch safety net — POI + Premium/Discount 60–80% fără gate ≤3 bare.
        Returns: '1H' | '4H' | None
        """
        if setup.get('status') == 'TRADE_OPEN':
            return None
        pending = None
        if setup.get('entry1_filled'):
            pending = setup.get('multi_entry_pending')
            if pending is None:
                plan = setup.get('multi_entry_plan') or ['1H', '4H']
                filled = [x.upper() for x in (setup.get('entries_filled_tfs') or [])]
                if not filled:
                    filled = [(setup.get('entry1_trigger_tf') or '1H').upper()]
                pending = [p for p in plan if p.upper() not in filled]
            else:
                pending = [p.upper() for p in pending]
            if not pending:
                return None
        if not result.pd_guard_passed:
            return None
        if not result.daily_zone_validated and not setup.get('poi_touch_latched'):
            return None

        setup_type = setup.get('setup_type', setup.get('strategy_type', 'reversal')).upper()
        is_reversal = 'REVERSAL' in setup_type
        allow_bos = bool(setup.get('radar_panda_active'))  # V47: BOS valid în panda
        macro_dir = 'bullish' if result.direction == 'LONG' else 'bearish'

        for tf_name, tf_data in (('1H', result.tf_1h), ('4H', result.tf_4h)):
            if tf_name == '1H' and not self._is_4h_aligned_for_1h_entry(
                result.tf_4h, macro_dir, allow_bos,
            ):
                continue
            if pending is not None and tf_name.upper() not in pending:
                continue
            if not tf_data.in_poi_entry_zone:
                continue
            if is_reversal:
                if not tf_data.choch_detected:
                    continue
            elif not (tf_data.choch_detected or tf_data.bos_detected):
                continue
            return tf_name
        return None

    def _rr_shield_blocks_execute(self, setup: dict, result: 'MultiTFResult',
                                  exec_tf_data=None) -> bool:
        """V37.7: Blocheaza EXECUTE_NOW daca RR entry→TP vs SL < 2.0."""
        _rr_entry = (
            setup.get('radar_4h_fvg_entry') or setup.get('radar_1h_fvg_entry')
            or setup.get('entry_price') or result.current_price
        )
        _rr_tp = setup.get('daily_tp_price') or setup.get('daily_target_price')
        _rr_sl = (
            (getattr(exec_tf_data, 'h4_sl_price', None) if exec_tf_data else None)
            or setup.get('h4_sl_price') or setup.get('stop_loss')
        )
        _pip_rr = self._get_pip_size(result.symbol)
        if not (_rr_tp and _rr_sl and _rr_entry):
            return False
        try:
            _rr_entry_f = float(_rr_entry)
            _rr_dist_tp = abs(float(_rr_tp) - _rr_entry_f)
            _rr_dist_sl = abs(_rr_entry_f - float(_rr_sl))
            if _rr_dist_sl <= 0:
                return False
            _rr_val = _rr_dist_tp / _rr_dist_sl
            if _rr_val < 2.0:
                logger.warning(
                    f"[V37.7 RR SHIELD] {result.symbol}: EXECUTE BLOCAT — "
                    f"RR={_rr_val:.2f} < 2.0 "
                    f"(TP dist={_rr_dist_tp/_pip_rr:.0f}p, SL dist={_rr_dist_sl/_pip_rr:.0f}p) — "
                    f"TP prea aproape / lichiditate deja atinsa"
                )
                print(f"  ⛔ [RADAR SKIP EXECUTE] {result.symbol}: RR Shield RR={_rr_val:.2f}<2.0")
                sys.stdout.flush()
                return True
            logger.info(f"[V37.7 RR SHIELD] {result.symbol}: RR={_rr_val:.2f} >= 2.0 OK")
        except Exception as _rr_err:
            logger.warning(
                f"[V37.7 RR SHIELD] {result.symbol}: calcul RR eșuat ({_rr_err}) — EXECUTE BLOCAT (fail-closed)"
            )
            return True
        return False

    _EXECUTE_NOW_FLUSH_KEYS = (
        'EXECUTE_NOW', 'execute_now_trigger_tf', 'execute_now_alert_sent',
        'execute_now_alert_key', 'radar_execution_ready', 'radar_verdict', 'h4_structure_locked',
    )
    _CHOCH_ALERT_FLUSH_KEYS = (
        'h4_choch_alert_sent', 'h4_bos_alert_sent', 'h1_choch_alert_sent', 'choch_1h_price',
        'h4_structure_locked_at', 'radar_1h_choch_stale',
        'poi_first_touch_time', 'h4_fvg_first_touch_time',
        'radar_panda_active', 'poi_radar_armed_at', 'poi_touch_latched', 'radar_4h_signal_type',
    )

    @staticmethod
    def _execute_now_alert_key(setup: dict) -> str:
        """Cheie dedup: o singura alerta Telegram per setup (supravietuieste restart + FVG flicker)."""
        sym = setup.get('symbol', '?')
        direction = str(setup.get('direction', '')).upper()
        setup_time = setup.get('setup_time') or setup.get('created_at') or ''
        return f"{sym}_{direction}_{setup_time}"

    def _hydrate_execute_now_dedup(self, setups: list) -> None:
        """V37.9: Reincarca dedup din JSON la startup — fara re-alert dupa restart."""
        for s in setups:
            if not isinstance(s, dict):
                continue
            if s.get('execute_now_alert_sent'):
                self._execute_now_alert_keys.add(
                    s.get('execute_now_alert_key') or self._execute_now_alert_key(s)
                )

    def _clear_execute_now_only(self, setup: dict, reason: str = '') -> None:
        """V37.9: Dezarmeaza EXECUTE_NOW — pastreaza execute_now_alert_sent (fara spam Telegram)."""
        sym = setup.get('symbol', '?')
        setup['EXECUTE_NOW'] = False
        setup.pop('execute_now_trigger_tf', None)
        if reason:
            logger.info(f"[V37.9] {sym}: EXECUTE_NOW dezarmat — {reason} (alerta Telegram pastrata)")

    def _v423_macro_bias(self, setup: dict, result: 'MultiTFResult') -> str:
        d = (setup.get('direction') or '').lower()
        if d in ('buy', 'long', 'bullish'):
            return 'bullish'
        if d in ('sell', 'short', 'bearish'):
            return 'bearish'
        return 'bullish' if result.direction == 'LONG' else 'bearish'

    def _v423_ltf_misalignment(self, setup: dict, result: 'MultiTFResult') -> tuple:
        """Returnează (macro_bias, listă de (tf, dir_choch) nealiniate)."""
        macro = self._v423_macro_bias(setup, result)
        issues = []
        if result.tf_4h.choch_detected and result.tf_4h.choch_direction != macro:
            issues.append(('4H', result.tf_4h.choch_direction))
        if result.tf_1h.choch_detected and result.tf_1h.choch_direction != macro:
            issues.append(('1H', result.tf_1h.choch_direction))
        return macro, issues

    def _v423_force_disarm_execute_now(
        self, setup: dict, result: 'MultiTFResult', reason_detail: str = '',
    ) -> None:
        """V42.3: Dezarmare instantanee EXECUTE_NOW în JSON când LTF ≠ D1 (atomic flush)."""
        if setup.get('status') == 'TRADE_OPEN':
            return
        sym = setup.get('symbol', '?')
        had_signal = setup.get('EXECUTE_NOW') is True
        setup['EXECUTE_NOW'] = False
        setup.pop('execute_now_trigger_tf', None)
        setup['radar_execution_ready'] = False
        h4_dir = setup.get('radar_4h_choch_direction') or result.tf_4h.choch_direction
        logger.warning(
            f"[⚠️ V42.3 ALINIERE] Execuție blocată pentru {sym}. "
            f"Lipsă sincron (D1: {setup.get('direction')} vs LTF: {h4_dir})"
            + (f" — {reason_detail}" if reason_detail else '')
        )
        if had_signal or reason_detail:
            self._flush_execute_now_to_json(setup)

    def _clear_execute_now_signal(self, setup: dict, reason: str = '') -> None:
        """V37.9: Curata complet semnalul — doar dupa fill sau setup nou/expirat."""
        sym = setup.get('symbol', '?')
        _alert_key = setup.get('execute_now_alert_key') or self._execute_now_alert_key(setup)
        self._execute_now_alert_keys.discard(_alert_key)
        setup.pop('EXECUTE_NOW', None)
        setup.pop('execute_now_trigger_tf', None)
        setup.pop('execute_now_alert_sent', None)
        setup.pop('execute_now_alert_key', None)
        if reason:
            logger.info(f"[V37.9] {sym}: EXECUTE_NOW + alert dedup cleared — {reason}")

    def _flush_execute_now_to_json(self, setup: dict) -> None:
        """V37.6: Scrie EXECUTE_NOW instant in JSON — executorul nu asteapta batch sync."""
        import os as _flush_os
        try:
            import numpy as _np

            def _json_safe(obj):
                if isinstance(obj, (_np.bool_,)):
                    return bool(obj)
                if isinstance(obj, (_np.integer,)):
                    return int(obj)
                if isinstance(obj, (_np.floating,)):
                    return float(obj)
                if isinstance(obj, (_np.ndarray,)):
                    return obj.tolist()
                raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

            with open(_MONITORING_FILE, 'r', encoding='utf-8') as _f:
                data = json.load(_f)
            setups = data.get('setups', data) if isinstance(data, dict) else data

            sym = setup.get('symbol')
            setup_dir = setup.get('direction', '').upper()
            matched = False
            for i, s in enumerate(setups):
                s_dir = s.get('direction', '').upper()
                dir_ok = (
                    s.get('symbol') == sym
                    and (
                        setup_dir == s_dir
                        or (setup_dir in ('SELL', 'SHORT') and s_dir in ('SELL', 'SHORT'))
                        or (setup_dir in ('BUY', 'LONG') and s_dir in ('BUY', 'LONG'))
                    )
                )
                if not dir_ok:
                    continue
                for key in self._EXECUTE_NOW_FLUSH_KEYS:
                    if key in setup:
                        setups[i][key] = setup[key]
                    elif key in setups[i] and key in ('EXECUTE_NOW', 'execute_now_trigger_tf'):
                        # V37.9: execute_now_alert_sent/key NU se sterg niciodata la flush —
                        # doar _clear_execute_now_signal() (entry1_filled / setup nou).
                        setups[i].pop(key, None)
                matched = True
                break

            if not matched:
                return

            if isinstance(data, dict):
                data['setups'] = setups
                data['last_updated'] = datetime.now().isoformat()
            else:
                data = setups

            tmp_path = _MONITORING_TMP
            with open(tmp_path, 'w', encoding='utf-8') as _wf:
                json.dump(data, _wf, indent=2, default=_json_safe)
            _flush_os.replace(tmp_path, _MONITORING_FILE)
            logger.debug(f"[V37.6 FLUSH] {sym}: EXECUTE_NOW scris instant in JSON")
        except Exception as _flush_err:
            logger.warning(f"[V37.6 FLUSH] {setup.get('symbol', '?')}: flush esuat ({_flush_err})")

    def _flush_choch_alerts_to_json(self, setup: dict) -> None:
        """Persist CHoCH alert dedup keys instantly — survives restart without re-alert."""
        import os as _flush_os
        try:
            import numpy as _np

            def _json_safe(obj):
                if isinstance(obj, (_np.bool_,)):
                    return bool(obj)
                if isinstance(obj, (_np.integer,)):
                    return int(obj)
                if isinstance(obj, (_np.floating,)):
                    return float(obj)
                if isinstance(obj, (_np.ndarray,)):
                    return obj.tolist()
                raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

            with open(_MONITORING_FILE, 'r', encoding='utf-8') as _f:
                data = json.load(_f)
            setups = data.get('setups', data) if isinstance(data, dict) else data

            sym = setup.get('symbol')
            setup_dir = setup.get('direction', '').upper()
            matched = False
            for i, s in enumerate(setups):
                s_dir = s.get('direction', '').upper()
                dir_ok = (
                    s.get('symbol') == sym
                    and (
                        setup_dir == s_dir
                        or (setup_dir in ('SELL', 'SHORT') and s_dir in ('SELL', 'SHORT'))
                        or (setup_dir in ('BUY', 'LONG') and s_dir in ('BUY', 'LONG'))
                    )
                )
                if not dir_ok:
                    continue
                for key in self._CHOCH_ALERT_FLUSH_KEYS:
                    if key in setup:
                        setups[i][key] = setup[key]
                matched = True
                break

            if not matched:
                return

            if isinstance(data, dict):
                data['setups'] = setups
                data['last_updated'] = datetime.now().isoformat()
            else:
                data = setups

            tmp_path = _MONITORING_TMP
            with open(tmp_path, 'w', encoding='utf-8') as _wf:
                json.dump(data, _wf, indent=2, default=_json_safe)
            _flush_os.replace(tmp_path, _MONITORING_FILE)
            logger.debug(f"[V15.0 CHoCH FLUSH] {sym}: alert dedup scris in JSON")
        except Exception as _flush_err:
            logger.warning(f"[V15.0 CHoCH FLUSH] {setup.get('symbol', '?')}: flush esuat ({_flush_err})")

    def _maybe_send_choch_alerts(
        self,
        setup: dict,
        result: 'MultiTFResult',
        macro_dir: str,
    ) -> None:
        """V52: Telegram structural alerts — post-POI (V52 anchor), 4H before 1H, CHoCH/BOS."""
        if setup.get('status') == 'TRADE_OPEN':
            return

        sym = result.symbol
        tf_4h = result.tf_4h
        tf_1h = result.tf_1h

        def _log_alert_skip(tf_label: str, post_poi, bars, retrace, reason: str) -> None:
            msg = (
                f"[V52 ALERT SKIP] {sym} {tf_label}: post_poi={post_poi} bars={bars} "
                f"retrace={retrace} reason={reason}"
            )
            print(f"  {msg}")
            sys.stdout.flush()
            logger.info(msg)

        if not setup.get('radar_panda_active'):
            if tf_4h.choch_detected or tf_4h.bos_detected:
                _log_alert_skip(
                    '4H', 'N/A', getattr(tf_4h, 'choch_bars_ago', None),
                    getattr(tf_4h, 'retrace_pct', None), 'panda_inactive',
                )
            return

        def _v47_4h_alert_check() -> tuple:
            sig_u = (tf_4h.signal_type or 'CHoCH').upper()
            if sig_u == 'BOS':
                if not tf_4h.bos_detected:
                    return False, 'bos_not_detected', tf_4h.choch_time, tf_4h.bos_bars_ago
                if tf_4h.bos_direction != macro_dir:
                    return False, 'bos_direction_mismatch', tf_4h.choch_time, tf_4h.bos_bars_ago
                break_time = tf_4h.choch_time
                bars_ago = tf_4h.bos_bars_ago
            else:
                if not tf_4h.choch_detected:
                    return False, 'choch_not_detected', tf_4h.choch_time, tf_4h.choch_bars_ago
                if tf_4h.choch_direction != macro_dir:
                    return False, 'choch_direction_mismatch', tf_4h.choch_time, tf_4h.choch_bars_ago
                break_time = tf_4h.choch_time
                bars_ago = tf_4h.choch_bars_ago
            post_poi = _v47_break_post_poi_touch(setup, break_time)
            if not post_poi:
                return False, 'pre_poi_or_no_anchor', break_time, bars_ago
            return True, '', break_time, bars_ago

        def _v47_1h_alert_check() -> tuple:
            if not tf_1h.choch_detected:
                return False, 'choch_not_detected'
            if tf_1h.choch_direction != macro_dir:
                return False, 'choch_direction_mismatch'
            if setup.get('h1_choch_alert_sent'):
                return False, 'already_sent'
            if setup.get('radar_1h_choch_stale') or getattr(result, 'h1_choch_stale', False):
                return False, 'h1_stale'
            if not (result.daily_zone_validated or setup.get('radar_panda_active')):
                return False, 'poi_not_active'
            if not setup.get('poi_first_touch_time'):
                return False, 'no_poi_anchor'
            if not _v47_break_post_poi_touch(setup, tf_1h.choch_time):
                return False, 'pre_poi_or_no_anchor'
            retrace = getattr(tf_1h, 'retrace_pct', None)
            if not _retrace_is_alert_valid(retrace):
                return False, 'retrace_invalid'
            h4_gate = bool(setup.get('h4_choch_alert_sent') or setup.get('h4_bos_alert_sent'))
            if not h4_gate:
                return False, 'no_h4_alert_this_poi'
            return True, ''

        sig = (tf_4h.signal_type or 'CHoCH').upper()
        ok_4h, reason_4h, _bt_4h, bars_4h = _v47_4h_alert_check()
        post_poi_4h = _v47_break_post_poi_touch(setup, _bt_4h)
        retrace_4h = getattr(tf_4h, 'retrace_pct', None)

        if sig == 'BOS' and ok_4h and not setup.get('h4_bos_alert_sent'):
            setup['h4_bos_alert_sent'] = True
            setup['radar_4h_signal_type'] = 'BOS'
            self._flush_choch_alerts_to_json(setup)
            try:
                from telegram_notifier import TelegramNotifier
                tn = TelegramNotifier()
                df_4h = self.get_historical_data(sym, 'H4', 300)
                tn.send_4h_structural_alert(setup, df_4h, signal_type='BOS', tf_data=tf_4h)
                logger.success(f"[V47] 4H BOS alert trimis: {sym}")
            except Exception as e:
                logger.warning(f"[V47] 4H BOS Telegram alert failed for {sym}: {e}")
        elif sig == 'CHOCH' and ok_4h and not setup.get('h4_choch_alert_sent'):
            setup['h4_choch_alert_sent'] = True
            setup['radar_4h_signal_type'] = 'CHoCH'
            self._flush_choch_alerts_to_json(setup)
            try:
                from telegram_notifier import TelegramNotifier
                tn = TelegramNotifier()
                df_4h = self.get_historical_data(sym, 'H4', 300)
                tn.send_4h_structural_alert(setup, df_4h, signal_type='CHoCH', tf_data=tf_4h)
                logger.success(f"[V47] 4H CHoCH alert trimis: {sym}")
            except Exception as e:
                logger.warning(f"[V47] 4H CHoCH Telegram alert failed for {sym}: {e}")
        elif sig == 'BOS' and tf_4h.bos_detected and not setup.get('h4_bos_alert_sent') and not ok_4h:
            _log_alert_skip('4H', post_poi_4h, bars_4h, retrace_4h, reason_4h)
        elif sig == 'CHOCH' and tf_4h.choch_detected and not setup.get('h4_choch_alert_sent') and not ok_4h:
            _log_alert_skip('4H', post_poi_4h, bars_4h, retrace_4h, reason_4h)

        # V50: poarta 1H = alertă 4H trimisă pe ciclul POI curent
        h4_gate_open = bool(
            setup.get('h4_choch_alert_sent') or setup.get('h4_bos_alert_sent')
        )
        ok_1h, reason_1h = _v47_1h_alert_check()
        if tf_1h.choch_detected and not setup.get('h1_choch_alert_sent'):
            if ok_1h:
                setup['h1_choch_alert_sent'] = True
                if tf_1h.choch_price is not None:
                    setup['choch_1h_price'] = tf_1h.choch_price
                self._flush_choch_alerts_to_json(setup)
                try:
                    from telegram_notifier import TelegramNotifier
                    tn = TelegramNotifier()
                    df_1h = self.get_historical_data(sym, 'H1', 400)
                    tn.send_1h_choch_alert(setup, df_1h, tf_data=tf_1h)
                    logger.success(f"[V47] 1H alert trimis: {sym}")
                except Exception as e:
                    logger.warning(f"[V47] 1H Telegram alert failed for {sym}: {e}")
            else:
                post_poi_1h = _v47_break_post_poi_touch(setup, tf_1h.choch_time)
                _log_alert_skip(
                    '1H', post_poi_1h, tf_1h.choch_bars_ago,
                    getattr(tf_1h, 'retrace_pct', None), reason_1h,
                )
                if reason_1h == 'no_h4_alert_this_poi':
                    print(
                        f"  [V50 H1 GATE] {sym}: 1H alert blocat — asteptam alertă 4H post-POI"
                    )
                    sys.stdout.flush()

    def _arm_execute_now(self, setup: dict, result: 'MultiTFResult', exec_tf: str,
                         source: str = 'trigger') -> None:
        """V37.5/6: Seteaza EXECUTE_NOW, flush instant JSON, Telegram o singura data per setup."""
        # V49: armare secvențială — touch POI latched + retrace 60–80% (fără overlap simultan)
        _poi_arm_ok = bool(
            result.daily_zone_validated or setup.get('poi_touch_latched')
        )
        if not _poi_arm_ok:
            logger.info(
                f"[V49 POI GATE] {setup.get('symbol', '?')}: skip EXECUTE_NOW arm — "
                f"preț {result.current_price:.5f} fără POI live și fără poi_touch_latched"
            )
            return
        _macro_dir = 'bullish' if result.direction == 'LONG' else 'bearish'
        _allow_bos = bool(_poi_arm_ok)
        if exec_tf == '1H' and not self._is_4h_aligned_for_1h_entry(
            result.tf_4h, _macro_dir, _allow_bos,
        ):
            logger.info(
                f"[V43.2 H1 GATE] {setup.get('symbol', '?')}: skip EXECUTE_NOW 1H — "
                f"4H nealiniat în POI validat"
            )
            return
        if setup.get('status') != 'TRADE_OPEN':
            _macro, _issues = self._v423_ltf_misalignment(setup, result)
            if _issues:
                _detail = '/'.join(f"{tf}={d}" for tf, d in _issues)
                self._v423_force_disarm_execute_now(
                    setup, result, f"arm blocked — {_detail} vs D1 {_macro}",
                )
                return
        # V40.9/V54: cooldown 30 min — skip pentru erori tranzitorie rețea/spread
        _blocked_at = setup.get('execute_now_blocked_at')
        if _blocked_at:
            _rej = setup.get('last_rejection_reason') or ''
            _transient = any(p in _rej for p in _TRANSIENT_BLOCK_PREFIXES)
            if not _transient:
                try:
                    _bt = datetime.fromisoformat(str(_blocked_at).replace('Z', '+00:00'))
                    if datetime.now(timezone.utc) - _bt < timedelta(minutes=30):
                        logger.debug(
                            f"[V40.9] {setup.get('symbol', '?')}: skip EXECUTE_NOW re-arm — "
                            f"executor block cooldown ({_rej[:60]})"
                        )
                        return
                except Exception:
                    pass

        was_already = setup.get('EXECUTE_NOW') is True
        setup['EXECUTE_NOW'] = True
        setup['execute_now_trigger_tf'] = exec_tf

        exec_tf_data = result.tf_1h if exec_tf == '1H' else result.tf_4h
        # V37.8: SL live din TF-ul de trigger (nu h4_sl stale din JSON)
        _live_sl = getattr(exec_tf_data, 'h4_sl_price', None)
        if _live_sl is None and exec_tf == '1H':
            _live_sl = getattr(result.tf_4h, 'h4_sl_price', None)
        _entry_ref = (
            setup.get('radar_4h_fvg_entry') or setup.get('radar_1h_fvg_entry')
            or setup.get('entry_price')
        )
        if _live_sl and _entry_ref:
            from pip_utils import prices_direction_valid, sl_entry_magnitude_sane
            if (
                prices_direction_valid(setup.get('direction', 'buy'), _entry_ref, _live_sl)
                and sl_entry_magnitude_sane(result.symbol, _entry_ref, _live_sl)
            ):
                setup['h4_sl_price'] = _live_sl

        exec_zone = (
            f"[{exec_tf_data.fvg_bottom:.5f} - {exec_tf_data.fvg_top:.5f}]"
            if exec_tf_data.fvg_top and exec_tf_data.fvg_bottom else "zona necunoscuta"
        )
        exec_eq = f"EQ={exec_tf_data.equilibrium:.5f}" if exec_tf_data.equilibrium else "EQ=N/A"
        _retrace_log = (
            f"{exec_tf_data.retrace_pct * 100:.1f}%"
            if exec_tf_data.retrace_pct is not None
            else "N/A"
        )
        logger.success(
            f"[V46 EXECUTE_NOW {source.upper()} {exec_tf}] {result.symbol} {result.direction} "
            f"-> EXECUTE_NOW=True | POI + Premium/Discount 60–80% "
            f"| Zona: {exec_zone} | Retrace={_retrace_log} | Pret={result.current_price:.5f} | {exec_eq}"
        )

        self._flush_execute_now_to_json(setup)

        # V37.9: Telegram DOAR la primul trigger per setup — latch/FVG flicker/restart = silent
        _alert_key = setup.get('execute_now_alert_key') or self._execute_now_alert_key(setup)
        if setup.get('execute_now_alert_sent'):
            self._execute_now_alert_keys.add(_alert_key)
        should_alert = (
            not setup.get('entry1_filled')
            and not setup.get('execute_now_alert_sent')
            and _alert_key not in self._execute_now_alert_keys
            and source == 'trigger'
            and not was_already
        )
        if should_alert:
            setup['execute_now_alert_sent'] = True
            setup['execute_now_alert_key'] = _alert_key
            self._execute_now_alert_keys.add(_alert_key)
            self._flush_execute_now_to_json(setup)
            try:
                from telegram_notifier import TelegramNotifier
                TelegramNotifier().send_execute_now_alert(setup, exec_tf)
            except Exception as e:
                logger.warning(f"[V37.3] EXECUTE_NOW Telegram alert failed: {e}")
        elif source == 'latch':
            logger.debug(
                f"[V37.8] {result.symbol}: latch EXECUTE_NOW — fara Telegram "
                f"(alert_sent={setup.get('execute_now_alert_sent')})"
            )

    def _update_setup_with_radar(self, setup: Dict, result: 'MultiTFResult') -> None:
        """
        V19.4: Pure in-memory update of a single setup dict with radar results.
        Shared by _batch_sync_to_monitoring_setups (batch path).
        FIX #3: scan_error guard — nu suprascrie FVG valid cu None dacă analiza a crapat.
        FIX #5: Direction matching non-case-sensitive.
        """
        _macro_dir = 'bullish' if result.direction == 'LONG' else 'bearish'

        # 🎯 1H RADAR DATA
        setup['radar_1h_choch_stale'] = bool(getattr(result, 'h1_choch_stale', False))
        if result.tf_1h.choch_detected:
            setup['radar_1h_choch_detected'] = True
            setup['radar_1h_choch_direction'] = result.tf_1h.choch_direction
            setup['radar_1h_choch_time'] = result.tf_1h.choch_time
            setup['radar_1h_choch_price'] = result.tf_1h.choch_price
            setup['radar_1h_choch_bars_ago'] = result.tf_1h.choch_bars_ago
            setup['radar_1h_choch_stale'] = False
        else:
            setup['radar_1h_choch_detected'] = False
            if getattr(result, 'h1_choch_stale', False):
                setup['radar_1h_choch_stale'] = True

        if getattr(result.tf_1h, 'overshoot_stale', False):
            setup['radar_1h_overshoot_stale'] = True
        else:
            setup.pop('radar_1h_overshoot_stale', None)

        if result.tf_1h.scan_error:
            setup['radar_1h_scan_error'] = True
            setup['radar_1h_scan_error_msg'] = result.tf_1h.scan_error_msg
        elif result.tf_1h.fvg_detected:
            setup['radar_1h_fvg_top'] = result.tf_1h.fvg_top
            setup['radar_1h_fvg_bottom'] = result.tf_1h.fvg_bottom
            setup['radar_1h_fvg_entry'] = result.tf_1h.fvg_entry
            setup['radar_1h_in_fvg'] = result.tf_1h.in_fvg
            setup['radar_1h_distance_pips'] = result.tf_1h.distance_to_fvg_pips
            setup['radar_1h_fvg_source'] = result.tf_1h.fvg_source
            setup.pop('radar_1h_scan_error', None)
        else:
            # V34 FIX V10: PROTECTIE MEMORIE FVG
            # Daca FVG nu e detectat in ACEST ciclu, NU suprascriem coordonatele deja valide.
            # Zona FVG ramane activa pana la invalidare structurala (Poarta 1/2/3).
            # Suprascrierea cu None cauza executorul sa piarda zona chiar daca pretul era in ea.
            if not setup.get('radar_1h_fvg_top'):   # Scrie None NUMAI daca nu existau date
                setup['radar_1h_fvg_top'] = None
            if not setup.get('radar_1h_fvg_bottom'):
                setup['radar_1h_fvg_bottom'] = None
            if not setup.get('radar_1h_fvg_entry'):
                setup['radar_1h_fvg_entry'] = None
            setup['radar_1h_in_fvg'] = False   # in_fvg se recalculeaza mereu
            setup.pop('radar_1h_scan_error', None)

        # V16.2: 50% Equilibrium al impulsului 1H CHoCH (frontiera P/D Array)
        if result.tf_1h.equilibrium is not None:
            setup['radar_1h_eq'] = result.tf_1h.equilibrium

        setup['radar_1h_status'] = result.tf_1h.status.value

        # 💎 4H RADAR DATA
        if result.tf_4h.choch_detected:
            setup['radar_4h_choch_detected'] = True
            setup['radar_4h_choch_direction'] = result.tf_4h.choch_direction
            setup['radar_4h_choch_time'] = result.tf_4h.choch_time
            setup['radar_4h_choch_price'] = result.tf_4h.choch_price
            setup['radar_4h_signal_type'] = result.tf_4h.signal_type
            setup['radar_4h_choch_bars_ago'] = result.tf_4h.choch_bars_ago
        else:
            setup['radar_4h_choch_detected'] = False

        if getattr(result.tf_4h, 'overshoot_stale', False):
            setup['radar_4h_overshoot_stale'] = True
        else:
            setup.pop('radar_4h_overshoot_stale', None)

        if result.tf_4h.scan_error:
            setup['radar_4h_scan_error'] = True
            setup['radar_4h_scan_error_msg'] = result.tf_4h.scan_error_msg
        elif result.tf_4h.fvg_detected:
            setup['radar_4h_fvg_top'] = result.tf_4h.fvg_top
            setup['radar_4h_fvg_bottom'] = result.tf_4h.fvg_bottom
            setup['radar_4h_fvg_entry'] = result.tf_4h.fvg_entry
            setup['radar_4h_in_fvg'] = result.tf_4h.in_fvg
            setup['radar_4h_distance_pips'] = result.tf_4h.distance_to_fvg_pips
            setup['radar_4h_fvg_source'] = result.tf_4h.fvg_source
            setup['radar_4h_retrace_pct'] = result.tf_4h.retrace_pct
            setup['radar_4h_in_poi_entry'] = result.tf_4h.in_poi_entry_zone
            setup.pop('radar_4h_scan_error', None)
        else:
            # V34 FIX V10: PROTECTIE MEMORIE FVG 4H
            # Coordonatele FVG detectate anterior raman valide pana la invalidare structurala.
            # Suprascriere cu None = zona pierduta chiar daca executorul era pe punctul de a intra.
            if not setup.get('radar_4h_fvg_top'):   # Scrie None NUMAI daca nu existau date
                setup['radar_4h_fvg_top'] = None
            if not setup.get('radar_4h_fvg_bottom'):
                setup['radar_4h_fvg_bottom'] = None
            if not setup.get('radar_4h_fvg_entry'):
                setup['radar_4h_fvg_entry'] = None
            setup['radar_4h_in_fvg'] = False   # in_fvg se recalculeaza mereu
            setup.pop('radar_4h_scan_error', None)

        # V16.2: 50% Equilibrium al impulsului 4H CHoCH (frontiera P/D Array)
        if result.tf_4h.equilibrium is not None:
            setup['radar_4h_eq'] = result.tf_4h.equilibrium

        # V24.5 / V37.8: SL structural — validare directie inainte de scriere in JSON
        _sl_candidate = result.tf_4h.h4_sl_price
        if result.tf_1h.h4_sl_price is not None and result.priority_timeframe == '1H':
            _sl_candidate = result.tf_1h.h4_sl_price
        if _sl_candidate is not None:
            from pip_utils import prices_direction_valid, sl_entry_magnitude_sane
            _entry_chk = (
                setup.get('radar_1h_fvg_entry') or setup.get('radar_4h_fvg_entry')
                or setup.get('entry_price') or result.current_price
            )
            if (
                _entry_chk
                and prices_direction_valid(setup.get('direction', 'buy'), _entry_chk, _sl_candidate)
                and sl_entry_magnitude_sane(result.symbol, _entry_chk, _sl_candidate)
            ):
                setup['h4_sl_price'] = _sl_candidate

        setup['radar_4h_status'] = result.tf_4h.status.value

        # V16 FIX (B4): Salvăm timestamp-ul ultimei atingeri FVG pentru persistență
        if result.tf_1h.in_fvg or result.tf_4h.in_fvg:
            setup['last_in_fvg_time'] = datetime.now().isoformat()

        # ── V53: h4_structure_locked — post-POI + panda (aliniat V52, fără gate ≤3b) ──
        _setup_direction_lower = 'bullish' if result.direction == 'LONG' else 'bearish'
        _prev_h4_locked = bool(setup.get('h4_structure_locked'))
        _panda_active = bool(setup.get('radar_panda_active'))

        _4h_choch_direction_ok = (
            result.tf_4h.choch_direction is not None
            and result.tf_4h.choch_direction == _setup_direction_lower
        )
        _4h_bos_direction_ok = (
            result.tf_4h.bos_direction is not None
            and result.tf_4h.bos_direction == _setup_direction_lower
        )
        _h4_post_poi = _v47_break_post_poi_touch(setup, result.tf_4h.choch_time)
        _4h_live_choch = (
            result.tf_4h.choch_detected
            and _4h_choch_direction_ok
            and _h4_post_poi
            and _panda_active
        )
        _4h_live_bos = (
            result.tf_4h.bos_detected
            and _4h_bos_direction_ok
            and _h4_post_poi
            and _panda_active
        )
        _h4_alerted_this_poi = bool(
            setup.get('h4_choch_alert_sent') or setup.get('h4_bos_alert_sent')
        )

        if _h4_alerted_this_poi or _4h_live_choch or _4h_live_bos:
            setup['h4_locked'] = True
            setup['h4_structure_locked'] = True
            if not _prev_h4_locked:
                _lock_ts = (
                    result.tf_4h.choch_time
                    if result.tf_4h.choch_detected and result.tf_4h.choch_time
                    else datetime.now(timezone.utc).isoformat()
                )
                setup['h4_structure_locked_at'] = _lock_ts
            if _4h_live_choch:
                _lock_trigger = (
                    f"CHoCH 4H post-POI (la -{result.tf_4h.choch_bars_ago} bare | "
                    f"dir={result.tf_4h.choch_direction} ✅)"
                )
            elif _4h_live_bos:
                _lock_trigger = (
                    f"BOS 4H post-POI (la -{result.tf_4h.bos_bars_ago} bare | "
                    f"dir={result.tf_4h.bos_direction} ✅)"
                )
            else:
                _lock_trigger = "4H alertă trimisă pe ciclul POI curent"
            logger.info(
                f"🔒 [V50 H4 LOCK] {result.symbol}: {_lock_trigger} "
                f"→ h4_structure_locked=True"
            )
        elif result.tf_4h.choch_detected and not _4h_choch_direction_ok:
            logger.warning(
                f"🚫 [V50 H4 DIRECTION MISMATCH] {result.symbol}: "
                f"CHoCH 4H dir={result.tf_4h.choch_direction} != setup={_setup_direction_lower} "
                f"— h4_structure_locked NESETAT"
            )
            setup['h4_structure_locked'] = False
            self._v423_force_disarm_execute_now(
                setup, result, 'H4 DIRECTION MISMATCH vs Daily bias',
            )
        # V54: H4 stale dezarmare mutată DUPĂ latch EXECUTE_NOW (vezi final secțiune)
        # else: în afara POI — păstrăm starea existentă

        # V42.3: 1H CHoCH contrar bias-ului Daily → dezarmare EXECUTE_NOW
        if (
            result.tf_1h.choch_detected
            and result.tf_1h.choch_direction is not None
            and result.tf_1h.choch_direction != _setup_direction_lower
        ):
            logger.warning(
                f"🚫 [V42.3 H1 DIRECTION MISMATCH] {result.symbol}: "
                f"CHoCH 1H dir={result.tf_1h.choch_direction} != setup={_setup_direction_lower}"
            )
            self._v423_force_disarm_execute_now(
                setup, result, 'H1 DIRECTION MISMATCH vs Daily bias',
            )

        # 🏆 PRIORITY & EXECUTION STATUS
        setup['radar_priority_timeframe'] = result.priority_timeframe
        setup['radar_execution_ready'] = result.execution_ready
        setup['radar_verdict'] = result.verdict
        setup['radar_last_scan'] = datetime.now().isoformat()
        setup['pd_guard_passed'] = result.pd_guard_passed
        setup['pd_guard_reason'] = result.pd_guard_reason or ''
        setup['daily_zone_validated'] = result.daily_zone_validated

        # V22.1: EXECUTE_NOW — cheia supremă de execuție
        # REGULA DE AUR: Radarul SETEAZĂ semnalul, EXECUTORUL îl consumă.
        # Radarul NU are voie să șteargă EXECUTE_NOW — doar executorul poate face asta
        # (după ce execută sau respinge). Altfel: radarul scrie False în ciclu T+30s,
        # înainte ca executorul să apuce să citească True-ul din T+00s → semnal pierdut.
        # Excepție V42.2: TRADE_OPEN = toate intrările complete; PARTIAL_OPEN = radar poate re-arma 4H.
        # V42.3: nu arma EXECUTE_NOW dacă LTF CHoCH ≠ Daily bias.
        _v423_macro, _v423_issues = self._v423_ltf_misalignment(setup, result)
        if _v423_issues and setup.get('status') != 'TRADE_OPEN':
            _detail = '/'.join(f"{tf}={d}" for tf, d in _v423_issues)
            self._v423_force_disarm_execute_now(
                setup, result, f"LTF misalignment ({_detail} vs D1 {_v423_macro})",
            )
        elif result.execution_ready:
            # V31.0 REVERSAL vs CONTINUATION TRIGGER GUARD
            # REVERSAL: accepta NUMAI CHoCH ca trigger (BOS = continuarea trendului anterior — invalid pt reversal)
            # CONTINUATION: accepta si BOS (trend in desfasurare, BOS = confirmare continuare)
            _setup_type_v31 = setup.get('setup_type', setup.get('strategy_type', 'reversal')).upper()
            _is_reversal_v31 = 'REVERSAL' in _setup_type_v31
            _exec_tf_v31 = result.priority_timeframe or '?'
            _exec_tf_data_v31 = result.tf_1h if _exec_tf_v31 == '1H' else result.tf_4h
            # BOS-only trigger detection
            _used_bos_only = (
                getattr(_exec_tf_data_v31, 'bos_detected', False)
                and not _exec_tf_data_v31.choch_detected
            )
            if _is_reversal_v31 and _used_bos_only:
                # REVERSAL pe BOS = INTERZIS — asteptam CHoCH autentic
                logger.warning(
                    f"[V31.0 REVERSAL GUARD] {result.symbol}: EXECUTE_NOW blocat — "
                    f"setup REVERSAL nu accepta BOS ca trigger. Numai CHoCH autentic!"
                )
                print(f"  ⛔ [RADAR SKIP EXECUTE] {result.symbol}: REVERSAL guard — "
                      f"BOS-only trigger respins, așteptăm CHoCH autentic")
                sys.stdout.flush()
                # Nu setam EXECUTE_NOW — asteptam CHoCH real
            else:
                # V37.7 RR SHIELD — toate trigger-ele (ex. BTC TP la low deja sweep-uit → RR 0.77)
                _exec_tf_v32 = result.priority_timeframe or '?'
                _exec_tf_data_v32 = result.tf_1h if _exec_tf_v32 == '1H' else result.tf_4h
                _block_execute = self._rr_shield_blocks_execute(setup, result, _exec_tf_data_v32)

                if not _block_execute:
                    self._arm_execute_now(
                        setup, result,
                        result.priority_timeframe or '1H',
                        source='trigger',
                    )
        elif setup.get('status') == 'TRADE_OPEN':
            self._clear_execute_now_signal(setup, 'trade_open')
        elif setup.get('entry1_filled') and setup.get('status') != 'PARTIAL_OPEN':
            self._clear_execute_now_signal(setup, 'entry1_filled')
        elif setup.get('EXECUTE_NOW') and setup.get('status') == 'PARTIAL_OPEN':
            still_in_fvg = result.tf_1h.in_fvg or result.tf_4h.in_fvg
            if still_in_fvg:
                setup['radar_execution_ready'] = True
                _ltf = setup.get('execute_now_trigger_tf') or '4H'
                setup['radar_verdict'] = (
                    f"🔥 EXECUTE NOW ({_ltf} LAYER-2 — asteptam executor scale-in)"
                )
        elif setup.get('EXECUTE_NOW') and not setup.get('entry1_filled'):
            # V37.5: Reset DOAR cand pretul paraseste FVG — NU cand CHoCH trece de 3 bare.
            # Bug V31: `not execution_ready` stergea semnalul desi pretul era inca in FVG.
            still_in_fvg = result.tf_1h.in_fvg or result.tf_4h.in_fvg
            if not still_in_fvg:
                self._clear_execute_now_only(setup, 'pretul a iesit din FVG')
                self._flush_execute_now_to_json(setup)
            else:
                setup['radar_execution_ready'] = True
                _ltf = setup.get('execute_now_trigger_tf') or (
                    '1H' if result.tf_1h.in_fvg else '4H'
                )
                setup['radar_verdict'] = (
                    f"🔥 EXECUTE NOW ({_ltf} LATCH — CHoCH confirmat, asteptam executor)"
                )
                logger.debug(
                    f"[V37.5 LATCH] {result.symbol}: EXECUTE_NOW pastrat — "
                    f"in FVG, CHoCH confirmat (trigger >3b OK)"
                )
        elif not setup.get('entry1_filled'):
            # V37.5: CHoCH confirmat + in FVG dar EXECUTE_NOW pierdut → re-arm pentru executor
            latch_tf = self._evaluate_confirmed_pullback_latch(setup, result)
            if latch_tf:
                _ltf_data = result.tf_1h if latch_tf == '1H' else result.tf_4h
                if not self._rr_shield_blocks_execute(setup, result, _ltf_data):
                    self._arm_execute_now(setup, result, latch_tf, source='latch')
                    setup['radar_execution_ready'] = True
                    setup['radar_verdict'] = (
                        f"🔥 EXECUTE NOW ({latch_tf} LATCH — reconectat executor)"
                    )

        # V54: H4 stale deferred — lock reset fără dezarmare EXECUTE_NOW dacă latch activ
        if (
            setup.get('poi_first_touch_time')
            and not _h4_alerted_this_poi
            and not (_4h_live_choch or _4h_live_bos)
            and not _preserve_execute_latch(setup, result)
        ):
            if _prev_h4_locked or setup.get('h4_structure_locked'):
                logger.info(
                    f"[V54 H4 STALE] {result.symbol}: lock reset — "
                    f"fără CHoCH/BOS 4H post-POI; EXECUTE_NOW păstrat"
                )
            setup['h4_structure_locked'] = False

        # V31.0: Propagam daily_target_price ca daily_tp_price pentru backward compat cu Executor
        if setup.get('daily_target_price') and not setup.get('daily_tp_price'):
            setup['daily_tp_price'] = setup['daily_target_price']

        self._maybe_send_choch_alerts(setup, result, _macro_dir)

    def _apply_lifecycle_gates(self, setups: list) -> list:
        """V33: Cele 3 Porti de Invalidare — singura responsabilitate a Radarului
        de a marca paritati ca 'moarte' inainte de analiza structurala.

        Poarta 1: Invalidare Structurala Macro
          LONG + close < daily_swing_low  → INVALIDATED
          SHORT + close > daily_swing_high → INVALIDATED

        Poarta 2: Target Atins Fara Noi
          Pretul atinge daily_tp_price fara entry1_filled → COMPLETED_WITHOUT_ENTRY

        V35: Poarta 3 (Timeout Calendaristic) ELIMINATA definitiv.
          Setup-urile in WAITING_D1_PULLBACK NU expira pe timp — numai structural.
        """
        import os as _os

        _TERMINAL_STATUSES = {
            'INVALIDATED', 'COMPLETED_WITHOUT_ENTRY', 'EXPIRED_TIMEOUT',
            'EXPIRED', 'CLOSED', 'FAILED', 'CANCELLED', 'TRADE_OPEN'
        }
        # V42.2: PARTIAL_OPEN — Poarta 1/2 inca active (structura macro poate invalida)

        changed = False
        for s in setups:
            sym    = s.get('symbol', '?')
            status = s.get('status', '')

            # Nu atingem statusuri terminale sau TRADE_OPEN
            if status in _TERMINAL_STATUSES:
                continue

            direction = s.get('direction', '').lower()  # 'buy' / 'sell'

            # Obtinem pret live (necesar pentru Portile 1 si 2)
            try:
                _cp = self.get_current_price(sym)
            except Exception as _cp_err:
                logger.warning(f"[V37.0] {sym}: live price unavailable for Poarta 1: {_cp_err}")
                _cp = None

            if _cp is not None:
                # ── POARTA 1: Invalidare Structurala Macro ────────────────────────
                # LONG: pretul inchide sub daily_swing_low (baza structurii invalidata)
                # SHORT: pretul inchide peste daily_swing_high (plafonul structurii spart)
                _dsl = s.get('daily_swing_low')
                _dsh = s.get('daily_swing_high')
                if direction == 'buy' and _dsl and _cp < float(_dsl):
                    s['status'] = 'INVALIDATED'
                    s['invalidation_reason'] = f'P1: close {_cp:.5f} < swing_low {_dsl:.5f}'
                    for _lk in ('poi_touch_latched', 'radar_panda_active', 'poi_first_touch_time',
                                'poi_radar_armed_at', '_poi_occupied'):
                        s.pop(_lk, None)
                    logger.warning(f"[V33 POARTA 1] {sym} LONG INVALIDATED: pret {_cp:.5f} < daily_swing_low {_dsl:.5f}")
                    changed = True
                    continue
                elif direction == 'sell' and _dsh and _cp > float(_dsh):
                    s['status'] = 'INVALIDATED'
                    s['invalidation_reason'] = f'P1: close {_cp:.5f} > swing_high {_dsh:.5f}'
                    for _lk in ('poi_touch_latched', 'radar_panda_active', 'poi_first_touch_time',
                                'poi_radar_armed_at', '_poi_occupied'):
                        s.pop(_lk, None)
                    logger.warning(f"[V33 POARTA 1] {sym} SHORT INVALIDATED: pret {_cp:.5f} > daily_swing_high {_dsh:.5f}")
                    changed = True
                    continue

                # ── POARTA 2: Target Atins Fara Noi ───────────────────────────────
                _tp = s.get('daily_tp_price') or s.get('daily_target_price')
                _filled = s.get('entry1_filled', False)
                if _tp and not _filled:
                    _tp_f = float(_tp)
                    if (direction == 'buy'  and _cp >= _tp_f) or \
                       (direction == 'sell' and _cp <= _tp_f):
                        s['status'] = 'COMPLETED_WITHOUT_ENTRY'
                        s['invalidation_reason'] = f'P2: pret {_cp:.5f} a atins TP {_tp_f:.5f} fara intrare'
                        logger.warning(f"[V33 POARTA 2] {sym} COMPLETED_WITHOUT_ENTRY: pret {_cp:.5f} a atins TP {_tp_f:.5f}")
                        changed = True
                        continue

        # V35: Poarta 3 (Timeout Calendaristic) ELIMINATA definitiv.
        # Setup-urile in WAITING_D1_PULLBACK raman active pana la invalidare structurala
        # (Poarta 1 sau Poarta 2). Sistemul nu mai ucide oportunitate pe criterii de timp.

        # Daca ceva s-a schimbat, salvam imediat JSON-ul (inainte de analiza structurala)
        if changed:
            try:
                import numpy as _np
                def _json_safe(obj):
                    if isinstance(obj, (_np.bool_,)):    return bool(obj)
                    if isinstance(obj, (_np.integer,)):  return int(obj)
                    if isinstance(obj, (_np.floating,)): return float(obj)
                    if isinstance(obj, (_np.ndarray,)):  return obj.tolist()
                    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
                with open(_MONITORING_FILE, 'r', encoding='utf-8') as _f:
                    _raw = json.load(_f)
                if isinstance(_raw, dict):
                    _raw['setups'] = setups
                    _raw['last_updated'] = datetime.now().isoformat()
                else:
                    _raw = {'setups': setups, 'last_updated': datetime.now().isoformat()}
                with open(_MONITORING_TMP, 'w', encoding='utf-8') as _f:
                    json.dump(_raw, _f, indent=2, default=_json_safe)
                _os.replace(_MONITORING_TMP, _MONITORING_FILE)
                logger.info("[V33 LIFECYCLE] JSON actualizat cu statusuri invalidate")
            except Exception as _se:
                logger.error(f"[V33 LIFECYCLE] Eroare salvare dupa gate: {_se}")

        return setups

    def _batch_sync_to_monitoring_setups(
        self,
        results: list
    ) -> None:
        """
        V22 MERGE PARȚIAL — elimină race condition (Time Warp).

        Problema V19.4: json_data era citit la STARTUL ciclului (T+01s) și scris
        la FINALUL ciclului (T+31s) — suprascriind orice modificare făcută de
        setup_executor_monitor în interval (execuții, cleanup, status updates).

        Soluția V22:
          1. Re-citim monitoring_setups.json FRESH în momentul scrierii (după analiză)
          2. Actualizăm DOAR cheile Radarului (radar_4h_*, radar_1h_*, EXECUTE_NOW)
          3. Toate celelalte setup-uri (adăugate de scanner, modificate de executor)
             rămân INTACTE — merge parțial, nu overwrite complet.
        """
        try:
            import numpy as _np
            import os as _os

            def _json_safe(obj):
                if isinstance(obj, (_np.bool_,)):    return bool(obj)
                if isinstance(obj, (_np.integer,)):  return int(obj)
                if isinstance(obj, (_np.floating,)): return float(obj)
                if isinstance(obj, (_np.ndarray,)):  return obj.tolist()
                raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

            # ── Re-citire LIVE: starea ACTUALĂ a fișierului, nu snapshot-ul de la startul ciclului ──
            fresh_data = None
            for _read_attempt in range(3):
                try:
                    with open(_MONITORING_FILE, 'r', encoding='utf-8') as _f:
                        fresh_data = json.load(_f)
                    break
                except Exception as _je:
                    if _read_attempt >= 2:
                        logger.error(
                            f"⚠️ _batch_sync V22: Nu pot re-citi monitoring_setups.json "
                            f"după 3 încercări: {_je}"
                        )
                        return
                    time.sleep(0.15)

            if isinstance(fresh_data, dict):
                setups = fresh_data.get("setups", [])
            elif isinstance(fresh_data, list):
                setups = fresh_data
            else:
                logger.error("⚠️ _batch_sync V22: format JSON nerecunoscut")
                return

            matched_count = 0
            for _original_setup, result in results:
                # Direction matching non-case-sensitive
                result_dir = result.direction.upper()
                for i, setup in enumerate(setups):
                    setup_dir = setup.get('direction', '').upper()
                    matches_sell   = (result_dir == 'SHORT' and setup_dir == 'SELL')
                    matches_buy    = (result_dir == 'LONG'  and setup_dir == 'BUY')
                    matches_direct = (result_dir == setup_dir)
                    if setup.get('symbol') == result.symbol and (matches_sell or matches_buy or matches_direct):
                        # V37.9 + V53: latch in-memory → JSON (bidirectional pop pentru chei zombie)
                        _merge_in_memory_latch_to_json(setups[i], _original_setup)
                        # V49 P0-A: post-update wins — NU restaura EXECUTE_NOW din snapshot scan-start
                        self._update_setup_with_radar(setups[i], result)
                        if setups[i].get('entry1_filled'):
                            for _ek in ('EXECUTE_NOW', 'execute_now_trigger_tf'):
                                setups[i].pop(_ek, None)
                        matched_count += 1
                        break

            if isinstance(fresh_data, dict):
                fresh_data['setups'] = setups
                fresh_data['last_updated'] = datetime.now().isoformat()
            else:
                fresh_data = setups

            # V33 CLEANUP: Elimina din JSON paritati cu status terminal
            # (marcate de _apply_lifecycle_gates sau de executor)
            _DEAD = {
                'INVALIDATED', 'COMPLETED_WITHOUT_ENTRY', 'EXPIRED_TIMEOUT',
                'EXPIRED', 'CLOSED', 'FAILED', 'CANCELLED'
            }
            if isinstance(fresh_data, dict):
                _before = len(fresh_data.get('setups', []))
                _survivors = []
                for s in fresh_data.get('setups', []):
                    st = s.get('status', '')
                    if st in _DEAD:
                        if st == 'CLOSED':
                            logger.info(
                                f"[V42.2 EVICTION] Purged {s.get('symbol', '?')} from JSON "
                                f"due to CLOSED status"
                            )
                    else:
                        _survivors.append(s)
                fresh_data['setups'] = _survivors
                _removed = _before - len(_survivors)
                if _removed:
                    logger.info(f"[V33 CLEANUP] {_removed} paritate(i) terminale eliminate din JSON")

            tmp_path = _MONITORING_TMP
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(fresh_data, f, indent=2, default=_json_safe)
            _os.replace(tmp_path, _MONITORING_FILE)
            logger.success(
                f"[BATCH SYNC V22 MERGE] monitoring_setups.json actualizat — "
                f"{matched_count}/{len(results)} paritati sincronizate (re-citire LIVE, race-free)"
            )
            sys.stdout.flush()

        except Exception as e:
            logger.error(f"⚠️ _batch_sync_to_monitoring_setups V22 error: {e}")

    def print_result(self, result: MultiTFResult):
        """Print formatted multi-timeframe analysis — V37.1 ASCII lizibil pe Windows VPS."""
        sep = "=" * 72
        d_lo = result.daily_fvg_bottom
        d_hi = result.daily_fvg_top
        if d_lo == 0 and d_hi == 0:
            daily_zone_txt = "N/A (Scanner: POI inca nesetat — WAITING_D1_PULLBACK)"
        else:
            daily_zone_txt = f"[{_fmt_price(d_lo)} - {_fmt_price(d_hi)}]"

        _radar_out("")
        _radar_out(sep)
        _radar_out(f"RADAR REPORT | {result.symbol} | {result.direction}")
        _radar_out(f"Scan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        _radar_out(sep)
        _radar_out(f"DAILY  | Status: VALIDATED (Always-On V36.5)")
        _radar_out(f"       | FVG ref: {daily_zone_txt}")
        _radar_out(f"       | Entry ref: {_fmt_price(result.daily_entry)}")
        if result.poi_first_touch_time:
            _radar_out(f"       | POI anchor: {result.poi_first_touch_time}")
        _radar_out(f"PRICE  | Live: {_fmt_price(result.current_price)}")
        _radar_out("-" * 72)

        for label, tf in [("1H", result.tf_1h), ("4H", result.tf_4h)]:
            _radar_out(f"{label} TIMEFRAME")
            _radar_out(f"  Status : {_plain_status(tf.status)}")
            if tf.choch_detected:
                _radar_out(
                    f"  CHoCH  : {tf.choch_direction.upper()} @ {_fmt_price(tf.choch_price)} "
                    f"({tf.choch_time or '?'})"
                )
            else:
                _radar_out("  CHoCH  : none")
            if tf.fvg_detected and tf.fvg_top and tf.fvg_bottom:
                _radar_out(
                    f"  FVG    : [{_fmt_price(tf.fvg_bottom)} - {_fmt_price(tf.fvg_top)}] "
                    f"entry={_fmt_price(tf.fvg_entry)}"
                )
                if tf.in_fvg:
                    _radar_out("  Zone   : PRICE IN FVG")
                else:
                    dist = tf.distance_to_fvg_pips
                    if dist > 5000:
                        _radar_out(f"  Zone   : waiting pullback (dist invalid — check data)")
                    else:
                        _radar_out(f"  Zone   : waiting pullback ({dist:.1f} pips)")
            else:
                _radar_out("  FVG    : none (Fibo fallback sau in asteptare CHoCH)")
            _radar_out("-" * 72)

        _radar_out(f"VERDICT: {result.verdict}")
        if result.pd_guard_passed is False and result.pd_guard_reason:
            _radar_out(f"P/D GUARD: BLOCK EXECUTE — {result.pd_guard_reason}")
        elif result.pd_guard_passed:
            _radar_out("P/D GUARD: OK (execuție permisă dacă trigger H4/H1)")
        if result.priority_timeframe:
            _radar_out(f"PRIORITY TF: {result.priority_timeframe}")
        if result.execution_ready:
            _radar_out("*** EXECUTE_NOW — semnal activ ***")
        else:
            _radar_out("EXECUTE: NU inca — asteptam trigger H4/H1 + conditii P/D")
        _radar_out(sep)
        _radar_out("")

        logger.info(
            f"{result.symbol} | {_plain_status(result.tf_4h.status)} | "
            f"exec_ready={result.execution_ready} | {result.verdict[:80]}"
        )
    
    def load_monitoring_setups(self) -> List[Dict]:
        """Load setups from monitoring_setups.json"""
        try:
            with open(_MONITORING_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                if isinstance(data, dict):
                    setups = data.get("setups", [])
                elif isinstance(data, list):
                    setups = data
                else:
                    return []
                
                # V22: Accept orice setup cu 'symbol' — entry_price poate lipsi la setups proaspete
                # Filtrul pe entry_price era cauza invizibilității setup-urilor nou create de daily_scanner
                return [s for s in setups if isinstance(s, dict) and s.get('symbol')]
        
        except FileNotFoundError:
            print("⚠️  monitoring_setups.json not found")
            return []
        except json.JSONDecodeError as e:
            print(f"⚠️  Error parsing monitoring_setups.json: {e}")
            return []
    
    def run_scan(self, symbol: Optional[str] = None, all_setups: bool = False):
        """Run multi-timeframe scan — V19.4: batch JSON (1 citire, 1 scriere per ciclu)"""
        setups = self.load_monitoring_setups()
        self._hydrate_execute_now_dedup(setups)

        # V43.2 E3-T2: purge structural_breach înainte de orice analiză LTF
        setups = self._purge_structural_breaches(setups)

        if not setups:
            print("\n📭 No active setups in monitoring\n")
            return

        _all_in_json = [
            f"{s.get('symbol','?')}({s.get('status','?')})"
            for s in setups if isinstance(s, dict)
        ]
        print(f"  📋 [V36.3] monitoring_setups.json: {len(setups)} intrări — {_all_in_json}")
        sys.stdout.flush()

        if symbol:
            target_setups = [s for s in setups if s.get('symbol') == symbol]
            if not target_setups:
                print(f"\n⚠️  No setup found for {symbol}\n")
                return
            setups = target_setups

        # V33: Inainte de analiza, aplicam cele 3 Porti de Invalidare pe toate setup-urile
        # Daca vreun status se schimba, salvam imediat JSON-ul (fara sa asteptam batch_sync)
        setups = self._apply_lifecycle_gates(setups)

        # Filtram: TRADE_OPEN (incetarea focului) si statusuri terminale nu intra in analiza
        # V42.2: PARTIAL_OPEN — radar continua scanarea pentru layer 4H (NU in _SKIP_STATUSES)
        _SKIP_STATUSES = {
            'TRADE_OPEN',           # Executorul are control — Radarul nu mai cauta trigaci
            'INVALIDATED',          # Poarta 1: structura macro incalcata
            'COMPLETED_WITHOUT_ENTRY',  # Poarta 2: tinta atinsa fara noi
            'EXPIRED_TIMEOUT',      # Poarta 3: timeout 5 zile lucratoare
            'EXPIRED', 'CLOSED', 'FAILED', 'CANCELLED'
        }
        active_setups = [s for s in setups if s.get('status', '') not in _SKIP_STATUSES]
        skipped = len(setups) - len(active_setups)
        if skipped:
            for s in setups:
                if s.get('status', '') in _SKIP_STATUSES:
                    print(f"  ⏸️  [RADAR SKIP] {s.get('symbol', '?')}: status={s.get('status')} "
                          f"— exclus din scan (terminal/TRADE_OPEN)")
            sys.stdout.flush()

        if not active_setups:
            print("\n📭 No active setups to scan (all TRADE_OPEN or invalidated)\n")
            return

        # V22: json_data pre-citire ELIMINATA — _batch_sync re-citeste LIVE la final ciclu

        print("\n" + "="*80)
        symbols_list = " | ".join([f"{s.get('symbol','?')} {s.get('direction','?')}" for s in active_setups])
        print(f"📋 LOADED {len(active_setups)} ACTIVE SETUP(S) FROM monitoring_setups.json")
        print(f"   {symbols_list}")
        print("="*80)
        sys.stdout.flush()

        ok_count = 0
        err_count = 0
        collected_results = []

        for setup in active_setups:
            sym = setup.get('symbol', 'UNKNOWN')
            direction_label = setup.get('direction', '?').upper()
            print(f"\n🔄 [RADAR INITIALIZAT] Pornire descarcare date si analiza istorica pentru: {sym} {direction_label}...")
            sys.stdout.flush()
            try:
                result = self.analyze_setup(setup, save_to_json=False)
                if result is None:
                    _reason = self._last_skip_reason or "motiv necunoscut (verifică log-urile de mai sus)"
                    print(f"  ⛔ [RADAR SKIP] {sym}: ciclu omis — {_reason}")
                    sys.stdout.flush()
                    ok_count += 1
                    continue
                self.print_result(result)
                sys.stdout.flush()
                collected_results.append((setup, result))
                ok_count += 1
            except Exception as e:
                import traceback
                print(f"\n{'='*80}")
                print(f"❌ [RADAR ERROR] {sym}: analiză eșuată — {e}")
                traceback.print_exc()
                print("="*80 + "\n")
                sys.stdout.flush()
                err_count += 1
                continue

        if collected_results:
            self._batch_sync_to_monitoring_setups(collected_results)

        print(f"\n✅ Scan complete: {ok_count} analyzed | ❌ {err_count} errors\n")
    
    def _compute_adaptive_interval(self, base_interval: int, symbol: Optional[str] = None) -> int:
        """
        V25.2 ADAPTIVE INTERVAL — ajustează frecvența scanării bazat pe proximitatea față de FVG.

        Logică:
          ≥ 1 setup cu preț < 10 pips de FVG  →  5s  (Sniper mode — nu ratăm wick-uri rapide)
          ≥ 1 setup în WAITING_*_PULLBACK      → 10s  (Pullback activ — monitorizare intensă)
          Altfel                               → base_interval (30s default)

        Date citite din JSON-ul deja scris de ciclul anterior — zero HTTP calls extra.
        """
        try:
            with open(_MONITORING_FILE, 'r', encoding='utf-8') as _af:
                _ad = json.load(_af)
            _setups = _ad.get('setups', _ad) if isinstance(_ad, dict) else _ad
            if not isinstance(_setups, list):
                return base_interval
            if symbol:
                _setups = [s for s in _setups if s.get('symbol') == symbol]

            _min_dist = float('inf')
            _has_pullback = False

            for _s in _setups:
                # Verifică distanța față de FVG (stocată de scanarea anterioară)
                for _dk in ('radar_1h_distance_pips', 'radar_4h_distance_pips'):
                    _dv = _s.get(_dk)
                    if isinstance(_dv, (int, float)) and _dv >= 0:
                        _min_dist = min(_min_dist, _dv)
                # Verifică dacă există pullback activ în statusuri
                for _sk in ('radar_1h_status', 'radar_4h_status'):
                    _sv = _s.get(_sk, '')
                    if 'WAITING' in _sv and 'PULLBACK' in _sv:
                        _has_pullback = True

            if _min_dist < 10:
                return 5    # ⚡ Sniper: preț la <10 pips de FVG
            if _has_pullback:
                return 10   # 🔍 Pullback activ pe 4H sau 1H
            return base_interval  # 🔄 Normal
        except Exception as _int_err:
            logger.warning(f"[V37.0] adaptive interval fallback to {base_interval}s: {_int_err}")
            return base_interval

    def watch_mode(self, interval: int, symbol: Optional[str] = None, all_setups: bool = False):
        """Run scan in watch mode with auto-refresh"""
        print("\n" + "="*80)
        print("👁️  MULTI-TF RADAR - WATCH MODE ACTIVE (V25.2 ADAPTIVE INTERVAL)")
        print("="*80)
        print(f"⏱️  Base Interval: {interval}s | Adaptive: 10s (pullback) / 5s (în FVG)")
        print(f"🎯 Target: {'ALL setups' if all_setups else (symbol if symbol else 'First setup')}")
        print("Press Ctrl+C to stop")
        print("="*80 + "\n")

        try:
            while True:
                self.run_scan(symbol=symbol, all_setups=all_setups)

                # V25.2: Interval adaptiv bazat pe proximitate FVG (citire JSON fără HTTP extra)
                next_interval = self._compute_adaptive_interval(interval, symbol)
                if next_interval <= 5:
                    print(f"\n⚡ [SNIPER MODE] Preț aproape de FVG — rescan în {next_interval}s...\n")
                elif next_interval <= 10:
                    print(f"\n🔍 [PULLBACK ACTIV] CHoCH detectat — rescan în {next_interval}s...\n")
                else:
                    print(f"\n⏳ Next scan în {next_interval}s (normal)...\n")
                time.sleep(next_interval)

        except KeyboardInterrupt:
            print("\n\n👋 Watch mode stopped by user\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='🎯 Multi-Timeframe Execution Radar - V8.3 SNIPER EDITION'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        help='Scan specific symbol (e.g., EURJPY)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Scan all setups in monitoring'
    )
    parser.add_argument(
        '--watch',
        action='store_true',
        help='Run in watch mode (auto-refresh)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Watch mode refresh interval in seconds (default: 30)'
    )
    
    args = parser.parse_args()
    
    radar = MultiTFRadar()
    logger.success(
        "[V42.4 CLEANUP] Successfully purged legacy branches and unified core system data defaults."
    )
    
    if args.watch:
        radar.watch_mode(
            interval=args.interval,
            symbol=args.symbol,
            all_setups=args.all
        )
    else:
        radar.run_scan(symbol=args.symbol, all_setups=args.all)


if __name__ == '__main__':
    main()
