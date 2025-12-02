# Setup Windows Task Scheduler for Morning GLITCH Scan at 08:00
# Run this script as Administrator

$taskName = "GLITCH_Morning_Scan"
$scriptPath = "C:\Users\admog\Desktop\siteRazvan\trading-ai-agent\morning_glitch_scan.py"
$pythonPath = "python"  # Adjust if needed
$workingDir = "C:\Users\admog\Desktop\siteRazvan\trading-ai-agent"

# Create the action
$action = New-ScheduledTaskAction -Execute $pythonPath `
    -Argument $scriptPath `
    -WorkingDirectory $workingDir

# Create the trigger (daily at 08:00)
$trigger = New-ScheduledTaskTrigger -Daily -At 08:00

# Create settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Register the task
Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Daily GLITCH IN MATRIX morning scan at 08:00 - sends results to Telegram" `
    -Force

Write-Host "✅ Task '$taskName' created successfully!" -ForegroundColor Green
Write-Host "📅 Will run daily at 08:00" -ForegroundColor Cyan
Write-Host "📱 Results will be sent to Telegram" -ForegroundColor Cyan
Write-Host ""
Write-Host "To test now, run:" -ForegroundColor Yellow
Write-Host "  python morning_glitch_scan.py" -ForegroundColor White
Write-Host ""
Write-Host "To view/edit task, open Task Scheduler and look for '$taskName'" -ForegroundColor Gray
