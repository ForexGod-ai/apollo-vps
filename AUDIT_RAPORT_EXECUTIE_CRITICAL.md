# 🔬 AUDIT TEHNIC CRITIC — Raport de Execuție
**Glitch in Matrix V11.2 — Discrepanțe Entry/TP/Direction**  
**Data audit:** 18 Aprilie 2026  
**Auditor:** GitHub Copilot (Claude Sonnet 4.6)  
**Fișiere analizate:** `smc_detector.py`, `daily_scanner.py`  
**Status:** ⛔ **2 BUG-URI CRITICE CONFIRMATE + 1 PROBLEMĂ ARHITECTURALĂ**

---

## 📋 SUMAR EXECUTIV

| # | Caz | Bug | Severitate |
|---|-----|-----|------------|
| 1 | GBPJPY LONG / TP < Entry | Validare TP inversată la ATH + `abs()` mask în RR | 🔴 CRITIC |
| 2 | XTIUSD Entry 60.76 vs FVG 78-84 | Fibonacci calculat pe impulse macro, nu pe FVG | 🔴 CRITIC |
| 3 | Daily FVG ≠ h4_sync_fvg la entry calc | Arhitectură: POI zone pasată la entry calculator în loc de sync FVG | 🟡 MAJOR |

---

## ❌ BUG #1 — GBPJPY: LONG cu TP < Entry (Inversiune Matematică)

### Simptom Raportat
```
Setup: LONG (Bullish Continuity)
Entry:  212.94
TP:     206.90   ← TP < Entry = logică de SELL!
```

### Diagnoză: Traseu în cod

**Fișier:** `smc_detector.py` → funcția `calculate_entry_sl_tp()` (linii ~2340–2370)

#### Pasul 1: Selecție TP normală (LONG path)
```python
# Filtrăm swing-urile D1 DEASUPRA prețului curent
highs_above_price = [sh for sh in swing_highs_d1_list if sh.price > current_price]
if highs_above_price:
    nearest_high = min(highs_above_price, key=lambda sh: sh.price)
    take_profit = df_daily['high'].iloc[nearest_high.index]
```
**Scenariul ATH:** GBPJPY la 212.94 = ALL-TIME HIGH → `highs_above_price = []` → **lista goală**.

#### Pasul 2: Fallback 1 (tot eșuează)
```python
else:
    if swing_highs_d1_list:
        take_profit = df_daily['high'].iloc[swing_highs_d1_list[-1].index]
        # ← ultimul swing High din D1 = sub 212.94 (e ATH!) → TP = 209.x
```
Rezultat: `take_profit ≈ 209.x < 212.94` → intră în validare.

#### Pasul 3: Validare → Fallback 2 (tot eșuează)
```python
# Validare: TP trebuie să fie deasupra entry pentru LONG
if take_profit <= entry:
    body_highs_d1 = df_daily[['open', 'close']].max(axis=1)
    take_profit = body_highs_d1.iloc[:-1].max()
    # ← MAX din toate corpurile D1 istorice, EXCLUSIV ultima bară
    # Dacă GBPJPY e la ATH, TOATE corpurile istorice sunt < 212.94
    # → take_profit = 206.90 (cel mai mare corp anterior, tot < 212.94)
```
**ATENȚIE:** Nu există Fallback 3. Codul continuă cu `take_profit = 206.90` chiar dacă e tot sub entry!

#### Pasul 4: Garda RR nu prinde eroarea ← **POARTA DESCHISĂ**
```python
risk   = abs(entry - stop_loss)      # ex: abs(212.94 - 211.44) = 1.50 = 150 pips JPY
reward = abs(take_profit - entry)    # abs(206.90 - 212.94) = 6.04 → 604 pips JPY
rr     = reward / risk               # 604 / 150 = 4.02 > 4.0 ✅ TRECE!
```

**🔑 ROOT CAUSE:** `reward = abs(take_profit - entry)` folosește `abs()` → măsoară **distanța**, nu **direcția**. Un TP greșit sub entry produce același număr pozitiv ca și unul corect deasupra. RR check trece, setup-ul iese în raport, dar direcția e inversată.

### Schema fluxului de eroare

