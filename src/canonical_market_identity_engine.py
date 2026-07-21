from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_DISPLAY_LIMIT = 30
POLYMARKET_EVENT_BASE = "https://polymarket.com/event"


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


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    return clean_text(value).lower() in {
        "1",
        "true",
        "yes",
        "y",
        "active",
        "open",
    }


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

    if isinstance(value, (dict, list, int, float, bool)):
        return value

    raw = clean_text(value)

    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def parse_datetime(value: Any) -> datetime | None:
    raw = clean_text(value)

    if not raw:
        return None

    normalized = raw.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def build_polymarket_url(
    event_slug: str,
    market_slug: str,
) -> tuple[str, str]:
    if event_slug:
        return (
            f"{POLYMARKET_EVENT_BASE}/"
            f"{quote(event_slug, safe='-')}",
            "EVENT_SLUG",
        )

    if market_slug:
        return (
            f"{POLYMARKET_EVENT_BASE}/"
            f"{quote(market_slug, safe='-')}",
            "MARKET_SLUG_EVENT_ROUTE",
        )

    return "", "MISSING"


def determine_time_state(
    start_at: datetime | None,
    end_at: datetime | None,
    active: bool,
    closed: bool,
    archived: bool,
) -> dict[str, Any]:
    now = utc_now()

    if closed or archived:
        status = "CLOSED"
        target = end_at

    elif end_at is not None and now >= end_at:
        status = "RESOLUTION PENDING"
        target = end_at

    elif active:
        status = "OPEN"
        target = end_at or start_at

    else:
        status = "INACTIVE"
        target = end_at or start_at

    seconds = (
        int((target - now).total_seconds())
        if target is not None
        else None
    )

    if status == "CLOSED":
        display = "CLOSED"

    elif status == "RESOLUTION PENDING":
        display = "RESOLUTION PENDING"

    elif seconds is None:
        display = "UNKNOWN"

    elif seconds < 0:
        display = "ENDED"

    else:
        days, remainder = divmod(seconds, 86_400)
        hours, remainder = divmod(remainder, 3_600)
        minutes = remainder // 60

        if days > 0:
            display = (
                f"T-{days}d "
                f"{hours:02d}h "
                f"{minutes:02d}m"
            )
        elif hours > 0:
            display = (
                f"T-{hours:02d}h "
                f"{minutes:02d}m"
            )
        else:
            display = f"T-{minutes:02d}m"

    return {
        "time_status": status,
        "t_minus_target_at": (
            target.isoformat()
            if target is not None
            else None
        ),
        "t_minus_seconds": seconds,
        "t_minus_display": display,
    }


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
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
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
            "gamma_markets",
        )

        require_table(
            connection,
            "gamma_market_outcomes",
        )

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS canonical_market_identities (
                condition_id TEXT PRIMARY KEY,

                gamma_market_id TEXT NOT NULL,
                gamma_event_id TEXT,

                question_id TEXT,
                question TEXT NOT NULL,
                description TEXT,

                market_slug TEXT,
                event_slug TEXT,

                category TEXT,
                subcategory TEXT,
                market_type TEXT,

                yes_token_id TEXT,
                no_token_id TEXT,

                yes_outcome_name TEXT,
                no_outcome_name TEXT,

                yes_implied_price REAL,
                no_implied_price REAL,

                polymarket_url TEXT,
                url_source TEXT,

                start_time TEXT,
                end_time TEXT,
                game_start_time TEXT,

                time_status TEXT,
                t_minus_target_at TEXT,
                t_minus_seconds INTEGER,
                t_minus_display TEXT,

                active INTEGER NOT NULL DEFAULT 0,
                closed INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                resolved INTEGER NOT NULL DEFAULT 0,
                restricted INTEGER NOT NULL DEFAULT 0,
                accepting_orders INTEGER NOT NULL DEFAULT 0,

                liquidity REAL NOT NULL DEFAULT 0,
                volume REAL NOT NULL DEFAULT 0,
                volume_24h REAL NOT NULL DEFAULT 0,
                open_interest REAL NOT NULL DEFAULT 0,
                spread REAL,

                mapping_method TEXT,
                mapping_confidence REAL NOT NULL DEFAULT 0,
                registry_verified INTEGER NOT NULL DEFAULT 0,

                identity_complete INTEGER NOT NULL DEFAULT 0,
                tradable_identity INTEGER NOT NULL DEFAULT 0,

                missing_fields_json TEXT,
                source_tables_json TEXT,
                metadata_json TEXT,

                first_built_at TEXT NOT NULL,
                last_built_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_canonical_market_identities_tradable
            ON canonical_market_identities(
                tradable_identity DESC,
                active DESC,
                mapping_confidence DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_canonical_market_identities_event
            ON canonical_market_identities(
                gamma_event_id,
                event_slug
            );

            CREATE INDEX IF NOT EXISTS
            idx_canonical_market_identities_tokens
            ON canonical_market_identities(
                yes_token_id,
                no_token_id
            );

            CREATE TABLE IF NOT EXISTS canonical_market_identity_aliases (
                alias_key TEXT PRIMARY KEY,

                condition_id TEXT NOT NULL,

                alias_type TEXT NOT NULL,
                alias_value TEXT NOT NULL,
                normalized_alias_value TEXT NOT NULL,

                verified INTEGER NOT NULL DEFAULT 0,
                confidence REAL NOT NULL DEFAULT 0,

                source_table TEXT NOT NULL,
                source_row_identifier TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(condition_id)
                    REFERENCES canonical_market_identities(condition_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
            idx_canonical_market_identity_aliases_lookup
            ON canonical_market_identity_aliases(
                alias_type,
                normalized_alias_value,
                verified DESC,
                confidence DESC
            );

            CREATE TABLE IF NOT EXISTS canonical_market_identity_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                registry_rows_loaded INTEGER NOT NULL DEFAULT 0,
                identities_saved INTEGER NOT NULL DEFAULT 0,
                complete_identities INTEGER NOT NULL DEFAULT 0,
                tradable_identities INTEGER NOT NULL DEFAULT 0,
                aliases_saved INTEGER NOT NULL DEFAULT 0,

                missing_url_count INTEGER NOT NULL DEFAULT 0,
                missing_time_count INTEGER NOT NULL DEFAULT 0,
                missing_token_count INTEGER NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            );
            """
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# LOADERS
# =============================================================================


def load_registry_rows() -> list[dict[str, Any]]:
    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM market_identifier_registry
            """
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def load_gamma_markets() -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM gamma_markets
            WHERE condition_id IS NOT NULL
              AND TRIM(condition_id) <> ''
            """
        ).fetchall()

        return {
            normalize_identifier(
                row["condition_id"]
            ): dict(row)
            for row in rows
        }

    finally:
        connection.close()


def load_outcomes() -> dict[
    str,
    list[dict[str, Any]],
]:
    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM gamma_market_outcomes
            """
        ).fetchall()

        output: dict[
            str,
            list[dict[str, Any]],
        ] = {}

        for row in rows:
            condition_id = normalize_identifier(
                row["condition_id"]
            )

            if not condition_id:
                continue

            output.setdefault(
                condition_id,
                [],
            ).append(
                dict(row)
            )

        return output

    finally:
        connection.close()


def load_registry_aliases() -> list[dict[str, Any]]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "market_identifier_aliases",
        ):
            return []

        rows = connection.execute(
            """
            SELECT *
            FROM market_identifier_aliases
            """
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


# =============================================================================
# BUILD
# =============================================================================


def select_binary_outcomes(
    outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    yes_row: dict[str, Any] = {}
    no_row: dict[str, Any] = {}

    for row in outcomes:
        name = clean_text(
            row.get("outcome_name")
            or row.get("outcome")
        )

        normalized = name.lower()
        index = safe_int(
            row.get("outcome_index"),
            -1,
        )

        if (
            normalized == "yes"
            or index == 0
        ) and not yes_row:
            yes_row = row

        elif (
            normalized == "no"
            or index == 1
        ) and not no_row:
            no_row = row

    return {
        "yes_token_id": clean_text(
            yes_row.get("token_id")
        ),
        "no_token_id": clean_text(
            no_row.get("token_id")
        ),
        "yes_outcome_name": clean_text(
            yes_row.get("outcome_name")
            or yes_row.get("outcome")
        ),
        "no_outcome_name": clean_text(
            no_row.get("outcome_name")
            or no_row.get("outcome")
        ),
        "yes_implied_price": (
            safe_float(
                yes_row.get("implied_price")
                or yes_row.get("price")
            )
            if yes_row
            else None
        ),
        "no_implied_price": (
            safe_float(
                no_row.get("implied_price")
                or no_row.get("price")
            )
            if no_row
            else None
        ),
    }


def build_identities() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    int,
]:
    registry_rows = load_registry_rows()
    gamma_markets = load_gamma_markets()
    outcomes_lookup = load_outcomes()
    registry_aliases = load_registry_aliases()

    now_iso = utc_now_iso()

    identities: list[dict[str, Any]] = []
    known_conditions: set[str] = set()

    for registry in registry_rows:
        condition_id = normalize_identifier(
            registry.get("condition_id")
        )

        if not condition_id:
            continue

        market = gamma_markets.get(
            condition_id,
            {},
        )

        if not market:
            continue

        known_conditions.add(condition_id)

        outcomes = select_binary_outcomes(
            outcomes_lookup.get(
                condition_id,
                [],
            )
        )

        event_slug = clean_text(
            registry.get("event_slug")
            or market.get("event_slug")
        )

        market_slug = clean_text(
            registry.get("market_slug")
            or market.get("slug")
        )

        polymarket_url, url_source = (
            build_polymarket_url(
                event_slug=event_slug,
                market_slug=market_slug,
            )
        )

        start_time = parse_datetime(
            market.get("start_time")
            or registry.get("market_start_at")
        )

        end_time = parse_datetime(
            market.get("end_time")
            or registry.get("market_end_at")
        )

        active = safe_bool(
            market.get("active")
        )

        closed = safe_bool(
            market.get("closed")
        )

        archived = safe_bool(
            market.get("archived")
        )

        time_state = determine_time_state(
            start_at=start_time,
            end_at=end_time,
            active=active,
            closed=closed,
            archived=archived,
        )

        gamma_market_id = clean_text(
            market.get("gamma_market_id")
            or registry.get("gamma_market_id")
        )

        question = clean_text(
            market.get("question")
            or registry.get("question")
        )

        missing_fields: list[str] = []

        required_identity_fields = {
            "condition_id": condition_id,
            "gamma_market_id": gamma_market_id,
            "question": question,
            "market_slug_or_event_slug": (
                event_slug or market_slug
            ),
            "yes_token_id": outcomes[
                "yes_token_id"
            ],
            "no_token_id": outcomes[
                "no_token_id"
            ],
        }

        for field_name, field_value in required_identity_fields.items():
            if not field_value:
                missing_fields.append(
                    field_name
                )

        identity_complete = int(
            not missing_fields
        )

        accepting_orders = safe_bool(
            market.get("accepting_orders")
        )

        restricted = safe_bool(
            market.get("restricted")
        )

        registry_verified = safe_int(
            registry.get("verified")
        )

        tradable_identity = int(
            identity_complete
            and registry_verified == 1
            and active
            and not closed
            and not archived
            and accepting_orders
            and bool(polymarket_url)
        )

        source_tables = parse_json_value(
            registry.get(
                "source_tables_json"
            )
        )

        if not isinstance(source_tables, list):
            source_tables = []

        identities.append(
            {
                "condition_id": condition_id,
                "gamma_market_id": gamma_market_id,
                "gamma_event_id": clean_text(
                    market.get("gamma_event_id")
                    or registry.get(
                        "gamma_event_id"
                    )
                ),
                "question_id": clean_text(
                    market.get("question_id")
                ),
                "question": (
                    question
                    or "Untitled market"
                ),
                "description": clean_text(
                    market.get("description")
                ),
                "market_slug": market_slug,
                "event_slug": event_slug,
                "category": clean_text(
                    market.get("category")
                    or registry.get("category")
                ),
                "subcategory": "",
                "market_type": clean_text(
                    market.get("market_type")
                ),
                **outcomes,
                "polymarket_url": polymarket_url,
                "url_source": url_source,
                "start_time": (
                    start_time.isoformat()
                    if start_time
                    else None
                ),
                "end_time": (
                    end_time.isoformat()
                    if end_time
                    else None
                ),
                "game_start_time": clean_text(
                    market.get(
                        "game_start_time"
                    )
                ),
                **time_state,
                "active": int(active),
                "closed": int(closed),
                "archived": int(archived),
                "resolved": safe_int(
                    market.get("resolved")
                ),
                "restricted": int(restricted),
                "accepting_orders": int(
                    accepting_orders
                ),
                "liquidity": safe_float(
                    market.get("liquidity")
                ),
                "volume": safe_float(
                    market.get("volume")
                ),
                "volume_24h": safe_float(
                    market.get("volume_24h")
                ),
                "open_interest": safe_float(
                    market.get("open_interest")
                ),
                "spread": (
                    safe_float(
                        market.get("spread")
                    )
                    if market.get("spread")
                    is not None
                    else None
                ),
                "mapping_method": clean_text(
                    registry.get(
                        "mapping_method"
                    )
                ),
                "mapping_confidence": (
                    safe_float(
                        registry.get(
                            "mapping_confidence"
                        )
                    )
                ),
                "registry_verified": (
                    registry_verified
                ),
                "identity_complete": (
                    identity_complete
                ),
                "tradable_identity": (
                    tradable_identity
                ),
                "missing_fields_json": (
                    stable_json(
                        missing_fields
                    )
                ),
                "source_tables_json": (
                    stable_json(
                        source_tables
                    )
                ),
                "metadata_json": stable_json(
                    {
                        "engine_version": "1.0",
                        "time_status": (
                            time_state[
                                "time_status"
                            ]
                        ),
                        "url_source": (
                            url_source
                        ),
                    }
                ),
                "first_built_at": now_iso,
                "last_built_at": now_iso,
            }
        )

    aliases: list[dict[str, Any]] = []

    for row in registry_aliases:
        condition_id = normalize_identifier(
            row.get("condition_id")
        )

        if condition_id not in known_conditions:
            continue

        alias_type = clean_text(
            row.get("alias_type")
        ).upper()

        alias_value = clean_text(
            row.get("alias_value")
        )

        normalized_alias_value = clean_text(
            row.get(
                "normalized_alias_value"
            )
        ) or normalize_identifier(
            alias_value
        )

        if not alias_type or not alias_value:
            continue

        alias_key = (
            f"{condition_id}:"
            f"{alias_type}:"
            f"{normalized_alias_value}:"
            f"{clean_text(row.get('source_table'))}"
        )

        aliases.append(
            {
                "alias_key": alias_key,
                "condition_id": condition_id,
                "alias_type": alias_type,
                "alias_value": alias_value,
                "normalized_alias_value": (
                    normalized_alias_value
                ),
                "verified": safe_int(
                    row.get("verified")
                ),
                "confidence": safe_float(
                    row.get("confidence")
                ),
                "source_table": clean_text(
                    row.get("source_table")
                ),
                "source_row_identifier": "",
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )

    identities.sort(
        key=lambda row: (
            row["tradable_identity"],
            row["identity_complete"],
            row["mapping_confidence"],
            row["liquidity"],
        ),
        reverse=True,
    )

    return (
        identities,
        aliases,
        len(registry_rows),
    )


# =============================================================================
# SAVE
# =============================================================================


IDENTITY_COLUMNS = [
    "condition_id",
    "gamma_market_id",
    "gamma_event_id",
    "question_id",
    "question",
    "description",
    "market_slug",
    "event_slug",
    "category",
    "subcategory",
    "market_type",
    "yes_token_id",
    "no_token_id",
    "yes_outcome_name",
    "no_outcome_name",
    "yes_implied_price",
    "no_implied_price",
    "polymarket_url",
    "url_source",
    "start_time",
    "end_time",
    "game_start_time",
    "time_status",
    "t_minus_target_at",
    "t_minus_seconds",
    "t_minus_display",
    "active",
    "closed",
    "archived",
    "resolved",
    "restricted",
    "accepting_orders",
    "liquidity",
    "volume",
    "volume_24h",
    "open_interest",
    "spread",
    "mapping_method",
    "mapping_confidence",
    "registry_verified",
    "identity_complete",
    "tradable_identity",
    "missing_fields_json",
    "source_tables_json",
    "metadata_json",
    "first_built_at",
    "last_built_at",
]


ALIAS_COLUMNS = [
    "alias_key",
    "condition_id",
    "alias_type",
    "alias_value",
    "normalized_alias_value",
    "verified",
    "confidence",
    "source_table",
    "source_row_identifier",
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


def save_results(
    identities: list[dict[str, Any]],
    aliases: list[dict[str, Any]],
) -> tuple[int, int]:
    connection = connect_database()

    identity_query = build_insert_query(
        "canonical_market_identities",
        IDENTITY_COLUMNS,
    )

    alias_query = build_insert_query(
        "canonical_market_identity_aliases",
        ALIAS_COLUMNS,
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

        connection.execute(
            "DELETE FROM canonical_market_identity_aliases"
        )

        connection.execute(
            "DELETE FROM canonical_market_identities"
        )

        for row in identities:
            connection.execute(
                identity_query,
                tuple(
                    row[column]
                    for column in IDENTITY_COLUMNS
                ),
            )

        for row in aliases:
            connection.execute(
                alias_query,
                tuple(
                    row[column]
                    for column in ALIAS_COLUMNS
                ),
            )

        connection.commit()

        return len(identities), len(aliases)

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
            INSERT INTO canonical_market_identity_runs (
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
    registry_rows_loaded: int,
    identities: list[dict[str, Any]],
    aliases_saved: int,
    error_message: str = "",
) -> None:
    finished_at = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE canonical_market_identity_runs
            SET
                finished_at=?,
                elapsed_seconds=?,
                registry_rows_loaded=?,
                identities_saved=?,
                complete_identities=?,
                tradable_identities=?,
                aliases_saved=?,
                missing_url_count=?,
                missing_time_count=?,
                missing_token_count=?,
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
                registry_rows_loaded,
                len(identities),
                sum(
                    1
                    for row in identities
                    if row["identity_complete"]
                ),
                sum(
                    1
                    for row in identities
                    if row["tradable_identity"]
                ),
                aliases_saved,
                sum(
                    1
                    for row in identities
                    if not row["polymarket_url"]
                ),
                sum(
                    1
                    for row in identities
                    if not row["t_minus_target_at"]
                ),
                sum(
                    1
                    for row in identities
                    if (
                        not row["yes_token_id"]
                        or not row["no_token_id"]
                    )
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
    identities: list[dict[str, Any]],
    aliases: list[dict[str, Any]],
    registry_rows_loaded: int,
    display_limit: int,
) -> None:
    print()
    print("=" * 122)
    print("CANONICAL MARKET IDENTITY SUMMARY")
    print("=" * 122)

    print(
        f"Registry rows loaded:            "
        f"{registry_rows_loaded:,}"
    )

    print(
        f"Canonical identities saved:      "
        f"{len(identities):,}"
    )

    print(
        f"Complete identities:             "
        f"{sum(1 for row in identities if row['identity_complete']):,}"
    )

    print(
        f"Tradable identities:             "
        f"{sum(1 for row in identities if row['tradable_identity']):,}"
    )

    print(
        f"Aliases saved:                   "
        f"{len(aliases):,}"
    )

    print(
        f"Missing URLs:                    "
        f"{sum(1 for row in identities if not row['polymarket_url']):,}"
    )

    print(
        f"Missing time targets:            "
        f"{sum(1 for row in identities if not row['t_minus_target_at']):,}"
    )

    print(
        f"Missing binary token pairs:      "
        f"{sum(1 for row in identities if not row['yes_token_id'] or not row['no_token_id']):,}"
    )

    print("=" * 122)

    print()
    print("TOP TRADABLE CANONICAL IDENTITIES")

    tradable = [
        row
        for row in identities
        if row["tradable_identity"]
    ]

    for index, row in enumerate(
        tradable[:display_limit],
        start=1,
    ):
        print()
        print("-" * 122)

        print(
            f"{index}. "
            f"{row['question']}"
        )

        print("-" * 122)

        print(
            f"Condition ID:                   "
            f"{row['condition_id']}"
        )

        print(
            f"Gamma market / event:           "
            f"{row['gamma_market_id']} "
            f"/ {row['gamma_event_id'] or '-'}"
        )

        print(
            f"YES / NO token IDs:             "
            f"{row['yes_token_id'] or '-'} "
            f"/ {row['no_token_id'] or '-'}"
        )

        print(
            f"Status / T-minus:               "
            f"{row['time_status']} "
            f"/ {row['t_minus_display']}"
        )

        print(
            f"Liquidity / volume:             "
            f"${row['liquidity']:,.2f} "
            f"/ ${row['volume']:,.2f}"
        )

        print(
            f"Polymarket URL:                 "
            f"{row['polymarket_url']}"
        )


# =============================================================================
# MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a single canonical market identity layer from the "
            "verified identifier registry, Gamma markets, Gamma outcomes, "
            "direct Polymarket URLs and market timing."
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
    arguments = parse_arguments()

    print()
    print("=" * 122)
    print("POLYMARKET CANONICAL MARKET IDENTITY ENGINE v1")
    print("=" * 122)

    print(f"Database:                    {DB}")

    print(
        "Purpose:                     "
        "ONE VERIFIED IDENTITY BUNDLE FOR ALL DOWNSTREAM ENGINES"
    )

    print(
        "Inputs:                      "
        "IDENTIFIER REGISTRY + GAMMA MARKETS + GAMMA OUTCOMES"
    )

    print(
        "Tradable rule:               "
        "COMPLETE + VERIFIED + ACTIVE + ACCEPTING ORDERS + URL"
    )

    print("=" * 122)

    create_tables()

    run_id, started_at = start_run()

    identities: list[dict[str, Any]] = []
    aliases: list[dict[str, Any]] = []
    registry_rows_loaded = 0
    aliases_saved = 0

    try:
        (
            identities,
            aliases,
            registry_rows_loaded,
        ) = build_identities()

        if not identities:
            raise RuntimeError(
                "No canonical identities could be built."
            )

        (
            _,
            aliases_saved,
        ) = save_results(
            identities=identities,
            aliases=aliases,
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            registry_rows_loaded=(
                registry_rows_loaded
            ),
            identities=identities,
            aliases_saved=aliases_saved,
        )

        display_summary(
            identities=identities,
            aliases=aliases,
            registry_rows_loaded=(
                registry_rows_loaded
            ),
            display_limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 122)
        print("CANONICAL MARKET IDENTITY ENGINE COMPLETE")
        print("=" * 122)

        print(
            "Canonical identities:       "
            "canonical_market_identities"
        )

        print(
            "Canonical aliases:          "
            "canonical_market_identity_aliases"
        )

        print(
            "Run history:                "
            "canonical_market_identity_runs"
        )

        print()
        print(
            "Next step: update Opportunity Ranking to resolve every "
            "prediction through canonical_market_identities."
        )

        print("=" * 122)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            registry_rows_loaded=(
                registry_rows_loaded
            ),
            identities=identities,
            aliases_saved=aliases_saved,
            error_message=(
                f"{type(error).__name__}: {error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()