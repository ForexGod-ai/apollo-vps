# 🧠 SISTEM COMPLET — Glitch in Matrix V17
## Arhitectură + Flux + Toate Editurile V16.4 → V17

> **Commit V17:** `813f825` — pushed pe GitHub  
> **VPS Status:** NU aplicat încă — necesită `git pull` + kill/restart procese

---

## 🏗️ ARHITECTURA SISTEMULUI

### Diagrama completă a fluxului

```
daily_scanner.py  (manual, dimineața)
    │  detectează: Daily CHoCH/BOS, direction, FVG, SL structural, TP
    ↓
monitoring_setups.json  ← scris de scanner
    │  conține: symbol, direction, fvg_top, fvg_bottom, stop_loss, take_profit,
    │           strategy_type (reversal/continuation), d1_bias_direction
    ↓
multi_tf_radar.py  (daemon 30s — OCHII)
    │  citește: monitoring_setups.json
    │  scanează: 1H + 4H CHoCH/FVG pe fiecare pereche
    │  scrie în setup: radar_4h_choch_detected, h4_locked, h4_structure_locked,
    │                  h4_sync_fvg_top, h4_sync_fvg_bottom, h4_lock_price, h4_lock_time
    ↓
setup_executor_monitor.py  (daemon 30s — CREIERUL)
    │  citește: monitoring_setups.json (cu câmpurile de la radar)
    │  decide: KEEP_MONITORING sau EXECUTE_ENTRY1
    │  folosește: ctrader_executor.py (LIBRĂRIE — nu daemon)
    ↓
signals.json  ← scris atomic (temp file + os.replace)
    ↓
cBot C# din cTrader  (polling ~10s)
    ↓
Ordin plasat pe cont live IC Markets 6139026
```

---

## 🎯 STRATEGIA SMC — CUM FUNCȚIONEAZĂ CORECT (V17)

### Principiul fundamental

```
Daily bias (CHoCH sau BOS) → identifică direcția + zona de pullback (FVG/OB)
    ↓
Prețul intră în zona Daily → pullback în curs
    ↓
4H CHoCH cu body close → CONFIRMĂ că pullback-ul Daily s-a terminat
    ↓  ← INTRAREA NOASTRĂ ESTE AICI (după confirmarea 4H)
Pullback pe 4H în FVG-ul CHoCH-ului 4H → EXECUTE
    │
    ├── SL = ultimul swing point 4H anterior CHoCH (structural)
    └── TP = ultimul structure point Daily (din scanner)
```

### Reversal vs Continuity
| Aspect | Reversal | Continuity |
|--------|----------|-----------|
| Daily trigger | CHoCH (schimbare structură) | BOS (continuare trend) |
| 4H confirmare | CHoCH obligatoriu | CHoCH SAU BOS (V17) |
| Logică entry | Identică | Identică |
| SL | Același (4H swing) | Același |
| TP | Același (Daily target) | Același |

### Exemplu EURNZD din chart

**Daily:**
1. Uptrend cu BOS-uri consecutive (continuity)
2. Apare CHoCH bearish → prețul lichidează low cu body close → **REVERSAL confirmat**
3. Pullback sus în zona FVG Daily (dreptunghiul verde de pe chart)
4. În acea zonă → așteptăm 4H CHoCH

**4H:**
1. Se face CHoCH bearish exact când pullback-ul Daily se epuizează în FVG
2. Acesta este **semnalul de intrare** → entry pe pullback 4H în FVG-ul CHoCH-ului 4H
3. SL = deasupra swing high 4H anterior CHoCH
4. TP = ultimul Daily structure point jos (target-ul bearish Daily)

---

## 📁 ROLUL FIECĂRUI SCRIPT

