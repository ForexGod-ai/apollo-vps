"""
Close wrong trades (GBPUSD and NZDCAD - against macro trend)
"""
from mt5_executor import MT5Executor
from loguru import logger
import json

logger.info("🔧 Closing trades that are against macro trend...")

# Load trade history
with open('trade_history.json', 'r') as f:
    trades = json.load(f)

executor = MT5Executor()

if executor.connect():
    # Close GBPUSD and NZDCAD (wrong trades)
    symbols_to_close = ['GBPUSD', 'NZDCAD']
    
    for symbol in symbols_to_close:
        logger.info(f"\n🔴 Closing {symbol} (against macro trend)...")
        result = executor.close_position(symbol)
        
        if result['success']:
            logger.info(f"✅ {symbol} closed: Profit ${result['profit']:.2f}")
            
            # Update trade history
            for trade in trades:
                if trade['symbol'] == symbol and trade['status'] == 'OPEN':
                    trade['status'] = 'CLOSED_MANUAL'
                    trade['profit'] = result['profit']
                    break
        else:
            logger.error(f"❌ Failed to close {symbol}: {result.get('error', 'Unknown error')}")
    
    # Save updated history
    with open('trade_history.json', 'w') as f:
        json.dump(trades, f, indent=2)
    
    # Keep BTCUSD open
    logger.info(f"\n✅ BTCUSD SELL remains open (correct macro trend)")
    
    executor.disconnect()
else:
    logger.error("❌ Failed to connect to MT5")
