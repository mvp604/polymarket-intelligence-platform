$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"
$platformDir = Join-Path $root "platform"
$srcDir = Join-Path $root "src"

New-Item -ItemType Directory -Path $platformDir -Force | Out-Null
New-Item -ItemType Directory -Path $srcDir -Force | Out-Null

$pluginManagerPath = Join-Path $platformDir "plugin_manager.py"
$orchestratorPath = Join-Path $platformDir "orchestrator.py"

$pluginManagerCode = @'
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"


class ManifestError(RuntimeError):
    pass


@dataclass(frozen=True)
class EngineManifest:
    engine_id: str
    name: str
    version: str
    runner: str
    enabled: bool
    required: bool
    stage: str
    order: int
    dependencies: tuple[str, ...]
    latest_report: str
    timeout_seconds: int
    manifest_path: str

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: Path) -> "EngineManifest":
        required_fields = ("id", "name", "runner")
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            raise ManifestError(
                f"{path}: missing required field(s): {', '.join(missing)}"
            )

        dependencies = data.get("dependencies", [])
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) and item.strip() for item in dependencies
        ):
            raise ManifestError(f"{path}: dependencies must be a list of engine IDs")

        return cls(
            engine_id=str(data["id"]).strip(),
            name=str(data["name"]).strip(),
            version=str(data.get("version", "1.0.0")).strip(),
            runner=str(data["runner"]).strip(),
            enabled=bool(data.get("enabled", True)),
            required=bool(data.get("required", False)),
            stage=str(data.get("stage", "analysis")).strip(),
            order=int(data.get("order", 100)),
            dependencies=tuple(item.strip() for item in dependencies),
            latest_report=str(data.get("latest_report", "")).strip(),
            timeout_seconds=int(data.get("timeout_seconds", 900)),
            manifest_path=str(path),
        )


