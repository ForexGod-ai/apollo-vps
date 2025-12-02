# 🤖 Trading AI Agent - Webhook TradingView cu AI

Agent local Python care primește semnale de la TradingView prin webhook, le validează cu AI, și le execută automat pe multiple brokere.

## 🌟 Caracteristici

### 📡 **Webhook TradingView**
- Server Flask care primește semnale în timp real
- Securitate prin HMAC signature validation
- Suport JSON complet configurabil
- Endpoint de testare și monitoring

### 🤖 **Validare AI/Machine Learning**
- Model RandomForest pentru evaluarea semnalelor
- Scoring inteligent bazat pe:
  - Risk/Reward ratio
  - Indicatori tehnici (RSI, MACD, Volume)
  - Timeframe și context de piață
  - Pattern recognition
- Reguli heuristice când modelul nu e antrenat
- Posibilitate de antrenare pe date istorice

### 💰 **Money Management Automat**
- Calculare automată a dimensiunii poziției
- Risc fix per trade (ex: 2%)
- Limite de poziții simultane
- Protecție drawdown maxim
- Limite de pierderi zilnice
- Tracking complet al balanței

### 🔌 **Multi-Broker Support**
Suportă conexiuni la:
- **MetaTrader 5** (Forex/CFD)
- **Oanda** (Forex)
- **Binance Futures** (Crypto)
- **cTrader** (pregătit pentru integrare)

### 📊 **Features Avansate**
- Logging detaliat cu Loguru
- Statistici în timp real
- Istoric complet tranzacții
- API REST pentru monitoring
- Fallback și error handling robust

## 📋 Instalare

### 1. Instalează dependențele

```powershell
cd c:\Users\admog\Desktop\siteRazvan\trading-ai-agent
pip install -r requirements.txt
```

### 2. Configurare

Copiază și editează fișierul de configurare:

```powershell
Copy-Item .env.example .env
notepad .env
```

Configurează:
- `WEBHOOK_SECRET` - cheie secretă pentru validare
- `DEFAULT_BROKER` - broker implicit (MT5, OANDA, BINANCE)
- Credențiale pentru broker-ul ales
- Setări AI și risk management

## 🚀 Utilizare

### Pornește serverul webhook

```powershell
python webhook_server.py
```

Serverul va porni pe `http://localhost:5001`

### Endpoints disponibile:

- **`POST /webhook`** - Primește semnale de la TradingView
- **`GET /health`** - Health check
- **`GET /signals`** - Vezi toate semnalele primite
- **`GET /signals/stats`** - Statistici semnale
- **`POST /test`** - Testează cu un semnal fictiv

## 📤 Configurare TradingView

### 1. În Pine Script, adaugă webhook alert:

```pine
//@version=5
strategy("My Strategy", overlay=true)

// Logica ta de trading
longCondition = ta.crossover(ta.sma(close, 14), ta.sma(close, 28))
shortCondition = ta.crossunder(ta.sma(close, 14), ta.sma(close, 28))

if longCondition
    strategy.entry("Long", strategy.long)
    
if shortCondition
    strategy.entry("Short", strategy.short)

// Alert pentru webhook
if longCondition or shortCondition
    alert('{"action": "' + (longCondition ? "buy" : "sell") + '", "symbol": "{{ticker}}", "price": {{close}}, "timeframe": "{{interval}}", "strategy": "my_strategy"}', alert.freq_once_per_bar)
```

### 2. Configurează Alert în TradingView:

1. Click pe "Alert" (ceas)
2. Condition: Selectează strategia
3. **Webhook URL**: `http://YOUR_IP:5001/webhook`
4. **Message**:
```json
{
  "action": "{{strategy.order.action}}",
  "symbol": "{{ticker}}",
  "price": {{close}},
  "stop_loss": {{strategy.order.price}} * 0.98,
  "take_profit": {{strategy.order.price}} * 1.04,
  "timeframe": "{{interval}}",
  "strategy": "my_strategy",
  "metadata": {
    "rsi": {{rsi}},
    "volume": {{volume}}
  }
}
```

## 🧪 Testare

### Test manual cu curl:

```powershell
curl -X POST http://localhost:5001/webhook `
  -H "Content-Type: application/json" `
  -d '{\"action\":\"buy\",\"symbol\":\"EURUSD\",\"price\":1.0850,\"stop_loss\":1.0820,\"take_profit\":1.0920}'
```

### Test cu endpoint dedicat:

```powershell
curl -X POST http://localhost:5001/test
```

## 📊 Format Semnal JSON

Structura completă acceptată:

```json
{
  "action": "buy",           // buy, sell, close
  "symbol": "EURUSD",        // Simbol trading
  "timeframe": "1h",         // Timeframe
  "price": 1.0850,           // Preț curent
  "stop_loss": 1.0820,       // Stop-loss (opțional)
  "take_profit": 1.0920,     // Take-profit (opțional)
  "strategy": "trend_following",  // Nume strategie
  "timestamp": "2024-01-01T12:00:00",  // Timestamp (opțional)
  "metadata": {              // Indicatori suplimentari (opțional)
    "rsi": 65,
    "macd": 0.0012,
    "volume": 12345,
    "atr": 0.0015
  }
}
```

