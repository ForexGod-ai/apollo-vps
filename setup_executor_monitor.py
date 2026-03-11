"""
Setup Executor Monitor - Monitorizează monitoring_setups.json și execută când devin READY

V3.2 PULLBACK STRATEGY + SCALE_IN:
- Entry 1: Wait for pullback to Fibo 50% after 1H CHoCH (50% position)
- Entry 2: Execute on 4H CHoCH within 48h (50% position)
- Timeout handling: Force entry at current price or skip after 24h

Verifică la fiecare 30s:
1. Citește monitoring_setups.json
2. Verifică 1H CHoCH + Pullback validation
3. Execută Entry 1 când pullback reached
4. Trimite Telegram notification
"""
import json
import time
from pathlib import Path
from loguru import logger
from datetime import datetime
import sys
import os
import psutil
import pandas as pd

# ━━━ V8.0 VPS-READY: Force UTC timezone + persistent log file ━━━
os.environ['TZ'] = 'UTC'
try:
    time.tzset()  # Apply TZ change (Unix only)
except AttributeError:
    pass  # Windows doesn't have tzset

_LOG_DIR = Path(__file__).parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)
logger.add(
    str(_LOG_DIR / "setup_executor_monitor.log"),
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
        if lock_file.exists():
            # Read existing PID
            with open(lock_file, 'r') as f:
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

from ctrader_cbot_client import CTraderCBotClient
from ctrader_executor import CTraderExecutor
from telegram_notifier import TelegramNotifier
from daily_scanner import CTraderDataProvider
from smc_detector import (
    validate_choch_confirmation_scale_in,
    SMCDetector,
    calculate_choch_fibonacci,
    validate_pullback_entry,
    TradeSetup,
    CHoCH,
    FVG
)

# 🛡️ V3.8 ANTI-SPAM SYSTEM by ФорексГод
from signal_cache import (
    SignalCache,
    TelegramDebouncer,
    cleanup_old_signals_file,
    get_signal_cache,
    get_telegram_debouncer
)


class SetupExecutorMonitor:
    """🔥 AGGRESSIVE EXECUTIONER - Instant MONITORING→EXECUTE transition"""
    
    def __init__(self, check_interval: int = 5):  # 🚀 5s HIGH-FREQUENCY for in-zone setups
        self.check_interval = check_interval
        self.monitoring_file = Path("monitoring_setups.json")
        self.executed_file = Path(".executed_setups.json")
        self.config_file = Path("pairs_config.json")
        
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
        self.rejection_cooldown_seconds = 14400  # 4 hours (V9.1 fix by POCOVNICU)
        
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
            'use_1h_sl': True,  # 🎯 V3.3 SNIPER: Use 1H SL instead of Daily SL
            'use_4h_sl': True   # 💎 V3.3 HIGH CONFIDENCE: Use 4H SL for 4H entries
        })
        
        # SMC Detector for CHoCH detection
        self.smc_detector = SMCDetector()
        
        # Track executed setups to avoid duplicates
        self.executed_setups = self._load_executed_setups()
        
        logger.info("🎯 Setup Executor Monitor initialized")
        logger.info(f"⏱️  Check interval: {check_interval}s")
        logger.info(f"📊 Execution Strategy: {self.execution_strategy.get('mode', 'N/A')}")
        logger.info(f"🎯 V3.2 Pullback Strategy: {'ENABLED' if self.pullback_config['enabled'] else 'DISABLED'}")
        logger.info(f"🎯 V3.3 SNIPER SL (1H): {'ENABLED' if self.pullback_config.get('use_1h_sl', True) else 'DISABLED'}")
        logger.info(f"💎 V3.3 HIGH CONFIDENCE SL (4H): {'ENABLED' if self.pullback_config.get('use_4h_sl', True) else 'DISABLED'}")
    
    def _load_config(self):
        """Load pairs_config.json"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
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
        """Load previously executed setups — V9.1: Auto-cleanup entries >30 days (R1 AUDIT FIX by POCOVNICU)"""
        if self.executed_file.exists():
            try:
                with open(self.executed_file, 'r') as f:
                    data = json.load(f)
                
                # V9.1 R1 FIX: Cleanup entries older than 30 days
                executed_keys = set(data.get('executed_keys', []))
                timestamps = data.get('timestamps', {})
                cutoff = (datetime.now() - timedelta(days=30)).isoformat()
                
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
                        with open(self.executed_file, 'w') as f:
                            json.dump({
                                'executed_keys': list(executed_keys),
                                'timestamps': timestamps,
                                'last_update': datetime.now().isoformat(),
                                'last_cleanup': datetime.now().isoformat()
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
                    with open(self.executed_file, 'r') as f:
                        old_data = json.load(f)
                        existing_timestamps = old_data.get('timestamps', {})
                except Exception:
                    pass
            
            # Add timestamp for new entry
            existing_timestamps[setup_key] = datetime.now().isoformat()
            
            with open(self.executed_file, 'w') as f:
                json.dump({
                    'executed_keys': list(self.executed_setups),
                    'timestamps': existing_timestamps,
                    'last_update': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save executed setup: {e}")
    
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
        """
        🎯 V3.3 SNIPER ENTRY - Uses 1H/4H FVG data from multi_tf_radar.py
        
        Priority System:
        1. If radar_1h_in_fvg=True → EXECUTE_ENTRY1 (SNIPER)
        2. If radar_4h_in_fvg=True → EXECUTE_ENTRY2 (HIGH CONFIDENCE)
        3. Otherwise → KEEP_MONITORING
        
        Entry Point: 
        - 1H: Use radar_1h_fvg_entry (middle of 1H FVG)
        - 4H: Use radar_4h_fvg_entry (middle of 4H FVG)
        
        Stop Loss:
        - 1H: Use 1H CHoCH swing + 10 pips buffer (SNIPER SL)
        - 4H: Use 4H CHoCH swing + 10 pips buffer
        
        This replaces Fibonacci 50% logic with actual FVG entry zones.
        """
        direction = setup['direction'].lower()
        
        # Get radar data
        radar_1h_in_fvg = setup.get('radar_1h_in_fvg', False)
        radar_1h_fvg_entry = setup.get('radar_1h_fvg_entry')
        radar_1h_choch_price = setup.get('radar_1h_choch_price')
        
        radar_4h_in_fvg = setup.get('radar_4h_in_fvg', False)
        radar_4h_fvg_entry = setup.get('radar_4h_fvg_entry')
        radar_4h_choch_price = setup.get('radar_4h_choch_price')
        
        # Check Premium/Discount validation
        if radar_1h_in_fvg and radar_1h_fvg_entry and radar_1h_choch_price:
            # Validate Premium/Discount zone
            if direction == 'buy':
                # For LONG: FVG should be in DISCOUNT (below CHoCH)
                zone_valid = radar_1h_fvg_entry < radar_1h_choch_price
                zone_type = "DISCOUNT"
            else:
                # For SHORT: FVG should be in PREMIUM (above CHoCH)
                zone_valid = radar_1h_fvg_entry > radar_1h_choch_price
                zone_type = "PREMIUM"
            
            if not zone_valid:
                logger.warning(f"⚠️  {symbol}: 1H FVG not in {zone_type} zone - skipping entry")
                return {
                    'action': 'KEEP_MONITORING',
                    'reason': f'1H FVG not in {zone_type} zone (invalid setup)'
                }
            
            # 🎯 EXECUTE SNIPER ENTRY (1H FVG)
            logger.success(f"🎯 {symbol}: SNIPER ENTRY! Price in 1H FVG @ {radar_1h_fvg_entry:.5f}")
            
            # Calculate SNIPER SL (10 pips from 1H CHoCH swing)
            if direction == 'buy':
                # For LONG: SL below 1H CHoCH low
                radar_1h_fvg_bottom = setup.get('radar_1h_fvg_bottom', radar_1h_fvg_entry)
                sniper_sl = radar_1h_fvg_bottom - (10 * 0.0001)  # 10 pips below FVG
            else:
                # For SHORT: SL above 1H CHoCH high
                radar_1h_fvg_top = setup.get('radar_1h_fvg_top', radar_1h_fvg_entry)
                sniper_sl = radar_1h_fvg_top + (10 * 0.0001)  # 10 pips above FVG
            
            # Use config option for SL (default: use sniper SL)
            use_sniper_sl = self.pullback_config.get('use_1h_sl', True)
            
            if use_sniper_sl:
                stop_loss = sniper_sl
                logger.info(f"   🎯 Using SNIPER SL: {stop_loss:.5f} (1H CHoCH + 10 pips)")
            else:
                stop_loss = setup.get('stop_loss')
                logger.info(f"   📊 Using DAILY SL: {stop_loss:.5f}")
            
            return {
                'action': 'EXECUTE_ENTRY1',
                'entry_price': radar_1h_fvg_entry,
                'stop_loss': stop_loss,
                'reason': f'SNIPER ENTRY: Price in 1H FVG ({zone_type} zone validated)',
                'entry_type': 'SNIPER_1H',
                'choch_timestamp': setup.get('radar_1h_choch_time'),
                'fibo_data': {}  # Not used in radar mode
            }
        
        elif radar_4h_in_fvg and radar_4h_fvg_entry and radar_4h_choch_price:
            # Validate Premium/Discount zone for 4H
            if direction == 'buy':
                zone_valid = radar_4h_fvg_entry < radar_4h_choch_price
                zone_type = "DISCOUNT"
            else:
                zone_valid = radar_4h_fvg_entry > radar_4h_choch_price
                zone_type = "PREMIUM"
            
            if not zone_valid:
                logger.warning(f"⚠️  {symbol}: 4H FVG not in {zone_type} zone - skipping entry")
                return {
                    'action': 'KEEP_MONITORING',
                    'reason': f'4H FVG not in {zone_type} zone (invalid setup)'
                }
            
            # 💎 EXECUTE HIGH CONFIDENCE ENTRY (4H FVG)
            logger.success(f"💎 {symbol}: HIGH CONFIDENCE ENTRY! Price in 4H FVG @ {radar_4h_fvg_entry:.5f}")
            
            # Calculate 4H SL (10 pips from 4H CHoCH swing)
            if direction == 'buy':
                radar_4h_fvg_bottom = setup.get('radar_4h_fvg_bottom', radar_4h_fvg_entry)
                sniper_sl = radar_4h_fvg_bottom - (10 * 0.0001)
            else:
                radar_4h_fvg_top = setup.get('radar_4h_fvg_top', radar_4h_fvg_entry)
                sniper_sl = radar_4h_fvg_top + (10 * 0.0001)
            
            use_sniper_sl = self.pullback_config.get('use_4h_sl', True)
            
            if use_sniper_sl:
                stop_loss = sniper_sl
                logger.info(f"   💎 Using 4H SL: {stop_loss:.5f} (4H CHoCH + 10 pips)")
            else:
                stop_loss = setup.get('stop_loss')
                logger.info(f"   📊 Using DAILY SL: {stop_loss:.5f}")
            
            return {
                'action': 'EXECUTE_ENTRY1',  # Or EXECUTE_ENTRY2 if Entry1 already filled
                'entry_price': radar_4h_fvg_entry,
                'stop_loss': stop_loss,
                'reason': f'HIGH CONFIDENCE: Price in 4H FVG ({zone_type} zone validated)',
                'entry_type': 'HIGH_CONFIDENCE_4H',
                'choch_timestamp': setup.get('radar_4h_choch_time'),
                'fibo_data': {}
            }
        
        else:
            # Not in FVG yet - keep monitoring
            radar_1h_distance = setup.get('radar_1h_distance_pips', 999)
            radar_4h_distance = setup.get('radar_4h_distance_pips', 999)
            
            if radar_1h_distance < radar_4h_distance:
                reason = f'Waiting for 1H pullback ({radar_1h_distance:.1f} pips away)'
            else:
                reason = f'Waiting for 4H pullback ({radar_4h_distance:.1f} pips away)'
            
            return {
                'action': 'KEEP_MONITORING',
                'reason': reason
            }
    
    def _check_pullback_entry(self, setup: dict, df_h1, symbol: str) -> dict:
        """
        V2.1 IMMEDIATE ENTRY LOGIC (for XAUUSD and fast-moving assets)
        
        Flow:
        1. Detect 1H CHoCH in FVG zone
        2. Execute entry immediately at CHoCH confirmation
        3. SL at FVG edge (simple, no pullback waiting)
        
        No pullback waiting, no continuation checks, no timeouts.
        Optimized for high volatility assets like Gold.
        """
        direction = setup['direction']
        fvg_top = setup.get('fvg_zone_top', 0)
        fvg_bottom = setup.get('fvg_zone_bottom', 0)
        
        # Check if already detected CHoCH
        choch_detected = setup.get('choch_1h_detected', False)
        
        if choch_detected:
            # CHoCH already detected, execute immediately
            return {
                'action': 'EXECUTE_ENTRY1',
                'reason': f'V2.1 Immediate entry at 1H CHoCH (use_immediate_entry=true)',
                'entry_type': 'immediate_choch',
                'choch_detected': True
            }
        
        # ========== DETECT 1H CHoCH ==========
        choch_list = self.smc_detector.detect_choch(df_h1)
        
        if not choch_list:
            return {
                'action': 'KEEP_MONITORING',
                'reason': 'No 1H CHoCH detected yet (immediate entry mode)'
            }
        
        # Find most recent CHoCH matching direction and in FVG zone
        matching_choch = None
        for choch in reversed(choch_list):
            choch_direction = 'buy' if choch['type'] == 'bullish_choch' else 'sell'
            choch_price = choch['price']
            
            # Verify CHoCH is in FVG zone
            in_fvg = fvg_bottom <= choch_price <= fvg_top
            
            if choch_direction == direction and in_fvg:
                matching_choch = choch
                break
        
        if not matching_choch:
            return {
                'action': 'KEEP_MONITORING',
                'reason': 'No CHoCH matching direction in FVG zone (immediate entry mode)'
            }
        
        # CHoCH detected! Execute immediately (V2.1 style)
        logger.success(f"✅ {symbol} V2.1 IMMEDIATE ENTRY: 1H CHoCH detected at {matching_choch['price']}, executing NOW")
        
        return {
            'action': 'EXECUTE_ENTRY1',
            'reason': f"V2.1 Immediate entry: 1H {matching_choch['type']} at {matching_choch['price']}",
            'entry_type': 'immediate_choch',
            'choch_data': matching_choch,
            'choch_detected': True,
            'choch_timestamp': datetime.now().isoformat()
        }
    
    def _check_pullback_entry(self, setup: dict, df_h1, symbol: str) -> dict:
        """
        V3.3 HYBRID ENTRY: Pullback OR Continuation
        
        Flow:
        1. Check if CHoCH already detected (stored in setup)
        2. If not, detect 1H CHoCH in FVG zone
        3. Calculate Fibonacci 50% from CHoCH swing
        4. Check if current price within tolerance of Fibo 50%
        5. If YES → EXECUTE_ENTRY1 (optimal pullback entry)
        6. If NO (after 6h) → Check continuation momentum
           - If strong momentum → EXECUTE_ENTRY1_CONTINUATION
           - If weak momentum → KEEP_MONITORING
        7. If timeout (12h) → Force entry or skip based on distance
        """
        # V4.0: Import datetime at function start to avoid UnboundLocalError
        from datetime import datetime
        
        # ========== CHECK FOR IMMEDIATE ENTRY MODE ==========
        pair_config = self.get_pair_config(symbol)
        if pair_config.get('use_immediate_entry', False):
            logger.debug(f"🚀 {symbol}: use_immediate_entry=true, using immediate entry logic")
            return self._immediate_entry_at_choch(setup, df_h1, symbol)
        
        # ========== STANDARD V3.3 HYBRID ENTRY LOGIC ==========
        direction = setup['direction']  # 'buy' or 'sell'
        fvg_top = setup.get('fvg_zone_top', 0)
        fvg_bottom = setup.get('fvg_zone_bottom', 0)
        
        # Check if CHoCH already detected
        choch_detected = setup.get('choch_1h_detected', False)
        choch_timestamp = setup.get('choch_1h_timestamp')
        fibo_data = setup.get('fibo_data')
        
        if not choch_detected:
            # ========== STEP 1: DETECT 1H CHoCH OR SWING BREAK ==========
            # For REVERSAL setups after Daily CHoCH, 1H may show BOS (continuation) not CHoCH
            # We accept ANY swing break in trade direction within FVG zone
            chochs, bos_list = self.smc_detector.detect_choch_and_bos(df_h1)
            
            # Combine CHoCH and BOS for unified structure break detection
            all_breaks = chochs + bos_list
            
            if not all_breaks:
                return {
                    'action': 'KEEP_MONITORING',
                    'reason': 'No 1H structure break detected yet'
                }
            
            # Find most recent break matching direction and in FVG zone
            matching_break = None
            for break_obj in reversed(all_breaks):
                break_price = break_obj.break_price
                break_direction = break_obj.direction
                break_idx = break_obj.index
                
                # CRITICAL: Verify candle has CLOSED confirming break (not just wick touch)
                close_price = df_h1['close'].iloc[break_idx]
                
                # For bullish: Close must be above break price
                # For bearish: Close must be below break price
                candle_closed_confirmation = (
                    (break_direction == 'bullish' and close_price > break_price) or
                    (break_direction == 'bearish' and close_price < break_price)
                )
                
                if not candle_closed_confirmation:
                    logger.debug(f"   ⚠️ {symbol}: Break at {break_price:.5f} rejected - wick only (Close: {close_price:.5f})")
                    continue
                
                # Check if break is in FVG zone
                in_fvg = fvg_bottom <= break_price <= fvg_top
                
                # Check if direction matches
                direction_match = (
                    (direction == 'buy' and break_direction == 'bullish') or
                    (direction == 'sell' and break_direction == 'bearish')
                )
                
                if in_fvg and direction_match:
                    matching_break = break_obj
                    break_type = "CHoCH" if break_obj in chochs else "BOS"
                    logger.info(f"   ✅ {symbol}: {break_type} CONFIRMED with body closure at {break_price:.5f} (Close: {close_price:.5f})")
                    break
            
            if not matching_break:
                return {
                    'action': 'KEEP_MONITORING',
                    'reason': f'No {direction} CHoCH/BOS in FVG zone yet'
                }
            
            # Structure break found! Calculate Fibonacci (V4.0 Multi-Timeframe)
            break_idx = matching_break.index
            break_timestamp = df_h1.index[break_idx]
            break_price = matching_break.break_price
            
            # V4.0: Get 4H and Daily data for REVERSAL strategies
            strategy_type = setup.get('strategy_type', 'continuation')
            
            # Fetch 4H and Daily data if needed for REVERSAL
            df_4h_fibo = None
            df_daily_fibo = None
            if strategy_type == 'reversal':
                try:
                    df_4h_fibo = self.data_provider.get_historical_data(symbol, "H4", 225)
                    df_daily_fibo = self.data_provider.get_historical_data(symbol, "D1", 100)
                except Exception as e:
                    logger.warning(f"   ⚠️ {symbol}: Could not fetch 4H/Daily for Fibonacci (fallback to 1H): {e}")
            
            fibo_data = calculate_choch_fibonacci(
                df_h1=df_h1,
                choch_idx=break_idx,
                direction='bullish' if direction == 'buy' else 'bearish',
                df_4h=df_4h_fibo,
                df_daily=df_daily_fibo,
                strategy_type=strategy_type,
                symbol=symbol
            )
            
            fibo_tf = fibo_data.get('fibo_timeframe', '1H')
            logger.info(f"   📊 {symbol}: Fibo 50%: {fibo_data['fibo_50']:.5f}, Range: {fibo_data['swing_range']:.1f} pips (from {fibo_tf} swing)")
            
            # Save structure break detection and continue monitoring for pullback
            setup['choch_1h_detected'] = True
            # V4.3 FIX: Ensure timestamp is always valid ISO format
            if hasattr(break_timestamp, 'isoformat'):
                setup['choch_1h_timestamp'] = break_timestamp.isoformat()
            elif isinstance(break_timestamp, str) and break_timestamp.startswith('20'):
                setup['choch_1h_timestamp'] = break_timestamp
            else:
                # Fallback: use current time if timestamp invalid
                setup['choch_1h_timestamp'] = datetime.now().isoformat()
                logger.warning(f"⚠️  {symbol}: Invalid break_timestamp type ({type(break_timestamp)}), using current time")
            setup['fibo_data'] = fibo_data
            
            logger.info(f"   ⏳ {symbol}: Waiting for pullback to Fibo 50% @ {fibo_data['fibo_50']:.5f}")
            
            # Don't execute yet - fall through to pullback validation below
            choch_detected = True
        
        # ========== STEP 2: VALIDATE PULLBACK TO FIBONACCI 50% ==========
        if choch_detected and fibo_data:
            # V4.3 FIX-007: Use HIGH for SELL pullback detection, LOW for BUY
            # SELL waits for pullback UP → check if HIGH touched Fibo 50%
            # BUY waits for pullback DOWN → check if LOW touched Fibo 50%
            
            fibo_50 = fibo_data['fibo_50']
            tolerance_pips = self.pullback_config['tolerance_pips']
            
            # V4.3 FIX-012: Use percentage-based tolerance for crypto (BTC, ETH, etc.)
            # Forex: 0.0001 * 50 pips = 0.005 (~5 pips tolerance)
            # Crypto: 1% of price (~$680 tolerance for BTC at $68,000)
            if 'BTC' in symbol.upper() or 'ETH' in symbol.upper() or 'CRYPTO' in symbol.upper():
                tolerance = fibo_50 * 0.01  # 1% tolerance for crypto
                logger.debug(f"   💰 {symbol}: Using 1% tolerance for crypto = ${tolerance:.2f}")
            elif 'JPY' in symbol.upper():
                tolerance = 0.01 * tolerance_pips  # JPY uses 2 decimals
            else:
                tolerance = 0.0001 * tolerance_pips  # Standard forex (4 decimals)
            
            # V4.3 FIX-011: Check fibo_timeframe to scan correct timeframe
            # If Fibo calculated from 4H swing → scan 4H candles
            # If Fibo calculated from 1H swing → scan 1H candles
            fibo_tf = fibo_data.get('fibo_timeframe', '1H')
            
            if fibo_tf == '4H' or fibo_tf == 'H4':
                # Fetch 4H data and scan last 20 4H candles
                try:
                    df_scan = self.data_provider.get_historical_data(symbol, "H4", 225)
                    last_candles = df_scan.tail(20)
                    logger.debug(f"   🔍 {symbol}: Scanning last 20 4H candles for pullback (Fibo from 4H swing)")
                except Exception as e:
                    logger.error(f"   ❌ {symbol}: Failed to fetch 4H data for pullback scan: {e}")
                    return {'action': 'KEEP_MONITORING', 'reason': 'Failed to fetch 4H data'}
            elif fibo_tf == 'D1' or fibo_tf == 'Daily':
                # Fetch Daily data and scan last 20 Daily candles
                try:
                    df_scan = self.data_provider.get_historical_data(symbol, "D1", 100)
                    last_candles = df_scan.tail(20)
                    logger.debug(f"   🔍 {symbol}: Scanning last 20 Daily candles for pullback (Fibo from Daily swing)")
                except Exception as e:
                    logger.error(f"   ❌ {symbol}: Failed to fetch Daily data for pullback scan: {e}")
                    return {'action': 'KEEP_MONITORING', 'reason': 'Failed to fetch Daily data'}
            else:
                # Default: scan 1H candles
                last_candles = df_h1.tail(20)
                logger.debug(f"   🔍 {symbol}: Scanning last 20 1H candles for pullback (Fibo from 1H swing)")
            
            # V4.3 FIX-009: Scan last 20 candles for HIGH/LOW touch
            pullback_detected = False
            touch_price = None
            
            if direction == 'sell':
                # For SELL: check if any HIGH in last 20 candles touched Fibo 50%
                for idx, candle in last_candles.iterrows():
                    price_diff = abs(candle['high'] - fibo_50)
                    if price_diff <= tolerance:
                        pullback_detected = True
                        touch_price = candle['high']
                        logger.success(f"   🎯 {symbol}: SELL pullback detected on {fibo_tf}! HIGH {touch_price:.5f} touched Fibo 50% {fibo_50:.5f}")
                        break
            else:
                # For BUY: check if any LOW in last 20 candles touched Fibo 50%
                for idx, candle in last_candles.iterrows():
                    price_diff = abs(candle['low'] - fibo_50)
                    if price_diff <= tolerance:
                        pullback_detected = True
                        touch_price = candle['low']
                        logger.success(f"   🎯 {symbol}: BUY pullback detected on {fibo_tf}! LOW {touch_price:.5f} touched Fibo 50% {fibo_50:.5f}")
                        break
            
            if pullback_detected:
                # Calculate SL based on swing
                # V4.4 FIX-014: Crypto SL buffer (use percentage instead of pips)
                if 'BTC' in symbol.upper() or 'ETH' in symbol.upper() or 'CRYPTO' in symbol.upper():
                    sl_buffer = fibo_50 * 0.005  # 0.5% buffer for crypto (~$340 for BTC at $68k)
                elif 'JPY' in symbol.upper():
                    sl_buffer = 0.01 * self.pullback_config['sl_buffer_pips']
                else:
                    sl_buffer = 0.0001 * self.pullback_config['sl_buffer_pips']
                
                if direction == 'buy':
                    sl_price = fibo_data['swing_low'] - sl_buffer
                else:
                    sl_price = fibo_data['swing_high'] + sl_buffer
                
                # V4.3 FIX-008: Use Fibo 50% as entry price (not HIGH/LOW which might be wick)
                entry_execution_price = fibo_50
                
                # Calculate pip difference for logging
                price_diff = abs(touch_price - fibo_50)
                
                # V4.4 FIX-013: Crypto pip calculation (1 pip = $1)
                if 'BTC' in symbol.upper() or 'ETH' in symbol.upper() or 'CRYPTO' in symbol.upper():
                    pips_display = price_diff
                elif 'JPY' in symbol.upper():
                    pips_display = price_diff * 100
                else:
                    pips_display = price_diff * 10000
                
                # 🔥 AGGRESSIVE LOGGING
                logger.critical(f"🔥 TRIGGER: {symbol} confirmed CHoCH + Pullback. Pushing to Executor NOW!")
                logger.success(f"   🎯 {symbol}: Pullback reached! Entry @ {entry_execution_price:.5f} (Fibo 50%: {fibo_50:.5f}, Touch: {touch_price:.5f})")
                logger.warning(f"   ⚡ INSTANT WRITE TO signals.json - NO DELAY!")
                
                return {
                    'action': 'EXECUTE_ENTRY1',
                    'entry_price': entry_execution_price,
                    'stop_loss': sl_price,
                    'choch_timestamp': (choch_timestamp if isinstance(choch_timestamp, str) else choch_timestamp.isoformat()) if choch_timestamp else datetime.now().isoformat(),
                    'fibo_data': fibo_data,
                    'reason': f'🔥 INSTANT: CHoCH + Pullback confirmed (diff: {pips_display:.1f} pips)'
                }
            else:
                # V4.3 FIX-010: Define current_price for logging (use close price as reference)
                current_price = df_h1.iloc[-1]['close']
                price_diff = abs(current_price - fibo_50)
                
                # V4.0 FIX-003: MOMENTUM ENTRY after 6H (if pullback not reached)
                # Safety check: choch_timestamp might not be set or invalid for old setups
                if choch_timestamp is None or (isinstance(choch_timestamp, str) and not choch_timestamp.startswith('20')):
                    # Fallback: use setup_time as reference (less accurate but safe)
                    # Handles: None, numeric strings like "217", or invalid formats
                    setup_time_str = setup.get('setup_time', datetime.now().isoformat())
                    reference_time = datetime.fromisoformat(setup_time_str) if isinstance(setup_time_str, str) else setup_time_str
                    hours_elapsed = (datetime.now() - reference_time).total_seconds() / 3600
                    logger.warning(f"⚠️  {symbol}: CHoCH timestamp invalid/missing (value: {choch_timestamp}) - using setup_time as reference ({hours_elapsed:.1f}H elapsed)")
                else:
                    # Normal flow: use CHoCH detection time
                    try:
                        choch_time = datetime.fromisoformat(choch_timestamp) if isinstance(choch_timestamp, str) else choch_timestamp
                        hours_elapsed = (datetime.now() - choch_time).total_seconds() / 3600
                    except (ValueError, TypeError) as e:
                        # Extra safety: if fromisoformat fails, use setup_time
                        logger.error(f"❌ {symbol}: Failed to parse CHoCH timestamp '{choch_timestamp}': {e}")
                        setup_time_str = setup.get('setup_time', datetime.now().isoformat())
                        reference_time = datetime.fromisoformat(setup_time_str) if isinstance(setup_time_str, str) else setup_time_str
                        hours_elapsed = (datetime.now() - reference_time).total_seconds() / 3600
                
                # V4.0 FIX-005: Detect JPY pairs and CRYPTO for correct pip calculation
                if 'BTC' in symbol.upper() or 'ETH' in symbol.upper() or 'CRYPTO' in symbol.upper():
                    distance_pips = price_diff  # Crypto: 1 pip = $1
                elif 'JPY' in symbol.upper():
                    distance_pips = price_diff * 100
                else:
                    distance_pips = price_diff * 10000
                
                logger.info(f"   ⏳ {symbol}: Waiting for pullback - current: {current_price:.5f}, target: {fibo_50:.5f} (diff: {distance_pips:.1f} pips, elapsed: {hours_elapsed:.1f}H)")
                
                # ========== V4.0 STEP 3: CONTINUATION MOMENTUM ENTRY (After 6H) ==========
                if hours_elapsed >= 6:
                    logger.debug(f"⏱️  {symbol}: {hours_elapsed:.1f}H elapsed since CHoCH, checking momentum entry...")
                    
                    # Check if price still moving in trade direction
                    last_5_candles = df_h1.tail(5)
                    
                    # Calculate momentum score
                    if direction == 'buy':
                        momentum_strong = (
                            current_price > last_5_candles['close'].mean() and
                            last_5_candles['close'].iloc[-1] > last_5_candles['close'].iloc[0]
                        )
                        price_beyond_target = current_price > fibo_50
                    else:
                        momentum_strong = (
                            current_price < last_5_candles['close'].mean() and
                            last_5_candles['close'].iloc[-1] < last_5_candles['close'].iloc[0]
                        )
                        price_beyond_target = current_price < fibo_50
                    
                    # Check if price within REASONABLE distance
                    # V4.4 FIX-015: Crypto uses dollar-based tolerance ($1000), Forex uses pips
                    if 'BTC' in symbol.upper() or 'ETH' in symbol.upper() or 'CRYPTO' in symbol.upper():
                        max_distance = 1000  # $1000 tolerance for crypto
                    elif 'JPY' in symbol.upper():
                        max_distance = 200
                    else:
                        max_distance = 100
                    
                    within_reasonable_distance = distance_pips <= max_distance
                    
                    if momentum_strong and price_beyond_target and within_reasonable_distance:
                        logger.success(f"🚀 {symbol}: Continuation momentum entry triggered!")
                        
                        # Use swing-based SL (from fibo_data)
                        # V4.4 FIX-016: Crypto SL buffer uses percentage
                        if 'BTC' in symbol.upper() or 'ETH' in symbol.upper() or 'CRYPTO' in symbol.upper():
                            sl_buffer = current_price * 0.005  # 0.5% buffer for crypto
                        elif 'JPY' in symbol.upper():
                            sl_buffer = 0.01 * self.pullback_config['sl_buffer_pips']
                        else:
                            sl_buffer = 0.0001 * self.pullback_config['sl_buffer_pips']
                        
                        if direction == 'buy':
                            sl_price = fibo_data['swing_low'] - sl_buffer
                        else:
                            sl_price = fibo_data['swing_high'] + sl_buffer
                        
                        return {
                            'action': 'EXECUTE_ENTRY1_CONTINUATION',
                            'entry_price': current_price,
                            'stop_loss': sl_price,
                            'choch_timestamp': (choch_timestamp if isinstance(choch_timestamp, str) else choch_timestamp.isoformat()) if choch_timestamp else datetime.now().isoformat(),
                            'fibo_data': fibo_data,
                            'reason': f'Continuation momentum after {hours_elapsed:.1f}H (distance: {distance_pips:.1f} pips)'
                        }
                    else:
                        logger.debug(f"⏳ {symbol}: Momentum not strong enough - keep waiting...")
                        logger.debug(f"   Strong momentum: {momentum_strong}, Beyond target: {price_beyond_target}, Within range: {within_reasonable_distance}")
                
                # ========== V4.0 STEP 4: TIMEOUT ENTRY (After 12H) ==========
                if hours_elapsed >= 12:
                    logger.warning(f"⏰ {symbol}: 12H timeout reached - evaluating force entry...")
                    
                    # V4.4 FIX-017: Crypto timeout uses dollar-based tolerance
                    if 'BTC' in symbol.upper() or 'ETH' in symbol.upper() or 'CRYPTO' in symbol.upper():
                        max_timeout_distance = 2000  # $2000 tolerance for crypto timeout
                    elif 'JPY' in symbol.upper():
                        max_timeout_distance = 300
                    else:
                        max_timeout_distance = 200
                    
                    if distance_pips <= max_timeout_distance:
                        logger.success(f"✅ {symbol}: Force entry at {current_price:.5f} (timeout, {distance_pips:.1f} pips from target)")
                        
                        # Use original SL from setup
                        sl_price = setup.get('stop_loss', fibo_data['swing_high'] if direction == 'sell' else fibo_data['swing_low'])
                        
                        return {
                            'action': 'EXECUTE_ENTRY1_TIMEOUT',
                            'entry_price': current_price,
                            'stop_loss': sl_price,
                            'choch_timestamp': (choch_timestamp if isinstance(choch_timestamp, str) else choch_timestamp.isoformat()) if choch_timestamp else datetime.now().isoformat(),
                            'fibo_data': fibo_data,
                            'reason': f'Timeout entry after 12H (distance: {distance_pips:.1f} pips)'
                        }
                    else:
                        # Too far → skip setup
                        logger.error(f"❌ {symbol}: Timeout but too far from target ({distance_pips:.1f} pips) - skipping setup")
                        return {
                            'action': 'SKIP_SETUP',
                            'reason': f'Timeout + distance too large ({distance_pips:.1f} pips)'
                        }
                
                # Still within 6H → keep monitoring normally
                return {
                    'action': 'KEEP_MONITORING',
                    'reason': f'Waiting for pullback to Fibo 50% (diff: {distance_pips:.1f} pips, {hours_elapsed:.1f}H elapsed)'
                }
        
        # Should not reach here
        return {
            'action': 'KEEP_MONITORING',
            'reason': 'CHoCH detected but waiting for pullback validation'
        }
    
    def _symbol_already_at_broker(self, symbol: str) -> bool:
        """
        🛡️ V7.1 DUPLICATE GUARD + V9.1 FRESHNESS CHECK (R7 AUDIT FIX by POCOVNICU)
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
            
            with open(active_pos_file, 'r') as f:
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

    def _cleanup_monitoring_setups(self):
        """
        🧹 V9.1 AUTO-CLEANUP: Remove EXPIRED/CLOSED/CANCELLED setups from monitoring_setups.json
        R6 AUDIT FIX by POCOVNICU — Prevents infinite file growth
        """
        if not self.monitoring_file.exists():
            return
        
        try:
            with open(self.monitoring_file, 'r') as f:
                data = json.load(f)
            
            if isinstance(data, dict):
                setups = data.get('setups', [])
            elif isinstance(data, list):
                setups = data
            else:
                return
            
            dead_statuses = {'EXPIRED', 'CLOSED', 'CANCELLED', 'FAILED'}
            active_setups = [s for s in setups if s.get('status', '') not in dead_statuses]
            removed_count = len(setups) - len(active_setups)
            
            if removed_count > 0:
                # Write cleaned data back
                if isinstance(data, dict):
                    data['setups'] = active_setups
                    write_data = data
                else:
                    write_data = active_setups
                
                with open(self.monitoring_file, 'w') as f:
                    json.dump(write_data, f, indent=2, default=str)
                
                logger.success(f"🧹 R6 CLEANUP: Removed {removed_count} dead setups from monitoring_setups.json ({len(setups)}→{len(active_setups)})")
        except Exception as e:
            logger.error(f"⚠️  Cleanup monitoring_setups failed: {e}")
    
    def _process_monitoring_setups(self):
        """
        Process all setups in monitoring_setups.json using V3.2 PULLBACK + SCALE_IN.
        
        V3.2 PULLBACK FLOW:
        1. Load setup from monitoring_setups.json
        2. Fetch current market data (Daily, 4H, 1H)
        3. Check if 1H CHoCH detected → calculate Fibonacci 50%
        4. Check if pullback to Fibo 50% reached → EXECUTE ENTRY1
        5. If timeout (24h) → force entry or skip based on config
        6. After Entry1 filled → wait for 4H CHoCH for Entry2 (same as V3.1)
        """
        if not self.monitoring_file.exists():
            return
        
        try:
            with open(self.monitoring_file, 'r') as f:
                data = json.load(f)
                setups = data.get('setups', [])
            
            if not setups:
                return
            
            logger.debug(f"📊 Checking {len(setups)} monitoring setups...")
            
            # 🚀 DYNAMIC FREQUENCY: Count how many setups are "IN ZONE" (CHoCH detected + close to entry)
            in_zone_count = 0
            for s in setups:
                if s.get('status') in ['MONITORING', 'READY'] and s.get('choch_1h_detected', False):
                    in_zone_count += 1
            
            if in_zone_count > 0:
                # ⚡ AGGRESSIVE MODE: Setups in zone → check every 5 seconds
                self.check_interval = 5
                logger.warning(f"⚡ AGGRESSIVE MODE: {in_zone_count} setups IN ZONE → 5s interval")
            else:
                # 🔄 NORMAL MODE: No setups close → check every 30s to save resources
                self.check_interval = 30
                logger.debug(f"🔄 Normal monitoring: 30s interval")
            
            updated = False
            
            for i, setup in enumerate(setups):
                symbol = setup['symbol']
                status = setup.get('status', 'MONITORING')
                
                # Skip expired or closed setups, but ALLOW READY for immediate execution
                if status not in ['MONITORING', 'READY']:
                    continue
                
                # 🔥 IN-ZONE INDICATOR
                # V3.2: choch_1h_detected (Fibo 50% logic)
                # V3.3: radar_1h_choch_detected (SNIPER MODE with FVG)
                in_zone = setup.get('choch_1h_detected', False) or setup.get('radar_1h_choch_detected', False)
                zone_emoji = "🎯" if in_zone else "🔍"
                logger.debug(f"{zone_emoji} Processing {symbol} (in_zone={in_zone})")
                
                try:
                    # Fetch market data
                    df_daily = self.data_provider.get_historical_data(symbol, "D1", 100)
                    df_4h = self.data_provider.get_historical_data(symbol, "H4", 225)
                    df_1h = self.data_provider.get_historical_data(symbol, "H1", 225)
                    
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
                            setups[i]['status'] = 'ACTIVE'
                            setups[i]['entry1_filled'] = True
                            setups[i]['force_executed'] = True
                            setups[i]['skip_reason'] = 'duplicate_guard_broker_position_exists'
                            updated = True
                            continue
                        
                        logger.success(f"🚀 EXECUTING {symbol} (status: READY, forced by owner)")
                        
                        success = self.executor.execute_trade(
                            symbol=symbol,
                            direction=setup['direction'],
                            entry_price=setup['entry_price'],
                            stop_loss=setup['stop_loss'],
                            take_profit=setup['take_profit'],
                            lot_size=0.01,  # Will be recalculated by Risk Manager
                            comment=f"Entry 1 - Forced execution",
                            status='READY'  # Force bypass status check in executor
                        )
                        
                        if success:
                            setups[i]['entry1_filled'] = True
                            setups[i]['entry1_price'] = setup['entry_price']
                            setups[i]['entry1_time'] = datetime.now().isoformat()
                            setups[i]['status'] = 'ACTIVE'
                            setups[i]['force_executed'] = True
                            updated = True
                            logger.success(f"✅ {symbol} Entry 1 executed successfully (forced)")
                        else:
                            logger.error(f"❌ {symbol} Entry 1 execution failed (rejected by Risk Manager)")
                        
                        continue  # Skip pullback logic for READY status
                    
                    if not entry1_filled:
                        # ========== V3.3 SNIPER ENTRY LOGIC (RADAR-ENHANCED) ==========
                        # Priority 1: Use 1H FVG from radar (if available)
                        # Priority 2: Fall back to V3.2 Pullback Strategy (Fibo 50%)
                        
                        use_radar_data = setup.get('radar_1h_choch_detected', False)
                        logger.debug(f"🔍 {symbol}: Entry 1 logic - use_radar_data={use_radar_data}")
                        
                        if use_radar_data:
                            # 🎯 SNIPER MODE: Use 1H FVG from multi_tf_radar.py
                            logger.info(f"🎯 {symbol}: SNIPER MODE activated - checking radar data...")
                            result = self._check_radar_entry(setup, df_1h, symbol)
                        else:
                            # 🔄 FALLBACK: Use V3.2 Pullback Strategy (Fibo 50%)
                            logger.info(f"🔄 {symbol}: FALLBACK MODE - using Fibo 50% logic...")
                            result = self._check_pullback_entry(setup, df_1h, symbol)
                        
                        if result['action'] == 'CHOCH_1H_DETECTED':
                            # 🔔 1H CHoCH just detected - Update setup and RESEND notification
                            setups[i]['choch_1h_detected'] = True
                            setups[i]['choch_1h_timestamp'] = result.get('choch_timestamp')
                            setups[i]['fibo_data'] = result.get('fibo_data', {})
                            setups[i]['choch_1h_price'] = result.get('choch_price')
                            updated = True
                            
                            # 📱 RESEND setup notification with 1H CHoCH status
                            try:
                                # Recreate TradeSetup with h1_choch
                                h1_choch_obj = CHoCH(
                                    index=0,  # Not critical for notification
                                    direction='bullish' if setup['direction'] == 'buy' else 'bearish',
                                    break_price=result.get('choch_price'),
                                    previous_trend='bearish' if setup['direction'] == 'buy' else 'bullish',
                                    candle_time=result.get('choch_timestamp'),
                                    swing_broken=None
                                )
                                
                                # Create minimal TradeSetup for notification
                                notification_setup = TradeSetup(
                                    symbol=symbol,
                                    daily_choch=CHoCH(
                                        index=0,
                                        direction='bullish' if setup['direction'] == 'buy' else 'bearish',
                                        break_price=setup.get('entry_price', 0),
                                        previous_trend='',
                                        candle_time=datetime.now(),
                                        swing_broken=None
                                    ),
                                    fvg=FVG(
                                        index=0,
                                        direction='bullish' if setup['direction'] == 'buy' else 'bearish',
                                        top=setup.get('fvg_zone_top', 0),
                                        bottom=setup.get('fvg_zone_bottom', 0),
                                        middle=(setup.get('fvg_zone_top', 0) + setup.get('fvg_zone_bottom', 0)) / 2,
                                        candle_time=datetime.now()
                                    ),
                                    h4_choch=None,
                                    h1_choch=h1_choch_obj,  # ← 1H CHoCH detected!
                                    entry_price=setup.get('entry_price', 0),
                                    stop_loss=setup.get('stop_loss', 0),
                                    take_profit=setup.get('take_profit', 0),
                                    risk_reward=setup.get('risk_reward', 0),
                                    setup_time=datetime.now(),
                                    priority=1,
                                    strategy_type=setup.get('strategy_type', 'reversal'),
                                    status='MONITORING'
                                )
                                
                                # 🛡️ V3.8 ANTI-SPAM: Check debouncer before sending
                                signal_id = f"{symbol}_{setup['direction']}_{setup.get('entry_price', 0)}"
                                
                                # Skip if duplicate signal already processed
                                if self.signal_cache.is_processed(signal_id):
                                    logger.warning(f"🚫 SKIP: {symbol} signal already processed (cache hit)")
                                    continue
                                
                                # Check Telegram debouncer (5 min cooldown)
                                if not self.telegram_debouncer.should_send(
                                    symbol, 
                                    "setup_alert_1h_choch", 
                                    str(setup.get('entry_price', 0))
                                ):
                                    logger.warning(f"🔕 DEBOUNCED: {symbol} setup alert (sent recently)")
                                    continue
                                
                                # Send updated setup notification (need df_daily and df_4h for charts)
                                self.telegram.send_setup_alert(notification_setup, df_daily, df_4h)
                                logger.success(f"📱 Resent setup notification for {symbol} with 1H CHoCH status ✅")
                                
                                # 🛡️ Mark signal as processed in persistent cache
                                self.signal_cache.mark_processed(signal_id)
                                logger.debug(f"💾 Signal cached: {signal_id}")
                            except Exception as tel_error:
                                logger.warning(f"⚠️ Failed to resend setup notification: {tel_error}")
                            
                            continue  # Skip to next iteration to wait for pullback
                        
                        # V4.0: Handle all execution action types
                        if result['action'] in ['EXECUTE_ENTRY1', 'EXECUTE_ENTRY1_CONTINUATION', 'EXECUTE_ENTRY1_TIMEOUT']:
                            # 🛡️ V3.8 ANTI-SPAM: Check if this execution was already triggered
                            execution_id = f"{symbol}_execute_{result['entry_price']:.5f}"
                            
                            if self.signal_cache.is_processed(execution_id):
                                logger.warning(f"🚫 SKIP EXECUTION: {symbol} already executed (cache hit)")
                                continue
                            
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
                            
                            if success:
                                logger.critical(f"✅ {symbol} SIGNAL WRITTEN TO signals.json - cTrader will execute in <10s!")
                                
                                # 🛡️ Mark execution as processed in persistent cache
                                self.signal_cache.mark_processed(execution_id)
                                logger.debug(f"💾 Execution cached: {execution_id}")
                                
                                # Update setup with Entry 1 details and pullback data
                                setups[i]['entry1_filled'] = True
                                setups[i]['entry1_price'] = result['entry_price']
                                setups[i]['entry1_time'] = datetime.now().isoformat()
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
                        
                        elif result['action'] == 'TIMEOUT_FORCE_ENTRY':
                            # Timeout exceeded - force entry at current price
                            current_price = df_1h.iloc[-1]['close']
                            success = self._execute_entry(
                                setup=setup,
                                entry_number=1,
                                entry_price=current_price,
                                stop_loss=result['stop_loss'],
                                take_profit=setup['take_profit'],
                                position_size=self.execution_strategy.get('entry1_position_size', 0.5)
                            )
                            
                            if success:
                                setups[i]['entry1_filled'] = True
                                setups[i]['entry1_price'] = current_price
                                setups[i]['entry1_time'] = datetime.now().isoformat()
                                setups[i]['entry1_lots'] = self.execution_strategy.get('entry1_position_size', 0.5)
                                setups[i]['pullback_status'] = 'TIMEOUT_FORCED_ENTRY'
                                updated = True
                                logger.warning(f"⏰ Timeout - forced entry for {symbol} at {current_price}")
                        
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
                        # ========== ENTRY 1 FILLED - CHECK FOR ENTRY 2 (V3.1 LOGIC) ==========
                        from types import SimpleNamespace
                        setup_obj = SimpleNamespace(**setup)
                        
                        # Convert times
                        if isinstance(setup.get('setup_time'), str):
                            setup_obj.setup_time = datetime.fromisoformat(setup['setup_time'])
                        if setup.get('entry1_time') and isinstance(setup['entry1_time'], str):
                            setup_obj.entry1_time = datetime.fromisoformat(setup['entry1_time'])
                        
                        # Add attributes
                        setup_obj.entry1_filled = True
                        setup_obj.entry1_price = setup.get('entry1_price')
                        setup_obj.entry2_filled = setup.get('entry2_filled', False)
                        
                        # FVG and CHoCH objects
                        fvg_dict = setup.get('fvg', {})
                        setup_obj.fvg = SimpleNamespace(bottom=fvg_dict.get('bottom', 0), top=fvg_dict.get('top', 0))
                        choch_dict = setup.get('daily_choch', {})
                        setup_obj.daily_choch = SimpleNamespace(direction=choch_dict.get('direction', 'bullish'))
                        
                        # Validate for Entry 2
                        result = validate_choch_confirmation_scale_in(
                            setup=setup_obj,
                            current_time=datetime.now(),
                            df_daily=df_daily,
                            df_4h=df_4h,
                            df_1h=df_1h,
                            config=self.execution_strategy,
                            debug=True
                        )
                        
                        action = result.get('action')
                        reason = result.get('reason')
                        
                        logger.info(f"   🎯 Action: {action}")
                        logger.info(f"   📝 Reason: {reason}")
                        
                        if action == 'EXECUTE_ENTRY2':
                            # Execute Entry 2 (50% position)
                            success = self._execute_entry(
                                setup=setup,
                                entry_number=2,
                                entry_price=result['entry_price'],
                                stop_loss=result['stop_loss'],
                                take_profit=result['take_profit'],
                                position_size=result['position_size']
                            )
                            
                            if success:
                                # Update setup with Entry 2 details
                                setups[i]['entry2_filled'] = True
                                setups[i]['entry2_price'] = result['entry_price']
                                setups[i]['entry2_time'] = datetime.now().isoformat()
                                setups[i]['entry2_lots'] = result['position_size']
                                updated = True
                                logger.success(f"✅ Entry 2 executed for {symbol}, full scale in complete!")
                        
                        elif action == 'CLOSE_ENTRY1':
                            # V8.0: ACTUALLY CLOSE THE POSITION AT BROKER!
                            close_price = result.get('close_price')
                            pnl_pips = result.get('pnl_pips', 0)
                            close_direction = setup.get('direction', 'UNKNOWN')
                            close_reason = f'Timeout expired, Entry 1 negative ({pnl_pips:.1f} pips)'
                            
                            logger.warning(f"   🔴 V8.0 CLOSE_ENTRY1: Closing {symbol} {close_direction} at broker!")
                            logger.warning(f"   📊 Price: {close_price} | P&L: {pnl_pips:.1f} pips")
                            
                            # SEND CLOSE SIGNAL TO CBOT VIA ctrader_executor
                            try:
                                close_success = self.executor.close_position(
                                    symbol=symbol,
                                    direction=close_direction,
                                    reason=close_reason
                                )
                                if close_success:
                                    logger.success(f"   ✅ Close signal sent to cBot for {symbol} {close_direction}")
                                else:
                                    logger.error(f"   ❌ Failed to send close signal for {symbol}")
                            except Exception as close_err:
                                logger.error(f"   ❌ Exception sending close signal: {close_err}")
                            
                            # Update setup status regardless (signal was attempted)
                            setups[i]['status'] = 'CLOSED'
                            setups[i]['close_reason'] = close_reason
                            setups[i]['close_time'] = datetime.now().isoformat()
                            setups[i]['broker_close_sent'] = True
                            updated = True
                        
                        elif action == 'EXPIRE':
                            logger.info(f"   ⏰ Setup {symbol} expired: {reason}")
                            setups[i]['status'] = 'EXPIRED'
                            setups[i]['expire_time'] = datetime.now().isoformat()
                            updated = True
                        
                        elif action == 'KEEP_MONITORING':
                            logger.debug(f"   ⏳ {reason}")
                            setups[i]['last_check'] = datetime.now().isoformat()
                            updated = True
                
                except Exception as e:
                    logger.error(f"❌ Error processing {symbol}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            # Save updated setups
            if updated:
                data['setups'] = setups
                data['last_update'] = datetime.now().isoformat()
                
                with open(self.monitoring_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                logger.debug(f"💾 Updated monitoring_setups.json")
        
        except Exception as e:
            logger.error(f"❌ Error in _process_monitoring_setups: {e}")
            import traceback
            traceback.print_exc()
    
    def _execute_entry(self, setup: dict, entry_number: int, entry_price: float, 
                       stop_loss: float, take_profit: float, position_size: float) -> bool:
        """
        Execute Entry 1 or Entry 2 via cTrader.
        
        Args:
            setup: Setup dict from monitoring_setups.json
            entry_number: 1 or 2
            entry_price: Entry price
            stop_loss: SL price
            take_profit: TP price
            position_size: Lot size (0.5 for scale in)
        
        Returns:
            bool: True if successful
        """
        try:
            symbol = setup['symbol']
            direction = setup['direction']
            
            logger.info(f"\n🚀 EXECUTING ENTRY {entry_number}: {symbol} {direction.upper()}")
            logger.info(f"   Entry: {entry_price}")
            logger.info(f"   SL: {stop_loss}")
            logger.info(f"   TP: {take_profit}")
            logger.info(f"   Lot Size: {position_size}")
            
            # Execute via cTrader executor
            success = self.executor.execute_trade(
                symbol=symbol,
                direction=direction.upper(),
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                lot_size=position_size,
                comment=f"SCALE_IN Entry {entry_number}",
                status='READY'  # Always READY when executing
            )
            
            if success:
                logger.success(f"✅ Entry {entry_number} signal written to signals.json!")
                logger.info(f"   cBot will execute automatically")
                
                # 🔥 Send execution notification (simplified - no TradeSetup object needed)
                try:
                    # 🛡️ V3.8 ANTI-SPAM: Check debouncer before sending execution notification
                    if not self.telegram_debouncer.should_send(
                        symbol, 
                        f"execution_entry{entry_number}", 
                        str(entry_price)
                    ):
                        logger.warning(f"🔕 DEBOUNCED: {symbol} execution notification (sent recently)")
                        return True  # Still return success, just skip notification
                    
                    direction_emoji = "🟢 LONG 📈" if direction == 'buy' else "🔴 SHORT 📉"
                    rr = abs((take_profit - entry_price) / (entry_price - stop_loss)) if abs(entry_price - stop_loss) > 0 else 0
                    
                    message = f"""
🔥 <b>TRADE EXECUTED - Entry {entry_number}</b>

{symbol} {direction_emoji}
──────────────────

✅ Scale-in entry triggered
📍 Entry: <code>{entry_price:.5f}</code>
🛡️ Stop Loss: <code>{stop_loss:.5f}</code>
🎯 Take Profit: <code>{take_profit:.5f}</code>
📊 RR: <code>1:{rr:.1f}</code>
📦 Lot Size: <code>{position_size}</code>

⚡ Aggressive Monitor - V4.0
"""
                    self.telegram.send_message(message.strip(), parse_mode="HTML")
                    logger.success(f"📱 Telegram execution notification sent")
                except Exception as tel_error:
                    import traceback
                    logger.error(f"❌ Telegram notification failed: {tel_error}")
                    logger.error(f"   Exception type: {type(tel_error).__name__}")
                    logger.error(f"   Traceback: {traceback.format_exc()}")
                
                return True
            else:
                logger.error(f"❌ Failed to write signal for Entry {entry_number}")
                return False
        
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
                logger.debug(f"\n🔄 Check #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 🧹 V9.1 R6 CLEANUP: Remove dead setups every 100 iterations (~50min at 30s)
                if iteration == 1 or iteration % 100 == 0:
                    self._cleanup_monitoring_setups()
                
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
        monitor._process_monitoring_setups()
        logger.info("✅ Check complete!")


if __name__ == "__main__":
    main()
