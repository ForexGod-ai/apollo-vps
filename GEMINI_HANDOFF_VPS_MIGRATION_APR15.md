# 🤖 GEMINI HANDOFF DOCUMENT — VPS MIGRATION SESSION
## Glitch in Matrix Trading System • April 15, 2026
### Authored by: GitHub Copilot (Claude Sonnet 4.6) • For: ФорексГод

---

## 1. CONTEXT GENERAL

Sistemul "Glitch in Matrix" a fost migrat de pe **Mac local** (macOS, `/Users/forexgod/Desktop/...`) pe un **Windows VPS în Helsinki** (`C:\Users\Administrator\Desktop\Glitch in Matrix\trading-ai-agent apollo\`).

- **Broker**: IC Markets cTrader
- **Cont live**: Account ID `6139026` (veteran live account)
- **Python**: 3.x, venv la `.venv\Scripts\python.exe` (Windows)
- **cTrader cBot**: `PythonSignalExecutor` (~1000 linii C#), compilat și activ
- **cTrader servere HTTP active**: port `8767` (DATA-Market), port `8768` (CalendarBOT Health Check)

---

## 2. FIȘIERE MODIFICATE ÎN ACEASTĂ SESIUNE

### 2.1 `PythonSignalExecutor_VPS.cs` ← NOU (creat din zero)
**Locație**: `C:\Users\Administrator\Desktop\Glitch in Matrix\trading-ai-agent apollo\PythonSignalExecutor_VPS.cs`

**Ce s-a schimbat față de versiunea Mac:**
- **O singură modificare chirurgicală** — path-ul din `[Parameter]`:

```csharp
// ÎNAINTE (Mac):
[Parameter("Signal File Path", DefaultValue = "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/signals.json")]

// DUPĂ (Windows VPS):
[Parameter("Signal File Path", DefaultValue = @"C:\Users\Administrator\Desktop\Glitch in Matrix\trading-ai-agent apollo\signals.json")]
```

**Zero modificări la logica de trading.** Păstrat intact:
- V7.0 Array Protocol (List<TradeSignal>)
- V7.1 Duplicate Position Guard
- V8.0 Close Position Handler (`Action="CLOSE"`)
- V9.3 BTC Nuclear Option (double type fix, 0.50 lots preserved)
- V9.4 Direction synonyms (SHORT/SELL/PUT/BEARISH → Sell)
- V10.2 Live Sync (`WriteAccountStatus()` → `account_info.json`)
- SMC Intelligence Display (Liquidity Sweeps, Order Block scoring)
- SL/TP Zero Guard (non-crypto: pips; crypto: absolute price)
- `ExportActivePositions()` → `active_positions.json`

---

### 2.2 `SUPER_CONFIG.json` ← MODIFICAT
**Locație**: `C:\Users\Administrator\Desktop\Glitch in Matrix\trading-ai-agent apollo\SUPER_CONFIG.json`

**Modificări aplicate:**

| Câmp | Valoare veche | Valoare nouă |
|------|--------------|--------------|
| `system_info.version` | `"3.1"` | `"3.2"` |
| `system_info.last_updated` | `"2026-02-04"` | `"2026-04-15"` |
| `system_info.environment` | *(absent)* | `"Windows VPS Helsinki"` |
| `account.account_id` | *(absent)* | `"6139026"` |
| `account.broker` | *(absent)* | `"IC Markets"` |
| `paths.base_dir` | *(absent)* | `"C:\\Users\\Administrator\\Desktop\\Glitch in Matrix\\trading-ai-agent apollo\\"` |
| `paths.signals_path` | *(absent)* | `"C:\\Users\\Administrator\\Desktop\\Glitch in Matrix\\trading-ai-agent apollo\\signals.json"` |
| `paths.history_path` | *(absent)* | `"C:\\Users\\Administrator\\Desktop\\Glitch in Matrix\\trading-ai-agent apollo\\trade_history.json"` |
| `paths.active_positions_path` | *(absent)* | `"C:\\Users\\Administrator\\Desktop\\Glitch in Matrix\\trading-ai-agent apollo\\active_positions.json"` |

**Notă**: Telegram credentials (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) NU sunt în SUPER_CONFIG.json — se află în `.env` (variabile de mediu). Copiat separat pe VPS.

**Toate setările de trading rămân neschimbate:**
- `risk_per_trade_percent`: 5.0%
- `max_open_positions`: 5
- `max_positions_per_symbol`: 2 (Entry 1 + scale-in Entry 2)
- `entry2_risk_percent`: 7.5% (1.5× Entry 1)
- `max_daily_loss_percent`: 10.0% (kill switch trigger)
- `spread_guard.max_spread_pips`: 2.5
- Rollover window: 00:00–01:05 EET

---

### 2.3 `unified_risk_manager.py` ← MODIFICAT (1 linie)
**Locație**: `C:\Users\Administrator\Desktop\Glitch in Matrix\trading-ai-agent apollo\unified_risk_manager.py`

**Modificare**: Linia ~418, funcția `get_open_positions_count()`:

```python
# ÎNAINTE:
if age_seconds > 10:
    print(f"⚠️  account_info.json is {age_seconds:.0f}s old (cBot may be offline!)")

# DUPĂ (VPS optimization):
if age_seconds > 30:  # VPS: relaxed to 30s (cBot + Python on same machine)
    print(f"⚠️  account_info.json is {age_seconds:.0f}s old (cBot may be offline!)")
```

**Motivul**: Pe Mac cu internet de acasă, cBot scria `account_info.json` și Python îl citea cu latență variabilă → warning fals la 10s. Pe VPS, cBot și Python sunt pe **aceeași mașină**, deci 30s e suficient de strict fără noise.

---

### 2.4 `start_all_monitors.bat` ← NOU (creat)
**Locație**: `C:\Users\Administrator\Desktop\Glitch in Matrix\trading-ai-agent apollo\start_all_monitors.bat`

**Scop**: Echivalentul Windows al `start_all_monitors.sh` (care mergea doar pe Mac/Linux).

**Ce face**: Pornește toate 7 monitoare cu dublu-click:
1. `ctrader_sync_daemon.py --loop`
2. `position_monitor.py --loop`
3. `setup_executor_monitor.py --interval 30 --loop` ← **COMANDANTUL**
4. `telegram_command_center.py`
5. `news_calendar_monitor.py`
6. `news_reminder_engine.py`
7. `watchdog_monitor.py --interval 60`

Fiecare pornim într-o fereastră minimizată separată (`start "name" /MIN`). Log-urile merg în folderul `logs\`.

---

## 3. ARHITECTURA SISTEMULUI — FLOW COMPLET

```
[CRON ZILNIC]
    daily_scanner.py
        └─► smc_detector.py (V13.0 Regula Generalului + V12.1 SL/TP Structural)
                └─► monitoring_setups.json  (setups MONITORING)

[24/7 — COMANDANTUL]
    setup_executor_monitor.py --interval 30 --loop
        ├─► citește monitoring_setups.json
        ├─► verifică CHoCH 4H body closure (V10.6)
        ├─► Dynamic Frequency: 30s normal / 5s automat când setup IN ZONE
        ├─► scrie signals.json
        └─► cTrader cBot PythonSignalExecutor
                ├─► ExecuteMarketOrder()
                ├─► scrie account_info.json (V10.2 Live Sync)
                ├─► scrie active_positions.json
                └─► scrie execution_report.json (Two-Way Handshake)

[SERVICII SUPORT 24/7]
    position_monitor.py        → notificări SL/TP hit pe Telegram
    ctrader_sync_daemon.py     → sincronizează trade_history.json
    telegram_command_center.py → comenzi manuale via Telegram
    news_calendar_monitor.py   → monitorizează știri HIGH impact
    news_reminder_engine.py    → reminder 15min înainte de NFP/CPI etc.
    watchdog_monitor.py        → repornire automată dacă un monitor moare
    unified_risk_manager.py    → validare risc înainte de execuție
```

---

## 4. IDENTIFICAREA "COMANDANTULUI" — RAȚIONAMENTUL

Utilizatorul a întrebat care fișier este "main.py" / punctul de intrare. Nu există `main.py` — arhitectura e microservicii. **Comandantul real** este `setup_executor_monitor.py` din aceste motive:

1. **2111 linii** — cel mai mare și complex fișier operațional
2. **Importă din toți ceilalți**: `CTraderExecutor`, `CTraderDataProvider`, `SMCDetector`, `TelegramNotifier`, `SignalCache`
3. **Singura componentă care scanează piața live** și decide execuția
4. **Scrie `signals.json`** — fișierul pe care cBot îl citește pentru ordine
5. **Dynamic Frequency built-in**: se accelerează automat la 5s când un setup e IN ZONE

Celelalte candidate:
- `watch_live_updates.py` (86 linii) — utility de display pentru `trade_history.json`, nu execută nimic
- `monitoring_radar.py` (341 linii) — display-only, vizualizează distanța până la FVG
- `unified_risk_manager.py` (912 linii) — validare și gardă de risc, nu scanează piața

---

## 5. STATUS COMPONENTE SMC (din sesiunile anterioare — ACTIV)

### `smc_detector.py` — V13.0 + V12.1
- **V13.0 Regula Generalului**: CHoCH Bullish valid DOAR dacă un bar D1 închide cu BODY-ul deasupra "Generalului" (ultimul Swing High înainte de Bearish BOS). Elimină false CHoCH bazate pe procente (V12.0 eliminat complet).
- **V12.1 SL/TP Structural**: SL = wick-ul ultimului 4H swing High/Low ÎNAINTE de CHoCH + 1 pip buffer. TP = cel mai apropiat D1 swing Low/High dincolo de prețul curent (nu extrema din 200 bare).
- **Rezultat pe EURJPY**: SL 83 pips (vs 207 pips în V11.2), Generalul @ 186.236 intact → bias corect BEARISH.

### `daily_scanner.py` — V13.0 Sniper Alignment + V11.0 Conflict Guard
- **Sniper Alignment**: compară `h4_choch.direction` vs `daily_choch.direction`. D1 Bearish + 4H CHoCH Bullish = ❌ REJECTAT (retragere). D1 Bearish + 4H CHoCH Bearish = ✅ VALID.
- **Conflict Guard V11.0**: blochează setup-uri opuse pozițiilor deschise.

---

## 6. FIȘIERE IMPORTANTE PE VPS — CHECKLIST

```
✅ SUPER_CONFIG.json          — configurat pentru VPS (paths + account_id)
✅ PythonSignalExecutor_VPS.cs — cBot cu path Windows, compilat în cTrader
✅ start_all_monitors.bat      — pornire cu dublu-click
✅ unified_risk_manager.py    — freshness threshold 30s (VPS optimizat)
⚠️  .env                      — TREBUIE copiat manual (nu în Git!)
                                 Conține: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
                                          CTRADER_ACCOUNT_ID, etc.
⚠️  data/upcoming_news.json   — actualizat manual la început de lună
⚠️  monitoring_setups.json    — generat de daily_scanner.py
```

---

## 7. COMENZI RAPIDE PE VPS (PowerShell)

```powershell
# Pornire completă sistem:
.\start_all_monitors.bat

# Rulare scanner zilnic manual:
.venv\Scripts\python.exe daily_scanner.py

# Verificare status monitoare:
Get-Process python | Select-Object Id, CPU, WorkingSet, StartTime

# Verificare log comandant:
Get-Content logs\setup_executor_monitor.log -Tail 50 -Wait

# Test conexiune cTrader API:
.venv\Scripts\python.exe -c "from ctrader_cbot_client import CTraderCBotClient; c = CTraderCBotClient(); print(c.get_price('EURUSD'))"
```

---

## 8. NEXT STEPS RECOMANDATE (pentru Gemini)

1. **Remote SSH setup** — configurează VS Code Remote SSH de pe Mac pentru a edita direct pe VPS (extensia `ms-vscode-remote.remote-ssh`)
2. **Git repo privat** — pentru sync Mac ↔ VPS și backup cod (`.env` în `.gitignore`!)
3. **Task Scheduler Windows** — înlocuiește `.bat` manual cu pornire automată la reboot VPS (echivalentul `launchd` plist de pe Mac)
4. **`add_monthly_events.py`** — scriptul e hardcodat pentru ianuarie 2026, trebuie actualizat pentru generare dinamică pe luna curentă
5. **`daily_scanner.py` cron pe Windows** — echivalentul `cron` pe Windows e Task Scheduler, setează scanul zilnic la 08:00 UTC

---

*Document generat de GitHub Copilot (Claude Sonnet 4.6) • Session April 15, 2026*
