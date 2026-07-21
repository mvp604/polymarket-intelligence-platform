from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_DISPLAY_LIMIT = 30
DEFAULT_MIN_TITLE_CONFIDENCE = 92.0


# =============================================================================
# GENERAL HELPERS
# =============================================================================


def configure_utf8() -> None:
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


def normalize_identifier(value: Any) -> str:
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


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def parse_json_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(
        value,
        (
            dict,
            list,
            int,
            float,
            bool,
        ),
    ):
        return value

    raw = clean_text(value)

    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def normalize_title(value: Any) -> str:
    raw = clean_text(value).lower()

    replacements = {
        "–": "-",
        "—": "-",
        "−": "-",
        "’": "'",
        "“": '"',
        "”": '"',
        "&": " and ",
        " vs. ": " vs ",
        " v. ": " vs ",
        " v ": " vs ",
    }

    for source, target in replacements.items():
        raw = raw.replace(
            source,
            target,
        )

    normalized = "".join(
        character
        if character.isalnum()
        else " "
        for character in raw
    )

    return " ".join(
        normalized.split()
    )


def title_similarity(
    left: Any,
    right: Any,
) -> float:
    left_normalized = normalize_title(
        left
    )

    right_normalized = normalize_title(
        right
    )

    if (
        not left_normalized
        or not right_normalized
    ):
        return 0.0

    if left_normalized == right_normalized:
        return 100.0

    left_tokens = set(
        left_normalized.split()
    )

    right_tokens = set(
        right_normalized.split()
    )

    if not left_tokens or not right_tokens:
        return 0.0

    intersection = len(
        left_tokens
        & right_tokens
    )

    union = len(
        left_tokens
        | right_tokens
    )

    containment = max(
        intersection
        / len(left_tokens),
        intersection
        / len(right_tokens),
    )

    jaccard = (
        intersection
        / union
        if union
        else 0.0
    )

    return min(
        100.0,
        (
            containment
            * 0.70
            + jaccard
            * 0.30
        )
        * 100.0,
    )


# =============================================================================
# DATABASE HELPERS
# =============================================================================


