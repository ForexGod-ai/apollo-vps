# Refresh data/upcoming_news.json for /news (Windows VPS — python3 is often missing)
Set-Location $PSScriptRoot\..

$py = $null
foreach ($cmd in @('py', 'python', 'python3')) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $py = $cmd
        break
    }
}
if (-not $py) {
    Write-Error "Python not found. Install Python 3 and ensure py or python is on PATH."
    exit 1
}

Write-Host "Using: $py"
Write-Host "news_fetcher -> data/upcoming_news.json (ForexFactory High HTML / mirror)"
& $py news_fetcher.py --days 14 --debug
exit $LASTEXITCODE
