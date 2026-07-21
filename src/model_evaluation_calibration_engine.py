"""
Polymarket Model Evaluation & Calibration Engine v1.1

Evaluates resolved institutional decisions using the action-aware learning
observations produced by the Institutional Learning Engine.

Scorable actions
----------------
BUY:
    Success means the selected outcome wins.

AVOID:
    Success means the selected outcome loses.

Excluded actions
----------------
WATCH, WAIT and PASS are abstentions and are excluded from predictive
accuracy and calibration calculations.

Dry-run mode is the default. Use --apply to save evaluation results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import argparse
import hashlib
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

SCORABLE_ACTIONS = {
    "BUY",
    "AVOID",
}

MINIMUM_REPORTING_SAMPLE = 5
MINIMUM_DIRECTIONAL_SAMPLE = 15
MINIMUM_RELIABLE_SAMPLE = 30
MINIMUM_STRONG_SAMPLE = 100

MINIMUM_ACTIONABLE_CALIBRATION_SAMPLE = 30

LOG_LOSS_EPSILON = 1e-15

CONFIDENCE_BUCKETS = (
    (0.00, 0.10),
    (0.10, 0.20),
    (0.20, 0.30),
    (0.30, 0.40),
    (0.40, 0.50),
    (0.50, 0.60),
    (0.60, 0.70),
    (0.70, 0.80),
    (0.80, 0.90),
    (0.90, 1.00),
)


@dataclass(frozen=True)
class EvaluationObservation:
    observation_key: str
    source_history_id: int
    opportunity_key: str
    market_id: str
    title: str
    selected_outcome: str

    decision_action: str
    decision_grade: str
    methodology_version: str

    decision_score: float
    actionability_score: float
    confidence_probability: float
    weighted_trust_score: float
    entry_quality_score: float
    market_structure_score: float
    data_quality_score: float

    actual_result: int
    is_correct: int
    stored_brier_score: float | None

    observed_at: str
    resolved_at: str
    evaluated_at: str


@dataclass(frozen=True)
class EvaluationMetric:
    evaluation_key: str
    group_type: str
    group_value: str

    methodology_version: str
    decision_action: str
    decision_grade: str

    sample_size: int
    correct_count: int
    incorrect_count: int

    accuracy: float
    average_confidence: float
    median_confidence: float

    calibration_gap: float
    absolute_calibration_gap: float

    brier_score: float
    log_loss: float

    expected_calibration_error: float
    maximum_calibration_error: float

    overconfidence_rate: float
    underconfidence_rate: float

    average_decision_score: float
    average_actionability_score: float
    average_trust_score: float
    average_entry_quality_score: float
    average_market_structure_score: float
    average_data_quality_score: float

    sample_status: str
    reliability_grade: str
    evaluation_warning: str

    calculated_at: str


@dataclass(frozen=True)
class CalibrationBucket:
    bucket_key: str
    group_type: str
    group_value: str

    bucket_number: int
    lower_bound: float
    upper_bound: float
    bucket_label: str

    sample_size: int
    correct_count: int
    incorrect_count: int

    average_confidence: float | None
    empirical_accuracy: float | None
    calibration_gap: float | None
    absolute_calibration_gap: float | None
    brier_score: float | None
    log_loss: float | None

    sample_status: str
    calculated_at: str


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(result):
        return default

    return result


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


def normalize_probability(
    value: Any,
) -> float:
    probability = safe_float(
        value,
        0.0,
    )

    if probability > 1:
        probability /= 100.0

    return min(
        max(probability, 0.0),
        1.0,
    )


def clamp_log_probability(
    value: float,
) -> float:
    return min(
        max(value, LOG_LOSS_EPSILON),
        1.0 - LOG_LOSS_EPSILON,
    )


def brier_score(
    probability: float,
    actual: int,
) -> float:
    return (
        probability
        - float(actual)
    ) ** 2


def log_loss(
    probability: float,
    actual: int,
) -> float:
    probability = clamp_log_probability(
        probability
    )

    return -(
        actual
        * math.log(probability)
        + (
            1 - actual
        )
        * math.log(
            1.0 - probability
        )
    )


def mean_or_zero(
    values: Iterable[float],
) -> float:
    items = list(values)

    if not items:
        return 0.0

    return statistics.fmean(items)


def median_or_zero(
    values: Iterable[float],
) -> float:
    items = list(values)

    if not items:
        return 0.0

    return statistics.median(items)


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


def require_source_table(
    connection: sqlite3.Connection,
) -> None:
    if not table_exists(
        connection,
        "institutional_learning_observations",
    ):
        raise RuntimeError(
            "institutional_learning_observations "
            "does not exist. Run the Institutional "
            "Learning Engine first."
        )


def create_tables(
    connection: sqlite3.Connection,
) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS
        model_evaluation_metrics (
            evaluation_key TEXT PRIMARY KEY,

            group_type TEXT NOT NULL,
            group_value TEXT NOT NULL,

            methodology_version TEXT,
            decision_action TEXT,
            decision_grade TEXT,

            sample_size INTEGER
                NOT NULL DEFAULT 0,

            correct_count INTEGER
                NOT NULL DEFAULT 0,

            incorrect_count INTEGER
                NOT NULL DEFAULT 0,

            accuracy REAL
                NOT NULL DEFAULT 0,

            average_confidence REAL
                NOT NULL DEFAULT 0,

            median_confidence REAL
                NOT NULL DEFAULT 0,

            calibration_gap REAL
                NOT NULL DEFAULT 0,

            absolute_calibration_gap REAL
                NOT NULL DEFAULT 0,

            brier_score REAL
                NOT NULL DEFAULT 0,

            log_loss REAL
                NOT NULL DEFAULT 0,

            expected_calibration_error REAL
                NOT NULL DEFAULT 0,

            maximum_calibration_error REAL
                NOT NULL DEFAULT 0,

            overconfidence_rate REAL
                NOT NULL DEFAULT 0,

            underconfidence_rate REAL
                NOT NULL DEFAULT 0,

            average_decision_score REAL
                NOT NULL DEFAULT 0,

            average_actionability_score REAL
                NOT NULL DEFAULT 0,

            average_trust_score REAL
                NOT NULL DEFAULT 0,

            average_entry_quality_score REAL
                NOT NULL DEFAULT 0,

            average_market_structure_score REAL
                NOT NULL DEFAULT 0,

            average_data_quality_score REAL
                NOT NULL DEFAULT 0,

            sample_status TEXT NOT NULL,
            reliability_grade TEXT NOT NULL,
            evaluation_warning TEXT,

            engine_version TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            UNIQUE(
                group_type,
                group_value,
                methodology_version,
                decision_action,
                decision_grade
            )
        );

        CREATE INDEX IF NOT EXISTS
        idx_model_evaluation_group
        ON model_evaluation_metrics(
            group_type,
            group_value
        );

        CREATE INDEX IF NOT EXISTS
        idx_model_evaluation_sample
        ON model_evaluation_metrics(
            sample_size,
            reliability_grade
        );

        CREATE TABLE IF NOT EXISTS
        model_calibration_buckets (
            bucket_key TEXT PRIMARY KEY,

            group_type TEXT NOT NULL,
            group_value TEXT NOT NULL,

            bucket_number INTEGER NOT NULL,
            lower_bound REAL NOT NULL,
            upper_bound REAL NOT NULL,
            bucket_label TEXT NOT NULL,

            sample_size INTEGER
                NOT NULL DEFAULT 0,

            correct_count INTEGER
                NOT NULL DEFAULT 0,

            incorrect_count INTEGER
                NOT NULL DEFAULT 0,

            average_confidence REAL,
            empirical_accuracy REAL,
            calibration_gap REAL,
            absolute_calibration_gap REAL,
            brier_score REAL,
            log_loss REAL,

            sample_status TEXT NOT NULL,

            engine_version TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            UNIQUE(
                group_type,
                group_value,
                bucket_number
            )
        );

        CREATE INDEX IF NOT EXISTS
        idx_model_calibration_group
        ON model_calibration_buckets(
            group_type,
            group_value,
            bucket_number
        );

        CREATE TABLE IF NOT EXISTS
        model_evaluation_runs (
            run_id TEXT PRIMARY KEY,

            engine_version TEXT NOT NULL,
            mode TEXT NOT NULL,

            started_at TEXT NOT NULL,
            completed_at TEXT,

            source_rows_loaded INTEGER
                NOT NULL DEFAULT 0,

            resolved_rows_loaded INTEGER
                NOT NULL DEFAULT 0,

            scorable_rows_loaded INTEGER
                NOT NULL DEFAULT 0,

            excluded_abstentions INTEGER
                NOT NULL DEFAULT 0,

            evaluation_groups_created INTEGER
                NOT NULL DEFAULT 0,

            calibration_buckets_created INTEGER
                NOT NULL DEFAULT 0,

            metrics_saved INTEGER
                NOT NULL DEFAULT 0,

            buckets_saved INTEGER
                NOT NULL DEFAULT 0,

            duration_seconds REAL,

            status TEXT NOT NULL,
            error_message TEXT
        );
        """
    )


