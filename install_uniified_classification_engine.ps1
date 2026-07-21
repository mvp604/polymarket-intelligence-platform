$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

$backup = Join-Path `
    $root `
    "backups\unified_classification_engine_$stamp"

if (-not (Test-Path $root)) {
    throw "Project root not found: $root"
}

$targets = @(
    "src\platform_version.py",
    "src\classification_v2\confidence.py",
    "src\classification_v2\classifier.py",
    "src\classification_v2\unified_classifier_tests.py",
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
Write-Host "Installing Unified Classification Engine..."

$platformVersionPath = Join-Path `
    $root `
    "src\platform_version.py"

@'
from __future__ import annotations


PLATFORM_NAME = "Polymarket Intelligence Platform"
PLATFORM_VERSION = "0.5.0"
CLASSIFICATION_ENGINE_VERSION = "2.6.0"


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

$confidencePath = Join-Path `
    $root `
    "src\classification_v2\confidence.py"

@'
from __future__ import annotations


DEFAULT_COMPONENT_WEIGHTS: dict[str, float] = {
    "category": 0.15,
    "sport": 0.25,
    "league": 0.30,
    "market_type": 0.30,
    "event_type": 0.20,
}


def calculate_coverage(
    matched_rule_types: set[str],
    available_rule_types: set[str],
) -> float:
    if not available_rule_types:
        return 0.0

    return round(
        len(
            matched_rule_types.intersection(
                available_rule_types
            )
        )
        / len(available_rule_types),
        4,
    )


def aggregate_confidence(
    component_confidences: dict[str, float],
    available_rule_types: set[str],
) -> tuple[float, float]:
    matched_rule_types = set(
        component_confidences
    )

    coverage = calculate_coverage(
        matched_rule_types,
        available_rule_types,
    )

    if not component_confidences:
        return 0.10, coverage

    weighted_total = 0.0
    weight_total = 0.0

    for rule_type, confidence in (
        component_confidences.items()
    ):
        weight = DEFAULT_COMPONENT_WEIGHTS.get(
            rule_type,
            0.20,
        )

        weighted_total += confidence * weight
        weight_total += weight

    if weight_total <= 0:
        return 0.10, coverage

    weighted_average = (
        weighted_total / weight_total
    )

    coverage_multiplier = (
        0.75 + (0.25 * coverage)
    )

    final_confidence = min(
        max(
            weighted_average
            * coverage_multiplier,
            0.10,
        ),
        0.99,
    )

    return round(final_confidence, 4), coverage
'@ | Set-Content `
    -Path $confidencePath `
    -Encoding UTF8

$classifierPath = Join-Path `
    $root `
    "src\classification_v2\classifier.py"

@'
from __future__ import annotations

from dataclasses import dataclass

from .confidence import aggregate_confidence
from .matching_engine import (
    MatchResult,
    RegistryMatcher,
)
from .registry.loader import registry_summary


@dataclass(frozen=True)
class ComponentResult:
    rule_id: str
    rule_type: str
    value: str
    confidence: float
    evidence: tuple[str, ...]
    category: str | None
    sport: str | None


@dataclass(frozen=True)
class UnifiedClassification:
    title: str
    normalized_title: str
    category: str | None
    sport: str | None
    league: str | None
    market_type: str | None
    event_type: str | None
    confidence: float
    coverage: float
    matched_components: int
    available_components: int
    component_confidences: dict[str, float]
    evidence: dict[str, tuple[str, ...]]
    rule_ids: dict[str, str]
    components: dict[str, ComponentResult]
    warnings: tuple[str, ...]


class UnifiedClassifier:
    def __init__(
        self,
        matcher: RegistryMatcher | None = None,
    ) -> None:
        self.matcher = matcher or RegistryMatcher()

    @staticmethod
    def registered_rule_types() -> tuple[str, ...]:
        summary = registry_summary()

        return tuple(
            sorted(
                rule_type
                for rule_type in summary
                if rule_type != "total"
            )
        )

    @staticmethod
    def to_component(
        result: MatchResult,
    ) -> ComponentResult:
        if (
            result.rule_id is None
            or result.value is None
        ):
            raise ValueError(
                "Cannot convert an unmatched result "
                "to a component"
            )

        return ComponentResult(
            rule_id=result.rule_id,
            rule_type=result.rule_type,
            value=result.value,
            confidence=result.confidence,
            evidence=result.evidence,
            category=result.category,
            sport=result.sport,
        )

    @staticmethod
    def resolve_metadata(
        components: dict[str, ComponentResult],
        attribute: str,
    ) -> tuple[str | None, tuple[str, ...]]:
        candidates: list[
            tuple[float, str, str]
        ] = []

        direct = components.get(attribute)

        if direct is not None:
            candidates.append(
                (
                    direct.confidence + 0.05,
                    direct.value,
                    f"direct:{attribute}",
                )
            )

        for rule_type, component in (
            components.items()
        ):
            metadata_value = getattr(
                component,
                attribute,
                None,
            )

            if metadata_value is None:
                continue

            candidates.append(
                (
                    component.confidence,
                    metadata_value,
                    f"inferred:{rule_type}",
                )
            )

        if not candidates:
            return None, ()

        candidates.sort(
            key=lambda item: (
                item[0],
                len(item[1]),
            ),
            reverse=True,
        )

        selected = candidates[0][1]

        distinct_values = sorted(
            {
                value
                for _, value, _ in candidates
            }
        )

        warnings: list[str] = []

        if len(distinct_values) > 1:
            warnings.append(
                f"conflicting-{attribute}:"
                + "|".join(distinct_values)
            )

        return selected, tuple(warnings)

    def classify(
        self,
        title: str,
    ) -> UnifiedClassification:
        normalized_title = (
            self.matcher.normalize(title)
        )

        rule_types = (
            self.registered_rule_types()
        )

        components: dict[
            str,
            ComponentResult,
        ] = {}

        for rule_type in rule_types:
            result = self.matcher.match(
                title,
                rule_type,
            )

            if (
                result.rule_id is None
                or result.value is None
            ):
                continue

            components[rule_type] = (
                self.to_component(result)
            )

        category, category_warnings = (
            self.resolve_metadata(
                components,
                "category",
            )
        )

        sport, sport_warnings = (
            self.resolve_metadata(
                components,
                "sport",
            )
        )

        league_component = components.get(
            "league"
        )

        market_type_component = components.get(
            "market_type"
        )

        event_type_component = components.get(
            "event_type"
        )

        component_confidences = {
            rule_type: component.confidence
            for rule_type, component
            in components.items()
        }

        confidence, coverage = (
            aggregate_confidence(
                component_confidences,
                set(rule_types),
            )
        )

        evidence = {
            rule_type: component.evidence
            for rule_type, component
            in components.items()
        }

        rule_ids = {
            rule_type: component.rule_id
            for rule_type, component
            in components.items()
        }

        warnings = (
            *category_warnings,
            *sport_warnings,
        )

        if not components:
            warnings = (
                *warnings,
                "no-classification-match",
            )

        return UnifiedClassification(
            title=title,
            normalized_title=normalized_title,
            category=category,
            sport=sport,
            league=(
                league_component.value
                if league_component
                else None
            ),
            market_type=(
                market_type_component.value
                if market_type_component
                else None
            ),
            event_type=(
                event_type_component.value
                if event_type_component
                else None
            ),
            confidence=confidence,
            coverage=coverage,
            matched_components=len(components),
            available_components=len(
                rule_types
            ),
            component_confidences=(
                component_confidences
            ),
            evidence=evidence,
            rule_ids=rule_ids,
            components=components,
            warnings=tuple(warnings),
        )
'@ | Set-Content `
    -Path $classifierPath `
    -Encoding UTF8

$testsPath = Join-Path `
    $root `
    "src\classification_v2\unified_classifier_tests.py"

@'
from __future__ import annotations

from .classifier import UnifiedClassifier


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
    classifier = UnifiedClassifier()

    rule_types = (
        classifier.registered_rule_types()
    )

    assert_equal(
        rule_types,
        (
            "league",
            "market_type",
            "sport",
        ),
        "Registered rule types",
    )

    nba = classifier.classify(
        "NBA Finals moneyline"
    )

    assert_equal(
        nba.category,
        "Sports",
        "NBA category",
    )

    assert_equal(
        nba.sport,
        "Basketball",
        "NBA inferred sport",
    )

    assert_equal(
        nba.league,
        "NBA",
        "NBA league",
    )

    assert_equal(
        nba.market_type,
        "Moneyline",
        "NBA market type",
    )

    assert_equal(
        nba.event_type,
        None,
        "NBA event type before registry",
    )

    assert_equal(
        nba.matched_components,
        2,
        "NBA matched components",
    )

    assert_true(
        nba.confidence >= 0.85,
        "NBA unified confidence",
    )

    assert_true(
        nba.coverage >= 0.66,
        "NBA classification coverage",
    )

    world_cup = classifier.classify(
        "FIFA World Cup tournament winner"
    )

    assert_equal(
        world_cup.category,
        "Sports",
        "World Cup category",
    )

    assert_equal(
        world_cup.sport,
        "Soccer",
        "World Cup inferred sport",
    )

    assert_equal(
        world_cup.league,
        "FIFA World Cup",
        "World Cup league",
    )

    assert_equal(
        world_cup.market_type,
        "Tournament Winner",
        "World Cup market type",
    )

    btts = classifier.classify(
        "Both teams to score"
    )

    assert_equal(
        btts.category,
        "Sports",
        "BTTS category",
    )

    assert_equal(
        btts.sport,
        "Soccer",
        "BTTS inferred sport",
    )

    assert_equal(
        btts.market_type,
        "Both Teams to Score",
        "BTTS market type",
    )

    bitcoin = classifier.classify(
        "Bitcoin price target of $150000"
    )

    assert_equal(
        bitcoin.category,
        "Finance",
        "Bitcoin category",
    )

    assert_equal(
        bitcoin.market_type,
        "Price Target",
        "Bitcoin market type",
    )

    assert_equal(
        bitcoin.sport,
        None,
        "Bitcoin sport",
    )

    election = classifier.classify(
        "2028 presidential election winner"
    )

    assert_equal(
        election.category,
        "Politics",
        "Election category",
    )

    assert_equal(
        election.market_type,
        "Election Winner",
        "Election market type",
    )

    explicit_sport = classifier.classify(
        "Soccer moneyline"
    )

    assert_equal(
        explicit_sport.sport,
        "Soccer",
        "Explicit sport",
    )

    assert_equal(
        explicit_sport.market_type,
        "Moneyline",
        "Explicit sport market type",
    )

    unknown = classifier.classify(
        "Completely unknown market structure"
    )

    assert_equal(
        unknown.category,
        None,
        "Unknown category",
    )

    assert_equal(
        unknown.sport,
        None,
        "Unknown sport",
    )

    assert_equal(
        unknown.league,
        None,
        "Unknown league",
    )

    assert_equal(
        unknown.market_type,
        None,
        "Unknown market type",
    )

    assert_equal(
        unknown.confidence,
        0.10,
        "Unknown confidence",
    )

    assert_equal(
        unknown.coverage,
        0.0,
        "Unknown coverage",
    )

    assert_true(
        "no-classification-match"
        in unknown.warnings,
        "Unknown classification warning",
    )

    assert_true(
        "league" in nba.evidence,
        "NBA league evidence",
    )

    assert_true(
        "market_type" in nba.evidence,
        "NBA market-type evidence",
    )

    assert_equal(
        nba.rule_ids["league"],
        "league.nba",
        "NBA league rule ID",
    )

    assert_equal(
        nba.rule_ids["market_type"],
        "market_type.moneyline",
        "NBA market-type rule ID",
    )

    print(
        "Unified classifier tests passed: 31"
    )


if __name__ == "__main__":
    run_tests()
'@ | Set-Content `
    -Path $testsPath `
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
        "0.5.0",
        "Platform version",
    )

    assert_equal(
        platform["classification_engine_version"],
        "2.6.0",
        "Classification Engine version",
    )

    assert_equal(
        manifest["registry_version"],
        "1.2.0",
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

    assert_equal(
        manifest["rule_counts"]["total"],
        53,
        "Registry total",
    )

    assert_true(
        "league" in manifest["rule_types"],
        "League rule type missing",
    )

    assert_true(
        "sport" in manifest["rule_types"],
        "Sport rule type missing",
    )

    assert_true(
        "market_type" in manifest["rule_types"],
        "Market type rule type missing",
    )

    print(
        "Versioned registry foundation tests "
        "passed: 9"
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

from classification_v2.classifier import (
    UnifiedClassifier,
)
from classification_v2.market_type_tests import (
    run_tests as run_market_type_tests,
)
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
from classification_v2.unified_classifier_tests import (
    run_tests as run_unified_tests,
)
from platform_version import version_info


MODULE_VERSION = "2.6.0-unified-classifier"


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
            "Classification v2 Unified "
            "Classification Engine"
        )
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
    )

    parser.add_argument(
        "--unified-test",
        action="store_true",
    )

    parser.add_argument(
        "--market-type-test",
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

    parser.add_argument(
        "--classify",
        action="store_true",
    )

    parser.add_argument("--type")
    parser.add_argument("--title")

    args = parser.parse_args()

    if args.self_test:
        run_registry_tests()
        run_plugin_tests()
        run_market_type_tests()
        run_unified_tests()
        run_version_tests()
        return

    if args.unified_test:
        run_unified_tests()
        return

    if args.market_type_test:
        run_market_type_tests()
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

    if args.classify:
        if not args.title:
            parser.error(
                "--title is required with "
                "--classify"
            )

        classifier = UnifiedClassifier()

        print_json(
            asdict(
                classifier.classify(
                    args.title
                )
            )
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

## [0.5.0] - 2026-07-20

### Added

- Unified Classification Engine.
- Standardized classification result object.
- Confidence aggregation module.
- Classification coverage measurement.
- Category and sport metadata inference.
- Component-level confidence reporting.
- Component-level evidence reporting.
- Rule ID traceability.
- Classification conflict warnings.
- Unified classification CLI mode.
- Unified classifier regression tests.

### Unified Output

- Category
- Sport
- League
- Market Type
- Event Type placeholder
- Overall confidence
- Registry coverage
- Matched components
- Evidence
- Rule IDs
- Warnings

### Changed

- Platform upgraded to 0.5.0.
- Classification Engine upgraded to 2.6.0.
- Registry remains at 1.2.0.
- Registry remains at 53 rules and 3 plugins.

### Preserved

- Existing registry rules.
- Existing direct matcher interface.
- Plugin discovery architecture.
- Registry schema version 1.
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
    -not $oldChangelog.Contains("## [0.5.0]")
) {
    $newEntry = (
        $newEntry.TrimEnd() +
        "`r`n`r`n" +
        $remainingChangelog.TrimStart()
    )
}
elseif (
    $oldChangelog.Contains("## [0.5.0]")
) {
    $newEntry = $oldChangelog
}

$newEntry | Set-Content `
    -Path $changelogPath `
    -Encoding UTF8

$compileFiles = @(
    $platformVersionPath,
    $confidencePath,
    $classifierPath,
    $testsPath,
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
Write-Host "Running NBA unified classification..."

& $runnerPath `
    --classify `
    --title "NBA Finals moneyline"

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "NBA unified classification failed. "
        "Previous files restored."
}

Write-Host ""
Write-Host "Running World Cup unified classification..."

& $runnerPath `
    --classify `
    --title "FIFA World Cup tournament winner"

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "World Cup unified classification failed. "
        "Previous files restored."
}

Write-Host ""
Write-Host "Running financial-market classification..."

& $runnerPath `
    --classify `
    --title 'Bitcoin price target of $150000'

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "Financial-market classification failed. "
        "Previous files restored."
}

Write-Host ""
Write-Host ("=" * 108)
Write-Host "UNIFIED CLASSIFICATION ENGINE INSTALLED"
Write-Host ("=" * 108)

Write-Host "Platform version:      0.5.0"
Write-Host "Classification engine: 2.6.0"
Write-Host "Registry version:      1.2.0"
Write-Host "Registry schema:       1"
Write-Host "Registry rules:        53"
Write-Host "Registry plugins:      3"
Write-Host "Unified classifier:    ENABLED"
Write-Host "Confidence aggregator: ENABLED"
Write-Host "Event type registry:   NOT YET INSTALLED"
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
Write-Host "Run unified tests:"
Write-Host `
    ".\run_classification_v2_registry.ps1 --unified-test"

Write-Host ""
Write-Host "Classify an NBA market:"
Write-Host `
    '.\run_classification_v2_registry.ps1 --classify --title "NBA Finals moneyline"'

Write-Host ""
Write-Host "Classify a World Cup market:"
Write-Host `
    '.\run_classification_v2_registry.ps1 --classify --title "FIFA World Cup tournament winner"'

Write-Host ""
Write-Host "Classify a financial market:"
Write-Host `
    ".\run_classification_v2_registry.ps1 --classify --title 'Bitcoin price target of `$150000'"

Write-Host ("=" * 108)