# 🪟 Windows VPS Deployment — Ghid Complet
**Glitch in Matrix V13.1 · Hetzner CPX41 "Tancul German" · Updated: April 2026**

---

## 📋 CUPRINS RAPID

1. [De Ce Windows VPS](#de-ce-windows)
2. [VPS Recomandat — Vultr](#vps-recomandat)
3. [Conectare RDP](#conectare-rdp)
4. [Deploy Automat — PowerShell Script](#deploy-automat)
5. [Transfer Fișiere Mac → VPS](#transfer-fisiere)
6. [Configurare .env](#configurare-env)
7. [cTrader Setup](#ctrader-setup)
8. [Pornire Sistem](#pornire-sistem)
9. [Test Final](#test-final)
10. [Monitorizare & Mentenanță](#monitorizare)

---

<a name="de-ce-windows"></a>
## 🎯 1. DE CE WINDOWS VPS?

### Problema cu Linux VPS

❌ **cTrader Desktop NU rulează pe Linux**
❌ **cBot-ul (MarketDataProvider) = Windows only**
❌ **Alternativa Linux = refactoring complet (zile de muncă)**

### Soluția Windows VPS

✅ **Zero modificări cod** — sistemul rămâne identic cu Mac-ul tău
✅ **cTrader Desktop native** — instalare directă
✅ **Remote Desktop (RDP)** — acces GUI complet
✅ **Windows Task Scheduler** — auto-start la boot inclus în script
✅ **signals.json IPC bridge** — cBot ↔ Python fără modificări

### Arhitectura Sistemului pe VPS

```
┌─────────────────────────────────────────────────────────────┐
│               Windows VPS (Hetzner CPX41 🇩🇪)               │
│                                                             │
│  ┌─────────────────┐      ┌──────────────────────────────┐  │
│  │  cTrader Desktop│      │   Python Monitors            │  │
│  │                 │      │                              │  │
│  │  cBot:          │      │  watchdog_monitor.py         │  │
│  │  MarketData     │◄────►│  setup_executor_monitor.py   │  │
│  │  Provider       │      │  position_monitor.py         │  │
│  │  :8767          │      │  telegram_command_center.py  │  │
│  └────────┬────────┘      │  news_calendar_monitor.py    │  │
│           │               │  ctrader_sync_daemon.py      │  │
│           │               └──────────────────────────────┘  │
│           │                            │                     │
│           └──── C:\matrix\signals.json ┘                     │
│                     (IPC bridge)                             │
└─────────────────────────────────────────────────────────────┘
           │                              │
           ▼                              ▼
    IC Markets Live               Telegram Bot
    (cTrader broker)             Notificări 24/7
```

---

<a name="vps-recomandat"></a>
## 💻 2. VPS — HETZNER CPX41 🇩🇪 "TANCUL GERMAN"

### ⭐ Planul Ales: CPX41 High Performance

**Link:** https://www.hetzner.com/cloud/

| Componentă | Specificație |
|------------|-------------|
| **CPU** | **8 vCPUs (AMD EPYC)** |
| **RAM** | **16 GB** |
| **Storage** | **240 GB NVMe SSD** |
| **Network** | 20 TB/lună |
| **OS** | Windows Server 2022 (via ISO manual) |
| **Location** | Nuremberg / Helsinki (EU) |
| **Cost** | ~€28/lună (~50% mai ieftin decât planul anterior) |

> ⚠️ **IMPORTANT — Instalare Windows via ISO:**
> Hetzner NU oferă Windows Server prin One-Click Install.
> Windows Server 2022 se montează **manual via ISO Image** din Hetzner Console.
> Vezi **Pasul 2B** mai jos pentru procedura completă.

**De ce CPX41 e superior:**
- ✅ **16 GB RAM** — cTrader (~1.5GB) + 6 monitors (~800MB) + Windows (~3GB) + **buffer 10.7 GB** pentru caching agresiv SMC
- ✅ **8 vCPUs AMD EPYC** — dublu față de planul anterior; `daily_scanner.py` poate rula pairs în ThreadPoolExecutor paralel
- ✅ **240 GB NVMe** — logs detaliate fără limitare spațiu (vs. 200 GB anterior)
- ✅ **AMD EPYC** — arhitectură server real, nu vCPU virtualizat generic

### Pași comandă Hetzner:
1. Creează cont: https://console.hetzner.cloud
2. **New Project** → New Server
3. Location: **Nuremberg (EU-Central)** sau **Helsinki**
4. OS Image: **Linux (oricare)** — îl vom înlocui cu Windows via ISO
5. Type: **CPX41** (8 vCPU / 16 GB)
6. **Create & Buy** → server activ în ~30 secunde

### Pasul 2B — Montare Windows Server 2022 via ISO:
```
1. Hetzner Console → Server → ISO Images
2. Search: "Windows Server 2022" → Mount ISO
3. Power → Reset (Force Reset)
4. Console (VNC) → urmează wizard instalare Windows:
   - Language: English
   - Edition: Windows Server 2022 Standard (Desktop Experience)
   - Custom Install → Select Disk → Next
5. Wait ~15 min → Windows boots
6. Set Administrator password
7. Unmount ISO → Hetzner Console → ISO → Unmount
8. RDP enabled by default pe Windows Server 2022
```

> 💡 **Alternativă rapidă:** Cumpără licență Windows Server 2022 (~€15 one-time de pe un reseller) sau activează cu KMS server public pentru test.

---

<a name="conectare-rdp"></a>
## 🔐 3. CONECTARE REMOTE DESKTOP (RDP)

### Credentials din Hetzner Console

```
IP:       [VPS_IP din Hetzner → Server → Overview]
Username: Administrator
Password: [setat de tine la instalarea Windows]
Port:     3389 (default)
```

### Conectare de pe Mac

**1. Descarcă Microsoft Remote Desktop (gratuit):**
```
App Store → "Microsoft Remote Desktop" → Install
```

**2. Configurare:**
```
1. Open Microsoft Remote Desktop
2. "Add PC"
3. PC name: [IP_VPS]
4. User account → Add:
   Username: Administrator
   Password: [parola setată la install ISO]
5. Save → Double-click → Connect
6. La warning certificate → "Continue"
```

### Test conexiune (Terminal Mac):
```bash
ping [IP_VPS]
# Trebuie: time < 30ms pentru Frankfurt
```

---

<a name="max-performance"></a>
## 🚀 3B. MAX PERFORMANCE MODE — 16 GB RAM + 8 vCPU

> **Aceste setări sunt specifice Hetzner CPX41. Nu le aplica pe mașini cu RAM < 8 GB.**

### 1. Caching Agresiv SMC (smc_detector.py)
Cu 16 GB RAM disponibil, cache-ul V13.1 poate fi extins fără nicio limitare de memorie.
Toate cele 3 cache-uri (`_swing_highs_cache`, `_swing_lows_cache`, `_choch_bos_cache`) rețin
rezultatele pentru **toate pair-urile din sesiune** — nu doar pentru pair-ul curent.

De setat în `smc_detector.py` → `__init__`:
```python
# MAX PERFORMANCE MODE (Hetzner CPX41 — 16 GB RAM)
# Cache-ul nu se mai golește între pair-uri — reduce ~90% compute time
self.CACHE_MAX_ENTRIES = 500   # default era 50
self.CACHE_PERSIST_ACROSS_PAIRS = True  # default era False
```
> Notă: Modificarea aceasta este opțională dacă vrei să implementezi manual. Comportamentul
> actual V13.1 (clear cache per pair) rămâne correct — aceasta e o optimizare viitoare.

### 2. Multi-Threading — daily_scanner.py
Cu 8 vCPU AMD EPYC, scanarea celor 15+ perechi poate rula în paralel.
Adaugă în `daily_scanner.py` → `run_daily_scan()` (opțional, nu obligatoriu pentru launch):

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

# Scanare paralelă (MAX 4 workers — cTrader API are rate limit)
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {
        executor.submit(self._scan_single_pair, pair_config): pair_config
        for pair_config in self.pairs
    }
    for future in as_completed(futures):
        result = future.result()
        if result:
            setups_found.append(result)
```
> ⚠️ **Launch Day**: Rulează secvențial (cod actual) pentru primul deployment.
> Threading se activează după ce confirmi că totul funcționează pe VPS.

### 3. Logging Detaliat (240 GB NVMe)
Cu 240 GB spațiu, activează logging complet în `loguru`:

```python
# În fiecare monitor, înlocuiește configurarea loguru cu:
logger.add(
    "logs/{name}.log",
    rotation="50 MB",    # Rotație la 50 MB (era 10 MB)
    retention="90 days", # Păstrare 90 zile (era 30 zile)
    level="DEBUG",       # DEBUG complet (era INFO)
    compression="zip",   # Compresie automată fișiere vechi
    enqueue=True         # Thread-safe async logging
)
```

Sau prin variabila de mediu în `.env`:
```env
LOG_LEVEL=DEBUG
LOG_ROTATION=50MB
LOG_RETENTION=90days
```

---

<a name="deploy-automat"></a>
## ⚡ 4. DEPLOY AUTOMAT — POWERSHELL SCRIPT

**`vps_deploy_windows.ps1` — Face TOTUL automat, rulează o singură dată.**

### Ce face scriptul:

| Fază | Acțiune |
|------|---------|
| **Phase 1** | Instalare Python 3.11.9 (silent, adăugat la PATH) |
| **Phase 2** | Creare `C:\matrix\` + subdirectoare + `signals.json` cu FullControl (IPC bridge) |
| **Phase 3** | Creare `.venv` + instalare toate dependențele Python |
| **Phase 4** | Download + instalare cTrader Desktop |
| **Phase 5** | Creare `start_matrix.bat` + înregistrare Task Scheduler (auto-start la logon) |

### Cum rulezi:

```powershell
# PowerShell pe VPS (Run as Administrator):
Set-ExecutionPolicy Bypass -Scope Process -Force
cd C:\matrix
.\vps_deploy_windows.ps1
```

> ⚠️ **Rulează după ce ai transferat fișierele în `C:\matrix\`**

---

<a name="transfer-fisiere"></a>
## 📤 5. TRANSFER FIȘIERE MAC → VPS

### Metoda Recomandată: ZIP via Google Drive

**Pe Mac (Terminal):**
```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

# Creează arhivă (exclude cache, logs, venv)
zip -r glitch_matrix.zip . \
  -x "*.pyc" \
  -x "**/__pycache__/*" \
  -x ".venv/*" \
  -x "logs/*" \
  -x "*.log" \
  -x ".git/*" \
  -x "charts/*" \
  -x "chart_snapshots/*" \
  -x "screenshots/*" \
  -x "data/backups/*"

echo "✅ ZIP creat: $(du -sh glitch_matrix.zip | cut -f1)"
```

**Pe VPS Windows:**
```
1. Chrome → drive.google.com → Login → Download glitch_matrix.zip
2. Right-click ZIP → "Extract All" → C:\matrix\
3. Verificare:
   Command Prompt → dir C:\matrix\*.py | find /c ".py"
   Trebuie: >50 fișiere .py
```

### Alternativă: Drag & Drop via RDP
```
Sesiunea RDP permite drag & drop direct din Finder Mac
→ în File Explorer Windows
```

---

<a name="configurare-env"></a>
## 🔐 6. CONFIGURARE .env

**Cel mai important fișier — fără el sistemul nu funcționează.**

### Creare pe VPS:

```
Notepad pe VPS → File → Save As:
  Path: C:\matrix\.env
  Encoding: UTF-8
```

**Conținut .env:**
```env
# ─── TELEGRAM ────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=6420069284

# ─── cTRADER API (local cBot HTTP server) ────────────────
CTRADER_API_URL=http://localhost:8767
CTRADER_ACCOUNT_ID=your_account_id

# ─── TIMEZONE ────────────────────────────────────────────
TZ=UTC
```

**Verificare:**
```cmd
cd C:\matrix
C:\matrix\.venv\Scripts\python.exe -c "from dotenv import load_dotenv; import os; load_dotenv(); print('Token OK:', bool(os.getenv('TELEGRAM_BOT_TOKEN')))"
```

---

<a name="ctrader-setup"></a>
## 📈 7. cTRADER SETUP

### Instalare (dacă scriptul PS1 nu a reușit auto-install)
```
Chrome pe VPS → https://ctrader.com/download/
Download → Run ctradersetup.exe → Install (~3 min)
```

### Login Cont Live
```
1. Deschide cTrader
2. Login → Broker: "IC Markets" (sau brokerul tău)
3. Email + Password → Connect → Selectează contul Live
```

### Import & Pornire cBot (MarketDataProvider)
```
1. cTrader → Automate (meniu sus)
2. Left panel "cBots" → Import
3. Navighează la: C:\matrix\MarketDataProvider_v2.cs
4. cAlgo compilează automat (~30 secunde)
5. Click "MarketDataProvider v2" → Start
6. ✅ Console: "HTTP Server running on http://localhost:8767"
```

### Verificare cBot:
```
Chrome pe VPS:
http://localhost:8767/health
→ {"status": "OK", "uptime": ...}

http://localhost:8767/price?symbol=EURUSD
→ preț live
```

### cTrader Auto-Start la Boot:
```
Win + R → taskschd.msc → Create Task:
  Name: cTrader Auto-Start
  ✅ Run with highest privileges
  Trigger: At startup → Delay 30s
  Action: C:\Users\Administrator\AppData\Local\Spotware\cTrader\cTrader.exe
```

---

<a name="pornire-sistem"></a>
## 🚀 8. PORNIRE SISTEM

### One-Click Start (creat automat de scriptul PS1):
```
C:\matrix\start_matrix.bat  →  Double-click
```

**Pornește în ordine:**
```
1. watchdog_monitor.py           → logs\watchdog.log
2. setup_executor_monitor.py     → logs\setup_monitor.log
3. position_monitor.py           → logs\position_monitor.log
4. telegram_command_center.py    → logs\command_center.log
5. news_calendar_monitor.py      → logs\news_calendar.log
6. ctrader_sync_daemon.py        → logs\ctrader_sync.log
```

### Verificare:
```cmd
tasklist | findstr python
# Trebuie: 6 procese python.exe
```

### Daily Scanner (manual, dimineața):
```cmd
cd C:\matrix
C:\matrix\.venv\Scripts\python.exe daily_scanner.py
```

---

<a name="test-final"></a>
## ✅ 9. TEST FINAL & VALIDARE

**cTrader + cBot:**
```
[ ] cTrader Desktop pornit
[ ] cBot "MarketDataProvider" status: Running
[ ] http://localhost:8767/health → {"status": "OK"}
[ ] http://localhost:8767/price?symbol=EURUSD → preț valid
```

**Python Monitors:**
```cmd
tasklist | findstr python
[ ] 6 procese python.exe active
```

**Telegram:**
```
[ ] /status → toate monitoare ONLINE
[ ] /active → poziții afișate corect
[ ] /monitoring → setup-uri din monitoring_setups.json
```

**IPC Bridge:**
```cmd
type C:\matrix\signals.json
[ ] Fișier accesibil R/W de cBot
```

**Test Reboot:**
```cmd
shutdown /r /t 0
# Wait 3 min → Reconectează RDP
tasklist | findstr python
[ ] Toate 6 procese repornite automat (Task Scheduler)
```

---

<a name="monitorizare"></a>
## 📊 10. MONITORIZARE & MENTENANȚĂ

### Logs live (PowerShell):
```powershell
# Urmărire live setup monitor:
Get-Content C:\matrix\logs\setup_monitor.log -Wait -Tail 50

# Watchdog:
Get-Content C:\matrix\logs\watchdog.log -Wait -Tail 20
```

### Telegram Quick Health:
```
/status     → 7 monitoare ONLINE/OFFLINE
/active     → Poziții cu P/L live
/stats      → Performance zilnic/săptămânal
/monitoring → Setup-uri în radar
```

### Troubleshooting Rapid:

**cBot nu răspunde (8767 timeout):**
```cmd
taskkill /im cTrader.exe /f
schtasks /run /tn "cTrader Auto-Start"
# Wait 60s → test http://localhost:8767/health
```

**Python monitors oprite:**
```cmd
taskkill /im python.exe /f
C:\matrix\start_matrix.bat
```

**signals.json permission error:**
```powershell
$acl = Get-Acl "C:\matrix\signals.json"
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone","FullControl","Allow")
$acl.SetAccessRule($rule)
Set-Acl "C:\matrix\signals.json" $acl
```

### Mentenanță Săptămânală (5 minute):
```cmd
# Backup
copy C:\matrix\monitoring_setups.json C:\matrix\backups\monitoring_%DATE:~-4%%DATE:~3,2%%DATE:~0,2%.json

# Curățare logs >30 zile
cd C:\matrix\logs
forfiles /p . /m *.log /d -30 /c "cmd /c del @path"

# Update packages
C:\matrix\.venv\Scripts\pip.exe install --upgrade -r C:\matrix\requirements_vps_windows.txt -q

# Restart monitors
taskkill /im python.exe /f
C:\matrix\start_matrix.bat
```

---

## 📁 Structura Finală pe VPS

```
C:\matrix\
├── .env                          ← Credentials (Telegram, cTrader)
├── .venv\                        ← Python virtual environment
├── signals.json                  ← IPC bridge cBot↔Python (FullControl)
├── monitoring_setups.json        ← Setups active în radar
├── trade_history.json            ← Positions live
├── active_positions.json         ← Poziții curente
├── start_matrix.bat              ← One-click start (generat de PS1)
├── vps_deploy_windows.ps1        ← Deploy script (rulat o singură dată)
├── requirements_vps_windows.txt  ← Dependencies Python (generat de PS1)
├── daily_scanner.py              ← Morning hunt (manual, dimineața)
├── setup_executor_monitor.py     ← Core executor (CHoCH + Fibo entry)
├── position_monitor.py           ← ARMAGEDDON notifications
├── watchdog_monitor.py           ← Guardian (repornește procesele căzute)
├── telegram_command_center.py    ← /status /active /stats /monitoring
├── news_calendar_monitor.py      ← News guard (blochează execuții)
├── ctrader_sync_daemon.py        ← Sync trade history
├── data\
│   └── trades.db                 ← SQLite closed trades history
├── logs\
│   ├── watchdog.log
│   ├── setup_monitor.log
│   ├── position_monitor.log
│   ├── command_center.log
│   ├── news_calendar.log
│   └── ctrader_sync.log
└── backups\                      ← Backup-uri automate săptămânale
```

---

## 🎉 DEPLOYMENT COMPLET!

### Ce ai după deploy:

✅ **Windows VPS 24/7** (~€28/lună Hetzner CPX41 🇩🇪, **8vCPU AMD EPYC / 16GB RAM / 240GB NVMe**)
✅ **cTrader Desktop + cBot** (localhost:8767 live data provider)
✅ **6 Python Monitors** activi + watchdog guardian
✅ **Auto-start la boot** (Task Scheduler → GlitchInMatrix_AutoStart)
✅ **ARMAGEDDON notifications** la fiecare trade deschis (fără duplicate)
✅ **signals.json IPC bridge** (FullControl, cTrader ↔ Python)
✅ **Anti-spam watchdog** (restart OK → 15 min / FAILED → 60 min cooldown)
✅ **News guard** (blochează execuții în ferestre de știri High Impact)
✅ **Control complet Telegram** — /status /active /stats /monitoring
✅ **MAX PERFORMANCE MODE** — 16 GB RAM cache agresiv + 8 vCPU threading ready
✅ **Logging complet DEBUG** — 90 zile retenție, rotație 50 MB, compresie automată

---

**Engineered by ФорексГод · Glitch in Matrix V13.1 · Hetzner CPX41 🇩🇪 · April 2026**
