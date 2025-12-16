#!/usr/bin/env python3
"""Test if BTCUSD setup is still valid"""

from ctrader_data_client import get_ctrader_client
from smc_detector import SMCDetector

client = get_ctrader_client()
df_daily = client.get_historical_data('BTCUSD', 'D1', 200)
df_4h = client.get_historical_data('BTCUSD', 'H4', 200)

detector = SMCDetector()
setup = detector.scan_for_setup('BTCUSD', df_daily, df_4h, priority=1)

current_price = df_daily['close'].iloc[-1]
print(f'\n💡 Current BTCUSD price: ${current_price:,.2f}')

if setup:
    print(f'\n✅ Setup VALID și ACCEPTAT!')
    print(f'   Direction: {setup.daily_choch.direction.upper()} (SHORT)')
    print(f'   Entry: ${setup.entry_price:,.2f}')
    print(f'   SL: ${setup.stop_loss:,.2f}')
    print(f'   TP: ${setup.take_profit:,.2f}')
    print(f'   R:R: 1:{setup.risk_reward:.2f}')
    print(f'\n📊 Status check:')
    print(f'   Current vs Entry: ${current_price:,.2f} vs ${setup.entry_price:,.2f}')
    sl_broken = current_price > setup.stop_loss
    print(f'   SL broken? {"❌ YES - INVALIDATED!" if sl_broken else "✅ NO (still valid!)"}')
    print(f'   Distance to TP: ${abs(current_price - setup.take_profit):,.2f}')
    
    if setup.risk_reward >= 5.0:
        print(f'\n🚀 R:R >= 5.0 - READY FOR AUTO-EXECUTION!')
    else:
        print(f'\n⏳ R:R {setup.risk_reward:.2f} < 5.0 - Needs manual review or priority change')
else:
    print(f'\n❌ Setup REJECTED')
    print(f'   Possible reasons:')
    print(f'   - SL already hit')
    print(f'   - Too close to TP (< 20% remaining)')
    print(f'   - R:R < 2.0')
    print(f'\n   Current price: ${current_price:,.2f}')
