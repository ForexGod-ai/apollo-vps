# 📋 CHANGELOG — Sesiunea 2026-04-08
## "Regula Generalului" — V12.1 → V13.2 Fix USDCHF + Hetzner Migration

---

## 🔴 FIX CRITIC: `smc_detector.py` — calculate_entry_sl_tp() V13.2

### Context (de ce a fost nevoie)
- **Trade pierdut**: SHORT USDCHF pe 2026-04-07
- **Direcție**: ✅ Corectă (bearish)
- **Stop-out**: SL de 16.1 pips — scos din zgomot intraday
- **Generalul structural** (Swing High major 4H) era mult mai sus (~80 pips deasupra)
- **Root cause**: `highs_before_choch[-1]` selecta ULTIMUL fractal (cel mai recent index), NU cel mai înalt wick structural

---

### Bug 1 — SHORT branch SL (linia ~2376 → acum ~2393)

**ÎNAINTE (V12.1 — BUGGY):**
```python
# ── V12.1 SL STRUCTURAL 4H: ultimul swing High pe 4H ÎNAINTE de CHoCH ────
...
if highs_before_choch:
    last_swing_high = highs_before_choch[-1]           # ← [-1] = RECENT, nu structural!
    stop_loss = df_4h['high'].iloc[last_swing_high.index] + sl_buffer
    print(f"   🛡️ [V12.1 SL] Ultimul swing High 4H înainte CHoCH: ...")
else:
    ...Body max 40-bar...
    print(f"   🛡️ [V12.1 SL FALLBACK] Body max 40-bar window: ...")
```

**DUPĂ (V13.2 — FIX):**
```python
# ── V13.2 SL STRUCTURAL 4H: cel mai înalt WICK din TOATE swing-urile ÎNAINTE de CHoCH ────
# FIX USDCHF 2026-04-07: [-1] = ultimul fractal RECENT, NU Generalul!
...
if highs_before_choch:
    # V13.2 FIX: MAX wick HIGH = GENERALUL
    general_wick_high = max(df_4h['high'].iloc[sh.index] for sh in highs_before_choch)
    stop_loss = general_wick_high + sl_buffer
    general_sh_obj = max(highs_before_choch, key=lambda sh: df_4h['high'].iloc[sh.index])
    sl_distance_pips = abs(stop_loss - entry) / pip_size
    print(f"   🛡️ [V13.2 SL GENERALUL SHORT] Cel mai înalt swing High 4H pre-CHoCH: ...")
    # REGULA DE FIER: dacă SL > 100 pips → REJECT
    _max_sl_pips = 200 if 'JPY' in symbol else 100
    if sl_distance_pips > _max_sl_pips:
        print(f"   ⛔ [V13.2 REJECT: SL distanță {sl_distance_pips:.1f} pips > {_max_sl_pips} max] ...")
        return None, None, None
else:
    ...Body max 40-bar...
    print(f"   🛡️ [V13.2 SL FALLBACK] Body max 40-bar window: ...")
```

---

### Bug 2 — LONG branch SL (linia ~2299 → acum ~2299, simetric)

**ÎNAINTE (V12.1 — BUGGY):**
```python
# ── V12.1 SL STRUCTURAL 4H: ultimul swing Low pe 4H ÎNAINTE de CHoCH ────
...
if lows_before_choch:
    last_swing_low = lows_before_choch[-1]             # ← [-1] = RECENT, nu structural!
    stop_loss = df_4h['low'].iloc[last_swing_low.index] - sl_buffer
    print(f"   🛡️ [V12.1 SL] Ultimul swing Low 4H înainte CHoCH: ...")
```

**DUPĂ (V13.2 — FIX):**
```python
# ── V13.2 SL STRUCTURAL 4H: cel mai scăzut WICK din TOATE swing-urile ÎNAINTE de CHoCH ────
...
if lows_before_choch:
    # V13.2 FIX: MIN wick LOW = GENERALUL
    general_wick_low = min(df_4h['low'].iloc[sl.index] for sl in lows_before_choch)
    stop_loss = general_wick_low - sl_buffer
    general_sl_obj = min(lows_before_choch, key=lambda sl: df_4h['low'].iloc[sl.index])
    sl_distance_pips = abs(entry - stop_loss) / pip_size
    print(f"   🛡️ [V13.2 SL GENERALUL LONG] Cel mai scăzut swing Low 4H pre-CHoCH: ...")
    _max_sl_pips = 200 if 'JPY' in symbol else 100
    if sl_distance_pips > _max_sl_pips:
        print(f"   ⛔ [V13.2 REJECT: SL distanță {sl_distance_pips:.1f} pips > {_max_sl_pips} max] ...")
        return None, None, None
```

