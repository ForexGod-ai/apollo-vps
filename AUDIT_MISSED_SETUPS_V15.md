# 🔬 AUDIT COMPLET — DE CE SE RATEAZĂ SETUP-URILE VALIDE
**Glitch in Matrix — Raport Tehnic Senior Quant / SMC Expert**  
**Data:** 14 Mai 2026 | **Versiune analizată:** V15.5 | **Fișiere:** `smc_detector.py`, `multi_tf_radar.py`, `setup_executor_monitor.py`

---

## 📋 REZUMAT EXECUTIV

Sistemul are **5 blocaje arhitecturale majore** și **3 blocaje de logică** care explică de ce setup-uri valide (ex: USDCAD LONG, alte perechi cu CHoCH clar pe 4H) nu se execută. Problemele nu sunt izolate — ele se compun în cascadă: dacă primul filtru eșuează, restul nici nu rulează.

---

## 🔍 1. AUDITUL ZONEI FVG (Fair Value Gap)

### 1.1 Mărimea minimă a FVG — Filtru activ

**Locație:** `smc_detector.py`, liniile 934 și 961 (body method) / liniile 975 și 988 (wick method fallback)

```python
# Body FVG — min gap size:
if gap_size > 0 and (gap_size / gap_bottom) >= 0.0005:  # Min 0.05% din preț
    # → EURUSD la 1.0800 → min FVG = 0.54 pips ← PRACTIC ZERO
    # → USDCAD la 1.3800 → min FVG = 0.69 pips ← LA FEL, APROAPE ZERO
    
# Wick FVG fallback — și mai permisiv:
if gap_size > 0 and (gap_size / gap_bottom) >= 0.0003:  # Min 0.03%
```

**Concluzie:** Filtrul de mărime minimă NU este problema. Orice FVG de 1+ pip trece. Dacă botul nu găsește FVG, nu e din cauza mărimii.

---

### 1.2 Selecția FVG — BUG CRITIC DE LOGICĂ 🔴

**Locație:** `smc_detector.py`, liniile 1060–1063

```python
# CODUL ACTUAL — Cel mai apropiat de prețul curent:
all_fvgs.sort(key=lambda fvg: abs(fvg.middle - current_price))
return all_fvgs[0]  # Closest FVG to current price
```

**Problema:** Sistemul selectează FVG-ul **cel mai aproape de prețul CURENT**, NU primul FVG format după CHoCH. Aceasta înseamnă:

- Scenariul real: CHoCH pe 4H la bara 60/100 → FVG format la bara 62 (impuls proaspăt) → prețul se află la bara 95 (departe de FVG)
- Ce face botul: Găsește un FVG mai vechi (din bara 20/100) care e mai aproape de prețul actual → returnează FVG GREȘIT
- **Consecință:** Chiar dacă FVG-ul relevant există, botul îl ignoră în favoarea unui FVG mai aproape de preț, dar irelevant pentru setup-ul actual

**Impactul direct:** Fibo Fallback (V15.4) nu se activează niciodată corect, pentru că `detect_fvg()` returnează ceva (un FVG vechi/greșit) în loc de `None`.

---

### 1.3 Mitigarea FVG — Logica e corectă, dar cu o problemă subtilă

**Locație:** `smc_detector.py`, liniile 1023–1049

```python
fvg_size = fvg.top - fvg.bottom
mitigation_buffer = fvg_size * 0.20  # 20% din dimensiunea FVG

# BULLISH FVG → filled DACĂ body_low < fvg.bottom - mitigation_buffer
# BEARISH FVG → filled DACĂ body_high > fvg.top + mitigation_buffer
```

**Analiza:** Logica 20% buffer e rezonabilă — un wick la marginea FVG NU invalidează zona. Dar există o problemă mascată:

- Scanarea pentru mitigation se face prin **toate barele DUPĂ formarea FVG** (`range(fvg.index + 1, len(df))`)
- Cu 100 de bare descărcate, dacă FVG-ul s-a format la bara 5 și s-a atins de 3 ori fără a fi consumat, scanarea durează O(n) pentru fiecare FVG candidat
- **Mai important:** Dacă FVG-ul este marcat incorect ca `filled` din cauza unui spike de spread sau wick anormal, este eliminat complet

