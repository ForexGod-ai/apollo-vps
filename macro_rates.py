#!/usr/bin/env python3
"""
macro_rates.py — V38 Live Central Bank Rates Service

Unified source for official CB policy rates (investing.com scrape + JSON cache)
and IC Markets swap carry via cTrader localhost:8767.

Used by: telegram_command_center (/rates), news_calendar_monitor (weekly macro),
         scripts/refresh_cb_rates.py (daily cron).
"""

from __future__ import annotations

import json
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

# Forex symbols for live IC Markets swap section on /rates card
SWAP_CARRY_SYMBOLS = ["GBPJPY", "NZDJPY", "AUDJPY", "USDJPY", "GBPNZD", "EURJPY"]

MIN_LIVE_CURRENCIES = 6
DEFAULT_TTL_HOURS = 6
STALE_CACHE_DAYS = 7
SIGNIFICANT_CHANGE_PCT = 0.25


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


def fetch_live_cb_rates() -> Dict[str, float]:
    """
    Scrape official central bank rates from investing.com.
    Returns partial or empty dict on failure.
    """
    if not HAS_REQUESTS:
        logger.warning("[macro_rates] requests not installed — skip live fetch")
        return {}

    live: Dict[str, float] = {}
    url = "https://www.investing.com/central-banks/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code != 200:
            logger.warning(f"[macro_rates] HTTP {resp.status_code} from investing.com")
            return {}

        if not HAS_BS4:
            logger.warning("[macro_rates] BeautifulSoup not available")
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")
        # investing.com layout (2026): col0=flag, col1=bank name, col2=rate %
        bank_map = [
            ("federal reserve", "USD"),
            ("european central", "EUR"),
            ("bank of england", "GBP"),
            ("swiss national", "CHF"),
            ("reserve bank of australia", "AUD"),
            ("bank of canada", "CAD"),
            ("reserve bank of new zealand", "NZD"),
            ("bank of japan", "JPY"),
        ]
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
            for key, ccy in bank_map:
                if key in row_text and ccy not in live:
                    live[ccy] = rate_val
                    break

        if len(live) >= MIN_LIVE_CURRENCIES:
            logger.success(f"[macro_rates] live fetch OK ({len(live)} currencies): {live}")
        else:
            logger.warning(f"[macro_rates] only {len(live)} currencies parsed — rejected")

    except Exception as e:
        logger.warning(f"[macro_rates] scrape failed: {e}")

    return live if len(live) >= MIN_LIVE_CURRENCIES else {}


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


def get_effective_rates(
    force_refresh: bool = False,
    ttl_hours: float = DEFAULT_TTL_HOURS,
) -> Tuple[Dict[str, float], str, Optional[str], List[Tuple[str, float, float]]]:
    """
    Returns (rates, source_label, fetched_at_iso, changes_vs_previous_cache).

    Priority:
      1. Fresh live scrape (if force or cache stale)
      2. Valid cache file
      3. FALLBACK_RATES
    """
    cache = load_cache()
    changes: List[Tuple[str, float, float]] = []
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
            return effective, "live (investing.com)", fetched_at, changes

    if cache and cache.get("rates"):
        age_h = _cache_age_hours(cache)
        if age_h < ttl_hours * 4:  # accept cache up to 24h when live fails
            return (
                cache["rates"],
                f"cache ({cache.get('source', 'unknown')})",
                cache.get("fetched_at"),
                [],
            )

    logger.warning("[macro_rates] using FALLBACK_RATES — no live data and no recent cache")
    return dict(FALLBACK_RATES), "fallback (manual baseline)", None, []


def is_cache_stale(days: int = STALE_CACHE_DAYS) -> bool:
    cache = load_cache()
    if not cache or not cache.get("fetched_at"):
        return True
    try:
        fetched = datetime.fromisoformat(cache["fetched_at"])
        return (_now_bucharest() - fetched) > timedelta(days=days)
    except Exception:
        return True


