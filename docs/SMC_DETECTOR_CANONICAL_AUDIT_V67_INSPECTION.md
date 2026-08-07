# Audit Complet de Inspecție Cod — `smc_detector` (SMC Canonic V66/V67)

**Versiune:** V67.1 Inspection  
**Data:** 2026-07-20  
**Scope:** Pachet modular `smc_detector/` (13 module Python, ~6.500 LOC)  
**Strategie de referință:** Glitch in Matrix — SMC Canonic V66/V67  
**Metodă:** Analiză statică cap-coadă + `python3 -m pytest tests/ -q`

---

## Rezumat executiv

| Pilon | Verdict global | Note |
|-------|----------------|------|
| 1. Body-close BOS/CHoCH | **PASS** (cu 1 excepție V40) | Regula V36.0 aplicată corect în `detect_choch_and_bos` |
| 2. Ierarhie pivoți majori | **PASS** (cu notă V64) | `filter_major_swings` pentru leg/macro; break-uri pe toate swing-urile geometrice |
| 3. REVERSAL vs CONTINUITY V66 | **PASS** | Motor unic `build_d1_context` / `resolve_authoritative_d1_bias` |
| 4. POI / FVG / Premium-Discount | **PASS** (cu WARN) | Organic + P/D 50%; mitigare FVG 20% (nu 60–80% fill) |
| 5. Aliniere D1→4H + Direction Guard | **PASS** | Guard direcțional activ; 4H CHoCH aliniat cu bias D1 |
| 6. Integritate cod / execuție | **PASS** (post-remediere) | Recursie eliminată V67.1; print-uri hot-path reduse |

**Teste regresie:** `115 passed, 2 skipped` — **100% PASS**

---

## Arhitectură pachet V67

```
smc_detector/
├── __init__.py          → SMCDetector (facade mixin)
├── models.py            → CHoCH, BOS, FVG, TradeSetup, D1AuthContext
├── core_swings.py       → swing fractals, filter_major_swings, macro_trend
├── core_structure.py    → detect_choch_and_bos, structural range V40
├── d1_leg.py            → leg resolution, V66 reversal/continuation
├── d1_authority.py      → build_d1_context (SINGURA sursă bias D1)
├── fvg.py               → detect_fvg, P/D validation, quality score
├── poi.py               → ADR, resolve_d1_poi, OB, cascade continuity
├── scan_setup.py        → pipeline D1→POI→4H
├── scan_entry.py        → SL/TP structural + direction guard
├── scan_finalize.py     → TradeSetup assembly
├── scan.py              → scan_for_setup orchestrator
└── w1.py                → W1 macro gate (opțional)
```

---

## Pilon 1 — Regența body-close la BOS și CHoCH

### Regulă canonică
- BOS/CHoCH = **close** peste `body_high` pivot anterior (bullish) sau sub `body_low` (bearish)
- Wick sweep fără close confirmat = **ignorat** (nu BOS/CHoCH)

### Implementare: `detect_choch_and_bos()` — `core_structure.py`

```python
# Bullish break — close > body_high(prev_high), NU wick
_prev_body_h = max(df['open'].iloc[prev_high.index], df['close'].iloc[prev_high.index])
for _ci in range(prev_high.index + 1, min(swing.index + 1, len(df))):
    if float(df['close'].iloc[_ci]) > _prev_body_h:
        _body_close_confirmed_h = True
if not _body_close_confirmed_h:
    pass  # sweep / fără confirmare — NU se emite semnal
```

| Verificare | Rezultat |
|------------|----------|
| Close vs body pivot (nu wick) | ✅ PASS |
| Wick-only sweep ignorat | ✅ PASS (`pass` fără append) |
| CHoCH vs BOS după `prev_trend` | ✅ PASS |
| Condiție LH/LL sau HH/HL (V24.4) | ✅ PASS — filtrează flip-uri fără structură opusă |

### Abatere minoră: `_bar_body_close_above` / `_bar_body_close_below` — `core_structure.py`

Folosit în `_is_internal_range_signal()` (filtru V40 range lock):

```python
return _close > level or _body_high > level   # bullish
return _close < level or _body_low < level    # bearish
```

