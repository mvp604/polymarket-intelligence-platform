from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_LOOKBACK_HOURS = 24
DEFAULT_DISPLAY_LIMIT = 30
DEFAULT_MIN_GROSS_FLOW = 1_000.0
DEFAULT_MIN_WALLETS = 2


# =============================================================================
# GENERAL HELPERS
# =============================================================================


def configure_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(minimum, min(value, maximum))


def divide(
    numerator: float,
    denominator: float,
    default: float = 0.0,
) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def format_probability(value: float) -> str:
    return f"{value:.1f}%"


def format_money(value: Any) -> str:
    amount = safe_float(value)

    if amount > 0:
        return f"+${amount:,.2f}"

    if amount < 0:
        return f"-${abs(amount):,.2f}"

    return "$0.00"


# =============================================================================
# DATABASE HELPERS
# =============================================================================


def connect_database() -> sqlite3.Connection:
    if not DB.exists():
        raise FileNotFoundError(f"Database not found: {DB}")

    connection = sqlite3.connect(DB, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    return connection


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table'
              AND name=?
            """,
            (table_name,),
        ).fetchone()
        is not None
    )


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    if not table_exists(connection, table_name):
        return set()

    return {
        clean_text(row["name"])
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def first_existing(
    columns: set[str],
    candidates: tuple[str, ...],
) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def require_table(
    connection: sqlite3.Connection,
    table_name: str,
) -> None:
    if not table_exists(connection, table_name):
        raise RuntimeError(
            f"Required table is missing: {table_name}"
        )


# =============================================================================
# TABLE CREATION
# =============================================================================


def create_tables() -> None:
    connection = connect_database()

    try:
        require_table(
            connection,
            "smart_money_flow_signals",
        )

        require_table(
            connection,
            "market_memory_snapshots",
        )

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS market_predictions (
                prediction_key TEXT PRIMARY KEY,

                condition_id TEXT NOT NULL,
                market_id TEXT,
                event_id TEXT,

                title TEXT,
                slug TEXT,
                event_slug TEXT,
                category TEXT,

                lookback_hours INTEGER NOT NULL,

                source_signal_key TEXT,
                source_snapshot_key TEXT,

                predicted_direction TEXT
                    NOT NULL DEFAULT 'NEUTRAL',

                research_probability REAL
                    NOT NULL DEFAULT 50,

                probability_edge REAL
                    NOT NULL DEFAULT 0,

                confidence_score REAL
                    NOT NULL DEFAULT 0,

                confidence_grade TEXT
                    NOT NULL DEFAULT 'LOW',

                prediction_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                recommended_action TEXT
                    NOT NULL DEFAULT 'PASS',

                smart_money_flow_score REAL
                    NOT NULL DEFAULT 0,

                market_memory_score REAL
                    NOT NULL DEFAULT 0,

                accumulation_score REAL
                    NOT NULL DEFAULT 0,

                distribution_score REAL
                    NOT NULL DEFAULT 0,

                consensus_strength REAL
                    NOT NULL DEFAULT 0,

                trusted_flow_score REAL
                    NOT NULL DEFAULT 0,

                persistence_score REAL
                    NOT NULL DEFAULT 0,

                breadth_score REAL
                    NOT NULL DEFAULT 0,

                velocity_score REAL
                    NOT NULL DEFAULT 0,

                acceleration_score REAL
                    NOT NULL DEFAULT 0,

                rotation_score REAL
                    NOT NULL DEFAULT 0,

                concentration_risk REAL
                    NOT NULL DEFAULT 0,

                whale_concentration REAL
                    NOT NULL DEFAULT 0,

                current_net_flow REAL
                    NOT NULL DEFAULT 0,

                current_gross_flow REAL
                    NOT NULL DEFAULT 0,

                current_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                qualified_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                watchlist_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                current_price REAL,
                average_trade_price REAL,

                data_completeness_score REAL
                    NOT NULL DEFAULT 0,

                model_disagreement_score REAL
                    NOT NULL DEFAULT 0,

                is_actionable INTEGER
                    NOT NULL DEFAULT 0,

                resolved INTEGER
                    NOT NULL DEFAULT 0,

                winning_outcome TEXT,

                positive_evidence_json TEXT,
                risk_flags_json TEXT,
                component_scores_json TEXT,
                metadata_json TEXT,

                predicted_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_predictions_rank
            ON market_predictions(
                is_actionable DESC,
                confidence_score DESC,
                research_probability DESC,
                predicted_at DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_predictions_condition
            ON market_predictions(
                condition_id,
                lookback_hours,
                predicted_at DESC
            );

            CREATE TABLE IF NOT EXISTS market_prediction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                prediction_key TEXT NOT NULL,
                condition_id TEXT NOT NULL,

                predicted_direction TEXT,
                research_probability REAL,
                probability_edge REAL,
                confidence_score REAL,
                confidence_grade TEXT,
                prediction_grade TEXT,
                recommended_action TEXT,

                smart_money_flow_score REAL,
                market_memory_score REAL,

                resolved INTEGER,
                winning_outcome TEXT,

                observed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_prediction_history_condition
            ON market_prediction_history(
                condition_id,
                observed_at DESC
            );

            CREATE TABLE IF NOT EXISTS market_prediction_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                lookback_hours INTEGER NOT NULL,

                flow_signals_loaded INTEGER
                    NOT NULL DEFAULT 0,

                predictions_saved INTEGER
                    NOT NULL DEFAULT 0,

                actionable_predictions INTEGER
                    NOT NULL DEFAULT 0,

                bullish_predictions INTEGER
                    NOT NULL DEFAULT 0,

                bearish_predictions INTEGER
                    NOT NULL DEFAULT 0,

                neutral_predictions INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            );
            """
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# SOURCE LOADERS
# =============================================================================


def latest_flow_signals(
    lookback_hours: int,
) -> list[dict[str, Any]]:
    connection = connect_database()

    try:
        latest_observed_at = connection.execute(
            """
            SELECT MAX(observed_at)
            FROM smart_money_flow_signals
            WHERE lookback_hours = ?
            """,
            (lookback_hours,),
        ).fetchone()[0]

        if not latest_observed_at:
            return []

        rows = connection.execute(
            """
            SELECT *
            FROM smart_money_flow_signals
            WHERE lookback_hours = ?
              AND observed_at = ?
            ORDER BY
                is_actionable DESC,
                smart_money_flow_score DESC,
                ABS(current_net_flow) DESC
            """,
            (
                lookback_hours,
                latest_observed_at,
            ),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        connection.close()


def latest_memory_by_condition(
    lookback_hours: int,
) -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        latest_snapshot_at = connection.execute(
            """
            SELECT MAX(snapshot_at)
            FROM market_memory_snapshots
            WHERE lookback_hours = ?
            """,
            (lookback_hours,),
        ).fetchone()[0]

        if not latest_snapshot_at:
            return {}

        rows = connection.execute(
            """
            SELECT *
            FROM market_memory_snapshots
            WHERE lookback_hours = ?
              AND snapshot_at = ?
            """,
            (
                lookback_hours,
                latest_snapshot_at,
            ),
        ).fetchall()

        return {
            clean_text(row["condition_id"]).lower(): dict(row)
            for row in rows
            if clean_text(row["condition_id"])
        }

    finally:
        connection.close()


def load_optional_market_scores() -> dict[str, dict[str, float]]:
    """
    Load optional market-level scores without assuming one exact schema.

    The engine deliberately treats these as secondary evidence. If a table
    is absent or cannot be mapped safely, prediction generation continues.
    """
    connection = connect_database()
    output: dict[str, dict[str, float]] = {}

    table_specs = (
        (
            "signal_fusion_results",
            (
                "condition_id",
                "market_id",
            ),
            (
                "fusion_score",
                "signal_score",
                "score",
            ),
            "signal_fusion_score",
        ),
        (
            "master_opportunities",
            (
                "condition_id",
                "market_id",
            ),
            (
                "opportunity_score",
                "master_score",
                "score",
            ),
            "master_opportunity_score",
        ),
        (
            "institutional_consensus",
            (
                "condition_id",
                "market_id",
            ),
            (
                "institutional_score",
                "consensus_score",
                "conviction_score",
            ),
            "institutional_consensus_score",
        ),
    )

    try:
        for (
            table_name,
            id_candidates,
            score_candidates,
            output_name,
        ) in table_specs:
            if not table_exists(connection, table_name):
                continue

            columns = table_columns(
                connection,
                table_name,
            )

            id_column = first_existing(
                columns,
                id_candidates,
            )

            score_column = first_existing(
                columns,
                score_candidates,
            )

            if id_column is None or score_column is None:
                continue

            rows = connection.execute(
                f"""
                SELECT
                    "{id_column}" AS condition_key,
                    "{score_column}" AS score_value
                FROM "{table_name}"
                """
            ).fetchall()

            for row in rows:
                condition_id = clean_text(
                    row["condition_key"]
                ).lower()

                if not condition_id:
                    continue

                output.setdefault(
                    condition_id,
                    {},
                )[output_name] = safe_float(
                    row["score_value"]
                )

        return output

    finally:
        connection.close()


# =============================================================================
# PREDICTION LOGIC
# =============================================================================


def logistic_probability(logit: float) -> float:
    bounded = max(
        -12.0,
        min(
            logit,
            12.0,
        ),
    )

    return (
        1.0
        / (
            1.0
            + math.exp(
                -bounded
            )
        )
        * 100.0
    )


def grade_from_confidence(
    score: float,
) -> str:
    if score >= 85:
        return "S"

    if score >= 75:
        return "A+"

    if score >= 65:
        return "A"

    if score >= 55:
        return "B"

    if score >= 45:
        return "WATCH"

    return "PASS"


def confidence_label(
    score: float,
) -> str:
    if score >= 75:
        return "HIGH"

    if score >= 55:
        return "MEDIUM"

    return "LOW"


def action_from_prediction(
    direction: str,
    probability: float,
    confidence_score: float,
    concentration_risk: float,
    data_completeness: float,
) -> str:
    edge = abs(
        probability
        - 50.0
    )

    if (
        data_completeness < 45
        or confidence_score < 45
    ):
        return "PASS"

    if concentration_risk >= 90:
        return "WATCH"

    if direction == "BULLISH":
        if probability >= 75 and confidence_score >= 72:
            return "STRONG YES LEAN"

        if probability >= 65 and confidence_score >= 60:
            return "YES LEAN"

    if direction == "BEARISH":
        if probability <= 25 and confidence_score >= 72:
            return "STRONG NO LEAN"

        if probability <= 35 and confidence_score >= 60:
            return "NO LEAN"

    if edge >= 8:
        return "WATCH"

    return "PASS"


def build_predictions(
    lookback_hours: int,
    minimum_gross_flow: float,
    minimum_wallets: int,
) -> tuple[
    list[dict[str, Any]],
    int,
]:
    flow_signals = latest_flow_signals(
        lookback_hours
    )

    if not flow_signals:
        raise RuntimeError(
            "No Smart Money Flow signals were found for the selected "
            f"{lookback_hours}-hour lookback."
        )

    memory_lookup = latest_memory_by_condition(
        lookback_hours
    )

    optional_scores = load_optional_market_scores()

    predicted_at = utc_now_iso()
    predictions: list[
        dict[str, Any]
    ] = []

    for signal in flow_signals:
        condition_id = clean_text(
            signal.get(
                "condition_id"
            )
        ).lower()

        if not condition_id:
            continue

        gross_flow = safe_float(
            signal.get(
                "current_gross_flow"
            )
        )

        wallet_count = safe_int(
            signal.get(
                "current_unique_wallet_count"
            )
        )

        if (
            gross_flow < minimum_gross_flow
            or wallet_count < minimum_wallets
        ):
            continue

        memory = memory_lookup.get(
            condition_id,
            {},
        )

        flow_score = safe_float(
            signal.get(
                "smart_money_flow_score"
            )
        )

        memory_score = safe_float(
            memory.get(
                "market_memory_score"
            )
        )

        accumulation_score = safe_float(
            signal.get(
                "accumulation_score"
            )
        )

        distribution_score = safe_float(
            signal.get(
                "distribution_score"
            )
        )

        consensus_strength = safe_float(
            signal.get(
                "consensus_strength"
            )
        )

        trusted_flow_score = safe_float(
            signal.get(
                "trusted_flow_score"
            )
        )

        persistence_score = safe_float(
            signal.get(
                "persistence_score"
            )
        )

        breadth_score = safe_float(
            signal.get(
                "breadth_score"
            )
        )

        velocity_score = safe_float(
            signal.get(
                "velocity_score"
            )
        )

        acceleration_score = safe_float(
            signal.get(
                "acceleration_score"
            )
        )

        rotation_score = safe_float(
            signal.get(
                "rotation_score"
            )
        )

        concentration_risk = safe_float(
            signal.get(
                "concentration_risk"
            )
        )

        whale_concentration = safe_float(
            signal.get(
                "whale_concentration"
            )
        )

        net_flow = safe_float(
            signal.get(
                "current_net_flow"
            )
        )

        flow_direction = clean_text(
            signal.get(
                "flow_direction"
            )
        ).upper()

        optional = optional_scores.get(
            condition_id,
            {},
        )

        optional_values = [
            safe_float(value)
            for value in optional.values()
            if value is not None
        ]

        optional_score = (
            sum(optional_values)
            / len(optional_values)
            if optional_values
            else 50.0
        )

        directional_balance = (
            accumulation_score
            - distribution_score
        )

        net_flow_ratio = divide(
            net_flow,
            max(
                gross_flow,
                1.0,
            ),
            0.0,
        )

        # Research probability is intentionally conservative.
        # It is not promoted as a calibrated probability until
        # resolution-based calibration has been completed.
        directional_logit = (
            directional_balance
            / 22.0
            + net_flow_ratio
            * 1.35
            + (
                consensus_strength
                - 50.0
            )
            / 90.0
            + (
                trusted_flow_score
                - 50.0
            )
            / 120.0
            + (
                flow_score
                - 50.0
            )
            / 130.0
            + (
                memory_score
                - 50.0
            )
            / 160.0
            + (
                optional_score
                - 50.0
            )
            / 220.0
            - (
                concentration_risk
                / 180.0
            )
        )

        if flow_direction == "OUTFLOW":
            directional_logit -= 0.35

        elif flow_direction == "INFLOW":
            directional_logit += 0.35

        raw_probability = logistic_probability(
            directional_logit
        )

        # Shrink toward 50 when breadth, completeness or trust is weak.
        source_count = 2 + len(
            optional_values
        )

        completeness_components = [
            100.0 if memory else 0.0,
            100.0 if signal else 0.0,
            clamp(
                wallet_count
                / 5.0
                * 100.0
            ),
            clamp(
                math.log1p(
                    gross_flow
                )
                / math.log1p(
                    100_000.0
                )
                * 100.0
            ),
            min(
                source_count
                / 5.0
                * 100.0,
                100.0,
            ),
        ]

        data_completeness = (
            sum(
                completeness_components
            )
            / len(
                completeness_components
            )
        )

        shrink_strength = clamp(
            data_completeness
            / 100.0,
            0.25,
            0.90,
        )

        research_probability = (
            50.0
            + (
                raw_probability
                - 50.0
            )
            * shrink_strength
        )

        model_components = [
            flow_score,
            memory_score,
            accumulation_score
            if net_flow >= 0
            else distribution_score,
            consensus_strength,
            trusted_flow_score,
            optional_score,
        ]

        model_average = (
            sum(
                model_components
            )
            / len(
                model_components
            )
        )

        model_variance = (
            sum(
                (
                    value
                    - model_average
                )
                ** 2
                for value in model_components
            )
            / len(
                model_components
            )
        )

        model_disagreement = clamp(
            math.sqrt(
                model_variance
            )
            * 2.0
        )

        confidence_score = clamp(
            data_completeness
            * 0.30
            + consensus_strength
            * 0.20
            + persistence_score
            * 0.15
            + breadth_score
            * 0.10
            + trusted_flow_score
            * 0.10
            + flow_score
            * 0.10
            + max(
                velocity_score,
                acceleration_score,
            )
            * 0.05
            - concentration_risk
            * 0.15
            - whale_concentration
            * 0.10
            - model_disagreement
            * 0.10
        )

        if research_probability >= 54:
            predicted_direction = "BULLISH"

        elif research_probability <= 46:
            predicted_direction = "BEARISH"

        else:
            predicted_direction = "NEUTRAL"

        confidence_grade = confidence_label(
            confidence_score
        )

        prediction_grade = grade_from_confidence(
            confidence_score
        )

        recommended_action = action_from_prediction(
            direction=predicted_direction,
            probability=research_probability,
            confidence_score=confidence_score,
            concentration_risk=max(
                concentration_risk,
                whale_concentration,
            ),
            data_completeness=data_completeness,
        )

        actionable = int(
            recommended_action
            in {
                "STRONG YES LEAN",
                "YES LEAN",
                "STRONG NO LEAN",
                "NO LEAN",
            }
        )

        positive_evidence: list[str] = []
        risk_flags: list[str] = []

        if consensus_strength >= 75:
            positive_evidence.append(
                "Strong directional wallet agreement"
            )

        if persistence_score >= 75:
            positive_evidence.append(
                "Persistent smart-money participation"
            )

        if trusted_flow_score >= 60:
            positive_evidence.append(
                "Trusted wallets dominate measured flow"
            )

        if wallet_count >= 5:
            positive_evidence.append(
                "Broad wallet participation"
            )

        if abs(
            net_flow_ratio
        ) >= 0.50:
            positive_evidence.append(
                "Large directional flow imbalance"
            )

        if concentration_risk >= 70:
            risk_flags.append(
                "High market-flow concentration"
            )

        if whale_concentration >= 70:
            risk_flags.append(
                "One wallet dominates observed flow"
            )

        if wallet_count < 3:
            risk_flags.append(
                "Limited wallet breadth"
            )

        if gross_flow < 10_000:
            risk_flags.append(
                "Low gross flow"
            )

        if model_disagreement >= 35:
            risk_flags.append(
                "Model components disagree materially"
            )

        if data_completeness < 60:
            risk_flags.append(
                "Incomplete prediction evidence"
            )

        prediction_key = (
            f"{condition_id}:"
            f"{lookback_hours}:"
            f"{predicted_at}"
        )

        current_price = (
            safe_float(
                memory.get(
                    "current_price"
                )
            )
            if memory.get(
                "current_price"
            )
            is not None
            else None
        )

        probability_edge = (
            research_probability
            - (
                current_price
                * 100.0
                if current_price is not None
                and 0 <= current_price <= 1
                else 50.0
            )
        )

        component_scores = {
            "flow_score": flow_score,
            "memory_score": memory_score,
            "accumulation_score": (
                accumulation_score
            ),
            "distribution_score": (
                distribution_score
            ),
            "consensus_strength": (
                consensus_strength
            ),
            "trusted_flow_score": (
                trusted_flow_score
            ),
            "persistence_score": (
                persistence_score
            ),
            "breadth_score": breadth_score,
            "velocity_score": velocity_score,
            "acceleration_score": (
                acceleration_score
            ),
            "rotation_score": rotation_score,
            "optional_scores": optional,
        }

        predictions.append(
            {
                "prediction_key": (
                    prediction_key
                ),
                "condition_id": condition_id,
                "market_id": clean_text(
                    signal.get(
                        "market_id"
                    )
                ),
                "event_id": clean_text(
                    signal.get(
                        "event_id"
                    )
                ),
                "title": clean_text(
                    signal.get(
                        "title"
                    )
                ),
                "slug": clean_text(
                    signal.get(
                        "slug"
                    )
                ),
                "event_slug": clean_text(
                    signal.get(
                        "event_slug"
                    )
                ),
                "category": clean_text(
                    signal.get(
                        "category"
                    )
                ),
                "lookback_hours": (
                    lookback_hours
                ),
                "source_signal_key": (
                    clean_text(
                        signal.get(
                            "signal_key"
                        )
                    )
                ),
                "source_snapshot_key": (
                    clean_text(
                        memory.get(
                            "snapshot_key"
                        )
                    )
                ),
                "predicted_direction": (
                    predicted_direction
                ),
                "research_probability": (
                    research_probability
                ),
                "probability_edge": (
                    probability_edge
                ),
                "confidence_score": (
                    confidence_score
                ),
                "confidence_grade": (
                    confidence_grade
                ),
                "prediction_grade": (
                    prediction_grade
                ),
                "recommended_action": (
                    recommended_action
                ),
                "smart_money_flow_score": (
                    flow_score
                ),
                "market_memory_score": (
                    memory_score
                ),
                "accumulation_score": (
                    accumulation_score
                ),
                "distribution_score": (
                    distribution_score
                ),
                "consensus_strength": (
                    consensus_strength
                ),
                "trusted_flow_score": (
                    trusted_flow_score
                ),
                "persistence_score": (
                    persistence_score
                ),
                "breadth_score": (
                    breadth_score
                ),
                "velocity_score": (
                    velocity_score
                ),
                "acceleration_score": (
                    acceleration_score
                ),
                "rotation_score": (
                    rotation_score
                ),
                "concentration_risk": (
                    concentration_risk
                ),
                "whale_concentration": (
                    whale_concentration
                ),
                "current_net_flow": (
                    net_flow
                ),
                "current_gross_flow": (
                    gross_flow
                ),
                "current_wallet_count": (
                    wallet_count
                ),
                "elite_wallet_count": (
                    safe_int(
                        memory.get(
                            "elite_wallet_count"
                        )
                    )
                ),
                "qualified_wallet_count": (
                    safe_int(
                        memory.get(
                            "qualified_wallet_count"
                        )
                    )
                ),
                "watchlist_wallet_count": (
                    safe_int(
                        memory.get(
                            "watchlist_wallet_count"
                        )
                    )
                ),
                "current_price": current_price,
                "average_trade_price": (
                    safe_float(
                        memory.get(
                            "average_trade_price"
                        )
                    )
                    if memory.get(
                        "average_trade_price"
                    )
                    is not None
                    else None
                ),
                "data_completeness_score": (
                    data_completeness
                ),
                "model_disagreement_score": (
                    model_disagreement
                ),
                "is_actionable": actionable,
                "resolved": safe_int(
                    signal.get(
                        "resolved"
                    )
                ),
                "winning_outcome": clean_text(
                    signal.get(
                        "winning_outcome"
                    )
                ),
                "positive_evidence_json": (
                    stable_json(
                        positive_evidence
                    )
                ),
                "risk_flags_json": (
                    stable_json(
                        risk_flags
                    )
                ),
                "component_scores_json": (
                    stable_json(
                        component_scores
                    )
                ),
                "metadata_json": stable_json(
                    {
                        "model_version": "1.0",
                        "probability_type": (
                            "UNCALIBRATED_RESEARCH_ESTIMATE"
                        ),
                        "important_warning": (
                            "Do not treat this as a calibrated true "
                            "probability until resolution-based "
                            "calibration is completed."
                        ),
                        "minimum_gross_flow": (
                            minimum_gross_flow
                        ),
                        "minimum_wallets": (
                            minimum_wallets
                        ),
                        "raw_probability": (
                            raw_probability
                        ),
                        "shrink_strength": (
                            shrink_strength
                        ),
                    }
                ),
                "predicted_at": predicted_at,
                "created_at": predicted_at,
                "updated_at": predicted_at,
            }
        )

    predictions.sort(
        key=lambda row: (
            row[
                "is_actionable"
            ],
            row[
                "confidence_score"
            ],
            abs(
                row[
                    "research_probability"
                ]
                - 50.0
            ),
            abs(
                row[
                    "current_net_flow"
                ]
            ),
        ),
        reverse=True,
    )

    return (
        predictions,
        len(flow_signals),
    )


# =============================================================================
# SAVE
# =============================================================================


PREDICTION_COLUMNS = [
    "prediction_key",
    "condition_id",
    "market_id",
    "event_id",
    "title",
    "slug",
    "event_slug",
    "category",
    "lookback_hours",
    "source_signal_key",
    "source_snapshot_key",
    "predicted_direction",
    "research_probability",
    "probability_edge",
    "confidence_score",
    "confidence_grade",
    "prediction_grade",
    "recommended_action",
    "smart_money_flow_score",
    "market_memory_score",
    "accumulation_score",
    "distribution_score",
    "consensus_strength",
    "trusted_flow_score",
    "persistence_score",
    "breadth_score",
    "velocity_score",
    "acceleration_score",
    "rotation_score",
    "concentration_risk",
    "whale_concentration",
    "current_net_flow",
    "current_gross_flow",
    "current_wallet_count",
    "elite_wallet_count",
    "qualified_wallet_count",
    "watchlist_wallet_count",
    "current_price",
    "average_trade_price",
    "data_completeness_score",
    "model_disagreement_score",
    "is_actionable",
    "resolved",
    "winning_outcome",
    "positive_evidence_json",
    "risk_flags_json",
    "component_scores_json",
    "metadata_json",
    "predicted_at",
    "created_at",
    "updated_at",
]


def build_insert_query(
    table_name: str,
    columns: list[str],
) -> str:
    names = ", ".join(
        f'"{column}"'
        for column in columns
    )

    placeholders = ", ".join(
        "?"
        for _ in columns
    )

    return (
        f'INSERT OR REPLACE INTO "{table_name}" '
        f'({names}) VALUES ({placeholders})'
    )


def save_predictions(
    predictions: list[dict[str, Any]],
) -> tuple[int, int]:
    connection = connect_database()

    prediction_query = build_insert_query(
        "market_predictions",
        PREDICTION_COLUMNS,
    )

    history_rows = 0

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        for row in predictions:
            connection.execute(
                prediction_query,
                tuple(
                    row[column]
                    for column in PREDICTION_COLUMNS
                ),
            )

            connection.execute(
                """
                INSERT INTO market_prediction_history (
                    prediction_key,
                    condition_id,
                    predicted_direction,
                    research_probability,
                    probability_edge,
                    confidence_score,
                    confidence_grade,
                    prediction_grade,
                    recommended_action,
                    smart_money_flow_score,
                    market_memory_score,
                    resolved,
                    winning_outcome,
                    observed_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
                """,
                (
                    row["prediction_key"],
                    row["condition_id"],
                    row["predicted_direction"],
                    row["research_probability"],
                    row["probability_edge"],
                    row["confidence_score"],
                    row["confidence_grade"],
                    row["prediction_grade"],
                    row["recommended_action"],
                    row["smart_money_flow_score"],
                    row["market_memory_score"],
                    row["resolved"],
                    row["winning_outcome"],
                    row["predicted_at"],
                ),
            )

            history_rows += 1

        connection.commit()

        return (
            len(predictions),
            history_rows,
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =============================================================================
# RUN LOGGING
# =============================================================================


def start_run(
    lookback_hours: int,
) -> tuple[int, datetime]:
    started_at = utc_now()
    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO market_prediction_runs (
                started_at,
                lookback_hours,
                status
            )
            VALUES (?, ?, 'RUNNING')
            """,
            (
                started_at.isoformat(),
                lookback_hours,
            ),
        )

        connection.commit()

        return (
            cursor.lastrowid,
            started_at,
        )

    finally:
        connection.close()


def finish_run(
    run_id: int,
    started_at: datetime,
    status: str,
    flow_signals_loaded: int,
    predictions: list[dict[str, Any]],
    predictions_saved: int,
    error_message: str = "",
) -> None:
    finished_at = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE market_prediction_runs
            SET
                finished_at=?,
                elapsed_seconds=?,
                flow_signals_loaded=?,
                predictions_saved=?,
                actionable_predictions=?,
                bullish_predictions=?,
                bearish_predictions=?,
                neutral_predictions=?,
                status=?,
                error_message=?
            WHERE id=?
            """,
            (
                finished_at.isoformat(),
                (
                    finished_at
                    - started_at
                ).total_seconds(),
                flow_signals_loaded,
                predictions_saved,
                sum(
                    1
                    for row in predictions
                    if row[
                        "is_actionable"
                    ]
                ),
                sum(
                    1
                    for row in predictions
                    if row[
                        "predicted_direction"
                    ]
                    == "BULLISH"
                ),
                sum(
                    1
                    for row in predictions
                    if row[
                        "predicted_direction"
                    ]
                    == "BEARISH"
                ),
                sum(
                    1
                    for row in predictions
                    if row[
                        "predicted_direction"
                    ]
                    == "NEUTRAL"
                ),
                status,
                error_message,
                run_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# DISPLAY
# =============================================================================


def display_summary(
    predictions: list[dict[str, Any]],
    flow_signals_loaded: int,
    display_limit: int,
) -> None:
    print()
    print("=" * 118)
    print("PREDICTION ENGINE SUMMARY")
    print("=" * 118)

    print(
        f"Flow signals loaded:            "
        f"{flow_signals_loaded}"
    )

    print(
        f"Predictions created:            "
        f"{len(predictions)}"
    )

    print(
        f"Actionable research leans:      "
        f"{sum(1 for row in predictions if row['is_actionable'])}"
    )

    print(
        f"Bullish / bearish / neutral:    "
        f"{sum(1 for row in predictions if row['predicted_direction'] == 'BULLISH')} "
        f"/ {sum(1 for row in predictions if row['predicted_direction'] == 'BEARISH')} "
        f"/ {sum(1 for row in predictions if row['predicted_direction'] == 'NEUTRAL')}"
    )

    print()
    print(
        "WARNING: research_probability is an uncalibrated model "
        "estimate until historical resolution calibration is complete."
    )

    print("=" * 118)

    print()
    print("TOP MARKET PREDICTIONS")

    for rank, row in enumerate(
        predictions[:display_limit],
        start=1,
    ):
        positive_evidence = json.loads(
            row[
                "positive_evidence_json"
            ]
        )

        risk_flags = json.loads(
            row[
                "risk_flags_json"
            ]
        )

        print()
        print("-" * 118)

        print(
            f"{rank}. "
            f"{row['title'] or row['slug'] or row['condition_id']}"
        )

        print("-" * 118)

        print(
            f"Research probability:           "
            f"{format_probability(row['research_probability'])}"
        )

        print(
            f"Direction / action:             "
            f"{row['predicted_direction']} "
            f"/ {row['recommended_action']}"
        )

        print(
            f"Confidence:                     "
            f"{row['confidence_score']:.1f} "
            f"/ {row['confidence_grade']} "
            f"/ grade {row['prediction_grade']}"
        )

        print(
            f"Flow / memory scores:           "
            f"{row['smart_money_flow_score']:.1f} "
            f"/ {row['market_memory_score']:.1f}"
        )

        print(
            f"Accumulation / distribution:    "
            f"{row['accumulation_score']:.1f} "
            f"/ {row['distribution_score']:.1f}"
        )

        print(
            f"Consensus / persistence:        "
            f"{row['consensus_strength']:.1f} "
            f"/ {row['persistence_score']:.1f}"
        )

        print(
            f"Wallets / gross flow:           "
            f"{row['current_wallet_count']} "
            f"/ ${row['current_gross_flow']:,.2f}"
        )

        print(
            f"Net flow:                       "
            f"{format_money(row['current_net_flow'])}"
        )

        print(
            f"Concentration / disagreement:   "
            f"{row['concentration_risk']:.1f} "
            f"/ {row['model_disagreement_score']:.1f}"
        )

        print(
            f"Data completeness:              "
            f"{row['data_completeness_score']:.1f}"
        )

        if row["current_price"] is not None:
            print(
                f"Current price / model edge:     "
                f"{row['current_price']:.4f} "
                f"/ {row['probability_edge']:+.1f} pts"
            )

        if positive_evidence:
            print(
                "Positive evidence:              "
                + ", ".join(
                    positive_evidence
                )
            )

        if risk_flags:
            print(
                "Risk flags:                     "
                + ", ".join(
                    risk_flags
                )
            )


# =============================================================================
# MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate conservative, uncalibrated research probability "
            "estimates from Smart Money Flow and Market Memory evidence."
        )
    )

    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=DEFAULT_LOOKBACK_HOURS,
    )

    parser.add_argument(
        "--minimum-gross-flow",
        type=float,
        default=DEFAULT_MIN_GROSS_FLOW,
    )

    parser.add_argument(
        "--minimum-wallets",
        type=int,
        default=DEFAULT_MIN_WALLETS,
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )

    return parser.parse_args()


def main() -> None:
    configure_utf8()
    arguments = parse_arguments()

    lookback_hours = max(
        arguments.lookback_hours,
        1,
    )

    minimum_gross_flow = max(
        arguments.minimum_gross_flow,
        0.0,
    )

    minimum_wallets = max(
        arguments.minimum_wallets,
        1,
    )

    print()
    print("=" * 118)
    print("POLYMARKET PREDICTION ENGINE v1")
    print("=" * 118)

    print(
        f"Database:                    {DB}"
    )

    print(
        f"Lookback:                    "
        f"{lookback_hours} hours"
    )

    print(
        f"Minimum gross flow:          "
        f"${minimum_gross_flow:,.2f}"
    )

    print(
        f"Minimum wallets:             "
        f"{minimum_wallets}"
    )

    print(
        "Probability status:          "
        "UNCALIBRATED RESEARCH ESTIMATE"
    )

    print(
        "Method:                     "
        "FLOW + MEMORY + TRUST + CONSENSUS + RISK SHRINKAGE"
    )

    print("=" * 118)

    create_tables()

    run_id, started_at = start_run(
        lookback_hours
    )

    predictions: list[
        dict[str, Any]
    ] = []

    flow_signals_loaded = 0
    predictions_saved = 0

    try:
        (
            predictions,
            flow_signals_loaded,
        ) = build_predictions(
            lookback_hours=(
                lookback_hours
            ),
            minimum_gross_flow=(
                minimum_gross_flow
            ),
            minimum_wallets=(
                minimum_wallets
            ),
        )

        if not predictions:
            raise RuntimeError(
                "No predictions passed the selected gross-flow "
                "and wallet thresholds."
            )

        (
            predictions_saved,
            _,
        ) = save_predictions(
            predictions
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            flow_signals_loaded=(
                flow_signals_loaded
            ),
            predictions=predictions,
            predictions_saved=(
                predictions_saved
            ),
        )

        display_summary(
            predictions=predictions,
            flow_signals_loaded=(
                flow_signals_loaded
            ),
            display_limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 118)
        print("PREDICTION ENGINE COMPLETE")
        print("=" * 118)

        print(
            "Current predictions:        "
            "market_predictions"
        )

        print(
            "Prediction history:         "
            "market_prediction_history"
        )

        print(
            "Run history:                "
            "market_prediction_runs"
        )

        print()
        print(
            "Next required validation: compare stored predictions "
            "against resolved outcomes before treating probabilities "
            "as calibrated."
        )

        print("=" * 118)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            flow_signals_loaded=(
                flow_signals_loaded
            ),
            predictions=predictions,
            predictions_saved=(
                predictions_saved
            ),
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()