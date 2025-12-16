#!/usr/bin/env python3
"""
Test script for live balance fetching from cTrader
"""

from loguru import logger
import sys

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
)

def test_ctrader_balance():
    """Test fetching live balance from cTrader"""
    
    logger.info("="*70)
    logger.info("🧪 TESTING LIVE BALANCE FETCH FROM CTRADER")
    logger.info("="*70)
    
    # Test 1: CTraderDataClient
    logger.info("\n📊 Test 1: CTraderDataClient.get_account_balance()")
    try:
        from ctrader_data_client import CTraderDataClient
        
        client = CTraderDataClient()
        balance_info = client.get_account_balance()
        
        if balance_info:
            logger.success("✅ Balance fetched successfully!")
            logger.info(f"   Account ID: {balance_info['account_id']}")
            logger.info(f"   Balance: ${balance_info['balance']:.2f}")
            logger.info(f"   Equity: ${balance_info['equity']:.2f}")
            logger.info(f"   Profit: ${balance_info.get('profit', 0):.2f}")
            logger.info(f"   Currency: {balance_info['currency']}")
            logger.info(f"   Open Positions: {balance_info.get('open_positions', 0)}")
            logger.info(f"   Closed Trades: {balance_info.get('closed_trades', 0)}")
        else:
            logger.error("❌ Failed to fetch balance")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    
    # Test 2: CTraderExecutor
    logger.info("\n📊 Test 2: CTraderExecutor.get_account_info()")
    try:
        from ctrader_executor import CTraderExecutor
        
        executor = CTraderExecutor()
        if executor.connect():
            account_info = executor.get_account_info()
            
            if account_info:
                logger.success("✅ Account info fetched via executor!")
                logger.info(f"   Balance: ${account_info['balance']:.2f}")
                logger.info(f"   Equity: ${account_info['equity']:.2f}")
            else:
                logger.error("❌ Failed to fetch account info")
        else:
            logger.error("❌ Failed to connect executor")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    
    # Test 3: MoneyManager with live balance
    logger.info("\n💰 Test 3: MoneyManager with LIVE balance")
    try:
        from money_manager import MoneyManager
        
        mm = MoneyManager(broker_type='CTRADER')
        logger.success(f"✅ MoneyManager initialized with live balance: ${mm.account_balance:.2f}")
        logger.info(f"   Risk per trade: {mm.risk_per_trade*100}%")
        logger.info(f"   Max positions: {mm.max_positions}")
        logger.info(f"   Max daily loss: ${mm.max_daily_loss:.2f}")
        
        # Test balance refresh
        logger.info("\n🔄 Testing balance refresh...")
        mm.refresh_balance()
        logger.success(f"✅ Balance after refresh: ${mm.account_balance:.2f}")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    
    # Test 4: BrokerManager with cTrader
    logger.info("\n🔌 Test 4: BrokerManager with cTrader")
    try:
        from broker_manager import BrokerManager
        
        broker = BrokerManager()
        logger.info(f"   Default broker: {broker.default_broker}")
        
        if broker.active_broker:
            logger.success("✅ Active broker connected")
            
            account_info = broker.get_account_info()
            if account_info:
                logger.success("✅ Account info from BrokerManager:")
                logger.info(f"   Balance: ${account_info['balance']:.2f}")
                logger.info(f"   Equity: ${account_info['equity']:.2f}")
            
            positions = broker.get_open_positions()
            logger.info(f"   Open positions: {len(positions)}")
            
        else:
            logger.error("❌ No active broker")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    
    logger.info("\n" + "="*70)
    logger.info("🏁 TESTING COMPLETE")
    logger.info("="*70)


if __name__ == "__main__":
    test_ctrader_balance()
