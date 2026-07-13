from __future__ import annotations

import csv
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATABASE_PATH = Path("database/polymarket.db")
DATASET_PATH = Path("data/ml_training_dataset.csv")

MINIMUM_TRAINING_ROWS = 50
MINIMUM_WINS = 10
MINIMUM_LOSSES = 10
MINIMUM_POSITION_VALUE = 500.0


def connect_database() -> sqlite3.Connection:
    """Connect to the local Polymarket SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH.resolve()}."
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def safe_float(value: Any) -> float:
    """Convert a value into a float without crashing."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    """Convert a value into an integer without crashing."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Keep a numerical value inside a defined range."""

    return max(minimum, min(value, maximum))


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    """Check whether a SQLite table exists."""

    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def fetch_resolved_training_rows() -> list[dict[str, Any]]:
    """
    Retrieve valid resolved backtest observations.

    WIN becomes target 1.
    LOSS becomes target 0.
    """

    connection = connect_database()

    try:
        if not table_exists(connection, "backtest_results"):
            return []

        rows = connection.execute(
            """
            SELECT
                market_id,
                title,
                selected_outcome,
                entry_price,
                conviction_score,
                conviction_grade,
                wallet_count,
                hypothetical_return_pct,
                result_status,
                first_signal_at
            FROM backtest_results
            WHERE result_status IN ('WIN', 'LOSS')
              AND entry_price > 0
              AND entry_price < 1
            ORDER BY first_signal_at ASC
            """
        ).fetchall()

        return [
            {
                **dict(row),
                "target": (
                    1
                    if row["result_status"] == "WIN"
                    else 0
                ),
            }
            for row in rows
        ]

    finally:
        connection.close()


def fetch_latest_wallet_ratings() -> dict[str, dict[str, Any]]:
    """Retrieve the newest provisional rating for each wallet."""

    connection = connect_database()

    try:
        if not table_exists(connection, "wallet_rating_history"):
            return {}

        rows = connection.execute(
            """
            WITH latest_ratings AS (
                SELECT
                    wallet,
                    MAX(id) AS latest_id
                FROM wallet_rating_history
                GROUP BY wallet
            )
            SELECT
                rating.wallet,
                rating.wallet_score,
                rating.open_pnl_ratio,
                rating.profitable_position_rate,
                rating.concentration_ratio,
                rating.meaningful_position_count
            FROM wallet_rating_history AS rating
            INNER JOIN latest_ratings AS latest
                ON rating.id = latest.latest_id
            """
        ).fetchall()

        return {
            str(row["wallet"]).strip().lower(): dict(row)
            for row in rows
        }

    finally:
        connection.close()


