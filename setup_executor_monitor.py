"""
Setup Executor Monitor - Monitorizează monitoring_setups.json și execută când devin READY

V3.1 SCALE_IN STRATEGY:
- Entry 1: Execute on 1H CHoCH (50% position)
- Entry 2: Execute on 4H CHoCH within 48h (50% position)
- Timeout handling: Evaluate Entry 1 P&L if no 4H confirmation

Verifică la fiecare 30s:
1. Citește monitoring_setups.json
2. Verifică SCALE_IN validation (validate_choch_confirmation_scale_in)
3. Execută Entry 1 sau Entry 2 automat în cTrader
4. Trimite Telegram notification
"""
import json
import time
from pathlib import Path
from loguru import logger
from datetime import datetime
import sys

from ctrader_cbot_client import CTraderCBotClient
from ctrader_executor import CTraderExecutor
from telegram_notifier import TelegramNotifier
from daily_scanner import CTraderDataProvider
from smc_detector import validate_choch_confirmation_scale_in


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
        
        # Load pairs config for SCALE_IN settings
        self.config = self._load_config()
        self.execution_strategy = self.config.get('scanner_settings', {}).get('execution_strategy', {})
        
        # Track executed setups to avoid duplicates
        self.executed_setups = self._load_executed_setups()
        
        logger.info("🎯 Setup Executor Monitor initialized")
        logger.info(f"⏱️  Check interval: {check_interval}s")
        logger.info(f"📊 Execution Strategy: {self.execution_strategy.get('mode', 'N/A')}")
    
    def _load_config(self):
        """Load pairs_config.json"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
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
    
    def _process_monitoring_setups(self):
        """
        Process all setups in monitoring_setups.json using SCALE_IN validation.
        
        V3.1 SCALE_IN FLOW:
        1. Load setup from monitoring_setups.json
        2. Fetch current market data (Daily, 4H, 1H)
        3. Call validate_choch_confirmation_scale_in()
        4. Execute action: EXECUTE_ENTRY1, EXECUTE_ENTRY2, CLOSE_ENTRY1, KEEP_MONITORING, EXPIRE
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
                
                logger.debug(f"🔍 Processing {symbol}")
                
                # V3.1 SCALE_IN VALIDATION
                try:
                    # Fetch market data
                    df_daily = self.data_provider.get_historical_data(symbol, "D1", 100)
                    df_4h = self.data_provider.get_historical_data(symbol, "H4", 225)
                    df_1h = self.data_provider.get_historical_data(symbol, "H1", 225)
                    
                    if df_daily is None or df_4h is None or df_1h is None:
                        logger.warning(f"⚠️  Could not fetch data for {symbol}, skipping")
                        continue
                    
                    # Convert setup to object-like dict for validation
                    from types import SimpleNamespace
                    setup_obj = SimpleNamespace(**setup)
                    
                    # Convert setup_time to datetime
                    if isinstance(setup.get('setup_time'), str):
                        setup_obj.setup_time = datetime.fromisoformat(setup['setup_time'])
                    
                    # Convert entry1_time to datetime if exists
                    if setup.get('entry1_time') and isinstance(setup['entry1_time'], str):
                        setup_obj.entry1_time = datetime.fromisoformat(setup['entry1_time'])
                    
                    # Add missing attributes with defaults
                    setup_obj.entry1_filled = setup.get('entry1_filled', False)
                    setup_obj.entry1_price = setup.get('entry1_price', None)
                    setup_obj.entry1_time = getattr(setup_obj, 'entry1_time', None)
                    
                    # FVG object
                    fvg_dict = setup.get('fvg', {})
                    setup_obj.fvg = SimpleNamespace(
                        bottom=fvg_dict.get('bottom', 0),
                        top=fvg_dict.get('top', 0)
                    )
                    
                    # Daily CHoCH object
                    choch_dict = setup.get('daily_choch', {})
                    setup_obj.daily_choch = SimpleNamespace(
                        direction=choch_dict.get('direction', 'bullish')
                    )
                    
                    # Call SCALE_IN validation
                    current_time = datetime.now()
                    result = validate_choch_confirmation_scale_in(
                        setup=setup_obj,
                        current_time=current_time,
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
                    
                    # Handle actions
                    if action == 'EXECUTE_ENTRY1':
                        # Execute Entry 1 (50% position)
                        success = self._execute_entry(
                            setup=setup,
                            entry_number=1,
                            entry_price=result['entry_price'],
                            stop_loss=result['stop_loss'],
                            take_profit=result['take_profit'],
                            position_size=result['position_size']
                        )
                        
                        if success:
                            # Update setup with Entry 1 details
                            setups[i]['entry1_filled'] = True
                            setups[i]['entry1_price'] = result['entry_price']
                            setups[i]['entry1_time'] = current_time.isoformat()
                            setups[i]['entry1_lots'] = result['position_size']
                            updated = True
                            logger.success(f"✅ Entry 1 executed for {symbol}")
                    
                    elif action == 'EXECUTE_ENTRY2':
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
                            setups[i]['entry2_time'] = current_time.isoformat()
                            setups[i]['entry2_lots'] = result['position_size']
                            
                            # Move Entry 1 SL to breakeven
                            if result.get('move_entry1_sl_to_breakeven'):
                                logger.info(f"   🔄 Moving Entry 1 SL to breakeven for {symbol}")
                                # TODO: Implement SL modification via cTrader API
                            
                            updated = True
                            logger.success(f"✅ Entry 2 executed for {symbol}, full scale in complete!")
                    
                    elif action == 'CLOSE_ENTRY1':
                        # Close Entry 1 due to timeout + negative P&L
                        close_price = result.get('close_price')
                        pnl_pips = result.get('pnl_pips', 0)
                        
                        logger.warning(f"   ⚠️  Closing Entry 1 for {symbol} @ {close_price} ({pnl_pips:.1f} pips)")
                        
                        # TODO: Implement position close via cTrader API
                        # For now, remove setup from monitoring
                        setups[i]['status'] = 'CLOSED'
                        setups[i]['close_reason'] = f'Timeout expired, Entry 1 negative ({pnl_pips:.1f} pips)'
                        setups[i]['close_time'] = current_time.isoformat()
                        updated = True
                    
                    elif action == 'EXPIRE':
                        # Setup expired (72h)
                        logger.info(f"   ⏰ Setup {symbol} expired: {reason}")
                        setups[i]['status'] = 'EXPIRED'
                        setups[i]['expire_time'] = current_time.isoformat()
                        updated = True
                    
                    elif action == 'KEEP_MONITORING':
                        # No action yet, keep monitoring
                        logger.debug(f"   ⏳ {reason}")
                        # Update last_check time
                        setups[i]['last_check'] = current_time.isoformat()
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
                
                # TODO: Send Telegram notification
                # self.telegram.send_entry_alert(entry_number, symbol, direction, entry_price)
                
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
