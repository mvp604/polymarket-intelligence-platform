"""
===============================================================================

Institutional Learning Outcome Engine
Version: 1.0

Purpose
-------
Convert officially verified Polymarket settlement facts into graded
institutional learning outcomes.

This engine evaluates whether prior BUY and AVOID decisions were correct.

Required settlement state
-------------------------
- resolution_status = RESOLVED
- actual_result IS NULL
- decision_action is BUY or AVOID
- source_outcome_won and source_outcome_lost are complementary binary values

Grading methodology
-------------------
BUY + selected outcome won:
    actual_result = WIN
    is_correct = 1

BUY + selected outcome lost:
    actual_result = LOSS
    is_correct = 0

AVOID + selected outcome lost:
    actual_result = CORRECT_AVOID
    is_correct = 1

AVOID + selected outcome won:
    actual_result = INCORRECT_AVOID
    is_correct = 0

Safety boundaries
-----------------
- Default mode is DRY RUN
- Database writes require --apply
- Existing actual_result values are never overwritten
- Unresolved observations are never graded
- Invalid settlement flags are quarantined
- Settlement verification is not performed here
- ROI is not calculated here
- Wallet rankings are not changed
- Conviction methodology is not changed

===============================================================================
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENGINE_VERSION = "1.0"

DATABASE_PATH = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "polymarket.db"
)

DEFAULT_LIMIT = 1000
DEFAULT_DISPLAY_LIMIT = 100


# =============================================================================
# GENERIC HELPERS
# =============================================================================


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def normalize_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value)
        .strip()
        .casefold()
        .split()
    )


def normalize_status(
    value: Any,
) -> str:
    return (
        normalize_text(value)
        .upper()
        .replace(" ", "_")
    )


def to_int(
    value: Any,
) -> int | None:
    if value is None:
        return None

    try:
        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


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
        (
            table_name,
        ),
    ).fetchone()

    return row is not None


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {
        str(
            row["name"]
        )
        for row in rows
    }


def validate_database(
    connection: sqlite3.Connection,
) -> None:
    table_name = (
        "institutional_learning_observations"
    )

    if not table_exists(
        connection,
        table_name,
    ):
        raise RuntimeError(
            "Missing required table: "
            f"{table_name}"
        )

    required_columns = {
        "observation_key",
        "market_id",
        "title",
        "selected_outcome",
        "decision_action",
        "resolution_status",
        "actual_result",
        "is_correct",
        "source_outcome_won",
        "source_outcome_lost",
        "winning_outcome",
        "resolved_at",
        "updated_at",
    }

    available_columns = table_columns(
        connection,
        table_name,
    )

    missing_columns = sorted(
        required_columns
        - available_columns
    )

    if missing_columns:
        raise RuntimeError(
            "institutional_learning_observations "
            "is missing required columns: "
            + ", ".join(
                missing_columns
            )
        )


# =============================================================================
# DATABASE TABLES
# =============================================================================


def create_engine_tables(
    connection: sqlite3.Connection,
) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS
        institutional_learning_outcome_runs (
            run_id TEXT PRIMARY KEY,

            engine_version TEXT NOT NULL,

            mode TEXT NOT NULL,

            started_at TEXT NOT NULL,

            completed_at TEXT,

            observations_loaded INTEGER
                NOT NULL DEFAULT 0,

            correct_buy_count INTEGER
                NOT NULL DEFAULT 0,

            incorrect_buy_count INTEGER
                NOT NULL DEFAULT 0,

            correct_avoid_count INTEGER
                NOT NULL DEFAULT 0,

            incorrect_avoid_count INTEGER
                NOT NULL DEFAULT 0,

            quarantined_count INTEGER
                NOT NULL DEFAULT 0,

            learning_rows_updated INTEGER
                NOT NULL DEFAULT 0,

            duration_seconds REAL,

            status TEXT NOT NULL,

            error_message TEXT
        );


        CREATE TABLE IF NOT EXISTS
        institutional_learning_outcome_audit (
            audit_key TEXT PRIMARY KEY,

            run_id TEXT NOT NULL,

            observation_key TEXT NOT NULL,

            market_id TEXT,

            title TEXT,

            selected_outcome TEXT,

            winning_outcome TEXT,

            decision_action TEXT NOT NULL,

            source_outcome_won INTEGER,

            source_outcome_lost INTEGER,

            calculated_actual_result TEXT,

            calculated_is_correct INTEGER,

            grading_status TEXT NOT NULL,

            grading_reason TEXT NOT NULL,

            evidence_json TEXT NOT NULL,

            created_at TEXT NOT NULL
        );


        CREATE INDEX IF NOT EXISTS
        idx_learning_outcome_audit_observation
        ON institutional_learning_outcome_audit (
            observation_key,
            created_at
        );


        CREATE INDEX IF NOT EXISTS
        idx_learning_outcome_audit_status
        ON institutional_learning_outcome_audit (
            grading_status,
            decision_action
        );


        CREATE TABLE IF NOT EXISTS
        institutional_learning_outcome_quarantine (
            quarantine_key TEXT PRIMARY KEY,

            observation_key TEXT NOT NULL,

            market_id TEXT,

            title TEXT,

            decision_action TEXT,

            quarantine_reason TEXT NOT NULL,

            evidence_json TEXT NOT NULL,

            first_seen_at TEXT NOT NULL,

            last_seen_at TEXT NOT NULL,

            occurrence_count INTEGER
                NOT NULL DEFAULT 1,

            resolved_from_quarantine INTEGER
                NOT NULL DEFAULT 0,

            resolution_note TEXT
        );


        CREATE INDEX IF NOT EXISTS
        idx_learning_outcome_quarantine_status
        ON institutional_learning_outcome_quarantine (
            resolved_from_quarantine,
            last_seen_at
        );
        """
    )


