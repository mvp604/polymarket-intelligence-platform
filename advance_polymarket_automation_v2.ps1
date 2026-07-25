param(
    [string]$ProjectRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)
    $Encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $Encoding)
}

$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$AutomationDir = Join-Path $ProjectRoot "automation"
$ConfigPath = Join-Path $AutomationDir "platform_automation.json"
$AutomationPath = Join-Path $AutomationDir "platform_automation.py"
$PreflightPath = Join-Path $AutomationDir "preflight_check.py"

foreach ($Required in @($ConfigPath, $AutomationPath)) {
    if (-not (Test-Path $Required)) {
        throw "Required file not found: $Required"
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $AutomationDir "backups\automation_v2_$Timestamp"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

Copy-Item $ConfigPath (Join-Path $BackupDir "platform_automation.json") -Force
Copy-Item $AutomationPath (Join-Path $BackupDir "platform_automation.py") -Force

Write-Host "Backup created: $BackupDir"

# ----------------------------------------------------------------------
# 1. Repair known stale module aliases in platform_automation.json
# ----------------------------------------------------------------------
$Config = Get-Content $ConfigPath -Raw | ConvertFrom-Json

$Aliases = @{
    "src.wallet_discovery_engine" = "src.elite_wallet_discovery_engine"
    "src.wallet_performance"      = "src.wallet_performance_engine"
    "src.resolution_warehouse"    = "src.resolution_warehouse_engine"
}

$Changes = 0

foreach ($Step in $Config.steps) {
    if ($null -ne $Step.module -and $Aliases.ContainsKey([string]$Step.module)) {
        $Old = [string]$Step.module
        $New = [string]$Aliases[$Old]
        $Step.module = $New
        Write-Host "Updated module: $Old -> $New"
        $Changes++
    }
}

$Json = $Config | ConvertTo-Json -Depth 20
Write-Utf8NoBom -Path $ConfigPath -Content $Json

python -c "import json, pathlib; p=pathlib.Path(r'$ConfigPath'); json.loads(p.read_text(encoding='utf-8')); print('CONFIG JSON: OK')"
if ($LASTEXITCODE -ne 0) {
    throw "Updated configuration is invalid."
}

# ----------------------------------------------------------------------
# 2. Fix Python 3.13 UTC deprecation warning
# ----------------------------------------------------------------------
$Automation = Get-Content $AutomationPath -Raw

if ($Automation -match "from datetime import datetime" -and $Automation -notmatch "from datetime import datetime, UTC") {
    $Automation = $Automation.Replace(
        "from datetime import datetime",
        "from datetime import datetime, UTC"
    )
}

$Automation = $Automation.Replace(
    'datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")',
    'datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")'
)

Write-Utf8NoBom -Path $AutomationPath -Content $Automation

python -m py_compile $AutomationPath
if ($LASTEXITCODE -ne 0) {
    throw "platform_automation.py failed compilation. Restore from: $BackupDir"
}

# ----------------------------------------------------------------------
# 3. Create reusable pre-flight validator
# ----------------------------------------------------------------------
$Preflight = @'
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    config_path = project_root / "automation" / "platform_automation.json"
    database_path = project_root / "database" / "polymarket.db"

    errors: list[str] = []
    warnings: list[str] = []

    print("=" * 92)
    print("POLYMARKET PLATFORM PRE-FLIGHT CHECK")
    print("=" * 92)

    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        print(f"Config: OK | {config_path}")
    except Exception as exc:
        errors.append(f"Config load failed: {exc}")
        config = {}

    steps = config.get("steps", [])
    print(f"Configured steps: {len(steps)}")

    seen_names: set[str] = set()

    for index, step in enumerate(steps, start=1):
        name = str(step.get("name", f"step_{index}"))
        module = step.get("module")
        required = bool(step.get("required", True))

        if name in seen_names:
            warnings.append(f"Duplicate step name: {name}")
        seen_names.add(name)

        if not module:
            warnings.append(f"{name}: no module configured")
            continue

        if importlib.util.find_spec(str(module)) is None:
            message = f"{name}: module not found: {module}"
            if required:
                errors.append(message)
            else:
                warnings.append(message)
        else:
            print(f"[OK] {name:<30} {module}")

    if not database_path.exists():
        errors.append(f"Database not found: {database_path}")
    else:
        try:
            with sqlite3.connect(database_path) as connection:
                result = connection.execute("PRAGMA integrity_check").fetchone()
            status = result[0] if result else "unknown"
            print(f"Database integrity: {status}")
            if status != "ok":
                errors.append(f"Database integrity failed: {status}")
        except Exception as exc:
            errors.append(f"Database check failed: {exc}")

    print("-" * 92)

    if warnings:
        print("WARNINGS")
        for item in warnings:
            print(f"  - {item}")

    if errors:
        print("ERRORS")
        for item in errors:
            print(f"  - {item}")
        print("=" * 92)
        print("PRE-FLIGHT STATUS: FAILED")
        return 1

    print("=" * 92)
    print("PRE-FLIGHT STATUS: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@

Write-Utf8NoBom -Path $PreflightPath -Content $Preflight

python -m py_compile $PreflightPath
if ($LASTEXITCODE -ne 0) {
    throw "preflight_check.py failed compilation."
}

Write-Host ""
Write-Host "AUTOMATION V2 FOUNDATION INSTALLED"
Write-Host "Config mappings updated: $Changes"
Write-Host "Pre-flight validator: $PreflightPath"
Write-Host ""
Write-Host "Run next:"
Write-Host "  python -m automation.preflight_check"
Write-Host ""
Write-Host "Then test resolution:"
Write-Host "  .\automation\run_platform.ps1 --only resolution_warehouse"
Write-Host ""
Write-Host "Then run everything:"
Write-Host "  .\automation\run_platform.ps1"
