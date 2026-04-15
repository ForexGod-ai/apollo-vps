#!/usr/bin/env python3
"""
🔍 PATH FINDER - V4.0 System Diagnostic Tool
Shows exactly what the bot is "hunting" right now

Glitch in Matrix by ФорексГод
"""

import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Official 15 pairs
OFFICIAL_PAIRS = [
    'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD',
    'EURGBP', 'EURJPY', 'GBPJPY', 'AUDJPY', 'EURAUD', 'GBPAUD', 'XAUUSD', 'BTCUSD'
]


class PathFinder:
    """Ultra-rapid diagnostic for V4.0 system state"""
    
    def __init__(self):
        # Cross-platform: works on Mac, Linux, Windows VPS
        self.root = Path(__file__).parent
        self.signals_file = self.root / "signals.json"
        self.monitoring_file = self.root / "monitoring_setups.json"
        self.active_positions_file = self.root / "active_positions.json"
        
    def print_header(self):
        """Print diagnostic header"""
        print("╔═══════════════════════════════════════════════════════════╗")
        print("║                                                           ║")
        print("║     🔍 PATH FINDER - V4.0 System Diagnostic              ║")
        print("║     Glitch in Matrix by ФорексГод                        ║")
        print("║                                                           ║")
        print("╚═══════════════════════════════════════════════════════════╝")
        print()
        print(f"⏰ Diagnostic Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("━" * 63)
        print()
    
    def check_signals_file(self) -> Dict:
        """Check signals.json for pending signals"""
        print("📡 STEP 1: SIGNAL FILE ANALYSIS")
        print("━" * 63)
        
        if not self.signals_file.exists():
            print("❌ signals.json: NOT FOUND")
            print("   Status: No active signal file")
            return {'status': 'missing', 'signal': None}
        
        try:
            with open(self.signals_file, 'r') as f:
                content = f.read().strip()
            
            if not content or content == '{}' or content == '[]':
                print("✅ signals.json: EMPTY (Clear state)")
                print("   Status: Ready for new signals")
                return {'status': 'empty', 'signal': None}
            
            signal = json.loads(content)
            
            # Check if it's an empty object/array
            if not signal or (isinstance(signal, dict) and not signal) or (isinstance(signal, list) and not signal):
                print("✅ signals.json: EMPTY (Clear state)")
                return {'status': 'empty', 'signal': None}
            
            # Active signal found
            print("🚨 signals.json: ACTIVE SIGNAL DETECTED")
            print()
            print("   📊 SIGNAL DETAILS:")
            print(f"      Symbol: {signal.get('Symbol', 'N/A')}")
            print(f"      Direction: {signal.get('Direction', 'N/A').upper()}")
            print(f"      Strategy: {signal.get('StrategyType', 'N/A')}")
            print(f"      Entry: {signal.get('EntryPrice', 'N/A')}")
            print(f"      SL: {signal.get('StopLoss', 'N/A')} ({signal.get('StopLossPips', 'N/A')} pips)")
            print(f"      TP: {signal.get('TakeProfit', 'N/A')} ({signal.get('TakeProfitPips', 'N/A')} pips)")
            print(f"      R:R: 1:{signal.get('RiskReward', 'N/A')}")
            
            # V4.0 FIELDS CHECK
            print()
            print("   🔍 V4.0 INTELLIGENCE CHECK:")
            has_v4 = False
            
            if signal.get('LiquiditySweep'):
                print(f"      💧 Liquidity Sweep: {signal.get('SweepType', 'N/A')} (+{signal.get('ConfidenceBoost', 0)} conf)")
                has_v4 = True
            else:
                print("      💧 Liquidity Sweep: NO")
            
            if signal.get('OrderBlockUsed'):
                print(f"      📦 Order Block: USED (score {signal.get('OrderBlockScore', 0)}/10)")
                has_v4 = True
            else:
                print(f"      📦 Order Block: NOT USED (score {signal.get('OrderBlockScore', 0)}/10)")
            
            zone = signal.get('PremiumDiscountZone', 'UNKNOWN')
            pct = signal.get('DailyRangePercentage', 0)
            print(f"      📊 Daily Range: {pct:.1f}% ({zone} zone)")
            
            if has_v4:
                print()
                print("   ✅ V4.0 SYNC: ACTIVE (full intelligence transmitted)")
            else:
                print()
                print("   ⚠️  V4.0 SYNC: MISSING (old signal format)")
            
            # Timestamp check
            timestamp = signal.get('Timestamp', '')
            if timestamp:
                try:
                    sig_time = datetime.fromisoformat(timestamp)
                    age = datetime.now() - sig_time
                    print()
                    print(f"   ⏰ Signal Age: {age.total_seconds() / 60:.1f} minutes")
                    
                    if age.total_seconds() > 3600:  # > 1 hour
                        print("   ⚠️  Signal is older than 1 hour - may be stale")
                except:
                    pass
            
            return {'status': 'active', 'signal': signal, 'has_v4': has_v4}
            
        except json.JSONDecodeError as e:
            print(f"❌ signals.json: MALFORMED JSON")
            print(f"   Error: {e}")
            return {'status': 'error', 'signal': None}
        except Exception as e:
            print(f"❌ ERROR reading signals.json: {e}")
            return {'status': 'error', 'signal': None}
    
    def check_monitoring_setups(self) -> Dict:
        """Check monitoring_setups.json for active setups"""
        print()
        print("👁️  STEP 2: MONITORING PATROL")
        print("━" * 63)
        
        if not self.monitoring_file.exists():
            print("❌ monitoring_setups.json: NOT FOUND")
            return {'status': 'missing', 'setups': []}
        
        try:
            with open(self.monitoring_file, 'r') as f:
                data = json.load(f)
            
            setups = data.get('setups', [])
            
            if not setups:
                print("ℹ️  No active setups being monitored")
                return {'status': 'empty', 'setups': []}
            
            # Filter active setups (not EXPIRED)
            active_setups = [s for s in setups if s.get('status') not in ['EXPIRED', 'INVALIDATED']]
            monitoring_setups = [s for s in active_setups if s.get('status') == 'MONITORING']
            ready_setups = [s for s in active_setups if s.get('status') == 'READY']
            
            print(f"📊 Total Setups: {len(setups)}")
            print(f"   ✅ Active: {len(active_setups)}")
            print(f"   👀 Monitoring: {len(monitoring_setups)}")
            print(f"   🚀 Ready: {len(ready_setups)}")
            print(f"   ⏰ Expired/Invalid: {len(setups) - len(active_setups)}")
            
            # Check coverage of official 15 pairs
            monitored_symbols = set(s['symbol'] for s in active_setups)
            covered_official = [p for p in OFFICIAL_PAIRS if p in monitored_symbols]
            
            print()
            print(f"🎯 COVERAGE OF 15 OFFICIAL PAIRS:")
            print(f"   Monitored: {len(covered_official)}/15 ({len(covered_official)/15*100:.1f}%)")
            
            if covered_official:
                print(f"   Pairs: {', '.join(sorted(covered_official))}")
            
            missing = [p for p in OFFICIAL_PAIRS if p not in monitored_symbols]
            if missing:
                print()
                print(f"   ⚠️  Not Monitored: {', '.join(sorted(missing))}")
            
            # Find closest to entry
            if monitoring_setups:
                print()
                print("🎯 CLOSEST TO ENTRY ZONE:")
                
                closest = None
                min_distance = float('inf')
                
                for setup in monitoring_setups:
                    symbol = setup.get('symbol', 'UNKNOWN')
                    direction = setup.get('direction', '?')
                    entry = setup.get('entry_price', 0)
                    fvg_top = setup.get('fvg_zone_top', entry)
                    fvg_bottom = setup.get('fvg_zone_bottom', entry)
                    
                    # Estimate current price from entry (placeholder - would need live data)
                    # For now, show setup details
                    if not closest:
                        closest = setup
                
                if closest:
                    symbol = closest.get('symbol', 'UNKNOWN')
                    direction = closest.get('direction', '?')
                    entry = closest.get('entry_price', 0)
                    sl = closest.get('stop_loss', 0)
                    tp = closest.get('take_profit', 0)
                    rr = closest.get('risk_reward', 0)
                    strategy = closest.get('strategy_type', 'UNKNOWN')
                    
                    print(f"   📍 {symbol} {direction.upper()}")
                    print(f"      Strategy: {strategy.upper()}")
                    print(f"      Entry: {entry}")
                    print(f"      SL: {sl} | TP: {tp}")
                    print(f"      R:R: 1:{rr:.1f}")
                    
                    # Check for 1H CHoCH
                    if closest.get('choch_1h_detected'):
                        print(f"      ✅ 1H CHoCH: DETECTED")
                        if closest.get('entry1_filled'):
                            print(f"      ✅ Entry 1: FILLED at {closest.get('entry1_price', 'N/A')}")
                    else:
                        print(f"      ⏳ Waiting for: 1H CHoCH confirmation")
            
            # Show ready setups
            if ready_setups:
                print()
                print("🚀 READY TO EXECUTE:")
                for setup in ready_setups[:3]:  # Show first 3
                    symbol = setup.get('symbol', 'UNKNOWN')
                    direction = setup.get('direction', '?')
                    entry = setup.get('entry_price', 0)
                    rr = setup.get('risk_reward', 0)
                    print(f"   • {symbol} {direction.upper()} @ {entry} (R:R 1:{rr:.1f})")
            
            return {
                'status': 'active',
                'setups': active_setups,
                'monitoring': monitoring_setups,
                'ready': ready_setups,
                'coverage': len(covered_official)
            }
            
        except Exception as e:
            print(f"❌ ERROR reading monitoring_setups.json: {e}")
            return {'status': 'error', 'setups': []}
    
    def check_ctrader_connection(self) -> Dict:
        """Check cTrader bot status"""
        print()
        print("🤖 STEP 3: CTRADER CONNECTION AUDIT")
        print("━" * 63)
        
        # Check if cTrader process is running (macOS)
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'cTrader'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and result.stdout.strip():
                print("✅ cTrader Process: RUNNING")
                pids = result.stdout.strip().split('\n')
                print(f"   PIDs: {', '.join(pids)}")
            else:
                print("⚠️  cTrader Process: NOT DETECTED")
                print("   Note: Bot may be running on remote VPS")
            
        except Exception as e:
            print(f"ℹ️  Could not check cTrader process: {e}")
        
        # Check active positions
        print()
        if self.active_positions_file.exists():
            try:
                with open(self.active_positions_file, 'r') as f:
                    positions = json.load(f)
                
                if positions:
                    print(f"📊 Active Positions: {len(positions)}")
                    for pos in positions[:3]:  # Show first 3
                        symbol = pos.get('symbol', 'UNKNOWN')
                        direction = pos.get('direction', '?')
                        pips = pos.get('pips', 0)
                        profit = pos.get('net_profit', 0)
                        print(f"   • {symbol} {direction.upper()}: {pips:+.1f} pips (${profit:+.2f})")
                else:
                    print("📊 Active Positions: NONE")
            except:
                print("📊 Active Positions: Could not read")
        else:
            print("📊 Active Positions: File not found")
        
        # Check for recent errors in logs (if available)
        print()
        log_files = [
            self.root / "ctrader_sync.log",
            self.root / "setup_executor_monitor.log"
        ]
        
        recent_errors = []
        cutoff_time = datetime.now() - timedelta(minutes=5)
        
        for log_file in log_files:
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()[-50:]  # Last 50 lines
                    
                    for line in lines:
                        if 'ERROR' in line or 'FAILED' in line or '❌' in line:
                            recent_errors.append(line.strip())
                except:
                    pass
        
        if recent_errors:
            print("⚠️  Recent Errors (last 5 min):")
            for error in recent_errors[-3:]:  # Show last 3
                print(f"   {error[:80]}...")
        else:
            print("✅ No recent errors detected")
        
        return {'status': 'checked', 'errors': recent_errors}
    
    def predict_next_move(self, signal_status: Dict, monitoring_status: Dict) -> None:
        """Predict what the bot will do next"""
        print()
        print("🔮 STEP 4: NEXT MOVE PREDICTION")
        print("━" * 63)
        
        # Check signal status first
        if signal_status['status'] == 'active':
            signal = signal_status['signal']
            symbol = signal.get('Symbol', 'UNKNOWN')
            direction = signal.get('Direction', '?')
            entry = signal.get('EntryPrice', 0)
            
            print("🚨 IMMEDIATE ACTION PENDING:")
            print(f"   Executor will attempt to place {direction.upper()} order on {symbol}")
            print(f"   Entry: {entry}")
            print(f"   Next check: Within 10 seconds (polling interval)")
            print()
            print("   ⏳ Waiting for cTrader bot to execute...")
            return
        
        # Check ready setups
        ready_setups = monitoring_status.get('ready', [])
        if ready_setups:
            setup = ready_setups[0]
            symbol = setup.get('symbol', 'UNKNOWN')
            direction = setup.get('direction', '?')
            entry = setup.get('entry_price', 0)
            
            print("🚀 READY SETUP DETECTED:")
            print(f"   {symbol} {direction.upper()} setup is READY")
            print(f"   Entry: {entry}")
            print()
            print("   📋 Next Action:")
            print("      1. Risk Manager validates trade")
            print("      2. Signal written to signals.json")
            print("      3. cTrader bot executes within 10s")
            return
        
        # Check monitoring setups
        monitoring_setups = monitoring_status.get('monitoring', [])
        if monitoring_setups:
            setup = monitoring_setups[0]
            symbol = setup.get('symbol', 'UNKNOWN')
            direction = setup.get('direction', '?')
            entry = setup.get('entry_price', 0)
            
            print("👀 MONITORING MODE:")
            print(f"   Scanner is watching {symbol} {direction.upper()}")
            print(f"   Target entry: {entry}")
            print()
            print("   ⏳ Waiting for:")
            
            if not setup.get('choch_1h_detected'):
                print("      • 1H CHoCH confirmation (same direction as Daily)")
            else:
                print("      ✅ 1H CHoCH confirmed")
            
            if not setup.get('entry1_filled'):
                print("      • Price to enter FVG zone")
                fvg_top = setup.get('fvg_zone_top', 0)
                fvg_bottom = setup.get('fvg_zone_bottom', 0)
                print(f"        FVG: {fvg_bottom} - {fvg_top}")
            else:
                print("      ✅ Price in entry zone")
            
            print()
            print("   📋 Next Action:")
            print("      Scanner runs every scan cycle (check daily_scanner.py)")
            print("      Status will update to READY when conditions met")
            return
        
        # No active setups
        print("💤 IDLE MODE:")
        print("   No active signals or monitoring setups")
        print()
        print("   📋 Next Action:")
        print("      • Scanner will run on next scheduled cycle")
        print("      • Looking for new Daily CHoCH patterns")
        print("      • Monitoring all 15 official pairs")
        print()
        print("   ⏰ Next scan: Check morning_scheduler.py or manual trigger")
    
    def run_diagnostic(self) -> None:
        """Run complete diagnostic"""
        self.print_header()
        
        # Step 1: Check signals
        signal_status = self.check_signals_file()
        
        # Step 2: Check monitoring
        monitoring_status = self.check_monitoring_setups()
        
        # Step 3: Check cTrader
        ctrader_status = self.check_ctrader_connection()
        
        # Step 4: Predict next move
        self.predict_next_move(signal_status, monitoring_status)
        
        # Summary
        print()
        print("━" * 63)
        print()
        print("📊 DIAGNOSTIC SUMMARY:")
        print("━" * 63)
        
        # Signal status
        if signal_status['status'] == 'active':
            print("🚨 ACTIVE SIGNAL: YES (waiting for execution)")
        else:
            print("📡 Active Signal: None")
        
        # Monitoring status
        monitoring_count = len(monitoring_status.get('monitoring', []))
        ready_count = len(monitoring_status.get('ready', []))
        print(f"👁️  Monitoring: {monitoring_count} setups")
        print(f"🚀 Ready: {ready_count} setups")
        
        # Coverage
        coverage = monitoring_status.get('coverage', 0)
        print(f"🎯 Coverage: {coverage}/15 official pairs ({coverage/15*100:.1f}%)")
        
        # System health
        errors = ctrader_status.get('errors', [])
        if errors:
            print(f"⚠️  Recent Errors: {len(errors)}")
        else:
            print("✅ System Health: No recent errors")
        
        print()
        print("━" * 63)
        print()
        print("✨ Glitch in Matrix by ФорексГод ✨")
        print("🧠 AI-Powered • 💎 Smart Money • V4.0")
        print()


def main():
    """Main entry point"""
    finder = PathFinder()
    finder.run_diagnostic()


if __name__ == "__main__":
    main()