# =============================================================================
# OBSERVATION LOADING
# =============================================================================


def load_observations(
    connection: sqlite3.Connection,
    limit: int,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            observation_key,
            market_id,
            title,
            selected_outcome,
            winning_outcome,
            decision_action,
            resolution_status,
            source_outcome_won,
            source_outcome_lost,
            resolved_at

        FROM institutional_learning_observations

        WHERE actual_result IS NULL

          AND UPPER(
                TRIM(
                    COALESCE(
                        resolution_status,
                        ''
                    )
                )
              ) = 'RESOLVED'

          AND UPPER(
                TRIM(
                    COALESCE(
                        decision_action,
                        ''
                    )
                )
              ) IN (
                'BUY',
                'AVOID'
              )

        ORDER BY
            resolved_at ASC,
            observation_key ASC

        LIMIT ?
        """,
        (
            limit,
        ),
    ).fetchall()


# =============================================================================
# OUTCOME GRADING
# =============================================================================


def make_result(
    observation: sqlite3.Row,
    *,
    grading_status: str,
    grading_reason: str,
    actual_result: str | None = None,
    is_correct: int | None = None,
) -> dict[str, Any]:
    evidence = {
        "observation": dict(
            observation
        ),

        "engine_version": (
            ENGINE_VERSION
        ),

        "graded_at": utc_now(),

        "methodology": (
            "DETERMINISTIC_DECISION_AND_"
            "SETTLEMENT_FLAG_GRADING"
        ),
    }

    return {
        "observation_key": (
            observation[
                "observation_key"
            ]
        ),

        "market_id": (
            observation[
                "market_id"
            ]
        ),

        "title": (
            observation[
                "title"
            ]
        ),

        "selected_outcome": (
            observation[
                "selected_outcome"
            ]
        ),

        "winning_outcome": (
            observation[
                "winning_outcome"
            ]
        ),

        "decision_action": (
            normalize_status(
                observation[
                    "decision_action"
                ]
            )
        ),

        "source_outcome_won": (
            to_int(
                observation[
                    "source_outcome_won"
                ]
            )
        ),

        "source_outcome_lost": (
            to_int(
                observation[
                    "source_outcome_lost"
                ]
            )
        ),

        "actual_result": (
            actual_result
        ),

        "is_correct": (
            is_correct
        ),

        "grading_status": (
            grading_status
        ),

        "grading_reason": (
            grading_reason
        ),

        "evidence_json": json.dumps(
            evidence,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ),
    }


def grade_observation(
    observation: sqlite3.Row,
) -> dict[str, Any]:
    decision_action = normalize_status(
        observation[
            "decision_action"
        ]
    )

    resolution_status = normalize_status(
        observation[
            "resolution_status"
        ]
    )

    source_outcome_won = to_int(
        observation[
            "source_outcome_won"
        ]
    )

    source_outcome_lost = to_int(
        observation[
            "source_outcome_lost"
        ]
    )

    if resolution_status != "RESOLVED":
        return make_result(
            observation,
            grading_status=(
                "QUARANTINED_NOT_RESOLVED"
            ),
            grading_reason=(
                "Observation is not officially "
                "marked RESOLVED."
            ),
        )

    if decision_action not in {
        "BUY",
        "AVOID",
    }:
        return make_result(
            observation,
            grading_status=(
                "QUARANTINED_INVALID_ACTION"
            ),
            grading_reason=(
                "Decision action must be "
                "BUY or AVOID."
            ),
        )

    if (
        source_outcome_won
        not in {
            0,
            1,
        }
        or source_outcome_lost
        not in {
            0,
            1,
        }
    ):
        return make_result(
            observation,
            grading_status=(
                "QUARANTINED_INVALID_FLAGS"
            ),
            grading_reason=(
                "Settlement win/loss flags "
                "must both be binary."
            ),
        )

    if (
        source_outcome_won
        + source_outcome_lost
        != 1
    ):
        return make_result(
            observation,
            grading_status=(
                "QUARANTINED_NON_COMPLEMENTARY_FLAGS"
            ),
            grading_reason=(
                "Settlement win/loss flags "
                "must be complementary."
            ),
        )

    if (
        decision_action == "BUY"
        and source_outcome_won == 1
    ):
        return make_result(
            observation,
            grading_status=(
                "GRADED_CORRECT_BUY"
            ),
            grading_reason=(
                "BUY recommendation selected "
                "the official winning outcome."
            ),
            actual_result="WIN",
            is_correct=1,
        )

    if (
        decision_action == "BUY"
        and source_outcome_lost == 1
    ):
        return make_result(
            observation,
            grading_status=(
                "GRADED_INCORRECT_BUY"
            ),
            grading_reason=(
                "BUY recommendation selected "
                "a losing outcome."
            ),
            actual_result="LOSS",
            is_correct=0,
        )

    if (
        decision_action == "AVOID"
        and source_outcome_lost == 1
    ):
        return make_result(
            observation,
            grading_status=(
                "GRADED_CORRECT_AVOID"
            ),
            grading_reason=(
                "AVOID recommendation correctly "
                "rejected a losing outcome."
            ),
            actual_result="CORRECT_AVOID",
            is_correct=1,
        )

    if (
        decision_action == "AVOID"
        and source_outcome_won == 1
    ):
        return make_result(
            observation,
            grading_status=(
                "GRADED_INCORRECT_AVOID"
            ),
            grading_reason=(
                "AVOID recommendation rejected "
                "the official winning outcome."
            ),
            actual_result="INCORRECT_AVOID",
            is_correct=0,
        )

    return make_result(
        observation,
        grading_status=(
            "QUARANTINED_UNCLASSIFIED"
        ),
        grading_reason=(
            "Observation could not be "
            "classified safely."
        ),
    )


# =============================================================================
# PERSISTENCE
# =============================================================================


def make_audit_key(
    run_id: str,
    observation_key: str,
) -> str:
    return hashlib.sha256(
        (
            f"{run_id}|"
            f"{observation_key}"
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def make_quarantine_key(
    observation_key: str,
    grading_status: str,
) -> str:
    return hashlib.sha256(
        (
            f"{observation_key}|"
            f"{grading_status}"
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def save_results(
    connection: sqlite3.Connection,
    run_id: str,
    results: list[dict[str, Any]],
) -> int:
    now = utc_now()
    updated_rows = 0

    for result in results:
        connection.execute(
            """
            INSERT INTO
            institutional_learning_outcome_audit (
                audit_key,
                run_id,
                observation_key,
                market_id,
                title,
                selected_outcome,
                winning_outcome,
                decision_action,
                source_outcome_won,
                source_outcome_lost,
                calculated_actual_result,
                calculated_is_correct,
                grading_status,
                grading_reason,
                evidence_json,
                created_at
            )

            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                make_audit_key(
                    run_id,
                    result[
                        "observation_key"
                    ],
                ),

                run_id,

                result[
                    "observation_key"
                ],

                result[
                    "market_id"
                ],

                result[
                    "title"
                ],

                result[
                    "selected_outcome"
                ],

                result[
                    "winning_outcome"
                ],

                result[
                    "decision_action"
                ],

                result[
                    "source_outcome_won"
                ],

                result[
                    "source_outcome_lost"
                ],

                result[
                    "actual_result"
                ],

                result[
                    "is_correct"
                ],

                result[
                    "grading_status"
                ],

                result[
                    "grading_reason"
                ],

                result[
                    "evidence_json"
                ],

                now,
            ),
        )

        if result[
            "grading_status"
        ].startswith(
            "QUARANTINED"
        ):
            quarantine_key = (
                make_quarantine_key(
                    result[
                        "observation_key"
                    ],
                    result[
                        "grading_status"
                    ],
                )
            )

            connection.execute(
                """
                INSERT INTO
                institutional_learning_outcome_quarantine (
                    quarantine_key,
                    observation_key,
                    market_id,
                    title,
                    decision_action,
                    quarantine_reason,
                    evidence_json,
                    first_seen_at,
                    last_seen_at,
                    occurrence_count,
                    resolved_from_quarantine
                )

                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0
                )

                ON CONFLICT(
                    quarantine_key
                )

                DO UPDATE SET
                    quarantine_reason =
                        excluded.quarantine_reason,

                    evidence_json =
                        excluded.evidence_json,

                    last_seen_at =
                        excluded.last_seen_at,

                    occurrence_count =
                        occurrence_count + 1
                """,
                (
                    quarantine_key,

                    result[
                        "observation_key"
                    ],

                    result[
                        "market_id"
                    ],

                    result[
                        "title"
                    ],

                    result[
                        "decision_action"
                    ],

                    result[
                        "grading_reason"
                    ],

                    result[
                        "evidence_json"
                    ],

                    now,

                    now,
                ),
            )

            continue

        cursor = connection.execute(
            """
            UPDATE
                institutional_learning_observations

            SET
                actual_result = ?,

                is_correct = ?,

                updated_at = ?

            WHERE observation_key = ?

              AND actual_result IS NULL

              AND UPPER(
                    TRIM(
                        COALESCE(
                            resolution_status,
                            ''
                        )
                    )
                  ) = 'RESOLVED'

              AND source_outcome_won = ?

              AND source_outcome_lost = ?
            """,
            (
                result[
                    "actual_result"
                ],

                result[
                    "is_correct"
                ],

                utc_now(),

                result[
                    "observation_key"
                ],

                result[
                    "source_outcome_won"
                ],

                result[
                    "source_outcome_lost"
                ],
            ),
        )

        updated_rows += (
            cursor.rowcount
        )

    return updated_rows


