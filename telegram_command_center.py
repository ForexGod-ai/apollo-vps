#!/usr/bin/env python3
"""
🎮 TELEGRAM COMMAND CENTER V10.4
────────────────
🔱 AUTHORED BY ФорексГод 🔱
🏛️ Глитч Ин Матрикс 🏛️

Interactive Command Interface:
- /stats - Daily trading statistics
- /monitoring - Active setup list
- /status - System monitors health check
- /btcusd - Quick BTCUSD analysis
────────────────
"""

import os
import json
import sqlite3
import subprocess
import sys
import atexit
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import requests
import time
import os
import psutil
from loguru import logger

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
    str(_LOG_DIR / "telegram_command_center.log"),
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
    level="DEBUG",
    rotation="10 MB",
    retention="7 days",
    compression="zip"
)

# Universal separator - EXACTLY 18 characters for alignment
UNIVERSAL_SEPARATOR = "──────────────────"


def acquire_pid_lock(lock_file: Path) -> bool:
    """
    🔒 PID LOCK SINGLETON PATTERN - Prevents duplicate process instances
    Returns True if lock acquired, False if another instance is already running
    """
    try:
        if lock_file.exists():
            # Read existing PID
            with open(lock_file, 'r') as f:
                old_pid = int(f.read().strip())
            
            # Check if process is still running
            if psutil.pid_exists(old_pid):
                try:
                    proc = psutil.Process(old_pid)
                    # Verify it's the same script (not PID reuse)
                    if 'telegram_command_center' in ' '.join(proc.cmdline()):
                        logger.error(f"❌ Command Center already running (PID {old_pid})")
                        logger.error("⚠️  Cannot start duplicate instance - exiting")
                        return False
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Stale lock file - remove it
            logger.warning(f"🔧 Removing stale lock file (PID {old_pid} not running)")
            lock_file.unlink()
        
        # Acquire lock
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        
        logger.success(f"🔒 PID lock acquired: {lock_file} (PID {os.getpid()})")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to acquire PID lock: {e}")
        return False


def release_pid_lock(lock_file: Path):
    """Release PID lock on exit"""
    try:
        if lock_file.exists():
            lock_file.unlink()
            logger.info(f"🔓 PID lock released: {lock_file}")
    except Exception as e:
        logger.error(f"⚠️  Failed to release lock: {e}")

