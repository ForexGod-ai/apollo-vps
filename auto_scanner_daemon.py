"""
⏰ AUTO SCANNER DAEMON - Glitch in Matrix V44.2
Rulează daily_scanner.py automat Luni/Miercuri/Vineri la 07:00 ora București

Logică:
  - Loop infinit, verifică ora la fiecare 60 secunde
  - Declanșează daily_scanner.py (15 perechi × D1/H4/H1/W1 + raport Telegram)
  - Timezone: Europe/Bucharest (EEST = UTC+3, EET = UTC+2)
  - Anti-double-trigger: last_auto_scan.json salvat DOAR după scan reușit
  - Retry automat în fereastra 07:00–07:59 dacă scanul eșuează / timeout
  - Trimite notificare Telegram la start + finish

Loguri VPS (watchdog redirect stdout → auto_scanner_daemon_stdout.log):
  - logs/auto_scanner.log              — loguru (daemon)
  - logs/auto_scanner_daemon_stdout.log — stdout watchdog (cel mai recent)
  - logs/daily_scanner_subprocess.log   — output live daily_scanner.py
"""

import os
import sys
import json
import time
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, date, timedelta
from loguru import logger
from dotenv import load_dotenv

# ✅ V14.4 TIMEZONE FIX: pytz explicit — nu depindem de setarea VPS-ului (UTC vs EET)
try:
    import pytz
    _BUCHAREST_TZ = pytz.timezone('Europe/Bucharest')
    _HAS_PYTZ = True
except ImportError:
    _HAS_PYTZ = False

load_dotenv()

# ━━━ CONFIG ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCAN_HOUR = 7           # 07:00 ora București
SCAN_MINUTE = 0         # :00
SCAN_DAYS = {0, 2, 4}  # Monday=0, Wednesday=2, Friday=4
CHECK_INTERVAL = 60     # Verifică la fiecare 60 secunde
        # V67: 16 perechi × cTrader + SMC — plasă de siguranță 20 min (perf target < 12 min)
SCAN_TIMEOUT_SEC = int(os.getenv('AUTO_SCAN_TIMEOUT_SEC', '1200'))
SCAN_WINDOW_END_MINUTE = 59  # retry până la 07:59 dacă scanul a eșuat

# ── Weekly Report: Vineri 23:59 EET (după închiderea pieței Forex) ──
WEEKLY_REPORT_HOUR = 23
WEEKLY_REPORT_MINUTE = 59
WEEKLY_REPORT_DAY = 4  # Friday

BASE_DIR = Path(__file__).parent
LAST_SCAN_FILE = BASE_DIR / "data" / "last_auto_scan.json"
SCAN_LOCK_FILE = BASE_DIR / "data" / "auto_scan_in_progress.lock"
DAILY_SCANNER_SUBPROCESS_LOG = BASE_DIR / "logs" / "daily_scanner_subprocess.log"
LAST_WEEKLY_REPORT_FILE = BASE_DIR / "data" / "last_weekly_report.json"
LAST_CB_RATES_REFRESH_FILE = BASE_DIR / "data" / "last_cb_rates_refresh.json"

# V38: daily macro rates refresh at 08:00 Bucharest
CB_RATES_REFRESH_HOUR = 8
CB_RATES_REFRESH_MINUTE = 0

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

DAY_NAMES = {0: "Luni", 1: "Marți", 2: "Miercuri", 3: "Joi", 4: "Vineri", 5: "Sâmbătă", 6: "Duminică"}


# ━━━ TIMEZONE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_bucharest_time() -> datetime:
    """
    Returnează ora curentă în Europa/București.
    ✅ V14.4: pytz explicit — corect indiferent dacă VPS-ul e pe UTC sau EET.
    Dacă pytz nu e instalat → fallback la ora sistemului (comportament vechi).
    """
    if _HAS_PYTZ:
        return datetime.now(_BUCHAREST_TZ).replace(tzinfo=None)
    return datetime.now()


