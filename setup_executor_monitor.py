"""
Setup Executor Monitor - Monitorizează monitoring_setups.json și execută când devin READY

Verifică la fiecare 30s:
1. Citește monitoring_setups.json
2. Verifică dacă price a atins entry level
3. Execută trade automat în cTrader
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


class SetupExecutorMonitor:
    """Monitorizează setups în MONITORING și execută automat când price atinge entry"""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.monitoring_file = Path("monitoring_setups.json")
        self.executed_file = Path(".executed_setups.json")
        
        self.ctrader_client = CTraderCBotClient()
        self.executor = CTraderExecutor()
        self.telegram = TelegramNotifier()
        
        # Track executed setups to avoid duplicates
        self.executed_setups = self._load_executed_setups()
        
        logger.info("🎯 Setup Executor Monitor initialized")
        logger.info(f"⏱️  Check interval: {check_interval}s")
    
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
            if df.empty:
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
    
    def _execute_setup(self, setup: dict) -> bool:
        """Execute setup in cTrader"""
        try:
            symbol = setup['symbol']
            direction = setup['direction']
            entry = setup['entry_price']
            sl = setup['stop_loss']
            tp = setup['take_profit']
            lot_size = setup.get('lot_size', 0.01)
            status = setup.get('status', 'MONITORING')  # V3.0: Get status field
            
            # V3.0 CHECK: Only execute if status is READY
            if status != 'READY':
                logger.info(f"⏳ SKIPPED: {symbol} is in MONITORING phase (status: {status})")
                logger.info(f"   Waiting for: 4H CHoCH + price in FVG")
                return False
            
            logger.info(f"\n🚀 EXECUTING SETUP: {symbol} {direction.upper()}")
            logger.info(f"   Status: {status} ✅")
            logger.info(f"   Entry: {entry}")
            logger.info(f"   SL: {sl}")
            logger.info(f"   TP: {tp}")
            logger.info(f"   Lot Size: {lot_size}")
            
            # Execute via cTrader executor (will double-check status)
            success = self.executor.execute_trade(
                symbol=symbol,
                direction=direction.upper(),
                entry_price=entry,
                stop_loss=sl,
                take_profit=tp,
                lot_size=lot_size,
                comment=f"Auto-Execute from Monitor",
                status=status  # V3.0: Pass status for validation
            )
            
            if success:
                logger.success(f"✅ Trade signal written to signals.json!")
                logger.info(f"   cBot will execute automatically")
                
                # Save executed setup to prevent re-execution
                setup_key = self._get_setup_key(setup)
                self._save_executed_setup(setup_key)
                
                # TODO: Send Telegram notification (method doesn't exist yet)
                # self.telegram.send_execution_alert(...)
                
                return True
            else:
                logger.error(f"❌ Failed to write signal")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error executing setup: {e}")
            return False
    
    def _process_monitoring_setups(self):
        """Process all setups in monitoring_setups.json"""
        if not self.monitoring_file.exists():
            return
        
        try:
            with open(self.monitoring_file, 'r') as f:
                data = json.load(f)
                setups = data.get('setups', [])
            
            if not setups:
                return
            
            logger.debug(f"📊 Checking {len(setups)} monitoring setups...")
            
            for setup in setups:
                setup_key = self._get_setup_key(setup)
                
                # Skip if already executed
                if setup_key in self.executed_setups:
                    continue
                
                symbol = setup['symbol']
                entry = setup['entry_price']
                direction = setup['direction']
                
                # Check if price hit entry
                hit, current_price = self._check_price_hit_entry(symbol, entry, direction)
                
                if hit:
                    logger.info(f"\n🎯 ENTRY HIT: {symbol} {direction.upper()}")
                    logger.info(f"   Entry Level: {entry}")
                    logger.info(f"   Current Price: {current_price}")
                    
                    # Execute the trade
                    success = self._execute_setup(setup)
                    
                    if success:
                        # Mark as executed
                        self._save_executed_setup(setup_key)
                        logger.success(f"✅ {symbol} executed and marked as done")
                    else:
                        logger.error(f"❌ Failed to execute {symbol}")
                        # Don't mark as executed so we can retry
                
        except Exception as e:
            logger.error(f"Error processing monitoring setups: {e}")
    
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
