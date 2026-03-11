#!/usr/bin/env python3
"""
🎯 MULTI-TIMEFRAME EXECUTION RADAR - V8.3 SNIPER EDITION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Double Entry Logic: Scans both 1H and 4H for CHoCH confirmation.

CRITICAL UPGRADE:
- ✅ Scans 1H timeframe (relaxed ATR: 0.8x for precision moves)
- ✅ Scans 4H timeframe (standard ATR: 1.2x for higher confidence)
- ✅ Detects CHoCH on both timeframes
- ✅ Extracts FVG left by CHoCH (entry zone)
- ✅ Calculates distance to pullback zone
- ✅ Shows BOTH confirmations in console

STATUS SYSTEM:
- ⏳ WAITING_DAILY_FVG: Price not in Daily FVG yet
- 👀 WAITING_1H_CHOCH: In Daily FVG, scanning 1H
- 👀 WAITING_4H_CHOCH: In Daily FVG, scanning 4H
- ⏳ WAITING_1H_PULLBACK: 1H CHoCH detected, waiting for pullback
- ⏳ WAITING_4H_PULLBACK: 4H CHoCH detected, waiting for pullback
- 🔥 EXECUTE_NOW_1H: Price in 1H FVG - SNIPER ENTRY!
- 🔥 EXECUTE_NOW_4H: Price in 4H FVG - HIGH CONFIDENCE ENTRY!

Usage:
    python3 multi_tf_radar.py
    python3 multi_tf_radar.py --symbol EURJPY
    python3 multi_tf_radar.py --watch --interval 30
"""

import json
import sys
import time
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger

try:
    from ctrader_cbot_client import CTraderCBotClient
    from smc_detector import SMCDetector
    import pandas as pd
    DEPS_AVAILABLE = True
except ImportError:
    DEPS_AVAILABLE = False
    print("⚠️  Dependencies not available")
    sys.exit(1)


class PullbackStatus(Enum):
    """Execution status for multi-timeframe analysis"""
    WAITING_DAILY_FVG = "⏳ WAITING_DAILY_FVG"
    WAITING_1H_CHOCH = "👀 WAITING_1H_CHOCH"
    WAITING_4H_CHOCH = "👀 WAITING_4H_CHOCH"
    WAITING_1H_PULLBACK = "⏳ WAITING_1H_PULLBACK"
    WAITING_4H_PULLBACK = "⏳ WAITING_4H_PULLBACK"
    EXECUTE_NOW_1H = "🔥 EXECUTE_NOW_1H"
    EXECUTE_NOW_4H = "🔥 EXECUTE_NOW_4H"


@dataclass
class TimeframeAnalysis:
    """Analysis result for a specific timeframe"""
    timeframe: str  # "1H" or "4H"
    choch_detected: bool
    choch_direction: Optional[str]
    choch_time: Optional[str]
    choch_price: Optional[float]
    fvg_detected: bool
    fvg_top: Optional[float]
    fvg_bottom: Optional[float]
    fvg_entry: Optional[float]
    in_fvg: bool
    distance_to_fvg_pips: float
    status: PullbackStatus


@dataclass
class MultiTFResult:
    """Complete multi-timeframe analysis result"""
    symbol: str
    direction: str
    
    # Daily validation
    daily_zone_validated: bool
    daily_fvg_top: float
    daily_fvg_bottom: float
    daily_entry: float
    
    # Current price
    current_price: float
    
    # 1H analysis
    tf_1h: TimeframeAnalysis
    
    # 4H analysis
    tf_4h: TimeframeAnalysis
    
    # Final verdict
    execution_ready: bool
    verdict: str
    priority_timeframe: Optional[str]  # "1H" or "4H"


