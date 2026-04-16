"""
Position Monitor - detectează NOUL TRADE OPEN și trimite ARMAGEDDON notification
Monitorizează trade_history.json pentru poziții noi deschise
"""

# Windows VPS fix: force UTF-8 stdout to prevent UnicodeEncodeError on emoji
import sys as _sys, io as _io
if hasattr(_sys.stdout, 'buffer'):
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(_sys.stderr, 'buffer'):
    _sys.stderr = _io.TextIOWrapper(_sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import time
import os
import subprocess
import sys
import atexit
from pathlib import Path
from loguru import logger
from datetime import datetime
import requests
import psutil
from dotenv import load_dotenv

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
    str(_LOG_DIR / "position_monitor.log"),
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
    level="DEBUG",
    rotation="10 MB",
    retention="7 days",
    compression="zip"
)


def acquire_pid_lock(lock_file: Path) -> bool:
    """
    🔒 PID LOCK SINGLETON PATTERN - Prevents duplicate process instances
    Returns True if lock acquired, False if another instance is already running
    """
    try:
        my_pid = os.getpid()
        if lock_file.exists():
            try:
                with open(lock_file, 'r') as f:
                    old_pid = int(f.read().strip())
            except (ValueError, OSError):
                old_pid = None

            # If lock contains our own PID, it's a stale lock from a previous failed start
            if old_pid == my_pid or old_pid is None:
                logger.warning(f"🔧 Stale lock with own PID — removing")
                lock_file.unlink()
            elif psutil.pid_exists(old_pid):
                try:
                    proc = psutil.Process(old_pid)
                    cmdline = ' '.join(proc.cmdline())
                    # Verify it's the same script (not PID reuse by another process)
                    if 'position_monitor' in cmdline:
                        logger.error(f"❌ Position Monitor already running (PID {old_pid})")
                        logger.error("⚠️  Cannot start duplicate instance - exiting")
                        return False
                    # PID exists but it's a different process (PID reuse) — stale lock
                    logger.warning(f"🔧 PID {old_pid} is a different process — stale lock, removing")
                    lock_file.unlink()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    logger.warning(f"🔧 Cannot verify PID {old_pid} — treating as stale lock")
                    lock_file.unlink()
            else:
                # PID not running — stale lock
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


