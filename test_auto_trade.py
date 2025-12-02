"""
Quick test to execute one trade manually
"""
from auto_trader import AutoTrader
from loguru import logger

logger.info("🧪 Testing Auto Trader - Manual Single Trade")

# Initialize trader
trader = AutoTrader()

# Run one cycle
logger.info("▶️ Running one scan cycle...")
trader.run_once()

# Check results
logger.info(f"\n📊 Results:")
logger.info(f"   • Trades executed today: {trader.trades_today}")
logger.info(f"   • Active positions: {len(trader.active_trades)}")
logger.info(f"   • Processed setups: {len(trader.processed_setups)}")

if trader.active_trades:
    logger.info(f"\n🎯 Active Trades:")
    for trade in trader.active_trades:
        logger.info(f"   • #{trade.ticket} {trade.symbol} {trade.direction} "
                   f"Entry: {trade.entry_price}, SL: {trade.stop_loss}, TP: {trade.take_profit}")

# Disconnect
trader.executor.disconnect()
logger.info("\n✅ Test complete!")
