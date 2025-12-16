"""
Auto Trading System - ForexGod Glitch
Scanează → Telegram → Scrie signals.json → PythonSignalExecutor execută
"""
from daily_scanner import DailyScanner
import json
from datetime import datetime
import time

print('🚀 ForexGod Auto Trading System')
print('='*60)

# Initialize scanner
scanner = DailyScanner(use_ctrader=True)
scanner.scanner_settings['telegram_alerts'] = True

# Signal file path (trebuie să fie același cu PythonSignalExecutor)
SIGNAL_FILE = '/Users/forexgod/Desktop/trading-ai-agent/signals.json'

def write_signal(setup):
    """Scrie setup în signals.json pentru PythonSignalExecutor"""
    
    # Calculate pips for cTrader (4/5 digit broker)
    # Forex: 0.0001 = 1 pip (EUR/USD, GBP/USD, etc.)
    # JPY pairs: 0.01 = 1 pip (USD/JPY, GBP/JPY, etc.)
    # Gold/Silver: 0.01 = 1 pip
    # BTC: 1.0 = 1 pip
    
    pip_size = 0.0001  # Default for most forex
    if 'JPY' in setup.symbol:
        pip_size = 0.01
    elif setup.symbol in ['XAUUSD', 'XAGUSD']:
        pip_size = 0.01
    elif setup.symbol == 'BTCUSD':
        pip_size = 1.0
    
    # Calculate SL and TP in pips
    sl_distance = abs(setup.entry_price - setup.stop_loss)
    tp_distance = abs(setup.take_profit - setup.entry_price)
    
    sl_pips = round(sl_distance / pip_size, 1)
    tp_pips = round(tp_distance / pip_size, 1)
    
    signal = {
        'SignalId': f"{setup.symbol}_{int(setup.setup_time.timestamp())}",
        'Symbol': setup.symbol,
        'Direction': 'buy' if setup.daily_choch.direction == 'bullish' else 'sell',
        'EntryPrice': setup.entry_price,
        'StopLoss': setup.stop_loss,
        'TakeProfit': setup.take_profit,
        'StopLossPips': sl_pips,
        'TakeProfitPips': tp_pips,
        'RiskReward': setup.risk_reward,
        'StrategyType': setup.strategy_type,
        'TimeGenerated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'Priority': setup.priority
    }
    
    with open(SIGNAL_FILE, 'w') as f:
        json.dump(signal, f, indent=2)
    
    print(f'✅ Signal scris pentru {setup.symbol}')
    print(f'   SL: {sl_pips} pips | TP: {tp_pips} pips')
    return True

if scanner.data_provider.connect():
    print('✅ Conectat la IC Markets')
    print('🔍 Scanez 21 perechi...\n')
    
    # Run scan
    setups = scanner.run_daily_scan(keep_connection=True)
    
    # Filter READY setups
    ready_setups = [s for s in setups if s.status == 'READY']
    
    print(f'\n📊 Scan complet: {len(setups)} setups găsite')
    print(f'✅ READY pentru execuție: {len(ready_setups)}')
    
    if ready_setups:
        print('\n📝 Scriu signals pentru PythonSignalExecutor...')
        for setup in ready_setups:
            write_signal(setup)
            print(f'   • {setup.symbol}: {setup.daily_choch.direction.upper()} RR:{setup.risk_reward:.1f}x')
            # Pauză între trade-uri pentru a nu overload cTrader
            time.sleep(2)
        
        print(f'\n✅ {len(ready_setups)} trade-uri pregătite pentru execuție!')
        print('🤖 PythonSignalExecutor le va executa automat!')
    else:
        print('\n⏳ Niciun setup READY acum')
        monitoring = [s for s in setups if s.status == 'MONITORING']
        if monitoring:
            print(f'   {len(monitoring)} setups în MONITORING (așteaptă H4 CHoCH)')
    
    scanner.data_provider.disconnect()
    print('\n🏁 Sistem automat funcțional!')
else:
    print('❌ Nu se poate conecta la cBot')