---

### 1.4 Localizarea POI — Nu există logică Premium/Discount pentru selecția FVG

**Problema:** `detect_fvg()` nu verifică dacă FVG-ul se află în zona Discount (pentru LONG) sau Premium (pentru SHORT) a impulsului CHoCH. Selectează **cel mai aproape de preț**, indiferent de poziție în structură.

**Consecință directă:** Un FVG din zona 70-80% a impulsului (overextended) este preferat față de un FVG din zona 40-60% (optimal POI).

---

## 🛰️ 2. AUDITUL MULTI-TF RADAR — Sincronizare și Praguri

### 2.1 Daily Zone — HARD GATE care blochează totul 🔴

**Locație:** `multi_tf_radar.py`, liniile 459–495

```python
daily_zone_validated = daily_fvg_bottom <= current_price <= daily_fvg_top

if not daily_zone_validated:
    # ← RETURNEAZA IMEDIAT. Nu se analizează NIMIC pe 1H sau 4H.
    # Status: WAITING_DAILY_FVG
    return MultiTFResult(... execution_ready=False ...)
```

**Problema:** Prețul trebuie să fie **EXACT** în interiorul Daily FVG (`fvg_bottom ≤ price ≤ fvg_top`). Nu există buffer de proximitate.

**Scenariul real (USDCAD tip):**
- Daily FVG: 1.3800 – 1.3850 (setup din scanner)
- Prețul actual: 1.3851 (1 pip deasupra FVG)
- Sistemul: `daily_zone_validated = False` → **anulează tot scanul 1H + 4H**
- Pe chart: prețul vizibil e în zonă, dar 1 pip afară → RATAT

**Nu există toleranță de proximitate pentru Daily FVG.** Chiar dacă prețul a atins marginea zonei și a ricoșat (pattern valid SMC), botul nu intră niciodată în scanul LTF.

---

### 2.2 Bara disponibilă pentru CHoCH + Fractal Window 10 — BUG STRUCTURAL 🔴

**Locație:** `multi_tf_radar.py`, linia 212; `smc_detector.py`, liniile 1297–1340

```python
# multi_tf_radar.py — Date descărcate:
df = self.get_historical_data(symbol, timeframe, 100)  # EXACT 100 bare

# smc_detector.py — Fractal Window:
FRACTAL_WINDOW = 10  # 10 bare stânga + 10 bare dreapta obligatoriu
```

**Analiza matematică a problemei:**

```
100 bare totale
- 10 bare la STÂNGA pentru swing detection (fractal window)
- 10 bare la DREAPTA pentru swing detection (fractal window)
= 80 bare UTILE pentru detectarea swing-urilor

CHoCH detection: caută break-uri CU 20 de bare ÎNAINTE de fiecare swing
→ Dacă swing-ul este la bara 85, break-ul e căutat la bara 85-105 (OUTSIDE range)
→ Dacă CHoCH s-a format la bara 78-95, NU are 10 bare confirmate la dreapta
   → detect_swing_highs() NU îl include în lista de swinguri
   → detect_choch_and_bos() NU găsește CHoCH
```

**Consecință:**

| Timeframe | 100 bare = | CHoCH recent (< 10 bare) |
|-----------|-----------|--------------------------|
| 1H | 4.2 zile | CHoCH din ultimele 10 ore → INVIZIBIL |
| 4H | 16.7 zile | CHoCH din ultimele 40 ore → INVIZIBIL |

**Aceasta este probabil cauza principală pentru care USDCAD 4H CHoCH clar vizibil pe chart nu era detectat de bot.** Dacă CHoCH s-a format cu mai puțin de 10 bare în urmă, Fractal Window 10 îl elimină din lista de swinguri.

---

### 2.3 ATR Multiplier și relevanta sa actuală

**Locație:** `multi_tf_radar.py`, liniile 136–144

```python
self.smc_1h = SMCDetector(swing_lookback=5, atr_multiplier=0.8)  # 1H
self.smc_4h = SMCDetector(swing_lookback=5, atr_multiplier=1.0)  # 4H (V15.4)
```

**Analiza:** Parametrul `atr_multiplier` este setat, dar din `smc_detector.py` linia 1306:

