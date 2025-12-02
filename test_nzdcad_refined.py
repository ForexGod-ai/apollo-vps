#!/usr/bin/env python3
"""
Test refined strategy detection on NZDCAD specifically
Should detect: REVERSAL BULLISH (BUY from green zone)

Expected:
- Previous trend: BEARISH (LH/LL pattern)
- CHoCH: BULLISH (broke structure up)
- FVG: GREEN zone (bullish imbalance)
- Strategy: REVERSAL BULLISH
"""

from smc_detector import SMCDetector
import yfinance as yf
import pandas as pd

def test_nzdcad_refined():
    print("\n" + "="*70)
    print("🧪 TESTING REFINED STRATEGY DETECTION - NZDCAD")
    print("="*70 + "\n")
    
    try:
        detector = SMCDetector()
        
        # Download NZDCAD data from TradingView via yfinance
        print("📊 Downloading NZDCAD data...")
        ticker = yf.Ticker("NZDCAD=X")
        df_daily = ticker.history(period="90d", interval="1d")
        df_4h = ticker.history(period="30d", interval="1h")  # yfinance doesn't have 4h, use 1h
        
        # Add 'time' column from index BEFORE renaming
        df_daily = df_daily.reset_index()
        df_4h = df_4h.reset_index()
        
        # Rename ALL columns to lowercase
        df_daily.columns = [c.lower() for c in df_daily.columns]
        df_4h.columns = [c.lower() for c in df_4h.columns]
        
        # Rename date/datetime columns to 'time'
        if 'date' in df_daily.columns:
            df_daily.rename(columns={'date': 'time'}, inplace=True)
        if 'datetime' in df_daily.columns:
            df_daily.rename(columns={'datetime': 'time'}, inplace=True)
        if 'date' in df_4h.columns:
            df_4h.rename(columns={'date': 'time'}, inplace=True)
        if 'datetime' in df_4h.columns:
            df_4h.rename(columns={'datetime': 'time'}, inplace=True)
        
        if df_daily.empty or df_4h.empty:
            print("❌ Failed to download data")
            return
        
        print(f"✅ Downloaded {len(df_daily)} daily candles, {len(df_4h)} 1h candles")
        print(f"   Daily columns: {list(df_daily.columns)}")
        print(f"   4H columns: {list(df_4h.columns)}")
        
        # Test NZDCAD
        print("\n📊 Testing NZDCAD...")
        print("-" * 70)
        
        result = detector.scan_for_setup(
            symbol="NZDCAD",
            df_daily=df_daily,
            df_4h=df_4h,
            priority=2
        )
        
        if result:
            print(f"\n✅ SETUP FOUND:")
            print(f"   Symbol: {result.symbol}")
            print(f"   Strategy Type: {result.strategy_type.upper()}")
            print(f"   Direction: {result.daily_choch.direction.upper()}")
            print(f"   Entry: {result.entry_price:.5f}")
            print(f"   Stop Loss: {result.stop_loss:.5f}")
            print(f"   Take Profit: {result.take_profit:.5f}")
            print(f"   Risk:Reward: 1:{result.risk_reward:.2f}")
            
            # Validation
            print("\n🔍 VALIDATION:")
            if result.strategy_type == 'reversal' and result.daily_choch.direction == 'bullish':
                print("   ✅ CORRECT! Detected as REVERSAL BULLISH")
            elif result.strategy_type == 'reversal' and result.daily_choch.direction == 'bearish':
                print("   ❌ WRONG! Detected as REVERSAL BEARISH (should be BULLISH)")
            else:
                print(f"   ⚠️  Unexpected: {result.strategy_type} {result.daily_choch.direction}")
            
            # Show FVG details
            if hasattr(result, 'fvg_zone'):
                fvg = result.fvg_zone
                print(f"\n   FVG Details:")
                print(f"   - Type: {fvg.direction}")
                print(f"   - High: {fvg.high:.5f}")
                print(f"   - Low: {fvg.low:.5f}")
            
            # Show CHoCH details
            if hasattr(result, 'choch'):
                choch = result.choch
                print(f"\n   CHoCH Details:")
                print(f"   - Direction: {choch.direction}")
                print(f"   - Price: {choch.price:.5f}")
                print(f"   - Index: {choch.index}")
        else:
            print("\n❌ NO SETUP FOUND")
        
        print("\n" + "="*70)
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_nzdcad_refined()
