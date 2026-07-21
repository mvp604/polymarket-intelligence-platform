$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $root "backups\classification_v2_phase1_$timestamp"

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

$targets = @(
    "src\classification_v2",
    "src\classification_v2_cli.py",
    "src\classification_v2_phase1.manifest.json",
    "run_market_classifier_v2_phase1.ps1"
)

foreach ($target in $targets) {
    $fullPath = Join-Path $root $target
    if (Test-Path $fullPath) {
        $destination = Join-Path $backupRoot $target
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item $fullPath $destination -Recurse -Force
    }
}

Write-Host ""
Write-Host "Installing Market Classification Engine v2 Phase 1..."

$path = Join-Path $root "src\classification_v2\__init__.py"
New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
@'
"""Market Classification Engine v2 package."""

'@ | Set-Content -Path $path -Encoding UTF8


$path = Join-Path $root "src\classification_v2\parser.py"
New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
@'
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedTitle:
    original: str
    normalized: str
    tokens: tuple[str, ...]


def normalize_title(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(value: str) -> tuple[str, ...]:
    normalized = normalize_title(value).lower()
    return tuple(re.findall(r"[a-z0-9$%+.:-]+", normalized))


def parse_title(value: str) -> ParsedTitle:
    normalized = normalize_title(value)
    return ParsedTitle(
        original=value or "",
        normalized=normalized,
        tokens=tokenize(normalized),
    )

'@ | Set-Content -Path $path -Encoding UTF8


$path = Join-Path $root "src\classification_v2\taxonomy.py"
New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
@'
from __future__ import annotations

PRIMARY_CATEGORIES = (
    "Sports",
    "Politics",
    "Crypto",
    "Economics",
    "Finance",
    "Technology",
    "Entertainment",
    "World Events",
    "Science",
    "Other",
)

SPORTS = (
    "Soccer",
    "Basketball",
    "Baseball",
    "American Football",
    "MMA",
    "Tennis",
    "Ice Hockey",
    "Golf",
    "Motorsport",
    "Cricket",
    "Boxing",
    "Esports",
)

CLASSIFIER_VERSION = "2.0.0-phase1"

'@ | Set-Content -Path $path -Encoding UTF8


$path = Join-Path $root "src\classification_v2\models.py"
New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
@'
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Detection:
    label: str | None
    confidence: float
    evidence: tuple[str, ...]
    method: str

    def validate(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Invalid confidence: {self.confidence}")
        if self.label is None and self.confidence > 0.5:
            raise ValueError("Unknown labels cannot have high confidence.")

'@ | Set-Content -Path $path -Encoding UTF8


$path = Join-Path $root "src\classification_v2\category_detector.py"
New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
@'
from __future__ import annotations

import re
from .models import Detection
from .parser import ParsedTitle


RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Politics", (
        r"\belection\b", r"\bpresident\b", r"\bnomination\b", r"\bgop\b",
        r"\brepublican\b", r"\bdemocrat\b", r"\bsenate\b", r"\bcongress\b",
        r"\bgovernor\b", r"\bprime minister\b", r"\bparliament\b",
    )),
    ("Crypto", (
        r"\bbitcoin\b", r"\bbtc\b", r"\bethereum\b", r"\beth\b",
        r"\bsolana\b", r"\bcrypto\b", r"\btoken\b", r"\bdefi\b",
        r"\bstablecoin\b", r"\bblockchain\b",
    )),
    ("Economics", (
        r"\bfederal reserve\b", r"\bfed\b", r"\binterest rates?\b",
        r"\binflation\b", r"\bcpi\b", r"\bgdp\b", r"\bunemployment\b",
        r"\brecession\b", r"\bjobs report\b",
    )),
    ("Finance", (
        r"\bs&p 500\b", r"\bspy\b", r"\bnasdaq\b", r"\bdow jones\b",
        r"\bstock price\b", r"\bmarket cap\b", r"\bipo\b", r"\bearnings\b",
    )),
    ("Technology", (
        r"\bopenai\b", r"\bartificial intelligence\b", r"\bai model\b",
        r"\bmicrosoft\b", r"\bgoogle\b", r"\bapple\b", r"\bmeta\b",
        r"\bspacex\b", r"\bsemiconductor\b",
    )),
    ("Entertainment", (
        r"\boscar\b", r"\bemmy\b", r"\bgrammy\b", r"\bbox office\b",
        r"\bmovie\b", r"\btelevision\b", r"\bcelebrity\b", r"\balbum\b",
    )),
    ("World Events", (
        r"\bceasefire\b", r"\binvasion\b", r"\bsanctions?\b", r"\bnato\b",
        r"\bunited nations\b", r"\btreaty\b", r"\bwar\b",
    )),
    ("Science", (
        r"\bnasa\b", r"\bspace mission\b", r"\bvaccine\b",
        r"\bpandemic\b", r"\bclinical trial\b",
    )),
)


