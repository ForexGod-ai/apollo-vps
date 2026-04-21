#!/usr/bin/env python3
"""
⏰ NEWS REMINDER ENGINE V10.4 — 15-MINUTE FLASH ALERTS
────────────────
🔱 AUTHORED BY ФорексГод 🔱
🏛️ Глитч Ин Матрикс 🏛️

Continuous daemon that checks data/upcoming_news.json every 60 seconds.
When a HIGH or MEDIUM impact event is exactly 15 minutes away:
  → Sends a FLASH ALERT to Telegram

KEY PRINCIPLE: INFORMATION ONLY — NO EXECUTION BLOCK.
The bot continues trading normally. This is YOUR personal assistant
that warns you so YOU decide whether to stay in or get out.

Architecture:
  news_fetcher.py (05:00 UTC daily) → data/upcoming_news.json
  news_reminder_engine.py (every 60s) → reads upcoming_news.json → Telegram Flash

Anti-Spam:
  - Each event gets ONE reminder at T-15min
  - Sent events tracked in data/sent_reminders.json (auto-cleaned daily)
  - No duplicate alerts, ever

Usage:
    python3 news_reminder_engine.py                # Start daemon
    python3 news_reminder_engine.py --test         # Send test alert
────────────────
"""

# Windows VPS fix: force UTF-8 stdout to prevent UnicodeEncodeError on emoji
import sys as _sys, io as _io
if hasattr(_sys.stdout, 'buffer'):
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(_sys.stderr, 'buffer'):
    _sys.stderr = _io.TextIOWrapper(_sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import os
import sys
import time
import argparse
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional
try:
    import pytz
    _RO_TZ = pytz.timezone('Europe/Bucharest')
except ImportError:
    _RO_TZ = None

# Setup logging
# Windows VPS fix: force UTF-8 on stdout handler to prevent UnicodeEncodeError on emoji
import io as _io
_utf8_stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'buffer') else sys.stdout
_stream_handler = logging.StreamHandler(_utf8_stdout)
_stream_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s'))
_logs_dir = Path(__file__).parent.resolve() / 'logs'
_logs_dir.mkdir(exist_ok=True)
_file_handler = logging.FileHandler(_logs_dir / 'news_reminder.log', mode='a', encoding='utf-8')
_file_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[_stream_handler, _file_handler])
logger = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    logger.error("❌ requests not installed — run: pip install requests")
    HAS_REQUESTS = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ━━━ CONSTANTS ━━━
SCRIPT_DIR = Path(__file__).parent.resolve()
NEWS_FILE = SCRIPT_DIR / 'data' / 'upcoming_news.json'
SENT_FILE = SCRIPT_DIR / 'data' / 'sent_reminders.json'
LOGS_DIR = SCRIPT_DIR / 'logs'

# ━━━ BRANDING ━━━
UNIVERSAL_SEPARATOR = "────────────────"  # EXACTLY 16 chars

# ━━━ CONFIGURATION ━━━
CHECK_INTERVAL_SECONDS = 60       # Check every 60 seconds
REMINDER_WINDOW_MINUTES = 15      # Alert 15 minutes before event
REMINDER_TOLERANCE_SECONDS = 90   # ±90s window to catch the 15-min mark

# Currency flags for clean formatting
FLAGS = {
    'USD': '🇺🇸', 'EUR': '🇪🇺', 'GBP': '🇬🇧', 'JPY': '🇯🇵',
    'AUD': '🇦🇺', 'NZD': '🇳🇿', 'CAD': '🇨🇦', 'CHF': '🇨🇭',
}

# Impact emojis
IMPACT_EMOJI = {
    'High': '🔴',
    'Medium': '🟠',
}

