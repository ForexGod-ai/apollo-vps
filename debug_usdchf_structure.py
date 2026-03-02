#!/usr/bin/env python3
"""
🔍 USDCHF STRUCTURE DEBUG TOOL
========================================
Diagnostic script to analyze what the scanner detected on USDCHF Daily
and verify if Bullish CHoCH was a false positive.

Purpose:
- Fetch last 100 Daily candles for USDCHF
- Show exactly where scanner identified Swing Highs/Lows
- Display the exact price where "Bullish CHoCH" was detected
- Compare with actual market structure (Lower Lows in downtrend)

This helps diagnose why scanner confuses micro-pullbacks with major swing points.
"""

import sys
import json
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from smc_detector import SMCDetector

# Configuration
CTRADER_API_URL = "http://localhost:8767"
SYMBOL = "USDCHF"
TIMEFRAME = "D1"
BAR_COUNT = 100

# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    END = '\033[0m'

def fetch_ctrader_data(symbol: str, timeframe: str, bars: int) -> Optional[List[Dict]]:
    """
    Fetch historical data from cTrader MarketDataProvider API
    
    Args:
        symbol: Trading pair (e.g., USDCHF)
        timeframe: Timeframe (D1, H4, etc.)
        bars: Number of bars to fetch
    
    Returns:
        List of candle dictionaries or None if error
    """
    try:
        # Try multiple possible endpoints
        endpoints = [
            f"{CTRADER_API_URL}/bars?symbol={symbol}&timeframe={timeframe}&bars={bars}",
            f"{CTRADER_API_URL}/price?symbol={symbol}",  # Returns bars array
            f"{CTRADER_API_URL}?symbol={symbol}"  # Default endpoint
        ]
        
        for url in endpoints:
            try:
                print(f"🔍 Trying endpoint: {url}")
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if bars exist in response
                    if 'bars' in data:
                        bars_data = data['bars']
                        print(f"✅ Fetched {len(bars_data)} bars from cTrader API")
                        return bars_data
                    elif isinstance(data, list):
                        print(f"✅ Fetched {len(data)} bars from cTrader API")
                        return data
                    else:
                        print(f"⚠️  Unexpected response format: {list(data.keys())}")
            except Exception as e:
                print(f"⚠️  Endpoint failed: {e}")
                continue
        
        print(f"❌ All endpoints failed for {symbol}")
        return None
    
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return None

def calculate_atr(bars: List[Dict], period: int = 14) -> float:
    """
    Calculate Average True Range
    
    Args:
        bars: List of candle bars
        period: ATR period (default 14)
    
    Returns:
        ATR value
    """
    if len(bars) < period + 1:
        return 0.0
    
    true_ranges = []
    for i in range(1, len(bars)):
        high = bars[i]['high']
        low = bars[i]['low']
        prev_close = bars[i-1]['close']
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)
    
    # Simple moving average of true ranges
    recent_trs = true_ranges[-period:]
    return sum(recent_trs) / len(recent_trs)

def analyze_structure(bars: List[Dict]) -> Dict:
    """
    Analyze USDCHF structure using current SMCDetector logic
    
    Args:
        bars: List of candle bars
    
    Returns:
        Dictionary with structure analysis results
    """
    print(f"\n{'='*80}")
    print(f"📊 ANALYZING USDCHF STRUCTURE")
    print(f"{'='*80}\n")
    
    # Convert bars list to pandas DataFrame (required by SMCDetector)
    import pandas as pd
    df = pd.DataFrame(bars)
    
    # Ensure time column is datetime
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
    
    # Initialize SMC Detector
    detector = SMCDetector()
    
    # Detect swing highs and lows
    swing_highs = detector.detect_swing_highs(df)
    swing_lows = detector.detect_swing_lows(df)
    
    # Calculate ATR for reference
    atr = calculate_atr(bars)
    
    # Get last 3 swing highs and lows
    recent_highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs
    recent_lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows
    
    # Detect CHoCH
    choch_list, _ = detector.detect_choch_and_bos(df)
    choch_result = choch_list[0] if choch_list else None
    
    return {
        'all_swing_highs': swing_highs,
        'all_swing_lows': swing_lows,
        'recent_highs': recent_highs,
        'recent_lows': recent_lows,
        'choch': choch_result,
        'atr': atr,
        'total_bars': len(bars),
        'df': df  # Keep DataFrame for further analysis
    }

