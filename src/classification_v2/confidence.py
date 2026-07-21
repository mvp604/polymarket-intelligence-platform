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
    """
    Calculate how much of the available classification registry
    produced a successful match.
    """

    if not available_rule_types:
        return 0.0

    matched_available_types = (
        matched_rule_types.intersection(
            available_rule_types
        )
    )

    coverage = (
        len(matched_available_types)
        / len(available_rule_types)
    )

    return round(coverage, 4)


def aggregate_confidence(
    component_confidences: dict[str, float],
    available_rule_types: set[str],
) -> tuple[float, float]:
    """
    Combine individual registry match confidence scores into one
    unified confidence score.

    Returns:
        unified_confidence
        coverage
    """

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

    final_confidence = (
        weighted_average
        * coverage_multiplier
    )

    final_confidence = min(
        max(final_confidence, 0.10),
        0.99,
    )

    return round(final_confidence, 4), coverage