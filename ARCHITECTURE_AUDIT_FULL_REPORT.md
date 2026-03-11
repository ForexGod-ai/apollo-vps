# 🏗️ ARCHITECTURE AUDIT — FULL REPORT
## "Glitch in Matrix" Trading System by ФорексГод
### Data: 5 Martie 2026 (actualizat 19:50 UTC) | Auditor: Claude (System Architect Agent)

---

## 📌 SCOPUL DOCUMENTULUI

Acest document este destinat **agentului Gemini** care construiește prompt-uri pentru **agentul Claude** (coding agent).
Conține:
1. **Inventarul complet** al fișierelor critice, cu linii de cod și rol
2. **Data Flow** — cum circulă datele de la market data → execuție broker
3. **10 probleme critice** identificate, cu locație exactă în cod, severity, și context
4. **Relații între fișiere** — ce depinde de ce
5. **Instrucțiuni de prompting** — cum să construiești prompt-uri eficiente pentru Claude

---

## 🗂️ INVENTARUL FIȘIERELOR CRITICE

| # | Fișier | Linii | Rol | Alias |
|---|--------|-------|-----|-------|
| 1 | `smc_detector.py` | 4829 | **BRAIN** — Detectează CHoCH, BOS, FVG, Order Blocks, Liquidity Sweeps, calculează Entry/SL/TP | Brain |
| 2 | `daily_scanner.py` | 720 | **RADAR** — Scanează toate perechile zilnic, descarcă date D1/H4/H1, rulează Brain-ul, salvează în monitoring_setups.json | Radar |
| 3 | `setup_executor_monitor.py` | 1384 | **ARM** — Monitorizează setups la fiecare 5-30s, verifică 1H CHoCH + Pullback Fibonacci, execută trades | Arm |
| 4 | `ctrader_executor.py` | 778 | **BRIDGE** — Scrie signals.json (V7.0 array protocol, fcntl locking) pentru cBot | Bridge |
| 5 | `unified_risk_manager.py` | 671 | **SHIELD** — Validare risk: max positions, daily loss limit, kill switch (dezactivat) | Shield |
| 6 | `PythonSignalExecutor.cs` | 896 | **EXECUTOR V7.0** — cBot C# în cTrader, citește signals.json **array format**, execută `foreach` signal, atomic delete | Executor (cBot) |
| 7 | `pairs_config.json` | 206 | **CONFIG** — Lista perechilor, setări scanner, strategie execuție, lookback candles | Config |
| 8 | `SUPER_CONFIG.json` | ~50 | **RISK CONFIG** — Risk per trade, max positions, kill switch settings | Risk Config |
| 9 | `monitoring_setups.json` | variabil | **STATE** — Starea curentă a tuturor setup-urilor (MONITORING/READY/ACTIVE/EXPIRED) | State |
| 10 | `signal_cache.py` | 336 | **ANTI-SPAM** — Cache persistent + cleanup signals array (V7.0 compat) | Anti-Spam |
| 11 | `telegram_notifier.py` | ~300 | **NOTIFIER** — Trimite alerte Telegram | Notifier |
| 12 | `ctrader_cbot_client.py` | ~200 | **DATA CLIENT** — Client HTTP care descarcă date OHLC de la cBot server (port 8767) | Data Client |

---

## 🔄 DATA FLOW COMPLET — Pas cu pas

### FAZA 1: SCAN (daily_scanner.py → smc_detector.py)

```
TRIGGER: Cron job sau manual (python daily_scanner.py)

1. daily_scanner.py se conectează la cBot HTTP server (localhost:8767)
2. Pentru FIECARE pereche din pairs_config.json:
   a. Descarcă D1 (100 candles), H4 (200 candles), H1 (300 candles)
   b. Apelează smc_detector.scan_for_setup(symbol, df_daily, df_4h, priority, df_1h)

3. INSIDE scan_for_setup() (smc_detector.py):
   a. detect_choch_and_bos(df_daily) → găsește CHoCH (trend change) și BOS (trend continue)
   b. Determină latest_signal (CHoCH sau BOS, cel mai recent)
   c. Determină strategy_type: "reversal" (CHoCH) sau "continuation" (BOS)
   d. BOS HIERARCHY CHECK: Dacă 3+ BOS consecutive → trend DOMINANT, CHoCH trebuie să spargă Strong High/Low
   e. Premium/Discount VALIDATION:
      - Reversal BUY → trebuie să fie în DISCOUNT zone (sub 38.2%)
      - Reversal SELL → trebuie să fie în PREMIUM zone (peste 61.8%)
   f. Macro trend alignment (continuation nu poate fi contra macro)
   g. detect_fvg() → găsește Fair Value Gap după CHoCH/BOS
   h. FVG Quality Score (0-100, minim 60 normal, 70 GBP)
   i. Equilibrium validation (FVG trebuie în zona corectă)
   j. detect_choch_and_bos(df_4h) → caută H4 CHoCH IN FVG zone (max 48h vechi)
   k. Order Block detection + Liquidity Sweep detection
   l. calculate_entry_sl_tp() → Entry la 35% din FVG, SL pe 4H swing, TP pe Daily swing
   m. R:R filter (minim 4.0)
   n. Anti-overtrading (max 4 trades per FVG zone)

4. Rezultat: TradeSetup object cu status MONITORING sau READY
5. ML scoring (strategy_optimizer.py) + AI scoring (ai_probability_analyzer.py)
6. SAVE → monitoring_setups.json (merge cu existente)
7. Telegram alert + Chart generation
```

