#!/usr/bin/env python3
"""
🔥 EXECUTION RADAR - V8.2 LTF Confirmation Scanner
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Radar avansat pentru detectarea automată a semnalelor de EXECUȚIE.

Features V8.2:
✅ Price Analysis - detectează când prețul a intrat în FVG Daily
✅ 4H CHoCH Detection - scanează automat pentru confirmare LTF
✅ Direction Validation - verifică alignment între Daily și 4H
✅ 3-Stage Status System:
   ⏳ WAITING_PULLBACK - Prețul nu a atins FVG
   👀 IN_ZONE_WAITING_CHOCH - În FVG, dar fără CHoCH pe 4H
   🔥 EXECUTION_READY - În FVG + CHoCH pe 4H confirmat!

Usage:
    python3 execution_radar.py
    python3 execution_radar.py --watch --interval 60  # Auto-refresh la 60s
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd

try:
    from ctrader_cbot_client import CTraderCBotClient
    CTRADER_AVAILABLE = True
except ImportError:
    CTRADER_AVAILABLE = False
    print("⚠️  Warning: CTrader client not available.")
    sys.exit(1)

try:
    from smc_detector import SMCDetector, CHoCH
    SMC_AVAILABLE = True
except ImportError:
    SMC_AVAILABLE = False
    print("⚠️  Warning: SMCDetector not available.")
    sys.exit(1)


class ExecutionStatus(Enum):
    """Status-uri pentru faza de execuție"""
    WAITING_PULLBACK = "⏳ WAITING_PULLBACK"           # Prețul nu a atins FVG Daily
    IN_ZONE_WAITING_CHOCH = "👀 IN_ZONE_WAITING_CHOCH"  # În FVG, dar fără CHoCH 4H
    EXECUTION_READY = "🔥 EXECUTION_READY"              # În FVG + CHoCH 4H confirmat!
    INVALIDATED = "🔴 INVALIDATED"                      # SL spart


@dataclass
class ExecutionSetup:
    """Setup cu status de execuție și confirmare LTF"""
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
    status: ExecutionStatus
    distance_pips: float
    choch_4h_detected: bool
    choch_4h_direction: Optional[str]  # 'bullish' sau 'bearish'
    choch_4h_time: Optional[str]
    setup_time: str
    priority: int
    
    def get_status_emoji(self) -> str:
        """Emoji pentru status vizual"""
        if self.status == ExecutionStatus.WAITING_PULLBACK:
            return "⏳"
        elif self.status == ExecutionStatus.IN_ZONE_WAITING_CHOCH:
            return "👀"
        elif self.status == ExecutionStatus.EXECUTION_READY:
            return "🔥"
        else:
            return "🔴"
    
    def get_direction_emoji(self) -> str:
        """Emoji pentru direcție"""
        return "🟢" if self.direction == "LONG" else "🔴"
    
    def get_strategy_emoji(self) -> str:
        """Emoji pentru strategie"""
        return "🔄" if self.strategy_type == "REVERSAL" else "➡️"


class ExecutionRadar:
    """Radar principal pentru detecția semnalelor de execuție"""
    
    def __init__(self):
        if not CTRADER_AVAILABLE or not SMC_AVAILABLE:
            print("❌ Required dependencies not available")
            sys.exit(1)
        
        self.ctrader = CTraderCBotClient()
        self.ctrader_connected = self.ctrader.is_available()
        
        if self.ctrader_connected:
            print("✅ cTrader cBot connected (live prices + 4H data)")
        else:
            print("❌ cTrader cBot not running. Please start MarketDataProvider cBot.")
            sys.exit(1)
        
        # Initialize SMC Detector pentru 4H analysis
        self.smc_detector = SMCDetector(
            swing_lookback=5,
            atr_multiplier=1.2  # V8.2 relaxed filter
        )
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Obține prețul curent din cTrader"""
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
    
    def get_4h_data(self, symbol: str, num_candles: int = 100) -> Optional[pd.DataFrame]:
        """Descarcă date 4H pentru analiză CHoCH"""
        try:
            df = self.ctrader.get_historical_data(symbol, "H4", num_candles)
            
            if df is not None and not df.empty:
                # Reset index to have 'time' as column
                df = df.reset_index()
                return df
            else:
                print(f"⚠️  No 4H data for {symbol}")
                return None
        
        except Exception as e:
            print(f"⚠️  Error downloading 4H data for {symbol}: {e}")
            return None
    
    def detect_4h_choch(
        self, 
        symbol: str, 
        required_direction: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Detectează CHoCH pe 4H în direcția dorită
        
        Args:
            symbol: Simbolul pentru scanare
            required_direction: 'bullish' pentru LONG, 'bearish' pentru SHORT
        
        Returns:
            (choch_detected, choch_direction, choch_time)
        """
        # Download 4H data
        df_4h = self.get_4h_data(symbol, num_candles=100)
        
        if df_4h is None or df_4h.empty:
            return False, None, None
        
        try:
            # Detect CHoCH using SMC Detector
            choch_list = self.smc_detector.detect_choch(df_4h)
            
            if not choch_list:
                return False, None, None
            
            # Get the most recent CHoCH
            latest_choch = choch_list[-1]
            choch_direction = latest_choch.direction
            
            # Get timestamp of CHoCH
            choch_index = latest_choch.index
            if choch_index < len(df_4h):
                choch_time = df_4h.iloc[choch_index]['time']
                if hasattr(choch_time, 'isoformat'):
                    choch_time_str = choch_time.isoformat()
                else:
                    choch_time_str = str(choch_time)
            else:
                choch_time_str = "Unknown"
            
            # Validate direction alignment
            if choch_direction == required_direction:
                return True, choch_direction, choch_time_str
            else:
                return False, choch_direction, choch_time_str
        
        except Exception as e:
            print(f"⚠️  Error detecting CHoCH for {symbol}: {e}")
            return False, None, None
    
    def analyze_execution_status(
        self,
        setup_data: Dict,
        current_price: Optional[float]
    ) -> Tuple[ExecutionStatus, float, bool, Optional[str], Optional[str]]:
        """
        Analizează statusul de execuție complet (preț + CHoCH 4H)
        
        Returns:
            (status, distance_pips, choch_detected, choch_direction, choch_time)
        """
        # Extract data
        symbol = setup_data.get('symbol', 'UNKNOWN')
        direction = setup_data.get('direction', 'SHORT').upper()
        entry = setup_data.get('entry_price', 0)
        stop_loss = setup_data.get('stop_loss', 0)
        
        # V8.2 FAIL-SAFE: Validate fields
        if entry is None or entry == 0 or stop_loss is None or stop_loss == 0:
            return ExecutionStatus.INVALIDATED, 0.0, False, None, None
        
        # FVG zone
        fvg_top = setup_data.get('fvg_top', entry)
        fvg_bottom = setup_data.get('fvg_bottom', entry)
        
        if fvg_top is None:
            fvg_top = entry
        if fvg_bottom is None:
            fvg_bottom = entry
        
        # If no current price, assume waiting
        if current_price is None:
            if direction == "LONG":
                distance = abs(entry - fvg_bottom) * 10000
            else:
                distance = abs(fvg_top - entry) * 10000
            
            return ExecutionStatus.WAITING_PULLBACK, distance, False, None, None
        
        # Analyze based on direction
        if direction == "LONG":
            # LONG Setup: FVG below current market (discount zone)
            
            if current_price < stop_loss:
                # Price breached stop loss
                distance = abs(current_price - stop_loss) * 10000
                return ExecutionStatus.INVALIDATED, distance, False, None, None
            
            elif fvg_bottom <= current_price <= fvg_top:
                # Price IN FVG zone - check for 4H CHoCH
                distance = abs(current_price - entry) * 10000
                
                # Look for BULLISH CHoCH on 4H
                choch_detected, choch_dir, choch_time = self.detect_4h_choch(
                    symbol, 
                    required_direction='bullish'
                )
                
                if choch_detected:
                    return ExecutionStatus.EXECUTION_READY, distance, True, choch_dir, choch_time
                else:
                    return ExecutionStatus.IN_ZONE_WAITING_CHOCH, distance, False, choch_dir, choch_time
            
            else:
                # Price above FVG - waiting for pullback
                distance = abs(current_price - fvg_top) * 10000
                return ExecutionStatus.WAITING_PULLBACK, distance, False, None, None
        
        else:  # SHORT
            # SHORT Setup: FVG above current market (premium zone)
            
            if current_price > stop_loss:
                # Price breached stop loss
                distance = abs(current_price - stop_loss) * 10000
                return ExecutionStatus.INVALIDATED, distance, False, None, None
            
            elif fvg_bottom <= current_price <= fvg_top:
                # Price IN FVG zone - check for 4H CHoCH
                distance = abs(current_price - entry) * 10000
                
                # Look for BEARISH CHoCH on 4H
                choch_detected, choch_dir, choch_time = self.detect_4h_choch(
                    symbol, 
                    required_direction='bearish'
                )
                
                if choch_detected:
                    return ExecutionStatus.EXECUTION_READY, distance, True, choch_dir, choch_time
                else:
                    return ExecutionStatus.IN_ZONE_WAITING_CHOCH, distance, False, choch_dir, choch_time
            
            else:
                # Price below FVG - waiting for retracement up
                distance = abs(fvg_bottom - current_price) * 10000
                return ExecutionStatus.WAITING_PULLBACK, distance, False, None, None
    
    def load_monitoring_setups(self) -> List[Dict]:
        """Încarcă setup-urile din monitoring_setups.json"""
        try:
            with open('monitoring_setups.json', 'r') as f:
                data = json.load(f)
                
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
    
    def create_execution_setup(self, setup_data: Dict) -> Optional[ExecutionSetup]:
        """Creează un ExecutionSetup din datele JSON cu analiză completă"""
        symbol = setup_data.get('symbol', 'UNKNOWN')
        
        # V8.2 FAIL-SAFE: Validate critical fields
        entry_price = setup_data.get('entry_price')
        stop_loss = setup_data.get('stop_loss')
        take_profit = setup_data.get('take_profit')
        
        if entry_price is None or stop_loss is None or take_profit is None:
            print(f"⚠️  SKIPPED: Setup {symbol} is corrupted or missing data")
            return None
        
        try:
            entry_price = float(entry_price)
            stop_loss = float(stop_loss)
            take_profit = float(take_profit)
        except (TypeError, ValueError):
            print(f"⚠️  SKIPPED: Setup {symbol} has invalid numeric data")
            return None
        
        # Get current price
        current_price = self.get_current_price(symbol)
        
        # Analyze execution status (includes 4H CHoCH detection)
        status, distance, choch_detected, choch_dir, choch_time = self.analyze_execution_status(
            setup_data, 
            current_price
        )
        
        # Extract direction
        direction_raw = setup_data.get('direction', 'SHORT')
        if isinstance(direction_raw, str):
            direction = direction_raw.upper()
            # Normalize BUY/SELL to LONG/SHORT
            if direction == 'BUY':
                direction = 'LONG'
            elif direction == 'SELL':
                direction = 'SHORT'
        else:
            direction = "SHORT"
        
        # Extract strategy type
        strategy_type = setup_data.get('strategy_type', 'REVERSAL').upper()
        if strategy_type not in ['REVERSAL', 'CONTINUITY']:
            strategy_type = 'REVERSAL'
        
        # Get FVG zone values
        fvg_top = setup_data.get('fvg_top', entry_price)
        fvg_bottom = setup_data.get('fvg_bottom', entry_price)
        
        if fvg_top is None:
            fvg_top = entry_price
        if fvg_bottom is None:
            fvg_bottom = entry_price
        
        # Create ExecutionSetup
        return ExecutionSetup(
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
            choch_4h_detected=choch_detected,
            choch_4h_direction=choch_dir,
            choch_4h_time=choch_time,
            setup_time=setup_data.get('setup_time', 'Unknown'),
            priority=setup_data.get('priority', 1)
        )
    
    def print_execution_radar(self, execution_setups: List[ExecutionSetup]):
        """Printează tabelul radar de execuție cu culori"""
        if not execution_setups:
            print("\n📭 No active setups in monitoring\n")
            return
        
        # Header
        print("\n" + "="*120)
        print("🔥 EXECUTION RADAR - V8.2 LTF CONFIRMATION SCANNER")
        print("="*120)
        print(f"⏰ Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Active Setups: {len(execution_setups)}")
        print("="*120)
        
        # Count by status
        waiting_count = sum(1 for s in execution_setups if s.status == ExecutionStatus.WAITING_PULLBACK)
        in_zone_count = sum(1 for s in execution_setups if s.status == ExecutionStatus.IN_ZONE_WAITING_CHOCH)
        ready_count = sum(1 for s in execution_setups if s.status == ExecutionStatus.EXECUTION_READY)
        invalid_count = sum(1 for s in execution_setups if s.status == ExecutionStatus.INVALIDATED)
        
        print(f"\n⏳ WAITING: {waiting_count} | 👀 IN ZONE (No CHoCH): {in_zone_count} | 🔥 READY TO EXECUTE: {ready_count} | 🔴 INVALIDATED: {invalid_count}\n")
        
        # Sort: EXECUTION_READY first, then IN_ZONE, then WAITING, then INVALIDATED
        status_priority = {
            ExecutionStatus.EXECUTION_READY: 1,
            ExecutionStatus.IN_ZONE_WAITING_CHOCH: 2,
            ExecutionStatus.WAITING_PULLBACK: 3,
            ExecutionStatus.INVALIDATED: 4
        }
        sorted_setups = sorted(execution_setups, key=lambda s: status_priority[s.status])
        
        # Print each setup
        for i, setup in enumerate(sorted_setups, 1):
            self._print_execution_row(i, setup)
        
        print("="*120)
        
        # Summary recommendations
        if ready_count > 0:
            print(f"\n🚨 URGENT: {ready_count} setup(s) READY TO EXECUTE NOW!")
            print("   ➡️  Price in FVG Daily + CHoCH 4H confirmed!")
            print("   ➡️  Execute immediately with risk management!")
        
        if in_zone_count > 0:
            print(f"\n⚠️  WATCH CLOSELY: {in_zone_count} setup(s) in FVG zone, waiting for 4H CHoCH")
        
        if invalid_count > 0:
            print(f"\n⚠️  CLEANUP REQUIRED: {invalid_count} setup(s) INVALIDATED - Remove from monitoring")
        
        print()
    
    def _print_execution_row(self, index: int, setup: ExecutionSetup):
        """Printează un rând pentru un setup de execuție"""
        # Status indicator
        status_emoji = setup.get_status_emoji()
        status_text = setup.status.value
        
        # Direction and strategy
        dir_emoji = setup.get_direction_emoji()
        strategy_emoji = setup.get_strategy_emoji()
        
        # Price info
        price_str = f"{setup.current_price:.5f}" if setup.current_price > 0 else "N/A"
        
        # Distance display based on status
        if setup.status == ExecutionStatus.WAITING_PULLBACK:
            distance_text = f"🔸 {setup.distance_pips:.1f} pips to FVG"
        elif setup.status == ExecutionStatus.IN_ZONE_WAITING_CHOCH:
            distance_text = f"⚠️  IN FVG (±{setup.distance_pips:.1f} pips) - NO 4H CHoCH YET"
        elif setup.status == ExecutionStatus.EXECUTION_READY:
            distance_text = f"✅ IN FVG + 4H CHoCH CONFIRMED! (±{setup.distance_pips:.1f} pips)"
        else:
            distance_text = f"❌ SL breached by {setup.distance_pips:.1f} pips"
        
        # FVG zone
        fvg_zone = f"[{setup.fvg_bottom:.5f} - {setup.fvg_top:.5f}]"
        
        # CHoCH info
        if setup.choch_4h_detected:
            choch_info = f"✅ 4H CHoCH: {setup.choch_4h_direction.upper()} @ {setup.choch_4h_time}"
        elif setup.status == ExecutionStatus.IN_ZONE_WAITING_CHOCH:
            if setup.choch_4h_direction:
                choch_info = f"❌ 4H CHoCH: {setup.choch_4h_direction.upper()} (WRONG DIRECTION)"
            else:
                choch_info = "⏳ No 4H CHoCH detected yet"
        else:
            choch_info = "N/A"
        
        # Print row
        print(f"\n{index}. {status_emoji} {setup.symbol} {dir_emoji} {setup.direction} {strategy_emoji} {setup.strategy_type}")
        print(f"   {status_text}")
        print(f"   💰 Current Price: {price_str}")
        print(f"   🎯 Entry: {setup.entry_price:.5f} | SL: {setup.stop_loss:.5f} | TP: {setup.take_profit:.5f}")
        print(f"   📦 FVG Zone: {fvg_zone}")
        print(f"   📏 {distance_text}")
        print(f"   🔍 {choch_info}")
        print(f"   ⚡ R:R 1:{setup.risk_reward:.1f} | ⏰ Setup: {setup.setup_time}")
    
    def run_execution_scan(self):
        """Rulează un scan complet de execuție"""
        # Load setups
        setups_data = self.load_monitoring_setups()
        
        if not setups_data:
            print("\n📭 No active setups found in monitoring_setups.json\n")
            return
        
        # Convert to ExecutionSetup objects
        execution_setups = []
        skipped_count = 0
        
        for setup_data in setups_data:
            try:
                exec_setup = self.create_execution_setup(setup_data)
                
                if exec_setup is None:
                    skipped_count += 1
                    continue
                
                execution_setups.append(exec_setup)
            
            except Exception as e:
                print(f"⚠️  Error processing setup {setup_data.get('symbol', 'UNKNOWN')}: {e}")
                skipped_count += 1
        
        # Report skipped
        if skipped_count > 0:
            print(f"\n⚠️  Skipped {skipped_count} corrupted/incomplete setup(s)\n")
        
        # Print execution radar
        self.print_execution_radar(execution_setups)
    
    def run_watch_mode(self, interval_seconds: int = 60):
        """Rulează radar în modul watch (auto-refresh)"""
        import time
        
        print("\n🔄 WATCH MODE ENABLED")
        print(f"⏰ Auto-refresh every {interval_seconds} seconds")
        print("⚠️  Note: 4H CHoCH detection may take a few seconds per symbol")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                # Clear screen
                print("\033[2J\033[H", end="")
                
                # Run scan
                self.run_execution_scan()
                
                # Wait
                time.sleep(interval_seconds)
        
        except KeyboardInterrupt:
            print("\n\n👋 Watch mode stopped\n")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='🔥 Execution Radar V8.2 - LTF Confirmation Scanner (4H CHoCH Detection)'
    )
    parser.add_argument(
        '--watch',
        action='store_true',
        help='Enable watch mode (auto-refresh every 60s)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Refresh interval in seconds for watch mode (default: 60)'
    )
    
    args = parser.parse_args()
    
    # Create radar
    radar = ExecutionRadar()
    
    # Run
    if args.watch:
        radar.run_watch_mode(interval_seconds=args.interval)
    else:
        radar.run_execution_scan()


if __name__ == '__main__':
    main()
