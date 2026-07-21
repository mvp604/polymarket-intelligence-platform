$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

python .\src\elite_wallet_intelligence_database.py @args
exit $LASTEXITCODE