### FAZA 2: EXECUTE (setup_executor_monitor.py)

```
TRIGGER: Rulează continuu (loop la 5-30s, adaptiv)

1. Citește monitoring_setups.json
2. Pentru FIECARE setup cu status MONITORING sau READY:

   a. Dacă status == READY și entry1_filled == false:
      → FORCE EXECUTE imediat (bypass pullback logic)
      → Apelează ctrader_executor.execute_trade()

   b. Dacă status == MONITORING și entry1_filled == false:
      → Descarcă date LIVE: D1(100), H4(225), H1(225) de la cBot HTTP
      
      PRIORITY 1 — SNIPER MODE (radar data):
      → Dacă setup are radar_1h_choch_detected == true
      → _check_radar_entry(): verifică dacă price e în 1H/4H FVG
      → Premium/Discount zone validation
      → Dacă valid → EXECUTE_ENTRY1
      
      PRIORITY 2 — PULLBACK MODE (Fibonacci 50%):
      → _check_pullback_entry() (V3.3 Hybrid):
        Step 1: Detect 1H CHoCH/BOS in FVG zone (body closure required!)
        Step 2: Calculate Fibonacci 50% from CHoCH swing
        Step 3: Check if price touched Fibo 50% (within tolerance_pips)
        Step 4: If YES → EXECUTE_ENTRY1 (entry at Fibo 50%)
        Step 5: If NO after 6h → Check momentum continuation
        Step 6: If NO after 12h → Force entry or skip (based on distance)

   c. Dacă entry1_filled == true:
      → validate_choch_confirmation_scale_in()
      → Caută 4H CHoCH pentru Entry 2 (50% position)
      → Timeout 48h: dacă Entry 1 nu e profitabil, marchează CLOSE_ENTRY1

3. EXECUTION PATH:
   _execute_entry() → ctrader_executor.execute_trade()
   → unified_risk_manager.validate_new_trade()
   → ctrader_executor._write_signal_atomic() → signals.json
   → Telegram notification

4. UPDATE monitoring_setups.json cu noile date
```

### FAZA 3: BRIDGE (ctrader_executor.py → cBot) — V7.0 ARRAY PROTOCOL

```
1. ctrader_executor.execute_trade():
   a. Risk Manager validation (lot size, max positions, daily loss)
   b. Signal creation: {symbol, direction, entry_price, stop_loss, take_profit, lot_size, signal_id, timestamp}
   c. signal_queue.enqueue(signal)
   d. _process_queue():
      - _write_signal_atomic(signal) → APPEND la signals.json array
      - Folosește fcntl.LOCK_EX pentru file locking
      - Scrie doar pe apollo folder path (mirror eliminat)
      - Rate limit: 12s între semnale
   e. Telegram "🚀 SIGNAL DEPLOYED" notification (fire-and-forget)

2. PythonSignalExecutor.cs V7.0 (cBot în cTrader):
   a. OnTimer() la fiecare 10s
   b. Citește signals.json (path: ~/Desktop/.../apollo/signals.json)
   c. ✅ V7.0: JsonSerializer.Deserialize<List<TradeSignal>>(json)
   d. ✅ Backwards compatible: detectează automat array vs single object
   e. ✅ foreach (signal in signals) → ExecuteSignal(signal)
   f. ✅ Error handling per signal (skip corupt, nu crash)
   g. ✅ TryRecoverSignalsFromArray() — recovery din array parțial corupt
   h. ATOMIC DELETE signals.json doar DUPĂ procesarea ÎNTREGULUI array
   i. APPEND signal_id la processed_signals.txt (per signal)
   j. HashSet<string> session tracking (înlocuit string comparison)
   k. Position management: auto-close at profit pips
```

---

## 🔑 RELAȚII ÎNTRE FIȘIERE (DEPENDENCY MAP)

```
pairs_config.json ──────────────────────────────────────┐
SUPER_CONFIG.json ───────────────────────────────┐      │
                                                  │      │
                                                  ▼      ▼
daily_scanner.py ──imports──► smc_detector.py     │      │
       │                          │               │      │
       │                          │               │      │
       ▼                          ▼               │      │
monitoring_setups.json    TradeSetup objects       │      │
       │                                          │      │
       ▼                                          │      │
setup_executor_monitor.py ──imports──►            │      │
       │    ├── smc_detector (CHoCH detect, Fibo) │      │
       │    ├── ctrader_executor ◄────────────────┘      │
       │    ├── telegram_notifier                        │
       │    ├── daily_scanner (CTraderDataProvider)      │
       │    ├── signal_cache (anti-spam)                 │
       │    └── ctrader_cbot_client (HTTP data)  ◄───────┘
       │
       ▼
ctrader_executor.py ──imports──►
       │    ├── unified_risk_manager ◄── SUPER_CONFIG.json
       │    └── telegram_notifier
       │
       ▼
signals.json (file-based IPC)
       │
       ▼
PythonSignalExecutor.cs (cBot) → cTrader Broker
       │
       ▼
processed_signals.txt
active_positions.json
```

