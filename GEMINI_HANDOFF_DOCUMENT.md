# 🔱 GLITCH IN MATRIX — GEMINI HANDOFF DOCUMENT
**Authored by ФорексГод | Terminal: INSTITUTIONAL TERMINAL**
**Last Updated: 16 Martie 2026 | Version: V10.5**

---

## SECȚIUNEA 1 — CONTEXT GENERAL AL SISTEMULUI

### Ce este acest sistem?
Un trading bot autonom care rulează 24/7 pe macOS, conectat la cTrader (IC Markets).
Strategia de bază: **D1 Bias Lock → 4H CHoCH Body Closure → 1H Fibonacci 50% Entry**

### Arhitectura (5 procese Python care rulează simultan):
```
watchdog_monitor.py          — Supraveghetor de procese (restart automat)
telegram_command_center.py   — Control via Telegram (@GlitchMatrixBot)
setup_executor_monitor.py    — Creierul principal: monitorizează + execută setup-uri
realtime_monitor.py          — Monitorizare live prețuri și alertă
daily_scanner.py             — Rulat manual/zilnic: scanează piața pe D1
```

### Fluxul complet de date:
```
daily_scanner.py
  → smc_detector.detect_trade_setup()   ← CREIERUL ANALITIC
  → monitoring_setups.json              ← FIȘIER CENTRAL DE STARE
  → setup_executor_monitor.py           ← EXECUȚIE AUTOMATĂ
  → ctrader_executor.py                 ← SCRIERE signals.json
  → cBot (C#) la broker                 ← EXECUȚIE REALĂ
```

### Fișiere cheie în workspace:
```
/trading-ai-agent apollo/
├── smc_detector.py              (4900 linii) — Toată logica SMC/ICT
├── setup_executor_monitor.py    (2050 linii) — Monitor principal
├── unified_risk_manager.py       (798 linii) — Risk management
├── daily_scanner.py              (747 linii) — Scanner zilnic
├── ctrader_executor.py           (898 linii) — Executor semnale
├── SUPER_CONFIG.json              (87 linii) — Configurare centralizată
├── monitoring_setups.json        (dinamic)   — Setup-uri active
├── signals.json                  (dinamic)   — Semnale pentru cBot
└── logs/                                     — Toate log-urile
```

### Semnătura oficială (EXACT 4 linii, nicio modificare):
```
────────────────
🔱 AUTHORED BY ФорексГод 🔱
────────────────
🏛️ INSTITUTIONAL TERMINAL 🏛️
```

---

## SECȚIUNEA 2 — STRATEGIA DE TRADING (CONTEXT TEHNIC PENTRU GEMINI)

### Logica de intrare (3 confirmare obligatorii):

**NIVELUL 1 — D1 Bias (Daily)**
- `smc_detector.detect_trade_setup()` analizează Daily chart
- Determină `strategy_type`:
  - `reversal` = CHoCH pe Daily care sparge un Strong High/Low (macro 100 candles)
  - `continuation` = BOS dominant pe Daily (trendul continuă)
- Dacă nu există semnal clar → `return None` (nicio scanare inutilă)

**NIVELUL 2 — 4H Body Closure (Sincronizare)**
- Se caută un CHoCH pe 4H în aceeași direcție ca D1 bias
- **OBLIGATORIU**: Corpul lumânării (nu wick-ul!) trebuie să închidă dincolo de break_price
- Verificare duală: `detect_choch_and_bos()` intern + guard explicit V10.5
- Dacă nu există 4H CHoCH valid → bot rămâne **SILENT** (status: MONITORING)

**NIVELUL 3 — 1H Fibonacci 50% (Entry)**
- La detectarea 1H CHoCH în FVG zone → se calculează Fibonacci din swing-ul CHoCH
- Entry optimal = 50% retracere (echilibru instituțional)
- SL sub/deasupra swing-ului de 4H
- TP la structura zilnică opusă

### Statusuri posibile ale unui setup:
```
MONITORING  → Așteptăm 4H CHoCH sau prețul să ajungă la FVG Daily
READY       → D1 + 4H confirmate, prețul ÎN zona FVG — execuție imediată
ACTIVE      → Entry 1 executat, monitorizăm pentru Entry 2
CLOSED      → Poziție închisă
EXPIRED     → Timeout depășit fără confirmare
```

