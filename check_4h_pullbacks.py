#!/usr/bin/env python3
"""
🎯 4H PULLBACK CHECKER - V8.2 Final Entry Scanner
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Verifică dacă setup-urile cu CHoCH pe 4H au făcut pullback către FVG-ul de 4H.

Logic Flow (SMC Compliant):
1. Setup Daily detectat (în monitoring_setups.json)
2. Prețul a intrat în FVG Daily ✅
3. CHoCH pe 4H confirmat în direcția corectă ✅
4. **[AICI SUNTEM] - Așteaptă pullback către FVG-ul de 4H** ⏳
5. Când prețul intră în FVG 4H → 🔥 EXECUTE NOW!

Features:
✅ Detectează CHoCH pe 4H
✅ Extrage FVG-ul creat de CHoCH pe 4H
✅ Calculează distanța prețului până la FVG 4H
✅ 2 Status-uri noi:
   ⏳ WAITING_4H_PULLBACK - CHoCH confirmat, așteaptă revenire în FVG 4H
   🔥 EXECUTE_NOW - Prețul în FVG 4H, gata de intrare!

Usage:
    python3 check_4h_pullbacks.py
    python3 check_4h_pullbacks.py --watch --interval 30
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
    from smc_detector import SMCDetector, CHoCH, FVG
    SMC_AVAILABLE = True
except ImportError:
    SMC_AVAILABLE = False
    print("⚠️  Warning: SMCDetector not available.")
    sys.exit(1)


class PullbackStatus(Enum):
    """Status-uri pentru faza de pullback 4H"""
    WAITING_DAILY_FVG = "⏳ WAITING_DAILY_FVG"           # Prețul nu a atins FVG Daily
    WAITING_4H_CHOCH = "👀 WAITING_4H_CHOCH"             # În FVG Daily, fără CHoCH 4H
    WAITING_4H_PULLBACK = "⏳ WAITING_4H_PULLBACK"       # CHoCH 4H confirmat, așteaptă pullback
    EXECUTE_NOW = "🔥 EXECUTE_NOW"                       # Prețul în FVG 4H - GATA!
    INVALIDATED = "🔴 INVALIDATED"                       # SL spart


@dataclass
class PullbackSetup:
    """Setup cu analiză completă de pullback 4H"""
    symbol: str
    direction: str  # 'LONG' sau 'SHORT'
    strategy_type: str
    
    # Daily levels
    entry_price_daily: float
    stop_loss: float
    take_profit: float
    fvg_daily_top: float
    fvg_daily_bottom: float
    
    # 4H CHoCH info
    choch_4h_detected: bool
    choch_4h_direction: Optional[str]
    choch_4h_time: Optional[str]
    choch_4h_price: Optional[float]
    
    # 4H FVG info (created by CHoCH)
    fvg_4h_detected: bool
    fvg_4h_top: Optional[float]
    fvg_4h_bottom: Optional[float]
    fvg_4h_entry: Optional[float]  # Middle of FVG 4H
    
    # Live price analysis
    current_price: float
    status: PullbackStatus
    distance_to_4h_fvg_pips: float
    
    # Other
    risk_reward: float
    setup_time: str
    priority: int
    
    def get_status_emoji(self) -> str:
        """Emoji pentru status"""
        if self.status == PullbackStatus.WAITING_DAILY_FVG:
            return "⏳"
        elif self.status == PullbackStatus.WAITING_4H_CHOCH:
            return "👀"
        elif self.status == PullbackStatus.WAITING_4H_PULLBACK:
            return "⏳"
        elif self.status == PullbackStatus.EXECUTE_NOW:
            return "🔥"
        else:
            return "🔴"
    
    def get_direction_emoji(self) -> str:
        return "🟢" if self.direction == "LONG" else "🔴"


class PullbackChecker:
    """Checker pentru analiza pullback-urilor 4H"""
    
    def __init__(self):
        if not CTRADER_AVAILABLE or not SMC_AVAILABLE:
            print("❌ Required dependencies not available")
            sys.exit(1)
        
        self.ctrader = CTraderCBotClient()
        self.ctrader_connected = self.ctrader.is_available()
        
        if self.ctrader_connected:
            print("✅ cTrader cBot connected (4H data + live prices)")
        else:
            print("❌ cTrader cBot not running")
            sys.exit(1)
        
        self.smc_detector = SMCDetector(swing_lookback=5, atr_multiplier=1.2)
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price from cTrader"""
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
        """Download 4H data"""
        try:
            df = self.ctrader.get_historical_data(symbol, "H4", num_candles)
            
            if df is not None and not df.empty:
                df = df.reset_index()
                return df
            else:
                return None
        
        except Exception as e:
            print(f"⚠️  Error downloading 4H data for {symbol}: {e}")
            return None
    
    def detect_4h_choch_and_fvg(
        self,
        symbol: str,
        required_direction: str
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[float], bool, Optional[float], Optional[float]]:
        """
        Detectează CHoCH pe 4H ȘI extrage FVG-ul creat de acel CHoCH
        
        Returns:
            (choch_detected, choch_direction, choch_time, choch_price,
             fvg_detected, fvg_top, fvg_bottom)
        """
        df_4h = self.get_4h_data(symbol, num_candles=100)
        
        if df_4h is None or df_4h.empty:
            return False, None, None, None, False, None, None
        
        try:
            # Detect CHoCH
            choch_list = self.smc_detector.detect_choch(df_4h)
            
            if not choch_list:
                return False, None, None, None, False, None, None
            
            # Get latest CHoCH
            latest_choch = choch_list[-1]
            choch_direction = latest_choch.direction
            choch_index = latest_choch.index
            
            # Get CHoCH timestamp and price
            if choch_index < len(df_4h):
                choch_time = df_4h.iloc[choch_index]['time']
                choch_time_str = choch_time.isoformat() if hasattr(choch_time, 'isoformat') else str(choch_time)
                choch_price = df_4h.iloc[choch_index]['close']
            else:
                choch_time_str = "Unknown"
                choch_price = None
            
            # Validate direction
            if choch_direction != required_direction:
                return False, choch_direction, choch_time_str, choch_price, False, None, None
            
            # Now detect FVG created by this CHoCH
            # FVG is typically found AFTER the CHoCH move
            fvg_list = self.smc_detector.detect_fvg(df_4h)
            
            if not fvg_list:
                # CHoCH detected but no FVG found
                return True, choch_direction, choch_time_str, choch_price, False, None, None
            
            # Find the FVG closest to the CHoCH
            # Typically the last FVG in the list (most recent)
            latest_fvg = fvg_list[-1]
            fvg_top = latest_fvg.top
            fvg_bottom = latest_fvg.bottom
            
            return True, choch_direction, choch_time_str, choch_price, True, fvg_top, fvg_bottom
        
        except Exception as e:
            print(f"⚠️  Error analyzing 4H for {symbol}: {e}")
            return False, None, None, None, False, None, None
    
    def analyze_pullback_status(
        self,
        setup_data: Dict,
        current_price: Optional[float]
    ) -> Tuple[PullbackStatus, float, bool, Optional[str], Optional[str], Optional[float], 
               bool, Optional[float], Optional[float], Optional[float]]:
        """
        Analiză completă de pullback 4H
        
        Returns:
            (status, distance_to_4h_fvg_pips, 
             choch_detected, choch_dir, choch_time, choch_price,
             fvg_4h_detected, fvg_4h_top, fvg_4h_bottom, fvg_4h_entry)
        """
        symbol = setup_data.get('symbol', 'UNKNOWN')
        direction = setup_data.get('direction', 'SHORT').upper()
        
        # Normalize direction
        if direction == 'BUY':
            direction = 'LONG'
        elif direction == 'SELL':
            direction = 'SHORT'
        
        entry = setup_data.get('entry_price', 0)
        stop_loss = setup_data.get('stop_loss', 0)
        
        # Validate
        if entry is None or entry == 0 or stop_loss is None or stop_loss == 0:
            return (PullbackStatus.INVALIDATED, 0.0, False, None, None, None, 
                    False, None, None, None)
        
        # Daily FVG zone
        fvg_daily_top = setup_data.get('fvg_top', entry)
        fvg_daily_bottom = setup_data.get('fvg_bottom', entry)
        
        if fvg_daily_top is None:
            fvg_daily_top = entry
        if fvg_daily_bottom is None:
            fvg_daily_bottom = entry
        
        # No current price
        if current_price is None:
            return (PullbackStatus.WAITING_DAILY_FVG, 0.0, False, None, None, None,
                    False, None, None, None)
        
        # Check if SL breached
        if direction == "LONG" and current_price < stop_loss:
            distance = abs(current_price - stop_loss) * 10000
            return (PullbackStatus.INVALIDATED, distance, False, None, None, None,
                    False, None, None, None)
        elif direction == "SHORT" and current_price > stop_loss:
            distance = abs(current_price - stop_loss) * 10000
            return (PullbackStatus.INVALIDATED, distance, False, None, None, None,
                    False, None, None, None)
        
        # Check if price in Daily FVG
        in_daily_fvg = fvg_daily_bottom <= current_price <= fvg_daily_top
        
        if not in_daily_fvg:
            # Price not in Daily FVG yet
            if direction == "LONG":
                distance = abs(current_price - fvg_daily_top) * 10000
            else:
                distance = abs(fvg_daily_bottom - current_price) * 10000
            
            return (PullbackStatus.WAITING_DAILY_FVG, distance, False, None, None, None,
                    False, None, None, None)
        
        # Price IS in Daily FVG - check for 4H CHoCH and FVG
        required_4h_direction = 'bullish' if direction == 'LONG' else 'bearish'
        
        (choch_detected, choch_dir, choch_time, choch_price,
         fvg_4h_detected, fvg_4h_top, fvg_4h_bottom) = self.detect_4h_choch_and_fvg(
            symbol, 
            required_4h_direction
        )
        
        if not choch_detected:
            # No CHoCH on 4H yet
            distance = abs(current_price - entry) * 10000
            return (PullbackStatus.WAITING_4H_CHOCH, distance, False, choch_dir, choch_time, choch_price,
                    False, None, None, None)
        
        # CHoCH detected - calculate FVG 4H entry
        if fvg_4h_detected and fvg_4h_top is not None and fvg_4h_bottom is not None:
            fvg_4h_entry = (fvg_4h_top + fvg_4h_bottom) / 2.0
            
            # Check if price has pulled back into FVG 4H
            in_fvg_4h = fvg_4h_bottom <= current_price <= fvg_4h_top
            
            if in_fvg_4h:
                # EXECUTE NOW!
                distance = abs(current_price - fvg_4h_entry) * 10000
                return (PullbackStatus.EXECUTE_NOW, distance, True, choch_dir, choch_time, choch_price,
                        True, fvg_4h_top, fvg_4h_bottom, fvg_4h_entry)
            else:
                # Waiting for pullback to FVG 4H
                if direction == "LONG":
                    distance = abs(current_price - fvg_4h_top) * 10000
                else:
                    distance = abs(fvg_4h_bottom - current_price) * 10000
                
                return (PullbackStatus.WAITING_4H_PULLBACK, distance, True, choch_dir, choch_time, choch_price,
                        True, fvg_4h_top, fvg_4h_bottom, fvg_4h_entry)
        else:
            # CHoCH detected but no FVG 4H found
            # Use CHoCH price as entry proxy
            distance = abs(current_price - (choch_price if choch_price else entry)) * 10000
            return (PullbackStatus.WAITING_4H_PULLBACK, distance, True, choch_dir, choch_time, choch_price,
                    False, None, None, None)
    
    def load_monitoring_setups(self) -> List[Dict]:
        """Load setups from monitoring_setups.json"""
        try:
            with open('monitoring_setups.json', 'r') as f:
                data = json.load(f)
                
                if isinstance(data, dict):
                    setups = data.get("setups", [])
                elif isinstance(data, list):
                    setups = data
                else:
                    return []
                
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
    
    def create_pullback_setup(self, setup_data: Dict) -> Optional[PullbackSetup]:
        """Create PullbackSetup with full 4H analysis"""
        symbol = setup_data.get('symbol', 'UNKNOWN')
        
        # Validate critical fields
        entry_price = setup_data.get('entry_price')
        stop_loss = setup_data.get('stop_loss')
        take_profit = setup_data.get('take_profit')
        
        if entry_price is None or stop_loss is None or take_profit is None:
            print(f"⚠️  SKIPPED: Setup {symbol} is corrupted")
            return None
        
        try:
            entry_price = float(entry_price)
            stop_loss = float(stop_loss)
            take_profit = float(take_profit)
        except (TypeError, ValueError):
            print(f"⚠️  SKIPPED: Setup {symbol} has invalid data")
            return None
        
        # Get current price
        current_price = self.get_current_price(symbol)
        
        # Analyze pullback status
        (status, distance, choch_detected, choch_dir, choch_time, choch_price,
         fvg_4h_detected, fvg_4h_top, fvg_4h_bottom, fvg_4h_entry) = self.analyze_pullback_status(
            setup_data, 
            current_price
        )
        
        # Extract direction
        direction_raw = setup_data.get('direction', 'SHORT')
        if isinstance(direction_raw, str):
            direction = direction_raw.upper()
            if direction == 'BUY':
                direction = 'LONG'
            elif direction == 'SELL':
                direction = 'SHORT'
        else:
            direction = "SHORT"
        
        # Strategy type
        strategy_type = setup_data.get('strategy_type', 'REVERSAL').upper()
        if strategy_type not in ['REVERSAL', 'CONTINUITY']:
            strategy_type = 'REVERSAL'
        
        # Daily FVG
        fvg_daily_top = setup_data.get('fvg_top', entry_price)
        fvg_daily_bottom = setup_data.get('fvg_bottom', entry_price)
        
        if fvg_daily_top is None:
            fvg_daily_top = entry_price
        if fvg_daily_bottom is None:
            fvg_daily_bottom = entry_price
        
        return PullbackSetup(
            symbol=symbol,
            direction=direction,
            strategy_type=strategy_type,
            entry_price_daily=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            fvg_daily_top=fvg_daily_top,
            fvg_daily_bottom=fvg_daily_bottom,
            choch_4h_detected=choch_detected,
            choch_4h_direction=choch_dir,
            choch_4h_time=choch_time,
            choch_4h_price=choch_price,
            fvg_4h_detected=fvg_4h_detected,
            fvg_4h_top=fvg_4h_top,
            fvg_4h_bottom=fvg_4h_bottom,
            fvg_4h_entry=fvg_4h_entry,
            current_price=current_price if current_price else entry_price,
            status=status,
            distance_to_4h_fvg_pips=distance,
            risk_reward=setup_data.get('risk_reward', 0) or 0,
            setup_time=setup_data.get('setup_time', 'Unknown'),
            priority=setup_data.get('priority', 1)
        )
    
    def print_pullback_radar(self, pullback_setups: List[PullbackSetup]):
        """Print pullback radar table"""
        if not pullback_setups:
            print("\n📭 No active setups\n")
            return
        
        # Header
        print("\n" + "="*120)
        print("🎯 4H PULLBACK CHECKER - V8.2 Final Entry Scanner")
        print("="*120)
        print(f"⏰ Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Active Setups: {len(pullback_setups)}")
        print("="*120)
        
        # Count by status
        waiting_daily = sum(1 for s in pullback_setups if s.status == PullbackStatus.WAITING_DAILY_FVG)
        waiting_choch = sum(1 for s in pullback_setups if s.status == PullbackStatus.WAITING_4H_CHOCH)
        waiting_pullback = sum(1 for s in pullback_setups if s.status == PullbackStatus.WAITING_4H_PULLBACK)
        execute_now = sum(1 for s in pullback_setups if s.status == PullbackStatus.EXECUTE_NOW)
        invalid = sum(1 for s in pullback_setups if s.status == PullbackStatus.INVALIDATED)
        
        print(f"\n⏳ Waiting Daily FVG: {waiting_daily} | 👀 Waiting 4H CHoCH: {waiting_choch}")
        print(f"⏳ Waiting 4H Pullback: {waiting_pullback} | 🔥 EXECUTE NOW: {execute_now} | 🔴 Invalidated: {invalid}\n")
        
        # Sort
        status_priority = {
            PullbackStatus.EXECUTE_NOW: 1,
            PullbackStatus.WAITING_4H_PULLBACK: 2,
            PullbackStatus.WAITING_4H_CHOCH: 3,
            PullbackStatus.WAITING_DAILY_FVG: 4,
            PullbackStatus.INVALIDATED: 5
        }
        sorted_setups = sorted(pullback_setups, key=lambda s: status_priority[s.status])
        
        # Print each
        for i, setup in enumerate(sorted_setups, 1):
            self._print_pullback_row(i, setup)
        
        print("="*120)
        
        # Recommendations
        if execute_now > 0:
            print(f"\n🚨🚨🚨 URGENT: {execute_now} setup(s) READY FOR EXECUTION NOW! 🚨🚨🚨")
            print("   ➡️  Price has pulled back into 4H FVG!")
            print("   ➡️  Execute immediately at 4H FVG entry level!")
        
        if waiting_pullback > 0:
            print(f"\n⚠️  WATCH CLOSELY: {waiting_pullback} setup(s) waiting for 4H pullback")
            print("   ➡️  CHoCH 4H confirmed, monitor for retracement")
        
        print()
    
    def _print_pullback_row(self, index: int, setup: PullbackSetup):
        """Print one setup row"""
        status_emoji = setup.get_status_emoji()
        status_text = setup.status.value
        dir_emoji = setup.get_direction_emoji()
        
        price_str = f"{setup.current_price:.5f}" if setup.current_price > 0 else "N/A"
        
        # Print header
        print(f"\n{index}. {status_emoji} {setup.symbol} {dir_emoji} {setup.direction}")
        print(f"   {status_text}")
        print(f"   💰 Current Price: {price_str}")
        
        # Daily info
        print(f"   📊 DAILY: Entry={setup.entry_price_daily:.5f} | SL={setup.stop_loss:.5f} | TP={setup.take_profit:.5f}")
        print(f"   📦 Daily FVG: [{setup.fvg_daily_bottom:.5f} - {setup.fvg_daily_top:.5f}]")
        
        # 4H CHoCH info
        if setup.choch_4h_detected:
            print(f"   ✅ 4H CHoCH: {setup.choch_4h_direction.upper()} @ {setup.choch_4h_time}")
            if setup.choch_4h_price:
                print(f"      CHoCH Price: {setup.choch_4h_price:.5f}")
        else:
            if setup.choch_4h_direction:
                print(f"   ❌ 4H CHoCH: {setup.choch_4h_direction.upper()} (WRONG DIRECTION)")
            else:
                print(f"   ⏳ No 4H CHoCH detected yet")
        
        # 4H FVG info
        if setup.fvg_4h_detected:
            print(f"   📦 4H FVG: [{setup.fvg_4h_bottom:.5f} - {setup.fvg_4h_top:.5f}]")
            print(f"   🎯 4H FVG Entry: {setup.fvg_4h_entry:.5f}")
            
            # Distance info
            if setup.status == PullbackStatus.EXECUTE_NOW:
                print(f"   ✅✅✅ PRICE IN 4H FVG! Execute at {setup.fvg_4h_entry:.5f} NOW!")
            elif setup.status == PullbackStatus.WAITING_4H_PULLBACK:
                print(f"   ⏳ Distance to 4H FVG: {setup.distance_to_4h_fvg_pips:.1f} pips")
        else:
            if setup.choch_4h_detected:
                print(f"   ⚠️  4H FVG not detected (use CHoCH price as entry proxy)")
        
        print(f"   ⚡ R:R 1:{setup.risk_reward:.1f} | ⏰ Setup: {setup.setup_time}")
    
    def run_scan(self):
        """Run full pullback scan"""
        setups_data = self.load_monitoring_setups()
        
        if not setups_data:
            print("\n📭 No active setups\n")
            return
        
        pullback_setups = []
        skipped = 0
        
        for setup_data in setups_data:
            try:
                pb_setup = self.create_pullback_setup(setup_data)
                
                if pb_setup is None:
                    skipped += 1
                    continue
                
                pullback_setups.append(pb_setup)
            
            except Exception as e:
                print(f"⚠️  Error processing {setup_data.get('symbol', 'UNKNOWN')}: {e}")
                skipped += 1
        
        if skipped > 0:
            print(f"\n⚠️  Skipped {skipped} corrupted setup(s)\n")
        
        self.print_pullback_radar(pullback_setups)
    
    def run_watch_mode(self, interval_seconds: int = 30):
        """Watch mode with auto-refresh"""
        import time
        
        print("\n🔄 WATCH MODE ENABLED")
        print(f"⏰ Auto-refresh every {interval_seconds} seconds")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                print("\033[2J\033[H", end="")
                self.run_scan()
                time.sleep(interval_seconds)
        
        except KeyboardInterrupt:
            print("\n\n👋 Watch mode stopped\n")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='🎯 4H Pullback Checker V8.2 - Final Entry Scanner'
    )
    parser.add_argument('--watch', action='store_true', help='Watch mode')
    parser.add_argument('--interval', type=int, default=30, help='Refresh interval (default: 30s)')
    
    args = parser.parse_args()
    
    checker = PullbackChecker()
    
    if args.watch:
        checker.run_watch_mode(interval_seconds=args.interval)
    else:
        checker.run_scan()


if __name__ == '__main__':
    main()
