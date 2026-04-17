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
from datetime import datetime, date
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ━━━ CONFIG ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCAN_HOUR = 7           # 07:00 ora București
SCAN_MINUTE = 0         # :00
SCAN_DAYS = {0, 2, 4}  # Monday=0, Wednesday=2, Friday=4
CHECK_INTERVAL = 60     # Verifică la fiecare 60 secunde

BASE_DIR = Path(__file__).parent
LAST_SCAN_FILE = BASE_DIR / "data" / "last_auto_scan.json"

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

DAY_NAMES = {0: "Luni", 1: "Marți", 2: "Miercuri", 3: "Joi", 4: "Vineri", 5: "Sâmbătă", 6: "Duminică"}


# ━━━ TIMEZONE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_bucharest_time() -> datetime:
    """
    Returnează ora curentă în Europa/București.
    VPS-ul este setat cu timezone București — folosim ora locală direct.
    """
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

    send_telegram(
        f"⏰ <b>AUTO SCAN PORNIT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 {day_name}, {timestamp}\n"
        f"🔄 Scanez piețele... (fara reset — setup-urile vechi sunt pastrate)\n"
        f"⏳ Scanul dureaza ~2-4 minute"
    )

    python = sys.executable
    scan_ok = False

    # ── Daily Scanner (SMCDetector — merge cu setups existente) ──────────────
    logger.info("[Step 1/1] Running daily_scanner.py (preserving existing setups)...")
    try:
        result = subprocess.run(
            [python, 'daily_scanner.py'],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute max
        )
        if result.returncode == 0:
            logger.success("[Step 1/1] daily_scanner.py DONE")
            scan_ok = True
        else:
            logger.error(f"[Step 1/1] daily_scanner.py FAILED (code {result.returncode})")
            logger.error(f"STDERR: {result.stderr[:400]}")
    except subprocess.TimeoutExpired:
        logger.error("[Step 1/1] daily_scanner.py TIMEOUT (300s)")
    except Exception as e:
        logger.error(f"[Step 1/1] daily_scanner.py ERROR: {e}")

    # ── Finish notification ──────────────────────────────
    finish_time = get_bucharest_time().strftime('%H:%M:%S')
    if scan_ok:
        logger.success(f"[AUTO SCAN] COMPLETED successfully at {finish_time}")
        send_telegram(
            f"✅ <b>AUTO SCAN COMPLET</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 {day_name} — Ora: {finish_time}\n"
            f"📊 Urmatorul scan: vezi /status\n"
            f"💡 Foloseste /monitoring pentru setups noi"
        )
    else:
        logger.error(f"[AUTO SCAN] FAILED at {finish_time}")
        send_telegram(
            f"❌ <b>AUTO SCAN ESUAT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 {day_name} — Ora: {finish_time}\n"
            f"⚠️ Verifica auto_scanner.log pe VPS\n"
            f"🔧 Ruleaza manual: python daily_scanner.py"
        )

    return scan_ok


# ━━━ MAIN LOOP ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    parser = argparse.ArgumentParser(description='Auto Scanner Daemon - Mon/Wed/Fri 07:00 Bucharest')
    parser.add_argument('--scan-hour', type=int, default=SCAN_HOUR, help='Ora scanului (default: 7)')
    parser.add_argument('--scan-minute', type=int, default=SCAN_MINUTE, help='Minutul scanului (default: 0)')
    parser.add_argument('--run-now', action='store_true', help='Ruleaza scanul imediat (test mode)')
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

    # ── Startup Telegram notification ───────────────────
    next_days = [DAY_NAMES[d] for d in sorted(SCAN_DAYS)]
    send_telegram(
        f"⏰ <b>AUTO SCANNER DAEMON ONLINE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Scan: {', '.join(next_days)} la {scan_hour:02d}:{scan_minute:02d}\n"
        f"🕐 Ora sistem: {get_bucharest_time().strftime('%H:%M:%S')}\n"
        f"✅ Watchdog il protejeaza automat"
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
