#!/usr/bin/env python3
"""
Service Watchdog - Glitch In Matrix v3.2
Monitors critical services and restarts them if down
Sends Telegram alerts on failures and recoveries
"""
import subprocess
import time
import os
from pathlib import Path
from datetime import datetime
from loguru import logger

# Import notification manager
from notification_manager import NotificationManager

# Critical services to monitor
CRITICAL_SERVICES = {
    'ctrader_sync_daemon.py': {
        'name': 'cTrader Sync Daemon',
        'priority': 'CRITICAL',
        'start_cmd': ['python3', 'ctrader_sync_daemon.py', '--loop'],
        'description': 'Syncs account data from cTrader API every 30s'
    },
    'position_monitor.py': {
        'name': 'Position Monitor',
        'priority': 'CRITICAL',
        'start_cmd': ['python3', 'position_monitor.py', '--loop'],
        'description': 'Monitors closed trades and sends notifications'
    },
    'setup_executor_monitor.py': {
        'name': 'Setup Executor',
        'priority': 'IMPORTANT',
        'start_cmd': ['python3', 'setup_executor_monitor.py', '--loop', '--interval', '30'],
        'description': 'Monitors setups and executes entries on pullbacks'
    }
}

class ServiceWatchdog:
    def __init__(self):
        self.project_dir = Path(__file__).parent
        self.telegram = NotificationManager()
        self.restart_counts = {}
        self.last_alert_time = {}  # Prevent alert spam
        
        # Configure logging
        log_file = self.project_dir / "logs" / "watchdog.log"
        log_file.parent.mkdir(exist_ok=True)
        
        logger.add(
            log_file,
            rotation="1 day",
            retention="30 days",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
        )
    
    def is_service_running(self, service_name):
        """Check if service process is running"""
        try:
            result = subprocess.run(
                ['pgrep', '-f', service_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.warning(f"⚠️  Timeout checking {service_name}")
            return False
        except Exception as e:
            logger.error(f"❌ Error checking {service_name}: {e}")
            return False
    
    def kill_old_process(self, service_name):
        """Kill old process safely"""
        try:
            subprocess.run(
                ['pkill', '-f', service_name],
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            return True
        except Exception as e:
            logger.warning(f"⚠️  Could not kill {service_name}: {e}")
            return False
    
    def start_service(self, service_name, config):
        """Start a service"""
        try:
            # Kill old process if exists (safety measure)
            self.kill_old_process(service_name)
            time.sleep(2)
            
            # Prepare log file
            log_file = self.project_dir / f"logs/{service_name.replace('.py', '.log')}"
            
            # Start new process
            with open(log_file, 'a') as f:
                subprocess.Popen(
                    config['start_cmd'],
                    cwd=self.project_dir,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    start_new_session=True  # Detach from parent
                )
            
            logger.success(f"✅ Started {config['name']}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Failed to start {config['name']}: {e}")
            return False
    
    def should_send_alert(self, service_name, alert_type='down'):
        """Check if we should send alert (prevent spam)"""
        key = f"{service_name}_{alert_type}"
        now = time.time()
        
        # Send alert max once every 5 minutes for same service+type
        if key in self.last_alert_time:
            if now - self.last_alert_time[key] < 300:  # 5 minutes
                return False
        
        self.last_alert_time[key] = now
        return True
    
    def check_and_restart(self, service_name, config):
        """Check if service is running, restart if down"""
        if not self.is_service_running(service_name):
            # Service is DOWN
            self.restart_counts[service_name] = self.restart_counts.get(service_name, 0) + 1
            
            priority_emoji = "🔴" if config['priority'] == 'CRITICAL' else "🟡"
            
            logger.warning(
                f"{priority_emoji} {config['name']} is DOWN! "
                f"Attempting restart #{self.restart_counts[service_name]}..."
            )
            
            # Send Telegram alert (if not spam)
            if self.should_send_alert(service_name, 'down'):
                try:
                    self.telegram.send_telegram_alert(
                        f"{priority_emoji} 🚨 GLITCH DETECTAT! 🚨\n\n"
                        f"💥 Serviciu căzut: {config['name']}\n"
                        f"⚠️ Prioritate: {config['priority']}\n"
                        f"🔧 Funcție: {config['description']}\n"
                        f"🔄 Tentativă restart: #{self.restart_counts[service_name]}\n"
                        f"⏱️ Timp: {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"🔧 Repar matriz... stand by!"
                    )
                except Exception as e:
                    logger.error(f"Failed to send Telegram alert: {e}")
            
            # Restart service
            if self.start_service(service_name, config):
                time.sleep(5)
                
                # Verify it started
                if self.is_service_running(service_name):
                    logger.success(f"✅ {config['name']} restarted successfully")
                    
                    # Send success notification
                    if self.should_send_alert(service_name, 'restored'):
                        try:
                            self.telegram.send_telegram_alert(
                                f"✅ 🎉 GLITCH REZOLVAT! 🎉\n\n"
                                f"🚀 Serviciu: {config['name']}\n"
                                f"✅ Status: ONLINE și funcțional\n"
                                f"⏱️ Restaurat la: {datetime.now().strftime('%H:%M:%S')}\n\n"
                                f"👍 Matriz reparată - back to making money! 💰"
                            )
                        except Exception as e:
                            logger.error(f"Failed to send success notification: {e}")
                else:
                    logger.error(f"❌ {config['name']} failed to start!")
                    
                    # Send critical failure alert
                    if self.should_send_alert(service_name, 'failed'):
                        try:
                            self.telegram.send_telegram_alert(
                                f"🚨 ☠️ CRITICAL GLITCH! ☠️\n\n"
                                f"🔥 Serviciu: {config['name']}\n"
                                f"⚠️ Prioritate: {config['priority']}\n"
                                f"❌ Status: RESTART EȘUAT!\n"
                                f"⏱️ Timp: {datetime.now().strftime('%H:%M:%S')}\n\n"
                                f"👨‍🔧 INTERVENȚIE MANUALĂ NECESARĂ!\n"
                                f"📞 Suna pe Neo - avem problemă!"
                            )
                        except Exception as e:
                            logger.error(f"Failed to send failure alert: {e}")
        else:
            # Service is running - reset restart counter
            if service_name in self.restart_counts and self.restart_counts[service_name] > 0:
                logger.info(f"✅ {config['name']} is healthy (was previously down)")
                self.restart_counts[service_name] = 0
    
    def get_all_services_status(self):
        """Get status of all monitored services"""
        status = {}
        for service_name, config in CRITICAL_SERVICES.items():
            status[service_name] = {
                'running': self.is_service_running(service_name),
                'name': config['name'],
                'priority': config['priority']
            }
        return status
    
    def send_startup_report(self):
        """Send initial status report on watchdog startup"""
        status = self.get_all_services_status()
        
        all_running = all(s['running'] for s in status.values())
        
        message = "🔍 🤖 SERVICE WATCHDOG ONLINE 🤖\n\n"
        message += f"⏰ Pornit la: {datetime.now().strftime('%H:%M:%S')}\n"
        message += f"🔄 Verific la fiecare: 60 secunde\n\n"
        message += "📋 Servicii monitorizate:\n"
        
        for service_name, info in status.items():
            emoji = "✅" if info['running'] else "❌"
            status_text = "ONLINE" if info['running'] else "🔴 DOWN"
            message += f"{emoji} {info['name']}: {status_text}\n"
        
        if all_running:
            message += "\n🎯 Toate sistemele funcționează perfect!\n"
            message += "💪 Gata de bătaie cu piața! Let's make money! 💸"
        else:
            message += "\n⚠️ Unele servicii au nevoie de atenție!\n"
            message += "🔧 Repar glitch-urile automat..."
        
        try:
            self.telegram.send_telegram_alert(message)
        except Exception as e:
            logger.error(f"Failed to send startup report: {e}")
    
    def monitor_loop(self, interval=60):
        """Main monitoring loop"""
        logger.info("🔍 Service Watchdog starting...")
        logger.info(f"Monitoring {len(CRITICAL_SERVICES)} critical services")
        logger.info(f"Check interval: {interval} seconds")
        
        # Send startup report
        self.send_startup_report()
        
        try:
            check_count = 0
            while True:
                check_count += 1
                logger.info(f"🔍 Check #{check_count} - Scanning services...")
                
                for service_name, config in CRITICAL_SERVICES.items():
                    self.check_and_restart(service_name, config)
                
                logger.info(f"✅ Check #{check_count} complete - Next check in {interval}s")
                time.sleep(interval)
        
        except KeyboardInterrupt:
            logger.info("⏹️  Watchdog stopped by user")
            try:
                self.telegram.send_telegram_alert(
                    "⏹️ <b>WATCHDOG OPRIT</b> 🚫\n\n"
                    f"⏱️ <b>Oprit la:</b> {datetime.now().strftime('%H:%M:%S')}\n"
                    f"👋 <b>Motiv:</b> Oprit manual (Ctrl+C)\n\n"
                    f"⚠️ Serviciile nu mai sunt monitorizate!\n"
                    f"🔄 Repornim watchdog-ul când e nevoie!"
                )
            except:
                pass
        
        except Exception as e:
            logger.critical(f"💥 Watchdog CRASHED: {e}")
            try:
                self.telegram.send_telegram_alert(
                    f"🚨 <b>WATCHDOG CRASHUIT!</b> 💥\n\n"
                    f"💀 <b>Eroare:</b> {str(e)}\n"
                    f"⏱️ <b>Crashuit la:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
                    f"⚠️ <b>SERVICIILE NU MAI SUNT MONITORIZATE!</b>\n"
                    f"🚑 Emergency mode - restart watchdog ACUM!\n"
                    f"📞 Suna pe Neo - matrix-ul e-n pericol!"
                )
            except:
                pass
            raise

def main():
    """Entry point"""
    print("🔍 Glitch In Matrix - Service Watchdog v3.2")
    print("━" * 50)
    print("Monitoring critical services...")
    print("Press Ctrl+C to stop")
    print("━" * 50)
    
    watchdog = ServiceWatchdog()
    watchdog.monitor_loop(interval=60)

if __name__ == "__main__":
    main()