```python
# V11.2: prominence 0.0 — Fractal Window 10 e filtrul principal, nu ATR
prominence_threshold = 0.0
```

**ATR multiplier NU mai filtrează swing-urile** — valoarea sa este irelevantă. Filtrul real este exclusiv **Fractal Window 10**. Scăderea la 1.0 (V15.4) nu a avut niciun efect real pe detecția swing-urilor, deși a ajutat indirect la alte calcule.

---

### 2.4 Timeframe Alignment — Cerința STRICTĂ de direcție

**Locație:** `multi_tf_radar.py`, liniile 267–282

```python
if choch_direction != required_direction:
    # Signal REJECTED - Not aligned with Daily bias
    return TimeframeAnalysis(
        choch_detected=False,  # ← marcat ca nedetectat, nu ca misaliniat
        ...
    )
```

**Problema:** Dacă pe 1H apare un CHoCH în direcție opusă (pullback pattern normal în SMC), botul:
1. Marchează `choch_detected=False` (incorect — CHoCH există, dar e contra-trend)
2. Nu salvează informația că există structură alternativă
3. La verificarea din `setup_executor_monitor.py`: `use_radar_data = False` → fallback la `_check_pullback_entry()`

**Scenariul:** Daily SELL → 4H CHoCH BEARISH (aliniat ✅) → 1H CHoCH BULLISH (retragere în structura bearish — normal SMC!)  
Bot-ul corect respinge 1H bullish, dar nu ar trebui să blocheze execuția pe 4H.

---

### 2.5 Logica FVG Proximity — Nu există toleranță de entry

**Locație:** `multi_tf_radar.py`, liniile 367–395

```python
in_fvg = fvg_bottom <= current_price <= fvg_top  # ← EXACT, fără buffer

if in_fvg:
    distance_to_fvg_pips = 0.0
    status = EXECUTE_NOW
else:
    status = WAITING_PULLBACK  # ← orice 1 pip afară = waiting
```

**Problema:** Dacă prețul atinge FVG-ul (`in_fvg=True`) și în **ciclul următor de 30 secunde** prețul a ieșit cu 0.5 pips, botul întoarce la `WAITING_PULLBACK`. Nu există **persistență de stare** — o singură atingere a FVG care nu coincide cu intervalul de 30s al radarului este complet ignorată.

**Aceasta explică:** "Prețul a ajuns la 1 pip de FVG și a plecat — botul a ratat intrarea."

---

## 🛠️ 3. ANALIZA SETUP-URILOR RATATE

### 3.1 Blocajul principal: `_check_pullback_entry()` cu Fix #4 — NO DAILY FALLBACK

**Locație:** `setup_executor_monitor.py`, liniile 905–920

```python
h4_sync_top = setup.get('h4_sync_fvg_top', 0)
h4_sync_bottom = setup.get('h4_sync_fvg_bottom', 0)

if h4_sync_top > 0 and h4_sync_bottom > 0:
    fvg_top = h4_sync_top
    fvg_bottom = h4_sync_bottom
else:
    # Fix #4: Daily FVG BLOCAT CA ZONĂ DE EXECUȚIE
    return {'action': 'KEEP_MONITORING', 'reason': 'Fix#4: Daily FVG = alertă only. Așteptăm 4H CHoCH + 4H sync FVG'}
```

**Fluxul complet al unui setup ratat:**

```
Setup activ: USDCAD LONG
  ↓
multi_tf_radar detectează: 4H CHoCH BEARISH → REJECTED (wrong direction: need bullish)
  ↓
setup_executor_monitor: use_radar_data = False (radar_4h_choch_detected=False)
  ↓ (după V15.5 fix — dar problema e în radar, nu în executor)
_check_pullback_entry() apelat
  ↓
h4_sync_fvg_top = 0 (nu a fost niciodată setat, radar nu a confirmat)
  ↓
Fix #4: return KEEP_MONITORING ← BLOCAT DEFINITIV
```

**Radarul nu detectează 4H CHoCH aliniat → h4_sync_fvg_top rămâne 0 → Fix #4 blochează execuția.**

---

### 3.2 Diagrama completă a blocajelor în cascadă

