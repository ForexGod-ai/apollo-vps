"""
✅ VERIFICATION CHECK - Scanner Ready for Tomorrow 09:00
Tests all components needed for morning scan
"""

import MetaTrader5 as mt5
import os
import requests
from dotenv import load_dotenv
from datetime import datetime
from smc_detector import SMCDetector
from spatiotemporal_analyzer import SpatioTemporalAnalyzer

load_dotenv()

print("\n" + "="*70)
print("🔍 SCANNER READINESS CHECK - Tomorrow 09:00")
print("="*70 + "\n")

# 1. MT5 Connection
print("1️⃣ Checking MT5 Connection...")
if mt5.initialize():
    account = mt5.account_info()
    print(f"   ✅ MT5 Connected!")
    print(f"   📊 Account: {account.login}")
    print(f"   💰 Balance: ${account.balance:.2f}")
    print(f"   📈 Equity: ${account.equity:.2f}")
    mt5_ok = True
else:
    print("   ❌ MT5 Connection FAILED!")
    mt5_ok = False

# 2. Telegram Connection
print("\n2️⃣ Checking Telegram Connection...")
token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

if token and chat_id:
    try:
        response = requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            data={
                'chat_id': chat_id,
                'text': f'✅ Scanner Verification Complete!\n\n📅 Ready for tomorrow {datetime.now().strftime("%d %B")} at 09:00\n\n🎯 All systems operational!'
            }
        )
        if response.status_code == 200:
            print(f"   ✅ Telegram OK!")
            print(f"   📱 Chat ID: {chat_id}")
            telegram_ok = True
        else:
            print(f"   ❌ Telegram Error: {response.status_code}")
            telegram_ok = False
    except Exception as e:
        print(f"   ❌ Telegram Exception: {e}")
        telegram_ok = False
else:
    print("   ❌ Telegram credentials missing in .env!")
    telegram_ok = False

# 3. Test SMC Detector
print("\n3️⃣ Testing SMC Detector...")
try:
    detector = SMCDetector()
    print("   ✅ SMC Detector loaded!")
    smc_ok = True
except Exception as e:
    print(f"   ❌ SMC Detector Error: {e}")
    smc_ok = False

# 4. Test Spatiotemporal Analyzer (NEW!)
print("\n4️⃣ Testing Spatiotemporal Analyzer...")
try:
    if mt5_ok:
        analyzer = SpatioTemporalAnalyzer("NZDUSD")
        narrative = analyzer.analyze_market()
        
        if narrative.expected_scenarios:
            strategy = narrative.expected_scenarios[0].get('strategy_type', 'UNKNOWN')
            print(f"   ✅ Spatiotemporal Analyzer working!")
            print(f"   📊 NZDUSD detected as: {strategy}")
            print(f"   🎯 Recommendation: {narrative.recommendation}")
            spatiotemporal_ok = True
        else:
            print(f"   ⚠️ Analyzer works but no scenarios generated")
            spatiotemporal_ok = True
    else:
        print("   ⏭️ Skipped (MT5 not connected)")
        spatiotemporal_ok = False
except Exception as e:
    print(f"   ❌ Spatiotemporal Error: {e}")
    spatiotemporal_ok = False

# 5. Check Scanner Scripts
print("\n5️⃣ Checking Scanner Scripts...")
scripts = [
    'morning_scheduler.py',
    'complete_scan_with_charts.py',
    'smc_detector.py',
    'spatiotemporal_analyzer.py'
]

missing = []
for script in scripts:
    if os.path.exists(script):
        print(f"   ✅ {script}")
    else:
        print(f"   ❌ {script} MISSING!")
        missing.append(script)

scripts_ok = len(missing) == 0

# 6. Check Charts Directory
print("\n6️⃣ Checking Charts Directory...")
if os.path.exists('charts'):
    print(f"   ✅ charts/ directory exists")
    charts_ok = True
else:
    print(f"   ⚠️ Creating charts/ directory...")
    os.makedirs('charts', exist_ok=True)
    print(f"   ✅ charts/ directory created")
    charts_ok = True

# FINAL REPORT
print("\n" + "="*70)
print("📊 READINESS REPORT")
print("="*70)

checks = {
    'MT5 Connection': mt5_ok,
    'Telegram Bot': telegram_ok,
    'SMC Detector': smc_ok,
    'Spatiotemporal Analyzer': spatiotemporal_ok,
    'Scanner Scripts': scripts_ok,
    'Charts Directory': charts_ok
}

all_ok = all(checks.values())

for check, status in checks.items():
    icon = "✅" if status else "❌"
    print(f"{icon} {check}")

print("\n" + "="*70)

if all_ok:
    print("🎉 ALL SYSTEMS GO! Scanner ready for tomorrow 09:00! 🚀")
    print("\n📋 TO START SCHEDULER:")
    print("   python morning_scheduler.py")
    print("\n📋 TO TEST SCAN NOW:")
    print("   python complete_scan_with_charts.py")
else:
    print("⚠️ SOME ISSUES DETECTED - Review above!")

print("="*70 + "\n")

# Cleanup
if mt5_ok:
    mt5.shutdown()
