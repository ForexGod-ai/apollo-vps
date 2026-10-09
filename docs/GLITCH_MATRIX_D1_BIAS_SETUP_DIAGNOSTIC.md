# Glitch in Matrix — Diagnostic D1 Bias & Citire Setup-uri

**Data:** 2026-10-08  
**Tip:** Audit read-only (diagnoză, fără patch-uri)  
**Context:** MARKET_REPORT ~15/16 perechi 🔴 SHORT; USDCAD Daily vizual bullish, bot raportează **🔴 SHORT · CONT (BOS) · D1 BEARISH BOS** + **W1 BULLISH ⚠️ nealiniat**.  
**Concluzie executivă:** Nu există un `default bearish` global. Skew-ul spre SHORT vine din **autoritatea D1 V67+** (`d1_leg.py` + `core_structure.py`), care **nu mai aliniază citirea HH/HL/LH/LL cu interpretarea vizuală Glitch** (trend activ = ultimul impuls structural clar). Esența strategiei s-a diluat prin straturi de „leg CHoCH”, filtre pullback, Rule 2 Major LH/HL și macro override condiționat.

---

## 1. Simptome observate (operational)

| Simptom | Detaliu |
|--------|---------|
| MARKET_REPORT | ~16 perechi scanate; ~15 cu bulină roșie (SHORT) |
| Telegram `_format_compact_line` | `🔴` când JSON `direction == 'sell'` — UI reflectă JSON, nu inversează bias-ul |
| USDCAD card | Preț ~1.42578; POI Daily vechi ~1.386–1.391; D1 **BEARISH BOS**; W1 **BULLISH** nealiniat |
| TradingView (utilizator) | HH/HL bullish pe Daily, BOS/CHoCH etichetate bullish pe structură recentă |
| Grupare raport | Multe rânduri sub **⏳ W+D nealiniat** — D1 bearish vs W1 bullish/neutral |

Statistic 15/16 SHORT pe un univers mixt (Forex, XAU, BTC) este semnal că **pipeline-ul D1 canonical** produce bias bearish mult prea des, nu că piața e uniform bearish.

---

## 2. Ce presupune strategia Glitch in Matrix (referință conceptuală)

Din documentația inline și fluxul `scan_for_setup` (`smc_detector/scan.py`):

1. **D1 stabilește direcția** (CHoCH = reversal, BOS = continuity).
2. **FVG / POI Daily** = zonă de reacție în Premium (SHORT) sau Discount (LONG).
3. **4H CHoCH** confirmă sfârșitul pullback-ului în direcția D1.
4. Structura **HH / HL / LH / LL** pe swing-uri relevante trebuie să reflecte **caracterul curent al pieței** (cine controlează: cumpărători vs vânzători), nu un leg bearish „înghețat” dintr-o corecție veche.

**Așteptarea utilizatorului (USDCAD):** Daily clar bullish → bias D1 **BULLISH**, setup LONG/CONT sau așteptare pullback în POI bullish, aliniere W+D.

**Comportament actual:** D1 rămâne **BEARISH** cu **BOS bearish** ca semnal afișat, POI în zona veche de discount, prețul mult deasupra POI-ului.

---

## 3. Unde se decide bias-ul în cod (lanț complet)

```
daily_scanner.py
  └─ build_d1_context()          [smc_detector/d1_authority.py]  ← SINGURA AUTORITATE D1
       ├─ detect_choch_and_bos()  [smc_detector/core_structure.py]
       ├─ detect_swing_* + filter_major_swings [core_swings.py]
       ├─ compute_structural_range() [core_structure.py]
       ├─ filter_internal_range_signals()
       └─ _resolve_d1_leg → _resolve_pure_d1_matrix() [d1_leg.py]
            → trend, leg_choch, latest_signal, strategy_type

  └─ scan_for_setup(..., d1_ctx=...) [scan.py → scan_setup.py]
       └─ current_trend = d1_ctx.trend (NU recalculează separat)

  └─ TradeSetup.d1_bias_direction = current_trend [scan_finalize.py]

  └─ JSON monitoring: direction = buy|sell [daily_scanner._setup_trade_direction]

telegram_notifier.py
  └─ MARKET_REPORT: 🔴 dacă direction == 'sell'
  └─ Card scan: raw_dir din d1_bias_direction → "BEARISH BOS" / "🔴 SHORT"
```