# Pairs affected by each currency
CURRENCY_PAIRS = {
    'USD': ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'AUDUSD', 'NZDUSD', 'BTCUSD'],
    'EUR': ['EURUSD', 'EURJPY', 'EURGBP', 'EURCHF', 'EURAUD', 'EURCAD', 'EURNZD'],
    'GBP': ['GBPUSD', 'EURGBP', 'GBPJPY', 'GBPCHF', 'GBPAUD', 'GBPCAD', 'GBPNZD'],
    'JPY': ['USDJPY', 'EURJPY', 'GBPJPY', 'AUDJPY', 'NZDJPY', 'CADJPY', 'CHFJPY'],
    'AUD': ['AUDUSD', 'EURAUD', 'GBPAUD', 'AUDJPY', 'AUDCAD', 'AUDNZD', 'AUDCHF'],
    'NZD': ['NZDUSD', 'EURNZD', 'GBPNZD', 'NZDJPY', 'AUDNZD', 'NZDCAD', 'NZDCHF'],
    'CAD': ['USDCAD', 'EURCAD', 'GBPCAD', 'CADJPY', 'AUDCAD', 'NZDCAD'],
    'CHF': ['USDCHF', 'EURCHF', 'GBPCHF', 'CHFJPY', 'AUDCHF', 'NZDCHF', 'CADCHF'],
}


