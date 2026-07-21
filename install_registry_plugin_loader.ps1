$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

$backup = Join-Path `
    $root `
    "backups\registry_plugin_loader_$stamp"

if (-not (Test-Path $root)) {
    throw "Project root not found: $root"
}

$targets = @(
    "src\platform_version.py",
    "src\classification_v2\registry\metadata.py",
    "src\classification_v2\registry\loader.py",
    "src\classification_v2\registry\__init__.py",
    "src\classification_v2\registry_plugin_tests.py",
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
Write-Host "Installing Plugin-Based Registry Loader..."

$platformVersionPath = Join-Path `
    $root `
    "src\platform_version.py"

@'
from __future__ import annotations


PLATFORM_NAME = "Polymarket Intelligence Platform"
PLATFORM_VERSION = "0.3.1"
CLASSIFICATION_ENGINE_VERSION = "2.4.0"


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

$registryDirectory = Join-Path `
    $root `
    "src\classification_v2\registry"

$metadataPath = Join-Path `
    $registryDirectory `
    "metadata.py"

@'
from __future__ import annotations


REGISTRY_NAME = "classification_v2_registry"
REGISTRY_VERSION = "1.1.0"
REGISTRY_SCHEMA_VERSION = "1"
REGISTRY_LOADER_TYPE = "plugin_discovery"


def registry_metadata() -> dict[str, str]:
    return {
        "registry_name": REGISTRY_NAME,
        "registry_version": REGISTRY_VERSION,
        "registry_schema_version": (
            REGISTRY_SCHEMA_VERSION
        ),
        "registry_loader_type": (
            REGISTRY_LOADER_TYPE
        ),
    }
'@ | Set-Content `
    -Path $metadataPath `
    -Encoding UTF8

$loaderPath = Join-Path `
    $registryDirectory `
    "loader.py"

@'
from __future__ import annotations

import importlib
import pkgutil
from collections import defaultdict
from pathlib import Path
from types import ModuleType

from .metadata import registry_metadata
from .models import RegistryRule


_EXCLUDED_MODULES: frozenset[str] = frozenset(
    {
        "__init__",
        "loader",
        "metadata",
        "models",
    }
)


def discover_plugin_names() -> tuple[str, ...]:
    registry_path = Path(__file__).resolve().parent

    names = []

    for module_info in pkgutil.iter_modules(
        [str(registry_path)]
    ):
        name = module_info.name

        if name in _EXCLUDED_MODULES:
            continue

        if name.startswith("_"):
            continue

        names.append(name)

    return tuple(sorted(names))


def import_plugin(
    plugin_name: str,
) -> ModuleType:
    return importlib.import_module(
        f"{__package__}.{plugin_name}"
    )


def extract_plugin_rules(
    module: ModuleType,
) -> tuple[RegistryRule, ...]:
    if not hasattr(module, "RULES"):
        return ()

    raw_rules = getattr(module, "RULES")

    if not isinstance(raw_rules, (tuple, list)):
        raise TypeError(
            f"{module.__name__}.RULES must be "
            "a tuple or list"
        )

    rules: list[RegistryRule] = []

    for index, rule in enumerate(raw_rules):
        if not isinstance(rule, RegistryRule):
            raise TypeError(
                f"{module.__name__}.RULES[{index}] "
                "is not a RegistryRule"
            )

        rules.append(rule)

    return tuple(rules)


def load_plugins(
) -> tuple[
    tuple[RegistryRule, ...],
    dict[str, int],
]:
    rules: list[RegistryRule] = []
    sources: dict[str, int] = {}

    for plugin_name in discover_plugin_names():
        module = import_plugin(plugin_name)
        plugin_rules = extract_plugin_rules(module)

        if not plugin_rules:
            continue

        sources[plugin_name] = len(plugin_rules)
        rules.extend(plugin_rules)

    return tuple(rules), sources


def validate_registry(
    rules: tuple[RegistryRule, ...],
) -> None:
    seen_ids: dict[str, RegistryRule] = {}

    for rule in rules:
        rule.validate()

        if rule.rule_id in seen_ids:
            previous = seen_ids[rule.rule_id]

            raise ValueError(
                "Duplicate rule_id detected: "
                f"{rule.rule_id}. Values: "
                f"{previous.value!r} and "
                f"{rule.value!r}"
            )

        seen_ids[rule.rule_id] = rule


_ALL_RULES, _PLUGIN_SOURCES = load_plugins()

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


def registry_sources() -> dict[str, int]:
    return dict(_PLUGIN_SOURCES)


def registry_summary() -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)

    for rule in _ALL_RULES:
        counts[rule.rule_type] += 1

    counts["total"] = len(_ALL_RULES)

    return dict(counts)


def registry_manifest() -> dict[str, object]:
    summary = registry_summary()
    sources = registry_sources()

    return {
        **registry_metadata(),
        "rule_counts": summary,
        "rule_types": sorted(
            rule_type
            for rule_type in summary
            if rule_type != "total"
        ),
        "plugin_count": len(sources),
        "plugins": sources,
    }
'@ | Set-Content `
    -Path $loaderPath `
    -Encoding UTF8

$initPath = Join-Path `
    $registryDirectory `
    "__init__.py"

@'
from .loader import (
    discover_plugin_names,
    get_registry,
    get_rules,
    registry_manifest,
    registry_sources,
    registry_summary,
)
from .metadata import registry_metadata
from .models import RegistryRule


__all__ = [
    "RegistryRule",
    "discover_plugin_names",
    "get_registry",
    "get_rules",
    "registry_manifest",
    "registry_metadata",
    "registry_sources",
    "registry_summary",
]
'@ | Set-Content `
    -Path $initPath `
    -Encoding UTF8

$pluginTestsPath = Join-Path `
    $root `
    "src\classification_v2\registry_plugin_tests.py"

@'
from __future__ import annotations

from .matching_engine import RegistryMatcher
from .registry.loader import (
    discover_plugin_names,
    get_registry,
    registry_manifest,
    registry_sources,
)


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
    discovered = discover_plugin_names()
    sources = registry_sources()
    registry = get_registry()
    manifest = registry_manifest()

    assert_true(
        "sports" in discovered,
        "Sports plugin was not discovered",
    )

    assert_true(
        "leagues" in discovered,
        "Leagues plugin was not discovered",
    )

    assert_equal(
        sources.get("sports"),
        10,
        "Sports plugin rule count",
    )

    assert_equal(
        sources.get("leagues"),
        24,
        "Leagues plugin rule count",
    )

    assert_equal(
        len(registry),
        34,
        "Registry rule total",
    )

    assert_equal(
        manifest["plugin_count"],
        2,
        "Registry plugin count",
    )

    assert_equal(
        manifest["registry_loader_type"],
        "plugin_discovery",
        "Registry loader type",
    )

    rule_ids = [
        rule.rule_id
        for rule in registry
    ]

    assert_equal(
        len(rule_ids),
        len(set(rule_ids)),
        "Duplicate registry IDs",
    )

    matcher = RegistryMatcher()

    nba = matcher.match(
        "NBA Finals winner",
        "league",
    )

    assert_equal(
        nba.value,
        "NBA",
        "NBA plugin match",
    )

    world_cup = matcher.match(
        "FIFA World Cup winner",
        "league",
    )

    assert_equal(
        world_cup.value,
        "FIFA World Cup",
        "World Cup plugin match",
    )

    soccer = matcher.match(
        "Soccer tournament winner",
        "sport",
    )

    assert_equal(
        soccer.value,
        "Soccer",
        "Soccer plugin match",
    )

    unknown = matcher.match(
        "Unknown test market",
        "league",
    )

    assert_equal(
        unknown.value,
        None,
        "Unknown league fallback",
    )

    print(
        "Registry plugin-loader tests passed: 12"
    )


if __name__ == "__main__":
    run_tests()
'@ | Set-Content `
    -Path $pluginTestsPath `
    -Encoding UTF8

$versionTestsPath = Join-Path `
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
        "0.3.1",
        "Platform version",
    )

    assert_equal(
        platform["classification_engine_version"],
        "2.4.0",
        "Classification Engine version",
    )

    assert_equal(
        manifest["registry_version"],
        "1.1.0",
        "Registry version",
    )

    assert_equal(
        manifest["registry_schema_version"],
        "1",
        "Registry schema version",
    )

    assert_equal(
        manifest["registry_loader_type"],
        "plugin_discovery",
        "Registry loader type",
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
        "passed: 8"
    )


