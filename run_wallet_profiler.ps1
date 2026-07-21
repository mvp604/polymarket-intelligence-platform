$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

python .\src\wallet_profiler.py @args
exit $LASTEXITCODE

