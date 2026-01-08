# 🪟 Windows VPS Deployment - Ghid Complet

**Migrare Glitch In Matrix Trading Bot pe Windows VPS (24/7)**

---

## 📋 CUPRINS RAPID

1. [De Ce Windows VPS](#de-ce-windows)
2. [VPS Recomandat](#vps-recomandat)
3. [Conectare RDP](#conectare-rdp)
4. [Instalare Componente](#instalare-componente)
5. [Transfer Fișiere](#transfer-fisiere)
6. [Configurare Auto-Start](#auto-start)
7. [Test Final](#test-final)
8. [Monitorizare](#monitorizare)

---

<a name="de-ce-windows"></a>
## 🎯 1. DE CE WINDOWS VPS?

### Problema cu Linux VPS

❌ **cTrader Desktop NU rulează pe Linux**  
❌ **cBot-ul tău (MarketDataProvider) = Windows/macOS only**  
❌ **Alternativa = Refactoring complet cod (4-8 ore)**

### Soluția Windows VPS

✅ **Zero modificări cod** - sistemul rămâne identic  
✅ **cTrader Desktop native** - instalare directă  
✅ **Remote Desktop (RDP)** - acces GUI complet  
✅ **Windows Task Scheduler** - automation built-in  

### Cost vs Linux

| Provider | Windows VPS | Linux VPS | Diferență |
|----------|-------------|-----------|-----------|
| **Contabo** | €9.99/lună | €4.99/lună | +€5/lună |
| **Vultr** | $18/lună | $12/lună | +$6/lună |

**Verdict:** +€5-10/lună pentru **zero development time** = excellent ROI

---

<a name="vps-recomandat"></a>
## 💻 2. VPS WINDOWS RECOMANDAT

### ⭐ Opțiunea #1: Contabo (RECOMANDAT)

**Specificații:**
- **Plan:** VPS S Windows
- **CPU:** 4 vCores
- **RAM:** 8GB
- **Storage:** 200GB NVMe SSD
- **Bandwidth:** 32TB/lună
- **Cost:** **€9.99/lună**
- **OS:** Windows Server 2019/2022
- **Location:** Nuremberg, Germany

**Link:** https://contabo.com/en/windows-vps/

**De ce Contabo:**
- ✅ **CEL MAI IEFTIN** Windows VPS de calitate
- ✅ **8GB RAM** = suficient pentru cTrader + Python + 15 perechi
- ✅ **4 vCores** = handle monitoring concurent fără lag
- ✅ **200GB storage** = generos pentru logs/backups
- ✅ **Latency:** ~15ms din Europa (Nuremberg)

**Pași comandă:**
1. Acces https://contabo.com/en/windows-vps/
2. Selectează **VPS S** (€9.99/lună)
3. **OS:** Windows Server 2022
4. **Region:** Nuremberg, Germany (EU-Central)
5. **Add-ons:** NONE (nu ai nevoie backup plătit)
6. **Checkout** → Email cu credentials în 10-30 min

---

### Opțiunea #2: Vultr (Premium, mai scump)

**Specificații:**
- **Plan:** Regular Cloud Compute
- **CPU:** 2 vCores
- **RAM:** 4GB
- **Storage:** 80GB SSD
- **Cost:** **$18/lună** (~€17)
- **OS:** Windows Server 2022
- **Location:** Frankfurt, Germany

**Link:** https://www.vultr.com/products/cloud-compute/

**Pro:**
- ✅ Deployment instant (30 secunde)
- ✅ UI excellent (dashboard intuitiv)
- ✅ 99.99% uptime SLA

**Contra:**
- ❌ Mai scump (+€7/lună vs Contabo)
- ❌ Specs mai slabe (4GB vs 8GB RAM)

---

### Specificații Minime

**Pentru Glitch In Matrix Bot:**
- **CPU:** 2 vCores (minimum) | 4 vCores (recomandat)
- **RAM:** 4GB (minimum) | 8GB (recomandat)
- **Storage:** 40GB (minimum) | 100GB+ (confortabil)
- **Bandwidth:** 1TB/lună (bot folosește <10GB/lună)

**De ce 8GB RAM:**
- cTrader Desktop: ~1.5GB
- Python (3 monitors): ~500MB
- Windows Server: ~2GB
- **Buffer:** ~4GB pentru scalare

---

<a name="conectare-rdp"></a>
## 🔐 3. CONECTARE REMOTE DESKTOP (RDP)

### Primire Credentials

După comandă Contabo, primești email:

```
Subject: VPS Activated

IP: 45.134.215.XXX
Username: Administrator
Password: XyZ123!@#AbC
RDP Port: 3389
```

### Conectare de pe Mac

**1. Descarcă Microsoft Remote Desktop:**
```
App Store → Caută "Microsoft Remote Desktop"
→ Install (FREE)
```

**2. Configurare conexiune:**
```
1. Deschide Microsoft Remote Desktop
2. Click "Add PC"
3. PC name: 45.134.215.XXX (IP-ul tău)
4. User account → Add User Account:
   Username: Administrator
   Password: [password din email]
5. Save
```

**3. Conectare:**
```
1. Double-click pe conexiunea salvată
2. Dacă apare warning certificate → "Continue"
3. ✅ Desktop Windows VPS visible
```

### Test Conexiune Rapidă

```bash
# Test ping de pe Mac
ping 45.134.215.XXX

# Trebuie să vezi:
# 64 bytes from 45.134.215.XXX: icmp_seq=0 ttl=50 time=15.2 ms
```

---

<a name="instalare-componente"></a>
## 📦 4. INSTALARE COMPONENTE PE WINDOWS VPS

### Conectează-te prin RDP (vezi Secțiunea 3)

---

### STEP 1: Instalare Python 3.14

**1. Descarcă Python:**
```
Pe VPS Windows:
1. Deschide Edge/Chrome
2. Acces: https://www.python.org/downloads/
3. Download "Python 3.14.0" (Windows 64-bit)
```

**2. Instalare:**
```
1. Run python-3.14.0-amd64.exe
2. ✅ Bifează "Add python.exe to PATH" (IMPORTANT!)
3. Click "Install Now"
4. Wait ~2 min
5. Click "Close"
```

**3. Verificare:**
```
1. Deschide Command Prompt (Win + R → cmd)
2. Rulează:
   python --version
   # Output: Python 3.14.0

3. Verifică pip:
   pip --version
   # Output: pip 24.x from C:\...
```

---

### STEP 2: Instalare cTrader Desktop

**1. Descarcă cTrader:**
```
Pe VPS Windows:
1. Acces: https://ctrader.com/download/
2. Click "Download cTrader Desktop" (Windows)
3. Save ctradersetup.exe
```

**2. Instalare:**
```
1. Run ctradersetup.exe
2. Acceptă Terms
3. Click "Install"
4. Wait ~3 min
5. cTrader se deschide automat
```

**3. Login IC Markets:**
```
1. În cTrader → Login
2. Broker: "IC Markets"
3. Email: [contul tău IC Markets]
4. Password: [password]
5. Login → Account loading...
```

---

### STEP 3: Install cBot (MarketDataProvider)

**1. Deschide cAlgo:**
```
cTrader Desktop → Top Menu → "Automate"
```

**2. Import cBot:**
```
1. cAlgo → Left Panel → "cBots"
2. Right-click în panel → "Import cBot"
3. Navighează la: (va fi uploaded în STEP 5)
   C:\TradingBot\MarketDataProvider_v2.cs
4. cAlgo compilează automat
5. ✅ Vezi "MarketDataProvider v2" în listă
```

**3. Rulare cBot:**
```
1. Click pe "MarketDataProvider v2"
2. Click "Start" (play button)
3. ✅ Status: "Running"
4. ✅ Console: "HTTP Server running on http://localhost:8767"
```

**4. Test HTTP endpoint:**
```
1. Deschide Chrome pe VPS
2. Acces: http://localhost:8767/health
3. Trebuie să vezi:
   {"status": "OK", "message": "MarketDataProvider is running"}
```

---

### STEP 4: Test Python Dependencies

**1. Deschide Command Prompt ca Administrator:**
```
Win + X → "Command Prompt (Admin)"
```

**2. Instalare dependencies (va fi rulat automat în STEP 5):**
```cmd
cd C:\TradingBot
pip install -r requirements.txt
```

**Dependencies principale:**
- pandas
- requests
- python-dotenv
- loguru
- python-telegram-bot

**Timp instalare:** ~2-3 minute

---

<a name="transfer-fisiere"></a>
## 📤 5. TRANSFER FIȘIERE DE PE MAC PE VPS

### Opțiunea A: Google Drive (CEL MAI SIMPLU)

**Pe Mac:**
```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

# 1. Creează arhivă ZIP (exclude logs/cache)
zip -r trading-bot.zip . \
  -x "*.pyc" \
  -x "**/__pycache__/*" \
  -x "logs/*" \
  -x "charts/*" \
  -x ".git/*"

# 2. Upload pe Google Drive:
# - Acces drive.google.com
# - Upload trading-bot.zip
# - Share link (Anyone with link can view)
```

**Pe Windows VPS:**
```
1. Deschide Chrome
2. Acces drive.google.com
3. Login cu același cont Google
4. Download trading-bot.zip
5. Extract în C:\TradingBot\
6. ✅ Toate fișierele în C:\TradingBot\
```

---

### Opțiunea B: GitHub (Pentru development)

**Pe Mac:**
```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

# 1. Init Git repo (dacă nu există)
git init
git add .
git commit -m "VPS deployment ready"

# 2. Creează repo privat pe GitHub
# - Acces github.com
# - New repository: "glitch-trading-bot" (Private)
# - Copy HTTPS URL

# 3. Push la GitHub
git remote add origin https://github.com/USERNAME/glitch-trading-bot.git
git branch -M main
git push -u origin main
```

**Pe Windows VPS:**
```cmd
# 1. Install Git
# Download: https://git-scm.com/download/win
# Install cu default settings

# 2. Clone repo
cd C:\
git clone https://github.com/USERNAME/glitch-trading-bot.git TradingBot

# 3. Install dependencies
cd C:\TradingBot
pip install -r requirements.txt
```

---

### Opțiunea C: SCP/SFTP (Advanced)

**Necesită:** OpenSSH activat pe Windows VPS

```bash
# Pe Mac (terminalul tău):
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

# Transfer cu scp
scp -r . Administrator@45.134.215.XXX:C:/TradingBot/

# Introduce password când e solicitat
```

---

### ✅ Verificare Transfer

**Pe Windows VPS Command Prompt:**
```cmd
cd C:\TradingBot
dir

# Trebuie să vezi:
# daily_scanner.py
# smc_detector.py
# pairs_config.json
# monitoring_setups.json
# .env
# requirements.txt
# etc...
```

**Test Python scripts:**
```cmd
cd C:\TradingBot
python --version
# Python 3.14.0

python -c "import pandas; print('Pandas OK')"
# Pandas OK

python -c "import requests; print('Requests OK')"
# Requests OK
```

---

<a name="auto-start"></a>
## ⚙️ 6. CONFIGURARE AUTO-START

### Windows Task Scheduler Setup

**Obiectiv:** Rulare automată monitors la boot + daily scanner la 08:00

---

### TASK 1: cTrader Auto-Start

**1. Deschide Task Scheduler:**
```
Win + R → taskschd.msc → Enter
```

**2. Creează task:**
```
1. Action → "Create Task" (nu "Create Basic Task")
2. Tab "General":
   Name: cTrader Auto-Start
   Description: Start cTrader Desktop at boot
   ✅ "Run whether user is logged on or not"
   ✅ "Run with highest privileges"
   
3. Tab "Triggers":
   Click "New"
   → Begin the task: "At startup"
   → Delay task for: 30 seconds (wait for network)
   → OK
   
4. Tab "Actions":
   Click "New"
   → Action: "Start a program"
   → Program/script: Browse to:
      C:\Users\Administrator\AppData\Local\Spotware\cTrader\cTrader.exe
   → OK
   
5. Tab "Conditions":
   ❌ Uncheck "Start only if on AC power"
   ✅ Check "Wake computer to run this task"
   
6. Tab "Settings":
   ✅ "Allow task to be run on demand"
   ✅ "If running task does not end when requested, force it to stop"
   
7. OK → Enter Administrator password
```

---

### TASK 2: Setup Executor Monitor

**Rulare continuă background pentru monitoring setups**

**1. Creează startup script:**
```cmd
# Pe VPS Windows, deschide Notepad
# Salvează ca: C:\TradingBot\start_executor_monitor.bat

@echo off
cd C:\TradingBot
python setup_executor_monitor.py --loop
pause
```

**2. Task Scheduler:**
```
1. Create Task
2. General:
   Name: Setup Executor Monitor
   ✅ Run whether user logged on or not
   ✅ Run with highest privileges
   
3. Triggers:
   New → At startup → Delay 2 minutes → OK
   
4. Actions:
   New → Start a program
   Program: C:\TradingBot\start_executor_monitor.bat
   OK
   
5. Conditions:
   ❌ Uncheck AC power
   
6. Settings:
   ✅ Allow on demand
   ✅ "If task fails, restart every: 5 minutes" (max 3 attempts)
   
7. OK → Password
```

---

### TASK 3: Position Monitor

**Monitorizare poziții active + Telegram notifications**

**1. Creează script:**
```cmd
# Notepad → Save as: C:\TradingBot\start_position_monitor.bat

@echo off
cd C:\TradingBot
python position_monitor.py
pause
```

**2. Task Scheduler:**
```
1. Create Task
2. General:
   Name: Position Monitor
   
3. Triggers:
   At startup → Delay 2 minutes
   
4. Actions:
   Start program: C:\TradingBot\start_position_monitor.bat
   
5. Settings:
   ✅ Restart every 5 min if fails
   
6. OK → Password
```

---

### TASK 4: Daily Scanner

**Scanare zilnică la 08:00 pentru noi setups**

**1. Creează script:**
```cmd
# Notepad → Save as: C:\TradingBot\run_daily_scanner.bat

@echo off
cd C:\TradingBot
python daily_scanner.py
pause
```

**2. Task Scheduler:**
```
1. Create Task
2. General:
   Name: Daily Scanner 08:00
   
3. Triggers:
   New → Daily
   → Start: (today) 08:00:00
   → Recur every: 1 days
   → ✅ Enabled
   → OK
   
4. Actions:
   Start program: C:\TradingBot\run_daily_scanner.bat
   
5. OK → Password
```

---

### TASK 5: Dashboard HTTP Server

**Dashboard accesibil http://VPS_IP:8080**

**1. Creează script:**
```cmd
# Notepad → Save as: C:\TradingBot\start_dashboard.bat

@echo off
cd C:\TradingBot
python -m http.server 8080
pause
```

**2. Task Scheduler:**
```
1. Create Task
2. General:
   Name: Dashboard Server
   
3. Triggers:
   At startup → Delay 2 minutes
   
4. Actions:
   Start program: C:\TradingBot\start_dashboard.bat
   
5. Settings:
   ✅ Restart every 5 min if fails
   
6. OK → Password
```

---

### ✅ Verificare Tasks

**Command Prompt (Admin):**
```cmd
# Listează toate tasks
schtasks /query /fo LIST /v | findstr "cTrader\|Trading\|Monitor"

# Test manual task
schtasks /run /tn "Setup Executor Monitor"

# Verifică status
tasklist | findstr "python\|cTrader"

# Trebuie să vezi:
# python.exe (multiple instances)
# cTrader.exe
```

---

### Windows Firewall Configuration

**Permite port 8080 pentru dashboard extern:**

```cmd
# Command Prompt (Admin)
netsh advfirewall firewall add rule ^
  name="Trading Bot Dashboard" ^
  dir=in action=allow protocol=TCP localport=8080

# Verifică
netsh advfirewall firewall show rule name="Trading Bot Dashboard"
```

**Acces dashboard extern:**
```
http://45.134.215.XXX:8080/dashboard.html
(Replace cu IP-ul tău VPS)
```

---

<a name="test-final"></a>
## ✅ 7. TEST FINAL & VALIDARE

### Test Checklist Complet

**1. cTrader + cBot:**
```
✅ cTrader Desktop pornit
✅ cBot "MarketDataProvider" Running
✅ http://localhost:8767/health → {"status": "OK"}
✅ http://localhost:8767/data?symbol=EURUSD&timeframe=D1&bars=10 → JSON valid
```

**2. Python Monitors:**
```cmd
# Command Prompt
tasklist | findstr python

# Trebuie să vezi 3-4 procese python.exe:
# - setup_executor_monitor.py
# - position_monitor.py
# - http.server (dashboard)
```

**3. Dashboard:**
```
Chrome → http://localhost:8080/dashboard.html
✅ Pagina se încarcă
✅ Vezi setups din monitoring_setups.json
✅ Auto-refresh la 10 secunde
```

**4. Telegram Notifications:**
```
# Test manual
cd C:\TradingBot
python -c "from notification_manager import NotificationManager; nm = NotificationManager(); nm.send_test_message()"

# Verifică Telegram → Primești mesaj de test
```

**5. Daily Scanner:**
```cmd
# Test manual
cd C:\TradingBot
python daily_scanner.py

# Observă output:
# - Fetch data pentru 15 perechi
# - CHoCH detection
# - FVG detection
# - Salvare în monitoring_setups.json
```

---

### Test Reboot VPS

**Verifică că totul pornește automat:**

```cmd
# Restart VPS
shutdown /r /t 0

# Wait 5 minutes pentru boot complet

# Reconectează RDP

# Verifică procese:
tasklist | findstr "cTrader\|python"

# Trebuie să vezi toate procesele pornite automat
```

---

<a name="monitorizare"></a>
## 📊 8. MONITORIZARE & MENTENANȚĂ

### Dashboard Access

**Local (pe VPS):**
```
http://localhost:8080/dashboard.html
```

**Extern (de pe Mac/phone):**
```
http://45.134.215.XXX:8080/dashboard.html
(Replace XXX cu IP-ul tău)
```

---

### Logs Monitoring

**Verifică logs Python:**
```cmd
cd C:\TradingBot\logs
dir /o-d

# Vezi cele mai recente:
type daily_scanner_*.log | more
type setup_executor_*.log | more
```

**Verifică logs cTrader:**
```
cTrader → Automate → cBots → MarketDataProvider
→ Tab "Log" (bottom panel)
```

---

### Weekly Maintenance

**Săptămânal (10 minute):**

```cmd
# 1. Verifică disk space
wmic logicaldisk get size,freespace,caption

# 2. Curățare logs vechi (>30 zile)
cd C:\TradingBot\logs
forfiles /p . /s /m *.log /d -30 /c "cmd /c del @path"

# 3. Backup monitoring_setups.json
copy C:\TradingBot\monitoring_setups.json ^
     C:\TradingBot\backups\monitoring_setups_%date:~-4,4%%date:~-7,2%%date:~-10,2%.json

# 4. Update Python dependencies
cd C:\TradingBot
pip install --upgrade -r requirements.txt

# 5. Restart monitors (Task Scheduler)
schtasks /end /tn "Setup Executor Monitor"
schtasks /run /tn "Setup Executor Monitor"
```

---

### Performance Monitoring

**Task Manager:**
```
Ctrl + Shift + Esc

→ Tab "Performance"
→ Monitor:
  - CPU: <20% normal, 40-60% during scan
  - RAM: ~3-4GB used
  - Disk: <10% active time
  - Network: <1Mbps
```

**Python procese:**
```cmd
# Check memory per process
tasklist /fi "imagename eq python.exe" /fo table

# Dacă > 500MB per process → possible memory leak
# Solution: Restart task în Task Scheduler
```

---

### Troubleshooting Quick Fixes

**cTrader cBot nu răspunde:**
```cmd
# Kill process
taskkill /im cTrader.exe /f

# Restart via Task Scheduler
schtasks /run /tn "cTrader Auto-Start"

# Wait 60 seconds
# Test: http://localhost:8767/health
```

**Python monitor stuck:**
```cmd
# Kill toate python
taskkill /im python.exe /f

# Restart tasks
schtasks /run /tn "Setup Executor Monitor"
schtasks /run /tn "Position Monitor"
schtasks /run /tn "Dashboard Server"
```

**Dashboard nu se încarcă:**
```cmd
# Check firewall
netsh advfirewall firewall show rule name=all | findstr 8080

# Restart dashboard
schtasks /end /tn "Dashboard Server"
schtasks /run /tn "Dashboard Server"

# Test local
curl http://localhost:8080
```

---

## 🎉 DEPLOYMENT COMPLET!

### Ce ai acum:

✅ **Windows VPS 24/7** (€9.99/lună Contabo)  
✅ **cTrader Desktop + cBot** (localhost:8767 data provider)  
✅ **Python Trading System** (3 monitors active)  
✅ **Auto-start la boot** (Windows Task Scheduler)  
✅ **Daily scanner** (08:00 automatic)  
✅ **Dashboard public** (http://VPS_IP:8080)  
✅ **Telegram notifications** (active)  
✅ **Zero modificări cod** (sistemul identic cu Mac)  

### Next Steps:

1. **Testează 1 săptămână** - monitorizează stability
2. **Optimizează** - adjust task timings dacă e nevoie
3. **Backup** - setup automatic backups săptămânal
4. **Scale** - când crește numărul de perechi, upgrade RAM (8→16GB)

### Support & Contact:

- **Contabo Support:** https://contabo.com/en/support/
- **cTrader Forum:** https://ctrader.com/forum/
- **Telegram Bot Issues:** @BotFather

---

**🚀 Happy Trading! Sistemul rulează 24/7 în cloud!**