class TelegramCommandCenter:
    """Handle interactive Telegram commands"""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.authorized_user_id = int(os.getenv('TELEGRAM_USER_ID', '0'))
        
        # V8.1: Path alignment — resolve relative to script location, not CWD
        script_dir = Path(__file__).parent.resolve()
        self.db_path = script_dir / 'data' / 'trades.db'
        self.monitoring_file = script_dir / 'monitoring_setups.json'
        self.active_positions_file = script_dir / 'active_positions.json'
        
        self.last_update_id = 0
        
        logger.info("🎮 Telegram Command Center V3.7 initialized")
        logger.info(f"🔐 Authorized User ID: {self.authorized_user_id}")
        logger.info(f"📁 Monitoring file: {self.monitoring_file}")
    
    def get_updates(self):
        """Get new messages from Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {'offset': self.last_update_id + 1, 'timeout': 30}
            
            response = requests.get(url, params=params, timeout=35)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return data.get('result', [])
        except Exception as e:
            logger.error(f"❌ Error getting updates: {e}")
        
        return []
    
    def force_sync_from_ctrader(self):
        """
        🔄 FORCE SYNC - Fetch fresh data from cTrader before showing stats
        Ensures we see the latest closed trades (including today's SL hits)
        """
        try:
            logger.info("🔄 Force syncing from cTrader...")
            
            # Fetch from cTrader API
            ctrader_api_url = "http://localhost:8767/history"
            response = requests.get(ctrader_api_url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # Quick sync to database
                from ctrader_sync_daemon import TradeDatabase, write_trade_history
                db = TradeDatabase()
                write_trade_history(data, db)
                
                logger.success("✅ Force sync complete - data is fresh!")
                return True
            else:
                logger.warning(f"⚠️  cTrader API returned {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.warning("⚠️  cTrader API offline - using cached data")
            return False
        except Exception as e:
            logger.error(f"❌ Force sync error: {e}")
            return False
    
    def send_message(self, text: str):
        """Send message to Telegram with HTML formatting"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            # ═══ V10.4 SOVEREIGN SIGNATURE — 16-Line Symmetry ═══
            sep = "────────────────"  # 16 chars
            branded_text = (
                f"{text}\n\n"
                f"  {sep}\n"
                f"  🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
                f"  {sep}\n"
                f"  🏛️  <b>Глитч Ин Матрикс</b>  🏛️"
            )
            
            payload = {
                'chat_id': self.chat_id,
                'text': branded_text,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}")
            return False
    
    def handle_stats_command(self):
        """📊 Handle /stats command - Show today's trading statistics (COMPACT VERTICAL)"""
        try:
            # 🔄 FORCE SYNC - Get fresh data from cTrader first
            self.force_sync_from_ctrader()
            
            if not self.db_path.exists():
                return "❌ <b>Database not found!</b>\n\n<code>trades.db</code> missing."
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 🕒 Today's stats using LOCALTIME (critical for timezone accuracy)
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute("""
                SELECT COUNT(*), 
                       SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                       SUM(profit) as total_profit,
                       AVG(profit) as avg_profit
                FROM closed_trades
                WHERE DATE(close_time, 'localtime') = ?
            """, (today,))
            
            row = cursor.fetchone()
            total_trades = row[0] or 0
            wins = row[1] or 0
            total_profit = row[2] or 0
            avg_profit = row[3] or 0
            
            losses = total_trades - wins
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            
            # Emoji based on profit
            profit_emoji = "🔥" if total_profit > 0 else ("💥" if total_profit < 0 else "⚪")
            
            # 📦 COMPACT VERTICAL LAYOUT (Dashboard Sniper)
            message = f"""<b>📊 DAILY STATS</b>
──────────────────
<b>📅 {datetime.now().strftime('%d %b %Y')}</b>

{profit_emoji} <b>Net Profit</b>
<code>${total_profit:+.2f}</code>

📈 <b>Trades</b>
<code>{total_trades}</code> total

✅ <b>Wins</b> / ❌ <b>Losses</b>
<code>{wins}</code> • <code>{losses}</code>

🎯 <b>Win Rate</b>
<code>{win_rate:.1f}%</code>

💵 <b>Avg P/L</b>
<code>${avg_profit:+.2f}</code>
──────────────────"""
            
            # Week stats (compact)
            week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            cursor.execute("""
                SELECT SUM(profit) as weekly_profit,
                       COUNT(*) as weekly_trades
                FROM closed_trades
                WHERE DATE(close_time, 'localtime') >= ?
            """, (week_ago,))
            
            row = cursor.fetchone()
            weekly_profit = row[0] or 0
            weekly_trades = row[1] or 0
            
            weekly_emoji = "🔥" if weekly_profit > 0 else ("💥" if weekly_profit < 0 else "⚪")
            
            message += f"""\n<b>📈 WEEKLY (7d)</b>\n\n{weekly_emoji} <b>Profit</b>\n<code>${weekly_profit:+.2f}</code>\n\n📋 <b>Trades</b>\n<code>{weekly_trades}</code>"""
            
            conn.close()
            return message
            
        except Exception as e:
            logger.error(f"❌ Stats command error: {e}")
            return f"❌ <b>Error:</b> {str(e)}"
    
    def _load_broker_positions(self) -> dict:
        """
        Load REAL positions from active_positions.json (written by cBot sync).
        Returns dict: {symbol: [position_data, ...]} for cross-reference.
        """
        broker = {}
        try:
            if not self.active_positions_file.exists():
                logger.warning("⚠️  active_positions.json not found — broker data unavailable")
                return broker
            
            with open(self.active_positions_file, 'r') as f:
                positions = json.load(f)
            
            if not isinstance(positions, list):
                return broker
            
            for pos in positions:
                sym = pos.get('symbol', '')
                if sym:
                    broker.setdefault(sym, []).append(pos)
            
            return broker
        except Exception as e:
            logger.error(f"❌ Error loading broker positions: {e}")
            return broker
    
    def _expire_stale_actives(self, setups: list, broker_symbols: set) -> int:
        """
        Auto-expire ACTIVE setups that are NOT at broker.
        If a setup has status='ACTIVE' but its symbol is missing from 
        active_positions.json, mark it as 'EXPIRED'.
        
        Returns count of expired setups.
        """
        expired_count = 0
        for setup in setups:
            if setup.get('status') == 'ACTIVE':
                sym = setup.get('symbol', '')
                if sym and sym not in broker_symbols:
                    setup['status'] = 'EXPIRED'
                    setup['expired_reason'] = 'Not found at broker (auto-cleanup)'
                    expired_count += 1
                    logger.info(f"🧹 EXPIRED: {sym} — not at broker, status → EXPIRED")
        
        if expired_count > 0:
            try:
                with open(self.monitoring_file, 'r') as f:
                    data = json.load(f)
                data['setups'] = setups
                with open(self.monitoring_file, 'w') as f:
                    json.dump(data, f, indent=2)
                logger.success(f"🧹 Auto-expired {expired_count} stale setup(s) from monitoring_setups.json")
            except Exception as e:
                logger.error(f"❌ Failed to save expired setups: {e}")
        
        return expired_count

    def handle_monitoring_command(self):
        """
        /monitoring — BROKER-VERIFIED overview.
        Cross-references monitoring_setups.json with active_positions.json
        to show only REAL positions as LIVE, and flags desync.
        """
        try:
            # ─── LOAD MONITORING SETUPS ───
            if not self.monitoring_file.exists():
                return "❌ <b>No monitoring setups found!</b>\n\n<code>monitoring_setups.json</code> missing."
            
            with open(self.monitoring_file, 'r') as f:
                data = json.load(f)
            
            setups = data.get('setups', [])
            
            # ─── LOAD REAL BROKER POSITIONS ───
            broker = self._load_broker_positions()
            broker_symbols = set(broker.keys())
            
            # ─── AUTO-EXPIRE stale ACTIVE setups not at broker ───
            expired_count = self._expire_stale_actives(setups, broker_symbols)
            
            # ─── RE-CLASSIFY after cleanup ───
            monitoring_setups = [s for s in setups if s.get('status') == 'MONITORING']
            confirmed_live = [s for s in setups if s.get('status') == 'ACTIVE' and s.get('symbol') in broker_symbols]
            desync_setups = [s for s in setups if s.get('status') == 'ACTIVE' and s.get('symbol') not in broker_symbols]
            expired_setups = [s for s in setups if s.get('status') == 'EXPIRED']
            
            total_broker = sum(len(v) for v in broker.values())
            
            if not monitoring_setups and not confirmed_live and not broker_symbols:
                return "⚪ <b>All clear</b>\n\nNo setups in pândă, no positions at broker.\nWaiting for new opportunities."
            
            message = (
                f"<b>🎯 COMMAND CENTER — BROKER VERIFIED</b>\n"
                f"{UNIVERSAL_SEPARATOR}\n\n"
                f"👁️ Pândă: <b>{len(monitoring_setups)}</b> | "
                f"🔥 Live: <b>{len(confirmed_live)}</b> ({total_broker} pos) | "
                f"🧹 Expired: <b>{expired_count}</b>\n"
            )
            
            # ═══ SECTION 1: 🔥 LIVE AT BROKER (confirmed by active_positions.json) ═══
            if broker_symbols:
                message += f"\n{UNIVERSAL_SEPARATOR}\n"
                message += "🔥 <b>LIVE LA BROKER</b> (confirmed)\n\n"
                
                idx = 0
                for sym in sorted(broker_symbols):
                    positions = broker[sym]
                    for pos in positions:
                        idx += 1
                        direction = pos.get('direction', '?')
                        entry = pos.get('entry_price', 0)
                        profit = pos.get('net_profit', 0)
                        pips = pos.get('pips', 0)
                        sl = pos.get('stop_loss')
                        tp = pos.get('take_profit')
                        
                        dir_emoji = "🟢" if direction in ('buy', 'BUY') else "🔴"
                        dir_label = direction.upper()
                        
                        # Profit coloring
                        if profit > 0:
                            pl_emoji = "💚"
                            pl_text = f"+${profit:.2f}"
                        elif profit < 0:
                            pl_emoji = "❤️"
                            pl_text = f"-${abs(profit):.2f}"
                        else:
                            pl_emoji = "💛"
                            pl_text = "$0.00"
                        
                        sl_text = f"{sl:.5f}" if sl else "NONE ⚠️"
                        tp_text = f"{tp:.5f}" if tp else "NONE ⚠️"
                        
                        message += (
                            f"<b>{idx}.</b> <code>{sym}</code> {dir_emoji} <b>{dir_label}</b>\n"
                            f"   📍 Entry: <code>{entry:.5f}</code>\n"
                            f"   🛡️ SL: <code>{sl_text}</code> | 🎯 TP: <code>{tp_text}</code>\n"
                            f"   {pl_emoji} P/L: <code>{pl_text}</code> ({pips:+.1f} pips)\n\n"
                        )
            
            # ═══ SECTION 2: 👁️ PÂNDĂ ACTIVĂ (waiting for confirmation) ═══
            if monitoring_setups:
                message += f"{UNIVERSAL_SEPARATOR}\n"
                message += "👁️ <b>PÂNDĂ ACTIVĂ</b> (waiting 1H CHoCH)\n\n"
                
                monitoring_sorted = sorted(monitoring_setups, key=lambda x: x.get('ml_score', 0), reverse=True)
                
                for idx, setup in enumerate(monitoring_sorted[:10], 1):
                    symbol = setup.get('symbol', 'UNKNOWN')
                    direction = setup.get('direction', '?')
                    entry = setup.get('entry_price') or 0.0
                    risk_reward = setup.get('risk_reward') or 0.0
                    ml_score = setup.get('ml_score', 0)
                    ai_prob = setup.get('ai_probability', 0)
                    
                    dir_emoji = "🟢" if direction in ('buy', 'BUY', 'LONG') else "🔴"
                    dir_label = direction.upper()
                    
                    if ml_score >= 70:
                        stars = "⭐⭐⭐"
                    elif ml_score >= 50:
                        stars = "⭐⭐"
                    else:
                        stars = "⭐"
                    
                    message += (
                        f"<b>{idx}.</b> <code>{symbol}</code> {dir_emoji} <b>{dir_label}</b>\n"
                        f"   📊 ML: <code>{ml_score}/100</code> {stars} | 🧠 AI: <code>{ai_prob}%</code>\n"
                        f"   💰 Entry: <code>{entry:.5f}</code> | ⚖️ RR: <code>1:{risk_reward:.1f}</code>\n\n"
                    )
                
                if len(monitoring_setups) > 10:
                    message += f"<i>... and {len(monitoring_setups) - 10} more in pândă</i>\n"
            
            # ═══ SECTION 3: ⚠️ DESYNC (ACTIVE in JSON but NOT at broker) ═══
            if desync_setups:
                message += f"{UNIVERSAL_SEPARATOR}\n"
                message += "⚠️ <b>DESYNC</b> (in JSON, not at broker)\n\n"
                
                for setup in desync_setups:
                    symbol = setup.get('symbol', '?')
                    direction = setup.get('direction', '?').upper()
                    message += f"   ⚠️ <code>{symbol}</code> {direction} — <i>ghost position</i>\n"
                
                message += "\n"
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Monitoring command error: {e}")
            return f"❌ <b>Error:</b> {str(e)}"
    
    def handle_status_command(self):
        """
        /status DASHBOARD — Full system health + P/L + Deep Sleep + Rejections + News
        ФорексГод — Глитч Ин Матрикс
        """
        try:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            message = (
                f"<b>🔧 SYSTEM STATUS — V10.4</b>\n"
                f"{UNIVERSAL_SEPARATOR}\n\n"
                f"⏰ {now.strftime('%d %b %Y, %H:%M:%S')} UTC\n\n"
            )
            
            # ═══ SECTION 1: MONITORS ═══
            message += "<b>📊 MONITORS:</b>\n"
            
            processes = {
                'realtime_monitor.py': '🔄 Realtime',
                'setup_executor_monitor.py': '🎯 Executor',
                'position_monitor.py': '📊 Positions',
                'telegram_command_center.py': '🎮 Telegram',
                'watchdog_monitor.py': '🛡️ Watchdog',
                'ctrader_sync_daemon.py': '📡 Sync',
                'news_reminder_engine.py': '🔔 News Alerts',
            }
            
            ps_output = ''
            try:
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=5)
                ps_output = result.stdout
            except Exception:
                pass
            
            online_count = 0
            total_count = len(processes)
            for proc_name, display_name in processes.items():
                if proc_name in ps_output:
                    # Get uptime from PID
                    uptime_str = ''
                    try:
                        for proc in psutil.process_iter(['pid', 'cmdline', 'create_time']):
                            if proc.info['cmdline'] and proc_name in ' '.join(proc.info['cmdline']):
                                age_s = time.time() - proc.info['create_time']
                                if age_s >= 86400:
                                    uptime_str = f" ({age_s/86400:.0f}d)"
                                elif age_s >= 3600:
                                    uptime_str = f" ({age_s/3600:.0f}h)"
                                else:
                                    uptime_str = f" ({age_s/60:.0f}m)"
                                break
                    except Exception:
                        pass
                    message += f"  {display_name} ✅{uptime_str}\n"
                    online_count += 1
                else:
                    message += f"  {display_name} ❌ OFFLINE\n"
            
            message += f"  <i>({online_count}/{total_count} online)</i>\n\n"
            
            # ═══ SECTION 2: CONNECTIONS ═══
            message += "<b>📡 CONNECTIONS:</b>\n"
            try:
                resp = requests.get('http://localhost:8767/health', timeout=2)
                cbot_status = '✅' if resp.status_code == 200 else '⚠️'
            except Exception:
                cbot_status = '❌'
            message += f"  🤖 cTrader cBot: {cbot_status}\n"
            message += f"  💾 Database: {'✅' if self.db_path.exists() else '❌'}\n\n"
            
            # ═══ SECTION 3: TODAY'S P/L ═══
            message += "<b>💰 TODAY'S P/L:</b>\n"
            try:
                # Force sync for fresh data
                self.force_sync_from_ctrader()
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                today = datetime.now().strftime('%Y-%m-%d')
                
                cursor.execute("""
                    SELECT COALESCE(SUM(profit), 0), COUNT(*)
                    FROM closed_trades WHERE DATE(close_time, 'localtime') = ?
                """, (today,))
                closed_pnl, trade_count = cursor.fetchone()
                
                # Get balance for percentage
                cursor.execute("SELECT balance FROM account_snapshots ORDER BY timestamp DESC LIMIT 1")
                row = cursor.fetchone()
                balance = row[0] if row else 0
                conn.close()
                
                pnl_pct = (closed_pnl / balance * 100) if balance > 0 else 0
                pnl_emoji = '🟢' if closed_pnl >= 0 else '🔴'
                
                message += f"  {pnl_emoji} Closed: <code>${closed_pnl:+.2f}</code> ({pnl_pct:+.1f}%)\n"
                message += f"  📊 Trades today: <code>{trade_count}</code>\n"
                
                # Risk status
                max_loss = 10.0  # From SUPER_CONFIG
                try:
                    config_file = Path(__file__).parent.resolve() / 'SUPER_CONFIG.json'
                    if config_file.exists():
                        with open(config_file, 'r') as f:
                            sc = json.load(f)
                        max_loss = sc.get('daily_limits', {}).get('max_daily_loss_percent', 10.0)
                except Exception:
                    pass
                
                if pnl_pct >= 0:
                    risk_label = '🟢 SAFE'
                elif pnl_pct > -max_loss:
                    risk_label = f'🟡 CAUTION ({pnl_pct:+.1f}%)'
                else:
                    risk_label = f'🔴 LIMIT HIT ({pnl_pct:+.1f}%)'
                message += f"  🛡️ Risk: {risk_label} (limit: -{max_loss}%)\n\n"
                
            except Exception as e:
                message += f"  ⚠️ Data unavailable: {e}\n\n"
            
            # ═══ SECTION 4: MONITORING SETUPS ═══
            message += "<b>📋 SETUPS:</b>\n"
            try:
                script_dir = Path(__file__).parent.resolve()
                mon_file = script_dir / 'monitoring_setups.json'
                if mon_file.exists():
                    with open(mon_file, 'r') as f:
                        setups = json.load(f).get('setups', [])
                    active = sum(1 for s in setups if s.get('status') == 'ACTIVE')
                    monitoring = sum(1 for s in setups if s.get('status') == 'MONITORING')
                    choch_waiting = sum(1 for s in setups if s.get('status') == 'MONITORING' and not s.get('choch_1h_detected', False))
                    in_zone = sum(1 for s in setups if s.get('choch_1h_detected', False) and s.get('status') in ('MONITORING', 'READY'))
                    message += f"  🔥 Active: <code>{active}</code> | 👀 Pândă: <code>{monitoring}</code>\n"
                    message += f"  ⏳ CHoCH wait: <code>{choch_waiting}</code> | 🎯 In Zone: <code>{in_zone}</code>\n"
                    # 3-column grid: symbol + strategy label [REV-🔒] / [CNT-🔒]
                    def _setup_cell(s: dict) -> str:
                        sym = s.get('symbol', '?')
                        stype = s.get('strategy_type', '').upper()
                        locked = s.get('strategy_locked', False)
                        if stype in ('REVERSAL',):
                            tag = 'REV'
                        elif stype in ('CONTINUATION', 'CONTINUITY'):
                            tag = 'CNT'
                        else:
                            tag = '?'
                        lock_icon = '🔒' if locked else '🔓'
                        return f"• {sym} [{tag}-{lock_icon}]"
                    mon_syms = [s for s in setups if s.get('status') == 'MONITORING']
                    if mon_syms:
                        cols = 3
                        cells = [_setup_cell(s) for s in mon_syms[:cols * 4]]
                        rows = [cells[i:i+cols] for i in range(0, len(cells), cols)]
                        grid = "\n".join("  " + "  ".join(row) for row in rows)
                        extra = len(mon_syms) - cols * 4
                        if extra > 0:
                            grid += f"\n  + {extra} more"
                        message += f"{grid}\n"
                    message += "\n"
                else:
                    message += "  ⚠️ No monitoring file\n\n"
            except Exception:
                message += "  ⚠️ Error reading setups\n\n"
            
            # ═══ SECTION 5: DEEP SLEEP STATUS ═══
            message += "<b>😴 DEEP SLEEP:</b>\n"
            try:
                sleep_file = Path(__file__).parent.resolve() / 'data' / 'deep_sleep_state.json'
                if sleep_file.exists():
                    with open(sleep_file, 'r') as f:
                        sleep_state = json.load(f)
                    wake_str = sleep_state.get('wake_time', '')
                    reason = sleep_state.get('reason', 'Unknown')
                    if wake_str:
                        wake_time = datetime.fromisoformat(wake_str)
                        if wake_time > now:
                            remaining_h = (wake_time - now).total_seconds() / 3600
                            message += f"  🔴 <b>SLEEPING</b> — {remaining_h:.1f}h remaining\n"
                            message += f"  Reason: <i>{reason}</i>\n"
                            message += f"  Wake: <code>{wake_time.strftime('%H:%M UTC')}</code>\n\n"
                        else:
                            message += "  ✅ ACTIVE (sleep expired)\n\n"
                    else:
                        message += "  ✅ ACTIVE\n\n"
                else:
                    message += "  ✅ ACTIVE — scanning normally\n\n"
            except Exception:
                message += "  ✅ ACTIVE\n\n"
            
            # ═══ SECTION 6: RISK REJECTIONS TODAY ═══
            message += "<b>⛔ REJECTIONS TODAY:</b>\n"
            try:
                rej_file = Path(__file__).parent.resolve() / 'data' / 'daily_rejections.json'
                if rej_file.exists():
                    with open(rej_file, 'r') as f:
                        rej_data = json.load(f)
                    today_str = datetime.now(timezone.utc).date().isoformat()
                    if rej_data.get('date') == today_str:
                        total_rej = rej_data.get('total', 0)
                        by_reason = rej_data.get('by_reason', {})
                        message += f"  Total: <code>{total_rej}</code>\n"
                        for reason, count in sorted(by_reason.items(), key=lambda x: -x[1]):
                            message += f"  • {reason}: <code>{count}</code>\n"
                        message += "\n"
                    else:
                        message += "  <code>0</code> (clean day)\n\n"
                else:
                    message += "  <code>0</code> (clean day)\n\n"
            except Exception:
                message += "  ⚠️ Data unavailable\n\n"
            
            # ═══ SECTION 7: NEXT 4H SCAN ═══
            message += "<b>⏰ NEXT 4H SCAN:</b>\n"
            try:
                current_hour = now.hour
                next_4h = [0, 4, 8, 12, 16, 20]
                next_h = None
                for h in next_4h:
                    if h > current_hour:
                        next_h = h
                        break
                if next_h is None:
                    next_close = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    next_close = now.replace(hour=next_h, minute=0, second=0, microsecond=0)
                remaining = next_close - now
                hours_left = remaining.total_seconds() / 3600
                message += f"  <code>{next_close.strftime('%H:%M UTC')}</code> ({hours_left:.1f}h)\n\n"
            except Exception:
                message += "  ⚠️ Unknown\n\n"
            
            # ═══ SECTION 8: NEWS TODAY (synced with upcoming_news.json) ═══
            message += "<b>📰 NEWS TODAY:</b>\n"
            try:
                news_file = Path(__file__).parent.resolve() / 'data' / 'upcoming_news.json'
                if news_file.exists():
                    with open(news_file, 'r') as f:
                        news_data = json.load(f)
                    
                    today_str = now.strftime('%Y-%m-%d')
                    all_events = news_data.get('events', [])
                    
                    # Filter: today's events that haven't happened yet
                    remaining_today = []
                    for ev in all_events:
                        if ev.get('date') == today_str:
                            ev_time = ev.get('time', '23:59')
                            try:
                                ev_hour, ev_min = map(int, ev_time.split(':'))
                                if ev_hour > now.hour or (ev_hour == now.hour and ev_min > now.minute):
                                    remaining_today.append(ev)
                            except Exception:
                                remaining_today.append(ev)  # Include if can't parse
                    
                    high_remaining = sum(1 for e in remaining_today if e.get('impact') == 'High')
                    med_remaining = sum(1 for e in remaining_today if e.get('impact') == 'Medium')
                    
                    if remaining_today:
                        message += f"  🔴 HIGH: <code>{high_remaining}</code> | 🟠 MED: <code>{med_remaining}</code>\n"
                        # Show next upcoming event
                        remaining_today.sort(key=lambda x: x.get('time', '23:59'))
                        next_ev = remaining_today[0]
                        next_flag = {'USD':'🇺🇸','EUR':'🇪🇺','GBP':'🇬🇧','JPY':'🇯🇵','AUD':'🇦🇺','NZD':'🇳🇿','CAD':'🇨🇦','CHF':'🇨🇭'}.get(next_ev.get('currency',''), '🏴')
                        message += f"  ➡️ Next: {next_flag} <b>{next_ev.get('currency','?')}</b> {next_ev.get('event','?')} @ <code>{next_ev.get('time','?')} UTC</code>\n"
                    else:
                        message += "  ✅ No remaining events today\n"
                    
                    # Show data freshness
                    last_updated = news_data.get('last_updated', 'unknown')
                    if last_updated != 'unknown':
                        try:
                            upd_time = datetime.fromisoformat(last_updated)
                            age_h = (now - upd_time).total_seconds() / 3600
                            freshness = '✅' if age_h < 12 else '⚠️'
                            message += f"  {freshness} Data age: <code>{age_h:.1f}h</code>\n\n"
                        except Exception:
                            message += f"  ℹ️ Updated: <code>{last_updated[:16]}</code>\n\n"
                    else:
                        message += "\n"
                else:
                    message += "  ⚠️ upcoming_news.json not found\n\n"
            except Exception:
                message += "  ⚠️ Error reading news data\n\n"
            
            message += f"{UNIVERSAL_SEPARATOR}\n<b>🎯 VERDICT:</b> {'😴 DEEP SLEEP' if (Path(__file__).parent.resolve() / 'data' / 'deep_sleep_state.json').exists() else '✅ OPERATIONAL'}"
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Status command error: {e}")
            return f"❌ <b>Error:</b> {str(e)}"
    
    def handle_btcusd_command(self):
        """Handle /btcusd command - Quick BTCUSD analysis"""
        try:
            # Check if BTCUSD is in monitoring
            if self.monitoring_file.exists():
                with open(self.monitoring_file, 'r') as f:
                    data = json.load(f)
                
                setups = data.get('setups', [])
                btc_setup = next((s for s in setups if s.get('symbol') == 'BTCUSD' and s.get('status') == 'MONITORING'), None)
                
                if btc_setup:
                    direction = btc_setup.get('direction', 'UNKNOWN')
                    entry = btc_setup.get('entry_price', 0)
                    sl = btc_setup.get('stop_loss', 0)
                    tp = btc_setup.get('take_profit', 0)
                    ml_score = btc_setup.get('ml_score', 0)
                    
                    dir_emoji = "🔴" if direction == "SHORT" else "🟢"
                    
                    message = f"""<b>₿ BTCUSD QUICK ANALYSIS</b>
──────────────────

<b>🎯 Active Setup:</b> {dir_emoji} <b>{direction}</b>

📊 ML Score: <code>{ml_score}/100</code>
💰 Entry: <code>${entry:,.2f}</code>
⛔ Stop Loss: <code>${sl:,.2f}</code>
🎯 Take Profit: <code>${tp:,.2f}</code>

<b>📦 Key Levels:</b>
• 1H OB: <code>$70,023-$70,596</code>
• 4H OB: <code>$68,905-$69,328</code>
• Daily FVG: <code>$89,972-$97,442</code> (8.3% gap)

⚠️ <b>Status:</b> MONITORING - Wait for confirmation"""
                    
                    return message
            
            return "⚪ <b>BTCUSD - No Active Setup</b>\n\nNot currently in monitoring list."
            
        except Exception as e:
            logger.error(f"❌ BTCUSD command error: {e}")
            return f"❌ <b>Error:</b> {str(e)}"
    
    def handle_active_command(self):
        """Handle /active command - Show live open positions from cTrader"""
        try:
            trade_history_file = Path('trade_history.json')
            
            if not trade_history_file.exists():
                return "❌ <b>No trading data found!</b>\n\n<code>trade_history.json</code> missing. Make sure cTrader sync is running."
            
            with open(trade_history_file, 'r') as f:
                data = json.load(f)
            
            account = data.get('account', {})
            positions = data.get('open_positions', [])
            balance = account.get('balance', 0)
            equity = account.get('equity', 0)
            
            if not positions:
                return f"""<b>⚪ NO ACTIVE POSITIONS</b>
{UNIVERSAL_SEPARATOR}
💰 <b>Balance:</b> <code>${balance:,.2f}</code>
📊 <b>Equity:</b> <code>${equity:,.2f}</code>
{UNIVERSAL_SEPARATOR}
🔍 All positions closed - Waiting for new setups"""
            
            # Build vertical message
            message = f"""<b>🔵 LIVE POSITIONS</b>
{UNIVERSAL_SEPARATOR}
<b>📊 Active:</b> <code>{len(positions)}</code>
{UNIVERSAL_SEPARATOR}
"""
            
            total_floating_pl = 0
            
            for idx, pos in enumerate(positions, 1):
                symbol = pos.get('symbol', 'N/A')
                direction = pos.get('direction', 'N/A')
                entry = pos.get('entry_price', 0)
                profit = pos.get('profit', 0)
                
                # Direction emoji
                dir_emoji = "🟢" if direction == "BUY" else "🔴"
                
                # P/L vertical format
                if profit > 0:
                    pl_emoji = "🟢"
                    pl_text = f"+${profit:.2f}"
                elif profit < 0:
                    pl_emoji = "🔴"
                    pl_text = f"-${abs(profit):.2f}"
                else:
                    pl_emoji = "⚪"
                    pl_text = "$0.00"
                
                total_floating_pl += profit
                
                # Vertical layout - each detail on own line with spacing
                message += f"""{idx}. {dir_emoji} <b>{symbol}</b>
   💰 In: <code>{entry:.5f}</code>
   {pl_emoji} P/L: <code>{pl_text}</code>

"""
            
            # Portfolio summary - vertical for clarity
            pl_summary_emoji = "🟢" if total_floating_pl > 0 else ("🔴" if total_floating_pl < 0 else "⚪")
            pl_summary_text = f"+${total_floating_pl:.2f}" if total_floating_pl > 0 else f"-${abs(total_floating_pl):.2f}"
            roi = ((equity - balance) / balance * 100) if balance > 0 else 0
            
            # ✅ CRITICAL FIX by ФорексГод: Remove double signature
            # Signature is added automatically by send_message function
            message += f"""{UNIVERSAL_SEPARATOR}
💰 <b>Balance:</b> <code>${balance:,.2f}</code>
📈 <b>Equity:</b> <code>${equity:,.2f}</code>
🔥 <b>Total Profit:</b> <code>{pl_summary_text}</code>
📊 <b>ROI:</b> <code>{roi:+.1f}%</code>"""
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Active command error: {e}")
            return f"❌ <b>Error:</b> {str(e)}"
    
    def handle_killall_command(self) -> str:
        """
        V10.6 /killall — Emergency stop:
        1. Close ALL open positions via cTrader API
        2. Write deep_sleep_state.json for 24h
        3. Kill all trading process locks so watchdog pauses restarts
        4. Send LOCKED DOWN confirmation
        """
        try:
            sep = "────────────────"
            script_dir = Path(__file__).parent.resolve()
            report_lines = []

            # ── STEP 1: Close all positions via cTrader REST API ────────────
            closed_count = 0
            failed_symbols = []
            try:
                active_file = script_dir / 'active_positions.json'
                if active_file.exists():
                    with open(active_file, 'r') as f:
                        positions = json.load(f)
                    if isinstance(positions, dict):
                        all_pos = [p for plist in positions.values() for p in plist]
                    elif isinstance(positions, list):
                        all_pos = positions
                    else:
                        all_pos = []

                    ctrader_host = os.getenv('CTRADER_CBOT_HOST', 'http://localhost:5000')
                    for pos in all_pos:
                        pos_id = pos.get('position_id') or pos.get('id')
                        sym = pos.get('symbol', '?')
                        if pos_id:
                            try:
                                resp = requests.post(
                                    f"{ctrader_host}/close_position",
                                    json={'position_id': pos_id},
                                    timeout=5
                                )
                                if resp.status_code == 200:
                                    closed_count += 1
                                    report_lines.append(f"✅ Closed: <code>{sym}</code> (#{pos_id})")
                                else:
                                    failed_symbols.append(sym)
                                    report_lines.append(f"⚠️ Failed: <code>{sym}</code>")
                            except Exception:
                                failed_symbols.append(sym)
                                report_lines.append(f"⚠️ Timeout: <code>{sym}</code>")
            except Exception as e:
                report_lines.append(f"❌ Position close error: {e}")

            # ── STEP 2: Write deep_sleep_state.json (24h lockdown) ────────
            sleep_file = script_dir / 'data' / 'deep_sleep_state.json'
            sleep_file.parent.mkdir(parents=True, exist_ok=True)
            wake_time = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            sleep_state = {
                'reason': 'MANUAL_KILLALL — /killall command by operator',
                'wake_time': wake_time,
                'triggered_at': datetime.now(timezone.utc).isoformat(),
                'daily_loss_reached': True,
                'lockdown': True
            }
            with open(sleep_file, 'w') as f:
                json.dump(sleep_state, f, indent=2)
            report_lines.append(f"🛌 Deep Sleep written — wake at <code>{wake_time[:16]} UTC</code>")

            # ── STEP 3: Remove setup locks / monitoring setups ────────────
            mon_file = script_dir / 'monitoring_setups.json'
            if mon_file.exists():
                backup = mon_file.with_suffix('.killall_backup.json')
                mon_file.rename(backup)
                report_lines.append(f"📋 monitoring_setups.json cleared (backup saved)")

            # ── STEP 4: Build confirmation message ──────────────────
            status_emoji = "🔴" if failed_symbols else "🟢"
            report_text = "\n".join(report_lines) if report_lines else "No positions found."

            message = (
                f"🚨 <b>KILLALL EXECUTED</b> {status_emoji}\n\n"
                f"{sep}\n"
                f"🛑 Positions closed: <b>{closed_count}</b>\n"
                f"⚠️ Failed: <b>{len(failed_symbols)}</b>\n"
                f"🛌 Lockdown: <b>24h DEEP SLEEP</b>\n\n"
                f"{sep}\n"
                f"{report_text}\n\n"
                f"{sep}\n"
                f"⏰ Wake time: <code>{wake_time[:16]} UTC</code>\n"
                f"⚠️ <b>All trading HALTED. Use /resume to restart manually.</b>"
            )
            logger.warning(f"🚨 KILLALL executed: {closed_count} closed, {len(failed_symbols)} failed")
            return message

        except Exception as e:
            logger.error(f"❌ KILLALL error: {e}")
            return f"❌ <b>KILLALL ERROR:</b> {str(e)}"

    def handle_resume_command(self) -> str:
        """
        V10.6 /resume — Remove deep_sleep_state.json and unlock trading.
        Sends: 🔱 SYSTEM AWAKENED. BIAS SYNC STARTING...
        """
        try:
            script_dir = Path(__file__).parent.resolve()
            sleep_file = script_dir / 'data' / 'deep_sleep_state.json'

            if sleep_file.exists():
                sleep_file.unlink()
                msg = (
                    f"🔱 <b>SYSTEM AWAKENED</b>\n\n"
                    f"✅ Deep sleep cleared manually\n"
                    f"🔄 <b>BIAS SYNC STARTING...</b>\n"
                    f"⏰ Time: <code>{datetime.now(timezone.utc).strftime('%H:%M UTC')}</code>\n\n"
                    f"⚠️ Watchdog will restart all processes within 60s."
                )
            else:
                msg = (
                    f"✅ <b>SYSTEM ALREADY ACTIVE</b>\n\n"
                    f"No deep sleep state found.\n"
                    f"Trading is operational."
                )
            logger.info("🔱 /resume executed — deep sleep cleared")
            return msg

        except Exception as e:
            logger.error(f"❌ Resume error: {e}")
            return f"❌ <b>RESUME ERROR:</b> {str(e)}"

    def process_command(self, message_obj):
        """Process incoming command"""
        try:
            # Check authorization
            from_user = message_obj.get('from', {})
            user_id = from_user.get('id')
            
            if user_id != self.authorized_user_id:
                logger.warning(f"⚠️ Unauthorized command attempt from user {user_id}")
                return
            
            text = message_obj.get('text', '').strip()
            
            if not text.startswith('/'):
                return
            
            command = text.split()[0].lower()
            
            logger.info(f"📥 Processing command: {command}")
            
            # Route command
            if command == '/stats':
                response = self.handle_stats_command()
            elif command == '/monitoring':
                response = self.handle_monitoring_command()
            elif command == '/status':
                response = self.handle_status_command()
            elif command == '/btcusd':
                response = self.handle_btcusd_command()
            elif command == '/active':
                response = self.handle_active_command()
            elif command == '/killall':
                response = self.handle_killall_command()
            elif command == '/resume':
                response = self.handle_resume_command()
            elif command == '/help':
                response = (
                    f"<b>🎮 COMMAND CENTER V10.6</b>\n"
                    f"{UNIVERSAL_SEPARATOR}\n\n"
                    f"<b>Available Commands:</b>\n\n"
                    f"<code>/stats</code> — Daily trading statistics\n"
                    f"<code>/monitoring</code> — Active setup list\n"
                    f"<code>/status</code> — System health check\n"
                    f"<code>/active</code> — Live open positions\n"
                    f"<code>/btcusd</code> — Quick BTCUSD analysis\n"
                    f"<code>/killall</code> — 🚨 Close ALL positions + 24h lockdown\n"
                    f"<code>/resume</code> — 🔱 Wake from deep sleep + restart trading\n"
                    f"<code>/help</code> — Show this message"
                )
            else:
                response = f"❌ <b>Unknown command:</b> <code>{command}</code>\n\nUse <code>/help</code> for available commands."
            
            self.send_message(response)
            
        except Exception as e:
            logger.error(f"❌ Command processing error: {e}")
    
    def run(self):
        """Main loop - listen for commands"""
        logger.info("🎮 Command Center started - Listening for commands...")
        
        while True:
            try:
                updates = self.get_updates()
                
                for update in updates:
                    self.last_update_id = update.get('update_id', 0)
                    
                    message = update.get('message', {})
                    if message:
                        self.process_command(message)
                
                time.sleep(1)  # Small delay between checks
                
            except KeyboardInterrupt:
                logger.info("👋 Command Center shutting down...")
                break
            except Exception as e:
                logger.error(f"❌ Main loop error: {e}")
                time.sleep(5)


if __name__ == "__main__":
    # 🔒 PID LOCK - Prevent duplicate instances
    lock_file = Path("process_telegram_command_center.lock")
    if not acquire_pid_lock(lock_file):
        logger.error("🚫 DUPLICATE INSTANCE DETECTED - Exiting to prevent double notifications")
        sys.exit(1)
    
    # Register cleanup on exit
    atexit.register(release_pid_lock, lock_file)
    
    center = TelegramCommandCenter()
    center.run()
