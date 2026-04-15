#!/usr/bin/env python3
"""
Check how STALE the monitoring setups are
Shows: age, distance from current price, if they're still valid
"""
import json
from datetime import datetime, timedelta
import sys

def check_setup_staleness():
    with open('monitoring_setups.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"🔍 SETUP STALENESS CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Total setups: {len(data['setups'])}\n")
    print("="*90)
    
    stale_count = 0
    expired_count = 0
    valid_count = 0
    
    for i, setup in enumerate(data['setups'], 1):
        symbol = setup['symbol']
        direction = setup['direction']
        entry = setup['entry_price']
        status = setup.get('status', 'MONITORING')
        setup_time_str = setup.get('setup_time', '1970-01-01T00:00:00')
        
        # Parse setup time
        try:
            if '1970-01-01' in setup_time_str:
                setup_time = datetime(1970, 1, 1)  # Corrupted timestamp
                age_hours = 999999  # Very old
                age_display = "CORRUPTED (1970)"
            else:
                setup_time = datetime.fromisoformat(setup_time_str.replace('Z', '+00:00'))
                age = datetime.now() - setup_time
                age_hours = age.total_seconds() / 3600
                age_days = age_hours / 24
                if age_days >= 1:
                    age_display = f"{age_days:.1f} days"
                else:
                    age_display = f"{age_hours:.1f} hours"
        except:
            age_hours = 999999
            age_display = "PARSE ERROR"
        
        # Categorize
        if status == 'EXPIRED':
            category = "❌ EXPIRED"
            expired_count += 1
        elif age_hours > 72:  # > 3 days
            category = "🗑️  STALE"
            stale_count += 1
        elif age_hours > 24:  # > 1 day
            category = "⚠️  OLD"
            stale_count += 1
        else:
            category = "✅ VALID"
            valid_count += 1
        
        print(f"{i}. {symbol} - {direction.upper()} @ {entry}")
        print(f"   Status: {status} | Age: {age_display}")
        print(f"   Category: {category}")
        
        if setup.get('choch_1h_detected'):
            fibo = setup.get('fibo_data', {}).get('fibo_50', 'N/A')
            print(f"   Fibo 50%: {fibo}")
        
        print("-"*90)
    
    print("\n📊 SUMMARY:")
    print(f"   ✅ Valid (< 24h): {valid_count}")
    print(f"   ⚠️  Stale (> 24h): {stale_count}")
    print(f"   ❌ Expired: {expired_count}")
    print(f"   Total: {len(data['setups'])}")
    
    if stale_count > 0 or expired_count > 0:
        print("\n🚨 RECOMMENDATION:")
        print("   Clear stale/expired setups and run fresh scanner:")
        print("   cp monitoring_setups.json monitoring_setups_backup_$(date +%Y%m%d).json")
        print("   echo '{\"setups\": []}' > monitoring_setups.json")
        print("   python3.14 daily_scanner.py")

if __name__ == '__main__':
    check_setup_staleness()
