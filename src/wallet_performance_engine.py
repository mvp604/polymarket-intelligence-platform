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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_DISPLAY_LIMIT = 25
MIN_RESOLVED_BETS_FOR_GRADE = 3


# =============================================================================
# GENERAL HELPERS
# =============================================================================


def configure_utf8_output() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)

        try:
            stream.reconfigure(
                encoding="utf-8",
                errors="replace",
            )
        except (AttributeError, OSError):
            pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_text(value: Any) -> str:
    return clean_text(value).casefold()


def normalize_wallet(value: Any) -> str:
    return clean_text(value).lower()


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
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


def safe_divide(
    numerator: float,
    denominator: float,
    default: float = 0.0,
) -> float:
    if denominator == 0:
        return default

    return numerator / denominator


def format_money(value: Any) -> str:
    number = safe_float(value)

    if number > 0:
        return f"+${number:,.2f}"

    if number < 0:
        return f"-${abs(number):,.2f}"

    return "$0.00"


def format_percentage(value: Any) -> str:
    return f"{safe_float(value):.1%}"


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


# =============================================================================
# DATABASE HELPERS
# =============================================================================


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    connection = sqlite3.connect(
        DATABASE_PATH,
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
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def require_tables(
    connection: sqlite3.Connection,
    table_names: list[str],
) -> None:
    missing = [
        table_name
        for table_name in table_names
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


# =============================================================================
# TABLE CREATION
# =============================================================================


def create_performance_tables() -> None:
    connection = connect_database()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS wallet_performance (
                wallet TEXT PRIMARY KEY,

                resolved_positions INTEGER
                    NOT NULL DEFAULT 0,

                wins INTEGER
                    NOT NULL DEFAULT 0,

                losses INTEGER
                    NOT NULL DEFAULT 0,

                unresolved_mapped_positions INTEGER
                    NOT NULL DEFAULT 0,

                win_rate REAL
                    NOT NULL DEFAULT 0,

                total_cost_basis REAL
                    NOT NULL DEFAULT 0,

                total_settlement_value REAL
                    NOT NULL DEFAULT 0,

                estimated_profit REAL
                    NOT NULL DEFAULT 0,

                estimated_roi REAL
                    NOT NULL DEFAULT 0,

                average_entry_price REAL
                    NOT NULL DEFAULT 0,

                average_winning_entry REAL,
                average_losing_entry REAL,

                average_edge_at_entry REAL
                    NOT NULL DEFAULT 0,

                profit_factor REAL,
                payoff_ratio REAL,

                weighted_brier_score REAL,
                calibration_score REAL,

                consistency_score REAL
                    NOT NULL DEFAULT 0,

                sample_size_score REAL
                    NOT NULL DEFAULT 0,

                profitability_score REAL
                    NOT NULL DEFAULT 0,

                accuracy_score REAL
                    NOT NULL DEFAULT 0,

                entry_quality_score REAL
                    NOT NULL DEFAULT 0,

                performance_score REAL
                    NOT NULL DEFAULT 0,

                performance_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                data_confidence TEXT
                    NOT NULL DEFAULT 'VERY LOW',

                mapped_market_count INTEGER
                    NOT NULL DEFAULT 0,

                first_resolved_scan_at TEXT,
                last_resolved_scan_at TEXT,

                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_wallet_performance_rank
            ON wallet_performance(
                performance_score DESC
            );

            CREATE TABLE IF NOT EXISTS wallet_performance_markets (
                performance_market_key TEXT PRIMARY KEY,

                wallet TEXT NOT NULL,

                scan_id INTEGER,
                scanned_at TEXT,

                market_id TEXT NOT NULL,
                title TEXT,
                selected_outcome TEXT,

                gamma_market_id TEXT,
                condition_id TEXT,

                resolution_status TEXT,
                winning_outcome_name TEXT,

                source_outcome_won INTEGER,
                source_outcome_lost INTEGER,

                shares REAL
                    NOT NULL DEFAULT 0,

                average_entry_price REAL
                    NOT NULL DEFAULT 0,

                cost_basis REAL
                    NOT NULL DEFAULT 0,

                settlement_price REAL,

                settlement_value REAL,
                estimated_profit REAL,
                estimated_roi REAL,

                brier_score REAL,

                match_method TEXT,
                match_confidence REAL,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_wallet_performance_markets_wallet
            ON wallet_performance_markets(
                wallet,
                source_outcome_won
            );

            CREATE INDEX IF NOT EXISTS
            idx_wallet_performance_markets_market
            ON wallet_performance_markets(
                market_id
            );

            CREATE TABLE IF NOT EXISTS wallet_performance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                wallet TEXT NOT NULL,

                resolved_positions INTEGER,
                wins INTEGER,
                losses INTEGER,

                win_rate REAL,
                total_cost_basis REAL,
                total_settlement_value REAL,
                estimated_profit REAL,
                estimated_roi REAL,

                performance_score REAL,
                performance_grade TEXT,
                data_confidence TEXT,

                observed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_wallet_performance_history_wallet
            ON wallet_performance_history(
                wallet,
                observed_at DESC
            );

            CREATE TABLE IF NOT EXISTS wallet_performance_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                latest_positions_loaded INTEGER
                    NOT NULL DEFAULT 0,

                resolved_position_rows INTEGER
                    NOT NULL DEFAULT 0,

                wallets_scored INTEGER
                    NOT NULL DEFAULT 0,

                performance_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                market_rows_saved INTEGER
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


def load_latest_positions() -> list[dict[str, Any]]:
    connection = connect_database()

    try:
        require_tables(
            connection,
            [
                "wallet_scans",
                "positions",
            ],
        )

        rows = connection.execute(
            """
            WITH latest_scans AS (
                SELECT
                    wallet,
                    MAX(id) AS scan_id
                FROM wallet_scans
                GROUP BY wallet
            )
            SELECT
                p.*,
                ws.scanned_at
            FROM latest_scans ls
            JOIN wallet_scans ws
              ON ws.id = ls.scan_id
            JOIN positions p
              ON p.scan_id = ls.scan_id
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        connection.close()


def load_resolved_mapping_lookup() -> dict[
    tuple[str, str],
    dict[str, Any],
]:
    connection = connect_database()

    try:
        require_tables(
            connection,
            [
                "mapped_market_results",
            ],
        )

        rows = connection.execute(
            """
            SELECT *
            FROM mapped_market_results
            WHERE resolution_status IN (
                'RESOLVED',
                'LIKELY_RESOLVED'
            )
              AND source_outcome_won IS NOT NULL
            """
        ).fetchall()

    finally:
        connection.close()

    lookup: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for row in rows:
        record = dict(row)

        market_id = clean_text(
            record.get(
                "source_market_id"
            )
        ).lower()

        outcome = normalize_text(
            record.get(
                "source_outcome"
            )
        )

        if not market_id:
            continue

        lookup[
            (
                market_id,
                outcome,
            )
        ] = record

    return lookup


def load_all_mapping_lookup() -> set[
    tuple[str, str]
]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "market_mappings",
        ):
            return set()

        rows = connection.execute(
            """
            SELECT
                source_market_id,
                source_outcome
            FROM market_mappings
            WHERE mapping_status = 'MAPPED'
            """
        ).fetchall()

    finally:
        connection.close()

    return {
        (
            clean_text(
                row["source_market_id"]
            ).lower(),
            normalize_text(
                row["source_outcome"]
            ),
        )
        for row in rows
    }


# =============================================================================
# PERFORMANCE CALCULATION
# =============================================================================


def grade_from_score(
    score: float,
    resolved_positions: int,
) -> str:
    if resolved_positions < MIN_RESOLVED_BETS_FOR_GRADE:
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


def confidence_from_sample(
    resolved_positions: int,
) -> str:
    if resolved_positions >= 100:
        return "VERY HIGH"

    if resolved_positions >= 50:
        return "HIGH"

    if resolved_positions >= 20:
        return "MEDIUM"

    if resolved_positions >= 8:
        return "LOW"

    return "VERY LOW"


def build_performance_rows() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    int,
]:
    latest_positions = load_latest_positions()
    resolved_lookup = (
        load_resolved_mapping_lookup()
    )
    mapped_lookup = load_all_mapping_lookup()

    market_rows: list[
        dict[str, Any]
    ] = []

    unresolved_mapped_by_wallet: dict[
        str,
        int,
    ] = defaultdict(int)

    for position in latest_positions:
        wallet = normalize_wallet(
            position.get("wallet")
        )

        market_id = clean_text(
            position.get("market_id")
        ).lower()

        selected_outcome = clean_text(
            position.get("outcome")
        )

        normalized_outcome = normalize_text(
            selected_outcome
        )

        key = (
            market_id,
            normalized_outcome,
        )

        resolution = resolved_lookup.get(
            key
        )

        if resolution is None:
            if key in mapped_lookup:
                unresolved_mapped_by_wallet[
                    wallet
                ] += 1

            continue

        shares = max(
            safe_float(
                position.get("shares")
            ),
            0.0,
        )

        average_entry_price = clamp(
            safe_float(
                position.get(
                    "average_price"
                )
            ),
            0.0,
            1.0,
        )

        cost_basis = (
            shares
            * average_entry_price
        )

        won = safe_int(
            resolution.get(
                "source_outcome_won"
            )
        )

        lost = safe_int(
            resolution.get(
                "source_outcome_lost"
            )
        )

        settlement_price = (
            1.0
            if won == 1
            else 0.0
        )

        settlement_value = (
            shares
            * settlement_price
        )

        estimated_profit = (
            settlement_value
            - cost_basis
        )

        estimated_roi = safe_divide(
            estimated_profit,
            cost_basis,
            0.0,
        )

        brier_score = (
            average_entry_price
            - float(won)
        ) ** 2

        performance_market_key = (
            f"{wallet}:"
            f"{safe_int(position.get('scan_id'))}:"
            f"{market_id}:"
            f"{normalized_outcome}"
        )

        market_rows.append(
            {
                "performance_market_key": (
                    performance_market_key
                ),
                "wallet": wallet,
                "scan_id": safe_int(
                    position.get(
                        "scan_id"
                    )
                ),
                "scanned_at": clean_text(
                    position.get(
                        "scanned_at"
                    )
                ),
                "market_id": market_id,
                "title": clean_text(
                    position.get("title")
                ),
                "selected_outcome": (
                    selected_outcome
                ),
                "gamma_market_id": clean_text(
                    resolution.get(
                        "gamma_market_id"
                    )
                ),
                "condition_id": clean_text(
                    resolution.get(
                        "condition_id"
                    )
                ),
                "resolution_status": (
                    clean_text(
                        resolution.get(
                            "resolution_status"
                        )
                    )
                ),
                "winning_outcome_name": (
                    clean_text(
                        resolution.get(
                            "winning_outcome_name"
                        )
                    )
                ),
                "source_outcome_won": won,
                "source_outcome_lost": lost,
                "shares": shares,
                "average_entry_price": (
                    average_entry_price
                ),
                "cost_basis": cost_basis,
                "settlement_price": (
                    settlement_price
                ),
                "settlement_value": (
                    settlement_value
                ),
                "estimated_profit": (
                    estimated_profit
                ),
                "estimated_roi": (
                    estimated_roi
                ),
                "brier_score": brier_score,
                "match_method": clean_text(
                    resolution.get(
                        "match_method"
                    )
                ),
                "match_confidence": safe_float(
                    resolution.get(
                        "match_confidence"
                    )
                ),
                "calculated_at": (
                    utc_now_iso()
                ),
                "updated_at": utc_now_iso(),
            }
        )

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in market_rows:
        grouped[
            row["wallet"]
        ].append(row)

    performance_rows: list[
        dict[str, Any]
    ] = []

    calculated_at = utc_now_iso()

    all_wallets = {
        normalize_wallet(
            position.get("wallet")
        )
        for position in latest_positions
        if normalize_wallet(
            position.get("wallet")
        )
    }

    for wallet in sorted(all_wallets):
        rows = grouped.get(
            wallet,
            [],
        )

        resolved_positions = len(
            rows
        )

        wins = sum(
            row["source_outcome_won"]
            for row in rows
        )

        losses = sum(
            row["source_outcome_lost"]
            for row in rows
        )

        win_rate = safe_divide(
            wins,
            resolved_positions,
            0.0,
        )

        total_cost_basis = sum(
            row["cost_basis"]
            for row in rows
        )

        total_settlement_value = sum(
            row["settlement_value"]
            for row in rows
        )

        estimated_profit = (
            total_settlement_value
            - total_cost_basis
        )

        estimated_roi = safe_divide(
            estimated_profit,
            total_cost_basis,
            0.0,
        )

        weighted_entry_numerator = sum(
            row["average_entry_price"]
            * row["cost_basis"]
            for row in rows
        )

        average_entry_price = safe_divide(
            weighted_entry_numerator,
            total_cost_basis,
            0.0,
        )

        winning_rows = [
            row
            for row in rows
            if row[
                "source_outcome_won"
            ]
            == 1
        ]

        losing_rows = [
            row
            for row in rows
            if row[
                "source_outcome_lost"
            ]
            == 1
        ]

        average_winning_entry = (
            sum(
                row["average_entry_price"]
                for row in winning_rows
            )
            / len(winning_rows)
            if winning_rows
            else None
        )

        average_losing_entry = (
            sum(
                row["average_entry_price"]
                for row in losing_rows
            )
            / len(losing_rows)
            if losing_rows
            else None
        )

        average_edge_at_entry = (
            sum(
                (
                    1.0
                    - row[
                        "average_entry_price"
                    ]
                )
                if row[
                    "source_outcome_won"
                ]
                else (
                    -row[
                        "average_entry_price"
                    ]
                )
                for row in rows
            )
            / resolved_positions
            if resolved_positions
            else 0.0
        )

        gross_profit = sum(
            max(
                row["estimated_profit"],
                0.0,
            )
            for row in rows
        )

        gross_loss = abs(
            sum(
                min(
                    row["estimated_profit"],
                    0.0,
                )
                for row in rows
            )
        )

        profit_factor = (
            safe_divide(
                gross_profit,
                gross_loss,
                float("inf"),
            )
            if gross_loss > 0
            else (
                float("inf")
                if gross_profit > 0
                else None
            )
        )

        average_win = (
            gross_profit
            / len(winning_rows)
            if winning_rows
            else 0.0
        )

        average_loss = (
            gross_loss
            / len(losing_rows)
            if losing_rows
            else 0.0
        )

        payoff_ratio = (
            safe_divide(
                average_win,
                average_loss,
                float("inf"),
            )
            if average_loss > 0
            else (
                float("inf")
                if average_win > 0
                else None
            )
        )

        weighted_brier_score = safe_divide(
            sum(
                row["brier_score"]
                * max(
                    row["cost_basis"],
                    1.0,
                )
                for row in rows
            ),
            sum(
                max(
                    row["cost_basis"],
                    1.0,
                )
                for row in rows
            ),
            1.0,
        )

        calibration_score = clamp(
            (
                1.0
                - weighted_brier_score
            )
            * 100.0
        )

        returns = [
            row["estimated_roi"]
            for row in rows
        ]

        if len(returns) >= 2:
            mean_return = sum(
                returns
            ) / len(returns)

            variance = sum(
                (
                    value
                    - mean_return
                )
                ** 2
                for value in returns
            ) / (
                len(returns)
                - 1
            )

            standard_deviation = math.sqrt(
                variance
            )

            consistency_score = clamp(
                50.0
                + safe_divide(
                    mean_return,
                    standard_deviation,
                    0.0,
                )
                * 15.0
            )

        elif len(returns) == 1:
            consistency_score = 40.0

        else:
            consistency_score = 0.0

        sample_size_score = clamp(
            math.log1p(
                resolved_positions
            )
            / math.log1p(100)
            * 100.0
        )

        profitability_score = clamp(
            50.0
            + max(
                min(
                    estimated_roi,
                    1.0,
                ),
                -1.0,
            )
            * 45.0
        )

        accuracy_score = clamp(
            win_rate
            * 100.0
        )

        entry_quality_score = clamp(
            50.0
            + average_edge_at_entry
            * 50.0
        )

        raw_performance_score = clamp(
            profitability_score * 0.35
            + accuracy_score * 0.25
            + entry_quality_score * 0.15
            + calibration_score * 0.10
            + consistency_score * 0.10
            + sample_size_score * 0.05
        )

        sample_reliability = clamp(
            resolved_positions
            / 20.0,
            0.0,
            1.0,
        )

        performance_score = (
            50.0
            + (
                raw_performance_score
                - 50.0
            )
            * sample_reliability
        )

        performance_score = clamp(
            performance_score
        )

        grade = grade_from_score(
            performance_score,
            resolved_positions,
        )

        confidence = (
            confidence_from_sample(
                resolved_positions
            )
        )

        scan_times = [
            clean_text(
                row["scanned_at"]
            )
            for row in rows
            if clean_text(
                row["scanned_at"]
            )
        ]

        explanation = {
            "model_version": "1.0",
            "method": (
                "LATEST POSITION SNAPSHOT JOINED TO "
                "RESOLVED MAPPED MARKETS"
            ),
            "important_limitation": (
                "Estimated profit is settlement value minus "
                "latest observed cost basis. It is not a "
                "complete realized trade ledger."
            ),
            "score_components": {
                "profitability_score": round(
                    profitability_score,
                    2,
                ),
                "accuracy_score": round(
                    accuracy_score,
                    2,
                ),
                "entry_quality_score": round(
                    entry_quality_score,
                    2,
                ),
                "calibration_score": round(
                    calibration_score,
                    2,
                ),
                "consistency_score": round(
                    consistency_score,
                    2,
                ),
                "sample_size_score": round(
                    sample_size_score,
                    2,
                ),
            },
        }

        performance_rows.append(
            {
                "wallet": wallet,
                "resolved_positions": (
                    resolved_positions
                ),
                "wins": wins,
                "losses": losses,
                "unresolved_mapped_positions": (
                    unresolved_mapped_by_wallet.get(
                        wallet,
                        0,
                    )
                ),
                "win_rate": win_rate,
                "total_cost_basis": (
                    total_cost_basis
                ),
                "total_settlement_value": (
                    total_settlement_value
                ),
                "estimated_profit": (
                    estimated_profit
                ),
                "estimated_roi": (
                    estimated_roi
                ),
                "average_entry_price": (
                    average_entry_price
                ),
                "average_winning_entry": (
                    average_winning_entry
                ),
                "average_losing_entry": (
                    average_losing_entry
                ),
                "average_edge_at_entry": (
                    average_edge_at_entry
                ),
                "profit_factor": (
                    profit_factor
                ),
                "payoff_ratio": payoff_ratio,
                "weighted_brier_score": (
                    weighted_brier_score
                ),
                "calibration_score": (
                    calibration_score
                ),
                "consistency_score": (
                    consistency_score
                ),
                "sample_size_score": (
                    sample_size_score
                ),
                "profitability_score": (
                    profitability_score
                ),
                "accuracy_score": (
                    accuracy_score
                ),
                "entry_quality_score": (
                    entry_quality_score
                ),
                "performance_score": (
                    performance_score
                ),
                "performance_grade": (
                    grade
                ),
                "data_confidence": (
                    confidence
                ),
                "mapped_market_count": (
                    resolved_positions
                    + unresolved_mapped_by_wallet.get(
                        wallet,
                        0,
                    )
                ),
                "first_resolved_scan_at": (
                    min(scan_times)
                    if scan_times
                    else ""
                ),
                "last_resolved_scan_at": (
                    max(scan_times)
                    if scan_times
                    else ""
                ),
                "explanation_json": (
                    stable_json(
                        explanation
                    )
                ),
                "calculated_at": (
                    calculated_at
                ),
                "updated_at": (
                    calculated_at
                ),
            }
        )

    performance_rows.sort(
        key=lambda row: (
            row["performance_score"],
            row["resolved_positions"],
            row["estimated_profit"],
        ),
        reverse=True,
    )

    return (
        performance_rows,
        market_rows,
        len(latest_positions),
    )


# =============================================================================
# SAVING
# =============================================================================


def save_performance_data(
    performance_rows: list[dict[str, Any]],
    market_rows: list[dict[str, Any]],
) -> tuple[int, int, int]:
    connection = connect_database()

    performance_columns = [
        "wallet",
        "resolved_positions",
        "wins",
        "losses",
        "unresolved_mapped_positions",
        "win_rate",
        "total_cost_basis",
        "total_settlement_value",
        "estimated_profit",
        "estimated_roi",
        "average_entry_price",
        "average_winning_entry",
        "average_losing_entry",
        "average_edge_at_entry",
        "profit_factor",
        "payoff_ratio",
        "weighted_brier_score",
        "calibration_score",
        "consistency_score",
        "sample_size_score",
        "profitability_score",
        "accuracy_score",
        "entry_quality_score",
        "performance_score",
        "performance_grade",
        "data_confidence",
        "mapped_market_count",
        "first_resolved_scan_at",
        "last_resolved_scan_at",
        "explanation_json",
        "calculated_at",
        "updated_at",
    ]

    market_columns = [
        "performance_market_key",
        "wallet",
        "scan_id",
        "scanned_at",
        "market_id",
        "title",
        "selected_outcome",
        "gamma_market_id",
        "condition_id",
        "resolution_status",
        "winning_outcome_name",
        "source_outcome_won",
        "source_outcome_lost",
        "shares",
        "average_entry_price",
        "cost_basis",
        "settlement_price",
        "settlement_value",
        "estimated_profit",
        "estimated_roi",
        "brier_score",
        "match_method",
        "match_confidence",
        "calculated_at",
        "updated_at",
    ]

    def upsert_query(
        table_name: str,
        columns: list[str],
        primary_key: str,
    ) -> str:
        names = ", ".join(
            f'"{column}"'
            for column in columns
        )

        placeholders = ", ".join(
            "?"
            for _ in columns
        )

        updates = ", ".join(
            f'"{column}" = excluded."{column}"'
            for column in columns
            if column != primary_key
        )

        return f"""
            INSERT INTO "{table_name}" (
                {names}
            )
            VALUES (
                {placeholders}
            )
            ON CONFLICT("{primary_key}")
            DO UPDATE SET
                {updates}
        """

    performance_query = upsert_query(
        "wallet_performance",
        performance_columns,
        "wallet",
    )

    market_query = upsert_query(
        "wallet_performance_markets",
        market_columns,
        "performance_market_key",
    )

    observed_at = utc_now_iso()

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        connection.execute(
            "DELETE FROM wallet_performance"
        )

        connection.execute(
            "DELETE FROM wallet_performance_markets"
        )

        for row in performance_rows:
            connection.execute(
                performance_query,
                tuple(
                    row[column]
                    for column
                    in performance_columns
                ),
            )

            connection.execute(
                """
                INSERT INTO wallet_performance_history (
                    wallet,
                    resolved_positions,
                    wins,
                    losses,
                    win_rate,
                    total_cost_basis,
                    total_settlement_value,
                    estimated_profit,
                    estimated_roi,
                    performance_score,
                    performance_grade,
                    data_confidence,
                    observed_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    row["wallet"],
                    row[
                        "resolved_positions"
                    ],
                    row["wins"],
                    row["losses"],
                    row["win_rate"],
                    row[
                        "total_cost_basis"
                    ],
                    row[
                        "total_settlement_value"
                    ],
                    row[
                        "estimated_profit"
                    ],
                    row["estimated_roi"],
                    row[
                        "performance_score"
                    ],
                    row[
                        "performance_grade"
                    ],
                    row[
                        "data_confidence"
                    ],
                    observed_at,
                ),
            )

        for row in market_rows:
            connection.execute(
                market_query,
                tuple(
                    row[column]
                    for column
                    in market_columns
                ),
            )

        connection.commit()

        return (
            len(performance_rows),
            len(market_rows),
            len(performance_rows),
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
    started = utc_now()
    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO wallet_performance_runs (
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
    started_at: datetime,
    status: str,
    latest_positions_loaded: int,
    resolved_position_rows: int,
    wallets_scored: int,
    performance_rows_saved: int,
    market_rows_saved: int,
    history_rows_saved: int,
    error_message: str = "",
) -> None:
    finished = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE wallet_performance_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                latest_positions_loaded = ?,
                resolved_position_rows = ?,
                wallets_scored = ?,
                performance_rows_saved = ?,
                market_rows_saved = ?,
                history_rows_saved = ?,
                status = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                finished.isoformat(),
                (
                    finished
                    - started_at
                ).total_seconds(),
                latest_positions_loaded,
                resolved_position_rows,
                wallets_scored,
                performance_rows_saved,
                market_rows_saved,
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
    performance_rows: list[dict[str, Any]],
    market_rows: list[dict[str, Any]],
    latest_positions_loaded: int,
    display_limit: int,
) -> None:
    print()
    print("=" * 108)
    print("WALLET PERFORMANCE ENGINE SUMMARY")
    print("=" * 108)

    print(
        f"Latest positions loaded:        "
        f"{latest_positions_loaded}"
    )

    print(
        f"Resolved position rows:         "
        f"{len(market_rows)}"
    )

    print(
        f"Wallets scored:                 "
        f"{len(performance_rows)}"
    )

    rated_wallets = sum(
        1
        for row in performance_rows
        if row[
            "performance_grade"
        ]
        != "UNRATED"
    )

    print(
        f"Rated wallets:                  "
        f"{rated_wallets}"
    )

    print(
        f"Estimated aggregate profit:     "
        f"{format_money(sum(row['estimated_profit'] for row in performance_rows))}"
    )

    print("=" * 108)

    print()
    print("TOP WALLET PERFORMANCE")

    for rank, row in enumerate(
        performance_rows[
            :display_limit
        ],
        start=1,
    ):
        print()
        print("-" * 108)

        print(
            f"{rank}. {row['wallet']}"
        )

        print("-" * 108)

        print(
            f"Performance score / grade:      "
            f"{row['performance_score']:.1f} "
            f"/ {row['performance_grade']}"
        )

        print(
            f"Data confidence:                "
            f"{row['data_confidence']}"
        )

        print(
            f"Resolved positions:             "
            f"{row['resolved_positions']}"
        )

        print(
            f"Wins / losses:                  "
            f"{row['wins']} / {row['losses']}"
        )

        print(
            f"Win rate:                       "
            f"{format_percentage(row['win_rate'])}"
        )

        print(
            f"Estimated profit:               "
            f"{format_money(row['estimated_profit'])}"
        )

        print(
            f"Estimated ROI:                  "
            f"{format_percentage(row['estimated_roi'])}"
        )

        print(
            f"Average entry price:            "
            f"{row['average_entry_price']:.4f}"
        )

        print(
            f"Calibration score:              "
            f"{row['calibration_score']:.1f}"
        )

        print(
            f"Unresolved mapped positions:    "
            f"{row['unresolved_mapped_positions']}"
        )


# =============================================================================
# ARGUMENTS AND MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Estimate wallet performance from each wallet's "
            "latest position snapshot and resolved mapped markets."
        )
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )

    return parser.parse_args()


def main() -> None:
    configure_utf8_output()
    arguments = parse_arguments()

    print()
    print("=" * 108)
    print("POLYMARKET WALLET PERFORMANCE ENGINE v1")
    print("=" * 108)

    print(
        f"Database: {DATABASE_PATH}"
    )

    print(
        "Method: latest position snapshot plus "
        "resolved mapped markets"
    )

    create_performance_tables()

    run_id, started_at = start_run()

    performance_rows: list[
        dict[str, Any]
    ] = []

    market_rows: list[
        dict[str, Any]
    ] = []

    latest_positions_loaded = 0

    performance_saved = 0
    market_saved = 0
    history_saved = 0

    try:
        (
            performance_rows,
            market_rows,
            latest_positions_loaded,
        ) = build_performance_rows()

        (
            performance_saved,
            market_saved,
            history_saved,
        ) = save_performance_data(
            performance_rows=(
                performance_rows
            ),
            market_rows=(
                market_rows
            ),
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            latest_positions_loaded=(
                latest_positions_loaded
            ),
            resolved_position_rows=(
                len(market_rows)
            ),
            wallets_scored=(
                len(performance_rows)
            ),
            performance_rows_saved=(
                performance_saved
            ),
            market_rows_saved=(
                market_saved
            ),
            history_rows_saved=(
                history_saved
            ),
        )

        display_summary(
            performance_rows=(
                performance_rows
            ),
            market_rows=(
                market_rows
            ),
            latest_positions_loaded=(
                latest_positions_loaded
            ),
            display_limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 108)
        print("WALLET PERFORMANCE ENGINE COMPLETE")
        print("=" * 108)

        print(
            "Current wallet scores were saved to "
            "wallet_performance."
        )

        print(
            "Resolved position-level calculations were saved "
            "to wallet_performance_markets."
        )

        print(
            "Historical wallet score snapshots were saved to "
            "wallet_performance_history."
        )

        print(
            "Important: estimated profit uses the latest observed "
            "position snapshot, not a complete realized trade ledger."
        )

        print("=" * 108)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            latest_positions_loaded=(
                latest_positions_loaded
            ),
            resolved_position_rows=(
                len(market_rows)
            ),
            wallets_scored=(
                len(performance_rows)
            ),
            performance_rows_saved=(
                performance_saved
            ),
            market_rows_saved=(
                market_saved
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