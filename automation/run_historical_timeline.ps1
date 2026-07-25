param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
Push-Location $ProjectRoot
try {
    python -m src.historical_timeline_engine
    if ($LASTEXITCODE -ne 0) {
        throw "Historical Timeline Engine failed."
    }
}
finally {
    Pop-Location
}