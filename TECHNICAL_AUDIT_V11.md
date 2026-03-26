# 🔬 RAPORT TEHNIC — ARHITECTURA BOTULUI (V11.2)
**Glitch in Matrix by ФорексГод — Audit Complet + Recalibrare EXTREME VISION**

> Generat: 26 Martie 2026 | Actualizat: 26 Martie 2026 | Claude Sonnet 4.6 | Bazat pe analiza directă a codului sursă
> **V11.2 STATUS: ✅ TOATE FIXURILE APLICATE ȘI VERIFICATE SYNTAX OK**

---

## 📦 SECȚIUNEA 1 — DATE DESCĂRCATE (Sursă: `pairs_config.json` + `daily_scanner.py`)

| Timeframe | Bare Descărcate | Perioadă Reală | Fișier / Linie | Status |
|-----------|----------------|----------------|----------------|--------|
| **D1**    | ~~100 bare~~ → **200 bare** | ~~5 luni~~ → **~10 luni** | `pairs_config.json:153` / `daily_scanner.py:568` | ✅ V11.2 FIX |
| **H4**    | **200 bare**   | ~33 zile       | `pairs_config.json:154` / `daily_scanner.py:569` | ✅ neschimbat |
| **H1**    | **300 bare**   | ~12.5 zile     | `pairs_config.json:155` / `daily_scanner.py:570` | ✅ neschimbat |

**Notă din config (V11.2):**
> "V11.2 EXTREME VISION: 200D=10mo extremes (USDCHF fix), 200x4H=33 days structure, 300x1H=12.5 days precision"

---

## 🧠 SECȚIUNEA 2 — DETECTARE STRUCTURĂ (CHoCH / BOS)
**Sursă: `smc_detector.py` — funcția `detect_choch_and_bos()` (linia 1331)**

| Parametru | Valoare Exactă | Linie în Cod | Status |
|-----------|---------------|--------------|--------|
| ~~`swing_lookback` adaptiv (V10)~~ | ~~**5–25 candele** via `ATR_200/ATR_14×5`~~ | ~~`smc_detector.py:180`~~ | ❌ ÎNLOCUIT |
| **Fractal Window (V11.2)** | **10 candele** fix — fiecare parte (bilateral) | `smc_detector.py:1222` | ✅ ACTIV |
| Condiție confirmare swing | Toate **10 bare stânga** + **10 bare dreapta** strict mai mici/mari | `smc_detector.py:1243-1251` | ✅ ACTIV |
| Minim bare necesar | **21 bare** (2×10+1) | `smc_detector.py:1227` | ✅ ACTIV |
| Prominence threshold (V11.2) | **0.0** — Fractal Window e filtrul, nu ATR | `smc_detector.py:1232` | ✅ ACTIV |
| Bare scanate efectiv | `len(df) - 20` → **180 bare** D1 / **180 bare** H4 | `smc_detector.py:1239` | ✅ ACTIV |
| Inițializare trend macro | Ultimele **150 bare** din df | `smc_detector.py:1371` | neschimbat |
| Re-evaluare trend | La fiecare swing, ultimii **5** highs + **5** lows | `smc_detector.py:1394` | neschimbat |
| Validare pattern CHoCH | Ultimele **3** highs + **3** lows | `smc_detector.py:1427` | neschimbat |
| **4H CHoCH max vârstă (REVERSAL)** | **48 candele = 8 zile** | `smc_detector.py:3379` | neschimbat |
| **4H CHoCH scan range** | Ultimele **50 candele** din df_4h | `smc_detector.py:3368` | neschimbat |
| **4H CHoCH max vârstă (SCALE_IN Entry 2)** | **12 candele = 48 ore** | `smc_detector.py:4409` | neschimbat |

