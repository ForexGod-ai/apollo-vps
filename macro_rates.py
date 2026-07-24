#!/usr/bin/env python3
"""
macro_rates.py — V38 Live Central Bank Rates Service

Unified source for official CB policy rates (investing.com scrape + JSON cache)
and IC Markets swap carry via cTrader MarketDataProvider localhost:8010.

Used by: telegram_command_center (/rates), news_calendar_monitor (weekly macro),
         scripts/refresh_cb_rates.py (daily cron).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    import pytz
    _BUCHAREST_TZ = pytz.timezone("Europe/Bucharest")
except ImportError:
    _BUCHAREST_TZ = None

ROOT = Path(__file__).parent.resolve()
CACHE_FILE = ROOT / "data" / "cb_rates_cache.json"
LAST_REFRESH_FILE = ROOT / "data" / "last_cb_rates_refresh.json"
LAST_ALERT_FILE = ROOT / "data" / "last_cb_rate_alert.json"

FETCH_RETRIES = 3
FETCH_RETRY_DELAY_SEC = 2

# Last-resort baseline (~June 2026 public policy rates). NOT used when cache/live exists.
FALLBACK_RATES: Dict[str, float] = {
    "NZD": 2.25,
    "GBP": 3.75,
    "USD": 3.75,
    "AUD": 4.35,
    "CAD": 2.25,
    "EUR": 2.40,
    "CHF": 0.00,
    "JPY": 1.00,
}

# Backward compatibility alias
CENTRAL_BANK_RATES = FALLBACK_RATES

FLAGS: Dict[str, str] = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵",
    "AUD": "🇦🇺", "NZD": "🇳🇿", "CAD": "🇨🇦", "CHF": "🇨🇭",
}

CARRY_PAIRS: List[Tuple[str, str]] = [
    ("GBP", "JPY"), ("NZD", "JPY"), ("AUD", "JPY"), ("USD", "JPY"),
    ("GBP", "CHF"), ("NZD", "CHF"), ("AUD", "CHF"), ("USD", "CHF"),
    ("GBP", "EUR"), ("NZD", "EUR"), ("AUD", "EUR"), ("USD", "EUR"),
    ("GBP", "CAD"), ("NZD", "CAD"), ("AUD", "CAD"), ("USD", "CAD"),
]

# Fallback if pairs_config.json unavailable
SWAP_CARRY_SYMBOLS = ["GBPJPY", "NZDJPY", "AUDJPY", "USDJPY", "GBPNZD", "EURJPY"]

PAIRS_CONFIG_FILE = ROOT / "pairs_config.json"
SWAP_FETCH_TIMEOUT_SEC = 3
SWAP_COL_SIZE = 8
# Match CB rates grid — Telegram mobile breathes at ~36 chars per column.
TELEGRAM_GRID_COL_WIDTH = 36
SWAP_COL_WIDTH = TELEGRAM_GRID_COL_WIDTH
CARRY_PAIR_WIDTH = 8
CARRY_SPREAD_WIDTH = 7
CARRY_MEDALS = ("🥇", "🥈", "🥉")

MIN_LIVE_CURRENCIES = 6
DEFAULT_TTL_HOURS = 6
STALE_CACHE_DAYS = 7
SIGNIFICANT_CHANGE_PCT = 0.25
CACHE_FRESH_MAX_HOURS = DEFAULT_TTL_HOURS * 4  # 24h — label "cache" vs "cache_stale"

INVESTING_CB_URL = "https://www.investing.com/central-banks/"
INVESTING_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.investing.com/",
    "Cache-Control": "no-cache",
}

BANK_NAME_TO_CCY = [
    ("federal reserve", "USD"),
    ("european central", "EUR"),
    ("bank of england", "GBP"),
    ("swiss national", "CHF"),
    ("reserve bank of australia", "AUD"),
    ("bank of canada", "CAD"),
    ("reserve bank of new zealand", "NZD"),
    ("bank of japan", "JPY"),
]


def _now_bucharest() -> datetime:
    if _BUCHAREST_TZ:
        return datetime.now(_BUCHAREST_TZ).replace(tzinfo=None)
    return datetime.now()


def load_cache() -> Optional[dict]:
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"[macro_rates] cache read failed: {e}")
    return None


def save_cache(rates: Dict[str, float], source: str) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "rates": rates,
        "fetched_at": _now_bucharest().isoformat(),
        "source": source,
    }
    tmp = CACHE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(CACHE_FILE)


def _parse_investing_cb_table(html: str) -> Dict[str, float]:
    """Parse G8 central bank rates from investing.com central-banks page."""
    if not HAS_BS4:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    live: Dict[str, float] = {}
    for row in soup.select("table tr"):
        cols = row.find_all("td")
        if len(cols) < 2:
            continue
        row_text = " ".join(c.get_text(" ", strip=True) for c in cols).lower()
        rate_val: Optional[float] = None
        for col in cols:
            txt = col.get_text(strip=True).replace("%", "").replace(",", ".")
            try:
                val = float(txt)
                if 0.0 <= val <= 30.0:
                    rate_val = val
                    break
            except ValueError:
                continue
        if rate_val is None:
            continue
        for key, ccy in BANK_NAME_TO_CCY:
            if key in row_text and ccy not in live:
                live[ccy] = rate_val
                break
    return live


def fetch_live_cb_rates(retries: int = FETCH_RETRIES) -> Dict[str, float]:
    """
    Scrape official central bank rates from investing.com.
    Returns partial or empty dict on failure.
    """
    if not HAS_REQUESTS:
        logger.warning("[macro_rates] requests not installed — skip live fetch")
        return {}
    if not HAS_BS4:
        logger.warning("[macro_rates] BeautifulSoup not installed — run: pip install beautifulsoup4")
        return {}

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                INVESTING_CB_URL,
                headers=INVESTING_BROWSER_HEADERS,
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning(
                    f"[macro_rates] HTTP {resp.status_code} (attempt {attempt}/{retries})"
                )
                if attempt < retries:
                    time.sleep(FETCH_RETRY_DELAY_SEC)
                continue

            live = _parse_investing_cb_table(resp.text)
            if len(live) >= MIN_LIVE_CURRENCIES:
                logger.success(f"[macro_rates] live fetch OK ({len(live)} currencies): {live}")
                return live
            logger.warning(
                f"[macro_rates] only {len(live)} currencies parsed (attempt {attempt}/{retries})"
            )

        except Exception as e:
            logger.warning(f"[macro_rates] scrape failed (attempt {attempt}/{retries}): {e}")

        if attempt < retries:
            time.sleep(FETCH_RETRY_DELAY_SEC)

    return {}


def _cache_age_hours(cache: dict) -> float:
    try:
        fetched = datetime.fromisoformat(cache["fetched_at"])
        return ( _now_bucharest() - fetched).total_seconds() / 3600.0
    except Exception:
        return float("inf")


def _merge_rates(live: Dict[str, float], base: Dict[str, float]) -> Dict[str, float]:
    effective = dict(base)
    effective.update(live)
    return effective


def detect_rate_changes(
    old_rates: Dict[str, float],
    new_rates: Dict[str, float],
    threshold: float = SIGNIFICANT_CHANGE_PCT,
) -> List[Tuple[str, float, float]]:
    changes = []
    for ccy, new_val in new_rates.items():
        old_val = old_rates.get(ccy)
        if old_val is not None and abs(new_val - old_val) >= threshold:
            changes.append((ccy, old_val, new_val))
    return changes


def _source_badge(source: str, fetched_at: Optional[str]) -> str:
    if source == "live":
        return "🟢 LIVE"
    if source in ("cache", "cache_stale"):
        if fetched_at:
            try:
                age_h = (_now_bucharest() - datetime.fromisoformat(fetched_at)).total_seconds() / 3600
                if source == "cache" and age_h < 1:
                    return "🟡 CACHE (<1h)"
                if age_h < 24:
                    return f"🟡 CACHE ({int(age_h)}h)"
                days = max(1, int(age_h / 24))
                return f"🟡 CACHE ({days}d)"
            except Exception:
                pass
        return "🟡 CACHE"
    return "🔴 OFFLINE"


def _is_usable_source(source: str) -> bool:
    """Live or cached real data — not hardcoded fallback."""
    return source in ("live", "cache", "cache_stale")


def _rates_from_cache_entry(cache: dict, ttl_hours: float = DEFAULT_TTL_HOURS) -> Tuple[Dict[str, float], str, Optional[str]]:
    """Return cached rates with fresh vs stale label."""
    age_h = _cache_age_hours(cache)
    label = "cache" if age_h < ttl_hours * 4 else "cache_stale"
    return cache["rates"], label, cache.get("fetched_at")


def _rate_bar(rate: float, max_rate: float = 5.0) -> str:
    """Visual bar scaled to max_rate (default 5%)."""
    if max_rate <= 0:
        max_rate = 5.0
    filled = min(8, max(0, round((rate / max_rate) * 8)))
    return "▰" * filled + "▱" * (8 - filled)


def _changes_fingerprint(changes: List[Tuple[str, float, float]]) -> str:
    return "|".join(f"{c}:{o:.2f}>{n:.2f}" for c, o, n in sorted(changes))


def _should_send_alert(changes: List[Tuple[str, float, float]]) -> bool:
    if not changes:
        return False
    fp = _changes_fingerprint(changes)
    try:
        if LAST_ALERT_FILE.exists():
            data = json.loads(LAST_ALERT_FILE.read_text(encoding="utf-8"))
            if data.get("fingerprint") == fp:
                sent_at = datetime.fromisoformat(data["sent_at"])
                if (_now_bucharest() - sent_at).total_seconds() < 6 * 3600:
                    return False
    except Exception:
        pass
    return True


def _mark_alert_sent(changes: List[Tuple[str, float, float]]) -> None:
    LAST_ALERT_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_ALERT_FILE.write_text(
        json.dumps({
            "fingerprint": _changes_fingerprint(changes),
            "sent_at": _now_bucharest().isoformat(),
        }, indent=2),
        encoding="utf-8",
    )


def get_effective_rates(
    force_refresh: bool = False,
    ttl_hours: float = DEFAULT_TTL_HOURS,
) -> Tuple[Dict[str, float], str, Optional[str], List[Tuple[str, float, float]]]:
    """
    Returns (rates, source_label, fetched_at_iso, changes_vs_previous_cache).

    Priority:
      1. Fresh live scrape (if force or cache TTL expired)
      2. Recent cache (<24h) → cache
      3. Any cached rates on disk → cache_stale (better than hardcoded)
      4. FALLBACK_RATES — last resort only
    """
    cache = load_cache()
    previous_rates = cache.get("rates", {}) if cache else dict(FALLBACK_RATES)

    needs_refresh = force_refresh
    if cache and not needs_refresh:
        needs_refresh = _cache_age_hours(cache) >= ttl_hours

    if needs_refresh:
        live = fetch_live_cb_rates()
        if live:
            effective = _merge_rates(live, FALLBACK_RATES)
            changes = detect_rate_changes(previous_rates, effective)
            save_cache(effective, "investing.com")
            fetched_at = _now_bucharest().isoformat()
            return effective, "live", fetched_at, changes

        # Live failed — use any existing cache before hardcoded fallback
        if cache and cache.get("rates"):
            rates, label, fetched_at = _rates_from_cache_entry(cache, ttl_hours)
            logger.warning(
                f"[macro_rates] live fetch failed — using {label} "
                f"(fetched {fetched_at or '?'})"
            )
            return rates, label, fetched_at, []

    if cache and cache.get("rates"):
        age_h = _cache_age_hours(cache)
        if age_h < ttl_hours * 4:
            return _rates_from_cache_entry(cache, ttl_hours)

    if cache and cache.get("rates"):
        rates, label, fetched_at = _rates_from_cache_entry(cache, ttl_hours)
        logger.warning(f"[macro_rates] using {label} — live unavailable")
        return rates, label, fetched_at, []

    logger.warning("[macro_rates] using FALLBACK_RATES — no live data and no cache file")
    return dict(FALLBACK_RATES), "fallback", None, []


def is_cache_stale(days: int = STALE_CACHE_DAYS) -> bool:
    cache = load_cache()
    if not cache or not cache.get("fetched_at"):
        return True
    try:
        fetched = datetime.fromisoformat(cache["fetched_at"])
        return (_now_bucharest() - fetched) > timedelta(days=days)
    except Exception:
        return True


def load_project_symbols() -> List[str]:
    """All active scanner symbols from pairs_config.json."""
    try:
        if PAIRS_CONFIG_FILE.exists():
            with open(PAIRS_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            symbols = [
                p["symbol"].upper()
                for p in data.get("pairs", [])
                if isinstance(p, dict) and p.get("symbol")
            ]
            if symbols:
                return symbols
    except Exception as e:
        logger.warning(f"[macro_rates] pairs_config load failed: {e}")
    return list(SWAP_CARRY_SYMBOLS)


def _swap_cbot_base_url() -> str:
    try:
        from ctrader_cbot_client import get_cbot_client
        return get_cbot_client().base_url
    except Exception:
        return "http://localhost:8010"


def _format_swap_grid_cell(symbol: str, swap_long: float, swap_short: float) -> str:
    """Fixed 22-char swap cell — no trailing spaces (Telegram strips them)."""
    return f"{symbol:<6} {swap_long:+7.2f}/{swap_short:+7.2f}"


def _format_carry_row(item: dict) -> str:
    """Monospaced carry row: pair(8) + spread(7) + rate math."""
    pair = f"{item['base']}/{item['quote']}"
    spread = f"+{item['spread']:.2f}%"
    calc = f"{item['base_rate']:.2f}-{item['quote_rate']:.2f}"
    return f"{pair:<{CARRY_PAIR_WIDTH}}{spread:>{CARRY_SPREAD_WIDTH}}  {calc}"


def _format_carry_block(items: List[dict]) -> str:
    """All carry rows in one monospace block, medals included."""
    return "\n".join(
        f"{CARRY_MEDALS[i]} {_format_carry_row(item)}"
        for i, item in enumerate(items)
    )


def _chunked(items: List[str], size: int) -> List[List[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _format_two_columns(
    left: List[str],
    right: List[str],
    width: int = SWAP_COL_WIDTH,
) -> str:
    """Monospace grid: fixed-width left cells with gap before right column."""
    rows = max(len(left), len(right))
    lines = []
    for i in range(rows):
        l_cell = left[i] if i < len(left) else ""
        r_cell = right[i] if i < len(right) else ""
        if r_cell:
            lines.append(f"{l_cell:<{width}}  {r_cell}")
        else:
            lines.append(l_cell)
    return "\n".join(lines)


CB_GRID_CELL_WIDTH = TELEGRAM_GRID_COL_WIDTH


def _format_cb_rate_cell(
    ccy: str,
    rate: float,
    median_rate: float,
    max_rate: float,
) -> str:
    """Single CB rate cell: flag, rate, visual bar, HIGH/LOW vs median."""
    flag = FLAGS.get(ccy, "")
    bar = _rate_bar(rate, max(max_rate, 0.01))
    tag = "HIGH" if rate >= median_rate else "LOW "
    return f"{flag}{ccy} {rate:>5.2f}% {bar} {tag}"


def _format_cb_rates_grid(
    sorted_rates: List[Tuple[str, float]],
    median_rate: float,
    max_rate: float,
) -> str:
    """Two-column monospace grid of CB rates with bars and HIGH/LOW tags."""
    cells = [
        _format_cb_rate_cell(ccy, rate, median_rate, max_rate)
        for ccy, rate in sorted_rates
    ]
    lines = []
    for row in _chunked(cells, 2):
        if len(row) == 2:
            lines.append(f"{row[0]:<{CB_GRID_CELL_WIDTH}}{row[1]}")
        else:
            lines.append(row[0])
    return "\n".join(lines)


def _top_swap_credits(
    swaps: List[dict],
    side: str = "long",
    top_n: int = 3,
) -> List[dict]:
    """Top positive swap credits from cTrader (long or short leg)."""
    key = "swap_long" if side == "long" else "swap_short"
    credits = [s for s in swaps if float(s.get(key, 0.0)) > 0]
    credits.sort(key=lambda s: float(s[key]), reverse=True)
    return credits[:top_n]


def _format_swap_highlights(swaps: List[dict]) -> str:
    """Compact pre block: top 3 LONG + top 3 SHORT swap credits (pips/day)."""
    long_top = _top_swap_credits(swaps, "long", 3)
    short_top = _top_swap_credits(swaps, "short", 3)
    if not long_top and not short_top:
        return ""
    lines: List[str] = []
    for i, s in enumerate(long_top):
        lines.append(
            f"{CARRY_MEDALS[i]} LONG  {s['symbol']:<6} {s['swap_long']:+.2f} pips/zi"
        )
    for i, s in enumerate(short_top):
        lines.append(
            f"{CARRY_MEDALS[i]} SHORT {s['symbol']:<6} {s['swap_short']:+.2f} pips/zi"
        )
    return "\n".join(lines)


def _parse_symbol_to_carry_pair(symbol: str) -> Optional[Tuple[str, str]]:
    """Parse 6-char FX symbol into (base, quote) when both legs have CB rates."""
    s = symbol.upper().replace("/", "").strip()
    if len(s) != 6:
        return None
    base, quote = s[:3], s[3:]
    fx_ccys = frozenset(FALLBACK_RATES.keys())
    if base in fx_ccys and quote in fx_ccys:
        return base, quote
    return None


def _carry_pairs_for_currency(currency: str) -> List[Tuple[str, str]]:
    """Matrix portfolio pairs that contain `currency` (base or quote)."""
    currency = currency.upper()
    pairs: List[Tuple[str, str]] = []
    seen: set = set()
    for sym in load_project_symbols():
        parsed = _parse_symbol_to_carry_pair(sym)
        if not parsed or currency not in parsed:
            continue
        if parsed in seen:
            continue
        seen.add(parsed)
        pairs.append(parsed)
    return pairs


def get_top_carry_pairs(
    rates: Dict[str, float],
    top_n: int = 3,
    triggered_currency: Optional[str] = None,
) -> List[dict]:
    """
    Top carry spreads (base CB rate − quote CB rate).

    triggered_currency: when set (macro alert), only pairs from pairs_config.json
    that physically contain that currency — never unrelated global top carry.
    """
    if triggered_currency:
        pair_list = _carry_pairs_for_currency(triggered_currency)
    else:
        pair_list = list(CARRY_PAIRS)

    spreads = []
    for base, quote in pair_list:
        b = float(rates.get(base, 0.0))
        q = float(rates.get(quote, 0.0))
        spread = round(b - q, 2)
        spreads.append({
            "pair": f"{base}/{quote}",
            "base": base,
            "quote": quote,
            "spread": spread,
            "base_rate": b,
            "quote_rate": q,
        })
    spreads.sort(key=lambda x: x["spread"], reverse=True)
    return spreads[:top_n]


def fetch_ic_markets_swaps(symbols: Optional[List[str]] = None) -> List[dict]:
    """Live swap for all project pairs via MarketDataProvider (port 8010)."""
    symbols = symbols or load_project_symbols()
    if not HAS_REQUESTS:
        return []

    base_url = _swap_cbot_base_url()
    results = []
    for sym in symbols:
        try:
            resp = requests.get(
                f"{base_url}/swap_info",
                params={"symbol": sym},
                timeout=SWAP_FETCH_TIMEOUT_SEC,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            if not data.get("success"):
                continue
            results.append({
                "symbol": sym,
                "swap_long": float(data["swap_long"]),
                "swap_short": float(data["swap_short"]),
                "triple_day": str(data.get("swap_triple_day", "")),
            })
        except Exception:
            continue
    return results


def _write_refresh_meta(
    *,
    source: str,
    fetched_at: Optional[str],
    rates: Dict[str, float],
    changes: List,
    success: bool,
    updated_by: str = "macro_rates.refresh_rates_daily",
) -> None:
    """V48: Single writer for last_cb_rates_refresh.json — unified schema."""
    now = _now_bucharest()
    payload = {
        "last_refresh_date": now.strftime("%Y-%m-%d"),
        "last_refresh_timestamp": now.isoformat(),
        "refreshed_at": fetched_at or now.isoformat(),
        "source": source,
        "success": success,
        "rates": rates,
        "changes": changes,
        "updated_by": updated_by,
    }
    LAST_REFRESH_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LAST_REFRESH_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(LAST_REFRESH_FILE)


def get_last_refresh_date() -> str:
    """Read last_refresh_date from unified meta file (daemon dedup)."""
    try:
        if LAST_REFRESH_FILE.exists():
            with open(LAST_REFRESH_FILE, "r", encoding="utf-8") as f:
                return str(json.load(f).get("last_refresh_date", "") or "")
    except Exception:
        pass
    return ""


def format_rates_telegram_message(
    separator: str = "────────────────",
    include_swaps: bool = True,
    force_refresh: bool = True,
    notify_on_change: bool = True,
) -> str:
    """Build compact /rates Telegram HTML card (V64 Elite)."""
    rates, source, fetched_at, changes = get_effective_rates(force_refresh=force_refresh)
    badge = _source_badge(source, fetched_at)

    if force_refresh:
        _write_refresh_meta(
            source=source,
            fetched_at=fetched_at,
            rates=rates,
            changes=[{"ccy": c, "old": o, "new": n} for c, o, n in changes],
            success=_is_usable_source(source),
            updated_by="macro_rates.format_rates_telegram_message",
        )

    if notify_on_change and source == "live" and changes and _should_send_alert(changes):
        _send_rate_change_alert(changes, source, rates)
        _mark_alert_sent(changes)

    if fetched_at:
        try:
            ts_str = datetime.fromisoformat(fetched_at).strftime("%d %b · %H:%M")
        except Exception:
            ts_str = fetched_at
    else:
        ts_str = _now_bucharest().strftime("%d %b · %H:%M")

    sorted_rates = sorted(rates.items(), key=lambda x: x[1], reverse=True)
    all_vals = [v for _, v in sorted_rates]
    median_rate = sorted(all_vals)[len(all_vals) // 2] if all_vals else 0.0
    max_rate = max(all_vals) if all_vals else 5.0

    msg = (
        f"<b>🏦 DOBÂNZI BĂNCI CENTRALE</b>  {badge}  <i>{ts_str} EET</i>\n"
        f"{separator}\n"
    )

    if source == "fallback":
        msg += (
            "⚠️ <b>Live indisponibil</b> — date estimate hardcodate, nu oficiale.\n"
            "Verifică VPS: <code>python3 scripts/refresh_cb_rates.py --print</code>\n"
        )
    elif badge == "🔴 OFFLINE":
        msg += "⚠️ Live indisponibil · <code>pip install beautifulsoup4</code>\n"

    msg += f"<pre>{_format_cb_rates_grid(sorted_rates, median_rate, max_rate)}</pre>\n"

    top3 = get_top_carry_pairs(rates, 3)
    msg += f"\n{separator}\n<b>🎯 CARRY POLICY (teoretic)</b>\n\n"
    msg += f"<pre>{_format_carry_block(top3)}</pre>\n"
    msg += "<i>Spread rate BC — nu e swap broker</i>\n"

    if include_swaps:
        swaps = fetch_ic_markets_swaps()
        if swaps:
            highlights = _format_swap_highlights(swaps)
            if highlights:
                msg += (
                    f"\n{separator}\n"
                    f"<b>💱 TOP SWAP IC MARKETS</b> <i>(cTrader live)</i>\n\n"
                    f"<pre>{highlights}</pre>\n"
                )
            cells = [
                _format_swap_grid_cell(s["symbol"], s["swap_long"], s["swap_short"])
                for s in swaps
            ]
            mid = (len(cells) + 1) // 2
            msg += (
                f"\n{separator}\n"
                f"<b>📊 SWAP GRID</b> <i>· {len(swaps)} perechi Matrix · L/S pips/zi</i>\n"
                f"<pre>{_format_two_columns(cells[:mid], cells[mid:])}</pre>\n\n"
            )
        else:
            msg += f"\n{separator}\n<i>💱 Swap offline · cBot DATA port 8010</i>\n\n"

    strongest_ccy, strongest_rate = sorted_rates[0]
    weakest_ccy, weakest_rate = sorted_rates[-1]
    msg += (
        f"{separator}\n"
        f"💪 {strongest_ccy} {strongest_rate:.2f}% · 😴 {weakest_ccy} {weakest_rate:.2f}%"
    )
    return msg


def format_weekly_macro_report(local_tz=None) -> str:
    """Weekly macro table — same data source as /rates."""
    rates, source, fetched_at, changes = get_effective_rates(force_refresh=True)

    if local_tz:
        now_ro = datetime.now(local_tz).replace(tzinfo=None)
    else:
        now_ro = _now_bucharest()

    week_str = now_ro.strftime("W%W • %d %b %Y")

    if source == "fallback":
        return (
            "🏦 <b>MACRO WEEKLY TABLE</b>\n"
            f"📅 <b>{week_str}</b>\n\n"
            "⚠️ <b>Live indisponibil</b> — nu trimit tabel cu rate estimate.\n"
            "Reîncerc la refresh zilnic <code>08:00 EET</code> sau rulează "
            "<code>python3 scripts/refresh_cb_rates.py</code> pe VPS."
        )

    sorted_rates = sorted(rates.items(), key=lambda x: x[1], reverse=True)
    all_vals = [v for _, v in sorted_rates]
    median_rate = sorted(all_vals)[len(all_vals) // 2] if all_vals else 0.0

    SEP = "━━━━━━━━━━━━━━━━"

    ts_label = ""
    if fetched_at:
        try:
            ts_label = datetime.fromisoformat(fetched_at).strftime("%d %b %H:%M")
        except Exception:
            ts_label = fetched_at

    badge = _source_badge(source, fetched_at)
    msg = "🏦 <b>MACRO WEEKLY TABLE</b>\n"
    msg += f"📅 <b>{week_str}</b>  {badge}\n"
    msg += f"🕐 <i>Transmis {now_ro.strftime('%H:%M')} EET"
    if ts_label:
        msg += f" | rate fetch: {ts_label}"
    msg += "</i>\n"
    msg += SEP + "\n"

    if source == "cache_stale" and fetched_at:
        msg += (
            f"ℹ️ <i>Ultimele rate live salvate · fetch {ts_label}</i>\n"
            f"{SEP}\n"
        )

    if changes and source == "live":
        msg += "🚨 <b>RATE CHANGES!</b>\n"
        for ccy, old, new in changes:
            arrow = "🔺" if new > old else "🔻"
            flag = FLAGS.get(ccy, "")
            msg += f"  {arrow} {flag} <b>{ccy}</b>: {old:.2f}% → <b>{new:.2f}%</b>\n"
        msg += SEP + "\n"

    msg += "📊 <b>DOBÂNZI BĂNCI CENTRALE</b>\n"
    msg += "<code>"
    msg += f"{'CCY':<5} {'RATĂ':>6}  STATUS\n"
    msg += f"{'─'*5} {'─'*6}  {'─'*8}\n"
    for ccy, rate in sorted_rates:
        flag = FLAGS.get(ccy, " ")
        status = "🟢 STRONG" if rate >= median_rate else "🔴 WEAK"
        marker = "*" if abs(rate - FALLBACK_RATES.get(ccy, rate)) >= 0.01 else " "
        msg += f"{flag}{ccy:<3} {rate:>5.2f}%  {status}{marker}\n"
    msg += "</code>"
    msg += "<i>* = live update vs fallback</i>\n"
    msg += SEP + "\n"

    msg += "🚀 <b>TOP 3 CARRY OPPORTUNITIES</b>\n"
    for rank, item in enumerate(get_top_carry_pairs(rates, 3), 1):
        b, q = item["base"], item["quote"]
        medal = ["🥇", "🥈", "🥉"][rank - 1]
        msg += (
            f"{medal} <b>{FLAGS.get(b,'')}{b}/{FLAGS.get(q,'')}{q}</b>  "
            f"<code>+{item['spread']:.2f}%</code>\n"
            f"   {item['base_rate']:.2f}% − {item['quote_rate']:.2f}% spread\n"
        )

    swaps = fetch_ic_markets_swaps()
    if swaps:
        msg += SEP + "\n"
        msg += "💱 <b>IC MARKETS SWAP (cTrader live)</b>\n"
        for s in swaps[:4]:
            msg += (
                f"  {s['symbol']}: L <code>{s['swap_long']:+.2f}</code> "
                f"S <code>{s['swap_short']:+.2f}</code> pips/zi\n"
            )

    strongest_ccy, strongest_rate = sorted_rates[0]
    weakest_ccy, weakest_rate = sorted_rates[-1]
    msg += SEP + "\n"
    msg += (
        f"💪 {FLAGS.get(strongest_ccy,'')} <b>{strongest_ccy}</b> {strongest_rate:.2f}% · "
        f"😴 {FLAGS.get(weakest_ccy,'')} <b>{weakest_ccy}</b> {weakest_rate:.2f}%\n"
    )
    msg += SEP + "\n"
    msg += "─────────────────\n"
    msg += "🔱 <b>AUTHORED BY ФорексГод</b> 🔱\n"
    msg += "🏛️ <b>Глитч Ин Матрикс</b> 🏛️"
    return msg


def refresh_rates_daily(notify_telegram: bool = True) -> dict:
    """
    Force refresh cache. Optionally notify Telegram on significant changes.
    V48: cache persisted before Telegram alert; unified meta schema.
    Returns summary dict for logging/cron.
    """
    cache_before = load_cache()
    prev = cache_before.get("rates", {}) if cache_before else dict(FALLBACK_RATES)

    rates, source, fetched_at, changes = get_effective_rates(force_refresh=True)

    change_rows = [{"ccy": c, "old": o, "new": n} for c, o, n in changes]
    summary = {
        "success": _is_usable_source(source),
        "source": source,
        "fetched_at": fetched_at,
        "changes": change_rows,
        "rates": rates,
    }

    _write_refresh_meta(
        source=source,
        fetched_at=fetched_at,
        rates=rates,
        changes=change_rows,
        success=summary["success"],
    )

    # Alert only on confirmed live rate moves (not cache/fallback noise).
    if notify_telegram and source == "live" and changes and _should_send_alert(changes):
        _send_rate_change_alert(changes, source, rates)
        _mark_alert_sent(changes)

    return summary


def _send_telegram_html(text: str) -> None:
    import os
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id or not HAS_REQUESTS:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        logger.warning(f"[macro_rates] Telegram send failed: {e}")


def _send_rate_change_alert(
    changes: List[Tuple[str, float, float]],
    source: str,
    rates: Optional[Dict[str, float]] = None,
) -> None:
    """Professional Telegram alert when a central bank rate moves."""
    now = _now_bucharest().strftime("%d %b %Y · %H:%M EET")
    lines = [
        "<b>[MACRO ALERT] 🏦 MACRO PULSE — RATE CHANGE</b>",
        "────────────────",
        "",
    ]
    for ccy, old, new in changes:
        arrow = "🔺 HIKED" if new > old else "🔻 CUT"
        delta = new - old
        flag = FLAGS.get(ccy, "")
        lines.append(
            f"{arrow}  {flag}<b>{ccy}</b>  "
            f"<code>{old:.2f}%</code> → <code>{new:.2f}%</code>  "
            f"({'+' if delta >= 0 else ''}{delta:.2f}%)"
        )

    if rates:
        old_rates = dict(rates)
        for ccy, old, new in changes:
            old_rates[ccy] = old

        for ccy, old, new in changes:
            lines.append("")
            lines.append(f"<b>📊 Carry pairs afectate ({ccy}):</b>")
            affected = get_top_carry_pairs(rates, top_n=5, triggered_currency=ccy)
            if not affected:
                lines.append(
                    f"  • <i>Nicio perechă Matrix cu {ccy} în pairs_config.</i>"
                )
                continue
            for item in affected[:3]:
                sign = "+" if item["spread"] >= 0 else ""
                lines.append(
                    f"  • <b>{item['pair']}</b> carry {sign}{item['spread']:.2f}% "
                    f"({item['base_rate']:.2f}-{item['quote_rate']:.2f})"
                )
            old_top = get_top_carry_pairs(old_rates, 1, triggered_currency=ccy)
            new_top = get_top_carry_pairs(rates, 1, triggered_currency=ccy)
            if (
                old_top
                and new_top
                and len(affected) > 1
                and old_top[0]["pair"] != new_top[0]["pair"]
            ):
                o, n = old_top[0], new_top[0]
                lines.append(
                    f"  • Best carry shift ({ccy}): {o['pair']} +{o['spread']:.2f}% → "
                    f"{n['pair']} +{n['spread']:.2f}%"
                )

    lines.extend([
        "",
        "────────────────",
        f"<i>🕐 {now} · {source} · investing.com</i>",
        "<i>Verifică setup-uri carry afectate.</i>",
    ])
    _send_telegram_html("\n".join(lines))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Refresh central bank rates cache")
    parser.add_argument("--no-notify", action="store_true")
    parser.add_argument("--print", action="store_true", help="Print rates to stdout")
    args = parser.parse_args()
    result = refresh_rates_daily(notify_telegram=not args.no_notify)
    if args.print:
        print(json.dumps(result, indent=2))
    else:
        print(f"OK source={result['source']} changes={len(result['changes'])}")
