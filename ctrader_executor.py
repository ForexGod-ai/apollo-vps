"""
cTrader Signal Executor - writes to signals.json for PythonSignalExecutor cBot
NOW WITH UNIFIED RISK MANAGER - Validates ALL trades before execution!

V5.0 ZERO-LATENCY PROTOCOL:
- Atomic file writes (race-condition proof)
- Signal queue (prevents overwrite)
- Execution confirmation (handshake)
- Absolute paths (location-independent)
"""

import json
import os
import tempfile
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from loguru import logger
from typing import Optional, Dict
from unified_risk_manager import UnifiedRiskManager
import requests
from dotenv import load_dotenv

load_dotenv()


class SignalQueue:
    """
    V5.0 ZERO-LATENCY: Thread-safe signal queue
    Prevents signal loss during simultaneous detections
    """
    def __init__(self, signals_file: str, confirmation_file: str, executor=None):
        self.signals_file = signals_file
        self.confirmation_file = confirmation_file
        self.executor = executor  # Reference to CTraderExecutor for Telegram notifications
        self.queue = queue.Queue(maxsize=20)  # Max 20 pending signals
        self.worker_thread = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="SignalQueueWorker"
        )
        self.worker_thread.start()
        logger.success("🔥 ZERO-LATENCY: Signal queue initialized")
    
    def enqueue(self, signal: dict) -> bool:
        """Add signal to queue (non-blocking)"""
        try:
            self.queue.put_nowait(signal)
            queue_size = self.queue.qsize()
            logger.info(f"📥 Signal queued: {signal['Symbol']} (queue: {queue_size}/20)")
            return True
        except queue.Full:
            logger.error(f"🚨 QUEUE OVERFLOW - Signal dropped: {signal['Symbol']}")
            return False
    
    def _write_signal_atomic(self, signal: dict):
        """
        V5.4 DUAL-PATH WRITE: Writes to BOTH locations for cTrader sync
        - Primary: Script directory (Desktop)
        - Mirror: /Users/forexgod/GlitchMatrix/ (legacy path)
        """
        # Define BOTH write paths
        primary_path = self.signals_file
        mirror_path = "/Users/forexgod/GlitchMatrix/signals.json"
        
        # Ensure mirror directory exists
        mirror_dir = os.path.dirname(mirror_path)
        os.makedirs(mirror_dir, exist_ok=True)
        
        paths_to_write = [primary_path, mirror_path]
        
        for target_path in paths_to_write:
            dir_path = os.path.dirname(target_path)
            
            # Create temp file in same directory
            fd, temp_path = tempfile.mkstemp(
                suffix='.json.tmp',
                dir=dir_path,
                text=True
            )
            
            try:
                # Write to temp file
                with os.fdopen(fd, 'w') as f:
                    json.dump(signal, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())  # Force OS write to disk
                
                # Atomic rename (cannot be interrupted)
                os.replace(temp_path, target_path)
                logger.debug(f"✅ Atomic write: {target_path}")
                
            except Exception as e:
                # Cleanup temp file on failure
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                logger.warning(f"⚠️  Failed to write to {target_path}: {e}")
                # Continue to next path (don't fail completely)
        
        logger.success(f"✅ Signal written to {len(paths_to_write)} locations: {signal['SignalId']}")
    
    def _wait_for_confirmation(self, signal_id: str, timeout: int = 30) -> Optional[Dict]:
        """
        V5.0 HANDSHAKE: Wait for cTrader execution confirmation
        
        ✅ TWO-WAY HANDSHAKE PROTOCOL:
        - Checks BOTH execution_report.json (new) and trade_confirmations.json (legacy)
        - Polls every 1 second for up to 30 seconds
        - Returns confirmation dict if found, None on timeout
        """
        start_time = time.time()
        
        # Check BOTH file paths (new protocol + legacy)
        execution_report_path = self.confirmation_file.replace('trade_confirmations.json', 'execution_report.json')
        legacy_path = self.confirmation_file
        
        while time.time() - start_time < timeout:
            try:
                # Try NEW protocol first (execution_report.json)
                if os.path.exists(execution_report_path):
                    with open(execution_report_path, 'r') as f:
                        data = json.load(f)
                    
                    if data.get('SignalId') == signal_id:
                        logger.debug(f"✅ Found confirmation in execution_report.json")
                        return data
                
                # Fallback to LEGACY (trade_confirmations.json)
                if os.path.exists(legacy_path):
                    with open(legacy_path, 'r') as f:
                        data = json.load(f)
                    
                    if data.get('SignalId') == signal_id:
                        logger.debug(f"✅ Found confirmation in trade_confirmations.json (legacy)")
                        return data
                
            except Exception as e:
                logger.debug(f"Confirmation check error: {e}")
            
            time.sleep(1)
        
        return None
    
    def _process_queue(self):
        """Background worker - processes signals with confirmation"""
        logger.info("🔄 Signal queue worker started")
        
        while True:
            try:
                # Get next signal (blocking)
                signal = self.queue.get(timeout=1)
                signal_id = signal['SignalId']
                symbol = signal['Symbol']
                
                logger.info(f"📤 Dispatching: {symbol} (ID: {signal_id})")
                
                # 1. Write signal atomically
                self._write_signal_atomic(signal)
                logger.success(f"✅ Signal written atomically: {symbol}")
                
                # 2. Wait for confirmation (30s timeout)
                logger.info(f"⏳ Waiting for cTrader confirmation...")
                confirmation = self._wait_for_confirmation(signal_id, timeout=30)
                
                if confirmation:
                    status = confirmation.get('Status')
                    
                    if status == 'EXECUTED':
                        order_id = confirmation.get('OrderId', 'N/A')
                        volume = confirmation.get('Volume', 0)
                        entry_price = confirmation.get('EntryPrice', 0)
                        logger.success(f"✅ CONFIRMED: {symbol} executed")
                        logger.info(f"   Order ID: {order_id}")
                        logger.info(f"   Volume: {volume}")
                        
                        # ✅ SEND SUCCESS NOTIFICATION
                        if self.executor:
                            self.executor._send_telegram_notification(
                                symbol=symbol,
                                direction=signal.get('Direction', 'UNKNOWN'),
                                status='SUCCESS',
                                order_id=order_id,
                                volume=volume,
                                entry_price=entry_price,
                                stop_loss=signal.get('StopLoss', 0),
                                take_profit=signal.get('TakeProfit', 0)
                            )
                    
                    elif status == 'REJECTED':
                        reason = confirmation.get('Reason', 'Unknown')
                        logger.error(f"❌ REJECTED: {symbol}")
                        logger.error(f"   Reason: {reason}")
                        
                        # ❌ SEND REJECTION NOTIFICATION
                        if self.executor:
                            self.executor._send_telegram_notification(
                                symbol=symbol,
                                direction=signal.get('Direction', 'UNKNOWN'),
                                status='REJECTED',
                                reason=reason
                            )
                    
                    else:
                        logger.warning(f"⚠️  UNKNOWN STATUS: {status}")
                        
                        # ⚠️ SEND UNKNOWN STATUS NOTIFICATION
                        if self.executor:
                            self.executor._send_telegram_notification(
                                symbol=symbol,
                                direction=signal.get('Direction', 'UNKNOWN'),
                                status='UNKNOWN',
                                reason=f"Unexpected status: {status}"
                            )
                
                else:
                    logger.warning(f"⏱️  TIMEOUT: No confirmation for {symbol} after 30s")
                    
                    # ⏱️ SEND TIMEOUT NOTIFICATION
                    if self.executor:
                        self.executor._send_telegram_notification(
                            symbol=symbol,
                            direction=signal.get('Direction', 'UNKNOWN'),
                            status='TIMEOUT',
                            reason='cTrader did not respond within 30 seconds'
                        )
                
                # 3. Wait before processing next signal (rate limiting)
                self.queue.task_done()
                time.sleep(15)  # 15s between signals (cTrader polling = 10s)
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Queue processing error: {e}")
                time.sleep(5)