---

### Bug 3 — Print final + calcul pip incorect (linia ~2472)

**ÎNAINTE:**
```python
print(f"✅ [V11.2 EXTREME VISION] {symbol} ...")
print(f"   📐 SL dist={abs(entry-stop_loss)/entry*10000:.1f} pips | TP dist=...")
#                                   ^^^ GREȘIT: împărțea la ENTRY (float mare), nu la pip_size!
```

**DUPĂ:**
```python
print(f"✅ [V13.2 GENERALUL] {symbol} ...")
pip_size_final = 0.01 if 'JPY' in symbol else 0.0001
print(f"   📐 SL dist={abs(entry-stop_loss)/pip_size_final:.1f} pips | TP dist=...")
#                                   ^^^ CORECT: divide la pip_size real
```

---

### Bug 4 — FALLBACK2 print labels

**ÎNAINTE:** `[V12.1 SL FALLBACK2]` (ambele LONG și SHORT)  
**DUPĂ:** `[V13.2 SL FALLBACK2]` (ambele LONG și SHORT)

---

### Regula de Fier adăugată (nouă, nu exista)

```
JPY:    max SL = 200 pips (100 pips = 1.00 unit — scala JPY diferită)
Non-JPY: max SL = 100 pips
Dacă Generalul e > limită → return None, None, None (trade ANULAT, nu strânge SL)
```

**Logica din spatele regulii:**
- SL 100 pips cu RR 1:4 → TP = 400 pips → rar atins structural
- Mai bine fără trade decât cu SL artificial strâns în zgomot
- La USDCHF: SL 96 pips (Generalul real) → acceptat; nu 16 pips (fractal minor) → respins cu noul fix

---

## 🟡 FIX MINOR: `daily_scanner.py`

### Duplicate import os (linia 869)

**ÎNAINTE:** `import os` exista atât la linia 10 cât și linia 869  
**DUPĂ:** Linia 869 eliminată — `import os` rămâne doar la linia 10

---

## 🟢 INFRASTRUCTURE UPDATE: Hetzner CPX41 Migration

### Fișiere actualizate

#### `WINDOWS_VPS_DEPLOYMENT_GUIDE.md`
- **Section 2**: Specificații actualizate Vultr → **Hetzner CPX41**
  - 8vCPU AMD EPYC / 16GB RAM / 240GB NVMe SSD / ~€28/mo
- **Pasul 2B**: Procedura ISO mounting via Hetzner Console VNC (nou)
- **Section 3B**: MAX PERFORMANCE MODE adăugat:
  - `cache_aggressive = True`
  - `ThreadPoolExecutor(max_workers=4)`
  - DEBUG logging: 90 zile retenție / 50MB rotation / zip compresie

#### `AUDIT_FINAL_100_PERCENT.md`
- Header actualizat: specificații Hetzner CPX41
- Check 2 actualizat: MAX PERFORMANCE MODE inclus
- VPS Box actualizat cu full deploy sequence pentru Hetzner

#### `vps_deploy_windows.ps1`
- Header comment actualizat: `Hetzner CPX41, 8vCPU AMD EPYC / 16GB RAM / 240GB NVMe`
- Banner ASCII actualizat cu noile specificații

---

## ✅ Verificare Finală

```
$ python3 -c "import ast; ast.parse(open('smc_detector.py').read()); print('OK')"
✅ smc_detector.py — SYNTAX OK, no errors
```

**Grep confirmare — zero urme V12.1/V11.2:**
```
grep "V12.1 SL" smc_detector.py     → No matches found ✅
grep "V11.2"    smc_detector.py     → No matches found ✅
grep "V13.2 GENERALUL"              → 5 matches (LONG, SHORT, REJECT×2, print final) ✅
```

---

## 📊 Sumar Impact

