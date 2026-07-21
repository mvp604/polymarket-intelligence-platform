$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"

$sourceFile = Join-Path `
    $root `
    "src\confidence.py"

$destinationDirectory = Join-Path `
    $root `
    "src\classification_v2"

$destinationFile = Join-Path `
    $destinationDirectory `
    "confidence.py"

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

$backupDirectory = Join-Path `
    $root `
    "backups\confidence_location_fix_$stamp"

Write-Host ""
Write-Host "Repairing confidence.py location..."
Write-Host ""

if (-not (Test-Path $root)) {
    throw "Project root does not exist: $root"
}

if (-not (Test-Path $destinationDirectory)) {
    throw (
        "classification_v2 directory does not exist: " +
        $destinationDirectory
    )
}

if (-not (Test-Path $sourceFile)) {
    if (Test-Path $destinationFile) {
        Write-Host (
            "confidence.py is already in the correct location:"
        )
        Write-Host $destinationFile
        Write-Host ""
    }
    else {
        throw (
            "confidence.py was not found in either expected location."
        )
    }
}
else {
    New-Item `
        -ItemType Directory `
        -Path $backupDirectory `
        -Force | Out-Null

    if (Test-Path $destinationFile) {
        $existingBackup = Join-Path `
            $backupDirectory `
            "confidence.py.existing_backup"

        Copy-Item `
            $destinationFile `
            $existingBackup `
            -Force

        Write-Host (
            "Backed up existing destination confidence.py."
        )
    }

    $sourceBackup = Join-Path `
        $backupDirectory `
        "confidence.py.source_backup"

    Copy-Item `
        $sourceFile `
        $sourceBackup `
        -Force

    Move-Item `
        $sourceFile `
        $destinationFile `
        -Force

    Write-Host "Moved confidence.py to:"
    Write-Host $destinationFile
    Write-Host ""
}

Write-Host "Running compile check..."

python -m py_compile $destinationFile

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Compile failed. Restoring original source file..."

    $sourceBackup = Join-Path `
        $backupDirectory `
        "confidence.py.source_backup"

    if (Test-Path $sourceBackup) {
        Copy-Item `
            $sourceBackup `
            $sourceFile `
            -Force
    }

    throw "confidence.py compile check failed."
}

Write-Host "Compile check passed."
Write-Host ""
Write-Host "Running confidence calculation test..."

Push-Location $root

try {
    python -c "from src.classification_v2.confidence import calculate_coverage, aggregate_confidence; coverage = calculate_coverage({'league','market_type'}, {'sport','league','market_type'}); result = aggregate_confidence({'league':0.98,'market_type':0.96}, {'sport','league','market_type'}); print('Coverage:', coverage); print('Aggregate:', result); assert coverage == 0.6667; assert result[1] == 0.6667"

    if ($LASTEXITCODE -ne 0) {
        throw "Confidence calculation test failed."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host ("=" * 90)
Write-Host "CONFIDENCE FILE LOCATION REPAIRED"
Write-Host ("=" * 90)
Write-Host "Correct file:"
Write-Host $destinationFile
Write-Host ""
Write-Host "Compile check: PASSED"
Write-Host "Calculation test: PASSED"

if (Test-Path $backupDirectory) {
    Write-Host "Backup folder:"
    Write-Host $backupDirectory
}

Write-Host ("=" * 90)