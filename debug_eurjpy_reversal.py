#!/usr/bin/env python3
"""
🔍 EURJPY REVERSAL DEBUG TOOL
Diagnostic script to understand what the algorithm sees on EURJPY

Usage:
    python3 debug_eurjpy_reversal.py
    python3 debug_eurjpy_reversal.py --timeframe D1
    python3 debug_eurjpy_reversal.py --bars 200
"""

import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ctrader_cbot_client import CTraderCBotClient
from smc_detector import SMCDetector


class EURJPYReversalDebugger:
    def __init__(self, timeframe: str = "D1", bars: int = 100):
        self.symbol = "EURJPY"
        self.timeframe = timeframe
        self.bars = bars
        self.ctrader = CTraderCBotClient()
        self.smc = SMCDetector()
        
        print(f"\n{'='*100}")
        print(f"🔍 EURJPY REVERSAL DIAGNOSTIC TOOL")
        print(f"{'='*100}")
        print(f"📊 Symbol: {self.symbol}")
        print(f"⏰ Timeframe: {self.timeframe}")
        print(f"📈 Bars: {self.bars}")
        print(f"{'='*100}\n")
    
    def download_data(self) -> Optional[List[Dict]]:
        """Download EURJPY data from cTrader"""
        print(f"📥 Downloading {self.symbol} data...")
        
        try:
            df = self.ctrader.get_historical_data(
                symbol=self.symbol,
                timeframe=self.timeframe,
                bars=self.bars
            )
            
            if df is None or df.empty:
                print(f"❌ No data received for {self.symbol}")
                return None
            
            # Convert DataFrame to list of dicts with timestamp
            bars = []
            for idx, row in df.iterrows():
                bars.append({
                    'time': str(idx),
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume']
                })
            
            print(f"✅ Downloaded {len(bars)} bars")
            print(f"   Latest price: {bars[-1]['close']:.5f}")
            print(f"   Date range: {bars[0]['time']} → {bars[-1]['time']}\n")
            
            return bars
        
        except Exception as e:
            print(f"❌ Error downloading data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def analyze_market_structure(self, bars: List[Dict]) -> Dict:
        """Analyze market structure using SMC detector"""
        print(f"{'='*100}")
        print(f"📊 MARKET STRUCTURE ANALYSIS")
        print(f"{'='*100}\n")
        
        # Find swing highs and lows
        swing_highs = self._find_swing_points(bars, 'high', lookback=5)
        swing_lows = self._find_swing_points(bars, 'low', lookback=5)
        
        print(f"🔴 SWING HIGHS (last 10):")
        for i, (idx, price, time) in enumerate(swing_highs[-10:]):
            print(f"   {i+1}. Price: {price:.5f} | Bar: {idx} | Time: {time}")
        
        print(f"\n🔵 SWING LOWS (last 10):")
        for i, (idx, price, time) in enumerate(swing_lows[-10:]):
            print(f"   {i+1}. Price: {price:.5f} | Bar: {idx} | Time: {time}")
        
        # Analyze structure breaks
        structure_analysis = self._analyze_structure_breaks(bars, swing_highs, swing_lows)
        
        return {
            'swing_highs': swing_highs,
            'swing_lows': swing_lows,
            'structure': structure_analysis
        }
    
    def _find_swing_points(self, bars: List[Dict], key: str, lookback: int = 5) -> List[Tuple[int, float, str]]:
        """Find swing highs or lows"""
        swings = []
        
        for i in range(lookback, len(bars) - lookback):
            current = bars[i][key]
            is_swing = True
            
            # Check if current bar is extreme in lookback window
            if key == 'high':
                # Swing high: higher than all bars in window
                for j in range(i - lookback, i + lookback + 1):
                    if j != i and bars[j][key] >= current:
                        is_swing = False
                        break
            else:
                # Swing low: lower than all bars in window
                for j in range(i - lookback, i + lookback + 1):
                    if j != i and bars[j][key] <= current:
                        is_swing = False
                        break
            
            if is_swing:
                swings.append((i, current, bars[i]['time']))
        
        return swings
    
    def _analyze_structure_breaks(self, bars: List[Dict], swing_highs: List, swing_lows: List) -> Dict:
        """Analyze BOS and CHoCH"""
        print(f"\n{'='*100}")
        print(f"🔄 STRUCTURE BREAK ANALYSIS")
        print(f"{'='*100}\n")
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            print("⚠️  Not enough swing points for structure analysis")
            return {'trend': 'UNKNOWN', 'breaks': []}
        
        # Get last swing points
        last_high = swing_highs[-1]
        prev_high = swing_highs[-2] if len(swing_highs) >= 2 else None
        last_low = swing_lows[-1]
        prev_low = swing_lows[-2] if len(swing_lows) >= 2 else None
        
        print(f"📍 LAST SWING HIGH:")
        print(f"   Price: {last_high[1]:.5f} | Bar: {last_high[0]} | Time: {last_high[2]}")
        
        if prev_high:
            print(f"\n📍 PREVIOUS SWING HIGH:")
            print(f"   Price: {prev_high[1]:.5f} | Bar: {prev_high[0]} | Time: {prev_high[2]}")
            diff_pips = (last_high[1] - prev_high[1]) * 100
            print(f"   Difference: {diff_pips:+.1f} pips")
        
        print(f"\n📍 LAST SWING LOW:")
        print(f"   Price: {last_low[1]:.5f} | Bar: {last_low[0]} | Time: {last_low[2]}")
        
        if prev_low:
            print(f"\n📍 PREVIOUS SWING LOW:")
            print(f"   Price: {prev_low[1]:.5f} | Bar: {prev_low[0]} | Time: {prev_low[2]}")
            diff_pips = (last_low[1] - prev_low[1]) * 100
            print(f"   Difference: {diff_pips:+.1f} pips")
        
        # Determine trend
        current_price = bars[-1]['close']
        trend = self._determine_trend(swing_highs, swing_lows, current_price)
        
        print(f"\n{'='*100}")
        print(f"📈 TREND ANALYSIS")
        print(f"{'='*100}")
        print(f"🎯 Current Price: {current_price:.5f}")
        print(f"📊 Trend: {trend['direction']}")
        print(f"📝 Reasoning: {trend['reason']}")
        
        # Check for structure breaks
        breaks = self._detect_structure_breaks(bars, swing_highs, swing_lows, last_high, last_low)
        
        return {
            'trend': trend,
            'last_high': last_high,
            'last_low': last_low,
            'prev_high': prev_high,
            'prev_low': prev_low,
            'breaks': breaks
        }
    
    def _determine_trend(self, swing_highs: List, swing_lows: List, current_price: float) -> Dict:
        """Determine current trend"""
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {
                'direction': 'UNKNOWN',
                'reason': 'Not enough swing points'
            }
        
        # Compare last two highs and lows
        higher_high = swing_highs[-1][1] > swing_highs[-2][1]
        higher_low = swing_lows[-1][1] > swing_lows[-2][1]
        lower_high = swing_highs[-1][1] < swing_highs[-2][1]
        lower_low = swing_lows[-1][1] < swing_lows[-2][1]
        
        if higher_high and higher_low:
            return {
                'direction': 'BULLISH',
                'reason': 'Higher Highs + Higher Lows'
            }
        elif lower_high and lower_low:
            return {
                'direction': 'BEARISH',
                'reason': 'Lower Highs + Lower Lows'
            }
        elif higher_high and lower_low:
            return {
                'direction': 'RANGING/VOLATILE',
                'reason': 'Higher Highs but Lower Lows (conflicting)'
            }
        elif lower_high and higher_low:
            return {
                'direction': 'RANGING/CONSOLIDATION',
                'reason': 'Lower Highs but Higher Lows (compression)'
            }
        else:
            return {
                'direction': 'NEUTRAL',
                'reason': 'No clear pattern in swing points'
            }
    
    def _detect_structure_breaks(self, bars: List[Dict], swing_highs: List, swing_lows: List, 
                                  last_high: Tuple, last_low: Tuple) -> List[Dict]:
        """Detect BOS and CHoCH"""
        print(f"\n{'='*100}")
        print(f"💥 STRUCTURE BREAKS DETECTION")
        print(f"{'='*100}\n")
        
        breaks = []
        
        # Check if price broke above last swing high (bullish BOS/CHoCH)
        last_high_idx = last_high[0]
        last_high_price = last_high[1]
        
        for i in range(last_high_idx + 1, len(bars)):
            if bars[i]['close'] > last_high_price:
                pips_above = (bars[i]['close'] - last_high_price) * 100
                breaks.append({
                    'type': 'BULLISH',
                    'bar_idx': i,
                    'time': bars[i]['time'],
                    'price': bars[i]['close'],
                    'broke_level': last_high_price,
                    'pips': pips_above,
                    'event': 'BOS/CHoCH'
                })
                print(f"✅ BULLISH BREAK DETECTED:")
                print(f"   Bar: {i} | Time: {bars[i]['time']}")
                print(f"   Price: {bars[i]['close']:.5f}")
                print(f"   Broke above: {last_high_price:.5f} (+{pips_above:.1f} pips)")
                break
        
        # Check if price broke below last swing low (bearish BOS/CHoCH)
        last_low_idx = last_low[0]
        last_low_price = last_low[1]
        
        for i in range(last_low_idx + 1, len(bars)):
            if bars[i]['close'] < last_low_price:
                pips_below = (last_low_price - bars[i]['close']) * 100
                breaks.append({
                    'type': 'BEARISH',
                    'bar_idx': i,
                    'time': bars[i]['time'],
                    'price': bars[i]['close'],
                    'broke_level': last_low_price,
                    'pips': pips_below,
                    'event': 'BOS/CHoCH'
                })
                print(f"✅ BEARISH BREAK DETECTED:")
                print(f"   Bar: {i} | Time: {bars[i]['time']}")
                print(f"   Price: {bars[i]['close']:.5f}")
                print(f"   Broke below: {last_low_price:.5f} (-{pips_below:.1f} pips)")
                break
        
        if not breaks:
            print("❌ NO STRUCTURE BREAKS DETECTED")
            print(f"   Current price: {bars[-1]['close']:.5f}")
            print(f"   Distance to last high ({last_high_price:.5f}): {(bars[-1]['close'] - last_high_price) * 100:+.1f} pips")
            print(f"   Distance to last low ({last_low_price:.5f}): {(bars[-1]['close'] - last_low_price) * 100:+.1f} pips")
        
        return breaks
    
    def check_setup_requirements(self, bars: List[Dict], structure: Dict) -> None:
        """Check why setup wasn't generated"""
        print(f"\n{'='*100}")
        print(f"🔍 SETUP GENERATION CHECK")
        print(f"{'='*100}\n")
        
        current_price = bars[-1]['close']
        
        # Check if there's a structure break
        breaks = structure.get('structure', {}).get('breaks', [])
        if not breaks:
            print("❌ NO SETUP: No structure break detected")
            print("   Requirement: Price must break last swing high (bullish) or low (bearish)")
            return
        
        print("✅ Structure break detected")
        
        # Check for FVG (Fair Value Gap)
        fvgs = self._find_fvgs(bars)
        
        if not fvgs:
            print("\n⚠️  NO FVG DETECTED")
            print("   An FVG (Fair Value Gap) is required for entry")
            print("   FVG = Gap between bar[i-1].low and bar[i+1].high (bullish)")
            print("        or bar[i-1].high and bar[i+1].low (bearish)")
        else:
            print(f"\n✅ Found {len(fvgs)} FVG(s):")
            for i, fvg in enumerate(fvgs[-5:], 1):
                print(f"   {i}. Type: {fvg['type']} | Range: {fvg['low']:.5f} - {fvg['high']:.5f} | Bar: {fvg['bar_idx']}")
        
        # Check Premium/Discount zone
        if structure['last_high'] and structure['last_low']:
            high = structure['last_high'][1]
            low = structure['last_low'][1]
            mid = (high + low) / 2
            
            if current_price > mid:
                zone = "PREMIUM"
                print(f"\n📊 Current price is in PREMIUM zone")
                print(f"   High: {high:.5f}")
                print(f"   Mid: {mid:.5f}")
                print(f"   Low: {low:.5f}")
                print(f"   Current: {current_price:.5f} ({((current_price - mid) / (high - mid) * 100):.1f}% into premium)")
                print("   ⚠️  SHORT setups require PREMIUM zone ✅")
                print("   ⚠️  LONG setups require DISCOUNT zone ❌")
            else:
                zone = "DISCOUNT"
                print(f"\n📊 Current price is in DISCOUNT zone")
                print(f"   High: {high:.5f}")
                print(f"   Mid: {mid:.5f}")
                print(f"   Low: {low:.5f}")
                print(f"   Current: {current_price:.5f} ({((mid - current_price) / (mid - low) * 100):.1f}% into discount)")
                print("   ⚠️  LONG setups require DISCOUNT zone ✅")
                print("   ⚠️  SHORT setups require PREMIUM zone ❌")
        
        # Check open positions (might block new signals)
        print(f"\n{'='*100}")
        print(f"🚦 SIGNAL GENERATION BLOCKERS")
        print(f"{'='*100}")
        
        # Check monitoring cache
        monitoring_file = Path("monitoring_setups.json")
        if monitoring_file.exists():
            with open(monitoring_file, 'r') as f:
                monitoring = json.load(f)
            
            eurjpy_setups = [s for s in monitoring.get('setups', []) if s.get('symbol') == 'EURJPY']
            
            if eurjpy_setups:
                print(f"\n⚠️  EURJPY already in monitoring cache:")
                for setup in eurjpy_setups:
                    print(f"   Status: {setup.get('status', 'N/A')}")
                    print(f"   Created: {setup.get('setup_time', 'N/A')}")
                    print(f"   Direction: {setup.get('direction', 'N/A')}")
            else:
                print("\n✅ EURJPY not in monitoring cache")
        
        # Check active positions
        positions_file = Path("active_positions.json")
        if positions_file.exists():
            with open(positions_file, 'r') as f:
                positions = json.load(f)
            
            eurjpy_positions = [p for p in positions if p.get('symbol') == 'EURJPY']
            
            if eurjpy_positions:
                print(f"\n⚠️  EURJPY has open positions:")
                for pos in eurjpy_positions:
                    print(f"   Direction: {pos.get('direction', 'N/A')}")
                    print(f"   Volume: {pos.get('volume', 'N/A')}")
                    print(f"   Entry: {pos.get('entry_price', 'N/A')}")
            else:
                print("\n✅ No open EURJPY positions")
    
    def _find_fvgs(self, bars: List[Dict], min_gap_pips: float = 5.0) -> List[Dict]:
        """Find Fair Value Gaps"""
        fvgs = []
        
        for i in range(1, len(bars) - 1):
            # Bullish FVG: bar[i-1].low > bar[i+1].high
            if bars[i-1]['low'] > bars[i+1]['high']:
                gap_pips = (bars[i-1]['low'] - bars[i+1]['high']) * 100
                if gap_pips >= min_gap_pips:
                    fvgs.append({
                        'type': 'BULLISH',
                        'bar_idx': i,
                        'time': bars[i]['time'],
                        'low': bars[i+1]['high'],
                        'high': bars[i-1]['low'],
                        'gap_pips': gap_pips
                    })
            
            # Bearish FVG: bar[i-1].high < bar[i+1].low
            elif bars[i-1]['high'] < bars[i+1]['low']:
                gap_pips = (bars[i+1]['low'] - bars[i-1]['high']) * 100
                if gap_pips >= min_gap_pips:
                    fvgs.append({
                        'type': 'BEARISH',
                        'bar_idx': i,
                        'time': bars[i]['time'],
                        'low': bars[i-1]['high'],
                        'high': bars[i+1]['low'],
                        'gap_pips': gap_pips
                    })
        
        return fvgs
    
    def run(self):
        """Run full diagnostic"""
        # Download data
        bars = self.download_data()
        if not bars:
            return
        
        # Analyze market structure
        structure = self.analyze_market_structure(bars)
        
        # Check setup requirements
        self.check_setup_requirements(bars, structure)
        
        print(f"\n{'='*100}")
        print(f"✅ DIAGNOSTIC COMPLETE")
        print(f"{'='*100}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Debug EURJPY reversal detection'
    )
    parser.add_argument(
        '--timeframe',
        default='D1',
        help='Timeframe (D1, H4, H1, etc.)'
    )
    parser.add_argument(
        '--bars',
        type=int,
        default=100,
        help='Number of bars to analyze'
    )
    
    args = parser.parse_args()
    
    debugger = EURJPYReversalDebugger(
        timeframe=args.timeframe,
        bars=args.bars
    )
    debugger.run()


if __name__ == "__main__":
    main()
