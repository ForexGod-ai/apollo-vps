# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 CLEAN RESTART - Windows VPS - Glitch in Matrix
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Rulare: Right-click → "Run with PowerShell"
#         sau: powershell -ExecutionPolicy Bypass -File clean_restart_windows.ps1
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  GLITCH IN MATRIX - CLEAN RESTART" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# ━━━ STEP 1: KILL ALL PYTHON TRADING PROCESSES ━━━━━━━━━━━━━━
Write-Host "STEP 1: Oprire toate procesele Python..." -ForegroundColor Red
Write-Host ""

$scripts = @(
    "setup_executor_monitor",
    "position_monitor",
    "telegram_command_center",
    "watchdog_monitor",
    "ctrader_sync_daemon",
    "news_calendar_monitor",
    "news_reminder_engine",
    "auto_scanner_daemon",
    "daily_scanner"
)

foreach ($script in $scripts) {
    $procs = Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like "*$script*" }
    if ($procs) {
        foreach ($proc in $procs) {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Write-Host "  ✅ $script - OPRIT (PID: $($procs.ProcessId -join ', '))" -ForegroundColor Green
    } else {
        Write-Host "  ℹ️  $script - nu rula" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "⏳ Asteptam 3 secunde pentru shutdown complet..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# ━━━ STEP 2: VERIFY CLEAN STATE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Write-Host ""
Write-Host "STEP 2: Verificare procese ramase..." -ForegroundColor Cyan

$remaining = Get-WmiObject Win32_Process | Where-Object { 
    $_.CommandLine -like "*setup_executor_monitor*" -or
    $_.CommandLine -like "*position_monitor*" -or
    $_.CommandLine -like "*telegram_command_center*" -or
    $_.CommandLine -like "*watchdog_monitor*" -or
    $_.CommandLine -like "*ctrader_sync_daemon*" -or
    $_.CommandLine -like "*news_calendar_monitor*" -or
    $_.CommandLine -like "*news_reminder_engine*" -or
    $_.CommandLine -like "*auto_scanner_daemon*"
}

if ($remaining) {
    Write-Host "  ⚠️  ATENTIE: $($remaining.Count) procese inca ruleaza!" -ForegroundColor Red
    foreach ($p in $remaining) {
        Write-Host "    PID $($p.ProcessId): $($p.CommandLine)" -ForegroundColor Red
    }
} else {
    Write-Host "  ✅ Toate procesele oprite cu succes!" -ForegroundColor Green
}

# ━━━ STEP 3: GIT PULL ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "STEP 3: Git pull (ultimul cod)..." -ForegroundColor Cyan

$projectDir = "C:\Users\Administrator\Desktop\Glitch in Matrix\trading-ai-agent apollo"
Set-Location $projectDir
git pull origin main
Write-Host "  ✅ Git pull complet" -ForegroundColor Green

# ━━━ STEP 4: RESTART TOATE PROCESELE ━━━━━━━━━━━━━━━━━━━━━━━
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "STEP 4: Pornire procese fresh..." -ForegroundColor Green
Write-Host ""

$python = "python"
$dir = $projectDir

# Watchdog - porneste primul si el restarteaza restul
Start-Process $python -ArgumentList "watchdog_monitor.py" -WorkingDirectory $dir -WindowStyle Minimized
Write-Host "  ✅ Watchdog pornit" -ForegroundColor Green
Start-Sleep -Seconds 2

# Porneste restul manual (watchdog le va supraveghea)
Start-Process $python -ArgumentList "telegram_command_center.py" -WorkingDirectory $dir -WindowStyle Minimized
Write-Host "  ✅ Telegram Command Center pornit" -ForegroundColor Green
Start-Sleep -Seconds 1

Start-Process $python -ArgumentList "setup_executor_monitor.py" -WorkingDirectory $dir -WindowStyle Minimized
Write-Host "  ✅ Setup Executor pornit" -ForegroundColor Green
Start-Sleep -Seconds 1

Start-Process $python -ArgumentList "position_monitor.py" -WorkingDirectory $dir -WindowStyle Minimized
Write-Host "  ✅ Position Monitor pornit" -ForegroundColor Green
Start-Sleep -Seconds 1

Start-Process $python -ArgumentList "ctrader_sync_daemon.py" -WorkingDirectory $dir -WindowStyle Minimized
Write-Host "  ✅ cTrader Sync Daemon pornit" -ForegroundColor Green
Start-Sleep -Seconds 1

Start-Process $python -ArgumentList "news_calendar_monitor.py" -WorkingDirectory $dir -WindowStyle Minimized
Write-Host "  ✅ News Calendar Monitor pornit" -ForegroundColor Green
Start-Sleep -Seconds 1

Start-Process $python -ArgumentList "news_reminder_engine.py" -WorkingDirectory $dir -WindowStyle Minimized
Write-Host "  ✅ News Reminder Engine pornit" -ForegroundColor Green
Start-Sleep -Seconds 1

Start-Process $python -ArgumentList "auto_scanner_daemon.py" -WorkingDirectory $dir -WindowStyle Minimized
Write-Host "  ✅ Auto Scanner Daemon pornit" -ForegroundColor Green

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  DONE! Toate procesele pornite fresh (8/8)" -ForegroundColor Green
Write-Host "  Asteapta 30 secunde apoi verifica /status pe Telegram" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

Read-Host "Apasa ENTER pentru a inchide"