| Fișier | Tip modificare | Severitate |
|--------|---------------|------------|
| `smc_detector.py` | Bug fix SL SHORT (max wick) | 🔴 CRITIC |
| `smc_detector.py` | Bug fix SL LONG (min wick) | 🔴 CRITIC |
| `smc_detector.py` | 100-pip hard guard (nou) | 🟠 IMPORTANT |
| `smc_detector.py` | Print labels + pip calc fix | 🟡 MINOR |
| `daily_scanner.py` | Duplicate import os eliminat | 🟢 CLEANUP |
| `WINDOWS_VPS_DEPLOYMENT_GUIDE.md` | Hetzner specs + MAX PERF | 🟢 INFRA |
| `AUDIT_FINAL_100_PERCENT.md` | Hetzner update | 🟢 INFRA |
| `vps_deploy_windows.ps1` | Hetzner header update | 🟢 INFRA |

---

*Generat: 2026-04-08 | V13.2 GENERALUL*

---

---

## 🔴 TASK 2 — `news_calendar_monitor.py` V12.2 → V13.2 VOLATILITY RADAR

**Trigger:** Alertă Telegram FOMC primită cu ora greșită + request eliminare bariere trading

---

### Modificare 1 — Format Sniper Alert complet rescris (BLACKOUT → Matrix Hunting)

**ÎNAINTE:**
```
⚠️ HIGH IMPACT NEWS ALERT
────────────────
📊 EVENIMENT: FOMC Meeting Minutes
🌍 CCY: 🇺🇸 USD
⏱️ START: PESTE 15 MINUTE (21:00 EET)
🚫 STATUS: BLACKOUT ZONE
```

**DUPĂ (V13.2):**
```
⚡ VOLATILITY RADAR
━━━━━━━━━━━━━━
📅 Event: FOMC Meeting Minutes
🌍 Impact: 🇺🇸 USD
⏳ Timer: 15 Minutes
🏛️ Status: Matrix Hunting
━━━━━━━━━━━━━━
🔱 AUTHORED BY ФорексГод 🔱
🏛️ Глитч Ин Матрикс 🏛️
```

---

### Modificare 2 — Eliminat barierele de trading din `format_telegram_message()`

**Eliminat:**
- `"⚠️ Avoid 30min before"` din header
- Blocul `🎯 *PROTOCOL:*` complet (reducere size 50%, Close 30m before, SL to BE)
- `"🟠 MODERATE\n• Watch news times\n• SL to BE before\n"`
- `"🔴 HIGH VOL\n• Reduce size 50%\n• Close 30m before\n"`
- `"🟢 NORMAL\n• Avoid 30m before\n"`

**Înlocuit cu:**
```
🏛️ Matrix Hunting 24/7
```

---

### Modificare 3 — Eliminat REGULA DE AUR din WAR MAP

**Eliminat:**
```
🚫 REGULA DE AUR: Niciun ordin deschis cu 15 min înainte.
```

**Înlocuit cu:**
```
⚡ Matrix Hunting 24/7 — Știrile sunt combustibil.
```

---

### Modificare 4 — Fix Timezone FOMC (bug ora greșită)

**Problema:** `economic_calendar.json` stoca orele ca UTC, dar codul le trata tot ca UTC și le converti: `21:00 UTC → 23:00 EET` → alertă primită la 20:45 EET pentru un eveniment aparent la 22:45 EET — GREȘIT.

**Fix aplicat:**
```python
# ÎNAINTE (BUGGY):
event_date = self.utc_tz.localize(event_date).astimezone(self.local_tz)
# Rezultat: FOMC 19:00 UTC → 21:00 EET corect dacă JSON e UTC
# DAR dacă JSON stochează EET direct (21:00), atunci 21:00 "UTC" → 23:00 EET ← GREȘIT

# DUPĂ (V13.2 FIX):
tz_field = e.get('tz', 'EET').upper()   # default EET
if tz_field == 'UTC':
    event_date = self.utc_tz.localize(event_date).astimezone(self.local_tz)
else:
    event_date = self.local_tz.localize(event_date)  # ora din JSON = ora EET direct
```

**Regula acum:** Dacă vrei UTC în JSON, adaugă `"tz": "UTC"` explicit la eveniment. Default = EET.

---

### Modificare 5 — Fix ForexFactory date parser (year boundary bug)

**ÎNAINTE:**
```python
current_date = datetime.strptime(f"{date_str} {datetime.now().year}", "%a %b %d %Y")
# Bug: dacă scrape-ul e pe 31 Dec 23:59 și evenimentul e pe 1 Ian → an greșit
```

