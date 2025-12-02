"""
Test Telegram messages with fake setup
Shows how alerts will look when real setups are found
"""

from telegram_notifier import TelegramNotifier
from smc_detector import TradeSetup, CHoCH, FVG, SwingPoint
from datetime import datetime
import pandas as pd
import numpy as np

def create_fake_setup(symbol: str, direction: str, priority: int):
    """Create a fake trade setup for testing Telegram messages"""
    
    # Create fake swing point
    fake_swing = SwingPoint(
        index=50,
        price=1.35000 if symbol == "GBPUSD" else 95000.0,
        swing_type='low' if direction == 'bullish' else 'high',
        candle_time=datetime(2025, 11, 20, 0, 0)
    )
    
    # Create fake Daily CHoCH
    if direction == 'bullish':
        daily_choch = CHoCH(
            index=55,
            direction='bullish',
            break_price=1.35200 if symbol == "GBPUSD" else 96000.0,
            previous_trend='bearish',
            candle_time=datetime(2025, 11, 25, 0, 0),
            swing_broken=fake_swing
        )
        
        # Create fake FVG
        fvg = FVG(
            index=57,
            direction='bullish',
            top=1.34800 if symbol == "GBPUSD" else 94500.0,
            bottom=1.34500 if symbol == "GBPUSD" else 93000.0,
            middle=1.34650 if symbol == "GBPUSD" else 93750.0,
            candle_time=datetime(2025, 11, 26, 0, 0),
            is_filled=False,
            associated_choch=daily_choch
        )
        
        # Create fake 4H CHoCH
        h4_choch = CHoCH(
            index=120,
            direction='bullish',
            break_price=1.34700 if symbol == "GBPUSD" else 94000.0,
            previous_trend='bearish',
            candle_time=datetime(2025, 12, 1, 4, 0),
            swing_broken=fake_swing
        )
        
        # Entry/SL/TP for LONG
        entry = fvg.middle
        stop_loss = fvg.bottom - (fvg.top - fvg.bottom) * 0.2
        take_profit = entry + (entry - stop_loss) * 2.0
        
    else:  # bearish
        daily_choch = CHoCH(
            index=55,
            direction='bearish',
            break_price=1.33800 if symbol == "GBPUSD" else 102000.0,
            previous_trend='bullish',
            candle_time=datetime(2025, 11, 25, 0, 0),
            swing_broken=fake_swing
        )
        
        fvg = FVG(
            index=57,
            direction='bearish',
            top=1.34500 if symbol == "GBPUSD" else 104000.0,
            bottom=1.34200 if symbol == "GBPUSD" else 103000.0,
            middle=1.34350 if symbol == "GBPUSD" else 103500.0,
            candle_time=datetime(2025, 11, 26, 0, 0),
            is_filled=False,
            associated_choch=daily_choch
        )
        
        h4_choch = CHoCH(
            index=120,
            direction='bearish',
            break_price=1.34300 if symbol == "GBPUSD" else 103200.0,
            previous_trend='bullish',
            candle_time=datetime(2025, 12, 1, 4, 0),
            swing_broken=fake_swing
        )
        
        # Entry/SL/TP for SHORT
        entry = fvg.middle
        stop_loss = fvg.top + (fvg.top - fvg.bottom) * 0.2
        take_profit = entry - (stop_loss - entry) * 2.0
    
    risk_reward = abs(take_profit - entry) / abs(entry - stop_loss)
    
    setup = TradeSetup(
        symbol=symbol,
        daily_choch=daily_choch,
        fvg=fvg,
        h4_choch=h4_choch,
        entry_price=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward=risk_reward,
        setup_time=datetime.now(),
        priority=priority
    )
    
    return setup


