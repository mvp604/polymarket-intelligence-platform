"""
Polymarket Institutional Methodology Optimization Engine v1.1

Evaluates candidate institutional decision methodologies against resolved
learning observations.

Important
---------
This engine is a research and recommendation layer.

It does not modify:
- institutional_decision_engine.py
- live methodology thresholds
- historical decisions
- learning observations

Dry-run mode is the default. Use --apply only to save optimization research.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any, Iterable
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

SCORABLE_ACTIONS = {
    "BUY",
    "AVOID",
}

MINIMUM_OPTIMIZATION_SAMPLE = 30
MINIMUM_CANDIDATE_SAMPLE = 15
MINIMUM_STRONG_SAMPLE = 100

LOG_LOSS_EPSILON = 1e-15

DEFAULT_TOP_LIMIT = 20

CONFIDENCE_THRESHOLDS = (
    0.00,
    0.60,
    0.65,
    0.70,
    0.75,
    0.80,
)

DECISION_SCORE_THRESHOLDS = (
    0.0,
    55.0,
    60.0,
    65.0,
    70.0,
    75.0,
)

ACTIONABILITY_THRESHOLDS = (
    0.0,
    50.0,
    60.0,
    70.0,
)

TRUST_THRESHOLDS = (
    0.0,
    50.0,
    60.0,
    70.0,
)

ENTRY_QUALITY_THRESHOLDS = (
    0.0,
    45.0,
    55.0,
    65.0,
)

MARKET_STRUCTURE_THRESHOLDS = (
    0.0,
    50.0,
    60.0,
    70.0,
)

DATA_QUALITY_THRESHOLDS = (
    0.0,
    50.0,
    60.0,
    70.0,
)


@dataclass(frozen=True)
class OptimizationObservation:
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

    hypothetical_profit: float | None
    hypothetical_return_pct: float | None

    observed_at: str
    resolved_at: str


@dataclass(frozen=True)
class CandidateMethodology:
    candidate_key: str
    candidate_name: str

    minimum_confidence: float
    minimum_decision_score: float
    minimum_actionability_score: float
    minimum_trust_score: float
    minimum_entry_quality_score: float
    minimum_market_structure_score: float
    minimum_data_quality_score: float

    is_baseline: int


@dataclass(frozen=True)
class CandidateEvaluation:
    evaluation_key: str
    candidate_key: str
    candidate_name: str

    minimum_confidence: float
    minimum_decision_score: float
    minimum_actionability_score: float
    minimum_trust_score: float
    minimum_entry_quality_score: float
    minimum_market_structure_score: float
    minimum_data_quality_score: float

    is_baseline: int

    total_resolved_pool: int
    selected_sample_size: int
    excluded_sample_size: int
    retention_rate: float

    correct_count: int
    incorrect_count: int
    accuracy: float

    average_confidence: float
    calibration_gap: float

    brier_score: float
    log_loss: float

    roi_sample_size: int
    total_hypothetical_profit: float
    average_hypothetical_return_pct: float

    composite_score: float

    sample_status: str
    recommendation_status: str
    recommendation_reason: str

    rank_position: int
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


def mean_or_zero(
    values: Iterable[float],
) -> float:
    items = list(values)

    if not items:
        return 0.0

    return statistics.fmean(items)


def clamp_probability(
    probability: float,
) -> float:
    return min(
        max(
            probability,
            LOG_LOSS_EPSILON,
        ),
        1.0 - LOG_LOSS_EPSILON,
    )


def calculate_brier(
    probability: float,
    actual: int,
) -> float:
    return (
        probability
        - float(actual)
    ) ** 2


def calculate_log_loss(
    probability: float,
    actual: int,
) -> float:
    probability = clamp_probability(
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
        methodology_optimization_candidates (
            evaluation_key TEXT PRIMARY KEY,

            candidate_key TEXT NOT NULL,
            candidate_name TEXT NOT NULL,

            minimum_confidence REAL
                NOT NULL DEFAULT 0,

            minimum_decision_score REAL
                NOT NULL DEFAULT 0,

            minimum_actionability_score REAL
                NOT NULL DEFAULT 0,

            minimum_trust_score REAL
                NOT NULL DEFAULT 0,

            minimum_entry_quality_score REAL
                NOT NULL DEFAULT 0,

            minimum_market_structure_score REAL
                NOT NULL DEFAULT 0,

            minimum_data_quality_score REAL
                NOT NULL DEFAULT 0,

            is_baseline INTEGER
                NOT NULL DEFAULT 0,

            total_resolved_pool INTEGER
                NOT NULL DEFAULT 0,

            selected_sample_size INTEGER
                NOT NULL DEFAULT 0,

            excluded_sample_size INTEGER
                NOT NULL DEFAULT 0,

            retention_rate REAL
                NOT NULL DEFAULT 0,

            correct_count INTEGER
                NOT NULL DEFAULT 0,

            incorrect_count INTEGER
                NOT NULL DEFAULT 0,

            accuracy REAL
                NOT NULL DEFAULT 0,

            average_confidence REAL
                NOT NULL DEFAULT 0,

            calibration_gap REAL
                NOT NULL DEFAULT 0,

            brier_score REAL
                NOT NULL DEFAULT 0,

            log_loss REAL
                NOT NULL DEFAULT 0,

            roi_sample_size INTEGER
                NOT NULL DEFAULT 0,

            total_hypothetical_profit REAL
                NOT NULL DEFAULT 0,

            average_hypothetical_return_pct REAL
                NOT NULL DEFAULT 0,

            composite_score REAL
                NOT NULL DEFAULT 0,

            sample_status TEXT NOT NULL,
            recommendation_status TEXT NOT NULL,
            recommendation_reason TEXT,

            rank_position INTEGER
                NOT NULL DEFAULT 0,

            engine_version TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS
        idx_methodology_optimization_rank
        ON methodology_optimization_candidates(
            recommendation_status,
            rank_position,
            composite_score
        );

        CREATE INDEX IF NOT EXISTS
        idx_methodology_optimization_candidate
        ON methodology_optimization_candidates(
            candidate_key
        );

        CREATE TABLE IF NOT EXISTS
        methodology_optimization_runs (
            run_id TEXT PRIMARY KEY,

            engine_version TEXT NOT NULL,
            mode TEXT NOT NULL,

            started_at TEXT NOT NULL,
            completed_at TEXT,

            resolved_observations INTEGER
                NOT NULL DEFAULT 0,

            candidate_definitions INTEGER
                NOT NULL DEFAULT 0,

            candidate_evaluations INTEGER
                NOT NULL DEFAULT 0,

            eligible_candidates INTEGER
                NOT NULL DEFAULT 0,

            saved_candidates INTEGER
                NOT NULL DEFAULT 0,

            duration_seconds REAL,

            optimization_status TEXT NOT NULL,
            status TEXT NOT NULL,

            error_message TEXT
        );
        """
    )