def detect_category(parsed: ParsedTitle) -> Detection:
    text = parsed.normalized.lower()
    evidence: list[str] = []

    for label, patterns in RULES:
        evidence.clear()
        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                evidence.append(f"matched:{pattern}")
        if evidence:
            confidence = min(0.70 + 0.08 * (len(evidence) - 1), 0.98)
            result = Detection(label, confidence, tuple(evidence), "category_rules_v2")
            result.validate()
            return result

    result = Detection("Other", 0.25, ("no-category-rule-match",), "category_fallback_v2")
    result.validate()
    return result

'@ | Set-Content -Path $path -Encoding UTF8


$path = Join-Path $root "src\classification_v2\sport_detector.py"
New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
@'
from __future__ import annotations

import re
from .models import Detection
from .parser import ParsedTitle


RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Soccer", (
        r"\bfifa\b", r"\bworld cup\b", r"\buefa\b", r"\bchampions league\b",
        r"\bpremier league\b", r"\bla liga\b", r"\bserie a\b",
        r"\bbundesliga\b", r"\bligue 1\b", r"\bmls\b", r"\bsoccer\b",
        r"\bbtts\b", r"\bclean sheet\b", r"\bexact score\b",
        r"\b(?:vs\.?|v\.?)\b.*\bgoals?\b",
        r"\bgoals?\b.*\b(?:vs\.?|v\.?)\b",
        r"\b(?:vs\.?|v\.?)\b.*\bcorners?\b",
        r"\b(?:vs\.?|v\.?)\b.*\bto qualify\b",
    )),
    ("Basketball", (
        r"\bnba\b", r"\bwnba\b", r"\beuroleague\b", r"\bbasketball\b",
        r"\bncaab\b", r"\bmarch madness\b",
    )),
    ("Baseball", (
        r"\bmlb\b", r"\bbaseball\b", r"\bworld series\b",
    )),
    ("American Football", (
        r"\bnfl\b", r"\bsuper bowl\b", r"\bcollege football\b", r"\bncaaf\b",
    )),
    ("MMA", (
        r"\bufc\b", r"\bmma\b", r"\bbellator\b", r"\bpfl\b", r"\bfight night\b",
    )),
    ("Tennis", (
        r"\btennis\b", r"\bwimbledon\b", r"\bus open\b",
        r"\baustralian open\b", r"\bfrench open\b", r"\batp\b", r"\bwta\b",
    )),
    ("Ice Hockey", (
        r"\bnhl\b", r"\bstanley cup\b", r"\bice hockey\b",
    )),
    ("Golf", (
        r"\bpga\b", r"\bliv golf\b", r"\bmasters tournament\b",
        r"\bthe open\b", r"\bgolf\b",
    )),
    ("Motorsport", (
        r"\bformula 1\b", r"\bf1\b", r"\bnascar\b",
        r"\bindycar\b", r"\bgrand prix\b",
    )),
    ("Cricket", (
        r"\bipl\b", r"\bcricket\b", r"\bt20\b", r"\btest match\b",
    )),
    ("Boxing", (
        r"\bboxing\b", r"\bheavyweight\b", r"\bknockout\b",
    )),
    ("Esports", (
        r"\besports\b", r"\bleague of legends\b", r"\bvalorant\b",
        r"\bdota\b", r"\bcounter-strike\b", r"\bcs2\b",
    )),
)


