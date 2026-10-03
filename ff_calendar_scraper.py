"""
ForexFactory calendar — direct HTML scrape (High impact / red folder only).

Uses cloudscraper to bypass Cloudflare. Output aligns with news_fetcher event schema.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

FF_CALENDAR_BASE = "https://www.forexfactory.com/calendar"
FF_MONTH_SLUG = (
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
)

MAJOR_CURRENCIES = frozenset({"USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF"})

_CLOUDFLARE_MARKERS = ("just a moment", "challenge-platform", "cf-browser-verification")

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DEBUG_HTML = SCRIPT_DIR / "debug_ff.html"


def default_now() -> datetime:
    return datetime.now(timezone.utc)


def debug_html_path() -> Path:
    raw = (os.getenv("FF_DEBUG_HTML") or "").strip()
    return Path(raw) if raw else DEFAULT_DEBUG_HTML


def ff_week_slug(sunday: datetime) -> str:
    """FF week URL token: oct4.2026 (Sunday that starts the displayed week)."""
    return f"{FF_MONTH_SLUG[sunday.month - 1]}{sunday.day}.{sunday.year}"


def build_week_urls(now: datetime, days_ahead: int = 14) -> List[str]:
    """Week view URLs covering [now, now + days_ahead]."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    end = now + timedelta(days=days_ahead)
    cursor = now.date()
    cursor = cursor - timedelta(days=(cursor.weekday() + 1) % 7)
    urls: List[str] = []
    seen: set[str] = set()
    while cursor <= end.date() + timedelta(days=7):
        sunday_dt = datetime(cursor.year, cursor.month, cursor.day, tzinfo=timezone.utc)
        slug = ff_week_slug(sunday_dt)
        if slug not in seen:
            seen.add(slug)
            urls.append(f"{FF_CALENDAR_BASE}?week={slug}")
        cursor += timedelta(days=7)
    return urls


def is_cloudflare_block(html: str) -> bool:
    head = (html or "")[:8000].lower()
    return any(m in head for m in _CLOUDFLARE_MARKERS)


def parse_page_year(html: str, fallback: int) -> int:
    m = re.search(r"(20\d{2})", html)
    if m:
        return int(m.group(1))
    return fallback


def parse_page_timezone(html: str, fallback: str) -> ZoneInfo:
    m = re.search(r"Calendar Time Zone:\s*([^\(<\n]+)", html, re.I)
    if not m:
        return ZoneInfo(fallback)
    label = m.group(1).strip()
    mapping = {
        "EET": "Europe/Bucharest",
        "EEST": "Europe/Bucharest",
        "GMT": "UTC",
        "UTC": "UTC",
        "America/New_York": "America/New_York",
        "America/Chicago": "America/Chicago",
    }
    for key, tz_name in mapping.items():
        if key.lower() in label.lower():
            return ZoneInfo(tz_name)
    try:
        return ZoneInfo(label.split()[0])
    except Exception:
        return ZoneInfo(fallback)


def _parse_event_time(time_text: str, event_date, tz: ZoneInfo) -> Optional[datetime]:
    t = (time_text or "").strip().lower()
    if not t or t in ("all day", "day", "tentative", "—", "-", ""):
        local = datetime.combine(event_date, datetime.min.time().replace(hour=12, minute=0))
        return local.replace(tzinfo=tz).astimezone(timezone.utc)
    m = re.match(r"(\d{1,2}):(\d{2})(?:\s*(am|pm))?", t)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    ampm = m.group(3)
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    local = datetime.combine(
        event_date,
        datetime.min.time().replace(hour=hour, minute=minute),
    )
    return local.replace(tzinfo=tz).astimezone(timezone.utc)


def _cell_text(td) -> str:
    if td is None:
        return ""
    return " ".join(td.stripped_strings)


