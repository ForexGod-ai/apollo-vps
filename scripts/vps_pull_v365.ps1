# Glitch in Matrix — VPS pull V36.5 + restart monitors
# Usage (PowerShell on VPS):
#   powershell -ExecutionPolicy Bypass -File scripts\vps_pull_v365.ps1

$ErrorActionPreference = "Stop"

$paths = @(
    "C:\Users\Administrator\Desktop\Glitch in Matrix\trading-ai-agent apollo",
    "C:\matrix"
)

$projectRoot = $null
foreach ($p in $paths) {
    if (Test-Path (Join-Path $p "multi_tf_radar.py")) {
        $projectRoot = $p
        break
    }
}

if (-not $projectRoot) {
    Write-Host "ERROR: Cannot find project root (multi_tf_radar.py)" -ForegroundColor Red
    exit 1
}

Set-Location $projectRoot
Write-Host "Project: $projectRoot" -ForegroundColor Cyan

$branch = "cursor/v36-3-radar-live-sync"
Write-Host "Branch: $branch" -ForegroundColor Cyan

git checkout $branch 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARN: checkout $branch failed — continuing on current branch" -ForegroundColor Yellow
}

Remove-Item "process_telegram_command_center.lock" -Force -ErrorAction SilentlyContinue
git pull origin $branch
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: git pull failed. Remove lock file and retry:" -ForegroundColor Red
    Write-Host "  Remove-Item process_telegram_command_center.lock -Force" -ForegroundColor Yellow
    exit 1
}

$head = git log -1 --oneline
Write-Host "HEAD: $head" -ForegroundColor Green

$check = Select-String -Path "multi_tf_radar.py" -Pattern "V36\.5 ALWAYS-ON" -Quiet
if (-not $check) {
    Write-Host "ERROR: multi_tf_radar.py does not contain V36.5 marker" -ForegroundColor Red
    exit 1
}
Write-Host "OK: V36.5 Always-On H4/H1 detected in multi_tf_radar.py" -ForegroundColor Green

Write-Host ""
Write-Host "Restart monitors (choose one):" -ForegroundColor Yellow
Write-Host "  A) Full stack:  .\start_all_monitors.bat" -ForegroundColor White
Write-Host "  B) Watchdog only (restarts all 9 processes): python watchdog_monitor.py --interval 60" -ForegroundColor White
Write-Host "  C) Radar only:  python multi_tf_radar.py" -ForegroundColor White
Write-Host ""
Write-Host "Expected console lines after restart:" -ForegroundColor Cyan
Write-Host "  [V36.5 SCAN DONE] SYMBOL H4 / H1" -ForegroundColor DarkGray
Write-Host "  [V36.5 P/D BLOCK EXECUTE] (when SHORT in Discount — NOT [RADAR SKIP] for P/D)" -ForegroundColor DarkGray