if __name__ == "__main__":
    run_tests()
'@ | Set-Content `
    -Path $versionTestsPath `
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
    registry_sources,
    registry_summary,
)
from classification_v2.registry_plugin_tests import (
    run_tests as run_plugin_tests,
)
from classification_v2.registry_tests import (
    run_tests as run_registry_tests,
)
from classification_v2.registry_version_tests import (
    run_tests as run_version_tests,
)
from platform_version import version_info


MODULE_VERSION = "2.4.0-plugin-registry"


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
            "Classification v2 Plugin-Based "
            "Registry and Matching Engine"
        )
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
    )

    parser.add_argument(
        "--plugin-test",
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
        "--sources",
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
        run_plugin_tests()
        run_version_tests()
        return

    if args.plugin_test:
        run_plugin_tests()
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

    if args.sources:
        print_json(
            {
                "plugins": registry_sources(),
            }
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

$newEntry = @'
# Changelog

## [0.3.1] - 2026-07-20

### Added

- Automatic registry plugin discovery.
- Dynamic registry module importing.
- Plugin rule validation.
- Plugin source diagnostics.
- Plugin manifest reporting.
- Duplicate rule ID protection.
- Registry plugin-loader tests.

### Changed

- Classification Engine upgraded to 2.4.0.
- Registry upgraded to 1.1.0.
- Registry loader no longer hardcodes sports and league imports.

### Preserved

- All 10 sport rules.
- All 24 league rules.
- Existing matching behavior.
- Existing registry schema.
- No database writes.
- No orchestrator activation.

'@

$remainingChangelog = $oldChangelog

if ($remainingChangelog.StartsWith("# Changelog")) {
    $remainingChangelog = $remainingChangelog.Substring(
        "# Changelog".Length
    ).TrimStart()
}

if (
    $oldChangelog -and
    -not $oldChangelog.Contains("## [0.3.1]")
) {
    $newEntry = (
        $newEntry.TrimEnd() +
        "`r`n`r`n" +
        $remainingChangelog.TrimStart()
    )
}
elseif (
    $oldChangelog.Contains("## [0.3.1]")
) {
    $newEntry = $oldChangelog
}

$newEntry | Set-Content `
    -Path $changelogPath `
    -Encoding UTF8

$compileFiles = @(
    $platformVersionPath,
    $metadataPath,
    $loaderPath,
    $initPath,
    $pluginTestsPath,
    $versionTestsPath,
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
Write-Host "Running complete test suite..."

& $runnerPath --self-test

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "Tests failed. Previous files restored."
}

Write-Host ""
Write-Host "Running plugin source report..."

& $runnerPath --sources

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "Plugin source report failed. "
        "Previous files restored."
}

Write-Host ""
Write-Host "Running registry manifest..."

& $runnerPath --manifest

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "Registry manifest failed. "
        "Previous files restored."
}

Write-Host ""
Write-Host "Running NBA regression match..."

& $runnerPath `
    --type league `
    --title "NBA Finals winner"

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "NBA regression match failed. "
        "Previous files restored."
}

Write-Host ""
Write-Host ("=" * 108)
Write-Host "PLUGIN-BASED REGISTRY LOADER INSTALLED"
Write-Host ("=" * 108)

Write-Host "Platform version:      0.3.1"
Write-Host "Classification engine: 2.4.0"
Write-Host "Registry version:      1.1.0"
Write-Host "Registry schema:       1"
Write-Host "Loader type:           plugin_discovery"
Write-Host "Existing rules:        34"
Write-Host "Expected plugins:      2"
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
Write-Host "Show discovered plugins:"
Write-Host `
    ".\run_classification_v2_registry.ps1 --sources"

Write-Host ""
Write-Host "Show registry manifest:"
Write-Host `
    ".\run_classification_v2_registry.ps1 --manifest"

Write-Host ""
Write-Host "Test an existing rule:"
Write-Host `
    '.\run_classification_v2_registry.ps1 --type league --title "NBA Finals winner"'

Write-Host ("=" * 108)