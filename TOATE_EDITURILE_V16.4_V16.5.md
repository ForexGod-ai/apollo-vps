# 📋 TOATE EDITURILE FĂCUTE — V16.4 + V16.5
## Document complet Before/After pentru review înainte de aplicare pe cont live

> ⚠️ Acest document este DOAR pentru review. Editurile au fost deja aplicate în cod.
> Dacă vrei să revii la starea anterioară: `git revert 38d140b` (V16.4) și `git revert 6be6597` (V16.5)

---

## COMMIT V16.4 — `38d140b`
**Fișier:** `setup_executor_monitor.py`  
**Data:** 2026-05-15

---

### EDITA 1 — `_check_radar_entry()` — else branch (linia ~895)

**ÎNAINTE:**
```python
        else:
            radar_1h_distance = setup.get('radar_1h_distance_pips', 999)
            radar_4h_distance = setup.get('radar_4h_distance_pips', 999)
            reason = (
                f'Price not in 1H FVG ({radar_1h_distance:.1f} pips) '
                f'or 4H FVG ({radar_4h_distance:.1f} pips)'
            )
            return {
                'action': 'KEEP_MONITORING',
                'reason': reason
            }
```

**DUPĂ:**
```python
        else:
            # V16.4 FIX BUG#1: CHoCH radar confirmat, dar prețul NU este in FVG momentan.
            # VECHI (bug): returnăm KEEP_MONITORING → Fibo pullback nu era NICIODATĂ verificat.
            # NOU: returnăm acțiunea specială RADAR_CHOCH_NO_FVG → executorul cade pe _check_pullback_entry.
            radar_1h_distance = setup.get('radar_1h_distance_pips', 999)
            radar_4h_distance = setup.get('radar_4h_distance_pips', 999)
            
            if radar_1h_distance < radar_4h_distance:
                reason = f'Preț nu este în FVG 1H ({radar_1h_distance:.1f} pips away) — verificăm Fibo 50% fallback'
            else:
                reason = f'Preț nu este în FVG 4H ({radar_4h_distance:.1f} pips away) — verificăm Fibo 50% fallback'
            
            return {
                'action': 'RADAR_CHOCH_NO_FVG',
                'reason': reason
            }
```

**De ce:** Când CHoCH era detectat dar prețul nu era în FVG în acel moment (30s window), returna KEEP_MONITORING → logica Fibo 50% nu era NICIODATĂ apelată → loop infinit.

---

### EDITA 2 — `_process_monitoring_setups()` — handler RADAR_CHOCH_NO_FVG (linia ~1860)

**ÎNAINTE:**
```python
                        if use_radar_data:
                            result = self._check_radar_entry(setup, df_1h, symbol)
                        else:
                            result = self._check_pullback_entry(setup, df_1h, symbol)
```

**DUPĂ:**
```python
                        if use_radar_data:
                            result = self._check_radar_entry(setup, df_1h, symbol)
                            
                            # V16.4 FIX BUG#3: CHoCH radar confirmat dar preț NU în FVG
                            # → nu bloca în KEEP_MONITORING — verifică Fibo 50% pullback
                            if result.get('action') == 'RADAR_CHOCH_NO_FVG':
                                logger.info(f"🔄 {symbol}: [V16.4] Radar CHoCH dar fără FVG activ — fallback pe Fibo 50% pullback scan")
                                result = self._check_pullback_entry(setup, df_1h, symbol)
                        else:
                            result = self._check_pullback_entry(setup, df_1h, symbol)
```

**De ce:** Acțiunea `RADAR_CHOCH_NO_FVG` nouă nu era gestionată nicăieri → era tratată ca KEEP_MONITORING de default.

---

### EDITA 3 — `_check_pullback_entry()` — `max_age_candles` (linia ~987)