class MultiTFRadar:
    """Multi-timeframe execution radar with 1H + 4H scanning"""
    
    def __init__(self):
        if not DEPS_AVAILABLE:
            sys.exit(1)
        
        self.ctrader = CTraderCBotClient()
        if not self.ctrader.is_available():
            print("❌ cTrader cBot not running")
            sys.exit(1)
        
        print("✅ cTrader cBot connected")
        
        # Create SMC detectors with different ATR thresholds
        self.smc_1h = SMCDetector(
            swing_lookback=5,
            atr_multiplier=0.8  # Relaxed for 1H precision moves
        )
        
        self.smc_4h = SMCDetector(
            swing_lookback=5,
            atr_multiplier=1.2  # Standard for 4H higher confidence
        )
        
        print("🎯 SMC Detectors initialized:")
        print("   - 1H: ATR 0.8x (SNIPER mode)")
        print("   - 4H: ATR 1.2x (HIGH CONFIDENCE mode)")
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price from cTrader"""
        try:
            import requests
            response = requests.get(
                f"http://localhost:8767/price",
                params={"symbol": symbol},
                timeout=2
            )
            
            if response.status_code == 200:
                data = response.json()
                bid = data.get('bid', 0)
                ask = data.get('ask', 0)
                if bid > 0 and ask > 0:
                    return (bid + ask) / 2.0
            
            return None
        except Exception as e:
            print(f"⚠️  Error fetching price for {symbol}: {e}")
            return None
    
    def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        num_candles: int = 100
    ) -> Optional[pd.DataFrame]:
        """Download historical data"""
        try:
            df = self.ctrader.get_historical_data(symbol, timeframe, num_candles)
            if df is not None and not df.empty:
                return df.reset_index()
            return None
        except Exception as e:
            print(f"⚠️  Error downloading {timeframe} data for {symbol}: {e}")
            return None
    
    def analyze_timeframe(
        self,
        symbol: str,
        timeframe: str,
        required_direction: str,
        current_price: float,
        smc_detector: SMCDetector
    ) -> TimeframeAnalysis:
        """
        Analyze a specific timeframe for CHoCH and FVG
        
        Args:
            symbol: Trading pair
            timeframe: "H1" or "H4"
            required_direction: "bullish" or "bearish"
            current_price: Current market price
            smc_detector: SMC detector with appropriate ATR threshold
        
        Returns:
            TimeframeAnalysis with CHoCH and FVG details
        """
        timeframe_display = "1H" if timeframe == "H1" else "4H"
        
        # Download data
        df = self.get_historical_data(symbol, timeframe, 100)
        
        if df is None or df.empty:
            return TimeframeAnalysis(
                timeframe=timeframe_display,
                choch_detected=False,
                choch_direction=None,
                choch_time=None,
                choch_price=None,
                fvg_detected=False,
                fvg_top=None,
                fvg_bottom=None,
                fvg_entry=None,
                in_fvg=False,
                distance_to_fvg_pips=0.0,
                status=PullbackStatus.WAITING_1H_CHOCH if timeframe == "H1" else PullbackStatus.WAITING_4H_CHOCH
            )
        
        try:
            # Detect CHoCH and BOS
            choch_list, bos_list = smc_detector.detect_choch_and_bos(df)
            
            if not choch_list:
                return TimeframeAnalysis(
                    timeframe=timeframe_display,
                    choch_detected=False,
                    choch_direction=None,
                    choch_time=None,
                    choch_price=None,
                    fvg_detected=False,
                    fvg_top=None,
                    fvg_bottom=None,
                    fvg_entry=None,
                    in_fvg=False,
                    distance_to_fvg_pips=0.0,
                    status=PullbackStatus.WAITING_1H_CHOCH if timeframe == "H1" else PullbackStatus.WAITING_4H_CHOCH
                )
            
            # Get latest CHoCH
            latest_choch = choch_list[-1]
            choch_direction = latest_choch.direction
            choch_index = latest_choch.index
            
            # Get CHoCH details
            if choch_index < len(df):
                choch_time = df.iloc[choch_index]['time']
                choch_time_str = choch_time.isoformat() if hasattr(choch_time, 'isoformat') else str(choch_time)
                choch_price = df.iloc[choch_index]['close']
            else:
                choch_time_str = "Unknown"
                choch_price = None
            
            # V6.1 DIRECTION ALIGNMENT: Daily Direction == LTF CHoCH Direction
            # If Daily is SELL and 1H gives CHoCH Buy, REJECT the signal
            if choch_direction != required_direction:
                print(f"⚠️  WAITING FOR {required_direction.upper()} ALIGNMENT ON {timeframe_display}")
                print(f"   Daily Direction: {required_direction.upper()}")
                print(f"   {timeframe_display} CHoCH: {choch_direction.upper()}")
                print(f"   🔒 Signal REJECTED - Not aligned with Daily bias")
                
                return TimeframeAnalysis(
                    timeframe=timeframe_display,
                    choch_detected=False,  # Mark as not detected since it's counter-trend
                    choch_direction=choch_direction,
                    choch_time=choch_time_str,
                    choch_price=choch_price,
                    fvg_detected=False,
                    fvg_top=None,
                    fvg_bottom=None,
                    fvg_entry=None,
                    in_fvg=False,
                    distance_to_fvg_pips=0.0,
                    status=PullbackStatus.WAITING_1H_CHOCH if timeframe == "H1" else PullbackStatus.WAITING_4H_CHOCH
                )
            
            # Detect FVG created by CHoCH
            fvg_list = smc_detector.detect_fvg(
                df,
                choch=latest_choch,
                current_price=current_price
            )
            
            if not fvg_list:
                # CHoCH detected but no FVG yet
                return TimeframeAnalysis(
                    timeframe=timeframe_display,
                    choch_detected=True,
                    choch_direction=choch_direction,
                    choch_time=choch_time_str,
                    choch_price=choch_price,
                    fvg_detected=False,
                    fvg_top=None,
                    fvg_bottom=None,
                    fvg_entry=None,
                    in_fvg=False,
                    distance_to_fvg_pips=0.0,
                    status=PullbackStatus.WAITING_1H_PULLBACK if timeframe == "H1" else PullbackStatus.WAITING_4H_PULLBACK
                )
            
            # Get latest FVG
            latest_fvg = fvg_list[-1]
            fvg_top = latest_fvg.top
            fvg_bottom = latest_fvg.bottom
            fvg_entry = (fvg_top + fvg_bottom) / 2.0
            
            # Check if price in FVG
            in_fvg = fvg_bottom <= current_price <= fvg_top
            
            # 🚫 V6.1 BLACKOUT HOUR FILTER: Block signals during high-risk hours
            # Hour 10:00 UTC has <10% win rate - block all EXECUTE_NOW signals
            current_hour_utc = datetime.utcnow().hour
            
            # Calculate distance to FVG
            if in_fvg:
                distance_to_fvg_pips = 0.0
                
                # Check if in blackout hour
                if current_hour_utc == 10:
                    # BLOCK execution during 10:00 UTC
                    print(f"🚫 BLACKOUT HOUR (10:00 UTC): Signal BLOCKED (Win Rate <10%)")
                    print(f"   Current Hour: {current_hour_utc}:00 UTC")
                    print(f"   Action: Waiting for next hour to execute")
                    status = PullbackStatus.WAITING_1H_PULLBACK if timeframe == "H1" else PullbackStatus.WAITING_4H_PULLBACK
                else:
                    # Safe hour - allow execution
                    status = PullbackStatus.EXECUTE_NOW_1H if timeframe == "H1" else PullbackStatus.EXECUTE_NOW_4H
            else:
                if required_direction == 'bullish':
                    # For LONG: need to pull back DOWN to FVG
                    distance_to_fvg_pips = abs(current_price - fvg_top) * 10000
                else:
                    # For SHORT: need to pull back UP to FVG
                    distance_to_fvg_pips = abs(fvg_bottom - current_price) * 10000
                
                status = PullbackStatus.WAITING_1H_PULLBACK if timeframe == "H1" else PullbackStatus.WAITING_4H_PULLBACK
            
            return TimeframeAnalysis(
                timeframe=timeframe_display,
                choch_detected=True,
                choch_direction=choch_direction,
                choch_time=choch_time_str,
                choch_price=choch_price,
                fvg_detected=True,
                fvg_top=fvg_top,
                fvg_bottom=fvg_bottom,
                fvg_entry=fvg_entry,
                in_fvg=in_fvg,
                distance_to_fvg_pips=distance_to_fvg_pips,
                status=status
            )
        
        except Exception as e:
            print(f"⚠️  Error analyzing {timeframe} for {symbol}: {e}")
            return TimeframeAnalysis(
                timeframe=timeframe_display,
                choch_detected=False,
                choch_direction=None,
                choch_time=None,
                choch_price=None,
                fvg_detected=False,
                fvg_top=None,
                fvg_bottom=None,
                fvg_entry=None,
                in_fvg=False,
                distance_to_fvg_pips=0.0,
                status=PullbackStatus.WAITING_1H_CHOCH if timeframe == "H1" else PullbackStatus.WAITING_4H_CHOCH
            )
    
    def analyze_setup(self, setup_data: Dict, save_to_json: bool = True) -> MultiTFResult:
        """
        Complete multi-timeframe analysis of a setup
        
        Scans both 1H and 4H for CHoCH and FVG
        
        Args:
            setup_data: Setup dict from monitoring_setups.json
            save_to_json: If True, write radar results back to monitoring_setups.json
        """
        symbol = setup_data.get('symbol', 'UNKNOWN')
        direction = setup_data.get('direction', 'SHORT').upper()
        
        # Normalize direction
        if direction == 'BUY':
            direction = 'LONG'
        elif direction == 'SELL':
            direction = 'SHORT'
        
        # Get Daily data
        daily_entry = float(setup_data.get('entry_price', 0))
        daily_fvg_top = float(setup_data.get('fvg_top', daily_entry))
        daily_fvg_bottom = float(setup_data.get('fvg_bottom', daily_entry))
        
        # Get current price
        current_price = self.get_current_price(symbol)
        if current_price is None:
            current_price = daily_entry
        
        # Validate Daily zone
        daily_zone_validated = daily_fvg_bottom <= current_price <= daily_fvg_top
        
        if not daily_zone_validated:
            # Price not in Daily FVG - skip multi-TF analysis
            return MultiTFResult(
                symbol=symbol,
                direction=direction,
                daily_zone_validated=False,
                daily_fvg_top=daily_fvg_top,
                daily_fvg_bottom=daily_fvg_bottom,
                daily_entry=daily_entry,
                current_price=current_price,
                tf_1h=TimeframeAnalysis(
                    timeframe="1H",
                    choch_detected=False,
                    choch_direction=None,
                    choch_time=None,
                    choch_price=None,
                    fvg_detected=False,
                    fvg_top=None,
                    fvg_bottom=None,
                    fvg_entry=None,
                    in_fvg=False,
                    distance_to_fvg_pips=0.0,
                    status=PullbackStatus.WAITING_DAILY_FVG
                ),
                tf_4h=TimeframeAnalysis(
                    timeframe="4H",
                    choch_detected=False,
                    choch_direction=None,
                    choch_time=None,
                    choch_price=None,
                    fvg_detected=False,
                    fvg_top=None,
                    fvg_bottom=None,
                    fvg_entry=None,
                    in_fvg=False,
                    distance_to_fvg_pips=0.0,
                    status=PullbackStatus.WAITING_DAILY_FVG
                ),
                execution_ready=False,
                verdict="⏳ WAITING FOR DAILY FVG ENTRY",
                priority_timeframe=None
            )
        
        # Price in Daily FVG - analyze both timeframes
        required_direction = 'bullish' if direction == 'LONG' else 'bearish'
        
        print(f"\n{'='*80}")
        print(f"🔍 Analyzing {symbol} - {direction}")
        print(f"{'='*80}")
        print(f"💰 Current Price: {current_price:.5f}")
        print(f"📊 Daily FVG: [{daily_fvg_bottom:.5f} - {daily_fvg_top:.5f}]")
        print(f"✅ Price IN Daily FVG - Scanning 1H + 4H...\n")
        
        # Analyze 1H
        print("🔎 [1H] SNIPER SCAN (ATR 0.8x)...")
        tf_1h = self.analyze_timeframe(
            symbol=symbol,
            timeframe="H1",
            required_direction=required_direction,
            current_price=current_price,
            smc_detector=self.smc_1h
        )
        
        # Analyze 4H
        print("\n🔎 [4H] HIGH CONFIDENCE SCAN (ATR 1.2x)...")
        tf_4h = self.analyze_timeframe(
            symbol=symbol,
            timeframe="H4",
            required_direction=required_direction,
            current_price=current_price,
            smc_detector=self.smc_4h
        )
        
        # Determine execution readiness and priority
        execution_ready = False
        priority_timeframe = None
        verdict = "👀 MONITORING BOTH TIMEFRAMES"
        
        if tf_1h.status == PullbackStatus.EXECUTE_NOW_1H:
            execution_ready = True
            priority_timeframe = "1H"
            verdict = "🔥 EXECUTE NOW (1H SNIPER ENTRY!)"
        elif tf_4h.status == PullbackStatus.EXECUTE_NOW_4H:
            execution_ready = True
            priority_timeframe = "4H"
            verdict = "🔥 EXECUTE NOW (4H HIGH CONFIDENCE!)"
        elif tf_1h.choch_detected and tf_1h.fvg_detected:
            verdict = f"⏳ WAITING FOR 1H PULLBACK ({tf_1h.distance_to_fvg_pips:.1f} pips away)"
        elif tf_4h.choch_detected and tf_4h.fvg_detected:
            verdict = f"⏳ WAITING FOR 4H PULLBACK ({tf_4h.distance_to_fvg_pips:.1f} pips away)"
        elif tf_1h.choch_detected or tf_4h.choch_detected:
            verdict = "👀 CHoCH DETECTED - Waiting for FVG formation"
        else:
            verdict = "👀 WAITING FOR 1H/4H CHoCH"
        
        result = MultiTFResult(
            symbol=symbol,
            direction=direction,
            daily_zone_validated=daily_zone_validated,
            daily_fvg_top=daily_fvg_top,
            daily_fvg_bottom=daily_fvg_bottom,
            daily_entry=daily_entry,
            current_price=current_price,
            tf_1h=tf_1h,
            tf_4h=tf_4h,
            execution_ready=execution_ready,
            verdict=verdict,
            priority_timeframe=priority_timeframe
        )
        
        # 🔥 V8.3 SYNC: Write radar results to monitoring_setups.json
        if save_to_json:
            self._sync_to_monitoring_setups(setup_data, result)
        
        return result
    
    def _sync_to_monitoring_setups(self, original_setup: Dict, result: MultiTFResult):
        """
        🔥 CRITICAL: Write radar analysis back to monitoring_setups.json
        
        This enables setup_executor_monitor.py to use 1H/4H FVG zones
        instead of just Fibonacci 50%.
        """
        try:
            # Load monitoring_setups.json
            with open('monitoring_setups.json', 'r') as f:
                data = json.load(f)
            
            if isinstance(data, dict):
                setups = data.get("setups", [])
            elif isinstance(data, list):
                setups = data
            else:
                return
            
            # Find matching setup
            setup_key = f"{result.symbol}_{result.direction}_{result.daily_entry}"
            logger.debug(f"🔍 Looking for setup: {result.symbol} {result.direction}")
            
            for i, setup in enumerate(setups):
                logger.debug(f"  Checking setup {i}: {setup.get('symbol')} {setup.get('direction')}")
                
                # Match direction: sell↔SHORT, buy↔LONG
                setup_direction = setup.get('direction', '').upper()
                matches_sell = (result.direction == 'SHORT' and setup_direction == 'SELL')
                matches_buy = (result.direction == 'LONG' and setup_direction == 'BUY')
                
                if setup.get('symbol') == result.symbol and (matches_sell or matches_buy):
                    
                    # 🎯 1H RADAR DATA
                    if result.tf_1h.choch_detected:
                        setup['radar_1h_choch_detected'] = True
                        setup['radar_1h_choch_direction'] = result.tf_1h.choch_direction
                        setup['radar_1h_choch_time'] = result.tf_1h.choch_time
                        setup['radar_1h_choch_price'] = result.tf_1h.choch_price
                    else:
                        setup['radar_1h_choch_detected'] = False
                    
                    if result.tf_1h.fvg_detected:
                        setup['radar_1h_fvg_top'] = result.tf_1h.fvg_top
                        setup['radar_1h_fvg_bottom'] = result.tf_1h.fvg_bottom
                        setup['radar_1h_fvg_entry'] = result.tf_1h.fvg_entry
                        setup['radar_1h_in_fvg'] = result.tf_1h.in_fvg
                        setup['radar_1h_distance_pips'] = result.tf_1h.distance_to_fvg_pips
                    else:
                        setup['radar_1h_fvg_top'] = None
                        setup['radar_1h_fvg_bottom'] = None
                        setup['radar_1h_fvg_entry'] = None
                    
                    setup['radar_1h_status'] = result.tf_1h.status.value
                    
                    # 💎 4H RADAR DATA
                    if result.tf_4h.choch_detected:
                        setup['radar_4h_choch_detected'] = True
                        setup['radar_4h_choch_direction'] = result.tf_4h.choch_direction
                        setup['radar_4h_choch_time'] = result.tf_4h.choch_time
                        setup['radar_4h_choch_price'] = result.tf_4h.choch_price
                    else:
                        setup['radar_4h_choch_detected'] = False
                    
                    if result.tf_4h.fvg_detected:
                        setup['radar_4h_fvg_top'] = result.tf_4h.fvg_top
                        setup['radar_4h_fvg_bottom'] = result.tf_4h.fvg_bottom
                        setup['radar_4h_fvg_entry'] = result.tf_4h.fvg_entry
                        setup['radar_4h_in_fvg'] = result.tf_4h.in_fvg
                        setup['radar_4h_distance_pips'] = result.tf_4h.distance_to_fvg_pips
                    else:
                        setup['radar_4h_fvg_top'] = None
                        setup['radar_4h_fvg_bottom'] = None
                        setup['radar_4h_fvg_entry'] = None
                    
                    setup['radar_4h_status'] = result.tf_4h.status.value
                    
                    # 🏆 PRIORITY & EXECUTION STATUS
                    setup['radar_priority_timeframe'] = result.priority_timeframe
                    setup['radar_execution_ready'] = result.execution_ready
                    setup['radar_verdict'] = result.verdict
                    setup['radar_last_scan'] = datetime.now().isoformat()
                    
                    setups[i] = setup
                    logger.success(f"✅ Synced radar data to monitoring_setups.json for {result.symbol}")
                    break
            
            # Save updated data
            if isinstance(data, dict):
                data['setups'] = setups
                data['last_updated'] = datetime.now().isoformat()
            else:
                data = setups
            
            with open('monitoring_setups.json', 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"💾 monitoring_setups.json updated with radar data")
        
        except Exception as e:
            logger.error(f"⚠️  Failed to sync radar data to monitoring_setups.json: {e}")
    
    def print_result(self, result: MultiTFResult):
        """Print formatted multi-timeframe analysis result"""
        print("\n" + "="*80)
        print(f"🎯 MULTI-TIMEFRAME EXECUTION RADAR - {result.symbol}")
        print("="*80)
        print(f"⏰ Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Direction: {'🟢' if result.direction == 'LONG' else '🔴'} {result.direction}")
        print("="*80)
        
        # Daily zone
        print("\n📊 [DAILY] ZONE VALIDATION")
        print(f"   Status: {'✅ VALIDATED' if result.daily_zone_validated else '❌ NOT IN ZONE'}")
        print(f"   FVG Zone: [{result.daily_fvg_bottom:.5f} - {result.daily_fvg_top:.5f}]")
        print(f"   Entry: {result.daily_entry:.5f}")
        
        # Current price
        print("\n💰 [CURRENT PRICE]")
        print(f"   Price: {result.current_price:.5f}")
        
        if not result.daily_zone_validated:
            print("\n⏳ Price not in Daily FVG - Skipping multi-TF analysis")
            print("\n" + "="*80)
            print(f"🎯 [VERDICT]: {result.verdict}")
            print("="*80)
            return
        
        # 1H Analysis
        print("\n" + "─"*80)
        print("🎯 [1H] SNIPER ANALYSIS (ATR 0.8x)")
        print("─"*80)
        print(f"   Status: {result.tf_1h.status.value}")
        
        if result.tf_1h.choch_detected:
            print(f"   ✅ CHoCH: {result.tf_1h.choch_direction.upper()}")
            print(f"   📅 Time: {result.tf_1h.choch_time}")
            if result.tf_1h.choch_price:
                print(f"   💰 Price: {result.tf_1h.choch_price:.5f}")
        else:
            print(f"   ❌ No 1H CHoCH detected")
        
        if result.tf_1h.fvg_detected:
            print(f"\n   📦 1H FVG Entry Zone:")
            print(f"      Zone: [{result.tf_1h.fvg_bottom:.5f} - {result.tf_1h.fvg_top:.5f}]")
            print(f"      🎯 Entry: {result.tf_1h.fvg_entry:.5f}")
            
            if result.tf_1h.in_fvg:
                print(f"      ✅✅✅ PRICE IN 1H FVG - SNIPER ENTRY!")
            else:
                print(f"      ⏳ Distance: {result.tf_1h.distance_to_fvg_pips:.1f} pips")
        
        # 4H Analysis
        print("\n" + "─"*80)
        print("💎 [4H] HIGH CONFIDENCE ANALYSIS (ATR 1.2x)")
        print("─"*80)
        print(f"   Status: {result.tf_4h.status.value}")
        
        if result.tf_4h.choch_detected:
            print(f"   ✅ CHoCH: {result.tf_4h.choch_direction.upper()}")
            print(f"   📅 Time: {result.tf_4h.choch_time}")
            if result.tf_4h.choch_price:
                print(f"   💰 Price: {result.tf_4h.choch_price:.5f}")
        else:
            print(f"   ❌ No 4H CHoCH detected")
        
        if result.tf_4h.fvg_detected:
            print(f"\n   📦 4H FVG Entry Zone:")
            print(f"      Zone: [{result.tf_4h.fvg_bottom:.5f} - {result.tf_4h.fvg_top:.5f}]")
            print(f"      🎯 Entry: {result.tf_4h.fvg_entry:.5f}")
            
            if result.tf_4h.in_fvg:
                print(f"      ✅✅✅ PRICE IN 4H FVG - HIGH CONFIDENCE!")
            else:
                print(f"      ⏳ Distance: {result.tf_4h.distance_to_fvg_pips:.1f} pips")
        
        # Final verdict
        print("\n" + "="*80)
        print(f"🎯 [VERDICT]: {result.verdict}")
        if result.priority_timeframe:
            print(f"🏆 [PRIORITY]: {result.priority_timeframe} timeframe")
        print("="*80)
        
        if result.execution_ready:
            print("\n🚨🚨🚨 EXECUTE IMMEDIATELY 🚨🚨🚨")
            if result.priority_timeframe == "1H":
                print(f"   🎯 SNIPER ENTRY (1H):")
                print(f"      Entry: {result.tf_1h.fvg_entry:.5f}")
                print(f"      FVG Zone: [{result.tf_1h.fvg_bottom:.5f} - {result.tf_1h.fvg_top:.5f}]")
            else:
                print(f"   💎 HIGH CONFIDENCE ENTRY (4H):")
                print(f"      Entry: {result.tf_4h.fvg_entry:.5f}")
                print(f"      FVG Zone: [{result.tf_4h.fvg_bottom:.5f} - {result.tf_4h.fvg_top:.5f}]")
        
        print()
    
    def load_monitoring_setups(self) -> List[Dict]:
        """Load setups from monitoring_setups.json"""
        try:
            with open('monitoring_setups.json', 'r') as f:
                data = json.load(f)
                
                if isinstance(data, dict):
                    setups = data.get("setups", [])
                elif isinstance(data, list):
                    setups = data
                else:
                    return []
                
                return [s for s in setups if isinstance(s, dict) and s.get('status') == 'MONITORING']
        
        except FileNotFoundError:
            print("⚠️  monitoring_setups.json not found")
            return []
        except json.JSONDecodeError as e:
            print(f"⚠️  Error parsing monitoring_setups.json: {e}")
            return []
    
    def run_scan(self, symbol: Optional[str] = None, all_setups: bool = False):
        """Run multi-timeframe scan"""
        setups = self.load_monitoring_setups()
        
        if not setups:
            print("\n📭 No active setups in monitoring\n")
            return
        
        if symbol:
            # Scan specific symbol
            target_setups = [s for s in setups if s.get('symbol') == symbol]
            if not target_setups:
                print(f"\n⚠️  No setup found for {symbol}\n")
                return
            setups = target_setups
        elif not all_setups:
            # Scan first setup only
            setups = [setups[0]]
        
        # Run multi-TF analysis
        for setup in setups:
            try:
                result = self.analyze_setup(setup)
                self.print_result(result)
            except Exception as e:
                print(f"\n⚠️  Error analyzing {setup.get('symbol', 'UNKNOWN')}: {e}\n")
    
    def watch_mode(self, interval: int, symbol: Optional[str] = None, all_setups: bool = False):
        """Run scan in watch mode with auto-refresh"""
        print("\n" + "="*80)
        print("👁️  MULTI-TF RADAR - WATCH MODE ACTIVE")
        print("="*80)
        print(f"⏱️  Refresh Interval: {interval}s")
        print(f"🎯 Target: {'ALL setups' if all_setups else (symbol if symbol else 'First setup')}")
        print("Press Ctrl+C to stop")
        print("="*80 + "\n")
        
        try:
            while True:
                self.run_scan(symbol=symbol, all_setups=all_setups)
                
                print(f"\n⏳ Next scan in {interval}s...\n")
                time.sleep(interval)
        
        except KeyboardInterrupt:
            print("\n\n👋 Watch mode stopped by user\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='🎯 Multi-Timeframe Execution Radar - V8.3 SNIPER EDITION'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        help='Scan specific symbol (e.g., EURJPY)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Scan all setups in monitoring'
    )
    parser.add_argument(
        '--watch',
        action='store_true',
        help='Run in watch mode (auto-refresh)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Watch mode refresh interval in seconds (default: 30)'
    )
    
    args = parser.parse_args()
    
    radar = MultiTFRadar()
    
    if args.watch:
        radar.watch_mode(
            interval=args.interval,
            symbol=args.symbol,
            all_setups=args.all
        )
    else:
        radar.run_scan(symbol=args.symbol, all_setups=args.all)


if __name__ == '__main__':
    main()
