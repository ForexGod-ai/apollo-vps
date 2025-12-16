"""
Detailed backtest for user's BTC SHORT trades
Entry 1: Oct 31, 2025
Entry 2: Nov 11, 2025
"""

from daily_scanner import DailyScanner
from smc_detector import SMCDetector
import pandas as pd
from datetime import datetime

def backtest_user_trades():
    """Check if algorithm would have detected user's BTC SHORT setups"""
    
    scanner = DailyScanner()
    
    print("="*70)
    print("🎯 BACKTEST: User's BTC SHORT Trades - Glitch Strategy")
    print("="*70 + "\n")
    
    if not scanner.data_provider.connect():
        print("❌ Failed to connect to MT5")
        return
    
    try:
        # Download data
        print("📊 Downloading BTCUSD data (150 days)...")
        df_daily = scanner.data_provider.get_historical_data("BTCUSD", "D1", 150)
        df_4h = scanner.data_provider.get_historical_data("BTCUSD", "H4", 300)
        
        if df_daily is None or df_4h is None:
            print("❌ Failed to download data")
            return
        
        print(f"✅ Data range: {df_daily['time'].iloc[0].date()} to {df_daily['time'].iloc[-1].date()}\n")
        
        # Find data around entry dates
        entry1_date = datetime(2025, 10, 31)
        entry2_date = datetime(2025, 11, 11)
        
        # Find closest candles to entry dates
        df_daily['date_only'] = df_daily['time'].dt.date
        
        idx1 = df_daily[df_daily['time'] >= entry1_date].index[0] if len(df_daily[df_daily['time'] >= entry1_date]) > 0 else None
        idx2 = df_daily[df_daily['time'] >= entry2_date].index[0] if len(df_daily[df_daily['time'] >= entry2_date]) > 0 else None
        
        print("="*70)
        print("📅 ENTRY 1: October 31, 2025 (SHORT)")
        print("="*70)
        
        if idx1:
            # Show price action around entry 1
            start_idx = max(0, idx1 - 10)
            end_idx = min(len(df_daily), idx1 + 5)
            
            print("\n📊 Daily candles around Oct 31:")
            for i in range(start_idx, end_idx):
                marker = " 👉 ENTRY" if i == idx1 else ""
                print(f"   {df_daily['time'].iloc[i].date()} | Close: ${df_daily['close'].iloc[i]:,.2f}{marker}")
            
            price_at_entry1 = df_daily['close'].iloc[idx1]
            print(f"\n💰 Price at entry: ${price_at_entry1:,.2f}")
            
            # Check what algorithm would detect at that point
            detector = SMCDetector(swing_lookback=5)
            
            # Simulate what algorithm knew at that date
            df_daily_sim = df_daily.iloc[:idx1+1].copy()
            chochs = detector.detect_choch(df_daily_sim)
            
            print(f"\n🔍 CHoCH patterns detected before Oct 31: {len(chochs)}")
            if chochs:
                latest_choch = chochs[-1]
                print(f"   Latest CHoCH: {latest_choch.direction.upper()} @ ${latest_choch.break_price:,.2f} on {latest_choch.candle_time.date()}")
                
                # Check for FVG
                fvg = detector.detect_fvg(df_daily_sim, latest_choch)
                if fvg:
                    print(f"   FVG detected: ${fvg.bottom:,.2f} - ${fvg.top:,.2f} ({fvg.direction})")
                    
                    # Check if price was in FVG
                    if fvg.bottom <= price_at_entry1 <= fvg.top:
                        print(f"   ✅ Price WAS in FVG zone at entry!")
                    else:
                        print(f"   ❌ Price was NOT in FVG zone (${price_at_entry1:,.2f})")
                else:
                    print(f"   ⚠️ No FVG found after CHoCH")
        
        print("\n" + "="*70)
        print("📅 ENTRY 2: November 11, 2025 (SHORT)")
        print("="*70)
        
        if idx2:
            # Show price action around entry 2
            start_idx = max(0, idx2 - 10)
            end_idx = min(len(df_daily), idx2 + 5)
            
            print("\n📊 Daily candles around Nov 11:")
            for i in range(start_idx, end_idx):
                marker = " 👉 ENTRY" if i == idx2 else ""
                print(f"   {df_daily['time'].iloc[i].date()} | Close: ${df_daily['close'].iloc[i]:,.2f}{marker}")
            
            price_at_entry2 = df_daily['close'].iloc[idx2]
            print(f"\n💰 Price at entry: ${price_at_entry2:,.2f}")
            
            # Check what algorithm would detect
            df_daily_sim2 = df_daily.iloc[:idx2+1].copy()
            chochs2 = detector.detect_choch(df_daily_sim2)
            
            print(f"\n🔍 CHoCH patterns detected before Nov 11: {len(chochs2)}")
            if chochs2:
                latest_choch2 = chochs2[-1]
                print(f"   Latest CHoCH: {latest_choch2.direction.upper()} @ ${latest_choch2.break_price:,.2f} on {latest_choch2.candle_time.date()}")
                
                fvg2 = detector.detect_fvg(df_daily_sim2, latest_choch2)
                if fvg2:
                    print(f"   FVG detected: ${fvg2.bottom:,.2f} - ${fvg2.top:,.2f} ({fvg2.direction})")
                    
                    if fvg2.bottom <= price_at_entry2 <= fvg2.top:
                        print(f"   ✅ Price WAS in FVG zone at entry!")
                    else:
                        print(f"   ❌ Price was NOT in FVG zone (${price_at_entry2:,.2f})")
                else:
                    print(f"   ⚠️ No FVG found after CHoCH")
        
        # Show current status
        print("\n" + "="*70)
        print("📈 CURRENT STATUS (Dec 1, 2025)")
        print("="*70)
        
        current_price = df_daily['close'].iloc[-1]
        print(f"\n💰 Current BTC price: ${current_price:,.2f}")
        
        if idx1:
            pnl1 = price_at_entry1 - current_price
            pnl1_pct = (pnl1 / price_at_entry1) * 100
            print(f"\n📊 Trade 1 (Oct 31):")
            print(f"   Entry: ${price_at_entry1:,.2f}")
            print(f"   Current P&L: ${pnl1:,.2f} ({pnl1_pct:+.2f}%)")
            print(f"   Status: {'✅ PROFIT' if pnl1 > 0 else '❌ LOSS'}")
        
        if idx2:
            pnl2 = price_at_entry2 - current_price
            pnl2_pct = (pnl2 / price_at_entry2) * 100
            print(f"\n📊 Trade 2 (Nov 11):")
            print(f"   Entry: ${price_at_entry2:,.2f}")
            print(f"   Current P&L: ${pnl2:,.2f} ({pnl2_pct:+.2f}%)")
            print(f"   Status: {'✅ PROFIT' if pnl2 > 0 else '❌ LOSS'}")
    
    finally:
        scanner.data_provider.disconnect()
    
    print("\n" + "="*70)


if __name__ == "__main__":
    backtest_user_trades()
