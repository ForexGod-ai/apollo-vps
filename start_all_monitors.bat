@echo off
cd /d "%~dp0"

echo.
echo ╔═══════════════════════════════════════════════════╗
echo ║  ✨ GLITCH IN MATRIX by ForexGod ✨             ║
echo ║  Starting All 7 Monitors on Windows VPS         ║
echo ╚═══════════════════════════════════════════════════╝
echo.

:: Create logs directory
if not exist logs mkdir logs

:: Kill any existing instances
echo Cleaning up old processes...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq ctrader_sync_daemon*" 2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq position_monitor*" 2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq setup_executor_monitor*" 2>nul
timeout /t 2 /nobreak >nul

echo.
echo 1/7 Starting cTrader Sync Daemon...
start "ctrader_sync_daemon" /MIN .venv\Scripts\python.exe ctrader_sync_daemon.py --loop

timeout /t 2 /nobreak >nul

echo 2/7 Starting Position Monitor...
start "position_monitor" /MIN .venv\Scripts\python.exe position_monitor.py --loop

timeout /t 2 /nobreak >nul

echo 3/7 Starting Setup Executor Monitor [COMANDANTUL]...
start "setup_executor_monitor" /MIN .venv\Scripts\python.exe setup_executor_monitor.py --interval 30 --loop

timeout /t 2 /nobreak >nul

echo 4/7 Starting Telegram Command Center...
start "telegram_command_center" /MIN .venv\Scripts\python.exe telegram_command_center.py

timeout /t 2 /nobreak >nul

echo 5/7 Starting News Calendar Monitor...
start "news_calendar_monitor" /MIN .venv\Scripts\python.exe news_calendar_monitor.py

timeout /t 2 /nobreak >nul

echo 6/7 Starting News Reminder Engine...
start "news_reminder_engine" /MIN .venv\Scripts\python.exe news_reminder_engine.py

timeout /t 2 /nobreak >nul

echo 7/7 Starting Watchdog Monitor...
start "watchdog_monitor" /MIN .venv\Scripts\python.exe watchdog_monitor.py --interval 60

timeout /t 4 /nobreak >nul

echo.
echo ╔═══════════════════════════════════════════════════╗
echo ║  ✅ All 7 monitors started!                      ║
echo ║  Check logs\ folder for output                   ║
echo ║  Use Task Manager to verify processes            ║
echo ╚═══════════════════════════════════════════════════╝
echo.
echo Press any key to exit...
pause >nul
