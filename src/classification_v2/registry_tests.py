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
