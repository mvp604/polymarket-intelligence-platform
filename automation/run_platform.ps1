# BEGIN PLATFORM UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
try {
    chcp 65001 | Out-Null
} catch {
}
# END PLATFORM UTF8
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "============================================================"
Write-Host "POLYMARKET PLATFORM - ONE CLICK RUN"
Write-Host "============================================================"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Error "Virtual environment not found at .\.venv\Scripts\python.exe"
    exit 1
}

$Python = ".\.venv\Scripts\python.exe"

& $Python ".\automation\platform_automation.py" @args
exit $LASTEXITCODE
