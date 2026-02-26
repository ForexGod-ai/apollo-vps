#!/usr/bin/env python3
"""
🌐 MATRIX WEB DASHBOARD V1.0
──────────────────
✨ Glitch in Matrix by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money

Live HTTP Dashboard for Complete System Audit:
- 🌳 Ecosystem Architecture (Visual Map)
- 🟢 Monitor Status (Live Health Check)
- 🎯 Active Setups Radar (Live Positioning)

Access: http://localhost:8080
──────────────────
"""

import os
import json
import psutil
import time
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify
from loguru import logger

app = Flask(__name__)
BASE_PATH = Path(__file__).parent


class MatrixDashboard:
    """Live dashboard data provider"""
    
    def __init__(self):
        self.base_path = BASE_PATH
        
        # Monitor definitions (matching watchdog_monitor.py)
        self.monitors = {
            'setup_executor_monitor.py': {
                'name': 'Setup Executor',
                'emoji': '🎯',
                'description': 'Executes trades when 4H conditions are met',
                'interval': '30s'
            },
            'position_monitor.py': {
                'name': 'Position Monitor',
                'emoji': '💰',
                'description': 'Tracks opened/closed positions & P/L',
                'interval': 'Real-time'
            },
            'telegram_command_center.py': {
                'name': 'Command Center',
                'emoji': '🤖',
                'description': 'Telegram bot for commands (/active, /status)',
                'interval': 'Event-driven'
            },
            'realtime_monitor.py': {
                'name': 'Realtime Monitor',
                'emoji': '📊',
                'description': '4H candle analysis & setup validation',
                'interval': '4H candles'
            },
            'ctrader_sync_daemon.py': {
                'name': 'cTrader Sync',
                'emoji': '🔗',
                'description': 'Broker synchronization daemon',
                'interval': 'Continuous'
            }
        }
    
    def get_ecosystem_architecture(self):
        """
        🌳 ECOSYSTEM ARCHITECTURE
        Visual map of all system components
        """
        architecture = {
            'core_components': [
                {
                    'name': '🧠 AI Strategy Engine',
                    'description': 'Smart Money + ICT Concepts (FVG, OB, Liquidity)',
                    'status': 'active',
                    'files': ['scanner_v3.py', 'unified_risk_manager.py']
                },
                {
                    'name': '📡 Daily Scanner',
                    'description': 'Scans all pairs for 4H setups (morning & real-time)',
                    'status': 'active',
                    'files': ['scan_all_pairs.py', 'daily_scanner.py']
                },
                {
                    'name': '🎯 Setup Executor Monitor',
                    'description': 'Auto-executes trades when 4H candle confirms',
                    'status': self._get_process_status('setup_executor_monitor.py'),
                    'files': ['setup_executor_monitor.py']
                },
                {
                    'name': '💰 Position Monitor',
                    'description': 'Tracks P/L, sends Telegram alerts on open/close',
                    'status': self._get_process_status('position_monitor.py'),
                    'files': ['position_monitor.py']
                },
                {
                    'name': '🤖 Telegram Command Center',
                    'description': 'Bot interface for system control',
                    'status': self._get_process_status('telegram_command_center.py'),
                    'files': ['telegram_command_center.py']
                }
            ],
            'optional_monitors': [
                {
                    'name': '📊 Realtime Monitor',
                    'description': '4H candle live analysis',
                    'status': self._get_process_status('realtime_monitor.py'),
                    'files': ['realtime_monitor.py']
                },
                {
                    'name': '🔗 cTrader Sync Daemon',
                    'description': 'Broker account synchronization',
                    'status': self._get_process_status('ctrader_sync_daemon.py'),
                    'files': ['ctrader_sync_daemon.py']
                },
                {
                    'name': '📰 News Calendar Monitor',
                    'description': 'Economic events tracker (NFP, CPI)',
                    'status': self._get_process_status('news_calendar_monitor.py'),
                    'files': ['news_calendar_monitor.py']
                }
            ],
            'execution_layer': [
                {
                    'name': '🔄 cTrader Executor',
                    'description': 'Python → cTrader bridge (signals.json)',
                    'status': 'active',
                    'files': ['ctrader_executor.py']
                },
                {
                    'name': '🤝 cTrader C# Bot',
                    'description': 'PythonSignalExecutor.cs (reads signals.json)',
                    'status': 'active',
                    'files': ['PythonSignalExecutor.cs']
                }
            ],
            'protection_layer': [
                {
                    'name': '🛡️ Watchdog Monitor V3.8',
                    'description': 'Auto-restarts failed monitors (State Tracking + Anti-Spam)',
                    'status': self._get_process_status('watchdog_monitor.py'),
                    'files': ['watchdog_monitor.py']
                },
                {
                    'name': '🚀 Matrix Bootloader',
                    'description': 'Startup script (Kill → Cleanup → Launch)',
                    'status': 'manual',
                    'files': ['start_matrix.sh']
                }
            ]
        }
        
        return architecture
    
    def get_monitor_status(self):
        """
        🟢 LIVE MONITOR STATUS
        Real-time health check of all background processes
        """
        status = []
        
        for process_name, info in self.monitors.items():
            is_running = self._is_process_running(process_name)
            pid = self._get_process_pid(process_name) if is_running else None
            
            status.append({
                'name': info['name'],
                'emoji': info['emoji'],
                'description': info['description'],
                'interval': info['interval'],
                'running': is_running,
                'pid': pid,
                'status_emoji': '🟢' if is_running else '🔴',
                'status_text': 'RUNNING' if is_running else 'STOPPED'
            })
        
        # Add watchdog status
        watchdog_running = self._is_process_running('watchdog_monitor.py')
        watchdog_pid = self._get_process_pid('watchdog_monitor.py') if watchdog_running else None
        
        status.insert(0, {
            'name': 'Watchdog Guardian',
            'emoji': '🛡️',
            'description': 'Auto-restart system (V3.8 State Tracking)',
            'interval': '60s checks',
            'running': watchdog_running,
            'pid': watchdog_pid,
            'status_emoji': '🟢' if watchdog_running else '🔴',
            'status_text': 'RUNNING' if watchdog_running else 'STOPPED'
        })
        
        return status
    
    def get_active_setups(self):
        """
        🎯 ACTIVE SETUPS RADAR
        Live positioning - pairs waiting for 4H confirmation
        """
        setups_file = self.base_path / 'monitoring_setups.json'
        
        if not setups_file.exists():
            return []
        
        try:
            with open(setups_file, 'r') as f:
                data = json.load(f)
            
            setups = []
            for setup in data.get('setups', []):
                # Calculate time since detection
                detected_time = datetime.fromisoformat(setup.get('detected_at', datetime.now().isoformat()))
                time_diff = datetime.now() - detected_time
                hours_waiting = time_diff.total_seconds() / 3600
                
                # Parse FVG zone
                fvg_zone = setup.get('fvg_zone', '?-?')
                
                # Calculate distance in pips (if available)
                entry_price = setup.get('entry_price', 0)
                current_price = setup.get('current_price', entry_price)
                distance_pips = abs(current_price - entry_price) * 10000  # Assuming 4-digit pairs
                
                setups.append({
                    'pair': setup.get('pair', 'UNKNOWN'),
                    'direction': setup.get('direction', 'UNKNOWN'),
                    'direction_emoji': '🟢' if setup.get('direction') == 'BUY' else '🔴',
                    'status': setup.get('status', 'UNKNOWN'),
                    'fvg_zone': fvg_zone,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'distance_pips': round(distance_pips, 1),
                    'hours_waiting': round(hours_waiting, 1),
                    'detected_at': detected_time.strftime('%Y-%m-%d %H:%M'),
                    'confidence': setup.get('confidence', 'N/A'),
                    'timeframe': setup.get('timeframe', '4H')
                })
            
            return setups
        
        except Exception as e:
            logger.error(f"❌ Error reading setups: {e}")
            return []
    
    def get_system_stats(self):
        """
        📊 SYSTEM STATISTICS
        Overall health metrics
        """
        monitors_running = sum(1 for m in self.get_monitor_status() if m['running'])
        total_monitors = len(self.monitors) + 1  # +1 for watchdog
        
        active_setups = len(self.get_active_setups())
        
        # Read open positions (if available)
        positions_file = self.base_path / 'active_positions.json'
        open_positions = 0
        if positions_file.exists():
            try:
                with open(positions_file, 'r') as f:
                    data = json.load(f)
                    open_positions = len(data.get('positions', []))
            except:
                pass
        
        return {
            'monitors_running': monitors_running,
            'total_monitors': total_monitors,
            'monitors_health': f"{monitors_running}/{total_monitors}",
            'health_percentage': round((monitors_running / total_monitors) * 100),
            'active_setups': active_setups,
            'open_positions': open_positions,
            'uptime': self._get_system_uptime()
        }
    
    def _is_process_running(self, process_name: str) -> bool:
        """Check if process is running"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        cmdline = proc.info['cmdline']
                        if cmdline:
                            cmdline_str = ' '.join(cmdline)
                            if process_name in cmdline_str:
                                return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            return False
        except:
            return False
    
    def _get_process_pid(self, process_name: str) -> int:
        """Get process PID"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        cmdline = proc.info['cmdline']
                        if cmdline:
                            cmdline_str = ' '.join(cmdline)
                            if process_name in cmdline_str:
                                return proc.info['pid']
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            return None
        except:
            return None
    
    def _get_process_status(self, process_name: str) -> str:
        """Get process status (active/stopped/manual)"""
        return 'active' if self._is_process_running(process_name) else 'stopped'
    
    def _get_system_uptime(self) -> str:
        """Get system uptime"""
        try:
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return f"{days}d {hours}h {minutes}m"
        except:
            return "N/A"