class PositionMonitor:
    """Monitorizează noi poziții deschise și trimite ARMAGEDDON notifications"""
    
    def __init__(self):
        self.trade_history_file = Path("trade_history.json")
        self.seen_positions_file = Path(".seen_positions.json")
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.seen_open_tickets = self._load_seen_tickets('seen_open_tickets')
        self.seen_closed_tickets = self._load_seen_tickets('seen_closed_tickets')
        
        logger.info("👀 Position Monitor initialized")
    
    def _load_seen_tickets(self, key):
        """Încarcă ticket-urile deja procesate (separate pentru open și closed)"""
        if self.seen_positions_file.exists():
            try:
                with open(self.seen_positions_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get(key, []))
            except Exception as e:
                logger.warning(f"Could not load seen tickets: {e}")
        return set()
    
    def _save_seen_tickets(self):
        """Salvează ticket-urile procesate (separate pentru open și closed)"""
        try:
            with open(self.seen_positions_file, 'w') as f:
                json.dump({
                    'seen_open_tickets': list(self.seen_open_tickets),
                    'seen_closed_tickets': list(self.seen_closed_tickets),
                    'last_update': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save seen tickets: {e}")
    
    def _send_closed_trade_notification(self, trade):
        """Trimite notificare pentru trade închis cu profit/loss + account status"""
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning("⚠️  Telegram credentials missing")
            return False
        
        symbol = trade.get('symbol', 'N/A')
        direction = trade.get('direction', 'N/A')
        profit = trade.get('profit', 0)
        lot = trade.get('lot_size', 0)
        ticket = trade.get('ticket', 'N/A')
        entry = trade.get('entry_price', 0)
        close_price = trade.get('close_price', 0)
        close_time = trade.get('close_time', 'N/A')
        
        # Get account info from trade_history.json
        account_balance = 0
        account_equity = 0
        open_positions_count = 0
        total_open_pl = 0
        
        try:
            with open(self.trade_history_file, 'r') as f:
                data = json.load(f)
                account_balance = data.get('account', {}).get('balance', 0)
                account_equity = data.get('account', {}).get('equity', 0)
                open_positions = data.get('open_positions', [])
                open_positions_count = len(open_positions)
                total_open_pl = sum(p.get('profit', 0) for p in open_positions)
        except Exception as e:
            logger.warning(f"Could not load account info: {e}")
        
        # Profit/Loss styling
        if profit > 0:
            profit_emoji = "🟢 💰"
            profit_text = f"+${profit:.2f}"
            title = "🎯 <b>TRADE WINNER!</b> 🎯"
            conclusion = "<i>💎 'Another one bites the dust'</i>"
        else:
            profit_emoji = "🔴 📉"
            profit_text = f"-${abs(profit):.2f}"
            title = "⚠️ <b>TRADE CLOSED</b> ⚠️"
            conclusion = "<i>📊 'We learn and adapt'</i>"
        
        direction_emoji = "📈" if direction == 'BUY' else "📉"
        
        # Open P/L emoji
        pl_emoji = "📈" if total_open_pl >= 0 else "📉"
        
        message = f"""
{title}

{profit_emoji} <b>POSITION CLOSED</b>

{direction_emoji} <b>{direction}</b> <code>{lot}</code> <b>{symbol}</b>
💵 Profit/Loss: <code>{profit_text}</code>
📊 Entry: <code>{entry:.5f}</code>
🎯 Close: <code>{close_price:.5f}</code>
🎫 Ticket: <code>#{ticket}</code>
⏰ Closed: {close_time}

{conclusion}

──────────────────
💼 <b>ACCOUNT STATUS</b>
──────────────────
💰 Balance: <code>${account_balance:.2f}</code>
💎 Equity: <code>${account_equity:.2f}</code>
{pl_emoji} Open P/L: <code>${total_open_pl:+.2f}</code>
📊 Open Positions: <code>{open_positions_count}</code>

<code>──────────────────</code>
✨ <b>Glitch in Matrix</b> by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money
"""
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message.strip(),
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.success(f"✅ Closed trade notification sent for {symbol} #{ticket} (Profit: ${profit:.2f})!")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Telegram: {e}")
            return False
    
    def _send_armageddon_notification(self, trade):
        """Trimite EPIC ARMAGEDDON notification pentru poziție nouă"""
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning("⚠️  Telegram credentials missing")
            return False
        
        symbol = trade.get('symbol', 'N/A')
        direction = trade.get('direction', 'N/A')
        entry = trade.get('entry_price', 0)
        lot = trade.get('lot_size', 0)
        ticket = trade.get('ticket', 'N/A')
        stop_loss = trade.get('stop_loss')
        take_profit = trade.get('take_profit')

        # ✅ V11.0 CARRY: fetch live swap from cTrader, fallback to monitoring_setups.json
        swap_long = None
        swap_short = None
        swap_triple_day = None
        try:
            import requests as _req
            swap_resp = _req.get(
                f"http://localhost:8767/swap_info",
                params={'symbol': symbol},
                timeout=5
            )
            if swap_resp.status_code == 200:
                sd = swap_resp.json()
                if sd.get('success'):
                    swap_long = float(sd['swap_long'])
                    swap_short = float(sd['swap_short'])
                    swap_triple_day = str(sd.get('swap_triple_day', ''))
        except Exception:
            pass

        # Fallback: read from monitoring_setups.json if cTrader offline
        if swap_long is None:
            try:
                import json as _json
                from pathlib import Path as _Path
                ms_file = _Path(__file__).parent / 'monitoring_setups.json'
                if ms_file.exists():
                    ms_data = _json.loads(ms_file.read_text())
                    for s in ms_data.get('setups', []):
                        if s.get('symbol', '').upper() == symbol.upper():
                            swap_long = s.get('swap_long')
                            swap_short = s.get('swap_short')
                            swap_triple_day = s.get('swap_triple_day')
                            break
            except Exception:
                pass
        
        direction_emoji = "📈" if direction == 'BUY' else "📉"
        
        # Epic ARMAGEDDON messages
        import random
        armageddon_messages = [
            "⚔️ <b>THE ARMAGEDDON BEGINS</b> ⚔️",
            "💥 <b>MARKET DOMINATION MODE</b> 💥",
            "🔥 <b>BEAST MODE UNLEASHED</b> 🔥",
            "⚡ <b>GODMODE ACTIVATED</b> ⚡",
            "🎯 <b>SNIPER ELITE • TARGET LOCKED</b> 🎯",
            "💀 <b>NO MERCY • FULL AGGRO</b> 💀",
            "🚀 <b>TO THE MOON WE GO</b> 🚀",
            "👑 <b>KING'S GAMBIT • CHECKMATE</b> 👑",
            "⚡ <b>GLITCH ACTIVATED • MATRIX BREACHED</b> ⚡",
            "🔮 <b>PROPHECY FULFILLED</b> 🔮"
        ]
        epic_title = random.choice(armageddon_messages)
        
        # Direction arrows
        direction_arrow = "📈 ↗️" if direction == 'BUY' else "📉 ↘️"
        
        # Calculate risk metrics if SL available
        risk_pips = ""
        reward_pips = ""
        rr_ratio = ""
        if stop_loss and take_profit:
            pip_value = 0.01 if 'JPY' in symbol else 0.0001
            risk_p = abs(entry - stop_loss) / pip_value
            reward_p = abs(take_profit - entry) / pip_value
            risk_pips = f"\n🛑 <b>Risk:</b> {risk_p:.1f} pips"
            reward_pips = f"\n🎯 <b>Reward:</b> {reward_p:.1f} pips"
            if risk_p > 0:
                rr = reward_p / risk_p
                rr_ratio = f"\n📊 <b>R:R Ratio:</b> 1:{rr:.2f}"
        
        # Build message with TP/SL
        message = f"""
{epic_title}

🔥 <b>GLITCH IN MATRIX • POSITION LIVE</b> 🔥
──────────────────

💎 <b>{symbol}</b> • {direction_arrow} <b>{direction}</b>
📦 <b>Volume:</b> <code>{lot}</code> lots
💰 <b>Entry:</b> <code>{entry:.5f}</code>
🎫 <b>Ticket:</b> <code>#{ticket}</code>
"""
        
        # Add SL/TP if available
        if stop_loss:
            message += f"\n🛑 <b>Stop Loss:</b> <code>{stop_loss:.5f}</code>"
        if take_profit:
            message += f"\n🎯 <b>Take Profit:</b> <code>{take_profit:.5f}</code>"
        
        # Add risk metrics
        message += risk_pips + reward_pips + rr_ratio

        # ✅ V11.0 CARRY MATRIX block
        if swap_long is not None and swap_short is not None:
            from datetime import datetime as _dt
            dir_lower = direction.lower()
            relevant_swap = swap_long if dir_lower in ('buy', 'long') else swap_short
            if relevant_swap > 0:
                carry_status = "✅ CREDIT"
                carry_val = f"+{relevant_swap:.4f} pips/zi"
            else:
                carry_status = "⚠️ COST"
                carry_val = f"{relevant_swap:.4f} pips/zi"
            message += f"\n\n──────────────────"
            message += f"\n💱 <b>CARRY MATRIX:</b> {carry_status}"
            message += f"\n   Long: <code>{swap_long:+.4f}</code> | Short: <code>{swap_short:+.4f}</code>"
            message += f"\n   Direcția ta: <code>{carry_val}</code>"
            if swap_triple_day:
                today_name = _dt.now().strftime('%A')
                if today_name.lower() == swap_triple_day.lower():
                    mult = relevant_swap * 3
                    message += f"\n   🔥 <b>TRIPLE SWAP DISEARĂ!</b> x3 = <code>{mult:+.4f} pips</code>"
                else:
                    message += f"\n   📅 Triple swap: <b>{swap_triple_day}</b>"

        message += """

──────────────────
🧠 <b>AI Validation:</b> ✅ CONFIRMED
⚡ <b>Risk Level:</b> CALCULATED
🤖 <b>Execution:</b> AUTOMATED
💯 <b>Confidence:</b> HIGH

<i>💎 "The Matrix cannot hold us" 💎</i>

<code>──────────────────</code>
✨ <b>Glitch in Matrix</b> by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money
"""
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message.strip(),
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.success(f"✅ ARMAGEDDON notification sent for {symbol} #{ticket}!")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Telegram: {e}")
            return False
    
    def check_for_new_positions(self):
        """Verifică dacă sunt poziții noi deschise"""
        if not self.trade_history_file.exists():
            logger.warning("trade_history.json not found")
            return
        
        try:
            # Always reload from disk for perfect sync
            self.seen_open_tickets = self._load_seen_tickets('seen_open_tickets')
            self.seen_closed_tickets = self._load_seen_tickets('seen_closed_tickets')
            
            with open(self.trade_history_file, 'r') as f:
                data = json.load(f)

            # Separate open and closed trades
            open_positions = data.get('open_positions', [])
            closed_trades = data.get('closed_trades', [])

            # Check for NEW OPEN positions (avoid duplicate notifications)
            new_open = []
            unique_tickets = set()
            for trade in open_positions:
                ticket = trade.get('ticket')
                if not ticket:
                    continue
                # Avoid duplicate notifications for same ticket
                if ticket in self.seen_open_tickets or ticket in unique_tickets:
                    continue
                new_open.append(trade)
                unique_tickets.add(ticket)
                self.seen_open_tickets.add(ticket)
                logger.info(f"🆕 NEW POSITION OPENED: {trade.get('symbol')} #{ticket}")

            # Check for NEW CLOSED trades (TP/SL hit) - SEPARATE tracking from opens!
            new_closed = []
            for trade in closed_trades:
                ticket = trade.get('ticket')
                # NEW LOGIC: Check if ticket is in seen_closed (not seen_open!)
                if ticket and ticket not in self.seen_closed_tickets:
                    new_closed.append(trade)
                    self.seen_closed_tickets.add(ticket)
                    profit = trade.get('profit', 0)
                    emoji = "✅" if profit > 0 else "❌"
                    logger.info(f"{emoji} TRADE CLOSED: {trade.get('symbol')} #{ticket} (Profit: ${profit:.2f})")

            # Send notifications
            for trade in new_open:
                self._send_armageddon_notification(trade)

            for trade in new_closed:
                self._send_closed_trade_notification(trade)
                
                # 🧠 AUTO-LEARNING: Trigger ML update after every closed trade
                logger.info("🧠 Triggering AUTO-LEARNING system...")
                try:
                    subprocess.Popen(
                        [sys.executable, "trigger_ml_update.py"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                    logger.success("✅ ML update triggered in background")
                except Exception as e:
                    logger.warning(f"⚠️  Could not trigger ML update: {e}")

            if new_open or new_closed:
                self._save_seen_tickets()
                logger.success(f"✅ Processed {len(new_open)} new opens, {len(new_closed)} new closes!")

        except Exception as e:
            logger.error(f"Error checking positions: {e}")
    
    def monitor_loop(self, interval=10):
        """Loop continuu de monitorizare (check la fiecare 10s)"""
        logger.info(f"🔄 Starting position monitor (check every {interval}s)")
        logger.info("🎯 Will send ARMAGEDDON notification for every new position!")
        
        try:
            while True:
                self.check_for_new_positions()
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("⏹️  Monitor stopped by user")
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")


if __name__ == "__main__":
    import sys
    import platform

    # 🔒 PID LOCK - Prevent duplicate instances (absolute path — works from any cwd)
    lock_file = Path(__file__).parent / "process_position_monitor.lock"

    # Cross-platform exclusive lock: msvcrt on Windows, fcntl on Unix
    _lock_fd = open(lock_file, 'w', encoding='utf-8')
    try:
        if platform.system() == 'Windows':
            import msvcrt
            msvcrt.locking(_lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fd.write(str(os.getpid()))
        _lock_fd.flush()
    except (BlockingIOError, OSError):
        logger.error("🚫 DUPLICATE INSTANCE DETECTED — another position_monitor is running. Exiting.")
        sys.exit(1)

    if not acquire_pid_lock(lock_file):
        logger.error("🚫 DUPLICATE INSTANCE DETECTED - Exiting to prevent double notifications")
        sys.exit(1)
    
    # Register cleanup on exit
    atexit.register(release_pid_lock, lock_file)
    
    monitor = PositionMonitor()
    
    # Check for --loop or --test
    if '--loop' in sys.argv:
        monitor.monitor_loop(interval=10)
    elif '--test' in sys.argv:
        # Test mode - check once
        print("\n🧪 Testing position detection...\n")
        monitor.check_for_new_positions()
        print("\n✅ Test complete!")
    else:
        # Default: run loop
        print("🚀 Starting Position Monitor...")
        print("💡 This will send ARMAGEDDON notification for EVERY new trade opened!")
        print("⏹️  Press Ctrl+C to stop\n")
        monitor.monitor_loop(interval=10)