def load_source_counts(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT
            COUNT(*) AS total_rows,

            SUM(
                CASE
                    WHEN actual_result IN (0, 1)
                    THEN 1
                    ELSE 0
                END
            ) AS resolved_rows,

            SUM(
                CASE
                    WHEN actual_result IN (0, 1)
                     AND UPPER(decision_action)
                         IN ('BUY', 'AVOID')
                     AND is_correct IN (0, 1)
                    THEN 1
                    ELSE 0
                END
            ) AS scorable_rows,

            SUM(
                CASE
                    WHEN actual_result IN (0, 1)
                     AND UPPER(decision_action)
                         IN ('WATCH', 'WAIT', 'PASS')
                    THEN 1
                    ELSE 0
                END
            ) AS excluded_abstentions
        FROM institutional_learning_observations
        """
    ).fetchone()

    return {
        "total_rows": safe_int(
            row["total_rows"]
        ),
        "resolved_rows": safe_int(
            row["resolved_rows"]
        ),
        "scorable_rows": safe_int(
            row["scorable_rows"]
        ),
        "excluded_abstentions": safe_int(
            row["excluded_abstentions"]
        ),
    }


def load_observations(
    connection: sqlite3.Connection,
) -> list[EvaluationObservation]:
    rows = connection.execute(
        """
        SELECT
            observation_key,
            source_history_id,
            opportunity_key,
            market_id,
            title,
            selected_outcome,

            decision_action,
            decision_grade,
            methodology_version,

            decision_score,
            actionability_score,
            confidence,
            weighted_trust_score,
            entry_quality_score,
            market_structure_score,
            data_quality_score,

            actual_result,
            is_correct,
            brier_score,

            observed_at,
            resolved_at,
            evaluated_at

        FROM institutional_learning_observations

        WHERE actual_result IN (0, 1)
          AND is_correct IN (0, 1)
          AND UPPER(decision_action)
              IN ('BUY', 'AVOID')

        ORDER BY
            observed_at,
            observation_key
        """
    ).fetchall()

    observations: list[
        EvaluationObservation
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

        seen.add(observation_key)

        actual_result = safe_int(
            row["actual_result"],
            -1,
        )

        is_correct = safe_int(
            row["is_correct"],
            -1,
        )

        if (
            actual_result not in {0, 1}
            or is_correct not in {0, 1}
        ):
            continue

        observations.append(
            EvaluationObservation(
                observation_key=observation_key,
                source_history_id=safe_int(
                    row["source_history_id"]
                ),
                opportunity_key=clean_text(
                    row["opportunity_key"]
                ),
                market_id=clean_text(
                    row["market_id"]
                ),
                title=clean_text(
                    row["title"]
                ),
                selected_outcome=clean_text(
                    row["selected_outcome"]
                ),
                decision_action=clean_text(
                    row["decision_action"]
                ).upper(),
                decision_grade=clean_text(
                    row["decision_grade"]
                ).upper(),
                methodology_version=clean_text(
                    row["methodology_version"]
                ),
                decision_score=safe_float(
                    row["decision_score"]
                ),
                actionability_score=safe_float(
                    row["actionability_score"]
                ),
                confidence_probability=(
                    normalize_probability(
                        row["confidence"]
                    )
                ),
                weighted_trust_score=safe_float(
                    row["weighted_trust_score"]
                ),
                entry_quality_score=safe_float(
                    row["entry_quality_score"]
                ),
                market_structure_score=safe_float(
                    row[
                        "market_structure_score"
                    ]
                ),
                data_quality_score=safe_float(
                    row["data_quality_score"]
                ),
                actual_result=actual_result,
                is_correct=is_correct,
                stored_brier_score=(
                    optional_float(
                        row["brier_score"]
                    )
                ),
                observed_at=clean_text(
                    row["observed_at"]
                ),
                resolved_at=clean_text(
                    row["resolved_at"]
                ),
                evaluated_at=clean_text(
                    row["evaluated_at"]
                ),
            )
        )

    return observations


def confidence_bucket_number(
    probability: float,
) -> int:
    if probability >= 1.0:
        return 10

    return min(
        int(probability * 10) + 1,
        10,
    )


def bucket_label(
    lower: float,
    upper: float,
) -> str:
    return (
        f"{int(lower * 100):02d}"
        f"?"
        f"{int(upper * 100):02d}%"
    )


def sample_status(
    sample_size: int,
) -> tuple[str, str, str]:
    if sample_size < MINIMUM_REPORTING_SAMPLE:
        return (
            "VERY_LOW_SAMPLE",
            "UNRATED",
            (
                "Too few resolved observations "
                "for meaningful evaluation."
            ),
        )

    if sample_size < MINIMUM_DIRECTIONAL_SAMPLE:
        return (
            "LOW_SAMPLE",
            "PROVISIONAL",
            (
                "Results are highly unstable and "
                "should not change methodology."
            ),
        )

    if sample_size < MINIMUM_RELIABLE_SAMPLE:
        return (
            "DEVELOPING_SAMPLE",
            "EARLY",
            (
                "Directional evidence only; "
                "continue collecting observations."
            ),
        )

    if sample_size < MINIMUM_STRONG_SAMPLE:
        return (
            "RELIABLE_SAMPLE",
            "RELIABLE",
            (
                "Useful for calibration adjustments, "
                "but monitor category concentration."
            ),
        )

    return (
        "STRONG_SAMPLE",
        "STRONG",
        "",
    )


def build_group_sets(
    observations: list[
        EvaluationObservation
    ],
) -> list[
    tuple[
        str,
        str,
        str,
        str,
        str,
        list[EvaluationObservation],
    ]
]:
    groups: list[
        tuple[
            str,
            str,
            str,
            str,
            str,
            list[EvaluationObservation],
        ]
    ] = []

    groups.append(
        (
            "OVERALL",
            "ALL",
            "",
            "",
            "",
            observations,
        )
    )

    actions = sorted(
        {
            row.decision_action
            for row in observations
        }
    )

    for action in actions:
        groups.append(
            (
                "ACTION",
                action,
                "",
                action,
                "",
                [
                    row
                    for row in observations
                    if row.decision_action
                    == action
                ],
            )
        )

    grades = sorted(
        {
            row.decision_grade
            for row in observations
            if row.decision_grade
        }
    )

    for grade in grades:
        groups.append(
            (
                "GRADE",
                grade,
                "",
                "",
                grade,
                [
                    row
                    for row in observations
                    if row.decision_grade
                    == grade
                ],
            )
        )

    methodologies = sorted(
        {
            row.methodology_version
            for row in observations
            if row.methodology_version
        }
    )

    for methodology in methodologies:
        groups.append(
            (
                "METHODOLOGY",
                methodology,
                methodology,
                "",
                "",
                [
                    row
                    for row in observations
                    if row.methodology_version
                    == methodology
                ],
            )
        )

    for methodology in methodologies:
        methodology_rows = [
            row
            for row in observations
            if row.methodology_version
            == methodology
        ]

        methodology_actions = sorted(
            {
                row.decision_action
                for row in methodology_rows
            }
        )

        for action in methodology_actions:
            groups.append(
                (
                    "METHODOLOGY_ACTION",
                    f"{methodology}:{action}",
                    methodology,
                    action,
                    "",
                    [
                        row
                        for row in methodology_rows
                        if row.decision_action
                        == action
                    ],
                )
            )

    return groups


def calibration_statistics(
    rows: list[EvaluationObservation],
) -> tuple[float, float]:
    if not rows:
        return 0.0, 0.0

    grouped: dict[
        int,
        list[EvaluationObservation],
    ] = {}

    for row in rows:
        number = confidence_bucket_number(
            row.confidence_probability
        )

        grouped.setdefault(
            number,
            [],
        ).append(row)

    total = len(rows)
    ece = 0.0
    mce = 0.0

    for bucket_rows in grouped.values():
        bucket_confidence = mean_or_zero(
            row.confidence_probability
            for row in bucket_rows
        )

        bucket_accuracy = mean_or_zero(
            float(row.is_correct)
            for row in bucket_rows
        )

        gap = abs(
            bucket_accuracy
            - bucket_confidence
        )

        weight = (
            len(bucket_rows)
            / total
        )

        ece += weight * gap
        mce = max(mce, gap)

    return ece, mce


def build_evaluation_metric(
    group_type: str,
    group_value: str,
    methodology_version: str,
    decision_action: str,
    decision_grade: str,
    rows: list[EvaluationObservation],
    calculated_at: str,
) -> EvaluationMetric:
    sample_size = len(rows)

    correct_count = sum(
        row.is_correct
        for row in rows
    )

    incorrect_count = (
        sample_size
        - correct_count
    )

    accuracy = (
        correct_count
        / sample_size
        if sample_size
        else 0.0
    )

    confidences = [
        row.confidence_probability
        for row in rows
    ]

    average_confidence = mean_or_zero(
        confidences
    )

    median_confidence = median_or_zero(
        confidences
    )

    calibration_gap = (
        accuracy
        - average_confidence
    )

    absolute_calibration_gap = abs(
        calibration_gap
    )

    brier = mean_or_zero(
        brier_score(
            row.confidence_probability,
            row.is_correct,
        )
        for row in rows
    )

    loss = mean_or_zero(
        log_loss(
            row.confidence_probability,
            row.is_correct,
        )
        for row in rows
    )

    ece, mce = calibration_statistics(
        rows
    )

    overconfidence_rate = mean_or_zero(
        max(
            row.confidence_probability
            - float(row.is_correct),
            0.0,
        )
        for row in rows
    )

    underconfidence_rate = mean_or_zero(
        max(
            float(row.is_correct)
            - row.confidence_probability,
            0.0,
        )
        for row in rows
    )

    (
        status,
        reliability,
        warning,
    ) = sample_status(sample_size)

    evaluation_key = stable_key(
        "model-evaluation-v1",
        group_type,
        group_value,
        methodology_version,
        decision_action,
        decision_grade,
    )

    return EvaluationMetric(
        evaluation_key=evaluation_key,
        group_type=group_type,
        group_value=group_value,
        methodology_version=(
            methodology_version
        ),
        decision_action=decision_action,
        decision_grade=decision_grade,
        sample_size=sample_size,
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        accuracy=accuracy,
        average_confidence=(
            average_confidence
        ),
        median_confidence=(
            median_confidence
        ),
        calibration_gap=calibration_gap,
        absolute_calibration_gap=(
            absolute_calibration_gap
        ),
        brier_score=brier,
        log_loss=loss,
        expected_calibration_error=ece,
        maximum_calibration_error=mce,
        overconfidence_rate=(
            overconfidence_rate
        ),
        underconfidence_rate=(
            underconfidence_rate
        ),
        average_decision_score=mean_or_zero(
            row.decision_score
            for row in rows
        ),
        average_actionability_score=(
            mean_or_zero(
                row.actionability_score
                for row in rows
            )
        ),
        average_trust_score=mean_or_zero(
            row.weighted_trust_score
            for row in rows
        ),
        average_entry_quality_score=(
            mean_or_zero(
                row.entry_quality_score
                for row in rows
            )
        ),
        average_market_structure_score=(
            mean_or_zero(
                row.market_structure_score
                for row in rows
            )
        ),
        average_data_quality_score=(
            mean_or_zero(
                row.data_quality_score
                for row in rows
            )
        ),
        sample_status=status,
        reliability_grade=reliability,
        evaluation_warning=warning,
        calculated_at=calculated_at,
    )


def build_calibration_buckets(
    group_type: str,
    group_value: str,
    rows: list[EvaluationObservation],
    calculated_at: str,
) -> list[CalibrationBucket]:
    buckets: list[
        CalibrationBucket
    ] = []

    for index, (
        lower,
        upper,
    ) in enumerate(
        CONFIDENCE_BUCKETS,
        start=1,
    ):
        if index == 10:
            bucket_rows = [
                row
                for row in rows
                if (
                    lower
                    <= row.confidence_probability
                    <= upper
                )
            ]
        else:
            bucket_rows = [
                row
                for row in rows
                if (
                    lower
                    <= row.confidence_probability
                    < upper
                )
            ]

        size = len(bucket_rows)

        correct = sum(
            row.is_correct
            for row in bucket_rows
        )

        incorrect = size - correct

        if size:
            average_confidence = (
                mean_or_zero(
                    row.confidence_probability
                    for row in bucket_rows
                )
            )

            empirical_accuracy = (
                correct / size
            )

            gap = (
                empirical_accuracy
                - average_confidence
            )

            absolute_gap = abs(gap)

            bucket_brier = mean_or_zero(
                brier_score(
                    row.confidence_probability,
                    row.is_correct,
                )
                for row in bucket_rows
            )

            bucket_log_loss = mean_or_zero(
                log_loss(
                    row.confidence_probability,
                    row.is_correct,
                )
                for row in bucket_rows
            )
        else:
            average_confidence = None
            empirical_accuracy = None
            gap = None
            absolute_gap = None
            bucket_brier = None
            bucket_log_loss = None

        status, _, _ = sample_status(size)

        bucket_key = stable_key(
            "model-calibration-bucket-v1",
            group_type,
            group_value,
            index,
        )

        buckets.append(
            CalibrationBucket(
                bucket_key=bucket_key,
                group_type=group_type,
                group_value=group_value,
                bucket_number=index,
                lower_bound=lower,
                upper_bound=upper,
                bucket_label=bucket_label(
                    lower,
                    upper,
                ),
                sample_size=size,
                correct_count=correct,
                incorrect_count=incorrect,
                average_confidence=(
                    average_confidence
                ),
                empirical_accuracy=(
                    empirical_accuracy
                ),
                calibration_gap=gap,
                absolute_calibration_gap=(
                    absolute_gap
                ),
                brier_score=bucket_brier,
                log_loss=bucket_log_loss,
                sample_status=status,
                calculated_at=calculated_at,
            )
        )

    return buckets


def build_results(
    observations: list[
        EvaluationObservation
    ],
) -> tuple[
    list[EvaluationMetric],
    list[CalibrationBucket],
]:
    calculated_at = utc_now()

    metrics: list[
        EvaluationMetric
    ] = []

    buckets: list[
        CalibrationBucket
    ] = []

    for (
        group_type,
        group_value,
        methodology_version,
        decision_action,
        decision_grade,
        group_rows,
    ) in build_group_sets(observations):
        metrics.append(
            build_evaluation_metric(
                group_type=group_type,
                group_value=group_value,
                methodology_version=(
                    methodology_version
                ),
                decision_action=(
                    decision_action
                ),
                decision_grade=(
                    decision_grade
                ),
                rows=group_rows,
                calculated_at=(
                    calculated_at
                ),
            )
        )

        if group_type in {
            "OVERALL",
            "ACTION",
            "METHODOLOGY",
        }:
            buckets.extend(
                build_calibration_buckets(
                    group_type=group_type,
                    group_value=group_value,
                    rows=group_rows,
                    calculated_at=(
                        calculated_at
                    ),
                )
            )

    return metrics, buckets


def save_metrics(
    connection: sqlite3.Connection,
    metrics: list[EvaluationMetric],
) -> int:
    updated_at = utc_now()

    sql = """
        INSERT INTO model_evaluation_metrics (
            evaluation_key,
            group_type,
            group_value,
            methodology_version,
            decision_action,
            decision_grade,
            sample_size,
            correct_count,
            incorrect_count,
            accuracy,
            average_confidence,
            median_confidence,
            calibration_gap,
            absolute_calibration_gap,
            brier_score,
            log_loss,
            expected_calibration_error,
            maximum_calibration_error,
            overconfidence_rate,
            underconfidence_rate,
            average_decision_score,
            average_actionability_score,
            average_trust_score,
            average_entry_quality_score,
            average_market_structure_score,
            average_data_quality_score,
            sample_status,
            reliability_grade,
            evaluation_warning,
            engine_version,
            calculated_at,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?
        )
        ON CONFLICT(evaluation_key)
        DO UPDATE SET
            sample_size =
                excluded.sample_size,
            correct_count =
                excluded.correct_count,
            incorrect_count =
                excluded.incorrect_count,
            accuracy =
                excluded.accuracy,
            average_confidence =
                excluded.average_confidence,
            median_confidence =
                excluded.median_confidence,
            calibration_gap =
                excluded.calibration_gap,
            absolute_calibration_gap =
                excluded.absolute_calibration_gap,
            brier_score =
                excluded.brier_score,
            log_loss =
                excluded.log_loss,
            expected_calibration_error =
                excluded.expected_calibration_error,
            maximum_calibration_error =
                excluded.maximum_calibration_error,
            overconfidence_rate =
                excluded.overconfidence_rate,
            underconfidence_rate =
                excluded.underconfidence_rate,
            average_decision_score =
                excluded.average_decision_score,
            average_actionability_score =
                excluded.average_actionability_score,
            average_trust_score =
                excluded.average_trust_score,
            average_entry_quality_score =
                excluded.average_entry_quality_score,
            average_market_structure_score =
                excluded.average_market_structure_score,
            average_data_quality_score =
                excluded.average_data_quality_score,
            sample_status =
                excluded.sample_status,
            reliability_grade =
                excluded.reliability_grade,
            evaluation_warning =
                excluded.evaluation_warning,
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
            row.group_type,
            row.group_value,
            row.methodology_version,
            row.decision_action,
            row.decision_grade,
            row.sample_size,
            row.correct_count,
            row.incorrect_count,
            row.accuracy,
            row.average_confidence,
            row.median_confidence,
            row.calibration_gap,
            row.absolute_calibration_gap,
            row.brier_score,
            row.log_loss,
            row.expected_calibration_error,
            row.maximum_calibration_error,
            row.overconfidence_rate,
            row.underconfidence_rate,
            row.average_decision_score,
            row.average_actionability_score,
            row.average_trust_score,
            row.average_entry_quality_score,
            row.average_market_structure_score,
            row.average_data_quality_score,
            row.sample_status,
            row.reliability_grade,
            row.evaluation_warning,
            ENGINE_VERSION,
            row.calculated_at,
            updated_at,
        )
        for row in metrics
    ]

    connection.executemany(
        sql,
        values,
    )

    return len(values)