# Initialize dashboard
dashboard = MatrixDashboard()


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('matrix_dashboard.html')


@app.route('/api/architecture')
def api_architecture():
    """Get ecosystem architecture"""
    return jsonify(dashboard.get_ecosystem_architecture())


@app.route('/api/monitors')
def api_monitors():
    """Get live monitor status"""
    return jsonify(dashboard.get_monitor_status())


@app.route('/api/setups')
def api_setups():
    """Get active setups"""
    return jsonify(dashboard.get_active_setups())


@app.route('/api/stats')
def api_stats():
    """Get system statistics"""
    return jsonify(dashboard.get_system_stats())


@app.route('/api/live')
def api_live():
    """
    Live SSE endpoint for real-time updates
    (Not implemented yet - future enhancement)
    """
    return jsonify({'status': 'ok'})


def main():
    """Entry point"""
    logger.info("🌐 MATRIX WEB DASHBOARD V1.0")
    logger.info("──────────────────")
    logger.info("✨ Glitch in Matrix by ФорексГод ✨")
    logger.info("🧠 AI-Powered • 💎 Smart Money")
    logger.info("──────────────────")
    logger.info("")
    logger.info("🚀 Starting web server on http://localhost:8080")
    logger.info("📊 Dashboard features:")
    logger.info("   🌳 Ecosystem Architecture")
    logger.info("   🟢 Live Monitor Status")
    logger.info("   🎯 Active Setups Radar")
    logger.info("")
    logger.info("Press Ctrl+C to stop")
    logger.info("")
    
    # Ensure templates directory exists
    templates_dir = Path(__file__).parent / 'templates'
    templates_dir.mkdir(exist_ok=True)
    
    # Run Flask server
    app.run(host='0.0.0.0', port=8080, debug=False)


if __name__ == "__main__":
    main()
