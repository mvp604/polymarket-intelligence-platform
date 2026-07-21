$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent `
    $MyInvocation.MyCommand.Path

Set-Location $projectRoot

python `
    .\src\classification_v2_registry_cli.py `
    @args

exit $LASTEXITCODE
