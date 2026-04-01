# 🔍 AUDIT: Daily CHoCH Hierarchy & Setup Direction Logic
**Data audit:** 1 Aprilie 2026  
**Trigger:** GBPJPY LONG greșit generat (Daily CHoCH bearish ignorat)  
**Scope:** Toate perechile valutare — bug-ul afectează global, nu doar GBPJPY

---

## ✅ CE FUNCȚIONEAZĂ CORECT (nu editezi)

### 1. Body-Only Detection — ✅ IMPLEMENTAT CORECT
**Fișier:** `smc_detector.py`

**Swing Highs/Lows** — detectate doar prin BODY (open/close), wicks ignorate complet:
```python
# detect_swing_highs() + detect_swing_lows() — liniile ~1232–1310
body_highs = df[['open', 'close']].max(axis=1)   # ← BODY HIGH, fără wick
body_lows  = df[['open', 'close']].min(axis=1)   # ← BODY LOW, fără wick
# Fractal Window 10: 10 bare stânga + 10 bare dreapta confirmare
```

**CHoCH/BOS break validation** — verificat prin body, nu wick:
```python
# detect_choch_and_bos() — liniile ~1036–1037
body_high = max(df['open'].iloc[j], df['close'].iloc[j])  # ← BODY, nu high
body_low  = min(df['open'].iloc[j], df['close'].iloc[j])  # ← BODY, nu low
```

**FVG detection** — body closure only:
```python
# detect_fvg() — liniile ~847–849
body_highs = df[['open', 'close']].max(axis=1)
body_lows  = df[['open', 'close']].min(axis=1)
```

**Concluzie:** Body-only este implementat corect în toată detecția de structură. ✅

---

## ❌ CE ESTE STRICAT (trebuie editat)

### BUG #1 — `smc_detector.py` — BOS din pullback override-uiește CHoCH-ul
**Locație:** liniile 2844–2863 (logica standard, fără BOS dominance)

**Problema:**
```
Timeline real GBPJPY:
  BOS bullish (idx 30) → BOS bullish (idx 35) → CHoCH bearish (idx 50)
  → Preț face pullback UP → BOS bullish din pullback (idx 55)

Cod curent:
  latest_choch.index = 50
  latest_bos.index   = 55   ← BOS din pullback (mai nou!)
  
  if latest_bos.index > latest_choch.index:     # 55 > 50 = TRUE
      strategy_type = 'continuation'             # ← GREȘIT!
      current_trend = latest_bos.direction       # ← 'bullish' din pullback!
```

**Cod actual (greșit):**
```python
# liniile ~2844–2863
elif latest_choch and latest_bos:
    if latest_choch.index > latest_bos.index:
        strategy_type = 'reversal'
        current_trend = latest_choch.direction
    else:
        strategy_type = 'continuation'          # ← BOS din pullback devine trend!
        current_trend = latest_bos.direction    # ← DIRECȚIE GREȘITĂ
```

**Fix necesar:**
```python
elif latest_choch and latest_bos:
    if latest_choch.index > latest_bos.index:
        # CHoCH mai recent → REVERSAL
        strategy_type = 'reversal'
        current_trend = latest_choch.direction
    else:
        # BOS mai recent — verificăm dacă e în ACEEAȘI direcție cu CHoCH
        # sau în direcție opusă (= BOS din pullback = de ignorat)
        if latest_bos.direction == latest_choch.direction:
            # BOS în aceeași direcție cu CHoCH = CONTINUITY validă
            strategy_type = 'continuation'
            current_trend = latest_bos.direction
        else:
            # BOS în direcție OPUSĂ CHoCH-ului = PULLBACK, CHoCH rămâne bias master
            strategy_type = 'reversal'
            current_trend = latest_choch.direction   # ← Direcția CHoCH, nu BOS!
```

---

### BUG #2 — `smc_detector.py` — BOS Dominance counting include BOS-uri din pullback
**Locație:** liniile 2800–2843 (blocul `consecutive_bos_count >= 3`)

**Problema:**
```
Timeline: CHoCH bearish (idx 50) → BOS bullish (idx 55) → BOS bullish (idx 58) → BOS bullish (idx 61)
consecutive_bos_count = 3 ← TOATE sunt din pullback, POSTERIOARE CHoCH-ului!
dominant_bos_direction = 'bullish'

Intră în blocul V10.7:
  latest_choch.index (50) < latest_bos.index (61)
  → strategy_type = 'continuation', current_trend = 'bullish'  ← GREȘIT!
```

**Cod actual (greșit):**
```python
# liniile ~2800–2812
if len(daily_bos_list) >= 3:
    recent_bos = daily_bos_list[-5:]   # ← include BOS-uri din pullback!
    for bos in reversed(recent_bos):
        if dominant_bos_direction is None:
            dominant_bos_direction = bos.direction
            consecutive_bos_count = 1
        elif bos.direction == dominant_bos_direction:
            consecutive_bos_count += 1
        else:
            break
```

**Fix necesar:**
```python
# Numărăm NUMAI BOS-uri ANTERIOARE ultimului CHoCH (nu din pullback)
if len(daily_bos_list) >= 3:
    choch_cutoff_idx = latest_choch.index if latest_choch else 999999
    # Filtrăm BOS-urile care au apărut ÎNAINTE de CHoCH
    pre_choch_bos = [b for b in daily_bos_list if b.index < choch_cutoff_idx]
    recent_bos = pre_choch_bos[-5:] if pre_choch_bos else []
    
    for bos in reversed(recent_bos):
        ...
```

---

### BUG #3 — `setup_executor_monitor.py` — V10.9 Bypass sare complet peste 4H CHoCH
**Locație:** liniile 905–908