### ⚙️ V11.2 — Fractal Window 10 (înlocuiește formula adaptivă)
```python
# V11.2 — FRACTAL WINDOW 10
FRACTAL_WINDOW = 10
# Condiție swing HIGH valid:
left_check  = all(current_high > body_highs.iloc[i-j] for j in range(1, FRACTAL_WINDOW+1))
right_check = all(current_high > body_highs.iloc[i+j] for j in range(1, FRACTAL_WINDOW+1))
# Condiție swing LOW valid — invers (strict mai mic)
```

**De ce Fractal Window 10?**
- Lookback 5 detecta false micro-swinguri (mușuroaie, nu munți)
- Lookback 25 rata swing-uri reale în piețe volatile
- **10 = mijlocul de aur**: detectăm doar structuri majore confirmate bilateral
- Body-to-body (fără wick) = nivelele la care instituțiile chiar au executat

---

## 🎯 SECȚIUNEA 3 — TAKE PROFIT (TP)
**Sursă: `smc_detector.py` — funcția `calculate_entry_sl_tp()` (liniile 2285-2310 LONG / 2360-2385 SHORT)**

| Aspect | V10 (vechi) | V11.2 (nou) | Linie |
|--------|-------------|-------------|-------|
| Sursă date | `detect_swing_highs(df_daily)` — filtrat prin Fractal | **`body_highs_d1.iloc[:-1].max()`** — RAW body | `smc_detector.py:2285` |
| Bare D1 disponibile | ~~100 bare~~ (~5 luni) | **200 bare** (~10 luni) | `pairs_config.json:153` |
| Metodă selectare TP (LONG) | `max(swing_highs, key=price)` — poate rata HH recent | **`body_highs.iloc[:-1].max()`** — absolut max body | `smc_detector.py:2287` |
| Metodă selectare TP (SHORT) | `min(swing_lows, key=price)` | **`body_lows.iloc[:-1].min()`** — absolut min body | `smc_detector.py:2362` |
| Excludere bara curentă | `sh.index < len(df_daily)-1` | **`iloc[:-1]`** — neconfirmată exclusă | `smc_detector.py:2287` |
| Validare corp | `max(open, close)` — fără wick | **`max(open, close)`** — fără wick | neschimbat |
| Fallback TP | `df_daily[body].max()` | **`body_highs_d1.max()`** (incl. bara curentă) | `smc_detector.py:2292` |
| Validare finală | TP > entry (LONG) / TP < entry (SHORT) | neschimbat | `smc_detector.py:2294` |

### ✅ FIX APLICAT — TP CORECT (V11.2)
```python
# LONG TP: maximul absolut body din 200 bare D1
body_highs_d1 = df_daily[['open', 'close']].max(axis=1)
take_profit   = body_highs_d1.iloc[:-1].max()   # RAW — fără swing detection

# SHORT TP: minimul absolut body din 200 bare D1
body_lows_d1 = df_daily[['open', 'close']].min(axis=1)
take_profit  = body_lows_d1.iloc[:-1].min()
```
**De ce bypassăm `detect_swing_highs()` pentru TP?**
Cu Fractal Window 10, un HH la bara 185/200 NU are 10 bare confirmate dreapta → e invizibil.
Soluție: ignorăm swing detection pentru TP și luăm direct extrema brută a corpului.
Instituțiile vânează lichiditate externă (HH/LL absolut) — nu swing-uri filtrate.

> **Exemplu USDCHF:** HH-ul la 0.9248 (Iulie 2025) era invizibil cu 100 D1 bare.
> Cu V11.2: 200 bare D1 + RAW max → TP corect la nivelul real instituțional.

---

## 🛡️ SECȚIUNEA 4 — STOP LOSS (SL)
**Sursă: `smc_detector.py` — funcția `calculate_entry_sl_tp()` (liniile 2253-2280 LONG / 2318-2345 SHORT)**

