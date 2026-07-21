$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = Join-Path `
    $root `
    "backups\classification_v2_registry_engine_$stamp"

if (-not (Test-Path $root)) {
    throw "Project root not found: $root"
}

$targets = @(
    "src\classification_v2\registry\__init__.py",
    "src\classification_v2\registry\models.py",
    "src\classification_v2\registry\sports.py",
    "src\classification_v2\registry\leagues.py",
    "src\classification_v2\registry\loader.py",
    "src\classification_v2\matching_engine.py",
    "src\classification_v2\registry_tests.py",
    "src\classification_v2_registry_cli.py",
    "run_classification_v2_registry.ps1"
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
Write-Host "Installing Classification v2 Shared Registry Engine..."

$registryDirectory = Join-Path `
    $root `
    "src\classification_v2\registry"

New-Item `
    -ItemType Directory `
    -Path $registryDirectory `
    -Force | Out-Null

@'
from .loader import get_registry, get_rules, registry_summary
from .models import RegistryRule

__all__ = [
    "RegistryRule",
    "get_registry",
    "get_rules",
    "registry_summary",
]
'@ | Set-Content `
    -Path (Join-Path $registryDirectory "__init__.py") `
    -Encoding UTF8

@'
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RegistryRule:
    rule_id: str
    rule_type: str
    value: str
    aliases: tuple[str, ...]
    confidence: float
    category: str | None = None
    sport: str | None = None
    metadata: dict[str, str] = field(
        default_factory=dict
    )

    def validate(self) -> None:
        if not self.rule_id.strip():
            raise ValueError(
                "rule_id cannot be empty"
            )

        if not self.rule_type.strip():
            raise ValueError(
                f"{self.rule_id}: rule_type cannot be empty"
            )

        if not self.value.strip():
            raise ValueError(
                f"{self.rule_id}: value cannot be empty"
            )

        if not self.aliases:
            raise ValueError(
                f"{self.rule_id}: aliases cannot be empty"
            )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"{self.rule_id}: invalid confidence "
                f"{self.confidence}"
            )
'@ | Set-Content `
    -Path (Join-Path $registryDirectory "models.py") `
    -Encoding UTF8

@'
from __future__ import annotations

from .models import RegistryRule


RULES: tuple[RegistryRule, ...] = (
    RegistryRule(
        rule_id="sport.soccer",
        rule_type="sport",
        value="Soccer",
        aliases=(
            r"\bsoccer\b",
            r"\bassociation football\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.basketball",
        rule_type="sport",
        value="Basketball",
        aliases=(
            r"\bbasketball\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.baseball",
        rule_type="sport",
        value="Baseball",
        aliases=(
            r"\bbaseball\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.american_football",
        rule_type="sport",
        value="American Football",
        aliases=(
            r"\bamerican football\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.ice_hockey",
        rule_type="sport",
        value="Ice Hockey",
        aliases=(
            r"\bice hockey\b",
            r"\bhockey\b",
        ),
        confidence=0.91,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.mma",
        rule_type="sport",
        value="MMA",
        aliases=(
            r"\bmma\b",
            r"\bmixed martial arts\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.tennis",
        rule_type="sport",
        value="Tennis",
        aliases=(
            r"\btennis\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.cricket",
        rule_type="sport",
        value="Cricket",
        aliases=(
            r"\bcricket\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.golf",
        rule_type="sport",
        value="Golf",
        aliases=(
            r"\bgolf\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.motorsport",
        rule_type="sport",
        value="Motorsport",
        aliases=(
            r"\bmotorsport\b",
            r"\bmotor racing\b",
        ),
        confidence=0.92,
        category="Sports",
    ),
)
'@ | Set-Content `
    -Path (Join-Path $registryDirectory "sports.py") `
    -Encoding UTF8

@'
from __future__ import annotations

from .models import RegistryRule


RULES: tuple[RegistryRule, ...] = (
    RegistryRule(
        rule_id="league.fifa_world_cup",
        rule_type="league",
        value="FIFA World Cup",
        aliases=(
            r"\bfifa world cup\b",
            r"\bworld cup\b",
        ),
        confidence=0.94,
        category="Sports",
        sport="Soccer",
    ),
    RegistryRule(
        rule_id="league.uefa_champions_league",
        rule_type="league",
        value="UEFA Champions League",
        aliases=(
            r"\buefa champions league\b",
            r"\bchampions league\b",
            r"\bucl\b",
        ),
        confidence=0.95,
        category="Sports",
        sport="Soccer",
    ),
    RegistryRule(
        rule_id="league.uefa_europa_league",
        rule_type="league",
        value="UEFA Europa League",
        aliases=(
            r"\buefa europa league\b",
            r"\beuropa league\b",
        ),
        confidence=0.95,
        category="Sports",
        sport="Soccer",
    ),
    RegistryRule(
        rule_id="league.premier_league",
        rule_type="league",
        value="Premier League",
        aliases=(
            r"\bpremier league\b",
            r"\benglish premier league\b",
            r"\bepl\b",
        ),
        confidence=0.95,
        category="Sports",
        sport="Soccer",
    ),
    RegistryRule(
        rule_id="league.la_liga",
        rule_type="league",
        value="La Liga",
        aliases=(
            r"\bla liga\b",
        ),
        confidence=0.96,
        category="Sports",
        sport="Soccer",
    ),
    RegistryRule(
        rule_id="league.serie_a",
        rule_type="league",
        value="Serie A",
        aliases=(
            r"\bserie a\b",
        ),
        confidence=0.96,
        category="Sports",
        sport="Soccer",
    ),
    RegistryRule(
        rule_id="league.bundesliga",
        rule_type="league",
        value="Bundesliga",
        aliases=(
            r"\bbundesliga\b",
        ),
        confidence=0.96,
        category="Sports",
        sport="Soccer",
    ),
    RegistryRule(
        rule_id="league.ligue_1",
        rule_type="league",
        value="Ligue 1",
        aliases=(
            r"\bligue 1\b",
        ),
        confidence=0.96,
        category="Sports",
        sport="Soccer",
    ),
    RegistryRule(
        rule_id="league.mls",
        rule_type="league",
        value="MLS",
        aliases=(
            r"\bmls\b",
            r"\bmajor league soccer\b",
        ),
        confidence=0.95,
        category="Sports",
        sport="Soccer",
    ),
    RegistryRule(
        rule_id="league.nba",
        rule_type="league",
        value="NBA",
        aliases=(
            r"\bnba\b",
        ),
        confidence=0.98,
        category="Sports",
        sport="Basketball",
    ),
    RegistryRule(
        rule_id="league.wnba",
        rule_type="league",
        value="WNBA",
        aliases=(
            r"\bwnba\b",
        ),
        confidence=0.98,
        category="Sports",
        sport="Basketball",
    ),
    RegistryRule(
        rule_id="league.euroleague",
        rule_type="league",
        value="EuroLeague",
        aliases=(
            r"\beuroleague\b",
        ),
        confidence=0.97,
        category="Sports",
        sport="Basketball",
    ),
    RegistryRule(
        rule_id="league.mlb",
        rule_type="league",
        value="MLB",
        aliases=(
            r"\bmlb\b",
            r"\bmajor league baseball\b",
        ),
        confidence=0.98,
        category="Sports",
        sport="Baseball",
    ),
    RegistryRule(
        rule_id="league.nfl",
        rule_type="league",
        value="NFL",
        aliases=(
            r"\bnfl\b",
            r"\bnational football league\b",
        ),
        confidence=0.98,
        category="Sports",
        sport="American Football",
    ),
    RegistryRule(
        rule_id="league.nhl",
        rule_type="league",
        value="NHL",
        aliases=(
            r"\bnhl\b",
            r"\bnational hockey league\b",
        ),
        confidence=0.98,
        category="Sports",
        sport="Ice Hockey",
    ),
    RegistryRule(
        rule_id="league.ufc",
        rule_type="league",
        value="UFC",
        aliases=(
            r"\bufc\b",
            r"\bufc fight night\b",
        ),
        confidence=0.98,
        category="Sports",
        sport="MMA",
    ),
    RegistryRule(
        rule_id="league.bellator",
        rule_type="league",
        value="Bellator",
        aliases=(
            r"\bbellator\b",
        ),
        confidence=0.98,
        category="Sports",
        sport="MMA",
    ),
    RegistryRule(
        rule_id="league.pfl",
        rule_type="league",
        value="PFL",
        aliases=(
            r"\bpfl\b",
            r"\bprofessional fighters league\b",
        ),
        confidence=0.97,
        category="Sports",
        sport="MMA",
    ),
    RegistryRule(
        rule_id="league.atp",
        rule_type="league",
        value="ATP",
        aliases=(
            r"\batp\b",
        ),
        confidence=0.97,
        category="Sports",
        sport="Tennis",
    ),
    RegistryRule(
        rule_id="league.wta",
        rule_type="league",
        value="WTA",
        aliases=(
            r"\bwta\b",
        ),
        confidence=0.97,
        category="Sports",
        sport="Tennis",
    ),
    RegistryRule(
        rule_id="league.pga_tour",
        rule_type="league",
        value="PGA Tour",
        aliases=(
            r"\bpga tour\b",
            r"\bpga\b",
        ),
        confidence=0.95,
        category="Sports",
        sport="Golf",
    ),
    RegistryRule(
        rule_id="league.formula_1",
        rule_type="league",
        value="Formula 1",
        aliases=(
            r"\bformula 1\b",
            r"\bf1\b",
        ),
        confidence=0.97,
        category="Sports",
        sport="Motorsport",
    ),
    RegistryRule(
        rule_id="league.nascar",
        rule_type="league",
        value="NASCAR",
        aliases=(
            r"\bnascar\b",
        ),
        confidence=0.98,
        category="Sports",
        sport="Motorsport",
    ),
    RegistryRule(
        rule_id="league.ipl",
        rule_type="league",
        value="IPL",
        aliases=(
            r"\bipl\b",
            r"\bindian premier league\b",
        ),
        confidence=0.97,
        category="Sports",
        sport="Cricket",
    ),
)
'@ | Set-Content `
    -Path (Join-Path $registryDirectory "leagues.py") `
    -Encoding UTF8

@'
from __future__ import annotations

from collections import defaultdict

from .leagues import RULES as LEAGUE_RULES
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
'@ | Set-Content `
    -Path (Join-Path $registryDirectory "loader.py") `
    -Encoding UTF8

$matchingEnginePath = Join-Path `
    $root `
    "src\classification_v2\matching_engine.py"

@'
from __future__ import annotations

import re
from dataclasses import dataclass

from .registry.loader import get_rules
from .registry.models import RegistryRule


@dataclass(frozen=True)
class MatchResult:
    rule_id: str | None
    rule_type: str
    value: str | None
    confidence: float
    evidence: tuple[str, ...]
    category: str | None = None
    sport: str | None = None


class RegistryMatcher:
    @staticmethod
    def normalize(text: str) -> str:
        return " ".join(
            text.strip().lower().split()
        )

    @staticmethod
    def find_alias_matches(
        text: str,
        rule: RegistryRule,
    ) -> tuple[str, ...]:
        return tuple(
            alias
            for alias in rule.aliases
            if re.search(
                alias,
                text,
                flags=re.IGNORECASE,
            )
        )

    def match(
        self,
        text: str,
        rule_type: str,
    ) -> MatchResult:
        normalized = self.normalize(text)

        best_rule: RegistryRule | None = None
        best_matches: tuple[str, ...] = ()

        for rule in get_rules(rule_type):
            matches = self.find_alias_matches(
                normalized,
                rule,
            )

            if not matches:
                continue

            if best_rule is None:
                best_rule = rule
                best_matches = matches
                continue

            current_score = (
                len(matches),
                rule.confidence,
                max(len(alias) for alias in matches),
            )

            best_score = (
                len(best_matches),
                best_rule.confidence,
                max(len(alias) for alias in best_matches),
            )

            if current_score > best_score:
                best_rule = rule
                best_matches = matches

        if best_rule is None:
            return MatchResult(
                rule_id=None,
                rule_type=rule_type,
                value=None,
                confidence=0.10,
                evidence=(
                    "no-registry-match",
                ),
            )

        confidence = min(
            best_rule.confidence
            + 0.015 * (len(best_matches) - 1),
            0.99,
        )

        return MatchResult(
            rule_id=best_rule.rule_id,
            rule_type=best_rule.rule_type,
            value=best_rule.value,
            confidence=confidence,
            evidence=tuple(
                f"matched:{alias}"
                for alias in best_matches
            ),
            category=best_rule.category,
            sport=best_rule.sport,
        )
'@ | Set-Content `
    -Path $matchingEnginePath `
    -Encoding UTF8

$testsPath = Join-Path `
    $root `
    "src\classification_v2\registry_tests.py"

@'
from __future__ import annotations

from .matching_engine import RegistryMatcher
from .registry.loader import (
    get_registry,
    get_rules,
    registry_summary,
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
    registry = get_registry()
    summary = registry_summary()

    assert_true(
        len(registry) >= 30,
        "Registry should contain at least 30 rules",
    )

    assert_equal(
        summary["total"],
        len(registry),
        "Registry summary total",
    )

    assert_true(
        len(get_rules("league")) >= 20,
        "Expected at least 20 league rules",
    )

    assert_true(
        len(get_rules("sport")) >= 10,
        "Expected at least 10 sport rules",
    )

    matcher = RegistryMatcher()

    premier = matcher.match(
        "English Premier League winner",
        "league",
    )

    assert_equal(
        premier.value,
        "Premier League",
        "Premier League match",
    )

    assert_equal(
        premier.sport,
        "Soccer",
        "Premier League sport",
    )

    assert_true(
        premier.confidence >= 0.95,
        "Premier League confidence",
    )

    ufc = matcher.match(
        "UFC Fight Night main event",
        "league",
    )

    assert_equal(
        ufc.value,
        "UFC",
        "UFC match",
    )

    assert_equal(
        ufc.sport,
        "MMA",
        "UFC sport",
    )

    nba = matcher.match(
        "NBA Finals winner",
        "league",
    )

    assert_equal(
        nba.value,
        "NBA",
        "NBA match",
    )

    assert_equal(
        nba.sport,
        "Basketball",
        "NBA sport",
    )

    formula_one = matcher.match(
        "Formula 1 Canadian Grand Prix winner",
        "league",
    )

    assert_equal(
        formula_one.value,
        "Formula 1",
        "Formula 1 match",
    )

    unknown = matcher.match(
        "France vs Spain under 2.5 goals",
        "league",
    )

    assert_equal(
        unknown.value,
        None,
        "Unknown league",
    )

    assert_true(
        unknown.confidence <= 0.20,
        "Unknown confidence",
    )

    invalid_type = matcher.match(
        "NBA Finals",
        "market_type",
    )

    assert_equal(
        invalid_type.value,
        None,
        "Unregistered rule type",
    )

    print(
        "Registry + matching engine tests passed: 16"
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
    registry_summary,
)
from classification_v2.registry_tests import (
    run_tests,
)


VERSION = "2.2.0-registry-engine"


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
        "--summary",
        action="store_true",
    )

    parser.add_argument(
        "--type",
    )

    parser.add_argument(
        "--title",
    )

    args = parser.parse_args()

    if args.self_test:
        run_tests()
        return

    if args.summary:
        result = registry_summary()
        result["module_version"] = VERSION

        print(
            json.dumps(
                result,
                indent=2,
            )
        )

        return

    if not args.type or not args.title:
        parser.error(
            "--type and --title are required unless "
            "--self-test or --summary is used"
        )

    matcher = RegistryMatcher()

    result = asdict(
        matcher.match(
            args.title,
            args.type,
        )
    )

    result["module_version"] = VERSION

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
'@ | Set-Content `
    -Path $cliPath `
    -Encoding UTF8

$runnerPath = Join-Path `
    $root `
    "run_classification_v2_registry.ps1"

@'
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent `
    $MyInvocation.MyCommand.Path

Set-Location $projectRoot

python `
    .\src\classification_v2_registry_cli.py `
    @args

exit $LASTEXITCODE
'@ | Set-Content `
    -Path $runnerPath `
    -Encoding UTF8

$compileFiles = @(
    (Join-Path $registryDirectory "__init__.py"),
    (Join-Path $registryDirectory "models.py"),
    (Join-Path $registryDirectory "sports.py"),
    (Join-Path $registryDirectory "leagues.py"),
    (Join-Path $registryDirectory "loader.py"),
    $matchingEnginePath,
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

Write-Host ""
Write-Host "Running registry and matching-engine tests..."

& $runnerPath --self-test

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "Registry tests failed. Previous files restored."
}

Write-Host ""
Write-Host "Running registry summary..."

& $runnerPath --summary

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "Registry summary failed. Previous files restored."
}

Write-Host ""
Write-Host "Running sample registry match..."

& $runnerPath `
    --type league `
    --title "English Premier League winner"

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "Sample registry match failed. Previous files restored."
}

Write-Host ""
Write-Host ("=" * 108)
Write-Host `
    "CLASSIFICATION v2 SHARED REGISTRY + MATCHING ENGINE INSTALLED"
Write-Host ("=" * 108)

Write-Host "Version:          2.2.0-registry-engine"
Write-Host `
    "Registry:         src\classification_v2\registry"
Write-Host `
    "Matcher:          src\classification_v2\matching_engine.py"
Write-Host `
    "Tests:            src\classification_v2\registry_tests.py"
Write-Host `
    "CLI:              src\classification_v2_registry_cli.py"
Write-Host `
    "Runner:           run_classification_v2_registry.ps1"
Write-Host "Backup folder:    $backup"
Write-Host "Compile checks:   PASSED"
Write-Host "Unit tests:       PASSED"
Write-Host "Database writes:  NONE"
Write-Host "Phase 1:          NOT MODIFIED"
Write-Host "Phase 2A:         NOT MODIFIED"
Write-Host "Orchestrator:     NOT ENABLED"

Write-Host ""
Write-Host "Re-run tests:"
Write-Host `
    ".\run_classification_v2_registry.ps1 --self-test"

Write-Host ""
Write-Host "Show registry summary:"
Write-Host `
    ".\run_classification_v2_registry.ps1 --summary"

Write-Host ""
Write-Host "Test a registry match:"
Write-Host `
    '.\run_classification_v2_registry.ps1 --type league --title "NBA Finals winner"'

Write-Host ("=" * 108)