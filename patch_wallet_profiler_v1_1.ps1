$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"
$enginePath = Join-Path $root "src\wallet_profiler.py"
$runnerPath = Join-Path $root "run_wallet_profiler.ps1"

if (-not (Test-Path $enginePath)) {
    throw "Wallet Profiler engine not found: $enginePath"
}

if (-not (Test-Path $runnerPath)) {
    throw "Wallet Profiler runner not found: $runnerPath"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupPath = "$enginePath.backup.v1_0.$timestamp"
Copy-Item $enginePath $backupPath -Force

Write-Host ""
Write-Host "Existing Wallet Profiler backed up:"
Write-Host $backupPath

$content = Get-Content -Path $enginePath -Raw

$oldBlock = @'
    select_sql = ", ".join(
        column if column in position_columns else f"NULL AS {column}"
        for column in selected
    )
'@

$newBlock = @'
    select_sql = ", ".join(
        (
            f'p."{column}" AS "{column}"'
            if column in position_columns
            else f'NULL AS "{column}"'
        )
        for column in selected
    )
'@

if (-not $content.Contains($oldBlock)) {
    throw @"
Expected SQL column-selection block was not found.

No changes were made.

The current engine was preserved at:
$enginePath

Backup created at:
$backupPath
"@
}

$content = $content.Replace($oldBlock, $newBlock)

$oldWhere = @'
        WHERE wallet IS NOT NULL
          AND TRIM(wallet) <> ''
        ORDER BY wallet, scanned_at
'@

$newWhere = @'
        WHERE p.wallet IS NOT NULL
          AND TRIM(p.wallet) <> ''
        ORDER BY p.wallet, scanned_at
'@

if (-not $content.Contains($oldWhere)) {
    throw @"
Expected SQL WHERE/ORDER block was not found.

No changes were written after the first validation stage.

Backup created at:
$backupPath
"@
}

$content = $content.Replace($oldWhere, $newWhere)

$oldVersion = 'PROFILE_VERSION = 1'
$newVersion = 'PROFILE_VERSION = 2'

if ($content.Contains($oldVersion)) {
    $content = $content.Replace($oldVersion, $newVersion)
}

Set-Content -Path $enginePath -Value $content -Encoding UTF8

Write-Host ""
Write-Host "Wallet Profiler SQL query patched."

Write-Host ""
Write-Host "Running compile check..."
python -m py_compile $enginePath
if ($LASTEXITCODE -ne 0) {
    Copy-Item $backupPath $enginePath -Force
    throw "Compile check failed. Wallet Profiler was restored from backup."
}

Write-Host "Compile check passed."

Write-Host ""
Write-Host "Running self-test..."
& $runnerPath --self-test
if ($LASTEXITCODE -ne 0) {
    Copy-Item $backupPath $enginePath -Force
    throw "Self-test failed. Wallet Profiler was restored from backup."
}

Write-Host ""
Write-Host "Running database-aware dry run..."
& $runnerPath --dry-run --no-open
if ($LASTEXITCODE -ne 0) {
    Copy-Item $backupPath $enginePath -Force
    throw "Dry run failed. Wallet Profiler was restored from backup."
}

Write-Host ""
Write-Host ("=" * 110)
Write-Host "WALLET PROFILER v1.1 PATCH INSTALLED"
Write-Host ("=" * 110)
Write-Host "Engine:          $enginePath"
Write-Host "Backup:          $backupPath"
Write-Host "Compile check:   PASSED"
Write-Host "Self-test:       PASSED"
Write-Host "Dry run:         PASSED"
Write-Host "Database writes: NONE during patch"
Write-Host ""
Write-Host "Run the production profiler:"
Write-Host ".\run_wallet_profiler.ps1"
Write-Host ""
Write-Host "Then run the complete platform:"
Write-Host ".\run_platform.ps1"
Write-Host ("=" * 110)