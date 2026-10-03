#!/usr/bin/env python3
"""
📡 NEWS FETCHER V39.5 — DAILY + WEEKLY AUTO-SYNC
────────────────
🔱 AUTHORED BY ФорексГод 🔱
🏛️ Глитч Ин Матрикс 🏛️

Automatically downloads HIGH + MEDIUM impact economic events.
Populates data/upcoming_news.json for executor, monitor, and reminders.

Data Sources (merged into upcoming_news.json):
    1. ForexFactory mirror (thisweek + nextweek JSON; stale cache rejected after 48h)
    2. cTrader EconomicCalendarBot :8768 (if FF empty or any mirror feed failed)
    3. Manual economic_calendar.json (custom_events_*)
    4. Trading Economics API (only if merged result is empty)

V39.5 Weekly pipeline:
    --weekly  → 14-day horizon, FF mirror merge, state file tracks last run (7-day cadence)

Usage:
    python3 news_fetcher.py              # Fetch today + 7 days
    python3 news_fetcher.py --days 14    # Fetch today + 14 days
    python3 news_fetcher.py --weekly     # Weekly auto-sync (14 days, FF merge)
────────────────
"""

import json
import os
import sys
import time
import argparse
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Setup logging — UTF-8 safe stdout for Windows cp1252 compatibility
import io as _io
_utf8_stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'buffer') else sys.stdout
_stream_handler = logging.StreamHandler(_utf8_stdout)
_stream_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s'))
_logs_dir = Path(__file__).parent.resolve() / 'logs'
_logs_dir.mkdir(exist_ok=True)
_file_handler = logging.FileHandler(_logs_dir / 'news_fetcher.log', mode='a', encoding='utf-8')
_file_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[_stream_handler, _file_handler])
logger = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    logger.error("❌ requests not installed — run: pip install requests")
    HAS_REQUESTS = False

# ━━━ CONSTANTS ━━━
SCRIPT_DIR = Path(__file__).parent.resolve()
OUTPUT_FILE = SCRIPT_DIR / 'data' / 'upcoming_news.json'
CALENDAR_FILE = SCRIPT_DIR / 'economic_calendar.json'
LOGS_DIR = SCRIPT_DIR / 'logs'
WEEKLY_STATE_FILE = SCRIPT_DIR / 'data' / 'news_fetcher_weekly_state.json'
FF_MIRROR_CACHE_DIR = SCRIPT_DIR / 'data' / 'ff_mirror_cache'
WEEKLY_INTERVAL_DAYS = 7

FF_MIRROR_URLS = {
    'thisweek': 'https://nfs.faireconomy.media/ff_calendar_thisweek.json',
}

# Deprecated on faireconomy (404) — tried optionally; do not fail sync if missing.
FF_MIRROR_OPTIONAL_URLS = {
    'nextweek': 'https://nfs.faireconomy.media/ff_calendar_nextweek.json',
}

_AGENT_DEBUG_LOG = Path(__file__).resolve().parent / '.cursor' / 'debug-ef6f10.log'


def _agent_debug_log(hypothesis_id: str, location: str, message: str, data: Optional[dict] = None) -> None:
    # #region agent log
    try:
        import json as _json_dbg
        _AGENT_DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_AGENT_DEBUG_LOG, 'a', encoding='utf-8') as _df:
            _df.write(_json_dbg.dumps({
                'sessionId': 'ef6f10',
                'hypothesisId': hypothesis_id,
                'location': location,
                'message': message,
                'data': data or {},
                'timestamp': int(time.time() * 1000),
            }) + '\n')
    except Exception:
        pass
    # #endregion

FF_MIRROR_RETRY_DELAYS_S = (2, 5, 10)
FF_MIRROR_CACHE_MAX_AGE_HOURS = 48

_BROWSER_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
}

IMPACT_MAP_FF = {
    'High': 'High',
    'Medium': 'Medium',
    'Low': 'Low',
    'Holiday': 'Low',
    'Non-Economic': 'Low',
}


def resolve_ctrader_calendar_url() -> str:
    raw = (os.getenv('CTRADER_CALENDAR_URL') or 'http://localhost:8768/calendar').strip()
    return raw


def horizon_end(now: datetime, days_ahead: int) -> datetime:
    """Inclusive end of fetch window (through end of day N)."""
    return now + timedelta(days=days_ahead, hours=23, minutes=59)


