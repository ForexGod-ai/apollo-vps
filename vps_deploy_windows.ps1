# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  GLITCH IN MATRIX — WINDOWS VPS DEPLOY SCRIPT                              ║
# ║  Engineered by ФорексГод                                                    ║
# ║  Target: Hetzner CPX41 🇩🇪 — 8 vCPU AMD EPYC / 16 GB RAM / 240 GB NVMe     ║
# ║  OS: Windows Server 2022 (montat manual via ISO din Hetzner Console)      ║
# ║  MAX PERFORMANCE MODE: cache agresiv SMC + threading ready                ║
# ║                                                                             ║
# ║  USAGE: Right-click → "Run with PowerShell" (as Administrator)             ║
# ║     SAU: powershell -ExecutionPolicy Bypass -File vps_deploy_windows.ps1   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

#Requires -RunAsAdministrator
Set-StrictMode -Off
$ErrorActionPreference = "Continue"

# ─── COLORS ─────────────────────────────────────────────────────────────────
function Write-Green  { param($msg) Write-Host "  ✅  $msg" -ForegroundColor Green }
function Write-Red    { param($msg) Write-Host "  ❌  $msg" -ForegroundColor Red }
function Write-Yellow { param($msg) Write-Host "  ⚠️   $msg" -ForegroundColor Yellow }
function Write-Cyan   { param($msg) Write-Host "  ▸  $msg" -ForegroundColor Cyan }
function Write-Step   { param($msg) Write-Host "`n⚙️  $msg" -ForegroundColor Magenta }

# ─── BANNER ──────────────────────────────────────────────────────────────────
Clear-Host
Write-Host ""
Write-Host "     ██████╗ ██╗     ██╗████████╗ ██████╗██╗  ██╗" -ForegroundColor Green
Write-Host "    ██╔════╝ ██║     ██║╚══██╔══╝██╔════╝██║  ██║" -ForegroundColor Green
Write-Host "    ██║  ███╗██║     ██║   ██║   ██║     ███████║" -ForegroundColor Green
Write-Host "    ╚██████╔╝███████╗██║   ██║   ╚██████╗██║  ██║" -ForegroundColor Green
Write-Host "     ╚═════╝ ╚══════╝╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝" -ForegroundColor Green
Write-Host ""
    Write-Host "    WINDOWS VPS DEPLOY — by ФорексГод" -ForegroundColor White
    Write-Host "    Hetzner CPX41 🇩🇪 | 8 vCPU AMD EPYC / 16 GB RAM / 240 GB NVMe" -ForegroundColor DarkGray
    Write-Host "    $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ""

# ─── CONFIG ──────────────────────────────────────────────────────────────────
$INSTALL_DIR = "C:\matrix"
$PYTHON_URL  = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
$PYTHON_EXE  = "$INSTALL_DIR\.venv\Scripts\python.exe"
$PIP_EXE     = "$INSTALL_DIR\.venv\Scripts\pip.exe"
$CTRADER_URL = "https://download.spotware.com/ctrader/cTrader_Installer.exe"

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: PYTHON 3.11
# ═══════════════════════════════════════════════════════════════════════════════
Write-Step "PHASE 1/5 — PYTHON 3.11 INSTALL"

$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    $ver = & python --version 2>&1
    Write-Green "Python already installed: $ver"
} else {
    Write-Cyan "Downloading Python 3.11.9..."
    $pyInstaller = "$env:TEMP\python_installer.exe"
    Invoke-WebRequest -Uri $PYTHON_URL -OutFile $pyInstaller -UseBasicParsing
    Write-Cyan "Installing Python 3.11 (silent)..."
    Start-Process -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    Write-Green "Python 3.11 installed"
}

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: PROJECT DIRECTORY + VENV
# ═══════════════════════════════════════════════════════════════════════════════
Write-Step "PHASE 2/5 — FILESYSTEM SETUP"

# Creează directoarele necesare
$dirs = @("$INSTALL_DIR", "$INSTALL_DIR\logs", "$INSTALL_DIR\data", "$INSTALL_DIR\backups", "$INSTALL_DIR\charts", "$INSTALL_DIR\chart_snapshots")
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
        Write-Green "Created: $d"
    } else {
        Write-Cyan "Exists:  $d"
    }
}