**Problema:**
```
Chiar dacă smc_detector.py returnează un setup GREȘIT (continuation bullish 
când trebuia reversal bearish), executorul NU verifică nimic pentru continuation:
```

**Cod actual (greșit):**
```python
# liniile ~905–908
if not h4_locked and strategy_type == 'continuation':
    setup['h4_structure_locked'] = True   # ← BYPASS TOTAL, fără verificare 4H CHoCH!
    h4_locked = True
    logger.info(f"V10.9 CONTINUATION BYPASS: structura 4H confirmată prin BOS activ")
```

**Fix necesar:**
```python
# CONTINUATION bypass valid NUMAI dacă BOS-ul NU urmează unui CHoCH opus recent
if not h4_locked and strategy_type == 'continuation':
    # Verificăm că nu există un CHoCH recent în direcție opusă (semn de pullback)
    d1_bias = setup.get('d1_bias_direction', '')
    d1_choch_after_bos = setup.get('d1_choch_after_bos', False)
    
    if d1_choch_after_bos:
        # BOS-ul e din pullback (posterior unui CHoCH opus) → NU bypass, cere 4H CHoCH
        logger.warning(f"V10.9 BYPASS BLOCAT: BOS din pullback post-CHoCH — cerem 4H CHoCH")
    else:
        setup['h4_structure_locked'] = True
        h4_locked = True
```

---

## 📊 CASCADA COMPLETĂ A BUG-ULUI (cum ajunge la execuție greșită)

```
┌─────────────────────────────────────────────────────────────────────┐
│ smc_detector.py — scan_for_setup()                                  │
│                                                                     │
│  Daily CHoCH bearish (idx 50) ──────────────────────┐              │
│  BOS bullish din pullback (idx 55) ──────────────┐  │              │
│                                                  │  │              │
│  latest_bos.index(55) > latest_choch.index(50)   │  │              │
│         ↓                                        │  │              │
│  strategy_type = 'continuation'  ← BUG #1        │  │              │
│  current_trend = 'bullish'       ← GREȘIT         │  │              │
└─────────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ daily_scanner.py — salvează în monitoring_setups.json               │
│                                                                     │
│  setup.strategy_type  = 'continuation'                              │
│  setup.daily_choch.direction = 'bullish'   ← din BOS, nu CHoCH!    │
│  d1_bias_direction = 'bullish'             ← GREȘIT                │
│  direction = 'buy'                         ← GREȘIT                │
└─────────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ setup_executor_monitor.py — execuție                                │
│                                                                     │
│  strategy_type == 'continuation'                                    │
│  → V10.9 BYPASS: h4_structure_locked = True INSTANT  ← BUG #3     │
│  → Nu verifică 4H CHoCH                                            │
│  → EXECUTĂ LONG ❌                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 REGULA CORECTĂ (ce trebuie să implementăm)

```
Daily CHoCH bearish = BIAS MASTER (override tot)
         ↓
Preț face pullback UP (normal, 4H bullish = corectiv)
         ↓
BOS bullish din pullback = IGNORAT ca semnal principal
         ↓
Așteptăm 4H CHoCH bearish = confirmă că pullback-ul s-a terminat
         ↓
Setup SELL valid → intrare în FVG
```

**Ierarhia structurală:**
```
Timeframe  │  Rol                        │  Override?
───────────┼─────────────────────────────┼──────────────────
Daily      │  BIAS MASTER (direcție)     │  Nu poate fi overridden
4H         │  CONFIRMATION GATE (timing) │  Trebuie aliniat cu Daily
1H         │  ENTRY TRIGGER (execuție)   │  Numai după 4H confirmat
```

---

## 📝 FIȘIERE DE EDITAT (prioritate)

| # | Fișier | Linii | Bug | Prioritate |
|---|--------|-------|-----|-----------|
| 1 | `smc_detector.py` | 2844–2863 | BOS din pullback override CHoCH | 🔴 CRITIC |
| 2 | `smc_detector.py` | 2800–2843 | BOS dominance include post-CHoCH | 🔴 CRITIC |
| 3 | `setup_executor_monitor.py` | 905–908 | V10.9 bypass fără verificare | 🟡 IMPORTANT |

---

## 🔒 CE NU TREBUIE ATINS

| Fișier | Componentă | Status |
|--------|-----------|--------|
| `smc_detector.py` | Body-only swing detection | ✅ Corect |
| `smc_detector.py` | Body-only CHoCH/BOS break validation | ✅ Corect |
| `smc_detector.py` | Body-only FVG detection + mitigation | ✅ Corect |
| `smc_detector.py` | Fractal Window 10 pentru swings | ✅ Corect |
| `smc_detector.py` | V10.7 REVERSAL BYPASS (CHoCH > BOS) | ✅ Corect |
| `check_4h_pullbacks.py` | 4H CHoCH detection (direction check) | ✅ Corect |
| `setup_executor_monitor.py` | 4H body closure lock pentru REVERSAL | ✅ Corect |

---

## 🧪 CUM SĂ VERIFICI DUPĂ FIX

Testează cu GBPJPY (trigger-ul original):
```
Așteptat după fix:
  - Daily CHoCH bearish → strategy_type = 'reversal', direction = 'sell'
  - BOS bullish din pullback → IGNORAT (nu mai override)
  - Setup apare numai când 4H face CHoCH bearish
  - h4_structure_locked = False până la confirmare 4H
```

Testează că nu ai regresii pe:
- EURUSD/GBPUSD cu trend clar bullish (BOS bullish consecutive → CONTINUATION LONG ✅)
- XAUUSD cu CHoCH bullish după BOS bearish → REVERSAL LONG ✅
- Orice pereche unde CHoCH este cel mai recent semnal → REVERSAL ✅