def save_buckets(
    connection: sqlite3.Connection,
    buckets: list[CalibrationBucket],
) -> int:
    updated_at = utc_now()

    sql = """
        INSERT INTO model_calibration_buckets (
            bucket_key,
            group_type,
            group_value,
            bucket_number,
            lower_bound,
            upper_bound,
            bucket_label,
            sample_size,
            correct_count,
            incorrect_count,
            average_confidence,
            empirical_accuracy,
            calibration_gap,
            absolute_calibration_gap,
            brier_score,
            log_loss,
            sample_status,
            engine_version,
            calculated_at,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(bucket_key)
        DO UPDATE SET
            sample_size =
                excluded.sample_size,
            correct_count =
                excluded.correct_count,
            incorrect_count =
                excluded.incorrect_count,
            average_confidence =
                excluded.average_confidence,
            empirical_accuracy =
                excluded.empirical_accuracy,
            calibration_gap =
                excluded.calibration_gap,
            absolute_calibration_gap =
                excluded.absolute_calibration_gap,
            brier_score =
                excluded.brier_score,
            log_loss =
                excluded.log_loss,
            sample_status =
                excluded.sample_status,
            engine_version =
                excluded.engine_version,
            calculated_at =
                excluded.calculated_at,
            updated_at =
                excluded.updated_at
    """

    values = [
        (
            row.bucket_key,
            row.group_type,
            row.group_value,
            row.bucket_number,
            row.lower_bound,
            row.upper_bound,
            row.bucket_label,
            row.sample_size,
            row.correct_count,
            row.incorrect_count,
            row.average_confidence,
            row.empirical_accuracy,
            row.calibration_gap,
            row.absolute_calibration_gap,
            row.brier_score,
            row.log_loss,
            row.sample_status,
            ENGINE_VERSION,
            row.calculated_at,
            updated_at,
        )
        for row in buckets
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
        INSERT INTO model_evaluation_runs (
            run_id,
            engine_version,
            mode,
            started_at,
            status
        )
        VALUES (?, ?, ?, ?, 'RUNNING')
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
    source_counts: dict[str, int],
    metrics_created: int,
    buckets_created: int,
    metrics_saved: int,
    buckets_saved: int,
    duration_seconds: float,
) -> None:
    connection.execute(
        """
        UPDATE model_evaluation_runs
        SET
            completed_at = ?,
            source_rows_loaded = ?,
            resolved_rows_loaded = ?,
            scorable_rows_loaded = ?,
            excluded_abstentions = ?,
            evaluation_groups_created = ?,
            calibration_buckets_created = ?,
            metrics_saved = ?,
            buckets_saved = ?,
            duration_seconds = ?,
            status = 'COMPLETE'
        WHERE run_id = ?
        """,
        (
            utc_now(),
            source_counts["total_rows"],
            source_counts["resolved_rows"],
            source_counts["scorable_rows"],
            source_counts[
                "excluded_abstentions"
            ],
            metrics_created,
            buckets_created,
            metrics_saved,
            buckets_saved,
            duration_seconds,
            run_id,
        ),
    )


