from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

ENGINE_VERSION = "1.0"
EPSILON = 1e-9

# Conservative prior: equivalent to 10 virtual trades at a 50% win rate.
BAYES_ALPHA = 5.0
BAYES_BETA = 5.0

# ROI winsorization limits used only for normalized scoring.
MIN_ROI_CAP = -1.0
MAX_ROI_CAP = 10.0


@dataclass(frozen=True)
class PositionRecord:
    wallet: str
    condition_id: str
    title: str | None
    selected_outcome: str | None
    won: int
    lost: int
    cost_basis: float
    estimated_profit: float
    estimated_roi: float
    average_entry_price: float
    brier_score: float | None
    resolved_at: str | None
    match_method: str
    match_confidence: float


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        if not math.isfinite(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA busy_timeout = 30000;")
    return connection


def require_table(
    connection: sqlite3.Connection,
    table_name: str,
) -> None:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()

    if row is None:
        raise RuntimeError(f"Required table missing: {table_name}")


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS wallet_performance_normalized (
            wallet TEXT PRIMARY KEY,

            resolved_positions INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,

            raw_win_rate REAL NOT NULL DEFAULT 0,
            bayesian_win_rate REAL NOT NULL DEFAULT 0,
            bayesian_lower_bound REAL NOT NULL DEFAULT 0,
            bayesian_upper_bound REAL NOT NULL DEFAULT 0,

            raw_roi REAL NOT NULL DEFAULT 0,
            capital_weighted_roi REAL NOT NULL DEFAULT 0,
            median_position_roi REAL NOT NULL DEFAULT 0,
            trimmed_mean_roi REAL NOT NULL DEFAULT 0,
            winsorized_mean_roi REAL NOT NULL DEFAULT 0,

            total_cost_basis REAL NOT NULL DEFAULT 0,
            total_profit REAL NOT NULL DEFAULT 0,
            gross_profit REAL NOT NULL DEFAULT 0,
            gross_loss REAL NOT NULL DEFAULT 0,
            profit_factor REAL,
            payoff_ratio REAL,
            expectancy_per_position REAL NOT NULL DEFAULT 0,
            expectancy_per_dollar REAL NOT NULL DEFAULT 0,

            weighted_brier_score REAL,
            calibration_score REAL NOT NULL DEFAULT 0,
            consistency_score REAL NOT NULL DEFAULT 0,
            sample_size_score REAL NOT NULL DEFAULT 0,
            profitability_score REAL NOT NULL DEFAULT 0,
            risk_adjusted_score REAL NOT NULL DEFAULT 0,
            normalization_score REAL NOT NULL DEFAULT 0,
            normalization_grade TEXT NOT NULL DEFAULT 'UNRATED',
            data_confidence TEXT NOT NULL DEFAULT 'VERY LOW',

            outlier_count INTEGER NOT NULL DEFAULT 0,
            high_roi_outlier_count INTEGER NOT NULL DEFAULT 0,
            low_roi_outlier_count INTEGER NOT NULL DEFAULT 0,
            unresolved_positions INTEGER NOT NULL DEFAULT 0,

            first_resolved_at TEXT,
            last_resolved_at TEXT,
            explanation_json TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS
            idx_wpn_score
        ON wallet_performance_normalized(
            normalization_score DESC
        );

        CREATE INDEX IF NOT EXISTS
            idx_wpn_grade
        ON wallet_performance_normalized(
            normalization_grade
        );
        """
    )


def load_positions(
    connection: sqlite3.Connection,
) -> tuple[
    list[PositionRecord],
    dict[str, int],
]:
    rows = connection.execute(
        """
        SELECT
            wallet,
            condition_id,
            title,
            selected_outcome,
            source_outcome_won,
            source_outcome_lost,
            cost_basis,
            estimated_profit,
            estimated_roi,
            average_entry_price,
            brier_score,
            scanned_at,
            match_method,
            match_confidence
        FROM wallet_performance_markets
        WHERE performance_market_key LIKE 'closed_snapshot:%'
        ORDER BY wallet, condition_id, selected_outcome
        """
    ).fetchall()

    positions: list[PositionRecord] = []
    unresolved_by_wallet: dict[str, int] = defaultdict(int)

    for row in rows:
        wallet = str(row["wallet"]).strip().lower()
        won_value = row["source_outcome_won"]

        if won_value not in (0, 1):
            unresolved_by_wallet[wallet] += 1
            continue

        positions.append(
            PositionRecord(
                wallet=wallet,
                condition_id=str(row["condition_id"] or ""),
                title=(
                    str(row["title"])
                    if row["title"] not in (None, "")
                    else None
                ),
                selected_outcome=(
                    str(row["selected_outcome"])
                    if row["selected_outcome"] not in (None, "")
                    else None
                ),
                won=int(row["source_outcome_won"]),
                lost=int(row["source_outcome_lost"] or 0),
                cost_basis=max(0.0, as_float(row["cost_basis"])),
                estimated_profit=as_float(row["estimated_profit"]),
                estimated_roi=as_float(row["estimated_roi"]),
                average_entry_price=clamp(
                    as_float(row["average_entry_price"]),
                    0.0,
                    1.0,
                ),
                brier_score=(
                    as_float(row["brier_score"])
                    if row["brier_score"] is not None
                    else None
                ),
                resolved_at=(
                    str(row["scanned_at"])
                    if row["scanned_at"] not in (None, "")
                    else None
                ),
                match_method=str(row["match_method"] or ""),
                match_confidence=as_float(row["match_confidence"]),
            )
        )

    return positions, dict(unresolved_by_wallet)


def percentile(
    values: list[float],
    probability: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    probability = clamp(probability, 0.0, 1.0)

    if len(ordered) == 1:
        return ordered[0]

    position = probability * (len(ordered) - 1)
    lower_index = math.floor(position)
    upper_index = math.ceil(position)

    if lower_index == upper_index:
        return ordered[lower_index]

    fraction = position - lower_index
    return (
        ordered[lower_index] * (1.0 - fraction)
        + ordered[upper_index] * fraction
    )


def trimmed_mean(
    values: list[float],
    trim_fraction: float = 0.10,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    trim_count = int(len(ordered) * trim_fraction)

    if trim_count == 0:
        return sum(ordered) / len(ordered)

    if trim_count * 2 >= len(ordered):
        return median(ordered)

    trimmed = ordered[trim_count:-trim_count]
    return sum(trimmed) / len(trimmed)


def winsorized_mean(
    values: list[float],
    lower_quantile: float = 0.05,
    upper_quantile: float = 0.95,
) -> float:
    if not values:
        return 0.0

    lower = percentile(values, lower_quantile)
    upper = percentile(values, upper_quantile)

    adjusted = [
        clamp(value, lower, upper)
        for value in values
    ]
    return sum(adjusted) / len(adjusted)


def beta_posterior_interval(
    wins: int,
    losses: int,
) -> tuple[float, float, float]:
    """
    Normal approximation to a Beta posterior interval.

    This avoids an external scipy dependency while still shrinking small
    samples toward 50% and exposing uncertainty.
    """
    alpha = BAYES_ALPHA + wins
    beta = BAYES_BETA + losses
    total = alpha + beta

    mean = alpha / total
    variance = (
        alpha * beta
        / ((total ** 2) * (total + 1.0))
    )
    standard_deviation = math.sqrt(max(0.0, variance))

    lower = clamp(mean - 1.96 * standard_deviation, 0.0, 1.0)
    upper = clamp(mean + 1.96 * standard_deviation, 0.0, 1.0)

    return mean, lower, upper


def sample_size_score(resolved_positions: int) -> float:
    if resolved_positions <= 0:
        return 0.0

    # Approximately 50 at 10 trades, 75 at 31, 100 at 99+.
    return clamp(
        50.0 * math.log10(resolved_positions + 1),
        0.0,
        100.0,
    )


def profitability_score(
    capital_weighted_roi: float,
    trimmed_roi: float,
    profit_factor: float | None,
) -> float:
    capital_component = (
        50.0
        + 50.0 * math.tanh(capital_weighted_roi)
    )
    trimmed_component = (
        50.0
        + 50.0 * math.tanh(trimmed_roi)
    )

    if profit_factor is None:
        profit_factor_component = 50.0
    else:
        profit_factor_component = clamp(
            50.0 + 25.0 * math.log10(max(profit_factor, EPSILON)),
            0.0,
            100.0,
        )

    return (
        capital_component * 0.45
        + trimmed_component * 0.35
        + profit_factor_component * 0.20
    )


def consistency_score(
    winsorized_rois: list[float],
) -> float:
    if not winsorized_rois:
        return 0.0
    if len(winsorized_rois) == 1:
        return 30.0

    mean_roi = sum(winsorized_rois) / len(winsorized_rois)
    variance = sum(
        (value - mean_roi) ** 2
        for value in winsorized_rois
    ) / len(winsorized_rois)
    volatility = math.sqrt(max(0.0, variance))

    positive_component = 50.0 + 30.0 * math.tanh(mean_roi)
    volatility_penalty = 30.0 * math.tanh(volatility)

    return clamp(
        positive_component - volatility_penalty,
        0.0,
        100.0,
    )


def risk_adjusted_score(
    trimmed_roi: float,
    winsorized_rois: list[float],
) -> float:
    if not winsorized_rois:
        return 0.0

    downside_values = [
        min(0.0, value)
        for value in winsorized_rois
    ]
    downside_variance = sum(
        value ** 2
        for value in downside_values
    ) / len(downside_values)
    downside_deviation = math.sqrt(downside_variance)

    ratio = (
        trimmed_roi / downside_deviation
        if downside_deviation > EPSILON
        else (
            3.0
            if trimmed_roi > 0
            else 0.0
        )
    )

    return clamp(
        50.0 + 20.0 * math.tanh(ratio),
        0.0,
        100.0,
    )


def normalization_grade(
    score: float,
    resolved_positions: int,
) -> str:
    if resolved_positions < 5:
        return "UNRATED"
    if score >= 90:
        return "S+"
    if score >= 84:
        return "S"
    if score >= 78:
        return "A+"
    if score >= 72:
        return "A"
    if score >= 65:
        return "B"
    if score >= 58:
        return "C"
    if score >= 50:
        return "WATCH"
    return "EXCLUDE"


def data_confidence(resolved_positions: int) -> str:
    if resolved_positions >= 100:
        return "VERY HIGH"
    if resolved_positions >= 40:
        return "HIGH"
    if resolved_positions >= 15:
        return "MEDIUM"
    if resolved_positions >= 5:
        return "LOW"
    return "VERY LOW"


def aggregate_wallet(
    wallet: str,
    positions: list[PositionRecord],
    unresolved_positions: int,
    calculated_at: str,
) -> dict[str, Any]:
    wins = sum(position.won for position in positions)
    losses = sum(position.lost for position in positions)
    resolved_positions = len(positions)

    raw_win_rate = (
        wins / resolved_positions
        if resolved_positions
        else 0.0
    )

    (
        bayesian_win_rate,
        bayesian_lower_bound,
        bayesian_upper_bound,
    ) = beta_posterior_interval(wins, losses)

    total_cost_basis = sum(
        position.cost_basis
        for position in positions
    )
    total_profit = sum(
        position.estimated_profit
        for position in positions
    )

    raw_roi = (
        total_profit / total_cost_basis
        if total_cost_basis > EPSILON
        else 0.0
    )
    capital_weighted_roi = raw_roi

    rois = [
        position.estimated_roi
        for position in positions
    ]
    capped_rois = [
        clamp(value, MIN_ROI_CAP, MAX_ROI_CAP)
        for value in rois
    ]

    median_position_roi = median(rois) if rois else 0.0
    trimmed_mean_roi = trimmed_mean(capped_rois)
    winsorized_mean_roi = winsorized_mean(capped_rois)

    high_roi_outlier_count = sum(
        value > MAX_ROI_CAP
        for value in rois
    )
    low_roi_outlier_count = sum(
        value < MIN_ROI_CAP
        for value in rois
    )
    outlier_count = (
        high_roi_outlier_count
        + low_roi_outlier_count
    )

    gross_profit = sum(
        max(0.0, position.estimated_profit)
        for position in positions
    )
    gross_loss = abs(
        sum(
            min(0.0, position.estimated_profit)
            for position in positions
        )
    )

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > EPSILON
        else None
    )

    average_win = (
        gross_profit / wins
        if wins
        else 0.0
    )
    average_loss = (
        gross_loss / losses
        if losses
        else 0.0
    )
    payoff_ratio = (
        average_win / average_loss
        if average_loss > EPSILON
        else None
    )

    expectancy_per_position = (
        total_profit / resolved_positions
        if resolved_positions
        else 0.0
    )
    expectancy_per_dollar = (
        total_profit / total_cost_basis
        if total_cost_basis > EPSILON
        else 0.0
    )

    brier_weight = sum(
        position.cost_basis
        for position in positions
        if position.brier_score is not None
    )
    weighted_brier_score = (
        sum(
            (position.brier_score or 0.0)
            * position.cost_basis
            for position in positions
            if position.brier_score is not None
        )
        / brier_weight
        if brier_weight > EPSILON
        else None
    )

    calibration_score = (
        clamp(
            (1.0 - weighted_brier_score) * 100.0,
            0.0,
            100.0,
        )
        if weighted_brier_score is not None
        else 0.0
    )

    consistency = consistency_score(capped_rois)
    sample_score = sample_size_score(resolved_positions)
    profitability = profitability_score(
        capital_weighted_roi=capital_weighted_roi,
        trimmed_roi=trimmed_mean_roi,
        profit_factor=profit_factor,
    )
    risk_score = risk_adjusted_score(
        trimmed_roi=trimmed_mean_roi,
        winsorized_rois=capped_rois,
    )

    # Bayesian accuracy is favored over raw win rate.
    accuracy_score = bayesian_win_rate * 100.0

    normalization_score = (
        accuracy_score * 0.25
        + profitability * 0.25
        + calibration_score * 0.15
        + consistency * 0.15
        + risk_score * 0.10
        + sample_score * 0.10
    )

    grade = normalization_grade(
        normalization_score,
        resolved_positions,
    )
    confidence = data_confidence(resolved_positions)

    resolved_dates = sorted(
        position.resolved_at
        for position in positions
        if position.resolved_at
    )

    explanation = {
        "engine": "PERFORMANCE NORMALIZATION ENGINE",
        "engine_version": ENGINE_VERSION,
        "bayesian_prior": {
            "alpha": BAYES_ALPHA,
            "beta": BAYES_BETA,
            "equivalent_prior_trades": BAYES_ALPHA + BAYES_BETA,
        },
        "roi_normalization": {
            "minimum_cap": MIN_ROI_CAP,
            "maximum_cap": MAX_ROI_CAP,
            "trim_fraction": 0.10,
            "winsorization_quantiles": [0.05, 0.95],
            "outlier_count": outlier_count,
        },
        "important_note": (
            "Raw ROI remains stored for transparency. Normalized scoring "
            "uses capped, trimmed, winsorized, capital-weighted and Bayesian "
            "metrics so small-cost-basis outliers cannot dominate rankings."
        ),
        "score_weights": {
            "bayesian_accuracy": 0.25,
            "profitability": 0.25,
            "calibration": 0.15,
            "consistency": 0.15,
            "risk_adjusted": 0.10,
            "sample_size": 0.10,
        },
    }

    return {
        "wallet": wallet,
        "resolved_positions": resolved_positions,
        "wins": wins,
        "losses": losses,
        "raw_win_rate": raw_win_rate,
        "bayesian_win_rate": bayesian_win_rate,
        "bayesian_lower_bound": bayesian_lower_bound,
        "bayesian_upper_bound": bayesian_upper_bound,
        "raw_roi": raw_roi,
        "capital_weighted_roi": capital_weighted_roi,
        "median_position_roi": median_position_roi,
        "trimmed_mean_roi": trimmed_mean_roi,
        "winsorized_mean_roi": winsorized_mean_roi,
        "total_cost_basis": total_cost_basis,
        "total_profit": total_profit,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "payoff_ratio": payoff_ratio,
        "expectancy_per_position": expectancy_per_position,
        "expectancy_per_dollar": expectancy_per_dollar,
        "weighted_brier_score": weighted_brier_score,
        "calibration_score": calibration_score,
        "consistency_score": consistency,
        "sample_size_score": sample_score,
        "profitability_score": profitability,
        "risk_adjusted_score": risk_score,
        "normalization_score": normalization_score,
        "normalization_grade": grade,
        "data_confidence": confidence,
        "outlier_count": outlier_count,
        "high_roi_outlier_count": high_roi_outlier_count,
        "low_roi_outlier_count": low_roi_outlier_count,
        "unresolved_positions": unresolved_positions,
        "first_resolved_at": (
            resolved_dates[0]
            if resolved_dates
            else None
        ),
        "last_resolved_at": (
            resolved_dates[-1]
            if resolved_dates
            else None
        ),
        "explanation_json": json.dumps(
            explanation,
            sort_keys=True,
        ),
        "calculated_at": calculated_at,
        "updated_at": calculated_at,
    }


def upsert_normalized_wallet(
    connection: sqlite3.Connection,
    summary: dict[str, Any],
) -> None:
    columns = list(summary.keys())
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(
        f"{column} = excluded.{column}"
        for column in columns
        if column != "wallet"
    )

    connection.execute(
        f"""
        INSERT INTO wallet_performance_normalized (
            {", ".join(columns)}
        )
        VALUES ({placeholders})
        ON CONFLICT(wallet) DO UPDATE SET
            {updates}
        """,
        tuple(summary[column] for column in columns),
    )


def print_report(
    summaries: list[dict[str, Any]],
) -> None:
    ranked = sorted(
        summaries,
        key=lambda summary: (
            summary["normalization_score"],
            summary["resolved_positions"],
        ),
        reverse=True,
    )

    print("\n" + "=" * 110)
    print("PERFORMANCE NORMALIZATION COMPLETE")
    print("=" * 110)
    print(f"Database: {DATABASE_PATH}")
    print(f"Wallets normalized: {len(summaries)}")

    print("\nTop normalized wallets:")
    for index, item in enumerate(ranked[:20], start=1):
        profit_factor_text = (
            f"{item['profit_factor']:.2f}"
            if item["profit_factor"] is not None
            else "N/A"
        )

        print(
            f"{index:>2}. {item['wallet']} | "
            f"grade={item['normalization_grade']} | "
            f"score={item['normalization_score']:.2f} | "
            f"resolved={item['resolved_positions']} | "
            f"raw_win={item['raw_win_rate']:.2%} | "
            f"bayes_win={item['bayesian_win_rate']:.2%} | "
            f"raw_roi={item['raw_roi']:.2%} | "
            f"trimmed_roi={item['trimmed_mean_roi']:.2%} | "
            f"profit_factor={profit_factor_text} | "
            f"outliers={item['outlier_count']} | "
            f"confidence={item['data_confidence']}"
        )


def run() -> None:
    calculated_at = utc_now()
    connection = connect_database()

    try:
        require_table(
            connection,
            "wallet_performance_markets",
        )
        ensure_schema(connection)

        positions, unresolved_by_wallet = load_positions(connection)

        grouped: dict[str, list[PositionRecord]] = defaultdict(list)
        for position in positions:
            grouped[position.wallet].append(position)

        all_wallets = sorted(
            set(grouped)
            | set(unresolved_by_wallet)
        )

        summaries = [
            aggregate_wallet(
                wallet=wallet,
                positions=grouped.get(wallet, []),
                unresolved_positions=unresolved_by_wallet.get(wallet, 0),
                calculated_at=calculated_at,
            )
            for wallet in all_wallets
        ]

        with connection:
            # The table is fully regenerated from the reconciled closed-position
            # dataset, so stale normalized rows should not survive.
            connection.execute(
                "DELETE FROM wallet_performance_normalized"
            )

            for summary in summaries:
                upsert_normalized_wallet(
                    connection,
                    summary,
                )

        print_report(summaries)

    finally:
        connection.close()


if __name__ == "__main__":
    run()