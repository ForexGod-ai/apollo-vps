"""
Test Auto Trader - Verifică dacă folosește datele corecte
"""
from auto_trader import AutoTrader
import json

print('🔍 Test Auto Trader Configuration')
print('='*60)

# Check config
with open('trading_config.json', 'r') as f:
    config = json.load(f)

print('\n📋 Trading Config:')
print(f'   Auto Trading: {config["auto_trading"]["enabled"]}')
print(f'   Max Trades/Day: {config["position_limits"]["max_trades_per_day"]}')
print(f'   Risk per Trade: {config["risk_management"]["risk_per_trade_percent"]}%')

# Initialize trader
print('\n🤖 Initializing Auto Trader...')
try:
    trader = AutoTrader()
    
    print(f'\n✅ Auto Trader initialized')
    print(f'   Scanner type: {type(trader.scanner).__name__}')
    print(f'   Data provider: {type(trader.scanner.data_provider).__name__}')
    
    # Check if scanner uses cTrader
    if hasattr(trader.scanner.data_provider, 'client'):
        print(f'   ✅ Using cTrader cBot client')
        print(f'   Connection: {trader.scanner.data_provider.is_available()}')
    else:
        print(f'   ⚠️  Not using cTrader!')
    
    # Run one scan cycle
    print('\n🔄 Running one scan cycle...')
    trader.run_cycle()
    
    print('\n✅ Cycle complete!')
    print(f'   Active trades: {len(trader.active_trades)}')
    print(f'   Trades today: {trader.trades_today}')
    
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