def load_observations(
    connection: sqlite3.Connection,
) -> list[OptimizationObservation]:
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

            hypothetical_profit,
            hypothetical_return_pct,

            observed_at,
            resolved_at

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
        OptimizationObservation
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
            OptimizationObservation(
                observation_key=(
                    observation_key
                ),
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
                hypothetical_profit=(
                    optional_float(
                        row["hypothetical_profit"]
                    )
                ),
                hypothetical_return_pct=(
                    optional_float(
                        row[
                            "hypothetical_return_pct"
                        ]
                    )
                ),
                observed_at=clean_text(
                    row["observed_at"]
                ),
                resolved_at=clean_text(
                    row["resolved_at"]
                ),
            )
        )

    return observations


def candidate_name(
    confidence: float,
    decision_score: float,
    actionability: float,
    trust: float,
    entry_quality: float,
    market_structure: float,
    data_quality: float,
) -> str:
    return (
        f"C{confidence:.2f}"
        f"_D{decision_score:.0f}"
        f"_A{actionability:.0f}"
        f"_T{trust:.0f}"
        f"_E{entry_quality:.0f}"
        f"_M{market_structure:.0f}"
        f"_Q{data_quality:.0f}"
    )


def build_candidate(
    confidence: float,
    decision_score: float,
    actionability: float,
    trust: float,
    entry_quality: float,
    market_structure: float,
    data_quality: float,
    is_baseline: int = 0,
) -> CandidateMethodology:
    name = candidate_name(
        confidence=confidence,
        decision_score=decision_score,
        actionability=actionability,
        trust=trust,
        entry_quality=entry_quality,
        market_structure=market_structure,
        data_quality=data_quality,
    )

    key = stable_key(
        "methodology-candidate-v1",
        confidence,
        decision_score,
        actionability,
        trust,
        entry_quality,
        market_structure,
        data_quality,
    )

    return CandidateMethodology(
        candidate_key=key,
        candidate_name=name,
        minimum_confidence=confidence,
        minimum_decision_score=(
            decision_score
        ),
        minimum_actionability_score=(
            actionability
        ),
        minimum_trust_score=trust,
        minimum_entry_quality_score=(
            entry_quality
        ),
        minimum_market_structure_score=(
            market_structure
        ),
        minimum_data_quality_score=(
            data_quality
        ),
        is_baseline=is_baseline,
    )


