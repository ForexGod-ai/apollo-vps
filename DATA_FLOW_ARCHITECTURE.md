# 🔄 GLITCH IN MATRIX - DATA FLOW ARCHITECTURE
## ✨ by ФорексГод ✨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Data:** 2026-02-05  
**Sistem:** Glitch in Matrix Trading System  
**Platformă:** cTrader Desktop + Python 3.14  
**Boți cTrader:** 4 active (MarketDataProvider, PythonSignalExecutor, TradeHistorySyncer, EconomicCalendarHTTP)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 📊 I. SURSA DATELOR - cTrader Desktop (4 Boți C#)

### 🤖 BOT #1: MarketDataProvider_v2.cs
**Rol:** Server HTTP care expune date OHLC live din cTrader

**Ce face:**
```
1. Pornește un HTTP server pe localhost:8000
2. Ascultă requests de la Python
3. Returnează date OHLC (Open, High, Low, Close) pentru orice simbol
4. Folosește API-ul cTrader (Symbol.Bars)
```

**Endpoints:**
- `http://localhost:8000/data?symbol=EURUSD&timeframe=Daily&bars=100`
- `http://localhost:8000/data?symbol=GBPUSD&timeframe=Hour4&bars=200`

**Metoda de Transfer:** **HTTP REST API** (JSON responses)

**Date exportate:**
```json
{
  "symbol": "EURUSD",
  "timeframe": "Daily",
  "bars": [
    {
      "time": "2026-02-05T00:00:00",
      "open": 1.08450,
      "high": 1.08650,
      "low": 1.08350,
      "close": 1.08550,
      "volume": 45000
    }
  ]
}
```

**Status:** ✅ RUNNING permanent (trebuie pornit în cTrader înainte de scan)

---

### 🤖 BOT #2: PythonSignalExecutor.cs (V3.1)
**Rol:** Execută comenzile de trading primite de la Python

**Ce face:**
```
1. Monitorizează fișierul signals.json la fiecare 10 secunde
2. Citește signal-ul (BUY/SELL + preț + SL + TP)
3. Execută ordinul în cTrader LIVE
4. Scrie confirmarea în trade_confirmations.json
5. Exportă pozițiile active în active_positions.json
```

**Metoda de Transfer:** **File-Based Communication** (JSON files)

**Input (Python → cTrader):**
```json
// signals.json
{
  "signal_id": "GBPUSD_20260205_120530",
  "symbol": "GBPUSD",
  "direction": "BUY",
  "entry_price": 1.27500,
  "stop_loss": 1.27200,
  "take_profit": 1.28300,
  "lot_size": 0.05,
  "comment": "V3.0 SCALE_IN - Entry 1 (1H CHoCH)",
  "timestamp": "2026-02-05T12:05:30"
}
```

**Output (cTrader → Python):**
```json
// trade_confirmations.json
{
  "signal_id": "GBPUSD_20260205_120530",
  "ticket": 123456789,
  "status": "EXECUTED",
  "execution_price": 1.27505,
  "execution_time": "2026-02-05T12:05:32",
  "message": "Order executed successfully"
}
```

**Features:**
- ✅ Auto close at profit (100 pips default)
- ✅ Move SL to breakeven (+50 pips)
- ✅ Duplicate signal protection (processed_signals.txt)
- ✅ Real-time position management

**Status:** ✅ RUNNING permanent (monitorizează signals.json 24/7)

---

### 🤖 BOT #3: TradeHistorySyncer.cs
**Rol:** Sincronizează istoric trade-uri + pozițiile LIVE

**Ce face:**
```
1. La fiecare 10 secunde citește:
   - History (toate trade-urile închise)
   - Positions (toate pozițiile deschise)
2. Exportă totul în trade_history.json
3. Calculează balance-ul după fiecare trade (cronologic)
```

**Metoda de Transfer:** **File-Based Sync** (JSON export)

**Output (cTrader → Python):**
```json
// trade_history.json
{
  "account": {
    "number": "1234567",
    "balance": 1257.50,
    "equity": 1312.75,
    "open_pl": 55.25,
    "currency": "USD",
    "last_update": "2026-02-05 13:15:42"
  },
  "open_positions": [
    {
      "ticket": 123456789,
      "symbol": "GBPUSD",
      "direction": "BUY",
      "entry_price": 1.27500,
      "current_price": 1.27650,
      "profit": 55.25,
      "pips": 15.0,
      "open_time": "2026-02-05T12:05:32"
    }
  ],
  "closed_trades": [
    {
      "ticket": 123456788,
      "symbol": "EURUSD",
      "direction": "SELL",
      "entry_price": 1.08550,
      "closing_price": 1.08100,
      "profit": 42.50,
      "pips": 45.0,
      "open_time": "2026-02-04T08:15:20",
      "close_time": "2026-02-04T14:30:45",
      "balance_after": 1202.25
    }
  ]
}
```

**Features:**
- ✅ Sortare cronologică (EntryTime → PositionId)
- ✅ Calculează balance_after pentru fiecare trade închis
- ✅ Include pozițiile LIVE cu P/L curent
- ✅ Metrics de cont (balance, equity, open P/L)

**Status:** ✅ RUNNING permanent (sync la fiecare 10s)

---

### 🤖 BOT #4: EconomicCalendarHTTP.cs
**Rol:** Trimite evenimente economice către Python

**Ce face:**
```
1. Monitorizează calendar economic din cTrader
2. Când apare un eveniment HIGH/MEDIUM impact:
   - Scrie în economic_calendar.json
3. Python citește și trimite alertă pe Telegram
```

**Metoda de Transfer:** **File-Based Events** (JSON append)

**Output:**
```json
// economic_calendar.json
[
  {
    "time": "2026-02-05T14:30:00",
    "currency": "USD",
    "event": "Non-Farm Payrolls",
    "impact": "HIGH",
    "actual": "250K",
    "forecast": "200K"
  }
]
```

**Status:** ✅ RUNNING permanent (monitorizează calendar)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🐍 II. PROCESAREA ÎN PYTHON - Logic Layer

### 📡 A. DATA INGESTION (Preluarea Datelor)

#### 1️⃣ ctrader_cbot_client.py
**Rol:** Client HTTP pentru a comunica cu MarketDataProvider

```python
class CTraderCBotClient:
    def __init__(self):
        self.base_url = "http://localhost:8000"
    
    def get_ohlc(self, symbol: str, timeframe: str, bars: int = 100):
        """Fetch OHLC data from cTrader cBot"""
        response = requests.get(
            f"{self.base_url}/data",
            params={
                "symbol": symbol,
                "timeframe": timeframe,
                "bars": bars
            }
        )
        return response.json()
```

**Folosit de:**
- `daily_scanner.py` - pentru a scana toate perechile
- `setup_executor_monitor.py` - pentru validări în timp real

---

### 📊 B. SCANNING & DETECTION (Găsirea Setup-urilor)

#### 2️⃣ daily_scanner.py
**Rol:** Scanează TOATE perechile zilnic pentru setup-uri SMC

**Flux:**
```
1. Pornește la 00:05 (cron job sau manual)
2. Citește pairs_config.json (lista de perechi)
3. Pentru fiecare pereche:
   a. Fetch DAILY OHLC (100 bars) via ctrader_cbot_client
   b. Fetch 4H OHLC (200 bars)
   c. Rulează SMCDetector.find_setups()
   d. Identifică CHoCH + FVG + Entry zones
4. Filtrează setup-uri HIGH priority
5. Trimite pe Telegram (cu chart snapshot)
6. Scrie în monitoring_setups.json pentru tracking
```

**Input:**
- `pairs_config.json` (lista de 15-20 perechi)
- OHLC data de la `MarketDataProvider` (via HTTP)

**Output:**
```json
// monitoring_setups.json
[
  {
    "symbol": "GBPUSD",
    "direction": "BULLISH",
    "daily_choch": {
      "break_price": 1.27800,
      "direction": "BULLISH",
      "time": "2026-02-03T00:00:00"
    },
    "fvg": {
      "bottom": 1.27450,
      "top": 1.27650
    },
    "entry_price": 1.27500,
    "stop_loss": 1.27200,
    "take_profit": 1.28300,
    "risk_reward": 2.67,
    "priority": "HIGH",
    "status": "MONITORING",
    "setup_time": "2026-02-05T00:05:30",
    "choch_1h_detected": false,
    "choch_4h_detected": false
  }
]
```

**AI Integration:**
```python
# Daily scanner folosește AI scoring ÎNAINTE de a trimite alerte
from ai_probability_analyzer import AIProbabilityAnalyzer
from strategy_optimizer import StrategyOptimizer

# 1. Load learned rules
analyzer = AIProbabilityAnalyzer()  # Încarcă learned_rules.json

# 2. Score fiecare setup
for setup in setups:
    ai_score = analyzer.calculate_probability_score(
        symbol=setup.symbol,
        timeframe='4H',
        hour=datetime.now().hour,
        pattern='ORDER_BLOCK'
    )
    setup.ai_probability_score = ai_score['score']  # 1-10
    setup.ai_probability_confidence = ai_score['confidence']  # LOW/MEDIUM/HIGH
```

**Rezultat:** Setup-urile cu AI score < 5 sunt marcate cu warning în Telegram!

---

### ⚙️ C. EXECUTION MONITORING (Monitorizarea Executării)

#### 3️⃣ setup_executor_monitor.py
**Rol:** Monitorizează setup-urile și le execută când devin READY

**Flux:**
```
1. Rulează în loop la fiecare 30 secunde
2. Citește monitoring_setups.json
3. Pentru fiecare setup în status "MONITORING":
   
   ENTRY 1 (1H CHoCH + Pullback):
   a. Fetch 1H OHLC pentru simbol
   b. Verifică dacă a apărut 1H CHoCH (same direction ca Daily)
   c. Calculează Fibonacci levels (23.6%, 38.2%, 50%, 61.8%)
   d. Verifică dacă prețul a atins Fibo 50% (pullback zone)
   e. Dacă DA → schimbă status la "READY"
   f. Scrie signal în signals.json (50% lot size)
   g. Așteaptă confirmare de la PythonSignalExecutor
   
   ENTRY 2 (4H CHoCH):
   h. Dacă apare 4H CHoCH în 48h → execută Entry 2 (50% lot size)
   
   TIMEOUT HANDLING:
   i. Dacă > 24h fără execuție → skip sau force entry
   
4. Trimite Telegram notification după execuție
5. Actualizează monitoring_setups.json cu noul status
```

**Input:**
- `monitoring_setups.json` (setup-uri găsite de daily_scanner)
- OHLC 1H/4H live (via ctrader_cbot_client)

**Output:**
```json
// signals.json (comandă pentru PythonSignalExecutor)
{
  "signal_id": "GBPUSD_20260205_120530",
  "symbol": "GBPUSD",
  "direction": "BUY",
  "entry_price": 1.27500,
  "stop_loss": 1.27200,
  "take_profit": 1.28300,
  "lot_size": 0.05,
  "comment": "V3.0 SCALE_IN - Entry 1 (1H CHoCH + Pullback 50%)",
  "timestamp": "2026-02-05T12:05:30"
}
```

**Confirmare primită:**
```json
// trade_confirmations.json (de la PythonSignalExecutor)
{
  "signal_id": "GBPUSD_20260205_120530",
  "ticket": 123456789,
  "status": "EXECUTED",
  "execution_price": 1.27505,
  "execution_time": "2026-02-05T12:05:32"
}
```

---

### 📊 D. POSITION MONITORING (Monitorizarea Pozițiilor)

#### 4️⃣ position_monitor.py
**Rol:** Monitorizează pozițiile LIVE și trimite alertă ARMAGEDDON

**Flux:**
```
1. Rulează în loop continuu
2. Citește trade_history.json (sincronizat de TradeHistorySyncer)
3. Verifică secțiunea "open_positions"
4. Când detectează o NOUĂ poziție:
   a. Trimite mesaj ARMAGEDDON pe Telegram (URGENT alert)
   b. Include detalii: simbol, direcție, entry, SL, TP, lot size, profit curent
5. Când detectează o poziție ÎNCHISĂ:
   a. Trimite notificare cu rezultatul (profit/loss)
   b. 🧠 TRIGGER AUTO-LEARNING (subprocess.Popen)
   c. Actualizează .seen_positions.json
```

**Auto-Learning Trigger:**
```python
# position_monitor.py - linia 319
for trade in new_closed:
    self._send_closed_trade_notification(trade)
    
    # 🧠 AUTO-LEARNING: Trigger ML update after every closed trade
    logger.info("🧠 Triggering AUTO-LEARNING system...")
    subprocess.Popen(
        [sys.executable, "trigger_ml_update.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True  # Non-blocking background execution
    )
    logger.success("✅ ML update triggered in background")
```

**Input:**
- `trade_history.json` (sincronizat de TradeHistorySyncer la 10s)
- `.seen_positions.json` (tracking local)

**Output:**
- Telegram notifications (ARMAGEDDON + Closed Trade alerts)
- Trigger pentru `trigger_ml_update.py`

---

### 📈 E. TRADE MONITORING (Monitorizarea Trade-urilor)

#### 5️⃣ trade_monitor.py
**Rol:** Monitorizează trade_history.json pentru TP/SL hits

**Flux:**
```
1. Rulează în loop la 30s
2. Citește trade_history.json
3. Verifică secțiunea "closed_trades"
4. Identifică trade-uri NOI (nu în .last_trade_check.json)
5. Trimite notificare pe Telegram cu:
   - Profit/Loss
   - Pips
   - Balance după trade
   - Account statistics
6. Actualizează .last_trade_check.json
```

**Status:** ✅ RUNNING (tocmai pornit de tine)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🗄️ III. BAZA DE DATE - SQLite (trades.db)

### 📊 A. STRUCTURA DATABASE

```sql
-- trades.db (SQLite)
CREATE TABLE trades (
    ticket INTEGER PRIMARY KEY,
    symbol TEXT,
    direction TEXT,  -- BUY/SELL
    entry_price REAL,
    closing_price REAL,
    lot_size REAL,
    profit REAL,
    pips REAL,
    status TEXT,  -- OPEN/CLOSED
    open_time TEXT,
    close_time TEXT,
    balance_after REAL
);
```

### 🔄 B. POPULAREA DATABASE-ULUI

#### Metoda 1: migrate_to_sqlite.py (One-time Migration)
```python
# Rulat manual pentru a migra din JSON → SQLite
# Citește trade_history.json
# Scrie toate trade-urile în trades.db
```

#### Metoda 2: Real-Time Sync (Via Python monitors)

**Flow:**
```
TradeHistorySyncer.cs (cTrader)
    ↓ (scrie la fiecare 10s)
trade_history.json
    ↓ (citit de)
position_monitor.py / trade_monitor.py
    ↓ (opțional: scrie în)
trades.db (SQLite)
```

**IMPORTANT:** trades.db NU este actualizat LIVE!

**Soluție actuală:**
- TradeHistorySyncer scrie în `trade_history.json` (LIVE sync)
- Python monitoarele citesc `trade_history.json` (real-time)
- `trades.db` este folosit DOAR pentru:
  1. Backup istoric
  2. AI training (strategy_optimizer.py)

**Sincronizare:**
```python
# db_backup.py - rulează periodic (cron sau manual)
import json
import sqlite3

# Citește trade_history.json
with open('trade_history.json') as f:
    data = json.load(f)

# Scrie în trades.db
conn = sqlite3.connect('trades.db')
for trade in data['closed_trades']:
    conn.execute(
        "INSERT OR REPLACE INTO trades VALUES (?, ?, ?, ...)",
        (trade['ticket'], trade['symbol'], ...)
    )
conn.commit()
```

**Frecvență:**
- ⚠️ NU este real-time!
- ✅ Rulează periodic (de ex. zilnic via cron)
- ✅ SAU manual când vrei să antrenezi AI-ul

---

### 📊 C. ACCES LA DATE

**Pentru monitorizare LIVE:**
```python
# Folosește trade_history.json (actualizat la 10s de TradeHistorySyncer)
with open('trade_history.json') as f:
    data = json.load(f)
    open_positions = data['open_positions']
    closed_trades = data['closed_trades']
```

**Pentru AI training:**
```python
# Folosește trades.db (backup static, actualizat periodic)
import sqlite3
conn = sqlite3.connect('trades.db')
trades = pd.read_sql("SELECT * FROM trades WHERE status='CLOSED'", conn)
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🧠 IV. SELF-LEARNING CIRCUIT (Învățarea AI)

### 🔄 A. FLUXUL COMPLET DE ÎNVĂȚARE

```
1. TRADE CLOSED (detectat de position_monitor.py)
    ↓
2. TRIGGER AUTO-LEARNING
   subprocess.Popen([python, "trigger_ml_update.py"])
    ↓
3. trigger_ml_update.py
   - Verifică dacă ultima actualizare a fost recent
   - Dacă NU → rulează strategy_optimizer.py
    ↓
4. strategy_optimizer.py
   - Citește ALL TRADES din trade_history.json
   - Analizează:
     • Profit Factor by Pair
     • Profit Factor by Hour
     • Blackout Periods (ore cu pierderi)
     • Pattern Success Rate
   - Generează learned_rules.json
    ↓
5. learned_rules.json (ACTUALIZAT)
   {
     "last_updated": "2026-02-05T13:15:42",
     "total_trades_analyzed": 116,
     "profit_factor_by_pair": {
       "GBPUSD": {
         "profit_factor": 2.54,
         "win_rate": 62.5,
         "recommendation": "STRONG"
       },
       "NZDUSD": {
         "profit_factor": 0.06,
         "win_rate": 15.38,
         "recommendation": "AVOID"
       }
     },
     "blackout_periods": [
       {
         "hour_start": 10,
         "hour_end": 11,
         "win_rate": 5.56,
         "severity": "HIGH"
       }
     ]
   }
    ↓
6. NEXT SCAN (daily_scanner.py)
   - Încarcă learned_rules.json
   - Folosește AIProbabilityAnalyzer
   - Scorează fiecare setup (1-10)
   - Adaugă AI warning în Telegram dacă score < 5
```

---

### 🧠 B. COMPONENTE AI

#### 1️⃣ strategy_optimizer.py
**Rol:** Antrenează AI-ul pe baza tuturor trade-urilor

**Input:**
- `trade_history.json` (ALL closed trades)

**Analize efectuate:**
```python
1. analyze_profit_factor_by_pair()
   - Separă wins vs losses per simbol
   - Calculează Profit Factor = Gross Profit / Gross Loss
   - Recomandare: STRONG (PF≥1.5), GOOD (1.0-1.5), AVOID (PF<1.0)

2. analyze_profit_factor_by_timeframe()
   - Analizează performanța pe 1H/4H/Daily
   
3. detect_blackout_periods()
   - Identifică orele cu <30% win rate
   - Severity: HIGH (<15% win rate), MEDIUM (15-30%)
   
4. calculate_pattern_success_rate()
   - Analizează CHoCH, FVG, Order Block success
   
5. generate_learned_rules()
   - Compilează toate analizele în learned_rules.json
```

**Output:**
```json
// learned_rules.json
{
  "version": "1.0",
  "last_updated": "2026-02-05T13:15:42.008078",
  "total_trades_analyzed": 116,
  "profit_factor_by_pair": {
    "EURUSD": {
      "profit_factor": "Infinity",
      "win_rate": 100.0,
      "total_trades": 2,
      "recommendation": "STRONG"
    },
    "GBPUSD": {
      "profit_factor": 2.54,
      "win_rate": 62.5,
      "total_trades": 32,
      "recommendation": "STRONG"
    },
    "NZDUSD": {
      "profit_factor": 0.06,
      "win_rate": 15.38,
      "total_trades": 26,
      "recommendation": "AVOID"
    }
  },
  "blackout_periods": [
    {
      "hour_start": 10,
      "hour_end": 11,
      "total_trades": 18,
      "win_rate": 5.56,
      "net_profit": -386.30,
      "severity": "HIGH"
    }
  ],
  "recommendations": {
    "best_pairs": ["EURUSD", "AUDUSD", "GBPUSD", "GBPJPY"],
    "avoid_pairs": ["NZDUSD", "USDCHF", "AUDCAD"],
    "blackout_hours": [10, 11, 13, 16, 17, 20, 21, 23]
  }
}
```

**Frecvență:**
- ✅ AUTOMAT după fiecare closed trade (trigger de position_monitor)
- ✅ Manual prin `python strategy_optimizer.py`

---

#### 2️⃣ ai_probability_analyzer.py
**Rol:** Scorează setup-urile NOI pe baza learned_rules.json

**Input:**
- `learned_rules.json` (generat de strategy_optimizer)
- Setup details (symbol, timeframe, hour, pattern)

**Scoring Logic:**
```python
def calculate_probability_score(self, symbol, timeframe, hour, pattern):
    score = 5  # Start neutral (1-10 scale)
    
    # 1. CHECK PAIR QUALITY
    if symbol in learned_rules['profit_factor_by_pair']:
        pf = learned_rules['profit_factor_by_pair'][symbol]['profit_factor']
        if pf >= 2.0:
            score += 2  # BOOST for strong pairs
        elif pf < 1.0:
            score -= 3  # PENALIZE for weak pairs
    
    # 2. CHECK BLACKOUT HOUR
    if hour in learned_rules['recommendations']['blackout_hours']:
        score -= 2  # PENALIZE dangerous hours
    
    # 3. CHECK SESSION
    if 8 <= hour <= 12:  # LONDON
        score += 1
    elif 13 <= hour <= 17:  # NEW YORK
        score += 1
    
    # Cap score 1-10
    score = max(1, min(10, score))
    
    return {
        'score': score,
        'confidence': 'HIGH' if score >= 8 else 'MEDIUM' if score >= 5 else 'LOW',
        'factors': {
            'pair_quality': 'Excellent' if pf >= 2.0 else 'Poor',
            'hour_quality': 'BLACKOUT' if hour in blackout else 'Safe',
            'session': 'LONDON' or 'NEW_YORK' or 'OVERLAP'
        }
    }
```

**Output:**
```python
{
  'score': 8,  # 1-10 scale
  'confidence': 'VERY HIGH',
  'factors': {
    'pair_quality': 'Excellent (PF: 2.54)',
    'hour_quality': 'Safe zone',
    'session': 'LONDON (optimal)'
  },
  'warning': None
}
```

**Folosit în:**
- `daily_scanner.py` - scorează setup-uri înainte de Telegram alert
- Telegram messages - afișează AI score în mesaje

---

### 🔄 C. SINCRONIZAREA DATELOR

**Întrebarea ta:** "Cum se asigură sistemul că datele de pe desktop sunt sincronizate cu AI?"

**Răspuns:**

```
┌─────────────────────────────────────────────────────────┐
│  DESKTOP (cTrader) → trade_history.json → PYTHON AI    │
└─────────────────────────────────────────────────────────┘

STEP 1: TradeHistorySyncer.cs (la fiecare 10s)
  ├─ Citește History + Positions din cTrader
  ├─ Scrie în trade_history.json
  └─ [SINCRONIZARE CONTINUĂ]

STEP 2: position_monitor.py (detectează closed trade)
  ├─ Citește trade_history.json
  ├─ Detectează "new closed trade"
  └─ Trigger: subprocess.Popen("trigger_ml_update.py")

STEP 3: trigger_ml_update.py
  ├─ Verifică last_ml_update.json (evită duplicate runs)
  └─ Rulează: subprocess.run("strategy_optimizer.py")

STEP 4: strategy_optimizer.py
  ├─ Citește trade_history.json (ALL 116+ trades)
  ├─ Analizează profit factors, blackout hours, patterns
  ├─ Generează learned_rules.json
  └─ Timestamp: "last_updated": "2026-02-05T13:15:42"

STEP 5: daily_scanner.py / setup_executor_monitor.py
  ├─ Încarcă learned_rules.json la fiecare scan
  ├─ Folosește AIProbabilityAnalyzer pentru scoring
  └─ Decizii bazate pe LATEST learned rules
```

**Garanții:**
- ✅ TradeHistorySyncer scrie trade_history.json la **10 secunde**
- ✅ Auto-learning se triggerează **IMEDIAT** după closed trade
- ✅ learned_rules.json are **timestamp** → știi când a fost ultima actualizare
- ✅ Daily scanner **reîncarcă** learned_rules.json la fiecare run

**Verificare:**
```bash
# Check last sync timestamp
cat trade_history.json | jq '.account.last_update'
# Output: "2026-02-05 13:15:42"

# Check last AI training
cat learned_rules.json | jq '.last_updated'
# Output: "2026-02-05T13:15:42.008078"

# Diferența < 1 minut = SINCRONIZAT! ✅
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 📱 V. VIZUALIZAREA FLUXULUI - SCHEMA COMPLETĂ

```
╔══════════════════════════════════════════════════════════════╗
║                  GLITCH IN MATRIX - DATA FLOW                ║
╚══════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: cTrader Desktop (IC Markets - LIVE Data)         │
└─────────────────────────────────────────────────────────────┘

🤖 MarketDataProvider_v2.cs
   ├─ HTTP Server: localhost:8000
   ├─ Expune: OHLC data (Daily, 4H, 1H)
   └─ [HTTP REST API]
        ↓
┌────────────────────┐
│   Python Client    │  ctrader_cbot_client.py
│ requests.get(...)  │  ← Fetch OHLC pentru scanning
└────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2: Python Logic - Scanning & Detection              │
└─────────────────────────────────────────────────────────────┘

📊 daily_scanner.py (00:05 zilnic)
   ├─ Input: pairs_config.json (15 perechi)
   ├─ Fetch: OHLC via HTTP (MarketDataProvider)
   ├─ Procesare: SMCDetector.find_setups()
   ├─ AI Scoring: AIProbabilityAnalyzer (1-10)
   │   └─ Citește: learned_rules.json (116 trades)
   ├─ Output: monitoring_setups.json
   └─ Telegram: Alertă setup-uri HIGH priority
        ↓
┌────────────────────┐
│ monitoring_setups  │  [FILE STORAGE]
│    .json           │  Setup-uri detectate (status: MONITORING)
└────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3: Python Logic - Execution Monitoring              │
└─────────────────────────────────────────────────────────────┘

⚙️ setup_executor_monitor.py (loop 30s)
   ├─ Citește: monitoring_setups.json
   ├─ Fetch: 1H/4H OHLC LIVE (via HTTP)
   ├─ Validare: 1H CHoCH + Pullback la Fibo 50%
   ├─ Dacă READY:
   │   ├─ Scrie: signals.json (comandă pentru cTrader)
   │   └─ Actualizează: monitoring_setups.json (status → READY)
   └─ Telegram: Notificare execuție
        ↓
┌────────────────────┐
│   signals.json     │  [FILE COMMUNICATION]
└────────────────────┘  Comandă trading pentru cTrader
        ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 4: cTrader Execution Bot                            │
└─────────────────────────────────────────────────────────────┘

🤖 PythonSignalExecutor.cs (loop 10s)
   ├─ Citește: signals.json
   ├─ Validare: Not duplicate (processed_signals.txt)
   ├─ Execută: BUY/SELL în cTrader LIVE
   ├─ Confirmă: trade_confirmations.json
   └─ Exportă: active_positions.json (pozițiile LIVE)
        ↓
┌────────────────────┐
│ trade_confirmations│  [EXECUTION FEEDBACK]
│    .json           │  Status: EXECUTED / FAILED
└────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 5: cTrader History Sync                             │
└─────────────────────────────────────────────────────────────┘

🤖 TradeHistorySyncer.cs (loop 10s)
   ├─ Citește: History (ALL closed trades)
   ├─ Citește: Positions (ALL open positions)
   ├─ Calculează: balance_after pentru fiecare trade
   ├─ Exportă: trade_history.json
   └─ Include: account metrics (balance, equity, open P/L)
        ↓
┌────────────────────┐
│  trade_history     │  [MASTER DATA SOURCE]
│    .json           │  ALL trades + open positions
└────────────────────┘
        ↓
        ├──────────────────────────────────┐
        │                                  │
┌───────▼──────────┐            ┌─────────▼────────┐
│ position_monitor │            │ trade_monitor    │
│    .py           │            │    .py           │
├──────────────────┤            ├──────────────────┤
│ Detectează:      │            │ Detectează:      │
│ - NEW positions  │            │ - Closed trades  │
│ - CLOSED trades  │            │ - TP/SL hits     │
├──────────────────┤            ├──────────────────┤
│ Acțiuni:         │            │ Acțiuni:         │
│ - Telegram alert │            │ - Telegram alert │
│ - 🧠 AUTO-LEARN  │            │ - Account stats  │
└──────┬───────────┘            └──────────────────┘
       │
       │ subprocess.Popen("trigger_ml_update.py")
       ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 6: AI Self-Learning Circuit                         │
└─────────────────────────────────────────────────────────────┘

🧠 trigger_ml_update.py
   ├─ Verifică: last_ml_update.json (evită duplicates)
   └─ Rulează: subprocess.run("strategy_optimizer.py")
        ↓
🧠 strategy_optimizer.py
   ├─ Input: trade_history.json (116+ trades)
   ├─ Analizează:
   │   ├─ Profit Factor by Pair (GBPUSD: 2.54, NZDUSD: 0.06)
   │   ├─ Profit Factor by Hour (10:00 = 5.6% win rate)
   │   ├─ Blackout Periods (9 ore periculoase)
   │   └─ Pattern Success Rate
   ├─ Output: learned_rules.json
   └─ Timestamp: last_updated
        ↓
┌────────────────────┐
│  learned_rules     │  [AI KNOWLEDGE BASE]
│    .json           │  116 trades analyzed, PF 2.11x
└────────────────────┘
        ↓ (încărcat de)
┌─────────────────────────────────────────────────────────────┐
│  LAYER 7: AI Scoring & Feedback Loop                       │
└─────────────────────────────────────────────────────────────┘

🧠 ai_probability_analyzer.py
   ├─ Încarcă: learned_rules.json
   ├─ Scorează: Fiecare setup nou (1-10)
   ├─ Factori:
   │   ├─ Pair Quality (PF ≥ 2.0 → +2, PF < 1.0 → -3)
   │   ├─ Hour Quality (Blackout → -2)
   │   └─ Session Quality (LONDON/NY → +1)
   └─ Output: AI score + confidence + factors
        ↓ (folosit de)
📊 daily_scanner.py
   ├─ Adaugă AI score la fiecare setup
   └─ Warning în Telegram dacă score < 5
        ↓
📱 Telegram Alert
   ├─ "🧠 AI PROBABILITY: 8/10 (VERY HIGH)"
   ├─ "🟩🟩🟩🟩🟩🟩🟩🟩⬜⬜"
   └─ "✅ Pair Quality: Excellent (PF 2.54)"

╔══════════════════════════════════════════════════════════════╗
║            🔄 CONTINUOUS LEARNING LOOP 🔄                    ║
╠══════════════════════════════════════════════════════════════╣
║  Trade Closed → Auto-Learn → Update Rules → Better Scores   ║
║         ↑________________________________________↓           ║
║                   INFINITE IMPROVEMENT                       ║
╚══════════════════════════════════════════════════════════════╝
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🔧 VI. TROUBLESHOOTING - VERIFICĂRI PER BOT

### ✅ Verificare Generală

```bash
# Check dacă toate monitoarele Python rulează
ps aux | grep -E "(daily_scanner|setup_executor|position_monitor|trade_monitor)" | grep -v grep

# Check dacă boții cTrader scriu fișiere
ls -lt *.json | head -5

# Check sincronizare
date && cat trade_history.json | jq '.account.last_update'
```

---

### 🤖 BOT #1: MarketDataProvider

**Simptom:** `daily_scanner.py` NU poate fetch OHLC

**Verificări:**
```bash
# 1. Check dacă botul rulează în cTrader
#    → Uită-te în cTrader → cBots → MarketDataProvider → Status: RUNNING

# 2. Test HTTP endpoint
curl "http://localhost:8000/data?symbol=EURUSD&timeframe=Daily&bars=5"

# Expected output:
# {
#   "symbol": "EURUSD",
#   "timeframe": "Daily",
#   "bars": [...]
# }

# 3. Verifică log-uri în cTrader
#    → cBots → MarketDataProvider → Log
#    → Caută: "HTTP Server started on port 8000"
```

**Fix:**
1. Restart MarketDataProvider în cTrader
2. Verifică că portul 8000 nu e ocupat: `lsof -i :8000`
3. Restart cTrader dacă e necesar

---

### 🤖 BOT #2: PythonSignalExecutor

**Simptom:** signals.json NU se execută

**Verificări:**
```bash
# 1. Check dacă botul rulează
#    → cTrader → cBots → PythonSignalExecutor → Status: RUNNING

# 2. Check path-ul corect
#    → Parametri → Signal File Path → Trebuie să fie:
#    /Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/signals.json

# 3. Test manual
echo '{
  "signal_id": "TEST_123",
  "symbol": "EURUSD",
  "direction": "BUY",
  "entry_price": 1.08500,
  "stop_loss": 1.08200,
  "take_profit": 1.09300,
  "lot_size": 0.01,
  "comment": "TEST",
  "timestamp": "2026-02-05T13:00:00"
}' > signals.json

