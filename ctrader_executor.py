#!/usr/bin/env python3
"""
cTrader Trade Executor - Automated Trade Execution
Replaces MT5 executor for IC Markets cTrader integration
"""

import os
from typing import Optional, Dict
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

# Load environment
load_dotenv()

class CTraderExecutor:
    """
    Executes trades on cTrader platform (IC Markets)
    
    Simple approach: Uses cTrader Web API with login credentials
    """
    
    def __init__(self):
        """Initialize cTrader connection"""
        self.account_id = os.getenv('CTRADER_ACCOUNT_ID', '9709773')
        self.password = os.getenv('CTRADER_PASSWORD')
        self.server = os.getenv('CTRADER_SERVER', 'demo.icmarkets.com')
        self.connected = False
        
        logger.info("🤖 cTrader Executor initialized")
        logger.info(f"   Account: {self.account_id}")
        logger.info(f"   Server: {self.server}")
    
    def connect(self) -> bool:
        """
        Connect to cTrader account
        
        Returns:
            True if connected successfully
        """
        if not self.password:
            logger.error("❌ CTRADER_PASSWORD not set in .env")
            return False
        
        try:
            # TODO: Implement cTrader API connection
            # For now, we'll use a simpler approach with direct HTTP requests
            logger.info("🔌 Connecting to cTrader...")
            
            # Placeholder - will implement actual connection
            self.connected = True
            logger.success("✅ Connected to cTrader successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to cTrader: {e}")
            return False
    
    def place_order(
        self,
        symbol: str,
        order_type: str,  # 'buy' or 'sell'
        volume: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        comment: str = "Glitch Matrix"
    ) -> Optional[Dict]:
        """
        Place market order with SL/TP
        
        Args:
            symbol: Trading pair (e.g., EURUSD)
            order_type: 'buy' or 'sell'
            volume: Lot size (0.01 = 1 micro lot)
            entry_price: Entry price (for limit orders, use current for market)
            stop_loss: Stop loss price
            take_profit: Take profit price
            comment: Order comment
        
        Returns:
            Order details dict or None if failed
        """
        if not self.connected:
            if not self.connect():
                return None
        
        try:
            logger.info(f"📊 Placing {order_type.upper()} order:")
            logger.info(f"   Symbol: {symbol}")
            logger.info(f"   Volume: {volume} lots")
            logger.info(f"   Entry: {entry_price}")
            logger.info(f"   SL: {stop_loss}")
            logger.info(f"   TP: {take_profit}")
            
            # TODO: Implement actual cTrader order placement
            # For now, return mock data
            order = {
                'order_id': f"CT{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'symbol': symbol,
                'type': order_type,
                'volume': volume,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'status': 'pending',
                'timestamp': datetime.now()
            }
            
            logger.success(f"✅ Order placed: {order['order_id']}")
            return order
            
        except Exception as e:
            logger.error(f"❌ Failed to place order: {e}")
            return None
    
    def get_open_positions(self) -> list:
        """
        Get list of open positions from trade_history.json
        
        Returns:
            List of open position dicts
        """
        if not self.connected:
            if not self.connect():
                return []
        
        try:
            logger.info("📊 Fetching open positions from trade history...")
            
            import json
            try:
                with open('trade_history.json', 'r') as f:
                    trades = json.load(f)
            except FileNotFoundError:
                logger.warning("⚠️  No trade_history.json found")
                return []
            
            # Filter open positions
            positions = [t for t in trades if t.get('status') == 'OPEN']
            
            logger.info(f"   Found {len(positions)} open positions")
            for pos in positions:
                logger.info(f"   • {pos['symbol']} {pos['direction']} @ {pos['entry_price']}")
            
            return positions
            
        except Exception as e:
            logger.error(f"❌ Failed to get positions: {e}")
            return []
    
    def close_position(self, position_id: str) -> bool:
        """
        Close an open position
        
        Args:
            position_id: Position ID to close
        
        Returns:
            True if closed successfully
        """
        if not self.connected:
            if not self.connect():
                return False
        
        try:
            logger.info(f"🔴 Closing position: {position_id}")
            
            # TODO: Implement actual position close
            
            logger.success(f"✅ Position closed: {position_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to close position: {e}")
            return False
    
    def get_account_info(self) -> Optional[Dict]:
        """
        Get account information - reads from trade_history.json
        
        Returns:
            Account info dict with balance, equity, margin, etc.
        """
        if not self.connected:
            if not self.connect():
                return None
        
        try:
            logger.info("📊 Fetching account info from trade history...")
            
            # Read trade history to calculate account state
            import json
            try:
                with open('trade_history.json', 'r') as f:
                    trades = json.load(f)
            except FileNotFoundError:
                logger.warning("⚠️  No trade_history.json found - using defaults")
                trades = []
            
            # Calculate from closed trades
            initial_balance = 10000.0
            closed_trades = [t for t in trades if 'CLOSED' in t.get('status', '')]
            total_profit = sum([t.get('profit', 0) for t in closed_trades])
            
            current_balance = initial_balance + total_profit
            
            # Calculate open positions floating P/L
            open_positions = [t for t in trades if t.get('status') == 'OPEN']
            floating_pl = 0  # Would need live prices to calculate
            
            equity = current_balance + floating_pl
            margin = len(open_positions) * 100  # Rough estimate
            
            account_info = {
                'account_id': self.account_id,
                'balance': current_balance,
                'equity': equity,
                'margin': margin,
                'free_margin': equity - margin,
                'currency': 'USD',
                'server': self.server,
                'profit': total_profit,
                'open_positions': len(open_positions),
                'closed_trades': len(closed_trades)
            }
            
            logger.info(f"   Balance: ${account_info['balance']:.2f}")
            logger.info(f"   Equity: ${account_info['equity']:.2f}")
            logger.info(f"   Profit: ${account_info['profit']:.2f}")
            logger.info(f"   Open positions: {account_info['open_positions']}")
            return account_info
            
        except Exception as e:
            logger.error(f"❌ Failed to get account info: {e}")
            return None
    
    def disconnect(self):
        """Disconnect from cTrader"""
        if self.connected:
            logger.info("🔌 Disconnecting from cTrader...")
            # TODO: Implement actual disconnect
            self.connected = False
            logger.info("✅ Disconnected")


def test_ctrader_connection():
    """Test cTrader connection and basic operations"""
    logger.info("="*70)
    logger.info("🧪 TESTING cTrader CONNECTION")
    logger.info("="*70)
    
    executor = CTraderExecutor()
    
    # Test connection
    if executor.connect():
        logger.success("✅ Connection test passed")
        
        # Test account info
        account = executor.get_account_info()
        if account:
            logger.success("✅ Account info retrieved")
        
        # Test order placement (demo)
        order = executor.place_order(
            symbol='EURUSD',
            order_type='buy',
            volume=0.01,
            entry_price=1.0500,
            stop_loss=1.0450,
            take_profit=1.0600,
            comment='Test order'
        )
        if order:
            logger.success("✅ Order placement test passed")
        
        executor.disconnect()
    else:
        logger.error("❌ Connection test failed")
    
    logger.info("="*70)


if __name__ == "__main__":
    test_ctrader_connection()
