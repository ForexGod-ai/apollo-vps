"""
cTrader Signal Executor - writes to signals.json for PythonSignalExecutor cBot
"""

import json
import os
from datetime import datetime
from loguru import logger
from typing import Optional


class CTraderExecutor:
    """
    Writes trading signals to signals.json
    PythonSignalExecutor cBot will read and execute them automatically
    """
    
    def __init__(self, signals_file: str = "signals.json"):
        self.signals_file = signals_file
        logger.info(f"🤖 CTraderExecutor initialized - writing to {signals_file}")
    
    def execute_trade(self, symbol: str, direction: str, entry_price: float, 
                     stop_loss: float, take_profit: float, lot_size: float = 0.01,
                     comment: str = ""):
        """
        Write a trade signal to signals.json for PythonSignalExecutor to execute
        
        Args:
            symbol: Trading pair (e.g., 'EURUSD')
            direction: 'BUY' or 'SELL'
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            lot_size: Position size in lots (default 0.01)
            comment: Optional comment for the trade
        """
        try:
            signal = {
                "symbol": symbol,
                "action": direction.upper(),
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "lot_size": lot_size,
                "comment": comment or f"AI {direction} {symbol}",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "morning_scanner"
            }
            
            # Read existing signals
            signals = []
            if os.path.exists(self.signals_file):
                try:
                    with open(self.signals_file, 'r') as f:
                        signals = json.load(f)
                        if not isinstance(signals, list):
                            signals = []
                except:
                    signals = []
            
            # Add new signal
            signals.append(signal)
            
            # Write back
            with open(self.signals_file, 'w') as f:
                json.dump(signals, f, indent=2)
            
            logger.success(f"✅ Signal written: {direction} {symbol} @ {entry_price} (SL: {stop_loss}, TP: {take_profit})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to write signal: {e}")
            return False
    
    def clear_signals(self):
        """Clear all signals from signals.json"""
        try:
            with open(self.signals_file, 'w') as f:
                json.dump([], f)
            logger.info(f"🗑️  Cleared all signals from {self.signals_file}")
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
