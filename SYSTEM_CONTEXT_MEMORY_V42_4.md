# SYSTEM CONTEXT MEMORY — Apollo V42.4

**Autoritate de context pentru sesiuni Cursor viitoare**  
**Proiect:** Apollo / Glitch in Matrix  
**Repository:** `ForexGod-ai/apollo-vps`  
**Branch activ:** `cursor/v36-3-radar-live-sync`  
**Ultima actualizare sesiune:** 2026-06-11  
**Versiune document:** V42.4 (Master Changelog V40.5 → V42.4)

> Acest fișier înlocuiește presupunerile din conversații vechi despre lifecycle JSON, merge cross-process, Range Lock și executor blind. **Dacă există conflict între un prompt vechi și acest document, acest document câștigă.**

---

## 1. Rezumat versiuni și evoluția pipeline-ului

### 1.1 De la zombie la arhitectură securizată

| Perioadă | Problemă dominantă | Stare |
|--------|-------------------|-------|
| **V37.14** | `/status` P/L deconectat de Deep Sleep; setup-uri `TRADE_OPEN` rămân în JSON după SL/TP (zombie până la ~14 zile) | Parțial remediat |
| **V40.3** | SOFT TTL (4 zile fără atingere POI) → `EXPIRED_TIMEOUT`; asymmetry `strategy_type` | TTL activ, protecții incomplete |
| **V40.5** | Dashboard și `/status` afișau ore UTC; PNL zilnic greu de reconciliat | **Rezolvat** |
| **V42** | Macro D1 stale în JSON (ex. GBPNZD SELL blocat de Range Lock bearish); scanner păstra bias vechi | **Rezolvat** |
| **V42.2** | Race merge executor rescria `INVALIDATED`; lipsă multi-entry; fără hook broker → `CLOSED` | **Rezolvat** |
| **V42.3** | Execuție posibilă când CHoCH LTF ≠ bias Daily | **Rezolvat** |
| **V42.4** | ~220 linii cod mort în executor; funcții orfane; fallback-uri `strategy_type` contradictorii | **Rezolvat** |

### 1.2 Pipeline operațional (adevărul actual)

```
daily_scanner.py (1×/zi, ~07:00 Europe/Bucharest)
    └─ smc_detector.scan_for_setup()  → macro: direction, strategy_type, POI, d1_signal_*
    └─ save_monitoring_setups()       → V42 LIVE AUTHORITY merge în monitoring_setups.json

multi_tf_radar.py (~30s)
    └─ scan H4/H1 Always-On           → radar_*, EXECUTE_NOW, h4_structure_locked
    └─ Poarta 1/2 invalidare          → INVALIDATED, COMPLETED_WITHOUT_ENTRY
    └─ V42.3 dezarmare                → EXECUTE_NOW=False dacă LTF ≠ D1

setup_executor_monitor.py (~5s)
    └─ singur trigger execuție        → EXECUTE_NOW=True (V19.8) + READY forțat (legacy)
    └─ V42.2 multi-entry              → PARTIAL_OPEN → TRADE_OPEN
    └─ V42.3 hard gate                → blocare ordin dacă D1 ≠ radar CHoCH
    └─ merge write-back               → fresh terminal status câștigă (V42.2)

position_monitor.py (~10s)
    └─ trade_history.json             → Telegram open/close
    └─ V42.2 broker hook              → symbol fără poziții open → status CLOSED în JSON

                    monitoring_setups.json  ← singura sursă de adevăr pentru watchlist
```

**Separare responsabilități (inviolabilă):**

- **D1 / Scanner** = autoritate macro (direction, strategy, POI, `d1_signal_*`).
- **Radar 4H/1H** = timing intrare, `EXECUTE_NOW`, invalidare structurală LTF — **nu** rescrie macro D1.
- **Executor** = mâini (ordine cTrader) — **nu** recalculează bias D1; așteaptă `EXECUTE_NOW` de la Radar.
- **Position Monitor** = adevăr broker pentru închidere poziții → `CLOSED`.

