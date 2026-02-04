#!/usr/bin/env python3
"""
Trimite raport morning scan UPGRADED pe Telegram cu CHARTURI
"""
import os
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
import json
from pathlib import Path
from telegram_notifier import TelegramNotifier
from chart_generator import ChartGenerator
import pandas as pd

load_dotenv()

token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

# Initialize notifier and chart generator for sending charts
notifier = TelegramNotifier()
chart_gen = ChartGenerator()

# Load monitoring_setups.json pentru setups actuale
setups_file = Path('monitoring_setups.json')
active_setups = []
if setups_file.exists():
    try:
        with open(setups_file, 'r') as f:
            data = json.load(f)
            # Handle both formats: list [] or dict {"setups": []}
            if isinstance(data, list):
                active_setups = data
            elif isinstance(data, dict) and 'setups' in data:
                active_setups = data['setups']
    except Exception as e:
        print(f"⚠️ Failed to load setups: {e}")
        pass

# Load economic calendar pentru news conflicts
calendar_file = Path('economic_calendar.json')
upcoming_news = []
try:
    if calendar_file.exists():
        with open(calendar_file, 'r') as f:
            cal_data = json.load(f)
            # Get events pentru astăzi
            today = datetime.now()
            month_key = f"custom_events_{today.strftime('%B').lower()}_{today.year}"
            if month_key in cal_data:
                upcoming_news = [
                    e for e in cal_data[month_key]
                    if datetime.fromisoformat(e['date']).date() == today.date()
                ][:3]  # Only first 3
except:
    pass

# Count setups by type
bullish_setups = [s for s in active_setups if s.get('direction') == 'buy']
bearish_setups = [s for s in active_setups if s.get('direction') == 'sell']
total_setups = len(active_setups)

# Market sentiment
if len(bullish_setups) > len(bearish_setups) * 1.5:
    market_bias = "🟢 BULLISH BIAS"
    bias_emoji = "📈"
elif len(bearish_setups) > len(bullish_setups) * 1.5:
    market_bias = "🔴 BEARISH BIAS"
    bias_emoji = "📉"
else:
    market_bias = "🟡 NEUTRAL/MIXED"
    bias_emoji = "⚖️"

# Calculate time to market open (if weekend)
now = datetime.now()
if now.weekday() >= 5:  # Weekend
    days_to_monday = (7 - now.weekday()) % 7
    market_open = now + timedelta(days=days_to_monday)
    market_open = market_open.replace(hour=0, minute=0, second=0)
    time_to_open = market_open - now
    hours_to_open = int(time_to_open.total_seconds() / 3600)
    countdown = f"⏰ Market opens in: {hours_to_open}h"
else:
    countdown = "✅ Market is OPEN"

message = f"""
🌅 <b>MORNING SCAN REPORT</b> 🌅
⏰ {datetime.now().strftime('%A, %d %B %Y - %H:%M')}

━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>MARKET OVERVIEW</b>
━━━━━━━━━━━━━━━━━━━━━━━━

{bias_emoji} <b>Market Bias:</b> {market_bias}
{countdown}

🎯 <b>ACTIVE SETUPS:</b> {total_setups}
"""

if total_setups > 0:
    message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━
📈 <b>BULLISH SETUPS:</b> {len(bullish_setups)}
"""
    for setup in bullish_setups[:5]:  # Max 5
        symbol = setup.get('symbol', 'N/A')
        entry = setup.get('entry_price', 0)
        priority = setup.get('priority', 'MEDIUM')
        
        priority_emoji = "🔥" if priority == 'HIGH' else "⭐" if priority == 'MEDIUM' else "✨"
        
        message += f"\n{priority_emoji} <b>{symbol}</b> @ {entry:.5f}"
    
    message += f"""

━━━━━━━━━━━━━━━━━━━━━━━━
📉 <b>BEARISH SETUPS:</b> {len(bearish_setups)}
"""
    for setup in bearish_setups[:5]:  # Max 5
        symbol = setup.get('symbol', 'N/A')
        entry = setup.get('entry_price', 0)
        priority = setup.get('priority', 'MEDIUM')
        
        priority_emoji = "🔥" if priority == 'HIGH' else "⭐" if priority == 'MEDIUM' else "✨"
        
        message += f"\n{priority_emoji} <b>{symbol}</b> @ {entry:.5f}"
else:
    message += """
━━━━━━━━━━━━━━━━━━━━━━━━
⚪ <b>NO ACTIVE SETUPS</b>
━━━━━━━━━━━━━━━━━━━━━━━━

🔍 Scanner in standby mode
✅ Waiting for valid SMC structure
📊 Monitoring all major pairs
"""

# News conflicts section
if upcoming_news:
    message += f"""

━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>NEWS ALERTS TODAY:</b>
━━━━━━━━━━━━━━━━━━━━━━━━
"""
    for news in upcoming_news:
        time_str = datetime.fromisoformat(news['date']).strftime('%H:%M')
        curr = news.get('currency', 'N/A')
        event = news.get('event', 'N/A')
        message += f"\n🔴 {time_str} - {curr} {event}"
    
    message += "\n\n⚠️ Avoid trading 30min before/during news"

# Recommendations
message += f"""

━━━━━━━━━━━━━━━━━━━━━━━━
💡 <b>RECOMMENDATIONS:</b>
━━━━━━━━━━━━━━━━━━━━━━━━
"""

if total_setups > 0:
    message += """
