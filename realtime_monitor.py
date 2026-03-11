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
from typing import Dict, List, Optional
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
            
            df_daily = self._get_historical_data(symbol, "D1", daily_count)
            df_4h = self._get_historical_data(symbol, "H4", h4_count)
            df_1h = self._get_historical_data(symbol, "H1", h1_count)
            
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
            
            monitoring_dict = {
                "symbol": setup.symbol,
                "direction": "buy" if setup.daily_choch.direction == "bullish" else "sell",
                "entry_price": float(setup.entry_price),
                "stop_loss": float(setup.stop_loss),
                "take_profit": float(setup.take_profit),
                "risk_reward": float(setup.risk_reward) if setup.risk_reward else 0.0,
                "strategy_type": setup.strategy_type,
                "setup_time": setup_time_str,
                "priority": setup.priority,
                "status": setup.status,  # MONITORING or READY
                "fvg_top": float(fvg_top) if fvg_top is not None else float(setup.entry_price),
                "fvg_bottom": float(fvg_bottom) if fvg_bottom is not None else float(setup.entry_price),
                "lot_size": 0.01,
                "source": "V9.0_AUTO_DISCOVERY"  # Tag auto-discovered setups
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
    
    def _send_auto_discovery_alert(self, setup_dict: dict):
        """
        V9.0: Send Telegram notification when a new setup is auto-discovered.
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
            
            strategy_emoji = "🔄" if strategy == "REVERSAL" else "➡️"
            dir_emoji = "🟢" if direction == "BUY" else "🔴"
            
            message = f"""
🤖 <b>V9.0 AUTO-DISCOVERY</b>

{dir_emoji} <b>{symbol} — {direction}</b>
{strategy_emoji} Strategy: <b>{strategy}</b>

📍 Entry: <code>{entry:.5f}</code>
🛡️ SL: <code>{sl:.5f}</code>
🎯 TP: <code>{tp:.5f}</code>
📊 R:R: <code>1:{rr:.1f}</code>

📋 Status: <b>{status}</b>
⚡ <i>Auto-detected at 4H candle close — execution engine armed</i>
"""
            
            self._send_telegram(message)
            logger.info(f"📱 V9.0 auto-discovery alert sent for {symbol}")
            
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
    
    def _send_startup_summary(self, ready_count: int, monitor_count: int, wait_count: int):
        """
        V8.5: ONE compact message after initial scan — replaces 16 individual alerts
        """
        try:
            # Collect monitoring symbols for the summary
            monitoring_symbols = [
                sym for sym, rec in self.last_recommendations.items()
                if rec == 'monitor_closely'
            ]
            ready_symbols = [
                sym for sym, rec in self.last_recommendations.items()
                if rec == 'ready_to_trade'
            ]
            
            message = f"""🛰️ <b>WATCHDOG SYNC COMPLETE</b>

📡 Monitoring <b>{len(self.symbols)}</b> pairs
"""
            if ready_count > 0:
                symbols_text = ", ".join(f"<code>{s}</code>" for s in ready_symbols)
                message += f"\n🔥 <b>Ready:</b> {symbols_text}\n"
            
            if monitor_count > 0:
                symbols_text = ", ".join(f"<code>{s}</code>" for s in monitoring_symbols[:8])
                if len(monitoring_symbols) > 8:
                    symbols_text += f" +{len(monitoring_symbols) - 8} more"
                message += f"\n👀 <b>Pândă ({monitor_count}):</b> {symbols_text}\n"
            
            message += f"⏳ <b>Waiting:</b> {wait_count}"
            
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
        🚨 READY TO TRADE - toate confirmările prezente!
        """
        try:
            scenarios = narrative.expected_scenarios if hasattr(narrative, 'expected_scenarios') else []
            
            if not scenarios:
                logger.debug(f"Skipping ready alert for {symbol} - no scenarios")
                return
            
            scenarios_text = "\n".join(f"• {s}" for s in scenarios[:3])
            
            message = f"""
🚨🔥 <b>{symbol} - READY TO TRADE!</b> 🔥🚨

<b>💪 Confidence:</b> {narrative.confidence:.0%}

<b>📊 SCENARIOS:</b>
{scenarios_text}

<b>✅ ALL CONFIRMATIONS PRESENT - EXECUTE NOW!</b>

<b>🔍 MARKET STATE:</b>
• Structure: {narrative.condition.value}
• CHoCH Count: {narrative.choch_count}
• FVG Count: {narrative.fvg_count}
• Volatility: {narrative.volatility_level}
"""
            
            self._send_telegram(message)
            logger.info(f"🚨 READY ALERT sent for {symbol}")
        except Exception as e:
            logger.debug(f"Could not send ready alert for {symbol}: {e}")
    
    def _send_monitoring_alert(self, symbol: str, narrative: MarketNarrative):
        """
        👀 MONITOR CLOSELY - setup forming
        """
        try:
            scenarios = narrative.expected_scenarios if hasattr(narrative, 'expected_scenarios') else []
            
            if not scenarios:
                logger.debug(f"Skipping alert for {symbol} - no scenarios")
                return
            
            scenarios_text = "\n".join(f"• {s}" for s in scenarios[:3])
            
            message = f"""
👀 <b>{symbol} - MONITOR CLOSELY</b>

<b>📊 SCENARIO:</b>
{scenarios_text}

<b>⏳ WAITING FOR:</b>
"""
            
            for conf in narrative.waiting_for[:5]:
                message += f"• {conf.replace('_', ' ').title()}\n"
            
            conf_display = f"{narrative.confidence:.0%}" if narrative.confidence > 0 else "🔄 SYNCING WITH MARKET DNA..."
            setup_display = narrative.setup_status.replace('_', ' ').title()
            if setup_display.lower() in ('error', 'data unavailable', 'data_unavailable'):
                setup_display = "🔍 MAPPING LIQUIDITY..."
            
            message += f"""
<b>🔍 STATUS:</b>
• Confidence: {conf_display}
• Setup: {setup_display}

🔔 <i>Will alert when READY!</i>
            """
            
            self._send_telegram(message)
            logger.info(f"👀 Monitoring alert sent for {symbol}")
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
        Send Telegram message with Sovereign Signature
        """
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("Telegram not configured")
            return
        
        try:
            sep = "────────────────"  # 16 chars — compact symmetric
            branded = (
                f"{message.strip()}\n\n"
                f"  {sep}\n"
                f"  🔱 <b>AUTHORED BY ФорексГод</b> 🔱\n"
                f"  {sep}\n"
                f"  🏛️ INSTITUTIONAL TERMINAL 🏛️"
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
    # 🔒 V9.1 PID LOCK — Prevent duplicate instances (R9 AUDIT FIX by POCOVNICU)
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