def connect_database() -> sqlite3.Connection:
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
    if not table_exists(
        connection,
        table_name,
    ):
        return set()

    return {
        clean_text(
            row["name"]
        )
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


def row_value(
    row: sqlite3.Row,
    columns: set[str],
    candidates: tuple[str, ...],
) -> Any:
    column = first_existing(
        columns,
        candidates,
    )

    if column is None:
        return None

    return row[column]


# =============================================================================
# TABLE CREATION
# =============================================================================


def create_tables() -> None:
    connection = connect_database()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS market_identifier_registry (
                condition_id TEXT PRIMARY KEY,

                gamma_market_id TEXT,
                gamma_event_id TEXT,

                market_slug TEXT,
                event_slug TEXT,

                question TEXT,
                category TEXT,

                token_id_yes TEXT,
                token_id_no TEXT,

                outcome_yes TEXT,
                outcome_no TEXT,

                market_start_at TEXT,
                market_end_at TEXT,

                active INTEGER NOT NULL DEFAULT 0,
                closed INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,

                exact_condition_match INTEGER
                    NOT NULL DEFAULT 0,

                exact_token_match INTEGER
                    NOT NULL DEFAULT 0,

                exact_market_id_match INTEGER
                    NOT NULL DEFAULT 0,

                exact_slug_match INTEGER
                    NOT NULL DEFAULT 0,

                inferred_title_match INTEGER
                    NOT NULL DEFAULT 0,

                mapping_method TEXT
                    NOT NULL DEFAULT 'UNMAPPED',

                mapping_confidence REAL
                    NOT NULL DEFAULT 0,

                verified INTEGER
                    NOT NULL DEFAULT 0,

                verification_reason TEXT,

                source_tables_json TEXT,
                alternate_identifiers_json TEXT,
                metadata_json TEXT,

                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_verified_at TEXT
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_identifier_registry_gamma_market
            ON market_identifier_registry(
                gamma_market_id
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_identifier_registry_event
            ON market_identifier_registry(
                gamma_event_id
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_identifier_registry_market_slug
            ON market_identifier_registry(
                market_slug
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_identifier_registry_event_slug
            ON market_identifier_registry(
                event_slug
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_identifier_registry_token_yes
            ON market_identifier_registry(
                token_id_yes
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_identifier_registry_token_no
            ON market_identifier_registry(
                token_id_no
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_identifier_registry_verified
            ON market_identifier_registry(
                verified,
                mapping_confidence DESC
            );

            CREATE TABLE IF NOT EXISTS market_identifier_aliases (
                alias_key TEXT PRIMARY KEY,

                condition_id TEXT NOT NULL,

                alias_type TEXT NOT NULL,
                alias_value TEXT NOT NULL,
                normalized_alias_value TEXT,

                source_table TEXT NOT NULL,
                source_column TEXT,

                confidence REAL NOT NULL DEFAULT 0,
                verified INTEGER NOT NULL DEFAULT 0,

                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,

                metadata_json TEXT,

                FOREIGN KEY(condition_id)
                    REFERENCES market_identifier_registry(condition_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_identifier_aliases_lookup
            ON market_identifier_aliases(
                alias_type,
                normalized_alias_value
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_identifier_aliases_condition
            ON market_identifier_aliases(
                condition_id
            );

            CREATE TABLE IF NOT EXISTS market_identifier_unmapped (
                unmapped_key TEXT PRIMARY KEY,

                source_table TEXT NOT NULL,
                source_row_identifier TEXT,
                source_condition_id TEXT,
                source_market_id TEXT,
                source_asset_id TEXT,
                source_slug TEXT,
                source_event_slug TEXT,
                source_title TEXT,

                best_candidate_condition_id TEXT,
                best_candidate_title TEXT,
                best_candidate_confidence REAL
                    NOT NULL DEFAULT 0,

                failure_reason TEXT NOT NULL,

                observed_at TEXT NOT NULL,
                metadata_json TEXT
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_identifier_unmapped_source
            ON market_identifier_unmapped(
                source_table,
                best_candidate_confidence DESC
            );

            CREATE TABLE IF NOT EXISTS market_identifier_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                gamma_markets_loaded INTEGER
                    NOT NULL DEFAULT 0,

                gamma_outcomes_loaded INTEGER
                    NOT NULL DEFAULT 0,

                source_rows_scanned INTEGER
                    NOT NULL DEFAULT 0,

                registry_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                aliases_saved INTEGER
                    NOT NULL DEFAULT 0,

                exact_condition_matches INTEGER
                    NOT NULL DEFAULT 0,

                exact_token_matches INTEGER
                    NOT NULL DEFAULT 0,

                exact_market_id_matches INTEGER
                    NOT NULL DEFAULT 0,

                exact_slug_matches INTEGER
                    NOT NULL DEFAULT 0,

                inferred_title_matches INTEGER
                    NOT NULL DEFAULT 0,

                unmapped_rows_saved INTEGER
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
# GAMMA LOADERS
# =============================================================================


def load_gamma_markets() -> tuple[
    dict[str, dict[str, Any]],
    dict[str, str],
    dict[str, str],
    dict[str, str],
    dict[str, list[str]],
]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "gamma_markets",
        ):
            raise RuntimeError(
                "gamma_markets is missing. "
                "Run gamma_market_registry.py first."
            )

        columns = table_columns(
            connection,
            "gamma_markets",
        )

        rows = connection.execute(
            """
            SELECT *
            FROM gamma_markets
            """
        ).fetchall()

        markets: dict[
            str,
            dict[str, Any],
        ] = {}

        market_id_to_condition: dict[
            str,
            str,
        ] = {}

        market_slug_to_condition: dict[
            str,
            str,
        ] = {}

        event_slug_to_conditions: dict[
            str,
            list[str],
        ] = defaultdict(list)

        event_id_to_conditions: dict[
            str,
            list[str],
        ] = defaultdict(list)

        for row in rows:
            condition_id = normalize_identifier(
                row_value(
                    row,
                    columns,
                    (
                        "condition_id",
                        "conditionId",
                        "conditionid",
                    ),
                )
            )

            if not condition_id:
                continue

            gamma_market_id = clean_text(
                row_value(
                    row,
                    columns,
                    (
                        "gamma_market_id",
                        "market_id",
                        "id",
                    ),
                )
            )

            gamma_event_id = clean_text(
                row_value(
                    row,
                    columns,
                    (
                        "gamma_event_id",
                        "event_id",
                    ),
                )
            )

            market_slug = clean_text(
                row_value(
                    row,
                    columns,
                    (
                        "slug",
                        "market_slug",
                    ),
                )
            )

            event_slug = clean_text(
                row_value(
                    row,
                    columns,
                    (
                        "event_slug",
                        "eventSlug",
                    ),
                )
            )

            question = clean_text(
                row_value(
                    row,
                    columns,
                    (
                        "question",
                        "title",
                    ),
                )
            )

            outcomes = parse_json_value(
                row_value(
                    row,
                    columns,
                    (
                        "outcomes",
                    ),
                )
            )

            markets[
                condition_id
            ] = {
                "condition_id": condition_id,
                "gamma_market_id": (
                    gamma_market_id
                ),
                "gamma_event_id": (
                    gamma_event_id
                ),
                "market_slug": (
                    market_slug
                ),
                "event_slug": (
                    event_slug
                ),
                "question": question,
                "category": clean_text(
                    row_value(
                        row,
                        columns,
                        (
                            "category",
                        ),
                    )
                ),
                "market_start_at": clean_text(
                    row_value(
                        row,
                        columns,
                        (
                            "start_date",
                            "startDate",
                            "start_at",
                            "start_time",
                        ),
                    )
                ),
                "market_end_at": clean_text(
                    row_value(
                        row,
                        columns,
                        (
                            "end_date",
                            "endDate",
                            "end_at",
                            "end_time",
                        ),
                    )
                ),
                "active": int(
                    bool(
                        row_value(
                            row,
                            columns,
                            (
                                "active",
                                "is_active",
                            ),
                        )
                    )
                ),
                "closed": int(
                    bool(
                        row_value(
                            row,
                            columns,
                            (
                                "closed",
                                "is_closed",
                            ),
                        )
                    )
                ),
                "archived": int(
                    bool(
                        row_value(
                            row,
                            columns,
                            (
                                "archived",
                                "is_archived",
                            ),
                        )
                    )
                ),
                "outcomes": outcomes,
            }

            if gamma_market_id:
                market_id_to_condition[
                    normalize_identifier(
                        gamma_market_id
                    )
                ] = condition_id

            if market_slug:
                market_slug_to_condition[
                    normalize_identifier(
                        market_slug
                    )
                ] = condition_id

            if event_slug:
                event_slug_to_conditions[
                    normalize_identifier(
                        event_slug
                    )
                ].append(
                    condition_id
                )

            if gamma_event_id:
                event_id_to_conditions[
                    normalize_identifier(
                        gamma_event_id
                    )
                ].append(
                    condition_id
                )

        return (
            markets,
            market_id_to_condition,
            market_slug_to_condition,
            event_id_to_conditions,
            event_slug_to_conditions,
        )

    finally:
        connection.close()


def load_gamma_outcomes() -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, str],
    int,
]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "gamma_market_outcomes",
        ):
            return {}, {}, 0

        columns = table_columns(
            connection,
            "gamma_market_outcomes",
        )

        rows = connection.execute(
            """
            SELECT *
            FROM gamma_market_outcomes
            """
        ).fetchall()

        outcomes_by_condition: dict[
            str,
            list[dict[str, Any]],
        ] = defaultdict(list)

        token_to_condition: dict[
            str,
            str,
        ] = {}

        for row in rows:
            condition_id = normalize_identifier(
                row_value(
                    row,
                    columns,
                    (
                        "condition_id",
                        "conditionId",
                    ),
                )
            )

            if not condition_id:
                continue

            token_id = clean_text(
                row_value(
                    row,
                    columns,
                    (
                        "token_id",
                        "clob_token_id",
                        "asset_id",
                        "asset",
                    ),
                )
            )

            outcome = clean_text(
                row_value(
                    row,
                    columns,
                    (
                        "outcome",
                        "outcome_name",
                    ),
                )
            )

            outcome_index = safe_int(
                row_value(
                    row,
                    columns,
                    (
                        "outcome_index",
                        "outcomeIndex",
                    ),
                ),
                -1,
            )

            outcome_row = {
                "token_id": token_id,
                "outcome": outcome,
                "outcome_index": (
                    outcome_index
                ),
            }

            outcomes_by_condition[
                condition_id
            ].append(
                outcome_row
            )

            if token_id:
                token_to_condition[
                    normalize_identifier(
                        token_id
                    )
                ] = condition_id

        return (
            outcomes_by_condition,
            token_to_condition,
            len(rows),
        )

    finally:
        connection.close()


# =============================================================================
# SOURCE SCANNING
# =============================================================================


SOURCE_TABLE_SPECS: tuple[
    dict[str, Any],
    ...,
] = (
    {
        "table": "official_wallet_trades",
        "row_id": (
            "trade_key",
            "id",
        ),
        "condition": (
            "condition_id",
            "conditionId",
        ),
        "market_id": (
            "market_id",
            "gamma_market_id",
        ),
        "asset": (
            "asset",
            "token_id",
            "clob_token_id",
        ),
        "slug": (
            "slug",
            "market_slug",
        ),
        "event_slug": (
            "event_slug",
            "eventSlug",
        ),
        "title": (
            "title",
            "question",
        ),
    },
    {
        "table": "official_wallet_activity",
        "row_id": (
            "activity_key",
            "id",
        ),
        "condition": (
            "condition_id",
            "conditionId",
        ),
        "market_id": (
            "market_id",
            "gamma_market_id",
        ),
        "asset": (
            "asset",
            "token_id",
            "clob_token_id",
        ),
        "slug": (
            "slug",
            "market_slug",
        ),
        "event_slug": (
            "event_slug",
            "eventSlug",
        ),
        "title": (
            "title",
            "question",
        ),
    },
    {
        "table": "market_predictions",
        "row_id": (
            "prediction_key",
            "id",
        ),
        "condition": (
            "condition_id",
        ),
        "market_id": (
            "market_id",
        ),
        "asset": (
            "asset",
            "token_id",
        ),
        "slug": (
            "slug",
            "market_slug",
        ),
        "event_slug": (
            "event_slug",
        ),
        "title": (
            "title",
        ),
    },
    {
        "table": "smart_money_flow_signals",
        "row_id": (
            "signal_key",
            "id",
        ),
        "condition": (
            "condition_id",
        ),
        "market_id": (
            "market_id",
        ),
        "asset": (
            "asset",
            "token_id",
        ),
        "slug": (
            "slug",
            "market_slug",
        ),
        "event_slug": (
            "event_slug",
        ),
        "title": (
            "title",
        ),
    },
    {
        "table": "market_memory_snapshots",
        "row_id": (
            "snapshot_key",
            "id",
        ),
        "condition": (
            "condition_id",
        ),
        "market_id": (
            "market_id",
        ),
        "asset": (
            "asset",
            "token_id",
        ),
        "slug": (
            "slug",
            "market_slug",
        ),
        "event_slug": (
            "event_slug",
        ),
        "title": (
            "title",
        ),
    },
)


def iter_source_rows() -> list[
    dict[str, Any]
]:
    connection = connect_database()
    output: list[
        dict[str, Any]
    ] = []

    try:
        for spec in SOURCE_TABLE_SPECS:
            table_name = spec[
                "table"
            ]

            if not table_exists(
                connection,
                table_name,
            ):
                continue

            columns = table_columns(
                connection,
                table_name,
            )

            rows = connection.execute(
                f'SELECT * FROM "{table_name}"'
            ).fetchall()

            for row in rows:
                output.append(
                    {
                        "source_table": (
                            table_name
                        ),
                        "row_id": clean_text(
                            row_value(
                                row,
                                columns,
                                spec[
                                    "row_id"
                                ],
                            )
                        ),
                        "condition_id": (
                            normalize_identifier(
                                row_value(
                                    row,
                                    columns,
                                    spec[
                                        "condition"
                                    ],
                                )
                            )
                        ),
                        "market_id": (
                            normalize_identifier(
                                row_value(
                                    row,
                                    columns,
                                    spec[
                                        "market_id"
                                    ],
                                )
                            )
                        ),
                        "asset_id": (
                            normalize_identifier(
                                row_value(
                                    row,
                                    columns,
                                    spec[
                                        "asset"
                                    ],
                                )
                            )
                        ),
                        "market_slug": (
                            normalize_identifier(
                                row_value(
                                    row,
                                    columns,
                                    spec[
                                        "slug"
                                    ],
                                )
                            )
                        ),
                        "event_slug": (
                            normalize_identifier(
                                row_value(
                                    row,
                                    columns,
                                    spec[
                                        "event_slug"
                                    ],
                                )
                            )
                        ),
                        "title": clean_text(
                            row_value(
                                row,
                                columns,
                                spec[
                                    "title"
                                ],
                            )
                        ),
                    }
                )

        deduplicated: dict[
            tuple[str, str, str, str, str, str, str],
            dict[str, Any],
        ] = {}

        for item in output:
            key = (
                item["source_table"],
                item["condition_id"],
                item["market_id"],
                item["asset_id"],
                item["market_slug"],
                item["event_slug"],
                normalize_title(
                    item["title"]
                ),
            )

            if key not in deduplicated:
                deduplicated[key] = item

        return list(
            deduplicated.values()
        )

    finally:
        connection.close()


# =============================================================================
# REGISTRY BUILD
# =============================================================================


def choose_outcome_tokens(
    outcomes: list[
        dict[str, Any]
    ],
) -> tuple[
    str,
    str,
    str,
    str,
]:
    token_yes = ""
    token_no = ""
    outcome_yes = ""
    outcome_no = ""

    for item in outcomes:
        label = clean_text(
            item.get(
                "outcome"
            )
        )

        normalized = label.lower()

        token_id = clean_text(
            item.get(
                "token_id"
            )
        )

        index = safe_int(
            item.get(
                "outcome_index"
            ),
            -1,
        )

        if (
            normalized == "yes"
            or index == 0
        ) and not token_yes:
            token_yes = token_id
            outcome_yes = label or "Yes"

        elif (
            normalized == "no"
            or index == 1
        ) and not token_no:
            token_no = token_id
            outcome_no = label or "No"

    return (
        token_yes,
        token_no,
        outcome_yes,
        outcome_no,
    )


def build_title_index(
    markets: dict[
        str,
        dict[str, Any],
    ],
) -> dict[
    str,
    list[str],
]:
    index: dict[
        str,
        list[str],
    ] = defaultdict(list)

    for condition_id, market in markets.items():
        normalized = normalize_title(
            market.get(
                "question"
            )
        )

        if normalized:
            index[
                normalized
            ].append(
                condition_id
            )

    return index


def build_title_token_index(
    markets: dict[
        str,
        dict[str, Any],
    ],
) -> dict[
    str,
    set[str],
]:
    """
    Build an inverted token index so fuzzy title matching only compares
    against plausible Gamma candidates instead of every market.
    """
    index: dict[
        str,
        set[str],
    ] = defaultdict(set)

    stop_tokens = {
        "a", "an", "and", "are", "at", "be", "by", "for", "from",
        "in", "is", "it", "of", "on", "or", "the", "to", "vs",
        "will", "with",
    }

    for condition_id, market in markets.items():
        normalized = normalize_title(
            market.get(
                "question"
            )
        )

        for token in normalized.split():
            if (
                len(token) >= 3
                and token not in stop_tokens
            ):
                index[token].add(
                    condition_id
                )

    return index


def resolve_source_row(
    source: dict[str, Any],
    markets: dict[str, dict[str, Any]],
    market_id_to_condition: dict[str, str],
    market_slug_to_condition: dict[str, str],
    event_id_to_conditions: dict[str, list[str]],
    event_slug_to_conditions: dict[str, list[str]],
    token_to_condition: dict[str, str],
    title_index: dict[str, list[str]],
    title_token_index: dict[str, set[str]],
    minimum_title_confidence: float,
) -> dict[str, Any]:
    condition_id = source[
        "condition_id"
    ]

    if (
        condition_id
        and condition_id in markets
    ):
        return {
            "condition_id": (
                condition_id
            ),
            "method": (
                "EXACT_CONDITION_ID"
            ),
            "confidence": 100.0,
            "verified": 1,
            "reason": (
                "Source condition ID exactly matches Gamma condition ID."
            ),
        }

    asset_id = source[
        "asset_id"
    ]

    if (
        asset_id
        and asset_id
        in token_to_condition
    ):
        return {
            "condition_id": (
                token_to_condition[
                    asset_id
                ]
            ),
            "method": (
                "EXACT_TOKEN_ID"
            ),
            "confidence": 100.0,
            "verified": 1,
            "reason": (
                "Source asset/token ID exactly matches Gamma outcome token."
            ),
        }

    market_id = source[
        "market_id"
    ]

    if (
        market_id
        and market_id
        in market_id_to_condition
    ):
        return {
            "condition_id": (
                market_id_to_condition[
                    market_id
                ]
            ),
            "method": (
                "EXACT_GAMMA_MARKET_ID"
            ),
            "confidence": 100.0,
            "verified": 1,
            "reason": (
                "Source market ID exactly matches Gamma market ID."
            ),
        }

    market_slug = source[
        "market_slug"
    ]

    if (
        market_slug
        and market_slug
        in market_slug_to_condition
    ):
        return {
            "condition_id": (
                market_slug_to_condition[
                    market_slug
                ]
            ),
            "method": (
                "EXACT_MARKET_SLUG"
            ),
            "confidence": 100.0,
            "verified": 1,
            "reason": (
                "Source market slug exactly matches Gamma market slug."
            ),
        }

    event_slug = source[
        "event_slug"
    ]

    if (
        event_slug
        and event_slug
        in event_slug_to_conditions
        and len(
            event_slug_to_conditions[
                event_slug
            ]
        )
        == 1
    ):
        return {
            "condition_id": (
                event_slug_to_conditions[
                    event_slug
                ][0]
            ),
            "method": (
                "UNIQUE_EVENT_SLUG"
            ),
            "confidence": 97.0,
            "verified": 1,
            "reason": (
                "Source event slug maps to one Gamma market only."
            ),
        }

    title = source[
        "title"
    ]

    normalized_title = normalize_title(
        title
    )

    exact_title_candidates = (
        title_index.get(
            normalized_title,
            [],
        )
        if normalized_title
        else []
    )

    if len(exact_title_candidates) == 1:
        return {
            "condition_id": (
                exact_title_candidates[
                    0
                ]
            ),
            "method": (
                "EXACT_NORMALIZED_TITLE"
            ),
            "confidence": 96.0,
            "verified": 1,
            "reason": (
                "Normalized source title exactly matches one Gamma question."
            ),
        }

    best_condition = ""
    best_title = ""
    best_confidence = 0.0

    if title:
        normalized_tokens = [
            token
            for token in normalize_title(
                title
            ).split()
            if len(token) >= 3
        ]

        candidate_counts: dict[
            str,
            int,
        ] = defaultdict(int)

        for token in normalized_tokens:
            for candidate_condition in title_token_index.get(
                token,
                set(),
            ):
                candidate_counts[
                    candidate_condition
                ] += 1

        # Compare only the strongest token-overlap candidates.
        candidate_conditions = [
            condition_id
            for condition_id, _ in sorted(
                candidate_counts.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:250]
        ]

        for candidate_condition in candidate_conditions:
            market = markets[
                candidate_condition
            ]

            candidate_title = clean_text(
                market.get(
                    "question"
                )
            )

            confidence = title_similarity(
                title,
                candidate_title,
            )

            if confidence > best_confidence:
                best_confidence = confidence
                best_condition = candidate_condition
                best_title = candidate_title

    if (
        best_condition
        and best_confidence
        >= minimum_title_confidence
    ):
        return {
            "condition_id": (
                best_condition
            ),
            "method": (
                "INFERRED_TITLE_MATCH"
            ),
            "confidence": (
                best_confidence
            ),
            "verified": 0,
            "reason": (
                "High-similarity title match. "
                "Requires downstream verification before actionable use."
            ),
            "best_candidate_title": (
                best_title
            ),
        }

    return {
        "condition_id": "",
        "method": "UNMAPPED",
        "confidence": (
            best_confidence
        ),
        "verified": 0,
        "reason": (
            "No exact official identifier match and no title "
            "candidate met the minimum confidence threshold."
        ),
        "best_candidate_condition_id": (
            best_condition
        ),
        "best_candidate_title": (
            best_title
        ),
    }


def build_registry(
    minimum_title_confidence: float,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, int],
]:
    (
        markets,
        market_id_to_condition,
        market_slug_to_condition,
        event_id_to_conditions,
        event_slug_to_conditions,
    ) = load_gamma_markets()

    (
        outcomes_by_condition,
        token_to_condition,
        gamma_outcome_count,
    ) = load_gamma_outcomes()

    source_rows = iter_source_rows()

    title_index = build_title_index(
        markets
    )

    title_token_index = build_title_token_index(
        markets
    )

    now_iso = utc_now_iso()

    registry_rows: dict[
        str,
        dict[str, Any],
    ] = {}

    alias_rows: dict[
        str,
        dict[str, Any],
    ] = {}

    unmapped_rows: dict[
        str,
        dict[str, Any],
    ] = {}

    stats = {
        "gamma_markets_loaded": (
            len(markets)
        ),
        "gamma_outcomes_loaded": (
            gamma_outcome_count
        ),
        "source_rows_scanned": (
            len(source_rows)
        ),
        "exact_condition_matches": 0,
        "exact_token_matches": 0,
        "exact_market_id_matches": 0,
        "exact_slug_matches": 0,
        "inferred_title_matches": 0,
    }

    # First create canonical rows for every Gamma market.
    for condition_id, market in markets.items():
        (
            token_yes,
            token_no,
            outcome_yes,
            outcome_no,
        ) = choose_outcome_tokens(
            outcomes_by_condition.get(
                condition_id,
                [],
            )
        )

        registry_rows[
            condition_id
        ] = {
            "condition_id": (
                condition_id
            ),
            "gamma_market_id": (
                clean_text(
                    market.get(
                        "gamma_market_id"
                    )
                )
            ),
            "gamma_event_id": (
                clean_text(
                    market.get(
                        "gamma_event_id"
                    )
                )
            ),
            "market_slug": (
                clean_text(
                    market.get(
                        "market_slug"
                    )
                )
            ),
            "event_slug": (
                clean_text(
                    market.get(
                        "event_slug"
                    )
                )
            ),
            "question": clean_text(
                market.get(
                    "question"
                )
            ),
            "category": clean_text(
                market.get(
                    "category"
                )
            ),
            "token_id_yes": (
                token_yes
            ),
            "token_id_no": (
                token_no
            ),
            "outcome_yes": (
                outcome_yes
            ),
            "outcome_no": (
                outcome_no
            ),
            "market_start_at": (
                clean_text(
                    market.get(
                        "market_start_at"
                    )
                )
            ),
            "market_end_at": (
                clean_text(
                    market.get(
                        "market_end_at"
                    )
                )
            ),
            "active": safe_int(
                market.get(
                    "active"
                )
            ),
            "closed": safe_int(
                market.get(
                    "closed"
                )
            ),
            "archived": safe_int(
                market.get(
                    "archived"
                )
            ),
            "exact_condition_match": 1,
            "exact_token_match": 0,
            "exact_market_id_match": 0,
            "exact_slug_match": 0,
            "inferred_title_match": 0,
            "mapping_method": (
                "GAMMA_CANONICAL"
            ),
            "mapping_confidence": 100.0,
            "verified": 1,
            "verification_reason": (
                "Canonical row created directly from Gamma market registry."
            ),
            "source_tables": {
                "gamma_markets",
            },
            "alternate_identifiers": {
                "market_ids": set(),
                "market_slugs": set(),
                "event_slugs": set(),
                "asset_ids": set(),
                "source_condition_ids": set(),
            },
            "metadata": {
                "source_match_counts": (
                    defaultdict(int)
                ),
            },
            "first_seen_at": (
                now_iso
            ),
            "last_seen_at": (
                now_iso
            ),
            "last_verified_at": (
                now_iso
            ),
        }

    total_source_rows = len(
        source_rows
    )

    for source_index, source in enumerate(
        source_rows,
        start=1,
    ):
        if (
            source_index == 1
            or source_index % 5000 == 0
            or source_index == total_source_rows
        ):
            print(
                f"Resolving source identifiers: "
                f"{source_index:,}/{total_source_rows:,}"
            )

        result = resolve_source_row(
            source=source,
            markets=markets,
            market_id_to_condition=(
                market_id_to_condition
            ),
            market_slug_to_condition=(
                market_slug_to_condition
            ),
            event_id_to_conditions=(
                event_id_to_conditions
            ),
            event_slug_to_conditions=(
                event_slug_to_conditions
            ),
            token_to_condition=(
                token_to_condition
            ),
            title_index=title_index,
            title_token_index=(
                title_token_index
            ),
            minimum_title_confidence=(
                minimum_title_confidence
            ),
        )

        condition_id = result[
            "condition_id"
        ]

        method = result[
            "method"
        ]

        if condition_id:
            registry = registry_rows[
                condition_id
            ]

            registry[
                "source_tables"
            ].add(
                source[
                    "source_table"
                ]
            )

            registry[
                "metadata"
            ][
                "source_match_counts"
            ][method] += 1

            if source[
                "condition_id"
            ]:
                registry[
                    "alternate_identifiers"
                ][
                    "source_condition_ids"
                ].add(
                    source[
                        "condition_id"
                    ]
                )

            if source[
                "market_id"
            ]:
                registry[
                    "alternate_identifiers"
                ][
                    "market_ids"
                ].add(
                    source[
                        "market_id"
                    ]
                )

            if source[
                "market_slug"
            ]:
                registry[
                    "alternate_identifiers"
                ][
                    "market_slugs"
                ].add(
                    source[
                        "market_slug"
                    ]
                )

            if source[
                "event_slug"
            ]:
                registry[
                    "alternate_identifiers"
                ][
                    "event_slugs"
                ].add(
                    source[
                        "event_slug"
                    ]
                )

            if source[
                "asset_id"
            ]:
                registry[
                    "alternate_identifiers"
                ][
                    "asset_ids"
                ].add(
                    source[
                        "asset_id"
                    ]
                )

            if method == "EXACT_CONDITION_ID":
                registry[
                    "exact_condition_match"
                ] = 1

                stats[
                    "exact_condition_matches"
                ] += 1

            elif method == "EXACT_TOKEN_ID":
                registry[
                    "exact_token_match"
                ] = 1

                stats[
                    "exact_token_matches"
                ] += 1

            elif method == "EXACT_GAMMA_MARKET_ID":
                registry[
                    "exact_market_id_match"
                ] = 1

                stats[
                    "exact_market_id_matches"
                ] += 1

            elif method in {
                "EXACT_MARKET_SLUG",
                "UNIQUE_EVENT_SLUG",
            }:
                registry[
                    "exact_slug_match"
                ] = 1

                stats[
                    "exact_slug_matches"
                ] += 1

            elif method in {
                "EXACT_NORMALIZED_TITLE",
                "INFERRED_TITLE_MATCH",
            }:
                registry[
                    "inferred_title_match"
                ] = 1

                stats[
                    "inferred_title_matches"
                ] += 1

            if (
                result[
                    "confidence"
                ]
                > registry[
                    "mapping_confidence"
                ]
            ):
                registry[
                    "mapping_confidence"
                ] = result[
                    "confidence"
                ]

                registry[
                    "mapping_method"
                ] = method

                registry[
                    "verified"
                ] = result[
                    "verified"
                ]

                registry[
                    "verification_reason"
                ] = result[
                    "reason"
                ]

            alias_candidates = (
                (
                    "CONDITION_ID",
                    source[
                        "condition_id"
                    ],
                    "condition_id",
                ),
                (
                    "MARKET_ID",
                    source[
                        "market_id"
                    ],
                    "market_id",
                ),
                (
                    "TOKEN_ID",
                    source[
                        "asset_id"
                    ],
                    "asset",
                ),
                (
                    "MARKET_SLUG",
                    source[
                        "market_slug"
                    ],
                    "slug",
                ),
                (
                    "EVENT_SLUG",
                    source[
                        "event_slug"
                    ],
                    "event_slug",
                ),
                (
                    "TITLE",
                    source[
                        "title"
                    ],
                    "title",
                ),
            )

            for (
                alias_type,
                alias_value,
                source_column,
            ) in alias_candidates:
                if not alias_value:
                    continue

                normalized_alias = (
                    normalize_title(
                        alias_value
                    )
                    if alias_type
                    == "TITLE"
                    else normalize_identifier(
                        alias_value
                    )
                )

                alias_key = (
                    f"{condition_id}:"
                    f"{alias_type}:"
                    f"{normalized_alias}:"
                    f"{source['source_table']}"
                )

                alias_rows[
                    alias_key
                ] = {
                    "alias_key": (
                        alias_key
                    ),
                    "condition_id": (
                        condition_id
                    ),
                    "alias_type": (
                        alias_type
                    ),
                    "alias_value": clean_text(
                        alias_value
                    ),
                    "normalized_alias_value": (
                        normalized_alias
                    ),
                    "source_table": (
                        source[
                            "source_table"
                        ]
                    ),
                    "source_column": (
                        source_column
                    ),
                    "confidence": (
                        result[
                            "confidence"
                        ]
                    ),
                    "verified": (
                        result[
                            "verified"
                        ]
                    ),
                    "first_seen_at": (
                        now_iso
                    ),
                    "last_seen_at": (
                        now_iso
                    ),
                    "metadata_json": (
                        stable_json(
                            {
                                "mapping_method": (
                                    method
                                ),
                                "source_row_identifier": (
                                    source[
                                        "row_id"
                                    ]
                                ),
                            }
                        )
                    ),
                }

        else:
            unmapped_key = (
                f"{source['source_table']}:"
                f"{source['row_id']}:"
                f"{source['condition_id']}:"
                f"{source['asset_id']}"
            )

            unmapped_rows[
                unmapped_key
            ] = {
                "unmapped_key": (
                    unmapped_key
                ),
                "source_table": (
                    source[
                        "source_table"
                    ]
                ),
                "source_row_identifier": (
                    source[
                        "row_id"
                    ]
                ),
                "source_condition_id": (
                    source[
                        "condition_id"
                    ]
                ),
                "source_market_id": (
                    source[
                        "market_id"
                    ]
                ),
                "source_asset_id": (
                    source[
                        "asset_id"
                    ]
                ),
                "source_slug": (
                    source[
                        "market_slug"
                    ]
                ),
                "source_event_slug": (
                    source[
                        "event_slug"
                    ]
                ),
                "source_title": (
                    source[
                        "title"
                    ]
                ),
                "best_candidate_condition_id": (
                    result.get(
                        "best_candidate_condition_id",
                        "",
                    )
                ),
                "best_candidate_title": (
                    result.get(
                        "best_candidate_title",
                        "",
                    )
                ),
                "best_candidate_confidence": (
                    result[
                        "confidence"
                    ]
                ),
                "failure_reason": (
                    result[
                        "reason"
                    ]
                ),
                "observed_at": (
                    now_iso
                ),
                "metadata_json": (
                    stable_json(
                        {
                            "mapping_method": (
                                result[
                                    "method"
                                ]
                            ),
                        }
                    )
                ),
            }

    finalized_registry: list[
        dict[str, Any]
    ] = []

    for row in registry_rows.values():
        row[
            "source_tables_json"
        ] = stable_json(
            sorted(
                row.pop(
                    "source_tables"
                )
            )
        )

        alternate = row.pop(
            "alternate_identifiers"
        )

        row[
            "alternate_identifiers_json"
        ] = stable_json(
            {
                key: sorted(value)
                for key, value
                in alternate.items()
            }
        )

        metadata = row.pop(
            "metadata"
        )

        metadata[
            "source_match_counts"
        ] = dict(
            metadata[
                "source_match_counts"
            ]
        )

        row[
            "metadata_json"
        ] = stable_json(
            metadata
        )

        finalized_registry.append(
            row
        )

    finalized_registry.sort(
        key=lambda row: (
            row[
                "verified"
            ],
            row[
                "mapping_confidence"
            ],
            row[
                "active"
            ],
            row[
                "question"
            ],
        ),
        reverse=True,
    )

    return (
        finalized_registry,
        list(
            alias_rows.values()
        ),
        list(
            unmapped_rows.values()
        ),
        stats,
    )


# =============================================================================
# SAVE
# =============================================================================


REGISTRY_COLUMNS = [
    "condition_id",
    "gamma_market_id",
    "gamma_event_id",
    "market_slug",
    "event_slug",
    "question",
    "category",
    "token_id_yes",
    "token_id_no",
    "outcome_yes",
    "outcome_no",
    "market_start_at",
    "market_end_at",
    "active",
    "closed",
    "archived",
    "exact_condition_match",
    "exact_token_match",
    "exact_market_id_match",
    "exact_slug_match",
    "inferred_title_match",
    "mapping_method",
    "mapping_confidence",
    "verified",
    "verification_reason",
    "source_tables_json",
    "alternate_identifiers_json",
    "metadata_json",
    "first_seen_at",
    "last_seen_at",
    "last_verified_at",
]


ALIAS_COLUMNS = [
    "alias_key",
    "condition_id",
    "alias_type",
    "alias_value",
    "normalized_alias_value",
    "source_table",
    "source_column",
    "confidence",
    "verified",
    "first_seen_at",
    "last_seen_at",
    "metadata_json",
]


UNMAPPED_COLUMNS = [
    "unmapped_key",
    "source_table",
    "source_row_identifier",
    "source_condition_id",
    "source_market_id",
    "source_asset_id",
    "source_slug",
    "source_event_slug",
    "source_title",
    "best_candidate_condition_id",
    "best_candidate_title",
    "best_candidate_confidence",
    "failure_reason",
    "observed_at",
    "metadata_json",
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
        f'INSERT INTO "{table_name}" '
        f'({names}) VALUES ({placeholders})'
    )


def save_registry(
    registry_rows: list[
        dict[str, Any]
    ],
    alias_rows: list[
        dict[str, Any]
    ],
    unmapped_rows: list[
        dict[str, Any]
    ],
) -> tuple[
    int,
    int,
    int,
]:
    connection = connect_database()

    registry_query = build_insert_query(
        "market_identifier_registry",
        REGISTRY_COLUMNS,
    )

    alias_query = build_insert_query(
        "market_identifier_aliases",
        ALIAS_COLUMNS,
    )

    unmapped_query = build_insert_query(
        "market_identifier_unmapped",
        UNMAPPED_COLUMNS,
    )

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        connection.execute(
            "DELETE FROM market_identifier_aliases"
        )

        connection.execute(
            "DELETE FROM market_identifier_unmapped"
        )

        connection.execute(
            "DELETE FROM market_identifier_registry"
        )

        for row in registry_rows:
            connection.execute(
                registry_query,
                tuple(
                    row[column]
                    for column
                    in REGISTRY_COLUMNS
                ),
            )

        for row in alias_rows:
            connection.execute(
                alias_query,
                tuple(
                    row[column]
                    for column
                    in ALIAS_COLUMNS
                ),
            )

        for row in unmapped_rows:
            connection.execute(
                unmapped_query,
                tuple(
                    row[column]
                    for column
                    in UNMAPPED_COLUMNS
                ),
            )

        connection.commit()

        return (
            len(registry_rows),
            len(alias_rows),
            len(unmapped_rows),
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =============================================================================
# RUN LOGGING
# =============================================================================


def start_run() -> tuple[
    int,
    datetime,
]:
    started_at = utc_now()
    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO market_identifier_runs (
                started_at,
                status
            )
            VALUES (?, 'RUNNING')
            """,
            (
                started_at.isoformat(),
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
    stats: dict[str, int],
    registry_rows_saved: int,
    aliases_saved: int,
    unmapped_rows_saved: int,
    error_message: str = "",
) -> None:
    finished_at = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE market_identifier_runs
            SET
                finished_at=?,
                elapsed_seconds=?,
                gamma_markets_loaded=?,
                gamma_outcomes_loaded=?,
                source_rows_scanned=?,
                registry_rows_saved=?,
                aliases_saved=?,
                exact_condition_matches=?,
                exact_token_matches=?,
                exact_market_id_matches=?,
                exact_slug_matches=?,
                inferred_title_matches=?,
                unmapped_rows_saved=?,
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
                stats.get(
                    "gamma_markets_loaded",
                    0,
                ),
                stats.get(
                    "gamma_outcomes_loaded",
                    0,
                ),
                stats.get(
                    "source_rows_scanned",
                    0,
                ),
                registry_rows_saved,
                aliases_saved,
                stats.get(
                    "exact_condition_matches",
                    0,
                ),
                stats.get(
                    "exact_token_matches",
                    0,
                ),
                stats.get(
                    "exact_market_id_matches",
                    0,
                ),
                stats.get(
                    "exact_slug_matches",
                    0,
                ),
                stats.get(
                    "inferred_title_matches",
                    0,
                ),
                unmapped_rows_saved,
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
    registry_rows: list[
        dict[str, Any]
    ],
    alias_rows: list[
        dict[str, Any]
    ],
    unmapped_rows: list[
        dict[str, Any]
    ],
    stats: dict[str, int],
    display_limit: int,
) -> None:
    verified_count = sum(
        1
        for row in registry_rows
        if row[
            "verified"
        ]
    )

    print()
    print("=" * 118)
    print("MARKET IDENTIFIER REGISTRY SUMMARY")
    print("=" * 118)

    print(
        f"Gamma markets loaded:           "
        f"{stats['gamma_markets_loaded']}"
    )

    print(
        f"Gamma outcomes loaded:          "
        f"{stats['gamma_outcomes_loaded']}"
    )

    print(
        f"Source rows scanned:            "
        f"{stats['source_rows_scanned']}"
    )

    print(
        f"Registry markets saved:         "
        f"{len(registry_rows)}"
    )

    print(
        f"Verified registry markets:      "
        f"{verified_count}"
    )

    print(
        f"Identifier aliases saved:       "
        f"{len(alias_rows)}"
    )

    print(
        f"Unmapped source rows:           "
        f"{len(unmapped_rows)}"
    )

    print()
    print(
        f"Exact condition matches:        "
        f"{stats['exact_condition_matches']}"
    )

    print(
        f"Exact token matches:            "
        f"{stats['exact_token_matches']}"
    )

    print(
        f"Exact market-ID matches:        "
        f"{stats['exact_market_id_matches']}"
    )

    print(
        f"Exact slug matches:             "
        f"{stats['exact_slug_matches']}"
    )

    print(
        f"Title-based matches:            "
        f"{stats['inferred_title_matches']}"
    )

    print("=" * 118)

    print()
    print("TOP UNMAPPED SOURCE RECORDS")

    for index, row in enumerate(
        sorted(
            unmapped_rows,
            key=lambda item: (
                item[
                    "best_candidate_confidence"
                ],
                item[
                    "source_title"
                ],
            ),
            reverse=True,
        )[:display_limit],
        start=1,
    ):
        print()
        print("-" * 118)

        print(
            f"{index}. "
            f"{row['source_title'] or row['source_condition_id'] or row['source_asset_id']}"
        )

        print("-" * 118)

        print(
            f"Source:                         "
            f"{row['source_table']}"
        )

        print(
            f"Source condition ID:            "
            f"{row['source_condition_id'] or '-'}"
        )

        print(
            f"Source asset/token ID:          "
            f"{row['source_asset_id'] or '-'}"
        )

        print(
            f"Best candidate confidence:      "
            f"{row['best_candidate_confidence']:.1f}"
        )

        print(
            f"Best candidate title:           "
            f"{row['best_candidate_title'] or '-'}"
        )

        print(
            f"Failure reason:                 "
            f"{row['failure_reason']}"
        )


# =============================================================================
# MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a canonical Polymarket market identity registry "
            "from Gamma markets, outcome tokens, official wallet data "
            "and downstream market analytics."
        )
    )

    parser.add_argument(
        "--minimum-title-confidence",
        type=float,
        default=DEFAULT_MIN_TITLE_CONFIDENCE,
        help=(
            "Minimum token-overlap score required for an inferred "
            "title match. Inferred matches remain unverified."
        ),
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

    minimum_title_confidence = max(
        0.0,
        min(
            arguments.minimum_title_confidence,
            100.0,
        ),
    )

    print()
    print("=" * 118)
    print("POLYMARKET MARKET IDENTIFIER REGISTRY ENGINE v1.1")
    print("=" * 118)

    print(
        f"Database:                    {DB}"
    )

    print(
        f"Minimum title confidence:    "
        f"{minimum_title_confidence:.1f}"
    )

    print(
        "Mapping priority:           "
        "CONDITION ID -> TOKEN ID -> MARKET ID -> SLUG -> TITLE"
    )

    print(
        "Actionable rule:            "
        "TITLE-ONLY MATCHES REMAIN UNVERIFIED"
    )

    print("=" * 118)

    create_tables()

    run_id, started_at = start_run()

    registry_rows: list[
        dict[str, Any]
    ] = []

    alias_rows: list[
        dict[str, Any]
    ] = []

    unmapped_rows: list[
        dict[str, Any]
    ] = []

    stats: dict[str, int] = {
        "gamma_markets_loaded": 0,
        "gamma_outcomes_loaded": 0,
        "source_rows_scanned": 0,
        "exact_condition_matches": 0,
        "exact_token_matches": 0,
        "exact_market_id_matches": 0,
        "exact_slug_matches": 0,
        "inferred_title_matches": 0,
    }

    registry_rows_saved = 0
    aliases_saved = 0
    unmapped_rows_saved = 0

    try:
        (
            registry_rows,
            alias_rows,
            unmapped_rows,
            stats,
        ) = build_registry(
            minimum_title_confidence=(
                minimum_title_confidence
            )
        )

        (
            registry_rows_saved,
            aliases_saved,
            unmapped_rows_saved,
        ) = save_registry(
            registry_rows=registry_rows,
            alias_rows=alias_rows,
            unmapped_rows=unmapped_rows,
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            stats=stats,
            registry_rows_saved=(
                registry_rows_saved
            ),
            aliases_saved=aliases_saved,
            unmapped_rows_saved=(
                unmapped_rows_saved
            ),
        )

        display_summary(
            registry_rows=registry_rows,
            alias_rows=alias_rows,
            unmapped_rows=unmapped_rows,
            stats=stats,
            display_limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 118)
        print("MARKET IDENTIFIER REGISTRY COMPLETE")
        print("=" * 118)

        print(
            "Canonical registry:          "
            "market_identifier_registry"
        )

        print(
            "Identifier aliases:          "
            "market_identifier_aliases"
        )

        print(
            "Unmapped records:            "
            "market_identifier_unmapped"
        )

        print(
            "Run history:                 "
            "market_identifier_runs"
        )

        print()
        print(
            "Next step: update Opportunity Ranking to resolve "
            "markets through this registry rather than joining only "
            "against gamma_markets.condition_id."
        )

        print("=" * 118)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            stats=stats,
            registry_rows_saved=(
                registry_rows_saved
            ),
            aliases_saved=aliases_saved,
            unmapped_rows_saved=(
                unmapped_rows_saved
            ),
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()