def _element_impact_level(el) -> Optional[str]:
    """Return 'high', 'medium', 'low', or None from FF impact icon / cell."""
    classes = " ".join(el.get("class") or []).lower()
    title = (el.get("title") or "").lower()
    aria = (el.get("aria-label") or "").lower()
    combined = f"{classes} {title} {aria}"

    if "ff-impact-red" in combined or "impact-red" in combined:
        return "high"
    if "impact-icon--high" in classes or "impact--high" in classes:
        return "high"
    if re.search(r"\bhigh\b", combined) and "high impact" in combined:
        return "high"
    if "high impact expected" in combined:
        return "high"

    if "ff-impact-ora" in combined or "impact-ora" in combined or "impact-icon--medium" in classes:
        return "medium"
    if "ff-impact-yel" in combined or "impact-yel" in combined or "impact-icon--low" in classes:
        return "low"
    return None


def _row_has_high_impact(tr) -> bool:
    for el in tr.find_all(True):
        if _element_impact_level(el) == "high":
            return True
    impact_td = tr.select_one(
        "td.calendar__impact, td.calendar__cell--impact, td[class*='calendar__impact']",
    )
    if impact_td and _element_impact_level(impact_td) == "high":
        return True
    if tr.select("span[class*='ff-impact-red'], span.icon--ff-impact-red"):
        return True
    return False


def _parse_date_from_text(date_text: str, year_guess: int):
    month_names = (
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    )
    for idx, mon_name in enumerate(month_names, 1):
        dm = re.search(rf"{mon_name}\s+(\d{{1,2}})", date_text, re.I)
        if dm:
            return datetime(year_guess, idx, int(dm.group(1))).date()
    return None


def _select_calendar_rows(soup) -> list:
    """All table rows in document order (includes day-breakers for date context)."""
    rows = soup.select("tr.calendar__row")
    if rows:
        return rows
    rows = soup.select("tr[data-event-id]")
    if rows:
        return rows
    return soup.select("tr[class*='calendar']")


def write_debug_html(html: str, url: str = "") -> Path:
    path = debug_html_path()
    try:
        header = f"<!-- debug url: {url} saved: {datetime.now(timezone.utc).isoformat()} -->\n"
        path.write_text(header + (html or ""), encoding="utf-8")
        logger.warning(f"📝 Wrote empty-parse debug HTML to {path} ({len(html or '')} bytes)")
    except Exception as exc:
        logger.error(f"Could not write debug HTML: {exc}")
    return path


