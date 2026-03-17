"""
Real-Time Market Monitor cu Spatiotemporal Analysis

Rulează continuu, monitorizează piața în timp real,
actualizează narrativul și alertează când setups become READY
"""

import time
import json
import fcntl
import sys
import atexit
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
import requests
import os
import psutil
from pathlib import Path
from dotenv import load_dotenv

from spatiotemporal_analyzer import SpatioTemporalAnalyzer, MarketNarrative
from smc_detector import SMCDetector, TradeSetup
from ctrader_cbot_client import CTraderCBotClient

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
    str(_LOG_DIR / "realtime_monitor.log"),
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
    level="DEBUG",
    rotation="10 MB",
    retention="7 days",
    compression="zip"
)

# ━━━ V9.1 PID LOCK — Prevents duplicate instances (R9 AUDIT FIX) ━━━
def acquire_pid_lock(lock_file: Path) -> bool:
    """🔒 PID LOCK SINGLETON — Only ONE realtime_monitor instance allowed"""
    try:
        if lock_file.exists():
            with open(lock_file, 'r') as f:
                old_pid = int(f.read().strip())
            if psutil.pid_exists(old_pid):
                try:
                    proc = psutil.Process(old_pid)
                    if 'realtime_monitor' in ' '.join(proc.cmdline()):
                        logger.error(f"❌ Realtime Monitor already running (PID {old_pid})")
                        logger.error("⚠️  Cannot start duplicate instance — exiting")
                        return False
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            logger.warning(f"🔧 Removing stale lock file (PID {old_pid} not running)")
            lock_file.unlink()
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


# Telegram config
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