def detect_sport(parsed: ParsedTitle) -> Detection:
    text = parsed.normalized.lower()

    best_label: str | None = None
    best_evidence: list[str] = []

    for label, patterns in RULES:
        evidence = [
            f"matched:{pattern}"
            for pattern in patterns
            if re.search(pattern, text, flags=re.IGNORECASE)
        ]
        if len(evidence) > len(best_evidence):
            best_label = label
            best_evidence = evidence

    if best_label:
        confidence = min(0.72 + 0.07 * (len(best_evidence) - 1), 0.99)
        result = Detection(
            best_label,
            confidence,
            tuple(best_evidence),
            "sport_rules_v2",
        )
        result.validate()
        return result

    result = Detection(None, 0.15, ("no-sport-rule-match",), "sport_fallback_v2")
    result.validate()
    return result

'@ | Set-Content -Path $path -Encoding UTF8


$path = Join-Path $root "src\classification_v2\classifier.py"
New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
@'
from __future__ import annotations

from dataclasses import dataclass

from .category_detector import detect_category
from .models import Detection
from .parser import parse_title
from .sport_detector import detect_sport


@dataclass(frozen=True)
class Phase1Classification:
    title: str
    normalized_title: str
    category: Detection
    sport: Detection


def classify_phase1(title: str) -> Phase1Classification:
    parsed = parse_title(title)
    sport = detect_sport(parsed)
    category = detect_category(parsed)

    if sport.label is not None:
        category = Detection(
            label="Sports",
            confidence=max(0.90, sport.confidence),
            evidence=("sport-detected", *sport.evidence),
            method="sport_override_v2",
        )

    category.validate()
    sport.validate()

    return Phase1Classification(
        title=title,
        normalized_title=parsed.normalized,
        category=category,
        sport=sport,
    )

'@ | Set-Content -Path $path -Encoding UTF8


$path = Join-Path $root "src\classification_v2\tests.py"
New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
@'
from __future__ import annotations

from .classifier import classify_phase1
from .parser import normalize_title, tokenize


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def run_tests() -> None:
    assert_equal(
        normalize_title("  France   vs Spain — Under 2.5 Goals  "),
        "France vs Spain - Under 2.5 Goals",
        "title normalization",
    )

    assert_equal(
        tokenize("Will Bitcoin be above $150,000 by December 2026?")[0],
        "will",
        "tokenization",
    )

    cases = [
        (
            "Will Spain win the 2026 FIFA World Cup?",
            "Sports",
            "Soccer",
        ),
        (
            "France vs Spain: Under 2.5 Goals",
            "Sports",
            "Soccer",
        ),
        (
            "Will Marco Rubio win the 2028 GOP nomination?",
            "Politics",
            None,
        ),
        (
            "Will Bitcoin be above $150,000 by December 2026?",
            "Crypto",
            None,
        ),
        (
            "Will the Fed cut interest rates in September?",
            "Economics",
            None,
        ),
        (
            "Will an NBA team win 70 games?",
            "Sports",
            "Basketball",
        ),
        (
            "UFC Fight Night: Fighter A vs Fighter B",
            "Sports",
            "MMA",
        ),
    ]

    for title, expected_category, expected_sport in cases:
        result = classify_phase1(title)
        assert_equal(
            result.category.label,
            expected_category,
            f"category for {title}",
        )
        assert_equal(
            result.sport.label,
            expected_sport,
            f"sport for {title}",
        )

    print(f"Phase 1 tests passed: {len(cases) + 2}")


if __name__ == "__main__":
    run_tests()

