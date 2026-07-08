# Glitch in Matrix — End-to-End Integration Audit (Ground Truth)

**Data audit:** 2026-07-08  
**Branch:** `cursor/v36-3-radar-live-sync`  
**Mod:** read-only (zero modificări de cod)  
**Context utilizator:** Setup-uri cu CHoCH format din zone de interes (POI Daily) — structura macro corectă vizibilă, dar **EXECUTE_NOW nu declanșează execuție la broker**.

**Module auditate:**

| Modul | Rol |
|-------|-----|
| `smc_detector.py` | Generator structură SMC (TradeSetup) |
| `daily_scanner.py` | Pod JSON: TradeSetup → `monitoring_setups.json` |
| `multi_tf_radar.py` | Creier alerte, POI latch, armat `EXECUTE_NOW` |
| `setup_executor_monitor.py` | Sentinela lansare (5s loop) |
| `ctrader_executor.py` | Scriere `signals.json` |
| `unified_risk_manager.py` | Validare risc, lotaj, limite zilnice |

---

## Executive Summary

### Simptom raportat

Utilizatorul observă setup-uri unde:
- Daily POI / zona de interes este identificată corect
- CHoCH LTF (4H sau 1H) apare (inclusiv alerte Telegram structurale)
- **Ordinul nu ajunge la broker** — execuția eșuează tăcut sau fără feedback clar

### Top 3 root causes (ranked by probability)

| # | Root cause | Severitate | Efect |
|---|------------|------------|-------|
| **1** | **`daily_bias_active: True` hardcodat în scanner JSON** activează greșit V24.6 guard pe setup-uri cu FVG natural | **P0** | `execution_ready=False` chiar cu CHoCH vizibil, dacă 4H CHoCH nu e detectat live în acel ciclu radar |
| **2** | **Lanțul EXECUTE_NOW are 15+ porți**; unele dezarmează **fără Telegram** (V42.3 alignment, `_can_execute_execute_now`, deep sleep) | **P0** | CHoCH armat vizual pe card/alertă, dar `EXECUTE_NOW` nu persistă sau executorul skip-uiește |
| **3** | **Contract JSON incomplet** (`entry_price`, SL/TP absente din scanner) + RR shield pe date incomplete | **P1** | Blocaje downstream la armare sau la executor (SL structural, RR < 2.0) |

### Verdict cleanup Faze 1–3

**Nu există import Python rupt** către `execution_radar.py`, `_sync_to_monitoring_setups()`, sau `calculate_atr()` global. Regresia este de **semantică date / flag-uri JSON**, nu de simbol șters.

---

## 1. Diagnostic End-to-End Data Flow

### 1.1 Arhitectura canonică

```
IC Markets (cTrader Desktop)
    │
    ├── MarketDataProvider.cs     → localhost:8010  (OHLCV, /price, spread)
    └── TradeHistorySyncer.cs     → localhost:8767  (account, closed_trades)

smc_detector.scan_for_setup()
    ↓ TradeSetup (dataclass)
daily_scanner._trade_setup_to_monitoring_dict()
    ↓
monitoring_setups.json
    ↓
multi_tf_radar.run_scan()          [loop secundar, ~30s]
    ├── analyze_setup()            [SMC primitives live, NU re-scan Daily]
    ├── _track_mitigation_touch()  [POI latch]
    ├── _arm_execute_now()         [EXECUTE_NOW=True + flush JSON]
    └── _batch_sync_to_monitoring_setups()
    ↓
setup_executor_monitor.py          [loop 5s]
    ├── _can_execute_execute_now()
    ├── live OHLC fail-hard
    ├── structural SL/TP recalc
    ├── _final_safety_check (Guards 1–4)
    ├── _check_spread_guard (/price:8010)
    └── ctrader_executor.execute_trade()
    ↓
signals.json
    ↓
PythonSignalExecutor.cs (cBot)     [poll ~10s]
    ↓
Broker MARKET order
```

**Notă critică:** Radar **nu** reapelează `scan_for_setup()` în loop secundar. Citește `monitoring_setups.json` și rulează detecție LTF live via `SMCDetector.detect_choch_and_bos`, `detect_fvg`, swing detection.

