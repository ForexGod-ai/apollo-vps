# 🏛️ AUDIT ARHITECTURAL COMPLET — ГЛИТЧ ИН МАТРИКС V10.8
**Data auditului**: 23 Martie 2026  
**Versiunea curentă**: V10.8 "THE CLEAN SLATE"  
**Versiunea profitabilă referință**: V3.1 (commit `1f43732`)  
**Auditor**: GitHub Copilot (Claude Sonnet 4.6)

> ✅ **UPDATE V10.8** — Documentul a fost actualizat pentru a reflecta toate modificările aplicate în sesiunile V10.6, V10.7 și V10.8. Rezultat final: **GBPUSD READY ✅ | USDCAD MONITORING ✅ | GBPJPY READY ✅** (confirmat live 23 Mar 2026)

---

## CUPRINS

1. [Evoluția Contului — Cronologie Financiară](#1-evolutia-contului)
2. [Harta Sistemului — 6 Componente](#2-harta-sistemului)
3. [Rolul Fiecărui Fișier](#3-rolul-fiecarui-fisier)
4. [Drumul unui Setup — De la Date la Buton](#4-drumul-unui-setup)
5. [Cele 19 Straturi de Filtre](#5-cele-19-straturi-de-filtre)
6. [Comparație V3.1 vs V10.5 vs V10.8](#6-comparatie-v31-vs-v105-vs-v108)
7. [Analiza Trade History — Ce a Funcționat și Ce a Ucis Contul](#7-analiza-trade-history)
8. [Punctele de Blocaj — Starea Înainte și După V10.8](#8-punctele-de-blocaj)
9. [Starea Curentă a Scanerului (23 Mar 2026)](#9-starea-curenta-scanner)
10. [Jurnal Complet Modificări V10.6 → V10.8](#10-jurnal-modificari)
11. [Recomandări Rămase](#11-recomandari-ramase)

---

## 1. EVOLUȚIA CONTULUI — CRONOLOGIE FINANCIARĂ

### Date oficiale (din `trade_history.json`, 23 Mar 2026)
```
Cont: IC Markets Demo #9709773
Start capital estimat: $1,000
Peak balance: $13,746.96 (la trade #155)
Balance curent (closed P/L): $5,162.74
Equity curentă: $2,761.89
Open P/L activ: -$2,400.85
Total trades închise: 230
Win Rate global: 36%
```

### Evoluția pe 4 Faze

| Fază | Trades | Profit/Pierdere | Win Rate | Observație |
|------|--------|-----------------|----------|------------|
| **Faza 1** (trade #1-50) | 50 | **+$634.99** | 50% | Start solid, scalare mică |
| **Faza 2** (trade #51-100) | 50 | **-$980.66** | 14% | Prăbușire — USDJPY/USDCHF repetitive |
| **Faza 3** (trade #101-155) | 55 | **+$11,361.50** | 51% | 🏆 PEAK — V3.1 + scalare mare |
| **Faza 4** (trade #156-230) | 75 | **-$6,853.09** | 29% | Catastrofă — XAUUSD + USDJPY |

### Momentul Peak (Trade #155)
```
Trade #154: BTCUSD SELL 0.50 lots → +$947.27 → sold $13,732.47
Trade #155: XAUUSD SELL 0.07 lots → +$14.49  → sold $13,746.96  ← PEAK MAXIM
Trade #156: XAUUSD SELL 0.30 lots → -$6,786.61 → sold $6,960.35 ← CATASTROFĂ
```
**Concluzie**: O singură tranzacție XAUUSD a distrus **49.3% din cont** ($6,786.61 dintr-un peak de $13,746).

---

## 2. HARTA SISTEMULUI — 6 COMPONENTE

```
┌─────────────────────────────────────────────────────────┐
│                    cTrader cBot                         │
│           HTTP Server localhost:8767                    │
│     Furnizează: D1(100 bare) + H4(200 bare) + H1(225)  │
│         Polls signals.json la fiecare ~10 secunde       │
└───────────────┬──────────────────────────┬──────────────┘
                │ DATE OHLC BRUTE          │ EXECUȚIE TRADE
                ▼                          ▼
┌──────────────────────┐    ┌──────────────────────────────┐
│  daily_scanner.py    │    │  ctrader_executor.py         │
│  ORCHESTRATORUL      │    │  EXECUTORUL                  │
│  778 linii           │───▶│  898 linii                   │
│  Descarcă date       │    │  Scrie signals.json          │
│  Apelează creierul   │    │  Calculează lot size         │
│  Trimite Telegram    │    │  V8.0 SL/TP ZERO GUARD       │
│  Salvează setups     │    │  BTCUSD bulletproof 0.50 lot │
└──────────┬───────────┘    └──────────────────────────────┘
           │ DataFrames                    ▲
           ▼                               │ ONLY if status='READY'
┌──────────────────────┐    ┌──────────────────────────────┐
│  smc_detector.py     │    │  setup_executor_monitor.py   │
│  CREIERUL            │    │  WATCHDOG SETUPS             │
│  4932 linii          │───▶│  2050 linii                  │
│  19 filtre           │    │  Polls cada 30 secunde       │
│  Returnează Setup    │    │  Citește monitoring_setups   │
│  READY / MONITORING  │    │  Detectează 4H CHoCH live    │
│  sau None (RESPINS)  │    │  → Schimbă MONITORING→READY  │
└──────────────────────┘    └──────────────────────────────┘
                                           ▲
                            ┌──────────────┴─────────────────┐
                            │  watchdog_monitor.py           │
                            │  PAZNICUL SISTEMULUI (V4.0)    │
                            │  533 linii                     │
                            │  Monitorizează 6 procese       │
                            │  Repornire automată la crash   │
                            └────────────────────────────────┘
```

---

## 3. ROLUL FIECĂRUI FIȘIER

### 🧠 `smc_detector.py` — CREIERUL (4932 linii)

**Scopul unic**: Primește date OHLC brute → analizează structura SMC → returnează `TradeSetup` sau `None`.

Nu știe de internet. Nu știe de Telegram. Nu trimite ordine. **Face un singur lucru**: citește bare și decide dacă există un setup valid.

**Funcții principale**:
| Funcție | Linii | Rol |
|---------|-------|-----|
| `detect_swing_highs()` | ~1197 | Identifică HH/LH cu filtru ATR prominence |
| `detect_swing_lows()` | ~1265 | Identifică LL/HL cu filtru ATR prominence |
| `detect_choch_and_bos()` | 1323-1516 | CHoCH și BOS — V10.5: OR + big_drop/pump >10% |
| `determine_daily_trend()` | ~1517 | Macro trend D1 prin ierarhia BOS (150 bare) |
| `detect_fvg()` | 800-993 | Fair Value Gap — corp + wick fallback |
| `validate_fvg_zone()` | ~330 | Verifică FVG în zona Premium/Discount ±10% buffer |
| `calculate_fvg_quality_score()` | ~1878 | Scor FVG 0-100 (4 criterii) |
| `calculate_entry_sl_tp()` | ~2169 | Calculează entry, Stop Loss, Take Profit |
| `scan_for_setup()` | 2748-4930 | **FUNCȚIA PRINCIPALĂ — 19 straturi de filtre** |

**Problema fundamentală**: `scan_for_setup()` are **~1382 linii** și **19 puncte de return None** independente. V3.1 (codul profitabil) executa aceeași logică în **~400 linii** cu **7 filtre**.

---

### 🎯 `daily_scanner.py` — ORCHESTRATORUL (778 linii)

**Scopul**: Rulează zilnic (sau la cerere), gestionează întregul ciclu de scanare.

**Fluxul complet `run_daily_scan()`**:
```
1. Conectare cTrader localhost:8767
2. Încarcă monitoring_setups.json (setups existente din sesiunile anterioare)
3. Pentru FIECARE din cele 16 perechi din pairs_config.json:
   a. Descarcă D1(100) + H4(200) + H1(225 bare)
   b. Apelează smc_detector.scan_for_setup(symbol, df_daily, df_4h, priority, df_1h)
      ↳ require_4h_choch=True (hardcodat)
      ↳ debug=False (NICIO informație de diagnostic în producție!)
   c. Dacă setup ≠ None:
      → Calculează ML score
      → Calculează AI probability
      → Generează grafic Telegram
      → Salvează în monitoring_setups.json
   d. Dacă None → print "⛔ NO SETUP [V10.2 REJECT: vezi log-ul ↑]"
4. Salvează toate setups în monitoring_setups.json
5. Trimite raport final Telegram
```

**⚠️ PUNCT CRITIC DE ORBIRE**: `debug=False` la linia 305. Când o pereche este respinsă, nu știi la ce strat. Poți vedea că USDCAD a picat, dar NU de ce.

---

### 👁️ `setup_executor_monitor.py` — WATCHDOG SETUPS (2050 linii)

**Scopul**: Rulează **non-stop**, verifică la fiecare 30 secunde dacă un setup MONITORING a primit confirmare 4H și trebuie executat.

**Logica V10.4**:
```
La fiecare 30s:
  1. Citește monitoring_setups.json
  2. Pentru fiecare setup cu status=MONITORING:
     a. Descarcă 4H recent de la cTrader :8767
     b. Verifică: există CHoCH 4H în direcția D1 bias?
     c. Verifică: CHoCH are body closure (nu doar wick)?
     d. Dacă DA → status = READY → apelează execute_trade()
  3. Trimite Telegram notification
```

**Observație importantă**: Acest modul este al doilea "creier" al sistemului. El poate schimba un setup din MONITORING în READY independent de `daily_scanner.py`. Dar logica lui de detecție 4H CHoCH **poate diferi** de logica din `smc_detector.py` — potențial conflict de versiuni.

---

### ⚡ `ctrader_executor.py` — EXECUTORUL (898 linii)

**Scopul**: Primește un setup READY → calculează lot size → scrie în `signals.json` → cBot execută.

**Garda principală (linia 462)**:
```python
if status != 'READY':
    logger.warning(f"⛔ EXECUTION BLOCKED: {symbol} status is '{status}'")
    return  # MONITORING nu ajunge NICIODATĂ la piață
```

**Pipeline execuție**:
```
execute_trade(symbol, direction, entry, sl, tp, lot_size, status='READY')
  │
  ├─ STEP 1: status != READY → BLOCAT (log + return)
  │
  ├─ STEP 1.5: V8.0 SL/TP ZERO GUARD
  │   SL=0 sau TP=0 sau SL=entry sau TP=entry → REJECTED
  │
  ├─ STEP 2: UnifiedRiskManager.validate_new_trade()
  │   Calculează lot_size pe baza % din cont + corelații
  │   Dacă validation eșuează → REJECTED
  │
  ├─ STEP 3: V5.6 BULLETPROOF BTC DETECTION
  │   Dacă 'BTC' în symbol → forțează lot_size = 0.50 (hardcodat)
  │   Dacă lot_size < 0.01 → forțează la 0.01 (minimum broker)
  │
  ├─ STEP 4: Calculează pip_size + SL_pips + TP_pips
  │
  └─ STEP 5: Scrie signals.json atomic
              cBot citește la ~10s → BUY/SELL plasat pe piață
```

**⚠️ PUNCT CRITIC**: BTCUSD hardcodat la 0.50 lots. La un cont de $5,162 cu BTCUSD la $83,000, 0.50 lots = **$41,500 expunere** = **803% din cont**. Aceasta este o bombă cu ceas.

---

### 🛡️ `watchdog_monitor.py` — PAZNICUL (V4.0, 533 linii)

**Scopul**: Asigură că toate cele 6 procese critice rulează non-stop. Dacă un proces moare → repornire automată instantanee.

**Procese monitorizate**:
1. `setup_executor_monitor.py` — watchdog setups
2. `position_monitor.py` — tracker poziții deschise
3. `telegram_command_center.py` — comenzi /scan /status etc.
4. `realtime_monitor.py` — analiza 4H în timp real
5. `ctrader_sync_daemon.py` — sincronizare date broker
6. `news_calendar_monitor.py` — calendar economic

**Rolul în drumul unui setup**: **INDIRECT**. Watchdog NU participă la detectarea sau execuția setups. Rolul lui este să se asigure că procesele care fac asta sunt vii.

---

### 📁 Alte fișiere importante

| Fișier | Rol |
|--------|-----|
| `monitoring_setups.json` | **Memória sistemului** — setups active READY/MONITORING |
| `signals.json` | **Interfața cu cBot** — ordinele de executat |
| `trade_confirmations.json` | Confirmări de la cTrader după execuție |
| `pairs_config.json` | 16 perechi active + setări scanner |
| `trade_history.json` | 230 trades închise + date cont |
| `unified_risk_manager.py` | Calculul lot size pe baza riscului % |
| `ai_probability_analyzer.py` | Score ML 0-100 pentru fiecare setup |

---

## 4. DRUMUL UNUI SETUP — DE LA DATE LA BUTON

```
╔══════════════════════════════════════════════════════════════════════╗
║  ETAPA 1: COLECTARE DATE                                            ║
║  cTrader cBot HTTP :8767                                            ║
║  → D1: 100 bare (≈5 luni de date zilnice)                          ║
║  → H4: 200 bare (≈33 zile de date 4H)                              ║
║  → H1: 225 bare (≈9.4 zile de date 1H)                             ║
╠══════════════════════════════════════════════════════════════════════╣
║  ETAPA 2: ORCHESTRARE (daily_scanner.py)                           ║
║  run_daily_scan() → iterează 16 perechi                            ║
║  scan_single_pair() → descarcă + apelează creierul                 ║
╠══════════════════════════════════════════════════════════════════════╣
║  ETAPA 3: ANALIZA SMC (smc_detector.py → scan_for_setup())         ║
║                                                                      ║
║  STRAT 1 │ detect_choch_and_bos(df_daily)                          ║
║          │ → CHoCH = schimbare de trend (pattern HL+LH sau ±10%)   ║
║          │ → BOS = continuare trend (break swing nivel)            ║
║          │ NU există CHoCH sau BOS? → return None ⛔               ║
║          │                                                          ║
║  STRAT 2 │ BOS dominanță: 3+ consecutive BOS → momentum setup     ║
║          │ strategy_type = 'continuation' sau 'reversal'          ║
║          │                                                          ║
║  STRAT 3 │ CHoCH vs BOS recency: care e mai recent?               ║
║          │ latest_signal = cel mai recent semnal structural        ║
║          │                                                          ║
║  STRAT 4 │ determine_daily_trend(df_daily) → BULLISH / BEARISH    ║
║          │ Analiză 150 bare, ierarhia BOS macro                    ║
║          │                                                          ║
║  STRAT 5 │ CONTINUATION macro check                                ║
║          │ LONG CONTINUATION în macro BEARISH? → return None ⛔    ║
║          │ SHORT CONTINUATION în macro BULLISH? → return None ⛔   ║
║          │                                                          ║
║  STRAT 6 │ detect_fvg(df_daily, latest_signal, current_price)     ║
║          │ → Scaneaza ultimele 30 bare de la choch.index           ║
║          │ → Metodă 1: Corp FVG (gap între body[i-1] și body[i+1]) ║
║          │ → Metodă 2: Wick fallback dacă nu găsim corp FVG        ║
║          │ → Verifică mitigare (prețul a intrat în FVG deja?)      ║
║          │                                                          ║
║  STRAT 7 │ if not fvg: → return None ⛔ ★★★ KILLER PRINCIPAL ★★★  ║
║          │ "Nu există FVG pur 3 lumânări"                          ║
║          │ 5 perechi blocate AZI: USDCAD, USDCHF, AUDUSD,         ║
║          │ USDJPY, GBPNZD — FVG există dar nu în ultimele 30 bare ║
║          │                                                          ║
║  STRAT 8 │ MOMENTUM PATH: dacă 3+ BOS consecutive                 ║
║          │ → creează FVG sintetic din ultimele swing-uri           ║
║          │ → Sare peste validare echilibru                         ║
║          │                                                          ║
║  STRAT 9 │ calculate_equilibrium_continuity/reversal()            ║
║          │ → Calculează nivelul 50% Fibonacci al macro leg-ului    ║
║          │                                                          ║
║  STRAT 10│ validate_fvg_zone() cu buffer ±10%                     ║
║          │ BULLISH: FVG.bottom ≤ equilibrium×1.10 (zona discount)  ║
║          │ BEARISH: FVG.top ≥ equilibrium×0.90 (zona premium)      ║
║          │ CONTINUATION eșuează? → return None ⛔                  ║
║          │ REVERSAL eșuează? → continuăm (nepenalizat V10.4)       ║
║          │                                                          ║
║  STRAT 11│ calculate_fvg_quality_score() → scor 0-100             ║
║          │ Criterii: gap size + body dominance + consecutive + clarity║
║          │ XAUUSD: gap ≥ 0.15% + body ≥ 40% (separate logic)      ║
║          │ GBP: scor ≥ 60                                          ║
║          │ Rest: scor ≥ 40                                          ║
║          │ Sub prag? → return None ⛔                              ║
║          │                                                          ║
║  STRAT 12│ V4 Golden Zone scoring (BONUS, nu penalizare)          ║
║          │ BUY în 20-29.5% din range → quality_score ≥ 90         ║
║          │ SELL în 70.5-80% din range → quality_score ≥ 90        ║
║          │ Altfel: +5 puncte bonus dacă în zona corectă            ║
║          │                                                          ║
║  STRAT 13│ CONTINUITY FILTER                                       ║
║          │ BOS age ≤ 100 bare ȘI quality_score ≥ 40/55?           ║
║          │ NU? → return None ⛔                                    ║
║          │                                                          ║
║  STRAT 14│ price_approaching_fvg cu buffer 0.5%                   ║
║          │ BULLISH: price ≤ fvg.top + (fvg_size×0.5 sau price×0.005)║
║          │ BEARISH: price ≥ fvg.bottom - (fvg_size×0.5 sau price×0.005)║
║          │ Prea departe? → return None ⛔                          ║
║          │                                                          ║
║  STRAT 15│ 4H CHoCH detection (max 48 bare = 8 zile)              ║
║          │ Există CHoCH 4H în direcția D1 în ultimele 48 bare?    ║
║          │ NU → status = MONITORING 👁️ (nu return None!)           ║
║          │                                                          ║
║  STRAT 16│ D1 POI Validation (price within 300% of FVG size)      ║
║          │ Prețul e în raza de 3× FVG față de zona D1?            ║
║          │ NU → status = MONITORING 👁️                             ║
║          │                                                          ║
║  STRAT 17│ GBP 2-TF Filter: necesită și 1H CHoCH în FVG          ║
║          │ GBP + 4H CHoCH valid + df_1h existe + nu există 1H?    ║
║          │ → return None ⛔                                        ║
║          │                                                          ║
║  STRAT 18│ continuity_validated flag                               ║
║          │ Flag setat în Strat 13 — verificare finală             ║
║          │ False? → return None ⛔                                 ║
║          │                                                          ║
║  STRAT 19│ STATUS FINAL                                            ║
║          │ 4H CHoCH confirmat + D1 POI → READY 🔥                 ║
║          │ Altceva → MONITORING 👁️                                 ║
╠══════════════════════════════════════════════════════════════════════╣
║  ETAPA 4: POST-PROCESARE (daily_scanner.py)                        ║
║  → ML score calculat (ai_probability_analyzer.py)                  ║
║  → AI probability calculat                                          ║
║  → Grafic generat (chart_generator.py)                             ║
║  → Telegram trimis (ORICE setup: READY sau MONITORING)             ║
║  → Salvat în monitoring_setups.json                                ║
╠══════════════════════════════════════════════════════════════════════╣
║  ETAPA 5: POLLING 30s (setup_executor_monitor.py)                  ║
║  Citește monitoring_setups.json la fiecare 30 secunde              ║
║  Verifică în timp real dacă 4H CHoCH s-a format                    ║
║  Dacă DA → status = READY → apelează execute_trade()               ║
╠══════════════════════════════════════════════════════════════════════╣
║  ETAPA 6: EXECUȚIE (ctrader_executor.py)                           ║
║  execute_trade() verifică status='READY'                           ║
║  UnifiedRiskManager calculează lot_size                            ║
║  SL/TP ZERO GUARD verificare                                        ║
║  signals.json scris atomic                                          ║
╠══════════════════════════════════════════════════════════════════════╣
║  ETAPA 7: cTrader cBot (polling la ~10 secunde)                    ║
║  Citește signals.json → VALIDEAZĂ → BUY / SELL PLASAT 🎯           ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## 5. CELE 19 STRATURI DE FILTRE

### Tabel complet

| # | Strat | Condiție de eșec | Acțiune | Versiunea introdusă |
|---|-------|-------------------|---------|---------------------|
| 1 | CHoCH/BOS detection | Niciun semnal structural | `return None` | V1.0 |
| 2 | BOS dominanță | < 3 BOS consecutive | continuă cu type implicit | V2.0 |
| 3 | Recency CHoCH vs BOS | — | selectează `latest_signal` | V2.0 |
| 4 | Macro trend D1 | — | setează `current_trend` | V2.0 |
| 5 | Macro alignment check | LONG în BEARISH sau SHORT în BULLISH | `return None` | V3.0 |
| 6 | detect_fvg() | — | caută FVG în ultimele 30 bare | V1.0 |
| 7 | FVG existence check | `fvg is None` | `return None` ⛔ KILLER | V1.0 |
| 8 | MOMENTUM path | — | FVG sintetic din swing-uri | V8.0 |
| 9 | Equilibrium calculation | — | calculează 50% Fib | V8.0 |
| 10 | validate_fvg_zone ±10% | FVG nu e în Premium/Discount | `return None` (doar CONTINUATION) | V8.0 |
| 11 | FVG quality score | < 40 non-GBP / < 60 GBP | `return None` | V3.0 |
| 12 | V4 Golden Zone | — | bonus +5 sau quality≥90 | V9.0 |
| 13 | Continuity filter | bos_age > 100 SAU score < 40/55 | `return None` | V10.3 |
| 14 | Price proximity 0.5% | Prețul > 0.5% depărtat de FVG | `return None` | V10.5 |
| 15 | 4H CHoCH (max 48 bare) | Nu există CHoCH 4H recent | `status = MONITORING` | V3.0 |
| 16 | D1 POI validation 300% | Prea departe de D1 FVG | `status = MONITORING` | V10.3 |
| 17 | GBP 2-TF filter (1H) | GBP + lipsă confirmare 1H | `return None` | V3.0 |
| 18 | continuity_validated | Flag False | `return None` | V10.1 |
| 19 | Status final | — | READY vs MONITORING | V3.0 |

### Puncte de `return None` (ucidere completă a setup-ului)
**Straturi 1, 5, 7, 10(CONT), 11, 13, 14, 17, 18** = **9 puncte de moarte**

### Puncte de degradare la MONITORING
**Straturi 15, 16** = **2 puncte de amânare**

---

## 6. COMPARAȚIE V3.1 vs V10.5 vs V10.8

### V3.1 (commit `1f43732`) — CODUL PROFITABIL ($1k → $13.7k)

```
Filtre active: CHoCH/BOS → determine_daily_trend → detect_fvg → 
               quality_score ≥ 60 → price_approaching → 4H CHoCH → READY/MONITORING
               
TOTAL: ~7 filtre
Linii scan_for_setup: ~400
Return None points: ~4
```

### V10.5 — CODUL BLOCAT (înainte de sesiunile de fix)

```
Filtre active: CHoCH/BOS → BOS dominance → recency → determine_daily_trend →
               macro alignment (Premium/Discount 150 bare) → detect_fvg(30 bare) →
               FVG existence → momentum path → equilibrium → validate_fvg_zone ±10% →
               quality_score ≥ 40/55/60 → V4 Golden Zone → continuity filter →
               price proximity 0.5% → 4H CHoCH → D1 POI → GBP 1H → 
               continuity_validated → STATUS
               
TOTAL: 19 filtre
Linii scan_for_setup: ~1382
Return None points: 9
```

### V10.8 "THE CLEAN SLATE" — CODUL CURENT (după fix-uri)

```
Filtre RĂMASE active:
  ✅ CHoCH/BOS detection (structura de bază)
  ✅ BOS dominance → momentum path
  ✅ V10.7 BYPASS: dacă CHoCH mai recent ca BOS → REVERSAL imediat (fără Strong H/L gate)
  ✅ V10.8 CLEAN: macro trend check → DOAR continuation contra-trend e blocat
  ✅ detect_fvg cu lookback +20 bare PRE-semnal (V10.8)
  ✅ validate_fvg_zone: INFORMATIV ONLY — nu mai blochează (V10.8)
  ✅ FVG quality_score: ≥15 non-GBP | ≥45 GBP (V10.8, relaxat de la 40/60)
  ✅ Continuity filter: ≥15 non-GBP | ≥45 GBP (V10.8)
  ✅ Price proximity (informativ)
  ✅ 4H CHoCH → MONITORING dacă lipsă (nu return None)
  ✅ GBP 2-TF: date 1H lipsă = MONITORING, nu reject (V10.8)
  ✅ Daily P/D V4.0: bypass complet pentru MOMENTUM entries (V10.8)

Filtre ȘTERSE definitiv:
  🗑️ Blocul macro Premium/Discount 150 bare (82 linii) — V10.8
  🗑️ BOS Hierarchy Strong H/L gate pentru REVERSAL — V10.7
  🗑️ validate_fvg_zone return None (CONTINUATION și REVERSAL) — V10.8
  🗑️ Restricție FVG scan la ultimele 30 bare — V10.6
```

### Tabel comparativ complet

| Funcționalitate | V3.1 | V10.5 | V10.8 | Impact V10.8 |
|-----------------|------|-------|-------|--------------|
| FVG scan start | De la CHoCH, fără restricție | `min(choch, end-30)` | `max(0, choch-20)` — 20 bare ÎNAINTE | ✅ GBPUSD deblocat |
| Macro P/D 150 bare | ❌ Nu exista | ✅ Bloca REVERSAL | 🗑️ ȘTERS complet | ✅ Fără blocare macro |
| BOS Hierarchy gate | ❌ Nu exista | ✅ Bloca REVERSAL | 🗑️ ȘTERS complet | ✅ REVERSAL imediat |
| validate_fvg_zone | ❌ Nu exista | ✅ Bloca CONTINUATION | ℹ️ Informativ only | ✅ FVG-uri acceptate |
| FVG min_score non-GBP | 60 | 40 | **15** | ✅ USDCAD deblocat |
| FVG min_score GBP | 60 | 60 | **45** | ✅ GBPUSD mai permisiv |
| GBP 1H lipsă | ❌ Nu testa | REJECT dur | MONITORING | ✅ GBPUSD nu mai pică |
| Daily P/D V4.0 | ❌ Nu exista | Bloca PREMIUM LONG | Bypass momentum | ✅ GBPJPY deblocat |
| debug=True zilnic | ❌ | False | **True** | ✅ Vizibilitate totală |

---

## 7. ANALIZA TRADE HISTORY — CE A FUNCȚIONAT ȘI CE A UCIS CONTUL

### Perechi profitabile (de păstrat și optimizat)

| Pereche | Trades | Win Rate | Profit | Observație |
|---------|--------|----------|--------|------------|
| **AUDUSD** | 24 | 29% | **+$5,246** | WR mic dar RR mare (lots 1.0-5.67!) |
| **EURUSD** | 8 | **100%** | **+$4,340** | Perfectă — 8/8 câștiguri |
| **BTCUSD** | 17 | 59% | **+$2,239** | Solid, lot fix 0.50 |
| **GBPUSD** | 34 | 62% | **+$1,035** | Consistent |
| **EURJPY** | 10 | 50% | **+$861** | Decent |
| **GBPJPY** | 25 | 44% | **+$751** | Decent |
| **USDCAD** | 12 | 33% | **+$585** | WR mic dar RR decent |
| **XTIUSD** | 5 | **100%** | **+$579** | Perfectă — 5/5 câștiguri |

### Perechi distrugătoare (de evitat sau eliminat)

| Pereche | Trades | Win Rate | Pierdere | Cauza |
|---------|--------|----------|----------|-------|
| **XAUUSD** | 2 | 50% | **-$6,772** | Trade #156: -$6,787 SINGUR (XAUUSD SELL 0.30 lots, price a urcat 228 pips) |
| **USDCHF** | 17 | 12% | **-$1,979** | SELL repetat pe trend bullish. Lots mari (2.07). Setup greșit de fiecare dată |
| **USDJPY** | 27 | **0%** | **-$1,799** | **0% Win Rate pe 27 trades** — ZERO câștiguri. Tot SELL pe trend bullish |
| **NZDUSD** | 28 | 18% | **-$761** | WR 18% pe 28 trades — sistematic greșit |

### Autopsie XAUUSD (catastrofa care a tăiat contul pe jumătate)

```
Trade #155: XAUUSD SELL @ 4,983.85 → close 4,981.48 | lots=0.07 → +$14.49
             ↑ SUCCES MIC — botul a văzut că merge shortul pe gold
             
Trade #156: XAUUSD SELL @ 4,979.10 → close 5,207.30 | lots=0.30 → -$6,786.61
             ↑ CATASTROFĂ — 228 puncte mișcare adversă
             
Întrebare critică: De ce 0.30 lots pe o mișcare atât de mare?
→ UnifiedRiskManager a calculat 0.30 lots pe baza balanței de $13,746
→ La 0.30 lots XAUUSD, fiecare $1 de mișcare = $30 pierdere
→ XAUUSD a urcat $226 = $6,780 pierdere
→ Nu exista SL suficient de aproape SAU SL a eșuat
```

**Concluzie XAUUSD**: XAUUSD trebuie **eliminat din liste** sau lotul forțat la 0.01-0.05 maxim, exact ca BTCUSD (hardcodat 0.50 — dar BTCUSD e profitabil).

### Autopsie USDJPY (27 trades, 0% Win Rate)

```
Din cele 27 trades USDJPY, TOATE sunt SELL.
USDJPY a fost în trend BULLISH puternic în această perioadă.
Botul a detectat "CHoCH bearish" la fiecare retragere și a short-uit.
Rezultat: 27 pierderi consecutive.

Problema: detect_choch_and_bos() detecta false CHoCH bearish la fiecare
correcție a trendului bullish. V10.5 CHoCH fix (OR condition) NU rezolvă
complet această problemă — USDJPY are mișcări > 10% doar la crize majore.
```

### Pattern loturilor (scală îngrijorătoare)

```
Faza 1 (1k): lots = 0.06-0.14 (corect ~1% risc)
Faza 2 (1k-2k): lots = 0.07-0.13 (corect)
Faza 3 (5k-13k): lots = 0.50-5.67 (scalare agresivă — asta a generat profiturile)
Faza 4 (după peak): lots = 0.86-2.07 (prea mari pentru balanța redusă)
```

**Concluzie risk management**: UnifiedRiskManager calculează lots proportional cu balanța. Când balanța a scăzut de la $13k la $6k, lots-urile NU s-au redus suficient de repede. Trades #180-208 (USDJPY) cu 1.04 lots pe o balanță de $6,000 = **~17% risc per trade**.

---

## 8. PUNCTELE DE BLOCAJ — STAREA ÎNAINTE ȘI DUPĂ V10.8

### Tabel: ce bloca fiecare pereche și ce s-a rezolvat

| Pereche | Cauza blocajului (V10.5) | Strat | Fix aplicat (V10.8) | Rezultat |
|---------|--------------------------|-------|---------------------|----------|
| **GBPUSD** | BOS la bara 93/100 → doar 6 bare după BOS → zero FVG găsit | Strat 7 | `start_idx = max(0, choch.index - 20)` → scanăm și 20 bare înainte | ✅ **READY** |
| **GBPUSD** | Date 1H existente dar GBP 2-TF filter → REJECT dur | Strat 17 | Date 1H lipsă = MONITORING, nu reject | ✅ Deblocat |
| **USDCAD** | FVG găsit dar scor 17/100 < 40 (prag minim) | Strat 11 | `min_score = 15` (non-GBP) | ✅ **MONITORING** |
| **GBPJPY** | 5 BOS consecutive (MOMENTUM) dar Daily P/D V4.0 bloca LONG la 70% range | V4.0 P/D | Bypass `is_momentum_entry` | ✅ **READY** |
| **AUDUSD** | Blocul macro P/D 150 bare respingea REVERSAL în PREMIUM | Strat 5 | Bloc macro șters complet (V10.8) | ✅ Deblocat |
| **EURJPY** | BOS Hierarchy: CHoCH mai recent ca BOS dar Strong H/L gate bloca REVERSAL | V10.5 Hierarchy | Bypass: CHoCH > BOS index → REVERSAL imediat (V10.7) | ✅ Deblocat |

### Diagrama: flow înainte vs după

```
ÎNAINTE (V10.5) — de ce GBPUSD pica:
  BOS bearish @ bara 93/100
  → detect_fvg: start_idx = 93, scan 6 bare → 0 FVG
  → return None ⛔ "Nu există FVG pur 3 lumânări"

DUPĂ (V10.8) — de ce GBPUSD trece:
  BOS bearish @ bara 93/100
  → detect_fvg: start_idx = max(0, 93-20) = 73, scan 26 bare → FVG găsit!
  → FVG: 1.33989 - 1.34786 (score 50/100 ≥ 45 prag GBP) ✅
  → GBP 2-TF: 3 bearish CHoCH 4H confirmate ✅
  → Status: READY ✅
```

```
ÎNAINTE (V10.5) — de ce USDCAD pica:
  FVG: 1.37111 - 1.37316 găsit ✅
  Body Dominance: 20.6% → 0/30 pts
  Total score: 17/100 < 40 → return None ⛔

DUPĂ (V10.8) — de ce USDCAD trece:
  Același FVG: 1.37111 - 1.37316
  Total score: 17/100 ≥ 15 (noul prag) ✅
  → Status: MONITORING (asteaptă 4H CHoCH) ✅
```

```
ÎNAINTE (V10.5) — de ce GBPJPY pica:
  5x BOS bullish → MOMENTUM ENTRY ✅
  Daily P/D V4.0: prețul la 70.1% → PREMIUM zone
  → Buying in PREMIUM → return None ⛔

DUPĂ (V10.8) — de ce GBPJPY trece:
  5x BOS bullish → MOMENTUM ENTRY (is_momentum_entry=True)
  Daily P/D V4.0: `_is_momentum = True` → filtru sărit complet
  → Status: READY ✅
```

---

## 9. STAREA CURENTĂ A SCANERULUI (23 Mar 2026)

### Rezultat live după V10.8 (confirmat în test manual)

| Pereche | Tip | Direcție | Status | RR | Note |
|---------|-----|----------|--------|-----|------|
| **GBPUSD** | continuation | **SELL** | ✅ **READY** | 1:8.69 | FVG 1.33989-1.34786, prețul în FVG |
| **USDCAD** | continuation | **SELL** | ✅ **MONITORING** | 1:8.24 | FVG 1.37111-1.37316, asteaptă 4H CHoCH |
| **GBPJPY** | continuation | **BUY** | ✅ **READY** | 1:17.82 | MOMENTUM 5x BOS, Entry 207.785 |
| AUDJPY | continuation | BUY | MONITORING | — | Asteaptă 4H CHoCH |
| BTCUSD | reversal | BUY | MONITORING | — | Posibil false reversal |
| EURUSD | continuation | SELL | MONITORING | — | Asteaptă 4H CHoCH |
| AUDUSD | continuation | BUY | MONITORING | — | Asteaptă 4H CHoCH |
| EURGBP | continuation | SELL | MONITORING | — | Asteaptă 4H CHoCH |
| EURJPY | continuation | SELL | MONITORING | — | Asteaptă 4H CHoCH |

### Poziții deschise active (cTrader, 23 Mar 2026)
```
• USDJPY - SHORT @ 157.613 | Vol: 132,000
• USDCAD - SHORT @ 1.37364 | Vol: 103,000
• BTCUSD - LONG  @ 73,243.21 | Vol: 0.50
```

---

## 10. JURNAL COMPLET MODIFICĂRI V10.6 → V10.8

> Toate modificările sunt în `smc_detector.py` dacă nu e specificat altfel.

---

### 🔧 V10.6 — "MEMORIA TOTALĂ + BODY CLOSE"

#### Fix #1 — `detect_fvg()`: eliminat limita de 30 bare
```python
# ÎNAINTE:
start_idx = min(raw_start, max(0, end_idx - 30))  # limita artificială 30 bare

# DUPĂ:
start_idx = raw_start  # MEMORIA TOTALĂ: fără min(raw, end-30)
```
**Motivul**: Scanatorul vedea CHoCH la bara 40 dar FVG la bara 35 → picat. Acum scanează toată seria de la CHoCH.index → prezent.

#### Fix #2 — `detect_swing_highs/lows()`: ATR multiplier 1.2 → 0.3 + body_close
```python
# ÎNAINTE: atr_multiplier=1.2 (swing-uri rare, greu de detectat)
# DUPĂ: atr_multiplier=0.3 (mai mulți swing high/low detectați, mai sensibil)
# ADĂUGAT: body_close_confirms=True (confirmarea cu închiderea corpului, nu wick)
```

#### Fix #3 — `validate_fvg_zone()`: buffere extinse
```python
# BEARISH: equilibrium * 0.80  (era 0.90)
# BULLISH: equilibrium * 1.20  (era 1.10)
```

#### Fix #3b — STATUS LOGIC 55/45 în `scan_for_setup()`
```python
# Setup READY dacă prețul a retras cel puțin 55% (bullish) / 45% (bearish) din impulse
if current_trend == 'bullish':
    retracement_ready = _pct_from_low <= 55.0
else:
    retracement_ready = _pct_from_low >= 45.0
```

#### Fix #4 — `get_4h_body_close_confirmation()` funcție unificată
- Adăugată la finalul `smc_detector.py`
- Import actualizat în `setup_executor_monitor.py`
- Blocul de detecție 4H înlocuit cu apel unificat

#### Fix #5 — `debug=True` în `daily_scanner.py`
- Ambele apeluri `scan_for_setup()` din `daily_scanner.py` au acum `debug=True`
- **Motivul**: fără debug, când o pereche pica nu știam la ce strat

---

### 🔧 V10.7 — "THE FINAL UNLOCK"

#### Fix principal — Eliminat BOS Hierarchy Strong H/L gate
**Problema**: Botul detecta CHoCH (semnal de REVERSAL) dar îl bloca dacă prețul nu depășea nivelul Strong High/Low — cerință care anula complet semnalul CHoCH.

```python
# ÎNAINTE (V10.5): BOS Hierarchy gate bloca REVERSAL
if latest_choch and latest_bos:
    if latest_choch.index > latest_bos.index:
        # Trebuia să mai treacă de Strong H/L check → bloca REVERSAL
        if not price_broke_strong_level:
            latest_signal = latest_bos  # Forța CONTINUATION în loc de REVERSAL
            
# DUPĂ (V10.7): Bypass imediat
if latest_choch and latest_bos and latest_choch.index > latest_bos.index:
    # CHoCH mai recent ca BOS → REVERSAL IMEDIAT (fără Strong H/L gate)
    latest_signal = latest_choch
    strategy_type = 'reversal'
    current_trend = latest_choch.direction
else:
    latest_signal = latest_bos
    strategy_type = 'continuation'
    current_trend = dominant_bos_direction
```

---

### 🔧 V10.8 — "THE CLEAN SLATE"

#### Fix #1 — Șters blocul macro Premium/Discount (82 linii → 28 linii)
**Blocul șters** genera reject-uri de tip:
- `REJECT: Buying in PREMIUM zone pe AUDUSD la 93.1%`
- `REJECT: DAILY TREND LOCK`
- `REJECT: SHORT CONTINUATION în macro BULLISH D1`

**Înlocuit cu**:
```python
# ━━━ V10.8 CLEAN SLATE ━━━
# FILTRUL PREMIUM/DISCOUNT MACRO (150 bare) A FOST ȘTERS DEFINITIV.
# SINGURUL bloc rămas: CONTINUATION contra-trend macro
if strategy_type == 'continuation':
    if overall_daily_trend == 'bearish' and current_trend == 'bullish':
        return None  # ONLY: long continuation în macro bearish
    elif overall_daily_trend == 'bullish' and current_trend == 'bearish':
        return None  # ONLY: short continuation în macro bullish
# REVERSAL: NICIODATĂ blocat de macro zone
```

#### Fix #2 — `validate_fvg_zone` → informativ only
```python
# ÎNAINTE: return None dacă FVG nu era în zona corectă (bloca CONTINUATION)
# DUPĂ: doar print informativ, niciun return None
if not is_valid_zone:
    print(f"[V10.8 INFO: FVG în afara zonă {zone_name}...]")
    # ✅ V10.8: NICIUN return None — ambele strategii continuă
```

#### Fix #3 — FVG min_score: 40 → 15 (non-GBP), 60 → 45 (GBP)
```python
# ÎNAINTE:
min_score = 60  # GBP
min_score = 40  # non-GBP

# DUPĂ:
min_score = 45  # GBP (V10.8)
min_score = 15  # non-GBP (V10.8) — USDCAD score=17 acum trece
```
**Motivul**: USDCAD avea FVG cu scor 17/100 (body dominance 20.6% → 0/30 pts). Cu pragul la 40, era respins. Scorul mic reflecta o lumânare slabă, nu un FVG fals.

#### Fix #4 — `detect_fvg()`: lookback +20 bare PRE-BOS
```python
# ÎNAINTE:
start_idx = raw_start  # Scana DUPĂ BOS/CHoCH

# DUPĂ (V10.8):
start_idx = max(0, raw_start - 20)  # 20 bare ÎNAINTE de BOS incluse
```
**Motivul**: GBPUSD avea BOS la bara 93 din 100 → doar 6 bare disponibile → zero FVG. Cu lookback de 20 bare, scanăm din bara 73 → FVG găsit la bara 78.

#### Fix #5 — GBP 2-TF filter: date 1H lipsă = MONITORING, nu REJECT
```python
# ÎNAINTE:
elif df_1h is None:
    print(f"⛔ REJECTED: GBP — date 1H lipsă")
    gbp_confirmed = False  # → return None

# DUPĂ (V10.8):
elif df_1h is None:
    # Dacă 1H date lipsesc, NU respingem — continuăm cu MONITORING
    gbp_confirmed = True  # lipsă date 1H ≠ reject, = MONITORING
```

#### Fix #6 — Daily P/D V4.0: bypass pentru MOMENTUM entries
```python
# ÎNAINTE: bloca LONG dacă prețul era în top 30% din range zilnic
if current_trend == 'bullish' and premium_discount['zone'] == 'PREMIUM':
    return None  # Bloca GBPJPY MOMENTUM la 70.1%

# DUPĂ (V10.8):
_is_momentum = hasattr(fvg, 'is_momentum_entry') and fvg.is_momentum_entry
if not skip_fvg_quality and not _is_momentum:
    # filtrul se aplică DOAR pentru non-momentum entries
    ...
elif _is_momentum:
    pass  # MOMENTUM = breakout, P/D zilnic irrelevant
```

#### Fix #7 — Continuity filter: prag actualizat la 15/45
```python
# ÎNAINTE: min_quality_for_cont = 55 (GBP) / 40 (non-GBP)
# DUPĂ:    min_quality_for_cont = 45 (GBP) / 15 (non-GBP)
```

---

### Fișiere modificate în V10.6 → V10.8

| Fișier | Modificări |
|--------|-----------|
| `smc_detector.py` | 7 fix-uri majore (toate listate mai sus) |
| `setup_executor_monitor.py` | Import `get_4h_body_close_confirmation`, bloc 4H unificat |
| `daily_scanner.py` | `debug=True` la ambele apeluri `scan_for_setup()` |

---

## 11. RECOMANDĂRI RĂMASE

### 🔴 Prioritate înaltă — XAUUSD (bombă cu ceas activă)
```
2 trades în istoric: +$14 și -$6,786 → Net: -$6,772
```
XAUUSD trebuie **eliminat din `pairs_config.json`** sau lot maxim forțat la 0.03. O singură tranzacție a tăiat contul cu 49.3%.

### 🟡 Prioritate medie — USDJPY (0% Win Rate, 27 trades)
Toate cele 27 trades au fost SELL pe trend BULLISH. Sistemul detecta false CHoCH bearish la fiecare retragere. Recomandat: eliminat temporar din lista de scanat sau adăugat filtru minim 2% pentru CHoCH bearish pe JPY.

### 🟡 Prioritate medie — Continuity filter Strat 13 + Strat 18 (logică duplicată)
Aceleași condiții verificate de două ori. Poate fi fuzionat într-un singur bloc.

### 🟢 Prioritate scăzută — Lot maxim per pereche în `pairs_config.json`
Adăugare câmp `max_lot` per pereche, care să suprascrie calculul `UnifiedRiskManager` atunci când volatilitatea e extremă (JPY, XAU, BTC).

---

## REZUMAT EXECUTIV

```
╔══════════════════════════════════════════════════════════════════╗
║  PROBLEMA CENTRALĂ (V10.5)                                      ║
║  V3.1 (7 filtre)  → $1k la $13.7k în 154 trades                ║
║  V10.5 (19 filtre) → $13.7k la $5.1k în 76 trades              ║
║  Sistemul nu era stricat — era sufocat de supraprotecție         ║
╠══════════════════════════════════════════════════════════════════╣
║  CE AM REZOLVAT ÎN V10.6 → V10.8                                ║
║  ✅ FVG scan extins: +20 bare pre-BOS (GBPUSD deblocat)         ║
║  ✅ FVG min_score: 40 → 15 (non-GBP), 60 → 45 (GBP)            ║
║  ✅ Bloc macro P/D 150 bare ȘTERS (82 linii eliminate)          ║
║  ✅ BOS Hierarchy gate ȘTERS (REVERSAL nu mai e blocat)          ║
║  ✅ validate_fvg_zone: informativ only (nu mai killează)         ║
║  ✅ GBP 1H lipsă: MONITORING în loc de REJECT                   ║
║  ✅ MOMENTUM entries: bypass daily P/D V4.0 (GBPJPY deblocat)   ║
║  ✅ debug=True în scanner: vizibilitate completă                 ║
╠══════════════════════════════════════════════════════════════════╣
║  REZULTAT CONFIRMAT LIVE (23 Mar 2026)                          ║
║  GBPUSD  → ✅ READY  (era: REJECT FVG 6 bare insuficiente)      ║
║  USDCAD  → ✅ MONITORING (era: REJECT score 17 < 40)            ║
║  GBPJPY  → ✅ READY  (era: REJECT BUYING IN PREMIUM 70%)        ║
╠══════════════════════════════════════════════════════════════════╣
║  ACȚIUNI RĂMASE                                                  ║
║  1. Elimina XAUUSD din pairs_config.json → previne catastrofă   ║
║  2. Elimina/suspendă USDJPY (0% WR pe 27 trades)               ║
║  3. Fuzionează Strat 13 + 18 (duplicate logice)                 ║
╚══════════════════════════════════════════════════════════════════╝
```

---

*Document actualizat: 23 Martie 2026 — V10.8 "THE CLEAN SLATE"*  
*Bazat pe: smc_detector.py (~4958 linii), daily_scanner.py (778 linii), ctrader_executor.py (898 linii), setup_executor_monitor.py (2050 linii), trade_history.json (230 trades)*  
*🏛️ Глитч Ин Матрикс 🏛️*