def event_in_horizon(event_dt_utc: datetime, now: datetime, days_ahead: int) -> bool:
    if event_dt_utc.tzinfo is None:
        event_dt_utc = event_dt_utc.replace(tzinfo=timezone.utc)
    event_dt_utc = event_dt_utc.astimezone(timezone.utc)
    return now <= event_dt_utc <= horizon_end(now, days_ahead)


def _parse_ff_mirror_datetime(date_str: str) -> Optional[datetime]:
    try:
        event_dt = datetime.fromisoformat(date_str)
        if event_dt.tzinfo is None:
            event_dt = event_dt.replace(tzinfo=timezone.utc)
        return event_dt.astimezone(timezone.utc)
    except Exception:
        return None


def _raw_ff_events_in_horizon(raw_items: List[Dict], days_ahead: int) -> int:
    """Count raw mirror rows with parseable dates inside the horizon."""
    now = datetime.now(timezone.utc)
    count = 0
    for item in raw_items:
        dt = _parse_ff_mirror_datetime(item.get('date', '') or '')
        if dt and event_in_horizon(dt, now, days_ahead):
            count += 1
    return count

# Currencies we trade
MAJOR_CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'NZD', 'CAD', 'CHF']

# Country → Currency mapping for Trading Economics
COUNTRY_TO_CURRENCY = {
    'United States': 'USD', 'Euro Area': 'EUR', 'United Kingdom': 'GBP',
    'Japan': 'JPY', 'Australia': 'AUD', 'New Zealand': 'NZD',
    'Canada': 'CAD', 'Switzerland': 'CHF', 'Germany': 'EUR',
    'France': 'EUR', 'Italy': 'EUR', 'Spain': 'EUR',
    'U.S.': 'USD', 'UK': 'GBP', 'EU': 'EUR',
    # Aliases
    'united states': 'USD', 'euro area': 'EUR', 'united kingdom': 'GBP',
    'japan': 'JPY', 'australia': 'AUD', 'new zealand': 'NZD',
    'canada': 'CAD', 'switzerland': 'CHF', 'germany': 'EUR',
}


def _ff_mirror_cache_path(label: str) -> Path:
    FF_MIRROR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return FF_MIRROR_CACHE_DIR / f'{label}.json'


def _load_ff_mirror_cache(label: str, days_ahead: int = 14) -> List[Dict]:
    cache_path = _ff_mirror_cache_path(label)
    if not cache_path.exists():
        return []
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        cached_at_str = None
        if isinstance(payload, list):
            cached = payload
        else:
            cached_at_str = payload.get('cached_at')
            cached = payload.get('events', [])
        if cached_at_str:
            cached_at = datetime.fromisoformat(str(cached_at_str).replace('Z', '+00:00'))
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            age_h = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600.0
            if age_h > FF_MIRROR_CACHE_MAX_AGE_HOURS:
                logger.warning(
                    f"⚠️ FF mirror cache rejected ({label}): "
                    f"cached_at {age_h:.0f}h ago (max {FF_MIRROR_CACHE_MAX_AGE_HOURS}h)"
                )
                return []
        in_window = _raw_ff_events_in_horizon(cached, days_ahead)
        if not in_window:
            logger.warning(
                f"⚠️ FF mirror cache rejected ({label}): "
                f"0 events in next {days_ahead}d window"
            )
            return []
        logger.info(
            f"📂 FF mirror cache hit: {label} ({len(cached)} raw, {in_window} in horizon)"
        )
        return cached
    except Exception as e:
        logger.warning(f"⚠️ FF mirror cache read failed ({label}): {e}")
        return []


def _save_ff_mirror_cache(label: str, events: List[Dict]) -> None:
    if not events:
        return
    try:
        cache_path = _ff_mirror_cache_path(label)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump({
                'cached_at': datetime.now(timezone.utc).isoformat(),
                'events': events,
            }, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"⚠️ FF mirror cache write failed ({label}): {e}")


def _parse_ff_mirror_json_body(text: str) -> Optional[List[Dict]]:
    stripped = (text or '').lstrip()
    if not stripped.startswith('['):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        return data
    return None


