"""
Daily Scanner for ForexGod - Glitch Signals
Scans all pairs for "Glitch in Matrix" setups at 00:05 daily
"""

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from typing import List, Optional, Dict
from dotenv import load_dotenv

from smc_detector import SMCDetector, TradeSetup
from telegram_notifier import TelegramNotifier

load_dotenv()


class MT5DataProvider:
    """Downloads historical data from MetaTrader 5"""
    
    def __init__(self):
        self.login = int(os.getenv('MT5_LOGIN'))
        self.password = os.getenv('MT5_PASSWORD')
        self.server = os.getenv('MT5_SERVER')
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to MT5"""
        try:
            if not mt5.initialize():
                print(f"❌ MT5 initialize() failed: {mt5.last_error()}")
                return False
            
            authorized = mt5.login(self.login, password=self.password, server=self.server)
            
            if not authorized:
                print(f"❌ MT5 login failed: {mt5.last_error()}")
                mt5.shutdown()
                return False
            
            account_info = mt5.account_info()
            if account_info:
                print(f"✅ MT5 Connected: Account #{account_info.login}, Balance: ${account_info.balance}")
                self.connected = True
                return True
            else:
                print(f"❌ Failed to get account info: {mt5.last_error()}")
                return False
        
        except Exception as e:
            print(f"❌ MT5 connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            print("🔌 MT5 disconnected")
            self.connected = False
    
    def get_historical_data(
        self, 
        symbol: str, 
        timeframe: str, 
        num_candles: int
    ) -> Optional[pd.DataFrame]:
        """
        Download historical candlestick data
        
        Args:
            symbol: Trading pair (e.g., "EURUSD")
            timeframe: "D1" (Daily) or "H4" (4-hour)
            num_candles: Number of candles to retrieve
        
        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        if not self.connected:
            print("❌ MT5 not connected")
            return None
        
        try:
            # Convert timeframe string to MT5 constant
            tf_map = {
                "D1": mt5.TIMEFRAME_D1,
                "H4": mt5.TIMEFRAME_H4,
                "H1": mt5.TIMEFRAME_H1,
                "M15": mt5.TIMEFRAME_M15
            }
            
            if timeframe not in tf_map:
                print(f"❌ Invalid timeframe: {timeframe}")
                return None
            
            mt5_timeframe = tf_map[timeframe]
            
            # Get current time and calculate start time
            to_date = datetime.now()
            
            # Download data
            rates = mt5.copy_rates_from(symbol, mt5_timeframe, to_date, num_candles)
            
            if rates is None or len(rates) == 0:
                print(f"⚠️ No data for {symbol} on {timeframe}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Keep only necessary columns
            df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
            df = df.rename(columns={'tick_volume': 'volume'})
            
            print(f"✅ Downloaded {len(df)} candles for {symbol} ({timeframe})")
            
            return df
        
        except Exception as e:
            print(f"❌ Error downloading data for {symbol}: {e}")
            return None


class DailyScanner:
    """Main scanner that runs daily at 00:05"""
    
    def __init__(self):
        self.data_provider = MT5DataProvider()
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
        
        # Send daily summary
        print("\n" + "="*60)
        print(f"✅ Scan Complete!")
        print(f"📊 Total Pairs Scanned: {len(self.pairs)}")
        print(f"🎯 Setups Found: {len(setups_found)}")
        print("="*60 + "\n")
        
        if self.scanner_settings['telegram_alerts']:
            self.telegram.send_daily_summary(
                scanned_pairs=len(self.pairs),
                setups_found=len(setups_found)
            )
        
        return setups_found
    
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
