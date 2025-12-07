# 📈 TradingView Webhook Setup Guide

## 🎯 Overview
Configurare webhook pentru a primi semnale LIVE de la TradingView alerts direct în sistemul de trading.

## 🔧 Setup Steps

### 1. Asigură-te că Webhook Server rulează
```bash
# Pornește server-ul (dacă nu e pornit deja)
python3 webhook_server.py

# Verifică că rulează pe:
# http://192.168.1.132:5001/webhook
```

### 2. Configurare în TradingView

#### A. Creează un Alert
1. Deschide TradingView (https://www.tradingview.com)
2. Selectează un symbol (ex: GBPUSD, EURUSD, XAUUSD)
3. Click pe ceas ⏰ sau apasă ALT+A
4. Click "Create Alert"

#### B. Configurare Alert Settings

**Condition:**
- Strategy: Alege strategia ta (Moving Average, RSI, etc.)
- SAU: Price crosses above/below

**Options:**
- Alert name: `ForexGod - {symbol} - {strategy}`
- Trigger: Once Per Bar Close (recomandat) sau Every Time

**Webhook URL:**
```
http://192.168.1.132:5001/webhook
```

**Message (JSON Format):**
```json
{
  "action": "buy",
  "symbol": "{{ticker}}",
  "price": {{close}},
  "stop_loss": {{low}},
  "take_profit": {{high}},
  "timeframe": "{{interval}}",
  "strategy": "tradingview_alert",
  "timestamp": "{{time}}",
  "priority": 1,
  "confidence": 0.85,
  "metadata": {
    "rsi": {{plot("RSI")}},
    "volume": {{volume}},
    "source": "tradingview"
  }
}
```

**Pentru Strategy Alerts (cu Pine Script):**
```json
{
  "action": "{{strategy.order.action}}",
  "symbol": "{{ticker}}",
  "price": {{close}},
  "stop_loss": {{strategy.order.price}},
  "take_profit": {{strategy.order.contracts}},
  "timeframe": "{{interval}}",
  "strategy": "{{strategy.name}}",
  "timestamp": "{{time}}",
  "priority": 1,
  "confidence": 0.85,
  "metadata": {
    "position_size": {{strategy.position_size}},
    "equity": {{strategy.equity}},
    "source": "tradingview_strategy"
  }
}
```

### 3. Test Alert

1. După ce salvezi alert-ul în TradingView
2. Verifică în terminal că mesajul a fost primit:
```bash
# Verifică log-ul webhook-ului
tail -f webhook.log

# SAU verifică direct în Telegram
# Ar trebui să primești notificare când alert-ul se activează
```

### 4. Perechi Recomandate pentru Alerts

**Priority 1 (High Probability):**
- GBPUSD
- XAUUSD (Gold)
- BTCUSD
- GBPJPY

**Priority 2 (Medium Probability):**
- EURUSD
- USDJPY
- AUDUSD
- EURJPY

## 🔥 Pine Script Example pentru Auto-Trading

```pinescript
//@version=5
strategy("ForexGod Auto Webhook", overlay=true)

// Strategy logic
fastMA = ta.sma(close, 20)
slowMA = ta.sma(close, 50)

buySignal = ta.crossover(fastMA, slowMA)
sellSignal = ta.crossunder(fastMA, slowMA)

// Calculate SL/TP
atr = ta.atr(14)
stopLoss = buySignal ? close - (atr * 2) : close + (atr * 2)
takeProfit = buySignal ? close + (atr * 3) : close - (atr * 3)

// Execute trades
if buySignal
    strategy.entry("Long", strategy.long)
    alert('{"action":"buy","symbol":"' + syminfo.ticker + '","price":' + str.tostring(close) + ',"stop_loss":' + str.tostring(stopLoss) + ',"take_profit":' + str.tostring(takeProfit) + ',"timeframe":"' + timeframe.period + '","strategy":"ma_cross","timestamp":"' + str.tostring(time) + '","priority":1,"confidence":0.85}', alert.freq_once_per_bar_close)
    
if sellSignal
    strategy.entry("Short", strategy.short)
    alert('{"action":"sell","symbol":"' + syminfo.ticker + '","price":' + str.tostring(close) + ',"stop_loss":' + str.tostring(stopLoss) + ',"take_profit":' + str.tostring(takeProfit) + ',"timeframe":"' + timeframe.period + '","strategy":"ma_cross","timestamp":"' + str.tostring(time) + '","priority":1,"confidence":0.85}', alert.freq_once_per_bar_close)

plot(fastMA, color=color.green, linewidth=2)
plot(slowMA, color=color.red, linewidth=2)
```

## 🎯 Flux Complet

```
TradingView Alert 
    ↓
Webhook (192.168.1.132:5001)
    ↓
AI Validator (70% threshold)
    ↓
Money Manager (2% risk)
    ↓
cTrader Executor (signals.json)
    ↓
PythonSignalExecutor (cTrader bot)
    ↓
Trade Executed + Telegram Notification
```

## ✅ Verificare Setup

```bash
# Test webhook cu curl
curl -X POST http://192.168.1.132:5001/webhook \
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

## 📱 Telegram Notifications

Vei primi notificări automate în:
**🔮 ForexGod - Glitch in Matrix 🧠**

Notificări includ:
- ✅ Signal received & validated
- 💰 Position size & risk
- 📊 Entry, SL, TP levels
- 🎯 R:R ratio
- 📈 Account status după trade

## 🚀 Next Steps

1. ✅ Configurează Alpha Vantage API key (backup)
2. ✅ Testează PythonSignalExecutor în cTrader
3. ✅ Configurează morning scan la 09:00
4. ✅ Deploy TradeHistorySyncer pentru auto-sync

---
**ForexGod Trading AI** - Powered by IC Markets + TradingView 🔥