# =============================================================================
# REPORTING
# =============================================================================


def result_bucket(
    grading_status: str,
) -> str:
    mapping = {
        "GRADED_CORRECT_BUY": (
            "CORRECT_BUY"
        ),

        "GRADED_INCORRECT_BUY": (
            "INCORRECT_BUY"
        ),

        "GRADED_CORRECT_AVOID": (
            "CORRECT_AVOID"
        ),

        "GRADED_INCORRECT_AVOID": (
            "INCORRECT_AVOID"
        ),
    }

    return mapping.get(
        grading_status,
        "QUARANTINED",
    )


def print_result(
    index: int,
    result: dict[str, Any],
) -> None:
    print(
        f"{index:>3}. "
        f"{result['grading_status']:<31} "
        f"{result['decision_action']:<6} "
        f"result="
        f"{(result['actual_result'] or '-'):<18} "
        f"correct="
        f"{str(result['is_correct']):<4}"
    )

    print(
        f"     selected="
        f"{result['selected_outcome']} "
        f"| winner="
        f"{result['winning_outcome'] or '-'}"
    )

    print(
        f"     title="
        f"{result['title']}"
    )

    print(
        f"     market_id="
        f"{result['market_id']}"
    )

    print(
        f"     reason="
        f"{result['grading_reason']}"
    )


