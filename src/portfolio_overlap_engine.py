from __future__ import annotations

import itertools
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence_database import create_intelligence_tables


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

MINIMUM_POSITION_VALUE = 500.0
MINIMUM_SHARED_MARKETS_TO_DISPLAY = 1
TOP_RESULTS_TO_DISPLAY = 50


def connect_database() -> sqlite3.Connection:
    """Open the main platform SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH}. "
            "Run the wallet scanner first."
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def safe_float(value: Any) -> float:
    """Convert a value to float safely."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    """Convert a value to integer safely."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """Keep a value inside a numerical range."""

    return max(
        minimum,
        min(value, maximum),
    )


def utc_now() -> str:
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: Any) -> str:
    """Normalize text for matching."""

    return str(value or "").strip().casefold()


def shorten_wallet(wallet: str) -> str:
    """Shorten a wallet address for terminal display."""

    wallet = str(wallet or "")

    if len(wallet) <= 20:
        return wallet

    return f"{wallet[:10]}...{wallet[-8:]}"


def load_latest_wallet_positions() -> dict[str, list[dict[str, Any]]]:
    """
    Load qualifying positions from the newest scan of every wallet.

    Only positions worth at least MINIMUM_POSITION_VALUE are included.
    """

    connection = connect_database()

    try:
        rows = connection.execute(
            """
            WITH latest_scans AS (
                SELECT
                    wallet,
                    MAX(id) AS latest_scan_id
                FROM wallet_scans
                GROUP BY wallet
            )
            SELECT
                positions.wallet,
                positions.market_id,
                positions.title,
                positions.outcome,
                positions.shares,
                positions.average_price,
                positions.current_price,
                positions.current_value,
                positions.cash_pnl,
                positions.percent_pnl
            FROM positions
            INNER JOIN latest_scans
                ON positions.wallet = latest_scans.wallet
               AND positions.scan_id = latest_scans.latest_scan_id
            WHERE positions.market_id IS NOT NULL
              AND TRIM(positions.market_id) != ''
              AND positions.outcome IS NOT NULL
              AND TRIM(positions.outcome) != ''
              AND COALESCE(positions.current_value, 0) >= ?
            ORDER BY
                positions.wallet,
                positions.current_value DESC
            """,
            (MINIMUM_POSITION_VALUE,),
        ).fetchall()

    finally:
        connection.close()

    grouped: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        wallet = normalize_text(row["wallet"])

        if not wallet:
            continue

        grouped.setdefault(wallet, []).append(
            dict(row)
        )

    return grouped


def build_market_lookup(
    positions: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """
    Group a wallet's positions by market ID.

    One market can contain more than one outcome position.
    """

    lookup: dict[str, list[dict[str, Any]]] = {}

    for position in positions:
        market_id = normalize_text(
            position.get("market_id")
        )

        if not market_id:
            continue

        lookup.setdefault(
            market_id,
            [],
        ).append(position)

    return lookup


def build_direction_lookup(
    positions: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Create a market-and-outcome lookup."""

    lookup: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for position in positions:
        market_id = normalize_text(
            position.get("market_id")
        )

        outcome = normalize_text(
            position.get("outcome")
        )

        if not market_id or not outcome:
            continue

        key = (
            market_id,
            outcome,
        )

        existing = lookup.get(key)

        if existing is None:
            lookup[key] = dict(position)
            continue

        existing_value = safe_float(
            existing.get("current_value")
        )

        new_value = safe_float(
            position.get("current_value")
        )

        if new_value > existing_value:
            lookup[key] = dict(position)

    return lookup


