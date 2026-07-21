from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Final


CONFIG_VERSION: Final[str] = "2.1"


@dataclass(frozen=True)
class DecisionThresholds:
    buy_score: float
    buy_actionability: float
    buy_confidence: float
    buy_entry: float
    buy_structure: float
    buy_trust: float
    buy_wallet_count: int
    buy_data_quality: float

    watch_score: float
    watch_actionability: float
    watch_confidence: float

    wait_score: float
    wait_confidence: float
    wait_entry_ceiling: float

    avoid_score: float


@dataclass(frozen=True)
class ScoringProfile:
    name: str
    weights: dict[str, float]
    thresholds: DecisionThresholds


DEFAULT_WEIGHTS: Final[dict[str, float]] = {
    "master": 0.18,
    "consensus": 0.18,
    "wallet": 0.14,
    "trust": 0.12,
    "entry": 0.14,
    "structure": 0.08,
    "evolution": 0.07,
    "timing": 0.05,
    "data": 0.04,
}


SPORTS_WEIGHTS: Final[dict[str, float]] = {
    "master": 0.16,
    "consensus": 0.19,
    "wallet": 0.15,
    "trust": 0.12,
    "entry": 0.15,
    "structure": 0.08,
    "evolution": 0.07,
    "timing": 0.05,
    "data": 0.03,
}


POLITICS_WEIGHTS: Final[dict[str, float]] = {
    "master": 0.20,
    "consensus": 0.18,
    "wallet": 0.12,
    "trust": 0.14,
    "entry": 0.12,
    "structure": 0.08,
    "evolution": 0.07,
    "timing": 0.04,
    "data": 0.05,
}


CRYPTO_WEIGHTS: Final[dict[str, float]] = {
    "master": 0.16,
    "consensus": 0.17,
    "wallet": 0.14,
    "trust": 0.13,
    "entry": 0.15,
    "structure": 0.08,
    "evolution": 0.08,
    "timing": 0.05,
    "data": 0.04,
}


MACRO_WEIGHTS: Final[dict[str, float]] = {
    "master": 0.19,
    "consensus": 0.17,
    "wallet": 0.12,
    "trust": 0.13,
    "entry": 0.13,
    "structure": 0.08,
    "evolution": 0.07,
    "timing": 0.05,
    "data": 0.06,
}


DEFAULT_THRESHOLDS: Final[DecisionThresholds] = (
    DecisionThresholds(
        buy_score=78.0,
        buy_actionability=72.0,
        buy_confidence=62.0,
        buy_entry=65.0,
        buy_structure=55.0,
        buy_trust=46.0,
        buy_wallet_count=2,
        buy_data_quality=55.0,

        watch_score=68.0,
        watch_actionability=58.0,
        watch_confidence=50.0,

        wait_score=61.0,
        wait_confidence=42.0,
        wait_entry_ceiling=62.0,

        avoid_score=43.0,
    )
)


SPORTS_THRESHOLDS: Final[DecisionThresholds] = (
    DecisionThresholds(
        buy_score=76.0,
        buy_actionability=70.0,
        buy_confidence=60.0,
        buy_entry=64.0,
        buy_structure=54.0,
        buy_trust=45.0,
        buy_wallet_count=2,
        buy_data_quality=52.0,

        watch_score=67.0,
        watch_actionability=57.0,
        watch_confidence=48.0,

        wait_score=60.0,
        wait_confidence=40.0,
        wait_entry_ceiling=62.0,

        avoid_score=42.0,
    )
)


POLITICS_THRESHOLDS: Final[DecisionThresholds] = (
    DecisionThresholds(
        buy_score=80.0,
        buy_actionability=72.0,
        buy_confidence=64.0,
        buy_entry=64.0,
        buy_structure=57.0,
        buy_trust=50.0,
        buy_wallet_count=3,
        buy_data_quality=60.0,

        watch_score=70.0,
        watch_actionability=59.0,
        watch_confidence=54.0,

        wait_score=63.0,
        wait_confidence=46.0,
        wait_entry_ceiling=61.0,

        avoid_score=44.0,
    )
)


CRYPTO_THRESHOLDS: Final[DecisionThresholds] = (
    DecisionThresholds(
        buy_score=81.0,
        buy_actionability=74.0,
        buy_confidence=65.0,
        buy_entry=68.0,
        buy_structure=60.0,
        buy_trust=50.0,
        buy_wallet_count=3,
        buy_data_quality=58.0,

        watch_score=71.0,
        watch_actionability=60.0,
        watch_confidence=54.0,

        wait_score=63.0,
        wait_confidence=45.0,
        wait_entry_ceiling=64.0,

        avoid_score=44.0,
    )
)


MACRO_THRESHOLDS: Final[DecisionThresholds] = (
    DecisionThresholds(
        buy_score=79.0,
        buy_actionability=72.0,
        buy_confidence=64.0,
        buy_entry=65.0,
        buy_structure=57.0,
        buy_trust=48.0,
        buy_wallet_count=2,
        buy_data_quality=60.0,

        watch_score=69.0,
        watch_actionability=59.0,
        watch_confidence=52.0,

        wait_score=62.0,
        wait_confidence=44.0,
        wait_entry_ceiling=62.0,

        avoid_score=44.0,
    )
)