**DUPĂ:**
```python
# FIX V13.2: use fetch_date.year NOT datetime.now().year
current_date = datetime.strptime(f"{date_str} {fetch_date.year}", "%a %b %d %Y")
# fetch_date = data exactă care se scrape-uiește → corectă indiferent de boundary
```

---

### Modificare 6 — Header/versiune actualizat

| Unde | Înainte | După |
|------|---------|------|
| Docstring modul | `V2.0 Features` | `V13.2 Features` |
| `run_daemon()` banner | `V12.2 — INTELLIGENCE PREEMPTIV` | `V13.2 — VOLATILITY RADAR` |
| Log sniper sent | `⚠️ SNIPER ALERT sent:` | `⚡ VOLATILITY RADAR sent:` |
| Ora log | fără EET | `@ {tstr} EET` |

---

### Verificare finală

```
$ python3 -c "import ast; ast.parse(open('news_calendar_monitor.py').read()); print('OK')"
✅ news_calendar_monitor.py — SYNTAX OK

grep "BLACKOUT ZONE|Avoid 30min|Reduce size|REGULA DE AUR" → No matches ✅
grep "VOLATILITY RADAR"   → 6 matches ✅
grep "Matrix Hunting"     → 3 matches ✅
grep "fetch_date.year"    → 2 matches ✅
grep "tz_field"           → 2 matches ✅
```

---

*Task 2 complet: 2026-04-08 | V13.2 VOLATILITY RADAR*

---

---

## 🔴 TASK 3 — `setup_executor_monitor.py` — Fix SL Executor (V13.2 Generalul Propagation)

**Trigger:** Audit End-to-End a descoperit că executorul **ignora** SL-ul structural din setup și recalcula un SL de 10 pips fix din marginea FVG — exact același bug ca USDCHF, dar în executor.

### Riscul descoperit

Când executorul intra în modul SNIPER (1H FVG) sau HIGH CONFIDENCE (4H FVG):
```python
# ❌ BUGGY (vechi):
sniper_sl = radar_1h_fvg_bottom - (10 * 0.0001)  # 10 pips fix — ignoră Generalul!
# Rezultat: SL de 10 pips în loc de SL structural din smc_detector.py V13.2
# Pe JPY: 10 * 0.0001 = 0.001 JPY pips → SL practic = 0!
```

### Fix aplicat — ambele ramuri (SNIPER 1H + HIGH CONFIDENCE 4H)

```python
# ✅ V13.2 FIX:
pip_size_exec = 0.01 if 'JPY' in symbol.upper() else 0.0001
structural_sl = setup.get('stop_loss')  # Generalul din smc_detector.py V13.2

if structural_sl and structural_sl != 0.0:
    stop_loss = structural_sl  # SL structural = PRIORITAR
    logger.info(f"🛡️ [V13.2 GENERALUL] Using structural SL: {stop_loss:.5f} ({sl_pips:.1f} pips)")
else:
    stop_loss = fallback_sl    # 10-pip fallback DOAR dacă SL lipsește din JSON
    logger.warning(f"⚠️ [V13.2 FALLBACK] Structural SL missing — using FVG 10-pip: {stop_loss:.5f}")
```

### Fișiere modificate
| Fișier | Linie | Modificare |
|--------|-------|------------|
| `setup_executor_monitor.py` | ~772 | SNIPER 1H: `sniper_sl = 10*0.0001` → `structural_sl = setup.get('stop_loss')` |
| `setup_executor_monitor.py` | ~820 | 4H HIGH CONF: `sniper_sl = 10*0.0001` → `structural_sl = setup.get('stop_loss')` |
| Ambele | — | JPY pip_size fix: `0.0001` → `0.01 if 'JPY' in symbol else 0.0001` |
| Ambele | — | Eliminat `use_sniper_sl` / `pullback_config` toggle — nu mai e nevoie de toggle |

---

*Task 3 complet: 2026-04-08 | Executor V13.2 GENERALUL*

---

## 🕐 TASK 5 — Deployment Live: Romania Time Sync + Rollover Pause + BTC Lot Fix

### V14.0 — `unified_risk_manager.py` + `SUPER_CONFIG.json`

---

### 5.1 — Romania Time Sync

**Problemă**: Resetul zilnic folosea UTC (`timezone.utc`). Pe Hetzner (UTC server), ziua se schimba la ora **02:00 EET** iarnă / **03:00 EET** vară — incorect față de miezul nopții românesc.