| Script | Tip | Rol | Watchdog |
|--------|-----|-----|----------|
| `watchdog_monitor.py` | Daemon | Guardian — repornește 9 procese automat | ❌ (el însuși) |
| `multi_tf_radar.py` | Daemon 30s | Detectează CHoCH 1H+4H, scrie câmpuri radar | ✅ |
| `setup_executor_monitor.py` | Daemon 30s | Decide execuția, apelează ctrader_executor | ✅ |
| `ctrader_executor.py` | **LIBRĂRIE** | Scrie signals.json — NU rulează singur | ❌ |
| `smc_detector.py` | **LIBRĂRIE** | Algoritmii CHoCH/BOS/FVG — NU rulează singur | ❌ |
| `daily_scanner.py` | Manual | Descoperire setup-uri noi dimineața | ❌ |
| `position_monitor.py` | Daemon | Live P/L tracker + notificări | ✅ |
| `telegram_command_center.py` | Daemon | Interfața mobilă Telegram | ✅ |
| `ctrader_sync_daemon.py` | Daemon | Bridge date IC Markets | ✅ |
| ~~`execution_radar.py`~~ | DEPRECATED | Oprit — înlocuit de multi_tf_radar | ⛔ |

---

## 🔧 TOATE EDITURILE — V16.4 → V16.5 → V17

---

### 📦 V16.4 — Commit `38d140b`
**Fișier:** `setup_executor_monitor.py`

#### Edit 1 — `_check_radar_entry()` else branch (linia ~895)
```python
# ÎNAINTE: returna KEEP_MONITORING → Fibo 50% nu era NICIODATĂ apelat
return {'action': 'KEEP_MONITORING', ...}

# DUPĂ: acțiune specială care cade pe _check_pullback_entry
return {'action': 'RADAR_CHOCH_NO_FVG', ...}
```
**Bug rezolvat:** CHoCH detectat dar preț nu în FVG → loop infinit KEEP_MONITORING

#### Edit 2 — `_process_monitoring_setups()` handler (linia ~1860)
```python
# DUPĂ: RADAR_CHOCH_NO_FVG → fallback _check_pullback_entry()
if result.get('action') == 'RADAR_CHOCH_NO_FVG':
    result = self._check_pullback_entry(setup, df_1h, symbol)
```
**Bug rezolvat:** Noua acțiune nu era gestionată nicăieri

#### Edit 3 — `max_age_candles=48 → 200` în `_check_pullback_entry()` (linia ~987)
**Bug rezolvat:** 48 bare = 8 zile — respingea CHoCH valide mai vechi de 8 zile

#### Edit 4 — `max_age_candles=48 → 200` în READY Guard (linia ~1773)
**Bug rezolvat:** Același limită resetea setup-uri READY dacă CHoCH > 8 zile vechi

---

### 📦 V16.5 — Commit `6be6597`
**Fișiere:** `setup_executor_monitor.py` + `multi_tf_radar.py`

#### Edit 5 — `multi_tf_radar.py` `_sync_to_monitoring_setups()` (linia ~660)
```python
# ÎNAINTE: scria doar h4_locked=True
setup['h4_locked'] = True

# DUPĂ: scrie și h4_structure_locked (cheia citită de executor)
setup['h4_locked'] = True
setup['h4_structure_locked'] = True  # V16.5
```
**Bug rezolvat:** Key mismatch — radar scria `h4_locked`, executor citea `h4_structure_locked`

#### Edit 6+7 — P/D EQ validation 1H + 4H (liniile ~775, ~840)
```python
# ÎNAINTE: fallback greșit la choch_price ca EQ
radar_1h_eq = setup.get('radar_1h_eq') or radar_1h_choch_price  # GREȘIT

# DUPĂ: None = skip check pentru setup pre-V16.2
radar_1h_eq = setup.get('radar_1h_eq')
if radar_1h_eq is None:
    zone_valid = True  # skip — EQ nedisponibil
```
**Bug rezolvat:** `choch_price` ≠ 50% EQ → validări P/D incorecte

#### Edit 8 — Propagare confirmări radar (linia ~1868)
```python
# DUPĂ: propagă h4_structure_locked + choch_1h_detected din radar în setup
if setup.get('radar_4h_choch_detected'):
    setup['h4_structure_locked'] = True
if setup.get('radar_1h_choch_detected') and not setup.get('choch_1h_detected'):
    setup['choch_1h_detected'] = True
```
**Bug rezolvat:** Executor re-valida independent cu ATR diferit → putea eșua