### 1.2 TradeSetup exportat de smc_detector

**Fișier:** `smc_detector.py` L110–141 (dataclass), L4840–4875 (return `scan_for_setup`)

Câmpuri relevante pentru execuție:

| Câmp | Populat la scan | Persistat în JSON scanner |
|------|-----------------|---------------------------|
| `symbol`, `daily_choch`, `fvg` | Da | Parțial (poi_top/bottom) |
| `h4_choch`, `h1_choch` | Da | **Nu** |
| `entry_price`, `stop_loss`, `take_profit` | Da | **Nu** |
| `risk_reward`, `estimated_rr` | Da | **Nu** |
| `strategy_type`, `priority`, `status` | Da | Da |
| `daily_bias_active` | Da (`fvg._is_daily_bias_zone`) | **Greșit: always True** |
| `adr_lh/ll/hl`, `structural_breach` | Da (V43) | Da via `_v43_fields_from_setup` |
| `h4_sync_fvg_*` | Da | **Nu** |

### 1.3 Ce scrie daily_scanner în JSON

**Fișier:** `daily_scanner.py` L1543–1583

```python
out = {
    "symbol", "direction", "daily_bias", "strategy_type",
    "daily_bias_active": True,   # ← BUG P0: hardcodat, nu din TradeSetup
    "poi_top/bottom", "fvg_top/bottom",
    "daily_target_price": getattr(setup, 'daily_tp_price', None),
    "status", "setup_time", "d1_signal_type", ...
}
# LIPSESC: entry_price, stop_loss, take_profit, risk_reward
```

Bias fallback (L692–714) setează și el `daily_bias_active: True` — acolo e intenționat (POI synthetic).

### 1.4 Ce așteaptă multi_tf_radar

**Fișier:** `multi_tf_radar.py` L1631–1946 (`analyze_setup`)

| Cheie JSON | Obligatoriu | Fallback / efect |
|------------|-------------|------------------|
| `direction` | **Da** — absent → skip CRITICAL (L1680–1701) | — |
| `poi_top` / `fvg_top` | Recomandat | `daily_entry` dacă lipsă |
| `entry_price` | Nu | `0.0` (L1707–1708) |
| `daily_bias_active` | Nu | `False` default, dar JSON are `True` |
| `strategy_type` | Nu | `'reversal'` — activează V31.0 BOS guard |
| `poi_touch_latched` | Nu | False — POI latch din ciclu curent |

### 1.5 Referințe moarte post-cleanup (Faze 1–3)

| Symbol eliminat | Referințe Python live | Impact |
|-----------------|----------------------|--------|
| `execution_radar.py` | 0 | None runtime |
| `_sync_to_monitoring_setups()` | 0 — doar `_batch_sync_to_monitoring_setups` | None |
| `calculate_atr()` global | 0 — folosit `SMCDetector.calculate_atr()` instanță | None |
| `detect_strategy_type()` | 0 | None |

**Concluzie:** Cleanup-ul nu a rupt importuri. Problema e **contract JSON + gates EXECUTE**.

---

## 2. POI Touch Latch — Pândă vs Batch Sync

### 2.1 State machine V49/V50

**Fișier:** `multi_tf_radar.py` L405–478 (`_track_mitigation_touch`)

| Stare | Comportament |
|-------|--------------|
| Preț **în POI** + `validated=True` | Set `poi_touch_latched=True`, `radar_panda_active=True`, reset dedup alerte (L446–462) |
| Preț **ieșit din POI**, latch ON | **Latch păstrat** — CHoCH + retrace 60–80% permise în afara casetei (L421–437) |
| Preț **ieșit din POI**, latch OFF | Clear complet: `pop('poi_touch_latched')` (L438–443) |
| Re-entry fără `poi_first_touch_time` | Re-arm latch (L464–468) |

**Design intent (V49):** După touch POI macro, panda rămâne activă pentru secvența CHoCH → retrace Premium/Discount 60–80% → EXECUTE, chiar dacă prețul iese din caseta POI Daily.