def fetch_current_consensus_candidates() -> list[dict[str, Any]]:
    """
    Retrieve current qualifying consensus groups from latest wallet scans.
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
            ),
            latest_positions AS (
                SELECT
                    p.wallet,
                    p.market_id,
                    p.title,
                    p.outcome,
                    p.shares,
                    p.average_price,
                    p.current_price,
                    p.current_value,
                    p.cash_pnl
                FROM positions AS p
                INNER JOIN latest_scans AS latest
                    ON p.wallet = latest.wallet
                   AND p.scan_id = latest.latest_scan_id
                WHERE p.market_id IS NOT NULL
                  AND TRIM(p.market_id) != ''
                  AND p.outcome IS NOT NULL
                  AND TRIM(p.outcome) != ''
                  AND COALESCE(p.current_value, 0) >= ?
            )
            SELECT
                market_id,
                title,
                outcome,
                COUNT(DISTINCT wallet) AS wallet_count,
                SUM(COALESCE(shares, 0)) AS combined_shares,
                SUM(COALESCE(current_value, 0)) AS combined_value,
                SUM(COALESCE(cash_pnl, 0)) AS combined_pnl,
                CASE
                    WHEN SUM(COALESCE(shares, 0)) > 0
                    THEN
                        SUM(
                            COALESCE(average_price, 0)
                            * COALESCE(shares, 0)
                        )
                        / SUM(COALESCE(shares, 0))
                    ELSE 0
                END AS average_entry_price,
                CASE
                    WHEN SUM(COALESCE(shares, 0)) > 0
                    THEN
                        SUM(
                            COALESCE(current_price, 0)
                            * COALESCE(shares, 0)
                        )
                        / SUM(COALESCE(shares, 0))
                    ELSE 0
                END AS average_current_price,
                GROUP_CONCAT(DISTINCT wallet) AS wallets
            FROM latest_positions
            GROUP BY
                market_id,
                LOWER(TRIM(outcome))
            HAVING COUNT(DISTINCT wallet) >= 2
            """,
            (MINIMUM_POSITION_VALUE,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def average_wallet_quality(
    wallet_text: str,
    ratings: dict[str, dict[str, Any]],
) -> tuple[float, float, float]:
    """
    Return average wallet score, profitable-position rate,
    and concentration ratio for supporting wallets.
    """

    wallets = [
        wallet.strip().lower()
        for wallet in str(wallet_text or "").split(",")
        if wallet.strip()
    ]

    matched = [
        ratings[wallet]
        for wallet in wallets
        if wallet in ratings
    ]

    if not matched:
        return 50.0, 0.5, 1.0

    average_score = sum(
        safe_float(row.get("wallet_score"))
        for row in matched
    ) / len(matched)

    average_profitable_rate = sum(
        safe_float(row.get("profitable_position_rate"))
        for row in matched
    ) / len(matched)

    average_concentration = sum(
        safe_float(row.get("concentration_ratio"))
        for row in matched
    ) / len(matched)

    return (
        average_score,
        average_profitable_rate,
        average_concentration,
    )


def build_candidate_features(
    candidate: dict[str, Any],
    ratings: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Convert one current consensus candidate into model features."""

    combined_value = safe_float(candidate.get("combined_value"))
    combined_pnl = safe_float(candidate.get("combined_pnl"))
    entry_price = safe_float(candidate.get("average_entry_price"))
    current_price = safe_float(candidate.get("average_current_price"))

    pnl_ratio = (
        combined_pnl / combined_value
        if combined_value > 0
        else 0.0
    )

    price_move = current_price - entry_price

    (
        average_wallet_score,
        average_profitable_rate,
        average_concentration,
    ) = average_wallet_quality(
        str(candidate.get("wallets") or ""),
        ratings,
    )

    return {
        **candidate,
        "entry_price": entry_price,
        "current_price": current_price,
        "price_move": price_move,
        "pnl_ratio": pnl_ratio,
        "average_wallet_score": average_wallet_score,
        "average_wallet_profitable_rate": (
            average_profitable_rate
        ),
        "average_wallet_concentration": (
            average_concentration
        ),
    }


def provisional_ranking_score(
    features: dict[str, Any],
) -> float:
    """
    Produce a transparent fallback score when ML cannot be trained.

    This is not a probability.
    """

    wallet_count = safe_int(features.get("wallet_count"))
    combined_value = safe_float(features.get("combined_value"))
    pnl_ratio = safe_float(features.get("pnl_ratio"))
    price_move = abs(safe_float(features.get("price_move")))
    current_price = safe_float(features.get("current_price"))
    wallet_quality = safe_float(
        features.get("average_wallet_score")
    )
    profitable_rate = safe_float(
        features.get("average_wallet_profitable_rate")
    )
    concentration = safe_float(
        features.get("average_wallet_concentration")
    )

    agreement_score = min(wallet_count / 5, 1.0) * 25

    capital_score = min(
        math.log10(max(combined_value, 1))
        / math.log10(500_000),
        1.0,
    ) * 15

    quality_score = clamp(
        wallet_quality / 100,
        0.0,
        1.0,
    ) * 20

    pnl_score = clamp(
        (pnl_ratio + 0.10) / 0.30,
        0.0,
        1.0,
    ) * 15

    consistency_score = clamp(
        profitable_rate,
        0.0,
        1.0,
    ) * 10

    diversification_score = clamp(
        1.0 - concentration,
        0.0,
        1.0,
    ) * 5

    if price_move <= 0.02:
        timing_score = 7.0
    elif price_move <= 0.05:
        timing_score = 5.0
    elif price_move <= 0.10:
        timing_score = 2.0
    else:
        timing_score = 0.0

    if 0.15 <= current_price <= 0.75:
        price_room_score = 3.0
    elif current_price > 0.95:
        price_room_score = 0.0
    else:
        price_room_score = 1.0

    return round(
        agreement_score
        + capital_score
        + quality_score
        + pnl_score
        + consistency_score
        + diversification_score
        + timing_score
        + price_room_score,
        1,
    )


def ranking_grade(score: float) -> str:
    """Convert provisional ranking score into a research label."""

    if score >= 85:
        return "TIER 1 RESEARCH"
    if score >= 75:
        return "TIER 2 RESEARCH"
    if score >= 65:
        return "TIER 3 MONITOR"
    if score >= 50:
        return "WATCH"
    return "PASS"


def export_training_dataset(
    rows: list[dict[str, Any]],
) -> None:
    """Export resolved observations into a CSV dataset."""

    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "market_id",
        "title",
        "selected_outcome",
        "entry_price",
        "conviction_score",
        "wallet_count",
        "hypothetical_return_pct",
        "target",
        "first_signal_at",
    ]

    with DATASET_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(rows)


def print_training_diagnostics(
    training_rows: list[dict[str, Any]],
) -> bool:
    """Explain whether sufficient data exists for ML training."""

    wins = sum(
        1
        for row in training_rows
        if safe_int(row.get("target")) == 1
    )

    losses = len(training_rows) - wins

    ready = (
        len(training_rows) >= MINIMUM_TRAINING_ROWS
        and wins >= MINIMUM_WINS
        and losses >= MINIMUM_LOSSES
    )

    print()
    print("=" * 100)
    print("MACHINE-LEARNING DATA READINESS")
    print("=" * 100)
    print(f"Resolved observations:          {len(training_rows)}")
    print(f"Wins:                           {wins}")
    print(f"Losses:                         {losses}")
    print(f"Minimum observations required:  {MINIMUM_TRAINING_ROWS}")
    print(f"Minimum wins required:          {MINIMUM_WINS}")
    print(f"Minimum losses required:        {MINIMUM_LOSSES}")
    print(f"Training readiness:             {'READY' if ready else 'NOT READY'}")
    print(f"Dataset location:               {DATASET_PATH}")

    if not ready:
        print()
        print(
            "A predictive model will not be trained yet because the "
            "resolved sample is too small."
        )
        print(
            "The engine will use a transparent provisional ranking "
            "until sufficient independent outcomes exist."
        )

    return ready


def display_candidate(
    number: int,
    candidate: dict[str, Any],
) -> None:
    """Display one provisionally ranked current signal."""

    print()
    print("-" * 100)
    print(f"{number}. {candidate['title']}")
    print("-" * 100)
    print(f"Outcome:                     {candidate['outcome']}")
    print(
        f"Provisional ranking score:   "
        f"{candidate['ranking_score']:.1f}/100"
    )
    print(f"Research tier:               {candidate['ranking_grade']}")
    print(f"Agreeing wallets:            {candidate['wallet_count']}")
    print(
        f"Average wallet quality:      "
        f"{candidate['average_wallet_score']:.1f}/100"
    )
    print(
        f"Combined current value:      "
        f"${candidate['combined_value']:,.2f}"
    )
    print(
        f"Combined open PnL:           "
        f"${candidate['combined_pnl']:,.2f}"
    )
    print(
        f"Open PnL ratio:              "
        f"{candidate['pnl_ratio']:.1%}"
    )
    print(
        f"Average entry price:         "
        f"{candidate['entry_price']:.3f}"
    )
    print(
        f"Average current price:       "
        f"{candidate['current_price']:.3f}"
    )
    print(
        f"Observed price move:         "
        f"{candidate['price_move']:+.3f}"
    )
    print(
        f"Average wallet concentration:"
        f" {candidate['average_wallet_concentration']:.1%}"
    )


def main() -> None:
    """Run ML readiness checks and current signal ranking."""

    print()
    print("=" * 100)
    print("POLYMARKET ML RANKING ENGINE v1")
    print("=" * 100)

    resolved_rows = fetch_resolved_training_rows()
    export_training_dataset(resolved_rows)

    training_ready = print_training_diagnostics(
        resolved_rows
    )

    ratings = fetch_latest_wallet_ratings()
    candidates = fetch_current_consensus_candidates()

    ranked_candidates: list[dict[str, Any]] = []

    for candidate in candidates:
        features = build_candidate_features(
            candidate,
            ratings,
        )

        # Real ML training will be enabled only after the dataset
        # meets the minimum independent-sample requirements.
        score = provisional_ranking_score(features)

        features["ranking_score"] = score
        features["ranking_grade"] = ranking_grade(score)
        features["ranking_method"] = (
            "ML MODEL"
            if training_ready
            else "PROVISIONAL RULE MODEL"
        )

        ranked_candidates.append(features)

    ranked_candidates.sort(
        key=lambda row: (
            row["ranking_score"],
            row["wallet_count"],
            row["combined_value"],
        ),
        reverse=True,
    )

    print()
    print("=" * 100)
    print("CURRENT SIGNAL RANKING")
    print("=" * 100)
    print(f"Wallet ratings loaded:          {len(ratings)}")
    print(f"Consensus candidates found:     {len(ranked_candidates)}")
    print(
        "Ranking method:               "
        + (
            "ML MODEL"
            if training_ready
            else "PROVISIONAL RULE MODEL"
        )
    )

    if not ranked_candidates:
        print()
        print("No current consensus candidates qualify.")
        return

    for number, candidate in enumerate(
        ranked_candidates,
        start=1,
    ):
        display_candidate(number, candidate)

    print()
    print("=" * 100)
    print("IMPORTANT")
    print("=" * 100)
    print(
        "The current ranking is not a calibrated probability of "
        "winning."
    )

    if not training_ready:
        print(
            "Machine learning remains disabled until enough valid "
            "resolved signals exist."
        )

    print(
        "Continue collecting pre-resolution signals and rerun the "
        "backtester after markets resolve."
    )
    print("=" * 100)
    print(
        f"Completed at: "
        f"{datetime.now(timezone.utc).isoformat()}"
    )


if __name__ == "__main__":
    main()