**Fix aplicat**:
- Adăugat import `pytz` cu `TZ_RO = pytz.timezone('Europe/Bucharest')`
- Fallback graceful dacă `pytz` nu este instalat: `UTC+3`
- Adăugate metode helper: `_today_ro()` și `_now_ro()` — folosite în toate comparațiile de dată
- `_load_daily_state()`: `today = self._today_ro()` în loc de `datetime.now(timezone.utc).date()`
- `_save_daily_state()`: `today = self._today_ro()`
- `_reset_daily_state()`: `reset_timestamp` = EET, câmp nou `'timezone': 'Europe/Bucharest'`
- `daily_state.json` acum conține timestamp EET explicit

---

### 5.2 — Mandatory Rollover Pause 00:00 – 01:05 EET

**Problemă**: Executorul putea trimite ordine la miezul nopții românesc, exact în fereastra de rollover când spread-urile sunt extreme (uneori 30–50 pips).

**Fix aplicat** în `validate_new_trade()` — primul check, înainte de orice altceva:
```python
# V14.0 MANDATORY ROLLOVER PAUSE — 00:00 → 01:05 EET
now_ro = self._now_ro()
ro_hour, ro_minute = now_ro.hour, now_ro.minute
in_rollover = (ro_hour == 0) or (ro_hour == 1 and ro_minute < 5)
if in_rollover:
    result['reason'] = f"Rollover pause: 00:00–01:05 EET (now {ro_hour:02d}:{ro_minute:02d} EET)"
    return result  # ← BLOCKED, nu Deep Sleep
```

- **Scannerul rămâne activ** — detectează setup-uri dar nu le execută
- Nu generează Telegram spam (return silențios fără `_send_rejection_alert`)
- `SUPER_CONFIG.json` actualizat: `rollover_window_eet_start: "00:00"`, `rollover_window_eet_end: "01:05"`

---

### 5.3 — BTCUSD Dynamic Lot Size (eliminat bypass)

**Problemă**: BTC avea `lot_size = 0.50` hardcodat și sărea peste **toate** verificările de risc (daily loss, max positions, duplicate guard).

**Root cause**: Blocul de calcul folosea `pip_value = 0.01` (model IC Markets micro-lot), greșit pentru cTrader unde **1 lot BTC = 1 BTC** și P&L = `lot × SL_distance`.

**Fix aplicat**:

| | ÎNAINTE (V8.1 bypass) | DUPĂ (V14.0 dinamic) |
|---|---|---|
| BTC lot | `0.50` fix | `risk_amount / sl_distance` dinamic |
| pip_size | `1.0` | `1.0` ✅ |
| pip_value | `0.01` ❌ | `1.0` ✅ (cTrader: 1$ move = $1 P&L/lot) |
| Risk checks | **SĂRITE** | **APLICATE** (daily loss, max positions etc.) |
| Rollover | **SĂRIT** | **BLOCAT** ca orice alt simbol |

**Formula BTC**: `lot_size = risk_amount / sl_distance_USD`

Exemplu: `$230 risc / $2000 SL distanță = 0.115 loturi` → rotunjit la `0.12`

---

### 5.4 — Telegram SYSTEM RESET (minimalist)

**Problemă**: Mesajul `🔱 SYSTEM AWAKENED` era verbos (8 linii + branding footer).

**Format nou** (exact cum a cerut ФорексГод):
```
🏛️ SYSTEM RESET
━━━━━━━━━━━━━━
📅 New Day: 08 Apr 2026
💰 Equity: $4519.00
🛡️ Status: Ready & Hunting
```

---

### Fișiere modificate

| Fișier | Modificare |
|--------|------------|
| `unified_risk_manager.py` | Import `pytz` + `TZ_RO` |
| `unified_risk_manager.py` | `_today_ro()` + `_now_ro()` helper methods |
| `unified_risk_manager.py` | `_load_daily_state()` → EET date |
| `unified_risk_manager.py` | `_save_daily_state()` → EET date |
| `unified_risk_manager.py` | `_reset_daily_state()` → EET timestamp |
| `unified_risk_manager.py` | `_send_daily_awakened_alert()` → minimalist SYSTEM RESET |
| `unified_risk_manager.py` | `validate_new_trade()` → rollover pause 00:00–01:05 EET (primul check) |
| `unified_risk_manager.py` | `validate_new_trade()` → BTC bypass eliminat, lot dinamic activat |
| `unified_risk_manager.py` | Lot calc: BTC `pip_value = 1.0` (cTrader model) în loc de `0.01` |
| `SUPER_CONFIG.json` | `spread_guard` actualizat cu `rollover_window_eet_start/end` EET |