def calculate_same_direction_markets(
    wallet_a_positions: list[dict[str, Any]],
    wallet_b_positions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find positions where both wallets hold the same outcome."""

    lookup_a = build_direction_lookup(
        wallet_a_positions
    )

    lookup_b = build_direction_lookup(
        wallet_b_positions
    )

    shared_keys = (
        set(lookup_a)
        & set(lookup_b)
    )

    results: list[dict[str, Any]] = []

    for key in shared_keys:
        position_a = lookup_a[key]
        position_b = lookup_b[key]

        value_a = safe_float(
            position_a.get("current_value")
        )

        value_b = safe_float(
            position_b.get("current_value")
        )

        results.append(
            {
                "market_id": key[0],
                "title": str(
                    position_a.get("title")
                    or position_b.get("title")
                    or "Unknown market"
                ),
                "outcome": str(
                    position_a.get("outcome")
                    or position_b.get("outcome")
                    or "Unknown"
                ),
                "wallet_a_value": value_a,
                "wallet_b_value": value_b,
                "shared_value": min(
                    value_a,
                    value_b,
                ),
            }
        )

    return results


def calculate_opposing_markets(
    wallet_a_positions: list[dict[str, Any]],
    wallet_b_positions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Find markets both wallets hold but on different outcomes.

    This identifies disagreement rather than consensus.
    """

    market_lookup_a = build_market_lookup(
        wallet_a_positions
    )

    market_lookup_b = build_market_lookup(
        wallet_b_positions
    )

    shared_market_ids = (
        set(market_lookup_a)
        & set(market_lookup_b)
    )

    results: list[dict[str, Any]] = []

    for market_id in shared_market_ids:
        positions_a = market_lookup_a[
            market_id
        ]

        positions_b = market_lookup_b[
            market_id
        ]

        outcomes_a = {
            normalize_text(
                position.get("outcome")
            )
            for position in positions_a
        }

        outcomes_b = {
            normalize_text(
                position.get("outcome")
            )
            for position in positions_b
        }

        if outcomes_a & outcomes_b:
            continue

        title = str(
            positions_a[0].get("title")
            or positions_b[0].get("title")
            or "Unknown market"
        )

        results.append(
            {
                "market_id": market_id,
                "title": title,
                "wallet_a_outcomes": sorted(
                    outcome
                    for outcome in outcomes_a
                    if outcome
                ),
                "wallet_b_outcomes": sorted(
                    outcome
                    for outcome in outcomes_b
                    if outcome
                ),
            }
        )

    return results


def calculate_pair_overlap(
    wallet_a: str,
    wallet_b: str,
    wallet_a_positions: list[dict[str, Any]],
    wallet_b_positions: list[dict[str, Any]],
    calculated_at: str,
) -> dict[str, Any]:
    """Calculate complete overlap metrics for one wallet pair."""

    markets_a = {
        normalize_text(
            position.get("market_id")
        )
        for position in wallet_a_positions
        if normalize_text(
            position.get("market_id")
        )
    }

    markets_b = {
        normalize_text(
            position.get("market_id")
        )
        for position in wallet_b_positions
        if normalize_text(
            position.get("market_id")
        )
    }

    shared_market_ids = (
        markets_a & markets_b
    )

    union_market_ids = (
        markets_a | markets_b
    )

    jaccard_similarity = (
        len(shared_market_ids)
        / len(union_market_ids)
        if union_market_ids
        else 0.0
    )

    same_direction = (
        calculate_same_direction_markets(
            wallet_a_positions,
            wallet_b_positions,
        )
    )

    opposing_direction = (
        calculate_opposing_markets(
            wallet_a_positions,
            wallet_b_positions,
        )
    )

    shared_current_value = sum(
        safe_float(
            record["shared_value"]
        )
        for record in same_direction
    )

    wallet_a_total_value = sum(
        safe_float(
            position.get("current_value")
        )
        for position in wallet_a_positions
    )

    wallet_b_total_value = sum(
        safe_float(
            position.get("current_value")
        )
        for position in wallet_b_positions
    )

    combined_current_value = (
        wallet_a_total_value
        + wallet_b_total_value
    )

    smaller_wallet_value = min(
        wallet_a_total_value,
        wallet_b_total_value,
    )

    value_overlap_ratio = (
        shared_current_value
        / smaller_wallet_value
        if smaller_wallet_value > 0
        else 0.0
    )

    shared_market_count = len(
        shared_market_ids
    )

    same_direction_count = len(
        same_direction
    )

    opposing_direction_count = len(
        opposing_direction
    )

    direction_agreement_ratio = (
        same_direction_count
        / shared_market_count
        if shared_market_count > 0
        else 0.0
    )

    market_overlap_component = (
        jaccard_similarity * 45
    )

    capital_overlap_component = (
        clamp(
            value_overlap_ratio,
            0,
            1,
        )
        * 35
    )

    direction_component = (
        direction_agreement_ratio * 20
    )

    weighted_overlap_score = round(
        clamp(
            market_overlap_component
            + capital_overlap_component
            + direction_component,
            0,
            100,
        ),
        1,
    )

    ordered_wallets = sorted(
        [
            wallet_a,
            wallet_b,
        ]
    )

    return {
        "wallet_a": ordered_wallets[0],
        "wallet_b": ordered_wallets[1],
        "wallet_a_market_count": len(
            markets_a
        ),
        "wallet_b_market_count": len(
            markets_b
        ),
        "shared_market_count": (
            shared_market_count
        ),
        "jaccard_similarity": (
            jaccard_similarity
        ),
        "weighted_overlap_score": (
            weighted_overlap_score
        ),
        "shared_current_value": (
            shared_current_value
        ),
        "combined_current_value": (
            combined_current_value
        ),
        "same_direction_count": (
            same_direction_count
        ),
        "opposing_direction_count": (
            opposing_direction_count
        ),
        "calculated_at": calculated_at,
        "same_direction_markets": (
            same_direction
        ),
        "opposing_markets": (
            opposing_direction
        ),
        "value_overlap_ratio": (
            value_overlap_ratio
        ),
        "direction_agreement_ratio": (
            direction_agreement_ratio
        ),
    }


def overlap_grade(score: float) -> str:
    """Convert overlap score into an intelligence label."""

    if score >= 80:
        return "EXTREME OVERLAP"

    if score >= 65:
        return "STRONG OVERLAP"

    if score >= 50:
        return "MEANINGFUL OVERLAP"

    if score >= 30:
        return "MODERATE OVERLAP"

    if score >= 15:
        return "LIGHT OVERLAP"

    return "MINIMAL OVERLAP"


def calculate_all_pairs(
    wallet_positions: dict[
        str,
        list[dict[str, Any]],
    ],
) -> list[dict[str, Any]]:
    """Calculate portfolio overlap for every wallet pair."""

    wallets = sorted(
        wallet_positions
    )

    calculated_at = utc_now()

    results: list[dict[str, Any]] = []

    for wallet_a, wallet_b in itertools.combinations(
        wallets,
        2,
    ):
        result = calculate_pair_overlap(
            wallet_a=wallet_a,
            wallet_b=wallet_b,
            wallet_a_positions=wallet_positions[
                wallet_a
            ],
            wallet_b_positions=wallet_positions[
                wallet_b
            ],
            calculated_at=calculated_at,
        )

        results.append(result)

    results.sort(
        key=lambda result: (
            result["weighted_overlap_score"],
            result["shared_market_count"],
            result["shared_current_value"],
        ),
        reverse=True,
    )

    return results


def save_overlap_results(
    results: list[dict[str, Any]],
) -> int:
    """Save one portfolio-overlap snapshot."""

    if not results:
        return 0

    connection = connect_database()

    try:
        calculated_at = str(
            results[0]["calculated_at"]
        )

        connection.execute(
            """
            DELETE FROM portfolio_overlap
            WHERE calculated_at = ?
            """,
            (calculated_at,),
        )

        rows_created = 0

        for result in results:
            connection.execute(
                """
                INSERT INTO portfolio_overlap (
                    wallet_a,
                    wallet_b,
                    wallet_a_market_count,
                    wallet_b_market_count,
                    shared_market_count,
                    jaccard_similarity,
                    weighted_overlap_score,
                    shared_current_value,
                    combined_current_value,
                    same_direction_count,
                    opposing_direction_count,
                    calculated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
                """,
                (
                    result["wallet_a"],
                    result["wallet_b"],
                    result[
                        "wallet_a_market_count"
                    ],
                    result[
                        "wallet_b_market_count"
                    ],
                    result[
                        "shared_market_count"
                    ],
                    result[
                        "jaccard_similarity"
                    ],
                    result[
                        "weighted_overlap_score"
                    ],
                    result[
                        "shared_current_value"
                    ],
                    result[
                        "combined_current_value"
                    ],
                    result[
                        "same_direction_count"
                    ],
                    result[
                        "opposing_direction_count"
                    ],
                    result[
                        "calculated_at"
                    ],
                ),
            )

            rows_created += 1

        connection.commit()

        return rows_created

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def display_overlap_result(
    number: int,
    result: dict[str, Any],
) -> None:
    """Display one pairwise overlap result."""

    print()
    print("-" * 100)
    print(
        f"{number}. "
        f"{shorten_wallet(result['wallet_a'])} "
        f"<-> "
        f"{shorten_wallet(result['wallet_b'])}"
    )
    print("-" * 100)

    score = safe_float(
        result["weighted_overlap_score"]
    )

    print(
        f"Overlap score:           "
        f"{score:.1f}/100"
    )

    print(
        f"Overlap grade:           "
        f"{overlap_grade(score)}"
    )

    print(
        f"Wallet A markets:        "
        f"{result['wallet_a_market_count']}"
    )

    print(
        f"Wallet B markets:        "
        f"{result['wallet_b_market_count']}"
    )

    print(
        f"Shared markets:          "
        f"{result['shared_market_count']}"
    )

    print(
        f"Same-direction markets:  "
        f"{result['same_direction_count']}"
    )

    print(
        f"Opposing markets:        "
        f"{result['opposing_direction_count']}"
    )

    print(
        f"Jaccard similarity:      "
        f"{result['jaccard_similarity']:.1%}"
    )

    print(
        f"Capital overlap ratio:   "
        f"{result['value_overlap_ratio']:.1%}"
    )

    print(
        f"Direction agreement:     "
        f"{result['direction_agreement_ratio']:.1%}"
    )

    print(
        f"Shared aligned capital:  "
        f"${result['shared_current_value']:,.2f}"
    )

    if result["same_direction_markets"]:
        print()
        print("Shared same-direction positions:")

        top_shared = sorted(
            result["same_direction_markets"],
            key=lambda item: item[
                "shared_value"
            ],
            reverse=True,
        )[:5]

        for shared in top_shared:
            print(
                f"  - {shared['title']} | "
                f"{shared['outcome']} | "
                f"shared value "
                f"${shared['shared_value']:,.2f}"
            )

    if result["opposing_markets"]:
        print()
        print("Opposing positions:")

        for opposing in result[
            "opposing_markets"
        ][:5]:
            wallet_a_outcomes = ", ".join(
                opposing[
                    "wallet_a_outcomes"
                ]
            )

            wallet_b_outcomes = ", ".join(
                opposing[
                    "wallet_b_outcomes"
                ]
            )

            print(
                f"  - {opposing['title']} | "
                f"A: {wallet_a_outcomes} | "
                f"B: {wallet_b_outcomes}"
            )


def display_summary(
    wallet_positions: dict[
        str,
        list[dict[str, Any]],
    ],
    results: list[dict[str, Any]],
    rows_saved: int,
) -> None:
    """Display engine-level summary."""

    meaningful_pairs = [
        result
        for result in results
        if result["shared_market_count"]
        >= MINIMUM_SHARED_MARKETS_TO_DISPLAY
    ]

    strong_pairs = [
        result
        for result in results
        if result["weighted_overlap_score"]
        >= 65
    ]

    opposing_pairs = [
        result
        for result in results
        if result["opposing_direction_count"]
        > 0
    ]

    print()
    print("=" * 100)
    print("PORTFOLIO OVERLAP SUMMARY")
    print("=" * 100)

    print(
        f"Wallets analyzed:          "
        f"{len(wallet_positions)}"
    )

    print(
        f"Wallet pairs calculated:   "
        f"{len(results)}"
    )

    print(
        f"Pairs sharing markets:     "
        f"{len(meaningful_pairs)}"
    )

    print(
        f"Strong-overlap pairs:      "
        f"{len(strong_pairs)}"
    )

    print(
        f"Pairs with opposition:     "
        f"{len(opposing_pairs)}"
    )

    print(
        f"Database rows saved:       "
        f"{rows_saved}"
    )

    print(
        f"Minimum position value:    "
        f"${MINIMUM_POSITION_VALUE:,.2f}"
    )

    print("=" * 100)


def main() -> None:
    """Calculate and store wallet portfolio overlap."""

    print()
    print("=" * 100)
    print(
        "POLYMARKET PORTFOLIO "
        "OVERLAP ENGINE v1"
    )
    print("=" * 100)

    create_intelligence_tables()

    wallet_positions = (
        load_latest_wallet_positions()
    )

    if len(wallet_positions) < 2:
        print()
        print(
            "At least two wallets with qualifying "
            "positions are required."
        )
        return

    print(
        f"Wallets with qualifying positions: "
        f"{len(wallet_positions)}"
    )

    results = calculate_all_pairs(
        wallet_positions
    )

    rows_saved = save_overlap_results(
        results
    )

    display_summary(
        wallet_positions=wallet_positions,
        results=results,
        rows_saved=rows_saved,
    )

    displayable_results = [
        result
        for result in results
        if result["shared_market_count"]
        >= MINIMUM_SHARED_MARKETS_TO_DISPLAY
    ]

    if not displayable_results:
        print()
        print(
            "No wallet pairs currently share a "
            "qualifying market."
        )

    else:
        print()
        print(
            "TOP PORTFOLIO OVERLAP PAIRS"
        )

        for number, result in enumerate(
            displayable_results[
                :TOP_RESULTS_TO_DISPLAY
            ],
            start=1,
        ):
            display_overlap_result(
                number=number,
                result=result,
            )

    print()
    print("=" * 100)
    print(
        "PORTFOLIO OVERLAP ENGINE COMPLETE"
    )
    print("=" * 100)

    print(
        "Results were saved to the "
        "portfolio_overlap table."
    )

    print(
        "Overlap scores rank observed portfolio "
        "similarity only."
    )

    print(
        "They do not prove coordination, copying, "
        "or shared ownership."
    )

    print("=" * 100)


if __name__ == "__main__":
    main()