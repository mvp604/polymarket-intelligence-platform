$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

python `
    .\src\market_intelligence_engine.py `
    @args

exit $LASTEXITCODE

