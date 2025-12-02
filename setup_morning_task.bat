@echo off
REM ========================================
REM Setup Windows Task Scheduler for Morning Scan
REM Laptop will WAKE UP automatically at 08:59 and run scan at 09:00
REM ========================================

echo.
echo ========================================
echo SETTING UP AUTOMATIC MORNING SCAN
echo ========================================
echo.

REM Get current directory
set "SCRIPT_DIR=%~dp0"
set "PYTHON_SCRIPT=%SCRIPT_DIR%complete_scan_with_charts.py"

echo Creating Windows Task Scheduler entry...
echo.
echo Task Name: GLITCH_MorningScan
echo Run Time: 09:00 Daily
echo Wake Computer: YES
echo.

REM Create the scheduled task with WAKE UP enabled
schtasks /Create /TN "GLITCH_MorningScan" /TR "cmd /c cd /d \"%SCRIPT_DIR%\" && python complete_scan_with_charts.py > scan_log.txt 2>&1" /SC DAILY /ST 09:00 /RU "%USERNAME%" /RL HIGHEST /F

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS! Task created successfully!
    echo ========================================
    echo.
    
    echo Now enabling WAKE COMPUTER option...
    echo.
    
    REM Enable wake computer feature using PowerShell
    powershell -Command "$task = Get-ScheduledTask -TaskName 'GLITCH_MorningScan'; $task.Settings.WakeToRun = $true; Set-ScheduledTask -InputObject $task"
    
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo ========================================
        echo PERFECT! All set up!
        echo ========================================
        echo.
        echo What this does:
        echo   - Laptop will WAKE UP at 08:59 if sleeping
        echo   - Runs scan at 09:00 EVERY DAY
        echo   - Sends results to Telegram
        echo   - You can CLOSE LAPTOP safely!
        echo.
        echo To view the task:
        echo   - Open Task Scheduler
        echo   - Look for: GLITCH_MorningScan
        echo.
        echo To disable:
        echo   schtasks /Change /TN "GLITCH_MorningScan" /DISABLE
        echo.
        echo To delete:
        echo   schtasks /Delete /TN "GLITCH_MorningScan" /F
        echo.
        echo ========================================
    ) else (
        echo.
        echo WARNING: Task created but wake feature may need manual activation
        echo Please check Task Scheduler and enable "Wake the computer to run this task"
        echo.
    )
) else (
    echo.
    echo ========================================
    echo ERROR! Failed to create task
    echo ========================================
    echo.
    echo Try running this script as Administrator:
    echo   - Right-click setup_morning_task.bat
    echo   - Select "Run as Administrator"
    echo.
)

echo.
echo Press any key to exit...
pause >nul
