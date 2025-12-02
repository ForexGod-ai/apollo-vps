@echo off
REM ForexGod - Glitch Daily Scanner Launcher
REM Runs at 08:00 AM daily before London session

cd /d "c:\Users\admog\Desktop\siteRazvan\trading-ai-agent"
python daily_scanner.py

REM Keep window open if there's an error (optional)
REM pause
