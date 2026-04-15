#!/usr/bin/env python3
"""
🔍 REJECTED TRADES RECOVERY TOOL
Recover and re-enable trades rejected due to "Max positions reached" bug

Usage:
    python3 recover_rejected_trades.py
    python3 recover_rejected_trades.py --log setup_monitor.log
    python3 recover_rejected_trades.py --date 2026-02-26
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import argparse

class RejectedTradeRecovery:
    def __init__(self, log_file: str = "setup_monitor.log", target_date: Optional[str] = None):
        self.log_file = Path(log_file)
        self.cache_file = Path("monitoring_setups.json")
        self.processed_signals_file = Path("processed_signals.txt")
        self.target_date = target_date or datetime.now().strftime("%Y-%m-%d")
        
        self.rejected_trades: List[Dict] = []
        
    def parse_logs(self):
        """Parse log file for rejected trades"""
        print(f"\n🔍 Scanning {self.log_file} for rejected trades on {self.target_date}...")
        
        if not self.log_file.exists():
            print(f"❌ Log file not found: {self.log_file}")
            return
        
        # Patterns to match rejection messages
        patterns = [
            # Pattern 1: Setup Executor Monitor format
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}).*?⛔\s+TRADE REJECTED:\s+(\w+).*?reason[\'"]:\s*[\'"]([^\'\"]+)',
            # Pattern 2: Direct rejection format
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}).*?REJECTED.*?Symbol:\s*(\w+).*?Direction:\s*(\w+).*?Reason:\s*([^\n]+)',
            # Pattern 3: Risk Manager format
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}).*?Max positions reached.*?\((\d+)/(\d+)\)',
        ]
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Check if line is from target date
                if self.target_date not in line:
                    continue
                
                # Check for rejection keywords
                if 'REJECTED' in line or 'Max positions reached' in line:
                    # Extract timestamp
                    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
                    if not timestamp_match:
                        continue
                    
                    timestamp = timestamp_match.group(1)
                    
                    # Try to extract symbol and direction
                    symbol = None
                    direction = None
                    reason = "Unknown"
                    
                    # Look for symbol patterns
                    symbol_match = re.search(r'(?:Symbol:\s*|TRADE REJECTED:\s*)([A-Z]{6,})', line)
                    if symbol_match:
                        symbol = symbol_match.group(1)
                    
                    # Look for direction
                    direction_match = re.search(r'(?:Direction:\s*|direction[\'"]:\s*[\'"])(\w+)', line, re.IGNORECASE)
                    if direction_match:
                        direction = direction_match.group(1).upper()
                    
                    # Extract reason
                    if 'Max positions reached' in line:
                        count_match = re.search(r'(\d+)/(\d+)', line)
                        if count_match:
                            reason = f"Max positions reached ({count_match.group(1)}/{count_match.group(2)})"
                        else:
                            reason = "Max positions reached"
                    elif 'Kill switch' in line:
                        reason = "Kill switch active"
                    elif 'Daily loss' in line:
                        reason = "Daily loss limit reached"
                    else:
                        reason_match = re.search(r'Reason:\s*([^\n]+)', line)
                        if reason_match:
                            reason = reason_match.group(1).strip()
                    
                    if symbol:
                        self.rejected_trades.append({
                            'timestamp': timestamp,
                            'symbol': symbol,
                            'direction': direction or 'UNKNOWN',
                            'reason': reason,
                            'raw_line': line.strip()
                        })
        
        print(f"✅ Found {len(self.rejected_trades)} rejected trades")
    
    def check_cache_status(self):
        """Check if rejected trades are in cache"""
        print(f"\n🔍 Checking cache status in {self.cache_file}...")
        
        # Check monitoring_setups.json
        cached_symbols = set()
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                if isinstance(cache_data, dict) and 'setups' in cache_data:
                    for setup in cache_data['setups']:
                        cached_symbols.add(setup.get('symbol', ''))
                elif isinstance(cache_data, list):
                    for setup in cache_data:
                        cached_symbols.add(setup.get('symbol', ''))
            
            except Exception as e:
                print(f"⚠️  Error reading cache: {e}")
        
        # Check processed_signals.txt
        processed_signals = set()
        if self.processed_signals_file.exists():
            try:
                with open(self.processed_signals_file, 'r', encoding='utf-8') as f:
                    processed_signals = set(line.strip() for line in f if line.strip())
            except Exception as e:
                print(f"⚠️  Error reading processed signals: {e}")
        
        # Mark trades with cache status
        for trade in self.rejected_trades:
            trade['in_cache'] = trade['symbol'] in cached_symbols
            trade['in_processed'] = any(trade['symbol'] in sig for sig in processed_signals)
    
    def display_report(self):
        """Display rejected trades report"""
        if not self.rejected_trades:
            print("\n✅ No rejected trades found for today!")
            return
        
        print(f"\n{'='*90}")
        print(f"📊 REJECTED TRADES REPORT - {self.target_date}")
        print(f"{'='*90}")
        print(f"{'🕒 TIME':<12} | {'💱 PAIR':<8} | {'↕️ DIR':<6} | {'❌ REASON':<35} | {'💾 CACHE?':<8}")
        print(f"{'-'*90}")
        
        for trade in self.rejected_trades:
            time = trade['timestamp'].split()[1] if ' ' in trade['timestamp'] else trade['timestamp']
            symbol = trade['symbol']
            direction = trade['direction']
            reason = trade['reason'][:35]  # Truncate long reasons
            in_cache = '✅ YES' if trade['in_cache'] else '❌ NO'
            
            print(f"{time:<12} | {symbol:<8} | {direction:<6} | {reason:<35} | {in_cache:<8}")
        
        print(f"{'='*90}")
        print(f"\n📈 Total rejected: {len(self.rejected_trades)}")
        print(f"💾 In monitoring cache: {sum(1 for t in self.rejected_trades if t['in_cache'])}")
        print(f"🔒 In processed signals: {sum(1 for t in self.rejected_trades if t['in_processed'])}")
    
    def clear_cache_interactive(self):
        """Ask user if they want to clear cache for rejected trades"""
        if not self.rejected_trades:
            return
        
        print(f"\n{'='*90}")
        print("🔄 RECOVERY OPTIONS")
        print(f"{'='*90}")
        
        cached_trades = [t for t in self.rejected_trades if t['in_cache']]
        processed_trades = [t for t in self.rejected_trades if t['in_processed']]
        
        if cached_trades:
            print(f"\n📋 {len(cached_trades)} trades found in monitoring cache:")
            for trade in cached_trades:
                print(f"   • {trade['symbol']} {trade['direction']}")
        
        if processed_trades:
            print(f"\n📋 {len(processed_trades)} signals found in processed cache:")
            for trade in processed_trades:
                print(f"   • {trade['symbol']} {trade['direction']}")
        
        if not cached_trades and not processed_trades:
            print("\n✅ No trades found in cache - they can be re-scanned immediately!")
            return
        
        print("\n❓ What do you want to do?")
        print("   1. Clear from monitoring cache only")
        print("   2. Clear from processed signals only")
        print("   3. Clear from BOTH caches (full recovery)")
        print("   4. Do nothing (exit)")
        
        choice = input("\n👉 Enter choice (1-4): ").strip()
        
        if choice == '1':
            self._clear_monitoring_cache(cached_trades)
        elif choice == '2':
            self._clear_processed_signals(processed_trades)
        elif choice == '3':
            self._clear_monitoring_cache(cached_trades)
            self._clear_processed_signals(processed_trades)
        else:
            print("\n❌ No changes made. Exiting...")
    
    def _clear_monitoring_cache(self, trades):
        """Remove trades from monitoring_setups.json"""
        if not self.cache_file.exists():
            print(f"⚠️  Cache file not found: {self.cache_file}")
            return
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            symbols_to_remove = {t['symbol'] for t in trades}
            
            if isinstance(cache_data, dict) and 'setups' in cache_data:
                original_count = len(cache_data['setups'])
                cache_data['setups'] = [
                    s for s in cache_data['setups'] 
                    if s.get('symbol') not in symbols_to_remove
                ]
                removed = original_count - len(cache_data['setups'])
            elif isinstance(cache_data, list):
                original_count = len(cache_data)
                cache_data = [
                    s for s in cache_data 
                    if s.get('symbol') not in symbols_to_remove
                ]
                removed = original_count - len(cache_data)
            else:
                print("⚠️  Unknown cache format")
                return
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            
            print(f"\n✅ Removed {removed} setups from monitoring cache")
            
        except Exception as e:
            print(f"❌ Error clearing monitoring cache: {e}")
    
    def _clear_processed_signals(self, trades):
        """Remove trades from processed_signals.txt"""
        if not self.processed_signals_file.exists():
            print(f"⚠️  Processed signals file not found: {self.processed_signals_file}")
            return
        
        try:
            with open(self.processed_signals_file, 'r', encoding='utf-8') as f:
                signals = [line.strip() for line in f if line.strip()]
            
            symbols_to_remove = {t['symbol'] for t in trades}
            original_count = len(signals)
            
            # Remove signals containing the rejected symbols
            filtered_signals = [
                sig for sig in signals 
                if not any(symbol in sig for symbol in symbols_to_remove)
            ]
            
            removed = original_count - len(filtered_signals)
            
            with open(self.processed_signals_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(filtered_signals))
                if filtered_signals:
                    f.write('\n')
            
            print(f"✅ Removed {removed} signals from processed cache")
            
        except Exception as e:
            print(f"❌ Error clearing processed signals: {e}")
    
    def run(self):
        """Run full recovery process"""
        print("\n" + "="*90)
        print("🔄 REJECTED TRADES RECOVERY TOOL")
        print("="*90)
        
        self.parse_logs()
        self.check_cache_status()
        self.display_report()
        self.clear_cache_interactive()
        
        print("\n✨ Recovery complete!")
        print("\n💡 TIP: Now you can re-run the scanner to pick up these setups again:")
        print("   python3 daily_scanner.py")
        print("   OR")
        print("   Restart setup_executor_monitor.py (it will auto-scan)")

def main():
    parser = argparse.ArgumentParser(
        description='Recover rejected trades due to Max positions bug'
    )
    parser.add_argument(
        '--log',
        default='setup_monitor.log',
        help='Log file to scan (default: setup_monitor.log)'
    )
    parser.add_argument(
        '--date',
        help='Target date (YYYY-MM-DD, default: today)'
    )
    
    args = parser.parse_args()
    
    recovery = RejectedTradeRecovery(
        log_file=args.log,
        target_date=args.date
    )
    recovery.run()

if __name__ == "__main__":
    main()