def build_candidate_grid() -> list[
    CandidateMethodology
]:
    candidates: dict[
        str,
        CandidateMethodology,
    ] = {}

    baseline = build_candidate(
        confidence=0.0,
        decision_score=0.0,
        actionability=0.0,
        trust=0.0,
        entry_quality=0.0,
        market_structure=0.0,
        data_quality=0.0,
        is_baseline=1,
    )

    candidates[
        baseline.candidate_key
    ] = baseline

    single_dimension_sets = (
        (
            "confidence",
            CONFIDENCE_THRESHOLDS,
        ),
        (
            "decision",
            DECISION_SCORE_THRESHOLDS,
        ),
        (
            "actionability",
            ACTIONABILITY_THRESHOLDS,
        ),
        (
            "trust",
            TRUST_THRESHOLDS,
        ),
        (
            "entry",
            ENTRY_QUALITY_THRESHOLDS,
        ),
        (
            "structure",
            MARKET_STRUCTURE_THRESHOLDS,
        ),
        (
            "quality",
            DATA_QUALITY_THRESHOLDS,
        ),
    )

    for dimension, thresholds in (
        single_dimension_sets
    ):
        for threshold in thresholds:
            values = {
                "confidence": 0.0,
                "decision": 0.0,
                "actionability": 0.0,
                "trust": 0.0,
                "entry": 0.0,
                "structure": 0.0,
                "quality": 0.0,
            }

            values[dimension] = threshold

            candidate = build_candidate(
                confidence=values[
                    "confidence"
                ],
                decision_score=values[
                    "decision"
                ],
                actionability=values[
                    "actionability"
                ],
                trust=values["trust"],
                entry_quality=values[
                    "entry"
                ],
                market_structure=values[
                    "structure"
                ],
                data_quality=values[
                    "quality"
                ],
            )

            candidates[
                candidate.candidate_key
            ] = candidate

    focused_confidence = (
        0.60,
        0.65,
        0.70,
        0.75,
    )

    focused_scores = (
        55.0,
        60.0,
        65.0,
        70.0,
    )

    focused_secondary = (
        50.0,
        60.0,
        70.0,
    )

    for (
        confidence,
        decision_score,
    ) in product(
        focused_confidence,
        focused_scores,
    ):
        candidate = build_candidate(
            confidence=confidence,
            decision_score=decision_score,
            actionability=0.0,
            trust=0.0,
            entry_quality=0.0,
            market_structure=0.0,
            data_quality=0.0,
        )

        candidates[
            candidate.candidate_key
        ] = candidate

    for (
        confidence,
        decision_score,
        actionability,
    ) in product(
        focused_confidence,
        focused_scores,
        focused_secondary,
    ):
        candidate = build_candidate(
            confidence=confidence,
            decision_score=decision_score,
            actionability=actionability,
            trust=0.0,
            entry_quality=0.0,
            market_structure=0.0,
            data_quality=0.0,
        )

        candidates[
            candidate.candidate_key
        ] = candidate

    for (
        confidence,
        trust,
        entry_quality,
    ) in product(
        focused_confidence,
        focused_secondary,
        focused_secondary,
    ):
        candidate = build_candidate(
            confidence=confidence,
            decision_score=0.0,
            actionability=0.0,
            trust=trust,
            entry_quality=entry_quality,
            market_structure=0.0,
            data_quality=0.0,
        )

        candidates[
            candidate.candidate_key
        ] = candidate

    for (
        confidence,
        market_structure,
        data_quality,
    ) in product(
        focused_confidence,
        focused_secondary,
        focused_secondary,
    ):
        candidate = build_candidate(
            confidence=confidence,
            decision_score=0.0,
            actionability=0.0,
            trust=0.0,
            entry_quality=0.0,
            market_structure=(
                market_structure
            ),
            data_quality=data_quality,
        )

        candidates[
            candidate.candidate_key
        ] = candidate

    return sorted(
        candidates.values(),
        key=lambda row: (
            -row.is_baseline,
            row.minimum_confidence,
            row.minimum_decision_score,
            row.minimum_actionability_score,
            row.minimum_trust_score,
            row.minimum_entry_quality_score,
            row.minimum_market_structure_score,
            row.minimum_data_quality_score,
        ),
    )


