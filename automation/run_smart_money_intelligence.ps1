param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
Push-Location $ProjectRoot
try {
    python -m src.smart_money_intelligence_engine
    if ($LASTEXITCODE -ne 0) {
        throw "Smart Money Intelligence Engine failed."
    }
}
finally {
    Pop-Location
}