### Eticheta de strategie pe fiecare trade (în signals.json → cBot):
```
Format:  D1_{REVERSAL|CONTINUITY}_4H_SYNC_{MODE}_E{1|2}
Exemple: D1_REVERSAL_4H_SYNC_SNIPER_E1
         D1_CONTINUITY_4H_SYNC_PB50_E2
         D1_REVERSAL_4H_SYNC_FORCED_E1
```

---

## SECȚIUNEA 3 — TOT CE AM ANALIZAT (AUDIT COMPLET)

### 3.1 — unified_risk_manager.py (798 linii)

**Funcții critice citite:**
- `_reset_daily_state()` (linii 114–138) — Reset zilnic la midnight
- `validate_new_trade()` (linii ~395–555) — Validare înainte de orice trade
- `get_account_balance()` — Returnează `(equity, balance)` din cTrader API
- `_send_rejection_alert()`, `_send_warning_alert()`, `_send_kill_switch_alert()` (linii ~560–700)

**Configurare risk (din SUPER_CONFIG.json):**
```json
"risk_per_trade_percent": 5.0      → 5% risc per trade
"max_open_positions": 5            → max 5 poziții simultane (MODIFICAT!)
"max_daily_loss_percent": 10.0     → 10% loss zilnic = KILL SWITCH
"daily_loss_warning_percent": 7.0  → 7% = avertisment Telegram
"max_lot": 2.0                     → lot maxim absolut
"min_lot": 0.01                    → lot minim (broker minimum)
```

**Formula de calcul lot size (pip_value per instrument):**
```python
XAU/Silver:  pip_size=0.01,    pip_value=10.0   ← $10 per pip per lot
JPY pairs:   pip_size=0.01,    pip_value=10.0   ← $10 per pip per lot
Oil (XTI):   pip_size=0.01,    pip_value=10.0   ← $10 per pip per lot
Forex std:   pip_size=0.0001,  pip_value=10.0   ← $10 per pip per lot
Crypto BTC:  pip_size=1.0,     pip_value=0.01   ← $0.01 per micro lot

lot_size = (balance * risk%) / (sl_pips * pip_value)
```

**IMPORTANT — BTC bypass hardcodat (linie ~820 în ctrader_executor.py):**
```python
if 'BTC' in symbol:
    lot_size = 0.50  # HARDCODAT — ignoră calculul de risk
```
→ Acest bypass **ignoră complet formula de risc** pentru BTC.
→ Pe un cont de $1,000 → 0.50 lots BTC poate fi mult prea mare.
→ **NU am schimbat asta** — risc să se spargă execuția BTC. Necesită investigare separată.

### 3.2 — smc_detector.py (4900 linii)

**Funcții critice citite:**
- `detect_trade_setup()` (linii ~2900–3830) — Funcția principală, 1000+ linii
- `detect_choch_and_bos()` — Detectare CHoCH/BOS cu body closure V8.1
- `calculate_equilibrium_reversal()` / `calculate_equilibrium_continuity()` — Fibo calc
- `detect_fvg()` — Fair Value Gap cu filtru body-based + proximity 30 candles

**Logica REVERSAL vs CONTINUITY:**
```python
# Dacă BOS dominant există:
#   CHoCH trebuie să spargă Strong High/Low (macro 100 candles) → REVERSAL
#   Altfel → BOS câștigă, CONTINUITY preservat

# Dacă nu există BOS dominant:
#   CHoCH mai recent decât BOS → REVERSAL
#   BOS mai recent → CONTINUITY
#   Doar CHoCH → REVERSAL
#   Doar BOS → CONTINUITY
```

**Body Closure în detect_choch_and_bos() (V8.1):**
```python
body_high = max(df['open'].iloc[j], df['close'].iloc[j])
body_low  = min(df['open'].iloc[j], df['close'].iloc[j])
# Swing se calculează din body, nu din high/low candle
```

**Status finalizat în detect_trade_setup():**
```python
if valid_h4_choch and d1_poi_validated:
    status = 'READY'   # D1 + 4H confirmat + prețul în zonă
elif valid_h4_choch and not d1_poi_validated:
    status = 'MONITORING'  # 4H confirmat dar prețul nu e la POI
else:
    status = 'MONITORING'  # Așteptăm 4H CHoCH
```

### 3.3 — daily_scanner.py (747 linii)

**Funcție critică: `save_monitoring_setups()` (linii 570–660)**