---

### 1.3 Patch-uri implementate în sesiunea curentă

#### V40.5 — Timezone Dashboard & Live Daily PNL Recovery

| Componentă | Schimbare |
|------------|-----------|
| `dashboard_time_utils.py` | Helper UTC → `Europe/Bucharest` pentru afișare close times |
| `dashboard_server.py` | API dashboard servește `trade_history.json` cu ore RO |
| `telegram_command_center.py` | `/status` → `_status_daily_pnl()` cu zi calendaristică Bucharest; recovery PNL live din `trade_history.json` / broker sync |
| `setup_executor_monitor.py`, `daily_scanner.py`, `unified_risk_manager.py`, `macro_rates.py` | Aliniere fus `Europe/Bucharest` pentru reset zilnic, scan schedule, rapoarte |

**Scop:** operatorul vede aceeași zi de trading în Dashboard, `/status` și rapoarte — fără drift UTC vs RO.

---

#### V42 — Live Structure Authority + Smart Range Lock (Forex / GBPNZD)

| Componentă | Schimbare |
|------------|-----------|
| `smc_detector.py` | `compute_structural_range()`: INSIDE range → bias din ultimul semnal D1 filtrat, **nu** bearish forțat |
| `smc_detector.py` | `_is_internal_range_signal()`: CHoCH bullish reversal (`previous_trend == bearish'`) sau body close peste LH local — **nu** filtrat ca zgomot |
| `smc_detector.py` | `determine_daily_trend()` / `scan_for_setup()`: eliminat override `locked_bias`; eliminat kill switch V40 care forța direcția range lock |
| `smc_detector.py` | `infer_d1_strategy_type()`: fără realignare forțată la `locked_bias` |
| `daily_scanner.py` | `save_monitoring_setups()`: macro override la scan valid — ramura „PĂSTRAT” eliminată |
| `daily_scanner.py` | `_apply_v42_macro_override()`: live D1 înlocuiește JSON stale; păstrează câmpuri executor; reset `radar_*` la flip direction/strategy |
| `daily_scanner.py` | `_macro_overwrite_blocked()`: blochează overwrite când trade activ |
| `daily_scanner.py` | `_trade_setup_to_monitoring_dict()`: metadate `d1_signal_type`, `d1_signal_bar`, `d1_signal_price`, `d1_scan_date` |

**Scop:** GBPNZD (și Forex similar) primește bias D1 live la scan dimineața — fără JSON zombie SELL când structura D1 a flip-uit la BUY/reversal.

---

#### V42.2 — Multi-Entry Engine + Recovery Lifecycle

| Componentă | Schimbare |
|------------|-----------|
| `setup_executor_monitor.py` | `_apply_multi_entry_post_fill()`: primul fill (ex. 1H) → `PARTIAL_OPEN`; toate layerele planificate (1H+4H) → `TRADE_OPEN` |
| `setup_executor_monitor.py` | `_merge_processed_with_fresh_radar()`: dacă `fresh.status ∈ {INVALIDATED, CLOSED, COMPLETED_WITHOUT_ENTRY}` → **fresh câștigă** peste RAM executor |
| `setup_executor_monitor.py` | `_cleanup_monitoring_setups()`: `PARTIAL_OPEN`/`TRADE_OPEN` **imune** la ștergere pe vârstă; `CLOSED` → evicție imediată |
| `multi_tf_radar.py` | `PARTIAL_OPEN` **exclus** din `_SKIP_STATUSES` — radar continuă scanarea pentru layer 4H |
| `multi_tf_radar.py` | Nu mai șterge `EXECUTE_NOW` automat la `entry1_filled` dacă status = `PARTIAL_OPEN` |
| `position_monitor.py` | `_mark_symbol_closed_in_monitoring()`: zero poziții broker pentru symbol → scriere atomică `status=CLOSED` |
| `daily_scanner.py` | `PARTIAL_OPEN` în `_ACTIVE_STATUSES`; SOFT TTL și V40 bias invalidate **sari** peste `PARTIAL_OPEN`/`TRADE_OPEN` |