PROFILES: Final[dict[str, ScoringProfile]] = {
    "DEFAULT": ScoringProfile(
        name="DEFAULT",
        weights=DEFAULT_WEIGHTS,
        thresholds=DEFAULT_THRESHOLDS,
    ),
    "SPORTS": ScoringProfile(
        name="SPORTS",
        weights=SPORTS_WEIGHTS,
        thresholds=SPORTS_THRESHOLDS,
    ),
    "POLITICS": ScoringProfile(
        name="POLITICS",
        weights=POLITICS_WEIGHTS,
        thresholds=POLITICS_THRESHOLDS,
    ),
    "CRYPTO": ScoringProfile(
        name="CRYPTO",
        weights=CRYPTO_WEIGHTS,
        thresholds=CRYPTO_THRESHOLDS,
    ),
    "MACRO": ScoringProfile(
        name="MACRO",
        weights=MACRO_WEIGHTS,
        thresholds=MACRO_THRESHOLDS,
    ),
}


SPORTS_TERMS: Final[tuple[str, ...]] = (
    "sport",
    "soccer",
    "football",
    "basketball",
    "baseball",
    "hockey",
    "tennis",
    "mma",
    "ufc",
    "boxing",
    "cricket",
    "esports",
    "world cup",
    "nba",
    "nfl",
    "nhl",
    "mlb",
    "wnba",
    "champions league",
    "premier league",
    "la liga",
)


POLITICS_TERMS: Final[tuple[str, ...]] = (
    "politic",
    "election",
    "president",
    "presidential",
    "nomination",
    "congress",
    "senate",
    "governor",
    "parliament",
    "prime minister",
    "republican",
    "democrat",
)


CRYPTO_TERMS: Final[tuple[str, ...]] = (
    "crypto",
    "bitcoin",
    "ethereum",
    "solana",
    "token",
    "blockchain",
    "btc",
    "eth",
)


MACRO_TERMS: Final[tuple[str, ...]] = (
    "macro",
    "inflation",
    "cpi",
    "interest rate",
    "fed",
    "federal reserve",
    "gdp",
    "unemployment",
    "recession",
    "treasury",
)


def validate_weights(
    weights: dict[str, float],
) -> None:
    expected_components = {
        "master",
        "consensus",
        "wallet",
        "trust",
        "entry",
        "structure",
        "evolution",
        "timing",
        "data",
    }

    missing = expected_components - set(weights)
    extra = set(weights) - expected_components

    if missing:
        raise ValueError(
            "Scoring profile is missing weights: "
            + ", ".join(sorted(missing))
        )

    if extra:
        raise ValueError(
            "Scoring profile has unknown weights: "
            + ", ".join(sorted(extra))
        )

    total = sum(weights.values())

    if abs(total - 1.0) > 0.000001:
        raise ValueError(
            f"Scoring weights must total 1.0, not {total:.6f}."
        )

    for component, weight in weights.items():
        if weight < 0:
            raise ValueError(
                f"Weight cannot be negative: "
                f"{component}={weight}"
            )


def validate_profiles() -> None:
    for profile in PROFILES.values():
        validate_weights(profile.weights)


def term_matches(
    combined: str,
    term: str,
) -> bool:
    normalized_term = term.strip().lower()

    if not normalized_term:
        return False

    pattern = (
        r"(?<![a-z0-9])"
        + re.escape(normalized_term)
        + r"(?![a-z0-9])"
    )

    return (
        re.search(
            pattern,
            combined,
            flags=re.IGNORECASE,
        )
        is not None
    )


def infer_profile_name(
    market_type: str | None,
    title: str | None,
) -> str:
    combined = " ".join(
        part.strip()
        for part in (
            market_type or "",
            title or "",
        )
        if part and part.strip()
    ).lower()

    profile_terms = (
        (
            "SPORTS",
            SPORTS_TERMS,
        ),
        (
            "POLITICS",
            POLITICS_TERMS,
        ),
        (
            "CRYPTO",
            CRYPTO_TERMS,
        ),
        (
            "MACRO",
            MACRO_TERMS,
        ),
    )

    for profile_name, terms in profile_terms:
        if any(
            term_matches(
                combined,
                term,
            )
            for term in terms
        ):
            return profile_name

    return "DEFAULT"


def get_scoring_profile(
    market_type: str | None,
    title: str | None,
) -> ScoringProfile:
    profile_name = infer_profile_name(
        market_type,
        title,
    )

    return PROFILES[profile_name]


def thresholds_as_dict(
    thresholds: DecisionThresholds,
) -> dict[str, float | int]:
    return {
        "buy_score": thresholds.buy_score,
        "buy_actionability": (
            thresholds.buy_actionability
        ),
        "buy_confidence": thresholds.buy_confidence,
        "buy_entry": thresholds.buy_entry,
        "buy_structure": thresholds.buy_structure,
        "buy_trust": thresholds.buy_trust,
        "buy_wallet_count": thresholds.buy_wallet_count,
        "buy_data_quality": (
            thresholds.buy_data_quality
        ),
        "watch_score": thresholds.watch_score,
        "watch_actionability": (
            thresholds.watch_actionability
        ),
        "watch_confidence": (
            thresholds.watch_confidence
        ),
        "wait_score": thresholds.wait_score,
        "wait_confidence": (
            thresholds.wait_confidence
        ),
        "wait_entry_ceiling": (
            thresholds.wait_entry_ceiling
        ),
        "avoid_score": thresholds.avoid_score,
    }


validate_profiles()