#!/usr/bin/env python3
"""
🛡️ WATCHDOG MONITOR V3.7
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✨ Glitch in Matrix by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money

System Guardian - Monitors and auto-restarts critical processes:
- setup_executor_monitor.py (Setup Scanner & Executor)
- position_monitor.py (Position & Profit Tracker)
- telegram_command_center.py (Command Center V3.7)

If any process dies → Instant restart (no manual intervention)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
                'last_restart': None
            },
            'position_monitor.py': {
                'name': 'Position Monitor',
                'command': [self.python_path, 'position_monitor.py'],
                'restart_count': 0,
                'last_restart': None
            },
            'telegram_command_center.py': {
                'name': 'Command Center',
                'command': [self.python_path, 'telegram_command_center.py'],
                'restart_count': 0,
                'last_restart': None
            }
        }
        
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        logger.info("🛡️ Watchdog Monitor V3.7 initialized")
        logger.info(f"⏱️  Check interval: {check_interval}s")
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
            
            branded_message = f"{message}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n✨ <b>Glitch in Matrix by ФорексГод</b> ✨\n🧠 AI-Powered • 💎 Smart Money"
            
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': branded_message,
                'parse_mode': 'HTML'
            }
            
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"❌ Telegram alert failed: {e}")
    
    def check_and_restart(self):
        """Check all processes and restart if needed"""
        for process_name, process_info in self.processes.items():
            if not self.is_process_running(process_name):
                logger.warning(f"⚠️ {process_info['name']} is DOWN!")
                
                # Attempt restart
                if self.start_process(process_name):
                    # Send Telegram alert
                    restart_count = process_info['restart_count']
                    alert = f"""🛡️ <b>WATCHDOG AUTO-RESTART</b>

⚠️ Process: <code>{process_info['name']}</code>
🔄 Status: <b>RESTARTED</b>
📊 Restart count: <code>{restart_count}</code>
⏰ Time: <code>{datetime.now().strftime('%H:%M:%S')}</code>

✅ System protection active"""
                    
                    self.send_telegram_alert(alert)
                else:
                    # Failed to restart - send critical alert
                    alert = f"""🚨 <b>WATCHDOG CRITICAL ALERT</b>

❌ Process: <code>{process_info['name']}</code>
🔴 Status: <b>FAILED TO RESTART</b>
⏰ Time: <code>{datetime.now().strftime('%H:%M:%S')}</code>

⚠️ Manual intervention required!"""
                    
                    self.send_telegram_alert(alert)
    
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
        logger.info("🛡️ WATCHDOG MONITOR - ARMED & PROTECTING")
        logger.info(f"⏱️  Check Interval: {self.check_interval}s")
        logger.info("="*60 + "\n")
        
        # Send startup notification
        startup_msg = f"""🛡️ <b>WATCHDOG ONLINE</b>

✅ System guardian activated
⏱️ Check interval: <code>{self.check_interval}s</code>

<b>Protected Processes:</b>
• Setup Monitor (30s interval)
• Position Monitor
• Command Center V3.7

🔒 Auto-restart enabled"""
        
        self.send_telegram_alert(startup_msg)
        
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
    
    parser = argparse.ArgumentParser(description='Watchdog Monitor V3.7')
    parser.add_argument('--interval', type=int, default=60,
                        help='Check interval in seconds (default: 60)')
    
    args = parser.parse_args()
    
    watchdog = WatchdogMonitor(check_interval=args.interval)
    watchdog.run()


if __name__ == "__main__":
    main()
