#!/usr/bin/env python3
"""
V39.5 — Shared economic calendar loader for executor, monitor, and fetcher.

Priority: data/upcoming_news.json → economic_calendar.json (all custom_events_* sections).
All datetimes normalized to UTC.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

SCRIPT_DIR = Path(__file__).parent.resolve()
UPCOMING_NEWS_FILE = SCRIPT_DIR / "data" / "upcoming_news.json"
CALENDAR_FILE = SCRIPT_DIR / "economic_calendar.json"

MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF"]

# Liquidity Sniper windows (minutes)
NEW_ENTRY_BLOCK_BEFORE_MIN = 15
BE_PROTECT_BEFORE_MIN = 2


def get_affected_currencies(symbol: str) -> Set[str]:
    """Map trading symbol to currencies affected by macro news."""
    symbol_upper = symbol.upper().replace(" ", "").replace("/", "")
    affected: Set[str] = set()
    for ccy in MAJOR_CURRENCIES:
        if ccy in symbol_upper:
            affected.add(ccy)
    if any(x in symbol_upper for x in ("BTC", "XAU", "GOLD")):
        affected.add("USD")
    return affected


def parse_event_datetime(event: Dict) -> Optional[datetime]:
    """Parse event dict to timezone-aware UTC datetime."""
    dt_str = event.get("datetime_utc") or event.get("datetime") or event.get("time_iso")
    if dt_str:
        try:
            dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass

    date_str = event.get("date", "")
    time_str = event.get("time", "12:00")
    if not date_str:
        return None
    if str(time_str).lower() in ("tentative", "all day", "day"):
        time_str = "00:00"
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _normalize_event(raw: Dict, source: str) -> Optional[Dict]:
    impact = str(raw.get("impact", "High")).strip()
    if impact.lower() not in ("high", "high impact expected", "red"):
        return None

    currency = str(raw.get("currency", "")).upper()
    if currency not in MAJOR_CURRENCIES:
        return None

    event_dt = parse_event_datetime(raw)
    if event_dt is None:
        return None

    return {
        "date": event_dt.strftime("%Y-%m-%d"),
        "time": event_dt.strftime("%H:%M"),
        "datetime_utc": event_dt.isoformat(),
        "currency": currency,
        "event": raw.get("event") or raw.get("title") or "Unknown",
        "impact": "High",
        "forecast": str(raw.get("forecast", "") or ""),
        "previous": str(raw.get("previous", "") or ""),
        "source": source,
    }


def load_from_upcoming_news(days_ahead: int = 14) -> List[Dict]:
    if not UPCOMING_NEWS_FILE.exists():
        return []

    try:
        with open(UPCOMING_NEWS_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return []

    if isinstance(payload, dict):
        raw_events = payload.get("events", [])
    elif isinstance(payload, list):
        raw_events = payload
    else:
        return []

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days_ahead)
    events: List[Dict] = []

    for raw in raw_events:
        norm = _normalize_event(raw, raw.get("source", "upcoming_news"))
        if norm is None:
            continue
        dt = parse_event_datetime(norm)
        if dt is None or dt < now - timedelta(hours=1) or dt > end:
            continue
        events.append(norm)

    return events


def load_from_manual_calendar(days_ahead: int = 14) -> List[Dict]:
    if not CALENDAR_FILE.exists():
        return []

    try:
        with open(CALENDAR_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days_ahead)
    events: List[Dict] = []

    for key, section in data.items():
        if not key.startswith("custom_events_") or not isinstance(section, list):
            continue
        for raw in section:
            norm = _normalize_event(raw, "manual_calendar")
            if norm is None:
                continue
            dt = parse_event_datetime(norm)
            if dt is None or dt < now - timedelta(hours=1) or dt > end:
                continue
            events.append(norm)

    return events


def load_high_impact_events(days_ahead: int = 14) -> List[Dict]:
    """
    Unified loader for /news, executor BE guard, and liquidity sniper blackout.

    Priority: data/upcoming_news.json (FF daily sync) → economic_calendar.json gaps.
    All consumers should use this — do not read economic_calendar.json directly.
    """
    upcoming = load_from_upcoming_news(days_ahead=days_ahead)
    manual = load_from_manual_calendar(days_ahead=days_ahead)

    seen: Set[str] = set()
    merged: List[Dict] = []

    for event in upcoming + manual:
        key = f"{event['currency']}_{event['event']}_{event['date']}_{event['time']}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(event)

    merged.sort(key=lambda e: e.get("datetime_utc", ""))
    return merged


def minutes_until_event(event: Dict, now: Optional[datetime] = None) -> Optional[float]:
    """Positive = event in future; negative = event passed."""
    dt = parse_event_datetime(event)
    if dt is None:
        return None
    now = now or datetime.now(timezone.utc)
    return (dt - now).total_seconds() / 60.0


def find_relevant_events(
    symbol: str,
    days_ahead: int = 1,
    high_only: bool = True,
) -> List[Tuple[Dict, float]]:
    """Return (event, minutes_until) for symbol's currencies."""
    currencies = get_affected_currencies(symbol)
    if not currencies:
        return []

    results: List[Tuple[Dict, float]] = []
    for event in load_high_impact_events(days_ahead=days_ahead):
        if high_only and event.get("impact", "").lower() != "high":
            continue
        if event.get("currency", "").upper() not in currencies:
            continue
        mins = minutes_until_event(event)
        if mins is None:
            continue
        results.append((event, mins))

    return results


def liquidity_sniper_blocks_new_entry(symbol: str) -> str:
    """
    Block NEW entries 15 minutes before HIGH impact (spread/slippage protection).
    Returns block reason or empty string if clear.
    """
    for event, mins in find_relevant_events(symbol, days_ahead=1):
        if 0 <= mins <= NEW_ENTRY_BLOCK_BEFORE_MIN:
            name = event.get("event", "Unknown")
            ccy = event.get("currency", "")
            return (
                f"LIQUIDITY SNIPER: {ccy} {name} in {mins:.0f}min "
                f"— new entry blocked (spread protection, scanner active)"
            )
    return ""


def liquidity_sniper_be_candidates(symbol: Optional[str] = None) -> List[Tuple[Dict, float]]:
    """
    Events in T-2min window for BE protection on open positions.
    Optional symbol filter.
    """
    candidates: List[Tuple[Dict, float]] = []
    seen_keys: Set[str] = set()

    events = load_high_impact_events(days_ahead=1)
    now = datetime.now(timezone.utc)

    for event in events:
        key = f"{event['currency']}_{event['event']}_{event['date']}_{event['time']}"
        if key in seen_keys:
            continue

        dt = parse_event_datetime(event)
        if dt is None:
            continue

        mins = (dt - now).total_seconds() / 60.0
        # Window: 1.5 to 2.5 minutes before event (executor polls ~5s)
        if not (BE_PROTECT_BEFORE_MIN - 0.5 <= mins <= BE_PROTECT_BEFORE_MIN + 0.5):
            continue

        if symbol:
            currencies = get_affected_currencies(symbol)
            if event.get("currency", "").upper() not in currencies:
                continue

        seen_keys.add(key)
        candidates.append((event, mins))

    return candidates