```
GBPJPY la ATH (212.94)
      │
      ▼
highs_above_price = []  (niciun swing H D1 deasupra)
      │
      ▼
Fallback 1: ultimul swing H D1 = 209.x < 212.94
      │
      ▼
Validare: (209.x <= 212.94) → TRUE → Fallback 2
      │
      ▼
Fallback 2: max(body D1 istorice) = 206.90 (tot ATH context)
      │
⚠️   Nicio a doua validare! TP = 206.90 acceptat.
      │
      ▼
reward = abs(206.90 - 212.94) = 6.04 → RR = 4.02 ✅
      │
      ▼
Setup iese în raport: LONG @ 212.94 TP 206.90 ← GREȘIT!
```

### Fix Recomandat

**Locație:** `smc_detector.py`, după blocul FALLBACK2 al LONG (linia ~2373)

```python
# ÎNAINTE (buggy):
if take_profit <= entry:
    body_highs_d1 = df_daily[['open', 'close']].max(axis=1)
    take_profit = body_highs_d1.iloc[:-1].max()
    print(f"   🎯 [V12.1 TP FALLBACK2] Max body D1: {take_profit:.5f}")
# ← codul continuă direct fără re-validare

# DUPĂ (fix):
if take_profit <= entry:
    body_highs_d1 = df_daily[['open', 'close']].max(axis=1)
    take_profit = body_highs_d1.iloc[:-1].max()
    print(f"   🎯 [V12.1 TP FALLBACK2] Max body D1: {take_profit:.5f}")
    
    # ✅ FIX: A doua validare după fallback2
    if take_profit <= entry:
        print(f"   ⛔ [ATH REJECT] {symbol}: Niciun swing H D1 deasupra entry {entry:.5f}"
              f" — preț la ATH, TP imposibil de calculat structural. Trade ANULAT.")
        return None, None, None
```

**De asemenea**, fix secundar în RR check — adaugă validare direcțională:

```python
# Adaugă înainte de rr = reward / risk:
if fvg.direction == 'bullish' and take_profit <= entry:
    print(f"⛔ [DIRECTION GUARD] {symbol} LONG: TP {take_profit:.5f} <= Entry {entry:.5f}. ANULAT.")
    return None, None, None
if fvg.direction == 'bearish' and take_profit >= entry:
    print(f"⛔ [DIRECTION GUARD] {symbol} SHORT: TP {take_profit:.5f} >= Entry {entry:.5f}. ANULAT.")
    return None, None, None
```

---

## ❌ BUG #2 — XTIUSD: Entry 60.76 vs FVG 78.96–84.85 (Decuplare Completă)

### Simptom Raportat
```
Setup:  BULLISH BOS / FVG
POI:    78.96 – 84.85  (Daily Fair Value Gap)
Entry:  60.76          ← 18$ sub FVG!
```

### Diagnoză: Traseu în cod

**Fișier:** `smc_detector.py` → funcția `calculate_entry_sl_tp()` (linii ~2263–2296)

#### Pasul 1: Calculul Fibonacci pe impulse CHoCH 4H
```python
if h4_choch is not None and hasattr(h4_choch, 'swing_low') and h4_choch.swing_low is not None:
    impulse_low  = h4_choch.swing_low   # ex: 52.88 (min macro swing pe 4H)
    impulse_high = h4_choch.swing_high  # ex: 84.17 (max macro swing = aproape de FVG top)
    impulse_range = impulse_high - impulse_low  # 84.17 - 52.88 = 31.29
    
    fib_70 = impulse_high - (impulse_range * 0.70)  # 84.17 - 21.90 = 62.27
    fib_80 = impulse_high - (impulse_range * 0.80)  # 84.17 - 25.03 = 59.14
    fib_75 = impulse_high - (impulse_range * 0.75)  # 84.17 - 23.47 = 60.70 ≈ 60.76
```
Nivelele Fibonacci 70-80% sunt calculate pe **TOATĂ mișcarea macro** a CHoCH 4H (31 puncte), nu pe mișcarea care a creat FVG-ul.

#### Pasul 2: Verificarea dacă FVG e în Golden Zone
```python
fvg_in_golden_zone = (fvg.bottom <= fib_70 and fvg.top >= fib_80)
# Adică: 78.96 <= 62.27 AND 84.85 >= 59.14
# = FALSE AND TRUE
# = FALSE  ← FVG la 78-84 NU e în Golden Zone 59-62!
```

