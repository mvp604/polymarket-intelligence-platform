$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent `
    $MyInvocation.MyCommand.Path

Set-Location $projectRoot

python `
    .\src\classification_v2_league_cli.py `
    @args

exit $LASTEXITCODE
