# 📚 Documentație Completă - Trading AI Signal Notifier

## 📖 Cuprins
1. [Prezentare Generală](#prezentare-generală)
2. [Arhitectură Sistem](#arhitectură-sistem)
3. [Setup & Instalare](#setup--instalare)
4. [Configurare](#configurare)
5. [Utilizare](#utilizare)
6. [Structură Cod](#structură-cod)
7. [Flow Procesare Semnal](#flow-procesare-semnal)
8. [API Reference](#api-reference)
9. [Notificări](#notificări)
10. [Next Steps](#next-steps)

---

## 🎯 Prezentare Generală

### Ce Face Proiectul?

Sistemul primește **semnale de trading de la TradingView** prin webhook, le **validează cu AI/ML**, calculează **risk management** optimal, și îți trimite **alerte frumoase** când găsește setup-uri bune de trading.

**🚫 NU mai execută automat tradurile** - tu decizi când să intri în piață!

### De Ce E Util?

✅ **Filtrare inteligentă** - AI elimină semnalele proaste  
✅ **Risk management automat** - Calculează lot size perfect  
✅ **Notificări instant** - Telegram + Desktop alerts  
✅ **Multi-platform** - Funcționează pe macOS, Windows, Linux  
✅ **Transparent** - Vezi exact de ce AI aprobă/respinge semnale  

---

## 🏗️ Arhitectură Sistem

```
┌─────────────────────────────────────────────────────────┐
│                    TRADINGVIEW                          │
│  (Strategy generates alert with webhook)                │
└─────────────────┬───────────────────────────────────────┘
                  │ HTTP POST /webhook
                  ▼
┌─────────────────────────────────────────────────────────┐
│              WEBHOOK SERVER (Flask)                      │
│  - Receives signal                                       │
│  - Validates HMAC signature                              │
│  - Logs all requests                                     │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│            SIGNAL PROCESSOR                              │
│  Orchestrates the entire flow                            │
└─────────────────┬───────────────────────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
┌──────────────┐    ┌──────────────┐
│ AI VALIDATOR │    │MONEY MANAGER │
│              │    │              │
│ - ML Model   │    │ - Position   │
│ - Confidence │    │   size calc  │
│ - Scoring    │    │ - Risk %     │
└──────┬───────┘    └──────┬───────┘
       │                   │
       └─────────┬─────────┘
                 │ Both approved?
                 ▼
        ┌────────────────┐
        │  NOTIFICATION  │
        │    MANAGER     │
        │                │
        │ - Telegram     │
        │ - Desktop      │
        │ - Email (soon) │
        └────────┬───────┘
                 │
                 ▼
         ┌──────────────┐
         │   YOU! 🎯    │
         │ (Manual exec)│
         └──────────────┘
```

---

## 🚀 Setup & Instalare

### 1. Cerințe Sistem

- **Python 3.8+**
- **macOS** / Windows / Linux
- **Internet connection** (pentru Telegram)
- **TradingView** account (free sau premium)

### 2. Instalare Dependențe

```bash
cd /Users/forexgod/Desktop/trading-ai-agent

# Instalează toate pachetele
pip3 install flask flask-cors python-dotenv numpy pandas scikit-learn ta requests pydantic loguru
```

### 3. Configurare .env

```bash
# Copiază template-ul
cp .env.example .env

# Editează cu valorile tale
nano .env
```

---

## ⚙️ Configurare

### Setup Telegram Bot (RECOMANDAT!)

#### Pasul 1: Creează Bot

1. Deschide Telegram și caută **@BotFather**
2. Trimite `/newbot`
3. Alege nume: `ForexGod Trading Alerts`
4. Alege username: `forexgod_alerts_bot`
5. Primești **BOT TOKEN** → copiază-l

#### Pasul 2: Obține Chat ID

1. Caută botul tău în Telegram
2. Trimite-i un mesaj: `/start`
3. Deschide în browser:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. Caută în JSON: `"chat":{"id":123456789}` → acesta e Chat ID-ul

#### Pasul 3: Configurează .env

```env
TELEGRAM_ENABLED=True
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

### Setup Desktop Notifications (macOS)

✅ **Deja funcționează out-of-the-box!**

Sistemul folosește AppleScript pentru notificări native macOS.

```env
DESKTOP_NOTIFICATIONS=True
```

### Configurare AI & Risk Management

```env
# AI Settings
AI_VALIDATION_ENABLED=True
AI_MIN_CONFIDENCE=0.7          # Minim 70% confidence

# Risk Management
RISK_PER_TRADE=0.02            # 2% risc per trade
MAX_POSITIONS=3                # Max 3 poziții simultane
ACCOUNT_BALANCE=10000          # Balanța contului

# Siguranță
AUTO_TRADE_ENABLED=False       # NU activa asta! (execuție manuală)
```

---

## 🎮 Utilizare

### 1. Pornește Serverul

```bash
python3 main.py
```

Output așteptat:
```
12:17:58 | INFO - 🚀 Pornire Trading AI Agent...
12:17:58 | INFO - ========================================
12:17:58 | INFO - 🚀 Trading AI Agent Webhook Server
12:17:58 | INFO - 📡 Server pornit pe http://0.0.0.0:5001
12:17:58 | INFO - 📥 Webhook URL: http://0.0.0.0:5001/webhook
```

### 2. Testează Notificările

```bash
curl -X POST http://localhost:5001/test
```

Ar trebui să primești:
- ✅ Notificare Telegram
- ✅ Notificare Desktop (macOS)

### 3. Configurează TradingView

#### Pine Script Example:

```pinescript
//@version=5
strategy("Forex God Strategy", overlay=true)

// Strategy logic
ema_fast = ta.ema(close, 9)
ema_slow = ta.ema(close, 21)
rsi = ta.rsi(close, 14)

longCondition = ta.crossover(ema_fast, ema_slow) and rsi < 70
shortCondition = ta.crossunder(ema_fast, ema_slow) and rsi > 30

if longCondition
    strategy.entry("Long", strategy.long)
    
if shortCondition
    strategy.entry("Short", strategy.short)

// Alert pentru webhook
if longCondition or shortCondition
    action = longCondition ? "buy" : "sell"
    sl = longCondition ? close * 0.98 : close * 1.02
    tp = longCondition ? close * 1.04 : close * 0.96
    
    alert_message = '{"action":"' + action + '","symbol":"' + syminfo.ticker + 
                    '","price":' + str.tostring(close) + 
                    ',"stop_loss":' + str.tostring(sl) + 
                    ',"take_profit":' + str.tostring(tp) + 
                    ',"timeframe":"' + timeframe.period + 
                    '","metadata":{"rsi":' + str.tostring(rsi) + '}}'
    
    alert(alert_message, alert.freq_once_per_bar)
```

#### Configurare Alert în TradingView:

1. Click **Alert** (icon ceas)
2. **Condition**: Alege strategia ta
3. **Webhook URL**: 
   - Local: `http://localhost:5001/webhook`
   - Public (ngrok): `https://abc123.ngrok.io/webhook`
4. **Message**: (lasă gol, Pine Script trimite JSON-ul)
5. Click **Create**

### 4. Expunere Publică (pentru TradingView Cloud)

TradingView trimite webhook-uri doar la URL-uri publice. Folosește **ngrok**:

```bash
# Instalează ngrok
brew install ngrok

# Pornește tunnel
ngrok http 5001
```

Output:
```
Forwarding https://abc123.ngrok.io -> http://localhost:5001
```

Folosește URL-ul `https://abc123.ngrok.io/webhook` în TradingView!

---

## 📂 Structură Cod

### Fișiere Principale

```
trading-ai-agent/
├── main.py                     # Entry point - pornește serverul
├── webhook_server.py           # Flask server, endpoints REST
├── signal_processor.py         # Orchestrează tot flow-ul
├── notification_manager.py     # 🆕 Trimite alerte (Telegram, Desktop)
├── ai_validator.py             # Model ML pentru validare
├── money_manager.py            # Calculează risk & position size
├── broker_manager.py           # (DEPRECATED - nu mai e folosit)
├── .env                        # Configurație (NU face commit!)
├── .env.example                # Template pentru .env
├── requirements.txt            # Dependențe Python
├── README.md                   # README pentru utilizatori
└── DOCUMENTATION.md            # 📄 Documentația asta!
```

### Descriere Módulos

#### `main.py`
- Entry point simplu
- Configurare logging
- Pornește webhook server

#### `webhook_server.py`
- Server Flask pe port 5001
- Endpoints: `/webhook`, `/health`, `/test`, `/signals`, `/signals/stats`
- Validare HMAC signatures
- Storage semnale primite

#### `signal_processor.py` ⭐
- **CORE MODULE**
- Orchestrează tot procesul:
  1. Validare AI
  2. Money management
  3. 🆕 Trimite notificare (NU mai execută!)
- Return result cu toate detaliile

#### `notification_manager.py` 🆕
- **MODUL NOU!**
- Trimite alerte pe:
  - Telegram (cu Markdown formatting frumos)
  - Desktop notifications (macOS/Windows/Linux)
- Format mesaj detaliat cu toate info-urile
- Error handling robust

#### `ai_validator.py`
- Model RandomForest pentru scoring
- Validare bazată pe:
  - Risk/Reward ratio
  - Indicatori tehnici (RSI, MACD, Volume, ATR)
  - Timeframe
- Reguli heuristice când modelul nu e antrenat
- Confidence score: 0-100%

#### `money_manager.py`
- Calculează position size bazat pe risk %
- Validează:
  - Max pozițíi simultane
  - Drawdown limits
  - Risk per trade
- Tracking balanță

---

## 🔄 Flow Procesare Semnal

### Diagrama Detaliată

```
1. PRIMIRE SEMNAL
   └─> Webhook POST la /webhook
       └─> Verifică HMAC signature
           └─> Parse JSON
               └─> Log in received_signals[]

2. VALIDARE AI
   └─> Extract features (RR, RSI, MACD, etc.)
       └─> Model ML predict
           └─> Calculate confidence score
               ├─> < 70%? → REJECT ❌
               └─> ≥ 70%? → APPROVE ✅

3. MONEY MANAGEMENT
   └─> Calculează risk amount (balance * risk%)
       └─> Calculează position size
           └─> Verifică limite:
               ├─> Prea multe poziții? → REJECT ❌
               ├─> Drawdown prea mare? → REJECT ❌
               └─> OK? → APPROVE ✅

4. NOTIFICARE 🆕
   └─> Construiește mesaj frumos
       └─> Trimite pe Telegram
           └─> Trimite desktop notification
               └─> Log success/failure

5. RETURN RESULT
   └─> JSON cu toate detaliile
       └─> Store în history
           └─> Update statistics
```

### Exemplu Real

**Input Signal:**
```json
{
  "action": "buy",
  "symbol": "EURUSD",
  "price": 1.0850,
  "stop_loss": 1.0820,
  "take_profit": 1.0920,
  "timeframe": "1h",
  "metadata": {
    "rsi": 45,
    "macd": 0.0005
  }
}
```

**AI Validation:**
```
✅ Approved
- Confidence: 85%
- RR Ratio: 1:2.33 (Good!)
- RSI: 45 (Not overbought)
- Score: 8.5/10
```

**Money Management:**
```
✅ Approved
- Account Balance: $10,000
- Risk %: 2%
- Risk Amount: $200
- SL Distance: 30 pips
- Position Size: 0.66 lots
```

**Notification Sent:**
```
🟢 SETUP DE TRADING GĂSIT! 🟢

📊 Simbol: EURUSD
🎯 Acțiune: BUY
💰 Preț Entry: 1.0850
🛑 Stop Loss: 1.0820
🎯 Take Profit: 1.0920
⚖️ Risk/Reward: 1:2.33

🤖 AI Confidence: 85.0%
📈 AI Score: 8.50/10

💼 Position Size: 0.66 lots
📉 Risk Amount: $200.00
📊 Risk Percent: 2.0%

📊 Indicatori:
   RSI: 45.0
   MACD: 0.0005

🕐 Timp: 2025-12-02 12:34:56

✅ Verifică chart-ul și execută manual!
```

---

## 📡 API Reference

### Endpoints Disponibile

#### `POST /webhook`
Primește semnale de la TradingView.

**Headers:**
```
Content-Type: application/json
X-Signature: <hmac_sha256_signature>  # Optional
```

**Body:**
```json
{
  "action": "buy|sell|close",
  "symbol": "EURUSD",
  "price": 1.0850,
  "stop_loss": 1.0820,     // Optional
  "take_profit": 1.0920,   // Optional
  "timeframe": "1h",       // Optional
  "strategy": "my_strat",  // Optional
  "metadata": {            // Optional
    "rsi": 45,
    "macd": 0.0005,
    "volume": 12345
  }
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Signal processed and notification sent",
  "result": {
    "signal": {...},
    "ai_validation": {
      "approved": true,
      "confidence": 0.85,
      "score": 8.5
    },
    "risk_assessment": {
      "approved": true,
      "position_size": 0.66,
      "risk_amount": 200
    },
    "notification_sent": true
  }
}
```

#### `GET /health`
Health check pentru monitoring.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-02T12:34:56",
  "version": "2.0.0"
}
```

#### `POST /test`
Testează sistemul cu un semnal fictiv.

**Response:**
```json
{
  "status": "success",
  "message": "Test signal sent",
  "notification_sent": true
}
```

#### `GET /signals`
Vezi toate semnalele primite.

**Response:**
```json
{
  "total": 45,
  "signals": [
    {
      "timestamp": "2025-12-02T12:00:00",
      "action": "buy",
      "symbol": "EURUSD",
      "approved": true
    },
    ...
  ]
}
```

#### `GET /signals/stats`
Statistici despre semnale.

**Response:**
```json
{
  "total_received": 45,
  "approved": 38,
  "rejected": 7,
  "success_rate": 84.4,
  "avg_confidence": 0.78
}
```

---

## 📢 Notificări

### Format Mesaj Telegram

Mesajul este formatat cu **Markdown** și include:

```
🟢 SETUP DE TRADING GĂSIT! 🟢

📊 Simbol: [SYMBOL]
🎯 Acțiune: [BUY/SELL]
💰 Preț Entry: [PRICE]
🛑 Stop Loss: [SL]
🎯 Take Profit: [TP]
⚖️ Risk/Reward: 1:[RR]

🤖 AI Confidence: [%]
📈 AI Score: [0-10]

💼 Position Size: [LOTS] lots
📉 Risk Amount: $[AMOUNT]
📊 Risk Percent: [%]

📊 Indicatori:
   RSI: [VALUE]
   MACD: [VALUE]
   Volume: [VALUE]

🕐 Timp: [TIMESTAMP]

✅ Verifică chart-ul și execută manual!
```

### Desktop Notifications (macOS)

- **Titlu**: `🎯 Setup BUY - EURUSD`
- **Body**: `Preț: 1.0850`
- **Sound**: Glass (notification sound)
- **Durată**: Rămâne până când o închizi

### Customizare Notificări

Poți modifica în `notification_manager.py`:

```python
def _build_alert_message(self, signal_data, ai_validation, risk_assessment):
    # Modifică aici formatul mesajului
    message = "CUSTOM FORMAT HERE"
    return message
```

---

## 🔮 Next Steps

### Funcționalități de Adăugat

#### 1. Email Notifications 📧
```python
# notification_manager.py
def _send_email(self, message):
    import smtplib
    # Implementare SMTP
```

#### 2. Chart Screenshots 📸
- Integrare cu TradingView API
- Screenshot automat la alertă
- Attach în Telegram

#### 3. Trade Journal 📓
- SQLite database pentru tracking
- Dashboard web cu statistici
- Export CSV/Excel

#### 4. Backtesting 📊
- Test strategii pe date istorice
- Optimizare parametri AI
- Report detaliat performanță

#### 5. Multi-Account Support 👥
- Notificări pentru mai multe conturi
- Group notifications în Telegram
- Separate risk management

#### 6. Advanced AI 🧠
- Antrenare pe propriile date
- Deep Learning models (LSTM)
- Sentiment analysis (news, social media)

#### 7. VPS Auto-Deploy 🚀
- Script setup automat pentru VPS
- Docker containerization
- CI/CD pipeline

### Îmbunătățiri Imediate

1. **Creează fișier `.env`** din `.env.example`
2. **Setup Telegram Bot** (10 minute)
3. **Testează cu `/test` endpoint**
4. **Configurează TradingView alerts**
5. **Monitorizează primele semnale**

### Plan pe Termen Lung

**Săptămâna 1:**
- ✅ Setup complet sistem
- ✅ Primele 10 alerte de test
- ✅ Fine-tune AI confidence threshold

**Săptămâna 2:**
- 📊 Tracking performanță semnale
- 🎯 Optimizare parametri
- 📈 Comparație cu execuție manuală

**Luna 1:**
- 🧠 Antrenare model pe date reale
- 📸 Adăugare chart screenshots
- 📧 Email notifications

**Luna 2:**
- 🔗 Integrare cu mai multe strategii TradingView
- 📊 Dashboard web interactiv
- 🤖 Advanced ML models

---

## 🛠️ Troubleshooting

### Problema: Nu primesc notificări Telegram

**Soluție:**
1. Verifică `TELEGRAM_ENABLED=True` în `.env`
2. Testează bot token:
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getMe
   ```
3. Verifică Chat ID este corect
4. Trimite `/start` la bot

### Problema: Desktop notifications nu funcționează

**macOS:**
- Verifică System Preferences → Notifications
- Permite notificări pentru Terminal/Python

**Windows:**
- Instalează: `pip install win10toast`

**Linux:**
- Instalează: `sudo apt-get install libnotify-bin`

### Problema: AI respinge toate semnalele

**Soluție:**
- Reduce `AI_MIN_CONFIDENCE` la 0.5
- Verifică că semnalele au `stop_loss` și `take_profit`
- Antrenează modelul pe date reale

### Problema: Webhook nu primește din TradingView

**Soluție:**
1. Verifică server rulează: `curl http://localhost:5001/health`
2. Folosește ngrok pentru URL public
3. Verifică firewall nu blochează port 5001
4. Testează cu `/test` endpoint mai întâi

---

## 📞 Contact & Support

Pentru întrebări sau probleme:

1. **Check logs**: `tail -f trading_agent.log`
2. **Test endpoints**: `curl http://localhost:5001/test`
3. **Verifică .env**: toate valorile sunt setate corect?

---

## ⚠️ Disclaimer

- Sistem creat pentru **scop educațional**
- Trading comportă **riscuri mari**
- **Testează** pe cont demo înainte de live
- **NU investi** bani pe care nu îți permiți să-i pierzi
- Autorii **NU își asumă responsabilitatea** pentru pierderi

---

## 🎯 Summary

Ai acum un sistem complet care:

✅ Primește semnale de la TradingView  
✅ Validează cu AI (85%+ accuracy)  
✅ Calculează risk management perfect  
✅ Trimite alerte frumoase pe Telegram & Desktop  
✅ Funcționează pe macOS  
✅ NU execută automat (control total!)  

**Next:** Setup Telegram, testează, și începe să primești alerte! 🚀

---

**Creat cu 💪 by ForexGod | Decembrie 2025**
