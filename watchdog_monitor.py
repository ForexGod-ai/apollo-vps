#!/usr/bin/env python3
"""
🛡️ WATCHDOG MONITOR V4.1 - 7 MONITORS (COMPLETE PROTECTION)
────────────────
🔱 AUTHORED BY ФорексГод 🔱
🏛️ Глитч Ин Матрикс 🏛️

System Guardian - Monitors and auto-restarts ALL critical processes:
- setup_executor_monitor.py (Setup Scanner & Executor)
- position_monitor.py (Position & Profit Tracker)
- telegram_command_center.py (Command Center V3.7)
- ctrader_sync_daemon.py (Broker Sync with --loop)
- news_calendar_monitor.py (Economic Calendar - V2.0 Always-On)
- news_reminder_engine.py (News Alert Engine)
[V4.1] REMOVED: realtime_monitor.py (ZOMBIE — superseded, no live callers)

🆕 V4.0 Features:
✅ 6 Monitors Protected (was 5 in V3.9)
✅ All monitors now run as daemons (Always-On architecture)
✅ State Tracking - Notifications only on state changes (stopped → running)
✅ Rate Limiter - Max 1 alert per process every 15 minutes (Anti-Spam)
✅ Aggregated Startup - Single boot message instead of 6 separate alerts

If any process dies → Instant restart (no manual intervention)
──────────────────
"""

# Windows VPS fix: force UTF-8 stdout to prevent UnicodeEncodeError on emoji
import sys as _sys, io as _io
if hasattr(_sys.stdout, 'buffer'):
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(_sys.stderr, 'buffer'):
    _sys.stderr = _io.TextIOWrapper(_sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import json
import subprocess
import time
import sys
import psutil
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
from dotenv import load_dotenv
import requests
try:
    import pytz
    _RO_TZ = pytz.timezone('Europe/Bucharest')
except ImportError:
    _RO_TZ = None

def now_ro() -> datetime:
    """Return current datetime in Romania timezone (UTC+2/UTC+3 DST)."""
    if _RO_TZ:
        return datetime.now(pytz.utc).astimezone(_RO_TZ)
    from datetime import timezone, timedelta
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=2)))

load_dotenv()

# ━━━ V8.0 VPS-READY: Force UTC timezone + persistent log file ━━━
os.environ['TZ'] = 'UTC'
try:
    time.tzset()
except AttributeError:
    pass

_LOG_DIR = Path(__file__).parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)
logger.add(
    str(_LOG_DIR / "watchdog_monitor.log"),
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
    level="DEBUG",
    rotation="10 MB",
    retention="7 days",
    compression="zip"
)


