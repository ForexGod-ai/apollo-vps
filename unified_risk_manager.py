#!/usr/bin/env python3
"""
──────────────────
🛡️ Unified Risk Manager - Single Source of Truth
──────────────────

Reads SUPER_CONFIG.json (shared with cBot)
Enforces risk limits across Python and cTrader
Activates KILL SWITCH on 10% daily loss

🔱 AUTHORED BY ФорексГод 🔱
──────────────────
"""

import json
import sqlite3
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import requests
try:
    import pytz
    TZ_RO = pytz.timezone('Europe/Bucharest')
except ImportError:
    pytz = None
    TZ_RO = None

load_dotenv()

class UnifiedRiskManager:
    """
    Unified Risk Manager - Enforces limits from SUPER_CONFIG.json
    Used by both Python and cBot (via config file)
    """
    
    def __init__(self, config_file="SUPER_CONFIG.json"):
        self.config_file = Path(config_file)
        self.db_path = Path("data/trades.db")
        self.kill_switch_file = Path("trading_disabled.flag")
        self.daily_state_file = Path("data/daily_state.json")  # ✅ NEW: Daily state persistence
        
        # Telegram
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Load unified config
        self.config = self._load_config()
        
        # Extract limits
        self.risk_per_trade = self.config['risk_management']['risk_per_trade_percent']
        self.max_positions = self.config['position_limits']['max_open_positions']
        self.max_daily_loss_pct = self.config['daily_limits']['max_daily_loss_percent']
        self.daily_warning_pct = self.config['daily_limits']['daily_loss_warning_percent']
        self.kill_switch_enabled = self.config['kill_switch']['enabled']
        self.kill_switch_trigger = self.config['kill_switch']['trigger_daily_loss_percent']
        
        # 🛡️ V7.1 DUPLICATE GUARD: Max positions per symbol (loaded from SUPER_CONFIG)
        # V14.1: Changed from hardcoded 1 → read from config for scale-in support (max=2)
        self.max_positions_per_symbol = self.config.get('position_limits', {}).get('max_positions_per_symbol', 1)
        self.active_positions_file = Path(__file__).parent / "active_positions.json"
        
        # 🔇 V9.1 SILENT REJECTION: 4-hour cooldown per reason category (ANTI-SPAM FIX by ФорексГод)
        # Format: {"reason_category": {"last_sent": datetime, "count": int}}
        self._rejection_cooldown = {}
        self._warning_cooldown = {}
        self.REJECTION_COOLDOWN_HOURS = 4  # Max 1 Telegram alert per reason per 4 hours
        self.WARNING_COOLDOWN_HOURS = 4   # Max 1 warning alert per 4 hours
        
        # ✅ Load daily state persistence
        self._reset_timestamp = None
        self._force_bypass_loss_limit = False
        self._load_daily_state()
        
        print(f"\n🛡️  UNIFIED RISK MANAGER INITIALIZED")
        print(f"──────────────────")
        print(f"📊 Risk per trade: {self.risk_per_trade}%")
        print(f"📈 Max positions: {self.max_positions}")
        print(f"🛡️ Max per symbol: {self.max_positions_per_symbol}")
        print(f"🛑 Daily loss limit: {self.max_daily_loss_pct}%")
        print(f"⚠️  Daily warning: {self.daily_warning_pct}%")
        print(f"🔴 Kill switch: {'ENABLED' if self.kill_switch_enabled else 'DISABLED'} @ {self.kill_switch_trigger}%")
        print(f"📅 Today's starting balance: ${self.starting_balance_today:.2f}")
        print(f"──────────────────")
    
    def _load_daily_state(self):
        """
        Load daily state from JSON. Auto-reset if new day detected.

        V14.0 FIX: Uses Europe/Bucharest for all date comparisons.
        Reset triggers at 00:05 EET (Romania standard time).
        Also clears rejection cooldowns on new day.
        """
        today = self._today_ro()
        
        try:
            if self.daily_state_file.exists():
                with open(self.daily_state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                
                last_date = state.get('date')
                
                if last_date == today:
                    # Same day - load existing state
                    self.starting_balance_today = state.get('starting_balance', 0.0)
                    self.daily_trades_count = state.get('trades_count', 0)
                    self._reset_timestamp = state.get('reset_timestamp')
                    self._force_bypass_loss_limit = bool(state.get('force_bypass_loss_limit', False))
                    print(f"✅ Daily state loaded: {today} (Starting: ${self.starting_balance_today:.2f})")
                    self._correct_stale_daily_starting()
                else:
                    # NEW DAY - reset everything
                    print(f"🔄 NEW DAY DETECTED: {last_date} → {today}")
                    self._rejection_cooldown.clear()  # V9.1: Clear rejection cooldowns on new day
                    self._warning_cooldown.clear()     # V9.1: Clear warning cooldowns on new day
                    self._reset_daily_state(today)
            else:
                # First run - initialize
                print(f"🆕 First run - initializing daily state for {today}")
                self._reset_daily_state(today)
        
        except Exception as e:
            print(f"⚠️  Error loading daily state: {e}")
            self._reset_daily_state(today)
    
    def _today_ro(self) -> str:
        """Return current date string in Europe/Bucharest timezone."""
        if TZ_RO is not None:
            return datetime.now(TZ_RO).date().isoformat()
        # fallback: UTC+3 (safe approximation for Romania during EEST)
        return (datetime.utcnow() + timedelta(hours=3)).date().isoformat()

    def _now_ro(self) -> datetime:
        """Return current naive datetime in Europe/Bucharest timezone."""
        if TZ_RO is not None:
            return datetime.now(TZ_RO).replace(tzinfo=None)
        return datetime.utcnow() + timedelta(hours=3)

    def _reset_daily_state(self, date):
        """
        Reset daily state for new day.
        V14.0: Uses Europe/Bucharest. Sends minimalist SYSTEM RESET alert.
        """
        # V52.1: Retry broker at startup — watchdog restart often races cBot on 8767.
        equity, balance = self.get_account_balance(broker_retries=5, broker_delay_s=2.0)
        live = self._fetch_broker_balance()
        if live:
            live_eq, live_bal = live
            if abs(live_eq - equity) > 0.5 or abs(live_bal - balance) > 0.5:
                print(
                    f"⚠️  SYSTEM RESET pre-alert correction: "
                    f"${equity:.2f} → ${live_eq:.2f} (live 8767)"
                )
                equity, balance = live_eq, live_bal
        self.starting_balance_today = equity
        self.daily_trades_count = 0

        # V10.6: Force-clear deep_sleep_state.json if it's a natural daily reset
        # (not a manual /killall lockdown — those have lockdown=True)
        try:
            sleep_file = self.daily_state_file.parent / 'deep_sleep_state.json'
            if sleep_file.exists():
                with open(sleep_file, 'r', encoding='utf-8') as f:
                    sleep_state = json.load(f)
                if not sleep_state.get('lockdown', False):
                    sleep_file.unlink()
                    print(f"🔱 Daily reset: deep_sleep_state.json cleared (non-lockdown)")
        except Exception as e:
            print(f"⚠️ Could not clear sleep file on reset: {e}")

        state = {
            'date': date,
            'starting_balance': equity,
            'starting_equity': equity,
            'starting_balance_note': 'Uses equity (not balance) — includes floating P&L',
            'trades_count': 0,
            'daily_loss_reached': False,
            'force_bypass_loss_limit': False,
            'reset_timestamp': self._now_ro().isoformat(),
            'timezone': 'Europe/Bucharest',
        }
        self._force_bypass_loss_limit = False
        self._reset_timestamp = state['reset_timestamp']

        self.daily_state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.daily_state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

        print(f"✅ Daily state RESET: Starting EQUITY = ${equity:.2f} (balance=${balance:.2f})")
        self._send_daily_awakened_alert(equity, balance)

    def _send_daily_awakened_alert(self, equity: float, balance: float):
        """
        V14.0: Minimalist SYSTEM RESET alert — Europe/Bucharest time.
        Format requested by ФорексГод: date, equity, status.
        """
        try:
            token = os.getenv('TELEGRAM_BOT_TOKEN')
            chat_id = os.getenv('TELEGRAM_CHAT_ID')
            if not token or not chat_id:
                return

            now_ro = self._now_ro()
            date_str = now_ro.strftime('%d %b %Y')   # e.g. "08 Apr 2026"
            message = (
                f"🏛️ <b>SYSTEM RESET</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"📅 New Day: <b>{date_str}</b>\n"
                f"💰 Equity: <code>${equity:.2f}</code>\n"
                f"🛡️ Status: <b>Ready &amp; Hunting</b>"
            )
            import requests as _req
            _req.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'},
                timeout=10
            )
            print("🏛️ SYSTEM RESET alert sent to Telegram (EET)")
        except Exception as e:
            print(f"⚠️ Could not send reset alert: {e}")

    def _correct_stale_daily_starting(self):
        """Fix daily_state when midnight reset used stale trade_history.json cache."""
        try:
            from trade_manager import TradeManager
            data = TradeManager(Path(__file__).parent.resolve()).fetch_broker_live()
            if not data:
                return
            acct = data.get('account', {})
            live_equity = float(acct.get('equity', 0) or 0)
            live_balance = float(acct.get('balance', 0) or 0)
            ref = live_balance if live_balance > 0 else live_equity
            stored = float(self.starting_balance_today or 0)
            if ref <= 0 or stored <= 0:
                return
            if stored < ref * 0.75 or stored > ref * 1.25:
                corrected = live_equity if live_equity > 0 else ref
                print(
                    f"⚠️  Stale daily starting ${stored:.2f} vs broker ${ref:.2f} "
                    f"— correcting to ${corrected:.2f}"
                )
                self.starting_balance_today = corrected
                self._save_daily_state()
        except Exception as e:
            print(f"⚠️  Could not correct stale daily starting: {e}")
    
    def _save_daily_state(self):
        """Save current daily state to JSON — V14.0: EET date, preserve reset_timestamp."""
        today = self._today_ro()

        state = {
            'date': today,
            'starting_balance': self.starting_balance_today,
            'trades_count': self.daily_trades_count,
            'last_update': datetime.now().isoformat(),
        }
        try:
            if self.daily_state_file.exists():
                with open(self.daily_state_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                for key in (
                    'reset_timestamp', 'daily_loss_reached', 'starting_equity',
                    'starting_balance_note', 'timezone', 'manual_resume_at',
                ):
                    if key in existing:
                        state[key] = existing[key]
        except Exception:
            pass
        if getattr(self, '_reset_timestamp', None):
            state['reset_timestamp'] = self._reset_timestamp
        
        self.daily_state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.daily_state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

    def _refresh_daily_state_from_disk(self) -> None:
        """V37.12 / V39.1: Reincarca daily_state dupa /resume (proces long-running)."""
        try:
            if not self.daily_state_file.exists():
                return
            with open(self.daily_state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            if state.get('date') == self._today_ro():
                self.starting_balance_today = float(state.get('starting_balance') or 0)
                self.daily_trades_count = int(state.get('trades_count') or 0)
                self._reset_timestamp = state.get('reset_timestamp')
                self._force_bypass_loss_limit = bool(state.get('force_bypass_loss_limit', False))
        except Exception:
            pass

    def reset_pnl_baseline_after_resume(self, reason: str = 'manual /resume') -> None:
        """V37.12: /resume — reseteaza P&L zilnic de la equity curent, Colonel continua trading."""
        today = self._today_ro()
        equity, balance = self.get_account_balance()
        now_iso = self._now_ro().isoformat()
        self.starting_balance_today = equity if equity > 0 else balance
        self._reset_timestamp = now_iso
        self._rejection_cooldown.pop('daily_loss_limit', None)
        self._warning_cooldown.pop('daily_loss_warning', None)

        state = {
            'date': today,
            'starting_balance': self.starting_balance_today,
            'starting_equity': equity,
            'starting_balance_note': f'Reset by {reason}',
            'trades_count': self.daily_trades_count,
            'daily_loss_reached': False,
            'force_bypass_loss_limit': True,
            'reset_timestamp': now_iso,
            'manual_resume_at': now_iso,
            'timezone': 'Europe/Bucharest',
            'last_update': datetime.now().isoformat(),
        }
        self._force_bypass_loss_limit = True
        self.daily_state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.daily_state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

        sleep_file = self.daily_state_file.parent / 'deep_sleep_state.json'
        sleep_file.unlink(missing_ok=True)
        print(f"🔱 [V37.12] PnL baseline reset ({reason}): starting=${self.starting_balance_today:.2f}")

    def _calc_daily_loss_pct(self, total_pnl: float, balance: float) -> float:
        """V37.12: % fata de starting_balance al zilei (sau balance daca lipseste)."""
        base = self.starting_balance_today if getattr(self, 'starting_balance_today', 0) > 0 else balance
        if base <= 0:
            return 0.0
        return (total_pnl / base) * 100
    
    def _load_config(self):
        """Load SUPER_CONFIG.json"""
        try:
            if not self.config_file.exists():
                raise FileNotFoundError(f"SUPER_CONFIG.json not found!")
            
            with open(self.config_file, 'r', encoding='utf-8') as config_f:
                config = json.load(config_f)
            
            print(f"✅ Config loaded: {config['system_info']['name']} v{config['system_info']['version']}")
            return config
            
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            raise
    
    def _fetch_broker_balance(self):
        """Live equity/balance from TradeHistorySyncer (8767). None if offline."""
        try:
            from trade_manager import TradeManager
            broker_data = TradeManager(Path(__file__).parent.resolve()).fetch_broker_live()
            if not broker_data:
                return None
            account = broker_data.get('account', {})
            equity = float(account.get('equity', 0) or 0)
            balance = float(account.get('balance', 0) or 0)
            if equity > 0 or balance > 0:
                return equity, balance
        except Exception as e:
            print(f"⚠️  cTrader broker fetch error: {e}")
        return None

    def get_account_balance(self, broker_retries: int = 1, broker_delay_s: float = 0.0):
        """Get current account equity/balance — live cTrader broker (8767) first."""
        retries = max(1, int(broker_retries))
        delay = max(0.0, float(broker_delay_s))
        for attempt in range(retries):
            live = self._fetch_broker_balance()
            if live:
                return live
            if attempt < retries - 1 and delay > 0:
                print(
                    f"⚠️  Broker 8767 unavailable "
                    f"(attempt {attempt + 1}/{retries}), retrying in {delay:.0f}s..."
                )
                time.sleep(delay)

        # OFFLINE FALLBACK: trade_history.json cache
        try:
            th_path = Path(__file__).parent / 'trade_history.json'
            if th_path.exists():
                with open(th_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                account = data.get('account', {})
                equity = float(account.get('equity', 0))
                balance = float(account.get('balance', 0))
                if equity > 0 or balance > 0:
                    print("⚠️  Using cached trade_history.json (broker offline)")
                    return equity, balance
        except Exception as e:
            print(f"⚠️  trade_history.json read error: {e}")

        # FALLBACK: SQLite account_snapshots
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT equity, balance 
                FROM account_snapshots 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            result = cursor.fetchone()
            conn.close()
            if result:
                equity, balance = result
                return float(equity), float(balance)
        except Exception as e:
            print(f"⚠️  Error reading balance from SQLite: {e}")

        # LAST RESORT: env variable
        balance = float(os.getenv('ACCOUNT_BALANCE', 1000))
        return balance, balance

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Fix #8: PIP VALUE DINAMIC — valoare reală USD per pip per lot standard
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _get_pip_value(self, symbol: str) -> float:
        """
        Fix #8: Returnează valoarea reală a unui pip în USD per lot standard (100k units).

        Logica:
        - Dacă quote currency = USD: pip_value = $10 (fix, nu se schimbă)
        - Dacă quote currency != USD: pip_value = 10 / (USD/QuoteCcy rate)
            e.g. GBPJPY: pip = 0.01 JPY; 1000 JPY / USDJPY rate = USD pip value
            e.g. GBPNZD: pip = 0.0001 NZD; 10 NZD / NZDUSE rate (sau 10 * NZDUSD)

        Rate-urile live sunt citite din trade_history.json (scris de cTrader la 30s).
        Fallback la valori statice calibrate dacă fişierul lipseşte.
        """
        sc = symbol.upper().replace('/', '').replace(' ', '')

        # ── Perechi direct USD-quoted: pip = $10 exact ─────────────────────────
        usd_quoted = ('EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'XAUUSD', 'XAGUSD',
                      'BTCUSD', 'ETHUSD', 'XTIUSD')
        if sc in usd_quoted or sc.endswith('USD'):
            return 10.0  # $10 per pip per standard lot — exact

        # ── JPY-quoted pairs: 1 pip = 0.01 JPY; 1000 JPY per lot per pip ────────
        # pip_value_USD = 1000 / USDJPY
        if sc.endswith('JPY'):
            usdjpy_rate = self._get_live_rate('USDJPY', fallback=150.0)
            pv = 1000.0 / usdjpy_rate
            print(f"   [Fix #8] {symbol}: pip_value = 1000 / {usdjpy_rate:.3f} = ${pv:.3f}")
            return pv

        # ── CAD-quoted pairs (USDCAD, GBPCAD): pip_value = 10 / USDCAD ─────────
        if sc.endswith('CAD'):
            usdcad_rate = self._get_live_rate('USDCAD', fallback=1.36)
            pv = 10.0 / usdcad_rate
            print(f"   [Fix #8] {symbol}: pip_value = 10 / {usdcad_rate:.4f} = ${pv:.3f}")
            return pv

        # ── CHF-quoted pairs (USDCHF, EURCHF): pip_value = 10 / USDCHF ────────
        if sc.endswith('CHF'):
            usdchf_rate = self._get_live_rate('USDCHF', fallback=0.895)
            pv = 10.0 / usdchf_rate
            print(f"   [Fix #8] {symbol}: pip_value = 10 / {usdchf_rate:.4f} = ${pv:.3f}")
            return pv

        # ── GBP-quoted pairs (EURGBP): pip_value = 10 * GBPUSD ──────────────
        if sc.endswith('GBP'):
            gbpusd_rate = self._get_live_rate('GBPUSD', fallback=1.27)
            pv = 10.0 * gbpusd_rate
            print(f"   [Fix #8] {symbol}: pip_value = 10 * {gbpusd_rate:.4f} = ${pv:.3f}")
            return pv

        # ── NZD-quoted pairs (GBPNZD, AUDNZD): pip_value = 10 * NZDUSD ───────
        if sc.endswith('NZD'):
            nzdusd_rate = self._get_live_rate('NZDUSD', fallback=0.60)
            pv = 10.0 * nzdusd_rate
            print(f"   [Fix #8] {symbol}: pip_value = 10 * {nzdusd_rate:.4f} = ${pv:.3f}")
            return pv

        # ── AUD-quoted pairs: pip_value = 10 * AUDUSD ────────────────────
        if sc.endswith('AUD'):
            audusd_rate = self._get_live_rate('AUDUSD', fallback=0.64)
            pv = 10.0 * audusd_rate
            print(f"   [Fix #8] {symbol}: pip_value = 10 * {audusd_rate:.4f} = ${pv:.3f}")
            return pv

        # ── Default fallback (EUR-quoted, etc.): $10 cu warning ────────────
        print(f"   [Fix #8] {symbol}: quote currency necunoscută — fallback $10/pip")
        return 10.0

    def _get_live_rate(self, pair: str, fallback: float = 1.0) -> float:
        """
        Fix #8: Citeşte rata de schimb live din trade_history.json.
        trade_history.json este scris de cTrader sync daemon la fiecare 30s
        şi conține prețurile curente ale perechilor active.
        """
        try:
            th_path = Path(__file__).parent / 'trade_history.json'
            if th_path.exists():
                with open(th_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # trade_history.json poate stoca prețuri în 'prices' sau 'rates'
                prices = data.get('prices', data.get('rates', {}))
                clean = pair.upper().replace('/', '').replace(' ', '')
                rate = prices.get(clean) or prices.get(pair.upper())
                if rate and float(rate) > 0:
                    return float(rate)
        except Exception:
            pass
        return fallback  # valoare statică calibrată ca fallback
    # ━━━ END Fix #8 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_daily_pnl(self) -> dict:
        """
        Calculate P&L for today.

        ✅ V10.9 FIX: Only count:
        1. Trades CLOSED today (realized P&L)
        2. Floating P&L of positions OPENED today (not multi-day carries)

        Positions opened on PREVIOUS days (e.g. USDJPY from March 6)
        are NOT counted — their floating P&L should not block new trades.

        ✅ V11.8 FIX: Use reset_timestamp from daily_state.json as cutoff.
        Manual resets (e.g. after intentional position closure) set a new
        reset_timestamp — trades closed BEFORE that timestamp are excluded,
        preventing ghost losses from triggering daily loss limit.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            today = datetime.now().date().isoformat()

            # V11.8: Read reset_timestamp from daily_state.json (cutoff for closed trades)
            reset_cutoff = None
            try:
                if self.daily_state_file.exists():
                    with open(self.daily_state_file, 'r', encoding='utf-8') as _f:
                        _state = json.load(_f)
                    _ts = _state.get('reset_timestamp')
                    if _ts:
                        reset_cutoff = _ts  # ISO string e.g. "2026-03-26T15:07:09"
            except Exception:
                pass

            # 1. Closed trades today (realized) — only AFTER reset_timestamp
            if reset_cutoff:
                cursor.execute("""
                    SELECT SUM(profit)
                    FROM closed_trades
                    WHERE DATE(close_time) = ?
                      AND close_time >= ?
                """, (today, reset_cutoff))
                print(f"📊 Daily PnL cutoff: {reset_cutoff} (V11.8 reset-aware)")
            else:
                cursor.execute("""
                    SELECT SUM(profit)
                    FROM closed_trades
                    WHERE DATE(close_time) = ?
                """, (today,))
            closed_pnl = cursor.fetchone()[0] or 0.0

            conn.close()

            # 2. Floating P&L of positions opened TODAY only
            open_pnl_today = 0.0
            try:
                import json as _json
                active_file = Path(self.db_path).parent / 'active_positions.json'
                if active_file.exists():
                    with open(active_file, encoding='utf-8') as _f:
                        active = _json.load(_f)
                    for pos in active:
                        opened_at = pos.get('opened_at', '')
                        if not opened_at:
                            continue
                        if reset_cutoff:
                            if opened_at < reset_cutoff:
                                continue
                        elif opened_at[:10] != today:
                            continue
                        open_pnl_today += float(pos.get('net_profit', 0))
            except Exception:
                pass

            total_pnl = float(closed_pnl) + float(open_pnl_today)

            return {
                'closed_pnl': float(closed_pnl),
                'open_pnl': float(open_pnl_today),
                'total_pnl': total_pnl
            }
            
        except Exception as e:
            print(f"⚠️  Error calculating daily P&L: {e}")
            return {'closed_pnl': 0, 'open_pnl': 0, 'total_pnl': 0}
    
    def _symbol_has_open_position(self, symbol: str) -> bool:
        """
        🛡️ V7.1 DUPLICATE GUARD: Check if symbol already has an open position at broker.
        Reads active_positions.json (written by cBot every 10s in ExportActivePositions).
        
        Returns True if symbol already has a Glitch Matrix position → trade should be REJECTED.
        """
        try:
            if not self.active_positions_file.exists():
                print(f"⚠️  active_positions.json not found — cannot verify broker state, ALLOWING trade")
                return False
            
            with open(self.active_positions_file, 'r', encoding='utf-8') as f:
                positions = json.load(f)
            
            if not isinstance(positions, list):
                return False
            
            # Normalize symbol for comparison (remove /, spaces, case-insensitive)
            clean_symbol = symbol.upper().replace("/", "").replace(" ", "")
            
            count = 0
            for pos in positions:
                pos_symbol = pos.get('symbol', '').upper().replace("/", "").replace(" ", "")
                if pos_symbol == clean_symbol:
                    count += 1
            
            if count >= self.max_positions_per_symbol:
                print(f"🛡️ DUPLICATE GUARD: {symbol} has {count} position(s) at broker (max: {self.max_positions_per_symbol})")
                return True
            
            return False
            
        except Exception as e:
            print(f"⚠️  Error checking broker positions for {symbol}: {e} — ALLOWING trade (fail-open)")
            return False
    
    def get_open_positions_count(self):
        """
        Get number of open positions from cTrader LIVE SYNC
        
        ✅ V10.2 LIVE SYNC: Reads from account_info.json written by cTrader cBot
        - Eliminates desync (Python counter vs cTrader reality)
        - Real-time position count from live broker
        - Counts ALL positions (bot + manual) for accurate risk limit
        - Fallback to SQLite if file not available
        """
        try:
            # ✅ PRIMARY: Read from cTrader live status file
            account_info_path = Path('account_info.json')
            if account_info_path.exists():
                with open(account_info_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # ✅ CRITICAL: Use TotalPositions (bot + manual trades) for risk limit
                # This prevents opening more trades than account can handle
                total_count = data.get('TotalPositions', 0)
                glitch_count = data.get('OpenPositionsCount', 0)
                
                # Verify file freshness (warn if older than 10 seconds)
                timestamp_str = data.get('Timestamp', '')
                if timestamp_str:
                    try:
                        from datetime import datetime, timezone
                        file_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        age_seconds = (datetime.now(timezone.utc) - file_time).total_seconds()
                        
                        if age_seconds > 30:  # VPS: relaxed to 30s (cBot + Python on same machine)
                            print(f"⚠️  account_info.json is {age_seconds:.0f}s old (cBot may be offline!)")
                    except:
                        pass  # Ignore timestamp parsing errors
                
                print(f"✅ LIVE SYNC: {total_count} total positions ({glitch_count} from bot) - Real cTrader count")
                return total_count  # Use total for position limit check
            
            # ❌ FALLBACK: Use SQLite if live file missing (cBot offline?)
            print(f"⚠️  account_info.json not found - using SQLite fallback")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM open_positions")
            count = cursor.fetchone()[0]
            
            conn.close()
            print(f"📊 SQLite count: {count} positions")
            return count
            
        except Exception as e:
            print(f"⚠️  Error counting positions: {e}")
            return 0
    
    def check_kill_switch(self):
        """Check if kill switch is active - DISABLED (always returns False)"""
        # DISABLED - Kill switch removed, will redesign later
        return False
    
    def activate_kill_switch(self, reason="Daily loss limit reached"):
        """Activate kill switch - DISABLED, will redesign later"""
        # DISABLED - Kill switch removed
        print(f"\n⚠️ KILL SWITCH DISABLED - Would have triggered: {reason}")
        print(f"   System continues trading normally.")
        return False
    
    def deactivate_kill_switch(self):
        """Deactivate kill switch - resume trading"""
        try:
            if self.kill_switch_file.exists():
                self.kill_switch_file.unlink()
                print(f"\n🟢 KILL SWITCH DEACTIVATED")
                print(f"   Trading resumed")
                
                # Send Telegram notification
                sep = "────────────────"
                message = (
                    f"🟢 <b>KILL SWITCH DEACTIVATED</b>\n\n"
                    f"Trading has been resumed.\n"
                    f"System is now accepting new signals.\n\n"
                    f"  {sep}\n"
                    f"  🔱 <b>AUTHORED BY ФорексГод</b> 🔱\n"
                    f"  {sep}\n"
                    f"  🏛️  <b>Глитч Ин Матрикс</b>  🏛️"
                )
                self._send_telegram(message)
                
                return True
            else:
                print("⚠️  Kill switch not active")
                return False
                
        except Exception as e:
            print(f"❌ Error deactivating kill switch: {e}")
            return False
    
    def _manual_resume_active(self) -> bool:
        """V37.10 / V39.1: /resume manual — bypass daily loss pana la 00:05 ora Romaniei."""
        try:
            resume_marker = Path(__file__).parent / 'data' / 'system_resumed.json'
            if not resume_marker.exists():
                return False
            with open(resume_marker, 'r', encoding='utf-8') as f:
                data = json.load(f)
            resumed_at_str = data.get('resumed_at', '')
            if not resumed_at_str:
                return False
            resumed_at = datetime.fromisoformat(resumed_at_str.replace('Z', '+00:00'))
            if resumed_at.tzinfo is None:
                resumed_at = resumed_at.replace(tzinfo=datetime.now().astimezone().tzinfo)
            if TZ_RO:
                today_ro = datetime.now(TZ_RO).strftime('%Y-%m-%d')
                resumed_day_ro = resumed_at.astimezone(TZ_RO).strftime('%Y-%m-%d')
                return resumed_day_ro == today_ro
            return resumed_at.date() == datetime.now().date()
        except Exception:
            return False

    def _force_bypass_loss_limit_active(self) -> bool:
        """V39.1: Flag explicit din daily_state.json — supravietuieste refresh-ului in-memory."""
        if getattr(self, '_force_bypass_loss_limit', False):
            return True
        try:
            if not self.daily_state_file.exists():
                return False
            with open(self.daily_state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            if state.get('date') != self._today_ro():
                return False
            active = bool(state.get('force_bypass_loss_limit', False))
            self._force_bypass_loss_limit = active
            return active
        except Exception:
            return False

    def _loss_limit_bypassed(self) -> bool:
        """V39.1: Colonel /resume sau force_bypass_loss_limit din JSON."""
        return self._manual_resume_active() or self._force_bypass_loss_limit_active()

    def compute_lot_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        risk_override_percent: float = None,
        balance: float = None,
    ) -> float:
        """
        V48: Single source of truth for lot sizing — no gates, no side effects.
        Used by setup_executor preview, Guard#3 sentinel, and validate_new_trade().
        """
        if entry_price <= 0 or stop_loss <= 0:
            return 0.01
        if balance is None or balance <= 0:
            _, balance = self.get_account_balance()
        if balance <= 0:
            balance = float(os.getenv('ACCOUNT_BALANCE', 1336))

        effective_risk_pct = (
            risk_override_percent if risk_override_percent is not None else self.risk_per_trade
        )
        risk_amount = balance * (effective_risk_pct / 100.0)
        sl_distance = abs(entry_price - stop_loss)
        symbol_clean = symbol.upper().replace(' ', '').replace('/', '')

        if 'BTC' in symbol_clean:
            pip_size = 1.0
            pip_value = 1.0
        elif any(x in symbol_clean for x in ['ETH', 'XRP', 'LTC', 'ADA']):
            pip_size = 1.0
            pip_value = 1.0
        elif any(x in symbol_clean for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
            pip_size = 0.01
            pip_value = 10.0
        elif 'JPY' in symbol_clean:
            pip_size = 0.01
            pip_value = self._get_pip_value(symbol)
        elif any(x in symbol_clean for x in ['XTI', 'WTI', 'OIL']):
            pip_size = 0.01
            pip_value = 10.0
        else:
            pip_size = 0.0001
            pip_value = self._get_pip_value(symbol)

        sl_pips = sl_distance / pip_size
        if sl_pips <= 0:
            return 0.01

        lot_size = risk_amount / (sl_pips * pip_value)
        lot_size = round(lot_size, 2)
        min_lot = self.config['lot_size']['min_lot']
        max_lot = self.config['lot_size']['max_lot']
        lot_size = max(min_lot, min(lot_size, max_lot))
        if lot_size < 0.01:
            lot_size = 0.01
        return lot_size

    def estimate_loss_at_sl(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        lot_size: float,
    ) -> float:
        """V48: USD loss if SL hit (for Guard#3 sentinel)."""
        if entry_price <= 0 or stop_loss <= 0 or lot_size <= 0:
            return 0.0
        symbol_clean = symbol.upper().replace(' ', '').replace('/', '')
        sl_distance = abs(entry_price - stop_loss)
        if 'BTC' in symbol_clean or any(x in symbol_clean for x in ['ETH', 'XRP', 'LTC', 'ADA']):
            return lot_size * sl_distance
        if any(x in symbol_clean for x in ['XAU', 'XAG', 'GOLD', 'SILVER', 'XTI', 'WTI', 'OIL']):
            pip_size = 0.01
            pip_value = 10.0
        elif 'JPY' in symbol_clean:
            pip_size = 0.01
            pip_value = self._get_pip_value(symbol)
        else:
            pip_size = 0.0001
            pip_value = self._get_pip_value(symbol)
        sl_pips = sl_distance / pip_size if pip_size > 0 else 0
        return lot_size * sl_pips * pip_value

    def validate_new_trade(self, symbol="", direction="", entry_price=0, stop_loss=0,
                           risk_override_percent: float = None):
        """
        Validate if new trade is allowed based on all risk rules

        Args:
            symbol, direction, entry_price, stop_loss: trade parameters
            risk_override_percent: V14.1 — optional risk % override for scale-in Entry 2.
                                   If None, uses SUPER_CONFIG risk_per_trade_percent (5%).
                                   Entry 2 passes 7.5% for a slightly larger lot.
        
        Returns:
            dict: {
                'approved': bool,
                'reason': str,
                'lot_size': float
            }
        """
        result = {
            'approved': False,
            'reason': None,
            'lot_size': 0.0,
            'deep_sleep': False  # V9.3: Signal setup_executor to enter Deep Sleep
        }

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🇷🇴 V14.0 MANDATORY ROLLOVER PAUSE — 00:00 → 01:05 EET
        # Executor BLOCKED during rollover. Scanner remains active.
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        now_ro = self._now_ro()
        ro_hour   = now_ro.hour
        ro_minute = now_ro.minute
        in_rollover = (ro_hour == 0) or (ro_hour == 1 and ro_minute < 5)
        if in_rollover:
            result['reason'] = f"Rollover pause: 00:00–01:05 EET (now {ro_hour:02d}:{ro_minute:02d} EET)"
            print(f"⏳ TRADE BLOCKED [ROLLOVER]: {result['reason']}")
            return result

        # 1. Kill switch check - DISABLED (will redesign later)
        # if self.check_kill_switch():
        #     result['reason'] = "Kill switch active - Trading disabled"
        #     print(f"⛔ TRADE REJECTED: {result['reason']}")
        #     return result
        
        # 🛡️ V7.1 DUPLICATE GUARD: Check if symbol already has position at broker
        if self._symbol_has_open_position(symbol):
            result['reason'] = f"Duplicate guard: {symbol} already has open position at broker (max {self.max_positions_per_symbol} per symbol)"
            print(f"🛡️ TRADE REJECTED: {result['reason']}")
            return result
        
        # 2. Check position count
        open_positions = self.get_open_positions_count()
        if open_positions >= self.max_positions:
            result['reason'] = f"Max positions reached ({open_positions}/{self.max_positions})"
            print(f"⛔ TRADE REJECTED: {result['reason']}")
            self._send_rejection_alert(symbol, direction, result['reason'])
            return result
        
        # ✅ Load daily state fresh (long-running executor poate rata /resume de pe disk)
        self._refresh_daily_state_from_disk()

        # 3. Check daily loss
        pnl = self.get_daily_pnl()
        equity, balance = self.get_account_balance()
        daily_loss_pct = self._calc_daily_loss_pct(pnl['total_pnl'], balance)
        _resume_override = self._loss_limit_bypassed()
        
        # Kill switch auto-activation - DISABLED (will redesign later)
        # if self.kill_switch_enabled and daily_loss_pct <= -self.kill_switch_trigger:
        #     self.activate_kill_switch(f"Daily loss {daily_loss_pct:.2f}% >= {self.kill_switch_trigger}%")
        #     result['reason'] = f"Kill switch activated - Daily loss {daily_loss_pct:.2f}%"
        #     print(f"🔴 TRADE REJECTED: {result['reason']}")
        #     return result
        
        # Check daily loss limit → V9.3 DEEP SLEEP: Signal executor to stop ALL scanning
        if daily_loss_pct <= -self.max_daily_loss_pct and not _resume_override:
            result['reason'] = f"Daily loss limit reached ({daily_loss_pct:.2f}%)"
            result['deep_sleep'] = True
            print(f"😴 DEEP SLEEP TRIGGER: {result['reason']}")
            self._send_rejection_alert(symbol, direction, result['reason'])
            return result
        elif daily_loss_pct <= -self.max_daily_loss_pct and _resume_override:
            print(
                f"🔱 [V37.12] Daily loss {daily_loss_pct:.2f}% >= -{self.max_daily_loss_pct}% "
                f"DAR /resume manual activ — trade PERMIS, fara alerte"
            )

        # Warning doar fara /resume manual (Colonelul a acceptat riscul)
        if not _resume_override and daily_loss_pct <= -self.daily_warning_pct:
            self._send_warning_alert(daily_loss_pct, balance, pnl['total_pnl'])
        
        # 4. Calculate lot size — V48: delegated to compute_lot_size()
        if entry_price > 0 and stop_loss > 0:
            effective_risk_pct = (
                risk_override_percent if risk_override_percent is not None else self.risk_per_trade
            )
            lot_size = self.compute_lot_size(
                symbol, entry_price, stop_loss, effective_risk_pct, balance=balance,
            )
            risk_amount = balance * (effective_risk_pct / 100.0)
            sl_distance = abs(entry_price - stop_loss)
            print(f"\n[LOT CALCULATION] {symbol}")
            print(f"   Risk Amount: ${risk_amount:.2f} ({effective_risk_pct:.1f}%)")
            print(f"   SL Distance: {sl_distance:.5f}")
            print(f"   Calculated Lot: {lot_size:.2f}")
            result['lot_size'] = lot_size
        else:
            result['lot_size'] = 0.01
            print(f"⚠️  Invalid SL distance, defaulting to 0.01 lots")
        
        # All checks passed
        result['approved'] = True
        result['reason'] = "All risk checks passed"
        
        # ✅ NEW: Increment trade counter and save state
        self.daily_trades_count += 1
        self._save_daily_state()
        
        print(f"\n✅ TRADE APPROVED: {symbol} {direction}")
        print(f"   Open positions: {open_positions}/{self.max_positions}")
        print(f"   Daily P&L: ${pnl['total_pnl']:.2f} ({daily_loss_pct:.2f}%)")
        print(f"   Lot size: {result['lot_size']}")
        
        return result
    
    def _send_rejection_alert(self, symbol, direction, reason):
        """
        V9.1 SILENT REJECTION: Send Telegram ONLY on state change or after 4h cooldown.
        Anti-spam fix by ФорексГод — prevents hundreds of 'Daily loss limit' notifications.
        
        Logic:
        - First rejection for this reason category → SEND
        - Same reason, <4 hours since last alert → SILENT (log only)
        - Same reason, >4 hours elapsed → SEND (reminder)
        - Reason CHANGED (e.g. max_positions → daily_loss) → SEND
        """
        # Categorize the reason for cooldown grouping
        if 'daily loss' in reason.lower() or 'loss limit' in reason.lower():
            cooldown_key = 'daily_loss_limit'
        elif 'max positions' in reason.lower():
            cooldown_key = 'max_positions'
        elif 'duplicate' in reason.lower():
            cooldown_key = f'duplicate_{symbol}'
        elif 'kill switch' in reason.lower():
            cooldown_key = 'kill_switch'
        else:
            cooldown_key = f'other_{symbol}'
        
        now = datetime.now()
        should_send = False
        
        if cooldown_key not in self._rejection_cooldown:
            # First rejection for this category → SEND
            should_send = True
        else:
            last_data = self._rejection_cooldown[cooldown_key]
            elapsed_hours = (now - last_data['last_sent']).total_seconds() / 3600
            
            if elapsed_hours >= self.REJECTION_COOLDOWN_HOURS:
                # Cooldown expired → SEND reminder
                should_send = True
            else:
                # Within cooldown → SILENT, just increment counter
                last_data['count'] += 1
                suppressed = last_data['count']
                remaining_h = self.REJECTION_COOLDOWN_HOURS - elapsed_hours
                print(f"🔇 SILENT REJECTION #{suppressed}: {symbol} {direction} — {reason} (next alert in {remaining_h:.1f}h)")
                return  # ← EXIT: No Telegram notification
        
        # Track this send
        self._rejection_cooldown[cooldown_key] = {
            'last_sent': now,
            'count': 0,
            'reason': reason
        }
        
        # Build and send
        sep = "────────────────"
        message = (
            f"⛔ <b>TRADE REJECTED</b>\n\n"
            f"Symbol: <b>{symbol}</b>\n"
            f"Direction: <b>{direction}</b>\n"
            f"Reason: <i>{reason}</i>\n\n"
            f"🔇 <i>Next alert for this reason in {self.REJECTION_COOLDOWN_HOURS}h</i>\n\n"
            f"  {sep}\n"
            f"  🔱 <b>AUTHORED BY ФорексГод</b> 🔱\n"
            f"  {sep}\n"
            f"  🏛️  <b>Глитч Ин Матрикс</b>  🏛️"
        )
        self._send_telegram(message)
    
    def _send_warning_alert(self, daily_loss_pct, balance, total_pnl=None):
        """
        V9.1: Send warning with 4h cooldown — max 1 warning per 4 hours.
        Anti-spam fix by ФорексГод.
        """
        if self._loss_limit_bypassed():
            return
        now = datetime.now()
        cooldown_key = 'daily_loss_warning'
        
        if cooldown_key in self._warning_cooldown:
            elapsed_hours = (now - self._warning_cooldown[cooldown_key]['last_sent']).total_seconds() / 3600
            if elapsed_hours < self.WARNING_COOLDOWN_HOURS:
                print(f"🔇 SILENT WARNING: Daily loss {daily_loss_pct:.2f}% (next alert in {self.WARNING_COOLDOWN_HOURS - elapsed_hours:.1f}h)")
                return  # ← SILENT
        
        self._warning_cooldown[cooldown_key] = {'last_sent': now}
        
        if total_pnl is None:
            pnl = self.get_daily_pnl()
            total_pnl = pnl['total_pnl']
        else:
            total_pnl = total_pnl
        
        sep = "────────────────"
        message = (
            f"⚠️ <b>DAILY LOSS WARNING</b>\n\n"
            f"Current loss: <b>{daily_loss_pct:.2f}%</b>\n"
            f"Warning threshold: <b>{self.daily_warning_pct}%</b>\n"
            f"Kill switch trigger: <b>{self.kill_switch_trigger}%</b>\n\n"
            f"💰 Balance: ${balance:.2f}\n"
            f"📊 Today's P&L: ${total_pnl:.2f}\n\n"
            f"🔇 <i>Next warning in {self.WARNING_COOLDOWN_HOURS}h</i>\n\n"
            f"  {sep}\n"
            f"  🔱 <b>AUTHORED BY ФорексГод</b> 🔱\n"
            f"  {sep}\n"
            f"  🏛️  <b>Глитч Ин Матрикс</b>  🏛️"
        )
        self._send_telegram(message)
    
    def _send_kill_switch_alert(self, reason):
        """Send kill switch activation alert"""
        pnl = self.get_daily_pnl()
        equity, balance = self.get_account_balance()
        daily_loss_pct = (pnl['total_pnl'] / balance) * 100 if balance > 0 else 0
        
        sep = "────────────────"
        message = (
            f"🔴 <b>KILL SWITCH ACTIVATED!</b> 🔴\n\n"
            f"<b>Reason:</b> {reason}\n\n"
            f"──────────────────\n"
            f"📊 <b>DAILY SUMMARY:</b>\n"
            f"💰 Balance: ${balance:.2f}\n"
            f"💎 Equity: ${equity:.2f}\n"
            f"📉 Daily P&L: ${pnl['total_pnl']:.2f} ({daily_loss_pct:.2f}%)\n"
            f"🛑 Loss limit: {self.max_daily_loss_pct}%\n\n"
            f"⛔ <b>ALL TRADING STOPPED</b>\n"
            f"Existing positions remain open.\n\n"
            f"  {sep}\n"
            f"  🔱 <b>AUTHORED BY ФорексГод</b> 🔱\n"
            f"  {sep}\n"
            f"  🏛️  <b>Глитч Ин Матрикс</b>  🏛️"
        )
        self._send_telegram(message)
    
    def _send_telegram(self, message):
        """Send message to Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️  Telegram credentials missing")
            return False
        
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            'chat_id': self.telegram_chat_id,
            'text': message.strip(),
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Telegram error: {e}")
            return False
    
    def send_daily_summary(self):
        """Send daily risk management summary"""
        pnl = self.get_daily_pnl()
        equity, balance = self.get_account_balance()
        open_positions = self.get_open_positions_count()
        daily_loss_pct = (pnl['total_pnl'] / balance) * 100 if balance > 0 else 0
        
        # Status emoji
        if pnl['total_pnl'] >= 0:
            status = "🟢 PROFIT"
        elif daily_loss_pct > -self.daily_warning_pct:
            status = "🟡 MINOR LOSS"
        else:
            status = "🔴 WARNING"
        
        kill_switch_status = "🔴 ACTIVE" if self.check_kill_switch() else "🟢 INACTIVE"
        
        message = (
            f"{status}\n"
            "──────────────────\n"
            "📊 <b>DAILY RISK SUMMARY</b>\n"
            "──────────────────\n\n"
            f"💰 <b>Balance:</b> ${balance:.2f}\n"
            f"💎 <b>Equity:</b> ${equity:.2f}\n"
            f"📈 <b>Open Positions:</b> {open_positions}/{self.max_positions}\n\n"
            "──────────────────\n"
            "📉 <b>TODAY'S P&L:</b>\n"
            f"💵 Closed: ${pnl['closed_pnl']:.2f}\n"
            f"📊 Open: ${pnl['open_pnl']:.2f}\n"
            f"💎 <b>Total: ${pnl['total_pnl']:.2f} ({daily_loss_pct:.2f}%)</b>\n\n"
            "──────────────────\n"
            "🛡️ <b>RISK LIMITS:</b>\n"
            f"⚠️  Warning: {self.daily_warning_pct}%\n"
            f"🛑 Daily limit: {self.max_daily_loss_pct}%\n"
            f"🔴 Kill switch: {self.kill_switch_trigger}%\n"
            f"🚦 Status: {kill_switch_status}\n\n"
            "  ────────────────\n"
            "  🔱 <b>AUTHORED BY ФорексГод</b> 🔱\n"
            "  ────────────────\n"
            "  🏛️  <b>Глитч Ин Матрикс</b>  🏛️"
        )
        
        self._send_telegram(message)
        print("\n✅ Daily summary sent to Telegram")


def main():
    """Main entry point"""
    import sys
    
    risk_manager = UnifiedRiskManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == '--summary':
            risk_manager.send_daily_summary()
        
        elif command == '--validate':
            # Test validation
            result = risk_manager.validate_new_trade(
                symbol='EURUSD',
                direction='BUY',
                entry_price=1.0850,
                stop_loss=1.0800
            )
            print(f"\nValidation result: {result}")
        
        elif command == '--kill-switch-on':
            risk_manager.activate_kill_switch("Manual activation")
        
        elif command == '--kill-switch-off':
            risk_manager.deactivate_kill_switch()
        
        elif command == '--check':
            pnl = risk_manager.get_daily_pnl()
            equity, balance = risk_manager.get_account_balance()
            positions = risk_manager.get_open_positions_count()
            kill_switch = risk_manager.check_kill_switch()
            
            print(f"\n📊 RISK STATUS:")
            print(f"──────────────────")
            print(f"💰 Balance: ${balance:.2f}")
            print(f"💎 Equity: ${equity:.2f}")
            print(f"📈 Positions: {positions}/{risk_manager.max_positions}")
            print(f"📊 Daily P&L: ${pnl['total_pnl']:.2f}")
            print(f"🚦 Kill switch: {'🔴 ACTIVE' if kill_switch else '🟢 INACTIVE'}")
            print(f"──────────────────\n")
        
        else:
            print(f"Unknown command: {command}")
            print("Available commands:")
            print("  --summary       Send daily summary")
            print("  --validate      Test trade validation")
            print("  --kill-switch-on   Activate kill switch")
            print("  --kill-switch-off  Deactivate kill switch")
            print("  --check         Show current risk status")
    
    else:
        # Default: check risk status
        risk_manager.send_daily_summary()


if __name__ == '__main__':
    main()
