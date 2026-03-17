# 🚀 DEPLOY CHECKLIST — Глитч Ин Матрикс VPS (Vultr Windows)
**Глитч Ин Матрикс V11.0 — Production Deployment Guide**

────────────────
🔱 AUTHORED BY ФорексГод 🔱
────────────────
🏛️  Глитч Ин Матрикс  🏛️

---

## ✅ PRE-DEPLOY AUDIT RESULTS

### 🔍 Path Analysis
| File | Status | Note |
|------|--------|------|
| `ctrader_executor.py` | ✅ CLEAN | Uses `Path(__file__).parent` — portable |
| `realtime_monitor.py` | ✅ CLEAN | Uses relative `Path("monitoring_setups.json")` |
| `setup_executor_monitor.py` | ✅ CLEAN | Uses `Path(__file__).parent.resolve()` |
| `telegram_command_center.py` | ✅ CLEAN | Uses `Path(__file__).parent.resolve()` |
| `watchdog_monitor.py` | ✅ CLEAN | Uses relative paths |
| `unified_risk_manager.py` | ✅ CLEAN | Uses relative paths |
| `daily_scanner.py` | ✅ FIXED | Was hardcoded → now `Path(__file__).parent` |
| `path_finder.py` | ⚠️ SKIP | Dev utility only — not used in production |
| `test_*.py` | ⚠️ SKIP | Test files only — not needed on VPS |

### 🏛️ Branding Audit
| Module | Status |
|--------|--------|
| `watchdog_monitor.py` | ✅ `🏛️  **Глитч Ин Матрикс**  🏛️` (bold + spacing) |
| `telegram_command_center.py` | ✅ `🏛️  **Глитч Ин Матрикс**  🏛️` (bold + spacing) |
| `realtime_monitor.py` | ✅ `🏛️  **Глитч Ин Матрикс**  🏛️` (bold + spacing) |
| `setup_executor_monitor.py` | ✅ `🏛️  **Глитч Ин Матрикс**  🏛️` (bold + spacing) |
| `ctrader_executor.py` | ✅ present (no bold — secondary module) |
| `unified_risk_manager.py` | ✅ present (no bold — secondary module) |

---

## 📁 STEP 1 — FILES TO TRANSFER (Core Production)

### 🔴 CRITICAL — Must Have
```
watchdog_monitor.py
setup_executor_monitor.py
telegram_command_center.py
realtime_monitor.py
ctrader_executor.py
daily_scanner.py
unified_risk_manager.py
position_monitor.py
ctrader_sync_daemon.py
notification_manager.py
smc_detector.py
```

### 🟡 REQUIRED — Support Modules
```
requirements.txt
.env                    ← FILL IN on server (never commit credentials)
SUPER_CONFIG.json
pairs_config.json
```

### 🟢 DATA FILES — Create fresh on server (or transfer)
```
monitoring_setups.json  ← transfer current setups OR create empty: {"setups": [], "last_updated": ""}
signals.json            ← create empty: []
active_positions.json   ← create empty: []
trade_history.json      ← transfer or create empty: {"open_positions": [], "account": {}}
data/account_stats.json ← transfer (contains total_withdrawals)
```

### 📊 OPTIONAL — Dashboards
```
dashboard_pro.html
dashboard_live.html
data/trades.db          ← transfer for trade history
```

---

## ⚙️ STEP 2 — VPS SETUP (Windows + Python)

### Install Python 3.11+ (recommended for Windows VPS)
```powershell
# Download from python.org/downloads
# ✅ CHECK "Add Python to PATH" during install
python --version
```

### Create virtual environment
```powershell
cd C:\GlitchMatrix
python -m venv .venv
.venv\Scripts\activate
```

### Install dependencies
```powershell
pip install -r requirements.txt
```

> ⚠️ **MetaTrader5** package: Only available on Windows. If needed:
> ```powershell
> pip install MetaTrader5
> ```
> If NOT using MT5 (cTrader only): skip it — not required.

---

## 🔑 STEP 3 — Configure .env

