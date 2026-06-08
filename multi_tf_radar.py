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
import os as _os_global
from pathlib import Path as _Path
# V22.2: Cale absolută — nu depinde de CWD la pornire
_RADAR_DIR = _Path(__file__).parent.resolve()
_MONITORING_FILE = str(_RADAR_DIR / 'monitoring_setups.json')
_MONITORING_TMP  = str(_RADAR_DIR / 'monitoring_setups.json.tmp')
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
    # V24.5: Structural SL = swing_broken.price ± buffer (4H only, dar calculat pe ambele TF)
    # LONG: SL sub swing_broken | SHORT: SL deasupra swing_broken
    h4_sl_price: Optional[float] = None
    # V24.9: Câte bare în urmă s-a format CHoCH-ul — recency guard pentru h4_structure_locked
    # 9999 = valoare default = CHoCH inexistent / nu am date
    choch_bars_ago: int = 9999
    # V25.1: BOS tracking INDEPENDENT de CHoCH — pentru confirmare trend continuu
    # Logica: CHoCH se formează O SINGURĂ DATĂ la schimbarea de caracter. Trendul continuă prin BOS.
    # Un trend valid = CHoCH vechi (inițiator) + BOS recent aliniat (confirmare trend activ).
    # h4_structure_locked se pune dacă: CHoCH proaspăt ALINIAT *SAU* BOS recent ALINIAT.
    bos_detected: bool = False
    bos_direction: Optional[str] = None
    bos_bars_ago: int = 9999


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

        # V25.2: Contor eșecuri consecutive port 8010 — alertă Telegram la 3 eșecuri
        self._port8010_fail_count: int = 0
        self._port8010_alert_sent: bool = False  # anti-spam: o singură alertă per incident
        self._telegram_token: str = _os_global.getenv('TELEGRAM_BOT_TOKEN', '')
        self._telegram_chat_id: str = _os_global.getenv('TELEGRAM_CHAT_ID', '')

    @staticmethod
    def _get_pip_size(symbol: str) -> float:
        """V24.4 Symbol-Agnostic pip size — suportă FX, JPY, XAU, BTC, OIL."""
        s = symbol.upper()
        if any(x in s for x in ['BTC', 'ETH', 'XRP', 'LTC', 'ADA', 'DOGE']):
            return 1.0       # Crypto: 1 USD = 1 pip
        elif any(x in s for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
            return 0.10      # Gold/Silver: 0.10 = 1 pip
        elif any(x in s for x in ['XTI', 'WTI', 'OIL', 'BRENT']):
            return 0.01      # Oil: 0.01 = 1 pip
        elif 'JPY' in s:
            return 0.01      # JPY pairs
        else:
            return 0.0001    # FX standard
    
    def _send_radar_telegram_alert(self, message: str) -> None:
        """V25.2: Trimite alertă critică pe Telegram din Radar (port 8010 offline etc.)"""
        if not self._telegram_token or not self._telegram_chat_id:
            return
        try:
            import requests as _req_tg
            sep = "────────────────"
            branded = (
                f"{message.strip()}\n\n"
                f"  {sep}\n"
                f"  🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
                f"  {sep}\n"
                f"  🏛 <b>ГЛИТЧ ИН МАТРИКС</b> 🏛"
            )
            _req_tg.post(
                f"https://api.telegram.org/bot{self._telegram_token}/sendMessage",
                json={'chat_id': self._telegram_chat_id, 'text': branded, 'parse_mode': 'HTML'},
                timeout=10
            )
        except Exception as _tg_err:
            print(f"⚠️ [RADAR TELEGRAM] Eroare trimitere alertă: {_tg_err}")

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price from cTrader — V25.2: contor eșecuri port 8010 cu alertă Telegram."""
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
                    # Succes — resetăm contorul și flag-ul de alertă
                    if self._port8010_fail_count > 0:
                        print(f"✅ [PORT 8010] Conexiune restaurată pentru {symbol} — resetare contor eșecuri")
                        self._port8010_fail_count = 0
                        self._port8010_alert_sent = False
                    return (bid + ask) / 2.0

            # Răspuns invalid (status != 200 sau bid/ask = 0)
            self._port8010_fail_count += 1
            print(f"⚠️  [PORT 8010] Răspuns invalid pentru {symbol} (eșec #{self._port8010_fail_count})")

        except Exception as e:
            self._port8010_fail_count += 1
            print(f"⚠️  [PORT 8010] Eroare conexiune pentru {symbol}: {e} (eșec #{self._port8010_fail_count})")

        # V25.2: Alertă Telegram la 3 eșecuri consecutive (anti-spam: o singură alertă per incident)
        if self._port8010_fail_count >= 3 and not self._port8010_alert_sent:
            self._port8010_alert_sent = True
            print(f"🚨 [PORT 8010 OFFLINE] {self._port8010_fail_count} eșecuri consecutive — trimit alertă Telegram!")
            self._send_radar_telegram_alert(
                f"🚨 <b>CONEXIUNE ÎNTRERUPTĂ — cBot OFFLINE</b>\n\n"
                f"MarketDataProvider cBot de pe cTrader NU răspunde pe portul 8010.\n"
                f"Eșecuri consecutive: <b>{self._port8010_fail_count}</b>\n\n"
                f"⛔ Datele live sunt INDISPONIBILE.\n"
                f"⛔ Execuția automată este BLOCATĂ.\n\n"
                f"🔧 Acțiune necesară:\n"
                f"  1. Verifică dacă cTrader este deschis pe VPS\n"
                f"  2. Verifică dacă cBot-ul <b>DATA-Market</b> rulează\n"
                f"  3. Verifică: <code>Test-NetConnection localhost -Port 8010</code>"
            )

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
        smc_detector: SMCDetector,
        allow_bos_trigger: bool = False  # V30.1: True pt CONTINUATION 4H — BOS = trigger direct
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

            # ── V25.1: BOS RECENCY — calculat INDEPENDENT, ÎNAINTE de orice filtrare ────────────
            # MOTIVUL: CHoCH apare o singură dată (schimbare de caracter). Continuarea trendului
            # e confirmată de BOS-uri succesive. Lacătul 4H trebuie să accepte și BOS recent aliniat
            # chiar dacă CHoCH-ul original are >30 bare vechime (trend sănătos, nu trend stale).
            _all_aligned_bos_for_lock = sorted(
                [b for b in bos_list if b.direction == required_direction],
                key=lambda x: x.index
            )
            _bos_detected_val: bool = bool(_all_aligned_bos_for_lock)
            _bos_direction_val: Optional[str] = _all_aligned_bos_for_lock[-1].direction if _all_aligned_bos_for_lock else None
            _bos_bars_ago_val: int = (len(df) - _all_aligned_bos_for_lock[-1].index) if _all_aligned_bos_for_lock else 9999
            # ─────────────────────────────────────────────────────────────────────────────────────

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
            
            # ━━━ V24.1: ORGANIC STRUCTURAL ALIGNMENT — NO LOOKBACK WALL ━━━
            # Colonel's fix: cel mai recent CHoCH sau BOS aliniat din TOATĂ seria.
            # LOOKBACK_BARS=100 eliminat — un semnal la bara 150 primează față de BOS minor la bara 80.
            # Consistent cu V24.0 organic (fractal 2, no pivot expiry în smc_detector).

            use_bos_as_choch = False
            bos_used = None

            # PAS 1: Cel mai recent CHoCH aliniat din TOATĂ seria descărcată
            # ── V24.9 DIRECTION GUARD: filtrăm STRICT pe required_direction ──
            # Setup BUY → acceptăm DOAR CHoCH Bullish. Setup SELL → DOAR CHoCH Bearish.
            # CHoCH-urile în direcție contrară sunt IGNORATE complet (zgomot structural).
            all_chochs_count = len(choch_list)
            aligned_chochs = sorted(
                [c for c in choch_list if c.direction == required_direction],
                key=lambda x: x.index
            )
            rejected_count = all_chochs_count - len(aligned_chochs)
            if rejected_count > 0:
                print(f"  🚫 [{timeframe_display} DIRECTION GUARD] {symbol}: {rejected_count} CHoCH(uri) în direcție contrară ({required_direction.upper()} opus) — IGNORATE strict")
                sys.stdout.flush()
            if aligned_chochs:
                bars_ago = len(df) - aligned_chochs[-1].index
                print(f"  ✅ [{timeframe_display} SCAN] {symbol} | CHoCH {required_direction.upper()} la -{bars_ago} bare | VALIDATED ✅")
                sys.stdout.flush()
            else:
                print(f"  ⚠️  [{timeframe_display} DIRECTION GUARD] {symbol}: Zero CHoCH {required_direction.upper()} găsit din {all_chochs_count} total — cascadem la BOS")
                sys.stdout.flush()

            # PAS 2: Cel mai recent BOS aliniat din TOATĂ seria (dacă nu există CHoCH)
            if not aligned_chochs:
                aligned_bos_all = sorted(
                    [b for b in bos_list if b.direction == required_direction],
                    key=lambda x: x.index
                )
                if aligned_bos_all:
                    use_bos_as_choch = True
                    bos_used = aligned_bos_all[-1]
                    bars_ago = len(df) - bos_used.index
                    if allow_bos_trigger:
                        # V30.1 CONTINUATION TRIGGER: BOS pe 4H in directia Daily Bias = intrare directa
                        # Trendul macro e lansat, pullback superficial nu va printa CHoCH de inversare.
                        # BOS = confirmare ca impulsul continua. Echivalent functional cu CHoCH pt entry.
                        print(f"  ⚡ [V30.1 CONTINUATION BOS-TRIGGER] {symbol} {timeframe_display}: "
                              f"BOS {required_direction.upper()} la -{bars_ago} bare — "
                              f"TRIGACI DIRECT (CONTINUATION, nu asteptam CHoCH inversare)")
                    else:
                        print(f"  ✅ [{timeframe_display} SCAN] {symbol} | BOS {required_direction.upper()} la -{bars_ago} bare | VALIDATED ✅ (BOS confirmare)")
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
                _choch_bars_ago = len(df) - bos_used.index
            else:
                latest_choch = aligned_chochs[-1]
                _choch_bars_ago = len(df) - latest_choch.index
            choch_direction = latest_choch.direction
            # ── V24.9 DIRECTION ASSERTION — guard final ──────────────────────
            # Paranoid check: dacă după toate filtrele choch_direction != required_direction
            # (nu ar trebui să se întâmple, dar dacă se întâmplă → WAITING forțat)
            if choch_direction != required_direction:
                print(f"  🚨 [{timeframe_display} DIRECTION ASSERT FAILED] {symbol}: "
                      f"CHoCH dir={choch_direction} != required={required_direction} — FORȚĂM WAITING")
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
                    status=PullbackStatus.WAITING_1H_CHOCH if timeframe == "H1" else PullbackStatus.WAITING_4H_CHOCH,
                    choch_bars_ago=9999
                )
            choch_index = latest_choch.index
            choch_break_price = float(latest_choch.break_price)   # V24.3 FIX: definit în scope principal
            
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
                pip_size_eq = self._get_pip_size(symbol)
                _eq_str = f"{choch_equilibrium:.5f}" if choch_equilibrium is not None else "N/A"
                print(f"  📐 [V16.2 EQ] {timeframe_display} Impulse: {_sbp:.5f} → {_cbp:.5f} | "
                      f"EQ={_eq_str} ({abs(_cbp - _sbp)/pip_size_eq:.1f} pips)")
                sys.stdout.flush()
            except Exception:
                pass

            # ── V24.5: Structural SL = swing_broken.price ± 3 pip buffer ──────
            # SL-ul autentic SMC: nivelul swing-ului rupt de CHoCH, cu buffer mic.
            # LONG (bullish CHoCH): swing_broken este un Swing Low → SL sub el
            # SHORT (bearish CHoCH): swing_broken este un Swing High → SL deasupra lui
            h4_sl_price = None
            try:
                _sl_swing_price = float(latest_choch.swing_broken.price)
                _sl_buffer = self._get_pip_size(symbol) * 3  # 3 pip buffer
                if choch_direction == 'bullish':
                    h4_sl_price = _sl_swing_price - _sl_buffer
                else:
                    h4_sl_price = _sl_swing_price + _sl_buffer
                print(f"  🛡️  [V24.5 SL] {timeframe_display} swing_broken={_sl_swing_price:.5f} "
                      f"→ h4_sl_price={h4_sl_price:.5f} (dir={choch_direction})")
                sys.stdout.flush()
            except Exception as _sl_err:
                print(f"  ⚠️ [V24.5 SL] Eroare calcul h4_sl_price: {_sl_err}")
                sys.stdout.flush()

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
                        pip_size_guard = self._get_pip_size(symbol)  # noqa: F841 — cosmetic log only
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
                            equilibrium=choch_equilibrium,
                            h4_sl_price=h4_sl_price,
                            bos_detected=_bos_detected_val,
                            bos_direction=_bos_direction_val,
                            bos_bars_ago=_bos_bars_ago_val
                        )
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
                        pip_size_synth = self._get_pip_size(symbol)  # V24.4 Symbol-Agnostic

                        # ── V24.2 SNIPER ANTI-FOMO — Fibo Fallback ──────────────────────
                        # EXECUTE_NOW STRICT doar dacă prețul a făcut pullback fizic în zona 40-60%.
                        # Dacă impulsul e proaspăt și prețul e la <35% retragere → WAITING.
                        # Calculăm retragerea curentă față de impulsul CHoCH.
                        if choch_direction == 'bullish':
                            # LONG: pullback = cât a coborât prețul față de break_price
                            retrace_pct = (choch_break_price - current_price) / impulse_size if impulse_size > 0 else 0
                        else:
                            # SHORT: pullback = cât a urcat prețul față de break_price
                            retrace_pct = (current_price - choch_break_price) / impulse_size if impulse_size > 0 else 0

                        in_fvg_synth = fvg_bottom_synth <= current_price <= fvg_top_synth
                        # Anti-FOMO guard: chiar dacă prețul e geometric în zonă,
                        # verificăm că retragerea e >= 35% (impulsul nu e proaspăt)
                        if in_fvg_synth and retrace_pct >= 0.35:
                            dist_synth = 0.0
                            # V31.0 CANDLE_AGE GUARD: Fibo Fallback EXECUTE_NOW numai pe CHoCH live (<=3 bare)
                            if _choch_bars_ago <= 3:
                                status_synth = PullbackStatus.EXECUTE_NOW_1H if timeframe == "H1" else PullbackStatus.EXECUTE_NOW_4H
                                print(f"  [V31.0 FIBO FALLBACK LIVE {timeframe_display}] {symbol} {required_direction.upper()} "
                                      f"-> EXECUTE_NOW (CHoCH la -{_choch_bars_ago} bare <=3 LIVE) "
                                      f"Fibo 40-60% [{fvg_bottom_synth:.5f}-{fvg_top_synth:.5f}] "
                                      f"Retrace={retrace_pct*100:.1f}% Pret={current_price:.5f}")
                                sys.stdout.flush()
                            else:
                                status_synth = PullbackStatus.WAITING_1H_PULLBACK if timeframe == "H1" else PullbackStatus.WAITING_4H_PULLBACK
                                print(f"  [V31.0 CANDLE_AGE FIBO {timeframe_display}] {symbol}: in Fibo zone dar CHoCH la -{_choch_bars_ago} bare > 3 — WAITING")
                                sys.stdout.flush()
                        else:
                            if choch_direction == 'bullish':
                                dist_synth = abs(current_price - fvg_top_synth) / pip_size_synth
                            else:
                                dist_synth = abs(fvg_bottom_synth - current_price) / pip_size_synth
                            status_synth = PullbackStatus.WAITING_1H_PULLBACK if timeframe == "H1" else PullbackStatus.WAITING_4H_PULLBACK

                        # V16.2: Fibo Fallback folosește 50% EQ exact (centrul zonei sintetice)
                        eq_for_synth = choch_equilibrium if choch_equilibrium else fvg_entry_synth
                        _eq_synth_str = f"{eq_for_synth:.5f}" if eq_for_synth is not None else "N/A"
                        _retrace_str = f"{retrace_pct*100:.1f}%"
                        _sniper_note = "🎯 IN ZONE — EXECUTE" if status_synth in (PullbackStatus.EXECUTE_NOW_1H, PullbackStatus.EXECUTE_NOW_4H) else f"⏳ PÂNDĂ ({_retrace_str} retrace, așteptăm 40-60%)"
                        print(f"  ⚡ [V24.2 FIBO FALLBACK] No FVG — Synthetic zone 40-60%")
                        print(f"     Impulse: {swing_broken_price:.5f} → {choch_break_price:.5f} ({impulse_size/pip_size_synth:.1f} pips)")
                        print(f"     Zone: [{fvg_bottom_synth:.5f} - {fvg_top_synth:.5f}] | EQ={_eq_synth_str} | Retrace: {_retrace_str} | {_sniper_note}")
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
                            in_fvg=in_fvg_synth and retrace_pct >= 0.35,  # Anti-FOMO
                            distance_to_fvg_pips=dist_synth,
                            status=status_synth,
                            equilibrium=eq_for_synth,
                            fvg_source="fibo_fallback",
                            h4_sl_price=h4_sl_price,
                            choch_bars_ago=_choch_bars_ago,
                            bos_detected=_bos_detected_val,
                            bos_direction=_bos_direction_val,
                            bos_bars_ago=_bos_bars_ago_val
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
                    equilibrium=choch_equilibrium,
                    h4_sl_price=h4_sl_price,
                    bos_detected=_bos_detected_val,
                    bos_direction=_bos_direction_val,
                    bos_bars_ago=_bos_bars_ago_val
                )
            
            fvg_top = latest_fvg.top
            fvg_bottom = latest_fvg.bottom
            fvg_entry = (fvg_top + fvg_bottom) / 2.0
            
            # ── V24.2 SNIPER ANTI-FOMO — Structural FVG ─────────────────────────
            # EXECUTE_NOW STRICT doar dacă prețul e FIZIC în FVG.
            # Dacă structura s-a rupt și prețul a fugit fără a mai reveni → WAITING.
            # Check if price in FVG
            in_fvg = fvg_bottom <= current_price <= fvg_top
            
            # Calculate distance to FVG
            # V24.4: pip_size Symbol-Agnostic — suportă FX, JPY, XAU, BTC, OIL
            _pip_size_dist = self._get_pip_size(symbol)
            if in_fvg:
                distance_to_fvg_pips = 0.0
                # V31.0 CANDLE_AGE GUARD: EXECUTE_NOW NUMAI pe CHoCH live (≤ 3 bare = ≤12h pe H4)
                # CHoCH > 3 bare = structură veche confirmată dar trăgaciul NU este pe lumânarea curentă
                if _choch_bars_ago <= 3:
                    status = PullbackStatus.EXECUTE_NOW_1H if timeframe == "H1" else PullbackStatus.EXECUTE_NOW_4H
                    _sniper_note = f"SNIPER EXECUTE LIVE — pret {current_price:.5f} IN FVG | CHoCH -{_choch_bars_ago} bare (LIVE <=3)"
                    print(f"  [V31.0 RADAR TRIGGER LIVE {timeframe_display}] {symbol} {required_direction.upper()} "
                          f"-> EXECUTE_NOW (CHoCH la -{_choch_bars_ago} bare <=3 = LIVE) "
                          f"FVG [{fvg_bottom:.5f}-{fvg_top:.5f}] | Entry={fvg_entry:.5f} | Pret={current_price:.5f}")
                    sys.stdout.flush()
                else:
                    # CHoCH vechi — in FVG dar nu live: ramane in WAITING
                    status = PullbackStatus.WAITING_1H_PULLBACK if timeframe == "H1" else PullbackStatus.WAITING_4H_PULLBACK
                    _sniper_note = f"IN FVG dar CHoCH la -{_choch_bars_ago} bare > 3 (V31.0: nu live) — WAITING"
                    print(f"  [V31.0 CANDLE_AGE {timeframe_display}] {symbol}: pret in FVG dar CHoCH la -{_choch_bars_ago} bare > 3 — WAITING pt CHoCH live")
                    sys.stdout.flush()
            else:
                if required_direction == 'bullish':
                    # For LONG: need to pull back DOWN to FVG
                    distance_to_fvg_pips = abs(current_price - fvg_top) / _pip_size_dist
                else:
                    # For SHORT: need to pull back UP to FVG
                    distance_to_fvg_pips = abs(fvg_bottom - current_price) / _pip_size_dist

                status = PullbackStatus.WAITING_1H_PULLBACK if timeframe == "H1" else PullbackStatus.WAITING_4H_PULLBACK
                _sniper_note = f"⏳ SNIPER PÂNDĂ — prețul {current_price:.5f} NOT IN FVG [{fvg_bottom:.5f}-{fvg_top:.5f}] | dist={distance_to_fvg_pips:.1f}p"

            print(f"  🔭 [V24.2 SNIPER] {symbol} {timeframe} | {choch_direction.upper()} CHoCH @ {choch_break_price:.5f}")
            print(f"     {_sniper_note}")
            sys.stdout.flush()
            
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
                equilibrium=choch_equilibrium,
                h4_sl_price=h4_sl_price,
                choch_bars_ago=_choch_bars_ago,
                bos_detected=_bos_detected_val,
                bos_direction=_bos_direction_val,
                bos_bars_ago=_bos_bars_ago_val
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
        # ── V25.0 DIRECTION GUARD: ZERO toleranță pentru direcție lipsă sau ambiguuă ──────────
        # BUG PRE-V25.0: default='SHORT' — dacă câmpul 'direction' lipsea din JSON,
        # Radarul scăna silențios CHoCH Bearish pentru un setup care era BUY.
        # FIX: dacă direction e absent sau nerecunoscut → SKIP complet cu log CRITICAL.
        # Nici un trade nu se execută fără direcție explicită confirmată.
        _raw_direction = setup_data.get('direction', '').strip().upper()
        if not _raw_direction:
            logger.critical(
                f"🚨 [V25.0 DIRECTION MISSING] {symbol}: Câmpul 'direction' este ABSENT din monitoring_setups.json. "
                f"Setup SKIPPED — Radarul NU ghicește direcția!"
            )
            return None
        # Normalizăm: BUY → LONG, SELL → SHORT (compatibilitate cu scanner)
        if _raw_direction in ('BUY', 'LONG'):
            direction = 'LONG'
        elif _raw_direction in ('SELL', 'SHORT'):
            direction = 'SHORT'
        else:
            logger.critical(
                f"🚨 [V25.0 DIRECTION INVALID] {symbol}: Valoare necunoscută '{_raw_direction}' "
                f"pentru 'direction'. Valori valide: BUY, SELL, LONG, SHORT. Setup SKIPPED!"
            )
            return None
        
        # Get Daily data
        # V30.2: Guard None — entry_price/fvg_top/fvg_bottom pot fi null in JSON
        # (setups salvate cu OB else-branch vechi sau WAITING_D1_PULLBACK fara h4_signal)
        # float(None) crasheaza cu TypeError → 12 errors per scan. Fix: fallback explicit la 0.
        _ep = setup_data.get('entry_price')
        daily_entry = float(_ep) if _ep is not None else 0.0
        # V31.0: poi_top/poi_bottom sunt câmpurile noi din Scanner V31.0 — backward compat cu fvg_top/fvg_bottom
        _ft = setup_data.get('poi_top') or setup_data.get('fvg_top')
        daily_fvg_top = float(_ft) if _ft is not None else daily_entry
        _fb = setup_data.get('poi_bottom') or setup_data.get('fvg_bottom')
        daily_fvg_bottom = float(_fb) if _fb is not None else daily_entry
        # V31.0: daily_target_price este TP-ul macro structural din Scanner
        _daily_target_v31 = setup_data.get('daily_target_price') or setup_data.get('daily_tp_price')
        # V24.6 PERMISSIVE DAILY FLOW: Setup cu FVG sintetic (zona Equilibrium) — niciun FVG corp natural
        # Radarul 4H TREBUIE să găsească un CHoCH real înainte de EXECUTE_NOW
        _daily_bias_active = bool(setup_data.get('daily_bias_active', False))
        # V30.1: strategy_type din JSON — determina trigaci diferentiat pe 4H
        # CONTINUATION (Daily BOS): allow_bos=True — 4H BOS in directie = executie imediata
        # REVERSAL (Daily CHoCH): allow_bos=False — asteptam CHoCH de inversare pe 4H
        _strategy_type = str(setup_data.get('strategy_type', 'reversal')).lower()
        _allow_bos_4h = (_strategy_type == 'continuation')  # True doar pentru trend continuation
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
        if _daily_bias_active:
            print(f"⚠️  [V24.6 DAILY BIAS] {symbol}: FVG sintetic (Equilibrium) — EXECUTE_NOW blocat până la CHoCH 4H real!")
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
        # V30.1: CONTINUATION setup — 4H BOS aliniat = trigaci direct (trendul continua fara CHoCH inversare)
        if _allow_bos_4h:
            print(f"  ⚡ [V30.1 CONTINUATION] {symbol}: allow_bos=True — 4H BOS in directie {required_direction.upper()} = trigger echivalent CHoCH")
        sys.stdout.flush()
        tf_4h = self.analyze_timeframe(
            symbol=symbol,
            timeframe="H4",
            required_direction=required_direction,
            current_price=current_price,
            smc_detector=self.smc_4h,
            allow_bos_trigger=_allow_bos_4h  # V30.1
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

        # ━━━ V24.6 DAILY BIAS GUARD: Setup cu FVG sintetic ━━━━━━━━━━━━━━━━━━━━━━━━
        # Dacă setup-ul vine din scanarea permisivă (fără FVG corp Daily natural),
        # EXECUTE_NOW este permis NUMAI dacă 4H a detectat un CHoCH real (nu BOS-ca-CHoCH).
        # Aceasta este REGULA DE AUR: Scanner = Bias, Radar = Arbitrul final.
        if _daily_bias_active and execution_ready:
            # Verificăm că avem un CHoCH 4H real (tf_4h.choch_detected = True din CHoCH real)
            # BOS-ul sintetic nu garantează confluență suficientă pe zona sintetică
            if not tf_4h.choch_detected:
                execution_ready = False
                priority_timeframe = None
                verdict = f"⚠️ [V24.6 DAILY BIAS] EXECUTE blocat: FVG sintetic necesită CHoCH 4H real (nu BOS)"
                print(f"  🛡️ [V24.6 DAILY BIAS GUARD] {symbol}: EXECUTE_NOW blocat — zona Equilibrium sintetic\u0103 fara CHoCH 4H confirmat")
            else:
                print(f"  ✅ [V24.6 DAILY BIAS UNLOCK] {symbol}: CHoCH 4H real detectat — EXECUTE_NOW autorizat pe zona Equilibrium")
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
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

        # V24.5: Structural SL din swing_broken 4H — scriem în JSON pentru Executor
        if result.tf_4h.h4_sl_price is not None:
            setup['h4_sl_price'] = result.tf_4h.h4_sl_price

        setup['radar_4h_status'] = result.tf_4h.status.value

        # V16 FIX (B4): Salvăm timestamp-ul ultimei atingeri FVG pentru persistență
        if result.tf_1h.in_fvg or result.tf_4h.in_fvg:
            setup['last_in_fvg_time'] = datetime.now().isoformat()

        # ── V25.1: h4_structure_locked — CHoCH PROASPĂT *SAU* BOS RECENT ALINIAT ────────────
        # ARHITECTURĂ SMC CORECTĂ (observație Colonel):
        #   CHoCH = schimbare de caracter, apare O SINGURĂ DATĂ la inversarea trendului.
        #   BOS   = confirmare continuare trend, apare REPETAT pe tot parcursul trendului.
        # PROBLEMA V25.0: limita de 30 bare pe CHoCH invalida trenduri 4H perfect sănătoase
        #   unde CHoCH-ul s-a format acum 60+ bare dar piața face BOS-uri recente aliniate.
        # FIX V25.1: Lacătul se pune dacă ORICARE din condiții e adevărată:
        #   A) CHoCH 4H PROASPĂT (≤72 bare) + ALINIAT — debut trend, confirmare inițială
        #   B) BOS 4H RECENT   (≤72 bare) + ALINIAT — trend stabilit, continuare confirmată
        # Direcția rămâne OBLIGATORIE în ambele cazuri (V25.0 Direction Guard intact).
        # V25.2: 30→72 bare — pullback pe Daily poate dura 4-14 zile, aliniat cu V25.0 din smc_detector
        _4H_STRUCT_MAX_BARS = 72   # 72 × 4H = 288h = 12 zile — fereastra extinsă (V25.2)
        _setup_direction_lower = 'bullish' if result.direction == 'LONG' else 'bearish'

        # — Condiția A: CHoCH proaspăt + aliniat ——————————————————————————————
        _4h_choch_direction_ok = (
            result.tf_4h.choch_direction is not None
            and result.tf_4h.choch_direction == _setup_direction_lower
        )
        _4h_choch_is_fresh_and_aligned = (
            result.tf_4h.choch_detected
            and result.tf_4h.choch_bars_ago <= _4H_STRUCT_MAX_BARS
            and _4h_choch_direction_ok
        )

        # — Condiția B: BOS recent + aliniat (trend deja stabilit, CHoCH poate fi mai vechi) ——
        _4h_bos_direction_ok = (
            result.tf_4h.bos_direction is not None
            and result.tf_4h.bos_direction == _setup_direction_lower
        )
        _4h_bos_is_fresh_and_aligned = (
            result.tf_4h.bos_detected
            and result.tf_4h.bos_bars_ago <= _4H_STRUCT_MAX_BARS
            and _4h_bos_direction_ok
        )

        # — Decizia lacătului ————————————————————————————————————————————————
        if _4h_choch_is_fresh_and_aligned or _4h_bos_is_fresh_and_aligned:
            setup['h4_locked'] = True
            setup['h4_structure_locked'] = True
            if _4h_choch_is_fresh_and_aligned:
                _lock_trigger = (
                    f"CHoCH 4H PROASPĂT (la -{result.tf_4h.choch_bars_ago} bare = "
                    f"~{result.tf_4h.choch_bars_ago * 4}h | dir={result.tf_4h.choch_direction} ✅)"
                )
            else:
                _lock_trigger = (
                    f"BOS 4H RECENT (la -{result.tf_4h.bos_bars_ago} bare = "
                    f"~{result.tf_4h.bos_bars_ago * 4}h | dir={result.tf_4h.bos_direction} ✅) "
                    f"[CHoCH la -{result.tf_4h.choch_bars_ago} bare — trend stabilit]"
                )
            logger.info(
                f"🔒 [V25.1 H4 LOCK] {result.symbol}: {_lock_trigger} "
                f"→ h4_structure_locked=True"
            )
        elif result.tf_4h.choch_detected and not _4h_choch_direction_ok:
            logger.warning(
                f"🚫 [V25.1 H4 DIRECTION MISMATCH] {result.symbol}: "
                f"CHoCH 4H dir={result.tf_4h.choch_direction} != setup={_setup_direction_lower} "
                f"— h4_structure_locked NESETAT (CHoCH contrar = zgomot structural)"
            )
        elif result.tf_4h.choch_detected and result.tf_4h.choch_bars_ago > _4H_STRUCT_MAX_BARS \
                and not _4h_bos_is_fresh_and_aligned:
            # CHoCH vechi ȘI fără BOS recent aliniat — structura poate fi stale
            logger.warning(
                f"⚠️  [V25.1 H4 STALE] {result.symbol}: CHoCH 4H la -{result.tf_4h.choch_bars_ago} bare "
                f"(>{_4H_STRUCT_MAX_BARS} max) + NICIUN BOS recent aliniat "
                f"— h4_structure_locked NESETAT (structură neconfirmată)"
            )
        # else: nicio structură → rămâne cum era (nu atingem flagul)

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
            # V31.0 REVERSAL vs CONTINUATION TRIGGER GUARD
            # REVERSAL: accepta NUMAI CHoCH ca trigger (BOS = continuarea trendului anterior — invalid pt reversal)
            # CONTINUATION: accepta si BOS (trend in desfasurare, BOS = confirmare continuare)
            _setup_type_v31 = setup.get('setup_type', setup.get('strategy_type', '')).upper()
            _is_reversal_v31 = 'REVERSAL' in _setup_type_v31
            _exec_tf_v31 = result.priority_timeframe or '?'
            _exec_tf_data_v31 = result.tf_1h if _exec_tf_v31 == '1H' else result.tf_4h
            # BOS-only trigger detection
            _used_bos_only = (
                getattr(_exec_tf_data_v31, 'bos_detected', False)
                and not _exec_tf_data_v31.choch_detected
            )
            if _is_reversal_v31 and _used_bos_only:
                # REVERSAL pe BOS = INTERZIS — asteptam CHoCH autentic
                logger.warning(
                    f"[V31.0 REVERSAL GUARD] {result.symbol}: EXECUTE_NOW blocat — "
                    f"setup REVERSAL nu accepta BOS ca trigger. Numai CHoCH autentic!"
                )
                # Nu setam EXECUTE_NOW — asteptam CHoCH real
            else:
                setup['EXECUTE_NOW'] = True
                _exec_tf = result.priority_timeframe or '?'
                _exec_tf_data = result.tf_1h if _exec_tf == '1H' else result.tf_4h
                _exec_fvg_src = getattr(_exec_tf_data, 'fvg_source', 'unknown')
                _exec_zone = (
                    f"[{_exec_tf_data.fvg_bottom:.5f} - {_exec_tf_data.fvg_top:.5f}]"
                    if _exec_tf_data.fvg_top and _exec_tf_data.fvg_bottom else "zona necunoscuta"
                )
                _exec_bars = getattr(_exec_tf_data, 'choch_bars_ago', '?')
                _exec_eq = f"EQ={_exec_tf_data.equilibrium:.5f}" if _exec_tf_data.equilibrium else "EQ=N/A"
                logger.success(
                    f"[V31.0 RADAR TRIGGER LIVE {_exec_tf}] {result.symbol} {result.direction} -> EXECUTE_NOW=True"
                    f" | {'FVG structural' if _exec_fvg_src == 'structural' else 'Fibo Fallback'}"
                    f" dupa CHoCH {_exec_tf} LIVE (<=3 bare) | Zona: {_exec_zone}"
                    f" | Pret={result.current_price:.5f} | {_exec_eq}"
                )
        elif not result.execution_ready and setup.get('EXECUTE_NOW') and not setup.get('entry1_filled'):
            # V31.0: Pretul a iesit din zona FVG — resetam EXECUTE_NOW (semnal expirat)
            setup.pop('EXECUTE_NOW', None)
            logger.info(f"[V31.0] {result.symbol}: EXECUTE_NOW resetat — pretul nu mai este in FVG zone")
        elif setup.get('entry1_filled', False):
            # Executorul a confirmat executia — acum putem curata semnalul
            setup.pop('EXECUTE_NOW', None)
        # ALTFEL: execution_ready=False dar entry1_filled=False → NU atingem EXECUTE_NOW

        # V31.0: Propagam daily_target_price ca daily_tp_price pentru backward compat cu Executor
        if setup.get('daily_target_price') and not setup.get('daily_tp_price'):
            setup['daily_tp_price'] = setup['daily_target_price']

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
                with open(_MONITORING_FILE, 'r', encoding='utf-8') as _f:
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

            tmp_path = _MONITORING_TMP
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(fresh_data, f, indent=2, default=_json_safe)
            _os.replace(tmp_path, _MONITORING_FILE)
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
            with open(_MONITORING_FILE, 'r', encoding='utf-8') as f:
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

            tmp_path = _MONITORING_TMP
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=_json_safe)
            import os as _os
            _os.replace(tmp_path, _MONITORING_FILE)
            
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
            with open(_MONITORING_FILE, 'r', encoding='utf-8') as f:
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
    
    def _compute_adaptive_interval(self, base_interval: int, symbol: Optional[str] = None) -> int:
        """
        V25.2 ADAPTIVE INTERVAL — ajustează frecvența scanării bazat pe proximitatea față de FVG.

        Logică:
          ≥ 1 setup cu preț < 10 pips de FVG  →  5s  (Sniper mode — nu ratăm wick-uri rapide)
          ≥ 1 setup în WAITING_*_PULLBACK      → 10s  (Pullback activ — monitorizare intensă)
          Altfel                               → base_interval (30s default)

        Date citite din JSON-ul deja scris de ciclul anterior — zero HTTP calls extra.
        """
        try:
            with open(_MONITORING_FILE, 'r', encoding='utf-8') as _af:
                _ad = json.load(_af)
            _setups = _ad.get('setups', _ad) if isinstance(_ad, dict) else _ad
            if not isinstance(_setups, list):
                return base_interval
            if symbol:
                _setups = [s for s in _setups if s.get('symbol') == symbol]

            _min_dist = float('inf')
            _has_pullback = False

            for _s in _setups:
                # Verifică distanța față de FVG (stocată de scanarea anterioară)
                for _dk in ('radar_1h_distance_pips', 'radar_4h_distance_pips'):
                    _dv = _s.get(_dk)
                    if isinstance(_dv, (int, float)) and _dv >= 0:
                        _min_dist = min(_min_dist, _dv)
                # Verifică dacă există pullback activ în statusuri
                for _sk in ('radar_1h_status', 'radar_4h_status'):
                    _sv = _s.get(_sk, '')
                    if 'WAITING' in _sv and 'PULLBACK' in _sv:
                        _has_pullback = True

            if _min_dist < 10:
                return 5    # ⚡ Sniper: preț la <10 pips de FVG
            if _has_pullback:
                return 10   # 🔍 Pullback activ pe 4H sau 1H
            return base_interval  # 🔄 Normal
        except Exception:
            return base_interval

    def watch_mode(self, interval: int, symbol: Optional[str] = None, all_setups: bool = False):
        """Run scan in watch mode with auto-refresh"""
        print("\n" + "="*80)
        print("👁️  MULTI-TF RADAR - WATCH MODE ACTIVE (V25.2 ADAPTIVE INTERVAL)")
        print("="*80)
        print(f"⏱️  Base Interval: {interval}s | Adaptive: 10s (pullback) / 5s (în FVG)")
        print(f"🎯 Target: {'ALL setups' if all_setups else (symbol if symbol else 'First setup')}")
        print("Press Ctrl+C to stop")
        print("="*80 + "\n")

        try:
            while True:
                self.run_scan(symbol=symbol, all_setups=all_setups)

                # V25.2: Interval adaptiv bazat pe proximitate FVG (citire JSON fără HTTP extra)
                next_interval = self._compute_adaptive_interval(interval, symbol)
                if next_interval <= 5:
                    print(f"\n⚡ [SNIPER MODE] Preț aproape de FVG — rescan în {next_interval}s...\n")
                elif next_interval <= 10:
                    print(f"\n🔍 [PULLBACK ACTIV] CHoCH detectat — rescan în {next_interval}s...\n")
                else:
                    print(f"\n⏳ Next scan în {next_interval}s (normal)...\n")
                time.sleep(next_interval)

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
