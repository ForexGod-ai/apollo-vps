# 🚀 VPS DEPLOYMENT - Ghid Complet pentru Glitch In Matrix

**Documentație completă pentru migrarea sistemului pe VPS plătit (24/7 trading)**

---

## 📋 CUPRINS

1. [Înțelegerea Arhitecturii](#arhitectura)
2. [Limitări Importante](#limitari)
3. [Scenarii de Deployment](#scenarii)
4. [VPS Recomandat](#vps-recomandat)
5. [Deployment Automat](#deployment-automat)
6. [Deployment Manual](#deployment-manual)
7. [Configurare Systemd](#systemd)
8. [Configurare Cron](#cron)
9. [Verificare Post-Deployment](#verificare)
10. [Backup & Recovery](#backup)
11. [Troubleshooting](#troubleshooting)
12. [Monitorizare & Mentenanță](#monitorizare)

---

<a name="arhitectura"></a>
## 🏗️ 1. ÎNȚELEGEREA ARHITECTURII ACTUALE

### Componente Sistem

```
┌─────────────────────────────────────────────────────────────┐
│                      MAC LOCAL (Current)                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ cTrader Desktop + MarketDataProvider cBot          │    │
│  │ HTTP Server: localhost:8767                         │    │
│  │ Provides: Real-time IC Markets data                │    │
│  └─────────────────────────────────────────────────────┘    │
│                         ▲                                     │
│                         │ HTTP Requests                       │
│  ┌──────────────────────┴──────────────────────────────┐    │
│  │ Python Trading System                               │    │
│  │ • daily_scanner.py (morning scan)                   │    │
│  │ • position_monitor.py (TP/SL notifications)         │    │
│  │ • setup_executor_monitor.py (auto-execution)        │    │
│  │ • Dashboard HTTP Server (port 8080)                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Fluxul de Date

1. **cTrader Desktop** (macOS/Windows):
   - Rulează cBot `MarketDataProvider_v2.cs`
   - Servește HTTP API pe `localhost:8767`
   - Endpoints: `/health`, `/data?symbol=EURUSD&timeframe=D1&bars=365`

2. **Python Scripts**:
   - Apelează `http://localhost:8767` pentru date OHLCV
   - Procesează date (CHoCH detection, FVG, setups)
   - Trimite notificări Telegram
   - Execută trades prin cTrader API

3. **Dashboard**:
   - HTTP server pe port 8080
   - Afișează setups active din `monitoring_setups.json`
   - Auto-refresh la 10 secunde

---

<a name="limitari"></a>
## ⚠️ 2. LIMITĂRI IMPORTANTE - CITEȘTE CU ATENȚIE!

### 🔴 PROBLEMA CRITICĂ: cTrader cBot nu rulează pe Linux VPS

**Realitatea:**
- cTrader Desktop (și cBot-urile) rulează doar pe **Windows** sau **macOS**
- VPS Linux (Ubuntu/Debian) **NU poate rula cTrader Desktop**
- Python scripts-urile tale depind de `localhost:8767` (cBot-ul tău)

**Impact:**
```
VPS Linux (Ubuntu)
    └─ Python scripts încearcă: http://localhost:8767
       └─ ❌ FAILED - cBot nu există pe Linux!
```

### Consecințe

**Ce NU merge direct pe VPS Linux:**
- `daily_scanner.py` - ❌ (necesită date de la cBot)
- `setup_executor_monitor.py` - ❌ (necesită date de la cBot)
- Trade execution - ⚠️ (funcționează dacă folosești cTrader Cloud API)

**Ce MERGE pe VPS Linux:**
- `position_monitor.py` - ✅ (citește `trade_history.json`)
- `dashboard HTTP server` - ✅
- Telegram notifications - ✅
- Scheduled tasks (cron) - ✅

---

<a name="scenarii"></a>
## 🎯 3. SCENARII DE DEPLOYMENT - ALEGE VARIANTA POTRIVITĂ

### Scenariul A: Mac LOCAL 24/7 (Cel mai simplu, NU recomand)

**Setup:**
- Mac rămâne pornit non-stop
- cTrader Desktop + cBot rulează pe Mac
- Python scripts rulează pe Mac
- Launchd automation (deja configurat)

**Pro:**
- ✅ Zero modificări cod
- ✅ Setup deja funcțional
- ✅ Cost 0 (fără VPS)

**Contra:**
- ❌ Mac trebuie să rămână pornit 24/7 (factura electricitate)
- ❌ Risc: Mac se închide accidental → sistem cade
- ❌ Dependență de internet acasă (power outage = downtime)
- ❌ Nu poți călători fără să oprești sistemul

**Verdict:** ❌ **NU RECOMAND** - înfrânge scopul unui sistem automat 24/7

---

### Scenariul B: HYBRID - Mac + VPS (Compromis temporar)

**Setup:**
- **Mac LOCAL**: cTrader Desktop + cBot (localhost:8767)
- **VPS**: Python monitors + dashboard
- **Conexiune**: VPS apelează Mac prin internet (port forwarding)

**Arhitectură:**
```
┌─────────────────┐                      ┌─────────────────┐
│  VPS (Cloud)    │                      │  Mac (Acasă)    │
│                 │                      │                 │
│  Python Scripts │────HTTP Request─────>│  cTrader cBot   │
│  (monitoring)   │  http://MAC_IP:8767  │  (port 8767)    │
│  Dashboard      │                      │                 │
└─────────────────┘                      └─────────────────┘
```

**Pro:**
- ✅ Dashboard public (accesibil de oriunde)
- ✅ Monitors rulează 24/7 pe VPS (reliability)
- ✅ Modificări minime de cod

**Contra:**
- ❌ Mac încă trebuie să fie pornit 24/7
- ❌ Port forwarding (risc securitate)
- ❌ Latency (VPS → Mac → VPS)
- ❌ Dacă Mac cade, totul cade

**Setup Port Forwarding pe Mac:**
```bash
# 1. Configurează router să forwarding port 8767 către Mac
# 2. Obține IP public (whatismyip.com)
# 3. Pe VPS, modifică ctrader_cbot_client.py:
#    self.base_url = "http://YOUR_MAC_PUBLIC_IP:8767"
# 4. IMPORTANT: Adaugă autentificare (nginx proxy) pentru securitate
```

**Verdict:** ⚠️ **Temporar acceptabil**, dar Mac rămâne single point of failure

---

### Scenariul C: VPS WINDOWS (Fully Cloud, Scump)

**Setup:**
- VPS Windows Server (€30-50/lună)
- cTrader Desktop instalat pe VPS Windows
- Python + toate scripts pe același VPS

**Arhitectură:**
```
┌──────────────────────────────────────────┐
│       VPS Windows (Cloud 24/7)           │
├──────────────────────────────────────────┤
│                                          │
│  cTrader Desktop + cBot (localhost:8767) │
│              ▲                           │
│              │ Local HTTP                │
│  Python Scripts + Dashboard              │
│                                          │
└──────────────────────────────────────────┘
```

**Pro:**
- ✅ Fully cloud - zero dependență de Mac
- ✅ Zero modificări arhitectură
- ✅ Reliability ridicată (VPS 99.9% uptime)

**Contra:**
- ❌ SCUMP: €30-50/lună (vs €5-10 pentru Linux VPS)
- ❌ Windows Server resource-intensive
- ❌ cTrader Desktop pe Windows Server (poate avea limitări GUI)

**VPS Recomandat:**
- **Contabo**: Windows VPS €9.99/lună (4GB RAM, 2 cores)
- **Vultr**: Windows VPS $20/lună
- **DigitalOcean**: Windows droplet $40/lună

**Verdict:** ✅ **Funcționează 100%**, dar costisitor pe termen lung

---

### Scenariul D: CLOUD API - FULL LINUX VPS (Recomandat, necesită refactoring)

**Setup:**
- VPS Linux Ubuntu (€5-10/lună)
- Înlocuiești `localhost:8767` cu **cTrader Cloud API** sau **Twelve Data API**
- Python scripts modificate să folosească API cloud

**Arhitectură:**
```
┌─────────────────────────────────────────┐
│      VPS Linux Ubuntu (Cloud 24/7)      │
├─────────────────────────────────────────┤
│                                         │
│  Python Scripts (modified)              │
│      │                                  │
│      └──HTTP Request──>  cTrader Cloud API
│                          (api.spotware.com)
│                          OR
│                          Twelve Data API
│                          (twelvedata.com)
│                                         │
│  Dashboard (port 8080)                  │
│                                         │
└─────────────────────────────────────────┘
```

**Modificări necesare:**

1. **Înlocuiește `CTraderCBotClient` cu `CloudDataProvider`:**
```python
# OLD: ctrader_cbot_client.py
class CTraderCBotClient:
    def __init__(self):
        self.base_url = "http://localhost:8767"

# NEW: cloud_data_provider.py
class CloudDataProvider:
    def __init__(self):
        # Option A: cTrader Cloud API (ProtoOA)
        self.api_url = "https://api.spotware.com"
        self.access_token = os.getenv("CTRADER_ACCESS_TOKEN")
        
        # Option B: Twelve Data (easier, $8/month)
        self.api_url = "https://api.twelvedata.com"
        self.api_key = os.getenv("TWELVEDATA_API_KEY")
    
    def get_historical_data(self, symbol, timeframe, bars):
        # Make HTTP request to cloud API
        # Parse JSON response
        # Return DataFrame with OHLCV data
```

2. **Update `daily_scanner.py` și `setup_executor_monitor.py`:**
```python
# OLD:
from ctrader_cbot_client import CTraderCBotClient
data_provider = CTraderCBotClient()

# NEW:
from cloud_data_provider import CloudDataProvider
data_provider = CloudDataProvider()
```

**Pro:**
- ✅ IEFTIN: €5-10/lună (Linux VPS)
- ✅ Zero dependență hardware local
- ✅ Reliability maximă (VPS + cloud API)
- ✅ Scalabil (poți adăuga multiple VPS pentru redundancy)

**Contra:**
- ❌ Necesită refactoring cod (2-4 ore development)
- ❌ API cloud poate avea costuri:
  - cTrader Cloud API: FREE (ProtoOA)
  - Twelve Data: $8/lună (600 requests/minut)
- ❌ Latency mai mare decât localhost (10-50ms vs <1ms)

**Verdict:** ✅ **CEL MAI BUN long-term** - investiție inițială în cod, dar sistem robust

---

<a name="vps-recomandat"></a>
## 💻 4. VPS RECOMANDAT - UNDE ȘI CE SĂ CUMPERI

### Pentru Scenariul D (Linux VPS - Recomandat)

#### **Opțiunea 1: DigitalOcean (Cel mai popular)**

**Specificații:**
- **Plan:** Basic Droplet
- **Specs:** 1 vCPU, 2GB RAM, 50GB SSD
- **Cost:** $12/lună ($0.018/oră)
- **Location:** Frankfurt, Germany (latency mică în Europa)
- **OS:** Ubuntu 22.04 LTS

**Link:** https://www.digitalocean.com/pricing/droplets

**Pro:**
- ✅ UI excelent (ușor pentru începători)
- ✅ Documentație vastă
- ✅ 99.99% uptime SLA
- ✅ Snapshots gratuite (backup automat)

**Setup Rapid:**
1. Creează cont DigitalOcean
2. Create Droplet → Ubuntu 22.04 → Basic ($12/lună)
3. Choose datacenter: Frankfurt
4. Add SSH key (vezi secțiunea SSH mai jos)
5. Create Droplet (gata în 60 secunde)

---

#### **Opțiunea 2: Hetzner (Cel mai ieftin)**

**Specificații:**
- **Plan:** CX21
- **Specs:** 2 vCPU, 4GB RAM, 40GB SSD
- **Cost:** €5.83/lună (~$6.50)
- **Location:** Falkenstein, Germany
- **OS:** Ubuntu 22.04

**Link:** https://www.hetzner.com/cloud

**Pro:**
- ✅ CEL MAI IEFTIN (jumătate din prețul DigitalOcean)
- ✅ Specs mai bune la același preț
- ✅ Datacentere în Europa (GDPR compliant)

**Contra:**
- ⚠️ Support mai lent decât DigitalOcean
- ⚠️ UI mai puțin intuitiv

---

#### **Opțiunea 3: Vultr (Middle ground)**

**Specificații:**
- **Plan:** Regular Performance
- **Specs:** 1 vCPU, 2GB RAM, 55GB SSD
- **Cost:** $12/lună
- **Location:** Frankfurt
- **OS:** Ubuntu 22.04

**Link:** https://www.vultr.com/pricing/

**Pro:**
- ✅ Fast provisioning (30 secunde)
- ✅ Multe locații (25+ datacentere)
- ✅ Snapshot backup inclus

---

### Pentru Scenariul C (Windows VPS)

#### **Opțiunea 1: Contabo (Cel mai ieftin Windows)**

**Specificații:**
- **Plan:** VPS S Windows
- **Specs:** 4 vCPU, 8GB RAM, 200GB SSD
- **Cost:** €9.99/lună
- **OS:** Windows Server 2022

**Link:** https://contabo.com/en/windows-vps/

**Pro:**
- ✅ MULT mai ieftin decât Vultr/DigitalOcean Windows
- ✅ Specs generoase (8GB RAM suficient pentru cTrader)

**Contra:**
- ⚠️ Support mai slab
- ⚠️ Setup mai complicat

---

### ⚙️ Specificații Minime Necesare

**Pentru Linux VPS (Python only):**
- CPU: 1 vCPU (suficient)
- RAM: 2GB (1GB ar merge, dar 2GB recomandabil)
- Storage: 20GB (logs + charts pot crește)
- Bandwidth: 1TB/lună (sub 10GB folosit pentru trading bot)

**Pentru Windows VPS (cTrader + Python):**
- CPU: 2 vCPU (cTrader Desktop mai resource-heavy)
- RAM: 4GB minimum (8GB recomandat)
- Storage: 40GB (cTrader instalare + date)

---

<a name="deployment-automat"></a>
## 🤖 5. DEPLOYMENT AUTOMAT - METODA RECOMANDATĂ

### Pregătire

**1. Creează SSH Key (pe Mac):**
```bash
# Generează SSH key pair (dacă nu ai deja)
ssh-keygen -t ed25519 -C "forexgod@trading-vps"
# Salvează în: ~/.ssh/id_ed25519

# Copiază public key
cat ~/.ssh/id_ed25519.pub
# Output: ssh-ed25519 AAAAC3N... forexgod@trading-vps
```

**2. Adaugă SSH Key pe VPS:**
- **DigitalOcean:** Settings → Security → SSH Keys → Add SSH Key
- **Manual:** Când creezi droplet, paste SSH public key

**3. Obține IP-ul VPS:**
```bash
# După ce VPS e creat, notează IP public
# Exemplu: 164.92.135.47
```

**4. Test SSH Connection:**
```bash
# Test conexiune (replace VPS_IP)
ssh root@164.92.135.47

# Prima conexiune va cere confirmare:
# "Are you sure you want to continue connecting (yes/no)?"
# Type: yes

# Dacă merge, disconnect:
exit
```

---

### Deployment cu Script Automat

**1. Verifică fișierul `deploy_to_vps.sh`:**
```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
cat deploy_to_vps.sh
```

**2. Rulează deployment:**
```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

# Fă script-ul executable
chmod +x deploy_to_vps.sh

# Rulează deployment (replace cu IP-ul tău)
./deploy_to_vps.sh 164.92.135.47
```

**Ce face script-ul automat:**
```
1. ✅ Test SSH connection
2. ✅ Upload toate fișierele (rsync) - exclude logs, cache, .pyc
3. ✅ Upload .env (credentials)
4. ✅ SSH în VPS și rulează vps_setup.sh:
   ├─ Update system packages (apt update)
   ├─ Install Python 3.11 + pip
   ├─ Install system dependencies (git, curl, ufw)
   ├─ Create user 'forexgod'
   ├─ Setup project directory: /home/forexgod/trading-ai-agent
   ├─ Create Python virtual environment
   ├─ Install dependencies from requirements.txt
   ├─ Create 3 systemd services:
   │  ├─ trading-monitor.service (position_monitor.py)
   │  ├─ trade-monitor.service (trade_monitor.py)
   │  └─ trading-dashboard.service (HTTP server port 8080)
   ├─ Configure UFW firewall (open 22, 8080)
   └─ Start all services
5. ✅ Display dashboard URL: http://VPS_IP:8080
6. ✅ Display management commands
```

**3. Verifică deployment:**
```bash
# SSH în VPS
ssh root@164.92.135.47

# Check services
systemctl status trading-monitor
systemctl status trading-dashboard

# Check logs
tail -f /home/forexgod/trading-ai-agent/logs/position_monitor.log
```

**4. Accesează dashboard:**
```
Open browser: http://164.92.135.47:8080/dashboard_live.html
```

---

<a name="deployment-manual"></a>
## 🛠️ 6. DEPLOYMENT MANUAL - PAS CU PAS

Dacă `deploy_to_vps.sh` nu merge sau vrei control total:

### Pas 1: Pregătire VPS

**SSH în VPS:**
```bash
ssh root@YOUR_VPS_IP
```

**Update sistem:**
```bash
apt update && apt upgrade -y
```

**Install dependencies:**
```bash
apt install -y python3 python3-pip python3-venv git curl ufw
```

**Verifică versiune Python:**
```bash
python3 --version
# Trebuie: Python 3.10+ (Ubuntu 22.04 are 3.10 default)
```

---

### Pas 2: Create User & Directory

**Create user 'forexgod':**
```bash
useradd -m -s /bin/bash forexgod
passwd forexgod
# Enter password (ex: TradingBot2026!)

# Add to sudo group (optional)
usermod -aG sudo forexgod
```

**Create project directory:**
```bash
mkdir -p /home/forexgod/trading-ai-agent
chown -R forexgod:forexgod /home/forexgod/trading-ai-agent
```

---

### Pas 3: Upload Code (pe Mac)

**Opțiunea A: rsync (recomandată):**
```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

# Upload toate fișierele (exclude logs, cache)
rsync -avz --progress \
  --exclude 'logs/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.git/' \
  --exclude 'charts/' \
  --exclude 'backups/' \
  ./ root@YOUR_VPS_IP:/home/forexgod/trading-ai-agent/

# Upload .env separat (credentials)
scp .env root@YOUR_VPS_IP:/home/forexgod/trading-ai-agent/.env
```

**Opțiunea B: Git (dacă ai repo privat):**
```bash
# Pe VPS (după SSH):
cd /home/forexgod/trading-ai-agent
git clone https://github.com/YOUR_USERNAME/trading-ai-agent.git .

# Upload .env manual (NU include în git!)
# Pe Mac:
scp .env root@YOUR_VPS_IP:/home/forexgod/trading-ai-agent/.env
```

---

### Pas 4: Setup Python Environment (pe VPS)

```bash
# Switch to forexgod user
su - forexgod
cd ~/trading-ai-agent

# Create virtual environment
python3 -m venv venv

# Activate venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Test imports
python3 -c "import pandas, requests, matplotlib; print('✅ All packages OK')"
```

---

### Pas 5: Configure Environment

**Verifică `.env` file:**
```bash
cat .env
# Trebuie să conțină:
# TELEGRAM_BOT_TOKEN=...
# TELEGRAM_CHAT_ID=...
# CTRADER_ACCOUNT_ID=...
```

**Set permissions:**
```bash
chmod 600 .env  # Read/write doar pentru owner
```

**Create logs directory:**
```bash
mkdir -p logs
chmod 755 logs
```

---

### Pas 6: Test Manual Runs

**Test position_monitor.py:**
```bash
cd /home/forexgod/trading-ai-agent
source venv/bin/activate
python3 position_monitor.py
# Ar trebui să printeze: "Starting position monitor..."
# Ctrl+C să oprești
```

**Test dashboard:**
```bash
python3 -m http.server 8080
# Open browser: http://VPS_IP:8080
# Ctrl+C să oprești
```

---

<a name="systemd"></a>
## ⚙️ 7. CONFIGURARE SYSTEMD (Linux Services)

Systemd înlocuiește launchd de pe Mac - pornește automat serviciile.

### Create Service Files

**1. Position Monitor Service:**
```bash
sudo nano /etc/systemd/system/trading-monitor.service
```

**Conținut:**
```ini
[Unit]
Description=Glitch In Matrix - Position Monitor
After=network.target

[Service]
Type=simple
User=forexgod
WorkingDirectory=/home/forexgod/trading-ai-agent
Environment="PATH=/home/forexgod/trading-ai-agent/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/forexgod/trading-ai-agent/venv/bin/python3 position_monitor.py
Restart=always
RestartSec=10
StandardOutput=append:/home/forexgod/trading-ai-agent/logs/position_monitor.log
StandardError=append:/home/forexgod/trading-ai-agent/logs/position_monitor_error.log

[Install]
WantedBy=multi-user.target
```

**2. Dashboard Service:**
```bash
sudo nano /etc/systemd/system/trading-dashboard.service
```

**Conținut:**
```ini
[Unit]
Description=Glitch In Matrix - Dashboard HTTP Server
After=network.target

[Service]
Type=simple
User=forexgod
WorkingDirectory=/home/forexgod/trading-ai-agent
Environment="PATH=/home/forexgod/trading-ai-agent/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 -m http.server 8080
Restart=always
RestartSec=10
StandardOutput=append:/home/forexgod/trading-ai-agent/logs/http_server.log
StandardError=append:/home/forexgod/trading-ai-agent/logs/http_server_error.log

[Install]
WantedBy=multi-user.target
```

**3. Setup Executor Monitor Service (dacă folosești Cloud API):**
```bash
sudo nano /etc/systemd/system/trading-executor.service
```

**Conținut:**
```ini
[Unit]
Description=Glitch In Matrix - Setup Executor Monitor
After=network.target

[Service]
Type=simple
User=forexgod
WorkingDirectory=/home/forexgod/trading-ai-agent
Environment="PATH=/home/forexgod/trading-ai-agent/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/forexgod/trading-ai-agent/venv/bin/python3 setup_executor_monitor.py --loop --interval 30
Restart=always
RestartSec=10
StandardOutput=append:/home/forexgod/trading-ai-agent/logs/setup_executor.log
StandardError=append:/home/forexgod/trading-ai-agent/logs/setup_executor_error.log

[Install]
WantedBy=multi-user.target
```

---

### Enable & Start Services

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Enable services (auto-start on boot)
sudo systemctl enable trading-monitor.service
sudo systemctl enable trading-dashboard.service
sudo systemctl enable trading-executor.service

# Start services now
sudo systemctl start trading-monitor
sudo systemctl start trading-dashboard
sudo systemctl start trading-executor

# Check status
sudo systemctl status trading-monitor
sudo systemctl status trading-dashboard
sudo systemctl status trading-executor
```

---

### Management Commands

```bash
# Start service
sudo systemctl start trading-monitor

# Stop service
sudo systemctl stop trading-monitor

# Restart service
sudo systemctl restart trading-monitor

# View status
sudo systemctl status trading-monitor

# View logs (real-time)
sudo journalctl -u trading-monitor -f

# View last 100 lines
sudo journalctl -u trading-monitor -n 100

# Disable service (prevent auto-start)
sudo systemctl disable trading-monitor

# Re-enable
sudo systemctl enable trading-monitor
```

---

<a name="cron"></a>
## ⏰ 8. CONFIGURARE CRON (Scheduled Tasks)

Cron înlocuiește launchd pentru scheduled tasks (morning scan).

### Setup Morning Scan

**1. Editează crontab:**
```bash
# Switch to forexgod user
su - forexgod

# Open crontab editor
crontab -e
# Va deschide nano sau vi
```

**2. Adaugă morning scan job:**
```bash
# Morning Scan - Daily at 08:00 (Mon-Fri)
0 8 * * 1-5 cd /home/forexgod/trading-ai-agent && /home/forexgod/trading-ai-agent/venv/bin/python3 daily_scanner.py >> logs/morning_scan.log 2>&1

# News Calendar Check - Daily at 09:00
0 9 * * * cd /home/forexgod/trading-ai-agent && /home/forexgod/trading-ai-agent/venv/bin/python3 news_calendar_monitor.py >> logs/news_calendar.log 2>&1

# Weekly cleanup - Sunday at 02:00
0 2 * * 0 find /home/forexgod/trading-ai-agent/logs -name "*.log" -mtime +7 -delete
```

**Salvează:** Ctrl+X, apoi Y, apoi Enter

**3. Verifică crontab:**
```bash
crontab -l
```

---

### Cron Syntax Explained

```
* * * * * command
│ │ │ │ │
│ │ │ │ └─── Ziua săptămânii (0-7, 0=Sunday, 7=Sunday)
│ │ │ └───── Luna (1-12)
│ │ └─────── Ziua lunii (1-31)
│ └───────── Ora (0-23)
└─────────── Minutul (0-59)
```

**Exemple:**
```bash
# Every day at 08:00
0 8 * * *

# Monday-Friday at 08:00
0 8 * * 1-5

# Every hour
0 * * * *

# Every 30 minutes
*/30 * * * *

# First day of month at 00:00
0 0 1 * *
```

---

### Set Timezone

**IMPORTANT:** VPS-ul trebuie să fie în timezone-ul corect pentru morning scan!

```bash
# Check current timezone
timedatectl

# List available timezones
timedatectl list-timezones | grep Europe

# Set timezone (example: Europe/Bucharest)
sudo timedatectl set-timezone Europe/Bucharest

# Verify
timedatectl
# Output: Time zone: Europe/Bucharest (EET, +0200)
```

---

<a name="verificare"></a>
## ✅ 9. VERIFICARE POST-DEPLOYMENT

### Checklist Complet

**1. Verifică procese:**
```bash
ssh forexgod@YOUR_VPS_IP

# Check systemd services
systemctl status trading-monitor
systemctl status trading-dashboard

# Should show: Active: active (running)
```

**2. Verifică logs:**
```bash
cd /home/forexgod/trading-ai-agent

# Position monitor logs
tail -50 logs/position_monitor.log

# Dashboard logs
tail -50 logs/http_server.log

# Should show no errors, monitoring messages
```

**3. Test dashboard:**
```bash
# Local test
curl http://localhost:8080

# External test (pe Mac)
curl http://YOUR_VPS_IP:8080

# Browser test
# Open: http://YOUR_VPS_IP:8080/dashboard_live.html
```

**4. Test Telegram notifications:**
```bash
cd /home/forexgod/trading-ai-agent
source venv/bin/activate

python3 -c "
from notification_manager import NotificationManager
nm = NotificationManager()
nm.send_message('🧪 Test from VPS deployment - System is LIVE!')
"
```

**5. Verifică firewall:**
```bash
sudo ufw status
# Should show:
# 22/tcp   ALLOW
# 8080/tcp ALLOW
```

**6. Verifică cron jobs:**
```bash
crontab -l
# Should show morning scan scheduled
```

**7. Test manual morning scan:**
```bash
cd /home/forexgod/trading-ai-agent
source venv/bin/activate
python3 daily_scanner.py
# Should complete without errors
```

---

<a name="backup"></a>
## 💾 10. BACKUP & RECOVERY

### Backup Strategy

**Ce să backup-ezi:**
1. **Configuration files** (critical):
   - `.env` - credentials
   - `pairs_config.json` - trading pairs
   - `monitoring_setups.json` - active setups

2. **Data files** (important):
   - `trade_history.json` - trade records
   - `active_positions.json` - current positions

3. **Logs** (optional):
   - `logs/*.log` - debugging history

---

### Manual Backup (pe Mac)

**Full backup:**
```bash
# Create backup directory
mkdir -p ~/VPS_Backups/$(date +%Y-%m-%d)

# Download from VPS
scp -r forexgod@YOUR_VPS_IP:/home/forexgod/trading-ai-agent/.env ~/VPS_Backups/$(date +%Y-%m-%d)/
scp -r forexgod@YOUR_VPS_IP:/home/forexgod/trading-ai-agent/*.json ~/VPS_Backups/$(date +%Y-%m-%d)/
scp -r forexgod@YOUR_VPS_IP:/home/forexgod/trading-ai-agent/logs ~/VPS_Backups/$(date +%Y-%m-%d)/

echo "✅ Backup saved to ~/VPS_Backups/$(date +%Y-%m-%d)/"
```

**Quick backup (config only):**
```bash
scp forexgod@YOUR_VPS_IP:/home/forexgod/trading-ai-agent/{.env,pairs_config.json,monitoring_setups.json} ~/VPS_Backups/
```

---

### Automated Backup (pe VPS)

**Create backup script:**
```bash
sudo nano /home/forexgod/backup.sh
```

**Conținut:**
```bash
#!/bin/bash
BACKUP_DIR="/home/forexgod/backups/$(date +%Y-%m-%d)"
PROJECT_DIR="/home/forexgod/trading-ai-agent"

mkdir -p $BACKUP_DIR

# Backup critical files
cp $PROJECT_DIR/.env $BACKUP_DIR/
cp $PROJECT_DIR/pairs_config.json $BACKUP_DIR/
cp $PROJECT_DIR/monitoring_setups.json $BACKUP_DIR/
cp $PROJECT_DIR/trade_history.json $BACKUP_DIR/

# Compress
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

# Keep last 7 days only
find /home/forexgod/backups -name "*.tar.gz" -mtime +7 -delete

echo "✅ Backup created: $BACKUP_DIR.tar.gz"
```

**Make executable:**
```bash
chmod +x /home/forexgod/backup.sh
```

**Schedule daily backup (cron):**
```bash
crontab -e

# Add:
0 3 * * * /home/forexgod/backup.sh >> /home/forexgod/backups/backup.log 2>&1
```

---

### Recovery Procedure

**Restaurare completă pe VPS nou:**

```bash
# 1. SSH în VPS nou
ssh root@NEW_VPS_IP

# 2. Install dependencies (vezi Pas 1-2 din Deployment Manual)
apt update && apt install -y python3 python3-venv git

# 3. Create user & directory
useradd -m -s /bin/bash forexgod
mkdir -p /home/forexgod/trading-ai-agent

# 4. Upload backup (pe Mac)
scp ~/VPS_Backups/2026-01-06.tar.gz forexgod@NEW_VPS_IP:/home/forexgod/

# 5. Extract backup (pe VPS)
cd /home/forexgod
tar -xzf 2026-01-06.tar.gz -C trading-ai-agent/

# 6. Re-upload full code
# (rsync de pe Mac, vezi Pas 3)

# 7. Setup Python environment (vezi Pas 4)

# 8. Restart services
sudo systemctl restart trading-monitor trading-dashboard
```

---

<a name="troubleshooting"></a>
## 🔧 11. TROUBLESHOOTING - PROBLEME COMUNE

### Problema 1: SSH Connection Refused

**Simptom:**
```bash
ssh root@VPS_IP
# ssh: connect to host VPS_IP port 22: Connection refused
```

**Soluții:**
1. **Verifică firewall VPS:**
   ```bash
   # Pe VPS (prin console web):
   sudo ufw status
   sudo ufw allow 22/tcp
   ```

2. **Verifică SSH service:**
   ```bash
   sudo systemctl status ssh
   sudo systemctl start ssh
   ```

3. **Verifică IP corect:**
   - Login în DigitalOcean/Hetzner dashboard
   - Confirmă IP public al droplet-ului

---

### Problema 2: Service Won't Start

**Simptom:**
```bash
sudo systemctl status trading-monitor
# Active: failed (Result: exit-code)
```

**Debugging:**
```bash
# View detailed error
sudo journalctl -u trading-monitor -n 50

# Check for common issues:
# 1. Python module not found
sudo journalctl -u trading-monitor | grep "ModuleNotFoundError"
# Solution: pip install -r requirements.txt

# 2. Permission denied
sudo journalctl -u trading-monitor | grep "Permission denied"
# Solution: chown -R forexgod:forexgod /home/forexgod/trading-ai-agent

# 3. .env file missing
sudo journalctl -u trading-monitor | grep "TELEGRAM_BOT_TOKEN"
# Solution: Upload .env file

# Test manual run
su - forexgod
cd ~/trading-ai-agent
source venv/bin/activate
python3 position_monitor.py
# Check error output
```

---

### Problema 3: Dashboard nu se încarcă

**Simptom:**
```bash
curl http://VPS_IP:8080
# curl: (7) Failed to connect to VPS_IP port 8080: Connection refused
```

**Soluții:**

1. **Verifică service:**
   ```bash
   sudo systemctl status trading-dashboard
   # Dacă inactive:
   sudo systemctl start trading-dashboard
   ```

2. **Verifică firewall:**
   ```bash
   sudo ufw status
   # Dacă 8080 nu e listat:
   sudo ufw allow 8080/tcp
   sudo ufw reload
   ```

3. **Verifică port listening:**
   ```bash
   sudo netstat -tulpn | grep 8080
   # Ar trebui: tcp 0.0.0.0:8080 LISTEN
   ```

4. **Test local vs extern:**
   ```bash
   # Local (pe VPS):
   curl http://localhost:8080
   # Dacă merge local dar nu extern → firewall issue

   # Extern (pe Mac):
   curl http://VPS_IP:8080
   ```

---

### Problema 4: Telegram Notifications nu vin

**Simptom:**
- Services rulează OK
- Logs arată "Sending Telegram notification..."
- Dar mesajele nu apar în Telegram

**Debugging:**

1. **Verifică .env credentials:**
   ```bash
   cd /home/forexgod/trading-ai-agent
   cat .env | grep TELEGRAM
   # Verifică: TELEGRAM_BOT_TOKEN și TELEGRAM_CHAT_ID
   ```

2. **Test manual:**
   ```bash
   source venv/bin/activate
   python3 -c "
   from notification_manager import NotificationManager
   nm = NotificationManager()
   result = nm.send_message('Test from VPS')
   print(f'Result: {result}')
   "
   ```

3. **Verifică bot token valid:**
   ```bash
   TOKEN="YOUR_BOT_TOKEN"
   curl "https://api.telegram.org/bot$TOKEN/getMe"
   # Should return: {"ok":true, "result":{...}}
   ```

4. **Verifică chat ID:**
   ```bash
   # Send message to yourself to get chat ID
   # 1. Message your bot in Telegram
   # 2. Get updates:
   curl "https://api.telegram.org/bot$TOKEN/getUpdates"
   # Look for "chat":{"id": YOUR_CHAT_ID}
   ```

---

### Problema 5: Morning Scan nu rulează

**Simptom:**
- Cron job configurat la 08:00
- Dar `logs/morning_scan.log` nu se actualizează

**Debugging:**

1. **Verifică cron job activ:**
   ```bash
   crontab -l
   # Should show: 0 8 * * 1-5 cd /home/forexgod/trading-ai-agent && ...
   ```

2. **Verifică timezone:**
   ```bash
   timedatectl
   # Time zone trebuie să fie corect (ex: Europe/Bucharest)
   ```

3. **Test manual cron command:**
   ```bash
   # Copy exact command from crontab
   cd /home/forexgod/trading-ai-agent && /home/forexgod/trading-ai-agent/venv/bin/python3 daily_scanner.py >> logs/morning_scan.log 2>&1
   
   # Check logs
   tail -50 logs/morning_scan.log
   ```

4. **Check cron service:**
   ```bash
   sudo systemctl status cron
   # Should be active
   ```

5. **View cron execution log:**
   ```bash
   sudo grep CRON /var/log/syslog | tail -20
   # Should show cron executions
   ```

---

### Problema 6: High CPU Usage

**Simptom:**
```bash
top
# Python process using 80-100% CPU constantly
```

**Soluții:**

1. **Identifică procesul:**
   ```bash
   top
   # Press 'P' to sort by CPU
   # Note PID of high CPU process
   ```

2. **Check ce script rulează:**
   ```bash
   ps aux | grep python3
   # Identify: position_monitor.py, setup_executor_monitor.py, etc.
   ```

3. **Posibilă cauză: Tight loop fără sleep:**
   ```bash
   # Check logs for rapid iterations
   tail -100 logs/position_monitor.log | grep "Checking positions"
   # Dacă vezi mii de mesaje/secundă → loop issue
   ```

4. **Fix temporar:**
   ```bash
   # Restart service
   sudo systemctl restart trading-monitor
   ```

5. **Fix permanent:**
   - Verifică că monitors au `time.sleep()` în loop
   - Exemplu: `position_monitor.py` ar trebui să aibă `time.sleep(10)` între checks

---

### Problema 7: Disk Full

**Simptom:**
```bash
df -h
# /dev/vda1  20G  19G  0  100% /
```

**Soluții:**

1. **Identifică fișiere mari:**
   ```bash
   du -sh /home/forexgod/trading-ai-agent/*
   # Check: logs/, charts/, backups/
   ```

2. **Curăță logs vechi:**
   ```bash
   cd /home/forexgod/trading-ai-agent/logs
   find . -name "*.log" -mtime +7 -delete
   ```

3. **Curăță charts vechi:**
   ```bash
   cd /home/forexgod/trading-ai-agent/charts
   find . -name "*.png" -mtime +7 -delete
   ```

4. **Setup log rotation:**
   ```bash
   sudo nano /etc/logrotate.d/trading-bot
   
   # Add:
   /home/forexgod/trading-ai-agent/logs/*.log {
       daily
       rotate 7
       compress
       missingok
       notifempty
   }
   ```

---

<a name="monitorizare"></a>
## 📊 12. MONITORIZARE & MENTENANȚĂ

### Daily Health Checks

**1. Quick status check:**
```bash
ssh forexgod@VPS_IP

# One-liner status
systemctl is-active trading-monitor trading-dashboard && echo "✅ Services OK" || echo "❌ Services DOWN"
```

**2. Check logs for errors:**
```bash
cd /home/forexgod/trading-ai-agent

# Last 20 lines of each log
tail -20 logs/position_monitor.log | grep -i error
tail -20 logs/http_server.log | grep -i error
```

**3. Check disk space:**
```bash
df -h | grep vda1
# Alert if >80% used
```

**4. Check setups:**
```bash
cat monitoring_setups.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Active setups: {len(data[\"setups\"])}')
"
```

---

### Weekly Maintenance

**1. Update system packages:**
```bash
ssh root@VPS_IP
apt update && apt upgrade -y
```

**2. Restart services:**
```bash
sudo systemctl restart trading-monitor trading-dashboard
```

**3. Backup configuration:**
```bash
/home/forexgod/backup.sh
```

**4. Review logs for anomalies:**
```bash
cd /home/forexgod/trading-ai-agent/logs
grep -i "error\|exception\|failed" *.log
```

---

### Monitoring Tools (Optional)

**Install htop (better than top):**
```bash
sudo apt install htop
htop
```

**Install Glances (system monitoring):**
```bash
sudo apt install glances
glances
```

**Setup email alerts (cron failures):**
```bash
crontab -e

# Add MAILTO at top:
MAILTO=your-email@gmail.com

# Cron will email you on job failures
```

---

### Performance Optimization

**1. Reduce log verbosity:**
```python
# În position_monitor.py, setup_executor_monitor.py:
# Change logging level from DEBUG to INFO
import logging
logging.basicConfig(level=logging.INFO)  # Was: DEBUG
```

**2. Increase check intervals:**
```ini
# În trading-monitor.service:
# Dacă position_monitor.py are sleep(10), consideră sleep(30)
# Reduce CPU usage, trade-off: detectare mai lentă
```

**3. Archive old data:**
```bash
# Monthly cron job:
0 0 1 * * cd /home/forexgod/trading-ai-agent && tar -czf archives/data_$(date +%Y-%m).tar.gz *.json && rm -f *.json.old
```

---

## 🎯 QUICK REFERENCE - COMENZI ESENȚIALE

```bash
# ════════════════════════════════════════════════════════════
# SSH CONNECTION
# ════════════════════════════════════════════════════════════
ssh forexgod@YOUR_VPS_IP

# ════════════════════════════════════════════════════════════
# SERVICE MANAGEMENT
# ════════════════════════════════════════════════════════════
sudo systemctl status trading-monitor      # Check status
sudo systemctl start trading-monitor       # Start
sudo systemctl stop trading-monitor        # Stop
sudo systemctl restart trading-monitor     # Restart
sudo journalctl -u trading-monitor -f      # View logs (real-time)

# ════════════════════════════════════════════════════════════
# LOGS
# ════════════════════════════════════════════════════════════
tail -f /home/forexgod/trading-ai-agent/logs/position_monitor.log
tail -100 /home/forexgod/trading-ai-agent/logs/morning_scan.log
grep "error" /home/forexgod/trading-ai-agent/logs/*.log

# ════════════════════════════════════════════════════════════
# CRON (SCHEDULED TASKS)
# ════════════════════════════════════════════════════════════
crontab -l                                  # List cron jobs
crontab -e                                  # Edit cron jobs
sudo grep CRON /var/log/syslog | tail -20  # View cron execution log

# ════════════════════════════════════════════════════════════
# BACKUP (RUN ON MAC)
# ════════════════════════════════════════════════════════════
scp forexgod@VPS_IP:/home/forexgod/trading-ai-agent/{.env,*.json} ~/VPS_Backups/

# ════════════════════════════════════════════════════════════
# FIREWALL
# ════════════════════════════════════════════════════════════
sudo ufw status                            # Check firewall
sudo ufw allow 8080/tcp                    # Open port 8080
sudo ufw reload                            # Reload rules

# ════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════
# URL: http://YOUR_VPS_IP:8080/dashboard_live.html

# ════════════════════════════════════════════════════════════
# SYSTEM STATUS
# ════════════════════════════════════════════════════════════
df -h                                      # Disk usage
top                                        # CPU/RAM usage
systemctl list-units --state=failed       # Failed services
```

---

## 📝 NEXT STEPS - CE URMEAZĂ DUPĂ DEPLOYMENT

### Immediate (Primele 24h)

1. ✅ **Monitor logs** - verifică că nu apar erori
2. ✅ **Test Telegram notifications** - confirmă că primești alerte
3. ✅ **Access dashboard** - verifică că se actualizează
4. ✅ **Wait for morning scan** - confirmă că rulează la 08:00
5. ✅ **Backup config** - download .env și JSON-uri pe Mac

### Short-term (Prima săptămână)

1. 📊 **Monitor performance** - CPU, RAM, disk usage
2. 🔧 **Adjust check intervals** - optimizează dacă CPU prea mare
3. 🗑️ **Setup log rotation** - previi disk full
4. 🔒 **Harden security** - change SSH port, setup fail2ban
5. 📧 **Setup email alerts** - primești notificări dacă cron failed

### Long-term (Primul lună)

1. 🌐 **Setup domain** (optional) - trading.yourdomain.com → VPS_IP
2. 🔐 **Add dashboard auth** - nginx reverse proxy cu password
3. 📈 **Setup monitoring** - UptimeRobot (alertă dacă VPS cade)
4. 💾 **Automate backups** - rsync periodic de pe VPS pe Mac
5. 🚀 **Consider Cloud API** - elimină dependența de localhost:8767

---

## ⚠️ IMPORTANT NOTES - CITEȘTE ÎNAINTE DE DEPLOYMENT!

### ❗ Limitări Actuale

1. **cTrader cBot dependency**: Sistemul actual necesită `localhost:8767` (cBot pe Mac/Windows). VPS Linux singur **NU poate rula complet fără modificări**.

2. **Deployment scenarios**:
   - **Scenariul B (Hybrid)**: VPS + Mac acasă → necesită port forwarding
   - **Scenariul C (Windows VPS)**: €30-50/lună → scump dar funcționează 100%
   - **Scenariul D (Cloud API)**: €5-10/lună → necesită refactoring cod (2-4 ore)

3. **Best recommendation**: **Scenariul D (Cloud API)** - investiție inițială în cod, dar sistem 100% cloud după.

### 🎯 Deployment Decision Tree

```
Ai buget €30+/lună?
├─ DA → Scenariul C (Windows VPS) - deploy direct cu deploy_to_vps.sh (adaptează pentru Windows)
└─ NU → 
    ├─ Poți modifica cod? (2-4 ore)
    │  ├─ DA → Scenariul D (Cloud API) - cel mai bun long-term
    │  └─ NU → Scenariul B (Hybrid) - temporar OK, Mac rămâne pornit
    └─ Doar testing? → Scenariul A (Mac local) - deja funcționează
```

---

**Autor:** ForexGod  
**Data:** 2026-01-06  
**Versiune:** v1.0  
**System:** Glitch In Matrix v3.0  

**Project Path:** `/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo`

---

*🚀 Succes cu deployment-ul! Dacă întâmpini probleme, vezi secțiunea Troubleshooting sau contactează support.*
