#!/usr/bin/env python3
"""
📡 NEWS FETCHER V10.0 — DAILY AUTO-SYNC
────────────────
🔱 AUTHORED BY ФорексГод 🔱
🏛️ Глитч Ин Матрикс 🏛️

Automatically downloads HIGH + MEDIUM impact economic events every day.
Runs at 05:00 UTC via launchd — populates data/upcoming_news.json.

Data Sources (in priority order):
  1. Trading Economics public API (free, no key)
  2. ForexFactory RSS fallback
  3. Manual economic_calendar.json as last resort

NO TRADE BLOCKING — information only.
The news_reminder_engine.py reads the output file for 15-min alerts.

Usage:
    python3 news_fetcher.py              # Fetch today + 7 days
    python3 news_fetcher.py --days 14    # Fetch today + 14 days
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
from typing import List, Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/news_fetcher.log', mode='a')
    ]
)
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


def fetch_forexfactory_mirror(days_ahead: int = 7) -> List[Dict]:
    """
    Source #1 (PRIMARY): ForexFactory calendar via faireconomy.media free JSON mirror.
    No API key, no Selenium, no Cloudflare — just clean JSON.
    Returns this week + next week events.
    """
    if not HAS_REQUESTS:
        return []

    try:
        logger.info("📡 [Source 1] Fetching from ForexFactory mirror (faireconomy.media)...")

        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=days_ahead)

        # Fetch this week and next week
        urls = [
            'https://nfs.faireconomy.media/ff_calendar_thisweek.json',
            'https://nfs.faireconomy.media/ff_calendar_nextweek.json',
        ]

        all_raw = []
        for url in urls:
            try:
                resp = requests.get(url, timeout=15, headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                })
                if resp.status_code == 200:
                    data = resp.json()
                    all_raw.extend(data)
                    logger.info(f"📥 {url.split('/')[-1]}: {len(data)} events")
                else:
                    logger.warning(f"⚠️ {url.split('/')[-1]}: HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ Error fetching {url.split('/')[-1]}: {e}")

        if not all_raw:
            return []

        # Impact mapping from ForexFactory format
        impact_map = {
            'High': 'High',
            'Medium': 'Medium',
            'Low': 'Low',
            'Holiday': 'Low',
            'Non-Economic': 'Low',
        }

        events = []
        for item in all_raw:
            impact = impact_map.get(item.get('impact', ''), 'Low')
            # Only HIGH + MEDIUM
            if impact not in ('High', 'Medium'):
                continue

            currency = item.get('country', '')
            if currency not in MAJOR_CURRENCIES:
                continue

            date_str = item.get('date', '')
            if not date_str:
                continue

            # Parse ISO date: "2026-03-11T13:30:00-04:00"
            try:
                event_dt = datetime.fromisoformat(date_str)
                # Convert to UTC
                event_dt_utc = event_dt.astimezone(timezone.utc)
            except Exception:
                continue

            # Filter by date range
            if event_dt_utc < now or event_dt_utc > end_date:
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

        logger.info(f"✅ Parsed {len(events)} HIGH/MEDIUM events from ForexFactory mirror")
        return events

    except Exception as e:
        logger.error(f"❌ ForexFactory mirror error: {e}")
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
    Source #2 (Fallback): Load from local economic_calendar.json.
    Uses the manually curated monthly sections.
    """
    try:
        logger.info("📖 [Source 2] Loading from manual economic_calendar.json...")

        if not CALENDAR_FILE.exists():
            logger.warning("⚠️ economic_calendar.json not found")
            return []

        with open(CALENDAR_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=days_ahead)

        # Try current month and next month sections
        events = []
        for month_offset in range(2):
            target = now + timedelta(days=month_offset * 30)
            section_name = f"custom_events_{target.strftime('%B_%Y').lower()}"
            section_events = data.get(section_name, [])

            for e in section_events:
                try:
                    date_str = e.get('date', '')
                    time_str = e.get('time', '12:00')
                    event_dt = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
                    event_dt = event_dt.replace(tzinfo=timezone.utc)

                    if event_dt < now or event_dt > end_date:
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

        logger.info(f"✅ Loaded {len(events)} events from manual calendar")
        return events

    except Exception as e:
        logger.error(f"❌ Manual calendar error: {e}")
        return []


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
            f"  🏛️ Глитч Ин Матрикс 🏛️"
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
    parser = argparse.ArgumentParser(description='News Fetcher V10.0 — Daily Auto-Sync')
    parser.add_argument('--days', type=int, default=7, help='Days ahead to fetch (default: 7)')
    args = parser.parse_args()

    # Ensure logs directory exists
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("📡 NEWS FETCHER V10.0 — DAILY AUTO-SYNC")
    logger.info(f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    logger.info(f"📅 Fetching next {args.days} days")
    logger.info("=" * 60)

    # Load .env for Telegram credentials
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    all_events = []

    # Source 1 (PRIMARY): ForexFactory mirror — free, no key, reliable
    ff_events = fetch_forexfactory_mirror(days_ahead=args.days)
    if ff_events:
        all_events.extend(ff_events)
        logger.info(f"✅ ForexFactory mirror: {len(ff_events)} events")
    else:
        logger.warning("⚠️ ForexFactory mirror: 0 events")

    # Source 2: Trading Economics API (may need API key)
    if not ff_events:
        te_events = fetch_trading_economics(days_ahead=args.days)
        if te_events:
            all_events.extend(te_events)
            logger.info(f"✅ Trading Economics: {len(te_events)} events")
        else:
            logger.warning("⚠️ Trading Economics: 0 events (API down or needs key)")

    # Source 3: Manual calendar fallback (always check for extra events)
    manual_events = fetch_from_manual_calendar(days_ahead=args.days)
    if manual_events:
        all_events.extend(manual_events)
        logger.info(f"✅ Manual Calendar: {len(manual_events)} events")

    if not all_events:
        logger.error("❌ NO EVENTS from any source! Check API connectivity.")
        logger.error("💡 Update economic_calendar.json: python3 add_monthly_events.py")
        return

    # Deduplicate
    unique_events = deduplicate_events(all_events)
    logger.info(f"📊 Total unique events: {len(unique_events)} (from {len(all_events)} raw)")

    # Save to data/upcoming_news.json
    if save_events(unique_events):
        logger.info(f"💾 Output: {OUTPUT_FILE}")

    # Send Telegram summary
    send_sync_summary(unique_events)

    logger.info("=" * 60)
    logger.info("✅ NEWS FETCHER V10.0 — SYNC COMPLETE")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
