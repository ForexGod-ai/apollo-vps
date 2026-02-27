#!/usr/bin/env python3
"""
🛡️ WATCHDOG MONITOR V4.0 - 6 MONITORS (COMPLETE PROTECTION)
──────────────────
✨ Glitch in Matrix by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money

System Guardian - Monitors and auto-restarts ALL critical processes:
- setup_executor_monitor.py (Setup Scanner & Executor)
- position_monitor.py (Position & Profit Tracker)
- telegram_command_center.py (Command Center V3.7)
- realtime_monitor.py (4H Candle Analysis)
- ctrader_sync_daemon.py (Broker Sync with --loop)
- news_calendar_monitor.py (Economic Calendar - V2.0 Always-On) 🆕

🆕 V4.0 Features:
✅ 6 Monitors Protected (was 5 in V3.9)
✅ All monitors now run as daemons (Always-On architecture)
✅ State Tracking - Notifications only on state changes (stopped → running)
✅ Rate Limiter - Max 1 alert per process every 15 minutes (Anti-Spam)
✅ Aggregated Startup - Single boot message instead of 6 separate alerts

If any process dies → Instant restart (no manual intervention)
──────────────────
"""

import os
import subprocess
import time
import sys
import psutil
from pathlib import Path
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv
import requests

load_dotenv()


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
            'realtime_monitor.py': {
                'name': 'Realtime Monitor',
                'command': [self.python_path, 'realtime_monitor.py'],
                'restart_count': 0,
                'last_restart': None,
                'state': 'unknown',  # 🔥 NEW: Track state
                'last_notification': 0  # 🔥 NEW: Rate limiter
            },
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
                'command': [self.python_path, 'news_calendar_monitor.py', '--interval', '24'],
                'restart_count': 0,
                'last_restart': None,
                'state': 'unknown',  # 🔥 NEW: Track state
                'last_notification': 0  # 🔥 NEW: Rate limiter
            }
        }
        
        # 🔥 NEW: Rate Limiter Configuration (Anti-Spam)
        self.notification_cooldown = 900  # 15 minutes (900 seconds)
        
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        logger.info("🛡️ Watchdog Monitor V4.0 - 6 MONITORS (COMPLETE PROTECTION)")
        logger.info(f"⏱️  Check interval: {check_interval}s")
        logger.info(f"🔇 Notification cooldown: {self.notification_cooldown}s (15 min)")
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
            
            # Start process in background
            subprocess.Popen(
                command,
                cwd=self.base_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
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
            
            branded_message = f"{message}\n\n──────────────────\n✨ <b>Glitch in Matrix by ФорексГод</b> ✨\n🧠 AI-Powered • 💎 Smart Money"
            
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
⏰ Time: <code>{datetime.now().strftime('%H:%M:%S')}</code>

✅ System protection active"""
                        
                        self.send_telegram_alert(alert)
                        self.update_notification_time(process_name)
                        logger.info(f"📱 Sent restart notification for {process_info['name']}")
                    else:
                        logger.debug(f"🔇 Restart notification skipped for {process_info['name']} (rate limiter)")
                else:
                    # Failed to restart - send critical alert (always send, ignore cooldown)
                    alert = f"""🚨 <b>WATCHDOG CRITICAL ALERT</b>

❌ Process: <code>{process_info['name']}</code>
🔴 Status: <b>FAILED TO RESTART</b>
⏰ Time: <code>{datetime.now().strftime('%H:%M:%S')}</code>

⚠️ Manual intervention required!"""
                    
                    self.send_telegram_alert(alert)
                    self.update_notification_time(process_name)
                    logger.error(f"📱 Sent critical alert for {process_info['name']}")
    
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
    
    def run(self):
        """Main monitoring loop"""
        logger.info("\n" + "="*60)
        logger.info("🛡️ WATCHDOG MONITOR V4.0 - ARMED & PROTECTING")
        logger.info(f"⏱️  Check Interval: {self.check_interval}s")
        logger.info(f"🔇 Anti-Spam: 15 min cooldown per alert")
        logger.info(f"📊 Monitoring: {len(self.processes)} processes")
        logger.info("="*60 + "\n")
        
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
🔇 Anti-Spam: 15 min cooldown
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
    
    args = parser.parse_args()
    
    watchdog = WatchdogMonitor(check_interval=args.interval)
    watchdog.run()


if __name__ == "__main__":
    main()
