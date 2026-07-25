param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
Push-Location $ProjectRoot
try {
    python -m src.elite_wallet_intelligence_engine
    if ($LASTEXITCODE -ne 0) {
        throw "Elite Wallet Intelligence Engine failed."
    }
}
finally {
    Pop-Location
}