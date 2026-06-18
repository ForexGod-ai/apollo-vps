"""
Setup Executor Monitor — V31/V36 Radar-only execution layer

Arhitectura 3 straturi (Apollo / Glitch in Matrix):
1. daily_scanner.py + smc_detector.scan_for_setup() → monitoring_setups.json + Telegram
2. multi_tf_radar.py V36.5 → scan H4/H1 Always-On, EXECUTE_NOW, h4_structure_locked
3. setup_executor_monitor.py (acest script) → signals.json → cTrader VPS port 8010

V31.0+ EXECUTOR BLIND:
- NU face analiză SMC proprie (_check_radar_entry / _check_pullback_entry = stub)
- Singurul trigger de execuție Entry 1: EXECUTE_NOW=True setat de Radar
- V37.2: SL live 4H obligatoriu la EXECUTE_NOW (min 30p); JSON nu mai poate impune micro-stop
- V37.0: Entry 2 scale-in dezactivat (validate_choch_confirmation_scale_in)

Sentinela _final_safety_check (Fix #13): RR net ≥ 1:2, SL cap, capital guard, h4_structure_locked

Ciclu: citește monitoring_setups.json la ~5s, merge-safe write-back, anti-duplicate broker guard.
"""
# Windows VPS fix: force UTF-8 stdout to prevent UnicodeEncodeError on emoji
import sys as _sys, io as _io, re as _re
if hasattr(_sys.stdout, 'buffer'):
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(_sys.stderr, 'buffer'):
    _sys.stderr = _io.TextIOWrapper(_sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import time
import requests
from pathlib import Path
from loguru import logger
from datetime import datetime, timedelta, timezone
import sys
import os
import psutil
import pandas as pd

# ━━━ Fix #5a: UTC via datetime.now(timezone.utc) — os.environ TZ eliminat ━━━
# Toate timestamp-urile folosesc datetime.now(timezone.utc) explicit.
# os.environ['TZ'] + time.tzset() eliminat: afecta procesul global și nu era portabil.

_LOG_DIR = Path(__file__).parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

# V30.4: Full ASCII log — elimina emoji + diacritice + simboluri Unicode
# Rezultat: Get-Content setup_monitor.log arata curat in orice PowerShell/cmd

# Diacritice romanesti + simboluri Unicode frecvente → echivalente ASCII
_ASCII_MAP = str.maketrans({
    'ă': 'a', 'â': 'a', 'î': 'i', 'ș': 's', 'ț': 't',
    'Ă': 'A', 'Â': 'A', 'Î': 'I', 'Ș': 'S', 'Ț': 'T',
    # Variante cu cedila (tastaturi vechi)
    'ş': 's', 'ţ': 't', 'Ş': 'S', 'Ţ': 'T',
    # Simboluri des intalnite in log-uri
    '\u2014': '--',   # em dash —
    '\u2013': '-',    # en dash –
    '\u2192': '->',   # →
    '\u2190': '<-',   # ←
    '\u2191': '^',    # ↑
    '\u2193': 'v',    # ↓
    '\u2265': '>=',   # ≥
    '\u2264': '<=',   # ≤
    '\u00d7': 'x',    # ×
    '\u00b7': '.',    # ·
    '\u2022': '*',    # •
    '\u2018': "'",    '\u2019': "'",   # smart quotes
    '\u201c': '"',    '\u201d': '"',   # smart double quotes
    '\u00e9': 'e',    '\u00e8': 'e',   # é è
    '\u00e0': 'a',    '\u00e2': 'a',   # à â (fr)
    '\u2248': '~=',   # ≈
    '\u00b0': 'deg',  # °
    '\u03c3': 'sigma', '\u03bc': 'mu', # σ μ
    '\u2260': '!=',   # ≠
    '\u00b1': '+/-',  # ±
})

_EMOJI_RE = _re.compile(
    u"[\U00010000-\U0010ffff"
    u"\U0001F300-\U0001F9FF"
    u"\u2600-\u26FF"
    u"\u2700-\u27BF"
    u"\u2300-\u23FF"
    u"\u2B00-\u2BFF"
    u"\u25A0-\u25FF"
    u"\u2400-\u243F"
    u"\uFE00-\uFE0F]+",
    flags=_re.UNICODE
)
_LEVEL_PREFIX = {
    "DEBUG":    "[DEBUG]",
    "INFO":     "[INFO] ",
    "SUCCESS":  "[OK]   ",
    "WARNING":  "[WARN] ",
    "ERROR":    "[ERROR]",
    "CRITICAL": "[CRIT] ",
}

def _clean_filter(record):
    """Produce ASCII pur: emoji + diacritice + Unicode → echivalente ASCII lizibile."""
    msg = _EMOJI_RE.sub("", record["message"]).strip()
    msg = msg.translate(_ASCII_MAP)
    msg = msg.encode('ascii', errors='ignore').decode('ascii')  # drop orice ramas
    prefix = _LEVEL_PREFIX.get(record["level"].name, "")
    record["message"] = f"{prefix} {msg}" if prefix else msg
    return True

logger.remove()  # Scoate sink-ul default (stderr cu emoji)
logger.add(
    str(_LOG_DIR / "setup_executor_monitor.log"),
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
    filter=_clean_filter,
    level="DEBUG",
    rotation="10 MB",
    retention="7 days",
    compression="zip"
)
# Scrie si pe stdout → capturat in setup_monitor.log de Start-Process
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    filter=_clean_filter,
    level="INFO",
    colorize=False
)


def acquire_pid_lock(lock_file: Path) -> bool:
    """
    🔒 PID LOCK SINGLETON PATTERN - Prevents duplicate process instances
    Returns True if lock acquired, False if another instance is already running
    """
    try:
        if lock_file.exists():
            # Read existing PID
            with open(lock_file, 'r', encoding='utf-8') as f:
                old_pid = int(f.read().strip())
            
            # Check if process is still running
            if psutil.pid_exists(old_pid):
                try:
                    proc = psutil.Process(old_pid)
                    # Verify it's the same script (not PID reuse)
                    if 'setup_executor_monitor' in ' '.join(proc.cmdline()):
                        logger.error(f"❌ Setup Executor already running (PID {old_pid})")
                        logger.error("⚠️  Cannot start duplicate instance - exiting")
                        return False
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Stale lock file - remove it
            logger.warning(f"🔧 Removing stale lock file (PID {old_pid} not running)")
            lock_file.unlink()
        
        # Acquire lock
        with open(lock_file, 'w', encoding='utf-8') as f:
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

from ctrader_cbot_client import CTraderCBotClient
from ctrader_executor import CTraderExecutor
from telegram_notifier import TelegramNotifier
from daily_scanner import CTraderDataProvider
from smc_detector import (
    SMCDetector,
    TradeSetup,
    CHoCH,
    FVG,
    get_4h_body_close_confirmation,  # ✅ V10.6 FUNCȚIE UNIFICATĂ — același creier ca scanner-ul
)
from pip_utils import get_pip_size, MIN_SL_PIPS, MAX_SL_PIPS, sl_pips_between, liquidity_already_swept
from news_calendar_utils import (
    load_high_impact_events,
    get_affected_currencies,
    parse_event_datetime,
    liquidity_sniper_blocks_new_entry,
    liquidity_sniper_be_candidates,
    NEW_ENTRY_BLOCK_BEFORE_MIN,
    BE_PROTECT_BEFORE_MIN,
)

