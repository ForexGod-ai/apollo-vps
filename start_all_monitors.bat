@echo off
title GLITCH IN MATRIX — Launcher
cd /d "%~dp0"

echo.
echo ╔═══════════════════════════════════════════════════╗
echo ║  ✨ GLITCH IN MATRIX by ForexGod ✨             ║
echo ║  Starting All 7 Monitors — Windows VPS Helsinki  ║
echo ╚═══════════════════════════════════════════════════╝
echo.

:: Create logs directory
if not exist logs mkdir logs

:: Kill any existing instances cleanly
echo [0/7] Cleaning up old Python processes...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq [1] cTrader Sync*"        2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq [2] Position Monitor*"    2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq [3] THE COMMANDER*"       2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq [4] Telegram CC*"         2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq [5] News Calendar*"       2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq [6] News Reminder*"       2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq [7] Watchdog*"            2>nul
del /Q process_*.lock 2>nul
timeout /t 2 /nobreak >nul

echo.
echo [1/7] Starting cTrader Sync Daemon...
start "[1] cTrader Sync" /MIN cmd /c "python ctrader_sync_daemon.py --loop >> logs\ctrader_sync_daemon.log 2>&1"
timeout /t 2 /nobreak >nul

echo [2/7] Starting Position Monitor...
start "[2] Position Monitor" /MIN cmd /c "python position_monitor.py --loop >> logs\position_monitor.log 2>&1"
timeout /t 2 /nobreak >nul

echo [3/7] Starting Setup Executor Monitor [THE COMMANDER]...
start "[3] THE COMMANDER" /MIN cmd /c "python setup_executor_monitor.py --interval 30 --loop >> logs\setup_executor_monitor.log 2>&1"
timeout /t 2 /nobreak >nul

echo [4/7] Starting Telegram Command Center...
start "[4] Telegram CC" /MIN cmd /c "python telegram_command_center.py >> logs\telegram_command_center.log 2>&1"
timeout /t 2 /nobreak >nul

echo [5/7] Starting News Calendar Monitor...
start "[5] News Calendar" /MIN cmd /c "python news_calendar_monitor.py >> logs\news_calendar_monitor.log 2>&1"
timeout /t 2 /nobreak >nul

echo [6/7] Starting News Reminder Engine...
start "[6] News Reminder" /MIN cmd /c "python news_reminder_engine.py >> logs\news_reminder_engine.log 2>&1"
timeout /t 2 /nobreak >nul

echo [7/7] Starting Watchdog Monitor...
start "[7] Watchdog" /MIN cmd /c "python watchdog_monitor.py --interval 60 >> logs\watchdog_monitor.log 2>&1"
timeout /t 4 /nobreak >nul

echo.
echo ╔═══════════════════════════════════════════════════╗
echo ║  ✅ All 7 monitors started!                      ║
echo ║  Named windows: [1] through [7]                  ║
echo ║  Logs: logs\*.log  (one file per monitor)        ║
echo ║  Use Task Manager to verify all python.exe alive ║
echo ╚═══════════════════════════════════════════════════╝
echo.
echo Press any key to exit launcher...
pause >nul
