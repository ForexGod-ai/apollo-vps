#!/usr/bin/env python3
"""
Debug script to check why backtest finds 0 trades
"""

import sys
from datetime import datetime, timedelta
from ctrader_cbot_client import CTraderCBotClient
from smc_detector import SMCDetector

def main():
    print("🔍 Debugging backtest - checking for setups...\n")
    
    client = CTraderCBotClient()
    detector = SMCDetector(swing_lookback=5)
    
    # Download NZDUSD data
    symbol = 'NZDUSD'
    print(f"📊 Downloading {symbol} data...")
    
    df_daily = client.get_historical_data(symbol, 'D1', 465)
    df_4h = client.get_historical_data(symbol, 'H4', 2690)
    
    print(f"   ✅ Daily: {len(df_daily)} candles")
    print(f"   ✅ 4H: {len(df_4h)} candles")
    print(f"   Latest Daily: {df_daily.index[-1]}")
    print(f"   Latest 4H: {df_4h.index[-1]}\n")
    
    # Try scanning with latest data
    print("🔎 Scanning for setups...")
    setup = detector.scan_for_setup(
        symbol=symbol,
        df_daily=df_daily,
        df_4h=df_4h,
        priority=1,
        df_1h=None
    )
    
    if setup:
        print(f"✅ FOUND SETUP!")
        print(f"   Type: {setup.get('pattern_type', 'N/A')}")
        print(f"   Direction: {setup.get('direction', 'N/A')}")
        print(f"   Status: {setup.get('status', 'N/A')}")
        print(f"   Entry: {setup.get('entry', 'N/A')}")
        print(f"   SL: {setup.get('stop_loss', 'N/A')}")
        print(f"   TP: {setup.get('take_profit', 'N/A')}")
        
        if 'fvg' in setup:
            fvg = setup['fvg']
            print(f"\n   FVG Details:")
            print(f"      Quality Score: {fvg.quality_score if hasattr(fvg, 'quality_score') else 'N/A'}")
            print(f"      High: {fvg.high}")
            print(f"      Low: {fvg.low}")
    else:
        print("❌ NO SETUP FOUND")
        print("\n📊 Checking pattern detection manually...")
        
        # Check for Daily CHoCH
        from smc_detector import detect_choch
        daily_chochs = detect_choch(df_daily, swing_lookback=5)
        print(f"   Daily CHoCH patterns: {len(daily_chochs)}")
        if len(daily_chochs) > 0:
            last_choch = daily_chochs[-1]
            print(f"      Latest: {last_choch.direction} at index {last_choch.break_index}")
        
        # Check for 4H CHoCH
        h4_chochs = detect_choch(df_4h, swing_lookback=5)
        print(f"   4H CHoCH patterns: {len(h4_chochs)}")
        if len(h4_chochs) > 0:
            last_choch = h4_chochs[-1]
            print(f"      Latest: {last_choch.direction} at index {last_choch.break_index}")
        
        # Check for FVGs
        from smc_detector import detect_fvg
        daily_fvgs = detect_fvg(df_daily)
        print(f"   Daily FVG patterns: {len(daily_fvgs)}")
        
        h4_fvgs = detect_fvg(df_4h)
        print(f"   4H FVG patterns: {len(h4_fvgs)}")

if __name__ == "__main__":
    main()
