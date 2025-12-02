"""
SIMULARE SCANARE DIMINEAȚĂ 09:00 - GLITCH IN MATRIX
Scanează toate perechile cu SMC Algorithm + Trimite raport pe Telegram cu grafice
"""

import MetaTrader5 as mt5
import pandas as pd
import json
import os
import requests
import matplotlib
matplotlib.use('Agg')  # Backend non-interactive
import matplotlib.pyplot as plt
import mplfinance as mpf
from datetime import datetime
from loguru import logger
from smc_detector import SMCDetector
from dotenv import load_dotenv

load_dotenv()

# Telegram config
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Create charts folder
os.makedirs('charts', exist_ok=True)

def send_telegram_message(message: str):
    """Send text message to Telegram"""
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
    """Send photo to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(photo_path, 'rb') as photo:
            response = requests.post(url, 
                data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'},
                files={'photo': photo})
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Photo send error: {e}")
        return False

def create_chart(symbol: str, timeframe, bars: int = 100):
    """Create candlestick chart"""
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        
        # Determine timeframe name
        tf_name = {
            mt5.TIMEFRAME_D1: 'Daily',
            mt5.TIMEFRAME_H4: '4H',
            mt5.TIMEFRAME_H1: '1H'
        }.get(timeframe, 'Unknown')
        
        filename = f"charts/{symbol}_{tf_name}.png"
        
        # Chart style
        mc = mpf.make_marketcolors(
            up='#26a69a', down='#ef5350',
            edge='inherit',
            wick={'up':'#26a69a', 'down':'#ef5350'},
            volume='in', alpha=0.9
        )
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=False)
        
        # Plot
        mpf.plot(df, type='candle', style=s, volume=True,
                title=f'{symbol} - {tf_name}',
                savefig=filename, figsize=(12, 8))
        
        logger.info(f"✅ Chart created: {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Chart creation error for {symbol}: {e}")
        return None

def analyze_pair(symbol: str, smc: SMCDetector):
    """Analyze one pair with full SMC"""
    try:
        # Get Daily data
        rates_d1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 100)
        if rates_d1 is None or len(rates_d1) == 0:
            return None
        
        df_daily = pd.DataFrame(rates_d1)
        df_daily['time'] = pd.to_datetime(df_daily['time'], unit='s')
        current_price = df_daily['close'].iloc[-1]
        
        # Detect CHoCH on Daily
        daily_chochs = smc.detect_choch(df_daily)
        if not daily_chochs:
            return None
        
        latest_choch = daily_chochs[-1]
        
        # Detect FVG after CHoCH
        fvg = smc.detect_fvg(df_daily, latest_choch, current_price)
        if not fvg:
            return None
        
        # Check if price in FVG or approaching
        in_fvg = smc.is_price_in_fvg(current_price, fvg)
        
        # Get 4H data for confirmation
        rates_4h = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 200)
        if rates_4h is None:
            return None
        
        df_4h = pd.DataFrame(rates_4h)
        df_4h['time'] = pd.to_datetime(df_4h['time'], unit='s')
        
        # Detect 4H CHoCH
        h4_chochs = smc.detect_choch(df_4h)
        
        # Check for opposite CHoCH on 4H inside FVG
        h4_opposite_choch = None
        if h4_chochs:
            for choch in reversed(h4_chochs):
                choch_price = choch.break_price
                if fvg.bottom <= choch_price <= fvg.top:
                    # Check if opposite direction
                    if latest_choch.direction != choch.direction:
                        h4_opposite_choch = choch
                        break
        
        # Build setup
        setup = {
            'symbol': symbol,
            'current_price': current_price,
            'daily_choch': latest_choch,
            'fvg': fvg,
            'in_fvg': in_fvg,
            'h4_choch': h4_opposite_choch,
            'direction': latest_choch.direction,
            'status': 'READY' if (in_fvg and h4_opposite_choch) else 'MONITORING'
        }
        
        # Calculate entry, SL, TP
        if setup['status'] == 'READY':
            if latest_choch.direction == 'bullish':
                setup['entry'] = fvg.bottom
                setup['sl'] = latest_choch.break_price * 0.998
                setup['tp'] = current_price * 1.02
            else:
                setup['entry'] = fvg.top
                setup['sl'] = latest_choch.break_price * 1.002
                setup['tp'] = current_price * 0.98
            
            setup['rr'] = abs(setup['tp'] - setup['entry']) / abs(setup['entry'] - setup['sl'])
        
        return setup
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return None

def main():
    """Main simulation function"""
    logger.info("\n" + "="*80)
    logger.info("🌅 SIMULARE SCANARE DIMINEAȚĂ 09:00")
    logger.info("🎯 GLITCH IN MATRIX - SMC ALGORITHM")
    logger.info("="*80)
    
    # Initialize MT5
    if not mt5.initialize():
        logger.error("❌ MT5 initialization failed")
        send_telegram_message("❌ <b>MT5 Connection Failed!</b>\n\nCannot run morning scan.")
        return
    
    logger.info(f"✅ MT5 Connected: Account #{mt5.account_info().login}")
    
    # Load pairs config
    try:
        with open('pairs_config.json', 'r') as f:
            config = json.load(f)
            pairs = [p['symbol'] for p in config['pairs']]
    except:
        pairs = ['GBPUSD', 'XAUUSD', 'BTCUSD', 'GBPJPY', 'GBPNZD', 'EURJPY', 
                 'EURUSD', 'NZDCAD', 'USDJPY', 'USDCAD', 'AUDNZD', 'GBPCHF']
    
    logger.info(f"📊 Scanning {len(pairs)} pairs...\n")
    
    # Initialize SMC
    smc = SMCDetector()
    
    # Scan all pairs
    found_setups = []
    monitoring_setups = []
    
    for i, symbol in enumerate(pairs, 1):
        logger.info(f"[{i}/{len(pairs)}] Analyzing {symbol}...")
        setup = analyze_pair(symbol, smc)
        
        if setup:
            if setup['status'] == 'READY':
                found_setups.append(setup)
                logger.info(f"   🔥 READY SETUP: {setup['direction'].upper()}")
            else:
                monitoring_setups.append(setup)
                logger.info(f"   👀 MONITORING: {setup['direction'].upper()}")
        else:
            logger.info(f"   ❌ No setup")
    
    # Send Telegram Report
    logger.info("\n" + "="*80)
    logger.info("📱 SENDING TELEGRAM REPORT")
    logger.info("="*80)
    
    # Header message
    now = datetime.now()
    msg = f"""
