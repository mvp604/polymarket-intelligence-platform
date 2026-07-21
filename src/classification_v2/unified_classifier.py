from __future__ import annotations

from dataclasses import dataclass

from .classifier import classify_phase1
from .confidence import aggregate_confidence
from .matching_engine import MatchResult, RegistryMatcher


AVAILABLE_COMPONENTS = {
    "category",
    "sport",
    "league",
    "market_type",
}


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
    component_confidences: dict[str, float]
    evidence: dict[str, tuple[str, ...]]
    rule_ids: dict[str, str | None]


def _best_category(
    matches: tuple[MatchResult, ...],
) -> tuple[str | None, float, tuple[str, ...]]:
    candidates = [
        match
        for match in matches
        if match.value is not None
        and match.category is not None
    ]

    if not candidates:
        return None, 0.0, ()

    best = max(
        candidates,
        key=lambda match: match.confidence,
    )

    return (
        best.category,
        best.confidence,
        best.evidence,
    )


def _best_sport(
    matches: tuple[MatchResult, ...],
) -> tuple[str | None, float, tuple[str, ...]]:
    candidates: list[
        tuple[str, float, tuple[str, ...]]
    ] = []

    for match in matches:
        if match.value is None:
            continue

        if match.rule_type == "sport":
            candidates.append(
                (
                    match.value,
                    match.confidence,
                    match.evidence,
                )
            )

        elif match.sport is not None:
            candidates.append(
                (
                    match.sport,
                    match.confidence,
                    match.evidence,
                )
            )

    if not candidates:
        return None, 0.0, ()

    return max(
        candidates,
        key=lambda candidate: candidate[1],
    )


class UnifiedClassifier:
    def __init__(
        self,
        matcher: RegistryMatcher | None = None,
    ) -> None:
        self.matcher = matcher or RegistryMatcher()

    def classify(
        self,
        title: str,
    ) -> UnifiedClassification:
        phase1 = classify_phase1(title)

        sport_match = self.matcher.match(
            title,
            "sport",
        )

        league_match = self.matcher.match(
            title,
            "league",
        )

        market_type_match = self.matcher.match(
            title,
            "market_type",
        )

        matches = (
            sport_match,
            league_match,
            market_type_match,
        )

        (
            registry_category,
            registry_category_confidence,
            registry_category_evidence,
        ) = _best_category(matches)

        (
            registry_sport,
            registry_sport_confidence,
            registry_sport_evidence,
        ) = _best_sport(matches)

        category = (
            registry_category
            or phase1.category.label
        )

        sport = (
            registry_sport
            or phase1.sport.label
        )

        if sport is not None:
            category = "Sports"

        league = league_match.value
        market_type = market_type_match.value

        component_confidences: dict[str, float] = {}
        evidence: dict[str, tuple[str, ...]] = {}

        if category is not None:
            component_confidences["category"] = max(
                phase1.category.confidence,
                registry_category_confidence,
            )

            evidence["category"] = tuple(
                dict.fromkeys(
                    (
                        *phase1.category.evidence,
                        *registry_category_evidence,
                    )
                )
            )

        if sport is not None:
            component_confidences["sport"] = max(
                phase1.sport.confidence,
                registry_sport_confidence,
            )

            evidence["sport"] = tuple(
                dict.fromkeys(
                    (
                        *phase1.sport.evidence,
                        *registry_sport_evidence,
                    )
                )
            )

        if league is not None:
            component_confidences["league"] = (
                league_match.confidence
            )

            evidence["league"] = (
                league_match.evidence
            )

        if market_type is not None:
            component_confidences["market_type"] = (
                market_type_match.confidence
            )

            evidence["market_type"] = (
                market_type_match.evidence
            )

        confidence, coverage = aggregate_confidence(
            component_confidences,
            AVAILABLE_COMPONENTS,
        )

        return UnifiedClassification(
            title=title,
            normalized_title=phase1.normalized_title,
            category=category,
            sport=sport,
            league=league,
            market_type=market_type,
            event_type=None,
            confidence=confidence,
            coverage=coverage,
            matched_components=len(
                component_confidences
            ),
            component_confidences=(
                component_confidences
            ),
            evidence=evidence,
            rule_ids={
                "sport": sport_match.rule_id,
                "league": league_match.rule_id,
                "market_type": (
                    market_type_match.rule_id
                ),
                "event_type": None,
            },
        )


def classify_market(
    title: str,
) -> UnifiedClassification:
    return UnifiedClassifier().classify(title)