def print_swing_points(swing_points: List, point_type: str, atr: float):
    """
    Print swing points with detailed information
    
    Args:
        swing_points: List of SwingPoint objects (dataclass)
        point_type: "HIGH" or "LOW"
        atr: Current ATR value
    """
    color = Colors.GREEN if point_type == "HIGH" else Colors.RED
    
    print(f"\n{color}{'─'*80}")
    print(f"📍 LAST 3 SWING {point_type}S (Most Recent First)")
    print(f"{'─'*80}{Colors.END}\n")
    
    if not swing_points:
        print(f"   ⚠️  No swing {point_type.lower()}s detected!")
        return
    
    for idx, point in enumerate(reversed(swing_points), 1):
        bar_idx = point.index
        price = point.price
        time = point.candle_time
        
        # Calculate distance from previous swing (if exists)
        distance_info = ""
        if idx < len(swing_points):
            prev_point = list(reversed(swing_points))[idx]
            prev_price = prev_point.price
            distance = abs(price - prev_price)
            atr_multiple = distance / atr if atr > 0 else 0
            distance_info = f" | Distance from prev: {distance:.5f} ({atr_multiple:.2f}x ATR)"
        
        print(f"   {color}#{idx}{Colors.END} {Colors.BOLD}Bar Index: {bar_idx}{Colors.END}")
        print(f"       Price: {Colors.BOLD}{price:.5f}{Colors.END}")
        print(f"       Time: {time}")
        if distance_info:
            print(f"      {distance_info}")
        print()

def print_choch_analysis(choch, bars: List[Dict], atr: float):
    """
    Print CHoCH detection analysis
    
    Args:
        choch: CHoCH detection result (can be dict or CHoCH dataclass)
        bars: List of candle bars
        atr: Current ATR value
    """
    print(f"\n{Colors.CYAN}{'='*80}")
    print(f"🔄 CHoCH DETECTION ANALYSIS")
    print(f"{'='*80}{Colors.END}\n")
    
    if not choch:
        print(f"   ⚠️  No CHoCH detected")
        return
    
    # Handle both dict and dataclass formats
    if hasattr(choch, 'direction'):
        # It's a CHoCH dataclass
        direction = choch.direction
        bar_index = choch.index
        price = choch.break_price
    else:
        # It's a dict
        direction = choch.get('direction', 'UNKNOWN')
        bar_index = choch.get('bar_index', choch.get('index', '?'))
        price = choch.get('price', choch.get('break_price', 0))
    
    # Get the actual candle that triggered CHoCH
    if isinstance(bar_index, int) and bar_index < len(bars):
        trigger_candle = bars[bar_index]
        candle_time = trigger_candle.get('time', 'N/A')
        candle_close = trigger_candle.get('close', 0)
        candle_high = trigger_candle.get('high', 0)
        candle_low = trigger_candle.get('low', 0)
    else:
        candle_time = 'N/A'
        candle_close = 0
        candle_high = 0
        candle_low = 0
    
    color = Colors.GREEN if 'BULL' in str(direction).upper() else Colors.RED
    
    print(f"   {color}Direction: {Colors.BOLD}{direction}{Colors.END}")
    print(f"   Bar Index: {bar_index}")
    print(f"   Break Price: {Colors.BOLD}{price:.5f}{Colors.END}")
    print(f"   Candle Time: {candle_time}")
    print(f"   Candle OHLC:")
    print(f"      High:  {candle_high:.5f}")
    print(f"      Close: {candle_close:.5f}")
    print(f"      Low:   {candle_low:.5f}")
    
    # Check if this is in a downtrend (for false positive detection)
    if len(bars) >= 5:
        last_5_closes = [bar['close'] for bar in bars[-5:]]
        avg_close = sum(last_5_closes) / len(last_5_closes)
        first_close = bars[-50]['close'] if len(bars) >= 50 else bars[0]['close']
        trend = "DOWNTREND" if first_close > avg_close else "UPTREND"
        
        print(f"\n   {Colors.YELLOW}Context:{Colors.END}")
        print(f"      Overall Trend (Last 50 bars): {Colors.BOLD}{trend}{Colors.END}")
        print(f"      Current ATR: {atr:.5f}")
        
        if 'BULL' in str(direction).upper() and trend == 'DOWNTREND':
            print(f"\n   {Colors.RED}⚠️  WARNING: Bullish CHoCH detected in DOWNTREND!{Colors.END}")
            print(f"      This might be a FALSE POSITIVE from micro-structure break.")