def _fetch_ff_mirror_feed(
    label: str, url: str, days_ahead: int = 14,
) -> Tuple[List[Dict], bool]:
    """Fetch one FF mirror JSON; on failure use last good cache. Returns (events, got_live_json)."""
    if not HAS_REQUESTS:
        return _load_ff_mirror_cache(label, days_ahead), False

    last_error = ''
    for attempt, delay in enumerate((0,) + FF_MIRROR_RETRY_DELAYS_S):
        if delay:
            time.sleep(delay)
        try:
            resp = requests.get(url, timeout=15, headers=_BROWSER_HEADERS)
            ctype = resp.headers.get('Content-Type', '')
            preview = (resp.text or '')[:120]
            logger.debug(
                f"{label} attempt {attempt + 1}: HTTP {resp.status_code} "
                f"Content-Type={ctype!r} preview={preview!r}"
            )

            if resp.status_code in (429, 500, 502, 503, 504):
                last_error = f"HTTP {resp.status_code}"
                continue

            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code}"
                logger.warning(
                    f"⚠️ {label}: HTTP {resp.status_code} — "
                    f"Failed to fetch news: mirror error (preview={preview!r})"
                )
                break

            data = _parse_ff_mirror_json_body(resp.text)
            if data is None:
                last_error = 'non-JSON or HTML response'
                logger.error(
                    f"❌ {label}: Failed to fetch news: mirror returned HTML or invalid JSON "
                    f"(Content-Type={ctype!r}, preview={preview!r})"
                )
                continue

            if not data:
                last_error = 'empty JSON list'
                logger.warning(f"⚠️ {label}: empty JSON payload")
                break

            _save_ff_mirror_cache(label, data)
            logger.info(f"📥 {label}: {len(data)} events (live)")
            return data, True

        except requests.exceptions.RequestException as exc:
            last_error = str(exc)
            logger.warning(f"⚠️ {label}: fetch error ({exc})")
            continue

    if last_error:
        logger.warning(f"⚠️ {label}: live fetch failed ({last_error}) — trying cache")
    return _load_ff_mirror_cache(label, days_ahead), False


def parse_ff_mirror_items(
    all_raw: List[Dict],
    days_ahead: int = 14,
    now: Optional[datetime] = None,
) -> List[Dict]:
    """Parse raw faireconomy FF mirror rows into normalized event dicts."""
    now = now or datetime.now(timezone.utc)
    events: List[Dict] = []
    for item in all_raw:
        impact = IMPACT_MAP_FF.get(item.get('impact', ''), 'Low')
        if impact not in ('High', 'Medium'):
            continue

        currency = item.get('country', '')
        if currency not in MAJOR_CURRENCIES:
            continue

        date_str = item.get('date', '')
        if not date_str:
            continue

        event_dt_utc = _parse_ff_mirror_datetime(date_str)
        if event_dt_utc is None:
            continue

        if not event_in_horizon(event_dt_utc, now, days_ahead):
            continue

        title = item.get('title', 'Unknown').strip()
        events.append({
            'date': event_dt_utc.strftime('%Y-%m-%d'),
            'time': event_dt_utc.strftime('%H:%M'),
            'datetime_utc': event_dt_utc.isoformat(),
            'currency': currency,
            'event': title,
            'impact': impact,
            'forecast': str(item.get('forecast', '') or ''),
            'previous': str(item.get('previous', '') or ''),
            'source': 'forexfactory_mirror',
        })
    return events


def fetch_forexfactory_mirror(days_ahead: int = 7) -> Tuple[List[Dict], bool]:
    """
    ForexFactory calendar via faireconomy.media free JSON mirror.
    Returns (parsed_events, any_feed_got_live_json).
    """
    if not HAS_REQUESTS:
        return [], False

    try:
        logger.info("📡 Fetching ForexFactory mirror (faireconomy.media)...")

        all_raw: List[Dict] = []
        thisweek_live = False
        for label, url in FF_MIRROR_URLS.items():
            chunk, live = _fetch_ff_mirror_feed(label, url, days_ahead)
            thisweek_live = live
            all_raw.extend(chunk)

        for label, url in FF_MIRROR_OPTIONAL_URLS.items():
            chunk, _live = _fetch_ff_mirror_feed(label, url, days_ahead)
            if chunk:
                all_raw.extend(chunk)

        if not all_raw:
            _agent_debug_log('H4', 'fetch_forexfactory_mirror', 'no raw FF rows', {
                'thisweek_live': thisweek_live, 'days_ahead': days_ahead,
            })
            return [], thisweek_live

        events = parse_ff_mirror_items(all_raw, days_ahead=days_ahead)
        _agent_debug_log('H4', 'fetch_forexfactory_mirror', 'FF parse result', {
            'raw_count': len(all_raw),
            'parsed_count': len(events),
            'high_count': sum(1 for e in events if e.get('impact') == 'High'),
            'thisweek_live': thisweek_live,
        })
        logger.info(f"✅ Parsed {len(events)} HIGH/MEDIUM events from ForexFactory mirror")
        return events, thisweek_live

    except Exception as e:
        logger.error(f"❌ ForexFactory mirror error: {e}")
        return [], False


