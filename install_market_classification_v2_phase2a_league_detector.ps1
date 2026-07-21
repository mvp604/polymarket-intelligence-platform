$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = Join-Path $root "backups\classification_v2_phase2a_league_$stamp"

if (-not (Test-Path $root)) {
    throw "Project root not found: $root"
}

New-Item -ItemType Directory -Path $backup -Force | Out-Null

$targets = @(
    "src\classification_v2\league_detector.py",
    "src\classification_v2\league_tests.py",
    "src\classification_v2_league_cli.py",
    "run_market_classifier_v2_league.ps1"
)

foreach ($target in $targets) {
    $source = Join-Path $root $target

    if (Test-Path $source) {
        $destination = Join-Path $backup $target

        New-Item `
            -ItemType Directory `
            -Path (Split-Path -Parent $destination) `
            -Force | Out-Null

        Copy-Item $source $destination -Recurse -Force
    }
}

function Restore-Previous {
    Write-Host ""
    Write-Host "Restoring previous files..."

    foreach ($target in $targets) {
        $current = Join-Path $root $target
        $saved = Join-Path $backup $target

        if (Test-Path $current) {
            Remove-Item $current -Recurse -Force
        }

        if (Test-Path $saved) {
            New-Item `
                -ItemType Directory `
                -Path (Split-Path -Parent $current) `
                -Force | Out-Null

            Copy-Item $saved $current -Recurse -Force
        }
    }

    Write-Host "Previous files restored."
}

Write-Host ""
Write-Host "Installing Market Classification v2 Phase 2A - League Detector..."

$detectorPath = Join-Path `
    $root `
    "src\classification_v2\league_detector.py"