class CTraderExecutor:
    """
    Writes trading signals to signals.json
    PythonSignalExecutor cBot will read and execute them automatically
    
    V3.1: Integrated with Unified Risk Manager
    - Validates against SUPER_CONFIG.json limits
    - Checks kill switch before execution
    - Enforces position limits
    
    V4.3 FIX-015: Anti-spam for rejected trades
    - Tracks rejection reasons per symbol
    - Logs only on status change or after 5-minute cooldown
    
    V5.0 ZERO-LATENCY PROTOCOL:
    - Atomic file writes (race-condition proof)
    - Signal queue (no overwrites)
    - Execution confirmation (handshake)
    - Absolute paths (location-independent)
    """
    
    def __init__(self, signals_file: str = "signals.json"):
        # V5.0: ABSOLUTE PATH ENFORCEMENT
        if not os.path.isabs(signals_file):
            # Force absolute path to script directory
            script_dir = Path(__file__).parent.resolve()
            signals_file = str(script_dir / signals_file)
        
        self.signals_file = signals_file
        
        # V4.3: Track rejected trades to prevent log spam
        self.rejected_trades = {}
        self.rejection_cooldown_seconds = 300
        
        # V5.0: Confirmation file path
        self.confirmation_file = self.signals_file.replace('signals.json', 'trade_confirmations.json')
        
        # Verify directory exists and is writable
        signals_dir = os.path.dirname(self.signals_file)
        if not os.path.exists(signals_dir):
            logger.error(f"❌ Directory does not exist: {signals_dir}")
            raise FileNotFoundError(f"Signals directory not found: {signals_dir}")
        
        # Test write permissions
        try:
            test_file = Path(signals_dir) / ".write_test"
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            logger.error(f"❌ No write permission in: {signals_dir}")
            raise PermissionError(f"Cannot write to signals directory: {e}")
        
        logger.success(f"✅ Signal path verified: {self.signals_file}")
        logger.info(f"✅ Confirmation path: {self.confirmation_file}")
        
        # V5.0: Initialize signal queue (pass self reference for Telegram notifications)
        self.signal_queue = SignalQueue(self.signals_file, self.confirmation_file, executor=self)
        
        # Initialize Unified Risk Manager
        try:
            self.risk_manager = UnifiedRiskManager()
            logger.success(f"✅ Unified Risk Manager integrated")
        except Exception as e:
            logger.error(f"❌ Failed to load Unified Risk Manager: {e}")
            self.risk_manager = None
        
        logger.success(f"🔥 CTraderExecutor V5.0 initialized (ZERO-LATENCY)")
    
    def _send_telegram_notification(self, symbol: str, direction: str, status: str, 
                                    order_id: str = None, volume: float = None, 
                                    entry_price: float = None, stop_loss: float = None,
                                    take_profit: float = None, reason: str = None):
        """
        Send execution status to Telegram with proper formatting
        
        ✅ TWO-WAY HANDSHAKE PROTOCOL:
        - SUCCESS: cTrader confirmed execution
        - REJECTED: cTrader rejected signal (BadVolume, etc.)
        - TIMEOUT: cTrader did not respond within 30s
        - UNKNOWN: cTrader returned unexpected status
        """
        try:
            telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
            telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
            
            if not telegram_token or not telegram_chat_id:
                logger.warning("⚠️  Telegram credentials missing - notification skipped")
                return
            
            # Build message based on status
            if status == 'SUCCESS':
                message = (
                    f"✅ <b>EXECUTION SUCCESS</b>\n\n"
                    f"Symbol: <b>{symbol}</b>\n"
                    f"Direction: <b>{direction}</b>\n"
                    f"Order ID: <code>{order_id}</code>\n"
                    f"Entry: <b>{entry_price:.5f}</b>\n"
                    f"Volume: <b>{volume:.2f}</b> units\n"
                    f"SL: <b>{stop_loss:.5f}</b>\n"
                    f"TP: <b>{take_profit:.5f}</b>\n\n"
                    f"🎯 <i>Trade confirmed by cTrader</i>\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"✨ <b>Glitch in Matrix by ФорексГод</b> ✨\n"
                    f"🧠 <i>AI-Powered</i> • 💎 <i>Smart Money</i>"
                )
            
            elif status == 'REJECTED':
                message = (
                    f"❌ <b>EXECUTION REJECTED</b>\n\n"
                    f"Symbol: <b>{symbol}</b>\n"
                    f"Direction: <b>{direction}</b>\n"
                    f"Reason: <i>{reason}</i>\n\n"
                    f"⚠️ <i>Signal rejected by cTrader</i>\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"✨ <b>Glitch in Matrix by ФорексГод</b> ✨\n"
                    f"🧠 <i>AI-Powered</i> • 💎 <i>Smart Money</i>"
                )
            
            elif status == 'TIMEOUT':
                message = (
                    f"⏱️ <b>EXECUTION TIMEOUT</b>\n\n"
                    f"Symbol: <b>{symbol}</b>\n"
                    f"Direction: <b>{direction}</b>\n\n"
                    f"🚨 <b>CRITICAL:</b> Signal sent but NO RESPONSE from cTrader\n"
                    f"Possible causes:\n"
                    f"• cBot not running\n"
                    f"• File lock conflict\n"
                    f"• Silent error in OnTimer\n\n"
                    f"⚠️ <i>Check cTrader logs immediately</i>\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"✨ <b>Glitch in Matrix by ФорексГод</b> ✨\n"
                    f"🧠 <i>AI-Powered</i> • 💎 <i>Smart Money</i>"
                )
            
            elif status == 'UNKNOWN':
                message = (
                    f"⚠️ <b>UNKNOWN STATUS</b>\n\n"
                    f"Symbol: <b>{symbol}</b>\n"
                    f"Direction: <b>{direction}</b>\n"
                    f"Details: <i>{reason}</i>\n\n"
                    f"🔍 <i>Unexpected response from cTrader</i>\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"✨ <b>Glitch in Matrix by ФорексГод</b> ✨\n"
                    f"🧠 <i>AI-Powered</i> • 💎 <i>Smart Money</i>"
                )
            
            else:
                logger.warning(f"⚠️  Unknown notification status: {status}")
                return
            
            # Send to Telegram
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            payload = {
                'chat_id': telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.success(f"📱 Telegram notification sent: {status}")
            else:
                logger.error(f"❌ Telegram failed: {response.status_code}")
        
        except Exception as e:
            logger.error(f"❌ Telegram notification error: {e}")
    
    def execute_trade(self, symbol: str, direction: str, entry_price: float, 
                     stop_loss: float, take_profit: float, lot_size: float = 0.01,
                     comment: str = "", status: str = "READY", setup=None):
        """
        Write a trade signal to signals.json for PythonSignalExecutor to execute
        
        V3.1: NOW WITH UNIFIED RISK VALIDATION!
        - Checks SUPER_CONFIG.json limits
        - Validates kill switch status
        - Enforces position limits
        - Checks daily loss limits
        
        V4.0: FULL SMC INTELLIGENCE SYNC!
        - Extracts liquidity_sweep from setup
        - Extracts order_block data from setup
        - Extracts premium_discount from setup
        - Populates all V4.0 fields for C# executor
        
        Args:
            symbol: Trading pair (e.g., 'EURUSD')
            direction: 'BUY' or 'SELL'
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            lot_size: Position size in lots (will be recalculated by risk manager)
            comment: Optional comment for the trade
            status: Setup status - MUST be 'READY' to execute (V3.0)
            setup: TradeSetup object from scanner (V4.0 - for metadata extraction)
            direction: 'BUY' or 'SELL'
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            lot_size: Position size in lots (will be recalculated by risk manager)
            comment: Optional comment for the trade
            status: Setup status - MUST be 'READY' to execute (V3.0)
        
        Returns:
            bool: True if signal written, False if rejected
        """
        
        # ──────────────────
        # STEP 1: V3.0 STATUS CHECK (4H confirmation required)
        # ──────────────────
        if status != 'READY':
            logger.warning(f"⛔ EXECUTION BLOCKED: {symbol} status is '{status}' (must be 'READY')")
            logger.info(f"   Setup is in MONITORING phase - waiting for:")
            logger.info(f"   1. 4H CHoCH confirmation (same direction as Daily)")
            logger.info(f"   2. Price to enter FVG zone")
            return False
        
        # ──────────────────
        # STEP 2: UNIFIED RISK VALIDATION (NEW IN V3.1!)
        # ──────────────────
        if self.risk_manager:
            validation = self.risk_manager.validate_new_trade(
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                stop_loss=stop_loss
            )
            
            if not validation['approved']:
                # V4.3 FIX-015: Anti-spam rejection logging
                should_log = self._should_log_rejection(symbol, validation['reason'])
                
                if should_log:
                    logger.error(f"🛑 TRADE REJECTED BY RISK MANAGER")
                    logger.error(f"   Symbol: {symbol} {direction}")
                    logger.error(f"   Reason: {validation['reason']}")
                    logger.error(f"   ✨ Glitch in Matrix by ФорексГод ✨")
                
                return False
            
            # Use risk manager calculated lot size
            if validation['lot_size'] > 0:
                lot_size = validation['lot_size']
                logger.info(f"💰 Lot size from risk manager: {lot_size}")
        else:
            logger.warning("⚠️  Risk manager not available - using default lot size")
        
        # ──────────────────
        # STEP 3: PREPARE SIGNAL FOR CBOT
        # ──────────────────
        
        # 🚨 V5.6 BULLETPROOF FIX: HARDCODED LOT SIZE FOR BTCUSD
        # Force 0.50 lots for BTCUSD to bypass all BadVolume issues
        # BULLETPROOF: Ignore case, spaces, slashes
        if 'BTC' in symbol.upper().replace(' ', '').replace('/', ''):
            lot_size = 0.50
            logger.warning(f"🚨 V5.6 BULLETPROOF: Forcing 0.50 lots for {symbol} (detected as BTC)")
        
        # 🚨 CRITICAL FIX by ФорексГод: Enforce minimum lot size of 0.01
        # Broker minimum = 0.01 lots (micro lot)
        # MUST be done BEFORE signal creation to prevent BadVolume!
        elif lot_size < 0.01:
            logger.warning(f"⚠️  Lot size {lot_size:.4f} below broker minimum - forcing to 0.01")
            lot_size = 0.01
        
        try:
            # Generate unique signal ID
            signal_id = f"{symbol}_{direction}_{int(datetime.now().timestamp())}"
            
            # 🚨 V5.6 BULLETPROOF: Calculate pip size based on instrument type
            # Clean symbol for robust detection (ignore case, spaces, slashes)
            symbol_clean = symbol.upper().replace(' ', '').replace('/', '')
            
            # Crypto (BTC, ETH, etc.): 1 pip = 1.0 (whole price)
            # JPY pairs: 1 pip = 0.01
            # Other forex: 1 pip = 0.0001
            # Gold/Silver: 1 pip = 0.01
            # Oil (XTIUSD, WTIUSD, etc.): 1 pip = 0.01
            if any(crypto in symbol_clean for crypto in ['BTC', 'ETH', 'XRP', 'LTC']):
                pip_size = 1.0
            elif 'JPY' in symbol_clean:
                pip_size = 0.01
            elif any(metal in symbol_clean for metal in ['XAU', 'XAG', 'GOLD', 'SILVER']):
                pip_size = 0.01
            elif any(oil in symbol_clean for oil in ['XTI', 'WTI', 'USOIL', 'CL']):
                pip_size = 0.01
            else:
                pip_size = 0.0001
            
            sl_pips = abs(entry_price - stop_loss) / pip_size
            tp_pips = abs(take_profit - entry_price) / pip_size
            
            # ──────────────────
            # 🚨 V5.6 BULLETPROOF CRYPTO DETECTION by ФорексГод:
            # 1. Crypto: INTEGER pips (1411 not 1411.5) - no decimals!
            # 2. Crypto: CLEAN PRICES (max 2 decimals) - prevents BadVolume
            # 3. BULLETPROOF: Case-insensitive, ignores spaces/slashes
            # ──────────────────
            symbol_clean = symbol.upper().replace(' ', '').replace('/', '')
            is_crypto = any(crypto in symbol_clean for crypto in ['BTC', 'ETH', 'XRP', 'LTC'])
            
            if is_crypto:
                # INTEGER ROUNDING for pips (1411.55 becomes 1412)
                sl_pips = int(round(sl_pips))
                tp_pips = int(round(tp_pips))
                
                # CLEAN PRICES: Round to 2 decimals max for crypto
                # 67258.39054999995 becomes 67258.39
                entry_price = round(entry_price, 2)
                stop_loss = round(stop_loss, 2)
                take_profit = round(take_profit, 2)
                
                logger.info(f"🪙 CRYPTO PRICE CLEANING: {symbol}")
                logger.info(f"   Entry: {entry_price:.2f} | SL: {stop_loss:.2f} | TP: {take_profit:.2f}")
                logger.info(f"   SL Pips: {sl_pips} | TP Pips: {tp_pips} (INTEGER)")
            
            # ──────────────────
            # V4.0 SMC LEVEL UP - POPULATE NEW FIELDS
            # ──────────────────
            # Extract V4.0 intelligence from setup object (if available)
            
            # 💧 Liquidity Sweep Detection
            liquidity_sweep = False
            sweep_type = ""
            confidence_boost = 0
            
            if hasattr(setup, 'liquidity_sweep') and setup.liquidity_sweep:
                liquidity_sweep = setup.liquidity_sweep.get('sweep_detected', False)
                sweep_type = setup.liquidity_sweep.get('sweep_type', '')
                confidence_boost = getattr(setup, 'confidence_boost', 0)
            
            # 📦 Order Block Activation
            order_block_used = False
            order_block_score = 0
            
            if hasattr(setup, 'order_block') and setup.order_block:
                order_block_score = setup.order_block.ob_score
                order_block_used = order_block_score >= 7  # Activated if score ≥7
            
            # 📊 Premium/Discount Filter
            premium_discount_zone = "UNKNOWN"
            daily_range_percentage = 0.0
            
            if hasattr(setup, 'premium_discount') and setup.premium_discount:
                premium_discount_zone = setup.premium_discount.get('zone', 'UNKNOWN')
                daily_range_percentage = setup.premium_discount.get('percentage', 0.0)
            
            # ──────────────────
            
            # 🚨 V5.5 BRUTE FORCE: Calculate RawUnits for direct volume control
            raw_units = None
            if is_crypto:
                raw_units = int(lot_size * 100000)  # 0.50 lots = 50,000 units for BTCUSD
                logger.info(f"🪙 CRYPTO: RawUnits = {raw_units} ({lot_size} lots)")
            
            # 🚨 V5.6 BULLETPROOF: For BTCUSD, REMOVE pips (use only absolute prices)
            # BULLETPROOF: Ignore case, spaces, slashes
            if 'BTC' in symbol_clean:
                signal = {
                    "SignalId": signal_id,
                    "Symbol": symbol,
                    "Direction": direction.lower(),
                    "StrategyType": "BRUTE_FORCE",
                    "EntryPrice": int(round(entry_price)),  # INTEGER only
                    "StopLoss": int(round(stop_loss)),      # INTEGER only
                    "TakeProfit": int(round(take_profit)),  # INTEGER only
                    # NO PIPS - cBot will use absolute prices only!
                    "RiskReward": 5.0,
                    "Timestamp": datetime.now().isoformat(),
                    "LotSize": lot_size,
                    "RawUnits": raw_units,
                    
                    # V4.0 fields (minimal)
                    "LiquiditySweep": False,
                    "SweepType": "",
                    "ConfidenceBoost": 0,
                    "OrderBlockUsed": False,
                    "OrderBlockScore": 0,
                    "PremiumDiscountZone": "UNKNOWN",
                    "DailyRangePercentage": 0.0
                }
                logger.warning(f"🚨 V5.6 BRUTE FORCE MODE: {symbol} with NO PIPS - using absolute prices only!")
            else:
                # Normal signal for non-crypto
                signal = {
                    # ━━━ V1.0 ORIGINAL FIELDS ━━━
                    "SignalId": signal_id,
                    "Symbol": symbol,
                    "Direction": direction.lower(),  # CRITICAL: cBot expects lowercase!
                    "StrategyType": "PULLBACK",
                    "EntryPrice": entry_price,
                    "StopLoss": stop_loss,
                    "TakeProfit": take_profit,
                    "StopLossPips": round(sl_pips, 1),
                    "TakeProfitPips": round(tp_pips, 1),
                    "RiskReward": round(tp_pips / sl_pips, 2),
                    "Timestamp": datetime.now().isoformat(),
                    "LotSize": lot_size,
                    "RawUnits": raw_units,
                    
                    # ━━━ V4.0 SMC LEVEL UP - NEW FIELDS ━━━
                    "LiquiditySweep": liquidity_sweep,
                    "SweepType": sweep_type,
                    "ConfidenceBoost": confidence_boost,
                    "OrderBlockUsed": order_block_used,
                    "OrderBlockScore": order_block_score,
                    "PremiumDiscountZone": premium_discount_zone,
                    "DailyRangePercentage": round(daily_range_percentage, 1)
                }
            
            # ──────────────────
            # V5.6 BULLETPROOF BTC_VOLUME_FIX: Inject raw units for crypto to prevent rounding to 0
            # BULLETPROOF: Case-insensitive, ignores spaces/slashes
            # ──────────────────
            if is_crypto:
                # For crypto, if lot_size < 1.0, calculate raw units
                if lot_size < 1.0:
                    raw_units = int(lot_size * 100000)  # 0.01 lots = 1000 units for BTC
                    if raw_units < 100:  # Minimum 100 units (0.001 lots)
                        raw_units = 100
                    signal["RawUnits"] = raw_units
                    logger.info(f"💉 BTC_VOLUME_FIX: Injected RawUnits={raw_units} (lot_size={lot_size})")
            
            # V5.0: QUEUE SIGNAL (atomic write + confirmation)
            success = self.signal_queue.enqueue(signal)
            
            if success:
                logger.success(f"✅ Signal queued: {direction} {symbol} @ {entry_price}")
                logger.info(f"   SL: {sl_pips:.1f} pips | TP: {tp_pips:.1f} pips | RR: 1:{signal['RiskReward']}")
                
                if liquidity_sweep:
                    logger.info(f"   💧 V4.0: Liquidity Sweep {sweep_type} (+{confidence_boost} conf)")
                
                if order_block_used:
                    logger.info(f"   📦 V4.0: Order Block entry (score {order_block_score}/10)")
                
                logger.info(f"   📊 V4.0: {premium_discount_zone} zone ({daily_range_percentage:.1f}% daily range)")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Failed to write signal: {e}")
            return False
    
    def clear_signals(self):
        """Clear all signals from signals.json (write empty object)"""
        try:
            # V5.0: Use atomic write for clearing too
            dir_path = os.path.dirname(self.signals_file)
            fd, temp_path = tempfile.mkstemp(suffix='.json.tmp', dir=dir_path, text=True)
            
            with os.fdopen(fd, 'w') as f:
                json.dump({}, f)
                f.flush()
                os.fsync(f.fileno())
            
            os.replace(temp_path, self.signals_file)
            logger.info("🗑️  Signals cleared (atomic)")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to clear signals: {e}")
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
            return False
    
    def get_pending_signals(self):
        """Get list of pending signals"""
        try:
            if not os.path.exists(self.signals_file):
                return []
            
            with open(self.signals_file, 'r') as f:
                signals = json.load(f)
                if not isinstance(signals, list):
                    return []
                return signals
        except:
            return []
    
    def _should_log_rejection(self, symbol: str, reason: str) -> bool:
        """
        V4.3 FIX-015: Determine if rejection should be logged
        
        Returns True if:
        - First rejection for this symbol
        - Rejection reason changed
        - 5+ minutes since last log
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSD')
            reason: Rejection reason from Risk Manager
        
        Returns:
            bool: True if should log, False to suppress
        """
        now = datetime.now()
        
        # First rejection for this symbol
        if symbol not in self.rejected_trades:
            self.rejected_trades[symbol] = {
                'reason': reason,
                'timestamp': now
            }
            return True
        
        last_rejection = self.rejected_trades[symbol]
        
        # Rejection reason changed (e.g., max positions -> daily loss)
        if last_rejection['reason'] != reason:
            self.rejected_trades[symbol] = {
                'reason': reason,
                'timestamp': now
            }
            logger.debug(f"📝 Rejection reason changed for {symbol}: {last_rejection['reason']} → {reason}")
            return True
        
        # Cooldown period elapsed (5 minutes)
        elapsed_seconds = (now - last_rejection['timestamp']).total_seconds()
        if elapsed_seconds >= self.rejection_cooldown_seconds:
            self.rejected_trades[symbol]['timestamp'] = now
            logger.debug(f"⏰ Rejection cooldown elapsed for {symbol} ({elapsed_seconds:.0f}s)")
            return True
        
        # Suppress duplicate rejection log
        logger.debug(f"🔇 Suppressing duplicate rejection for {symbol} ({elapsed_seconds:.0f}s ago)")
        return False


# Quick test
if __name__ == "__main__":
    executor = CTraderExecutor()
    
    # Example signal
    executor.execute_trade(
        symbol="EURUSD",
        direction="BUY",
        entry_price=1.0850,
        stop_loss=1.0800,
        take_profit=1.0950,
        lot_size=0.01,
        comment="Test signal from morning scanner"
    )
    
    print(f"\n📋 Pending signals: {len(executor.get_pending_signals())}")
