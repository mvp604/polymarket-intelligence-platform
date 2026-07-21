$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host ""
Write-Host ("=" * 100)
Write-Host "INSTITUTIONAL DECISION INTELLIGENCE DASHBOARD"
Write-Host ("=" * 100)

$pythonFile = Join-Path `
    $projectRoot `
    "src\institutional_decision_intelligence_dashboard.py"

if (-not (Test-Path $pythonFile -PathType Leaf)) {
    throw "Python dashboard file not found: $pythonFile"
}

python `
    $pythonFile `
    --latest-run-only `
    --top-limit 25

if ($LASTEXITCODE -ne 0) {
    throw "Dashboard failed with exit code $LASTEXITCODE"
}

$reportPath = Join-Path `
    $projectRoot `
    "reports\decision_intelligence_dashboard\latest.html"

if (Test-Path $reportPath) {
    Write-Host ""
    Write-Host "Opening latest dashboard..."
    Start-Process $reportPath
}

Write-Host ""
Write-Host "Dashboard complete."
Write-Host "Latest HTML:"
Write-Host $reportPath
Write-Host ("=" * 100)
