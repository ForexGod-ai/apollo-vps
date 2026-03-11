"""
Spatiotemporal Market Analyzer - v2.1
Analizează mișcări de preț pe 4H și confirmă setups de la daily scanner

Flow:
1. Daily scanner găsește setup-uri pe DAILY
2. Realtime monitor (4H) confirmă pe timeframe 4H
3. Trimite alert când setup e READY_TO_TRADE
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
from enum import Enum

# Import SMC Detector pentru v2.1 logic
try:
    from smc_detector import SMCDetector
except ImportError:
    logger.warning("SMCDetector not available, using basic analysis")
    SMCDetector = None

from ctrader_cbot_client import CTraderCBotClient


class MarketCondition(Enum):
    """Market conditions for narratives"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    RANGING = "ranging"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"


@dataclass
class MarketNarrative:
    """Story about market structure"""
    symbol: str
    timeframe: str
    timestamp: datetime
    
    # Structure elements
    condition: MarketCondition
    choch_count: int  # Number of CHoCH breaks
    fvg_count: int    # Number of Fair Value Gaps
    
    # Trend
    higher_highs: bool
    higher_lows: bool
    lower_highs: bool
    lower_lows: bool
    
    # Volatility
    atr: float
    volatility_level: str  # low, medium, high
    
    # Setup status
    setup_status: str  # "waiting", "monitoring", "ready_to_trade"
    confidence: float  # 0.0 - 1.0
    
    # Details
    notes: str
    
    # Compatibility properties for realtime_monitor.py
    @property
    def recommendation(self) -> str:
        """Convert setup_status to recommendation format"""
        if self.setup_status == "ready_to_trade":
            return "ready_to_trade"
        elif self.setup_status == "monitoring_closely":
            return "monitor_closely"
        elif self.setup_status == "data_unavailable":
            return "data_unavailable"
        else:
            return "wait_for_confirmation"
    
    @property
    def waiting_for(self) -> List[str]:
        """What are we waiting for"""
        waiting = []
        if self.choch_count == 0:
            waiting.append("CHoCH confirmation")
        if self.fvg_count == 0:
            waiting.append("FVG formation")
        if not (self.higher_highs or self.higher_lows or self.lower_highs or self.lower_lows):
            waiting.append("trend confirmation")
        return waiting[:3]  # Max 3
    
    @property
    def expected_scenarios(self) -> List[str]:
        """Expected next price movements"""
        scenarios = []
        
        if self.higher_highs and self.higher_lows:
            scenarios.append(f"Continue bullish trend, targets: +{self.atr * 2:.6f}")
        
        if self.lower_highs and self.lower_lows:
            scenarios.append(f"Continue bearish trend, targets: -{self.atr * 2:.6f}")
        
        if self.choch_count > 0:
            scenarios.append(f"Trend reversal scenario ({self.choch_count} CHoCH breaks)")
        
        if self.fvg_count > 0:
            scenarios.append(f"FVG fill-in likely ({self.fvg_count} FVG(s) unfilled)")
        
        return scenarios[:3]  # Max 3 scenarios
    
    def __str__(self) -> str:
        return f"[{self.symbol} {self.timeframe}] {self.condition.value.upper()} | {self.setup_status} ({self.confidence:.0%})"