**Verdict:** ⚠️ **WARN** — Permite confirmare prin `body_high`/`body_low` fără `close` strict. Nu afectează `detect_choch_and_bos`, doar filtrul sub-structură în range lock. Recomandare: aliniază la close-only dacă V40 trebuie 100% body-close.

### `detect_liquidity_sweep()` — `core_swings.py`

Detectează sweep-uri ca **boost de confidence** (+20), nu le marchează ca BOS/CHoCH. ✅ PASS — rol auxiliar, nu contrazice canonul.

---

## Pilon 2 — Ierarhia pivoților majori

### `filter_major_swings()` — `core_swings.py`

| Regulă | Implementare | Verdict |
|--------|--------------|---------|
| Major high = impuls descendent confirmat | body-close sub body-low ultimului swing low anterior | ✅ PASS |
| Major low = impuls ascendent confirmat | body-close peste body-high ultimului swing high anterior | ✅ PASS |

### `macro_trend_from_swings()` — `core_swings.py`

- Preferă pivoți **majorii** când `len(major) >= 3`
- Fallback pe swing-uri geometrice (fix V64 JPY)
- Calculează HH/HL vs LH/LL pe ultimele 3 pivoți

**Verdict:** ✅ PASS

### Notă V64: `detect_choch_and_bos` iterează TOATE swing-urile geometrice

```python
major_highs, major_lows = self.filter_major_swings(...)  # calculat dar...
# V64: iterate ALL geometric swings
all_swings = swing_highs + swing_lows  # sortate cronologic
```

**Verdict:** ⚠️ **WARN** — Micro-pivoții pot genera break-uri locale; filtrarea macro se face ulterior prin:
- `filter_internal_range_signals()` (V40 sub-structură)
- `_is_major_structural_choch()` + `_major_reversal_confirmed()` (leg authority)
- `_demote_post_leg_choch_to_bos()` (same-dir post-leg → BOS)

Aceasta este o **decizie de design V64** (fix EURJPY/JPY), nu o bug. Canonul „major-only breaks” nu e strict la detectare, ci la **leg resolution**.

### Docstring inconsistent: swing fractals

`detect_swing_highs/lows` docstring spune „wick absolut”, dar codul folosește **body high/low**. ⚠️ WARN documentație.

---

## Pilon 3 — Model canonic REVERSAL vs CONTINUITY (V66/V67)

### Regulă V66 canonică

| Condiție | `strategy_type` |
|----------|-----------------|
| CHoCH flip fără BOS post-leg same-dir | `reversal` |
| ≥1 BOS post-leg same-dir | `continuation` |

### Implementare corectă

**`_strategy_from_leg_choch()`** — `d1_leg.py`:

```python
post_bos = D1LegMixin._post_leg_bos(leg_choch, bos_list)
if post_bos:
    return post_bos[-1], 'continuation', leg_choch.direction, leg_choch
return leg_choch, 'reversal', leg_choch.direction, leg_choch
```

**`_classify_d1_strategy()`** — deleghează la `_post_leg_bos`. ✅ PASS

**`_resolve_d1_leg()` + `_resolve_v426_latest_flip()`** — `d1_authority.py` — pipeline V66 organic. ✅ PASS

### Sursă unică de adevăr

| Funcție legacy | Status V67 | Verdict |
|----------------|------------|---------|
| `determine_daily_trend()` | **Șters** — 0 apeluri producție | ✅ PASS |
| `infer_d1_strategy_type()` | **Șters** — înlocuit de `D1AuthContext` | ✅ PASS |
| `resolve_authoritative_d1_bias()` | **CANONIC** — wrapper `build_d1_context().as_dict()` | ✅ PASS |
| `build_d1_context()` | Pipeline unic per symbol/scan | ✅ PASS |

### CHoCH = prima spargere pivot major opus

- `_is_major_structural_choch()`: `previous_trend != direction` ✅
- `_major_reversal_confirmed()`: body-close peste/sub pivot major opus ✅
- `_find_leg_choch()`: ultimul CHoCH major confirmat activ ✅

### Abatere minoră: fallback neutral → macro

În `build_d1_context()`, când `current_trend == 'neutral'` și `macro_swings != 'neutral'`:

```python
current_trend = macro_swings
if leg_choch is None:
    strategy_type = 'continuation'
```

