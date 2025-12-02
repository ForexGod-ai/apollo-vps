"""
Live Market Scanner - Analizează piețele și trimite alerte prin webhook
Funcționează pe macOS fără MT5
"""
import requests
import json
import time
from datetime import datetime
from loguru import logger
import os
from dotenv import load_dotenv

load_dotenv()

# Configurare
WEBHOOK_URL = "http://localhost:5001/webhook"
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram_summary(message):
    """Trimite mesaj sumar pe Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        })
    except Exception as e:
        logger.error(f"Eroare Telegram: {e}")

def get_market_data(symbol):
    """
    Obține date de piață pentru un simbol
    Folosește API-uri publice (demo pentru început)
    """
    # Pentru demo, simulăm date de piață
    # În producție, folosești API real (Oanda, Binance, Alpha Vantage, etc.)
    
    import random
    
    # Simulare date realiste bazate pe simbol
    base_prices = {
        'GBPUSD': 1.2650,
        'EURUSD': 1.0850,
        'XAUUSD': 2050.00,
        'BTCUSD': 42000.00,
        'GBPJPY': 188.50,
        'EURJPY': 161.20,
        'GBPNZD': 2.1200,
        'NZDUSD': 0.5980,
    }
    
    base_price = base_prices.get(symbol, 1.0000)
    
    # Adaugă variație mică pentru realism
    variation = random.uniform(-0.002, 0.002)
    price = base_price * (1 + variation)
    
    # Calculează SL/TP bazate pe analiza tehnică simulată
    # În realitate, aici ar fi analiza ta SMC/Price Action
    atr_percent = random.uniform(0.008, 0.015)
    
    # Decide trend (demo - random cu bias)
    trend_score = random.uniform(-1, 1)
    
    if trend_score > 0.3:  # Bullish
        action = "buy"
        stop_loss = price * (1 - atr_percent)
        take_profit = price * (1 + atr_percent * 2)
    elif trend_score < -0.3:  # Bearish
        action = "sell"
        stop_loss = price * (1 + atr_percent)
        take_profit = price * (1 - atr_percent * 2)
    else:
        return None  # No clear signal
    
    # Metadata pentru AI validator
    metadata = {
        'rsi': random.uniform(30, 70),
        'macd': random.uniform(-0.001, 0.001),
        'volume': random.randint(50000, 150000),
        'atr': price * atr_percent,
        'trend_strength': abs(trend_score)
    }
    
    return {
        'symbol': symbol,
        'action': action,
        'price': round(price, 5),
        'stop_loss': round(stop_loss, 5),
        'take_profit': round(take_profit, 5),
        'timeframe': '1h',
        'strategy': 'live_scanner',
        'timestamp': datetime.now().isoformat(),
        'metadata': metadata
    }

def scan_pairs():
    """Scanează toate perechile configurate"""
    
    # Încarcă perechi din config
    try:
        with open('pairs_config.json', 'r') as f:
            config = json.load(f)
            pairs = [p['symbol'] for p in config['pairs']]
    except Exception as e:
        logger.error(f"Eroare la citirea pairs_config.json: {e}")
        return
    
    logger.info("=" * 60)
    logger.info(f"🔍 LIVE MARKET SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"📊 Scanning {len(pairs)} pairs...")
    logger.info("=" * 60)
    
    found_setups = []
    
    for i, symbol in enumerate(pairs, 1):
        logger.info(f"[{i}/{len(pairs)}] 🔎 Analyzing {symbol}...")
        
        try:
            # Obține date piață
            signal_data = get_market_data(symbol)
            
            if signal_data is None:
                logger.info(f"   ⚪ No clear signal")
                continue
            
            # Trimite la webhook pentru validare AI + notificare
            response = requests.post(
                WEBHOOK_URL,
                json=signal_data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Verifică dacă a fost aprobat
                if result.get('status') == 'success':
                    if result['result'].get('notification_sent'):
                        logger.info(f"   ✅ SETUP GĂSIT! Alert trimis pentru {symbol}")
                        found_setups.append(symbol)
                    else:
                        rejection = result['result'].get('rejection_reason', 'Unknown')
                        logger.info(f"   ❌ Respins: {rejection}")
                else:
                    logger.info(f"   ⚠️ Error: {result.get('message')}")
            else:
                logger.warning(f"   ⚠️ Webhook error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"   ❌ Error scanning {symbol}: {e}")
        
        # Pauză între requests pentru a nu overload sistemul
        time.sleep(0.5)
    
    logger.info("=" * 60)
    logger.info(f"✅ Scan complet!")
    logger.info(f"📊 Total perechi scanate: {len(pairs)}")
    logger.info(f"🎯 Setup-uri găsite: {len(found_setups)}")
    
    if found_setups:
        logger.info(f"🔥 Setup-uri: {', '.join(found_setups)}")
        
        # Trimite sumar pe Telegram
        summary = f"📊 *LIVE MARKET SCAN COMPLET*\n\n"
        summary += f"✅ Scanate: {len(pairs)} perechi\n"
        summary += f"🎯 Setup-uri găsite: {len(found_setups)}\n\n"
        if found_setups:
            summary += f"🔥 *Perechi cu setup-uri:*\n"
            summary += "\n".join([f"   • {s}" for s in found_setups])
        else:
            summary += "Niciun setup valid găsit momentan."
        
        send_telegram_summary(summary)
    else:
        logger.info("⚪ Niciun setup valid găsit în acest scan")
    
    logger.info("=" * 60)

def continuous_scan(interval_minutes=30):
    """Scanează continuu la intervale regulate"""
    logger.info("🚀 Starting continuous market scanner...")
    logger.info(f"⏰ Scan interval: {interval_minutes} minutes")
    
    while True:
        try:
            scan_pairs()
            logger.info(f"\n⏳ Next scan in {interval_minutes} minutes...\n")
            time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            logger.info("\n⚠️ Scanner stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Error in continuous scan: {e}")
            time.sleep(60)  # Wait 1 minute before retry

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "continuous":
        # Mod continuu
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        continuous_scan(interval)
    else:
        # Un singur scan
        scan_pairs()