**Schema unui setup salvat în monitoring_setups.json:**
```json
{
  "symbol": "EURUSD",
  "direction": "buy",
  "entry_price": 1.08500,
  "stop_loss": 1.07800,
  "take_profit": 1.09800,
  "risk_reward": 4.71,
  "strategy_type": "reversal",
  "setup_time": "2026-03-16T09:00:00",
  "priority": 1,
  "status": "MONITORING",
  "fvg_top": 1.08650,
  "fvg_bottom": 1.08350,
  "lot_size": 0.01
}
```

**ATENȚIE la nomenclatură câmpuri FVG:**
- `daily_scanner.py` salvează: `fvg_top` și `fvg_bottom`
- `setup_executor_monitor.py` citea: `fvg_zone_top` și `fvg_zone_bottom` (FĂRĂ fallback în unele locuri)
- → Cauza unui bug reparat în sesiunea curentă (vezi Secțiunea 4)

### 3.4 — setup_executor_monitor.py (2050 linii)

**Funcții critice citite:**
- `_process_monitoring_setups()` (linii 1366–1800) — Loop principal de monitorizare
- `_check_pullback_entry()` (linii 808–960) — Logica 4H lock + 1H CHoCH + Fibo
- `_check_radar_entry()` (linii ~680–808) — Intrare cu date radar din multi_tf_radar.py
- `_execute_entry()` (linii 1811–1900) — Execuție efectivă via ctrader_executor
- `_symbol_already_at_broker()` — Guard anti-duplicare poziții
- `_cleanup_monitoring_setups()` — Curățare setup-uri EXPIRED/CLOSED

**Fluxul `_process_monitoring_setups()`:**
```
1. Deep Sleep check → EXIT dacă activ
2. Load setups din monitoring_setups.json
3. Pentru fiecare setup cu status MONITORING/READY:
   a. Fetch D1, 4H, 1H data (cu cache)
   b. Dacă status=READY → Re-validare 4H body closure (V10.5) → execute direct
   c. Dacă status=MONITORING → _check_pullback_entry() sau _check_radar_entry()
4. Save updated setups
```

**Frecvență adaptivă:**
```python
if in_zone_count > 0:
    check_interval = 5s   # Setup-uri active în zonă → agresiv
else:
    check_interval = 30s  # Normal → economic
```

### 3.5 — ctrader_executor.py (898 linii)

