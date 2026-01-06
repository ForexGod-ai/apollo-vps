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
                     comment: str = "", status: str = "READY"):
        """
        Write a trade signal to signals.json for PythonSignalExecutor to execute
        
        Args:
            symbol: Trading pair (e.g., 'EURUSD')
            direction: 'BUY' or 'SELL'
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            lot_size: Position size in lots (ignored - cBot calculates based on risk %)
            comment: Optional comment for the trade
            status: Setup status - MUST be 'READY' to execute (V3.0)
        
        Note: cBot expects prices AND pips. Direction must be lowercase.
        """
        # V3.0 STRICT EXECUTION BLOCKER:
        # Only execute if status is 'READY' (4H confirmed + price in FVG)
        if status != 'READY':
            logger.warning(f"⛔ EXECUTION BLOCKED: {symbol} status is '{status}' (must be 'READY')")
            logger.info(f"   Setup is in MONITORING phase - waiting for:")
            logger.info(f"   1. 4H CHoCH confirmation (same direction as Daily)")
            logger.info(f"   2. Price to enter FVG zone")
            return False
        
        try:
            # Generate unique signal ID
            signal_id = f"{symbol}_{direction}_{int(datetime.now().timestamp())}"
            
            # Calculate pip size based on instrument type
            # Crypto (BTC, ETH, etc.): 1 pip = 1.0 (whole price)
            # JPY pairs: 1 pip = 0.01
            # Other forex: 1 pip = 0.0001
            # Gold/Silver: 1 pip = 0.01
            if symbol in ['BTCUSD', 'ETHUSD', 'XRPUSD', 'LTCUSD']:
                pip_size = 1.0
            elif 'JPY' in symbol:
                pip_size = 0.01
            elif symbol in ['XAUUSD', 'XAGUSD']:  # Gold, Silver
                pip_size = 0.01
            else:
                pip_size = 0.0001
            
            sl_pips = abs(entry_price - stop_loss) / pip_size
            tp_pips = abs(take_profit - entry_price) / pip_size
            
            signal = {
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
                "Timestamp": datetime.now().isoformat()
            }
            
            # Write SINGLE signal (cBot expects object, not array)
            with open(self.signals_file, 'w') as f:
                json.dump(signal, f, indent=2)
            
            logger.success(f"✅ Signal written: {direction} {symbol} @ {entry_price} (SL: {sl_pips:.1f} pips, TP: {tp_pips:.1f} pips)")
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
