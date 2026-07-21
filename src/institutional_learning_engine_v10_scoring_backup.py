"""
Polymarket Institutional Learning Engine v1.0

Purpose
-------
Close the feedback loop between historical institutional decisions and
confirmed market outcomes.

The engine:

1. Reads prediction-time records from institutional_decision_history.
2. Resolves each selected outcome through mapped_market_results.
3. Falls back to market_resolution_outcomes when needed.
4. Preserves unresolved observations without guessing.
5. Calculates correctness, confidence calibration and hypothetical ROI.
6. Produces action-, score-band-, confidence-band- and methodology-level
   evaluations.
7. Runs in dry-run mode unless --apply is supplied.

Important
---------
This engine does not retrain or modify the Institutional Decision Engine.
It creates an auditable learning dataset that later calibration and
optimization engines can consume.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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


ENGINE_VERSION = "1.0"

ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = (
    ROOT
    / "database"
    / "polymarket.db"
)

CONFIRMED_STATUSES = {
    "RESOLVED",
    "LIKELY_RESOLVED",
    "WINNER",
    "LOSER",
}

ACTION_ORDER = {
    "BUY": 0,
    "WATCH": 1,
    "WAIT": 2,
    "PASS": 3,
    "AVOID": 4,
}

DEFAULT_STAKE = 100.0


@dataclass(frozen=True)
class LearningObservation:
    observation_key: str
    source_history_id: int
    source_run_id: str
    opportunity_key: str
    market_id: str
    title: str
    selected_outcome: str
    decision_action: str
    decision_grade: str
    decision_score: float
    actionability_score: float
    confidence: float
    weighted_trust_score: float
    entry_quality_score: float
    market_structure_score: float
    data_quality_score: float
    hard_veto: int
    methodology_version: str
    observed_at: str

    resolution_status: str
    resolution_evidence: str
    winning_outcome: str
    source_outcome_won: int | None
    source_outcome_lost: int | None
    settlement_price: float | None
    resolved_at: str
    match_method: str
    match_confidence: float

    prediction_probability: float
    actual_result: int | None
    is_correct: int | None
    brier_score: float | None
    hypothetical_stake: float
    hypothetical_profit: float | None
    hypothetical_return_pct: float | None
    evaluated_at: str


@dataclass(frozen=True)
class Evaluation:
    evaluation_key: str
    evaluation_type: str
    evaluation_group: str
    methodology_version: str
    sample_count: int
    resolved_count: int
    correct_count: int
    incorrect_count: int
    unresolved_count: int
    accuracy: float | None
    average_confidence: float | None
    calibration_gap: float | None
    brier_score: float | None
    total_hypothetical_profit: float | None
    average_return_pct: float | None
    sample_warning: str
    calculated_at: str


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def normalize_text(value: Any) -> str:
    text = clean_text(value).lower()

    return " ".join(
        text.replace("_", " ")
        .replace("-", " ")
        .split()
    )


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(parsed):
        return default

    return parsed


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def optional_int(
    value: Any,
) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(parsed):
        return None

    return parsed


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(
        minimum,
        min(value, maximum),
    )


def quote_identifier(
    value: str,
) -> str:
    return '"' + value.replace('"', '""') + '"'


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


def get_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    if not table_exists(
        connection,
        table_name,
    ):
        return set()

    rows = connection.execute(
        f"PRAGMA table_info("
        f"{quote_identifier(table_name)}"
        f")"
    ).fetchall()

    return {
        clean_text(row["name"])
        for row in rows
    }


def require_tables(
    connection: sqlite3.Connection,
) -> None:
    required = (
        "institutional_decision_history",
        "mapped_market_results",
        "market_resolution_outcomes",
    )

    missing = [
        table_name
        for table_name in required
        if not table_exists(
            connection,
            table_name,
        )
    ]

    if missing:
        raise RuntimeError(
            "Required tables are missing: "
            + ", ".join(missing)
        )


def create_learning_tables(
    connection: sqlite3.Connection,
) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS
        institutional_learning_observations (
            observation_key TEXT PRIMARY KEY,

            source_history_id INTEGER NOT NULL,
            source_run_id TEXT NOT NULL,

            opportunity_key TEXT NOT NULL,
            market_id TEXT NOT NULL,
            title TEXT NOT NULL,
            selected_outcome TEXT NOT NULL,

            decision_action TEXT NOT NULL,
            decision_grade TEXT NOT NULL,
            decision_score REAL NOT NULL,
            actionability_score REAL NOT NULL,
            confidence REAL NOT NULL,
            weighted_trust_score REAL NOT NULL,
            entry_quality_score REAL NOT NULL,
            market_structure_score REAL NOT NULL,
            data_quality_score REAL NOT NULL,
            hard_veto INTEGER NOT NULL,

            methodology_version TEXT NOT NULL,
            observed_at TEXT NOT NULL,

            resolution_status TEXT
                NOT NULL DEFAULT 'UNRESOLVED',

            resolution_evidence TEXT
                NOT NULL DEFAULT 'NONE',

            winning_outcome TEXT,

            source_outcome_won INTEGER,
            source_outcome_lost INTEGER,

            settlement_price REAL,
            resolved_at TEXT,

            match_method TEXT,
            match_confidence REAL NOT NULL DEFAULT 0,

            prediction_probability REAL NOT NULL,
            actual_result INTEGER,
            is_correct INTEGER,
            brier_score REAL,

            hypothetical_stake REAL NOT NULL,
            hypothetical_profit REAL,
            hypothetical_return_pct REAL,

            evaluated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            UNIQUE(
                source_history_id,
                methodology_version
            )
        );

        CREATE INDEX IF NOT EXISTS
        idx_learning_observations_market
        ON institutional_learning_observations(
            market_id,
            selected_outcome
        );

        CREATE INDEX IF NOT EXISTS
        idx_learning_observations_action
        ON institutional_learning_observations(
            decision_action,
            methodology_version,
            is_correct
        );

        CREATE INDEX IF NOT EXISTS
        idx_learning_observations_resolution
        ON institutional_learning_observations(
            resolution_status,
            actual_result
        );

        CREATE TABLE IF NOT EXISTS
        institutional_learning_evaluations (
            evaluation_key TEXT PRIMARY KEY,

            run_id TEXT NOT NULL,

            evaluation_type TEXT NOT NULL,
            evaluation_group TEXT NOT NULL,
            methodology_version TEXT NOT NULL,

            sample_count INTEGER NOT NULL,
            resolved_count INTEGER NOT NULL,
            correct_count INTEGER NOT NULL,
            incorrect_count INTEGER NOT NULL,
            unresolved_count INTEGER NOT NULL,

            accuracy REAL,
            average_confidence REAL,
            calibration_gap REAL,
            brier_score REAL,

            total_hypothetical_profit REAL,
            average_return_pct REAL,

            sample_warning TEXT NOT NULL,

            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS
        idx_learning_evaluations_group
        ON institutional_learning_evaluations(
            evaluation_type,
            evaluation_group,
            methodology_version
        );

        CREATE TABLE IF NOT EXISTS
        institutional_learning_runs (
            run_id TEXT PRIMARY KEY,

            engine_version TEXT NOT NULL,
            mode TEXT NOT NULL,

            started_at TEXT NOT NULL,
            completed_at TEXT,

            history_rows_loaded INTEGER
                NOT NULL DEFAULT 0,

            mapped_resolution_matches INTEGER
                NOT NULL DEFAULT 0,

            fallback_resolution_matches INTEGER
                NOT NULL DEFAULT 0,

            resolved_observations INTEGER
                NOT NULL DEFAULT 0,

            unresolved_observations INTEGER
                NOT NULL DEFAULT 0,

            correct_observations INTEGER
                NOT NULL DEFAULT 0,

            incorrect_observations INTEGER
                NOT NULL DEFAULT 0,

            observation_rows_saved INTEGER
                NOT NULL DEFAULT 0,

            evaluation_rows_saved INTEGER
                NOT NULL DEFAULT 0,

            duration_seconds REAL,
            status TEXT NOT NULL,
            error_message TEXT
        );
        """
    )


