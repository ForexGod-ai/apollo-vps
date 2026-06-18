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
from datetime import datetime, timedelta
import json
import os
import time
import argparse
from typing import List, Optional, Dict
from dotenv import load_dotenv
from loguru import logger

from smc_detector import SMCDetector, TradeSetup
from telegram_notifier import TelegramNotifier
from ctrader_cbot_client import CTraderCBotClient
from strategy_optimizer import StrategyOptimizer
from ai_probability_analyzer import AIProbabilityAnalyzer
from pip_utils import get_pip_size, liquidity_already_swept

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
        print("🔥 ForexGod - Glitch Daily Scanner Starting... [V40.3 W1 INFO + SMART RE-HYDRATE]")
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

        # V3.0: Load existing monitoring setups to re-evaluate their status
        monitoring_symbols = set()
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
                if monitoring_symbols:
                    print(f"\n🔄 Re-evaluating {len(monitoring_symbols)} MONITORING setups: {', '.join(monitoring_symbols)}")
        except FileNotFoundError:
            pass
        except json.JSONDecodeError as e:
            print(f"⚠️  ERROR: monitoring_setups.json is corrupted: {e}")
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
                
                # Download Daily data
                df_daily = self.data_provider.get_historical_data(
                    symbol,
                    "D1",
                    250  # V31.0: 250 bare fixe — suficient pentru 1 an D1
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
                
                # V3.1 SCALE_IN: Download 1H data for ALL pairs (Entry 1 validation)
                print(f"   📊 Downloading 1H data (SCALE_IN strategy)...") 
                df_1h = self.data_provider.get_historical_data(
                    symbol,
                    "H1",
                    self.scanner_settings['lookback_candles'].get('h1', 225)
                )
                if df_1h is None:
                    print(f"⚠️ Warning: {symbol} has no 1H data (Entry 1 disabled)")

                # V40.3: W1 = macro anchor informativ (confidence flag, fără reject)
                print(f"   📅 Downloading W1 data (Weekly Anchor — 52 bars, ~1 an)...")
                df_w1 = None
                w1_result = {'bias': 'NEUTRAL', 'last_bos_direction': None, 'last_bos_price': None, 'last_bos_bar_idx': None}
                try:
                    df_w1 = self.data_provider.get_historical_data(symbol, "W1", 52)  # V31.0
                    if df_w1 is not None:
                        print(f"   ✅ W1 data: {len(df_w1)} bars")
                        w1_result = self.smc_detector.calculate_w1_bias(df_w1)
                        w1_bias_map[symbol] = w1_result.get('bias', 'NEUTRAL')
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
                    setup = self.smc_detector.scan_for_setup(
                        symbol=symbol,
                        df_daily=df_daily,
                        df_4h=df_4h,
                        priority=priority,
                        df_1h=df_1h,  # V3.0: Pass 1H data for GBP pairs
                        debug=True    # ✅ V10.6: verbose reject messages
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

                    # V40.3 W1 INFO — annotare counter-trend, fără reject
                    setup = self.smc_detector.apply_w1_gate(setup, w1_bias_map.get(symbol, 'NEUTRAL'))

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
                    # V15.1 DEDUP FIX: Trimite alert DOAR pentru setup-uri NOI sau READY.
                    # Setup-urile re-evaluate (deja in monitoring) NU primesc alert repetat
                    # la fiecare scan — evitam spam Mon/Wed/Fri pentru aceeasi pereche.
                    if self.scanner_settings.get('telegram_alerts', True):
                        is_reevaluation = symbol in monitoring_symbols
                        if setup_status == 'READY':
                            tg_prefix = "🔥 READY TO EXECUTE"
                        else:
                            tg_prefix = "👁️ MONITORING (PÂNDĂ)"

                        # V15.2: Trimite chart pentru TOATE setup-urile valide (inclusiv re-evaluate)
                        # Re-evaluate primesc prefix diferit pt claritate in Telegram
                        if is_reevaluation and setup_status == 'MONITORING':
                            tg_prefix = "🔄 RE-EVALUAT (PÂNDĂ)"
                        print(f"   📸 {tg_prefix} — Generez chart pentru {symbol}...")
                        try:
                            self.telegram.send_setup_alert(
                                setup=setup,
                                df_daily=df_daily,
                                df_4h=df_4h,
                                df_1h=df_1h,
                                charts_mode='daily_only'  # V15.0: Silent Scan — doar Daily chart la scanare
                            )
                            print(f"   ✅ Chart trimis pe Telegram: {symbol} [{tg_prefix}] [DAILY ONLY]")
                        except Exception as e:
                            print(f"   ⚠️ Failed to send charts: {e}")
                    
                    print(f"✓ {symbol} adăugat în raportul de dimineață [{setup_status}]")
                else:
                    # V10.2: Setup respins — motivul exact a fost printat de smc_detector
                    # ── V31.0 BIAS FALLBACK ──────────────────────────────────────────────────
                    # Nu mai scriem direct în JSON. Colectăm în bias_fallback_entries[].
                    # save_monitoring_setups() face WIPE&OVERWRITE la final cu tot.
                    try:
                        _bias_dir = self.smc_detector.determine_daily_trend(df_daily, symbol=symbol)
                        if _bias_dir in ('bullish', 'bearish'):
                            _w1 = w1_bias_map.get(symbol, 'NEUTRAL')
                            _bias_trade_dir = 'buy' if _bias_dir == 'bullish' else 'sell'
                            _bf_confidence = 'NORMAL'
                            if _bias_dir == 'bullish' and _w1 == 'BEARISH':
                                _bf_confidence = 'LOW_W1_COUNTER_TREND'
                                print(
                                    f"⚠️ [V40.3 W1 INFO] {symbol}: bias fallback LONG — "
                                    f"⚠️ [COUNTER-TREND W1] (salvat cu confidence={_bf_confidence})"
                                )
                            print(f"📡 [V31.0 BIAS FALLBACK] {symbol}: bias={_bias_dir.upper()} → colectat WAITING_D1_PULLBACK")
                            bias_fallback_entries.append({
                                'symbol': symbol,
                                'direction': _bias_trade_dir,
                                'd1_bias_direction': _bias_dir,
                                'daily_bias': _bias_dir.upper(),
                                'setup_type': 'CONTINUATION',
                                'strategy_type': 'continuation',
                                'strategy_locked': True,
                                'daily_bias_active': True,
                                'confidence': _bf_confidence,
                                'w1_bias': _w1,
                                'poi_top': None,
                                'poi_bottom': None,
                                'fvg_top': None,
                                'fvg_bottom': None,
                                'daily_target_price': None,
                                'status': 'WAITING_D1_PULLBACK',
                                'setup_time': datetime.now().isoformat(),
                                'bias_fallback': True,
                            })
                            print(f"   ✅ [V31.0] {symbol} {_bias_trade_dir.upper()} → bias_fallback_entries ({len(bias_fallback_entries)} total)")
                        else:
                            print(f"⛔ {symbol} — NO SETUP + BIAS NEUTRAL [V10.2 REJECT: vezi log-ul ↑]")
                    except Exception as _bf_err:
                        print(f"⛔ {symbol} — NO SETUP [V10.2 REJECT: vezi log-ul ↑] | bias fallback error: {_bf_err}")
        
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
        active_setups_count = len(monitoring_setups)
        executed_positions = []
        all_open_positions = []
        open_position_symbols = set()  # Track which symbols have open positions
        try:
            with open('trade_history.json', 'r', encoding='utf-8') as f:
                trade_data = json.load(f)
                all_open_positions = trade_data.get('open_positions', [])
                # V8.2: If IGNORE_OPEN_POSITIONS is True, treat as if no positions exist
                if not IGNORE_OPEN_POSITIONS:
                    open_position_symbols = {p.get('symbol') for p in all_open_positions}
                    active_setups_count += len(all_open_positions)
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

        # Breakdown: setups cu vs fără poziție deschisă (pentru summary report)
        truly_new_setups   = [s for s in all_active_setups if s.symbol not in open_position_symbols]
        active_with_position = [s for s in all_active_setups if s.symbol in open_position_symbols]

        # V15.2 Option A: Breakdown corect — brand_new vs re_evaluated (era deja in monitoring)
        brand_new_setups   = [s for s in all_active_setups if s.symbol not in monitoring_symbols]
        re_evaluated_setups = [s for s in all_active_setups if s.symbol in monitoring_symbols]

        # SAVE first, then show final summary — V31.0: WIPE + bias fallback
        save_monitoring_setups(all_active_setups, bias_fallback_entries, daily_bias_map, w1_bias_map, symbol_price_map)

        # Now reload to get accurate count
        final_monitoring_count = 0
        try:
            with open('monitoring_setups.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # V8.0 FAILSAFE: Handle both formats
                if isinstance(data, dict):
                    final_monitoring_count = len(data.get("setups", []))
                elif isinstance(data, list):
                    final_monitoring_count = len(data)
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
            
            # Build setup symbols info for the report (V37.17: include bias fallback entries)
            setup_symbols = []
            _report_syms = set()
            for s in setups_found:
                direction_str = "buy" if s.daily_choch.direction == 'bullish' else "sell"
                strategy_str = getattr(s, 'strategy_type', 'UNKNOWN').upper()
                h4_locked = getattr(s, 'h4_structure_locked', getattr(s, 'h4_bias_locked', False))
                setup_symbols.append({
                    'symbol': s.symbol,
                    'direction': direction_str,
                    'strategy': strategy_str,
                    'h4_structure_locked': h4_locked,
                    'bias_fallback': False,
                })
                _report_syms.add(s.symbol)
            for entry in bias_fallback_entries:
                sym = entry.get('symbol')
                if not sym or sym in _report_syms:
                    continue
                setup_symbols.append({
                    'symbol': sym,
                    'direction': entry.get('direction', 'buy'),
                    'strategy': (entry.get('setup_type') or 'CONTINUATION').upper(),
                    'h4_structure_locked': False,
                    'bias_fallback': True,
                })
                _report_syms.add(sym)
            
            # Send the OFFICIAL scan report (mirrors console exactly)
            try:
                self.telegram.send_scan_report(
                    total_pairs=len(self.pairs),
                    new_setups_found=len(setups_found),
                    truly_new=len(brand_new_setups),
                    re_detected=len(re_evaluated_setups),
                    monitoring_count=final_monitoring_count,
                    open_positions=len(all_open_positions),
                    deep_sleep_active=deep_sleep_active,
                    deep_sleep_until=deep_sleep_until_str,
                    setup_symbols=setup_symbols
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
            
            # Download data (add 1H for SCALE_IN strategy)
            # V11.2: citim din pairs_config.json — NU mai hardcodăm 100
            d1_bars = self.scanner_settings.get('lookback_candles', {}).get('daily', 200)
            h4_bars = self.scanner_settings.get('lookback_candles', {}).get('h4', 200)
            h1_bars = self.scanner_settings.get('lookback_candles', {}).get('h1', 300)
            df_daily = self.data_provider.get_historical_data(symbol, "D1", d1_bars)
            df_4h = self.data_provider.get_historical_data(symbol, "H4", h4_bars)
            df_1h = self.data_provider.get_historical_data(symbol, "H1", h1_bars)  # NEW: 1H data
            
            if df_daily is None or df_4h is None:
                print(f"❌ Failed to download data for {symbol}")
                return None
            
            if df_1h is None:
                print(f"⚠️  Warning: 1H data unavailable for {symbol}, SCALE_IN disabled")
            
            # Run detection (pass df_1h for SCALE_IN validation)
            setup = self.smc_detector.scan_for_setup(
                symbol=symbol,
                df_daily=df_daily,
                df_4h=df_4h,
                df_1h=df_1h,  # NEW: pass 1H data
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
    """Normalize continuation vs reversal for SMART MERGE comparisons."""
    s = (val or 'continuation').lower()
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


def _price_in_daily_poi(price: float, stored: dict) -> bool:
    """True dacă prețul curent intersectează zona POI/FVG Daily salvată."""
    top = stored.get('poi_top') if stored.get('poi_top') is not None else stored.get('fvg_top')
    bottom = stored.get('poi_bottom') if stored.get('poi_bottom') is not None else stored.get('fvg_bottom')
    if top is None or bottom is None:
        return False
    lo, hi = min(float(top), float(bottom)), max(float(top), float(bottom))
    return lo <= float(price) <= hi


def _level_differs(old_val, new_val, rel_tol: float = 1e-6) -> bool:
    if old_val is None and new_val is None:
        return False
    if old_val is None or new_val is None:
        return True
    return abs(float(old_val) - float(new_val)) > max(abs(float(old_val)), abs(float(new_val)), 1.0) * rel_tol


def _structural_rehydrate_needed(old: dict, new: dict) -> bool:
    """V40.3: strategy flip sau niveluri structurale diferite → re-hidratare."""
    if _norm_strategy_type(old.get('strategy_type')) != _norm_strategy_type(new.get('strategy_type')):
        return True
    for key in ('poi_top', 'poi_bottom', 'daily_swing_low', 'daily_swing_high', 'daily_target_price'):
        if _level_differs(old.get(key), new.get(key)):
            return True
    return False


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
    if scan_status not in ('MONITORING', 'READY', 'WAITING_D1_PULLBACK', 'WAITING_4H_CHOCH', 'WAITING_1H_CHOCH'):
        scan_status = 'WAITING_D1_PULLBACK'
    return {
        "symbol": setup.symbol,
        "direction": direction,
        "daily_bias": setup.daily_choch.direction.upper(),
        "setup_type": (getattr(setup, 'strategy_type', 'continuation') or 'continuation').upper(),
        "strategy_type": getattr(setup, 'strategy_type', 'continuation'),
        "strategy_locked": True,
        "d1_bias_direction": setup.daily_choch.direction,
        "daily_bias_active": True,
        "confidence": getattr(setup, 'confidence', 'NORMAL'),
        "w1_bias": getattr(setup, 'w1_bias', 'NEUTRAL'),
        "poi_top": float(fvg_top) if fvg_top is not None else None,
        "poi_bottom": float(fvg_bottom) if fvg_bottom is not None else None,
        "fvg_top": float(fvg_top) if fvg_top is not None else None,
        "fvg_bottom": float(fvg_bottom) if fvg_bottom is not None else None,
        "daily_target_price": getattr(setup, 'daily_tp_price', None),
        "status": scan_status,
        "setup_time": setup_time_str,
        "priority": setup.priority,
        "swap_long": getattr(setup, 'swap_long', None),
        "swap_short": getattr(setup, 'swap_short', None),
        "swap_triple_day": getattr(setup, 'swap_triple_day', None),
        "daily_swing_low": getattr(setup, 'daily_swing_low', None),
        "daily_swing_high": getattr(setup, 'daily_swing_high', None),
    }


def save_monitoring_setups(
    setups: List[TradeSetup],
    bias_fallback: list = None,
    daily_bias_map: dict = None,
    w1_bias_map: dict = None,
    symbol_price_map: dict = None,
):
    """[V33 SMART MERGE] + V40.3 re-hidratare strategică + soft TTL 4 zile fără POI.
    Un pullback pe Daily poate dura zile — stergerea oarba de dimineata este interzisa.
    V40.3: W1 strict informativ; continuation↔reversal re-hidratează JSON; TTL 4d fără POI.

    Logica:
      1. Citim JSON existent.
      2. Pastram INTACTE paritati cu status: WAITING_D1_PULLBACK, MONITORING, READY,
         WAITING_4H_CHOCH, WAITING_1H_CHOCH, TRADE_OPEN.
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

    _SOFT_TTL_DAYS = 4

    # Status-uri active — PASTRATE INTACTE de la o zi la alta
    _ACTIVE_STATUSES = {
        'WAITING_D1_PULLBACK', 'MONITORING', 'READY',
        'WAITING_4H_CHOCH', 'WAITING_1H_CHOCH', 'TRADE_OPEN'
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
            if price is not None and _price_in_daily_poi(price, stored):
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

        # Pasul 2: Construim lista finala
        monitoring_setups = list(existing_active.values())  # Incepem cu ce era activ
        preserved_symbols = set(existing_active.keys())

        # Pasul 3: Adaugam setup-uri NOI din scanul de azi (numai daca nu exista deja)
        for setup in setups:
            if setup.status not in ("MONITORING", "READY", "WAITING_D1_PULLBACK",
                                    "WAITING_4H_CHOCH", "WAITING_1H_CHOCH"):
                continue

            direction = "buy" if setup.daily_choch.direction == "bullish" else "sell"

            _d1b = daily_bias_map.get(setup.symbol)
            if direction == 'buy' and _d1b == 'bearish':
                print(f"  ⛔ [V40 SAVE GUARD] {setup.symbol}: BUY blocat — D1 LOCK BEARISH")
                continue

            # Conflict guard
            open_dir = open_position_dir_map.get(setup.symbol)
            if open_dir and open_dir != direction:
                print(f"⛔ SAVE GUARD: {setup.symbol} — NOT saving {direction.upper()} setup, "
                      f"open {open_dir.upper()} position exists")
                continue

            setup_time_str = _setup_time_to_iso(setup.setup_time)

            if setup.symbol in preserved_symbols:
                _old = existing_active.get(setup.symbol, {})
                _old_dir = (_old.get('direction') or '').lower()
                if _old_dir and _old_dir != direction:
                    monitoring_setups = [s for s in monitoring_setups if s.get('symbol') != setup.symbol]
                    preserved_symbols.discard(setup.symbol)
                    existing_active.pop(setup.symbol, None)
                    print(
                        f"  🔄 [V40 BIAS FLIP] {setup.symbol}: {_old_dir.upper()} → {direction.upper()} "
                        f"— setup vechi eliminat (INVALIDATED_BIAS_FLIP)"
                    )
                else:
                    monitoring_setup = _trade_setup_to_monitoring_dict(setup, setup_time_str)
                    if _structural_rehydrate_needed(_old, monitoring_setup):
                        strategy_flipped = (
                            _norm_strategy_type(_old.get('strategy_type'))
                            != _norm_strategy_type(monitoring_setup.get('strategy_type'))
                        )
                        if not strategy_flipped:
                            monitoring_setup['setup_time'] = _old.get('setup_time', setup_time_str)
                        monitoring_setups = [
                            s for s in monitoring_setups if s.get('symbol') != setup.symbol
                        ]
                        monitoring_setups.append(monitoring_setup)
                        existing_active[setup.symbol] = monitoring_setup
                        _chg = 'strategy flip' if strategy_flipped else 'niveluri structurale'
                        print(
                            f"  🔄 [V40.3 RE-HYDRATE] {setup.symbol}: {_chg} "
                            f"({_norm_strategy_type(_old.get('strategy_type'))} → "
                            f"{_norm_strategy_type(monitoring_setup.get('strategy_type'))}) — JSON actualizat"
                        )
                    else:
                        print(
                            f"  ✅ [V40.3 MERGE] {setup.symbol}: structură neschimbată "
                            f"({existing_active.get(setup.symbol, {}).get('status')}) — păstrat"
                        )
                    continue

            monitoring_setup = _trade_setup_to_monitoring_dict(setup, setup_time_str)
            monitoring_setups.append(monitoring_setup)
            preserved_symbols.add(setup.symbol)

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
                    _old_st = _norm_strategy_type(_old.get('strategy_type'))
                    _new_st = _norm_strategy_type(_new_fb.get('strategy_type'))
                    if _old_st != _new_st or _structural_rehydrate_needed(_old, _new_fb):
                        monitoring_setups = [s for s in monitoring_setups if s.get('symbol') != sym]
                        _new_fb['setup_time'] = _old.get('setup_time', _new_fb.get('setup_time'))
                        if _old_st != _new_st:
                            _new_fb['setup_time'] = entry.get('setup_time', datetime.now().isoformat())
                        monitoring_setups.append(_new_fb)
                        existing_active[sym] = _new_fb
                        print(f"  🔄 [V40.3 RE-HYDRATE] {sym}: bias fallback actualizat")
                    else:
                        print(f"  ✅ [V40.3 MERGE] {sym}: bias fallback neschimbat — păstrat")
                    continue
            open_dir = open_position_dir_map.get(sym)
            if open_dir and open_dir != direction:
                print(f"⛔ SAVE GUARD: {sym} — NOT saving bias fallback {direction.upper()}, "
                      f"open {open_dir.upper()} position exists")
                continue
            monitoring_setups.append(entry)
            if sym:
                preserved_symbols.add(sym)

        # Atomic write
        _ms_write = {
            "setups": monitoring_setups,
            "last_updated": datetime.now().isoformat()
        }
        _ms_tmp = 'monitoring_setups.json.tmp'
        with open(_ms_tmp, 'w', encoding='utf-8') as f:
            json.dump(_ms_write, f, indent=2)
        import os as _ms_os
        _ms_os.replace(_ms_tmp, 'monitoring_setups.json')

        new_count = max(0, len(monitoring_setups) - len(existing_active))
        print(f"\n💾 [V40.3 SMART MERGE] {len(monitoring_setups)} total — "
              f"{len(existing_active)} pastrate/rehidratate + {new_count} noi din scan de azi")

    except Exception as e:
        print(f"❌ Error saving monitoring setups: {e}")


def main():
    """Main entry point"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Daily Scanner for Glitch in Matrix V8.2')
    parser.add_argument(
        '--ignore-open-positions',
        action='store_true',
        help='Force scan all pairs even if they have open positions (for testing/audit)'
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='Run in live mode (connects to cTrader on port 8010)'
    )
    args = parser.parse_args()
    
    # Set global flag
    global IGNORE_OPEN_POSITIONS
    IGNORE_OPEN_POSITIONS = args.ignore_open_positions
    
    if IGNORE_OPEN_POSITIONS:
        print("⚠️  AUDIT MODE: Ignoring open positions check - scanning ALL pairs\n")
    
    scanner = DailyScanner()
    
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