**Câmpuri JSON multi-entry:** `multi_entry_plan` (default `['1H','4H']`), `entries_filled_tfs`, `multi_entry_pending`, `entry1_trigger_tf`, `entry2_*`.

**Scop:** eliminare setup-uri zombie, execuție stratificată 1H apoi 4H, închidere confirmată de broker.

---

#### V42.3 — Hard Gate sincron structural D1 = H4 = 1H

| Componentă | Schimbare |
|------------|-----------|
| `setup_executor_monitor.py` | `_v423_structural_sync_ok()`: înainte de ordin cTrader — `direction` (buy/sell) trebuie aliniat cu `radar_4h_choch_direction` / `radar_1h_choch_direction` (bullish/bearish) pe TF-ul trigger |
| `setup_executor_monitor.py` | Mismatch → `EXECUTE_NOW=False`, log `[⚠️ V42.3 ALINIERE]` |
| `multi_tf_radar.py` | `_v423_force_disarm_execute_now()`: H4/H1 direction mismatch vs Daily → dezarmare instant + flush atomic JSON |
| `multi_tf_radar.py` | `_arm_execute_now()`: refuz arming dacă LTF misaligned |

**Scop:** interzicere execuție când CHoCH mic contrazice bias-ul Daily — regula de fier SMC.

**Notă:** `TRADE_OPEN` nu este dezarmat/modificat de V42.3 (poziție deja deschisă).

---

#### V42.4 — Curățenie arhitecturală + unificare default-uri

| Componentă | Schimbare |
|------------|-----------|
| `setup_executor_monitor.py` | **Eliminat** bloc unreachable V3.x (~220 linii): `KEEP_MONITORING` hardcodat → ramuri Fibo/CHOCH_1H/EXECUTE_ENTRY1/RR barriers |
| `setup_executor_monitor.py` | **Eliminat** `_check_radar_entry()`, `_check_pullback_entry()` (stub-uri moarte) |
| `setup_executor_monitor.py` | **Eliminat** fetch OHLC redundant post-EXECUTE_NOW (D1/H4/H1 nefolosit) |
| `daily_scanner.py` | **Eliminat** `_structural_rehydrate_needed()`, `_level_differs()` (orfane post-V42) |
| `smc_detector.py` | **Simplificat** atribuire `strategy_type` (fără dublă suprascriere CHoCH-vs-BOS apoi rescriere) |
| `smc_detector.py` | **Eliminat** guard inaccesibil `gbp_confirmed` |
| **Global** | Fallback canonic `strategy_type = 'reversal'` (aliniat `TradeSetup` dataclass) |

**Scop:** mentenanță, CPU/memorie VPS, zero risc de reactivare accidentală a fluxului V3.x pullback.

**Log startup:** `[V42.4 CLEANUP] Successfully purged legacy branches and unified core system data defaults.`

---

## 2. Jurnal modificări per fișier (Touched Files Matrix)

### 2.1 `daily_scanner.py`

| Funcție / zonă | Reguli V42.x |
|----------------|--------------|
| `save_monitoring_setups()` | Smart merge păstrează active; V42 macro override în loc de „PĂSTRAT”; SOFT TTL 4 zile doar pe `MONITORING`/`WAITING_D1_PULLBACK` |
| `_macro_overwrite_blocked()` | Blochează rescriere macro dacă `entry1_filled`, `TRADE_OPEN`, `PARTIAL_OPEN` sau poziție deschisă pe symbol |
| `_apply_v42_macro_override()` | Live scan înlocuiește POI/direction/strategy; păstrează `_EXECUTOR_PRESERVE_KEYS`; reset `radar_*` + `EXECUTE_NOW` la flip macro |
| `_norm_strategy_type()` | **V42.4:** fallback `'reversal'` (nu `'continuation'`) |
| `_ACTIVE_STATUSES` | Include `PARTIAL_OPEN`, `TRADE_OPEN` |
| V40 bias invalidate loop | **V42.2:** skip dacă `PARTIAL_OPEN` / `TRADE_OPEN` |
| ~~`_structural_rehydrate_needed()`~~ | **V42.4:** șters (orfan) |

