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
