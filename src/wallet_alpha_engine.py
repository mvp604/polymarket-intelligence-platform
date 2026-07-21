from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_DISPLAY_LIMIT = 25
MIN_EVENTS_FOR_RATING = 5


# =============================================================================
# GENERAL HELPERS
# =============================================================================


def configure_utf8() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)

        try:
            stream.reconfigure(
                encoding="utf-8",
                errors="replace",
            )
        except (AttributeError, OSError):
            pass


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def wallet_text(value: Any) -> str:
    return text(value).lower()


def number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def divide(
    numerator: float,
    denominator: float,
    default: float = 0.0,
) -> float:
    if denominator == 0:
        return default

    return numerator / denominator


def clamp(
    value: float,
    low: float = 0.0,
    high: float = 100.0,
) -> float:
    return max(low, min(value, high))


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def money(value: Any) -> str:
    amount = number(value)

    if amount > 0:
        return f"+${amount:,.2f}"

    if amount < 0:
        return f"-${abs(amount):,.2f}"

    return "$0.00"


def percentage(value: Any) -> str:
    return f"{number(value):.1%}"


# =============================================================================
# DATABASE
# =============================================================================


def connect() -> sqlite3.Connection:
    if not DB.exists():
        raise FileNotFoundError(
            f"Database not found: {DB}"
        )

    connection = sqlite3.connect(
        DB,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    connection.execute(
        f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}"
    )

    return connection


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


def require_tables(
    connection: sqlite3.Connection,
    names: list[str],
) -> None:
    missing = [
        name
        for name in names
        if not table_exists(
            connection,
            name,
        )
    ]

    if missing:
        raise RuntimeError(
            "Required tables are missing: "
            + ", ".join(missing)
        )


# =============================================================================
# TABLE CREATION
# =============================================================================