```
USDCAD LONG Setup — Drum spre execuție (actual vs. așteptat)

[1] DAILY ZONE CHECK (multi_tf_radar.py:459)
    → Price în Daily FVG? SE/NU
    ⚠️ BUG: 0 pip toleranță — 1 pip afară = blocat complet

[2] 4H CHoCH DETECTION (smc_detector.py detect_choch_and_bos)
    → Fractal Window 10 pe 100 bare
    🔴 BUG: CHoCH format în ultimele 10 bare (40h) = INVIZIBIL
    🔴 BUG: break_end = swing.index + 20 → break-uri > 20 bare = RATATE

[3] 4H FVG DETECTION (smc_detector.py detect_fvg)  
    → Selectează cel mai aproape de preț curent
    🔴 BUG: Poate selecta FVG vechi/greșit în loc de FVG CHoCH
    → Nu există fallback corect dacă FVG greșit e returnat

[4] DIRECTION ALIGNMENT (multi_tf_radar.py:267)
    → CHoCH direction == required_direction?
    ⚠️ Corect conceptual, dar suprastrict pentru 1H counter-swing

[5] in_fvg CHECK (multi_tf_radar.py:367)
    → price IN FVG la momentul exact al scanului de 30s
    🔴 BUG: Nicio persistență — atingere ratată între scanuri = RESET

[6] EXECUTOR ROUTING (setup_executor_monitor.py:1771 — V15.5 fixed)
    → use_radar_data = radar_1h_ok OR radar_4h_ok
    ✅ FIXED în V15.5

[7] _check_radar_entry PREMIUM/DISCOUNT (setup_executor_monitor.py:760)
    → fvg_entry < choch_price (BUY) / fvg_entry > choch_price (SELL)
    ⚠️ FVG format la CHoCH nivel → fvg_entry ≈ choch_price → REJECTED ca "not in discount"

[8] _check_pullback_entry FIX#4 (setup_executor_monitor.py:905)
    → h4_sync_fvg_top > 0?
    🔴 BUG: Niciodată setat dacă radarul n-a confirmat → BLOCAT PERMANENT
```

---

### 3.3 Timeout 12H — Aplicabil DOAR în Path B (Pullback Fibo)

**Locație:** `setup_executor_monitor.py`, liniile 1395–1405

```python
if hours_elapsed >= 12:
    return {'action': 'EXPIRE_SETUP', 'reason': 'Timeout 12H fără pullback'}
```

Timeoutful de 12H există și funcționează DOAR dacă:
1. `_check_pullback_entry()` este apelat (nu `_check_radar_entry()`)
2. Un CHoCH 1H a fost detectat și înregistrat cu timestamp
3. S-au scurs 12 ore fără pullback la Fibo 50%

**Nu există timeout pentru:** setup-uri blocate la Fix#4 (h4_sync_fvg absent) sau la Daily FVG gate. Acele setup-uri rămân **BLOCATE PE TERMEN NEDEFINIT** în `KEEP_MONITORING`.

---

## 📊 4. TABEL CENTRALIZAT — BLOCAJE GĂSITE

| # | Locație | Tip | Severitate | Descriere |
|---|---------|-----|-----------|-----------|
| B1 | `multi_tf_radar.py:459` | HARD GATE | 🔴 CRITIC | Daily FVG: 0 toleranță → 1 pip afară = niciun scan LTF |
| B2 | `smc_detector.py:1297` | STRUCTURAL | 🔴 CRITIC | Fractal Window 10 pe 100 bare → CHoCH < 10 bare vechi = INVIZIBIL |
| B3 | `smc_detector.py:1063` | LOGICĂ | 🔴 CRITIC | FVG selectat după proximitate preț, nu după CHoCH relevance |
| B4 | `multi_tf_radar.py:367` | TIMING | 🟡 MAJOR | in_fvg fără persistență → atingere între scanuri = PIERDUTĂ |
| B5 | `setup_executor_monitor.py:905` | ARHITECTURAL | 🟡 MAJOR | Fix#4 blochează execuția fără h4_sync_fvg setat de radar |
| B6 | `smc_detector.py:1085` | LOGICĂ | 🟡 MAJOR | Break search limitat la 20 bare după swing → CHoCH la distanță > 20 bare = RATAT |
| B7 | `setup_executor_monitor.py:760` | LOGICĂ | 🟠 MODERAT | Premium/Discount check prea strict → FVG la nivelul CHoCH = REJECTED |
| B8 | `multi_tf_radar.py:212` | DATE | 🟠 MODERAT | Doar 100 bare per TF → context insuficient pentru structura 4H |
| B9 | `smc_detector.py:1306` | DOCUMENTAR | 🟢 MINOR | ATR multiplier documentat ca activ, dar efectiv = 0 (Fractal Window e filtrul real) |