def load_decision_history(
    connection: sqlite3.Connection,
    limit: int | None,
) -> list[sqlite3.Row]:
    sql = """
        SELECT
            id,
            run_id,
            opportunity_key,
            market_id,
            title,
            outcome,
            decision_score,
            decision_grade,
            decision_action,
            actionability_score,
            confidence,
            weighted_trust_score,
            entry_quality_score,
            market_structure_score,
            data_quality_score,
            hard_veto,
            observed_at,
            methodology_version
        FROM institutional_decision_history
        ORDER BY observed_at, id
    """

    parameters: tuple[Any, ...] = ()

    if limit is not None:
        sql += "\nLIMIT ?"
        parameters = (limit,)

    return connection.execute(
        sql,
        parameters,
    ).fetchall()


def load_mapped_results(
    connection: sqlite3.Connection,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    rows = connection.execute(
        """
        SELECT
            source_table,
            source_market_id,
            source_title,
            source_outcome,
            gamma_market_id,
            condition_id,
            resolution_status,
            winning_outcome_name,
            source_outcome_normalized,
            winning_outcome_normalized,
            source_outcome_won,
            source_outcome_lost,
            settlement_price,
            match_method,
            match_confidence,
            resolved_at_detected,
            calculated_at
        FROM mapped_market_results
        """
    ).fetchall()

    lookup: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = {}

    for row in rows:
        record = dict(row)

        market_candidates = {
            normalize_text(
                record.get("source_market_id")
            ),
            normalize_text(
                record.get("condition_id")
            ),
            normalize_text(
                record.get("gamma_market_id")
            ),
        }

        outcome_candidates = {
            normalize_text(
                record.get("source_outcome")
            ),
            normalize_text(
                record.get(
                    "source_outcome_normalized"
                )
            ),
        }

        market_candidates.discard("")
        outcome_candidates.discard("")

        for market_id in market_candidates:
            for outcome in outcome_candidates:
                lookup.setdefault(
                    (market_id, outcome),
                    [],
                ).append(record)

    return lookup


def load_resolution_outcomes(
    connection: sqlite3.Connection,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    rows = connection.execute(
        """
        SELECT
            resolution_key,
            gamma_market_id,
            condition_id,
            outcome_name,
            winner,
            settlement_price,
            resolution_status,
            last_checked_at,
            updated_at
        FROM market_resolution_outcomes
        """
    ).fetchall()

    lookup: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = {}

    for row in rows:
        record = dict(row)

        market_candidates = {
            normalize_text(
                record.get("condition_id")
            ),
            normalize_text(
                record.get("gamma_market_id")
            ),
        }

        outcome_name = normalize_text(
            record.get("outcome_name")
        )

        market_candidates.discard("")

        if not outcome_name:
            continue

        for market_id in market_candidates:
            lookup.setdefault(
                (market_id, outcome_name),
                [],
            ).append(record)

    return lookup


def choose_best_record(
    records: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    candidate_records = list(records)

    if not candidate_records:
        return None

    def ranking(
        record: dict[str, Any],
    ) -> tuple[int, int, float, str]:
        status = clean_text(
            record.get("resolution_status")
        ).upper()

        won = optional_int(
            record.get("source_outcome_won")
        )

        lost = optional_int(
            record.get("source_outcome_lost")
        )

        winner = optional_int(
            record.get("winner")
        )

        terminal_label = int(
            won in {0, 1}
            or lost in {0, 1}
            or winner in {0, 1}
        )

        confirmed_status = int(
            status in CONFIRMED_STATUSES
        )

        confidence = safe_float(
            record.get("match_confidence")
        )

        timestamp = clean_text(
            record.get("calculated_at")
            or record.get("updated_at")
            or record.get("last_checked_at")
        )

        return (
            terminal_label,
            confirmed_status,
            confidence,
            timestamp,
        )

    return max(
        candidate_records,
        key=ranking,
    )


def decision_probability(
    confidence: float,
) -> float:
    normalized = confidence

    if normalized > 1:
        normalized /= 100.0

    return clamp(
        normalized,
        0.0,
        1.0,
    )


def calculate_profit(
    actual_result: int | None,
    prediction_probability: float,
    stake: float,
) -> tuple[
    float | None,
    float | None,
]:
    if actual_result is None:
        return None, None

    entry_price = clamp(
        prediction_probability,
        0.01,
        0.99,
    )

    shares = stake / entry_price

    settlement_value = (
        shares
        if actual_result == 1
        else 0.0
    )

    profit = settlement_value - stake

    return_pct = (
        profit / stake * 100.0
        if stake > 0
        else None
    )

    return (
        round(profit, 6),
        (
            round(return_pct, 6)
            if return_pct is not None
            else None
        ),
    )


def build_observations(
    history_rows: list[sqlite3.Row],
    mapped_lookup: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ],
    outcome_lookup: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ],
    stake: float,
) -> tuple[
    list[LearningObservation],
    dict[str, int],
]:
    evaluated_at = utc_now()

    observations: list[
        LearningObservation
    ] = []

    statistics_map = {
        "mapped_matches": 0,
        "fallback_matches": 0,
        "resolved": 0,
        "unresolved": 0,
        "correct": 0,
        "incorrect": 0,
    }

    for row in history_rows:
        market_id = clean_text(
            row["market_id"]
        )

        selected_outcome = clean_text(
            row["outcome"]
        )

        lookup_key = (
            normalize_text(market_id),
            normalize_text(selected_outcome),
        )

        mapped_record = choose_best_record(
            mapped_lookup.get(
                lookup_key,
                [],
            )
        )

        fallback_record = None

        resolution_status = "UNRESOLVED"
        resolution_evidence = "NONE"
        winning_outcome = ""
        source_outcome_won: int | None = None
        source_outcome_lost: int | None = None
        settlement_price: float | None = None
        resolved_at = ""
        match_method = ""
        match_confidence = 0.0

        if mapped_record is not None:
            source_outcome_won = optional_int(
                mapped_record.get(
                    "source_outcome_won"
                )
            )

            source_outcome_lost = optional_int(
                mapped_record.get(
                    "source_outcome_lost"
                )
            )

            resolution_status = clean_text(
                mapped_record.get(
                    "resolution_status"
                )
            ).upper() or "UNRESOLVED"

            winning_outcome = clean_text(
                mapped_record.get(
                    "winning_outcome_name"
                )
            )

            settlement_price = optional_float(
                mapped_record.get(
                    "settlement_price"
                )
            )

            resolved_at = clean_text(
                mapped_record.get(
                    "resolved_at_detected"
                )
            )

            match_method = clean_text(
                mapped_record.get(
                    "match_method"
                )
            )

            match_confidence = safe_float(
                mapped_record.get(
                    "match_confidence"
                )
            )

            if (
                source_outcome_won in {0, 1}
                or source_outcome_lost in {0, 1}
            ):
                resolution_evidence = (
                    "MAPPED_MARKET_RESULT"
                )

                statistics_map[
                    "mapped_matches"
                ] += 1

        if (
            source_outcome_won not in {0, 1}
            and source_outcome_lost not in {0, 1}
        ):
            fallback_record = choose_best_record(
                outcome_lookup.get(
                    lookup_key,
                    [],
                )
            )

            if fallback_record is not None:
                winner = optional_int(
                    fallback_record.get(
                        "winner"
                    )
                )

                fallback_status = clean_text(
                    fallback_record.get(
                        "resolution_status"
                    )
                ).upper()

                if (
                    winner in {0, 1}
                    and fallback_status
                    in CONFIRMED_STATUSES
                ):
                    source_outcome_won = winner
                    source_outcome_lost = (
                        1 - winner
                    )

                    resolution_status = (
                        fallback_status
                    )

                    settlement_price = (
                        optional_float(
                            fallback_record.get(
                                "settlement_price"
                            )
                        )
                    )

                    resolved_at = clean_text(
                        fallback_record.get(
                            "updated_at"
                        )
                        or fallback_record.get(
                            "last_checked_at"
                        )
                    )

                    match_method = (
                        "CONDITION_OUTCOME_FALLBACK"
                    )

                    match_confidence = 100.0

                    resolution_evidence = (
                        "MARKET_RESOLUTION_OUTCOME"
                    )

                    statistics_map[
                        "fallback_matches"
                    ] += 1

        actual_result: int | None = None

        if source_outcome_won in {0, 1}:
            actual_result = source_outcome_won
        elif source_outcome_lost in {0, 1}:
            actual_result = (
                1 - source_outcome_lost
            )

        prediction_probability = (
            decision_probability(
                safe_float(row["confidence"])
            )
        )

        is_correct = (
            actual_result
            if actual_result is not None
            else None
        )

        brier_score = (
            (
                prediction_probability
                - actual_result
            ) ** 2
            if actual_result is not None
            else None
        )

        hypothetical_profit, return_pct = (
            calculate_profit(
                actual_result=actual_result,
                prediction_probability=(
                    prediction_probability
                ),
                stake=stake,
            )
        )

        if actual_result is None:
            statistics_map["unresolved"] += 1
        else:
            statistics_map["resolved"] += 1

            if is_correct == 1:
                statistics_map["correct"] += 1
            else:
                statistics_map[
                    "incorrect"
                ] += 1

        observation_key = stable_key(
            "institutional-learning-v1",
            row["id"],
            row["run_id"],
            market_id,
            selected_outcome,
            row["observed_at"],
            row["methodology_version"],
        )

        observations.append(
            LearningObservation(
                observation_key=(
                    observation_key
                ),
                source_history_id=safe_int(
                    row["id"]
                ),
                source_run_id=clean_text(
                    row["run_id"]
                ),
                opportunity_key=clean_text(
                    row["opportunity_key"]
                ),
                market_id=market_id,
                title=clean_text(
                    row["title"]
                ),
                selected_outcome=(
                    selected_outcome
                ),
                decision_action=clean_text(
                    row["decision_action"]
                ).upper(),
                decision_grade=clean_text(
                    row["decision_grade"]
                ),
                decision_score=safe_float(
                    row["decision_score"]
                ),
                actionability_score=safe_float(
                    row["actionability_score"]
                ),
                confidence=safe_float(
                    row["confidence"]
                ),
                weighted_trust_score=safe_float(
                    row["weighted_trust_score"]
                ),
                entry_quality_score=safe_float(
                    row["entry_quality_score"]
                ),
                market_structure_score=(
                    safe_float(
                        row[
                            "market_structure_score"
                        ]
                    )
                ),
                data_quality_score=safe_float(
                    row["data_quality_score"]
                ),
                hard_veto=safe_int(
                    row["hard_veto"]
                ),
                methodology_version=clean_text(
                    row["methodology_version"]
                ),
                observed_at=clean_text(
                    row["observed_at"]
                ),
                resolution_status=(
                    resolution_status
                ),
                resolution_evidence=(
                    resolution_evidence
                ),
                winning_outcome=(
                    winning_outcome
                ),
                source_outcome_won=(
                    source_outcome_won
                ),
                source_outcome_lost=(
                    source_outcome_lost
                ),
                settlement_price=(
                    settlement_price
                ),
                resolved_at=resolved_at,
                match_method=match_method,
                match_confidence=(
                    match_confidence
                ),
                prediction_probability=(
                    prediction_probability
                ),
                actual_result=actual_result,
                is_correct=is_correct,
                brier_score=(
                    round(brier_score, 8)
                    if brier_score is not None
                    else None
                ),
                hypothetical_stake=stake,
                hypothetical_profit=(
                    hypothetical_profit
                ),
                hypothetical_return_pct=(
                    return_pct
                ),
                evaluated_at=evaluated_at,
            )
        )

    return observations, statistics_map


def score_band(
    score: float,
) -> str:
    lower = int(score // 5) * 5
    upper = lower + 4.99

    return (
        f"{lower:02d}-"
        f"{upper:05.2f}"
    )


def confidence_band(
    confidence: float,
) -> str:
    normalized = (
        confidence * 100.0
        if confidence <= 1
        else confidence
    )

    lower = int(normalized // 10) * 10
    upper = lower + 9.99

    return (
        f"{lower:02d}-"
        f"{upper:05.2f}"
    )


def sample_warning(
    resolved_count: int,
) -> str:
    if resolved_count == 0:
        return "NO_RESOLVED_SAMPLE"

    if resolved_count < 10:
        return "VERY_LOW_SAMPLE"

    if resolved_count < 30:
        return "LOW_SAMPLE"

    if resolved_count < 100:
        return "MODERATE_SAMPLE"

    return "ADEQUATE_SAMPLE"


def mean_or_none(
    values: Iterable[float | None],
) -> float | None:
    clean_values = [
        float(value)
        for value in values
        if value is not None
    ]

    if not clean_values:
        return None

    return statistics.fmean(
        clean_values
    )


def build_evaluation(
    evaluation_type: str,
    evaluation_group: str,
    methodology_version: str,
    rows: list[LearningObservation],
    calculated_at: str,
) -> Evaluation:
    resolved_rows = [
        row
        for row in rows
        if row.actual_result is not None
    ]

    correct_count = sum(
        row.is_correct == 1
        for row in resolved_rows
    )

    incorrect_count = sum(
        row.is_correct == 0
        for row in resolved_rows
    )

    resolved_count = len(
        resolved_rows
    )

    unresolved_count = (
        len(rows) - resolved_count
    )

    accuracy = (
        correct_count / resolved_count
        if resolved_count
        else None
    )

    average_confidence = mean_or_none(
        row.prediction_probability
        for row in resolved_rows
    )

    calibration_gap = (
        average_confidence - accuracy
        if (
            average_confidence is not None
            and accuracy is not None
        )
        else None
    )

    average_brier = mean_or_none(
        row.brier_score
        for row in resolved_rows
    )

    profits = [
        row.hypothetical_profit
        for row in resolved_rows
        if row.hypothetical_profit
        is not None
    ]

    returns = [
        row.hypothetical_return_pct
        for row in resolved_rows
        if row.hypothetical_return_pct
        is not None
    ]

    total_profit = (
        sum(profits)
        if profits
        else None
    )

    average_return = (
        statistics.fmean(returns)
        if returns
        else None
    )

    evaluation_key = stable_key(
        "institutional-learning-evaluation-v1",
        evaluation_type,
        evaluation_group,
        methodology_version,
    )

    return Evaluation(
        evaluation_key=evaluation_key,
        evaluation_type=(
            evaluation_type
        ),
        evaluation_group=(
            evaluation_group
        ),
        methodology_version=(
            methodology_version
        ),
        sample_count=len(rows),
        resolved_count=resolved_count,
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        unresolved_count=unresolved_count,
        accuracy=accuracy,
        average_confidence=(
            average_confidence
        ),
        calibration_gap=(
            calibration_gap
        ),
        brier_score=average_brier,
        total_hypothetical_profit=(
            total_profit
        ),
        average_return_pct=(
            average_return
        ),
        sample_warning=sample_warning(
            resolved_count
        ),
        calculated_at=calculated_at,
    )


def build_evaluations(
    observations: list[
        LearningObservation
    ],
) -> list[Evaluation]:
    calculated_at = utc_now()

    groups: dict[
        tuple[str, str, str],
        list[LearningObservation],
    ] = {}

    for row in observations:
        methodology = (
            row.methodology_version
            or "UNKNOWN"
        )

        group_definitions = (
            (
                "OVERALL",
                "ALL",
            ),
            (
                "ACTION",
                row.decision_action
                or "UNKNOWN",
            ),
            (
                "SCORE_BAND",
                score_band(
                    row.decision_score
                ),
            ),
            (
                "CONFIDENCE_BAND",
                confidence_band(
                    row.confidence
                ),
            ),
            (
                "GRADE",
                row.decision_grade
                or "UNKNOWN",
            ),
            (
                "VETO",
                (
                    "HARD_VETO"
                    if row.hard_veto
                    else "NO_HARD_VETO"
                ),
            ),
        )

        for evaluation_type, group in (
            group_definitions
        ):
            groups.setdefault(
                (
                    evaluation_type,
                    group,
                    methodology,
                ),
                [],
            ).append(row)

    return [
        build_evaluation(
            evaluation_type=key[0],
            evaluation_group=key[1],
            methodology_version=key[2],
            rows=rows,
            calculated_at=calculated_at,
        )
        for key, rows in sorted(
            groups.items()
        )
    ]


def observation_values(
    row: LearningObservation,
    updated_at: str,
) -> tuple[Any, ...]:
    return (
        row.observation_key,
        row.source_history_id,
        row.source_run_id,
        row.opportunity_key,
        row.market_id,
        row.title,
        row.selected_outcome,
        row.decision_action,
        row.decision_grade,
        row.decision_score,
        row.actionability_score,
        row.confidence,
        row.weighted_trust_score,
        row.entry_quality_score,
        row.market_structure_score,
        row.data_quality_score,
        row.hard_veto,
        row.methodology_version,
        row.observed_at,
        row.resolution_status,
        row.resolution_evidence,
        row.winning_outcome,
        row.source_outcome_won,
        row.source_outcome_lost,
        row.settlement_price,
        row.resolved_at,
        row.match_method,
        row.match_confidence,
        row.prediction_probability,
        row.actual_result,
        row.is_correct,
        row.brier_score,
        row.hypothetical_stake,
        row.hypothetical_profit,
        row.hypothetical_return_pct,
        row.evaluated_at,
        updated_at,
    )


def save_observations(
    connection: sqlite3.Connection,
    observations: list[
        LearningObservation
    ],
) -> int:
    updated_at = utc_now()

    sql = """
        INSERT INTO
        institutional_learning_observations (
            observation_key,
            source_history_id,
            source_run_id,
            opportunity_key,
            market_id,
            title,
            selected_outcome,
            decision_action,
            decision_grade,
            decision_score,
            actionability_score,
            confidence,
            weighted_trust_score,
            entry_quality_score,
            market_structure_score,
            data_quality_score,
            hard_veto,
            methodology_version,
            observed_at,
            resolution_status,
            resolution_evidence,
            winning_outcome,
            source_outcome_won,
            source_outcome_lost,
            settlement_price,
            resolved_at,
            match_method,
            match_confidence,
            prediction_probability,
            actual_result,
            is_correct,
            brier_score,
            hypothetical_stake,
            hypothetical_profit,
            hypothetical_return_pct,
            evaluated_at,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(observation_key)
        DO UPDATE SET
            resolution_status =
                excluded.resolution_status,
            resolution_evidence =
                excluded.resolution_evidence,
            winning_outcome =
                excluded.winning_outcome,
            source_outcome_won =
                excluded.source_outcome_won,
            source_outcome_lost =
                excluded.source_outcome_lost,
            settlement_price =
                excluded.settlement_price,
            resolved_at =
                excluded.resolved_at,
            match_method =
                excluded.match_method,
            match_confidence =
                excluded.match_confidence,
            actual_result =
                excluded.actual_result,
            is_correct =
                excluded.is_correct,
            brier_score =
                excluded.brier_score,
            hypothetical_profit =
                excluded.hypothetical_profit,
            hypothetical_return_pct =
                excluded.hypothetical_return_pct,
            evaluated_at =
                excluded.evaluated_at,
            updated_at =
                excluded.updated_at
    """

    connection.executemany(
        sql,
        [
            observation_values(
                row,
                updated_at,
            )
            for row in observations
        ],
    )

    return len(observations)


def save_evaluations(
    connection: sqlite3.Connection,
    run_id: str,
    evaluations: list[Evaluation],
) -> int:
    updated_at = utc_now()

    sql = """
        INSERT INTO
        institutional_learning_evaluations (
            evaluation_key,
            run_id,
            evaluation_type,
            evaluation_group,
            methodology_version,
            sample_count,
            resolved_count,
            correct_count,
            incorrect_count,
            unresolved_count,
            accuracy,
            average_confidence,
            calibration_gap,
            brier_score,
            total_hypothetical_profit,
            average_return_pct,
            sample_warning,
            calculated_at,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(evaluation_key)
        DO UPDATE SET
            run_id =
                excluded.run_id,
            sample_count =
                excluded.sample_count,
            resolved_count =
                excluded.resolved_count,
            correct_count =
                excluded.correct_count,
            incorrect_count =
                excluded.incorrect_count,
            unresolved_count =
                excluded.unresolved_count,
            accuracy =
                excluded.accuracy,
            average_confidence =
                excluded.average_confidence,
            calibration_gap =
                excluded.calibration_gap,
            brier_score =
                excluded.brier_score,
            total_hypothetical_profit =
                excluded.total_hypothetical_profit,
            average_return_pct =
                excluded.average_return_pct,
            sample_warning =
                excluded.sample_warning,
            calculated_at =
                excluded.calculated_at,
            updated_at =
                excluded.updated_at
    """

    values = [
        (
            row.evaluation_key,
            run_id,
            row.evaluation_type,
            row.evaluation_group,
            row.methodology_version,
            row.sample_count,
            row.resolved_count,
            row.correct_count,
            row.incorrect_count,
            row.unresolved_count,
            row.accuracy,
            row.average_confidence,
            row.calibration_gap,
            row.brier_score,
            row.total_hypothetical_profit,
            row.average_return_pct,
            row.sample_warning,
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
        institutional_learning_runs (
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
    completed_at: str,
    duration_seconds: float,
    history_rows_loaded: int,
    statistics_map: dict[str, int],
    observation_rows_saved: int,
    evaluation_rows_saved: int,
) -> None:
    connection.execute(
        """
        UPDATE institutional_learning_runs
        SET
            completed_at = ?,
            history_rows_loaded = ?,
            mapped_resolution_matches = ?,
            fallback_resolution_matches = ?,
            resolved_observations = ?,
            unresolved_observations = ?,
            correct_observations = ?,
            incorrect_observations = ?,
            observation_rows_saved = ?,
            evaluation_rows_saved = ?,
            duration_seconds = ?,
            status = 'COMPLETE'
        WHERE run_id = ?
        """,
        (
            completed_at,
            history_rows_loaded,
            statistics_map["mapped_matches"],
            statistics_map[
                "fallback_matches"
            ],
            statistics_map["resolved"],
            statistics_map["unresolved"],
            statistics_map["correct"],
            statistics_map["incorrect"],
            observation_rows_saved,
            evaluation_rows_saved,
            duration_seconds,
            run_id,
        ),
    )


def save_run_failure(
    connection: sqlite3.Connection,
    run_id: str,
    error_message: str,
) -> None:
    connection.execute(
        """
        UPDATE institutional_learning_runs
        SET
            completed_at = ?,
            status = 'FAILED',
            error_message = ?
        WHERE run_id = ?
        """,
        (
            utc_now(),
            error_message,
            run_id,
        ),
    )


def percent_text(
    value: float | None,
) -> str:
    if value is None:
        return "-"

    return f"{value * 100.0:,.2f}%"


def number_text(
    value: float | None,
) -> str:
    if value is None:
        return "-"

    return f"{value:,.4f}"


def print_summary(
    mode: str,
    run_id: str,
    history_count: int,
    observations: list[
        LearningObservation
    ],
    evaluations: list[Evaluation],
    statistics_map: dict[str, int],
    duration_seconds: float,
    display_limit: int,
) -> None:
    print()
    print("=" * 118)
    print(
        "POLYMARKET INSTITUTIONAL "
        "LEARNING ENGINE v1.0"
    )
    print("=" * 118)
    print(f"Database:                     {DATABASE_PATH}")
    print(f"Mode:                         {mode}")
    print(f"Run ID:                       {run_id}")
    print(f"Decision history rows:        {history_count:,}")
    print(
        "Mapped resolution matches:    "
        f"{statistics_map['mapped_matches']:,}"
    )
    print(
        "Fallback resolution matches:  "
        f"{statistics_map['fallback_matches']:,}"
    )
    print(
        "Resolved observations:        "
        f"{statistics_map['resolved']:,}"
    )
    print(
        "Unresolved observations:      "
        f"{statistics_map['unresolved']:,}"
    )
    print(
        "Correct / incorrect:          "
        f"{statistics_map['correct']:,} / "
        f"{statistics_map['incorrect']:,}"
    )
    print(
        f"Evaluation groups:            "
        f"{len(evaluations):,}"
    )
    print(
        f"Duration:                     "
        f"{duration_seconds:,.3f}s"
    )
    print("=" * 118)

    overall = [
        row
        for row in evaluations
        if (
            row.evaluation_type == "OVERALL"
            and row.evaluation_group == "ALL"
        )
    ]

    if overall:
        print()
        print("OVERALL METHODOLOGY PERFORMANCE")
        print("-" * 118)

        for row in overall:
            print(
                f"{row.methodology_version:<12} "
                f"sample={row.sample_count:>4} "
                f"resolved={row.resolved_count:>4} "
                f"accuracy={percent_text(row.accuracy):>9} "
                f"avg_conf={percent_text(row.average_confidence):>9} "
                f"gap={percent_text(row.calibration_gap):>9} "
                f"brier={number_text(row.brier_score):>8} "
                f"warning={row.sample_warning}"
            )

    action_rows = sorted(
        [
            row
            for row in evaluations
            if row.evaluation_type == "ACTION"
        ],
        key=lambda row: (
            row.methodology_version,
            ACTION_ORDER.get(
                row.evaluation_group,
                99,
            ),
        ),
    )

    if action_rows:
        print()
        print("ACTION PERFORMANCE")
        print("-" * 118)

        for row in action_rows:
            print(
                f"{row.methodology_version:<10} "
                f"{row.evaluation_group:<7} "
                f"sample={row.sample_count:>4} "
                f"resolved={row.resolved_count:>4} "
                f"accuracy={percent_text(row.accuracy):>9} "
                f"profit="
                f"{number_text(row.total_hypothetical_profit):>10} "
                f"warning={row.sample_warning}"
            )

    resolved_rows = [
        row
        for row in observations
        if row.actual_result is not None
    ]

    if resolved_rows:
        print()
        print("SAMPLE RESOLVED OBSERVATIONS")
        print("-" * 118)

        ranked = sorted(
            resolved_rows,
            key=lambda row: (
                -row.decision_score,
                row.title,
            ),
        )

        for index, row in enumerate(
            ranked[:display_limit],
            start=1,
        ):
            result = (
                "CORRECT"
                if row.is_correct == 1
                else "INCORRECT"
            )

            print(
                f"{index:>3}. "
                f"{result:<9} "
                f"{row.decision_action:<6} "
                f"score={row.decision_score:>6.2f} "
                f"confidence={row.confidence:>6.2f} "
                f"evidence={row.resolution_evidence}"
            )
            print(
                f"     {row.title} ? "
                f"{row.selected_outcome}"
            )
            print(
                f"     winner="
                f"{row.winning_outcome or '-'} "
                f"status={row.resolution_status} "
                f"match={row.match_method or '-'} "
                f"match_confidence="
                f"{row.match_confidence:,.2f}"
            )

    print()
    print("=" * 118)

    if mode == "DRY RUN":
        print(
            "Dry run complete. No learning "
            "observations or evaluations were saved."
        )
        print(
            "Review the results, then rerun "
            "with --apply."
        )
    else:
        print(
            "Learning observations and evaluations "
            "were saved successfully."
        )

    print(
        "Hypothetical ROI uses decision confidence "
        "as a provisional entry-price proxy."
    )
    print(
        "It must not be treated as realized trading "
        "performance until actual entry prices are stored."
    )
    print("=" * 118)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate historical institutional "
            "decisions against resolved outcomes."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Save observations, evaluations "
            "and run metadata."
        ),
    )

    parser.add_argument(
        "--history-limit",
        type=int,
        default=None,
        help=(
            "Optional maximum number of decision "
            "history rows to analyze."
        ),
    )

    parser.add_argument(
        "--stake",
        type=float,
        default=DEFAULT_STAKE,
        help=(
            "Hypothetical stake per resolved "
            "observation."
        ),
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=10,
        help=(
            "Maximum resolved observations "
            "displayed."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.history_limit is not None:
        if args.history_limit <= 0:
            raise SystemExit(
                "--history-limit must be "
                "greater than zero."
            )

    if args.stake <= 0:
        raise SystemExit(
            "--stake must be greater than zero."
        )

    if args.display_limit <= 0:
        raise SystemExit(
            "--display-limit must be "
            "greater than zero."
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

    run_started = False

    try:
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        require_tables(connection)

        if args.apply:
            create_learning_tables(
                connection
            )

            save_run_start(
                connection=connection,
                run_id=run_id,
                mode=mode,
                started_at=started_at,
            )

            connection.commit()
            run_started = True

        history_rows = load_decision_history(
            connection,
            args.history_limit,
        )

        mapped_lookup = load_mapped_results(
            connection
        )

        outcome_lookup = (
            load_resolution_outcomes(
                connection
            )
        )

        observations, statistics_map = (
            build_observations(
                history_rows=history_rows,
                mapped_lookup=mapped_lookup,
                outcome_lookup=outcome_lookup,
                stake=args.stake,
            )
        )

        evaluations = build_evaluations(
            observations
        )

        observation_rows_saved = 0
        evaluation_rows_saved = 0

        if args.apply:
            observation_rows_saved = (
                save_observations(
                    connection,
                    observations,
                )
            )

            evaluation_rows_saved = (
                save_evaluations(
                    connection,
                    run_id,
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
                completed_at=utc_now(),
                duration_seconds=(
                    duration_seconds
                ),
                history_rows_loaded=(
                    len(history_rows)
                ),
                statistics_map=(
                    statistics_map
                ),
                observation_rows_saved=(
                    observation_rows_saved
                ),
                evaluation_rows_saved=(
                    evaluation_rows_saved
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
            history_count=len(history_rows),
            observations=observations,
            evaluations=evaluations,
            statistics_map=statistics_map,
            duration_seconds=(
                duration_seconds
            ),
            display_limit=(
                args.display_limit
            ),
        )

    except Exception as error:
        if args.apply and run_started:
            try:
                save_run_failure(
                    connection,
                    run_id,
                    str(error),
                )

                connection.commit()
            except Exception:
                connection.rollback()

        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()
