# ForexGod Glitch Scanner - Task Scheduler Setup
# Run this script as Administrator

Write-Host "🔧 Setting up Task Scheduler for ForexGod Glitch Scanner..." -ForegroundColor Cyan
Write-Host ""

$taskName = "FOREXGOD Morning Scan 09:00"
$scriptPath = "c:\Users\admog\Desktop\siteRazvan\trading-ai-agent\complete_scan_with_charts.py"
$workingDir = "c:\Users\admog\Desktop\siteRazvan\trading-ai-agent"
$pythonExe = "python"

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "⚠️  Task already exists. Removing old task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Create action (run Python script directly)
$action = New-ScheduledTaskAction -Execute $pythonExe -Argument $scriptPath -WorkingDirectory $workingDir

# Create trigger (daily at 09:00)
$trigger = New-ScheduledTaskTrigger -Daily -At "09:00AM"

# Create settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# Create principal (run as current user)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest

# Register task
try {
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "Daily market scan at 09:00 - Glitch in Matrix with Charts & Telegram" `
        -Force | Out-Null
    
    Write-Host "✅ Task Scheduler configured successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📋 Task Details:" -ForegroundColor Cyan
    Write-Host "   Name: $taskName"
    Write-Host "   Schedule: Daily at 09:00 AM"
    Write-Host "   Script: $scriptPath"
    Write-Host ""
    Write-Host "🎯 Scanner will run automatically every day at 09:00!" -ForegroundColor Green
    Write-Host "📱 Results with charts will be sent to Telegram" -ForegroundColor Green
    
} catch {
    Write-Host "❌ Error creating task: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 Make sure to run PowerShell as Administrator!" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Press any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
