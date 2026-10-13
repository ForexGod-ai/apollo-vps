@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
  python scripts\audit_swings_usdcad.py %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
  py -3 scripts\audit_swings_usdcad.py %*
  exit /b %ERRORLEVEL%
)

echo.
echo [ERROR] Python nu este in PATH. Instaleaza Python sau foloseste:
echo   py -3 scripts\audit_swings_usdcad.py --bars 365
echo.
exit /b 1
