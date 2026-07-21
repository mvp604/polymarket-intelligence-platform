$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

python `
    .\platform\orchestrator.py `
    @args

exit $LASTEXITCODE

