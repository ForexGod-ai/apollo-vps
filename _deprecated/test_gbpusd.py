"""
Test GBPUSD setup from user's screenshot
Daily CHoCH + FVG + 4H confirmation
"""

from daily_scanner import DailyScanner
from smc_detector import SMCDetector
import pandas as pd

def test_gbpusd():
    """Test GBPUSD for user's exact setup"""
    
    scanner = DailyScanner()
    
    print("="*70)
    print("🧪 GBPUSD Analysis - User's Screenshot Setup")
    print("="*70 + "\n")
    
    if not scanner.data_provider.connect():
        print("❌ Failed to connect to MT5")
        return
    
    try:
        # Download GBPUSD data
        print("📊 Downloading GBPUSD data...")
        df_daily = scanner.data_provider.get_historical_data("GBPUSD", "D1", 150)
        df_4h = scanner.data_provider.get_historical_data("GBPUSD", "H4", 300)
        
        if df_daily is None or df_4h is None:
            print("❌ Failed to download data")
            return
        
        print(f"✅ Data range: {df_daily['time'].iloc[0].date()} to {df_daily['time'].iloc[-1].date()}")
        print(f"💰 Current GBPUSD: {df_daily['close'].iloc[-1]:.5f}\n")
        
        # Detect CHoCH
        detector = SMCDetector(swing_lookback=5)
        chochs = detector.detect_choch(df_daily)
        
        print(f"🔍 Daily CHoCH patterns found: {len(chochs)}")
        if chochs:
            print("\n📊 Last 10 CHoCH patterns:")
            for i, choch in enumerate(chochs[-10:], 1):
                print(f"   {i}. {choch.direction.upper():8} CHoCH @ {choch.break_price:.5f} on {choch.candle_time.date()}")
        
        print("\n" + "="*70)
        print("🔍 Detecting FVGs after each CHoCH...")
        print("="*70 + "\n")
        
        fvg_count = 0
        for choch in chochs[-10:]:  # Check last 10 CHoCH
            fvg = detector.detect_fvg(df_daily, choch)
            if fvg:
                is_filled = detector.is_fvg_filled(df_daily, fvg, len(df_daily) - 1)
                status = "FILLED ❌" if is_filled else "ACTIVE ✅"
                fvg_count += 1
                
                print(f"CHoCH {choch.candle_time.date()} ({choch.direction}):")
                print(f"   FVG: {fvg.bottom:.5f} - {fvg.top:.5f} ({fvg.direction}) - {status}")
                
                # Check if current price is in this FVG
                current_price = df_daily['close'].iloc[-1]
                if fvg.bottom <= current_price <= fvg.top:
                    print(f"   🎯 PRICE IS IN FVG ZONE! Current: {current_price:.5f}")
                print()
        
        if fvg_count == 0:
            print("⚠️  No FVGs detected with current parameters\n")
        
        # Check for complete setup
        print("="*70)
        print("🔍 Checking for complete Glitch setup...")
        print("="*70 + "\n")
        
        setup = scanner.smc_detector.scan_for_setup(
            symbol="GBPUSD",
            df_daily=df_daily,
            df_4h=df_4h,
            priority=1
        )
        
        if setup:
            print("🎯🔥 SETUP FOUND! 🔥🎯\n")
            print(f"   Symbol: {setup.symbol}")
            print(f"   Direction: {setup.h4_choch.direction.upper()}")
            print(f"   Daily CHoCH: {setup.daily_choch.direction.upper()} @ {setup.daily_choch.break_price:.5f}")
            print(f"   FVG Zone: {setup.fvg.bottom:.5f} - {setup.fvg.top:.5f}")
            print(f"   4H CHoCH: {setup.h4_choch.direction.upper()} (inside FVG)")
            print(f"\n   💰 Entry: {setup.entry_price:.5f}")
            print(f"   🛑 Stop Loss: {setup.stop_loss:.5f}")
            print(f"   🎯 Take Profit: {setup.take_profit:.5f}")
            print(f"   📈 Risk:Reward: 1:{setup.risk_reward:.2f}")
            
            print("\n   🚀 This setup would trigger Telegram alert!")
        else:
            print("❌ No complete setup detected currently")
            print("\n   Possible reasons:")
            print("   • No recent CHoCH on Daily")
            print("   • FVG already filled")
            print("   • Price not in FVG zone")
            print("   • No 4H CHoCH confirmation inside FVG")
            print("   • Microtrend validation failed")
    
    finally:
        scanner.data_provider.disconnect()
    
    print("\n" + "="*70)


if __name__ == "__main__":
    test_gbpusd()