def passes_candidate(
    row: OptimizationObservation,
    candidate: CandidateMethodology,
) -> bool:
    return (
        row.confidence_probability
        >= candidate.minimum_confidence
        and row.decision_score
        >= candidate.minimum_decision_score
        and row.actionability_score
        >= candidate.minimum_actionability_score
        and row.weighted_trust_score
        >= candidate.minimum_trust_score
        and row.entry_quality_score
        >= candidate.minimum_entry_quality_score
        and row.market_structure_score
        >= candidate.minimum_market_structure_score
        and row.data_quality_score
        >= candidate.minimum_data_quality_score
    )


def sample_status(
    sample_size: int,
    total_pool: int,
) -> tuple[str, str, str]:
    if total_pool < MINIMUM_OPTIMIZATION_SAMPLE:
        return (
            "INSUFFICIENT_POOL",
            "INSUFFICIENT_SAMPLE",
            (
                "The total resolved observation "
                "pool is below 30. No methodology "
                "change may be recommended."
            ),
        )

    if sample_size < MINIMUM_CANDIDATE_SAMPLE:
        return (
            "INSUFFICIENT_CANDIDATE_SAMPLE",
            "RESEARCH_ONLY",
            (
                "Candidate retains fewer than 15 "
                "resolved observations."
            ),
        )

    if sample_size < MINIMUM_OPTIMIZATION_SAMPLE:
        return (
            "LOW_CANDIDATE_SAMPLE",
            "RESEARCH_ONLY",
            (
                "Candidate has directional evidence "
                "but not enough observations for "
                "methodology review."
            ),
        )

    if sample_size < MINIMUM_STRONG_SAMPLE:
        return (
            "RELIABLE_CANDIDATE_SAMPLE",
            "ELIGIBLE_FOR_REVIEW",
            (
                "Candidate may be reviewed manually. "
                "It must not be auto-deployed."
            ),
        )

    return (
        "STRONG_CANDIDATE_SAMPLE",
        "STRONG_CANDIDATE",
        (
            "Candidate has enough observations for "
            "formal methodology review. Manual "
            "approval is still required."
        ),
    )


def composite_score(
    accuracy: float,
    brier: float,
    log_loss: float,
    retention_rate: float,
    average_return: float,
    sample_size: int,
    total_pool: int,
) -> float:
    accuracy_component = (
        accuracy * 35.0
    )

    brier_component = (
        max(
            1.0 - brier,
            0.0,
        )
        * 25.0
    )

    normalized_log_loss = min(
        log_loss / 1.5,
        1.0,
    )

    log_loss_component = (
        1.0
        - normalized_log_loss
    ) * 15.0

    retention_component = (
        retention_rate * 15.0
    )

    roi_component = max(
        min(
            average_return,
            1.0,
        ),
        -1.0,
    )

    roi_component = (
        roi_component + 1.0
    ) / 2.0 * 10.0

    evidence_ratio = (
        sample_size
        / max(total_pool, 1)
    )

    if sample_size < MINIMUM_CANDIDATE_SAMPLE:
        sample_multiplier = 0.10
    elif sample_size < MINIMUM_OPTIMIZATION_SAMPLE:
        sample_multiplier = 0.50
    elif sample_size < MINIMUM_STRONG_SAMPLE:
        sample_multiplier = min(
            0.75
            + 0.25 * evidence_ratio,
            1.0,
        )
    else:
        sample_multiplier = 1.0

    raw_score = (
        accuracy_component
        + brier_component
        + log_loss_component
        + retention_component
        + roi_component
    )

    return raw_score * sample_multiplier