🌅 <b>GOOD MORNING - GLITCH IN MATRIX</b>
📅 {now.strftime('%d %B %Y')} - 09:00

━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>SCAN RESULTS:</b>
✅ Scanned: {len(pairs)} pairs
🔥 Ready to Trade: {len(found_setups)}
👀 Monitoring: {len(monitoring_setups)}
"""
    
    if found_setups:
        msg += f"\n🎯 <b>EXECUTE THESE {len(found_setups)} SETUP(S):</b>\n"
    elif monitoring_setups:
        msg += f"\n⏳ <b>WAITING FOR CONFIRMATION...</b>\n"
    else:
        msg += f"\n💤 <b>NO QUALITY SETUPS TODAY</b>\nStay patient!\n"
    
    send_telegram_message(msg)
    
    # Send READY setups with charts
    for i, setup in enumerate(found_setups, 1):
        logger.info(f"\n📤 Sending setup #{i}: {setup['symbol']}")
        
        # Setup details
        direction_emoji = "🟢" if setup['direction'] == 'bullish' else "🔴"
        direction_text = "LONG" if setup['direction'] == 'bullish' else "SHORT"
        
        detail_msg = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>#{i} {setup['symbol']}</b> {direction_emoji} <b>{direction_text}</b>

💰 <b>TRADE SETUP:</b>
Entry: <b>${setup['entry']:.5f}</b>
Stop Loss: ${setup['sl']:.5f}
Take Profit: ${setup['tp']:.5f}
Risk/Reward: <b>1:{setup['rr']:.2f}</b>

📊 <b>ANALYSIS:</b>
• Daily CHoCH: {setup['direction'].upper()}
• FVG Zone: ${setup['fvg'].bottom:.5f} - ${setup['fvg'].top:.5f}
• Price in FVG: ✅
• 4H Confirmation: ✅

✅ <b>STATUS: READY TO EXECUTE</b>
"""
        send_telegram_message(detail_msg)
        
        # Daily chart
        logger.info(f"   Creating Daily chart...")
        chart_d1 = create_chart(setup['symbol'], mt5.TIMEFRAME_D1)
        if chart_d1:
            send_telegram_photo(chart_d1, f"{setup['symbol']} - Daily Timeframe")
        
        # 4H chart
        logger.info(f"   Creating 4H chart...")
        chart_4h = create_chart(setup['symbol'], mt5.TIMEFRAME_H4)
        if chart_4h:
            send_telegram_photo(chart_4h, f"{setup['symbol']} - 4H Timeframe")
    
    # Send MONITORING setups (brief)
    if monitoring_setups:
        monitor_msg = "\n👀 <b>MONITORING THESE SETUPS:</b>\n\n"
        for setup in monitoring_setups[:5]:  # Max 5
            status = "In FVG" if setup['in_fvg'] else "Approaching FVG"
            monitor_msg += f"• {setup['symbol']} {setup['direction'].upper()} ({status})\n"
        
        send_telegram_message(monitor_msg)
    
    # Final summary
    summary = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 <b>ACCOUNT STATUS:</b>
Balance: ${mt5.account_info().balance:.2f}
Equity: ${mt5.account_info().equity:.2f}

⏰ Next scan: Tomorrow 09:00

<i>FOREXGOD - Glitch in Matrix</i>
<i>"When institutions glitch, we profit"</i> 💎
"""
    send_telegram_message(summary)
    
    logger.info("\n" + "="*80)
    logger.info("✅ SIMULARE COMPLETĂ!")
    logger.info(f"🔥 Found {len(found_setups)} ready setups")
    logger.info(f"👀 Monitoring {len(monitoring_setups)} potential setups")
    logger.info("📱 Raport trimis pe Telegram cu grafice!")
    logger.info("="*80)
    
    mt5.shutdown()

if __name__ == "__main__":
    main()
