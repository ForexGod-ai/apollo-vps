"""Shared POI box helpers — daily_scanner lifecycle + multi_tf_radar gate (V45 wick)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def price_in_poi_box(
    price: float,
    poi_bottom: Optional[float],
    poi_top: Optional[float],
) -> bool:
    """Preț live strict în caseta POI [poi_bottom, poi_top]."""
    if poi_bottom is None or poi_top is None:
        return False
    lo = min(float(poi_bottom), float(poi_top))
    hi = max(float(poi_bottom), float(poi_top))
    return lo <= float(price) <= hi


def poi_box_intersects_wick(
    candle_high: Optional[float],
    candle_low: Optional[float],
    poi_bottom: Optional[float],
    poi_top: Optional[float],
) -> bool:
    """Wick Daily intersectează POI — trigger pândă radar / lifecycle MONITORING."""
    if poi_bottom is None or poi_top is None:
        return False
    if candle_high is None or candle_low is None:
        return False
    lo = min(float(poi_bottom), float(poi_top))
    hi = max(float(poi_bottom), float(poi_top))
    return float(candle_low) <= hi and float(candle_high) >= lo


def poi_touch_active(
    price: Optional[float],
    poi_bottom: Optional[float],
    poi_top: Optional[float],
    d1_wick_high: Optional[float] = None,
    d1_wick_low: Optional[float] = None,
) -> bool:
    """V45: wick Daily ∩ POI sau preț în POI."""
    if poi_touch_via_wick(poi_bottom, poi_top, d1_wick_high, d1_wick_low):
        return True
    if price is not None and price_in_poi_box(price, poi_bottom, poi_top):
        return True
    return False


def poi_touch_via_wick(
    poi_bottom: Optional[float],
    poi_top: Optional[float],
    d1_wick_high: Optional[float],
    d1_wick_low: Optional[float],
) -> bool:
    return poi_box_intersects_wick(d1_wick_high, d1_wick_low, poi_bottom, poi_top)


def poi_bounds_from_stored(stored: dict) -> tuple[Optional[float], Optional[float]]:
    """POI top/bottom din JSON (poi_* sau fvg_* legacy)."""
    top = stored.get('poi_top') if stored.get('poi_top') is not None else stored.get('fvg_top')
    bottom = (
        stored.get('poi_bottom')
        if stored.get('poi_bottom') is not None
        else stored.get('fvg_bottom')
    )
    if top is None or bottom is None:
        return None, None
    return float(bottom), float(top)


def _parse_iso_ts(ts: Optional[str]) -> Optional[datetime]:
    if ts is None:
        return None
    try:
        s = str(ts).replace('Z', '+00:00')
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _bar_open_iso(df: Any, row_idx: int) -> Optional[str]:
    """ISO timestamp for bar open (matches multi_tf_radar D1 anchor convention)."""
    if df is None or getattr(df, 'empty', True):
        return None
    try:
        row = df.iloc[row_idx]
        for col in ('time', 'datetime', 'Date', 'date', 'timestamp'):
            if col in df.columns:
                dt = _parse_iso_ts(row[col])
                if dt is not None:
                    return dt.isoformat()
        idx = df.index[row_idx]
        dt = _parse_iso_ts(idx)
        if dt is not None:
            return dt.isoformat()
    except Exception:
        pass
    return None


def find_first_poi_touch_time(
    df_d1: Any,
    df_h4: Any,
    poi_bottom: Optional[float],
    poi_top: Optional[float],
) -> Optional[str]:
    """
    V52.2: Prima bară (cronologic) unde high/low intersectează caseta POI.
    Scanează D1 apoi H4 — returnează timestamp deschidere bară.
    """
    if poi_bottom is None or poi_top is None:
        return None
    for df in (df_d1, df_h4):
        if df is None or getattr(df, 'empty', True):
            continue
        if 'high' not in df.columns or 'low' not in df.columns:
            continue
        for i in range(len(df)):
            try:
                hi = float(df.iloc[i]['high'])
                lo = float(df.iloc[i]['low'])
            except Exception:
                continue
            if poi_box_intersects_wick(hi, lo, poi_bottom, poi_top):
                ts = _bar_open_iso(df, i)
                if ts:
                    return ts
    return None


def resolve_poi_touch_anchor(
    *,
    d1_touch_time: Optional[str],
    now_ts: str,
    historical_touch: Optional[str] = None,
    existing: Optional[str] = None,
) -> str:
    """
    V52.2: Ancoră POI = cel mai devreme timestamp valid.
    Nu avansează ancoră în viitor față de `existing`.
    """
    candidates: list[tuple[str, datetime]] = []
    for raw in (existing, historical_touch, d1_touch_time):
        if not raw:
            continue
        dt = _parse_iso_ts(raw)
        if dt is not None:
            candidates.append((raw, dt))
    if not candidates:
        return now_ts
    return min(candidates, key=lambda x: x[1])[0]