✅ Review each setup on TradingView
✅ Set price alerts at entry levels
✅ Prepare risk management (SL/TP)
✅ Wait for final confirmations
"""
else:
    message += """
✅ Patience - wait for quality setups
✅ Monitor 4H timeframe for structure
✅ System will alert when setup detected
✅ Focus on high-probability trades only
"""

if upcoming_news:
    message += "\n⚠️ Be cautious around news times"

message += """

━━━━━━━━━━━━━━━━━━━━━━━━
<i>📅 Next scan: Tomorrow at 09:00</i>
"""

# Use TelegramNotifier for automatic branding signature
success = notifier.send_message(message.strip(), parse_mode="HTML")

if success:
    print("✅ Enhanced morning scan report sent to Telegram!")
    
    # NOW SEND CHARTS FOR EACH SETUP FOUND
    if total_setups > 0:
        print(f"\n📊 Sending charts for {total_setups} setups...")
        
        # Import data_fetcher to get real OHLC data
        try:
            from data_fetcher import DataFetcher
            fetcher = DataFetcher()
            
            for idx, setup in enumerate(active_setups[:5], 1):  # Max 5 setups to avoid spam
                symbol = setup.get('symbol')
                if not symbol:
                    continue
                    
                print(f"\n📈 [{idx}/{min(total_setups, 5)}] Generating charts for {symbol}...")
                
                try:
                    # Fetch real data for this pair
                    df_daily = fetcher.fetch_ohlc(symbol, 'D', limit=100)
                    df_4h = fetcher.fetch_ohlc(symbol, '4h', limit=200)
                    df_1h = fetcher.fetch_ohlc(symbol, '1h', limit=300)
                    
                    # Recreate TradeSetup object from JSON data
                    from smc_detector import TradeSetup, CHoCH, FVG, SwingPoint
                    
                    # Mock objects from JSON data
                    swing = SwingPoint(
                        index=0,
                        price=0.0,
                        swing_type='high',
                        candle_time=datetime.now()
                    )
                    
                    daily_choch = CHoCH(
                        index=setup.get('choch_index', 0),
                        direction=setup.get('direction', 'bullish'),
                        break_price=setup.get('choch_break_price', 0.0),
                        previous_trend='bullish' if setup.get('direction') == 'bearish' else 'bearish',
                        candle_time=datetime.now(),
                        swing_broken=swing
                    )
                    
                    fvg_data = setup.get('fvg', {})
                    fvg = FVG(
                        index=0,
                        direction=setup.get('direction', 'bullish'),
                        top=fvg_data.get('top', 0.0),
                        bottom=fvg_data.get('bottom', 0.0),
                        middle=(fvg_data.get('top', 0.0) + fvg_data.get('bottom', 0.0)) / 2,
                        candle_time=datetime.now(),
                        is_filled=False,
                        associated_choch=daily_choch
                    )
                    
                    h4_choch = CHoCH(
                        index=0,
                        direction=setup.get('direction', 'bullish'),
                        break_price=setup.get('h4_choch_price', 0.0),
                        previous_trend='bullish' if setup.get('direction') == 'bearish' else 'bearish',
                        candle_time=datetime.now(),
                        swing_broken=swing
                    ) if setup.get('h4_choch') else None
                    
                    trade_setup = TradeSetup(
                        symbol=symbol,
                        daily_choch=daily_choch,
                        fvg=fvg,
                        h4_choch=h4_choch,
                        h1_choch=None,
                        entry_price=setup.get('entry_price', 0.0),
                        stop_loss=setup.get('stop_loss', 0.0),
                        take_profit=setup.get('take_profit', 0.0),
                        risk_reward=setup.get('risk_reward', 0.0),
                        setup_time=datetime.now(),
                        priority=setup.get('priority', 'MEDIUM'),
                        strategy_type=setup.get('strategy_type', 'reversal'),
                        status=setup.get('status', 'MONITORING')
                    )
                    
                    # Generate and send Daily chart
                    print(f"   📊 Generating Daily chart...")
                    daily_chart = chart_gen.create_daily_chart(trade_setup, df_daily)
                    if daily_chart:
                        notifier.send_photo(daily_chart, f"📊 {symbol} - Daily Chart")
                        print(f"   ✅ Daily chart sent")
                    
                    # Generate and send 4H chart
                    print(f"   📊 Generating 4H chart...")
                    h4_chart = chart_gen.create_4h_chart(trade_setup, df_4h)
                    if h4_chart:
                        notifier.send_photo(h4_chart, f"📊 {symbol} - 4H Chart")
                        print(f"   ✅ 4H chart sent")
                    
                    # Generate and send 1H chart
                    print(f"   📊 Generating 1H chart...")
                    h1_chart = chart_gen.create_1h_chart(trade_setup, df_1h)
                    if h1_chart:
                        notifier.send_photo(h1_chart, f"📊 {symbol} - 1H Chart")
                        print(f"   ✅ 1H chart sent")
                    
                    print(f"   ✅ All charts sent for {symbol}")
                    
                except Exception as e:
                    print(f"   ❌ Failed to generate charts for {symbol}: {e}")
                    continue
        
        except ImportError:
            print("⚠️ DataFetcher not available - skipping charts")
        
        print(f"\n✅ Morning scan complete with {total_setups} setups and charts!")
    else:
        print("ℹ️ No active setups - no charts to send")
else:
    print(f"❌ Error: {response.status_code} - {response.text}")
