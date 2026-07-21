$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"
$enginePath = Join-Path $root "src\market_classifier.py"
$runnerPath = Join-Path $root "run_market_classifier.ps1"

if (-not (Test-Path $enginePath)) {
    throw "Market classifier not found: $enginePath"
}

if (-not (Test-Path $runnerPath)) {
    throw "Market classifier runner not found: $runnerPath"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupPath = "$enginePath.backup.v1_0_0.$timestamp"
Copy-Item $enginePath $backupPath -Force

Write-Host ""
Write-Host "Existing Market Classification Engine backed up:"
Write-Host $backupPath

$content = Get-Content -Path $enginePath -Raw

$oldRule = @'
    ("Resolution Event", [
        r"\bwill .* happen\b", r"\bwill .* occur\b", r"\bby 20\d{2}\b",
        r"\bbefore 20\d{2}\b"
    ]),
'@

$newRule = @'
    ("Resolution Event", [
        r"\bwill .* happen\b",
        r"\bwill .* occur\b",
        r"\bby\s+(?:(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+)?20\d{2}\b",
        r"\bbefore\s+(?:(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+)?20\d{2}\b",
        r"\bby\s+(?:q[1-4]\s+)?20\d{2}\b",
        r"\bbefore\s+(?:q[1-4]\s+)?20\d{2}\b",
        r"\bby\s+\w+\s+\d{1,2},?\s+20\d{2}\b",
        r"\bbefore\s+\w+\s+\d{1,2},?\s+20\d{2}\b"
    ]),
'@

if (-not $content.Contains($oldRule)) {
    throw @"
Expected Resolution Event rule block was not found.

No changes were made.
Backup created at:
$backupPath
"@
}

$content = $content.Replace($oldRule, $newRule)
$content = $content.Replace('CLASSIFIER_VERSION = "1.0.0"', 'CLASSIFIER_VERSION = "1.0.1"')

Set-Content -Path $enginePath -Value $content -Encoding UTF8

Write-Host ""
Write-Host "Deadline classification rules patched."

Write-Host ""
Write-Host "Running compile check..."
python -m py_compile $enginePath
if ($LASTEXITCODE -ne 0) {
    Copy-Item $backupPath $enginePath -Force
    throw "Compile check failed. Original classifier restored."
}
Write-Host "Compile check passed."

Write-Host ""
Write-Host "Running classifier self-test..."
& $runnerPath --self-test
if ($LASTEXITCODE -ne 0) {
    Copy-Item $backupPath $enginePath -Force
    throw "Self-test failed. Original classifier restored."
}

Write-Host ""
Write-Host "Running database-aware dry run..."
& $runnerPath --dry-run --no-open
if ($LASTEXITCODE -ne 0) {
    Copy-Item $backupPath $enginePath -Force
    throw "Dry run failed. Original classifier restored."
}

Write-Host ""
Write-Host ("=" * 110)
Write-Host "MARKET CLASSIFICATION ENGINE v1.0.1 PATCH INSTALLED"
Write-Host ("=" * 110)
Write-Host "Engine:          $enginePath"
Write-Host "Backup:          $backupPath"
Write-Host "Compile check:   PASSED"
Write-Host "Self-test:       PASSED"
Write-Host "Dry run:         PASSED"
Write-Host "Database writes: NONE during patch"
Write-Host ""
Write-Host "Run production classification:"
Write-Host ".\run_market_classifier.ps1"
Write-Host ""
Write-Host "Then refresh wallet intelligence:"
Write-Host ".\run_wallet_profiler.ps1"
Write-Host ""
Write-Host "Then run the complete platform:"
Write-Host ".\run_platform.ps1"
Write-Host ("=" * 110)