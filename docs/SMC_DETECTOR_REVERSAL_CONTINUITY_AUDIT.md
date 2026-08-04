# Audit SMC Detector — REVERSAL vs CONTINUITY & Body-Close Rules

**Versiune:** 1.1 (V61 update)  
**Data:** 2026-07-23 (audit inițial) · **2026-07-20 (V61 fix)**  
**Scope:** `smc_detector.py`, `multi_tf_radar.py`, `radar_gates.py` (+ teste)  
**Status:** Audit inițial read-only · **V61 implementat** (secțiunea 12)  
**Context:** După editările Faza A / V40 / V42 / V57–V58, setup-urile (ex. USDJPY SHORT când chartul pare bullish pe toate TF-urile) nu mai corespund așteptărilor SMC manuale.

---

## Rezumat executiv

| Întrebare | Verdict |
|-----------|---------|
| **Respectă body-close la BOS/CHoCH?** | **Da, în mare parte** — spargerea pivotului anterior cere `close` peste/sub **body high/low** al pivotului, nu wick. |
| **CHoCH = REVERSAL, BOS = CONTINUITY?** | **Nu** — regula simplă din comentarii **nu reflectă codul**. CHoCH poate fi CONTINUATION; REVERSAL e ramură rară, cu multe priorități înainte. |
| **De ce „nu mai citește setup-urile cum trebuie”?** | Combinație de: **prioritate macro BOS**, **V40 range lock asimetric**, **default CONTINUATION**, **cod mort V57 flip**, **swing-uri body vs doc wick**, **FVG pe wick**. |
| **Body-close peste tot?** | **Nu** — FVG = wick gaps; swing fractals = body; leg validity = close vs `break_price` (preț pivot, nu nivel body-break). |

**Concluzie:** Detectorul nu e „stricat la date” — **modelul de decizie s-a îndepărtat de intuiția SMC manuală** (TradingView). REVERSAL e greu de atins; CONTINUATION (inclusiv bearish) e default-ul când leg-ul nu e invalidat clar.

---

## Metodologie

1. Citire integrală funcții: `detect_choch_and_bos`, `_resolve_d1_leg`, `_find_leg_leg_choch`, `filter_internal_range_signals`, `compute_structural_range`, `scan_for_setup`, `infer_d1_strategy_type`, `resolve_d1_poi`, W1 pipeline.
2. Rulare `scripts/audit_structural_classification.py --cache --symbol USDJPY GBPCAD EURJPY` (300 bare D1 din cache local).
3. Comparare cu `docs/SMC_ALIGNMENT_AUDIT_GIM.md` și `tests/test_d1_leg_invalidation.py`.
4. **Zero modificări** în cod sursă.

---

## 1. Reguli Body-Close — ce face codul de fapt

### 1.1 BOS și CHoCH — **BODY CLOSE pe pivot anterior** ✅

În `detect_choch_and_bos()` (L1708–1798):

- Pentru **HH / BOS bullish**: un bar din intervalul `(prev_high.index, swing.index]` trebuie să aibă `close > body_high(prev_high)`, unde `body_high = max(open, close)`.
- Pentru **LL / BOS bearish**: `close < body_low(prev_low)`, unde `body_low = min(open, close)`.
- Dacă close **nu** depășește body-ul → **skip** (tratat ca sweep / fără confirmare structurală).
- **CHoCH vs BOS** pe același break: depinde de `prev_trend` + condiții LH/LL sau HH/HL în ultimele 5 swing-uri (V24.4 volatile fix).

**Răspuns direct:** Da — **BOS și CHoCH folosesc body-close** față de body-ul pivotului spart, **nu** wick-ul absolut (fix V36.0 B1).

### 1.2 Pivoți majori (`filter_major_swings`) — body-close ✅

- Swing high devine **major** dacă după el există body-close **sub** body-low-ul ultimului swing low anterior.
- Swing low devine **major** dacă după el există body-close **peste** body-high-ul ultimului swing high anterior.

