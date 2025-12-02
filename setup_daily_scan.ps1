# Setup Daily Scan - PowerShell version
# Run this as Administrator

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "GLITCH IN MATRIX - DAILY SCAN SETUP" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$workDir = $PSScriptRoot
$wrapperPath = Join-Path $workDir "run_scan.bat"

Write-Host "Setting up DAILY scan at 09:00..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Task: GLITCH_MorningScan"
Write-Host "Time: 09:00 DAILY (Mon-Sun)"
Write-Host "Wake: YES"
Write-Host "Mode: Auto-detect weekend"
Write-Host ""

# Delete old task
schtasks /Delete /TN "GLITCH_MorningScan" /F 2>$null | Out-Null

# Create wrapper batch file
@"
@echo off
cd /d "$workDir"
python complete_scan_with_charts.py > scan_log.txt 2>&1
"@ | Out-File -FilePath $wrapperPath -Encoding ASCII

# Create scheduled task
$result = schtasks /Create /TN "GLITCH_MorningScan" /TR "`"$wrapperPath`"" /SC DAILY /ST 09:00 /RU "$env:USERNAME" /RL HIGHEST /F

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Task created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Enabling WAKE COMPUTER feature..." -ForegroundColor Yellow
    
    $task = Get-ScheduledTask -TaskName 'GLITCH_MorningScan'
    $task.Settings.WakeToRun = $true
    $task.Settings.AllowHardTerminate = $false
    $task.Settings.ExecutionTimeLimit = 'PT1H'
    $task.Settings.StartWhenAvailable = $true
    Set-ScheduledTask -InputObject $task | Out-Null
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "✅ SUCCESS! Daily scan configured!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Your laptop will now:" -ForegroundColor White
    Write-Host "  ✅ WAKE UP at 08:59 if sleeping" -ForegroundColor Green
    Write-Host "  ✅ RUN SCAN at 09:00 EVERY DAY" -ForegroundColor Green
    Write-Host "  📊 Monday-Friday: All FOREX pairs + BTCUSD" -ForegroundColor Yellow
    Write-Host "  🔷 Saturday-Sunday: BTCUSD only" -ForegroundColor Cyan
    Write-Host "  📱 SEND results to Telegram" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can safely CLOSE your laptop! 💤" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor White
    Write-Host "  Test now:  schtasks /Run /TN 'GLITCH_MorningScan'" -ForegroundColor Gray
    Write-Host "  Disable:   schtasks /Change /TN 'GLITCH_MorningScan' /DISABLE" -ForegroundColor Gray
    Write-Host "  Remove:    schtasks /Delete /TN 'GLITCH_MorningScan' /F" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "❌ ERROR! Need Administrator privileges" -ForegroundColor Red
    Write-Host ""
    Write-Host "Right-click PowerShell and 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "Press any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
