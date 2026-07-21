"""
Polymarket Institutional Signal Weight Learning Engine v1.1

Evaluates the historical predictive value, direction and redundancy of
institutional decision signals.

This engine is research-only.

It does not modify:
- institutional_decision_engine.py
- live methodology weights
- historical institutional decisions
- learning observations

Dry-run mode is the default.
Use --apply only to persist signal-learning research.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import argparse
import hashlib
import json
import math
import sqlite3
import statistics
import time
import uuid


ENGINE_VERSION = "1.1"

ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = (
    ROOT
    / "database"
    / "polymarket.db"
)

SOURCE_TABLE = (
    "institutional_learning_observations"
)

MINIMUM_DIRECTIONAL_SAMPLE = 15
MINIMUM_ACTIONABLE_SAMPLE = 30
MINIMUM_PRODUCTION_SAMPLE = 100

MINIMUM_FEATURE_COVERAGE = 0.70
REDUNDANCY_CORRELATION_THRESHOLD = 0.85

DEFAULT_DISPLAY_LIMIT = 25


PREFERRED_FEATURES = (
    "decision_score",
    "actionability_score",
    "weighted_trust_score",
    "entry_quality_score",
    "market_structure_score",
    "data_quality_score",
    "wallet_consensus_score",
    "wallet_quality_score",
    "smart_money_score",
    "elite_wallet_score",
    "consensus_score",
    "conviction_score",
    "liquidity_score",
    "market_liquidity_score",
    "price_edge_score",
    "entry_edge_score",
    "market_efficiency_score",
    "source_quality_score",
    "resolution_quality_score",
)


NON_FEATURE_COLUMNS = {
    "id",
    "observation_key",
    "source_history_id",
    "opportunity_key",
    "market_id",
    "condition_id",
    "token_id",
    "title",
    "selected_outcome",
    "decision_action",
    "decision_grade",
    "methodology_version",
    "methodology_name",
    "actual_result",
    "is_correct",
    "resolution_status",
    "prediction_probability",
    "confidence",
    "brier_score",
    "log_loss",
    "hypothetical_profit",
    "hypothetical_return_pct",
    "observed_at",
    "resolved_at",
    "created_at",
    "updated_at",
}


@dataclass(frozen=True)
class LearningObservation:
    observation_key: str
    decision_action: str
    is_correct: int
    features: dict[str, float | None]


@dataclass(frozen=True)
class FeatureEvaluation:
    evaluation_key: str
    feature_name: str

    total_observations: int
    available_observations: int
    missing_observations: int
    coverage_rate: float

    mean_value: float
    standard_deviation: float
    minimum_value: float
    maximum_value: float

    successful_count: int
    unsuccessful_count: int
    successful_mean: float
    unsuccessful_mean: float
    mean_difference: float

    point_biserial_correlation: float
    absolute_correlation: float

    predictive_strength: float
    raw_importance_score: float
    normalized_importance: float | None

    relationship_direction: str
    evidence_status: str
    recommendation_status: str
    recommendation_reason: str

    rank_position: int
    calculated_at: str


@dataclass(frozen=True)
class RedundancyEvaluation:
    redundancy_key: str
    feature_a: str
    feature_b: str

    paired_observations: int
    correlation: float
    absolute_correlation: float

    redundancy_status: str
    recommendation: str
    calculated_at: str


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def clean_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return str(value).strip()


def optional_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(result):
        return None

    return result


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def stable_key(
    *parts: Any,
) -> str:
    payload = "|".join(
        clean_text(part)
        for part in parts
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def mean_or_zero(
    values: list[float],
) -> float:
    if not values:
        return 0.0

    return statistics.fmean(values)


def standard_deviation(
    values: list[float],
) -> float:
    if len(values) < 2:
        return 0.0

    return statistics.pstdev(values)


def pearson_correlation(
    values_x: list[float],
    values_y: list[float],
) -> float:
    if (
        len(values_x) != len(values_y)
        or len(values_x) < 2
    ):
        return 0.0

    mean_x = statistics.fmean(values_x)
    mean_y = statistics.fmean(values_y)

    numerator = sum(
        (x - mean_x) * (y - mean_y)
        for x, y in zip(
            values_x,
            values_y,
        )
    )

    denominator_x = math.sqrt(
        sum(
            (x - mean_x) ** 2
            for x in values_x
        )
    )

    denominator_y = math.sqrt(
        sum(
            (y - mean_y) ** 2
            for y in values_y
        )
    )

    denominator = (
        denominator_x
        * denominator_y
    )

    if denominator == 0:
        return 0.0

    return numerator / denominator


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> dict[str, str]:
    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {
        clean_text(row["name"]): clean_text(
            row["type"]
        ).upper()
        for row in rows
    }


def is_numeric_sql_type(
    sql_type: str,
) -> bool:
    markers = (
        "INT",
        "REAL",
        "FLOAT",
        "DOUBLE",
        "NUMERIC",
        "DECIMAL",
    )

    return any(
        marker in sql_type
        for marker in markers
    )


def discover_features(
    connection: sqlite3.Connection,
) -> list[str]:
    columns = table_columns(
        connection,
        SOURCE_TABLE,
    )

    available: list[str] = []

    for feature in PREFERRED_FEATURES:
        if feature in columns:
            available.append(feature)

    additional = [
        column_name
        for column_name, sql_type
        in columns.items()
        if (
            column_name not in available
            and column_name
            not in NON_FEATURE_COLUMNS
            and column_name.endswith(
                "_score"
            )
            and is_numeric_sql_type(
                sql_type
            )
        )
    ]

    available.extend(
        sorted(additional)
    )

    return available


def require_source(
    connection: sqlite3.Connection,
) -> None:
    if not table_exists(
        connection,
        SOURCE_TABLE,
    ):
        raise RuntimeError(
            f"{SOURCE_TABLE} does not exist. "
            "Run the Institutional Learning "
            "Engine first."
        )

    columns = table_columns(
        connection,
        SOURCE_TABLE,
    )

    required = {
        "observation_key",
        "decision_action",
        "is_correct",
        "actual_result",
    }

    missing = sorted(
        required - set(columns)
    )

    if missing:
        raise RuntimeError(
            "Learning table is missing required "
            f"columns: {', '.join(missing)}"
        )


def load_observations(
    connection: sqlite3.Connection,
    feature_names: list[str],
) -> list[LearningObservation]:
    feature_sql = ",\n            ".join(
        f'"{feature}"'
        for feature in feature_names
    )

    optional_feature_block = (
        ",\n            "
        + feature_sql
        if feature_sql
        else ""
    )

    sql = f"""
        SELECT
            observation_key,
            decision_action,
            actual_result,
            is_correct
            {optional_feature_block}

        FROM {SOURCE_TABLE}

        WHERE actual_result IN (0, 1)
          AND is_correct IN (0, 1)
          AND UPPER(decision_action)
              IN ('BUY', 'AVOID')

        ORDER BY
            observed_at,
            observation_key
    """

    rows = connection.execute(
        sql
    ).fetchall()

    observations: list[
        LearningObservation
    ] = []

    seen: set[str] = set()

    for row in rows:
        observation_key = clean_text(
            row["observation_key"]
        )

        if (
            not observation_key
            or observation_key in seen
        ):
            continue

        is_correct = safe_int(
            row["is_correct"],
            -1,
        )

        if is_correct not in {0, 1}:
            continue

        seen.add(observation_key)

        features = {
            feature_name: optional_float(
                row[feature_name]
            )
            for feature_name
            in feature_names
        }

        observations.append(
            LearningObservation(
                observation_key=(
                    observation_key
                ),
                decision_action=clean_text(
                    row["decision_action"]
                ).upper(),
                is_correct=is_correct,
                features=features,
            )
        )

    return observations


def evidence_status(
    total_observations: int,
    feature_observations: int,
    coverage_rate: float,
) -> tuple[str, str, str]:
    if total_observations < (
        MINIMUM_DIRECTIONAL_SAMPLE
    ):
        return (
            "EXPERIMENTAL",
            "INSUFFICIENT_SAMPLE",
            (
                "Too few resolved observations "
                "for signal interpretation."
            ),
        )

    if coverage_rate < (
        MINIMUM_FEATURE_COVERAGE
    ):
        return (
            "LOW_COVERAGE",
            "RESEARCH_ONLY",
            (
                "Feature coverage is below the "
                "minimum 70% threshold."
            ),
        )

    if feature_observations < (
        MINIMUM_ACTIONABLE_SAMPLE
    ):
        return (
            "EARLY_SIGNAL",
            "RESEARCH_ONLY",
            (
                "Directional evidence exists, "
                "but proposed weights remain "
                "suppressed."
            ),
        )

    if feature_observations < (
        MINIMUM_PRODUCTION_SAMPLE
    ):
        return (
            "RELIABLE_RESEARCH",
            "ELIGIBLE_FOR_REVIEW",
            (
                "Feature importance may be "
                "reviewed manually. Live weights "
                "must not change automatically."
            ),
        )

    return (
        "PRODUCTION_RESEARCH",
        "STRONG_RESEARCH_SIGNAL",
        (
            "Feature has sufficient historical "
            "coverage for formal methodology "
            "review. Manual approval remains "
            "required."
        ),
    )


def relationship_direction(
    correlation: float,
    mean_difference: float,
    successful_count: int,
    unsuccessful_count: int,
) -> str:
    if (
        successful_count == 0
        or unsuccessful_count == 0
    ):
        return "UNDETERMINED"

    tolerance = 1e-9

    if (
        abs(correlation) <= tolerance
        and abs(mean_difference)
        <= tolerance
    ):
        return "NEUTRAL"

    if (
        correlation > 0
        or mean_difference > 0
    ):
        return "HIGHER_IS_BETTER"

    return "LOWER_IS_BETTER"


def evaluate_feature(
    feature_name: str,
    observations: list[
        LearningObservation
    ],
    calculated_at: str,
) -> FeatureEvaluation:
    available_rows = [
        row
        for row in observations
        if row.features.get(
            feature_name
        ) is not None
    ]

    total = len(observations)
    available = len(available_rows)
    missing = total - available

    coverage_rate = (
        available / total
        if total
        else 0.0
    )

    values = [
        float(
            row.features[feature_name]
        )
        for row in available_rows
        if row.features[feature_name]
        is not None
    ]

    outcomes = [
        float(row.is_correct)
        for row in available_rows
    ]

    successful_values = [
        float(
            row.features[feature_name]
        )
        for row in available_rows
        if (
            row.is_correct == 1
            and row.features[feature_name]
            is not None
        )
    ]

    unsuccessful_values = [
        float(
            row.features[feature_name]
        )
        for row in available_rows
        if (
            row.is_correct == 0
            and row.features[feature_name]
            is not None
        )
    ]

    mean_value = mean_or_zero(
        values
    )

    std_value = standard_deviation(
        values
    )

    minimum_value = (
        min(values)
        if values
        else 0.0
    )

    maximum_value = (
        max(values)
        if values
        else 0.0
    )

    successful_mean = mean_or_zero(
        successful_values
    )

    unsuccessful_mean = mean_or_zero(
        unsuccessful_values
    )

    if (
        successful_values
        and unsuccessful_values
    ):
        mean_difference = (
            successful_mean
            - unsuccessful_mean
        )
    else:
        mean_difference = 0.0

    has_outcome_variation = (
        bool(successful_values)
        and bool(unsuccessful_values)
    )

    correlation = (
        pearson_correlation(
            values,
            outcomes,
        )
        if has_outcome_variation
        else 0.0
    )

    absolute_correlation = abs(
        correlation
    )

    standardized_difference = (
        abs(mean_difference)
        / std_value
        if std_value > 0
        else 0.0
    )

    predictive_strength = (
        0.70 * absolute_correlation
        + 0.30 * min(
            standardized_difference,
            1.0,
        )
    )

    raw_importance = (
        predictive_strength
        * coverage_rate
    )

    (
        evidence,
        recommendation,
        reason,
    ) = evidence_status(
        total_observations=total,
        feature_observations=available,
        coverage_rate=coverage_rate,
    )

    normalized_importance = (
        None
        if total
        < MINIMUM_ACTIONABLE_SAMPLE
        else 0.0
    )

    evaluation_key = stable_key(
        "signal-weight-feature-v1",
        feature_name,
    )

    return FeatureEvaluation(
        evaluation_key=evaluation_key,
        feature_name=feature_name,
        total_observations=total,
        available_observations=available,
        missing_observations=missing,
        coverage_rate=coverage_rate,
        mean_value=mean_value,
        standard_deviation=std_value,
        minimum_value=minimum_value,
        maximum_value=maximum_value,
        successful_count=len(
            successful_values
        ),
        unsuccessful_count=len(
            unsuccessful_values
        ),
        successful_mean=successful_mean,
        unsuccessful_mean=(
            unsuccessful_mean
        ),
        mean_difference=mean_difference,
        point_biserial_correlation=(
            correlation
        ),
        absolute_correlation=(
            absolute_correlation
        ),
        predictive_strength=(
            predictive_strength
        ),
        raw_importance_score=(
            raw_importance
        ),
        normalized_importance=(
            normalized_importance
        ),
        relationship_direction=(
            relationship_direction(
                correlation,
                mean_difference,
                len(successful_values),
                len(unsuccessful_values),
            )
        ),
        evidence_status=evidence,
        recommendation_status=(
            recommendation
        ),
        recommendation_reason=reason,
        rank_position=0,
        calculated_at=calculated_at,
    )


def normalize_importances(
    evaluations: list[
        FeatureEvaluation
    ],
    total_observations: int,
) -> list[FeatureEvaluation]:
    total_importance = sum(
        row.raw_importance_score
        for row in evaluations
        if row.coverage_rate
        >= MINIMUM_FEATURE_COVERAGE
    )

    ordered = sorted(
        evaluations,
        key=lambda row: (
            -row.raw_importance_score,
            -row.coverage_rate,
            row.feature_name,
        ),
    )

    normalized: list[
        FeatureEvaluation
    ] = []

    for rank, row in enumerate(
        ordered,
        start=1,
    ):
        proposed_weight: float | None

        if (
            total_observations
            < MINIMUM_ACTIONABLE_SAMPLE
        ):
            proposed_weight = None
        elif (
            row.coverage_rate
            < MINIMUM_FEATURE_COVERAGE
            or total_importance <= 0
        ):
            proposed_weight = 0.0
        else:
            proposed_weight = (
                row.raw_importance_score
                / total_importance
            )

        normalized.append(
            FeatureEvaluation(
                evaluation_key=(
                    row.evaluation_key
                ),
                feature_name=(
                    row.feature_name
                ),
                total_observations=(
                    row.total_observations
                ),
                available_observations=(
                    row.available_observations
                ),
                missing_observations=(
                    row.missing_observations
                ),
                coverage_rate=(
                    row.coverage_rate
                ),
                mean_value=row.mean_value,
                standard_deviation=(
                    row.standard_deviation
                ),
                minimum_value=(
                    row.minimum_value
                ),
                maximum_value=(
                    row.maximum_value
                ),
                successful_count=(
                    row.successful_count
                ),
                unsuccessful_count=(
                    row.unsuccessful_count
                ),
                successful_mean=(
                    row.successful_mean
                ),
                unsuccessful_mean=(
                    row.unsuccessful_mean
                ),
                mean_difference=(
                    row.mean_difference
                ),
                point_biserial_correlation=(
                    row.point_biserial_correlation
                ),
                absolute_correlation=(
                    row.absolute_correlation
                ),
                predictive_strength=(
                    row.predictive_strength
                ),
                raw_importance_score=(
                    row.raw_importance_score
                ),
                normalized_importance=(
                    proposed_weight
                ),
                relationship_direction=(
                    row.relationship_direction
                ),
                evidence_status=(
                    row.evidence_status
                ),
                recommendation_status=(
                    row.recommendation_status
                ),
                recommendation_reason=(
                    row.recommendation_reason
                ),
                rank_position=rank,
                calculated_at=(
                    row.calculated_at
                ),
            )
        )

    return normalized


def evaluate_redundancy(
    feature_names: list[str],
    observations: list[
        LearningObservation
    ],
    calculated_at: str,
) -> list[RedundancyEvaluation]:
    results: list[
        RedundancyEvaluation
    ] = []

    for index, feature_a in enumerate(
        feature_names
    ):
        for feature_b in feature_names[
            index + 1:
        ]:
            paired_rows = [
                row
                for row in observations
                if (
                    row.features.get(
                        feature_a
                    ) is not None
                    and row.features.get(
                        feature_b
                    ) is not None
                )
            ]

            values_a = [
                float(
                    row.features[feature_a]
                )
                for row in paired_rows
                if row.features[feature_a]
                is not None
            ]

            values_b = [
                float(
                    row.features[feature_b]
                )
                for row in paired_rows
                if row.features[feature_b]
                is not None
            ]

            correlation = (
                pearson_correlation(
                    values_a,
                    values_b,
                )
            )

            absolute_correlation = abs(
                correlation
            )

            if len(paired_rows) < (
                MINIMUM_DIRECTIONAL_SAMPLE
            ):
                status = (
                    "INSUFFICIENT_SAMPLE"
                )
                recommendation = (
                    "No redundancy conclusion."
                )
            elif absolute_correlation >= (
                REDUNDANCY_CORRELATION_THRESHOLD
            ):
                status = (
                    "POTENTIAL_REDUNDANCY"
                )
                recommendation = (
                    "Review whether both signals "
                    "should retain independent "
                    "weight."
                )
            else:
                status = (
                    "NO_HIGH_REDUNDANCY"
                )
                recommendation = (
                    "No immediate redundancy "
                    "warning."
                )

            results.append(
                RedundancyEvaluation(
                    redundancy_key=stable_key(
                        "signal-redundancy-v1",
                        feature_a,
                        feature_b,
                    ),
                    feature_a=feature_a,
                    feature_b=feature_b,
                    paired_observations=len(
                        paired_rows
                    ),
                    correlation=correlation,
                    absolute_correlation=(
                        absolute_correlation
                    ),
                    redundancy_status=status,
                    recommendation=(
                        recommendation
                    ),
                    calculated_at=(
                        calculated_at
                    ),
                )
            )

    return sorted(
        results,
        key=lambda row: (
            -row.absolute_correlation,
            row.feature_a,
            row.feature_b,
        ),
    )


def create_tables(
    connection: sqlite3.Connection,
) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS
        institutional_signal_feature_evaluations (
            evaluation_key TEXT PRIMARY KEY,

            feature_name TEXT NOT NULL,

            total_observations INTEGER
                NOT NULL DEFAULT 0,

            available_observations INTEGER
                NOT NULL DEFAULT 0,

            missing_observations INTEGER
                NOT NULL DEFAULT 0,

            coverage_rate REAL
                NOT NULL DEFAULT 0,

            mean_value REAL
                NOT NULL DEFAULT 0,

            standard_deviation REAL
                NOT NULL DEFAULT 0,

            minimum_value REAL
                NOT NULL DEFAULT 0,

            maximum_value REAL
                NOT NULL DEFAULT 0,

            successful_count INTEGER
                NOT NULL DEFAULT 0,

            unsuccessful_count INTEGER
                NOT NULL DEFAULT 0,

            successful_mean REAL
                NOT NULL DEFAULT 0,

            unsuccessful_mean REAL
                NOT NULL DEFAULT 0,

            mean_difference REAL
                NOT NULL DEFAULT 0,

            point_biserial_correlation REAL
                NOT NULL DEFAULT 0,

            absolute_correlation REAL
                NOT NULL DEFAULT 0,

            predictive_strength REAL
                NOT NULL DEFAULT 0,

            raw_importance_score REAL
                NOT NULL DEFAULT 0,

            normalized_importance REAL,

            relationship_direction TEXT
                NOT NULL,

            evidence_status TEXT
                NOT NULL,

            recommendation_status TEXT
                NOT NULL,

            recommendation_reason TEXT,

            rank_position INTEGER
                NOT NULL DEFAULT 0,

            engine_version TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS
        idx_signal_feature_rank
        ON institutional_signal_feature_evaluations(
            recommendation_status,
            rank_position,
            raw_importance_score
        );

        CREATE TABLE IF NOT EXISTS
        institutional_signal_redundancy (
            redundancy_key TEXT PRIMARY KEY,

            feature_a TEXT NOT NULL,
            feature_b TEXT NOT NULL,

            paired_observations INTEGER
                NOT NULL DEFAULT 0,

            correlation REAL
                NOT NULL DEFAULT 0,

            absolute_correlation REAL
                NOT NULL DEFAULT 0,

            redundancy_status TEXT
                NOT NULL,

            recommendation TEXT,

            engine_version TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS
        idx_signal_redundancy_strength
        ON institutional_signal_redundancy(
            redundancy_status,
            absolute_correlation
        );

        CREATE TABLE IF NOT EXISTS
        institutional_signal_learning_runs (
            run_id TEXT PRIMARY KEY,

            engine_version TEXT NOT NULL,
            mode TEXT NOT NULL,

            started_at TEXT NOT NULL,
            completed_at TEXT,

            resolved_observations INTEGER
                NOT NULL DEFAULT 0,

            discovered_features INTEGER
                NOT NULL DEFAULT 0,

            evaluated_features INTEGER
                NOT NULL DEFAULT 0,

            redundancy_pairs INTEGER
                NOT NULL DEFAULT 0,

            saved_feature_rows INTEGER
                NOT NULL DEFAULT 0,

            saved_redundancy_rows INTEGER
                NOT NULL DEFAULT 0,

            learning_status TEXT NOT NULL,
            status TEXT NOT NULL,

            duration_seconds REAL,
            error_message TEXT
        );
        """
    )