### 2.2 Persistență în `_batch_sync_to_monitoring_setups`

**Fișier:** `multi_tf_radar.py` L2884–2999

Flux:
1. Re-citire **LIVE** `monitoring_setups.json` (anti-race V22)
2. Match `symbol` + direction (BUY/LONG, SELL/SHORT)
3. **Copiere chei in-memory** înainte de merge (L2940–2949):
   - `poi_touch_latched`, `poi_first_touch_time`, `radar_panda_active`
   - dedup alerte, `_poi_occupied`, `_h4_fvg_occupied`
4. `_update_setup_with_radar()` — **nu rescrie** `poi_touch_latched`
5. Atomic write via temp file + `os.replace`

**Riscuri identificate:**

| Risc | Severitate | Detaliu |
|------|------------|---------|
| Re-read JSON fail | P1 | L2916–2918: `return` fără write — **pierdere întreg ciclu** radar |
| Symbol+direction mismatch | P1 | Setup ne-match-uit → latch din memorie nu persistă |
| `analyze_setup` returnează `None` | P2 | Setup exclus din `collected_results` → batch sync nu-l atinge |
| D1 wick fetch silent fail | P1 | L1747–1748 `except: pass` → `poi_first_touch_time` anchor greșit |

### 2.3 Gate POI la armare EXECUTE_NOW

**Fișier:** `multi_tf_radar.py` L2351–2358

```python
_poi_arm_ok = daily_zone_validated OR setup.get('poi_touch_latched')
if not _poi_arm_ok:
    return  # skip arm — LOG info, fără Telegram
```

**Scenariu utilizator (CHoCH din POI, fără execuție):**
- CHoCH 4H detectat și alertă Telegram trimisă
- Dar `poi_touch_latched=False` (touch pierdut: wick fail, batch sync fail, sau preț niciodată `validated` în POI)
- `_arm_execute_now` **returnează fără** seta `EXECUTE_NOW`
- Utilizatorul vede CHoCH pe Telegram, dar executorul nu primește semnal

---

## 3. Lanțul CHoCH → EXECUTE_NOW → Broker

### 3.1 Condiții pentru `execution_ready=True`

**Fișier:** `multi_tf_radar.py` L1845–1921

Ordinea gates în `analyze_setup`:

```
1. tf_4h.status == EXECUTE_NOW_4H OR tf_4h.in_poi_entry_zone  → execution_ready
2. SAU tf_1h.status == EXECUTE_NOW_1H (dacă V43.2 H1 gate pass)
3. V43.2 POI/P-D block: dacă NOT daily_zone_validated AND NOT pd_guard_passed → execution_ready=False
4. V49 POI entry gate: execution_ready AND (daily_zone_validated OR poi_touch_latched)
5. V24.6 DAILY BIAS GUARD: dacă daily_bias_active AND execution_ready AND NOT tf_4h.choch_detected → BLOCK
6. V31.0 REVERSAL GUARD (în _update_setup_with_radar): BOS-only pe REVERSAL → no EXECUTE_NOW
7. V37.7 RR SHIELD: RR entry→TP vs SL < 2.0 → no EXECUTE_NOW
8. V42.3 LTF misalignment → _v423_force_disarm_execute_now
9. V50 H4 stale post-POI → dezarmare dacă fără CHoCH/BOS LIVE post-touch
```

### 3.2 De ce CHoCH vizibil ≠ EXECUTE_NOW

| Situație | Alertă CHoCH Telegram | EXECUTE_NOW armat | Motiv |
|----------|------------------------|-------------------|-------|
| CHoCH 4H alert V47 (≤3 bare post-POI) | Da | **Nu** | Alerta ≠ entry gate; EXECUTE cere retrace 60–80% + POI latch |
| CHoCH 4H dar preț nu în PD 60–80% | Da | Nu | V46 entry band |
| CHoCH 1H, 4H nealiniat | Da 1H | Nu | V43.2 H1 gate (L2362–2368) |
| CHoCH 4H, `daily_bias_active=True`, BOS nu CHoCH | Poate | Nu | V24.6 guard (L1912–1919) — **afectează TOATE setup-urile scanner** |
| REVERSAL + trigger BOS-only | Poate | Nu | V31.0 guard (L2705–2714) |
| `execution_ready=True` dar RR < 2.0 | Poate | Nu | RR shield (L2719+) |
| EXECUTE_NOW=True, V42.3 fail la executor | — | **Dezarmat silent** | setup_executor L1419–1433 |
| EXECUTE_NOW=True, deep sleep | — | Skip silent 5s | L1319 |
| EXECUTE_NOW=True, spread > 2.5p | — | Abort + Telegram (dedup 1h) | L1575–1583 |

