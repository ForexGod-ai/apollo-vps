"""
Advanced SMC (Smart Money Concepts) Algorithm
Based on LuxAlgo style + ForexGod's institutional knowledge

KEY PRINCIPLES:
- BOS & CHoCH calculated ONLY with BODY (wicks are manipulation/Wyckoff games)
- Order Blocks: Last opposing candle before strong move
- FVG: 3-candle imbalance gaps
- Liquidity: Equal highs/lows + stop hunts
- Premium/Discount: 50% Fibonacci zones for smart money entries
- Market Structure: Body-based HH/HL/LH/LL detection

Author: ForexGod's Vision + AI Implementation
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
from loguru import logger


@dataclass
class OrderBlock:
    """Order Block (OB) - Last opposing candle before institutional move"""
    type: str  # 'bullish' or 'bearish'
    top: float
    bottom: float
    body_top: float  # Close of the OB candle
    body_bottom: float  # Open of the OB candle
    index: int
    strength: str  # 'weak', 'medium', 'strong'
    volume: float
    touched: bool = False
    
    @property
    def middle(self) -> float:
        return (self.top + self.bottom) / 2
    
    @property
    def body_middle(self) -> float:
        return (self.body_top + self.body_bottom) / 2


@dataclass
class FairValueGap:
    """Fair Value Gap (FVG) - Imbalance zone"""
    type: str  # 'bullish' or 'bearish'
    top: float
    bottom: float
    index: int
    filled: bool = False
    
    @property
    def middle(self) -> float:
        return (self.top + self.bottom) / 2
    
    @property
    def size(self) -> float:
        return self.top - self.bottom


@dataclass
class LiquidityZone:
    """Liquidity Zone - Equal highs/lows where stops are sitting"""
    type: str  # 'resistance' (equal highs) or 'support' (equal lows)
    price: float
    count: int  # Number of times price touched this level
    index: int
    swept: bool = False


@dataclass
class MarketStructure:
    """Market Structure State"""
    trend: str  # 'bullish', 'bearish', 'ranging'
    last_high: float
    last_low: float
    highs: List[Tuple[int, float]]  # (index, price)
    lows: List[Tuple[int, float]]
    bos_detected: bool = False
    choch_detected: bool = False


@dataclass
class SMCSignal:
    """Complete SMC Signal with all confluence factors"""
    symbol: str
    direction: str  # 'bullish' or 'bearish'
    entry_zone: Tuple[float, float]
    stop_loss: float
    take_profit: float
    confidence: int  # 1-10
    
    # SMC Components
    order_block: Optional[OrderBlock]
    fvg: Optional[FairValueGap]
    liquidity_swept: bool
    market_structure: str
    in_premium: bool  # True if in premium zone (bearish bias)
    in_discount: bool  # True if in discount zone (bullish bias)
    
    # Confluence reasons
    reasons: List[str]
    
    # Risk/Reward
    risk_reward: float


class SMCAlgorithm:
    """
    Advanced Smart Money Concepts Algorithm
    
    Detects institutional footprints:
    - Order Blocks (where banks entered)
    - Fair Value Gaps (imbalance zones)
    - Liquidity Sweeps (stop hunts)
    - Market Structure (BOS/CHoCH with BODY only)
    - Premium/Discount Zones
    """
    
    def __init__(self):
        self.min_ob_strength = 0.0015  # 0.15% minimum move for OB
        self.fvg_min_gap = 0.001  # 0.1% minimum gap for FVG
        self.liquidity_tolerance = 0.0005  # 0.05% tolerance for equal levels
        
    def analyze(self, df: pd.DataFrame, symbol: str) -> Optional[SMCSignal]:
        """
        Main analysis function - returns SMC signal if found
        
        Args:
            df: DataFrame with OHLCV data
            symbol: Trading symbol
            
        Returns:
            SMCSignal if high-quality setup found, None otherwise
        """
        if len(df) < 50:
            return None
        
        # 1. Detect Market Structure (BODY-based BOS/CHoCH)
        structure = self._detect_market_structure(df)
        
        # 2. Detect Order Blocks
        order_blocks = self._detect_order_blocks(df, structure)
        
        # 3. Detect Fair Value Gaps
        fvgs = self._detect_fvgs(df)
        
        # 4. Detect Liquidity Zones
        liquidity_zones = self._detect_liquidity_zones(df)
        
        # 5. Calculate Premium/Discount Zones
        premium_discount = self._calculate_premium_discount(df)
        
        # 6. Check for Liquidity Sweeps
        liquidity_swept = self._check_liquidity_sweep(df, liquidity_zones)
        
        # 7. Build Signal with Confluence
        signal = self._build_smc_signal(
            df, symbol, structure, order_blocks, fvgs, 
            liquidity_swept, premium_discount
        )
        
        return signal
    
    def _detect_market_structure(self, df: pd.DataFrame) -> MarketStructure:
        """
        Detect market structure using BODY ONLY (no wicks!)
        
        BOS = Break of Structure (continuation)
        CHoCH = Change of Character (reversal)
        
        CRITICAL: Use CLOSE prices for highs/lows (body only)
        """
        # Use close prices (body) for structure
        body_highs = []
        body_lows = []
        
        # Find swing highs/lows with BODY
        window = 3
        for i in range(window, len(df) - window):
            # Body high = close if bullish, open if bearish
            body_high = max(df['open'].iloc[i], df['close'].iloc[i])
            body_low = min(df['open'].iloc[i], df['close'].iloc[i])
            
            # Check if this is a swing high (body)
            is_high = True
            is_low = True
            
            for j in range(i - window, i + window + 1):
                if j == i:
                    continue
                compare_high = max(df['open'].iloc[j], df['close'].iloc[j])
                compare_low = min(df['open'].iloc[j], df['close'].iloc[j])
                
                if body_high <= compare_high:
                    is_high = False
                if body_low >= compare_low:
                    is_low = False
            
            if is_high:
                body_highs.append((i, body_high))
            if is_low:
                body_lows.append((i, body_low))
        
        if not body_highs or not body_lows:
            return MarketStructure(
                trend='ranging',
                last_high=df['close'].iloc[-1],
                last_low=df['close'].iloc[-1],
                highs=body_highs,
                lows=body_lows
            )
        
        # Determine trend (HH/HL = bullish, LH/LL = bearish)
        recent_highs = [h[1] for h in body_highs[-3:]]
        recent_lows = [l[1] for l in body_lows[-3:]]
        
        trend = 'ranging'
        if len(recent_highs) >= 2 and len(recent_lows) >= 2:
            if recent_highs[-1] > recent_highs[-2] and recent_lows[-1] > recent_lows[-2]:
                trend = 'bullish'  # HH + HL
            elif recent_highs[-1] < recent_highs[-2] and recent_lows[-1] < recent_lows[-2]:
                trend = 'bearish'  # LH + LL
        
        return MarketStructure(
            trend=trend,
            last_high=body_highs[-1][1] if body_highs else df['close'].iloc[-1],
            last_low=body_lows[-1][1] if body_lows else df['close'].iloc[-1],
            highs=body_highs,
            lows=body_lows
        )
    
    def _detect_order_blocks(
        self, 
        df: pd.DataFrame, 
        structure: MarketStructure
    ) -> List[OrderBlock]:
        """
        Detect Order Blocks - last opposing candle before strong move
        
        Bullish OB: Last RED candle before bullish move
        Bearish OB: Last GREEN candle before bearish move
        """
        order_blocks = []
        
        for i in range(10, len(df) - 5):
            candle_open = df['open'].iloc[i]
            candle_close = df['close'].iloc[i]
            candle_high = df['high'].iloc[i]
            candle_low = df['low'].iloc[i]
            candle_body = abs(candle_close - candle_open)
            
            # Check next 5 candles for strong move
            next_5_high = df['high'].iloc[i+1:i+6].max()
            next_5_low = df['low'].iloc[i+1:i+6].min()
            
            # Bullish OB: Red candle followed by bullish move
            if candle_close < candle_open:  # Red candle
                move_up = (next_5_high - candle_high) / candle_high
                if move_up > self.min_ob_strength:
                    strength = 'strong' if move_up > 0.003 else 'medium'
                    
                    ob = OrderBlock(
                        type='bullish',
                        top=candle_high,
                        bottom=candle_low,
                        body_top=candle_open,  # Top of red candle body
                        body_bottom=candle_close,
                        index=i,
                        strength=strength,
                        volume=df['tick_volume'].iloc[i] if 'tick_volume' in df else 0
                    )
                    order_blocks.append(ob)
            
            # Bearish OB: Green candle followed by bearish move
            elif candle_close > candle_open:  # Green candle
                move_down = (candle_low - next_5_low) / candle_low
                if move_down > self.min_ob_strength:
                    strength = 'strong' if move_down > 0.003 else 'medium'
                    
                    ob = OrderBlock(
                        type='bearish',
                        top=candle_high,
                        bottom=candle_low,
                        body_top=candle_close,  # Top of green candle body
                        body_bottom=candle_open,
                        index=i,
                        strength=strength,
                        volume=df['tick_volume'].iloc[i] if 'tick_volume' in df else 0
                    )
                    order_blocks.append(ob)
        
        # Keep only untouched OBs (price hasn't returned yet)
        current_price = df['close'].iloc[-1]
        valid_obs = []
        
        for ob in order_blocks:
            if ob.type == 'bullish' and current_price >= ob.bottom:
                # Price near or above bullish OB
                if current_price <= ob.top * 1.02:  # Within 2% above
                    valid_obs.append(ob)
            elif ob.type == 'bearish' and current_price <= ob.top:
                # Price near or below bearish OB
                if current_price >= ob.bottom * 0.98:  # Within 2% below
                    valid_obs.append(ob)
        
        return valid_obs[-5:]  # Keep last 5 valid OBs
    
    def _detect_fvgs(self, df: pd.DataFrame) -> List[FairValueGap]:
        """
        Detect Fair Value Gaps (3-candle imbalance)
        
        Bullish FVG: Gap between candle[i-1].low and candle[i+1].high
        Bearish FVG: Gap between candle[i-1].high and candle[i+1].low
        """
        fvgs = []
        
        for i in range(1, len(df) - 1):
            # Bullish FVG: Previous low > Next high (gap up)
            if df['low'].iloc[i-1] > df['high'].iloc[i+1]:
                gap_size = (df['low'].iloc[i-1] - df['high'].iloc[i+1]) / df['close'].iloc[i]
                
                if gap_size > self.fvg_min_gap:
                    fvg = FairValueGap(
                        type='bullish',
                        top=df['low'].iloc[i-1],
                        bottom=df['high'].iloc[i+1],
                        index=i
                    )
                    fvgs.append(fvg)
            
            # Bearish FVG: Previous high < Next low (gap down)
            elif df['high'].iloc[i-1] < df['low'].iloc[i+1]:
                gap_size = (df['low'].iloc[i+1] - df['high'].iloc[i-1]) / df['close'].iloc[i]
                
                if gap_size > self.fvg_min_gap:
                    fvg = FairValueGap(
                        type='bearish',
                        top=df['low'].iloc[i+1],
                        bottom=df['high'].iloc[i-1],
                        index=i
                    )
                    fvgs.append(fvg)
        
        # Filter unfilled FVGs
        current_price = df['close'].iloc[-1]
        unfilled = []
        
        for fvg in fvgs:
            if fvg.type == 'bullish' and current_price < fvg.top:
                unfilled.append(fvg)
            elif fvg.type == 'bearish' and current_price > fvg.bottom:
                unfilled.append(fvg)
        
        return unfilled[-5:]  # Keep last 5 unfilled FVGs
    
    def _detect_liquidity_zones(self, df: pd.DataFrame) -> List[LiquidityZone]:
        """
        Detect liquidity zones (equal highs/lows where stops are sitting)
        """
        liquidity_zones = []
        
        # Find equal highs (resistance)
        highs = df['high'].iloc[-30:].values
        for i in range(len(highs) - 5):
            level = highs[i]
            count = 1
            
            for j in range(i + 1, len(highs)):
                if abs(highs[j] - level) / level < self.liquidity_tolerance:
                    count += 1
            
            if count >= 2:
                liquidity_zones.append(LiquidityZone(
                    type='resistance',
                    price=level,
                    count=count,
                    index=len(df) - 30 + i
                ))
        
        # Find equal lows (support)
        lows = df['low'].iloc[-30:].values
        for i in range(len(lows) - 5):
            level = lows[i]
            count = 1
            
            for j in range(i + 1, len(lows)):
                if abs(lows[j] - level) / level < self.liquidity_tolerance:
                    count += 1
            
            if count >= 2:
                liquidity_zones.append(LiquidityZone(
                    type='support',
                    price=level,
                    count=count,
                    index=len(df) - 30 + i
                ))
        
        return liquidity_zones
    
    def _check_liquidity_sweep(
        self, 
        df: pd.DataFrame, 
        liquidity_zones: List[LiquidityZone]
    ) -> bool:
        """
        Check if recent price action swept liquidity (stop hunt)
        """
        if not liquidity_zones:
            return False
        
        # Check last 5 candles for sweeps
        for i in range(max(0, len(df) - 5), len(df)):
            candle_high = df['high'].iloc[i]
            candle_low = df['low'].iloc[i]
            candle_close = df['close'].iloc[i]
            
            for liq in liquidity_zones:
                # Check if swept above resistance then closed below
                if liq.type == 'resistance':
                    if candle_high > liq.price and candle_close < liq.price:
                        return True
                
                # Check if swept below support then closed above
                elif liq.type == 'support':
                    if candle_low < liq.price and candle_close > liq.price:
                        return True
        
        return False
    
    def _calculate_premium_discount(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Calculate Premium/Discount zones (50% Fibonacci)
        
        Premium = Above 50% (bearish bias - institutions sell)
        Discount = Below 50% (bullish bias - institutions buy)
        """
        # Use last 50 candles for range
        high = df['high'].iloc[-50:].max()
        low = df['low'].iloc[-50:].min()
        range_size = high - low
        
        equilibrium = low + (range_size * 0.5)
        premium_zone = low + (range_size * 0.618)  # 61.8% (premium starts)
        discount_zone = low + (range_size * 0.382)  # 38.2% (discount starts)
        
        current_price = df['close'].iloc[-1]
        
        in_premium = current_price > premium_zone
        in_discount = current_price < discount_zone
        in_equilibrium = discount_zone <= current_price <= premium_zone
        
        return {
            'high': high,
            'low': low,
            'equilibrium': equilibrium,
            'premium_zone': premium_zone,
            'discount_zone': discount_zone,
            'in_premium': in_premium,
            'in_discount': in_discount,
            'in_equilibrium': in_equilibrium
        }
    
    def _detect_recent_choch(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        Detect FRESH CHoCH in last 10 bars (BODY-based)
        This gets PRIORITY over old Order Blocks!
        """
        if len(df) < 15:
            return None
        
        # Look at last 15 bars for fresh CHoCH
        recent_df = df.iloc[-15:]
        
        # Find swing highs/lows with BODY
        body_highs = []
        body_lows = []
        
        for i in range(2, len(recent_df) - 2):
            body_high = max(recent_df['open'].iloc[i], recent_df['close'].iloc[i])
            body_low = min(recent_df['open'].iloc[i], recent_df['close'].iloc[i])
            
            # Check if swing high
            is_high = True
            is_low = True
            for j in range(i - 2, i + 3):
                if j == i:
                    continue
                compare_high = max(recent_df['open'].iloc[j], recent_df['close'].iloc[j])
                compare_low = min(recent_df['open'].iloc[j], recent_df['close'].iloc[j])
                
                if body_high <= compare_high:
                    is_high = False
                if body_low >= compare_low:
                    is_low = False
            
            if is_high:
                body_highs.append((i, body_high))
            if is_low:
                body_lows.append((i, body_low))
        
        if len(body_highs) < 2 or len(body_lows) < 2:
            return None
        
        # Check for CHoCH pattern
        # Bullish CHoCH: Price breaks above recent high after lower lows
        # Bearish CHoCH: Price breaks below recent low after higher highs
        
        current_price = recent_df['close'].iloc[-1]
        
        # Bullish CHoCH check
        if len(body_lows) >= 2:
            # Check if we had lower lows (bearish structure)
            if body_lows[-1][1] < body_lows[-2][1]:
                # Now check if price broke above recent high
                if len(body_highs) >= 1:
                    recent_high = body_highs[-1][1]
                    if current_price > recent_high:
                        bars_ago = len(recent_df) - 1
                        return {
                            'direction': 'bullish',
                            'bar_ago': bars_ago,
                            'break_price': recent_high
                        }
        
        # Bearish CHoCH check
        if len(body_highs) >= 2:
            # Check if we had higher highs (bullish structure)
            if body_highs[-1][1] > body_highs[-2][1]:
                # Now check if price broke below recent low
                if len(body_lows) >= 1:
                    recent_low = body_lows[-1][1]
                    if current_price < recent_low:
                        bars_ago = len(recent_df) - 1
                        return {
                            'direction': 'bearish',
                            'bar_ago': bars_ago,
                            'break_price': recent_low
                        }
        
        return None
    
    def _build_smc_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        structure: MarketStructure,
        order_blocks: List[OrderBlock],
        fvgs: List[FairValueGap],
        liquidity_swept: bool,
        premium_discount: Dict
    ) -> Optional[SMCSignal]:
        """
        Build complete SMC signal with confluence scoring
        
        FOREXGOD ADJUSTMENT: Prioritize fresh CHoCH/BOS over old Order Blocks!
        """
        current_price = df['close'].iloc[-1]
        reasons = []
        confidence = 0
        
        # Check for FRESH CHoCH first (last 10 bars)
        recent_choch = self._detect_recent_choch(df)
        
        # Find best Order Block
        best_ob = None
        for ob in order_blocks:
            # Check recency - prefer recent OBs (last 20 bars)
            ob_age = len(df) - ob.index
            if ob_age > 20:
                continue  # Skip old OBs
            
            if ob.type == 'bullish' and premium_discount['in_discount']:
                best_ob = ob
                break
            elif ob.type == 'bearish' and premium_discount['in_premium']:
                best_ob = ob
                break
        
        # FRESH CHoCH OVERRIDE: If fresh CHoCH exists, prioritize it over OB direction
        if recent_choch and best_ob:
            if recent_choch['direction'] != best_ob.type:
                # CHoCH says opposite of OB - trust the FRESH move!
                logger.info(f"   🔄 FRESH CHoCH detected: {recent_choch['direction'].upper()} (overriding old OB)")
                direction = recent_choch['direction']
                confidence += 3  # Bonus for fresh CHoCH
                reasons.append(f"⚡ FRESH CHoCH {direction.upper()} (bar {recent_choch['bar_ago']} ago) - PRIORITY!")
            else:
                direction = best_ob.type
        elif not best_ob:
            return None
        else:
            direction = best_ob.type
        
        # Score confluence factors
        
        # 1. Order Block (base requirement)
        reasons.append(f"💎 {direction.upper()} Order Block at ${best_ob.body_middle:.5f}")
        confidence += 3
        
        # 2. Market Structure alignment
        if (direction == 'bullish' and structure.trend == 'bullish') or \
           (direction == 'bearish' and structure.trend == 'bearish'):
            reasons.append(f"📊 Market Structure: {structure.trend.upper()} (aligned)")
            confidence += 2
        
        # 3. FVG confluence
        matching_fvg = None
        for fvg in fvgs:
            if fvg.type == direction:
                matching_fvg = fvg
                reasons.append(f"⚡ FVG confluence: ${fvg.bottom:.5f} - ${fvg.top:.5f}")
                confidence += 2
                break
        
        # 4. Liquidity sweep
        if liquidity_swept:
            reasons.append("🎯 Liquidity SWEPT (stop hunt confirmed)")
            confidence += 2
        
        # 5. Premium/Discount positioning
        if direction == 'bullish' and premium_discount['in_discount']:
            reasons.append("💰 In DISCOUNT zone (smart money buying area)")
            confidence += 2
        elif direction == 'bearish' and premium_discount['in_premium']:
            reasons.append("💰 In PREMIUM zone (smart money selling area)")
            confidence += 2
        
        # 6. Order Block strength
        if best_ob.strength == 'strong':
            reasons.append(f"🔥 STRONG Order Block (institutional footprint)")
            confidence += 1
        
        # Minimum confidence threshold
        if confidence < 5:
            return None
        
        # Calculate entry, SL, TP
        if direction == 'bullish':
            entry_zone = (best_ob.body_bottom, best_ob.body_top)
            stop_loss = best_ob.bottom * 0.997  # SL below OB low
            take_profit = structure.last_high * 1.01  # TP at structure high
        else:
            entry_zone = (best_ob.body_bottom, best_ob.body_top)
            stop_loss = best_ob.top * 1.003  # SL above OB high
            take_profit = structure.last_low * 0.99  # TP at structure low
        
        # Calculate R:R
        risk = abs(entry_zone[0] - stop_loss)
        reward = abs(take_profit - entry_zone[0])
        risk_reward = reward / risk if risk > 0 else 0
        
        if risk_reward < 1.5:
            return None  # Minimum 1.5:1 R:R
        
        return SMCSignal(
            symbol=symbol,
            direction=direction,
            entry_zone=entry_zone,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=min(confidence, 10),
            order_block=best_ob,
            fvg=matching_fvg,
            liquidity_swept=liquidity_swept,
            market_structure=structure.trend,
            in_premium=premium_discount['in_premium'],
            in_discount=premium_discount['in_discount'],
            reasons=reasons,
            risk_reward=risk_reward
        )


# Test function
if __name__ == "__main__":
    logger.info("SMC Algorithm initialized - ForexGod's Institutional Edge")
    logger.info("Ready to detect smart money footprints! 💰")