### 1.3 Swing fractals (`detect_swing_highs/lows`) — **body**, nu wick ⚠️

- Fractalul compară **body high/low** (`max/min(open,close)`), deși docstring-ul încă spune „wick absolut”.
- Efect: pivoții pot diferi față de indicatori TradingView pe wick.

### 1.4 FVG (`detect_fvg`) — **WICK gaps** ❌ (nu body)

- Gap bullish: `high[i-1] < low[i+1]` (wick-to-wick).
- Mitigare FVG: **body close** cu buffer 20%.
- Docstring-ul mențione uneori body-gap — **contrazice implementarea**.

### 1.5 Validitate leg CHoCH (`_leg_choch_still_valid`) — close vs `break_price`

- Bearish leg valid: `close < leg_choch.break_price`
- Bullish leg valid: `close > leg_choch.break_price`
- `break_price` = prețul noului swing (CHoCH), **nu** nivelul body-break calculat la detectare.

### 1.6 V40 excepție (`_bar_body_close_above`)

- Pentru CHoCH bullish în range: poate trece filtrul internal dacă `close > level` **sau** `body_high > level` — ușor mai permisiv decât close strict.

### Tabel sinteză

| Componentă | Body-close? | Note |
|------------|-------------|------|
| BOS break | ✅ | close vs body pivot anterior |
| CHoCH break | ✅ | aceeași regulă + prev_trend |
| Major swings | ✅ | impuls LL/HH confirmat cu close |
| Swing fractal | Body pivot | Nu wick |
| FVG gap | ❌ Wick | Body doar la mitigare |
| Leg validity | Close vs swing price | Nu body-break level |
| Major reversal confirm | ✅ | `_body_close_above/below_after` |

---

## 2. REVERSAL vs CONTINUITY — cum decide `_resolve_d1_leg`

### 2.1 Filozofia din cod (L2871–2876)

```
CONTINUATION = macro HH/HL sau LH/LL + BOS aliniat (prioritar)
REVERSAL     = leg CHoCH major confirmat, FĂRĂ BOS same-dir post-leg
Fluctuații interne fără BOS ≠ REVERSAL când trendul macro e activ
```

**Important:** Tipul semnalului (CHoCH vs BOS) **nu** determină direct strategia.

### 2.2 Arbore de priorități (implementare reală)

```
1. macro_trend ∈ {bullish,bearish}  AND  există BOS în direcția macro
   → CONTINUATION + direcția macro + ultimul macro BOS

2. leg_choch is None
   → CONTINUATION pe ultimul BOS (sau neutral)

3. ≥1 BOS same-direction DUPĂ leg_choch
   → CONTINUATION (V42.6) + direcția leg-ului

4. V40 expansion: range locked, leg dir == locked_bias, close dincolo de range
   → CONTINUATION (semnal = leg CHoCH)

5. ≥2 BOS consecutive aceeași direcție (în toată lista)
   → CONTINUATION (BOS chain)

6. _major_reversal_confirmed(leg) AND _leg_choch_still_valid(leg)
   → REVERSAL (singura intrare clară REVERSAL)

7. Fallback: ultimul BOS / macro hold / default
   → CONTINUATION pe direcția leg-ului (chiar dacă leg e discutabil)
```

### 2.3 Ce înseamnă asta practic

| Așteptare utilizator | Comportament cod |
|---------------------|------------------|
| CHoCH bearish recent = REVERSAL SHORT | Poate fi CONTINUATION dacă există macro BOS bearish sau post-leg BOS |
| Trend vizual bullish = LONG | Poate rămâne SHORT dacă V40 a eliminat BOS bullish și leg bearish e încă valid |
| Un singur CHoCH major = schimbare trend | Trebuie să eșueze **toate** ramurile CONTINUATION de mai sus |
| REVERSAL când prețul a făcut HH noi | Macro BOS priority (P1) poate forța CONTINUATION bullish **înainte** de a evalua REVERSAL |

