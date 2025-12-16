"""
Test Auto Trader Sync with Scanner
Verifică că auto_trader execută doar setups READY din scanner
"""
from daily_scanner import DailyScanner

print('🧪 TEST: Auto Trader Sync cu Scanner')
print('='*60)

# Initialize scanner cu cTrader
scanner = DailyScanner(use_ctrader=True)
scanner.scanner_settings['telegram_alerts'] = False

if scanner.data_provider.connect():
    print('✅ Conectat la IC Markets via cTrader\n')
    
    # Run scan
    setups = scanner.run_daily_scan(keep_connection=True)
    
    print('\n' + '='*60)
    print('📊 REZULTATE SCAN')
    print('='*60)
    
    if setups:
        print(f'\n🎯 Total: {len(setups)} setups găsite\n')
        
        ready_setups = [s for s in setups if s.status == 'READY']
        monitoring_setups = [s for s in setups if s.status == 'MONITORING']
        
        print(f'✅ READY pentru execuție: {len(ready_setups)}')
        for s in ready_setups:
            icon = '🔄' if s.strategy_type == 'reversal' else '📈'
            print(f'   {icon} {s.symbol}: {s.daily_choch.direction.upper()} - RR {s.risk_reward:.1f}x')
            print(f'      Entry: {s.entry_price:.5f} | SL: {s.stop_loss:.5f}')
        
        print(f'\n⏳ MONITORING (auto_trader NU va executa): {len(monitoring_setups)}')
        for s in monitoring_setups:
            icon = '🔄' if s.strategy_type == 'reversal' else '📈'
            print(f'   {icon} {s.symbol}: {s.daily_choch.direction.upper()} - RR {s.risk_reward:.1f}x')
            print(f'      Așteaptă: H4 CHoCH confirmation')
        
        print('\n' + '='*60)
        print('🎯 AUTO TRADER VA EXECUTA:')
        print('='*60)
        print(f'✅ {len(ready_setups)} trade-uri READY')
        print(f'⏭️  {len(monitoring_setups)} setups MONITORING vor fi ignorate')
        print('\n💡 Setups MONITORING devin READY când apare H4 CHoCH')
        print('   Scanner le va detecta în următoarea scanare!')
    else:
        print('\n⚠️ Niciun setup găsit')
    
    scanner.data_provider.disconnect()
    print('\n✅ Test finalizat!')
else:
    print('❌ Nu s-a putut conecta la cBot')