#### Pasul 3: Fallback la fib_75 ← **DECUPLAREA TOTALĂ**
```python
if fvg_in_golden_zone:
    entry = fvg.bottom  # ← n-ar fi ales oricum (FALSE)
else:
    entry = fib_75      # ← entry = 60.70 ≈ 60.76 !!!
```
**Concluzie:** FVG-ul identificat la 78-84 este **complet ignorat** ca entry. Algoritmul îl foloseste pe FVG doar pentru a verifica suprapunerea (care eșuează), după care calculează entry pe baza unui Fibonacci aplicat pe o mișcare macro mult mai mare.

### Schema fluxului de eroare

```
Daily Scanner detectează:
  FVG Daily (POI): 78.96 – 84.85
  4H CHoCH bullish: swing_low=52.88, swing_high=84.17

      │
      ▼
calculate_entry_sl_tp(symbol, fvg=DailyFVG, h4_choch=CHoCH4H, ...)
      │
      ▼
impulse_range = 84.17 - 52.88 = 31.29 pct
fib_70 = 62.27   fib_75 = 60.70   fib_80 = 59.14
      │
      ▼
fvg_in_golden_zone: (78.96 <= 62.27) = FALSE
      │
      ▼
entry = fib_75 = 60.76   ← ignoră complet FVG la 78-84!
      │
      ▼
Raport: "POI: 78.96–84.85 | Entry: 60.76" ← decuplat!
```

### Cauza Profundă (Arhitecturală)

Există o **confuzie semantică fundamentală** în ce este pasat ca `fvg` în `calculate_entry_sl_tp`:

| Ce ar trebui să fie | Ce este în realitate |
|--------------------|--------------------|
| FVG 4H creat de impulsul CHoCH (entry zone sniper) | Daily FVG / POI zone macro (zona de interes structurală) |

**Proba:** Codul detectează deja `h4_sync_fvg` (linia 3678):
```python
h4_sync_fvg = self.detect_fvg(df_4h, valid_h4_choch, current_price)
h4_sync_fvg.direction = current_trend  # Align with D1 bias
```
Dar când apelează `calculate_entry_sl_tp` (linia 3983):
```python
entry, sl, tp = self.calculate_entry_sl_tp(symbol, fvg, h4_signal, df_4h, df_daily)
#                                                   ^^^
#                                                   Daily FVG (POI), NU h4_sync_fvg!
```
`h4_sync_fvg` este stocat în obiectul `TradeSetup` dar **nu este folosit pentru calculul entry-ului**.

### Fix Recomandat

**Locație:** `smc_detector.py`, linia ~3983 (pasarea FVG la calculate_entry_sl_tp)

```python
# ÎNAINTE (buggy):
entry, sl, tp = self.calculate_entry_sl_tp(symbol, fvg, h4_signal, df_4h, df_daily)

# DUPĂ (fix):
# Prioritate: h4_sync_fvg (entry zone precisă) > fvg (Daily POI macro)
fvg_for_entry = h4_sync_fvg if h4_sync_fvg else fvg
entry, sl, tp = self.calculate_entry_sl_tp(symbol, fvg_for_entry, h4_signal, df_4h, df_daily)
if entry is None:
    return None
```

**De asemenea**, în `calculate_entry_sl_tp`, adaugă o validare finală că entry-ul calculat e în/aproape de FVG pasat:

```python
# La finalul blocului LONG, înainte de RR check:
fvg_midpoint = (fvg.bottom + fvg.top) / 2
max_distance = (fvg.top - fvg.bottom) * 3.0  # max 3x mărimea FVG
if abs(entry - fvg_midpoint) > max_distance:
    print(f"   ⛔ [ENTRY DRIFT] {symbol}: Entry {entry:.5f} prea departe de FVG {fvg.bottom:.5f}–{fvg.top:.5f}. Trade ANULAT.")
    return None, None, None
```

---

## ⚠️ PROBLEMA #3 — Instrucțiuni Contradictorii: Reversal vs Continuity

### Descriere
Strategia are **două tipuri de setup** cu logici diferite:

| | REVERSAL | CONTINUITY |
|--|----------|------------|
| Semnal D1 | CHoCH (schimbare trend) | BOS (continuarea trend-ului) |
| Așteptare | Pullback în FVG Daily | Pullback în FVG Daily |
| Entry | FVG 4H creat post-CHoCH | FVG 4H creat post-BOS |
| POI | Sub-zona structurii ruptă | Zona imbalance din push |