### Funcții cheie de normalizare

| Funcție | Fișier | Rol |
|---------|--------|-----|
| `_setup_d1_trend()` | `daily_scanner.py` | Citește `d1_bias_direction` (V64), fallback `daily_choch.direction` |
| `_setup_trade_direction()` | `daily_scanner.py` | `bullish` → `buy`, `bearish` → `sell` |
| `_identity_direction()` | `daily_scanner.py` | Reconciliere JSON la rehydrate |
| `build_d1_context()` | `d1_authority.py` | Mapare finală `trend` → `direction` (`buy`/`sell`) |

**Important:** Cardul Telegram **nu** folosește ultimul HH de pe grafic; folosește **`d1_bias_direction`** produs de matricea leg din `d1_leg.py`.

---

## 4. Module structură (echivalent `structure.py`)

Nu există `smc_detector/structure.py`. Logica este împărțită:

| Modul | Responsabilitate |
|-------|------------------|
| `core_structure.py` | CHoCH/BOS V68: major swings only, **body close** (close > body_high / < body_low) |
| `core_swings.py` | Swing highs/lows, `filter_major_swings`, `macro_trend_from_swings` |
| `d1_leg.py` | Leg CHoCH activ, invalidare LH/HL, pullback BOS, `_strategy_from_leg_choch` |
| `d1_authority.py` | Orchestrare + fallback V58 + override macro V68 (condiționat) |

### Reguli care deviază de la „HH/HL vizual simplu”

1. **CHoCH bullish din bearish** (`core_structure.py`): necesită body-close peste **Major LH** (Rule 2), nu simplu break de HH recent.
2. **BOS contratrend** după leg activ: filtrat ca **pullback** (`_filter_countertrend_pullback_bos`) dacă nu reclaim structural.
3. **Trend = `leg_choch.direction`**, nu ultimul BOS vizibil pe chart (`_strategy_from_leg_choch`).
4. **V69:** când leg lipsește, trend din range macro body-close — altfel legul domină.

Aceste reguli sunt **conservatoare bearish** după un crash/corecție: rally-uri bullish pot fi ignorate până la confirmări stricte Major LH.

---

## 5. Există fallback greșit la SHORT?

### Nu (eșec → neutral)

`build_d1_context()` returnează `trend='neutral'`, `direction=''` când DataFrame lipsă/invalid.

`resolve_structural_bias_fallback()` (`d1_leg.py`): inferă din macro swings / range locked — **nu** returnează bearish by default.

Bias fallback V63 (`daily_scanner.py`): folosește `_auth.trend` din același context; la eroare → log, nu forțare SHORT.

### Da (coercții secundare — de corectat la configurare)

| Loc | Comportament | Risc |
|-----|--------------|------|
| `_rehydrate_poi_from_bos_range()` | `direction = 'buy' if bullish else 'sell'` | **`neutral` → sell** |
| Log scan `direction_str` | `"LONG" if bullish else "SHORT"` | neutral apare ca SHORT în log |
| `_normalize_alert_direction()` | non-BUY → SELL | alerte 4H |

Acestea **nu explică singure** 15/16 SHORT, dar amplifică confuzia operațională.

---

## 6. De ce codul „nu citește” HH/HL/LH/LL ca pe Glitch (USDCAD)

### 6.1 Leg bearish activ + preț deasupra POI vechi

- POI ~1.386–1.391 = zonă FVG/OTE ancorată la **leg bearish** / ADR vechi.
- Preț ~1.425 = structură vizual **deasupra** ultimului LH relevant pentru ochiul uman.
- Bot: leg bearish încă **valid** dacă plafonul de invalidare (Major LH body, ~1.4106 pe date test) nu e tratat ca „flip complet” în pipeline **sau** seria D1 de pe VPS nu conține aceleași bare OHLC ca chartul.

### 6.2 W1 bullish vs D1 bearish

- `calculate_w1_bias()` (Weekly) vede macro bullish.
- D1 canonical rămâne bearish → **W+D nealiniat** în raport.
- Override V68 Pilon 1 (`d1_authority.py` l.82–92): **macro swings câștigă doar când `leg_choch is None`**. Cu leg bearish activ, **macro bullish nu flip-uiește D1**.