### 3.3 Flux armare `_arm_execute_now`

**Fișier:** `multi_tf_radar.py` L2347–2457

Porți **înainte** de `EXECUTE_NOW=True`:

1. POI arm OK (validated OR latched)
2. V43.2: 1H entry → 4H aligned
3. V42.3: LTF ≠ Daily → force disarm
4. V40.9: cooldown 30min după `execute_now_blocked_at`
5. RR shield (din caller)
6. `_flush_execute_now_to_json` — scriere instant JSON (L2430)
7. Telegram alert — **o singură dată** per setup (dedup)

**Regula de aur V22.1 (L2679–2683):** Radar **setează** EXECUTE_NOW; doar executorul **consumă/șterge** (except V42.3 dezarmare).

---

## 4. Matricea Blocurilor — setup_executor_monitor

### 4.1 Flux complet

**Fișier:** `setup_executor_monitor.py` — loop 5s, `_process_monitoring_setups` L1310+

```
EXECUTE_NOW=True in JSON
    → Deep sleep?                    [SILENT skip]
    → _can_execute_execute_now?      [SILENT skip if false]
    → V42.3 structural sync          [SILENT dezarmare, NO Telegram]
    → Live OHLC H1/H4 + D1           [ABORT + Telegram]
    → Structural SL (min 30p)        [ABORT + Telegram]
    → Structural TP (D1 live)        [ABORT + Telegram]
    → Session risk cap 15%           [SILENT retry]
    → _final_safety_check Guards 1-4 [ABORT + Telegram]
    → _check_spread_guard :8010      [ABORT + Telegram, dedup 1h]
    → ctrader_executor.execute_trade [ABORT + Telegram if False]
    → signals.json → cBot ~10s       [Broker]
```

### 4.2 Spread Guard (/price port 8010)

**Fișier:** `setup_executor_monitor.py` L877–931

| Check | Condiție abort |
|-------|----------------|
| Rollover | 00:00–00:15 UTC |
| HTTP | status != 200 |
| Quote invalid | bid/ask/spread unusable |
| Too wide | spread_pips > max (default 2.5 din SUPER_CONFIG) |
| Offline | ConnectionError port 8010 |

**Pip conversion:**
- Primary: `(ask - bid) / get_pip_size(symbol)`
- Fallback: `data['spread'] / 10.0` (cTrader points → pips)

**Timeout:** HTTP 3s. **Verdict:** Logică corectă; abort cu Telegram (suprimat dedup 1h).

### 4.3 OHLC Fail-Hard

**Fișier:** `setup_executor_monitor.py` L829–873, L1454–1470

| Mod | Comportament |
|-----|--------------|
| `require_live=False` | Cache TTL; stale fallback permis |
| `require_live=True` | **Always fetch**; None → CRITICAL abort + Telegram |

Underlying: `ctrader_cbot_client.py` timeout 30s cu retry bar-count fallback.

**Verdict:** Timeout minor → abort explicit, **nu** skip silent.

### 4.4 _final_safety_check (Guards 1–4)

**Fișier:** `setup_executor_monitor.py` L2104–2177

| Guard | Condiție | Telegram |
|-------|----------|----------|
| #2b | SL < 30 pips | Da |
| #1 | RR net < 2.0 (post-commission) | Da |
| #2 | SL > max per symbol (40p FX, 30p XAU) | Da |
| #3 | Loss estimat > 5.1% balance | Da |
| #4 | h4_structure_locked=False OR unknown strategy | Da |

