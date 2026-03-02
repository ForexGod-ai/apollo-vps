#!/usr/bin/env python3
"""
🔍 SPECIFIC TRADES RECOVERY TOOL
Recover and unblock specific rejected trades: GBPNZD & USDCHF

Usage:
    python3 recover_specific_trades.py
    python3 recover_specific_trades.py --symbols GBPNZD USDCHF
    python3 recover_specific_trades.py --date 2026-02-26
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import argparse

class SpecificTradeRecovery:
    def __init__(self, symbols: List[str], target_date: Optional[str] = None):
        self.target_symbols = [s.upper() for s in symbols]
        self.target_date = target_date or datetime.now().strftime("%Y-%m-%d")
        
        # File paths
        self.log_files = [
            Path("setup_monitor.log"),
            Path("logs/setup_executor.log"),
            Path("logs/setup_monitor.log"),
            Path("logs/scanner.log"),
            Path("app.log"),
        ]
        
        self.cache_file = Path("monitoring_setups.json")
        self.processed_signals_file = Path("processed_signals.txt")
        
        self.found_trades: Dict[str, Dict] = {}
        
    def scan_logs_for_trades(self):
        """Scan all log files for specific symbols"""
        print(f"\n{'='*100}")
        print(f"🔍 INVESTIGATING REJECTED TRADES")
        print(f"{'='*100}")
        print(f"📅 Date: {self.target_date}")
        print(f"💱 Symbols: {', '.join(self.target_symbols)}")
        print(f"{'='*100}\n")
        
        for log_file in self.log_files:
            if not log_file.exists():
                continue
                
            print(f"📂 Scanning: {log_file}")
            self._parse_log_file(log_file)
        
        print(f"\n✅ Investigation complete: Found {len(self.found_trades)} trades")
    
    def _parse_log_file(self, log_file: Path):
        """Parse single log file for trade details"""
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            for symbol in self.target_symbols:
                if symbol not in content:
                    continue
                
                # Find all lines mentioning this symbol
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if self.target_date not in line or symbol not in line:
                        continue
                    
                    # Check if this is a rejection or signal generation
                    if any(keyword in line for keyword in ['REJECTED', 'RESPINS', 'Max positions']):
                        self._extract_rejection_details(symbol, line, lines, i)
                    elif any(keyword in line for keyword in ['NEW SIGNAL', 'SETUP DETECTED', '📊']):
                        self._extract_signal_details(symbol, line, lines, i)
        
        except Exception as e:
            print(f"⚠️  Error reading {log_file}: {e}")
    
    def _extract_rejection_details(self, symbol: str, line: str, all_lines: List[str], index: int):
        """Extract rejection details from log line"""
        # Extract timestamp
        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
        timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"
        
        # Extract reason
        reason = "Unknown"
        if 'Max positions reached' in line:
            count_match = re.search(r'(\d+)/(\d+)', line)
            if count_match:
                reason = f"Max positions reached ({count_match.group(1)}/{count_match.group(2)})"
            else:
                reason = "Max positions reached"
        elif 'Kill switch' in line:
            reason = "Kill switch active"
        elif 'Daily loss' in line:
            reason = "Daily loss limit"
        else:
            reason_match = re.search(r'[Rr]eason[:\s]+([^\n]+)', line)
            if reason_match:
                reason = reason_match.group(1).strip()
        
        # Look for direction in nearby lines
        direction = "UNKNOWN"
        for offset in range(-5, 6):
            if 0 <= index + offset < len(all_lines):
                nearby_line = all_lines[index + offset]
                if symbol in nearby_line:
                    dir_match = re.search(r'(?:Direction|direction)[:\s]+([A-Z]+)', nearby_line, re.IGNORECASE)
                    if dir_match:
                        direction = dir_match.group(1).upper()
                        break
        
        # Store or update trade info
        if symbol not in self.found_trades:
            self.found_trades[symbol] = {}
        
        self.found_trades[symbol]['rejection'] = {
            'timestamp': timestamp,
            'reason': reason,
            'direction': direction,
            'raw_line': line.strip()
        }
    
    def _extract_signal_details(self, symbol: str, line: str, all_lines: List[str], index: int):
        """Extract signal generation details"""
        # Extract timestamp
        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
        timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"
        
        # Look for detailed signal parameters in nearby lines (next 20 lines)
        signal_details = {
            'timestamp': timestamp,
            'direction': None,
            'entry': None,
            'stop_loss': None,
            'take_profit': None,
            'risk_reward': None,
            'strategy': None,
            'ml_score': None
        }
        
        # Search in context window
        context_lines = all_lines[index:min(index + 20, len(all_lines))]
        context = '\n'.join(context_lines)
        
        # Extract direction
        dir_match = re.search(r'(?:Direction|direction)[:\s]+([A-Z]+)', context, re.IGNORECASE)
        if dir_match:
            signal_details['direction'] = dir_match.group(1).upper()
        
        # Extract entry price
        entry_match = re.search(r'(?:Entry|entry_price)[:\s]+([\d.]+)', context)
        if entry_match:
            signal_details['entry'] = float(entry_match.group(1))
        
        # Extract stop loss
        sl_match = re.search(r'(?:SL|Stop[_ ]?Loss|stop_loss)[:\s]+([\d.]+)', context, re.IGNORECASE)
        if sl_match:
            signal_details['stop_loss'] = float(sl_match.group(1))
        
        # Extract take profit
        tp_match = re.search(r'(?:TP|Take[_ ]?Profit|take_profit)[:\s]+([\d.]+)', context, re.IGNORECASE)
        if tp_match:
            signal_details['take_profit'] = float(tp_match.group(1))
        
        # Extract R:R ratio
        rr_match = re.search(r'(?:R:R|Risk[_ ]?Reward)[:\s]+1?:?([\d.]+)', context, re.IGNORECASE)
        if rr_match:
            signal_details['risk_reward'] = float(rr_match.group(1))
        
        # Extract strategy
        strategy_match = re.search(r'(?:Strategy|strategy_type)[:\s]+([A-Z_]+)', context, re.IGNORECASE)
        if strategy_match:
            signal_details['strategy'] = strategy_match.group(1)
        
        # Extract ML score
        ml_match = re.search(r'(?:ML[_ ]?Score|ml_score)[:\s]+([\d.]+)', context, re.IGNORECASE)
        if ml_match:
            signal_details['ml_score'] = float(ml_match.group(1))
        
        # Store signal details
        if symbol not in self.found_trades:
            self.found_trades[symbol] = {}
        
        self.found_trades[symbol]['signal'] = signal_details
    
    def display_trade_details(self):
        """Display detailed information about found trades"""
        if not self.found_trades:
            print("\n❌ No trades found for specified symbols!")
            return
        
        print(f"\n{'='*100}")
        print(f"📊 DETAILED TRADE INFORMATION")
        print(f"{'='*100}\n")
        
        for symbol in sorted(self.found_trades.keys()):
            trade_data = self.found_trades[symbol]
            
            print(f"{'='*100}")
            print(f"💱 {symbol}")
            print(f"{'='*100}")
            
            # Signal details
            if 'signal' in trade_data:
                signal = trade_data['signal']
                print(f"\n✅ SIGNAL GENERATED:")
                print(f"   🕒 Time:          {signal['timestamp']}")
                print(f"   ↕️  Direction:     {signal['direction'] or 'N/A'}")
                print(f"   💰 Entry:         {signal['entry'] or 'N/A'}")
                print(f"   🛑 Stop Loss:     {signal['stop_loss'] or 'N/A'}")
                print(f"   🎯 Take Profit:   {signal['take_profit'] or 'N/A'}")
                print(f"   📊 R:R Ratio:     1:{signal['risk_reward'] or 'N/A'}")
                print(f"   🎲 Strategy:      {signal['strategy'] or 'N/A'}")
                print(f"   🧠 ML Score:      {signal['ml_score'] or 'N/A'}")
                
                # Calculate pip distances if we have prices
                if signal['entry'] and signal['stop_loss']:
                    sl_pips = abs(signal['entry'] - signal['stop_loss']) * 10000
                    print(f"   📏 SL Distance:   {sl_pips:.1f} pips")
                
                if signal['entry'] and signal['take_profit']:
                    tp_pips = abs(signal['take_profit'] - signal['entry']) * 10000
                    print(f"   📏 TP Distance:   {tp_pips:.1f} pips")
            
            # Rejection details
            if 'rejection' in trade_data:
                rejection = trade_data['rejection']
                print(f"\n❌ TRADE REJECTED:")
                print(f"   🕒 Time:          {rejection['timestamp']}")
                print(f"   ↕️  Direction:     {rejection['direction']}")
                print(f"   🚫 Reason:        {rejection['reason']}")
                print(f"   📝 Raw message:   {rejection['raw_line'][:80]}...")
            
            print()
    
    def check_cache_status(self):
        """Check if trades are blocked in cache"""
        print(f"\n{'='*100}")
        print(f"🔍 CACHE STATUS CHECK")
        print(f"{'='*100}\n")
        
        # Check monitoring_setups.json
        monitoring_blocked = {}
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                # Check for our symbols
                setups = cache_data.get('setups', []) if isinstance(cache_data, dict) else cache_data
                
                for setup in setups:
                    symbol = setup.get('symbol', '')
                    if symbol in self.target_symbols:
                        monitoring_blocked[symbol] = setup
                        print(f"💾 {symbol} found in monitoring_setups.json")
                        print(f"   Setup ID: {setup.get('setup_id', 'N/A')}")
                        print(f"   Status: {setup.get('status', 'N/A')}")
                        print(f"   Created: {setup.get('setup_time', 'N/A')}")
            
            except Exception as e:
                print(f"⚠️  Error reading monitoring cache: {e}")
        
        # Check processed_signals.txt
        processed_blocked = {}
        if self.processed_signals_file.exists():
            try:
                with open(self.processed_signals_file, 'r') as f:
                    signals = [line.strip() for line in f if line.strip()]
                
                for signal_id in signals:
                    for symbol in self.target_symbols:
                        if symbol in signal_id:
                            if symbol not in processed_blocked:
                                processed_blocked[symbol] = []
                            processed_blocked[symbol].append(signal_id)
                
                for symbol, ids in processed_blocked.items():
                    print(f"\n🔒 {symbol} found in processed_signals.txt:")
                    for sig_id in ids:
                        print(f"   • {sig_id}")
            
            except Exception as e:
                print(f"⚠️  Error reading processed signals: {e}")
        
        self.monitoring_blocked = monitoring_blocked
        self.processed_blocked = processed_blocked
        
        if not monitoring_blocked and not processed_blocked:
            print("\n✅ No cache blocks found - trades can be re-scanned immediately!")
        
        return monitoring_blocked or processed_blocked
    
    def clear_cache_interactive(self):
        """Interactive cache clearing"""
        has_blocks = self.check_cache_status()
        
        if not has_blocks:
            return
        
        print(f"\n{'='*100}")
        print(f"🔄 CACHE RECOVERY OPTIONS")
        print(f"{'='*100}\n")
        
        print("❓ Do you want to unblock these trades?")
        print(f"   This will remove them from cache so the scanner can pick them up again.\n")
        
        response = input("👉 Unblock trades? (Y/N): ").strip().upper()
        
        if response != 'Y':
            print("\n❌ No changes made. Exiting...")
            return
        
        # Clear monitoring cache
        if self.monitoring_blocked:
            self._clear_from_monitoring_cache()
        
        # Clear processed signals
        if self.processed_blocked:
            self._clear_from_processed_signals()
        
        print("\n✅ Cache cleared successfully!")
        print("\n💡 Next steps:")
        print("   1. Verify setups are still valid on charts")
        print("   2. Re-run scanner: python3 daily_scanner.py")
        print("   3. OR restart monitor: setup_executor_monitor.py will auto-scan")
    
    def _clear_from_monitoring_cache(self):
        """Remove symbols from monitoring_setups.json"""
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            
            if isinstance(cache_data, dict) and 'setups' in cache_data:
                original_count = len(cache_data['setups'])
                cache_data['setups'] = [
                    s for s in cache_data['setups']
                    if s.get('symbol') not in self.target_symbols
                ]
                removed = original_count - len(cache_data['setups'])
            elif isinstance(cache_data, list):
                original_count = len(cache_data)
                cache_data = [
                    s for s in cache_data
                    if s.get('symbol') not in self.target_symbols
                ]
                removed = original_count - len(cache_data)
            else:
                print("⚠️  Unknown cache format")
                return
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            print(f"✅ Removed {removed} setups from {self.cache_file}")
            
        except Exception as e:
            print(f"❌ Error clearing monitoring cache: {e}")
    
    def _clear_from_processed_signals(self):
        """Remove symbols from processed_signals.txt"""
        try:
            with open(self.processed_signals_file, 'r') as f:
                signals = [line.strip() for line in f if line.strip()]
            
            original_count = len(signals)
            
            # Remove signals containing our target symbols
            filtered_signals = [
                sig for sig in signals
                if not any(symbol in sig for symbol in self.target_symbols)
            ]
            
            removed = original_count - len(filtered_signals)
            
            with open(self.processed_signals_file, 'w') as f:
                for sig in filtered_signals:
                    f.write(sig + '\n')
            
            print(f"✅ Removed {removed} signals from {self.processed_signals_file}")
            
        except Exception as e:
            print(f"❌ Error clearing processed signals: {e}")
    
    def run(self):
        """Run full recovery process"""
        self.scan_logs_for_trades()
        self.display_trade_details()
        self.clear_cache_interactive()


def main():
    parser = argparse.ArgumentParser(
        description='Recover specific rejected trades (GBPNZD, USDCHF)'
    )
    parser.add_argument(
        '--symbols',
        nargs='+',
        default=['GBPNZD', 'USDCHF'],
        help='Symbols to recover (default: GBPNZD USDCHF)'
    )
    parser.add_argument(
        '--date',
        help='Target date (YYYY-MM-DD, default: today)'
    )
    
    args = parser.parse_args()
    
    recovery = SpecificTradeRecovery(
        symbols=args.symbols,
        target_date=args.date
    )
    recovery.run()


if __name__ == "__main__":
    main()