### 2.4 `infer_d1_strategy_type` — override suplimentar

Dacă `_resolve_d1_leg` returnează `reversal`, dar există BOS în direcția `macro_trend_from_swings`:

```python
strategy = 'continuation'  # forțat
```

Deci **bias fallback / infer** poate eticheta CONTINUITY chiar când leg resolver a zis REVERSAL.

### 2.5 `scan_for_setup` — același resolver + gates V57/V58

- Folosește output-ul `_resolve_d1_leg` direct pentru direcție.
- **V58** respinge anumite REVERSAL-uri (ex. LONG sub LL cu macro bearish) — doar pe `strategy_type == 'reversal'`.
- **Nu există gate simetric** pentru CONTINUATION bearish când prețul e deasupra LH cu macro bullish (ex. USDJPY @ 163).

Comentariul din `scan_for_setup` („CHoCH=REVERSAL, BOS=CONTINUITY”) este **depășit / greșit**.

---

## 3. V40 Range Lock — impact major pe direcție

### 3.1 `compute_structural_range`

- Construiește LH/LL din swing-uri **nefiltrate major** (raw) transmise de caller.
- `locked_bias` inside range: **implicit bearish** (L2460–2463).
- Peste LH → `locked_bias = bullish`; sub LL → bearish.

### 3.2 `filter_internal_range_signals` — **asimetrie critică**

- Filtrează **doar semnale BULLISH** când range-ul e locked.
- Semnale **bearish** din interiorul range-ului **nu** sunt eliminate.

**Efect:** În range 152–158 USDJPY, toate BOS/CHoCH bullish sunt „internal bounce” → dispare structura bullish din pipeline → rămâne **bearish CONTINUATION**.

### 3.3 Divergență swing sets

- `detect_choch_and_bos` → `filter_major_swings` intern.
- `scan_for_setup` → `compute_structural_range` pe `_swing_highs_unconf` **raw**.

Range bounds și semnale structurale pot **nu** fi calculate pe același set de pivoți.

---

## 4. W1 Pipeline

- `_resolve_w1_leg_pipeline` = același lanț ca D1 pe ultimele ~60 bare W1, `swing_lookback=3`.
- Moștenește **aceleași probleme** (V40, macro priority, default continuation).
- `apply_w_d_sync_gate` nu schimbă direcția — doar status (`WAITING_W_D_SYNC` etc.).

---

## 5. POI & setup final

### 5.1 `resolve_d1_poi` (Faza A)

- `stored_poi_*` din JSON = **ignorat** la scan (`_ = (...)`).
- Fără FVG organic → setup **respins** (`return None`).
- Continuation: cascade `_resolve_continuation_poi_cascade` (FVG wick în impuls P/D, fallback OB).

### 5.2 Cod mort / nefolosit

| Element | Stare |
|---------|--------|
| `_build_v246_synthetic_fvg` | Definit, **niciodată apelat** din `scan_for_setup` |
| `is_momentum_entry = True` | **Niciodată setat** în repo |
| `dominant_bos_direction` în `scan_for_setup` L4700 | Variabilă definită doar în `determine_daily_trend` → **NameError latent** dacă momentum s-ar activa |
| `_resolve_post_leg_flip` (V57) | Testat unitar, **neapelat** din `_resolve_d1_leg` |

---

## 6. Rezultate audit live (cache D1, 300 bare)

| Symbol | Close (cache) | `current_trend` | `strategy_type` | Observații |
|--------|---------------|-----------------|-----------------|------------|
| **USDJPY** | ~154.79 | bearish | CONTINUATION | V40 LOCK BEARISH; 6 semnale bullish eliminate |
| **GBPCAD** | ~1.864 | bullish | CONTINUATION | macro_swings neutral; 5 CHoCH bearish post-leg ignorate |
| **EURJPY** | — | bullish | CONTINUATION | Caz doc „false REVERSAL long” — acum continuation (OK) |