def save_feature_evaluations(
    connection: sqlite3.Connection,
    evaluations: list[
        FeatureEvaluation
    ],
) -> int:
    updated_at = utc_now()

    sql = """
        INSERT INTO
        institutional_signal_feature_evaluations (
            evaluation_key,
            feature_name,

            total_observations,
            available_observations,
            missing_observations,
            coverage_rate,

            mean_value,
            standard_deviation,
            minimum_value,
            maximum_value,

            successful_count,
            unsuccessful_count,
            successful_mean,
            unsuccessful_mean,
            mean_difference,

            point_biserial_correlation,
            absolute_correlation,

            predictive_strength,
            raw_importance_score,
            normalized_importance,

            relationship_direction,
            evidence_status,
            recommendation_status,
            recommendation_reason,

            rank_position,

            engine_version,
            calculated_at,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(evaluation_key)
        DO UPDATE SET
            total_observations =
                excluded.total_observations,

            available_observations =
                excluded.available_observations,

            missing_observations =
                excluded.missing_observations,

            coverage_rate =
                excluded.coverage_rate,

            mean_value =
                excluded.mean_value,

            standard_deviation =
                excluded.standard_deviation,

            minimum_value =
                excluded.minimum_value,

            maximum_value =
                excluded.maximum_value,

            successful_count =
                excluded.successful_count,

            unsuccessful_count =
                excluded.unsuccessful_count,

            successful_mean =
                excluded.successful_mean,

            unsuccessful_mean =
                excluded.unsuccessful_mean,

            mean_difference =
                excluded.mean_difference,

            point_biserial_correlation =
                excluded.point_biserial_correlation,

            absolute_correlation =
                excluded.absolute_correlation,

            predictive_strength =
                excluded.predictive_strength,

            raw_importance_score =
                excluded.raw_importance_score,

            normalized_importance =
                excluded.normalized_importance,

            relationship_direction =
                excluded.relationship_direction,

            evidence_status =
                excluded.evidence_status,

            recommendation_status =
                excluded.recommendation_status,

            recommendation_reason =
                excluded.recommendation_reason,

            rank_position =
                excluded.rank_position,

            engine_version =
                excluded.engine_version,

            calculated_at =
                excluded.calculated_at,

            updated_at =
                excluded.updated_at
    """

    values = [
        (
            row.evaluation_key,
            row.feature_name,

            row.total_observations,
            row.available_observations,
            row.missing_observations,
            row.coverage_rate,

            row.mean_value,
            row.standard_deviation,
            row.minimum_value,
            row.maximum_value,

            row.successful_count,
            row.unsuccessful_count,
            row.successful_mean,
            row.unsuccessful_mean,
            row.mean_difference,

            row.point_biserial_correlation,
            row.absolute_correlation,

            row.predictive_strength,
            row.raw_importance_score,
            row.normalized_importance,

            row.relationship_direction,
            row.evidence_status,
            row.recommendation_status,
            row.recommendation_reason,

            row.rank_position,

            ENGINE_VERSION,
            row.calculated_at,
            updated_at,
        )
        for row in evaluations
    ]

    connection.executemany(
        sql,
        values,
    )

    return len(values)