def discover_manifests() -> dict[str, EngineManifest]:
    manifests: dict[str, EngineManifest] = {}

    for path in sorted(SRC_DIR.glob("*.manifest.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ManifestError(f"{path}: invalid JSON: {exc}") from exc

        manifest = EngineManifest.from_dict(raw, path)

        if manifest.engine_id in manifests:
            other = manifests[manifest.engine_id].manifest_path
            raise ManifestError(
                f"Duplicate engine ID '{manifest.engine_id}' in {other} and {path}"
            )

        manifests[manifest.engine_id] = manifest

    return manifests


def validate_manifests(manifests: dict[str, EngineManifest]) -> list[str]:
    errors: list[str] = []

    for engine_id, manifest in manifests.items():
        runner_path = ROOT / manifest.runner
        if not runner_path.exists():
            errors.append(
                f"{engine_id}: runner does not exist: {runner_path}"
            )

        for dependency in manifest.dependencies:
            if dependency not in manifests:
                errors.append(
                    f"{engine_id}: missing dependency manifest: {dependency}"
                )
            elif dependency == engine_id:
                errors.append(f"{engine_id}: engine cannot depend on itself")

    try:
        resolve_execution_order(manifests, include_disabled=True)
    except ManifestError as exc:
        errors.append(str(exc))

    return errors


def resolve_execution_order(
    manifests: dict[str, EngineManifest],
    include_disabled: bool = False,
) -> list[EngineManifest]:
    selected = {
        engine_id: manifest
        for engine_id, manifest in manifests.items()
        if include_disabled or manifest.enabled
    }

    temporary: set[str] = set()
    permanent: set[str] = set()
    result: list[EngineManifest] = []

    def visit(engine_id: str, trail: list[str]) -> None:
        if engine_id in permanent:
            return
        if engine_id in temporary:
            cycle = " -> ".join(trail + [engine_id])
            raise ManifestError(f"Circular dependency detected: {cycle}")

        manifest = selected.get(engine_id)
        if manifest is None:
            return

        temporary.add(engine_id)
        for dependency in sorted(manifest.dependencies):
            if dependency in selected:
                visit(dependency, trail + [engine_id])
        temporary.remove(engine_id)
        permanent.add(engine_id)
        result.append(manifest)

    for engine_id in sorted(
        selected,
        key=lambda item: (selected[item].order, selected[item].name.lower()),
    ):
        visit(engine_id, [])

    return result


def build_pipeline_entries(
    manifests: dict[str, EngineManifest],
) -> list[dict[str, Any]]:
    ordered = resolve_execution_order(manifests)
    return [
        {
            "order": index * 10,
            "id": manifest.engine_id,
            "name": manifest.name,
            "runner": manifest.runner,
            "latest_report": manifest.latest_report,
            "enabled": manifest.enabled,
            "required": manifest.required,
            "timeout_seconds": manifest.timeout_seconds,
            "stage": manifest.stage,
            "version": manifest.version,
            "dependencies": list(manifest.dependencies),
            "manifest_path": manifest.manifest_path,
        }
        for index, manifest in enumerate(ordered, start=1)
    ]


def print_manifest_summary(manifests: dict[str, EngineManifest]) -> None:
    print()
    print("=" * 110)
    print("ENGINE PLUGIN MANIFESTS")
    print("=" * 110)

    if not manifests:
        print("No engine manifests discovered.")
        return

    for manifest in resolve_execution_order(manifests, include_disabled=True):
        dependencies = ", ".join(manifest.dependencies) or "none"
        print(
            f"{manifest.engine_id:<34} "
            f"enabled={str(manifest.enabled):<5} "
            f"required={str(manifest.required):<5} "
            f"stage={manifest.stage}"
        )
        print(f"  runner:       {manifest.runner}")
        print(f"  dependencies: {dependencies}")

'@

Set-Content -Path $pluginManagerPath -Value $pluginManagerCode -Encoding UTF8

$dashboardManifest = @'
{
  "id": "decision_intelligence_dashboard",
  "name": "Decision Intelligence Dashboard",
  "version": "1.0.0",
  "runner": "run_decision_intelligence_dashboard.ps1",
  "enabled": true,
  "required": true,
  "stage": "diagnostics",
  "order": 100,
  "dependencies": [],
  "latest_report": "reports/decision_intelligence_dashboard/latest.html",
  "timeout_seconds": 900
}
'@
$auditManifest = @'
{
  "id": "decision_audit",
  "name": "Decision Audit",
  "version": "1.0.0",
  "runner": "run_decision_audit.ps1",
  "enabled": true,
  "required": true,
  "stage": "diagnostics",
  "order": 200,
  "dependencies": [
    "decision_intelligence_dashboard"
  ],
  "latest_report": "reports/decision_audit/latest.html",
  "timeout_seconds": 900
}
'@
$thresholdManifest = @'
{
  "id": "threshold_optimizer",
  "name": "Threshold Optimizer",
  "version": "1.0.0",
  "runner": "run_threshold_optimizer.ps1",
  "enabled": true,
  "required": false,
  "stage": "optimization",
  "order": 300,
  "dependencies": [
    "decision_audit"
  ],
  "latest_report": "reports/threshold_optimizer/latest.html",
  "timeout_seconds": 900
}
'@

Set-Content -Path (Join-Path $srcDir "decision_intelligence_dashboard.manifest.json") -Value $dashboardManifest -Encoding UTF8
Set-Content -Path (Join-Path $srcDir "decision_audit.manifest.json") -Value $auditManifest -Encoding UTF8
Set-Content -Path (Join-Path $srcDir "threshold_optimizer.manifest.json") -Value $thresholdManifest -Encoding UTF8

python -m py_compile $pluginManagerPath
if ($LASTEXITCODE -ne 0) {
    throw "Plugin manager compile check failed."
}

if (-not (Test-Path $orchestratorPath)) {
    throw "Existing orchestrator not found: $orchestratorPath"
}

$orchestrator = Get-Content -Path $orchestratorPath -Raw

if ($orchestrator -notmatch "from platform\.plugin_manager import") {
    $importMarker = "from typing import Any"
    $replacement = @"
from typing import Any

from platform.plugin_manager import (
    ManifestError,
    build_pipeline_entries,
    discover_manifests,
    print_manifest_summary,
    validate_manifests,
)
"@
    $orchestrator = $orchestrator.Replace($importMarker, $replacement)
}

$oldPipeline = @'
    pipeline = sorted(
        config.get("pipeline", []),
        key=lambda step: int(step.get("order", 9999)),
    )
'@

$newPipeline = @'
    use_plugins = bool(config.get("plugins", {}).get("enabled", True))

    if use_plugins:
        try:
            manifests = discover_manifests()
            manifest_errors = validate_manifests(manifests)
            if manifest_errors:
                raise ManifestError("; ".join(manifest_errors))
            print_manifest_summary(manifests)
            pipeline = build_pipeline_entries(manifests)
        except ManifestError as exc:
            finished_at = iso_now()
            health["status"] = "FAIL"
            health.setdefault("failures", []).append("plugin_validation")
            health["plugin_validation_message"] = str(exc)
            report = write_master_report(
                run_id, health, results, config, started_at, finished_at
            )
            return 3, report
    else:
        pipeline = sorted(
            config.get("pipeline", []),
            key=lambda step: int(step.get("order", 9999)),
        )
'@

if ($orchestrator.Contains($oldPipeline)) {
    $orchestrator = $orchestrator.Replace($oldPipeline, $newPipeline)
} elseif ($orchestrator -notmatch "use_plugins = bool") {
    throw "Could not safely locate the pipeline block in orchestrator.py."
}

Set-Content -Path $orchestratorPath -Value $orchestrator -Encoding UTF8

$configPath = Join-Path $root "config\platform_pipeline.json"
$config = Get-Content -Path $configPath -Raw | ConvertFrom-Json

if (-not $config.plugins) {
    $config | Add-Member -MemberType NoteProperty -Name "plugins" -Value ([PSCustomObject]@{
        enabled = $true
        manifest_pattern = "src/*.manifest.json"
    })
} else {
    $config.plugins.enabled = $true
}

$config | ConvertTo-Json -Depth 12 | Set-Content -Path $configPath -Encoding UTF8

$platformPackage = Join-Path $platformDir "__init__.py"
if (-not (Test-Path $platformPackage)) {
    Set-Content -Path $platformPackage -Value "" -Encoding UTF8
}

python -m py_compile $pluginManagerPath $orchestratorPath
if ($LASTEXITCODE -ne 0) {
    throw "Compile validation failed."
}

Write-Host ""
Write-Host "Running plugin-aware dry run..."
Write-Host ""

Set-Location $root
.\run_platform.ps1 --dry-run --no-open

if ($LASTEXITCODE -ne 0) {
    throw "Plugin-aware dry run failed."
}

Write-Host ""
Write-Host ("=" * 110)
Write-Host "ENGINE PLUGIN SYSTEM INSTALLED"
Write-Host ("=" * 110)
Write-Host "Automatic discovery:        ENABLED"
Write-Host "Dependency validation:      ENABLED"
Write-Host "Circular dependency check:  ENABLED"
Write-Host "Duplicate ID detection:     ENABLED"
Write-Host "Runner validation:          ENABLED"
Write-Host ""
Write-Host "Manifests created:"
Write-Host "src\decision_intelligence_dashboard.manifest.json"
Write-Host "src\decision_audit.manifest.json"
Write-Host "src\threshold_optimizer.manifest.json"
Write-Host ""
Write-Host "Run the plugin-aware platform:"
Write-Host ".\run_platform.ps1"
Write-Host ""
Write-Host "Existing analytical engine code and database were not modified."
Write-Host ("=" * 110)