---

### 2.2 `smc_detector.py`

| Funcție / zonă | Reguli V42.x |
|----------------|--------------|
| `TradeSetup.strategy_type` | Default canonic: `"reversal"` |
| `compute_structural_range()` | **V42:** INSIDE range → bias din semnal D1, nu lock bearish implicit |
| `_is_internal_range_signal()` | **V42:** CHoCH reversal bullish + body close peste LH — semnal valid |
| `determine_daily_trend()` | **V42:** fără early return pe `locked_bias`; filtrare apoi ultim semnal |
| `scan_for_setup()` | **V42:** fără override `current_trend = locked_bias`; fără V40 GUARD final range |
| `infer_d1_strategy_type()` | **V42:** fără realignare forțată la lock |
| `scan_for_setup()` L3493+ | **V42.4:** o singură atribuire `strategy_type = reversal if CHoCH else continuation` |
| ~~`gbp_confirmed` guard~~ | **V42.4:** șters — confirmare 1H exclusiv în radar la execuție |
| `calculate_choch_fibonacci()` | **V42.4:** default param `strategy_type='reversal'` |

---

### 2.3 `multi_tf_radar.py`

| Funcție / zonă | Reguli V42.x |
|----------------|--------------|
| `_SKIP_STATUSES` | **V42.2:** `PARTIAL_OPEN` **NU** e skip — doar `TRADE_OPEN` + terminale |
| `_update_setup_with_radar()` | **V42.2:** la `PARTIAL_OPEN`, păstrează/re-armează EXECUTE_NOW pentru 4H; **V42.3:** dezarmare pe H4/H1 mismatch |
| `_apply_lifecycle_gates()` | Poarta 1 (swing break), Poarta 2 (TP fără entry); **Poarta 3 eliminată** (V35) |
| `_batch_sync_to_monitoring_setups()` | Cleanup `_DEAD` include `CLOSED`; log `[V42.2 EVICTION]` |
| `_v423_ltf_misalignment()` / `_v423_force_disarm_execute_now()` | **V42.3:** sincron D1 vs LTF |
| `_arm_execute_now()` | **V42.3:** guard înainte de arming |
| `_evaluate_confirmed_pullback_latch()` | **V42.2:** latch permis pentru TF-uri din `multi_entry_pending` când `PARTIAL_OPEN` |
| `setup_type` fallback | **V42.4:** `'reversal'` când gol |

**Notă audit:** `EXPIRED_TIMEOUT` în `_DEAD` — **produs de scanner** (V40.3 SOFT TTL), nu de radar.

---

### 2.4 `setup_executor_monitor.py`

| Funcție / zonă | Reguli V42.x |
|----------------|--------------|
| `_process_monitoring_setups()` | **V42.4:** flux activ = EXECUTE_NOW + READY; fără V3.x pullback |
| Bloc V19.8 `EXECUTE_NOW` | Execuție structurală live SL/TP; **V42.3** gate înainte de broker |
| `_apply_multi_entry_post_fill()` | **V42.2:** PARTIAL_OPEN / TRADE_OPEN |
| `_merge_processed_with_fresh_radar()` | **V42.2:** `_FRESH_TERMINAL_STATUSES` → fresh wins |
| `_cleanup_monitoring_setups()` | **V42.2:** protecție open trades; evicție `CLOSED` |
| `_v423_structural_sync_ok()` | **V42.3:** hard gate aliniere |
| ~~Bloc L1784–L2007 (V3.x)~~ | **V42.4:** eliminat complet |
| ~~`_check_radar_entry()` / `_check_pullback_entry()`~~ | **V42.4:** eliminate |

