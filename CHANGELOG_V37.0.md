# CHANGELOG V37.0 — Dead Code Cleanup & Architectural Alignment

Branch: `cursor/v36-3-radar-live-sync`  
Base: V36.5 Always-On H4/H1 Radar

## Sprint 1 — Dead code removal (zero risk)

### Șters
- `setup_executor_monitor.py`: ~937 linii unreachable în `_check_radar_entry()` / `_check_pullback_entry()` (stub V31 păstrat, 5 linii fiecare)
- `multi_tf_radar.py`: `_daily_target_v31` orphan, enum `WAITING_DAILY_FVG`, dead branch `daily_zone_validated` în `print_result`, imports duplicate `sys`/`io`/`time`
- `daily_scanner.py`: `is_gbp` orphan, bloc TZ comentat V11.2

### Păstrat intact
- `detect_choch_and_bos()` Body Close logic
- V36.5 P/D Guard (blochează EXECUTE, nu scanarea)
- Trigger A/B, REVERSAL guard, RR Shield, Poarta 1

### Line count (before → after)
| Fișier | Before | After | Δ |
|--------|--------|-------|---|
| setup_executor_monitor.py | 3316 | 2381 | −935 |
| multi_tf_radar.py | 2094 | 2067 | −27 |
| daily_scanner.py | 1117 | 1107 | −10 |

## Sprint 2 — Architectural alignment (medium risk)

### Unificat
- `pip_utils.get_pip_size()` — sursă unică pentru XTI/BTC/XAU/JPY/Forex (Radar + Executor Guard#1 RR)
- `strategy_type` — exclusiv logica V25.0 UNIVERSAL BIAS (index CHoCH vs BOS); `detect_strategy_type()` + `_analyze_pre_choch_structure()` eliminate ca dead code

### Comportament modificat
- **EXECUTE_NOW**: prioritate `h4_sl_price` + `daily_tp_price` din JSON Radar → recalc structural 4H/D1 → `stop_loss`/`take_profit` Scanner → ATR ultim resort
- **Entry 2 scale-in**: dezactivat complet (`validate_choch_confirmation_scale_in` neapelat)

### Line count
| Fișier | Sprint 1 end | Sprint 2 end | Δ |
|--------|--------------|--------------|---|
| setup_executor_monitor.py | 2381 | 2272 | −109 |
| smc_detector.py | 5686 | 5397 | −289 |
| pip_utils.py | — | 15 | +15 (new) |

## Sprint 3 — Hardening

### Șters
- `smc_detector._adaptive_lookback()` (DEPRECATED V11.2, zero apeluri)

### Îmbunătățit
- `except: pass` → `logger.warning` în locații prioritare: `multi_tf_radar.py`, `daily_scanner.py`, `setup_executor_monitor.py` (spread guard, equilibrium calc, Poarta 1 price, Guard#3 balance)
- Docstring header `setup_executor_monitor.py` actualizat la arhitectura V31/V36 Radar-only

## VPS test checklist (post-pull + restart watchdog)

```powershell
git pull origin cursor/v36-3-radar-live-sync
# Remove lock if needed: del process_telegram_command_center.lock
python scripts/verify_v365_radar.py
python multi_tf_radar.py --symbol XTIUSD
python multi_tf_radar.py --symbol GBPJPY
python multi_tf_radar.py --symbol GBPNZD
```

Verifică în `monitoring_setups.json` pentru fiecare simbol:
- [ ] `pd_guard_passed` / `pd_guard_reason` prezente (V36.5)
- [ ] `h4_structure_locked` setat când EXECUTE_NOW=True
- [ ] `h4_sl_price` + `daily_tp_price` populate de Radar
- [ ] Log `[V36.5 SCAN DONE]` chiar când P/D blochează EXECUTE
- [ ] XTIUSD: RR Guard#1 folosește pip_size=0.01 (nu 0.0001)
- [ ] Executor: `[V37.0 JSON PRIORITY]` la EXECUTE_NOW când JSON valid
- [ ] Fără `[V14.1 SCALE-IN]` / Entry 2 în logs

## Deploy

**Mac:** `git push origin cursor/v36-3-radar-live-sync`  
**VPS:** `git pull` + restart watchdog/radar/executor (un singur executor via watchdog)