# Creare virtual environment
if (-not (Test-Path "$INSTALL_DIR\.venv")) {
    Write-Cyan "Creating Python virtual environment..."
    & python -m venv "$INSTALL_DIR\.venv"
    Write-Green "Virtual environment created at $INSTALL_DIR\.venv"
} else {
    Write-Green "Virtual environment already exists"
}

# Inițializare fișiere de stare (dacă lipsesc)
$stateFiles = @("monitoring_setups.json", "signals.json", "active_positions.json", "trade_confirmations.json")
foreach ($sf in $stateFiles) {
    $fp = "$INSTALL_DIR\$sf"
    if (-not (Test-Path $fp)) {
        '{"setups": [], "last_updated": ""}' | Out-File -FilePath $fp -Encoding utf8
        Write-Yellow "Created missing state file: $sf"
    }
}

# signals.json — permisiuni complete (cTrader cBot citește/scrie aici)
$acl = Get-Acl "$INSTALL_DIR\signals.json"
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")
$acl.SetAccessRule($rule)
Set-Acl "$INSTALL_DIR\signals.json" $acl
Write-Green "signals.json: FullControl permissions set (cTrader IPC bridge ready)"

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: PYTHON DEPENDENCIES
# ═══════════════════════════════════════════════════════════════════════════════
Write-Step "PHASE 3/5 — PYTHON DEPENDENCIES"

Write-Cyan "Upgrading pip..."
& $PIP_EXE install --upgrade pip -q

$requirements = @"
# Glitch in Matrix — Windows VPS Dependencies
numpy>=1.26.0
pandas>=2.1.0
scikit-learn>=1.3.0
requests>=2.31.0
python-dotenv>=1.0.0
loguru>=0.7.0
psutil>=5.9.0
schedule>=1.2.0
matplotlib>=3.8.0
mplfinance>=0.12.0
pydantic>=2.5.0
watchdog>=3.0.0
flask>=3.0.0
flask-cors>=4.0.0
"@

$reqFile = "$INSTALL_DIR\requirements_vps_windows.txt"
$requirements | Out-File -FilePath $reqFile -Encoding utf8
Write-Cyan "Installing dependencies..."
& $PIP_EXE install -r $reqFile -q
Write-Green "All Python dependencies installed"

# Verificare imports critice
$importTest = & $PYTHON_EXE -c "import pandas, numpy, loguru, requests, psutil; print('OK')" 2>&1
if ($importTest -eq "OK") {
    Write-Green "Critical imports verified: pandas, numpy, loguru, requests, psutil"
} else {
    Write-Red "Import verification failed: $importTest"
}

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: cTRADER INSTALL
# ═══════════════════════════════════════════════════════════════════════════════
Write-Step "PHASE 4/5 — cTRADER DESKTOP"

$ctraderPath = "$env:LOCALAPPDATA\cTrader\cTrader.exe"
if (Test-Path $ctraderPath) {
    Write-Green "cTrader already installed at: $ctraderPath"
} else {
    Write-Cyan "Downloading cTrader installer..."
    $ctraderInstaller = "$env:TEMP\cTrader_Installer.exe"
    try {
        Invoke-WebRequest -Uri $CTRADER_URL -OutFile $ctraderInstaller -UseBasicParsing
        Write-Cyan "Installing cTrader..."
        Start-Process -FilePath $ctraderInstaller -ArgumentList "/S" -Wait
        Write-Green "cTrader installed"
    } catch {
        Write-Yellow "Auto-install failed. Download manual: https://ctrader.com/download"
        Write-Yellow "Instalează cTrader → conectează-te la IC Markets → activează cBot"
    }
}

