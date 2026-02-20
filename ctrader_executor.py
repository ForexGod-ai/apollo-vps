"""
cTrader Signal Executor - writes to signals.json for PythonSignalExecutor cBot
NOW WITH UNIFIED RISK MANAGER - Validates ALL trades before execution!
"""

import json
import os
from datetime import datetime
from loguru import logger
from typing import Optional
from unified_risk_manager import UnifiedRiskManager


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
    """
    
    def __init__(self, signals_file: str = "signals.json"):
        self.signals_file = signals_file
        
        # V4.3: Track rejected trades to prevent log spam
        # Format: {symbol: {'reason': str, 'timestamp': datetime}}
        self.rejected_trades = {}
        self.rejection_cooldown_seconds = 300  # 5 minutes
        
        # MATRIX LINK: Show absolute path for debugging
        absolute_path = os.path.abspath(signals_file)
        logger.info(f"🔗 MATRIX LINK: Scriu semnale în -> {absolute_path}")
        
        # Verify directory exists
        signals_dir = os.path.dirname(absolute_path)
        if not os.path.exists(signals_dir):
            logger.warning(f"⚠️  Directory {signals_dir} does not exist, creating...")
            os.makedirs(signals_dir, exist_ok=True)
        
        # Initialize Unified Risk Manager
        try:
            self.risk_manager = UnifiedRiskManager()
            logger.success(f"✅ Unified Risk Manager integrated")
        except Exception as e:
            logger.error(f"❌ Failed to load Unified Risk Manager: {e}")
            self.risk_manager = None
        
        logger.info(f"🤖 CTraderExecutor initialized - writing to {signals_file}")
    
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
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # STEP 1: V3.0 STATUS CHECK (4H confirmation required)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if status != 'READY':
            logger.warning(f"⛔ EXECUTION BLOCKED: {symbol} status is '{status}' (must be 'READY')")
            logger.info(f"   Setup is in MONITORING phase - waiting for:")
            logger.info(f"   1. 4H CHoCH confirmation (same direction as Daily)")
            logger.info(f"   2. Price to enter FVG zone")
            return False
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # STEP 2: UNIFIED RISK VALIDATION (NEW IN V3.1!)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # STEP 3: PREPARE SIGNAL FOR CBOT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        try:
            # Generate unique signal ID
            signal_id = f"{symbol}_{direction}_{int(datetime.now().timestamp())}"
            
            # Calculate pip size based on instrument type
            # Crypto (BTC, ETH, etc.): 1 pip = 1.0 (whole price)
            # JPY pairs: 1 pip = 0.01
            # Other forex: 1 pip = 0.0001
            # Gold/Silver: 1 pip = 0.01
            # Oil (XTIUSD, WTIUSD, etc.): 1 pip = 0.01
            if symbol in ['BTCUSD', 'ETHUSD', 'XRPUSD', 'LTCUSD']:
                pip_size = 1.0
            elif 'JPY' in symbol:
                pip_size = 0.01
            elif symbol in ['XAUUSD', 'XAGUSD']:  # Gold, Silver
                pip_size = 0.01
            elif symbol in ['XTIUSD', 'WTIUSD', 'USOIL', 'CL']:  # Oil (WTI, Brent)
                pip_size = 0.01
            else:
                pip_size = 0.0001
            
            sl_pips = abs(entry_price - stop_loss) / pip_size
            tp_pips = abs(take_profit - entry_price) / pip_size
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # V4.0 SMC LEVEL UP - POPULATE NEW FIELDS
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            
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
                
                # ━━━ V4.0 SMC LEVEL UP - NEW FIELDS ━━━
                "LiquiditySweep": liquidity_sweep,
                "SweepType": sweep_type,
                "ConfidenceBoost": confidence_boost,
                "OrderBlockUsed": order_block_used,
                "OrderBlockScore": order_block_score,
                "PremiumDiscountZone": premium_discount_zone,
                "DailyRangePercentage": round(daily_range_percentage, 1)
            }
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # BTC_VOLUME_FIX: Inject raw units for crypto to prevent rounding to 0
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            if symbol in ['BTCUSD', 'ETHUSD', 'XRPUSD', 'LTCUSD']:
                # For crypto, if lot_size < 1.0, calculate raw units
                if lot_size < 1.0:
                    raw_units = int(lot_size * 100000)  # 0.01 lots = 1000 units for BTC
                    if raw_units < 100:  # Minimum 100 units (0.001 lots)
                        raw_units = 100
                    signal["RawUnits"] = raw_units
                    logger.info(f"💉 BTC_VOLUME_FIX: Injected RawUnits={raw_units} (lot_size={lot_size})")
            
            # Write SINGLE signal (cBot expects object, not array)
            with open(self.signals_file, 'w') as f:
                json.dump(signal, f, indent=2)
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # V4.0 SYNC CONFIRMATION LOGGING
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            logger.success(f"✅ Signal written: {direction} {symbol} @ {entry_price} (SL: {sl_pips:.1f} pips, TP: {tp_pips:.1f} pips)")
            
            if liquidity_sweep:
                logger.info(f"   💧 V4.0: Liquidity Sweep {sweep_type} (+{confidence_boost} conf)")
            
            if order_block_used:
                logger.info(f"   📦 V4.0: Order Block entry (score {order_block_score}/10)")
            
            logger.info(f"   📊 V4.0: {premium_discount_zone} zone ({daily_range_percentage:.1f}% of daily range)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to write signal: {e}")
            return False
    
    def clear_signals(self):
        """Clear all signals from signals.json (write empty object)"""
        try:
            with open(self.signals_file, 'w') as f:
                json.dump({}, f)  # Empty object, not array
            logger.info(f"🗑️  Cleared signals from {self.signals_file}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to clear signals: {e}")
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
