# AUDIT COMPLET — Pachetul `smc_detector/` și cei 4 Piloni ai Sistemului

> **Data audit:** 2026-08-14  
> **Branch:** `cursor/v36-3-radar-live-sync`  
> **Mod:** read-only (raport de mapare — fără modificări de cod la generare)  
> **Context:** Degradare precizie SMC după split monolit → module + scripturi externe de patch

---

## Notă critică — MASTER SPEC

Fișierul `docs/GLITCH_IN_MATRIX_MASTER_SPEC.md` **nu există în repository-ul curent** (căutare exhaustivă). Constituția SMC este dispersată în:

- comentarii inline V68 în `core_structure.py` (MASTER SPEC alignment)
- `docs/V67_MASTER_PLAN_AND_AUDIT.md`
- `docs/SMC_DETECTOR_FULL_AUDIT_V67.md`
- `docs/GLITCH_IN_MATRIX_INTEGRATION_AUDIT.md`

Raportul mapează **starea reală a codului**, nu un document absent.

---

## Cuprins

1. [Maparea fișierelor `.py` din `smc_detector/`](#1-maparea-fișierelor-py-din-smc_detector)
2. [Diagnosticul rupturii de citire SMC (D1 → 4H RADAR)](#2-diagnosticul-rupturii-de-citire-smc-d1--4h-radar)
3. [Plan de curățare și integrare a scripturilor de patch](#3-plan-de-curățare-și-integrare-a-scripturilor-de-patch)
4. [Reorganizarea și simplificarea fluxului canonic](#4-reorganizarea-și-simplificarea-fluxului-canon)
5. [Rezumat executiv](#5-rezumat-executiv)

---

## 1. MAPAREA FIȘIERELOR `.PY` DIN `smc_detector/`

### 1.1 Arhitectura generală — Mixin Composition

`SMCDetector` din `__init__.py` este un **facade** care compune 11 mixin-uri într-o singură clasă. Nu există ierarhie de import între module — dependențele sunt **la runtime prin MRO** (Method Resolution Order):

```
SMCDetector (__init__.py)
├── W1Mixin              (w1.py)
├── D1LegMixin           (d1_leg.py)
├── D1AuthorityMixin     (d1_authority.py)
├── PoiMixin             (poi.py)
├── FvgMixin             (fvg.py)
├── CoreStructureMixin   (core_structure.py)
├── CoreSwingsMixin      (core_swings.py)
├── ScanFinalizeMixin    (scan_finalize.py)
├── ScanSetupMixin       (scan_setup.py)
├── ScanOrchestratorMixin (scan.py)
└── ScanEntryMixin       (scan_entry.py)
         ↓
    models.py (dataclass-uri)
```

| Fișier | Rol | Input → Output |
|--------|-----|----------------|
| **`models.py`** | Tipuri canonice: `SwingPoint`, `CHoCH`, `BOS`, `FVG`, `OrderBlock`, `D1AuthContext`, `TradeSetup`, `StructuralRangeState`, `POIResolution` | Structuri pure — fără logică |
| **`core_swings.py`** | Pivoți geometrici + filtrare majori | OHLC → `List[SwingPoint]` |
| **`core_structure.py`** | CHoCH/BOS pe majori + range lock V40 | OHLC + swings → `(chochs, bos_list)` |
| **`d1_leg.py`** | Matrice pură D1: leg activ, REV/CONT, validitate | semnale + majors → `(signal, strategy, trend, leg_choch)` |
| **`d1_authority.py`** | Pipeline autoritar D1 | OHLC → `D1AuthContext` |
| **`fvg.py`** | Detectare FVG + P/D validation + quality score | OHLC + CHoCH → `FVG` |
| **`poi.py`** | POI D1: ADR + cascade FVG/OB | D1 context → `POIResolution` |
| **`w1.py`** | Bias W1 + W+D sync gate | W1 OHLC + D1 setup → bias/POI modificat |
| **`scan.py`** | Entry public `scan_for_setup()` | delegă la scan_setup |
| **`scan_setup.py`** | Corpul scanului (~700L): D1 auth → POI → 4H sync → status | dfs → handoff finalize |
| **`scan_entry.py`** | SL/TP structural 4H/D1, RR ≥ 4 | structură → entry/sl/tp |
| **`scan_finalize.py`** | Asamblează `TradeSetup` final | parametri → `TradeSetup` |

### 1.2 Graf dependențe cross-module

```
models.py (dataclasses)
    ↑
core_swings.py ←→ core_structure.py
    ↑                    ↑
d1_leg.py ──────────────┘
    ↑
d1_authority.py
    ↑
fvg.py ←→ poi.py
    ↑
w1.py (uses full detector sub-instance)
    ↑
scan_setup.py → scan_finalize.py
    ↑              ↑
scan.py      scan_entry.py
    ↑
__init__.py → SMCDetector
```

---

### 1.3 `core_swings.py` — Pivoți și Major Swings

**Clasă:** `CoreSwingsMixin`

**Ce calculează:**

1. **`detect_swing_highs/lows(df)`** — fractali adaptivi (FW=2/3 pe TF), cu cache `(id(df), len)`
2. **`filter_major_swings(df, swing_h, swing_l)`** — **Filtrează pivoții majori reali**:

```
Swing High MAJOR  ← close a trecut SUB body_low al ultimului Swing Low anterior
Swing Low MAJOR   ← close a trecut PESTE body_high al ultimului Swing High anterior
```

Aceasta este **poarta de intrare** pentru tot ce urmează. Micro-fractalele geometrice rămân disponibile pentru macro trend (`macro_trend_from_swings`), dar **NU generează CHoCH/BOS**.

3. **`macro_trend_from_swings(df)`** — HH+HL = bullish, LH+LL = bearish (pe majori dacă ≥3, altfel geometrici)
4. **`calculate_equilibrium_reversal/continuity(...)`** — 50% leg pre/post-CHoCH pentru Premium/Discount
5. **`detect_liquidity_sweep(...)`** — BSL/SSL înainte de CHoCH
6. **`has_confirmation_swing(...)`** — HL/LH post-CHoCH validation

**Helpers:** `_swing_body_high/low`, `_body_close_above/below_after`, `_last_swing_before`

**Legătură:** Consumat de `core_structure.py`, `d1_leg.py`, `poi.py`, `fvg.py`.

---

### 1.4 `core_structure.py` — Body-Close BOS/CHoCH

**Clasă:** `CoreStructureMixin`

**Ce calculează:**

1. **`detect_choch_and_bos(df)`** (V68, aliniat MASTER SPEC inline):
   - Iterează **doar pivoții majori** din `filter_major_swings()`
   - **Body-close strict:** `close > body_high` (bullish) / `close < body_low` (bearish) al pivotului anterior spart
   - `prev_trend == bearish` + body-close peste major high → **CHoCH bullish**
   - `prev_trend == bullish` + body-close sub major low → **CHoCH bearish**
   - Same-direction breaks → **BOS**

2. **`compute_structural_range(...)`** — V40/V40.1 macro LH/LL lock (+ crypto ceiling)
3. **`filter_internal_range_signals(...)`** — elimină semnale sub-structură în range locked

**Helpers:** `_bar_body_close_above/below`, `_is_internal_range_signal`, `_range_signal_level`

**Legătură:** Output-ul `(chochs, bos_list)` alimentează direct `build_d1_context()` → `_resolve_pure_d1_matrix()`.

---

### 1.5 `d1_leg.py` — Leg Activ, Reversal vs Continuation

**Clasă:** `D1LegMixin`

**Ce calculează — Matricea Pură D1 (`_resolve_pure_d1_matrix`):**

```
Pas 1: filter_major_swings() → major_highs, major_lows
Pas 2: _true_choch_flips() → flips cronologice
Pas 3: _resolve_active_leg_from_flips() → leg_choch activ
        ├─ confirmare flip via swing_broken (pivot spart)
        ├─ validitate via protected HL/LH + ultim Major High/Low
        └─ fallback: skip leg cu BOS opus post-flip
Pas 4: Reguli simetrice bear-before-bull (fără post-leg BOS / fără LH reclaim)
Pas 5: _filter_countertrend_pullback_bos() → BOS contrar = pullback dacă nu sparge range
Pas 6: _strategy_from_leg_choch():
        0 BOS post-leg → REVERSAL (CHoCH)
        ≥1 BOS post-leg → CONTINUATION (ultimul BOS)
Pas 7 (fallback): _resolve_active_direction_from_bos() când nu există leg CHoCH
```

**Funcții cheie (grupate):**

| Grup | Funcții |
|------|---------|
| Leg boundaries | `_protected_hl/lh_level_after_leg`, `_leg_origin_major_high/low`, `_latest_major_high/low_body` |
| Flip / invalidation | `_flip_threshold_for_*`, `_leg_invalidation_level_*`, `_pure_leg_still_valid_at` |
| Resolution | `_resolve_active_leg_from_flips`, `_resolve_active_direction_from_bos`, `_resolve_pure_d1_matrix` |
| Strategy | `_strategy_from_leg_choch`, `_demote_post_leg_choch_to_bos`, `_classify_d1_strategy` |
| Validation | `_major_reversal_confirmed`, `_leg_choch_still_valid`, `resolve_structural_bias_fallback` |

**Funcții legacy ELIMINATE** (prezent doar în `smc_detector.py.bak`):

- `_bearish_authority()`
- `_resolve_orphan_d1_bias()`
- `_bear_crash_leg_still_active()` / `_bull_rally_leg_still_active()`
- `_crash_origin_major_high()` / `_crash_origin_major_low()`
- `_countertrend_bos_is_pullback()`
- `_pseudo_leg_from_bos()` → înlocuit cu `_leg_anchor_from_bos()`

---

### 1.6 `d1_authority.py` — `D1AuthContext` / `build_d1_context()`

**Clasă:** `D1AuthorityMixin`

**Pipeline canonic (V67):**

```
OHLC D1
  → detect_choch_and_bos()
  → detect_swing_highs/lows()
  → compute_structural_range()
  → filter_internal_range_signals()
  → _resolve_d1_leg() → _resolve_pure_d1_matrix()
  → _classify_d1_strategy() + _d1_signal_for_strategy()
  → [dacă neutral] resolve_structural_bias_fallback()
  → D1AuthContext { trend, strategy_type, direction, leg_choch, latest_signal, ... }
```

**API public:**

| Metodă | Rol |
|--------|-----|
| `build_d1_context(df, symbol, debug)` | Pipeline complet → `D1AuthContext` |
| `resolve_authoritative_d1_bias(df, symbol)` | `.as_dict()` wrapper |
| `macro_authority_supports_direction(...)` | Verificare direcție |
| `_resolve_d1_leg(...)` | Delegă la `_resolve_pure_d1_matrix` |

**Eliminat:**

- Override asimetric `macro_swings → current_trend` când neutral
- `_resolve_v426_latest_flip()` + `_bearish_authority()` / `_bullish_authority()` nested

---

### 1.7 `poi.py` & `fvg.py` — Zone Organice POI

#### `fvg.py` — `FvgMixin`

| Metodă | Rol |
|--------|-----|
| `detect_fvg(...)` | Scan wick-to-wick post-semnal, filtru P/D, gate ADR |
| `validate_fvg_zone(...)` | Preț în zona corectă P/D (55/45 buffers) |
| `calculate_fvg_quality_score(...)` | Scor 0–100 |
| `store_fvg_magnet()` / `get_fvg_magnets()` | Ultimele 2 FVG per TF |

#### `poi.py` — `PoiMixin`

| Metodă | Rol |
|--------|-----|
| `build_active_dealing_range(...)` | ADR V43 post-leg |
| `resolve_d1_poi(...)` | Cascadă organică: FVG → OB fallback |
| `detect_order_block(...)` | Lumânare opusă înainte de impuls CHoCH |
| `calculate_premium_discount_zones(df)` | Macro P/D pe 150 bare |
| `compute_structural_breach(...)` | ADR protected bound breach |

**Principiu Faza A:** Fără POI sintetic, fără clip Equilibrium forțat, fără JSON preserve bounds.

---

### 1.8 Fișiere scan + W1

#### `w1.py` — `W1Mixin`

- `calculate_w1_bias(df_w1)` — același pipeline D1 pe W1 (FW=3, 60 bars)
- `resolve_w1_poi(...)` — FVG W1 sau bandă P/D fallback
- `evaluate_w_d_sync(...)` / `apply_w_d_sync_gate(...)` — soft sync W1 vs D1

#### Pipeline scan (3 fișiere)

| Fișier | Entry | Rol |
|--------|-------|-----|
| `scan.py` | `scan_for_setup()` | Delegă la `_scan_through_poi_validation` |
| `scan_setup.py` | `_scan_through_poi_validation()` | D1 auth → POI → 4H sync → status |
| `scan_entry.py` | `calculate_entry_sl_tp()` | SL 4H structural, TP D1, RR ≥ 4 |
| `scan_finalize.py` | `_scan_finalize_trade_setup()` | Asamblează `TradeSetup` |

**Flux scan end-to-end:**

```
df_daily, df_4h, symbol
    → build_d1_context (sau inline) → trend, strategy, leg_choch, signals
    → build_active_dealing_range → ADR
    → resolve_d1_poi → FVG POI
    → detect_choch_and_bos (4H) → valid_h4_choch, h4_sync_fvg
    → calculate_entry_sl_tp → entry, SL, TP
    → TradeSetup(status, strategy_type, fvg, h4_choch, ...)
    → [optional] apply_w_d_sync_gate
```

---

### 1.9 `scripts/apply_pure_d1_patch.py` — Ce face și de ce e periculos

**Scop:** Script one-shot care **rescrie textual** `d1_leg.py` și `d1_authority.py` via regex/splice.

**Ce injectează:**

| Target | Acțiune |
|--------|---------|
| `d1_leg.py` | ~290 linii: `_latest_major_*`, `_pure_leg_still_valid`, `_resolve_pure_d1_matrix`, `_resolve_active_leg_from_flips`, etc. |
| `d1_leg.py` | Rescrie `_leg_invalidated_by_protected_breach`, `_find_leg_choch` |
| `d1_authority.py` | Șterge `_resolve_v426_latest_flip()` + `_bearish_authority()` |
| `d1_authority.py` | Elimină override `macro_swings → current_trend` |

**Status curent:** Logica patch-ului este **DEJA NATIVĂ** în `d1_leg.py` / `d1_authority.py`, cu **evoluții suplimentare** față de patch:

| Zonă | Patch | Cod nativ (evoluție) |
|------|-------|----------------------|
| Validitate leg | `_pure_leg_still_valid` cu flip thresholds | + protected HL/LH în `_pure_leg_still_valid_at` |
| Confirmare flip | `_flip_threshold_for_*` pe active leg | `_structural_break_level_for_signal` pe swing_broken |
| BOS flip | Single threshold | Dual: structural break + `_active_leg_range_boundary_for_flip` |
| Flip resolver | Fallback scan simplu | + `bos_list` param; skip leg cu BOS opus post-flip |
| BOS direction | Last/prior-opposite | Walk cronologic + `_forming_higher_low/_forming_lower_high` |
| Pure matrix | Straight resolution | + bear-before-bull, LH reclaim pentru crash pairs |

**Risc:** Re-rularea scriptului **corupe** fișierele (splice points stale, suprascrie logică evoluată).

---

## 2. DIAGNOSTICUL RUPTURII DE CITIRE SMC (D1 → 4H RADAR)

### 2.1 Flux end-to-end al celor 4 Piloni

```
PILON 1: smc_detector
  build_d1_context() → resolve_d1_poi() → scan_for_setup() → TradeSetup
       ↓
PILON 2: daily_scanner.py
  monitoring_setups.json (SMART MERGE)
       ↓
PILON 3: multi_tf_radar.py
  POI panda latch → analyze_setup (4H) → _arm_execute_now()
       ↓
PILON 4: setup_executor_monitor.py
  signals.json → PythonSignalExecutor.cs (cBot) → Broker
```

**Hub central:** `monitoring_setups.json`

---

### 2.2 a) PILON 1 — `smc_detector`: Degradarea preciziei D1

**Simptome raportate:**

- Pullback-uri clasificate ca BOS opus fals
- Panel monocrom (16/16 aceeași culoare)
- REV/CONT inversate pe JPY crosses

**Unde se pierde informația de pivot major:**

| Punct de ruptură | Mecanism | Efect |
|------------------|----------|-------|
| **Split monolit → mixin-uri** | 11 fișiere, MRO implicit, fără import explicit | Logică duplicată, ordine MRO fragilă |
| **Patch-uri externe paralele** | `apply_pure_d1_patch.py` + `smc_detector.py.bak` + `split_smc_detector.py` | Versiuni divergente ale aceleiași funcții |
| **Heuristici Frankenstein (eliminate recent)** | `_bearish_authority()`, `_crash_origin_major_high()` (wick peak) | Forțau bearish pe crash pairs — mascau bug-uri reale |
| **BOS walk fără pullback guard** | Counter-trend BOS confirmat doar pe swing_broken local | Bull BOS în bear leg = flip fals (ex. EURGBP Aug-14) |
| **`filter_internal_range_signals`** | Range lock V40 poate elimina CHoCH-uri valide | Trend neutral → fallback → bias incorect |
| **Scan fără `d1_ctx` cache** | `scan_setup.py` re-rulează D1 dacă caller omite cache | Rezultate diferite scanner vs JSON merge |

**Stare post-refactor Pure D1:**

- 132 teste trec, matrice simetrică pe major pivots
- Distribuție scan: 3 bullish / 13 bearish (mix real, nu monocrom)
- Risc rămas: distribuție bearish-heavy pe unele cache-uri

**Reguli canonice V66 (din V67 plan):**

```
CHoCH = flip structural O SINGURĂ DATĂ
BOS   = spargeri same-direction DUPĂ ce piciorul CHoCH a început
NU    = praguri arbitrare de timp (50/15 bare) pentru „maturitate"
```

---

### 2.3 b) PILON 2 — `daily_scanner.py`: POI și bias opuse chartului

**Entry points:**

| Funcție | Rol |
|---------|-----|
| `main()` | CLI entry |
| `DailyScanner.run_daily_scan()` | Loop principal perechi |
| `DailyScanner.scan_single_pair()` | Re-scan per pereche |
| `save_monitoring_setups()` | V33 SMART MERGE → JSON |
| `_trade_setup_to_monitoring_dict()` | TradeSetup → dict |

**Flux corect (V67):**

```python
_ctx = smc_detector.build_d1_context(df_daily, symbol)  # O SINGURĂ DATĂ
d1_auth_cache[symbol] = _ctx
setup = smc_detector.scan_for_setup(..., d1_ctx=_ctx)  # refolosește cache
```

**Puncte de ruptură:**

| Problemă | Unde | Efect |
|----------|------|-------|
| **Bias fallback fără POI** | `_hydrate_bias_fallback_poi()` apelează `_resolve_d1_leg` direct | Drift față de cache scanner |
| **`strategy_locked=True` la save** | JSON frozen cu etichetă REV/CONT veche | Reclassificare D1 intra-day ignorată |
| **`daily_bias_active: True` hardcodat** | Setup-uri cu FVG natural | Radar V24.6 guard blochează execuția |
| **No FVG organic → `None`** | Scanner creează bias_fallback fără POI | Radar: POI gate închis permanent |
| **Rehydrate drift** | `resolve_authoritative_d1_bias()` la merge | `_log_d1_bias_drift` — bias JSON ≠ bias live |
| **W1 lazy skip** | D1 neutral → W1 nu se descarcă | Lipsă context macro weekly |

**Output JSON:** `direction`, `d1_bias_direction`, `daily_bias`, `strategy_type`, `poi_top/bottom`, `adr_*`, `daily_bias_active`, `structural_breach`, `status`

---

### 2.4 c) PILON 3 — `multi_tf_radar.py`: Panda pe CHoCH fantomă

**Entry points:**

| Funcție | Rol |
|---------|-----|
| `MultiTFRadar.run_scan()` | Loop ~30s |
| `analyze_setup()` | Scan structural 4H per setup |
| `analyze_timeframe()` | CHoCH/BOS + FVG + retrace 60–80% |
| `_track_mitigation_touch()` | **POI panda state machine** |
| `_update_setup_with_radar()` | Scrie radar_* + armează EXECUTE_NOW |
| `_arm_execute_now()` | `EXECUTE_NOW=True`, flush JSON, Telegram |

**Mecanism panda (V49):**

```
poi_touch_latched=True  →  radar_panda_active=True  →  scan 4H chiar dacă prețul a părăsit POI
```

**Chei JSON panda:**

| Key | Semnificație |
|-----|--------------|
| `poi_touch_latched` | Primul touch POI validat |
| `poi_first_touch_time` | Ancoră post-POI CHoCH (V50) |
| `radar_panda_active` | Scan 4H activ după leave POI |
| `poi_radar_armed_at` | Timestamp touch |

**De ce CHoCH fantomă / vechi:**

| Cauză | Detaliu |
|-------|---------|
| Fereastră 300 bare 4H | CHoCH la -17 bars — valid structural, pre-POI |
| Filtru V50 post-POI | CHoCH pre-`poi_first_touch_time` eliminat la execuție |
| Alert ≤3 bars vs EXECUTE fără cap | Alertă tăcută, EXECUTE poate arma pe CHoCH vechi |
| Desincronizare D1 JSON vs 4H live | V42.3 dezarmează dacă misalignment |
| `allow_bos_trigger=True` cu panda | BOS post-CHoCH ca trigger CONT — confuz vizual |

**EXECUTE_NOW — condiții cumulative:**

- `poi_touch_latched` OR live POI validated
- `execution_ready` (retrace 60–80%)
- `pd_guard_passed`
- W+D sync not blocking
- REVERSAL: real 4H CHoCH (not BOS-only — V31.0)
- RR shield ≥ 2.0
- `daily_bias_active`: extra guard — need real 4H CHoCH

**Helpers partajate:** `poi_utils.py`, `radar_gates.py`

---

### 2.5 d) PILON 4 — `setup_executor_monitor.py`: EXECUTE_NOW ne-armat

**Entry points:**

| Funcție | Rol |
|---------|-----|
| `main()` | Daemon loop ~5s |
| `_process_monitoring_setups()` | Consumer principal |
| `_can_execute_execute_now()` | Poarta execuție |
| `_v423_structural_sync_ok()` | D1 vs `radar_4h_choch_direction` |
| `executor.execute_trade()` | Scrie `signals.json` |

**Lanțul complet (15+ porți):**

```
EXECUTE_NOW=True (din radar JSON)
  → _execute_trigger_active()
  → _can_execute_execute_now() — scale-in / entry1_filled
  → _check_execution_infrastructure() — cBot port 8010
  → _v423_structural_sync_ok() — D1 == radar_4h_choch_direction
  → live OHLC H4+D1 (fail-hard V48)
  → _resolve_execute_now_sl/tp
  → spread guard (/price:8010)
  → unified_risk_manager lot sizing
  → ctrader_executor.execute_trade() → signals.json
  → PythonSignalExecutor.cs cBot poll ~10s
```

**Top blockers:**

| # | Blocker | Layer | Simptom |
|---|---------|-------|---------|
| 1 | POI gate închis | Radar | `poi_touch_latched=False` → skip arm |
| 2 | `daily_bias_active` + fără 4H CHoCH | Radar V24.6 | `execution_ready=False` |
| 3 | V42.3 misalignment | Executor | Dezarmează EXECUTE_NOW fără Telegram |
| 4 | cBot 8010 offline | Infra | Alert la armare, execuție imposibilă |
| 5 | RR shield < 2.0 | Radar | `_rr_shield_blocks_execute` |
| 6 | Cooldown 30min | Radar | `execute_now_blocked_at` |
| 7 | Contract JSON incomplet | Scanner→Executor | SL/TP/entry absente |
| 8 | Race radar flush | Executor | Necesită `_merge_processed_with_fresh_radar` |

**cTrader handoff:** `ctrader_executor.py` → `signals.json` (array) → `PythonSignalExecutor.cs`

---

### 2.6 Căi divergente vs SMC canonic

| Item | Path | Risc |
|------|------|------|
| Legacy monolith backup | `smc_detector.py.bak` | Referință stale |
| Parallel 4H scanner | `check_4h_pullbacks.py` | Pre-V45, fără panda/V50/V68 |
| Patch script | `scripts/apply_pure_d1_patch.py` | Obsolet, re-run periculos |
| Bias fallback re-resolve | `_hydrate_bias_fallback_poi()` | Bypass `build_d1_context` |
| Identity snapshot | `_d1_identity_snapshot()` | Duplicat parțial pipeline D1 |
| Scan fără d1_ctx | Fallback în `scan_setup.py` | Re-rulare D1 completă |
| Alert vs EXECUTE gates | `radar_gates.py` ≤3b vs V52 EXECUTE | CHoCH fantomă vizual |

---

## 3. PLAN DE CURĂȚARE ȘI INTEGRARE A SCRIPTURILOR DE PATCH

### 3.1 Starea `scripts/apply_pure_d1_patch.py`

| Aspect | Status |
|--------|--------|
| Logica core injectată | ✅ **Deja nativă** în `d1_leg.py` + `d1_authority.py` |
| Evoluții post-patch | ✅ Cod nativ **depășește** patch-ul |
| Re-rulare safe | ❌ **Periculoasă** |
| Fișiere auxiliare duplicate | `smc_detector.py.bak`, `scripts/split_smc_detector.py`, `scripts/secondary_split_smc.py` |

### 3.2 Plan recomandat

**Pas 1 — Verificare integritate**

```bash
python3 -m py_compile smc_detector/*.py daily_scanner.py
python3 -m pytest tests/test_d1_bias_canonical.py tests/test_d1_leg_invalidation.py -q
python3 -m pytest tests/ -q
```

**Pas 2 — Ștergere datorie tehnică**

| Fișier | Acțiune |
|--------|---------|
| `scripts/apply_pure_d1_patch.py` | **ȘTERGE** — logică 100% nativă |
| `smc_detector.py.bak` | **ȘTERGE** sau mută în `archive/` |
| `scripts/split_smc_detector.py` | Actualizează referințe V426 → pure matrix |
| `scripts/secondary_split_smc.py` | Idem |

**Pas 3 — Checklist funcții patch → native**

| Funcție patch | Locație nativă | Extra față de patch |
|---------------|----------------|---------------------|
| `_resolve_pure_d1_matrix` | `d1_leg.py` | + bear-before-bull, LH reclaim |
| `_structural_break_level_for_signal` | `d1_leg.py` | **NOU** — swing_broken pivot |
| `_forming_higher_low/_forming_lower_high` | `d1_leg.py` | **NOU** — simetric HL/LH forming |
| `_active_leg_range_boundary_for_flip` | `d1_leg.py` | **NOU** — pullback guard BOS |
| `_resolve_d1_leg → pure matrix` | `d1_authority.py` | ✅ identic |
| Eliminare v426/bearish_authority | `d1_authority.py` | ✅ confirmat absent |

**Pas 4:** Zero acțiune necesară pe logică D1 — codul nativ este sursa de adevăr.

---

## 4. REORGANIZAREA ȘI SIMPLIFICAREA FLUXULUI CANONIC

### 4.1 Flux propus — un singur pipeline

```
Layer 1: PIVOTS (core_swings.py)
  detect_swing_highs/lows() → filter_major_swings()
       ↓
Layer 2: STRUCTURĂ (core_structure.py)
  detect_choch_and_bos() → compute_structural_range() → filter_internal_range_signals()
       ↓
Layer 3: LEG D1 (d1_leg.py)
  _resolve_pure_d1_matrix() → _strategy_from_leg_choch() — REV vs CONT
       ↓
Layer 4: AUTORITATE (d1_authority.py)
  build_d1_context() → D1AuthContext
       ↓
Layer 5: POI (poi.py + fvg.py)
  build_active_dealing_range() → resolve_d1_poi()
       ↓
Layer 6: SCAN (scan_*.py)
  scan_for_setup(d1_ctx=cached) → calculate_entry_sl_tp() → TradeSetup
       ↓
Layer 7: TRANSPORT
  daily_scanner → JSON → multi_tf_radar → EXECUTE_NOW → setup_executor_monitor → cTrader
```

### 4.2 Reguli canonice

| Regulă | Unde trăiește | Ce eliminăm |
|--------|---------------|-------------|
| Major pivots only pentru CHoCH/BOS | `core_structure.py` V68 | CHoCH pe fractali geometrici |
| Body-close strict (nu wick) | `core_structure.py` | Wick-peak crash origin |
| Pullback ≠ BOS flip | `_filter_countertrend_pullback_bos` | `_countertrend_bos_is_pullback` cu wick |
| 0 post-leg BOS = REVERSAL | `_strategy_from_leg_choch` | Praguri arbitrare timp |
| ≥1 post-leg BOS = CONTINUATION | Idem | `_bearish_authority()` forțat |
| Un singur `build_d1_context()` per pair | `daily_scanner` cache | `_hydrate` cu `_resolve_d1_leg` direct |
| POI organic sau None | `resolve_d1_poi` Faza A | Equilibrium clip, JSON preserve |
| Simetrie bullish/bearish | `_resolve_pure_d1_matrix` | Macro override unilateral |

### 4.3 Acțiuni de simplificare (prioritate)

| Prioritate | Acțiune | Impact |
|------------|---------|--------|
| **P0** | Șterge `scripts/apply_pure_d1_patch.py` + `smc_detector.py.bak` | Elimină confuzia versiuni |
| **P0** | Restaurează `docs/GLITCH_IN_MATRIX_MASTER_SPEC.md` în repo | Sursă unică constituție |
| **P1** | Unifică `_hydrate_bias_fallback_poi` → `build_d1_context` cache | Elimină drift D1 |
| **P1** | Audit `daily_bias_active` flag | Deblochează EXECUTE_NOW |
| **P1** | Aliniază alert gate (≤3 bars) cu EXECUTE gate (V52) | Elimină CHoCH fantomă |
| **P2** | Deprecate `check_4h_pullbacks.py` | Elimină cod mort |
| **P2** | Mută `_forming_higher_low/_forming_lower_high` în `core_swings.py` | Claritate layer 1 |
| **P3** | Module explicite vs mixin-uri MRO | Reduce fragilitate |

### 4.4 Teste validare canonică

```bash
python3 -m py_compile smc_detector/*.py daily_scanner.py
python3 -m pytest tests/test_d1_bias_canonical.py tests/test_d1_leg_invalidation.py -q
python3 -m pytest tests/test_w_d_sync.py tests/test_4h_alert_gates.py -q
python3 -m pytest tests/ -q
```

Scan uscat 16 perechi — mix LONG/SHORT, nu monocrom.

---

## 5. REZUMAT EXECUTIV

| Dimensiune | Verdict |
|------------|---------|
| **Split monolit → module** | Funcțional dar fragil (MRO, 11 mixin-uri, logică dispersată) |
| **Patch extern** | **Obsolet** — logică integrată nativ, re-rulare periculoasă |
| **Precizie D1** | **Restaurată** post Pure Matrix (132 tests pass) |
| **Lanț 4 piloni** | **Intact ca arhitectură**, rupt pe flag-uri JSON + porți EXECUTE + POI latch |
| **MASTER SPEC** | **Absent din repo** — risc major pentru audit viitor |
| **Prioritate #1** | Șterge patch scripts, restaurează spec, unifică `build_d1_context` |

---

## Anexe

### A. Index fișiere absolute

| Pilon / Modul | Path |
|---------------|------|
| Package init | `smc_detector/__init__.py` |
| Models | `smc_detector/models.py` |
| Swings | `smc_detector/core_swings.py` |
| Structure | `smc_detector/core_structure.py` |
| D1 leg | `smc_detector/d1_leg.py` |
| D1 authority | `smc_detector/d1_authority.py` |
| FVG | `smc_detector/fvg.py` |
| POI | `smc_detector/poi.py` |
| W1 | `smc_detector/w1.py` |
| Scan | `smc_detector/scan.py`, `scan_setup.py`, `scan_entry.py`, `scan_finalize.py` |
| Patch (de șters) | `scripts/apply_pure_d1_patch.py` |
| Monolith backup | `smc_detector.py.bak` |
| Scanner | `daily_scanner.py` |
| Radar | `multi_tf_radar.py` |
| Executor | `setup_executor_monitor.py` |
| cTrader | `ctrader_executor.py` |
| Hub JSON | `monitoring_setups.json` |

### B. Documente conexe în repo

- `docs/V67_MASTER_PLAN_AND_AUDIT.md`
- `docs/SMC_DETECTOR_FULL_AUDIT_V67.md`
- `docs/GLITCH_IN_MATRIX_INTEGRATION_AUDIT.md`
- `docs/SMC_DETECTOR_CANONICAL_AUDIT_V67_INSPECTION.md`
- `docs/REMAINING_CLEANUP_ROADMAP.md`

### C. Referințe MASTER SPEC inline (cod)

```python
# core_structure.py — detect_choch_and_bos docstring V68
# - CHoCH/BOS calculate STRICT pe pivoții majori (filter_major_swings)
# - Micro-fractale geometrice NU generează CHoCH/BOS
# - BODY CLOSE ONLY: close > body_high / close < body_low
# - prev_trend se schimbă EXCLUSIV când CHoCH e confirmat
```

---

*Generat: 2026-08-14 — audit read-only, fără modificări de cod la creare.*