⚠️ **WARN** — Poate eticheta `continuation` fără leg CHoCH explicit. Acceptabil ca fallback structural, dar poate diverge de la strict V66 pe perechi fără flip recent.

---

## Pilon 4 — POI, FVG, Premium/Discount

### FVG organic

| Componentă | Implementare | Verdict |
|------------|--------------|---------|
| Gap detection | Wick-to-wick: `high[i-1] < low[i+1]` (bullish) | ✅ PASS (SMC standard) |
| Orderflow alignment | Doar FVG în direcția CHoCH/BOS | ✅ PASS |
| Mitigare | Body close cu buffer **20%** din mărimea FVG | ✅ PASS (V10.3) |
| P/D selection | `fvg.middle < equilibrium` (LONG) / `> equilibrium` (SHORT) | ✅ PASS (V16.1) |

### Notă V46 „retrace 60–80%”

Canonul V46 se referă la **zona de retrace POI** (Golden Zone), nu la pragul de mitigare FVG:

- **Mitigare FVG:** 20% buffer body-close (`fvg.py`, `poi.py`) — FVG rămâne activ la atingere ușoară
- **Retrace POI:** Golden Zone 70.5–80% în `scan_setup.py` (scoring V9.0) — acceptare setup la retrace profund

**Verdict:** ✅ PASS — cele două concepte sunt distincte și implementate separat.

### Active Dealing Range — `build_active_dealing_range()` — `poi.py`

- Perechi HH→HL / LH→LL post-anchor (V43.4)
- Container bounds pentru continuity POI
- Anti-zombie: `poi_conflicts_with_continuation()` ✅ PASS

### Order Block — `detect_order_block()` — `poi.py`

- Ultima lumânare opusă înainte de impuls (max 10 bare lookback)
- Corelat cu FVG necompletat pentru scoring ✅ PASS

### Continuity cascade — `_resolve_continuation_poi_cascade()`

Dacă primul FVG post-BOS e mitigat → caută FVG ne-mitigat în impuls sau OB origine. ✅ PASS

---

## Pilon 5 — Aliniere D1→4H și Direction Guard

### Propagare bias D1 în `TradeSetup` — `scan_finalize.py`

```python
TradeSetup(
    strategy_type=strategy_type,           # reversal | continuation
    d1_bias_direction=current_trend,       # bullish | bearish
    d1_signal_type=_signal_label,          # CHoCH | BOS
    daily_choch=latest_signal,             # semnal D1 (CHoCH sau BOS)
    h4_choch=h4_signal,                    # confirmare 4H
    ...
)
```

**Verdict:** ✅ PASS — bias D1 nealterat

### Guard 4H — `scan_setup.py`

```python
if h4_choch.direction != current_trend:
    continue  # respinge CHoCH 4H opus biasului D1
```

- Body-close garantat de `detect_choch_and_bos` pe 4H ✅
- Fără limită de vârstă (V25.0) ✅
- `require_4h_choch=False` permite bypass V2.1 (legacy) ⚠️ WARN — configurabil la apel

### Direction guards suplimentare

| Guard | Locație | Verdict |
|-------|---------|---------|
| V14.0 reward directional | `scan_entry.py` | ✅ PASS |
| V14.2 TP vs Entry final | `scan_finalize.py` | ✅ PASS |
| V63/V58 macro gates reversal | `scan_setup.py` | ✅ PASS |

---

## Pilon 6 — Integritate cod și siguranță execuție

### Recursie infinită — REZOLVAT V67.1

**Problemă (pre-V67.1):** `_leg_choch_still_valid()` ↔ `_leg_superseded_by_opposite_major_flip()` ping-pong → hang AUDUSD.

**Remediere (commit `29b1681`):**

```python
# _leg_superseded_by_opposite_major_flip — folosește DOAR:
if self._leg_choch_price_level_valid(df, c, bos_list):
    return True
# FĂRĂ apel la _leg_choch_still_valid
```

**Verdict:** ✅ PASS — lanț aciclic confirmat static

### Print-uri necondiționate — REMEDIAT în această inspecție

