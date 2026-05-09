"""
⏰ AUTO SCANNER DAEMON - Glitch in Matrix V11.2
Rulează daily_scanner.py automat Luni/Miercuri/Vineri la 07:00 ora București

Logică:
  - Loop infinit, verifică ora la fiecare 60 secunde
  - Declanșează: reset_matrix.py → daily_scanner.py
  - Timezone: Europe/Bucharest (EEST = UTC+3, EET = UTC+2)
  - Anti-double-trigger: salvează data ultimului scan în data/last_auto_scan.json
  - Trimite notificare Telegram la start + finish
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

# ── Weekly Report: Vineri 23:59 EET (după închiderea pieței Forex) ──
WEEKLY_REPORT_HOUR = 23
WEEKLY_REPORT_MINUTE = 59
WEEKLY_REPORT_DAY = 4  # Friday

BASE_DIR = Path(__file__).parent
LAST_SCAN_FILE = BASE_DIR / "data" / "last_auto_scan.json"
LAST_WEEKLY_REPORT_FILE = BASE_DIR / "data" / "last_weekly_report.json"

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


def save_last_scan_date(scan_date: str):
    """Salvează data ultimului scan"""
    try:
        LAST_SCAN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LAST_SCAN_FILE, 'w') as f:
            json.dump({
                'last_scan_date': scan_date,
                'last_scan_timestamp': datetime.now().isoformat(),
                'updated_by': 'auto_scanner_daemon.py'
            }, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save last scan date: {e}")


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
        f"⏳ Scanul durează ~2-4 minute\n"
        f"{_sep}\n"
        f"🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
        f"{_sep}\n"
        f"🏛 <b>ГЛИТЧ ИН МАТРИКС</b> 🏛"
    )

    python = sys.executable
    scan_ok = False

    # ── Daily Scanner (SMCDetector — merge cu setups existente) ──────────────
    logger.info("[Step 1/1] Running daily_scanner.py (preserving existing setups)...")
    try:
        # ✅ V14.6 FIX: Force UTF-8 in child process so emoji prints don't crash
        # Windows cp1252 can't encode 📊 🔥 etc → UnicodeEncodeError in daily_scanner.py
        child_env = os.environ.copy()
        child_env['PYTHONIOENCODING'] = 'utf-8'
        child_env['PYTHONUTF8'] = '1'  # Python 3.7+ UTF-8 mode

        result = subprocess.run(
            [python, 'daily_scanner.py'],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding='utf-8',       # ✅ Windows fix: prevent cp1252 crash
            errors='replace',       # ✅ Replace undecodable chars instead of crashing
            timeout=300,            # 5 minute max
            env=child_env           # ✅ V14.6: UTF-8 mode for child process
        )
        if result.returncode == 0:
            logger.success("[Step 1/1] daily_scanner.py DONE")
            scan_ok = True
        else:
            logger.error(f"[Step 1/1] daily_scanner.py FAILED (code {result.returncode})")
            stderr_snippet = result.stderr.strip()[:1500] if result.stderr.strip() else ''
            stdout_snippet = result.stdout.strip()[-1500:] if result.stdout.strip() else ''
            if stderr_snippet:
                logger.error(f"STDERR:\n{stderr_snippet}")
            if stdout_snippet:
                logger.error(f"STDOUT (last 1500 chars):\n{stdout_snippet}")
            # ✅ Send error details to Telegram so user can diagnose from phone
            error_preview = stderr_snippet or stdout_snippet or 'No output captured'
            _sep = "────────────────"
            send_telegram(
                f"❌ <b>SCAN ERROR (code {result.returncode})</b>\n"
                f"{_sep}\n"
                f"<pre>{error_preview[:800]}</pre>"
            )
    except subprocess.TimeoutExpired:
        logger.error("[Step 1/1] daily_scanner.py TIMEOUT (300s)")
        send_telegram("⏰ <b>AUTO SCAN TIMEOUT</b>\ndaily_scanner.py a depasit 5 minute!")
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
            f"⚠️ Verifică auto_scanner.log pe VPS\n"
            f"🔧 Rulează manual: python daily_scanner.py\n"
            f"{_sep}\n"
            f"🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
            f"{_sep}\n"
            f"🏛 <b>ГЛИТЧ ИН МАТРИКС</b> 🏛"
        )

    return scan_ok


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


def send_weekly_report():
    """Construieste și trimite Weekly Report pe Telegram — rulat Vineri 23:59 EET"""
    import sqlite3

    now = get_bucharest_time()
    week_ago = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    week_start_label = (now - timedelta(days=7)).strftime('%d %b')
    week_end_label = now.strftime('%d %b %Y')

    _sep = "────────────────"
    total = wins = losses = 0
    total_pnl = 0.0
    best_trade = worst_trade = None

    # ── Sursa 1: trade_history.json ──
    trade_history_file = BASE_DIR / 'trade_history.json'
    sourced_from = None
    if trade_history_file.exists():
        try:
            with open(trade_history_file, 'r', encoding='utf-8') as f:
                th = json.load(f)
            for trade in th.get('closed_trades', []):
                ct = trade.get('close_time', '')
                if not ct or ct[:10] < week_ago:
                    continue
                profit = float(trade.get('profit', 0))
                total += 1
                total_pnl += profit
                if profit > 0:
                    wins += 1
                else:
                    losses += 1
                if best_trade is None or profit > best_trade:
                    best_trade = profit
                if worst_trade is None or profit < worst_trade:
                    worst_trade = profit
            sourced_from = 'trade_history.json'
        except Exception as e:
            logger.warning(f"[WeeklyReport] trade_history.json error: {e}")

    # ── Sursa 2: SQLite fallback ──
    if sourced_from is None:
        db_path = BASE_DIR / 'data' / 'trades.db'
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        COUNT(*),
                        SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END),
                        SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END),
                        SUM(profit),
                        MAX(profit),
                        MIN(profit)
                    FROM closed_trades
                    WHERE DATE(close_time, 'localtime') >= ?
                """, (week_ago,))
                row = cursor.fetchone()
                conn.close()
                if row and row[0]:
                    total = row[0] or 0
                    wins = row[1] or 0
                    losses = row[2] or 0
                    total_pnl = row[3] or 0.0
                    best_trade = row[4]
                    worst_trade = row[5]
                sourced_from = 'trades.db'
            except Exception as e:
                logger.warning(f"[WeeklyReport] SQLite error: {e}")

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
        level="DEBUG"
    )

    logger.info("")
    logger.info("=" * 60)
    logger.info("  AUTO SCANNER DAEMON - Glitch in Matrix V11.2")
    logger.info("=" * 60)
    logger.info(f"  Trigger: Luni / Miercuri / Vineri la {scan_hour:02d}:{scan_minute:02d} Bucuresti")
    logger.info(f"  Python:  {sys.executable}")
    logger.info(f"  Dir:     {BASE_DIR}")
    logger.info(f"  State:   {LAST_SCAN_FILE}")
    logger.info("=" * 60)
    logger.info("")

    # ── Run now mode (manual test) ───────────────────────
    if args.run_now:
        logger.warning("[--run-now] Manual trigger! Running scan immediately...")
        run_auto_scan()
        today_str = date.today().isoformat()
        save_last_scan_date(today_str)
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
            is_scan_time = (now.hour == scan_hour) and (now.minute == scan_minute)
            already_scanned_today = (get_last_scan_date() == today_str)

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

            if is_scan_day and is_scan_time and not already_scanned_today:
                logger.info(f"[TRIGGER] {DAY_NAMES[weekday]} {now.strftime('%H:%M')} — SCAN START!")
                save_last_scan_date(today_str)   # Salvează ÎNAINTE să ruleze (anti double-trigger)
                run_auto_scan()

            else:
                # Log la fiecare 30 minute pentru vizibilitate în logs
                if now.minute % 30 == 0 and now.second < CHECK_INTERVAL:
                    next_scan_info = "azi" if (is_scan_day and not already_scanned_today) else "nu azi"
                    logger.debug(
                        f"[HEARTBEAT] {DAY_NAMES[weekday]} {now.strftime('%H:%M')} | "
                        f"scan_day={is_scan_day} | scanned={already_scanned_today} | "
                        f"next={next_scan_info}"
                    )

        except Exception as e:
            logger.error(f"[LOOP ERROR] {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