Simulare preț USDJPY → 163: D1 trece la **bullish CONTINUATION**, W1 **BULLISH** — confirmă că la breakout real clasificarea se schimbă; problema apare cât timp close D1 / regulile V40 mențin structura bearish.

---

## 7. Probleme identificate (severitate)

### 🔴 Critical

| ID | Problema | Efect |
|----|----------|-------|
| **C1** | V40 filtrează **doar bullish** inside range + default bearish lock | Bias sistematic bearish în range (USDJPY-class) |
| **C2** | Prioritate P1: macro BOS forțează CONTINUATION înainte de REVERSAL | CHoCH major valid poate fi ignorat |
| **C3** | Default tail = CONTINUATION pe direcția leg-ului | Setup directional chiar când structura e ambiguă |
| **C4** | Lipsă gate: CONTINUATION bearish cu close > LH + macro bullish | SHORT permis în breakout bullish (USDJPY @ 163) |

### 🟠 High

| ID | Problema | Efect |
|----|----------|-------|
| **H1** | `_resolve_post_leg_flip` neintegrat în `_resolve_d1_leg` | Leg invalidat nu transferă autoritatea la CHoCH opus (USDCAD-class sticky leg) |
| **H2** | Range pe swing-uri raw vs CHoCH pe major filtered | LH/LL și semnale destructure pot diverge |
| **H3** | `infer_d1_strategy_type` forțează continuation extra | Inconsistență față de `_resolve_d1_leg` |
| **H4** | GBPCAD: multiple CHoCH bearish post-leg, trend bullish | Structură opusă ignorată după ce CONTINUATION câștigă |

### 🟡 Medium

| ID | Problema | Efect |
|----|----------|-------|
| **M1** | Doc „CHoCH=Rev / BOS=Cont” vs cod | Confuzie la interpretarea alertelor Telegram |
| **M2** | Doc „wick” vs cod „body” la swings | Divergență față de TradingView |
| **M3** | FVG wick, BOS body — policy neuniform | POI și structură pe reguli diferite |
| **M4** | `audit_structural_classification._macro_trend_swings` ≠ `macro_trend_from_swings` | Audit script poate minți vs producție |
| **M5** | Synthetic FVG / momentum — cod mort | Doc Faza A „eliminat synthetic” — parțial adevărat |

### 🟢 Low

| ID | Problema |
|----|----------|
| **L1** | BOS `break_price` = pivot spart; CHoCH = preț swing nou — măsurători equilibrium inconsistente |
| **L2** | Fractal lag 3 bare dreapta — HH recente invizibile câteva zile |
| **L3** | Coverage teste: 6 teste, fără USDJPY/GBPCAD golden cases |

---

## 8. Contradicții documentație vs cod

| Document / comentariu | Realitate cod |
|----------------------|---------------|
| `SMC_ALIGNMENT_AUDIT_GIM.md` — V57/V58 eliminate din `_resolve_d1_leg` | Flip V57 **nu e apelat**; V58 gates **active** în `scan_for_setup` |
| Faza A — synthetic POI eliminat | `_build_v246_synthetic_fvg` există; cascade OB-as-FVG încă activ |
| `scan_for_setup` — CHoCH=REVERSAL | CHoCH poate fi CONTINUATION (expansion, default tail) |
| `detect_choch_and_bos` — break beyond wick | Break beyond **body** pivot anterior |
| `detect_swing_*` — wick identification | **Body** fractals |
| `detect_fvg` doc body-gap | Implementare **wick-gap** |

---

## 9. De ce alertele par „greșite” după scan fresh

Scanul **este** live (cTrader OHLC). Cardul Telegram folosește `setup.daily_choch.direction` din **`scan_for_setup`**, nu cache Telegram.

Discrepanța față de chart:

1. **Reguli diferite** de TradingView (body fractals, major filter, V40).
2. **„BEARISH BOS”** = direcție setup SHORT, nu „piața e bearish vizual”.
3. **FVG la 157 cu preț 163** = POI bearish din structură veche / continuation short la pullback, nu citire bullish actuală.
4. **W1 în bot** poate fi BEARISH (leg CHoCH weekly vechi) deși TV arată HH recente.

---

## 10. Coverage teste

**Fișier:** `tests/test_d1_leg_invalidation.py` (6 teste)

- EURUSD — nu REVERSAL long
- BTCUSD — nu REVERSAL long pe structură bear
- V58 dead-cat synthetic fixture
- `_resolve_post_leg_flip` unit ( **neintegrat** în resolver principal)
- `_leg_choch_still_valid` smoke

**Lipsesc:** USDJPY V40 strip, GBPCAD post-leg conflict, paritate `infer_d1_strategy_type` vs `scan_for_setup`, W1/D1 alignment, body-close edge JPY 3dp.

---

## 11. Recomandări (pentru fază viitoare — fără implementare acum)

### Prioritate 1 — Model de decizie

1. **Rescrie specificația** REVERSAL vs CONTINUITY ca arbore de priorități documentat (secțiunea 2.2), nu regula CHoCH/BOS simplă.
2. **Decide policy V40:** filtrare simetrică (bullish + bearish) sau eliminare default bearish inside range.
3. **Gate simetric V58** pentru CONTINUATION bearish când `close > macro_range_high` și/sau `macro_swings == bullish`.

### Prioritate 2 — Integritate cod

4. **Integrează sau elimină** `_resolve_post_leg_flip` — testele dau falsă încredere.
5. **Unifică swing set** pentru V40 range și CHoCH/BOS (major filtered peste tot).
6. **Curăță dead code:** synthetic FVG, momentum path, `dominant_bos_direction` scope bug.

### Prioritate 3 — Observabilitate

7. **Aliniază** `audit_structural_classification.py` la `macro_trend_from_swings()` production.
8. **Log structurat** la scan: P1/P2/... ramură `_resolve_d1_leg`, semnale V40 eliminate, body-break level vs close.
9. **Telegram:** afișează `classify_branch` + `d1_scan_date` + distanță preț–POI (ATR).

### Prioritate 4 — Teste

10. Golden fixtures: USDJPY (range lock + breakout 163), GBPCAD (bullish cu CHoCH bearish post-leg), EURJPY, USDCAD sticky leg.
11. Test paritate: `_resolve_d1_leg` == output `scan_for_setup` direction pre-POI.

---

## 12. Verdict final

**Body-close la BOS/CHoCH:** implementat corect (V36.0) — **nu** e problema principală.

**REVERSAL vs CONTINUITY:** aici e problema centrală:

- REVERSAL e **subordinat** și greu de atins.
- CONTINUATION e **default-ul** al resolver-ului.
- V40 + macro BOS priority **mută sistematic** clasificarea față de ce vezi pe chart.
- Editările Faza A au **curățat POI synthetic la scan**, dar **nu au simplificat** arborele reversal/continuity — l-au făcut mai strict pe macro BOS, nu mai fidel SMC manual.

**Pentru USDJPY / GBPCAD:** comportamentul observat e **consistent cu codul actual**, nu cu intuiția „bullish pe toate TF-urile”. Remediul necesită **redesign policy** (secțiunea 11), nu doar refresh JSON.

---

## Anexe

### A. Fișiere analizate

- `smc_detector.py` (~5300 linii)
- `daily_scanner.py` (integrare scan, identity lock — context)
- `scripts/audit_structural_classification.py`
- `tests/test_d1_leg_invalidation.py`
- `docs/SMC_ALIGNMENT_AUDIT_GIM.md`

### B. Comenzi reproducere audit

```bash
python3 scripts/audit_structural_classification.py --cache --symbol USDJPY GBPCAD EURJPY
python3 -m pytest tests/test_d1_leg_invalidation.py -q
```

### C. Referințe cod cheie