**Problema:** Ambele tipuri converg spre același apel `calculate_entry_sl_tp(symbol, fvg, ...)` cu aceleași formule. **Nu există ramuri separate de calcul pentru REVERSAL vs CONTINUITY.**

### Unde se manifestă
- CONTINUITY pe XTIUSD: BOS detectat la nivel 84+, preț continuă bullish, dar formula Fibonacci (calculată pe swing-ul macro din CHoCH anterior) dă entry la 60 — care era valid pentru REVERSAL dar NU pentru CONTINUITY unde entry trebuie să fie aproape de BOS level sau în FVG recent.
- REVERSAL pe GBPJPY la ATH: nu există swing High structural deasupra → formula nu are anchor valid → colaps în fallback.

### Fix Arhitectural Recomandat

Adaugă ramuri separate în `calculate_entry_sl_tp`:

```python
def calculate_entry_sl_tp(self, symbol, fvg, h4_choch, df_4h, df_daily, 
                           strategy_type='reversal', ...):
    if strategy_type == 'continuation':
        # CONTINUITY: Entry = FVG edge (BOS imbalance zone)
        # Nu calc Fibonacci pe CHoCH macro — entry = direct în FVG
        entry = fvg.bottom if fvg.direction == 'bullish' else fvg.top
    else:
        # REVERSAL: Entry = Fibonacci 70-80% pe impulse CHoCH
        entry = calculate_fib_entry(h4_choch, fvg)
```

---

## 🔩 VALORI HARDCODATE care trebuie dinamizate

| Locație | Valoare hardcodată | Impact | Fix sugerat |
|---|---|---|---|
| `smc_detector.py:3960` | `sl = order_block.bottom * 0.9995` | 5 pips fix pe orice pereche | `order_block.bottom - (atr_4h * 0.5)` |
| `smc_detector.py:3971` | `tp = entry * 1.02 / entry * 0.98` | 2% TP fix (OB fallback) | `entry ± (daily_atr * 2.0)` |
| `calculate_entry_sl_tp:fib_75` | `impulse_range * 0.75` | 75% Fib fix | Adaptabil la structura locală |
| `calculate_entry_sl_tp:sl_buffer` | `pip_size * 1` | 1 pip buffer SL | `pip_size * max(1, atr_ratio * 0.5)` |
| `RR floor` | `rr < 4.0` | Același prag pentru XTI/BTC/JPY | `rr_min = 3.0 if 'XTI' in symbol or 'BTC' in symbol else 4.0` |
| `OB SL multiplier` | `* 0.9995` / `* 1.0005` | 5 pips fix (1 pip pe JPY!) | Calculat pe pip_size dinamic |

### Detaliu critic: OB SL pe JPY
```python
# BUGGY pentru JPY (0.9995 = ~1 JPY pip, nu 5 pips normale):
sl = order_block.bottom * 0.9995  # GBPJPY @ 212.94: sl = 212.83 = 11 pips, ok
sl = order_block.bottom * 0.9995  # EURUSD @ 1.09000: sl = 1.08945 = 5.5 pips, ok
sl = order_block.bottom * 0.9995  # XTIUSD @ 81.50: sl = 81.459 = 0.041$ = ok
# Problema apare pe instrumente cu valori mici (XAGUSD @ 26.5) sau mari (BTCUSD @ 95000)
```

---

## 🗺️ HARTA PORȚILOR LOGICE (IF/THEN) CARE EȘUEAZĂ

```
scan_for_setup(symbol, ...)
    │
    ├─ detect D1 CHoCH/BOS → current_trend, strategy_type
    ├─ detect Daily FVG → fvg (POI zone)
    ├─ fvg.direction = current_trend  [FORȚAT - corect]
    │
    ├─ detect h4_choch (body close)
    ├─ detect h4_sync_fvg  ← detectat DAR NEUTILIZAT la entry ⚠️
    │
    └─ calculate_entry_sl_tp(symbol, fvg=DAILY_FVG, h4_choch, ...)
            │
            ├─ LONG path:
            │    ├─ Fibonacci pe h4_choch.swing_low/high ← impulse MACRO ⚠️
            │    ├─ fvg_in_golden_zone check ← poate eșua pentru FVG-uri la vârf ⚠️
            │    ├─ entry = fib_75 dacă FVG nu-i în zone ← decuplat de FVG! ⚠️
            │    ├─ TP = nearest swing High D1 > current_price
            │    ├─ FALLBACK1: ultimul swing High D1 ← poate fi sub entry (ATH) ⚠️
            │    ├─ FALLBACK2: max(body D1) ← tot poate fi sub entry (ATH) ⚠️
            │    └─ [LIPSĂ FALLBACK3!] ← codul merge mai departe fără validare ⛔
            │
            └─ RR check:
                 └─ reward = abs(TP - Entry)  ← abs() maschează direcția greșită ⛔
```

