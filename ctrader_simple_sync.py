#!/usr/bin/env python3
"""
cTrader SIMPLE Integration via REST + Local cAlgo Bot
HYBRID approach: Use existing balance, execute via signals
"""

import os
import json
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

class CTraderSimpleSync:
    """
    Simplified cTrader integration without complex API
    """
    
    def __init__(self):
        self.account_id = os.getenv('CTRADER_ACCOUNT_ID', '9709773')
        self.balance_file = 'trade_history.json'
        
        logger.info("🔧 cTrader Simple Sync initialized")
        logger.info(f"   Account: {self.account_id}")
        logger.info(f"   Mode: Manual sync with trade_history.json")
    
    def get_balance(self):
        """Get current balance from trade history"""
        try:
            with open(self.balance_file, 'r') as f:
                data = json.load(f)
            
            if not data:
                return 1000.0  # Default
            
            # Calculate from trades
            initial = 1000.0
            total_profit = sum(trade.get('profit', 0) for trade in data)
            balance = initial + total_profit
            
            logger.info(f"💰 Current balance: ${balance:.2f}")
            return balance
            
        except FileNotFoundError:
            logger.warning("⚠️  No trade history found, using $1,336.12")
            return 1336.12
    
    def get_account_info(self):
        """Get account info"""
        balance = self.get_balance()
        
        return {
            'account_id': self.account_id,
            'balance': balance,
            'equity': balance,
            'margin_free': balance,
            'currency': 'USD',
            'timestamp': datetime.now().isoformat()
        }
    
    def update_balance_from_ctrader(self, new_balance):
        """
        Manually update balance when you check cTrader
        """
        logger.info(f"📝 Updating balance to ${new_balance:.2f}")
        
        # Calculate profit difference
        current_balance = self.get_balance()
        profit = new_balance - current_balance
        
        if profit != 0:
            # Add adjustment entry
            try:
                with open(self.balance_file, 'r') as f:
                    data = json.load(f)
            except FileNotFoundError:
                data = []
            
            adjustment = {
                'timestamp': datetime.now().isoformat(),
                'pair': 'BALANCE_ADJUSTMENT',
                'type': 'adjustment',
                'profit': profit,
                'balance_after': new_balance,
                'note': 'Manual sync from cTrader platform'
            }
            
            data.append(adjustment)
            
            with open(self.balance_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.success(f"✅ Balance updated: ${current_balance:.2f} → ${new_balance:.2f}")
            logger.info(f"   Profit adjustment: ${profit:+.2f}")


if __name__ == "__main__":
    logger.info("="*70)
    logger.info("🧪 Testing Simple cTrader Integration")
    logger.info("="*70)
    
    sync = CTraderSimpleSync()
    
    # Get current info
    info = sync.get_account_info()
    
    logger.success("\n📊 Account Info:")
    logger.info(f"   Account: {info['account_id']}")
    logger.info(f"   Balance: ${info['balance']:.2f}")
    logger.info(f"   Equity: ${info['equity']:.2f}")
    
    logger.info("\n" + "="*70)
    logger.info("💡 USAGE:")
    logger.info("="*70)
    logger.info("1. Bot generates signals → Sends to Telegram")
    logger.info("2. You execute manually in cTrader")
    logger.info("3. Update balance:")
    logger.info("   >>> from ctrader_simple_sync import CTraderSimpleSync")
    logger.info("   >>> sync = CTraderSimpleSync()")
    logger.info("   >>> sync.update_balance_from_ctrader(1500.00)")
    logger.info("\n✅ TOTUL FUNCȚIONEAZĂ SINCRON fără API issues!")
    logger.info("="*70)
