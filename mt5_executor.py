"""
MT5 Executor - Execute trades on MetaTrader 5
"""
import MetaTrader5 as mt5
from loguru import logger
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


class MT5Executor:
    """Execute trades on MT5"""
    
    def __init__(self):
        self.login = int(os.getenv('MT5_LOGIN'))
        self.password = os.getenv('MT5_PASSWORD')
        self.server = os.getenv('MT5_SERVER')
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to MT5"""
        try:
            if not mt5.initialize():
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return False
            
            if not mt5.login(self.login, self.password, self.server):
                logger.error(f"MT5 login failed: {mt5.last_error()}")
                return False
            
            account_info = mt5.account_info()
            logger.info(f"✅ Connected to MT5: Account #{account_info.login}, Balance: ${account_info.balance}")
            self.connected = True
            return True
        
        except Exception as e:
            logger.error(f"MT5 connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MT5"""
        mt5.shutdown()
        self.connected = False
    
    def execute_buy(self, symbol: str, volume: float, sl: float, tp: float):
        """Execute BUY order"""
        try:
            if not self.connected:
                if not self.connect():
                    return None
            
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logger.error(f"Symbol {symbol} not found")
                return None
            
            # Enable symbol
            if not symbol_info.visible:
                if not mt5.symbol_select(symbol, True):
                    logger.error(f"Failed to select {symbol}")
                    return None
            
            # Prepare order
            point = symbol_info.point
            price = mt5.symbol_info_tick(symbol).ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 234000,
                "comment": "ForexGod-Glitch",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send order
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Order failed: {result.retcode} - {result.comment}")
            else:
                logger.info(f"✅ BUY order executed: {symbol}, Order #{result.order}, Volume: {volume}")
            
            return result
        
        except Exception as e:
            logger.error(f"Execute BUY error: {e}")
            return None
    
    def execute_sell(self, symbol: str, volume: float, sl: float, tp: float):
        """Execute SELL order"""
        try:
            if not self.connected:
                if not self.connect():
                    return None
            
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logger.error(f"Symbol {symbol} not found")
                return None
            
            # Enable symbol
            if not symbol_info.visible:
                if not mt5.symbol_select(symbol, True):
                    logger.error(f"Failed to select {symbol}")
                    return None
            
            # Prepare order
            point = symbol_info.point
            price = mt5.symbol_info_tick(symbol).bid
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_SELL,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 234000,
                "comment": "ForexGod-Glitch",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send order
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Order failed: {result.retcode} - {result.comment}")
            else:
                logger.info(f"✅ SELL order executed: {symbol}, Order #{result.order}, Volume: {volume}")
            
            return result
        
        except Exception as e:
            logger.error(f"Execute SELL error: {e}")
            return None
    
    def close_position(self, symbol: str):
        """Close open position for symbol"""
        try:
            if not self.connected:
                if not self.connect():
                    return {"success": False, "error": "Not connected"}
            
            # Get open positions
            positions = mt5.positions_get(symbol=symbol)
            
            if positions is None or len(positions) == 0:
                return {"success": False, "error": "No open position"}
            
            position = positions[0]
            
            # Prepare close request
            tick = mt5.symbol_info_tick(symbol)
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": position.volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "position": position.ticket,
                "price": tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask,
                "deviation": 20,
                "magic": 234000,
                "comment": "Close by ForexGod",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send close order
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {"success": False, "error": f"Close failed: {result.comment}"}
            else:
                profit = position.profit
                logger.info(f"✅ Position closed: {symbol}, Profit: ${profit:.2f}")
                return {"success": True, "profit": profit}
        
        except Exception as e:
            logger.error(f"Close position error: {e}")
            return {"success": False, "error": str(e)}
    
    def get_account_info(self):
        """Get account information"""
        try:
            if not self.connected:
                if not self.connect():
                    return None
            
            account_info = mt5.account_info()
            return {
                "login": account_info.login,
                "balance": account_info.balance,
                "equity": account_info.equity,
                "profit": account_info.profit,
                "margin": account_info.margin,
                "margin_free": account_info.margin_free,
                "leverage": account_info.leverage
            }
        except Exception as e:
            logger.error(f"Get account info error: {e}")
            return None


if __name__ == "__main__":
    """Test MT5 executor"""
    print("🧪 Testing MT5 Executor...")
    
    executor = MT5Executor()
    if executor.connect():
        info = executor.get_account_info()
        print(f"✅ Account #{info['login']}")
        print(f"Balance: ${info['balance']}")
        print(f"Equity: ${info['equity']}")
        print(f"Leverage: 1:{info['leverage']}")
        executor.disconnect()
    else:
        print("❌ MT5 connection failed")
