#!/usr/bin/env python3
"""
Retrimite charturile pentru toate setups-urile ACTIVE din monitoring
"""
import json
from pathlib import Path
from telegram_notifier import TelegramNotifier
from ctrader_cbot_client import CTraderCBotClient
from smc_detector import TradeSetup, CHoCH, FVG, SwingPoint
from datetime import datetime
import pandas as pd

print("📊 RESENDING ACTIVE SETUPS WITH CHARTS\n")

# Load monitoring setups
setups_file = Path('monitoring_setups.json')
if not setups_file.exists():
    print("❌ No monitoring_setups.json found")
    exit(1)

with open(setups_file, 'r', encoding='utf-8') as f:
    data = json.load(f)
    active_setups = data.get('setups', []) if isinstance(data, dict) else data

if not active_setups:
    print("ℹ️ No active setups to resend")
    exit(0)

print(f"✅ Found {len(active_setups)} active setups\n")

notifier = TelegramNotifier()
ctrader = CTraderCBotClient()

for idx, setup_data in enumerate(active_setups, 1):
    symbol = setup_data.get('symbol')
    if not symbol:
        continue
    
    print(f"\n{'='*60}")
    print(f"[{idx}/{len(active_setups)}] {symbol} - {setup_data.get('direction', '').upper()}")
    print(f"{'='*60}")
    
    try:
        # Fetch real data from cTrader
        print(f"📡 Fetching data for {symbol}...")
        df_daily = ctrader.get_historical_data(symbol, 'Daily', bars=100)
        df_4h = ctrader.get_historical_data(symbol, 'Hour4', bars=200)
        df_1h = ctrader.get_historical_data(symbol, 'Hour', bars=300)
        
        # Recreate TradeSetup object
        swing = SwingPoint(
            index=0,
            price=0.0,
            swing_type='high',
            candle_time=datetime.now()
        )
        
        daily_choch = CHoCH(
            index=0,
            direction=setup_data.get('direction', 'bullish'),
            break_price=setup_data.get('entry_price', 0.0),
            previous_trend='bullish' if setup_data.get('direction') == 'bearish' else 'bearish',
            candle_time=datetime.now(),
            swing_broken=swing
        )
        
        fvg = FVG(
            index=0,
            direction=setup_data.get('direction', 'bullish'),
            top=setup_data.get('fvg_zone_top', 0.0),
            bottom=setup_data.get('fvg_zone_bottom', 0.0),
            middle=(setup_data.get('fvg_zone_top', 0.0) + setup_data.get('fvg_zone_bottom', 0.0)) / 2,
            candle_time=datetime.now(),
            is_filled=False,
            associated_choch=daily_choch
        )
        
        h4_choch = None  # Will be set if exists
        
        trade_setup = TradeSetup(
            symbol=symbol,
            daily_choch=daily_choch,
            fvg=fvg,
            h4_choch=h4_choch,
            h1_choch=None,
            entry_price=setup_data.get('entry_price', 0.0),
            stop_loss=setup_data.get('stop_loss', 0.0),
            take_profit=setup_data.get('take_profit', 0.0),
            risk_reward=setup_data.get('risk_reward', 0.0),
            setup_time=datetime.now(),
            priority=setup_data.get('priority', 'MEDIUM'),
            strategy_type=setup_data.get('strategy_type', 'reversal'),
            status=setup_data.get('status', 'MONITORING')
        )
        
        # Add current price for live distance calculation
        if len(df_1h) > 0:
            trade_setup.current_price = df_1h['close'].iloc[-1]
        
        # Send setup alert with charts
        print(f"📱 Sending {symbol} setup to Telegram...")
        success = notifier.send_setup_alert(trade_setup, df_daily, df_4h, df_1h)
        
        if success:
            print(f"✅ {symbol} sent successfully with 3 charts!")
        else:
            print(f"⚠️ {symbol} - partial success or errors")
            
    except Exception as e:
        print(f"❌ Failed to process {symbol}: {e}")
        continue

print(f"\n{'='*60}")
print(f"✅ Finished resending {len(active_setups)} setups!")
print(f"{'='*60}\n")
