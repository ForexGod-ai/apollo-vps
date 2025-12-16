"""
Test scanner on BTCUSD to validate strategy detection
"""

from daily_scanner import DailyScanner
from smc_detector import SMCDetector
import pandas as pd

def analyze_btc_detailed():
    """Detailed analysis of BTCUSD to see what the scanner finds"""
    
    scanner = DailyScanner()
    
    print("="*60)
    print("🧪 BTCUSD Detailed Analysis - Glitch Strategy Test")
    print("="*60 + "\n")
    
    # Connect MT5
    if not scanner.data_provider.connect():
        print("❌ Failed to connect to MT5")
        return
    
    try:
        # Download BTCUSD data
        print("📊 Downloading BTCUSD data...")
        df_daily = scanner.data_provider.get_historical_data("BTCUSD", "D1", 100)
        df_4h = scanner.data_provider.get_historical_data("BTCUSD", "H4", 200)
        
        if df_daily is None or df_4h is None:
            print("❌ Failed to download BTCUSD data")
            return
        
        print(f"✅ Daily candles: {len(df_daily)}")
        print(f"✅ 4H candles: {len(df_4h)}")
        print(f"📅 Daily range: {df_daily['time'].iloc[0]} to {df_daily['time'].iloc[-1]}")
        print(f"💰 Current price: ${df_daily['close'].iloc[-1]:,.2f}\n")
        
        # Detect CHoCH
        print("🔍 Step 1: Detecting Daily CHoCH...")
        detector = SMCDetector(swing_lookback=5)
        chochs = detector.detect_choch(df_daily)
        
        print(f"   Found {len(chochs)} CHoCH patterns")
        if chochs:
            for i, choch in enumerate(chochs[-5:], 1):  # Show last 5
                print(f"   {i}. {choch.direction.upper()} CHoCH @ ${choch.break_price:,.2f} on {choch.candle_time.date()}")
        print()
        
        # Detect FVGs
        print("🔍 Step 2: Detecting FVGs after CHoCH...")
        fvgs_found = 0
        for choch in chochs:
            fvg = detector.detect_fvg(df_daily, choch)
            if fvg:
                fvgs_found += 1
                is_filled = detector.is_fvg_filled(df_daily, fvg, len(df_daily) - 1)
                status = "FILLED ❌" if is_filled else "ACTIVE ✅"
                print(f"   FVG: ${fvg.bottom:,.2f} - ${fvg.top:,.2f} ({fvg.direction}) - {status}")
        
        if fvgs_found == 0:
            print("   No FVGs found")
        print()
        
        # Check for complete setup
        print("🔍 Step 3: Checking for complete Glitch setup...")
        setup = scanner.smc_detector.scan_for_setup(
            symbol="BTCUSD",
            df_daily=df_daily,
            df_4h=df_4h,
            priority=1
        )
        
        if setup:
            print("🎯 SETUP FOUND! ✅\n")
            print(f"   Direction: {setup.h4_choch.direction.upper()}")
            print(f"   Entry: ${setup.entry_price:,.2f}")
            print(f"   Stop Loss: ${setup.stop_loss:,.2f}")
            print(f"   Take Profit: ${setup.take_profit:,.2f}")
            print(f"   Risk:Reward: 1:{setup.risk_reward:.2f}")
            print(f"   Setup Time: {setup.setup_time}")
        else:
            print("❌ No complete setup detected currently")
            print("\nThis could mean:")
            print("  - No recent CHoCH on Daily")
            print("  - FVG already filled")
            print("  - Price not in FVG zone yet")
            print("  - No 4H confirmation inside FVG")
            print("  - Microtrend validation failed")
    
    finally:
        scanner.data_provider.disconnect()
    
    print("\n" + "="*60)


if __name__ == "__main__":
    analyze_btc_detailed()
