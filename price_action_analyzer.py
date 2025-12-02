"""
GLITCH IN MATRIX - Price Action Analysis Module
Analizează structura pieței și detectează momentele când Smart Money intră
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from loguru import logger


@dataclass
class PriceActionSignal:
    """Semnal complet de price action cu confluence"""
    symbol: str
    direction: str  # 'bullish' or 'bearish'
    entry_zone: Tuple[float, float]  # (min, max)
    stop_loss: float
    take_profit: float
    confidence: int  # 1-10
    reasons: List[str]
    market_structure: str  # 'trending', 'ranging', 'reversal'
    momentum: str  # 'strong', 'moderate', 'weak'
    liquidity_cleared: bool
    fvg_present: bool
    choch_confirmed: bool


class PriceActionAnalyzer:
    """
    Analizează price action și structura pieței pentru a găsi GLITCH moments
    Combină SMC, market structure, și momentum pentru semnale high-probability
    """
    
    def __init__(self, swing_lookback: int = 5):
        self.swing_lookback = swing_lookback
        
    def analyze_full_context(self, df: pd.DataFrame, symbol: str) -> Optional[PriceActionSignal]:
        """
        Analiză completă - caută GLITCH IN MATRIX moments
        
        Returns:
            PriceActionSignal sau None dacă nu e setup valid
        """
        if len(df) < 50:
            return None
        
        # 1. Market Structure Analysis
        structure = self._analyze_market_structure(df)
        
        # 2. Smart Money Footprints (CHoCH, BOS, FVG)
        smc_data = self._detect_smart_money_activity(df)
        
        # 3. Liquidity Analysis (stops, sweeps)
        liquidity = self._analyze_liquidity(df)
        
        # 4. Momentum & Trend Strength
        momentum = self._analyze_momentum(df)
        
        # 5. Price Action Patterns la zone cheie
        patterns = self._detect_key_patterns(df)
        
        # 6. CONFLUENCE SCORING - când toate se aliniază!
        signal = self._build_signal(
            symbol=symbol,
            structure=structure,
            smc=smc_data,
            liquidity=liquidity,
            momentum=momentum,
            patterns=patterns,
            current_price=df['close'].iloc[-1]
        )
        
        return signal
    
    def _analyze_market_structure(self, df: pd.DataFrame) -> Dict:
        """
        Analizează structura pieței: HH/HL vs LH/LL
        Determină dacă suntem în trend sau reversal
        """
        swing_highs = self._find_swing_points(df, 'high')
        swing_lows = self._find_swing_points(df, 'low')
        
        if len(swing_highs) < 3 or len(swing_lows) < 3:
            return {'type': 'insufficient_data'}
        
        # Analizează ultimele 3 swing highs/lows
        recent_highs = swing_highs[-3:]
        recent_lows = swing_lows[-3:]
        
        # Check pentru Higher Highs + Higher Lows (BULLISH TREND)
        hh_pattern = all(recent_highs[i+1]['price'] > recent_highs[i]['price'] 
                        for i in range(len(recent_highs)-1))
        hl_pattern = all(recent_lows[i+1]['price'] > recent_lows[i]['price'] 
                        for i in range(len(recent_lows)-1))
        
        # Check pentru Lower Highs + Lower Lows (BEARISH TREND)
        lh_pattern = all(recent_highs[i+1]['price'] < recent_highs[i]['price'] 
                        for i in range(len(recent_highs)-1))
        ll_pattern = all(recent_lows[i+1]['price'] < recent_lows[i]['price'] 
                        for i in range(len(recent_lows)-1))
        
        # Determine structure
        if hh_pattern and hl_pattern:
            structure_type = 'bullish_trending'
            strength = 'strong' if len(recent_highs) >= 3 else 'moderate'
        elif lh_pattern and ll_pattern:
            structure_type = 'bearish_trending'
            strength = 'strong' if len(recent_lows) >= 3 else 'moderate'
        elif (hh_pattern and not hl_pattern) or (lh_pattern and not ll_pattern):
            structure_type = 'potential_reversal'
            strength = 'weak'
        else:
            structure_type = 'ranging'
            strength = 'neutral'
        
        return {
            'type': structure_type,
            'strength': strength,
            'swing_highs': recent_highs,
            'swing_lows': recent_lows,
            'last_high': recent_highs[-1]['price'],
            'last_low': recent_lows[-1]['price']
        }
    
    def _detect_smart_money_activity(self, df: pd.DataFrame) -> Dict:
        """
        Detectează CHoCH, BOS, și FVG (Fair Value Gaps)
        Acesta e核心 - unde Smart Money lasă urme!
        """
        swing_highs = self._find_swing_points(df, 'high')
        swing_lows = self._find_swing_points(df, 'low')
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {'choch': None, 'bos': None, 'fvg': None}
        
        # Detectare CHoCH (Change of Character)
        choch = self._detect_choch(df, swing_highs, swing_lows)
        
        # Detectare BOS (Break of Structure)
        bos = self._detect_bos(df, swing_highs, swing_lows)
        
        # Detectare FVG (Fair Value Gaps)
        fvg = self._detect_fvg_zones(df)
        
        return {
            'choch': choch,
            'bos': bos,
            'fvg': fvg,
            'smc_active': choch is not None or (bos and len(bos) > 0)
        }
    
    def _detect_choch(self, df: pd.DataFrame, highs: List, lows: List) -> Optional[Dict]:
        """
        Detectează CHoCH - momentul când trendul se schimbă
        BULLISH CHoCH: break high după LH+LL
        BEARISH CHoCH: break low după HH+HL
        """
        if len(df) < 20:
            return None
        
        current_price = df['close'].iloc[-1]
        recent_bars = df.tail(20)
        
        # Check pentru BULLISH CHoCH
        if len(highs) >= 2 and len(lows) >= 2:
            last_high = highs[-1]
            prev_high = highs[-2]
            last_low = lows[-1]
            prev_low = lows[-2]
            
            # BULLISH: break above recent high după structure bearish
            if (last_high['price'] < prev_high['price'] and  # LH
                last_low['price'] < prev_low['price'] and    # LL
                current_price > last_high['price']):          # Break!
                
                return {
                    'direction': 'bullish',
                    'break_level': last_high['price'],
                    'confirmed': True,
                    'bars_ago': len(df) - last_high['index']
                }
            
            # BEARISH: break below recent low după structure bullish
            if (last_high['price'] > prev_high['price'] and  # HH
                last_low['price'] > prev_low['price'] and    # HL
                current_price < last_low['price']):          # Break!
                
                return {
                    'direction': 'bearish',
                    'break_level': last_low['price'],
                    'confirmed': True,
                    'bars_ago': len(df) - last_low['index']
                }
        
        return None
    
    def _detect_bos(self, df: pd.DataFrame, highs: List, lows: List) -> List[Dict]:
        """
        Detectează BOS (Break of Structure) - continuarea trendului
        """
        bos_list = []
        recent_bars = df.tail(30)
        
        for i in range(len(recent_bars) - 1):
            bar = recent_bars.iloc[i]
            
            # Check dacă am rupt un swing high/low recent
            for high in highs[-5:]:
                if bar['close'] > high['price'] and bar['open'] < high['price']:
                    bos_list.append({
                        'direction': 'bullish',
                        'level': high['price'],
                        'index': i
                    })
            
            for low in lows[-5:]:
                if bar['close'] < low['price'] and bar['open'] > low['price']:
                    bos_list.append({
                        'direction': 'bearish',
                        'level': low['price'],
                        'index': i
                    })
        
        return bos_list
    
    def _detect_fvg_zones(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detectează Fair Value Gaps - zone unde prețul a sărit (imbalance)
        Acestea sunt MAGNETS pentru price retracement!
        """
        fvg_zones = []
        
        for i in range(2, len(df)):
            # 3-candle pattern: gap între candle[i-2] și candle[i]
            
            # BULLISH FVG: low[i] > high[i-2]
            if df['low'].iloc[i] > df['high'].iloc[i-2]:
                gap_size = df['low'].iloc[i] - df['high'].iloc[i-2]
                gap_percent = (gap_size / df['close'].iloc[i-1]) * 100
                
                if gap_percent > 0.1:  # Minimum 0.1% gap
                    fvg_zones.append({
                        'direction': 'bullish',
                        'top': df['low'].iloc[i],
                        'bottom': df['high'].iloc[i-2],
                        'index': i,
                        'filled': False
                    })
            
            # BEARISH FVG: high[i] < low[i-2]
            elif df['high'].iloc[i] < df['low'].iloc[i-2]:
                gap_size = df['low'].iloc[i-2] - df['high'].iloc[i]
                gap_percent = (gap_size / df['close'].iloc[i-1]) * 100
                
                if gap_percent > 0.1:
                    fvg_zones.append({
                        'direction': 'bearish',
                        'top': df['low'].iloc[i-2],
                        'bottom': df['high'].iloc[i],
                        'index': i,
                        'filled': False
                    })
        
        # Check dacă FVG-urile au fost filled
        current_price = df['close'].iloc[-1]
        for fvg in fvg_zones:
            if fvg['bottom'] <= current_price <= fvg['top']:
                fvg['filled'] = True
        
        # Return doar ultimele 10 FVG-uri unfilled
        unfilled = [f for f in fvg_zones if not f['filled']]
        return unfilled[-10:]
    
    def _analyze_liquidity(self, df: pd.DataFrame) -> Dict:
        """
        Analizează liquidity zones - unde sunt stop-loss-urile?
        Smart Money "sweep" aceste zone înainte să meargă în direcția corectă!
        """
        swing_highs = self._find_swing_points(df, 'high')
        swing_lows = self._find_swing_points(df, 'low')
        
        # Equal highs/lows = liquidity pools
        liquidity_highs = self._find_equal_levels(swing_highs, threshold=0.0005)
        liquidity_lows = self._find_equal_levels(swing_lows, threshold=0.0005)
        
        current_price = df['close'].iloc[-1]
        recent_high = df['high'].tail(10).max()
        recent_low = df['low'].tail(10).min()
        
        # Check dacă am swept liquidity recent
        swept_high = any(h['price'] < recent_high for h in liquidity_highs[-3:])
        swept_low = any(l['price'] > recent_low for l in liquidity_lows[-3:])
        
        return {
            'liquidity_highs': liquidity_highs[-5:],
            'liquidity_lows': liquidity_lows[-5:],
            'recent_sweep_high': swept_high,
            'recent_sweep_low': swept_low,
            'next_target_high': liquidity_highs[-1]['price'] if liquidity_highs else None,
            'next_target_low': liquidity_lows[-1]['price'] if liquidity_lows else None
        }
    
    def _analyze_momentum(self, df: pd.DataFrame) -> Dict:
        """
        Analizează momentum-ul pieței - cât de puternic e mișcarea?
        """
        if len(df) < 20:
            return {'strength': 'unknown'}
        
        # Calculate ATR pentru volatilitate
        atr = self._calculate_atr(df, period=14)
        
        # Calculate momentum indicators
        recent_bars = df.tail(10)
        price_change = (df['close'].iloc[-1] - df['close'].iloc[-10]) / df['close'].iloc[-10] * 100
        
        # Volume analysis (dacă există)
        volume_avg = df['tick_volume'].tail(20).mean() if 'tick_volume' in df else None
        volume_recent = df['tick_volume'].tail(5).mean() if 'tick_volume' in df else None
        volume_surge = volume_recent / volume_avg > 1.5 if volume_avg else False
        
        # Determine momentum strength
        if abs(price_change) > 1.0 and volume_surge:
            strength = 'explosive'
        elif abs(price_change) > 0.5:
            strength = 'strong'
        elif abs(price_change) > 0.2:
            strength = 'moderate'
        else:
            strength = 'weak'
        
        return {
            'strength': strength,
            'direction': 'bullish' if price_change > 0 else 'bearish',
            'price_change_pct': price_change,
            'atr': atr,
            'volume_surge': volume_surge
        }
    
    def _detect_key_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detectează pattern-uri cheie de price action:
        - Engulfing candles
        - Pin bars / hammers
        - Inside bars
        """
        patterns = []
        
        if len(df) < 3:
            return patterns
        
        # Check ultimele 3 candele
        for i in range(len(df) - 3, len(df)):
            if i < 1:
                continue
            
            current = df.iloc[i]
            previous = df.iloc[i-1]
            
            # BULLISH ENGULFING
            if (previous['close'] < previous['open'] and  # Previous bearish
                current['close'] > current['open'] and    # Current bullish
                current['open'] <= previous['close'] and  # Opens at/below prev close
                current['close'] >= previous['open']):    # Closes above prev open
                
                patterns.append({
                    'type': 'bullish_engulfing',
                    'index': i,
                    'strength': 'strong' if current['close'] > previous['high'] else 'moderate'
                })
            
            # BEARISH ENGULFING
            if (previous['close'] > previous['open'] and  # Previous bullish
                current['close'] < current['open'] and    # Current bearish
                current['open'] >= previous['close'] and  # Opens at/above prev close
                current['close'] <= previous['open']):    # Closes below prev open
                
                patterns.append({
                    'type': 'bearish_engulfing',
                    'index': i,
                    'strength': 'strong' if current['close'] < previous['low'] else 'moderate'
                })
            
            # PIN BAR / HAMMER (long wick, small body)
            body_size = abs(current['close'] - current['open'])
            total_range = current['high'] - current['low']
            
            if total_range > 0:
                body_ratio = body_size / total_range
                
                # BULLISH PIN BAR (long lower wick)
                lower_wick = min(current['open'], current['close']) - current['low']
                if lower_wick / total_range > 0.6 and body_ratio < 0.3:
                    patterns.append({
                        'type': 'bullish_pinbar',
                        'index': i,
                        'strength': 'strong' if body_ratio < 0.2 else 'moderate'
                    })
                
                # BEARISH PIN BAR (long upper wick)
                upper_wick = current['high'] - max(current['open'], current['close'])
                if upper_wick / total_range > 0.6 and body_ratio < 0.3:
                    patterns.append({
                        'type': 'bearish_pinbar',
                        'index': i,
                        'strength': 'strong' if body_ratio < 0.2 else 'moderate'
                    })
        
        return patterns
    
    def _build_signal(self, symbol: str, structure: Dict, smc: Dict, 
                     liquidity: Dict, momentum: Dict, patterns: List,
                     current_price: float) -> Optional[PriceActionSignal]:
        """
        Combină toate analizele și creează semnal HIGH-CONFLUENCE
        Aceasta e MAGIA - când toate se aliniază = GLITCH!
        """
        reasons = []
        confidence = 0
        direction = None
        
        # 1. Market Structure contribuție
        if structure['type'] == 'bullish_trending':
            reasons.append(f"📈 Bullish market structure ({structure['strength']})")
            confidence += 2 if structure['strength'] == 'strong' else 1
            direction = 'bullish'
        elif structure['type'] == 'bearish_trending':
            reasons.append(f"📉 Bearish market structure ({structure['strength']})")
            confidence += 2 if structure['strength'] == 'strong' else 1
            direction = 'bearish'
        elif structure['type'] == 'potential_reversal':
            reasons.append(f"🔄 Potential reversal setup")
            confidence += 1
        
        # 2. Smart Money Concepts
        choch_present = smc['choch'] is not None
        if choch_present:
            choch_dir = smc['choch']['direction']
            reasons.append(f"⚡ CHoCH {choch_dir.upper()} confirmed")
            confidence += 3
            if direction is None:
                direction = choch_dir
            elif direction != choch_dir:
                # Conflict! CHoCH overrides structure
                direction = choch_dir
                reasons.append("🔥 CHoCH OVERRIDE - Fresh direction change!")
                confidence += 1
        
        # FVG presence
        if smc['fvg'] and len(smc['fvg']) > 0:
            latest_fvg = smc['fvg'][-1]
            fvg_dir = latest_fvg['direction']
            
            # Check dacă price e în FVG zone
            if latest_fvg['bottom'] <= current_price <= latest_fvg['top']:
                reasons.append(f"💎 Price in FVG zone ({fvg_dir})")
                confidence += 2
            elif abs(current_price - latest_fvg['bottom']) / current_price < 0.005:
                reasons.append(f"📍 Price near FVG zone ({fvg_dir})")
                confidence += 1
        
        # 3. Liquidity cleared?
        if liquidity['recent_sweep_high'] and direction == 'bearish':
            reasons.append("🌊 Liquidity sweep HIGH completed")
            confidence += 2
        if liquidity['recent_sweep_low'] and direction == 'bullish':
            reasons.append("🌊 Liquidity sweep LOW completed")
            confidence += 2
        
        # 4. Momentum alignment
        if momentum['strength'] in ['strong', 'explosive']:
            if momentum['direction'] == direction:
                reasons.append(f"🚀 {momentum['strength'].upper()} momentum aligned")
                confidence += 2 if momentum['strength'] == 'explosive' else 1
        
        # 5. Price Action Patterns
        bullish_patterns = [p for p in patterns if 'bullish' in p['type']]
        bearish_patterns = [p for p in patterns if 'bearish' in p['type']]
        
        if direction == 'bullish' and bullish_patterns:
            reasons.append(f"📊 Bullish pattern: {bullish_patterns[0]['type']}")
            confidence += 1
        elif direction == 'bearish' and bearish_patterns:
            reasons.append(f"📊 Bearish pattern: {bearish_patterns[0]['type']}")
            confidence += 1
        
        # MINIMUM CONFIDENCE REQUIRED
        if confidence < 5 or direction is None:
            return None
        
        # Calculate entry, SL, TP based on structure
        entry_zone, stop_loss, take_profit = self._calculate_levels(
            direction, current_price, structure, smc, momentum
        )
        
        return PriceActionSignal(
            symbol=symbol,
            direction=direction,
            entry_zone=entry_zone,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=min(confidence, 10),
            reasons=reasons,
            market_structure=structure['type'],
            momentum=momentum['strength'],
            liquidity_cleared=liquidity['recent_sweep_high'] or liquidity['recent_sweep_low'],
            fvg_present=len(smc['fvg']) > 0 if smc['fvg'] else False,
            choch_confirmed=choch_present
        )
    
    def _calculate_levels(self, direction: str, current_price: float,
                         structure: Dict, smc: Dict, momentum: Dict) -> Tuple:
        """Calculează entry zone, SL, și TP bazat pe structură"""
        
        if direction == 'bullish':
            # Entry zone: current price +/- small range
            entry_min = current_price * 0.998
            entry_max = current_price * 1.002
            
            # SL: below last swing low
            stop_loss = structure['last_low'] * 0.998 if 'last_low' in structure else current_price * 0.985
            
            # TP: above last swing high sau 2:1 R:R
            risk = current_price - stop_loss
            take_profit = current_price + (risk * 2.5)  # 1:2.5 R:R
            
        else:  # bearish
            entry_min = current_price * 0.998
            entry_max = current_price * 1.002
            
            stop_loss = structure['last_high'] * 1.002 if 'last_high' in structure else current_price * 1.015
            
            risk = stop_loss - current_price
            take_profit = current_price - (risk * 2.5)
        
        return (entry_min, entry_max), stop_loss, take_profit
    
    # ============= HELPER METHODS =============
    
    def _find_swing_points(self, df: pd.DataFrame, price_type: str) -> List[Dict]:
        """Găsește swing highs sau lows"""
        swings = []
        lookback = self.swing_lookback
        
        for i in range(lookback, len(df) - lookback):
            if price_type == 'high':
                is_swing = all(df['high'].iloc[i] >= df['high'].iloc[i-j] for j in range(1, lookback+1)) and \
                          all(df['high'].iloc[i] >= df['high'].iloc[i+j] for j in range(1, lookback+1))
                if is_swing:
                    swings.append({'index': i, 'price': df['high'].iloc[i]})
            else:  # low
                is_swing = all(df['low'].iloc[i] <= df['low'].iloc[i-j] for j in range(1, lookback+1)) and \
                          all(df['low'].iloc[i] <= df['low'].iloc[i+j] for j in range(1, lookback+1))
                if is_swing:
                    swings.append({'index': i, 'price': df['low'].iloc[i]})
        
        return swings
    
    def _find_equal_levels(self, swing_points: List[Dict], threshold: float = 0.0005) -> List[Dict]:
        """Găsește equal highs/lows (liquidity pools)"""
        equal_levels = []
        
        for i in range(len(swing_points) - 1):
            for j in range(i + 1, len(swing_points)):
                price_diff = abs(swing_points[i]['price'] - swing_points[j]['price'])
                avg_price = (swing_points[i]['price'] + swing_points[j]['price']) / 2
                
                if price_diff / avg_price < threshold:
                    equal_levels.append({
                        'price': avg_price,
                        'count': 2,
                        'indices': [swing_points[i]['index'], swing_points[j]['index']]
                    })
        
        return equal_levels
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(df) < period:
            return 0.0
        
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean().iloc[-1]
        
        return atr


# ============= QUICK TEST FUNCTION =============

def test_price_action_analyzer():
    """Test cu date demo"""
    logger.info("🧪 Testing Price Action Analyzer...")
    
    # Creează date demo
    dates = pd.date_range(start='2024-01-01', periods=100, freq='h')
    np.random.seed(42)
    
    # Simulate bullish trend with CHoCH
    price = 1.0000
    prices = []
    for i in range(100):
        if i < 50:
            # Bearish phase (LH + LL)
            price += np.random.normal(-0.0001, 0.0005)
        else:
            # Bullish phase (HH + HL) după CHoCH
            price += np.random.normal(0.0002, 0.0005)
        prices.append(price)
    
    df = pd.DataFrame({
        'time': dates,
        'open': prices,
        'high': [p * 1.0005 for p in prices],
        'low': [p * 0.9995 for p in prices],
        'close': [p * 1.0001 for p in prices],
        'tick_volume': np.random.randint(100, 1000, 100)
    })
    
    analyzer = PriceActionAnalyzer()
    signal = analyzer.analyze_full_context(df, 'EURUSD')
    
    if signal:
        logger.info(f"\n✅ SIGNAL DETECTED!")
        logger.info(f"Direction: {signal.direction.upper()}")
        logger.info(f"Confidence: {signal.confidence}/10")
        logger.info(f"Reasons:")
        for reason in signal.reasons:
            logger.info(f"  • {reason}")
        logger.info(f"Entry Zone: {signal.entry_zone[0]:.5f} - {signal.entry_zone[1]:.5f}")
        logger.info(f"SL: {signal.stop_loss:.5f} | TP: {signal.take_profit:.5f}")
    else:
        logger.info("❌ No high-confidence signal found")


if __name__ == '__main__':
    test_price_action_analyzer()
