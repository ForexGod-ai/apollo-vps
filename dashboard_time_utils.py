"""
V40.5 — Dashboard timezone helpers (UTC broker feed → Europe/Bucharest display).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import pytz
except ImportError:
    pytz = None  # type: ignore

DISPLAY_TZ = 'Europe/Bucharest'


def _parse_utc(dt_str: str) -> Optional[datetime]:
    """Parse cTrader/sync timestamp as UTC (naive strings = UTC server time)."""
    if not dt_str or not str(dt_str).strip():
        return None
    raw = str(dt_str).strip()
    try:
        if raw.endswith('Z'):
            return datetime.fromisoformat(raw.replace('Z', '+00:00'))
        normalized = raw.replace(' ', 'T')
        if '.' in normalized:
            base, frac = normalized.split('.', 1)
            normalized = f"{base}.{frac[:6]}"
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def format_close_time_for_display(
    dt_str: str,
    tz_name: str = DISPLAY_TZ,
) -> Dict[str, str]:
    """
    Convert UTC close_time to Romania display fields for dashboard JSON.

    Returns dict with close_time_utc, close_time_display, close_time_iso.
    """
    utc_dt = _parse_utc(dt_str)
    if utc_dt is None:
        return {
            'close_time_utc': dt_str or '',
            'close_time_display': (dt_str or '')[:16].replace('T', ' '),
            'close_time_iso': dt_str or '',
        }

    if pytz is not None:
        local_dt = utc_dt.astimezone(pytz.timezone(tz_name))
    else:
        # Fallback: fixed UTC+3 when pytz unavailable
        from datetime import timedelta
        local_dt = utc_dt + timedelta(hours=3)
        local_dt = local_dt.replace(tzinfo=timezone.utc)

    return {
        'close_time_utc': utc_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        'close_time_display': local_dt.strftime('%Y-%m-%d %H:%M'),
        'close_time_iso': local_dt.isoformat(),
    }


def localize_closed_trades(
    closed_trades: List[Dict[str, Any]],
    tz_name: str = DISPLAY_TZ,
) -> List[Dict[str, Any]]:
    """Enrich each closed trade with RO display times; preserve UTC for sorting."""
    out: List[Dict[str, Any]] = []
    for trade in closed_trades:
        item = dict(trade)
        raw = item.get('close_time') or item.get('closeTime') or ''
        fields = format_close_time_for_display(raw, tz_name)
        item.update(fields)
        # Primary field used by legacy frontend substring — now RO local
        item['close_time'] = fields['close_time_display']
        out.append(item)
    return out


def localize_dashboard_payload(data: Dict[str, Any], tz_name: str = DISPLAY_TZ) -> Dict[str, Any]:
    """Apply timezone conversion to dashboard JSON before HTTP response."""
    payload = dict(data)
    payload['closed_trades'] = localize_closed_trades(
        payload.get('closed_trades') or [],
        tz_name,
    )
    payload['timezone'] = tz_name
    payload['timezone_label'] = 'ora României (Europe/Bucharest)'
    return payload