def get_top_carry_pairs(rates: Dict[str, float], top_n: int = 3) -> List[dict]:
    spreads = []
    for base, quote in CARRY_PAIRS:
        b = rates.get(base, 0.0)
        q = rates.get(quote, 0.0)
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
    """Live swap from cTrader MarketDataProvider (IC Markets on VPS)."""
    if not HAS_REQUESTS:
        return []
    symbols = symbols or SWAP_CARRY_SYMBOLS
    results = []
    for sym in symbols:
        try:
            resp = requests.get(
                "http://localhost:8767/swap_info",
                params={"symbol": sym},
                timeout=5,
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


def format_rates_telegram_message(
    separator: str = "────────────────",
    include_swaps: bool = True,
    force_refresh: bool = False,
) -> str:
    """Build /rates Telegram HTML card."""
    rates, source, fetched_at, _ = get_effective_rates(force_refresh=force_refresh)
    now = _now_bucharest()

    if fetched_at:
        try:
            ts = datetime.fromisoformat(fetched_at)
            ts_str = ts.strftime("%d %b %Y %H:%M EET")
        except Exception:
            ts_str = fetched_at
    else:
        ts_str = now.strftime("%d %b %Y %H:%M EET")

    year = now.year
    msg = (
        f"<b>🏦 CENTRAL BANK RATES — {year}</b>\n"
        f"<i>Actualizat: {ts_str} | sursă: {source}</i>\n"
        f"{separator}\n\n"
    )

    if is_cache_stale() and source.startswith("fallback"):
        msg += "⚠️ <b>Date posibil depășite — verifică VPS / rețea</b>\n\n"

    sorted_rates = sorted(rates.items(), key=lambda x: x[1], reverse=True)
    strong_threshold = 3.50

    for ccy, rate in sorted_rates:
        flag = FLAGS.get(ccy, "")
        filled = min(6, max(0, round(rate)))
        bar = "▰" * filled + "▱" * (6 - filled)
        status = "🟢 Strong" if rate >= strong_threshold else "🔴 Weak"
        live_marker = ""
        if abs(rate - FALLBACK_RATES.get(ccy, rate)) >= 0.01:
            live_marker = " *"
        msg += f"{flag} <b>{ccy}</b>  {rate:.2f}%  {bar}  {status}{live_marker}\n"

    msg += f"\n{separator}\n"
    msg += f"<b>🎯 TOP CARRY PAIRS (Buy High / Sell Low)</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for idx, item in enumerate(get_top_carry_pairs(rates, 3)):
        b, q = item["base"], item["quote"]
        msg += (
            f"{medals[idx]} <b>{FLAGS.get(b,'')}{b}/{FLAGS.get(q,'')}{q}</b>\n"
            f"   📈 Diff: <b>+{item['spread']:.2f}%</b>  "
            f"({item['base_rate']:.2f}% vs {item['quote_rate']:.2f}%)\n\n"
        )

    if include_swaps:
        swaps = fetch_ic_markets_swaps()
        if swaps:
            msg += f"{separator}\n"
            msg += f"<b>💱 IC MARKETS CARRY (live swap cTrader)</b>\n\n"
            for s in swaps[:6]:
                sym = s["symbol"]
                msg += (
                    f"• <b>{sym}</b>  "
                    f"Long: <code>{s['swap_long']:+.2f}</code>  "
                    f"Short: <code>{s['swap_short']:+.2f}</code> pips/zi\n"
                )
            msg += f"\n<i>Swap = cost/credit overnight real de la broker</i>\n"

    msg += f"\n{separator}\n"
    msg += f"<i>* = diferă de baseline fallback</i>"
    return msg


def format_weekly_macro_report(local_tz=None) -> str:
    """Weekly macro table — same data source as /rates."""
    rates, source, fetched_at, changes = get_effective_rates(force_refresh=True)
    sorted_rates = sorted(rates.items(), key=lambda x: x[1], reverse=True)
    all_vals = [v for _, v in sorted_rates]
    median_rate = sorted(all_vals)[len(all_vals) // 2] if all_vals else 0.0

    if local_tz:
        now_ro = datetime.now(local_tz).replace(tzinfo=None)
    else:
        now_ro = _now_bucharest()

    week_str = now_ro.strftime("W%W • %d %b %Y")
    SEP = "━━━━━━━━━━━━━━━━"

    ts_label = ""
    if fetched_at:
        try:
            ts_label = datetime.fromisoformat(fetched_at).strftime("%d %b %H:%M")
        except Exception:
            ts_label = fetched_at

    msg = "🏦 <b>MACRO WEEKLY TABLE</b>\n"
    msg += f"📅 <b>{week_str}</b>\n"
    msg += f"🕐 <i>Transmis {now_ro.strftime('%H:%M')} EET"
    if ts_label:
        msg += f" | rate fetch: {ts_label} ({source})"
    msg += "</i>\n"
    msg += SEP + "\n"

    if is_cache_stale():
        msg += "⚠️ <b>Rate macro stale (&gt;7 zile) — verifică VPS</b>\n" + SEP + "\n"

    if changes:
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
    Returns summary dict for logging/cron.
    """
    cache_before = load_cache()
    prev = cache_before.get("rates", {}) if cache_before else dict(FALLBACK_RATES)

    rates, source, fetched_at, changes = get_effective_rates(force_refresh=True)

    summary = {
        "success": source.startswith("live") or bool(cache_before),
        "source": source,
        "fetched_at": fetched_at,
        "changes": [{"ccy": c, "old": o, "new": n} for c, o, n in changes],
        "rates": rates,
    }

    LAST_REFRESH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LAST_REFRESH_FILE, "w", encoding="utf-8") as f:
        json.dump({**summary, "refreshed_at": _now_bucharest().isoformat()}, f, indent=2)

    if notify_telegram and changes:
        _send_rate_change_alert(changes, source)

    if notify_telegram and is_cache_stale() and not source.startswith("live"):
        _send_stale_alert(source)

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


def _send_rate_change_alert(changes: List[Tuple[str, float, float]], source: str) -> None:
    lines = ["🚨 <b>MACRO RATE CHANGE</b>", "────────────────"]
    for ccy, old, new in changes:
        arrow = "🔺" if new > old else "🔻"
        flag = FLAGS.get(ccy, "")
        lines.append(f"{arrow} {flag} <b>{ccy}</b>: {old:.2f}% → <b>{new:.2f}%</b>")
    lines.append(f"\n<i>Sursă: {source}</i>")
    _send_telegram_html("\n".join(lines))


def _send_stale_alert(source: str) -> None:
    _send_telegram_html(
        "⚠️ <b>MACRO RATES STALE</b>\n"
        "────────────────\n"
        f"Cache-ul de dobânzi centrale are &gt;7 zile sau fetch-ul live a eșuat.\n"
        f"Sursă curentă: <code>{source}</code>\n"
        "Verifică VPS / investing.com scrape."
    )


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
