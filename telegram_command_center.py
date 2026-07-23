#!/usr/bin/env python3
"""
🎮 TELEGRAM COMMAND CENTER V11.5
────────────────
🔱 AUTHORED BY ФорексГод 🔱
🏛️ Глитч Ин Матрикс 🏛️

Interactive Command Interface:
- /stats    - Daily trading statistics
- /monitoring - Active setup list
- /status  - System monitors health check
- /btcusd  - Quick BTCUSD analysis
- /news    - Next 3 High Impact events this week
- /rates   - Central Bank rates + carry pairs
────────────────
[V11.5] PID Lock singleton, /news, /rates
"""

# Windows VPS fix: force UTF-8 stdout to prevent UnicodeEncodeError on emoji
import sys as _sys, io as _io
if hasattr(_sys.stdout, 'buffer'):
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(_sys.stderr, 'buffer'):
    _sys.stderr = _io.TextIOWrapper(_sys.stderr.buffer, encoding='utf-8', errors='replace')

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

from telegram_command_format import (
    SLIM_FOOTER_SEP,
    append_slim_footer,
    format_btcusd_card,
    format_stat_block,
    format_two_column_grid,
    load_monitoring_json,
    save_monitoring_json,
    section_header,
)

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
UNIVERSAL_SEPARATOR = "────────────────"


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
                    cmdline = ' '.join(proc.cmdline() or [])
                    # Verify it's the same script (not PID reuse)
                    if 'telegram_command_center' in cmdline:
                        logger.error(f"❌ Command Center already running (PID {old_pid})")
                        logger.error("⚠️  Cannot start duplicate instance - exiting")
                        return False
                    # Windows VPS: minimized/detached python often has cmdline=[] — still block duplicate
                    if os.name == 'nt' and not cmdline:
                        pname = (proc.name() or '').lower()
                        if 'python' in pname:
                            logger.error(
                                f"❌ Command Center already running (PID {old_pid}, cmdline hidden)"
                            )
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
        # ── V11.5 ACCESS CONTROL ──────────────────────────────────────────
        # ADMIN_ID = ID-ul tău Telegram — singurul cu acces la comenzile critice
        self.admin_id = self.authorized_user_id
        # Comenzi PUBLIC — oricine din grup poate folosi
        self.PUBLIC_COMMANDS = {'/monitoring', '/stats', '/weekly', '/help', '/status', '/news', '/rates', '/btcusd'}
        # Comenzi ADMIN ONLY — restricționate strict
        self.ADMIN_COMMANDS  = {'/killall', '/resume', '/active'}
        
        # V8.1: Path alignment — resolve relative to script location, not CWD
        script_dir = Path(__file__).parent.resolve()
        self.db_path = script_dir / 'data' / 'trades.db'
        self.monitoring_file = script_dir / 'monitoring_setups.json'
        self.active_positions_file = script_dir / 'active_positions.json'
        
        self._offset_file = script_dir / 'data' / 'tg_last_update_id.json'
        self.last_update_id = self._load_update_id()
        
        logger.info("🎮 Telegram Command Center V3.7 initialized")
        logger.info(f"🔐 Authorized User ID: {self.authorized_user_id}")
        logger.info(f"📁 Monitoring file: {self.monitoring_file}")
        if not self.bot_token:
            logger.error("❌ TELEGRAM_BOT_TOKEN lipsă din .env — comenzile Telegram NU vor funcționa")
        if not self.chat_id:
            logger.warning("⚠️ TELEGRAM_CHAT_ID lipsă — sendMessage va eșua")
    
    def _load_update_id(self) -> int:
        """Load last processed update_id from disk (prevents re-processing on restart)"""
        try:
            if self._offset_file.exists():
                with open(self._offset_file, 'r') as f:
                    data = json.load(f)
                uid = int(data.get('last_update_id', 0))
                logger.info(f"📂 Resumed from update_id={uid} (no duplicate commands on restart)")
                return uid
        except Exception as e:
            logger.warning(f"Could not load update_id from disk: {e}")
        return 0

    def _ensure_polling_mode(self) -> None:
        """Asigură long-polling (deleteWebhook) — altfel getUpdates nu primește comenzi."""
        if not self.bot_token:
            return
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/deleteWebhook"
            response = requests.get(url, params={'drop_pending_updates': 'false'}, timeout=15)
            if response.status_code == 200 and response.json().get('ok'):
                logger.info("✅ Telegram polling mode (webhook dezactivat)")
            else:
                logger.warning(f"⚠️ deleteWebhook: {response.text[:200]}")
        except Exception as e:
            logger.warning(f"⚠️ deleteWebhook failed: {e}")

    def _save_update_id(self, update_id: int):
        """Persist last_update_id to disk immediately"""
        try:
            self._offset_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._offset_file, 'w') as f:
                json.dump({'last_update_id': update_id}, f)
        except Exception as e:
            logger.warning(f"Could not save update_id: {e}")

    def get_updates(self):
        """Get new messages from Telegram"""
        if not self.bot_token:
            logger.error("❌ TELEGRAM_BOT_TOKEN lipsă — getUpdates oprit")
            return []
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {'offset': self.last_update_id + 1, 'timeout': 30}
            
            response = requests.get(url, params=params, timeout=35)
            if response.status_code != 200:
                body = response.text[:300]
                logger.error(f"❌ getUpdates HTTP {response.status_code}: {body}")
                if response.status_code == 409:
                    logger.error(
                        "❌ getUpdates 409 CONFLICT — alt proces face polling pe același bot. "
                        "Oprește duplicatele telegram_command_center.py"
                    )
                return []
            data = response.json()
            if not data.get('ok'):
                logger.error(f"❌ getUpdates API error: {data.get('description', data)}")
                return []
            results = data.get('result', [])
            if results:
                logger.debug(f"📥 getUpdates: {len(results)} update(s), offset>{self.last_update_id}")
            return results
        except Exception as e:
            logger.error(f"❌ Error getting updates: {e}")
        
        return []
    
    def force_sync_from_ctrader(self):
        """
        🔄 FORCE SYNC - Fetch fresh data from cTrader before showing stats
        V40.4: delegates to trade_manager.refresh_account_balance()
        """
        try:
            logger.info("🔄 Force syncing from cTrader...")
            from trade_manager import TradeManager
            ok = TradeManager(Path(__file__).parent.resolve()).refresh_account_balance()
            if ok:
                logger.success("✅ Force sync complete - data is fresh!")
            return ok
        except Exception as e:
            logger.error(f"❌ Force sync error: {e}")
            return False
    
    def send_message(self, text: str, chat_id=None, add_signature: bool = True):
        """Send message to Telegram with HTML formatting"""
        target_chat = chat_id if chat_id is not None else self.chat_id
        if not target_chat:
            logger.error("❌ sendMessage: chat_id lipsă")
            return False
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            branded_text = append_slim_footer(text) if add_signature else text.rstrip()
            # Telegram hard limit 4096 chars
            if len(branded_text) > 4096:
                branded_text = branded_text[:4080] + "\n\n… [truncat]"
            
            payload = {
                'chat_id': target_chat,
                'text': branded_text,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(
                    f"❌ sendMessage HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )
                return False
            return True
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}")
            return False
    
    def handle_stats_command(self):
        """📊 Handle /stats command - Show today's trading statistics (COMPACT VERTICAL)"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

            # ── Read from trade_history.json (live cBot data) ──
            trade_history_file = Path(__file__).parent.resolve() / 'trade_history.json'
            total_trades = wins = losses = 0
            total_profit = avg_profit = 0.0
            weekly_profit = 0.0
            weekly_trades = 0

            if trade_history_file.exists():
                with open(trade_history_file, 'r', encoding='utf-8') as f:
                    th = json.load(f)
                for trade in th.get('closed_trades', []):
                    ct = trade.get('close_time', '')
                    profit = float(trade.get('profit', 0))
                    if ct and ct[:10] == today:
                        total_trades += 1
                        total_profit += profit
                        if profit > 0:
                            wins += 1
                        else:
                            losses += 1
                    if ct and ct[:10] >= week_ago:
                        weekly_profit += profit
                        weekly_trades += 1
                avg_profit = (total_profit / total_trades) if total_trades > 0 else 0.0
            else:
                # Fallback to SQLite
                self.force_sync_from_ctrader()
                if not self.db_path.exists():
                    return "❌ <b>Database not found!</b>\n\n<code>trades.db</code> missing."
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*),
                           SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END),
                           SUM(profit), AVG(profit)
                    FROM closed_trades WHERE DATE(close_time, 'localtime') = ?
                """, (today,))
                row = cursor.fetchone()
                total_trades = row[0] or 0
                wins = row[1] or 0
                total_profit = row[2] or 0
                avg_profit = row[3] or 0
                losses = total_trades - wins
                cursor.execute("""
                    SELECT SUM(profit), COUNT(*) FROM closed_trades
                    WHERE DATE(close_time, 'localtime') >= ?
                """, (week_ago,))
                row = cursor.fetchone()
                weekly_profit = row[0] or 0
                weekly_trades = row[1] or 0
                conn.close()
            
            # Emoji based on profit
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            profit_emoji = "🔥" if total_profit > 0 else ("💥" if total_profit < 0 else "⚪")
            weekly_emoji = "🔥" if weekly_profit > 0 else ("💥" if weekly_profit < 0 else "⚪")

            # V63 compact hibrid RO
            date_str = datetime.now().strftime('%d %b %Y')
            message = (
                f"<b>📊 Stats · {date_str}</b>\n"
                f"{SLIM_FOOTER_SEP}\n\n"
                f"{format_stat_block('P/L azi', f'${total_profit:+.2f}', profit_emoji)}\n\n"
                f"📈 <b>Tranzacții</b> · <code>{total_trades}</code>\n"
                f"✅ <code>{wins}</code> · ❌ <code>{losses}</code> · "
                f"WR <code>{win_rate:.1f}%</code>\n"
                f"💵 Medie · <code>${avg_profit:+.2f}</code>\n\n"
                f"{section_header('📈 Săptămână (7z)')}\n\n"
                f"{format_stat_block('Profit', f'${weekly_profit:+.2f}', weekly_emoji)}\n"
                f"📋 Tranzacții · <code>{weekly_trades}</code>"
            )

            return message
            
        except Exception as e:
            logger.error(f"❌ Stats command error: {e}")
            return f"❌ <b>Error:</b> {str(e)}"

    def handle_weekly_command(self):
        """📈 Handle /weekly command - Show full weekly trading report (last 7 days)"""
        try:
            from trade_manager import TradeManager

            week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            week_start = (datetime.now() - timedelta(days=7)).strftime('%d %b')
            week_end = datetime.now().strftime('%d %b %Y')

            weekly = TradeManager(Path(__file__).parent.resolve()).get_weekly_pnl(week_ago)
            total = weekly['total']
            wins = weekly['wins']
            losses = weekly['losses']
            total_pnl = weekly['total_pnl']
            best_trade = weekly['best_trade']
            worst_trade = weekly['worst_trade']

            win_rate = (wins / total * 100) if total > 0 else 0
            avg_pnl = (total_pnl / total) if total > 0 else 0.0
            pnl_emoji = "🔥" if total_pnl > 0 else ("💥" if total_pnl < 0 else "⚪")
            wr_emoji = "✅" if win_rate >= 50 else "⚠️"

            message = (
                f"<b>📈 Raport săptămânal</b>\n"
                f"{SLIM_FOOTER_SEP}\n"
                f"📅 <b>{week_start} — {week_end}</b>\n\n"
                f"{format_stat_block('P/L total', f'${total_pnl:+.2f}', pnl_emoji)}\n\n"
                f"📋 Tranzacții · <code>{total}</code>\n"
                f"✅ <code>{wins}</code> · ❌ <code>{losses}</code>\n"
                f"{wr_emoji} Win rate · <code>{win_rate:.1f}%</code>\n"
                f"💵 Medie/trade · <code>${avg_pnl:+.2f}</code>"
            )
            if best_trade is not None:
                message += (
                    f"\n\n🏆 Best · <code>${best_trade:+.2f}</code>\n"
                    f"💣 Worst · <code>${worst_trade:+.2f}</code>"
                )
            return message

        except Exception as e:
            logger.error(f"❌ Weekly command error: {e}")
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
            
            with open(self.active_positions_file, 'r', encoding='utf-8') as f:
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
                data, _ = load_monitoring_json(self.monitoring_file)
                data['setups'] = setups
                save_monitoring_json(self.monitoring_file, data)
                logger.success(f"🧹 Auto-expired {expired_count} stale setup(s) from monitoring_setups.json")
            except Exception as e:
                logger.error(f"❌ Failed to save expired setups: {e}")
        
        return expired_count

    def handle_monitoring_command(self):
        """
        V37.17: /monitoring — setup-uri în pândă (JSON + radar).
        Poziții live la broker → folosește /active
        """
        _WATCHING = frozenset({
            'MONITORING', 'READY', 'WAITING_D1_PULLBACK',
            'WAITING_4H_CHOCH', 'WAITING_4H_PULLBACK',
            'WAITING_W_D_SYNC', 'WAITING_W_ZONE',
            'WAITING_POSITION_CLOSE',
        })

        try:
            if not self.monitoring_file.exists():
                return "❌ <b>Fără setup-uri!</b>\n\n<code>monitoring_setups.json</code> lipsește."

            _, setups = load_monitoring_json(self.monitoring_file)

            broker = self._load_broker_positions()
            broker_symbols = set(broker.keys())
            total_broker = sum(len(v) for v in broker.values())
            expired_count = self._expire_stale_actives(setups, broker_symbols)

            watching = [s for s in setups if s.get('status') in _WATCHING]
            trade_open = [s for s in setups if s.get('status') == 'TRADE_OPEN']
            desync_setups = [
                s for s in setups
                if s.get('status') == 'ACTIVE' and s.get('symbol') not in broker_symbols
            ]
            execute_now = [s for s in watching if s.get('EXECUTE_NOW')]

            if not watching and not broker_symbols:
                return (
                    "⚪ <b>Nicio pândă activă</b>\n\n"
                    "Nu există setup-uri în <code>monitoring_setups.json</code> "
                    "și nici poziții la broker.\n"
                    "Așteptăm următorul scan sau semnal radar."
                )

            from telegram_notifier import _render_grouped_setups

            message = (
                f"<b>👁️ Setup-uri în pândă</b>\n"
                f"{SLIM_FOOTER_SEP}\n\n"
                f"📋 Total · <b>{len(watching)}</b>"
            )
            if execute_now:
                message += f" · 🔥 EXECUTE_NOW · <b>{len(execute_now)}</b>"
            if trade_open:
                message += f" · 📂 TRADE_OPEN · <b>{len(trade_open)}</b>"
            message += "\n"

            if total_broker:
                message += (
                    f"\n💡 Live broker · <b>{total_broker}</b> poziții → <code>/active</code>\n"
                )

            if watching:
                watching_sorted = sorted(
                    watching,
                    key=lambda x: (0 if x.get('EXECUTE_NOW') else 1, x.get('symbol', '')),
                )
                message += f"\n{section_header('📡 Radar / Scanner')}\n\n"
                message += _render_grouped_setups(watching_sorted[:15])
                if len(watching) > 15:
                    message += f"\n<i>… + {len(watching) - 15} setup-uri</i>\n"
            elif total_broker:
                message += (
                    f"\n<i>Niciun setup în pândă — <code>/status</code> pentru health.</i>\n"
                )

            if desync_setups:
                message += f"\n{section_header('⚠️ Desync')}\n"
                message += "<i>ACTIVE în JSON, lipsă la broker</i>\n\n"
                for setup in desync_setups:
                    sym = setup.get('symbol', '?')
                    dr = setup.get('direction', '?').upper()
                    message += f"   ⚠️ <code>{sym}</code> {dr}\n"
                message += "\n"

            if expired_count:
                message += f"🧹 Auto-expired ghost ACTIVE: <code>{expired_count}</code>\n"

            return message
            
        except Exception as e:
            logger.error(f"❌ Monitoring command error: {e}")
            return f"❌ <b>Error:</b> {str(e)}"

    def _status_ro_today(self) -> str:
        """Data curentă în timezone România (pentru P/L și rejections)."""
        try:
            import pytz as _pytz
            return datetime.now(_pytz.timezone('Europe/Bucharest')).strftime('%Y-%m-%d')
        except Exception:
            return (datetime.now(timezone.utc) + timedelta(hours=3)).strftime('%Y-%m-%d')

    def _status_resumed_today(self) -> bool:
        """True dacă /resume a fost folosit azi (UTC date, ca executorul)."""
        try:
            resume_file = Path(__file__).parent.resolve() / 'data' / 'system_resumed.json'
            if resume_file.exists():
                rm = json.loads(resume_file.read_text(encoding='utf-8'))
                resumed_at = datetime.fromisoformat(rm.get('resumed_at', ''))
                if resumed_at.date() == datetime.now(timezone.utc).date():
                    return True
        except Exception:
            pass
        return False

    def get_today_pnl(self) -> dict:
        """V40.4: Broker-first today's P/L (cTrader history_deals via trade_manager)."""
        return self._status_daily_pnl()

    def _status_daily_pnl(self) -> dict:
        """
        V40.4 + V44.2: P/L pentru /status — sursă cTrader (8767).
        Calendar (00:00 RO → acum) + session (de la /resume) când există reset_cutoff.
        """
        script_dir = Path(__file__).parent.resolve()
        today = self._status_ro_today()
        reset_cutoff = None
        starting_balance = 0.0

        daily_state_file = script_dir / 'data' / 'daily_state.json'
        if daily_state_file.exists():
            try:
                state = json.loads(daily_state_file.read_text(encoding='utf-8'))
                ts = state.get('reset_timestamp') or state.get('manual_resume_at')
                if ts:
                    try:
                        import pytz as _pytz
                        _ro_tz = _pytz.timezone('Europe/Bucharest')
                        reset_dt = datetime.fromisoformat(ts)
                        if reset_dt.tzinfo is None:
                            reset_dt = reset_dt.replace(tzinfo=timezone.utc)
                        if reset_dt.astimezone(_ro_tz).strftime('%Y-%m-%d') == today:
                            reset_cutoff = ts
                    except Exception:
                        reset_cutoff = ts
                if state.get('date') == today or reset_cutoff:
                    starting_balance = float(state.get('starting_balance') or 0)
            except Exception:
                pass

        from trade_manager import TradeManager
        tm = TradeManager(script_dir)
        pnl = tm.get_today_pnl(
            today=today,
            reset_cutoff=reset_cutoff,
            starting_balance=starting_balance,
            calendar_day_pnl=True,
        )
        closed_pnl = pnl['closed_pnl']
        trade_count = pnl['trade_count']
        balance = pnl['balance']
        pnl_pct = pnl['pnl_pct']
        broker_synced = pnl.get('broker_synced', False)

        session_closed_pnl = closed_pnl
        session_trade_count = trade_count
        session_pnl_pct = pnl_pct
        if reset_cutoff:
            session = tm.get_today_pnl(
                today=today,
                reset_cutoff=reset_cutoff,
                starting_balance=starting_balance,
                calendar_day_pnl=False,
            )
            session_closed_pnl = session['closed_pnl']
            session_trade_count = session['trade_count']
            session_pnl_pct = session['pnl_pct']

        max_loss = 10.0
        try:
            config_file = script_dir / 'SUPER_CONFIG.json'
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    sc = json.load(f)
                max_loss = sc.get('daily_limits', {}).get('max_daily_loss_percent', 10.0)
        except Exception:
            pass

        resumed_today = self._status_resumed_today()
        risk_pnl_pct = session_pnl_pct if reset_cutoff else pnl_pct
        if reset_cutoff and resumed_today:
            if risk_pnl_pct >= 0:
                risk_label = f'🔱 RESUME ACTIVE — session {risk_pnl_pct:+.1f}%'
            elif risk_pnl_pct > -max_loss:
                risk_label = f'🔱 RESUME ACTIVE — session {risk_pnl_pct:+.1f}%'
            else:
                risk_label = f'🔴 SESSION LIMIT ({risk_pnl_pct:+.1f}%)'
        elif risk_pnl_pct >= 0:
            risk_label = '🟢 SAFE'
        elif risk_pnl_pct > -max_loss:
            risk_label = f'🟡 CAUTION ({risk_pnl_pct:+.1f}%)'
        else:
            risk_label = f'🔴 LIMIT HIT ({risk_pnl_pct:+.1f}%)'

        return {
            'closed_pnl': closed_pnl,
            'trade_count': trade_count,
            'pnl_pct': pnl_pct,
            'session_closed_pnl': session_closed_pnl,
            'session_trade_count': session_trade_count,
            'session_pnl_pct': session_pnl_pct,
            'risk_pnl_pct': risk_pnl_pct,
            'balance': balance,
            'starting_balance': starting_balance,
            'max_loss': max_loss,
            'risk_label': risk_label,
            'resumed_today': resumed_today,
            'reset_cutoff': reset_cutoff,
            'broker_synced': broker_synced,
        }

    _STATUS_WATCHING_STATUSES = frozenset({
        'MONITORING', 'READY', 'ACTIVE', 'WAITING_D1_PULLBACK',
        'WAITING_4H_CHOCH', 'WAITING_4H_PULLBACK',
        'WAITING_W_D_SYNC', 'WAITING_W_ZONE',
        'WAITING_POSITION_CLOSE',
    })

    def handle_status_command(self):
        """
        /status DASHBOARD — Full system health + P/L + Deep Sleep + Rejections + News
        ФорексГод — Глитч Ин Матрикс
        """
        try:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            # V19.6.9: Afișează ora României în header-ul /status
            try:
                import pytz as _pytz_hdr
                _ro_tz_hdr = _pytz_hdr.timezone('Europe/Bucharest')
                _now_ro_hdr = now.astimezone(_ro_tz_hdr)
                _time_header = _now_ro_hdr.strftime('%d %b %Y, %H:%M:%S (ora României)')
            except Exception:
                _time_header = (now + timedelta(hours=3)).strftime('%d %b %Y, %H:%M:%S (ora României)')

            message = (
                f"<b>🔧 System Status</b>\n"
                f"{SLIM_FOOTER_SEP}\n"
                f"⏰ {_time_header}\n\n"
            )
            
            # ═══ SECTION 1: MONITORS (grid 2 coloane) ═══
            message += f"{section_header('📊 Monitoare')}\n\n"
            
            processes = {
                'setup_executor_monitor.py': '🎯 Executor',
                'position_monitor.py': '📊 Positions',
                'telegram_command_center.py': '🎮 Telegram',
                'watchdog_monitor.py': '🛡️ Watchdog',
                'ctrader_sync_daemon.py': '📡 Sync',
                'news_calendar_monitor.py': '📅 News Calendar',
                'news_reminder_engine.py': '🔔 News Alerts',
                'auto_scanner_daemon.py': '🔍 Auto Scanner',
                'dashboard_server.py': '🌐 Dashboard',
                'multi_tf_radar.py': '📡 Multi-TF Radar',
            }
            
            # V10.5 FIX: On Windows, psutil cannot read cmdline of Hidden processes
            # (started with -WindowStyle Hidden → cmdline=[]).
            # Use wmic on Windows — reads ALL processes regardless of visibility.
            running_procs = {}

            def _get_running_procs_windows():
                """wmic reads cmdlines of ALL processes including hidden ones"""
                result = {}
                try:
                    import subprocess as _sp
                    out = _sp.run(
                        ['wmic', 'process', 'where', 'name="python.exe"',
                         'get', 'ProcessId,CommandLine', '/format:csv'],
                        capture_output=True, text=True, timeout=10,
                        encoding='utf-8', errors='replace'
                    )
                    for line in out.stdout.splitlines():
                        line = line.strip()
                        if not line or line.startswith('Node'):
                            continue
                        parts = line.split(',', 2)
                        if len(parts) < 3:
                            continue
                        cmdline_str = parts[1]
                        try:
                            pid = int(parts[2])
                        except ValueError:
                            continue
                        for proc_name in processes:
                            if proc_name in cmdline_str and proc_name not in result:
                                try:
                                    result[proc_name] = psutil.Process(pid).create_time()
                                except Exception:
                                    result[proc_name] = time.time()
                except Exception:
                    pass
                return result

            if os.name == 'nt':  # Windows VPS
                running_procs = _get_running_procs_windows()

            if not running_procs:  # fallback: psutil (Linux/Mac or wmic failed)
                try:
                    for proc in psutil.process_iter(['pid', 'cmdline', 'create_time']):
                        try:
                            cmdline = ' '.join(proc.info['cmdline'] or [])
                            for proc_name in processes:
                                if proc_name in cmdline and proc_name not in running_procs:
                                    running_procs[proc_name] = proc.info['create_time']
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                except Exception:
                    pass

            online_count = 0
            total_count = len(processes)
            monitor_cells = []
            for proc_name, display_name in processes.items():
                if proc_name in running_procs:
                    uptime_str = ''
                    try:
                        age_s = time.time() - running_procs[proc_name]
                        if age_s >= 86400:
                            uptime_str = f" ({age_s/86400:.0f}d)"
                        elif age_s >= 3600:
                            uptime_str = f" ({age_s/3600:.0f}h)"
                        else:
                            uptime_str = f" ({age_s/60:.0f}m)"
                    except Exception:
                        pass
                    monitor_cells.append(f"{display_name} ✅{uptime_str}")
                    online_count += 1
                else:
                    monitor_cells.append(f"{display_name} ❌")
            message += format_two_column_grid(monitor_cells, cols=2)
            message += f"\n  <i>{online_count}/{total_count} online</i>\n\n"
            
            # ═══ SECTION 2: CONNECTIONS ═══
            message += f"{section_header('📡 Conexiuni')}\n\n"
            try:
                resp = requests.get('http://localhost:8767/', timeout=3)
                cbot_status = '✅' if resp.status_code == 200 else '⚠️'
            except Exception:
                cbot_status = '❌'
            message += f"  🤖 cBot {cbot_status}    💾 DB {'✅' if self.db_path.exists() else '❌'}\n\n"
            
            # ═══ SECTION 3: TODAY'S P/L (o linie — fără duplicat session/calendar) ═══
            message += f"{section_header('💰 P/L azi')}\n\n"
            pnl_ctx = {
                'closed_pnl': 0.0, 'trade_count': 0, 'pnl_pct': 0.0,
                'max_loss': 10.0, 'risk_label': '🟢 SAFE', 'resumed_today': False,
            }
            try:
                pnl_ctx = self._status_daily_pnl()
                closed_pnl = pnl_ctx['closed_pnl']
                trade_count = pnl_ctx['trade_count']
                pnl_pct = pnl_ctx['pnl_pct']
                max_loss = pnl_ctx['max_loss']
                reset_cutoff = pnl_ctx.get('reset_cutoff')

                if reset_cutoff and pnl_ctx.get('resumed_today'):
                    sess_pnl = pnl_ctx['session_closed_pnl']
                    sess_pct = pnl_ctx['session_pnl_pct']
                    sess_trades = pnl_ctx['session_trade_count']
                    sess_emoji = '🟢' if sess_pnl >= 0 else '🔴'
                    message += (
                        f"  🔱 Session {sess_emoji} <code>${sess_pnl:+.2f}</code> "
                        f"({sess_pct:+.1f}%) · <code>{sess_trades}</code> trade(s)\n"
                    )
                else:
                    pnl_emoji = '🟢' if closed_pnl >= 0 else '🔴'
                    message += (
                        f"  {pnl_emoji} <code>${closed_pnl:+.2f}</code> "
                        f"({pnl_pct:+.1f}%) · <code>{trade_count}</code> trade(s)\n"
                    )

                if pnl_ctx.get('broker_synced'):
                    message += "  📡 <code>cTrader synced</code>\n"
                message += f"  🛡️ {pnl_ctx['risk_label']} (limit −{max_loss}%)\n\n"

            except Exception as e:
                message += f"  ⚠️ Data unavailable: {e}\n\n"
            
            # ═══ SECTION 4: MONITORING SETUPS (grouped V60) ═══
            message += f"{section_header('📋 Setup-uri')}\n\n"
            try:
                from telegram_notifier import _render_grouped_setups

                script_dir = Path(__file__).parent.resolve()
                mon_file = script_dir / 'monitoring_setups.json'
                if mon_file.exists():
                    _, setups = load_monitoring_json(mon_file)
                    active = sum(1 for s in setups if s.get('status') == 'TRADE_OPEN')
                    watching = self._STATUS_WATCHING_STATUSES
                    monitoring = sum(1 for s in setups if s.get('status') in watching)
                    choch_waiting = sum(
                        1 for s in setups
                        if s.get('status') in watching
                        and not s.get('radar_4h_choch_detected')
                    )
                    in_zone = sum(
                        1 for s in setups
                        if s.get('status') in watching
                        and (
                            s.get('radar_4h_in_fvg')
                            or (
                                s.get('radar_4h_choch_detected')
                                and not s.get('EXECUTE_NOW')
                            )
                        )
                    )
                    message += (
                        f"  🔥 Open <code>{active}</code> · 👀 Pândă <code>{monitoring}</code>\n"
                        f"  ⏳ CHoCH wait <code>{choch_waiting}</code> · 🎯 In zone <code>{in_zone}</code>\n\n"
                    )
                    mon_syms = [s for s in setups if s.get('status') in self._STATUS_WATCHING_STATUSES]
                    if mon_syms:
                        message += _render_grouped_setups(mon_syms[:12])
                        if len(mon_syms) > 12:
                            message += f"\n<i>+ {len(mon_syms) - 12} setup-uri</i>\n"
                    message += "\n"
                else:
                    message += "  ⚠️ Fișier monitoring lipsă\n\n"
            except Exception:
                message += "  ⚠️ Eroare citire setup-uri\n\n"
            
            # ═══ SECTION 5: DEEP SLEEP STATUS ═══
            message += f"{section_header('😴 Deep Sleep')}\n\n"
            try:
                sleep_file = Path(__file__).parent.resolve() / 'data' / 'deep_sleep_state.json'
                if sleep_file.exists():
                    with open(sleep_file, 'r') as f:
                        sleep_state = json.load(f)
                    wake_str = sleep_state.get('wake_time', '')
                    stored_reason = sleep_state.get('reason', 'Unknown')
                    # V19.6.4 FIX: sanitizează reason-ul stocat — poate conține % greşit
                    # (ex: -4358% din bug-ul balance=1 în V19.6.2)
                    # Înlocuim cu P/L real deja calculat în Section 3
                    import re as _re
                    _pct_match = _re.search(r'\(([\-\d\.]+)%\)', stored_reason)
                    if _pct_match:
                        _stored_pct = float(_pct_match.group(1))
                        # Dacă procentul stocat e aberant (>100% sau <-100%), înlocuim cu real
                        if abs(_stored_pct) > 100:
                            _real_reason = (
                                f"Daily loss limit reached ({pnl_ctx.get('pnl_pct', 0):+.1f}%) — auto Deep Sleep"
                            )
                        else:
                            _real_reason = stored_reason
                    else:
                        _real_reason = stored_reason
                    if wake_str:
                        wake_time_raw = datetime.fromisoformat(wake_str)
                        # V19.6.7 FIX: RECALCULĂM wake_time la 00:05 RO — nu ne încredem
                        # în valoarea stocată (poate fi veche, scrisă de cod UTC-based)
                        try:
                            import pytz as _pytz
                            _ro_tz = _pytz.timezone('Europe/Bucharest')
                            _now_ro = datetime.now(_ro_tz)
                            _target_ro = _now_ro.replace(hour=0, minute=5, second=0, microsecond=0)
                            if _now_ro >= _target_ro:
                                _target_ro = _target_ro + timedelta(days=1)
                            wake_time = _target_ro.astimezone(timezone.utc)
                            wake_display = _target_ro.strftime('%H:%M (ora României)')
                        except Exception:
                            # Fallback: UTC+3
                            _ro_off = timedelta(hours=3)
                            _now_ro_n = now + _ro_off
                            _tgt = _now_ro_n.replace(hour=0, minute=5, second=0, microsecond=0)
                            if _now_ro_n >= _tgt:
                                _tgt = _tgt + timedelta(days=1)
                            wake_time = (_tgt - _ro_off).replace(tzinfo=timezone.utc)
                            wake_display = '00:05 (ora României)'
                        if wake_time > now:
                            remaining_h = (wake_time - now).total_seconds() / 3600
                            message += f"  🔴 <b>SLEEPING</b> — {remaining_h:.1f}h remaining\n"
                            message += f"  Reason: <i>{_real_reason}</i>\n"
                            message += f"  Wake: <code>{wake_display}</code>\n\n"
                        else:
                            message += "  ✅ ACTIVE (sleep expired)\n\n"
                    else:
                        message += "  ✅ ACTIVE\n\n"
                else:
                    # V19.6.2: Fallback — dacă fișierul nu există dar P/L arată LIMIT HIT
                    # (executor vechi nu a scris fișierul, dar știm că limita e atinsă)
                    try:
                        _pnl_pct_check = pnl_ctx.get('risk_pnl_pct', pnl_ctx.get('pnl_pct', 0))
                        _max_loss_check = pnl_ctx.get('max_loss', 10.0)
                        _resumed_today = pnl_ctx.get('resumed_today', False) or self._status_resumed_today()
                        if _pnl_pct_check <= -_max_loss_check and not _resumed_today:
                            message += f"  🔴 <b>SLEEPING</b> — Daily loss limit atins ({_pnl_pct_check:+.1f}%)\n"
                            message += f"  Reason: <i>Daily loss limit reached (auto-detected)</i>\n"
                            message += f"  ⚠️ <i>deep_sleep_state.json lipsă — restart executor pentru sync</i>\n\n"
                        else:
                            message += "  ✅ ACTIVE — scanning normally\n\n"
                    except NameError:
                        message += "  ✅ ACTIVE — scanning normally\n\n"
            except Exception:
                message += "  ✅ ACTIVE\n\n"
            
            # ═══ SECTION 6: RISK REJECTIONS TODAY ═══
            message += f"{section_header('⛔ Rejections azi')}\n\n"
            try:
                rej_file = Path(__file__).parent.resolve() / 'data' / 'daily_rejections.json'
                if rej_file.exists():
                    with open(rej_file, 'r') as f:
                        rej_data = json.load(f)
                    # V19.6.10: data României pentru rejections
                    try:
                        import pytz as _pytz_rj
                        _ro_tz_rj = _pytz_rj.timezone('Europe/Bucharest')
                        today_str = datetime.now(_ro_tz_rj).strftime('%Y-%m-%d')
                    except Exception:
                        today_str = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime('%Y-%m-%d')
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
                    # V19.6.2: Fallback — dacă fișierul nu există dar P/L arată LIMIT HIT
                    # afișăm cel puțin că există rejecții legate de daily loss
                    try:
                        _risk_pct = pnl_ctx.get('risk_pnl_pct', pnl_ctx.get('pnl_pct', 0))
                        _resumed = pnl_ctx.get('resumed_today', False)
                        if _risk_pct <= -pnl_ctx.get('max_loss', 10.0) and not _resumed:
                            message += f"  ⚠️ <i>Rejecții detectate via P/L (fișier lipsă)\n"
                            message += f"  • Daily Loss Limit: <code>≥1</code> (trade respins la {_risk_pct:+.1f}%)\n"
                            message += f"  ℹ️ Restart executor pentru tracking complet</i>\n\n"
                        else:
                            message += "  <code>0</code> (clean day)\n\n"
                    except Exception:
                        message += "  <code>0</code> (clean day)\n\n"
            except Exception:
                message += "  ⚠️ Data unavailable\n\n"
            
            # ═══ SECTION 7: NEXT AUTO SCAN ═══
            message += f"{section_header('🤖 Următorul scan')}\n\n"
            try:
                SCAN_DAYS = {0, 2, 4}  # Mon=0, Wed=2, Fri=4
                SCAN_HOUR_UTC = 5      # 07:00 Bucharest = 05:00 UTC (summer) / 06:00 UTC (winter)
                days_ro = {0: 'Luni', 1: 'Marți', 2: 'Miercuri', 3: 'Joi', 4: 'Vineri', 5: 'Sâmbătă', 6: 'Duminică'}
                # Find next scan day
                next_scan_dt = None
                for offset in range(1, 8):
                    candidate = (now + timedelta(days=offset)).replace(hour=SCAN_HOUR_UTC, minute=0, second=0, microsecond=0)
                    if candidate.weekday() in SCAN_DAYS:
                        next_scan_dt = candidate
                        break
                # Also check today if scan hour not yet passed
                today_scan = now.replace(hour=SCAN_HOUR_UTC, minute=0, second=0, microsecond=0)
                if now.weekday() in SCAN_DAYS and now < today_scan:
                    next_scan_dt = today_scan
                if next_scan_dt:
                    remaining_scan = next_scan_dt - now
                    hours_left = remaining_scan.total_seconds() / 3600
                    day_name = days_ro[next_scan_dt.weekday()]
                    if hours_left < 24:
                        message += f"  📅 <b>{day_name}</b> <code>07:00 EET</code> — în <code>{hours_left:.1f}h</code>\n\n"
                    else:
                        days_left = hours_left / 24
                        message += f"  📅 <b>{day_name}</b> <code>07:00 EET</code> — în <code>{days_left:.1f} zile</code>\n\n"
                else:
                    message += "  ⚠️ Unknown\n\n"
            except Exception:
                message += "  ⚠️ Unknown\n\n"
            
            # ═══ SECTION 8: NEWS TODAY ═══
            message += f"{section_header('📰 News azi')}\n\n"
            try:
                from datetime import timezone as _tz
                news_file = Path(__file__).parent.resolve() / 'data' / 'upcoming_news.json'
                if news_file.exists():
                    with open(news_file, 'r') as f:
                        raw = json.load(f)
                    if isinstance(raw, list):
                        all_events = raw
                    elif isinstance(raw, dict):
                        all_events = raw.get('events', raw.get('data', []))
                    else:
                        all_events = []
                    now_utc = datetime.now(_tz.utc)
                    today_str = now_utc.strftime('%Y-%m-%d')
                    # ✅ V11.6 FIX: filter ALL future events (not just today) — so after today's news pass, show tomorrow's
                    future_events = []
                    for ev in all_events:
                        ev_datetime = ev.get('datetime', ev.get('datetime_utc', ''))
                        ev_date = ev.get('date', ev_datetime[:10] if ev_datetime else '')
                        ev_time = ev.get('time', ev_datetime[11:16] if len(ev_datetime) > 10 else '23:59')
                        if not ev_date:
                            continue
                        try:
                            ev_hour, ev_min = map(int, ev_time.split(':')[:2])
                            ev_dt = datetime(
                                int(ev_date[:4]), int(ev_date[5:7]), int(ev_date[8:10]),
                                ev_hour, ev_min, tzinfo=_tz.utc
                            )
                            if ev_dt > now_utc:
                                future_events.append({**ev, '_time': ev_time, '_date': ev_date, '_dt': ev_dt})
                        except Exception:
                            pass
                    # Count today's remaining HIGH/MED
                    remaining_today = [e for e in future_events if e['_date'] == today_str]
                    high_remaining = sum(1 for e in remaining_today if e.get('impact', '').upper() == 'HIGH')
                    med_remaining = sum(1 for e in remaining_today if e.get('impact', '').upper() in ('MEDIUM', 'MED'))
                    flag_map = {'USD':'🇺🇸','EUR':'🇪🇺','GBP':'🇬🇧','JPY':'🇯🇵','AUD':'🇦🇺','NZD':'🇳🇿','CAD':'🇨🇦','CHF':'🇨🇭'}
                    if remaining_today:
                        message += f"  🔴 HIGH: <code>{high_remaining}</code> | 🟠 MED: <code>{med_remaining}</code>\n"
                        next_ev = sorted(remaining_today, key=lambda x: x['_dt'])[0]
                        next_flag = flag_map.get(next_ev.get('currency', ''), '🏴')
                        message += f"  ➡️ Next: {next_flag} <b>{next_ev.get('currency','?')}</b> {next_ev.get('event','?')} @ <code>{next_ev.get('_time','?')} UTC</code>\n\n"
                    elif future_events:
                        # All today's news passed — show next upcoming event (tomorrow or later)
                        message += f"  ✅ Niciun eveniment rămas azi\n"
                        next_ev = sorted(future_events, key=lambda x: x['_dt'])[0]
                        next_flag = flag_map.get(next_ev.get('currency', ''), '🏴')
                        next_day = next_ev['_dt'].strftime('%a %d %b')
                        message += f"  ➡️ Următor: {next_flag} <b>{next_ev.get('currency','?')}</b> {next_ev.get('event','?')} @ <code>{next_ev.get('_time','?')} UTC {next_day}</code>\n\n"
                    else:
                        message += "  ✅ Niciun eveniment programat în săptămâna curentă\n\n"
                else:
                    message += "  ℹ️ upcoming_news.json indisponibil\n\n"
            except Exception as _e:
                message += f"  ⚠️ News error: <code>{str(_e)[:60]}</code>\n\n"
            
            _script_dir = Path(__file__).parent.resolve()
            _deep_sleep_file = _script_dir / 'data' / 'deep_sleep_state.json'
            _limit_hit = pnl_ctx.get('risk_pnl_pct', pnl_ctx.get('pnl_pct', 0)) <= -pnl_ctx.get('max_loss', 10.0)
            _resumed = pnl_ctx.get('resumed_today', False)
            if _deep_sleep_file.exists() and not _resumed:
                _verdict = '😴 DEEP SLEEP'
            elif _limit_hit and not _resumed:
                _verdict = '🔴 LIMIT — NO NEW TRADES'
            else:
                _verdict = '✅ OPERATIONAL'
            message += f"\n{SLIM_FOOTER_SEP}\n<b>🎯 Verdict:</b> {_verdict}"
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Status command error: {e}")
            return f"❌ <b>Error:</b> {str(e)}"
    
    def handle_btcusd_command(self):
        """Handle /btcusd command - Quick BTCUSD analysis (V63 V61-style)"""
        try:
            if not self.monitoring_file.exists():
                return "⚪ <b>BTCUSD — fără setup</b>\n\n<code>monitoring_setups.json</code> lipsește."

            _, setups = load_monitoring_json(self.monitoring_file)

            ACTIVE_STATUSES = {
                'ACTIVE', 'MONITORING', 'WATCHING', 'PENDING', 'READY',
                'WAITING_D1_PULLBACK', 'WAITING_4H_CHOCH', 'WAITING_4H_PULLBACK',
                'WAITING_W_D_SYNC', 'WAITING_W_ZONE', 'WAITING_POSITION_CLOSE',
            }
            btc_setup = next(
                (s for s in setups
                 if s.get('symbol', '').upper() == 'BTCUSD'
                 and s.get('status', '').upper() in ACTIVE_STATUSES),
                None
            )

            if not btc_setup:
                btc_any = next((s for s in setups if s.get('symbol', '').upper() == 'BTCUSD'), None)
                if btc_any:
                    st = btc_any.get('status', '?').upper()
                    return (
                        f"⚪ <b>BTCUSD — setup {st}</b>\n\n"
                        f"Există în JSON dar status <code>{st}</code> — nu mai e activ."
                    )
                return "⚪ <b>BTCUSD — fără setup</b>\n\nNu există BTCUSD în lista de monitorizare."

            return format_btcusd_card(btc_setup)

        except Exception as e:
            logger.error(f"❌ BTCUSD command error: {e}")
            return f"❌ <b>Error:</b> {str(e)}"
    
    def handle_active_command(self):
        """Handle /active command - Show live open positions from cTrader"""
        try:
            trade_history_file = Path(__file__).parent.resolve() / 'trade_history.json'
            
            if not trade_history_file.exists():
                return "❌ <b>No trading data found!</b>\n\n<code>trade_history.json</code> missing. Make sure cTrader sync is running."
            
            with open(trade_history_file, 'r') as f:
                data = json.load(f)
            
            account = data.get('account', {})
            positions = data.get('open_positions', [])
            balance = account.get('balance', 0)
            equity = account.get('equity', 0)
            
            if not positions:
                return (
                    f"<b>⚪ Fără poziții active</b>\n"
                    f"{SLIM_FOOTER_SEP}\n"
                    f"💰 Balance · <code>${balance:,.2f}</code>\n"
                    f"📊 Equity · <code>${equity:,.2f}</code>\n\n"
                    f"<i>Așteptăm setup-uri noi</i>"
                )

            message = (
                f"<b>🔵 Poziții live</b>\n"
                f"{SLIM_FOOTER_SEP}\n"
                f"📊 Active · <code>{len(positions)}</code>\n\n"
            )
            
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
   💰 Entry · <code>{entry:.5f}</code>
   {pl_emoji} P/L · <code>{pl_text}</code>

