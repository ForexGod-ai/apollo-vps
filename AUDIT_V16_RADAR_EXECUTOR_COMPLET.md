# 🔬 AUDIT COMPLET — multi_tf_radar.py ↔ setup_executor_monitor.py
## V16.5 — De ce nu se executa nimic după dezactivarea monitorului vechi

**Data:** 2026-05-15  
**Concluzie:** TF Radar NU este un motor de execuție complet standalone. Are 5 bug-uri arhitecturale care blochează orice execuție.

---

## 🏗️ ARHITECTURA REALĂ (cum funcționează ACUM)

```
multi_tf_radar.py (daemon 30s)
  ↓ detectează CHoCH pe 1H + 4H
  ↓ calculează FVG din CHoCH
  ↓ scrie în monitoring_setups.json:
      radar_4h_choch_detected = True
      radar_4h_fvg_top / _bottom
      radar_4h_in_fvg = True/False   ← POINT-IN-TIME (se suprascrie la fiecare 30s!)
      h4_locked = True               ← CHEIE GREȘITĂ (executor citește h4_structure_locked)
      radar_1h_choch_detected = True
      radar_1h_fvg_top / _bottom
      radar_1h_in_fvg = True/False   ← POINT-IN-TIME

setup_executor_monitor.py (daemon 5-30s)
  ↓ citește monitoring_setups.json
  ↓ dacă radar_1h_choch_detected OR radar_4h_choch_detected → use_radar_data=True
  ↓ apelează _check_radar_entry()
      dacă radar_1h_in_fvg=True → EXECUTE SNIPER    ← ferestră <30s!
      dacă radar_4h_in_fvg=True → EXECUTE 4H        ← ferestră <30s!
      altfel → RADAR_CHOCH_NO_FVG (V16.4)
  ↓ fallback pe _check_pullback_entry()
      verifică h4_structure_locked → NICIODATĂ True (cheia greșită!)
      → re-rulează get_4h_body_close_confirmation() cu ATR 0.6x
      → dacă nu găsește CHoCH → KEEP_MONITORING "Așteptăm CHoCH 4H"
```

---

## 🐛 BUG #5 — KEY MISMATCH FATAL (CAUZA PRINCIPALĂ)

**Fișier:** `multi_tf_radar.py` linia ~660 în `_sync_to_monitoring_setups()`  
**Severitate:** 🔴 CRITIC — blochează 100% din execuții

```python
# RADAR SCRIE:
setup['h4_locked'] = True          ← cheia pe care o scrie radar-ul

# EXECUTOR CITEȘTE:
h4_locked = setup.get('h4_structure_locked', False)  ← cheie DIFERITĂ
```

**Efectul:** Chiar dacă radar confirmă clar 4H CHoCH, executorul NU îl vede niciodată.  
La fiecare iterație, executorul re-rulează `get_4h_body_close_confirmation()` cu **propriul** SMC detector.

---

## 🐛 BUG #6 — DUBLA VALIDARE CU ATR DIFERIT

**Fișier:** `setup_executor_monitor.py`  
**Severitate:** 🔴 CRITIC

- **Radar** folosește `SMCDetector(atr_multiplier=1.0)` pentru 4H
- **Executor** folosește `SMCDetector(atr_multiplier=0.6)` pentru re-validare

Aceiași date H4, dar detectoare **diferite** → pot găsi CHoCH-uri **complet diferite**.

Scenariul de eșec:
```
Radar (1.0x ATR): detectează CHoCH valid pe 4H la bara X → scrie radar_4h_choch_detected=True
Executor (0.6x ATR): nu găsește același CHoCH (pragul diferit) → returnează KEEP_MONITORING
→ Infinit KEEP_MONITORING chiar dacă CHoCH e vizibil pe grafic
```

---

## 🐛 BUG #7 — P/D EQ FALLBACK FOLOSEȘTE VALOARE GREȘITĂ

**Fișier:** `setup_executor_monitor.py` linia ~762  
**Severitate:** 🟡 MEDIU — respinge intrări valide

```python
# CODUL ACTUAL (greșit):
radar_1h_eq = setup.get('radar_1h_eq') or radar_1h_choch_price
```

`radar_1h_choch_price` = CLOSE-ul lumânării CHoCH ≠ 50% EQ al impulsului.  
Sunt valori complet diferite. Folosirea lui ca EQ produce validări P/D incorecte.

**Fix:** Dacă `radar_1h_eq` lipsește → skip P/D check (setup pre-V16.2), nu folosi fallback greșit.

---

## 🐛 BUG #8 — RADAR 1H CHoCH NU ESTE PROPAGAT LA EXECUTOR

**Fișier:** `setup_executor_monitor.py`  
**Severitate:** 🟡 MEDIU

Radar setează: `radar_1h_choch_detected = True`  
Executor verifică: `setup.get('choch_1h_detected', False)` ← cheie DIFERITĂ

**Efectul:** Când executorul cade pe `_check_pullback_entry` (după V16.4 RADAR_CHOCH_NO_FVG),  
re-detectează 1H CHoCH independent. Dacă nu-l găsește sau break_price nu e în FVG → KEEP_MONITORING.

---

## 🐛 BUG #9 — FEREASTRA `in_fvg` PREA MICĂ (ARHITECTURAL)

**Severitate:** 🟡 MEDIU — cauzează trade-uri ratate

`radar_4h_in_fvg=True` este **POINT-IN-TIME** — suprascris la fiecare scan (30s).