def print_summary(
    mode: str,
    run_id: str,
    observations: list[sqlite3.Row],
    results: list[dict[str, Any]],
    updated_rows: int,
    duration_seconds: float,
    display_limit: int,
) -> None:
    buckets = [
        result_bucket(
            result[
                "grading_status"
            ]
        )
        for result in results
    ]

    print()
    print(
        "=" * 145
    )

    print(
        "POLYMARKET INSTITUTIONAL "
        "LEARNING OUTCOME ENGINE v1.0"
    )

    print(
        "=" * 145
    )

    print(
        f"Database:                       "
        f"{DATABASE_PATH}"
    )

    print(
        f"Mode:                           "
        f"{mode}"
    )

    print(
        f"Run ID:                         "
        f"{run_id}"
    )

    print(
        f"Eligible resolved observations: "
        f"{len(observations):,}"
    )

    print(
        f"Correct BUY decisions:          "
        f"{buckets.count('CORRECT_BUY'):,}"
    )

    print(
        f"Incorrect BUY decisions:        "
        f"{buckets.count('INCORRECT_BUY'):,}"
    )

    print(
        f"Correct AVOID decisions:        "
        f"{buckets.count('CORRECT_AVOID'):,}"
    )

    print(
        f"Incorrect AVOID decisions:      "
        f"{buckets.count('INCORRECT_AVOID'):,}"
    )

    print(
        f"Quarantined:                    "
        f"{buckets.count('QUARANTINED'):,}"
    )

    print(
        f"Learning rows updated:          "
        f"{updated_rows:,}"
    )

    print(
        f"Duration:                       "
        f"{duration_seconds:.3f}s"
    )

    print(
        "=" * 145
    )

    print()
    print(
        "OUTCOME GRADING BOARD"
    )

    print(
        "-" * 145
    )

    for index, result in enumerate(
        results[
            :display_limit
        ],
        start=1,
    ):
        print_result(
            index,
            result,
        )

    if (
        len(results)
        > display_limit
    ):
        print()

        print(
            f"... "
            f"{len(results) - display_limit:,} "
            f"additional rows omitted."
        )

    print()
    print(
        "SAFETY INTERPRETATION"
    )

    print(
        "-" * 145
    )

    print(
        "Settlement requirement:         "
        "resolution_status = RESOLVED"
    )

    print(
        "Settlement flag requirement:    "
        "COMPLEMENTARY BINARY FLAGS"
    )

    print(
        "Existing actual_result values:  "
        "NEVER OVERWRITTEN"
    )

    print(
        "Settlement verification:        "
        "NOT PERFORMED"
    )

    print(
        "ROI calculation:                "
        "NOT PERFORMED"
    )

    print(
        "Wallet rankings:                "
        "NOT MODIFIED"
    )

    print(
        "Conviction methodology:         "
        "NOT MODIFIED"
    )

    print(
        "=" * 145
    )

    if mode == "DRY RUN":
        print(
            "Dry run complete. "
            "No database records were modified."
        )

    else:
        print(
            "Outcome audits were saved. "
            "Only safely graded unresolved "
            "learning rows were updated."
        )

    print(
        "=" * 145
    )