**ÎNAINTE:**
```python
                    confirmed_4h, valid_4h_lock, lock_reason = get_4h_body_close_confirmation(
                        df_4h=df_4h_lock,
                        daily_trend=expected_direction,
                        max_age_candles=48,  # V10.8: 12→48 bare (era prea strict)
                        debug=False,
                        detector=self.smc_detector
                    )
```

**DUPĂ:**
```python
                    confirmed_4h, valid_4h_lock, lock_reason = get_4h_body_close_confirmation(
                        df_4h=df_4h_lock,
                        daily_trend=expected_direction,
                        max_age_candles=200,  # V16.4 FIX BUG#2: 48→200 bare (era 8 zile — respingea CHoCH structurale valide mai vechi)
                        debug=False,
                        detector=self.smc_detector
                    )
```

**De ce:** 48 bare = 8 zile. CHoCH format acum 10 zile era respins → `h4_structure_locked` niciodată True → KEEP_MONITORING "Așteptăm CHoCH 4H" la infinit.

---

### EDITA 4 — READY Guard recheck — `max_age_candles` (linia ~1773)

**ÎNAINTE:**
```python
                                    if (len(df_4h_recheck) - 1 - h4rc.index) > 48:  # V10.8: 12→48 bare (era prea strict)
```

**DUPĂ:**
```python
                                    if (len(df_4h_recheck) - 1 - h4rc.index) > 200:  # V16.4 FIX BUG#4: 48→200 bare
```

**De ce:** Același limită de 48 bare era și în re-validarea READY — putea reseta setup-uri READY înapoi la MONITORING dacă CHoCH era mai vechi de 8 zile.

---
---

## COMMIT V16.5 — `6be6597`
**Fișiere:** `setup_executor_monitor.py` + `multi_tf_radar.py`  
**Data:** 2026-05-15

---

### EDITA 5 — `multi_tf_radar.py` — `_sync_to_monitoring_setups()` (linia ~660)

**ÎNAINTE:**
```python
                    # V16 FIX (B4): Propagăm h4_locked din executor în radar
                    if result.tf_4h.choch_detected:
                        setup['h4_locked'] = True
```

**DUPĂ:**
```python
                    # V16 FIX (B4): Propagăm h4_locked din executor în radar
                    # V16.5 FIX BUG#5: executor citește 'h4_structure_locked', nu 'h4_locked' — scriem ambele
                    if result.tf_4h.choch_detected:
                        setup['h4_locked'] = True
                        setup['h4_structure_locked'] = True  # V16.5: cheia pe care o citește setup_executor_monitor
```

**De ce:** Radar scria `h4_locked=True` dar executorul citea `h4_structure_locked` — chei diferite → executorul nu vedea niciodată confirmarea 4H din radar.

---

### EDITA 6 — `setup_executor_monitor.py` — P/D validation bloc 1H (linia ~775)

**ÎNAINTE:**
```python
        if radar_1h_in_fvg and radar_1h_fvg_entry and radar_1h_choch_price:
            # Folosim EQ salvat; fallback la choch_price (mai permisiv, dar corect ca direcție)
            radar_1h_eq = setup.get('radar_1h_eq') or radar_1h_choch_price
            if direction == 'buy':
                # LONG: FVG trebuie în DISCOUNT (middle sub 50% EQ al impulsului)
                zone_valid = radar_1h_fvg_entry < radar_1h_eq
                zone_type = "DISCOUNT"
            else:
                # SHORT: FVG trebuie în PREMIUM (middle peste 50% EQ al impulsului)
                zone_valid = radar_1h_fvg_entry > radar_1h_eq
                zone_type = "PREMIUM"
```