# ━━━ TELEGRAM ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def send_telegram(message: str):
    """Trimite mesaj Telegram (non-blocking, fail-safe)"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logger.warning(f"[Telegram] Send failed: {e}")


# ━━━ LAST SCAN STATE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_last_scan_date() -> str:
    """Citește data ultimului scan automat (format: YYYY-MM-DD)"""
    try:
        if LAST_SCAN_FILE.exists():
            with open(LAST_SCAN_FILE, 'r') as f:
                data = json.load(f)
                return data.get('last_scan_date', '')
    except Exception:
        pass
    return ''


def save_last_scan_date(scan_date: str, *, success: bool = True):
    """Salvează data ultimului scan — doar după succes (V44.2)."""
    try:
        LAST_SCAN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LAST_SCAN_FILE, 'w') as f:
            json.dump({
                'last_scan_date': scan_date,
                'last_scan_timestamp': datetime.now().isoformat(),
                'last_scan_success': success,
                'updated_by': 'auto_scanner_daemon.py'
            }, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save last scan date: {e}")


def is_scan_in_progress() -> bool:
    """Lock file — evită 2 scanuri paralele când primul depășește 5 min."""
    try:
        if not SCAN_LOCK_FILE.exists():
            return False
        # Lock stale > 20 min (proces mort fără cleanup)
        age_sec = time.time() - SCAN_LOCK_FILE.stat().st_mtime
        if age_sec > max(SCAN_TIMEOUT_SEC + 300, 1200):
            logger.warning(f"[SCAN LOCK] Stale lock ({age_sec:.0f}s) — removing")
            SCAN_LOCK_FILE.unlink(missing_ok=True)
            return False
        return True
    except Exception:
        return False


def acquire_scan_lock() -> bool:
    try:
        SCAN_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        if is_scan_in_progress():
            return False
        with open(SCAN_LOCK_FILE, 'w', encoding='utf-8') as f:
            json.dump({'pid': os.getpid(), 'started_at': datetime.now().isoformat()}, f)
        return True
    except Exception as e:
        logger.warning(f"Could not acquire scan lock: {e}")
        return True  # fail-open — nu blocăm scanul permanent


def release_scan_lock():
    try:
        SCAN_LOCK_FILE.unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Could not release scan lock: {e}")


def is_scan_trigger_window(now: datetime, scan_hour: int, scan_minute: int) -> bool:
    """
    V44.2: Fereastră 07:00–07:59 (retry dacă eșuează).
    V11.3 folosea doar 07:00–07:04 — prea îngust + save prematur = scan pierdut.
    """
    if now.hour != scan_hour:
        return False
    return scan_minute <= now.minute <= SCAN_WINDOW_END_MINUTE


# ━━━ CORE: RUN SCAN ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def run_auto_scan():
    """
    Execută secvența completă de scan:
      1. reset_matrix.py  — șterge setups vechi
      2. daily_scanner.py — scanează piețele, trimite raport
    """
    now = get_bucharest_time()
    day_name = DAY_NAMES.get(now.weekday(), "?")
    timestamp = now.strftime('%d %b %Y, %H:%M:%S')

    logger.success(f"")
    logger.success(f"{'='*60}")
    logger.success(f"[AUTO SCAN] TRIGGER - {day_name} {timestamp}")
    logger.success(f"{'='*60}")

    _sep = "────────────────"
    send_telegram(
        f"<b>ФорексГод.АИ</b>\n"
        f"⏰ <b>AUTO SCAN PORNIT</b>\n"
        f"{_sep}\n"
        f"📅 {day_name}, {timestamp}\n"
        f"🔄 Scanez piețele... (setup-urile vechi sunt pastrate)\n"
        f"⏳ Scanul durează ~5-12 minute (16 perechi × cTrader API)\n"
        f"{_sep}\n"
        f"🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
        f"{_sep}\n"
        f"🏛 <b>ГЛИТЧ ИН МАТРИКС</b> 🏛"
    )

    python = sys.executable
    scan_ok = False

    # ── News sync before scan (upcoming_news.json for /news + blackout guard) ──
    logger.info("[Step 0/1] Running news_fetcher.py --days 14...")
    try:
        news_result = subprocess.run(
            [python, 'news_fetcher.py', '--days', '14'],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'},
        )
        if news_result.returncode == 0:
            logger.success("[Step 0/1] news_fetcher.py DONE")
        else:
            logger.warning(
                f"[Step 0/1] news_fetcher.py exit {news_result.returncode} — scan continues"
            )
    except Exception as news_err:
        logger.warning(f"[Step 0/1] news_fetcher skipped: {news_err}")

    # ── Daily Scanner (SMCDetector — merge cu setups existente) ──────────────
    logger.info(
        f"[Step 1/1] Running daily_scanner.py (timeout={SCAN_TIMEOUT_SEC}s, "
        f"log={DAILY_SCANNER_SUBPROCESS_LOG.name})..."
    )
    subprocess_log_path = DAILY_SCANNER_SUBPROCESS_LOG
    subprocess_log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # ✅ V14.6 FIX: Force UTF-8 in child process so emoji prints don't crash
        child_env = os.environ.copy()
        child_env['PYTHONIOENCODING'] = 'utf-8'
        child_env['PYTHONUTF8'] = '1'
        child_env['PYTHONUNBUFFERED'] = '1'
        child_env['SCANNER_DEBUG'] = '0'
        child_env['SCANNER_QUIET'] = '1'
        child_env['AUTO_SCAN'] = '1'

        with open(subprocess_log_path, 'a', encoding='utf-8', errors='replace') as scan_log:
            scan_log.write(f"\n{'=' * 60}\n")
            scan_log.write(f"[AUTO SCAN] {day_name} {timestamp} — daily_scanner.py start\n")
            scan_log.write(f"{'=' * 60}\n")
            scan_log.flush()

            result = subprocess.run(
                [python, '-u', 'daily_scanner.py'],
                cwd=str(BASE_DIR),
                stdout=scan_log,
                stderr=subprocess.STDOUT,
                timeout=SCAN_TIMEOUT_SEC,
                env=child_env,
            )
            scan_log.write(
                f"\n[EXIT] code={result.returncode} at "
                f"{get_bucharest_time().strftime('%H:%M:%S')}\n"
            )
            scan_log.flush()

        if result.returncode == 0:
            logger.success("[Step 1/1] daily_scanner.py DONE")
            scan_ok = True
        else:
            logger.error(f"[Step 1/1] daily_scanner.py FAILED (code {result.returncode})")
            tail = _read_log_tail(subprocess_log_path, 1500)
            if tail:
                logger.error(f"Subprocess log (last 1500 chars):\n{tail}")
            _sep = "────────────────"
            send_telegram(
                f"❌ <b>SCAN ERROR (code {result.returncode})</b>\n"
                f"{_sep}\n"
                f"<pre>{tail[:800] if tail else 'No output captured'}</pre>"
            )
    except subprocess.TimeoutExpired:
        logger.error(f"[Step 1/1] daily_scanner.py TIMEOUT ({SCAN_TIMEOUT_SEC}s)")
        send_telegram(
            f"⏰ <b>AUTO SCAN TIMEOUT</b>\n"
            f"daily_scanner.py a depășit {SCAN_TIMEOUT_SEC // 60} minute!\n"
            f"Verifică logs/daily_scanner_subprocess.log pe VPS."
        )
    except Exception as e:
        logger.error(f"[Step 1/1] daily_scanner.py ERROR: {e}")
        send_telegram(f"💥 <b>SCAN EXCEPTION</b>\n<code>{str(e)[:500]}</code>")

    # ── Finish notification ──────────────────────────────
    finish_time = get_bucharest_time().strftime('%H:%M:%S')
    if scan_ok:
        _sep = "────────────────"
        logger.success(f"[AUTO SCAN] COMPLETED successfully at {finish_time}")
        send_telegram(
            f"<b>ФорексГод.АИ</b>\n"
            f"✅ <b>AUTO SCAN COMPLET</b>\n"
            f"{_sep}\n"
            f"📅 {day_name} — Ora: {finish_time}\n"
            f"📊 Următorul scan: vezi /status\n"
            f"💡 Folosește /monitoring pentru setup-uri noi\n"
            f"{_sep}\n"
            f"🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
            f"{_sep}\n"
            f"🏛 <b>ГЛИТЧ ИН МАТРИКС</b> 🏛"
        )
    else:
        logger.error(f"[AUTO SCAN] FAILED at {finish_time}")
        send_telegram(
            f"<b>ФорексГод.АИ</b>\n"
            f"❌ <b>AUTO SCAN EȘUAT</b>\n"
            f"{_sep}\n"
            f"📅 {day_name} — Ora: {finish_time}\n"
            f"⚠️ Verifică logs/daily_scanner_subprocess.log\n"
            f"⚠️ sau logs/auto_scanner_daemon_stdout.log pe VPS\n"
            f"🔧 Rulează manual: python daily_scanner.py\n"
            f"{_sep}\n"
            f"🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
            f"{_sep}\n"
            f"🏛 <b>ГЛИТЧ ИН МАТРИКС</b> 🏛"
        )

    return scan_ok


def _read_log_tail(path: Path, max_chars: int = 1500) -> str:
    try:
        if not path.exists():
            return ''
        text = path.read_text(encoding='utf-8', errors='replace')
        return text.strip()[-max_chars:]
    except Exception:
        return ''


# ━━━ WEEKLY REPORT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_last_weekly_report_date() -> str:
    """Citește data ultimului weekly report trimis"""
    try:
        if LAST_WEEKLY_REPORT_FILE.exists():
            with open(LAST_WEEKLY_REPORT_FILE, 'r') as f:
                data = json.load(f)
                return data.get('last_weekly_report_date', '')
    except Exception:
        pass
    return ''


def save_last_weekly_report_date(report_date: str):
    """Salvează data ultimului weekly report trimis"""
    try:
        LAST_WEEKLY_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LAST_WEEKLY_REPORT_FILE, 'w') as f:
            json.dump({
                'last_weekly_report_date': report_date,
                'last_weekly_report_timestamp': datetime.now().isoformat(),
                'updated_by': 'auto_scanner_daemon.py'
            }, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save weekly report date: {e}")


# ━━━ V38: DAILY CB RATES REFRESH ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_last_cb_rates_refresh_date() -> str:
    try:
        from macro_rates import get_last_refresh_date
        return get_last_refresh_date()
    except Exception:
        pass
    return ''


def run_daily_cb_rates_refresh():
    """Refresh central bank rates cache + optional Telegram alert on change."""
    try:
        from macro_rates import refresh_rates_daily
        result = refresh_rates_daily(notify_telegram=True)
        logger.info(
            f"[CB_RATES] refresh source={result.get('source')} "
            f"changes={len(result.get('changes', []))}"
        )
        return True
    except Exception as e:
        logger.error(f"[CB_RATES] refresh failed: {e}")
        return False


def send_weekly_report():
    """Construieste și trimite Weekly Report pe Telegram — rulat Vineri 23:59 EET"""
    from trade_manager import TradeManager

    now = get_bucharest_time()
    week_ago = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    week_start_label = (now - timedelta(days=7)).strftime('%d %b')
    week_end_label = now.strftime('%d %b %Y')

    _sep = "────────────────"
    weekly = TradeManager(BASE_DIR).get_weekly_pnl(week_ago)
    total = weekly['total']
    wins = weekly['wins']
    losses = weekly['losses']
    total_pnl = weekly['total_pnl']
    best_trade = weekly['best_trade']
    worst_trade = weekly['worst_trade']
    logger.info(
        f"[WeeklyReport] source={weekly.get('source')} "
        f"synced={weekly.get('broker_synced')} window>={week_ago}"
    )

    win_rate = (wins / total * 100) if total > 0 else 0
    avg_pnl = (total_pnl / total) if total > 0 else 0.0
    pnl_emoji = "🔥" if total_pnl > 0 else ("💥" if total_pnl < 0 else "⚪")
    wr_emoji = "✅" if win_rate >= 50 else "⚠️"

    message = (
        f"<b>ФорексГод.АИ</b>\n"
        f"📈 <b>WEEKLY REPORT — VINERI</b>\n"
        f"{_sep}\n"
        f"<b>📅 {week_start_label} — {week_end_label}</b>\n"
        f"{_sep}\n"
        f"{pnl_emoji} <b>Total P&amp;L</b>\n"
        f"<code>${total_pnl:+.2f}</code>\n\n"
        f"📋 <b>Trades executate</b>\n"
        f"<code>{total}</code>\n\n"
        f"✅ <b>Wins</b> / ❌ <b>Losses</b>\n"
        f"<code>{wins}</code> • <code>{losses}</code>\n\n"
        f"{wr_emoji} <b>Win Rate</b>\n"
        f"<code>{win_rate:.1f}%</code>\n\n"
        f"💵 <b>Profit Mediu / Trade</b>\n"
        f"<code>${avg_pnl:+.2f}</code>\n"
    )
    if best_trade is not None:
        message += (
            f"\n🏆 <b>Best Trade</b>\n"
            f"<code>${best_trade:+.2f}</code>\n"
            f"💣 <b>Worst Trade</b>\n"
            f"<code>${worst_trade:+.2f}</code>\n"
        )
    message += _sep

    logger.success(f"[WeeklyReport] Sending — {total} trades, P&L ${total_pnl:+.2f}, WR {win_rate:.1f}%")
    send_telegram(message)


# ━━━ MAIN LOOP ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    parser = argparse.ArgumentParser(description='Auto Scanner Daemon - Mon/Wed/Fri 07:00 Bucharest')
    parser.add_argument('--scan-hour', type=int, default=SCAN_HOUR, help='Ora scanului (default: 7)')
    parser.add_argument('--scan-minute', type=int, default=SCAN_MINUTE, help='Minutul scanului (default: 0)')
    parser.add_argument('--run-now', action='store_true', help='Ruleaza scanul imediat (test mode)')
    parser.add_argument('--weekly-now', action='store_true', help='Trimite Weekly Report imediat (manual trigger)')
    args = parser.parse_args()

    scan_hour = args.scan_hour
    scan_minute = args.scan_minute

    # ── Setup logging ────────────────────────────────────
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    logger.remove()
    logger.add(sys.stdout, format="{time:HH:mm:ss} | {level:<7} | {message}", level="INFO")
    logger.add(
        str(log_dir / "auto_scanner.log"),
        rotation="7 days",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}",
        level="DEBUG",
        enqueue=True,  # V44.2: flush async pe Windows — evită log blocat în buffer
    )

    logger.info("")
    logger.info("=" * 60)
    logger.info("  AUTO SCANNER DAEMON - Glitch in Matrix V44.2")
    logger.info("=" * 60)
    logger.info(f"  Trigger: Luni / Miercuri / Vineri la {scan_hour:02d}:{scan_minute:02d} Bucuresti")
    logger.info(f"  Timeout: {SCAN_TIMEOUT_SEC}s | Retry window: {scan_hour:02d}:00-{scan_hour:02d}:59")
    logger.info(f"  Subprocess log: {DAILY_SCANNER_SUBPROCESS_LOG}")
    logger.info(f"  Watchdog stdout: logs/auto_scanner_daemon_stdout.log")
    logger.info(f"  Python:  {sys.executable}")
    logger.info(f"  Dir:     {BASE_DIR}")
    logger.info(f"  State:   {LAST_SCAN_FILE}")
    logger.info("=" * 60)
    logger.info("")

    # ── Run now mode (manual test) ───────────────────────
    if args.run_now:
        logger.warning("[--run-now] Manual trigger! Running scan immediately...")
        if acquire_scan_lock():
            try:
                scan_ok = run_auto_scan()
                if scan_ok:
                    save_last_scan_date(date.today().isoformat())
            finally:
                release_scan_lock()
        logger.info("[--run-now] Done. Exiting.")
        return

    # ── Weekly now mode (manual trigger) ─────────────────
    if args.weekly_now:
        logger.warning("[--weekly-now] Manual trigger! Sending Weekly Report immediately...")
        send_weekly_report()
        today_str = date.today().isoformat()
        save_last_weekly_report_date(today_str)
        logger.info("[--weekly-now] Done. Exiting.")
        return

    # ── Startup Telegram notification ───────────────────
    next_days = [DAY_NAMES[d] for d in sorted(SCAN_DAYS)]
    _sep = "──────────────────"
    send_telegram(
        f"⏰ <b>AUTO SCANNER DAEMON ONLINE</b>\n"
        f"{_sep}\n"
        f"📅 Scan: {', '.join(next_days)} la {scan_hour:02d}:{scan_minute:02d}\n"
        f"🕐 Ora sistem: {get_bucharest_time().strftime('%H:%M:%S')}\n"
        f"📊 Auto-restart enabled\n"
        f"📈 State tracking active\n"
        f"{_sep}\n"
        f"🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
        f"{_sep}\n"
        f"🏛️  <b>Глитч Ин Матрикс</b>  🏛️"
    )

    logger.info(f"[DAEMON] Loop started. Checking every {CHECK_INTERVAL}s...")

    # ── Main loop ────────────────────────────────────────
    while True:
        try:
            now = get_bucharest_time()
            weekday = now.weekday()   # 0=Mon, 1=Tue, 2=Wed...
            today_str = now.strftime('%Y-%m-%d')

            # Verifică dacă suntem în fereastra de trigger (ziua + ora + minutul)
            is_scan_day = weekday in SCAN_DAYS
            is_scan_time = is_scan_trigger_window(now, scan_hour, scan_minute)
            already_scanned_today = (get_last_scan_date() == today_str)
            scan_busy = is_scan_in_progress()

            # ── Weekly Report: Vineri 23:59 EET ──────────────────────────────
            is_weekly_report_time = (
                weekday == WEEKLY_REPORT_DAY
                and now.hour == WEEKLY_REPORT_HOUR
                and now.minute == WEEKLY_REPORT_MINUTE
            )
            already_sent_weekly = (get_last_weekly_report_date() == today_str)
            if is_weekly_report_time and not already_sent_weekly:
                logger.info(f"[WEEKLY] Vineri 23:59 — trimit Weekly Report...")
                save_last_weekly_report_date(today_str)
                send_weekly_report()

            # ── V38: Daily CB rates refresh 08:00 EET ───────────────────────
            is_cb_rates_time = (
                now.hour == CB_RATES_REFRESH_HOUR
                and CB_RATES_REFRESH_MINUTE <= now.minute <= CB_RATES_REFRESH_MINUTE + 4
            )
            already_refreshed_cb = (get_last_cb_rates_refresh_date() == today_str)
            if is_cb_rates_time and not already_refreshed_cb:
                logger.info("[CB_RATES] 08:00 — refresh macro rates cache...")
                run_daily_cb_rates_refresh()

            if is_scan_day and is_scan_time and not already_scanned_today and not scan_busy:
                if acquire_scan_lock():
                    logger.info(f"[TRIGGER] {DAY_NAMES[weekday]} {now.strftime('%H:%M')} — SCAN START!")
                    try:
                        scan_ok = run_auto_scan()
                        if scan_ok:
                            save_last_scan_date(today_str)
                        else:
                            logger.warning(
                                "[TRIGGER] Scan failed — last_scan_date NOT saved; "
                                f"retry until {scan_hour:02d}:{SCAN_WINDOW_END_MINUTE:02d}"
                            )
                    finally:
                        release_scan_lock()

            else:
                # Log la fiecare 30 minute pentru vizibilitate în logs
                if now.minute % 30 == 0 and now.second < CHECK_INTERVAL:
                    next_scan_info = "azi" if (is_scan_day and not already_scanned_today) else "nu azi"
                    logger.debug(
                        f"[HEARTBEAT] {DAY_NAMES[weekday]} {now.strftime('%H:%M')} | "
                        f"scan_day={is_scan_day} | scan_time={is_scan_time} | "
                        f"scanned={already_scanned_today} | busy={scan_busy} | "
                        f"next={next_scan_info}"
                    )

        except Exception as e:
            logger.error(f"[LOOP ERROR] {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
