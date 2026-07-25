param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
Push-Location $ProjectRoot
try {
    python -m src.opportunity_intelligence_engine_v2
    if ($LASTEXITCODE -ne 0) {
        throw "Opportunity Intelligence Engine v2 failed."
    }
}
finally {
    Pop-Location
}