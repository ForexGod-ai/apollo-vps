"""
Daily Scanner for ForexGod - Glitch Signals
Scans all pairs for "Glitch in Matrix" setups at 00:05 daily
Uses IC Markets data via cTrader cBot HTTP server
"""

import pandas as pd
from datetime import datetime, timedelta
import json
import os
from typing import List, Optional, Dict
from dotenv import load_dotenv
from loguru import logger

from smc_detector import SMCDetector, TradeSetup
from telegram_notifier import TelegramNotifier
from ctrader_cbot_client import CTraderCBotClient
from strategy_optimizer import StrategyOptimizer
from ai_probability_analyzer import AIProbabilityAnalyzer

load_dotenv()


class CTraderDataProvider:
    """Downloads historical data from cTrader via cBot HTTP server"""
    
    def __init__(self):
        self.client = CTraderCBotClient()
        self.connected = False
    
    def connect(self) -> bool:
        """Check if cBot server is running"""
        try:
            if self.client.is_available():
                print("✅ cTrader cBot connected (IC Markets)")
                self.connected = True
                return True
            else:
                print("❌ cTrader cBot not running. Please start MarketDataProvider cBot in cTrader.")
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
                print(f"✅ Downloaded {len(df)} candles for {symbol} ({timeframe}) from IC Markets")
                return df
            else:
                print(f"⚠️ No data for {symbol} on {timeframe}")
                return None
                
        except Exception as e:
            print(f"❌ Error downloading data for {symbol}: {e}")
            return None