**Executor activ post-V42.4:** ~2646 linii (față de ~2900+ cu dead code).

---

### 2.5 `position_monitor.py`

| Funcție / zonă | Reguli V42.x |
|----------------|--------------|
| `_atomic_write_monitoring()` | `.tmp` + `os.replace()` |
| `_mark_symbol_closed_in_monitoring()` | **V42.2:** broker zero open → `CLOSED` |
| `check_for_new_positions()` | După `new_closed`, dacă symbol ∉ `open_positions` → mark CLOSED |

---

### 2.6 Fișiere auxiliare V40.5 (context operațional)

| Fișier | Rol |
|--------|-----|
| `dashboard_server.py` | Dashboard API cu timezone RO |
| `dashboard_time_utils.py` | Conversie UTC → Bucharest |
| `telegram_command_center.py` | `/status` PNL zilnic live, recovery state |

---

## 3. Matrice stări JSON (Definitions of Done)

### 3.1 Lifecycle principal (multi-entry V42.2)

```
MONITORING / WAITING_* / READY
        │
        │  Radar: EXECUTE_NOW + Executor fill layer 1 (ex. 1H)
        ▼
   PARTIAL_OPEN          ← entry1_filled; multi_entry_pending = ['4H'] (typical)
        │
        │  Radar: re-arm EXECUTE_NOW 4H + Executor fill layer 2
        ▼
   TRADE_OPEN            ← toate TF-urile din multi_entry_plan completate
        │
        │  Position Monitor: broker raportează 0 poziții pe symbol
        ▼
   CLOSED                ← scriere atomică imediată
        │
        │  Radar batch sync + Executor cleanup (<30s tipic)
        ▼
   [evicted din JSON]    ← paritate liberă pentru scan viitor
```

### 3.2 Stări terminale (moarte structurală / fără trade)

| Status | Produs de | Evicție JSON |
|--------|-----------|--------------|
| `INVALIDATED` | Radar Poarta 1 (swing macro spart) | Radar batch + merge fresh wins |
| `COMPLETED_WITHOUT_ENTRY` | Radar Poarta 2 (TP atins fără entry) | Idem |
| `EXPIRED_TIMEOUT` | Scanner V40.3 SOFT TTL (4 zile, POI neatins) | Radar `_DEAD` |
| `EXPIRED` / `FAILED` / `CANCELLED` | Executor / scanner | Executor cleanup |
| `CLOSED` | **Position Monitor** (broker confirmat) | **Evicție imediată** (<30s) |

### 3.3 Stări protejate (interdicții absolute)

**Niciun proces automat nu poate:**

1. **Modifica macro D1** (direction, POI, strategy, `d1_signal_*`) pentru setup-uri cu:
   - `status ∈ {PARTIAL_OPEN, TRADE_OPEN}`
   - `entry1_filled == true`
   - poziție deschisă pe symbol în `trade_history.json`

2. **Șterge sau expira** (`SOFT TTL`, V40 bias invalidate, cleanup vârstă 14 zile) setup-uri `PARTIAL_OPEN` / `TRADE_OPEN` **fără** confirmare broker → `CLOSED`.

3. **Rescrie** status terminal din JSON fresh (`INVALIDATED`, `CLOSED`, `COMPLETED_WITHOUT_ENTRY`) cu starea stale din RAM executor (V42.2 merge veto).

4. **Executa** `EXECUTE_NOW` când CHoCH LTF (4H/1H) contrazice direction Daily (V42.3).

**Excepții permise:**

- Radar poate invalida structural (`INVALIDATED`) un setup `PARTIAL_OPEN` dacă Poarta 1 detectează spargere swing macro — protecție risc, nu TTL.
- Executor poate completa layer 2 pe `PARTIAL_OPEN` cu position guard bypass pentru scale-in (`_scale_in_ok`).

### 3.4 Câmpuri cheie JSON (referință rapidă)

