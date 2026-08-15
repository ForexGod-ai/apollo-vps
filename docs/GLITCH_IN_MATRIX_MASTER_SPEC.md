# Glitch in Matrix — Master Spec (Constituție Canonică)

> **Versiune:** V68 / Pure D1 Matrix  
> **Data:** 2026-08-16  
> **Principiu:** *less is more* — un motor D1, fără recalcule paralele, fără patch-uri externe

Acest document este **sursa unică de adevăr** pentru strategia Glitch in Matrix. Orice cod, test sau audit trebuie aliniat la cele 4 Piloni și la regulile de mai jos.

---

## 1. Cei 4 Piloni ai Sistemului

| Pilon | Modul | Rol |
|-------|-------|-----|
| **1 — SMC Engine** | `smc_detector/` | Structură D1/W1, POI, `scan_for_setup()` → `TradeSetup` |
| **2 — Daily Scanner** | `daily_scanner.py` | Scan dimineața → `monitoring_setups.json` |
| **3 — Multi-TF Radar** | `multi_tf_radar.py` | POI latch, scan 4H, armat `EXECUTE_NOW` |
| **4 — Executor** | `setup_executor_monitor.py` → `ctrader_executor.py` | `signals.json` → cBot → broker |

**Flux end-to-end:**

```
cTrader OHLCV
  → build_d1_context() [cache per pair]
  → scan_for_setup(d1_ctx=cached)
  → monitoring_setups.json
  → multi_tf_radar (4H CHoCH + retrace gate)
  → EXECUTE_NOW
  → setup_executor_monitor
  → signals.json → cBot
```

**Interzis:** scripturi care rescriu textual fișiere din `smc_detector/`; recalcule D1 paralele în scanner (`_resolve_d1_leg` direct, `_hydrate` fără cache).

---

## 2. Autoritate Timeframe

### 2.1 W1 — Informativ (soft sync)

- W1 **nu blochează** setup-uri D1 directionale.
- Rol: context macro, soft sync (`WAITING_W_D_SYNC`), confidence `LOW_W1_COUNTER_TREND`.
- `calculate_w1_bias()` + `resolve_w1_poi()` — lazy, doar când D1 e bullish/bearish.

### 2.2 D1 — Autoritar (hard authority)

- **O singură sursă:** `SMCDetector.build_d1_context(df, symbol)` → `D1AuthContext`.
- Scanner, JSON, identity lock, bias fallback — **toate** citesc din cache-ul `build_d1_context`, nu recalculează leg separat.
- `resolve_authoritative_d1_bias()` = wrapper thin peste `build_d1_context().as_dict()` (legacy API).

---

## 3. Reguli Structurale SMC (V68)

### 3.1 Major Swings Filter

- CHoCH/BOS se calculează **strict pe pivoții majori** (`filter_major_swings`).
- Micro-fractale geometrice **NU** generează CHoCH/BOS.
- Implementare: `core_swings.py` + `core_structure.py` → `filter_internal_range_signals()`.

### 3.2 Body-Close Mandatory

- Validare BOS/CHoCH: **închidere corp candle** (open/close), nu wick.
- Wick-peak / crash-origin heuristici sunt **eliminate**.
- Implementare: `detect_choch_and_bos()` în `core_structure.py`.

### 3.3 D1 Leg Resolution (Pure Matrix)

- `_resolve_pure_d1_matrix()` — simetric bullish/bearish.
- Pullback intern ≠ flip structural; BOS counter-trend filtrat (`_filter_countertrend_pullback_bos`).
- Forming HL/LH, LH reclaim, post-flip BOS skip — reguli simetrice în `d1_leg.py`.

### 3.4 V66 REV vs CONT (Organic)

| Condiție | Strategy | Signal afișat |
|----------|----------|---------------|
| 0 BOS same-direction **după** leg CHoCH | **REVERSAL** | CHoCH (leg) |
| ≥1 BOS same-direction post-leg | **CONTINUATION** | Ultimul BOS |

- **Fără** praguri arbitrare de timp (50/15 bare) pentru „maturitate”.
- `_strategy_from_leg_choch()` + `_classify_d1_strategy()` + `_d1_signal_for_strategy()`.

---

## 4. POI & Entry Gates

### 4.1 D1 POI

- `build_active_dealing_range()` → `resolve_d1_poi()` — organic FVG sau None.
- Fără equilibrium clip forțat; JSON preserve doar când ADR stabil (V43/V44 lifecycle).

### 4.2 4H Retrace Gate (V46 / EXECUTE_NOW)

- **EXECUTE_NOW** necesită:
  1. POI Daily atins (latch radar)
  2. CHoCH 4H în direcția D1
  3. **Retrace 60–80%** pe impulsul CHoCH/BOS LTF

- Alertele structurale pot apărea mai devreme; execuția rămâne gated.

### 4.3 Status lifecycle (JSON)

| Status | Semnificație |
|--------|--------------|
| `WAITING_D1_PULLBACK` | Bias activ, preț în afara POI |
| `MONITORING` / `READY` | POI atins, așteptare 4H |
| `WAITING_4H_CHOCH` | POI valid, fără confirmare LTF |
| `WAITING_W_D_SYNC` | D1 vs W1 conflict soft |
| `EXECUTE_NOW` | Armat de radar — toate porțile trecute |

---

## 5. Pipeline D1 Canonic (Layer Stack)

```
Layer 1: PIVOTS          core_swings.py     → detect_swing_highs/lows, filter_major_swings
Layer 2: STRUCTURĂ       core_structure.py  → detect_choch_and_bos (body-close), structural range
Layer 3: LEG D1          d1_leg.py          → _resolve_pure_d1_matrix, REV/CONT
Layer 4: AUTORITATE      d1_authority.py    → build_d1_context() → D1AuthContext
Layer 5: POI             poi.py + fvg.py    → ADR + resolve_d1_poi
Layer 6: SCAN            scan_*.py          → scan_for_setup(d1_ctx=...)
Layer 7: TRANSPORT       daily_scanner → JSON → radar → executor
```

---

## 6. Invariante de Cod

1. **Un `build_d1_context()` per pair per scan run** — cache în `d1_auth_cache`.
2. **`scan_for_setup(d1_ctx=cached)`** — fără rebuild D1 în interior când ctx furnizat.
3. **Bias fallback** — citește `D1AuthContext`; POI hydrate via același ctx, nu `_resolve_d1_leg` direct.
4. **Fără patch scripts** în `scripts/` care modifică `smc_detector/*.py`.
5. **Teste canonice** trec înainte de deploy:
   ```bash
   python3 -m py_compile smc_detector/*.py daily_scanner.py multi_tf_radar.py setup_executor_monitor.py
   python3 -m pytest tests/test_d1_bias_canonical.py -q
   python3 -m pytest tests/ -q
   ```

---

## 7. Referințe

- Audit 4 piloni: `docs/SMC_DETECTOR_FOUR_PILLARS_AUDIT.md`
- Plan V67: `docs/V67_MASTER_PLAN_AND_AUDIT.md`
- Integrare E2E: `docs/GLITCH_IN_MATRIX_INTEGRATION_AUDIT.md`

---

*„Structura macro decide direcția. 4H confirmă entry-ul. Executorul respectă porțile — fără scurtături.”*
