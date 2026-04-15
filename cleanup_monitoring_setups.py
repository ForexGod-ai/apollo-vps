#!/usr/bin/env python3
"""
🧹 CLEANUP MONITORING SETUPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Utilitar pentru curățarea setup-urilor corupte/incomplete din monitoring_setups.json

Caută și elimină setup-uri cu:
- entry_price = None
- stop_loss = None  
- take_profit = None
- Alte date invalide

Usage:
    python3 cleanup_monitoring_setups.py              # Dry run (preview only)
    python3 cleanup_monitoring_setups.py --execute    # Actually clean the file
"""

import json
import argparse
from datetime import datetime
from typing import List, Dict


def load_monitoring_setups() -> tuple[List[Dict], Dict]:
    """Load monitoring_setups.json
    
    Returns:
        (setups_list, metadata_dict)
    """
    try:
        with open('monitoring_setups.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            setups = data.get("setups", [])
            metadata = {k: v for k, v in data.items() if k != "setups"}
            return setups, metadata
        elif isinstance(data, list):
            return data, {}
        else:
            return [], {}
    
    except FileNotFoundError:
        print("❌ monitoring_setups.json not found")
        return [], {}
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing monitoring_setups.json: {e}")
        return [], {}


def validate_setup(setup: Dict) -> tuple[bool, str]:
    """Validate a setup for data integrity
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(setup, dict):
        return False, "Not a dictionary"
    
    # Check required fields
    required_fields = ['symbol', 'entry_price', 'stop_loss', 'take_profit']
    for field in required_fields:
        if field not in setup:
            return False, f"Missing field: {field}"
        
        value = setup[field]
        
        # Check for None values
        if value is None:
            return False, f"{field} is None"
        
        # Check for valid numeric types (except symbol)
        if field != 'symbol':
            try:
                float(value)
            except (TypeError, ValueError):
                return False, f"{field} is not numeric: {value}"
    
    # Validate direction
    direction = setup.get('direction', '').upper()
    if direction not in ['LONG', 'SHORT', 'BUY', 'SELL']:
        return False, f"Invalid direction: {direction}"
    
    # All checks passed
    return True, "OK"


def cleanup_setups(dry_run: bool = True) -> tuple[int, int, List[Dict]]:
    """Clean corrupted setups from monitoring_setups.json
    
    Args:
        dry_run: If True, only preview changes without saving
    
    Returns:
        (total_count, corrupted_count, valid_setups)
    """
    setups, metadata = load_monitoring_setups()
    
    if not setups:
        print("\n📭 No setups found in monitoring_setups.json\n")
        return 0, 0, []
    
    total_count = len(setups)
    valid_setups = []
    corrupted_setups = []
    
    print(f"\n🔍 Analyzing {total_count} setup(s)...\n")
    
    # Validate each setup
    for setup in setups:
        is_valid, error_msg = validate_setup(setup)
        
        if is_valid:
            valid_setups.append(setup)
        else:
            symbol = setup.get('symbol', 'UNKNOWN')
            corrupted_setups.append({
                'symbol': symbol,
                'error': error_msg,
                'data': setup
            })
            print(f"❌ CORRUPTED: {symbol} - {error_msg}")
    
    corrupted_count = len(corrupted_setups)
    valid_count = len(valid_setups)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"📊 CLEANUP SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Valid setups:     {valid_count}")
    print(f"❌ Corrupted setups: {corrupted_count}")
    print(f"{'='*80}\n")
    
    if corrupted_count == 0:
        print("✨ All setups are valid! No cleanup needed.\n")
        return total_count, 0, valid_setups
    
    # If not dry run, save cleaned data
    if not dry_run:
        metadata['last_updated'] = datetime.now().isoformat()
        metadata['last_cleanup'] = datetime.now().isoformat()
        metadata['setups'] = valid_setups
        
        with open('monitoring_setups.json', 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✅ Cleaned monitoring_setups.json")
        print(f"   Removed {corrupted_count} corrupted setup(s)")
        print(f"   Kept {valid_count} valid setup(s)\n")
        
        # Create backup of corrupted data
        if corrupted_setups:
            backup_file = f"monitoring_setups_corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup_file, 'w') as f:
                json.dump({
                    'corrupted_setups': corrupted_setups,
                    'timestamp': datetime.now().isoformat()
                }, f, indent=2)
            print(f"💾 Backup of corrupted setups saved to: {backup_file}\n")
    
    else:
        print("ℹ️  DRY RUN MODE - No changes made")
        print("   Run with --execute to actually clean the file\n")
    
    return total_count, corrupted_count, valid_setups


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='🧹 Cleanup corrupted setups from monitoring_setups.json'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually clean the file (default is dry run/preview only)'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("🧹 MONITORING SETUPS CLEANUP UTILITY")
    print("="*80)
    
    if args.execute:
        print("⚠️  EXECUTE MODE: Will modify monitoring_setups.json")
    else:
        print("ℹ️  DRY RUN MODE: Preview only (no changes will be made)")
    
    print("="*80)
    
    # Run cleanup
    total, corrupted, valid = cleanup_setups(dry_run=not args.execute)
    
    # Exit code
    if corrupted > 0 and not args.execute:
        print("💡 TIP: Run with --execute flag to clean the file")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
