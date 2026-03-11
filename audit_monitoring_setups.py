#!/usr/bin/env python3
"""
🎯 LIVE MONITORING RADAR - V8.2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Radar principal pentru monitorizarea setup-urilor active în timp real.

Features V8.2:
✅ Strategy Type Display (REVERSAL/CONTINUITY)
✅ Live Price Analysis (3 scenarii: WAITING/IN_ZONE/INVALIDATED)
✅ Distance to FVG în pips
✅ Tabel colorat cu status vizual

Usage:
    python3 audit_monitoring_setups.py
    python3 audit_monitoring_setups.py --watch  # Auto-refresh la 30s
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

try:
    from ctrader_cbot_client import CTraderCBotClient
    CTRADER_AVAILABLE = True
except ImportError:
    CTRADER_AVAILABLE = False
    print("⚠️  Warning: CTrader client not available. Using mock prices.")


class SetupStatus(Enum):
    """Status-uri posibile pentru un setup în monitoring"""
    WAITING_PULLBACK = "⏳ WAITING_PULLBACK"  # Prețul nu a atins FVG încă
    IN_ZONE = "🎯 IN_ZONE"                     # Prețul în FVG - gata de execuție!
    INVALIDATED = "🔴 INVALIDATED"             # Prețul a spart SL - setup invalid


@dataclass
class LiveSetup:
    """Setup activ cu date live de preț"""
    symbol: str
    direction: str  # 'LONG' sau 'SHORT'
    strategy_type: str  # 'REVERSAL' sau 'CONTINUITY'
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    fvg_top: float
    fvg_bottom: float
    current_price: float
    status: SetupStatus
    distance_pips: float  # Distanța până la FVG (sau distanța în FVG)
    setup_time: str
    priority: int
    
    def get_status_emoji(self) -> str:
        """Emoji pentru status vizual"""
        if self.status == SetupStatus.WAITING_PULLBACK:
            return "⏳"
        elif self.status == SetupStatus.IN_ZONE:
            return "🎯"
        else:
            return "🔴"
    
    def get_direction_emoji(self) -> str:
        """Emoji pentru direcție"""
        return "🟢" if self.direction == "LONG" else "🔴"
    
    def get_strategy_emoji(self) -> str:
        """Emoji pentru strategie"""
        return "🔄" if self.strategy_type == "REVERSAL" else "➡️"


class MonitoringRadar:
    """Radar principal pentru monitorizare live"""
    
    def __init__(self):
        if CTRADER_AVAILABLE:
            self.ctrader = CTraderCBotClient()
            self.ctrader_connected = self.ctrader.is_available()
            if self.ctrader_connected:
                print("✅ cTrader cBot connected (live prices)")
            else:
                print("⚠️  cTrader cBot not running (using last known prices)")
        else:
            self.ctrader = None
            self.ctrader_connected = False
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Obține prețul curent din cTrader"""
        if not self.ctrader_connected:
            return None
        
        try:
            # Fetch current price from cTrader cBot
            import requests
            response = requests.get(
                f"http://localhost:8767/price",
                params={"symbol": symbol},
                timeout=2
            )
            
            if response.status_code == 200:
                data = response.json()
                # Get bid price (for sell) or ask price (for buy)
                # Use mid-price as approximation
                bid = data.get('bid', 0)
                ask = data.get('ask', 0)
                if bid > 0 and ask > 0:
                    return (bid + ask) / 2.0
            
            return None
        
        except Exception as e:
            print(f"⚠️  Error fetching price for {symbol}: {e}")
            return None
    
    def analyze_setup_status(
        self, 
        setup_data: Dict,
        current_price: Optional[float]
    ) -> tuple[SetupStatus, float]:
        """
        Analizează statusul unui setup bazat pe prețul curent
        
        Returns:
            (status, distance_pips)
        """
        # Extract data
        direction = setup_data.get('direction', 'SHORT').upper()
        entry = setup_data.get('entry_price', 0)
        stop_loss = setup_data.get('stop_loss', 0)
        
        # V8.2 FAIL-SAFE: Validate entry and stop_loss before calculations
        if entry is None or entry == 0:
            entry = 0
        if stop_loss is None or stop_loss == 0:
            stop_loss = 0
        
        # FVG zone (entry = middle of FVG în implementarea noastră)
        fvg_top = setup_data.get('fvg_top', entry)
        fvg_bottom = setup_data.get('fvg_bottom', entry)
        
        # V8.2 FAIL-SAFE: Handle None in FVG fields
        if fvg_top is None:
            fvg_top = entry
        if fvg_bottom is None:
            fvg_bottom = entry
        
        # If no current price, assume waiting
        if current_price is None:
            # Calculate distance to FVG based on last known entry
            if direction == "LONG":
                distance = abs(entry - fvg_bottom) * 10000  # Convert to pips
            else:
                distance = abs(fvg_top - entry) * 10000
            
            return SetupStatus.WAITING_PULLBACK, distance
        
        # Analyze based on direction
        if direction == "LONG":
            # LONG Setup:
            # - FVG below current market (discount zone)
            # - WAITING: Price above FVG top
            # - IN_ZONE: Price between FVG bottom and top
            # - INVALIDATED: Price below stop loss
            
            if current_price < stop_loss:
                # Price breached stop loss
                distance = abs(current_price - stop_loss) * 10000
                return SetupStatus.INVALIDATED, distance
            
            elif fvg_bottom <= current_price <= fvg_top:
                # Price in FVG zone - READY!
                distance = abs(current_price - entry) * 10000
                return SetupStatus.IN_ZONE, distance
            
            else:
                # Price above FVG - waiting for pullback
                distance = abs(current_price - fvg_top) * 10000
                return SetupStatus.WAITING_PULLBACK, distance
        
        else:  # SHORT
            # SHORT Setup:
            # - FVG above current market (premium zone)
            # - WAITING: Price below FVG bottom
            # - IN_ZONE: Price between FVG bottom and top
            # - INVALIDATED: Price above stop loss
            
            if current_price > stop_loss:
                # Price breached stop loss
                distance = abs(current_price - stop_loss) * 10000
                return SetupStatus.INVALIDATED, distance
            
            elif fvg_bottom <= current_price <= fvg_top:
                # Price in FVG zone - READY!
                distance = abs(current_price - entry) * 10000
                return SetupStatus.IN_ZONE, distance
            
            else:
                # Price below FVG - waiting for retracement up
                distance = abs(fvg_bottom - current_price) * 10000
                return SetupStatus.WAITING_PULLBACK, distance
    
    def load_monitoring_setups(self) -> List[Dict]:
        """Încarcă setup-urile din monitoring_setups.json"""
        try:
            with open('monitoring_setups.json', 'r') as f:
                data = json.load(f)
                
                # Handle both formats (dict with 'setups' key or direct list)
                if isinstance(data, dict):
                    setups = data.get("setups", [])
                elif isinstance(data, list):
                    setups = data
                else:
                    print("⚠️  Invalid monitoring_setups.json format")
                    return []
                
                # Filter only MONITORING status
                active_setups = [
                    s for s in setups 
                    if isinstance(s, dict) and s.get('status') == 'MONITORING'
                ]
                
                return active_setups
        
        except FileNotFoundError:
            print("⚠️  monitoring_setups.json not found")
            return []
        
        except json.JSONDecodeError as e:
            print(f"⚠️  Error parsing monitoring_setups.json: {e}")
            return []
    
    def create_live_setup(self, setup_data: Dict) -> Optional[LiveSetup]:
        """Creează un LiveSetup din datele JSON
        
        Returns:
            LiveSetup object or None if data is corrupted/incomplete
        """
        symbol = setup_data.get('symbol', 'UNKNOWN')
        
        # V8.2 FAIL-SAFE: Validate critical fields first
        entry_price = setup_data.get('entry_price')
        stop_loss = setup_data.get('stop_loss')
        take_profit = setup_data.get('take_profit')
        
        # Check for None/corrupted values in critical fields
        if entry_price is None or stop_loss is None or take_profit is None:
            print(f"⚠️  SKIPPED: Setup {symbol} is corrupted or missing data (Legacy setup)")
            print(f"   └─ entry={entry_price}, SL={stop_loss}, TP={take_profit}")
            return None
        
        # Validate numeric types
        try:
            entry_price = float(entry_price)
            stop_loss = float(stop_loss)
            take_profit = float(take_profit)
        except (TypeError, ValueError):
            print(f"⚠️  SKIPPED: Setup {symbol} has invalid numeric data")
            return None
        
        # Get current price
        current_price = self.get_current_price(symbol)
        
        # Analyze status
        status, distance = self.analyze_setup_status(setup_data, current_price)
        
        # Extract direction
        direction_raw = setup_data.get('direction', 'SHORT')
        if isinstance(direction_raw, str):
            direction = direction_raw.upper()
        else:
            # Fallback: derive from daily_choch if present
            daily_choch = setup_data.get('daily_choch', {})
            if isinstance(daily_choch, dict):
                choch_dir = daily_choch.get('direction', 'bearish')
                direction = "LONG" if choch_dir == 'bullish' else "SHORT"
            else:
                direction = "SHORT"
        
        # V8.2: Extract strategy type
        strategy_type = setup_data.get('strategy_type', 'REVERSAL').upper()
        if strategy_type not in ['REVERSAL', 'CONTINUITY']:
            strategy_type = 'REVERSAL'  # Default fallback
        
        # Get FVG zone values (with fallback to entry_price)
        fvg_top = setup_data.get('fvg_top', entry_price)
        fvg_bottom = setup_data.get('fvg_bottom', entry_price)
        
        # Validate FVG fields
        if fvg_top is None:
            fvg_top = entry_price
        if fvg_bottom is None:
            fvg_bottom = entry_price
        
        # Create LiveSetup
        return LiveSetup(
            symbol=symbol,
            direction=direction,
            strategy_type=strategy_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=setup_data.get('risk_reward', 0) or 0,
            fvg_top=fvg_top,
            fvg_bottom=fvg_bottom,
            current_price=current_price if current_price else entry_price,
            status=status,
            distance_pips=distance,
            setup_time=setup_data.get('setup_time', 'Unknown'),
            priority=setup_data.get('priority', 1)
        )
    
    def print_radar_table(self, live_setups: List[LiveSetup]):
        """Printează tabelul radar colorat"""
        if not live_setups:
            print("\n📭 No active setups in monitoring\n")
            return
        
        # Header
        print("\n" + "="*120)
        print("🎯 LIVE MONITORING RADAR - V8.2")
        print("="*120)
        print(f"⏰ Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Active Setups: {len(live_setups)}")
        print("="*120)
        
        # Count by status
        waiting_count = sum(1 for s in live_setups if s.status == SetupStatus.WAITING_PULLBACK)
        in_zone_count = sum(1 for s in live_setups if s.status == SetupStatus.IN_ZONE)
        invalid_count = sum(1 for s in live_setups if s.status == SetupStatus.INVALIDATED)
        
        print(f"\n⏳ WAITING: {waiting_count} | 🎯 IN ZONE: {in_zone_count} | 🔴 INVALIDATED: {invalid_count}\n")
        
        # Sort: IN_ZONE first, then WAITING, then INVALIDATED
        status_priority = {
            SetupStatus.IN_ZONE: 1,
            SetupStatus.WAITING_PULLBACK: 2,
            SetupStatus.INVALIDATED: 3
        }
        sorted_setups = sorted(live_setups, key=lambda s: status_priority[s.status])
        
        # Print each setup
        for i, setup in enumerate(sorted_setups, 1):
            self._print_setup_row(i, setup)
        
        print("="*120)
        
        # Summary recommendations
        if in_zone_count > 0:
            print(f"\n🔥 ACTION REQUIRED: {in_zone_count} setup(s) IN ZONE - Check 4H/1H for entry trigger!")
        
        if invalid_count > 0:
            print(f"\n⚠️  CLEANUP REQUIRED: {invalid_count} setup(s) INVALIDATED - Consider removing from monitoring")
        
        print()
    
    def _print_setup_row(self, index: int, setup: LiveSetup):
        """Printează un rând pentru un setup"""
        # Status indicator
        status_emoji = setup.get_status_emoji()
        status_text = setup.status.value
        
        # Direction and strategy
        dir_emoji = setup.get_direction_emoji()
        strategy_emoji = setup.get_strategy_emoji()
        
        # Price info
        price_str = f"{setup.current_price:.5f}" if setup.current_price > 0 else "N/A"
        
        # Distance display
        if setup.status == SetupStatus.WAITING_PULLBACK:
            distance_text = f"🔸 {setup.distance_pips:.1f} pips to FVG"
        elif setup.status == SetupStatus.IN_ZONE:
            distance_text = f"✅ IN FVG (±{setup.distance_pips:.1f} pips from entry)"
        else:
            distance_text = f"❌ SL breached by {setup.distance_pips:.1f} pips"
        
        # FVG zone
        fvg_zone = f"[{setup.fvg_bottom:.5f} - {setup.fvg_top:.5f}]"
        
        # Print row
        print(f"\n{index}. {status_emoji} {setup.symbol} {dir_emoji} {setup.direction} {strategy_emoji} {setup.strategy_type}")
        print(f"   {status_text}")
        print(f"   💰 Current Price: {price_str}")
        print(f"   🎯 Entry: {setup.entry_price:.5f} | SL: {setup.stop_loss:.5f} | TP: {setup.take_profit:.5f}")
        print(f"   📦 FVG Zone: {fvg_zone}")
        print(f"   📏 {distance_text}")
        print(f"   ⚡ R:R 1:{setup.risk_reward:.1f} | �� Setup: {setup.setup_time}")
    
    def run_radar_scan(self):
        """Rulează un scan complet al tuturor setup-urilor"""
        # Load setups
        setups_data = self.load_monitoring_setups()
        
        if not setups_data:
            print("\n📭 No active setups found in monitoring_setups.json\n")
            return
        
        # Convert to LiveSetup objects
        live_setups = []
        skipped_count = 0
        for setup_data in setups_data:
            try:
                live_setup = self.create_live_setup(setup_data)
                
                # V8.2 FAIL-SAFE: Skip if create_live_setup returned None (corrupted data)
                if live_setup is None:
                    skipped_count += 1
                    continue
                
                live_setups.append(live_setup)
            except Exception as e:
                print(f"⚠️  Error processing setup {setup_data.get('symbol', 'UNKNOWN')}: {e}")
                skipped_count += 1
        
        # Report skipped setups
        if skipped_count > 0:
            print(f"\n⚠️  Skipped {skipped_count} corrupted/incomplete setup(s)")
            print("   Recommendation: Clean up monitoring_setups.json or re-run daily scanner\n")
        
        # Print radar table
        self.print_radar_table(live_setups)
    
    def run_watch_mode(self, interval_seconds: int = 30):
        """Rulează radar în modul watch (auto-refresh)"""
        import time
        
        print("\n🔄 WATCH MODE ENABLED")
        print(f"⏰ Auto-refresh every {interval_seconds} seconds")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                # Clear screen (works on Unix/Linux/Mac)
                print("\033[2J\033[H", end="")
                
                # Run scan
                self.run_radar_scan()
                
                # Wait
                time.sleep(interval_seconds)
        
        except KeyboardInterrupt:
            print("\n\n👋 Watch mode stopped\n")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='🎯 Live Monitoring Radar V8.2 - Track your active setups in real-time'
    )
    parser.add_argument(
        '--watch',
        action='store_true',
        help='Enable watch mode (auto-refresh every 30s)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Refresh interval in seconds for watch mode (default: 30)'
    )
    
    args = parser.parse_args()
    
    # Create radar
    radar = MonitoringRadar()
    
    # Run
    if args.watch:
        radar.run_watch_mode(interval_seconds=args.interval)
    else:
        radar.run_radar_scan()


if __name__ == '__main__':
    main()