class WatchdogMonitor:
    """System guardian - monitors and restarts critical processes"""
    
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self.base_path = Path(__file__).parent
        self.python_path = sys.executable
        
        # Critical processes to monitor
        self.processes = {
            'setup_executor_monitor.py': {
                'name': 'Setup Monitor',
                'command': [self.python_path, 'setup_executor_monitor.py', '--interval', '30', '--loop'],
                'restart_count': 0,
                'last_restart': None,
                'state': 'unknown',  # 🔥 NEW: Track state (unknown/running/stopped)
                'last_notification': 0  # 🔥 NEW: Last notification timestamp (rate limiter)
            },
            'position_monitor.py': {
                'name': 'Position Monitor',
                'command': [self.python_path, 'position_monitor.py'],
                'restart_count': 0,
                'last_restart': None,
                'state': 'unknown',  # 🔥 NEW: Track state
                'last_notification': 0  # 🔥 NEW: Rate limiter
            },
            'telegram_command_center.py': {
                'name': 'Command Center',
                'command': [self.python_path, 'telegram_command_center.py'],
                'restart_count': 0,
                'last_restart': None,
                'state': 'unknown',  # 🔥 NEW: Track state
                'last_notification': 0  # 🔥 NEW: Rate limiter
            },
            # [V4.1] realtime_monitor.py REMOVED — zombie process, superseded
            'ctrader_sync_daemon.py': {
                'name': 'cTrader Sync',
                'command': [self.python_path, 'ctrader_sync_daemon.py', '--loop'],
                'restart_count': 0,
                'last_restart': None,
                'state': 'unknown',  # 🔥 NEW: Track state
                'last_notification': 0  # 🔥 NEW: Rate limiter
            },
            'news_calendar_monitor.py': {
                'name': 'News Calendar',
                'command': [self.python_path, 'news_calendar_monitor.py'],
                'restart_count': 0,
                'last_restart': None,
                'state': 'unknown',  # 🔥 NEW: Track state
                'last_notification': 0  # 🔥 NEW: Rate limiter
            },
            'news_reminder_engine.py': {
                'name': 'News Reminder',
                'command': [self.python_path, 'news_reminder_engine.py'],
                'restart_count': 0,
                'last_restart': None,
                'state': 'unknown',
                'last_notification': 0
            },
            'auto_scanner_daemon.py': {
                'name': 'Auto Scanner',
                'command': [self.python_path, 'auto_scanner_daemon.py'],
                'restart_count': 0,
                'last_restart': None,
                'state': 'unknown',
                'last_notification': 0
            },
            'dashboard_server.py': {
                'name': 'Dashboard Server',
                'command': [self.python_path, 'dashboard_server.py'],
                'restart_count': 0,
                'last_restart': None,
                'state': 'unknown',
                'last_notification': 0
            }
        }
        
        # 🔥 NEW: Rate Limiter Configuration (Anti-Spam)
        self.notification_cooldown = 900        # 15 minutes — restart OK alerts
        self.failed_restart_cooldown = 3600     # 60 minutes — FAILED TO RESTART (anti-spam)
        self._failed_restart_last_sent = {}     # {process_name: timestamp}
        
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        logger.info("🛡️ Watchdog Monitor V4.2 - 9 MONITORS (+ Auto Scanner Mon/Wed/Fri + Dashboard)")
        logger.info(f"⏱️  Check interval: {check_interval}s")
        logger.info(f"🔇 Notification cooldown: {self.notification_cooldown}s (15 min) | FAILED: {self.failed_restart_cooldown}s (60 min)")
        logger.info(f"🐍 Python: {self.python_path}")
    
    def is_process_running(self, process_name: str) -> bool:
        """
        🔍 Check if process is running using psutil (accurate PID + cmdline verification)
        Returns True only if process exists AND matches the script name
        """
        try:
            # Iterate through all running Python processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    # Check if it's a Python process
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        cmdline = proc.info['cmdline']
                        if cmdline:
                            # Check if our script is in the command line
                            cmdline_str = ' '.join(cmdline)
                            if process_name in cmdline_str and 'watchdog' not in cmdline_str:
                                logger.debug(f"✅ Found running: {process_name} (PID {proc.info['pid']})")
                                return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            logger.debug(f"❌ Not running: {process_name}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking process {process_name}: {e}")
            # Fallback to False to trigger restart attempt
            return False
    
    def start_process(self, process_name: str) -> bool:
        """Start a process"""
        try:
            process_info = self.processes[process_name]
            command = process_info['command']
            
            logger.info(f"🚀 Starting {process_info['name']}...")
            
            # V8.0 VPS-READY: Redirect stdout/stderr to log files (NOT DEVNULL!)
            # Critical for forensics: if a process crashes, we have the output
            log_dir = self.base_path / "logs"
            log_dir.mkdir(exist_ok=True)
            process_stem = process_name.replace('.py', '')
            stdout_log = open(log_dir / f"{process_stem}_stdout.log", 'a')
            stderr_log = open(log_dir / f"{process_stem}_stderr.log", 'a')
            
            # Windows-compatible process spawning
            import platform
            if platform.system() == 'Windows':
                import ctypes
                CREATE_NEW_PROCESS_GROUP = 0x00000200
                DETACHED_PROCESS = 0x00000008
                subprocess.Popen(
                    command,
                    cwd=self.base_path,
                    stdout=stdout_log,
                    stderr=stderr_log,
                    creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
                )
            else:
                subprocess.Popen(
                    command,
                    cwd=self.base_path,
                    stdout=stdout_log,
                    stderr=stderr_log,
                    start_new_session=True
                )
            
            time.sleep(2)  # Wait for process to start
            
            # Verify it started
            if self.is_process_running(process_name):
                process_info['restart_count'] += 1
                process_info['last_restart'] = datetime.now()
                logger.success(f"✅ {process_info['name']} started successfully!")
                return True
            else:
                logger.error(f"❌ {process_info['name']} failed to start")
                return False
        
        except Exception as e:
            logger.error(f"❌ Error starting {process_name}: {e}")
            return False
    
    def send_telegram_alert(self, message: str):
        """Send alert to Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            
            # ═══ V10.4 SOVEREIGN SIGNATURE — 16-Line Symmetry ═══
            sep = "────────────────"  # 16 chars
            branded_message = (
                f"{message}\n\n"
                f"  {sep}\n"
                f"  🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
                f"  {sep}\n"
                f"  🏛️  <b>Глитч Ин Матрикс</b>  🏛️"
            )
            
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': branded_message,
                'parse_mode': 'HTML'
            }
            
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"❌ Telegram alert failed: {e}")
    
    def can_send_notification(self, process_name: str) -> bool:
        """
        🔇 RATE LIMITER (Anti-Spam)
        Check if enough time has passed since last notification for this process
        Returns True only if cooldown period (15 min) has elapsed
        """
        process_info = self.processes[process_name]
        current_time = time.time()
        time_since_last = current_time - process_info['last_notification']
        
        if time_since_last < self.notification_cooldown:
            minutes_remaining = (self.notification_cooldown - time_since_last) / 60
            logger.debug(f"🔇 Rate limiter: Skipping notification for {process_info['name']} "
                        f"(cooldown active, {minutes_remaining:.1f} min remaining)")
            return False
        
        return True
    
    def update_notification_time(self, process_name: str):
        """Update last notification timestamp"""
        self.processes[process_name]['last_notification'] = time.time()
    
    def check_and_restart(self):
        """
        🔍 STATE TRACKING (Smart Notifications)
        Check all processes and restart if needed.
        Send notification ONLY when state changes (stopped → running)
        """
        for process_name, process_info in self.processes.items():
            is_running = self.is_process_running(process_name)
            old_state = process_info['state']
            new_state = 'running' if is_running else 'stopped'
            
            # 🔥 STATE CHANGE DETECTION
            state_changed = (old_state != new_state)
            
            # Update state
            process_info['state'] = new_state
            
            # If process is down → Attempt restart
            if not is_running:
                if state_changed:
                    logger.warning(f"⚠️ {process_info['name']} is DOWN! (state: {old_state} → {new_state})")
                
                # Attempt restart
                if self.start_process(process_name):
                    process_info['state'] = 'running'  # Update state after successful restart
                    
                    # 🔥 SEND NOTIFICATION ONLY IF:
                    # 1. State changed (stopped → running)
                    # 2. Cooldown period elapsed (15 min since last notification)
                    if state_changed and self.can_send_notification(process_name):
                        restart_count = process_info['restart_count']
                        alert = f"""🛡️ <b>WATCHDOG AUTO-RESTART</b>

