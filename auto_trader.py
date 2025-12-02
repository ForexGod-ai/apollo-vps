"""
Autonomous Trading System
Monitors for setups and executes trades automatically on MT5
"""
import json
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import MetaTrader5 as mt5
from loguru import logger
from dataclasses import dataclass, asdict
import os

from daily_scanner import DailyScanner
from mt5_executor import MT5Executor
from telegram_bot import TelegramBot
from smc_detector import TradeSetup
from price_action_analyzer import PriceActionAnalyzer


@dataclass
class ExecutedTrade:
    """Record of executed trade"""
    ticket: int
    symbol: str
    direction: str  # 'BUY' or 'SELL'
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    risk_reward: float
    strategy_type: str
    open_time: datetime
    status: str = 'OPEN'  # 'OPEN', 'TP_HIT', 'SL_HIT', 'CLOSED_MANUAL'
    close_time: Optional[datetime] = None
    profit: Optional[float] = None
    close_price: Optional[float] = None


class AutoTrader:
    """Autonomous trading system"""
    
    def __init__(self, config_path: str = "trading_config.json"):
        """Initialize auto trader"""
        # Load config
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Initialize components
        self.scanner = DailyScanner()
        self.executor = MT5Executor()
        self.telegram = TelegramBot()
        self.price_action = PriceActionAnalyzer()  # NEW: GLITCH detector!
        
        # Trading state
        self.active_trades: List[ExecutedTrade] = []
        self.trades_today = 0
        self.last_scan_time = None
        self.processed_setups = set()  # Track which setups we've already processed
        
        # Connect to MT5
        if not self.executor.connect():
            raise Exception("Failed to connect to MT5")
        
        logger.info("✅ Auto Trader initialized")
        logger.info(f"⚙️ Config: Risk {self.config['risk_management']['risk_per_trade_percent']}%, "
                   f"Max {self.config['position_limits']['max_trades_per_day']} trades/day")
    
    def calculate_lot_size(self, symbol: str, entry: float, sl: float, account_balance: float) -> float:
        """
        Calculate lot size based on risk management
        Risk = (Entry - SL) * Lot Size * Contract Size
        Lot Size = Risk Amount / (Entry - SL) / Contract Size
        """
        try:
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logger.error(f"Cannot get symbol info for {symbol}")
                return self.config['lot_size']['min_lot']
            
            # Calculate risk amount
            risk_percent = self.config['risk_management']['risk_per_trade_percent'] / 100
            risk_amount = account_balance * risk_percent
            
            # Calculate pip distance
            pip_distance = abs(entry - sl)
            
            # Contract size (usually 100,000 for forex)
            contract_size = symbol_info.trade_contract_size
            
            # Point value
            point = symbol_info.point
            
            # Calculate lot size
            # Risk = Distance in pips * Point value * Contract size * Lot size
            lot_size = risk_amount / (pip_distance * contract_size)
            
            # Apply constraints
            min_lot = self.config['lot_size']['min_lot']
            max_lot = self.config['lot_size']['max_lot']
            step_lot = self.config['lot_size']['step_lot']
            
            # Round to step
            lot_size = round(lot_size / step_lot) * step_lot
            
            # Clamp to min/max
            lot_size = max(min_lot, min(max_lot, lot_size))
            
            logger.info(f"💰 Calculated lot size for {symbol}: {lot_size} "
                       f"(Risk: ${risk_amount:.2f}, Distance: {pip_distance:.5f})")
            
            return lot_size
        
        except Exception as e:
            logger.error(f"Error calculating lot size: {e}")
            return self.config['lot_size']['min_lot']
    
    def should_execute_setup(self, setup: TradeSetup) -> bool:
        """Check if setup meets execution criteria"""
        
        # Check if already processed
        setup_id = f"{setup.symbol}_{setup.setup_time.isoformat()}"
        if setup_id in self.processed_setups:
            logger.debug(f"⏭️ Setup {setup.symbol} already processed")
            return False
        
        # Check if trading enabled
        if not self.config['auto_trading']['enabled']:
            logger.info("🛑 Auto trading is DISABLED in config")
            return False
        
        # Check daily trade limit
        if self.trades_today >= self.config['position_limits']['max_trades_per_day']:
            logger.warning(f"⚠️ Daily trade limit reached: {self.trades_today}/{self.config['position_limits']['max_trades_per_day']}")
            return False
        
        # Check max open positions
        if len(self.active_trades) >= self.config['position_limits']['max_open_positions']:
            logger.warning(f"⚠️ Max open positions reached: {len(self.active_trades)}/{self.config['position_limits']['max_open_positions']}")
            return False
        
        # Check if already have position on this symbol
        max_per_symbol = self.config['position_limits']['max_positions_per_symbol']
        symbol_positions = [t for t in self.active_trades if t.symbol == setup.symbol and t.status == 'OPEN']
        if len(symbol_positions) >= max_per_symbol:
            logger.warning(f"⚠️ Already have {len(symbol_positions)} position(s) on {setup.symbol}")
            return False
        
        # Check minimum R:R
        min_rr = self.config['filters']['min_risk_reward']
        if setup.risk_reward < min_rr:
            logger.info(f"⏭️ {setup.symbol} R:R {setup.risk_reward:.2f} < minimum {min_rr}")
            return False
        
        # Check strategy type
        allowed_types = self.config['filters']['allowed_strategy_types']
        if setup.strategy_type.lower() not in allowed_types:
            logger.info(f"⏭️ {setup.symbol} strategy type {setup.strategy_type} not in allowed list")
            return False
        
        # Check priority
        min_priority = self.config['filters']['min_priority']
        max_priority = self.config['filters']['max_priority']
        if not (min_priority <= setup.priority <= max_priority):
            logger.info(f"⏭️ {setup.symbol} priority {setup.priority} outside range [{min_priority}, {max_priority}]")
            return False
        
        logger.info(f"✅ {setup.symbol} meets all execution criteria")
        return True
    
    def execute_trade(self, setup: TradeSetup) -> Optional[ExecutedTrade]:
        """Execute trade on MT5"""
        try:
            # Get account info
            account_info = self.executor.get_account_info()
            if not account_info:
                logger.error("Cannot get account info")
                return None
            
            balance = account_info['balance']
            
            # Calculate lot size
            lot_size = self.calculate_lot_size(
                setup.symbol, 
                setup.entry_price, 
                setup.stop_loss, 
                balance
            )
            
            # Determine direction
            direction = setup.daily_choch.direction
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🚀 EXECUTING TRADE: {setup.symbol}")
            logger.info(f"📊 Direction: {direction}")
            logger.info(f"💵 Entry: {setup.entry_price}")
            logger.info(f"🛑 SL: {setup.stop_loss}")
            logger.info(f"🎯 TP: {setup.take_profit}")
            logger.info(f"📦 Lot Size: {lot_size}")
            logger.info(f"📈 R:R: 1:{setup.risk_reward:.2f}")
            logger.info(f"🎲 Strategy: {setup.strategy_type.upper()}")
            logger.info(f"{'='*60}\n")
            
            # Execute on MT5
            result = None
            if direction == 'bullish':
                result = self.executor.execute_buy(
                    setup.symbol, 
                    lot_size, 
                    setup.stop_loss, 
                    setup.take_profit
                )
            else:
                result = self.executor.execute_sell(
                    setup.symbol, 
                    lot_size, 
                    setup.stop_loss, 
                    setup.take_profit
                )
            
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                # Create trade record
                trade = ExecutedTrade(
                    ticket=result.order,
                    symbol=setup.symbol,
                    direction='BUY' if direction == 'bullish' else 'SELL',
                    entry_price=setup.entry_price,
                    stop_loss=setup.stop_loss,
                    take_profit=setup.take_profit,
                    lot_size=lot_size,
                    risk_reward=setup.risk_reward,
                    strategy_type=setup.strategy_type,
                    open_time=datetime.now()
                )
                
                # Update state
                self.active_trades.append(trade)
                self.trades_today += 1
                self.processed_setups.add(f"{setup.symbol}_{setup.setup_time.isoformat()}")
                
                # Send Telegram notification
                self._send_trade_notification(trade, "OPENED")
                
                # Save to history
                self._save_trade_history(trade)
                
                logger.info(f"✅ Trade #{trade.ticket} EXECUTED successfully!")
                logger.info(f"📊 Trades today: {self.trades_today}/{self.config['position_limits']['max_trades_per_day']}")
                logger.info(f"📊 Active positions: {len(self.active_trades)}")
                
                return trade
            else:
                error_msg = result.comment if result else "Unknown error"
                logger.error(f"❌ Trade execution FAILED: {error_msg}")
                
                # Send error notification
                self.telegram.send_message(
                    f"❌ **Trade Execution FAILED**\n\n"
                    f"Symbol: {setup.symbol}\n"
                    f"Direction: {direction}\n"
                    f"Error: {error_msg}"
                )
                
                return None
        
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return None
    
    def monitor_active_trades(self):
        """Check status of active trades and update if TP/SL hit"""
        try:
            for trade in self.active_trades:
                if trade.status != 'OPEN':
                    continue
                
                # Get position from MT5
                positions = mt5.positions_get(ticket=trade.ticket)
                
                if positions is None or len(positions) == 0:
                    # Position closed (TP or SL hit)
                    # Get from history
                    from_date = trade.open_time
                    to_date = datetime.now()
                    
                    deals = mt5.history_deals_get(from_date, to_date, position=trade.ticket)
                    
                    if deals and len(deals) > 0:
                        last_deal = deals[-1]
                        
                        trade.close_time = datetime.fromtimestamp(last_deal.time)
                        trade.close_price = last_deal.price
                        trade.profit = last_deal.profit
                        
                        # Determine if TP or SL
                        if trade.direction == 'BUY':
                            if trade.close_price >= trade.take_profit * 0.999:  # 0.1% tolerance
                                trade.status = 'TP_HIT'
                            else:
                                trade.status = 'SL_HIT'
                        else:
                            if trade.close_price <= trade.take_profit * 1.001:  # 0.1% tolerance
                                trade.status = 'TP_HIT'
                            else:
                                trade.status = 'SL_HIT'
                        
                        logger.info(f"🔔 Trade #{trade.ticket} {trade.status}: {trade.symbol} "
                                   f"Profit: ${trade.profit:.2f}")
                        
                        # Send notification
                        self._send_trade_notification(trade, trade.status)
                        
                        # Save to history
                        self._save_trade_history(trade)
        
        except Exception as e:
            logger.error(f"Error monitoring trades: {e}")
    
    def _send_trade_notification(self, trade: ExecutedTrade, event: str):
        """Send Telegram notification for trade event"""
        try:
            if event == "OPENED":
                icon = "🚀"
                title = "NEW TRADE OPENED"
                extra = ""
            elif event == "TP_HIT":
                icon = "✅"
                title = "TAKE PROFIT HIT"
                extra = f"\n💰 **Profit**: ${trade.profit:.2f}"
            elif event == "SL_HIT":
                icon = "🛑"
                title = "STOP LOSS HIT"
                extra = f"\n💔 **Loss**: ${trade.profit:.2f}"
            else:
                icon = "📊"
                title = "TRADE UPDATE"
                extra = ""
            
            message = (
                f"{icon} **{title}**\n\n"
                f"🎫 Ticket: #{trade.ticket}\n"
                f"📊 Symbol: {trade.symbol}\n"
                f"📈 Direction: {trade.direction}\n"
                f"💵 Entry: {trade.entry_price:.5f}\n"
                f"🛑 SL: {trade.stop_loss:.5f}\n"
                f"🎯 TP: {trade.take_profit:.5f}\n"
                f"📦 Lot Size: {trade.lot_size}\n"
                f"📊 R:R: 1:{trade.risk_reward:.2f}\n"
                f"🎲 Strategy: {trade.strategy_type.upper()}\n"
                f"⏰ Time: {trade.open_time.strftime('%Y-%m-%d %H:%M:%S')}"
                f"{extra}"
            )
            
            self.telegram.send_alert(message)
            
            # Post to website dashboard
            if event == "OPENED":
                self._post_to_dashboard(trade)
        except Exception as e:
            logger.error(f"❌ Failed to send notification: {e}")
    
    def _post_to_dashboard(self, trade: ExecutedTrade):
        """Post trade to website dashboard"""
        try:
            trade_data = {
                'symbol': trade.symbol,
                'direction': trade.direction,
                'entry': trade.entry_price,
                'stop_loss': trade.stop_loss,
                'take_profit': trade.take_profit,
                'lot_size': trade.lot_size,
                'risk_reward': trade.risk_reward,
                'strategy': trade.strategy_type,
                'timestamp': trade.open_time.isoformat(),
                'ticket': trade.ticket
            }
            
            url = "http://127.0.0.1:5001/api/trades"
            response = requests.post(url, json=trade_data, timeout=5)
            
            if response.status_code == 200:
                logger.info(f"✅ Dashboard updated for trade #{trade.ticket}")
            else:
                logger.warning(f"⚠️ Dashboard update failed: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Dashboard post error: {e}")
    
    def _save_trade_history(self, trade: ExecutedTrade):
        """Save trade to history file"""
        try:
            history_file = "trade_history.json"
            
            # Load existing history
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    history = json.load(f)
            else:
                history = []
            
            # Add/update trade
            trade_dict = asdict(trade)
            trade_dict['open_time'] = trade.open_time.isoformat()
            if trade.close_time:
                trade_dict['close_time'] = trade.close_time.isoformat()
            
            # Remove existing entry if updating
            history = [t for t in history if t['ticket'] != trade.ticket]
            history.append(trade_dict)
            
            # Save
            with open(history_file, 'w') as f:
                json.dump(history, f, indent=2)
        
        except Exception as e:
            logger.error(f"Error saving trade history: {e}")
    
    def run_once(self):
        """Run one cycle of scanning and execution"""
        try:
            logger.info("\n" + "="*60)
            logger.info(f"🔄 AUTO TRADER CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("="*60)
            
            # Monitor active trades first
            if len(self.active_trades) > 0:
                logger.info(f"👀 Monitoring {len(self.active_trades)} active trades...")
                self.monitor_active_trades()
            
            # Scan for new setups
            logger.info("🔍 Scanning for new setups...")
            setups = self.scanner.run_daily_scan(keep_connection=True)  # Keep MT5 connected
            
            logger.info(f"📊 Found {len(setups)} total setups")
            
            # Filter and execute
            executed_count = 0
            for setup in setups:
                if self.should_execute_setup(setup):
                    trade = self.execute_trade(setup)
                    if trade:
                        executed_count += 1
            
            if executed_count > 0:
                logger.info(f"✅ Executed {executed_count} new trades this cycle")
            else:
                logger.info("ℹ️ No new trades executed this cycle")
            
            # Summary
            logger.info(f"\n📊 **SUMMARY**")
            logger.info(f"   • Active Trades: {len([t for t in self.active_trades if t.status == 'OPEN'])}")
            logger.info(f"   • Trades Today: {self.trades_today}/{self.config['position_limits']['max_trades_per_day']}")
            logger.info(f"   • Total Processed: {len(self.processed_setups)}")
            
            self.last_scan_time = datetime.now()
        
        except Exception as e:
            logger.error(f"Error in auto trader cycle: {e}")
    
    def run_continuous(self):
        """Run continuously with interval checking"""
        logger.info("\n" + "="*80)
        logger.info("🤖 AUTONOMOUS TRADING SYSTEM STARTED")
        logger.info("="*80)
        logger.info(f"⚙️ Mode: {self.config['auto_trading']['mode'].upper()}")
        logger.info(f"⚙️ Risk per trade: {self.config['risk_management']['risk_per_trade_percent']}%")
        logger.info(f"⚙️ Max trades/day: {self.config['position_limits']['max_trades_per_day']}")
        logger.info(f"⚙️ Check interval: {self.config['monitoring']['check_interval_seconds']}s")
        logger.info("="*80)
        
        # Send startup notification
        account_info = self.executor.get_account_info()
        self.telegram.send_message(
            f"🤖 **AUTO TRADER STARTED**\n\n"
            f"📊 Account: #{account_info['login']}\n"
            f"💰 Balance: ${account_info['balance']:.2f}\n"
            f"⚙️ Mode: {self.config['auto_trading']['mode'].upper()}\n"
            f"📈 Risk: {self.config['risk_management']['risk_per_trade_percent']}% per trade\n"
            f"🎯 Ready to execute trades automatically!"
        )
        
        try:
            while True:
                # Run cycle
                self.run_once()
                
                # Reset daily counter at midnight
                now = datetime.now()
                if now.hour == 0 and now.minute == 0:
                    self.trades_today = 0
                    logger.info("🔄 Daily counter reset")
                
                # Wait for next cycle
                interval = self.config['monitoring']['check_interval_seconds']
                logger.info(f"\n⏸️ Waiting {interval}s until next cycle...\n")
                time.sleep(interval)
        
        except KeyboardInterrupt:
            logger.info("\n⚠️ Auto trader stopped by user")
            self.telegram.send_message("⚠️ **AUTO TRADER STOPPED**\n\nStopped by user.")
        except Exception as e:
            logger.error(f"Fatal error in auto trader: {e}")
            self.telegram.send_message(f"❌ **AUTO TRADER ERROR**\n\n{str(e)}")
        finally:
            self.executor.disconnect()


if __name__ == "__main__":
    """Run autonomous trading"""
    logger.info("🚀 Starting Autonomous Trading System...")
    
    trader = AutoTrader()
    trader.run_continuous()