class DailyScanner:
    """Main scanner that runs daily at 00:05"""
    
    def __init__(self, use_ctrader: bool = True):
        # Choose data provider
        if use_ctrader:
            self.data_provider = CTraderDataProvider()
            print("📊 Using cTrader cBot for market data (IC Markets)")
        else:
            self.data_provider = MT5DataProvider()
            print("📊 Using MT5 for market data")
            
        # V8.0: Initialize SMCDetector with ATR Prominence + Premium/Discount filters
        self.smc_detector = SMCDetector(
            swing_lookback=5,      # Standard swing validation (5 bars each side)
            atr_multiplier=1.5     # V7.0: ATR Prominence Filter (1.5x ATR threshold)
        )
        print("✅ SMC Detector V8.0 initialized:")
        print("   🔥 ATR Prominence Filter: 1.5x ATR (eliminates micro-swings)")
        print("   🎯 Premium/Discount Zone: 50% Fibonacci (only deep retracements)")
        
        self.telegram = TelegramNotifier()
        
        # NEW: Load ML optimizer for setup scoring
        self.ml_optimizer = StrategyOptimizer()
        self.learned_rules = self._load_learned_rules()
        
        # NEW: Load AI Probability Analyzer (1-10 scoring)
        self.ai_analyzer = AIProbabilityAnalyzer()
        
        # Load pairs configuration
        with open('pairs_config.json', 'r') as f:
            config = json.load(f)
            self.pairs = config['pairs']
            self.scanner_settings = config['scanner_settings']
    
    def _load_learned_rules(self) -> dict:
        """Load learned rules from ML optimizer"""
        try:
            with open('learned_rules.json', 'r') as f:
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
        print("🔥 ForexGod - Glitch Daily Scanner Starting...")
        print(f"⏰ Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60 + "\n")
        
        # Connect to cTrader
        if not self.data_provider.connect():
            error_msg = "Failed to connect to cTrader cBot API (localhost:8767)"
            print(f"❌ {error_msg}")
            self.telegram.send_error_alert(error_msg)
            return []
        
        setups_found = []
        
        # V3.0: Load existing monitoring setups to re-evaluate their status
        monitoring_symbols = set()
        try:
            with open('monitoring_setups.json', 'r') as f:
                data = json.load(f)
                existing_setups = data.get("setups", [])
                monitoring_symbols = {s['symbol'] for s in existing_setups if s.get('status') == 'MONITORING'}
                if monitoring_symbols:
                    print(f"\n🔄 Re-evaluating {len(monitoring_symbols)} MONITORING setups: {', '.join(monitoring_symbols)}")
        except FileNotFoundError:
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
                    self.scanner_settings['lookback_candles']['daily']
                )
                
                if df_daily is None or df_daily.empty:
                    print(f"⚠️  Skipping {symbol} - no Daily data")
                    # 🚨 AUDIT: Log data errors for forensics
                    try:
                        with open('data_errors.log', 'a') as f:
                            f.write(f"{datetime.now().isoformat()} - {symbol} - D1 data unavailable\n")
                    except Exception as log_err:
                        print(f"⚠️  Could not write to data_errors.log: {log_err}")
                    continue
                
                # Download 4H data
                df_4h = self.data_provider.get_historical_data(
                    symbol, 
                    "H4", 
                    self.scanner_settings['lookback_candles']['h4']
                )
                
                if df_4h is None:
                    print(f"⚠️ Skipping {symbol} - no 4H data")
                    continue
                
                # V3.1 SCALE_IN: Download 1H data for ALL pairs (Entry 1 validation)
                print(f"   📊 Downloading 1H data (SCALE_IN strategy)...")
                df_1h = self.data_provider.get_historical_data(
                    symbol,
                    "H1",
                    self.scanner_settings['lookback_candles'].get('h1', 225)
                )
                if df_1h is None:
                    print(f"⚠️ Warning: {symbol} has no 1H data (Entry 1 disabled)")
                
                # GBP pairs still need 1H for additional validation
                is_gbp = 'GBP' in symbol
                
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
                        df_1h=df_1h  # V3.0: Pass 1H data for GBP pairs
                    )
                except Exception as scan_error:
                    print(f"⚠️  Error scanning {symbol}: {scan_error}")
                    # Log error but continue to next pair
                    try:
                        with open('scanner_errors.log', 'a') as f:
                            f.write(f"{datetime.now().isoformat()} - {symbol} - {scan_error}\n")
                    except:
                        pass
                    setup = None
                
                if setup:
                    print(f"🎯 SETUP FOUND on {symbol}!")
                    
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
                    
                    # V8.0: Log filter validation status
                    print(f"   ✅ V8.0 Filters PASSED:")
                    print(f"      • ATR Prominence: Swing validated (1.5x ATR)")
                    print(f"      • Premium/Discount: FVG in correct zone (>50% retracement)")
                    
                    # V3.3: ALWAYS send chart alert when setup is found
                    # User expects automatic Telegram notifications with 3 charts for EVERY scan
                    if self.scanner_settings.get('telegram_alerts', True):
                        is_reevaluation = symbol in monitoring_symbols
                        status = "Re-evaluating" if is_reevaluation else "New setup"
                        print(f"   📸 {status} - Generating and sending charts for {symbol}...")
                        try:
                            self.telegram.send_setup_alert(
                                setup=setup,
                                df_daily=df_daily,
                                df_4h=df_4h,
                                df_1h=df_1h
                            )
                            print(f"   ✅ Charts sent to Telegram for {symbol}")
                        except Exception as e:
                            print(f"   ⚠️ Failed to send charts: {e}")
                    
                    print(f"✓ {symbol} added to morning scan report")
                else:
                    # V8.0: Setup rejected by one or more filters
                    # Could be:
                    # - No CHoCH/BOS detected
                    # - No FVG found
                    # - ATR Filter: Swing not prominent enough
                    # - Premium/Discount: FVG in wrong zone (shallow retracement)
                    # - FVG quality check failed
                    # - 4H confirmation missing
                    print(f"✓ {symbol} - No valid setup (rejected by V8.0 filters or no signal)")
        
        finally:
            # Disconnect cTrader unless keep_connection=True
            if not keep_connection:
                self.data_provider.disconnect()
        
        # Load monitoring setups + check for recently executed setups still in open positions
        monitoring_setups = []
        try:
            with open('monitoring_setups.json', 'r') as f:
                data = json.load(f)
                monitoring_setups = data.get("setups", [])
        except FileNotFoundError:
            pass  # No existing file
        
        # Include ALL open positions from trade_history.json as active setups
        active_setups_count = len(monitoring_setups)
        executed_positions = []
        all_open_positions = []
        open_position_symbols = set()  # Track which symbols have open positions
        try:
            with open('trade_history.json', 'r') as f:
                trade_data = json.load(f)
                all_open_positions = trade_data.get('open_positions', [])
                open_position_symbols = {p.get('symbol') for p in all_open_positions}
                active_setups_count += len(all_open_positions)
                logger.info(f"📊 Found {len(all_open_positions)} open positions: {[p.get('symbol') for p in all_open_positions]}")
        except Exception as e:
            logger.debug(f"Could not check open positions: {e}")
        
        # NEW LOGIC: Don't filter out setups with open positions
        # They need to stay in monitoring until TP/SL is hit
        # Split into: truly_new (no position) and active_with_position (has position, still monitoring)
        truly_new_setups = [s for s in setups_found if s.symbol not in open_position_symbols]
        active_with_position = [s for s in setups_found if s.symbol in open_position_symbols]
        
        # All setups (new + active with positions) should be saved for monitoring
        all_active_setups = setups_found  # Keep ALL detected setups active

        # SAVE first, then show final summary
        save_monitoring_setups(all_active_setups)
        
        # Now reload to get accurate count
        final_monitoring_count = 0
        try:
            with open('monitoring_setups.json', 'r') as f:
                data = json.load(f)
                final_monitoring_count = len(data.get("setups", []))
        except:
            pass
        
        # Send daily summary AFTER saving
        print("\n" + "="*60)
        print(f"✅ Scan Complete!")
        print(f"📊 Total Pairs Scanned: {len(self.pairs)}")
        print(f"🆕 New Setups Found: {len(setups_found)}")
        print(f"    └─ Truly New (no position): {len(truly_new_setups)}")
        print(f"    └─ Re-detected (has position): {len(active_with_position)}")
        print(f"📋 Total Active Tracking:")
        print(f"    └─ Saved in Monitoring: {final_monitoring_count}")
        print(f"    └─ Open Positions: {len(all_open_positions)}")
        print("="*60 + "\n")

        if self.scanner_settings['telegram_alerts']:
            # Create combined active setups list for Telegram
            combined_active = monitoring_setups.copy()
            # Add ALL open positions info, calculând corect R:R
            for pos in all_open_positions:
                entry = pos.get('entry_price', 0)
                sl = pos.get('stop_loss', 0)
                tp = pos.get('take_profit', 0)
                direction = str(pos.get('direction', 'buy')).strip().lower()
                # Calcul R:R: (|TP-Entry|) / (|Entry-SL|), protejat la div zero
                risk = abs(entry - sl)
                reward = abs(tp - entry)
                rr = round(reward / risk, 2) if risk > 0 else 0
                combined_active.append({
                    'symbol': pos.get('symbol', 'N/A'),
                    'direction': pos.get('direction', 'buy'),
                    'entry_price': entry,
                    'status': 'EXECUTED',
                    'ticket': pos.get('ticket', 'N/A'),
                    'profit': pos.get('profit', 0),
                    'risk_reward': rr
                })
            self.telegram.send_daily_summary(
                scanned_pairs=len(self.pairs),
                setups_found=len(truly_new_setups),  # Only truly new setups in summary
                active_setups=combined_active
            )
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
            df_daily = self.data_provider.get_historical_data(symbol, "D1", 100)
            df_4h = self.data_provider.get_historical_data(symbol, "H4", 200)
            df_1h = self.data_provider.get_historical_data(symbol, "H1", 225)  # NEW: 1H data
            
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
                priority=pair_config['priority']
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


