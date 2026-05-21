#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import io
# Fix UTF-8 encoding for Windows PowerShell console
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

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
import io
# Force UTF-8 output on Windows (fixes emoji display in PowerShell)
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer') and sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
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
    # V16.2: 50% Equilibrium al impulsului CHoCH (frontiera Discount/Premium)
    # LONG = Discount = sub EQ  |  SHORT = Premium = peste EQ
    equilibrium: Optional[float] = None
    # V19.4 FIX #3: scan_error propagation — previne suprascrierea FVG valid cu None
    scan_error: bool = False
    scan_error_msg: str = ""
    # V19.6 FIX #3: transparență sursă zonă — structural FVG vs. Fibo sintetic
    fvg_source: str = "structural"  # "structural" | "fibo_fallback"


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
            swing_lookback=8,   # V19: più context structural pe 4H (5→8)
            atr_multiplier=1.0  # V15.4: relaxed from 1.2→1.0 — avoid missing clear 4H CHoCH
        )
        
        print("🎯 SMC Detectors initialized:")
        print("   - 1H: ATR 0.8x (SNIPER mode)")
        print("   - 4H: ATR 1.0x (HIGH CONFIDENCE mode — V15.4)")
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price from cTrader"""
        try:
            import requests
            response = requests.get(
                f"http://localhost:8010/price",  # V19 FIX #5: port corect MarketDataProvider
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
        
        # V19 FIX #3: Extindere orizont vizual
        # 1H: 400 bare = ~16 zile → CHoCH < 10h acoperit
        # 4H: 300 bare = ~50 zile → CHoCH major Daily acoperit complet
        num_bars = 400 if timeframe == "H1" else 300
        
        # Download data
        df = self.get_historical_data(symbol, timeframe, num_bars)
        
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
            
            # V19.4 FIX #2: returnăm WAITING doar dacă AMBELE liste sunt goale.
            # Dacă există BOS valid în direcția biasului, cascade-ul trebuie să ruleze (PAS 2/4).
            if not choch_list and not bos_list:
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
            
            # ━━━ V19.2: STRUCTURAL ALIGNMENT — 4-STEP CASCADE, ZERO COUNTER-TREND REJECTION ━━━
            # REGULA ABSOLUTĂ: Dacă există CEL PUȚIN UN CHoCH sau BOS în direcția biasului Daily
            # în ORICE punct din seria de date → ALIGNED = VALIDATED.
            # Mișcările counter-trend (micro-pullback 4H/1H) = zgomot normal într-un pullback Daily.
            # NU invalidăm structura pe baza ultimului semnal de pe grafic.
            LOOKBACK_BARS = 100

            use_bos_as_choch = False
            bos_used = None

            # PAS 1: CHoCH aliniat în fereastra de 100 bare (prioritate maximă — semnal recent)
            # V19.4 FIX #1: sorted garantat după index cronologic — elimină selecție counter-trend rezidual
            aligned_chochs = sorted(
                [c for c in choch_list
                 if c.direction == required_direction
                 and c.index >= len(df) - LOOKBACK_BARS],
                key=lambda x: x.index
            )
            if aligned_chochs:
                bars_ago = len(df) - aligned_chochs[-1].index
                print(f"  ✅ [{timeframe_display} SCAN] {symbol} | CHoCH {required_direction.upper()} în fereastra 100 bare la -{bars_ago} bare | VALIDATED ✅")
                sys.stdout.flush()

            # PAS 2: BOS aliniat în fereastra de 100 bare
            if not aligned_chochs:
                # V19.4 FIX #1: sorted — cel mai recent BOS în fereastră la [-1]
                aligned_bos_window = sorted(
                    [b for b in bos_list
                     if b.direction == required_direction
                     and b.index >= len(df) - LOOKBACK_BARS],
                    key=lambda x: x.index
                )
                if aligned_bos_window:
                    use_bos_as_choch = True
                    bos_used = aligned_bos_window[-1]
                    bars_ago = len(df) - bos_used.index
                    print(f"  ✅ [{timeframe_display} SCAN] {symbol} | BOS {required_direction.upper()} în fereastra 100 bare la -{bars_ago} bare | VALIDATED ✅ (BOS confirmare)")
                    sys.stdout.flush()

            # PAS 3: FALLBACK FULL-DATASET CHoCH — ignorăm COMPLET orice counter-trend
            # Luăm cel mai recent CHoCH aliniat din TOATĂ seria, indiferent ce micro-pullback a urmat
            if not aligned_chochs and not use_bos_as_choch:
                # V19.4 FIX #1: sorted — [-1] va fi garantat cel mai RECENT CHoCH aliniat din toată seria
                all_aligned_chochs = sorted(
                    [c for c in choch_list if c.direction == required_direction],
                    key=lambda x: x.index
                )
                if all_aligned_chochs:
                    aligned_chochs = [all_aligned_chochs[-1]]  # cel mai recent aliniat — definitiv valid
                    bars_ago = len(df) - all_aligned_chochs[-1].index
                    print(f"  ✅ [{timeframe_display} SCAN] {symbol} | CHoCH {required_direction.upper()} full-dataset la -{bars_ago} bare | VALIDATED ✅ (counter-trend ignorat)")
                    sys.stdout.flush()

            # PAS 4: FALLBACK FULL-DATASET BOS
            if not aligned_chochs and not use_bos_as_choch:
                # V19.4 FIX #1: sorted — [-1] va fi garantat cel mai RECENT BOS din toată seria
                all_aligned_bos = sorted(
                    [b for b in bos_list if b.direction == required_direction],
                    key=lambda x: x.index
                )
                if all_aligned_bos:
                    use_bos_as_choch = True
                    bos_used = all_aligned_bos[-1]
                    bars_ago = len(df) - bos_used.index
                    print(f"  ✅ [{timeframe_display} SCAN] {symbol} | BOS {required_direction.upper()} full-dataset la -{bars_ago} bare | VALIDATED ✅")
                    sys.stdout.flush()

            # TRULY NOTHING — nicio structură aliniată în toți cei {len(df)} bari descărcați
            if not aligned_chochs and not use_bos_as_choch:
                print(f"  ⚠️  [{timeframe_display}] Nicio structură {required_direction.upper()} găsită în {len(df)} bare disponibile — WAITING")
                sys.stdout.flush()
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

            if use_bos_as_choch and bos_used is not None:
                # Construim un CHoCH sintetic din BOS pentru a putea extrage FVG
                from smc_detector import CHoCH as _CHoCH
                latest_choch = _CHoCH(
                    index=bos_used.index,
                    direction=bos_used.direction,
                    break_price=bos_used.break_price,
                    previous_trend=required_direction,
                    candle_time=bos_used.candle_time,
                    swing_broken=bos_used.swing_broken
                )
            else:
                latest_choch = aligned_chochs[-1]
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
            
            # V18.3: direction alignment este garantat — am filtrat deja pe required_direction
            # Blocul vechi de reject nu mai e necesar
            
            # ── V16.2: Calcul Equilibrium (50% EQ) din impulsul CHoCH ─────────
            # Utilizat în P/D Array validation în _check_radar_entry().
            # Stocat în setup ca radar_1h_eq / radar_4h_eq.
            choch_equilibrium = None
            try:
                _sbp = float(latest_choch.swing_broken.price)
                _cbp = float(latest_choch.break_price)
                choch_equilibrium = (_sbp + _cbp) / 2.0
                pip_size_eq = 0.01 if 'JPY' in symbol.upper() else 0.0001
                _eq_str = f"{choch_equilibrium:.5f}" if choch_equilibrium is not None else "N/A"
                print(f"  📐 [V16.2 EQ] {timeframe_display} Impulse: {_sbp:.5f} → {_cbp:.5f} | "
                      f"EQ={_eq_str} ({abs(_cbp - _sbp)/pip_size_eq:.1f} pips)")
                sys.stdout.flush()
            except Exception:
                pass

            # Detect FVG created by CHoCH
            # detect_fvg() returns a single FVG object or None (not a list)
            # V19.2 FIX 1: wrap in try/except — smc_detector.detect_fvg() poate crapa cu
            # ValueError/f-string crash intern. Prinsă eroarea → forțăm Fibo Fallback.
            latest_fvg = None
            try:
                latest_fvg = smc_detector.detect_fvg(
                    df,
                    choch=latest_choch,
                    current_price=current_price
                )
            except Exception as fvg_err:
                print(f"  ⚠️ [PATCH RADAR] detect_fvg structural crash caught: {fvg_err}")
                print(f"  ⚠️ [PATCH RADAR] Forcing V15.4 Fibo Fallback.")
                sys.stdout.flush()
                latest_fvg = None
            
            if not latest_fvg:
                # V15.4 FIBO FALLBACK: CHoCH detectat dar FVG nu există sau a fost consumat.
                # Calculăm zona Fibonacci 40-60% din impulsul CHoCH ca fallback entry zone sintetică.
                # Aceasta previne ratarea intrărilor clare (ex: USDCAD 4H CHoCH vizibil dar FVG absent)
                try:
                    # Găsim swing-ul rupt de CHoCH (swing_broken.price) și CHoCH break_price
                    swing_broken_price = float(latest_choch.swing_broken.price)
                    choch_break_price = float(latest_choch.break_price)
                    impulse_size = abs(choch_break_price - swing_broken_price)
                    # V19.4 FIX — Guard impuls 0 pips: date corupte sau tick duplicat din cBot.
                    # NU activăm Fibo Fallback pe impuls nul → returnăm WAITING curat.
                    if impulse_size <= 0:
                        pip_size_guard = 0.01 if 'JPY' in symbol.upper() else 0.0001
                        print(f"  ⚠️ [RADAR GUARD] Impuls invalid de 0 pips detectat pentru {symbol}. "
                              f"Se păstrează starea de WAITING fără activare fallback.")
                        sys.stdout.flush()
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
                            status=PullbackStatus.WAITING_1H_PULLBACK if timeframe == "H1" else PullbackStatus.WAITING_4H_PULLBACK,
                            equilibrium=choch_equilibrium
                        )
                    if impulse_size > 0:
                        if choch_direction == 'bullish':
                            # LONG: pullback DOWN la 40-60% din impuls
                            fib60 = choch_break_price - impulse_size * 0.40  # top zone
                            fib40 = choch_break_price - impulse_size * 0.60  # bottom zone
                        else:
                            # SHORT: pullback UP la 40-60% din impuls
                            fib60 = choch_break_price + impulse_size * 0.60  # top zone
                            fib40 = choch_break_price + impulse_size * 0.40  # bottom zone
                        fvg_top_synth = max(fib40, fib60)
                        fvg_bottom_synth = min(fib40, fib60)
                        fvg_entry_synth = (fvg_top_synth + fvg_bottom_synth) / 2.0
                        in_fvg_synth = fvg_bottom_synth <= current_price <= fvg_top_synth
                        pip_size_synth = 0.01 if 'JPY' in symbol.upper() else 0.0001
                        if in_fvg_synth:
                            dist_synth = 0.0
                            status_synth = PullbackStatus.EXECUTE_NOW_1H if timeframe == "H1" else PullbackStatus.EXECUTE_NOW_4H
                        else:
                            if choch_direction == 'bullish':
                                dist_synth = abs(current_price - fvg_top_synth) / pip_size_synth
                            else:
                                dist_synth = abs(fvg_bottom_synth - current_price) / pip_size_synth
                            status_synth = PullbackStatus.WAITING_1H_PULLBACK if timeframe == "H1" else PullbackStatus.WAITING_4H_PULLBACK
                        # V16.2: Fibo Fallback folosește 50% EQ exact (centrul zonei sintetice)
                        # choch_equilibrium calculat mai sus din același impuls
                        eq_for_synth = choch_equilibrium if choch_equilibrium else fvg_entry_synth
                        _eq_synth_str = f"{eq_for_synth:.5f}" if eq_for_synth is not None else "N/A"
                        print(f"  ⚡ [V15.4 FIBO FALLBACK] No FVG found — using Fibo 40-60% synthetic zone")
                        print(f"     Impulse: {swing_broken_price:.5f} → {choch_break_price:.5f} ({impulse_size/pip_size_synth:.1f} pips)")
                        print(f"     Synthetic FVG: [{fvg_bottom_synth:.5f} - {fvg_top_synth:.5f}] | EQ={_eq_synth_str} | In zone: {in_fvg_synth}")
                        sys.stdout.flush()
                        return TimeframeAnalysis(
                            timeframe=timeframe_display,
                            choch_detected=True,
                            choch_direction=choch_direction,
                            choch_time=choch_time_str,
                            choch_price=choch_price,
                            fvg_detected=True,
                            fvg_top=fvg_top_synth,
                            fvg_bottom=fvg_bottom_synth,
                            fvg_entry=fvg_entry_synth,
                            in_fvg=in_fvg_synth,
                            distance_to_fvg_pips=dist_synth,
                            status=status_synth,
                            equilibrium=eq_for_synth,
                            fvg_source="fibo_fallback"  # V19.6: transparență sursă
                        )
                except Exception as _fib_err:
                    print(f"  ⚠️ [V15.4 FIBO FALLBACK] Error computing synthetic zone: {_fib_err}")
                # Dacă fallback-ul eșuează, rămânem în WAITING
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
                    status=PullbackStatus.WAITING_1H_PULLBACK if timeframe == "H1" else PullbackStatus.WAITING_4H_PULLBACK,
                    equilibrium=choch_equilibrium
                )
            
            fvg_top = latest_fvg.top
            fvg_bottom = latest_fvg.bottom
            fvg_entry = (fvg_top + fvg_bottom) / 2.0
            
            # Check if price in FVG
            in_fvg = fvg_bottom <= current_price <= fvg_top
            
            # Calculate distance to FVG
            # V19.6 FIX #2: pip_size dinamic — corectează bug-ul JPY (x100 cosmetic)
            _pip_size_dist = 0.01 if 'JPY' in symbol.upper() else 0.0001
            if in_fvg:
                distance_to_fvg_pips = 0.0
                # V18: Blackout hour filter eliminat complet — sistemul execută 24/7 fără restricții de timp
                status = PullbackStatus.EXECUTE_NOW_1H if timeframe == "H1" else PullbackStatus.EXECUTE_NOW_4H
            else:
                if required_direction == 'bullish':
                    # For LONG: need to pull back DOWN to FVG
                    distance_to_fvg_pips = abs(current_price - fvg_top) / _pip_size_dist
                else:
                    # For SHORT: need to pull back UP to FVG
                    distance_to_fvg_pips = abs(fvg_bottom - current_price) / _pip_size_dist

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
                status=status,
                equilibrium=choch_equilibrium
            )
        
        except Exception as e:
            import traceback
            print(f"⚠️  Error analyzing {timeframe} for {symbol}: {e}")
            traceback.print_exc()
            sys.stdout.flush()
            # V19.4 FIX #3: scan_error=True propagat în JSON → Executor nu va folosi date corupte
            # Valorile FVG anterioare valabile din JSON sunt PĂSTRATE (nu suprascrise cu None)
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
                status=PullbackStatus.WAITING_1H_CHOCH if timeframe == "H1" else PullbackStatus.WAITING_4H_CHOCH,
                scan_error=True,
                scan_error_msg=str(e)
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
        # V19.4 FIX #4: prețul live este IMPERATIV — nu existe fallback silențios la daily_entry.
        # Dacă portul 8010 nu răspunde → RuntimeError explicit, prins de run_scan cu `continue`.
        current_price = self.get_current_price(symbol)
        if current_price is None:
            raise RuntimeError(
                f"Preț indisponibil pentru {symbol} — portul 8010 nu răspunde. "
                f"Verifică MarketDataProvider cBot pe VPS."
            )
        
        # ━━━ V19.5: POARTA DAILY ELIMINATĂ DEFINITIV ━━━
        # Radarul este EXCLUSIV un Scanner de Aliniere Fractală — Ochii sistemului.
        # NU are voie să blocheze execuția pe baza SL-ului Daily.
        # Aceasta este responsabilitatea EXCLUSIVĂ a Executorului (Mâinile).
        # Radarul citește DOAR direcția Daily ca Bias și descarcă imediat barele 4H/1H.
        required_direction = 'bullish' if direction == 'LONG' else 'bearish'

        print(f"\n{'='*80}")
        print(f"🔍 [{symbol}] Bias Daily: {direction} | Scanare structurală 4H+1H...")
        print(f"{'='*80}")
        print(f"💰 Current Price: {current_price:.5f}")
        print(f"📊 Daily FVG Referință: [{daily_fvg_bottom:.5f} - {daily_fvg_top:.5f}]")
        print(f"✅ Poartă: PERMANENT DESCHISĂ — decizia de invalidare aparține Executorului")
        sys.stdout.flush()

        # Analyze 1H — ALWAYS
        print("\n🔎 [1H] SNIPER SCAN (ATR 0.8x)...")
        sys.stdout.flush()
        tf_1h = self.analyze_timeframe(
            symbol=symbol,
            timeframe="H1",
            required_direction=required_direction,
            current_price=current_price,
            smc_detector=self.smc_1h
        )

        # Analyze 4H — ALWAYS
        print("\n🔎 [4H] HIGH CONFIDENCE SCAN (ATR 1.0x — V15.4)...")
        sys.stdout.flush()
        tf_4h = self.analyze_timeframe(
            symbol=symbol,
            timeframe="H4",
            required_direction=required_direction,
            current_price=current_price,
            smc_detector=self.smc_4h
        )

        # ━━━ V19.5: Determină execution_ready — FĂRĂ nicio poartă Daily ━━━
        # Radarul validează EXCLUSIV alinierea fractală 4H/1H cu biasul Daily.
        # Invalidarea pe SL = responsabilitatea EXCLUSIVĂ a Executorului.
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
            daily_zone_validated=True,  # V19.5: permanent True — Radarul nu invalidează niciodată
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
    
    def _update_setup_with_radar(self, setup: Dict, result: 'MultiTFResult') -> None:
        """
        V19.4: Pure in-memory update of a single setup dict with radar results.
        Shared by both _sync_to_monitoring_setups (single) and _batch_sync (batch).
        FIX #3: scan_error guard — nu suprascrie FVG valid cu None dacă analiza a crapat.
        FIX #5: Direction matching non-case-sensitive.
        """
        # 🎯 1H RADAR DATA
        if result.tf_1h.choch_detected:
            setup['radar_1h_choch_detected'] = True
            setup['radar_1h_choch_direction'] = result.tf_1h.choch_direction
            setup['radar_1h_choch_time'] = result.tf_1h.choch_time
            setup['radar_1h_choch_price'] = result.tf_1h.choch_price
        else:
            setup['radar_1h_choch_detected'] = False

        if result.tf_1h.scan_error:
            # V19.4 FIX #3: crash silențios detectat — semnalizăm în JSON dar PĂSTRĂM FVG anterior
            setup['radar_1h_scan_error'] = True
            setup['radar_1h_scan_error_msg'] = result.tf_1h.scan_error_msg
        elif result.tf_1h.fvg_detected:
            setup['radar_1h_fvg_top'] = result.tf_1h.fvg_top
            setup['radar_1h_fvg_bottom'] = result.tf_1h.fvg_bottom
            setup['radar_1h_fvg_entry'] = result.tf_1h.fvg_entry
            setup['radar_1h_in_fvg'] = result.tf_1h.in_fvg
            setup['radar_1h_distance_pips'] = result.tf_1h.distance_to_fvg_pips
            setup['radar_1h_fvg_source'] = result.tf_1h.fvg_source  # V19.6: "structural" | "fibo_fallback"
            setup.pop('radar_1h_scan_error', None)
        else:
            setup['radar_1h_fvg_top'] = None
            setup['radar_1h_fvg_bottom'] = None
            setup['radar_1h_fvg_entry'] = None
            setup.pop('radar_1h_scan_error', None)

        # V16.2: 50% Equilibrium al impulsului 1H CHoCH (frontiera P/D Array)
        if result.tf_1h.equilibrium is not None:
            setup['radar_1h_eq'] = result.tf_1h.equilibrium

        setup['radar_1h_status'] = result.tf_1h.status.value

        # 💎 4H RADAR DATA
        if result.tf_4h.choch_detected:
            setup['radar_4h_choch_detected'] = True
            setup['radar_4h_choch_direction'] = result.tf_4h.choch_direction
            setup['radar_4h_choch_time'] = result.tf_4h.choch_time
            setup['radar_4h_choch_price'] = result.tf_4h.choch_price
        else:
            setup['radar_4h_choch_detected'] = False

        if result.tf_4h.scan_error:
            # V19.4 FIX #3: crash silențios detectat — semnalizăm în JSON dar PĂSTRĂM FVG anterior
            setup['radar_4h_scan_error'] = True
            setup['radar_4h_scan_error_msg'] = result.tf_4h.scan_error_msg
        elif result.tf_4h.fvg_detected:
            setup['radar_4h_fvg_top'] = result.tf_4h.fvg_top
            setup['radar_4h_fvg_bottom'] = result.tf_4h.fvg_bottom
            setup['radar_4h_fvg_entry'] = result.tf_4h.fvg_entry
            setup['radar_4h_in_fvg'] = result.tf_4h.in_fvg
            setup['radar_4h_distance_pips'] = result.tf_4h.distance_to_fvg_pips
            setup['radar_4h_fvg_source'] = result.tf_4h.fvg_source  # V19.6: "structural" | "fibo_fallback"
            setup.pop('radar_4h_scan_error', None)
        else:
            setup['radar_4h_fvg_top'] = None
            setup['radar_4h_fvg_bottom'] = None
            setup['radar_4h_fvg_entry'] = None
            setup.pop('radar_4h_scan_error', None)

        # V16.2: 50% Equilibrium al impulsului 4H CHoCH (frontiera P/D Array)
        if result.tf_4h.equilibrium is not None:
            setup['radar_4h_eq'] = result.tf_4h.equilibrium

        setup['radar_4h_status'] = result.tf_4h.status.value

        # V16 FIX (B4): Salvăm timestamp-ul ultimei atingeri FVG pentru persistență
        if result.tf_1h.in_fvg or result.tf_4h.in_fvg:
            setup['last_in_fvg_time'] = datetime.now().isoformat()

        # V16 FIX (B4): Propagăm h4_locked din executor în radar
        # V16.5 FIX BUG#5: executor citește 'h4_structure_locked', nu 'h4_locked' — scriem ambele
        if result.tf_4h.choch_detected:
            setup['h4_locked'] = True
            setup['h4_structure_locked'] = True

        # 🏆 PRIORITY & EXECUTION STATUS
        setup['radar_priority_timeframe'] = result.priority_timeframe
        setup['radar_execution_ready'] = result.execution_ready
        setup['radar_verdict'] = result.verdict
        setup['radar_last_scan'] = datetime.now().isoformat()

        # V22.1: EXECUTE_NOW — cheia supremă de execuție
        # REGULA DE AUR: Radarul SETEAZĂ semnalul, EXECUTORUL îl consumă.
        # Radarul NU are voie să șteargă EXECUTE_NOW — doar executorul poate face asta
        # (după ce execută sau respinge). Altfel: radarul scrie False în ciclu T+30s,
        # înainte ca executorul să apuce să citească True-ul din T+00s → semnal pierdut.
        # Excepție: dacă entry1_filled=True, semnalul a fost deja consumat → safe to clear.
        if result.execution_ready:
            setup['EXECUTE_NOW'] = True
            logger.success(f"🔥 [V22.1 EXECUTE_NOW] {result.symbol}: Semnal complet confirmat → EXECUTE_NOW=True")
        elif setup.get('entry1_filled', False):
            # Executorul a confirmat execuția — acum putem curăța semnalul
            setup.pop('EXECUTE_NOW', None)
        # ALTFEL: execution_ready=False dar entry1_filled=False → NU atingem EXECUTE_NOW
        # Executorul îl va procesa și șterge el însuși la ciclul său de 30s

    def _batch_sync_to_monitoring_setups(
        self,
        results: list
    ) -> None:
        """
        V22 MERGE PARȚIAL — elimină race condition (Time Warp).

        Problema V19.4: json_data era citit la STARTUL ciclului (T+01s) și scris
        la FINALUL ciclului (T+31s) — suprascriind orice modificare făcută de
        setup_executor_monitor în interval (execuții, cleanup, status updates).

        Soluția V22:
          1. Re-citim monitoring_setups.json FRESH în momentul scrierii (după analiză)
          2. Actualizăm DOAR cheile Radarului (radar_4h_*, radar_1h_*, EXECUTE_NOW)
          3. Toate celelalte setup-uri (adăugate de scanner, modificate de executor)
             rămân INTACTE — merge parțial, nu overwrite complet.
        """
        try:
            import numpy as _np
            import os as _os

            def _json_safe(obj):
                if isinstance(obj, (_np.bool_,)):    return bool(obj)
                if isinstance(obj, (_np.integer,)):  return int(obj)
                if isinstance(obj, (_np.floating,)): return float(obj)
                if isinstance(obj, (_np.ndarray,)):  return obj.tolist()
                raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

            # ── Re-citire LIVE: starea ACTUALĂ a fișierului, nu snapshot-ul de la startul ciclului ──
            try:
                with open('monitoring_setups.json', 'r', encoding='utf-8') as _f:
                    fresh_data = json.load(_f)
            except Exception as _je:
                logger.error(f"⚠️ _batch_sync V22: Nu pot re-citi monitoring_setups.json: {_je}")
                return

            if isinstance(fresh_data, dict):
                setups = fresh_data.get("setups", [])
            elif isinstance(fresh_data, list):
                setups = fresh_data
            else:
                logger.error("⚠️ _batch_sync V22: format JSON nerecunoscut")
                return

            matched_count = 0
            for _original_setup, result in results:
                # Direction matching non-case-sensitive
                result_dir = result.direction.upper()
                for i, setup in enumerate(setups):
                    setup_dir = setup.get('direction', '').upper()
                    matches_sell   = (result_dir == 'SHORT' and setup_dir == 'SELL')
                    matches_buy    = (result_dir == 'LONG'  and setup_dir == 'BUY')
                    matches_direct = (result_dir == setup_dir)
                    if setup.get('symbol') == result.symbol and (matches_sell or matches_buy or matches_direct):
                        # ── Merge parțial: _update_setup_with_radar scrie DOAR cheile Radarului ──
                        # Cheile scanner/executor (status, entry_price, sl, tp etc.) rămân INTACTE
                        self._update_setup_with_radar(setups[i], result)
                        matched_count += 1
                        break

            if isinstance(fresh_data, dict):
                fresh_data['setups'] = setups
                fresh_data['last_updated'] = datetime.now().isoformat()
            else:
                fresh_data = setups

            tmp_path = 'monitoring_setups.json.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(fresh_data, f, indent=2, default=_json_safe)
            _os.replace(tmp_path, 'monitoring_setups.json')
            logger.success(
                f"💾 [BATCH SYNC V22 MERGE] monitoring_setups.json actualizat — "
                f"{matched_count}/{len(results)} parități sincronizate (re-citire LIVE, race-free)"
            )
            sys.stdout.flush()

        except Exception as e:
            logger.error(f"⚠️ _batch_sync_to_monitoring_setups V22 error: {e}")

    def _sync_to_monitoring_setups(self, original_setup: Dict, result: MultiTFResult):
        """
        🔥 CRITICAL: Write radar analysis back to monitoring_setups.json
        
        This enables setup_executor_monitor.py to use 1H/4H FVG zones
        instead of just Fibonacci 50%.
        """
        try:
            # Load monitoring_setups.json
            with open('monitoring_setups.json', 'r', encoding='utf-8') as f:
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

                # V19.4 FIX #5: direction matching non-case-sensitive (.upper() pe ambele)
                setup_direction = setup.get('direction', '').upper()
                result_direction = result.direction.upper()
                matches_sell   = (result_direction == 'SHORT' and setup_direction == 'SELL')
                matches_buy    = (result_direction == 'LONG'  and setup_direction == 'BUY')
                matches_direct = (result_direction == setup_direction)

                if setup.get('symbol') == result.symbol and (matches_sell or matches_buy or matches_direct):
                    # V19.4: logica de update delegată la helper partajat cu batch sync
                    self._update_setup_with_radar(setup, result)
                    setups[i] = setup
                    logger.success(f"✅ Synced radar data to monitoring_setups.json for {result.symbol}")
                    break
            
            # Save updated data
            if isinstance(data, dict):
                data['setups'] = setups
                data['last_updated'] = datetime.now().isoformat()
            else:
                data = setups
            
            # Atomic write: scrie în fișier temporar, apoi rename
            # Previne coruperea JSON-ului dacă două procese scriu simultan
            import numpy as _np

            def _json_safe(obj):
                """Convertește numpy types și alte tipuri non-serializabile la Python native."""
                if isinstance(obj, (_np.bool_,)):
                    return bool(obj)
                if isinstance(obj, (_np.integer,)):
                    return int(obj)
                if isinstance(obj, (_np.floating,)):
                    return float(obj)
                if isinstance(obj, (_np.ndarray,)):
                    return obj.tolist()
                raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

            tmp_path = 'monitoring_setups.json.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=_json_safe)
            import os as _os
            _os.replace(tmp_path, 'monitoring_setups.json')
            
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
            pip_sz = 0.01 if 'JPY' in result.symbol or 'XTI' in result.symbol else 0.0001
            if result.current_price > result.daily_fvg_top:
                dist_pips = (result.current_price - result.daily_fvg_top) / pip_sz
                direction_txt = f"ABOVE FVG — {dist_pips:.0f} pips to top of zone"
            else:
                dist_pips = (result.daily_fvg_bottom - result.current_price) / pip_sz
                direction_txt = f"BELOW FVG — {dist_pips:.0f} pips to bottom of zone"
            print(f"\n\u23f3 WAITING DAILY FVG: {direction_txt}")
            print(f"   Daily FVG: [{result.daily_fvg_bottom:.5f} - {result.daily_fvg_top:.5f}]")
            print(f"   Entry target: {result.daily_entry:.5f}")
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
        print("💎 [4H] HIGH CONFIDENCE ANALYSIS (ATR 1.0x — V15.4)")
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
            with open('monitoring_setups.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                if isinstance(data, dict):
                    setups = data.get("setups", [])
                elif isinstance(data, list):
                    setups = data
                else:
                    return []
                
                # V22: Accept orice setup cu 'symbol' — entry_price poate lipsi la setups proaspete
                # Filtrul pe entry_price era cauza invizibilității setup-urilor nou create de daily_scanner
                return [s for s in setups if isinstance(s, dict) and s.get('symbol')]
        
        except FileNotFoundError:
            print("⚠️  monitoring_setups.json not found")
            return []
        except json.JSONDecodeError as e:
            print(f"⚠️  Error parsing monitoring_setups.json: {e}")
            return []
    
    def run_scan(self, symbol: Optional[str] = None, all_setups: bool = False):
        """Run multi-timeframe scan — V19.4: batch JSON (1 citire, 1 scriere per ciclu)"""
        setups = self.load_monitoring_setups()

        if not setups:
            print("\n📭 No active setups in monitoring\n")
            return

        if symbol:
            target_setups = [s for s in setups if s.get('symbol') == symbol]
            if not target_setups:
                print(f"\n⚠️  No setup found for {symbol}\n")
                return
            setups = target_setups

        # V22: json_data pre-citire ELIMINATĂ — _batch_sync re-citește LIVE la final ciclu
        # (fix race condition cu setup_executor_monitor care scria în fișier în interval)

        # Print summary header
        print("\n" + "="*80)
        symbols_list = " | ".join([f"{s.get('symbol','?')} {s.get('direction','?')}" for s in setups])
        print(f"📋 LOADED {len(setups)} SETUP(S) FROM monitoring_setups.json")
        print(f"   {symbols_list}")
        print("="*80)
        sys.stdout.flush()

        ok_count = 0
        err_count = 0
        collected_results = []  # V19.4 FIX #5: colectăm (setup, result) pentru scriere batch

        for setup in setups:
            sym = setup.get('symbol', 'UNKNOWN')
            direction_label = setup.get('direction', '?').upper()
            print(f"\n🔄 [RADAR INIȚIALIZAT] Pornire descărcare date și analiză istorică pentru: {sym} {direction_label}...")
            sys.stdout.flush()
            try:
                # V19.4: save_to_json=False — NU scriem individual, scriem batch la final
                result = self.analyze_setup(setup, save_to_json=False)
                self.print_result(result)
                sys.stdout.flush()
                collected_results.append((setup, result))
                ok_count += 1
            except Exception as e:
                import traceback
                print(f"\n{'='*80}")
                print(f"❌ ERROR ANALYZING {sym}: {e}")
                traceback.print_exc()
                print("="*80 + "\n")
                sys.stdout.flush()
                err_count += 1
                continue  # izolare erori — continuăm cu paritatea următoare

        # V22: O SINGURĂ SCRIERE JSON — re-citire LIVE în _batch_sync (race-free merge)
        if collected_results:
            self._batch_sync_to_monitoring_setups(collected_results)

        print(f"\n✅ Scan complete: {ok_count} analyzed | ❌ {err_count} errors\n")
    
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
