# ============================================================
# KILL ALL MONITORS — Glitch in Matrix
# Opreste toate procesele Python (monitors + daemons)
# ============================================================

Write-Host "🔴 Stopping all Python monitors..." -ForegroundColor Red

# Kill toate procesele Python
taskkill /F /IM python.exe 2>$null

Start-Sleep -Seconds 2

# Verifica daca s-au oprit
$remaining = Get-Process python -ErrorAction SilentlyContinue
if ($remaining) {
    Write-Host "⚠️  Still running: $($remaining.Count) process(es). Force killing..." -ForegroundColor Yellow
    $remaining | ForEach-Object { Stop-Process -Id $_.Id -Force }
} else {
    Write-Host "✅ All Python processes stopped." -ForegroundColor Green
}

# Sterge lock files stale
$dir = "C:\Users\Administrator\Desktop\Glitch in Matrix\trading-ai-agent apollo"
Remove-Item "$dir\*.lock" -ErrorAction SilentlyContinue
Write-Host "🧹 Lock files cleared." -ForegroundColor Cyan

Write-Host ""
Write-Host "💡 To restart everything, run:" -ForegroundColor Yellow
Write-Host "   Start-Process python -ArgumentList 'watchdog_monitor.py --interval 60' -WorkingDirectory '$dir' -RedirectStandardOutput '$dir\watchdog.log' -RedirectStandardError '$dir\watchdog_err.log' -WindowStyle Hidden" -ForegroundColor White
Write-Host ""
Write-Host "Done." -ForegroundColor Green