def save_monitoring_setups(setups: List[TradeSetup]):
    """Salvează setup-urile MONITORING și READY în monitoring_setups.json
    
    V3.0: Salvăm AMBELE statusuri:
    - MONITORING: așteptăm 4H CHoCH + price in FVG
    - READY: poate fi executat (4H confirmat + price în FVG)
    
    IMPORTANT: Păstrează setups existente și adaugă doar pe cele noi.
    Doar dacă același symbol are setup nou, îl înlocuiește.
    """
    try:
        # Load existing setups FIRST
        existing_setups = {}
        try:
            with open('monitoring_setups.json', 'r') as f:
                data = json.load(f)
                for setup in data.get("setups", []):
                    existing_setups[setup["symbol"]] = setup
        except FileNotFoundError:
            pass  # No existing file, start fresh
        
        # Add/update with new setups (both MONITORING and READY)
        for setup in setups:
            # V3.0: Save BOTH MONITORING and READY status
            if setup.status in ["MONITORING", "READY"]:
                # Convert setup_time to proper datetime string
                if isinstance(setup.setup_time, (int, float)):
                    setup_time_str = datetime.fromtimestamp(setup.setup_time).isoformat()
                elif isinstance(setup.setup_time, str):
                    setup_time_str = setup.setup_time
                elif hasattr(setup.setup_time, 'isoformat'):
                    setup_time_str = setup.setup_time.isoformat()
                else:
                    setup_time_str = datetime.now().isoformat()
                
                monitoring_setup = {
                    "symbol": setup.symbol,
                    "direction": "buy" if setup.daily_choch.direction == "bullish" else "sell",
                    "entry_price": setup.entry_price,
                    "stop_loss": setup.stop_loss,
                    "take_profit": setup.take_profit,
                    "risk_reward": setup.risk_reward,
                    "strategy_type": setup.strategy_type,
                    "setup_time": setup_time_str,
                    "priority": setup.priority,
                    "status": setup.status,  # V3.0: Include status field
                    "fvg_zone_top": setup.fvg.top if setup.fvg else None,
                    "fvg_zone_bottom": setup.fvg.bottom if setup.fvg else None,
                    "lot_size": 0.01  # Default lot size
                }
                existing_setups[setup.symbol] = monitoring_setup  # Update/add
        
        # Convert back to list
        monitoring_setups = list(existing_setups.values())
        
        # ALWAYS save (even if empty, to update timestamp)
        # But if we have setups, they should persist
        with open('monitoring_setups.json', 'w') as f:
            json.dump({
                "setups": monitoring_setups,
                "last_updated": datetime.now().isoformat()
            }, f, indent=2)
        
        if monitoring_setups:
            print(f"\n💾 Saved {len(monitoring_setups)} setup(s) to MONITORING (kept existing + added new)")
        else:
            print(f"\n💾 No monitoring setups (file cleared)")
        
    except Exception as e:
        print(f"❌ Error saving monitoring setups: {e}")