def parse_high_impact_rows(
    html: str,
    tz: ZoneInfo,
    *,
    now: Optional[datetime] = None,
    days_ahead: int = 14,
    event_in_horizon: Optional[Callable[..., bool]] = None,
) -> List[dict]:
    """Parse FF calendar HTML; return only red-folder (High) events."""
    from bs4 import BeautifulSoup

    now = now or default_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    soup = BeautifulSoup(html, "html.parser")
    year_guess = parse_page_year(html, now.year)
    rows = _select_calendar_rows(soup)

    events: List[dict] = []
    current_date = None
    last_time_text = ""

    for tr in rows:
        classes = " ".join(tr.get("class") or [])

        if "day-breaker" in classes or "calendar__row--day-breaker" in classes:
            date_cell = tr.select_one(".calendar__date, td.calendar__cell")
            if date_cell:
                parsed = _parse_date_from_text(_cell_text(date_cell), year_guess)
                if parsed:
                    current_date = parsed
            continue

        date_cell = tr.select_one(
            "td.calendar__date, td[class*='calendar__date']",
        )
        if date_cell and _cell_text(date_cell):
            parsed = _parse_date_from_text(_cell_text(date_cell), year_guess)
            if parsed:
                current_date = parsed

        time_td = tr.select_one(
            "td.calendar__time, td[class*='calendar__time']",
        )
        time_text = _cell_text(time_td)
        if time_text and time_text.lower() not in ("", "—", "-"):
            last_time_text = time_text

        if tr.get("data-event-id") is None and "calendar__row--event" not in classes:
            continue

        if not _row_has_high_impact(tr):
            continue

        currency_td = tr.select_one(
            "td.calendar__currency, td[class*='calendar__currency']",
        )
        event_td = tr.select_one(
            "td.calendar__event, td[class*='calendar__event']",
        )
        title_el = tr.select_one(".calendar__event-title, span[class*='event-title']")
        title = _cell_text(title_el) if title_el else _cell_text(event_td)

        currency = _cell_text(currency_td).upper()
        if currency not in MAJOR_CURRENCIES:
            continue
        if not title:
            continue
        if current_date is None:
            continue

        effective_time = time_text or last_time_text
        event_dt_utc = _parse_event_time(effective_time, current_date, tz)
        if event_dt_utc is None:
            continue

        if event_in_horizon is not None:
            if not event_in_horizon(event_dt_utc, now, days_ahead):
                continue
        else:
            end = now + timedelta(days=days_ahead, hours=23, minutes=59)
            if event_dt_utc < now - timedelta(hours=1) or event_dt_utc > end:
                continue

        forecast_td = tr.select_one("td.calendar__forecast, td[class*='calendar__forecast']")
        previous_td = tr.select_one("td.calendar__previous, td[class*='calendar__previous']")
        forecast = _cell_text(forecast_td)
        previous = _cell_text(previous_td)
        if not forecast and not previous:
            detail = tr.select_one("td.calendar__detail, td[class*='calendar__detail']")
            if detail:
                spans = detail.find_all("span")
                if len(spans) >= 2:
                    forecast = _cell_text(spans[0])
                    previous = _cell_text(spans[1])

        events.append({
            "date": event_dt_utc.strftime("%Y-%m-%d"),
            "time": event_dt_utc.strftime("%H:%M"),
            "datetime_utc": event_dt_utc.isoformat(),
            "currency": currency,
            "event": title,
            "impact": "High",
            "forecast": forecast,
            "previous": previous,
            "source": "forexfactory_html",
        })

    return events


def fetch_week_html(url: str, timeout: float = 30.0) -> Tuple[Optional[str], str]:
    """GET calendar week page. Returns (html, error_message)."""
    try:
        import cloudscraper
    except ImportError:
        return None, "cloudscraper not installed"

    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False},
        )
        resp = scraper.get(url, timeout=timeout)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        text = resp.text or ""
        if is_cloudflare_block(text):
            return None, "Cloudflare challenge page"
        return text, ""
    except Exception as exc:
        return None, str(exc)


def fetch_forexfactory_high_impact_html(
    days_ahead: int = 14,
    *,
    now: Optional[datetime] = None,
    event_in_horizon: Optional[Callable[..., bool]] = None,
) -> Tuple[List[dict], str, int]:
    """
    Scrape FF week pages for High impact events.
    Returns (events, meta_message, count_of_http_200_pages_fetched).
    """
    now = now or default_now()
    fallback_tz = os.getenv("FF_CALENDAR_TZ", "Europe/Bucharest")
    urls = build_week_urls(now, days_ahead)
    all_events: List[dict] = []
    errors: List[str] = []
    pages_ok = 0
    debug_written = False

    for url in urls:
        html, err = fetch_week_html(url)
        if not html:
            errors.append(f"{url}: {err}")
            continue
        pages_ok += 1
        tz = parse_page_timezone(html, fallback_tz)
        chunk = parse_high_impact_rows(
            html, tz, now=now, days_ahead=days_ahead, event_in_horizon=event_in_horizon,
        )
        logger.info(f"FF HTML {url}: {len(chunk)} High events")
        if not chunk and not debug_written:
            write_debug_html(html, url)
            debug_written = True
        all_events.extend(chunk)

    if not all_events:
        return [], "; ".join(errors) or "no High events parsed", pages_ok

    seen: set[str] = set()
    unique: List[dict] = []
    for e in all_events:
        key = f"{e['currency']}_{e['event']}_{e['date']}_{e['time']}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)

    unique.sort(key=lambda x: x.get("datetime_utc", ""))
    return unique, "forexfactory_html", pages_ok