Auto-bypass: L1438–1441 setează `h4_structure_locked=True` când lipsește.

### 4.5 Blocaje SILENȚIOASE (prioritate investigație producție)

| Gate | Locație | Efect | Telegram |
|------|---------|-------|----------|
| Deep sleep | SEM L1319 | Skip tot cycle | No |
| `_can_execute_execute_now` false | L257–265 | Skip (entry1 filled, scale-in) | No |
| Position guard same symbol | L1377–1385 | WAITING_POSITION_CLOSE | No |
| **V42.3 alignment fail** | L1419–1433 | **EXECUTE_NOW=False** | **No** |
| Session risk 15% cap | L1527–1532 | Retry next cycle | No |
| URM rollover/duplicate | URM L858–874 | Reject | print only |
| Telegram dedup blocked | dedup 1h | Suppress repeat alerts | — |
| V40.9 executor cooldown | radar L2379–2388 | Skip re-arm 30min | No |

### 4.6 ctrader_executor + signals.json

**Fișier:** `ctrader_executor.py` L319–577

Pre-build rejection (L362–371):
- `stop_loss <= 0` or `take_profit <= 0` → return False
- SL == entry or TP == entry → return False

**Notă:** Executor recalculează SL/TP structural live — **nu** citește SL/TP din JSON scanner. Riscul e abort la recalcul eșuat, nu transmisie None din radar.

Lot floor: L417–419 force `lot_size >= 0.01`.

---

## 5. Reguli Strategice SL/TP

### 5.1 Model V19.8 / V40.8 (executor)

**Fișier:** `setup_executor_monitor.py` L1443–1482

| Component | Sursă | Timeframe |
|-----------|-------|-----------|
| Entry | `radar_4h_fvg_entry` OR `radar_1h_fvg_entry` OR `entry_price` | LTF FVG |
| Stop Loss | `_resolve_execute_now_sl()` | H4 dacă trigger=4H, else H1 |
| Take Profit | `_resolve_execute_now_tp(d1_live_only=True)` | **D1 structural only** |
| Min SL | 30 pips (`MIN_SL_PIPS`) | — |

Direction guards (L1485–1496): SL/TP invalid side → nullify → abort la gate SL min.

### 5.2 Ce lipsește din JSON scanner

Scanner **nu** persistă `entry_price`, `stop_loss`, `take_profit` din `TradeSetup`. Radar RR shield (L1997–2030) folosește:
- `setup.get('stop_loss')` — absent → shield incomplet
- `daily_target_price` OR `take_profit` — parțial

**Efect:** RR shield poate returna False pe eroare (`except: return False` L2028) → EXECUTE poate proceda fără shield sau cu date incomplete.

---

## 6. Analiza Matematică Risc — Cont ~$100

**Fișier:** `unified_risk_manager.py` L742–798 (`compute_lot_size`)

| Parametru | Valoare |
|-----------|---------|
| Risk target | 5% din balance (SUPER_CONFIG) |
| Min lot | 0.01 (clamp forțat) |
| Max lot | 2.0 |
| Guard#3 (executor) | Reject dacă loss la SL > **5.1%** balance |
| Balance fallback | env `ACCOUNT_BALANCE` default **1000** dacă broker offline |

### Exemple $100 balance, lot 0.01

| Pereche | SL pips | Loss USD | % balance | Rezultat |
|---------|---------|----------|-----------|----------|
| EURUSD | 30p | $3.00 | 3.0% | PASS |
| EURUSD | 40p | $4.00 | 4.0% | PASS |
| EURUSD | 55p | $5.50 | 5.5% | **BLOCK Guard#3** |
| GBPJPY | 30p | ~$3* | ~3% | PASS |

*JPY: pip_value dinamic via `_get_pip_value()`.

**Concluzie:** Nu există reject explicit „cont $100 prea mic". Constrângere indirectă: floor 0.01 lot + Guard#3 pe SL larg. Pe SL 30–40p FX, lotajul **trebuie** să treacă — problema utilizatorului **nu** e probabil limită de lotaj minim.

---

## 7. Post-Cleanup Regression Inventory