**DUPĂ:**
```python
        if radar_1h_in_fvg and radar_1h_fvg_entry and radar_1h_choch_price:
            # V16.5 FIX BUG#7: Nu mai folosim choch_price ca fallback EQ — valori complet diferite!
            # choch_price = close-ul lumânării CHoCH ≠ 50% EQ al impulsului
            # Dacă radar_1h_eq lipsește (setup pre-V16.2) → skip P/D check, permite execuția
            radar_1h_eq = setup.get('radar_1h_eq')  # None = EQ nedisponibil
            if radar_1h_eq is None:
                logger.info(f"   ℹ️ {symbol}: [V16.5] radar_1h_eq absent (setup pre-V16.2) — skip P/D check, permit execuție SNIPER")
                zone_valid = True
                zone_type = "UNKNOWN"
            elif direction == 'buy':
                # LONG: FVG trebuie în DISCOUNT (middle sub 50% EQ al impulsului)
                zone_valid = radar_1h_fvg_entry < radar_1h_eq
                zone_type = "DISCOUNT"
            else:
                # SHORT: FVG trebuie în PREMIUM (middle peste 50% EQ al impulsului)
                zone_valid = radar_1h_fvg_entry > radar_1h_eq
                zone_type = "PREMIUM"
```

**De ce:** `radar_1h_choch_price` = close-ul lumânării CHoCH ≠ 50% din impulsul CHoCH. Folosit ca EQ producea validări P/D incorecte → respingea FVG-uri valide.

---

### EDITA 7 — `setup_executor_monitor.py` — P/D validation bloc 4H (linia ~840)

**ÎNAINTE:**
```python
        elif radar_4h_in_fvg and radar_4h_fvg_entry and radar_4h_choch_price:
            # V16.2 P/D Array: 50% EQ strict pentru 4H FVG
            radar_4h_eq = setup.get('radar_4h_eq') or radar_4h_choch_price
            if direction == 'buy':
                zone_valid = radar_4h_fvg_entry < radar_4h_eq
                zone_type = "DISCOUNT"
            else:
```

**DUPĂ:**
```python
        elif radar_4h_in_fvg and radar_4h_fvg_entry and radar_4h_choch_price:
            # V16.5 FIX BUG#7: idem 1H — nu folosim choch_price ca fallback EQ pentru 4H
            radar_4h_eq = setup.get('radar_4h_eq')
            if radar_4h_eq is None:
                logger.info(f"   ℹ️ {symbol}: [V16.5] radar_4h_eq absent (setup pre-V16.2) — skip P/D check, permit execuție 4H")
                zone_valid = True
                zone_type = "UNKNOWN"
            elif direction == 'buy':
                zone_valid = radar_4h_fvg_entry < radar_4h_eq
                zone_type = "DISCOUNT"
            else:
```

**De ce:** Același motiv ca Edita 6, dar pentru blocul 4H.

---

### EDITA 8 — `setup_executor_monitor.py` — Propagare confirmări radar (linia ~1868)

**ÎNAINTE:**
```python
                            # V16.4 FIX BUG#3: CHoCH radar confirmat dar preț NU în FVG
                            # → nu bloca în KEEP_MONITORING — verifică Fibo 50% pullback
                            if result.get('action') == 'RADAR_CHOCH_NO_FVG':
                                logger.info(f"🔄 {symbol}: [V16.4] Radar CHoCH dar fără FVG activ — fallback pe Fibo 50% pullback scan")
                                result = self._check_pullback_entry(setup, df_1h, symbol)
```