Create `.env` in project root with:
```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
TELEGRAM_USER_ID=6420069284
TELEGRAM_ENABLED=True

# cTrader API
CTRADER_CLIENT_ID=your_client_id
CTRADER_CLIENT_SECRET=your_client_secret
CTRADER_ACCOUNT_ID=9709773
CTRADER_ACCESS_TOKEN=your_access_token

# Twelve Data (market data)
TWELVE_DATA_API_KEY=your_key_here
```

---

## 🚀 STEP 4 — START-UP SEQUENCE (Windows)

> Run each in a **separate PowerShell window** or use `start` command

### 1. Watchdog (FIRST — System Guardian)
```powershell
cd C:\GlitchMatrix
.venv\Scripts\python watchdog_monitor.py --interval 60
```

### 2. Setup Executor Monitor (Core Scanner)
```powershell
cd C:\GlitchMatrix
.venv\Scripts\python setup_executor_monitor.py --interval 30 --loop
```

### 3. Position Monitor
```powershell
cd C:\GlitchMatrix
.venv\Scripts\python position_monitor.py
```

### 4. Telegram Command Center
```powershell
cd C:\GlitchMatrix
.venv\Scripts\python telegram_command_center.py
```

### 5. cTrader Sync Daemon
```powershell
cd C:\GlitchMatrix
.venv\Scripts\python ctrader_sync_daemon.py
```

### 6. Dashboard Server (optional)
```powershell
cd C:\GlitchMatrix
.venv\Scripts\python -m http.server 8000
```

---

## 🎯 STEP 5 — signals.json Path for cBot

The cTrader cBot (`PythonSignalExecutor`) reads `signals.json` from:
```
C:\GlitchMatrix\signals.json
```

In cTrader cBot settings, set the parameter:
```
Signal File Path: C:\GlitchMatrix\signals.json
```

The executor writes to: **`<project_root>/signals.json`** (auto-detected via `Path(__file__).parent`).

> ✅ As long as the project is in `C:\GlitchMatrix\`, no path changes needed in code.

---

## 🔒 STEP 6 — Windows Auto-Start (Optional)

To auto-start all processes on server reboot, create a batch file `start_all.bat`:
```batch
@echo off
cd C:\GlitchMatrix
start "Watchdog" .venv\Scripts\python watchdog_monitor.py --interval 60
timeout /t 3
start "SetupExecutor" .venv\Scripts\python setup_executor_monitor.py --interval 30 --loop
timeout /t 2
start "PositionMonitor" .venv\Scripts\python position_monitor.py
timeout /t 2
start "CommandCenter" .venv\Scripts\python telegram_command_center.py
timeout /t 2
start "SyncDaemon" .venv\Scripts\python ctrader_sync_daemon.py
echo All processes started!
```

Add `start_all.bat` to Windows Task Scheduler → Run at startup.

---

## ✅ STEP 7 — Verification

After startup, send `/status` in Telegram. Expected response:
```
✅ Setup Monitor: ONLINE
✅ Position Monitor: ONLINE
✅ Command Center: ONLINE
✅ Realtime Monitor: ONLINE
✅ cTrader Sync: ONLINE
```

---

## ⚠️ KNOWN ISSUES & NOTES

| Issue | Status | Note |
|-------|--------|------|
| BTC lot bypass | 🟡 INTENTIONAL | `lot_size = 0.50` hardcoded in `ctrader_executor.py` ~line 527 |
| `path_finder.py` | ⚠️ SKIP | Has hardcoded `/Users/` path — dev utility only |
| `test_*.py` files | ⚠️ SKIP | All test files have hardcoded paths — not needed on VPS |
| `start_execution*.py` | ⚠️ SKIP | Old launcher scripts — replaced by `watchdog_monitor.py` |

---

## 📋 QUICK COPY-PASTE: Files to skip on VPS

```
path_finder.py
start_execution.py
start_execution_v2.py
test_*.py
view_dashboard_status.py
*.log (regenerate fresh)
.venv/ (recreate on server)
__pycache__/
```

---

**Generated:** 17 March 2026
**Version:** Глитч Ин Матрикс V11.0
**Status:** ✅ Ready for VPS Deployment

────────────────
🔱 AUTHORED BY ФорексГод 🔱
────────────────
🏛️  Глитч Ин Матрикс  🏛️