| Zonă | Status | Notă |
|------|--------|------|
| Importuri Python moarte | Clean | Faze 1–3 OK |
| `_batch_sync_to_monitoring_setups` | Active | Unic path sync (V22 merge) |
| `daily_bias_active` JSON | **Regresie semantică** | Hardcodat True — pre-date V24.6 |
| Entry/SL/TP JSON | **Regresie date** | Niciodată persistate din TradeSetup |
| POI latch V49 | Active | Design corect, risc persistență batch |
| Broker sync P&L (8767) | Fixed recent | weekly report + SYSTEM RESET |
| Docs `execution_radar` | Stale | Doar documentație |

---

## 8. Scenarii Concrete — CHoCH din POI, Fără Execuție

### Scenariul A: Alertă CHoCH Telegram, fără EXECUTE_NOW

**Cauză probabilă:** Alerta structurală V47 (≤3 bare post-POI) este **decoupled** de gate-ul V46 entry (POI + retrace 60–80%). Utilizatorul vede CHoCH confirmat pe card, dar prețul nu e în banda Premium/Discount → `_arm_execute_now` nu e apelat.

**Verificare VPS:** `monitoring_setups.json` → caută `EXECUTE_NOW`, `poi_touch_latched`, `radar_4h_status`, `retrace_pct`.

### Scenariul B: EXECUTE_NOW=True, ordin absent

**Cauză probabilă:** Executor gate silent (V42.3 alignment L1419–1433) sau deep sleep.

**Verificare VPS:** `logs/setup_executor*.log` → `[V42.3 ALINIERE]`, `[EXECUTE_NOW ABORT]`, `deep_sleep`.

### Scenariul C: V24.6 block pe setup FVG natural

**Cauză probabilă:** `daily_bias_active: True` hardcodat → guard cere CHoCH 4H real chiar pe setup-uri cu FVG Daily natural.

**Fix P0:** `daily_scanner.py` L1561 → `getattr(setup, 'daily_bias_active', False)`.

### Scenariul D: POI latch pierdut

**Cauză probabilă:** Batch sync fail (re-read JSON) sau D1 wick silent pass → `poi_touch_latched` never set → V49 POI gate block armare.

**Verificare VPS:** Log `[V49 POI GATE] skip EXECUTE_NOW arm`.

### Scenariul E: REVERSAL + BOS trigger

**Cauză probabilă:** V31.0 guard respinge BOS-only pe setup REVERSAL — așteaptă CHoCH autentic.

**Verificare:** Log `[V31.0 REVERSAL GUARD]`.

---

## 9. Plan Remedieri Urgente

### P0 — Restabilire execuție (implementare imediată)

| # | Acțiune | Fișier | Linie |
|---|---------|--------|-------|
| 1 | Fix `daily_bias_active` — nu hardcoda True | `daily_scanner.py` | L1561 |
| 2 | Persist `entry_price`, `stop_loss`, `take_profit`, `risk_reward` în JSON | `daily_scanner.py` | L1553–1581 |
| 3 | V42.3 alignment: Telegram când dezarmează EXECUTE_NOW | `setup_executor_monitor.py` | L1419–1433 |
| 4 | VPS checklist: 8010 + 8767 + cBot SignalExecutor + deep_sleep | ops | — |

### P1 — Robustness

| # | Acțiune | Fișier |
|---|---------|--------|
| 5 | `_batch_sync` re-read fail: retry 3x | `multi_tf_radar.py` L2916 |
| 6 | D1 wick fetch: log warning not bare pass | `multi_tf_radar.py` L1747 |
| 7 | RR shield except: fail-closed (block) not bypass | `multi_tf_radar.py` L2028 |
| 8 | Documentare decoupling alert CHoCH vs EXECUTE gate | docs | — |

### P2 — Observability

| # | Acțiune |
|---|---------|
| 9 | Script audit: per setup raportează block reason chain |
| 10 | Dashboard badge: EXECUTE_NOW + last_rejection_reason |

---

## 10. VPS Production Checklist