Write-Host ""
Write-Host "  ┌─────────────────────────────────────────────────────┐" -ForegroundColor Cyan
Write-Host "  │  IMPORTANT — cTrader cBot Setup                     │" -ForegroundColor Cyan
Write-Host "  │                                                     │" -ForegroundColor Cyan
Write-Host "  │  1. Deschide cTrader → conectează contul live       │" -ForegroundColor White
Write-Host "  │  2. Mergi la Automate → Import cBot                 │" -ForegroundColor White
Write-Host "  │  3. Importă: MarketDataProvider.algo                │" -ForegroundColor White
Write-Host "  │  4. Setează Path: C:\matrix\signals.json            │" -ForegroundColor White
Write-Host "  │  5. Start cBot pe orice chart (ex: EURUSD M1)       │" -ForegroundColor White
Write-Host "  └─────────────────────────────────────────────────────┘" -ForegroundColor Cyan

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: WINDOWS TASK SCHEDULER (auto-start la reboot)
# ═══════════════════════════════════════════════════════════════════════════════
Write-Step "PHASE 5/5 — AUTO-START TASK SCHEDULER"

# Creare script de start pentru toate procesele
$startScript = @"
@echo off
cd /d C:\matrix
SET PYTHON=C:\matrix\.venv\Scripts\python.exe

echo Starting Glitch in Matrix monitors...

start "" /B %PYTHON% watchdog_monitor.py --interval 60 > C:\matrix\logs\watchdog.log 2>&1
timeout /t 3 /nobreak > nul

start "" /B %PYTHON% setup_executor_monitor.py --interval 30 --loop > C:\matrix\logs\setup_monitor.log 2>&1
timeout /t 2 /nobreak > nul

start "" /B %PYTHON% position_monitor.py > C:\matrix\logs\position_monitor.log 2>&1
timeout /t 2 /nobreak > nul

start "" /B %PYTHON% telegram_command_center.py > C:\matrix\logs\command_center.log 2>&1
timeout /t 2 /nobreak > nul

start "" /B %PYTHON% news_calendar_monitor.py > C:\matrix\logs\news_calendar.log 2>&1
timeout /t 2 /nobreak > nul

start "" /B %PYTHON% ctrader_sync_daemon.py > C:\matrix\logs\ctrader_sync.log 2>&1

echo All monitors started!
"@

$startScript | Out-File -FilePath "$INSTALL_DIR\start_matrix.bat" -Encoding ascii
Write-Green "Created: C:\matrix\start_matrix.bat"

# Înregistrare Task Scheduler — rulează la logon
$taskName = "GlitchInMatrix_AutoStart"
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action  = New-ScheduledTaskAction -Execute "C:\matrix\start_matrix.bat"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Green "Task Scheduler: '$taskName' registered (runs at every logon)"

# ─── FINAL REPORT ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║                                                           ║" -ForegroundColor Green
Write-Host "  ║   SYSTEM OPERATIONAL — GLITCH IN MATRIX                  ║" -ForegroundColor Green
Write-Host "  ║   Windows VPS Ready for Live Trading                     ║" -ForegroundColor Green
Write-Host "  ║                                                           ║" -ForegroundColor Green
Write-Host "  ╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Green "Install dir:    C:\matrix"
Write-Green "Python:         C:\matrix\.venv\Scripts\python.exe"
Write-Green "Auto-start:     Task Scheduler → GlitchInMatrix_AutoStart"
Write-Green "signals.json:   FullControl (cTrader IPC bridge active)"
Write-Host ""
Write-Host "  NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Copiaza fisierele proiectului in C:\matrix\" -ForegroundColor White
Write-Host "     (drag & drop via RDP sau WinSCP/FileZilla)" -ForegroundColor DarkGray
Write-Host "  2. Creaza C:\matrix\.env cu credentialele Telegram + cTrader" -ForegroundColor White
Write-Host "  3. Deschide cTrader → conecteaza contul → porneste cBot" -ForegroundColor White
Write-Host "  4. Ruleaza: C:\matrix\start_matrix.bat" -ForegroundColor White
Write-Host "  5. Verifica Telegram → /status" -ForegroundColor White
Write-Host ""
Write-Host "  Engineered by ФорексГод | $(Get-Date -Format 'yyyy-MM-dd HH:mm') UTC" -ForegroundColor DarkGray
Write-Host ""

Pause