| Aspect | V10 (vechi) | V11.2 (nou) | Linie |
|--------|-------------|-------------|-------|
| Metodă LONG | `structural_lows_4h[-1]` — cel mai recent swing | **`body_lows_4h[choch_idx-40:].min()`** — extrema absolută | `smc_detector.py:2260` |
| Metodă SHORT | `structural_highs_4h[-1]` — cel mai recent swing | **`body_highs_4h[choch_idx-40:].max()`** — extrema absolută | `smc_detector.py:2325` |
| Fereastră structurală | ~~ultimul swing~~ | **40 bare înainte de CHoCH → prezent** | `smc_detector.py:2257` |
| Bare H4 disponibile | 200 bare (~33 zile) | **200 bare** — neschimbat | `pairs_config.json:154` |
| ATR buffer pe SL | variabil | **0 (zero)** — fără buffer, extrema brută | `smc_detector.py:2263` |
| Validare corp | `min(open, close)` — fără wick | `min(open, close)` — fără wick | neschimbat |
| Fallback SL | `df_4h[body_lows].min()` toți df_4h | **`body_lows_4h.min()`** — toți df_4h | `smc_detector.py:2267` |
| Validare finală | SL < entry (LONG) / SL > entry (SHORT) | neschimbat | `smc_detector.py:2270` |
| Minimum SL Forex | 30 pips hard floor | neschimbat | `smc_detector.py:2171` |
| Minimum SL Crypto | 0.3% din entry | neschimbat | `smc_detector.py:2162` |
| Minimum SL Metals | 50 pips | neschimbat | `smc_detector.py:2174` |
| Minimum SL Energy | 30 pips | neschimbat | `smc_detector.py:2177` |

### ✅ FIX APLICAT — SL STRUCTURAL REAL (V11.2)
```python
# LONG SL: minimul absolut body din fereastra structurală CHoCH
h4_choch_idx   = h4_choch.index  # bara CHoCH
sl_window_start = max(0, h4_choch_idx - 40)  # 40 bare înainte = Supply/Demand zone
body_lows_4h    = df_4h[['open', 'close']].min(axis=1)
stop_loss       = body_lows_4h.iloc[sl_window_start:].min()  # GROAPA REALĂ

# SHORT SL: maximul absolut body din fereastra structurală CHoCH
body_highs_4h   = df_4h[['open', 'close']].max(axis=1)
stop_loss       = body_highs_4h.iloc[sl_window_start:].max()  # VÂRFUL REAL
```
**Logică:** SL trebuie la baza/vârful structurii din care a plecat mișcarea CHoCH.
Zona de ±40 bare H4 în jurul CHoCH = Supply/Demand Zone instituțională.
SL la extrema absolută a acestei zone = stop-out doar dacă structura e INVALIDATĂ TOTAL.

---

## 🧲 SECȚIUNEA 5 — FVG DETECTION (Magnet de Entry)
**Sursă: `smc_detector.py` — funcția `detect_fvg()` (linia 800)**

| Aspect | Valoare Exactă | Linie |
|--------|---------------|-------|
| Start scan | `max(0, choch.index - 20)` — **20 bare ÎNAINTE** de CHoCH | `smc_detector.py:845` |
| End scan | `len(df) - 1` — **până la ultima bară** (FĂRĂ LIMITĂ) | `smc_detector.py:853` |
| Limita veche (eliminată) | ~~`choch.index + 30`~~ → **eliminată în V10.3** | — |
| Method 1 (primar) | **Body-to-body FVG strict**: `body_high[i-1] < body_low[i+1]` | `smc_detector.py:867` |
| Method 2 (fallback) | **Wick-to-wick FVG**: `high[i-1] < low[i+1]` (dacă Method 1 = 0 rezultate) | `smc_detector.py:~960` |
| Gap size minim | **0.05%** din preț pentru Method 1 | `smc_detector.py:876` |
| Gap size minim | **0.03%** din preț pentru Method 2 | `smc_detector.py:~975` |
| Direcție FVG | STRICT aliniată cu CHoCH — ignoră FVG-uri opuse | `smc_detector.py:860` |
| ✅ Status | Scanează **TOT** intervalul `CHoCH → prezent + 20 pre-CHoCH` | — |

---

## ⏱️ SECȚIUNEA 6 — COMPARAȚIE 4H vs 1H

