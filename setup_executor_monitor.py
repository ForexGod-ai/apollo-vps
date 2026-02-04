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
import pandas as pd

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


class SetupExecutorMonitor:
    """Monitorizează setups în MONITORING și execută automat când price atinge entry"""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.monitoring_file = Path("monitoring_setups.json")
        self.executed_file = Path(".executed_setups.json")
        self.config_file = Path("pairs_config.json")
        
        self.ctrader_client = CTraderCBotClient()
        self.executor = CTraderExecutor()
        self.telegram = TelegramNotifier()
        self.data_provider = CTraderDataProvider()
        
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
            'on_timeout_action': 'force_entry'
        })
        
        # SMC Detector for CHoCH detection
        self.smc_detector = SMCDetector()
        
        # Track executed setups to avoid duplicates
        self.executed_setups = self._load_executed_setups()
        
        logger.info("🎯 Setup Executor Monitor initialized")
        logger.info(f"⏱️  Check interval: {check_interval}s")
        logger.info(f"📊 Execution Strategy: {self.execution_strategy.get('mode', 'N/A')}")
        logger.info(f"🎯 V3.2 Pullback Strategy: {'ENABLED' if self.pullback_config['enabled'] else 'DISABLED'}")
    
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
        """Load previously executed setups"""
        if self.executed_file.exists():
            try:
                with open(self.executed_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('executed_keys', []))
            except Exception as e:
                logger.warning(f"Could not load executed setups: {e}")
        return set()
    
    def _save_executed_setup(self, setup_key: str):
        """Save executed setup to prevent re-execution"""
        self.executed_setups.add(setup_key)
        try:
            with open(self.executed_file, 'w') as f:
                json.dump({
                    'executed_keys': list(self.executed_setups),
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
    
    def _immediate_entry_at_choch(self, setup: dict, df_h1, symbol: str) -> dict:
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
        # ========== CHECK FOR IMMEDIATE ENTRY MODE ==========
        pair_config = self.get_pair_config(symbol)
        if pair_config.get('use_immediate_entry', False):
            logger.debug(f"🚀 {symbol}: use_immediate_entry=true, using V2.1 logic")
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
            # ========== STEP 1: DETECT 1H CHoCH ==========
            choch_list = self.smc_detector.detect_choch(df_h1)
            
            if not choch_list:
                return {
                    'action': 'KEEP_MONITORING',
                    'reason': 'No 1H CHoCH detected yet'
                }
            
            # Find most recent CHoCH matching direction and in FVG zone
            matching_choch = None
            for choch in reversed(choch_list):
                choch_price = choch.break_price
                choch_direction = choch.direction
                choch_idx = choch.index
                
                # CRITICAL: Verify candle has CLOSED confirming CHoCH (not just wick touch)
                close_price = df_h1['close'].iloc[choch_idx]
                
                # For bullish CHoCH: Close must be above break price
                # For bearish CHoCH: Close must be below break price
                candle_closed_confirmation = (
                    (choch_direction == 'bullish' and close_price > choch_price) or
                    (choch_direction == 'bearish' and close_price < choch_price)
                )
                
                if not candle_closed_confirmation:
                    logger.debug(f"   ⚠️ {symbol}: CHoCH at {choch_price:.5f} rejected - wick only (Close: {close_price:.5f})")
                    continue
                
                # Check if CHoCH is in FVG zone
                in_fvg = fvg_bottom <= choch_price <= fvg_top
                
                # Check if direction matches
                direction_match = (
                    (direction == 'buy' and choch_direction == 'bullish') or
                    (direction == 'sell' and choch_direction == 'bearish')
                )
                
                if in_fvg and direction_match:
                    matching_choch = choch
                    logger.info(f"   ✅ {symbol}: CHoCH CONFIRMED with body closure at {choch_price:.5f} (Close: {close_price:.5f})")
                    break
            
            if not matching_choch:
                return {
                    'action': 'KEEP_MONITORING',
                    'reason': f'No {direction} CHoCH in FVG zone yet'
                }
            
            # CHoCH found! Calculate Fibonacci
            choch_idx = matching_choch.index
            choch_timestamp = df_h1.index[choch_idx]
            
            fibo_data = calculate_choch_fibonacci(
                df_h1=df_h1,
                choch_idx=choch_idx,
                direction='bullish' if direction == 'buy' else 'bearish'
            )
            
            logger.info(f"   ✅ {symbol}: 1H CHoCH detected at {matching_choch.break_price:.5f}")
            logger.info(f"   📊 Fibo 50%: {fibo_data['fibo_50']:.5f}, Range: {fibo_data['swing_range']:.1f} pips")
            
            # Save CHoCH detection and continue monitoring for pullback
            setup['choch_1h_detected'] = True
            setup['choch_1h_timestamp'] = choch_timestamp.isoformat() if hasattr(choch_timestamp, 'isoformat') else str(choch_timestamp)
            setup['fibo_data'] = fibo_data
            
            logger.info(f"   ⏳ {symbol}: Waiting for pullback to Fibo 50% @ {fibo_data['fibo_50']:.5f}")
            
            # Don't execute yet - fall through to pullback validation below
            choch_detected = True
        
        # ========== STEP 2: VALIDATE PULLBACK TO FIBONACCI 50% ==========
        if choch_detected and fibo_data:
            current_price = df_h1.iloc[-1]['close']
            fibo_50 = fibo_data['fibo_50']
            tolerance_pips = self.pullback_config['tolerance_pips']
            tolerance = 0.0001 * tolerance_pips
            
            # Check if price is within tolerance of Fibo 50%
            price_diff = abs(current_price - fibo_50)
            in_pullback_zone = price_diff <= tolerance
            
            if in_pullback_zone:
                # Calculate SL based on swing
                if direction == 'buy':
                    sl_price = fibo_data['swing_low'] - (0.0001 * self.pullback_config['sl_buffer_pips'])
                else:
                    sl_price = fibo_data['swing_high'] + (0.0001 * self.pullback_config['sl_buffer_pips'])
                
                logger.success(f"   🎯 {symbol}: Pullback reached! Entry @ {current_price:.5f} (Fibo 50%: {fibo_50:.5f})")
                
                return {
                    'action': 'EXECUTE_ENTRY1',
                    'entry_price': current_price,
                    'stop_loss': sl_price,
                    'choch_timestamp': choch_timestamp if isinstance(choch_timestamp, str) else choch_timestamp.isoformat(),
                    'fibo_data': fibo_data,
                    'reason': f'Pullback to Fibo 50% after 1H CHoCH (diff: {price_diff*10000:.1f} pips)'
                }
            else:
                logger.info(f"   ⏳ {symbol}: Waiting for pullback - current: {current_price:.5f}, target: {fibo_50:.5f} (diff: {price_diff*10000:.1f} pips)")
                return {
                    'action': 'KEEP_MONITORING',
                    'reason': f'Waiting for pullback to Fibo 50% (diff: {price_diff*10000:.1f} pips)'
                }
        
        # Should not reach here
        return {
            'action': 'KEEP_MONITORING',
            'reason': 'CHoCH detected but waiting for pullback validation'
        }
    
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
            
            updated = False
            
            for i, setup in enumerate(setups):
                symbol = setup['symbol']
                status = setup.get('status', 'MONITORING')
                
                # Skip expired or non-monitoring setups
                if status != 'MONITORING':
                    continue
                
                logger.debug(f"🔍 Processing {symbol}")
                
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
                    
                    if not entry1_filled:
                        # ========== V3.2 PULLBACK LOGIC FOR ENTRY 1 ==========
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
                                
                                # Send updated setup notification (need df_daily and df_4h for charts)
                                self.telegram.send_setup_alert(notification_setup, df_daily, df_4h)
                                logger.success(f"📱 Resent setup notification for {symbol} with 1H CHoCH status ✅")
                            except Exception as tel_error:
                                logger.warning(f"⚠️ Failed to resend setup notification: {tel_error}")
                            
                            continue  # Skip to next iteration to wait for pullback
                        
                        if result['action'] == 'EXECUTE_ENTRY1':
                            # Execute Entry 1 with pullback price and optimized SL
                            success = self._execute_entry(
                                setup=setup,
                                entry_number=1,
                                entry_price=result['entry_price'],
                                stop_loss=result['stop_loss'],
                                take_profit=setup['take_profit'],
                                position_size=self.execution_strategy.get('entry1_position_size', 0.5)
                            )
                            
                            if success:
                                # Update setup with Entry 1 details and pullback data
                                setups[i]['entry1_filled'] = True
                                setups[i]['entry1_price'] = result['entry_price']
                                setups[i]['entry1_time'] = datetime.now().isoformat()
                                setups[i]['entry1_lots'] = self.execution_strategy.get('entry1_position_size', 0.5)
                                setups[i]['choch_1h_detected'] = True
                                setups[i]['choch_1h_timestamp'] = result.get('choch_timestamp')
                                setups[i]['fibo_data'] = result.get('fibo_data', {})
                                setups[i]['pullback_status'] = 'PULLBACK_REACHED'
                                updated = True
                                logger.success(f"✅ V3.2 Entry 1 executed for {symbol} at Fibo 50%")
                        
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
                            # Close Entry 1 due to timeout + negative P&L
                            close_price = result.get('close_price')
                            pnl_pips = result.get('pnl_pips', 0)
                            logger.warning(f"   ⚠️  Closing Entry 1 for {symbol} @ {close_price} ({pnl_pips:.1f} pips)")
                            setups[i]['status'] = 'CLOSED'
                            setups[i]['close_reason'] = f'Timeout expired, Entry 1 negative ({pnl_pips:.1f} pips)'
                            setups[i]['close_time'] = datetime.now().isoformat()
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
                
                # Send basic execution confirmation (no entry_type info available here)
                try:
                    # Create minimal TradeSetup object for notification
                    from smc_detector import TradeSetup
                    notification_setup = TradeSetup(
                        symbol=symbol,
                        direction=direction,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        risk_reward=abs((take_profit - entry_price) / (entry_price - stop_loss)) if abs(entry_price - stop_loss) > 0 else 0,
                        setup_time=datetime.now(),
                        priority=1
                    )
                    
                    # Send simple notification (entry_type not available in this context)
                    self.telegram.send_execution_confirmation(
                        setup=notification_setup,
                        entry_type='pullback',  # Default
                        momentum_score=0,
                        hours_elapsed=0
                    )
                    logger.success(f"📱 Telegram execution confirmation sent")
                except Exception as tel_error:
                    logger.warning(f"⚠️ Telegram notification failed: {tel_error}")
                
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
    
    parser = argparse.ArgumentParser(description='Setup Executor Monitor')
    parser.add_argument('--interval', type=int, default=30,
                        help='Check interval in seconds (default: 30)')
    parser.add_argument('--loop', action='store_true',
                        help='Run in continuous loop mode')
    
    args = parser.parse_args()
    
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
