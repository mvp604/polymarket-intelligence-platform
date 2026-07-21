$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

$backup = Join-Path `
    $root `
    "backups\platform_versioned_registry_$stamp"

if (-not (Test-Path $root)) {
    throw "Project root not found: $root"
}

$targets = @(
    "src\platform_version.py",
    "src\classification_v2\registry\metadata.py",
    "src\classification_v2\registry\loader.py",
    "src\classification_v2\registry\__init__.py",
    "src\classification_v2\registry_version_tests.py",
    "src\classification_v2_registry_cli.py",
    "CHANGELOG.md"
)

New-Item `
    -ItemType Directory `
    -Path $backup `
    -Force | Out-Null

foreach ($target in $targets) {
    $source = Join-Path $root $target

    if (Test-Path $source) {
        $destination = Join-Path $backup $target

        New-Item `
            -ItemType Directory `
            -Path (Split-Path -Parent $destination) `
            -Force | Out-Null

        Copy-Item `
            $source `
            $destination `
            -Recurse `
            -Force
    }
}

function Restore-Previous {
    Write-Host ""
    Write-Host "Restoring previous files..."

    foreach ($target in $targets) {
        $current = Join-Path $root $target
        $saved = Join-Path $backup $target

        if (Test-Path $current) {
            Remove-Item `
                $current `
                -Recurse `
                -Force
        }

        if (Test-Path $saved) {
            New-Item `
                -ItemType Directory `
                -Path (Split-Path -Parent $current) `
                -Force | Out-Null

            Copy-Item `
                $saved `
                $current `
                -Recurse `
                -Force
        }
    }

    Write-Host "Previous files restored."
}

Write-Host ""
Write-Host "Installing Versioned Registry Foundation..."

$platformVersionPath = Join-Path `
    $root `
    "src\platform_version.py"

@'
from __future__ import annotations


PLATFORM_NAME = "Polymarket Intelligence Platform"
PLATFORM_VERSION = "0.3.0"
CLASSIFICATION_ENGINE_VERSION = "2.3.0"


def version_info() -> dict[str, str]:
    return {
        "platform_name": PLATFORM_NAME,
        "platform_version": PLATFORM_VERSION,
        "classification_engine_version": (
            CLASSIFICATION_ENGINE_VERSION
        ),
    }