'@ | Set-Content -Path $path -Encoding UTF8


$path = Join-Path $root "src\classification_v2_cli.py"
New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
@'
from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from classification_v2.classifier import classify_phase1
from classification_v2.tests import run_tests
from classification_v2.taxonomy import CLASSIFIER_VERSION


def main() -> None:
    parser = argparse.ArgumentParser(description="Market Classification Engine v2 Phase 1")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--title")
    args = parser.parse_args()

    if args.self_test:
        run_tests()
        return

    if not args.title:
        parser.error("--title is required unless --self-test is used")

    result = classify_phase1(args.title)
    payload = asdict(result)
    payload["classifier_version"] = CLASSIFIER_VERSION
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

'@ | Set-Content -Path $path -Encoding UTF8


$path = Join-Path $root "run_market_classifier_v2_phase1.ps1"
New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
@'
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot
python .\src\classification_v2_cli.py @args
exit $LASTEXITCODE

'@ | Set-Content -Path $path -Encoding UTF8


$path = Join-Path $root "src\classification_v2_phase1.manifest.json"
New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
@'
{
  "id": "market_classifier_v2_phase1",
  "name": "Market Classification Engine v2 Phase 1",
  "version": "2.0.0-phase1",
  "runner": "run_market_classifier_v2_phase1.ps1",
  "enabled": false,
  "required": false,
  "stage": "development",
  "order": 40,
  "dependencies": [],
  "latest_report": null,
  "timeout_seconds": 300
}
'@ | Set-Content -Path $path -Encoding UTF8


$cli = Join-Path $root "src\classification_v2_cli.py"
$runner = Join-Path $root "run_market_classifier_v2_phase1.ps1"

Write-Host ""
Write-Host "Running compile checks..."
python -m py_compile `
    (Join-Path $root "src\classification_v2\parser.py") `
    (Join-Path $root "src\classification_v2\taxonomy.py") `
    (Join-Path $root "src\classification_v2\models.py") `
    (Join-Path $root "src\classification_v2\category_detector.py") `
    (Join-Path $root "src\classification_v2\sport_detector.py") `
    (Join-Path $root "src\classification_v2\classifier.py") `
    (Join-Path $root "src\classification_v2\tests.py") `
    $cli

if ($LASTEXITCODE -ne 0) {
    throw "Compile check failed."
}

Write-Host "Compile checks passed."

Write-Host ""
Write-Host "Running Phase 1 unit tests..."
& $runner --self-test
if ($LASTEXITCODE -ne 0) {
    throw "Phase 1 unit tests failed."
}

Write-Host ""
Write-Host "Running sample classifications..."
& $runner --title "France vs Spain: Under 2.5 Goals"
if ($LASTEXITCODE -ne 0) {
    throw "Sample soccer classification failed."
}

& $runner --title "Will Bitcoin be above `$150,000 by December 2026?"
if ($LASTEXITCODE -ne 0) {
    throw "Sample crypto classification failed."
}

Write-Host ""
Write-Host ("=" * 110)
Write-Host "MARKET CLASSIFICATION ENGINE v2 - PHASE 1 INSTALLED"
Write-Host ("=" * 110)
Write-Host "Package:        src\classification_v2"
Write-Host "CLI:            src\classification_v2_cli.py"
Write-Host "Runner:         run_market_classifier_v2_phase1.ps1"
Write-Host "Backup folder:  $backupRoot"
Write-Host "Compile checks: PASSED"
Write-Host "Unit tests:     PASSED"
Write-Host "Database writes: NONE"
Write-Host "Orchestrator enabled: NO - Phase 1 is isolated for validation"
Write-Host ""
Write-Host "Re-run tests:"
Write-Host ".\run_market_classifier_v2_phase1.ps1 --self-test"
Write-Host ""
Write-Host "Test any title:"
Write-Host '.\run_market_classifier_v2_phase1.ps1 --title "France vs Spain: Under 2.5 Goals"'
Write-Host ("=" * 110)