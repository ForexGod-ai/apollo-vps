"""
Setup Executor Monitor — V31/V36 Radar-only execution layer

Arhitectura 3 straturi (Apollo / Glitch in Matrix):
1. daily_scanner.py + smc_detector.scan_for_setup() → monitoring_setups.json + Telegram
2. multi_tf_radar.py V36.5 → scan H4/H1 Always-On, EXECUTE_NOW, h4_structure_locked
3. setup_executor_monitor.py (acest script) → signals.json → cTrader VPS port 8010

V31.0+ EXECUTOR BLIND:
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
from pip_utils import get_pip_size, get_max_sl_pips, MIN_SL_PIPS, sl_pips_between, liquidity_already_swept
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

    # V42.2: status terminal din JSON fresh — Radar/position_monitor au autoritate absolută
    _FRESH_TERMINAL_STATUSES = frozenset({
        'INVALIDATED', 'CLOSED', 'COMPLETED_WITHOUT_ENTRY',
    })

    _DEFAULT_MULTI_ENTRY_PLAN = ('1H', '4H')

    @classmethod
    def _multi_entry_plan(cls, setup: dict) -> list:
        return list(setup.get('multi_entry_plan') or cls._DEFAULT_MULTI_ENTRY_PLAN)

    @classmethod
    def _apply_multi_entry_post_fill(cls, setup: dict, trigger_tf: str) -> None:
        """V42.2: first fill → PARTIAL_OPEN; all planned TFs filled → TRADE_OPEN."""
        symbol = setup.get('symbol', '?')
        plan = cls._multi_entry_plan(setup)
        tf = (trigger_tf or setup.get('execute_now_trigger_tf') or '1H').upper()
        filled = [x.upper() for x in (setup.get('entries_filled_tfs') or [])]
        if tf not in filled:
            filled.append(tf)
        setup['entries_filled_tfs'] = filled
        setup.setdefault('multi_entry_plan', plan)

        if not setup.get('entry1_filled'):
            setup['entry1_filled'] = True
            setup['entry1_trigger_tf'] = tf
        elif tf != (setup.get('entry1_trigger_tf') or '').upper():
            setup['entry2_filled'] = True
            setup['entry2_trigger_tf'] = tf

        pending = [p for p in plan if p.upper() not in filled]
        setup['multi_entry_pending'] = pending

        if not pending:
            setup['status'] = 'TRADE_OPEN'
            logger.success(
                f"[V42.2 MULTI-ENTRY] {symbol}: all planned entries filled → TRADE_OPEN"
            )
        else:
            setup['status'] = 'PARTIAL_OPEN'
            logger.success(
                f"[V42.2 MULTI-ENTRY] {symbol} moved to PARTIAL_OPEN "
                f"(filled={filled}, pending={pending})"
            )

    @classmethod
    def _infer_multi_entry_pending(cls, setup: dict) -> list:
        pending = setup.get('multi_entry_pending')
        if pending is not None:
            return list(pending)
        plan = cls._multi_entry_plan(setup)
        filled = [x.upper() for x in (setup.get('entries_filled_tfs') or [])]
        if setup.get('entry1_filled') and not filled:
            filled = [(setup.get('entry1_trigger_tf') or '1H').upper()]
        return [p for p in plan if p.upper() not in filled]

    @classmethod
    def _executor_can_consume_execute_now(cls, processed: dict) -> bool:
        """Whether executor RAM state still accepts a fresh EXECUTE_NOW from radar."""
        if not processed.get('entry1_filled'):
            return True
        if processed.get('status') != 'PARTIAL_OPEN':
            return False
        return bool(cls._infer_multi_entry_pending(processed))

    @classmethod
    def _can_execute_execute_now(cls, setup: dict) -> bool:
        if setup.get('EXECUTE_NOW') is not True:
            return False
        return cls._executor_can_consume_execute_now(setup) and (
            not setup.get('entry1_filled')
            or (
                (setup.get('execute_now_trigger_tf') or '4H').upper()
                not in [x.upper() for x in (setup.get('entries_filled_tfs') or [])]
            )
        )

    @staticmethod
    def _v423_norm_daily_bias(direction: str):
        """V42.3: buy/sell → bullish/bearish pentru comparatie cu radar_*_choch_direction."""
        d = (direction or '').lower()
        if d in ('buy', 'long', 'bullish'):
            return 'bullish'
        if d in ('sell', 'short', 'bearish'):
            return 'bearish'
        return None

    @classmethod
    def _v423_structural_sync_ok(cls, setup: dict) -> tuple:
        """
        V42.3: Scut absolut D1 = LTF — EXECUTE_NOW doar cu CHoCH 4H/1H aliniat cu Daily.
        TRADE_OPEN: nu blocăm (poziție deja deschisă).
        """
        if setup.get('status') == 'TRADE_OPEN':
            return True, ''
        macro = cls._v423_norm_daily_bias(setup.get('direction', ''))
        if not macro:
            return False, 'invalid D1 direction'

        h4_dir = setup.get('radar_4h_choch_direction')
        h1_dir = setup.get('radar_1h_choch_direction')
        trigger = (setup.get('execute_now_trigger_tf') or '1H').upper()

        if setup.get('radar_4h_choch_detected') and h4_dir and h4_dir != macro:
            return False, h4_dir
        if setup.get('radar_1h_choch_detected') and h1_dir and h1_dir != macro:
            return False, h1_dir

        if trigger == '4H':
            if not (setup.get('radar_4h_choch_detected') and h4_dir == macro):
                return False, h4_dir or 'missing'
        elif not (setup.get('radar_1h_choch_detected') and h1_dir == macro):
            return False, h1_dir or 'missing'

        return True, ''

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

        V42.2: Daca fresh are status terminal structural (INVALIDATED/CLOSED/CWE),
        fresh castiga disputa — executorul nu re-salveaza setup-uri invalidate live.
        """
        fresh_status = fresh.get('status', '')
        if fresh_status in cls._FRESH_TERMINAL_STATUSES:
            merged = {**processed, **fresh}
            sym = fresh.get('symbol', '?')
            logger.info(
                f"[V42.2 MERGE] {sym}: fresh terminal status {fresh_status} "
                f"wins over executor RAM"
            )
            return merged

        merged = {**fresh, **processed}
        if fresh.get('EXECUTE_NOW') is True and cls._executor_can_consume_execute_now(processed):
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

        # V40.9/V41: o singura alerta Telegram per blocare EXECUTE_NOW (persista pe disc)
        self._execute_now_block_alert_keys: set = set()
        self._execute_now_block_alert_file = Path("data/execute_now_block_alerts.json")
        self._load_execute_now_block_alert_state()
        
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

    def _load_execute_now_block_alert_state(self):
        """V41: dedup alerte EXECUTE NOW BLOCAT — supravietuieste restart + procese paralele."""
        try:
            if not self._execute_now_block_alert_file.exists():
                return
            with open(self._execute_now_block_alert_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                for key, ts in data.items():
                    try:
                        sent = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                        if sent >= cutoff:
                            self._execute_now_block_alert_keys.add(key)
                    except Exception:
                        self._execute_now_block_alert_keys.add(key)
            elif isinstance(data, list):
                self._execute_now_block_alert_keys.update(data)
        except Exception as e:
            logger.debug(f"V41 block alert state load skipped: {e}")

    def _save_execute_now_block_alert_state(self):
        try:
            self._execute_now_block_alert_file.parent.mkdir(parents=True, exist_ok=True)
            now = datetime.now(timezone.utc).isoformat()
            payload = {k: now for k in sorted(self._execute_now_block_alert_keys)}
            with open(self._execute_now_block_alert_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logger.debug(f"V41 block alert state save skipped: {e}")

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
          3. Câmpuri obligatorii lipsă: symbol / direction
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
                st = s.get('status', '')
                if st in dead_statuses:
                    reason_remove = f"status mort={st}"
                    if st == 'CLOSED':
                        logger.info(
                            f"[V42.2 EVICTION] Purged {symbol} from JSON due to CLOSED status"
                        )

                # V42.2: PARTIAL_OPEN / TRADE_OPEN — doar broker confirmă închiderea (→ CLOSED)
                if not reason_remove and st in ('PARTIAL_OPEN', 'TRADE_OPEN'):
                    active_setups.append(s)
                    continue

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
        Process all setups in monitoring_setups.json — V31+ Radar-only execution.

        V9.3 DEEP SLEEP: If active, skip ALL processing (zero HTTP calls).

        V42.4 ACTIVE FLOW:
        1. Load setup from monitoring_setups.json
        2. EXECUTE_NOW=True → execuție structurală live (bloc V19.8)
        3. status=READY → execuție forțată Entry 1 (legacy owner flag)
        4. Altfel → așteptare pasivă (Radar setează EXECUTE_NOW)
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
                    'WAITING_D1_PULLBACK', 'WAITING_4H_CHOCH', 'WAITING_1H_CHOCH',
                    'PARTIAL_OPEN',  # V42.2: second layer (4H) while 1H position open
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
                        _scale_in_ok = (
                            setup.get('status') == 'PARTIAL_OPEN'
                            and setup.get('multi_entry_pending')
                            and setup.get('EXECUTE_NOW') is True
                        )
                        if _existing and not _scale_in_ok:
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
                    if self._can_execute_execute_now(setup):
                        # ── V42.3: Scut absolut sincron structural D1 = 4H = 1H ───────────────
                        if setup.get('status') != 'TRADE_OPEN':
                            _sync_ok, _ltf_mismatch = self._v423_structural_sync_ok(setup)
                            if not _sync_ok:
                                logger.warning(
                                    f"[⚠️ V42.3 ALINIERE] Execuție blocată pentru {symbol}. "
                                    f"Lipsă sincron (D1: {setup.get('direction')} vs LTF: "
                                    f"{setup.get('radar_4h_choch_direction')})"
                                )
                                setups[i]['EXECUTE_NOW'] = False
                                setups[i].pop('execute_now_trigger_tf', None)
                                setups[i]['v42_3_alignment_block'] = _ltf_mismatch
                                setups[i]['v42_3_alignment_block_at'] = (
                                    datetime.now(timezone.utc).isoformat()
                                )
                                updated = True
                                continue

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

                        # ── V40.8: SL/TP — REGULA FIXA: SL=1H/4H structural mic, TP=D1 structural ──
                        def _float_price(val):
                            try:
                                return float(val) if val not in (None, 0, '0', '') else None
                            except (TypeError, ValueError):
                                return None

                        _df_4h_en = self._get_cached_data(symbol, "H4", 225)
                        _df_d1_en = self._get_cached_data(symbol, "D1", 100)

                        _sl = None
                        _tp = None

                        _sl = self._resolve_execute_now_sl(
                            setup, symbol, _en_direction, _en_entry, _df_4h_en, _pip_size_en
                        )

                        _tp = self._resolve_execute_now_tp(
                            setup, symbol, _en_direction, _en_entry,
                            _df_4h_en, _df_d1_en, _pip_size_en, _sl,
                        )

                        # Validare direcție SL/TP
                        if _en_direction == 'buy' and _sl and _sl >= _en_entry:
                            _sl = None
                            logger.warning(f"[V19.8 DIR GUARD] {symbol} BUY: SL deasupra entry — invalid")
                        if _en_direction == 'sell' and _sl and _sl <= _en_entry:
                            _sl = None
                            logger.warning(f"[V19.8 DIR GUARD] {symbol} SELL: SL sub entry — invalid")
                        if _en_direction == 'buy' and _tp and _tp <= _en_entry:
                            _tp = None
                            logger.warning(f"[V19.8 DIR GUARD] {symbol} BUY: TP sub entry — invalid")
                        if _en_direction == 'sell' and _tp and _tp >= _en_entry:
                            _tp = None
                            logger.warning(f"[V19.8 DIR GUARD] {symbol} SELL: TP deasupra entry — invalid")

                        _sl_pips_en = sl_pips_between(symbol, _en_entry, _sl) if _sl else 0.0
                        if not _sl or _sl_pips_en < MIN_SL_PIPS:
                            _blk = (
                                f'V40.8: SL 1H/4H indisponibil sau {_sl_pips_en:.1f}p < min {MIN_SL_PIPS}p'
                            )
                            logger.critical(f"🚨 [V40.8 MIN SL] {symbol}: {_blk}")
                            self._track_rejection(f"V40.8 min SL {symbol}: {_sl_pips_en:.1f}p")
                            setups[i].pop('EXECUTE_NOW', None)
                            setups[i]['last_rejection_reason'] = _blk
                            setups[i]['execute_now_blocked_at'] = datetime.now(timezone.utc).isoformat()
                            self._notify_execute_now_blocked(
                                symbol, _en_direction, _blk, setup=setups[i],
                            )
                            updated = True
                            continue

                        if not _tp:
                            _blk = 'V40.8: TP D1 structural indisponibil (fara fallback ATR/2xSL)'
                            logger.critical(f"🚨 [V40.8 NO TP D1] {symbol}: {_blk}")
                            self._track_rejection(f"V40.8 no D1 TP {symbol}")
                            setups[i].pop('EXECUTE_NOW', None)
                            setups[i]['last_rejection_reason'] = _blk
                            setups[i]['execute_now_blocked_at'] = datetime.now(timezone.utc).isoformat()
                            self._notify_execute_now_blocked(
                                symbol, _en_direction, _blk, setup=setups[i],
                            )
                            updated = True
                            continue

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
                            _blk = 'V40.7: SL structural indisponibil (Radar/FVG/TF mic)'
                            self._track_rejection(f"EXECUTE_NOW no SL available for {symbol}")
                            setups[i].pop('EXECUTE_NOW', None)
                            setups[i]['last_rejection_reason'] = _blk
                            self._notify_execute_now_blocked(
                                symbol, _en_direction, _blk, setup=setups[i],
                            )
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
                            setups[i]['execute_now_blocked_at'] = datetime.now(timezone.utc).isoformat()
                            self._notify_execute_now_blocked(
                                symbol, _en_direction, _sentinel_reason_en, setup=setups[i],
                            )
                            updated = True
                            continue

                        # ── STEP 7: Execuție în cTrader ───────────────────────────────────────────────
                        _trigger_tf = (setup.get('execute_now_trigger_tf') or '1H').upper()
                        _entry_num = 2 if setup.get('entry1_filled') else 1
                        _en_comment = (
                            f"D1_EXECUTE_NOW_V42.2_{_en_direction.upper()}_{_trigger_tf}_E{_entry_num}"
                        )
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
                            if _entry_num == 1:
                                setups[i]['entry1_price'] = _en_entry
                                setups[i]['entry1_sl'] = _sl
                                setups[i]['entry1_tp'] = _tp
                                setups[i]['entry1_lots'] = _lot_size_en
                                setups[i]['entry1_time'] = datetime.now(timezone.utc).isoformat()
                            else:
                                setups[i]['entry2_price'] = _en_entry
                                setups[i]['entry2_sl'] = _sl
                                setups[i]['entry2_tp'] = _tp
                                setups[i]['entry2_lots'] = _lot_size_en
                                setups[i]['entry2_time'] = datetime.now(timezone.utc).isoformat()
                            self._apply_multi_entry_post_fill(setups[i], _trigger_tf)
                            setups[i].pop('EXECUTE_NOW', None)
                            setups[i].pop('execute_now_trigger_tf', None)
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
                            _block_reason = 'Risk Manager: EXECUTE_NOW rejected'
                            try:
                                _rej = getattr(self.executor, 'rejected_trades', {}).get(symbol, {})
                                if _rej.get('reason'):
                                    _block_reason = str(_rej['reason'])
                            except Exception:
                                pass
                            logger.error(f"❌ [V19.8 EXECUTE_NOW] {symbol} execuție respinsă: {_block_reason}")
                            self._track_rejection(f"EXECUTE_NOW loss limit rejected for {symbol}")
                            setups[i].pop('EXECUTE_NOW', None)
                            setups[i]['last_rejection_time'] = datetime.now(timezone.utc).isoformat()
                            setups[i]['last_rejection_reason'] = _block_reason
                            setups[i]['execute_now_blocked_at'] = datetime.now(timezone.utc).isoformat()
                            self._notify_execute_now_blocked(
                                symbol, _en_direction, _block_reason, setup=setups[i],
                            )
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

                    # Check if Entry1 already filled
                    entry1_filled = setup.get('entry1_filled', False)
                    
                    # V4.3 FIX-016: Force execute if status is READY
                    if status == 'READY' and not entry1_filled:
                        # 🛡️ V7.1 DUPLICATE GUARD: Check broker before execution
                        if self._symbol_already_at_broker(symbol):
                            logger.warning(f"🛡️ SKIP {symbol}: Already has open position at broker (duplicate guard)")
                            setups[i]['force_executed'] = True
                            setups[i]['skip_reason'] = 'duplicate_guard_broker_position_exists'
                            self._apply_multi_entry_post_fill(
                                setups[i], setup.get('execute_now_trigger_tf') or '1H'
                            )
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
                        forced_strategy = setup.get('strategy_type', 'reversal').upper()
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
                            setups[i]['entry1_price'] = setup['entry_price']
                            setups[i]['entry1_time'] = datetime.now(timezone.utc).isoformat()
                            self._apply_multi_entry_post_fill(setups[i], '1H')
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
                        # V42.4: Blind executor — asteptam EXECUTE_NOW de la Radar (legacy V3.x eliminat)
                        logger.debug(
                            f"[V31.0] {symbol}: entry1 pending — asteptam EXECUTE_NOW de la Radar"
                        )
                    
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
        nearest: bool = False,
    ):
        """
        SL structural pe TF (4H sau 1H) — ultimul pivot valid in interval sniper.
        V42.6: nearest=False (default) = ultimul swing 4H/1H in [30p, max_pips].
        nearest=True = cel mai apropiat de entry (legacy sniper strict).
        """
        if df_4h is None or df_4h.empty or not entry:
            return None
        sl_buffer = pip_size * 2
        min_dist = min_sl_pips * pip_size
        max_dist = get_max_sl_pips(symbol) * pip_size
        min_dist = min(min_sl_pips * pip_size, max_dist * 0.95)
        try:
            _atr_4h = float((df_4h['high'] - df_4h['low']).rolling(14).mean().iloc[-1])
            min_dist = max(min_dist, min(_atr_4h * 0.3, max_dist * 0.85))
        except Exception:
            pass
        min_dist = min(min_dist, max_dist * 0.95)

        direction = direction.lower()
        if direction == 'buy':
            swings = self.smc_detector.detect_swing_lows(df_4h)
            candidates = [
                s for s in swings
                if float(df_4h['low'].iloc[s.index]) < entry
                and min_dist <= (entry - float(df_4h['low'].iloc[s.index])) <= max_dist
            ]
            if candidates:
                if nearest:
                    best = min(
                        candidates,
                        key=lambda s: entry - float(df_4h['low'].iloc[s.index]),
                    )
                else:
                    best = sorted(candidates, key=lambda s: s.index, reverse=True)[0]
                return float(df_4h['low'].iloc[best.index]) - sl_buffer
            if not nearest:
                window_low = float(df_4h['low'].iloc[-40:].min())
                if entry - window_low >= min_dist:
                    return window_low - sl_buffer
        else:
            swings = self.smc_detector.detect_swing_highs(df_4h)
            candidates = [
                s for s in swings
                if float(df_4h['high'].iloc[s.index]) > entry
                and min_dist <= (float(df_4h['high'].iloc[s.index]) - entry) <= max_dist
            ]
            if candidates:
                if nearest:
                    best = min(
                        candidates,
                        key=lambda s: float(df_4h['high'].iloc[s.index]) - entry,
                    )
                else:
                    best = sorted(candidates, key=lambda s: s.index, reverse=True)[0]
                return float(df_4h['high'].iloc[best.index]) + sl_buffer
            if not nearest:
                window_high = float(df_4h['high'].iloc[-40:].max())
                if window_high - entry >= min_dist:
                    return window_high + sl_buffer
        return None

    def _sl_valid_for_execute(
        self,
        symbol: str,
        direction: str,
        entry: float,
        stop_loss: float,
    ) -> bool:
        """V40.7: SL valid pentru EXECUTE_NOW (directie + min/max pips)."""
        if not entry or not stop_loss:
            return False
        d = str(direction).lower()
        if d == 'buy' and stop_loss >= entry:
            return False
        if d == 'sell' and stop_loss <= entry:
            return False
        sl_p = sl_pips_between(symbol, entry, stop_loss)
        return MIN_SL_PIPS <= sl_p <= get_max_sl_pips(symbol)

    def _resolve_execute_now_sl(
        self,
        setup: dict,
        symbol: str,
        direction: str,
        entry: float,
        df_4h,
        pip_size: float,
    ):
        """
        V40.8 REGULA SL: ultimul punct structural pe 1H + 4H (in cap sniper) — tightest valid.
        Radar h4_sl_price intra in competitie daca e valid.
        """
        def _f(v):
            try:
                return float(v) if v not in (None, 0, '0', '') else None
            except (TypeError, ValueError):
                return None

        sl_candidates = []

        radar_sl = _f(setup.get('h4_sl_price')) or _f(setup.get('stop_loss'))
        if self._sl_valid_for_execute(symbol, direction, entry, radar_sl):
            sl_candidates.append(
                (radar_sl, 'RADAR', sl_pips_between(symbol, entry, radar_sl))
            )

        df_1h = self._get_cached_data(symbol, '1H', 225)
        for tf_label, df in (('1H', df_1h), ('4H', df_4h)):
            if df is None or df.empty:
                continue
            sl = self._calc_structural_sl_4h(
                symbol, direction, entry, df, pip_size, MIN_SL_PIPS, nearest=False
            )
            if self._sl_valid_for_execute(symbol, direction, entry, sl):
                sl_candidates.append(
                    (sl, tf_label, sl_pips_between(symbol, entry, sl))
                )

        if not sl_candidates:
            return None

        best_sl, best_tf, best_pips = min(sl_candidates, key=lambda x: x[2])
        logger.info(
            f"📐 [V40.8 SL {best_tf}] {symbol}: SL={best_sl:.5f} ({best_pips:.1f}p) "
            f"— tightest of {[f'{t}:{p:.0f}p' for _, t, p in sl_candidates]}"
        )
        return best_sl

    def _resolve_execute_now_tp(
        self,
        setup: dict,
        symbol: str,
        direction: str,
        entry: float,
        df_4h,
        df_d1,
        pip_size: float,
        stop_loss: float,
    ):
        """
        V40.8 REGULA TP: DOAR structura D1 — fara ATR / 2xSL inventat.
        1) daily_tp_price din scan (D1 structural)
        2) recalc live _calc_structural_tp_d1
        """
        def _f(v):
            try:
                return float(v) if v not in (None, 0, '0', '') else None
            except (TypeError, ValueError):
                return None

        d = str(direction).lower()
        tp_json = _f(setup.get('daily_tp_price') or setup.get('daily_target_price'))
        if tp_json:
            if d == 'buy' and tp_json > entry:
                logger.info(f"📐 [V40.8 TP D1 SCAN] {symbol}: TP={tp_json:.5f}")
                return tp_json
            if d == 'sell' and tp_json < entry:
                logger.info(f"📐 [V40.8 TP D1 SCAN] {symbol}: TP={tp_json:.5f}")
                return tp_json

        # V40.9: pivot structural D1 din scanner (Gate1)
        swing_key = 'daily_swing_low' if d == 'sell' else 'daily_swing_high'
        tp_swing = _f(setup.get(swing_key))
        if tp_swing:
            if d == 'buy' and tp_swing > entry:
                logger.info(f"📐 [V40.9 TP D1 SWING] {symbol}: TP={tp_swing:.5f} ({swing_key})")
                return tp_swing
            if d == 'sell' and tp_swing < entry:
                logger.info(f"📐 [V40.9 TP D1 SWING] {symbol}: TP={tp_swing:.5f} ({swing_key})")
                return tp_swing

        if df_d1 is not None and not df_d1.empty:
            tp_live = self._calc_structural_tp_d1(
                direction, entry, df_4h, df_d1, pip_size,
                symbol=symbol, stop_loss=stop_loss, execute_now=True,
            )
            if tp_live:
                if d == 'buy' and tp_live > entry:
                    logger.info(f"📐 [V40.8 TP D1 LIVE] {symbol}: TP={tp_live:.5f}")
                    return tp_live
                if d == 'sell' and tp_live < entry:
                    logger.info(f"📐 [V40.8 TP D1 LIVE] {symbol}: TP={tp_live:.5f}")
                    return tp_live

            tp_last = self._calc_last_d1_structure_tp(
                direction, entry, df_d1, pip_size, stop_loss=stop_loss, symbol=symbol,
            )
            if tp_last:
                if d == 'buy' and tp_last > entry:
                    logger.info(f"📐 [V40.9 TP D1 LAST] {symbol}: TP={tp_last:.5f}")
                    return tp_last
                if d == 'sell' and tp_last < entry:
                    logger.info(f"📐 [V40.9 TP D1 LAST] {symbol}: TP={tp_last:.5f}")
                    return tp_last

        return None

    def _calc_last_d1_structure_tp(
        self,
        direction: str,
        entry: float,
        df_d1,
        pip_size: float,
        stop_loss: float = None,
        symbol: str = '',
    ):
        """
        V40.9: Ultimul punct structural D1 — regula utilizator.
        Fara floor 1x ATR (BTC: TP valid la ~1500p chiar daca ATR D1 > distanta).
        """
        if df_d1 is None or df_d1.empty or not entry:
            return None
        try:
            entry_f = float(entry)
            d = str(direction).lower()
            if stop_loss:
                min_dist = abs(entry_f - float(stop_loss)) * 2.0
            else:
                min_dist = MIN_SL_PIPS * pip_size

            if d == 'buy':
                swings = self.smc_detector.detect_swing_highs(df_d1)
                targets = [
                    s for s in swings
                    if s.price > entry_f and (s.price - entry_f) >= min_dist
                ]
                if targets:
                    nearest = min(targets, key=lambda s: s.price)
                    return float(df_d1['high'].iloc[nearest.index])
            else:
                swings = self.smc_detector.detect_swing_lows(df_d1)
                targets = [
                    s for s in swings
                    if s.price < entry_f and (entry_f - s.price) >= min_dist
                ]
                if targets:
                    nearest = max(targets, key=lambda s: s.price)
                    return float(df_d1['low'].iloc[nearest.index])
        except Exception as exc:
            logger.warning(f"[V40.9] last D1 structure TP failed ({symbol}): {exc}")
        return None

    def _notify_execute_now_blocked(
        self,
        symbol: str,
        direction: str,
        reason: str,
        setup: dict = None,
    ) -> None:
        """V41.1: delegare dedup la telegram_notifier (file lock — anti 15 procese paralele)."""
        try:
            self.telegram.send_execute_now_blocked_alert(symbol, direction, reason)
        except Exception as exc:
            logger.warning(f"[V40.7] blocked alert failed: {exc}")

    def _calc_structural_tp_d1(
        self,
        direction: str,
        entry: float,
        df_4h,
        df_d1,
        pip_size: float,
        symbol: str = '',
        stop_loss: float = None,
        execute_now: bool = False,
    ):
        """
        TP = primul swing D1 lichiditate NEATINS recent in directia trade-ului.
        V37.7: exclude swing-uri deja sweep-uite (ex. BTC low luat → pullback sus).
        V40.9 execute_now: min dist = 2x SL (RR), fara floor 1x ATR care exclude TP BTC valid.
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
            _sweep_tol = pip_size * 10 if pip_size else 0.0
            _sweep_lookback = 25 if any(x in symbol.upper() for x in ['BTC', 'ETH']) else 15

            if execute_now:
                _sl_dist = abs(entry - float(stop_loss)) if stop_loss else (MIN_SL_PIPS * pip_size)
                _min_tp_dist = max(_sl_dist * 2.0, MIN_SL_PIPS * pip_size)
                _max_tp_dist = _atr_d1 * 50.0 if _atr_d1 > 0 else float('inf')
            else:
                _min_tp_dist = _atr_d1 * 1.0
                _max_tp_dist = _atr_d1 * 8.0
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

        # ── Guard 2: SL cap per instrument (V40.6 — BTC structural OK, forex sniper 100p) ──
        _max_sl = get_max_sl_pips(symbol)
        if sl_pips > _max_sl:
            return False, (
                f"Guard#2 SL={sl_pips:.1f}p > {_max_sl:.0f}p max for {symbol} (whale stop)"
            )

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

        # pip_value_per_lot — aliniat cu unified_risk_manager (BTC=1.0, JPY=8.33, FX=10)
        sym_up = symbol.upper()
        if any(x in sym_up for x in ['BTC', 'ETH', 'LTC', 'XRP', 'ADA', 'DOGE']):
            pip_value_per_lot = 1.0
        elif 'JPY' in sym_up:
            pip_value_per_lot = 8.33
        else:
            pip_value_per_lot = 10.0
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
            strategy_type = setup.get('strategy_type', 'reversal').upper()
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
    logger.success(
        "[V42.4 CLEANUP] Successfully purged legacy branches and unified core system data defaults."
    )
    
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
