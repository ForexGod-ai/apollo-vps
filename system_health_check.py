#!/usr/bin/env python3
"""
──────────────────
🔍 Glitch in Matrix - System Health Check
──────────────────

Diagnostic rapid pentru verificarea integrității sistemului.
Autor: ФорексГод
Data: 2026-02-04
──────────────────
"""

import os
import sys
import json
import sqlite3
import psutil
import requests
from pathlib import Path
from datetime import datetime
from telegram import Bot
import asyncio

# Configuration
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "trades.db"  # Database in data/ subdirectory
LOGS_DIR = BASE_DIR / "logs"
CHARTS_DIR = BASE_DIR / "charts"

# Load Telegram credentials from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
except Exception as e:
    TELEGRAM_TOKEN = None
    TELEGRAM_CHAT_ID = None


class HealthCheck:
    """Verificare stare sistem Glitch in Matrix"""
    
    def __init__(self):
        self.results = {}
        self.errors = []
        
    def print_header(self):
        """Afișează header elegant"""
        print("\n" + "═" * 70)
        print("🔍 GLITCH IN MATRIX - SYSTEM HEALTH CHECK")
        print("═" * 70)
        print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("═" * 70 + "\n")
        
    def check_services(self):
        """Verifică procesele critice"""
        print("📊 STATUS SERVICII:")
        print("─" * 70)
        
        services = {
            "ctrader_sync_daemon.py": "cTrader Sync Daemon",
            "position_monitor.py": "Position Monitor",
            "setup_executor_monitor.py": "Setup Executor Monitor",
            "service_watchdog.py": "Service Watchdog"
        }
        
        running = {}
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline:
                    cmdline_str = ' '.join(cmdline)
                    for service_file, service_name in services.items():
                        if service_file in cmdline_str:
                            running[service_name] = proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        service_status = {}
        for service_file, service_name in services.items():
            if service_name in running:
                print(f"   ✅ {service_name:<30} RUNNING (PID {running[service_name]})")
                service_status[service_name] = True
            else:
                print(f"   ❌ {service_name:<30} NOT RUNNING")
                service_status[service_name] = False
                self.errors.append(f"Service {service_name} is not running")
        
        self.results['services'] = service_status
        print()
        
    def check_sqlite(self):
        """Verifică integritatea bazei de date"""
        print("💾 INTEGRITATE SQLite:")
        print("─" * 70)
        
        if not DB_PATH.exists():
            print(f"   ❌ Database NOT FOUND: {DB_PATH}")
            self.errors.append(f"Database file missing: {DB_PATH}")
            self.results['sqlite'] = False
            print()
            return
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Check closed_trades table
            cursor.execute("SELECT COUNT(*) FROM closed_trades")
            total_trades = cursor.fetchone()[0]
            
            # Check open_positions table
            cursor.execute("SELECT COUNT(*) FROM open_positions")
            open_positions = cursor.fetchone()[0]
            
            # Check account_snapshots table
            cursor.execute("SELECT COUNT(*) FROM account_snapshots")
            total_snapshots = cursor.fetchone()[0]
            
            # Check latest snapshot
            cursor.execute("SELECT timestamp FROM account_snapshots ORDER BY timestamp DESC LIMIT 1")
            latest_snapshot = cursor.fetchone()
            latest_time = latest_snapshot[0] if latest_snapshot else "Never"
            
            conn.close()
            
            print(f"   ✅ Database: {DB_PATH}")
            print(f"   📊 Total Trades: {total_trades}")
            print(f"   🔓 Open Positions: {open_positions}")
            print(f"   📸 Total Snapshots: {total_snapshots}")
            print(f"   ⏰ Latest Snapshot: {latest_time}")
            
            self.results['sqlite'] = {
                'accessible': True,
                'trades': total_trades,
                'open_positions': open_positions,
                'snapshots': total_snapshots
            }
            
        except Exception as e:
            print(f"   ❌ Database Error: {e}")
            self.errors.append(f"SQLite error: {e}")
            self.results['sqlite'] = False
        
        print()
        
    def check_ctrader(self):
        """Verifică conexiunea cTrader API"""
        print("🔌 CONEXIUNE cTrader:")
        print("─" * 70)
        
        try:
            # Test API endpoint
            response = requests.get("http://localhost:8767/health", timeout=5)
            
            if response.status_code == 200:
                print("   ✅ cTrader API: CONNECTED (http://localhost:8767)")
            else:
                print(f"   ⚠️  cTrader API: HTTP {response.status_code}")
                self.errors.append(f"cTrader API returned status {response.status_code}")
            
            # Test price feed with a sample symbol
            test_symbol = "EURUSD"
            response = requests.get(
                f"http://localhost:8767/data?symbol={test_symbol}&timeframe=D1&bars=1",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'bars' in data and len(data['bars']) > 0:
                    latest_bar = data['bars'][-1]
                    print(f"   ✅ Price Feed: ACTIVE")
                    print(f"      └─ {test_symbol}: {latest_bar.get('close', 'N/A')} (Latest close)")
                    self.results['ctrader'] = True
                else:
                    print(f"   ⚠️  Price Feed: No data returned for {test_symbol}")
                    self.errors.append("cTrader price feed returned no data")
                    self.results['ctrader'] = False
            else:
                print(f"   ❌ Price Feed: HTTP {response.status_code}")
                self.errors.append(f"cTrader price feed error: {response.status_code}")
                self.results['ctrader'] = False
                
        except requests.exceptions.ConnectionError:
            print("   ❌ cTrader API: NOT REACHABLE (localhost:8767)")
            self.errors.append("cTrader API connection failed")
            self.results['ctrader'] = False
        except Exception as e:
            print(f"   ❌ cTrader API Error: {e}")
            self.errors.append(f"cTrader API error: {e}")
            self.results['ctrader'] = False
        
        print()
        
    def check_telegram_and_charts(self):
        """Verifică Telegram și directorul de grafice"""
        print("📱 TELEGRAM & CHARTS:")
        print("─" * 70)
        
        # Check charts directory
        if not CHARTS_DIR.exists():
            try:
                CHARTS_DIR.mkdir(parents=True, exist_ok=True)
                print(f"   ✅ Charts Directory: CREATED ({CHARTS_DIR})")
            except Exception as e:
                print(f"   ❌ Charts Directory: FAILED TO CREATE - {e}")
                self.errors.append(f"Charts directory error: {e}")
                self.results['charts_dir'] = False
                print()
                return
        else:
            print(f"   ✅ Charts Directory: EXISTS ({CHARTS_DIR})")
        
        # Check write permissions
        test_file = CHARTS_DIR / "test_write.tmp"
        try:
            test_file.write_text("test")
            test_file.unlink()
            print(f"   ✅ Charts Directory: WRITABLE")
            self.results['charts_dir'] = True
        except Exception as e:
            print(f"   ❌ Charts Directory: NOT WRITABLE - {e}")
            self.errors.append(f"Charts directory not writable: {e}")
            self.results['charts_dir'] = False
        
        # Check Telegram
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            print("   ❌ Telegram: CREDENTIALS NOT FOUND")
            self.errors.append("Telegram credentials missing")
            self.results['telegram'] = False
            print()
            return
        
        try:
            # Test message with signature
            async def send_test_message():
                bot = Bot(token=TELEGRAM_TOKEN)
                message = (
                    "🔍 System Health Check - Test Message\n\n"
                    "──────────────────\n"
                    "✨ Glitch in Matrix by ФорексГод ✨\n"
                    "🧠 AI-Powered • 💎 Smart Money"
                )
                await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            
            asyncio.run(send_test_message())
            print("   ✅ Telegram: MESSAGE SENT")
            self.results['telegram'] = True
            
        except Exception as e:
            print(f"   ❌ Telegram: FAILED TO SEND - {e}")
            self.errors.append(f"Telegram error: {e}")
            self.results['telegram'] = False
        
        print()
        
    def check_logs(self):
        """Scanează log-urile pentru erori"""
        print("📋 LOG-URI RECENT:")
        print("─" * 70)
        
        log_files = {
            "daily_scanner.log": "Daily Scanner",
            "sync_daemon.log": "Sync Daemon",
            "position_monitor.log": "Position Monitor",
            "setup_executor.log": "Setup Executor"
        }
        
        errors_found = False
        
        for log_file, log_name in log_files.items():
            log_path = LOGS_DIR / log_file
            
            if not log_path.exists():
                print(f"   ⚠️  {log_name}: LOG FILE NOT FOUND")
                continue
            
            try:
                with open(log_path, 'r') as f:
                    lines = f.readlines()
                    recent_lines = lines[-50:] if len(lines) > 50 else lines
                    
                    error_lines = [
                        line.strip() for line in recent_lines 
                        if 'Error' in line or 'Exception' in line or 'ERROR' in line
                    ]
                    
                    if error_lines:
                        print(f"   ⚠️  {log_name}: {len(error_lines)} errors in last 50 lines")
                        for err_line in error_lines[-3:]:  # Show last 3 errors
                            print(f"      └─ {err_line[:80]}...")
                        errors_found = True
                    else:
                        print(f"   ✅ {log_name}: No errors in last 50 lines")
                        
            except Exception as e:
                print(f"   ❌ {log_name}: Failed to read - {e}")
        
        self.results['logs'] = not errors_found
        print()
        
    def print_summary(self):
        """Afișează rezumatul final"""
        print("═" * 70)
        print("📊 SUMMARY:")
        print("═" * 70)
        
        if self.errors:
            print("\n❌ PROBLEME DETECTATE:")
            for i, error in enumerate(self.errors, 1):
                print(f"   {i}. {error}")
            print()
            print("⚠️  Sistemul necesită atenție! Verifică erorile de mai sus.")
        else:
            print("\n✅ Sistemul Glitch in Matrix este Nominal.")
            print("💰 Spor la profit!")
        
        print("\n" + "═" * 70)
        print("──────────────────")
        print("✨ Glitch in Matrix by ФорексГод ✨")
        print("🧠 AI-Powered • 💎 Smart Money")
        print("──────────────────")
        print()
        
    def run(self):
        """Rulează toate verificările"""
        self.print_header()
        self.check_services()
        self.check_sqlite()
        self.check_ctrader()
        self.check_telegram_and_charts()
        self.check_logs()
        self.print_summary()
        
        # Return exit code
        return 0 if not self.errors else 1


if __name__ == "__main__":
    checker = HealthCheck()
    exit_code = checker.run()
    sys.exit(exit_code)