def main():
    """Main entry point"""
    scanner = DailyScanner()
    
    # Test Telegram connection first
    print("🧪 Testing Telegram connection...")
    if scanner.telegram.test_connection():
        print("✅ Telegram connected successfully!\n")
    else:
        print("⚠️ Telegram connection failed - check .env configuration\n")
    
    # Run full daily scan
    setups = scanner.run_daily_scan()
    
    # ALWAYS save monitoring setups (preserves existing + adds new)
    # Even if setups is empty, we keep existing ones
    save_monitoring_setups(setups if setups else [])
    
    # Print summary
    if setups:
        print("\n📋 SETUPS SUMMARY:")
        for i, setup in enumerate(setups, 1):
            direction = "LONG" if setup.daily_choch.direction == 'bullish' else "SHORT"
            status = f"[{setup.status}]"
            print(f"{i}. {setup.symbol} - {direction} @ {setup.entry_price:.5f} (R:R 1:{setup.risk_reward:.2f}) {status}")


if __name__ == "__main__":
    # For testing single pair:
    # scanner = DailyScanner()
    # scanner.scan_single_pair("GBPUSD")
    
    # For full daily scan:
    main()

import os

def get_active_positions(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r') as f:
        return json.load(f)

def format_telegram_active_setups(positions):
    if not positions:
        return 'No active positions in cTrader.'
    msg = '🎯 ACTIVE SETUPS (cTrader Sync):\n'
    for pos in positions:
        direction = 'LONG' if pos['direction'] == 'buy' else 'SHORT'
        msg += f"• {pos['symbol']} - {direction}\n  Entry: {pos['entry_price']} | Vol: {pos['volume']}\n"
    return msg

# La finalul scanării, trimite active setups din cTrader
ACTIVE_POSITIONS_FILE = '/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/active_positions.json'
active_positions = get_active_positions(ACTIVE_POSITIONS_FILE)
active_setups_message = format_telegram_active_setups(active_positions)
print(active_setups_message)
# Dacă vrei să trimiți și aici mesajul pe Telegram, decomentează liniile de mai jos:
# from telegram_notifier import TelegramNotifier
# telegram = TelegramNotifier()
# telegram.send_message(active_setups_message)