# =============================================================================
# COMMAND-LINE ARGUMENTS
# =============================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Grade officially resolved "
            "institutional learning observations."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Persist outcome audits, quarantine "
            "records and safely graded outcomes."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=(
            DEFAULT_DISPLAY_LIMIT
        ),
    )

    return parser.parse_args()


# =============================================================================
# MAIN ENGINE
# =============================================================================


def main() -> None:
    args = parse_args()

    mode = (
        "APPLY"
        if args.apply
        else "DRY RUN"
    )

    run_id = uuid.uuid4().hex
    started_at = utc_now()
    started_clock = time.perf_counter()

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = (
        sqlite3.Row
    )

    run_saved = False

    try:
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        validate_database(
            connection
        )

        observations = load_observations(
            connection,
            max(
                args.limit,
                1,
            ),
        )

        results = [
            grade_observation(
                observation
            )
            for observation in observations
        ]

        updated_rows = 0

        if args.apply:
            create_engine_tables(
                connection
            )

            connection.commit()

            connection.execute(
                """
                INSERT INTO
                institutional_learning_outcome_runs (
                    run_id,
                    engine_version,
                    mode,
                    started_at,
                    status
                )

                VALUES (
                    ?, ?, ?, ?, 'RUNNING'
                )
                """,
                (
                    run_id,
                    ENGINE_VERSION,
                    mode,
                    started_at,
                ),
            )

            connection.commit()
            run_saved = True

            connection.execute(
                "BEGIN"
            )

            updated_rows = save_results(
                connection,
                run_id,
                results,
            )

            buckets = [
                result_bucket(
                    result[
                        "grading_status"
                    ]
                )
                for result in results
            ]

            duration_seconds = (
                time.perf_counter()
                - started_clock
            )

            connection.execute(
                """
                UPDATE
                    institutional_learning_outcome_runs

                SET
                    completed_at = ?,

                    observations_loaded = ?,

                    correct_buy_count = ?,

                    incorrect_buy_count = ?,

                    correct_avoid_count = ?,

                    incorrect_avoid_count = ?,

                    quarantined_count = ?,

                    learning_rows_updated = ?,

                    duration_seconds = ?,

                    status = 'COMPLETED'

                WHERE run_id = ?
                """,
                (
                    utc_now(),

                    len(
                        observations
                    ),

                    buckets.count(
                        "CORRECT_BUY"
                    ),

                    buckets.count(
                        "INCORRECT_BUY"
                    ),

                    buckets.count(
                        "CORRECT_AVOID"
                    ),

                    buckets.count(
                        "INCORRECT_AVOID"
                    ),

                    buckets.count(
                        "QUARANTINED"
                    ),

                    updated_rows,

                    duration_seconds,

                    run_id,
                ),
            )

            connection.commit()

        duration_seconds = (
            time.perf_counter()
            - started_clock
        )

        print_summary(
            mode,
            run_id,
            observations,
            results,
            updated_rows,
            duration_seconds,
            max(
                args.display_limit,
                1,
            ),
        )

    except Exception as error:
        connection.rollback()

        if (
            args.apply
            and run_saved
        ):
            try:
                connection.execute(
                    """
                    UPDATE
                        institutional_learning_outcome_runs

                    SET
                        completed_at = ?,

                        duration_seconds = ?,

                        status = 'FAILED',

                        error_message = ?

                    WHERE run_id = ?
                    """,
                    (
                        utc_now(),

                        (
                            time.perf_counter()
                            - started_clock
                        ),

                        (
                            f"{type(error).__name__}: "
                            f"{error}"
                        ),

                        run_id,
                    ),
                )

                connection.commit()

            except Exception:
                connection.rollback()

        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()
