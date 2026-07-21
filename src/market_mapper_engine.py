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

LOCAL_SOURCE_TABLES = (
    ("positions", "POSITIONS"),
    ("opportunity_scores", "OPPORTUNITY_SCORES"),
    ("consensus_history", "CONSENSUS_HISTORY"),
    ("market_metadata", "MARKET_METADATA"),
    ("tracked_markets", "TRACKED_MARKETS"),
)


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


def normalize_market_id(value: Any) -> str:
    return clean_text(value).lower()


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    if not table_exists(
        connection,
        table_name,
    ):
        return set()

    return {
        clean_text(row["name"])
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


# =============================================================================
# MAPPER TABLES
# =============================================================================


def create_mapper_tables() -> None:
    connection = connect_database()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS market_mappings (
                mapping_key TEXT PRIMARY KEY,

                source_table TEXT NOT NULL,
                source_market_id TEXT NOT NULL,
                source_title TEXT,
                source_outcome TEXT,

                gamma_market_id TEXT,
                gamma_event_id TEXT,
                condition_id TEXT,

                canonical_question TEXT,
                canonical_slug TEXT,

                match_method TEXT NOT NULL,
                match_confidence REAL
                    NOT NULL DEFAULT 0,

                mapping_status TEXT NOT NULL,

                outcome_count INTEGER
                    NOT NULL DEFAULT 0,

                token_count INTEGER
                    NOT NULL DEFAULT 0,

                source_payload_json TEXT,
                registry_payload_json TEXT,

                first_mapped_at TEXT NOT NULL,
                last_mapped_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_mappings_source
            ON market_mappings(
                source_table,
                source_market_id
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_mappings_condition
            ON market_mappings(
                condition_id
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_mappings_status
            ON market_mappings(
                mapping_status,
                match_confidence DESC
            );

            CREATE TABLE IF NOT EXISTS market_mapping_outcomes (
                mapping_outcome_key TEXT PRIMARY KEY,

                mapping_key TEXT NOT NULL,
                gamma_market_id TEXT NOT NULL,
                gamma_event_id TEXT,
                condition_id TEXT,

                outcome_index INTEGER NOT NULL,
                outcome_name TEXT NOT NULL,
                token_id TEXT,
                implied_price REAL,
                winner INTEGER
                    NOT NULL DEFAULT 0,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(
                    mapping_key
                )
                REFERENCES market_mappings(
                    mapping_key
                )
                ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_mapping_outcomes_mapping
            ON market_mapping_outcomes(
                mapping_key,
                outcome_index
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_mapping_outcomes_token
            ON market_mapping_outcomes(
                token_id
            );

            CREATE TABLE IF NOT EXISTS market_mapper_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                source_rows_loaded INTEGER
                    NOT NULL DEFAULT 0,

                exact_condition_matches INTEGER
                    NOT NULL DEFAULT 0,

                unresolved_rows INTEGER
                    NOT NULL DEFAULT 0,

                mappings_saved INTEGER
                    NOT NULL DEFAULT 0,

                outcomes_saved INTEGER
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
# LOCAL SOURCE LOADING
# =============================================================================


def load_local_markets() -> list[dict[str, Any]]:
    connection = connect_database()
    output: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    try:
        for table_name, source_name in LOCAL_SOURCE_TABLES:
            if not table_exists(
                connection,
                table_name,
            ):
                continue

            columns = table_columns(
                connection,
                table_name,
            )

            if "market_id" not in columns:
                continue

            selected_columns = [
                "market_id",
            ]

            for optional in (
                "title",
                "outcome",
            ):
                if optional in columns:
                    selected_columns.append(
                        optional
                    )

            rows = connection.execute(
                f"""
                SELECT
                    {", ".join(selected_columns)}
                FROM "{table_name}"
                WHERE market_id IS NOT NULL
                  AND TRIM(
                        CAST(
                            market_id AS TEXT
                        )
                      ) != ''
                """
            ).fetchall()

            for row in rows:
                market_id = normalize_market_id(
                    row["market_id"]
                )

                title = (
                    clean_text(
                        row["title"]
                    )
                    if "title"
                    in row.keys()
                    else ""
                )

                outcome = (
                    clean_text(
                        row["outcome"]
                    )
                    if "outcome"
                    in row.keys()
                    else ""
                )

                key = (
                    source_name,
                    market_id,
                )

                prior = output.get(key)

                candidate = {
                    "source_table": (
                        source_name
                    ),
                    "source_market_id": (
                        market_id
                    ),
                    "source_title": title,
                    "source_outcome": outcome,
                    "source_payload_json": (
                        stable_json(
                            dict(row)
                        )
                    ),
                }

                if prior is None:
                    output[key] = candidate
                    continue

                prior_quality = sum(
                    bool(
                        clean_text(
                            prior.get(field)
                        )
                    )
                    for field in (
                        "source_title",
                        "source_outcome",
                    )
                )

                current_quality = sum(
                    bool(
                        clean_text(
                            candidate.get(field)
                        )
                    )
                    for field in (
                        "source_title",
                        "source_outcome",
                    )
                )

                if current_quality > prior_quality:
                    output[key] = candidate

    finally:
        connection.close()

    return list(
        output.values()
    )


# =============================================================================
# EXACT CONDITION-ID MAPPING
# =============================================================================


def load_gamma_by_condition() -> dict[
    str,
    list[dict[str, Any]],
]:
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
            WHERE condition_id IS NOT NULL
              AND TRIM(condition_id) != ''
            """
        ).fetchall()

    finally:
        connection.close()

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for row in rows:
        condition_id = normalize_market_id(
            row["condition_id"]
        )

        grouped.setdefault(
            condition_id,
            [],
        ).append(
            dict(row)
        )

    return grouped


def load_gamma_outcomes(
    gamma_market_ids: set[str],
) -> dict[
    str,
    list[dict[str, Any]],
]:
    if not gamma_market_ids:
        return {}

    connection = connect_database()

    try:
        placeholders = ", ".join(
            "?"
            for _ in gamma_market_ids
        )

        rows = connection.execute(
            f"""
            SELECT *
            FROM gamma_market_outcomes
            WHERE gamma_market_id IN (
                {placeholders}
            )
            ORDER BY
                gamma_market_id,
                outcome_index
            """,
            list(gamma_market_ids),
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


def choose_best_gamma_match(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    return max(
        candidates,
        key=lambda row: (
            safe_int(
                row.get(
                    "active"
                )
            ),
            -safe_int(
                row.get(
                    "closed"
                )
            ),
            safe_int(
                row.get(
                    "accepting_orders"
                )
            ),
            float(
                row.get(
                    "liquidity"
                )
                or 0.0
            ),
            float(
                row.get(
                    "volume"
                )
                or 0.0
            ),
        ),
    )


def build_mappings() -> tuple[
    list[dict[str, Any]],
    int,
    int,
]:
    local_rows = load_local_markets()
    gamma_lookup = (
        load_gamma_by_condition()
    )

    mappings: list[
        dict[str, Any]
    ] = []

    exact_matches = 0
    unresolved = 0
    timestamp = utc_now_iso()

    for source in local_rows:
        source_market_id = (
            source[
                "source_market_id"
            ]
        )

        candidates = gamma_lookup.get(
            source_market_id,
            [],
        )

        mapping_key = (
            f"{source['source_table']}:"
            f"{source_market_id}"
        )

        if candidates:
            selected = (
                choose_best_gamma_match(
                    candidates
                )
            )

            exact_matches += 1

            mapping_status = "MAPPED"
            match_method = "CONDITION_ID"
            match_confidence = 100.0

            gamma_market_id = clean_text(
                selected.get(
                    "gamma_market_id"
                )
            )

            gamma_event_id = clean_text(
                selected.get(
                    "gamma_event_id"
                )
            )

            condition_id = normalize_market_id(
                selected.get(
                    "condition_id"
                )
            )

            canonical_question = clean_text(
                selected.get(
                    "question"
                )
            )

            canonical_slug = clean_text(
                selected.get(
                    "slug"
                )
            )

            outcome_count = safe_int(
                selected.get(
                    "outcome_count"
                )
            )

            registry_payload_json = (
                clean_text(
                    selected.get(
                        "raw_payload_json"
                    )
                )
            )

        else:
            unresolved += 1

            mapping_status = "UNRESOLVED"
            match_method = "NONE"
            match_confidence = 0.0

            gamma_market_id = ""
            gamma_event_id = ""
            condition_id = ""
            canonical_question = ""
            canonical_slug = ""
            outcome_count = 0
            registry_payload_json = ""

        mappings.append(
            {
                "mapping_key": mapping_key,

                "source_table": (
                    source[
                        "source_table"
                    ]
                ),

                "source_market_id": (
                    source_market_id
                ),

                "source_title": (
                    source[
                        "source_title"
                    ]
                ),

                "source_outcome": (
                    source[
                        "source_outcome"
                    ]
                ),

                "gamma_market_id": (
                    gamma_market_id
                ),

                "gamma_event_id": (
                    gamma_event_id
                ),

                "condition_id": (
                    condition_id
                ),

                "canonical_question": (
                    canonical_question
                ),

                "canonical_slug": (
                    canonical_slug
                ),

                "match_method": (
                    match_method
                ),

                "match_confidence": (
                    match_confidence
                ),

                "mapping_status": (
                    mapping_status
                ),

                "outcome_count": (
                    outcome_count
                ),

                "token_count": 0,

                "source_payload_json": (
                    source[
                        "source_payload_json"
                    ]
                ),

                "registry_payload_json": (
                    registry_payload_json
                ),

                "first_mapped_at": (
                    timestamp
                ),

                "last_mapped_at": (
                    timestamp
                ),

                "updated_at": (
                    timestamp
                ),
            }
        )

    return (
        mappings,
        exact_matches,
        unresolved,
    )


# =============================================================================
# SAVING
# =============================================================================


def save_mappings(
    mappings: list[dict[str, Any]],
) -> tuple[int, int]:
    mapped_market_ids = {
        clean_text(
            mapping[
                "gamma_market_id"
            ]
        )
        for mapping in mappings
        if clean_text(
            mapping[
                "gamma_market_id"
            ]
        )
    }

    outcomes_lookup = (
        load_gamma_outcomes(
            mapped_market_ids
        )
    )

    connection = connect_database()

    mapping_columns = [
        "mapping_key",
        "source_table",
        "source_market_id",
        "source_title",
        "source_outcome",
        "gamma_market_id",
        "gamma_event_id",
        "condition_id",
        "canonical_question",
        "canonical_slug",
        "match_method",
        "match_confidence",
        "mapping_status",
        "outcome_count",
        "token_count",
        "source_payload_json",
        "registry_payload_json",
        "first_mapped_at",
        "last_mapped_at",
        "updated_at",
    ]

    names = ", ".join(
        f'"{column}"'
        for column in mapping_columns
    )

    placeholders = ", ".join(
        "?"
        for _ in mapping_columns
    )

    updates = ", ".join(
        f'"{column}" = '
        f'excluded."{column}"'
        for column in mapping_columns
        if column not in {
            "mapping_key",
            "first_mapped_at",
        }
    )

    mapping_query = f"""
        INSERT INTO market_mappings (
            {names}
        )
        VALUES (
            {placeholders}
        )
        ON CONFLICT(mapping_key)
        DO UPDATE SET
            {updates}
    """

    mappings_saved = 0
    outcomes_saved = 0
    timestamp = utc_now_iso()

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        for mapping in mappings:
            gamma_market_id = clean_text(
                mapping[
                    "gamma_market_id"
                ]
            )

            outcomes = (
                outcomes_lookup.get(
                    gamma_market_id,
                    [],
                )
            )

            mapping[
                "token_count"
            ] = sum(
                1
                for outcome in outcomes
                if clean_text(
                    outcome.get(
                        "token_id"
                    )
                )
            )

            existing = connection.execute(
                """
                SELECT first_mapped_at
                FROM market_mappings
                WHERE mapping_key = ?
                """,
                (
                    mapping[
                        "mapping_key"
                    ],
                ),
            ).fetchone()

            if existing is not None:
                mapping[
                    "first_mapped_at"
                ] = clean_text(
                    existing[
                        "first_mapped_at"
                    ]
                )

            connection.execute(
                mapping_query,
                tuple(
                    mapping[column]
                    for column in mapping_columns
                ),
            )

            mappings_saved += 1

            connection.execute(
                """
                DELETE FROM market_mapping_outcomes
                WHERE mapping_key = ?
                """,
                (
                    mapping[
                        "mapping_key"
                    ],
                ),
            )

            for outcome in outcomes:
                outcome_index = safe_int(
                    outcome.get(
                        "outcome_index"
                    )
                )

                mapping_outcome_key = (
                    f"{mapping['mapping_key']}:"
                    f"{outcome_index}"
                )

                connection.execute(
                    """
                    INSERT INTO market_mapping_outcomes (
                        mapping_outcome_key,
                        mapping_key,
                        gamma_market_id,
                        gamma_event_id,
                        condition_id,
                        outcome_index,
                        outcome_name,
                        token_id,
                        implied_price,
                        winner,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        mapping_outcome_key,
                        mapping[
                            "mapping_key"
                        ],
                        gamma_market_id,
                        mapping[
                            "gamma_event_id"
                        ],
                        mapping[
                            "condition_id"
                        ],
                        outcome_index,
                        clean_text(
                            outcome.get(
                                "outcome_name"
                            )
                        ),
                        clean_text(
                            outcome.get(
                                "token_id"
                            )
                        ),
                        outcome.get(
                            "implied_price"
                        ),
                        safe_int(
                            outcome.get(
                                "winner"
                            )
                        ),
                        timestamp,
                        timestamp,
                    ),
                )

                outcomes_saved += 1

        connection.commit()

        return (
            mappings_saved,
            outcomes_saved,
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
            INSERT INTO market_mapper_runs (
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
    source_rows_loaded: int,
    exact_condition_matches: int,
    unresolved_rows: int,
    mappings_saved: int,
    outcomes_saved: int,
    error_message: str = "",
) -> None:
    finished = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE market_mapper_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                source_rows_loaded = ?,
                exact_condition_matches = ?,
                unresolved_rows = ?,
                mappings_saved = ?,
                outcomes_saved = ?,
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
                source_rows_loaded,
                exact_condition_matches,
                unresolved_rows,
                mappings_saved,
                outcomes_saved,
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
    mappings: list[dict[str, Any]],
    mappings_saved: int,
    outcomes_saved: int,
    display_limit: int,
) -> None:
    counts = Counter(
        mapping[
            "mapping_status"
        ]
        for mapping in mappings
    )

    print()
    print("=" * 108)
    print("MARKET MAPPER STAGE 1 SUMMARY")
    print("=" * 108)

    print(
        f"Local source rows:              "
        f"{len(mappings)}"
    )

    print(
        f"Mapped by condition ID:         "
        f"{counts.get('MAPPED', 0)}"
    )

    print(
        f"Unresolved:                     "
        f"{counts.get('UNRESOLVED', 0)}"
    )

    print(
        f"Mappings saved:                 "
        f"{mappings_saved}"
    )

    print(
        f"Outcome/token rows saved:       "
        f"{outcomes_saved}"
    )

    print("=" * 108)

    mapped = [
        mapping
        for mapping in mappings
        if mapping[
            "mapping_status"
        ] == "MAPPED"
    ]

    print()
    print("TOP EXACT CONDITION-ID MAPPINGS")

    for rank, mapping in enumerate(
        mapped[:display_limit],
        start=1,
    ):
        print()
        print("-" * 108)

        print(
            f"{rank}. "
            f"{mapping['source_title'] or mapping['source_market_id']}"
        )

        print("-" * 108)

        print(
            f"Source table:                   "
            f"{mapping['source_table']}"
        )

        print(
            f"Source market ID:               "
            f"{mapping['source_market_id']}"
        )

        print(
            f"Gamma market ID:                "
            f"{mapping['gamma_market_id']}"
        )

        print(
            f"Canonical question:             "
            f"{mapping['canonical_question']}"
        )

        print(
            f"Outcomes / tokens:              "
            f"{mapping['outcome_count']} "
            f"/ {mapping['token_count']}"
        )


# =============================================================================
# ARGUMENTS AND MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stage 1 Market Mapper: map local market IDs "
            "to the Gamma registry using exact condition IDs."
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
    print("POLYMARKET MARKET MAPPER ENGINE v1 - STAGE 1")
    print("=" * 108)

    print(
        f"Database: {DATABASE_PATH}"
    )

    print(
        "Mapping method: exact condition ID only"
    )

    create_mapper_tables()

    run_id, started_at = start_run()

    mappings: list[
        dict[str, Any]
    ] = []

    exact_matches = 0
    unresolved = 0
    mappings_saved = 0
    outcomes_saved = 0

    try:
        (
            mappings,
            exact_matches,
            unresolved,
        ) = build_mappings()

        (
            mappings_saved,
            outcomes_saved,
        ) = save_mappings(
            mappings
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            source_rows_loaded=(
                len(mappings)
            ),
            exact_condition_matches=(
                exact_matches
            ),
            unresolved_rows=(
                unresolved
            ),
            mappings_saved=(
                mappings_saved
            ),
            outcomes_saved=(
                outcomes_saved
            ),
        )

        display_summary(
            mappings=mappings,
            mappings_saved=(
                mappings_saved
            ),
            outcomes_saved=(
                outcomes_saved
            ),
            display_limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 108)
        print("MARKET MAPPER STAGE 1 COMPLETE")
        print("=" * 108)

        print(
            "Exact mappings were saved to "
            "market_mappings."
        )

        print(
            "Mapped outcomes and CLOB token IDs were saved "
            "to market_mapping_outcomes."
        )

        print(
            "Unresolved rows were preserved for later slug, "
            "event, and structured matching stages."
        )

        print("=" * 108)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            source_rows_loaded=(
                len(mappings)
            ),
            exact_condition_matches=(
                exact_matches
            ),
            unresolved_rows=(
                unresolved
            ),
            mappings_saved=(
                mappings_saved
            ),
            outcomes_saved=(
                outcomes_saved
            ),
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()