"""
🎯 COMPLETE MARKET SCAN - GLITCH IN MATRIX
- Scanează toate perechile
- Generează grafice pentru fiecare setup
- Trimite pe Telegram cu Daily + 4H charts
- Detectează READY vs MONITORING setups
"""

import MetaTrader5 as mt5
import pandas as pd
import json
import os
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mplfinance as mpf
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv
from smc_detector import SMCDetector

load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Create charts folder
os.makedirs('charts', exist_ok=True)

def send_telegram_message(message: str):
    """Trimite mesaj text"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(url, data={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        })
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

def send_telegram_photo(photo_path: str, caption: str):
    """Trimite foto cu caption"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(photo_path, 'rb') as photo:
            response = requests.post(url,
                data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'},
                files={'photo': photo})
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Photo error: {e}")
        return False

def create_chart(symbol: str, timeframe, bars: int = 100):
    """Creează grafic candlestick cu zone marcate"""
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        
        tf_name = {
            mt5.TIMEFRAME_D1: 'Daily',
            mt5.TIMEFRAME_H4: '4H',
            mt5.TIMEFRAME_H1: '1H'
        }.get(timeframe, 'Unknown')
        
        filename = f"charts/{symbol}_{tf_name}_{datetime.now().strftime('%H%M%S')}.png"
        
        # Chart style
        mc = mpf.make_marketcolors(
            up='#26a69a', down='#ef5350',
            edge='inherit',
            wick={'up':'#26a69a', 'down':'#ef5350'},
            volume='in', alpha=0.9
        )
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=False)
        
        # Plot (without volume - some symbols don't have it)
        mpf.plot(df, type='candle', style=s, volume=False,
                title=f'{symbol} - {tf_name}',
                savefig=filename, figsize=(12, 8))
        
        logger.info(f"  📊 Chart created: {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Chart error {symbol}: {e}")
        return None

def analyze_pair_intelligent(symbol: str, smc: SMCDetector):
    """
    Analiză inteligentă - detectează:
    1. READY TO TRADE - toate confirmările prezente
    2. MONITORING - CHoCH + FVG dar așteptăm 4H confirmation sau price retest
    3. NO SETUP - nimic relevant
    """
    try:
        # Daily data
        rates_d1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 100)
        if rates_d1 is None or len(rates_d1) == 0:
            return None
        
        df_d1 = pd.DataFrame(rates_d1)
        df_d1['time'] = pd.to_datetime(df_d1['time'], unit='s')
        current_price = df_d1['close'].iloc[-1]
        
        # Detect Daily CHoCH
        daily_chochs = smc.detect_choch(df_d1)
        if not daily_chochs:
            return None
        
        latest_choch = daily_chochs[-1]
        
        # Detect FVG
        fvg = smc.detect_fvg(df_d1, latest_choch, current_price)
        if not fvg:
            return None
        
        # Premium/Discount
        high = df_d1['high'].max()
        low = df_d1['low'].min()
        equilibrium = (high + low) / 2
        range_size = high - low
        
        in_premium = current_price > (equilibrium + range_size * 0.05)
        in_discount = current_price < (equilibrium - range_size * 0.05)
        
        # 4H data
        rates_4h = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 200)
        if rates_4h is None:
            return None
        
        df_4h = pd.DataFrame(rates_4h)
        df_4h['time'] = pd.to_datetime(df_4h['time'], unit='s')
        
        # 4H CHoCH
        h4_chochs = smc.detect_choch(df_4h)
        h4_confirmation = False
        h4_opposite = False
        
        if h4_chochs:
            latest_4h = h4_chochs[-1]
            # Check if 4H CHoCH inside FVG zone
            if fvg.bottom <= latest_4h.break_price <= fvg.top:
                if latest_4h.direction != latest_choch.direction:
                    h4_opposite = True  # Opposite direction = contra-trend entry
                else:
                    h4_confirmation = True  # Same direction = trend continuation
        
        # Price in FVG?
        in_fvg = fvg.bottom <= current_price <= fvg.top
        
        # Distance to FVG if not inside
        if not in_fvg:
            distance_to_fvg = min(abs(current_price - fvg.bottom), abs(current_price - fvg.top))
            distance_percent = (distance_to_fvg / current_price) * 100
        else:
            distance_to_fvg = 0
            distance_percent = 0
        
        # DECISION LOGIC
        status = 'NO_SETUP'
        entry_price = None
        reason = ""
        
        # READY TO TRADE - toate confirmările
        if in_fvg and (h4_confirmation or h4_opposite):
            status = 'READY'
            entry_price = current_price
            reason = "Price in FVG + 4H confirmation ✅"
        
        # MONITORING - avem CHoCH + FVG dar așteptăm
        elif not in_fvg and distance_percent < 2.0:  # < 2% distance
            status = 'MONITORING'
            # Entry ideal = FVG bottom for LONG, FVG top for SHORT
            if latest_choch.direction == 'bullish':
                entry_price = fvg.bottom
            else:
                entry_price = fvg.top
            reason = f"Waiting for retest at ${entry_price:.5f}"
        
        elif in_fvg and not (h4_confirmation or h4_opposite):
            status = 'MONITORING'
            entry_price = current_price
            reason = "In FVG, waiting for 4H confirmation"
        
        else:
            return None  # Nu e relevant
        
        # Calculate SL & TP
        if latest_choch.direction == 'bullish':
            sl = latest_choch.break_price * 0.997
            tp = high * 1.01
        else:
            sl = latest_choch.break_price * 1.003
            tp = low * 0.99
        
        # R:R
        if entry_price:
            risk = abs(entry_price - sl)
            reward = abs(tp - entry_price)
            rr = reward / risk if risk > 0 else 0
        else:
            rr = 0
        
        return {
            'symbol': symbol,
            'status': status,
            'direction': latest_choch.direction,
            'current_price': current_price,
            'daily_choch': latest_choch,
            'fvg': fvg,
            'in_fvg': in_fvg,
            'distance_to_fvg': distance_to_fvg,
            'distance_percent': distance_percent,
            'entry_price': entry_price,
            'sl': sl,
            'tp': tp,
            'rr': rr,
            'in_premium': in_premium,
            'in_discount': in_discount,
            'h4_confirmation': h4_confirmation,
            'h4_opposite': h4_opposite,
            'reason': reason
        }
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return None

