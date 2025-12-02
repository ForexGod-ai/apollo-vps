"""
SMC Detector FIXED - Glitch in Matrix Strategy
Detectare corectă: TREND → CHoCH → PULLBACK → Entry pe 4H

LOGICA CORECTĂ:
1. Detectează TREND pe Daily (HH/HL = BULLISH, LH/LL = BEARISH)
2. CHoCH = când break-ul SCHIMBĂ trendul (ex: BEARISH → BULLISH)
3. PULLBACK = retragere ÎN trend (NU e CHoCH!)
4. Entry = pe 4H când face CHoCH în direcția trendului Daily
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SwingPoint:
    index: int
    price: float
    swing_type: str  # 'high' or 'low'
    candle_time: datetime


@dataclass  
class TrendAnalysis:
    """Analiza trendului pe bază de swing points"""
    direction: str  # 'bullish', 'bearish', 'neutral'
    confidence: float  # 0.0 - 1.0
    swing_highs: List[SwingPoint]
    swing_lows: List[SwingPoint]
    structure: str  # 'HH_HL', 'LH_LL', 'mixed'


def analyze_trend_structure(swing_highs: List[SwingPoint], swing_lows: List[SwingPoint]) -> TrendAnalysis:
    """
    Analizează structura trendului bazat pe swing points
    
    BULLISH TREND = Higher Highs (HH) + Higher Lows (HL)
    BEARISH TREND = Lower Highs (LH) + Lower Lows (LL)
    """
    
    if len(swing_highs) < 3 or len(swing_lows) < 3:
        return TrendAnalysis('neutral', 0.0, swing_highs, swing_lows, 'insufficient_data')
    
    # Analizează ultimele 3-4 swing highs pentru trend
    recent_highs = swing_highs[-4:] if len(swing_highs) >= 4 else swing_highs
    recent_lows = swing_lows[-4:] if len(swing_lows) >= 4 else swing_lows
    
    # Count Higher Highs vs Lower Highs
    hh_count = 0
    lh_count = 0
    for i in range(1, len(recent_highs)):
        if recent_highs[i].price > recent_highs[i-1].price:
            hh_count += 1
        else:
            lh_count += 1
    
    # Count Higher Lows vs Lower Lows  
    hl_count = 0
    ll_count = 0
    for i in range(1, len(recent_lows)):
        if recent_lows[i].price > recent_lows[i-1].price:
            hl_count += 1
        else:
            ll_count += 1
    
    # Determine trend
    if hh_count > lh_count and hl_count > ll_count:
        # Majority HH and HL = BULLISH
        confidence = (hh_count + hl_count) / (len(recent_highs) + len(recent_lows) - 2)
        return TrendAnalysis('bullish', confidence, recent_highs, recent_lows, 'HH_HL')
    
    elif lh_count > hh_count and ll_count > hl_count:
        # Majority LH and LL = BEARISH  
        confidence = (lh_count + ll_count) / (len(recent_highs) + len(recent_lows) - 2)
        return TrendAnalysis('bearish', confidence, recent_highs, recent_lows, 'LH_LL')
    
    else:
        # Mixed structure
        return TrendAnalysis('neutral', 0.5, recent_highs, recent_lows, 'mixed')


def detect_body_swing_highs(df: pd.DataFrame, lookback: int = 5) -> List[SwingPoint]:
    """Detectează swing highs folosind DOAR BODY (fără wick-uri)"""
    swing_highs = []
    body_highs = df[['open', 'close']].max(axis=1)
    
    for i in range(lookback, len(df) - lookback):
        current_high = body_highs.iloc[i]
        
        left_check = all(current_high > body_highs.iloc[i - j] for j in range(1, lookback + 1))
        right_check = all(current_high > body_highs.iloc[i + j] for j in range(1, lookback + 1))
        
        if left_check and right_check:
            swing_highs.append(SwingPoint(
                index=i,
                price=current_high,
                swing_type='high',
                candle_time=df['time'].iloc[i]
            ))
    
    return swing_highs


def detect_body_swing_lows(df: pd.DataFrame, lookback: int = 5) -> List[SwingPoint]:
    """Detectează swing lows folosind DOAR BODY (fără wick-uri)"""
    swing_lows = []
    body_lows = df[['open', 'close']].min(axis=1)
    
    for i in range(lookback, len(df) - lookback):
        current_low = body_lows.iloc[i]
        
        left_check = all(current_low < body_lows.iloc[i - j] for j in range(1, lookback + 1))
        right_check = all(current_low < body_lows.iloc[i + j] for j in range(1, lookback + 1))
        
        if left_check and right_check:
            swing_lows.append(SwingPoint(
                index=i,
                price=current_low,
                swing_type='low',
                candle_time=df['time'].iloc[i]
            ))
    
    return swing_lows


# Test cu GBPUSD
if __name__ == "__main__":
    import yfinance as yf
    from datetime import timedelta
    
    # Get GBPUSD data
    ticker = yf.Ticker('GBPUSD=X')
    end = datetime.now()
    start = end - timedelta(days=150)
    df = ticker.history(start=start, end=end, interval='1d').tail(100)
    
    df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
    df['time'] = df.index
    df = df.reset_index(drop=True)
    
    # Detect swings
    highs = detect_body_swing_highs(df)
    lows = detect_body_swing_lows(df)
    
    print("🔍 GBPUSD FIXED ANALYSIS:")
    print("\n📈 Swing Highs (BODY-ONLY):")
    for h in highs[-5:]:
        print(f"   {h.price:.5f} @ index {h.index}")
    
    print("\n📉 Swing Lows (BODY-ONLY):")
    for l in lows[-5:]:
        print(f"   {l.price:.5f} @ index {l.index}")
    
    # Analyze trend
    trend = analyze_trend_structure(highs, lows)
    print(f"\n📊 TREND ANALYSIS:")
    print(f"   Direction: {trend.direction.upper()}")
    print(f"   Structure: {trend.structure}")
    print(f"   Confidence: {trend.confidence:.1%}")
    
    if trend.direction == 'bearish':
        print("\n✅ BEARISH TREND DETECTED - Lower Highs + Lower Lows!")
        print("   → Așteaptă pullback la FVG zone pentru SELL")
        print("   → Confirmă cu CHoCH bearish pe 4H")
    elif trend.direction == 'bullish':
        print("\n✅ BULLISH TREND DETECTED - Higher Highs + Higher Lows!")
        print("   → Așteaptă pullback la FVG zone pentru BUY")
        print("   → Confirmă cu CHoCH bullish pe 4H")
