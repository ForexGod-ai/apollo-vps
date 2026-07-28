"""
Daily Scanner for ForexGod - Glitch Signals
Scans all pairs for "Glitch in Matrix" setups at 00:05 daily
Uses IC Markets data via cTrader cBot HTTP server
"""

import sys
import io
# Fix Windows cp1252 emoji encoding issue
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import requests
import pandas as pd
from datetime import datetime
import json
import os
import time
import argparse
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from dotenv import load_dotenv
from loguru import logger

from smc_detector import SMCDetector, TradeSetup, CHoCH, BOS
from telegram_notifier import TelegramNotifier
from ctrader_cbot_client import CTraderCBotClient
from strategy_optimizer import StrategyOptimizer
from ai_probability_analyzer import AIProbabilityAnalyzer
from pip_utils import get_pip_size, liquidity_already_swept
from poi_utils import poi_bounds_from_stored, poi_touch_active

load_dotenv()

# Global flag for testing/audit - ignore open positions check
IGNORE_OPEN_POSITIONS = False


def _clear_deep_sleep_on_resume() -> bool:
    """V39.1: Daca /resume activ, sterge deep_sleep_state.json inainte de scan."""
    try:
        resume_marker = os.path.join('data', 'system_resumed.json')
        if not os.path.exists(resume_marker):
            return False
        with open(resume_marker, 'r', encoding='utf-8') as f:
            rm = json.load(f)
        resumed_at = datetime.fromisoformat(rm.get('resumed_at', '').replace('Z', '+00:00'))
        try:
            import pytz
            ro_tz = pytz.timezone('Europe/Bucharest')
            is_today = resumed_at.astimezone(ro_tz).strftime('%Y-%m-%d') == datetime.now(ro_tz).strftime('%Y-%m-%d')
        except Exception:
            is_today = resumed_at.date() == datetime.utcnow().date()
        if not is_today:
            return False
        ds_file = os.path.join('data', 'deep_sleep_state.json')
        if os.path.exists(ds_file):
            os.remove(ds_file)
            print("🔱 [V39.1] deep_sleep_state.json sters — scan permis dupa /resume")
        return True
    except Exception as e:
        logger.debug(f"[V39.1] resume wake check: {e}")
        return False


