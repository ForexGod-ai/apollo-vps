"""V95 — Dedicated 4H range engine (body-only, fw=2 fractals, target_armed)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from smc_detector.models import BOS, CHoCH, SwingPoint


def _body_high(df: pd.DataFrame, i: int) -> float:
    return float(max(df['open'].iloc[i], df['close'].iloc[i]))


def _body_low(df: pd.DataFrame, i: int) -> float:
    return float(min(df['open'].iloc[i], df['close'].iloc[i]))


def _bar_time(df: pd.DataFrame, idx: int):
    if isinstance(df.index, pd.RangeIndex):
        return idx
    if 'time' in df.columns:
        t = df['time'].iloc[idx]
        return t if isinstance(t, datetime) else idx
    return df.index[idx] if idx < len(df.index) else idx


def _min_body_low_between(df: pd.DataFrame, start_idx: int, end_idx: int) -> Tuple[int, float]:
    start_idx = max(0, int(start_idx))
    end_idx = min(int(end_idx), len(df) - 1)
    best_i, best_v = start_idx, _body_low(df, start_idx)
    for j in range(start_idx, end_idx + 1):
        v = _body_low(df, j)
        if v < best_v:
            best_v, best_i = v, j
    return best_i, float(best_v)


def _max_body_high_between(df: pd.DataFrame, start_idx: int, end_idx: int) -> Tuple[int, float]:
    start_idx = max(0, int(start_idx))
    end_idx = min(int(end_idx), len(df) - 1)
    best_i, best_v = start_idx, _body_high(df, start_idx)
    for j in range(start_idx, end_idx + 1):
        v = _body_high(df, j)
        if v > best_v:
            best_v, best_i = v, j
    return best_i, float(best_v)


def _detect_fractal_swings(df: pd.DataFrame, fw: int) -> Tuple[List[SwingPoint], List[SwingPoint]]:
    """Local 4H fractals on body highs/lows only (no D1 major filter)."""
    highs: List[SwingPoint] = []
    lows: List[SwingPoint] = []
    if df is None or len(df) < 2 * fw + 1:
        return highs, lows
    for i in range(fw, len(df) - fw):
        bh_i = _body_high(df, i)
        bl_i = _body_low(df, i)
        is_h = all(bh_i >= _body_high(df, j) for j in range(i - fw, i + fw + 1))
        is_l = all(bl_i <= _body_low(df, j) for j in range(i - fw, i + fw + 1))
        ct = _bar_time(df, i)
        if is_h:
            highs.append(SwingPoint(index=i, price=bh_i, swing_type='high', candle_time=ct))
        if is_l:
            lows.append(SwingPoint(index=i, price=bl_i, swing_type='low', candle_time=ct))
    return highs, lows


def _alternating_chain(
    df: pd.DataFrame,
    swing_highs: List[SwingPoint],
    swing_lows: List[SwingPoint],
) -> List[Tuple[str, int, float, SwingPoint]]:
    events: List[Tuple[str, int, float, SwingPoint]] = []
    for l in swing_lows:
        events.append(('L', l.index, _body_low(df, l.index), l))
    for h in swing_highs:
        events.append(('H', h.index, _body_high(df, h.index), h))
    events.sort(key=lambda x: x[1])
    chain: List[Tuple[str, int, float, SwingPoint]] = []
    for typ, idx, px, sp in events:
        if not chain:
            chain.append((typ, idx, px, sp))
            continue
        last_typ, last_idx, last_px, _ = chain[-1]
        if typ == last_typ:
            if typ == 'L' and px < last_px:
                chain[-1] = (typ, idx, px, sp)
            elif typ == 'H' and px > last_px:
                chain[-1] = (typ, idx, px, sp)
        else:
            chain.append((typ, idx, px, sp))
    return chain


def swing_pt(df: pd.DataFrame, i: int, st: str) -> SwingPoint:
    price = _body_high(df, i) if st == 'high' else _body_low(df, i)
    return SwingPoint(
        index=i,
        price=price,
        swing_type=st,
        candle_time=_bar_time(df, i),
    )


def h4_impulse_retrace_pct(
    impulse_origin: float,
    impulse_extreme: float,
    current_price: float,
    direction: str,
) -> Tuple[float, float]:
    """Retrace from impulse_extreme toward origin (V95)."""
    impulse_size = abs(float(impulse_extreme) - float(impulse_origin))
    if impulse_size <= 0:
        return 0.0, 0.0
    d = str(direction or '').lower()
    if d == 'bullish':
        retrace = (float(impulse_extreme) - float(current_price)) / impulse_size
    else:
        retrace = (float(current_price) - float(impulse_extreme)) / impulse_size
    return retrace, impulse_size


def _impulse_at_event(
    df: pd.DataFrame,
    bias: str,
    protected_idx: int,
    event_i: int,
    event_kind: str,
) -> Tuple[float, float]:
    """Origin / extreme at CHoCH or BOS bar."""
    if event_kind == 'choch' and bias == 'bearish':
        # Was bullish → bearish CHoCH
        _, origin = _max_body_high_between(df, protected_idx, event_i)
        extreme = _body_low(df, event_i)
        return float(origin), float(extreme)
    if event_kind == 'choch' and bias == 'bullish':
        _, origin = _min_body_low_between(df, protected_idx, event_i)
        extreme = _body_high(df, event_i)
        return float(origin), float(extreme)
    if event_kind == 'bos' and bias == 'bullish':
        hl_idx, origin = _min_body_low_between(df, protected_idx, event_i)
        _, extreme = _max_body_high_between(df, hl_idx, event_i)
        return float(origin), float(extreme)
    if event_kind == 'bos' and bias == 'bearish':
        lh_idx, origin = _max_body_high_between(df, protected_idx, event_i)
        _, extreme = _min_body_low_between(df, lh_idx, event_i)
        return float(origin), float(extreme)
    return 0.0, 0.0


def _extend_impulse_to_bar(
    df: pd.DataFrame,
    direction: str,
    origin: float,
    extreme: float,
    from_i: int,
    to_i: int,
) -> float:
    d = str(direction).lower()
    ext = float(extreme)
    for j in range(from_i, to_i + 1):
        if d == 'bullish':
            ext = max(ext, _body_high(df, j))
        else:
            ext = min(ext, _body_low(df, j))
    return ext


def _poi_start_index(df: pd.DataFrame, poi_touch_time) -> int:
    if poi_touch_time is None:
        return 0
    try:
        from radar_gates import parse_radar_dt
        anchor = parse_radar_dt(poi_touch_time)
        if anchor is None:
            return 0
        if 'time' in df.columns:
            for i in range(len(df)):
                t = df['time'].iloc[i]
                if hasattr(t, 'to_pydatetime'):
                    t = t.to_pydatetime()
                if t >= anchor.replace(tzinfo=None) if getattr(t, 'tzinfo', None) is None else t >= anchor:
                    return i
        for i in range(len(df.index)):
            if df.index[i] >= anchor:
                return i
    except Exception:
        pass
    return 0


def run_h4_range_engine(
    df_4h: pd.DataFrame,
    required_direction: str,
    poi_touch_time=None,
    fw: int = 2,
) -> Dict[str, Any]:
    """
  Run body-only 4H dealing range SM. Returns chochs, bos_list, impulse anchors,
  and metadata for radar / Telegram.
    """
    empty: Dict[str, Any] = {
        'chochs': [],
        'bos_list': [],
        'bias': 'neutral',
        'impulse_origin': None,
        'impulse_extreme': None,
        'initial_choch_price': None,
        'hl': None,
        'hh': None,
        'lh': None,
        'll': None,
    }
    if df_4h is None or len(df_4h) < 5:
        return empty

    df = df_4h.reset_index(drop=True) if 'open' not in df_4h.columns else df_4h.copy()
    if 'open' not in df.columns:
        return empty

    fw = max(int(fw), 2)
    swing_highs, swing_lows = _detect_fractal_swings(df, fw)
    chain = _alternating_chain(df, swing_highs, swing_lows)
    if len(chain) < 2:
        return empty

    p0, p1 = chain[0], chain[1]
    if p0[0] == 'L' and p1[0] == 'H':
        bias = 'bullish'
        protected_idx, protected_pivot = p0[1], p0[2]
        target_idx, target_pivot = p1[1], p1[2]
    elif p0[0] == 'H' and p1[0] == 'L':
        bias = 'bearish'
        protected_idx, protected_pivot = p0[1], p0[2]
        target_idx, target_pivot = p1[1], p1[2]
    else:
        return empty

    chochs: List[CHoCH] = []
    bos_list: List[BOS] = []
    start_i = max(int(protected_idx), int(target_idx)) + 1
    last_event_bar = start_i - 1
    target_armed = True
    event_impulse: Dict[int, Tuple[float, float, str]] = {}

    def _rearm_target(bar_i: int) -> None:
        nonlocal target_armed
        if target_idx is not None and int(target_idx) + fw <= bar_i:
            target_armed = True

    for i in range(start_i, len(df)):
        close = float(df['close'].iloc[i])
        ct = _bar_time(df, i)
        event_at_bar = False

        lo_p = float(protected_pivot)
        hi_p = float(target_pivot)

        if bias == 'bullish' and lo_p <= close <= hi_p:
            _rearm_target(i)
            if not target_armed:
                bh = _body_high(df, i)
                if bh > float(target_pivot):
                    target_idx = i
                    target_pivot = bh
            continue
        if bias == 'bearish' and hi_p >= close >= lo_p:
            _rearm_target(i)
            if not target_armed:
                bl = _body_low(df, i)
                if bl < float(target_pivot):
                    target_idx = i
                    target_pivot = bl
            continue

        if not target_armed:
            _rearm_target(i)

        if bias == 'bullish' and i > last_event_bar and close < protected_pivot - 1e-12:
            old_prot = int(protected_idx)
            old_tgt = int(target_idx)
            win_lo = min(old_prot, old_tgt)
            lh_idx, lh_px = _max_body_high_between(df, win_lo, i)
            ll_idx = i
            ll_px = _body_low(df, i)
            o, e = float(lh_px), float(ll_px)
            event_impulse[i] = (o, e, 'choch')
            bias = 'bearish'
            protected_idx, protected_pivot = lh_idx, lh_px
            target_idx, target_pivot = ll_idx, ll_px
            last_event_bar = i
            event_at_bar = True
            target_armed = False
            broken = swing_pt(df, old_prot, 'low')
            ev = CHoCH(
                index=i,
                direction='bearish',
                break_price=lo_p,
                previous_trend='bullish',
                candle_time=ct,
                swing_broken=broken,
            )
            chochs.append(ev)

        elif bias == 'bearish' and i > last_event_bar and close > protected_pivot + 1e-12:
            old_prot = int(protected_idx)
            old_tgt = int(target_idx)
            win_lo = min(old_prot, old_tgt)
            hl_idx, hl_px = _min_body_low_between(df, win_lo, i)
            hh_idx = i
            hh_px = _body_high(df, i)
            o, e = float(hl_px), float(hh_px)
            event_impulse[i] = (o, e, 'choch')
            bias = 'bullish'
            protected_idx, protected_pivot = hl_idx, hl_px
            target_idx, target_pivot = hh_idx, hh_px
            last_event_bar = i
            event_at_bar = True
            target_armed = False
            broken = swing_pt(df, old_prot, 'high')
            ev = CHoCH(
                index=i,
                direction='bullish',
                break_price=hi_p,
                previous_trend='bearish',
                candle_time=ct,
                swing_broken=broken,
            )
            chochs.append(ev)

        elif (
            bias == 'bullish'
            and target_armed
            and i > last_event_bar
            and close > target_pivot + 1e-12
            and target_idx is not None
        ):
            old_target_idx = int(target_idx)
            hl_idx, hl_px = _min_body_low_between(df, old_target_idx, i)
            hh_idx, hh_px = _max_body_high_between(df, old_target_idx + 1, i)
            o, e = float(hl_px), float(hh_px)
            event_impulse[i] = (o, e, 'bos')
            protected_idx, protected_pivot = hl_idx, hl_px
            target_idx, target_pivot = hh_idx, hh_px
            last_event_bar = i
            event_at_bar = True
            target_armed = False
            br_h = swing_pt(df, old_target_idx, 'high')
            ev = BOS(
                index=i,
                direction='bullish',
                break_price=hh_px,
                candle_time=ct,
                swing_broken=br_h,
            )
            bos_list.append(ev)

        elif (
            bias == 'bearish'
            and target_armed
            and i > last_event_bar
            and close < target_pivot - 1e-12
            and target_idx is not None
        ):
            old_target_idx = int(target_idx)
            lh_idx, lh_px = _max_body_high_between(df, old_target_idx, i)
            ll_idx, ll_px = _min_body_low_between(df, old_target_idx + 1, i)
            o, e = float(lh_px), float(ll_px)
            event_impulse[i] = (o, e, 'bos')
            protected_idx, protected_pivot = lh_idx, lh_px
            target_idx, target_pivot = ll_idx, ll_px
            last_event_bar = i
            event_at_bar = True
            target_armed = False
            br_l = swing_pt(df, old_target_idx, 'low')
            ev = BOS(
                index=i,
                direction='bearish',
                break_price=ll_px,
                candle_time=ct,
                swing_broken=br_l,
            )
            bos_list.append(ev)

        elif not target_armed and not event_at_bar:
            if bias == 'bullish':
                bh = _body_high(df, i)
                if bh > float(target_pivot):
                    target_idx = i
                    target_pivot = bh
            elif bias == 'bearish':
                bl = _body_low(df, i)
                if bl < float(target_pivot):
                    target_idx = i
                    target_pivot = bl

    req = str(required_direction or '').lower()
    poi_i = _poi_start_index(df, poi_touch_time)

    aligned_chochs = [c for c in chochs if c.direction == req and c.index >= poi_i]
    aligned_bos = [b for b in bos_list if b.direction == req and b.index >= poi_i]

    initial_choch_price = None
    if aligned_chochs:
        initial_choch_price = float(aligned_chochs[0].break_price)

    latest_event = None
    signal_type = None
    if aligned_chochs:
        latest_event = aligned_chochs[-1]
        signal_type = 'CHoCH'
    elif aligned_bos:
        latest_event = aligned_bos[-1]
        signal_type = 'BOS'

    impulse_origin = impulse_extreme = None
    if latest_event is not None:
        ei = int(latest_event.index)
        if ei in event_impulse:
            impulse_origin, impulse_extreme, _ = event_impulse[ei]
        else:
            impulse_origin, impulse_extreme = _impulse_at_event(
                df,
                latest_event.direction,
                int(getattr(latest_event.swing_broken, 'index', ei - 1)),
                ei,
                'choch' if signal_type == 'CHoCH' else 'bos',
            )
        impulse_extreme = _extend_impulse_to_bar(
            df,
            latest_event.direction,
            impulse_origin,
            impulse_extreme,
            ei,
            len(df) - 1,
        )

    hl = hh = lh = ll = None
    if bias == 'bullish':
        hl, hh = float(protected_pivot), float(target_pivot)
    elif bias == 'bearish':
        lh, ll = float(protected_pivot), float(target_pivot)

    return {
        'chochs': chochs,
        'bos_list': bos_list,
        'aligned_chochs': aligned_chochs,
        'aligned_bos': aligned_bos,
        'latest_event': latest_event,
        'signal_type': signal_type,
        'bias': bias,
        'impulse_origin': impulse_origin,
        'impulse_extreme': impulse_extreme,
        'initial_choch_price': initial_choch_price,
        'hl': hl,
        'hh': hh,
        'lh': lh,
        'll': ll,
    }