| Parametru | **4H** | **1H** |
|-----------|--------|--------|
| Bare descărcate | **200** (33 zile) | **300** (12.5 zile) |
| Rol în sistem | Confirmare CHoCH + SL structural | Entry 1 sniper (SCALE_IN) |
| CHoCH max vârstă (REVERSAL) | **48 candele** = 8 zile | Nu se aplică |
| CHoCH max vârstă (Entry 2 SCALE_IN) | **12 candele** = 48h | — |
| Swing lookback | **5–25** (adaptiv) | **5–25** (adaptiv) |
| Bare efective scanate | **190–176** (200 − 2×lookback) | **290–276** (300 − 2×lookback) |
| Sursa SL | ✅ DA — `detect_swing_lows(df_4h)` | ❌ NU (SL e mereu structural 4H) |
| Sursa TP | ❌ NU (TP e mereu structural D1) | ❌ NU |

---

## 🔴 SECȚIUNEA 7 — REZUMAT UNGHIURI MOARTE

| # | Problemă | TF Afectat | Impact Real | Fix | Status |
|---|---------|-----------|-------------|-----|--------|
| **1** | **TP trunhiat** — HH/LL mai vechi de 5 luni invizibile | D1 | TP prea jos/sus față de structura reală | `"daily": 200` + RAW body max (bypass swing detection) | ✅ **REZOLVAT V11.2** |
| **2** | **SL prea strâns** — `structural_lows[-1]` = minor swing lângă entry | H4 | Stop-out prematur pe zgomot normal | SL = extrema absolută zona CHoCH ±40 bare | ✅ **REZOLVAT V11.2** |
| **3** | **False micro-swinguri** — lookback adaptiv 5-25 detecta mușuroaie | Toate TF | Nivel structuri false → CHoCH invalid | Fractal Window 10 — bilateral confirmare | ✅ **REZOLVAT V11.2** |
| **4** | **4H CHoCH scan: max 50 bare** — structuri lente ignorate | H4 | Setup-uri valide cu CHoCH >8.3 zile pierdute | Extinde scan range la 80–100 bare | 🟡 **PENDING** |

---

## ✅ SECȚIUNEA 8 — CE FUNCȚIONEAZĂ CORECT

| Funcție | Status | Detalii |
|---------|--------|----------|
| FVG detection range | ✅ **COMPLET** | Scanează tot intervalul CHoCH→prezent (V10.3 fix) |
| Body closure validation | ✅ **ACTIV** | Niciodată wick — `max(open,close)` / `min(open,close)` |
| 4H CHoCH age (REVERSAL) | ✅ **EXTINS** | 48 candele = 8 zile (V10.2 fix) |
| ATR prominence filter | ✅ **ELIMINAT** | Înlocuit cu Fractal Window 10 (V11.2) — prominence = 0.0 |
| RR floor | ✅ **STRUCTURAL** | Minim **1:4** — sub 1:4 → trade RESPINS |
| **Fractal Window 10** | ✅ **NOU V11.2** | Bilateral 10 bare confirmare — body-to-body — doar munți/văi reale |
| **SL = Extrema absolută** | ✅ **NOU V11.2** | `body_lows/highs_4h[choch_idx-40:].min/max()` — groapa/vârful real |
| **TP = RAW body extreme** | ✅ **NOU V11.2** | `body_highs/lows_d1.iloc[:-1].max/min()` — bypass swing detection |
| **D1 memorie 10 luni** | ✅ **NOU V11.2** | 200 bare D1 — vede HH/LL până la 10 luni în urmă (USDCHF fix) |
| CARRY MATRIX | ✅ **LIVE** | Swap live de la cTrader port 8767 în mesaje Telegram |
| Macro Weekly Table | ✅ **AUTOMAT** | Luni 09:00 RO, cu scraping live dobânzi + top 3 carry pairs |
| Single instance lock | ✅ **ACTIV** | `fcntl.LOCK_EX` previne mesaje duble |