## 🤖 Antrenare Model AI

Pentru a antrena modelul pe date istorice:

```python
from ai_validator import AISignalValidator

validator = AISignalValidator()

# Date istorice
historical_signals = [
    {"action": "buy", "symbol": "EURUSD", "price": 1.08, "stop_loss": 1.07, "take_profit": 1.10},
    # ... mai multe semnale
]

# Labels: 1 = succes, 0 = eșec
labels = [1, 0, 1, 1, 0, 1, ...]

# Antrenare
accuracy = validator.train_model(historical_signals, labels)
print(f"Model trained with accuracy: {accuracy:.2%}")
```

## 🔧 Configurare Brokeri

### MetaTrader 5

```env
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=BrokerName-Demo
```

Asigură-te că:
- MT5 este instalat și deschis
- Algo Trading este permis
- Serverul este conectat

### Oanda

```env
OANDA_API_KEY=your_api_token
OANDA_ACCOUNT_ID=101-004-12345678-001
OANDA_ENVIRONMENT=practice  # sau 'live'
```

Obține API key de pe: https://www.oanda.com/account/tpa/personal_token

### Binance Futures

```env
BINANCE_API_KEY=your_api_key
BINANCE_SECRET=your_secret_key
BINANCE_TESTNET=True  # pentru testare
```

Creează API key: https://www.binance.com/en/my/settings/api-management

## 📈 Monitoring

### Vezi semnalele primite:

```powershell
curl http://localhost:5001/signals
```

### Statistici:

```powershell
curl http://localhost:5001/signals/stats
```

Răspuns exemplu:
```json
{
  "total_received": 45,
  "processed": 45,
  "successful": 38,
  "success_rate": 84.4
}
```

## ⚙️ Configurare Avansată

### Risk Management

```env
RISK_PER_TRADE=0.02        # 2% risc per trade
MAX_POSITIONS=3            # Max 3 poziții simultane
ACCOUNT_BALANCE=10000      # Balanță cont
```

### AI Validation

```env
AI_VALIDATION_ENABLED=True  # Activează validare AI
AI_MIN_CONFIDENCE=0.7       # Minim 70% confidence
AI_MODEL_PATH=models/signal_validator.pkl
```

## 🛡️ Securitate

### Protejează webhook-ul:

1. **Folosește HTTPS** (Nginx reverse proxy sau ngrok)
2. **Validare signature**: Setează `WEBHOOK_SECRET`
3. **Firewall**: Permite doar IP-uri TradingView
4. **Rate limiting**: Implementează în producție

### IP-uri TradingView (whitelist):

```
52.89.214.238
34.212.75.30
54.218.53.128
52.32.178.7
```

## 🐛 Troubleshooting

### Webhook nu primește semnale

1. Verifică că serverul rulează: `curl http://localhost:5001/health`
2. Verifică firewall-ul
3. Pentru acces extern, folosește ngrok: `ngrok http 5001`
4. Verifică logs în terminal

### Erori de conectare broker

- **MT5**: Asigură-te că MT5 este deschis
- **Oanda**: Verifică API token și account ID
- **Binance**: Verifică permisiuni API (Futures trading enabled)

### AI nu validează semnale

- Verifică `AI_VALIDATION_ENABLED=True`
- Ajustează `AI_MIN_CONFIDENCE` (ex: 0.5 pentru mai puține rejecții)
- Antrenează modelul pe date reale

## 📁 Structura Proiectului

```
trading-ai-agent/
├── webhook_server.py       # Server Flask webhook
├── ai_validator.py         # Validare AI/ML
├── signal_processor.py     # Procesare semnale
├── broker_manager.py       # Gestionare brokeri
├── money_manager.py        # Money management
├── requirements.txt        # Dependențe Python
├── .env.example           # Template configurație
└── models/                # Modele AI antrenate
```

## 🎯 Flow Complet

```
TradingView Alert
      ↓
Webhook Server (Flask)
      ↓
Security Check (HMAC)
      ↓
AI Validator (ML Model)
      ↓
Money Manager (Risk Calc)
      ↓
Broker Manager (MT5/Oanda/Binance)
      ↓
Order Execution
      ↓
Position Tracking
```

## ⚠️ Disclaimer

**Acest agent este furnizat "ca atare" doar în scop educațional.**

- Trading-ul comportă riscuri mari
- Testează pe cont demo înainte de live
- Nu investi bani pe care nu îți permiți să-i pierzi
- Autorii nu își asumă responsabilitatea pentru pierderi

## 📞 Suport

Pentru probleme:
1. Verifică logs în terminal
2. Testează cu endpoint `/test`
3. Verifică configurația `.env`

---

**Creat pentru trading automatizat inteligent! 🚀📈**

Hai sa facem bani