# 4. Verifică processed_signals.txt
#    → Dacă signal_id e deja în listă → SKIP (nu execută)

# 5. Check log cTrader
#    → Caută: "✅ Signal deserialized: TEST_123"
#    → Sau: "❌ Failed to deserialize signal"
```

**Fix:**
1. Verifică path-ul (cu spațiu: "Glitch in Matrix")
2. Șterge processed_signals.txt pentru retry
3. Restart PythonSignalExecutor

---

### 🤖 BOT #3: TradeHistorySyncer

**Simptom:** trade_history.json NU se actualizează

**Verificări:**
```bash
# 1. Check timestamp
cat trade_history.json | jq '.account.last_update'
# Trebuie să fie < 10 secunde în urmă!

# 2. Check dacă botul rulează
#    → cTrader → cBots → TradeHistorySyncer → Status: RUNNING

# 3. Check path-ul
#    → Parametri → JSON File Path → Trebuie să fie:
#    /Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/trade_history.json

# 4. Check log cTrader
#    → Caută: "🔍 SYNCING TRADE HISTORY"
#    → Frecvență: la fiecare 10 secunde
```

**Fix:**
1. Restart TradeHistorySyncer
2. Verifică că path-ul e corect (cu spațiu)
3. Check permissions: `ls -l trade_history.json` (trebuie să fie writable)

---

### 🤖 BOT #4: EconomicCalendarHTTP

**Simptom:** NU primești alertele de news

**Verificări:**
```bash
# 1. Check dacă botul rulează
#    → cTrader → cBots → EconomicCalendarHTTP → Status: RUNNING

