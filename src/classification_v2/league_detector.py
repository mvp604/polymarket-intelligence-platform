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
