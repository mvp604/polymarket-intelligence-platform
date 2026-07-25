param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
Push-Location $ProjectRoot
try {
    python -m src.outcome_intelligence_engine
    if ($LASTEXITCODE -ne 0) {
        throw "Outcome Intelligence Engine failed."
    }
}
finally {
    Pop-Location
}