def main():
    logger.info("\n" + "="*80)
    logger.info("🎯 GLITCH IN MATRIX - COMPLETE MARKET SCAN")
    logger.info("="*80)
    
    # MT5 init
    if not mt5.initialize():
        logger.error("❌ MT5 failed")
        send_telegram_message("❌ <b>MT5 Connection Failed!</b>")
        return
    
    logger.info(f"✅ MT5 Connected: #{mt5.account_info().login}")
    
    # Check if weekend (Saturday=5, Sunday=6)
    now = datetime.now()
    is_weekend = now.weekday() in [5, 6]  # Saturday or Sunday
    
    # Load pairs - WEEKEND = only BTCUSD, WEEKDAY = all pairs
    if is_weekend:
        pairs = ['BTCUSD']
        logger.info("📅 WEEKEND MODE - Scanning only BTCUSD (FOREX markets closed)")
    else:
        try:
            with open('pairs_config.json', 'r') as f:
                config = json.load(f)
                pairs = [p['symbol'] for p in config['pairs']]
        except:
            pairs = ['GBPUSD', 'XAUUSD', 'BTCUSD', 'GBPJPY', 'EURUSD', 'GBPNZD',
                     'EURJPY', 'NZDCAD', 'NZDUSD', 'AUDNZD', 'GBPCHF', 'USDJPY']
        logger.info(f"📊 WEEKDAY MODE - Scanning {len(pairs)} pairs")
    
    logger.info(f"📊 Scanning {len(pairs)} pairs...\n")
    
    # Send start message
    day_name = now.strftime('%A')  # Monday, Tuesday, etc.
    scan_mode = "🔷 <b>WEEKEND MODE</b> - BTCUSD Only" if is_weekend else f"📊 <b>WEEKDAY MODE</b> - {len(pairs)} Pairs"
    
    send_telegram_message(f"""
🎯 <b>GLITCH IN MATRIX</b>
🔍 Complete Market Scan

{scan_mode}
⏰ Time: {now.strftime('%H:%M:%S')}
📅 {day_name}, {now.strftime('%d %B %Y')}

<i>{"Analyzing crypto markets..." if is_weekend else "Analyzing institutional footprints..."}</i>
""")
    
    smc = SMCDetector()
    
    ready_setups = []
    monitoring_setups = []
    
    for i, symbol in enumerate(pairs, 1):
        logger.info(f"[{i}/{len(pairs)}] {symbol}...")
        setup = analyze_pair_intelligent(symbol, smc)
        
        if setup:
            if setup['status'] == 'READY':
                ready_setups.append(setup)
                logger.info(f"  🔥 READY: {setup['direction'].upper()}")
            elif setup['status'] == 'MONITORING':
                monitoring_setups.append(setup)
                logger.info(f"  👀 MONITORING: {setup['direction'].upper()} - {setup['reason']}")
        else:
            logger.info(f"  ❌ No setup")
    
    # Send READY setups with charts
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 READY SETUPS: {len(ready_setups)}")
    logger.info(f"👀 MONITORING: {len(monitoring_setups)}")
    logger.info(f"{'='*80}\n")
    
    if ready_setups:
        send_telegram_message(f"\n🔥 <b>{len(ready_setups)} READY TO TRADE!</b>\n")
        
        for idx, setup in enumerate(ready_setups, 1):
            direction_emoji = "🟢" if setup['direction'] == 'bullish' else "🔴"
            direction_text = "LONG" if setup['direction'] == 'bullish' else "SHORT"
            
            msg = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>#{idx} {setup['symbol']}</b> {direction_emoji} <b>{direction_text}</b>

