$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$pythonFile = Join-Path `
    $projectRoot `
    "src\threshold_optimizer.py"

if (-not (Test-Path $pythonFile -PathType Leaf)) {
    throw "Engine not found: $pythonFile"
}

python $pythonFile

if ($LASTEXITCODE -ne 0) {
    throw "Threshold Optimizer failed with exit code $LASTEXITCODE"
}

$reportPath = Join-Path `
    $projectRoot `
    "reports\threshold_optimizer\latest.html"

if (Test-Path $reportPath) {
    Start-Process $reportPath
}

Write-Host ""
Write-Host "Threshold Optimizer complete."
Write-Host "Latest report:"
Write-Host $reportPath