def save_redundancy(
    connection: sqlite3.Connection,
    evaluations: list[
        RedundancyEvaluation
    ],
) -> int:
    updated_at = utc_now()

    sql = """
        INSERT INTO
        institutional_signal_redundancy (
            redundancy_key,
            feature_a,
            feature_b,

            paired_observations,
            correlation,
            absolute_correlation,

            redundancy_status,
            recommendation,

            engine_version,
            calculated_at,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(redundancy_key)
        DO UPDATE SET
            paired_observations =
                excluded.paired_observations,

            correlation =
                excluded.correlation,

            absolute_correlation =
                excluded.absolute_correlation,

            redundancy_status =
                excluded.redundancy_status,

            recommendation =
                excluded.recommendation,

            engine_version =
                excluded.engine_version,

            calculated_at =
                excluded.calculated_at,

            updated_at =
                excluded.updated_at
    """

    values = [
        (
            row.redundancy_key,
            row.feature_a,
            row.feature_b,

            row.paired_observations,
            row.correlation,
            row.absolute_correlation,

            row.redundancy_status,
            row.recommendation,

            ENGINE_VERSION,
            row.calculated_at,
            updated_at,
        )
        for row in evaluations
    ]

    connection.executemany(
        sql,
        values,
    )

    return len(values)