New-Item `
    -ItemType Directory `
    -Path (Split-Path -Parent $detectorPath) `
    -Force | Out-Null

@'
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .models import Detection
from .parser import ParsedTitle, parse_title


@dataclass(frozen=True)
class LeagueRule:
    label: str
    sport: str
    patterns: tuple[str, ...]
    base_confidence: float


LEAGUE_RULES: tuple[LeagueRule, ...] = (
    LeagueRule(
        "FIFA World Cup",
        "Soccer",
        (r"\bfifa world cup\b", r"\bworld cup\b"),
        0.94,
    ),
    LeagueRule(
        "UEFA Champions League",
        "Soccer",
        (
            r"\buefa champions league\b",
            r"\bchampions league\b",
            r"\bucl\b",
        ),
        0.95,
    ),
    LeagueRule(
        "UEFA Europa League",
        "Soccer",
        (
            r"\buefa europa league\b",
            r"\beuropa league\b",
        ),
        0.95,
    ),
    LeagueRule(
        "Premier League",
        "Soccer",
        (r"\bpremier league\b", r"\bepl\b"),
        0.95,
    ),
    LeagueRule(
        "La Liga",
        "Soccer",
        (r"\bla liga\b",),
        0.96,
    ),
    LeagueRule(
        "Serie A",
        "Soccer",
        (r"\bserie a\b",),
        0.96,
    ),
    LeagueRule(
        "Bundesliga",
        "Soccer",
        (r"\bbundesliga\b",),
        0.96,
    ),
    LeagueRule(
        "Ligue 1",
        "Soccer",
        (r"\bligue 1\b",),
        0.96,
    ),
    LeagueRule(
        "MLS",
        "Soccer",
        (r"\bmls\b", r"\bmajor league soccer\b"),
        0.95,
    ),
    LeagueRule(
        "NBA",
        "Basketball",
        (r"\bnba\b",),
        0.98,
    ),
    LeagueRule(
        "WNBA",
        "Basketball",
        (r"\bwnba\b",),
        0.98,
    ),
    LeagueRule(
        "EuroLeague",
        "Basketball",
        (r"\beuroleague\b",),
        0.97,
    ),
    LeagueRule(
        "NCAA Basketball",
        "Basketball",
        (
            r"\bncaab\b",
            r"\bncaa basketball\b",
            r"\bmarch madness\b",
        ),
        0.94,
    ),
    LeagueRule(
        "MLB",
        "Baseball",
        (
            r"\bmlb\b",
            r"\bmajor league baseball\b",
        ),
        0.98,
    ),
    LeagueRule(
        "NFL",
        "American Football",
        (
            r"\bnfl\b",
            r"\bnational football league\b",
        ),
        0.98,
    ),
    LeagueRule(
        "NCAA Football",
        "American Football",
        (
            r"\bncaaf\b",
            r"\bncaa football\b",
            r"\bcollege football\b",
        ),
        0.94,
    ),
    LeagueRule(
        "NHL",
        "Ice Hockey",
        (
            r"\bnhl\b",
            r"\bnational hockey league\b",
        ),
        0.98,
    ),
    LeagueRule(
        "UFC",
        "MMA",
        (
            r"\bufc\b",
            r"\bufc fight night\b",
        ),
        0.98,
    ),
    LeagueRule(
        "Bellator",
        "MMA",
        (r"\bbellator\b",),
        0.98,
    ),
    LeagueRule(
        "PFL",
        "MMA",
        (
            r"\bpfl\b",
            r"\bprofessional fighters league\b",
        ),
        0.97,
    ),
    LeagueRule(
        "ATP",
        "Tennis",
        (r"\batp\b",),
        0.97,
    ),
    LeagueRule(
        "WTA",
        "Tennis",
        (r"\bwta\b",),
        0.97,
    ),
    LeagueRule(
        "PGA Tour",
        "Golf",
        (
            r"\bpga tour\b",
            r"\bpga\b",
        ),
        0.95,
    ),
    LeagueRule(
        "Formula 1",
        "Motorsport",
        (
            r"\bformula 1\b",
            r"\bf1\b",
        ),
        0.97,
    ),
    LeagueRule(
        "NASCAR",
        "Motorsport",
        (r"\bnascar\b",),
        0.98,
    ),
    LeagueRule(
        "IPL",
        "Cricket",
        (
            r"\bipl\b",
            r"\bindian premier league\b",
        ),
        0.97,
    ),
)


def matching_evidence(
    text: str,
    patterns: Iterable[str],
) -> tuple[str, ...]:
    return tuple(
        f"matched:{pattern}"
        for pattern in patterns
        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
    )


def detect_league(parsed: ParsedTitle) -> Detection:
    text = parsed.normalized.lower()

    best_rule: LeagueRule | None = None
    best_evidence: tuple[str, ...] = ()

    for rule in LEAGUE_RULES:
        evidence = matching_evidence(
            text,
            rule.patterns,
        )

        if len(evidence) > len(best_evidence):
            best_rule = rule
            best_evidence = evidence

    if best_rule is None:
        result = Detection(
            label=None,
            confidence=0.10,
            evidence=("no-explicit-league-match",),
            method="league_fallback_v2",
        )

        result.validate()
        return result

    confidence = min(
        best_rule.base_confidence
        + 0.015 * (len(best_evidence) - 1),
        0.99,
    )

    result = Detection(
        label=best_rule.label,
        confidence=confidence,
        evidence=(
            f"sport:{best_rule.sport}",
            *best_evidence,
        ),
        method="league_rules_v2",
    )

    result.validate()
    return result


def classify_league(title: str) -> Detection:
    return detect_league(
        parse_title(title)
    )
'@ | Set-Content `
    -Path $detectorPath `
    -Encoding UTF8

$testsPath = Join-Path `
    $root `
    "src\classification_v2\league_tests.py"

@'
from __future__ import annotations

from .league_detector import classify_league


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
    cases = (
        (
            "2026 FIFA World Cup Winner",
            "FIFA World Cup",
        ),
        (
            "UEFA Champions League: Real Madrid vs Arsenal",
            "UEFA Champions League",
        ),
        (
            "Premier League: Arsenal vs Chelsea",
            "Premier League",
        ),
        (
            "La Liga: Barcelona vs Real Madrid",
            "La Liga",
        ),
        (
            "NBA Finals Winner",
            "NBA",
        ),
        (
            "WNBA: New York Liberty vs Las Vegas Aces",
            "WNBA",
        ),
        (
            "MLB World Series Winner",
            "MLB",
        ),
        (
            "NFL Super Bowl Winner",
            "NFL",
        ),
        (
            "NHL Stanley Cup Winner",
            "NHL",
        ),
        (
            "UFC Fight Night Main Event",
            "UFC",
        ),
        (
            "Bellator Championship Bout",
            "Bellator",
        ),
        (
            "PFL World Tournament",
            "PFL",
        ),
        (
            "ATP Wimbledon Champion",
            "ATP",
        ),
        (
            "WTA US Open Champion",
            "WTA",
        ),
        (
            "Formula 1 Canadian Grand Prix",
            "Formula 1",
        ),
        (
            "IPL Champion",
            "IPL",
        ),
    )

    for title, expected in cases:
        result = classify_league(title)

        assert_equal(
            result.label,
            expected,
            title,
        )

        assert_true(
            result.confidence >= 0.90,
            f"Low confidence for {title}",
        )

        assert_true(
            len(result.evidence) >= 2,
            f"Missing evidence for {title}",
        )

    unknown = classify_league(
        "France vs Spain: Under 2.5 Goals"
    )

    assert_equal(
        unknown.label,
        None,
        "League must not be invented",
    )

    assert_true(
        unknown.confidence <= 0.20,
        "Unknown league confidence must remain low",
    )

    print(
        f"Phase 2A league tests passed: "
        f"{len(cases) * 3 + 2}"
    )


if __name__ == "__main__":
    run_tests()
'@ | Set-Content `
    -Path $testsPath `
    -Encoding UTF8

$cliPath = Join-Path `
    $root `
    "src\classification_v2_league_cli.py"

@'
from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from classification_v2.league_detector import (
    classify_league,
)
from classification_v2.league_tests import (
    run_tests,
)


VERSION = "2.1.0-phase2a"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Market Classification v2 "
            "Phase 2A League Detector"
        )
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
    )

    parser.add_argument(
        "--title",
    )

    args = parser.parse_args()

    if args.self_test:
        run_tests()
        return

    if not args.title:
        parser.error(
            "--title is required unless "
            "--self-test is supplied"
        )

    result = asdict(
        classify_league(args.title)
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
    "run_market_classifier_v2_league.ps1"

@'
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent `
    $MyInvocation.MyCommand.Path