def _normalize_ctrader_impact(raw: str) -> Optional[str]:
    s = str(raw or '').strip()
    if not s:
        return None
    if s.lower() in ('high', 'high impact expected', 'red'):
        return 'High'
    if s.lower() in ('medium', 'medium impact expected', 'orange', 'ora'):
        return 'Medium'
    if s in ('High', 'Medium'):
        return s
    return None


def fetch_ctrader_calendar(days_ahead: int = 14) -> List[Dict]:
    """EconomicCalendarBot HTTP feed (localhost:8768 by default)."""
    if not HAS_REQUESTS:
        return []

    url = resolve_ctrader_calendar_url()
    try:
        logger.info(f"📅 Fetching cTrader economic calendar ({url})...")
        resp = requests.get(url, timeout=10, headers=_BROWSER_HEADERS)
        if resp.status_code != 200:
            logger.error(
                f"❌ cTrader calendar HTTP {resp.status_code} — "
                f"Failed to fetch news (preview={(resp.text or '')[:120]!r})"
            )
            return []

        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            logger.error(f"❌ cTrader calendar JSONDecodeError: {exc}")
            return []

        if not data.get('success'):
            logger.error(
                f"❌ cTrader calendar success=false: {data.get('error', data.get('message', '?'))}"
            )
            return []

        raw_events = data.get('events', [])
        logger.info(f"📊 cTrader returned {len(raw_events)} raw events")

        now = datetime.now(timezone.utc)
        events: List[Dict] = []
        for item in raw_events:
            impact = _normalize_ctrader_impact(item.get('impact', ''))
            if impact not in ('High', 'Medium'):
                continue

            currency = str(item.get('currency', '')).upper()
            if currency not in MAJOR_CURRENCIES:
                continue

            time_str = item.get('time', '')
            if not time_str:
                continue
            try:
                event_dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                event_dt = event_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            if not event_in_horizon(event_dt, now, days_ahead):
                continue

            def _fmt_val(v) -> str:
                if v is None or v == 'null':
                    return ''
                return str(v)

            events.append({
                'date': event_dt.strftime('%Y-%m-%d'),
                'time': event_dt.strftime('%H:%M'),
                'datetime_utc': event_dt.isoformat(),
                'currency': currency,
                'event': str(item.get('event', 'Unknown')).strip(),
                'impact': impact,
                'forecast': _fmt_val(item.get('forecast')),
                'previous': _fmt_val(item.get('previous')),
                'source': 'ctrader_calendar',
            })

        logger.info(f"✅ Parsed {len(events)} HIGH/MEDIUM events from cTrader calendar")
        return events

    except requests.exceptions.ConnectionError:
        logger.error(
            f"❌ Cannot connect to cTrader calendar at {url} — "
            "is EconomicCalendarBot running on port 8768?"
        )
        return []
    except Exception as e:
        logger.error(f"❌ cTrader calendar error: {e}")
        return []


