@echo off
REM Setup DAILY Task Scheduler (Monday-Sunday at 09:00)
REM - Weekdays: All pairs
REM - Weekends: BTCUSD only (auto-detected in script)

echo.
echo ========================================
echo GLITCH IN MATRIX - DAILY SCAN SETUP
echo ========================================
echo.

set "WORK_DIR=%~dp0"
set "SCAN_SCRIPT=%WORK_DIR%complete_scan_with_charts.py"

echo Setting up DAILY scan at 09:00...
echo.
echo Task: GLITCH_MorningScan
echo Time: 09:00 DAILY (Mon-Sun)
echo Wake: YES
echo Mode: Auto-detect weekend
echo.

REM Delete old task if exists
schtasks /Delete /TN "GLITCH_MorningScan" /F >nul 2>&1

REM Create wrapper script
echo @echo off > "%WORK_DIR%run_scan.bat"
echo cd /d "%WORK_DIR%" >> "%WORK_DIR%run_scan.bat"
echo python complete_scan_with_charts.py ^> scan_log.txt 2^>^&1 >> "%WORK_DIR%run_scan.bat"

REM Create DAILY scheduled task (runs every day)
schtasks /Create /TN "GLITCH_MorningScan" /TR "\"%WORK_DIR%run_scan.bat\"" /SC DAILY /ST 09:00 /RU "%USERNAME%" /RL HIGHEST /F

if %ERRORLEVEL% EQU 0 (
    echo Task created successfully!
    echo.
    echo Enabling WAKE COMPUTER feature...
    
    powershell -Command "$task = Get-ScheduledTask -TaskName 'GLITCH_MorningScan'; $task.Settings.WakeToRun = $true; $task.Settings.AllowHardTerminate = $false; $task.Settings.ExecutionTimeLimit = 'PT1H'; $task.Settings.StartWhenAvailable = $true; Set-ScheduledTask -InputObject $task"
    
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo ========================================
        echo SUCCESS! Daily scan configured!
        echo ========================================
        echo.
        echo Your laptop will now:
        echo   - WAKE UP at 08:59 if sleeping
        echo   - RUN SCAN at 09:00 EVERY DAY
        echo   - Monday-Friday: All FOREX pairs + BTCUSD
        echo   - Saturday-Sunday: BTCUSD only
        echo   - SEND results to Telegram
        echo.
        echo You can safely CLOSE your laptop!
        echo.
        echo To view: Open Task Scheduler and look for "GLITCH_MorningScan"
        echo.
        echo To test now: schtasks /Run /TN "GLITCH_MorningScan"
        echo To disable:  schtasks /Change /TN "GLITCH_MorningScan" /DISABLE
        echo To remove:   schtasks /Delete /TN "GLITCH_MorningScan" /F
        echo.
    ) else (
        echo Task created but wake feature needs manual setup
        echo Open Task Scheduler ^> GLITCH_MorningScan ^> Properties
        echo Enable: "Wake the computer to run this task"
    )
) else (
    echo.
    echo ERROR! Need Administrator privileges
    echo.
    echo Right-click this file and select "Run as Administrator"
    echo.
)

echo.
pause
