from __future__ import annotations

from .classifier import classify_phase1
from .parser import normalize_title, tokenize


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def run_tests() -> None:
    assert_equal(
        normalize_title("  France   vs Spain â€” Under 2.5 Goals  "),
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