def fetch_trading_economics(days_ahead: int = 7) -> List[Dict]:
    """
    Source #2: Trading Economics calendar endpoint.
    May require API key — used as fallback.
    """
    if not HAS_REQUESTS:
        return []

    try:
        logger.info("📡 [Source 1] Fetching from Trading Economics (free tier)...")

        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=days_ahead)

        url = "https://api.tradingeconomics.com/calendar"
        params = {
            'f': 'json',
            'd1': now.strftime('%Y-%m-%d'),
            'd2': end_date.strftime('%Y-%m-%d'),
        }
        te_key = (os.getenv('TRADING_ECONOMICS_API_KEY') or os.getenv('TE_API_KEY') or '').strip()
        if te_key:
            params['c'] = te_key

        response = requests.get(url, params=params, timeout=20, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

        if response.status_code != 200:
            logger.warning(f"⚠️ Trading Economics returned HTTP {response.status_code}")
            return []

        raw_data = response.json()
        logger.info(f"📥 Received {len(raw_data)} raw events from Trading Economics")

        events = []
        for item in raw_data:
            importance = item.get('Importance', 1)
            # 3 = HIGH, 2 = MEDIUM — skip LOW (1)
            if importance < 2:
                continue

            country = item.get('Country', '')
            currency = COUNTRY_TO_CURRENCY.get(country, COUNTRY_TO_CURRENCY.get(country.lower(), ''))
            if not currency or currency not in MAJOR_CURRENCIES:
                continue

            event_date_str = item.get('Date', '')
            if not event_date_str:
                continue

            # Parse ISO date from Trading Economics
            try:
                # Format: "2026-03-11T13:30:00"
                event_dt = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            impact = 'High' if importance >= 3 else 'Medium'

            events.append({
                'date': event_dt.strftime('%Y-%m-%d'),
                'time': event_dt.strftime('%H:%M'),
                'datetime_utc': event_dt.isoformat(),
                'currency': currency,
                'event': item.get('Event', 'Unknown').strip(),
                'impact': impact,
                'forecast': str(item.get('Forecast', '') or ''),
                'previous': str(item.get('Previous', '') or ''),
                'source': 'trading_economics',
            })

        logger.info(f"✅ Parsed {len(events)} HIGH/MEDIUM events for major currencies")
        return events

    except requests.exceptions.Timeout:
        logger.warning("⏰ Trading Economics request timed out")
        return []
    except Exception as e:
        logger.error(f"❌ Trading Economics error: {e}")
        return []


def fetch_from_manual_calendar(days_ahead: int = 7) -> List[Dict]:
    """
    Source #1 (PRIMARY): Load from local economic_calendar.json.
    Scans ALL custom_events_* sections within the date window.
    """
    try:
        logger.info("📖 [Source 1] Loading from manual economic_calendar.json...")

        if not CALENDAR_FILE.exists():
            logger.warning("⚠️ economic_calendar.json not found")
            return []

        with open(CALENDAR_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        now = datetime.now(timezone.utc)

        events = []
        for section_name, section_events in data.items():
            if not section_name.startswith('custom_events_') or not isinstance(section_events, list):
                continue

            for e in section_events:
                try:
                    date_str = e.get('date', '')
                    time_str = e.get('time', '12:00')
                    if str(time_str).lower() in ('tentative', 'all day', 'day'):
                        time_str = '00:00'
                    event_dt = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
                    event_dt = event_dt.replace(tzinfo=timezone.utc)

                    if event_dt < now - timedelta(hours=1):
                        continue
                    if not event_in_horizon(event_dt, now, days_ahead):
                        continue

                    impact = e.get('impact', 'High')
                    if impact not in ('High', 'Medium'):
                        continue

                    events.append({
                        'date': date_str,
                        'time': time_str,
                        'datetime_utc': event_dt.isoformat(),
                        'currency': e.get('currency', 'USD'),
                        'event': e.get('event', 'Unknown'),
                        'impact': impact,
                        'forecast': e.get('forecast', ''),
                        'previous': e.get('previous', ''),
                        'source': 'manual_calendar',
                    })
                except Exception:
                    continue

        logger.info(f"✅ Loaded {len(events)} events from manual calendar (all sections)")
        return events

    except Exception as e:
        logger.error(f"❌ Manual calendar error: {e}")
        return []


def should_run_weekly_sync(force: bool = False) -> bool:
    """Return True if weekly sync is due (every 7 days)."""
    if force:
        return True
    try:
        if not WEEKLY_STATE_FILE.exists():
            return True
        with open(WEEKLY_STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
        last_run = state.get('last_weekly_run')
        if not last_run:
            return True
        last_dt = datetime.fromisoformat(str(last_run).replace('Z', '+00:00'))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - last_dt >= timedelta(days=WEEKLY_INTERVAL_DAYS)
    except Exception:
        return True


def mark_weekly_sync_done():
    try:
        WEEKLY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(WEEKLY_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'last_weekly_run': datetime.now(timezone.utc).isoformat(),
                'interval_days': WEEKLY_INTERVAL_DAYS,
            }, f, indent=2)
    except Exception as e:
        logger.warning(f"⚠️ Could not write weekly state: {e}")


def fetch_all_merged(days_ahead: int = 14, debug: bool = False) -> List[Dict]:
    """
    V67.3 — FF mirror, cTrader fallback, manual calendar, TE last resort.
    """
    ff, ff_all_feeds_live = fetch_forexfactory_mirror(days_ahead=days_ahead)

    ctrader: List[Dict] = []
    # cTrader bot serves upcoming_news.json (not live FF) — only when FF parse is empty.
    if not ff:
        ctrader = fetch_ctrader_calendar(days_ahead=days_ahead)

    manual = fetch_from_manual_calendar(days_ahead=days_ahead)
    merged = deduplicate_events(ff + ctrader + manual)

    logger.info(
        f"📊 Merge: FF {len(ff)} | cTrader {len(ctrader)} | manual {len(manual)} "
        f"→ {len(merged)} unique (ff_all_feeds_live={ff_all_feeds_live})"
    )
    _agent_debug_log('H2', 'fetch_all_merged', 'merge totals', {
        'ff': len(ff), 'ctrader': len(ctrader), 'manual': len(manual),
        'merged': len(merged), 'ff_all_feeds_live': ff_all_feeds_live,
    })

    if debug:
        for label, chunk in (
            ('FF', ff), ('cTrader', ctrader), ('manual', manual),
        ):
            if not chunk:
                continue
            logger.debug(f"DEBUG {label} first: {chunk[:3]}")
            if len(chunk) > 3:
                logger.debug(f"DEBUG {label} last: {chunk[-3:]}")

    if merged:
        return merged

    te = fetch_trading_economics(days_ahead=days_ahead)
    if te:
        logger.info(f"✅ Trading Economics (last resort): {len(te)} events")
    return te


def run_weekly_auto_sync(days_ahead: int = 14, force: bool = False) -> List[Dict]:
    """
    V39.5 weekly pipeline: same merge as daily; marks weekly state when forced/due.
    """
    if not should_run_weekly_sync(force=force):
        logger.info("⏭️ Weekly sync not due — using daily merge pipeline")
        return fetch_all_merged(days_ahead=days_ahead)

    logger.info("🔄 V39.5 WEEKLY AUTO-SYNC — manual + ForexFactory mirror")
    merged = fetch_all_merged(days_ahead=days_ahead)
    mark_weekly_sync_done()
    return merged


def deduplicate_events(events: List[Dict]) -> List[Dict]:
    """Remove duplicate events (same currency + event name + date)"""
    seen = set()
    unique = []
    for e in events:
        key = f"{e['currency']}_{e['event']}_{e['date']}_{e['time']}"
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def save_events(events: List[Dict]) -> bool:
    """Save fetched events to data/upcoming_news.json"""
    if not events:
        logger.error("❌ Refusing to write empty upcoming_news.json")
        return False
    try:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Sort by datetime
        events.sort(key=lambda e: e.get('datetime_utc', ''))

        output = {
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'event_count': len(events),
            'high_count': sum(1 for e in events if e['impact'] == 'High'),
            'medium_count': sum(1 for e in events if e['impact'] == 'Medium'),
            'events': events,
        }

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(f"💾 Saved {len(events)} events to {OUTPUT_FILE}")
        return True

    except Exception as e:
        logger.error(f"❌ Error saving events: {e}")
        return False


def send_sync_summary(events: List[Dict]):
    """Send a summary notification to Telegram after daily sync"""
    try:
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        if not bot_token or not chat_id:
            return

        now = datetime.now(timezone.utc)
        high = [e for e in events if e['impact'] == 'High']
        medium = [e for e in events if e['impact'] == 'Medium']

        # Group HIGH by currency
        by_currency = {}
        for e in high:
            c = e['currency']
            by_currency[c] = by_currency.get(c, 0) + 1

        flags = {
            'USD': '🇺🇸', 'EUR': '🇪🇺', 'GBP': '🇬🇧', 'JPY': '🇯🇵',
            'AUD': '🇦🇺', 'NZD': '🇳🇿', 'CAD': '🇨🇦', 'CHF': '🇨🇭',
        }

        currency_lines = '\n'.join(
            f"  {flags.get(c, '🏴')} {c}: <code>{n}</code>"
            for c, n in sorted(by_currency.items(), key=lambda x: -x[1])
        )

        # Today's events specifically
        today_str = now.strftime('%Y-%m-%d')
        today_events = [e for e in high if e['date'] == today_str]
        today_section = ""
        if today_events:
            today_section = "\n<b>📌 TODAY'S HIGH IMPACT:</b>\n"
            for e in today_events:
                f = flags.get(e['currency'], '🏴')
                today_section += f"  {f} <code>{e['time']}</code> {e['event']}\n"
            today_section += "\n"

        sep = "────────────────"
        message = (
            f"📡 <b>NEWS SYNC COMPLETE</b>\n"
            f"{sep}\n\n"
            f"⏰ {now.strftime('%d %b %Y, %H:%M')} UTC\n\n"
            f"<b>📊 UPCOMING EVENTS:</b>\n"
            f"  🔴 High Impact: <code>{len(high)}</code>\n"
            f"  🟠 Medium Impact: <code>{len(medium)}</code>\n\n"
            f"<b>🌍 BY CURRENCY:</b>\n{currency_lines}\n\n"
            f"{today_section}"
            f"💡 <i>15-min reminders active for all HIGH events</i>\n\n"
            f"  {sep}\n"
            f"  🔱 <b>AUTHORED BY ФорексГод</b> 🔱\n"
            f"  {sep}\n"
            f"  🏛️  <b>Глитч Ин Матрикс</b>  🏛️"
        )

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        requests.post(url, json={
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML',
        }, timeout=10)
        logger.info("📨 Sync summary sent to Telegram")

    except Exception as e:
        logger.warning(f"⚠️ Could not send Telegram summary: {e}")


def main():
    """Main entry point — fetch, merge, save, notify"""
    parser = argparse.ArgumentParser(description='News Fetcher V39.5 — Daily + Weekly Auto-Sync')
    parser.add_argument('--days', type=int, default=7, help='Days ahead to fetch (default: 7)')
    parser.add_argument('--weekly', action='store_true', help='Weekly auto-sync (14 days, FF merge)')
    parser.add_argument('--force-weekly', action='store_true', help='Force weekly sync even if not due')
    parser.add_argument('--debug', action='store_true', help='Verbose logging + sample parsed events')
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        for h in logger.handlers:
            h.setLevel(logging.DEBUG)

    days_ahead = 14 if args.weekly else args.days

    # Ensure logs directory exists
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("📡 NEWS FETCHER V39.5 — AUTO-SYNC")
    logger.info(f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    logger.info(f"📅 Fetching next {days_ahead} days")
    if args.weekly:
        logger.info("🔄 Mode: WEEKLY (manual + FF mirror merge)")
    logger.info("=" * 60)

    # Load .env for Telegram credentials
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    all_events = []

    if args.weekly:
        if not should_run_weekly_sync(force=args.force_weekly):
            logger.info("⏭️ Weekly sync not due — using daily merge pipeline")
            all_events = fetch_all_merged(days_ahead=days_ahead, debug=args.debug)
        else:
            logger.info("🔄 V39.5 WEEKLY AUTO-SYNC — FF + cTrader + manual")
            all_events = fetch_all_merged(days_ahead=days_ahead, debug=args.debug)
            mark_weekly_sync_done()
    else:
        all_events = fetch_all_merged(days_ahead=days_ahead, debug=args.debug)

    if not all_events:
        logger.error("❌ Failed to fetch news: all sources returned 0 events")
        logger.error(
            "💡 Check: FF mirror (rate limit / weekend gap — nextweek JSON removed by host), "
            f"CalendarBOT :8768 ({resolve_ctrader_calendar_url()}), "
            "TRADING_ECONOMICS_API_KEY in .env, add_monthly_events.py"
        )
        logger.error("💡 Windows VPS: py news_fetcher.py --days 14 --debug")
        _agent_debug_log('H2', 'news_fetcher.main', 'fetch failed exit 1', {'days_ahead': days_ahead})
        sys.exit(1)

    logger.info(f"📊 Total unique events: {len(all_events)}")

    if not save_events(all_events):
        sys.exit(1)

    logger.info(f"💾 Output: {OUTPUT_FILE}")
    logger.info("=" * 60)
    logger.info("✅ NEWS FETCHER V39.5 — SYNC COMPLETE")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