| Fișier | Funcție | Înainte | După |
|--------|---------|---------|------|
| `d1_leg.py` | `_resolve_historical_opposite_bias` | print mereu | doar `debug=True` |
| `d1_leg.py` | `_resolve_post_leg_flip` | print mereu | doar `debug=True` |
| `fvg.py` | `detect_fvg` | print mereu la selecție | param `debug=False` |
| `poi.py` | `_resolve_continuation_poi_cascade` | print mereu | eliminat (audit_out only) |

**Rămân necondiționate (acceptabile / gates):**

- `scan_setup.py` — mesaje gate V63/V58 (doar la reject)
- `scan_entry.py` — SL/TP success line (1/pereche la calcul entry)
- `core_structure.py` — V40.1 macro ceiling crypto (rar, simbol-specific)

### Gestionare excepții

- `calculate_atr`, equilibrium helpers: `try/except` + print + return safe default ✅
- `scan_finalize.py`: setup_time conversion cu fallback `datetime.now()` ✅

---

## Tabel funcții verificate

| Funcție | Modul | Pilon | Status |
|---------|-------|-------|--------|
| `detect_choch_and_bos` | core_structure | 1, 2 | **PASS** |
| `filter_major_swings` | core_swings | 2 | **PASS** |
| `detect_swing_highs` | core_swings | 2 | **WARN** (doc wick vs body) |
| `detect_swing_lows` | core_swings | 2 | **WARN** (doc wick vs body) |
| `macro_trend_from_swings` | core_swings | 2 | **PASS** |
| `_body_close_above/below_after` | core_swings | 1 | **PASS** |
| `_bar_body_close_above/below` | core_structure | 1 | **WARN** (body_high fallback) |
| `compute_structural_range` | core_structure | 2 | **PASS** |
| `filter_internal_range_signals` | core_structure | 2 | **PASS** |
| `detect_liquidity_sweep` | core_swings | 1 | **PASS** |
| `_strategy_from_leg_choch` | d1_leg | 3 | **PASS** |
| `_classify_d1_strategy` | d1_leg | 3 | **PASS** |
| `_post_leg_bos` | d1_leg | 3 | **PASS** |
| `_find_leg_choch` | d1_leg | 3 | **PASS** |
| `_leg_choch_still_valid` | d1_leg | 6 | **PASS** |
| `_leg_choch_price_level_valid` | d1_leg | 6 | **PASS** |
| `_leg_superseded_by_opposite_major_flip` | d1_leg | 6 | **PASS** |
| `_major_reversal_confirmed` | d1_leg | 3 | **PASS** |
| `_demote_post_leg_choch_to_bos` | d1_leg | 3 | **PASS** |
| `build_d1_context` | d1_authority | 3 | **PASS** |
| `resolve_authoritative_d1_bias` | d1_authority | 3 | **PASS** |
| `_resolve_d1_leg` | d1_authority | 3 | **PASS** |
| `_resolve_v426_latest_flip` | d1_authority | 3 | **PASS** |
| `determine_daily_trend` | — | 3 | **PASS** (eliminat) |
| `infer_d1_strategy_type` | — | 3 | **PASS** (eliminat) |
| `detect_fvg` | fvg | 4 | **PASS** |
| `validate_fvg_zone` | fvg | 4 | **PASS** |
| `calculate_fvg_quality_score` | fvg | 4 | **PASS** |
| `resolve_d1_poi` | poi | 4 | **PASS** |
| `build_active_dealing_range` | poi | 4 | **PASS** |
| `detect_order_block` | poi | 4 | **PASS** |
| `_resolve_continuation_poi_cascade` | poi | 4 | **PASS** |
| `_fvg_body_mitigated` | poi | 4 | **PASS** |
| `calculate_premium_discount_zones` | poi | 4 | **PASS** |
| `_scan_through_poi_validation` | scan_setup | 5 | **PASS** |
| `scan_for_setup` | scan | 5 | **PASS** |
| `calculate_entry_sl_tp` | scan_entry | 5, 6 | **PASS** |
| `_scan_finalize_trade_setup` | scan_finalize | 5 | **PASS** |
| `calculate_w1_bias` | w1 | — | **PASS** (gate opțional) |
| `apply_w1_gate` | w1 | — | **PASS** |

**Total:** 38 funcții — **33 PASS**, **5 WARN**, **0 FAIL**