### 6.3 `_strategy_from_leg_choch` — CONT bearish pe rally

Pentru leg bearish:

- BOS-uri bullish post-leg = contratrend (pullback).
- Dacă există BOS bearish post-leg → semnal afișat = **ultimul BOS bearish**, trend = **bearish**, strategy = **continuation**.

Rezultat Telegram: **CONT (BOS)** + **BEARISH** — exact cardul USDCAD, chiar când chartul arată impuls bullish recent.

### 6.4 Simulări pe cache local `USDCAD` D1

| Condiție | Rezultat `build_d1_context().trend` |
|----------|--------------------------------------|
| Cache vechi, close ~1.377 | `bearish`, leg bearish, LH inv. ~1.4106 |
| Doar ultima bară close=1.425 (fără OHLC complet) | Poate rămâne `bearish` |
| Mai multe bare consecutive bullish realiste ~1.425 | Flip la `bullish` |

**Implicație VPS:** dacă prețul live e 1.425 dar ultima **bară D1 închisă** din feed e încă sub pragul de flip sau istoricul nu e la zi, bias rămâne bearish deși cTrader afișează preț spot.

### 6.5 Distribuție panel (cache local, 16 simboluri)

Pe `data/historical_cache` + `build_d1_context`:

- **12 bearish / 4 bullish / 0 neutral**
- Exemple **macro bullish, trend bearish:** AUDJPY, EURGBP, GBPJPY, USDCHF → pattern W+D nealiniat

Test existent: `tests/test_d1_bias_canonical.py::test_scanner_panel_not_monochrome_bearish` cere ≥3 bullish și ≥3 bearish — trece, dar **skew-ul rămâne puternic bearish** (compatibil cu raportul utilizatorului 15/16).

---

## 7. Unde s-a pierdut „esența” Glitch (drift arhitectural)

| Strat | Versiune / intent | Efect asupra citirii setup-urilor |
|-------|-------------------|-----------------------------------|
| Body-close strict | V36+ | Sweep-uri vs break real — corect SMC, dar întârzie flip față de HH wick |
| Major swings only | V68 | Micro HH/HL de pe chart nu generează BOS/CHoCH |
| Leg matrix | V63–V67 | Trend = leg vechi până la invalidare Major LH/HL — **persistent bearish** |
| Pullback demotion | V68 Pilon 1 | BOS bullish în leg bearish = noise, nu schimbare caracter |
| Macro override | V68 | Doar fără leg — **W1/macro nu repară D1** când leg există |
| Range lock bearish | V40 | LH/LL locked → bias bearish cât timp close ≤ plafon |
| D1 authority unică | V67 | Scanner + JSON + card = aceeași sursă — **greșeala e consistentă**, nu random |
| POI V70 | OTE fallback | **Nu atinge bias** — doar zone POI când lipsește FVG organic |

**Esenta pierdută (formulare pentru configurare viitoare):**

> Direcția D1 ar trebui să urmeze **ultimul impuls structural valid HH/HL sau LH/LL** pe timeframe Daily (Glitch), cu aliniere W1 și POI în P/D corespunzător.  
> Implementarea actuală urmărește **leg CHoCH istoric + filtre anti-false-break** care **îngheță bearish** multe piețe aflate deja în re-expansiune bullish (și simetric invers).

---

## 8. Impact V70 Daily POI (commit recent)

| Fișier | Schimbare | Afectează bias D1? |
|--------|-----------|-------------------|
| `smc_detector/fvg.py` | P/D strict, OTE box | **Nu** |
| `smc_detector/poi.py` | `ote_pd_fallback` | **Nu** |
| `daily_scanner.py` | `_apply_poi_to_setup_dict`, POI obligatoriu JSON | **Nu** (citește bias existent pentru entry) |
| `multi_tf_radar.py` | POI missing ≠ 0.0 | **Nu** |

V70 poate face POI-ul **coerent cu un leg bearish greșit** (zonă jos, preț sus) — simptom vizual în card, nu cauza bias-ului.

---

## 9. Fișiere de atins la „reconfigurare sistem” (prompt următor)

### Autoritate & structură (prioritate 1)