⚠️ Process: <code>{process_info['name']}</code>
🔄 Status: <b>RESTARTED</b>
📊 Restart count: <code>{restart_count}</code>
⏰ Time: <code>{now_ro().strftime('%H:%M:%S')} RO</code>

✅ System protection active"""
                        
                        self.send_telegram_alert(alert)
                        self.update_notification_time(process_name)
                        logger.info(f"📱 Sent restart notification for {process_info['name']}")
                    else:
                        logger.debug(f"🔇 Restart notification skipped for {process_info['name']} (rate limiter)")
                else:
                    # Failed to restart — cooldown 60 min (anti-spam)
                    import time as _time
                    last_sent = self._failed_restart_last_sent.get(process_name, 0)
                    if _time.time() - last_sent >= self.failed_restart_cooldown:
                        alert = f"""🚨 <b>WATCHDOG CRITICAL ALERT</b>

❌ Process: <code>{process_info['name']}</code>
🔴 Status: <b>FAILED TO RESTART</b>
⏰ Time: <code>{now_ro().strftime('%H:%M:%S')} RO</code>

⚠️ Manual intervention required!"""
                        
                        self.send_telegram_alert(alert)
                        self._failed_restart_last_sent[process_name] = _time.time()
                        logger.error(f"📱 Sent critical alert for {process_info['name']} (next in 60 min)")
                    else:
                        remaining = int((self.failed_restart_cooldown - (_time.time() - last_sent)) / 60)
                        logger.warning(f"🔇 Critical alert suppressed for {process_info['name']} ({remaining} min until next alert)")
    
    def get_status_report(self) -> dict:
        """Get status of all monitored processes"""
        status = {}
        for process_name, process_info in self.processes.items():
            is_running = self.is_process_running(process_name)
            status[process_name] = {
                'name': process_info['name'],
                'running': is_running,
                'restart_count': process_info['restart_count'],
                'last_restart': process_info['last_restart'].isoformat() if process_info['last_restart'] else None
            }
        return status
    
    def _check_deep_sleep_reminder(self):
        """
        V10.6 PERSISTENT WARNING:
        If deep_sleep_state.json exists, send a Telegram reminder every 4 hours.
        """
        sleep_file = self.base_path / 'data' / 'deep_sleep_state.json'
        if not sleep_file.exists():
            self._last_sleep_reminder = 0  # reset so next sleep gets immediate alert
            return

        now = datetime.now()
        last_sent = getattr(self, '_last_sleep_reminder', 0)
        elapsed_hours = (time.time() - last_sent) / 3600

        if elapsed_hours < 4:
            return  # still within cooldown

        try:
            with open(sleep_file, 'r') as f:
                state = json.load(f)
            wake_str = state.get('wake_time', '')
            reason = state.get('reason', 'Unknown')
            wake_display = wake_str[:16] if wake_str else '?'

            msg = (
                f"🚨 <b>SYSTEM ACTIVE BUT TRADING IS LOCKED</b>\n\n"
                f"🛌 Status: <b>DEEP SLEEP / LOCKDOWN</b>\n"
                f"📝 Reason: <i>{reason}</i>\n"
                f"⏰ Wake: <code>{wake_display} UTC</code>\n\n"
                f"⚠️ No trades will be opened until sleep expires\n"
                f"or you send <code>/resume</code> to unlock manually.\n\n"
                f"🔄 Next reminder in <b>4 hours</b>"
            )
            self.send_telegram_alert(msg)
            self._last_sleep_reminder = time.time()
            logger.warning("🚨 Deep sleep reminder sent")
        except Exception as e:
            logger.error(f"❌ Deep sleep reminder error: {e}")

    def _check_midnight_auto_resume(self):
        """
        V10.6 AUTO-RESUME AUDIT:
        At 00:05 UTC, check if deep_sleep_state.json has expired.
        If wake_time has passed, delete the file and send SYSTEM AWAKENED.
        """
        now_utc = datetime.utcnow()
        # Only run in the 00:05–00:06 UTC window
        if not (now_utc.hour == 0 and now_utc.minute == 5):
            return
        # Deduplicate — only once per day
        today = now_utc.date().isoformat()
        if getattr(self, '_last_midnight_resume_date', '') == today:
            return

        sleep_file = self.base_path / 'data' / 'deep_sleep_state.json'
        if not sleep_file.exists():
            return

        try:
            with open(sleep_file, 'r') as f:
                state = json.load(f)
            wake_str = state.get('wake_time', '')
            lockdown = state.get('lockdown', False)
            if lockdown:
                # Manual /killall lockdown — do NOT auto-resume, just warn
                msg = (
                    f"⚠️ <b>00:05 UTC — MANUAL LOCKDOWN STILL ACTIVE</b>\n\n"
                    f"🛌 System remains in LOCKDOWN (triggered by /killall)\n"
                    f"🔑 Send <code>/resume</code> to unlock trading manually."
                )
                self.send_telegram_alert(msg)
                self._last_midnight_resume_date = today
                return

            # Auto-expire: check if wake_time has passed
            if wake_str:
                from datetime import timezone
                wake_dt = datetime.fromisoformat(wake_str.replace('Z', '+00:00'))
                now_aware = datetime.now(timezone.utc)
                if now_aware >= wake_dt or True:  # at 00:05 we always reset daily state
                    sleep_file.unlink()
                    msg = (
                        f"🔱 <b>SYSTEM AWAKENED</b>\n\n"
                        f"✅ Daily reset at 00:05 UTC\n"
                        f"🔄 <b>BIAS SYNC STARTING...</b>\n"
                        f"📊 Daily loss counter: <b>RESET</b>\n"
                        f"⏰ Time: <code>{now_utc.strftime('%Y-%m-%d 00:05 UTC')}</code>\n\n"
                        f"⚠️ Scanner will re-evaluate all pairs on next 4H candle close."
                    )
                    self.send_telegram_alert(msg)
                    logger.info("🔱 Midnight auto-resume: deep sleep cleared at 00:05 UTC")
            self._last_midnight_resume_date = today
        except Exception as e:
            logger.error(f"❌ Midnight auto-resume error: {e}")

    def run(self):
        """Main monitoring loop"""
        logger.info("\n" + "="*60)
        logger.info("🛡️ WATCHDOG MONITOR V4.1 - ARMED & PROTECTING")
        logger.info(f"⏱️  Check Interval: {self.check_interval}s")
        logger.info(f"🔇 Anti-Spam: restart OK → 15 min | FAILED TO RESTART → 60 min")
        logger.info(f"📊 Monitoring: {len(self.processes)} processes")
        logger.info("="*60 + "\n")
        # V10.6: init persistent-reminder state
        self._last_sleep_reminder = 0
        self._last_midnight_resume_date = ''
        
        # 🔥 INITIAL STATE CHECK (before sending startup message)
        # Detect which monitors are already running
        initial_status = []
        for process_name, process_info in self.processes.items():
            is_running = self.is_process_running(process_name)
            process_info['state'] = 'running' if is_running else 'stopped'
            
            if is_running:
                initial_status.append(f"✅ {process_info['name']}")
                logger.info(f"   ✅ {process_info['name']}: Already running")
            else:
                initial_status.append(f"⏳ {process_info['name']}")
                logger.info(f"   ⏳ {process_info['name']}: Will start on first check")
        
        # 🔥 AGGREGATED STARTUP MESSAGE (Single notification)
        running_count = sum(1 for p in self.processes.values() if p['state'] == 'running')
        total_count = len(self.processes)
        
        startup_msg = f"""🛡️ <b>WATCHDOG V4.0 ONLINE</b>

