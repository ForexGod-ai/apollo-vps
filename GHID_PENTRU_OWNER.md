# 🎯 GHID SIMPLU - Trading AI Agent pentru ICMarkets

## CE AI CONSTRUIT (explicat simplu):

Ai un **robot inteligent** care:
1. **Primește alerte** de la TradingView (când apare un semnal bun)
2. **AI verifică** dacă semnalul chiar merită
3. **Calculează automat** câți loți să tranzacționezi (based on risc 2%)
4. **Trimite ordinul** la MetaTrader 5 (la contul tău de ICMarkets)

---

## 📋 PAȘI PENTRU CONFIGURARE:

### STEP 1: Deschide MetaTrader 5
- Conectează-te la contul tău de ICMarkets
- Notează-ți aceste 3 lucruri:
  - **Account Number** (ex: 12345678)
  - **Password** (parola contului)
  - **Server** (ex: "ICMarketsSC-Demo" sau "ICMarketsSC-Live01")

### STEP 2: Editează fișierul `.env`
Deschide: `c:\Users\admog\Desktop\siteRazvan\trading-ai-agent\.env`

Găsește secțiunea **MT5 Configuration** și completează:

```env
# MT5 Configuration - ICMarkets
MT5_LOGIN=12345678                    # Numărul contului tău
MT5_PASSWORD=parola_ta_aici          # Parola de la MT5
MT5_SERVER=ICMarketsSC-Demo          # Serverul (îl vezi în MT5)
```

**IMPORTANT:** 
- Dacă ai cont DEMO → Server = `ICMarketsSC-Demo`
- Dacă ai cont LIVE → Server = `ICMarketsSC-Live01` (sau similar, vezi în MT5)

### STEP 3: Configurează riscul
În același fișier `.env`:

```env
# Trading Configuration
DEFAULT_BROKER=MT5                    # Folosim MetaTrader 5
RISK_PER_TRADE=0.02                  # 2% risc per trade (recomandabil)
MAX_POSITIONS=3                      # Max 3 poziții simultane
ACCOUNT_BALANCE=10000                # Balance-ul tău (actualizează!)

# Cu levier 1:500, risc 2% înseamnă:
# Pe $10,000 → riști $200 per trade
# Pe $5,000 → riști $100 per trade
```

### STEP 4: Pornește robotul

Deschide **PowerShell** în folderul `trading-ai-agent` și rulează:

```powershell
python webhook_server.py
```

Ar trebui să vezi:
```
✅ MT5 conectat cu succes
💰 Money Manager inițializat: Balance=$10000.0, Risk=2.0%
🤖 Inițializare model AI de bază
🚀 Trading AI Agent Webhook Server
📡 Server pornit pe http://0.0.0.0:5001
```

---

## 🎮 CUM ÎL FOLOSEȘTI:

### OPȚIUNEA A: Manual (testare)

1. Deschide browser: **http://127.0.0.1:5001**
2. Vezi dashboard-ul cu statistici
3. Modifică JSON-ul și click "🚀 Trimite Semnal"
4. Vezi ordinul executat în MT5!

### OPȚIUNEA B: Automat cu TradingView (RECOMANDAT)

#### 1. Creează o alertă în TradingView:
- Deschide un chart (ex: EURUSD)
- Click pe ceas ⏰ (Alerts)
- Setează condiții (ex: "RSI crosses above 30")

#### 2. În secțiunea "Webhook URL":
```
http://IP_CALCULATOR_TAU:5001/webhook
```

**Cum afli IP-ul?** În PowerShell: `ipconfig` → caută "IPv4 Address"

#### 3. În "Message" (copiază asta):
```json
{
  "action": "buy",
  "symbol": "{{ticker}}",
  "price": {{close}},
  "stop_loss": {{close}} * 0.997,
  "take_profit": {{close}} * 1.006,
  "timeframe": "{{interval}}",
  "strategy": "tradingview_rsi",
  "metadata": {
    "rsi": 30,
    "volume": {{volume}}
  }
}
```

#### 4. Save Alert!

**Ce se întâmplă:**
- TradingView detectează condiția → trimite alerta
- AI-ul tău primește semnalul → verifică
- Dacă e OK → calculează loturi → execută în MT5
- Vezi totul live în dashboard!

---

## ⚙️ PERSONALIZĂRI IMPORTANTE:

### Risc Management (editează `.env`):

```env
RISK_PER_TRADE=0.02        # 2% per trade (conservator)
                           # 0.01 = 1% (foarte sigur)
                           # 0.03 = 3% (agresiv)

MAX_POSITIONS=3            # Câte tradeuri simultane
                           # 2 = mai puține, mai sigure
                           # 5 = mai multe, mai riscant
```

### AI Validation (cât de strict e AI-ul):

