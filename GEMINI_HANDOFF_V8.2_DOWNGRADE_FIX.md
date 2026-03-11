# 🧠 GEMINI HANDOFF — V8.2 DOWNGRADE SPAM FIX
## Glitch in Matrix • Institutional Trading AI System
### Document generat: 7 Martie 2026 | Autor: Claude (Copilot Agent)

---

## 📋 CONTEXT — CE S-A ÎNTÂMPLAT

Userul (ФорексГод) primea pe Telegram alerte repetate de tip:
```
⚠️ XAUUSD - SETUP DOWNGRADED
Status: Monitor Closely → Wait For Confirmation
• Confidence: 0%
• Setup: Error
```

Aceste alerte erau **FALSE** — nu reflectau o schimbare reală de piață, ci o eroare de date API.

---

## 🔍 ANALIZA ROOT CAUSE — LANȚUL COMPLET

### Lanțul de execuție:
```
realtime_monitor.py  →  _check_symbol(symbol)
        ↓
spatiotemporal_analyzer.py  →  analyze_4h_setup()
        ↓
    get_4h_data(1200)  →  ctrader_cbot_client.py  →  get_historical_data()
        ↓
    HTTP GET http://localhost:8767/data?symbol=XAUUSD&timeframe=H4&bars=1200
        ↓
    cBot C# Server  →  HTTP 500: "Asset 'XAU' not found. (Parameter 'assetName')"
```

### Simbolurile afectate (din log-uri reale):
| Simbol | Eroare cBot API | Frecvență |
|--------|----------------|-----------|
| XAUUSD | `Asset 'XAU' not found` | 4 apariții |
| USDCAD | `Asset 'USD' not found` | 4 apariții |
| USDCHF | `Symbol USDCHF not found` | 2 apariții |
| AUDUSD | `Symbol AUDUSD not found` | 4 apariții |
| AUDJPY | `Symbol AUDJPY not found` | 2 apariții |

### Cauza exactă — 4 pași:

**Pasul 1:** `analyze_4h_setup()` cerea date: `self.get_4h_data(1200)`

**Pasul 2:** cBot-ul la localhost:8767 returna HTTP 500 (simbol necunoscut) → `get_4h_data()` returna `None`

**Pasul 3:** `analyze_4h_setup()` intra pe branch-ul de fail:
```python
# spatiotemporal_analyzer.py, linia 314 (ÎNAINTE DE FIX)
if df_4h is None or len(df_4h) < 10:
    return MarketNarrative(
        setup_status="error",      # ← PROBLEMA #1: "error" nu e un status valid
        confidence=0.0,            # ← PROBLEMA #2: 0% confidence e misleading
        notes="Insufficient data"
    )
```

**Pasul 4:** `MarketNarrative.recommendation` property mapea `"error"` pe fallback:
```python
# spatiotemporal_analyzer.py, linia 68-76 (ÎNAINTE DE FIX)
@property
def recommendation(self) -> str:
    if self.setup_status == "ready_to_trade":
        return "ready_to_trade"
    elif self.setup_status == "monitoring_closely":
        return "monitor_closely"
    else:
        return "wait_for_confirmation"  # ← "error" cădea AICI
```

**Pasul 5:** `realtime_monitor.py` → `_handle_state_change()` interpreta tranziția:
```python
# realtime_monitor.py, linia 186 (ÎNAINTE DE FIX)
elif new_state == 'wait_for_confirmation' and old_state in ['monitor_closely', 'ready_to_trade']:
    # ⚠️ Downgrade - setup degraded
    self._send_downgrade_alert(symbol, old_state, new_state, narrative)
```

**Rezultat:** Eroare API → `setup_status="error"` → `recommendation="wait_for_confirmation"` → `monitor_closely → wait_for_confirmation` = **FAKE DOWNGRADE** trimis pe Telegram cu Confidence: 0%.

---

## 🛠️ CE S-A EDITAT — 2 FIȘIERE, 6 MODIFICĂRI

### FIȘIER 1: `spatiotemporal_analyzer.py`

#### Modificarea 1 — `setup_status` la erori de date (linia ~314-332)

**ÎNAINTE:**
```python
if df_4h is None or len(df_4h) < 10:
    logger.error(f"❌ Insufficient data for {self.symbol}")
    return MarketNarrative(
        ...
        setup_status="error",
        confidence=0.0,
        notes="Insufficient data"
    )
```