- `smc_detector/d1_authority.py` — `build_d1_context`, macro override cu leg activ
- `smc_detector/d1_leg.py` — `_resolve_pure_d1_matrix`, `_strategy_from_leg_choch`, invalidare LH/HL, pullback filters
- `smc_detector/core_structure.py` — `detect_choch_and_bos`, Rule 2 Major LH/HL
- `smc_detector/core_swings.py` — `macro_trend_from_swings`, major filter

### Orchestrare & persistență (prioritate 2)

- `daily_scanner.py` — bias map, bias fallback V63, rehydrate V62, coercții neutral→sell
- `smc_detector/scan_setup.py` — consum `d1_ctx`
- `smc_detector/scan_finalize.py` — `d1_bias_direction` pe TradeSetup

### Raportare (prioritate 3 — verificare, nu sursă bug)

- `telegram_notifier.py` — MARKET_REPORT, format_setup_alert

### Teste de regresie

- `tests/test_d1_bias_canonical.py` — mix bullish/bearish, USDCAD/XAUUSD, panel non-monochrome
- `tests/test_d1_poi_strict_pd_ote.py` — POI (separat de bias)

---

## 10. Ipoteze de verificat pe VPS (fără cod)

1. Log scanner `[PURE SMC] leg CHoCH` pentru USDCAD: direction, bar index, LH invalidation level vs close ultimă bară D1.
2. Compară **ultima bară D1 din cTrader** (OHLC închis) cu prețul **live** din card — dacă diferă, bias folosește close D1, nu spot.
3. Export `monitoring_setups.json`: `direction`, `d1_bias_direction`, `daily_bias`, `w1_bias`, `d1_signal_type`, `poi_top/bottom`.
4. Rulează pytest `test_d1_bias_canonical` pe VPS cu cache-ul live al datelor.
5. Verifică commit deploy: branch `cursor/v36-3-radar-live-sync` include V67+ authority (nu doar V70 POI).

---

## 11. Direcții de lucru recomandate (pentru prompt configurare)

1. **Reancorare Glitch D1:** definire explicită când HH+HL (sau LH+LL) recente **suprascriu** leg CHoCH vechi — simetric bullish/bearish.
2. **Macro + W1:** când W1 bullish și close D1 > plafon structural bearish, D1 trebuie să poată trece bullish fără a aștepta CHoCH filtrat complet.
3. **Citire swing-uri:** audit parametri `swing_lookback`, `filter_major_swings`, ATR — aliniere la pivotii de pe TradingView.
4. **Eliminare coercții:** `neutral` ≠ `sell`; logging SHORT doar pentru `bearish` confirmat.
5. **Test golden USDCAD:** bară D1 la ~1.425+ cu structură HH/HL → `trend == bullish`, `direction == buy`, W+D aliniat sau fără contradicție flagrantă.
6. **Document MASTER SPEC:** o singură pagină „truth table” HH/HL/LH/LL → bias / CHoCH / BOS / invalidare — codul să o implementeze literal.

---

## 12. Rezumat one-liner

**Codul actual citește setup-urile prin prisma unui leg bearish conservator (V67+), nu prin ultimul caracter structural Daily pe care îl vezi pe Glitch; MARKET_REPORT roșu este consecința consistentă a JSON `sell`, iar USDCAD exemplifică conflictul D1 bearish vs W1/chart bullish — nu un bug de Telegram și nu V70 POI.**

---

*Document generat din audit read-only sesiune 2026-10-08. Următorul pas: prompt de configurare sistem pe baza secțiunilor 9–11.*

---

## 13. Remediere implementată — V71 Glitch lifecycle (2026-10-09)

| Modul | Schimbare |
|-------|-----------|
| `core_structure.py` | Rule 2 Major LH/HL eliminată; CHoCH la body-close confirmat; `filter_internal_range_signals` passthrough |
| `d1_leg.py` | `_resolve_pure_d1_matrix` = ultim CHoCH/BOS; `_coerce_leg_with_boundary_gate` passthrough |
| `d1_authority.py` | Eliminat override macro V68 când leg absent |
| `scan.py` | Docstring lifecycle D1 → POI → 4H → BOS |

**Validare cache local:** USDCAD `trend=bullish`; panel 16 simboluri **8 bullish / 8 bearish** (vs ~12 bearish înainte).
