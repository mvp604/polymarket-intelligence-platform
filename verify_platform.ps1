$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ReportDirectory = Join-Path $ProjectRoot "reports\platform_verification"
$ReportPath = Join-Path $ReportDirectory "platform_verification_$Timestamp.txt"
$LatestReportPath = Join-Path $ReportDirectory "latest.txt"

New-Item -ItemType Directory -Force -Path $ReportDirectory | Out-Null
Set-Location $ProjectRoot

$Results = New-Object System.Collections.Generic.List[string]

function Add-Line {
    param([string]$Text = "")

    Write-Host $Text
    $Results.Add($Text)
}

function Add-Section {
    param([string]$Title)

    Add-Line ""
    Add-Line ("=" * 100)
    Add-Line $Title
    Add-Line ("=" * 100)
}

function Add-Result {
    param(
        [string]$Status,
        [string]$Message
    )

    $Symbol = switch ($Status) {
        "PASS" { "[PASS]" }
        "WARN" { "[WARN]" }
        "FAIL" { "[FAIL]" }
        default { "[INFO]" }
    }

    Add-Line "$Symbol $Message"
}

function Test-CommandExists {
    param([string]$Command)

    return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

Add-Section "POLYMARKET INTELLIGENCE PLATFORM — SAFE VERIFICATION"

Add-Line "Generated:     $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Add-Line "Project root:  $ProjectRoot"
Add-Line "Computer:      $env:COMPUTERNAME"
Add-Line "PowerShell:    $($PSVersionTable.PSVersion)"
Add-Line ""
Add-Line "This verifier does not modify the database or source code."

# =============================================================================
# PROJECT STRUCTURE
# =============================================================================

Add-Section "1. PROJECT STRUCTURE"

$RequiredDirectories = @(
    "src",
    "database"
)

$RecommendedDirectories = @(
    "tests",
    "tools",
    "reports"
)

foreach ($Directory in $RequiredDirectories) {
    $FullPath = Join-Path $ProjectRoot $Directory

    if (Test-Path $FullPath) {
        Add-Result "PASS" "Required directory exists: $Directory"
    }
    else {
        Add-Result "FAIL" "Required directory is missing: $Directory"
    }
}

foreach ($Directory in $RecommendedDirectories) {
    $FullPath = Join-Path $ProjectRoot $Directory

    if (Test-Path $FullPath) {
        Add-Result "PASS" "Recommended directory exists: $Directory"
    }
    else {
        Add-Result "WARN" "Recommended directory is missing: $Directory"
    }
}

$PythonFiles = @(
    Get-ChildItem `
        -Path $ProjectRoot `
        -Filter "*.py" `
        -File `
        -Recurse `
        -ErrorAction SilentlyContinue |
    Where-Object {
        $_.FullName -notmatch "\\\.venv\\" -and
        $_.FullName -notmatch "\\venv\\" -and
        $_.FullName -notmatch "\\__pycache__\\" -and
        $_.FullName -notmatch "\\reports\\" -and
        $_.FullName -notmatch "\\logs\\"
    }
)

$PowerShellFiles = @(
    Get-ChildItem `
        -Path $ProjectRoot `
        -Filter "*.ps1" `
        -File `
        -Recurse `
        -ErrorAction SilentlyContinue |
    Where-Object {
        $_.FullName -notmatch "\\\.venv\\" -and
        $_.FullName -notmatch "\\reports\\" -and
        $_.FullName -notmatch "\\logs\\"
    }
)

$JsonFiles = @(
    Get-ChildItem `
        -Path $ProjectRoot `
        -Filter "*.json" `
        -File `
        -Recurse `
        -ErrorAction SilentlyContinue |
    Where-Object {
        $_.FullName -notmatch "\\\.venv\\" -and
        $_.FullName -notmatch "\\reports\\" -and
        $_.FullName -notmatch "\\logs\\"
    }
)

Add-Line ""
Add-Line "Python files:      $($PythonFiles.Count)"
Add-Line "PowerShell files:  $($PowerShellFiles.Count)"
Add-Line "JSON files:        $($JsonFiles.Count)"

# =============================================================================
# PYTHON
# =============================================================================

Add-Section "2. PYTHON ENVIRONMENT"

$PythonCommand = $null

if (Test-Path ".\.venv\Scripts\python.exe") {
    $PythonCommand = ".\.venv\Scripts\python.exe"
    Add-Result "PASS" "Project virtual-environment Python found."
}
elseif (Test-CommandExists "python") {
    $PythonCommand = "python"
    Add-Result "WARN" "Using system Python because .venv Python was not found."
}
elseif (Test-CommandExists "py") {
    $PythonCommand = "py"
    Add-Result "WARN" "Using the Windows Python launcher."
}
else {
    Add-Result "FAIL" "Python could not be found."
}

if ($PythonCommand) {
    try {
        $PythonVersion = & $PythonCommand --version 2>&1
        Add-Line "Python version: $PythonVersion"
    }
    catch {
        Add-Result "FAIL" "Python version command failed: $($_.Exception.Message)"
    }
}

# =============================================================================
# PYTHON SYNTAX
# =============================================================================

Add-Section "3. PYTHON SYNTAX VALIDATION"

$SyntaxFailures = 0
$EmptyPythonFiles = 0

foreach ($File in $PythonFiles) {
    if ($File.Length -eq 0) {
        $EmptyPythonFiles++
        Add-Result "WARN" "Empty Python file: $($File.FullName)"
    }
}

if ($PythonCommand) {
    foreach ($File in $PythonFiles) {
        if ($File.Length -eq 0) {
            continue
        }

        $Output = & $PythonCommand `
            -m py_compile `
            $File.FullName `
            2>&1

        if ($LASTEXITCODE -ne 0) {
            $SyntaxFailures++
            Add-Result "FAIL" "Syntax failure: $($File.FullName)"
            Add-Line ($Output | Out-String)
        }
    }

    if ($SyntaxFailures -eq 0) {
        Add-Result "PASS" "All non-empty Python files compiled successfully."
    }
    else {
        Add-Result "FAIL" "$SyntaxFailures Python file(s) failed compilation."
    }
}