def format_percent(
    value: float,
) -> str:
    return f"{value * 100:,.2f}%"


def calibration_status(
    sample_size: int,
) -> tuple[str, bool, int]:
    remaining = max(
        MINIMUM_ACTIONABLE_CALIBRATION_SAMPLE
        - sample_size,
        0,
    )

    if sample_size < MINIMUM_REPORTING_SAMPLE:
        return (
            "EXPERIMENTAL",
            False,
            remaining,
        )

    if sample_size < MINIMUM_DIRECTIONAL_SAMPLE:
        return (
            "VERY_LOW_SAMPLE",
            False,
            remaining,
        )

    if sample_size < MINIMUM_RELIABLE_SAMPLE:
        return (
            "EARLY_SIGNAL",
            False,
            remaining,
        )

    if sample_size < MINIMUM_STRONG_SAMPLE:
        return (
            "RELIABLE",
            True,
            0,
        )

    return (
        "PRODUCTION_QUALITY",
        True,
        0,
    )


def display_calibration_value(
    value: float,
    actionable: bool,
) -> str:
    if not actionable:
        return "SUPPRESSED"

    return format_percent(value)


def print_metric(
    metric: EvaluationMetric,
) -> None:
    (
        calibration_label,
        calibration_actionable,
        observations_needed,
    ) = calibration_status(
        metric.sample_size
    )

    print(
        f"{metric.group_type:<22} "
        f"{metric.group_value:<24} "
        f"n={metric.sample_size:<5} "
        f"accuracy="
        f"{format_percent(metric.accuracy):>8} "
        f"confidence="
        f"{format_percent(metric.average_confidence):>8}"
    )

    print(
        f"{'':<22} "
        f"{'':<24} "
        f"Brier={metric.brier_score:.4f} "
        f"LogLoss={metric.log_loss:.4f} "
        f"ECE="
        f"{display_calibration_value(metric.expected_calibration_error, calibration_actionable):>10} "
        f"status={metric.sample_status}"
    )

    if not calibration_actionable:
        print(
            f"{'':<22} "
            f"{'':<24} "
            f"calibration={calibration_label} "
            f"need={observations_needed} more resolved"
        )