def print_market_context(bars: List[Dict]):
    """
    Print overall market context and trend
    
    Args:
        bars: List of candle bars
    """
    print(f"\n{Colors.MAGENTA}{'='*80}")
    print(f"📈 MARKET CONTEXT")
    print(f"{'='*80}{Colors.END}\n")
    
    if len(bars) < 10:
        print("   ⚠️  Not enough bars for context analysis")
        return
    
    # Get key price levels
    oldest_bar = bars[0]
    newest_bar = bars[-1]
    
    highest_bar = max(bars, key=lambda x: x['high'])
    lowest_bar = min(bars, key=lambda x: x['low'])
    
    print(f"   Period: {oldest_bar.get('time', 'N/A')} → {newest_bar.get('time', 'N/A')}")
    print(f"   Total Bars: {len(bars)}")
    print()
    print(f"   Oldest Close: {oldest_bar['close']:.5f}")
    print(f"   Newest Close: {newest_bar['close']:.5f}")
    print(f"   Change: {Colors.BOLD}{((newest_bar['close'] - oldest_bar['close']) / oldest_bar['close'] * 100):.2f}%{Colors.END}")
    print()
    print(f"   Highest: {highest_bar['high']:.5f} (Bar {bars.index(highest_bar)})")
    print(f"   Lowest:  {lowest_bar['low']:.5f} (Bar {bars.index(lowest_bar)})")
    
    # Detect trend
    first_third = bars[:len(bars)//3]
    last_third = bars[-len(bars)//3:]
    
    avg_first = sum(bar['close'] for bar in first_third) / len(first_third)
    avg_last = sum(bar['close'] for bar in last_third) / len(last_third)
    
    trend = "DOWNTREND" if avg_first > avg_last else "UPTREND"
    trend_color = Colors.RED if trend == "DOWNTREND" else Colors.GREEN
    
    print()
    print(f"   Visual Trend: {trend_color}{Colors.BOLD}{trend}{Colors.END}")
    print(f"   (First 1/3 avg: {avg_first:.5f} vs Last 1/3 avg: {avg_last:.5f})")

def main():
    """Main diagnostic function"""
    print(f"\n{Colors.BOLD}{'='*80}")
    print(f"🔍 USDCHF STRUCTURE DIAGNOSTIC TOOL")
    print(f"{'='*80}{Colors.END}\n")
    print(f"Symbol: {SYMBOL}")
    print(f"Timeframe: {TIMEFRAME}")
    print(f"Bars: {BAR_COUNT}")
    print()
    
    # Fetch data
    print(f"📡 Fetching data from cTrader API...\n")
    bars = fetch_ctrader_data(SYMBOL, TIMEFRAME, BAR_COUNT)
    
    if not bars:
        print(f"\n{Colors.RED}❌ Failed to fetch data from cTrader API{Colors.END}")
        print(f"\nTroubleshooting:")
        print(f"   1. Check if cTrader is running")
        print(f"   2. Check if MarketDataProvider bot is active")
        print(f"   3. Verify API endpoint: {CTRADER_API_URL}")
        return 1
    
    # Ensure we have enough bars
    if len(bars) < 20:
        print(f"\n{Colors.RED}❌ Not enough bars ({len(bars)}) for analysis (need at least 20){Colors.END}")
        return 1
    
    # Trim to requested count if we got more
    if len(bars) > BAR_COUNT:
        bars = bars[-BAR_COUNT:]
    
    print(f"✅ Got {len(bars)} bars\n")
    
    # Print market context first
    print_market_context(bars)
    
    # Analyze structure
    analysis = analyze_structure(bars)
    
    # Print ATR
    print(f"\n{Colors.CYAN}📊 ATR (14-period): {Colors.BOLD}{analysis['atr']:.5f}{Colors.END}")
    
    # Print swing highs
    print_swing_points(analysis['recent_highs'], "HIGH", analysis['atr'])
    
    # Print swing lows
    print_swing_points(analysis['recent_lows'], "LOW", analysis['atr'])
    
    # Print CHoCH analysis
    print_choch_analysis(analysis['choch'], analysis['df'].reset_index().to_dict('records'), analysis['atr'])
    
    # Summary
    print(f"\n{Colors.BOLD}{'='*80}")
    print(f"📋 SUMMARY")
    print(f"{'='*80}{Colors.END}\n")
    print(f"   Total Swing Highs Detected: {len(analysis['all_swing_highs'])}")
    print(f"   Total Swing Lows Detected: {len(analysis['all_swing_lows'])}")
    print(f"   CHoCH Detected: {Colors.BOLD}{'YES' if analysis['choch'] else 'NO'}{Colors.END}")
    
    if analysis['choch']:
        direction = analysis['choch'].direction
        color = Colors.GREEN if 'bull' in direction.lower() else Colors.RED
        print(f"   CHoCH Direction: {color}{Colors.BOLD}{direction.upper()}{Colors.END}")
    
    print(f"\n{Colors.BOLD}{'='*80}")
    print(f"✅ DIAGNOSTIC COMPLETE")
    print(f"{'='*80}{Colors.END}\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