"""
            
            pl_summary_emoji = "🟢" if total_floating_pl > 0 else ("🔴" if total_floating_pl < 0 else "⚪")
            pl_summary_text = f"+${total_floating_pl:.2f}" if total_floating_pl > 0 else f"-${abs(total_floating_pl):.2f}"
            roi = ((equity - balance) / balance * 100) if balance > 0 else 0
            
            message += (
                f"{SLIM_FOOTER_SEP}\n"
                f"💰 Balance · <code>${balance:,.2f}</code>\n"
                f"📈 Equity · <code>${equity:,.2f}</code>\n"
                f"🔥 Floating · <code>{pl_summary_text}</code>\n"
                f"📊 ROI · <code>{roi:+.1f}%</code>"
            )
            
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
        /resume — Deblocare exclusiv: deep sleep OFF, P&L anchor reset, force_bypass_loss_limit.
        Fără scanare Daily / bias sync (pivoți falși pe lumânări neînchise).
        """
        try:
            script_dir = Path(__file__).parent.resolve()
            sleep_file = script_dir / 'data' / 'deep_sleep_state.json'

            if sleep_file.exists():
                sleep_file.unlink()

            # Marker resume — executor + /status îl citesc live
            try:
                resume_marker = script_dir / 'data' / 'system_resumed.json'
                resume_marker.parent.mkdir(parents=True, exist_ok=True)
                with open(resume_marker, 'w', encoding='utf-8') as _f:
                    json.dump({
                        'resumed_at': datetime.now(timezone.utc).isoformat(),
                        'resumed_by': 'manual /resume',
                    }, _f, indent=2)
            except Exception:
                pass

            # Reset ancora P&L + force_bypass_loss_limit in daily_state.json
            try:
                from unified_risk_manager import UnifiedRiskManager
                _rm = UnifiedRiskManager()
                _rm.reset_pnl_baseline_after_resume('manual /resume')
            except Exception as _pnl_reset_err:
                logger.warning(f"⚠️ PnL baseline reset on /resume failed: {_pnl_reset_err}")

            msg = (
                "🔱 <b>Sistem reactivat</b>\n\n"
                "Deep sleep șters · executor și radar reluate pe setup-urile din JSON.\n"
                "<i>Fără scan Daily / bias sync</i>"
            )
            logger.info("🔱 /resume executed — deep sleep cleared, loss limit bypass, no market scan")
            return msg

        except Exception as e:
            logger.error(f"❌ Resume error: {e}")
            return f"❌ <b>RESUME ERROR:</b> {str(e)}"

    def handle_news_command(self) -> str:
        """/news — Next 5 High Impact events (next 7 days). V12.2: dual-source with origin label."""
        FLAG_MAP = {
            'USD': '🇺🇸', 'EUR': '🇪🇺', 'GBP': '🇬🇧', 'JPY': '🇯🇵',
            'AUD': '🇦🇺', 'NZD': '🇳🇿', 'CAD': '🇨🇦', 'CHF': '🇨🇭',
        }
        MAJOR_CCY = set(FLAG_MAP.keys())
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=14)  # V19.11: 14 zile în loc de 7 — acoperă săptămâna viitoare complet

        def _parse_events_from_json() -> tuple[list, str]:
            """Load from economic_calendar.json — returns (events, source_label)."""
            script_dir = Path(__file__).parent.resolve()
            cal_file = script_dir / 'economic_calendar.json'
            if not cal_file.exists():
                return [], ''
            with open(cal_file, 'r') as f:
                data = json.load(f)
            raw = []
            if isinstance(data, list):
                raw = data
            else:
                for v in data.values():
                    if isinstance(v, list):
                        raw.extend(v)
            result = []
            for e in raw:
                if str(e.get('impact', '')).lower() not in ('high', 'red'):
                    continue
                if e.get('currency') not in MAJOR_CCY:
                    continue
                t = e.get('time', '00:00') or '00:00'
                if t in ('All Day', 'Tentative', ''):
                    t = '00:00'
                try:
                    dt = datetime.strptime(
                        f"{e['date']} {t}", '%Y-%m-%d %H:%M'
                    ).replace(tzinfo=timezone.utc)
                    if now <= dt <= cutoff:
                        result.append((dt, e))
                except Exception:
                    continue
            return result, '📂 economic_calendar.json'

        def _parse_events_from_ctrader() -> tuple[list, str]:
            """Load from cTrader EconomicCalendarBot port 8768."""
            try:
                import requests as _req
                resp = _req.get('http://localhost:8768/calendar', timeout=5)
                if resp.status_code != 200:
                    return [], ''
                data = resp.json()
                raw = data.get('events', [])
                if not raw:
                    return [], ''
                result = []
                for e in raw:
                    if str(e.get('impact', '')).lower() not in ('high', 'red'):
                        continue
                    if e.get('currency') not in MAJOR_CCY:
                        continue
                    try:
                        dt = datetime.strptime(
                            e['time'], '%Y-%m-%d %H:%M:%S'
                        ).replace(tzinfo=timezone.utc)
                        if now <= dt <= cutoff:
                            result.append((dt, {
                                'currency': e.get('currency'),
                                'event':    e.get('event'),
                                'forecast': str(e.get('forecast', '')) if e.get('forecast') else '',
                                'previous': str(e.get('previous', '')) if e.get('previous') else '',
                            }))
                    except Exception:
                        continue
                return result, '🤖 cTrader Live Bot (8768)'
            except Exception:
                return [], ''

        try:
            # ── Source 1: JSON file
            upcoming, source = _parse_events_from_json()

            # ── Source 2: cTrader bot (fallback if JSON empty or stale)
            if not upcoming:
                upcoming, source = _parse_events_from_ctrader()

            upcoming.sort(key=lambda x: x[0])

            # ── Build header
            msg = (
                f"<b>🚨 News HIGH IMPACT — 14 zile</b>\n"
                f"{SLIM_FOOTER_SEP}\n\n"
            )

            if not upcoming:
                msg += "✅ <b>All clear</b> — fără evenimente HIGH în următoarele 14 zile.\n"
                msg += f"\n<i>Sursă: {source or 'economic_calendar.json'}</i>"
                return msg

            # ── Group by day and display ALL events
            current_day = None
            for dt, e in upcoming:
                try:
                    import pytz as _pytz_news
                    _ro = _pytz_news.timezone('Europe/Bucharest')
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    dt_ro = dt.astimezone(_ro)
                except Exception:
                    dt_ro = dt + timedelta(hours=3)
                day_label = dt_ro.strftime('%A, %d %b').upper()
                if day_label != current_day:
                    if current_day is not None:
                        msg += "\n"
                    msg += f"📅 <b>{day_label}</b>\n"
                    current_day = day_label

                flag     = FLAG_MAP.get(e.get('currency', ''), '🌐')
                currency = e.get('currency', 'N/A')
                name     = e.get('event', 'N/A')
                fc       = e.get('forecast', '') or '—'
                prev     = e.get('previous', '') or '—'
                tstr = f"{dt_ro.strftime('%H:%M')} {dt_ro.tzname() or 'RO'}"

                # Countdown
                delta_s = (dt - now).total_seconds()
                delta_h = int(delta_s // 3600)
                if delta_s < 3600:
                    delta_m = int(delta_s // 60)
                    countdown = f"⏳ {delta_m}min"
                elif delta_h < 24:
                    countdown = f"⏳ {delta_h}h"
                else:
                    countdown = f"⏳ {delta_h // 24}d {delta_h % 24}h"

                # Critical badge
                is_critical = any(kw.lower() in name.lower() for kw in
                    ['NFP','Non-Farm','Payroll','FOMC','CPI','GDP','Interest Rate','Bank Rate'])
                badge = "🔥" if is_critical else "🚨"

                msg += (
                    f"{badge} <b>{flag} {currency} — {name}</b>\n"
                    f"   ⏰ {tstr}  {countdown}  |  F:<b>{fc}</b>  P:{prev}\n"
                )

            msg += f"\n{SLIM_FOOTER_SEP}\n"
            msg += f"<i>Sursă: {source}</i>"
            return msg

        except Exception as e:
            logger.error(f"❌ /news error: {e}")
            return f"❌ <b>NEWS ERROR:</b> {str(e)}"

    def handle_rates_command(self) -> str:
        """/rates — Live central bank rates + carry + IC Markets swap (V38.6)"""
        try:
            from macro_rates import format_rates_telegram_message
            return format_rates_telegram_message(
                separator=SLIM_FOOTER_SEP,
                include_swaps=True,
                force_refresh=True,
                notify_on_change=True,
            )
        except Exception as e:
            logger.error(f"❌ /rates error: {e}")
            return f"❌ <b>RATES ERROR:</b> {str(e)}"

    def process_command(self, message_obj):
        """
        V11.5 ACCESS CONTROL — Ierarhie PUBLIC vs ADMIN

        🔓 PUBLIC  → /monitoring /stats /weekly /help /status
        🔐 ADMIN   → /killall /resume /active /btcusd /news /rates
        """
        reply_chat_id = None
        try:
            from_user = message_obj.get('from', {})
            user_id   = from_user.get('id')
            text      = message_obj.get('text', '').strip()
            reply_chat_id = message_obj.get('chat', {}).get('id')

            if not text.startswith('/'):
                return

            command = text.split()[0].lower()
            is_admin = (user_id == self.admin_id)

            logger.info(f"📥 cmd={command} user={user_id} admin={is_admin} chat={reply_chat_id}")

            # ── ACCES RESTRICȚIONAT: comandă ADMIN apelată de non-admin ──
            if command in self.ADMIN_COMMANDS and not is_admin:
                logger.warning(f"🔐 ACCES REFUZAT: user={user_id} a încercat {command}")
                self.send_message(
                    f"⚠️ <b>ACCES RESTRICȚIONAT.</b>\n\n"
                    f"Comanda <code>{command}</code> este rezervată exclusiv administratorului.",
                    chat_id=reply_chat_id,
                )
                return

            # ── Comenzi necunoscute: ignoră silenţios dacă non-admin ──
            known = self.PUBLIC_COMMANDS | self.ADMIN_COMMANDS
            if command not in known and not is_admin:
                return  # non-admin vede un command necunoscut → ignorăm

            # ── ROUTING ──────────────────────────────────────────────────
            if command == '/stats':
                response = self.handle_stats_command()
            elif command == '/weekly':
                response = self.handle_weekly_command()
            elif command == '/monitoring':
                response = self.handle_monitoring_command()
            elif command == '/status':
                response = self.handle_status_command()
            elif command == '/active':
                response = self.handle_active_command()
            elif command == '/btcusd':
                response = self.handle_btcusd_command()
            elif command == '/killall':
                response = self.handle_killall_command()
            elif command == '/resume':
                response = self.handle_resume_command()
            elif command == '/news':
                response = self.handle_news_command()
            elif command == '/rates':
                response = self.handle_rates_command()
            elif command == '/help':
                if is_admin:
                    response = (
                        f"<b>🎮 Command Center V63</b>\n"
                        f"{SLIM_FOOTER_SEP}\n\n"
                        f"🔓 <b>Public</b>\n"
                        f"<code>/monitoring</code> — Setup-uri în pândă\n"
                        f"<code>/stats</code> — P/L zilnic\n"
                        f"<code>/weekly</code> — Raport 7 zile\n"
                        f"<code>/status</code> — Health sistem\n"
                        f"<code>/btcusd</code> — Quick BTCUSD\n"
                        f"<code>/news</code> — HIGH IMPACT\n"
                        f"<code>/rates</code> — Rate BC\n"
                        f"<code>/help</code> — Această listă\n\n"
                        f"{SLIM_FOOTER_SEP}\n\n"
                        f"🔐 <b>Admin</b>\n"
                        f"<code>/active</code> — Poziții live\n"
                        f"<code>/killall</code> — Stop total + 24h lock\n"
                        f"<code>/resume</code> — Ieșire deep sleep\n"
                    )
                else:
                    response = (
                        f"<b>🎮 Command Center V63</b>\n"
                        f"{SLIM_FOOTER_SEP}\n\n"
                        f"🔓 <b>Comenzi</b>\n"
                        f"<code>/monitoring</code> — Setup-uri în pândă\n"
                        f"<code>/stats</code> — P/L zilnic\n"
                        f"<code>/weekly</code> — Raport săptămânal\n"
                        f"<code>/status</code> — Stare sistem\n"
                        f"<code>/btcusd</code> — Quick BTCUSD\n"
                        f"<code>/news</code> — HIGH IMPACT\n"
                        f"<code>/rates</code> — Rate BC\n"
                        f"<code>/help</code> — Această listă\n"
                    )
            else:
                if is_admin:
                    response = f"❌ <b>Unknown command:</b> <code>{command}</code>\n\nUse <code>/help</code> for available commands."
                else:
                    return  # non-admin + comandă necunoscută → ignorăm

            self.send_message(response, chat_id=reply_chat_id)

        except Exception as e:
            logger.exception(f"❌ Command processing error: {e}")
            if reply_chat_id:
                self.send_message(
                    f"❌ <b>Eroare la procesarea comenzii</b>\n\n<code>{str(e)[:200]}</code>",
                    chat_id=reply_chat_id,
                )
    
    def run(self):
        """Main loop - listen for commands"""
        self._ensure_polling_mode()
        logger.info("🎮 Command Center started - Listening for commands...")
        
        while True:
            try:
                updates = self.get_updates()
                
                for update in updates:
                    self.last_update_id = update.get('update_id', 0)
                    self._save_update_id(self.last_update_id)  # persist — no duplicate on restart
                    
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
    # ✅ V11.6 FIX: Use absolute path — relative path breaks when watchdog starts
    # from different CWD, causing 2 instances to see different lock files
    lock_file = Path(__file__).parent.resolve() / "process_telegram_command_center.lock"
    if not acquire_pid_lock(lock_file):
        logger.error("🚫 DUPLICATE INSTANCE DETECTED - Exiting to prevent double notifications")
        sys.exit(1)
    
    # Register cleanup on exit
    atexit.register(release_pid_lock, lock_file)
    
    center = TelegramCommandCenter()
    center.run()