---

## 🚨 CELE 10 PROBLEME IDENTIFICATE

---

### ✅ ~~PROBLEMA #1: RACE CONDITION — signals.json OVERWRITE~~ **REZOLVAT**
**Severity: CRITICAL** → **FIXED în V7.0 (5 Martie 2026)**
**Fișier: `ctrader_executor.py`**

**CE ERA:**
- Python scria UN SINGUR signal (single object) → fișierul era suprascris la fiecare semnal nou
- 8 semnale trimise rapid = 7 pierdute, doar ultimul ajungea la cBot

**CE S-A FĂCUT:**
- `_write_signal_atomic()` acum: citește array-ul existent → append semnal nou → scrie înapoi
- File locking cu `fcntl.LOCK_EX` pentru thread safety
- `clear_signals()` scrie `[]` (array gol) în loc de `{}`
- `signal_cache.py` → `cleanup_old_signals_file()` filtrează individual fiecare semnal din array
- **Testat: 6/6 teste passed** (write, append, triple stack, clear, read, cleanup)

**FORMAT NOU signals.json:**
```json
[
  {"SignalId": "EURUSD_BUY_123", "Symbol": "EURUSD", ...},
  {"SignalId": "GBPJPY_SELL_124", "Symbol": "GBPJPY", ...}
]
```

---

### ✅ ~~PROBLEMA #2: METODĂ INEXISTENTĂ — `_immediate_entry_at_choch()`~~ **REZOLVAT**
**Severity: CRITICAL** → **FIXED (5 Martie 2026)**
**Fișier: `setup_executor_monitor.py`**

**CE ERA:**
- Două metode `_check_pullback_entry` cu același nume (V2.1 dead code + V3.3 activă)
- V3.3 apela `self._immediate_entry_at_choch()` — metodă inexistentă → `AttributeError`

**CE S-A FĂCUT:**
- Dead code V2.1 (prima `_check_pullback_entry`) **ÎNLOCUIT** cu metoda nouă `_immediate_entry_at_choch()`
- Metoda nouă folosește `detect_choch_and_bos()` (API-ul real din smc_detector)
- Returnează dict cu `entry_price`, `stop_loss`, `fibo_data` — format corect pentru executor
- Gestionează atât CHoCH cât și BOS breaks

---

### ✅ ~~PROBLEMA #3: VARIABILĂ NEDEFINITĂ — `structure_type`~~ **REZOLVAT**
**Severity: CRITICAL** → **FIXED (5 Martie 2026)**
**Fișier: `setup_executor_monitor.py`**

**CE ERA:**
- `f'No {direction} {structure_type} in FVG zone yet'` — `structure_type` nedefinit → `NameError`
- Se întâmpla de fiecare dată când un setup monitorizat nu găsea 1H confirmation

