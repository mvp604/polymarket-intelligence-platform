from __future__ import annotations

from .unified_classifier import classify_market


def run_tests() -> None:
    checks = 0

    nba = classify_market(
        "NBA Finals moneyline"
    )

    assert nba.category == "Sports"
    checks += 1

    assert nba.sport == "Basketball"
    checks += 1

    assert nba.league == "NBA"
    checks += 1

    assert nba.market_type == "Moneyline"
    checks += 1

    assert nba.coverage == 1.0
    checks += 1

    btts = classify_market(
        "France vs Spain both teams to score"
    )

    assert btts.category == "Sports"
    checks += 1

    assert btts.sport == "Soccer"
    checks += 1

    assert btts.market_type == (
        "Both Teams to Score"
    )
    checks += 1

    bitcoin = classify_market(
        "Bitcoin price target of $150000"
    )

    assert bitcoin.category == "Finance"
    checks += 1

    assert bitcoin.sport is None
    checks += 1

    assert bitcoin.market_type == "Price Target"
    checks += 1

    assert bitcoin.rule_ids["market_type"] == (
        "market_type.price_target"
    )
    checks += 1

    election = classify_market(
        "2028 presidential election winner"
    )

    assert election.market_type == (
        "Election Winner"
    )
    checks += 1

    unknown = classify_market(
        "Completely unknown market wording"
    )

    assert unknown.event_type is None
    checks += 1

    assert 0.0 <= unknown.coverage <= 1.0
    checks += 1

    assert 0.0 <= unknown.confidence <= 0.99
    checks += 1

    assert isinstance(unknown.evidence, dict)
    checks += 1

    assert isinstance(unknown.rule_ids, dict)
    checks += 1

    print(
        f"Unified classifier tests passed: {checks}"
    )


if __name__ == "__main__":
    run_tests()
