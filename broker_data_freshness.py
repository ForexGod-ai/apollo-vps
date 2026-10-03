"""
V56: Validate TradeHistorySyncer (8767) payloads — reject stale zombie cache.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse


def resolve_trade_sync_url() -> str:
    """TradeHistorySyncer base URL — env chain, default localhost (HttpListener cBot)."""
    raw = (
        os.getenv('CTRADER_SYNC_URL')
        or os.getenv('TRADE_SYNC_URL')
        or os.getenv('CTRADER_API_URL')
        or 'http://localhost:8767/'
    ).strip()
    if not raw.endswith('/'):
        raw += '/'
    return raw


def trade_sync_fetch_attempts() -> List[Tuple[str, Dict[str, str]]]:
    """
    HTTP GET attempts for TradeHistorySyncer (Windows HttpListener = localhost prefix).
    127.0.0.1 requests must send Host: localhost to avoid 400 Invalid Hostname.
    """
    primary = resolve_trade_sync_url()
    parsed = urlparse(primary)
    port = parsed.port or 8767
    attempts: List[Tuple[str, Dict[str, str]]] = []
    seen: set[str] = set()

    def _add(url: str, headers: Optional[Dict[str, str]] = None) -> None:
        if url not in seen:
            seen.add(url)
            attempts.append((url, headers or {}))

    _add(primary, {})
    _add(f'http://127.0.0.1:{port}/', {'Host': 'localhost'})
    host = (parsed.hostname or '').lower()
    if host not in ('localhost', '127.0.0.1'):
        _add(f'http://localhost:{port}/', {'Host': 'localhost'})

    return attempts


# cBot UpdateInterval default 10s — allow 2 min before calling data stale
MAX_BROKER_AGE_SECONDS = 120


def disk_payload_fresh(
    path: Path,
    max_age_seconds: Optional[float] = None,
) -> bool:
    """True if path exists and JSON account.last_update is within max_age."""
    if max_age_seconds is None:
        max_age_seconds = MAX_BROKER_AGE_SECONDS
    data = load_local_trade_history(path)
    return data is not None and is_payload_fresh(data, max_age_seconds=max_age_seconds)


def parse_last_update(ts: Any) -> Optional[datetime]:
    """Parse account.last_update from TradeHistorySyncer JSON."""
    if ts is None:
        return None
    try:
        s = str(ts).strip()
        if not s:
            return None
        # cBot format: yyyy-MM-dd HH:mm:ss UTC (TradeHistorySyncer V57+ uses DateTime.UtcNow)
        if 'T' in s:
            s = s.replace('Z', '+00:00')
            dt = datetime.fromisoformat(s)
        else:
            dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def payload_age_seconds(data: dict) -> Optional[float]:
    """Seconds since account.last_update in payload; None if unparseable."""
    account = data.get('account') or {}
    dt = parse_last_update(account.get('last_update'))
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    return max(0.0, (now - dt).total_seconds())


def is_payload_fresh(data: dict, max_age_seconds: float = MAX_BROKER_AGE_SECONDS) -> bool:
    age = payload_age_seconds(data)
    if age is None:
        return False
    return age <= max_age_seconds


def load_local_trade_history(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def incoming_is_newer_or_equal(incoming: dict, local: Optional[dict]) -> bool:
    """True if incoming last_update >= local (safe to overwrite file)."""
    if local is None:
        return True
    inc_dt = parse_last_update((incoming.get('account') or {}).get('last_update'))
    loc_dt = parse_last_update((local.get('account') or {}).get('last_update'))
    if inc_dt is None:
        return False
    if loc_dt is None:
        return True
    return inc_dt >= loc_dt


def format_stale_reason(data: dict) -> str:
    age = payload_age_seconds(data)
    lu = (data.get('account') or {}).get('last_update', '?')
    if age is None:
        return f"last_update missing/unparseable ({lu!r})"
    return f"last_update={lu} age={age:.0f}s (max {MAX_BROKER_AGE_SECONDS:.0f}s)"