**DUPĂ:**
```python
if df_4h is None or len(df_4h) < 10:
    logger.error(f"❌ Insufficient data for {self.symbol}")
    return MarketNarrative(
        ...
        setup_status="data_unavailable",
        confidence=0.0,
        notes="Insufficient data - cBot may not support this symbol"
    )
```

**De ce:** `"data_unavailable"` e un status distinct care permite downstream code să diferențieze între "piața s-a schimbat" și "API-ul nu funcționează".

---

#### Modificarea 2 — `recommendation` property (linia ~68-79)

**ÎNAINTE:**
```python
@property
def recommendation(self) -> str:
    if self.setup_status == "ready_to_trade":
        return "ready_to_trade"
    elif self.setup_status == "monitoring_closely":
        return "monitor_closely"
    else:
        return "wait_for_confirmation"
```

**DUPĂ:**
```python
@property
def recommendation(self) -> str:
    if self.setup_status == "ready_to_trade":
        return "ready_to_trade"
    elif self.setup_status == "monitoring_closely":
        return "monitor_closely"
    elif self.setup_status == "data_unavailable":
        return "data_unavailable"
    else:
        return "wait_for_confirmation"
```

**De ce:** `"data_unavailable"` acum NU mai cade pe `else → "wait_for_confirmation"`, deci nu mai triggereaza DOWNGRADE.

---

### FIȘIER 2: `realtime_monitor.py`

#### Modificarea 3 — `__init__` — noi trackere pentru spam protection (linia ~55-65)

**ADĂUGAT (V8.2):**
```python
# V8.2: Downgrade spam protection
self.downgrade_cooldown: Dict[str, datetime] = {}   # symbol → last downgrade time
self.data_error_counts: Dict[str, int] = {}          # symbol → consecutive data errors
self.DOWNGRADE_COOLDOWN_HOURS = 24                    # Max 1 downgrade alert per symbol per 24h
self.MAX_DATA_ERRORS_BEFORE_ALERT = 3                 # Only alert after 3 consecutive data failures

# Initialize analyzers
for symbol in symbols:
    self.analyzers[symbol] = SpatioTemporalAnalyzer(symbol)
    self.last_recommendations[symbol] = 'unknown'
    self.data_error_counts[symbol] = 0
```

---

#### Modificarea 4 — `_check_symbol()` — izolare completă a erorilor de date (linia ~127-185)

**ÎNAINTE:**
```python
def _check_symbol(self, symbol: str):
    """Check un simbol și detectează schimbări în narrativ"""
    try:
        analyzer = self.analyzers[symbol]
        narrative = analyzer.analyze_market()
        
        if not narrative or not hasattr(narrative, 'recommendation'):
            return
        
        # Store narrative
        self.last_narratives[symbol] = narrative
        
        # Check for state changes
        previous_rec = self.last_recommendations[symbol]
        current_rec = narrative.recommendation
        
        if current_rec != previous_rec:
            self._handle_state_change(symbol, previous_rec, current_rec, narrative)
        
        self.last_recommendations[symbol] = current_rec
    except Exception as e:
        logger.error(f"❌ Error analyzing {symbol}: {e}")
```

**DUPĂ (V8.2):**
```python
def _check_symbol(self, symbol: str):
    """
    Check un simbol și detectează schimbări în narrativ
    V8.2: Data error isolation — nu mai triggerează DOWNGRADE pe erori de date
    """
    try:
        analyzer = self.analyzers[symbol]
        narrative = analyzer.analyze_market()
        
        if not narrative or not hasattr(narrative, 'recommendation'):
            return
        
        # V8.2: ISOLATE DATA ERRORS — don't let API failures trigger fake downgrades
        if narrative.setup_status == 'data_unavailable':
            self.data_error_counts[symbol] = self.data_error_counts.get(symbol, 0) + 1
            count = self.data_error_counts[symbol]
            logger.warning(f"⚠️ {symbol}: Data unavailable (consecutive: {count}/{self.MAX_DATA_ERRORS_BEFORE_ALERT})")
            
            # Only send ONE alert after N consecutive failures, then silence
            if count == self.MAX_DATA_ERRORS_BEFORE_ALERT:
                self._send_data_error_alert(symbol, count)
            
            # CRITICAL: Do NOT update last_recommendations — keep previous valid state
            return
        
        # Data is valid — reset error counter
        self.data_error_counts[symbol] = 0
        
        # Store narrative
        self.last_narratives[symbol] = narrative
        
        # Check for state changes
        previous_rec = self.last_recommendations[symbol]
        current_rec = narrative.recommendation
        
        if current_rec != previous_rec:
            self._handle_state_change(symbol, previous_rec, current_rec, narrative)
        else:
            logger.info(f"   Status: {current_rec.upper()}")
            if narrative.waiting_for:
                logger.info(f"   Waiting: {', '.join(narrative.waiting_for[:2])}")
        
        self.last_recommendations[symbol] = current_rec
    except Exception as e:
        logger.error(f"❌ Error analyzing {symbol}: {e}", exc_info=False)
```