def evaluate_candidate(
    candidate: CandidateMethodology,
    observations: list[
        OptimizationObservation
    ],
    calculated_at: str,
) -> CandidateEvaluation:
    selected = [
        row
        for row in observations
        if passes_candidate(
            row,
            candidate,
        )
    ]

    total_pool = len(observations)
    sample_size = len(selected)

    excluded = (
        total_pool
        - sample_size
    )

    retention_rate = (
        sample_size / total_pool
        if total_pool
        else 0.0
    )

    correct_count = sum(
        row.is_correct
        for row in selected
    )

    incorrect_count = (
        sample_size
        - correct_count
    )

    accuracy = (
        correct_count / sample_size
        if sample_size
        else 0.0
    )

    average_confidence = mean_or_zero(
        row.confidence_probability
        for row in selected
    )

    calibration_gap = (
        accuracy
        - average_confidence
    )

    brier = mean_or_zero(
        calculate_brier(
            row.confidence_probability,
            row.is_correct,
        )
        for row in selected
    )

    log_loss = mean_or_zero(
        calculate_log_loss(
            row.confidence_probability,
            row.is_correct,
        )
        for row in selected
    )

    roi_rows = [
        row
        for row in selected
        if row.hypothetical_return_pct
        is not None
    ]

    roi_sample_size = len(roi_rows)

    total_profit = sum(
        row.hypothetical_profit or 0.0
        for row in roi_rows
    )

    average_return = mean_or_zero(
        row.hypothetical_return_pct or 0.0
        for row in roi_rows
    )

    (
        status,
        recommendation,
        reason,
    ) = sample_status(
        sample_size=sample_size,
        total_pool=total_pool,
    )

    score = composite_score(
        accuracy=accuracy,
        brier=brier,
        log_loss=log_loss,
        retention_rate=retention_rate,
        average_return=average_return,
        sample_size=sample_size,
        total_pool=total_pool,
    )

    evaluation_key = stable_key(
        "methodology-evaluation-v1",
        candidate.candidate_key,
    )

    return CandidateEvaluation(
        evaluation_key=evaluation_key,
        candidate_key=candidate.candidate_key,
        candidate_name=candidate.candidate_name,
        minimum_confidence=(
            candidate.minimum_confidence
        ),
        minimum_decision_score=(
            candidate.minimum_decision_score
        ),
        minimum_actionability_score=(
            candidate.minimum_actionability_score
        ),
        minimum_trust_score=(
            candidate.minimum_trust_score
        ),
        minimum_entry_quality_score=(
            candidate.minimum_entry_quality_score
        ),
        minimum_market_structure_score=(
            candidate.minimum_market_structure_score
        ),
        minimum_data_quality_score=(
            candidate.minimum_data_quality_score
        ),
        is_baseline=candidate.is_baseline,
        total_resolved_pool=total_pool,
        selected_sample_size=sample_size,
        excluded_sample_size=excluded,
        retention_rate=retention_rate,
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        accuracy=accuracy,
        average_confidence=(
            average_confidence
        ),
        calibration_gap=calibration_gap,
        brier_score=brier,
        log_loss=log_loss,
        roi_sample_size=roi_sample_size,
        total_hypothetical_profit=(
            total_profit
        ),
        average_hypothetical_return_pct=(
            average_return
        ),
        composite_score=score,
        sample_status=status,
        recommendation_status=(
            recommendation
        ),
        recommendation_reason=reason,
        rank_position=0,
        calculated_at=calculated_at,
    )