```env
AI_MIN_CONFIDENCE=0.7      # 70% confidence = echilibrat
                           # 0.5 = mai multe tradeuri (mai puține verificări)
                           # 0.9 = doar tradeuri super sigure (puține dar bune)
```

---

## 🔥 EXEMPLE PRACTICE:

### Exemplu 1: Trade Manual
```json
{
  "action": "buy",
  "symbol": "EURUSD",
  "price": 1.0850,
  "stop_loss": 1.0820,
  "take_profit": 1.0920,
  "timeframe": "1h",
  "strategy": "manual_test"
}
```

**Ce se întâmplă:**
1. AI verifică: RSI OK? MACD OK? Risk:Reward OK?
2. Money Manager: Ai $10k, risc 2% = $200, SL = 30 pips → **0.67 loți**
3. MT5 execută: **BUY 0.67 EURUSD @ 1.0850**
4. SL: 1.0820 | TP: 1.0920

### Exemplu 2: Cu Levier 1:500
```
Balance: $10,000
Risc per trade: 2% = $200
Levier: 1:500

Trade EURUSD:
- 1 lot = $100,000
- Cu levier 1:500 → necesari $200 margin
- Poți deschide: $10,000 / $200 = 50 loți MAXIM

Robotul calculează automat:
- SL = 30 pips → riști $200
- Position size = 0.67 loți (safe!)
```

---

## 🛡️ SIGURANȚĂ:

### Reguli automate de protecție:

1. **Daily Loss Limit**: Max 5% pierdere pe zi ($500)
   - După pierdere de $500 → STOP automat

2. **Max Drawdown**: Max 20% pierdere totală ($2,000)
   - După pierdere de $2,000 → STOP automat

3. **Max Positions**: Max 3 poziții deschise
   - Nu deschide al 4-lea trade

4. **AI Filter**: Respinge tradeuri cu confidence < 70%

---

## 📊 MONITORIZARE:

### Dashboard Live:
- **Total semnale primite**
- **Executate cu succes**
- **Success rate** (%)
- **Poziții deschise**
- **Profit/Loss**

### Log Files:
Toate tradeurile sunt salvate în: `trading_agent.log`

---

## ❓ TROUBLESHOOTING:

### Problema: "MT5 initialize() failed"
**Soluție:** 
1. Verifică dacă MT5 e deschis și conectat
2. Verifică datele din `.env` (login, password, server)
3. În MT5: Tools → Options → Expert Advisors → Allow automated trading ✅

### Problema: "No active broker"
**Soluție:** 
- În `.env` setează: `DEFAULT_BROKER=MT5`

### Problema: Ordinele nu apar în MT5
**Soluție:**
1. MT5 → Tools → Options → Expert Advisors
2. ✅ Allow automated trading
3. ✅ Allow DLL imports
4. Restart MT5

---

## 🚀 NEXT STEPS:

1. **Testează pe DEMO** prima săptămână
2. **Monitorizează** success rate-ul
3. **Ajustează** AI_MIN_CONFIDENCE după performanță
4. Când ești sigur → **Treci pe LIVE**

---

## 💡 TIPS & TRICKS:

### Tip 1: Backtesting
Rulează teste cu date istorice pentru a vedea cum ar fi performat:
```powershell
python test_signals.py --days 30
```

### Tip 2: Paper Trading
Păstrează `DEFAULT_BROKER=DEMO` și testează strategii noi fără risc.

### Tip 3: Multi-Timeframe
Creează alerte separate pentru:
- M15 (scalping)
- H1 (day trading)
- H4 (swing trading)

### Tip 4: Pair Diversification
Configurează alerte pentru:
- EURUSD, GBPUSD, USDJPY (majors)
- XAUUSD (gold)
- NAS100, US30 (indices)

---

## 📞 COMENZI RAPIDE:

### Pornește robotul:
```powershell
cd c:\Users\admog\Desktop\siteRazvan\trading-ai-agent
python webhook_server.py
```

### Oprește robotul:
`CTRL + C` în terminal

### Vezi dashboard:
Browser: `http://127.0.0.1:5001`

### Test rapid:
```powershell
curl -X POST http://127.0.0.1:5001/test
```

---

## 🎯 REZUMAT:

| Ce face | Cum | Unde |
|---------|-----|------|
| Primește alerte | TradingView webhook | Port 5001 |
| Validează AI | Machine Learning | ai_validator.py |
| Calculează loturi | 2% risk management | money_manager.py |
| Execută tradeuri | MetaTrader 5 API | broker_manager.py |
| Monitorizare | Dashboard web | http://127.0.0.1:5001 |

---

**Succes la trading! 🚀💰**

*P.S.: Întotdeauna testează pe DEMO înainte de LIVE!*
