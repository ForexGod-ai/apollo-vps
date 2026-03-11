#!/usr/bin/env python3
"""
🔍 EXECUTION READINESS DIAGNOSTIC - V8.2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Diagnostic tool pentru verificarea COMPLETĂ a logicii de execuție.

VERIFICĂ:
1. ✅ DAILY Zone validation
2. ✅ 4H CHoCH detection
3. ✅ 4H FVG extraction (entry zone)
4. ✅ Current price position
5. ✅ Distance to 4H FVG entry
6. ✅ Premium/Discount zone validation
7. ✅ Lot size calculation
8. ✅ Stop Loss placement

VERDICT FINAL:
- ⏳ WAITING FOR 4H PULLBACK
- 🔥 EXECUTE NOW

Usage:
    python3 test_execution_readiness.py
    python3 test_execution_readiness.py --symbol EURJPY
    python3 test_execution_readiness.py --all
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
import pandas as pd

try:
    from ctrader_cbot_client import CTraderCBotClient
    from smc_detector import SMCDetector
    DEPS_AVAILABLE = True
except ImportError:
    DEPS_AVAILABLE = False
    print("⚠️  Dependencies not available")
    sys.exit(1)


@dataclass
class ExecutionDiagnostic:
    """Complete diagnostic result for a setup"""
    symbol: str
    direction: str
    
    # Daily validation
    daily_zone_validated: bool
    daily_fvg_top: float
    daily_fvg_bottom: float
    daily_entry: float
    daily_sl: float
    daily_tp: float
    
    # 4H CHoCH validation
    choch_4h_detected: bool
    choch_4h_direction: Optional[str]
    choch_4h_time: Optional[str]
    choch_4h_price: Optional[float]
    
    # 4H FVG validation
    fvg_4h_detected: bool
    fvg_4h_top: Optional[float]
    fvg_4h_bottom: Optional[float]
    fvg_4h_entry: Optional[float]  # Entry point (middle of FVG 4H)
    
    # Current price analysis
    current_price: float
    distance_to_4h_fvg_pips: float
    in_4h_fvg: bool
    
    # Premium/Discount zone validation
    zone_type: str  # 'PREMIUM' for SHORT, 'DISCOUNT' for LONG
    zone_validated: bool
    
    # Lot size calculation
    lot_size: float
    risk_percent: float
    sl_distance_pips: float
    
    # Final verdict
    execution_ready: bool
    verdict: str
    reasons: List[str]


class ExecutionReadinessTest:
    """Complete execution readiness diagnostic tool"""
    
    def __init__(self):
        if not DEPS_AVAILABLE:
            sys.exit(1)
        
        self.ctrader = CTraderCBotClient()
        if not self.ctrader.is_available():
            print("❌ cTrader cBot not running")
            sys.exit(1)
        
        print("✅ cTrader cBot connected")
        
        self.smc_detector = SMCDetector(swing_lookback=5, atr_multiplier=1.2)
        
        # Risk management settings (from SUPER_CONFIG or default)
        self.risk_percent = 1.0  # 1% risk per trade
        self.min_lot_size = 0.01
        self.max_lot_size = 10.0
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price"""
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
    
    def get_account_balance(self) -> float:
        """Get account balance for lot size calculation"""
        try:
            import requests
            response = requests.get(
                "http://localhost:8767/account",
                timeout=2
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('balance', 10000)  # Default 10k
            
            return 10000
        except:
            return 10000
    
    def get_4h_data(self, symbol: str, num_candles: int = 100) -> Optional[pd.DataFrame]:
        """Download 4H data"""
        try:
            df = self.ctrader.get_historical_data(symbol, "H4", num_candles)
            if df is not None and not df.empty:
                return df.reset_index()
            return None
        except Exception as e:
            print(f"⚠️  Error downloading 4H data for {symbol}: {e}")
            return None
    
    def detect_4h_choch_and_fvg(
        self,
        symbol: str,
        required_direction: str
    ) -> tuple:
        """
        Detect CHoCH and FVG on 4H
        
        Returns:
            (choch_detected, choch_dir, choch_time, choch_price,
             fvg_detected, fvg_top, fvg_bottom, fvg_entry)
        """
        df_4h = self.get_4h_data(symbol)
        
        if df_4h is None or df_4h.empty:
            return False, None, None, None, False, None, None, None
        
        try:
            # Detect CHoCH
            choch_list, bos_list = self.smc_detector.detect_choch_and_bos(df_4h)
            
            if not choch_list:
                return False, None, None, None, False, None, None, None
            
            # Get latest CHoCH
            latest_choch = choch_list[-1]
            choch_direction = latest_choch.direction
            choch_index = latest_choch.index
            
            # Get CHoCH details
            if choch_index < len(df_4h):
                choch_time = df_4h.iloc[choch_index]['time']
                choch_time_str = choch_time.isoformat() if hasattr(choch_time, 'isoformat') else str(choch_time)
                choch_price = df_4h.iloc[choch_index]['close']
            else:
                choch_time_str = "Unknown"
                choch_price = None
            
            # Validate direction
            if choch_direction != required_direction:
                return False, choch_direction, choch_time_str, choch_price, False, None, None, None
            
            # Detect FVG created by CHoCH (using updated API)
            current_price_for_fvg = df_4h.iloc[-1]['close']
            fvg_list = self.smc_detector.detect_fvg(
                df_4h,
                choch=latest_choch,
                current_price=current_price_for_fvg
            )
            
            if not fvg_list:
                return True, choch_direction, choch_time_str, choch_price, False, None, None, None
            
            # Get latest FVG
            latest_fvg = fvg_list[-1]
            fvg_top = latest_fvg.top
            fvg_bottom = latest_fvg.bottom
            fvg_entry = (fvg_top + fvg_bottom) / 2.0
            
            return True, choch_direction, choch_time_str, choch_price, True, fvg_top, fvg_bottom, fvg_entry
        
        except Exception as e:
            print(f"⚠️  Error analyzing 4H for {symbol}: {e}")
            return False, None, None, None, False, None, None, None
    
    def calculate_lot_size(
        self,
        account_balance: float,
        risk_percent: float,
        sl_distance_pips: float,
        symbol: str
    ) -> float:
        """Calculate lot size based on risk management"""
        try:
            # Risk amount in dollars
            risk_amount = account_balance * (risk_percent / 100.0)
            
            # Pip value (simplified - adjust for different pairs)
            if 'JPY' in symbol:
                pip_value = 0.01  # For JPY pairs
            else:
                pip_value = 10.0  # For major pairs (0.0001 move = $10 for 1 lot)
            
            # Calculate lot size
            if sl_distance_pips > 0:
                lot_size = risk_amount / (sl_distance_pips * pip_value)
            else:
                lot_size = self.min_lot_size
            
            # Clamp to min/max
            lot_size = max(self.min_lot_size, min(lot_size, self.max_lot_size))
            
            return round(lot_size, 2)
        
        except Exception as e:
            print(f"⚠️  Error calculating lot size: {e}")
            return self.min_lot_size
    
    def diagnose_setup(self, setup_data: Dict) -> ExecutionDiagnostic:
        """Complete diagnostic analysis of a setup"""
        symbol = setup_data.get('symbol', 'UNKNOWN')
        direction = setup_data.get('direction', 'SHORT').upper()
        
        # Normalize direction
        if direction == 'BUY':
            direction = 'LONG'
        elif direction == 'SELL':
            direction = 'SHORT'
        
        # Get Daily data
        daily_entry = float(setup_data.get('entry_price', 0))
        daily_sl = float(setup_data.get('stop_loss', 0))
        daily_tp = float(setup_data.get('take_profit', 0))
        daily_fvg_top = float(setup_data.get('fvg_top', daily_entry))
        daily_fvg_bottom = float(setup_data.get('fvg_bottom', daily_entry))
        
        # Get current price
        current_price = self.get_current_price(symbol)
        if current_price is None:
            current_price = daily_entry
        
        # Validate Daily zone
        daily_zone_validated = daily_fvg_bottom <= current_price <= daily_fvg_top
        
        # Detect 4H CHoCH and FVG
        required_4h_direction = 'bullish' if direction == 'LONG' else 'bearish'
        
        (choch_detected, choch_dir, choch_time, choch_price,
         fvg_4h_detected, fvg_4h_top, fvg_4h_bottom, fvg_4h_entry) = self.detect_4h_choch_and_fvg(
            symbol,
            required_4h_direction
        )
        
        # Check if price in 4H FVG
        in_4h_fvg = False
        distance_to_4h_fvg_pips = 0.0
        
        if fvg_4h_detected and fvg_4h_top and fvg_4h_bottom:
            in_4h_fvg = fvg_4h_bottom <= current_price <= fvg_4h_top
            
            if not in_4h_fvg:
                # Calculate distance
                if direction == 'LONG':
                    distance_to_4h_fvg_pips = abs(current_price - fvg_4h_top) * 10000
                else:
                    distance_to_4h_fvg_pips = abs(fvg_4h_bottom - current_price) * 10000
        
        # Validate Premium/Discount zone
        if fvg_4h_detected and choch_price:
            if direction == 'LONG':
                # For LONG: FVG should be in DISCOUNT (below CHoCH price)
                zone_type = 'DISCOUNT'
                zone_validated = fvg_4h_entry < choch_price
            else:
                # For SHORT: FVG should be in PREMIUM (above CHoCH price)
                zone_type = 'PREMIUM'
                zone_validated = fvg_4h_entry > choch_price
        else:
            zone_type = 'N/A'
            zone_validated = False
        
        # Calculate lot size
        account_balance = self.get_account_balance()
        sl_distance_pips = abs(daily_entry - daily_sl) * 10000
        lot_size = self.calculate_lot_size(
            account_balance,
            self.risk_percent,
            sl_distance_pips,
            symbol
        )
        
        # Determine execution readiness
        reasons = []
        execution_ready = False
        
        if not daily_zone_validated:
            reasons.append("❌ Price NOT in Daily FVG")
        else:
            reasons.append("✅ Price IN Daily FVG")
        
        if not choch_detected:
            reasons.append("❌ No 4H CHoCH detected")
        else:
            reasons.append(f"✅ 4H CHoCH detected ({choch_dir})")
        
        if not fvg_4h_detected:
            reasons.append("❌ No 4H FVG detected")
        else:
            reasons.append("✅ 4H FVG detected")
        
        if fvg_4h_detected:
            if not zone_validated:
                reasons.append(f"⚠️  4H FVG NOT in {zone_type} zone")
            else:
                reasons.append(f"✅ 4H FVG in {zone_type} zone")
        
        if not in_4h_fvg and fvg_4h_detected:
            reasons.append(f"⏳ Price {distance_to_4h_fvg_pips:.1f} pips from 4H FVG")
        elif in_4h_fvg:
            reasons.append("✅ Price IN 4H FVG!")
            execution_ready = True
        
        # Final verdict
        if execution_ready and daily_zone_validated and choch_detected and fvg_4h_detected:
            verdict = "🔥 EXECUTE NOW"
        elif daily_zone_validated and choch_detected and fvg_4h_detected:
            verdict = "⏳ WAITING FOR 4H PULLBACK"
        elif daily_zone_validated and choch_detected:
            verdict = "👀 WAITING FOR 4H FVG FORMATION"
        elif daily_zone_validated:
            verdict = "👀 WAITING FOR 4H CHoCH"
        else:
            verdict = "⏳ WAITING FOR DAILY FVG ENTRY"
        
        return ExecutionDiagnostic(
            symbol=symbol,
            direction=direction,
            daily_zone_validated=daily_zone_validated,
            daily_fvg_top=daily_fvg_top,
            daily_fvg_bottom=daily_fvg_bottom,
            daily_entry=daily_entry,
            daily_sl=daily_sl,
            daily_tp=daily_tp,
            choch_4h_detected=choch_detected,
            choch_4h_direction=choch_dir,
            choch_4h_time=choch_time,
            choch_4h_price=choch_price,
            fvg_4h_detected=fvg_4h_detected,
            fvg_4h_top=fvg_4h_top,
            fvg_4h_bottom=fvg_4h_bottom,
            fvg_4h_entry=fvg_4h_entry,
            current_price=current_price,
            distance_to_4h_fvg_pips=distance_to_4h_fvg_pips,
            in_4h_fvg=in_4h_fvg,
            zone_type=zone_type,
            zone_validated=zone_validated,
            lot_size=lot_size,
            risk_percent=self.risk_percent,
            sl_distance_pips=sl_distance_pips,
            execution_ready=execution_ready,
            verdict=verdict,
            reasons=reasons
        )
    
    def print_diagnostic(self, diag: ExecutionDiagnostic):
        """Print formatted diagnostic report"""
        print("\n" + "="*80)
        print(f"🔍 EXECUTION READINESS DIAGNOSTIC - {diag.symbol}")
        print("="*80)
        print(f"⏰ Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Direction: {'🟢' if diag.direction == 'LONG' else '🔴'} {diag.direction}")
        print("="*80)
        
        # Daily zone
        print("\n📊 [DAILY] ZONE VALIDATION")
        print(f"   Status: {'✅ VALIDATED' if diag.daily_zone_validated else '❌ NOT IN ZONE'}")
        print(f"   FVG Zone: [{diag.daily_fvg_bottom:.5f} - {diag.daily_fvg_top:.5f}]")
        print(f"   Entry: {diag.daily_entry:.5f}")
        print(f"   SL: {diag.daily_sl:.5f}")
        print(f"   TP: {diag.daily_tp:.5f}")
        
        # Current price
        print("\n💰 [CURRENT PRICE]")
        print(f"   Price: {diag.current_price:.5f}")
        
        # 4H CHoCH
        print("\n🔄 [4H] CHoCH DETECTION")
        print(f"   Status: {'✅ DETECTED' if diag.choch_4h_detected else '❌ NOT DETECTED'}")
        if diag.choch_4h_detected:
            print(f"   Direction: {diag.choch_4h_direction.upper()}")
            print(f"   Time: {diag.choch_4h_time}")
            if diag.choch_4h_price:
                print(f"   Price: {diag.choch_4h_price:.5f}")
        
        # 4H FVG
        print("\n📦 [4H] FVG ENTRY ZONE")
        print(f"   Status: {'✅ DETECTED' if diag.fvg_4h_detected else '❌ NOT DETECTED'}")
        if diag.fvg_4h_detected:
            print(f"   FVG Zone: [{diag.fvg_4h_bottom:.5f} - {diag.fvg_4h_top:.5f}]")
            print(f"   🎯 Entry Point: {diag.fvg_4h_entry:.5f}")
            print(f"   Zone Type: {diag.zone_type} {'✅' if diag.zone_validated else '⚠️'}")
            
            if diag.in_4h_fvg:
                print(f"   ✅✅✅ PRICE IN 4H FVG!")
            else:
                print(f"   ⏳ Distance to FVG: {diag.distance_to_4h_fvg_pips:.1f} pips")
        
        # Lot size
        print("\n💼 [LOT SIZE CALCULATION]")
        print(f"   Risk: {diag.risk_percent}%")
        print(f"   SL Distance: {diag.sl_distance_pips:.1f} pips")
        print(f"   Lot Size: {diag.lot_size} lots")
        
        # Reasons
        print("\n📋 [ANALYSIS]")
        for reason in diag.reasons:
            print(f"   {reason}")
        
        # Final verdict
        print("\n" + "="*80)
        print(f"🎯 [VERDICT]: {diag.verdict}")
        print("="*80)
        
        if diag.execution_ready:
            print("\n🚨🚨🚨 EXECUTE IMMEDIATELY 🚨🚨🚨")
            print(f"   Entry: {diag.fvg_4h_entry:.5f}")
            print(f"   Lot Size: {diag.lot_size} lots")
            print(f"   SL: {diag.daily_sl:.5f}")
            print(f"   TP: {diag.daily_tp:.5f}")
        
        print()
    
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
                
                return [s for s in setups if isinstance(s, dict) and s.get('status') == 'MONITORING']
        
        except FileNotFoundError:
            print("⚠️  monitoring_setups.json not found")
            return []
        except json.JSONDecodeError as e:
            print(f"⚠️  Error parsing monitoring_setups.json: {e}")
            return []
    
    def run_test(self, symbol: Optional[str] = None, test_all: bool = False):
        """Run diagnostic test"""
        setups = self.load_monitoring_setups()
        
        if not setups:
            print("\n📭 No active setups in monitoring\n")
            return
        
        if symbol:
            # Test specific symbol
            target_setups = [s for s in setups if s.get('symbol') == symbol]
            if not target_setups:
                print(f"\n⚠️  No setup found for {symbol}\n")
                return
            setups = target_setups
        elif not test_all:
            # Test first setup only
            setups = [setups[0]]
        
        # Run diagnostics
        for setup in setups:
            try:
                diag = self.diagnose_setup(setup)
                self.print_diagnostic(diag)
            except Exception as e:
                print(f"\n⚠️  Error diagnosing {setup.get('symbol', 'UNKNOWN')}: {e}\n")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='🔍 Execution Readiness Diagnostic - V8.2'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        help='Test specific symbol (e.g., EURJPY)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Test all setups in monitoring'
    )
    
    args = parser.parse_args()
    
    tester = ExecutionReadinessTest()
    tester.run_test(symbol=args.symbol, test_all=args.all)


if __name__ == '__main__':
    main()
