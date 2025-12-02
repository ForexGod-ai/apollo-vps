"""
SPATIOTEMPORAL MARKET ANALYZER
Viziune Spațiu-Timp pentru Trading

Acest modul analizează piața în 4D:
- SPAȚIU: Price levels (OB, FVG, structure)
- TIMP: Timeframes și secvența evenimentelor
- CONTEXT: Market conditions și momentum
- FUTURE: Predicții și așteptări
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from loguru import logger

from smc_detector import SMCDetector, CHoCH, FVG, TradeSetup


@dataclass
class SpatialLevel:
    """Un nivel spațial important (OB, FVG, structure)"""
    level_type: str  # 'order_block', 'fvg', 'swing_high', 'swing_low', 'liquidity'
    price_top: float
    price_bottom: float
    strength: int  # 0-100
    timeframe: str  # 'daily', '4h', '1h'
    created_at: datetime
    tested_count: int  # De câte ori a fost testat
    last_test: Optional[datetime]
    held_tests: int  # Câte teste a ținut
    direction: str  # 'bullish', 'bearish'
    active: bool = True


@dataclass
class TemporalEvent:
    """Un eveniment temporal important (CHoCH, BOS, breakout)"""
    event_type: str  # 'choch', 'bos', 'breakout', 'rejection', 'sweep'
    timeframe: str
    timestamp: datetime
    price: float
    direction: str  # 'bullish', 'bearish'
    significance: int  # 0-100
    confirmed: bool
    bars_ago: int


@dataclass
class MarketNarrative:
    """Story-ul pieței - ce s-a întâmplat și ce așteptăm"""
    symbol: str
    current_price: float
    
    # PAST - Ce s-a întâmplat
    past_events: List[TemporalEvent]
    key_levels: List[SpatialLevel]
    
    # PRESENT - Unde suntem acum
    current_state: str  # 'bullish_structure', 'bearish_structure', 'ranging', 'transition'
    price_position: str  # 'premium', 'equilibrium', 'discount'
    momentum: str  # 'strong_bullish', 'weak_bullish', 'neutral', 'weak_bearish', 'strong_bearish'
    
    # FUTURE - Ce așteptăm
    expected_scenarios: List[Dict]  # Multiple scenarii posibile
    waiting_for: List[str]  # Confirmări necesare
    invalidation_levels: List[float]  # Nivele care invalidează setup-ul
    
    # META
    confidence: int  # 0-100 cât de clar e narrativul
    complexity: str  # 'simple', 'moderate', 'complex'
    recommendation: str  # 'ready_to_trade', 'monitor_closely', 'wait_for_confirmation', 'avoid'


class SpatioTemporalAnalyzer:
    """
    Analizator principal care vede piața în 4D
    """
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.detector = SMCDetector()
        
        # Historical context (memory)
        self.spatial_levels: List[SpatialLevel] = []
        self.temporal_events: List[TemporalEvent] = []
        self.narrative_history: List[MarketNarrative] = []
        
    def analyze_market(self) -> MarketNarrative:
        """
        Analiză completă 4D a pieței
        Returns: MarketNarrative cu tot story-ul
        """
        logger.info(f"\n🔍 SPATIOTEMPORAL ANALYSIS - {self.symbol}")
        
        # 1. Colectează date multi-timeframe
        df_daily = self._get_data('D1', 100)
        df_4h = self._get_data('H4', 200)
        df_1h = self._get_data('H1', 300)
        
        current_price = df_daily['close'].iloc[-1]
        
        # 2. SPAȚIU - Identifică toate nivelurile importante
        spatial_levels = self._identify_spatial_levels(df_daily, df_4h, df_1h)
        
        # 3. TIMP - Identifică toate evenimentele temporale
        temporal_events = self._identify_temporal_events(df_daily, df_4h, df_1h)
        
        # 4. Construiește narrativul (story-ul pieței)
        narrative = self._build_narrative(
            current_price, 
            spatial_levels, 
            temporal_events,
            df_daily,
            df_4h,
            df_1h
        )
        
        # 5. Salvează în memory pentru tracking
        self.spatial_levels = spatial_levels
        self.temporal_events = temporal_events
        self.narrative_history.append(narrative)
        
        return narrative
    
    def _identify_spatial_levels(
        self, 
        df_daily: pd.DataFrame, 
        df_4h: pd.DataFrame,
        df_1h: pd.DataFrame
    ) -> List[SpatialLevel]:
        """
        Identifică toate nivelurile spațiale importante
        """
        levels = []
        
        # DAILY LEVELS (cele mai importante)
        logger.info("📍 Identifying DAILY spatial levels...")
        
        # 1. Order Blocks (Daily)
        daily_obs = self._find_order_blocks(df_daily, 'daily')
        levels.extend(daily_obs)
        logger.info(f"   Found {len(daily_obs)} Daily Order Blocks")
        
        # 2. FVGs (Daily)
        daily_fvgs = self._find_fvg_levels(df_daily, 'daily')
        levels.extend(daily_fvgs)
        logger.info(f"   Found {len(daily_fvgs)} Daily FVGs")
        
        # 3. Swing Highs/Lows (Daily)
        daily_swings = self._find_swing_levels(df_daily, 'daily')
        levels.extend(daily_swings)
        logger.info(f"   Found {len(daily_swings)} Daily Swing Levels")
        
        # 4H LEVELS (confirmation levels)
        logger.info("📍 Identifying 4H spatial levels...")
        
        h4_obs = self._find_order_blocks(df_4h, '4h')
        h4_fvgs = self._find_fvg_levels(df_4h, '4h')
        h4_swings = self._find_swing_levels(df_4h, '4h')
        
        levels.extend(h4_obs + h4_fvgs + h4_swings)
        logger.info(f"   Found {len(h4_obs + h4_fvgs + h4_swings)} 4H levels")
        
        # 1H LEVELS (entry levels - doar cele foarte recent)
        logger.info("📍 Identifying 1H spatial levels (recent only)...")
        
        h1_obs = self._find_order_blocks(df_1h, '1h', max_age=20)
        h1_fvgs = self._find_fvg_levels(df_1h, '1h', max_age=20)
        
        levels.extend(h1_obs + h1_fvgs)
        logger.info(f"   Found {len(h1_obs + h1_fvgs)} 1H levels")
        
        # Sortează by strength
        levels.sort(key=lambda x: x.strength, reverse=True)
        
        logger.info(f"✅ Total spatial levels identified: {len(levels)}")
        
        return levels
    
    def _identify_temporal_events(
        self,
        df_daily: pd.DataFrame,
        df_4h: pd.DataFrame,
        df_1h: pd.DataFrame
    ) -> List[TemporalEvent]:
        """
        Identifică toate evenimentele temporale importante
        """
        events = []
        
        # DAILY EVENTS (macro story)
        logger.info("⏰ Identifying DAILY temporal events...")
        
        # 1. CHoCH (Daily) - FOARTE IMPORTANT
        daily_chochs = self._find_choch_events(df_daily, 'daily')
        events.extend(daily_chochs)
        logger.info(f"   Found {len(daily_chochs)} Daily CHoCH events")
        
        # 2. BOS (Daily)
        daily_bos = self._find_bos_events(df_daily, 'daily')
        events.extend(daily_bos)
        logger.info(f"   Found {len(daily_bos)} Daily BOS events")
        
        # 4H EVENTS (confirmation story)
        logger.info("⏰ Identifying 4H temporal events...")
        
        h4_chochs = self._find_choch_events(df_4h, '4h')
        h4_bos = self._find_bos_events(df_4h, '4h')
        h4_rejections = self._find_rejection_events(df_4h, '4h')
        
        events.extend(h4_chochs + h4_bos + h4_rejections)
        logger.info(f"   Found {len(h4_chochs + h4_bos + h4_rejections)} 4H events")
        
        # 1H EVENTS (entry timing)
        logger.info("⏰ Identifying 1H temporal events (recent only)...")
        
        h1_chochs = self._find_choch_events(df_1h, '1h', max_lookback=50)
        h1_rejections = self._find_rejection_events(df_1h, '1h', max_lookback=50)
        h1_sweeps = self._find_liquidity_sweeps(df_1h, '1h')
        
        events.extend(h1_chochs + h1_rejections + h1_sweeps)
        logger.info(f"   Found {len(h1_chochs + h1_rejections + h1_sweeps)} 1H events")
        
        # Sortează chronologically (oldest first)
        events.sort(key=lambda x: x.timestamp)
        
        logger.info(f"✅ Total temporal events identified: {len(events)}")
        
        return events
    
    def _build_narrative(
        self,
        current_price: float,
        spatial_levels: List[SpatialLevel],
        temporal_events: List[TemporalEvent],
        df_daily: pd.DataFrame,
        df_4h: pd.DataFrame,
        df_1h: pd.DataFrame
    ) -> MarketNarrative:
        """
        Construiește story-ul complet al pieței
        """
        logger.info("\n📖 Building Market Narrative...")
        
        # 1. Analizează PAST - Ce s-a întâmplat?
        past_story = self._analyze_past(temporal_events)
        
        # 2. Analizează PRESENT - Unde suntem acum?
        present_state = self._analyze_present(
            current_price, 
            spatial_levels, 
            temporal_events,
            df_daily,
            df_4h,
            df_1h
        )
        
        # 3. Proiectează FUTURE - Ce așteptăm?
        future_scenarios = self._project_future(
            current_price,
            spatial_levels,
            temporal_events,
            present_state,
            df_daily,
            df_4h
        )
        
        # 4. Determină RECOMMENDATION
        recommendation = self._make_recommendation(
            present_state,
            future_scenarios,
            spatial_levels,
            temporal_events
        )
        
        narrative = MarketNarrative(
            symbol=self.symbol,
            current_price=current_price,
            past_events=temporal_events[-20:],  # Ultimele 20 events
            key_levels=spatial_levels[:10],  # Top 10 cele mai importante
            current_state=present_state['state'],
            price_position=present_state['position'],
            momentum=present_state['momentum'],
            expected_scenarios=future_scenarios,
            waiting_for=self._identify_waiting_confirmations(present_state, future_scenarios),
            invalidation_levels=self._identify_invalidation_levels(spatial_levels, temporal_events),
            confidence=self._calculate_narrative_confidence(present_state, future_scenarios),
            complexity=self._assess_complexity(spatial_levels, temporal_events),
            recommendation=recommendation
        )
        
        return narrative
    
    def _analyze_past(self, events: List[TemporalEvent]) -> Dict:
        """
        Analizează ce s-a întâmplat în trecut
        """
        # Ultimele 10 events importante
        recent_events = events[-10:]
        
        # Detectează trend changes
        choch_events = [e for e in recent_events if e.event_type == 'choch']
        
        # Latest CHoCH pe fiecare timeframe
        daily_choch = next((e for e in reversed(choch_events) if e.timeframe == 'daily'), None)
        h4_choch = next((e for e in reversed(choch_events) if e.timeframe == '4h'), None)
        h1_choch = next((e for e in reversed(choch_events) if e.timeframe == '1h'), None)
        
        return {
            'recent_events': recent_events,
            'daily_choch': daily_choch,
            'h4_choch': h4_choch,
            'h1_choch': h1_choch,
            'last_major_event': recent_events[-1] if recent_events else None
        }
    
    def _analyze_present(
        self,
        current_price: float,
        levels: List[SpatialLevel],
        events: List[TemporalEvent],
        df_daily: pd.DataFrame,
        df_4h: pd.DataFrame,
        df_1h: pd.DataFrame
    ) -> Dict:
        """
        Analizează starea curentă a pieței
        """
        # Market Structure
        daily_structure = self._determine_structure(df_daily, 'daily')
        h4_structure = self._determine_structure(df_4h, '4h')
        
        # Price Position (Premium/Discount)
        price_position = self._calculate_price_position(current_price, df_daily)
        
        # Momentum
        momentum = self._calculate_momentum(df_daily, df_4h, df_1h)
        
        # Closest levels
        closest_levels = self._find_closest_levels(current_price, levels)
        
        return {
            'state': daily_structure,
            'h4_state': h4_structure,
            'position': price_position,
            'momentum': momentum,
            'closest_support': closest_levels['support'],
            'closest_resistance': closest_levels['resistance'],
            'at_key_level': closest_levels['at_level']
        }
    
    def _determine_strategy_type(
        self,
        df_daily: pd.DataFrame,
        events: List[TemporalEvent]
    ) -> str:
        """
        Determină tipul de strategie bazat pe structura Daily
        
        Returns:
            'continuity_bullish': Trend bullish stabilit (HH+HL), trade pullbacks
            'continuity_bearish': Trend bearish stabilit (LL+LH), trade pullbacks
            'reversal_bullish': Recent Daily CHoCH bullish, trade reversal
            'reversal_bearish': Recent Daily CHoCH bearish, trade reversal
            'ranging': No clear trend or CHoCH
        """
        logger.info("🎯 Determining Strategy Type...")
        
        # Check pentru Daily CHoCH recent (ultimele 15-20 candles)
        recent_daily_choch = next(
            (e for e in reversed(events) if e.event_type == 'choch' and e.timeframe == 'daily' and e.bars_ago <= 20),
            None
        )
        
        # Dacă avem CHoCH recent = REVERSAL STRATEGY
        if recent_daily_choch:
            strategy = f"reversal_{recent_daily_choch.direction}"
            logger.info(f"   ✅ REVERSAL Strategy detected: Daily CHoCH {recent_daily_choch.direction} {recent_daily_choch.bars_ago} bars ago")
            logger.info(f"   📋 Strategy: Wait for retest of FVG created on breakout → 4H CHoCH → Entry in new direction")
            return strategy
        
        # Nu avem CHoCH recent - check pentru trend stabilit (CONTINUITY)
        # IMPORTANT: Use CLOSE prices only (BODY), not high/low (wicks)
        recent_candles = df_daily.tail(20)  # Analyze more candles for better trend detection
        closes = recent_candles['close'].values
        
        # Identify swing highs and swing lows using CLOSE prices
        swing_highs = []
        swing_lows = []
        
        for j in range(2, len(closes) - 2):
            # Swing high: CLOSE higher than 2 candles before and after
            if (closes[j] > closes[j-1] and closes[j] > closes[j-2] and
                closes[j] > closes[j+1] and closes[j] > closes[j+2]):
                swing_highs.append(closes[j])
            
            # Swing low: CLOSE lower than 2 candles before and after
            if (closes[j] < closes[j-1] and closes[j] < closes[j-2] and
                closes[j] < closes[j+1] and closes[j] < closes[j+2]):
                swing_lows.append(closes[j])
        
        logger.info(f"   📊 Structure Analysis (last 20 candles using CLOSE prices):")
        logger.info(f"      Swing Highs found: {len(swing_highs)}")
        logger.info(f"      Swing Lows found: {len(swing_lows)}")
        
        # Analyze swing high progression (HH or LH?)
        hh_count = 0
        lh_count = 0
        if len(swing_highs) >= 3:
            for k in range(1, len(swing_highs)):
                if swing_highs[k] > swing_highs[k-1]:
                    hh_count += 1
                elif swing_highs[k] < swing_highs[k-1]:
                    lh_count += 1
            
            logger.info(f"      Swing High progression: HH={hh_count}, LH={lh_count}")
        
        # Analyze swing low progression (HL or LL?)
        hl_count = 0
        ll_count = 0
        if len(swing_lows) >= 3:
            for k in range(1, len(swing_lows)):
                if swing_lows[k] > swing_lows[k-1]:
                    hl_count += 1
                elif swing_lows[k] < swing_lows[k-1]:
                    ll_count += 1
            
            logger.info(f"      Swing Low progression: HL={hl_count}, LL={ll_count}")
        
        # Bullish Continuity: Predominantly HH + HL
        if hh_count >= 2 and hl_count >= 2 and (hh_count + hl_count) > (lh_count + ll_count):
            logger.info(f"   ✅ CONTINUITY BULLISH detected: {hh_count} HH + {hl_count} HL")
            logger.info(f"   📋 Strategy: Wait for pullback to HL in FVG → 4H CHoCH confirms support → Continue bullish")
            return 'continuity_bullish'
        
        # Bearish Continuity: Predominantly LH + LL
        if lh_count >= 2 and ll_count >= 2 and (lh_count + ll_count) > (hh_count + hl_count):
            logger.info(f"   ✅ CONTINUITY BEARISH detected: {lh_count} LH + {ll_count} LL")
            logger.info(f"   📋 Strategy: Wait for pullback to LH in FVG → 4H CHoCH confirms resistance → Continue bearish")
            return 'continuity_bearish'
        
        # No clear trend or CHoCH
        logger.info(f"   ⚠️ RANGING detected: No clear HH+HL or LL+LH structure, no recent CHoCH")
        return 'ranging'
    
    def _project_future(
        self,
        current_price: float,
        levels: List[SpatialLevel],
        events: List[TemporalEvent],
        present_state: Dict,
        df_daily: pd.DataFrame,
        df_4h: pd.DataFrame
    ) -> List[Dict]:
        """
        Proiectează scenarii viitoare posibile
        UPDATED: Detectează CONTINUITY vs REVERSAL apoi generează scenarii corespunzătoare
        """
        scenarios = []
        
        # STEP 1: Determină tipul de strategie
        strategy_type = self._determine_strategy_type(df_daily, events)
        
        logger.info(f"\n🎯 STRATEGY TYPE: {strategy_type.upper()}")
        logger.info(f"   Generating scenarios for {strategy_type}...")
        
        # STEP 2: Generează scenarii bazate pe tipul de strategie
        
        if strategy_type == 'reversal_bullish':
            scenarios = self._generate_reversal_bullish_scenarios(
                current_price, levels, events, present_state, df_daily, df_4h
            )
        
        elif strategy_type == 'reversal_bearish':
            scenarios = self._generate_reversal_bearish_scenarios(
                current_price, levels, events, present_state, df_daily, df_4h
            )
        
        elif strategy_type == 'continuity_bullish':
            scenarios = self._generate_continuity_bullish_scenarios(
                current_price, levels, events, present_state, df_daily, df_4h
            )
        
        elif strategy_type == 'continuity_bearish':
            scenarios = self._generate_continuity_bearish_scenarios(
                current_price, levels, events, present_state, df_daily, df_4h
            )
        
        else:  # ranging
            scenarios = self._generate_ranging_scenarios(
                current_price, levels, events, present_state, df_daily, df_4h
            )
        
        return scenarios
    
    def _generate_reversal_bullish_scenarios(
        self,
        current_price: float,
        levels: List[SpatialLevel],
        events: List[TemporalEvent],
        present_state: Dict,
        df_daily: pd.DataFrame,
        df_4h: pd.DataFrame
    ) -> List[Dict]:
        """
        REVERSAL BULLISH Strategy:
        - Era BEARISH (LH+LL)
        - Daily CHoCH bullish (rupt structura)
        - Acum așteaptă retest FVG → 4H CHoCH → Entry LONG
        """
        scenarios = []
        
        # Find Daily CHoCH
        daily_choch = next(
            (e for e in reversed(events) if e.event_type == 'choch' and e.timeframe == 'daily' and e.direction == 'bullish'),
            None
        )
        
        # Find FVG zone created on breakout
        fvg_level = next(
            (l for l in levels if l.level_type == 'fvg' and l.direction == 'bullish' and l.timeframe == 'daily'),
            None
        )
        
        if fvg_level:
            atr = self._calculate_atr(df_daily)
            
            # SCENARIO 1: Optimal Retest & Reversal
            scenarios.append({
                'name': 'Optimal Retest & Reversal',
                'probability': self._calculate_scenario_probability('optimal_retest', present_state, fvg_level, daily_choch),
                'description': f'Price retests FVG bottom at ${fvg_level.price_bottom:.5f}, gets 4H CHoCH bullish, NEW bullish trend begins',
                'action': 'WAIT for price @ FVG bottom, then WAIT for 4H CHoCH bullish confirmation',
                'targets': [
                    {'level': fvg_level.price_bottom, 'type': 'entry_zone'},
                    {'level': fvg_level.price_bottom - atr * 0.5, 'type': 'stop_loss'},
                    {'level': self._find_next_resistance(current_price, levels), 'type': 'take_profit'}
                ],
                'invalidation': fvg_level.price_bottom - atr * 0.5,
                'confirmations_needed': ['price_at_fvg_bottom', '4h_rejection_candle', '4h_choch_bullish'],
                'timeframe': 'Daily REVERSAL + 4H entry',
                'expected_timing': self._estimate_timing(current_price, fvg_level.price_bottom, df_4h),
                'strategy_type': 'REVERSAL_BULLISH'
            })
            
            # SCENARIO 2: Early Bounce (miss optimal)
            scenarios.append({
                'name': 'Early Bounce',
                'probability': 20,
                'description': 'Price bounces before reaching FVG bottom - miss optimal entry',
                'action': 'MONITOR - Wait for next pullback or skip',
                'targets': [],
                'invalidation': None,
                'confirmations_needed': [],
                'timeframe': 'N/A',
                'expected_timing': 'Unknown',
                'strategy_type': 'REVERSAL_BULLISH'
            })
        
        # SCENARIO 3: Invalidation (False CHoCH)
        invalidation_level = daily_choch.price - self._calculate_atr(df_daily) if daily_choch else current_price * 0.98
        scenarios.append({
            'name': 'Invalidation - False CHoCH',
            'probability': 15,
            'description': f'Price breaks below ${invalidation_level:.5f}, Daily CHoCH was false, continue bearish',
            'action': 'AVOID - Wait for new setup',
            'targets': [],
            'invalidation': invalidation_level,
            'confirmations_needed': [],
            'timeframe': 'N/A',
            'expected_timing': 'N/A',
            'strategy_type': 'REVERSAL_BULLISH'
        })
        
        return scenarios
    
    def _generate_continuity_bullish_scenarios(
        self,
        current_price: float,
        levels: List[SpatialLevel],
        events: List[TemporalEvent],
        present_state: Dict,
        df_daily: pd.DataFrame,
        df_4h: pd.DataFrame
    ) -> List[Dict]:
        """
        CONTINUITY BULLISH Strategy:
        - Trend bullish stabilit (HH+HL)
        - NU e nevoie de CHoCH pe Daily!
        - Așteaptă pullback la HL în FVG → 4H CHoCH confirmă zona → Continue LONG
        """
        scenarios = []
        
        # Find FVG zone for pullback
        fvg_level = next(
            (l for l in levels if l.level_type == 'fvg' and l.direction == 'bullish' and l.timeframe == 'daily'),
            None
        )
        
        if fvg_level:
            atr = self._calculate_atr(df_daily)
            
            # SCENARIO 1: Healthy Pullback & Continuation
            scenarios.append({
                'name': 'Healthy Pullback & Continuation',
                'probability': self._calculate_scenario_probability('continuity_pullback', present_state, fvg_level, None),
                'description': f'Price pulls back to HL at ${fvg_level.price_bottom:.5f}, 4H CHoCH confirms support holds, CONTINUE bullish trend',
                'action': 'WAIT for pullback to FVG/HL zone, then WAIT for 4H CHoCH bullish (confirms zona ține)',
                'targets': [
                    {'level': fvg_level.price_bottom, 'type': 'entry_zone_hl'},
                    {'level': fvg_level.price_bottom - atr * 0.4, 'type': 'stop_loss'},
                    {'level': self._find_next_resistance(current_price, levels), 'type': 'take_profit'}
                ],
                'invalidation': fvg_level.price_bottom - atr * 0.4,
                'confirmations_needed': ['pullback_to_hl', 'price_in_fvg', '4h_choch_bullish_confirms_support'],
                'timeframe': 'Daily CONTINUITY + 4H confirmation',
                'expected_timing': self._estimate_timing(current_price, fvg_level.price_bottom, df_4h),
                'strategy_type': 'CONTINUITY_BULLISH'
            })
            
            # SCENARIO 2: Shallow Pullback (early entry opportunity)
            scenarios.append({
                'name': 'Shallow Pullback',
                'probability': 25,
                'description': 'Price makes shallow pullback above FVG bottom - strong momentum',
                'action': 'MONITOR - May enter if 4H shows bullish CHoCH at higher level',
                'targets': [],
                'invalidation': None,
                'confirmations_needed': ['4h_choch_bullish_at_current_level'],
                'timeframe': '4H',
                'expected_timing': 'Short-term',
                'strategy_type': 'CONTINUITY_BULLISH'
            })
        
        # SCENARIO 3: Break of Structure (would become reversal!)
        recent_lows = df_daily['low'].tail(10).min()
        scenarios.append({
            'name': 'Structure Break - Trend Reversal',
            'probability': 10,
            'description': f'Price breaks below ${recent_lows:.5f} - bullish trend BREAKS, ar deveni REVERSAL bearish!',
            'action': 'AVOID - Bullish setup invalidated, wait for bearish reversal setup',
            'targets': [],
            'invalidation': recent_lows,
            'confirmations_needed': [],
            'timeframe': 'N/A',
            'expected_timing': 'N/A',
            'strategy_type': 'CONTINUITY_BULLISH'
        })
        
        return scenarios
    
    def _generate_reversal_bearish_scenarios(
        self,
        current_price: float,
        levels: List[SpatialLevel],
        events: List[TemporalEvent],
        present_state: Dict,
        df_daily: pd.DataFrame,
        df_4h: pd.DataFrame
    ) -> List[Dict]:
        """
        REVERSAL BEARISH Strategy:
        - Era BULLISH (HH+HL)
        - Daily CHoCH bearish (rupt structura)
        - Acum așteaptă retest FVG → 4H CHoCH → Entry SHORT
        """
        scenarios = []
        
        daily_choch = next(
            (e for e in reversed(events) if e.event_type == 'choch' and e.timeframe == 'daily' and e.direction == 'bearish'),
            None
        )
        
        fvg_level = next(
            (l for l in levels if l.level_type == 'fvg' and l.direction == 'bearish' and l.timeframe == 'daily'),
            None
        )
        
        if fvg_level:
            atr = self._calculate_atr(df_daily)
            
            scenarios.append({
                'name': 'Optimal Retest & Reversal',
                'probability': self._calculate_scenario_probability('optimal_retest', present_state, fvg_level, daily_choch),
                'description': f'Price retests FVG top at ${fvg_level.price_top:.5f}, gets 4H CHoCH bearish, NEW bearish trend begins',
                'action': 'WAIT for price @ FVG top, then WAIT for 4H CHoCH bearish confirmation',
                'targets': [
                    {'level': fvg_level.price_top, 'type': 'entry_zone'},
                    {'level': fvg_level.price_top + atr * 0.5, 'type': 'stop_loss'},
                    {'level': self._find_next_support(current_price, levels), 'type': 'take_profit'}
                ],
                'invalidation': fvg_level.price_top + atr * 0.5,
                'confirmations_needed': ['price_at_fvg_top', '4h_rejection_candle', '4h_choch_bearish'],
                'timeframe': 'Daily REVERSAL + 4H entry',
                'expected_timing': self._estimate_timing(current_price, fvg_level.price_top, df_4h),
                'strategy_type': 'REVERSAL_BEARISH'
            })
        
        return scenarios
    
    def _generate_continuity_bearish_scenarios(
        self,
        current_price: float,
        levels: List[SpatialLevel],
        events: List[TemporalEvent],
        present_state: Dict,
        df_daily: pd.DataFrame,
        df_4h: pd.DataFrame
    ) -> List[Dict]:
        """
        CONTINUITY BEARISH Strategy:
        - Trend bearish stabilit (LL+LH)
        - NU e nevoie de CHoCH pe Daily!
        - Așteaptă pullback la LH în FVG → 4H CHoCH confirmă zona → Continue SHORT
        """
        scenarios = []
        
        fvg_level = next(
            (l for l in levels if l.level_type == 'fvg' and l.direction == 'bearish' and l.timeframe == 'daily'),
            None
        )
        
        if fvg_level:
            atr = self._calculate_atr(df_daily)
            
            scenarios.append({
                'name': 'Healthy Pullback & Continuation',
                'probability': self._calculate_scenario_probability('continuity_pullback', present_state, fvg_level, None),
                'description': f'Price pulls back to LH at ${fvg_level.price_top:.5f}, 4H CHoCH confirms resistance holds, CONTINUE bearish trend',
                'action': 'WAIT for pullback to FVG/LH zone, then WAIT for 4H CHoCH bearish (confirms zona ține)',
                'targets': [
                    {'level': fvg_level.price_top, 'type': 'entry_zone_lh'},
                    {'level': fvg_level.price_top + atr * 0.4, 'type': 'stop_loss'},
                    {'level': self._find_next_support(current_price, levels), 'type': 'take_profit'}
                ],
                'invalidation': fvg_level.price_top + atr * 0.4,
                'confirmations_needed': ['pullback_to_lh', 'price_in_fvg', '4h_choch_bearish_confirms_resistance'],
                'timeframe': 'Daily CONTINUITY + 4H confirmation',
                'expected_timing': self._estimate_timing(current_price, fvg_level.price_top, df_4h),
                'strategy_type': 'CONTINUITY_BEARISH'
            })
        
        return scenarios
    
    def _generate_ranging_scenarios(
        self,
        current_price: float,
        levels: List[SpatialLevel],
        events: List[TemporalEvent],
        present_state: Dict,
        df_daily: pd.DataFrame,
        df_4h: pd.DataFrame
    ) -> List[Dict]:
        """
        RANGING Market:
        - No clear trend (HH+HL or LL+LH)
        - No recent Daily CHoCH
        - Wait for clear direction
        """
        scenarios = []
        
        scenarios.append({
            'name': 'Ranging Market - Wait for Direction',
            'probability': 70,
            'description': 'No clear Daily trend or CHoCH - market ranging or consolidating',
            'action': 'WAIT for clear Daily CHoCH (reversal) or clear HH+HL/LL+LH structure (continuity)',
            'targets': [],
            'invalidation': None,
            'confirmations_needed': ['daily_choch_or_clear_structure'],
            'timeframe': 'Daily',
            'expected_timing': 'Unknown',
            'strategy_type': 'RANGING'
        })
        
        scenarios.append({
            'name': 'Range Trading (Advanced)',
            'probability': 30,
            'description': 'Trade range boundaries if clear support/resistance',
            'action': 'Advanced strategy - trade bounces at range extremes with tight stops',
            'targets': [],
            'invalidation': None,
            'confirmations_needed': ['clear_range_boundaries', '4h_confirmation'],
            'timeframe': '4H',
            'expected_timing': 'Short-term',
            'strategy_type': 'RANGING'
        })
        
        return scenarios
    
    def _make_recommendation(
        self,
        present_state: Dict,
        future_scenarios: List[Dict],
        levels: List[SpatialLevel],
        events: List[TemporalEvent]
    ) -> str:
        """
        Face recomandarea finală
        """
        if not future_scenarios:
            return 'avoid'
        
        best_scenario = future_scenarios[0]
        
        # Check dacă toate confirmările sunt prezente
        if 'confirmations_needed' in best_scenario:
            confirmations = best_scenario['confirmations_needed']
            
            if not confirmations:
                # No confirmations needed = READY
                return 'ready_to_trade'
            
            # Check how many confirmations we have
            confirmations_present = self._check_confirmations(
                confirmations, 
                present_state, 
                levels, 
                events
            )
            
            if confirmations_present == len(confirmations):
                return 'ready_to_trade'
            elif confirmations_present >= len(confirmations) * 0.5:
                return 'monitor_closely'
            else:
                return 'wait_for_confirmation'
        
        return 'monitor_closely'
    
    def print_narrative(self, narrative: MarketNarrative):
        """
        Printează narrativul într-un format human-readable
        """
        logger.info(f"\n" + "="*80)
        logger.info(f"📖 MARKET NARRATIVE - {narrative.symbol}")
        logger.info(f"="*80)
        
        logger.info(f"\n💰 CURRENT PRICE: ${narrative.current_price:.5f}")
        
        # PAST
        logger.info(f"\n📚 PAST EVENTS (What happened):")
        for event in narrative.past_events[-5:]:
            logger.info(f"   [{event.timeframe.upper()}] {event.event_type.upper()} {event.direction} @ ${event.price:.5f} ({event.bars_ago} bars ago)")
        
        # PRESENT
        logger.info(f"\n📍 PRESENT STATE (Where we are):")
        logger.info(f"   Structure: {narrative.current_state}")
        logger.info(f"   Position: {narrative.price_position}")
        logger.info(f"   Momentum: {narrative.momentum}")
        
        logger.info(f"\n🔑 KEY LEVELS:")
        for level in narrative.key_levels[:5]:
            logger.info(f"   [{level.timeframe.upper()}] {level.level_type.upper()} {level.direction} @ ${level.price_bottom:.5f}-${level.price_top:.5f} (strength: {level.strength})")
        
        # FUTURE
        logger.info(f"\n🔮 FUTURE SCENARIOS:")
        for i, scenario in enumerate(narrative.expected_scenarios, 1):
            logger.info(f"\n   Scenario {i}: {scenario['name']} ({scenario['probability']}%)")
            logger.info(f"      {scenario['description']}")
            logger.info(f"      Action: {scenario['action']}")
            
            if scenario.get('confirmations_needed'):
                logger.info(f"      Waiting for:")
                for conf in scenario['confirmations_needed']:
                    logger.info(f"         - {conf}")
        
        # RECOMMENDATION
        logger.info(f"\n✅ RECOMMENDATION: {narrative.recommendation.upper()}")
        
        if narrative.waiting_for:
            logger.info(f"\n⏳ WAITING FOR:")
            for item in narrative.waiting_for:
                logger.info(f"   - {item}")
        
        if narrative.invalidation_levels:
            logger.info(f"\n❌ INVALIDATION LEVELS:")
            for level in narrative.invalidation_levels:
                logger.info(f"   - ${level:.5f}")
        
        logger.info(f"\n📊 META:")
        logger.info(f"   Confidence: {narrative.confidence}%")
        logger.info(f"   Complexity: {narrative.complexity}")
        
        logger.info(f"\n" + "="*80 + "\n")
    
    def _get_data(self, timeframe: str, bars: int) -> pd.DataFrame:
        """Get MT5 data"""
        tf_map = {'D1': mt5.TIMEFRAME_D1, 'H4': mt5.TIMEFRAME_H4, 'H1': mt5.TIMEFRAME_H1}
        rates = mt5.copy_rates_from_pos(self.symbol, tf_map[timeframe], 0, bars)
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    
    # Helper methods (simplified - expand based on smc_detector.py logic)
    def _find_order_blocks(self, df: pd.DataFrame, tf: str, max_age: int = 50) -> List[SpatialLevel]:
        """Find Order Block levels"""
        # Implementation using smc_detector logic
        return []
    
    def _find_fvg_levels(self, df: pd.DataFrame, tf: str, max_age: int = 50) -> List[SpatialLevel]:
        """Find FVG levels"""
        # Implementation using smc_detector logic
        return []
    
    def _find_swing_levels(self, df: pd.DataFrame, tf: str) -> List[SpatialLevel]:
        """Find swing high/low levels"""
        return []
    
    def _find_choch_events(self, df: pd.DataFrame, tf: str, max_lookback: int = 30) -> List[TemporalEvent]:
        """
        Find CHoCH (Change of Character) events - STRICT VERSION
        CHoCH = When CLOSE breaks structure AND confirms REVERSAL
        
        IMPORTANT: Use CLOSE prices only! Wicks = manipulation
        - BULLISH CHoCH: CLOSE breaks above recent swing high + OVERALL trend was BEARISH
        - BEARISH CHoCH: CLOSE breaks below recent swing low + OVERALL trend was BULLISH
        
        NOT CHoCH if just a pullback in existing trend!
        """
        events = []
        
        closes = df['close'].values
        times = df['time'].values
        
        if len(closes) < 20:
            return events
        
        # First, determine OVERALL trend (last 20-30 candles)
        trend_window = min(30, len(closes))
        trend_closes = closes[-trend_window:]
        
        # Count swing highs and swing lows to determine trend
        swing_highs = []
        swing_lows = []
        
        for j in range(2, len(trend_closes) - 2):
            # Swing high: higher than 2 candles before and after
            if (trend_closes[j] > trend_closes[j-1] and trend_closes[j] > trend_closes[j-2] and
                trend_closes[j] > trend_closes[j+1] and trend_closes[j] > trend_closes[j+2]):
                swing_highs.append(trend_closes[j])
            
            # Swing low: lower than 2 candles before and after
            if (trend_closes[j] < trend_closes[j-1] and trend_closes[j] < trend_closes[j-2] and
                trend_closes[j] < trend_closes[j+1] and trend_closes[j] < trend_closes[j+2]):
                swing_lows.append(trend_closes[j])
        
        # Determine trend based on swing structure
        overall_trend = 'ranging'
        
        if len(swing_highs) >= 3:
            # Check if Lower Highs (bearish) or Higher Highs (bullish)
            lh_count = sum(1 for k in range(1, len(swing_highs)) if swing_highs[k] < swing_highs[k-1])
            hh_count = sum(1 for k in range(1, len(swing_highs)) if swing_highs[k] > swing_highs[k-1])
            
            if lh_count >= len(swing_highs) - 1:  # All or most are LH
                overall_trend = 'bearish'
            elif hh_count >= len(swing_highs) - 1:  # All or most are HH
                overall_trend = 'bullish'
        
        if len(swing_lows) >= 3:
            # Check if Lower Lows (bearish) or Higher Lows (bullish)
            ll_count = sum(1 for k in range(1, len(swing_lows)) if swing_lows[k] < swing_lows[k-1])
            hl_count = sum(1 for k in range(1, len(swing_lows)) if swing_lows[k] > swing_lows[k-1])
            
            if ll_count >= len(swing_lows) - 1 and overall_trend != 'bullish':
                overall_trend = 'bearish'
            elif hl_count >= len(swing_lows) - 1 and overall_trend != 'bearish':
                overall_trend = 'bullish'
        
        # Now look for CHoCH that REVERSES this trend
        lookback = min(max_lookback, len(df) - 10)
        
        for i in range(len(df) - lookback, len(df) - 1):
            current_close = closes[i]
            
            # Get previous candles
            lookback_window = 15
            prev_closes = closes[max(0, i-lookback_window):i]
            
            if len(prev_closes) < 8:
                continue
            
            recent_swing_high = max(prev_closes[-10:])
            recent_swing_low = min(prev_closes[-10:])
            
            # BULLISH CHoCH: Only if overall trend was BEARISH and we break structure UP
            if current_close > recent_swing_high and overall_trend == 'bearish':
                # Additional confirmation: check if this is significant break (not just noise)
                break_strength = (current_close - recent_swing_high) / recent_swing_high * 100
                
                if break_strength > 0.1:  # At least 0.1% break
                    bars_ago = len(df) - 1 - i
                    
                    events.append(TemporalEvent(
                        event_type='choch',
                        timeframe=tf,
                        timestamp=pd.to_datetime(times[i]),
                        price=current_close,
                        direction='bullish',
                        significance=85,
                        confirmed=True,
                        bars_ago=bars_ago
                    ))
                    
                    logger.info(f"      ✅ BULLISH CHoCH at bar -{bars_ago} (CLOSE: {current_close:.5f} broke bearish structure at {recent_swing_high:.5f})")
            
            # BEARISH CHoCH: Only if overall trend was BULLISH and we break structure DOWN
            elif current_close < recent_swing_low and overall_trend == 'bullish':
                # Additional confirmation: check if this is significant break
                break_strength = (recent_swing_low - current_close) / recent_swing_low * 100
                
                if break_strength > 0.1:  # At least 0.1% break
                    bars_ago = len(df) - 1 - i
                    
                    events.append(TemporalEvent(
                        event_type='choch',
                        timeframe=tf,
                        timestamp=pd.to_datetime(times[i]),
                        price=current_close,
                        direction='bearish',
                        significance=85,
                        confirmed=True,
                        bars_ago=bars_ago
                    ))
                    
                    logger.info(f"      ✅ BEARISH CHoCH at bar -{bars_ago} (CLOSE: {current_close:.5f} broke bullish structure at {recent_swing_low:.5f})")
        
        return events
    
    def _find_bos_events(self, df: pd.DataFrame, tf: str) -> List[TemporalEvent]:
        """Find BOS events"""
        return []
    
    def _find_rejection_events(self, df: pd.DataFrame, tf: str, max_lookback: int = 50) -> List[TemporalEvent]:
        """Find rejection candle events"""
        return []
    
    def _find_liquidity_sweeps(self, df: pd.DataFrame, tf: str) -> List[TemporalEvent]:
        """Find liquidity sweep events"""
        return []
    
    def _determine_structure(self, df: pd.DataFrame, tf: str) -> str:
        """Determine market structure"""
        return 'bullish_structure'
    
    def _calculate_price_position(self, price: float, df: pd.DataFrame) -> str:
        """Calculate premium/discount position"""
        return 'discount'
    
    def _calculate_momentum(self, df_daily: pd.DataFrame, df_4h: pd.DataFrame, df_1h: pd.DataFrame) -> str:
        """Calculate momentum"""
        return 'neutral'
    
    def _find_closest_levels(self, price: float, levels: List[SpatialLevel]) -> Dict:
        """Find closest support/resistance"""
        return {'support': None, 'resistance': None, 'at_level': False}
    
    def _calculate_scenario_probability(self, scenario_type: str, present: Dict, fvg: Optional[SpatialLevel], choch: Optional[TemporalEvent]) -> int:
        """Calculate probability for scenario"""
        base_prob = 60
        
        if scenario_type == 'optimal_retest':
            # REVERSAL scenario - higher if CHoCH recent and strong
            if choch and choch.bars_ago <= 5:
                base_prob += 10
            if fvg and fvg.strength >= 70:
                base_prob += 10
            if present.get('momentum', '').startswith('strong'):
                base_prob += 5
        
        elif scenario_type == 'continuity_pullback':
            # CONTINUITY scenario - higher if clear trend structure
            if fvg and fvg.strength >= 60:
                base_prob += 10
            if present.get('price_position') in ['discount', 'equilibrium', 'premium']:
                base_prob += 5
        
        return min(85, max(40, base_prob))
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR"""
        return df['close'].std()
    
    def _find_next_resistance(self, price: float, levels: List[SpatialLevel]) -> float:
        """Find next resistance level"""
        resistance_levels = [
            l.price_top for l in levels 
            if l.price_top > price and l.level_type in ['order_block', 'swing_high', 'fvg']
        ]
        return min(resistance_levels) if resistance_levels else price * 1.02
    
    def _find_next_support(self, price: float, levels: List[SpatialLevel]) -> float:
        """Find next support level"""
        support_levels = [
            l.price_bottom for l in levels 
            if l.price_bottom < price and l.level_type in ['order_block', 'swing_low', 'fvg']
        ]
        return max(support_levels) if support_levels else price * 0.98
    
    def _estimate_timing(self, current_price: float, target_price: float, df_4h: pd.DataFrame) -> str:
        """Estimate when price might reach target"""
        return "2-5 candles (8-20 hours)"
    
    def _identify_waiting_confirmations(self, present: Dict, scenarios: List[Dict]) -> List[str]:
        """Identify what confirmations we're waiting for"""
        if not scenarios:
            return []
        
        best_scenario = scenarios[0]
        return best_scenario.get('confirmations_needed', [])
    
    def _identify_invalidation_levels(self, levels: List[SpatialLevel], events: List[TemporalEvent]) -> List[float]:
        """Identify invalidation price levels"""
        return []
    
    def _calculate_narrative_confidence(self, present: Dict, scenarios: List[Dict]) -> int:
        """Calculate confidence în narrativ"""
        if not scenarios:
            return 30
        
        best_prob = scenarios[0].get('probability', 50)
        return min(100, best_prob + 10)
    
    def _assess_complexity(self, levels: List[SpatialLevel], events: List[TemporalEvent]) -> str:
        """Assess complexity of market situation"""
        if len(levels) < 5 and len(events) < 5:
            return 'simple'
        elif len(levels) < 10 and len(events) < 10:
            return 'moderate'
        else:
            return 'complex'
    
    def _check_confirmations(
        self,
        needed: List[str],
        present: Dict,
        levels: List[SpatialLevel],
        events: List[TemporalEvent]
    ) -> int:
        """Check how many confirmations are present"""
        count = 0
        
        for confirmation in needed:
            if confirmation == 'price_at_fvg_bottom':
                # Check if price is at FVG bottom
                # ... logic
                pass
            elif confirmation == '4h_rejection_candle':
                # Check for recent 4H rejection
                # ... logic
                pass
            elif confirmation == '4h_choch_bullish':
                # Check for 4H CHoCH
                recent_4h_choch = next(
                    (e for e in reversed(events) if e.event_type == 'choch' and e.timeframe == '4h' and e.direction == 'bullish'),
                    None
                )
                if recent_4h_choch and recent_4h_choch.bars_ago < 10:
                    count += 1
        
        return count


def main():
    """
    Test analyzer pe NZDUSD (exemplul tău)
    """
    if not mt5.initialize():
        logger.error("MT5 initialization failed")
        return
    
    try:
        # Analyze NZDUSD
        analyzer = SpatioTemporalAnalyzer("NZDUSD")
        narrative = analyzer.analyze_market()
        
        # Print narrative
        analyzer.print_narrative(narrative)
        
        # Test pe alte perechi
        for symbol in ["GBPUSD", "BTCUSD", "XAUUSD"]:
            logger.info(f"\n{'='*80}")
            analyzer = SpatioTemporalAnalyzer(symbol)
            narrative = analyzer.analyze_market()
            analyzer.print_narrative(narrative)
            
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