'@ | Set-Content `
    -Path $platformVersionPath `
    -Encoding UTF8

$metadataPath = Join-Path `
    $root `
    "src\classification_v2\registry\metadata.py"

@'
from __future__ import annotations


REGISTRY_NAME = "classification_v2_registry"
REGISTRY_VERSION = "1.0.0"
REGISTRY_SCHEMA_VERSION = "1"


def registry_metadata() -> dict[str, str]:
    return {
        "registry_name": REGISTRY_NAME,
        "registry_version": REGISTRY_VERSION,
        "registry_schema_version": (
            REGISTRY_SCHEMA_VERSION
        ),
    }
'@ | Set-Content `
    -Path $metadataPath `
    -Encoding UTF8

$loaderPath = Join-Path `
    $root `
    "src\classification_v2\registry\loader.py"

@'
from __future__ import annotations

from collections import defaultdict

from .leagues import RULES as LEAGUE_RULES
from .metadata import registry_metadata
from .models import RegistryRule
from .sports import RULES as SPORT_RULES


_ALL_RULES: tuple[RegistryRule, ...] = (
    *SPORT_RULES,
    *LEAGUE_RULES,
)


def validate_registry(
    rules: tuple[RegistryRule, ...],
) -> None:
    seen_ids: set[str] = set()

    for rule in rules:
        rule.validate()

        if rule.rule_id in seen_ids:
            raise ValueError(
                f"Duplicate rule_id: {rule.rule_id}"
            )

        seen_ids.add(rule.rule_id)


validate_registry(_ALL_RULES)


def get_registry() -> tuple[RegistryRule, ...]:
    return _ALL_RULES


def get_rules(
    rule_type: str,
) -> tuple[RegistryRule, ...]:
    normalized = rule_type.strip().lower()

    return tuple(
        rule
        for rule in _ALL_RULES
        if rule.rule_type.lower() == normalized
    )


def registry_summary() -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)

    for rule in _ALL_RULES:
        counts[rule.rule_type] += 1

    counts["total"] = len(_ALL_RULES)

    return dict(counts)


def registry_manifest() -> dict[str, object]:
    summary = registry_summary()

    return {
        **registry_metadata(),
        "rule_counts": summary,
        "rule_types": sorted(
            rule_type
            for rule_type in summary
            if rule_type != "total"
        ),
    }
'@ | Set-Content `
    -Path $loaderPath `
    -Encoding UTF8

$initPath = Join-Path `
    $root `
    "src\classification_v2\registry\__init__.py"

@'
from .loader import (
    get_registry,
    get_rules,
    registry_manifest,
    registry_summary,
)
from .metadata import registry_metadata
from .models import RegistryRule


__all__ = [
    "RegistryRule",
    "get_registry",
    "get_rules",
    "registry_manifest",
    "registry_metadata",
    "registry_summary",
]
'@ | Set-Content `
    -Path $initPath `
    -Encoding UTF8

$testsPath = Join-Path `
    $root `
    "src\classification_v2\registry_version_tests.py"

@'
from __future__ import annotations

from platform_version import version_info

from .registry.loader import registry_manifest


def assert_equal(
    actual,
    expected,
    message: str,
) -> None:
    if actual != expected:
        raise AssertionError(
            f"{message}: expected {expected!r}, "
            f"got {actual!r}"
        )


def assert_true(
    value: bool,
    message: str,
) -> None:
    if not value:
        raise AssertionError(message)


def run_tests() -> None:
    platform = version_info()
    manifest = registry_manifest()

    assert_equal(
        platform["platform_version"],
        "0.3.0",
        "Platform version",
    )

    assert_equal(
        platform["classification_engine_version"],
        "2.3.0",
        "Classification Engine version",
    )

    assert_equal(
        manifest["registry_version"],
        "1.0.0",
        "Registry version",
    )

    assert_equal(
        manifest["registry_schema_version"],
        "1",
        "Registry schema version",
    )

    assert_true(
        manifest["rule_counts"]["total"] >= 34,
        "Existing registry rules were not preserved",
    )

    assert_true(
        "league" in manifest["rule_types"],
        "League rule type missing",
    )

    assert_true(
        "sport" in manifest["rule_types"],
        "Sport rule type missing",
    )

    print(
        "Versioned registry foundation tests "
        "passed: 7"
    )


if __name__ == "__main__":
    run_tests()
'@ | Set-Content `
    -Path $testsPath `
    -Encoding UTF8

$cliPath = Join-Path `
    $root `
    "src\classification_v2_registry_cli.py"

@'
from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from classification_v2.matching_engine import (
    RegistryMatcher,
)
from classification_v2.registry.loader import (
    registry_manifest,
    registry_summary,
)
from classification_v2.registry_tests import (
    run_tests as run_registry_tests,
)
from classification_v2.registry_version_tests import (
    run_tests as run_version_tests,
)
from platform_version import version_info


MODULE_VERSION = "2.3.0-versioned-registry"


def print_json(
    result: dict[str, object],
) -> None:
    result["module_version"] = MODULE_VERSION

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Classification v2 Shared Registry "
            "and Matching Engine"
        )
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
    )

    parser.add_argument(
        "--version-test",
        action="store_true",
    )

    parser.add_argument(
        "--summary",
        action="store_true",
    )

    parser.add_argument(
        "--manifest",
        action="store_true",
    )

    parser.add_argument(
        "--version",
        action="store_true",
    )

    parser.add_argument("--type")
    parser.add_argument("--title")

    args = parser.parse_args()

    if args.self_test:
        run_registry_tests()
        run_version_tests()
        return

    if args.version_test:
        run_version_tests()
        return

    if args.summary:
        print_json(
            registry_summary()
        )
        return

    if args.manifest:
        print_json(
            registry_manifest()
        )
        return

    if args.version:
        print_json(
            version_info()
        )
        return

    if not args.type or not args.title:
        parser.error(
            "--type and --title are required "
            "unless a control flag is used"
        )

    matcher = RegistryMatcher()

    result = asdict(
        matcher.match(
            args.title,
            args.type,
        )
    )

    print_json(result)


if __name__ == "__main__":
    main()
'@ | Set-Content `
    -Path $cliPath `
    -Encoding UTF8

$changelogPath = Join-Path `
    $root `
    "CHANGELOG.md"

$oldChangelog = ""

if (Test-Path $changelogPath) {
    $oldChangelog = Get-Content `
        $changelogPath `
        -Raw
}

$changelogEntry = @'
# Changelog

## [0.3.0] - 2026-07-20

### Added

- Platform semantic version source.
- Classification Engine version source.
- Registry version and schema metadata.
- Registry manifest output.
- Version validation tests.

### Preserved

- Existing sport rules.
- Existing league rules.
- Existing generic matching behavior.
- No database writes.
- No orchestrator activation.

'@

if (
    $oldChangelog -and
    -not $oldChangelog.Contains("## [0.3.0]")
) {
    $changelogEntry = `
        $changelogEntry +
        "`r`n" +
        $oldChangelog
}

$changelogEntry | Set-Content `
    -Path $changelogPath `
    -Encoding UTF8

$compileFiles = @(
    $platformVersionPath,
    $metadataPath,
    $loaderPath,
    $initPath,
    $testsPath,
    $cliPath
)

Write-Host ""
Write-Host "Running compile checks..."

python -m py_compile $compileFiles

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "Compile checks failed. Previous files restored."
}

Write-Host "Compile checks passed."

$runnerPath = Join-Path `
    $root `
    "run_classification_v2_registry.ps1"

if (-not (Test-Path $runnerPath)) {
    Restore-Previous

    throw "Registry runner not found: $runnerPath"
}

Write-Host ""
Write-Host "Running registry and version tests..."

& $runnerPath --self-test

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "Tests failed. Previous files restored."
}

Write-Host ""
Write-Host "Running platform version output..."

& $runnerPath --version

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "Version output failed. Previous files restored."
}

Write-Host ""
Write-Host "Running registry manifest..."

& $runnerPath --manifest

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "Registry manifest failed. Previous files restored."
}

Write-Host ""
Write-Host ("=" * 108)
Write-Host "VERSIONED REGISTRY FOUNDATION INSTALLED"
Write-Host ("=" * 108)

Write-Host "Platform version:      0.3.0"
Write-Host "Classification engine: 2.3.0"
Write-Host "Registry version:      1.0.0"
Write-Host "Registry schema:       1"
Write-Host "Backup folder:         $backup"
Write-Host "Compile checks:        PASSED"
Write-Host "Tests:                 PASSED"
Write-Host "Database writes:       NONE"
Write-Host "Orchestrator:          NOT ENABLED"

Write-Host ""
Write-Host "Re-run all tests:"
Write-Host `
    ".\run_classification_v2_registry.ps1 --self-test"

Write-Host ""
Write-Host "Show platform version:"
Write-Host `
    ".\run_classification_v2_registry.ps1 --version"

Write-Host ""
Write-Host "Show registry manifest:"
Write-Host `
    ".\run_classification_v2_registry.ps1 --manifest"

Write-Host ("=" * 108)