---

## 🛠️ SECȚIUNEA 9 — FIXURI APLICATE ÎN ACEASTĂ SESIUNE (V11.0 + V11.2)

### Fix 4 — Fractal Window 10 (`smc_detector.py` — V11.2)
```python
# detect_swing_highs() + detect_swing_lows()
# ÎNAINTE (V10): adaptive lookback int(5 × ATR_200/ATR_14) clamped [5,25]
# DUPĂ (V11.2): Fractal Window 10 — fix bilateral
FRACTAL_WINDOW = 10
for i in range(FRACTAL_WINDOW, len(df) - FRACTAL_WINDOW):
    left_check  = all(current_high > body_highs.iloc[i-j] for j in range(1, FRACTAL_WINDOW+1))
    right_check = all(current_high > body_highs.iloc[i+j] for j in range(1, FRACTAL_WINDOW+1))
    if left_check and right_check:
        swing_highs.append(SwingPoint(index=i, price=current_high, ...))
```

### Fix 5 — SL = Extrema Absolută Zona CHoCH (`smc_detector.py` — V11.2)
```python
# ÎNAINTE (V10): stop_loss = structural_lows_4h[-1].price  (ultimul swing mic)
# DUPĂ (V11.2): extrema absolută din fereastra ±40 bare în jurul CHoCH
h4_choch_idx    = h4_choch.index
sl_window_start = max(0, h4_choch_idx - 40)
body_lows_4h    = df_4h[['open', 'close']].min(axis=1)
stop_loss       = body_lows_4h.iloc[sl_window_start:].min()  # LONG
# stop_loss = body_highs_4h.iloc[sl_window_start:].max()   # SHORT
```

### Fix 6 — TP = RAW Body Extreme D1 (`smc_detector.py` — V11.2)
```python
# ÎNAINTE (V10): take_profit = max(detect_swing_highs(df_daily), key=price)
# DUPĂ (V11.2): RAW body maximum din 200 D1 bare (bypass swing detection)
body_highs_d1 = df_daily[['open', 'close']].max(axis=1)
take_profit   = body_highs_d1.iloc[:-1].max()  # LONG — absolut max
# take_profit = body_lows_d1.iloc[:-1].min()   # SHORT — absolut min
```

### Fix 7 — D1 Memorie Extinsă la 200 Bare (`pairs_config.json` — V11.2)
```json
// ÎNAINTE: "daily": 100  (5 luni)
// DUPĂ:    "daily": 200  (10 luni = USDCHF HH vizibil)
"lookback_candles": {
  "daily": 200,
  "h4": 200,
  "h1": 300,
  "note": "V11.2 EXTREME VISION: 200D=10mo extremes (USDCHF fix)"
}
```

---

### Fix 1 — CARRY MATRIX în mesajul SNIPER ELITE (`position_monitor.py`)
```python
# Prioritate: live cTrader port 8767 → fallback monitoring_setups.json
swap_long, swap_short, swap_triple_day = fetch_live_or_cached(symbol)
# Output în mesaj:
# 💱 CARRY MATRIX: ✅ CREDIT
#    Long: +1.3900 | Short: -2.2100
#    Direcția ta: +1.3900 pips/zi
#    🔥 TRIPLE SWAP DISEARĂ! x3 = +4.1700 pips
```

### Fix 2 — Macro Weekly Table (`news_calendar_monitor.py`)
```python
CENTRAL_BANK_RATES = {
    "NZD": 5.25, "GBP": 5.00, "USD": 4.75, "AUD": 4.35,
    "CAD": 3.75, "EUR": 3.50, "CHF": 1.50, "JPY": 0.25
}
# Automat: Luni ≥ 09:00 RO → trimite tabel pe Telegram
# Live scraping: investing.com → override hardcoded dacă rata s-a schimbat
# Alert automat: 🚨 RATE CHANGE DETECTED! când banca centrală modifică dobânda
```

