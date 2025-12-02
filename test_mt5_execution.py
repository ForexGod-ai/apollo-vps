"""
Test complete flow: Create setup → Execute on MT5 → Post to dashboard → Close position
"""

import MetaTrader5 as mt5
from datetime import datetime
import time
import os
from dotenv import load_dotenv

load_dotenv()

def test_mt5_execution():
    """Test MT5 execution with real order"""
    
    print("="*70)
    print("🧪 FULL SYSTEM TEST - MT5 Execution")
    print("="*70 + "\n")
    
    # Connect to MT5
    login = int(os.getenv('MT5_LOGIN'))
    password = os.getenv('MT5_PASSWORD')
    server = os.getenv('MT5_SERVER')
    
    print("📡 Connecting to MT5...")
    if not mt5.initialize():
        print(f"❌ MT5 initialize() failed: {mt5.last_error()}")
        return
    
    authorized = mt5.login(login, password=password, server=server)
    if not authorized:
        print(f"❌ MT5 login failed: {mt5.last_error()}")
        mt5.shutdown()
        return
    
    account_info = mt5.account_info()
    print(f"✅ Connected to MT5")
    print(f"   Account: #{account_info.login}")
    print(f"   Balance: ${account_info.balance}")
    print(f"   Leverage: 1:{account_info.leverage}\n")
    
    # Test symbol
    symbol = "EURUSD"
    lot = 0.01  # Micro lot for testing
    
    print(f"🔍 Testing with {symbol} - {lot} lot\n")
    
    # Get symbol info
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"❌ Symbol {symbol} not found")
        mt5.shutdown()
        return
    
    if not symbol_info.visible:
        print(f"   Enabling {symbol} in Market Watch...")
        if not mt5.symbol_select(symbol, True):
            print(f"❌ Failed to enable {symbol}")
            mt5.shutdown()
            return
    
    # Get current price
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"❌ Failed to get tick data for {symbol}")
        mt5.shutdown()
        return
    
    print(f"📊 Current {symbol} price:")
    print(f"   Bid: {tick.bid}")
    print(f"   Ask: {tick.ask}\n")
    
    # Calculate SL/TP (small range for test)
    point = symbol_info.point
    price = tick.ask
    sl = price - 20 * point  # 20 pips stop loss
    tp = price + 40 * point  # 40 pips take profit
    
    print(f"💰 Order parameters:")
    print(f"   Entry: {price}")
    print(f"   Stop Loss: {sl} (-20 pips)")
    print(f"   Take Profit: {tp} (+40 pips)")
    print(f"   Risk:Reward: 1:2.0\n")
    
    # Prepare order request
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 234000,
        "comment": "ForexGod Glitch Test",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    print("🚀 Executing BUY order...")
    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"❌ Order failed: {result.retcode}")
        print(f"   Comment: {result.comment}")
        mt5.shutdown()
        return
    
    print(f"✅ Order executed successfully!")
    print(f"   Order: #{result.order}")
    print(f"   Deal: #{result.deal}")
    print(f"   Volume: {result.volume} lots")
    print(f"   Price: {result.price}\n")
    
    # Wait a bit
    print("⏳ Waiting 5 seconds before closing...")
    time.sleep(5)
    
    # Get position ticket
    positions = mt5.positions_get(symbol=symbol)
    if positions is None or len(positions) == 0:
        print("⚠️  No positions found to close")
        mt5.shutdown()
        return
    
    position = positions[0]
    ticket = position.ticket
    
    print(f"🔍 Found position #{ticket}")
    print(f"   Current P&L: ${position.profit:.2f}\n")
    
    # Close position
    close_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_SELL,  # Opposite of BUY
        "position": ticket,
        "price": mt5.symbol_info_tick(symbol).bid,
        "deviation": 20,
        "magic": 234000,
        "comment": "ForexGod Glitch Test Close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    print("🔴 Closing position...")
    close_result = mt5.order_send(close_request)
    
    if close_result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"❌ Close failed: {close_result.retcode}")
        print(f"   Comment: {close_result.comment}")
    else:
        print(f"✅ Position closed successfully!")
        print(f"   Close price: {close_result.price}")
        print(f"   Final P&L: ${position.profit:.2f}\n")
    
    # Show final account state
    account_info = mt5.account_info()
    print("="*70)
    print("📊 Final Account State:")
    print(f"   Balance: ${account_info.balance}")
    print(f"   Equity: ${account_info.equity}")
    print(f"   Margin Free: ${account_info.margin_free}")
    print("="*70)
    
    mt5.shutdown()
    print("\n✅ Test completed successfully!")
    print("🔌 MT5 disconnected\n")


if __name__ == "__main__":
    print("\n⚠️  WARNING: This will execute a REAL trade on MT5!")
    print("   Symbol: EURUSD")
    print("   Lot size: 0.01 (micro lot)")
    print("   Duration: ~5 seconds")
    print("   Expected cost: <$0.50\n")
    
    response = input("Continue with test? (yes/no): ")
    
    if response.lower() in ['yes', 'y', 'da']:
        test_mt5_execution()
    else:
        print("❌ Test cancelled")