def create_fake_dataframes(symbol: str):
    """Create fake price data for chart generation"""
    
    # Create fake Daily data
    dates_daily = pd.date_range(start='2025-09-01', periods=60, freq='D')
    
    if symbol == "GBPUSD":
        prices = np.linspace(1.32, 1.35, 60) + np.random.randn(60) * 0.003
    else:
        prices = np.linspace(90000, 104000, 60) + np.random.randn(60) * 2000
    
    df_daily = pd.DataFrame({
        'time': dates_daily,
        'open': prices + np.random.randn(60) * 0.001,
        'high': prices + abs(np.random.randn(60)) * 0.002,
        'low': prices - abs(np.random.randn(60)) * 0.002,
        'close': prices,
        'volume': np.random.randint(1000, 5000, 60)
    })
    
    # Create fake 4H data
    dates_4h = pd.date_range(start='2025-11-15', periods=120, freq='4H')
    
    if symbol == "GBPUSD":
        prices_4h = np.linspace(1.34, 1.345, 120) + np.random.randn(120) * 0.001
    else:
        prices_4h = np.linspace(102000, 103500, 120) + np.random.randn(120) * 500
    
    df_4h = pd.DataFrame({
        'time': dates_4h,
        'open': prices_4h + np.random.randn(120) * 0.0005,
        'high': prices_4h + abs(np.random.randn(120)) * 0.001,
        'low': prices_4h - abs(np.random.randn(120)) * 0.001,
        'close': prices_4h,
        'volume': np.random.randint(500, 2000, 120)
    })
    
    return df_daily, df_4h


def test_telegram_messages():
    """Send test messages to Telegram"""
    
    print("="*70)
    print("🧪 Testing Telegram Messages - ForexGod Glitch Signals")
    print("="*70 + "\n")
    
    notifier = TelegramNotifier()
    
    # Test connection
    print("📱 Testing Telegram connection...")
    if not notifier.test_connection():
        print("❌ Failed to connect to Telegram")
        return
    
    print("✅ Telegram connected!\n")
    
    # Test 1: Bearish setup (HIGH PRIORITY - REVERSAL)
    print("🔥 Test 1: REVERSAL Setup - GBPUSD SHORT (Priority 1)")
    print("-" * 70)
    
    setup_bearish = create_fake_setup("GBPUSD", "bearish", priority=1)
    df_daily, df_4h = create_fake_dataframes("GBPUSD")
    
    print(f"   Symbol: {setup_bearish.symbol}")
    print(f"   Direction: SHORT")
    print(f"   Entry: {setup_bearish.entry_price:.5f}")
    print(f"   SL: {setup_bearish.stop_loss:.5f}")
    print(f"   TP: {setup_bearish.take_profit:.5f}")
    print(f"   R:R: 1:{setup_bearish.risk_reward:.2f}")
    
    print("\n   📤 Sending to Telegram...")
    success = notifier.send_setup_alert(setup_bearish, df_daily, df_4h)
    
    if success:
        print("   ✅ Message sent successfully!")
    else:
        print("   ❌ Failed to send message")
    
    print("\n" + "="*70 + "\n")
    
    # Wait a bit between messages
    import time
    time.sleep(2)
    
    # Test 2: Bullish setup (CONTINUATION)
    print("💎 Test 2: CONTINUATION Setup - BTCUSD LONG (Priority 1)")
    print("-" * 70)
    
    setup_bullish = create_fake_setup("BTCUSD", "bullish", priority=1)
    df_daily_btc, df_4h_btc = create_fake_dataframes("BTCUSD")
    
    print(f"   Symbol: {setup_bullish.symbol}")
    print(f"   Direction: LONG")
    print(f"   Entry: ${setup_bullish.entry_price:,.2f}")
    print(f"   SL: ${setup_bullish.stop_loss:,.2f}")
    print(f"   TP: ${setup_bullish.take_profit:,.2f}")
    print(f"   R:R: 1:{setup_bullish.risk_reward:.2f}")
    
    print("\n   📤 Sending to Telegram...")
    success = notifier.send_setup_alert(setup_bullish, df_daily_btc, df_4h_btc)
    
    if success:
        print("   ✅ Message sent successfully!")
    else:
        print("   ❌ Failed to send message")
    
    print("\n" + "="*70 + "\n")
    
    # Test 3: Daily summary
    time.sleep(2)
    
    print("📊 Test 3: Daily Scan Summary")
    print("-" * 70)
    
    print("\n   📤 Sending summary...")
    success = notifier.send_daily_summary(scanned_pairs=18, setups_found=2)
    
    if success:
        print("   ✅ Summary sent successfully!")
    else:
        print("   ❌ Failed to send summary")
    
    print("\n" + "="*70)
    print("✅ Test complete! Check your Telegram group for messages!")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_telegram_messages()