Scenariul de ratare:
```
t=0s:  Radar scanează → preț ÎN FVG → scrie radar_4h_in_fvg=True
t=8s:  Executor scanează → citește True → încearcă execuție → RR check fails → blochează
t=30s: Radar scanează din nou → preț IEȘIT din FVG → scrie radar_4h_in_fvg=False
t=35s: Executor scanează → citește False → KEEP_MONITORING → trade RATAT
```

Vechiul monitor folosea Fibo 50% "odată atins = rămâne triggerat" — mult mai robust.

---

## 🗺️ DIAGRAMA COMPLETĂ A MORȚII (FLOW ACTUAL FĂRĂ FIX-URI)

```
[radar detectează 4H CHoCH]
         ↓
radar scrie:
  radar_4h_choch_detected = True
  h4_locked = True              ← CHEIE GREȘITĂ
         ↓
executor citește:
  use_radar_data = True
  → _check_radar_entry()
         ↓
  radar_4h_in_fvg = False? (preț nu e în FVG)
  → returnează RADAR_CHOCH_NO_FVG (V16.4)
         ↓
  → _check_pullback_entry()
         ↓
  h4_structure_locked = False  ← NICIODATĂ True (cheie greșită!)
         ↓
  → get_4h_body_close_confirmation(atr=0.6x)
         ↓
  poate nu găsește CHoCH (ATR diferit de radar)
         ↓
  → KEEP_MONITORING "Așteptăm CHoCH 4H"
         ↓
  [bucla se repetă la infinit]
```

---

## ✅ FIX-URILE V16.5

### FIX A — `multi_tf_radar.py`: scrie ambele chei
```python
# ÎNAINTE:
setup['h4_locked'] = True

# DUPĂ:
setup['h4_locked'] = True
setup['h4_structure_locked'] = True  # V16.5: cheia pe care o citește executorul
```

### FIX B — `setup_executor_monitor.py`: propagă confirmările radar înainte de _check_pullback_entry
```python
# Când vine din RADAR_CHOCH_NO_FVG, injectează confirmările radar:
if result.get('action') == 'RADAR_CHOCH_NO_FVG':
    if setup.get('radar_4h_choch_detected'):
        setup['h4_structure_locked'] = True   # BUG#5+6: trust radar's 4H confirmation
        setups[i]['h4_structure_locked'] = True
    if setup.get('radar_1h_choch_detected') and not setup.get('choch_1h_detected'):
        setup['choch_1h_detected'] = True     # BUG#8: propagate 1H CHoCH
        setup['choch_1h_timestamp'] = setup.get('radar_1h_choch_time', ...)
        setups[i]['choch_1h_detected'] = True
        setups[i]['choch_1h_timestamp'] = ...
    result = self._check_pullback_entry(setup, df_1h, symbol)
```

### FIX C — `setup_executor_monitor.py`: skip P/D check când EQ lipsește
```python
# ÎNAINTE:
radar_1h_eq = setup.get('radar_1h_eq') or radar_1h_choch_price  # GREȘIT

# DUPĂ:
radar_1h_eq = setup.get('radar_1h_eq')  # None = skip P/D check
```

---

## 📊 TABEL SUMAR BUG-URI

| # | Bug | Cauza | Efect | Severitate | Status |
|---|-----|-------|-------|------------|--------|
| 5 | Key mismatch `h4_locked` vs `h4_structure_locked` | Radar și executor folosesc chei diferite | Executor re-validează 4H independent la infinit | 🔴 CRITIC | ✅ Fix V16.5 |
| 6 | ATR mismatch 1.0x vs 0.6x | Detector-e diferite pentru același TF | Re-validarea executorului poate eșua | 🔴 CRITIC | ✅ Fix V16.5 |
| 7 | P/D EQ fallback la choch_price greșit | `radar_1h_eq or choch_price` | Respingere FVG-uri valide | 🟡 MEDIU | ✅ Fix V16.5 |
| 8 | `radar_1h_choch_detected` ≠ `choch_1h_detected` | Chei diferite | Re-detecție 1H CHoCH inutilă | 🟡 MEDIU | ✅ Fix V16.5 |
| 9 | `in_fvg` point-in-time (30s ferestră) | Design radar | Trade-uri ratate la FVG-uri rapide | 🟡 MEDIU | Parțial via Fibo fallback |

**Bug-uri 1-4 fixate anterior (V16.4):**
| 1+3 | `_check_radar_entry` returnează `KEEP_MONITORING` când nu e în FVG | `RADAR_CHOCH_NO_FVG` | ✅ Fix V16.4 |
| 2 | `max_age_candles=48` respingea CHoCH vechi | → 200 | ✅ Fix V16.4 |
| 4 | READY guard cu 48 bare | → 200 | ✅ Fix V16.4 |

---

## 🎯 DE CE NU SE EXECUTA NIMIC DUPĂ DEZACTIVAREA MONITORULUI VECHI

**Monitorul vechi (`execution_radar.py`)** era un motor COMPLET standalone:
- Detecta 4H CHoCH cu `get_4h_body_close_confirmation()`
- Calcula Fibo 50% din swingul 4H
- Așteptea pullback-ul la Fibo 50%
- Executa direct

**`multi_tf_radar.py`** NU este un motor de execuție — este un detector de semnal care **scrie date** în JSON pentru ca executorul să le citească. 

Problema: executorul (`setup_executor_monitor.py`) are propria sa logică de validare completă (4H body close, 1H CHoCH în FVG, Fibo pullback) și tratează datele radar ca **hints** (sugestii), NU ca confirmări finale. Cele 5 bug-uri de mai sus fac ca hint-urile radar să fie **complet ignorate** → executorul rulează propria sa validare → care eșuează din cauza ATR diferit → **KEEP_MONITORING infinit**.

---

**Versiune fixată:** V16.5  
**Commit:** (pending)