**Schema completă a signals.json (ce primește cBot-ul C#):**
```json
{
  "SignalId": "EURUSD_buy_1710000000",
  "Symbol": "EURUSD",
  "Direction": "buy",
  "StrategyType": "PULLBACK",
  "EntryPrice": 1.08500,
  "StopLoss": 1.07800,
  "TakeProfit": 1.09800,
  "StopLossPips": 70.0,
  "TakeProfitPips": 130.0,
  "RiskReward": 1.86,
  "Timestamp": "2026-03-16T09:00:00",
  "LotSize": 0.05,
  "RawUnits": null,
  "LiquiditySweep": false,
  "SweepType": "",
  "ConfidenceBoost": 0,
  "OrderBlockUsed": false,
  "OrderBlockScore": 0,
  "PremiumDiscountZone": "DISCOUNT",
  "DailyRangePercentage": 45.2,
  "Comment": "D1_REVERSAL_4H_SYNC_SNIPER_E1",
  "StrategyTag": "D1_REVERSAL_4H_SYNC_SNIPER_E1"
}
```

**BTC are format special (prețuri integer, fără pips):**
```json
{
  "EntryPrice": 67258,
  "StopLoss": 65928,
  "TakeProfit": 72000,
  "LotSize": 0.50,
  "RawUnits": 50000,
  "StrategyType": "BRUTE_FORCE"
}
```

---

## SECȚIUNEA 4 — TOT CE AM EDITAT (LISTA COMPLETĂ DE MODIFICĂRI)

### Sesiunea 1 (sesiune anterioară curentei)
**Fișier: `unified_risk_manager.py`**
- ✅ **FIX `_reset_daily_state()`** — Înlocuit `self.starting_balance_today = balance` cu `self.starting_balance_today = equity`
- Motivație: La midnight reset, equity reflectă P&L floating pe poziții deschise; balance nu

### Sesiunea 2 (sesiunea "Make It Perfect for Investor")
**Fișier: `unified_risk_manager.py`**
- ✅ **FIX `validate_new_trade()` linia 449** — `daily_loss_pct = (pnl['total_pnl'] / balance) * 100` → `(pnl['total_pnl'] / equity) * 100`
- ✅ **FIX `_send_warning_alert()`** — Al doilea argument schimbat din `balance` în `equity` (consistență)
- Motivație: Dacă ai $80 pierdere flotantă pe un cont de $1,000 → equity=$920. Formula cu balance raporta -8.0%, corect e -8.7%. Kill switch-ul se activa la threshold greșit.

**Fișier: `setup_executor_monitor.py`**
- ✅ **FIX V10.5 Explicit 4H Body Closure Guard** (linii 860–887) — Adăugat verificare explicită `body_high` / `body_low` în loop-ul 4H Structure Lock, în afara `detect_choch_and_bos()`. Wick-only breaks sunt acum respinse explicit cu log.

**Fișier: `setup_executor_monitor.py`**
- ✅ **FIX Strategy Tag Validation** (linii 1849–1852) — Adăugat warning runtime dacă `strategy_type` nu e `REVERSAL/CONTINUITY/UNKNOWN` + log dual-line explicit la fiecare execuție

**Fișier: `SUPER_CONFIG.json` linia 18**
- ✅ **FIX `max_open_positions`** — `15` → `5`
- Motivație: Cont live $1,000 × 5% risc = $50 per trade × max 5 = $250 expunere totală maximă (25% din cont). Rezonabil și sigur.

### Sesiunea 4 (Audit Circuit Închis D1→4H→1H)
**Fişier: `smc_detector.py`**

- ✅ **FIX STRATEGY LOCK GUARD** (linia 4067) — Adugat validare explicită `strategy_type not in ('reversal', 'continuation')` înainte de `return TradeSetup(...)`. Dacă valoarea nu e explicit determinată, setup-ul e RESPINS (`return None`). Previne valoarea default `"reversal"` din dataclass să treacă prin sistem fără determinare explicită.

- ✅ **FIX Fibonacci pip_multiplier instrument-aware** (linia 4734) — `validate_pullback_entry()` folosea `pip_multiplier = 10000` hardcodat. Perechi JPY: `100`, metale XAU/XAG: `100`, crypto BTC/ETH: `1`. Eroarea făcea ca distanţa la Fibo 50% să fie calculată de 100x greşit pentru EURJPY/XAUUSD, ceea ce bloca sau triggera intrările incorect.

- ✅ **FIX `calculate_choch_fibonacci()` return dict** (linia 4687) — Adugat `'symbol': symbol` în return dict. Necesar pentru ca `validate_pullback_entry()` să detecteze tipul instrumentului fără parametru separat.

**Fişier: `daily_scanner.py`**

- ✅ **FIX AUTOMATIC HANDSHAKE schema** (linia 641) — `save_monitoring_setups()` acum salvează în `monitoring_setups.json`:
  - `"strategy_locked": True` — confirmă că D1 bias a fost determinat explicit
  - `"d1_bias_direction": "bullish"|"bearish"` — directia D1 pentru LURKING mode
  - `"h4_sync_fvg_top": float` — zona de intrare din mișcarea de confirmare 4H
  - `"h4_sync_fvg_bottom": float` — `0.0` dacă nu s-a confirmat încă 4H sync
  - Anterior aceste câmpuri erau calculate de `smc_detector` în memorie dar PIERDUTE la salvare pe disc. La reluarea monitorului după restart, executor-ul nu ştia zona exactă de intrare 4H.

**Fişier: `SUPER_CONFIG.json`**
- ✅ **UPDATE comment** — Comentariul stale `"Temporary 15 for current 11 positions"` actualizat la: `"Live $1000 account — 5 positions x 5% risk = $250 max simultaneous exposure"`

### Sesiunea 4 — STATUS CONFIRMED ALREADY DONE (not re-applied)
- ✅ `_reset_daily_state()` — Foloseşte equity în loc de balance (aplicat în Sesiunea 1)
- ✅ `validate_new_trade()` daily_loss_pct — equity denominator (aplicat în Sesiunea 2)
- ✅ 4H body closure guard explicit (aplicat în Sesiunea 2)
- ✅ READY path 4H bypass fix (aplicat în Sesiunea 3)

### Sesiunea 3 (Audit Sincron Automat)
**Fișier: `setup_executor_monitor.py`**

- ✅ **FIX CRITIC — READY path 4H bypass** (linia 1454–1491) — Adăugat re-validare 4H body closure înainte de execuție forțată pe status READY:
  ```python
  # Re-fetch 4H, re-run body closure check pe ultimele 12 candles
  # Dacă CHoCH-ul original nu mai e valid → status revert la MONITORING
  # Previne execuția pe semnale stale de la scanări anterioare
  ```

- ✅ **FIX — FVG notification zero values** (linia 1580–1592) — Înlocuit `fvg_zone_top/bottom` (inexistent în schema daily_scanner) cu fallback chain complet:
  ```python
  top = setup.get('fvg_zone_top', setup.get('fvg_top', setup.get('entry_price', 0)))
  # Previne: "FVG: 0.00000 - 0.00000" în notificările Telegram de 1H CHoCH
  ```

---

## SECȚIUNEA 5 — CE MAI E DE PERFECȚIONAT (TODO LIST PENTRU GEMINI)

### 🔴 PRIORITATE CRITICĂ

#### TODO-1: BTC Lot Size — Bypass Hardcodat
**Fișier:** `ctrader_executor.py` linia ~820
**Problemă:**
```python
if 'BTC' in symbol:
    lot_size = 0.50  # HARDCODAT — ignoră Risk Manager complet
```
Pe un cont de $1,000 la IC Markets, 0.50 lots BTC echivalează cu ~$500 expunere. Asta e 50% din cont pe un singur trade. Formula corectă ar trebui să calculeze:
```
lot_size = (balance * 0.05) / (sl_pips * 0.01)
# Exemplu: ($1000 * 0.05) / (1330 * 0.01) = 50 / 13.30 = 3.76 micro lots = 0.04 standard lots
```
**Ce trebuie făcut:** Înlocuit valoarea hardcodată cu calculul corect din Risk Manager, sau adăugat o verificare separată pentru BTC care să respecte `risk_per_trade_percent`.
**Risc dacă nu se face:** Trade BTC poate pierde 50% din cont dintr-o singură mișcare nefavorabilă.

#### TODO-2: SUPER_CONFIG.json — Câmpul `comment` pentru `max_open_positions`
**Fișier:** `SUPER_CONFIG.json` linia ~20
**Problemă:**
```json
"comment": "Temporary 15 for current 11 positions, reduce to 5 on live"
```
Valoarea a fost schimbată la 5, dar comentariul e vechi și confuz.
**Ce trebuie făcut:**
```json
"comment": "Live account $1000 — max 5 positions x 5% risk = $250 max exposure"
```

---

### 🟠 PRIORITATE MEDIE

#### TODO-3: `daily_scanner.py` — Câmpuri FVG inconsistente
**Problemă:** Scanner-ul salvează `fvg_top`/`fvg_bottom`. Executor-ul are cod legacy care cauta `fvg_zone_top`/`fvg_zone_bottom` în alte locuri neverificate încă.
**Ce trebuie făcut:** Audit complet în `setup_executor_monitor.py` pentru toate referințele la `fvg_zone_*` și adăugat fallback chain peste tot sau standardizat la un singur nume.
**Grep de rulat:**
```bash
grep -n "fvg_zone_top\|fvg_zone_bottom" setup_executor_monitor.py
```

#### TODO-4: `monitoring_setups.json` — Nu se salvează câmpuri 4H sync
**Problemă:** Când `smc_detector` setează status=READY cu un `h4_sync_fvg`, aceste câmpuri sunt calculate în memorie dar `save_monitoring_setups()` în `daily_scanner.py` nu salvează `h4_sync_fvg_top`/`h4_sync_fvg_bottom` în JSON.
**Ce trebuie verificat:** `daily_scanner.py` linia ~625–650 (schema `monitoring_setup` dict) — dacă lipsesc câmpurile `h4_sync_fvg_top` și `h4_sync_fvg_bottom`, executor-ul va folosi Daily FVG în locul 4H Sync FVG la reîncărcare.
**Ce trebuie adăugat în schema din `save_monitoring_setups()`:**
```python
"h4_sync_fvg_top": float(setup.h4_sync_fvg.top) if hasattr(setup, 'h4_sync_fvg') and setup.h4_sync_fvg else None,
"h4_sync_fvg_bottom": float(setup.h4_sync_fvg.bottom) if hasattr(setup, 'h4_sync_fvg') and setup.h4_sync_fvg else None,
```

#### TODO-5: ~~`setup_executor_monitor.py` — Câmpul `fvg_zone_top/bottom` în setup-urile READY~~ — ✅ REZOLVAT în Sesiunea 3
Fallback chain complet adăugat în ambele locuri critice (linia 840 + linia 1580).

#### TODO-6: `unified_risk_manager.py` — Risk amount folosește `balance` nu `equity`
**Linia 471:**
```python
risk_amount = balance * (self.risk_per_trade / 100.0)
```
Aceasta e **intenționat** (lot sizing se bazează pe capital deținut efectiv, nu pe flotant), dar merită documentat explicit pentru că poate crea confuzie. Pe un cont cu pierderi flotante mari, riști mai mult decât ar trebui raportat la equity.
**Decizie de luat:** Preferați `equity` (conservator, protejează la pierderi flotante) sau `balance` (standard industrie)?

---

### 🟡 PRIORITATE MICĂ (Cosmetic/Calitate)

#### TODO-7: `SUPER_CONFIG.json` — Câmpul `branding`
**Linia ~75:**
Există un câmp `telegram_alerts.branding` cu text verbose vechi. Ar trebui actualizat la semnătura oficială exactă de 4 linii.

#### TODO-8: `realtime_monitor.py` — ✅ AUDIT FINAL COMPLET (sesiunea curentă)
**AUDIT V2 efectuat. 5 misiuni originale + 5 verigi slabe noi rezolvate:**

| Item | Status | Fix Applied |
|---|---|---|
| 1. BIAS AWARENESS | ✅ | `_get_setup_from_monitoring()`: citește `strategy_type` + validează `strategy_locked` + `h4_sync_fvg` |
| 2. 4H BODY CLOSURE | ✅ | `_check_4h_body_closure()`: body_ratio ≥ 30%, wick/doji blocate |
| 3. DASHBOARD SYNC | ✅ | `XAUUSD \| REVERSAL \| READY TO TRADE` format pe toate alertele |
| 4. VPS CACHE H4 | ✅ | `_get_historical_data_cached()`: H4=30min, D1=60min, H1=15min TTL |
| 5. SIGNATURE | ✅ | Zero referințe `V10.4` sau `POCOVNICU` — branding curat |
| 6. TODO-4 H4_SYNC GUARD | ✅ | `_discover_setup()`: dacă `h4_sync_fvg=0.0` → `return None` (forțează re-scanare) |
| 7. STRATEGY_LOCKED GUARD | ✅ | `_discover_setup()`: dacă `strategy_locked=False` → `return None` |
| 8. PIP_MULTIPLIER DISPLAY | ✅ | `_get_pip_multiplier()` + `_fmt_price()`: XAU/JPY=100→2dec, BTC=1→2dec, forex→5dec |
| 9. CLEANUP EXPIRED | ✅ | `_cleanup_expired_setups()`: șterge EXPIRED/CLOSED/FILLED din JSON la fiecare ciclu 4H |
| 10. BRANDING STRICT | ✅ | `grep V10.4\|POCOVNICU → 0 matches` confirmat |

**Funcții în fișier (complete):**
- `_get_pip_multiplier(symbol)` — JPY/XAU=100, BTC=1, forex=10000
- `_price_decimals(symbol)` — XAU/BTC=2 dec, JPY=3 dec, forex=5 dec
- `_fmt_price(price, symbol)` — formatare uniformă în toate alertele
- `_cleanup_expired_setups()` — curăță JSON la fiecare ciclu 4H
- `_get_setup_from_monitoring(symbol)` — citește + validează h4_sync + strategy_locked
- `_check_4h_body_closure(symbol)` — body_ratio ≥ 30% (instrument-aware prices)
- `_get_historical_data_cached(symbol, tf, count)` — cache TTL
- `_send_waiting_body_closure_alert(symbol, reason)` — alertă wick/doji

**Logica h4_sync GUARD (TODO-4):**
```
_discover_setup():
  h4_sync_top = 0.0? → return None (no re-scan forced — skip cycle)
  strategy_locked = False? → return None
  → only saves to monitoring if BOTH fields valid
```

**Logica CLEANUP (per ciclu 4H):**
```
EXPIRED | CLOSED | CANCELLED | FILLED | INVALIDATED → removed from JSON
```

#### TODO-9: Kill Switch redesign
**În `unified_risk_manager.py`** la linia ~449, kill switch-ul e comentat:
```python
# Kill switch auto-activation - DISABLED (will redesign later)
```
Nu există mecanism automat de oprire la pierderi catastrofale. Există doar Deep Sleep (care oprește scanarea, nu pozițiile deschise). Dacă ai 5 poziții deschise și toate merg prost în același timp, sistemul nu le poate închide automat.

#### TODO-10: `watchdog_monitor.py` — Comportament la restart neclar
Nu știm ce face watchdog-ul dacă `setup_executor_monitor.py` cade în mijlocul scrierii în `monitoring_setups.json`. Există risc de corupere a fișierului JSON.

---

## SECȚIUNEA 6 — STAREA CURENTĂ A PROCESELOR

### Procese care rulează (verificat ultima dată):
```bash
# Comanda de verificare:
ps aux | grep -E "python.*monitor|python.*executor|python.*telegram|python.*watchdog" | grep -v grep

# Așteptat:
watchdog_monitor.py       → PID ~xxx
telegram_command_center.py → PID ~xxx
setup_executor_monitor.py  → PID ~xxx
realtime_monitor.py        → PID ~xxx
```

### Start All Monitors (comanda corectă):
```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo" && \
rm -f process_watchdog.lock process_command_center.lock process_setup_executor.lock process_realtime_monitor.lock data/deep_sleep_state.json 2>/dev/null; \
.venv/bin/python watchdog_monitor.py --interval 60 >> logs/watchdog.log 2>&1 & sleep 2 && \
.venv/bin/python telegram_command_center.py >> logs/command_center.log 2>&1 & sleep 2 && \
.venv/bin/python setup_executor_monitor.py --loop >> logs/setup_executor_monitor.log 2>&1 & sleep 2 && \
.venv/bin/python realtime_monitor.py >> logs/realtime_monitor.log 2>&1 & echo DONE
```

### Verificare log-uri live:
```bash
tail -f logs/setup_executor_monitor.log
tail -f logs/realtime_monitor.log
tail -f logs/command_center.log
```

---

## SECȚIUNEA 7 — INFORMAȚII TEHNICE PENTRU GEMINI

### Python Environment:
```
Path:    /Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/.venv/bin/python
Python:  3.x (venv)
```

### Dependințe principale:
```python
pandas, numpy        — Procesare date OHLCV
loguru               — Logging avansat (logger.success, logger.critical etc.)
requests             — HTTP calls (Telegram, cTrader API)
python-dotenv        — .env file pentru credențiale
```

### Variabile de mediu necesare (în .env):
```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
CTRADER_CLIENT_ID=...
CTRADER_CLIENT_SECRET=...
CTRADER_ACCESS_TOKEN=...
CTRADER_ACCOUNT_ID=...
```

### DataProvider (cTrader API):
- Sistem de rate limiting cu retry exponențial
- Cache intern pe timeframe: D1=4h, H4=30m, H1=5m
- Simboluri suportate: toate perechile disponibile la IC Markets

---

## SECȚIUNEA 8 — VERSIONING HISTORY

| Versiune | Ce s-a adăugat |
|---|---|
| V8.1 | Body closure în detect_choch_and_bos() (body_high/body_low) |
| V8.2 | REVERSAL vs CONTINUITY equilibrium calculation separat |
| V9.1 | Anti-spam rejection logging (4h cooldown) |
| V9.3 | Deep Sleep mode (stop scanare la daily loss limit) |
| V10.2 | Fix: READY rejection nu mai activează Deep Sleep |
| V10.3 | Strategy tagging în signals.json (Comment + StrategyTag fields) |
| V10.4 | D1 Bias + 4H Sync flow complet (REVERSAL/CONTINUITY_4H_SYNC) |
| V10.5 | **SESIUNILE 2-4:** Equity fix (×2), Explicit 4H body closure, READY bypass fix, FVG notification fix, max_positions=5, **Strategy Lock Guard** (reject dacă strategy_type neclar), **Fibonacci pip_multiplier instrument-aware** (JPY/XAU fix), **Automatic Handshake** (h4_sync_fvg + strategy_locked în JSON), READY path 4H revalidation |

---

*Document generat de GitHub Copilot (Claude Sonnet 4.6) pentru handoff către Gemini*
*🔱 AUTHORED BY ФорексГод 🔱 | 🏛️ INSTITUTIONAL TERMINAL 🏛️*