| Câmp | Setat de | Consumat de |
|------|----------|-------------|
| `direction`, `strategy_type`, `poi_*`, `d1_signal_*` | Scanner / V42 override | Radar, Executor, Telegram |
| `radar_*`, `EXECUTE_NOW`, `execute_now_trigger_tf` | Radar | Executor |
| `entry1_filled`, `entries_filled_tfs`, `multi_entry_pending` | Executor | Radar (layer 2), Scanner guards |
| `status` | Toate straturile | Toate straturile |
| `closed_at`, `closed_reason` | Position Monitor | Audit |

---

## 4. Reguli de merge și concurență (anti-amnesie)

### 4.1 Merge executor write-back (V42.2)

```python
# Prioritate normală: processed (executor RAM) peste fresh
merged = {**fresh, **processed}

# EXCEPȚIE terminală: fresh status ∈ {INVALIDATED, CLOSED, COMPLETED_WITHOUT_ENTRY}
merged = {**processed, **fresh}  # fresh câștigă
```

### 4.2 Scriere atomică (obligatoriu)

Pattern: `monitoring_setups.json.tmp` → `os.replace()`  
Folosit de: executor, radar flush, position monitor.

---

## 5. Log-uri de trasabilitate (grep-friendly)

| Tag | Semnificație |
|-----|--------------|
| `[V42 LIVE AUTHORITY]` | Macro re-hydrated din scan D1 |
| `[V42 CONFLICT]` | Macro overwrite blocat (trade activ) |
| `[V42.2 MULTI-ENTRY]` | PARTIAL_OPEN / TRADE_OPEN post-fill |
| `[V42.2 MERGE]` | Fresh terminal status wins merge |
| `[V42.2 EVICTION]` | Purged din JSON (CLOSED) |
| `[V42.2 CLOSED]` | Position monitor marchează CLOSED |
| `[⚠️ V42.3 ALINIERE]` | Execuție blocată / EXECUTE_NOW dezarmat — D1 ≠ LTF |
| `[V42.4 CLEANUP]` | Startup post-curățenie cod mort |

---

## 6. Deploy & verificare post-patch

**Branch:** `cursor/v36-3-radar-live-sync`

```powershell
git pull origin cursor/v36-3-radar-live-sync
python -m py_compile setup_executor_monitor.py daily_scanner.py smc_detector.py multi_tf_radar.py position_monitor.py
# Restart: multi_tf_radar, setup_executor_monitor, position_monitor
```

**Smoke checks:**

1. `/status` — PNL zi Bucharest, monitoare ONLINE  
2. Log executor — absență referințe `_check_pullback_entry` / bloc Fibo  
3. După close broker — `[V42.2 CLOSED]` apoi `[V42.2 EVICTION]` în ≤30s  
4. GBPNZD / pereche cu flip D1 — `[V42 LIVE AUTHORITY]` la scan dimineață  

---

## 7. Datorii tehnice rămase (post-V42.4)

| Item | Severitate | Notă |
|------|------------|------|
| `_sync_to_monitoring_setups()` single-sync radar | Scăzut | Semi-mort; batch sync e calea VPS |
| `store_fvg_magnet()` print în scan | Scăzut | Side-effect fără consum pipeline |
| `EXPIRED_TIMEOUT` comentariu stale „Poarta 3” în radar | Cosmetic | Aliniat la V40.3 scanner TTL |
| Entry 2 scale-in legacy în executor (`entry1_filled` branch) | Info | Dezactivat explicit; multi-entry via EXECUTE_NOW V42.2 |

---

## 8. Istoric document

| Versiune | Data | Conținut |
|----------|------|----------|
| V42.4 | 2026-06-11 | Master memory V40.5–V42.4; post curățenie executor; state matrix multi-entry |

---

*Generat ca memorie contextuală permanentă — nu înlocuiește `AUDIT_ARCHITECTURAL_V42_1.md` (audit read-only pre-V42.2), ci documentează starea **implementată** a sistemului.*
