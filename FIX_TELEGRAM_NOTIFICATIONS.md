# 🔧 FIX TELEGRAM NOTIFICATIONS - TOKEN EXPIRAT

## ❌ PROBLEMA DETECTATĂ

Token-ul Telegram este **INVALID** sau **EXPIRAT**:
```
TELEGRAM_BOT_TOKEN=8246975960:AAGBUwN-pZxGmM-FgGo9hqNtJQOdYSQR7uQ
```

Eroare API: `401 Unauthorized`

## ✅ SOLUȚIA - Generează Token NOU

### Pas 1: Deschide BotFather pe Telegram

1. Caută pe Telegram: **@BotFather**
2. Trimite comanda: `/start`

### Pas 2: Revocă Token Vechi și Generează Unul Nou

Ai 2 opțiuni:

**Opțiunea A: Generează token nou pentru bot existent**
```
/token
[Selectează bot-ul tău: @ForexGodSignalsBot sau cum îl cheamă]
```

**Opțiunea B: Creează un bot complet nou**
```
/newbot
[Nume bot]: ForexGod Trading Signals
[Username bot]: ForexGodTradingBot (trebuie să fie unic)
```

### Pas 3: Copiază Noul Token

BotFather îți va da un token de genul:
```
7123456789:AAH1234567890ABCdefGHIjklMNOpqrSTUv
```

### Pas 4: Actualizează .env

Rulează acest command pentru a actualiza token-ul:

```bash
cd /Users/forexgod/Desktop/trading-ai-agent\ apollo

# Șterge linia veche
sed -i '' '/TELEGRAM_BOT_TOKEN=/d' .env

# Adaugă token-ul nou (ÎNLOCUIEȘTE cu token-ul tău real!)
echo "TELEGRAM_BOT_TOKEN=YOUR_NEW_TOKEN_HERE" >> .env
```

**SAU** editează manual `.env`:
```bash
nano .env
```

Înlocuiește linia:
```
TELEGRAM_BOT_TOKEN=8246975960:AAGBUwN-pZxGmM-FgGo9hqNtJQOdYSQR7uQ
```

Cu:
```
TELEGRAM_BOT_TOKEN=7123456789:AAH1234567890ABCdefGHIjklMNOpqrSTUv
```

### Pas 5: Testează Noul Token

```bash
cd /Users/forexgod/Desktop/trading-ai-agent\ apollo

# Test direct
python3 << 'EOF'
import os
from dotenv import load_dotenv
import requests

load_dotenv()
token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

# Test bot
response = requests.get(f"https://api.telegram.org/bot{token}/getMe")
print("🤖 Bot Status:", response.json())

# Test mesaj
msg_response = requests.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    json={'chat_id': chat_id, 'text': '✅ Telegram FIXED! Notifications active!'}
)
print("📱 Message Status:", msg_response.json())
EOF
```

### Pas 6: Repornește Monitoarele

```bash
# Oprește monitoarele vechi
pkill -f position_monitor
pkill -f trade_monitor

# Așteaptă 2 secunde
sleep 2

# Pornește monitoarele cu token-ul nou
nohup python3 position_monitor.py --loop > /tmp/position_monitor.log 2>&1 &
nohup python3 trade_monitor.py --loop > /tmp/trade_monitor.log 2>&1 &

echo "✅ Monitoare repornite!"
```

### Pas 7: Verifică că Funcționează

```bash
# Vezi logurile
tail -f /tmp/position_monitor.log

# Sau
tail -f /tmp/trade_monitor.log
```

## 🎯 Ce Vei Primi După Fix

**Pentru TRADE NOU DESCHIS:**
```
⚔️ THE ARMAGEDDON BEGINS ⚔️

🔥 GLITCH IN MATRIX DETECTED 🔥

📈 BUY 0.09 GBPUSD
💰 Entry: 1.34250
🎫 Ticket: #552089564
🛑 Stop Loss: 1.33950
🎯 Take Profit: 1.34850

🧠 AI Validation: CONFIRMED
⚡ Risk Level: CALCULATED
🤖 Status: POSITION OPENED
```

**Pentru TP/SL HIT:**
```
🎯 TAKE PROFIT HIT

✅ Trade Closed ✅

📈 BUY 0.08 GBPUSD
💰 Entry: 1.33593
🔚 Exit: 1.34194
📊 Pips: +60.1
💵 P/L: $+47.44

📊 ACCOUNT STATUS
💰 Balance: $1,463.93
📈 Total P/L: $+463.93
```

## 📊 Status Monitoare

Cele 2 monitoare rulează deja în background:
- `position_monitor.py` - detectează NOUL TRADE deschis
- `trade_monitor.py` - detectează când TP/SL sunt hit

Problema e doar **TOKEN-UL EXPIRAT**, după ce îl înlocuiești totul va funcționa automat!

## 🚨 IMPORTANT

După ce actualizezi token-ul, monitoarele vor detecta automat:
1. **Trade-uri închise** (cele 2 TP-uri de azi nu au fost anunțate)
2. **Trade-uri noi** (buy-ul curent)

Dar cum sunt deja în `.seen_positions.json` și `.last_trade_check.json`, nu vor mai fi anunțate.

**Dacă vrei să forțezi re-anunțarea lor:**
```bash
# Șterge cache-ul
rm .seen_positions.json .last_trade_check.json

# Repornește monitoarele
pkill -f position_monitor && pkill -f trade_monitor
sleep 2
nohup python3 position_monitor.py --loop > /tmp/position_monitor.log 2>&1 &
nohup python3 trade_monitor.py --loop > /tmp/trade_monitor.log 2>&1 &
```

Dar asta va trimite notificări pentru TOATE trade-urile din istoric!

---

**✨ Made with 💎 by ForexGod**