✅ <b>STATUS: READY TO EXECUTE</b>

💰 <b>SETUP:</b>
Entry: <b>${setup['entry_price']:.5f}</b>
Stop Loss: ${setup['sl']:.5f}
Take Profit: ${setup['tp']:.5f}
Risk/Reward: <b>1:{setup['rr']:.2f}</b>

📊 <b>ANALYSIS:</b>
• Daily CHoCH: {setup['direction'].upper()}
• FVG Zone: ${setup['fvg'].bottom:.5f} - ${setup['fvg'].top:.5f}
• Price in FVG: ✅
• {'Premium' if setup['in_premium'] else 'Discount'} Zone: ✅
• 4H Confirmation: {'✅' if setup['h4_confirmation'] or setup['h4_opposite'] else '⏳'}

<i>{setup['reason']}</i>
"""
            send_telegram_message(msg)
            
            # Daily chart
            logger.info(f"  📊 Creating charts for {setup['symbol']}...")
            chart_d1 = create_chart(setup['symbol'], mt5.TIMEFRAME_D1)
            if chart_d1:
                send_telegram_photo(chart_d1, f"{setup['symbol']} - Daily CHoCH {setup['direction'].upper()}")
            
            # 4H chart
            chart_4h = create_chart(setup['symbol'], mt5.TIMEFRAME_H4)
            if chart_4h:
                send_telegram_photo(chart_4h, f"{setup['symbol']} - 4H Confirmation")
    
    # MONITORING setups
    if monitoring_setups:
        msg = f"\n👀 <b>{len(monitoring_setups)} MONITORING SETUPS:</b>\n\n"
        
        for setup in monitoring_setups[:5]:  # Max 5
            direction_emoji = "🟢" if setup['direction'] == 'bullish' else "🔴"
            msg += f"{direction_emoji} <b>{setup['symbol']}</b> {setup['direction'].upper()}\n"
            msg += f"   Entry: ${setup['entry_price']:.5f}\n"
            msg += f"   {setup['reason']}\n\n"
        
        send_telegram_message(msg)
        
        # Send charts for top 3 monitoring
        for setup in monitoring_setups[:3]:
            logger.info(f"  📊 Chart for monitoring: {setup['symbol']}...")
            chart_d1 = create_chart(setup['symbol'], mt5.TIMEFRAME_D1, 50)
            if chart_d1:
                caption = f"{setup['symbol']} - MONITORING\n{setup['reason']}"
                send_telegram_photo(chart_d1, caption)
    
    # Summary
    summary = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>SCAN COMPLETE</b>

✅ Scanned: {len(pairs)} pairs
🔥 Ready: {len(ready_setups)}
👀 Monitoring: {len(monitoring_setups)}
⏰ {datetime.now().strftime('%H:%M:%S')}

"""
    
    if not ready_setups and not monitoring_setups:
        summary += """
💤 <b>NO QUALITY SETUPS</b>

Market not showing institutional glitches.
<i>Patience is profit 💎</i>
"""
    else:
        summary += "<i>FOREXGOD - When institutions glitch, we profit</i> 💎"
    
    send_telegram_message(summary)
    
    logger.info("\n" + "="*80)
    logger.info("✅ SCAN COMPLETE - Results sent to Telegram!")
    logger.info(f"🔥 Ready: {len(ready_setups)} | 👀 Monitoring: {len(monitoring_setups)}")
    logger.info("="*80)
    
    mt5.shutdown()

if __name__ == "__main__":
    main()