### Verificări
- ✅ `unified_risk_manager.py` — SYNTAX OK
- ✅ `SUPER_CONFIG.json` — JSON OK
- ✅ `pytz 2025.2` disponibil în `.venv`

---

*Task 5 complet: 2026-04-08 | unified_risk_manager.py V14.0*

---

---

## 🔴 TASK 6 — BTCUSD Live Execution Fixes (V14.2)

**Trigger:** Test live BTCUSD SELL — poziție executată la 71,633 fără SL/TP. Screenshot confirmat de user.

---

### 6.1 — `ctrader_executor.py` — Eliminat al doilea bypass V5.6

**Problemă descoperită**: Existau **două** bypass-uri BTC, nu unul:
- Bypass 1 (în `unified_risk_manager.py`) → eliminat în Task 5 ✅
- **Bypass 2** (în `ctrader_executor.py` linia ~530) → trecut neobservat

```python
# ❌ BUGGY (V5.6 BULLETPROOF — bypass ascuns în executor):
if 'BTC' in symbol_clean or any(c in symbol_clean for c in ['ETH', 'XRP']):
    lot_size = 0.50   # ← FORȚA 0.50 loturi INDIFERENT de ce calcula risk manager-ul!
    logger.info(f"🪙 V5.6 BULLETPROOF: BTC/Crypto lot fixed at {lot_size}")
```

**Fix**: Bloc complet eliminat. Înlocuit cu:
```python
# ✅ V14.0: BTC bypass REMOVED — lot_size vine din unified_risk_manager.py (pip_value=1.0)
if lot_size < 0.01:
    logger.warning(f"⚠️ Lot size {lot_size:.4f} below broker minimum - forcing to 0.01")
    lot_size = 0.01
```

---

### 6.2 — `btc_market_order.py` — V14.2: Live price din broker

**Problema root cause SL/TP missing**: `current_price = 66516.60` era **hardcodat** în fișier.
- BTC era la **71,633** când s-a executat ordinul
- Formula SL pentru SELL: `SL = entry + buffer` → `66516 + 1330 = 67,846`
- `67,846 < 71,633 (entry)` → **SL sub prețul de intrare** pentru un SHORT → `ModifyPosition` a eșuat silențios
- Rezultat: poziție deschisă **fără SL/TP**

**Fix V14.2 — ierarhie prețuri live**:
```python
def get_btc_price_from_broker() -> float:
    # Sursa 1: active_positions.json (entry_price poziție BTC deschisă)
    # Sursa 2: monitoring_setups.json (entry_price setup BTC activ)
    # Sursa 3: yfinance BTC-USD (fallback live)
    # Sursa 4: excepție explicită (nu mai există fallback hardcodat)
```

**Adăugat**: `assert stop_loss > entry_price` pentru SELL — aruncă eroare explicită dacă SL e greșit, nu mai eșuează silențios.

**Adăugat**: `time.sleep(2)` după `execute_trade()` — flush queue async înainte de exit proces.

**Suport CLI**: `python btc_market_order.py 71390` — prețul ca argument direct.

---

### 6.3 — Confirmare execuție live

```
execution_report.json:
  Symbol:     BTCUSD
  Direction:  SELL
  Volume:     0.15 lots  (dinamic, nu 0.50 fix ✅)
  StopLoss:   72818       (deasupra entry ✅)
  TakeProfit: 64251       (sub entry ✅)
  Position:   #604058430
```

| Verificare | Rezultat |
|-----------|---------|
| Lot dinamic (nu 0.50) | ✅ 0.15 loturi |
| SL setat corect | ✅ 72,818 (SHORT: SL > entry) |
| TP setat corect | ✅ 64,251 (SHORT: TP < entry) |
| Duplicate guard funcțional | ✅ Al doilea ordin blocat (poziție deja deschisă) |

### Fișiere modificate