Set-Location $projectRoot

python `
    .\src\classification_v2_league_cli.py `
    @args

exit $LASTEXITCODE
'@ | Set-Content `
    -Path $runnerPath `
    -Encoding UTF8

Write-Host ""
Write-Host "Running compile checks..."

python -m py_compile `
    $detectorPath `
    $testsPath `
    $cliPath

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "Compile checks failed. Previous files restored."
}

Write-Host "Compile checks passed."

Write-Host ""
Write-Host "Running Phase 2A league tests..."

& $runnerPath --self-test

if ($LASTEXITCODE -ne 0) {
    Restore-Previous

    throw `
        "League tests failed. Previous files restored."
}

Write-Host ""
Write-Host "Running sample classifications..."

& $runnerPath `
    --title `
    "2026 FIFA World Cup Winner"

if ($LASTEXITCODE -ne 0) {
    Restore-Previous
    throw "FIFA World Cup sample failed."
}

& $runnerPath `
    --title `
    "UFC Fight Night Main Event"

if ($LASTEXITCODE -ne 0) {
    Restore-Previous
    throw "UFC sample failed."
}

& $runnerPath `
    --title `
    "France vs Spain: Under 2.5 Goals"

if ($LASTEXITCODE -ne 0) {
    Restore-Previous
    throw "Unknown-league sample failed."
}

Write-Host ""
Write-Host ("=" * 108)
Write-Host `
    "MARKET CLASSIFICATION v2 - PHASE 2A LEAGUE DETECTOR INSTALLED"
Write-Host ("=" * 108)

Write-Host "Version:          2.1.0-phase2a"
Write-Host `
    "Detector:         src\classification_v2\league_detector.py"
Write-Host `
    "Tests:            src\classification_v2\league_tests.py"
Write-Host `
    "CLI:              src\classification_v2_league_cli.py"
Write-Host `
    "Runner:           run_market_classifier_v2_league.ps1"
Write-Host "Backup folder:    $backup"
Write-Host "Compile checks:   PASSED"
Write-Host "Unit tests:       PASSED"
Write-Host "Database writes:  NONE"
Write-Host "Main classifier:  NOT MODIFIED"
Write-Host "Orchestrator:     NOT ENABLED"

Write-Host ""
Write-Host "Re-run tests:"
Write-Host `
    ".\run_market_classifier_v2_league.ps1 --self-test"

Write-Host ""
Write-Host "Test a title:"
Write-Host `
    '.\run_market_classifier_v2_league.ps1 --title "Premier League: Arsenal vs Chelsea"'

Write-Host ("=" * 108)