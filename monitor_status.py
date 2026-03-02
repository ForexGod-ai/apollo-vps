#!/usr/bin/env python3
"""
🎯 GLITCH IN MATRIX - MONITOR STATUS DASHBOARD
✨ by ФорексГод ✨

Afișează statusul TUTUROR monitoarelor active și ce fac ele.
"""

import psutil
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import json
from typing import List, Dict, Optional


class MonitorDashboard:
    """Dashboard pentru toate monitoarele active"""
    
    def __init__(self):
        self.monitors = {
            'position_monitor.py': {
                'name': '📊 Position Monitor',
                'description': 'Detectează poziții noi/închise → Trimite ARMAGEDDON notifications',
                'lock_file': 'process_position_monitor.lock',
                'log_file': 'position_monitor.log'
            },
            'realtime_monitor.py': {
                'name': '🔄 Realtime Monitor',
                'description': 'Analizează piața la fiecare 4H candle close → Telegram alerts',
                'lock_file': None,
                'log_file': 'realtime_monitor.log'
            },
            'ctrader_sync_daemon.py': {
                'name': '🔗 cTrader Sync Daemon',
                'description': 'Sincronizare live cu cTrader → Trade history updates',
                'lock_file': 'ctrader_sync.lock',
                'log_file': 'ctrader_sync.log'
            },
            'news_calendar_monitor.py': {
                'name': '📰 News Calendar Monitor',
                'description': 'Monitorizare evenimente economice → NFP/CPI alerts',
                'lock_file': None,
                'log_file': 'news_calendar.log'
            },
            'signal_confirmation_monitor.py': {
                'name': '✅ Signal Confirmation Monitor',
                'description': 'Verifică setup-uri MONITORING → Execută când 4H CHoCH apare',
                'lock_file': None,
                'log_file': None
            }
        }
    
    def find_running_process(self, script_name: str) -> Optional[Dict]:
        """Găsește procesul Python care rulează script-ul specificat"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'memory_info']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and script_name in ' '.join(cmdline):
                    return {
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': ' '.join(cmdline),
                        'create_time': datetime.fromtimestamp(proc.info['create_time']),
                        'memory_mb': proc.info['memory_info'].rss / 1024 / 1024,
                        'cpu_percent': proc.cpu_percent(interval=0.1)
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    
    def read_last_log_lines(self, log_file: str, lines: int = 5) -> List[str]:
        """Citește ultimele linii din log"""
        log_path = Path(log_file)
        if not log_path.exists():
            return []
        
        try:
            result = subprocess.run(
                ['tail', '-n', str(lines), str(log_path)],
                capture_output=True,
                text=True,
                timeout=2
            )
            return result.stdout.strip().split('\n') if result.stdout else []
        except:
            return []
    
    def check_monitoring_setups(self) -> Dict:
        """Citește monitoring_setups.json pentru a vedea ce trade-uri așteaptă"""
        monitoring_file = Path("monitoring_setups.json")
        if not monitoring_file.exists():
            return {'count': 0, 'setups': []}
        
        try:
            with open(monitoring_file, 'r') as f:
                data = json.load(f)
            
            setups = data.get('setups', [])
            active_setups = [s for s in setups if s.get('status') != 'EXPIRED']
            
            return {
                'count': len(active_setups),
                'setups': active_setups[:5]  # First 5
            }
        except:
            return {'count': 0, 'setups': []}
    
    def check_open_positions(self) -> Dict:
        """Citește trade_history.json pentru poziții deschise"""
        trade_history = Path("trade_history.json")
        if not trade_history.exists():
            return {'count': 0, 'positions': []}
        
        try:
            with open(trade_history, 'r') as f:
                data = json.load(f)
            
            open_trades = [t for t in data.get('trades', []) if t.get('status') == 'open']
            
            return {
                'count': len(open_trades),
                'positions': open_trades[:5]  # First 5
            }
        except:
            return {'count': 0, 'positions': []}
    
    def print_dashboard(self):
        """Afișează dashboard-ul complet"""
        print("\n" + "="*100)
        print("🎯 GLITCH IN MATRIX - MONITOR STATUS DASHBOARD V6.0")
        print("✨ by ФорексГод ✨")
        print("="*100)
        print(f"📅 Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*100)
        
        # Check each monitor
        running_count = 0
        
        for script_name, info in self.monitors.items():
            proc_info = self.find_running_process(script_name)
            
            print(f"\n{info['name']}")
            print(f"   📝 {info['description']}")
            
            if proc_info:
                running_count += 1
                uptime = datetime.now() - proc_info['create_time']
                days = uptime.days
                hours = uptime.seconds // 3600
                minutes = (uptime.seconds % 3600) // 60
                
                print(f"   ✅ STATUS: RUNNING")
                print(f"   🆔 PID: {proc_info['pid']}")
                print(f"   ⏰ Uptime: {days}d {hours}h {minutes}m")
                print(f"   💾 Memory: {proc_info['memory_mb']:.1f} MB")
                print(f"   ⚡ CPU: {proc_info['cpu_percent']:.1f}%")
                
                # Show last log activity
                if info['log_file']:
                    last_logs = self.read_last_log_lines(info['log_file'], 2)
                    if last_logs:
                        print(f"   📋 Last Activity:")
                        for log_line in last_logs:
                            # Truncate long lines
                            if len(log_line) > 80:
                                log_line = log_line[:77] + "..."
                            print(f"      {log_line}")
            else:
                print(f"   ❌ STATUS: NOT RUNNING")
                print(f"   ⚠️  Monitor inactiv - poate fi pornit cu: python3 {script_name}")
        
        # Summary
        print(f"\n{'='*100}")
        print(f"📊 SUMMARY:")
        print(f"   🟢 Running Monitors: {running_count}/{len(self.monitors)}")
        print(f"   🔴 Stopped Monitors: {len(self.monitors) - running_count}/{len(self.monitors)}")
        
        # Check monitoring setups
        monitoring_data = self.check_monitoring_setups()
        print(f"\n📋 MONITORING SETUPS (în așteptare pentru confirmarea 4H):")
        print(f"   📊 Total Active: {monitoring_data['count']}")
        
        if monitoring_data['setups']:
            print(f"   🎯 Top Setups:")
            for setup in monitoring_data['setups'][:3]:
                symbol = setup.get('symbol', 'N/A')
                direction = setup.get('direction', 'N/A')
                status = setup.get('status', 'N/A')
                dir_icon = "🔴" if direction == 'sell' else "🟢"
                print(f"      {dir_icon} {symbol} {direction.upper()} - Status: {status}")
        
        # Check open positions
        positions_data = self.check_open_positions()
        print(f"\n💼 OPEN POSITIONS (trade-uri active):")
        print(f"   📊 Total Open: {positions_data['count']}")
        
        if positions_data['positions']:
            print(f"   💰 Active Trades:")
            for pos in positions_data['positions'][:3]:
                symbol = pos.get('symbol', 'N/A')
                direction = pos.get('direction', 'N/A')
                lot = pos.get('lot_size', 0)
                entry = pos.get('entry_price', 0)
                dir_icon = "📈" if direction == 'BUY' else "📉"
                print(f"      {dir_icon} {symbol} {direction} {lot} lot @ {entry:.5f}")
        
        print("\n" + "="*100)
        
        # What each monitor does
        print(f"\n💡 CE FAC MONITOARELE:")
        print(f"{'─'*100}")
        
        print(f"\n1. 📊 POSITION MONITOR (cel mai important!):")
        print(f"   • Verifică trade_history.json la fiecare 10 secunde")
        print(f"   • Detectează când se DESCHIDE o poziție nouă")
        print(f"   • Trimite ARMAGEDDON notification pe Telegram")
        print(f"   • Detectează când se ÎNCHIDE o poziție")
        print(f"   • Trimite profit/loss report pe Telegram")
        print(f"   • Trigger ML auto-learning după fiecare trade închis")
        
        print(f"\n2. 🔄 REALTIME MONITOR:")
        print(f"   • Analizează TOATE perechile la fiecare 4H candle close")
        print(f"   • Verifică dacă status s-a schimbat (ex: MONITOR → READY)")
        print(f"   • Trimite alert pe Telegram când setup devine READY")
        print(f"   • Spatiotemporal analysis (narrativ market)")
        
        print(f"\n3. 🔗 CTRADER SYNC DAEMON:")
        print(f"   • Sincronizare live cu cTrader API")
        print(f"   • Actualizează trade_history.json automat")
        print(f"   • Verifică poziții deschise/închise")
        print(f"   • Rulează continuu în background")
        
        print(f"\n4. 📰 NEWS CALENDAR MONITOR:")
        print(f"   • Monitorizează evenimente economice majore")
        print(f"   • Alert înainte de NFP, CPI, FOMC")
        print(f"   • Kill switch automat la evenimente HIGH IMPACT")
        
        print(f"\n5. ✅ SIGNAL CONFIRMATION MONITOR:")
        print(f"   • Verifică setup-uri în MONITORING status")
        print(f"   • Scanează pentru 4H CHoCH confirmation")
        print(f"   • Când găsește CHoCH → Execută trade automat")
        print(f"   • Update status MONITORING → READY")
        
        print(f"\n{'─'*100}")
        print(f"\n🚀 PENTRU CE SERVEȘTE FIECARE:")
        print(f"   📊 Position Monitor → NOTIFICĂRI când trade-uri se deschid/închid")
        print(f"   🔄 Realtime Monitor → ALERTEAZĂ când market devine favorabil")
        print(f"   🔗 cTrader Sync → SINCRONIZARE cu broker-ul")
        print(f"   📰 News Monitor → PROTECȚIE la evenimente majore")
        print(f"   ✅ Signal Confirmation → EXECUȚIE AUTOMATĂ când confirmarea apare")
        
        print(f"\n{'='*100}\n")


def main():
    """Main entry point"""
    dashboard = MonitorDashboard()
    dashboard.print_dashboard()


if __name__ == "__main__":
    main()