# 2. Check economic_calendar.json
cat economic_calendar.json | jq '.[-5:]'  # Ultimele 5 evenimente

# 3. Check log cTrader
#    → Caută evenimente HIGH/MEDIUM impact
```

**Fix:**
1. Restart EconomicCalendarHTTP
2. Verifică path-ul

---

### 🐍 PYTHON MONITORS

**Simptom:** Monitoarele NU rulează

**Verificări:**
```bash
# Check procese active
ps aux | grep -E "(setup_executor|position_monitor|trade_monitor)" | grep -v grep

# Check log-uri
tail -50 setup_executor_monitor.log
tail -50 position_monitor.log
tail -50 trade_monitor.log

# Check erori
grep -i "error\|exception" *.log | tail -20
```

**Fix:**
```bash
# Restart monitoare
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

# Setup Executor
nohup .venv/bin/python setup_executor_monitor.py --loop --interval 30 > setup_executor_monitor.log 2>&1 &

# Position Monitor
nohup .venv/bin/python position_monitor.py --loop > position_monitor.log 2>&1 &

# Trade Monitor
nohup .venv/bin/python trade_monitor.py --loop > trade_monitor.log 2>&1 &
```

---

### 🧠 AI LEARNING

**Simptom:** AI scores NU se actualizează

**Verificări:**
```bash
# 1. Check learned_rules.json timestamp
cat learned_rules.json | jq '.last_updated'
# Trebuie să fie recent (< 1h de la ultimul closed trade)