| Fișier | Modificare |
|--------|------------|
| `ctrader_executor.py` | V5.6 BTC bypass eliminat (~linia 530) |
| `btc_market_order.py` | `get_btc_price_from_broker()` nou — live price ierarhie |
| `btc_market_order.py` | `assert stop_loss > entry_price` guard SELL |
| `btc_market_order.py` | `time.sleep(2)` async flush |
| `btc_market_order.py` | CLI argument `sys.argv[1]` pentru preț manual |

---

*Task 6 complet: 2026-04-08 | ctrader_executor.py V14.0 + btc_market_order.py V14.2*

---

---

## 🟢 TASK 7 — V14.1 Dual Entry Scale-In Implementation

**Trigger:** User request — "vreau sa implementam ambele intrari, daca al 2 lea entry confirma choch pe 4h sa adauge a2 intrare cu volum putin mai mare fata de primul entry pe 1h"

---

### Arhitectura implementată

```
Entry 1: 1H FVG confirmat  →  EXECUTE_ENTRY1  →  Risk 5%   →  lot ~0.17 (30-pip SL, $1000)
            ↓ (entry1_filled = True)
Entry 2: 4H CHoCH confirmat →  EXECUTE_ENTRY2  →  Risk 7.5% →  lot ~0.25 (1.5× mai mare)
            ↓ (entry2_filled = True)
         STOP — nu mai intră
Broker: 2 poziții deschise simultan pe același simbol ✅
```

---

### 7.1 — `SUPER_CONFIG.json`

**Modificări:**

```json
// ÎNAINTE:
"max_positions_per_symbol": 1,

// DUPĂ (V14.1):
"max_positions_per_symbol": 2,

// ADĂUGAT — bloc nou:
"scale_in": {
  "entry2_risk_percent": 7.5,
  "entry2_risk_multiplier": 1.5,
  "comment": "Entry 2 (4H CHoCH scale-in) uses 7.5% risk = 1.5x Entry 1 (5%)"
}
```

---

### 7.2 — `unified_risk_manager.py`

**Modificare 1**: `max_positions_per_symbol` citit din SUPER_CONFIG (nu mai e hardcodat):
```python
# ÎNAINTE:
self.max_positions_per_symbol = 1  # hardcodat

# DUPĂ (V14.1):
self.max_positions_per_symbol = self.config.get('position_limits', {}).get('max_positions_per_symbol', 1)
# → citit din SUPER_CONFIG: acum = 2
```

**Modificare 2**: `validate_new_trade()` acceptă `risk_override_percent`:
```python
# ÎNAINTE:
def validate_new_trade(self, symbol="", direction="", entry_price=0, stop_loss=0):

# DUPĂ (V14.1):
def validate_new_trade(self, symbol="", direction="", entry_price=0, stop_loss=0,
                       risk_override_percent: float = None):
# Entry 1: risk_override_percent=None → folosește 5% din SUPER_CONFIG
# Entry 2: risk_override_percent=7.5  → lot 1.5× mai mare
```

**Modificare 3**: Lot calc folosește `effective_risk_pct`:
```python
effective_risk_pct = risk_override_percent if risk_override_percent is not None else self.risk_per_trade
risk_amount = balance * (effective_risk_pct / 100.0)
```

---

### 7.3 — `ctrader_executor.py`

`execute_trade()` acceptă și transmite `risk_override_percent`:
```python
# ÎNAINTE:
def execute_trade(self, symbol, direction, entry_price, stop_loss, take_profit,
                  lot_size=0.01, comment="", status="READY", setup=None):

# DUPĂ (V14.1):
def execute_trade(self, symbol, direction, entry_price, stop_loss, take_profit,
                  lot_size=0.01, comment="", status="READY", setup=None,
                  risk_override_percent: float = None):

# Transmis la risk manager:
validation = self.risk_manager.validate_new_trade(
    ...,
    risk_override_percent=risk_override_percent  # None pt E1, 7.5 pt E2
)
```

---

### 7.4 — `setup_executor_monitor.py`

**Modificare 1**: Guard `entry2_filled` — previne execuție duplicată:
```python
else:  # entry1_filled = True
    # ✅ V14.1: Skip dacă Entry 2 deja executat
    if setup.get('entry2_filled', False):
        logger.debug(f"✅ {symbol}: Entry 2 already filled — monitoring position")
        continue
```