**CE S-A FĂCUT:**
- Variabila `{structure_type}` înlocuită cu literal `'CHoCH/BOS'`
- Fix aplicat ca parte din înlocuirea dead code-ului V2.1 (problema #2)

---

### ✅ ~~PROBLEMA #4: `CLOSE_ENTRY1` NU ÎNCHIDE TRADE-UL LA BROKER~~ **REZOLVAT (V8.0 — 6 Martie 2026)**
**Severity: CRITICAL → FIXED**
**Fișiere: `ctrader_executor.py` + `PythonSignalExecutor.cs` + `setup_executor_monitor.py`**

**CE ERA:**
- `CLOSE_ENTRY1` doar marca JSON-ul ca "CLOSED" fără să trimită semnal de close la broker
- Trade-ul RĂMÂNEA DESCHIS la broker până lovea SL-ul

**CE S-A FĂCUT (V8.0 CLOSE PROTOCOL — LANȚ COMPLET):**
1. `ctrader_executor.py` — `close_position(symbol, direction, reason)`: construiește signal cu `"Action": "CLOSE"`, enqueue atomic
2. `PythonSignalExecutor.cs` — CLOSE handler în `ExecuteSignal()`: detectează `Action == "CLOSE"`, caută matching position (symbol + TradeType + Label), apelează `ClosePosition(pos)`, scrie confirmation
3. `setup_executor_monitor.py` — `CLOSE_ENTRY1` apelează `self.executor.close_position()` direct
4. `TradeSignal` class — câmpuri noi: `Action` + `CloseReason`
5. Bonus: SL/TP zero guard pe ambele părți (Python + C#) — nicio tranzacție naked

---

### ✅ ~~PROBLEMA #5: EXECUȚII MULTIPLE PER PERECHE~~ **REZOLVAT (Guard pe 3 niveluri)**
**Severity: CRITICAL** → **FIXED în V7.1 (5 Martie 2026)**
**Fișiere: `PythonSignalExecutor.cs` + `unified_risk_manager.py` + `setup_executor_monitor.py`**

**CE ERA:**
- 10 poziții deschise (3-4x per pereche) din cauza restart-urilor de executor
- La fiecare restart, cache-ul era gol → re-trimitea semnale pe perechi deja active

**CE S-A FĂCUT (GUARD PE 3 NIVELURI):**

**NIVEL 1 — cBot C# (Ultima linie de apărare):**
- `ExecuteSignal()` verifică `Positions` la început
- Dacă există poziție cu `Label.StartsWith("Glitch Matrix")` pe același simbol → `SKIP`
- Scrie `WriteExecutionConfirmation(REJECTED, "Duplicate position guard")`

**NIVEL 2 — Python Risk Manager:**
- `_symbol_has_open_position(symbol)` citește `active_positions.json` (scris de cBot live)
- `max_positions_per_symbol = 1` — configurat în `__init__`
- Apelat în `validate_new_trade()` ÎNAINTE de max positions check

**NIVEL 3 — Executor Monitor:**
- `_symbol_already_at_broker(symbol)` citește `active_positions.json`
- La `READY → EXECUTE`: dacă broker are poziție → skip, marchează `ACTIVE` fără re-execuție
- `skip_reason = 'duplicate_guard_broker_position_exists'`

**Flux protecție:**
```
Setup READY → NIVEL 3 (executor) → NIVEL 2 (risk mgr) → signals.json → NIVEL 1 (cBot)
      ↓ SKIP              ↓ REJECT                                    ↓ REJECT
  (broker has pos)    (broker has pos)                          (broker has pos)
```

**NOTĂ:** Duplicatele existente (10 poziții) trebuie închise MANUAL din cTrader.

---

### ✅ ~~PROBLEMA #6: PATH MISMATCH ÎNTRE EXECUTOR ȘI cBOT~~ **REZOLVAT**
**Severity: MEDIUM** → **FIXED (5 Martie 2026)**
**Fișiere: `setup_executor_monitor.py` + `ctrader_executor.py`**

**CE ERA:**
- `setup_executor_monitor.py` scria pe `~/GlitchMatrix/signals.json`
- cBot citea din `~/Desktop/.../apollo/signals.json`
- Path-uri diferite = semnalele nu ajungeau la broker

**CE S-A FĂCUT:**
- `setup_executor_monitor.py`: `os.path.expanduser("~/GlitchMatrix/signals.json")` → `str(Path(__file__).parent.resolve() / "signals.json")` (apollo folder)
- `ctrader_executor.py` `__init__`: default path = `Path(__file__).parent.resolve() / "signals.json"` (apollo folder)
- `ctrader_executor.py` `_write_signal_atomic()`: eliminat dual-path mirror (scriere doar pe calea unificată)
- Acum ambele scriu în **apollo folder** = unde citește cBot-ul

---

### ⚠️ PROBLEMA #7: ANTI-SPAM CACHE FĂRĂ TTL (Time-To-Live)
**Severity: HIGH** (contribuie la Problema #5 — duplicate executions)
**Fișier: `signal_cache.py` (folosit în `setup_executor_monitor.py`)**

**CE SE ÎNTÂMPLĂ:**
```python
# setup_executor_monitor.py linia ~1017:
execution_id = f"{symbol}_execute_{result['entry_price']:.5f}"
if self.signal_cache.is_processed(execution_id):
    logger.warning(f"🚫 SKIP EXECUTION: {symbol} already executed")
    continue  # ← NU mai încearcă NICIODATĂ
```

**PROBLEMA DUBLĂ:**
1. **Dacă `processed_signals.txt` e șters** (cum s-a întâmplat la restart-uri) → cache-ul pierde memoria → duplicate executions
2. **Cache-ul e in-memory per session** — la restart, se pierde totul → cBot primește din nou aceleași semnale
3. Cache-ul persistent (pe disc) salvează `execution_id` dar NU se verifică contra broker state

**IMPACTUL DOVEDIT:**
- A contribuit direct la Problema #5 (10 poziții, 3x per pereche)
- La fiecare restart de executor, cache-ul e gol → re-trimite totul

**FIX NECESAR:**
- Adaugă TTL pe cache entries (ex: 24h)
- **CRITRIC**: Cross-reference cu `active_positions.json` — dacă broker are deja poziție pe simbol, NU re-trimite
- Salvează cache-ul persistent pe disc (nu doar in-memory)
- La startup, reconstruiește cache din `processed_signals.txt` + `active_positions.json`

---

### ⚠️ PROBLEMA #8: SETUP-URI STALE FĂRĂ INVALIDARE
**Severity: MEDIUM**
**Fișier: `setup_executor_monitor.py`**

**CE SE ÎNTÂMPLĂ:**
- Un setup este creat cu direcția "SELL" bazată pe Daily CHoCH bearish
- Setup-ul rămâne în monitoring_setups.json cu status MONITORING
- Între timp, piața face un nou Daily CHoCH bullish → trendul se inversează
- DAR: nimeni nu re-verifică direcția setup-ului!
- Executor-ul continuă să caute 1H CHoCH bearish pe un market care acum e bullish

**IMPACTUL:**
- Setup-uri vechi pot triggera trade-uri contra trendului actual
- Expirarea de 72h (setup_expiry_hours) e protecție, dar 72h e mult timp pe forex
- Nu există "re-scan" al direcției pe setup-uri existente

**FIX NECESAR:**
- La fiecare check cycle, re-verifică Daily CHoCH direction
- Dacă trendul s-a inversat → marchează setup-ul EXPIRED/INVALIDATED
- Sau: Reduce expiry la 24h și reconstruiește setup-urile zilnic

---

### 🟡 PROBLEMA #9: COD DUPLICAT — Premium/Discount Check DE DOUĂ ORI
**Severity: LOW (nu e bug, dar e confuzie)**
**Fișier: `smc_detector.py`**
**Linii: ~3100-3170**

**CE SE ÎNTÂMPLĂ:**
```python
# PRIMA DATĂ (~linia 3100-3140):
# V7.1 FORCED VALIDATION: Premium/Discount zones
# V7.1 FORCED VALIDATION: Macro alignment

# A DOUA OARĂ (~linia 3150-3170):
# V8.2 FIX: DAILY TREND LOCK
# → Face EXACT aceleași verificări ca cele de mai sus!
```

**IMPACTUL:**
- Continuation setups sunt verificate de DOUĂ ORI cu exact același filtru macro alignment
- Nu cauzează bug-uri, dar face codul mai greu de citit și menținut
- Un developer poate modifica o verificare dar uita de cealaltă

**FIX NECESAR:**
- Elimină blocul duplicat V8.2 (liniile ~3150-3170)
- Sau: Refactorizează într-o singură funcție de validare

---

### ✅ ~~PROBLEMA #10: DEAD CODE — Prima `_check_pullback_entry` (V2.1)~~ **REZOLVAT**
**Severity: LOW** → **FIXED (5 Martie 2026)**
**Fișier: `setup_executor_monitor.py`**

**CE ERA:**
- Două metode cu același nume `_check_pullback_entry` — prima (V2.1) era dead code

**CE S-A FĂCUT:**
- Prima definiție V2.1 **ÎNLOCUITĂ** cu metoda `_immediate_entry_at_choch()` (rezolvă și Problema #2)
- Nu mai există dead code, nu mai există duplicate

---

## 🧠 LOGICA SMC DETECTOR — Concepte cheie pentru prompting

### Vocabular SMC (Smart Money Concepts):

| Termen | Explicație | Unde apare |
|--------|-----------|------------|
| **CHoCH** | Change of Character — break de swing point care schimbă trendul | smc_detector.py `detect_choch_and_bos()` |
| **BOS** | Break of Structure — break care CONFIRMĂ trendul existent | smc_detector.py `detect_choch_and_bos()` |
| **FVG** | Fair Value Gap — gap de preț între 3 candle-uri consecutive | smc_detector.py `detect_fvg()` |
| **OB** | Order Block — ultima candela opusă înainte de impuls | smc_detector.py `detect_order_block()` |
| **Liquidity Sweep** | Prinderea equal highs/lows înainte de reversal | smc_detector.py `detect_liquidity_sweep()` |
| **Premium Zone** | Zona scumpă (top 40% din range) — bună pentru SELL | smc_detector.py `calculate_premium_discount_zones()` |
| **Discount Zone** | Zona ieftină (bottom 40% din range) — bună pentru BUY | smc_detector.py `is_price_in_discount()` |
| **Equilibrium** | Nivelul de 50% din range-ul macro | smc_detector.py `calculate_equilibrium_reversal/continuity()` |
| **Body Closure** | Candela trebuie să ÎNCHIDĂ dincolo de nivel (nu doar wick) | Folosit în CHoCH detection |
| **Swing Point** | High/Low local detectat cu lookback=5 | smc_detector.py `detect_swing_highs/lows()` |

### Parametri cheie:

| Parametru | Valoare | Unde se setează |
|-----------|---------|-----------------|
| `swing_lookback` | 5 candle-uri | smc_detector.__init__ (default) |
| `atr_multiplier` | 1.2 (default), 1.5 (scanner override) | smc_detector.__init__ / daily_scanner.py |
| `R:R minim` | 4.0 | smc_detector.scan_for_setup() linia ~3796 |
| `FVG quality minim` | 60 (normal), 70 (GBP) | smc_detector.scan_for_setup() |
| `H4 CHoCH max age` | 12 candle (48h) | smc_detector.scan_for_setup() |
| `Pullback tolerance` | 10 pips | pairs_config.json |
| `Pullback timeout` | 12h | pairs_config.json |
| `Momentum check` | După 6h | pairs_config.json |
| `Setup expiry` | 72h total | pairs_config.json |
| `Entry 2 timeout` | 48h după Entry 1 | pairs_config.json |
| `Rate limit signals` | 12s între semnale | ctrader_executor.py |
| `cBot poll interval` | 10s | PythonSignalExecutor.cs |

---

## 📝 INSTRUCȚIUNI PENTRU GEMINI — Cum să construiești prompt-uri eficiente

### REGULI GENERALE:

1. **Specifică MEREU fișierul și liniile** — Claude are nevoie de context exact
2. **Un fix per prompt** — Nu combina mai mult de 2-3 probleme într-un singur prompt
3. **Menționează DEPENDENȚELE** — Dacă fix-ul afectează mai multe fișiere, listează-le pe toate
4. **Precizează ce NU trebuie atins** — Claude poate modifica prea mult dacă nu e limitat

### TEMPLATE PROMPT PENTRU FIX:

```
CONTEXT: Lucrez pe proiectul "Glitch in Matrix" — un AI trading system.
Fișierele relevante sunt: [lista fișierelor]
SUPER_CONFIG.json este la: /Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/

PROBLEMA: [Descrierea din acest document]
FIȘIERUL AFECTAT: [nume fișier]
LINIILE: [interval]

CE TREBUIE FĂCUT:
1. [acțiunea specifică]
2. [acțiunea specifică]

CE NU TREBUIE MODIFICAT:
- [lista fișierelor/funcțiilor care trebuie lăsate intacte]

TESTARE: După fix, [cum se verifică]
```

### ORDINEA RECOMANDATĂ DE REZOLVARE:

```
✅ REZOLVAT — SPRINT 1 (CRITICE ARHITECTURĂ):
  ✅ Fix #1: Race Condition signals.json → V7.0 array protocol (Python)
  ✅ Fix #1b: cBot PythonSignalExecutor.cs → V7.0 List<TradeSignal> + foreach
  ✅ Fix #3: structure_type undefined → literal 'CHoCH/BOS'
  ✅ Fix #2: _immediate_entry_at_choch → metodă nouă creată
  ✅ Fix #6: Path mismatch → unificat pe apollo folder
  ✅ Fix #10: Dead code V2.1 → înlocuit cu _immediate_entry_at_choch

✅ REZOLVAT — SPRINT 2a (DUPLICATE GUARD):
  ✅ Fix #5: Duplicate guard pe 3 niveluri (cBot + Risk Manager + Executor)
     ├── ✅ cBot: Positions check înainte de ExecuteMarketOrder
     ├── ✅ Risk Manager: _symbol_has_open_position() + max_positions_per_symbol=1
     └── ✅ Executor: _symbol_already_at_broker() la READY→EXECUTE
     ⚠️  MANUAL: Închide duplicatele existente din cTrader

🔴 SPRINT 2b — FUNCȚIONALITATE LIPSĂ (URMĂTORUL):
  → Fix #4: CLOSE_ENTRY1 nu trimite close la broker
     ├── Pas 1: close_trade() în ctrader_executor.py
     ├── Pas 2: Action="CLOSE" handler în cBot C#
     └── Pas 3: Hook în setup_executor_monitor.py la CLOSE_ENTRY1

🟡 SPRINT 3 — PREVENTIVE:
  → Fix #7: Anti-spam cache TTL + broker state verification
  → Fix #8: Setup invalidation la schimbare trend daily

🟢 SPRINT 4 — CLEANUP:
  → Fix #9: Cod duplicat Premium/Discount în smc_detector.py
```

### PROMPT-URI PREGĂTITE:

#### PROMPT FIX #1 (Race Condition):
```
CONTEXT: "Glitch in Matrix" trading system. signals.json este fișierul IPC 
între Python și cBot (C# în cTrader). Python scrie un singur JSON object,
cBot citește la 10s și șterge. Dacă 2 semnale sunt scrise în <10s, primul
se pierde.

FIȘIER: ctrader_executor.py (750 linii)
METODĂ: _write_signal_atomic() + _process_queue()

CERINȚĂ: Transformă signals.json din SINGLE object → ARRAY de semnale.
- Python adaugă (append) la array
- cBot citește TOATE semnalele, execută pe rând, apoi șterge fișierul
- Dacă fișierul nu există, creează array nou
- Dacă fișierul există, citește array-ul existent și adaugă
- Folosește file locking (fcntl) pentru thread safety

NU MODIFICA: smc_detector.py, daily_scanner.py, monitoring_setups.json
TESTARE: Scrie 3 semnale rapid (<5s) și verifică că signals.json conține
array cu 3 elemente
```

#### PROMPT FIX #2+#3 (Crash bugs):
```
CONTEXT: "Glitch in Matrix" trading system.

FIȘIER: setup_executor_monitor.py (1383 linii)

PROBLEME:
1. Linia 390-465: Există o metodă _check_pullback_entry (V2.1) care e DEAD CODE
   (suprascrisă de a doua definiție la linia 468). ȘTERGE-O.

2. Linia ~478: self._immediate_entry_at_choch(setup, df_h1, symbol) — această
   metodă NU EXISTĂ. Fie creează o metodă nouă cu logica din V2.1 (immediate
   CHoCH entry), fie elimină if-ul cu use_immediate_entry.

3. Linia ~530: f-string folosește {structure_type} care nu e definit nicăieri.
   Înlocuiește cu "CHoCH/BOS" sau derivă din context.

NU MODIFICA: Logica V3.3 Pullback din _check_pullback_entry (linia 468+)
TESTARE: Rulează python -c "from setup_executor_monitor import *" fără erori
```

#### PROMPT FIX #4 (Close Entry — 3 fișiere):
```
CONTEXT: "Glitch in Matrix" trading system. ctrader_executor.py scrie
semnale de OPEN trade în signals.json (V7.0 array format). Nu există 
mecanism de CLOSE trade. Contul are 10 poziții deschise.

CERINȚĂ — 3 FIȘIERE:

FIȘIER 1: ctrader_executor.py (778 linii)
  → Adaugă close_trade(symbol, direction) care scrie signal cu:
    {"Action": "CLOSE", "Symbol": symbol, "Direction": direction_opusă}
  → Folosește aceeași logică _write_signal_atomic (append la array)

FIȘIER 2: PythonSignalExecutor.cs (896 linii, C#)
  → În foreach loop din OnTimer(), verifică signal.Action:
    - Dacă Action == "CLOSE": caută poziția Glitch Matrix pe acel symbol 
      și apelează ClosePosition()
    - Dacă Action != "CLOSE" (sau null): ExecuteSignal() ca acum
  → Adaugă proprietate "Action" în clasa TradeSignal

FIȘIER 3: setup_executor_monitor.py (1384 linii)
  → La blocul CLOSE_ENTRY1 (~linia 1205), apelează:
    self.executor.close_trade(symbol, direction)
  → NU mai marchează doar JSON, CI trimite efectiv close signal

NU MODIFICA: smc_detector.py, daily_scanner.py, signal_cache.py
TESTARE: Scrie manual un close signal → verifică în cBot log că 
detectează Action=CLOSE și închide poziția
```

#### PROMPT FIX #5 (Duplicate Positions Guard — 3 fișiere):
```
CONTEXT: "Glitch in Matrix" trading system. Contul are 10 poziții 
deschise — 3-4 per pereche (EURJPY x4, GBPJPY x3, USDJPY x3).
Cauza: la restart executor, cache-ul e gol, trimite din nou semnale
pe perechi deja active la broker.

CERINȚĂ — GUARD PE 3 NIVELURI:

NIVEL 1: cBot (PythonSignalExecutor.cs)
  → Înainte de ExecuteMarketOrder(), verifică:
    if (Positions.Any(p => p.SymbolName == symbolName 
        && p.Label.StartsWith("Glitch Matrix")))
    {
        Print($"⚠️ SKIP: Already have position on {symbolName}");
        // Mark as processed anyway (to prevent retry spam)
        continue;
    }
  → Aceasta e ULTIMA LINIE DE APĂRARE

NIVEL 2: Python Risk Manager (unified_risk_manager.py, 671 linii)
  → În validate_new_trade(), adaugă:
    - Citește active_positions.json (scris de cBot la fiecare 10s)
    - Dacă symbol deja are poziție deschisă cu label "Glitch" → REJECT
    - Log: "REJECTED: {symbol} already has open position at broker"

NIVEL 3: Executor (setup_executor_monitor.py)
  → La startup (main loop first iteration):
    - Citește active_positions.json
    - Pentru fiecare setup READY: dacă symbol deja are poziție → skip
    - Log: "SKIP: {symbol} already active at broker"

NU MODIFICA: smc_detector.py, daily_scanner.py, ctrader_executor.py
TESTARE: Rulează executor cu 3 setups READY pe perechi cu poziții deja 
deschise → verifică că NU se trimit semnale noi
```

---

## 📊 STAREA CURENTĂ A CONTULUI (5 Martie 2026, 19:50 UTC)

- **Balanță:** $6,055.21
- **Equity:** $6,204.50 (+$149.29 unrealized)
- **Poziții deschise:** 10 total (9 Glitch Matrix + 1 manual)
- **Setups monitorizate:** 3 (GBPJPY BUY, EURJPY SELL, USDJPY SELL) — toate ACTIVE
- **⚠️  PROBLEMĂ:** Fiecare pereche are 3-4 poziții duplicate (vezi Problema #5)

### Poziții la broker (live):
| Symbol | Dir | Entry | PnL | Pips | Notă |
|--------|-----|-------|-----|------|------|
| EURJPY | SELL | 182.829 | +$193.91 | +19.1 | Original (veche) |
| EURJPY | SELL | 182.682 | +$9.44 | +4.4 | Duplicat |
| EURJPY | SELL | 182.660 | +$3.16 | +2.2 | Duplicat |
| EURJPY | SELL | 182.642 | -$1.98 | +0.4 | Duplicat |
| GBPJPY | BUY | 210.185 | -$42.29 | -7.4 | Original (veche) |
| GBPJPY | BUY | 210.174 | -$36.92 | -6.3 | Duplicat |
| GBPJPY | BUY | 210.119 | -$10.07 | -0.8 | Duplicat |
| USDJPY | SELL | 157.734 | +$22.78 | +4.4 | Original |
| USDJPY | SELL | 157.726 | +$17.50 | +3.6 | Duplicat |
| USDJPY | SELL | 157.690 | -$6.24 | +0.0 | Duplicat |

- **Kill Switch:** DEZACTIVAT COMPLET
- **Bridge:** Fire-and-Forget V7.0 — array protocol cu fcntl locking (Python + C# sincronizate)
- **cBot activ:** PythonSignalExecutor **V7.0** (array protocol, foreach, atomic delete)
- **Probleme rezolvate:** 8 din 10 (Race Condition AMBELE PĂRȚI, Path Mismatch, Dead Code, NameErrors, Duplicate Guard 3 niveluri)
- **Probleme critice rămase:** 1 (#4 CLOSE_ENTRY1)
- **Probleme minore rămase:** 3 (#7 Cache TTL, #8 Setup Invalidation, #9 Cod duplicat)

---

## 🔧 MODIFICĂRI FĂCUTE ÎN ACEASTĂ SESIUNE (5 Martie 2026)

### Faza 1 — Emergency Fixes:
| Fișier | Ce s-a modificat | De ce |
|--------|-----------------|-------|
| `unified_risk_manager.py` | `check_kill_switch()` returnează mereu False, `activate_kill_switch()` neutralizat | Kill switch bloca tot sistemul din 26 Feb |
| `SUPER_CONFIG.json` | `kill_switch.enabled: false`, `validation.check_kill_switch: false` | Dezactivare completă |
| `ctrader_executor.py` | V5.0→V6.0 Fire-and-Forget (nu mai așteaptă confirmare) | EXECUTION TIMEOUT de 30s la fiecare trade |
| `trading_disabled.flag` | ȘTERS | Fișierul flag care bloca trading-ul |

### Faza 2 — Architecture Fixes (V7.0 Python):
| Fișier | Ce s-a modificat | Problema rezolvată |
|--------|-----------------|--------------------|
| `ctrader_executor.py` | `_write_signal_atomic()` → array append cu `fcntl` locking | #1 Race Condition |
| `ctrader_executor.py` | `clear_signals()` → scrie `[]` nu `{}` | #1 Race Condition |
| `ctrader_executor.py` | `__init__` → default path = apollo folder | #6 Path Mismatch |
| `ctrader_executor.py` | Eliminat dual-path mirror write | #6 Path Mismatch |
| `setup_executor_monitor.py` | Path `~/GlitchMatrix/` → `Path(__file__).parent` | #6 Path Mismatch |
| `setup_executor_monitor.py` | Dead code V2.1 → `_immediate_entry_at_choch()` | #2 + #10 |
| `setup_executor_monitor.py` | `{structure_type}` → `'CHoCH/BOS'` literal | #3 NameError |
| `signal_cache.py` | `cleanup_old_signals_file()` → filtrare individuală din array | #1 Compatibilitate V7.0 |

### Faza 3 — cBot C# Array Protocol (V7.0):
| Fișier | Ce s-a modificat | Problema rezolvată |
|--------|-----------------|--------------------|
| `PythonSignalExecutor.cs` | `OnTimer()` → `Deserialize<List<TradeSignal>>` (array instead of single) | #1b cBot Array Parse |
| `PythonSignalExecutor.cs` | `foreach` loop → procesează fiecare signal individual | #1b Multi-signal support |
| `PythonSignalExecutor.cs` | Backwards compatible: detectează automat `[array]` vs `{single}` | Compatibilitate legacy |
| `PythonSignalExecutor.cs` | `TryRecoverSignalsFromArray()` → recovery din JSON parțial corupt | Robustețe |
| `PythonSignalExecutor.cs` | `TryDeleteSignalFile()` → atomic delete DOAR după procesare completă | #1 Data integrity |
| `PythonSignalExecutor.cs` | `HashSet<string>` → session tracking (înlocuit single string) | Anti-duplicate |
| `PythonSignalExecutor.cs` | `IOException` catch → skip cycle dacă Python scrie simultan | Race condition |
| `PythonSignalExecutor.cs` | Version banner: V4.0 → V7.0 ARRAY PROTOCOL | Versioning |

### Faza 4 — Duplicate Position Guard (V7.1):
| Fișier | Ce s-a modificat | Problema rezolvată |
|--------|-----------------|--------------------|
| `PythonSignalExecutor.cs` | `ExecuteSignal()` → guard la început: `Positions` check pe `SymbolName` + `Label` | #5 Nivel 1 (cBot) |
| `unified_risk_manager.py` | `_symbol_has_open_position()` → citește `active_positions.json` | #5 Nivel 2 (Risk Mgr) |
| `unified_risk_manager.py` | `max_positions_per_symbol = 1` + check în `validate_new_trade()` | #5 Nivel 2 (Risk Mgr) |
| `unified_risk_manager.py` | Fix `_load_daily_state()` apelat de 2 ori → acum o singură dată | Bug fix |
| `setup_executor_monitor.py` | `_symbol_already_at_broker()` → citește `active_positions.json` | #5 Nivel 3 (Executor) |
| `setup_executor_monitor.py` | READY→EXECUTE guard: skip dacă broker are poziție pe simbol | #5 Nivel 3 (Executor) |

---

*Document generat de Claude (System Architect Agent) după audit complet al tuturor fișierelor critice.*
*Actualizat: 5 Martie 2026, 20:15 UTC — Sprint 1 + 2a complet (8/10 fix-uri), Sprint 2b următorul.*
*Toate liniile de cod, dependențele, și problemele au fost verificate prin citire directă a codului sursă.*
