$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

$backup = Join-Path `
    $root `
    "backups\market_type_registry_$stamp"

if (-not (Test-Path $root)) {
    throw "Project root not found: $root"
}

$targets = @(
    "src\platform_version.py",
    "src\classification_v2\registry\metadata.py",
    "src\classification_v2\registry\market_types.py",
    "src\classification_v2\market_type_tests.py",
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
Write-Host "Installing Market Type Registry..."

$platformVersionPath = Join-Path `
    $root `
    "src\platform_version.py"

@'
from __future__ import annotations


PLATFORM_NAME = "Polymarket Intelligence Platform"
PLATFORM_VERSION = "0.4.0"
CLASSIFICATION_ENGINE_VERSION = "2.5.0"


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
REGISTRY_VERSION = "1.2.0"
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

$marketTypesPath = Join-Path `
    $registryDirectory `
    "market_types.py"

@'
from __future__ import annotations

from .models import RegistryRule


RULES: tuple[RegistryRule, ...] = (
    RegistryRule(
        rule_id="market_type.moneyline",
        rule_type="market_type",
        value="Moneyline",
        aliases=(
            r"\bmoneyline\b",
            r"\bmoney line\b",
            r"\bmatch winner\b",
            r"\bgame winner\b",
        ),
        confidence=0.96,
        category=None,
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.spread",
        rule_type="market_type",
        value="Spread",
        aliases=(
            r"\bspread\b",
            r"\bpoint spread\b",
            r"\bhandicap\b",
            r"\b(?:[+-]\d+(?:\.\d+)?)\s+spread\b",
        ),
        confidence=0.96,
        category=None,
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.total",
        rule_type="market_type",
        value="Total",
        aliases=(
            r"\bgame total\b",
            r"\bmatch total\b",
            r"\btotal goals\b",
            r"\btotal points\b",
            r"\btotal runs\b",
            r"\bover\/under\b",
            r"\bover under\b",
            r"\b(?:over|under)\s+\d+(?:\.\d+)?\s+"
            r"(?:goals|points|runs|games|sets|rounds)\b",
        ),
        confidence=0.96,
        category=None,
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.team_total",
        rule_type="market_type",
        value="Team Total",
        aliases=(
            r"\bteam total\b",
            r"\bteam goals total\b",
            r"\bteam points total\b",
            r"\bteam runs total\b",
        ),
        confidence=0.98,
        category=None,
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.player_prop",
        rule_type="market_type",
        value="Player Prop",
        aliases=(
            r"\bplayer prop\b",
            r"\bplayer props\b",
            r"\bplayer total\b",
            r"\bplayer performance\b",
            r"\bplayer statistics?\b",
        ),
        confidence=0.97,
        category=None,
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.both_teams_to_score",
        rule_type="market_type",
        value="Both Teams to Score",
        aliases=(
            r"\bboth teams to score\b",
            r"\bbtts\b",
            r"\bboth teams score\b",
        ),
        confidence=0.99,
        category="Sports",
        sport="Soccer",
    ),
    RegistryRule(
        rule_id="market_type.exact_score",
        rule_type="market_type",
        value="Exact Score",
        aliases=(
            r"\bexact score\b",
            r"\bcorrect score\b",
            r"\bfinal score exactly\b",
        ),
        confidence=0.98,
        category="Sports",
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.to_qualify",
        rule_type="market_type",
        value="To Qualify",
        aliases=(
            r"\bto qualify\b",
            r"\bwill qualify\b",
            r"\badvance to the next round\b",
            r"\bto advance\b",
        ),
        confidence=0.97,
        category="Sports",
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.tournament_winner",
        rule_type="market_type",
        value="Tournament Winner",
        aliases=(
            r"\btournament winner\b",
            r"\bwin the tournament\b",
            r"\bwin the world cup\b",
            r"\bworld cup winner\b",
            r"\bchampionship winner\b",
        ),
        confidence=0.96,
        category="Sports",
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.season_winner",
        rule_type="market_type",
        value="Season Winner",
        aliases=(
            r"\bseason winner\b",
            r"\bwin the league\b",
            r"\bleague winner\b",
            r"\bwin the championship\b",
            r"\bregular season winner\b",
        ),
        confidence=0.96,
        category="Sports",
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.election_winner",
        rule_type="market_type",
        value="Election Winner",
        aliases=(
            r"\belection winner\b",
            r"\bwin the election\b",
            r"\bpresidential election winner\b",
            r"\bwin the presidency\b",
            r"\belected president\b",
        ),
        confidence=0.97,
        category="Politics",
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.award_winner",
        rule_type="market_type",
        value="Award Winner",
        aliases=(
            r"\baward winner\b",
            r"\bwin the award\b",
            r"\bmost valuable player\b",
            r"\bwin mvp\b",
            r"\bwin the oscar\b",
            r"\bwin the grammy\b",
        ),
        confidence=0.96,
        category=None,
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.binary_yes_no",
        rule_type="market_type",
        value="Yes/No Binary",
        aliases=(
            r"\byes\/no\b",
            r"\byes or no\b",
            r"\bbinary market\b",
            r"\bbinary outcome\b",
            r"\bresolve(?:s|d)?\s+(?:yes|no)\b",
        ),
        confidence=0.95,
        category=None,
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.threshold",
        rule_type="market_type",
        value="Above/Below Threshold",
        aliases=(
            r"\babove or below\b",
            r"\babove\/below\b",
            r"\bthreshold market\b",
            r"\bexceed the threshold\b",
            r"\breach the threshold\b",
            r"\bat least \$?\d+(?:,\d{3})*(?:\.\d+)?\b",
        ),
        confidence=0.93,
        category=None,
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.price_target",
        rule_type="market_type",
        value="Price Target",
        aliases=(
            r"\bprice target\b",
            r"\breach \$?\d+(?:,\d{3})*(?:\.\d+)?\b",
            r"\bhit \$?\d+(?:,\d{3})*(?:\.\d+)?\b",
            r"\breach a price of\b",
            r"\btrade above \$?\d+(?:,\d{3})*(?:\.\d+)?\b",
            r"\btrade below \$?\d+(?:,\d{3})*(?:\.\d+)?\b",
        ),
        confidence=0.95,
        category="Finance",
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.range",
        rule_type="market_type",
        value="Range",
        aliases=(
            r"\brange market\b",
            r"\bbetween \$?\d+(?:,\d{3})*(?:\.\d+)? "
            r"and \$?\d+(?:,\d{3})*(?:\.\d+)?\b",
            r"\bwithin the range\b",
            r"\bprice range\b",
            r"\bpercentage range\b",
        ),
        confidence=0.94,
        category=None,
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.resolution_event",
        rule_type="market_type",
        value="Resolution Event",
        aliases=(
            r"\bresolution event\b",
            r"\bmarket resolution\b",
            r"\bresolve based on\b",
            r"\bwill be resolved\b",
            r"\bresolution criteria\b",
        ),
        confidence=0.95,
        category=None,
        sport=None,
    ),
    RegistryRule(
        rule_id="market_type.method_of_victory",
        rule_type="market_type",
        value="Method of Victory",
        aliases=(
            r"\bmethod of victory\b",
            r"\bwin by knockout\b",
            r"\bwin by ko\b",
            r"\bwin by tko\b",
            r"\bwin by submission\b",
            r"\bwin by decision\b",
        ),
        confidence=0.98,
        category="Sports",
        sport="MMA",
    ),
    RegistryRule(
        rule_id="market_type.winning_margin",
        rule_type="market_type",
        value="Winning Margin",
        aliases=(
            r"\bwinning margin\b",
            r"\bmargin of victory\b",
            r"\bwin by \d+(?:\.\d+)? or more\b",
            r"\bwin by between \d+ and \d+\b",
        ),
        confidence=0.96,
        category="Sports",
        sport=None,
    ),
)
'@ | Set-Content `
    -Path $marketTypesPath `
    -Encoding UTF8

$marketTypeTestsPath = Join-Path `
    $root `
    "src\classification_v2\market_type_tests.py"

@'
from __future__ import annotations

from .matching_engine import RegistryMatcher
from .registry.loader import (
    get_rules,
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


def assert_market_type(
    matcher: RegistryMatcher,
    title: str,
    expected: str,
) -> None:
    result = matcher.match(
        title,
        "market_type",
    )

    assert_equal(
        result.value,
        expected,
        f"Market type for {title!r}",
    )

    assert_true(
        result.confidence >= 0.90,
        f"Confidence for {title!r}",
    )


def run_tests() -> None:
    rules = get_rules("market_type")
    sources = registry_sources()
    manifest = registry_manifest()

    assert_equal(
        len(rules),
        19,
        "Market type rule count",
    )

    assert_equal(
        sources.get("market_types"),
        19,
        "Market type plugin source count",
    )

    assert_equal(
        manifest["plugin_count"],
        3,
        "Plugin count",
    )

    assert_equal(
        manifest["rule_counts"]["market_type"],
        19,
        "Manifest market type count",
    )

    assert_equal(
        manifest["rule_counts"]["total"],
        53,
        "Manifest total rule count",
    )

    matcher = RegistryMatcher()

    cases = (
        (
            "France moneyline",
            "Moneyline",
        ),
        (
            "Lakers -4.5 point spread",
            "Spread",
        ),
        (
            "Over 2.5 total goals",
            "Total",
        ),
        (
            "Boston team total points",
            "Team Total",
        ),
        (
            "LeBron James player prop",
            "Player Prop",
        ),
        (
            "Both teams to score",
            "Both Teams to Score",
        ),
        (
            "France vs Spain exact score",
            "Exact Score",
        ),
        (
            "Will Canada qualify? To qualify market",
            "To Qualify",
        ),
        (
            "FIFA World Cup tournament winner",
            "Tournament Winner",
        ),
        (
            "Premier League season winner",
            "Season Winner",
        ),
        (
            "2028 presidential election winner",
            "Election Winner",
        ),
        (
            "NBA most valuable player",
            "Award Winner",
        ),
        (
            "This is a yes/no binary market",
            "Yes/No Binary",
        ),
        (
            "Bitcoin above or below threshold",
            "Above/Below Threshold",
        ),
        (
            "Bitcoin price target of $150000",
            "Price Target",
        ),
        (
            "Bitcoin price range market",
            "Range",
        ),
        (
            "Market resolution criteria",
            "Resolution Event",
        ),
        (
            "Fighter to win by submission",
            "Method of Victory",
        ),
        (
            "Winning margin of 10 points",
            "Winning Margin",
        ),
    )

    for title, expected in cases:
        assert_market_type(
            matcher,
            title,
            expected,
        )

    unknown = matcher.match(
        "Completely unknown market structure",
        "market_type",
    )

    assert_equal(
        unknown.value,
        None,
        "Unknown market type fallback",
    )

    assert_true(
        unknown.confidence <= 0.20,
        "Unknown market type confidence",
    )

    print(
        "Market type registry tests passed: 26"
    )


if __name__ == "__main__":
    run_tests()
'@ | Set-Content `
    -Path $marketTypeTestsPath `
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

    assert_true(
        "market_types" in discovered,
        "Market types plugin was not discovered",
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
        sources.get("market_types"),
        19,
        "Market types plugin rule count",
    )

    assert_equal(
        len(registry),
        53,
        "Registry rule total",
    )

    assert_equal(
        manifest["plugin_count"],
        3,
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

    moneyline = matcher.match(
        "France moneyline",
        "market_type",
    )

    assert_equal(
        moneyline.value,
        "Moneyline",
        "Market type plugin match",
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
        "Registry plugin-loader tests passed: 15"
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
        "0.4.0",
        "Platform version",
    )

    assert_equal(
        platform["classification_engine_version"],
        "2.5.0",
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
from platform_version import version_info


MODULE_VERSION = "2.5.0-market-types"


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

    parser.add_argument("--type")
    parser.add_argument("--title")

    args = parser.parse_args()

    if args.self_test:
        run_registry_tests()
        run_plugin_tests()
        run_market_type_tests()
        run_version_tests()
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

## [0.4.0] - 2026-07-20

### Added

- Market Type Registry plugin.
- Nineteen market-type classification rules.
- Sports betting market structures.
- Political and financial market structures.
- Market type regression tests.
- Automatic discovery of the market-types plugin.

### Market Types

- Moneyline
- Spread
- Total
- Team Total
- Player Prop
- Both Teams to Score
- Exact Score
- To Qualify
- Tournament Winner
- Season Winner
- Election Winner
- Award Winner
- Yes/No Binary
- Above/Below Threshold
- Price Target
- Range
- Resolution Event
- Method of Victory
- Winning Margin

### Changed

- Platform upgraded to 0.4.0.
- Classification Engine upgraded to 2.5.0.
- Registry upgraded to 1.2.0.
- Registry now contains 53 total rules.
- Registry now discovers three plugins.

### Preserved

- All existing sport rules.
- All existing league rules.
- Plugin-based loading architecture.
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
    -not $oldChangelog.Contains("## [0.4.0]")
) {
    $newEntry = (
        $newEntry.TrimEnd() +
        "`r`n`r`n" +
        $remainingChangelog.TrimStart()
    )
}
elseif (
    $oldChangelog.Contains("## [0.4.0]")
) {
    $newEntry = $oldChangelog
}

$newEntry | Set-Content `
    -Path $changelogPath `
    -Encoding UTF8

$compileFiles = @(
    $platformVersionPath,
    $metadataPath,
    $marketTypesPath,
    $marketTypeTestsPath,
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
Write-Host "Running market-type regression matches..."

& $runnerPath `
    --type market_type `
    --title "France moneyline"

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "Moneyline regression match failed. "
        "Previous files restored."
}

& $runnerPath `
    --type market_type `
    --title "Both teams to score"

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "BTTS regression match failed. "
        "Previous files restored."
}

& $runnerPath `
    --type market_type `
    --title "2028 presidential election winner"

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "Election regression match failed. "
        "Previous files restored."
}

Write-Host ""
Write-Host ("=" * 108)
Write-Host "MARKET TYPE REGISTRY INSTALLED"
Write-Host ("=" * 108)

Write-Host "Platform version:      0.4.0"
Write-Host "Classification engine: 2.5.0"
Write-Host "Registry version:      1.2.0"
Write-Host "Registry schema:       1"
Write-Host "Loader type:           plugin_discovery"
Write-Host "Sport rules:           10"
Write-Host "League rules:          24"
Write-Host "Market type rules:     19"
Write-Host "Total rules:           53"
Write-Host "Discovered plugins:    3"
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
Write-Host "Run market-type tests:"
Write-Host `
    ".\run_classification_v2_registry.ps1 --market-type-test"

Write-Host ""
Write-Host "Show discovered plugins:"
Write-Host `
    ".\run_classification_v2_registry.ps1 --sources"

Write-Host ""
Write-Host "Show registry manifest:"
Write-Host `
    ".\run_classification_v2_registry.ps1 --manifest"

Write-Host ""
Write-Host "Test a market type:"
Write-Host `
    '.\run_classification_v2_registry.ps1 --type market_type --title "France moneyline"'

Write-Host ("=" * 108)