class RealtimeMonitor:
    """
    Monitor în timp real pentru toate perechile
    """
    
    def __init__(self, symbols: List[str], check_interval_hours: int = 4):
        self.symbols = symbols
        self.check_interval_hours = check_interval_hours
        
        # Tracking pentru fiecare simbol
        self.analyzers: Dict[str, SpatioTemporalAnalyzer] = {}
        self.last_narratives: Dict[str, MarketNarrative] = {}
        self.last_recommendations: Dict[str, str] = {}
        
        # V8.5: STARTUP SILENCE — suppress spam on restart
        self.is_initial_scan = True  # First scan after boot = silent (no individual alerts)
        
        # V8.2: Downgrade spam protection
        self.downgrade_cooldown: Dict[str, datetime] = {}  # symbol → last downgrade time
        self.data_error_counts: Dict[str, int] = {}  # symbol → consecutive data errors
        self.DOWNGRADE_COOLDOWN_HOURS = 24  # Max 1 downgrade alert per symbol per 24h
        self.MAX_DATA_ERRORS_BEFORE_ALERT = 3  # Only alert after 3 consecutive data failures
        
        # ━━━ V9.0: AUTO-EXECUTION ENGINE ━━━
        # SMC Detector for concrete setup discovery (entry/SL/TP)
        self.smc_detector = SMCDetector(
            swing_lookback=5,
            atr_multiplier=1.5
        )
        # Data provider for downloading D1/H4/H1 candles
        self.ctrader_client = CTraderCBotClient()
        # Load pairs config for priority + lookback settings
        self.pairs_config: Dict[str, dict] = {}
        self.scanner_settings: dict = {}
        self._load_pairs_config()
        # Track which symbols already have setups in monitoring_setups.json
        # to avoid spamming duplicate discoveries
        self.discovered_setups: Dict[str, str] = {}  # symbol → setup_time ISO string
        self.monitoring_file = Path("monitoring_setups.json")
        logger.info("🚀 V9.0 AUTO-EXECUTION ENGINE initialized — autonomous setup discovery enabled")

        # ━━━ MISSION 4: VPS H4 CACHE — 30min TTL to avoid hammering broker API ━━━
        # Dict: symbol/timeframe → (dataframe, fetch_timestamp)
        self._data_cache: Dict[str, Tuple[object, datetime]] = {}
        self.H4_CACHE_TTL_MINUTES = 30  # H4 candles: refresh max once per 30min
        self.D1_CACHE_TTL_MINUTES = 60  # D1 candles: refresh max once per 60min
        self.H1_CACHE_TTL_MINUTES = 15  # H1 candles: refresh max once per 15min
        
        # Initialize analyzers
        for symbol in symbols:
            self.analyzers[symbol] = SpatioTemporalAnalyzer(symbol)
            self.last_recommendations[symbol] = 'unknown'
            self.data_error_counts[symbol] = 0
    
    def _wait_for_next_candle_close(self):
        """Wait until next 4H candle closes (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)"""
        now = datetime.now()
        # Calculate next 4H candle close
        current_hour = now.hour
        next_4h_hours = [0, 4, 8, 12, 16, 20]
        
        # Find next 4H boundary
        next_close_hour = None
        for h in next_4h_hours:
            if h > current_hour:
                next_close_hour = h
                break
        
        if next_close_hour is None:
            # Next day 00:00
            next_close = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            next_close = now.replace(hour=next_close_hour, minute=0, second=0, microsecond=0)
        
        wait_seconds = (next_close - now).total_seconds()
        
        logger.info(f"\n⏰ Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"🕐 Next 4H candle closes at: {next_close.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"💤 Waiting {int(wait_seconds)} seconds ({int(wait_seconds/3600):.1f} hours)...")
        
        time.sleep(wait_seconds + 10)  # Wait + 10 seconds buffer for candle to fully close
    
    # ━━━ V9.0: AUTO-EXECUTION ENGINE — Setup Discovery & Monitoring Writer ━━━
    
    def _load_pairs_config(self):
        """Load pairs_config.json for priorities and scanner settings"""
        try:
            with open('pairs_config.json', 'r') as f:
                config = json.load(f)
                for pair in config.get('pairs', []):
                    sym = pair.get('symbol', '')
                    self.pairs_config[sym] = pair
                self.scanner_settings = config.get('scanner_settings', {})
                logger.info(f"📋 Loaded config for {len(self.pairs_config)} pairs")
        except Exception as e:
            logger.error(f"❌ Failed to load pairs_config.json: {e}")
    
    def _get_historical_data(self, symbol: str, timeframe: str, count: int) -> Optional[object]:
        """Download historical data via cTrader cBot client"""
        try:
            df = self.ctrader_client.get_historical_data(symbol, timeframe, count)
            if df is not None and not df.empty:
                # Reset index to match smc_detector expectations
                df = df.reset_index()
                return df
            return None
        except Exception as e:
            logger.error(f"❌ Data download error {symbol}/{timeframe}: {e}")
            return None

    def _get_historical_data_cached(self, symbol: str, timeframe: str, count: int) -> Optional[object]:
        """
        MISSION 4 — VPS-SAFE CACHED FETCH.
        Returns cached data if still fresh, otherwise fetches and caches.
        H4=30min TTL | D1=60min TTL | H1=15min TTL
        """
        ttl_map = {
            "H4": self.H4_CACHE_TTL_MINUTES,
            "D1": self.D1_CACHE_TTL_MINUTES,
            "H1": self.H1_CACHE_TTL_MINUTES,
        }
        ttl_minutes = ttl_map.get(timeframe, 30)
        cache_key = f"{symbol}_{timeframe}"
        now = datetime.now()

        # Check cache validity
        if cache_key in self._data_cache:
            cached_df, cached_at = self._data_cache[cache_key]
            age_minutes = (now - cached_at).total_seconds() / 60
            if age_minutes < ttl_minutes:
                logger.debug(f"💾 CACHE HIT {symbol}/{timeframe} — age {age_minutes:.1f}min (TTL={ttl_minutes}min)")
                return cached_df
            else:
                logger.debug(f"🔄 CACHE EXPIRED {symbol}/{timeframe} — age {age_minutes:.1f}min → refreshing")

        # Cache miss or expired — fetch fresh data
        df = self._get_historical_data(symbol, timeframe, count)
        if df is not None:
            self._data_cache[cache_key] = (df, now)
            logger.debug(f"📥 CACHED {symbol}/{timeframe} at {now.strftime('%H:%M:%S')}")
        return df
    
    # ━━━ AUDIT: PIP_MULTIPLIER — Instrument-aware (XAU/JPY=100, BTC=1, forex=10000) ━━━

    def _get_pip_multiplier(self, symbol: str) -> int:
        """
        Returns pip multiplier for distance calculations and price display.
        XAU (Gold): 100 | JPY pairs: 100 | BTC/Crypto: 1 | All other forex: 10000
        """
        sym = symbol.upper()
        if 'XAU' in sym or 'GOLD' in sym:
            return 100
        if 'JPY' in sym:
            return 100
        if 'BTC' in sym or 'ETH' in sym or 'XRP' in sym or 'LTC' in sym:
            return 1
        return 10000

    def _price_decimals(self, symbol: str) -> int:
        """
        Returns decimal places for price display per instrument.
        XAU/BTC: 2 | JPY: 3 | All other forex: 5
        """
        sym = symbol.upper()
        if 'XAU' in sym or 'GOLD' in sym or 'BTC' in sym:
            return 2
        if 'JPY' in sym:
            return 3
        return 5

    def _fmt_price(self, price: float, symbol: str) -> str:
        """Format price with correct decimal places per instrument."""
        dec = self._price_decimals(symbol)
        return f"{price:.{dec}f}"

    def _discover_setup(self, symbol: str, narrative: MarketNarrative) -> Optional[dict]:
        """
        V9.0 AUTO-EXECUTION: Run full SMC scan to discover concrete TradeSetup.
        Called when SpatioTemporalAnalyzer says 'ready_to_trade' or 'monitor_closely'.
        
        Returns setup dict if found, None otherwise.
        """
        try:
            # Check if we already have this symbol in monitoring_setups.json
            if self._symbol_already_monitoring(symbol):
                logger.debug(f"⏭️ {symbol}: Already in monitoring_setups.json — skipping discovery")
                return None
            
            # Get pair priority from config
            pair_cfg = self.pairs_config.get(symbol, {})
            priority = pair_cfg.get('priority', 3)  # Default priority 3 if not in config
            
            # Download market data (same candle counts as daily_scanner)
            lookback = self.scanner_settings.get('lookback_candles', {})
            daily_count = lookback.get('daily', 100)
            h4_count = lookback.get('h4', 200)
            h1_count = lookback.get('h1', 300)
            
            logger.info(f"🔬 V9.0 DISCOVERY: Scanning {symbol} (priority={priority})...")
            
            df_daily = self._get_historical_data_cached(symbol, "D1", daily_count)
            df_4h = self._get_historical_data_cached(symbol, "H4", h4_count)
            df_1h = self._get_historical_data_cached(symbol, "H1", h1_count)
            
            if df_daily is None or df_4h is None:
                logger.warning(f"⚠️ {symbol}: Cannot download D1/H4 data for setup discovery")
                return None
            
            # Run SMC detector — same as daily_scanner.py
            setup: Optional[TradeSetup] = self.smc_detector.scan_for_setup(
                symbol=symbol,
                df_daily=df_daily,
                df_4h=df_4h,
                priority=priority,
                df_1h=df_1h
            )
            
            if setup is None:
                logger.info(f"   ✓ {symbol}: No valid setup (rejected by V8.0 filters)")
                return None
            
            # Validate critical fields
            if setup.entry_price is None or setup.stop_loss is None or setup.take_profit is None:
                logger.warning(f"⚠️ {symbol}: Setup incomplete (entry/SL/TP is None) — skipping")
                return None
            
            # Convert TradeSetup to monitoring dict (same format as save_monitoring_setups)
            if isinstance(setup.setup_time, (int, float)):
                setup_time_str = datetime.fromtimestamp(setup.setup_time).isoformat()
            elif isinstance(setup.setup_time, str):
                setup_time_str = setup.setup_time
            elif hasattr(setup.setup_time, 'isoformat'):
                setup_time_str = setup.setup_time.isoformat()
            else:
                setup_time_str = datetime.now().isoformat()
            
            fvg_top = setup.fvg.top if setup.fvg and hasattr(setup.fvg, 'top') else setup.entry_price
            fvg_bottom = setup.fvg.bottom if setup.fvg and hasattr(setup.fvg, 'bottom') else setup.entry_price
            
            # ── TODO-4 SYNC GUARD: Validate h4_sync_fvg fields ─────────────
            h4_sync_top_raw = getattr(setup, 'h4_sync_fvg_top', None)
            h4_sync_bot_raw = getattr(setup, 'h4_sync_fvg_bottom', None)
            h4_sync_top = float(h4_sync_top_raw) if h4_sync_top_raw and float(h4_sync_top_raw) > 0 else 0.0
            h4_sync_bot = float(h4_sync_bot_raw) if h4_sync_bot_raw and float(h4_sync_bot_raw) > 0 else 0.0

            if h4_sync_top == 0.0 or h4_sync_bot == 0.0:
                logger.warning(
                    f"⚠️ {symbol}: h4_sync_fvg missing or zero — "
                    f"setup lacks 4H Handshake confirmation. "
                    f"Tagging as NEEDS_RESCAN, skipping auto-arm."
                )
                # Do NOT save to monitoring — force a re-scan next cycle
                return None

            # ── TODO-4: Validate strategy_locked flag ─────────────────────────
            strategy_locked = getattr(setup, 'strategy_locked', None)
            if strategy_locked is False:
                logger.warning(
                    f"⚠️ {symbol}: strategy_locked=False — D1 bias not confirmed. "
                    f"Rejecting setup until daily_scanner re-locks bias."
                )
                return None

            monitoring_dict = {
                "symbol": setup.symbol,
                "direction": "buy" if setup.daily_choch.direction == "bullish" else "sell",
                "entry_price": float(setup.entry_price),
                "stop_loss": float(setup.stop_loss),
                "take_profit": float(setup.take_profit),
                "risk_reward": float(setup.risk_reward) if setup.risk_reward else 0.0,
                "strategy_type": setup.strategy_type,  # D1 bias: 'reversal' or 'continuation'
                "strategy_locked": True,  # Only reaches here if locked
                "setup_time": setup_time_str,
                "priority": setup.priority,
                "status": setup.status,  # MONITORING or READY
                "fvg_top": float(fvg_top) if fvg_top is not None else float(setup.entry_price),
                "fvg_bottom": float(fvg_bottom) if fvg_bottom is not None else float(setup.entry_price),
                "lot_size": 0.01,
                "source": "V9.0_AUTO_DISCOVERY",
                # 4H Sync FVG — entry zone from 4H confirmation move (validated above)
                "h4_sync_fvg_top": h4_sync_top,
                "h4_sync_fvg_bottom": h4_sync_bot,
            }
            
            strategy = setup.strategy_type.upper() if hasattr(setup, 'strategy_type') else "UNKNOWN"
            direction = monitoring_dict['direction'].upper()
            rr = monitoring_dict['risk_reward']
            
            logger.success(
                f"🎯 V9.0 SETUP DISCOVERED: {symbol} {direction} "
                f"@ {setup.entry_price:.5f} | SL {setup.stop_loss:.5f} | "
                f"TP {setup.take_profit:.5f} | RR 1:{rr:.1f} | {strategy}"
            )
            
            return monitoring_dict
            
        except Exception as e:
            logger.error(f"❌ V9.0 Discovery error for {symbol}: {e}")
            return None
    
    def _symbol_already_monitoring(self, symbol: str) -> bool:
        """Check if symbol already has an active setup in monitoring_setups.json"""
        try:
            if not self.monitoring_file.exists():
                return False
            with open(self.monitoring_file, 'r') as f:
                data = json.load(f)
                setups = data.get('setups', []) if isinstance(data, dict) else data
                for s in setups:
                    if s.get('symbol') == symbol and s.get('status') in ['MONITORING', 'READY', 'ACTIVE']:
                        return True
            return False
        except Exception:
            return False
    
    def _save_setup_to_monitoring(self, setup_dict: dict):
        """
        Save discovered setup to monitoring_setups.json.
        Uses fcntl locking to prevent corruption with setup_executor_monitor.py reading simultaneously.
        Merges with existing setups (same logic as daily_scanner.save_monitoring_setups).
        """
        try:
            symbol = setup_dict['symbol']
            
            # Load existing setups
            existing_setups = {}
            if self.monitoring_file.exists():
                try:
                    with open(self.monitoring_file, 'r') as f:
                        data = json.load(f)
                        setups_list = data.get('setups', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                        for s in setups_list:
                            if isinstance(s, dict) and 'symbol' in s:
                                existing_setups[s['symbol']] = s
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"⚠️ Could not read monitoring_setups.json: {e}")
            
            # Add/update the new setup
            existing_setups[symbol] = setup_dict
            
            # Write atomically with file lock
            monitoring_data = {
                "setups": list(existing_setups.values()),
                "last_updated": datetime.now().isoformat()
            }
            
            # Write to temp file first, then rename (atomic)
            tmp_file = self.monitoring_file.with_suffix('.tmp')
            with open(tmp_file, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(monitoring_data, f, indent=2)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            
            # Atomic rename
            tmp_file.rename(self.monitoring_file)
            
            # Track discovery to prevent re-discovery spam
            self.discovered_setups[symbol] = setup_dict.get('setup_time', datetime.now().isoformat())
            
            logger.success(f"💾 V9.0: {symbol} setup saved to monitoring_setups.json ({setup_dict['status']})")
            
        except Exception as e:
            logger.error(f"❌ Failed to save setup for {setup_dict.get('symbol', '?')}: {e}")

    # ━━━ AUDIT: CLEANUP — Remove EXPIRED/CLOSED setups to save VPS CPU/RAM ━━━

    def _cleanup_expired_setups(self):
        """
        VPS CLEANUP: Remove setups with status EXPIRED, CLOSED, CANCELLED, or FILLED
        from monitoring_setups.json.
        Called once per 4H cycle. Keeps file lean — no stale data accumulating.
        """
        try:
            if not self.monitoring_file.exists():
                return

            with open(self.monitoring_file, 'r') as f:
                data = json.load(f)

            setups = data.get('setups', []) if isinstance(data, dict) else data
            if not isinstance(setups, list):
                return

            DEAD_STATUSES = {'EXPIRED', 'CLOSED', 'CANCELLED', 'FILLED', 'INVALIDATED'}
            active = [s for s in setups if s.get('status', '').upper() not in DEAD_STATUSES]
            removed = len(setups) - len(active)

            if removed > 0:
                monitoring_data = {
                    "setups": active,
                    "last_updated": datetime.now().isoformat()
                }
                tmp_file = self.monitoring_file.with_suffix('.tmp')
                with open(tmp_file, 'w') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    json.dump(monitoring_data, f, indent=2)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                tmp_file.rename(self.monitoring_file)
                logger.info(f"🧹 CLEANUP: Removed {removed} dead setup(s) from monitoring_setups.json ({len(active)} active remaining)")
            else:
                logger.debug(f"🧹 CLEANUP: No dead setups found ({len(active)} active)")

        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")

    # ━━━ MISSION 1: BIAS AWARENESS — Read strategy_type from monitoring_setups.json ━━━

    def _get_setup_from_monitoring(self, symbol: str) -> Optional[dict]:
        """
        MISSION 1 + TODO-4: Read the current monitoring setup for a symbol from disk.
        Also validates: strategy_locked=True, h4_sync_fvg_top/bottom > 0.
        Logs a warning if handshake fields are missing so operator knows re-scan needed.
        Returns the setup dict or None.
        """
        try:
            if not self.monitoring_file.exists():
                return None
            with open(self.monitoring_file, 'r') as f:
                data = json.load(f)
            setups = data.get('setups', []) if isinstance(data, dict) else data
            for s in setups:
                if s.get('symbol') == symbol:
                    # Warn if handshake fields missing — operator should re-run scanner
                    h4_top = s.get('h4_sync_fvg_top', 0.0)
                    h4_bot = s.get('h4_sync_fvg_bottom', 0.0)
                    locked = s.get('strategy_locked', None)
                    if not h4_top or float(h4_top) == 0.0 or not h4_bot or float(h4_bot) == 0.0:
                        logger.warning(
                            f"⚠️ {symbol}: Disk setup missing h4_sync_fvg — "
                            f"run daily_scanner.py to refresh 4H Handshake data"
                        )
                    if locked is not True:
                        logger.warning(
                            f"⚠️ {symbol}: strategy_locked != True on disk "
                            f"(locked={locked}) — D1 bias unconfirmed"
                        )
                    return s
            return None
        except Exception as e:
            logger.debug(f"⚠️ Could not read setup from monitoring for {symbol}: {e}")
            return None

    # ━━━ MISSION 2: 4H BODY CLOSURE GUARD ━━━

    def _check_4h_body_closure(self, symbol: str) -> Tuple[bool, str]:
        """
        MISSION 2: Fetch the last closed 4H candle and verify it closed with a REAL BODY.
        Returns (body_closed: bool, reason: str).
        "Generalul 4H must close with a body — wicks don't count!"
        """
        try:
            df_4h = self._get_historical_data_cached(symbol, "H4", 5)
            if df_4h is None or len(df_4h) < 2:
                return False, "4H data unavailable"

            # Last CLOSED candle = second-to-last row (last row = current forming candle)
            candle = df_4h.iloc[-2]

            open_price = float(candle.get('open', candle.get('Open', 0)))
            close_price = float(candle.get('close', candle.get('Close', 0)))
            high_price = float(candle.get('high', candle.get('High', 0)))
            low_price = float(candle.get('low', candle.get('Low', 0)))

            if open_price == 0 or close_price == 0:
                return False, "4H candle data malformed"

            body_size = abs(close_price - open_price)
            candle_range = high_price - low_price if high_price > low_price else 0

            # Body must be > 30% of total candle range (not a doji/spinning top)
            if candle_range > 0:
                body_ratio = body_size / candle_range
            else:
                body_ratio = 0.0

            body_direction = "BULLISH" if close_price > open_price else "BEARISH"

            if body_size > 0 and body_ratio >= 0.30:
                reason = (
                    f"4H {body_direction} body ✅ "
                    f"O={self._fmt_price(open_price, symbol)} "
                    f"C={self._fmt_price(close_price, symbol)} "
                    f"body_ratio={body_ratio:.0%}"
                )
                logger.info(f"   ✅ {symbol} 4H body closure confirmed: {reason}")
                return True, reason
            else:
                reason = (
                    f"4H WICK/DOJI ❌ "
                    f"O={self._fmt_price(open_price, symbol)} "
                    f"C={self._fmt_price(close_price, symbol)} "
                    f"body_ratio={body_ratio:.0%} < 30%"
                )
                logger.warning(f"   ❌ {symbol} 4H body closure FAILED: {reason}")
                return False, reason

        except Exception as e:
            logger.error(f"❌ 4H body closure check error for {symbol}: {e}")
            return False, f"check error: {e}"

    def _send_auto_discovery_alert(self, setup_dict: dict):
        """
        V9.0: Send Telegram notification when a new setup is auto-discovered.
        MISSION 3: Format — SYMBOL | STRATEGY | STATUS
        ONE message per setup — no spam.
        """
        try:
            symbol = setup_dict['symbol']
            direction = setup_dict['direction'].upper()
            entry = setup_dict['entry_price']
            sl = setup_dict['stop_loss']
            tp = setup_dict['take_profit']
            rr = setup_dict['risk_reward']
            strategy = setup_dict.get('strategy_type', 'UNKNOWN').upper()
            status = setup_dict['status']

            strategy_emoji = "🔄" if strategy == "REVERSAL" else ("➡️" if strategy == "CONTINUITY" else "❓")
            dir_emoji = "🟢" if direction == "BUY" else "🔴"
            status_label = "READY TO TRADE" if status == "READY" else "MONITORING — WAITING FOR 4H BODY CLOSURE"

            message = (
                f"🤖 <b>V9.0 AUTO-DISCOVERY</b>\n\n"
                f"{dir_emoji} <b>{symbol} | {strategy} | {status_label}</b>\n\n"
                f"{strategy_emoji} Strategy: <b>{strategy}</b>\n"
                f"📍 Entry: <code>{entry:.5f}</code>\n"
                f"🛡️ SL:    <code>{sl:.5f}</code>\n"
                f"🎯 TP:    <code>{tp:.5f}</code>\n"
                f"📊 R:R:   <code>1:{rr:.1f}</code>\n\n"
                f"📋 Status: <b>{status}</b>\n"
                f"⚡ <i>Auto-detected at 4H candle close — execution engine armed</i>"
            )

            self._send_telegram(message)
            logger.info(f"📱 V9.0 auto-discovery alert sent for {symbol} [{strategy}]")
            
        except Exception as e:
            logger.error(f"❌ Auto-discovery alert error: {e}")
    
    def run(self):
        """
        Main loop - rulează continuu, analizează la fiecare închidere de candelă 4H
        """
        logger.info("🚀 Starting Real-Time Market Monitor (4H Timeframe)...")
        logger.info(f"📊 Monitoring {len(self.symbols)} symbols (ALL PAIRS)")
        logger.info(f"🕐 Analysis trigger: Every 4H candle close (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)")
        logger.info(f"🔔 Telegram alerts enabled\n")
        
        iteration = 0
        
        while True:
            iteration += 1
            logger.info(f"\n{'='*80}")
            logger.info(f"🕐 4H CANDLE CLOSE #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*80}\n")
            
            # V8.3: WEEKEND STANDBY — Markets closed, silence all alerts
            weekday = datetime.now().weekday()  # 0=Mon, 5=Sat, 6=Sun
            if weekday >= 5:  # Saturday or Sunday
                day_name = 'Saturday' if weekday == 5 else 'Sunday'
                logger.info(f"🌙 WEEKEND STANDBY — {day_name}. Markets closed. All alerts silenced.")
                self._wait_for_next_candle_close()
                continue
            
            # VPS CLEANUP: Remove dead setups before processing
            self._cleanup_expired_setups()

            for symbol in self.symbols:
                try:
                    self._check_symbol(symbol)
                except Exception as e:
                    logger.error(f"❌ Error checking {symbol}: {e}")
            
            # Summary
            ready_count = sum(1 for rec in self.last_recommendations.values() if rec == 'ready_to_trade')
            monitor_count = sum(1 for rec in self.last_recommendations.values() if rec == 'monitor_closely')
            wait_count = len(self.symbols) - ready_count - monitor_count
            
            logger.info(f"\n📊 4H CANDLE CLOSE SUMMARY:")
            logger.info(f"   ✅ Ready to trade: {ready_count}")
            logger.info(f"   👀 Monitor closely: {monitor_count}")
            logger.info(f"   ⏳ Waiting: {wait_count}")
            
            # V8.5: STARTUP SILENCE — send ONE compact summary on first scan, then unlock
            if self.is_initial_scan:
                self.is_initial_scan = False
                self._send_startup_summary(ready_count, monitor_count, wait_count)
                logger.info("🔓 Initial scan complete — individual alerts now UNLOCKED")
            
            # Wait for next 4H candle close
            self._wait_for_next_candle_close()
    
    def _check_symbol(self, symbol: str):
        """
        Check un simbol și detectează schimbări în narrativ
        V8.2: Data error isolation — nu mai triggerează DOWNGRADE pe erori de date
        """
        try:
            logger.info(f"🔍 Analyzing {symbol}...")
            
            # Get analyzer
            analyzer = self.analyzers[symbol]
            
            # Analyze current state
            narrative = analyzer.analyze_market()
            
            if not narrative or not hasattr(narrative, 'recommendation'):
                logger.warning(f"⚠️  Invalid narrative for {symbol}, skipping")
                return
            
            # V8.2: ISOLATE DATA ERRORS — don't let API failures trigger fake downgrades
            if narrative.setup_status == 'data_unavailable':
                self.data_error_counts[symbol] = self.data_error_counts.get(symbol, 0) + 1
                count = self.data_error_counts[symbol]
                logger.warning(f"⚠️ {symbol}: Data unavailable (consecutive: {count}/{self.MAX_DATA_ERRORS_BEFORE_ALERT})")
                
                # Only send ONE alert after N consecutive failures, then silence
                if count == self.MAX_DATA_ERRORS_BEFORE_ALERT:
                    self._send_data_error_alert(symbol, count)
                
                # CRITICAL: Do NOT update last_recommendations — keep previous valid state
                return
            
            # Data is valid — reset error counter
            self.data_error_counts[symbol] = 0
            
            # Store narrative
            self.last_narratives[symbol] = narrative
            
            # Check for state changes
            previous_rec = self.last_recommendations[symbol]
            current_rec = narrative.recommendation
            
            if current_rec != previous_rec:
                # CHANGE DETECTED!
                self._handle_state_change(symbol, previous_rec, current_rec, narrative)
            else:
                # Same state — but if actionable, check if setup needs discovery
                logger.info(f"   Status: {current_rec.upper()}")
                if narrative.waiting_for:
                    logger.info(f"   Waiting: {', '.join(narrative.waiting_for[:2])}")
                
                # V9.0: If state is already actionable AND no setup in monitoring, discover
                if current_rec in ('ready_to_trade', 'monitor_closely'):
                    if not self._symbol_already_monitoring(symbol):
                        logger.info(f"🔬 V9.0: {symbol} is {current_rec} but not in monitoring — running discovery")
                        setup_dict = self._discover_setup(symbol, narrative)
                        if setup_dict:
                            self._save_setup_to_monitoring(setup_dict)
                            if not self.is_initial_scan:
                                self._send_auto_discovery_alert(setup_dict)
            
            # Update last recommendation
            self.last_recommendations[symbol] = current_rec
        except Exception as e:
            logger.error(f"❌ Error analyzing {symbol}: {e}", exc_info=False)
            # Don't update state - keep previous recommendation
    
    def _handle_state_change(
        self, 
        symbol: str, 
        old_state: str, 
        new_state: str, 
        narrative: MarketNarrative
    ):
        """
        Handle state change (unknown → waiting → monitoring → ready)
        V8.5: During initial scan, only READY_TO_TRADE sends individual alerts
        """
        logger.info(f"\n🔔 {symbol} STATE CHANGE: {old_state} → {new_state}")
        
        if new_state == 'ready_to_trade':
            # 🚨 READY TO TRADE - ALWAYS send (even on initial scan — this is critical)
            self._send_ready_alert(symbol, narrative)
            # V9.0: AUTO-DISCOVER concrete setup and save to monitoring
            setup_dict = self._discover_setup(symbol, narrative)
            if setup_dict:
                self._save_setup_to_monitoring(setup_dict)
                self._send_auto_discovery_alert(setup_dict)
            
        elif new_state == 'monitor_closely':
            # V8.5: Suppress individual MONITOR alerts during initial scan
            if self.is_initial_scan:
                logger.info(f"   🔇 Startup silence — {symbol} MONITOR alert suppressed (will be in summary)")
            else:
                # 👀 MONITOR CLOSELY - Send tracking alert
                self._send_monitoring_alert(symbol, narrative)
            
            # V9.0: AUTO-DISCOVER concrete setup and save to monitoring
            # Even during startup silence, we still discover and save setups
            setup_dict = self._discover_setup(symbol, narrative)
            if setup_dict:
                self._save_setup_to_monitoring(setup_dict)
                if not self.is_initial_scan:
                    self._send_auto_discovery_alert(setup_dict)
            
        elif new_state == 'wait_for_confirmation' and old_state in ['monitor_closely', 'ready_to_trade']:
            # ⚠️ Downgrade - setup degraded
            # V8.2: Cooldown — max 1 downgrade per symbol per 24h
            last_downgrade = self.downgrade_cooldown.get(symbol)
            if last_downgrade and (datetime.now() - last_downgrade).total_seconds() < self.DOWNGRADE_COOLDOWN_HOURS * 3600:
                hours_ago = (datetime.now() - last_downgrade).total_seconds() / 3600
                logger.info(f"   ⏸️ Downgrade alert suppressed for {symbol} (cooldown: sent {hours_ago:.1f}h ago)")
            else:
                self._send_downgrade_alert(symbol, old_state, new_state, narrative)
                self.downgrade_cooldown[symbol] = datetime.now()
        
        elif new_state == 'avoid' and old_state != 'unknown':
            # ❌ INVALIDATED - setup invalidated
            self._send_invalidation_alert(symbol, narrative)
    
    @staticmethod
    def _symbols_grid(symbols: list, cols: int = 3, max_rows: int = 5) -> str:
        """
        Render a list of symbols as a mobile-friendly grid.
        Accepts plain strings OR (symbol, label) tuples.
          str   → '• XAUUSD'
          tuple → '• XAUUSD [REV-🔒]'
        max_rows * cols = max symbols shown before '+ N more'.
        """
        max_show = cols * max_rows
        shown = symbols[:max_show]
        remaining = len(symbols) - len(shown)
        lines = []
        for i in range(0, len(shown), cols):
            row = shown[i:i + cols]
            cells = []
            for item in row:
                if isinstance(item, tuple):
                    sym, lbl = item[0], item[1]
                    cells.append(f"• {sym} {lbl}")
                else:
                    cells.append(f"• {item:<7}")
            lines.append("  " + "  ".join(cells))
        grid = "\n".join(lines)
        if remaining > 0:
            grid += f"\n  + {remaining} more"
        return grid

    def _send_startup_summary(self, ready_count: int, monitor_count: int, wait_count: int):
        """
        ONE compact message after initial scan — replaces N individual alerts.
        Mobile-friendly 3-column grid for symbol lists.
        """
        try:
            # ── Build labeled symbol tuples: (symbol, '[REV-🔒]') ──
            def _strategy_label(sym: str) -> str:
                """Return '[REV-🔒]' / '[CNT-🔒]' / '[🔓]' based on monitoring_setups.json"""
                try:
                    setup = self._get_setup_from_monitoring(sym)
                    if not setup:
                        return ''
                    stype = setup.get('strategy_type', '').upper()
                    locked = setup.get('strategy_locked', False)
                    if stype in ('REVERSAL',):
                        tag = 'REV'
                    elif stype in ('CONTINUATION', 'CONTINUITY'):
                        tag = 'CNT'
                    else:
                        tag = ''
                    lock_icon = '🔒' if locked else '🔓'
                    return f'[{tag}-{lock_icon}]' if tag else f'[{lock_icon}]'
                except Exception:
                    return ''

            monitoring_symbols = [
                (sym, _strategy_label(sym))
                for sym, rec in self.last_recommendations.items()
                if rec == 'monitor_closely'
            ]
            ready_symbols = [
                (sym, _strategy_label(sym))
                for sym, rec in self.last_recommendations.items()
                if rec == 'ready_to_trade'
            ]

            message = (
                f"🛰️ <b>WATCHDOG SYNC COMPLETE</b>\n\n"
                f"📡 Monitoring <b>{len(self.symbols)}</b> pairs\n"
            )

            if ready_count > 0:
                grid = self._symbols_grid(ready_symbols, cols=3)
                message += f"\n🔥 <b>Ready ({ready_count}):</b>\n{grid}\n"

            if monitor_count > 0:
                grid = self._symbols_grid(monitoring_symbols, cols=3)
                message += f"\n👀 <b>Pândă ({monitor_count}):</b>\n{grid}\n"

            message += f"\n⏳ <b>Waiting:</b> {wait_count}"
            
            self._send_telegram(message)
            logger.info(f"🛰️ Startup summary sent (ready={ready_count}, monitor={monitor_count}, wait={wait_count})")
        except Exception as e:
            logger.error(f"❌ Startup summary error: {e}")
    
    def _send_data_error_alert(self, symbol: str, consecutive_count: int):
        """
        🔍 Data unavailable — Elite format, sent only once after N failures
        """
        try:
            message = f"""
🔍 <b>{symbol} — MAPPING LIQUIDITY...</b>

🔄 SYNCING WITH MARKET DNA...
Consecutive cycles: {consecutive_count}

<i>Silent mode engaged. Will auto-resume.</i>
            """
            self._send_telegram(message)
            logger.warning(f"🔍 Data sync alert sent for {symbol} (after {consecutive_count} failures)")
        except Exception as e:
            logger.debug(f"Could not send data error alert for {symbol}: {e}")
    
    def _send_ready_alert(self, symbol: str, narrative: MarketNarrative):
        """
        MISSION 2+3: READY TO TRADE — 4H Body Closure Gate + Strategy/Bias in message.
        "Generalul 4H must close with body — wicks don't count!"
        """
        try:
            # ── MISSION 2: 4H BODY CLOSURE GATE ──────────────────────────────
            body_closed, body_reason = self._check_4h_body_closure(symbol)
            if not body_closed:
                # 4H closed as wick/doji — downgrade alert to WAITING
                logger.warning(
                    f"🚫 {symbol}: READY suppressed — 4H body closure FAILED ({body_reason})"
                )
                # Send a WAITING alert instead of READY
                self._send_waiting_body_closure_alert(symbol, body_reason)
                return

            # ── MISSION 1: BIAS AWARENESS — read strategy_type from disk ─────
            setup = self._get_setup_from_monitoring(symbol)
            strategy_type = "UNKNOWN"
            direction = "N/A"
            entry = sl = tp = rr = None
            if setup:
                strategy_type = setup.get('strategy_type', 'UNKNOWN').upper()
                direction = setup.get('direction', 'N/A').upper()
                entry = setup.get('entry_price')
                sl = setup.get('stop_loss')
                tp = setup.get('take_profit')
                rr = setup.get('risk_reward')

            strategy_emoji = "🔄" if strategy_type == "REVERSAL" else ("➡️" if strategy_type == "CONTINUITY" else "❓")
            dir_emoji = "🟢" if direction == "BUY" else ("🔴" if direction == "SELL" else "⚪")

            scenarios = narrative.expected_scenarios if hasattr(narrative, 'expected_scenarios') else []
            scenarios_text = "\n".join(f"• {s}" for s in scenarios[:3]) if scenarios else "• Execution conditions met"

            # Build entry/SL/TP lines only if available — instrument-aware decimals
            levels_text = ""
            if entry is not None and sl is not None and tp is not None:
                levels_text = (
                    f"\n📍 Entry: <code>{self._fmt_price(entry, symbol)}</code>"
                    f"\n🛡️ SL:    <code>{self._fmt_price(sl, symbol)}</code>"
                    f"\n🎯 TP:    <code>{self._fmt_price(tp, symbol)}</code>"
                    + (f"\n📊 R:R:   <code>1:{rr:.1f}</code>" if rr else "")
                )

            message = (
                f"🚨🔥 <b>{symbol} | {strategy_type} | READY TO TRADE!</b> 🔥🚨\n\n"
                f"{dir_emoji} Direction: <b>{direction}</b>\n"
                f"{strategy_emoji} Strategy: <b>{strategy_type}</b>\n"
                f"💪 Confidence: <b>{narrative.confidence:.0%}</b>\n"
                f"✅ 4H Body: <b>CONFIRMED</b> — {body_reason}\n"
                f"{levels_text}\n\n"
                f"<b>📊 SCENARIOS:</b>\n{scenarios_text}\n\n"
                f"<b>✅ ALL CONFIRMATIONS PRESENT — EXECUTE NOW!</b>\n\n"
                f"<b>🔍 MARKET STATE:</b>\n"
                f"• Structure: {narrative.condition.value}\n"
                f"• CHoCH Count: {narrative.choch_count}\n"
                f"• FVG Count: {narrative.fvg_count}\n"
                f"• Volatility: {narrative.volatility_level}"
            )

            self._send_telegram(message)
            logger.info(f"🚨 READY ALERT sent for {symbol} [{strategy_type}]")
        except Exception as e:
            logger.debug(f"Could not send ready alert for {symbol}: {e}")

    def _send_waiting_body_closure_alert(self, symbol: str, body_reason: str):
        """
        MISSION 2+3: 4H candle closed as wick/doji — notify WAITING FOR 4H BODY CLOSURE.
        Prevents false READY signals from wick-only 4H closes.
        """
        try:
            setup = self._get_setup_from_monitoring(symbol)
            strategy_type = setup.get('strategy_type', 'UNKNOWN').upper() if setup else "UNKNOWN"
            direction = setup.get('direction', 'N/A').upper() if setup else "N/A"
            status = setup.get('status', 'MONITORING') if setup else "MONITORING"
            strategy_emoji = "🔄" if strategy_type == "REVERSAL" else ("➡️" if strategy_type == "CONTINUITY" else "❓")
            dir_emoji = "🟢" if direction == "BUY" else ("🔴" if direction == "SELL" else "⚪")

            message = (
                f"⏳ <b>{symbol} | {strategy_type} | WAITING FOR 4H BODY CLOSURE</b>\n\n"
                f"{dir_emoji} Direction: <b>{direction}</b>\n"
                f"{strategy_emoji} Strategy: <b>{strategy_type}</b>\n"
                f"📋 Status: <b>{status}</b>\n\n"
                f"❌ 4H Body: <b>NOT CONFIRMED</b>\n"
                f"<i>Reason: {body_reason}</i>\n\n"
                f"⚠️ <b>Generalul 4H must close with body — wicks don't count!</b>\n"
                f"🔔 <i>Will re-check at next 4H candle close</i>"
            )
            self._send_telegram(message)
            logger.info(f"⏳ WAITING-BODY-CLOSURE alert sent for {symbol} [{strategy_type}]")
        except Exception as e:
            logger.debug(f"Could not send waiting body closure alert for {symbol}: {e}")

    def _send_monitoring_alert(self, symbol: str, narrative: MarketNarrative):
        """
        MISSION 3: MONITOR CLOSELY — shows strategy_type + D1 bias in Telegram.
        Format: XAUUSD | REVERSAL | PRICE IN D1 ZONE
        """
        try:
            # ── MISSION 1: Read strategy_type from disk ───────────────────────
            setup = self._get_setup_from_monitoring(symbol)
            strategy_type = "UNKNOWN"
            direction = "N/A"
            fvg_top = fvg_bottom = None
            if setup:
                strategy_type = setup.get('strategy_type', 'UNKNOWN').upper()
                direction = setup.get('direction', 'N/A').upper()
                fvg_top = setup.get('fvg_top') or setup.get('h4_sync_fvg_top')
                fvg_bottom = setup.get('fvg_bottom') or setup.get('h4_sync_fvg_bottom')

            strategy_emoji = "🔄" if strategy_type == "REVERSAL" else ("➡️" if strategy_type == "CONTINUITY" else "❓")
            dir_emoji = "🟢" if direction == "BUY" else ("🔴" if direction == "SELL" else "⚪")

            scenarios = narrative.expected_scenarios if hasattr(narrative, 'expected_scenarios') else []
            scenarios_text = "\n".join(f"• {s}" for s in scenarios[:3]) if scenarios else "• Setup forming..."

            # FVG zone lines — instrument-aware decimal display
            zone_text = ""
            if fvg_top and fvg_bottom and float(fvg_top) > 0 and float(fvg_bottom) > 0:
                zone_text = (
                    f"\n📦 D1 Zone: <code>{self._fmt_price(float(fvg_bottom), symbol)}</code>"
                    f" → <code>{self._fmt_price(float(fvg_top), symbol)}</code>"
                )

            waiting_lines = ""
            for conf in narrative.waiting_for[:5]:
                waiting_lines += f"• {conf.replace('_', ' ').title()}\n"

            conf_display = f"{narrative.confidence:.0%}" if narrative.confidence > 0 else "🔄 SYNCING..."

            message = (
                f"👀 <b>{symbol} | {strategy_type} | PRICE IN D1 ZONE</b>\n\n"
                f"{dir_emoji} Direction: <b>{direction}</b>\n"
                f"{strategy_emoji} Strategy: <b>{strategy_type}</b>\n"
                f"💪 Confidence: <b>{conf_display}</b>"
                f"{zone_text}\n\n"
                f"<b>📊 SCENARIO:</b>\n{scenarios_text}\n\n"
                f"<b>⏳ WAITING FOR:</b>\n{waiting_lines}"
                f"\n🔔 <i>Will alert when 4H closes with body → READY!</i>"
            )

            self._send_telegram(message)
            logger.info(f"👀 Monitoring alert sent for {symbol} [{strategy_type}]")
        except Exception as e:
            logger.debug(f"Could not send monitoring alert for {symbol}: {e}")
    
    def _send_downgrade_alert(self, symbol: str, old_state: str, new_state: str, narrative: MarketNarrative):
        """
        ⚠️ Setup degraded — V8.3 Elite Terminal Format
        """
        try:
            # V8.3: Elite terminology
            conf_display = f"{narrative.confidence:.0%}" if narrative.confidence > 0 else "🔄 SYNCING WITH MARKET DNA..."
            setup_display = narrative.setup_status.replace('_', ' ').title()
            if setup_display.lower() in ('error', 'data unavailable', 'data_unavailable'):
                setup_display = "🔍 MAPPING LIQUIDITY..."
            
            message = f"""
⚠️ <b>{symbol} — RECALIBRATING</b>

{old_state.replace('_', ' ').upper()} → {new_state.replace('_', ' ').upper()}

• Confidence: {conf_display}
• Status: {setup_display}
• Condition: {narrative.condition.value}
• Volatility: {narrative.volatility_level}

⏳ <i>Sovereign logic recalibrating...</i>
            """
            
            self._send_telegram(message)
            logger.warning(f"⚠️ Downgrade alert sent for {symbol}")
        except Exception as e:
            logger.debug(f"Could not send downgrade alert for {symbol}: {e}")
    
    def _send_invalidation_alert(self, symbol: str, narrative: MarketNarrative):
        """
        ❌ Setup invalidated — V8.3 Elite Terminal Format
        """
        try:
            conf_display = f"{narrative.confidence:.0%}" if narrative.confidence > 0 else "🔄 SYNCING WITH MARKET DNA..."
            setup_display = narrative.setup_status.replace('_', ' ').title()
            if setup_display.lower() in ('error', 'data unavailable', 'data_unavailable'):
                setup_display = "🔍 MAPPING LIQUIDITY..."
            
            message = f"""
❌ <b>{symbol} — SETUP INVALIDATED</b>

• Condition: {narrative.condition.value}
• Confidence: {conf_display}
• Status: {setup_display}

⏸️ <i>Awaiting new sovereign setup...</i>
            """
            
            self._send_telegram(message)
            logger.warning(f"❌ Invalidation alert sent for {symbol}")
        except Exception as e:
            logger.debug(f"Could not send invalidation alert for {symbol}: {e}")
    
    def _send_telegram(self, message: str):
        """
        Send Telegram message — Official 4-line Sovereign Signature on every alert.
        """
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("Telegram not configured")
            return
        
        try:
            # ═══ SOVEREIGN SIGNATURE — 4-line official branding ═══
            sep = "────────────────"  # 16 chars
            branded = (
                f"{message.strip()}\n\n"
                f"  {sep}\n"
                f"  🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
                f"  {sep}\n"
                f"&#8195;&#8195;🏛️ <b>Глитч Ин Матрикс</b> 🏛️"
            )
            
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': branded,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                logger.debug("✅ Telegram message sent")
            else:
                logger.error(f"❌ Telegram error: {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Telegram exception: {e}")


def main():
    """
    Start real-time monitor pentru TOATE perechile din config (4H timeframe)
    """
    # 🔒 PID LOCK SINGLETON — Prevent duplicate instances
    lock_file = Path("process_realtime_monitor.lock")
    if not acquire_pid_lock(lock_file):
        logger.error("🚫 DUPLICATE INSTANCE DETECTED — Exiting to prevent race conditions")
        sys.exit(1)
    atexit.register(release_pid_lock, lock_file)

    try:
        # Load ALL symbols from pairs_config.json
        import json
        with open('pairs_config.json', 'r') as f:
            config = json.load(f)
            symbols = [pair['symbol'] for pair in config['pairs']]
        
        logger.info(f"📋 Loaded {len(symbols)} pairs from config:")
        for i, sym in enumerate(symbols, 1):
            logger.info(f"   {i}. {sym}")
        
        # Create monitor (checks every 4H candle close)
        monitor = RealtimeMonitor(symbols, check_interval_hours=4)
        
        # Run forever
        monitor.run()
        
    except KeyboardInterrupt:
        logger.info("\n\n⏸️  Monitor stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")


if __name__ == "__main__":
    main()
