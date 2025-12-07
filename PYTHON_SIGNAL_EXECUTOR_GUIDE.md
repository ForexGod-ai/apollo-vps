# 🤖 PythonSignalExecutor - Deployment Guide

## 📋 Overview
Bot cTrader care citește signals.json și execută automat trade-uri în IC Markets.

## 🚀 DEPLOYMENT STEPS

### 1. Deschide cTrader
```
✅ Login la IC Markets Demo: 9709773
✅ Asigură-te că ai cTrader Automate (cAlgo) instalat
```

### 2. Accesează cTrader Automate
```
1. Click pe "Automate" în meniul principal
2. SAU apasă F9
3. Se va deschide cAlgo Editor
```

### 3. Creează Bot Nou
```
1. În cAlgo, click pe "New" → "cBot"
2. Nume: PythonSignalExecutor
3. Click "Create"
```

### 4. Copiază Codul
```
1. Șterge tot codul template din editor
2. Copiază tot conținutul din PythonSignalExecutor.cs
3. Paste în editor
4. Click "Build" (sau Ctrl+B)
5. Verifică că build-ul e success (fără erori)
```

### 5. Configurare Parametri

**IMPORTANT: Actualizează Signal File Path!**

Calea curentă în cod:
```csharp
[Parameter("Signal File Path", DefaultValue = "/Users/forexgod/Desktop/trading-ai-agent apollo/signals.json")]
```

Verifică calea exactă pe Mac:
```bash
# Rulează acest command pentru a afla calea exactă:
pwd
# Apoi adaugă /signals.json la final
```

**Parametri Bot:**
```
Signal File Path: /Users/forexgod/Desktop/trading-ai-agent apollo/signals.json
Check Interval: 10 secunde
Max Risk %: 2.0
Auto Close at Profit: 100 pips
Breakeven Trigger: 50 pips
```

### 6. Start Bot
```
1. În cTrader, deschide orice chart (ex: GBPUSD, H4)
2. Click pe "Automate" tab
3. Găsește "PythonSignalExecutor" în listă
4. Drag & drop pe chart
5. Setează parametrii (vezi mai sus)
6. Click "Start"
```

### 7. Verifică Funcționarea

**A. Check Logs:**
```
✅ Ar trebui să vezi în cTrader log:
   "🤖 Python Signal Executor Started (Swing Trading Mode)"
   "📁 Monitoring: /path/to/signals.json"
   "⏱️ Check interval: 10s"
```

**B. Test cu Signal:**
```bash
# Trimite test signal prin webhook:
curl -X POST http://127.0.0.1:5001/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "action": "buy",
    "symbol": "GBPUSD",
    "price": 1.27500,
    "stop_loss": 1.27200,
    "take_profit": 1.28100,
    "timeframe": "4H",
    "strategy": "test",
    "timestamp": "2025-12-07T15:00:00"
  }'
```

**C. Monitorizează:**
```
1. Verifică că signals.json s-a actualizat
2. În max 10 secunde, bot-ul ar trebui să execute trade-ul
3. Verifică în cTrader că trade-ul e deschis
4. Check în Telegram pentru notificare
```

## 🔧 Troubleshooting

### Problem: Bot nu găsește signals.json
```
✅ FIX:
1. Verifică calea completă cu pwd
2. Actualizează parametrul "Signal File Path" în bot
3. Restart bot
```

### Problem: Bot nu execută trade-uri
```
✅ CHECK:
1. Bot e pornit? (verde în cTrader)
2. signals.json există și e actualizat recent?
3. Check cTrader logs pentru erori
4. Verifică că account-ul are margin disponibil
```

### Problem: Erori de Build
```
✅ FIX:
1. Asigură-te că folosești cTrader Desktop (nu web)
2. Verifică că ai API access enabled
3. Copy/paste din nou tot codul (poate ai pierdut caractere)
```

## 📊 Cum Funcționează Fluxul Complet

```
┌─────────────────────────────────────────────────────────────┐
│ 1. TradingView / Morning Scanner găsește setup              │
│    → trimite la webhook                                      │
└─────────────────┬───────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Webhook Server primește signal                           │
│    → AI Validator (70% confidence)                           │
│    → Money Manager (2% risk, calculate lots)                 │
└─────────────────┬───────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. ctrader_executor.py scrie în signals.json                │
│    {                                                          │
│      "signalId": "SIGNAL_20251207_150000",                   │
│      "symbol": "GBPUSD",                                      │
│      "direction": "buy",                                      │
│      "entryPrice": 1.27500,                                   │
│      "stopLoss": 1.27200,                                     │
│      "takeProfit": 1.28100,                                   │
│      "volume": 0.09                                           │
│    }                                                          │
└─────────────────┬───────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. PythonSignalExecutor (cTrader bot)                        │
│    → Check signals.json every 10s                            │
│    → Detectează new signal                                   │
│    → Execute în cTrader                                       │
└─────────────────┬───────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Trade LIVE în IC Markets                                  │
│    → Telegram notification sent                               │
│    → TradeHistorySyncer updates trade_history.json           │
│    → Dashboard refreshed                                      │
└─────────────────────────────────────────────────────────────┘
```

## ✅ Success Indicators

Când totul funcționează corect:

1. **✅ Bot Status în cTrader:** Verde (Running)
2. **✅ Logs:** "Monitoring: /path/to/signals.json"
3. **✅ Test Signal:** Trade executat în <10s
4. **✅ Telegram:** Notificare primită automat
5. **✅ cTrader:** Trade vizibil cu label "Glitch Matrix"

## 🔥 Features

### Auto Risk Management
- ✅ Lot size calculat automat (2% risk)
- ✅ SL și TP setate din signal
- ✅ Max 3 poziții simultan

### Position Management
- ✅ Breakeven la +50 pips profit
- ✅ Auto-close la +100 pips profit
- ✅ Label: "Glitch Matrix - {strategy}"

### Smart Execution
- ✅ Verifică overlap cu trade-uri existente
- ✅ Skip duplicate signals
- ✅ Market execution pentru INSTANT entry

## 📱 Monitoring

### Real-time:
```
✅ cTrader: Logs tab
✅ Telegram: 🔮 ForexGod - Glitch in Matrix 🧠
✅ Webhook logs: tail -f webhook.log
✅ signals.json: cat signals.json
```

### Daily:
```
✅ trade_history.json: Total trades & profit
✅ Dashboard: http://127.0.0.1:5001
✅ Account report: python3 generate_account_report.py
```

---

## 🚀 NEXT: STEP 3 - Morning Scan Automation

După ce ai PythonSignalExecutor running, trecem la automatizarea morning scan-ului la 09:00! 🔥
