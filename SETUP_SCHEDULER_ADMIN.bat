@echo off
echo ========================================
echo   FOREX GOD - Task Scheduler Setup
echo ========================================
echo.
echo This will create a daily task at 08:00 AM
echo.
echo Right-click this file and select "Run as Administrator"
echo.
pause

powershell -ExecutionPolicy Bypass -Command "$action = New-ScheduledTaskAction -Execute 'python' -Argument '%~dp0run_daily_scan.py' -WorkingDirectory '%~dp0'; $trigger = New-ScheduledTaskTrigger -Daily -At '08:00AM'; $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable; $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest; Register-ScheduledTask -TaskName 'ForexGod Glitch Scanner' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Daily forex scanner at 08:00 AM' -Force"

echo.
echo ========================================
echo Task created successfully!
echo.
echo The scanner will run automatically every day at 08:00 AM
echo.
echo To test now: python run_daily_scan.py
echo ========================================
pause