# 🛡️ V3.8 ANTI-SPAM SYSTEM by ФорексГод
from signal_cache import (
    SignalCache,
    TelegramDebouncer,
    cleanup_old_signals_file,
    get_signal_cache,
    get_telegram_debouncer
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# V16.3 EQUILIBRIUM BUFFER
# Toleranță directională față de nivelul 50% Equilibrium al impulsului CHoCH.
# Scop: permite execuția chiar dacă prețul nu a atins exact fibo_50,
#       ci a fost cu până la 3 pips deasupra EQ (LONG) / sub EQ (SHORT).
# Formula pip:
#   JPY: EQUILIBRIUM_BUFFER_PIPS * 0.01
#   Standard forex: EQUILIBRIUM_BUFFER_PIPS * 0.0001
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EQUILIBRIUM_BUFFER_PIPS = 3


class SetupExecutorMonitor:
    """V3.2 Pullback + Scale-In executor — reads EXECUTE_NOW from radar via JSON."""

    # V37.13: chei scrise de multi_tf_radar — executorul NU le sterge la merge JSON
    _RADAR_EXECUTE_NOW_KEYS = (
        'EXECUTE_NOW', 'execute_now_trigger_tf', 'execute_now_alert_sent',
        'execute_now_alert_key', 'radar_execution_ready', 'radar_verdict', 'h4_structure_locked',
    )

    @staticmethod
    def _setup_merge_key(setup: dict) -> tuple:
        sym = (setup.get('symbol') or '').upper()
        d = str(setup.get('direction', '')).upper()
        if d in ('LONG', 'BUY'):
            d = 'BUY'
        elif d in ('SHORT', 'SELL'):
            d = 'SELL'
        return (sym, d)

    @classmethod
    def _merge_processed_with_fresh_radar(cls, processed: dict, fresh: dict) -> dict:
        """
        V37.13: Radar flush poate scrie EXECUTE_NOW intre read-ul executorului (T+0)
        si save (T+12). Versiunea processed din memorie NU trebuie sa stearga semnalul fresh.
        """
        merged = {**fresh, **processed}
        if fresh.get('EXECUTE_NOW') is True and not processed.get('entry1_filled'):
            for key in cls._RADAR_EXECUTE_NOW_KEYS:
                if key in fresh:
                    merged[key] = fresh[key]
            sym = fresh.get('symbol', '?')
            logger.info(f"[V37.13 RADAR MERGE] {sym}: EXECUTE_NOW pastrat din JSON fresh (radar flush)")
        return merged

    def __init__(self, check_interval: int = 5):  # V30.9: 5s constant — radar scrie la 30s, executor citeste la 5s = max 5s lag
        self.check_interval = check_interval
        _script_root = Path(__file__).parent.resolve()  # V22.2: absolut, nu CWD-dependent
        self.monitoring_file = _script_root / "monitoring_setups.json"
        self.executed_file = _script_root / ".executed_setups.json"
        self.config_file = _script_root / "pairs_config.json"
        
        self.ctrader_client = CTraderCBotClient()
        
        # V7.0 FIX: Use apollo folder (where cBot actually reads signals.json)
        # Previously pointed to ~/GlitchMatrix/ which was WRONG
        script_dir = Path(__file__).parent.resolve()
        signals_path = str(script_dir / "signals.json")
        self.executor = CTraderExecutor(signals_file=signals_path)
        
        self.telegram = TelegramNotifier()
        self.data_provider = CTraderDataProvider()
        
        # 🛡️ V3.8 ANTI-SPAM SYSTEM by ФорексГод
        self.signal_cache = get_signal_cache()
        self.telegram_debouncer = get_telegram_debouncer()
        
        # 🧹 STARTUP CLEANUP: Remove old signals from signals.json
        cleanup_old_signals_file(Path(signals_path), max_age_hours=1)
        logger.success("🧹 Startup cleanup complete - old signals removed")
        
        # V9.1 ANTI-SPAM: Track rejected trades — 4h cooldown (was 5min, caused spam)
        # Format: {symbol: {'reason': str, 'timestamp': datetime, 'count': int}}
        self.rejected_trades = {}
        self.rejection_cooldown_seconds = 14400  # 4 hours (V9.1 ФорексГод)
        
        # ━━━ V9.3 DEEP SLEEP MODE ━━━
        # When daily loss limit is hit, STOP all scanning until 00:05 UTC next day.
        # Zero HTTP calls, zero CPU usage — the system SLEEPS intelligently.
        self.deep_sleep_until = None  # datetime (UTC) — None = ACTIVE
        self.deep_sleep_state_file = Path("data/deep_sleep_state.json")  # Persist across restarts

        # V19.9 MANUAL RESUME OVERRIDE
        # Când Colonelul dă /resume, acest flag devine True și BLOCHEAZĂ re-intrarea
        # în Deep Sleep pe baza daily loss până la resetul la 00:05 ora României.
        # Comunicare inter-proces prin fișier system_resumed.json (scris de telegram_command_center)
        self.manual_resume_triggered = False
        self._check_manual_resume_marker()  # Verifică la pornire dacă există marker

        self._load_deep_sleep_state()

        # V39.5 LIQUIDITY SNIPER — BE protection dedup (position_key → event_key)
        self._liquidity_sniper_be_applied: set = set()
        self._liquidity_sniper_be_file = Path("data/liquidity_sniper_be_applied.json")
        self._load_liquidity_sniper_be_state()
        
        # V9.3 DAILY REJECTION COUNTER (for /status dashboard)
        self.daily_rejections = 0
        self.daily_rejections_by_reason = {}  # {"Daily Loss Limit": 42, "Duplicate Guard": 5}
        # V19.6.10: data României pentru reset zilnic corect (la 00:05 RO, nu 03:05 RO)
        try:
            import pytz as _pytz_init
            _ro_tz_init = _pytz_init.timezone('Europe/Bucharest')
            self.daily_rejections_date = datetime.now(_ro_tz_init).strftime('%Y-%m-%d')
        except Exception:
            self.daily_rejections_date = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime('%Y-%m-%d')
        
        # ━━━ V9.3 HTTP CACHE ━━━
        # Cache D1 (4h TTL) and H4 (30m TTL) to reduce redundant HTTP calls to cBot
        # Format: {"EURUSD_D1": {"data": DataFrame, "fetched_at": datetime}}
        self._data_cache = {}
        self._cache_ttl = {
            'D1': 14400,  # 4 hours (D1 candles don't change between 4H closes)
            'H4': 1800,   # 30 minutes
            'H1': 300,    # 5 minutes
            'W1': 86400,  # V15.0: 24 hours (W1 se schimbă o dată/săptămână)
        }
        
        # Telegram config for Deep Sleep alerts
        self._telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self._telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        
        # Load pairs config for SCALE_IN settings and V3.2 Pullback Strategy
        self.config = self._load_config()
        self.execution_strategy = self.config.get('scanner_settings', {}).get('execution_strategy', {})
        self.pullback_config = self.config.get('scanner_settings', {}).get('pullback_strategy', {
            'enabled': True,
            'fibo_level': 0.5,
            'tolerance_pips': 10,
            'pullback_timeout_hours': 24,
            'swing_lookback_candles': 5,
            'sl_buffer_pips': 10,
            'on_timeout_action': 'force_entry',
            'use_1h_sl': True,  # [LEGACY — Dezactivat permanent din V31.0] V3.3 SNIPER SL
            'use_4h_sl': True   # [LEGACY — Dezactivat permanent din V31.0] V3.3 HIGH CONFIDENCE SL
        })
        
        # SMC Detector for CHoCH detection
        # V10.5 ATR SYNC: atr_multiplier=0.6 — echilibru între Scanner (1.2) și
        # vechiul default (0.3). Elimină intrările false pe 4H noise fără a bloca
        # swing-urile structurale valide. Scanner rămâne la 1.2 (detecție strictă D1).
        self.smc_detector = SMCDetector(
            atr_multiplier=0.6
        )
        
        # Track executed setups to avoid duplicates
        self.executed_setups = self._load_executed_setups()
        
        logger.info("🎯 Setup Executor Monitor initialized")
        logger.info(f"⏱️  Check interval: {check_interval}s")
        logger.info(f"📊 Execution Strategy: {self.execution_strategy.get('mode', 'N/A')}")
        logger.info(f"🎯 V3.2 Pullback Strategy: {'ENABLED' if self.pullback_config['enabled'] else 'DISABLED'}")
        logger.info(f"[LEGACY V3.3 — dezactivat V31.0] SL 1H: {'ENABLED' if self.pullback_config.get('use_1h_sl', True) else 'DISABLED'}")
        logger.info(f"[LEGACY V3.3 — dezactivat V31.0] SL 4H: {'ENABLED' if self.pullback_config.get('use_4h_sl', True) else 'DISABLED'}")
    
    def _load_config(self):
        """Load pairs_config.json"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
        return {}
    
    def get_pair_config(self, symbol: str) -> dict:
        """Get configuration for specific pair"""
        pairs = self.config.get('pairs', [])
        for pair in pairs:
            if pair.get('symbol') == symbol:
                return pair
        return {}
    
    def _load_executed_setups(self):
        """Load previously executed setups — V9.1: Auto-cleanup entries >30 days (ФорексГод)"""
        if self.executed_file.exists():
            try:
                with open(self.executed_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # V9.1 R1 FIX: Cleanup entries older than 30 days
                executed_keys = set(data.get('executed_keys', []))
                timestamps = data.get('timestamps', {})
                cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
                
                if timestamps:
                    old_count = len(executed_keys)
                    # Keep only entries newer than 30 days
                    keys_to_remove = set()
                    for key in executed_keys:
                        ts = timestamps.get(key, '')
                        if ts and ts < cutoff and ts > '1971':  # Skip epoch dates
                            keys_to_remove.add(key)
                    
                    if keys_to_remove:
                        executed_keys -= keys_to_remove
                        for k in keys_to_remove:
                            timestamps.pop(k, None)
                        # Save cleaned data
                        with open(self.executed_file, 'w', encoding='utf-8') as f:
                            json.dump({
                                'executed_keys': list(executed_keys),
                                'timestamps': timestamps,
                                'last_update': datetime.now(timezone.utc).isoformat(),
                                'last_cleanup': datetime.now(timezone.utc).isoformat()
                            }, f, indent=2)
                        logger.success(f"🧹 R1 CLEANUP: Removed {len(keys_to_remove)} expired entries from .executed_setups.json ({old_count}→{len(executed_keys)})")
                
                return executed_keys
            except Exception as e:
                logger.warning(f"Could not load executed setups: {e}")
        return set()
    
    def _save_executed_setup(self, setup_key: str):
        """Save executed setup to prevent re-execution — V9.1: With timestamp for cleanup (R1 FIX)"""
        self.executed_setups.add(setup_key)
        try:
            # Load existing timestamps
            existing_timestamps = {}
            if self.executed_file.exists():
                try:
                    with open(self.executed_file, 'r', encoding='utf-8') as f:
                        old_data = json.load(f)
                        existing_timestamps = old_data.get('timestamps', {})
                except Exception as _err:
                    logger.warning(f"[V37.0] non-critical error: {_err}")
            
            # Add timestamp for new entry
            existing_timestamps[setup_key] = datetime.now(timezone.utc).isoformat()
            
            with open(self.executed_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'executed_keys': list(self.executed_setups),
                    'timestamps': existing_timestamps,
                    'last_update': datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save executed setup: {e}")
    
    # ━━━ V9.3 DEEP SLEEP ENGINE ━━━
    
    @staticmethod
    def _next_0005_ro() -> datetime:
        """
        V19.6.7: Calculează NEXT 00:05 în fusul orar Europe/Bucharest (EEST/EET).
        Dacă acum e înainte de 00:05 RO → returnează azi la 00:05 RO (convertit UTC).
        Dacă acum e după 00:05 RO → returnează mâine la 00:05 RO (convertit UTC).
        """
        try:
            import pytz
            ro_tz = pytz.timezone('Europe/Bucharest')
            now_ro = datetime.now(ro_tz)
            target_ro = now_ro.replace(hour=0, minute=5, second=0, microsecond=0)
            if now_ro >= target_ro:
                # Am trecut de 00:05 azi — next target e mâine
                target_ro = target_ro + timedelta(days=1)
            return target_ro.astimezone(timezone.utc)
        except Exception:
            # Fallback hardcodat EEST (UTC+3)
            ro_offset = timedelta(hours=3)
            now_ro_naive = datetime.now(timezone.utc) + ro_offset
            target_naive = now_ro_naive.replace(hour=0, minute=5, second=0, microsecond=0)
            if now_ro_naive >= target_naive:
                target_naive = target_naive + timedelta(days=1)
            return (target_naive - ro_offset).replace(tzinfo=timezone.utc)

    def _check_manual_resume_marker(self):
        """
        V19.9: Verifică dacă Colonelul a dat /resume azi.
        Dacă fișierul data/system_resumed.json există și a fost scris AZI (ora României),
        setăm manual_resume_triggered=True și ștergem deep_sleep_state.json.
        """
        try:
            resume_marker = Path(__file__).parent / 'data' / 'system_resumed.json'
            if not resume_marker.exists():
                return
            with open(resume_marker, 'r', encoding='utf-8') as _f:
                _rm_data = json.load(_f)
            _resumed_at_str = _rm_data.get('resumed_at', '')
            if not _resumed_at_str:
                return
            _resumed_at = datetime.fromisoformat(_resumed_at_str)
            # Verifică dacă e azi în ora României
            try:
                import pytz as _pytz_mr
                _ro_tz_mr = _pytz_mr.timezone('Europe/Bucharest')
                _today_ro = datetime.now(_ro_tz_mr).strftime('%Y-%m-%d')
                _resumed_day_ro = _resumed_at.astimezone(_ro_tz_mr).strftime('%Y-%m-%d')
                is_today = (_resumed_day_ro == _today_ro)
            except Exception:
                is_today = (_resumed_at.date() == datetime.now(timezone.utc).date())
            if is_today:
                if not self.manual_resume_triggered:
                    _rm = getattr(self.executor, 'risk_manager', None)
                    if _rm is not None:
                        _rm.reset_pnl_baseline_after_resume('manual /resume')
                self.manual_resume_triggered = True
                # V39.1 CRITICAL: curata starea in-memory — altfel _check_deep_sleep ramane True
                self.deep_sleep_until = None
                self.deep_sleep_state_file.unlink(missing_ok=True)
                logger.success(
                    "🔱 [V39.1] manual_resume_triggered=True — Deep Sleep OFF, "
                    "PnL baseline reset, loss limit bypass activ"
                )
        except Exception as _mr_err:
            logger.debug(f"⚠️ _check_manual_resume_marker: {_mr_err}")

    def _load_deep_sleep_state(self):
        """Load Deep Sleep state from disk (survives restarts)"""
        try:
            # V39.1: /resume manual are prioritate — nu reactiva Deep Sleep din fisier
            if self.manual_resume_triggered:
                self.deep_sleep_until = None
                self.deep_sleep_state_file.unlink(missing_ok=True)
                return

            if self.deep_sleep_state_file.exists():
                with open(self.deep_sleep_state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)

                # Manual lockdown (/killall) — nu recalcula, respectă wake_time manual
                if state.get('lockdown'):
                    wake_time_str = state.get('wake_time')
                    if wake_time_str:
                        wake_time = datetime.fromisoformat(wake_time_str)
                        if wake_time > datetime.now(timezone.utc):
                            self.deep_sleep_until = wake_time
                    return

                # V19.6.7 FIX: RECALCULEAZĂ MEREU wake_time la 00:05 ora României
                # Nu ne încredem niciodată în valoarea stocată — poate fi scrisă de cod vechi (UTC-based)
                wake_time = self._next_0005_ro()
                now_utc = datetime.now(timezone.utc)

                if wake_time > now_utc:
                    self.deep_sleep_until = wake_time
                    remaining_h = (wake_time - now_utc).total_seconds() / 3600
                    try:
                        import pytz
                        ro_tz = pytz.timezone('Europe/Bucharest')
                        wake_ro = wake_time.astimezone(ro_tz)
                        wake_label = wake_ro.strftime('%H:%M (ora României)')
                    except Exception:
                        wake_label = '00:05 (ora României)'
                    logger.warning(f"😴 DEEP SLEEP RESTORED — {remaining_h:.1f}h until {wake_label}")
                    # V25.2: Alertă Telegram la startup când Deep Sleep e activ
                    # Evităm situația tăcută: Watchdog repornește executorul, nimeni nu știe că doarme
                    self._send_deep_sleep_telegram(
                        f"😴 <b>SYSTEM RESTARTAT ÎN DEEP SLEEP</b>\n\n"
                        f"Executorul a fost repornit de Watchdog dar Deep Sleep era activ din sesiunea anterioară.\n\n"
                        f"⏰ Activare automată la ora: <b>{wake_label}</b>\n"
                        f"🕐 Timp rămas: <b>{remaining_h:.1f}h</b>\n\n"
                        f"Zero scanări, zero execuții până la trezire.\n"
                        f"Folosește /resume pentru a ieși forțat din Deep Sleep."
                    )
                    # Suprascrie fișierul cu wake_time corectat (elimină valori vechi greșite)
                    state['wake_time'] = wake_time.isoformat()
                    try:
                        with open(self.deep_sleep_state_file, 'w', encoding='utf-8') as f:
                            json.dump(state, f, indent=2)
                    except Exception:
                        pass
                else:
                    logger.info("🌅 Deep Sleep state expired — system is ACTIVE")
                    self.deep_sleep_state_file.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"⚠️  Error loading Deep Sleep state: {e}")
    
    def _enter_deep_sleep(self, reason: str):
        """
        😴 V9.3 DEEP SLEEP — Stop ALL scanning until 00:05 UTC next day.
        
        When daily loss limit is reached, there is ZERO point in continuing to:
        - Download D1/H4/H1 candles (27+ HTTP calls per iteration)
        - Analyze setups (CPU-intensive SMC detection)
        - Attempt execution (will be rejected by risk manager)
        
        Instead: SLEEP until the limit resets at midnight UTC.
        Impact: 77,760 HTTP calls/day → ZERO.
        """
        # V19.9 MANUAL RESUME GUARD: Dacă Colonelul a dat /resume azi, NU intrăm în Deep Sleep
        if self._loss_limit_bypassed():
            logger.warning(f"🔱 [V39.1] _enter_deep_sleep BLOCAT — loss limit bypass activ ({reason})")
            return

        # V19.6.2 FIX: guard — dacă deja în Deep Sleep, nu mai scriem/trimitem din nou
        if self.deep_sleep_until is not None:
            now_check = datetime.now(timezone.utc)
            if self.deep_sleep_until > now_check:
                logger.debug(f"😴 Deep Sleep deja activ — ignorăm apel duplicat ({reason})")
                return
        now = datetime.now(timezone.utc)
        # V19.6.7 FIX: Folosește _next_0005_ro() — calcul corect indiferent de ora curentă
        tomorrow_0005 = self._next_0005_ro()
        self.deep_sleep_until = tomorrow_0005
        remaining_h = (tomorrow_0005 - now).total_seconds() / 3600
        
        # Persist to disk (survives process restarts)
        try:
            self.deep_sleep_state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.deep_sleep_state_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'wake_time': tomorrow_0005.isoformat(),
                    'reason': reason,
                    'entered_at': now.isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"⚠️  Could not persist Deep Sleep state: {e}")
        
        logger.warning(f"😴 DEEP SLEEP ACTIVATED — wake at {tomorrow_0005.strftime('%Y-%m-%d %H:%M UTC')} ({remaining_h:.1f}h)")
        logger.warning(f"   Reason: {reason}")
        logger.warning(f"   Impact: ALL scanning paused — zero HTTP calls, zero CPU")
        
        # Send ONE Telegram notification
        try:
            import pytz
            ro_tz = pytz.timezone('Europe/Bucharest')
            wake_ro_label = tomorrow_0005.astimezone(ro_tz).strftime('%H:%M (ora României)')
        except Exception:
            wake_ro_label = '00:05 (ora României)'
        self._send_deep_sleep_telegram(
            f"😴 <b>DEEP SLEEP ACTIVATED</b>\n\n"
            f"Reason: <i>{reason}</i>\n"
            f"Wake-up: <code>{wake_ro_label}</code>\n"
            f"Duration: <code>{remaining_h:.1f}h</code>\n\n"
            f"⚡ All scanning PAUSED — zero resource usage\n"
            f"🌅 Auto-resume la 00:05 ora României (new trading day)"
        )
    
    def _loss_limit_bypassed(self) -> bool:
        """V39.1: Colonel /resume sau force_bypass_loss_limit din daily_state.json."""
        if self.manual_resume_triggered:
            return True
        try:
            _rm = getattr(self.executor, 'risk_manager', None)
            if _rm is not None and hasattr(_rm, '_loss_limit_bypassed'):
                return _rm._loss_limit_bypassed()
        except Exception:
            pass
        return False

    def _check_deep_sleep(self) -> bool:
        """
        Check if system is in Deep Sleep. Returns True if sleeping (skip all work).
        Auto-wakes when time expires.
        """
        # V39.1: /resume — iesire instantanee din Deep Sleep (memorie + disk)
        if self._loss_limit_bypassed():
            if self.deep_sleep_until is not None:
                logger.success("🔱 [V39.1] Deep Sleep anulat — loss limit bypass activ (/resume)")
                self.deep_sleep_until = None
            try:
                self.deep_sleep_state_file.unlink(missing_ok=True)
            except Exception:
                pass
            return False

        if self.deep_sleep_until is None:
            return False
        
        now = datetime.now(timezone.utc)
        if now < self.deep_sleep_until:
            remaining_h = (self.deep_sleep_until - now).total_seconds() / 3600
            # V25.2: Log la FIECARE ciclu cu WARNING — vizibil imediat în consolă și log
            # Motivul: logul la 100 iterații (~50min) era INVIZIBIL în practică.
            # Acum e clar la fiecare 30s că sistemul doarme intenționat.
            try:
                import pytz as _pytz_ds
                _ro_tz_ds = _pytz_ds.timezone('Europe/Bucharest')
                _wake_ro = self.deep_sleep_until.astimezone(_ro_tz_ds)
                _wake_label = _wake_ro.strftime('%H:%M (ora României)')
            except Exception:
                _wake_label = 'la 00:05'
            logger.warning(
                f"😴 [DEEP SLEEP ACTIV] {remaining_h:.1f}h rămase — trezire la {_wake_label} | "
                f"zero scanări, zero execuții | /resume pentru ieșire forțată"
            )
            return True  # ← SLEEPING: Skip all processing
        else:
            # WAKE UP! (auto-wake la 00:05 ora României = nou trading day)
            self.deep_sleep_until = None
            self._deep_sleep_log_counter = 0

            # V19.9: Reset manual_resume_triggered la nou trading day
            # Override-ul Colonelului expiră odată cu ziua de trading
            if self.manual_resume_triggered:
                self.manual_resume_triggered = False
                logger.info("🔱 [V19.9] manual_resume_triggered resetat la 00:05 — nou trading day")
                # Ștergem și marker-ul de pe disc
                try:
                    _rm_path = Path(__file__).parent / 'data' / 'system_resumed.json'
                    _rm_path.unlink(missing_ok=True)
                except Exception:
                    pass

            # Reset daily rejection counter
            self.daily_rejections = 0
            self.daily_rejections_by_reason = {}
            try:
                import pytz as _pytz_wu
                _ro_tz_wu = _pytz_wu.timezone('Europe/Bucharest')
                self.daily_rejections_date = datetime.now(_ro_tz_wu).strftime('%Y-%m-%d')
            except Exception:
                self.daily_rejections_date = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime('%Y-%m-%d')

            # Clean up state file
            try:
                self.deep_sleep_state_file.unlink(missing_ok=True)
            except Exception:
                pass
            
            logger.success("🌅 DEEP SLEEP ENDED — Daily loss limit reset, resuming execution!")
            self._send_deep_sleep_telegram(
                "🌅 <b>SYSTEM AWAKE</b>\n\n"
                "Daily loss limit has been reset.\n"
                "✅ Scanning and execution resumed.\n"
                "⚡ All monitors are active."
            )
            return False  # ← AWAKE: Continue processing
    
    def _send_deep_sleep_telegram(self, message: str):
        """Send a Deep Sleep notification to Telegram"""
        if not self._telegram_token or not self._telegram_chat_id:
            return
        try:
            # ═══ V10.4 SOVEREIGN SIGNATURE — 16-Line Symmetry ═══
            sep = "────────────────"
            branded = (
                f"{message.strip()}\n\n"
                f"  {sep}\n"
                f"  🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
                f"  {sep}\n"
                f"  🏛 <b>ГЛИТЧ ИН МАТРИКС</b> 🏛"
            )
            url = f"https://api.telegram.org/bot{self._telegram_token}/sendMessage"
            requests.post(url, json={
                'chat_id': self._telegram_chat_id,
                'text': branded,
                'parse_mode': 'HTML'
            }, timeout=10)
        except Exception as e:
            logger.error(f"❌ Deep Sleep Telegram error: {e}")
    
    def _track_rejection(self, reason: str):
        """V9.3: Track rejection for /status dashboard counter"""
        # V19.6.10: Reset counter pe ziua României, nu UTC
        try:
            import pytz as _pytz_tr
            _ro_tz_tr = _pytz_tr.timezone('Europe/Bucharest')
            today = datetime.now(_ro_tz_tr).strftime('%Y-%m-%d')
        except Exception:
            today = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime('%Y-%m-%d')
        if today != self.daily_rejections_date:
            self.daily_rejections = 0
            self.daily_rejections_by_reason = {}
            self.daily_rejections_date = today
        
        self.daily_rejections += 1
        
        # Categorize
        if 'daily loss' in reason.lower() or 'loss limit' in reason.lower():
            cat = 'Daily Loss Limit'
        elif 'max positions' in reason.lower():
            cat = 'Max Positions'
        elif 'duplicate' in reason.lower():
            cat = 'Duplicate Guard'
        else:
            cat = 'Other'
        self.daily_rejections_by_reason[cat] = self.daily_rejections_by_reason.get(cat, 0) + 1
        
        # Persist for /status command to read
        try:
            rejection_file = Path("data/daily_rejections.json")
            rejection_file.parent.mkdir(parents=True, exist_ok=True)
            with open(rejection_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'date': self.daily_rejections_date,
                    'total': self.daily_rejections,
                    'by_reason': self.daily_rejections_by_reason
                }, f, indent=2)
        except Exception:
            pass
    
    # ━━━ V9.3 HTTP CACHE ENGINE ━━━
    
    def _get_cached_data(self, symbol: str, timeframe: str, count: int):
        """
        V9.3 HTTP CACHE: Fetch market data with TTL-based caching.
        
        - D1 candles → cached 4 hours (don't change between 4H closes)
        - H4 candles → cached 30 minutes
        - H1 candles → cached 5 minutes
        
        Reduces HTTP calls from ~27 per iteration to ~5-10.
        At 30s interval: from 77,760 calls/day → ~20,000 calls/day (74% reduction).
        """
        cache_key = f"{symbol}_{timeframe}"
        now_ts = time.time()
        ttl = self._cache_ttl.get(timeframe, 300)  # Default 5 min
        
        # Check cache
        if cache_key in self._data_cache:
            entry = self._data_cache[cache_key]
            age = now_ts - entry['fetched_at']
            if age < ttl:
                logger.debug(f"📦 CACHE HIT: {cache_key} (age: {age:.0f}s / TTL: {ttl}s)")
                return entry['data']
            else:
                logger.debug(f"📦 CACHE EXPIRED: {cache_key} (age: {age:.0f}s > TTL: {ttl}s)")
        
        # Cache miss — fetch from cBot
        try:
            df = self.data_provider.get_historical_data(symbol, timeframe, count)
            if df is not None and not df.empty:
                self._data_cache[cache_key] = {
                    'data': df,
                    'fetched_at': now_ts
                }
                logger.debug(f"📦 CACHE STORE: {cache_key} ({len(df)} candles, TTL: {ttl}s)")
            return df
        except Exception as e:
            logger.error(f"❌ Cache fetch error {cache_key}: {e}")
            # Return stale cache if available (better than nothing)
            if cache_key in self._data_cache:
                logger.warning(f"📦 CACHE STALE FALLBACK: {cache_key} (fetch failed, using old data)")
                return self._data_cache[cache_key]['data']
            return None
    
    # ━━━ V10.3 PILLAR 4: NEWS GUARD ENGINE (Information Only) ━━━
    
    def _check_spread_guard(self, symbol: str) -> str:
        """
        V11.2 SPREAD GUARD: Blochează execuția dacă spread > max_spread_pips
        sau dacă suntem în fereastra de rollover 00:00 UTC.

        Returnează string cu eroarea dacă trebuie blocat, '' dacă e OK.
        """
        try:
            # ── 1. Rollover check (00:00-00:15 UTC) ─────────────────────
            now_utc = datetime.now(timezone.utc)
            if now_utc.hour == 0 and now_utc.minute < 15:
                return (f"ROLLOVER 00:{now_utc.minute:02d} UTC — spread periculos "
                        f"(IC Markets rollover). Execuție blocată 15 min.")

            # ── 2. Live spread check via cTrader bridge ─────────────────
            try:
                super_cfg_path = Path("SUPER_CONFIG.json")
                with open(super_cfg_path, encoding='utf-8') as f:
                    scfg = json.load(f)
                max_spread = scfg.get('spread_guard', {}).get('max_spread_pips', 2.5)
                block = scfg.get('spread_guard', {}).get('block_execution', True)
            except Exception:
                max_spread, block = 2.5, True

            if not block:
                return ""

            ctrader_port = int(os.environ.get('CTRADER_PORT', '8010'))
            try:
                r = requests.get(
                    f"http://127.0.0.1:{ctrader_port}/spread?symbol={symbol}",
                    timeout=3
                )
                if r.status_code == 200:
                    data = r.json()
                    spread_pips = data.get('spread_pips') or data.get('spread')
                    if spread_pips is not None and float(spread_pips) > max_spread:
                        return (f"{symbol} spread={spread_pips:.1f} pips > max {max_spread} pips "
                                f"— execuție blocată")
            except requests.exceptions.ConnectionError:
                logger.warning(f"[V37.0] spread check skipped — cBot bridge offline for {symbol}")
            except Exception as _spr_err:
                logger.warning(f"[V37.0] spread check failed for {symbol}: {_spr_err}")

        except Exception as _guard_err:
            logger.warning(f"[V37.0] spread guard error for {symbol}: {_guard_err}")

        return ""

    def _load_liquidity_sniper_be_state(self):
        """Restore BE-protection dedup keys across restarts."""
        try:
            if self._liquidity_sniper_be_file.exists():
                with open(self._liquidity_sniper_be_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._liquidity_sniper_be_applied = set(data)
        except Exception as e:
            logger.debug(f"V39.5 BE state load skipped: {e}")

    def _save_liquidity_sniper_be_state(self):
        try:
            self._liquidity_sniper_be_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._liquidity_sniper_be_file, "w", encoding="utf-8") as f:
                json.dump(sorted(self._liquidity_sniper_be_applied), f, indent=2)
        except Exception as e:
            logger.debug(f"V39.5 BE state save skipped: {e}")

    def _check_news_guard(self, symbol: str) -> str:
        """
        V39.5 LIQUIDITY SNIPER — NEW ENTRY GUARD.

        Blocks NEW positions 15 min before HIGH impact (spread/slippage protection).
        Scanner stays active — no total shutdown.
        Returns block reason string, or empty if clear.
        """
        try:
            block = liquidity_sniper_blocks_new_entry(symbol)
            if block:
                logger.warning(f"   🎯 V39.5 LIQUIDITY SNIPER: {block}")
            return block
        except Exception as e:
            logger.debug(f"V39.5 News Guard check error: {e}")
            return ""

    def _liquidity_sniper_be_protect_open_positions(self):
        """
        V39.5 LIQUIDITY SNIPER — TRADE MANAGEMENT (Protect & Ride).

        At T-2 min before HIGH impact: if position is ITM, move SL to BE + commission.
        Does NOT close trades — leaves them open to ride liquidity spike toward TP.
        """
        try:
            active_pos_file = Path(__file__).parent / "active_positions.json"
            if not active_pos_file.exists():
                return

            file_age = time.time() - active_pos_file.stat().st_mtime
            if file_age > 300:
                return

            with open(active_pos_file, encoding="utf-8") as f:
                positions = json.load(f)
            if not isinstance(positions, list) or not positions:
                return

            commission_pips_per_side = 0.7
            be_buffer_pips = commission_pips_per_side * 2  # both sides

            for pos in positions:
                symbol = pos.get("symbol", "")
                direction = str(pos.get("direction", "")).lower()
                entry = float(pos.get("entry_price") or 0)
                current_sl = float(pos.get("stop_loss") or 0)
                pips = float(pos.get("pips") or 0)
                net_profit = float(pos.get("net_profit") or 0)

                if not symbol or not entry or direction not in ("buy", "sell"):
                    continue

                # ITM check
                if pips <= 0 and net_profit <= 0:
                    continue

                candidates = liquidity_sniper_be_candidates(symbol=symbol)
                if not candidates:
                    continue

                event, mins = candidates[0]
                event_key = f"{event['currency']}_{event['event']}_{event['date']}_{event['time']}"
                pos_key = f"{symbol}_{direction}_{entry:.5f}"
                dedup_key = f"{pos_key}|{event_key}"
                if dedup_key in self._liquidity_sniper_be_applied:
                    continue

                pip_size = get_pip_size(symbol)
                buffer = be_buffer_pips * pip_size

                if direction == "buy":
                    new_sl = entry + buffer
                    if current_sl >= new_sl - pip_size * 0.1:
                        self._liquidity_sniper_be_applied.add(dedup_key)
                        continue
                else:
                    new_sl = entry - buffer
                    if current_sl > 0 and current_sl <= new_sl + pip_size * 0.1:
                        self._liquidity_sniper_be_applied.add(dedup_key)
                        continue

                reason = (
                    f"LIQUIDITY_SNIPER_BE|{event['currency']} {event['event']} "
                    f"T-{mins:.1f}min"
                )
                ok = self.executor.modify_stop_loss(
                    symbol=symbol,
                    direction=direction.upper(),
                    new_stop_loss=new_sl,
                    reason=reason,
                )
                if ok:
                    self._liquidity_sniper_be_applied.add(dedup_key)
                    self._save_liquidity_sniper_be_state()
                    logger.success(
                        f"🔒 V39.5 LIQUIDITY SNIPER BE: {symbol} {direction.upper()} "
                        f"SL→{new_sl:.5f} ({reason})"
                    )
                    try:
                        sep = "────────────────"
                        msg = (
                            f"🔒 <b>LIQUIDITY SNIPER — BE PROTECT</b>\n\n"
                            f"<b>{symbol}</b> {direction.upper()} ITM\n"
                            f"SL moved to BE+commission: <code>{new_sl:.5f}</code>\n"
                            f"News: {event['currency']} {event['event']} in {mins:.0f}min\n\n"
                            f"ℹ️ <i>Position kept open — riding liquidity to TP</i>\n\n"
                            f"  {sep}\n"
                            f"  🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
                            f"  {sep}\n"
                            f"  🏛 <b>ГЛИТЧ ИН МАТРИКС</b> 🏛"
                        )
                        url = f"https://api.telegram.org/bot{self._telegram_token}/sendMessage"
                        requests.post(
                            url,
                            json={
                                "chat_id": self._telegram_chat_id,
                                "text": msg,
                                "parse_mode": "HTML",
                            },
                            timeout=10,
                        )
                    except Exception:
                        pass

        except Exception as e:
            logger.debug(f"V39.5 BE protect error: {e}")

    # ━━━ END V39.5 LIQUIDITY SNIPER ━━━
    
    def _get_setup_key(self, setup: dict) -> str:
        """Generate unique key for setup"""
        return f"{setup['symbol']}_{setup['direction']}_{setup['entry_price']}_{setup['setup_time']}"
    
    def _check_price_hit_entry(self, symbol: str, entry_price: float, direction: str) -> tuple:
        """
        Check if current price has hit entry level
        Returns: (hit: bool, current_price: float)
        """
        try:
            # Get current price from last 4H candle
            df = self.ctrader_client.get_historical_data(symbol, 'H4', 5)
            if df is None or df.empty:
                logger.debug(f"⚠️ No data available for {symbol}, skipping price check")
                return False, 0
            
            current_price = df['close'].iloc[-1]
            last_candle = df.iloc[-1]
            
            # For BUY: price should go UP to entry (current >= entry)
            # For SELL: price should go DOWN to entry (current <= entry)
            
            if direction.lower() == 'buy':
                # BUY entry: check if price reached or exceeded entry level
                hit = current_price >= entry_price
                # Also check if recent candle touched the entry
                candle_hit = last_candle['high'] >= entry_price
                return (hit or candle_hit), current_price
            else:
                # SELL entry: check if price reached or went below entry level
                hit = current_price <= entry_price
                # Also check if recent candle touched the entry
                candle_hit = last_candle['low'] <= entry_price
                return (hit or candle_hit), current_price
                
        except Exception as e:
            logger.error(f"Error checking price for {symbol}: {e}")
            return False, 0
    
    def _check_radar_entry(self, setup: dict, df_h1, symbol: str) -> dict:
        """[LEGACY — Dezactivat permanent din V31.0]
        V3.3 SNIPER ENTRY a fost înlocuit de arhitectura Radar-only (multi_tf_radar.py).
        Singurul trigger valid de execuție este EXECUTE_NOW=True setat de Radar.
        Executorul NU mai face analiză SMC proprie (FVG / P/D / CHoCH independent).
        """
        logger.debug(f"[V31.0 LEGACY] _check_radar_entry: {symbol} → KEEP_MONITORING")
        return {'action': 'KEEP_MONITORING', 'reason': '[V31.0 LEGACY] Radar-only mode — doar EXECUTE_NOW=True declanseaza executia'}

    def _check_pullback_entry(self, setup: dict, df_h1, symbol: str) -> dict:
        """V31.0 STUB: DEZACTIVAT.
        Executorul NU mai face analiza SMC proprie.
        Singurul trigger valid este EXECUTE_NOW=True setat de Radar (multi_tf_radar.py).
        Functia returneaza imediat KEEP_MONITORING pentru orice apel rezidual.
        """
        # V31.0: Dezactivat complet — Radar-only mode.
        logger.debug(f"[V31.0] _check_pullback_entry stub: {symbol} → KEEP_MONITORING")
        return {'action': 'KEEP_MONITORING', 'reason': '[V31.0] Executor fara SMC propriu — asteptam EXECUTE_NOW live de la Radar'}

    def _symbol_already_at_broker(self, symbol: str) -> bool:
        """
        🛡️ V7.1 DUPLICATE GUARD + V9.1 FRESHNESS CHECK (ФорексГод)
        Reads active_positions.json (written by cBot every 10s).
        
        V9.1: If file is older than 5 minutes → REFUSE execution (stale data = danger).
        Returns True if symbol has existing position → should SKIP execution.
        """
        try:
            active_pos_file = Path(__file__).parent / "active_positions.json"
            if not active_pos_file.exists():
                logger.warning(f"⚠️  active_positions.json not found — cannot verify broker, allowing {symbol}")
                return False
            
            # V9.1 R7 FIX: Freshness check — refuse execution on stale data
            file_age_seconds = time.time() - active_pos_file.stat().st_mtime
            if file_age_seconds > 300:  # 5 minutes
                logger.error(f"🚨 R7 SAFETY: active_positions.json is {file_age_seconds:.0f}s old (>{300}s) — BLOCKING {symbol} execution until fresh sync!")
                return True  # Conservative: block execution when data is stale
            
            with open(active_pos_file, 'r', encoding='utf-8') as f:
                positions = json.load(f)
            
            if not isinstance(positions, list):
                return False
            
            clean_symbol = symbol.upper().replace("/", "").replace(" ", "")
            
            for pos in positions:
                pos_symbol = pos.get('symbol', '').upper().replace("/", "").replace(" ", "")
                if pos_symbol == clean_symbol:
                    logger.warning(f"🛡️ DUPLICATE GUARD: {symbol} already at broker ({pos.get('direction', '?')} @ {pos.get('entry_price', '?')})")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"⚠️  Error checking broker positions for {symbol}: {e} — BLOCKING execution (conservative)")
            return True  # V9.1: Conservative — block on error instead of allowing

    def _atomic_write_monitoring(self, write_data: dict):
        """V24.8: Scriere atomică monitoring_setups.json — previne coruperea JSON la crash/restart.
        
        Mecanismul: scrie în .tmp → os.replace() atomic (operație kernel-level indivizibilă).
        Dacă procesul crapă în mijlocul scrierii → fișierul original rămâne intact (nu parțial scris).
        Aceasta elimină cauza principală a dispariției setup-urilor din JSON.
        """
        import os as _atomic_os
        tmp_path = str(self.monitoring_file) + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(write_data, f, indent=2, default=str)
        _atomic_os.replace(tmp_path, str(self.monitoring_file))

    def _cleanup_monitoring_setups(self):
        """
        V19.20: SACRED WATCHLIST POLICY — Un setup în monitorizare este SFÂNT.

        ELIMINAT DEFINITIV (V19.20):
          ❌ Condiția 3 (distanță pips) — ȘTEARSĂ COMPLET.
             Era cauza principală a dispariției setup-urilor: citea prețuri din
             trade_history.json (fișier static, actualizat la 30s) și elimina
             perechi proaspăt adăugate înainte ca TF Radar să apuce să confirme 4H CHoCH.

        SINGURELE MOTIVE LEGALE DE ȘTERGERE AUTOMATĂ:
          1. Status mort explicit: EXPIRED / CLOSED / CANCELLED / FAILED
             (scris de executor DUPĂ execuție sau de Daily Scanner la invalidare manuală)
          2. Vârstă cronologică > 14 zile (crescut de la 7→30→14 zile: echilibru macro)
             Setup-urile Daily au nevoie de timp pentru pullback — 14 zile = 2 săptămâni.
          3. Câmpuri obligatorii lipsă: symbol / direction / entry_price
             (setup corupt, inutilizabil de executor)

        GARANTAT PĂSTRAT:
          ✅ Orice setup < 14 zile vârstă, cu status activ, rămâne în JSON
          ✅ multi_tf_radar îl analizează ciclu de ciclu (30s) fără întrerupere
          ✅ Nicio ștergere pe baza distanței față de preț live
        """
        if not self.monitoring_file.exists():
            return

        try:
            with open(self.monitoring_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, dict):
                setups = data.get('setups', [])
            elif isinstance(data, list):
                setups = data
            else:
                return

            now = datetime.now(timezone.utc)
            active_setups = []
            removed_reasons = []

            for s in setups:
                symbol = s.get('symbol', '?')
                reason_remove = None

                # ── Condiția 1: Status mort explicit ────────────────────────────────────
                # Scris de executor după execuție finalizată sau de scanner la invalidare
                dead_statuses = {'EXPIRED', 'CLOSED', 'CANCELLED', 'FAILED'}
                if s.get('status', '') in dead_statuses:
                    reason_remove = f"status mort={s.get('status')}"

                # ── Condiția 2: Vârstă cronologică > 14 zile ────────────────────────────
                # V19.20: 14 zile = 2 săptămâni complete pentru pullback macro
                # (Istoric: 7 zile V19.0 → 30 zile V19.12 → 14 zile V19.20 echilibru)
                if not reason_remove:
                    setup_time_str = s.get('setup_time') or s.get('created_at', '')
                    if setup_time_str:
                        try:
                            st = datetime.fromisoformat(str(setup_time_str).replace('Z', '+00:00'))
                            if st.tzinfo is None:
                                st = st.replace(tzinfo=timezone.utc)
                            age_days = (now - st).total_seconds() / 86400
                            if age_days > 14:
                                reason_remove = f"vârstă={age_days:.1f} zile > 14 (macro expirat)"
                        except Exception as _date_err:
                            logger.warning(f"[V37.0] setup date parse failed — keeping setup: {_date_err}")

                # ── Condiția 3 (DISTANȚĂ) — ELIMINATĂ DEFINITIV în V19.20 ──────────────
                # ERA: dist_pips = abs(current_px - entry_px) / pip_sz → elimina la >500p
                # MOTIVUL ELIMINĂRII:
                #   • trade_history.json se actualizează la ~30s → prețuri stale
                #   • BTCUSD/XAU au pip_size=1.0 → distanța în "pips" era falsă
                #   • Setup-uri proaspete (< 1h) erau șterse înainte de confirmare 4H
                #   • Radical: dacă structura Daily e validă, intrarea rămâne validă
                #     indiferent de distanța momentană față de entry
                # ─────────────────────────────────────────────────────────────────────────

                # ── Condiția 4: Câmpuri obligatorii lipsă (setup corupt) ─────────────────
                # V22: entry_price eliminat din câmpuri obligatorii la cleanup.
                # Scanner poate scrie setup fără entry_price (e adăugat ulterior de radar).
                # Ștergem DOAR dacă lipsesc symbol sau direction (setup complet inutilizabil).
                if not reason_remove:
                    if not s.get('symbol') or not s.get('direction'):
                        reason_remove = "câmpuri obligatorii lipsă (symbol/direction) — setup corupt"

                if reason_remove:
                    removed_reasons.append(f"{symbol}: {reason_remove}")
                else:
                    active_setups.append(s)

            removed_count = len(setups) - len(active_setups)

            if removed_count > 0:
                if isinstance(data, dict):
                    data['setups'] = active_setups
                    data['last_cleanup'] = now.isoformat()
                    write_data = data
                else:
                    write_data = active_setups

                # V24.8: Fresh re-read înainte de scriere — nu ștergem setup-uri noi
                # adăugate de scanner între momentul citirii și momentul scrierii.
                try:
                    with open(self.monitoring_file, 'r', encoding='utf-8') as _fresh_r:
                        _fresh = json.load(_fresh_r)
                    _fresh_setups = _fresh.get('setups', _fresh) if isinstance(_fresh, dict) else _fresh
                    _fresh_sym_map = {s.get('symbol'): s for s in _fresh_setups if isinstance(s, dict)}
                    # Păstrăm setup-urile fresh care nu erau prezente la citirea inițială
                    for _fs in active_setups:
                        _fresh_sym_map[_fs.get('symbol', '')] = _fs
                    # Re-excludem doar statusurile moarte (nu pierdem setup-urile noi)
                    _final_setups = [s for s in _fresh_sym_map.values()
                                     if s.get('status', '') not in {'EXPIRED', 'CLOSED', 'CANCELLED', 'FAILED'}]
                    if isinstance(_fresh, dict):
                        write_data = {**_fresh, 'setups': _final_setups, 'last_cleanup': now.isoformat()}
                    else:
                        write_data = _final_setups
                except Exception as _fresh_err:
                    logger.warning(f"[V37.0] fresh re-read failed — using prior write_data: {_fresh_err}")
                self._atomic_write_monitoring(write_data)

                logger.success(
                    f"🧹 [V19.20 SACRED WATCHLIST] {removed_count} setup-uri șterse "
                    f"({len(setups)}→{len(active_setups)} active). Motive: status mort / vârstă >14z / corupt."
                )
                for r in removed_reasons:
                    logger.info(f"   🗑️  Removed: {r}")
            else:
                logger.debug(
                    f"🧹 [V19.20 SACRED WATCHLIST] 0 șterse — "
                    f"{len(active_setups)} setup-uri protejate în monitorizare."
                )

        except Exception as e:
            logger.error(f"⚠️  [V19.20] Cleanup monitoring_setups failed: {e}")
    
    def _process_monitoring_setups(self):
        """
        Process all setups in monitoring_setups.json using V3.2 PULLBACK + SCALE_IN.
        
        V9.3 DEEP SLEEP: If active, skip ALL processing (zero HTTP calls).
        
        V3.2 PULLBACK FLOW:
        1. Load setup from monitoring_setups.json
        2. Fetch current market data (Daily, 4H, 1H)
        3. Check if 1H CHoCH detected → calculate Fibonacci 50%
        4. Check if pullback to Fibo 50% reached → EXECUTE ENTRY1
        5. If timeout (24h) → force entry or skip based on config
        6. After Entry1 filled → wait for 4H CHoCH for Entry2 (same as V3.1)
        """
        # ━━━ V9.3 DEEP SLEEP CHECK (MUST be first — zero cost) ━━━
        # V19.9: Verifică marker-ul system_resumed.json la fiecare ciclu
        # (Colonelul poate da /resume în orice moment — trebuie prins live, nu doar la init)
        if not self.manual_resume_triggered:
            self._check_manual_resume_marker()

        if self._check_deep_sleep():
            return  # ← EXIT: No HTTP calls, no analysis, no CPU usage
        
        if not self.monitoring_file.exists():
            return
        
        try:
            with open(self.monitoring_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                setups = data.get('setups', [])
            
            if not setups:
                return
            
            logger.debug(f"Checking {len(setups)} monitoring setups...")

            # V30.9: interval fix 5s -- nu mai e nevoie de dual-speed
            # Radar scrie la 30s, executor citeste la 5s -> max 5s lag pana la EXECUTE_NOW
            
            updated = False
            # V19.14: Tracker risc cumulativ pe sesiunea curentă de execuție
            # Previne supra-expunerea în scenarii Mass-Trigger (6 perechi simultan)
            # Max 15% risc cumulat per ciclu (3 trades × 5%) — celelalte se amână la ciclul următor
            _session_risk_used = 0.0   # procent cumulat din balanță angajat în ciclul curent
            _SESSION_RISK_MAX = 0.15   # 15% max per ciclu (ex: 300$ cont → max 45$ expus simultan)

            for i, setup in enumerate(setups):
                symbol = setup['symbol']
                status = setup.get('status', 'MONITORING')
                
                # Skip expired or closed setups, but ALLOW READY for immediate execution
                # V30.4: EXECUTE_NOW=True bypasses status filter
                # V31.0: WAITING_D1_PULLBACK si WAITING_4H_CHOCH sunt statusuri noi din Scanner V31.0
                _active_statuses_v31 = [
                    'MONITORING', 'READY', 'WAITING_POSITION_CLOSE',
                    'WAITING_D1_PULLBACK', 'WAITING_4H_CHOCH', 'WAITING_1H_CHOCH'
                ]
                if status not in _active_statuses_v31:
                    if not setup.get('EXECUTE_NOW', False):
                        continue
                    logger.info(f"[V30.4] {symbol}: status={status} dar EXECUTE_NOW=True — bypass status filter")
                
                # ✅ V10.9 SMART POSITION GUARD: Pause setup if same symbol+direction already open
                # TEMPORARY — auto-resumes when broker position closes (not permanent block)
                try:
                    import json as _json
                    active_pos_file = Path(__file__).parent / "active_positions.json"
                    if active_pos_file.exists():
                        with open(active_pos_file, encoding='utf-8') as _f:
                            _active = _json.load(_f)
                        direction = setup.get('direction', '')
                        _existing = [p for p in _active if p.get('symbol', '').upper() == symbol.upper() and p.get('direction', '').lower() == direction.lower()]
                        if _existing:
                            if status != 'WAITING_POSITION_CLOSE':
                                logger.warning(f"⏸️  V10.9 POSITION GUARD: {symbol} {direction.upper()} already open at broker — pausing setup until position closes")
                                setups[i]['status'] = 'WAITING_POSITION_CLOSE'
                                setups[i]['block_reason'] = f'{symbol} position already open — will auto-resume when closed'
                                updated = True
                            else:
                                logger.debug(f"⏸️  {symbol}: Waiting for existing position to close...")
                            continue
                        else:
                            # Position closed — resume monitoring
                            if status == 'WAITING_POSITION_CLOSE':
                                logger.success(f"▶️  V10.9 POSITION GUARD: {symbol} position closed — resuming setup monitoring!")
                                setups[i]['status'] = 'MONITORING'
                                setups[i].pop('block_reason', None)
                                # Reset execution cache so it can re-execute
                                old_exec_id = f"{symbol}_execute_{setup.get('entry_price', 0):.5f}"
                                self.signal_cache.cache.pop(old_exec_id, None)
                                updated = True
                                status = 'MONITORING'
                except Exception:
                    pass
                
                # 🔥 IN-ZONE INDICATOR
                # V3.2: choch_1h_detected (Fibo 50% logic)
                # V3.3: radar_1h_choch_detected (SNIPER MODE with FVG)
                in_zone = setup.get('choch_1h_detected', False) or setup.get('radar_1h_choch_detected', False)
                zone_emoji = "🎯" if in_zone else "🔍"
                logger.debug(f"{zone_emoji} Processing {symbol} (in_zone={in_zone})")
                
                try:
                    # ━━━ V19.8: EXECUTE_NOW — CALCUL STRUCTURAL LIVE (înlocuiește PRE-FETCH static) ━━━
                    # NZDUSD 19May bug: SL/TP static din JSON (calculat față de alt entry) + lot 0.01 fix
                    # V19.8 FIX COMPLET:
                    #   1. Descarcă date live 4H + D1 din cBot (același cache ca restul executorului)
                    #   2. Recalculează SL structural pe 4H (ultimul swing point pre-CHoCH)
                    #   3. Recalculează TP structural pe D1 (primul swing point dincolo de preț)
                    #   4. Calculează loturi dinamic: balance * 5% / (SL_pips * pip_value)
                    #   5. Sentinelă pe valorile REALE înainte de execuție
                    if setup.get('EXECUTE_NOW') == True and not setup.get('entry1_filled', False):
                        # V19.14b: Radarul a confirmat EXECUTE_NOW → h4_structure_locked implicit True
                        # Guard#4 bloca toate tradurile pentru că Radarul seta EXECUTE_NOW=True
                        # dar NU seta și h4_structure_locked=True în același scriere atomică
                        if not setup.get('h4_structure_locked', False):
                            setups[i]['h4_structure_locked'] = True
                            setup['h4_structure_locked'] = True
                            logger.info(f"🔓 [V19.14b] {symbol}: h4_structure_locked=True auto-set (EXECUTE_NOW=True implică confirmare Radar)")

                        # ── STEP 1: Entry price — din FVG-ul radar (midpoint zonă de intrare) ──────
                        _en_entry = (
                            setup.get('radar_4h_fvg_entry') or
                            setup.get('radar_1h_fvg_entry') or
                            setup.get('entry_price', 0)
                        )
                        _en_direction = setup.get('direction', 'buy').lower()
                        _pip_size_en = get_pip_size(symbol)
                        _pip_value_en = 8.33 if 'JPY' in symbol.upper() else 10.0

                        # ── V37.2: SL/TP — recalc structural LIVE (SL min 30p pe 4H) ─────────────
                        def _float_price(val):
                            try:
                                return float(val) if val not in (None, 0, '0', '') else None
                            except (TypeError, ValueError):
                                return None

                        _df_4h_en = self._get_cached_data(symbol, "H4", 225)
                        _df_d1_en = self._get_cached_data(symbol, "D1", 100)

                        _sl = None
                        _tp = None

                        if _df_4h_en is not None and not _df_4h_en.empty:
                            _sl = self._calc_structural_sl_4h(
                                symbol, _en_direction, _en_entry, _df_4h_en, _pip_size_en, MIN_SL_PIPS
                            )
                            if _sl:
                                logger.info(
                                    f"📐 [V37.2 SL LIVE 4H] {symbol}: SL={_sl:.5f} "
                                    f"({sl_pips_between(symbol, _en_entry, _sl):.1f}p)"
                                )

                        if _sl is None:
                            _sl_json = _float_price(setup.get('h4_sl_price')) or _float_price(setup.get('stop_loss'))
                            if _sl_json and sl_pips_between(symbol, _en_entry, _sl_json) >= MIN_SL_PIPS:
                                _sl = _sl_json
                                logger.info(f"📐 [V37.2 SL JSON OK] {symbol}: SL={_sl:.5f} (>= {MIN_SL_PIPS}p)")
                            elif _sl_json:
                                logger.warning(
                                    f"[V37.2 SL JSON REJECT] {symbol}: "
                                    f"{sl_pips_between(symbol, _en_entry, _sl_json):.1f}p < min {MIN_SL_PIPS}p"
                                )

                        if _df_d1_en is not None and not _df_d1_en.empty:
                            _tp = self._calc_structural_tp_d1(
                                _en_direction, _en_entry, _df_4h_en, _df_d1_en, _pip_size_en,
                                symbol=symbol, stop_loss=_sl,
                            )
                            if _tp:
                                logger.info(
                                    f"📐 [V37.2 TP LIVE D1] {symbol}: TP={_tp:.5f} "
                                    f"({sl_pips_between(symbol, _en_entry, _tp):.1f}p)"
                                )

                        if _tp is None:
                            _tp_json = _float_price(
                                setup.get('daily_tp_price') or setup.get('daily_target_price')
                            )
                            if _tp_json:
                                if _en_direction == 'buy' and _tp_json > _en_entry:
                                    _tp = _tp_json
                                elif _en_direction == 'sell' and _tp_json < _en_entry:
                                    _tp = _tp_json

                        if _tp is None:
                            _tp = _float_price(setup.get('take_profit')) or 0

                        # Validare direcție: SL sub entry pentru BUY, deasupra pentru SELL
                        if _en_direction == 'buy' and _sl and _sl >= _en_entry:
                            _sl = None
                            logger.warning(f"[V19.8 DIR GUARD] {symbol} BUY: SL deasupra entry — invalid")
                        if _en_direction == 'sell' and _sl and _sl <= _en_entry:
                            _sl = None
                            logger.warning(f"[V19.8 DIR GUARD] {symbol} SELL: SL sub entry — invalid")
                        if _en_direction == 'buy' and _tp and _tp <= _en_entry:
                            _tp = setup.get('take_profit') or 0
                            logger.warning(f"[V19.8 DIR GUARD] {symbol} BUY: TP sub entry — revert")
                        if _en_direction == 'sell' and _tp and _tp >= _en_entry:
                            _tp = setup.get('take_profit') or 0
                            logger.warning(f"[V19.8 DIR GUARD] {symbol} SELL: TP deasupra entry — revert")

                        # V37.2: respinge micro-stop — SL structural 4H trebuie >= 30 pips
                        _sl_pips_en = sl_pips_between(symbol, _en_entry, _sl) if _sl else 0.0
                        if not _sl or _sl_pips_en < MIN_SL_PIPS:
                            logger.critical(
                                f"🚨 [V37.2 MIN SL] {symbol}: {_sl_pips_en:.1f}p < {MIN_SL_PIPS}p — "
                                f"execuție anulată (structură 4H insuficientă, așteptăm setup valid)"
                            )
                            self._track_rejection(f"V37.2 min SL {symbol}: {_sl_pips_en:.1f}p")
                            setups[i].pop('EXECUTE_NOW', None)
                            setups[i]['last_rejection_reason'] = (
                                f'V37.2: SL {_sl_pips_en:.1f}p < min {MIN_SL_PIPS}p structural 4H'
                            )
                            updated = True
                            continue

                        # V30.5: Guard None/0 TP — ATR fallback
                        if not _tp or _tp == 0:
                            _atr_fb = float(setup.get('atr_daily', 0) or 0)
                            if _atr_fb > 0:
                                _tp = (_en_entry - _atr_fb * 3.0) if _en_direction == 'sell' else (_en_entry + _atr_fb * 3.0)
                                logger.warning(f"[V30.5 TP FALLBACK] {symbol}: TP=null in JSON, calculat din ATR (3x): {_tp:.5f}")
                            else:
                                _sl_dist = abs(_en_entry - _sl)
                                _tp = (_en_entry - _sl_dist * 2.0) if _en_direction == 'sell' else (_en_entry + _sl_dist * 2.0)
                                logger.warning(f"[V30.5 TP FALLBACK] {symbol}: TP=null, calculat 2xSL: {_tp:.5f}")

                        # ── STEP 5: Calcul dinamic loturi — 5% risc din balanță live ────────────────
                        _sl_pips_en = abs(_en_entry - _sl) / _pip_size_en if _sl and _en_entry else 0.0

                        # ── V19.14: GUARD RISC CUMULATIV (Mass-Trigger protection) ──────────────────
                        # Dacă deja am angajat ≥15% din cont în ciclul curent → amânăm restul
                        # Exemplu: cont 300$ → după 3 traduri (3×5%=15%) → stop, nu mai intrăm
                        _base_balance_guard = float(os.getenv('ACCOUNT_BALANCE', 1336))
                        try:
                            _th_guard = Path(__file__).parent / 'trade_history.json'
                            if _th_guard.exists():
                                with open(_th_guard, 'r', encoding='utf-8') as _fg:
                                    _tg = json.load(_fg)
                                _lg = float(_tg.get('account', {}).get('balance', 0))
                                if _lg > 0:
                                    _base_balance_guard = _lg
                        except Exception:
                            pass
                        if _session_risk_used >= _SESSION_RISK_MAX:
                            logger.warning(
                                f"⛔ [V19.14 RISK CAP] {symbol}: risc cumulat {_session_risk_used*100:.1f}% ≥ {_SESSION_RISK_MAX*100:.0f}% — "
                                f"execuție amânată la ciclul următor (30s). Balanță protejată: {_base_balance_guard:.0f}$"
                            )
                            continue  # Sărim perechea — va fi preluată în ciclul următor

                        _balance_en = _base_balance_guard
                        try:
                            _th_path_en = Path(__file__).parent / 'trade_history.json'
                            if _th_path_en.exists():
                                with open(_th_path_en, 'r', encoding='utf-8') as _tf_en:
                                    _th_en = json.load(_tf_en)
                                _live_bal_en = float(_th_en.get('account', {}).get('balance', 0))
                                if _live_bal_en > 0:
                                    _balance_en = _live_bal_en
                        except Exception as _bal2_err:
                            logger.warning(f"[V37.0] live balance read failed: {_bal2_err}")

                        if _sl_pips_en > 0:
                            _risk_budget_en = _balance_en * 0.05
                            _lot_size_en = _risk_budget_en / (_sl_pips_en * _pip_value_en)
                            _lot_size_en = round(_lot_size_en, 2)
                            _lot_size_en = max(0.01, min(_lot_size_en, 10.0))
                        else:
                            # SL lipsă complet — nu executa, nu are sens
                            logger.critical(f"🚨 [V19.8 NO SL] {symbol}: SL=0, execuție anulată — retry la ciclul următor")
                            self._track_rejection(f"EXECUTE_NOW no SL available for {symbol}")
                            setups[i].pop('EXECUTE_NOW', None)  # V22.2: pop (nu False) → radar re-triggereaza
                            setups[i]['last_rejection_reason'] = 'V19.8: SL structural indisponibil'
                            updated = True
                            continue

                        logger.success(
                            f"🔥 [V19.8 EXECUTE_NOW STRUCTURAL] {symbol}: Entry={_en_entry:.5f} "
                            f"SL={_sl:.5f} ({_sl_pips_en:.1f}p) TP={_tp:.5f} | "
                            f"Bal={_balance_en:.0f}$ | Risk=5% | Lots={_lot_size_en:.2f}"
                        )

                        # ── STEP 6: SENTINELĂ pe valorile REALE calculate structural ─────────────────
                        _sentinel_ok_en, _sentinel_reason_en = self._final_safety_check(
                            symbol=symbol,
                            direction=_en_direction,
                            entry_price=_en_entry,
                            stop_loss=_sl,
                            take_profit=_tp,
                            setup=setup
                        )
                        if not _sentinel_ok_en:
                            logger.critical(
                                f"🚨 [V19.8 SENTINELĂ] {symbol} BLOCAT: {_sentinel_reason_en}"
                            )
                            self._track_rejection(f"EXECUTE_NOW sentinel rejected: {_sentinel_reason_en[:60]}")
                            setups[i].pop('EXECUTE_NOW', None)  # V22.2: pop (nu False) → radar re-triggereaza
                            setups[i]['last_rejection_reason'] = f'Sentinel: {_sentinel_reason_en}'
                            updated = True
                            continue

                        # ── STEP 7: Execuție în cTrader ───────────────────────────────────────────────
                        _en_comment = f"D1_EXECUTE_NOW_V19.8_{_en_direction.upper()}_E1"
                        success = self.executor.execute_trade(
                            symbol=symbol,
                            direction=_en_direction,
                            entry_price=_en_entry,
                            stop_loss=_sl,
                            take_profit=_tp,
                            lot_size=_lot_size_en,
                            comment=_en_comment,
                            status='READY'
                        )
                        if success:
                            # ── STEP 8: Curățare semnal — prevenire spam ordine ────────────────────
                            setups[i]['entry1_filled'] = True
                            setups[i]['entry1_price'] = _en_entry
                            setups[i]['entry1_sl'] = _sl
                            setups[i]['entry1_tp'] = _tp
                            setups[i]['entry1_lots'] = _lot_size_en
                            setups[i]['entry1_time'] = datetime.now(timezone.utc).isoformat()
                            setups[i]['status'] = 'TRADE_OPEN'  # V31.0: status explicit post-executie
                            setups[i].pop('EXECUTE_NOW', None)  # eliminare completa cheie
                            updated = True
                            # V19.14: Actualizare tracker risc cumulativ
                            _session_risk_used += 0.05
                            logger.success(f"[V31.0 EXECUTE_NOW] {symbol} executat structural: "
                                           f"SL={_sl_pips_en:.1f}p | Lots={_lot_size_en:.2f} | 5% risk "
                                           f"| Risc cumulat sesiune: {_session_risk_used*100:.0f}%")
                            # V19.14: Anti rate-limit cTrader — 500ms pauză între ordine consecutive
                            # Fără acest sleep, 6 ordine MARKET ajung la broker în <50ms → risc de reject
                            import time as _time_module
                            _time_module.sleep(0.5)
                        else:
                            logger.error(f"❌ [V19.8 EXECUTE_NOW] {symbol} execuție respinsă de Risk Manager")
                            self._track_rejection(f"EXECUTE_NOW loss limit rejected for {symbol}")
                            setups[i].pop('EXECUTE_NOW', None)
                            setups[i]['last_rejection_time'] = datetime.now(timezone.utc).isoformat()
                            setups[i]['last_rejection_reason'] = 'Risk Manager: EXECUTE_NOW rejected'
                            updated = True
                            try:
                                _rm = getattr(self.executor, 'risk_manager', None)
                                if _rm is not None:
                                    _pnl = _rm.get_daily_pnl()
                                    _bal = float(os.getenv('ACCOUNT_BALANCE', 1336))
                                    try:
                                        _th_path_ds = Path(__file__).parent / 'trade_history.json'
                                        if _th_path_ds.exists():
                                            with open(_th_path_ds, 'r', encoding='utf-8') as _tf_ds:
                                                _th_ds = json.load(_tf_ds)
                                            _live_bal_ds = float(_th_ds.get('account', {}).get('balance', 0))
                                            if _live_bal_ds > 0:
                                                _bal = _live_bal_ds
                                    except Exception as _ds_tg_err:
                                        logger.warning(f"[V37.0] Deep Sleep Telegram alert failed: {_ds_tg_err}")
                                    _loss_pct = (_pnl.get('total_pnl', 0) / _bal * 100) if _bal > 0 else 0
                                    _limit = getattr(_rm, 'max_daily_loss_pct', 10.0)
                                    if _loss_pct <= -_limit and not self._loss_limit_bypassed():
                                        self._enter_deep_sleep(
                                            f"Daily loss limit reached ({_loss_pct:.2f}%) — auto Deep Sleep"
                                        )
                                        logger.warning(f"😴 [V19.8] Deep Sleep activat: {_loss_pct:.2f}% loss >= -{_limit}%")
                                    elif _loss_pct <= -_limit and self._loss_limit_bypassed():
                                        logger.warning(
                                            f"🔱 [V39.1] Daily loss {_loss_pct:.2f}% >= -{_limit}% "
                                            f"DAR bypass activ — Deep Sleep BLOCAT"
                                        )
                            except Exception as _ds_err:
                                logger.warning(f"⚠️ Deep Sleep check error: {_ds_err}")
                        continue
                    # ━━━ END V19.8 EXECUTE_NOW STRUCTURAL ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    # V9.3 CACHED FETCH: D1=4h cache, H4=30m cache, H1=5m cache
                    df_daily = self._get_cached_data(symbol, "D1", 100)
                    df_4h = self._get_cached_data(symbol, "H4", 225)
                    df_1h = self._get_cached_data(symbol, "H1", 225)
                    
                    if df_daily is None or df_4h is None or df_1h is None:
                        logger.warning(f"⚠️  Could not fetch data for {symbol}, skipping")
                        continue
                    
                    # Check if Entry1 already filled
                    entry1_filled = setup.get('entry1_filled', False)
                    
                    # V4.3 FIX-016: Force execute if status is READY
                    if status == 'READY' and not entry1_filled:
                        # 🛡️ V7.1 DUPLICATE GUARD: Check broker before execution
                        if self._symbol_already_at_broker(symbol):
                            logger.warning(f"🛡️ SKIP {symbol}: Already has open position at broker (duplicate guard)")
                            setups[i]['status'] = 'TRADE_OPEN'  # V31.0
                            setups[i]['entry1_filled'] = True
                            setups[i]['force_executed'] = True
                            setups[i]['skip_reason'] = 'duplicate_guard_broker_position_exists'
                            updated = True
                            continue
                        
                        logger.success(f"🚀 EXECUTING {symbol} (status: READY, forced by owner)")
                        
                        # ✅ V10.5 AUDIT FIX: Re-validate 4H body closure before READY execution
                        # READY setups loaded from disk may have a stale h4_structure_locked=True
                        # from a prior scan session. Re-check body closure now to ensure the
                        # 4H CHoCH that originally triggered READY is still recent and valid.
                        # V10.8: Extins de la 12 → 48 bare (era prea strict — bloca CHoCH de 35 bare = 5 zile, valide structural)
                        try:
                            df_4h_recheck = self._get_cached_data(symbol, "H4", 225)
                            if df_4h_recheck is not None and not df_4h_recheck.empty:
                                expected_dir_rc = 'bullish' if setup['direction'] == 'buy' else 'bearish'
                                h4_chochs_rc, _ = self.smc_detector.detect_choch_and_bos(df_4h_recheck)
                                h4_still_valid = False
                                for h4rc in reversed(h4_chochs_rc):
                                    if (len(df_4h_recheck) - 1 - h4rc.index) > 200:  # V16.4 FIX BUG#4: 48→200 bare
                                        continue
                                    if h4rc.direction != expected_dir_rc:
                                        continue
                                    o_ = df_4h_recheck['open'].iloc[h4rc.index]
                                    c_ = df_4h_recheck['close'].iloc[h4rc.index]
                                    bh = max(o_, c_); bl = min(o_, c_)
                                    if expected_dir_rc == 'bullish' and bh <= h4rc.break_price:
                                        continue
                                    if expected_dir_rc == 'bearish' and bl >= h4rc.break_price:
                                        continue
                                    h4_still_valid = True
                                    break
                                if not h4_still_valid:
                                    logger.warning(f"   ⚠️ V10.5 READY GUARD: {symbol} 4H CHoCH no longer valid (stale/wick-only). Reverting to MONITORING.")
                                    setups[i]['status'] = 'MONITORING'
                                    setups[i]['h4_structure_locked'] = False
                                    updated = True
                                    continue
                                logger.success(f"   ✅ V10.5 READY GUARD: {symbol} 4H body closure re-confirmed. Executing.")
                        except Exception as rc_err:
                            logger.warning(f"   ⚠️ V10.5 READY GUARD: 4H recheck failed for {symbol}: {rc_err} — proceeding")
                        
                        # V10.4: Strategy tag for forced execution
                        forced_strategy = setup.get('strategy_type', 'unknown').upper()
                        forced_comment = f"D1_{forced_strategy}_4H_SYNC_FORCED_E1"
                        
                        success = self.executor.execute_trade(
                            symbol=symbol,
                            direction=setup['direction'],
                            entry_price=setup['entry_price'],
                            stop_loss=setup['stop_loss'],
                            take_profit=setup['take_profit'],
                            lot_size=0.01,  # Will be recalculated by Risk Manager
                            comment=forced_comment,
                            status='READY'  # Force bypass status check in executor
                        )
                        
                        if success:
                            setups[i]['entry1_filled'] = True
                            setups[i]['entry1_price'] = setup['entry_price']
                            setups[i]['entry1_time'] = datetime.now(timezone.utc).isoformat()
                            setups[i]['status'] = 'TRADE_OPEN'  # V31.0
                            setups[i]['force_executed'] = True
                            updated = True
                            logger.success(f"✅ {symbol} Entry 1 executed successfully (forced)")
                        else:
                            logger.error(f"❌ {symbol} Entry 1 execution failed (rejected by Risk Manager)")
                            # V10.2 FIX: Do NOT enter Deep Sleep on rejection
                            self._track_rejection(f"READY execution rejected for {symbol}")
                            setups[i]['status'] = 'MONITORING'  # V31.0: revenim la MONITORING (nu ACTIVE)
                            setups[i]['last_rejection_time'] = datetime.now(timezone.utc).isoformat()
                            setups[i]['last_rejection_reason'] = 'Risk Manager: daily loss limit'
                            updated = True
                            logger.warning(f"⚠️ {symbol}: READY → MONITORING (rejected, will retry when risk allows)")
                        
                        continue  # Skip pullback logic for READY status
                    
                    if not entry1_filled:
                        # ━━━ V31.0 EXECUTOR BLIND — zero initiativa SMC proprie ━━━━━━━━━━
                        # EXECUTE_NOW este tratata EXCLUSIV in blocul V19.8 de mai sus.
                        # Daca ajungem aici cu entry1_filled=False = EXECUTE_NOW nu era setat
                        # (lag 5s intre Radar si Executor) sau V19.8 a rejectat si a pop-at flagul.
                        # FIX Bug #01 & #18: eliminam _check_radar_entry() si _check_pullback_entry()
                        # din calea de executie — evitam bypass al Risk Manager si dual personality.
                        # Singura actiune valida = KEEP_MONITORING → asteptam EXECUTE_NOW live.
                        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                        result = {'action': 'KEEP_MONITORING', 'reason': '[V31.0] Blind executor — asteptam EXECUTE_NOW de la Radar'}
                        
                        if result['action'] == 'CHOCH_1H_DETECTED':
                            # 🔔 1H CHoCH just detected - Update setup and RESEND notification
                            setups[i]['choch_1h_detected'] = True
                            setups[i]['choch_1h_timestamp'] = result.get('choch_timestamp')
                            setups[i]['fibo_data'] = result.get('fibo_data', {})
                            setups[i]['choch_1h_price'] = result.get('choch_price')
                            updated = True
                            
                            # V15.0 EVENT ALERT: 1H CHoCH confirmat — trimite 1H chart
                            if not setups[i].get('alert_1h_sent', False):
                                try:
                                    setup_data_1h = {
                                        'symbol': symbol,
                                        'direction': setup.get('direction', 'buy'),
                                        'entry_price': setup.get('entry_price', 0),
                                        'stop_loss': setup.get('stop_loss', 0),
                                        'take_profit': setup.get('take_profit', 0),
                                        'risk_reward': setup.get('risk_reward', 0),
                                        'choch_1h_price': result.get('choch_price', setup.get('entry_price', 0)),
                                        'w1_bias': setup.get('w1_bias', 'NEUTRAL'),
                                    }
                                    self.telegram.send_1h_choch_alert(setup_data_1h, df_1h)
                                    setups[i]['alert_1h_sent'] = True
                                    updated = True
                                    logger.info(f"📱 V15.0 1H CHoCH Alert sent: {symbol} @ {result.get('choch_price', 'N/A')}")
                                except Exception as alert_err:
                                    logger.warning(f"⚠️ V15.0 1H alert error for {symbol}: {alert_err}")
                            else:
                                logger.info(f"📱 {symbol} 1H CHoCH @ {result.get('choch_price', 'N/A')} — ARMAGEDDON pending via position_monitor")
                            
                            continue  # Skip to next iteration to wait for pullback
                        
                        # V4.0: Handle all execution action types
                        if result['action'] in ['EXECUTE_ENTRY1', 'EXECUTE_ENTRY1_CONTINUATION', 'EXECUTE_ENTRY1_TIMEOUT']:
                            # 🛡️ V3.8 ANTI-SPAM: Check if this execution was already triggered
                            execution_id = f"{symbol}_execute_{result['entry_price']:.5f}"
                            
                            if self.signal_cache.is_processed(execution_id):
                                logger.warning(f"SKIP EXECUTION: {symbol} already executed (cache hit)")
                                # V30.6: sterge EXECUTE_NOW din JSON -- altfel ramine in JSON si
                                # spameaza la infinit in AGGRESSIVE MODE 5s (bucla infinita)
                                setups[i].pop('EXECUTE_NOW', None)
                                setups[i]['entry1_filled'] = True  # confirma executia anterioara
                                updated = True
                                continue
                            
                            # ✅ V10.9 ANTI-DOUBLE: Also check rejection cooldown (timestamp in setup)
                            rejection_ts = setup.get('last_rejection_ts', 0)
                            if rejection_ts and (time.time() - rejection_ts) < 300:  # 5 min cooldown
                                remaining = int(300 - (time.time() - rejection_ts))
                                logger.warning(f"🔕 V10.9 COOLDOWN: {symbol} rejected recently — {remaining}s remaining")
                                continue
                            
                            # ✅ V10.9 PRE-LOCK: Mark execution_id BEFORE calling _execute_entry
                            # Prevents same-cycle double execution (race condition fix)
                            self.signal_cache.mark_processed(execution_id)
                            
                            # ━━━ Fix #6: RR SAFETY BARRIER — revalidare RR la prețul de INTRARE ━━━
                            # V24.8 FIX: RR calculat față de entry_price (ordinul limit), NU față de current_price.
                            # Motivul: current_price fluctuează înainte de activarea ordinului limit.
                            # Un trade valid cu RR 5:1 la entry poate părea sub 4:1 dacă prețul a ajuns deja
                            # mai aproape de TP (sau invers — respins greșit). Entry_price = contractul real.
                            _entry_px = result.get('entry_price', setup.get('entry_price', 0))
                            _sl_px = result.get('stop_loss', setup.get('stop_loss', 0))
                            _tp_px = setup.get('daily_tp_price') or setup.get('take_profit', 0)
                            if _entry_px and _sl_px and _tp_px:
                                _risk_real = abs(_entry_px - _sl_px)
                                _reward_real = abs(_tp_px - _entry_px)
                                _rr_real = _reward_real / _risk_real if _risk_real > 0 else 0
                                if _rr_real < 4.0:
                                    logger.warning(f"⛔ [Fix #6 RR BARRIER] {symbol}: RR_Real=1:{_rr_real:.2f} < 1:4 la execuție — BLOCAT. Setup → EXPIRED.")
                                    setups[i]['status'] = 'EXPIRED'
                                    setups[i]['expired_reason'] = f'RR_Real={_rr_real:.2f} < 4.0 at execution'
                                    updated = True
                                    try:
                                        self.telegram.send_setup_expired_alert(
                                            symbol=symbol,
                                            direction=setup.get('direction', '?'),
                                            reason=f"RR Real la execuție = 1:{_rr_real:.2f} < 1:4 minim structural — trade blocat de Garda de Risc"
                                        )
                                    except Exception as _tg_exp_err:
                                        logger.warning(f"[V37.0] setup expired Telegram alert failed for {symbol}: {_tg_exp_err}")
                                    continue
                                else:
                                    logger.info(f"✅ [Fix #6 RR OK] {symbol}: RR_Real=1:{_rr_real:.2f} ≥ 1:4 — execuție permisă")
                            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                            # ━━━ Fix #7: SL ULTIMATUM BARRIER — max pips hard cap ━━━
                            # V24.4 FIX: pip_size și hard cap sunt acum asset-aware.
                            # BUG anterior: _pip_sz = 0.0001 pentru BTC → SL în milioane de pips → blocat mereu.
                            # V24.7 FIX: _sl_entry folosește ÎNTOTDEAUNA setup.entry_price (FVG edge structural),
                            # NU result['entry_price'] care pentru CONTINUATION = current_price (vârful impulsului).
                            # Exemplu BUG: BTC current=97000, SL=95000, entry_FVG=96000
                            #   ÎNAINTE (greșit): abs(97000-95000)/1.0 = 2000 pips → BLOCAT fals
                            #   ACUM (corect):    abs(96000-95000)/1.0 = 1000 pips → PASS ✅
                            _sym_up7 = symbol.upper()
                            if any(x in _sym_up7 for x in ['BTC', 'ETH', 'LTC', 'XRP', 'ADA', 'DOGE']):
                                _pip_sz = 1.0      # Crypto: 1 pip = $1
                                _sl_hard_cap = 2000  # BTC: SL max $2000 structural
                            elif any(x in _sym_up7 for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
                                _pip_sz = 0.10     # Gold: 1 pip = $0.10
                                _sl_hard_cap = 500   # Gold: SL max 500 pips ($50)
                            elif any(x in _sym_up7 for x in ['OIL', 'BRENT', 'WTI']):
                                _pip_sz = 0.01
                                _sl_hard_cap = 300
                            elif 'JPY' in _sym_up7:
                                _pip_sz = 0.01
                                _sl_hard_cap = 150
                            else:
                                _pip_sz = 0.0001   # Forex standard
                                _sl_hard_cap = 150   # Forex: SL max 150 pips
                            # V24.7: ÎNTOTDEAUNA setup.entry_price (FVG structural) ca reper, NU current_price
                            _sl_entry = setup.get('entry_price', 0) or result.get('entry_price', 0)
                            _sl_val = result.get('stop_loss', setup.get('stop_loss', 0))
                            _is_execute_now = result.get('entry_type') == 'EXECUTE_NOW'
                            # V24.8 FIX #3: SL Hard Cap se validează EXCLUSIV la EXECUTE_NOW.
                            # În stările WAITING (WAITING_4H_CHOCH, WAITING_4H_PULLBACK),
                            # SL-ul e calculat din structura Daily/curentă — poate fi enorm (BTC).
                            # Validarea corectă: DOAR după CHoCH 4H confirmat, din entry FVG → swing local 4H.
                            if _sl_entry and _sl_val and _is_execute_now:
                                _sl_pips = abs(_sl_entry - _sl_val) / _pip_sz
                                if _sl_pips > _sl_hard_cap:
                                    logger.critical(f"🚨 [Fix #7 SL ULTIMATUM] {symbol}: SL={_sl_pips:.1f} pips (entry={_sl_entry:.5f}→sl={_sl_val:.5f}) > {_sl_hard_cap} — BLOCAT DEFINITIV. Setup → EXPIRED.")
                                    setups[i]['status'] = 'EXPIRED'
                                    setups[i]['expired_reason'] = f'SL={_sl_pips:.1f} pips > {_sl_hard_cap} hard cap'
                                    updated = True
                                    try:
                                        self.telegram.send_setup_expired_alert(
                                            symbol=symbol,
                                            direction=setup.get('direction', '?'),
                                            reason=f"SL structural = {_sl_pips:.1f} pips depăşeşte limita hard cap de {_sl_hard_cap} pips — risc neacceptabil"
                                        )
                                    except Exception as _tg_exp_err:
                                        logger.warning(f"[V37.0] setup expired Telegram alert failed for {symbol}: {_tg_exp_err}")
                                    continue
                                else:
                                    logger.info(f"✅ [Fix #7 SL OK] {symbol}: SL={_sl_pips:.1f} pips (entry={_sl_entry:.5f}→sl={_sl_val:.5f}) ≤ {_sl_hard_cap} — execuție permisă")
                            elif _is_execute_now:
                                logger.info(f"✅ [Fix #7 SKIP — EXECUTE_NOW] {symbol}: SL structural acceptat direct")
                            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                            # 🔥🔥🔥 AGGRESSIVE EXECUTION - INSTANT SIGNALS.JSON WRITE!
                            logger.critical(f"🔥 TRIGGER: {symbol} confirmed CHoCH + Pullback. Pushing to Executor NOW!")
                            logger.success(f"🚀 EXECUTING {symbol} Entry 1: {setup['direction'].upper()} @ {result['entry_price']:.5f}")
                            logger.info(f"   SL: {result['stop_loss']:.5f} | TP: {setup['take_profit']:.5f}")
                            logger.info(f"   Reason: {result.get('reason', 'Pullback reached')}")
                            logger.warning(f"   ⚡ WRITING TO signals.json INSTANTLY - NO DELAYS!")
                            
                            # Execute Entry 1 (pullback, momentum, or timeout)
                            success = self._execute_entry(
                                setup=setup,
                                entry_number=1,
                                entry_price=result['entry_price'],
                                stop_loss=result['stop_loss'],
                                take_profit=setup['take_profit'],
                                position_size=self.execution_strategy.get('entry1_position_size', 0.5)
                            )
                            
                            if not success:
                                # ✅ V10.9 ANTI-LOOP: Persist rejection timestamp to setups[i]
                                setups[i]['last_rejection_ts'] = time.time()
                                updated = True
                                continue
                            
                            if success:
                                logger.critical(f"✅ {symbol} SIGNAL WRITTEN TO signals.json - cTrader will execute in <10s!")
                                
                                # 🛡️ Mark execution as processed in persistent cache
                                self.signal_cache.mark_processed(execution_id)
                                logger.debug(f"💾 Execution cached: {execution_id}")
                                
                                # Update setup with Entry 1 details and pullback data
                                setups[i]['entry1_filled'] = True
                                setups[i]['entry1_price'] = result['entry_price']
                                setups[i]['entry1_time'] = datetime.now(timezone.utc).isoformat()
                                setups[i]['entry1_lots'] = self.execution_strategy.get('entry1_position_size', 0.5)
                                setups[i]['choch_1h_detected'] = True
                                setups[i]['choch_1h_timestamp'] = result.get('choch_timestamp')
                                setups[i]['fibo_data'] = result.get('fibo_data', {})
                                setups[i]['pullback_status'] = 'PULLBACK_REACHED' if result['action'] == 'EXECUTE_ENTRY1' else 'MOMENTUM_ENTRY'
                                setups[i]['entry_reason'] = result.get('reason', 'Entry executed')
                                updated = True
                                logger.success(f"✅ V4.0 Entry 1 executed for {symbol} - {result.get('reason', 'Executed')}")
                        
                        elif result['action'] == 'SKIP_SETUP':
                            # V4.0: Timeout reached but distance too far - remove setup
                            logger.warning(f"⏰ {symbol}: Timeout + distance exceeded - removing setup")
                            setups.pop(i)
                            updated = True
                            continue

                        elif result['action'] == 'EXPIRE_SETUP':
                            # Fix #1: TP reached before pullback OR 12H timeout — EXPIRED
                            logger.warning(f"⛔ [Fix #1 EXPIRE_SETUP] {symbol}: {result.get('reason', 'Setup expirat')} — slot eliberat.")
                            setups[i]['status'] = 'EXPIRED'
                            setups[i]['expired_reason'] = result.get('reason', 'Fix#1 EXPIRE_SETUP')
                            updated = True
                            continue

                        elif result['action'] == 'TIMEOUT_FORCE_ENTRY':
                            # Fix #1: TIMEOUT_FORCE_ENTRY ELIMINAT — treat as EXPIRED
                            logger.warning(f"⛔ [Fix #1] {symbol}: TIMEOUT_FORCE_ENTRY blocat — nu forțăm intrarea. Setup → EXPIRED.")
                            setups[i]['status'] = 'EXPIRED'
                            setups[i]['expired_reason'] = 'Fix#1: TIMEOUT_FORCE_ENTRY eliminat — nu alergăm după preț'
                            updated = True
                            continue
                        
                        elif result['action'] == 'KEEP_MONITORING':
                            # Update pullback tracking data
                            if 'fibo_data' in result:
                                setups[i]['choch_1h_detected'] = True
                                setups[i]['choch_1h_timestamp'] = result.get('choch_timestamp')
                                setups[i]['fibo_data'] = result['fibo_data']
                                setups[i]['pullback_status'] = 'WAITING_PULLBACK'
                                setups[i]['pullback_distance_pips'] = result.get('distance_to_fibo', 0)
                                updated = True
                            
                            logger.info(f"⏳ {symbol}: {result.get('reason', 'Waiting')}")
                        
                        elif result['action'] == 'EXPIRE':
                            setups[i]['status'] = 'EXPIRED'
                            setups[i]['expire_reason'] = result.get('reason')
                            updated = True
                            logger.warning(f"❌ {symbol}: {result.get('reason')}")
                    
                    else:
                        # V37.0: Entry 2 scale-in dezactivat — arhitectură Radar-only (EXECUTE_NOW singur trigger)
                        logger.debug(
                            f"[V37.0] {symbol}: Entry 2 scale-in dezactivat "
                            f"(entry1_filled=True) — skip validate_choch_confirmation_scale_in"
                        )
                        continue
                
                except Exception as e:
                    logger.error(f"❌ Error processing {symbol}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            # Save updated setups
            if updated:
                # ━━━ V22.3 RACE CONDITION FIX ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # BUG: Executorul citea fișierul la start de ciclu (t=0), procesa 30s,
                # iar dacă daily_scanner.py adăuga setups noi în interval (t=15s),
                # write-back-ul executorului (t=30s) ștergea setups-urile noi —
                # pentru că `data['setups'] = setups` conținea doar setups-urile VECHI.
                # Simptom: GBPCAD și EURJPY dispăreau din monitoring în 1 minut.
                #
                # FIX: Re-citim fișierul fresh înainte de write-back.
                # Merge policy: setups procesate de executor (cu last_check updated) au
                # prioritate; setups noi adăugate de scanner în interval sunt PĂSTRATE.
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                try:
                    with open(self.monitoring_file, 'r', encoding='utf-8') as _f_fresh:
                        _fresh_data = json.load(_f_fresh)
                    _fresh_setups = _fresh_data.get('setups', []) if isinstance(_fresh_data, dict) else _fresh_data
                    _processed_map = {
                        self._setup_merge_key(s): s for s in setups if s.get('symbol')
                    }
                    _merged = []
                    for _fs in _fresh_setups:
                        _key = self._setup_merge_key(_fs)
                        if _key[0] and _key in _processed_map:
                            _merged.append(
                                self._merge_processed_with_fresh_radar(_processed_map[_key], _fs)
                            )
                        else:
                            _merged.append(_fs)
                    _fresh_keys = {self._setup_merge_key(s) for s in _fresh_setups if s.get('symbol')}
                    for _ps in setups:
                        _pk = self._setup_merge_key(_ps)
                        if _pk[0] and _pk not in _fresh_keys:
                            _merged.append(_ps)
                    if isinstance(_fresh_data, dict):
                        _fresh_data['setups'] = _merged
                        _fresh_data['last_update'] = datetime.now(timezone.utc).isoformat()
                        _write_data = _fresh_data
                    else:
                        _write_data = _merged
                except Exception as _merge_err:
                    # Fallback la comportamentul vechi dacă merge-ul eșuează
                    logger.warning(f"⚠️ [V22.3] Merge fresh read failed ({_merge_err}) — fallback la write direct")
                    data['setups'] = setups
                    data['last_update'] = datetime.now(timezone.utc).isoformat()
                    _write_data = data

                # V24.9: Atomic write — previne coruperea JSON la crash între open(w) și json.dump
                self._atomic_write_monitoring(_write_data)
                logger.debug(f"💾 [V24.9] Updated monitoring_setups.json (atomic write)")
        
        except Exception as e:
            logger.error(f"❌ Error in _process_monitoring_setups: {e}")
            import traceback
            traceback.print_exc()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # V37.2: SL/TP structural live — 4H swing + D1 target
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _calc_structural_sl_4h(
        self,
        symbol: str,
        direction: str,
        entry: float,
        df_4h,
        pip_size: float,
        min_sl_pips: float = MIN_SL_PIPS,
    ):
        """
        SL = ultimul swing 4H valid cu distanta >= min_sl_pips (default 30p) fata de entry.
        Evita micro-stop-ul de 3-5p (AUDJPY bug) care umfla lotul la 5% risc.
        """
        if df_4h is None or df_4h.empty or not entry:
            return None
        sl_buffer = pip_size * 2
        min_dist = min_sl_pips * pip_size
        try:
            _atr_4h = float((df_4h['high'] - df_4h['low']).rolling(14).mean().iloc[-1])
            min_dist = max(min_dist, _atr_4h * 0.3)
        except Exception:
            pass

        direction = direction.lower()
        if direction == 'buy':
            swings = self.smc_detector.detect_swing_lows(df_4h)
            candidates = [
                s for s in swings
                if float(df_4h['low'].iloc[s.index]) < entry
                and (entry - float(df_4h['low'].iloc[s.index])) >= min_dist
            ]
            if candidates:
                best = sorted(candidates, key=lambda s: s.index, reverse=True)[0]
                return float(df_4h['low'].iloc[best.index]) - sl_buffer
            window_low = float(df_4h['low'].iloc[-40:].min())
            if entry - window_low >= min_dist:
                return window_low - sl_buffer
        else:
            swings = self.smc_detector.detect_swing_highs(df_4h)
            candidates = [
                s for s in swings
                if float(df_4h['high'].iloc[s.index]) > entry
                and (float(df_4h['high'].iloc[s.index]) - entry) >= min_dist
            ]
            if candidates:
                best = sorted(candidates, key=lambda s: s.index, reverse=True)[0]
                return float(df_4h['high'].iloc[best.index]) + sl_buffer
            window_high = float(df_4h['high'].iloc[-40:].max())
            if window_high - entry >= min_dist:
                return window_high + sl_buffer
        return None

    def _calc_structural_tp_d1(
        self,
        direction: str,
        entry: float,
        df_4h,
        df_d1,
        pip_size: float,
        symbol: str = '',
        stop_loss: float = None,
    ):
        """
        TP = primul swing D1 lichiditate NEATINS recent in directia trade-ului.
        V37.7: exclude swing-uri deja sweep-uite (ex. BTC low luat → pullback sus).
        """
        if df_d1 is None or df_d1.empty or not entry:
            return None
        try:
            from pip_utils import liquidity_already_swept as _liq_swept

            current = float(df_4h['close'].iloc[-1]) if df_4h is not None and not df_4h.empty else float(df_d1['close'].iloc[-1])
            _tr = (
                (df_d1['high'] - df_d1['low'])
                .combine((df_d1['high'] - df_d1['close'].shift(1)).abs(), max)
                .combine((df_d1['low'] - df_d1['close'].shift(1)).abs(), max)
            )
            _atr_d1 = float(_tr.rolling(14).mean().iloc[-1])
            _min_tp_dist = _atr_d1 * 1.0
            _max_tp_dist = _atr_d1 * 8.0
            _sweep_tol = pip_size * 10 if pip_size else 0.0
            _sweep_lookback = 25 if any(x in symbol.upper() for x in ['BTC', 'ETH']) else 15

            if stop_loss:
                _sl_dist = abs(entry - float(stop_loss))
                _min_tp_dist = max(_min_tp_dist, _sl_dist * 2.0)

            direction = direction.lower()
            if direction == 'buy':
                swings = self.smc_detector.detect_swing_highs(df_d1)
                targets = [
                    s for s in swings
                    if s.price > current
                    and (s.price - entry) >= _min_tp_dist
                    and (s.price - entry) <= _max_tp_dist
                    and not _liq_swept(df_d1, s.price, 'high', lookback=_sweep_lookback, tolerance=_sweep_tol)
                ]
                if targets:
                    nearest = min(targets, key=lambda s: s.price)
                    return float(df_d1['high'].iloc[nearest.index])
            else:
                swings = self.smc_detector.detect_swing_lows(df_d1)
                targets = [
                    s for s in swings
                    if s.price < current
                    and (entry - s.price) >= _min_tp_dist
                    and (entry - s.price) <= _max_tp_dist
                    and not _liq_swept(df_d1, s.price, 'low', lookback=_sweep_lookback, tolerance=_sweep_tol)
                ]
                if targets:
                    nearest = max(targets, key=lambda s: s.price)
                    logger.info(
                        f"[V37.7 TP D1] {symbol or '?'} SELL: swing low neatin={nearest.price:.5f} "
                        f"(sweep-uit excluse, min_dist={_min_tp_dist:.1f})"
                    )
                    return float(df_d1['low'].iloc[nearest.index])
                logger.warning(
                    f"[V37.7 TP D1] {symbol or '?'} SELL: niciun swing low D1 valid — "
                    f"lichiditatea sub pret e deja sweep-uita sau prea aproape"
                )
        except Exception as _tp_err:
            logger.warning(f"[V37.2] structural TP D1 calc failed: {_tp_err}")
        return None

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Fix #13: SENTINELA DE RISC — 4 bariere finale înainte de execuție
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _final_safety_check(self, symbol: str, direction: str, entry_price: float,
                            stop_loss: float, take_profit: float, setup: dict) -> tuple:
        """
        Fix #13: Sentinela finală — 4 bariere de risc validate înainte de execuția cTrader.
        Returns: (passed: bool, reason: str)
        """
        pip_size = get_pip_size(symbol)
        sl_pips = sl_pips_between(symbol, entry_price, stop_loss)
        tp_pips = abs(take_profit - entry_price) / pip_size if pip_size > 0 else 0

        # ── Guard 2b: SL minim structural (V37.2) — respinge micro-stop ─────────
        if sl_pips < MIN_SL_PIPS:
            return False, (f"Guard#2b SL={sl_pips:.1f}p < {MIN_SL_PIPS}p min structural 4H "
                           f"(micro-stop interzis)")

        # ── Guard 1: RR Net cu comisionul cTrader (~0.7 pips per side) ──────────
        commission_pips = 0.7  # cTrader spread/commission approximation per side
        net_reward = tp_pips - commission_pips
        net_risk   = sl_pips + commission_pips
        rr_net = net_reward / net_risk if net_risk > 0 else 0
        # V19.14b: 1:4 → 1:2 — pragul 1:4 bloca setup-uri valide cu TP realist
        # Pe Daily structural, 1:2 net este acceptabil (ex: SL 30p TP 60p = 1:2)
        if rr_net < 2.0:
            return False, (f"Guard#1 RR Net={rr_net:.2f} < 1:2 "
                           f"(TP={tp_pips:.1f}p SL={sl_pips:.1f}p comision~{commission_pips}p)")

        # ── Guard 2: SL Sniper Limit — max 100 pips ─────────────────────────────
        if sl_pips > MAX_SL_PIPS:
            return False, f"Guard#2 SL={sl_pips:.1f} pips > {MAX_SL_PIPS} sniper cap (whale stop)"

        # ── Guard 3: Capital Guard — pierderea estimată ≤ 5.1% din balanță ──────
        balance = float(os.getenv('ACCOUNT_BALANCE', 1336))
        try:
            _th_path = Path(__file__).parent / 'trade_history.json'
            if _th_path.exists():
                with open(_th_path, 'r', encoding='utf-8') as _tf:
                    _th = json.load(_tf)
                _live_bal = float(_th.get('account', {}).get('balance', 0))
                if _live_bal > 0:
                    balance = _live_bal
        except Exception as _bal_err:
            logger.warning(f"[V37.0] Guard#3 balance read failed — using env fallback: {_bal_err}")

        # pip_value_per_lot: USD profit per pip, per standard lot (100k units)
        # JPY pairs ≈ $8.33/pip, non-JPY ≈ $10/pip (USD-quoted)
        pip_value_per_lot = 8.33 if 'JPY' in symbol.upper() else 10.0
        risk_budget = balance * 0.05
        lots = risk_budget / (sl_pips * pip_value_per_lot) if sl_pips > 0 else 0
        estimated_loss = lots * sl_pips * pip_value_per_lot
        estimated_loss_pct = estimated_loss / balance if balance > 0 else 0
        if estimated_loss_pct > 0.051:
            return False, (f"Guard#3 Risc estimat={estimated_loss_pct*100:.2f}% > 5.1% "
                           f"(lots={lots:.3f} sl={sl_pips:.1f}p bal={balance:.0f})")

        # ── Guard 4: D1 Bias → 4H CHoCH aliniere confirmată ────────────────────
        # V17 FIX BUG#9: h4_bias_locked nu există — cheia corectă este h4_structure_locked
        # Fallback la h4_bias_locked pentru backward-compat cu setup-uri vechi
        h4_locked = setup.get('h4_structure_locked', False) or setup.get('h4_bias_locked', False)
        strategy_type = setup.get('strategy_type', '').upper()
        if not h4_locked:
            return False, (f"Guard#4 h4_structure_locked=False — CHoCH 4H neconfirmat "
                           f"pentru strategie {strategy_type or 'UNKNOWN'}")
        # V18: acceptăm și 'continuation_counter_w1', 'reversal_counter_w1' (tagged de daily_scanner cu W1 bias)
        _st_base = strategy_type.split('_')[0] if strategy_type else ''
        if _st_base not in ('REVERSAL', 'CONTINUITY', 'CONTINUATION'):
            return False, (f"Guard#4 strategy_type='{strategy_type}' necunoscut "
                           f"— setup posibil stale sau corupt")

        return True, "TOATE 4 GĂRZI TRECUTE — execuție autorizată"
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _execute_entry(self, setup: dict, entry_number: int, entry_price: float, 
                       stop_loss: float, take_profit: float, position_size: float,
                       risk_override_percent: float = None) -> bool:
        """
        Execute Entry 1 or Entry 2 via cTrader.
        
        Args:
            setup: Setup dict from monitoring_setups.json
            entry_number: 1 or 2
            entry_price: Entry price
            stop_loss: SL price
            take_profit: TP price
            position_size: Lot size (overridden by risk manager dynamic calc)
            risk_override_percent: V14.1 — optional risk % override for scale-in Entry 2.
                                   None = use SUPER_CONFIG default (5%).
                                   Entry 2 passes 7.5% for slightly larger lot.
        
        Returns:
            bool: True if successful
        """
        try:
            symbol = setup['symbol']
            direction = setup['direction']
            
            # ━━━ Fix #13: SENTINELA FINALĂ — validare obligatorie la execuție ━━━
            _sentinel_ok, _sentinel_reason = self._final_safety_check(
                symbol=symbol, direction=direction,
                entry_price=entry_price, stop_loss=stop_loss,
                take_profit=take_profit, setup=setup
            )
            if not _sentinel_ok:
                logger.warning(f"⚠️ [Fix #13 SENTINELĂ] {symbol} E{entry_number} SKIP (nu șters): {_sentinel_reason}")
                # V19.10: NU mai ștergem setup-ul din monitoring — skip silențios, retry la ciclul următor.
                # Setup-ul rămâne activ; radarul va recalcula la 30s; condițiile se pot schimba.
                return False
            logger.success(f"✅ [Fix #13 SENTINELĂ] {symbol}: {_sentinel_reason}")
            # ━━━ END SENTINELĂ ━━━

            # ━━━ V10.4: STRATEGY TAGGING — D1_{REVERSAL|CONTINUITY}_4H_SYNC ━━━
            # Format: D1_REVERSAL_4H_SYNC_SNIPER_E1 or D1_CONTINUITY_4H_SYNC_PB50_E2
            # Fix #10: Normalize 'CONTINUATION' → 'CONTINUITY' pentru consistență
            strategy_type = setup.get('strategy_type', 'unknown').upper()
            if strategy_type in ('CONTINUATION', 'CONTINUITY'):
                strategy_type = 'CONTINUITY'
            entry_mode = setup.get('pullback_status', setup.get('entry_reason', 'STANDARD')).upper()
            
            # Simplify entry_mode tag
            if 'SNIPER' in entry_mode or '1H' in entry_mode:
                mode_tag = 'SNIPER'
            elif 'HIGH_CONF' in entry_mode or '4H' in entry_mode:
                mode_tag = 'HC4H'
            elif 'MOMENTUM' in entry_mode:
                mode_tag = 'MOM'
            elif 'PULLBACK' in entry_mode or 'FIBO' in entry_mode:
                mode_tag = 'PB50'
            elif 'IMMEDIATE' in entry_mode:
                mode_tag = 'IMM'
            elif 'TIMEOUT' in entry_mode:
                mode_tag = 'TMO'
            else:
                mode_tag = 'STD'
            
            strategy_comment = f"D1_{strategy_type}_4H_SYNC_{mode_tag}_E{entry_number}"
            # ✅ V10.5: Validate strategy_type is a known tag — prevent empty/unknown
            if strategy_type not in ('REVERSAL', 'CONTINUITY', 'UNKNOWN'):
                logger.warning(f"   ⚠️ V10.5 STRATEGY TAG: Unexpected type '{strategy_type}' — check setup['strategy_type']")
            logger.info(f"   🏷️ V10.5 STRATEGY TAG: {strategy_comment}")
            logger.info(f"   📌 D1 Bias: {strategy_type} | 4H Sync: CONFIRMED | Entry: E{entry_number} | Mode: {mode_tag}")
            # ━━━ END V10.4 TAGGING ━━━
            
            # ━━━ V11.2: SPREAD GUARD (Block Execution if spread > max) ━━━
            spread_block = self._check_spread_guard(symbol)
            if spread_block:
                logger.warning(f"   🛡️ V11.2 SPREAD GUARD: {spread_block}")
                logger.warning(f"   ⏸️ Execuție BLOCATĂ pentru {symbol} — retry la următorul ciclu")
                setup['last_rejection_ts'] = time.time()
                return False
            # ━━━ END SPREAD GUARD ━━━

            # ━━━ V39.5: LIQUIDITY SNIPER — block NEW entries 15 min pre-news ━━━
            news_block = self._check_news_guard(symbol)
            if news_block:
                logger.warning(f"   ⏸️ V39.5 LIQUIDITY SNIPER: {news_block}")
                setup['last_rejection_ts'] = time.time()
                return False
            # ━━━ END LIQUIDITY SNIPER ENTRY GUARD ━━━

            # ━━━ V12.0: LIVE SWAP FETCH — Transparență financiară la execuție ━━━
            swap_info = {}
            try:
                swap_raw = self.ctrader_client.get_swap_info(symbol)
                if swap_raw.get('success'):
                    swap_val = swap_raw['swap_short'] if direction == 'sell' else swap_raw['swap_long']
                    swap_label = "✅ CREDIT" if swap_val > 0 else "⚠️ DEBIT"
                    swap_info = {
                        'value': swap_val,
                        'label': swap_label,
                        'triple_day': swap_raw.get('swap_triple_day', '?'),
                    }
                    logger.info(f"   💱 SWAP {symbol} ({'SHORT' if direction == 'sell' else 'LONG'}): {swap_label} {swap_val:+.2f} pips/day")
                else:
                    logger.debug(f"   💱 Swap data unavailable for {symbol}: {swap_raw.get('error')}")
            except Exception as sw_err:
                logger.debug(f"   💱 Swap fetch skipped: {sw_err}")
            # ━━━ END LIVE SWAP FETCH ━━━

            logger.info(f"\n🚀 EXECUTING ENTRY {entry_number}: {symbol} {direction.upper()}")
            logger.info(f"   Entry: {entry_price}")
            logger.info(f"   SL: {stop_loss}")
            logger.info(f"   TP: {take_profit}")
            logger.info(f"   Lot Size: {position_size}")
            logger.info(f"   🏷️ Tag: {strategy_comment}")
            
            # Execute via cTrader executor
            success = self.executor.execute_trade(
                symbol=symbol,
                direction=direction.upper(),
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                lot_size=position_size,
                comment=strategy_comment,
                status='READY',  # Always READY when executing
                risk_override_percent=risk_override_percent  # V14.1: None for E1, 7.5% for E2
            )
            
            if not success:
                # V10.2 FIX: Do NOT enter Deep Sleep on rejection
                # Rejections mean no trade was placed → no reason to pause system
                # Deep Sleep should only activate from ACTUAL realized losses
                if hasattr(self.executor, 'risk_manager') and self.executor.risk_manager:
                    self._track_rejection(f"Entry {entry_number} rejected for {symbol}")
                    logger.warning(f"⚠️ {symbol} Entry {entry_number} rejected by Risk Manager — continuing monitoring")
                
                logger.error(f"❌ Failed to write signal for Entry {entry_number}")
                # ✅ V10.9 ANTI-LOOP FIX: Store rejection timestamp so we don't spam-retry every 5s
                # Caller (_process_monitoring_setups) will use setup['last_rejection_ts'] to enforce cooldown
                setup['last_rejection_ts'] = time.time()
                logger.warning(f"   🔕 V10.9: {symbol} rejection timestamped — 5 min cooldown active")
                return False
            
            if success:
                logger.success(f"✅ Entry {entry_number} signal written to signals.json!")
                logger.info(f"   cBot will execute automatically")
                
                # 🔕 Telegram notification intentionally disabled here — ARMAGEDDON from
                # position_monitor.py handles the notification when trade appears in cTrader.
                # Avoids duplicate messages on Telegram.
                logger.success(f"📱 Trade written to signals.json — ARMAGEDDON via position_monitor")
                
                return True
        
        except Exception as e:
            logger.error(f"❌ Error executing Entry {entry_number}: {e}")
            return False
    
    def run(self):
        """Main monitoring loop"""
        logger.info("\n" + "="*60)
        logger.info("🎯 Setup Executor Monitor Starting...")
        logger.info(f"⏱️  Check Interval: {self.check_interval}s")
        logger.info(f"📂 Monitoring File: {self.monitoring_file}")
        logger.info("="*60 + "\n")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                logger.debug(f"\n🔄 Check #{iteration} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Fix #11: CLEAN SLATE — cleanup la fiecare ciclu (nu la 100)
                # Setup-urile stale blochează sloturi — trebuie șterse imediat ce devin invalide
                self._cleanup_monitoring_setups()

                # V39.5: BE protect open ITM positions at T-2 min before news
                self._liquidity_sniper_be_protect_open_positions()

                self._process_monitoring_setups()
                
                # Wait before next check
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("\n⚠️  Stopping Setup Executor Monitor...")
            sys.exit(0)
        except Exception as e:
            logger.error(f"❌ Fatal error in monitor loop: {e}")
            sys.exit(1)


def main():
    """Entry point"""
    import argparse
    import atexit
    
    parser = argparse.ArgumentParser(description='Setup Executor Monitor')
    parser.add_argument('--interval', type=int, default=30,
                        help='Check interval in seconds (default: 30)')
    parser.add_argument('--loop', action='store_true',
                        help='Run in continuous loop mode')
    
    args = parser.parse_args()
    
    # 🔒 PID LOCK - Prevent duplicate instances
    lock_file = Path("process_setup_executor.lock")
    if not acquire_pid_lock(lock_file):
        logger.error("🚫 DUPLICATE INSTANCE DETECTED - Exiting to prevent double notifications")
        sys.exit(1)
    
    # Register cleanup on exit
    atexit.register(release_pid_lock, lock_file)
    
    monitor = SetupExecutorMonitor(check_interval=args.interval)
    
    if args.loop:
        monitor.run()
    else:
        # Single check mode
        logger.info("🔍 Single check mode...")
        monitor._liquidity_sniper_be_protect_open_positions()
        monitor._process_monitoring_setups()
        logger.info("✅ Check complete!")


if __name__ == "__main__":
    main()