Add-Line "Empty Python files: $EmptyPythonFiles"

# =============================================================================
# DATABASE
# =============================================================================

Add-Section "4. SQLITE DATABASE"

$DatabasePath = Join-Path $ProjectRoot "database\polymarket.db"

if (-not (Test-Path $DatabasePath)) {
    Add-Result "FAIL" "Database does not exist: $DatabasePath"
}
elseif (-not $PythonCommand) {
    Add-Result "FAIL" "Python is required to inspect SQLite."
}
else {
    Add-Result "PASS" "Database exists."

    $DatabaseSize = (Get-Item $DatabasePath).Length
    Add-Line "Database size: $DatabaseSize bytes"

    $DatabaseAuditCode = @'
import json
import sqlite3
import sys
from pathlib import Path

database_path = Path(sys.argv[1])

result = {
    "database": str(database_path),
    "quick_check": [],
    "foreign_key_violations": [],
    "journal_mode": None,
    "table_count": 0,
    "index_count": 0,
    "empty_table_count": 0,
    "largest_tables": [],
}

connection = sqlite3.connect(
    f"file:{database_path}?mode=ro",
    uri=True,
    timeout=30,
)

try:
    result["quick_check"] = [
        row[0]
        for row in connection.execute(
            "PRAGMA quick_check"
        ).fetchall()
    ]

    result["foreign_key_violations"] = [
        list(row)
        for row in connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
    ]

    result["journal_mode"] = connection.execute(
        "PRAGMA journal_mode"
    ).fetchone()[0]

    tables = [
        row[0]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    ]

    result["table_count"] = len(tables)

    result["index_count"] = connection.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'index'
          AND name NOT LIKE 'sqlite_%'
        """
    ).fetchone()[0]

    row_counts = []

    for table_name in tables:
        escaped = table_name.replace('"', '""')

        count = connection.execute(
            f'SELECT COUNT(*) FROM "{escaped}"'
        ).fetchone()[0]

        row_counts.append(
            {
                "table": table_name,
                "rows": count,
            }
        )

    result["empty_table_count"] = sum(
        item["rows"] == 0
        for item in row_counts
    )

    result["largest_tables"] = sorted(
        row_counts,
        key=lambda item: item["rows"],
        reverse=True,
    )[:30]

finally:
    connection.close()

print(json.dumps(result, indent=2))
'@

    $TemporaryDatabaseAudit = Join-Path `
        $env:TEMP `
        "polymarket_database_audit_$Timestamp.py"

    Set-Content `
        -Path $TemporaryDatabaseAudit `
        -Value $DatabaseAuditCode `
        -Encoding UTF8

    try {
        $DatabaseOutput = & $PythonCommand `
            $TemporaryDatabaseAudit `
            $DatabasePath `
            2>&1

        Add-Line ($DatabaseOutput | Out-String)

        if ($LASTEXITCODE -eq 0) {
            Add-Result "PASS" "SQLite inspection completed."
        }
        else {
            Add-Result "FAIL" "SQLite inspection failed."
        }
    }
    catch {
        Add-Result "FAIL" "SQLite inspection error: $($_.Exception.Message)"
    }
    finally {
        Remove-Item `
            $TemporaryDatabaseAudit `
            -Force `
            -ErrorAction SilentlyContinue
    }
}

# =============================================================================
# GIT AND SECURITY
# =============================================================================

Add-Section "5. GIT AND SECURITY"

$GitIgnorePath = Join-Path $ProjectRoot ".gitignore"

if (-not (Test-Path $GitIgnorePath)) {
    Add-Result "FAIL" ".gitignore is missing."
}
else {
    Add-Result "PASS" ".gitignore exists."

    $GitIgnoreContent = Get-Content `
        $GitIgnorePath `
        -Raw `
        -ErrorAction SilentlyContinue

    $RequiredIgnoreRules = @(
        ".env",
        ".venv/",
        "__pycache__/",
        "*.pyc",
        "database/*.db",
        "logs/",
        "reports/"
    )

    foreach ($Rule in $RequiredIgnoreRules) {
        if ($GitIgnoreContent -match [regex]::Escape($Rule)) {
            Add-Result "PASS" ".gitignore contains: $Rule"
        }
        else {
            Add-Result "WARN" ".gitignore may be missing: $Rule"
        }
    }
}

if (Test-CommandExists "git") {
    Add-Result "PASS" "Git is installed."

    if (Test-Path (Join-Path $ProjectRoot ".git")) {
        Add-Result "PASS" "The project is a Git repository."

        $TrackedFiles = @(
            git ls-files 2>$null
        )

        $SensitiveTrackedFiles = @(
            $TrackedFiles |
            Where-Object {
                $_ -match "(^|/)\.env$" -or
                $_ -match "\.(db|sqlite|sqlite3)$"
            }
        )

        if ($SensitiveTrackedFiles.Count -gt 0) {
            Add-Result "FAIL" "Sensitive files appear to be tracked by Git."

            foreach ($File in $SensitiveTrackedFiles) {
                Add-Line "Tracked sensitive file: $File"
            }
        }
        else {
            Add-Result "PASS" "No .env or SQLite database files appear to be tracked."
        }

        Add-Line ""
        Add-Line "Git status:"
        Add-Line (git status --short --branch | Out-String)
    }
    else {
        Add-Result "WARN" "The project does not appear to contain a .git folder."
    }
}
else {
    Add-Result "WARN" "Git was not found."
}

# =============================================================================
# BACKUPS AND DUPLICATES
# =============================================================================

Add-Section "6. BACKUP AND LEGACY FILES"

$BackupFiles = @(
    Get-ChildItem `
        -Path (Join-Path $ProjectRoot "src") `
        -File `
        -Recurse `
        -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match "backup|baseline|legacy|before_|\.old|\.bak"
    }
)

Add-Line "Backup or legacy files detected: $($BackupFiles.Count)"

foreach ($File in $BackupFiles | Select-Object -First 100) {
    Add-Line $File.FullName
}

if ($BackupFiles.Count -gt 10) {
    Add-Result "WARN" "Many backup or legacy files exist inside active source paths."
}
else {
    Add-Result "PASS" "Backup-file volume is limited."
}

# =============================================================================
# PLATFORM VERSION
# =============================================================================

Add-Section "7. PLATFORM VERSION"

$PlatformVersionPath = Join-Path `
    $ProjectRoot `
    "src\platform_version.py"

if (Test-Path $PlatformVersionPath) {
    Add-Result "PASS" "Canonical platform-version file exists."
    Add-Line (Get-Content $PlatformVersionPath -Raw)
}
else {
    Add-Result "WARN" "src\platform_version.py was not found."
}

# =============================================================================
# TEST INVENTORY
# =============================================================================

Add-Section "8. TEST INVENTORY"

$TestFiles = @(
    $PythonFiles |
    Where-Object {
        $_.Name -match "test" -or
        $_.FullName -match "\\tests\\"
    }
)

Add-Line "Test-related Python files: $($TestFiles.Count)"

foreach ($File in $TestFiles | Select-Object -First 100) {
    Add-Line $File.FullName
}

if ($TestFiles.Count -eq 0) {
    Add-Result "WARN" "No automated Python tests were detected."
}
else {
    Add-Result "PASS" "Automated test files were detected."
}

# =============================================================================
# FINAL SUMMARY
# =============================================================================

Add-Section "9. FINAL SUMMARY"

$FailCount = @(
    $Results |
    Where-Object {
        $_ -like "[FAIL]*"
    }
).Count

$WarningCount = @(
    $Results |
    Where-Object {
        $_ -like "[WARN]*"
    }
).Count

$PassCount = @(
    $Results |
    Where-Object {
        $_ -like "[PASS]*"
    }
).Count

Add-Line "Pass results:     $PassCount"
Add-Line "Warnings:         $WarningCount"
Add-Line "Failures:         $FailCount"

if ($FailCount -gt 0) {
    Add-Line ""
    Add-Line "OVERALL STATUS: FAIL"
    Add-Line "Blocking issues must be reviewed."
}
elseif ($WarningCount -gt 0) {
    Add-Line ""
    Add-Line "OVERALL STATUS: WARNING"
    Add-Line "No confirmed blocking failure, but improvements are required."
}
else {
    Add-Line ""
    Add-Line "OVERALL STATUS: PASS"
    Add-Line "No issues were detected by this verification pass."
}

$Results | Set-Content `
    -Path $ReportPath `
    -Encoding UTF8

$Results | Set-Content `
    -Path $LatestReportPath `
    -Encoding UTF8

Add-Line ""
Add-Line "Report created:"
Add-Line $ReportPath
Add-Line ""
Add-Line "UPLOAD THIS FILE BACK TO CHATGPT:"
Add-Line $LatestReportPath