**Modificare 2**: Execuție Entry 2 cu risc scale-in:
```python
if action == 'EXECUTE_ENTRY2':
    scale_in_risk = self.config.get('scale_in', {}).get('entry2_risk_percent', 7.5)
    e1_risk = self.config.get('risk_management', {}).get('risk_per_trade_percent', 5.0)
    logger.info(f"📈 V14.1 SCALE-IN: Entry 2 risk = {scale_in_risk}% (vs Entry 1 = {e1_risk:.1f}%)")
    success = self._execute_entry(
        ...,
        risk_override_percent=scale_in_risk  # 7.5%
    )
```

**Modificare 3**: `_execute_entry()` acceptă și transmite `risk_override_percent`:
```python
def _execute_entry(self, setup, entry_number, entry_price, stop_loss, take_profit,
                   position_size, risk_override_percent: float = None):
    ...
    success = self.executor.execute_trade(
        ...,
        risk_override_percent=risk_override_percent  # propagat la risk manager
    )
```

---

### Verificări

```
$ python -m py_compile unified_risk_manager.py   ✅
$ python -m py_compile ctrader_executor.py       ✅
$ python -m py_compile setup_executor_monitor.py ✅
$ SUPER_CONFIG.json max_per_symbol=2 | E2 risk=7.5% ✅
```

**Simulare lot calc** (verificată live în Python):
```
$1000 balance | 30-pip SL | EURUSD
  Entry 1: 0.17 lots  (5.0%  risk = $50)
  Entry 2: 0.25 lots  (7.5%  risk = $75)
  Ratio: Entry 2 = 1.50× Entry 1 ✅
```

### Fișiere modificate

| Fișier | Modificare | Tip |
|--------|------------|-----|
| `SUPER_CONFIG.json` | `max_positions_per_symbol: 1 → 2` | 🔴 CONFIG |
| `SUPER_CONFIG.json` | Bloc `"scale_in"` nou (`entry2_risk_percent: 7.5`) | 🔴 CONFIG |
| `unified_risk_manager.py` | `max_positions_per_symbol` citit din SUPER_CONFIG | 🟠 LOGIC |
| `unified_risk_manager.py` | `validate_new_trade()` + `risk_override_percent` param | 🟠 LOGIC |
| `unified_risk_manager.py` | Lot calc: `effective_risk_pct` override-abil | 🟠 LOGIC |
| `ctrader_executor.py` | `execute_trade()` + `risk_override_percent` param | 🟠 LOGIC |
| `ctrader_executor.py` | Transmis la `validate_new_trade()` | 🟠 LOGIC |
| `setup_executor_monitor.py` | Guard `entry2_filled` (anti-spam) | 🟢 GUARD |
| `setup_executor_monitor.py` | Entry 2 execuție cu `scale_in_risk=7.5%` | 🟢 FEATURE |
| `setup_executor_monitor.py` | `_execute_entry()` + `risk_override_percent` param | 🟢 FEATURE |

---

*Task 7 complet: 2026-04-08 | V14.1 SCALE-IN DUAL ENTRY*

---

---

## 📊 SUMAR SESIUNE 2026-04-08 — Toate Task-urile

| # | Task | Fișier(e) | Status |
|---|------|-----------|--------|
| 1 | SL Bug Fix — Regula Generalului | `smc_detector.py` | ✅ |
| 2 | Volatility Radar + EET fix | `news_calendar_monitor.py` | ✅ |
| 3 | Executor SL Propagation (V13.2) | `setup_executor_monitor.py` | ✅ |
| 4 | *(Circuit Breaker Audit — read-only)* | `unified_risk_manager.py` | ✅ |
| 5 | Romania Time + Rollover + BTC lot | `unified_risk_manager.py`, `SUPER_CONFIG.json` | ✅ |
| 6 | BTC live SL/TP fix + al doilea bypass | `ctrader_executor.py`, `btc_market_order.py` | ✅ |
| 7 | Dual Entry Scale-In V14.1 | 4 fișiere | ✅ |

**Versiuni finale:**
- `smc_detector.py` → V13.2 GENERALUL
- `news_calendar_monitor.py` → V13.2 VOLATILITY RADAR
- `setup_executor_monitor.py` → V13.2 + V14.1 SCALE-IN
- `unified_risk_manager.py` → V14.0 + V14.1
- `ctrader_executor.py` → V14.0 (bypass eliminat)
- `btc_market_order.py` → V14.2

---

*Sesiune închisă: 2026-04-08 | ФорексГод*
