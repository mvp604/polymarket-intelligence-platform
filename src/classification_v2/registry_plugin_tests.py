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