def print_summary(
    mode: str,
    run_id: str,
    source_counts: dict[str, int],
    observations: list[
        EvaluationObservation
    ],
    metrics: list[EvaluationMetric],
    buckets: list[CalibrationBucket],
    duration_seconds: float,
) -> None:
    print()
    print("=" * 120)
    print(
        "POLYMARKET MODEL EVALUATION & "
        "CALIBRATION ENGINE v1.1"
    )
    print("=" * 120)
    print(f"Database:                   {DATABASE_PATH}")
    print(f"Mode:                       {mode}")
    print(f"Run ID:                     {run_id}")
    print(
        f"Learning observations:      "
        f"{source_counts['total_rows']:,}"
    )
    print(
        f"Resolved observations:      "
        f"{source_counts['resolved_rows']:,}"
    )
    print(
        f"Scorable BUY/AVOID:         "
        f"{source_counts['scorable_rows']:,}"
    )
    print(
        f"Excluded abstentions:       "
        f"{source_counts['excluded_abstentions']:,}"
    )
    print(
        f"Evaluation groups:          "
        f"{len(metrics):,}"
    )
    print(
        f"Calibration buckets:        "
        f"{len(buckets):,}"
    )
    print(
        f"Duration:                   "
        f"{duration_seconds:,.3f}s"
    )
    print("=" * 120)

    print()
    print("EVALUATION BOARD")
    print("-" * 120)

    ordered_metrics = sorted(
        metrics,
        key=lambda row: (
            0
            if row.group_type
            == "OVERALL"
            else 1,
            row.group_type,
            row.group_value,
        ),
    )

    for metric in ordered_metrics:
        print_metric(metric)

    overall = next(
        (
            row
            for row in metrics
            if (
                row.group_type
                == "OVERALL"
                and row.group_value
                == "ALL"
            )
        ),
        None,
    )

    if overall is not None:
        print()
        print("OVERALL INTERPRETATION")
        print("-" * 120)
        print(
            f"Accuracy:                   "
            f"{format_percent(overall.accuracy)}"
        )
        print(
            f"Average decision confidence:"
            f" {format_percent(overall.average_confidence)}"
        )
        (
            calibration_label,
            calibration_actionable,
            observations_needed,
        ) = calibration_status(
            overall.sample_size
        )

        print(
            f"Calibration status:         "
            f"{calibration_label}"
        )

        if calibration_actionable:
            print(
                f"Calibration gap:            "
                f"{format_percent(overall.calibration_gap)}"
            )
            print(
                f"Expected calibration error: "
                f"{format_percent(overall.expected_calibration_error)}"
            )
        else:
            print(
                "Calibration gap:            "
                "SUPPRESSED"
            )
            print(
                "Expected calibration error: "
                "SUPPRESSED"
            )
            print(
                f"Resolved observations needed:"
                f" {observations_needed}"
            )
            print(
                "Calibration interpretation: "
                "Metrics are calculated internally "
                "but are not actionable yet."
            )

        print(
            f"Brier score:                "
            f"{overall.brier_score:.4f}"
        )
        print(
            f"Log loss:                   "
            f"{overall.log_loss:.4f}"
        )
        print(
            f"Reliability:                "
            f"{overall.reliability_grade}"
        )

        if overall.evaluation_warning:
            print(
                f"Warning:                    "
                f"{overall.evaluation_warning}"
            )

    print()
    print("POPULATED CONFIDENCE BUCKETS")
    print("-" * 120)

    populated_buckets = [
        row
        for row in buckets
        if (
            row.group_type
            == "OVERALL"
            and row.group_value
            == "ALL"
            and row.sample_size > 0
        )
    ]

    if not populated_buckets:
        print(
            "No populated confidence buckets."
        )

    for row in populated_buckets:
        (
            bucket_calibration_label,
            bucket_actionable,
            bucket_needed,
        ) = calibration_status(
            row.sample_size
        )

        gap_display = (
            format_percent(
                row.calibration_gap or 0
            )
            if bucket_actionable
            else "SUPPRESSED"
        )

        print(
            f"{row.bucket_label:<10} "
            f"n={row.sample_size:<5} "
            f"confidence="
            f"{format_percent(row.average_confidence or 0):>8} "
            f"accuracy="
            f"{format_percent(row.empirical_accuracy or 0):>8} "
            f"gap="
            f"{gap_display:>10} "
            f"status={row.sample_status}"
        )

        if not bucket_actionable:
            print(
                f"{'':<10} "
                f"calibration="
                f"{bucket_calibration_label} "
                f"need={bucket_needed} more resolved"
            )

    print()
    print("=" * 120)

    if mode == "DRY RUN":
        print(
            "Dry run complete. No evaluation "
            "metrics were saved."
        )
        print(
            "Review the action semantics, sample "
            "warnings and confidence buckets."
        )
    else:
        print(
            "Evaluation metrics and calibration "
            "buckets were saved successfully."
        )

    print(
        "WATCH, WAIT and PASS were excluded "
        "from predictive accuracy."
    )
    print(
        "Confidence is evaluated as probability "
        "that the institutional decision succeeds."
    )
    print(
        "Calibration metrics remain internally "
        "available but are suppressed until at "
        "least 30 resolved observations exist."
    )
    print("=" * 120)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate institutional decision "
            "accuracy and calibration."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Save evaluation metrics, "
            "calibration buckets and run metadata."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    started_clock = time.perf_counter()
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

    connection.row_factory = sqlite3.Row

    try:
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        require_source_table(
            connection
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

        source_counts = load_source_counts(
            connection
        )

        observations = load_observations(
            connection
        )

        metrics, buckets = build_results(
            observations
        )

        metrics_saved = 0
        buckets_saved = 0

        if args.apply:
            metrics_saved = save_metrics(
                connection,
                metrics,
            )

            buckets_saved = save_buckets(
                connection,
                buckets,
            )

            duration_seconds = (
                time.perf_counter()
                - started_clock
            )

            save_run_complete(
                connection=connection,
                run_id=run_id,
                source_counts=source_counts,
                metrics_created=len(metrics),
                buckets_created=len(buckets),
                metrics_saved=metrics_saved,
                buckets_saved=buckets_saved,
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
            source_counts=source_counts,
            observations=observations,
            metrics=metrics,
            buckets=buckets,
            duration_seconds=(
                duration_seconds
            ),
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