class CTraderDataProvider:
    """Downloads historical data from cTrader via cBot HTTP server"""
    
    def __init__(self):
        self.client = CTraderCBotClient()
        self.connected = False
    
    def connect(self) -> bool:
        """Check if cBot server is running on port 8010"""
        try:
            if self.client.is_available():
                print("✅ cTrader cBot connected (IC Markets, port 8010)")
                self.connected = True
                return True
            else:
                print("❌ cTrader cBot not running.")
                print("   → Start the DATA-Market (MarketDataProvider) cBot in cTrader on port 8010.")
                return False
        except requests.exceptions.ConnectionError:
            print("⏳ Waiting for cTrader on port 8010... cBot not reachable.")
            return False
        except Exception as e:
            print(f"❌ cTrader connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect (no-op for HTTP client)"""
        print("🔌 cTrader cBot disconnected")
        self.connected = False
    
    def get_historical_data(
        self, 
        symbol: str, 
        timeframe: str, 
        num_candles: int
    ) -> Optional[pd.DataFrame]:
        """
        Download historical candlestick data from cTrader
        
        Args:
            symbol: Trading symbol (e.g., 'GBPUSD')
            timeframe: 'M1', 'M5', 'M15', 'H1', 'H4', 'D1'
            num_candles: Number of candles to retrieve
            
        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        try:
            df = self.client.get_historical_data(symbol, timeframe, num_candles)
            
            if df is not None and not df.empty:
                # Rename index to 'time' column
                df = df.reset_index()
                # V30.8: logger in loc de print() -- print() aparea in setup_monitor.log cu emoji stricati
                try:
                    from loguru import logger as _lg
                    _lg.debug(f"Downloaded {len(df)} candles for {symbol} ({timeframe}) from IC Markets")
                except Exception as _log_err:
                    logger.debug(f"loguru unavailable in data provider: {_log_err}")
                return df
            else:
                try:
                    from loguru import logger as _lg
                    _lg.warning(f"No data for {symbol} on {timeframe}")
                except Exception as _log_err:
                    logger.debug(f"loguru unavailable in data provider: {_log_err}")
                
        except Exception as e:
            try:
                from loguru import logger as _lg
                _lg.error(f"Error downloading data for {symbol}: {e}")
            except Exception as _log_err:
                logger.debug(f"loguru unavailable in data provider: {_log_err}")
            return None


class DailyScanner:
    """Main scanner that runs daily at 00:05"""
    
    def __init__(self, use_ctrader: bool = True):
        # Choose data provider
        if use_ctrader:
            self.data_provider = CTraderDataProvider()
            print("📊 Using cTrader cBot for market data (IC Markets)")
        else:
            raise NotImplementedError(
                "MT5DataProvider nu mai este suportat. "
                "Folosește DailyScanner(use_ctrader=True) sau omite argumentul (default=True)."
            )
            
        # V10.1: Initialize SMCDetector — pure structural, no arbitrary ATR floors
        self.smc_detector = SMCDetector(
            swing_lookback=5,      # Standard swing validation (5 bars each side)
            atr_multiplier=0.5     # V24.5: era 1.2 (4x prea restrictiv) — aliniat cu practica SMC
        )
        print("✅ SMC Detector V10.2 initialized (ГЛИТЧ ИН МАТРИКС — VERSIUNEA FINALĂ):")
        print("   🎯 Entry: Marginea FVG în zona 70-80% Fibonacci pe impulsul 4H")
        print("   🛑 SL: Body close structural pur — ZERO floor, ZERO ATR buffer")
        print("   🏆 TP: Max/Min HH/LL din TOATĂ structura D1 — fără limită 60 zile")
        print("   📊 RR: Minim 1:4 structural — sub 1:4 = trade RESPINS")
        print("   👁️ MONITORING vizibil pe Telegram — chart trimis la orice setup (PÂNDĂ + READY)")
        print("   ❌ Method 2 Large Imbalance ELIMINAT — FVG pur 3 lumânări EXCLUSIV")
        print("   ⏱️ 4H CHoCH max 48 candle (8 zile) — setup-uri masive incluse")
        
        self.telegram = TelegramNotifier()
        
        # NEW: Load ML optimizer for setup scoring
        self.ml_optimizer = StrategyOptimizer()
        self.learned_rules = self._load_learned_rules()
        
        # NEW: Load AI Probability Analyzer (1-10 scoring)
        self.ai_analyzer = AIProbabilityAnalyzer()
        
        # Load pairs configuration
        with open('pairs_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            self.pairs = config['pairs']
            self.scanner_settings = config['scanner_settings']
    
    def _load_learned_rules(self) -> dict:
        """Load learned rules from ML optimizer"""
        try:
            with open('learned_rules.json', 'r', encoding='utf-8') as f:
                rules = json.load(f)
                print(f"✅ Loaded learned rules (analyzed {rules['total_trades_analyzed']} trades)")
                return rules
        except FileNotFoundError:
            print("⚠️  No learned_rules.json found - run strategy_optimizer.py first")
            return {}
        except Exception as e:
            print(f"⚠️  Error loading learned rules: {e}")
            return {}
    
    def _calculate_ml_score(self, setup: TradeSetup, df_4h: pd.DataFrame) -> dict:
        """
        Calculate ML confidence score for a setup
        Uses learned_rules.json to score based on historical performance
        """
        if not self.learned_rules:
            return {
                'score': 50,
                'confidence': 'UNKNOWN',
                'recommendation': 'REVIEW',
                'factors': {'ml_status': 'No learned rules available'}
            }
        
        # Extract setup details
        current_hour = datetime.now().hour
        
        # Determine timeframe (from setup or default to 4H)
        timeframe = '4H'  # Default since we use 4H confirmation
        
        # Determine pattern type from setup
        pattern = 'UNKNOWN'
        if hasattr(setup, 'strategy_type') and setup.strategy_type:
            pattern = setup.strategy_type.upper()
        
        # Build setup dict for ML optimizer
        setup_data = {
            'symbol': setup.symbol,
            'timeframe': timeframe,
            'hour': current_hour,
            'pattern': pattern
        }
        
        # Use ML optimizer to calculate score
        return self.ml_optimizer.calculate_setup_score(setup_data)
    
    def run_daily_scan(self, keep_connection: bool = False) -> List[TradeSetup]:
        """
        Main scan function - runs through all pairs
        Returns list of valid setups found
        
        Args:
            keep_connection: If True, don't disconnect MT5 after scan (for auto-trader)
        """
        print("\n" + "="*60)
        print("🔥 ForexGod - Glitch Daily Scanner Starting... [V37.15 DYNAMIC REVERSAL + V40.3]")
        print(f"⏰ Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60 + "\n")

        # V39.1: /resume — nu bloca scanul daca deep_sleep ramane pe disk
        if _clear_deep_sleep_on_resume():
            print("🔱 [V39.1] Post-resume scan — daily loss bypass activ (PnL anchor resetat de /resume)")
        
        # ✅ V14.4 RETRY: 3 încercări la 30s — cTrader poate fi lent la start VPS
        connected = False
        for _attempt in range(1, 4):
            if self.data_provider.connect():
                connected = True
                break
            print(f"⏳ [Attempt {_attempt}/3] cTrader nu răspunde pe port 8010 — retry în 30s...")
            time.sleep(30)

        if not connected:
            error_msg = "Failed to connect to cTrader cBot API (localhost:8010) după 3 încercări (90s)"
            print(f"❌ {error_msg}")
            # V24.5 FIX: Trimitem alert Telegram imediat — mesaj explicit cu instrucțiuni VPS
            try:
                self.telegram.send_message(
                    "⚠️ <b>ФорексГод.АИ</b>\n"
                    "❌ <b>SCAN EȘUAT — cTrader OFFLINE</b>\n"
                    "────────────────\n"
                    "🔌 Port 8010 nu răspunde pe VPS!\n"
                    "\n"
                    "<b>Acțiune necesară:</b>\n"
                    "1. Deschide cTrader pe VPS\n"
                    "2. Pornește cBot-ul <code>MarketDataProvider</code>\n"
                    "3. Rulează manual: <code>python daily_scanner.py</code>\n"
                    "────────────────\n"
                    "🏛 <b>ГЛИТЧ ИН МАТРИКС</b> 🏛"
                )
            except Exception as _tg_err:
                logger.warning(f"Telegram alert failed during cBot connection error: {_tg_err}")
            # V24.5 FIX: Ridicăm excepție în loc să returnăm [] silențios.
            # Aceasta face ca subprocess.run() din auto_scanner_daemon.py să vadă
            # exit code 1 (nu 0) și să trimită corect alertul de eroare.
            raise RuntimeError(error_msg)
        
        setups_found = []
        bias_fallback_entries = []  # V31.0: Bias-only entries colectate pentru WIPE final
        daily_bias_map = {}  # V40: D1 bias per symbol pentru invalidare setup-uri stale
        w1_bias_map = {}  # V40.3: W1 macro bias informativ (confidence flag)
        symbol_price_map = {}  # V40.3: preț D1 close per simbol — soft TTL POI
        symbol_df_daily_map: Dict[str, pd.DataFrame] = {}  # V43.1: post-TP evolution

        # V3.0: Load existing monitoring setups to re-evaluate their status
        monitoring_symbols = set()
        existing_setups_by_symbol: Dict[str, dict] = {}
        try:
            with open('monitoring_setups.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # V8.0 FAILSAFE: Handle both formats (dict with 'setups' key or direct list)
                if isinstance(data, dict):
                    existing_setups = data.get("setups", [])
                elif isinstance(data, list):
                    # Old format: direct array - convert to dict format
                    existing_setups = data
                    print(f"⚠️  WARNING: monitoring_setups.json in old format (list). Converting...")
                else:
                    print(f"⚠️  WARNING: monitoring_setups.json has invalid format. Skipping...")
                    existing_setups = []
                
                monitoring_symbols = {s['symbol'] for s in existing_setups if isinstance(s, dict) and s.get('status') == 'MONITORING'}
                existing_setups_by_symbol = {
                    s['symbol']: s for s in existing_setups
                    if isinstance(s, dict) and s.get('symbol')
                }
                if monitoring_symbols:
                    print(f"\n🔄 Re-evaluating {len(monitoring_symbols)} MONITORING setups: {', '.join(monitoring_symbols)}")
        except FileNotFoundError:
            existing_setups_by_symbol = {}
            pass
        except json.JSONDecodeError as e:
            print(f"⚠️  ERROR: monitoring_setups.json is corrupted: {e}")
            existing_setups_by_symbol = {}
            pass
        
        try:
            # Scan each pair
            for pair_config in self.pairs:
                symbol = pair_config['mt5_symbol']
                priority = pair_config['priority']
                
                # Check if this symbol is in monitoring (needs re-evaluation)
                is_monitoring = symbol in monitoring_symbols
                scan_reason = "Re-evaluating MONITORING" if is_monitoring else f"Priority {priority}"
                
                print(f"\n🔍 Scanning {symbol} ({scan_reason})...")
                
                # Download Daily data — V44.2: min 250 bare (~1 an), prefer config (365 în pairs_config)
                _d1_lookback = max(
                    250,
                    int(self.scanner_settings.get('lookback_candles', {}).get('daily', 250)),
                )
                df_daily = self.data_provider.get_historical_data(
                    symbol,
                    "D1",
                    _d1_lookback,
                )
                
                if df_daily is None or df_daily.empty:
                    print(f"⚠️  Skipping {symbol} - no Daily data")
                    # 🚨 AUDIT: Log data errors for forensics
                    try:
                        with open('data_errors.log', 'a', encoding='utf-8') as f:
                            f.write(f"{datetime.now().isoformat()} - {symbol} - D1 data unavailable\n")
                    except Exception as log_err:
                        print(f"⚠️  Could not write to data_errors.log: {log_err}")
                    continue
                
                symbol_price_map[symbol] = float(df_daily['close'].iloc[-1])
                symbol_df_daily_map[symbol] = df_daily

                # Download 4H data
                df_4h = self.data_provider.get_historical_data(
                    symbol, 
                    "H4", 
                    self.scanner_settings['lookback_candles']['h4']
                )
                
                if df_4h is None:
                    print(f"⚠️ Skipping {symbol} - no 4H data")
                    continue

                # V40: înregistrăm bias D1 înainte de scan — folosit la SMART MERGE invalidare
                try:
                    daily_bias_map[symbol] = self.smc_detector.determine_daily_trend(df_daily, symbol=symbol)
                except Exception as _dbm_err:
                    daily_bias_map[symbol] = 'neutral'
                    print(f"   ⚠️ [V40] bias map error {symbol}: {_dbm_err}")
                
                # V40.3: W1 = macro anchor informativ (confidence flag, fără reject)
                print(f"   📅 Downloading W1 data (Weekly Anchor — 52 bars, ~1 an)...")
                df_w1 = None
                w1_poi = None
                w1_result = {'bias': 'NEUTRAL', 'last_bos_direction': None, 'last_bos_price': None, 'last_bos_bar_idx': None}
                try:
                    df_w1 = self.data_provider.get_historical_data(symbol, "W1", 52)  # V31.0
                    if df_w1 is not None:
                        print(f"   ✅ W1 data: {len(df_w1)} bars")
                        w1_result = self.smc_detector.calculate_w1_bias(df_w1)
                        w1_bias_map[symbol] = w1_result.get('bias', 'NEUTRAL')
                        w1_poi = self.smc_detector.resolve_w1_poi(
                            df_w1, w1_result.get('bias', 'NEUTRAL'),
                        )
                    else:
                        print(f"   ⚠️ W1 data unavailable for {symbol} — bias = NEUTRAL")
                        w1_bias_map[symbol] = 'NEUTRAL'
                except Exception as w1_err:
                    print(f"   ⚠️ W1 fetch error for {symbol}: {w1_err} — continuing")
                    w1_bias_map[symbol] = 'NEUTRAL'
                
                # V8.0: Run SMC detection with ATR + Premium/Discount filters
                # These filters may reject setups:
                # - ATR Filter: Eliminates micro-swings (not prominent enough)
                # - Premium/Discount: Rejects shallow retracements (<50%)
                try:
                    _stored = existing_setups_by_symbol.get(symbol, {})
                    setup = self.smc_detector.scan_for_setup(
                        symbol=symbol,
                        df_daily=df_daily,
                        df_4h=df_4h,
                        priority=priority,
                        debug=True,    # ✅ V10.6: verbose reject messages
                        stored_poi_top=_stored.get('poi_top') if _stored.get('poi_top') is not None else _stored.get('fvg_top'),
                        stored_poi_bottom=_stored.get('poi_bottom') if _stored.get('poi_bottom') is not None else _stored.get('fvg_bottom'),
                    )
                except Exception as scan_error:
                    print(f"⚠️  Error scanning {symbol}: {scan_error}")
                    # Log error but continue to next pair
                    try:
                        with open('scanner_errors.log', 'a', encoding='utf-8') as f:
                            f.write(f"{datetime.now().isoformat()} - {symbol} - {scan_error}\n")
                    except Exception as _log_w_err:
                        logger.warning(f"Could not write scanner_errors.log for {symbol}: {_log_w_err}")
                    setup = None
                
                if setup:
                    # ━━━ V13.0 SNIPER ALIGNMENT FILTER ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # FLUX CORECT:
                    #   D1 Bearish + preț în FVG Daily → așteptăm CHoCH BEARISH pe 4H
                    #   → 4H CHoCH bearish = aliniere cu D1 → VALID SELL ✅
                    #   → 4H CHoCH bullish = contrar D1 → RESPINS ❌
                    #
                    # D1 stabilește DIRECȚIA. 4H confirmă ENTRY-UL în aceeași direcție.
                    # Un CHoCH bullish pe 4H într-un D1 bearish = retracement intern, nu setup.
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    d1_direction = setup.daily_choch.direction if hasattr(setup, 'daily_choch') and setup.daily_choch else None
                    h4_direction = setup.h4_choch.direction if hasattr(setup, 'h4_choch') and setup.h4_choch else None

                    if d1_direction and h4_direction and h4_direction != d1_direction:
                        # ✅ V13.1 FIX: 4H CHoCH opus D1 = PULLBACK activ, NU anulăm setup-ul!
                        # Ex: D1 bearish + H4 CHoCH bullish = bounce/pullback normal.
                        # Păstrăm setup-ul ca MONITORING și așteptăm CHoCH H4 în direcția D1.
                        # (V13.0 vechi: anula complet → pierdea setup-uri perfecte de sell/buy)
                        h4_label = "SELL" if h4_direction == 'bearish' else "BUY"
                        d1_label  = "SELL" if d1_direction == 'bearish' else "BUY"
                        print(f"⏳ [V13.1 PULLBACK ACTIV] {symbol}: 4H CHoCH={h4_label} (pullback) în D1={d1_label} — "
                              f"Setup MONITORING: așteptăm CHoCH {d1_label} pe 4H din FVG Daily.")
                        # Marchează H4 CHoCH ca pullback și resetează la None — radar va detecta CHoCH-ul corect
                        setup.h4_choch = None
                        setup.status = 'MONITORING'
                    elif d1_direction and h4_direction and h4_direction == d1_direction:
                        d1_label = "SELL" if d1_direction == 'bearish' else "BUY"
                        print(f"✅ [V13.0 SNIPER ALIGNED] {symbol}: 4H CHoCH {h4_direction.upper()} = aliniat cu D1 {d1_direction.upper()} → {d1_label} valid")
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    # Faza 2: W+D soft sync gate (W1 POI + anti-counter-trend)
                    _live_px = symbol_price_map.get(symbol)
                    setup = self.smc_detector.apply_w_d_sync_gate(
                        setup,
                        w1_bias_map.get(symbol, 'NEUTRAL'),
                        w1_poi=w1_poi,
                        current_price=_live_px,
                    )

                if setup:
                    # V10.1: Display strategy type immediately
                    strategy = setup.strategy_type.upper() if hasattr(setup, 'strategy_type') else "UNKNOWN"
                    strategy_emoji = "🔄" if strategy == "REVERSAL" else "➡️"
                    print(f"🎯 SETUP FOUND on {symbol}! {strategy_emoji} {strategy}")
                    
                    # NEW: ML SCORING - Calculate AI confidence score (0-100)
                    ml_score = self._calculate_ml_score(setup, df_4h)
                    setup.ml_score = ml_score['score']
                    setup.ml_confidence = ml_score['confidence']
                    setup.ml_recommendation = ml_score['recommendation']
                    setup.ml_factors = ml_score['factors']
                    
                    # NEW: AI PROBABILITY SCORING (1-10 scale)
                    ai_prob = self.ai_analyzer.calculate_probability_score(
                        symbol=symbol,
                        timeframe='4H',
                        hour=datetime.now().hour,
                        pattern=setup.strategy_type if hasattr(setup, 'strategy_type') else None
                    )
                    setup.ai_probability_score = ai_prob['score']
                    setup.ai_probability_confidence = ai_prob['confidence']
                    setup.ai_probability_factors = ai_prob['factors']
                    setup.ai_probability_warning = ai_prob['warning']
                    
                    # Print ML analysis
                    score_emoji = "🟢" if ml_score['score'] >= 75 else "🟡" if ml_score['score'] >= 60 else "🔴"
                    print(f"   {score_emoji} ML SCORE: {ml_score['score']}/100 ({ml_score['confidence']})")
                    print(f"   🤖 AI Recommendation: {ml_score['recommendation']}")
                    for factor, desc in ml_score['factors'].items():
                        print(f"      • {factor}: {desc}")
                    
                    # Print AI Probability analysis
                    prob_emoji = "🟢" if ai_prob['score'] >= 7 else "🟡" if ai_prob['score'] >= 5 else "🔴"
                    print(f"   {prob_emoji} AI PROBABILITY: {ai_prob['score']}/10 ({ai_prob['confidence']})")
                    if ai_prob['warning']:
                        print(f"   {ai_prob['warning']}")
                    
                    setups_found.append(setup)

                    # V40.3: W1 context informativ pe setup
                    try:
                        setup.w1_bias = w1_result.get('bias', 'NEUTRAL')
                        setup.w1_last_bos_price = w1_result.get('last_bos_price')
                        d1_dir = setup.daily_choch.direction
                        w1_bias_lower = (w1_result.get('bias') or 'NEUTRAL').lower()
                        if w1_bias_lower != 'neutral' and w1_bias_lower != d1_dir:
                            print(
                                f"   ⚠️ [V40.3 W1 INFO] {symbol}: D1={d1_dir.upper()} vs W1={w1_result['bias']} "
                                f"— ⚠️ [COUNTER-TREND W1] (confidence={getattr(setup, 'confidence', 'LOW_W1_COUNTER_TREND')})"
                            )
                        else:
                            align_label = "ALINIAT" if w1_bias_lower == d1_dir else "NEUTRAL"
                            print(f"   📅 [W1 INFO] {symbol}: {w1_result['bias']} — {align_label} cu D1")
                    except Exception as w1_bias_err:
                        setup.w1_bias = 'NEUTRAL'
                        setup.w1_last_bos_price = None
                        print(f"   ⚠️ W1 bias attach error: {w1_bias_err}")

                    # ✅ V24.6 DAILY LIQUIDITY TARGET: D1 Swing High/Low SEMNIFICATIV
                    # LONG: nearest Swing High deasupra prețului curent = TP Lichiditate
                    # SHORT: nearest Swing Low sub prețul curent = TP Lichiditate
                    # V24.6 ATR FILTER: swing-ul țintă trebuie să fie minim 1x ATR Daily
                    # față de entry — eliminăm micro-pivoții / inside bars ca țintă.
                    try:
                        _current_px = float(df_daily['close'].iloc[-1])
                        _d1_dir = setup.daily_choch.direction  # 'bullish' / 'bearish'
                        # Calculăm ATR Daily (14 bare) pentru filtrul de distanță minimă
                        _tr = pd.concat([
                            df_daily['high'] - df_daily['low'],
                            (df_daily['high'] - df_daily['close'].shift(1)).abs(),
                            (df_daily['low']  - df_daily['close'].shift(1)).abs()
                        ], axis=1).max(axis=1)
                        _atr_daily = float(_tr.rolling(14).mean().iloc[-1])
                        _min_tp_dist = _atr_daily * 1.0  # minim 1x ATR față de entry
                        _entry_ref = setup.entry_price if setup.entry_price else _current_px
                        _pip_sz = get_pip_size(symbol)
                        _sweep_tol = _pip_sz * 10
                        _sweep_lb = 25 if any(x in symbol.upper() for x in ['BTC', 'ETH']) else 15
                        if _d1_dir == 'bullish':
                            _swings = self.smc_detector.detect_swing_highs(df_daily)
                            _targets = [
                                s for s in _swings
                                if s.price > _current_px
                                and (s.price - _entry_ref) >= _min_tp_dist
                                and not liquidity_already_swept(
                                    df_daily, s.price, 'high',
                                    lookback=_sweep_lb, tolerance=_sweep_tol,
                                )
                            ]
                            _daily_tp = min(_targets, key=lambda s: s.price).price if _targets else None
                        else:
                            _swings = self.smc_detector.detect_swing_lows(df_daily)
                            _targets = [
                                s for s in _swings
                                if s.price < _current_px
                                and (_entry_ref - s.price) >= _min_tp_dist
                                and not liquidity_already_swept(
                                    df_daily, s.price, 'low',
                                    lookback=_sweep_lb, tolerance=_sweep_tol,
                                )
                            ]
                            _daily_tp = max(_targets, key=lambda s: s.price).price if _targets else None
                        setup.daily_tp_price = float(_daily_tp) if _daily_tp else None
                        if setup.daily_tp_price:
                            _tp_dist_pips = abs(setup.daily_tp_price - _entry_ref) / _pip_sz
                            print(f"   🎯 [V37.7 D1 TP] {symbol} {_d1_dir.upper()}: Target D1 = {setup.daily_tp_price:.5f} ({_tp_dist_pips:.0f}p | sweep-uit exclus | ATR={_atr_daily/_pip_sz:.0f}p)")
                        else:
                            print(f"   ⚠️ [V37.7 D1 TP] {symbol}: Niciun swing D1 valid (lichiditate sweep-uita sau < 1x ATR)")
                            setup.daily_tp_price = None
                    except Exception as _dtp_err:
                        setup.daily_tp_price = None
                        print(f"   ⚠️ [V24.6 D1 TP] Eroare calcul daily_tp_price: {_dtp_err}")

                    # ✅ V35 T2: Pivoti structurali D1 pentru Poarta 1 (Gate 1 - Invalidare Structurala)
                    # daily_swing_low  (LONG) : cel mai adanc swing low sub pret  = baza structurala D1
                    # daily_swing_high (SHORT): cel mai inalt swing high deasupra  = plafonul structural D1
                    # Poarta 1 in _apply_lifecycle_gates() marcheaza INVALIDATED daca:
                    #   LONG:  close < daily_swing_low  (baza sparta -> structura bullish invalida)
                    #   SHORT: close > daily_swing_high (plafonul spart -> structura bearish invalida)
                    try:
                        _gate1_dir = setup.daily_choch.direction  # 'bullish' / 'bearish'
                        _gate1_px  = float(df_daily['close'].iloc[-1])
                        if _gate1_dir == 'bullish':
                            _gate1_lows  = self.smc_detector.detect_swing_lows(df_daily)
                            _gate1_below = [s for s in _gate1_lows if s.price < _gate1_px]
                            setup.daily_swing_low  = float(min(_gate1_below, key=lambda s: s.price).price) if _gate1_below else None
                            setup.daily_swing_high = None
                            if setup.daily_swing_low:
                                print(f"   🏛️  [V35 GATE1] {symbol} LONG: baza structurala D1 = {setup.daily_swing_low:.5f}")
                        else:
                            _gate1_highs = self.smc_detector.detect_swing_highs(df_daily)
                            _gate1_above = [s for s in _gate1_highs if s.price > _gate1_px]
                            setup.daily_swing_high = float(max(_gate1_above, key=lambda s: s.price).price) if _gate1_above else None
                            setup.daily_swing_low  = None
                            if setup.daily_swing_high:
                                print(f"   🏛️  [V35 GATE1] {symbol} SHORT: plafon structural D1 = {setup.daily_swing_high:.5f}")
                    except Exception as _gate1_err:
                        setup.daily_swing_low  = None
                        setup.daily_swing_high = None

                    # ✅ V10.9 CARRY MATRIX: Fetch live swap rates and attach to setup
                    try:
                        swap_info = self.data_provider.client.get_swap_info(symbol)
                        if swap_info.get('success'):
                            setup.swap_long        = swap_info['swap_long']
                            setup.swap_short       = swap_info['swap_short']
                            setup.swap_triple_day  = swap_info['swap_triple_day']
                            direction_str_swap = "buy" if setup.daily_choch.direction == 'bullish' else "sell"
                            relevant_swap = setup.swap_long if direction_str_swap == 'buy' else setup.swap_short
                            swap_label = "✅ POZITIV (credit)" if relevant_swap > 0 else "⚠️ NEGATIV (cost)"
                            print(f"   💱 CARRY: long={setup.swap_long:+.4f} short={setup.swap_short:+.4f} triple={setup.swap_triple_day} → {swap_label}")
                        else:
                            setup.swap_long = setup.swap_short = setup.swap_triple_day = None
                            print(f"   💱 CARRY: N/A (cTrader offline)")
                    except Exception as swap_ex:
                        setup.swap_long = setup.swap_short = setup.swap_triple_day = None
                        print(f"   💱 CARRY: eroare fetch swap — {swap_ex}")
                    
                    # V10.2: Log structural validation status
                    direction_str = "LONG" if setup.daily_choch.direction == 'bullish' else "SHORT"
                    setup_status = getattr(setup, 'status', 'MONITORING')
                    entry_str = f"{setup.entry_price:.5f}" if setup.entry_price else "N/A"
                    sl_str = f"{setup.stop_loss:.5f}" if setup.stop_loss else "N/A"
                    tp_str = f"{setup.take_profit:.5f}" if setup.take_profit else "N/A"
                    rr_str = f"1:{setup.risk_reward:.2f}" if setup.risk_reward else "N/A"
                    status_emoji = "🔥 READY" if setup_status == "READY" else "👁️ PÂNDĂ"
                    print(f"   ✅ [V10.2 STRUCTURAL PASS] {symbol} {direction_str}:")
                    print(f"      • Status: {status_emoji}")
                    print(f"      • Entry (FVG Edge 70-80% Fib): {entry_str}")
                    print(f"      • SL (4H Body Close): {sl_str}")
                    print(f"      • TP (D1 Structural Max): {tp_str}")
                    print(f"      • RR: {rr_str}")
                    
                    # V10.2: RAPORTARE FORȜATĂ MONITORING
                    # V15.1 DEDUP: alertă Telegram doar setup NOU sau READY (nu re-evaluate MONITORING)
                    if self.scanner_settings.get('telegram_alerts', True):
                        is_reevaluation = symbol in monitoring_symbols
                        send_telegram_card = (not is_reevaluation) or setup_status == 'READY'
                        if setup_status == 'READY':
                            tg_prefix = "🔥 READY TO EXECUTE"
                        else:
                            tg_prefix = "👁️ MONITORING (PÂNDĂ)"

                        if send_telegram_card:
                            print(f"   📸 {tg_prefix} — Generez chart pentru {symbol}...")
                            try:
                                setup.live_price = symbol_price_map.get(symbol)
                                setup.live_price_source = 'ctrader_d1_close'
                                _radar_snap = (
                                    existing_setups_by_symbol.get(symbol, {})
                                    if setup_status == 'READY'
                                    else {}
                                )
                                self.telegram.send_setup_alert(
                                    setup=setup,
                                    df_daily=df_daily,
                                    df_4h=df_4h,
                                    charts_mode='daily_only',  # V43.9: info-only — no manual Execute/Skip buttons
                                    radar_snapshot=_radar_snap,
                                )
                                print(f"   ✅ Chart trimis pe Telegram: {symbol} [{tg_prefix}] [DAILY ONLY]")
                            except Exception as e:
                                print(f"   ⚠️ Failed to send charts: {e}")
                        elif is_reevaluation:
                            print(f"   ⏭️ [V15.1 DEDUP] {symbol}: re-evaluat MONITORING — skip card Telegram (radar LTF activ)")
                    
                    print(f"✓ {symbol} adăugat în raportul de dimineață [{setup_status}]")
                else:
                    # V10.2: Setup respins — motivul exact a fost printat de smc_detector
                    # ── V31.0 BIAS FALLBACK ──────────────────────────────────────────────────
                    # Nu mai scriem direct în JSON. Colectăm în bias_fallback_entries[].
                    # save_monitoring_setups() face WIPE&OVERWRITE la final cu tot.
                    try:
                        _bias_dir = self.smc_detector.determine_daily_trend(df_daily, symbol=symbol)
                        if _bias_dir not in ('bullish', 'bearish'):
                            _bias_dir = self.smc_detector.macro_trend_from_swings(df_daily)
                        if _bias_dir not in ('bullish', 'bearish'):
                            _sh = self.smc_detector.detect_swing_highs(df_daily)
                            _sl = self.smc_detector.detect_swing_lows(df_daily)
                            _ch, _bo = self.smc_detector.detect_choch_and_bos(df_daily)
                            _rs = self.smc_detector.compute_structural_range(
                                df_daily, _sh, _sl, symbol=symbol,
                            )
                            _ch, _bo, _rs = self.smc_detector.filter_internal_range_signals(
                                symbol, df_daily, _ch, _bo, _rs,
                            )
                            _bias_dir = self.smc_detector.resolve_structural_bias_fallback(
                                df_daily, _ch, _bo, _rs,
                            )
                        if _bias_dir in ('bullish', 'bearish'):
                            _w1 = w1_bias_map.get(symbol, 'NEUTRAL')
                            _bias_trade_dir = 'buy' if _bias_dir == 'bullish' else 'sell'
                            _bf_status = 'WAITING_D1_PULLBACK'
                            _bf_w_d_aligned = True
                            _bf_confidence = 'NORMAL'
                            if _w1 == 'BEARISH' and _bias_dir == 'bullish':
                                _bf_status = 'WAITING_W_D_SYNC'
                                _bf_w_d_aligned = False
                                _bf_confidence = 'LOW_W1_COUNTER_TREND'
                                print(
                                    f"⏸️ [W+D SOFT SYNC] {symbol}: bias fallback LONG vs W1 BEARISH — "
                                    f"status=WAITING_W_D_SYNC (monitor only)"
                                )
                            elif _w1 == 'BULLISH' and _bias_dir == 'bearish':
                                _bf_status = 'WAITING_W_D_SYNC'
                                _bf_w_d_aligned = False
                                _bf_confidence = 'LOW_W1_COUNTER_TREND'
                                print(
                                    f"⏸️ [W+D SOFT SYNC] {symbol}: bias fallback SHORT vs W1 BULLISH — "
                                    f"status=WAITING_W_D_SYNC (monitor only)"
                                )
                            # V37.15: strategy din semnal D1 real (CHoCH/BOS), nu hardcod continuation
                            _bf_strategy, _bf_sig = self.smc_detector.infer_d1_strategy_type(
                                df_daily, symbol=symbol
                            )
                            _bf_setup_type = _bf_strategy.upper()
                            print(
                                f"📡 [V31.0 BIAS FALLBACK] {symbol}: bias={_bias_dir.upper()} "
                                f"→ {_bf_sig}/{_bf_strategy.upper()} {_bf_status}"
                            )
                            _bf_entry = {
                                'symbol': symbol,
                                'direction': _bias_trade_dir,
                                'd1_bias_direction': _bias_dir,
                                'daily_bias': _bias_dir.upper(),
                                'setup_type': _bf_setup_type,
                                'strategy_type': _bf_strategy,
                                'strategy_locked': True,
                                'daily_bias_active': True,
                                'confidence': _bf_confidence,
                                'w1_bias': _w1,
                                'w_d_aligned': _bf_w_d_aligned,
                                'w1_poi_top': w1_poi.get('w1_poi_top') if w1_poi else None,
                                'w1_poi_bottom': w1_poi.get('w1_poi_bottom') if w1_poi else None,
                                'poi_top': None,
                                'poi_bottom': None,
                                'fvg_top': None,
                                'fvg_bottom': None,
                                'daily_target_price': None,
                                'status': _bf_status,
                                'setup_time': datetime.now().isoformat(),
                                'bias_fallback': True,
                            }
                            bias_fallback_entries.append(
                                _hydrate_bias_fallback_poi(self.smc_detector, _bf_entry, df_daily)
                            )
                            print(f"   ✅ [V31.0] {symbol} {_bias_trade_dir.upper()} → bias_fallback_entries ({len(bias_fallback_entries)} total)")
                        else:
                            print(f"⛔ {symbol} — NO SETUP + BIAS NEUTRAL [V10.2 REJECT: vezi log-ul ↑]")
                    except Exception as _bf_err:
                        print(f"⛔ {symbol} — NO SETUP [V10.2 REJECT: vezi log-ul ↑] | bias fallback error: {_bf_err}")

                # V44.2: pauză scurtă — cBot main thread (radar + scanner simultan → HTTP 500 Timeout)
                time.sleep(0.25)
        
        finally:
            # Disconnect cTrader unless keep_connection=True
            if not keep_connection:
                self.data_provider.disconnect()
        
        # Load monitoring setups + check for recently executed setups still in open positions
        monitoring_setups = []
        try:
            with open('monitoring_setups.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # V8.0 FAILSAFE: Handle both formats
                if isinstance(data, dict):
                    monitoring_setups = data.get("setups", [])
                elif isinstance(data, list):
                    monitoring_setups = data
                else:
                    monitoring_setups = []
        except FileNotFoundError:
            pass  # No existing file
        except json.JSONDecodeError:
            print(f"⚠️  WARNING: monitoring_setups.json corrupted. Skipping...")
            pass
        
        # Include ALL open positions from trade_history.json as active setups
        all_open_positions = []
        open_position_symbols = set()  # Track which symbols have open positions
        try:
            with open('trade_history.json', 'r', encoding='utf-8') as f:
                trade_data = json.load(f)
                all_open_positions = trade_data.get('open_positions', [])
                # V8.2: If IGNORE_OPEN_POSITIONS is True, treat as if no positions exist
                if not IGNORE_OPEN_POSITIONS:
                    open_position_symbols = {p.get('symbol') for p in all_open_positions}
                    logger.info(f"📊 Found {len(all_open_positions)} open positions: {[p.get('symbol') for p in all_open_positions]}")
                else:
                    logger.info(f"⚠️  AUDIT MODE: Ignoring {len(all_open_positions)} open positions for full analysis")
        except Exception as e:
            logger.debug(f"Could not check open positions: {e}")
        
        # V11.0 FIX: Build open position direction map {symbol: 'buy'/'sell'}
        open_position_direction = {}
        for p in all_open_positions:
            sym = p.get('symbol')
            direction = (p.get('direction') or '').lower()  # 'SELL' → 'sell'
            if sym:
                open_position_direction[sym] = direction

        # FILTER: Remove setups that CONFLICT with open positions (opposite direction)
        # A new BUY setup must NOT override an existing SELL position and vice-versa
        filtered_setups = []
        skipped_conflict = []
        for s in setups_found:
            setup_dir = "buy" if s.daily_choch.direction == "bullish" else "sell"
            open_dir = open_position_direction.get(s.symbol)
            if open_dir and open_dir != setup_dir:
                # CONFLICT: scanner found opposite direction to open position
                logger.warning(
                    f"⛔ CONFLICT GUARD: {s.symbol} scanner→{setup_dir.upper()} "
                    f"but open position is {open_dir.upper()} — skipping this setup"
                )
                skipped_conflict.append(s.symbol)
            else:
                filtered_setups.append(s)

        if skipped_conflict:
            print(f"\n⛔ CONFLICT GUARD: Skipped {skipped_conflict} — opposite direction to open positions")

        # Use filtered setups (no conflicts with open positions)
        all_active_setups = filtered_setups

        # V15.2 Option A: Breakdown corect — brand_new vs re_evaluated (era deja in monitoring)
        brand_new_setups   = [s for s in all_active_setups if s.symbol not in monitoring_symbols]
        re_evaluated_setups = [s for s in all_active_setups if s.symbol in monitoring_symbols]

        # SAVE first, then show final summary — V31.0: WIPE + bias fallback
        save_result = save_monitoring_setups(
            all_active_setups,
            bias_fallback_entries,
            daily_bias_map,
            w1_bias_map,
            symbol_price_map,
            symbol_df_daily_map=symbol_df_daily_map,
            smc_detector=self.smc_detector,
        )
        persist_missing = _audit_scan_persistence(
            all_active_setups,
            bias_fallback_entries,
            save_result.get('saved_symbols', []),
            save_result.get('skipped', {}),
        )

        # Now reload to get accurate count
        final_monitoring_count = save_result.get('total', 0)
        watching_count = 0
        _WATCHING_STATUSES = frozenset({
            'MONITORING', 'READY', 'WAITING_D1_PULLBACK',
            'WAITING_4H_CHOCH', 'WAITING_4H_PULLBACK',
            'WAITING_W_D_SYNC', 'WAITING_W_ZONE', 'WAITING_POSITION_CLOSE',
        })
        try:
            with open('monitoring_setups.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _setups_list = data.get("setups", [])
                    final_monitoring_count = len(_setups_list)
                    watching_count = sum(
                        1 for s in _setups_list if s.get('status') in _WATCHING_STATUSES
                    )
                elif isinstance(data, list):
                    final_monitoring_count = len(data)
                    watching_count = sum(
                        1 for s in data if s.get('status') in _WATCHING_STATUSES
                    )
        except Exception as _cnt_err:
            logger.warning(f"[V37.0] Could not read final monitoring count: {_cnt_err}")
        
        # Send daily summary AFTER saving
        print("\n" + "="*60)
        print(f"✅ Scan Complete!")
        print(f"📊 Total Pairs Scanned: {len(self.pairs)}")
        print(f"🆕 New Setups Found: {len(setups_found)}")
        print(f"    └─ Brand New (never in monitoring): {len(brand_new_setups)}")
        print(f"    └─ Re-evaluated (already in monitoring): {len(re_evaluated_setups)}")
        print(f"📋 Total Active Tracking:")
        print(f"    └─ Saved in Monitoring: {final_monitoring_count}")
        print(f"    └─ Open Positions: {len(all_open_positions)}")
        print("="*60 + "\n")

        if self.scanner_settings['telegram_alerts']:
            # ━━━ V10.1 SCAN REPORT — The Official Stamp ━━━
            # Anti-flood: wait 2s after last chart before sending final report
            time.sleep(2)
            
            # Check Deep Sleep status from disk state file
            deep_sleep_active = False
            deep_sleep_until_str = None
            try:
                ds_file = os.path.join('data', 'deep_sleep_state.json')
                if os.path.exists(ds_file):
                    with open(ds_file, 'r', encoding='utf-8') as f:
                        ds_state = json.load(f)
                    wake_str = ds_state.get('wake_time')
                    if wake_str:
                        from datetime import timezone
                        wake_time = datetime.fromisoformat(wake_str)
                        if wake_time > datetime.now(timezone.utc):
                            deep_sleep_active = True
                            deep_sleep_until_str = wake_time.strftime('%Y-%m-%d %H:%M UTC')  # UTC intentionat (stored as UTC)
            except Exception as e:
                logger.debug(f"Could not check Deep Sleep state: {e}")
            
            # Build setup symbols from JSON (inventar real) + fallback scan-only pentru nesalvate
            setup_symbols = []
            _json_syms = set()
            try:
                with open('monitoring_setups.json', 'r', encoding='utf-8') as _jf:
                    _jdata = json.load(_jf)
                _jlist = _jdata.get('setups', []) if isinstance(_jdata, dict) else _jdata
                for row in _jlist:
                    if not isinstance(row, dict):
                        continue
                    sym = row.get('symbol')
                    if not sym:
                        continue
                    _json_syms.add(sym)
                    setup_symbols.append({
                        'symbol': sym,
                        'direction': row.get('direction', 'buy'),
                        'strategy': (row.get('strategy_type') or 'CONTINUATION').upper(),
                        'h4_structure_locked': row.get('h4_structure_locked', False),
                        'bias_fallback': bool(row.get('bias_fallback')),
                        'status': row.get('status', 'MONITORING'),
                        'w_d_aligned': row.get('w_d_aligned', True),
                    })
            except Exception as _js_err:
                logger.warning(f"[V59] Could not build report from JSON: {_js_err}")
                _json_syms = set()
                for s in setups_found:
                    direction_str = "buy" if s.daily_choch.direction == 'bullish' else "sell"
                    setup_symbols.append({
                        'symbol': s.symbol,
                        'direction': direction_str,
                        'strategy': getattr(s, 'strategy_type', 'UNKNOWN').upper(),
                        'h4_structure_locked': getattr(s, 'h4_structure_locked', False),
                        'bias_fallback': False,
                        'status': getattr(s, 'status', 'MONITORING'),
                        'w_d_aligned': getattr(s, 'w_d_aligned', True),
                    })
                    _json_syms.add(s.symbol)

            # Send the OFFICIAL scan report (mirrors console exactly)
            try:
                self.telegram.send_scan_report(
                    total_pairs=len(self.pairs),
                    new_setups_found=len(setups_found),
                    truly_new=len(brand_new_setups),
                    re_detected=len(re_evaluated_setups),
                    monitoring_count=final_monitoring_count,
                    watching_count=watching_count,
                    open_positions=len(all_open_positions),
                    deep_sleep_active=deep_sleep_active,
                    deep_sleep_until=deep_sleep_until_str,
                    setup_symbols=setup_symbols,
                    persist_missing=persist_missing,
                )
            except Exception as e:
                print(f"[ERROR] send_scan_report failed: {e} — trimite versiune simpla")
                try:
                    self.telegram.send_message(
                        f"✅ <b>Scan Complete!</b>\n"
                        f"📊 Pairs: <code>{len(self.pairs)}</code> | Setups: <code>{len(setups_found)}</code>\n"
                        f"📋 Monitoring: <code>{final_monitoring_count}</code> | Pozitii: <code>{len(all_open_positions)}</code>\n"
                        f"⏰ <code>{datetime.now().strftime('%Y-%m-%d %H:%M EET')}</code>",
                        parse_mode='HTML'
                    )
                except Exception as e2:
                    print(f"[ERROR] Fallback scan report failed: {e2}")
            
        # DEBUG: Print status for each setup found
        print('\n--- DEBUG: Status setup-uri returnate de run_daily_scan ---')
        for s in all_active_setups:
            status_tag = "🆕 NEW" if s.symbol not in open_position_symbols else "🔄 ACTIVE"
            print(f"{status_tag} {getattr(s, 'symbol', 'N/A')}: status={getattr(s, 'status', 'N/A')}")
        print('----------------------------------------------------------')
        return all_active_setups  # Return ALL setups (new + active with positions)
    
    def scan_single_pair(self, symbol: str) -> Optional[TradeSetup]:
        """Scan a single pair (for testing)"""
        print(f"\n🔍 Testing single pair: {symbol}")
        
        if not self.data_provider.connect():
            print("❌ Failed to connect to cTrader cBot API")
            return None
        
        try:
            # Find pair config
            pair_config = next((p for p in self.pairs if p['symbol'] == symbol), None)
            
            if not pair_config:
                print(f"❌ {symbol} not found in pairs_config.json")
                return None
            
            # Download data (W→D→4H)
            # V11.2: citim din pairs_config.json — NU mai hardcodăm 100
            d1_bars = self.scanner_settings.get('lookback_candles', {}).get('daily', 200)
            h4_bars = self.scanner_settings.get('lookback_candles', {}).get('h4', 200)
            df_daily = self.data_provider.get_historical_data(symbol, "D1", d1_bars)
            df_4h = self.data_provider.get_historical_data(symbol, "H4", h4_bars)
            
            if df_daily is None or df_4h is None:
                print(f"❌ Failed to download data for {symbol}")
                return None
            
            # Run detection (W→D→4H)
            setup = self.smc_detector.scan_for_setup(
                symbol=symbol,
                df_daily=df_daily,
                df_4h=df_4h,
                priority=pair_config['priority'],
                debug=True    # ✅ V10.6: verbose reject messages
            )
            
            if setup:
                print(f"\n🎯 SETUP FOUND on {symbol}!")
                print(f"Direction: {setup.h4_choch.direction.upper()}")
                print(f"Entry: {setup.entry_price:.5f}")
                print(f"SL: {setup.stop_loss:.5f}")
                print(f"TP: {setup.take_profit:.5f}")
                print(f"R:R: 1:{setup.risk_reward:.2f}")
                
                # Send test alert
                # self.telegram.send_setup_alert(setup, df_daily, df_4h)
            else:
                print(f"✓ No setup detected on {symbol}")
            
            return setup
        
        finally:
            self.data_provider.disconnect()


def _norm_strategy_type(val) -> str:
    """Normalize continuation vs reversal for SMART MERGE comparisons (TradeSetup default: reversal)."""
    s = (val or 'reversal').lower()
    return 'reversal' if s.startswith('reversal') else 'continuation'


def _parse_setup_time_days(setup_time_str) -> Optional[float]:
    """Return setup age in days, or None if unparseable."""
    if not setup_time_str:
        return None
    try:
        ts = str(setup_time_str).replace('Z', '+00:00')
        if '1970-01-01' in ts:
            return None
        st = datetime.fromisoformat(ts)
        if st.tzinfo is not None:
            st = st.replace(tzinfo=None)
        return (datetime.now() - st).total_seconds() / 86400.0
    except Exception:
        return None


def _price_in_daily_poi(
    price: Optional[float],
    stored: dict,
    d1_wick_high: Optional[float] = None,
    d1_wick_low: Optional[float] = None,
) -> bool:
    """True dacă wick Daily sau prețul curent intersectează POI (V45 aliniat cu radar)."""
    poi_bottom, poi_top = poi_bounds_from_stored(stored)
    return poi_touch_active(price, poi_bottom, poi_top, d1_wick_high, d1_wick_low)


def _d1_wick_from_df(df_d1: Optional[pd.DataFrame]) -> tuple[Optional[float], Optional[float]]:
    if df_d1 is None or df_d1.empty:
        return None, None
    return float(df_d1['high'].iloc[-1]), float(df_d1['low'].iloc[-1])


def _v43_fields_from_setup(setup: TradeSetup) -> dict:
    """Extract V43 ADR / POI metadata from TradeSetup for JSON persistence."""
    return {
        "adr_lh": getattr(setup, 'adr_lh', None),
        "adr_ll": getattr(setup, 'adr_ll', None),
        "adr_hl": getattr(setup, 'adr_hl', None),
        "poi_v43_source": getattr(setup, 'poi_v43_source', None),
        "structural_breach": bool(getattr(setup, 'structural_breach', False)),
    }


def _identity_direction(entry: dict) -> str:
    """Normalize JSON direction to bullish/bearish."""
    raw = (
        entry.get('d1_bias_direction')
        or entry.get('daily_bias')
        or entry.get('direction')
        or ''
    )
    d = str(raw).lower()
    if d in ('buy', 'long', 'bullish'):
        return 'bullish'
    if d in ('sell', 'short', 'bearish'):
        return 'bearish'
    return ''


def _d1_identity_snapshot(
    detector: SMCDetector,
    df_daily: pd.DataFrame,
    symbol: str,
) -> dict:
    """Faza B — leg CHoCH + podea/plafon structural pentru setup_identity_lock."""
    if df_daily is None or df_daily.empty:
        return {}
    sym = symbol or '?'
    swing_h = detector.detect_swing_highs(df_daily)
    swing_l = detector.detect_swing_lows(df_daily)
    chochs, bos_list = detector.detect_choch_and_bos(df_daily)
    range_state = detector.compute_structural_range(df_daily, swing_h, swing_l, symbol=sym)
    chochs, bos_list, range_state = detector.filter_internal_range_signals(
        sym, df_daily, chochs, bos_list, range_state,
    )
    _latest, _strategy, current_trend, leg_choch = detector._resolve_d1_leg(
        df_daily, chochs, bos_list, debug=False, range_state=range_state,
    )
    if leg_choch is None:
        return {}

    leg_price = float(leg_choch.break_price)
    floor = ceiling = None
    if leg_choch.direction == 'bullish':
        floor = leg_price
        if range_state is not None and range_state.macro_range_high:
            ceiling = float(range_state.macro_range_high)
        elif swing_h:
            ceiling = float(max(s.price for s in swing_h[-5:]))
    else:
        ceiling = leg_price
        if range_state is not None and range_state.macro_range_low:
            floor = float(range_state.macro_range_low)
        elif swing_l:
            floor = float(min(s.price for s in swing_l[-5:]))

    return {
        'leg_choch_bar': int(leg_choch.index),
        'leg_choch_price': leg_price,
        'leg_choch_direction': leg_choch.direction,
        'major_structure_floor': floor,
        'major_structure_ceiling': ceiling,
        'setup_identity_locked': True,
    }


def _structure_identity_breached(df_daily: Optional[pd.DataFrame], locked: dict) -> bool:
    """True when daily close breaks the locked leg invalidation bound."""
    if df_daily is None or df_daily.empty or not locked.get('setup_identity_locked'):
        return False
    close = float(df_daily['close'].iloc[-1])
    trend = _identity_direction(locked)
    floor = locked.get('major_structure_floor')
    ceiling = locked.get('major_structure_ceiling')
    leg_price = locked.get('leg_choch_price')
    if trend == 'bullish':
        inv = floor if floor is not None else leg_price
        return inv is not None and close <= float(inv)
    if trend == 'bearish':
        inv = ceiling if ceiling is not None else leg_price
        return inv is not None and close >= float(inv)
    return False


def _live_contradicts_locked_identity(old: dict, new_macro: dict) -> bool:
    old_dir = _identity_direction(old)
    new_dir = _identity_direction(new_macro)
    if old_dir and new_dir and old_dir != new_dir:
        return True
    return _norm_strategy_type(old.get('strategy_type')) != _norm_strategy_type(
        new_macro.get('strategy_type')
    )


_IDENTITY_MACRO_KEYS = (
    'direction', 'daily_bias', 'd1_bias_direction', 'setup_type',
    'strategy_type', 'd1_signal_type', 'd1_signal_bar', 'd1_signal_price',
)
_IDENTITY_BOUND_KEYS = (
    'leg_choch_bar', 'leg_choch_price', 'leg_choch_direction',
    'major_structure_floor', 'major_structure_ceiling',
)
_IDENTITY_STALE_LEVEL_KEYS = (
    'poi_top', 'poi_bottom', 'fvg_top', 'fvg_bottom',
    'entry_price', 'stop_loss', 'take_profit', 'risk_reward',
    'adr_lh', 'adr_hl', 'adr_ll', 'poi_v43_source', 'daily_target_price',
)


def _apply_setup_identity_lock(
    old: dict,
    new_macro: dict,
    df_daily: Optional[pd.DataFrame],
    detector: SMCDetector,
    symbol: Optional[str] = None,
) -> dict:
    """Faza B — blocare identitate setup până la spargerea podelei/plafonului major."""
    sym = symbol or new_macro.get('symbol') or old.get('symbol') or '?'
    out = dict(new_macro)

    if old.get('entry1_filled') or old.get('status') in ('TRADE_OPEN', 'PARTIAL_OPEN'):
        for key in _IDENTITY_BOUND_KEYS + _IDENTITY_MACRO_KEYS:
            if key in old and old.get(key) is not None:
                out[key] = old[key]
        out['setup_identity_locked'] = bool(old.get('setup_identity_locked'))
        return out

    def _snapshot() -> dict:
        if df_daily is None:
            return {}
        try:
            return _d1_identity_snapshot(detector, df_daily, sym)
        except Exception:
            return {}

    if not old.get('setup_identity_locked'):
        out.update(_snapshot())
        if out.get('setup_identity_locked'):
            print(
                f"  🔒 [Faza B] {sym}: identity locked "
                f"floor={out.get('major_structure_floor')} "
                f"ceiling={out.get('major_structure_ceiling')} "
                f"leg@bar{out.get('leg_choch_bar')}"
            )
        return out

    breached = _structure_identity_breached(df_daily, old)
    contradicts = _live_contradicts_locked_identity(old, new_macro)

    if breached:
        out.update(_snapshot())
        if contradicts:
            print(f"  🔓 [Faza B] {sym}: structure breached — new identity from live D1")
        return out

    if contradicts:
        for key in _IDENTITY_MACRO_KEYS + _IDENTITY_BOUND_KEYS:
            if key in old and old.get(key) is not None:
                out[key] = old[key]
        for key in _IDENTITY_STALE_LEVEL_KEYS:
            if key in old and old.get(key) is not None:
                out[key] = old[key]
        out['setup_identity_locked'] = True
        print(
            f"  🔒 [Faza B] {sym}: live D1 flip blocked — "
            f"identity {old.get('direction', '').upper()}/"
            f"{_norm_strategy_type(old.get('strategy_type'))} held (pullback noise)"
        )
        return out

    out.update(_snapshot())
    out['setup_identity_locked'] = True
    return out


def _unlock_identity_on_direction_flip(old: dict, new_direction: str, symbol: str = '?') -> dict:
    """Bias/direction flip — drop stale identity lock so live D1 macro can persist."""
    old_dir = (old.get('direction') or '').lower()
    new_dir = (new_direction or '').lower()
    if old_dir and new_dir and old_dir != new_dir:
        print(
            f"  🔓 [V59 FLIP] {symbol}: identity unlock {old_dir.upper()} → {new_dir.upper()} "
            f"(fresh D1 macro from scan)"
        )
        return {}
    return old


def _audit_scan_persistence(
    scan_setups: list,
    bias_fallback: list,
    saved_symbols: list,
    skip_audit: dict,
) -> list:
    """Return list of {symbol, reason} for detections missing from JSON after save."""
    expected = set()
    for s in scan_setups:
        sym = getattr(s, 'symbol', None)
        if sym:
            expected.add(sym)
    for entry in bias_fallback or []:
        sym = entry.get('symbol')
        if sym:
            expected.add(sym)

    saved = set(saved_symbols or [])
    missing = []
    for sym in sorted(expected - saved):
        missing.append({'symbol': sym, 'reason': skip_audit.get(sym, 'not_persisted_unknown')})
    if missing:
        print("\n⚠️  [V59 PERSIST AUDIT] Setup-uri detectate dar LIPSĂ din JSON după save:")
        for row in missing:
            print(f"   • {row['symbol']}: {row['reason']}")
    else:
        print(f"\n✅ [V59 PERSIST AUDIT] Toate cele {len(expected)} detectări sunt în JSON.")
    return missing


def _adr_level_shift(
    old_val,
    new_val,
    threshold_pct: float = 0.2,
) -> bool:
    """True when a single ADR bound moved materially."""
    if old_val is None or new_val is None:
        return False
    try:
        old_f, new_f = float(old_val), float(new_val)
    except (TypeError, ValueError):
        return False
    if old_f <= 0:
        return old_f != new_f
    return abs(new_f - old_f) / old_f * 100.0 >= threshold_pct


def _adr_container_shift_detected(
    old: dict,
    new: dict,
    threshold_pct: float = 0.2,
) -> bool:
    """True when live ADR LH/HL/LL moved materially vs JSON (rehydrate POI)."""
    for key in ('adr_lh', 'adr_hl', 'adr_ll'):
        if _adr_level_shift(old.get(key), new.get(key), threshold_pct):
            return True
    return False


def _bos_new_range_detected(old: dict, new_macro: dict, threshold_pct: float = 0.2) -> bool:
    """V44.1 — BOS expansion new range overrides POI preserve."""
    if new_macro.get('d1_signal_type') == 'BOS' and old.get('d1_signal_type') != 'BOS':
        return True
    if new_macro.get('d1_signal_type') == 'BOS' and _adr_container_shift_detected(old, new_macro, threshold_pct):
        return True

    direction = (
        new_macro.get('d1_bias_direction')
        or new_macro.get('daily_bias')
        or new_macro.get('direction')
        or old.get('direction')
        or ''
    ).lower()
    old_top = old.get('poi_top') if old.get('poi_top') is not None else old.get('fvg_top')
    old_bottom = old.get('poi_bottom') if old.get('poi_bottom') is not None else old.get('fvg_bottom')
    adr_hl = new_macro.get('adr_hl')
    adr_lh = new_macro.get('adr_lh')

    if old_top is not None and old_bottom is not None:
        if direction in ('buy', 'long', 'bullish') and adr_hl is not None:
            if float(old_top) < float(adr_hl):
                return True
        if direction in ('sell', 'short', 'bearish') and adr_lh is not None:
            if float(old_bottom) > float(adr_lh):
                return True

    if not new_macro.get('preserve_stored_poi'):
        new_top = new_macro.get('poi_top')
        new_bottom = new_macro.get('poi_bottom')
        if (
            old_top is not None and old_bottom is not None
            and new_top is not None and new_bottom is not None
            and (abs(float(new_top) - float(old_top)) > 1e-9
                 or abs(float(new_bottom) - float(old_bottom)) > 1e-9)
            and new_macro.get('d1_signal_type') == 'BOS'
        ):
            return True
    return False


def _apply_v43_poi_persistence(old: dict, new_macro: dict) -> dict:
    """Faza B — BOS new range + ADR shift rehydrate only (no POI preserve)."""
    out = dict(new_macro)
    sym = out.get('symbol', '?')

    if _bos_new_range_detected(old, new_macro):
        out['preserve_stored_poi'] = False
        _old_top = old.get('poi_top') if old.get('poi_top') is not None else old.get('fvg_top')
        _old_bottom = old.get('poi_bottom') if old.get('poi_bottom') is not None else old.get('fvg_bottom')
        if _old_top is not None:
            out.setdefault('legacy_poi_top', _old_top)
            out.setdefault('legacy_poi_bottom', _old_bottom)
        out['poi_v43_source'] = new_macro.get('poi_v43_source') or 'V44.1 BOS new range rehydrate'
        print(
            f"  [V44.1 NEW RANGE] {sym}: BOS expansion — archived old POI, rehydrated live "
            f"[{out.get('poi_bottom')} – {out.get('poi_top')}]"
        )
        return out

    if _adr_container_shift_detected(old, new_macro):
        out['poi_v43_source'] = new_macro.get('poi_v43_source') or 'V43 ADR shift rehydrate'
        print(
            f"  [V43.1 LIFECYCLE] {sym}: ADR shift detected "
            f"LH {old.get('adr_lh')}→{new_macro.get('adr_lh')} "
            f"HL {old.get('adr_hl')}→{new_macro.get('adr_hl')} "
            f"LL {old.get('adr_ll')}→{new_macro.get('adr_ll')} — POI rehydrated from live scan"
        )
    return out


def _infer_reversal_tp_hit(setup_dict: dict, df_daily: Optional[pd.DataFrame] = None) -> bool:
    """True if reversal structural TP was reached or explicit flag set."""
    if setup_dict.get('reversal_tp_hit') or setup_dict.get('tp_hit'):
        return True
    if df_daily is None or df_daily.empty:
        return False
    tp = setup_dict.get('daily_target_price') or setup_dict.get('take_profit')
    if tp is None:
        return False
    try:
        tp_f = float(tp)
    except (TypeError, ValueError):
        return False
    direction = (
        setup_dict.get('d1_bias_direction')
        or setup_dict.get('daily_bias')
        or setup_dict.get('direction')
        or ''
    ).lower()
    recent = df_daily.iloc[-30:]
    if direction in ('buy', 'bullish', 'long'):
        return float(recent['high'].max()) >= tp_f
    if direction in ('sell', 'bearish', 'short'):
        return float(recent['low'].min()) <= tp_f
    return False


def _has_expansion_bos_after_tp(
    detector: SMCDetector,
    df_daily: pd.DataFrame,
    setup_dict: dict,
    symbol: str,
) -> bool:
    """Post-TP: confirm new BOS in trend direction on Daily."""
    swing_h = detector.detect_swing_highs(df_daily)
    swing_l = detector.detect_swing_lows(df_daily)
    chochs, bos_list = detector.detect_choch_and_bos(df_daily)
    range_state = detector.compute_structural_range(df_daily, swing_h, swing_l, symbol=symbol)
    chochs, bos_list, _ = detector.filter_internal_range_signals(
        symbol, df_daily, chochs, bos_list, range_state
    )
    if not bos_list:
        return False
    last_bos = bos_list[-1]
    if len(df_daily) - last_bos.index > 35:
        return False
    direction = (
        setup_dict.get('d1_bias_direction')
        or setup_dict.get('daily_bias')
        or setup_dict.get('direction')
        or ''
    ).lower()
    if direction in ('buy', 'bullish', 'long'):
        return last_bos.direction == 'bullish'
    if direction in ('sell', 'bearish', 'short'):
        return last_bos.direction == 'bearish'
    return False


def _rehydrate_poi_from_bos_range(
    detector: SMCDetector,
    df_daily: pd.DataFrame,
    setup_dict: dict,
    symbol: str,
    poi_source_label: str = 'V44.1 BOS new range',
) -> dict:
    """V44.1 — rebuild ADR + POI from live BOS anchor (no stored POI)."""
    sym = setup_dict.get('symbol', symbol)
    swing_h = detector.detect_swing_highs(df_daily)
    swing_l = detector.detect_swing_lows(df_daily)
    chochs, bos_list = detector.detect_choch_and_bos(df_daily)
    range_state = detector.compute_structural_range(df_daily, swing_h, swing_l, symbol=sym)
    chochs, bos_list, range_state = detector.filter_internal_range_signals(
        sym, df_daily, chochs, bos_list, range_state
    )
    latest_signal, _strategy, current_trend, _leg = detector._resolve_d1_leg(
        df_daily, chochs, bos_list, debug=False
    )
    if latest_signal is None:
        return setup_dict

    price = float(df_daily['close'].iloc[-1])
    adr = detector.build_active_dealing_range(
        df_daily, swing_h, swing_l, latest_signal.index, current_trend,
        range_state=range_state, symbol=sym,
    )
    out = dict(setup_dict)
    if out.get('poi_top') is not None and out.get('legacy_poi_top') is None:
        out['legacy_poi_top'] = out.get('poi_top')
        out['legacy_poi_bottom'] = out.get('poi_bottom')

    poi_res = detector.resolve_d1_poi(
        df_daily, latest_signal, price, current_trend, 'continuation', adr,
        symbol=sym,
        stored_poi_top=None,
        stored_poi_bottom=None,
    )
    if poi_res.fvg:
        out['poi_top'] = float(poi_res.fvg.top)
        out['poi_bottom'] = float(poi_res.fvg.bottom)
        out['fvg_top'] = float(poi_res.fvg.top)
        out['fvg_bottom'] = float(poi_res.fvg.bottom)
    if adr:
        out['adr_lh'] = float(adr.last_lh)
        out['adr_ll'] = float(adr.last_ll)
        out['adr_hl'] = float(adr.last_hl)

    out['strategy_type'] = 'continuation'
    out['setup_type'] = 'CONTINUATION'
    out['poi_v43_source'] = poi_res.poi_source or poi_source_label
    out['preserve_stored_poi'] = False
    out['d1_signal_type'] = 'BOS' if isinstance(latest_signal, BOS) else 'CHoCH'
    out['d1_signal_bar'] = getattr(latest_signal, 'index', None)
    out['d1_signal_price'] = getattr(latest_signal, 'break_price', None)
    out['d1_bias_direction'] = current_trend
    out['daily_bias'] = current_trend.upper()
    out['direction'] = 'buy' if current_trend == 'bullish' else 'sell'
    if out.get('status') not in ('TRADE_OPEN', 'PARTIAL_OPEN'):
        out['status'] = 'WAITING_D1_PULLBACK'
    for key in (
        'poi_first_touch_time', 'h4_fvg_first_touch_time',
        '_poi_occupied', '_h4_fvg_occupied',
    ):
        out.pop(key, None)
    for key in _RADAR_RESET_KEYS:
        out.pop(key, None)
    for key in list(out.keys()):
        if key.startswith('radar_'):
            out.pop(key, None)
    return out


def _try_bos_new_range_evolution(
    detector: SMCDetector,
    df_daily: pd.DataFrame,
    setup_dict: dict,
    symbol: str,
) -> dict:
    """V44.1 — reversal/stale POI → continuation after expansion BOS (no TP required)."""
    if setup_dict.get('entry1_filled') or setup_dict.get('status') in ('TRADE_OPEN', 'PARTIAL_OPEN'):
        return setup_dict

    sym = setup_dict.get('symbol', symbol)
    swing_h = detector.detect_swing_highs(df_daily)
    swing_l = detector.detect_swing_lows(df_daily)
    chochs, bos_list = detector.detect_choch_and_bos(df_daily)
    range_state = detector.compute_structural_range(df_daily, swing_h, swing_l, symbol=sym)
    chochs, bos_list, range_state = detector.filter_internal_range_signals(
        sym, df_daily, chochs, bos_list, range_state
    )
    latest_signal, strategy_type, current_trend, leg_choch = detector._resolve_d1_leg(
        df_daily, chochs, bos_list, debug=False
    )
    if latest_signal is None or leg_choch is None:
        return setup_dict
    if not isinstance(latest_signal, BOS):
        return setup_dict
    if not detector._expansion_bos_confirms_new_range(df_daily, leg_choch, latest_signal):
        return setup_dict

    price = float(df_daily['close'].iloc[-1])
    adr = detector.build_active_dealing_range(
        df_daily, swing_h, swing_l, latest_signal.index, current_trend,
        range_state=range_state, symbol=sym,
    )
    if adr is None:
        return setup_dict

    stored_top = setup_dict.get('poi_top') if setup_dict.get('poi_top') is not None else setup_dict.get('fvg_top')
    stored_bottom = setup_dict.get('poi_bottom') if setup_dict.get('poi_bottom') is not None else setup_dict.get('fvg_bottom')
    direction = (
        setup_dict.get('d1_bias_direction')
        or setup_dict.get('daily_bias')
        or setup_dict.get('direction')
        or ''
    ).lower()

    poi_conflict = False
    if stored_top is not None and stored_bottom is not None:
        poi_conflict = SMCDetector.poi_conflicts_with_continuation(
            float(stored_top), float(stored_bottom), direction, adr,
        )

    live_adr = {
        'adr_lh': float(adr.last_lh),
        'adr_hl': float(adr.last_hl),
        'adr_ll': float(adr.last_ll),
    }
    adr_shift = _adr_container_shift_detected(setup_dict, live_adr)
    stale_signal = setup_dict.get('d1_signal_type') != 'BOS'
    is_reversal = _norm_strategy_type(setup_dict.get('strategy_type')) == 'reversal'

    if not (is_reversal or poi_conflict or stale_signal or adr_shift or setup_dict.get('preserve_stored_poi')):
        return setup_dict

    out = _rehydrate_poi_from_bos_range(
        detector, df_daily, setup_dict, sym,
        poi_source_label='V44.1 BOS new range evolution',
    )
    print(
        f"  [V44.1 NEW RANGE] {sym}: BOS expansion — POI archived "
        f"[{out.get('legacy_poi_bottom')} – {out.get('legacy_poi_top')}] → "
        f"new [{out.get('poi_bottom')} – {out.get('poi_top')}] | "
        f"ADR HL={out.get('adr_hl')} LH={out.get('adr_lh')}"
    )
    return out


def _try_post_tp_evolution(
    detector: SMCDetector,
    df_daily: pd.DataFrame,
    setup_dict: dict,
    symbol: str,
) -> dict:
    """V43.1 E2-T6: reversal → continuation after structural TP + expansion BOS."""
    if _norm_strategy_type(setup_dict.get('strategy_type')) != 'reversal':
        return setup_dict
    if setup_dict.get('entry1_filled') or setup_dict.get('status') in ('TRADE_OPEN', 'PARTIAL_OPEN'):
        return setup_dict
    if not _infer_reversal_tp_hit(setup_dict, df_daily):
        return setup_dict
    if not _has_expansion_bos_after_tp(detector, df_daily, setup_dict, symbol):
        return setup_dict

    sym = setup_dict.get('symbol', symbol)
    out = _rehydrate_poi_from_bos_range(
        detector, df_daily, setup_dict, sym,
        poi_source_label='V43.1 post-TP evolution',
    )
    out['poi_mitigated'] = True
    out['reversal_tp_hit'] = False

    print(
        f"  [V43.1 LIFECYCLE] {sym}: REVERSAL → CONTINUATION (post-TP + expansion BOS) "
        f"| new POI [{out.get('poi_bottom')} – {out.get('poi_top')}]"
    )
    return out


def _hydrate_bias_fallback_poi(
    detector: SMCDetector,
    entry: dict,
    df_daily: pd.DataFrame,
) -> dict:
    """V43.1 E2-T4: populate POI for bias-fallback entries missing coordinates."""
    if entry.get('poi_top') is not None and entry.get('poi_bottom') is not None:
        return entry
    sym = entry.get('symbol', '?')
    try:
        swing_h = detector.detect_swing_highs(df_daily)
        swing_l = detector.detect_swing_lows(df_daily)
        chochs, bos_list = detector.detect_choch_and_bos(df_daily)
        range_state = detector.compute_structural_range(df_daily, swing_h, swing_l, symbol=sym)
        chochs, bos_list, range_state = detector.filter_internal_range_signals(
            sym, df_daily, chochs, bos_list, range_state
        )
        latest_signal, strategy_type, current_trend, _ = detector._resolve_d1_leg(
            df_daily, chochs, bos_list, debug=False
        )
        if latest_signal is None:
            return entry
        price = float(df_daily['close'].iloc[-1])
        adr = detector.build_active_dealing_range(
            df_daily, swing_h, swing_l, latest_signal.index, current_trend,
            range_state=range_state, symbol=sym,
        )
        poi_res = detector.resolve_d1_poi(
            df_daily, latest_signal, price, current_trend, strategy_type, adr, symbol=sym,
        )
        out = dict(entry)
        if poi_res.fvg:
            out['poi_top'] = float(poi_res.fvg.top)
            out['poi_bottom'] = float(poi_res.fvg.bottom)
            out['fvg_top'] = float(poi_res.fvg.top)
            out['fvg_bottom'] = float(poi_res.fvg.bottom)
            out['poi_v43_source'] = poi_res.poi_source or 'V43.1 bias fallback hydrate'
        if adr:
            out['adr_lh'] = float(adr.last_lh)
            out['adr_ll'] = float(adr.last_ll)
            out['adr_hl'] = float(adr.last_hl)
        out['structural_breach'] = SMCDetector.compute_structural_breach(
            price, current_trend, adr,
        )
        print(f"  [V43.1 LIFECYCLE] {sym}: bias fallback POI hydrated")
        return out
    except Exception as exc:
        print(f"  ⚠️ [V43.1 LIFECYCLE] {sym}: bias fallback POI hydrate failed: {exc}")
        return entry


def _apply_v431_lifecycle_gates(
    setup_dict: dict,
    price: Optional[float],
    d1_wick_high: Optional[float] = None,
    d1_wick_low: Optional[float] = None,
) -> dict:
    """V43.1 E2-T1/T4: strict state machine POI gates (stateless JSON dict). V45: wick Daily ∪ preț."""
    if price is None and d1_wick_high is None and d1_wick_low is None:
        return setup_dict
    setup_dict = dict(setup_dict)
    sym = setup_dict.get('symbol', '?')
    status = setup_dict.get('status', '')
    in_poi = _price_in_daily_poi(price, setup_dict, d1_wick_high, d1_wick_low)

    if setup_dict.get('structural_breach'):
        _swing_watch = frozenset({
            'MONITORING', 'READY', 'WAITING_D1_PULLBACK', 'WAITING_W_D_SYNC',
            'WAITING_W_ZONE', 'WAITING_4H_CHOCH', 'WAITING_4H_PULLBACK',
        })
        if (
            not setup_dict.get('entry1_filled')
            and status in _swing_watch
            and status not in ('TRADE_OPEN', 'PARTIAL_OPEN')
        ):
            print(
                f"  [V43.1 LIFECYCLE] {sym}: structural_breach flag — "
                f"swing monitor kept ({status}), no instant INVALIDATED"
            )
        elif not setup_dict.get('entry1_filled') and status not in ('TRADE_OPEN', 'PARTIAL_OPEN'):
            setup_dict['status'] = 'INVALIDATED'
            setup_dict['invalidation_reason'] = 'V43.1 structural_breach'
            for key in _RADAR_RESET_KEYS:
                setup_dict.pop(key, None)
            print(f"  [V43.1 LIFECYCLE] {sym}: INVALIDATED — structural_breach (protected LH/LL broken)")
            return setup_dict

    if status == 'WAITING_D1_PULLBACK' and in_poi:
        setup_dict['status'] = 'MONITORING'
        _touch = 'wick/preț în POI' if d1_wick_high is not None else 'preț în POI'
        print(f"  [V43.1 LIFECYCLE] {sym}: WAITING_D1_PULLBACK → MONITORING ({_touch})")

    elif status == 'MONITORING' and not in_poi:
        setup_dict['status'] = 'WAITING_D1_PULLBACK'
        for key in _RADAR_RESET_KEYS:
            setup_dict.pop(key, None)
        print(f"  [V43.1 LIFECYCLE] {sym}: MONITORING → WAITING_D1_PULLBACK (price left POI)")

    elif status == 'READY' and not in_poi:
        setup_dict['status'] = 'WAITING_D1_PULLBACK'
        for key in _RADAR_RESET_KEYS:
            setup_dict.pop(key, None)
        print(f"  [V43.1 LIFECYCLE] {sym}: READY → WAITING_D1_PULLBACK (price left POI macro zone)")

    return setup_dict


def _apply_v427_poi_status_gate(setup_dict: dict, price: float) -> dict:
    """V42.7 + V43.1: lifecycle gates (READY/MONITORING/WAITING strict POI incinta)."""
    return _apply_v431_lifecycle_gates(setup_dict, price)


_EXECUTOR_PRESERVE_KEYS = (
    'entry1_filled', 'entry1_price', 'entry1_time', 'entry1_order_id',
    'entry1_volume', 'entry1_trigger_tf', 'entry2_filled', 'entry2_price',
    'entry2_time', 'entry2_trigger_tf', 'entries_filled_tfs', 'multi_entry_pending',
    'multi_entry_plan', 'last_rejection_reason', 'last_rejection_time',
    'last_executor_block_reason', 'last_executor_block_time',
)


_RADAR_RESET_KEYS = (
    'EXECUTE_NOW', 'execute_now_trigger_tf', 'execute_now_alert_sent',
    'execute_now_alert_key', 'radar_execution_ready', 'radar_verdict',
    'h4_structure_locked', 'h4_sl_price',
)


def _macro_overwrite_blocked(stored: dict, open_position_dir_map: dict) -> bool:
    """V42: active trade — do not change direction/POI from live D1 scan."""
    if stored.get('entry1_filled'):
        return True
    if stored.get('status') in ('TRADE_OPEN', 'PARTIAL_OPEN'):
        return True
    sym = stored.get('symbol')
    return bool(sym and sym in open_position_dir_map)


def _apply_v42_macro_override(old: dict, new_macro: dict) -> dict:
    """V42: live D1 macro replaces stale JSON; preserve executor state; reset LTF on flip."""
    merged = dict(new_macro)
    for key in _EXECUTOR_PRESERVE_KEYS:
        if key in old and old.get(key) is not None:
            merged[key] = old[key]

    if old.get('status') in ('TRADE_OPEN', 'PARTIAL_OPEN') or old.get('entry1_filled'):
        merged['status'] = old.get('status', merged.get('status'))

    old_dir = (old.get('direction') or '').lower()
    new_dir = (merged.get('direction') or '').lower()
    old_st = _norm_strategy_type(old.get('strategy_type'))
    new_st = _norm_strategy_type(merged.get('strategy_type'))
    macro_flipped = bool(old_dir and new_dir and old_dir != new_dir) or old_st != new_st

    if macro_flipped and merged.get('status') != 'TRADE_OPEN' and not merged.get('entry1_filled'):
        for key in list(merged.keys()):
            if key.startswith('radar_'):
                merged.pop(key, None)
        for key in _RADAR_RESET_KEYS:
            merged.pop(key, None)
        merged['status'] = 'WAITING_4H_CHOCH'

    return merged


def _setup_time_to_iso(setup_time) -> str:
    if isinstance(setup_time, (int, float)):
        return datetime.fromtimestamp(setup_time).isoformat()
    if isinstance(setup_time, str):
        return setup_time
    if hasattr(setup_time, 'isoformat'):
        return setup_time.isoformat()
    return datetime.now().isoformat()


def _trade_setup_to_monitoring_dict(setup: TradeSetup, setup_time_str: str) -> dict:
    """Construiește dict JSON din TradeSetup (scan proaspăt)."""
    direction = "buy" if setup.daily_choch.direction == "bullish" else "sell"
    fvg_top = setup.fvg.top if setup.fvg and hasattr(setup.fvg, 'top') else None
    fvg_bottom = setup.fvg.bottom if setup.fvg and hasattr(setup.fvg, 'bottom') else None
    scan_status = getattr(setup, 'status', 'WAITING_D1_PULLBACK')
    if scan_status not in (
        'MONITORING', 'READY', 'WAITING_D1_PULLBACK', 'WAITING_4H_CHOCH',
        'WAITING_W_D_SYNC', 'WAITING_W_ZONE',
    ):
        scan_status = 'WAITING_D1_PULLBACK'
    _d1_sig = setup.daily_choch
    _d1_signal_type = 'CHoCH' if isinstance(_d1_sig, CHoCH) else 'BOS'
    out = {
        "symbol": setup.symbol,
        "direction": direction,
        "daily_bias": setup.daily_choch.direction.upper(),
        "setup_type": (getattr(setup, 'strategy_type', 'reversal') or 'reversal').upper(),
        "strategy_type": getattr(setup, 'strategy_type', 'reversal'),
        "strategy_locked": True,
        "d1_bias_direction": setup.daily_choch.direction,
        "daily_bias_active": bool(getattr(setup, 'daily_bias_active', False)),
        "confidence": getattr(setup, 'confidence', 'NORMAL'),
        "w1_bias": getattr(setup, 'w1_bias', 'NEUTRAL'),
        "w1_poi_top": getattr(setup, 'w1_poi_top', None),
        "w1_poi_bottom": getattr(setup, 'w1_poi_bottom', None),
        "w_d_aligned": bool(getattr(setup, 'w_d_aligned', True)),
        "poi_top": float(fvg_top) if fvg_top is not None else None,
        "poi_bottom": float(fvg_bottom) if fvg_bottom is not None else None,
        "fvg_top": float(fvg_top) if fvg_top is not None else None,
        "fvg_bottom": float(fvg_bottom) if fvg_bottom is not None else None,
        "daily_target_price": getattr(setup, 'daily_tp_price', None),
        "entry_price": float(setup.entry_price) if getattr(setup, 'entry_price', 0) else None,
        "stop_loss": float(setup.stop_loss) if getattr(setup, 'stop_loss', 0) else None,
        "take_profit": float(setup.take_profit) if getattr(setup, 'take_profit', 0) else None,
        "risk_reward": float(setup.risk_reward) if getattr(setup, 'risk_reward', 0) else None,
        "status": scan_status,
        "setup_time": setup_time_str,
        "priority": setup.priority,
        "swap_long": getattr(setup, 'swap_long', None),
        "swap_short": getattr(setup, 'swap_short', None),
        "swap_triple_day": getattr(setup, 'swap_triple_day', None),
        "daily_swing_low": getattr(setup, 'daily_swing_low', None),
        "daily_swing_high": getattr(setup, 'daily_swing_high', None),
        "d1_signal_type": _d1_signal_type,
        "d1_signal_bar": getattr(_d1_sig, 'index', None),
        "d1_signal_price": getattr(_d1_sig, 'break_price', None),
        "d1_scan_date": datetime.now().isoformat(),
    }
    out.update(_v43_fields_from_setup(setup))
    return out


def save_monitoring_setups(
    setups: List[TradeSetup],
    bias_fallback: list = None,
    daily_bias_map: dict = None,
    w1_bias_map: dict = None,
    symbol_price_map: dict = None,
    symbol_df_daily_map: dict = None,
    smc_detector: Optional[SMCDetector] = None,
) -> dict:
    """[V33 SMART MERGE] + V40.3 re-hidratare strategică + soft TTL 4 zile fără POI.
    Un pullback pe Daily poate dura zile — stergerea oarba de dimineata este interzisa.
    V40.3: W1 strict informativ; continuation↔reversal re-hidratează JSON; TTL 4d fără POI.

    Logica:
      1. Citim JSON existent.
      2. Pastram INTACTE paritati cu status: WAITING_D1_PULLBACK, MONITORING, READY,
         WAITING_4H_CHOCH, PARTIAL_OPEN, TRADE_OPEN.
      3. Setup-uri noi din scan: adaugam NUMAI daca paritatea NU exista deja activa in JSON.
      4. Bias fallback: la fel (nu suprascrie activ).
      5. Paritati cu status terminal (INVALIDATED, EXPIRED_TIMEOUT, COMPLETED_WITHOUT_ENTRY,
         EXPIRED, CLOSED, FAILED): nu le restauram, le ignoram.
    """
    if bias_fallback is None:
        bias_fallback = []
    if daily_bias_map is None:
        daily_bias_map = {}
    if w1_bias_map is None:
        w1_bias_map = {}
    if symbol_price_map is None:
        symbol_price_map = {}
    if symbol_df_daily_map is None:
        symbol_df_daily_map = {}
    detector = smc_detector or SMCDetector()
    _skip_audit: dict = {}

    _SOFT_TTL_DAYS = 4

    # Status-uri active — PASTRATE INTACTE de la o zi la alta
    _ACTIVE_STATUSES = {
        'WAITING_D1_PULLBACK', 'MONITORING', 'READY',
        'WAITING_4H_CHOCH', 'WAITING_4H_PULLBACK',
        'WAITING_W_D_SYNC', 'WAITING_W_ZONE',
        'PARTIAL_OPEN', 'TRADE_OPEN'
    }
    # Status-uri terminale — nu se mai includ in output
    _DEAD_STATUSES = {
        'INVALIDATED', 'EXPIRED_TIMEOUT', 'COMPLETED_WITHOUT_ENTRY',
        'EXPIRED', 'CLOSED', 'FAILED', 'CANCELLED'
    }

    # V11.0: Load open positions for direction conflict check
    open_position_dir_map = {}
    try:
        with open('trade_history.json', 'r', encoding='utf-8') as f:
            trade_data = json.load(f)
            for p in trade_data.get('open_positions', []):
                sym = p.get('symbol')
                direction = (p.get('direction') or '').lower()
                if sym:
                    open_position_dir_map[sym] = direction
    except Exception as _pos_err:
        logger.warning(f"[V37.0] Could not load open positions for monitoring merge: {_pos_err}")

    try:
        # Pasul 1: Citim JSON existent si pastram paritati active
        existing_active = {}  # symbol -> dict, pastrate de Radar
        try:
            with open('monitoring_setups.json', 'r', encoding='utf-8') as f:
                _ex_data = json.load(f)
            _ex_list = _ex_data.get('setups', []) if isinstance(_ex_data, dict) else _ex_data
            for s in _ex_list:
                if not isinstance(s, dict):
                    continue
                sym = s.get('symbol')
                st  = s.get('status', '')
                if sym and st in _ACTIVE_STATUSES and st not in _DEAD_STATUSES:
                    existing_active[sym] = s
            if existing_active:
                print(f"\n📌 [V33 SMART MERGE] {len(existing_active)} paritati active pastrate din ziua precedenta: "
                      f"{', '.join(existing_active.keys())}")
        except FileNotFoundError:
            pass  # Prima rulare — nimic de pastrat
        except json.JSONDecodeError:
            print("\u26a0\ufe0f  monitoring_setups.json corupt — pornim fresh")

        # V40.3 SOFT TTL — MONITORING / WAITING_D1_PULLBACK > 4 zile fără atingere POI
        _soft_ttl_expired = []
        for sym, stored in list(existing_active.items()):
            st = stored.get('status', '')
            if st not in ('MONITORING', 'WAITING_D1_PULLBACK'):
                continue
            age_days = _parse_setup_time_days(stored.get('setup_time'))
            if age_days is None or age_days <= _SOFT_TTL_DAYS:
                continue
            poi_top = stored.get('poi_top') if stored.get('poi_top') is not None else stored.get('fvg_top')
            poi_bottom = stored.get('poi_bottom') if stored.get('poi_bottom') is not None else stored.get('fvg_bottom')
            if poi_top is None or poi_bottom is None:
                continue
            price = symbol_price_map.get(sym)
            df_d1 = symbol_df_daily_map.get(sym)
            _d1_h, _d1_l = _d1_wick_from_df(df_d1)
            if _price_in_daily_poi(price, stored, _d1_h, _d1_l):
                continue
            _soft_ttl_expired.append(sym)
            print(
                f"  ⏱️ [V40.3 SOFT TTL] {sym}: {age_days:.1f}d > {_SOFT_TTL_DAYS}d, "
                f"POI [{poi_bottom}–{poi_top}] neatins (close={price}) → EXPIRED_TIMEOUT"
            )
        for sym in _soft_ttl_expired:
            existing_active.pop(sym, None)

        # V40: Invalidează setup-uri stale când D1 bias contradictă direcția salvată
        _invalidated = []
        for sym, stored in list(existing_active.items()):
            st = stored.get('status', '')
            # V42.2: open trades — doar broker confirmă închiderea
            if st in ('PARTIAL_OPEN', 'TRADE_OPEN'):
                continue
            bias = daily_bias_map.get(sym)
            stored_dir = (stored.get('direction') or '').lower()
            if not stored_dir:
                continue

            _purge = False
            _reason = ''

            if bias in ('bullish', 'bearish'):
                expected = 'buy' if bias == 'bullish' else 'sell'
                if stored_dir != expected:
                    _purge = True
                    _reason = f"JSON {stored_dir.upper()} ≠ D1 {bias.upper()}"

            if _purge:
                _invalidated.append(sym)
                print(f"  🔄 [V40 BIAS INVALIDATE] {sym}: {_reason} — setup vechi eliminat")
        for sym in _invalidated:
            existing_active.pop(sym, None)

        # V43.1 + V44.1: lifecycle + BOS new range + post-TP pe setup-uri păstrate
        for sym, stored in list(existing_active.items()):
            price = symbol_price_map.get(sym)
            df_d1 = symbol_df_daily_map.get(sym)
            _d1_h, _d1_l = _d1_wick_from_df(df_d1)
            stored = _apply_v431_lifecycle_gates(stored, price, _d1_h, _d1_l)
            if stored.get('status') in _DEAD_STATUSES:
                existing_active.pop(sym, None)
                continue
            if df_d1 is not None:
                stored = _try_bos_new_range_evolution(detector, df_d1, stored, sym)
                stored = _try_post_tp_evolution(detector, df_d1, stored, sym)
            existing_active[sym] = stored

        # Pasul 2: Construim lista finala
        monitoring_setups = list(existing_active.values())  # Incepem cu ce era activ
        preserved_symbols = set(existing_active.keys())

        # Pasul 3: Adaugam setup-uri NOI din scanul de azi (numai daca nu exista deja)
        for setup in setups:
            if setup.status not in ("MONITORING", "READY", "WAITING_D1_PULLBACK",
                                    "WAITING_4H_CHOCH", "WAITING_W_D_SYNC", "WAITING_W_ZONE"):
                _skip_audit[setup.symbol] = f"scan_status={getattr(setup, 'status', '?')}_not_saveable"
                continue

            direction = "buy" if setup.daily_choch.direction == "bullish" else "sell"

            # Conflict guard
            open_dir = open_position_dir_map.get(setup.symbol)
            if open_dir and open_dir != direction:
                print(f"⛔ SAVE GUARD: {setup.symbol} — NOT saving {direction.upper()} setup, "
                      f"open {open_dir.upper()} position exists")
                _skip_audit[setup.symbol] = f"conflict_open_{open_dir}"
                continue

            setup_time_str = _setup_time_to_iso(setup.setup_time)

            if setup.symbol in preserved_symbols:
                _old = existing_active.get(setup.symbol, {})
                _old = _unlock_identity_on_direction_flip(_old, direction, setup.symbol)
                if _macro_overwrite_blocked(_old, open_position_dir_map):
                    print(
                        f"  ⚠️ [V42 CONFLICT] Skipping macro overwrite for {setup.symbol} "
                        f"due to active TRADE_OPEN/PARTIAL_OPEN"
                    )
                    _skip_audit[setup.symbol] = 'macro_overwrite_blocked_trade_open'
                    continue

                monitoring_setup = _trade_setup_to_monitoring_dict(setup, setup_time_str)
                _live_price = symbol_price_map.get(setup.symbol) if symbol_price_map else None
                monitoring_setup = _apply_v427_poi_status_gate(monitoring_setup, _live_price)
                df_d1 = symbol_df_daily_map.get(setup.symbol)
                monitoring_setup = _apply_setup_identity_lock(
                    _old, monitoring_setup, df_d1, detector, setup.symbol,
                )
                merged = _apply_v42_macro_override(_old, monitoring_setup)
                merged = _apply_v43_poi_persistence(_old, merged)
                if df_d1 is not None:
                    merged = _try_bos_new_range_evolution(detector, df_d1, merged, setup.symbol)
                    merged = _try_post_tp_evolution(detector, df_d1, merged, setup.symbol)
                if merged.get('status') in _DEAD_STATUSES:
                    _skip_audit[setup.symbol] = f"lifecycle_{merged.get('status')}"
                    monitoring_setups = [
                        s for s in monitoring_setups if s.get('symbol') != setup.symbol
                    ]
                    existing_active.pop(setup.symbol, None)
                    continue
                monitoring_setups = [
                    s for s in monitoring_setups if s.get('symbol') != setup.symbol
                ]
                monitoring_setups.append(merged)
                existing_active[setup.symbol] = merged
                print(
                    f"  🏛️ [V42 LIVE AUTHORITY] {setup.symbol}: Macro re-hydrated from live D1 scan "
                    f"(Strategy: {merged.get('strategy_type')}, Direction: {merged.get('direction')})"
                )
                continue

            monitoring_setup = _trade_setup_to_monitoring_dict(setup, setup_time_str)
            _live_price = symbol_price_map.get(setup.symbol) if symbol_price_map else None
            monitoring_setup = _apply_v427_poi_status_gate(monitoring_setup, _live_price)
            df_d1 = symbol_df_daily_map.get(setup.symbol)
            monitoring_setup = _apply_setup_identity_lock(
                {}, monitoring_setup, df_d1, detector, setup.symbol,
            )
            if df_d1 is not None:
                monitoring_setup = _try_bos_new_range_evolution(detector, df_d1, monitoring_setup, setup.symbol)
                monitoring_setup = _try_post_tp_evolution(detector, df_d1, monitoring_setup, setup.symbol)
            if monitoring_setup.get('status') in _DEAD_STATUSES:
                _skip_audit[setup.symbol] = f"lifecycle_{monitoring_setup.get('status')}"
                continue
            monitoring_setups.append(monitoring_setup)
            preserved_symbols.add(setup.symbol)
            _skip_audit.pop(setup.symbol, None)

        # Pasul 4: Bias fallback entries (numai daca simbolul nu e deja activ)
        for entry in bias_fallback:
            sym = entry.get('symbol')
            direction = entry.get('direction', '')
            if sym in preserved_symbols:
                _old = existing_active.get(sym, {})
                _old_dir = (_old.get('direction') or '').lower()
                if _old_dir and _old_dir != direction:
                    monitoring_setups = [s for s in monitoring_setups if s.get('symbol') != sym]
                    preserved_symbols.discard(sym)
                    existing_active.pop(sym, None)
                    print(
                        f"  🔄 [V40 BIAS FLIP] {sym} fallback: {_old_dir.upper()} → {direction.upper()}"
                    )
                else:
                    _new_fb = dict(entry)
                    if _macro_overwrite_blocked(_old, open_position_dir_map):
                        print(
                            f"  ⚠️ [V42 CONFLICT] Skipping macro overwrite for {sym} fallback "
                            f"due to active TRADE_OPEN/PARTIAL_OPEN"
                        )
                        continue
                    merged_fb = _apply_v42_macro_override(_old, _new_fb)
                    _df_fb = symbol_df_daily_map.get(sym)
                    merged_fb = _apply_setup_identity_lock(_old, merged_fb, _df_fb, detector, sym)
                    merged_fb = _apply_v43_poi_persistence(_old, merged_fb)
                    _live_fb = symbol_price_map.get(sym)
                    _fb_h, _fb_l = _d1_wick_from_df(_df_fb)
                    merged_fb = _apply_v431_lifecycle_gates(merged_fb, _live_fb, _fb_h, _fb_l)
                    df_d1 = _df_fb
                    if df_d1 is not None:
                        merged_fb = _try_bos_new_range_evolution(detector, df_d1, merged_fb, sym)
                        merged_fb = _try_post_tp_evolution(detector, df_d1, merged_fb, sym)
                    if merged_fb.get('status') in _DEAD_STATUSES:
                        monitoring_setups = [s for s in monitoring_setups if s.get('symbol') != sym]
                        existing_active.pop(sym, None)
                        preserved_symbols.discard(sym)
                        continue
                    monitoring_setups = [s for s in monitoring_setups if s.get('symbol') != sym]
                    monitoring_setups.append(merged_fb)
                    existing_active[sym] = merged_fb
                    print(
                        f"  🏛️ [V42 LIVE AUTHORITY] {sym}: bias fallback re-hydrated "
                        f"(Strategy: {merged_fb.get('strategy_type')}, Direction: {merged_fb.get('direction')})"
                    )
                    continue
            open_dir = open_position_dir_map.get(sym)
            if open_dir and open_dir != direction:
                print(f"⛔ SAVE GUARD: {sym} — NOT saving bias fallback {direction.upper()}, "
                      f"open {open_dir.upper()} position exists")
                continue
            _live_fb = symbol_price_map.get(sym)
            _df_fb = symbol_df_daily_map.get(sym)
            entry = _apply_v431_lifecycle_gates(entry, _live_fb, *_d1_wick_from_df(_df_fb))
            entry = _apply_setup_identity_lock({}, entry, _df_fb, detector, sym)
            if entry.get('status') in _DEAD_STATUSES:
                continue
            monitoring_setups.append(entry)
            if sym:
                preserved_symbols.add(sym)

        # Atomic write
        _ms_write = {
            "setups": monitoring_setups,
            "last_updated": datetime.now().isoformat()
        }
        from monitoring_json_io import save_monitoring_json
        save_monitoring_json(
            Path('monitoring_setups.json'),
            _ms_write,
            tmp_tag='.scanner',
        )

        new_count = max(0, len(monitoring_setups) - len(existing_active))
        print(f"\n💾 [V42 LIVE AUTHORITY] {len(monitoring_setups)} total — "
              f"{len(existing_active)} pastrate/rehidratate + {new_count} noi din scan de azi")

        return {
            'saved_symbols': [s.get('symbol') for s in monitoring_setups if s.get('symbol')],
            'skipped': dict(_skip_audit),
            'total': len(monitoring_setups),
        }

    except Exception as e:
        print(f"❌ Error saving monitoring setups: {e}")
        return {'saved_symbols': [], 'skipped': dict(_skip_audit), 'total': 0, 'error': str(e)}


def main():
    """Main entry point"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Daily Scanner for Glitch in Matrix V8.2')
    parser.add_argument(
        '--ignore-open-positions',
        action='store_true',
        help='Force scan all pairs even if they have open positions (for testing/audit)'
    )
    args = parser.parse_args()
    
    # Set global flag
    global IGNORE_OPEN_POSITIONS
    IGNORE_OPEN_POSITIONS = args.ignore_open_positions
    
    if IGNORE_OPEN_POSITIONS:
        print("⚠️  AUDIT MODE: Ignoring open positions check - scanning ALL pairs\n")
    
    scanner = DailyScanner()
    logger.success(
        "[V42.4 CLEANUP] Successfully purged legacy branches and unified core system data defaults."
    )
    
    # Test Telegram connection first
    print("🧪 Testing Telegram connection...")
    if scanner.telegram.test_connection():
        print("✅ Telegram connected successfully!\n")
    else:
        print("⚠️ Telegram connection failed - check .env configuration\n")
    
    # Run full daily scan
    setups = scanner.run_daily_scan()

    # V31.0: save_monitoring_setups() WIPE apelat intern de run_daily_scan() — nu repetăm din main().

    # Print summary
    if setups:
        print("\n📋 SETUPS SUMMARY:")
        for i, setup in enumerate(setups, 1):
            direction = "LONG" if setup.daily_choch.direction == 'bullish' else "SHORT"
            status = f"[{setup.status}]"
            # V8.4: Display strategy type (REVERSAL or CONTINUITY)
            strategy = setup.strategy_type.upper() if hasattr(setup, 'strategy_type') else "UNKNOWN"
            strategy_emoji = "🔄" if strategy == "REVERSAL" else "➡️"
            # V8.2 FIX: Handle None values for entry_price and risk_reward
            entry_price = setup.entry_price if setup.entry_price is not None else 0.0
            risk_reward = setup.risk_reward if setup.risk_reward is not None else 0.0
            print(f"{i}. {strategy_emoji} {strategy} - {setup.symbol} - {direction} @ {entry_price:.5f} (R:R 1:{risk_reward:.2f}) {status}")


if __name__ == "__main__":
    import sys
    import traceback
    try:
        # For testing single pair:
        # scanner = DailyScanner()
        # scanner.scan_single_pair("GBPUSD")

        # For full daily scan:
        main()

        # Show active positions summary after scan
        from pathlib import Path as _Path
        _active_path = str(_Path(__file__).parent / 'active_positions.json')
        if os.path.exists(_active_path):
            with open(_active_path, 'r', encoding='utf-8') as _f:
                _positions = json.load(_f)
            if _positions:
                print('\n🎯 ACTIVE SETUPS (cTrader Sync):')
                for pos in _positions:
                    _dir = 'LONG' if pos.get('direction') == 'buy' else 'SHORT'
                    print(f"• {pos.get('symbol','?')} - {_dir}  Entry: {pos.get('entry_price','?')} | Vol: {pos.get('volume', 0)}")
            else:
                print('No active positions in cTrader.')
    except Exception as _e:
        # ✅ V14.6: encode-safe error print (Windows cp1252 can't handle emoji)
        try:
            print(f"\nFATAL ERROR in daily_scanner.py: {_e}", flush=True)
        except Exception:
            sys.stdout.buffer.write(f"\nFATAL ERROR: {_e}\n".encode('utf-8', errors='replace'))
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
