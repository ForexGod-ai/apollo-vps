"""
Test Telegram cu Setup READY
Trimite AUDCAD setup cu ștampila ForexGod + charts
"""
from daily_scanner import DailyScanner
import pandas as pd

print('🚀 Test Telegram Alert cu Setup READY')
print('='*60)

scanner = DailyScanner(use_ctrader=True)
scanner.scanner_settings['telegram_alerts'] = True  # ACTIVAT!

if scanner.data_provider.connect():
    print('✅ Conectat la IC Markets\n')
    
    # Run scan
    setups = scanner.run_daily_scan(keep_connection=True)
    
    ready_setups = [s for s in setups if s.status == 'READY']
    
    print('\n' + '='*60)
    if ready_setups:
        print(f'✅ {len(ready_setups)} setup-uri READY trimise pe Telegram!')
        for s in ready_setups:
            print(f'   📱 {s.symbol}: {s.daily_choch.direction.upper()} RR:{s.risk_reward:.1f}x')
    else:
        print('⏳ Niciun setup READY (toate sunt în MONITORING)')
    
    print('\n📱 Verifică grupul Telegram pentru mesaje!')
    print('   Ar trebui să vezi:')
    print('   ✅ Ștampila: "ForexGod AI Trading"')
    print('   ✅ Strategy: Glitch in Matrix')
    print('   ✅ IC Markets branding')
    
    scanner.data_provider.disconnect()
else:
    print('❌ Nu se poate conecta')