# 2. Check last_ml_update.json
cat last_ml_update.json | jq '.'

# 3. Test manual AI training
.venv/bin/python strategy_optimizer.py

# 4. Test AI scoring
.venv/bin/python ai_probability_analyzer.py
```

**Fix:**
1. Rulează manual strategy_optimizer.py
2. Verifică că trade_history.json are date
3. Restart position_monitor (pentru auto-trigger)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 📋 VII. CHECKLIST ZILNIC - HEALTH CHECK

```bash
┌─────────────────────────────────────────────────────────┐
│         GLITCH IN MATRIX - DAILY HEALTH CHECK           │
└─────────────────────────────────────────────────────────┘

📅 Data: 2026-02-05
⏰ Ora: 13:30 UTC

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 cTrader Bots (4/4 ACTIVE):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ MarketDataProvider_v2.cs      → HTTP Server (localhost:8000)
✅ PythonSignalExecutor.cs       → Execută comenzi (signals.json)
✅ TradeHistorySyncer.cs         → Sync trade_history.json (10s)
✅ EconomicCalendarHTTP.cs       → Calendar economic

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🐍 Python Monitors (3/3 ACTIVE):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ setup_executor_monitor.py     → PID 30206 (6h 24min uptime)
✅ position_monitor.py           → PID 28613 (17min uptime)
✅ trade_monitor.py              → PID 56594 (TOCMAI PORNIT)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Data Sync Status:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ trade_history.json            → Last update: 13:15:42 (< 1min)
✅ monitoring_setups.json        → 3 active setups
✅ signals.json                  → Empty (no pending signals)
✅ learned_rules.json            → 116 trades, last: 13:15:42

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🧠 AI Status:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Learned Rules:                → 116 trades analyzed
✅ Best Pairs:                   → EURUSD, GBPUSD, GBPJPY
✅ Avoid Pairs:                  → NZDUSD, USDCHF
✅ Blackout Hours:               → 10, 11, 13, 16, 17, 20, 21, 23
✅ Global Profit Factor:         → 2.11x (EXCELENT!)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 Account Status:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Balance:    $1,257.50
Equity:     $1,312.75
Open P/L:   +$55.25
Open Pos:   1 (GBPUSD BUY)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 System Health: ✅ ALL GREEN
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🎯 VIII. CONCLUZIE - MECANISMUL COMPLET

