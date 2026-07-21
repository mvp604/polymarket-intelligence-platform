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
