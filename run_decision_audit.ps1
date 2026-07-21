$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$pythonFile = Join-Path `
    $projectRoot `
    "src\institutional_decision_audit_engine.py"

if (-not (Test-Path $pythonFile -PathType Leaf)) {
    throw "Audit engine not found: $pythonFile"
}

python `
    $pythonFile `
    --latest-run-only

if ($LASTEXITCODE -ne 0) {
    throw "Decision audit failed with exit code $LASTEXITCODE"
}

$reportPath = Join-Path `
    $projectRoot `
    "reports\decision_audit\latest.html"

if (Test-Path $reportPath) {
    Start-Process $reportPath
}

Write-Host ""
Write-Host "Decision audit complete."
Write-Host "Latest report:"
Write-Host $reportPath

