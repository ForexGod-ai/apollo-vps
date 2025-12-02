#!/usr/bin/env python3
"""
Debug NZDCAD detection - see what's happening step by step
"""

from smc_detector import SMCDetector
import yfinance as yf

def debug_nzdcad():
    print("\n" + "="*70)
    print("🔍 DEBUG NZDCAD DETECTION")
    print("="*70 + "\n")
    
    try:
        detector = SMCDetector()
        
        # Download data
        print("📊 Downloading NZDCAD data...")
        ticker = yf.Ticker("NZDCAD=X")
        df_daily = ticker.history(period="90d", interval="1d")
        df_4h = ticker.history(period="30d", interval="1h")
        
        # Prepare data
        df_daily = df_daily.reset_index()
        df_4h = df_4h.reset_index()
        df_daily.columns = [c.lower() for c in df_daily.columns]
        df_4h.columns = [c.lower() for c in df_4h.columns]
        if 'date' in df_daily.columns:
            df_daily.rename(columns={'date': 'time'}, inplace=True)
        if 'datetime' in df_daily.columns:
            df_daily.rename(columns={'datetime': 'time'}, inplace=True)
        if 'date' in df_4h.columns:
            df_4h.rename(columns={'date': 'time'}, inplace=True)
        if 'datetime' in df_4h.columns:
            df_4h.rename(columns={'datetime': 'time'}, inplace=True)
        
        print(f"✅ Downloaded {len(df_daily)} daily candles, {len(df_4h)} 1h candles\n")
        
        # Step 1: Detect Daily CHoCH
        print("STEP 1: Detecting Daily CHoCH...")
        print("-" * 70)
        daily_chochs = detector.detect_choch(df_daily)
        print(f"Found {len(daily_chochs)} CHoCH(s) on Daily")
        
        if daily_chochs:
            latest_choch = daily_chochs[-1]
            print(f"\nLatest CHoCH:")
            print(f"  Direction: {latest_choch.direction.upper()}")
            print(f"  Break Price: {latest_choch.break_price:.5f}")
            print(f"  Index: {latest_choch.index}")
            print(f"  Date: {df_daily['time'].iloc[latest_choch.index]}")
            print(f"  Previous Trend: {latest_choch.previous_trend}")
            
            # Step 2: Analyze pre-CHoCH structure
            print(f"\nSTEP 2: Analyzing structure BEFORE CHoCH...")
            print("-" * 70)
            pre_choch_structure = detector._analyze_pre_choch_structure(df_daily, latest_choch)
            print(f"Previous trend pattern: {pre_choch_structure['pattern']}")
            print(f"Confidence: {pre_choch_structure['confidence']}%")
            
            # Step 3: Determine strategy type
            print(f"\nSTEP 3: Determining strategy type...")
            print("-" * 70)
            strategy_type = detector.detect_strategy_type(df_daily, latest_choch, None)
            print(f"Strategy Type: {strategy_type.upper()}")
            
            # Explain logic
            if latest_choch.direction == 'bullish':
                if pre_choch_structure['pattern'] == 'LH_LL':
                    print("  Logic: Previous BEARISH (LH/LL) → CHoCH BULLISH = REVERSAL")
                elif pre_choch_structure['pattern'] == 'HH_HL':
                    print("  Logic: Previous BULLISH (HH/HL) → CHoCH BULLISH = CONTINUATION")
            else:
                if pre_choch_structure['pattern'] == 'HH_HL':
                    print("  Logic: Previous BULLISH (HH/HL) → CHoCH BEARISH = REVERSAL")
                elif pre_choch_structure['pattern'] == 'LH_LL':
                    print("  Logic: Previous BEARISH (LH/LL) → CHoCH BEARISH = CONTINUATION")
            
            # Step 4: Detect FVG
            print(f"\nSTEP 4: Detecting FVG zones...")
            print("-" * 70)
            fvgs = detector.detect_fvg(df_daily)
            print(f"Found {len(fvgs)} FVG(s) on Daily")
            
            if fvgs:
                # Find FVG near CHoCH
                for fvg in fvgs[-5:]:  # Check last 5 FVGs
                    print(f"\n  FVG:")
                    print(f"    Direction: {fvg.direction.upper()}")
                    print(f"    High: {fvg.high:.5f}")
                    print(f"    Low: {fvg.low:.5f}")
                    print(f"    Index: {fvg.index}")
                    
                    # Check alignment
                    if strategy_type == 'reversal':
                        if latest_choch.direction == 'bullish' and fvg.direction == 'bullish':
                            print(f"    ✅ ALIGNED: REVERSAL BULLISH needs GREEN FVG")
                        elif latest_choch.direction == 'bearish' and fvg.direction == 'bearish':
                            print(f"    ✅ ALIGNED: REVERSAL BEARISH needs RED FVG")
                        else:
                            print(f"    ❌ NOT ALIGNED with {strategy_type} {latest_choch.direction}")
            
            # Step 5: Check 4H confirmation
            print(f"\nSTEP 5: Checking 4H confirmation...")
            print("-" * 70)
            h4_chochs = detector.detect_choch(df_4h)
            print(f"Found {len(h4_chochs)} CHoCH(s) on 4H")
            
            if h4_chochs:
                latest_4h = h4_chochs[-1]
                print(f"\nLatest 4H CHoCH:")
                print(f"  Direction: {latest_4h.direction.upper()}")
                print(f"  Break Price: {latest_4h.break_price:.5f}")
                print(f"  Date: {df_4h['time'].iloc[latest_4h.index]}")
                
                if latest_4h.direction == latest_choch.direction:
                    print(f"  ✅ ALIGNED with Daily {latest_choch.direction.upper()} CHoCH")
                else:
                    print(f"  ❌ NOT ALIGNED (Daily: {latest_choch.direction}, 4H: {latest_4h.direction})")
        else:
            print("❌ No CHoCH found on Daily")
        
        print("\n" + "="*70)
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_nzdcad()