| Funcție | Rol |
|---------|-----|
| `detect_choch_and_bos` | Body-close BOS/CHoCH |
| `filter_major_swings` | Leg authority pivoți |
| `compute_structural_range` | V40 LH/LL lock |
| `filter_internal_range_signals` | Strip bullish in range |
| `_find_leg_choch` | Selectare leg activ |
| `_resolve_d1_leg` | **REVERSAL vs CONTINUATION** |
| `_major_reversal_confirmed` | Gate REVERSAL |
| `scan_for_setup` | Pipeline complet + V58 gates |
| `infer_d1_strategy_type` | Override continuation |
| `resolve_d1_poi` | FVG organic + cascade |

---

## 12. V61 — Fix implementat (2026-07-20): 4H direction guard + D1 bias coerce

**Status:** Implementat în cod (nu mai e read-only pentru aceste puncte).

### Problema raportată

Când prețul atinge POI Daily, radarul emitea alerte 4H CHoCH chiar dacă spargerea 4H era **în direcția opusă** bias-ului Daily (ex. setup SHORT + CHoCH 4H bullish = doar extindere pullback în POI).

### Fix-uri aplicate

| Layer | Fișier | Ce s-a schimbat |
|-------|--------|-----------------|
| **Normalizare direcții** | `radar_gates.py` | `normalize_structural_direction()` — `long`/`buy` → `bullish`, `short`/`sell` → `bearish`; `h4_structural_direction_ok()` |
| **Guard 4H strict** | `multi_tf_radar.py` | `analyze_timeframe()`: filtrează CHoCH/BOS contrare; log `[4H DIRECTION MISMATCH SKIP]`; fără alertă Telegram / lock / EXECUTE_NOW |
| **Alerte Telegram** | `multi_tf_radar.py` | `_maybe_send_choch_alerts()`: verificare direcție **înainte** de post-POI; mismatch → skip + log |
| **EXECUTE_NOW** | `multi_tf_radar.py` | `_v423_ltf_misalignment()` + `_update_setup_with_radar()` folosesc `h4_structural_direction_ok()` |
| **Post-POI anchor** | `radar_gates.py` | `v47_break_post_poi_touch()`: `break_dt is None` → `False` (nu mai trece alerte fără timestamp) |
| **D1 bias authority** | `smc_detector.py` | `_coerce_d1_bias_to_major_structure()`: LL < close ≤ LH → bearish continuation, nu REVERSAL bullish |
| **Leg resolve** | `smc_detector.py` | `_resolve_d1_leg()`: ignoră bullish reversal CHoCH în range bearish locked (V40) |
| **V58 extins** | `smc_detector.py` | REVERSAL LONG respins când close e **în interior** LL–LH fără break LH; coerce la bearish continuation |

### Teste

```bash
python3 -m py_compile multi_tf_radar.py smc_detector.py telegram_notifier.py
python3 -m pytest tests/test_4h_alert_gates.py -q
python3 -m pytest tests/ -q
```

- `tests/test_4h_alert_gates.py::test_4h_alert_blocked_when_choch_opposes_daily_bias` — Daily SHORT + 4H bullish CHoCH → alertă **blocată**.

### Verdict post-V61

| Verificare | Status |
|------------|--------|
| CHoCH 4H contrar bias Daily poate trece alerta Telegram? | **Nu** — blocat de `h4_structural_direction_ok` + filtru `analyze_timeframe` |
| EXECUTE_NOW cu 4H misaligned? | **Nu** — `_v423_ltf_misalignment` dezarmează |
| D1 JSON poate rămâne LONG greșit în range bearish? | **Redus** — `_coerce_d1_bias_to_major_structure` forțează bearish continuation |
| Root cause complet (V60 macro LH authority)? | **Parțial** — V61 acoperă radar + coerce D1; refactor complet `_resolve_d1_leg` rămâne roadmap |

---

*Document actualizat post-V61. Secțiunile 1–11 rămân audit istoric; secțiunea 12 reflectă fix-urile implementate.*