**Logica cheie:** Când `setup_status == 'data_unavailable'`:
1. NU actualizează `self.last_recommendations[symbol]` → starea anterioară (ex: `monitor_closely`) rămâne intactă
2. Numără erorile consecutive → trimite UN singur alert la a 3-a eroare consecutivă
3. Face `return` înainte de `_handle_state_change()` → ZERO fake downgrades

---

#### Modificarea 5 — `_handle_state_change()` — cooldown 24h pe downgrades (linia ~196-218)

**ÎNAINTE:**
```python
elif new_state == 'wait_for_confirmation' and old_state in ['monitor_closely', 'ready_to_trade']:
    self._send_downgrade_alert(symbol, old_state, new_state, narrative)
```

**DUPĂ (V8.2):**
```python
elif new_state == 'wait_for_confirmation' and old_state in ['monitor_closely', 'ready_to_trade']:
    # V8.2: Cooldown — max 1 downgrade per symbol per 24h
    last_downgrade = self.downgrade_cooldown.get(symbol)
    if last_downgrade and (datetime.now() - last_downgrade).total_seconds() < self.DOWNGRADE_COOLDOWN_HOURS * 3600:
        hours_ago = (datetime.now() - last_downgrade).total_seconds() / 3600
        logger.info(f"   ⏸️ Downgrade alert suppressed for {symbol} (cooldown: sent {hours_ago:.1f}h ago)")
    else:
        self._send_downgrade_alert(symbol, old_state, new_state, narrative)
        self.downgrade_cooldown[symbol] = datetime.now()
```

**Nouă metodă adăugată — `_send_data_error_alert()`:**
```python
def _send_data_error_alert(self, symbol: str, consecutive_count: int):
    """🔇 Data unavailable alert — sent only once after N consecutive failures"""
    try:
        message = f"""
🔇 <b>{symbol} - DATA UNAVAILABLE</b>

cBot API nu returnează date pentru acest simbol.
Consecutive failures: {consecutive_count}

<i>Alert-ul NU se va repeta. Fix: verifică cBot symbol mapping.</i>
        """
        self._send_telegram(message)
    except Exception as e:
        logger.debug(f"Could not send data error alert for {symbol}: {e}")
```

---

#### Modificarea 6 — `_send_ready_alert()` + `_send_monitoring_alert()` — fix `string indices must be integers`

**Bug descoperit:** `MarketNarrative.expected_scenarios` returnează `List[str]` (ex: `["Continue bullish trend, targets: +0.002"]`), dar codul încerca acces dict-style: `best_scenario['name']`, `best_scenario['probability']`.

**ÎNAINTE (_send_monitoring_alert):**
```python
best_scenario = narrative.expected_scenarios[0] if ... else None
if not best_scenario:
    return

message = f"""
👀 <b>{symbol} - MONITOR CLOSELY</b>
<b>📊 SETUP FORMING:</b> {best_scenario['name']}          # ← CRASH: str['name']
<b>🎯 Probability:</b> {best_scenario['probability']}%    # ← CRASH: str['probability']
"""
```

**DUPĂ:**
```python
scenarios = narrative.expected_scenarios if hasattr(narrative, 'expected_scenarios') else []
if not scenarios:
    return

scenarios_text = "\n".join(f"• {s}" for s in scenarios[:3])

message = f"""
👀 <b>{symbol} - MONITOR CLOSELY</b>
<b>📊 SCENARIO:</b>
{scenarios_text}
"""
```

