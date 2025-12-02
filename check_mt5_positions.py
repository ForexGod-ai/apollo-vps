"""
Check active trades on MT5
"""
import MetaTrader5 as mt5
from mt5_executor import MT5Executor
from loguru import logger

logger.info("🔍 Checking active trades on MT5...")

executor = MT5Executor()
if executor.connect():
    # Get account info
    account_info = executor.get_account_info()
    logger.info(f"\n📊 Account Info:")
    logger.info(f"   • Balance: ${account_info['balance']:.2f}")
    logger.info(f"   • Equity: ${account_info['equity']:.2f}")
    logger.info(f"   • Profit: ${account_info['profit']:.2f}")
    logger.info(f"   • Margin Free: ${account_info['margin_free']:.2f}")
    
    # Get positions
    positions = mt5.positions_get()
    
    if positions:
        logger.info(f"\n🎯 Active Positions: {len(positions)}")
        for pos in positions:
            direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
            logger.info(f"\n   Ticket #{pos.ticket}")
            logger.info(f"   • Symbol: {pos.symbol} {direction}")
            logger.info(f"   • Entry: {pos.price_open}")
            logger.info(f"   • Current: {pos.price_current}")
            logger.info(f"   • SL: {pos.sl}")
            logger.info(f"   • TP: {pos.tp}")
            logger.info(f"   • Volume: {pos.volume}")
            logger.info(f"   • Profit: ${pos.profit:.2f}")
    else:
        logger.warning("❌ No active positions")
    
    executor.disconnect()
else:
    logger.error("❌ Failed to connect to MT5")
