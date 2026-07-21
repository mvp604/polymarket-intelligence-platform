from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_DISPLAY_LIMIT = 25


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
    maximum: float = 1.0,
) -> float:
    return max(minimum, min(value, maximum))


def parse_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value

    text = clean_text(value)

    if not text:
        return []

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []

    return parsed if isinstance(parsed, list) else []


def resolution_key(
    gamma_market_id: str,
) -> str:
    return f"gamma:{gamma_market_id}"


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


# =============================================================================
# TABLE CREATION
# =============================================================================


def create_resolution_tables() -> None:
    connection = connect_database()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS market_resolutions (
                resolution_key TEXT PRIMARY KEY,

                gamma_market_id TEXT NOT NULL,
                gamma_event_id TEXT,
                condition_id TEXT,

                question TEXT NOT NULL,
                slug TEXT,

                resolved INTEGER
                    NOT NULL DEFAULT 0,

                resolution_status TEXT
                    NOT NULL DEFAULT 'UNRESOLVED',

                winning_outcome_index INTEGER,
                winning_outcome_name TEXT,
                winning_token_id TEXT,

                settlement_price REAL,

                outcome_count INTEGER
                    NOT NULL DEFAULT 0,

                resolved_outcome_count INTEGER
                    NOT NULL DEFAULT 0,

                closed INTEGER
                    NOT NULL DEFAULT 0,

                active INTEGER
                    NOT NULL DEFAULT 0,

                end_time TEXT,
                updated_at_gamma TEXT,

                resolution_source TEXT,
                resolved_by TEXT,

                confidence_score REAL
                    NOT NULL DEFAULT 0,

                source_payload_json TEXT,
                explanation_json TEXT,

                first_seen_at TEXT NOT NULL,
                last_checked_at TEXT NOT NULL,
                resolved_at_detected TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_resolutions_status
            ON market_resolutions(
                resolution_status,
                resolved,
                last_checked_at DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_resolutions_condition
            ON market_resolutions(
                condition_id
            );

            CREATE TABLE IF NOT EXISTS market_resolution_outcomes (
                resolution_outcome_key TEXT PRIMARY KEY,

                resolution_key TEXT NOT NULL,

                gamma_market_id TEXT NOT NULL,
                condition_id TEXT,

                outcome_index INTEGER
                    NOT NULL,

                outcome_name TEXT NOT NULL,
                token_id TEXT,

                implied_price REAL,

                winner INTEGER
                    NOT NULL DEFAULT 0,

                settlement_price REAL,

                resolution_status TEXT
                    NOT NULL DEFAULT 'UNRESOLVED',

                first_seen_at TEXT NOT NULL,
                last_checked_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(
                    resolution_key
                )
                REFERENCES market_resolutions(
                    resolution_key
                )
                ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_resolution_outcomes_market
            ON market_resolution_outcomes(
                gamma_market_id,
                outcome_index
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_resolution_outcomes_token
            ON market_resolution_outcomes(
                token_id
            );

            CREATE TABLE IF NOT EXISTS mapped_market_results (
                mapped_result_key TEXT PRIMARY KEY,

                mapping_key TEXT NOT NULL,

                source_table TEXT NOT NULL,
                source_market_id TEXT NOT NULL,
                source_title TEXT,
                source_outcome TEXT,

                gamma_market_id TEXT NOT NULL,
                condition_id TEXT,

                resolution_status TEXT
                    NOT NULL DEFAULT 'UNRESOLVED',

                winning_outcome_name TEXT,
                winning_token_id TEXT,

                source_outcome_normalized TEXT,
                winning_outcome_normalized TEXT,

                source_outcome_won INTEGER,
                source_outcome_lost INTEGER,

                settlement_price REAL,

                match_method TEXT,
                match_confidence REAL,

                resolved_at_detected TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_mapped_market_results_resolution
            ON mapped_market_results(
                resolution_status,
                source_outcome_won
            );

            CREATE INDEX IF NOT EXISTS
            idx_mapped_market_results_mapping
            ON mapped_market_results(
                mapping_key
            );

            CREATE TABLE IF NOT EXISTS market_resolution_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                registry_markets_checked INTEGER
                    NOT NULL DEFAULT 0,

                resolved_markets_found INTEGER
                    NOT NULL DEFAULT 0,

                ambiguous_markets INTEGER
                    NOT NULL DEFAULT 0,

                unresolved_markets INTEGER
                    NOT NULL DEFAULT 0,

                resolution_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                outcome_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                mapped_results_saved INTEGER
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


def load_registry_markets() -> list[dict[str, Any]]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "gamma_markets",
        ):
            raise RuntimeError(
                "gamma_markets does not exist. "
                "Run gamma_market_registry.py first."
            )

        rows = connection.execute(
            """
            SELECT *
            FROM gamma_markets
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        connection.close()


def load_registry_outcomes() -> dict[
    str,
    list[dict[str, Any]],
]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "gamma_market_outcomes",
        ):
            raise RuntimeError(
                "gamma_market_outcomes does not exist. "
                "Run gamma_market_registry.py first."
            )

        rows = connection.execute(
            """
            SELECT *
            FROM gamma_market_outcomes
            ORDER BY
                gamma_market_id,
                outcome_index
            """
        ).fetchall()

    finally:
        connection.close()

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for row in rows:
        grouped.setdefault(
            clean_text(
                row["gamma_market_id"]
            ),
            [],
        ).append(
            dict(row)
        )

    return grouped


def load_market_mappings() -> list[dict[str, Any]]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "market_mappings",
        ):
            return []

        rows = connection.execute(
            """
            SELECT *
            FROM market_mappings
            WHERE mapping_status = 'MAPPED'
              AND gamma_market_id IS NOT NULL
              AND TRIM(gamma_market_id) != ''
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        connection.close()


# =============================================================================
# RESOLUTION LOGIC
# =============================================================================


def infer_resolution(
    market: dict[str, Any],
    outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    market_resolved_flag = safe_int(
        market.get("resolved")
    )

    market_closed_flag = safe_int(
        market.get("closed")
    )

    winner_rows = [
        outcome
        for outcome in outcomes
        if safe_int(
            outcome.get("winner")
        ) == 1
    ]

    terminal_price_rows = [
        outcome
        for outcome in outcomes
        if safe_float(
            outcome.get("implied_price"),
            -1.0,
        ) in {
            0.0,
            1.0,
        }
    ]

    winning_outcome: dict[str, Any] | None = None
    status = "UNRESOLVED"
    confidence = 0.0

    if len(winner_rows) == 1:
        winning_outcome = winner_rows[0]
        status = "RESOLVED"
        confidence = 1.0

    elif (
        market_resolved_flag == 1
        and len(terminal_price_rows) >= 1
    ):
        one_price_rows = [
            row
            for row in terminal_price_rows
            if safe_float(
                row.get("implied_price")
            ) == 1.0
        ]

        if len(one_price_rows) == 1:
            winning_outcome = one_price_rows[0]
            status = "RESOLVED"
            confidence = 0.95

        else:
            status = "AMBIGUOUS"
            confidence = 0.35

    elif market_resolved_flag == 1:
        status = "AMBIGUOUS"
        confidence = 0.25

    elif (
        market_closed_flag == 1
        and len(terminal_price_rows) >= 1
    ):
        one_price_rows = [
            row
            for row in terminal_price_rows
            if safe_float(
                row.get("implied_price")
            ) == 1.0
        ]

        if len(one_price_rows) == 1:
            winning_outcome = one_price_rows[0]
            status = "LIKELY_RESOLVED"
            confidence = 0.80

        else:
            status = "CLOSED_UNRESOLVED"
            confidence = 0.20

    elif market_closed_flag == 1:
        status = "CLOSED_UNRESOLVED"
        confidence = 0.10

    winning_outcome_name = (
        clean_text(
            winning_outcome.get(
                "outcome_name"
            )
        )
        if winning_outcome
        else ""
    )

    winning_token_id = (
        clean_text(
            winning_outcome.get(
                "token_id"
            )
        )
        if winning_outcome
        else ""
    )

    winning_outcome_index = (
        safe_int(
            winning_outcome.get(
                "outcome_index"
            )
        )
        if winning_outcome
        else None
    )

    settlement_price = (
        safe_float(
            winning_outcome.get(
                "implied_price"
            )
        )
        if winning_outcome
        else None
    )

    explanation = {
        "market_resolved_flag": (
            market_resolved_flag
        ),
        "market_closed_flag": (
            market_closed_flag
        ),
        "winner_rows": len(
            winner_rows
        ),
        "terminal_price_rows": len(
            terminal_price_rows
        ),
        "inference_method": (
            "WINNER_FLAG"
            if len(winner_rows) == 1
            else (
                "TERMINAL_PRICE"
                if winning_outcome
                else "NO_CONFIRMED_WINNER"
            )
        ),
    }

    return {
        "resolution_status": status,
        "resolved": int(
            status
            in {
                "RESOLVED",
                "LIKELY_RESOLVED",
            }
        ),
        "winning_outcome_index": (
            winning_outcome_index
        ),
        "winning_outcome_name": (
            winning_outcome_name
        ),
        "winning_token_id": (
            winning_token_id
        ),
        "settlement_price": (
            settlement_price
        ),
        "confidence_score": (
            confidence
        ),
        "explanation_json": json.dumps(
            explanation,
            ensure_ascii=False,
        ),
    }


def build_resolution_records() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    markets = load_registry_markets()
    outcomes_by_market = (
        load_registry_outcomes()
    )

    now = utc_now_iso()

    market_records: list[
        dict[str, Any]
    ] = []

    outcome_records: list[
        dict[str, Any]
    ] = []

    for market in markets:
        gamma_market_id = clean_text(
            market.get(
                "gamma_market_id"
            )
        )

        if not gamma_market_id:
            continue

        outcomes = outcomes_by_market.get(
            gamma_market_id,
            [],
        )

        inferred = infer_resolution(
            market,
            outcomes,
        )

        key = resolution_key(
            gamma_market_id
        )

        market_records.append(
            {
                "resolution_key": key,
                "gamma_market_id": (
                    gamma_market_id
                ),
                "gamma_event_id": clean_text(
                    market.get(
                        "gamma_event_id"
                    )
                ),
                "condition_id": clean_text(
                    market.get(
                        "condition_id"
                    )
                ).lower(),
                "question": clean_text(
                    market.get(
                        "question"
                    )
                )
                or "Untitled market",
                "slug": clean_text(
                    market.get("slug")
                ),
                "resolved": inferred[
                    "resolved"
                ],
                "resolution_status": inferred[
                    "resolution_status"
                ],
                "winning_outcome_index": inferred[
                    "winning_outcome_index"
                ],
                "winning_outcome_name": inferred[
                    "winning_outcome_name"
                ],
                "winning_token_id": inferred[
                    "winning_token_id"
                ],
                "settlement_price": inferred[
                    "settlement_price"
                ],
                "outcome_count": len(
                    outcomes
                ),
                "resolved_outcome_count": sum(
                    1
                    for outcome in outcomes
                    if safe_int(
                        outcome.get(
                            "winner"
                        )
                    )
                    == 1
                ),
                "closed": safe_int(
                    market.get("closed")
                ),
                "active": safe_int(
                    market.get("active")
                ),
                "end_time": clean_text(
                    market.get(
                        "end_time"
                    )
                ),
                "updated_at_gamma": clean_text(
                    market.get(
                        "updated_at_gamma"
                    )
                ),
                "resolution_source": clean_text(
                    market.get(
                        "resolution_source"
                    )
                ),
                "resolved_by": clean_text(
                    market.get(
                        "resolved_by"
                    )
                ),
                "confidence_score": inferred[
                    "confidence_score"
                ],
                "source_payload_json": clean_text(
                    market.get(
                        "raw_payload_json"
                    )
                ),
                "explanation_json": inferred[
                    "explanation_json"
                ],
                "first_seen_at": now,
                "last_checked_at": now,
                "resolved_at_detected": (
                    now
                    if inferred[
                        "resolved"
                    ]
                    else ""
                ),
                "updated_at": now,
            }
        )

        for outcome in outcomes:
            implied_price = outcome.get(
                "implied_price"
            )

            winner = safe_int(
                outcome.get("winner")
            )

            if winner == 1:
                outcome_status = (
                    "WINNER"
                )

            elif (
                inferred[
                    "resolution_status"
                ]
                in {
                    "RESOLVED",
                    "LIKELY_RESOLVED",
                }
            ):
                outcome_status = "LOSER"

            else:
                outcome_status = (
                    "UNRESOLVED"
                )

            outcome_index = safe_int(
                outcome.get(
                    "outcome_index"
                )
            )

            outcome_records.append(
                {
                    "resolution_outcome_key": (
                        f"{key}:{outcome_index}"
                    ),
                    "resolution_key": key,
                    "gamma_market_id": (
                        gamma_market_id
                    ),
                    "condition_id": clean_text(
                        market.get(
                            "condition_id"
                        )
                    ).lower(),
                    "outcome_index": (
                        outcome_index
                    ),
                    "outcome_name": clean_text(
                        outcome.get(
                            "outcome_name"
                        )
                    ),
                    "token_id": clean_text(
                        outcome.get(
                            "token_id"
                        )
                    ),
                    "implied_price": (
                        implied_price
                    ),
                    "winner": winner,
                    "settlement_price": (
                        1.0
                        if winner == 1
                        else (
                            0.0
                            if outcome_status
                            == "LOSER"
                            else None
                        )
                    ),
                    "resolution_status": (
                        outcome_status
                    ),
                    "first_seen_at": now,
                    "last_checked_at": now,
                    "updated_at": now,
                }
            )

    return (
        market_records,
        outcome_records,
    )


# =============================================================================
# MAPPED RESULT LABELS
# =============================================================================


def outcome_matches(
    source_outcome: str,
    winning_outcome: str,
) -> bool | None:
    source = normalize_text(
        source_outcome
    )

    winner = normalize_text(
        winning_outcome
    )

    if not source or not winner:
        return None

    if source == winner:
        return True

    aliases = {
        "y": "yes",
        "n": "no",
    }

    source = aliases.get(
        source,
        source,
    )

    winner = aliases.get(
        winner,
        winner,
    )

    return source == winner


def build_mapped_results(
    resolution_lookup: dict[
        str,
        dict[str, Any],
    ],
) -> list[dict[str, Any]]:
    mappings = load_market_mappings()
    now = utc_now_iso()

    results: list[
        dict[str, Any]
    ] = []

    for mapping in mappings:
        gamma_market_id = clean_text(
            mapping.get(
                "gamma_market_id"
            )
        )

        resolution = resolution_lookup.get(
            gamma_market_id
        )

        if resolution is None:
            continue

        source_outcome = clean_text(
            mapping.get(
                "source_outcome"
            )
        )

        winning_outcome = clean_text(
            resolution.get(
                "winning_outcome_name"
            )
        )

        verdict = outcome_matches(
            source_outcome,
            winning_outcome,
        )

        results.append(
            {
                "mapped_result_key": (
                    f"{mapping['mapping_key']}:"
                    f"result"
                ),
                "mapping_key": clean_text(
                    mapping.get(
                        "mapping_key"
                    )
                ),
                "source_table": clean_text(
                    mapping.get(
                        "source_table"
                    )
                ),
                "source_market_id": clean_text(
                    mapping.get(
                        "source_market_id"
                    )
                ),
                "source_title": clean_text(
                    mapping.get(
                        "source_title"
                    )
                ),
                "source_outcome": (
                    source_outcome
                ),
                "gamma_market_id": (
                    gamma_market_id
                ),
                "condition_id": clean_text(
                    mapping.get(
                        "condition_id"
                    )
                ).lower(),
                "resolution_status": clean_text(
                    resolution.get(
                        "resolution_status"
                    )
                ),
                "winning_outcome_name": (
                    winning_outcome
                ),
                "winning_token_id": clean_text(
                    resolution.get(
                        "winning_token_id"
                    )
                ),
                "source_outcome_normalized": (
                    normalize_text(
                        source_outcome
                    )
                ),
                "winning_outcome_normalized": (
                    normalize_text(
                        winning_outcome
                    )
                ),
                "source_outcome_won": (
                    int(verdict)
                    if verdict is not None
                    and resolution.get(
                        "resolved"
                    )
                    else None
                ),
                "source_outcome_lost": (
                    int(not verdict)
                    if verdict is not None
                    and resolution.get(
                        "resolved"
                    )
                    else None
                ),
                "settlement_price": (
                    resolution.get(
                        "settlement_price"
                    )
                ),
                "match_method": clean_text(
                    mapping.get(
                        "match_method"
                    )
                ),
                "match_confidence": safe_float(
                    mapping.get(
                        "match_confidence"
                    )
                ),
                "resolved_at_detected": clean_text(
                    resolution.get(
                        "resolved_at_detected"
                    )
                ),
                "calculated_at": now,
                "updated_at": now,
            }
        )

    return results


# =============================================================================
# SAVING
# =============================================================================


def save_resolution_data(
    market_records: list[dict[str, Any]],
    outcome_records: list[dict[str, Any]],
    mapped_results: list[dict[str, Any]],
) -> tuple[int, int, int]:
    connection = connect_database()

    market_columns = [
        "resolution_key",
        "gamma_market_id",
        "gamma_event_id",
        "condition_id",
        "question",
        "slug",
        "resolved",
        "resolution_status",
        "winning_outcome_index",
        "winning_outcome_name",
        "winning_token_id",
        "settlement_price",
        "outcome_count",
        "resolved_outcome_count",
        "closed",
        "active",
        "end_time",
        "updated_at_gamma",
        "resolution_source",
        "resolved_by",
        "confidence_score",
        "source_payload_json",
        "explanation_json",
        "first_seen_at",
        "last_checked_at",
        "resolved_at_detected",
        "updated_at",
    ]

    outcome_columns = [
        "resolution_outcome_key",
        "resolution_key",
        "gamma_market_id",
        "condition_id",
        "outcome_index",
        "outcome_name",
        "token_id",
        "implied_price",
        "winner",
        "settlement_price",
        "resolution_status",
        "first_seen_at",
        "last_checked_at",
        "updated_at",
    ]

    mapped_columns = [
        "mapped_result_key",
        "mapping_key",
        "source_table",
        "source_market_id",
        "source_title",
        "source_outcome",
        "gamma_market_id",
        "condition_id",
        "resolution_status",
        "winning_outcome_name",
        "winning_token_id",
        "source_outcome_normalized",
        "winning_outcome_normalized",
        "source_outcome_won",
        "source_outcome_lost",
        "settlement_price",
        "match_method",
        "match_confidence",
        "resolved_at_detected",
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
            if column
            not in {
                primary_key,
                "first_seen_at",
            }
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

    market_query = upsert_query(
        "market_resolutions",
        market_columns,
        "resolution_key",
    )

    outcome_query = upsert_query(
        "market_resolution_outcomes",
        outcome_columns,
        "resolution_outcome_key",
    )

    mapped_query = upsert_query(
        "mapped_market_results",
        mapped_columns,
        "mapped_result_key",
    )

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        for record in market_records:
            existing = connection.execute(
                """
                SELECT
                    first_seen_at,
                    resolved_at_detected
                FROM market_resolutions
                WHERE resolution_key = ?
                """,
                (
                    record[
                        "resolution_key"
                    ],
                ),
            ).fetchone()

            if existing is not None:
                record[
                    "first_seen_at"
                ] = clean_text(
                    existing[
                        "first_seen_at"
                    ]
                )

                if clean_text(
                    existing[
                        "resolved_at_detected"
                    ]
                ):
                    record[
                        "resolved_at_detected"
                    ] = clean_text(
                        existing[
                            "resolved_at_detected"
                        ]
                    )

            connection.execute(
                market_query,
                tuple(
                    record[column]
                    for column in market_columns
                ),
            )

        for record in outcome_records:
            existing = connection.execute(
                """
                SELECT first_seen_at
                FROM market_resolution_outcomes
                WHERE resolution_outcome_key = ?
                """,
                (
                    record[
                        "resolution_outcome_key"
                    ],
                ),
            ).fetchone()

            if existing is not None:
                record[
                    "first_seen_at"
                ] = clean_text(
                    existing[
                        "first_seen_at"
                    ]
                )

            connection.execute(
                outcome_query,
                tuple(
                    record[column]
                    for column in outcome_columns
                ),
            )

        for record in mapped_results:
            connection.execute(
                mapped_query,
                tuple(
                    record[column]
                    for column in mapped_columns
                ),
            )

        connection.commit()

        return (
            len(market_records),
            len(outcome_records),
            len(mapped_results),
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
            INSERT INTO market_resolution_runs (
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
    registry_markets_checked: int,
    resolved_markets_found: int,
    ambiguous_markets: int,
    unresolved_markets: int,
    resolution_rows_saved: int,
    outcome_rows_saved: int,
    mapped_results_saved: int,
    error_message: str = "",
) -> None:
    finished = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE market_resolution_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                registry_markets_checked = ?,
                resolved_markets_found = ?,
                ambiguous_markets = ?,
                unresolved_markets = ?,
                resolution_rows_saved = ?,
                outcome_rows_saved = ?,
                mapped_results_saved = ?,
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
                registry_markets_checked,
                resolved_markets_found,
                ambiguous_markets,
                unresolved_markets,
                resolution_rows_saved,
                outcome_rows_saved,
                mapped_results_saved,
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
    market_records: list[dict[str, Any]],
    outcome_records: list[dict[str, Any]],
    mapped_results: list[dict[str, Any]],
    display_limit: int,
) -> None:
    counts = Counter(
        record[
            "resolution_status"
        ]
        for record in market_records
    )

    print()
    print("=" * 108)
    print("MARKET RESOLUTION ENGINE SUMMARY")
    print("=" * 108)

    print(
        f"Registry markets checked:       "
        f"{len(market_records)}"
    )

    print(
        f"Resolved:                       "
        f"{counts.get('RESOLVED', 0)}"
    )

    print(
        f"Likely resolved:                "
        f"{counts.get('LIKELY_RESOLVED', 0)}"
    )

    print(
        f"Ambiguous:                      "
        f"{counts.get('AMBIGUOUS', 0)}"
    )

    print(
        f"Closed unresolved:              "
        f"{counts.get('CLOSED_UNRESOLVED', 0)}"
    )

    print(
        f"Open unresolved:                "
        f"{counts.get('UNRESOLVED', 0)}"
    )

    print(
        f"Resolution outcome rows:        "
        f"{len(outcome_records)}"
    )

    print(
        f"Mapped local result rows:       "
        f"{len(mapped_results)}"
    )

    print("=" * 108)

    resolved_records = [
        record
        for record in market_records
        if record[
            "resolution_status"
        ]
        in {
            "RESOLVED",
            "LIKELY_RESOLVED",
        }
    ]

    print()
    print("SAMPLE RESOLVED MARKETS")

    for rank, record in enumerate(
        resolved_records[
            :display_limit
        ],
        start=1,
    ):
        print()
        print("-" * 108)

        print(
            f"{rank}. "
            f"{record['question']}"
        )

        print("-" * 108)

        print(
            f"Status:                         "
            f"{record['resolution_status']}"
        )

        print(
            f"Winner:                         "
            f"{record['winning_outcome_name'] or '-'}"
        )

        print(
            f"Winning token:                  "
            f"{record['winning_token_id'] or '-'}"
        )

        print(
            f"Confidence:                     "
            f"{record['confidence_score']:.2f}"
        )


# =============================================================================
# ARGUMENTS AND MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect resolved Gamma markets, identify winning "
            "outcomes and label mapped local market results."
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
    print("POLYMARKET MARKET RESOLUTION ENGINE v1")
    print("=" * 108)

    print(
        f"Database: {DATABASE_PATH}"
    )

    create_resolution_tables()

    run_id, started_at = start_run()

    market_records: list[
        dict[str, Any]
    ] = []

    outcome_records: list[
        dict[str, Any]
    ] = []

    mapped_results: list[
        dict[str, Any]
    ] = []

    saved_markets = 0
    saved_outcomes = 0
    saved_mapped_results = 0

    try:
        (
            market_records,
            outcome_records,
        ) = build_resolution_records()

        resolution_lookup = {
            record[
                "gamma_market_id"
            ]: record
            for record in market_records
        }

        mapped_results = (
            build_mapped_results(
                resolution_lookup
            )
        )

        (
            saved_markets,
            saved_outcomes,
            saved_mapped_results,
        ) = save_resolution_data(
            market_records=(
                market_records
            ),
            outcome_records=(
                outcome_records
            ),
            mapped_results=(
                mapped_results
            ),
        )

        status_counts = Counter(
            record[
                "resolution_status"
            ]
            for record in market_records
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            registry_markets_checked=(
                len(market_records)
            ),
            resolved_markets_found=(
                status_counts.get(
                    "RESOLVED",
                    0,
                )
                + status_counts.get(
                    "LIKELY_RESOLVED",
                    0,
                )
            ),
            ambiguous_markets=(
                status_counts.get(
                    "AMBIGUOUS",
                    0,
                )
            ),
            unresolved_markets=(
                status_counts.get(
                    "UNRESOLVED",
                    0,
                )
                + status_counts.get(
                    "CLOSED_UNRESOLVED",
                    0,
                )
            ),
            resolution_rows_saved=(
                saved_markets
            ),
            outcome_rows_saved=(
                saved_outcomes
            ),
            mapped_results_saved=(
                saved_mapped_results
            ),
        )

        display_summary(
            market_records=(
                market_records
            ),
            outcome_records=(
                outcome_records
            ),
            mapped_results=(
                mapped_results
            ),
            display_limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 108)
        print("MARKET RESOLUTION ENGINE COMPLETE")
        print("=" * 108)

        print(
            "Market-level resolution records were saved "
            "to market_resolutions."
        )

        print(
            "Outcome-level settlement labels were saved "
            "to market_resolution_outcomes."
        )

        print(
            "Mapped local market result labels were saved "
            "to mapped_market_results."
        )

        print(
            "Only confirmed winner flags or terminal "
            "settlement prices produce resolved labels."
        )

        print("=" * 108)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            registry_markets_checked=(
                len(market_records)
            ),
            resolved_markets_found=0,
            ambiguous_markets=0,
            unresolved_markets=0,
            resolution_rows_saved=(
                saved_markets
            ),
            outcome_rows_saved=(
                saved_outcomes
            ),
            mapped_results_saved=(
                saved_mapped_results
            ),
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()