---

## ✅ PLAN DE REPARARE (Prioritizat)

### P0 — Fix IMEDIAT (opresc pierderi active)

**1. Adaugă re-validare după FALLBACK2 în LONG TP** (`smc_detector.py` ~linia 2370):
```python
if take_profit <= entry:
    print(f"⛔ [ATH REJECT] {symbol}: TP impossible (ATH context). Trade ANULAT.")
    return None, None, None
```

**2. Adaugă Direction Guard înainte de RR check** (~linia 2464):
```python
if fvg.direction == 'bullish' and take_profit <= entry:
    return None, None, None
if fvg.direction == 'bearish' and take_profit >= entry:
    return None, None, None
```

### P1 — Fix URGENT (în 24h)

**3. Folosește h4_sync_fvg pentru entry când disponibil** (~linia 3983):
```python
fvg_for_entry = h4_sync_fvg if h4_sync_fvg else fvg
entry, sl, tp = self.calculate_entry_sl_tp(symbol, fvg_for_entry, h4_signal, df_4h, df_daily)
```

**4. Adaugă Entry Drift Guard în calculate_entry_sl_tp**:
```python
fvg_span = abs(fvg.top - fvg.bottom)
if abs(entry - fvg.bottom) > fvg_span * 5:
    return None, None, None  # Entry prea departe de FVG
```

### P2 — Refactoring (în 1 săptămână)

**5. Separă calculul entry pentru REVERSAL vs CONTINUITY**
**6. Înlocuiește SL OB hardcodat cu ATR-based**
**7. Înlocuiește TP OB fallback 2% cu Daily ATR × 2**
**8. Adaugă `strategy_type` ca parametru în `calculate_entry_sl_tp`**

---

## 📊 REZUMAT TEHNIC

| Aspect | Detaliu |
|--------|---------|
| **Bug #1 trigger** | GBPJPY (sau orice pereche) la ATH = niciun swing H D1 deasupra entry |
| **Bug #1 root cause** | `reward = abs(TP-Entry)` maskează TP inversat + lipsă re-validare post-FALLBACK2 |
| **Bug #2 trigger** | h4_choch cu impulse mare (ex: 31 pct XTIUSD) → Fib 70-80% mult sub FVG |
| **Bug #2 root cause** | `fvg_in_golden_zone = FALSE` → fallback la `fib_75` care ignoră FVG complet |
| **Confuzie arhitecturală** | `h4_sync_fvg` detectat corect dar nefolosit → Daily POI ≠ Entry Zone |
| **Valori hardcodate critice** | `* 0.9995`, `* 1.02`, `fib_75`, `rr < 4.0` — nu se adaptează la instrument |
| **Instrucțiuni contradictorii** | REVERSAL și CONTINUITY → aceeași formulă entry → comportament divergent |

---

## 🔐 CONCLUZIE

Sistemul are o logică **corectă conceptual** (D1 Bias → 4H Sync → Entry în FVG), dar implementarea are **două puncte de rupere critice**:

1. **Capătul logic (TP la ATH):** Lipsă guard final care să respingă trade-ul dacă TOATE fallback-urile de TP eșuează. Soluția este simplă — 3 linii de cod.

2. **Decuplarea geometrică (FVG vs Fibonacci):** Entry-ul este calculat pe Fibonacci aplicat la impulsul macro al CHoCH-ului, nu pe FVG-ul efectiv. Când impulsul macro e mare (Oil, BTC), nivele Fibonacci cad sub FVG → fallback la fib_75 care nu are nicio legătură cu zona de interes. Soluția: prioritizează `h4_sync_fvg` pentru entry când e disponibil.

Niciun bug nu este aleatoriu — ambele sunt deterministice și reproductibile în condiții specifice de piață (ATH și instrumente cu impulse macro mari).

---

*Audit generat pe baza analizei directe a codului sursă din `smc_detector.py` și `daily_scanner.py`*  
*Toate referințele la numere de linii sunt aproximative (fișier ~5255 linii)*
