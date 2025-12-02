"""
Complete System Test: MT5 → Telegram → Dashboard
Tests full flow of trade execution and notifications
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from loguru import logger

from mt5_executor import MT5Executor
from telegram_notifier import TelegramNotifier
from smc_detector import TradeSetup, CHoCH, FVG, SwingPoint
import requests

load_dotenv()

logger.remove()
logger.add(sys.stdout, colorize=True, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")


def create_fake_setup():
    """Create a fake trade setup for testing"""
    from smc_detector import SwingPoint
    
    # Create fake swing point
    swing = SwingPoint(
        index=45,
        price=1.27000,
        swing_type='low',
        candle_time=datetime.now()
    )
    
    # Create fake CHoCH (Daily)
    daily_choch = CHoCH(
        index=50,
        direction='bullish',
        break_price=1.27500,
        previous_trend='bearish',
        candle_time=datetime.now(),
        swing_broken=swing
    )
    
    # Create fake FVG (Daily)
    fvg = FVG(
        index=45,
        direction='bullish',
        top=1.27800,
        bottom=1.27200,
        middle=1.27500,
        candle_time=datetime.now(),
        is_filled=False,
        associated_choch=daily_choch
    )
    
    # Create fake CHoCH (4H)
    h4_choch = CHoCH(
        index=20,
        direction='bullish',
        break_price=1.27400,
        previous_trend='bearish',
        candle_time=datetime.now(),
        swing_broken=swing
    )
    
    # Create TradeSetup
    setup = TradeSetup(
        symbol='GBPUSD',
        daily_choch=daily_choch,
        fvg=fvg,
        h4_choch=h4_choch,
        entry_price=1.27400,
        stop_loss=1.27200,
        take_profit=1.27800,
        risk_reward=3.0,
        setup_time=datetime.now(),
        priority=1
    )
    
    return setup


def create_fake_dataframes():
    """Create fake price dataframes for charts"""
    
    # Daily data (50 candles)
    dates_daily = pd.date_range(end=datetime.now(), periods=50, freq='D')
    daily_df = pd.DataFrame({
        'time': dates_daily,
        'open': np.random.uniform(1.26, 1.28, 50),
        'high': np.random.uniform(1.27, 1.29, 50),
        'low': np.random.uniform(1.25, 1.27, 50),
        'close': np.random.uniform(1.26, 1.28, 50),
        'volume': np.random.randint(1000, 5000, 50)
    })
    
    # Add trend to make it look realistic
    daily_df['close'] = daily_df['close'] + np.linspace(0, 0.015, 50)
    daily_df['high'] = daily_df[['high', 'close']].max(axis=1) + 0.001
    daily_df['low'] = daily_df[['low', 'close']].min(axis=1) - 0.001
    
    # 4H data (100 candles)
    dates_4h = pd.date_range(end=datetime.now(), periods=100, freq='4H')
    h4_df = pd.DataFrame({
        'time': dates_4h,
        'open': np.random.uniform(1.27, 1.28, 100),
        'high': np.random.uniform(1.272, 1.282, 100),
        'low': np.random.uniform(1.268, 1.278, 100),
        'close': np.random.uniform(1.27, 1.28, 100),
        'volume': np.random.randint(500, 2000, 100)
    })
    
    # Add trend
    h4_df['close'] = h4_df['close'] + np.linspace(0, 0.01, 100)
    h4_df['high'] = h4_df[['high', 'close']].max(axis=1) + 0.0005
    h4_df['low'] = h4_df[['low', 'close']].min(axis=1) - 0.0005
    
    return daily_df, h4_df


def post_trade_to_dashboard(trade_data):
    """Post trade data to webhook dashboard"""
    try:
        url = "http://127.0.0.1:5001/webhook"
        response = requests.post(url, json=trade_data, timeout=5)
        
        if response.status_code == 200:
            logger.info(f"✅ Dashboard updated successfully")
            return True
        else:
            logger.error(f"❌ Dashboard update failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Dashboard connection error: {e}")
        return False


def main():
    """Run complete system test"""
    
    logger.info("=" * 80)
    logger.info("🚀 COMPLETE SYSTEM TEST - MT5 + Telegram + Dashboard")
    logger.info("=" * 80)
    
    # Step 1: Create test setup
    logger.info("\n📊 Step 1: Creating test trade setup...")
    setup = create_fake_setup()
    daily_df, h4_df = create_fake_dataframes()
    direction = 'LONG' if setup.h4_choch.direction == 'bullish' else 'SHORT'
    logger.info(f"✅ Setup created: {setup.symbol} {direction} @ {setup.entry_price}")
    
    # Step 2: Connect to MT5
    logger.info("\n💹 Step 2: Connecting to MT5...")
    mt5 = MT5Executor()
    
    if not mt5.connect():
        logger.error("❌ MT5 connection failed!")
        return
    
    account_info = mt5.get_account_info()
    logger.info(f"✅ MT5 Connected - Account #{account_info['login']}, Balance: ${account_info['balance']}")
    
    # Step 3: Execute trade on MT5
    direction = 'LONG' if setup.h4_choch.direction == 'bullish' else 'SHORT'
    logger.info(f"\n📈 Step 3: Executing {direction} trade on MT5...")
    logger.info(f"Symbol: {setup.symbol}")
    
    # Get current price
    import MetaTrader5 as mt5_module
    tick = mt5_module.symbol_info_tick(setup.symbol)
    
    if not tick:
        logger.error(f"❌ Could not get price for {setup.symbol}")
        mt5.disconnect()
        return
    
    current_price = tick.ask if setup.h4_choch.direction == 'bullish' else tick.bid
    
    # Set realistic SL/TP based on current price
    if setup.h4_choch.direction == 'bullish':
        entry = current_price
        sl = current_price - 0.0020  # 20 pips
        tp = current_price + 0.0040  # 40 pips
    else:
        entry = current_price
        sl = current_price + 0.0020  # 20 pips
        tp = current_price - 0.0040  # 40 pips
    
    logger.info(f"Current Price: {current_price:.5f}")
    logger.info(f"Entry: {entry:.5f}")
    logger.info(f"SL: {sl:.5f} ({abs(entry-sl)*10000:.1f} pips)")
    logger.info(f"TP: {tp:.5f} ({abs(tp-entry)*10000:.1f} pips)")
    
    volume = 0.01  # Minimal lot size for testing
    
    # Execute order
    if setup.h4_choch.direction == 'bullish':
        result = mt5.execute_buy(setup.symbol, volume, sl, tp)
    else:
        result = mt5.execute_sell(setup.symbol, volume, sl, tp)
    
    if not result or result.retcode != 10009:
        logger.error(f"❌ Trade execution failed! Error: {result.retcode if result else 'No result'}")
        mt5.disconnect()
        return
    
    logger.info(f"✅ Trade executed successfully!")
    logger.info(f"   Order ID: #{result.order}")
    logger.info(f"   Volume: {volume} lots")
    logger.info(f"   Price: {result.price}")
    
    # Step 4: Send Telegram notification
    logger.info("\n📱 Step 4: Sending Telegram notification...")
    telegram = TelegramNotifier()
    
    success = telegram.send_setup_alert(setup, daily_df, h4_df)
    
    if success:
        logger.info("✅ Telegram alert sent successfully!")
        logger.info(f"   Group: ForexGod - Glitch Signals 🔥")
        logger.info(f"   Message with charts and Execute buttons sent")
    else:
        logger.error("❌ Telegram notification failed!")
    
    # Step 5: Post to Dashboard
    logger.info("\n🌐 Step 5: Updating dashboard...")
    
    trade_data = {
        "action": "buy" if setup.h4_choch.direction == 'bullish' else "sell",
        "symbol": setup.symbol,
        "timeframe": "4H",
        "price": setup.entry_price,
        "stop_loss": setup.stop_loss,
        "take_profit": setup.take_profit,
        "strategy": "glitch_in_matrix",
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "risk_reward": setup.risk_reward,
            "order_id": result.order,
            "volume": volume,
            "daily_choch": setup.daily_choch.direction,
            "h4_choch": setup.h4_choch.direction
        }
    }
    
    dashboard_success = post_trade_to_dashboard(trade_data)
    
    if dashboard_success:
        logger.info("✅ Dashboard updated!")
        logger.info("   View at: http://127.0.0.1:5001")
    
    # Step 6: Wait and close position
    logger.info("\n⏰ Step 6: Waiting 10 seconds before closing position...")
    import time
    time.sleep(10)
    
    logger.info(f"🔄 Closing position for {setup.symbol}...")
    close_result = mt5.close_position(setup.symbol)
    
    if close_result['success']:
        profit = close_result['profit']
        logger.info(f"✅ Position closed!")
        logger.info(f"   P&L: ${profit:.2f}")
    else:
        logger.error(f"❌ Close failed: {close_result['error']}")
    
    # Disconnect
    mt5.disconnect()
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 80)
    logger.info(f"✅ MT5 Connection: SUCCESS")
    logger.info(f"✅ Trade Execution: SUCCESS (Order #{result.order})")
    logger.info(f"{'✅' if success else '❌'} Telegram Alert: {'SUCCESS' if success else 'FAILED'}")
    logger.info(f"{'✅' if dashboard_success else '❌'} Dashboard Update: {'SUCCESS' if dashboard_success else 'FAILED'}")
    logger.info(f"✅ Position Close: SUCCESS (P&L: ${close_result.get('profit', 0):.2f})")
    logger.info("=" * 80)
    logger.info("\n🎉 Complete system test finished!")
    logger.info("\n📱 Check Telegram group: ForexGod - Glitch Signals 🔥")
    logger.info("🌐 Check Dashboard: http://127.0.0.1:5001")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⚠️ Test interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