---

### 📦 V17 — Commit `813f825`
**Fișiere:** `setup_executor_monitor.py` + `smc_detector.py`

#### Edit 9 — BUG#9 Fix: Guard#4 în `_execute_entry()` (linia ~2245)
```python
# ÎNAINTE (BUG CRITIC): cheia h4_bias_locked nu există în niciun setup!
h4_locked = setup.get('h4_bias_locked', False)
# → bloca TOATE execuțiile silențios

# DUPĂ:
h4_locked = setup.get('h4_structure_locked', False) or setup.get('h4_bias_locked', False)
```
**Bug rezolvat:** Guard#4 bloca executarea oricărui semnal valid — nimeni nu trecea

#### Edit 10 — Continuity BOS support în `smc_detector.py` `get_4h_body_close_confirmation()`
```python
# ÎNAINTE: accepta DOAR CHoCH pe 4H → continuity niciodată confirmat
h4_chochs, _ = detector.detect_choch_and_bos(df_4h)
for h4ch in reversed(h4_chochs):

# DUPĂ: parametru nou allow_bos=True pentru continuity
def get_4h_body_close_confirmation(..., allow_bos: bool = False):
    h4_chochs, h4_bos_list = detector.detect_choch_and_bos(df_4h)
    if allow_bos and h4_bos_list:
        candidates = sorted(list(h4_chochs) + list(h4_bos_list), key=lambda x: x.index)
    else:
        candidates = list(h4_chochs)
    for h4ch in reversed(candidates):
```
**Bug rezolvat:** Continuity nu se găsea niciodată — BOS pe 4H era ignorat complet

#### Edit 11 — Propagare allow_bos în apelul din `setup_executor_monitor.py` (linia ~998)
```python
# DUPĂ:
confirmed_4h, valid_4h_lock, lock_reason = get_4h_body_close_confirmation(
    ...,
    allow_bos=(strategy_type == 'continuation')  # V17
)
```

#### Edit 12 — V17 bypass 4H pullback în `_check_pullback_entry()` (după END V14.2)
```python
# LOGICA NOUĂ: după h4_structure_locked=True, dacă avem h4_sync_fvg_top/bottom:
# → skip 1H CHoCH complet
# → scanăm ultimele 20 bare 4H pentru pullback în FVG CHoCH-ului
# → entry la midpoint FVG | SL = swing 4H | TP = setup['take_profit']

if h4_locked and h4_sync_fvg_top and h4_sync_fvg_bottom:
    for candle in last_candles_4h:
        if direction == 'buy' and candle['low'] <= fvg_top_4h:
            → EXECUTE_ENTRY1
        if direction == 'sell' and candle['high'] >= fvg_bottom_4h:
            → EXECUTE_ENTRY1
    else:
        → KEEP_MONITORING (așteptăm pullback în FVG)
# Dacă h4_sync_fvg lipsește → fallback la 1H CHoCH path (legacy)
```
**Schimbare fundamentală:** Trigger-ul principal devine **4H CHoCH + pullback 4H**, nu 1H CHoCH

#### Edit 13 — Continuity fetch 4H/Daily data pentru Fibo (linia ~1135)
```python
# ÎNAINTE: doar reversal fetcha 4H/Daily pentru Fibo
if strategy_type == 'reversal':
    df_4h_fibo = ...

# DUPĂ: ambele tipuri — continuity are și ea 4H CHoCH
if True:  # V17: era strategy_type == 'reversal'
    df_4h_fibo = ...
```
**Schimbare:** Continuity calculează Fibo din swing 4H (nu 1H) pentru entry mai precis

---

## 📊 SUMAR COMPLET TOATE EDITURILE