**DUPĂ:**
```python
                            # V16.4 FIX BUG#3: CHoCH radar confirmat dar preț NU în FVG
                            # → nu bloca în KEEP_MONITORING — verifică Fibo 50% pullback
                            if result.get('action') == 'RADAR_CHOCH_NO_FVG':
                                logger.info(f"🔄 {symbol}: [V16.4] Radar CHoCH dar fără FVG activ — fallback pe Fibo 50% pullback scan")
                                # V16.5 FIX BUG#5+6: Propagă confirmările radar în setup
                                # Altfel executorul re-validează independent cu ATR diferit → poate eșua
                                if setup.get('radar_4h_choch_detected'):
                                    setup['h4_structure_locked'] = True     # Trust radar 4H — skip re-validation
                                    setups[i]['h4_structure_locked'] = True
                                    logger.info(f"   ✅ [V16.5 BUG#5] {symbol}: h4_structure_locked=True propagat din radar")
                                # V16.5 FIX BUG#8: Propagă și 1H CHoCH din radar
                                if setup.get('radar_1h_choch_detected') and not setup.get('choch_1h_detected'):
                                    setup['choch_1h_detected'] = True
                                    setup['choch_1h_timestamp'] = setup.get('radar_1h_choch_time', datetime.now(timezone.utc).isoformat())
                                    setups[i]['choch_1h_detected'] = True
                                    setups[i]['choch_1h_timestamp'] = setup['choch_1h_timestamp']
                                    logger.info(f"   ✅ [V16.5 BUG#8] {symbol}: choch_1h_detected=True propagat din radar")
                                result = self._check_pullback_entry(setup, df_1h, symbol)
```

**De ce:** Fără propagare, `_check_pullback_entry` nu vedea confirmarea radar → re-rula `get_4h_body_close_confirmation()` cu ATR 0.6x (diferit de radar 1.0x) → putea eșua → KEEP_MONITORING.

---

## 📊 SUMAR TOATE EDITURILE

| # | Fișier | Funcție | Ce schimbă | Bug rezolvat |
|---|--------|---------|------------|--------------|
| 1 | setup_executor_monitor.py | `_check_radar_entry` else | `KEEP_MONITORING` → `RADAR_CHOCH_NO_FVG` | BUG#1 |
| 2 | setup_executor_monitor.py | `_process_monitoring_setups` | Handler `RADAR_CHOCH_NO_FVG` → fallback Fibo | BUG#3 |
| 3 | setup_executor_monitor.py | `_check_pullback_entry` | `max_age_candles=48` → `200` | BUG#2 |
| 4 | setup_executor_monitor.py | READY guard | `> 48` → `> 200` | BUG#4 |
| 5 | multi_tf_radar.py | `_sync_to_monitoring_setups` | Adaugă `h4_structure_locked=True` | BUG#5 |
| 6 | setup_executor_monitor.py | `_check_radar_entry` 1H P/D | EQ fallback corect: None → skip check | BUG#7 |
| 7 | setup_executor_monitor.py | `_check_radar_entry` 4H P/D | EQ fallback corect: None → skip check | BUG#7 |
| 8 | setup_executor_monitor.py | `_process_monitoring_setups` | Propagare `h4_structure_locked` + `choch_1h_detected` din radar | BUG#6+8 |

---

## 🔄 CUM SĂ REVII LA STAREA ANTERIOARĂ (dacă vrei)

```powershell
# Pe VPS — revin la versiunea dinainte de V16.4 (commit anterior: 8c556c2)
git revert 6be6597  # Revert V16.5
git revert 38d140b  # Revert V16.4
git push origin main
```

Sau mai simplu — revin la ultima versiune stabilă V16.3:
```powershell
git reset --hard 8c556c2
git push origin main --force
```

> ⚠️ `--force` suprascrie istoricul remote. Folosește cu atenție.

---

## ❓ CE NU AM SCHIMBAT (intentionat)

- `smc_detector.py` — nicio modificare
- `multi_tf_radar.py` — o singură linie adăugată (Edita 5)
- Logica de calcul SL/TP — neatinsă
- Risk Manager — neatins
- Logica de execuție finală `_execute_entry` — neatinsă
- Fibo 50% calculation `calculate_choch_fibonacci` — neatinsă
- Blackout hour filter (10:00 UTC) — neatins

---

**Commits:**
- V16.4: `38d140b` — 4 edituri în setup_executor_monitor.py
- V16.5: `6be6597` — 4 edituri în setup_executor_monitor.py + 1 în multi_tf_radar.py