---

## 💡 5. PROPUNERI DE OPTIMIZARE (pentru iterația viitoare)

> ⚠️ Aceasta este **EXCLUSIV o analiză** — nu se implementează nimic în acest document.
> Propunerile vor fi evaluate și implementate separat, cu validare pe backtest.

---

### P1 — Daily FVG: Adăugare buffer de proximitate (B1)

```python
# ACTUAL:
daily_zone_validated = daily_fvg_bottom <= current_price <= daily_fvg_top

# PROPUS:
daily_pip_size = 0.01 if 'JPY' in symbol else 0.0001
proximity_buffer = daily_pip_size * 5  # 5 pips toleranță
daily_zone_validated = (daily_fvg_bottom - proximity_buffer) <= current_price <= (daily_fvg_top + proximity_buffer)
```

**Impact:** Permite scanul LTF când prețul e la marginea Daily FVG (±5 pips), nu doar exact în interior.

---

### P2 — Fractal Window adaptiv sau mai multe bare (B2)

```python
# OPȚIUNEA A — Mai multe bare descărcate:
df = self.get_historical_data(symbol, timeframe, 200)  # 200 în loc de 100
# 1H: 8.3 zile → CHoCH < 10 bare (10h) e acoperit și are context

# OPȚIUNEA B — Fractal Window 7 în loc de 10:
FRACTAL_WINDOW = 7  # 7 bare stânga + 7 dreapta
# Reduce "orbirea" pentru CHoCH recent: 10h → 7h pe 1H, 40h → 28h pe 4H

# OPȚIUNEA C (preferată) — Combinat: 200 bare + Fractal Window 10 păstrat
# → Nu schimbi algoritmul de detecție swing, doar dai mai mult context
```

**Risc:** Mai multe bare = mai mult timp de procesare la fiecare scan de 30s. Neesențial pe VPS dedicat.

---

### P3 — FVG Selection: Prioritizează FVG-ul format imediat după CHoCH (B3)

```python
# ACTUAL: closest to current price
all_fvgs.sort(key=lambda fvg: abs(fvg.middle - current_price))
return all_fvgs[0]

# PROPUS: FVG format cel mai aproape temporal de CHoCH (prima apariție după CHoCH)
# Filtrăm la FVG-uri în zona de 40-70% din impulsul CHoCH, sortăm după index
choch_idx = choch.index
post_choch_fvgs = [f for f in all_fvgs if f.index >= choch_idx]
if post_choch_fvgs:
    post_choch_fvgs.sort(key=lambda f: f.index)  # primul FVG după CHoCH
    return post_choch_fvgs[0]
else:
    # Fallback la cel mai aproape de preț dacă nu există FVG post-CHoCH
    all_fvgs.sort(key=lambda fvg: abs(fvg.middle - current_price))
    return all_fvgs[0]
```

---

### P4 — in_fvg Persistență: Memoizare stare pe setup (B4)

```python
# Salvăm în monitoring_setups.json momentul când in_fvg a fost True prima dată
# și păstrăm starea activă pentru N minute (ex: 60 minute)

last_in_fvg_time = setup.get('last_in_fvg_time')
if in_fvg:
    setup['last_in_fvg_time'] = datetime.utcnow().isoformat()
    setup['last_in_fvg_status'] = True

# La execuție: dacă in_fvg_now SAU (last_in_fvg < 60 min)
in_fvg_persisted = in_fvg or (
    last_in_fvg_time and 
    (datetime.utcnow() - datetime.fromisoformat(last_in_fvg_time)).seconds < 3600
)
```

**Impact:** Dacă prețul a atins FVG-ul și a ieșit cu < 5 pips, se consideră că atingerea a fost validă timp de 60 minute.