### Fix 3 — CARRY MATRIX în `/monitoring` Telegram (`telegram_command_center.py`)
```
PÂNDĂ ACTIVĂ: 💱 CARRY: ✅ POZITIV | +1.3900 pips/zi
LIVE LA BROKER: 💱 CARRY: ✅ CREDIT -20.0000 pips/zi
```

---

## 📋 SECȚIUNEA 10 — FIȘIERE CRITICE ȘI ROLURILE LOR

| Fișier | Rol | Versiune |
|--------|-----|---------|
| `smc_detector.py` | Inima sistemului — detectare CHoCH/BOS/FVG, calcul Entry/SL/TP | **V11.2** ✅ |
| `daily_scanner.py` | Orchestrator — descarcă date, apelează SMC, trimite pe Telegram | V10.2 |
| `setup_executor_monitor.py` | Daemon — verifică la 30s dacă prețul a atins zona de entry | V8.2 |
| `position_monitor.py` | Daemon — detectează poziții noi/închise, trimite notificări | V11.0 ✅ |
| `telegram_command_center.py` | Daemon — ascultă comenzi Telegram `/monitoring` `/active` `/stats` | V3.7 ✅ |
| `news_calendar_monitor.py` | Daemon — rapoarte știri + Macro Weekly Table (Luni 09:00) | V11.0 ✅ |
| `watchdog_monitor.py` | Daemon — repornește automat procesele cazute | V2.0 |
| `ctrader_cbot_client.py` | Client HTTP → cTrader port 8767 (prețuri, swap, historical data) | V11.0 |
| `pairs_config.json` | Config central — perechi, bare, RR minim, lookback | **V11.2** ✅ |
| `monitoring_setups.json` | Stare live — 12 setup-uri cu swap_long/swap_short/swap_triple_day | V11.0 ✅ |
| `economic_calendar.json` | Calendar manual — events până 28 Martie 2026 | V11.0 |

---

## 🚀 SECȚIUNEA 11 — NEXT STEPS RECOMANDATE

### ✅ COMPLETAT — Prioritate 1 (D1 200 bare + TP RAW extreme):
```json
// pairs_config.json — DONE V11.2
"daily": 200  // era 100 → vede acum 10 luni
```
```python
# smc_detector.py — DONE V11.2
body_highs_d1 = df_daily[['open', 'close']].max(axis=1)
take_profit   = body_highs_d1.iloc[:-1].max()  # RAW extrema
```

### ✅ COMPLETAT — Prioritate 2 (SL extrema absolută + Fractal Window 10):
```python
# smc_detector.py — DONE V11.2
# SL: body extremes din fereastra CHoCH ±40 bare
# Fractal Window 10: bilateral 10 bare confirmare
```

### 🟡 PENDING — Prioritate 3 (4H CHoCH scan range extins):
```python
# smc_detector.py — scan_for_setup()
# Problema: scan range = ultimele 50 bare H4 = 8.3 zile
# Fix propus: extinde la 80-100 bare H4 = 13-16 zile
# Linie: smc_detector.py:3368
scan_start = max(0, len(df_4h) - 100)  # era 50 → 100
```

### 🔴 URGENT — Prioritate 4 (April 2026 calendar):
```bash
# DEADLINE: 1 Aprilie 2026 (5 ZILE!)
# Key events: NFP 3 Apr, FOMC Minutes, RBA, BoE
python3 add_monthly_events.py  # sau adaugă manual în economic_calendar.json
```

### 🟡 PENDING — Prioritate 5 (Live test USDCHF V11.2):
```bash
# Verifică că TP USDCHF SHORT e acum ~0.9248+ (10-month HH)
# Era truncat la 5-month high cu V10
python3 daily_scanner.py  # rulează scan complet și verifică output
```

---

*Ultima actualizare: 26 Martie 2026 | Glitch in Matrix **V11.2 EXTREME VISION** | ✨ by ФорексГод*
*V11.2 verificat syntax: `smc_detector.py ✅ | daily_scanner.py ✅ | pairs_config.json ✅`*
