# 🔬 AUDIT DIAGNOSTIC REPORT — Glitch in Matrix V11.2
**Data:** 1 Mai 2026 → Actualizat: 4 Mai 2026  
**Analizat de:** Claude Sonnet 4.6  
**Fișiere auditate:** `setup_executor_monitor.py` (2190 linii) + `smc_detector.py` (5438 linii) + `unified_risk_manager.py` (920 linii) + `audit_monitoring_setups.py` (485 linii)  
**Status cont:** LIVE — IC Markets #6139026  
**Verdict global:** ⚠️ 11 Logic Leaks active cu risc direct pe cont LIVE

---

## 📋 CUPRINS

1. [FINDING #1 — Continuation Bypass fără CHoCH 4H real](#finding-1)
2. [FINDING #2 — BOS tratat identic cu CHoCH în execuție](#finding-2)
3. [FINDING #3 — CHoCH confirmed=True by default (wick poate declanșa)](#finding-3)
4. [FINDING #4 — Fallback nesigur de la 4H sync FVG la Daily FVG](#finding-4)
5. [FINDING #5 — Audit Operațional (Timezone, W1 Depth, Cache)](#finding-5)
6. [FINDING #6 — RR nu este revalidat la momentul execuției](#finding-6)
7. [FINDING #7 — SL de 385 pips a trecut filtrul de 100 pips](#finding-7)
8. [FINDING #8 — Pip value fix $10 incorect pentru cross pairs](#finding-8)
9. [FINDING #9 — V13.2 GENERALUL: SL ia maximul din TOATĂ istoria, nu ultimul swing valid](#finding-9)
10. [FINDING #10 — 'continuation' vs 'continuity': typo silențios forțează TOATE setup-urile la REVERSAL](#finding-10)
11. [FINDING #11 — Setup-uri stale (vârstă > 7 zile) rămân active în monitoring](#finding-11)
12. [FINDING #12 — CHoCH nu se întâmplă "o singură dată": botul ia ultimul CHoCH minor, nu major](#finding-12)
13. [Risk Summary Table](#risk-summary)
14. [Lanțurile de execuție periculoase](#lanturile-de-executie)

---

## FINDING #1 — Continuation Bypass fără CHoCH 4H real {#finding-1}

**Severitate:** 🔴 CRITIC  
**Fișier:** `setup_executor_monitor.py`  
**Linii:** 952–988  
**Funcție:** `_check_pullback_entry()`

### Ce face codul:

```python
# V10.9 CONTINUATION BYPASS
if not h4_locked and strategy_type == 'continuation':
    d1_bias = setup.get('d1_bias_direction', '').lower()
    trade_dir = direction

    # V16.0 FVG PROXIMITY
    if 'JPY' in symbol.upper():
        fvg_proximity_ok = (current_price <= fvg_top + 0.20) if direction == 'buy' \
                           else (current_price >= fvg_bottom - 0.20)
    else:
        fvg_proximity_ok = (current_price <= fvg_top + 0.0020) if direction == 'buy' \
                           else (current_price >= fvg_bottom - 0.0020)

    if d1_bias and trade_dir != expected_dir:
        logger.warning(...)  # BLOCAT: direcție opusă D1
    elif not fvg_proximity_ok:
        logger.warning(...)  # BLOCAT: prea departe de FVG
    else:
        setup['h4_structure_locked'] = True  # ← BYPASS! Fără CHoCH real.
        h4_locked = True
```

### Problema exactă:

Dacă `strategy_type` din `monitoring_setups.json` este `"continuation"` (sau orice string care începe cu `"continuation"`), codul setează `h4_structure_locked = True` **fără să detecteze niciun CHoCH pe 4H**. Singura barieră e verificarea de proximitate față de FVG.

### Valorile proximității (prea permisive):

| Pereche | Proximitate permisă | În pips reali |
|---------|---------------------|---------------|
| JPY (ex. GBPJPY) | ± 0.20 yeni | **~20 pips** |
| Forex standard | ± 0.0020 | **~20 pips** |
| BTC/ETH | ± 500 USD | **~500 USD** |

### De ce e periculos:

Prețul poate fi la **20 pips deasupra FVG** (fără să fi atins zona) și sistemul consideră că structura 4H e confirmată. Nicio lumânare 4H nu trebuie să fi închis cu corpul în nicio direcție.

### Context istoric:

Comentariul din cod (linia 963) documentează exact acest bug:
```python
# BUG FIX (18 Apr 2026): GBPJPY executat la 213 cu FVG la 211.8-212 prin momentum fallback
```
Fix-ul V16.0 a adăugat proximity check, dar **bypass-ul fundamental rămâne** — nu există CHoCH 4H real cerut.

### Fix necesar:

Bypass-ul V10.9 ar trebui să verifice că există cel puțin un **BOS 4H recent** (ultimele 20 bare) în direcția corectă, nu doar că prețul e aproape de FVG.

---

## FINDING #2 — BOS tratat identic cu CHoCH în execuție {#finding-2}

**Severitate:** 🔴 CRITIC  
**Fișier:** `setup_executor_monitor.py`  
**Linii:** 1060–1085  
**Funcție:** `_check_pullback_entry()` — Step 1

### Ce face codul:

```python
# Combine CHoCH and BOS for unified structure break detection
chochs, bos_list = self.smc_detector.detect_choch_and_bos(df_h1)
all_breaks = chochs + bos_list  # ← AMESTECATE!

for break_obj in reversed(all_breaks):
    break_price = break_obj.break_price
    in_fvg = fvg_bottom <= break_price <= fvg_top
    direction_match = (...)

    if in_fvg and direction_match:
        matching_break = break_obj  # ← BOS sau CHoCH, tratate LA FEL
        break_type = "CHoCH" if break_obj in chochs else "BOS"
        break
```

### Problema exactă:

**CHoCH** = Change of Character = schimbare de trend (reversare).  
**BOS** = Break of Structure = continuarea trendului existent.

Din punct de vedere SMC, un BOS pe 1H nu semnalează că prețul este gata de intrare — semnalează că trendul continuă. Strategia corectă cere un **CHoCH pe 1H** (micro-reversare spre zona de intrare), **nu un BOS**.

Un BOS în interiorul Daily FVG înseamnă că prețul continuă în direcția trendului **prin** zona de intrare — exact opusul unui pullback.

### Exemplu concret:

Setup SELL (EUR/USD bearish). FVG Daily: 1.0850–1.0900.  
Prețul urcă la 1.0870 (în FVG) și face BOS bullish (continuare urcuș).  
Sistemul detectează BOS bullish în FVG → `direction_match` pentru SELL? Nu — dar dacă era un setup BUY cu FVG Daily bullish și BOS bullish în zonă → execuție imediată fără CHoCH real.

### Fix necesar:

Step 1 trebuie să filtreze **exclusiv CHoCH** (`chochs`), nu `all_breaks`. BOS-urile să fie ignorate complet în logica de entry.

---

## FINDING #3 — CHoCH `confirmed=True` by default {#finding-3}

**Severitate:** 🟠 RIDICAT  
**Fișier:** `smc_detector.py`  
**Linii:** 1163 și 1240  
**Funcție:** `detect_choch_and_bos()`

### Ce face codul:

```python
# RELAXED: Allow CHoCH even without full confirmation (MONITORING status)
confirmed = True  # Default to true for monitoring

# If we have recent data after break, validate confirmation
if len(swings_after_break) >= 1:
    highs_after = [s for s in swing_highs if s.index > j]
    if len(highs_after) >= 1:
        if any(h.price > swing.price for h in highs_after):
            confirmed = True  # ← Deja True, această linie e redundantă
```

### Problema exactă:

`confirmed` este setat `True` **înainte** de orice verificare. Codul ulterior poate seta `confirmed = True` din nou (redundant) dar **nu poate seta `confirmed = False`** — nu există nicio ramură care să respingă.

Rezultat:
- Dacă nu există swings după break → `confirmed = True` (valid fără confirmare)
- Dacă există swings dar nu confirmă structura → `confirmed = True` (acceptat oricum)
- Singurul caz în care CHoCH e respins: nu îndeplinește condițiile LH+LL sau HH+HL înainte de break (liniile de `if hh_pattern and hl_pattern`)

### Scenariul periculos:

Pe 1H cu mișcare rapidă: prețul sparge un swing high cu CORPUL (valid), nu există niciun swing format după break (piața e în mișcare) → `swings_after_break` e gol → `confirmed = True` → CHoCH adăugat în listă → Fibonacci calculat → dacă Fibo 50% e atins → EXECUȚIE.

Un impuls puternic care sparge structura și continuă → CHoCH "confirmat" → intrare împotriva trendului real.

### Fix necesar:

Inversarea logicii: `confirmed = False` by default. Să se seteze `True` **doar** dacă există cel puțin un swing valid post-break care confirmă structura.

---

## FINDING #4 — Fallback nesigur de la 4H sync FVG la Daily FVG {#finding-4}

**Severitate:** 🟠 RIDICAT  
**Fișier:** `setup_executor_monitor.py`  
**Linii:** 1000–1018  
**Funcție:** `_check_pullback_entry()` — după 4H lock

### Ce face codul:

```python
if confirmed_4h and valid_4h_lock:
    # Detectăm FVG generat de mișcarea CHoCH 4H (entry zone optimă)
    sync_fvg = self.smc_detector.detect_fvg(df_4h_lock, valid_4h_lock, current_price_4h)
    if sync_fvg:
        setup['h4_sync_fvg_top'] = float(sync_fvg.top)
        setup['h4_sync_fvg_bottom'] = float(sync_fvg.bottom)
    else:
        logger.info(f"⚠️ No 4H sync FVG — using Daily FVG for entry")
        # ← NICIO MODIFICARE A fvg_top/fvg_bottom — rămâne Daily FVG!
```

Și mai sus, la începutul funcției:

```python
if h4_sync_top > 0 and h4_sync_bottom > 0:
    fvg_top = h4_sync_top    # Ideal: 4H sync FVG
    fvg_bottom = h4_sync_bottom
else:
    fvg_top = setup.get('fvg_zone_top', ...)   # Fallback: Daily FVG (mult mai larg!)
    fvg_bottom = setup.get('fvg_zone_bottom', ...)
```

### Problema exactă:

Diferența de dimensiune între FVG-uri:

| Tip FVG | Dimensiune tipică | Precizie entry |
|---------|------------------|----------------|
| 4H sync FVG | 15–40 pips | ✅ Precisă |
| Daily FVG | 80–300 pips | ❌ Laxă |

Când CHoCH 4H nu lasă un FVG clar (mișcare prea agresivă, gap inexistent), sistemul cade automat pe Daily FVG. Prețul poate fi la 150 pips de centrul Daily FVG și tot să declanșeze execuție dacă Fibo 50% dintr-un micro-swing 1H e atins în interiorul zonei largi.

### Scenariul periculos:

1. CHoCH 4H confirmat (valid, cu body close)
2. Nu există 4H sync FVG (impuls puternic fără gap)
3. Daily FVG: 1.2800–1.3100 (300 pips)
4. Preț curent: 1.2950 (mijlocul zonei)
5. 1H BOS la 1.2960 → Fibo 50% la 1.2955
6. Preț coboară 5 pips → EXECUȚIE la 1.2955 fără niciun POI real touchat

### Fix necesar:

Dacă nu există 4H sync FVG, execuția ar trebui **blocată** (nu fallback la Daily FVG), sau cel puțin ar trebui cerut ca prețul să fie în **treimea superioară/inferioară a Daily FVG** (discount/premium strict).

---

## FINDING #5 — Audit Operațional {#finding-5}

### 5a. Timezone — Windows VPS ignoră `os.environ['TZ']`

**Severitate:** 🟡 MEDIU  
**Fișier:** `setup_executor_monitor.py`  
**Linii:** 42–47

```python
os.environ['TZ'] = 'UTC'
try:
    time.tzset()   # ← funcționează DOAR pe Unix/Linux/Mac
except AttributeError:
    pass           # ← Windows: excepție ignorată silențios
```

Pe Windows VPS, `time.tzset()` nu există și `os.environ['TZ']` nu afectează `datetime.now()`. Rezultat: `datetime.now()` returnează ora serverului VPS (ex. UTC-5 dacă datacenterul e în SUA de Est).

**Impact concret:** Timeout-ul de 24h pentru pullback e calculat greșit — un setup creat la 20:00 UTC poate expira după 19h sau 29h reale, nu 24h. Execuțiile forțate la timeout pot apărea la ore nepotrivite.

**Inconsistență în cod:** Unele locuri folosesc corect `datetime.now(timezone.utc)` (liniile 177, 317, 339, 381), altele folosesc `datetime.now()` fără UTC (liniile 250, 270, 295, 301).

### 5b. W1 Data Depth — OK

**Severitate:** ✅ NICIO PROBLEMĂ  
Cererea de 300 bare W1 (~5.7 ani) este configurată corect:
```python
df_w1_alert = self._get_cached_data(symbol, "W1", 300)
```
Cache-ul W1 de 24h este adecvat (bara se schimbă săptămânal). Nu există problemă de depth.

**Risc minor:** Dacă cBot-ul MarketData (port 8010) returnează mai puțin de 300 bare, nu există validare — codul procesează silențios mai puțin context W1 decât așteptat.

### 5c. AttributeError pe Swing Cache — Cauza exactă

**Severitate:** 🟡 MEDIU  
**Fișier:** `smc_detector.py`, linia 5378 (funcția standalone `get_4h_body_close_confirmation`)

```python
def get_4h_body_close_confirmation(df_4h, daily_trend, ...):
    detector = SMCDetector()  # ← INSTANȚĂ NOUĂ la fiecare apel!
    h4_chochs, _ = detector.detect_choch_and_bos(df_4h)
```

**Problema 1 — Performance:** La fiecare ciclu de 30s, pentru fiecare pereche monitorizată, se creează un obiect `SMCDetector` nou cu cache gol. Swing-urile 4H se recalculează de la zero de fiecare dată. La 15 perechi = 15 recalculări complete per ciclu, inutil.

**Problema 2 — AttributeError potențial:** Dacă `df_4h` nu conține coloanele `open`, `close`, `high`, `low` (cBot-ul returnează un format diferit sau câmpuri lipsă), `detect_choch_and_bos` aruncă `AttributeError` la accesarea `df[['open', 'close']].max(axis=1)`. Eroarea e prinsă de `except Exception as e: return False, None, reason` și ignorată silențios — sistemul continuă cu `h4_locked = False` și nu știi că analiza 4H a eșuat.

**Problema 3 — Thread safety:** Dacă `setup_executor_monitor.py` și `watchdog_monitor.py` rulează în același proces sau accesează același obiect `SMCDetector`, cache-ul dict poate fi modificat concurent → `RuntimeError` care apare ca `AttributeError` în loguri.

---

## 📊 RISK SUMMARY {#risk-summary}

| # | Finding | Fișier | Linii | Severitate | Impact Direct |
|---|---------|--------|-------|-----------|---------------|
| 1 | Continuation bypass fără CHoCH 4H | `setup_executor_monitor.py` | 952–988 | 🔴 CRITIC | Intrare fără confirmare structurală 4H |
| 2 | BOS = CHoCH în Step 1 entry logic | `setup_executor_monitor.py` | 1060–1085 | 🔴 CRITIC | BOS de continuare declanșează execuție |
| 3 | CHoCH `confirmed=True` by default | `smc_detector.py` | 1163, 1240 | 🟠 RIDICAT | False CHoCH din impuls fără confirmare |
| 4 | Fallback 4H FVG → Daily FVG | `setup_executor_monitor.py` | 1000–1018 | 🟠 RIDICAT | Zone entry de 200-300 pips, nicio precizie |
| 5a | `datetime.now()` fără UTC pe Windows | `setup_executor_monitor.py` | 250, 270, 295 | 🟡 MEDIU | Timeout ±5h eronat |
| 5b | W1 depth | — | — | ✅ OK | Nicio problemă |
| 5c | Cache per-instanță + silent errors | `smc_detector.py` | 5378 | 🟡 MEDIU | Analiza 4H poate eșua silențios |

---

## ⛓️ LANȚURILE DE EXECUȚIE PERICULOASE {#lanturile-de-executie}

### Lanț A — "Continuation cu preț în aer" (Finding #1 + #4)

```
monitoring_setups.json: strategy_type='continuation'
    ↓
V10.9 BYPASS: h4_locked=True fără CHoCH (prețul la max 20 pips de FVG)
    ↓
4H sync FVG absent → fallback la Daily FVG (200-300 pips larg)
    ↓
Step 1: BOS 1H în Daily FVG detectat (Finding #2)
    ↓
Fibonacci 50% calculat din micro-swing 1H
    ↓
EXECUȚIE la Fibo 50% — prețul niciodată n-a atins POI-ul real
```

### Lanț B — "False CHoCH din impuls rapid" (Finding #3 + #2)

```
Piața face impuls puternic pe 1H (news, breakout)
    ↓
detect_choch_and_bos: body sparge swing → confirmed=True (fără swings post-break)
    ↓
all_breaks conține acest CHoCH/BOS → matching_break găsit în FVG
    ↓
Fibonacci calculat → Fibo 50% = mijlocul impulsului
    ↓
EXECUȚIE în mijlocul unui impuls, contra-trend real
```

### Lanț C — "READY status: execuție directă la preț greșit"

```
multi_tf_radar.py marchează setup ca status='READY' cu entry_price=X
    ↓
Prețul pieței s-a mișcat între timp (ex. 50 pips)
    ↓
_process_monitoring_setups: status=='READY' → execuție directă la setup['entry_price']=X
    ↓
Re-validare 4H: max_age_candles=48 (8 zile!) → CHoCH vechi de 7 zile e considerat valid
    ↓
EXECUȚIE la preț depășit, fără verificare că prețul actual e în POI
```

---

---

## FINDING #6 — RR nu este revalidat la momentul execuției {#finding-6}

**Severitate:** 🔴 CRITIC  
**Fișier:** `setup_executor_monitor.py`  
**Linii:** ~1760–1780  
**Funcție:** `_process_monitoring_setups()` — blocul `EXECUTE_ENTRY1`

### Ce face codul:

```python
success = self._execute_entry(
    setup=setup,
    entry_number=1,
    entry_price=result['entry_price'],
    stop_loss=result['stop_loss'],       # ← din setup JSON salvat
    take_profit=setup['take_profit'],    # ← din setup JSON salvat
    position_size=...
)
```

### Problema exactă:

Filtrul RR 1:4 există **doar în `calculate_entry_sl_tp()`** din `smc_detector.py` (linia ~2580), care rulează **la momentul scanării** (daily scanner). La execuție, valorile SL și TP sunt citite direct din `monitoring_setups.json` fără nicio revalidare.

**Scenariul concret GBPNZD:**
- La momentul scanării: RR calculat = 1:1.62 (sub filtrul de 1:4)
- Filtrul **ar fi trebuit să respingă** setup-ul la scanner
- Dacă setup-ul a ajuns în `monitoring_setups.json` cu aceste valori (ex. dintr-o versiune mai veche a scannerului, sau prin `multi_tf_radar.py` care nu aplică filtrul RR), la execuție **nimeni nu mai verifică RR-ul**
- Trade executat cu R:R 1:1.62 — risc > reward

**Locul unde lipsește verificarea:**

```python
# LIPSĂ: Revalidare RR înainte de execuție
# Ar trebui să existe:
rr = abs(take_profit - entry_price) / abs(entry_price - stop_loss)
if rr < 2.0:  # minimum acceptabil la execuție
    logger.warning(f"⛔ RR {rr:.2f} sub minim la execuție — BLOCAT")
    return 'KEEP_MONITORING'
```

### Fix necesar:

Adaugă validare RR minimă (≥ 1:2) direct în `_process_monitoring_setups()` înainte de a apela `_execute_entry()`. Separată de filtrul de 1:4 din scanner (care poate fi mai strict).

---

## FINDING #7 — SL de 385.5 pips a trecut filtrul de 100 pips {#finding-7}

**Severitate:** 🔴 CRITIC  
**Fișier:** `smc_detector.py`  
**Linii:** ~2407–2415  
**Funcție:** `calculate_entry_sl_tp()`

### Ce face codul:

```python
_max_sl_pips = 200 if 'JPY' in symbol else 100
if sl_distance_pips > _max_sl_pips:
    return None, None, None  # RESPINS
```

### Problema exactă:

Filtrul de 100 pips există în `calculate_entry_sl_tp()` — dar **această funcție nu este apelată de `setup_executor_monitor.py` la execuție**. Este apelată de `daily_scanner.py` la generarea setup-ului.

Există **două căi prin care SL-ul ajunge în setup JSON**:

**Calea 1 — `daily_scanner.py`** → apelează `calculate_entry_sl_tp()` → filtru 100 pips activ ✅  
**Calea 2 — `validate_pullback_entry()` / `calculate_choch_fibonacci()`** → calculează SL direct din swing structural fără filtru de pips ❌

Dacă setup-ul vine prin `multi_tf_radar.py` sau prin re-evaluare, SL-ul poate fi setat din swing structural (ex. 385 pips) fără să treacă prin filtrul de 100 pips.

În plus, `_check_pullback_entry()` din executor (`setup_executor_monitor.py` linia ~790) recalculează SL astfel:
```python
structural_sl = setup.get('stop_loss')  # ← folosit ca-atare, fără validare pips
```

**Efectul:** Un SL de 385.5 pips pe GBPNZD la 0.01 lots = **$22.87 risc** (din screenshot). La 5% risc din $789, ar trebui să fie ~$39 → lotajul calculat e 0.01 datorită pip value greșit (Finding #8).

### Fix necesar:

Adaugă validare `max_sl_pips` și în `_execute_entry()` din `setup_executor_monitor.py`. Orice SL > 150 pips (forex non-JPY) sau > 300 pips (JPY) → BLOCAT la execuție.

---

## FINDING #8 — Pip value fix $10 incorect pentru cross pairs {#finding-8}

**Severitate:** 🟠 RIDICAT  
**Fișier:** `unified_risk_manager.py`  
**Linii:** 617–628  
**Funcție:** `validate_new_trade()`

### Ce face codul:

```python
else:
    # Standard forex: pip at 4th decimal (0.0001)
    pip_size = 0.0001
    pip_value = 10.0  # $10 per standard lot per pip
```

### Problema exactă:

`pip_value = $10.00` este corect **exclusiv** pentru perechi cu USD ca quote currency (EURUSD, GBPUSD, AUDUSD, NZDUSD). Pentru orice altă pereche, pip value-ul real în USD depinde de cursul quote currency față de USD la momentul tranzacției.

**Tabel erori concrete:**

| Pereche | Quote | Pip value real/lot | Cod folosește | Eroare |
|---------|-------|--------------------|---------------|--------|
| EURUSD | USD | **$10.00** | $10.00 | ✅ Corect |
| GBPUSD | USD | **$10.00** | $10.00 | ✅ Corect |
| GBPNZD | NZD | **~$5.90** (NZD/USD≈0.59) | $10.00 | ❌ +69% supraevaluat |
| GBPCAD | CAD | **~$7.20** (CAD/USD≈0.72) | $10.00 | ❌ +39% supraevaluat |
| USDCHF | CHF | **~$11.60** (CHF/USD≈1.16) | $10.00 | ❌ -14% subevaluat |
| EURGBP | GBP | **~$12.60** (GBP/USD≈1.26) | $10.00 | ❌ -21% subevaluat |
| EURJPY | JPY | **$6.80** (JPY pip = 0.01) | $10.00 | ❌ +47% supraevaluat |
| AUDJPY | JPY | **$6.80** | $10.00 | ❌ +47% supraevaluat |

**Efectul concret pe GBPNZD (din screenshot):**

```
Risk dorit:   $789.59 × 5% = $39.48
SL pips:      385.5

Cod calculează:
  lot_size = $39.48 / (385.5 × $10.00) = 0.0102 → 0.01 lots
  Risc real:  0.01 × 385.5 × $5.90 = $22.74  ← confirmat de screenshot ($22.87)

Lot corect ar fi:
  lot_size = $39.48 / (385.5 × $5.90) = 0.0173 → 0.02 lots
  Risc real: 0.02 × 385.5 × $5.90 = $45.49 ≈ 5.76% din cont
```

**Concluzie:** Pe GBPNZD botul risca **2.89% din cont** în loc de 5%. Pe USDCHF risca **5.8%** în loc de 5%. Pe EURJPY risca **3.4%** în loc de 5%. Calculul de lot size e sistematic greșit pentru toate cross pairs.

### Fix necesar:

Înlocuiește `pip_value = 10.0` fix cu calcul dinamic bazat pe quote currency. Cel mai simplu: obține cursul curent USD/quote din prețurile disponibile în cBot sau dintr-un dict de rate statice actualizate zilnic.

**Implementare minimă (rate statice hardcodate, actualizate la fiecare restart):**
```python
# Pip value = 10.0 × (USD/quote_currency_rate)
quote_to_usd_rates = {
    'NZD': 0.59, 'CAD': 0.72, 'CHF': 1.16,
    'GBP': 1.26, 'EUR': 1.08, 'AUD': 0.64,
    'JPY': 0.0067,  # 1 JPY = 0.0067 USD
}
```

---

## FINDING #9 — V13.2 GENERALUL: SL ia maximul din TOATĂ istoria {#finding-9}

**Severitate:** 🔴 CRITIC  
**Fișier:** `smc_detector.py`  
**Linii:** 2491–2510 (SHORT) și ~2387–2420 (LONG)  
**Funcție:** `calculate_entry_sl_tp()`

### Ce face codul:

```python
# V13.2 FIX: MAX wick HIGH dintre TOATE swing-urile pre-CHoCH = GENERALUL
highs_before_choch = [sh for sh in swing_highs_4h_list if sh.index <= h4_choch_idx]

# ← PROBLEMA: ia MAXIMUL absolut din toată lista, nu ultimul swing
general_wick_high = max(df_4h['high'].iloc[sh.index] for sh in highs_before_choch)
stop_loss = general_wick_high + sl_buffer
```

### Problema exactă:

`highs_before_choch` conține **TOATE** swing-urile 4H de la începutul istoricului până la CHoCH. `max()` returnează **nivelul cel mai înalt din ultimele 3-6 luni**, nu ultimul swing valid.

**Regula SMC corectă:** SL = **ultimul** swing valid înainte de CHoCH (cel mai recent fractal structural), nu maximul absolut din toată istoria.

**Dovadă concretă — GBPNZD SELL (01/05/2026):**

```
highs_before_choch = [swing @ idx 12 (2.33966), swing @ idx 45 (2.31200), swing @ idx 67 (2.30500)]
max() → 2.33966 (swing din IANUARIE 2026 — 3 luni în urmă!)
SL = 2.33966 + buffer = 2.33970
Entry = 2.30111
Distanță SL = 385.5 pips  ← CONFIRMAT ÎN SCREENSHOT

Regula corectă ([-1] = ultimul swing):
last_swing = highs_before_choch[-1]  # idx=67, wick_high=2.30500
SL = 2.30500 + buffer = 2.30510
Distanță SL = ~40 pips  ← SL corect
```

### Istoricul bug-ului (regresia V13.2):

V13.2 a fost creat ca fix pentru USDCHF (7 Apr 2026) unde `[-1]` lua un fractal minor de 80 pips sub "Generalul" structural. Fix-ul corect era să filtreze fractalii minori, dar implementarea a ales `max()` din toată istoria → **overcorrecție fatală**.

| Versiune | Metodă SL | Problema |
|----------|-----------|----------|
| Pre-V13.2 | `highs_before_choch[-1]` | Lua ultimul fractal, putea fi fractal minor |
| V13.2 | `max(highs_before_choch)` | Ia maximul absolut din 3-6 luni istorie ← **BUG ACTUAL** |
| Corect | `highs_before_choch[-1]` cu filtru ATR | Ultimul swing valid, filtrat de micro-fractali |

### Fix necesar:

```python
# CORECT — ultimul swing valid pre-CHoCH, filtrat de micro-fractali
lows_before_choch_sorted = sorted(highs_before_choch, key=lambda s: s.index, reverse=True)
# Filtrăm fractali prea mici (sub 0.5x ATR) — fix real pentru problema USDCHF
atr = df_4h['high'].rolling(14).mean().iloc[-1] - df_4h['low'].rolling(14).mean().iloc[-1]
for sh in lows_before_choch_sorted:
    wick = df_4h['high'].iloc[sh.index]
    if wick > entry + atr * 0.5:  # Swing semnificativ
        stop_loss = wick + sl_buffer
        break
```

---

## FINDING #10 — 'continuation' vs 'continuity': typo silențios forțează TOATE setup-urile la REVERSAL {#finding-10}

**Severitate:** 🔴 CRITIC  
**Fișier:** `audit_monitoring_setups.py`  
**Linii:** 286–288  
**Impact:** Toate cele 12 setup-uri din radar apar ca REVERSAL — confirmat în screenshot (03/05/2026)

### Ce face codul:

```python
# audit_monitoring_setups.py linia 286
strategy_type = setup_data.get('strategy_type', 'REVERSAL').upper()

# Linia 287-288 — THE BUG
if strategy_type not in ['REVERSAL', 'CONTINUITY']:
    strategy_type = 'REVERSAL'  # Default fallback ← forțat silențios!
```

### Problema exactă:

`smc_detector.py` (linia ~814 din `scan_for_setup()`) salvează în JSON:
```python
'strategy_type': 'continuation'   # ← cu 'tion', nu 'ity'
```

`audit_monitoring_setups.py` validează față de:
```python
['REVERSAL', 'CONTINUITY']   # ← cu 'ity', nu 'tion'
```

`'continuation'.upper()` → `'CONTINUATION'` ≠ `'CONTINUITY'` → forțat la `'REVERSAL'`.

**Rezultat:** Orice setup de tip continuation apare în radar ca REVERSAL. Logica de display și filtrare e incorectă pentru toate setup-urile continuation.

| Valoare salvată în JSON | După `.upper()` | Whitelist conține | Match? | Afișat ca |
|------------------------|-----------------|------------------|--------|-----------|
| `"reversal"` | `"REVERSAL"` | `"REVERSAL"` | ✅ | REVERSAL ✓ |
| `"continuation"` | `"CONTINUATION"` | `"CONTINUITY"` | ❌ | **REVERSAL ✗** |

### Dovadă din screenshot (03/05/2026):
Toate 12 setup-uri active (USDCAD, USDJPY, XTIUSD, GBPJPY, EURJPY etc.) apar cu label **REVERSAL** — statistic imposibil ca toate 12 perechi să fie simultan în setup de reversare.

### Fix necesar:

```python
# CORECT — normalizare completă
strategy_type = setup_data.get('strategy_type', 'reversal').upper()
# Acceptă ambele variante istorice
if strategy_type == 'CONTINUITY':
    strategy_type = 'CONTINUATION'
if strategy_type not in ['REVERSAL', 'CONTINUATION']:
    strategy_type = 'REVERSAL'
```

### Verificare suplimentară necesară:

`setup_executor_monitor.py` citește și el `strategy_type` din JSON la linia ~952 (`if strategy_type == 'continuation'`). Acesta compară cu lowercase `'continuation'` — deci **executorul funcționează corect**. Bug-ul e doar în **display/audit** (`audit_monitoring_setups.py`), dar creează confuzie masivă pentru user.

---

## FINDING #11 — Setup-uri stale (vârstă > 7 zile) rămân active în monitoring {#finding-11}

**Severitate:** 🟠 RIDICAT  
**Fișier:** `setup_executor_monitor.py`  
**Linii:** ~1700 (timeout logic)  
**Dovadă:** Screenshot 03/05/2026 — GBPJPY LONG setup creat `2026-04-18T19:45:59` → **15 zile** în monitoring, FVG la 200-204, preț la 212 → **90,955 pips distanță**

### Ce face codul:

```python
# Timeout: 24h de la crearea setup-ului
setup_age = (datetime.now(timezone.utc) - setup_created_at).total_seconds() / 3600
if setup_age > 24:
    # Force entry sau expire
    if allow_timeout_entry:
        result = {'action': 'EXECUTE_ENTRY1_TIMEOUT', ...}
    else:
        setup['status'] = 'EXPIRED'
```

### Problema exactă:

Timeoutul de 24h este **corect în teorie**, dar există un bug de timezone (Finding #5a) care poate face timeoutul să nu se declanșeze corect pe Windows VPS. Mai grav: există condiții în cod unde setup-urile cu `status='WAITING_PULLBACK'` **nu sunt niciodată expirate** dacă nu sunt procesate activ.

**Dovezi din screenshot:**
- GBPJPY LONG: creat `2026-04-18` → activ pe `2026-05-03` = **15 zile**
- USDCAD LONG: creat `2026-04-27` → activ pe `2026-05-03` = **6 zile**
- XTIUSD LONG: creat `2026-04-27` → activ pe `2026-05-03` = **6 zile**
- USDJPY SHORT: creat `2026-05-01` → OK (3 zile)

**Problema concretă GBPJPY:**
- FVG Zone: 200.02 – 203.85
- Preț curent: 212.94
- Distanță: 90,955 pips până la FVG
- Setup REVERSAL bazat pe CHoCH din **18 Aprilie** — structura pieței s-a schimbat complet de atunci
- Dacă prețul ar face o corecție bruscă la 202 (impuls de news), botul ar putea executa pe un setup din acum 2 săptămâni

### Fix necesar:

1. **Auto-invalidare după 7 zile:** Orice setup cu vârsta > 7 zile → `status = 'EXPIRED'` indiferent de alte condiții
2. **Auto-invalidare după distanță FVG > 500 pips:** Dacă prețul e la > 500 pips de FVG, setup-ul nu mai are relevanță structurală
3. **Re-validare CHoCH la fiecare ciclu:** Verifică că CHoCH-ul original nu a fost „consumat" (prețul a trecut prin el și l-a inversat)

---

## 📊 RISK SUMMARY {#risk-summary}

| # | Finding | Fișier | Linii | Severitate | Impact Direct |
|---|---------|--------|-------|-----------|---------------|
| 1 | Continuation bypass fără CHoCH 4H | `setup_executor_monitor.py` | 952–988 | 🔴 CRITIC | Intrare fără confirmare structurală 4H |
| 2 | BOS = CHoCH în Step 1 entry logic | `setup_executor_monitor.py` | 1060–1085 | 🔴 CRITIC | BOS de continuare declanșează execuție |
| 3 | CHoCH `confirmed=True` by default | `smc_detector.py` | 1163, 1240 | 🟠 RIDICAT | False CHoCH din impuls fără confirmare |
| 4 | Fallback 4H FVG → Daily FVG | `setup_executor_monitor.py` | 1000–1018 | 🟠 RIDICAT | Zone entry de 200-300 pips, nicio precizie |
| 5a | `datetime.now()` fără UTC pe Windows | `setup_executor_monitor.py` | 250, 270, 295 | 🟡 MEDIU | Timeout ±5h eronat |
| 5b | W1 depth | — | — | ✅ OK | Nicio problemă |
| 5c | Cache per-instanță + silent errors | `smc_detector.py` | 5378 | 🟡 MEDIU | Analiza 4H poate eșua silențios |
| 6 | RR nu e revalidat la execuție | `setup_executor_monitor.py` | ~1760 | 🔴 CRITIC | Trade cu RR 1:1.62 se execută pe LIVE |
| 7 | SL 385 pips trece filtrul de 100 | `smc_detector.py` / `setup_executor_monitor.py` | ~2407 / ~790 | 🔴 CRITIC | SL structural uriaș fără blocare la execuție |
| 8 | `pip_value=$10` fix pe cross pairs | `unified_risk_manager.py` | 617–628 | 🟠 RIDICAT | Lot size greșit pe GBPNZD, GBPCAD, USDCHF, EURJPY |
| 9 | V13.2 GENERALUL: SL din maximul absolut | `smc_detector.py` | 2491–2510 | 🔴 CRITIC | SL 385 pips în loc de 40 pips (GBPNZD real) |
| 10 | `'continuation'`≠`'continuity'` typo | `audit_monitoring_setups.py` | 287–288 | 🔴 CRITIC | **TOATE** setup-urile continuation apar ca REVERSAL |
| 11 | Setup-uri stale > 7 zile rămân active | `setup_executor_monitor.py` | ~1700 | 🟠 RIDICAT | GBPJPY activ 15 zile, FVG la 90,955 pips distanță |

---

## ⛓️ LANȚURILE DE EXECUȚIE PERICULOASE {#lanturile-de-executie}

### Lanț A — "Continuation cu preț în aer" (Finding #1 + #4)

```
monitoring_setups.json: strategy_type='continuation'
    ↓
V10.9 BYPASS: h4_locked=True fără CHoCH (prețul la max 20 pips de FVG)
    ↓
4H sync FVG absent → fallback la Daily FVG (200-300 pips larg)
    ↓
Step 1: BOS 1H în Daily FVG detectat (Finding #2)
    ↓
Fibonacci 50% calculat din micro-swing 1H
    ↓
EXECUȚIE la Fibo 50% — prețul niciodată n-a atins POI-ul real
```

### Lanț B — "False CHoCH din impuls rapid" (Finding #3 + #2)

```
Piața face impuls puternic pe 1H (news, breakout)
    ↓
detect_choch_and_bos: body sparge swing → confirmed=True (fără swings post-break)
    ↓
all_breaks conține acest CHoCH/BOS → matching_break găsit în FVG
    ↓
Fibonacci calculat → Fibo 50% = mijlocul impulsului
    ↓
EXECUȚIE în mijlocul unui impuls, contra-trend real
```

### Lanț C — "READY status: execuție directă la preț greșit"

```
multi_tf_radar.py marchează setup ca status='READY' cu entry_price=X
    ↓
Prețul pieței s-a mișcat între timp (ex. 50 pips)
    ↓
_process_monitoring_setups: status=='READY' → execuție directă la setup['entry_price']=X
    ↓
Re-validare 4H: max_age_candles=48 (8 zile!) → CHoCH vechi de 7 zile e considerat valid
    ↓
EXECUȚIE la preț depășit, fără verificare că prețul actual e în POI
```

### Lanț D — "RR prost + SL mare + pip value greșit" (Finding #6 + #7 + #8) ← NOU

```
Setup creat cu SL structural 385 pips (Finding #7 — filtrul de 100 pips ocolit)
    ↓
RR calculat la scanner: 1:1.62 — sub filtrul de 1:4
    ↓
Setup ajunge în monitoring_setups.json (filtrul RR nu blochează salvarea)
    ↓
La execuție: RR nu e revalidat (Finding #6) → trade SE EXECUTĂ
    ↓
Lot size calculat cu pip_value=$10 în loc de $5.90 pentru GBPNZD (Finding #8)
    ↓
Risc real: 2.89% din cont în loc de 5% — dar SL de 385 pips rămâne
    ↓
Rezultat: trade cu R:R 1:1.62 pe LIVE, confirmat în screenshot (GBPNZD 01/05/2026)
```

### Lanț E — "GENERALUL + Filtrul 100 pips ocolit" (Finding #9 + #7)

```
CHoCH bearish pe 4H detectat la bara 67 (entry ~2.30111)
    ↓
V13.2 GENERALUL: highs_before_choch = toate swing-urile de la bara 0 la 67
    ↓
max() → swing de la bara 12 (Ianuarie 2026) = 2.33966 → SL = 2.33970 (385 pips)
    ↓
Filtrul de 100 pips din calculate_entry_sl_tp() → ar trebui să respingă (385 > 100)
    ↓
Dar setup-ul vine prin multi_tf_radar.py / re-evaluare → filtrul NU se aplică
    ↓
SL de 385 pips ajunge în monitoring_setups.json nevalidat
    ↓
La execuție: _execute_entry() nu validează SL pips → TRADE EXECUTAT cu SL de 385 pips
```

### Lanț F — "Continuation apare ca Reversal → logică incorectă" (Finding #10 + #1)

```
smc_detector.py: setup continuation salvat cu strategy_type='continuation' în JSON
    ↓
audit_monitoring_setups.py: 'CONTINUATION' not in ['REVERSAL', 'CONTINUITY'] → forțat la REVERSAL
    ↓
User vede REVERSAL în radar → nu știe că bypass-ul V10.9 s-ar activa dacă era continuation
    ↓
setup_executor_monitor.py: citește 'continuation' din JSON corect → activează bypass CHoCH 4H
    ↓
Bypass + FVG fallback (Finding #1 + #4) → execuție fără confirmare structurală
    ↓
User nu a știut că setup-ul era continuation (a văzut REVERSAL în radar)
```

### Lanț G — "Daily setup corect, 4H nu s-a aliniat, bot execută oricum" (Finding #2 + #12)

```
Daily: CHoCH bearish ✅ + FVG marcat ✅ → setup REVERSAL SELL generat
    ↓
Pullback: prețul intră în Daily FVG (corect ✅)
    ↓
4H realitate: HH → HL → HH → HL (4H încă BULLISH, NU s-a format CHoCH bearish pe 4H)
    ↓
Finding #12: daily_chochs[-1] = micro-CHoCH bullish recent (pullback minor) → setup marcat BULLISH REVERSAL
    ↓
Finding #2: all_breaks = chochs + bos_list → BOS bullish 1H detectat în FVG = "confirmare"
    ↓
EXECUȚIE SELL — 4H NU s-a aliniat cu Daily, prețul continuă bullish → trade în pierdere imediată

LOGICA CORECTĂ AR FI:
Daily bearish FVG → așteptare CHoCH bearish pe 4H (LH+LL pe 4H + break swing low)
→ ABIA ATUNCI = aliniere confirmată → EXECUȚIE
```

---

## 🛠️ FIX-URI PROPUSE (prioritizate)

### Fix #1 — CRITIC: Continuation bypass trebuie să ceară BOS 4H real
**Unde:** `setup_executor_monitor.py`, linia ~975  
**Logică:** Înlocuiește proximity check cu verificare că există un BOS 4H recent (ultimele 20 bare) în direcția corectă, confirmat cu body close.

### Fix #2 — CRITIC: Separă CHoCH de BOS în Step 1
**Unde:** `setup_executor_monitor.py`, linia ~1064  
**Logică:** Schimbă `all_breaks = chochs + bos_list` în `all_breaks = chochs`. BOS-urile nu trebuie să declanșeze execuție.

### Fix #3 — RIDICAT: CHoCH confirmed=False by default
**Unde:** `smc_detector.py`, liniile 1163 și 1240  
**Logică:** Schimbă `confirmed = True` în `confirmed = False`. Adaugă ramură `else: confirmed = False` după blocul de validare post-break.

### Fix #4 — RIDICAT: Blochează execuția dacă nu există 4H sync FVG
**Unde:** `setup_executor_monitor.py`, linia ~1015  
**Logică:** Dacă `detect_fvg()` returnează `None` (nu există 4H sync FVG), returnează `KEEP_MONITORING` în loc de fallback la Daily FVG.

### Fix #5 — MEDIU: Forțează UTC consistent
**Unde:** `setup_executor_monitor.py`, toate apelurile `datetime.now()`  
**Logică:** Înlocuiește `datetime.now()` cu `datetime.now(timezone.utc)` în tot fișierul.

### Fix #6 — CRITIC: Revalidare RR minimă la execuție
**Unde:** `setup_executor_monitor.py`, linia ~1755 (înainte de `_execute_entry`)  
**Logică:** Adaugă verificare `rr = abs(tp - entry) / abs(entry - sl)`. Dacă `rr < 1.5` → BLOCAT la execuție, setează status `EXPIRED`.

### Fix #7 — CRITIC: Validare max SL pips la execuție
**Unde:** `setup_executor_monitor.py`, funcția `_execute_entry()` sau imediat înainte  
**Logică:** Dacă `abs(entry - stop_loss) / pip_size > 150` (forex) sau `> 300` (JPY) → BLOCAT. Evită execuții cu SL structural uriaș care au ocolit filtrul din scanner.

### Fix #8 — RIDICAT: Pip value dinamic pentru cross pairs
**Unde:** `unified_risk_manager.py`, liniile 617–628  
**Logică:** Înlocuiește `pip_value = 10.0` fix cu dict de rate quote→USD. Actualizat la fiecare restart din prețurile cBot sau hardcodat cu rate de referință săptămânale.

### Fix #9 — CRITIC: V13.2 GENERALUL — SL pe ultimul swing valid, nu maximul absolut
**Unde:** `smc_detector.py`, liniile 2491–2510 (SHORT) și ~2387–2420 (LONG)  
**Logică:** Înlocuiește `max(highs_before_choch)` cu `sorted(highs_before_choch, key=lambda s: s.index, reverse=True)[0]` + filtru ATR pentru a elimina micro-fractali. SL = ultimul swing structural valid, nu maximul din 6 luni.

### Fix #10 — CRITIC: Normalizare strategy_type în audit_monitoring_setups.py
**Unde:** `audit_monitoring_setups.py`, liniile 286–288  
**Logică:** Extinde whitelist-ul: `['REVERSAL', 'CONTINUATION', 'CONTINUITY']`. Normalizează `'CONTINUITY'` → `'CONTINUATION'` pentru consistență cu valoarea salvată de `smc_detector.py`.

### Fix #11 — RIDICAT: Auto-invalidare setup-uri stale
**Unde:** `setup_executor_monitor.py`, logica de procesare a setup-urilor  
**Logică:** Adaugă la fiecare ciclu:
- Dacă `setup_age > 7 zile` → `status = 'EXPIRED'` automat
- Dacă `distance_to_fvg_pips > 500` → `status = 'EXPIRED'` automat (structura nu mai e relevantă)
- Log clar: `"⌛ EXPIRED: GBPJPY stale 15 zile / 90,955 pips de FVG"`

### Fix #12 — CRITIC: CHoCH structural valid = cel care confirmă alinierea Daily + 4H
**Unde:** `smc_detector.py`, funcția `scan_for_setup()`, linia ~3098  
**Logică:**

Pas 1 — Filtrează `daily_chochs[]` și păstrează **doar CHoCH-ul structural major** (cel care a depășit swing-ul dominant anterior), nu ultimul micro-CHoCH din pullback:
```python
# În loc de: latest_choch = daily_chochs[-1]
# Folosește:
structural_chochs = [
    c for c in daily_chochs
    if is_structural_choch(c, df_daily, swing_highs_d1, swing_lows_d1)
]
latest_choch = structural_chochs[-1] if structural_chochs else None
```

Pas 2 — Implementează `is_structural_choch()`: CHoCH este major dacă `break_price` depășește cel mai semnificativ swing din ultimele 20 bare pre-CHoCH (nu orice fractal):
```python
def is_structural_choch(choch, df_daily, swing_highs, swing_lows):
    if choch.direction == 'bullish':
        highs_before = [sh for sh in swing_highs if sh.index < choch.index][-5:]
        if not highs_before: return False
        structural_high = max(sh.price for sh in highs_before)
        return choch.break_price >= structural_high * 0.998
    else:
        lows_before = [sl for sl in swing_lows if sl.index < choch.index][-5:]
        if not lows_before: return False
        structural_low = min(sl.price for sl in lows_before)
        return choch.break_price <= structural_low * 1.002
```

Pas 3 — **Separarea rolurilor timeframe-urilor** în `_check_pullback_entry()`:
```python
# Daily CHoCH = definește BIAS (direcția trade-ului)
# 4H CHoCH   = confirmă ALINIEREA (structura 4H se întoarce cu Daily)
# 1H CHoCH   = declanșează EXECUȚIA (intrare precisă după pullback)

# BLOCAT dacă 4H nu are CHoCH în direcția Daily bias:
if not h4_choch_aligned_with_daily_bias:
    return 'KEEP_MONITORING'  # Așteptăm alinierea 4H
```

---

## FINDING #12 — CHoCH nu se întâmplă "o singură dată": botul acumulează CHoCH-uri și ia ultimul {#finding-12}

**Severitate:** 🔴 CRITIC  
**Fișier:** `smc_detector.py`  
**Funcții:** `detect_choch_and_bos()` + `scan_for_setup()`  
**Linii cheie:** 1195 (`chochs.append`), 1278 (`chochs.append`), 3098 (`latest_choch = daily_chochs[-1]`)

---

### Conceptul SMC corect (ce înțelegi tu):

```
BEARISH TREND:
  LH → LL → LH → LL → LH → LL
  BOS bearish    BOS bearish    BOS bearish
                                     ↓
                              CHoCH BULLISH ← se întâmplă O SINGURĂ DATĂ
                              (primul break al swing-ului High anterior — schimbare de caracter)
                                     ↓
BULLISH TREND NOU:
  HH → HL → HH → HL → HH → HL
  BOS bullish   BOS bullish   BOS bullish
```

**CHoCH = primul și singurul moment în care prețul sparge structura precedentă.**  
**Tot ce urmează în noua direcție = BOS (confirmarea noului trend).**

---

### Ce face codul în realitate:

`detect_choch_and_bos()` menține un `current_trend` și detectează CHoCH/BOS corect **în timpul scanării**. ÎNSĂ returnează o **listă cu TOATE CHoCH-urile din istoricul complet** (100+ bare D1):

```python
# Fiecare dată când trendul se inversează → CHoCH nou adăugat în listă
chochs.append(CHoCH(index=j, direction='bullish', ...))
current_trend = 'bullish'
# ... mai târziu ...
chochs.append(CHoCH(index=j, direction='bearish', ...))
current_trend = 'bearish'
# ... mai târziu ...
chochs.append(CHoCH(index=j, direction='bullish', ...))  # al 3-lea CHoCH
```

Pe 100 bare D1, pot exista **5-10 CHoCH-uri** acumulate. Și `scan_for_setup()` face pur și simplu:

```python
latest_choch = daily_chochs[-1]   # ← ultimul CHoCH din listă, indiferent de importanță
latest_bos   = daily_bos_list[-1]  # ← ultimul BOS din listă
```

---

### Scenariul concret care produce setup-uri greșite:

```
Timeline pe D1 (100 bare):

Bar 20: CHoCH bearish (MAJOR — trend se schimbă la bearish)  ← chochs[0]
Bar 25: BOS bearish
Bar 30: BOS bearish
Bar 35: BOS bearish

Bar 50: CHoCH bullish (MINOR — pullback corectiv)             ← chochs[1]
Bar 55: BOS bullish (continuarea pullback-ului)

Bar 70: CHoCH bearish (MAJOR — structura bearish confirmată)  ← chochs[2]
Bar 75: BOS bearish
Bar 80: BOS bearish

Bar 90: CHoCH bullish (MINOR pullback corectiv 2)             ← chochs[3] = chochs[-1]
                                                                            ↑
                                                              scan_for_setup() ia ACESTA!

Rezultat: latest_choch = CHoCH bullish minor la bar 90
          strategy_type = 'reversal' BULLISH
          
Realitate: trendul dominant e BEARISH, CHoCH-ul de la bar 90 e doar un pullback
```

---

### De ce V13.0 GENERALUL nu rezolvă complet:

V13.0 GENERALUL rulează **doar când `latest_choch is None`** (nu există CHoCH detectat):

```python
# smc_detector.py linia ~3110
if latest_choch is None and latest_bos is not None:
    # V13.0: verificăm dacă "Generalul" a fost doborât cu body close
    ...
```

Dacă `latest_choch` există (chiar dacă e minor/pullback), V13.0 NU se activează. Deci protecția nu se aplică exact în scenariul cel mai periculos.

---

### Protecțiile existente și limitele lor:

| Protecție | Funcționează? | Limitare |
|-----------|--------------|----------|
| `current_trend` state machine | ✅ Corect în scanare | Protejează în timp real, nu ierarhic |
| WHIPSAW (10 candle gap) | ⚠️ Parțial | Blochează CHoCH la 10 bare, dar nu la 20-50 bare |
| V11.9: BOS opus = pullback ignorat | ⚠️ Parțial | Funcționează când BOS > CHoCH index, nu invers |
| V13.0 GENERALUL | ⚠️ Parțial | Rulează DOAR dacă `latest_choch is None` |
| BOS Dominance (3+ consecutive) | ⚠️ Parțial | V11.9 exclude BOS post-CHoCH din numărătoare |

---

### Problema la nivel de arhitectură:

Botul nu face diferența între:

| Tip CHoCH | Definiție | Acțiune corectă |
|-----------|-----------|-----------------|
| **CHoCH Structural MAJOR** | Primul break al trendului dominant | ✅ Setup REVERSAL valid |
| **CHoCH Minor (pullback)** | Break corectiv în noua direcție, NU depășește "Generalul" principal | ❌ Acesta e doar un 4H CHoCH în interiorul trendului D1 |

Un CHoCH minor pe D1 = de fapt un **pullback** al trendului principal. Ar trebui să fie ignorat pentru determinarea `strategy_type` și `direction` — sau tratat ca semnal de entry continuation, NU reversal.

---

### Dovadă din setup-urile active:

Din screenshot-ul 03/05/2026 — **TOATE 12 setup-uri sunt REVERSAL**. Pe piață, în orice moment există atât trend-uri care continuă (BOS → BOS) cât și reversale. Statistic, nu pot fi simultan 12 reversale pe 12 perechi diferite. Motivul: codul ia `chochs[-1]` (ultimul CHoCH din 100 bare), care e aproape întotdeauna un micro-CHoCH recent, nu marele BOS de continuare.

---

### Fix necesar — Ierarhia CHoCH (CHoCH Structural vs CHoCH Minor):

```python
# CORECT: CHoCH valid doar dacă a depășit swing-ul STRUCTURAL MAJOR
# (= swing-ul care a definit maximul/minimul trendului anterior)
# Nu orice break de swing high/low = CHoCH de setup

# Criteriu adițional de validare pentru scan_for_setup():
def is_structural_choch(choch, df_daily, swing_highs, swing_lows):
    """
    CHoCH este structural (MAJOR) dacă break_price depășește 
    cel mai înalt swing high / cel mai jos swing low din
    ultimele 20 bare ÎNAINTE de CHoCH.
    Un CHoCH minor nu depășește swing-ul structural anterior.
    """
    if choch.direction == 'bullish':
        highs_before = [sh for sh in swing_highs if sh.index < choch.index][-5:]
        structural_high = max(sh.price for sh in highs_before) if highs_before else 0
        return choch.break_price >= structural_high * 0.998  # depășit 99.8% din structural high
    else:
        lows_before = [sl for sl in swing_lows if sl.index < choch.index][-5:]
        structural_low = min(sl.price for sl in lows_before) if lows_before else float('inf')
        return choch.break_price <= structural_low * 1.002
```

---

## 📊 RISK SUMMARY {#risk-summary-final}

| # | Finding | Fișier | Linii | Severitate | Impact Direct |
|---|---------|--------|-------|-----------|---------------|
| 1 | Continuation bypass fără CHoCH 4H | `setup_executor_monitor.py` | 952–988 | 🔴 CRITIC | Intrare fără confirmare structurală 4H |
| 2 | BOS = CHoCH în Step 1 entry logic | `setup_executor_monitor.py` | 1060–1085 | 🔴 CRITIC | BOS de continuare declanșează execuție |
| 3 | CHoCH `confirmed=True` by default | `smc_detector.py` | 1163, 1240 | 🟠 RIDICAT | False CHoCH din impuls fără confirmare |
| 4 | Fallback 4H FVG → Daily FVG | `setup_executor_monitor.py` | 1000–1018 | 🟠 RIDICAT | Zone entry de 200-300 pips, nicio precizie |
| 5a | `datetime.now()` fără UTC pe Windows | `setup_executor_monitor.py` | 250, 270, 295 | 🟡 MEDIU | Timeout ±5h eronat |
| 5b | W1 depth | — | — | ✅ OK | Nicio problemă |
| 5c | Cache per-instanță + silent errors | `smc_detector.py` | 5378 | 🟡 MEDIU | Analiza 4H poate eșua silențios |
| 6 | RR nu e revalidat la execuție | `setup_executor_monitor.py` | ~1760 | 🔴 CRITIC | Trade cu RR 1:1.62 se execută pe LIVE |
| 7 | SL 385 pips trece filtrul de 100 | `smc_detector.py` / `setup_executor_monitor.py` | ~2407 / ~790 | 🔴 CRITIC | SL structural uriaș fără blocare la execuție |
| 8 | `pip_value=$10` fix pe cross pairs | `unified_risk_manager.py` | 617–628 | 🟠 RIDICAT | Lot size greșit pe GBPNZD, GBPCAD, USDCHF, EURJPY |
| 9 | V13.2 GENERALUL: SL din maximul absolut | `smc_detector.py` | 2491–2510 | 🔴 CRITIC | SL 385 pips în loc de 40 pips (GBPNZD real) |
| 10 | `'continuation'`≠`'continuity'` typo | `audit_monitoring_setups.py` | 287–288 | 🔴 CRITIC | **TOATE** setup-urile continuation apar ca REVERSAL |
| 11 | Setup-uri stale > 7 zile rămân active | `setup_executor_monitor.py` | ~1700 | 🟠 RIDICAT | GBPJPY activ 15 zile, FVG la 90,955 pips distanță |
| 12 | `chochs[-1]` = ultimul CHoCH minor, nu major | `smc_detector.py` | 3098 | 🔴 CRITIC | Setup REVERSAL din pullback minor, nu din CHoCH structural |

---

*Raport generat pe baza analizei statice a codului. Nicio modificare nu a fost efectuată.*  
*Versiune sistem analizat: Glitch in Matrix V11.2 Eagle Eye*  
*Ultima actualizare: 4 Mai 2026 — **AUDIT COMPLET: 12 findings, 12 fix-uri, 7 lanțuri de execuție periculoase***  

---

## 📌 REZUMAT EXECUTIV — pentru implementare

**Fișiere de modificat:**

| Fișier | Finding-uri | Prioritate |
|--------|-------------|------------|
| `smc_detector.py` | #3, #7(parțial), #9, #12 | 🔴 CRITIC |
| `setup_executor_monitor.py` | #1, #2, #4, #5a, #6, #7, #11 | 🔴 CRITIC |
| `unified_risk_manager.py` | #8 | 🟠 RIDICAT |
| `audit_monitoring_setups.py` | #10 | 🔴 CRITIC |

**Ordinea de implementare recomandată (impact maxim → minim):**
1. 🔴 Fix #9 — SL din ultimul swing, nu maximul absolut (`smc_detector.py`)
2. 🔴 Fix #2 — Separă CHoCH de BOS în execuție (`setup_executor_monitor.py`)
3. 🔴 Fix #12 — CHoCH structural major, nu micro-CHoCH (`smc_detector.py`)
4. 🔴 Fix #6 — Revalidare RR la execuție (`setup_executor_monitor.py`)
5. 🔴 Fix #7 — Max SL pips gate la execuție (`setup_executor_monitor.py`)
6. 🔴 Fix #10 — Typo continuity→continuation (`audit_monitoring_setups.py`)
7. 🟠 Fix #8 — Pip value dinamic cross pairs (`unified_risk_manager.py`)
8. 🟠 Fix #1 — Continuation bypass cu BOS 4H real (`setup_executor_monitor.py`)
9. 🟠 Fix #4 — Blochează fallback la Daily FVG (`setup_executor_monitor.py`)
10. 🟠 Fix #3 — CHoCH confirmed=False default (`smc_detector.py`)
11. 🟠 Fix #11 — Auto-expire setup-uri stale (`setup_executor_monitor.py`)
12. 🟡 Fix #5a — UTC consistent pe Windows (`setup_executor_monitor.py`)
