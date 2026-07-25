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
$RunnerPath = Join-Path $AutomationDir "run_platform.ps1"
$AutomationPath = Join-Path $AutomationDir "platform_automation.py"
$ConfigPath = Join-Path $AutomationDir "platform_automation.json"

foreach ($Path in @($RunnerPath, $AutomationPath, $ConfigPath)) {
    if (-not (Test-Path $Path)) {
        throw "Required file not found: $Path"
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $AutomationDir "backups\hardening_$Timestamp"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

Copy-Item $RunnerPath (Join-Path $BackupDir "run_platform.ps1") -Force
Copy-Item $AutomationPath (Join-Path $BackupDir "platform_automation.py") -Force
Copy-Item $ConfigPath (Join-Path $BackupDir "platform_automation.json") -Force

Write-Host "Backup created: $BackupDir"

# Normalize JSON to UTF-8 without BOM.
$ConfigText = Get-Content $ConfigPath -Raw
Write-Utf8NoBom -Path $ConfigPath -Content $ConfigText

python -c "import json, pathlib; p=pathlib.Path(r'$ConfigPath'); json.loads(p.read_text(encoding='utf-8')); print('CONFIG JSON: OK')"
if ($LASTEXITCODE -ne 0) {
    throw "Configuration validation failed."
}

# Force UTF-8 for every engine launched by the PowerShell runner.
$Runner = Get-Content $RunnerPath -Raw
$Utf8RunnerBlock = @'
# BEGIN AUTOMATION UTF-8 HARDENING
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
try { chcp 65001 | Out-Null } catch {}
# END AUTOMATION UTF-8 HARDENING

'@

if ($Runner -notmatch "BEGIN AUTOMATION UTF-8 HARDENING") {
    Write-Utf8NoBom -Path $RunnerPath -Content ($Utf8RunnerBlock + $Runner)
    Write-Host "UTF-8 environment added to run_platform.ps1"
} else {
    Write-Host "run_platform.ps1 already hardened"
}

# Make the Python controller tolerate BOM files and console encoding problems.
$Automation = Get-Content $AutomationPath -Raw
$Automation = $Automation.Replace('encoding="utf-8"', 'encoding="utf-8-sig"')

$PythonBlock = @'
# BEGIN AUTOMATION CONSOLE HARDENING
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
# END AUTOMATION CONSOLE HARDENING

'@

if ($Automation -notmatch "BEGIN AUTOMATION CONSOLE HARDENING") {
    if ($Automation -match "(?m)^import sys\s*$") {
        $Automation = [regex]::Replace(
            $Automation,
            "(?m)^import sys\s*$",
            "import sys`r`n`r`n$PythonBlock",
            1
        )
    } else {
        $Automation = "import sys`r`n`r`n$PythonBlock" + $Automation
    }
}

Write-Utf8NoBom -Path $AutomationPath -Content $Automation

python -m py_compile $AutomationPath
if ($LASTEXITCODE -ne 0) {
    throw "platform_automation.py failed compilation. Restore from: $BackupDir"
}

Write-Host "platform_automation.py: COMPILE OK"

# Report missing configured modules before the next run.
python -c @"
import importlib.util
import json
from pathlib import Path

config = json.loads(Path(r"$ConfigPath").read_text(encoding="utf-8-sig"))
missing = []

for step in config.get("steps", []):
    module = step.get("module")
    if module and importlib.util.find_spec(module) is None:
        missing.append((step.get("name", module), module, step.get("required", True)))

if missing:
    print("Missing configured modules:")
    for name, module, required in missing:
        print(f"  - {name}: {module} [{'REQUIRED' if required else 'OPTIONAL'}]")
else:
    print("All configured modules are importable.")
"@

Write-Host ""
Write-Host "HARDENING COMPLETE"
Write-Host "Next test:"
Write-Host "  .\automation\run_platform.ps1 --only market_change"
Write-Host ""
Write-Host "Then:"
Write-Host "  .\automation\run_platform.ps1"