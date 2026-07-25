$ErrorActionPreference = "Stop"

Write-Host "`n=== Snapshot Test Setup ===" -ForegroundColor Cyan

# Confirm we are in the project root
if (-not (Test-Path ".\pytest.ini")) {
    throw "pytest.ini was not found. Run this from the Polymarket Intelligence Platform root folder."
}

if (-not (Test-Path ".\src\snapshots")) {
    throw "src\snapshots was not found. You may be in the wrong folder."
}

# Back up pytest.ini
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupPath = ".\backups\pytest.ini_$timestamp.bak"

New-Item -ItemType Directory -Path ".\backups" -Force | Out-Null
Copy-Item ".\pytest.ini" $backupPath -Force

Write-Host "Backup created: $backupPath" -ForegroundColor Green

# Read pytest.ini
$content = Get-Content ".\pytest.ini" -Raw

# Add pythonpath only if it is missing
if ($content -notmatch "(?m)^\s*pythonpath\s*=") {
    $content = $content -replace `
        "(?m)^(testpaths\s*=\s*\r?\n(?:\s+.+\r?\n)+)", `
        "`$1pythonpath =`r`n    .`r`n"

    Set-Content ".\pytest.ini" $content -Encoding UTF8

    Write-Host "Added pythonpath = . to pytest.ini" -ForegroundColor Green
}
else {
    Write-Host "pytest.ini already contains pythonpath configuration." -ForegroundColor Yellow
}

# Remove accidental duplicate from project root
$duplicateTest = ".\test_storage_roundtrip.py"

if (Test-Path $duplicateTest) {
    Remove-Item $duplicateTest -Force
    Write-Host "Removed duplicate root test: $duplicateTest" -ForegroundColor Green
}
else {
    Write-Host "No duplicate root-level test was found." -ForegroundColor Yellow
}

# Confirm correct test exists
$correctTest = ".\tests\snapshots\test_storage_roundtrip.py"

if (-not (Test-Path $correctTest)) {
    throw "The correct test file does not exist: $correctTest"
}

Write-Host "Correct test file confirmed." -ForegroundColor Green

# Show updated pytest configuration
Write-Host "`n=== Updated pytest.ini ===" -ForegroundColor Cyan
Get-Content ".\pytest.ini"

# Run the test
Write-Host "`n=== Running Snapshot Round-Trip Test ===" -ForegroundColor Cyan
python -m pytest $correctTest -v

if ($LASTEXITCODE -ne 0) {
    throw "The snapshot round-trip test failed with exit code $LASTEXITCODE."
}

Write-Host "`nSnapshot round-trip test passed." -ForegroundColor Green