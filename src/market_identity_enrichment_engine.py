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
DEFAULT_SOURCE_LIMIT = 0


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
        raw = raw.replace(source, target)

    normalized = "".join(
        character if character.isalnum() else " "
        for character in raw
    )

    return " ".join(normalized.split())


def safe_int(value: Any, default: int = 0) -> int:
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


def row_value(
    row: sqlite3.Row,
    columns: set[str],
    candidates: tuple[str, ...],
) -> Any:
    column = first_existing(columns, candidates)

    if column is None:
        return None

    return row[column]


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
            "market_identifier_registry",
        )

        require_table(
            connection,
            "market_identifier_aliases",
        )

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS market_identity_enrichments (
                enrichment_key TEXT PRIMARY KEY,

                source_table TEXT NOT NULL,
                source_row_identifier TEXT NOT NULL,

                source_condition_id TEXT,
                source_market_id TEXT,
                source_asset_id TEXT,
                source_market_slug TEXT,
                source_event_slug TEXT,
                source_title TEXT,

                canonical_condition_id TEXT,
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

                mapping_method TEXT
                    NOT NULL DEFAULT 'UNMAPPED',

                mapping_confidence REAL
                    NOT NULL DEFAULT 0,

                verified INTEGER
                    NOT NULL DEFAULT 0,

                actionable_identity INTEGER
                    NOT NULL DEFAULT 0,

                enrichment_status TEXT
                    NOT NULL DEFAULT 'UNRESOLVED',

                resolution_reason TEXT,

                source_identity_json TEXT,
                canonical_identity_json TEXT,
                metadata_json TEXT,

                enriched_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_identity_enrichments_source
            ON market_identity_enrichments(
                source_table,
                source_row_identifier
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_identity_enrichments_condition
            ON market_identity_enrichments(
                canonical_condition_id,
                verified
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_identity_enrichments_status
            ON market_identity_enrichments(
                enrichment_status,
                mapping_confidence DESC
            );

            CREATE TABLE IF NOT EXISTS market_identity_source_summary (
                source_table TEXT PRIMARY KEY,

                source_rows_scanned INTEGER
                    NOT NULL DEFAULT 0,

                enriched_rows INTEGER
                    NOT NULL DEFAULT 0,

                verified_rows INTEGER
                    NOT NULL DEFAULT 0,

                actionable_identity_rows INTEGER
                    NOT NULL DEFAULT 0,

                unresolved_rows INTEGER
                    NOT NULL DEFAULT 0,

                exact_condition_matches INTEGER
                    NOT NULL DEFAULT 0,

                exact_token_matches INTEGER
                    NOT NULL DEFAULT 0,

                exact_market_id_matches INTEGER
                    NOT NULL DEFAULT 0,

                exact_slug_matches INTEGER
                    NOT NULL DEFAULT 0,

                title_matches INTEGER
                    NOT NULL DEFAULT 0,

                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS market_identity_enrichment_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                source_rows_scanned INTEGER
                    NOT NULL DEFAULT 0,

                enriched_rows INTEGER
                    NOT NULL DEFAULT 0,

                verified_rows INTEGER
                    NOT NULL DEFAULT 0,

                actionable_identity_rows INTEGER
                    NOT NULL DEFAULT 0,

                unresolved_rows INTEGER
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
# SOURCE TABLE DEFINITIONS
# =============================================================================


SOURCE_TABLE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "table": "market_predictions",
        "row_id": ("prediction_key", "id"),
        "condition": ("condition_id",),
        "market_id": ("market_id",),
        "asset": ("asset", "token_id"),
        "slug": ("slug", "market_slug"),
        "event_slug": ("event_slug",),
        "title": ("title",),
    },
    {
        "table": "smart_money_flow_signals",
        "row_id": ("signal_key", "id"),
        "condition": ("condition_id",),
        "market_id": ("market_id",),
        "asset": ("asset", "token_id"),
        "slug": ("slug", "market_slug"),
        "event_slug": ("event_slug",),
        "title": ("title",),
    },
    {
        "table": "market_memory_snapshots",
        "row_id": ("snapshot_key", "id"),
        "condition": ("condition_id",),
        "market_id": ("market_id",),
        "asset": ("asset", "token_id"),
        "slug": ("slug", "market_slug"),
        "event_slug": ("event_slug",),
        "title": ("title",),
    },
    {
        "table": "official_wallet_trades",
        "row_id": ("trade_key", "id"),
        "condition": ("condition_id", "conditionId"),
        "market_id": ("market_id", "gamma_market_id"),
        "asset": ("asset", "token_id", "clob_token_id"),
        "slug": ("slug", "market_slug"),
        "event_slug": ("event_slug", "eventSlug"),
        "title": ("title", "question"),
    },
    {
        "table": "official_wallet_activity",
        "row_id": ("activity_key", "id"),
        "condition": ("condition_id", "conditionId"),
        "market_id": ("market_id", "gamma_market_id"),
        "asset": ("asset", "token_id", "clob_token_id"),
        "slug": ("slug", "market_slug"),
        "event_slug": ("event_slug", "eventSlug"),
        "title": ("title", "question"),
    },
)


# =============================================================================
# REGISTRY / ALIAS INDEXES
# =============================================================================


def load_registry() -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM market_identifier_registry
            """
        ).fetchall()

        return {
            normalize_identifier(row["condition_id"]): dict(row)
            for row in rows
            if normalize_identifier(row["condition_id"])
        }

    finally:
        connection.close()


def load_alias_indexes() -> dict[str, dict[str, list[dict[str, Any]]]]:
    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM market_identifier_aliases
            """
        ).fetchall()

        indexes: dict[
            str,
            dict[str, list[dict[str, Any]]],
        ] = defaultdict(
            lambda: defaultdict(list)
        )

        for row in rows:
            alias_type = clean_text(
                row["alias_type"]
            ).upper()

            normalized_value = normalize_identifier(
                row["normalized_alias_value"]
            )

            if alias_type == "TITLE":
                normalized_value = normalize_title(
                    row["alias_value"]
                )

            if not alias_type or not normalized_value:
                continue

            indexes[
                alias_type
            ][
                normalized_value
            ].append(
                dict(row)
            )

        return indexes

    finally:
        connection.close()


def build_direct_registry_indexes(
    registry: dict[str, dict[str, Any]],
) -> dict[str, dict[str, str]]:
    indexes: dict[str, dict[str, str]] = {
        "CONDITION_ID": {},
        "MARKET_ID": {},
        "MARKET_SLUG": {},
        "EVENT_SLUG": {},
        "TOKEN_ID": {},
        "TITLE": {},
    }

    title_candidates: dict[
        str,
        list[str],
    ] = defaultdict(list)

    for condition_id, row in registry.items():
        indexes[
            "CONDITION_ID"
        ][condition_id] = condition_id

        gamma_market_id = normalize_identifier(
            row.get("gamma_market_id")
        )

        if gamma_market_id:
            indexes[
                "MARKET_ID"
            ][gamma_market_id] = condition_id

        market_slug = normalize_identifier(
            row.get("market_slug")
        )

        if market_slug:
            indexes[
                "MARKET_SLUG"
            ][market_slug] = condition_id

        event_slug = normalize_identifier(
            row.get("event_slug")
        )

        if event_slug:
            existing = indexes[
                "EVENT_SLUG"
            ].get(event_slug)

            if existing is None:
                indexes[
                    "EVENT_SLUG"
                ][event_slug] = condition_id
            elif existing != condition_id:
                indexes[
                    "EVENT_SLUG"
                ][event_slug] = ""

        for token_column in (
            "token_id_yes",
            "token_id_no",
        ):
            token_id = normalize_identifier(
                row.get(token_column)
            )

            if token_id:
                indexes[
                    "TOKEN_ID"
                ][token_id] = condition_id

        normalized_question = normalize_title(
            row.get("question")
        )

        if normalized_question:
            title_candidates[
                normalized_question
            ].append(
                condition_id
            )

    for title, condition_ids in title_candidates.items():
        if len(condition_ids) == 1:
            indexes[
                "TITLE"
            ][title] = condition_ids[0]

    return indexes


# =============================================================================
# SOURCE LOADING
# =============================================================================


def load_source_rows(
    selected_sources: set[str],
    source_limit: int,
) -> list[dict[str, Any]]:
    connection = connect_database()
    output: list[dict[str, Any]] = []

    try:
        for spec in SOURCE_TABLE_SPECS:
            table_name = spec["table"]

            if (
                selected_sources
                and table_name not in selected_sources
            ):
                continue

            if not table_exists(
                connection,
                table_name,
            ):
                continue

            columns = table_columns(
                connection,
                table_name,
            )

            row_id_column = first_existing(
                columns,
                spec["row_id"],
            )

            if row_id_column is None:
                continue

            sql = (
                f'SELECT * FROM "{table_name}"'
            )

            if source_limit > 0:
                sql += f" LIMIT {source_limit}"

            rows = connection.execute(
                sql
            ).fetchall()

            for row in rows:
                row_id = clean_text(
                    row[row_id_column]
                )

                if not row_id:
                    continue

                output.append(
                    {
                        "source_table": table_name,
                        "row_id": row_id,
                        "condition_id": normalize_identifier(
                            row_value(
                                row,
                                columns,
                                spec["condition"],
                            )
                        ),
                        "market_id": normalize_identifier(
                            row_value(
                                row,
                                columns,
                                spec["market_id"],
                            )
                        ),
                        "asset_id": normalize_identifier(
                            row_value(
                                row,
                                columns,
                                spec["asset"],
                            )
                        ),
                        "market_slug": normalize_identifier(
                            row_value(
                                row,
                                columns,
                                spec["slug"],
                            )
                        ),
                        "event_slug": normalize_identifier(
                            row_value(
                                row,
                                columns,
                                spec["event_slug"],
                            )
                        ),
                        "title": clean_text(
                            row_value(
                                row,
                                columns,
                                spec["title"],
                            )
                        ),
                    }
                )

        return output

    finally:
        connection.close()


# =============================================================================
# RESOLUTION
# =============================================================================


def unique_alias_match(
    alias_indexes: dict[
        str,
        dict[str, list[dict[str, Any]]],
    ],
    alias_type: str,
    value: str,
) -> dict[str, Any] | None:
    candidates = alias_indexes.get(
        alias_type,
        {},
    ).get(
        value,
        [],
    )

    condition_ids = {
        normalize_identifier(
            candidate.get(
                "condition_id"
            )
        )
        for candidate in candidates
        if normalize_identifier(
            candidate.get(
                "condition_id"
            )
        )
    }

    if len(condition_ids) != 1:
        return None

    best = max(
        candidates,
        key=lambda row: (
            safe_int(row.get("verified")),
            float(row.get("confidence") or 0),
        ),
    )

    return {
        "condition_id": next(
            iter(condition_ids)
        ),
        "confidence": float(
            best.get("confidence")
            or 0
        ),
        "verified": safe_int(
            best.get("verified")
        ),
    }


def resolve_identity(
    source: dict[str, Any],
    registry: dict[str, dict[str, Any]],
    direct_indexes: dict[str, dict[str, str]],
    alias_indexes: dict[
        str,
        dict[str, list[dict[str, Any]]],
    ],
) -> dict[str, Any]:
    resolution_order = (
        (
            "CONDITION_ID",
            source["condition_id"],
            "EXACT_CONDITION_ID",
            100.0,
            1,
        ),
        (
            "TOKEN_ID",
            source["asset_id"],
            "EXACT_TOKEN_ID",
            100.0,
            1,
        ),
        (
            "MARKET_ID",
            source["market_id"],
            "EXACT_GAMMA_MARKET_ID",
            100.0,
            1,
        ),
        (
            "MARKET_SLUG",
            source["market_slug"],
            "EXACT_MARKET_SLUG",
            100.0,
            1,
        ),
        (
            "EVENT_SLUG",
            source["event_slug"],
            "UNIQUE_EVENT_SLUG",
            97.0,
            1,
        ),
    )

    for (
        alias_type,
        value,
        method,
        confidence,
        verified,
    ) in resolution_order:
        if not value:
            continue

        direct_condition = direct_indexes.get(
            alias_type,
            {},
        ).get(value)

        if direct_condition:
            return {
                "condition_id": direct_condition,
                "method": method,
                "confidence": confidence,
                "verified": verified,
                "reason": (
                    f"Resolved through canonical {alias_type} index."
                ),
            }

        alias_match = unique_alias_match(
            alias_indexes,
            alias_type,
            value,
        )

        if alias_match:
            return {
                "condition_id": alias_match[
                    "condition_id"
                ],
                "method": (
                    f"REGISTRY_ALIAS_{alias_type}"
                ),
                "confidence": alias_match[
                    "confidence"
                ],
                "verified": alias_match[
                    "verified"
                ],
                "reason": (
                    f"Resolved through unique registry alias: {alias_type}."
                ),
            }

    normalized_title = normalize_title(
        source["title"]
    )

    if normalized_title:
        direct_condition = direct_indexes[
            "TITLE"
        ].get(normalized_title)

        if direct_condition:
            return {
                "condition_id": direct_condition,
                "method": (
                    "EXACT_NORMALIZED_TITLE"
                ),
                "confidence": 96.0,
                "verified": 0,
                "reason": (
                    "Title exactly matches one canonical market, "
                    "but title-only identity remains unverified."
                ),
            }

        alias_match = unique_alias_match(
            alias_indexes,
            "TITLE",
            normalized_title,
        )

        if alias_match:
            return {
                "condition_id": alias_match[
                    "condition_id"
                ],
                "method": (
                    "REGISTRY_ALIAS_TITLE"
                ),
                "confidence": min(
                    alias_match[
                        "confidence"
                    ],
                    96.0,
                ),
                "verified": 0,
                "reason": (
                    "Resolved through a unique title alias. "
                    "Title-only identity remains unverified."
                ),
            }

    return {
        "condition_id": "",
        "method": "UNMAPPED",
        "confidence": 0.0,
        "verified": 0,
        "reason": (
            "No canonical registry identifier or unique alias matched."
        ),
    }


def build_enrichments(
    selected_sources: set[str],
    source_limit: int,
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, int]],
]:
    registry = load_registry()
    alias_indexes = load_alias_indexes()
    direct_indexes = build_direct_registry_indexes(
        registry
    )

    source_rows = load_source_rows(
        selected_sources=selected_sources,
        source_limit=source_limit,
    )

    now_iso = utc_now_iso()
    enrichments: list[dict[str, Any]] = []

    summaries: dict[
        str,
        dict[str, int],
    ] = defaultdict(
        lambda: defaultdict(int)
    )

    total_rows = len(source_rows)

    for index, source in enumerate(
        source_rows,
        start=1,
    ):
        if (
            index == 1
            or index % 10_000 == 0
            or index == total_rows
        ):
            print(
                f"Enriching source identities: "
                f"{index:,}/{total_rows:,}"
            )

        source_table = source[
            "source_table"
        ]

        summaries[
            source_table
        ][
            "source_rows_scanned"
        ] += 1

        resolution = resolve_identity(
            source=source,
            registry=registry,
            direct_indexes=direct_indexes,
            alias_indexes=alias_indexes,
        )

        canonical_condition_id = resolution[
            "condition_id"
        ]

        canonical = registry.get(
            canonical_condition_id,
            {},
        )

        verified = safe_int(
            resolution["verified"]
        )

        actionable_identity = int(
            bool(canonical_condition_id)
            and verified == 1
            and safe_int(
                canonical.get("verified")
            )
            == 1
        )

        if canonical_condition_id:
            enrichment_status = (
                "VERIFIED"
                if actionable_identity
                else "ENRICHED_UNVERIFIED"
            )

            summaries[
                source_table
            ][
                "enriched_rows"
            ] += 1

        else:
            enrichment_status = (
                "UNRESOLVED"
            )

            summaries[
                source_table
            ][
                "unresolved_rows"
            ] += 1

        if verified:
            summaries[
                source_table
            ][
                "verified_rows"
            ] += 1

        if actionable_identity:
            summaries[
                source_table
            ][
                "actionable_identity_rows"
            ] += 1

        method = resolution["method"]

        method_counters = {
            "EXACT_CONDITION_ID": (
                "exact_condition_matches"
            ),
            "EXACT_TOKEN_ID": (
                "exact_token_matches"
            ),
            "EXACT_GAMMA_MARKET_ID": (
                "exact_market_id_matches"
            ),
            "EXACT_MARKET_SLUG": (
                "exact_slug_matches"
            ),
            "UNIQUE_EVENT_SLUG": (
                "exact_slug_matches"
            ),
            "EXACT_NORMALIZED_TITLE": (
                "title_matches"
            ),
            "REGISTRY_ALIAS_TITLE": (
                "title_matches"
            ),
        }

        counter = method_counters.get(
            method
        )

        if counter:
            summaries[
                source_table
            ][counter] += 1

        enrichment_key = (
            f"{source_table}:"
            f"{source['row_id']}"
        )

        source_identity = {
            "condition_id": source[
                "condition_id"
            ],
            "market_id": source[
                "market_id"
            ],
            "asset_id": source[
                "asset_id"
            ],
            "market_slug": source[
                "market_slug"
            ],
            "event_slug": source[
                "event_slug"
            ],
            "title": source[
                "title"
            ],
        }

        canonical_identity = {
            "condition_id": (
                canonical_condition_id
            ),
            "gamma_market_id": clean_text(
                canonical.get(
                    "gamma_market_id"
                )
            ),
            "gamma_event_id": clean_text(
                canonical.get(
                    "gamma_event_id"
                )
            ),
            "market_slug": clean_text(
                canonical.get(
                    "market_slug"
                )
            ),
            "event_slug": clean_text(
                canonical.get(
                    "event_slug"
                )
            ),
            "question": clean_text(
                canonical.get(
                    "question"
                )
            ),
            "category": clean_text(
                canonical.get(
                    "category"
                )
            ),
            "token_id_yes": clean_text(
                canonical.get(
                    "token_id_yes"
                )
            ),
            "token_id_no": clean_text(
                canonical.get(
                    "token_id_no"
                )
            ),
        }

        enrichments.append(
            {
                "enrichment_key": (
                    enrichment_key
                ),
                "source_table": (
                    source_table
                ),
                "source_row_identifier": (
                    source["row_id"]
                ),
                "source_condition_id": (
                    source["condition_id"]
                ),
                "source_market_id": (
                    source["market_id"]
                ),
                "source_asset_id": (
                    source["asset_id"]
                ),
                "source_market_slug": (
                    source["market_slug"]
                ),
                "source_event_slug": (
                    source["event_slug"]
                ),
                "source_title": (
                    source["title"]
                ),
                "canonical_condition_id": (
                    canonical_condition_id
                ),
                "gamma_market_id": (
                    canonical_identity[
                        "gamma_market_id"
                    ]
                ),
                "gamma_event_id": (
                    canonical_identity[
                        "gamma_event_id"
                    ]
                ),
                "market_slug": (
                    canonical_identity[
                        "market_slug"
                    ]
                ),
                "event_slug": (
                    canonical_identity[
                        "event_slug"
                    ]
                ),
                "question": (
                    canonical_identity[
                        "question"
                    ]
                ),
                "category": (
                    canonical_identity[
                        "category"
                    ]
                ),
                "token_id_yes": (
                    canonical_identity[
                        "token_id_yes"
                    ]
                ),
                "token_id_no": (
                    canonical_identity[
                        "token_id_no"
                    ]
                ),
                "outcome_yes": clean_text(
                    canonical.get(
                        "outcome_yes"
                    )
                ),
                "outcome_no": clean_text(
                    canonical.get(
                        "outcome_no"
                    )
                ),
                "market_start_at": clean_text(
                    canonical.get(
                        "market_start_at"
                    )
                ),
                "market_end_at": clean_text(
                    canonical.get(
                        "market_end_at"
                    )
                ),
                "mapping_method": method,
                "mapping_confidence": (
                    float(
                        resolution[
                            "confidence"
                        ]
                    )
                ),
                "verified": verified,
                "actionable_identity": (
                    actionable_identity
                ),
                "enrichment_status": (
                    enrichment_status
                ),
                "resolution_reason": (
                    resolution["reason"]
                ),
                "source_identity_json": (
                    stable_json(
                        source_identity
                    )
                ),
                "canonical_identity_json": (
                    stable_json(
                        canonical_identity
                    )
                ),
                "metadata_json": stable_json(
                    {
                        "engine_version": (
                            "1.0"
                        ),
                        "registry_verified": (
                            safe_int(
                                canonical.get(
                                    "verified"
                                )
                            )
                        ),
                    }
                ),
                "enriched_at": now_iso,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )

    return enrichments, summaries


# =============================================================================
# SAVE
# =============================================================================


ENRICHMENT_COLUMNS = [
    "enrichment_key",
    "source_table",
    "source_row_identifier",
    "source_condition_id",
    "source_market_id",
    "source_asset_id",
    "source_market_slug",
    "source_event_slug",
    "source_title",
    "canonical_condition_id",
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
    "mapping_method",
    "mapping_confidence",
    "verified",
    "actionable_identity",
    "enrichment_status",
    "resolution_reason",
    "source_identity_json",
    "canonical_identity_json",
    "metadata_json",
    "enriched_at",
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
        f'INSERT INTO "{table_name}" '
        f'({names}) VALUES ({placeholders})'
    )


def save_enrichments(
    enrichments: list[dict[str, Any]],
    summaries: dict[str, dict[str, int]],
) -> int:
    connection = connect_database()

    enrichment_query = build_insert_query(
        "market_identity_enrichments",
        ENRICHMENT_COLUMNS,
    )

    now_iso = utc_now_iso()

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        connection.execute(
            "DELETE FROM market_identity_enrichments"
        )

        connection.execute(
            "DELETE FROM market_identity_source_summary"
        )

        for row in enrichments:
            connection.execute(
                enrichment_query,
                tuple(
                    row[column]
                    for column in ENRICHMENT_COLUMNS
                ),
            )

        for source_table, summary in summaries.items():
            connection.execute(
                """
                INSERT INTO market_identity_source_summary (
                    source_table,
                    source_rows_scanned,
                    enriched_rows,
                    verified_rows,
                    actionable_identity_rows,
                    unresolved_rows,
                    exact_condition_matches,
                    exact_token_matches,
                    exact_market_id_matches,
                    exact_slug_matches,
                    title_matches,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    source_table,
                    summary.get(
                        "source_rows_scanned",
                        0,
                    ),
                    summary.get(
                        "enriched_rows",
                        0,
                    ),
                    summary.get(
                        "verified_rows",
                        0,
                    ),
                    summary.get(
                        "actionable_identity_rows",
                        0,
                    ),
                    summary.get(
                        "unresolved_rows",
                        0,
                    ),
                    summary.get(
                        "exact_condition_matches",
                        0,
                    ),
                    summary.get(
                        "exact_token_matches",
                        0,
                    ),
                    summary.get(
                        "exact_market_id_matches",
                        0,
                    ),
                    summary.get(
                        "exact_slug_matches",
                        0,
                    ),
                    summary.get(
                        "title_matches",
                        0,
                    ),
                    now_iso,
                ),
            )

        connection.commit()

        return len(enrichments)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =============================================================================
# RUN LOGGING
# =============================================================================


def start_run() -> tuple[int, datetime]:
    started_at = utc_now()
    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO market_identity_enrichment_runs (
                started_at,
                status
            )
            VALUES (?, 'RUNNING')
            """,
            (started_at.isoformat(),),
        )

        connection.commit()

        return cursor.lastrowid, started_at

    finally:
        connection.close()


def finish_run(
    run_id: int,
    started_at: datetime,
    status: str,
    enrichments: list[dict[str, Any]],
    error_message: str = "",
) -> None:
    finished_at = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE market_identity_enrichment_runs
            SET
                finished_at=?,
                elapsed_seconds=?,
                source_rows_scanned=?,
                enriched_rows=?,
                verified_rows=?,
                actionable_identity_rows=?,
                unresolved_rows=?,
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
                len(enrichments),
                sum(
                    1
                    for row in enrichments
                    if row[
                        "enrichment_status"
                    ]
                    != "UNRESOLVED"
                ),
                sum(
                    1
                    for row in enrichments
                    if row["verified"]
                ),
                sum(
                    1
                    for row in enrichments
                    if row[
                        "actionable_identity"
                    ]
                ),
                sum(
                    1
                    for row in enrichments
                    if row[
                        "enrichment_status"
                    ]
                    == "UNRESOLVED"
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
    enrichments: list[dict[str, Any]],
    summaries: dict[str, dict[str, int]],
    display_limit: int,
) -> None:
    print()
    print("=" * 120)
    print("MARKET IDENTITY ENRICHMENT SUMMARY")
    print("=" * 120)

    print(
        f"Source rows scanned:            "
        f"{len(enrichments):,}"
    )

    print(
        f"Enriched rows:                  "
        f"{sum(1 for row in enrichments if row['enrichment_status'] != 'UNRESOLVED'):,}"
    )

    print(
        f"Verified rows:                  "
        f"{sum(1 for row in enrichments if row['verified']):,}"
    )

    print(
        f"Actionable identity rows:       "
        f"{sum(1 for row in enrichments if row['actionable_identity']):,}"
    )

    print(
        f"Unresolved rows:                "
        f"{sum(1 for row in enrichments if row['enrichment_status'] == 'UNRESOLVED'):,}"
    )

    print()
    print("SOURCE TABLE BREAKDOWN")

    for source_table in sorted(
        summaries
    ):
        summary = summaries[
            source_table
        ]

        print(
            f"{source_table:<32} "
            f"scanned={summary.get('source_rows_scanned', 0):>8,} | "
            f"enriched={summary.get('enriched_rows', 0):>8,} | "
            f"verified={summary.get('verified_rows', 0):>8,} | "
            f"unresolved={summary.get('unresolved_rows', 0):>8,}"
        )

    unresolved = [
        row
        for row in enrichments
        if row[
            "enrichment_status"
        ]
        == "UNRESOLVED"
    ]

    print()
    print("TOP UNRESOLVED IDENTITIES")

    for index, row in enumerate(
        unresolved[:display_limit],
        start=1,
    ):
        print()
        print("-" * 120)

        print(
            f"{index}. "
            f"{row['source_title'] or row['source_condition_id'] or row['source_asset_id']}"
        )

        print("-" * 120)

        print(
            f"Source:                         "
            f"{row['source_table']}"
        )

        print(
            f"Condition ID:                   "
            f"{row['source_condition_id'] or '-'}"
        )

        print(
            f"Asset/token ID:                 "
            f"{row['source_asset_id'] or '-'}"
        )

        print(
            f"Reason:                         "
            f"{row['resolution_reason']}"
        )


# =============================================================================
# MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Enrich downstream Polymarket records with canonical market "
            "identities resolved through the Market Identifier Registry."
        )
    )

    parser.add_argument(
        "--source",
        action="append",
        choices=[
            spec["table"]
            for spec in SOURCE_TABLE_SPECS
        ],
        help=(
            "Source table to enrich. May be repeated. "
            "Default: all available source tables."
        ),
    )

    parser.add_argument(
        "--source-limit",
        type=int,
        default=DEFAULT_SOURCE_LIMIT,
        help=(
            "Optional per-table row limit for controlled tests. "
            "Zero means no limit."
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

    selected_sources = set(
        arguments.source
        or []
    )

    source_limit = max(
        arguments.source_limit,
        0,
    )

    print()
    print("=" * 120)
    print("POLYMARKET MARKET IDENTITY ENRICHMENT ENGINE v1")
    print("=" * 120)

    print(f"Database:                    {DB}")

    print(
        f"Sources:                     "
        f"{', '.join(sorted(selected_sources)) if selected_sources else 'ALL AVAILABLE'}"
    )

    print(
        f"Per-source row limit:        "
        f"{source_limit or 'NONE'}"
    )

    print(
        "Resolution priority:        "
        "CONDITION -> TOKEN -> MARKET ID -> SLUG -> UNIQUE ALIAS -> TITLE"
    )

    print(
        "Actionable identity rule:   "
        "CANONICAL REGISTRY + VERIFIED NON-TITLE MATCH"
    )

    print("=" * 120)

    create_tables()

    run_id, started_at = start_run()

    enrichments: list[dict[str, Any]] = []
    summaries: dict[
        str,
        dict[str, int],
    ] = {}

    try:
        (
            enrichments,
            summaries,
        ) = build_enrichments(
            selected_sources=selected_sources,
            source_limit=source_limit,
        )

        if not enrichments:
            raise RuntimeError(
                "No source records were available for enrichment."
            )

        save_enrichments(
            enrichments=enrichments,
            summaries=summaries,
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            enrichments=enrichments,
        )

        display_summary(
            enrichments=enrichments,
            summaries=summaries,
            display_limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 120)
        print("MARKET IDENTITY ENRICHMENT COMPLETE")
        print("=" * 120)

        print(
            "Enriched identities:         "
            "market_identity_enrichments"
        )

        print(
            "Per-source summary:          "
            "market_identity_source_summary"
        )

        print(
            "Run history:                "
            "market_identity_enrichment_runs"
        )

        print()
        print(
            "Next step: update Opportunity Ranking to join "
            "market_predictions through market_identity_enrichments "
            "before requiring direct Gamma condition-ID equality."
        )

        print("=" * 120)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            enrichments=enrichments,
            error_message=(
                f"{type(error).__name__}: {error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()