### 📡 Metode de Transfer Date:

1. **HTTP REST API** - MarketDataProvider → Python
   - Port: localhost:8000
   - Format: JSON
   - Frecvență: On-demand (când Python face request)

2. **File-Based Communication** - Bidirectional
   - Python → cTrader: `signals.json`
   - cTrader → Python: `trade_confirmations.json`, `active_positions.json`, `trade_history.json`
   - Format: JSON
   - Frecvență: 10-30 secunde

3. **Database** - SQLite (optional backup)
   - `trades.db` - backup istoric
   - NU este real-time!
   - Actualizat periodic prin `db_backup.py`

### 🔄 Fluxul Complet Simplificat:

```
cTrader Desktop (IC Markets LIVE)
    ↓ [HTTP + Files]
Python Logic (Scanning + Execution + Monitoring)
    ↓ [Auto-Learning Trigger]
AI Training (strategy_optimizer.py)
    ↓ [learned_rules.json]
AI Scoring (ai_probability_analyzer.py)
    ↓ [Better Setup Filtering]
Telegram Alerts (Setup notifications + AI scores)
```

### ✅ Ce să verifici dacă un bot nu comunică:

1. **MarketDataProvider NU răspunde:**
   - `curl http://localhost:8000/data?symbol=EURUSD&timeframe=Daily&bars=5`
   - Fix: Restart bot în cTrader

2. **PythonSignalExecutor NU execută:**
   - Check path: `/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/signals.json`
   - Check `processed_signals.txt` (șterge pentru retry)
   - Fix: Restart bot

3. **TradeHistorySyncer NU sincronizează:**
   - Check timestamp: `cat trade_history.json | jq '.account.last_update'`
   - Trebuie < 10 secunde!
   - Fix: Restart bot

4. **AI NU învață:**
   - Check `learned_rules.json` timestamp
   - Rulează manual: `python strategy_optimizer.py`
   - Verifică position_monitor (auto-trigger)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✨ Glitch in Matrix by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money • 🚀 Automated
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Autor:** Claude Sonnet 4.5 + ФорексГод  
**Data:** 2026-02-05  
**Status:** ✅ COMPLETE - SISTEM FULLY DOCUMENTED