Aceeași reparație aplicată și în `_send_ready_alert()`.

---

## 📊 REZULTAT LIVE DUPĂ FIX

### Scan la 19:59 UTC, 7 Martie 2026:
```
📊 4H CANDLE CLOSE SUMMARY:
   ✅ Ready to trade: 0
   👀 Monitor closely: 16    ← TOATE 16 simbolurile procesate corect
   ⏳ Waiting: 0             ← ZERO simboluri stuck pe "error"
```

### Confirmări din log:
- **16/16 simboluri** au trimis `👀 Monitoring alert sent` cu succes
- **ZERO** `string indices must be integers` erori
- **ZERO** `SETUP DOWNGRADED` alerte false
- **ZERO** `data_unavailable` (cBot-ul recunoaște acum toate simbolurile)

---

## 📁 FIȘIERE MODIFICATE

| Fișier | Linii afectate | Tip modificare |
|--------|---------------|----------------|
| `spatiotemporal_analyzer.py` | 68-79, 314-332 | 2 edituri: status + recommendation mapping |
| `realtime_monitor.py` | 55-65, 127-185, 196-218, 243-275, 278-312 | 4 edituri: init, _check_symbol, cooldown, alert format fix |

---

## 🏗️ STRUCTURA RELEVANTĂ

```
realtime_monitor.py          — Main loop, procesează 16 perechi la fiecare 4H candle close
    ↓ importă
spatiotemporal_analyzer.py   — Analiză SMC (CHoCH, FVG, trend) pe 4H timeframe
    ↓ importă
ctrader_cbot_client.py       — HTTP client pentru cBot server (localhost:8767)
    ↓ comunică cu
PythonSignalExecutor.cs      — cBot C# care rulează în cTrader (serveste date + execută ordine)
```

### Flow de date complet:
```
pairs_config.json (16 perechi)
    → realtime_monitor.py (loop la 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC)
        → spatiotemporal_analyzer.py.analyze_4h_setup()
            → ctrader_cbot_client.get_historical_data(symbol, "H4", 1200)
            → ctrader_cbot_client.get_historical_data(symbol, "D1", 365)
            → detect_choch(), detect_fvg(), analyze_trend()
            → determine setup_status + confidence
        → _handle_state_change()
            → _send_ready_alert() / _send_monitoring_alert() / _send_downgrade_alert()
                → Telegram API
```

---

## ⚠️ OBSERVAȚII PENTRU GEMINI

1. **`expected_scenarios`** este o proprietate `@property` pe `MarketNarrative` care returnează `List[str]`, NU `List[Dict]`. Orice cod viitor care accesează scenarii trebuie să le trateze ca string-uri.

2. **Cooldown-ul de 24h** e in-memory (se pierde la restart). Dacă e nevoie de persistență, trebuie salvat într-un JSON.

3. **`data_error_counts`** se resetează la restart. Dacă cBot-ul are probleme persistente cu anumite simboluri, alertele se vor retrimite o dată la fiecare restart (al 3-lea ciclu).

4. **Simbolurile problematice** (XAUUSD, USDCAD, USDCHF, AUDUSD, AUDJPY) funcționează acum, dar eroarea originală era din cBot — posibil actualizare/restart cBot a rezolvat. Dacă reapare, V8.2 o izolează corect.

5. **`_send_monitoring_alert()`** se trimite pe Telegram la **fiecare primă detecție** (unknown → monitor_closely). La restart, toate 16 perechiledeclanșează monitoring alerts. Asta e by design (first scan after restart).

---

## 🔧 VERSIUNI ACTIVE

| Componenta | Versiune |
|-----------|----------|
| realtime_monitor.py | V8.2 (data isolation + cooldown) |
| spatiotemporal_analyzer.py | V2.1 + V8.2 patch |
| ctrader_executor.py | V8.1 (duplicate alert fix) |
| PythonSignalExecutor.cs | V8.0 (CLOSE + SL/TP guard) |
| telegram_command_center.py | V8.2 (broker cross-reference) |
| unified_risk_manager.py | V8.0 (3-level duplicate guard) |

---

*Document generat automat de Claude (Copilot Agent) pentru continuitate cu Gemini.*
*Glitch in Matrix • Institutional Edition • ФорексГод*