def save_run_start(
    connection: sqlite3.Connection,
    run_id: str,
    mode: str,
    started_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO
        institutional_signal_learning_runs (
            run_id,
            engine_version,
            mode,
            started_at,
            learning_status,
            status
        )
        VALUES (
            ?, ?, ?, ?,
            'RUNNING',
            'RUNNING'
        )
        """,
        (
            run_id,
            ENGINE_VERSION,
            mode,
            started_at,
        ),
    )


def save_run_complete(
    connection: sqlite3.Connection,
    run_id: str,
    observations: list[
        LearningObservation
    ],
    feature_names: list[str],
    evaluations: list[
        FeatureEvaluation
    ],
    redundancy: list[
        RedundancyEvaluation
    ],
    saved_features: int,
    saved_redundancy: int,
    duration_seconds: float,
) -> None:
    learning_status = (
        "INSUFFICIENT_SAMPLE"
        if len(observations)
        < MINIMUM_ACTIONABLE_SAMPLE
        else "ACTIVE_RESEARCH"
    )

    connection.execute(
        """
        UPDATE institutional_signal_learning_runs
        SET
            completed_at = ?,
            resolved_observations = ?,
            discovered_features = ?,
            evaluated_features = ?,
            redundancy_pairs = ?,
            saved_feature_rows = ?,
            saved_redundancy_rows = ?,
            learning_status = ?,
            status = 'COMPLETE',
            duration_seconds = ?
        WHERE run_id = ?
        """,
        (
            utc_now(),
            len(observations),
            len(feature_names),
            len(evaluations),
            len(redundancy),
            saved_features,
            saved_redundancy,
            learning_status,
            duration_seconds,
            run_id,
        ),
    )


def format_percent(
    value: float,
) -> str:
    return f"{value * 100:,.2f}%"


def format_weight(
    value: float | None,
) -> str:
    if value is None:
        return "SUPPRESSED"

    return format_percent(value)


def print_feature(
    row: FeatureEvaluation,
) -> None:
    rank_label = (
        f"E{row.rank_position:03d}"
        if row.total_observations
        < MINIMUM_ACTIONABLE_SAMPLE
        else f"{row.rank_position:>3}"
    )

    has_outcome_variation = (
        row.successful_count > 0
        and row.unsuccessful_count > 0
    )

    correlation_text = (
        f"{row.point_biserial_correlation:>7.3f}"
        if (
            has_outcome_variation
            and row.available_observations
            >= MINIMUM_DIRECTIONAL_SAMPLE
        )
        else "SUPPRESSED"
    )

    successful_mean_text = (
        f"{row.successful_mean:>8.3f}"
        if row.successful_count > 0
        else "UNAVAILABLE"
    )

    unsuccessful_mean_text = (
        f"{row.unsuccessful_mean:>8.3f}"
        if row.unsuccessful_count > 0
        else "UNAVAILABLE"
    )

    print(
        f"{rank_label}. "
        f"{row.feature_name:<32} "
        f"n={row.available_observations:<5} "
        f"coverage="
        f"{format_percent(row.coverage_rate):>8} "
        f"corr="
        f"{correlation_text:>10} "
        f"weight="
        f"{format_weight(row.normalized_importance):>10}"
    )

    print(
        f"      success_mean="
        f"{successful_mean_text:>11} "
        f"failure_mean="
        f"{unsuccessful_mean_text:>11} "
        f"direction="
        f"{row.relationship_direction:<17} "
        f"status="
        f"{row.recommendation_status}"
    )


def print_summary(
    mode: str,
    run_id: str,
    observations: list[
        LearningObservation
    ],
    feature_names: list[str],
    evaluations: list[
        FeatureEvaluation
    ],
    redundancy: list[
        RedundancyEvaluation
    ],
    display_limit: int,
    duration_seconds: float,
) -> None:
    learning_status = (
        "INSUFFICIENT_SAMPLE"
        if len(observations)
        < MINIMUM_ACTIONABLE_SAMPLE
        else "ACTIVE_RESEARCH"
    )

    print()
    print("=" * 130)
    print(
        "POLYMARKET INSTITUTIONAL SIGNAL "
        "WEIGHT LEARNING ENGINE v1.1"
    )
    print("=" * 130)
    print(
        f"Database:                    "
        f"{DATABASE_PATH}"
    )
    print(
        f"Mode:                        "
        f"{mode}"
    )
    print(
        f"Run ID:                      "
        f"{run_id}"
    )
    print(
        f"Resolved BUY/AVOID pool:     "
        f"{len(observations):,}"
    )
    print(
        f"Discovered signals:          "
        f"{len(feature_names):,}"
    )
    print(
        f"Evaluated signals:           "
        f"{len(evaluations):,}"
    )
    print(
        f"Redundancy pairs:            "
        f"{len(redundancy):,}"
    )
    print(
        f"Learning status:             "
        f"{learning_status}"
    )
    print(
        f"Duration:                    "
        f"{duration_seconds:,.3f}s"
    )
    print("=" * 130)

    print()

    if len(observations) < (
        MINIMUM_ACTIONABLE_SAMPLE
    ):
        print(
            "EXPLORATORY SIGNAL BOARD"
        )
        print(
            "E-prefix indicates exploratory "
            "ordering, not an actionable weight rank."
        )
    else:
        print(
            "SIGNAL IMPORTANCE BOARD"
        )

    print("-" * 130)

    if not evaluations:
        print(
            "No compatible numeric signal columns "
            "were discovered."
        )
    else:
        for row in evaluations[
            :display_limit
        ]:
            print_feature(row)

    print()
    print("REDUNDANCY REVIEW")
    print("-" * 130)

    redundancy_displayed = 0

    for row in redundancy:
        if (
            row.redundancy_status
            == "POTENTIAL_REDUNDANCY"
            or redundancy_displayed < 10
        ):
            correlation_text = (
                f"{row.correlation:>7.3f}"
                if row.paired_observations
                >= MINIMUM_DIRECTIONAL_SAMPLE
                else "SUPPRESSED"
            )

            print(
                f"{row.feature_a:<30} "
                f"<-> "
                f"{row.feature_b:<30} "
                f"n={row.paired_observations:<5} "
                f"corr={correlation_text:>10} "
                f"status={row.redundancy_status}"
            )

            redundancy_displayed += 1

        if redundancy_displayed >= 10:
            break

    if not redundancy:
        print(
            "No feature pairs were available."
        )

    print()
    print("LEARNING INTERPRETATION")
    print("-" * 130)

    if len(observations) < (
        MINIMUM_ACTIONABLE_SAMPLE
    ):
        needed = (
            MINIMUM_ACTIONABLE_SAMPLE
            - len(observations)
        )

        print(
            "Status:                      "
            "INSUFFICIENT_SAMPLE"
        )
        print(
            f"Resolved observations needed:"
            f" {needed}"
        )
        print(
            "Proposed signal weights:     "
            "SUPPRESSED"
        )
        print(
            "Signal recommendation:       "
            "NONE"
        )
        print(
            "Live weight changes:         "
            "PROHIBITED"
        )
        print(
            "Reason:                      "
            "Feature statistics are exploratory "
            "and cannot justify weight changes."
        )

        outcome_classes = {
            row.is_correct
            for row in observations
        }

        if len(outcome_classes) < 2:
            print(
                "Outcome variation:           "
                "INSUFFICIENT"
            )
            print(
                "Correlation interpretation:  "
                "SUPPRESSED"
            )
    else:
        print(
            "Status:                      "
            "ACTIVE_RESEARCH"
        )
        print(
            "Proposed signal weights:     "
            "AVAILABLE FOR MANUAL REVIEW"
        )
        print(
            "Live weight changes:         "
            "NOT AUTOMATIC"
        )

    print()
    print("=" * 130)

    if mode == "DRY RUN":
        print(
            "Dry run complete. No signal-learning "
            "research was saved."
        )
    else:
        print(
            "Signal-learning research was saved "
            "successfully."
        )

    print(
        "The Institutional Decision Engine "
        "was not modified."
    )
    print(
        "No learned weight may be deployed "
        "without sufficient evidence and "
        "manual approval."
    )
    print("=" * 130)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate institutional decision "
            "signals and proposed relative weights."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Save feature evaluations, redundancy "
            "research and run metadata."
        ),
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
        help=(
            "Maximum number of signal evaluations "
            "to display."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    display_limit = max(
        args.display_limit,
        1,
    )

    started_clock = (
        time.perf_counter()
    )

    started_at = utc_now()
    run_id = uuid.uuid4().hex

    mode = (
        "APPLY"
        if args.apply
        else "DRY RUN"
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = (
        sqlite3.Row
    )

    try:
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        require_source(
            connection
        )

        feature_names = (
            discover_features(
                connection
            )
        )

        if args.apply:
            create_tables(
                connection
            )

            save_run_start(
                connection=connection,
                run_id=run_id,
                mode=mode,
                started_at=started_at,
            )

            connection.commit()

        observations = load_observations(
            connection=connection,
            feature_names=feature_names,
        )

        calculated_at = utc_now()

        raw_evaluations = [
            evaluate_feature(
                feature_name=feature_name,
                observations=observations,
                calculated_at=calculated_at,
            )
            for feature_name
            in feature_names
        ]

        evaluations = (
            normalize_importances(
                evaluations=raw_evaluations,
                total_observations=len(
                    observations
                ),
            )
        )

        redundancy = evaluate_redundancy(
            feature_names=feature_names,
            observations=observations,
            calculated_at=calculated_at,
        )

        saved_features = 0
        saved_redundancy_count = 0

        if args.apply:
            saved_features = (
                save_feature_evaluations(
                    connection,
                    evaluations,
                )
            )

            saved_redundancy_count = (
                save_redundancy(
                    connection,
                    redundancy,
                )
            )

            duration_seconds = (
                time.perf_counter()
                - started_clock
            )

            save_run_complete(
                connection=connection,
                run_id=run_id,
                observations=observations,
                feature_names=feature_names,
                evaluations=evaluations,
                redundancy=redundancy,
                saved_features=(
                    saved_features
                ),
                saved_redundancy=(
                    saved_redundancy_count
                ),
                duration_seconds=(
                    duration_seconds
                ),
            )

            connection.commit()
        else:
            duration_seconds = (
                time.perf_counter()
                - started_clock
            )

        print_summary(
            mode=mode,
            run_id=run_id,
            observations=observations,
            feature_names=feature_names,
            evaluations=evaluations,
            redundancy=redundancy,
            display_limit=display_limit,
            duration_seconds=(
                duration_seconds
            ),
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
