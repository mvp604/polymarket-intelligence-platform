$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host ("=" * 100)
Write-Host "AUTOMATED BUY FAILURE ANALYSIS"
Write-Host ("=" * 100)

python `
    .\src\institutional_buy_failure_analysis_engine.py `
    --latest-run-only `
    --near-buy-max-failed 2 `
    --near-buy-max-gap-pct 10 `
    --top-limit 25

if ($LASTEXITCODE -ne 0) {
    throw "BUY Failure Analysis failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Analysis complete."
Write-Host "Latest report: .\reports\buy_failure_analysis\latest.txt"
Write-Host ("=" * 100)