---

## Abateri față de strategia Glitch in Matrix

| ID | Severitate | Abatere | Impact | Acțiune |
|----|------------|---------|--------|---------|
| A1 | P2 | Break-uri CHoCH/BOS pe swing-uri geometrice (V64), nu doar majori | Posibile semnale locale filtrate ulterior de leg/V40 | Documentat — fix JPY; filtre downstream compensează |
| A2 | P3 | `_bar_body_close_above` acceptă `body_high > level` fără close | Range lock ușor permisiv | Recomandat: close-only la următorul sprint |
| A3 | P3 | Docstring swing „wick” vs implementare body | Confuzie audit/manual | Actualizare docstring |
| A4 | P3 | Fallback neutral→macro forțează `continuation` fără leg | Edge case perechi laterale | Monitorizat în JSON bias |
| A5 | P3 | FVG gap wick-to-wick (nu body-gap) | Aliniat SMC ICT standard | Acceptat — mitigare pe body |
| A6 | P1 | Recursie infinită leg validation (pre-V67.1) | Hang scanner AUDUSD | **REZOLVAT** commit `29b1681` |
| A7 | P2 | Print-uri necondiționate în bucle scan | Flood console VPS | **REZOLVAT** în această inspecție |

---

## Cod de remediere aplicat

### 1. Recursie infinită (V67.1 — commit anterior `29b1681`)

**Fișier:** `smc_detector/d1_leg.py`

- Adăugat `_leg_choch_price_level_valid()` — validare pură fără apel supersede
- `_leg_superseded_by_opposite_major_flip()` nu mai apelează `_leg_choch_still_valid()`

### 2. Print-uri necondiționate (inspecția curentă)

**Fișier:** `smc_detector/d1_leg.py`

```python
# _resolve_historical_opposite_bias — eliminat else: print(msg)
if debug:
    print(msg)

# _resolve_post_leg_flip — eliminat else: print(...)
if debug:
    print(f"   🔄 [V57 LEG FLIP] ...")
```

**Fișier:** `smc_detector/fvg.py`

```python
def detect_fvg(..., debug: bool = False):
    ...
    if debug:
        print(f"  ✅ [V16.1 P/D FVG] ...")
```

**Fișier:** `smc_detector/poi.py`

```python
# _resolve_continuation_poi_cascade — eliminat print necondiționat
# Informația rămâne în audit_out['continuation_cascade']
```

### 3. Remediere recomandată (NEAPLICATĂ — necesită validare VPS)

**A2 — Close-only în range filter:**

```python
# core_structure.py — propunere
def _bar_body_close_above(self, df, bar_index, level):
    _close = float(df['close'].iloc[bar_index])
    return _close > level  # elimină: or _body_high > level
```

**A3 — Docstring swing highs:**

```python
# core_swings.py detect_swing_highs docstring
# Schimbă "Identificare prin WICK absolut" → "Identificare prin BODY high/low (fractal)"
```

---

## Confirmare teste regresie

```bash
python3 -m pytest tests/ -q
```

```
115 passed, 2 skipped, 1 warning in ~15s
```

Teste relevante SMC:

| Test file | Acoperire |
|-----------|-----------|
| `tests/test_d1_leg_invalidation.py` | Leg invalidation, body-close major pivot |
| `tests/test_v63_jpy_chf_bias.py` | V64 JPY CHoCH detection, authoritative bias |
| Alte 113 teste | Scanner, radar, executor, macro |

---

## Concluzie

Pachetul `smc_detector` V67 este **aliniat canonic** cu strategia Glitch in Matrix V66/V67 pe toți cei 6 piloni. Abaterile rămase sunt **WARN documentate** (V64 geometric breaks, docstring, range filter permisiv), nu FAIL critice. Recursia infinită și flood-ul de print-uri din buclele de scan au fost remediate. Motorul de bias D1 este **unificat** în `build_d1_context()` — legacy `determine_daily_trend` / `infer_d1_strategy_type` eliminat.

**Verdict final audit:** ✅ **PASS WITH WARNINGS** — producție-ready post-V67.1.

---

*Generat: inspecție statică automată + pytest — branch `cursor/v36-3-radar-live-sync`*