def create_tables() -> None:
    connection = connect()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS wallet_alpha_profiles (
                wallet TEXT PRIMARY KEY,

                alpha_score REAL
                    NOT NULL DEFAULT 0,

                alpha_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                data_confidence TEXT
                    NOT NULL DEFAULT 'VERY LOW',

                trade_event_count INTEGER
                    NOT NULL DEFAULT 0,

                reconstructed_position_count INTEGER
                    NOT NULL DEFAULT 0,

                closed_position_count INTEGER
                    NOT NULL DEFAULT 0,

                open_position_count INTEGER
                    NOT NULL DEFAULT 0,

                estimated_realized_pnl REAL
                    NOT NULL DEFAULT 0,

                estimated_unrealized_pnl REAL
                    NOT NULL DEFAULT 0,

                total_estimated_pnl REAL
                    NOT NULL DEFAULT 0,

                estimated_buy_cost REAL
                    NOT NULL DEFAULT 0,

                estimated_sell_proceeds REAL
                    NOT NULL DEFAULT 0,

                realized_roi REAL
                    NOT NULL DEFAULT 0,

                total_roi REAL
                    NOT NULL DEFAULT 0,

                win_rate REAL
                    NOT NULL DEFAULT 0,

                resolved_positions INTEGER
                    NOT NULL DEFAULT 0,

                performance_score REAL
                    NOT NULL DEFAULT 50,

                dna_score REAL
                    NOT NULL DEFAULT 50,

                consistency_score REAL
                    NOT NULL DEFAULT 0,

                calibration_score REAL
                    NOT NULL DEFAULT 0,

                timing_score REAL
                    NOT NULL DEFAULT 50,

                entry_quality_score REAL
                    NOT NULL DEFAULT 50,

                exit_quality_score REAL
                    NOT NULL DEFAULT 50,

                position_management_score REAL
                    NOT NULL DEFAULT 50,

                conviction_quality_score REAL
                    NOT NULL DEFAULT 50,

                risk_adjusted_score REAL
                    NOT NULL DEFAULT 50,

                drawdown_control_score REAL
                    NOT NULL DEFAULT 50,

                scale_in_quality_score REAL
                    NOT NULL DEFAULT 50,

                scale_out_quality_score REAL
                    NOT NULL DEFAULT 50,

                specialization_bonus REAL
                    NOT NULL DEFAULT 0,

                independence_bonus REAL
                    NOT NULL DEFAULT 0,

                ledger_quality_score REAL
                    NOT NULL DEFAULT 0,

                sample_size_score REAL
                    NOT NULL DEFAULT 0,

                negative_pnl_penalty REAL
                    NOT NULL DEFAULT 0,

                low_sample_penalty REAL
                    NOT NULL DEFAULT 0,

                incomplete_ledger_penalty REAL
                    NOT NULL DEFAULT 0,

                total_penalty REAL
                    NOT NULL DEFAULT 0,

                primary_archetype TEXT,
                primary_category TEXT,
                sports_specialty TEXT,
                market_type_specialty TEXT,

                alpha_label TEXT,
                strengths_json TEXT,
                risks_json TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_wallet_alpha_profiles_rank
            ON wallet_alpha_profiles(
                alpha_score DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_wallet_alpha_profiles_grade
            ON wallet_alpha_profiles(
                alpha_grade,
                alpha_score DESC
            );

            CREATE TABLE IF NOT EXISTS wallet_alpha_components (
                component_key TEXT PRIMARY KEY,

                wallet TEXT NOT NULL,
                component_name TEXT NOT NULL,

                raw_value REAL,
                normalized_score REAL
                    NOT NULL DEFAULT 0,

                weight REAL
                    NOT NULL DEFAULT 0,

                weighted_contribution REAL
                    NOT NULL DEFAULT 0,

                explanation TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(
                    wallet
                )
                REFERENCES wallet_alpha_profiles(
                    wallet
                )
                ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
            idx_wallet_alpha_components_wallet
            ON wallet_alpha_components(
                wallet,
                weighted_contribution DESC
            );

            CREATE TABLE IF NOT EXISTS wallet_alpha_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                wallet TEXT NOT NULL,

                alpha_score REAL,
                alpha_grade TEXT,
                data_confidence TEXT,

                realized_roi REAL,
                total_roi REAL,
                performance_score REAL,
                dna_score REAL,
                timing_score REAL,
                entry_quality_score REAL,
                exit_quality_score REAL,
                risk_adjusted_score REAL,
                ledger_quality_score REAL,

                observed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_wallet_alpha_history_wallet
            ON wallet_alpha_history(
                wallet,
                observed_at DESC
            );

            CREATE TABLE IF NOT EXISTS wallet_alpha_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                wallets_loaded INTEGER
                    NOT NULL DEFAULT 0,

                profiles_saved INTEGER
                    NOT NULL DEFAULT 0,

                component_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_saved INTEGER
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
# SOURCE LOADING
# =============================================================================


def load_table_by_wallet(
    table_name: str,
) -> dict[str, dict[str, Any]]:
    connection = connect()

    try:
        if not table_exists(
            connection,
            table_name,
        ):
            return {}

        rows = connection.execute(
            f'SELECT * FROM "{table_name}"'
        ).fetchall()

        output: dict[
            str,
            dict[str, Any],
        ] = {}

        for row in rows:
            wallet = wallet_text(
                row["wallet"]
            )

            if wallet:
                output[wallet] = dict(row)

        return output

    finally:
        connection.close()


def load_trade_positions() -> dict[
    str,
    list[dict[str, Any]],
]:
    connection = connect()

    try:
        if not table_exists(
            connection,
            "wallet_trade_positions",
        ):
            return {}

        rows = connection.execute(
            """
            SELECT *
            FROM wallet_trade_positions
            """
        ).fetchall()

    finally:
        connection.close()

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in rows:
        wallet = wallet_text(
            row["wallet"]
        )

        if wallet:
            grouped[wallet].append(
                dict(row)
            )

    return grouped


# =============================================================================
# SCORING HELPERS
# =============================================================================


def grade_from_score(
    score: float,
    event_count: int,
) -> str:
    if event_count < MIN_EVENTS_FOR_RATING:
        return "UNRATED"

    if score >= 90:
        return "S+"

    if score >= 82:
        return "S"

    if score >= 74:
        return "A+"

    if score >= 66:
        return "A"

    if score >= 58:
        return "B"

    if score >= 48:
        return "C"

    return "PASS"


def confidence_label(
    ledger_quality_score: float,
    event_count: int,
    closed_positions: int,
) -> str:
    combined = (
        ledger_quality_score * 0.55
        + min(
            event_count / 100.0,
            1.0,
        )
        * 25.0
        + min(
            closed_positions / 25.0,
            1.0,
        )
        * 20.0
    )

    if combined >= 85:
        return "VERY HIGH"

    if combined >= 70:
        return "HIGH"

    if combined >= 55:
        return "MEDIUM"

    if combined >= 35:
        return "LOW"

    return "VERY LOW"


def score_roi(
    roi: float,
) -> float:
    capped = max(
        -1.0,
        min(
            roi,
            1.5,
        ),
    )

    return clamp(
        50.0
        + capped
        * 35.0
    )


def score_drawdown_control(
    realized_pnl: float,
    unrealized_pnl: float,
    buy_cost: float,
) -> float:
    downside = abs(
        min(
            realized_pnl
            + unrealized_pnl,
            0.0,
        )
    )

    downside_ratio = divide(
        downside,
        max(
            buy_cost,
            1.0,
        ),
        0.0,
    )

    return clamp(
        100.0
        - downside_ratio
        * 100.0
    )


def score_position_management(
    positions: list[dict[str, Any]],
) -> tuple[
    float,
    float,
    float,
    float,
]:
    if not positions:
        return (
            50.0,
            50.0,
            50.0,
            50.0,
        )

    buy_events = sum(
        integer(
            row.get(
                "buy_event_count"
            )
        )
        for row in positions
    )

    sell_events = sum(
        integer(
            row.get(
                "sell_event_count"
            )
        )
        for row in positions
    )

    scale_ins = sum(
        integer(
            row.get(
                "scale_in_count"
            )
        )
        for row in positions
    )

    scale_outs = sum(
        integer(
            row.get(
                "scale_out_count"
            )
        )
        for row in positions
    )

    closed_positions = [
        row
        for row in positions
        if text(
            row.get(
                "position_status"
            )
        ).upper()
        == "CLOSED"
    ]

    profitable_closed = [
        row
        for row in closed_positions
        if number(
            row.get(
                "estimated_realized_pnl"
            )
        )
        > 0
    ]

    scale_in_rate = divide(
        scale_ins,
        max(
            buy_events,
            1,
        ),
    )

    scale_out_rate = divide(
        scale_outs,
        max(
            sell_events,
            1,
        ),
    )

    profitable_close_rate = divide(
        len(
            profitable_closed
        ),
        len(
            closed_positions
        ),
        0.0,
    )

    scale_in_quality = clamp(
        45.0
        + min(
            scale_in_rate,
            1.0,
        )
        * 20.0
        + profitable_close_rate
        * 20.0
    )

    scale_out_quality = clamp(
        45.0
        + min(
            scale_out_rate,
            1.0,
        )
        * 20.0
        + profitable_close_rate
        * 25.0
    )

    position_management = clamp(
        scale_in_quality
        * 0.40
        + scale_out_quality
        * 0.40
        + profitable_close_rate
        * 100.0
        * 0.20
    )

    exit_quality = clamp(
        40.0
        + profitable_close_rate
        * 50.0
        + min(
            scale_out_rate,
            1.0,
        )
        * 10.0
    )

    return (
        position_management,
        scale_in_quality,
        scale_out_quality,
        exit_quality,
    )


# =============================================================================
# ALPHA BUILD
# =============================================================================


COMPONENT_WEIGHTS = {
    "realized_roi": 0.18,
    "total_roi": 0.10,
    "performance": 0.16,
    "dna": 0.10,
    "consistency": 0.08,
    "calibration": 0.06,
    "timing": 0.08,
    "entry_quality": 0.07,
    "exit_quality": 0.06,
    "position_management": 0.05,
    "drawdown_control": 0.04,
    "ledger_quality": 0.02,
}


def build_profiles() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    ledger_lookup = load_table_by_wallet(
        "wallet_trade_ledger_summary"
    )

    if not ledger_lookup:
        raise RuntimeError(
            "wallet_trade_ledger_summary is empty or missing. "
            "Run wallet_trade_ledger.py first."
        )

    performance_lookup = load_table_by_wallet(
        "wallet_performance"
    )

    dna_lookup = load_table_by_wallet(
        "wallet_dna_profiles"
    )

    trade_positions = load_trade_positions()

    calculated_at = now_iso()

    profiles: list[
        dict[str, Any]
    ] = []

    components: list[
        dict[str, Any]
    ] = []

    for wallet, ledger in (
        ledger_lookup.items()
    ):
        performance = (
            performance_lookup.get(
                wallet,
                {},
            )
        )

        dna = dna_lookup.get(
            wallet,
            {},
        )

        positions = trade_positions.get(
            wallet,
            [],
        )

        trade_event_count = integer(
            ledger.get(
                "trade_event_count"
            )
        )

        reconstructed_position_count = integer(
            ledger.get(
                "reconstructed_position_count"
            )
        )

        open_position_count = integer(
            ledger.get(
                "open_position_count"
            )
        )

        closed_position_count = integer(
            ledger.get(
                "closed_position_count"
            )
        )

        estimated_realized_pnl = number(
            ledger.get(
                "estimated_realized_pnl"
            )
        )

        estimated_unrealized_pnl = number(
            ledger.get(
                "estimated_unrealized_pnl"
            )
        )

        total_estimated_pnl = number(
            ledger.get(
                "total_estimated_pnl"
            )
        )

        estimated_buy_cost = number(
            ledger.get(
                "estimated_buy_cost"
            )
        )

        estimated_sell_proceeds = number(
            ledger.get(
                "estimated_sell_proceeds"
            )
        )

        realized_roi = divide(
            estimated_realized_pnl,
            max(
                estimated_buy_cost,
                1.0,
            ),
            0.0,
        )

        total_roi = divide(
            total_estimated_pnl,
            max(
                estimated_buy_cost,
                1.0,
            ),
            0.0,
        )

        resolved_positions = integer(
            performance.get(
                "resolved_positions"
            )
        )

        win_rate = number(
            performance.get(
                "win_rate"
            )
        )

        performance_score = number(
            performance.get(
                "performance_score"
            ),
            50.0,
        )

        dna_score = number(
            dna.get(
                "dna_score"
            ),
            50.0,
        )

        consistency_score = number(
            performance.get(
                "consistency_score"
            ),
            50.0,
        )

        calibration_score = number(
            performance.get(
                "calibration_score"
            ),
            50.0,
        )

        entry_quality_score = number(
            performance.get(
                "entry_quality_score"
            ),
            50.0,
        )

        (
            position_management_score,
            scale_in_quality_score,
            scale_out_quality_score,
            exit_quality_score,
        ) = score_position_management(
            positions
        )

        timing_score = clamp(
            entry_quality_score
            * 0.55
            + position_management_score
            * 0.25
            + consistency_score
            * 0.20
        )

        conviction_quality_score = clamp(
            number(
                dna.get(
                    "conviction_score"
                ),
                50.0,
            )
            * 0.55
            + performance_score
            * 0.45
        )

        drawdown_control_score = (
            score_drawdown_control(
                estimated_realized_pnl,
                estimated_unrealized_pnl,
                estimated_buy_cost,
            )
        )

        roi_variance_proxy = abs(
            realized_roi
            - total_roi
        )

        risk_adjusted_score = clamp(
            score_roi(
                total_roi
            )
            * 0.50
            + consistency_score
            * 0.25
            + drawdown_control_score
            * 0.25
            - min(
                roi_variance_proxy,
                1.0,
            )
            * 10.0
        )

        ledger_quality_score = number(
            ledger.get(
                "complete_history_score"
            )
        )

        sample_size_score = clamp(
            math.log1p(
                trade_event_count
            )
            / math.log1p(500)
            * 100.0
        )

        specialization_score = number(
            dna.get(
                "specialization_score"
            )
        )

        independence_score = number(
            dna.get(
                "portfolio_independence_score"
            ),
            50.0,
        )

        specialization_bonus = max(
            specialization_score
            - 65.0,
            0.0,
        ) / 35.0 * 4.0

        independence_bonus = max(
            independence_score
            - 65.0,
            0.0,
        ) / 35.0 * 4.0

        component_scores = {
            "realized_roi": score_roi(
                realized_roi
            ),
            "total_roi": score_roi(
                total_roi
            ),
            "performance": performance_score,
            "dna": dna_score,
            "consistency": consistency_score,
            "calibration": calibration_score,
            "timing": timing_score,
            "entry_quality": entry_quality_score,
            "exit_quality": exit_quality_score,
            "position_management": (
                position_management_score
            ),
            "drawdown_control": (
                drawdown_control_score
            ),
            "ledger_quality": (
                ledger_quality_score
            ),
        }

        raw_alpha_score = sum(
            component_scores[name]
            * weight
            for name, weight
            in COMPONENT_WEIGHTS.items()
        )

        raw_alpha_score += (
            specialization_bonus
            + independence_bonus
        )

        negative_pnl_penalty = 0.0

        if total_estimated_pnl < 0:
            negative_ratio = divide(
                abs(
                    total_estimated_pnl
                ),
                max(
                    estimated_buy_cost,
                    1.0,
                ),
                0.0,
            )

            negative_pnl_penalty = clamp(
                negative_ratio
                * 25.0,
                0.0,
                25.0,
            )

        low_sample_penalty = 0.0

        if trade_event_count < 5:
            low_sample_penalty = 15.0

        elif trade_event_count < 15:
            low_sample_penalty = 8.0

        elif closed_position_count < 2:
            low_sample_penalty = 5.0

        incomplete_ledger_penalty = clamp(
            max(
                60.0
                - ledger_quality_score,
                0.0,
            )
            / 60.0
            * 12.0,
            0.0,
            12.0,
        )

        total_penalty = (
            negative_pnl_penalty
            + low_sample_penalty
            + incomplete_ledger_penalty
        )

        alpha_score = clamp(
            raw_alpha_score
            - total_penalty
        )

        alpha_grade = grade_from_score(
            alpha_score,
            trade_event_count,
        )

        data_confidence = (
            confidence_label(
                ledger_quality_score,
                trade_event_count,
                closed_position_count,
            )
        )

        if alpha_score >= 82:
            alpha_label = (
                "ELITE OBSERVED ALPHA"
            )

        elif alpha_score >= 74:
            alpha_label = (
                "STRONG OBSERVED ALPHA"
            )

        elif alpha_score >= 66:
            alpha_label = (
                "POSITIVE OBSERVED EDGE"
            )

        elif alpha_score >= 58:
            alpha_label = (
                "DEVELOPING EDGE"
            )

        elif alpha_score >= 48:
            alpha_label = (
                "UNPROVEN / MIXED"
            )

        else:
            alpha_label = (
                "NEGATIVE OR INSUFFICIENT EDGE"
            )

        strengths: list[str] = []
        risks: list[str] = []

        if realized_roi > 0.10:
            strengths.append(
                "Positive estimated realized ROI"
            )

        if total_roi > 0.10:
            strengths.append(
                "Positive total estimated ROI"
            )

        if performance_score >= 70:
            strengths.append(
                "Strong resolved-market performance"
            )

        if dna_score >= 74:
            strengths.append(
                "High-quality wallet DNA"
            )

        if consistency_score >= 70:
            strengths.append(
                "Consistent observed returns"
            )

        if drawdown_control_score >= 75:
            strengths.append(
                "Strong drawdown control"
            )

        if position_management_score >= 70:
            strengths.append(
                "Strong position management"
            )

        if total_estimated_pnl < 0:
            risks.append(
                "Negative estimated total PnL"
            )

        if realized_roi < 0:
            risks.append(
                "Negative estimated realized ROI"
            )

        if closed_position_count < 3:
            risks.append(
                "Limited closed-position sample"
            )

        if ledger_quality_score < 60:
            risks.append(
                "Incomplete inferred ledger"
            )

        if calibration_score < 45:
            risks.append(
                "Weak calibration evidence"
            )

        explanation = {
            "model_version": "1.0",
            "weights": COMPONENT_WEIGHTS,
            "important_limitations": [
                (
                    "This engine uses an inferred snapshot ledger, "
                    "not exchange-confirmed fills."
                ),
                (
                    "Estimated PnL may be distorted when several "
                    "real trades occur between scans."
                ),
                (
                    "Alpha score is a ranking score, not a "
                    "statistical estimate of true excess return."
                ),
                (
                    "Beta is intentionally excluded from v1 because "
                    "a valid market benchmark return series has not "
                    "yet been constructed."
                ),
            ],
            "bonuses": {
                "specialization_bonus": round(
                    specialization_bonus,
                    2,
                ),
                "independence_bonus": round(
                    independence_bonus,
                    2,
                ),
            },
            "penalties": {
                "negative_pnl_penalty": round(
                    negative_pnl_penalty,
                    2,
                ),
                "low_sample_penalty": round(
                    low_sample_penalty,
                    2,
                ),
                "incomplete_ledger_penalty": round(
                    incomplete_ledger_penalty,
                    2,
                ),
            },
        }

        profile = {
            "wallet": wallet,
            "alpha_score": round(
                alpha_score,
                1,
            ),
            "alpha_grade": alpha_grade,
            "data_confidence": (
                data_confidence
            ),
            "trade_event_count": (
                trade_event_count
            ),
            "reconstructed_position_count": (
                reconstructed_position_count
            ),
            "closed_position_count": (
                closed_position_count
            ),
            "open_position_count": (
                open_position_count
            ),
            "estimated_realized_pnl": (
                estimated_realized_pnl
            ),
            "estimated_unrealized_pnl": (
                estimated_unrealized_pnl
            ),
            "total_estimated_pnl": (
                total_estimated_pnl
            ),
            "estimated_buy_cost": (
                estimated_buy_cost
            ),
            "estimated_sell_proceeds": (
                estimated_sell_proceeds
            ),
            "realized_roi": realized_roi,
            "total_roi": total_roi,
            "win_rate": win_rate,
            "resolved_positions": (
                resolved_positions
            ),
            "performance_score": (
                performance_score
            ),
            "dna_score": dna_score,
            "consistency_score": (
                consistency_score
            ),
            "calibration_score": (
                calibration_score
            ),
            "timing_score": timing_score,
            "entry_quality_score": (
                entry_quality_score
            ),
            "exit_quality_score": (
                exit_quality_score
            ),
            "position_management_score": (
                position_management_score
            ),
            "conviction_quality_score": (
                conviction_quality_score
            ),
            "risk_adjusted_score": (
                risk_adjusted_score
            ),
            "drawdown_control_score": (
                drawdown_control_score
            ),
            "scale_in_quality_score": (
                scale_in_quality_score
            ),
            "scale_out_quality_score": (
                scale_out_quality_score
            ),
            "specialization_bonus": (
                specialization_bonus
            ),
            "independence_bonus": (
                independence_bonus
            ),
            "ledger_quality_score": (
                ledger_quality_score
            ),
            "sample_size_score": (
                sample_size_score
            ),
            "negative_pnl_penalty": (
                negative_pnl_penalty
            ),
            "low_sample_penalty": (
                low_sample_penalty
            ),
            "incomplete_ledger_penalty": (
                incomplete_ledger_penalty
            ),
            "total_penalty": (
                total_penalty
            ),
            "primary_archetype": text(
                dna.get(
                    "primary_archetype"
                )
            ),
            "primary_category": text(
                dna.get(
                    "primary_category"
                )
            ),
            "sports_specialty": text(
                dna.get(
                    "sports_specialty"
                )
            ),
            "market_type_specialty": text(
                dna.get(
                    "market_type_specialty"
                )
            ),
            "alpha_label": alpha_label,
            "strengths_json": stable_json(
                strengths
            ),
            "risks_json": stable_json(
                risks
            ),
            "explanation_json": stable_json(
                explanation
            ),
            "calculated_at": calculated_at,
            "updated_at": calculated_at,
        }

        profiles.append(profile)

        for component_name, weight in (
            COMPONENT_WEIGHTS.items()
        ):
            normalized_score = (
                component_scores[
                    component_name
                ]
            )

            components.append(
                {
                    "component_key": (
                        f"{wallet}:"
                        f"{component_name}"
                    ),
                    "wallet": wallet,
                    "component_name": (
                        component_name
                    ),
                    "raw_value": (
                        realized_roi
                        if component_name
                        == "realized_roi"
                        else (
                            total_roi
                            if component_name
                            == "total_roi"
                            else normalized_score
                        )
                    ),
                    "normalized_score": (
                        normalized_score
                    ),
                    "weight": weight,
                    "weighted_contribution": (
                        normalized_score
                        * weight
                    ),
                    "explanation": (
                        f"{component_name} contributes "
                        f"{normalized_score * weight:.2f} "
                        f"weighted points."
                    ),
                    "calculated_at": (
                        calculated_at
                    ),
                    "updated_at": (
                        calculated_at
                    ),
                }
            )

    profiles.sort(
        key=lambda row: (
            row["alpha_score"],
            row["data_confidence"],
            row["trade_event_count"],
        ),
        reverse=True,
    )

    return (
        profiles,
        components,
    )


# =============================================================================
# SAVING
# =============================================================================


PROFILE_COLUMNS = [
    "wallet",
    "alpha_score",
    "alpha_grade",
    "data_confidence",
    "trade_event_count",
    "reconstructed_position_count",
    "closed_position_count",
    "open_position_count",
    "estimated_realized_pnl",
    "estimated_unrealized_pnl",
    "total_estimated_pnl",
    "estimated_buy_cost",
    "estimated_sell_proceeds",
    "realized_roi",
    "total_roi",
    "win_rate",
    "resolved_positions",
    "performance_score",
    "dna_score",
    "consistency_score",
    "calibration_score",
    "timing_score",
    "entry_quality_score",
    "exit_quality_score",
    "position_management_score",
    "conviction_quality_score",
    "risk_adjusted_score",
    "drawdown_control_score",
    "scale_in_quality_score",
    "scale_out_quality_score",
    "specialization_bonus",
    "independence_bonus",
    "ledger_quality_score",
    "sample_size_score",
    "negative_pnl_penalty",
    "low_sample_penalty",
    "incomplete_ledger_penalty",
    "total_penalty",
    "primary_archetype",
    "primary_category",
    "sports_specialty",
    "market_type_specialty",
    "alpha_label",
    "strengths_json",
    "risks_json",
    "explanation_json",
    "calculated_at",
    "updated_at",
]


COMPONENT_COLUMNS = [
    "component_key",
    "wallet",
    "component_name",
    "raw_value",
    "normalized_score",
    "weight",
    "weighted_contribution",
    "explanation",
    "calculated_at",
    "updated_at",
]


def insert_query(
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
        f'INSERT INTO "{table_name}" '
        f'({names}) VALUES ({placeholders})'
    )


def save_profiles(
    profiles: list[dict[str, Any]],
    components: list[dict[str, Any]],
) -> tuple[int, int, int]:
    connection = connect()
    observed_at = now_iso()

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        connection.execute(
            "DELETE FROM wallet_alpha_components"
        )

        connection.execute(
            "DELETE FROM wallet_alpha_profiles"
        )

        profile_query = insert_query(
            "wallet_alpha_profiles",
            PROFILE_COLUMNS,
        )

        component_query = insert_query(
            "wallet_alpha_components",
            COMPONENT_COLUMNS,
        )

        for row in profiles:
            connection.execute(
                profile_query,
                tuple(
                    row[column]
                    for column
                    in PROFILE_COLUMNS
                ),
            )

            connection.execute(
                """
                INSERT INTO wallet_alpha_history (
                    wallet,
                    alpha_score,
                    alpha_grade,
                    data_confidence,
                    realized_roi,
                    total_roi,
                    performance_score,
                    dna_score,
                    timing_score,
                    entry_quality_score,
                    exit_quality_score,
                    risk_adjusted_score,
                    ledger_quality_score,
                    observed_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    row["wallet"],
                    row["alpha_score"],
                    row["alpha_grade"],
                    row[
                        "data_confidence"
                    ],
                    row["realized_roi"],
                    row["total_roi"],
                    row[
                        "performance_score"
                    ],
                    row["dna_score"],
                    row["timing_score"],
                    row[
                        "entry_quality_score"
                    ],
                    row[
                        "exit_quality_score"
                    ],
                    row[
                        "risk_adjusted_score"
                    ],
                    row[
                        "ledger_quality_score"
                    ],
                    observed_at,
                ),
            )

        for row in components:
            connection.execute(
                component_query,
                tuple(
                    row[column]
                    for column
                    in COMPONENT_COLUMNS
                ),
            )

        connection.commit()

        return (
            len(profiles),
            len(components),
            len(profiles),
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =============================================================================
# RUN LOGGING
# =============================================================================


def start_run() -> tuple[int, datetime]:
    started = now_utc()
    connection = connect()

    try:
        cursor = connection.execute(
            """
            INSERT INTO wallet_alpha_runs (
                started_at,
                status
            )
            VALUES (
                ?,
                'RUNNING'
            )
            """,
            (started.isoformat(),),
        )

        connection.commit()

        return (
            cursor.lastrowid,
            started,
        )

    finally:
        connection.close()


def finish_run(
    run_id: int,
    started: datetime,
    status: str,
    wallets_loaded: int,
    profiles_saved: int,
    component_rows_saved: int,
    history_rows_saved: int,
    error_message: str = "",
) -> None:
    finished = now_utc()
    connection = connect()

    try:
        connection.execute(
            """
            UPDATE wallet_alpha_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                wallets_loaded = ?,
                profiles_saved = ?,
                component_rows_saved = ?,
                history_rows_saved = ?,
                status = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                finished.isoformat(),
                (
                    finished
                    - started
                ).total_seconds(),
                wallets_loaded,
                profiles_saved,
                component_rows_saved,
                history_rows_saved,
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
    profiles: list[dict[str, Any]],
    components: list[dict[str, Any]],
    display_limit: int,
) -> None:
    print()
    print("=" * 112)
    print("WALLET ALPHA ENGINE SUMMARY")
    print("=" * 112)

    print(
        f"Wallets scored:                 "
        f"{len(profiles)}"
    )

    print(
        f"Component rows:                 "
        f"{len(components)}"
    )

    print(
        f"Rated wallets:                  "
        f"{sum(1 for row in profiles if row['alpha_grade'] != 'UNRATED')}"
    )

    print(
        f"Positive total estimated PnL:   "
        f"{sum(1 for row in profiles if row['total_estimated_pnl'] > 0)}"
    )

    print(
        f"Negative total estimated PnL:   "
        f"{sum(1 for row in profiles if row['total_estimated_pnl'] < 0)}"
    )

    print("=" * 112)

    print()
    print("TOP WALLET ALPHA PROFILES")

    for rank, row in enumerate(
        profiles[:display_limit],
        start=1,
    ):
        strengths = json.loads(
            row["strengths_json"]
        )

        risks = json.loads(
            row["risks_json"]
        )

        print()
        print("-" * 112)

        print(
            f"{rank}. {row['wallet']}"
        )

        print("-" * 112)

        print(
            f"Alpha score / grade:            "
            f"{row['alpha_score']:.1f} "
            f"/ {row['alpha_grade']}"
        )

        print(
            f"Alpha label:                    "
            f"{row['alpha_label']}"
        )

        print(
            f"Data confidence:                "
            f"{row['data_confidence']}"
        )

        print(
            f"Trade events / closed positions:"
            f" {row['trade_event_count']} "
            f"/ {row['closed_position_count']}"
        )

        print(
            f"Realized / total ROI:           "
            f"{percentage(row['realized_roi'])} "
            f"/ {percentage(row['total_roi'])}"
        )

        print(
            f"Estimated realized PnL:         "
            f"{money(row['estimated_realized_pnl'])}"
        )

        print(
            f"Total estimated PnL:            "
            f"{money(row['total_estimated_pnl'])}"
        )

        print(
            f"Performance / DNA:              "
            f"{row['performance_score']:.1f} "
            f"/ {row['dna_score']:.1f}"
        )

        print(
            f"Timing / entry / exit:          "
            f"{row['timing_score']:.1f} "
            f"/ {row['entry_quality_score']:.1f} "
            f"/ {row['exit_quality_score']:.1f}"
        )

        print(
            f"Risk-adjusted / drawdown:       "
            f"{row['risk_adjusted_score']:.1f} "
            f"/ {row['drawdown_control_score']:.1f}"
        )

        print(
            f"Ledger quality / penalty:       "
            f"{row['ledger_quality_score']:.1f} "
            f"/ -{row['total_penalty']:.1f}"
        )

        if strengths:
            print(
                "Strengths:                       "
                + ", ".join(
                    strengths
                )
            )

        if risks:
            print(
                "Risks:                           "
                + ", ".join(
                    risks
                )
            )


# =============================================================================
# MAIN
# =============================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rank wallets by observed alpha using the inferred "
            "trade ledger, performance, DNA, consistency, "
            "calibration and risk controls."
        )
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )

    return parser.parse_args()


def main() -> None:
    configure_utf8()
    arguments = parse_args()

    print()
    print("=" * 112)
    print("POLYMARKET WALLET ALPHA ENGINE v1")
    print("=" * 112)

    print(
        f"Database: {DB}"
    )

    print(
        "Method: inferred ledger + performance + DNA + risk controls"
    )

    create_tables()

    run_id, started = start_run()

    profiles: list[
        dict[str, Any]
    ] = []

    components: list[
        dict[str, Any]
    ] = []

    profiles_saved = 0
    components_saved = 0
    history_saved = 0

    try:
        (
            profiles,
            components,
        ) = build_profiles()

        (
            profiles_saved,
            components_saved,
            history_saved,
        ) = save_profiles(
            profiles,
            components,
        )

        finish_run(
            run_id=run_id,
            started=started,
            status="SUCCESS",
            wallets_loaded=(
                len(profiles)
            ),
            profiles_saved=(
                profiles_saved
            ),
            component_rows_saved=(
                components_saved
            ),
            history_rows_saved=(
                history_saved
            ),
        )

        display_summary(
            profiles,
            components,
            max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 112)
        print("WALLET ALPHA ENGINE COMPLETE")
        print("=" * 112)

        print(
            "Current alpha rankings were saved to "
            "wallet_alpha_profiles."
        )

        print(
            "Weighted component details were saved to "
            "wallet_alpha_components."
        )

        print(
            "Historical alpha snapshots were saved to "
            "wallet_alpha_history."
        )

        print(
            "Alpha scores are comparative research rankings, "
            "not calibrated estimates of true excess return."
        )

        print(
            "Beta is intentionally excluded until a valid "
            "benchmark return series is constructed."
        )

        print("=" * 112)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started=started,
            status="FAILED",
            wallets_loaded=(
                len(profiles)
            ),
            profiles_saved=(
                profiles_saved
            ),
            component_rows_saved=(
                components_saved
            ),
            history_rows_saved=(
                history_saved
            ),
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()