| # | Versiune | Fișier | Funcție | Bug rezolvat / Schimbare |
|---|---------|--------|---------|--------------------------|
| 1 | V16.4 | setup_executor_monitor | `_check_radar_entry` else | KEEP_MONITORING → RADAR_CHOCH_NO_FVG |
| 2 | V16.4 | setup_executor_monitor | `_process_monitoring_setups` | Handler RADAR_CHOCH_NO_FVG → fallback |
| 3 | V16.4 | setup_executor_monitor | `_check_pullback_entry` | max_age_candles 48→200 |
| 4 | V16.4 | setup_executor_monitor | READY guard | max_age_candles 48→200 |
| 5 | V16.5 | multi_tf_radar | `_sync_to_monitoring_setups` | Adaugă h4_structure_locked=True |
| 6 | V16.5 | setup_executor_monitor | `_check_radar_entry` 1H P/D | EQ fallback None → skip check |
| 7 | V16.5 | setup_executor_monitor | `_check_radar_entry` 4H P/D | EQ fallback None → skip check |
| 8 | V16.5 | setup_executor_monitor | `_process_monitoring_setups` | Propagare h4_structure_locked + choch_1h din radar |
| **9** | **V17** | **setup_executor_monitor** | **`_execute_entry` Guard#4** | **BUG#9: h4_bias_locked → h4_structure_locked** |
| **10** | **V17** | **smc_detector** | **`get_4h_body_close_confirmation`** | **Continuity BOS support (allow_bos)** |
| **11** | **V17** | **setup_executor_monitor** | **apel get_4h_body_close_confirmation** | **allow_bos=True pentru continuity** |
| **12** | **V17** | **setup_executor_monitor** | **`_check_pullback_entry` V17 bypass** | **4H pullback în FVG (skip 1H CHoCH)** |
| **13** | **V17** | **setup_executor_monitor** | **Fibo fetch continuity** | **Continuity și reversal = 4H/Daily Fibo** |

---

## 🚦 STATUS VERSIUNI

| Versiune | Commit | GitHub | VPS |
|---------|--------|--------|-----|
| V16.1 P/D FVG | `498e495` | ✅ | ✅ |
| V16.2 EQ pipeline | `a179b98` | ✅ | ✅ |
| V16.3 EQ buffer 3 pips | `8c556c2` | ✅ | ✅ |
| V16.4 Death loop fix | `38d140b` | ✅ | ❌ |
| V16.5 Sync fixes | `6be6597` | ✅ | ❌ |
| V17 4H pullback + continuity + BUG#9 | `813f825` | ✅ | ❌ |

---

## 🔄 GIT PULL PE VPS — Procedura completă

```powershell
cd "C:\Users\Administrator\Desktop\Glitch in Matrix\trading-ai-agent apollo"
git pull origin main

# Kill setup_executor_monitor + multi_tf_radar (Watchdog repornește în 60s)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | `
  Where-Object { $_.CommandLine -like "*setup_executor_monitor*" } | `
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Get-CimInstance Win32_Process -Filter "Name='python.exe'" | `
  Where-Object { $_.CommandLine -like "*multi_tf_radar*" } | `
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

### Log-uri de confirmat că V17 funcționează:
```
🎯 [V17] EURNZD: 4H pullback în CHoCH FVG! touch=1.98700 FVG=[1.98500-1.98900] entry=1.98700 diff=0.0p
🔥 [V17] 4H CHoCH + pullback 4H în FVG (diff=2.3p)
✅ [V17 SL] EURNZD: SL @ 4H swing high 1.99250 + buf = 1.99260
```

### Revert dacă ceva nu merge:
```powershell
git reset --hard 8c556c2  # revin la V16.3 stabilă
git push origin main --force
```

---

## 🔮 CE URMEAZĂ (backlog)

1. **Race condition monitoring_setups.json** — scris fără lock de ambele procese simultan → posibil data corruption sub load
2. **Fire-and-forget signals.json** — nicio confirmare că cBot a executat → add ACK mechanism
3. **TP dinamic** — TP să se ajusteze dacă structura Daily se modifică după intrare
4. **Partial close** — 50% la TP1 (primul structure point), 50% la TP2 (target final Daily)

---

**Data:** 2026-05-15  
**Commit V17:** `813f825`  
**Platformă:** Windows VPS (PowerShell) — IC Markets Live 6139026  
**Strategia:** SMC — Daily + 4H Sync Entry  
