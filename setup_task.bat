@echo off
REM Setup Task Scheduler for Morning Scan at 09:00 with WAKE UP

echo.
echo ========================================
echo GLITCH IN MATRIX - Morning Scan Setup
echo ========================================
echo.

set "WORK_DIR=%~dp0"
set "PYTHON_EXE=python"
set "SCAN_SCRIPT=%WORK_DIR%complete_scan_with_charts.py"

echo Setting up daily scan at 09:00...
echo.
echo Task: GLITCH_MorningScan
echo Time: 09:00 Daily
echo Wake: YES
echo.

REM Create wrapper script
echo @echo off > "%WORK_DIR%run_scan.bat"
echo cd /d "%WORK_DIR%" >> "%WORK_DIR%run_scan.bat"
echo python complete_scan_with_charts.py ^> scan_log.txt 2^>^&1 >> "%WORK_DIR%run_scan.bat"

REM Create scheduled task
schtasks /Create /TN "GLITCH_MorningScan" /TR "\"%WORK_DIR%run_scan.bat\"" /SC DAILY /ST 09:00 /RU "%USERNAME%" /RL HIGHEST /F

if %ERRORLEVEL% EQU 0 (
    echo Task created successfully!
    echo.
    echo Enabling WAKE COMPUTER feature...
    
    powershell -Command "$task = Get-ScheduledTask -TaskName 'GLITCH_MorningScan'; $task.Settings.WakeToRun = $true; $task.Settings.AllowHardTerminate = $false; $task.Settings.ExecutionTimeLimit = 'PT1H'; Set-ScheduledTask -InputObject $task"
    
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo ========================================
        echo SUCCESS! All configured!
        echo ========================================
        echo.
        echo Your laptop will now:
        echo   - WAKE UP at 08:59 if sleeping
        echo   - RUN SCAN at 09:00 every day
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