✅ System guardian activated
⏱️ Check interval: <code>{self.check_interval}s</code>
🔇 Anti-Spam: restart OK → 15 min
↳ FAILED → 60 min
📊 Monitoring: <b>{total_count} processes</b>

<b>Initial Status ({running_count}/{total_count} running):</b>
{chr(10).join(initial_status)}

🔒 Auto-restart enabled
📊 State tracking active"""
        
        self.send_telegram_alert(startup_msg)
        logger.info("📱 Sent aggregated startup notification")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                logger.debug(f"\n🔍 Watchdog Check #{iteration} - {datetime.now().strftime('%H:%M:%S')}")
                
                self.check_and_restart()

                # V10.6: Persistent deep sleep reminder (every 4h)
                self._check_deep_sleep_reminder()

                # V10.6: Midnight auto-resume at 00:05 UTC
                self._check_midnight_auto_resume()

                # ✅ V10.9 NEWS HEARTBEAT: Log news monitor status every 5 checks
                if iteration % 5 == 0:
                    news_running = self.is_process_running('news_calendar_monitor.py')
                    news_status = "✅ ONLINE" if news_running else "❌ OFFLINE"
                    news_log = self.base_path / "logs" / "news_calendar.log"
                    last_activity = "N/A"
                    if news_log.exists():
                        import os as _os
                        age_sec = time.time() - _os.path.getmtime(str(news_log))
                        age_h = age_sec / 3600
                        last_activity = f"{age_h:.1f}h ago"
                    logger.info(
                        f"📰 NEWS HEARTBEAT | status={news_status} | "
                        f"last_log={last_activity} | "
                        f"restarts={self.processes['news_calendar_monitor.py']['restart_count']} | "
                        f"check=#{iteration}"
                    )

                # Log status every 10 checks
                if iteration % 10 == 0:
                    status = self.get_status_report()
                    logger.info(f"📊 Status Report (Check #{iteration}):")
                    for process_name, info in status.items():
                        status_emoji = "✅" if info['running'] else "❌"
                        logger.info(f"   {status_emoji} {info['name']}: {'ONLINE' if info['running'] else 'OFFLINE'}")
                
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            logger.info("\n⚠️ Watchdog shutting down...")
            shutdown_msg = "🛡️ <b>WATCHDOG SHUTDOWN</b>\n\n⚠️ System guardian stopped"
            self.send_telegram_alert(shutdown_msg)
            sys.exit(0)
        except Exception as e:
            logger.error(f"❌ Fatal error in watchdog: {e}")
            sys.exit(1)


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Watchdog Monitor V4.0 - 6 Monitors (Complete Protection)')
    parser.add_argument('--interval', type=int, default=60,
                        help='Check interval in seconds (default: 60)')
    parser.add_argument('--live', action='store_true',
                        help='Live account mode (passed through to child processes)')
    
    args = parser.parse_args()
    
    watchdog = WatchdogMonitor(check_interval=args.interval)
    watchdog.run()


if __name__ == "__main__":
    main()