def rank_evaluations(
    evaluations: list[
        CandidateEvaluation
    ],
) -> list[CandidateEvaluation]:
    ordered = sorted(
        evaluations,
        key=lambda row: (
            -row.composite_score,
            -row.selected_sample_size,
            -row.accuracy,
            row.brier_score,
            row.log_loss,
            -row.is_baseline,
            row.candidate_name,
        ),
    )

    ranked: list[
        CandidateEvaluation
    ] = []

    for rank, row in enumerate(
        ordered,
        start=1,
    ):
        ranked.append(
            CandidateEvaluation(
                evaluation_key=(
                    row.evaluation_key
                ),
                candidate_key=row.candidate_key,
                candidate_name=row.candidate_name,
                minimum_confidence=(
                    row.minimum_confidence
                ),
                minimum_decision_score=(
                    row.minimum_decision_score
                ),
                minimum_actionability_score=(
                    row.minimum_actionability_score
                ),
                minimum_trust_score=(
                    row.minimum_trust_score
                ),
                minimum_entry_quality_score=(
                    row.minimum_entry_quality_score
                ),
                minimum_market_structure_score=(
                    row.minimum_market_structure_score
                ),
                minimum_data_quality_score=(
                    row.minimum_data_quality_score
                ),
                is_baseline=row.is_baseline,
                total_resolved_pool=(
                    row.total_resolved_pool
                ),
                selected_sample_size=(
                    row.selected_sample_size
                ),
                excluded_sample_size=(
                    row.excluded_sample_size
                ),
                retention_rate=(
                    row.retention_rate
                ),
                correct_count=row.correct_count,
                incorrect_count=(
                    row.incorrect_count
                ),
                accuracy=row.accuracy,
                average_confidence=(
                    row.average_confidence
                ),
                calibration_gap=(
                    row.calibration_gap
                ),
                brier_score=row.brier_score,
                log_loss=row.log_loss,
                roi_sample_size=(
                    row.roi_sample_size
                ),
                total_hypothetical_profit=(
                    row.total_hypothetical_profit
                ),
                average_hypothetical_return_pct=(
                    row.average_hypothetical_return_pct
                ),
                composite_score=(
                    row.composite_score
                ),
                sample_status=(
                    row.sample_status
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

    return ranked


def build_evaluations(
    candidates: list[
        CandidateMethodology
    ],
    observations: list[
        OptimizationObservation
    ],
) -> list[CandidateEvaluation]:
    calculated_at = utc_now()

    evaluations = [
        evaluate_candidate(
            candidate=candidate,
            observations=observations,
            calculated_at=calculated_at,
        )
        for candidate in candidates
    ]

    return rank_evaluations(
        evaluations
    )


def save_evaluations(
    connection: sqlite3.Connection,
    evaluations: list[
        CandidateEvaluation
    ],
) -> int:
    updated_at = utc_now()

    sql = """
        INSERT INTO
        methodology_optimization_candidates (
            evaluation_key,
            candidate_key,
            candidate_name,

            minimum_confidence,
            minimum_decision_score,
            minimum_actionability_score,
            minimum_trust_score,
            minimum_entry_quality_score,
            minimum_market_structure_score,
            minimum_data_quality_score,

            is_baseline,

            total_resolved_pool,
            selected_sample_size,
            excluded_sample_size,
            retention_rate,

            correct_count,
            incorrect_count,
            accuracy,

            average_confidence,
            calibration_gap,

            brier_score,
            log_loss,

            roi_sample_size,
            total_hypothetical_profit,
            average_hypothetical_return_pct,

            composite_score,

            sample_status,
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
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?
        )
        ON CONFLICT(evaluation_key)
        DO UPDATE SET
            total_resolved_pool =
                excluded.total_resolved_pool,

            selected_sample_size =
                excluded.selected_sample_size,

            excluded_sample_size =
                excluded.excluded_sample_size,

            retention_rate =
                excluded.retention_rate,

            correct_count =
                excluded.correct_count,

            incorrect_count =
                excluded.incorrect_count,

            accuracy =
                excluded.accuracy,

            average_confidence =
                excluded.average_confidence,

            calibration_gap =
                excluded.calibration_gap,

            brier_score =
                excluded.brier_score,

            log_loss =
                excluded.log_loss,

            roi_sample_size =
                excluded.roi_sample_size,

            total_hypothetical_profit =
                excluded.total_hypothetical_profit,

            average_hypothetical_return_pct =
                excluded.average_hypothetical_return_pct,

            composite_score =
                excluded.composite_score,

            sample_status =
                excluded.sample_status,

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
            row.candidate_key,
            row.candidate_name,

            row.minimum_confidence,
            row.minimum_decision_score,
            row.minimum_actionability_score,
            row.minimum_trust_score,
            row.minimum_entry_quality_score,
            row.minimum_market_structure_score,
            row.minimum_data_quality_score,

            row.is_baseline,

            row.total_resolved_pool,
            row.selected_sample_size,
            row.excluded_sample_size,
            row.retention_rate,

            row.correct_count,
            row.incorrect_count,
            row.accuracy,

            row.average_confidence,
            row.calibration_gap,

            row.brier_score,
            row.log_loss,

            row.roi_sample_size,
            row.total_hypothetical_profit,
            row.average_hypothetical_return_pct,

            row.composite_score,

            row.sample_status,
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


def save_run_start(
    connection: sqlite3.Connection,
    run_id: str,
    mode: str,
    started_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO methodology_optimization_runs (
            run_id,
            engine_version,
            mode,
            started_at,
            optimization_status,
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
        OptimizationObservation
    ],
    candidates: list[
        CandidateMethodology
    ],
    evaluations: list[
        CandidateEvaluation
    ],
    saved_candidates: int,
    duration_seconds: float,
) -> None:
    eligible = sum(
        1
        for row in evaluations
        if row.recommendation_status
        in {
            "ELIGIBLE_FOR_REVIEW",
            "STRONG_CANDIDATE",
        }
    )

    optimization_status = (
        "INSUFFICIENT_SAMPLE"
        if len(observations)
        < MINIMUM_OPTIMIZATION_SAMPLE
        else "ACTIVE_RESEARCH"
    )

    connection.execute(
        """
        UPDATE methodology_optimization_runs
        SET
            completed_at = ?,
            resolved_observations = ?,
            candidate_definitions = ?,
            candidate_evaluations = ?,
            eligible_candidates = ?,
            saved_candidates = ?,
            duration_seconds = ?,
            optimization_status = ?,
            status = 'COMPLETE'
        WHERE run_id = ?
        """,
        (
            utc_now(),
            len(observations),
            len(candidates),
            len(evaluations),
            eligible,
            saved_candidates,
            duration_seconds,
            optimization_status,
            run_id,
        ),
    )


def format_percent(
    value: float,
) -> str:
    return f"{value * 100:,.2f}%"


def print_candidate(
    row: CandidateEvaluation,
) -> None:
    baseline_text = (
        " BASELINE"
        if row.is_baseline
        else ""
    )

    if (
        row.total_resolved_pool
        < MINIMUM_OPTIMIZATION_SAMPLE
    ):
        rank_label = (
            f"E{row.rank_position:03d}"
        )
    else:
        rank_label = (
            f"{row.rank_position:>3}"
        )

    print(
        f"{rank_label}. "
        f"{row.candidate_name:<42} "
        f"n={row.selected_sample_size:<5} "
        f"acc={format_percent(row.accuracy):>8} "
        f"Brier={row.brier_score:.4f} "
        f"score={row.composite_score:>7.2f}"
        f"{baseline_text}"
    )

    print(
        f"     retention="
        f"{format_percent(row.retention_rate):>8} "
        f"confidence="
        f"{format_percent(row.average_confidence):>8} "
        f"logloss={row.log_loss:.4f} "
        f"status="
        f"{row.recommendation_status}"
    )


def print_summary(
    mode: str,
    run_id: str,
    observations: list[
        OptimizationObservation
    ],
    candidates: list[
        CandidateMethodology
    ],
    evaluations: list[
        CandidateEvaluation
    ],
    display_limit: int,
    duration_seconds: float,
) -> None:
    eligible = [
        row
        for row in evaluations
        if row.recommendation_status
        in {
            "ELIGIBLE_FOR_REVIEW",
            "STRONG_CANDIDATE",
        }
    ]

    optimization_status = (
        "INSUFFICIENT_SAMPLE"
        if len(observations)
        < MINIMUM_OPTIMIZATION_SAMPLE
        else "ACTIVE_RESEARCH"
    )

    print()
    print("=" * 125)
    print(
        "POLYMARKET INSTITUTIONAL METHODOLOGY "
        "OPTIMIZATION ENGINE v1.1"
    )
    print("=" * 125)
    print(f"Database:                    {DATABASE_PATH}")
    print(f"Mode:                        {mode}")
    print(f"Run ID:                      {run_id}")
    print(
        f"Resolved BUY/AVOID pool:     "
        f"{len(observations):,}"
    )
    print(
        f"Candidate methodologies:     "
        f"{len(candidates):,}"
    )
    print(
        f"Candidate evaluations:       "
        f"{len(evaluations):,}"
    )
    print(
        f"Eligible for review:         "
        f"{len(eligible):,}"
    )
    print(
        f"Optimization status:         "
        f"{optimization_status}"
    )
    print(
        f"Duration:                    "
        f"{duration_seconds:,.3f}s"
    )
    print("=" * 125)

    print()
    if len(observations) < (
        MINIMUM_OPTIMIZATION_SAMPLE
    ):
        print(
            "EXPLORATORY CANDIDATE BOARD"
        )
        print(
            "E-prefix = exploratory order, "
            "not an actionable methodology rank."
        )
    else:
        print("TOP CANDIDATE BOARD")

    print("-" * 125)

    for row in evaluations[
        :display_limit
    ]:
        print_candidate(row)

    baseline = next(
        (
            row
            for row in evaluations
            if row.is_baseline
        ),
        None,
    )

    if baseline is not None:
        print()
        print("BASELINE")
        print("-" * 125)
        print_candidate(baseline)

    print()
    print("OPTIMIZATION INTERPRETATION")
    print("-" * 125)

    if len(observations) < (
        MINIMUM_OPTIMIZATION_SAMPLE
    ):
        needed = (
            MINIMUM_OPTIMIZATION_SAMPLE
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
            "Methodology recommendation:  "
            "NONE"
        )
        print(
            "Reason:                      "
            "Candidate order is exploratory "
            "and cannot justify threshold changes."
        )
        print(
            "Ranking label:               "
            "EXPLORATORY_RANK"
        )
        print(
            "Live methodology changes:    "
            "PROHIBITED"
        )
    else:
        print(
            "Status:                      "
            "ACTIVE_RESEARCH"
        )
        print(
            "Methodology recommendation:  "
            "MANUAL REVIEW REQUIRED"
        )
        print(
            "Live methodology changes:    "
            "NOT AUTOMATIC"
        )

    print()
    print("=" * 125)

    if mode == "DRY RUN":
        print(
            "Dry run complete. No optimization "
            "research was saved."
        )
    else:
        print(
            "Optimization candidate research "
            "was saved successfully."
        )

    print(
        "The Institutional Decision Engine "
        "was not modified."
    )
    print(
        "No candidate may be deployed without "
        "sufficient resolved evidence and "
        "manual approval."
    )

    if len(observations) < (
        MINIMUM_OPTIMIZATION_SAMPLE
    ):
        print(
            "Displayed E-ranks are exploratory "
            "ordering only."
        )

    print("=" * 125)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate candidate institutional "
            "decision methodologies."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Save candidate evaluations and "
            "optimization run metadata."
        ),
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_TOP_LIMIT,
        help=(
            "Number of ranked candidates "
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

        observations = load_observations(
            connection
        )

        candidates = build_candidate_grid()

        evaluations = build_evaluations(
            candidates=candidates,
            observations=observations,
        )

        saved_candidates = 0

        if args.apply:
            saved_candidates = (
                save_evaluations(
                    connection,
                    evaluations,
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
                candidates=candidates,
                evaluations=evaluations,
                saved_candidates=(
                    saved_candidates
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
            candidates=candidates,
            evaluations=evaluations,
            display_limit=display_limit,
            duration_seconds=(
                duration_seconds
            ),
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