class SpatioTemporalAnalyzer:
    """
    Analizator 4H cu v2.1 improvements:
    - CHoCH detection cu spacing (10 candles minimum)
    - ATR-adaptive tolerance (30% daily ATR)
    - FVG detection
    - Market narrative generation
    """
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.client = CTraderCBotClient()
        
        # Use SMCDetector if available
        self.smc_detector = SMCDetector() if SMCDetector else None
        
        logger.info(f"🔍 Initialized SpatioTemporalAnalyzer for {symbol}")
        
    def get_4h_data(self, num_candles: int = 100) -> Optional[pd.DataFrame]:
        """Get 4H OHLC data from cTrader"""
        try:
            df = self.client.get_historical_data(self.symbol, "H4", num_candles)
            if df is not None and not df.empty:
                return df
            else:
                logger.warning(f"⚠️ No 4H data for {self.symbol}")
                return None
        except Exception as e:
            logger.error(f"❌ Error getting 4H data for {self.symbol}: {e}")
            return None
    
    def get_daily_data(self, num_candles: int = 50) -> Optional[pd.DataFrame]:
        """Get DAILY OHLC data from cTrader"""
        try:
            df = self.client.get_historical_data(self.symbol, "D1", num_candles)
            if df is not None and not df.empty:
                return df
            else:
                logger.warning(f"⚠️ No Daily data for {self.symbol}")
                return None
        except Exception as e:
            logger.error(f"❌ Error getting Daily data for {self.symbol}: {e}")
            return None
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR (Average True Range)"""
        if df is None or len(df) < period:
            return 0.0
        
        df = df.copy()
        
        # True Range
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift(1))
        df['low_close'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        
        # ATR
        atr = df['tr'].rolling(window=period).mean().iloc[-1]
        return float(atr) if not np.isnan(atr) else 0.0
    
    def detect_choch(self, df: pd.DataFrame, min_spacing: int = 10) -> List[Dict]:
        """
        Detect Change of Character (CHoCH) breaks
        v2.1: Requires minimum spacing (10 candles)
        """
        if df is None or len(df) < min_spacing + 5:
            return []
        
        # Use SMC Detector if available, else basic detection
        if self.smc_detector:
            try:
                choches = self.smc_detector.detect_choch(df)
                return choches if choches else []
            except Exception as e:
                logger.warning(f"SMC Detector error: {e}, using basic detection")
        
        # Basic CHOCH detection (uptrend to downtrend or vice versa)
        choches = []
        
        for i in range(min_spacing + 2, len(df)):
            # Uptrend: higher highs and higher lows
            # Downtrend: lower highs and lower lows
            
            uptrend = (df['high'].iloc[i] > df['high'].iloc[i-1] and 
                      df['low'].iloc[i] > df['low'].iloc[i-1])
            
            downtrend = (df['high'].iloc[i] < df['high'].iloc[i-1] and 
                        df['low'].iloc[i] < df['low'].iloc[i-1])
            
            if i > min_spacing + 2:
                prev_uptrend = (df['high'].iloc[i-min_spacing] > df['high'].iloc[i-min_spacing-1])
                
                if downtrend and prev_uptrend:
                    choches.append({
                        'index': i,
                        'type': 'downtrend',
                        'price': df['high'].iloc[i],
                        'time': df['time'].iloc[i] if 'time' in df.columns else None
                    })
        
        return choches
    
    def detect_fvg(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect Fair Value Gaps (zones without trading)
        """
        if df is None or len(df) < 3:
            return []
        
        fvgs = []
        
        for i in range(1, len(df) - 1):
            # Bullish FVG: low[i] > high[i-1]
            if df['low'].iloc[i] > df['high'].iloc[i-1]:
                fvgs.append({
                    'type': 'bullish',
                    'top': df['low'].iloc[i],
                    'bottom': df['high'].iloc[i-1],
                    'index': i,
                    'time': df['time'].iloc[i] if 'time' in df.columns else None
                })
            
            # Bearish FVG: high[i] < low[i-1]
            elif df['high'].iloc[i] < df['low'].iloc[i-1]:
                fvgs.append({
                    'type': 'bearish',
                    'top': df['low'].iloc[i-1],
                    'bottom': df['high'].iloc[i],
                    'index': i,
                    'time': df['time'].iloc[i] if 'time' in df.columns else None
                })
        
        return fvgs
    
    def analyze_trend(self, df: pd.DataFrame) -> Tuple[bool, bool, bool, bool]:
        """
        Analyze trend structure:
        Returns: higher_highs, higher_lows, lower_highs, lower_lows
        """
        if df is None or len(df) < 10:
            return False, False, False, False
        
        last_10 = df.tail(10)
        
        # Check for higher highs (bullish)
        higher_highs = (last_10['high'].iloc[-1] > last_10['high'].iloc[-6] > last_10['high'].iloc[-10])
        higher_lows = (last_10['low'].iloc[-1] > last_10['low'].iloc[-6] > last_10['low'].iloc[-10])
        
        # Check for lower lows (bearish)
        lower_highs = (last_10['high'].iloc[-1] < last_10['high'].iloc[-6] < last_10['high'].iloc[-10])
        lower_lows = (last_10['low'].iloc[-1] < last_10['low'].iloc[-6] < last_10['low'].iloc[-10])
        
        return higher_highs, higher_lows, lower_highs, lower_lows
    
    def determine_market_condition(
        self, 
        choch_count: int, 
        fvg_count: int,
        higher_highs: bool,
        higher_lows: bool,
        lower_highs: bool,
        lower_lows: bool
    ) -> MarketCondition:
        """Determine current market condition"""
        
        if higher_highs and higher_lows:
            return MarketCondition.BULLISH
        elif lower_highs and lower_lows:
            return MarketCondition.BEARISH
        elif choch_count > 2:
            return MarketCondition.BREAKOUT
        else:
            return MarketCondition.RANGING
    
    def analyze_market(self, daily_setup: Optional[Dict] = None) -> MarketNarrative:
        """
        Compatibilitate cu realtime_monitor.py
        Alias pentru analyze_4h_setup
        """
        return self.analyze_4h_setup(daily_setup)
    
    def analyze_4h_setup(
        self,
        daily_setup: Optional[Dict] = None
    ) -> MarketNarrative:
        """
        Analizează setup pe 4H
        
        Args:
            daily_setup: Setup de la daily scanner (optional)
        
        Returns:
            MarketNarrative cu status și confidence
        """
        
        # Get data - 365 Daily candles (1 year) + 1200 H4 candles (50 days at 4H)
        df_4h = self.get_4h_data(1200)
        df_daily = self.get_daily_data(365)
        
        if df_4h is None or len(df_4h) < 10:
            logger.error(f"❌ Insufficient data for {self.symbol}")
            return MarketNarrative(
                symbol=self.symbol,
                timeframe="H4",
                timestamp=datetime.now(),
                condition=MarketCondition.RANGING,
                choch_count=0,
                fvg_count=0,
                higher_highs=False,
                higher_lows=False,
                lower_highs=False,
                lower_lows=False,
                atr=0.0,
                volatility_level="low",
                setup_status="data_unavailable",
                confidence=0.0,
                notes="Insufficient data - cBot may not support this symbol"
            )
        
        # Calculate ATR (4H)
        atr_4h = self.calculate_atr(df_4h, period=14)
        atr_daily = self.calculate_atr(df_daily, period=14) if df_daily is not None else 0.0
        
        # Analyze structure
        choches = self.detect_choch(df_4h)
        fvgs = self.detect_fvg(df_4h)
        
        # Trend
        higher_highs, higher_lows, lower_highs, lower_lows = self.analyze_trend(df_4h)
        
        # Market condition
        condition = self.determine_market_condition(
            len(choches), len(fvgs),
            higher_highs, higher_lows,
            lower_highs, lower_lows
        )
        
        # Volatility assessment
        if atr_4h > 0:
            atr_percent = (atr_4h / df_4h['close'].iloc[-1]) * 100
            if atr_percent < 0.5:
                volatility = "low"
            elif atr_percent < 1.5:
                volatility = "medium"
            else:
                volatility = "high"
        else:
            volatility = "unknown"
        
        # Determine setup status
        setup_status = "waiting"
        confidence = 0.0
        notes = []
        
        if daily_setup:
            # Confirmă setup de pe daily
            if condition == MarketCondition.BULLISH and daily_setup.get("type") == "BUY":
                confidence += 0.3
                notes.append("✅ Daily BUY confirmed by 4H bullish trend")
            elif condition == MarketCondition.BEARISH and daily_setup.get("type") == "SELL":
                confidence += 0.3
                notes.append("✅ Daily SELL confirmed by 4H bearish trend")
            
            # Check for FVG confluence
            if len(fvgs) > 0:
                confidence += 0.2
                notes.append(f"📍 {len(fvgs)} FVG(s) detected on 4H")
            
            # Check for CHoCH
            if len(choches) > 0:
                confidence += 0.2
                notes.append(f"🔄 {len(choches)} CHoCH break(s) detected")
            
            # Final status
            if confidence >= 0.6:
                setup_status = "ready_to_trade"
            elif confidence >= 0.4:
                setup_status = "monitoring_closely"
            else:
                setup_status = "waiting"
        else:
            # No daily setup reference
            if len(choches) > 0 or len(fvgs) > 0:
                confidence = 0.5
                setup_status = "monitoring_closely"
        
        return MarketNarrative(
            symbol=self.symbol,
            timeframe="H4",
            timestamp=datetime.now(),
            condition=condition,
            choch_count=len(choches),
            fvg_count=len(fvgs),
            higher_highs=higher_highs,
            higher_lows=higher_lows,
            lower_highs=lower_highs,
            lower_lows=lower_lows,
            atr=atr_4h,
            volatility_level=volatility,
            setup_status=setup_status,
            confidence=confidence,
            notes="\n".join(notes) if isinstance(notes, list) else notes
        )
    
    def format_narrative(self, narrative: MarketNarrative) -> str:
        """Format narrative for logging/alerts"""
        
        lines = [
            f"📊 {narrative.symbol} - 4H Analysis",
            f"⏰ {narrative.timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "",
            f"🎯 Status: {narrative.setup_status.upper()} ({narrative.confidence:.0%} confidence)",
            f"📈 Condition: {narrative.condition.value.upper()}",
            f"🔢 CHoCH: {narrative.choch_count} | FVG: {narrative.fvg_count}",
            f"📊 ATR: {narrative.atr:.6f} ({narrative.volatility_level.upper()})",
            "",
            f"Trend Structure:",
            f"  • Higher Highs: {'✅' if narrative.higher_highs else '❌'}",
            f"  • Higher Lows: {'✅' if narrative.higher_lows else '❌'}",
            f"  • Lower Highs: {'✅' if narrative.lower_highs else '❌'}",
            f"  • Lower Lows: {'✅' if narrative.lower_lows else '❌'}",
            "",
        ]
        
        if narrative.notes:
            lines.append(f"📝 Notes:\n{narrative.notes}")
        
        return "\n".join(lines)


# Test
if __name__ == "__main__":
    analyzer = SpatioTemporalAnalyzer("GBPUSD")
    narrative = analyzer.analyze_4h_setup(
        daily_setup={"type": "BUY"}
    )
    print(analyzer.format_narrative(narrative))