---

### P5 — Break Search: Extinde limita de la 20 la 40 bare (B6)

```python
# ACTUAL:
break_end = min(swing.index + 20, len(df))  # Look 20 candles ahead

# PROPUS:
break_end = min(swing.index + 40, len(df))  # Look 40 candles ahead
# → Prinde CHoCH-uri care se formează mai lent (trending market)
```

---

### P6 — Premium/Discount check: Buffer toleranță 5 pips (B7)

```python
# ACTUAL:
zone_valid = radar_1h_fvg_entry < radar_1h_choch_price  # STRICT

# PROPUS:
pip_size = 0.01 if 'JPY' in symbol else 0.0001
pd_buffer = pip_size * 5  # 5 pips buffer la verificarea zonei
zone_valid = radar_1h_fvg_entry < (radar_1h_choch_price + pd_buffer)  # BUY
# FVG la nivelul CHoCH sau ușor deasupra (5 pip toleranță) = valid pentru LONG
```

---

### P7 — h4_sync_fvg Fallback: Acceptă Daily FVG ca ultimă opțiune (B5)

```python
# ACTUAL:
# Fix #4: Daily FVG BLOCAT. Fără h4_sync_fvg → KEEP_MONITORING permanent

# PROPUS:
# Dacă CHoCH 4H confirmat (h4_locked=True) dar h4_sync_fvg absent:
# → Folosim zona Daily FVG ca entry zone (mai largă, dar validă)
# → Marcat explicit ca "DAILY_FVG_FALLBACK" pentru statistici
if h4_locked and (h4_sync_top == 0):
    fvg_top = setup.get('fvg_top', 0)
    fvg_bottom = setup.get('fvg_bottom', 0)
    logger.info(f"   ⚠️ [P7 DAILY FALLBACK] {symbol}: No 4H sync FVG, 4H confirmed → using Daily FVG range")
```

---

## 🔑 6. CONCLUZIE — DE CE NU S-A EXECUTAT USDCAD

**Cauza probabilă în ordinea impactului:**

1. **B2 (FRACTAL WINDOW):** CHoCH-ul 4H bullish s-a format prea recent (< 10 bare × 4H = < 40 ore) → `detect_swing_highs()` cu Fractal Window 10 l-a ignorat din cauza lipsei de confirmare bilaterală. **Radarul nu a găsit niciun CHoCH valid.**

2. **B1 (DAILY GATE):** Chiar dacă prețul era aproape de Daily FVG, eventual cu 1-2 pips în afara zonei stricte → `daily_zone_validated=False` → **zero analiză LTF.**

3. **B3 (FVG SELECTION):** Dacă CHoCH era detectat, `detect_fvg()` returna FVG greșit (cel mai aproape de preț, nu cel din impulsul CHoCH) → Fibo Fallback V15.4 nu se activa (nu `None` returnat, ci FVG incorect).

4. **B5 (FIX#4):** Chiar dacă totul mergea corect până la executor, `h4_sync_fvg_top=0` în `_check_pullback_entry()` → blocaj permanent înainte de orice evaluare.

**Verdict:** Setup-ul era valid pe chart, dar sistemul l-a filtrat prin 4 straturi independente de blocaje, fiecare suficient singur pentru a opri execuția.

---

## 📝 NOTE PENTRU IMPLEMENTARE

- Propunerile **P2 (200 bare)** și **P5 (break_end 40)** au risc minim și impact maxim
- Propunerea **P3 (FVG selection by CHoCH proximity)** este cea mai importantă corectitudine algoritmică
- Propunerea **P4 (in_fvg persistență)** necesită testare pe backtesting pentru a evita false entries pe atingeri false
- **Nu se schimbă Fractal Window 10** — e un filtru bun. Se cresc barele disponibile pentru el.
- Propunerea **P7 (Daily FVG fallback)** se activează DOAR dacă h4_locked=True, nu ca fallback general

---

*Raport generat: 14 Mai 2026 — Glitch in Matrix V15.5*  
*Analiză: Senior Quant / GitHub Copilot*  
*Fișiere auditate: `smc_detector.py` (5458 linii), `multi_tf_radar.py` (931 linii), `setup_executor_monitor.py` (2400 linii)*
