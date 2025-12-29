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
            
        self.smc_detector = SMCDetector(swing_lookback=5)
        self.telegram = TelegramNotifier()
        
        # Load pairs configuration
        with open('pairs_config.json', 'r') as f:
            config = json.load(f)
            self.pairs = config['pairs']
            self.scanner_settings = config['scanner_settings']
    
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
        
        # Connect to MT5
        if not self.data_provider.connect():
            error_msg = "Failed to connect to MT5"
            print(f"❌ {error_msg}")
            self.telegram.send_error_alert(error_msg)
            return []
        
        setups_found = []
        
        try:
            # Scan each pair
            for pair_config in self.pairs:
                symbol = pair_config['mt5_symbol']
                priority = pair_config['priority']
                
                print(f"\n🔍 Scanning {symbol} (Priority {priority})...")
                
                # Download Daily data
                df_daily = self.data_provider.get_historical_data(
                    symbol, 
                    "D1", 
                    self.scanner_settings['lookback_candles']['daily']
                )
                
                if df_daily is None:
                    print(f"⚠️ Skipping {symbol} - no Daily data")
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
                
                # Run SMC detection
                setup = self.smc_detector.scan_for_setup(
                    symbol=symbol,
                    df_daily=df_daily,
                    df_4h=df_4h,
                    priority=priority
                )
                
                if setup:
                    print(f"🎯 SETUP FOUND on {symbol}!")
                    setups_found.append(setup)
                    
                    # Send Telegram alert
                    if self.scanner_settings['telegram_alerts']:
                        print(f"📱 Sending Telegram alert for {symbol}...")
                        self.telegram.send_setup_alert(setup, df_daily, df_4h)
                else:
                    print(f"✓ {symbol} - No setup detected")
        
        finally:
            # Disconnect MT5 unless keep_connection=True
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
        
        # FILTER OUT setups that are already in open positions (don't report as NEW)
        new_setups = [s for s in setups_found if s.symbol not in open_position_symbols]

        # Send daily summary
        print("\n" + "="*60)
        print(f"✅ Scan Complete!")
        print(f"📊 Total Pairs Scanned: {len(self.pairs)}")
        print(f"🎯 New Setups Found (not already open): {len(new_setups)}")
        print(f"📋 Total Active Setups: {active_setups_count}")
        print(f"    └─ Monitoring: {len(monitoring_setups)} | Executed & Open: {len(all_open_positions)}")
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
                setups_found=len(new_setups),
                active_setups=combined_active
            )
        # DEBUG: Print status for each setup found
        print('\n--- DEBUG: Status setup-uri returnate de run_daily_scan ---')
        for s in new_setups:
            print(f"{getattr(s, 'symbol', 'N/A')}: status={getattr(s, 'status', 'N/A')}")
        print('----------------------------------------------------------')
        return new_setups
    
    def scan_single_pair(self, symbol: str) -> Optional[TradeSetup]:
        """Scan a single pair (for testing)"""
        print(f"\n🔍 Testing single pair: {symbol}")
        
        if not self.data_provider.connect():
            print("❌ Failed to connect to MT5")
            return None
        
        try:
            # Find pair config
            pair_config = next((p for p in self.pairs if p['symbol'] == symbol), None)
            
            if not pair_config:
                print(f"❌ {symbol} not found in pairs_config.json")
                return None
            
            # Download data
            df_daily = self.data_provider.get_historical_data(symbol, "D1", 100)
            df_4h = self.data_provider.get_historical_data(symbol, "H4", 200)
            
            if df_daily is None or df_4h is None:
                print(f"❌ Failed to download data for {symbol}")
                return None
            
            # Run detection
            setup = self.smc_detector.scan_for_setup(
                symbol=symbol,
                df_daily=df_daily,
                df_4h=df_4h,
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
    """Salvează setup-urile MONITORING în monitoring_setups.json
    
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
        
        # Add/update with new setups
        for setup in setups:
            if setup.status == "MONITORING":
                monitoring_setup = {
                    "symbol": setup.symbol,
                    "direction": "buy" if setup.daily_choch.direction == "bullish" else "sell",
                    "entry_price": setup.entry_price,
                    "stop_loss": setup.stop_loss,
                    "take_profit": setup.take_profit,
                    "risk_reward": setup.risk_reward,
                    "strategy_type": setup.strategy_type,
                    "setup_time": setup.setup_time.isoformat(),
                    "priority": setup.priority,
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