```
[ ] cTrader Desktop deschis, cont IC Markets conectat
[ ] MarketDataProvider cBot activ → curl http://localhost:8010/health
[ ] TradeHistorySyncer cBot activ → curl http://localhost:8767/
[ ] PythonSignalExecutor cBot activ (poll signals.json ~10s)
[ ] watchdog_monitor.py running (radar + executor + sync)
[ ] deep_sleep_state.json — verifică lockdown=False
[ ] data/daily_state.json — starting_balance corect (broker live)
[ ] monitoring_setups.json — per setup activ:
      EXECUTE_NOW, poi_touch_latched, radar_4h_choch_detected,
      execute_now_blocked_at, last_rejection_reason
[ ] logs/setup_executor*.log — caută V42.3, ABORT, spread guard
[ ] logs/multi_tf_radar*.log — caută V24.6, V49 POI GATE, V31.0
```

### Comenzi diagnostic rapide (Windows VPS)

```powershell
python -c "import json; d=json.load(open('monitoring_setups.json')); [print(s.get('symbol'), s.get('EXECUTE_NOW'), s.get('poi_touch_latched'), s.get('last_rejection_reason','')[:50]) for s in d.get('setups',[])]"

curl http://localhost:8010/health
curl http://localhost:8767/
```

---

## 11. Fișiere Cheie — Index Referințe

| Fișier | Funcții / zone critice | Linii |
|--------|------------------------|-------|
| `smc_detector.py` | TradeSetup, scan_for_setup | 110–141, 3429–4875 |
| `daily_scanner.py` | _trade_setup_to_monitoring_dict | 1543–1583 |
| `multi_tf_radar.py` | _track_mitigation_touch, analyze_setup, _arm_execute_now, _batch_sync | 405–478, 1631–1946, 2347–2457, 2884–2999 |
| `setup_executor_monitor.py` | EXECUTE_NOW block, spread guard, fail-hard | 257–305, 829–931, 1416–1643 |
| `ctrader_executor.py` | execute_trade, SL/TP zero guard | 319–577 |
| `unified_risk_manager.py` | compute_lot_size, validate_new_trade | 742–798, 826–949 |
| `radar_gates.py` | Shared LTF confirmation gates (V51) | — |
| `trade_manager.py` | fetch_broker_live (8767) | 204–265 |

---

## 12. Concluzie Finală

Sistemul **identifică corect structura macro** (SMC + scanner zilnic) și **poate detecta CHoCH LTF** (radar + alerte Telegram). Execuția eșuează din cauza unui **lanț lung de gates** între „CHoCH detectat" și „ordin la broker", unde:

1. **Alerta CHoCH ≠ EXECUTE_NOW** — condiții V46 (retrace 60–80%) sunt stricte
2. **`daily_bias_active: True` hardcodat** poate bloca setup-uri valide via V24.6
3. **Porți silențioase** (V42.3, deep sleep, `_can_execute_execute_now`) lasă utilizatorul fără feedback
4. **Cleanup Faze 1–3** nu a rupt codul, dar a expus inconsistențe JSON pre-existente

Document pregătit pentru prompt colosal de remediere P0/P1.

---

## 13. Remedieri V52 implementate (2026-07-08)

| Fix | Fișier | Status |
|-----|--------|--------|
| `daily_bias_active` din TradeSetup (nu hardcodat True) | `daily_scanner.py` | Done |
| Persist `entry_price`, SL, TP, `risk_reward` în JSON | `daily_scanner.py` | Done |
| P/D guard: latch post-POI nu mai cere `in_poi` simultan | `multi_tf_radar.py` `_compute_pd_guard_for_execute` | Done |
| Telegram când P/D blochează EXECUTE cu CHoCH activ | `multi_tf_radar.py` | Done |
| V42.3 alignment → Telegram blocked alert | `setup_executor_monitor.py` | Done |
| RR shield fail-closed | `multi_tf_radar.py` | Done |
| Batch sync re-read retry 3x | `multi_tf_radar.py` | Done |
| D1 wick fetch → log warning | `multi_tf_radar.py` | Done |

Test: `tests/test_v52_pd_guard_latch.py`

---

*Authored by integration audit — Glitch in Matrix / Apollo VPS — 2026-07-08*