class NewsReminderEngine:
    """
    ⏰ V10.0 — The 15-Minute Flash Alert Engine
    
    Reads data/upcoming_news.json every 60s.
    When an event is 15 minutes away → Telegram Flash Alert.
    ZERO trade blocking — information only.
    """

    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.sent_reminders = self._load_sent_reminders()
        
        if not self.bot_token or not self.chat_id:
            logger.warning("⚠️ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — alerts disabled")
        
        # Ensure directories exist
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        NEWS_FILE.parent.mkdir(parents=True, exist_ok=True)

    # ━━━ STATE PERSISTENCE ━━━

    def _load_sent_reminders(self) -> dict:
        """Load set of already-sent reminder keys to prevent duplicates"""
        try:
            if SENT_FILE.exists():
                with open(SENT_FILE, 'r') as f:
                    data = json.load(f)
                # Auto-clean: remove entries older than 48h
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
                cleaned = {k: v for k, v in data.items() if v > cutoff}
                return cleaned
            return {}
        except Exception:
            return {}

    def _save_sent_reminders(self):
        """Persist sent reminders to disk"""
        try:
            with open(SENT_FILE, 'w') as f:
                json.dump(self.sent_reminders, f, indent=2)
        except Exception as e:
            logger.error(f"⚠️ Could not save sent reminders: {e}")

    def _make_reminder_key(self, event: Dict) -> str:
        """Unique key per event to prevent duplicate alerts"""
        return f"{event['currency']}_{event['event']}_{event['date']}_{event['time']}"

    # ━━━ NEWS FILE READER ━━━

    def _load_upcoming_news(self) -> List[Dict]:
        """Load events from data/upcoming_news.json"""
        try:
            if not NEWS_FILE.exists():
                return []
            with open(NEWS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Handle both formats: dict with 'events' key OR direct list
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get('events', [])
            return []
        except Exception as e:
            logger.error(f"Error reading {NEWS_FILE}: {e}")
            return []

    # ━━━ FLASH ALERT FORMATTER ━━━

    def _format_flash_alert(self, event: Dict) -> str:
        """
        Format a clean, short 15-minute flash alert.
        
        🔔 NEWS IN 15 MINUTES
        ────────────────
        🇺🇸 USD | 📊 HIGH IMPACT
        ⏰ 13:30 UTC
        📰 Non-Farm Employment Change
        📊 Forecast: 180K | Previous: 175K
        
        ⚠️ Affected pairs:
        EURUSD GBPUSD USDJPY USDCHF
        
        💡 Information only — trading continues normally
        
          ────────────────
          🔱 AUTHORED BY ФорексГод 🔱
          ────────────────
          🏛️ Глитч Ин Матрикс 🏛️
        """
        currency = event.get('currency', 'USD')
        flag = FLAGS.get(currency, '🏴')
        impact = event.get('impact', 'High')
        impact_dot = IMPACT_EMOJI.get(impact, '⚪')
        event_name = event.get('event', 'Unknown')
        event_time_utc = event.get('time', '??:??')  # raw UTC string from JSON
        forecast = event.get('forecast', '')
        previous = event.get('previous', '')

        # Convert UTC time → Romania time for display
        try:
            dt_str = event.get('datetime_utc', '')
            if dt_str and _RO_TZ:
                event_dt = datetime.fromisoformat(dt_str)
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=timezone.utc)
                event_dt_ro = event_dt.astimezone(_RO_TZ)
                event_time = event_dt_ro.strftime('%H:%M')
                time_label = 'RO'
            else:
                event_time = event_time_utc
                time_label = 'UTC'
        except Exception:
            event_time = event_time_utc
            time_label = 'UTC'
        
        # Affected pairs — 3-column grid layout
        pairs = CURRENCY_PAIRS.get(currency, [])[:6]  # Max 6 pairs
        # Build rows of 3, each cell padded to 8 chars for alignment
        grid_rows = []
        for i in range(0, len(pairs), 3):
            row = pairs[i:i+3]
            grid_rows.append('  '.join(f"{p:<8}" for p in row).rstrip())
        pairs_grid = '\n'.join(grid_rows)

        # Forecast/Previous line
        data_line = ""
        if forecast or previous:
            parts = []
            if forecast:
                parts.append(f"Forecast: <code>{forecast}</code>")
            if previous:
                parts.append(f"Previous: <code>{previous}</code>")
            data_line = f"📊 {' | '.join(parts)}\n"

        message = (
            f"🔔 <b>NEWS IN 15 MINUTES</b>\n"
            f"{UNIVERSAL_SEPARATOR}\n\n"
            f"{flag} <b>{currency}</b> | {impact_dot} {impact.upper()} IMPACT\n"
            f"⏰ <code>{event_time} {time_label}</code>\n"
            f"📰 {event_name}\n"
            f"{data_line}\n"
            f"⚠️ <b>Affected pairs:</b>\n"
            f"<code>{pairs_grid}</code>\n\n"
            f"💡 <i>Information only — trading continues normally</i>\n\n"
            f"  {UNIVERSAL_SEPARATOR}\n"
            f"  🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
            f"  {UNIVERSAL_SEPARATOR}\n"
            f"  🏛️  <b>Глитч Ин Матрикс</b>  🏛️"
        )
        
        return message

    # ━━━ TELEGRAM SENDER ━━━

    def _send_telegram(self, message: str) -> bool:
        """Send flash alert to Telegram"""
        if not self.bot_token or not self.chat_id or not HAS_REQUESTS:
            return False
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            resp = requests.post(url, json={
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML',
            }, timeout=10)
            if resp.status_code == 200:
                logger.info("📨 Flash alert sent to Telegram")
                return True
            else:
                logger.error(f"❌ Telegram error: {resp.status_code} — {resp.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"❌ Telegram send error: {e}")
            return False

    # ━━━ CORE CHECK LOOP ━━━

    def check_upcoming_events(self):
        """
        Core logic: Check all events. If any is ~15 min away → send alert.
        Called every 60 seconds by the daemon loop.

        ⚠️ DISABLED: news_calendar_monitor.py already sends VOLATILITY RADAR
        alerts at T-15min from economic_calendar.json. Running both causes
        duplicate alerts. This engine keeps running (watchdog compatibility)
        but skips sending to avoid spam.
        """
        return  # Disabled — use news_calendar_monitor.py VOLATILITY RADAR only
        events = self._load_upcoming_news()
        if not events:
            return

        now = datetime.now(timezone.utc)
        target_time = now + timedelta(minutes=REMINDER_WINDOW_MINUTES)
        alerts_sent = 0

        for event in events:
            try:
                # Parse event datetime
                dt_str = event.get('datetime_utc', '')
                if not dt_str:
                    # Reconstruct from date + time
                    dt_str = f"{event['date']}T{event['time']}:00+00:00"

                event_dt = datetime.fromisoformat(dt_str)
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=timezone.utc)

                # Calculate time until event
                diff_seconds = (event_dt - now).total_seconds()

                # Check if event is within the 15-minute window (±90s tolerance)
                target_seconds = REMINDER_WINDOW_MINUTES * 60  # 900s
                if abs(diff_seconds - target_seconds) <= REMINDER_TOLERANCE_SECONDS:
                    # This event is ~15 minutes away!
                    reminder_key = self._make_reminder_key(event)

                    # Anti-spam: check if already sent
                    if reminder_key in self.sent_reminders:
                        continue

                    # Format and send flash alert
                    message = self._format_flash_alert(event)
                    if self._send_telegram(message):
                        self.sent_reminders[reminder_key] = now.isoformat()
                        self._save_sent_reminders()
                        alerts_sent += 1
                        
                        impact = event.get('impact', '?')
                        logger.info(
                            f"🔔 FLASH ALERT: {event['currency']} {event['event']} "
                            f"at {event['time']} UTC ({impact})"
                        )

            except Exception as e:
                logger.debug(f"⚠️ Error checking event: {e}")
                continue

        if alerts_sent > 0:
            logger.info(f"📨 Sent {alerts_sent} flash alert(s) this check")

    # ━━━ DAEMON LOOP ━━━

    def run(self):
        """
        Main daemon loop — runs forever, checks every 60 seconds.
        Watchdog-compatible (always shows RUNNING).
        """
        logger.info("\n" + "=" * 60)
        logger.info("⏰ NEWS REMINDER ENGINE V10.0 — STARTING")
        logger.info(f"🔔 Reminder window: {REMINDER_WINDOW_MINUTES} minutes before event")
        logger.info(f"⏱️  Check interval: {CHECK_INTERVAL_SECONDS} seconds")
        logger.info(f"📂 News file: {NEWS_FILE}")
        logger.info(f"📡 Telegram: {'✅' if self.bot_token else '❌'}")
        logger.info("💡 NO TRADE BLOCKING — information only")
        logger.info("=" * 60 + "\n")

        iteration = 0
        while True:
            iteration += 1
            try:
                self.check_upcoming_events()

                # Log heartbeat every 30 iterations (~30 min)
                if iteration % 30 == 0:
                    events = self._load_upcoming_news()
                    now = datetime.now(timezone.utc)
                    upcoming_today = [
                        e for e in events
                        if e.get('date') == now.strftime('%Y-%m-%d')
                    ]
                    logger.info(
                        f"💓 Heartbeat #{iteration} — "
                        f"{len(events)} events loaded, "
                        f"{len(upcoming_today)} today, "
                        f"{len(self.sent_reminders)} reminders sent"
                    )

                    # Daily cleanup of old sent reminders
                    if iteration % 1440 == 0:  # Every ~24h
                        cutoff = (now - timedelta(hours=48)).isoformat()
                        self.sent_reminders = {
                            k: v for k, v in self.sent_reminders.items() if v > cutoff
                        }
                        self._save_sent_reminders()
                        logger.info("🧹 Cleaned old sent reminders")

            except Exception as e:
                logger.error(f"❌ Check error: {e}")
                # Never crash — daemon must stay alive

            try:
                time.sleep(CHECK_INTERVAL_SECONDS)
            except KeyboardInterrupt:
                logger.warning("\n⚠️ Interrupted by user (Ctrl+C)")
                logger.info("🛑 News Reminder Engine shutting down gracefully")
                break

    # ━━━ TEST MODE ━━━

    def send_test_alert(self):
        """Send a test flash alert to verify Telegram connectivity"""
        test_event = {
            'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'time': (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime('%H:%M'),
            'datetime_utc': (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
            'currency': 'USD',
            'event': '🧪 TEST — Non-Farm Employment Change',
            'impact': 'High',
            'forecast': '180K',
            'previous': '175K',
            'source': 'test',
        }
        
        message = self._format_flash_alert(test_event)
        success = self._send_telegram(message)
        if success:
            logger.info("✅ Test alert sent successfully!")
        else:
            logger.error("❌ Test alert failed — check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        return success


def main():
    parser = argparse.ArgumentParser(description='News Reminder Engine V10.0')
    parser.add_argument('--test', action='store_true', help='Send a test flash alert')
    args = parser.parse_args()

    engine = NewsReminderEngine()

    if args.test:
        engine.send_test_alert()
    else:
        engine.run()


if __name__ == '__main__':
    main()
