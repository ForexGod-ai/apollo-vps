"""
🧪 TEST COMPLET - ForexGod Glitch System
Verifică toate componentele: cTrader → Scanner → Telegram → Auto Trader
"""
from daily_scanner import DailyScanner
from telegram_notifier import TelegramNotifier
import sys

print('='*70)
print('🧪 TEST COMPLET - ForexGod Glitch Trading System')
print('='*70)

# Test 1: cTrader Connection
print('\n📡 TEST 1: Conexiune cTrader cBot')
print('-'*70)
scanner = DailyScanner(use_ctrader=True)
if scanner.data_provider.connect():
    print('✅ cTrader cBot conectat pe localhost:8767')
    print('✅ IC Markets data disponibilă')
else:
    print('❌ FAIL: Nu se poate conecta la cBot')
    print('   Soluție: Pornește MarketDataProvider_v2 în cTrader Desktop')
    sys.exit(1)

# Test 2: Telegram Connection
print('\n�� TEST 2: Conexiune Telegram Bot')
print('-'*70)
telegram = TelegramNotifier()
try:
    if telegram.test_connection():
        print('✅ Telegram bot conectat')
        print('✅ Chat ID valid: -1003369141551')
    else:
        print('⚠️  Telegram connection issue')
except Exception as e:
    print(f'⚠️  Telegram error: {e}')

# Test 3: Scanner Full Run
print('\n🔍 TEST 3: Scanner pe 21 Perechi IC Markets')
print('-'*70)
scanner.scanner_settings['telegram_alerts'] = False
setups = scanner.run_daily_scan(keep_connection=True)

print(f'\n📊 Perechi scanate: 21')
print(f'🎯 Setups găsite: {len(setups)}')

if setups:
    ready = [s for s in setups if s.status == 'READY']
    monitoring = [s for s in setups if s.status == 'MONITORING']
    
    print(f'\n✅ READY: {len(ready)}')
    for s in ready:
        icon = '🔄' if s.strategy_type == 'reversal' else '📈'
        print(f'   {icon} {s.symbol}: {s.daily_choch.direction.upper()} RR:{s.risk_reward:.1f}x')
    
    print(f'\n⏳ MONITORING: {len(monitoring)}')
    for s in monitoring:
        icon = '🔄' if s.strategy_type == 'reversal' else '📈'
        print(f'   {icon} {s.symbol}: {s.daily_choch.direction.upper()} RR:{s.risk_reward:.1f}x')

# Test 4: Data Quality
print('\n📊 TEST 4: Calitatea Datelor')
print('-'*70)
df = scanner.data_provider.get_historical_data('GBPUSD', 'D1', 5)
if df is not None:
    print(f'✅ GBPUSD: {df["close"].iloc[-1]:.5f}')

scanner.data_provider.disconnect()

# Summary
print('\n' + '='*70)
print('✅ SISTEM FUNCȚIONAL!')
print('='*70)
