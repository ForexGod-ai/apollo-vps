@echo off
REM ========================================
REM GLITCH IN MATRIX - Morning Scan Launcher
REM Runs automatically at 09:00 daily
REM ========================================

echo.
echo ========================================
echo   GLITCH IN MATRIX - Morning Scan
echo   Starting scheduler...
echo ========================================
echo.

cd /d "%~dp0"

REM Activate conda environment if needed (uncomment if using conda)
REM call conda activate trading

REM Run the scheduler
python morning_scheduler.py

pause
