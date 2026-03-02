#!/usr/bin/env python3
"""
🎯 GLITCH IN MATRIX - MONITORING RADAR V6.0
✨ by ФорексГод ✨

Real-time radar pentru setup-uri în așteptare.
Monitorizează distanța până la FVG zones și status-ul live.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from ctrader_cbot_client import CTraderCBotClient
from loguru import logger
import sys

# Configure logger
logger.remove()
logger.add(sys.stderr, level="ERROR")  # Only errors to console


@dataclass
class MonitoringSetup:
    """Setup în monitoring cu toate detaliile necesare"""
    symbol: str
    direction: str  # 'buy' or 'sell'
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    status: str
    fvg_zone_top: float
    fvg_zone_bottom: float
    setup_time: datetime
    strategy_type: str
    
    # Optional fields
    choch_1h_detected: bool = False
    entry1_filled: bool = False
    pullback_status: Optional[str] = None


class MonitoringRadar:
    """🎯 Real-time Monitoring Radar pentru Glitch in Matrix"""
    
    def __init__(self):
        self.monitoring_file = Path("monitoring_setups.json")
        self.client = CTraderCBotClient()
        
        # Pip values per symbol type
        self.pip_multipliers = {
            'JPY': 0.01,      # JPY pairs: 1 pip = 0.01
            'DEFAULT': 0.0001  # Most pairs: 1 pip = 0.0001
        }
    
    def get_pip_value(self, symbol: str) -> float:
        """Get pip value for symbol"""
        if 'JPY' in symbol:
            return self.pip_multipliers['JPY']
        return self.pip_multipliers['DEFAULT']
    
    def calculate_pips(self, symbol: str, price1: float, price2: float) -> float:
        """Calculate pip distance between two prices"""
        pip_value = self.get_pip_value(symbol)
        return abs(price1 - price2) / pip_value
    
    def load_monitoring_setups(self) -> List[MonitoringSetup]:
        """Load all setups from monitoring_setups.json"""
        if not self.monitoring_file.exists():
            print(f"❌ File not found: {self.monitoring_file}")
            return []
        
        with open(self.monitoring_file, 'r') as f:
            data = json.load(f)
        
        setups = []
        for setup_data in data.get('setups', []):
            # Skip expired setups
            if setup_data.get('status') == 'EXPIRED':
                continue
            
            # Parse datetime
            setup_time_str = setup_data.get('setup_time', '')
            try:
                setup_time = datetime.fromisoformat(setup_time_str)
            except:
                setup_time = datetime.now()
            
            setup = MonitoringSetup(
                symbol=setup_data.get('symbol', ''),
                direction=setup_data.get('direction', ''),
                entry_price=setup_data.get('entry_price', 0.0),
                stop_loss=setup_data.get('stop_loss', 0.0),
                take_profit=setup_data.get('take_profit', 0.0),
                risk_reward=setup_data.get('risk_reward', 0.0),
                status=setup_data.get('status', 'UNKNOWN'),
                fvg_zone_top=setup_data.get('fvg_zone_top', 0.0),
                fvg_zone_bottom=setup_data.get('fvg_zone_bottom', 0.0),
                setup_time=setup_time,
                strategy_type=setup_data.get('strategy_type', 'unknown'),
                choch_1h_detected=setup_data.get('choch_1h_detected', False),
                entry1_filled=setup_data.get('entry1_filled', False),
                pullback_status=setup_data.get('pullback_status')
            )
            setups.append(setup)
        
        return setups
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current live price from cTrader"""
        try:
            df = self.client.get_historical_data(symbol, 'M1', 1)
            if df is not None and len(df) > 0:
                return float(df['close'].iloc[-1])
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
        return None
    
    def calculate_status(self, setup: MonitoringSetup, current_price: float) -> Dict:
        """Calculate live status based on current price vs FVG zone"""
        fvg_middle = (setup.fvg_zone_top + setup.fvg_zone_bottom) / 2
        fvg_size_pips = self.calculate_pips(
            setup.symbol, 
            setup.fvg_zone_top, 
            setup.fvg_zone_bottom
        )
        
        # Calculate distance to FVG zone
        if setup.direction == 'sell':
            # For SHORT: waiting for price to pullback UP to FVG
            if current_price > setup.fvg_zone_top:
                # Price ABOVE FVG (inside or above)
                distance_pips = self.calculate_pips(
                    setup.symbol,
                    current_price,
                    setup.fvg_zone_top
                )
                status_icon = "🟢"
                status_text = "🚨 ÎN ZONĂ! Scanează 4H"
                status_color = "green"
            elif current_price < setup.fvg_zone_bottom:
                # Price BELOW FVG (too far down)
                distance_pips = self.calculate_pips(
                    setup.symbol,
                    setup.fvg_zone_bottom,
                    current_price
                )
                status_icon = "🔵"
                status_text = "Așteaptă Pullback UP"
                status_color = "blue"
            else:
                # Price INSIDE FVG zone
                distance_pips = self.calculate_pips(
                    setup.symbol,
                    current_price,
                    fvg_middle
                )
                status_icon = "🟢"
                status_text = "🚨 ÎN ZONĂ! Scanează 4H"
                status_color = "green"
        
        else:  # 'buy'
            # For LONG: waiting for price to pullback DOWN to FVG
            if current_price < setup.fvg_zone_bottom:
                # Price BELOW FVG (inside or below)
                distance_pips = self.calculate_pips(
                    setup.symbol,
                    setup.fvg_zone_bottom,
                    current_price
                )
                status_icon = "🟢"
                status_text = "🚨 ÎN ZONĂ! Scanează 4H"
                status_color = "green"
            elif current_price > setup.fvg_zone_top:
                # Price ABOVE FVG (too far up)
                distance_pips = self.calculate_pips(
                    setup.symbol,
                    current_price,
                    setup.fvg_zone_top
                )
                status_icon = "🔵"
                status_text = "Așteaptă Pullback DOWN"
                status_color = "blue"
            else:
                # Price INSIDE FVG zone
                distance_pips = self.calculate_pips(
                    setup.symbol,
                    fvg_middle,
                    current_price
                )
                status_icon = "🟢"
                status_text = "🚨 ÎN ZONĂ! Scanează 4H"
                status_color = "green"
        
        # Check if setup is stale (older than 7 days)
        age_days = (datetime.now() - setup.setup_time).days
        if age_days > 7:
            status_icon = "⚠️"
            status_text = f"Setup Vechi ({age_days}d)"
            status_color = "yellow"
        
        # Check if entry already filled
        if setup.entry1_filled:
            status_icon = "✅"
            status_text = "Entry 1 FILLED"
            status_color = "cyan"
        
        return {
            'icon': status_icon,
            'text': status_text,
            'color': status_color,
            'distance_pips': distance_pips,
            'fvg_size_pips': fvg_size_pips,
            'age_days': age_days
        }
    
    def print_radar_table(self):
        """Print professional monitoring radar table"""
        setups = self.load_monitoring_setups()
        
        if not setups:
            print("\n❌ No active setups in monitoring\n")
            return
        
        print("\n" + "="*120)
        print("🎯 GLITCH IN MATRIX - MONITORING RADAR V6.0")
        print("✨ by ФорексГод ✨")
        print("="*120)
        print(f"📅 Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Active Setups: {len(setups)}")
        print("="*120)
        
        # Header
        print(f"\n{'💱 SIMBOL':<12} {'DIR':<6} {'🎯 ZONA FVG':<25} "
              f"{'📍 PREȚ':<12} {'📏 DIST':<12} {'🔎 STATUS LIVE':<35} {'⏰ AGE':<8}")
        print("-"*120)
        
        for setup in setups:
            # Get current price
            current_price = self.get_current_price(setup.symbol)
            
            if current_price is None:
                print(f"{setup.symbol:<12} {'❌ Nu pot obține preț live':<100}")
                continue
            
            # Direction icon
            dir_icon = "🔴" if setup.direction == 'sell' else "🟢"
            dir_text = "SHORT" if setup.direction == 'sell' else "LONG"
            
            # FVG Zone
            fvg_zone = f"{setup.fvg_zone_top:.5f} - {setup.fvg_zone_bottom:.5f}"
            
            # Calculate status
            status_info = self.calculate_status(setup, current_price)
            
            # Format distance
            distance_str = f"{status_info['distance_pips']:.1f} pips"
            
            # Age
            age_str = f"{status_info['age_days']}d"
            
            # Print row
            print(f"{setup.symbol:<12} {dir_icon} {dir_text:<4} {fvg_zone:<25} "
                  f"{current_price:<12.5f} {distance_str:<12} "
                  f"{status_info['icon']} {status_info['text']:<33} {age_str:<8}")
        
        print("-"*120)
        
        # Summary stats
        in_zone_count = 0
        waiting_count = 0
        filled_count = 0
        
        for setup in setups:
            current_price = self.get_current_price(setup.symbol)
            if current_price:
                status_info = self.calculate_status(setup, current_price)
                if "ÎN ZONĂ" in status_info['text']:
                    in_zone_count += 1
                elif "FILLED" in status_info['text']:
                    filled_count += 1
                else:
                    waiting_count += 1
        
        print(f"\n📊 SUMMARY:")
        print(f"   🟢 În Zonă FVG (Ready!): {in_zone_count}")
        print(f"   🔵 Așteaptă Pullback: {waiting_count}")
        print(f"   ✅ Entry Filled: {filled_count}")
        print(f"   📋 Total Active: {len(setups)}")
        print("\n" + "="*120 + "\n")
    
    def run_continuous(self, interval_seconds: int = 60):
        """Run radar continuously with refresh interval"""
        import time
        
        print("\n🎯 MONITORING RADAR - CONTINUOUS MODE")
        print(f"🔄 Refresh every {interval_seconds} seconds")
        print("⏹️  Press Ctrl+C to stop\n")
        
        try:
            while True:
                self.print_radar_table()
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n\n⏹️  Radar stopped by user\n")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='🎯 Glitch in Matrix - Monitoring Radar V6.0'
    )
    parser.add_argument(
        '--continuous',
        action='store_true',
        help='Run continuously with auto-refresh'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Refresh interval in seconds (default: 60)'
    )
    
    args = parser.parse_args()
    
    radar = MonitoringRadar()
    
    if args.continuous:
        radar.run_continuous(args.interval)
    else:
        radar.print_radar_table()


if __name__ == "__main__":
    main()
